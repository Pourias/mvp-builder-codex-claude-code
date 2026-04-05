---
name: mvp-builder
description: "Build a first-pass MVP through a disk-backed state machine with request contract, architecture research, staged implementation, verification, and final handoff. Use when Codex should take a product idea, app idea, internal tool request, workflow concept, prototype request, or early feature spec and autonomously turn it into a small shipped first version with minimal human involvement. This Codex adapter uses the shared mvp-builder core, which also supports Claude Code. Use native web research directly when a research stage needs outside information."
---

# MVP Builder

## Overview

Use this skill when the user wants a real builder workflow, not just a one-off implementation pass. The skill creates a visible run folder on disk, advances through explicit states, preserves durable artifacts, and keeps pushing toward a working MVP unless there is a genuine reason to stop.

This file is the Codex adapter for the shared `mvp-builder` core. The shared runner lives at `core/scripts/mvp_builder.py`.

## Workflow

Drive the runner directly from Codex. The human should not need to manually manage the state machine in normal use.

1. Initialize a run:

```bash
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py init \
  --host codex \
  --calling-agent codex \
  --raw-input "build a simple internal dashboard for tracking invoices"
```

2. Render the current prompt:

```bash
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py render-prompt --run <run-dir>
```

3. Do the work for that state inside Codex.

4. Apply the structured reply back into the run:

```bash
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py apply-reply \
  --run <run-dir> \
  --reply-file /absolute/path/to/reply.md
```

5. Repeat until the run reaches `COMPLETED` or `FAILED`.

Read these files between steps:

- `status.md`
- `latest_update.md`
- `human_progress.md`

## States

- `BOOTSTRAP_AGENT`
- `REQUEST_CONTRACT`
- `RESEARCH_ARCHITECTURE`
- `IMPLEMENT_SCAFFOLD`
- `ENUMERATE_STAGES`
- `STAGE_BRAINSTORM`
- `STAGE_RESEARCH`
- `STAGE_IMPLEMENT`
- `STAGE_VERIFY`
- `FINAL_VERIFY`
- `FINAL_REPORT`
- `COMPLETED`
- `FAILED`

Keep the machine flat and explicit. Do not skip states.

## Autonomy Policy

Default to continuing without asking the human follow-up questions.

Only pause when one of these is true:

- a secret, login, API key, or account choice is required and cannot be safely stubbed
- the next action is destructive or production-facing
- the request contract itself determines that human review is required
- there is a major ambiguity with real product or business consequences
- the run is genuinely blocked

Otherwise, make reasonable assumptions, log them in the reply artifact, and keep moving.

## Research Policy

This skill does not use researcher agents, queues, or external orchestration services.

When a research state needs outside information:

- use native web research directly
- keep the research proportional to the MVP
- write the conclusions into the reply artifact for that state
- include short source notes in the `Research evidence` section
- do not invent citations if web research was not actually used

When a stage is straightforward, explicitly say web search was not needed and proceed.

## Request Contract

`REQUEST_CONTRACT` must return:

- `Input mode`
- `Approval mode`
- `Approval reason`
- `Proposed approved prompt`
- `Must-haves`
- `Success criteria`
- `Approval question`

Default to `Approval mode: auto_proceed`.

Use `human_review_required` only for real risk, not ordinary product ambiguity.

## Artifact Rules

Each run writes visible files on disk:

- `run_spec.json`
- `state.json`
- `agent_session.json`
- `events.jsonl`
- `status.md`
- `latest_update.md`
- `human_progress.md`
- `human_updates.jsonl`

Important artifacts are also preserved under `artifacts/`.

Do not mutate old events. Append to `events.jsonl`.

## Verification Rules

`STAGE_IMPLEMENT`, `STAGE_VERIFY`, and `FINAL_VERIFY` should prefer real evidence over vague claims.

Always include:

- exact commands run when commands were run
- exact checks performed when manual review was used
- what each check showed
- what is still incomplete

If something could not be tested, say exactly why.

## Commands

The shared runner lives at:

- `~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py`

Useful commands:

```bash
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py status --run <run-dir>
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py render-prompt --run <run-dir>
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py apply-human-feedback --run <run-dir> --decision approve
python3 ~/.codex/skills/mvp-builder/core/scripts/mvp_builder.py apply-human-feedback --run <run-dir> --decision change --feedback "Tighten the scope."
```

## Resources

- `core/scripts/mvp_builder.py`: the shared state-machine runner
- `core/prompts/`: shared prompt templates and follow-up prompts
- `adapters/claude-code/`: Claude Code installer and templates
