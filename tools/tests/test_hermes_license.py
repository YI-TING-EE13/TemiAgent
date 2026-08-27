"""No-network tests for pinned Hermes license verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.verify_hermes_license import (
    HermesLicenseVerificationError,
    verify_pinned_license,
)


def git(checkout: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def create_repo(tmp: Path, license_content: bytes | None) -> tuple[Path, str]:
    checkout = tmp / "hermes"
    checkout.mkdir()
    git(checkout, "init", "--quiet")
    git(checkout, "config", "user.email", "tests@example.invalid")
    git(checkout, "config", "user.name", "Tests")
    if license_content is not None:
        (checkout / "LICENSE").write_bytes(license_content)
    (checkout / "README").write_text("fixture\n", encoding="utf-8")
    git(checkout, "add", ".")
    git(checkout, "commit", "--quiet", "-m", "fixture")
    return checkout, git(checkout, "rev-parse", "HEAD")


def write_manifest(
    path: Path,
    *,
    base_commit: str,
    status: str = "VERIFIED",
    license_sha256: str | None = None,
) -> None:
    manifest = {
        "base_commit": base_commit,
        "license_path": "LICENSE",
        "license_status": status,
    }
    if license_sha256 is not None:
        manifest["license_sha256"] = license_sha256
    path.write_text(json.dumps(manifest), encoding="utf-8")


class HermesLicenseTests(unittest.TestCase):
    def test_correct_pinned_license_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-license-") as temp:
            checkout, base_commit = create_repo(Path(temp), b"MIT fixture\n")
            manifest = Path(temp) / "manifest.json"
            digest = hashlib.sha256(b"MIT fixture\n").hexdigest()
            write_manifest(
                manifest,
                base_commit=base_commit,
                license_sha256=digest,
            )

            evidence = verify_pinned_license(manifest, checkout, base_commit)

            self.assertEqual(evidence.license_sha256, digest)

    def test_missing_license_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-license-") as temp:
            checkout, base_commit = create_repo(Path(temp), None)
            manifest = Path(temp) / "manifest.json"
            write_manifest(
                manifest,
                base_commit=base_commit,
                license_sha256="0" * 64,
            )

            with self.assertRaisesRegex(HermesLicenseVerificationError, "GIT_FAILED"):
                verify_pinned_license(manifest, checkout, base_commit)

    def test_wrong_license_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-license-") as temp:
            checkout, base_commit = create_repo(Path(temp), b"MIT fixture\n")
            manifest = Path(temp) / "manifest.json"
            write_manifest(
                manifest,
                base_commit=base_commit,
                license_sha256="0" * 64,
            )

            with self.assertRaisesRegex(HermesLicenseVerificationError, "MISMATCH"):
                verify_pinned_license(manifest, checkout, base_commit)

    def test_wrong_checkout_revision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-license-") as temp:
            checkout, base_commit = create_repo(Path(temp), b"MIT fixture\n")
            manifest = Path(temp) / "manifest.json"
            digest = hashlib.sha256(b"MIT fixture\n").hexdigest()
            write_manifest(
                manifest,
                base_commit=base_commit,
                license_sha256=digest,
            )
            (checkout / "LICENSE").write_bytes(b"wrong revision\n")
            git(checkout, "add", "LICENSE")
            git(checkout, "commit", "--quiet", "-m", "wrong revision")

            with self.assertRaisesRegex(HermesLicenseVerificationError, "differs"):
                verify_pinned_license(manifest, checkout, base_commit)

    def test_unverified_manifest_cannot_report_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-license-") as temp:
            checkout, base_commit = create_repo(Path(temp), b"MIT fixture\n")
            manifest = Path(temp) / "manifest.json"
            write_manifest(
                manifest,
                base_commit=base_commit,
                status="UNVERIFIED_PENDING_PUBLIC_FETCH",
            )

            with self.assertRaisesRegex(
                HermesLicenseVerificationError, "HERMES_LICENSE_UNVERIFIED"
            ):
                verify_pinned_license(manifest, checkout, base_commit)


if __name__ == "__main__":
    unittest.main()
