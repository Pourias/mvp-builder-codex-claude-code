#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = REPO_ROOT / "adapters" / "claude-code" / "templates"
CLAUDE_TEMPLATE = TEMPLATES_ROOT / "CLAUDE.md"
COMMAND_TEMPLATE = TEMPLATES_ROOT / ".claude" / "commands" / "mvp-builder.md"
START_MARKER = "<!-- MVP_BUILDER_ADAPTER:START -->"
END_MARKER = "<!-- MVP_BUILDER_ADAPTER:END -->"


def render_template(path: Path, repo_root: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.replace("__MVP_BUILDER_REPO_ROOT__", str(repo_root))


def upsert_marked_block(path: Path, block: str) -> None:
    wrapped = f"{START_MARKER}\n{block.strip()}\n{END_MARKER}\n"
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if START_MARKER in current and END_MARKER in current:
            prefix, rest = current.split(START_MARKER, 1)
            _, suffix = rest.split(END_MARKER, 1)
            updated = prefix.rstrip() + "\n\n" + wrapped + suffix.lstrip()
        else:
            updated = current.rstrip() + "\n\n" + wrapped
    else:
        updated = wrapped
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.strip() + "\n", encoding="utf-8")


def install(project: Path, repo_root: Path) -> None:
    project = project.expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)

    claude_path = project / "CLAUDE.md"
    command_path = project / ".claude" / "commands" / "mvp-builder.md"

    claude_block = render_template(CLAUDE_TEMPLATE, repo_root)
    upsert_marked_block(claude_path, claude_block)

    command_path.parent.mkdir(parents=True, exist_ok=True)
    command_path.write_text(render_template(COMMAND_TEMPLATE, repo_root).strip() + "\n", encoding="utf-8")

    print(f"Installed Claude Code adapter into {project}")
    print(f"- {claude_path}")
    print(f"- {command_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the MVP Builder Claude Code adapter into a target project.")
    parser.add_argument("--project", required=True, help="Absolute or relative path to the target project.")
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Path to the shared mvp-builder repo clone. Defaults to the current repo root.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    install(Path(args.project), Path(args.repo_root).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
