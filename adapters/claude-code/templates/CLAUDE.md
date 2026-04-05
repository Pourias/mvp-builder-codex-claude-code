## MVP Builder

This project has access to the shared `mvp-builder` workflow installed at `__MVP_BUILDER_REPO_ROOT__`.

When the user explicitly asks to use MVP Builder or runs `/mvp-builder`:

- use the shared runner at `__MVP_BUILDER_REPO_ROOT__/core/scripts/mvp_builder.py`
- initialize with `--host claude-code --calling-agent claude-code --workspace-path "$PWD"` when starting a new run
- do not skip workflow states
- use native web research only when it is genuinely useful
- preserve the run artifacts and status files
- pause only for real blockers, risky destructive actions, credentials, or high-consequence ambiguity
