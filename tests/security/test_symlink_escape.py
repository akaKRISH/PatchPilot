"""Security tests ensuring symlinks pointing outside workspace are rejected."""

import os
from pathlib import Path

import pytest

from patchpilot.errors import SymlinkEscapeError
from patchpilot.safety.paths import PathPolicy


@pytest.mark.security
def test_symlink_escaping_boundary_rejected(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_target = tmp_path / "outside_secret.txt"
    outside_target.write_text("SUPER_SECRET_HOST_KEY", encoding="utf-8")

    symlink_path = ws_dir / "sneaky_link.txt"
    try:
        os.symlink(outside_target, symlink_path)
    except OSError:
        pytest.skip(
            "Symlink creation requires elevated permissions or developer mode on this Windows host."
        )

    policy = PathPolicy(ws_dir)
    with pytest.raises(SymlinkEscapeError):
        policy.sanitize_and_resolve("sneaky_link.txt")
