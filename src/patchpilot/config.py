"""Configuration system for PatchPilot with strict validation and safe defaults."""

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from patchpilot.errors import ConfigError


class PatchPilotConfig(BaseModel):
    """Validated configuration for PatchPilot runtime."""

    # Model settings
    model_name: str = Field(default="qwen3.5:4b", description="Target Ollama model")
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama server endpoint"
    )
    request_timeout_seconds: int = Field(
        default=180, ge=5, le=600, description="Ollama API timeout in seconds"
    )
    ollama_think: bool = Field(
        default=False,
        description="Explicit Ollama thinking flag for chat requests (top-level think parameter)",
    )

    @property
    def think(self) -> bool:
        """Convenience property for ollama_think."""
        return self.ollama_think

    # Agent loop limits
    max_repair_attempts: int = Field(
        default=3, ge=1, le=10, description="Maximum self-healing attempts"
    )
    max_agent_steps: int = Field(
        default=12, ge=1, le=50, description="Maximum agent reasoning steps per attempt"
    )
    max_tool_calls: int = Field(
        default=24, ge=1, le=100, description="Total budget of tool calls allowed"
    )
    max_context_characters: int = Field(
        default=50000, ge=1000, le=200000, description="Maximum context window characters"
    )

    # Safety limits
    max_file_bytes: int = Field(
        default=200000, ge=1024, le=10000000, description="Maximum file size readable"
    )
    test_timeout_seconds: int = Field(
        default=120, ge=5, le=600, description="Test execution timeout in seconds"
    )
    max_command_output_characters: int = Field(
        default=20000, ge=500, le=100000, description="Maximum test output characters captured"
    )
    allow_host_execution: bool = Field(
        default=False,
        description="Unsafe opt-in to execute repository tests on host without Docker",
    )

    # Storage paths
    data_dir: Path = Field(
        default=Path(".patchpilot-data"), description="Directory storing runs, workspaces, and logs"
    )

    @model_validator(mode="before")
    @classmethod
    def handle_think_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "think" in data and "ollama_think" not in data:
            data["ollama_think"] = data.pop("think")
        return data

    @field_validator("ollama_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("ollama_base_url must start with http:// or https://")
        return v

    def to_redacted_dict(self) -> dict[str, Any]:
        """Return configuration dictionary safe for logging or console display."""
        d = self.model_dump()
        d["data_dir"] = str(self.data_dir)
        return d

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        env_prefix: str = "PATCHPILOT_",
    ) -> "PatchPilotConfig":
        """Load configuration from optional TOML file, overridden by environment variables."""
        data: dict[str, Any] = {}

        # 1. Search for TOML config
        search_paths = [config_path] if config_path else [Path(".patchpilot.toml")]

        for p in search_paths:
            if p.is_file():
                try:
                    with open(p, "rb") as f:
                        toml_data = tomllib.load(f)
                        # Flatten common sections if nested
                        if "model" in toml_data and isinstance(toml_data["model"], dict):
                            for k, v in toml_data["model"].items():
                                if k == "name":
                                    data["model_name"] = v
                                elif k in ("think", "ollama_think"):
                                    data["ollama_think"] = v
                                else:
                                    data[k] = v
                        if "agent" in toml_data and isinstance(toml_data["agent"], dict):
                            data.update(toml_data["agent"])
                        if "safety" in toml_data and isinstance(toml_data["safety"], dict):
                            data.update(toml_data["safety"])
                        if "storage" in toml_data and isinstance(toml_data["storage"], dict):
                            data.update(toml_data["storage"])
                    break
                except Exception as e:
                    raise ConfigError(f"Failed to parse TOML configuration from {p}: {e}") from e

        from collections.abc import Callable

        env_mappings: dict[str, tuple[str, Callable[[str], Any]]] = {
            f"{env_prefix}MODEL_NAME": ("model_name", str),
            f"{env_prefix}OLLAMA_BASE_URL": ("ollama_base_url", str),
            f"{env_prefix}REQUEST_TIMEOUT_SECONDS": ("request_timeout_seconds", int),
            f"{env_prefix}OLLAMA_THINK": (
                "ollama_think",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            f"{env_prefix}THINK": (
                "ollama_think",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            f"{env_prefix}MAX_REPAIR_ATTEMPTS": ("max_repair_attempts", int),
            f"{env_prefix}MAX_AGENT_STEPS": ("max_agent_steps", int),
            f"{env_prefix}MAX_TOOL_CALLS": ("max_tool_calls", int),
            f"{env_prefix}MAX_FILE_BYTES": ("max_file_bytes", int),
            f"{env_prefix}MAX_CONTEXT_CHARACTERS": ("max_context_characters", int),
            f"{env_prefix}TEST_TIMEOUT_SECONDS": ("test_timeout_seconds", int),
            f"{env_prefix}MAX_COMMAND_OUTPUT_CHARACTERS": ("max_command_output_characters", int),
            f"{env_prefix}ALLOW_HOST_EXECUTION": (
                "allow_host_execution",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            f"{env_prefix}DATA_DIR": ("data_dir", Path),
        }

        for env_var, (field_name, converter) in env_mappings.items():
            val = os.getenv(env_var)
            if val is not None:
                try:
                    data[field_name] = converter(val)
                except Exception as e:
                    raise ConfigError(
                        f"Invalid value for environment variable {env_var}='{val}': {e}"
                    ) from e

        try:
            return cls(**data)
        except Exception as e:
            raise ConfigError(f"Configuration validation failed: {e}") from e
