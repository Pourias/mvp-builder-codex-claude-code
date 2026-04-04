You are in the verification step for stage `{{stage_name}}` of project `{{factory_name}}`.

Stage position:
`{{stage_index_display}} / {{stage_count}}`

Approved build prompt:
```text
{{active_build_request}}
```

Stage purpose:
`{{stage_purpose}}`

Stage brief artifact:
`{{stage_plan_artifact_path}}`

Stage research artifact:
`{{research_artifact_path}}`

Stage implementation artifact:
`{{last_reply_artifact}}`

Previous verified stage handoff artifact:
`{{previous_stage_handoff_artifact_display}}`

Acceptance criteria to verify:
```text
{{stage_acceptance_criteria_display}}
```

Your job in this stage is to verify that this stage is correctly connected and ready for the next handoff.

Use the approved build prompt and stage brief as the source of truth for what this stage was supposed to accomplish and what “done” means. Use the stage implementation artifact to inspect what was actually reported as implemented.

What to check:

- whether this stage behaves as intended
- whether the files, modules, skills, or integrations are connected correctly
- whether the acceptance criteria from the stage brief are actually met
- whether continuity with the previous verified stage handoff was preserved
- whether the handoff to the next stage is clear
- what testing or validation is possible right now
- which prerequisites are still missing

Important constraints:

- test as much as possible even if some API keys are missing
- partial validation is acceptable when external dependencies are unavailable
- keep the recommendation practical
- prefer real commands, real checks, and real file review over vague confidence statements

Return:

- what you checked
- verification evidence:
  exact checks, tests, commands, or review steps performed and what each one showed
- what works
- what still needs tightening
- whether the acceptance criteria were met
- whether continuity with the previous verified handoff was preserved
- missing API keys or external prerequisites
- whether we should move to the next stage now
