"""No-network tests for the formal Hermes submodule contract."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools.verify_hermes_license import (
    HermesLicenseVerificationError,
    verify_pinned_license,
)
from tools.verify_hermes_submodule import (
    AUTHORIZED_BASE_COMMIT,
    AUTHORIZED_BASE_TREE,
    AUTHORIZED_FINAL_TREE,
    AUTHORIZED_TEAM_REMOTE,
    HermesSubmoduleVerificationError,
    SubmoduleVerificationState,
    validate_manifest,
    validate_patch_contract,
    validate_submodule_state,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "third_party" / "hermes" / "manifest.json"


def load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def pinned_base_state(**changes: object) -> SubmoduleVerificationState:
    state = SubmoduleVerificationState(
        configured_path="hermes-agent",
        configured_url=AUTHORIZED_TEAM_REMOTE,
        configured_branch=None,
        root_gitlink=AUTHORIZED_BASE_COMMIT,
        checkout_present=True,
        checkout_origin=AUTHORIZED_TEAM_REMOTE,
        checkout_commit=AUTHORIZED_BASE_COMMIT,
        base_object_available=True,
        actual_base_tree=AUTHORIZED_BASE_TREE,
        checkout_tree=AUTHORIZED_BASE_TREE,
        base_is_ancestor=True,
        checkout_dirty=False,
        alternates_present=False,
    )
    return replace(state, **changes)


class HermesSubmoduleContractTests(unittest.TestCase):
    def test_gitmodules_records_one_pinned_team_submodule(self) -> None:
        gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")
        self.assertIn('[submodule "hermes-agent"]', gitmodules)
        self.assertIn("\tpath = hermes-agent", gitmodules)
        self.assertIn(f"\turl = {AUTHORIZED_TEAM_REMOTE}", gitmodules)
        self.assertNotIn("branch =", gitmodules)

        result = subprocess.run(
            ["git", "ls-files", "--stage", "--", "hermes-agent"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertRegex(
            result.stdout,
            rf"^160000 {AUTHORIZED_BASE_COMMIT} 0\thermes-agent$",
        )

    def test_pinned_base_state_passes(self) -> None:
        self.assertEqual(
            validate_submodule_state(load_manifest(), pinned_base_state()),
            "BASE",
        )

    def test_wrong_remote_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "REMOTE_MISMATCH"
        ):
            validate_submodule_state(
                load_manifest(),
                pinned_base_state(configured_url="https://example.invalid/hermes.git"),
            )

    def test_wrong_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(HermesSubmoduleVerificationError, "PATH_MISMATCH"):
            validate_submodule_state(
                load_manifest(), pinned_base_state(configured_path="other-hermes")
            )

    def test_floating_branch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "FLOATING_BRANCH"
        ):
            validate_submodule_state(
                load_manifest(), pinned_base_state(configured_branch="main")
            )

    def test_wrong_base_tree_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "BASE_TREE_MISMATCH"
        ):
            validate_submodule_state(
                load_manifest(), pinned_base_state(actual_base_tree="0" * 40)
            )

    def test_missing_submodule_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "UNINITIALIZED"
        ):
            validate_submodule_state(
                load_manifest(), pinned_base_state(checkout_present=False)
            )

    def test_wrong_submodule_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(HermesSubmoduleVerificationError, "PIN_MISMATCH"):
            validate_submodule_state(
                load_manifest(), pinned_base_state(checkout_commit="1" * 40)
            )

    def test_wrong_final_tree_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "FINAL_TREE_MISMATCH"
        ):
            validate_submodule_state(
                load_manifest(),
                pinned_base_state(
                    checkout_commit="2" * 40,
                    checkout_tree="3" * 40,
                    base_is_ancestor=True,
                ),
            )

    def test_alternates_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "ALTERNATES_FORBIDDEN"
        ):
            validate_submodule_state(
                load_manifest(), pinned_base_state(alternates_present=True)
            )

    def test_patch_hash_mismatch_is_rejected(self) -> None:
        manifest = load_manifest()
        manifest["patches"] = copy.deepcopy(manifest["patches"])
        manifest["patches"][0]["sha256"] = "0" * 64  # type: ignore[index]
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "PATCH_HASH_MISMATCH"
        ):
            validate_patch_contract(ROOT, manifest)

    def test_wrong_final_manifest_identity_is_rejected(self) -> None:
        manifest = load_manifest()
        manifest["target_tree_sha"] = "0" * 40
        with self.assertRaisesRegex(
            HermesSubmoduleVerificationError, "expected final tree mismatch"
        ):
            validate_manifest(manifest)

    def test_license_mismatch_is_rejected(self) -> None:
        manifest = load_manifest()
        checkout = ROOT / "hermes-agent"
        manifest["license_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-contract-") as temp:
            manifest_path = Path(temp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(
                HermesLicenseVerificationError, "MISMATCH"
            ):
                verify_pinned_license(
                    manifest_path,
                    checkout,
                    AUTHORIZED_BASE_COMMIT,
                )

    def test_bootstrap_has_no_clone_fetch_file_url_or_alternate_fallback(self) -> None:
        bootstrap = (ROOT / "scripts" / "bootstrap_hermes.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("git clone", bootstrap)
        self.assertNotIn("git fetch", bootstrap)
        self.assertNotIn("file://", bootstrap)
        self.assertNotIn("--reference", bootstrap)
        self.assertNotIn("GIT_ALTERNATE_OBJECT_DIRECTORIES", bootstrap)
        self.assertNotIn("NousResearch", bootstrap)

    def test_reconstructed_tree_identity_is_the_authoritative_value(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["target_tree_sha"], AUTHORIZED_FINAL_TREE)


if __name__ == "__main__":
    unittest.main()
