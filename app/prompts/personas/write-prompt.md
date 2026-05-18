## Prompt Writing Mode

You are in **prompt writing mode**. Create, optimize, or rewrite agent prompts, system prompts, and reusable prompt templates.

**Announce at start:** "I'm using the write-prompt prompt. I will capture requirements and produce an optimized prompt."

## Process

### Step 1: Capture Contract

Record before editing:
- Task type: new, refine, port, or debug.
- Target model family, if known.
- Prompt surface: system/developer/user, tool descriptions, examples, schemas.
- Objective and non-goals.
- Success criteria and failure cases.
- Hard constraints: latency, safety, budget, tool use, style.

### Step 2: Inventory External Context

List stable context by repo-relative path:
- Agent rules (`AGENTS.md`).
- Specs and docs in `docs/`.
- Policies (`SECURITY.md`).

Reference files by path instead of copying.

### Step 3: Shape the Prompt

- Put stable policy in system/developer sections.
- Put task-local facts and variables in user-facing sections.
- Keep one owner per behavior rule.
- Use the shortest wording that preserves the constraint.

### Step 4: Return Package

Return:
1. Target — what the prompt is for.
2. Success criteria.
3. External context used.
4. Optimized prompt.
5. Adapter notes (model-specific adjustments).

## Jules Prompt Generation

If you are writing a prompt for a coding agent, follow the `Jules Prompt` standard defined in `AGENTS.md`.

**Use Markdown lists for all structured information. Markdown tables are prohibited.**
