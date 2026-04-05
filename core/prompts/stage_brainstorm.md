You are in the stage-planning step for stage `{{stage_name}}` of project `{{factory_name}}`.

Stage position:
`{{stage_index_display}} / {{stage_count}}`

Approved build prompt:
```text
{{active_build_request}}
```

Architecture artifact:
`{{architecture_artifact_path}}`

Scaffold artifact:
`{{scaffold_artifact_path}}`

Previous verified stage handoff artifact:
`{{previous_stage_handoff_artifact_display}}`

Stage purpose:
`{{stage_purpose}}`

Your job in this stage is to prepare the stage brief before focused research or implementation begins.

Use the approved build prompt, architecture artifact, scaffold artifact, and previous verified stage handoff above as the source of truth.

Do not build anything yet.
Do not perform the focused research yet.
Do not change the frozen stage list unless you are flagging a clear stage-sizing problem.

Focus on:

- the exact objective of this stage and why it exists
- the boundary of this stage:
  what belongs in this stage and what must be left to another stage
- the required inputs, dependencies, and source artifacts for this stage
- how the previous verified stage handoff constrains or enables this stage
- the outputs, deliverables, interfaces, and handoff expectations for the next stage
- the acceptance criteria or done criteria for this stage
- the files, modules, artifacts, tools, APIs, or commands this stage likely needs
- the main risks, unknowns, dependencies, and weak spots in this stage
- the exact research brief that Stage 7 should answer before implementation
- whether this stage appears too broad, too small, or mis-sized, without silently changing the stage list

Return in this exact structure:

Stage Brief
- Objective:
- Why this stage exists:
- In scope:
- Out of scope:
- Required inputs and source artifacts:
- Planned outputs and handoff:
- Files, modules, and artifacts likely involved:
- Interfaces, tools, APIs, or commands needed:
- Acceptance criteria:
- Risks, dependencies, assumptions, and open questions:
- Stage sizing note:

Research Brief For Stage 7
- What research should answer:
- Public repo patterns to inspect:
- Tools, libraries, or workflow patterns to evaluate:
- Tradeoffs to compare:
- Anti-patterns or failure modes to avoid:
- Open technical questions:
