# PatchPilot 🛠️✈️

> **Local-First, Self-Healing AI Coding Agent Powered by Ollama**
> *Developed by Ruru Labs*

PatchPilot investigates codebases, diagnoses bugs, proposes minimal targeted repairs, tests them in isolated disposable working copies, detects regressions against baselines, and delivers mathematically verified patches—all while guaranteeing that your original source repository remains completely untouched.

```mermaid
flowchart TD
    User([User Request / Task]) --> CLI[PatchPilot CLI]
    CLI --> Doctor{Preflight Checks}
    Doctor -->|Ready| Manager[Workspace Manager]
    Manager --> Snapshot[Compute SHA-256 Manifest of Source]
    Snapshot --> Disposable[Create Disposable Copy in .patchpilot-data]
    Disposable --> Baseline[Run Baseline Test Suite]
    Baseline --> Agent[Single-Agent Repair Loop]
    subgraph Self-Healing Loop [Bounded Self-Healing Loop (Max 3 Attempts)]
        Agent --> Model[Ollama: qwen3.5:4b]
        Model -->|Structured Tool Call| Registry[Tool Registry]
        Registry -->|inspect_repo / search_code / read_file| SafeFS[Safe Filesystem Layer]
        Registry -->|edit_file| Disposable
        Registry -->|run_tests| Runner[Docker Sandbox / Predefined Suite]
        Runner --> Verifier[Verification & Regression Engine]
        Verifier -->|Failures / Regressions| Agent
    end
    Verifier -->|Passed & Verified| Diff[Generate Unified Diff]
    Diff --> Integrity[Verify Source Hash Invariance]
    Integrity --> Report[Save RunReport & Patch Artifact]
    Report --> Summary([User Reviewable Output])
```

---

## Key Features

- 🔒 **Original Repository Immutability:** Your target repository is treated as strictly read-only. Edits occur solely in disposable, collision-resistant working directories. At the end of every run, SHA-256 manifests are reverified to guarantee no mutations leaked.
- 🏠 **100% Local-First & Cost-Free:** Powered directly by local Ollama (`qwen3.5:4b` by default with thinking disabled for fast native tool-calling). No external API keys, no paid tokens, no telemetry, and zero data leakage.
- 🛡️ **Defensive Tool Registry:** The LLM cannot execute arbitrary shell commands. It operates strictly through validated tools (`inspect_repository`, `search_code`, `read_file`, `edit_file`, `run_tests`).
- 🐳 **Docker Sandboxed Test Execution:** Tests for untrusted repository code run inside constrained Docker containers with network disabled, read-only root filesystems, dropped capabilities, and strict timeout bounds.
- 🔁 **True Self-Healing Repair Loop:** If tests fail or regressions appear against the baseline, PatchPilot feeds structured failure diagnostics back into the model for bounded retries (up to 3 attempts by default).
- 📊 **Auditable Artifacts & Run Store:** Generates standard unified diffs, structured JSON run reports, and append-only JSONL event logs.

---

## Architecture & Safety Model

PatchPilot's design separates the untrusted intelligence (the LLM) from privileged system operations:

1. **Path Containment:** Absolute paths outside the workspace, parent-directory traversals (`..`), and escaping symlinks are rejected by the centralized safety validator before any filesystem operation executes.
2. **Secret Redaction & Exclusion:** Secret-bearing files (`.env`, `*.pem`, `*.key`, Git credentials, and `node_modules`/`.venv` directories) are automatically excluded during workspace creation and redacted from logs.
3. **Predefined Command Policy:** Only vetted test suites (`pytest`, `unittest`, `compileall`) can be triggered with fixed parameter templates.
4. **Baseline & Regression Analysis:** Baseline test state is recorded prior to any code modifications. If a patch fixes the target test but breaks previously passing tests, it is flagged as a regression and rejected.

---

## Installation & Setup (Windows / PowerShell)

### Prerequisites

- **Python 3.11 – 3.13**
- **Ollama** installed with model `qwen3.5:4b`:
  ```powershell
  ollama pull qwen3.5:4b
  ```
- **Docker Desktop** (optional, recommended for sandboxed test execution).

### Step-by-Step Setup

1. **Clone or enter the PatchPilot directory:**
   ```powershell
   cd C:\Users\2k25c\PROJECTS\patchpilot
   ```

2. **Create the local virtual environment:**
   ```powershell
   py -3.13 -m venv .venv
   ```

3. **Install dependencies in editable mode:**
   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

4. **Verify environment health:**
   ```powershell
   .\.venv\Scripts\python.exe -m patchpilot doctor
   ```

---

## CLI Usage

PatchPilot provides an intuitive command-line interface:

### 1. Doctor (System & Dependency Check)
```powershell
.\.venv\Scripts\python.exe -m patchpilot doctor
```
Checks Python version, Ollama connectivity, installed models, Docker sandbox status, and storage directories.

### 2. Models (List Local Ollama Models)
```powershell
.\.venv\Scripts\python.exe -m patchpilot models
```

### 3. Diagnostic Chat
```powershell
.\.venv\Scripts\python.exe -m patchpilot chat "Reply with PATCHPILOT_OK"
```

### 4. Self-Healing Repair
```powershell
.\.venv\Scripts\python.exe -m patchpilot repair `
  --repo .\examples\buggy_python_project `
  --task "Fix the bug in the calculator's add function. Preserve the public API." `
  --test-suite pytest
```

### 5. Inspect Run History
```powershell
.\.venv\Scripts\python.exe -m patchpilot runs list
.\.venv\Scripts\python.exe -m patchpilot runs show <RUN_ID>
```

### 6. Run Evaluation Benchmark
```powershell
.\.venv\Scripts\python.exe -m patchpilot eval --suite smoke
```

---

## Automated Testing

Execute the test suite without requiring live Ollama or Docker:

```powershell
# Unit & Security Tests
.\.venv\Scripts\python.exe -m pytest tests/unit tests/security

# Linting
.\.venv\Scripts\python.exe -m ruff check .

# Type Checking
.\.venv\Scripts\python.exe -m mypy src tests
```

---

## Project Structure

```text
patchpilot/
├── src/patchpilot/
│   ├── agent/           # Orchestrator, context builder, prompt templates, repair loop
│   ├── tools/           # Explicit tool registry, definitions, and implementations
│   ├── safety/          # Path validation, command policy, secret redaction, limits
│   ├── workspace/       # Disposable copy manager, SHA-256 manifests, unified diffs
│   ├── verification/    # Baseline runner, regression analysis, results parser
│   ├── storage/         # RunStore (JSON reports and JSONL events)
│   ├── evaluation/      # Local benchmark runner and reporting
│   ├── cli.py           # Typer CLI application
│   ├── config.py        # Validated configuration settings
│   ├── ollama_client.py # Robust local Ollama HTTP client with tool-calling
│   ├── schemas.py       # Pydantic data contracts
│   └── errors.py        # Exception hierarchy
├── tests/
│   ├── unit/            # Isolated component tests with mocks
│   ├── security/        # Traversal, symlink, and immutability security tests
│   └── integration/     # Optional live Ollama & Docker integration tests
├── examples/            # Bundled buggy Python projects for live verification
├── evals/               # Deterministic benchmark cases and test harnesses
├── sandbox/             # Dockerfile and sandbox execution specs
└── docs/                # Comprehensive architectural and threat documentation
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
