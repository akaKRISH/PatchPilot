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
- **[Ollama](https://ollama.com/)** running locally:
  ```powershell
  ollama pull qwen3.5:4b
  ```
- **[Docker Desktop](https://www.docker.com/)** (recommended for sandboxed test execution).

### 1. Installation & Environment Setup

You can use the automated PowerShell setup script on Windows:

```powershell
.\scripts\setup.ps1
```

Or perform manual setup:

```powershell
git clone https://github.com/akaKRISH/PatchPilot.git
Set-Location PatchPilot

# Detect Python 3.11, 3.12, or 3.13
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

*(On Linux / macOS, substitute `.venv/bin/python` and `.venv/bin/pip`)*

### 2. Initialize Configuration & Build Docker Sandbox Image

Initialize your local `.patchpilot.toml` configuration with tested defaults (`qwen3.5:4b`, Ollama thinking disabled):

```powershell
.\.venv\Scripts\python.exe -m patchpilot init
```

Build the lightweight, self-contained Python test sandbox:

```powershell
docker build -t patchpilot-sandbox:latest .\sandbox\
```

### 3. Verify System Health

Run the diagnostic doctor to verify Ollama connectivity, Docker sandbox availability, model presence, and filesystem readiness:

```powershell
.\.venv\Scripts\python.exe -m patchpilot doctor
```

If any prerequisite is missing, `doctor` returns a `NOT READY` status with exact remediation commands.

### 4. Run the Safe Demo

Run the safe, end-to-end demonstration repair on the bundled buggy calculator project:

```powershell
.\.venv\Scripts\python.exe -m patchpilot demo
```

---

## Repair Walkthrough

PatchPilot includes a reproducible bug test case in [`examples/buggy_python_project`](examples/buggy_python_project). The project contains an off-by-one bug in a basic calculator utility where `add(a, b)` incorrectly returns `a + b + 1`.

### Run the Repair Agent

```powershell
.\.venv\Scripts\python.exe -m patchpilot repair `
  --repo .\examples\buggy_python_project `
  --task "Fix the bug in the calculator's add function. Preserve the public API." `
  --test-suite pytest
```

### Execution Lifecycle

1. **Preflight & Invariance Check:** PatchPilot verifies system health and records the initial SHA-256 hash of all source files.
2. **Workspace Isolation:** A disposable copy is provisioned at `.patchpilot-data/workspaces/<run_id>/`.
3. **Baseline Evaluation:** The existing test suite runs inside the Docker sandbox, capturing the failing test assertion.
4. **Agent Inspection & Tool Calling:** The model inspects the repository layout, locates `calculator.py`, and inspects the implementation.
5. **Targeted Edit:** The model applies a minimal surgical edit to `calculator.py` inside the temporary workspace.
6. **Sandboxed Verification:** The test runner re-executes `pytest` in Docker. Tests pass with zero regressions.
7. **Integrity Re-evaluation:** The original source directory is verified to have zero file changes.
8. **Artifact Generation:** A unified diff and structured JSON report are written to `.patchpilot-data/runs/<run_id>/`.

Review the resulting patch:

```powershell
.\.venv\Scripts\python.exe -m patchpilot runs list
.\.venv\Scripts\python.exe -m patchpilot runs show <RUN_ID>
```

Apply the verified patch to your repository:

```powershell
git apply .patchpilot-data\runs\<RUN_ID>\patch.diff
```

---

## Safety Model & Workspace Isolation

PatchPilot enforces security through deterministic software boundaries rather than relying on LLM instruction-following:

| Defense Layer | Implementation Details |
| :--- | :--- |
| **Path Traversal Containment** | All paths resolve against the workspace root. Traversal patterns (`..`), null bytes, and escaping symlinks trigger immediate validation errors (`PathTraversalError`, `SymlinkEscapeError`). |
| **Secret Redaction** | Sensitive files (`.env`, `*.pem`, `*.key`, `id_rsa`, `.git`, `.venv`) are excluded during workspace cloning. Terminal outputs and stored run logs pass through regex redaction. |
| **Command Whitelist** | The model has no terminal access. `run_tests` only accepts pre-approved test suites (`pytest`, `unittest`, `compileall`) with immutable argument templates. |
| **Docker Sandbox** | Untrusted test suites run inside isolated containers with `--network none`, `--read-only`, unprivileged user privileges, and strict execution timeouts. |
| **Execution Budgets** | Hard boundaries prevent runaway execution: maximum 3 repair attempts, 12 agent reasoning steps per attempt, and bounded tool calls. |

For complete threat vectors and mitigations, refer to [docs/SAFETY_MODEL.md](docs/SAFETY_MODEL.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

---

## CLI Reference

| Command | Purpose |
| :--- | :--- |
| `patchpilot init` | Generates a valid `.patchpilot.toml` configuration with tested defaults (`qwen3.5:4b`, Ollama thinking disabled). |
| `patchpilot doctor` | Inspects environment health: Ollama, Docker sandbox, installed models, and data paths. Returns exit code 1 if dependencies are missing. |
| `patchpilot demo` | Runs the safe, sandboxed end-to-end repair demonstration using the bundled calculator project. |
| `patchpilot models` | Lists available local models retrieved from the Ollama daemon. |
| `patchpilot chat "<msg>"` | Diagnostic endpoint to verify LLM latency and connectivity without running repairs. |
| `patchpilot repair` | Initiates the bounded self-healing repair pipeline on a target repository. Fast-fails if prerequisites are unmet. |
| `patchpilot runs list` | Displays recorded historical repair runs with exit statuses and durations. |
| `patchpilot runs show <ID>` | Displays detailed metrics, applied patches, and event logs for a specific run. |
| `patchpilot eval --suite smoke` | Executes local benchmark evaluation suites in Docker sandbox (or host with `--allow-host-execution`). |

---

## Configuration

PatchPilot can be configured via environment variables or a `.patchpilot.toml` file. Environment variables take precedence over configuration files.

| Setting | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `ollama_host` | `PATCHPILOT_OLLAMA_HOST` | `http://localhost:11434` | Ollama service endpoint. |
| `model` | `PATCHPILOT_MODEL` | `qwen3.5:4b` | Tested default model for tool calling. |
| `ollama_think` | `PATCHPILOT_OLLAMA_THINK` | `false` | Disables verbose chain-of-thought for fast tool calls. |
| `max_repair_attempts` | `PATCHPILOT_MAX_REPAIR_ATTEMPTS` | `3` | Maximum self-healing attempts. |
| `max_reasoning_steps`| `PATCHPILOT_MAX_REASONING_STEPS` | `12` | Reasoning step budget per attempt. |
| `container_timeout` | `PATCHPILOT_CONTAINER_TIMEOUT_SECONDS` | `120` | Maximum containerized test run duration. |
| `sandbox_image` | `PATCHPILOT_SANDBOX_IMAGE` | `patchpilot-sandbox:latest` | Docker image tag for sandboxed tests. |

See [`.patchpilot.example.toml`](.patchpilot.example.toml) and [`.env.example`](.env.example) for reference configurations.

---

## Repository Structure

```text
patchpilot/
├── src/patchpilot/
│   ├── agent/           # Orchestrator, context builder, prompt templates, bounded repair loop
│   ├── tools/           # Validated tool registry (inspect, search, read, edit, run_tests)
│   ├── safety/          # Path containment, command policies, secret redaction, resource budgets
│   ├── workspace/       # Isolated workspace manager, SHA-256 manifests, unified diff generator
│   ├── verification/    # Baseline test runner, Docker execution, regression analysis engine
│   ├── storage/         # RunStore (JSON reports and append-only JSONL event logs)
│   ├── evaluation/      # Local benchmark evaluation harness
│   ├── cli.py           # Typer-powered CLI interface
│   ├── config.py        # Pydantic settings and environment loader
│   ├── ollama_client.py # Robust local Ollama HTTP client with tool extraction
│   ├── schemas.py       # Pydantic data models and tool contracts
│   └── errors.py        # Typed exception hierarchy
├── tests/
│   ├── unit/            # Isolated unit tests with mocked providers
│   ├── security/        # Path traversal, symlink boundary, and immutability security tests
│   └── integration/     # Optional live Ollama & Docker integration tests
├── examples/            # Bundled test repositories for reproduction and verification
├── evals/               # Deterministic evaluation cases and manifests
├── sandbox/             # Dockerfile and specification for the unprivileged Python test sandbox
├── scripts/             # Developer verification and quality gate automation scripts
└── docs/                # Architecture, safety specifications, and developer guides
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

> **Note on Test Results:**
> The standard offline test suite comprises **75 passed tests and 1 skipped test**. The single skipped test (`tests/security/test_symlink_escape.py::test_workspace_rejects_external_symlink`) is an environment-dependent check that requires Windows Developer Mode or administrative privileges to create native filesystem symlinks. It automatically executes on POSIX environments and Windows systems with symlink privileges enabled.

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
