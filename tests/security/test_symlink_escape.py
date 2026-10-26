"""Security tests ensuring symlinks pointing outside workspace are rejected."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from patchpilot.errors import SymlinkEscapeError
from patchpilot.safety.paths import PathPolicy


def _try_create_symlink(src: Path, dst: Path, target_is_directory: bool = False) -> bool:
    """Attempt to create a symlink, returning False if OS permissions disallow it."""
    try:
        os.symlink(src, dst, target_is_directory=target_is_directory)
        return True
    except OSError:
        return False


@pytest.mark.security
def test_symlink_escaping_boundary_rejected(tmp_path: Path) -> None:
    """Ensure a direct symlink targeting a file outside the workspace is rejected with SymlinkEscapeError."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_target = tmp_path / "outside_secret.txt"
    outside_target.write_text("SUPER_SECRET_HOST_KEY", encoding="utf-8")

    symlink_path = ws_dir / "sneaky_link.txt"
    if not _try_create_symlink(outside_target, symlink_path):
        pytest.skip(
            "Symlink creation requires elevated permissions or developer mode on this Windows host."
        )

    policy = PathPolicy(ws_dir)
    with pytest.raises(SymlinkEscapeError):
        policy.sanitize_and_resolve("sneaky_link.txt")


@pytest.mark.security
def test_directory_symlink_escaping_boundary_rejected(tmp_path: Path) -> None:
    """Ensure an intermediate directory symlink targeting outside the workspace is rejected."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("HOST_SECRET", encoding="utf-8")

    symlink_dir = ws_dir / "ext_link"
    if not _try_create_symlink(outside_dir, symlink_dir, target_is_directory=True):
        pytest.skip(
            "Symlink creation requires elevated permissions or developer mode on this Windows host."
        )

    policy = PathPolicy(ws_dir)
    with pytest.raises(SymlinkEscapeError):
        policy.sanitize_and_resolve("ext_link/secret.txt")


@pytest.mark.security
def test_in_workspace_symlink_allowed(tmp_path: Path) -> None:
    """Ensure a legitimate symlink remaining inside the workspace is accepted."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    real_file = ws_dir / "real.txt"
    real_file.write_text("safe content", encoding="utf-8")

    symlink_file = ws_dir / "link_to_real.txt"
    if not _try_create_symlink(real_file, symlink_file):
        pytest.skip(
            "Symlink creation requires elevated permissions or developer mode on this Windows host."
        )

    policy = PathPolicy(ws_dir)
    resolved = policy.sanitize_and_resolve("link_to_real.txt", must_exist=True)
    assert resolved == real_file.resolve()


@pytest.mark.security
def test_in_workspace_directory_symlink_allowed(tmp_path: Path) -> None:
    """Ensure a legitimate directory symlink remaining inside the workspace is accepted."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    real_dir = ws_dir / "internal_dir"
    real_dir.mkdir()
    target_file = real_dir / "file.txt"
    target_file.write_text("safe inner content", encoding="utf-8")

    symlink_dir = ws_dir / "dir_link"
    if not _try_create_symlink(real_dir, symlink_dir, target_is_directory=True):
        pytest.skip(
            "Symlink creation requires elevated permissions or developer mode on this Windows host."
        )

    policy = PathPolicy(ws_dir)
    resolved = policy.sanitize_and_resolve("dir_link/file.txt", must_exist=True)
    assert resolved == target_file.resolve()


@pytest.mark.security
def test_symlink_escaping_boundary_detected_mocked(tmp_path: Path) -> None:
    """Ensure symlink escape detection is unit-verified even on hosts without OS symlink creation permissions."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    policy = PathPolicy(ws_dir)

    with (
        patch.object(Path, "is_symlink", autospec=True) as mock_is_symlink,
        patch.object(Path, "readlink", autospec=True) as mock_readlink,
    ):
        mock_is_symlink.side_effect = lambda self: self.name == "mock_link.txt"
        mock_readlink.side_effect = lambda self: Path("/outside/system/secret.txt")

        with pytest.raises(SymlinkEscapeError):
            policy.sanitize_and_resolve("mock_link.txt")
