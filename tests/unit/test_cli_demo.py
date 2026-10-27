"""Unit tests for 'patchpilot demo' CLI command."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchpilot.cli import app
from patchpilot.schemas import (
    PatchArtifact,
    RepairStatus,
    RunReport,
    TaskRequest,
    TestSuiteName,
    VerificationSummary,
)

runner = CliRunner()


def test_demo_fails_fast_when_docker_unavailable(tmp_path: Path) -> None:
    demo_repo = tmp_path / "demo_repo"
    demo_repo.mkdir()
    (demo_repo / "calculator.py").write_text("def add(a, b): return a - b\n")

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = False
        mock_runner.is_sandbox_image_available.return_value = False
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["demo", "--repo", str(demo_repo)])
        assert result.exit_code == 1
        assert "Docker daemon is not running" in result.stdout
        assert "docker info" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_demo_fails_fast_when_sandbox_image_missing(tmp_path: Path) -> None:
    demo_repo = tmp_path / "demo_repo"
    demo_repo.mkdir()
    (demo_repo / "calculator.py").write_text("def add(a, b): return a - b\n")

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = False
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["demo", "--repo", str(demo_repo)])
        assert result.exit_code == 1
        assert "Docker sandbox image" in result.stdout
        assert "docker build -t patchpilot-sandbox:latest" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_demo_fails_when_repo_not_found(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["demo", "--repo", str(nonexistent)])
    assert result.exit_code == 1
    assert "does not exist" in result.stdout


def test_demo_executes_successfully_and_reports_artifacts(tmp_path: Path) -> None:
    demo_repo = tmp_path / "demo_repo"
    demo_repo.mkdir()
    (demo_repo / "calculator.py").write_text("def add(a, b): return a - b\n")

    data_dir = tmp_path / ".patchpilot-data"

    mock_report = RunReport(
        run_id="run_demo_123",
        task=TaskRequest(
            repo_path=str(demo_repo),
            task_description="Fix add",
            test_suite=TestSuiteName.PYTEST,
        ),
        status=RepairStatus.FIXED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=3.5,
        attempts_made=1,
        max_attempts=3,
        verification=VerificationSummary(verified=True),
        patch=PatchArtifact(
            changed_files=[],
            unified_diff="--- a/calculator.py\n+++ b/calculator.py\n@@ -1 +1 @@\n-return a - b\n+return a + b\n",
        ),
        original_repo_unmodified=True,
    )

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
        patch("patchpilot.cli.PatchPilotConfig.load") as mock_cfg_load,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner_cls.return_value = mock_runner

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_repair.return_value = mock_report
        mock_orchestrator_cls.return_value = mock_orchestrator

        from patchpilot.config import PatchPilotConfig

        test_cfg = PatchPilotConfig(data_dir=data_dir, allow_host_execution=True)
        mock_cfg_load.return_value = test_cfg

        result = runner.invoke(app, ["demo", "--repo", str(demo_repo)])

        assert result.exit_code == 0
        assert "Run ID: run_demo_123" in result.stdout
        assert "FIXED" in result.stdout
        assert "[SUCCESS] Demo repair successfully verified" in result.stdout
        assert "Report Artifact:" in result.stdout

        # Verify host execution was forcefully disabled for demo
        assert test_cfg.allow_host_execution is False


def test_demo_fails_when_repair_unresolved(tmp_path: Path) -> None:
    demo_repo = tmp_path / "demo_repo"
    demo_repo.mkdir()
    (demo_repo / "calculator.py").write_text("def add(a, b): return a - b\n")

    mock_report = RunReport(
        run_id="run_demo_fail",
        task=TaskRequest(
            repo_path=str(demo_repo),
            task_description="Fix add",
            test_suite=TestSuiteName.PYTEST,
        ),
        status=RepairStatus.UNRESOLVED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=5.0,
        attempts_made=3,
        max_attempts=3,
        verification=VerificationSummary(verified=False),
        original_repo_unmodified=True,
        error_message="Test assertion failed",
    )

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner_cls.return_value = mock_runner

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_repair.return_value = mock_report
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = runner.invoke(app, ["demo", "--repo", str(demo_repo)])
        assert result.exit_code == 1
        assert "Demo repair concluded with status: UNRESOLVED" in result.stdout
        assert "Failure Reason:" in result.stdout
