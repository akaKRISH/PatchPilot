"""Benchmark harness executing deterministic smoke evaluation cases."""

import json
import time
from pathlib import Path

from patchpilot.agent.orchestrator import AgentOrchestrator
from patchpilot.config import PatchPilotConfig
from patchpilot.schemas import (
    BenchmarkCase,
    EvalReport,
    EvalResult,
    RepairStatus,
    TaskRequest,
    TestSuiteName,
)


def load_benchmark_manifest(manifest_path: Path | None = None) -> list[BenchmarkCase]:
    """Load benchmark cases from evals/cases/manifest.json."""
    if not manifest_path:
        manifest_path = Path("evals/cases/manifest.json")

    if not manifest_path.is_file():
        # Fallback default benchmark case
        return [
            BenchmarkCase(
                case_id="calculator_bug",
                name="Calculator Add Bug",
                description="Fix subtraction bug inside calculator add function",
                source_dir="examples/buggy_python_project",
                task_description="Fix the bug in the calculator's add function. Preserve the public API and ensure all tests pass.",
                test_suite=TestSuiteName.PYTEST,
                targeted_test="tests/test_calculator.py",
                expected_status=RepairStatus.FIXED,
            )
        ]

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    cases: list[BenchmarkCase] = []
    for item in data.get("cases", []):
        cases.append(BenchmarkCase.model_validate(item))
    return cases


def run_smoke_benchmark(config: PatchPilotConfig) -> EvalReport:
    """Run smoke benchmark suite measuring verification rate, runtime, and attempts."""
    cases = load_benchmark_manifest()
    results: list[EvalResult] = []
    total_start = time.monotonic()

    # Enable host execution for benchmark evaluation if running locally
    cfg_copy = config.model_copy()
    cfg_copy.allow_host_execution = True

    orchestrator = AgentOrchestrator(cfg_copy)

    for case in cases:
        case_start = time.monotonic()
        task = TaskRequest(
            repo_path=case.source_dir,
            task_description=case.task_description,
            test_suite=case.test_suite,
            test_target=case.targeted_test,
        )

        try:
            report = orchestrator.run_repair(task)
            case_duration = time.monotonic() - case_start
            success = report.status == case.expected_status
            tool_calls = sum(len(a.tool_calls) for a in report.attempts)
            has_regression = bool(
                report.verification and len(report.verification.regression_tests) > 0
            )

            results.append(
                EvalResult(
                    case_id=case.case_id,
                    success=success,
                    status=report.status,
                    duration_seconds=case_duration,
                    attempts=report.attempts_made,
                    tool_calls_count=tool_calls,
                    regression_detected=has_regression,
                    error=report.error_message,
                )
            )
        except Exception as e:
            case_duration = time.monotonic() - case_start
            results.append(
                EvalResult(
                    case_id=case.case_id,
                    success=False,
                    status=RepairStatus.UNRESOLVED,
                    duration_seconds=case_duration,
                    attempts=0,
                    tool_calls_count=0,
                    regression_detected=False,
                    error=str(e),
                )
            )

    total_duration = time.monotonic() - total_start
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    rate = passed / len(results) if results else 0.0

    return EvalReport(
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=failed,
        success_rate=rate,
        total_duration_seconds=total_duration,
        results=results,
    )
