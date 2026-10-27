# PatchPilot — User Guide

This guide provides end-to-end instructions for installing PatchPilot, diagnosing environment readiness, executing safe repairs, reviewing artifacts, and resolving common errors.

---

## First-Time Setup & Primary Workflow

The primary first-time developer journey is designed to be safe, self-contained, and informative:

```powershell
# 1. Discover available commands
patchpilot --help

# 2. Generate initial configuration with tested defaults
patchpilot init

# 3. Verify complete environment readiness (Ollama, Docker, model)
patchpilot doctor

# 4. Run the safe, sandboxed calculator repair demonstration
patchpilot demo

# 5. Repair a project with a failing test
patchpilot repair --repo "C:\path\to\project" --task "Fix the failing calculator test"

# 6. List historical repair runs
patchpilot runs list

# 7. Inspect the generated unified diff and report
patchpilot runs show <actual-run-id>
```

---

## Installation & Environment Setup

### Option A: Automated PowerShell Setup (Windows)

PatchPilot provides an automated setup script that detects Python 3.11, 3.12, or 3.13, provisions `.venv`, installs dependencies, checks Ollama and model presence, and builds the Docker sandbox image:

```powershell
.\scripts\setup.ps1
```

### Option B: Manual Setup

1. **Ensure Ollama is running and download the default model:**
   ```powershell
   ollama serve
   ollama pull qwen3.5:4b
   ```

2. **Create virtual environment and install in editable mode:**
   ```powershell
   # Windows
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

   *(On Linux/macOS, use `python3.13 -m venv .venv` and `source .venv/bin/activate`)*

3. **Build the Docker sandbox image:**
   ```powershell
   docker build -t patchpilot-sandbox:latest .\sandbox\
   ```

4. **Verify health:**
   ```powershell
   patchpilot doctor
   ```

---

## Command Reference

### `patchpilot init`

Generates `.patchpilot.toml` using the supported schema and tested defaults (`qwen3.5:4b`, Ollama thinking disabled).

```powershell
# Create .patchpilot.toml in the current directory
patchpilot init

# Overwrite existing configuration file
patchpilot init --force

# Write to a custom path
patchpilot init --path C:\path\to\.patchpilot.toml
```

- **Protection:** Refuses to overwrite an existing configuration unless `--force` is explicitly passed.
- **Validation:** Generated configuration is verified against `PatchPilotConfig.load()`.

### `patchpilot doctor [--probe-tools]`

Performs a thorough preflight readiness diagnostic:
- Python version (requires `>= 3.11`)
- Configuration file / environment validity
- Ollama endpoint reachability (`http://localhost:11434`)
- Configured model presence in local Ollama tags
- Docker daemon reachability and `patchpilot-sandbox:latest` image presence
- Data directory write permissions (`.patchpilot-data`)
- Optional tool-calling capability test with `--probe-tools`

**Exit Codes:**
- `0`: All prerequisites satisfied (`System Status: READY`).
- `1`: One or more prerequisites missing (`System Status: NOT READY`). Detailed remediation commands are printed.

### `patchpilot demo [--repo <PATH>]`

Demonstrates the built-in calculator repair in `examples/buggy_python_project` safely using the normal repair pipeline.

```powershell
patchpilot demo
```

- **Safety:** Always uses Docker container sandboxing. Host execution is never enabled implicitly.
- **Fail-Closed:** Halts immediately with exit code 1 if Docker or the sandbox image is missing.
- **Artifacts:** Prints the generated run ID, artifact directory, and instructions for applying the patch.

### `patchpilot repair --repo <PATH> --task "<TASK>" [OPTIONS]`

Initiates the bounded self-healing repair loop on a target repository.

**Preflight Validation:**
Before creating an agent or starting model inference, `patchpilot repair` validates:
1. Target repository directory exists.
2. Configuration parses successfully.
3. Ollama service is reachable.
4. Configured model is installed.
5. Docker daemon is running and `patchpilot-sandbox:latest` exists (unless `--allow-host-execution` is explicitly set).

If any check fails, PatchPilot exits immediately without wasting model reasoning calls.

**Options:**
- `--repo`: Target project root directory (required).
- `--task`: Description of the bug or requirement (required).
- `--test-suite`: Predefined test suite (`pytest`, `unittest`, `compileall`, `jest`, `go_test`, `cargo_test`). Default: `pytest`.
- `--test-target`: Optional relative path to a specific test file or directory.
- `--allow-host-execution`: Explicit unsafe opt-in to execute tests directly on the host machine without Docker. Prints a prominent warning.

### `patchpilot models`

Queries the Ollama API and lists all locally installed models, indicating whether the configured model is ready.

### `patchpilot chat "<MESSAGE>"`

Sends a direct message to the configured Ollama model to test latency and response generation without initiating a repair session.

### `patchpilot runs list`

Lists all historical repair sessions stored in `.patchpilot-data/runs/`, displaying run IDs, final outcomes (`RESOLVED` / `UNRESOLVED`), durations, and attempt counts.

### `patchpilot runs show <RUN_ID>`

Displays comprehensive execution metrics, event timeline, files modified, test logs, and the full unified diff for a specific run.

### `patchpilot eval [--suite <SUITE>] [--allow-host-execution]`

Executes local benchmark evaluation suites from `evals/cases/manifest.json`.

```powershell
# Runs benchmarks safely inside Docker containers (default)
patchpilot eval --suite smoke

# Explicit opt-in for host execution (prints warning)
patchpilot eval --suite smoke --allow-host-execution
```

---

## Troubleshooting & FAQ

### "Ollama is not running at http://localhost:11434"
Start Ollama via the application launcher or run `ollama serve` in a dedicated terminal.

### "Model 'qwen3.5:4b' not found in local Ollama"
Download the default model using:
```powershell
ollama pull qwen3.5:4b
```

### "Docker daemon is not running or unreachable"
Start Docker Desktop on Windows. Verify connectivity with:
```powershell
docker info
```

### "Sandbox image 'patchpilot-sandbox:latest' not found"
Build the sandbox image from the repository root:
```powershell
docker build -t patchpilot-sandbox:latest .\sandbox\
```

### "Can I run repairs without Docker?"
Docker sandboxing is strongly recommended to protect your host filesystem and prevent untrusted test code execution. If Docker is unavailable and you completely trust the repository code, you may pass `--allow-host-execution`:
```powershell
patchpilot repair --repo <PATH> --task "<TASK>" --allow-host-execution
```
