"""Pytest fixtures and test environment setup."""

from pathlib import Path

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.workspace.manager import WorkspaceManager


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with basic python code and tests."""
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    src = repo / "calculator.py"
    src.write_text(
        '"""Sample calculator."""\n\ndef add(a, b):\n    return a - b\n\ndef subtract(a, b):\n    return a - b\n',
        encoding="utf-8",
    )

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_calculator.py"
    test_file.write_text(
        "from calculator import add, subtract\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_subtract():\n    assert subtract(5, 3) == 2\n",
        encoding="utf-8",
    )

    return repo


@pytest.fixture
def test_config(tmp_path: Path) -> PatchPilotConfig:
    """Provide a validated test configuration pointing to a temp data dir."""
    data_dir = tmp_path / "test_patchpilot_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return PatchPilotConfig(
        model_name="qwen3.5:4b",
        ollama_base_url="http://localhost:11434",
        request_timeout_seconds=10,
        max_repair_attempts=2,
        max_agent_steps=5,
        max_tool_calls=10,
        data_dir=data_dir,
        allow_host_execution=True,
    )


@pytest.fixture
def workspace_manager(temp_repo: Path, test_config: PatchPilotConfig) -> WorkspaceManager:
    """Initialize a WorkspaceManager instance on temp_repo."""
    mgr = WorkspaceManager(source_repo_path=temp_repo, data_dir=test_config.data_dir)
    mgr.setup()
    return mgr
