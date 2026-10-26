"""Ollama HTTP client supporting native tool-calling, chat, and capability verification."""

import json
import logging
from typing import Any

import httpx

from patchpilot.config import PatchPilotConfig
from patchpilot.errors import (
    OllamaConnectionError,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from patchpilot.schemas import ToolCall

logger = logging.getLogger("patchpilot.ollama")


def sanitize_response_body(raw_text: str, max_length: int = 500) -> str:
    """Sanitize and bound response body for diagnostic error reporting."""
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "error" in parsed:
            cleaned = str(parsed["error"]).strip()
    except Exception:
        pass
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    return cleaned


class OllamaClient:
    """Robust local Ollama client."""

    def __init__(self, config: PatchPilotConfig, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self.base_url = config.ollama_base_url.rstrip("/")
        self.model_name = config.model_name
        self.think = config.ollama_think
        self.timeout = float(config.request_timeout_seconds)
        self._client = http_client or httpx.Client(timeout=self.timeout)

    def is_reachable(self) -> bool:
        """Check if the Ollama endpoint is running and reachable."""
        try:
            resp = self._client.get(f"{self.base_url}/api/version")
            return resp.status_code == 200
        except Exception:
            try:
                resp = self._client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
            except Exception:
                return False

    def list_models(self) -> list[str]:
        """Query installed model tags from Ollama."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags")
            if resp.status_code != 200:
                sanitized = sanitize_response_body(resp.text)
                err_msg = f"Ollama returned HTTP {resp.status_code} when listing models"
                if sanitized:
                    err_msg += f": {sanitized}"
                raise OllamaResponseError(
                    err_msg,
                    status_code=resp.status_code,
                    response_body=sanitized,
                    details={"status_code": resp.status_code, "response_body": sanitized},
                )
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", []) if "name" in m]
            return models
        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Could not connect to Ollama at {self.base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Timed out contacting Ollama at {self.base_url}: {e}") from e
        except json.JSONDecodeError as e:
            raise OllamaResponseError(f"Invalid JSON response from Ollama /api/tags: {e}") from e
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error querying Ollama models: {e}") from e

    def is_model_installed(self, model: str | None = None) -> bool:
        """Check if the given model (or configured model) is installed."""
        target = model or self.model_name
        models = self.list_models()
        # Match exact tag or base tag without :latest
        target_base = target.split(":")[0]
        return any(m == target or m.split(":")[0] == target_base for m in models)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        think: bool | None = None,
    ) -> dict[str, Any]:
        """Send chat completion request to Ollama /api/chat."""
        effective_think = self.think if think is None else think
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "think": effective_think,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.0,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            if resp.status_code == 404:
                sanitized = sanitize_response_body(resp.text)
                raise OllamaModelNotFoundError(
                    f"Model '{self.model_name}' not found on Ollama server at {self.base_url}. "
                    f"Run: ollama pull {self.model_name}"
                    + (f" ({sanitized})" if sanitized else ""),
                    details={
                        "model": self.model_name,
                        "status_code": 404,
                        "response_body": sanitized,
                    },
                )
            if resp.status_code != 200:
                sanitized = sanitize_response_body(resp.text)
                err_msg = f"Ollama chat request failed with HTTP {resp.status_code}"
                if sanitized:
                    err_msg += f": {sanitized}"
                raise OllamaResponseError(
                    err_msg,
                    status_code=resp.status_code,
                    response_body=sanitized,
                    details={"status_code": resp.status_code, "response_body": sanitized},
                )

            data = resp.json()
            if not isinstance(data, dict) or "message" not in data:
                raise OllamaResponseError(
                    "Ollama response missing 'message' field", details={"response": data}
                )
            return data
        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Could not connect to Ollama at {self.base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(
                f"Ollama chat request timed out after {self.timeout}s: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise OllamaResponseError(f"Invalid JSON returned by Ollama chat: {e}") from e
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error during Ollama chat: {e}") from e

    def parse_tool_calls(self, message: dict[str, Any]) -> list[ToolCall]:
        """Extract and validate tool calls from Ollama chat message."""
        raw_calls = message.get("tool_calls", [])
        if not raw_calls or not isinstance(raw_calls, list):
            return []

        calls: list[ToolCall] = []
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            fn = item.get("function")
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name or not isinstance(name, str):
                continue
            name = name.strip()
            if not name:
                continue
            args = fn.get("arguments")
            if args is None:
                args = {}
            elif isinstance(args, str):
                try:
                    parsed_args = json.loads(args)
                    args = parsed_args if isinstance(parsed_args, dict) else {}
                except Exception:
                    args = {}
            elif not isinstance(args, dict):
                args = {}

            call_id = item.get("id")
            if call_id is not None and not isinstance(call_id, str):
                call_id = str(call_id)

            calls.append(ToolCall(name=name, arguments=args, call_id=call_id))

        return calls

    def check_tool_capability(self) -> tuple[bool, str]:
        """Probe if the model produces valid structured tool calls."""
        probe_tools = [
            {
                "type": "function",
                "function": {
                    "name": "ping_test",
                    "description": "Respond to a ping request with a pong string",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                },
            }
        ]
        probe_messages = [
            {
                "role": "system",
                "content": "You are a test assistant. If asked to ping, ALWAYS call ping_test tool.",
            },
            {
                "role": "user",
                "content": "Ping with value 'hello'",
            },
        ]
        try:
            resp = self.chat(probe_messages, tools=probe_tools)
            message = resp.get("message", {})
            calls = self.parse_tool_calls(message)
            if calls and calls[0].name == "ping_test":
                return True, "Model natively produced valid tool call."
            # Fallback check
            return False, "Model did not emit a tool call in response to prompt."
        except Exception as e:
            return False, f"Capability probe failed: {e}"
