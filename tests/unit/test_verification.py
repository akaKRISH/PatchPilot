"""Unit tests for verification and regression analysis."""

from patchpilot.schemas import TestCaseResult, TestSuiteName, TestSuiteResult
from patchpilot.verification.regression import analyze_regressions
from patchpilot.verification.results import parse_test_output


def test_analyze_regressions_success() -> None:
    baseline = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=False),
            TestCaseResult(test_id="test_sub", passed=True),
        ],
    )

    final = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=0,
        passed=True,
        summary="2 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=True),
            TestCaseResult(test_id="test_sub", passed=True),
        ],
    )

    summary = analyze_regressions(baseline, final)
    assert summary.verified is True
    assert summary.is_regression_free is True
    assert "test_add" in summary.fixed_tests
    assert len(summary.regression_tests) == 0


def test_analyze_regressions_detects_regression() -> None:
    baseline = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=False),
            TestCaseResult(test_id="test_sub", passed=True),
        ],
    )

    # test_add now passes, but test_sub was broken
    final = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=True),
            TestCaseResult(test_id="test_sub", passed=False),
        ],
    )

    summary = analyze_regressions(baseline, final)
    assert summary.verified is False
    assert summary.is_regression_free is False
    assert "test_sub" in summary.regression_tests
    assert "test_add" in summary.fixed_tests


def test_parse_pytest_output() -> None:
    raw = """
tests/test_calculator.py::test_add PASSED
tests/test_calculator.py::test_sub FAILED
"""
    result = parse_test_output(TestSuiteName.PYTEST, exit_code=1, output=raw)
    assert result.passed is False
    assert result.tests_run == 2
    assert result.tests_passed == 1
    assert result.tests_failed == 1


def test_parse_jest_output() -> None:
    raw = """
PASS tests/math.test.js
  Math Suite
    ✓ adds numbers correctly (2 ms)
    ✕ subtracts numbers correctly (1 ms)

Test Suites: 1 failed, 1 total
Tests:       1 failed, 1 passed, 2 total
Snapshots:   0 total
Time:        0.45 s
"""
    result = parse_test_output(TestSuiteName.JEST, exit_code=1, output=raw)
    assert result.passed is False
    assert result.tests_run == 2
    assert result.tests_passed == 1
    assert result.tests_failed == 1
    assert len(result.test_cases) == 2
    assert result.test_cases[0].test_id == "adds numbers correctly"
    assert result.test_cases[0].passed is True
    assert result.test_cases[1].test_id == "subtracts numbers correctly"
    assert result.test_cases[1].passed is False


def test_parse_jest_summary_fallback() -> None:
    raw = """
FAIL tests/index.test.js
Tests: 2 failed, 3 passed, 5 total
"""
    result = parse_test_output(TestSuiteName.JEST, exit_code=1, output=raw)
    assert result.passed is False
    assert result.tests_passed == 3
    assert result.tests_failed == 2
    assert result.tests_run == 5


def test_parse_go_test_output() -> None:
    raw = """
=== RUN   TestAdd
--- PASS: TestAdd (0.00s)
=== RUN   TestDivide
--- FAIL: TestDivide (0.00s)
=== RUN   TestSkip
--- SKIP: TestSkip (0.00s)
FAIL
exit status 1
FAIL	example.com/math	0.012s
"""
    result = parse_test_output(TestSuiteName.GO_TEST, exit_code=1, output=raw)
    assert result.passed is False
    assert result.tests_run == 2
    assert result.tests_passed == 1
    assert result.tests_failed == 1
    assert len(result.test_cases) == 2
    assert result.test_cases[0].test_id == "TestAdd"
    assert result.test_cases[0].passed is True
    assert result.test_cases[1].test_id == "TestDivide"
    assert result.test_cases[1].passed is False


def test_parse_cargo_test_output() -> None:
    raw = """
running 3 tests
test tests::test_add ... ok
test tests::test_sub ... FAILED
test tests::test_ignored ... ignored

failures:

failures:
    tests::test_sub

test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""
    result = parse_test_output(TestSuiteName.CARGO_TEST, exit_code=1, output=raw)
    assert result.passed is False
    assert result.tests_run == 2
    assert result.tests_passed == 1
    assert result.tests_failed == 1
    assert len(result.test_cases) == 2
    assert result.test_cases[0].test_id == "tests::test_add"
    assert result.test_cases[0].passed is True
    assert result.test_cases[1].test_id == "tests::test_sub"
    assert result.test_cases[1].passed is False
