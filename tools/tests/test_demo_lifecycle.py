"""Focused no-hardware tests for the canonical Demo lifecycle CLI helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import sys
import socket
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "demo_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("demo_lifecycle", MODULE_PATH)
assert SPEC and SPEC.loader
demo = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demo
SPEC.loader.exec_module(demo)


class DemoLifecycleConfigTests(unittest.TestCase):
    def make_config(self, root: Path, *, flags: tuple[str, str, str] = ("true", "true", "true")) -> Path:
        runtime = root / "runtime"
        config = root / "demo.env"
        config.write_text(
            "\n".join(
                [
                    f"TEMIAGENT_RUNTIME_ROOT={runtime}",
                    "MQTT_BROKER_HOST=127.0.0.1",
                    "MQTT_BROKER_PORT=1883",
                    "ROBOT_ID_ALLOWLIST=temi-01",
                    f"TEMI_SHARED_BRIDGE_PATH={runtime}/data/shared",
                    f"TEMI_SHARED_HERMES_PATH={runtime}/data/shared",
                    "HERMES_INVOKE_MODE=http",
                    "HERMES_HTTP_URL=http://127.0.0.1:8765/invoke",
                    f"LOG_DIR={runtime}/logs/bridge",
                    f"MEMORY_DIR={runtime}/data/care-memory",
                    f"HERMES_MEDIA_CALLBACK_SOCKET={runtime}/tmp/sockets/bridge.sock",
                    f"MEDIA_V11_ENABLED={flags[0]}",
                    f"HERMES_MEDIA_TOOL_ENABLED={flags[1]}",
                    f"HERMES_MEDIA_FAST_PATH_ENABLED={flags[2]}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        config.chmod(0o600)
        return config

    def test_external_owner_only_config_loads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root)
            loaded = demo.load_config(config)
            self.assertEqual(loaded.robot_id, "temi-01")
            self.assertTrue(loaded.runtime_root.is_relative_to(root))
            demo.ensure_runtime_layout(loaded)
            self.assertEqual(stat.S_IMODE(loaded.runtime_root.stat().st_mode), 0o700)
            self.assertTrue((loaded.runtime_root / "state" / "ownership").is_dir())

    def test_private_config_requires_0600(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary))
            config.chmod(0o644)
            with self.assertRaisesRegex(demo.DemoError, "0600"):
                demo.load_config(config)

    def test_media_flags_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary), flags=("true", "true", "false"))
            with self.assertRaisesRegex(demo.DemoError, "HERMES_MEDIA_FAST_PATH_ENABLED"):
                demo.load_config(config)

    def test_source_gate_allows_both_index_and_worktree_memory_changes(self) -> None:
        source = {
            "branch": demo.EXPECTED_BRANCH,
            "head": "test",
            "tree": [
                " M memory/daily_state.json",
                "M  memory/event_log.jsonl",
                " M memory/reminders.json",
            ],
        }
        with (
            mock.patch.object(demo, "_source_record", return_value=source),
            mock.patch.object(demo, "_git", return_value=""),
        ):
            self.assertEqual(demo._validate_source(), source)

    def test_stop_is_idempotent_without_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = demo.load_config(self.make_config(root))
            result = demo.stop(config, dry_run=True)
            self.assertEqual(result["state"], "DEMO_STOPPED")
            self.assertTrue(result["already_stopped"])

    def test_doctor_is_read_only_with_mocked_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = demo.load_config(self.make_config(root))
            demo.ensure_runtime_layout(config)
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": demo.EXPECTED_BRANCH, "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", side_effect=lambda port: 1 if port == 1883 else 0),
                mock.patch.object(demo, "_http_json", return_value={"status": "ok"}),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 2, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(result["summary"]["FAIL"], 0)

    def test_trace_export_requires_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with self.assertRaisesRegex(demo.DemoError, "no lifecycle state"):
                demo.trace_export(config)


class DemoLifecycleRecordTests(unittest.TestCase):
    def test_identity_match_rejects_changed_start_ticks(self) -> None:
        record = {"pid": 1, "start_ticks": -1, "cwd": "/", "executable": "/x", "cmdline_sha256": "bad"}
        self.assertFalse(demo._identity_matches(record))

    def test_stop_signals_only_the_recorded_exact_pid(self) -> None:
        record = {"name": "bridge", "leader": {"pid": 731}, "members": [], "ports": []}
        with (
            mock.patch.object(demo, "_identity_matches", side_effect=[True, False, False]),
            mock.patch.object(demo.os, "kill") as kill,
        ):
            self.assertEqual(demo._stop_record(record, timeout_seconds=1), "stopped_term")
        kill.assert_called_once_with(731, demo.signal.SIGTERM)

    def test_stop_waits_for_exact_listener_release(self) -> None:
        record = {"name": "resident", "leader": {"pid": 732}, "members": [], "ports": [8765]}
        with (
            mock.patch.object(demo, "_identity_matches", side_effect=[True, False, False]),
            mock.patch.object(demo.os, "kill"),
            mock.patch.object(demo, "_listener_count", return_value=0) as listener_count,
        ):
            self.assertEqual(demo._stop_record(record, timeout_seconds=1), "stopped_term")
        listener_count.assert_called_with(8765)

    def test_callback_socket_cleanup_requires_a_stopped_recorded_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(config.callback_socket))
            try:
                with mock.patch.object(demo, "_identity_matches", return_value=False):
                    demo._remove_owned_callback_socket(config, {"name": "bridge", "leader": {"pid": 733}})
                self.assertFalse(config.callback_socket.exists())
            finally:
                server.close()

    def test_callback_socket_cleanup_rejects_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            config.callback_socket.write_text("not a socket", encoding="utf-8")
            with mock.patch.object(demo, "_identity_matches", return_value=False):
                with self.assertRaisesRegex(demo.DemoError, "non-socket"):
                    demo._remove_owned_callback_socket(config, {"name": "bridge", "leader": {"pid": 734}})

    def test_archived_bridge_record_can_reconcile_its_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(config.callback_socket))
            try:
                demo._atomic_json(config.last_run_path, {"services": {"bridge": {"name": "bridge", "leader": {"pid": 735}, "members": []}}})
                with mock.patch.object(demo, "_identity_matches", return_value=False):
                    demo._reconcile_archived_callback_socket(config)
                self.assertFalse(config.callback_socket.exists())
            finally:
                server.close()

    def test_latest_trace_extracts_public_index_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "_index.jsonl").write_text(json.dumps({"event_id": "old", "payload": {"secret": "no"}}) + "\n" + json.dumps({"event_id": "new", "stage": "event_completed", "status": "ok"}) + "\n", encoding="utf-8")
            self.assertEqual(demo._latest_trace(directory), {"timestamp": None, "event_id": "new", "stage": "event_completed", "status": "ok", "run_id": None, "source_type": None})


if __name__ == "__main__":
    unittest.main()
