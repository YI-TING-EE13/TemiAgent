"""No-broker tests for the managed Mosquitto child contract."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "managed_mosquitto_supervisor.py"
SPEC = importlib.util.spec_from_file_location("managed_mosquitto_supervisor", MODULE_PATH)
assert SPEC and SPEC.loader
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


class _ExitedChild:
    pid = 41002
    returncode = 0

    def poll(self) -> int:
        return self.returncode


class ManagedMosquittoSupervisorTests(unittest.TestCase):
    def test_publishes_exact_child_pid_contract_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            broker_config = root / "mosquitto.conf"
            child_state = root / "mqtt-child.json"
            broker_config.write_text("listener 1883 127.0.0.1\n", encoding="utf-8")
            child_identity = {
                "pid": _ExitedChild.pid,
                "ppid": os.getpid(),
                "start_ticks": 42,
                "cmdline": ["mosquitto", "-c", str(broker_config)],
                "cmdline_sha256": "child-digest",
            }
            child = _ExitedChild()
            with (
                mock.patch.object(supervisor.subprocess, "Popen", return_value=child) as popen,
                mock.patch.object(supervisor.shutil, "which", return_value="/usr/sbin/mosquitto"),
                mock.patch.object(supervisor, "_limited_child_identity", return_value=child_identity),
                mock.patch.object(supervisor.signal, "signal"),
            ):
                result = supervisor.main(
                    [
                        "--config",
                        str(broker_config),
                        "--run-id",
                        "mqtt-test",
                        "--child-state-path",
                        str(child_state),
                    ]
                )

            self.assertEqual(result, 0)
            popen.assert_called_once_with(["mosquitto", "-c", str(broker_config)])
            payload = json.loads(child_state.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], supervisor.CHILD_STATE_SCHEMA)
            self.assertEqual(payload["run_id"], "mqtt-test")
            self.assertEqual(payload["supervisor_pid"], os.getpid())
            self.assertEqual(payload["pid"], _ExitedChild.pid)
            self.assertEqual(payload["ppid"], os.getpid())
            self.assertEqual(payload["cmdline"], child_identity["cmdline"])
            self.assertEqual(child_state.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
