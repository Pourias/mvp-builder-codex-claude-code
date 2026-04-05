You are in the research-and-architecture stage for a new build project.

Approved build prompt:

```text
{{active_build_request}}
```

Your job in this stage is to research and plan the project. Do not build anything yet.

What to do:

1. Decide whether web search is actually needed for this request.
2. If needed, use the active host's native web research directly for similar implementations, patterns, and best practices.
3. Propose the simplest practical architecture that satisfies the request.
4. Give the project a short working name.
5. Break the work into an ordered list of implementation stages.
6. Keep the architecture and stage list proportional to a first MVP, not a platform rewrite.

Important constraints:

- Do not build anything yet.
- Optimize for clarity and simplicity.
- If the project is simple, the architecture should stay simple.
- Do not invent unnecessary stages, services, or abstractions.
- Do not rely on any other skill or agent.
- Call out assumptions, risks, dependencies, missing API keys, or unknowns.

Return in this exact structure:

Working project name:

Short summary of what is being built:

Research evidence:
- Whether web search was used:
- Key sources or patterns examined:
- What mattered from that research:

Recommended architecture:

Ordered stage list:
1.

Main implementation recommendations:

Risks, assumptions, and open questions:
