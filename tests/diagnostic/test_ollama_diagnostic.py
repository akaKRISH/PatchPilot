"""Inexpensive opt-in live diagnostic test for Ollama model tool-calling capability."""

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import (
    OllamaConnectionError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from patchpilot.ollama_client import OllamaClient


@pytest.mark.diagnostic
def test_ollama_minimal_tool_call_diagnostic() -> None:
    """Send an inexpensive minimal diagnostic request to verify model response type."""
    config = PatchPilotConfig.load()
    client = OllamaClient(config)

    if not client.is_reachable():
        pytest.skip(f"Ollama is unreachable at {config.ollama_base_url}")

    if not client.is_model_installed(config.model_name):
        pytest.skip(f"Target model '{config.model_name}' is not installed in local Ollama")

    # Bounded execution timeout for quick diagnostic probe (15s)
    client.timeout = 15.0
    client._client.timeout = 15.0

    harmless_tools = [
        {
            "type": "function",
            "function": {
                "name": "ping_test",
                "description": "A harmless diagnostic tool.",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            },
        }
    ]

    messages = [
        {
            "role": "user",
            "content": "Call ping_test exactly once with value 42. Do not answer in natural language.",
        }
    ]

    outcome: str = "UNKNOWN"
    details: str = ""

    try:
        resp = client.chat(messages=messages, tools=harmless_tools)
        msg = resp.get("message", {})
        calls = client.parse_tool_calls(msg)
        content = msg.get("content", "")

        if calls:
            outcome = "TOOL_CALL"
            details = (
                f"Received valid tool call to '{calls[0].name}' with args {calls[0].arguments}"
            )
            # Validate function name and argument structure without executing
            assert calls[0].name == "ping_test"
            assert isinstance(calls[0].arguments, dict)
            # Never execute model-generated tool calls inside the diagnostic test
        elif content:
            outcome = "ORDINARY_TEXT"
            details = f"Model returned text instead of calling tool: {content[:150]}"
        else:
            outcome = "EMPTY_RESPONSE"
            details = "Model returned empty message without content or tool calls"

    except OllamaTimeoutError as e:
        outcome = "TIMEOUT"
        details = str(e)
    except OllamaResponseError as e:
        outcome = f"HTTP_{e.status_code or 'ERROR'}"
        details = f"Status: {e.status_code}, Response Body: {e.response_body or str(e)}"
    except OllamaConnectionError as e:
        outcome = "CONNECTION_ERROR"
        details = str(e)
    except Exception as e:
        outcome = f"UNEXPECTED_{type(e).__name__}"
        details = str(e)

    # Output diagnostic report for log inspection
    print(f"\n[Ollama Diagnostic] Model: {config.model_name} | Outcome: {outcome}")
    print(f"[Ollama Diagnostic] Details: {details}")

    # Validate that outcome is one of the recognized categories
    assert outcome in (
        "TOOL_CALL",
        "ORDINARY_TEXT",
        "TIMEOUT",
        "HTTP_500",
        "HTTP_ERROR",
        "CONNECTION_ERROR",
        "EMPTY_RESPONSE",
    )
    # Ensure text output is NEVER falsely assumed to be a tool call
    if outcome == "ORDINARY_TEXT":
        assert calls == []
