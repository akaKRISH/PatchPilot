"""Unit tests for configuration system."""

from pathlib import Path

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import ConfigError


def test_default_config() -> None:
    cfg = PatchPilotConfig()
    assert cfg.model_name == "qwen3.5:4b"
    assert cfg.ollama_base_url == "http://localhost:11434"
    assert cfg.ollama_think is False
    assert cfg.think is False
    assert cfg.max_repair_attempts == 3
    assert cfg.allow_host_execution is False


def test_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATCHPILOT_OLLAMA_BASE_URL", "invalid_url_without_protocol")
    with pytest.raises(ConfigError):
        PatchPilotConfig.load()


def test_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATCHPILOT_MODEL_NAME", "custom-model:latest")
    monkeypatch.setenv("PATCHPILOT_MAX_REPAIR_ATTEMPTS", "5")
    monkeypatch.setenv("PATCHPILOT_THINK", "true")
    cfg = PatchPilotConfig.load()
    assert cfg.model_name == "custom-model:latest"
    assert cfg.max_repair_attempts == 5
    assert cfg.ollama_think is True
    assert cfg.think is True


def test_toml_loading(tmp_path: Path) -> None:
    toml_path = tmp_path / "custom.toml"
    toml_path.write_text(
        '[model]\nname = "toml-model:latest"\nrequest_timeout_seconds = 45\nthink = true\n\n[agent]\nmax_repair_attempts = 2\n',
        encoding="utf-8",
    )
    cfg = PatchPilotConfig.load(config_path=toml_path)
    assert cfg.model_name == "toml-model:latest"
    assert cfg.request_timeout_seconds == 45
    assert cfg.ollama_think is True
    assert cfg.think is True
    assert cfg.max_repair_attempts == 2


def test_think_alias_init() -> None:
    cfg1 = PatchPilotConfig.model_validate({"think": True})
    assert cfg1.ollama_think is True
    assert cfg1.think is True

    cfg2 = PatchPilotConfig(ollama_think=False)
    assert cfg2.ollama_think is False
    assert cfg2.think is False


def test_to_redacted_dict() -> None:
    cfg = PatchPilotConfig()
    d = cfg.to_redacted_dict()
    assert "model_name" in d
    assert "ollama_base_url" in d
    assert isinstance(d["data_dir"], str)
