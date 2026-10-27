"""Unit tests for 'patchpilot init' CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from patchpilot.cli import app
from patchpilot.config import PatchPilotConfig

runner = CliRunner()


def test_init_creates_valid_default_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "[OK] Initialized configuration at:" in result.stdout
    assert "patchpilot doctor" in result.stdout

    target = tmp_path / ".patchpilot.toml"
    assert target.is_file()

    content = target.read_text(encoding="utf-8")
    assert 'name = "qwen3.5:4b"' in content
    assert "think = false" in content
    assert "allow_host_execution = false" in content

    # Verify that PatchPilotConfig can parse and load the generated config
    cfg = PatchPilotConfig.load(config_path=target)
    assert cfg.model_name == "qwen3.5:4b"
    assert cfg.ollama_think is False
    assert cfg.allow_host_execution is False


def test_init_prevents_overwrite_without_force(tmp_path: Path) -> None:
    config_file = tmp_path / ".patchpilot.toml"
    config_file.write_text("existing content", encoding="utf-8")

    result = runner.invoke(app, ["init", "--path", str(config_file)])
    assert result.exit_code == 1
    assert "already exists" in result.stdout
    assert "--force" in result.stdout
    assert config_file.read_text(encoding="utf-8") == "existing content"


def test_init_overwrites_with_force(tmp_path: Path) -> None:
    config_file = tmp_path / ".patchpilot.toml"
    config_file.write_text("existing content", encoding="utf-8")

    result = runner.invoke(app, ["init", "--path", str(config_file), "--force"])
    assert result.exit_code == 0
    assert "[OK] Initialized configuration at:" in result.stdout

    content = config_file.read_text(encoding="utf-8")
    assert 'name = "qwen3.5:4b"' in content
    assert content != "existing content"


def test_init_creates_parent_directories_when_needed(tmp_path: Path) -> None:
    nested_path = tmp_path / "deep" / "nested" / "dir" / ".patchpilot.toml"
    result = runner.invoke(app, ["init", "--path", str(nested_path)])
    assert result.exit_code == 0
    assert nested_path.is_file()

    cfg = PatchPilotConfig.load(config_path=nested_path)
    assert cfg.model_name == "qwen3.5:4b"
