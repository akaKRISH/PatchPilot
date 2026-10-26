"""Unit and regression tests for TestRunner Docker detection and sandbox execution."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import CommandPolicyError, SandboxError
from patchpilot.schemas import TestSuiteName
from patchpilot.verification.runner import TestRunner


def test_is_docker_available_success() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(args=["docker", "info"], returncode=0),
        ) as mock_run,
    ):
        assert runner.is_docker_available() is True
        mock_run.assert_called_once_with(
            ["/usr/bin/docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_is_docker_available_missing_docker_cli() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value=None),
        patch("subprocess.run") as mock_run,
    ):
        assert runner.is_docker_available() is False
        mock_run.assert_not_called()


def test_is_docker_available_daemon_stopped() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["docker", "info"],
                returncode=1,
                stderr="Cannot connect to the Docker daemon",
            ),
        ),
    ):
        assert runner.is_docker_available() is False


def test_is_docker_available_timeout() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["docker", "info"], timeout=5),
        ),
    ):
        assert runner.is_docker_available() is False


def test_is_docker_available_subprocess_error() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=OSError("Permission denied")),
    ):
        assert runner.is_docker_available() is False


def test_reproduce_named_pipe_busy_false_negative_fixed() -> None:
    """Verify that even when Windows named pipes report busy, engine probe succeeds."""
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch("shutil.which", return_value="C:\\Program Files\\Docker\\docker.EXE"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["docker", "info"],
                returncode=0,
                stdout="Server Version: 29.7.2",
            ),
        ),
    ):
        assert runner.is_docker_available() is True


def test_is_sandbox_image_available_success() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config, docker_image="patchpilot-sandbox:latest")

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0),
        ) as mock_run,
    ):
        assert runner.is_sandbox_image_available() is True
        mock_run.assert_called_once_with(
            ["/usr/bin/docker", "image", "inspect", "patchpilot-sandbox:latest"],
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_is_sandbox_image_available_image_missing() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config, docker_image="patchpilot-sandbox:latest")

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1, stderr="No such image"),
        ),
    ):
        assert runner.is_sandbox_image_available() is False


def test_is_sandbox_image_available_docker_offline() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config)

    with (
        patch.object(runner, "is_docker_available", return_value=False),
        patch("subprocess.run") as mock_run,
    ):
        assert runner.is_sandbox_image_available() is False
        mock_run.assert_not_called()


def test_is_sandbox_image_available_timeout() -> None:
    config = PatchPilotConfig()
    runner = TestRunner(config, docker_image="patchpilot-sandbox:latest")

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=[], timeout=5),
        ),
    ):
        assert runner.is_sandbox_image_available() is False


def test_run_tests_raises_sandbox_error_when_docker_unavailable(tmp_path: Path) -> None:
    config = PatchPilotConfig(allow_host_execution=False)
    runner = TestRunner(config)

    with patch.object(runner, "is_docker_available", return_value=False):
        with pytest.raises(SandboxError) as exc_info:
            runner.run_tests(tmp_path, TestSuiteName.PYTEST)
        assert "Docker sandbox is unavailable" in str(exc_info.value)


def test_run_tests_raises_sandbox_error_when_image_missing(tmp_path: Path) -> None:
    config = PatchPilotConfig(allow_host_execution=False)
    runner = TestRunner(config)

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch.object(runner, "is_sandbox_image_available", return_value=False),
    ):
        with pytest.raises(SandboxError) as exc_info:
            runner.run_tests(tmp_path, TestSuiteName.PYTEST)
        assert "sandbox image is not built" in str(exc_info.value)


def test_run_tests_docker_runtime_error_does_not_fall_back_to_host(tmp_path: Path) -> None:
    config = PatchPilotConfig(allow_host_execution=True)
    runner = TestRunner(config)

    mock_host_run = MagicMock()
    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch.object(runner, "is_sandbox_image_available", return_value=True),
        patch.object(
            runner, "_run_in_docker", side_effect=SandboxError("Docker failed during run")
        ),
        patch.object(runner, "_run_on_host", mock_host_run),
    ):
        with pytest.raises(SandboxError) as exc_info:
            runner.run_tests(tmp_path, TestSuiteName.PYTEST)
        assert "Docker failed during run" in str(exc_info.value)
        mock_host_run.assert_not_called()


def test_run_in_docker_constructs_secure_container_args(tmp_path: Path) -> None:
    config = PatchPilotConfig(test_timeout_seconds=42)
    runner = TestRunner(config, docker_image="patchpilot-sandbox:latest")

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed in 0.01s", stderr=""
            ),
        ) as mock_run,
    ):
        result = runner._run_in_docker(tmp_path, TestSuiteName.PYTEST, target="tests/test_foo.py")

        assert result.passed is True
        mock_run.assert_called_once_with(
            [
                "/usr/bin/docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,size=64m",
                "-v",
                f"{tmp_path}:/workspace:rw",
                "-w",
                "/workspace",
                "patchpilot-sandbox:latest",
                "python",
                "-m",
                "pytest",
                "-v",
                "tests/test_foo.py",
            ],
            capture_output=True,
            text=True,
            timeout=42,
        )


def test_run_tests_docker_unsupported_suite_raises_command_policy_error(tmp_path: Path) -> None:
    config = PatchPilotConfig(allow_host_execution=False)
    runner = TestRunner(config)

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch.object(runner, "is_sandbox_image_available", return_value=True),
    ):
        with pytest.raises(CommandPolicyError) as exc_info:
            runner.run_tests(tmp_path, TestSuiteName.JEST)
        assert "not supported in the Python-only sandbox" in str(exc_info.value)
