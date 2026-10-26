"""Tool to execute predefined test suites against the disposable workspace."""

from pathlib import Path
from typing import Any

from patchpilot.schemas import TestSuiteName, TestSuiteResult
from patchpilot.verification.runner import TestRunner


def run_tests_tool(
    workspace_dir: Path,
    runner: TestRunner,
    suite: str,
    target: str | None = None,
) -> dict[str, Any]:
    """Execute the specified test suite and return structured outcomes."""
    try:
        suite_enum = TestSuiteName(suite.lower())
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid test suite '{suite}'. Must be one of: {', '.join([s.value for s in TestSuiteName])}",
        }

    try:
        result: TestSuiteResult = runner.run_tests(
            workspace_dir=workspace_dir,
            suite=suite_enum,
            target=target,
        )
        return {
            "success": True,
            "suite": result.suite_name.value,
            "suite_name": result.suite_name.value,
            "passed": result.passed,
            "exit_code": result.exit_code,
            "tests_run": result.tests_run,
            "tests_passed": result.tests_passed,
            "tests_failed": result.tests_failed,
            "summary": result.summary,
            "raw_output": result.raw_output,
            "test_cases": [tc.model_dump() for tc in result.test_cases],
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
