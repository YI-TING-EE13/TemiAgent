#!/usr/bin/env python3
"""Verify Hermes license identity against a pinned Git base and checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from bounded_process import BoundedProcessResult, run_bounded_command
except ImportError:
    from tools.bounded_process import BoundedProcessResult, run_bounded_command


class HermesLicenseVerificationError(RuntimeError):
    """Raised when the pinned Hermes license contract cannot be verified."""


@dataclass(frozen=True)
class HermesLicenseEvidence:
    """Machine-verifiable identity recorded for a pinned license file."""

    license_path: str
    license_sha256: str
    license_blob_sha: str
    base_commit: str


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HermesLicenseVerificationError(
            f"HERMES_LICENSE_CONTRACT_INVALID: cannot read {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_CONTRACT_INVALID: manifest must be an object"
        )
    return manifest


def _validated_license_contract(manifest: dict[str, Any]) -> tuple[str, str, str | None]:
    status = manifest.get("license_status")
    if status != "VERIFIED":
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_UNVERIFIED: manifest license_status is not VERIFIED; "
            "fetch and inspect the pinned base before recording license identity"
        )

    license_path = manifest.get("license_path")
    if (
        not isinstance(license_path, str)
        or not license_path
        or license_path.startswith("/")
        or ".." in PurePosixPath(license_path).parts
    ):
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_CONTRACT_INVALID: license_path must stay below the "
            "Hermes checkout"
        )

    license_sha256 = manifest.get("license_sha256")
    if not isinstance(license_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", license_sha256
    ):
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_CONTRACT_INVALID: verified license_sha256 is required"
        )

    license_blob_sha = manifest.get("license_blob_sha")
    if license_blob_sha is not None and (
        not isinstance(license_blob_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", license_blob_sha)
    ):
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_CONTRACT_INVALID: license_blob_sha is invalid"
        )
    return license_path, license_sha256, license_blob_sha


def _git_result(checkout: Path, *arguments: str) -> BoundedProcessResult:
    try:
        result = run_bounded_command(
            ["git", "-C", str(checkout), *arguments],
            timeout_seconds=10,
            kill_grace_seconds=1,
        )
    except (OSError, ValueError) as exc:
        raise HermesLicenseVerificationError(
            f"HERMES_LICENSE_GIT_FAILED: git {' '.join(arguments)}: {exc}"
        ) from exc
    if result.timed_out:
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_GIT_TIMEOUT: "
            f"git {' '.join(arguments)} exceeded 10s; owned process group cleaned"
        )
    if result.returncode != 0:
        detail = result.output.strip()
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_GIT_FAILED: "
            f"git {' '.join(arguments)} failed: {detail or 'unknown error'}"
        )
    return result


def verify_pinned_license(
    manifest_path: Path,
    checkout_path: Path,
    base_commit: str,
    *,
    require_worktree: bool = True,
) -> HermesLicenseEvidence:
    """Verify the declared license at the pinned base and optionally checkout."""

    manifest = _load_manifest(manifest_path)
    if manifest.get("base_commit") != base_commit:
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_CONTRACT_INVALID: requested base commit does not "
            "match manifest base_commit"
        )
    license_path, expected_sha256, expected_blob_sha = _validated_license_contract(
        manifest
    )
    license_ref = f"{base_commit}:{license_path}"
    blob_sha = _git_result(checkout_path, "rev-parse", license_ref).output.strip()
    license_bytes = _git_result(checkout_path, "cat-file", "blob", blob_sha).output_bytes
    actual_sha256 = hashlib.sha256(license_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_MISMATCH: pinned base LICENSE content does not "
            "match manifest license_sha256"
        )
    if expected_blob_sha is not None and blob_sha != expected_blob_sha:
        raise HermesLicenseVerificationError(
            "HERMES_LICENSE_MISMATCH: pinned base LICENSE blob does not "
            "match manifest license_blob_sha"
        )

    if require_worktree:
        checkout_root = checkout_path.resolve()
        worktree_license = checkout_path / PurePosixPath(license_path)
        if worktree_license.is_symlink() or not worktree_license.is_file():
            raise HermesLicenseVerificationError(
                "HERMES_LICENSE_MISMATCH: checked-out LICENSE path is absent "
                "or is not a regular file"
            )
        if not worktree_license.resolve().is_relative_to(checkout_root):
            raise HermesLicenseVerificationError(
                "HERMES_LICENSE_CONTRACT_INVALID: checked-out LICENSE escapes "
                "the Hermes checkout"
            )
        if hashlib.sha256(worktree_license.read_bytes()).hexdigest() != expected_sha256:
            raise HermesLicenseVerificationError(
                "HERMES_LICENSE_MISMATCH: checked-out LICENSE differs from "
                "the pinned base content"
            )

    return HermesLicenseEvidence(
        license_path=license_path,
        license_sha256=actual_sha256,
        license_blob_sha=blob_sha,
        base_commit=base_commit,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--base-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = verify_pinned_license(
            args.manifest,
            args.checkout,
            args.base_commit,
            require_worktree=not args.base_only,
        )
    except HermesLicenseVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    print(
        "hermes_license: PASS "
        f"(base={evidence.base_commit} path={evidence.license_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
