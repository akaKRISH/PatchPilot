"""Unit tests for path safety and containment policies."""

from pathlib import Path

import pytest

from patchpilot.errors import PathTraversalError, SecretAccessError
from patchpilot.safety.paths import PathPolicy


def test_valid_path_resolution(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    file_path = tmp_path / "valid.txt"
    file_path.write_text("ok", encoding="utf-8")

    resolved = policy.sanitize_and_resolve("valid.txt", must_exist=True)
    assert resolved == file_path.resolve()


def test_directory_traversal_rejected(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    with pytest.raises(PathTraversalError):
        policy.sanitize_and_resolve("../outside.txt")


def test_absolute_path_escape_rejected(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    outside_file = tmp_path.parent / "escape.txt"
    with pytest.raises(PathTraversalError):
        policy.sanitize_and_resolve(str(outside_file))


def test_secret_access_rejected(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=123", encoding="utf-8")
    with pytest.raises(SecretAccessError):
        policy.sanitize_and_resolve(".env")


def test_private_key_rejected(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    key_file = tmp_path / "server.key"
    key_file.write_text("dummy", encoding="utf-8")
    with pytest.raises(SecretAccessError):
        policy.sanitize_and_resolve("server.key")
