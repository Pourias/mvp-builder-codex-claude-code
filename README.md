# MVP Builder

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

I built `mvp-builder` because I wanted Codex to do more of the real product work for me and push projects all the way to an MVP state with much less human involvement.

Instead of treating each request like a one-off coding task, `mvp-builder` uses a disk-backed state machine that moves through a full build workflow: request contract, architecture, scaffold, staged implementation, verification, and final handoff. When research is needed, Codex uses its own built-in web search inside the workflow so it can gather the context it needs before making implementation decisions.

The goal is simple: save time, reduce context drift, and help Codex ship stronger first iterations of products instead of stopping at vague plans or half-finished prototypes.

`mvp-builder` is intentionally self-contained. It does not depend on OpenClaw services, brokered research, or other skills. The runner handles state and artifacts on disk, and Codex handles the actual research, coding, verification, and handoff.

## Status

`mvp-builder` is an early open-source release aimed at real-world MVP shipping, not academic demos. The current focus is:

- strong first-pass product scaffolding
- stateful autonomous execution with minimal human intervention
- durable artifacts and resumable runs
- practical research inside the workflow using Codex web search

If you want to help improve it, see [CONTRIBUTING.md](CONTRIBUTING.md).

## What It Does

`mvp-builder` helps Codex:

- turn a product idea into a structured build workflow
- create an approved request contract before building
- research architecture and stage-level decisions when useful
- scaffold the project
- break work into clear implementation stages
- implement each stage with minimal human intervention
- verify the work before handing it off
- produce a final report with what was built, what remains, and what to test next

## Why This Exists

Most coding agents are good at one isolated implementation pass, but much weaker at managing the full path from vague request to believable MVP. I built this to close that gap.

The core idea is simple:

- give Codex a product request
- move it through explicit states
- let it research what it needs at the right moments
- keep visible artifacts on disk
- reduce how much the human needs to manually re-steer the process

That should save a lot of time, especially on early product work where the most expensive part is usually coordination and lost context, not writing the code itself.

## Why I Built It

I wanted a way to hand Codex an idea and let it keep moving without repeatedly asking me to re-scope, re-explain, or manually coordinate each phase.

This skill is designed to make Codex act more like an autonomous MVP builder:

- it keeps durable state on disk
- it preserves artifacts from each step
- it keeps work moving toward a shipped first version
- it only pauses when there is a real blocker or a genuinely high-risk decision

## How It Works

The state machine includes these core states:

- `BOOTSTRAP_CODEX`
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

Each run writes durable files like:

- `run_spec.json`
- `state.json`
- `events.jsonl`
- `status.md`
- `latest_update.md`
- `human_progress.md`
- artifacts under `artifacts/`

The repository is split between:

- [README.md](README.md): human-facing overview and setup
- [SKILL.md](SKILL.md): the actual skill contract Codex reads
- [scripts/mvp_builder.py](scripts/mvp_builder.py): the runner and state machine
- [prompts/](prompts): prompt templates for each state

## Research

This version is intentionally self-contained.

It does not depend on:

- OpenClaw services
- brokered research queues
- researcher agents
- other Codex skills

When research is needed, Codex uses its own built-in web search directly inside the workflow and writes the useful conclusions into the run artifacts.

## Install

Clone or copy this folder into your Codex skills directory:

```bash
git clone https://github.com/Pourias/Codex-MVP-builder.git ~/.codex/skills/mvp-builder
```

Or, if you already have the folder locally:

```bash
mkdir -p ~/.codex/skills
cp -R ./mvp-builder ~/.codex/skills/mvp-builder
```

## Use In Codex

Open a fresh Codex thread and say something like:

```text
Use $mvp-builder to build a tiny local CRM for one salesperson.
```

If you want to drive the runner manually or debug a run, use the CLI commands below.

## Usage

Initialize a run:

```bash
python3 ~/.codex/skills/mvp-builder/scripts/mvp_builder.py init \
  --raw-input "Build a tiny local CRM for one salesperson"
```

Render the current prompt:

```bash
python3 ~/.codex/skills/mvp-builder/scripts/mvp_builder.py render-prompt --run <run-dir>
```

Apply the reply for that state:

```bash
python3 ~/.codex/skills/mvp-builder/scripts/mvp_builder.py apply-reply \
  --run <run-dir> \
  --reply-file /absolute/path/to/reply.md
```

Check status:

```bash
python3 ~/.codex/skills/mvp-builder/scripts/mvp_builder.py status --run <run-dir>
```

## Validation

The runner itself uses only the Python standard library.

You can do a minimal local validation with:

```bash
python3 -m py_compile ~/.codex/skills/mvp-builder/scripts/mvp_builder.py
```

If you want to use the bundled Codex skill validator, install `PyYAML` first:

```bash
python3 -m pip install PyYAML
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/mvp-builder
```

## Community

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Support: [SUPPORT.md](SUPPORT.md)
- Security reporting: [SECURITY.md](SECURITY.md)

## License

This project is released under the MIT License. See `LICENSE`.

## Best First Test

The best way to test `mvp-builder` is in a fresh Codex thread with a small real MVP request, for example:

- a tiny CRM notes app
- a local habit tracker
- a one-page invoice tracker
- a simple shared expense tracker

Start small. The point of the first test is to see whether the workflow stays focused, uses research when needed, and gets to a believable MVP handoff with minimal intervention.

## Maintainer

Maintained by [@Pourias](https://github.com/Pourias).
