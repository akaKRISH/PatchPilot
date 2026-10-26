"""Integration tests for live local Ollama endpoint."""

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.ollama_client import OllamaClient


@pytest.mark.integration
def test_live_ollama_connectivity() -> None:
    config = PatchPilotConfig.load()
    client = OllamaClient(config)
    if not client.is_reachable():
        pytest.skip(f"Live Ollama server is not reachable at {config.ollama_base_url}")

    models = client.list_models()
    assert isinstance(models, list)


@pytest.mark.integration
def test_live_ollama_chat_completion() -> None:
    config = PatchPilotConfig.load()
    client = OllamaClient(config)
    if not client.is_reachable():
        pytest.skip("Live Ollama server is not reachable")
    if not client.is_model_installed(config.model_name):
        pytest.skip(f"Configured model '{config.model_name}' is not installed in Ollama")

    resp = client.chat(
        messages=[{"role": "user", "content": "Reply with PATCHPILOT_OK"}],
    )
    assert "message" in resp
    content = resp["message"].get("content", "")
    assert len(content) > 0
