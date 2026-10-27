"""Regression tests for benchmark safety boundaries and fail-closed defaults."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchpilot.cli import app
from patchpilot.config import PatchPilotConfig
from patchpilot.errors import SandboxError
from patchpilot.evaluation.benchmark import run_smoke_benchmark
from patchpilot.schemas import (
    EvalReport,
    RepairStatus,
)

runner = CliRunner()


def test_smoke_benchmark_default_does_not_enable_host_execution() -> None:
    """Prove that run_smoke_benchmark does not silently enable host execution."""
    cfg = PatchPilotConfig(allow_host_execution=False)

    with patch("patchpilot.evaluation.benchmark.AgentOrchestrator") as mock_orch_cls:
        mock_orch = MagicMock()
        mock_orch.run_repair.side_effect = SandboxError("Docker sandbox unavailable")
        mock_orch_cls.return_value = mock_orch

        report = run_smoke_benchmark(cfg)

        mock_orch_cls.assert_called_once()
        passed_cfg: PatchPilotConfig = mock_orch_cls.call_args[0][0]
        # Crucial invariant: allow_host_execution must remain False
        assert passed_cfg.allow_host_execution is False

        # Benchmark must fail-closed
        assert report.passed_cases == 0
        assert report.failed_cases > 0
        assert any("Docker sandbox unavailable" in r.error for r in report.results if r.error)


def test_smoke_benchmark_preserves_explicit_host_execution_opt_in() -> None:
    """Verify that when host execution is explicitly configured, it is respected."""
    cfg = PatchPilotConfig(allow_host_execution=True)

    with patch("patchpilot.evaluation.benchmark.AgentOrchestrator") as mock_orch_cls:
        mock_orch = MagicMock()
        mock_report = MagicMock()
        mock_report.status = RepairStatus.FIXED
        mock_report.attempts = []
        mock_report.attempts_made = 1
        mock_report.verification = None
        mock_report.error_message = None
        mock_orch.run_repair.return_value = mock_report
        mock_orch_cls.return_value = mock_orch

        report = run_smoke_benchmark(cfg)

        mock_orch_cls.assert_called_once()
        passed_cfg: PatchPilotConfig = mock_orch_cls.call_args[0][0]
        assert passed_cfg.allow_host_execution is True
        assert report.passed_cases == report.total_cases


def test_eval_cli_defaults_to_safe_mode() -> None:
    """Verify CLI eval defaults to safe mode without host execution."""
    mock_eval_report = EvalReport(
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        success_rate=1.0,
        total_duration_seconds=1.0,
        results=[],
    )

    with patch("patchpilot.cli.run_smoke_benchmark") as mock_run_benchmark:
        mock_run_benchmark.return_value = mock_eval_report

        result = runner.invoke(app, ["eval", "--suite", "smoke"])
        assert result.exit_code == 0
        assert "WARNING: Unsafe host execution mode enabled" not in result.stdout

        mock_run_benchmark.assert_called_once()
        passed_cfg: PatchPilotConfig = mock_run_benchmark.call_args[0][0]
        assert passed_cfg.allow_host_execution is False


def test_eval_cli_explicit_allow_host_execution_prints_warning() -> None:
    """Verify CLI eval with --allow-host-execution shows conspicuous warning."""
    mock_eval_report = EvalReport(
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        success_rate=1.0,
        total_duration_seconds=1.0,
        results=[],
    )

    with patch("patchpilot.cli.run_smoke_benchmark") as mock_run_benchmark:
        mock_run_benchmark.return_value = mock_eval_report

        result = runner.invoke(app, ["eval", "--suite", "smoke", "--allow-host-execution"])
        assert result.exit_code == 0
        assert (
            "WARNING: Unsafe host execution mode enabled for benchmark evaluation." in result.stdout
        )

        mock_run_benchmark.assert_called_once()
        passed_cfg: PatchPilotConfig = mock_run_benchmark.call_args[0][0]
        assert passed_cfg.allow_host_execution is True
