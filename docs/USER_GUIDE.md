# PatchPilot — User Guide

This guide provides end-to-end instructions for installing PatchPilot, diagnosing environment readiness, executing safe repairs, reviewing artifacts, and resolving common errors.

---

## Table of Contents

1. [First-Time Developer Journey](#first-time-developer-journey)
2. [Installation & Setup](#installation--setup)
3. [Configuration Reference](#configuration-reference)
4. [Preflight Diagnostics (`doctor`)](#preflight-diagnostics-doctor)
5. [Safe Demonstration (`demo`)](#safe-demonstration-demo)
6. [Repairing Your Own Project (`repair`)](#repairing-your-own-project-repair)
7. [Inspecting Runs & Patch Artifacts (`runs`)](#inspecting-runs--patch-artifacts-runs)
8. [Benchmark Evaluation (`eval`)](#benchmark-evaluation-eval)
9. [Safety Architecture: Sandbox vs. Host Execution](#safety-architecture-sandbox-vs-host-execution)
10. [Artifact & Storage Layout](#artifact--storage-layout)
11. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## First-Time Developer Journey

PatchPilot is built to provide an immediate, fail-closed, and safe onboarding experience. If you are using Windows PowerShell, the primary developer journey is:

```powershell
# 1. Discover available commands and flags
patchpilot --help

# 2. Generate a valid local configuration file
patchpilot init

# 3. Verify complete environment readiness (Ollama, Docker, model)
patchpilot doctor

# 4. Safely run an end-to-end self-healing repair demonstration
patchpilot demo

# 5. Repair a real bug in your own repository
patchpilot repair --repo "C:\path\to\project" --task "Fix the failing calculator test"

# 6. View recorded repair history
patchpilot runs list

# 7. Inspect the generated unified diff and report
patchpilot runs show <run-id>

# 8. Apply the verified patch to your project
git apply .patchpilot-data\runs\<run-id>.patch
```

---

## Installation & Setup

### Prerequisites

- **Python:** Version 3.11, 3.12, or 3.13.
- **Ollama:** Installed and running locally (download from [ollama.com](https://ollama.com/)).
- **Docker Desktop:** Installed and running with Linux container mode enabled (download from [docker.com](https://www.docker.com/)).

---

### Option A: Automated PowerShell Setup (Windows)

PatchPilot includes an automated setup script that prepares your development environment:

```powershell
.\scripts\setup.ps1
```

**What `setup.ps1` does:**
1. Searches for Python 3.13, 3.12, or 3.11 via `py` launcher or `python`.
2. Creates `.venv` in the repository root if one does not already exist.
3. Upgrades `pip` and installs PatchPilot in editable mode with development dependencies (`pip install -e ".[dev]"`).
4. Checks whether the Ollama server is running at `http://localhost:11434`.
5. Checks if `qwen3.5:4b` is installed, displaying exact `ollama pull qwen3.5:4b` instructions if missing (avoiding unexpected multi-gigabyte downloads).
6. Checks whether the Docker daemon is accessible and automatically builds `patchpilot-sandbox:latest` if Docker is running.
7. Executes `patchpilot doctor` to display an overall readiness verdict.

> **Tip (Execution Policy):** If PowerShell prevents running scripts, enable process-level bypass:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\scripts\setup.ps1
> ```

---

### Option B: Manual Setup

1. **Start Ollama and pull the default model:**
   ```powershell
   ollama serve
   ollama pull qwen3.5:4b
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   # Windows PowerShell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```
   *(On Linux / macOS: `python3.13 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`)*

3. **Build the Docker test sandbox:**
   ```powershell
   docker build -t patchpilot-sandbox:latest .\sandbox\
   ```

4. **Verify installation:**
   ```powershell
   patchpilot --help
   ```

---

## Configuration Reference

PatchPilot loads settings from `.patchpilot.toml` (or a custom path via `--config`), overridden by environment variables with the `PATCHPILOT_` prefix.

### Generating Configuration (`patchpilot init`)

The `init` command generates a `.patchpilot.toml` file with tested defaults:

```powershell
# Create .patchpilot.toml in the current directory
patchpilot init

# Overwrite an existing configuration explicitly
patchpilot init --force

# Write configuration to a custom path
patchpilot init --path C:\path\to\.patchpilot.toml
```

**Output & Overwrite Protection:**
- By default, if `.patchpilot.toml` already exists, `patchpilot init` aborts with exit code `1` and instructs you to use `--force`.
- When successful, it prints the resolved configuration file path and reminds you to run `patchpilot doctor`.

### Configuration Schema

```toml
# .patchpilot.toml
[model]
name = "qwen3.5:4b"
ollama_base_url = "http://localhost:11434"
request_timeout_seconds = 180
think = false

[agent]
max_repair_attempts = 3
max_agent_steps = 12
max_tool_calls = 24
max_context_characters = 50000

[safety]
max_file_bytes = 200000
test_timeout_seconds = 120
max_command_output_characters = 20000
allow_host_execution = false

[storage]
data_dir = ".patchpilot-data"
```

### Settings & Environment Variables

| TOML Key | Section | Environment Variable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | `[model]` | `PATCHPILOT_MODEL_NAME` | `qwen3.5:4b` | Target Ollama model with native tool-calling capabilities. |
| `ollama_base_url` | `[model]` | `PATCHPILOT_OLLAMA_BASE_URL` | `http://localhost:11434` | HTTP endpoint of the local Ollama server. Must start with `http://` or `https://`. |
| `request_timeout_seconds` | `[model]` | `PATCHPILOT_REQUEST_TIMEOUT_SECONDS` | `180` | Ollama HTTP request timeout in seconds (5–600). |
| `think` / `ollama_think` | `[model]` | `PATCHPILOT_OLLAMA_THINK` / `PATCHPILOT_THINK` | `false` | Sets top-level `think` parameter in Ollama chat requests. `false` disables chain-of-thought tokens for fast tool execution. |
| `max_repair_attempts` | `[agent]` | `PATCHPILOT_MAX_REPAIR_ATTEMPTS` | `3` | Maximum self-healing repair iterations (1–10). |
| `max_agent_steps` | `[agent]` | `PATCHPILOT_MAX_AGENT_STEPS` | `12` | Reasoning step budget per attempt (1–50). |
| `max_tool_calls` | `[agent]` | `PATCHPILOT_MAX_TOOL_CALLS` | `24` | Total tool invocation budget across attempts (1–100). |
| `max_context_characters` | `[agent]` | `PATCHPILOT_MAX_CONTEXT_CHARACTERS` | `50000` | Context window character limit (1,000–200,000). |
| `max_file_bytes` | `[safety]` | `PATCHPILOT_MAX_FILE_BYTES` | `200000` | Maximum file size readable by agent (1 KB–10 MB). |
| `test_timeout_seconds` | `[safety]` | `PATCHPILOT_TEST_TIMEOUT_SECONDS` | `120` | Maximum containerized test run duration in seconds (5–600). |
| `max_command_output_characters` | `[safety]` | `PATCHPILOT_MAX_COMMAND_OUTPUT_CHARACTERS` | `20000` | Maximum test output characters captured (500–100,000). |
| `allow_host_execution` | `[safety]` | `PATCHPILOT_ALLOW_HOST_EXECUTION` | `false` | Unsafe opt-in to execute repository tests directly on the host without Docker. |
| `data_dir` | `[storage]` | `PATCHPILOT_DATA_DIR` | `.patchpilot-data` | Directory storing runs, workspaces, and event logs. |

> **Note on Sandbox Image:** The Docker test runner uses the image `patchpilot-sandbox:latest` (built from `sandbox/Dockerfile`).

---

## Preflight Diagnostics (`doctor`)

The `doctor` command inspects the complete operating environment to determine whether safe sandboxed repairs can run:

```powershell
patchpilot doctor
```

### Diagnostic Checks

| Component | Pass Condition | Remediation Command |
| :--- | :--- | :--- |
| **Python Runtime** | Python `>= 3.11` | Install Python 3.11, 3.12, or 3.13 |
| **Configuration** | Valid TOML / constraints | Run `patchpilot init` |
| **Ollama Server** | HTTP endpoint reachable | Run `ollama serve` |
| **Model Availability** | Model present in `ollama list` | Run `ollama pull qwen3.5:4b` |
| **Docker CLI & Daemon** | `docker info` returns 0 | Start Docker Desktop |
| **Sandbox Image** | `patchpilot-sandbox:latest` present | Run `docker build -t patchpilot-sandbox:latest .\sandbox\` |
| **Data Directory** | Target `.patchpilot-data` writable | Check filesystem permissions |

### Status Verdict & Exit Codes

- **`System Status: READY` (exit code `0`):** The system is fully operational for safe containerized repairs.
- **`System Status: NOT READY` (exit code `1`):** One or more required components are missing. Remediation commands are printed.

### Optional Tool Probe (`--probe-tools`)

Send a test prompt to local Ollama to verify that the model returns structured tool calls:
```powershell
patchpilot doctor --probe-tools
```

---

## Safe Demonstration (`demo`)

PatchPilot includes a reproducible bug test case in [`examples/buggy_python_project`](examples/buggy_python_project).

### The Bug & Expected Repair

In [`examples/buggy_python_project/calculator.py`](examples/buggy_python_project/calculator.py), the `add(a, b)` function has an inverted operator defect:

```python
def add(a: float, b: float) -> float:
    """Return the sum of a and b.

    BUG: Incorrectly subtracts b from a.
    """
    return a - b  # Bug: performs subtraction instead of addition
```

The accompanying unit test suite in [`examples/buggy_python_project/tests/test_calculator.py`](examples/buggy_python_project/tests/test_calculator.py) asserts `assert add(2, 3) == 5`, failing with `AssertionError: assert -1 == 5`.

### Running the Demo

```powershell
patchpilot demo
```

**What happens during the demo:**
1. Verifies Docker and sandbox image readiness (fails closed immediately with exit code `1` if missing).
2. Computes the baseline SHA-256 hash manifest of `examples/buggy_python_project`.
3. Creates a disposable workspace copy in `.patchpilot-data/workspaces/<run_id>/`.
4. Executes the baseline pytest suite inside the isolated Docker sandbox, capturing the failure.
5. Invokes the agent orchestrator: Ollama inspects `calculator.py` using structured tool calls and edits `return a - b` to `return a + b`.
6. Executes the pytest suite again inside Docker: tests pass with zero regressions.
7. Cryptographically verifies that the original `examples/buggy_python_project` repository was never modified.
8. Writes `.patchpilot-data/runs/<run_id>.json` and `.patchpilot-data/runs/<run_id>.patch`.
9. Prints the syntax-highlighted unified diff and reports success with exit code `0`.

---

## Repairing Your Own Project (`repair`)

To diagnose and repair bugs in any project:

```powershell
patchpilot repair `
  --repo "C:\Users\username\Projects\my-app" `
  --task "Fix the failing test in user_auth. Preserve public API." `
  --test-suite pytest `
  --test-target "tests/test_auth.py"
```

### Command Options

- `--repo`, `-r`: Path to target repository (required).
- `--task`, `-t`: Description of the bug to resolve (required).
- `--test-suite`, `-s`: Test framework runner. Choices:
  - `pytest` (default for Python)
  - `unittest` (Python built-in)
  - `compileall` (Python syntax compilation)
  - `jest` (JavaScript/TypeScript)
  - `go_test` (Go)
  - `cargo_test` (Rust)
- `--test-target`: Optional relative path to a specific test file or directory (e.g., `tests/test_calc.py`).
- `--allow-host-execution`: Explicit unsafe opt-in to run tests directly on the host machine without Docker.
- `--config`, `-c`: Custom `.patchpilot.toml` configuration file.

### Fail-Fast Preflight Validation

Before creating an agent or spending time calling the language model, `patchpilot repair` executes preflight checks:
1. Target repository directory exists and is accessible.
2. Configuration parses successfully.
3. Ollama server is reachable.
4. Target model is installed locally.
5. Docker daemon is reachable and the sandbox image exists (unless `--allow-host-execution` was passed).

If any check fails, PatchPilot exits immediately with exit code `1` and shows exact remediation steps.

---

## Inspecting Runs & Patch Artifacts (`runs`)

Every repair session records structured artifacts in `.patchpilot-data/`.

### Listing Historical Runs

```powershell
patchpilot runs list
```

Displays a table of past repair sessions:
- **Run ID:** Timestamped unique identifier (e.g., `run_20261027_065022_9304df06`).
- **Status:** Outcome (`FIXED`, `UNRESOLVED`, `FAILED_SAFETY_CHECK`).
- **Duration:** Wall-clock execution time in seconds.
- **Attempts:** Number of self-healing iterations made (e.g., `1/3`).
- **Task:** Brief task summary.

### Showing Run Details & Diff

```powershell
patchpilot runs show <run-id>
```

Displays:
- Full run metadata (Status, Duration, Attempts).
- Syntax-highlighted unified diff of all accepted file edits.

### Applying the Verified Patch

Because original source repositories are strictly immutable during repair, PatchPilot stores the unified diff on disk. Apply it to your working repository with:

```powershell
git apply .patchpilot-data\runs\<run-id>.patch
```

---

## Benchmark Evaluation (`eval`)

PatchPilot includes a deterministic benchmarking harness for evaluating agent repair rates against curated defect cases:

```powershell
# Run smoke benchmark cases inside the Docker sandbox (default)
patchpilot eval --suite smoke

# Run benchmark cases directly on the host (unsafe opt-in)
patchpilot eval --suite smoke --allow-host-execution
```

Cases are read from `evals/cases/manifest.json`. The harness reports repair convergence rates, step counts, and duration metrics.

---

## Safety Architecture: Sandbox vs. Host Execution

| Aspect | Docker Sandbox (Default) | Host Execution (`--allow-host-execution`) |
| :--- | :--- | :--- |
| **Network Access** | Completely disabled (`--network none`) | Full access to host network and interfaces |
| **Filesystem Access** | Read-only container root; temporary `/tmp` mount | Full access to user filesystem and environment |
| **Privileges** | Unprivileged non-root user (`uid 1000`) | Current user privileges (can modify host files) |
| **Process Isolation** | Kernel namespaces & cgroups | Uncontained host process execution |
| **Default Mode** | **Yes (fail-closed if Docker is missing)** | **No (requires explicit CLI flag)** |
| **Warning Banner** | None (safe by design) | Prominent yellow warning banner displayed |

> **Warning:** Never use `--allow-host-execution` on repositories containing untrusted dependencies or unknown test code.

---

## Artifact & Storage Layout

PatchPilot organizes persistent artifacts beneath `.patchpilot-data/`:

```text
.patchpilot-data/
├── runs/
│   ├── run_20261027_065022_9304df06.json    # Machine-readable RunReport (status, metrics, diff)
│   └── run_20261027_065022_9304df06.patch   # Standard unified diff ready for git apply
├── workspaces/
│   └── run_20261027_065022_9304df06/        # Ephemeral isolated workspace (cleaned up on completion)
└── events.jsonl                             # Append-only operational event trace log
```

---

## Troubleshooting & FAQ

### "Ollama server is unreachable at http://localhost:11434"
**Cause:** Ollama daemon is not running.
**Fix:**
```powershell
ollama serve
```
Or start Ollama Desktop from the Windows Start Menu.

---

### "Model 'qwen3.5:4b' is not installed in local Ollama"
**Cause:** The default model has not been downloaded yet.
**Fix:**
```powershell
ollama pull qwen3.5:4b
```

---

### "Docker daemon is not running or unreachable"
**Cause:** Docker Desktop is stopped or the Docker service has not initialized.
**Fix:**
1. Start Docker Desktop from the Start Menu.
2. Confirm the daemon is responsive:
   ```powershell
   docker info
   ```
3. Run `patchpilot doctor` to verify connectivity.

---

### "Docker sandbox image 'patchpilot-sandbox:latest' is not built"
**Cause:** The container image has not been built yet.
**Fix:** From the repository root, run:
```powershell
docker build -t patchpilot-sandbox:latest .\sandbox\
```

---

### "Configuration file already exists at '.patchpilot.toml'"
**Cause:** `patchpilot init` detected an existing configuration file and refused to overwrite it.
**Fix:** Pass `--force` to explicitly overwrite:
```powershell
patchpilot init --force
```

---

### "Execution policy prevents running scripts" (PowerShell)
**Cause:** Windows default PowerShell execution policy restricts running unsigned `.ps1` scripts.
**Fix:** Temporarily bypass policy for the current PowerShell process:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

### "Can I run PatchPilot without Docker?"
Docker is strongly recommended to protect your host system. However, if Docker cannot be installed and you completely trust the repository code, you may pass the `--allow-host-execution` flag:
```powershell
patchpilot repair --repo "C:\path\to\repo" --task "Fix bug" --allow-host-execution
```
