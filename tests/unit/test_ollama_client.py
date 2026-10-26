"""Unit tests for Ollama client mocking HTTP communication."""

from typing import Any

import httpx
import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import (
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from patchpilot.ollama_client import OllamaClient


def test_is_reachable_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "0.1.0"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    assert client.is_reachable() is True


def test_is_reachable_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    assert client.is_reachable() is False


def test_list_models_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen3.5:9b"}, {"name": "llama3.1:8b"}]},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    models = client.list_models()
    assert "qwen3.5:9b" in models
    assert client.is_model_installed("qwen3.5:9b") is True
    assert client.is_model_installed("nonexistent:latest") is False


def test_default_model_is_qwen3_5_4b() -> None:
    client = OllamaClient(PatchPilotConfig())
    assert client.model_name == "qwen3.5:4b"
    assert client.think is False


def test_chat_outgoing_payload_contains_top_level_think() -> None:
    captured_payload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        nonlocal captured_payload
        captured_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    # 1. Default config (think=False)
    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    client.chat([{"role": "user", "content": "hi"}])
    assert "think" in captured_payload
    assert captured_payload["think"] is False
    assert "think" not in captured_payload["options"]
    assert captured_payload["model"] == "qwen3.5:4b"

    # 2. Configured think=True
    client_think = OllamaClient(PatchPilotConfig(ollama_think=True), http_client=mock_client)
    client_think.chat([{"role": "user", "content": "hi"}])
    assert captured_payload["think"] is True

    # 3. Request-level think override
    client.chat([{"role": "user", "content": "hi"}], think=True)
    assert captured_payload["think"] is True


def test_chat_success_with_tool_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        data = {
            "message": {
                "role": "assistant",
                "content": "Inspecting repository files",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "calculator.py"},
                        }
                    }
                ],
            }
        }
        return httpx.Response(200, json=data)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    resp = client.chat([{"role": "user", "content": "read the file"}])
    assert "message" in resp
    calls = client.parse_tool_calls(resp["message"])
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments["path"] == "calculator.py"


def test_parse_tool_calls_valid_ping_test() -> None:
    client = OllamaClient(PatchPilotConfig())
    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_abkjudwh",
                "function": {
                    "index": 0,
                    "name": "ping_test",
                    "arguments": {"value": "42"},
                },
            }
        ],
    }
    calls = client.parse_tool_calls(msg)
    assert len(calls) == 1
    assert calls[0].name == "ping_test"
    assert calls[0].arguments == {"value": "42"}
    assert calls[0].call_id == "call_abkjudwh"


def test_chat_model_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(model_name="missing_model"), http_client=mock_client)
    with pytest.raises(OllamaModelNotFoundError):
        client.chat([{"role": "user", "content": "hi"}])


def test_chat_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)
    with pytest.raises(OllamaTimeoutError):
        client.chat([{"role": "user", "content": "hi"}])


def test_chat_http_500_response_body_preserved() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500, json={"error": "model 'qwen3.5:9b' requires more memory than available"}
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaClient(PatchPilotConfig(), http_client=mock_client)

    with pytest.raises(OllamaResponseError) as exc_info:
        client.chat([{"role": "user", "content": "hello"}])

    err = exc_info.value
    assert err.status_code == 500
    assert err.response_body == "model 'qwen3.5:9b' requires more memory than available"
    assert "HTTP 500: model 'qwen3.5:9b' requires more memory than available" in str(err)


def test_parse_tool_calls_malformed_arguments() -> None:
    client = OllamaClient(PatchPilotConfig())

    # 1. Invalid JSON string in arguments
    msg1 = {
        "tool_calls": [
            {
                "function": {
                    "name": "edit_file",
                    "arguments": "{not valid json",
                }
            }
        ]
    }
    calls1 = client.parse_tool_calls(msg1)
    assert len(calls1) == 1
    assert calls1[0].name == "edit_file"
    assert calls1[0].arguments == {}

    # 2. Non-dict function or non-dict item
    msg2 = {
        "tool_calls": [
            "not a dict",
            {"function": "not a dict"},
            {"function": {"name": None}},
            {"function": {"name": "inspect_repo", "arguments": ["not a dict"]}},
        ]
    }
    calls2 = client.parse_tool_calls(msg2)
    assert len(calls2) == 1
    assert calls2[0].name == "inspect_repo"
    assert calls2[0].arguments == {}


def test_sanitize_response_body() -> None:
    from patchpilot.ollama_client import sanitize_response_body

    assert sanitize_response_body("") == ""
    assert sanitize_response_body('{"error": "out of memory"}') == "out of memory"
    assert sanitize_response_body("raw text error") == "raw text error"

    # Truncation test
    long_text = "x" * 600
    sanitized = sanitize_response_body(long_text, max_length=100)
    assert len(sanitized) == 103  # 100 + "..."
    assert sanitized.endswith("...")
