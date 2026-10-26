# PatchPilot — Architectural Specification

## System Overview

PatchPilot is an engineering-grade, self-healing AI coding agent operating locally via Ollama. It addresses software defects by systematically isolating target repositories, executing controlled test suites, and applying bounded repair loops.

```mermaid
graph TD
    subgraph Host Environment
        CLI[Typer CLI / Doctor / Repair]
        Config[PatchPilotConfig]
        Ollama[Ollama Client - Local HTTP]
        Store[RunStore / Event Logs]
    end

    subgraph Disposable Isolation
        Manager[WorkspaceManager]
        SourceRepo[Target Repository - Immutable]
        DisposableCopy[Disposable Workspace Copy]
        Policy[PathPolicy / CommandPolicy]
    end

    subgraph Agentic Repair Core
        Orchestrator[Agent Orchestrator]
        Loop[Bounded Repair Loop]
        Registry[Tool Registry]
        Verifier[Verification & Regression Engine]
    end

    subgraph Sandbox Execution
        Docker[Docker Container - Network None]
        HostRunner[Controlled Host Runner]
    end

    CLI --> Config
    CLI --> Orchestrator
    Orchestrator --> Manager
    Manager --> SourceRepo
    Manager -->|Copy Permitted Files| DisposableCopy
    Orchestrator --> Loop
    Loop --> Ollama
    Loop --> Registry
    Registry --> Policy
    Registry --> DisposableCopy
    Registry --> Verifier
    Verifier --> Docker
    Verifier --> HostRunner
    Manager -->|SHA-256 Check| SourceRepo
    Orchestrator --> Store
```

## Module Boundaries

1. **`patchpilot.config`:**
   Provides typed configuration backed by Pydantic. Loads `.toml` files and environment variables (`PATCHPILOT_*`), with environment variables having precedence.
2. **`patchpilot.ollama_client`:**
   Manages HTTP communication with the local Ollama daemon (`http://localhost:11434`). Handles model queries, structured chat calls, and extracts native tool calls.
3. **`patchpilot.safety`:**
   Centralizes security boundaries:
   - `paths.py`: Path sanitization, boundary checking, symlink inspection, and secret detection.
   - `commands.py`: Sanitizes test arguments and blocks arbitrary command execution.
   - `redaction.py`: Masks passwords, tokens, and private keys.
   - `limits.py`: Enforces agent step and tool invocation budgets.
4. **`patchpilot.workspace`:**
   Guarantees source repository immutability:
   - `manifest.py`: Computes SHA-256 manifests across repositories.
   - `manager.py`: Copies permitted files to disposable workspaces and verifies source hash invariance.
   - `diff.py`: Computes clean unified diffs.
5. **`patchpilot.tools`:**
   Implements registered agent actions: `inspect_repository`, `search_code`, `read_file`, `edit_file`, and `run_tests`.
6. **`patchpilot.verification`:**
   Executes predefined test suites in sandboxes and evaluates regression states against pre-repair baselines.
7. **`patchpilot.agent`:**
   Contains prompt templates, conversation context window builder, and the bounded self-healing repair loop.
8. **`patchpilot.storage`:**
   Maintains append-only JSONL operational logs and structured JSON run reports with unified diff artifacts.
9. **`patchpilot.evaluation`:**
   Provides deterministic benchmark harnesses and performance metric tracking.
