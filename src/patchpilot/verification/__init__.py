"""Verification and regression testing module for PatchPilot."""

from patchpilot.verification.baseline import run_baseline_tests
from patchpilot.verification.regression import analyze_regressions
from patchpilot.verification.results import parse_test_output
from patchpilot.verification.runner import TestRunner

__all__ = [
    "TestRunner",
    "analyze_regressions",
    "parse_test_output",
    "run_baseline_tests",
]
