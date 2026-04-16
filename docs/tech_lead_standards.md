# Technical Lead Standards

These standards are for the **Technical Lead Agent** (Prompt Architect) and should be followed when generating prompts or architectural decisions.

## Prompting Standards (Jules Prompts)
When generating a ## Jules Prompt, the Technical Lead must ensure maximum context density:
1. **Architectural Intent:** If the task involves a design change, create an ADR in `docs/` and reference it in the prompt.
2. **Visual Logic:** Include Mermaid diagrams directly in the prompt block for complex state machines, data flows, or component hierarchies.
3. **Reference Docs:** Always instruct Jules to read `AGENTS.md` and any newly created task-specific documentation in `docs/`.
4. **Structure:** Start with a concise one-sentence summary, followed by specific technical requirements and acceptance criteria.

## Documentation Responsibility
- Maintain `AGENTS.md` for the Coding Agent.
- Create ADRs in `docs/` for significant changes.
- Ensure `README.md` is up-to-date with setup instructions.
