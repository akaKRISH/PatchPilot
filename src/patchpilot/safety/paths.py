"""Centralized path safety validation preventing directory traversal, escapes, and secret leaks."""

import os
from pathlib import Path, PureWindowsPath

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


def _normalize_extended_path(p: Path) -> Path:
    """Normalize Windows extended-length path prefix (\\?\\) so containment checks match."""
    s = str(p)
    if s.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + s[8:])
    if s.startswith("\\\\?\\"):
        return Path(s[4:])
    return p


class PathPolicy:
    """Enforces strict path containment inside an authorized root directory."""

    def __init__(self, root_dir: Path, max_file_bytes: int = 200_000) -> None:
        self.root_dir = _normalize_extended_path(root_dir.resolve())
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
            PathTraversalError: If path attempts to escape root_dir or uses foreign absolute forms.
            SymlinkEscapeError: If path traverses a symlink targeting outside root_dir.
            SecretAccessError: If path targets a secret or protected file.
            FileNotFoundError: If must_exist is True and the target does not exist.
        """
        raw_str = str(candidate_path)
        if "\0" in raw_str:
            raise PathTraversalError("Null byte detected in file path.")

        # 1. Directory traversal components check across all separator styles (/ and \)
        # PureWindowsPath parses both forward slash and backslash on all platforms.
        win_pure = PureWindowsPath(raw_str)
        if ".." in win_pure.parts:
            raise PathTraversalError(f"Directory traversal ('..') detected in path: '{raw_str}'")

        # 2. Foreign-platform absolute and drive-qualified forms
        # On POSIX, a Windows drive-qualified path (e.g. C:\...) or UNC path (\\...)
        # is not considered absolute by native pathlib.Path and would otherwise be treated
        # as a relative file inside workspace.
        if os.name != "nt" and (
            win_pure.is_absolute() or win_pure.drive or raw_str.startswith("\\\\")
        ):
            raise PathTraversalError(
                f"Windows drive-qualified or absolute path outside workspace: '{raw_str}'"
            )

        # UNC or network share paths (e.g. \\server\share or //server/share)
        if raw_str.startswith(("\\\\", "//")):
            raise PathTraversalError(f"UNC or network path not permitted: '{raw_str}'")

        # Drive check on Windows: reject drives different from root_dir
        if (
            os.name == "nt"
            and win_pure.drive
            and self.root_dir.drive
            and win_pure.drive.lower() != self.root_dir.drive.lower()
        ):
            raise PathTraversalError(
                f"Path on drive '{win_pure.drive}' is outside workspace root '{self.root_dir}'"
            )

        # 3. Determine if candidate is an absolute path or relative path
        candidate = Path(candidate_path)

        # Check if candidate path is absolute on the current platform, or root-relative on Windows (e.g. /etc/passwd or \Windows)
        if candidate.is_absolute() or (os.name == "nt" and raw_str.startswith(("/", "\\"))):
            norm_candidate = _normalize_extended_path(candidate)
            try:
                if not norm_candidate.is_relative_to(self.root_dir):
                    raise PathTraversalError(
                        f"Absolute path '{candidate_path}' is outside root '{self.root_dir}'"
                    )
                rel_candidate = norm_candidate.relative_to(self.root_dir)
            except ValueError as e:
                raise PathTraversalError(
                    f"Path '{candidate_path}' is outside root '{self.root_dir}'"
                ) from e
        else:
            # Candidate is a relative path
            rel_candidate = candidate

        # 4. Check for symlink escapes component by component before resolving
        current = self.root_dir
        for part in rel_candidate.parts:
            current = current / part
            if current.is_symlink():
                target = current.readlink()
                if not target.is_absolute():
                    resolved_target = (current.parent / target).resolve()
                else:
                    resolved_target = target.resolve()

                resolved_target = _normalize_extended_path(resolved_target)

                try:
                    if not resolved_target.is_relative_to(self.root_dir):
                        raise SymlinkEscapeError(
                            f"Symlink '{current}' targets '{resolved_target}' outside root '{self.root_dir}'"
                        )
                except ValueError as e:
                    raise SymlinkEscapeError(
                        f"Symlink '{current}' targets '{resolved_target}' outside root '{self.root_dir}'"
                    ) from e

                # Symlink stays inside workspace; update current to the resolved target so
                # any subsequent path components are evaluated from the target.
                current = resolved_target

        # 5. Canonical resolution & final root containment check
        resolved = _normalize_extended_path(current.resolve())
        try:
            if not resolved.is_relative_to(self.root_dir):
                raise PathTraversalError(
                    f"Path '{candidate_path}' resolves to '{resolved}', which is outside root '{self.root_dir}'"
                )
        except ValueError as e:
            raise PathTraversalError(
                f"Path '{candidate_path}' resolves to '{resolved}', which is outside root '{self.root_dir}'"
            ) from e

        # 6. Check for secret or excluded files
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
