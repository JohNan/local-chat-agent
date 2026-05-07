# ADR: Jules Prompt Content Standardization

## Status
Accepted

## Context
The user expressed dissatisfaction with the current Jules Prompt generation process. Specifically:
1. The deployment system only captures content after the *last* `## Jules Prompt` heading.
2. Autonomous agents (like Jules) benefit from architectural context like ADRs and diagrams within their execution context.

## Decision
We will standardize the Jules Prompt format to include all necessary context (Summary, ADR, Diagram, and Instructions) within a single `## Jules Prompt` block at the end of the Architect's response.

## Consequences
- Jules will have immediate access to the "why" (ADR) and "how" (Diagram) of the task.
- The Architect must ensure only one `## Jules Prompt` heading is used per response.
- Prompts will be longer but more self-contained.
