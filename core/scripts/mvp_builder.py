#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


CORE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CORE_ROOT.parent
PROMPTS_DIR = CORE_ROOT / "prompts"
RUN_ROOT = Path(".mvp-builder") / "runs"
THREAD_CONTEXT_ENV_VARS = ("CODEX_THREAD_ID",)
MODEL_CONTEXT_ENV_VARS = ("OPENAI_MODEL", "CODEX_MODEL", "ANTHROPIC_MODEL", "CLAUDE_CODE_MODEL")
REASONING_CONTEXT_ENV_VARS = (
    "OPENAI_REASONING_EFFORT",
    "CODEX_REASONING_EFFORT",
    "ANTHROPIC_REASONING_EFFORT",
    "CLAUDE_CODE_REASONING_EFFORT",
)
QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
}

STATE_ORDER = [
    "BOOTSTRAP_AGENT",
    "REQUEST_CONTRACT",
    "RESEARCH_ARCHITECTURE",
    "IMPLEMENT_SCAFFOLD",
    "ENUMERATE_STAGES",
    "STAGE_BRAINSTORM",
    "STAGE_RESEARCH",
    "STAGE_IMPLEMENT",
    "STAGE_VERIFY",
    "FINAL_VERIFY",
    "FINAL_REPORT",
    "COMPLETED",
    "FAILED",
]

STATE_PROMPTS = {
    "BOOTSTRAP_AGENT": "bootstrap_verify_environment",
    "REQUEST_CONTRACT": "request_contract_prepare",
    "RESEARCH_ARCHITECTURE": "research_architecture",
    "IMPLEMENT_SCAFFOLD": "implement_scaffold",
    "ENUMERATE_STAGES": "enumerate_stages",
    "STAGE_BRAINSTORM": "stage_brainstorm",
    "STAGE_RESEARCH": "stage_research",
    "STAGE_IMPLEMENT": "stage_implement",
    "STAGE_VERIFY": "stage_verify",
    "FINAL_VERIFY": "final_verify",
    "FINAL_REPORT": "final_report",
    "COMPLETED": "",
    "FAILED": "",
}

PROMPT_FILES = {
    "bootstrap_verify_environment": PROMPTS_DIR / "bootstrap_verify_environment.md",
    "request_contract_prepare": PROMPTS_DIR / "request_contract_prepare.md",
    "request_contract_revise": PROMPTS_DIR / "request_contract_revise.md",
    "research_architecture": PROMPTS_DIR / "research_architecture.md",
    "implement_scaffold": PROMPTS_DIR / "implement_scaffold.md",
    "enumerate_stages": PROMPTS_DIR / "enumerate_stages.md",
    "stage_brainstorm": PROMPTS_DIR / "stage_brainstorm.md",
    "stage_research": PROMPTS_DIR / "stage_research.md",
    "stage_implement": PROMPTS_DIR / "stage_implement.md",
    "stage_verify": PROMPTS_DIR / "stage_verify.md",
    "final_verify": PROMPTS_DIR / "final_verify.md",
    "final_report": PROMPTS_DIR / "final_report.md",
    "followup_suggestion": PROMPTS_DIR / "followup_suggestion.md",
    "followup_implement": PROMPTS_DIR / "followup_implement.md",
    "followup_recommended_option": PROMPTS_DIR / "followup_recommended_option.md",
}

REPLY_CLASSES = {
    "COMPLETED",
    "RECOMMENDED_OPTION",
    "NEEDS_SUGGESTION",
    "NEEDS_IMPLEMENT_CONFIRMATION",
    "STATUS_ONLY",
    "BLOCKED_NEEDS_HUMAN",
    "HARD_ERROR",
}

RESEARCH_FLOW_STATES = {}

RESEARCH_WAIT_TIMEOUT_MINUTES = 20


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def iso_plus_minutes(value: str, minutes: int) -> str:
    base = parse_iso(value) or datetime.now(timezone.utc).astimezone()
    return (base + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "mvp-builder"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


@contextmanager
def run_lock(run_dir: Path, name: str = "runner.lock"):
    lock_path = run_dir / name
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_text(inline_value: str | None, file_value: str | None) -> str:
    if inline_value:
        return inline_value.strip()
    if file_value:
        return Path(file_value).expanduser().resolve().read_text(encoding="utf-8").strip()
    return ""


def read_optional_text(path_value: str) -> str:
    if not path_value:
        return ""
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def extract_stage_acceptance_criteria(path_value: str) -> str:
    text = read_optional_text(path_value)
    if not text:
        return ""
    match = re.search(r"^- Acceptance criteria:\s*(.+)$", text, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def request_contract_root(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "request-contract"


def detect_request_contract_mode(raw_input: str) -> str:
    stripped = raw_input.strip()
    if len(stripped) < 2:
        return "refine_for_approval"
    for open_quote, close_quote in QUOTE_PAIRS.items():
        if stripped.startswith(open_quote) and stripped.endswith(close_quote):
            return "literal_locked"
    return "refine_for_approval"


def strip_matching_outer_quotes(raw_input: str) -> str:
    stripped = raw_input.strip()
    if len(stripped) < 2:
        return stripped
    for open_quote, close_quote in QUOTE_PAIRS.items():
        if stripped.startswith(open_quote) and stripped.endswith(close_quote):
            return stripped[len(open_quote) : len(stripped) - len(close_quote)].strip()
    return stripped


def request_contract_key(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return normalized


def parse_request_contract(reply_text: str) -> dict:
    parsed: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if not current_key:
            return
        value = "\n".join(current_lines).strip()
        parsed[current_key] = value
        current_key = ""
        current_lines = []

    for raw_line in reply_text.splitlines():
        stripped = raw_line.strip()
        bullet_match = re.match(r"^-\s*([^:]+):\s*(.*)$", stripped)
        if bullet_match:
            flush()
            current_key = request_contract_key(bullet_match.group(1))
            current_lines = [bullet_match.group(2).strip()] if bullet_match.group(2).strip() else []
            continue
        if stripped and not raw_line.startswith(" ") and not stripped.startswith("-") and current_key:
            flush()
            continue
        if current_key:
            current_lines.append(stripped)
    flush()
    return parsed


def normalize_request_contract_mode(mode_value: str, raw_input: str, fallback_mode: str = "") -> str:
    cleaned = mode_value.strip().strip("`").strip().lower().replace("-", "_")
    if cleaned in {"literal_locked", "refine_for_approval"}:
        return cleaned
    if fallback_mode in {"literal_locked", "refine_for_approval"}:
        return fallback_mode
    return detect_request_contract_mode(raw_input)


def looks_like_request_contract_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "request contract",
        "input mode:",
        "approval mode:",
        "proposed approved prompt:",
        "must-haves:",
        "success criteria:",
        "approval question:",
    ]
    return all(marker in lower for marker in required_markers)


def trim_summary(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-._")
    return cleaned or "reply"


def save_reply_artifact(run_dir: Path, state_name: str, reply_text: str) -> Path:
    replies_dir = run_dir / "artifacts" / "replies"
    replies_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{safe_filename(state_name)}.md"
    path = replies_dir / filename
    path.write_text(reply_text.strip() + "\n", encoding="utf-8")
    return path


def extract_project_name(reply_text: str) -> str:
    def clean_name(value: str) -> str:
        cleaned = value.strip().strip("`").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        for pattern in [
            r"\.\s+(?=recommended architecture\b)",
            r"\.\s+(?=research-backed architecture recommendation\b)",
            r"\.\s+(?=architecture options considered\b)",
            r"\.\s+(?=short summary\b)",
            r"\.\s+(?=ordered stage list\b)",
            r"\.\s+(?=stage-by-stage plan\b)",
            r"\.\s+(?=recommended tools\b)",
            r"\.\s+(?=risks[, ]assumptions\b)",
        ]:
            cleaned = re.split(pattern, cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
        return cleaned.rstrip(".,;:)")

    patterns = [
        r"working project name:\s*[-*]?\s*`?([A-Za-z0-9][A-Za-z0-9 _.-]{1,80})`?",
        r"project name:\s*[-*]?\s*`?([A-Za-z0-9][A-Za-z0-9 _.-]{1,80})`?",
        r"proposed project name:\s*[-*]?\s*`?([A-Za-z0-9][A-Za-z0-9 _.-]{1,80})`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, reply_text, flags=re.IGNORECASE)
        if not match:
            continue
        value = clean_name(match.group(1))
        if value:
            return value
    multiline_match = re.search(
        r"working project name:\s*\n\s*[-*]\s*`?([^\n`]+)`?",
        reply_text,
        flags=re.IGNORECASE,
    )
    if multiline_match:
        value = clean_name(multiline_match.group(1))
        if value:
            return value
    return ""


def current_research_owner_key(state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    if current_state not in RESEARCH_FLOW_STATES:
        return ""
    if current_state == "STAGE_RESEARCH":
        return f"STAGE_RESEARCH:{state.get('stage_index', 0)}"
    return current_state


def research_target_label(state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    if current_state == "RESEARCH_ARCHITECTURE":
        return "Stage 2"
    if current_state == "STAGE_RESEARCH":
        stage_name = current_stage_name(state)
        if stage_name:
            return f"stage `{stage_name}`"
        return "the current stage"
    return "the current research step"


def infer_architecture_artifact_path(run_dir: Path) -> str:
    replies_dir = run_dir / "artifacts" / "replies"
    if not replies_dir.exists():
        return ""
    candidates = sorted(replies_dir.glob("*research_architecture_synthesize*.md"))
    if not candidates:
        return ""
    return str(candidates[-1].resolve())


def sync_architecture_artifact_state(run_dir: Path, state: dict) -> tuple[dict, bool]:
    current_value = str(state.get("architecture_artifact_path", "")).strip()
    if current_value:
        return state, False
    inferred = infer_architecture_artifact_path(run_dir)
    if not inferred:
        return state, False
    state["architecture_artifact_path"] = inferred
    write_json(run_dir / "state.json", state)
    return state, True


def infer_scaffold_artifact_path(run_dir: Path) -> str:
    replies_dir = run_dir / "artifacts" / "replies"
    if not replies_dir.exists():
        return ""
    candidates = sorted(replies_dir.glob("*implement_scaffold*.md"))
    if not candidates:
        return ""
    return str(candidates[-1].resolve())


def sync_scaffold_artifact_state(run_dir: Path, state: dict) -> tuple[dict, bool]:
    current_value = str(state.get("scaffold_artifact_path", "")).strip()
    if current_value:
        return state, False
    inferred = infer_scaffold_artifact_path(run_dir)
    if not inferred:
        return state, False
    state["scaffold_artifact_path"] = inferred
    write_json(run_dir / "state.json", state)
    return state, True


def sync_request_contract_artifacts(run_dir: Path, run_spec: dict, state: dict) -> tuple[dict, bool]:
    changed = False
    root = request_contract_root(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    raw_input_path = root / "raw_input.txt"
    if not raw_input_path.exists():
        raw_input_path.write_text(run_spec["raw_input"].strip() + "\n", encoding="utf-8")
    proposed_path = str(state.get("proposed_prompt_path", "")).strip()
    approved_path = str(state.get("approved_prompt_path", "")).strip()
    if proposed_path and not Path(proposed_path).exists():
        state["proposed_prompt_path"] = ""
        changed = True
    if approved_path and not Path(approved_path).exists():
        state["approved_prompt_path"] = ""
        changed = True
    if changed:
        write_json(run_dir / "state.json", state)
    return state, changed


def infer_stage_plan_artifact_path(run_dir: Path, state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    if current_state not in {"STAGE_RESEARCH", "STAGE_IMPLEMENT", "STAGE_VERIFY"}:
        return ""
    replies_dir = run_dir / "artifacts" / "replies"
    if not replies_dir.exists():
        return ""
    candidates = sorted(replies_dir.glob("*stage_brainstorm*.md"))
    if not candidates:
        return ""
    return str(candidates[-1].resolve())


def sync_stage_plan_artifact_state(run_dir: Path, state: dict) -> tuple[dict, bool]:
    current_value = str(state.get("stage_plan_artifact_path", "")).strip()
    if current_value:
        return state, False
    inferred = infer_stage_plan_artifact_path(run_dir, state)
    if not inferred:
        return state, False
    state["stage_plan_artifact_path"] = inferred
    write_json(run_dir / "state.json", state)
    return state, True


def infer_previous_stage_handoff_artifact_path(run_dir: Path, state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    stage_index = int(state.get("stage_index", 0) or 0)
    if stage_index <= 0:
        return ""
    if current_state not in {"STAGE_BRAINSTORM", "STAGE_RESEARCH", "STAGE_IMPLEMENT", "STAGE_VERIFY"}:
        return ""
    replies_dir = run_dir / "artifacts" / "replies"
    if not replies_dir.exists():
        return ""
    candidates = sorted(replies_dir.glob("*stage_verify*.md"))
    if not candidates:
        return ""
    return str(candidates[-1].resolve())


def sync_previous_stage_handoff_artifact_state(run_dir: Path, state: dict) -> tuple[dict, bool]:
    current_value = str(state.get("previous_stage_handoff_artifact_path", "")).strip()
    if current_value:
        return state, False
    inferred = infer_previous_stage_handoff_artifact_path(run_dir, state)
    if not inferred:
        return state, False
    state["previous_stage_handoff_artifact_path"] = inferred
    write_json(run_dir / "state.json", state)
    return state, True


def research_paths_for_task(task_id: str) -> dict:
    clean = task_id.strip()
    return {
        "request_path": str(RESEARCH_REQUESTS_DIR / f"{clean}.json"),
        "response_path": str(RESEARCH_RESPONSES_DIR / f"{clean}.json"),
        "artifact_path": str(RESEARCH_ARTIFACTS_DIR / f"{clean}.md"),
    }


def launch_research_dispatch(run_dir: Path, state: dict) -> tuple[str, str]:
    task_id = str(state.get("research_task_id", "")).strip()
    if not task_id:
        return "", "missing research task id"
    if not RESEARCH_QUEUE_SCRIPT.exists():
        return "", f"missing queue processor script: {RESEARCH_QUEUE_SCRIPT}"

    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"research-dispatch-{task_id}.log"
    command = [
        "python3",
        str(RESEARCH_QUEUE_SCRIPT),
        "--task-id",
        task_id,
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] launching: {' '.join(command)}\n")
        handle.flush()
        subprocess.Popen(
            command,
            cwd=str(RESEARCH_SERVICE_ROOT),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return str(log_path), ""


def extract_research_task_id(reply_text: str) -> str:
    patterns = [
        r"research task id:\s*`?([A-Za-z0-9._-]+)`?",
        r"task id:\s*`?([A-Za-z0-9._-]+)`?",
        r"research_task_id:\s*`?([A-Za-z0-9._-]+)`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, reply_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;:)")

    path_patterns = [
        r"expected artifact path:\s*`?([^`\n]+)`?",
        r"artifact path:\s*`?([^`\n]+)`?",
        r"expected response json path:\s*`?([^`\n]+)`?",
        r"response path:\s*`?([^`\n]+)`?",
    ]
    for pattern in path_patterns:
        match = re.search(pattern, reply_text, flags=re.IGNORECASE)
        if not match:
            continue
        stem = Path(match.group(1).strip()).stem
        if stem:
            return stem.rstrip(".,;:)")
    return ""


def extract_research_path(reply_text: str, path_kind: str) -> str:
    label_patterns = {
        "request": [
            r"expected request path:\s*`?([^`\n]+?\.json)`?",
            r"request path:\s*`?([^`\n]+?\.json)`?",
        ],
        "response": [
            r"expected response json path:\s*`?([^`\n]+?\.json)`?",
            r"response json path:\s*`?([^`\n]+?\.json)`?",
            r"response path:\s*`?([^`\n]+?\.json)`?",
        ],
        "artifact": [
            r"expected artifact path:\s*`?([^`\n]+?\.md)`?",
            r"artifact path:\s*`?([^`\n]+?\.md)`?",
        ],
    }
    for pattern in label_patterns.get(path_kind, []):
        match = re.search(pattern, reply_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;:)")
    return ""


def load_optional_json(path_value: str) -> dict | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def expand_home_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def first_env_value(names: tuple[str, ...]) -> str:
    for env_name in names:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return ""


def detect_host(explicit_host: str) -> str:
    cleaned = explicit_host.strip().lower()
    if cleaned and cleaned != "auto":
        return cleaned
    if os.environ.get("CODEX_THREAD_ID", "").strip():
        return "codex"
    if os.environ.get("CLAUDECODE", "").strip() or os.environ.get("CLAUDE_CODE", "").strip():
        return "claude-code"
    return "generic"

def derive_agent_session_status(conversation_id: str) -> str:
    return "bound_to_conversation" if conversation_id else "conversation_not_exposed"


def agent_session_path(run_dir: Path) -> Path:
    new_path = run_dir / "agent_session.json"
    old_path = run_dir / "codex_session.json"
    if new_path.exists():
        return new_path
    if old_path.exists():
        try:
            payload = load_json(old_path)
            write_json(new_path, payload)
        except Exception:
            pass
    return new_path


def load_agent_session(run_dir: Path) -> dict:
    path = agent_session_path(run_dir)
    if path.exists():
        return load_json(path)
    return {}


def sync_agent_session(run_dir: Path, run_spec: dict) -> tuple[dict, bool]:
    session_path = agent_session_path(run_dir)
    agent_session = load_agent_session(run_dir)
    changed = False

    conversation_id = first_env_value(THREAD_CONTEXT_ENV_VARS)
    host = str(run_spec.get("host", "generic")).strip() or "generic"
    desired = {
        "provider": f"{host}-adapter",
        "host": host,
        "transport_mode": str(run_spec.get("transport_mode", "host-adapter")).strip() or "host-adapter",
        "binding_scope": "conversation_if_available",
        "session_id": conversation_id,
        "openclaw_session_key": "",
        "session_key_origin": "",
        "thread_id": conversation_id,
        "conversation_id": conversation_id,
        "project_id": "",
        "model": first_env_value(MODEL_CONTEXT_ENV_VARS) or "unknown",
        "reasoning_effort": first_env_value(REASONING_CONTEXT_ENV_VARS) or "unknown",
        "status": derive_agent_session_status(conversation_id),
        "workspace_path": run_spec["workspace_path"],
        "source_channel": "",
        "source_peer_or_thread": "",
        "created_at": str(agent_session.get("created_at", "")).strip() or now_iso(),
        "last_used_at": now_iso(),
        "updated_at": now_iso(),
    }

    for key, value in desired.items():
        if agent_session.get(key) != value:
            agent_session[key] = value
            changed = True

    if changed:
        write_json(session_path, agent_session)
    return agent_session, changed


def event_payload(
    run_id: str,
    state: dict,
    event_type: str,
    prompt_id: str = "",
    reply_class: str = "",
    decision: str = "",
    next_state: str = "",
    input_summary: str = "",
    reply_summary: str = "",
    artifacts: list[str] | None = None,
    error: str = "",
) -> dict:
    return {
        "ts": now_iso(),
        "run_id": run_id,
        "current_state": state.get("current_state", ""),
        "event_type": event_type,
        "prompt_id": prompt_id,
        "reply_class": reply_class,
        "decision": decision,
        "next_state": next_state,
        "input_summary": input_summary,
        "reply_summary": reply_summary,
        "artifacts": artifacts or [],
        "error": error,
    }


def prompt_for_state(state_name: str) -> str:
    return STATE_PROMPTS[state_name]


def current_stage_item(state: dict) -> dict:
    stages = state.get("stages", [])
    index = state.get("stage_index", 0)
    if 0 <= index < len(stages):
        item = stages[index]
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            purpose = str(item.get("purpose", "")).strip()
            return {
                "name": name,
                "purpose": purpose,
            }
        name = str(item).strip()
        if name:
            return {
                "name": name,
                "purpose": "",
            }
    return {
        "name": "",
        "purpose": "",
    }


def current_stage_name(state: dict) -> str:
    return current_stage_item(state)["name"]


def current_stage_purpose(state: dict) -> str:
    return current_stage_item(state)["purpose"]


def render_stage_manifest(state: dict) -> str:
    stages = state.get("stages", [])
    if not stages:
        return "- none"
    lines = []
    for index, item in enumerate(stages, start=1):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            purpose = str(item.get("purpose", "")).strip()
        else:
            name = str(item).strip()
            purpose = ""
        if not name:
            continue
        if purpose:
            lines.append(f"{index}. {name}: {purpose}")
        else:
            lines.append(f"{index}. {name}")
    return "\n".join(lines) if lines else "- none"


def render_template(prompt_id: str, context: dict) -> str:
    template = PROMPT_FILES[prompt_id].read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(context.get(key, ""))

    return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", repl, template).strip() + "\n"


def context_for_run(run_spec: dict, state: dict) -> dict:
    stage_count = state.get("stage_count", 0)
    stage_index = state.get("stage_index", 0)
    approved_prompt_text = read_optional_text(str(state.get("approved_prompt_path", "")))
    active_build_request = approved_prompt_text or run_spec["raw_input"]
    previous_stage_handoff_artifact_path = str(state.get("previous_stage_handoff_artifact_path", "")).strip()
    stage_acceptance_criteria = extract_stage_acceptance_criteria(str(state.get("stage_plan_artifact_path", "")))
    if previous_stage_handoff_artifact_path:
        previous_stage_handoff_artifact_display = previous_stage_handoff_artifact_path
    elif stage_index > 0:
        previous_stage_handoff_artifact_display = "not yet captured"
    else:
        previous_stage_handoff_artifact_display = "none for the first implementation stage"
    if stage_acceptance_criteria:
        stage_acceptance_criteria_display = stage_acceptance_criteria
    else:
        stage_acceptance_criteria_display = "not explicitly captured; derive from the stage brief artifact"
    stage_manifest = render_stage_manifest(state)
    return {
        "run_id": run_spec["run_id"],
        "calling_agent": run_spec["calling_agent"],
        "workspace_path": run_spec["workspace_path"],
        "raw_input": run_spec["raw_input"],
        "active_build_request": active_build_request,
        "factory_name": state.get("factory_name", ""),
        "architecture_artifact_path": state.get("architecture_artifact_path", ""),
        "scaffold_artifact_path": state.get("scaffold_artifact_path", ""),
        "stage_plan_artifact_path": state.get("stage_plan_artifact_path", ""),
        "request_contract_mode": state.get("request_contract_mode", ""),
        "request_contract_status": state.get("request_contract_status", ""),
        "request_contract_feedback": state.get("request_contract_feedback", ""),
        "request_contract_version": state.get("request_contract_version", 0),
        "proposed_prompt_path": state.get("proposed_prompt_path", ""),
        "approved_prompt_path": state.get("approved_prompt_path", ""),
        "previous_stage_handoff_artifact_path": previous_stage_handoff_artifact_path,
        "previous_stage_handoff_artifact_display": previous_stage_handoff_artifact_display,
        "stage_acceptance_criteria": stage_acceptance_criteria,
        "stage_acceptance_criteria_display": stage_acceptance_criteria_display,
        "stage_manifest": stage_manifest,
        "stage_name": current_stage_name(state),
        "stage_purpose": current_stage_purpose(state),
        "stage_index": stage_index,
        "stage_index_display": stage_index + 1 if stage_count else 0,
        "stage_count": stage_count,
        "last_reply_artifact": state.get("last_reply_artifact", ""),
        "recommended_choice": state.get("last_recommended_choice", ""),
        "research_owner_key": state.get("research_owner_key", ""),
        "research_owner_state": state.get("research_owner_state", ""),
        "research_stage_name": state.get("research_stage_name", ""),
        "research_task_id": state.get("research_task_id", ""),
        "research_request_path": state.get("research_request_path", ""),
        "research_response_path": state.get("research_response_path", ""),
        "research_artifact_path": state.get("research_artifact_path", ""),
        "research_wait_started_at": state.get("research_wait_started_at", ""),
        "research_wait_deadline_at": state.get("research_wait_deadline_at", ""),
        "research_fallback_reason": state.get("research_fallback_reason", ""),
    }


def render_status(run_spec: dict, state: dict, codex_session: dict) -> str:
    terminal = str(state.get("current_state", "")).strip() in {"COMPLETED", "FAILED"}
    stage_name = "" if terminal else current_stage_name(state)
    stage_purpose = "" if terminal else current_stage_purpose(state)
    lines = [
        f"# MVP Builder Status: {run_spec['run_id']}",
        "",
        f"- status: {state['status']}",
        f"- current_state: {state['current_state']}",
        f"- factory_name: {state.get('factory_name', '')}",
        f"- stage_index: {state['stage_index']}",
        f"- stage_count: {state['stage_count']}",
        f"- current_stage_name: {stage_name or ('none (terminal state)' if terminal else 'none')}",
        f"- current_stage_purpose: {stage_purpose or ('none (terminal state)' if terminal else 'none')}",
        f"- current_prompt_id: {state['current_prompt_id']}",
        f"- last_reply_class: {state['last_reply_class']}",
        f"- last_decision: {state['last_decision']}",
        f"- last_reply_artifact: {state.get('last_reply_artifact', '')}",
        f"- previous_stage_handoff_artifact_path: {state.get('previous_stage_handoff_artifact_path', '')}",
        f"- loop_count: {state['loop_count']}",
        f"- autoselect_count: {state['autoselect_count']}",
        f"- updated_at: {state['updated_at']}",
        "",
        "## Transport",
        "",
        f"- transport_mode: {run_spec.get('transport_mode', '')}",
        *(
            [f"- requested_transport_mode: {run_spec.get('requested_transport_mode', '')}"]
            if run_spec.get("requested_transport_mode", "") != run_spec.get("transport_mode", "")
            else []
        ),
        *(
            [f"- transport_mode_note: {run_spec.get('transport_mode_note', '')}"]
            if run_spec.get("transport_mode_note", "")
            else []
        ),
        f"- host: {run_spec.get('host', '')}",
        f"- binding_scope: {codex_session.get('binding_scope', '')}",
        f"- agent_session_id: {codex_session.get('session_id', '')}",
        f"- session_key_origin: {codex_session.get('session_key_origin', '')}",
        f"- agent_conversation_id: {codex_session.get('conversation_id', '') or codex_session.get('thread_id', '') or 'unmapped'}",
        f"- agent_session_status: {codex_session.get('status', '')}",
        f"- model: {codex_session.get('model', '')}",
        f"- workspace_path: {codex_session.get('workspace_path', '')}",
    ]
    if codex_session.get("source_channel"):
        lines.extend(
            [
                f"- source_channel: {codex_session.get('source_channel', '')}",
                f"- source_peer_or_thread: {codex_session.get('source_peer_or_thread', '')}",
            ]
        )
    lines.extend(["", "## Pending Items", ""])
    pending = state.get("pending_items", [])
    if pending:
        lines.extend([f"- {item}" for item in pending])
    else:
        lines.append("- none")
    if state.get("architecture_artifact_path"):
        lines.extend(
            [
                "",
                "## Architecture",
                "",
                f"- architecture_artifact_path: {state.get('architecture_artifact_path', '')}",
            ]
        )
    if state.get("request_contract_status") or state.get("proposed_prompt_path") or state.get("approved_prompt_path"):
        lines.extend(
            [
                "",
                "## Request Contract",
                "",
                f"- request_contract_mode: {state.get('request_contract_mode', '')}",
                f"- request_contract_status: {state.get('request_contract_status', '')}",
                f"- request_contract_version: {state.get('request_contract_version', 0)}",
                f"- proposed_prompt_path: {state.get('proposed_prompt_path', '')}",
                f"- approved_prompt_path: {state.get('approved_prompt_path', '')}",
                f"- request_contract_feedback: {state.get('request_contract_feedback', '')}",
            ]
        )
    if state.get("scaffold_artifact_path"):
        lines.extend(
            [
                "",
                "## Scaffold",
                "",
                f"- scaffold_artifact_path: {state.get('scaffold_artifact_path', '')}",
            ]
        )
    if state.get("stage_plan_artifact_path") and not terminal:
        lines.extend(
            [
                "",
                "## Current Stage Plan",
                "",
                f"- stage_plan_artifact_path: {state.get('stage_plan_artifact_path', '')}",
            ]
        )
    if state.get("research_task_id") and not terminal:
        lines.extend(
            [
                "",
                "## Research",
                "",
                f"- research_owner_state: {state.get('research_owner_state', '')}",
                f"- research_owner_key: {state.get('research_owner_key', '')}",
                f"- research_stage_name: {state.get('research_stage_name', '')}",
                f"- research_status: {state.get('research_status', '')}",
                f"- research_task_id: {state.get('research_task_id', '')}",
                f"- research_request_path: {state.get('research_request_path', '')}",
                f"- research_response_path: {state.get('research_response_path', '')}",
                f"- research_artifact_path: {state.get('research_artifact_path', '')}",
                f"- research_dispatch_log_path: {state.get('research_dispatch_log_path', '')}",
                f"- research_wait_started_at: {state.get('research_wait_started_at', '')}",
                f"- research_wait_deadline_at: {state.get('research_wait_deadline_at', '')}",
                f"- research_fallback_reason: {state.get('research_fallback_reason', '')}",
            ]
        )
    if state.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend([f"- {item}" for item in state["errors"]])
    return "\n".join(lines).strip() + "\n"


def render_latest_update(
    run_spec: dict,
    state: dict,
    codex_session: dict,
    happened: str,
    decision: str,
    next_state: str,
    note: str = "",
) -> str:
    stage_name = current_stage_name(state)
    lines = [
        f"# MVP Builder Update: {run_spec['run_id']}",
        "",
        f"- happened: {happened}",
        f"- decision: {decision}",
        f"- next_state: {next_state}",
        f"- status: {state['status']}",
        f"- stage_name: {stage_name}",
        f"- agent_conversation_id: {codex_session.get('conversation_id', '') or codex_session.get('thread_id', '') or 'unmapped'}",
    ]
    if note:
        lines.append(f"- note: {note}")
    lines.extend(
        [
            "",
            "Human update:",
            (
                f"{happened}. Decision: `{decision}`. Next state: `{next_state}`. "
                f"Run status: `{state['status']}`. Conversation id: "
                f"`{codex_session.get('conversation_id', '') or codex_session.get('thread_id', '') or 'unmapped'}`."
            ),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def machine_stage_number(state_name: str) -> str:
    mapping = {
        "BOOTSTRAP_AGENT": "Stage 1",
        "REQUEST_CONTRACT": "Stage 2",
        "RESEARCH_ARCHITECTURE": "Stage 3",
        "IMPLEMENT_SCAFFOLD": "Stage 4",
        "ENUMERATE_STAGES": "Stage 5",
        "STAGE_BRAINSTORM": "Stage 6",
        "STAGE_RESEARCH": "Stage 7",
        "STAGE_IMPLEMENT": "Stage 8",
        "STAGE_VERIFY": "Stage 9",
        "FINAL_VERIFY": "Stage 10",
        "FINAL_REPORT": "Stage 11",
        "COMPLETED": "Terminal",
        "FAILED": "Terminal",
    }
    return mapping.get(state_name.strip(), "Unknown")


def human_state_headline(state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    status = str(state.get("status", "")).strip()
    stage_name = current_stage_name(state)
    target_label = research_target_label(state)

    if current_state == "COMPLETED":
        return "MVP Builder run completed."
    if current_state == "FAILED":
        return "MVP Builder run failed."
    if current_state == "REQUEST_CONTRACT" and status == "waiting":
        return "Waiting for human approval of the request contract."
    if current_state in RESEARCH_FLOW_STATES and status == "waiting":
        task_id = str(state.get("research_task_id", "")).strip()
        if task_id:
            return f"Waiting for research to finish for {target_label}."
        return f"Waiting for research to finish for {target_label}."
    if current_state == "STAGE_BRAINSTORM" and stage_name:
        return f"Planning implementation stage: {stage_name}."
    if current_state == "STAGE_RESEARCH" and stage_name and status == "active":
        return f"Researching the implementation approach for stage: {stage_name}."
    if current_state == "STAGE_IMPLEMENT" and stage_name:
        return f"Implementing stage: {stage_name}."
    if current_state == "STAGE_VERIFY" and stage_name:
        return f"Verifying stage: {stage_name}."
    if current_state == "FINAL_VERIFY":
        return "Running final end-to-end verification."
    if current_state == "FINAL_REPORT":
        return "Writing the final completion report."
    if current_state == "BOOTSTRAP_AGENT":
        return "Verifying the local agent environment and runtime setup."
    if current_state == "RESEARCH_ARCHITECTURE":
        return "Researching and shaping the overall architecture."
    if current_state == "IMPLEMENT_SCAFFOLD":
        return "Creating the project scaffold."
    if current_state == "ENUMERATE_STAGES":
        return "Freezing the implementation stage list."
    return f"Working in {current_state or 'the current state'}."


def human_state_detail(run_spec: dict, state: dict, codex_session: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    status = str(state.get("status", "")).strip()
    stage_name = current_stage_name(state)
    stage_purpose = current_stage_purpose(state)
    stage_index = int(state.get("stage_index", 0) or 0)
    stage_count = int(state.get("stage_count", 0) or 0)
    thread_id = str(codex_session.get("conversation_id", "") or codex_session.get("thread_id", "") or "unmapped").strip()
    transport_note = str(run_spec.get("transport_mode_note", "")).strip()

    details: list[str] = []
    if current_state in {"STAGE_BRAINSTORM", "STAGE_RESEARCH", "STAGE_IMPLEMENT", "STAGE_VERIFY"} and stage_name:
        details.append(f"Current implementation loop: {stage_index + 1} of {stage_count} (`{stage_name}`).")
        if stage_purpose:
            details.append(f"Purpose: {stage_purpose}")
    if current_state in RESEARCH_FLOW_STATES:
        task_id = str(state.get("research_task_id", "")).strip()
        if task_id:
            details.append(f"Research task: `{task_id}`.")
        fallback_reason = str(state.get("research_fallback_reason", "")).strip()
        if fallback_reason:
            details.append(f"Fallback status: {fallback_reason}")
    if current_state == "REQUEST_CONTRACT":
        mode = str(state.get("request_contract_mode", "")).strip()
        contract_status = str(state.get("request_contract_status", "")).strip()
        if mode:
            details.append(f"Request-contract mode: `{mode}`.")
        if contract_status:
            details.append(f"Contract status: `{contract_status}`.")
    if transport_note:
        details.append(f"Transport note: {transport_note}")
    if status == "completed":
        details.append("No further machine steps remain in this run.")
    details.append(f"Conversation id: `{thread_id}`.")
    return " ".join(item for item in details if item).strip()


def human_next_step(state: dict) -> str:
    current_state = str(state.get("current_state", "")).strip()
    status = str(state.get("status", "")).strip()
    next_prompt = str(state.get("current_prompt_id", "")).strip()

    if current_state == "COMPLETED":
        return "Next: human browser review or distribution of the finished project."
    if current_state == "FAILED":
        return "Next: inspect the latest error and decide whether to retry or repair the workflow."
    if current_state == "REQUEST_CONTRACT" and status == "waiting":
        return "Next: approve the proposed prompt or request changes."
    if current_state in RESEARCH_FLOW_STATES and status == "waiting":
        return "Next: wait for the research artifact or the next machine step."
    if current_state == "ENUMERATE_STAGES":
        return "Next: freeze the ordered implementation stage list."
    if current_state == "STAGE_BRAINSTORM":
        return "Next: finalize the stage brief before stage-specific research."
    if current_state == "STAGE_RESEARCH" and next_prompt.endswith("_synthesize"):
        return "Next: synthesize the completed research into implementation guidance."
    if current_state == "STAGE_RESEARCH":
        return "Next: capture the strongest practical approach for this stage."
    if current_state == "STAGE_IMPLEMENT":
        return "Next: implement the current stage against its brief and research."
    if current_state == "STAGE_VERIFY":
        return "Next: decide whether this stage is done and advance the loop."
    if current_state == "FINAL_VERIFY":
        return "Next: confirm end-to-end readiness before final reporting."
    if current_state == "FINAL_REPORT":
        return "Next: write the final completion summary and close the run."
    if current_state == "BOOTSTRAP_AGENT":
        return "Next: confirm the runtime is ready and move into the request-contract gate."
    if current_state == "RESEARCH_ARCHITECTURE":
        return "Next: complete architecture research and synthesize the recommended design."
    if current_state == "IMPLEMENT_SCAFFOLD":
        return "Next: create the minimal project shell."
    return "Next: continue the current machine step."


def human_progress_payload(run_spec: dict, state: dict, codex_session: dict) -> dict:
    current_state = str(state.get("current_state", "")).strip()
    stage_name = current_stage_name(state)
    stage_purpose = current_stage_purpose(state)
    return {
        "timestamp": str(state.get("updated_at") or now_iso()).strip(),
        "run_id": run_spec["run_id"],
        "factory_name": str(state.get("factory_name", "")).strip(),
        "status": str(state.get("status", "")).strip(),
        "current_state": current_state,
        "machine_stage": machine_stage_number(current_state),
        "current_stage_name": stage_name,
        "current_stage_purpose": stage_purpose,
        "loop_position": (
            f"{int(state.get('stage_index', 0) or 0) + 1}/{int(state.get('stage_count', 0) or 0)}"
            if current_state in {"STAGE_BRAINSTORM", "STAGE_RESEARCH", "STAGE_IMPLEMENT", "STAGE_VERIFY"}
            and int(state.get("stage_count", 0) or 0) > 0
            else ""
        ),
        "headline": human_state_headline(state),
        "detail": human_state_detail(run_spec, state, codex_session),
        "next_step": human_next_step(state),
        "last_decision": str(state.get("last_decision", "")).strip(),
        "current_prompt_id": str(state.get("current_prompt_id", "")).strip(),
        "research_task_id": str(state.get("research_task_id", "")).strip(),
        "agent_conversation_id": str(
            codex_session.get("conversation_id", "") or codex_session.get("thread_id", "") or "unmapped"
        ).strip(),
        "transport_mode": str(run_spec.get("transport_mode", "")).strip(),
        "requested_transport_mode": str(run_spec.get("requested_transport_mode", "")).strip(),
        "transport_mode_note": str(run_spec.get("transport_mode_note", "")).strip(),
    }


def render_human_progress(run_dir: Path, run_spec: dict, state: dict, codex_session: dict) -> str:
    payload = human_progress_payload(run_spec, state, codex_session)
    updates_path = run_dir / "human_updates.jsonl"
    recent_updates: list[dict] = []
    if updates_path.exists():
        try:
            lines = [line for line in updates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for raw_line in lines[-8:]:
                recent_updates.append(json.loads(raw_line))
        except Exception:
            recent_updates = []

    lines = [
        f"# MVP Builder Human Progress: {run_spec['run_id']}",
        "",
        f"- project: {payload['factory_name'] or run_spec.get('raw_input', '').strip()[:60]}",
        f"- machine_stage: {payload['machine_stage']}",
        f"- current_state: {payload['current_state']}",
        f"- status: {payload['status']}",
        f"- transport_mode: {payload['transport_mode']}",
    ]
    if payload["requested_transport_mode"] and payload["requested_transport_mode"] != payload["transport_mode"]:
        lines.append(f"- requested_transport_mode: {payload['requested_transport_mode']}")
    if payload["current_stage_name"] and payload["current_state"] not in {"COMPLETED", "FAILED"}:
        lines.append(f"- current_loop_stage: {payload['current_stage_name']}")
    if payload["loop_position"]:
        lines.append(f"- loop_position: {payload['loop_position']}")
    if payload["transport_mode_note"]:
        lines.append(f"- transport_note: {payload['transport_mode_note']}")
    lines.extend(
        [
            f"- headline: {payload['headline']}",
            f"- detail: {payload['detail'] or 'none'}",
            f"- next_step: {payload['next_step']}",
            f"- updated_at: {payload['timestamp']}",
            "",
            "## Recent Human Updates",
            "",
        ]
    )
    if recent_updates:
        for item in recent_updates:
            ts = str(item.get("timestamp", "")).strip()
            headline = str(item.get("headline", "")).strip()
            next_step = str(item.get("next_step", "")).strip()
            lines.append(f"- {ts} - {headline}")
            if next_step:
                lines.append(f"  {next_step}")
    else:
        lines.append("- none yet")
    return "\n".join(lines).strip() + "\n"


def append_human_update_if_changed(run_dir: Path, run_spec: dict, state: dict, codex_session: dict, latest_update: str) -> None:
    latest_path = run_dir / "latest_update.md"
    updates_path = run_dir / "human_updates.jsonl"
    previous_latest = ""
    if latest_path.exists():
        previous_latest = latest_path.read_text(encoding="utf-8")
    if previous_latest == latest_update and updates_path.exists():
        return
    append_jsonl(updates_path, human_progress_payload(run_spec, state, codex_session))


def write_views(run_dir: Path, run_spec: dict, state: dict, codex_session: dict, latest_update: str) -> None:
    append_human_update_if_changed(run_dir, run_spec, state, codex_session, latest_update)
    (run_dir / "status.md").write_text(render_status(run_spec, state, codex_session), encoding="utf-8")
    (run_dir / "latest_update.md").write_text(latest_update, encoding="utf-8")
    (run_dir / "human_progress.md").write_text(
        render_human_progress(run_dir, run_spec, state, codex_session),
        encoding="utf-8",
    )


def reject_incomplete_research_request(
    run_dir: Path,
    run_spec: dict,
    state: dict,
    codex_session: dict,
    reply_summary: str,
) -> int:
    current_state = str(state.get("current_state", "")).strip()
    flow = RESEARCH_FLOW_STATES.get(current_state, {})
    request_prompt_id = str(flow.get("request_prompt_id") or state.get("current_prompt_id") or "").strip()
    target_label = research_target_label(state)
    state["last_reply_class"] = "STATUS_ONLY"
    state["last_decision"] = "reject_incomplete_research_request"
    state["status"] = "active"
    state["current_prompt_id"] = request_prompt_id
    state["updated_at"] = now_iso()
    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened=f"Research request launch was incomplete for {target_label}",
        decision=state["last_decision"],
        next_state=state["current_state"],
        note=f"Reply did not include a usable research task id or artifact path for {target_label}.",
    )
    write_json(run_dir / "state.json", state)
    write_views(run_dir, run_spec, state, codex_session, latest)
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_rejected",
            prompt_id=state["current_prompt_id"],
            decision=state["last_decision"],
            next_state=state["current_state"],
            reply_summary=reply_summary,
            error=f"missing research task id or artifact path for {target_label}",
        ),
    )
    print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
    return 0


def sync_research_state(run_dir: Path, run_spec: dict, state: dict, codex_session: dict) -> tuple[dict, dict, bool]:
    with run_lock(run_dir, "research-sync.lock"):
        state = load_json(run_dir / "state.json")
        codex_session = load_agent_session(run_dir)

        current_state = str(state.get("current_state", "")).strip()
        flow = RESEARCH_FLOW_STATES.get(current_state)
        if not flow:
            return state, codex_session, False

        owner_key = str(state.get("research_owner_key", "")).strip()
        if not owner_key or owner_key != current_research_owner_key(state):
            return state, codex_session, False

        task_id = str(state.get("research_task_id", "")).strip()
        if not task_id:
            return state, codex_session, False

        changed = False
        target_label = research_target_label(state)
        synthesize_prompt_id = str(flow["synthesize_prompt_id"]).strip()
        fallback_prompt_id = str(flow.get("fallback_prompt_id", "")).strip()
        response_path_value = str(state.get("research_response_path", "")).strip()
        artifact_path_value = str(state.get("research_artifact_path", "")).strip()
        response = load_optional_json(response_path_value)
        response_status = str((response or {}).get("status", "")).strip().lower()
        artifact_exists = bool(artifact_path_value) and Path(artifact_path_value).exists()
        current_prompt_id = str(state.get("current_prompt_id", "")).strip()
        if current_prompt_id == fallback_prompt_id and state.get("status") == "active":
            return state, codex_session, False

        if not str(state.get("research_wait_started_at", "")).strip():
            state["research_wait_started_at"] = str(state.get("updated_at") or now_iso()).strip()
            changed = True
        if not str(state.get("research_wait_deadline_at", "")).strip():
            state["research_wait_deadline_at"] = iso_plus_minutes(state["research_wait_started_at"], RESEARCH_WAIT_TIMEOUT_MINUTES)
            changed = True
        if changed:
            write_json(run_dir / "state.json", state)

        def activate_fallback(reason: str, error_message: str = "") -> tuple[dict, dict, bool]:
            nonlocal changed, state, codex_session
            if (
                state.get("research_status") != "fallback_search"
                or state.get("current_prompt_id") != fallback_prompt_id
                or state.get("status") != "active"
                or str(state.get("research_fallback_reason", "")).strip() != reason.strip()
            ):
                state["research_status"] = "fallback_search"
                state["status"] = "active"
                state["current_prompt_id"] = fallback_prompt_id
                state["last_decision"] = "fallback_to_native_search"
                state["research_fallback_reason"] = reason.strip()
                state["research_broker_unhealthy"] = True
                state["updated_at"] = now_iso()
                if error_message and error_message not in state["errors"]:
                    state["errors"].append(error_message)
                latest = render_latest_update(
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    happened=f"Brokered research fell back to native host search for {target_label}",
                    decision=state["last_decision"],
                    next_state=state["current_state"],
                    note=(
                        f"{reason.strip()} "
                        f"Use the fallback prompt to have the host agent perform regular online search directly for {target_label}."
                    ),
                )
                write_json(run_dir / "state.json", state)
                write_views(run_dir, run_spec, state, codex_session, latest)
                append_jsonl(
                    run_dir / "events.jsonl",
                    event_payload(
                        run_id=run_spec["run_id"],
                        state=state,
                        event_type="research_fallback_triggered",
                        prompt_id=fallback_prompt_id,
                        decision=state["last_decision"],
                        next_state=state["current_state"],
                        input_summary=reason.strip(),
                        artifacts=[response_path_value, artifact_path_value],
                        error=error_message,
                    ),
                )
                changed = True
            return state, codex_session, changed

        inferred_status = response_status or str(state.get("research_status") or "requested").strip().lower()

        if (
            state.get("research_broker_unhealthy")
            and inferred_status in {"requested", "queued", "running"}
            and fallback_prompt_id
        ):
            sticky_reason = (
                "Brokered research already timed out or failed earlier in this run. "
                "Skipping another brokered wait and falling back to regular host search."
            )
            return activate_fallback(sticky_reason)

        if response_status == "completed" and artifact_exists:
            if (
                state.get("research_status") != "completed"
                or state.get("current_prompt_id") != synthesize_prompt_id
                or state.get("status") != "active"
            ):
                state["research_status"] = "completed"
                state["status"] = "active"
                state["current_prompt_id"] = synthesize_prompt_id
                state["last_decision"] = "ready_for_research_synthesis"
                state["updated_at"] = now_iso()
                latest = render_latest_update(
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    happened=f"Research completed for {target_label}",
                    decision=state["last_decision"],
                    next_state=state["current_state"],
                    note=f"Research task `{task_id}` completed for {target_label}. The synthesis prompt is now ready.",
                )
                write_json(run_dir / "state.json", state)
                write_views(run_dir, run_spec, state, codex_session, latest)
                append_jsonl(
                    run_dir / "events.jsonl",
                    event_payload(
                        run_id=run_spec["run_id"],
                        state=state,
                        event_type="research_completed",
                        prompt_id=synthesize_prompt_id,
                        decision=state["last_decision"],
                        next_state=state["current_state"],
                        input_summary=f"Research task `{task_id}` is complete for {target_label} and artifact is available.",
                        artifacts=[artifact_path_value, response_path_value],
                    ),
                )
                changed = True
            return state, codex_session, changed

        if response_status in {"failed", "stale"}:
            raw_error = (response or {}).get("error")
            error_text = ""
            if raw_error not in {None, ""}:
                error_text = str(raw_error).strip()
            summary_text = str((response or {}).get("summary") or "").strip()
            failure_note = error_text or summary_text or f"Research task `{task_id}` for {target_label} is in `{response_status}` status."
            fallback_reason = (
                f"Brokered research entered `{response_status}` status for task `{task_id}`. "
                f"Falling back to regular host search."
            )
            return activate_fallback(fallback_reason, failure_note)

        deadline_at = parse_iso(str(state.get("research_wait_deadline_at", "")).strip())
        now_dt = datetime.now(timezone.utc).astimezone()
        if inferred_status in {"requested", "queued", "running"} and deadline_at and now_dt >= deadline_at:
            timeout_reason = (
                f"Brokered research did not complete within {RESEARCH_WAIT_TIMEOUT_MINUTES} minutes for task `{task_id}`. "
                f"Falling back to regular host search."
            )
            return activate_fallback(timeout_reason)
        if (
            inferred_status in {"requested", "queued", "running"}
            and (
                state.get("status") != "waiting"
                or state.get("current_prompt_id") != ""
                or state.get("research_status") != inferred_status
            )
        ):
            state["research_status"] = inferred_status
            state["status"] = "waiting"
            state["current_prompt_id"] = ""
            state["last_decision"] = "wait_for_research_completion"
            state["updated_at"] = now_iso()
            latest = render_latest_update(
                run_spec=run_spec,
                state=state,
                codex_session=codex_session,
                happened=f"Waiting for research for {target_label}",
                decision=state["last_decision"],
                next_state=state["current_state"],
                note=f"Research task `{task_id}` for {target_label} is not complete yet. Waiting for `{artifact_path_value or 'research artifact'}`.",
            )
            write_json(run_dir / "state.json", state)
            write_views(run_dir, run_spec, state, codex_session, latest)
            append_jsonl(
                run_dir / "events.jsonl",
                event_payload(
                    run_id=run_spec["run_id"],
                    state=state,
                    event_type="research_waiting",
                    decision=state["last_decision"],
                    next_state=state["current_state"],
                    input_summary=f"Research task `{task_id}` is still in progress for {target_label}.",
                    artifacts=[response_path_value, artifact_path_value],
                ),
            )
            changed = True

        return state, codex_session, changed


def classify_reply(reply_text: str) -> tuple[str, str]:
    text = reply_text.strip()
    lower = text.lower()

    hard_error_patterns = [
        r"\bhard error\b",
        r"\bunrecoverable\b",
        r"\bfatal\b",
        r"\bcannot proceed\b",
        r"\bhard blocker\b",
        r"\b(run|state|workflow|request)\s+failed\b",
        r"\bfailed to\b",
        r"^\s*(error|failure|failed)\s*[:\-]",
    ]
    if any(re.search(pattern, lower, flags=re.IGNORECASE | re.MULTILINE) for pattern in hard_error_patterns):
        return "HARD_ERROR", ""
    if re.search(r"\b(waiting for|need (your|human) input|provide the missing|human-only)\b", lower):
        return "BLOCKED_NEEDS_HUMAN", ""
    if re.search(r"\b(done|completed|complete|implemented|finished|ready)\b", lower):
        return "COMPLETED", ""

    recommended_patterns = [
        r"recommended option[:\s]+([^\n]+)",
        r"i recommend[:\s]+([^\n]+)",
        r"my recommendation is[:\s]+([^\n]+)",
        r"\(recommended\)\s*[:\-]?\s*([^\n]+)",
    ]
    for pattern in recommended_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return "RECOMMENDED_OPTION", match.group(1).strip().strip("`")

    if re.search(r"\b(what is your suggestion|what do you suggest|how would you like me to proceed)\b", lower):
        return "NEEDS_SUGGESTION", ""
    if re.search(r"\b(should i proceed|should i go ahead|do you want me to implement|approve this implementation)\b", lower):
        return "NEEDS_IMPLEMENT_CONFIRMATION", ""
    if re.search(r"\b(progress|working on|in progress|currently|ongoing)\b", lower):
        return "STATUS_ONLY", ""
    return "STATUS_ONLY", ""


def looks_like_bootstrap_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "workspace verification",
        "file-access verification",
        "tooling verification",
        "web search verification",
        "model and reasoning verification",
        "blocker:",
    ]
    return all(marker in lower for marker in required_markers)


def bootstrap_completion_missing_requirements(reply_text: str) -> list[str]:
    lower = reply_text.lower()
    missing = []
    if "workspace verification" not in lower:
        missing.append("workspace verification")
    if "file-access verification" not in lower:
        missing.append("file-access verification")
    if "tooling verification" not in lower:
        missing.append("tooling verification")
    if "web search verification" not in lower:
        missing.append("web search verification")
    if "model and reasoning verification" not in lower:
        missing.append("model and reasoning verification")
    return missing


def extract_research_launch_state(reply_text: str) -> str:
    match = re.search(
        r"research request successfully launched:\s*`?(yes|no)`?",
        reply_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group(1).strip().lower()


def request_contract_completion_missing_requirements(reply_text: str) -> list[str]:
    parsed = parse_request_contract(reply_text)
    missing = []
    if not parsed.get("input_mode", "").strip():
        missing.append("Input mode")
    if not parsed.get("approval_mode", "").strip():
        missing.append("Approval mode")
    if not parsed.get("proposed_approved_prompt", "").strip():
        missing.append("Proposed approved prompt")
    if not parsed.get("must_haves", "").strip():
        missing.append("Must-haves")
    if not parsed.get("success_criteria", "").strip():
        missing.append("Success criteria")
    if not parsed.get("approval_question", "").strip():
        missing.append("Approval question")
    return missing


def looks_like_stage_plan_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "stage brief",
        "research brief for stage",
        "objective:",
        "acceptance criteria:",
        "what research should answer:",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_research_architecture_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "working project name",
        "recommended architecture",
        "ordered stage list",
        "research evidence",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_scaffold_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "scaffold summary",
        "purpose of each",
        "intentionally deferred",
        "blocker",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_stage_research_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "stage research summary",
        "research evidence",
        "recommended approach for this stage",
        "pitfalls to avoid",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_stage_implementation_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "implementation summary",
        "test evidence",
        "important development decisions made",
        "anything still incomplete",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_stage_verification_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "verification evidence",
        "whether the acceptance criteria were met",
        "whether continuity with the previous verified handoff was preserved",
        "whether we should move to the next stage now",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_final_verification_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "end-to-end verification summary",
        "verification evidence",
        "remaining gaps",
        "whether the project is ready for human testing",
    ]
    return all(marker in lower for marker in required_markers)


def looks_like_final_report_completion(reply_text: str) -> bool:
    lower = reply_text.lower()
    required_markers = [
        "what was completed",
        "what still remains",
        "what the human should test next",
    ]
    return all(marker in lower for marker in required_markers)


def normalize_request_contract_approval_mode(value: str) -> str:
    cleaned = value.strip().strip("`").strip().lower().replace("-", "_")
    if cleaned in {"auto_proceed", "human_review_required"}:
        return cleaned
    return "human_review_required"


def write_request_contract_artifacts(run_dir: Path, run_spec: dict, state: dict, reply_text: str) -> dict:
    root = request_contract_root(run_dir)
    history_dir = root / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    version = int(state.get("request_contract_version", 0)) + 1
    parsed = parse_request_contract(reply_text)
    mode = normalize_request_contract_mode(
        parsed.get("input_mode", ""),
        run_spec["raw_input"],
        str(state.get("request_contract_mode", "")),
    )
    if mode == "literal_locked":
        proposed_prompt = strip_matching_outer_quotes(run_spec["raw_input"])
    else:
        proposed_prompt = parsed.get("proposed_approved_prompt", "").strip()
    if not proposed_prompt:
        proposed_prompt = run_spec["raw_input"].strip()
    approval_mode = normalize_request_contract_approval_mode(parsed.get("approval_mode", ""))

    contract_payload = {
        "version": version,
        "mode": mode,
        "approval_mode": approval_mode,
        "raw_input": run_spec["raw_input"],
        "raw_input_summary": parsed.get("raw_input_summary", "").strip(),
        "proposed_approved_prompt": proposed_prompt,
        "must_haves": parsed.get("must_haves", "").strip(),
        "constraints": parsed.get("constraints", "").strip(),
        "non_goals": parsed.get("non_goals", "").strip(),
        "success_criteria": parsed.get("success_criteria", "").strip(),
        "assumptions_or_ambiguities_to_confirm": parsed.get("assumptions_or_ambiguities_to_confirm", "").strip(),
        "how_the_human_feedback_was_incorporated": parsed.get("how_the_human_feedback_was_incorporated", "").strip(),
        "approval_question": parsed.get("approval_question", "").strip(),
        "source_reply_text": reply_text.strip(),
        "created_at": now_iso(),
    }

    versioned_json_path = history_dir / f"request_contract.v{version:03d}.json"
    latest_json_path = root / "request_contract.json"
    versioned_prompt_path = root / f"proposed_prompt.v{version:03d}.md"
    latest_prompt_path = root / "proposed_prompt.latest.md"

    write_json(versioned_json_path, contract_payload)
    write_json(latest_json_path, contract_payload)
    versioned_prompt_path.write_text(proposed_prompt.strip() + "\n", encoding="utf-8")
    latest_prompt_path.write_text(proposed_prompt.strip() + "\n", encoding="utf-8")

    state["request_contract_mode"] = mode
    state["request_contract_status"] = "prepared"
    state["request_contract_version"] = version
    state["proposed_prompt_path"] = str(latest_prompt_path.resolve())
    state["approved_prompt_path"] = ""

    return {
        "version": version,
        "mode": mode,
        "approval_mode": approval_mode,
        "proposed_prompt_path": str(latest_prompt_path.resolve()),
        "versioned_prompt_path": str(versioned_prompt_path.resolve()),
        "request_contract_json_path": str(latest_json_path.resolve()),
        "versioned_request_contract_json_path": str(versioned_json_path.resolve()),
    }


def reject_incomplete_bootstrap_completion(
    run_dir: Path,
    run_spec: dict,
    state: dict,
    codex_session: dict,
    reply_summary: str,
    missing: list[str],
) -> int:
    state["last_reply_class"] = "STATUS_ONLY"
    state["last_decision"] = "reject_incomplete_bootstrap_completion"
    state["status"] = "active"
    state["current_prompt_id"] = "bootstrap_verify_environment"
    state["updated_at"] = now_iso()
    missing_note = "; ".join(missing)
    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened="Bootstrap verification was incomplete",
        decision=state["last_decision"],
        next_state=state["current_state"],
        note=f"Reply did not confirm all required bootstrap items: {missing_note}.",
    )
    write_json(run_dir / "state.json", state)
    write_views(run_dir, run_spec, state, codex_session, latest)
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_rejected",
            prompt_id=state["current_prompt_id"],
            decision=state["last_decision"],
            next_state=state["current_state"],
            reply_summary=reply_summary,
            error=missing_note,
        ),
    )
    print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
    return 0


def reject_incomplete_request_contract_completion(
    run_dir: Path,
    run_spec: dict,
    state: dict,
    codex_session: dict,
    reply_summary: str,
    missing: list[str],
) -> int:
    state["last_reply_class"] = "STATUS_ONLY"
    state["last_decision"] = "reject_incomplete_request_contract_completion"
    state["status"] = "active"
    state["current_prompt_id"] = state.get("current_prompt_id") or "request_contract_prepare"
    state["updated_at"] = now_iso()
    missing_note = "; ".join(missing)
    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened="Request contract was incomplete",
        decision=state["last_decision"],
        next_state=state["current_state"],
        note=f"Reply did not include all required request-contract fields: {missing_note}.",
    )
    write_json(run_dir / "state.json", state)
    write_views(run_dir, run_spec, state, codex_session, latest)
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_rejected",
            prompt_id=state["current_prompt_id"],
            decision=state["last_decision"],
            next_state=state["current_state"],
            reply_summary=reply_summary,
            error=missing_note,
        ),
    )
    print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
    return 0


def reject_invalid_stage_list(
    run_dir: Path,
    run_spec: dict,
    state: dict,
    codex_session: dict,
    reply_summary: str,
    reasons: list[str],
) -> int:
    state["last_reply_class"] = "STATUS_ONLY"
    state["last_decision"] = "reject_invalid_stage_list"
    state["status"] = "active"
    state["current_prompt_id"] = "enumerate_stages"
    state["updated_at"] = now_iso()
    note = "; ".join(reasons)
    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened="Stage list enumeration was rejected",
        decision=state["last_decision"],
        next_state=state["current_state"],
        note=note,
    )
    write_json(run_dir / "state.json", state)
    write_views(run_dir, run_spec, state, codex_session, latest)
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_rejected",
            prompt_id=state["current_prompt_id"],
            decision=state["last_decision"],
            next_state=state["current_state"],
            reply_summary=reply_summary,
            error=note,
        ),
    )
    print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
    return 0


def next_state_after_success(state: dict) -> str:
    current = state["current_state"]
    if current == "BOOTSTRAP_AGENT":
        return "REQUEST_CONTRACT"
    if current == "REQUEST_CONTRACT":
        return "RESEARCH_ARCHITECTURE"
    if current == "RESEARCH_ARCHITECTURE":
        return "IMPLEMENT_SCAFFOLD"
    if current == "IMPLEMENT_SCAFFOLD":
        return "ENUMERATE_STAGES"
    if current == "ENUMERATE_STAGES":
        return "STAGE_BRAINSTORM"
    if current == "STAGE_BRAINSTORM":
        return "STAGE_RESEARCH"
    if current == "STAGE_RESEARCH":
        return "STAGE_IMPLEMENT"
    if current == "STAGE_IMPLEMENT":
        return "STAGE_VERIFY"
    if current == "STAGE_VERIFY":
        if state["stage_index"] + 1 < state["stage_count"]:
            return "STAGE_BRAINSTORM"
        return "FINAL_VERIFY"
    if current == "FINAL_VERIFY":
        return "FINAL_REPORT"
    if current == "FINAL_REPORT":
        return "COMPLETED"
    return current


def normalize_stage_entry(raw_name: str, raw_purpose: str = "") -> dict:
    return {
        "name": " ".join(raw_name.split()).strip(),
        "purpose": " ".join(raw_purpose.split()).strip(),
    }


def parse_stage_items_from_reply(reply_text: str) -> list[dict]:
    items: list[dict] = []
    lines = reply_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        match = re.match(r"^\s*(\d+)[.)]\s*(.+?)\s*::\s*(.+?)\s*$", line)
        if match:
            items.append(normalize_stage_entry(match.group(2), match.group(3)))
            continue
        match = re.match(r"^\s*(\d+)[.)]\s*(.+?)\s*[-:]\s+(.+?)\s*$", line)
        if match:
            items.append(normalize_stage_entry(match.group(2), match.group(3)))
            continue
        match = re.match(r"^\s*(\d+)[.)]\s*(.+?)\s*$", line)
        if match:
            stage_name = match.group(2)
            purpose = ""
            if i < len(lines):
                next_line = lines[i].strip()
                purpose_match = re.match(r"^(purpose|goal)\s*:\s*(.+?)\s*$", next_line, flags=re.IGNORECASE)
                if purpose_match:
                    purpose = purpose_match.group(2)
                    i += 1
            items.append(normalize_stage_entry(stage_name, purpose))
    return [item for item in items if item["name"]]


def parse_stage_list(explicit_stages: list[str], stages_file: str | None, reply_text: str = "") -> list[dict]:
    if explicit_stages:
        parsed = []
        for item in explicit_stages:
            cleaned = item.strip()
            if not cleaned:
                continue
            if "::" in cleaned:
                name, purpose = cleaned.split("::", 1)
                parsed.append(normalize_stage_entry(name, purpose))
            else:
                parsed.append(normalize_stage_entry(cleaned, ""))
        return parsed
    if not stages_file:
        return parse_stage_items_from_reply(reply_text)
    path = Path(stages_file).expanduser().resolve()
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise SystemExit("--stages-file JSON must be an array of stage names or stage objects.")
        parsed = []
        for item in payload:
            if isinstance(item, dict):
                parsed.append(normalize_stage_entry(str(item.get("name", "")), str(item.get("purpose", ""))))
            else:
                parsed.append(normalize_stage_entry(str(item), ""))
        return [item for item in parsed if item["name"]]
    parsed_lines = []
    for line in raw.splitlines():
        cleaned = line.strip("- ").strip()
        if not cleaned:
            continue
        if "::" in cleaned:
            name, purpose = cleaned.split("::", 1)
            parsed_lines.append(normalize_stage_entry(name, purpose))
        else:
            parsed_lines.append(normalize_stage_entry(cleaned, ""))
    return [item for item in parsed_lines if item["name"]]


def is_tiny_project_request(raw_input: str) -> bool:
    lower = raw_input.lower()
    complex_markers = (
        "database",
        "backend",
        "api",
        "authentication",
        "auth",
        "queue",
        "worker",
        "pipeline",
        "multi-agent",
        "multiple agents",
        "payment",
        "storage",
        "webhook",
        "integration",
        "mobile app",
        "ios",
        "android",
    )
    if any(marker in lower for marker in complex_markers):
        return False
    return len(" ".join(raw_input.split())) <= 220


def validate_stage_items(stage_items: list[dict], raw_input: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for item in stage_items:
        name = str(item.get("name", "")).strip()
        purpose = str(item.get("purpose", "")).strip()
        if not name:
            errors.append("Stage list contains an empty stage name.")
            continue
        normalized_name = slugify(name)
        if normalized_name in seen:
            errors.append(f"Duplicate stage name detected: `{name}`.")
        seen.add(normalized_name)
        if not purpose:
            warnings.append(f"Stage `{name}` is missing a one-line purpose.")
    if is_tiny_project_request(raw_input) and len(stage_items) > 6:
        errors.append(
            f"Tiny project requests should not produce more than 6 stages, but this reply produced {len(stage_items)} stages."
        )
    return errors, warnings


def fail_run(run_dir: Path, run_spec: dict, state: dict, reason: str) -> None:
    codex_session, _ = sync_agent_session(run_dir, run_spec)
    state["status"] = "failed"
    state["current_state"] = "FAILED"
    state["current_prompt_id"] = ""
    state["updated_at"] = now_iso()
    state.setdefault("errors", []).append(reason)
    write_json(run_dir / "state.json", state)
    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened="Run failed",
        decision="fail_run",
        next_state="FAILED",
        note=reason,
    )
    write_views(run_dir, run_spec, state, codex_session, latest)
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="state_failed",
            decision="fail_run",
            next_state="FAILED",
            error=reason,
        ),
    )


def init_run(args: argparse.Namespace) -> int:
    calling_agent = args.calling_agent.strip()
    host = detect_host(args.host)
    run_root = Path(args.run_root).expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"mvp-builder-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = run_root / run_id
    if run_dir.exists():
        raise SystemExit(f"Run already exists: {run_dir}")

    workspace_path = str(Path(args.workspace_path).expanduser().resolve())
    effective_transport_mode = f"{host}-adapter"
    openclaw_session_key = ""
    binding_scope = "conversation_if_available"
    session_key_origin = ""
    transport_note = (
        "This run is self-contained inside the MVP Builder shared workflow. "
        "The active host may record the current conversation id when the environment exposes it, "
        "but the run does not depend on external orchestration services."
    )

    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "artifacts" / "replies").mkdir()
    request_contract_root(run_dir).mkdir(parents=True, exist_ok=True)

    raw_input = args.raw_input.strip()
    run_spec = {
        "run_id": run_id,
        "created_at": now_iso(),
        "calling_agent": calling_agent,
        "host": host,
        "workspace_path": workspace_path,
        "raw_input": raw_input,
        "transport_mode": effective_transport_mode,
        "requested_transport_mode": effective_transport_mode,
        "transport_mode_note": transport_note,
        "binding_scope": binding_scope,
        "openclaw_session_key": openclaw_session_key,
        "session_key_origin": session_key_origin,
        "required_agents": [],
        "required_skills": [],
        "required_tools": [],
        "policy": {
            "auto_select_recommended_option": True,
            "max_followups_per_state": args.max_followups_per_state,
            "max_recommended_option_autoselects_per_state": args.max_recommended_option_autoselects_per_state,
        },
    }
    write_json(run_dir / "run_spec.json", run_spec)

    state = {
        "run_id": run_id,
        "status": "active",
        "current_state": "BOOTSTRAP_AGENT",
        "loop_count": 0,
        "autoselect_count": 0,
        "stage_index": 0,
        "stage_count": 0,
        "stages": [],
        "factory_name": args.factory_name.strip() if args.factory_name else slugify(raw_input)[:48],
        "current_prompt_id": "bootstrap_verify_environment",
        "last_reply_class": "",
        "last_decision": "",
        "last_reply_artifact": "",
        "last_recommended_choice": "",
        "request_contract_mode": detect_request_contract_mode(raw_input),
        "request_contract_status": "",
        "request_contract_feedback": "",
        "request_contract_version": 0,
        "proposed_prompt_path": "",
        "approved_prompt_path": "",
        "architecture_artifact_path": "",
        "scaffold_artifact_path": "",
        "stage_plan_artifact_path": "",
        "previous_stage_handoff_artifact_path": "",
        "research_owner_state": "",
        "research_owner_key": "",
        "research_stage_name": "",
        "research_artifact_path": "",
        "pending_items": [],
        "errors": [],
        "updated_at": now_iso(),
    }
    write_json(run_dir / "state.json", state)
    sync_request_contract_artifacts(run_dir, run_spec, state)

    codex_session = {
        "provider": f"{host}-adapter",
        "host": host,
        "transport_mode": effective_transport_mode,
        "binding_scope": binding_scope,
        "session_id": "",
        "openclaw_session_key": openclaw_session_key,
        "session_key_origin": session_key_origin,
        "thread_id": "",
        "conversation_id": "",
        "project_id": "",
        "model": first_env_value(MODEL_CONTEXT_ENV_VARS) or "unknown",
        "reasoning_effort": first_env_value(REASONING_CONTEXT_ENV_VARS) or "unknown",
        "status": "conversation_not_exposed",
        "workspace_path": workspace_path,
        "source_channel": "",
        "source_peer_or_thread": "",
        "created_at": "",
        "last_used_at": "",
        "updated_at": now_iso(),
    }
    write_json(run_dir / "agent_session.json", codex_session)
    codex_session, _ = sync_agent_session(run_dir, run_spec)

    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_id,
            state=state,
            event_type="run_initialized",
            prompt_id=state["current_prompt_id"],
            input_summary=trim_summary(raw_input),
        ),
    )
    if transport_note:
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_id,
                state=state,
                event_type="run_note_recorded",
                decision="record_run_note",
                next_state=state["current_state"],
                input_summary=transport_note,
            ),
        )

    init_note = "Render the current prompt, complete that state inside the active host, then apply the structured reply back to the run."
    if transport_note:
        init_note = f"{transport_note} {init_note}"

    latest = render_latest_update(
        run_spec=run_spec,
        state=state,
        codex_session=codex_session,
        happened="Run initialized",
        decision="set_initial_state",
        next_state=state["current_state"],
        note=init_note,
    )
    write_views(run_dir, run_spec, state, codex_session, latest)

    print(f"RUN_DIR={run_dir}")
    print(f"RUN_ID={run_id}")
    print(f"CURRENT_STATE={state['current_state']}")
    print(f"PROMPT_ID={state['current_prompt_id']}")
    print(f"HOST={host}")
    print(f"TRANSPORT_MODE={effective_transport_mode}")
    print(f"REQUESTED_TRANSPORT_MODE={effective_transport_mode}")
    if transport_note:
        print(f"TRANSPORT_MODE_NOTE={transport_note}")
    if codex_session.get("conversation_id") or codex_session.get("thread_id"):
        print(f"AGENT_CONVERSATION_ID={codex_session.get('conversation_id') or codex_session.get('thread_id')}")
    return 0


def status_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).expanduser().resolve()
    run_spec = load_json(run_dir / "run_spec.json")
    state = load_json(run_dir / "state.json")
    state, _ = sync_request_contract_artifacts(run_dir, run_spec, state)
    state, _ = sync_architecture_artifact_state(run_dir, state)
    state, _ = sync_scaffold_artifact_state(run_dir, state)
    state, _ = sync_stage_plan_artifact_state(run_dir, state)
    state, _ = sync_previous_stage_handoff_artifact_state(run_dir, state)
    codex_session, _ = sync_agent_session(run_dir, run_spec)
    state = load_json(run_dir / "state.json")
    codex_session = load_agent_session(run_dir)
    latest = (run_dir / "latest_update.md").read_text(encoding="utf-8").strip()
    write_views(run_dir, run_spec, state, codex_session, latest + "\n")
    print((run_dir / "status.md").read_text(encoding="utf-8").strip())
    return 0


def render_prompt_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).expanduser().resolve()
    run_spec = load_json(run_dir / "run_spec.json")
    state = load_json(run_dir / "state.json")
    state, _ = sync_request_contract_artifacts(run_dir, run_spec, state)
    state, _ = sync_architecture_artifact_state(run_dir, state)
    state, _ = sync_scaffold_artifact_state(run_dir, state)
    state, _ = sync_stage_plan_artifact_state(run_dir, state)
    state, _ = sync_previous_stage_handoff_artifact_state(run_dir, state)
    codex_session, _ = sync_agent_session(run_dir, run_spec)
    state = load_json(run_dir / "state.json")

    prompt_id = state["current_prompt_id"]
    if not prompt_id:
        if state.get("status") == "waiting":
            latest = (run_dir / "latest_update.md").read_text(encoding="utf-8").strip()
            print(latest)
            return 0
        raise SystemExit(f"No current prompt is available for state `{state['current_state']}`.")
    context = context_for_run(run_spec, state)
    prompt_text = render_template(prompt_id, context)

    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="prompt_sent",
            prompt_id=prompt_id,
            input_summary=f"Rendered prompt for state {state['current_state']}",
        ),
    )
    print(prompt_text.rstrip())
    return 0


def apply_reply_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).expanduser().resolve()
    run_spec = load_json(run_dir / "run_spec.json")
    state = load_json(run_dir / "state.json")
    state, _ = sync_request_contract_artifacts(run_dir, run_spec, state)
    state, _ = sync_architecture_artifact_state(run_dir, state)
    state, _ = sync_scaffold_artifact_state(run_dir, state)
    state, _ = sync_stage_plan_artifact_state(run_dir, state)
    state, _ = sync_previous_stage_handoff_artifact_state(run_dir, state)
    codex_session, _ = sync_agent_session(run_dir, run_spec)
    state = load_json(run_dir / "state.json")
    codex_session = load_agent_session(run_dir)
    if state["current_state"] in {"COMPLETED", "FAILED"}:
        raise SystemExit(f"Run is already terminal in state `{state['current_state']}`.")
    if state["status"] == "waiting" and not state.get("current_prompt_id"):
        latest = (run_dir / "latest_update.md").read_text(encoding="utf-8").strip()
        raise SystemExit(f"Run is waiting and has no active prompt.\n\n{latest}")

    reply_text = read_text(args.reply, args.reply_file)
    if not reply_text:
        raise SystemExit("Provide --reply or --reply-file.")

    reply_artifact_path = save_reply_artifact(run_dir, state["current_state"], reply_text)

    reply_class, inferred_choice = (
        (args.reply_class, args.recommended_choice or "")
        if args.reply_class
        else classify_reply(reply_text)
    )
    stages = parse_stage_list(args.stage, args.stages_file, reply_text)
    if (
        not args.reply_class
        and state.get("current_state") == "BOOTSTRAP_AGENT"
        and reply_class == "STATUS_ONLY"
        and looks_like_bootstrap_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "REQUEST_CONTRACT"
        and reply_class == "STATUS_ONLY"
        and looks_like_request_contract_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "STAGE_BRAINSTORM"
        and reply_class == "STATUS_ONLY"
        and looks_like_stage_plan_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "RESEARCH_ARCHITECTURE"
        and reply_class == "STATUS_ONLY"
        and looks_like_research_architecture_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "STAGE_RESEARCH"
        and reply_class == "STATUS_ONLY"
        and looks_like_stage_research_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "IMPLEMENT_SCAFFOLD"
        and reply_class == "STATUS_ONLY"
        and looks_like_scaffold_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "ENUMERATE_STAGES"
        and reply_class == "STATUS_ONLY"
        and bool(stages)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "STAGE_IMPLEMENT"
        and reply_class == "STATUS_ONLY"
        and looks_like_stage_implementation_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "STAGE_VERIFY"
        and reply_class == "STATUS_ONLY"
        and looks_like_stage_verification_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "FINAL_VERIFY"
        and reply_class == "STATUS_ONLY"
        and looks_like_final_verification_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if (
        not args.reply_class
        and state.get("current_state") == "FINAL_REPORT"
        and reply_class == "STATUS_ONLY"
        and looks_like_final_report_completion(reply_text)
    ):
        reply_class = "COMPLETED"
    if not args.reply_class and reply_class == "STATUS_ONLY":
        research_flow = RESEARCH_FLOW_STATES.get(str(state.get("current_state", "")).strip(), {})
        request_prompt_id = str(research_flow.get("request_prompt_id", "")).strip()
        if request_prompt_id and str(state.get("current_prompt_id", "")).strip() == request_prompt_id:
            launch_state = extract_research_launch_state(reply_text)
            if launch_state == "yes":
                reply_class = "COMPLETED"
            elif launch_state == "no":
                reply_class = "HARD_ERROR"
    if reply_class not in REPLY_CLASSES:
        raise SystemExit(f"Invalid reply class `{reply_class}`.")

    artifacts = [str(reply_artifact_path)]
    artifacts.extend(str(Path(item).expanduser().resolve()) for item in args.artifact)
    reply_summary = trim_summary(reply_text)

    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_received",
            prompt_id=state["current_prompt_id"],
            input_summary=f"Applied reply for state {state['current_state']}",
            reply_summary=reply_summary,
            artifacts=artifacts,
        ),
    )
    append_jsonl(
        run_dir / "events.jsonl",
        event_payload(
            run_id=run_spec["run_id"],
            state=state,
            event_type="reply_classified",
            prompt_id=state["current_prompt_id"],
            reply_class=reply_class,
            reply_summary=reply_summary,
        ),
    )

    current_state = state["current_state"]

    current_prompt_id = str(state.get("current_prompt_id", "")).strip()
    research_flow = RESEARCH_FLOW_STATES.get(current_state, {})

    if args.factory_name:
        state["factory_name"] = args.factory_name.strip()
    elif current_state == "RESEARCH_ARCHITECTURE" and current_prompt_id in {
        "research_architecture",
        "research_architecture_synthesize",
        "research_architecture_fallback_search",
    }:
        extracted_name = extract_project_name(reply_text)
        if extracted_name:
            state["factory_name"] = extracted_name
    if args.pending_item:
        for item in args.pending_item:
            cleaned = item.strip()
            if cleaned and cleaned not in state["pending_items"]:
                state["pending_items"].append(cleaned)
    state["last_reply_artifact"] = str(reply_artifact_path)

    policy = run_spec["policy"]
    note = ""

    if reply_class == "COMPLETED":
        if current_state == "REQUEST_CONTRACT":
            missing = request_contract_completion_missing_requirements(reply_text)
            if missing:
                return reject_incomplete_request_contract_completion(
                    run_dir=run_dir,
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    reply_summary=reply_summary,
                    missing=missing,
                )
            request_contract_meta = write_request_contract_artifacts(run_dir, run_spec, state, reply_text)
            state["last_reply_class"] = reply_class
            state["last_recommended_choice"] = ""
            state["loop_count"] = 0
            state["autoselect_count"] = 0
            state["request_contract_feedback"] = ""
            state["updated_at"] = now_iso()

            if request_contract_meta["approval_mode"] == "auto_proceed":
                approved_prompt_path = request_contract_root(run_dir) / "approved_prompt.md"
                shutil.copyfile(request_contract_meta["proposed_prompt_path"], str(approved_prompt_path))
                state["approved_prompt_path"] = str(approved_prompt_path.resolve())
                state["request_contract_status"] = "approved"
                state["last_decision"] = "auto_approve_request_contract"
                state["current_state"] = next_state_after_success(state)
                state["status"] = "active"
                state["current_prompt_id"] = prompt_for_state(state["current_state"])
                latest = render_latest_update(
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    happened="Request contract auto-approved",
                    decision=state["last_decision"],
                    next_state=state["current_state"],
                    note=(
                        f"Approval mode is `{request_contract_meta['approval_mode']}`. "
                        f"Approved prompt saved to `{state['approved_prompt_path']}`."
                    ),
                )
                write_json(run_dir / "state.json", state)
                write_views(run_dir, run_spec, state, codex_session, latest)
                append_jsonl(
                    run_dir / "events.jsonl",
                    event_payload(
                        run_id=run_spec["run_id"],
                        state=state,
                        event_type="request_contract_auto_approved",
                        prompt_id=current_prompt_id,
                        decision=state["last_decision"],
                        next_state=state["current_state"],
                        reply_summary=reply_summary,
                        artifacts=artifacts
                        + [
                            request_contract_meta["proposed_prompt_path"],
                            state["approved_prompt_path"],
                            request_contract_meta["request_contract_json_path"],
                        ],
                    ),
                )
            else:
                state["status"] = "waiting"
                state["current_prompt_id"] = ""
                state["last_decision"] = "wait_for_request_contract_approval"
                latest = render_latest_update(
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    happened="Request contract prepared for human approval",
                    decision=state["last_decision"],
                    next_state=state["current_state"],
                    note=(
                        f"Approval mode is `{request_contract_meta['approval_mode']}`. "
                        f"Review `{request_contract_meta['proposed_prompt_path']}` and use human feedback only if you want to intervene."
                    ),
                )
                write_json(run_dir / "state.json", state)
                write_views(run_dir, run_spec, state, codex_session, latest)
                append_jsonl(
                    run_dir / "events.jsonl",
                    event_payload(
                        run_id=run_spec["run_id"],
                        state=state,
                        event_type="request_contract_waiting_for_human",
                        prompt_id=current_prompt_id,
                        decision=state["last_decision"],
                        next_state=state["current_state"],
                        reply_summary=reply_summary,
                        artifacts=artifacts
                        + [
                            request_contract_meta["proposed_prompt_path"],
                            request_contract_meta["request_contract_json_path"],
                        ],
                    ),
                )
            print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
            return 0
        if current_state == "RESEARCH_ARCHITECTURE":
            state["architecture_artifact_path"] = str(reply_artifact_path)
            state["research_artifact_path"] = str(reply_artifact_path)
        if current_state == "IMPLEMENT_SCAFFOLD":
            state["scaffold_artifact_path"] = str(reply_artifact_path)
        if current_state == "STAGE_BRAINSTORM":
            state["stage_plan_artifact_path"] = str(reply_artifact_path)
        if current_state == "STAGE_RESEARCH":
            state["research_artifact_path"] = str(reply_artifact_path)
        if current_state == "BOOTSTRAP_AGENT":
            missing = bootstrap_completion_missing_requirements(reply_text)
            if missing:
                return reject_incomplete_bootstrap_completion(
                    run_dir=run_dir,
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    reply_summary=reply_summary,
                    missing=missing,
                )
        if current_state == "ENUMERATE_STAGES":
            if not stages:
                return reject_invalid_stage_list(
                    run_dir=run_dir,
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    reply_summary=reply_summary,
                    reasons=["Completed ENUMERATE_STAGES without a parseable stage list."],
                )
            stage_errors, stage_warnings = validate_stage_items(stages, run_spec["raw_input"])
            if stage_errors:
                return reject_invalid_stage_list(
                    run_dir=run_dir,
                    run_spec=run_spec,
                    state=state,
                    codex_session=codex_session,
                    reply_summary=reply_summary,
                    reasons=stage_errors,
                )
            state["stages"] = stages
            state["stage_count"] = len(stages)
            state["stage_index"] = 0
            for warning in stage_warnings:
                if warning not in state["pending_items"]:
                    state["pending_items"].append(warning)
        elif current_state == "FINAL_REPORT":
            final_report = [
                f"# MVP Builder Final Report: {run_spec['run_id']}",
                "",
                f"- factory_name: {state.get('factory_name', '')}",
                f"- raw_input: {run_spec['raw_input']}",
                f"- status: completed",
                f"- stage_count: {state['stage_count']}",
                f"- transport_mode: {run_spec.get('transport_mode', '')}",
                f"- host: {run_spec.get('host', '')}",
                f"- agent_conversation_id: {codex_session.get('conversation_id', '') or codex_session.get('thread_id', '') or 'unmapped'}",
                f"- approved_prompt_path: {state.get('approved_prompt_path', '')}",
                "",
                "## Stages",
                "",
            ]
            if state.get("stages"):
                for item in state.get("stages", []):
                    if isinstance(item, dict):
                        name = str(item.get("name", "")).strip()
                        purpose = str(item.get("purpose", "")).strip()
                        if purpose:
                            final_report.append(f"- {name}: {purpose}")
                        else:
                            final_report.append(f"- {name}")
                    else:
                        final_report.append(f"- {item}")
            else:
                final_report.append("- none")
            final_report.extend(["", "## Pending Items", ""])
            final_report.extend([f"- {item}" for item in state.get("pending_items", [])] or ["- none"])
            final_report.extend(
                [
                    "",
                    "## Agent Context",
                    "",
                    f"- Host: {run_spec.get('host', '') or 'unknown'}",
                    f"- Conversation id: {codex_session.get('conversation_id', '') or codex_session.get('thread_id', '') or 'unmapped'}",
                    f"- Model: {codex_session.get('model', '') or 'unknown'}",
                    f"- Reasoning effort: {codex_session.get('reasoning_effort', '') or 'unknown'}",
                ]
            )
            final_reply_body = reply_text.strip() or reply_summary.strip()
            final_report.extend(
                [
                    "",
                    "## Final Agent Reply",
                    "",
                    final_reply_body,
                ]
            )
            report_path = run_dir / "artifacts" / "final-report.md"
            report_path.write_text("\n".join(final_report).strip() + "\n", encoding="utf-8")
            artifacts.append(str(report_path))
            append_jsonl(
                run_dir / "events.jsonl",
                event_payload(
                    run_id=run_spec["run_id"],
                    state=state,
                    event_type="artifact_written",
                    prompt_id=state["current_prompt_id"],
                    artifacts=[str(report_path)],
                    input_summary="Wrote final report artifact.",
                ),
            )

        next_state = next_state_after_success(state)
        if current_state == "STAGE_VERIFY" and next_state == "STAGE_BRAINSTORM":
            state["previous_stage_handoff_artifact_path"] = str(reply_artifact_path)
            state["stage_index"] += 1
            state["stage_plan_artifact_path"] = ""
            state["research_owner_state"] = ""
            state["research_owner_key"] = ""
            state["research_stage_name"] = ""
            state["research_artifact_path"] = ""
        state["current_state"] = next_state
        state["status"] = "completed" if next_state == "COMPLETED" else "active"
        state["current_prompt_id"] = prompt_for_state(next_state)
        state["last_reply_class"] = reply_class
        state["last_decision"] = "advance_state"
        state["last_recommended_choice"] = ""
        state["loop_count"] = 0
        state["autoselect_count"] = 0
        state["updated_at"] = now_iso()
        if next_state == "COMPLETED":
            append_jsonl(
                run_dir / "events.jsonl",
                event_payload(
                    run_id=run_spec["run_id"],
                    state=state,
                    event_type="run_completed",
                    decision="complete_run",
                    next_state="COMPLETED",
                    reply_summary=reply_summary,
                    artifacts=artifacts,
                ),
            )
        else:
            append_jsonl(
                run_dir / "events.jsonl",
                event_payload(
                    run_id=run_spec["run_id"],
                    state=state,
                    event_type="state_advanced",
                    decision="advance_state",
                    next_state=next_state,
                    reply_summary=reply_summary,
                    artifacts=artifacts,
                ),
            )
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened=f"Agent completed state {current_state}",
            decision="advance_state",
            next_state=state["current_state"],
            note=note or reply_summary,
        )
        write_json(run_dir / "state.json", state)
        codex_session, _ = sync_agent_session(run_dir, run_spec)
        write_views(run_dir, run_spec, state, codex_session, latest)
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if reply_class == "RECOMMENDED_OPTION":
        if state["autoselect_count"] + 1 > policy["max_recommended_option_autoselects_per_state"]:
            fail_run(run_dir, run_spec, state, "Recommended-option auto-select limit exceeded.")
            print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
            return 0
        choice = args.recommended_choice or inferred_choice
        if not choice:
            state["status"] = "waiting"
            state["last_reply_class"] = "BLOCKED_NEEDS_HUMAN"
            state["last_decision"] = "pause_for_human"
            state["updated_at"] = now_iso()
            latest = render_latest_update(
                run_spec=run_spec,
                state=state,
                codex_session=codex_session,
                happened=f"Agent returned a recommended option in {current_state}",
                decision="pause_for_human",
                next_state=current_state,
                note="The recommendation was ambiguous and could not be auto-selected safely.",
            )
            write_json(run_dir / "state.json", state)
            write_views(run_dir, run_spec, state, codex_session, latest)
            append_jsonl(
                run_dir / "events.jsonl",
                event_payload(
                    run_id=run_spec["run_id"],
                    state=state,
                    event_type="state_paused",
                    reply_class="BLOCKED_NEEDS_HUMAN",
                    decision="pause_for_human",
                    next_state=current_state,
                    error="Ambiguous recommended option.",
                ),
            )
            print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
            return 0
        state["loop_count"] += 1
        state["autoselect_count"] += 1
        state["current_prompt_id"] = "followup_recommended_option"
        state["last_reply_class"] = reply_class
        state["last_decision"] = f"auto_select_recommended_option:{choice}"
        state["last_recommended_choice"] = choice
        state["status"] = "active"
        state["updated_at"] = now_iso()
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_spec["run_id"],
                state=state,
                event_type="followup_sent",
                prompt_id="followup_recommended_option",
                reply_class=reply_class,
                decision=state["last_decision"],
                next_state=current_state,
                reply_summary=reply_summary,
            ),
        )
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened=f"Agent returned a recommended option in {current_state}",
            decision=state["last_decision"],
            next_state=current_state,
            note=f"Next prompt is `followup_recommended_option` with selected choice `{choice}`.",
        )
        write_json(run_dir / "state.json", state)
        codex_session, _ = sync_agent_session(run_dir, run_spec)
        write_views(run_dir, run_spec, state, codex_session, latest)
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if reply_class in {"NEEDS_SUGGESTION", "NEEDS_IMPLEMENT_CONFIRMATION"}:
        if state["loop_count"] + 1 > policy["max_followups_per_state"]:
            fail_run(run_dir, run_spec, state, "Follow-up loop limit exceeded.")
            print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
            return 0
        prompt_id = "followup_suggestion" if reply_class == "NEEDS_SUGGESTION" else "followup_implement"
        state["loop_count"] += 1
        state["current_prompt_id"] = prompt_id
        state["last_reply_class"] = reply_class
        state["last_decision"] = f"send_{prompt_id}"
        state["status"] = "active"
        state["updated_at"] = now_iso()
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_spec["run_id"],
                state=state,
                event_type="followup_sent",
                prompt_id=prompt_id,
                reply_class=reply_class,
                decision=state["last_decision"],
                next_state=current_state,
                reply_summary=reply_summary,
            ),
        )
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened=f"Agent requested follow-up in {current_state}",
            decision=state["last_decision"],
            next_state=current_state,
            note=f"Next prompt is `{prompt_id}`.",
        )
        write_json(run_dir / "state.json", state)
        codex_session, _ = sync_agent_session(run_dir, run_spec)
        write_views(run_dir, run_spec, state, codex_session, latest)
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if reply_class == "STATUS_ONLY":
        state["last_reply_class"] = reply_class
        state["last_decision"] = "hold_state"
        state["status"] = "active"
        state["updated_at"] = now_iso()
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened=f"Agent reported progress in {current_state}",
            decision="hold_state",
            next_state=current_state,
            note="No state advance. Do not send another prompt automatically unless the transport layer is waiting for input.",
        )
        write_json(run_dir / "state.json", state)
        write_views(run_dir, run_spec, state, codex_session, latest)
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if reply_class == "BLOCKED_NEEDS_HUMAN":
        state["last_reply_class"] = reply_class
        state["last_decision"] = "pause_for_human"
        state["status"] = "waiting"
        state["updated_at"] = now_iso()
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened=f"Agent is blocked in {current_state}",
            decision="pause_for_human",
            next_state=current_state,
            note=reply_summary,
        )
        write_json(run_dir / "state.json", state)
        write_views(run_dir, run_spec, state, codex_session, latest)
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_spec["run_id"],
                state=state,
                event_type="state_paused",
                reply_class=reply_class,
                decision="pause_for_human",
                next_state=current_state,
                reply_summary=reply_summary,
            ),
        )
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if reply_class == "HARD_ERROR":
        fail_run(run_dir, run_spec, state, reply_summary)
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    raise SystemExit(f"Unhandled reply class `{reply_class}`.")


def apply_human_feedback_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).expanduser().resolve()
    run_spec = load_json(run_dir / "run_spec.json")
    state = load_json(run_dir / "state.json")
    state, _ = sync_request_contract_artifacts(run_dir, run_spec, state)
    state, _ = sync_architecture_artifact_state(run_dir, state)
    state, _ = sync_scaffold_artifact_state(run_dir, state)
    state, _ = sync_stage_plan_artifact_state(run_dir, state)
    state, _ = sync_previous_stage_handoff_artifact_state(run_dir, state)
    codex_session, _ = sync_agent_session(run_dir, run_spec)

    if state["current_state"] != "REQUEST_CONTRACT":
        raise SystemExit("Human feedback is currently only supported for REQUEST_CONTRACT.")

    decision = args.decision
    feedback_text = read_text(args.feedback, args.feedback_file)
    proposed_prompt_path = Path(str(state.get("proposed_prompt_path", "")).strip()) if state.get("proposed_prompt_path") else None
    if decision == "approve":
        if not proposed_prompt_path or not proposed_prompt_path.exists():
            raise SystemExit("Cannot approve request contract because no proposed prompt artifact exists yet.")
        approved_prompt_path = request_contract_root(run_dir) / "approved_prompt.md"
        shutil.copyfile(str(proposed_prompt_path), str(approved_prompt_path))
        state["approved_prompt_path"] = str(approved_prompt_path.resolve())
        state["request_contract_status"] = "approved"
        state["request_contract_feedback"] = ""
        next_state = next_state_after_success(state)
        state["current_state"] = next_state
        state["status"] = "active"
        state["current_prompt_id"] = prompt_for_state(next_state)
        state["last_reply_class"] = "COMPLETED"
        state["last_decision"] = "approve_request_contract"
        state["updated_at"] = now_iso()
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened="Human approved the request contract",
            decision=state["last_decision"],
            next_state=state["current_state"],
            note=f"Approved prompt saved to `{state['approved_prompt_path']}`.",
        )
        write_json(run_dir / "state.json", state)
        write_views(run_dir, run_spec, state, codex_session, latest)
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_spec["run_id"],
                state=state,
                event_type="human_feedback_applied",
                decision=state["last_decision"],
                next_state=state["current_state"],
                input_summary="Human approved the request contract.",
                artifacts=[state["approved_prompt_path"]],
            ),
        )
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    if decision == "change":
        if not feedback_text:
            raise SystemExit("Provide --feedback or --feedback-file when decision is `change`.")
        state["request_contract_feedback"] = feedback_text
        state["request_contract_status"] = "drafting"
        state["approved_prompt_path"] = ""
        state["status"] = "active"
        state["current_prompt_id"] = "request_contract_revise"
        state["last_reply_class"] = "BLOCKED_NEEDS_HUMAN"
        state["last_decision"] = "revise_request_contract"
        state["updated_at"] = now_iso()
        latest = render_latest_update(
            run_spec=run_spec,
            state=state,
            codex_session=codex_session,
            happened="Human requested changes to the request contract",
            decision=state["last_decision"],
            next_state=state["current_state"],
            note="Render `request_contract_revise` and send it through the active host transport.",
        )
        write_json(run_dir / "state.json", state)
        write_views(run_dir, run_spec, state, codex_session, latest)
        append_jsonl(
            run_dir / "events.jsonl",
            event_payload(
                run_id=run_spec["run_id"],
                state=state,
                event_type="human_feedback_applied",
                prompt_id="request_contract_revise",
                decision=state["last_decision"],
                next_state=state["current_state"],
                input_summary=trim_summary(feedback_text),
            ),
        )
        print((run_dir / "latest_update.md").read_text(encoding="utf-8").strip())
        return 0

    raise SystemExit(f"Unsupported human feedback decision `{decision}`.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Shared state-machine runner for MVP Builder across Codex and Claude Code."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a new MVP Builder run.")
    init_parser.add_argument("--raw-input", required=True)
    init_parser.add_argument("--calling-agent", default="codex")
    init_parser.add_argument("--host", default="auto", choices=["auto", "codex", "claude-code", "generic"])
    init_parser.add_argument(
        "--workspace-path",
        default=str(Path.cwd()),
    )
    init_parser.add_argument("--factory-name")
    init_parser.add_argument("--run-root", default=str(RUN_ROOT))
    init_parser.add_argument("--run-id")
    init_parser.add_argument("--max-followups-per-state", type=int, default=8)
    init_parser.add_argument("--max-recommended-option-autoselects-per-state", type=int, default=4)
    init_parser.set_defaults(func=init_run)

    status_parser = subparsers.add_parser("status", help="Show run status.")
    status_parser.add_argument("--run", required=True)
    status_parser.set_defaults(func=status_run)

    render_parser = subparsers.add_parser("render-prompt", help="Render the current prompt for the run.")
    render_parser.add_argument("--run", required=True)
    render_parser.set_defaults(func=render_prompt_run)

    reply_parser = subparsers.add_parser("apply-reply", help="Apply a host-agent reply to the current run.")
    reply_parser.add_argument("--run", required=True)
    reply_parser.add_argument("--reply")
    reply_parser.add_argument("--reply-file")
    reply_parser.add_argument("--reply-class", choices=sorted(REPLY_CLASSES))
    reply_parser.add_argument("--recommended-choice")
    reply_parser.add_argument("--research-task-id")
    reply_parser.add_argument("--research-request-path")
    reply_parser.add_argument("--research-response-path")
    reply_parser.add_argument("--research-artifact-path")
    reply_parser.add_argument("--factory-name")
    reply_parser.add_argument("--stage", action="append", default=[])
    reply_parser.add_argument("--stages-file")
    reply_parser.add_argument("--pending-item", action="append", default=[])
    reply_parser.add_argument("--artifact", action="append", default=[])
    reply_parser.set_defaults(func=apply_reply_run)

    human_parser = subparsers.add_parser(
        "apply-human-feedback",
        help="Apply human approval or revision feedback to the current run.",
    )
    human_parser.add_argument("--run", required=True)
    human_parser.add_argument("--decision", choices=["approve", "change"], required=True)
    human_parser.add_argument("--feedback")
    human_parser.add_argument("--feedback-file")
    human_parser.set_defaults(func=apply_human_feedback_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
