# ADR: Persona Write Isolation (OS-Level Read-Only Enforcement)

Status: **Proposed / Deferred** — captured for a future iteration. Not yet implemented.

## Context

The persona model was collapsed to two top-level personas:

- **CHAT** — read-only. Advises, plans, and emits an ADR + `## Jules Prompt` for delegation.
- **CODE** — read-write. Implements changes directly.

Write access is currently enforced at the **application layer** by a single gate,
`git_ops._writes_allowed()`, which requires both the global `config.WRITE_ACCESS_ENABLED`
kill-switch and a write-capable active persona (only CODE):

- `git_ops.write_file_safe` / `replace_in_file_safe` / `write_to_docs` check it.
- `mcp_server.run_shell_command` checks it.
- The ACP `delete_file` handler in `llm_service.py` checks it.
- In SDK mode, `get_tool_config` additionally withholds write tools entirely when write
  access is off.

This is solid defense-in-depth, but it is **cooperative**: the read-only guarantee for CHAT
depends on the model not finding an ungated path, on no prompt-injection (e.g. via a file CHAT
reads) inducing a write, and on every future write path remembering to call `_writes_allowed()`.
For a stronger, tamper-proof boundary we want the **operating system**, not the model, to decide
what is writable.

## Why not Gemini CLI's built-in `--sandbox`

Gemini CLI's `--sandbox` has two backends:

- **macOS Seatbelt** (`sandbox-exec`) — no container, but macOS-only.
- **Container** (Docker / Podman) — required on Linux.

This app runs inside a Linux container (`python:3.13-slim`), so `--sandbox` would require the
**container backend → Docker-in-Docker**. DinD inside our already-Dockerized app means either
mounting the host Docker socket or running a privileged DinD daemon — both add security/ops cost
and are best avoided. So Gemini's own sandbox is impractical here. **However, we do not need it to
achieve the goal.**

## Decision (proposed)

Enforce read-only at the **process boundary** for the **CLI engine** by dropping privileges on the
spawned `gemini` subprocess per persona, while keeping `_writes_allowed()` as the app-level gate.

### Approach A — privilege-drop (recommended, fewest host dependencies)

1. Stop running as root. The Dockerfile currently has no `USER` directive, so the agent and the
   `gemini` subprocess run as root and can write `/codebase` regardless of persona.
2. Create an unprivileged user/group (e.g. `agent`) **without** write permission on `/codebase`,
   and a write-capable user/group for CODE. Set ownership/group on `/codebase` so:
   - CHAT's user can read but not write.
   - CODE's user/group can write.
3. In `spawn_agent_process` (CLI engine, `llm_service.py`), spawn `gemini` with the uid/gid that
   matches the active persona (CHAT → read-only user, CODE → write user).

**Why this is clean:** in ACP mode the MCP server is a **child of the `gemini` process**
(launched via `McpServerStdio`). A single privilege-drop at the `gemini` spawn is therefore
inherited by the MCP server, so `write_file_safe` / `replace_safe` / `run_shell_command` and the
model's built-in tools are all constrained by one OS boundary — no per-tool policing required.

### Approach B — bubblewrap (alternative)

Wrap the spawn: `bwrap --ro-bind /codebase /codebase … gemini …` for CHAT, `--bind` (rw) for CODE.
Purpose-built and daemonless, but requires `bubblewrap` installed and **unprivileged user
namespaces** enabled, which depends on how the outer container is launched. Prefer Approach A
unless namespaces are already available.

## Consequences

- **CLI engine** gets a kernel-enforced read-only boundary for CHAT that no prompt or tool
  confusion can defeat.
- **SDK engine** is unchanged: tools run **in-process** in the FastAPI app, so privileges cannot be
  dropped per-request. SDK mode continues to rely on the application-level `_writes_allowed()` gate
  and tool withholding. Acceptable because this app is primarily CLI.
- Requires Dockerfile changes (create users, set `/codebase` ownership/group) and a uid/gid argument
  threaded into `spawn_agent_process`.
- `_writes_allowed()` stays as defense-in-depth even after OS isolation lands.

## Related design note (already implemented)

The "deny built-in `write_file`/`replace` via `fix_tools_policy.toml`, force MCP
`write_file_safe`/`replace_safe`" pattern remains. Its real purpose is to give one interception
point for writes (path validation, persona checks). With OS isolation in place this becomes a
convenience rather than a security boundary. The CLI-specific guidance telling CODE to use the safe
tool variants now lives in `prompt_router.CLI_CODE_TOOL_GUIDANCE` (appended to the system
instruction only for CODE + CLI).

## Next steps when resumed

1. Add a non-root `agent` user + a write group to `Dockerfile`; set `/codebase` ownership so CHAT
   cannot write and CODE can.
2. Thread persona-derived uid/gid into `spawn_agent_process` in `app/services/llm_service.py`.
3. Verify the MCP child process inherits the dropped privileges (CHAT: confirm a write attempt
   fails at the OS level, not just via `_writes_allowed()`).
4. Confirm CODE still writes and runs tests/shell normally.
