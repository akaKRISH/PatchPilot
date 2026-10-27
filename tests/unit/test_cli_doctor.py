"""Unit tests for 'patchpilot doctor' CLI command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchpilot.cli import app

runner = CliRunner()


def test_doctor_reports_ready_when_all_checks_pass() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "System Status: READY" in result.stdout
        assert "patchpilot demo" in result.stdout


def test_doctor_reports_not_ready_when_docker_unavailable() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
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

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "System Status: NOT READY" in result.stdout
        assert "Start Docker Desktop" in result.stdout
        assert "docker info" in result.stdout


def test_doctor_reports_not_ready_when_sandbox_image_missing() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
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

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "System Status: NOT READY" in result.stdout
        assert "Build sandbox image" in result.stdout
        assert "patchpilot-sandbox:latest" in result.stdout


def test_doctor_reports_not_ready_when_ollama_offline() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = False
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "System Status: NOT READY" in result.stdout
        assert "Ollama server is offline" in result.stdout
        assert "ollama serve" in result.stdout


def test_doctor_reports_not_ready_when_model_missing() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = False
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "System Status: NOT READY" in result.stdout
        assert "ollama pull" in result.stdout


def test_doctor_probe_tools_supported() -> None:
    with (
        patch("patchpilot.cli.OllamaClient") as mock_client_cls,
        patch("patchpilot.cli.TestRunner") as mock_runner_cls,
    ):
        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.is_model_installed.return_value = True
        mock_client.check_tool_capability.return_value = (True, "Tool calls verified")
        mock_client_cls.return_value = mock_client

        mock_runner = MagicMock()
        mock_runner.is_docker_available.return_value = True
        mock_runner.is_sandbox_image_available.return_value = True
        mock_runner.docker_image = "patchpilot-sandbox:latest"
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["doctor", "--probe-tools"])
        assert result.exit_code == 0
        assert "Tool-Calling Probe" in result.stdout
        assert "SUPPORTED" in result.stdout
        assert "System Status: READY" in result.stdout
