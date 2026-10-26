"""Centralized path safety validation preventing directory traversal, escapes, and secret leaks."""

import os
from pathlib import Path

from patchpilot.errors import PathTraversalError, SecretAccessError, SymlinkEscapeError

# Patterns and names of files that should never be copied, read, or modified by agent
EXCLUDED_PATTERNS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SECRET_EXTENSIONS = {
    ".pem",
    ".key",
    ".pkcs12",
    ".pfx",
    ".p12",
}

SECRET_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
    ".git-credentials",
}


class PathPolicy:
    """Enforces strict path containment inside an authorized root directory."""

    def __init__(self, root_dir: Path, max_file_bytes: int = 200_000) -> None:
        self.root_dir = root_dir.resolve()
        self.max_file_bytes = max_file_bytes

    def is_secret_or_excluded(self, path: Path) -> bool:
        """Check if path targets a known secret or excluded directory."""
        parts = [p.lower() for p in path.parts]
        name = path.name.lower()

        # Check directory/part exclusion
        for part in parts:
            if part in EXCLUDED_PATTERNS:
                return True

        # Check filename
        if name in SECRET_FILENAMES or name.startswith(".env"):
            return True

        # Check extension
        return path.suffix.lower() in SECRET_EXTENSIONS

    def sanitize_and_resolve(self, candidate_path: str | Path, must_exist: bool = False) -> Path:
        """Resolve candidate path and verify it remains strictly inside root_dir.

        Raises:
            PathTraversalError: If path attempts to escape root_dir.
            SymlinkEscapeError: If path traverses a symlink targeting outside root_dir.
            SecretAccessError: If path targets a secret or protected file.
        """
        raw_str = str(candidate_path)
        if "\0" in raw_str:
            raise PathTraversalError("Null byte detected in file path.")

        # If candidate is absolute, ensure it starts with root_dir
        candidate = Path(candidate_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            # Prevent simple '..' traversal in path string before join
            norm = os.path.normpath(raw_str)
            if norm.startswith("..") or ("../" in raw_str) or ("..\\" in raw_str):
                raise PathTraversalError(
                    f"Directory traversal ('..') detected in path: '{raw_str}'"
                )
            resolved = (self.root_dir / candidate).resolve()

        # Check boundary containment
        try:
            resolved.relative_to(self.root_dir)
        except ValueError as e:
            raise PathTraversalError(
                f"Path '{candidate_path}' resolves to '{resolved}', which is outside root '{self.root_dir}'"
            ) from e

        # Check for symlink escaping boundary
        if resolved.is_symlink():
            target = resolved.readlink()
            if not target.is_absolute():
                target = (resolved.parent / target).resolve()
            else:
                target = target.resolve()
            try:
                target.relative_to(self.root_dir)
            except ValueError as e:
                raise SymlinkEscapeError(
                    f"Symlink '{resolved}' targets '{target}' outside root '{self.root_dir}'"
                ) from e

        # Check for secret access
        if self.is_secret_or_excluded(resolved):
            raise SecretAccessError(
                f"Access to sensitive or excluded file '{resolved.name}' is prohibited."
            )

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"File not found: '{candidate_path}'")

        return resolved

    def validate_file_size(self, path: Path) -> None:
        """Verify file does not exceed maximum allowable size."""
        if path.is_file():
            size = path.stat().st_size
            if size > self.max_file_bytes:
                raise SecretAccessError(
                    f"File '{path.name}' size ({size} bytes) exceeds safety limit ({self.max_file_bytes} bytes)."
                )
