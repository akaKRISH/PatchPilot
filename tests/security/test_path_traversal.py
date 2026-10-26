"""Security tests verifying defense against path traversal attacks."""

from pathlib import Path

import pytest

from patchpilot.errors import PathTraversalError
from patchpilot.safety.paths import PathPolicy

TRAVERSAL_PAYLOADS = [
    # Standard POSIX relative traversal
    "../outside.txt",
    "../../outside.txt",
    "..",
    "foo/../../outside.txt",
    "nested/../../secret",
    # Windows relative traversal with backslashes
    "..\\outside.txt",
    "..\\..\\outside.txt",
    "foo\\..\\outside.txt",
    "foo\\..\\..\\outside.txt",
    # Mixed separator traversal
    "foo/..\\outside.txt",
    "foo\\../outside.txt",
    "nested/..\\../secret",
    "nested\\../../secret",
    # POSIX absolute paths outside authorized workspace
    "/etc/passwd",
    "/var/log/syslog",
    # Windows drive-qualified absolute paths
    "C:\\Windows\\System32\\cmd.exe",
    "C:/Windows/System32/cmd.exe",
    "D:\\outside\\secret.txt",
    "D:/outside/secret.txt",
    # UNC and network share paths
    "\\\\server\\share\\secret.txt",
    "//server/share/secret.txt",
]


@pytest.mark.security
@pytest.mark.parametrize("payload", TRAVERSAL_PAYLOADS)
def test_path_traversal_payloads_rejected(tmp_path: Path, payload: str) -> None:
    """Ensure every traversal payload is rejected independently with PathTraversalError."""
    policy = PathPolicy(tmp_path)
    with pytest.raises(PathTraversalError):
        policy.sanitize_and_resolve(payload)


@pytest.mark.security
@pytest.mark.parametrize(
    "valid_filename",
    [
        "archive.tar.gz",
        "my..file.py",
        "module..name.txt",
        "nested/sub..dir/file..test.py",
        "config.local.json",
    ],
)
def test_legitimate_paths_with_multiple_dots_allowed(tmp_path: Path, valid_filename: str) -> None:
    """Ensure filenames containing multiple dots are not falsely identified as traversal."""
    policy = PathPolicy(tmp_path)
    # File does not need to exist when must_exist=False
    resolved = policy.sanitize_and_resolve(valid_filename, must_exist=False)
    assert resolved.is_relative_to(tmp_path.resolve())


@pytest.mark.security
def test_null_byte_path_injection(tmp_path: Path) -> None:
    """Ensure null byte injections are immediately rejected."""
    policy = PathPolicy(tmp_path)
    with pytest.raises(PathTraversalError):
        policy.sanitize_and_resolve("valid.py\0malicious")
