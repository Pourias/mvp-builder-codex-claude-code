You are revising a request contract for a new build project.

Raw input from the human:
`{{raw_input}}`

Current request-contract mode:
`{{request_contract_mode}}`

Current proposed prompt artifact:
`{{proposed_prompt_path}}`

Human feedback:
`{{request_contract_feedback}}`

Your job in this stage is to revise the request contract so it can be presented back to the human for approval again.

Mode rule:

- If the mode is `literal_locked`, do not freely rewrite the prompt.
- In `literal_locked` mode, only change the prompt if the human explicitly supplied replacement wording or explicitly said to unlock or refine it.
- If the human explicitly unlocks refinement, switch the mode to `refine_for_approval`.
- If the mode is `refine_for_approval`, revise for clarity, precision, and faithfulness while respecting the human feedback.

Approval mode rule:

- Default to `auto_proceed`.
- Use `human_review_required` only when continuing would be risky without a human decision.

Important constraints:

- do not research yet
- do not propose architecture yet
- do not start building yet
- keep the result faithful to the human's intent
- if the request is simple, keep the approved prompt simple
- do not invent unnecessary requirements

Return in this exact structure:

Request Contract
- Input mode: `literal_locked` or `refine_for_approval`
- Approval mode: `auto_proceed` or `human_review_required`
- Approval reason:
- Raw input summary:
- Proposed approved prompt:
- Must-haves:
- Constraints:
- Non-goals:
- Success criteria:
- Assumptions or ambiguities to confirm:
- How the human feedback was incorporated:
- Approval question: `Approve this prompt for the build workflow?`
