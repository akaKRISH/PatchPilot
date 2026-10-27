<p align="center">
  <img src="docs/assets/patchpilot-mark.svg" alt="PatchPilot Mark" width="96" height="96" />
</p>

<h1 align="center">PatchPilot</h1>

<p align="center">
  <strong>A local-first AI coding agent that repairs code and proves the fix.</strong>
</p>

<p align="center">
  <a href="https://github.com/akaKRISH/PatchPilot/actions/workflows/tests.yml"><img src="https://github.com/akaKRISH/PatchPilot/actions/workflows/tests.yml/badge.svg" alt="Tests" /></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB.svg?style=flat&logo=python&logoColor=white" alt="Python Versions" />
  <img src="https://img.shields.io/badge/ollama-qwen3.5%3A4b-black.svg?logo=ollama" alt="Ollama Default Model" />
  <img src="https://img.shields.io/badge/sandbox-docker%20fail--closed-2496ED.svg?logo=docker&logoColor=white" alt="Docker Sandbox" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#core-architecture--execution-flow">Architecture</a> •
  <a href="#safety-model--workspace-isolation">Safety Model</a> •
  <a href="#repair-walkthrough">Walkthrough</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#verification--quality-gate">Quality Gate</a> •
  <a href="docs/USER_GUIDE.md">User Guide</a>
</p>

---

## Overview

PatchPilot is an autonomous, local-first coding agent engineered to diagnose test failures, generate targeted source repairs, and cryptographically verify patches before touching production code.

Most AI coding assistants apply unverified edits directly to your working tree or upload proprietary source files to external LLM APIs. PatchPilot takes a fundamentally different engineering approach:

1. **Your original repository is strictly immutable.** Every diagnostic step and repair attempt runs inside an isolated, collision-resistant workspace.
2. **Untrusted code runs in a sandbox.** Test suites execute inside ephemeral, unprivileged Docker containers with network access disabled.
3. **Every fix must be proven.** A patch is accepted only if targeted tests pass and pre-existing baseline tests show zero regressions. If verification fails or budget bounds are reached, the agent marks the run as unresolved rather than guessing.
4. **Local by design.** Powered by local Ollama instances (`qwen3.5:4b` default with native tool calling). No external API keys, metered tokens, or cloud telemetry.

---

## Core Architecture & Execution Flow

PatchPilot separates high-level language model reasoning from privileged filesystem and test execution operations. The model is constrained to an explicit tool registry, and every filesystem operation passes through boundary validation.

```mermaid
flowchart TD
    User([Developer Task / Bug Report]) --> CLI[PatchPilot CLI]
    CLI --> Doctor{Preflight Checks}
    Doctor -->|Healthy| Manager[Workspace Manager]
    Manager --> PreHash[Compute Source SHA-256 Manifest]
    PreHash --> Copy[Create Disposable Workspace in .patchpilot-data]
    Copy --> Baseline[Run Baseline Test Suite in Docker]
    Baseline --> Loop[Bounded Self-Healing Loop]

    subgraph Self-Healing Loop [Bounded Repair Loop (Max 3 Attempts)]
        Loop --> Agent[Agent Orchestrator]
        Agent --> Context[Build Prompt & Diagnostics]
        Context --> Ollama[Local Ollama: qwen3.5:4b]
        Ollama -->|Structured Tool Call| Registry[Tool Registry]
        Registry -->|inspect_repo / search_code / read_file| SafeFS[Path Containment Layer]
        Registry -->|edit_file| Workspace[Isolated Workspace]
        Registry -->|run_tests| Runner[Docker Sandbox: --network none]
        Runner --> Verifier[Regression & Verification Engine]
        Verifier -->|Failures / Regressions| Loop
    end

    Verifier -->|Tests Pass & No Regressions| Diff[Generate Unified Diff]
    Diff --> PostHash[Re-verify Source SHA-256 Invariance]
    PostHash -->|Match| Store[Save RunReport & Patch Artifact]
    PostHash -->|Mismatch| SecurityAbort[Abort: Source Immutability Violation]
    Store --> Output([Auditable Run Summary & Patch])
```

---

## Key Capabilities

- **Cryptographic Immutability Guarantee:** Before an agent loop begins, a SHA-256 manifest of the source repository is recorded. After the run completes, this manifest is verified byte-for-byte. Any mutation to the original source triggers an immediate safety abort.
- **Fail-Closed Docker Sandboxing:** Tests run in locked-down containers (`--network none`, `--read-only`, non-root user, and dropped Linux capabilities). If Docker is unavailable and `--allow-host-execution` is not set, PatchPilot safely halts.
- **True Self-Healing with Regression Prevention:** When a test fails or introduces a regression against baseline tests, structured failure output is fed back into the agent context for up to 3 bounded repair attempts.
- **Strict Defensive Tool Registry:** The language model cannot execute arbitrary shell commands. It operates exclusively through five strictly typed, validated tools: `inspect_repository`, `search_code`, `read_file`, `edit_file`, and `run_tests`.
- **Auditable Run Artifacts:** Every execution produces a machine-readable JSON run report, an append-only JSONL event trace, and a standard unified diff ready for `git apply`.

---

## Quickstart

### Prerequisites

- **Python 3.11 – 3.13**
- **[Ollama](https://ollama.com/)** installed and running locally.
- **[Docker Desktop](https://www.docker.com/)** installed and running (required for fail-closed containerized test execution).

---

### Step-by-Step First-Run Workflow

#### 1. Prepare Python Environment

Clone the repository and set up a Python virtual environment:

**Automated Setup (Windows PowerShell):**
```powershell
.\scripts\setup.ps1
```
The setup script auto-detects Python 3.11, 3.12, or 3.13, creates `.venv` if absent, installs package and developer dependencies, checks Ollama connectivity, prompts to pull `qwen3.5:4b` if missing, and automatically builds `patchpilot-sandbox:latest` if Docker is running.

**Manual Setup:**
```powershell
git clone https://github.com/akaKRISH/PatchPilot.git
Set-Location PatchPilot

# Create virtual environment using Python 3.11, 3.12, or 3.13
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```
*(On Linux / macOS: `python3.13 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`)*

#### 2. Start Ollama and Pull Default Model

Ensure the Ollama daemon is running and fetch the tested default model:
```powershell
ollama serve
ollama pull qwen3.5:4b
```

#### 3. Build the Docker Sandbox Image

Build the lightweight, self-contained Python test sandbox:
```powershell
docker build -t patchpilot-sandbox:latest .\sandbox\
```
Verify the Docker daemon is accessible with `docker info`.

#### 4. Initialize Configuration (`patchpilot init`)

Create `.patchpilot.toml` in your working directory with sensible, tested defaults:
```powershell
patchpilot init
```
- **Defaults:** Configures `model_name = "qwen3.5:4b"`, `ollama_base_url = "http://localhost:11434"`, and `think = false` (Ollama thinking disabled for fast tool calling).
- **Overwrite Protection:** If `.patchpilot.toml` already exists, `patchpilot init` refuses to overwrite it to prevent data loss. Pass `--force` to explicitly overwrite.
- **Custom Location:** Use `--path <custom-path>` to write the configuration to an alternative location or parent directory.

#### 5. Verify Readiness (`patchpilot doctor`)

Run the preflight health check to verify all services and permissions:
```powershell
patchpilot doctor
```
`doctor` validates 7 core readiness criteria:
1. **Python Runtime:** Python `>= 3.11`
2. **Configuration:** Valid `.patchpilot.toml` schema and field constraints
3. **Ollama Server:** Local HTTP API reachability (`http://localhost:11434`)
4. **Model Availability:** Configured model (`qwen3.5:4b`) installed in local Ollama tags
5. **Docker CLI / Daemon:** Docker daemon reachable and responsive
6. **Sandbox Image:** `patchpilot-sandbox:latest` built and available locally
7. **Data Directory:** Data storage path (`.patchpilot-data`) writable

**Verdict & Exit Codes:**
- `System Status: READY` (exit code `0`): All prerequisites met; safe sandboxed repairs are ready to run.
- `System Status: NOT READY` (exit code `1`): Identifies missing components with actionable resolution commands (e.g., `ollama serve`, `ollama pull qwen3.5:4b`, `docker build -t patchpilot-sandbox:latest .\sandbox\`).
- *Optional:* Pass `--probe-tools` to test native model tool-calling capability with a lightweight probe.

#### 6. Run the Safe Demo (`patchpilot demo`)

Run an end-to-end self-healing repair demonstration on the bundled calculator project:
```powershell
patchpilot demo
```
- **Safety:** Executes strictly inside the Docker sandbox (`--network none`, read-only container). The original repository remains completely unmodified.
- **Fail-Closed:** Halts immediately with exit code 1 if Docker or the sandbox image is missing.
- **Output:** Reports the run ID, duration, attempt count, generated patch diff, and file artifact paths.

#### 7. Repair Your Own Project & Inspect Artifacts

Diagnose and repair a bug in your own repository:
```powershell
patchpilot repair `
  --repo "C:\path\to\project" `
  --task "Fix the failing test in calculator. Preserve public API." `
  --test-suite pytest
```

Inspect run history and review the generated unified diff:
```powershell
# List all historical repair runs
patchpilot runs list

# Inspect detailed metrics and diff for a specific run
patchpilot runs show <RUN_ID>
```

Apply the verified patch to your project:
```powershell
git apply .patchpilot-data\runs\<RUN_ID>.patch
```

---

## Repair Walkthrough

PatchPilot includes a reproducible bug test case in [`examples/buggy_python_project`](examples/buggy_python_project). The module [`calculator.py`](examples/buggy_python_project/calculator.py) contains an inverted operator bug where `add(a, b)` incorrectly subtracts `b` from `a`:

```python
def add(a: float, b: float) -> float:
    """Return the sum of a and b.

    BUG: Incorrectly subtracts b from a.
    """
    return a - b  # Defect: should be return a + b
```

The test suite in [`tests/test_calculator.py`](examples/buggy_python_project/tests/test_calculator.py) fails with `AssertionError: assert add(2, 3) == 5` (evaluating to `-1`).

### Run the Repair Agent

```powershell
patchpilot repair `
  --repo .\examples\buggy_python_project `
  --task "Fix the bug in the calculator's add function. Preserve the public API." `
  --test-suite pytest
```

### Execution Lifecycle

1. **Preflight & Invariance Check:** PatchPilot verifies system health and records an initial SHA-256 hash manifest of all source files.
2. **Workspace Isolation:** A disposable copy is provisioned at `.patchpilot-data/workspaces/<run_id>/`.
3. **Baseline Evaluation:** The test suite runs inside the Docker sandbox, capturing the failing test assertion.
4. **Agent Inspection & Tool Calling:** The model inspects the repository layout, locates `calculator.py`, and reads the implementation.
5. **Targeted Edit:** The model applies a minimal surgical edit (`return a + b`) inside the temporary workspace.
6. **Sandboxed Verification:** The test runner re-executes `pytest` inside the Docker container. All tests pass with zero regressions.
7. **Integrity Re-evaluation:** The original source directory is verified byte-for-byte against the initial SHA-256 manifest.
8. **Artifact Generation:** The structured JSON report (`.patchpilot-data/runs/<run_id>.json`) and standalone unified diff (`.patchpilot-data/runs/<run_id>.patch`) are written to disk, and the operational event is logged in `.patchpilot-data/events.jsonl`.

Review the resulting patch:
```powershell
patchpilot runs list
patchpilot runs show <RUN_ID>
```

Apply the verified patch to your repository:
```powershell
git apply .patchpilot-data\runs\<RUN_ID>.patch
```

---

## Safety Model & Workspace Isolation

PatchPilot enforces security through deterministic software boundaries rather than relying on LLM instruction-following:

| Defense Layer | Implementation Details |
| :--- | :--- |
| **Path Traversal Containment** | All paths resolve against the workspace root. Traversal patterns (`..`), null bytes, and escaping symlinks trigger immediate validation errors (`PathTraversalError`, `SymlinkEscapeError`). |
| **Secret Redaction** | Sensitive files (`.env`, `*.pem`, `*.key`, `id_rsa`, `.git`, `.venv`) are excluded during workspace cloning. Terminal outputs and stored run logs pass through regex redaction. |
| **Command Whitelist** | The model has no terminal access. `run_tests` only accepts pre-approved test suites (`pytest`, `unittest`, `compileall`, `jest`, `go_test`, `cargo_test`) with immutable argument templates. |
| **Docker Sandbox** | Untrusted test suites run inside isolated containers with `--network none`, `--read-only`, unprivileged user privileges, and strict execution timeouts. |
| **Execution Budgets** | Hard boundaries prevent runaway execution: maximum 3 repair attempts, 12 agent reasoning steps per attempt, and bounded tool calls (24). |

For complete threat vectors and mitigations, refer to [docs/SAFETY_MODEL.md](docs/SAFETY_MODEL.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

---

## CLI Reference

| Command | Options | Purpose |
| :--- | :--- | :--- |
| `patchpilot init` | `[--path, -p <PATH>]`<br>`[--force, -f]` | Generates a valid `.patchpilot.toml` configuration with tested defaults (`qwen3.5:4b`, thinking disabled). Refuses overwrite unless `--force` is set. |
| `patchpilot doctor` | `[--probe-tools]`<br>`[--config, -c <CONFIG>]` | Inspects environment health: Ollama, Docker sandbox, installed models, and data paths. Returns exit code 1 if dependencies are missing. |
| `patchpilot demo` | `[--repo, -r <PATH>]`<br>`[--config, -c <CONFIG>]` | Runs the safe, sandboxed end-to-end repair demonstration on `examples/buggy_python_project`. Fails closed if Docker is absent. |
| `patchpilot models` | `[--config, -c <CONFIG>]` | Lists available local models retrieved from the Ollama daemon. |
| `patchpilot chat "<msg>"` | `[--config, -c <CONFIG>]` | Diagnostic endpoint to verify LLM latency and connectivity without running repairs. |
| `patchpilot repair` | `--repo, -r <PATH>`<br>`--task, -t "<TASK>"`<br>`[--test-suite, -s <SUITE>]`<br>`[--test-target <TARGET>]`<br>`[--allow-host-execution]`<br>`[--config, -c <CONFIG>]` | Initiates the bounded self-healing repair pipeline on a target repository. Fast-fails if prerequisites are unmet before invoking model inference. |
| `patchpilot eval` | `[--suite, -s <SUITE>]`<br>`[--allow-host-execution]`<br>`[--config, -c <CONFIG>]` | Executes local benchmark evaluation suites from `evals/cases/manifest.json`. Defaults to Docker sandboxing fail-closed. |
| `patchpilot runs list` | `[--config, -c <CONFIG>]` | Displays recorded historical repair runs with exit statuses, durations, and attempt counts. |
| `patchpilot runs show <ID>` | `[--config, -c <CONFIG>]` | Displays detailed metrics, unified diff, and status for a specific run ID. |

---

## Configuration

PatchPilot can be configured via environment variables or a `.patchpilot.toml` file. Environment variables take precedence over configuration file settings.

| Setting | TOML Section | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `model_name` | `[model] name` | `PATCHPILOT_MODEL_NAME` | `qwen3.5:4b` | Target Ollama model for reasoning & tool calling. |
| `ollama_base_url` | `[model] ollama_base_url` | `PATCHPILOT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server HTTP API endpoint. |
| `request_timeout_seconds` | `[model] request_timeout_seconds` | `PATCHPILOT_REQUEST_TIMEOUT_SECONDS` | `180` | Ollama HTTP request timeout in seconds (5–600). |
| `ollama_think` | `[model] think` | `PATCHPILOT_OLLAMA_THINK` / `PATCHPILOT_THINK` | `false` | Explicit Ollama thinking parameter (`false` disables chain-of-thought for fast tool calls). |
| `max_repair_attempts` | `[agent] max_repair_attempts` | `PATCHPILOT_MAX_REPAIR_ATTEMPTS` | `3` | Maximum self-healing repair iterations (1–10). |
| `max_agent_steps` | `[agent] max_agent_steps` | `PATCHPILOT_MAX_AGENT_STEPS` | `12` | Reasoning step budget per attempt (1–50). |
| `max_tool_calls` | `[agent] max_tool_calls` | `PATCHPILOT_MAX_TOOL_CALLS` | `24` | Total budget of tool calls allowed (1–100). |
| `max_context_characters` | `[agent] max_context_characters` | `PATCHPILOT_MAX_CONTEXT_CHARACTERS` | `50000` | Maximum context window character budget (1,000–200,000). |
| `max_file_bytes` | `[safety] max_file_bytes` | `PATCHPILOT_MAX_FILE_BYTES` | `200000` | Maximum file size readable by agent (1 KB–10 MB). |
| `test_timeout_seconds` | `[safety] test_timeout_seconds` | `PATCHPILOT_TEST_TIMEOUT_SECONDS` | `120` | Test runner timeout in seconds (5–600). |
| `max_command_output_characters` | `[safety] max_command_output_characters` | `PATCHPILOT_MAX_COMMAND_OUTPUT_CHARACTERS` | `20000` | Maximum test output characters captured (500–100,000). |
| `allow_host_execution` | `[safety] allow_host_execution` | `PATCHPILOT_ALLOW_HOST_EXECUTION` | `false` | Unsafe opt-in to execute repository tests on host without Docker. |
| `data_dir` | `[storage] data_dir` | `PATCHPILOT_DATA_DIR` | `.patchpilot-data` | Directory storing runs, workspaces, and logs. |

> **Docker Sandbox Image Note:** The containerized test runner (`TestRunner`) uses `patchpilot-sandbox:latest`, built from `sandbox/Dockerfile`.

See [`.patchpilot.example.toml`](.patchpilot.example.toml) and [`.env.example`](.env.example) for reference configurations.

---

## Storage & Artifact Layout

PatchPilot stores all operational data under `.patchpilot-data/` (configurable via `data_dir`):

```text
.patchpilot-data/
├── runs/
│   ├── <run_id>.json       # Machine-readable RunReport (status, metrics, diff)
│   └── <run_id>.patch      # Unified diff patch file ready for git apply
├── workspaces/
│   └── <run_id>/           # Ephemeral isolated workspace copies
└── events.jsonl            # Append-only JSONL operational event log
```

---

## Verification & Quality Gate

PatchPilot maintains rigorous code quality standards. Run the local quality suite:

```powershell
.\scripts\check.ps1
```

Or execute the checks individually:

```powershell
# Ruff code formatting check
.\.venv\Scripts\python.exe -m ruff format --check src tests

# Ruff lint check
.\.venv\Scripts\python.exe -m ruff check .

# Static type checking
.\.venv\Scripts\python.exe -m mypy src tests

# Unit and security test suite
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

> **Note on Symlink Tests on Windows:**
> Filesystem symlink creation checks in `tests/security/test_symlink_escape.py` require Windows Developer Mode or administrative privileges to create native symlinks on Windows. They execute automatically on POSIX environments or when Windows Developer Mode is enabled, and gracefully skip otherwise.

---

## Limitations & Design Boundaries

- **Single-Agent Architecture:** PatchPilot uses a single orchestrator with bounded sequential tool-calling. It does not spawn unmonitored multi-agent swarms.
- **Python-Focused Default Sandbox:** The bundled sandbox container image is preconfigured for Python (`pytest`, `unittest`). Multi-language sandboxes can be configured via custom Docker images.
- **Local Model Reasoning:** Small quantized models (e.g., `4b` parameters) excel at targeted, localized bugs with clear test diagnostics, but may require multiple iterations or human refinement for architectural refactors.

---

## Documentation Links

- [Architectural Specification](docs/ARCHITECTURE.md)
- [Safety Model & Defenses](docs/SAFETY_MODEL.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [User Guide & Troubleshooting](docs/USER_GUIDE.md)
- [Evaluation Harness](docs/EVALUATION.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Reporting](SECURITY.md)

---

## License

PatchPilot is open-source software licensed under the [MIT License](LICENSE).
