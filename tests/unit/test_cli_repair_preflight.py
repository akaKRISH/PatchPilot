"""Unit tests proving fast prerequisite failure before model inference."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchpilot.agent.orchestrator import AgentOrchestrator
from patchpilot.cli import app
from patchpilot.config import PatchPilotConfig
from patchpilot.errors import SandboxError
from patchpilot.schemas import (
    RepairStatus,
    RunReport,
    TaskRequest,
    TestSuiteName,
    VerificationSummary,
)

runner = CliRunner()


def test_repair_fails_fast_when_repo_not_found(tmp_path: Path) -> None:
    nonexistent = tmp_path / "nonexistent_repo"

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        result = runner.invoke(app, ["repair", "--repo", str(nonexistent), "--task", "Fix bug"])
        assert result.exit_code == 1
        assert "does not exist or is not a directory" in result.stdout
        mock_client_cls.assert_not_called()
        mock_orchestrator_cls.assert_not_called()


def test_repair_fails_fast_when_ollama_unreachable(tmp_path: Path) -> None:
    repo = tmp_path / "valid_repo"
    repo.mkdir()

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = False
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repair", "--repo", str(repo), "--task", "Fix bug"])
        assert result.exit_code == 1
        assert "Ollama server is unreachable" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_repair_fails_fast_when_model_missing(tmp_path: Path) -> None:
    repo = tmp_path / "valid_repo"
    repo.mkdir()

    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.AgentOrchestrator") as mock_orchestrator_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = False
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repair", "--repo", str(repo), "--task", "Fix bug"])
        assert result.exit_code == 1
        assert "is not installed in local Ollama" in result.stdout
        assert "ollama pull" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_repair_fails_fast_when_docker_unavailable_without_opt_in(tmp_path: Path) -> None:
    repo = tmp_path / "valid_repo"
    repo.mkdir()

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

        result = runner.invoke(app, ["repair", "--repo", str(repo), "--task", "Fix bug"])
        assert result.exit_code == 1
        assert "Docker daemon is not running or unreachable" in result.stdout
        assert "docker info" in result.stdout
        assert "patchpilot doctor" in result.stdout
        assert "--allow-host-execution" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_repair_fails_fast_when_sandbox_image_missing_without_opt_in(tmp_path: Path) -> None:
    repo = tmp_path / "valid_repo"
    repo.mkdir()

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

        result = runner.invoke(app, ["repair", "--repo", str(repo), "--task", "Fix bug"])
        assert result.exit_code == 1
        assert "Docker sandbox image" in result.stdout
        assert "docker build -t patchpilot-sandbox:latest" in result.stdout
        assert "patchpilot doctor" in result.stdout
        mock_orchestrator_cls.assert_not_called()


def test_repair_allows_host_execution_opt_in_with_warning(tmp_path: Path) -> None:
    repo = tmp_path / "valid_repo"
    repo.mkdir()

    mock_report = RunReport(
        run_id="run_host_exec",
        task=TaskRequest(
            repo_path=str(repo),
            task_description="Fix bug",
            test_suite=TestSuiteName.PYTEST,
        ),
        status=RepairStatus.FIXED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=1.0,
        attempts_made=1,
        max_attempts=3,
        verification=VerificationSummary(verified=True),
        original_repo_unmodified=True,
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
        mock_runner.is_docker_available.return_value = False
        mock_runner_cls.return_value = mock_runner

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_repair.return_value = mock_report
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = runner.invoke(
            app, ["repair", "--repo", str(repo), "--task", "Fix bug", "--allow-host-execution"]
        )

        assert result.exit_code == 0
        assert "WARNING: Unsafe host execution mode enabled." in result.stdout
        mock_orchestrator_cls.assert_called_once()


def test_orchestrator_run_repair_aborts_on_sandbox_error_without_model_inference(
    tmp_path: Path,
) -> None:
    """Prove that AgentOrchestrator.run_repair halts before model inference on SandboxError."""
    source_repo = tmp_path / "repo"
    source_repo.mkdir()
    (source_repo / "calc.py").write_text("def add(a, b): return a - b\n")

    cfg = PatchPilotConfig(data_dir=tmp_path / "data", allow_host_execution=False)
    mock_client = MagicMock()
    mock_runner = MagicMock()
    mock_runner.run_tests.side_effect = SandboxError("Docker daemon is offline")

    orchestrator = AgentOrchestrator(
        config=cfg,
        ollama_client=mock_client,
        test_runner=mock_runner,
    )

    task = TaskRequest(
        repo_path=str(source_repo),
        task_description="Fix add",
        test_suite=TestSuiteName.PYTEST,
    )

    report = orchestrator.run_repair(task)

    assert report.status == RepairStatus.UNRESOLVED
    assert "Sandbox error: Docker daemon is offline" in (report.error_message or "")
    assert report.attempts_made == 0
    # Crucial assertion: the language model was NEVER invoked
    mock_client.chat.assert_not_called()
