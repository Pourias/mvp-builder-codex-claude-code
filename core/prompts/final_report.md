You are in the final reporting stage for project `{{factory_name}}`.

Approved build prompt:
```text
{{active_build_request}}
```

Frozen stage list:
```text
{{stage_manifest}}
```

Final verification artifact:
`{{last_reply_artifact}}`

Write a concise final completion report.

Include:

- a short summary of the project
- what was completed
- the final stage list
- what still remains
- missing API keys, integrations, or setup items
- known limitations or gaps
- what the human should test next

Important constraints:

- keep the report structured and concise
- do not claim work was completed if it was not actually completed
- make the next human testing step concrete and easy to follow
