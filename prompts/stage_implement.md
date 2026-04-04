You are in the implementation step for stage `{{stage_name}}` of project `{{factory_name}}`.

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

Previous verified stage handoff artifact:
`{{previous_stage_handoff_artifact_display}}`

Acceptance criteria to satisfy:
```text
{{stage_acceptance_criteria_display}}
```

Your job in this stage is to implement or improve this stage based on the accepted recommendations.

Use the approved build prompt, stage brief, completed stage research, and previous verified stage handoff as the source of truth.

What to do:

- implement the recommendations you believe are best
- make reasonable development decisions yourself
- wire as much as possible even if some API keys are missing
- keep the work proportional to the actual goal and boundary of this stage
- make sure the implementation is aligned with the stage acceptance criteria and planned handoff
- preserve any continuity constraints established by the previous verified stage handoff
- prefer the smallest clean implementation that satisfies the stage

Important constraints:

- do not ask unnecessary questions
- do not block on missing API keys if stubs, wiring, or partial setup can still be done
- if the project is simple, keep the implementation simple
- do not silently expand the stage beyond the agreed boundary unless you clearly explain why
- only treat something as blocked if you truly cannot continue

Return:

- implementation summary
- exact files or modules touched
- important development decisions made
- test evidence:
  exact checks, commands, or validation steps performed and what each one showed
- what was intentionally left for later stages
- anything still incomplete
- any real blocker that remains
