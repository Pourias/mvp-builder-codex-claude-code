You are in the stage-enumeration step for project `{{factory_name}}`.

Approved build prompt:
```text
{{active_build_request}}
```

Scaffold artifact:
`{{scaffold_artifact_path}}`

Your job in this stage is to freeze the final ordered implementation stage list for this project.

Use the scaffold artifact above as the source of truth for what has already been set up.

Requirements:

- order the stages from start to finish
- keep the list concise and practical
- make it high-level enough to guide implementation
- make it specific enough that we can work through it stage by stage
- if the project is simple, keep the stage count small and merge unnecessary steps
- do not include stages that are already fully handled by the scaffold step
- do not create unnecessary micro-stages
- make the stage names short, stable, and implementation-friendly
- optimize for a good first shipped MVP, not completeness theater

Return:

- the final ordered stage list as a numbered list
- one line of purpose for each stage
- no extra commentary outside the stage list
