# Changelog

All notable changes to PatchPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Multi-Language Test Suite Adapters (Phase 2):**
  - Added support for JavaScript/TypeScript testing via `jest`.
  - Added support for Go testing via `go_test` (`go test -v`).
  - Added support for Rust testing via `cargo_test` (`cargo test`).
  - Added host and Docker sandbox execution command builders with path containment.
  - Added comprehensive regex parsers for Jest checkmark/suite outcomes, Go PASS/FAIL/SKIP indicators, and Cargo test results.
  - Updated sandbox Dockerfile with pinned multi-language runtime dependencies (`nodejs`, `npm`, `golang-go`, `cargo`, `rustc`).

## [0.1.0] - 2026-10-25

### Added
- **Core Architecture:**
  - Local-first agent architecture supporting Ollama models (defaulting to `qwen3.5:9b`).
  - Structured orchestration loop with explicit tool registry and strict step/token limits.
  - Safe disposable workspace manager with cryptographic file manifest hashing and original repository immutability verification.
- **Safety Engine:**
  - Centralized path containment validator rejecting traversal, escaping symlinks, and absolute foreign paths.
  - Strict command policy enforcing predefined test suites (`pytest`, `unittest`, `compileall`).
  - Sensitive data redaction for environment variables, keys, and tokens.
- **Verification Engine:**
  - Baseline execution capture prior to code modifications.
  - Regression detector comparing passing vs. failing test sets.
  - Unified diff generator for human review.
  - Docker sandbox test runner for untrusted repository code.
- **CLI & Developer Tools:**
  - Rich CLI with `doctor`, `models`, `chat`, `repair`, `runs list`, `runs show`, and `eval` commands.
  - Append-only JSONL run store and persistent JSON report generation.
  - Automated smoke evaluation harness with bundled calculator bug benchmark.
  - PowerShell automation scripts (`setup.ps1`, `check.ps1`, `run_demo.ps1`).
