# PatchPilot — User Guide

This guide provides end-to-end instructions for diagnosing environments, executing repairs, reviewing artifacts, and resolving common errors.

## Installation & First-Time Setup

1. **Ensure Ollama is installed and running:**
   ```powershell
   ollama pull qwen3.5:4b
   ```
2. **Setup virtual environment:**
   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```
3. **Run Doctor:**
   ```powershell
   python -m patchpilot doctor
   ```

---

## Command Reference

### `patchpilot doctor`
Performs comprehensive pre-flight verification:
- Python version >= 3.11
- Configuration file / environment syntax
- Ollama endpoint reachability
- Model presence in local tags
- Docker daemon status and sandbox image readiness
- Data directory write permissions

### `patchpilot models`
Lists all models currently available in local Ollama and highlights whether the configured model is installed.

### `patchpilot chat "<PROMPT>"`
Direct test query to the configured model.

### `patchpilot repair --repo <PATH> --task "<TASK>" [--test-suite <SUITE>]`
Executes an isolated repair mission.
- `--repo`: Target project root.
- `--task`: Description of the bug to resolve.
- `--test-suite`: Predefined test suite (`pytest`, `unittest`, `compileall`, `jest`, `go_test`, or `cargo_test`).
- `--test-target`: Optional relative path to a specific test file.
- `--allow-host-execution`: Opt-in to run tests directly on the host if Docker is unavailable.

### `patchpilot runs list`
Lists all past repair runs with run IDs, final outcomes, durations, and attempt counts.

### `patchpilot runs show <RUN_ID>`
Displays detailed execution metadata and the full unified diff.

### `patchpilot eval --suite smoke`
Executes local evaluation cases from `evals/cases/manifest.json`.

---

## Troubleshooting & FAQ

### "Ollama is not running at http://localhost:11434"
Start Ollama via the Windows start menu or run `ollama serve` in a background terminal.

### "Model 'qwen3.5:9b' not found"
Download the model using `ollama pull qwen3.5:9b`.

### "Docker sandbox is unavailable"
To protect your machine, PatchPilot will not run untrusted tests directly on your host by default. Either start Docker Desktop and run `docker build -t patchpilot-sandbox:latest sandbox/`, or explicitly pass `--allow-host-execution` if you trust the repository.
