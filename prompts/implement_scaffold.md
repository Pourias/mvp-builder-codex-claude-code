You are in the scaffold-implementation stage for project `{{factory_name}}`.

Approved build prompt:
```text
{{active_build_request}}
```

Architecture recommendation artifact:
`{{architecture_artifact_path}}`

Your job in this stage is to create the project scaffold that the later stages will build on.

Use the architecture recommendation artifact above as the source of truth.

What to do:

- create the minimal file and folder structure needed for this project
- create the main entry points, modules, and wiring points
- add placeholders or light skeletons where later stages will implement behavior
- prepare the structure so we can improve each stage one by one later

Important constraints:

- do not fully implement the feature behavior yet
- do not collapse later stages into this stage
- do not stop for unnecessary questions
- do not wait for API keys unless local wiring is impossible without them
- if the project is simple, keep the scaffold very simple
- do not add frameworks, services, or abstractions unless the architecture recommendation clearly justifies them
- make reasonable development decisions yourself

Return:

- scaffold summary
- exact files, folders, or modules created or changed
- the purpose of each file or module
- what was intentionally deferred to later stages
- any real blocker that prevents moving on
