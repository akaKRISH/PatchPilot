"""Capture baseline test suite execution before code edits."""

from pathlib import Path

from patchpilot.schemas import TestSuiteName, TestSuiteResult
from patchpilot.verification.runner import TestRunner


def run_baseline_tests(
    runner: TestRunner,
    workspace_dir: Path,
    suite: TestSuiteName,
    target: str | None = None,
) -> TestSuiteResult:
    """Execute baseline tests and record pre-repair test outcomes."""
    return runner.run_tests(workspace_dir=workspace_dir, suite=suite, target=target)
