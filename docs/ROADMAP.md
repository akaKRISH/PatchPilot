# PatchPilot — Product Roadmap

This roadmap outlines planned future enhancements for PatchPilot beyond the MVP.

## Phase 1: MVP Core (Current Release — v0.1.0)
- [x] Local Ollama integration with `qwen3.5:4b` (think=False).
- [x] Immutable source repository isolation with SHA-256 manifests.
- [x] Centralized path containment and command policy enforcement.
- [x] Standard tool registry: `inspect_repository`, `search_code`, `read_file`, `edit_file`, `run_tests`.
- [x] Regression detection against baseline test suites.
- [x] Docker sandbox test runner with network isolation.
- [x] Append-only run store and unified diff generation.
- [x] CLI commands (`doctor`, `models`, `chat`, `repair`, `runs`, `eval`).

## Phase 2: Enhanced Language & Framework Support
- [x] Multi-language test suite adapters (Node.js/Jest, Go/testing, Rust/cargo test).
- [ ] Tree-sitter AST-guided semantic code edits.
- [ ] Multi-file co-dependent repair transactions.

## Phase 3: Provider Abstraction & Advanced Isolation
- [ ] Pluggable model providers (llama.cpp server, vLLM, local OpenAI-compatible endpoints).
- [ ] MicroVM isolation backends (Firecracker / gVisor) for even stronger runtime guarantees.
- [ ] Interactive patch review and staging CLI workflow (`patchpilot patch apply`).
