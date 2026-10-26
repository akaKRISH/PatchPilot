"""Parsers for test suite executions into structured TestSuiteResult models."""

import re

from patchpilot.safety.redaction import redact_sensitive_text
from patchpilot.schemas import TestCaseResult, TestSuiteName, TestSuiteResult

PYTEST_LINE_PATTERN = re.compile(
    r"^([\w\/\.\:\-\\]+)\s+(PASSED|FAILED|ERROR|SKIPPED)", re.MULTILINE
)
UNITTEST_LINE_PATTERN = re.compile(
    r"^([\w\.\s\(\)]+)\s+\.\.\.\s+(ok|FAIL|ERROR|skipped)", re.MULTILINE
)
JEST_TEST_LINE_PATTERN = re.compile(r"^\s*([✓√✕×])\s+(.+?)(?:\s+\(\d+\s*m?s\))?$", re.MULTILINE)
JEST_SUMMARY_PATTERN = re.compile(
    r"Tests:\s+(?:(\d+)\s+failed,?\s*)?(?:(\d+)\s+passed,?\s*)?(?:(\d+)\s+total)?",
    re.MULTILINE,
)
GO_TEST_LINE_PATTERN = re.compile(
    r"^--- (PASS|FAIL|SKIP):\s+([\w\/\.\:\-]+)(?:\s+\([^\)]+\))?", re.MULTILINE
)
CARGO_TEST_LINE_PATTERN = re.compile(
    r"^test\s+([\w\:\-\.]+)\s+\.\.\.\s+(ok|FAILED|ignored)", re.MULTILINE
)
CARGO_SUMMARY_PATTERN = re.compile(
    r"test result:\s+(?:FAILED|ok)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;",
    re.MULTILINE,
)


def parse_test_output(
    suite: TestSuiteName,
    exit_code: int,
    output: str,
    duration_seconds: float = 0.0,
    max_output_chars: int = 20000,
) -> TestSuiteResult:
    """Parse raw output of a test runner into a structured TestSuiteResult."""
    sanitized_output = redact_sensitive_text(output)
    if len(sanitized_output) > max_output_chars:
        # Keep head and tail of output with truncation indicator
        half = max_output_chars // 2
        sanitized_output = (
            sanitized_output[:half]
            + f"\n\n... [OUTPUT TRUNCATED: EXCEEDED {max_output_chars} CHARACTERS] ...\n\n"
            + sanitized_output[-half:]
        )

    test_cases: list[TestCaseResult] = []
    tests_passed = 0
    tests_failed = 0

    if suite == TestSuiteName.PYTEST:
        for match in PYTEST_LINE_PATTERN.finditer(sanitized_output):
            test_id, outcome = match.groups()
            test_id = test_id.strip()
            passed = outcome == "PASSED"
            if passed:
                tests_passed += 1
            elif outcome in ("FAILED", "ERROR"):
                tests_failed += 1
            test_cases.append(TestCaseResult(test_id=test_id, passed=passed))

    elif suite == TestSuiteName.UNITTEST:
        for match in UNITTEST_LINE_PATTERN.finditer(sanitized_output):
            test_id, outcome = match.groups()
            test_id = test_id.strip()
            passed = outcome == "ok"
            if passed:
                tests_passed += 1
            elif outcome in ("FAIL", "ERROR"):
                tests_failed += 1
            test_cases.append(TestCaseResult(test_id=test_id, passed=passed))

    elif suite == TestSuiteName.COMPILEALL:
        # compileall exits 0 on success, 1 on syntax error
        if exit_code == 0:
            tests_passed = 1
            test_cases.append(TestCaseResult(test_id="compileall_check", passed=True))
        else:
            tests_failed = 1
            test_cases.append(
                TestCaseResult(
                    test_id="compileall_check",
                    passed=False,
                    failure_message="Syntax or compilation error",
                )
            )

    elif suite == TestSuiteName.JEST:
        for match in JEST_TEST_LINE_PATTERN.finditer(sanitized_output):
            symbol, test_name = match.groups()
            test_id = test_name.strip()
            passed = symbol in ("✓", "√")
            if passed:
                tests_passed += 1
            else:
                tests_failed += 1
            test_cases.append(TestCaseResult(test_id=test_id, passed=passed))

        if len(test_cases) == 0:
            m = JEST_SUMMARY_PATTERN.search(sanitized_output)
            if m:
                failed_cnt = int(m.group(1)) if m.group(1) else 0
                passed_cnt = int(m.group(2)) if m.group(2) else 0
                tests_failed += failed_cnt
                tests_passed += passed_cnt

    elif suite == TestSuiteName.GO_TEST:
        for match in GO_TEST_LINE_PATTERN.finditer(sanitized_output):
            status, test_name = match.groups()
            test_id = test_name.strip()
            if status == "PASS":
                tests_passed += 1
                test_cases.append(TestCaseResult(test_id=test_id, passed=True))
            elif status == "FAIL":
                tests_failed += 1
                test_cases.append(TestCaseResult(test_id=test_id, passed=False))

    elif suite == TestSuiteName.CARGO_TEST:
        for match in CARGO_TEST_LINE_PATTERN.finditer(sanitized_output):
            test_name, outcome = match.groups()
            test_id = test_name.strip()
            if outcome == "ok":
                tests_passed += 1
                test_cases.append(TestCaseResult(test_id=test_id, passed=True))
            elif outcome == "FAILED":
                tests_failed += 1
                test_cases.append(TestCaseResult(test_id=test_id, passed=False))

        if len(test_cases) == 0:
            m = CARGO_SUMMARY_PATTERN.search(sanitized_output)
            if m:
                tests_passed += int(m.group(1))
                tests_failed += int(m.group(2))

    tests_run = tests_passed + tests_failed
    if suite == TestSuiteName.PYTEST and tests_run == 0:
        pass_m = re.search(r"(\d+)\s+passed", sanitized_output)
        fail_m = re.search(r"(\d+)\s+failed", sanitized_output)
        if pass_m:
            tests_passed = int(pass_m.group(1))
        if fail_m:
            tests_failed = int(fail_m.group(1))
        tests_run = tests_passed + tests_failed

    if exit_code != 0 and tests_failed == 0 and len(test_cases) == 0:
        tests_failed = 1
        tests_run += 1
        test_cases.append(
            TestCaseResult(
                test_id=f"{suite.value}_execution",
                passed=False,
                failure_message=f"Process exited with non-zero exit code {exit_code}",
            )
        )

    passed = exit_code == 0

    summary = (
        f"{suite.value}: {'PASSED' if passed else 'FAILED'} "
        f"({tests_passed} passed, {tests_failed} failed, total {tests_run})"
    )

    return TestSuiteResult(
        suite_name=suite,
        exit_code=exit_code,
        passed=passed,
        summary=summary,
        tests_run=tests_run,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        test_cases=test_cases,
        raw_output=sanitized_output,
        duration_seconds=duration_seconds,
    )
