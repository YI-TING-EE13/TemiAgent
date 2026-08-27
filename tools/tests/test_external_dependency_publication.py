"""Focused publication and external-source bootstrap contract tests."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_LAN_DEFAULT = ".".join(("192", "168", "50", "236"))


def wait_for_pid_to_exit(pid: int, timeout_seconds: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not Path(f"/proc/{pid}").exists():
            return True
        time.sleep(0.02)
    return not Path(f"/proc/{pid}").exists()


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
        self.assertEqual(manifest["license_path"], "LICENSE")
        self.assertEqual(
            manifest["license_status"],
            "UNVERIFIED_PENDING_PUBLIC_FETCH",
        )
        self.assertNotIn("license_sha256", manifest)
        self.assertNotIn("expected_base_tree", manifest)

    def test_hermes_rate_limit_retry_is_bounded_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-rate-limit-") as temp_dir:
            fixture = Path(temp_dir) / "fixture"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / "third_party").mkdir()
            (fixture / "tools").mkdir()
            shutil.copy2(
                ROOT / "scripts" / "bootstrap_hermes.sh",
                fixture / "scripts" / "bootstrap_hermes.sh",
            )
            for helper in (
                "bounded_process.py",
                "run_bounded_process.py",
                "verify_hermes_license.py",
            ):
                shutil.copy2(ROOT / "tools" / helper, fixture / "tools" / helper)
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

    def test_hermes_timeout_kills_owned_tree_and_is_resumable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-hermes-timeout-") as temp_dir:
            fixture = Path(temp_dir) / "fixture"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / "third_party").mkdir()
            (fixture / "tools").mkdir()
            bootstrap = fixture / "scripts" / "bootstrap_hermes.sh"
            shutil.copy2(ROOT / "scripts" / "bootstrap_hermes.sh", bootstrap)
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8")
                .replace("FETCH_TIMEOUT_SECONDS=20", "FETCH_TIMEOUT_SECONDS=0.2")
                .replace("FETCH_KILL_GRACE_SECONDS=2", "FETCH_KILL_GRACE_SECONDS=0.1"),
                encoding="utf-8",
            )
            for helper in (
                "bounded_process.py",
                "run_bounded_process.py",
                "verify_hermes_license.py",
            ):
                shutil.copy2(ROOT / "tools" / helper, fixture / "tools" / helper)
            shutil.copytree(
                ROOT / "third_party" / "hermes",
                fixture / "third_party" / "hermes",
            )

            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            fetch_log = Path(temp_dir) / "fetch.log"
            child_pid_path = Path(temp_dir) / "child.pid"
            real_git = shutil.which("git")
            self.assertIsNotNone(real_git)
            git_command = shlex.quote(real_git or "git")
            python_command = shlex.quote(sys.executable)
            resistant_git_source = (
                "import signal\n"
                "import subprocess\n"
                "import sys\n"
                "import time\n"
                "child = subprocess.Popen([\n"
                "    sys.executable, '-c',\n"
                "    'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)',\n"
                "])\n"
                "with open(sys.argv[1], 'w', encoding='ascii') as handle:\n"
                "    handle.write(str(child.pid))\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "while True:\n"
                "    time.sleep(1)\n"
            )
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                'if [ "${1:-}" = "-C" ] && [ "${3:-}" = "fetch" ]; then\n'
                '  printf "fetch\\n" >> "$FAKE_GIT_FETCH_LOG"\n'
                f"  exec {python_command} -c {shlex.quote(resistant_git_source)} "
                '"$FAKE_GIT_CHILD_PID_FILE"\n'
                "fi\n"
                f"exec {git_command} \"$@\"\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
            env["FAKE_GIT_FETCH_LOG"] = str(fetch_log)
            env["FAKE_GIT_CHILD_PID_FILE"] = str(child_pid_path)
            result = subprocess.run(
                ["bash", str(bootstrap), "--bootstrap"],
                cwd=fixture,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 3)
            combined_output = f"{result.stdout}\n{result.stderr}"
            self.assertIn("PUBLIC_UPSTREAM_TIMEOUT", combined_output)
            self.assertIn("HERMES_FETCH_PROCESS_HARD_KILL", combined_output)
            self.assertIn("no local fallback was used", combined_output)
            self.assertEqual(fetch_log.read_text(encoding="utf-8").splitlines(), ["fetch", "fetch"])
            self.assertTrue(child_pid_path.exists())
            self.assertTrue(
                wait_for_pid_to_exit(
                    int(child_pid_path.read_text(encoding="ascii"))
                )
            )
            self.assertTrue((fixture / "hermes-agent" / ".git").exists())


if __name__ == "__main__":
    unittest.main()
