# PatchPilot — Agent Operating Guidelines

This file governs any AI assistant or coding agent working within the PatchPilot codebase.

## 1. Prime Directive: Immutability of Target Repositories

- PatchPilot is a self-healing repair agent designed to test and patch code in **disposable copies only**.
- When repairing a user codebase or running tests, **never** modify the user's source repository directly.
- The target source repository is treated as read-only.
- All patches are exported to the PatchPilot data directory (`.patchpilot-data/`) as unified diffs and structured run reports.

## 2. Safety and Architecture Boundaries

- **Local First:** All inference communicates with local Ollama (`http://localhost:11434`), default model `qwen3.5:4b` with think=False. No external or paid cloud APIs.
- **Controlled Tool Registry:** The agent only acts through explicitly registered tools (`inspect_repository`, `search_code`, `read_file`, `edit_file`, `run_tests`). Arbitrary shell execution or dynamic tool registration is strictly forbidden.
- **Path Sanitization:** All relative paths must resolve within the disposable workspace boundary. `..` traversal and escaping symlinks must raise `PathTraversalError`.
- **Predefined Commands:** Only registered test suites (`pytest`, `unittest`, `compileall`) can be executed.
- **Docker Isolation:** Repository tests must run inside containerized Docker sandboxes. Do not fall back to host execution without explicit interactive user approval.

## 3. Testing and Verification Standards

- All new functionality must have corresponding unit, security, and verification tests.
- When fixing issues or adding features in PatchPilot, run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\python.exe -m ruff check .
  .\.venv\Scripts\python.exe -m mypy src tests
  ```
- Never suppress safety failures, skip security checks, or claim a feature works without verifiable automated test output.
