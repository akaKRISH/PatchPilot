# PatchPilot — Gemini & Antigravity Instructions

## Workspace Boundaries
- Workspace Root: `C:\Users\2k25c\PROJECTS\patchpilot\`
- Never touch files outside this directory.
- Preserve all existing files.
- Use the project-local `.venv` for Python execution.

## Architectural Constraints
- Model Inference: Local Ollama (`qwen3.5:4b` on `http://localhost:11434`, think=False).
- Strict Single-Agent Loop: Orchestrator -> Context Builder -> Tool Registry -> Repair Loop.
- Immutable Target Repositories: File manifest hashes are calculated before repair and verified after repair. Any mutation of the source repository triggers a safety fault.
- Test Execution: Docker sandbox preferred; host execution disabled by default.
