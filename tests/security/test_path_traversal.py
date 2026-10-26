"""Security tests verifying defense against path traversal attacks."""

from pathlib import Path

import pytest

from patchpilot.errors import PathTraversalError
from patchpilot.safety.paths import PathPolicy


@pytest.mark.security
def test_relative_path_traversal_attempts(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)

    traversal_payloads = [
        "../outside.txt",
        "..\\outside.txt",
        "foo/../../outside.txt",
        "nested/../../secret",
        "..",
        "/etc/passwd",
        "C:\\Windows\\System32\\cmd.exe",
    ]

    for payload in traversal_payloads:
        with pytest.raises(PathTraversalError):
            policy.sanitize_and_resolve(payload)


@pytest.mark.security
def test_null_byte_path_injection(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    with pytest.raises(PathTraversalError):
        policy.sanitize_and_resolve("valid.py\0malicious")
