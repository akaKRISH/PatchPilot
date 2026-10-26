# PatchPilot — Safety Model

## Foundational Principle: Untrusted Intelligence, Trusted Enforcement

PatchPilot treats both the LLM's outputs and the target repository's contents as untrusted inputs. Security boundaries are implemented in conventional Python code rather than relying exclusively on prompt adherence.

## Invariant Safety Rules

### 1. Source Repository Immutability
- Target repositories are never edited in place.
- All repairs operate within temporary workspaces inside `.patchpilot-data/workspaces/<run_id>/`.
- Before any repair attempt, a cryptographic manifest (SHA-256) is recorded for all source files.
- After completion, this manifest is re-evaluated. If any byte in the original repository changed, the run fails immediately with `FAILED_SAFETY_CHECK`.

### 2. Path Containment
- All relative paths passed to tools (`read_file`, `edit_file`) are canonicalized using `.resolve()` and checked against the disposable workspace root.
- Parent-directory traversals (`..`), null bytes, or absolute paths outside the workspace raise `PathTraversalError`.
- Symlinks pointing outside the workspace raise `SymlinkEscapeError`.

### 3. Secret and Key Protection
- Files matching secret patterns (`.env`, `*.pem`, `*.key`, `id_rsa`, `node_modules`, `.git`, `.venv`) are automatically excluded from the disposable workspace manifest.
- Any attempt to access them directly triggers `SecretAccessError`.
- All output logs and terminal displays pass through the regex-based `redact_sensitive_text` engine.

### 4. Command Policy & Sandboxing
- The LLM has no generic terminal, bash, or powershell tool.
- The `run_tests` tool accepts only enumerated test suite names (`pytest`, `unittest`, `compileall`).
- Tests are executed inside a Docker container with `--network none`, `--read-only`, and unprivileged users.
- Host execution is disabled by default and requires explicit CLI opt-in (`--allow-host-execution`).

### 5. Bounded Budgets
- Hard maximum limits are placed on:
  - Agent steps per attempt (`max_agent_steps = 12`)
  - Total tool calls (`max_tool_calls = 24`)
  - Repair attempts (`max_repair_attempts = 3`)
  - File reading size (`max_file_bytes = 200,000`)
  - Test command execution time (`test_timeout_seconds = 120`)
