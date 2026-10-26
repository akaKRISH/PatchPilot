"""Test runner supporting Docker sandboxed execution and explicit opt-in host execution."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import SandboxError
from patchpilot.safety.commands import CommandPolicy
from patchpilot.schemas import TestSuiteName, TestSuiteResult
from patchpilot.verification.results import parse_test_output


class TestRunner:
    """Executes predefined test suites in Docker sandboxes or controlled host environments."""

    __test__ = False

    def __init__(
        self,
        config: PatchPilotConfig,
        docker_image: str = "patchpilot-sandbox:latest",
    ) -> None:
        self.config = config
        self.docker_image = docker_image
        self.test_timeout = float(config.test_timeout_seconds)

    def is_docker_available(self) -> bool:
        """Check if Docker CLI and daemon are available."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run(
                [docker_bin, "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def is_sandbox_image_available(self) -> bool:
        """Check if the sandbox image is already built locally."""
        if not self.is_docker_available():
            return False
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run(
                [docker_bin, "image", "inspect", self.docker_image],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_tests(
        self,
        workspace_dir: Path,
        suite: TestSuiteName,
        target: str | None = None,
    ) -> TestSuiteResult:
        """Run the requested test suite against workspace_dir."""
        workspace_dir = workspace_dir.resolve()

        if self.is_docker_available() and self.is_sandbox_image_available():
            return self._run_in_docker(workspace_dir, suite, target)
        elif self.config.allow_host_execution:
            return self._run_on_host(workspace_dir, suite, target)
        else:
            raise SandboxError(
                "Docker sandbox is unavailable or sandbox image is not built.\n"
                "To protect your host, PatchPilot will not execute untrusted repository code.\n"
                "Build the sandbox image using: docker build -t patchpilot-sandbox:latest sandbox/\n"
                "Or explicitly enable unsafe host execution with --allow-host-execution."
            )

    def _run_in_docker(
        self,
        workspace_dir: Path,
        suite: TestSuiteName,
        target: str | None = None,
    ) -> TestSuiteResult:
        """Run tests inside Docker container with restricted isolation flags."""
        docker_cmd = CommandPolicy.build_docker_test_command(suite, target)

        # Docker isolation flags:
        # --network none: no outbound/inbound network
        # --read-only: read-only root container filesystem
        # --tmpfs /tmp: bounded writable temp dir
        # -v <workspace>:/workspace:rw: disposable copy mounted to /workspace
        # -w /workspace: working directory
        docker_bin = shutil.which("docker") or "docker"
        container_args = [
            docker_bin,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
            "-v",
            f"{workspace_dir}:/workspace:rw",
            "-w",
            "/workspace",
            self.docker_image,
            *docker_cmd,
        ]

        start_time = time.monotonic()
        try:
            res = subprocess.run(
                container_args,
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
            )
            duration = time.monotonic() - start_time
            combined_output = (res.stdout or "") + "\n" + (res.stderr or "")
            return parse_test_output(
                suite=suite,
                exit_code=res.returncode,
                output=combined_output,
                duration_seconds=duration,
                max_output_chars=self.config.max_command_output_characters,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start_time
            out_str = (
                e.stdout.decode("utf-8", errors="replace")
                if isinstance(e.stdout, bytes)
                else str(e.stdout or "")
            )
            output = out_str + "\n[TEST TIMEOUT EXPIRED]"
            return parse_test_output(
                suite=suite,
                exit_code=-1,
                output=output,
                duration_seconds=duration,
                max_output_chars=self.config.max_command_output_characters,
            )
        except Exception as e:
            raise SandboxError(f"Docker sandbox execution failed: {e}") from e

    def _run_on_host(
        self,
        workspace_dir: Path,
        suite: TestSuiteName,
        target: str | None = None,
    ) -> TestSuiteResult:
        """Unsafe fallback: run tests using the local Python interpreter."""
        python_exec = sys.executable
        host_cmd = CommandPolicy.build_test_command(suite, python_exec, target)

        start_time = time.monotonic()
        try:
            res = subprocess.run(
                host_cmd,
                cwd=str(workspace_dir),
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
            )
            duration = time.monotonic() - start_time
            combined_output = (res.stdout or "") + "\n" + (res.stderr or "")
            return parse_test_output(
                suite=suite,
                exit_code=res.returncode,
                output=combined_output,
                duration_seconds=duration,
                max_output_chars=self.config.max_command_output_characters,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start_time
            out_str = (
                e.stdout.decode("utf-8", errors="replace")
                if isinstance(e.stdout, bytes)
                else str(e.stdout or "")
            )
            output = out_str + "\n[HOST EXECUTION TIMEOUT EXPIRED]"
            return parse_test_output(
                suite=suite,
                exit_code=-1,
                output=output,
                duration_seconds=duration,
                max_output_chars=self.config.max_command_output_characters,
            )
        except Exception as e:
            raise SandboxError(f"Host test execution failed: {e}") from e
