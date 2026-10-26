# Security Policy

## Reporting Security Issues

Ruru Labs takes the security of PatchPilot seriously. If you discover a security vulnerability or potential threat boundary violation, please report it privately:

- **Email:** `security@rurulabs.local`
- **Response window:** Initial response within 48 hours.

Please do not open public GitHub issues for undisclosed vulnerabilities.

## Core Security Model & Guarantees

PatchPilot is architected with strict defensive safety boundaries:

1. **Original Repository Immutability:**
   PatchPilot will **never** directly edit, patch, or alter files in the target source repository. All inspection, editing, and execution occur exclusively within isolated, disposable workspaces beneath `.patchpilot-data/`.
2. **Path Traversal & Symlink Escapes:**
   Centralized path validation resolves absolute canonical paths and rejects any path escaping the authorized disposable workspace boundary or targeting system root.
3. **Restricted Command Execution:**
   The AI model cannot execute arbitrary shell commands. It may only invoke explicitly registered test suites (`pytest`, `unittest`, `compileall`) via predefined argument structures.
4. **Untrusted Code Sandboxing:**
   Test suites for untrusted repository code are run inside containerized Docker sandboxes with dropped capabilities, read-only root filesystems, memory/CPU limits, and disabled networking.
5. **No Secret Ingestion:**
   Files such as `.env`, private keys (`*.pem`, `*.key`), and VCS credentials are automatically excluded from workspace copy manifests and redacted from all logs and run reports.
6. **Local-First & Offline:**
   PatchPilot operates against a local Ollama instance (`http://localhost:11434`). It does not send code, prompts, or telemetry to external cloud endpoints.
