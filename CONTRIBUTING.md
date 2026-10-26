# Contributing to PatchPilot

Thank you for your interest in contributing to PatchPilot!

## Development Setup

1. **Clone and enter the workspace:**
   ```powershell
   cd patchpilot
   ```

2. **Create and activate the virtual environment:**
   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies in editable mode:**
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

4. **Verify environment health:**
   ```powershell
   python -m patchpilot doctor
   ```

## Development Standards

- **Formatting & Linting:** Run `ruff check .` and `ruff format --check .`.
- **Type Checking:** Run `mypy src tests`.
- **Tests:** Run `pytest tests/unit tests/security`.
- **Safety First:** Never weaken path validation or command policy checks to make a test pass.
- **Original Repository Protection:** Every feature must preserve original repositories as strictly immutable.

## Pull Request Guidelines

1. Ensure all unit and security tests pass.
2. Provide test coverage for new tools, validation rules, or edge cases.
3. Update documentation and architectural diagrams when modifying boundaries or tool contracts.
