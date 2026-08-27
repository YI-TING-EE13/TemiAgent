"""Focused publication and external-source bootstrap contract tests."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
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

    def test_hermes_manifest_records_contract_without_unverified_tree(self) -> None:
        manifest = json.loads(
            (ROOT / "third_party" / "hermes" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            manifest["contract_semantics"],
            "PINNED_BASE_PLUS_PATCHED_WORKTREE",
        )
        self.assertNotIn("expected_base_tree", manifest)

    def test_hermes_rate_limit_retry_is_bounded_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-rate-limit-") as temp_dir:
            fixture = Path(temp_dir) / "fixture"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / "third_party").mkdir()
            shutil.copy2(
                ROOT / "scripts" / "bootstrap_hermes.sh",
                fixture / "scripts" / "bootstrap_hermes.sh",
            )
            shutil.copytree(
                ROOT / "third_party" / "hermes",
                fixture / "third_party" / "hermes",
            )

            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            fetch_log = Path(temp_dir) / "fetch.log"
            real_git = shutil.which("git")
            self.assertIsNotNone(real_git)
            git_command = shlex.quote(real_git or "git")
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = \"-C\" ] && [ \"${3:-}\" = \"fetch\" ]; then\n"
                "  printf \"fetch\\n\" >> \"$FAKE_GIT_FETCH_LOG\"\n"
                "  printf \"remote: HTTP 429 Too Many Requests\\n\" >&2\n"
                "  exit 128\n"
                "fi\n"
                f"exec {git_command} \"$@\"\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)

            env = os.environ.copy()
            env_path = env.get("PATH", "")
            env["PATH"] = f"{fake_bin}:{env_path}"
            env["FAKE_GIT_FETCH_LOG"] = str(fetch_log)
            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap_hermes.sh"), "--bootstrap"],
                cwd=fixture,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            combined_output = f"{result.stdout}\n{result.stderr}"
            self.assertIn("PUBLIC_UPSTREAM_RATE_LIMITED", combined_output)
            self.assertIn("no local fallback was used", combined_output)
            self.assertEqual(fetch_log.read_text(encoding="utf-8").splitlines(), ["fetch", "fetch"])

            runtime = fixture / "hermes-agent"
            self.assertTrue((runtime / ".git").exists())
            origin = subprocess.run(
                [real_git or "git", "-C", str(runtime), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                origin.stdout.strip(),
                "https://github.com/NousResearch/hermes-agent.git",
            )


if __name__ == "__main__":
    unittest.main()
