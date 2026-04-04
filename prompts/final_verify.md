You are in the final verification stage for project `{{factory_name}}`.

Approved build prompt:
```text
{{active_build_request}}
```

Frozen stage list:
```text
{{stage_manifest}}
```

Latest stage verification artifact:
`{{last_reply_artifact}}`

Your job in this stage is to do a final end-to-end verification pass before human testing.

What to check:

- whether the stages connect correctly from start to finish
- whether the frozen stage list was completed coherently and in the intended order
- whether any handoffs, memory hygiene, or file structure still need tightening
- whether the overall project wiring is sound
- what can be tested right now, even if some API keys are still missing
- every missing API key, integration, or external prerequisite

Important constraints:

- optimize for realistic readiness, not perfection
- do not rebuild the project from scratch in this step
- if the project is simple, keep the final recommendations simple
- include real evidence from commands, tests, or concrete inspection wherever possible

Return:

- an end-to-end verification summary
- what was checked
- verification evidence:
  exact review steps, tests, or checks performed and what each one showed
- what works
- remaining gaps
- missing API keys and setup items
- whether the project is ready for human testing
