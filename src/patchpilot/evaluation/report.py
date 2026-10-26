"""Report formatting utilities for evaluation benchmarks."""

from patchpilot.schemas import EvalReport


def format_evaluation_summary(report: EvalReport) -> str:
    """Format evaluation report as a human-readable text summary."""
    lines = [
        "========================================",
        "        PATCHPILOT BENCHMARK REPORT      ",
        "========================================",
        f"Total Cases:     {report.total_cases}",
        f"Passed Cases:    {report.passed_cases}",
        f"Failed Cases:    {report.failed_cases}",
        f"Success Rate:    {report.success_rate * 100:.1f}%",
        f"Total Duration:  {report.total_duration_seconds:.2f}s",
        "----------------------------------------",
        "Case Details:",
    ]
    for r in report.results:
        outcome = "PASS" if r.success else "FAIL"
        lines.append(
            f"  [{outcome}] {r.case_id} - Status: {r.status.value} - {r.duration_seconds:.2f}s - "
            f"Tools: {r.tool_calls_count} - Attempts: {r.attempts}"
        )
        if r.error:
            lines.append(f"         Error: {r.error}")

    lines.append("========================================")
    return "\n".join(lines)
