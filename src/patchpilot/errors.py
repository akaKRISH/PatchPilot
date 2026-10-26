"""Typed exception hierarchy for PatchPilot."""

from typing import Any


class PatchPilotError(Exception):
    """Base exception for all PatchPilot errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Configuration Errors
class ConfigError(PatchPilotError):
    """Raised when configuration validation or loading fails."""


# Ollama Client Errors
class OllamaError(PatchPilotError):
    """Base error for Ollama client interactions."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama server cannot be reached."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when the specified model is not installed in Ollama."""


class OllamaTimeoutError(OllamaError):
    """Raised when an Ollama request times out."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an HTTP error or an invalid/malformed response."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = details.copy() if details else {}
        if status_code is not None:
            merged["status_code"] = status_code
        if response_body is not None:
            merged["response_body"] = response_body
        super().__init__(message, details=merged)
        self.status_code = status_code
        self.response_body = response_body


# Safety Errors
class SafetyError(PatchPilotError):
    """Base error for safety policy violations."""


class PathTraversalError(SafetyError):
    """Raised when a path escapes the authorized workspace."""


class SymlinkEscapeError(SafetyError):
    """Raised when a symlink points outside the authorized workspace."""


class SecretAccessError(SafetyError):
    """Raised when an operation attempts to access sensitive files."""


class CommandPolicyError(SafetyError):
    """Raised when an unapproved command or argument is requested."""


class OriginalRepositoryModifiedError(SafetyError):
    """Raised if the original repository has been altered in violation of immutability rules."""


# Workspace Errors
class WorkspaceError(PatchPilotError):
    """Raised when disposable workspace creation, reset, or diffing fails."""


# Tool Errors
class ToolError(PatchPilotError):
    """Base error for tool execution."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered."""


class ToolArgumentError(ToolError):
    """Raised when tool arguments fail validation."""


class ToolExecutionError(ToolError):
    """Raised when tool execution encounters a runtime failure."""


class BudgetExceededError(ToolError):
    """Raised when tool call or agent step limits are exceeded."""


# Verification & Sandbox Errors
class VerificationError(PatchPilotError):
    """Raised when verification or test execution fails unexpectedly."""


class SandboxError(VerificationError):
    """Raised when container sandbox execution fails or is unavailable."""
