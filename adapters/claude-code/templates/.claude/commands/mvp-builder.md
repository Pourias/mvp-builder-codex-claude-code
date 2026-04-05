---
description: Run or resume MVP Builder for the current project
argument-hint: product request or continuation note
---

Use the shared `mvp-builder` workflow installed at `__MVP_BUILDER_REPO_ROOT__`.

Treat this command as the canonical way to start or continue MVP Builder in this project.

Workflow:

1. Determine whether there is already an active relevant run in `.mvp-builder/runs/`.
2. If there is no relevant active run, initialize one:

```bash
python3 "__MVP_BUILDER_REPO_ROOT__/core/scripts/mvp_builder.py" init \
  --host claude-code \
  --calling-agent claude-code \
  --workspace-path "$PWD" \
  --raw-input "$ARGUMENTS"
```

3. Determine the run directory you are continuing.
4. Render the current prompt:

```bash
python3 "__MVP_BUILDER_REPO_ROOT__/core/scripts/mvp_builder.py" render-prompt --run "<run_dir>"
```

5. Complete that state inside Claude Code. Use native web research only when it is useful.
6. Save your structured reply to a markdown file inside the run directory, for example `<run_dir>/claude-reply.md`.
7. Apply the reply:

```bash
python3 "__MVP_BUILDER_REPO_ROOT__/core/scripts/mvp_builder.py" apply-reply \
  --run "<run_dir>" \
  --reply-file "<run_dir>/claude-reply.md"
```

8. Repeat until the run reaches `COMPLETED` or `FAILED`.

Rules:

- Do not skip states.
- Read `status.md`, `latest_update.md`, and `human_progress.md` before advancing.
- Prefer the smallest believable MVP.
- Ask the human only for real blockers, credentials, destructive actions, or high-consequence ambiguity.
