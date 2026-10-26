"""Integration tests for Docker-backed sandbox execution."""

from pathlib import Path

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.schemas import TestSuiteName
from patchpilot.verification.runner import TestRunner


@pytest.mark.integration
def test_docker_runner_sandbox(tmp_path: Path) -> None:
    config = PatchPilotConfig.load()
    runner = TestRunner(config)

    if not runner.is_docker_available():
        pytest.skip("Docker CLI or daemon is not available on host system.")
    if not runner.is_sandbox_image_available():
        pytest.skip(f"Sandbox image '{runner.docker_image}' is not built.")

    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    result = runner.run_tests(workspace_dir=tmp_path, suite=TestSuiteName.PYTEST)
    assert result.passed is True
    assert result.tests_run >= 1
