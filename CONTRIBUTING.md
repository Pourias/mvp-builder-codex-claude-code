# Contributing to MVP Builder

Thanks for helping improve `mvp-builder`.

This project is trying to make coding agents more autonomous at getting from a vague product request to a believable MVP, while staying small, durable, and understandable. Contributions are most helpful when they improve that core mission without adding unnecessary complexity.

## Good Contribution Areas

- tighter prompt wording that reduces drift
- better state transitions or artifact handling
- stronger verification behavior
- clearer documentation for users and contributors
- bug fixes in the runner
- tests and validation improvements

## Before You Start

- Read [README.md](README.md) for the public overview.
- Read [SKILL.md](SKILL.md) for the actual agent-facing contract.
- Check existing issues before starting work on a larger change.
- For anything non-trivial, open an issue first so we can align on scope.

## Contribution Principles

- Keep the workflow stateful, explicit, and easy to inspect.
- Prefer small, focused improvements over broad rewrites.
- Preserve the self-contained design.
- Avoid adding external services or hidden orchestration dependencies.
- Prefer Python standard library unless a new dependency has a strong payoff.
- Keep the MVP bias: the skill should help ship a first version, not overbuild.

## Development Notes

Important files:

- [SKILL.md](SKILL.md)
- [core/scripts/mvp_builder.py](core/scripts/mvp_builder.py)
- [core/prompts/](core/prompts)
- [adapters/claude-code/](adapters/claude-code)
- [agents/openai.yaml](agents/openai.yaml)

Try to keep user-facing docs in `README.md` and agent-facing operational guidance in `SKILL.md`.

## Validation

Minimum local check:

```bash
python3 -m py_compile core/scripts/mvp_builder.py
```

Optional validator if you have the bundled Codex system skill available:

```bash
python3 -m pip install PyYAML
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/mvp-builder
```

If your change affects prompts or state transitions, a real smoke run is strongly encouraged.

## Pull Requests

Please keep pull requests narrow and explain:

- what changed
- why it changed
- how you validated it
- any tradeoffs or follow-up work

Use the pull request template when opening a PR.

## Communication

- Bugs: use the bug report issue form
- Ideas: use the feature request form
- Questions: see [SUPPORT.md](SUPPORT.md)
- Security issues: follow [SECURITY.md](SECURITY.md)
