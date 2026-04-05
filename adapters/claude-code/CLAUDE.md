# Claude Code Adapter

This folder contains the installable Claude Code adapter for the shared `mvp-builder` core.

Use the installer from the repo root:

```bash
python3 core/scripts/install_claude_code_adapter.py \
  --project /absolute/path/to/your/project
```

That will:

- add or update an `MVP Builder` block in the target project's `CLAUDE.md`
- install `.claude/commands/mvp-builder.md` into the target project

The installed adapter points back to the shared runner at `core/scripts/mvp_builder.py`.
