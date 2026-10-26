"""Regression analysis comparing baseline test execution with post-repair results."""

from patchpilot.schemas import TestSuiteResult, VerificationSummary


def analyze_regressions(
    baseline: TestSuiteResult | None,
    final_result: TestSuiteResult | None,
) -> VerificationSummary:
    """Compare baseline vs final test runs to detect regressions and fixed tests."""
    if not final_result:
        return VerificationSummary(
            baseline_result=baseline,
            final_result=None,
            is_regression_free=False,
            verified=False,
        )

    if not baseline or not baseline.test_cases:
        # If no baseline test cases were recorded (e.g. compileall or single check)
        is_pass = final_result.passed
        return VerificationSummary(
            baseline_result=baseline,
            final_result=final_result,
            is_regression_free=is_pass,
            verified=is_pass,
        )

    def norm(tid: str) -> str:
        return tid.split("::")[-1].strip()

    baseline_passes = {norm(tc.test_id) for tc in baseline.test_cases if tc.passed}
    baseline_fails = {norm(tc.test_id) for tc in baseline.test_cases if not tc.passed}

    final_passes = {norm(tc.test_id) for tc in final_result.test_cases if tc.passed}
    final_fails = {norm(tc.test_id) for tc in final_result.test_cases if not tc.passed}

    # Regression: previously passed, now failed
    regression_tests = sorted(baseline_passes & final_fails)

    # Fixed: previously failed, now passed
    fixed_tests = sorted(baseline_fails & final_passes)

    # Persisting: previously failed, still failed
    persisting_failures = sorted(baseline_fails & final_fails)

    is_regression_free = len(regression_tests) == 0
    # Verified if regression-free, final run passed, and either failing baseline tests were resolved or all pass
    baseline_had_failures = not baseline.passed or len(baseline_fails) > 0
    verified = (
        is_regression_free
        and final_result.passed
        and (len(fixed_tests) > 0 or not baseline_had_failures)
    )

    return VerificationSummary(
        baseline_result=baseline,
        final_result=final_result,
        fixed_tests=fixed_tests,
        persisting_failures=persisting_failures,
        regression_tests=regression_tests,
        is_regression_free=is_regression_free,
        verified=verified,
    )
