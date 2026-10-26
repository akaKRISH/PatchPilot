# PatchPilot Docker Sandbox

The Docker sandbox provides containerized isolation for executing untrusted repository test suites.

## Python-Only MVP Image

The initial MVP sandbox image is purposefully Python-only:
- Based on `python:3.13-slim`.
- Installs pinned `pytest==8.3.4` via standard pip (with TLS verification).
- Omits external Debian `apt-get` package downloads (such as Node.js, Go, Rust) to keep the build small, fast, reproducible, and immune to package mirror network failures.

### Test Suite Compatibility
- **Supported in Sandbox**:
  - `pytest`
  - `unittest`
  - `compileall`
- **Unsupported in Sandbox**:
  - `jest` (JavaScript/TypeScript)
  - `go_test` (Go)
  - `cargo_test` (Rust)

Attempting to run `jest`, `go_test`, or `cargo_test` inside the sandbox raises a clear `CommandPolicyError`. These multi-language suites are preserved for isolated host execution (via `--allow-host-execution` when explicitly allowed) and will be supported in containerized sandboxes via future dedicated images.

## Building the Image

Ensure Docker Desktop (or the Docker daemon) is running, then build the image:

```powershell
docker build -t patchpilot-sandbox:latest .\sandbox\
```

## Runtime Security Constraints

Containers are executed with strict isolation flags (`shell=False`):
- `--network none`: Disables all inbound and outbound network connectivity.
- `--read-only`: Enforces a read-only root container filesystem.
- `--tmpfs /tmp:rw,size=64m`: Bounded writable in-memory temporary directory.
- Disposable Mount: `-v <disposable_workspace>:/workspace:rw` strictly targeting the temporary isolated copy.
- Working Directory: `-w /workspace`.
- Unprivileged User: `sandboxuser` (UID 10001).
- Execution timeout and bounded output capture to prevent denial-of-service or memory exhaustion.
