"""Cryptographic manifest computation and integrity verification."""

import hashlib
from pathlib import Path

from patchpilot.safety.paths import PathPolicy
from patchpilot.schemas import ManifestEntry, RepositoryManifest


def hash_file_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_repository_manifest(root_dir: Path, policy: PathPolicy) -> RepositoryManifest:
    """Traverse root_dir and calculate SHA-256 hashes for all non-excluded files."""
    root_dir = root_dir.resolve()
    entries: dict[str, ManifestEntry] = {}

    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue

        # Skip if within excluded patterns or is secret
        if policy.is_secret_or_excluded(path):
            continue

        try:
            rel_path = str(path.relative_to(root_dir)).replace("\\", "/")
            sha256_hash = hash_file_sha256(path)
            size_bytes = path.stat().st_size
            entries[rel_path] = ManifestEntry(
                relative_path=rel_path,
                sha256=sha256_hash,
                size_bytes=size_bytes,
            )
        except Exception:
            continue

    return RepositoryManifest(root_path=str(root_dir), entries=entries)


def verify_manifest_integrity(
    original_manifest: RepositoryManifest, current_dir: Path, policy: PathPolicy
) -> tuple[bool, list[str]]:
    """Compare the original manifest against the current directory state.

    Returns:
        (is_identical, list_of_violations)
    """
    current_manifest = compute_repository_manifest(current_dir, policy)
    added, modified, deleted = original_manifest.compute_diff(current_manifest)

    violations: list[str] = []
    for f in added:
        violations.append(f"Unexpected file created in original repository: {f}")
    for f in modified:
        violations.append(f"Unexpected modification in original repository: {f}")
    for f in deleted:
        violations.append(f"Unexpected file deleted from original repository: {f}")

    return len(violations) == 0, violations
