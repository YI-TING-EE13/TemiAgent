"""Focused publication and external-source bootstrap contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_LAN_DEFAULT = ".".join(("192", "168", "50", "236"))


class ExternalDependencyPublicationTests(unittest.TestCase):
    def test_private_lan_defaults_are_not_tracked(self) -> None:
        legacy_scripts = (
            ROOT / "tools" / "start_temi_pc_services.sh",
            ROOT / "tools" / "start_temi_pc_services_background.sh",
        )
        adapter = ROOT / "tools" / "temi_overview_adapter.py"

        for path in (*legacy_scripts, adapter):
            self.assertNotIn(PRIVATE_LAN_DEFAULT, path.read_text(encoding="utf-8"))
        for path in legacy_scripts:
            self.assertIn(": \"${PC_IP:?", path.read_text(encoding="utf-8"))
        adapter_text = adapter.read_text(encoding="utf-8")
        self.assertIn("os.environ.get(\"TEMI_MQTT_BROKER\")", adapter_text)
        self.assertIn("set --broker or TEMI_MQTT_BROKER", adapter_text)

    def test_llama_manifest_declares_verified_license(self) -> None:
        manifest = json.loads(
            (ROOT / "third_party" / "llama_cpp" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(manifest["license_path"], "LICENSE")
        self.assertEqual(manifest["license_spdx"], "MIT")
        self.assertEqual(
            manifest["license_sha256"],
            "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d",
        )

    def test_hermes_manifest_records_formal_submodule_contract(self) -> None:
        manifest = json.loads(
            (ROOT / "third_party" / "hermes" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            manifest["contract_semantics"],
            "PINNED_BASE_PLUS_PATCHED_WORKTREE",
        )
        self.assertEqual(
            manifest["upstream_url"],
            "https://github.com/NousResearch/hermes-agent.git",
        )
        self.assertEqual(
            manifest["team_remote"],
            "https://github.com/YI-TING-EE13/hermes-agent.git",
        )
        self.assertEqual(manifest["submodule_path"], "hermes-agent")
        self.assertEqual(manifest["submodule_url"], manifest["team_remote"])
        self.assertEqual(
            manifest["base_commit"],
            "a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2",
        )
        self.assertEqual(
            manifest["expected_base_tree"],
            "bda69c575e65725bf9264dd1288a63093cea3cc3",
        )
        self.assertEqual(manifest["license_path"], "LICENSE")
        self.assertEqual(manifest["license_status"], "VERIFIED")
        self.assertEqual(manifest["license_identifier"], "MIT")
        self.assertEqual(
            manifest["copyright"], "Copyright (c) 2025 Nous Research"
        )
        self.assertEqual(manifest["patch_count"], 9)
        self.assertEqual(
            manifest["target_tree_sha"],
            "968f1668a05fafd09461c17a835198421f14a48f",
        )


if __name__ == "__main__":
    unittest.main()
