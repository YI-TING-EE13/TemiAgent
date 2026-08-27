"""Focused no-hardware tests for the canonical Demo lifecycle CLI helpers."""

from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from dataclasses import replace
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
    def make_config(
        self,
        root: Path,
        *,
        flags: tuple[str, str, str] = ("true", "true", "true"),
        viewer_enabled: bool = False,
    ) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        runtime = root / "runtime"
        config = root / "demo.env"
        lines = [
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
        if viewer_enabled:
            lines.extend(
                [
                    "DEMO_ACTION_VIEWER_ENABLED=true",
                    "DEMO_ACTION_VIEWER_MODEL=test-model",
                    "DEMO_ACTION_VIEWER_GGUF_MODEL_PATH=/tmp/test.gguf",
                    "DEMO_ACTION_VIEWER_MMPROJ_PATH=/tmp/test.mmproj",
                    "DEMO_ACTION_VIEWER_LLAMA_SERVER=/tmp/llama-server",
                    "DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH=enabled",
                    "DEMO_ACTION_VIEWER_DISCORD_NOTIFY=disabled",
                ]
            )
        config.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        config.chmod(0o600)
        return config

    def make_mock_config(self, root: Path) -> Path:
        """Materialize the tracked newcomer sample as an owner-only test config."""
        runtime = root / "newcomer-runtime"
        config = root / "demo.mock.env"
        config.write_text(
            (ROOT / "config" / "demo.mock.env.example").read_text(encoding="utf-8").replace(
                "<CANONICAL_RUNTIME_ROOT>", str(runtime)
            ),
            encoding="utf-8",
        )
        config.chmod(0o600)
        return config

    def make_managed_config(self, root: Path, *, broker_config: Path | None = None) -> Path:
        """Create a production-shaped managed-broker config for unit tests."""
        config = self.make_config(root)
        broker = broker_config or (root / "mosquitto.conf")
        broker.parent.mkdir(parents=True, exist_ok=True)
        broker.write_text(
            "listener 1883 127.0.0.1\n"
            "allow_anonymous true\n"
            "persistence false\n"
            "log_dest stdout\n",
            encoding="utf-8",
        )
        broker.chmod(0o600)
        with config.open("a", encoding="utf-8") as handle:
            handle.write("DEMO_GIT_BRANCH_POLICY=disabled\n")
            handle.write("MQTT_OWNERSHIP=managed\n")
            handle.write(f"MQTT_CONFIG_PATH={broker}\n")
        return config

    def test_default_discovery_never_selects_a_legacy_temporary_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / ".runtime" / "demo"
            config = runtime / "demo.env"
            legacy = root / "temiagent_fast_media_demo.env"
            legacy.write_text("TEMIAGENT_RUNTIME_ROOT=/tmp/legacy\n", encoding="utf-8")
            legacy.chmod(0o600)
            with (
                mock.patch.object(demo, "CANONICAL_RUNTIME_ROOT", runtime),
                mock.patch.object(demo, "CANONICAL_CONFIG_PATH", config),
            ):
                with self.assertRaisesRegex(demo.DemoError, "Canonical Demo config not initialized"):
                    demo.resolve_config_path(None)
                self.assertEqual(demo.resolve_config_path(str(legacy)), legacy)


    def test_external_owner_only_config_loads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root)
            loaded = demo.load_config(config)
            self.assertEqual(loaded.robot_id, "temi-01")
            self.assertTrue(loaded.runtime_root.is_relative_to(root))
            self.assertEqual(loaded.context_length, 64_000)
            self.assertEqual(loaded.lmstudio_context_length, 64_000)
            self.assertEqual(loaded.lmstudio_visible_gpus, "0,1")
            demo.ensure_runtime_layout(loaded)
            self.assertEqual(stat.S_IMODE(loaded.runtime_root.stat().st_mode), 0o700)
            self.assertTrue((loaded.runtime_root / "state" / "ownership").is_dir())

    def test_initializer_creates_an_idempotent_owner_only_canonical_mock_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / ".runtime" / "demo"
            config = runtime / "demo.env"
            with (
                mock.patch.object(demo, "CANONICAL_RUNTIME_ROOT", runtime),
                mock.patch.object(demo, "CANONICAL_CONFIG_PATH", config),
            ):
                initial = demo.initialize_canonical_config(profile=demo.PROFILE_NEWCOMER_MOCK)
                repeated = demo.initialize_canonical_config(profile=demo.PROFILE_NEWCOMER_MOCK)
            self.assertEqual(initial["state"], "DEMO_CONFIG_INITIALIZED")
            self.assertTrue(config.is_file())
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)
            self.assertTrue((runtime / "state" / "notifications").is_dir())
            self.assertTrue((runtime / "data" / "test-memory").is_dir())
            self.assertEqual(repeated["state"], "DEMO_CONFIG_READY")
            self.assertEqual(repeated["manual_secret_keys"], [])


    def test_private_config_requires_0600(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary))
            config.chmod(0o644)
            with self.assertRaisesRegex(demo.DemoError, "0600"):
                demo.load_config(config)

    def test_context_config_rejects_drift_from_canonical_64k(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary))
            with config.open("a", encoding="utf-8") as handle:
                handle.write("CONTEXT_LENGTH=32000\n")
            with self.assertRaisesRegex(demo.DemoError, "CONTEXT_LENGTH must be 64000"):
                demo.load_config(config)

    def test_lmstudio_context_must_match_canonical_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary))
            with config.open("a", encoding="utf-8") as handle:
                handle.write("LMSTUDIO_CONTEXT_LENGTH=32000\n")
            with self.assertRaisesRegex(demo.DemoError, "LMSTUDIO_CONTEXT_LENGTH must match"):
                demo.load_config(config)

    def test_lmstudio_gpu_policy_allows_only_zero_and_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary))
            with config.open("a", encoding="utf-8") as handle:
                handle.write("LMSTUDIO_VISIBLE_GPUS=0,1,2\n")
            with self.assertRaisesRegex(demo.DemoError, "LMSTUDIO_VISIBLE_GPUS must be 0,1"):
                demo.load_config(config)

    def test_media_flags_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_config(Path(temporary), flags=("true", "true", "false"))
            with self.assertRaisesRegex(demo.DemoError, "HERMES_MEDIA_FAST_PATH_ENABLED"):
                demo.load_config(config)

    def test_viewer_abnormal_event_flags_are_forwarded_without_discord_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_config(Path(temporary), viewer_enabled=True)
            config = demo.load_config(config_path)
            viewer_argv = demo._service_argv(config, "viewer")

        self.assertTrue(config.viewer_enabled)
        self.assertEqual(
            viewer_argv[viewer_argv.index("--abnormal-publish") + 1],
            "enabled",
        )
        self.assertNotIn("--discord-notify", viewer_argv)
        self.assertNotIn("--discord-env-path", viewer_argv)
        self.assertEqual(viewer_argv[viewer_argv.index("--notification-mode") + 1], "disabled")

    def test_real_discord_requires_a_valid_private_credential_before_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            credential = root / "discord.env"
            credential.write_text("DISCORD_WEBHOOK_URL=https://example.invalid/webhook\n", encoding="utf-8")
            credential.chmod(0o600)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("ABNORMAL_NOTIFICATION_MODE=discord_webhook\n")
                handle.write(f"ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH={credential}\n")
            config = demo.load_config(config_path)

        self.assertEqual(config.notification_mode, "discord_webhook")
        self.assertEqual(config.discord_env_path, credential)
        self.assertFalse(config.demo_notification_mock_enabled)

    def test_real_discord_missing_or_unsafe_credential_fails_during_config_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            missing = root / "missing.env"
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("ABNORMAL_NOTIFICATION_MODE=discord_webhook\n")
                handle.write(f"ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH={missing}\n")
            with self.assertRaisesRegex(demo.DemoError, "Discord credential file"):
                demo.load_config(config_path)

            missing.write_text("DISCORD_WEBHOOK_URL=https://example.invalid/webhook\n", encoding="utf-8")
            missing.chmod(0o644)
            with self.assertRaisesRegex(demo.DemoError, "mode 0600"):
                demo.load_config(config_path)

    def test_real_discord_requires_the_webhook_key_and_rejects_mock_mix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            credential = root / "discord.env"
            credential.write_text("OTHER_KEY=value\n", encoding="utf-8")
            credential.chmod(0o600)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("ABNORMAL_NOTIFICATION_MODE=discord_webhook\n")
                handle.write(f"ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH={credential}\n")
                handle.write("DEMO_NOTIFICATION_MOCK_ENABLED=true\n")
            with self.assertRaisesRegex(demo.DemoError, "DISCORD_WEBHOOK_URL"):
                demo.load_config(config_path)

    def test_real_discord_rejects_mock_flags_even_with_a_valid_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            credential = root / "discord.env"
            credential.write_text("DISCORD_WEBHOOK_URL=https://example.invalid/webhook\n", encoding="utf-8")
            credential.chmod(0o600)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("ABNORMAL_NOTIFICATION_MODE=discord_webhook\n")
                handle.write(f"ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH={credential}\n")
                handle.write("DEMO_NOTIFICATION_MOCK_ENABLED=true\n")
                handle.write("DEMO_NOTIFICATION_MOCK_RECEIPT_ENABLED=true\n")
            with self.assertRaisesRegex(demo.DemoError, "requires ABNORMAL_NOTIFICATION_MODE=demo_mock"):
                demo.load_config(config_path)

    def test_viewer_discord_flag_is_rejected_before_service_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_config(Path(temporary), viewer_enabled=True)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("DEMO_ACTION_VIEWER_DISCORD_NOTIFY=enabled\n")
            with self.assertRaisesRegex(demo.DemoError, "Bridge owns"):
                demo.load_config(config_path)

    def test_demo_mock_notification_requires_both_explicit_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_config(Path(temporary))
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("ABNORMAL_NOTIFICATION_MODE=demo_mock\nDEMO_NOTIFICATION_MOCK_ENABLED=true\n")
            with self.assertRaisesRegex(demo.DemoError, "both Demo notification mock flags"):
                demo.load_config(config_path)

    def test_managed_ownership_requires_a_broker_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("MQTT_OWNERSHIP=managed\n")
            with self.assertRaisesRegex(demo.DemoError, "MQTT_CONFIG_PATH"):
                demo.load_config(config_path)

    def test_managed_broker_uses_exact_identity_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("MQTT_OWNERSHIP=managed\n")
                handle.write(f"MQTT_CONFIG_PATH={ROOT / 'mqtt' / 'mosquitto.conf'}\n")
            config = demo.load_config(config_path)
            argv = demo._service_argv(config, "mqtt")
        self.assertIn("managed_mosquitto_supervisor.py", " ".join(argv))

    def test_managed_lmstudio_uses_exact_identity_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_config(root)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("LMSTUDIO_OWNERSHIP=managed\n")
            config = demo.load_config(config_path)
            argv = demo._service_argv(config, "lmstudio")
        self.assertIn("managed_lmstudio_supervisor.py", " ".join(argv))
        self.assertIn(config.lmstudio_api_identifier, argv)

    def test_newcomer_mock_profile_uses_isolated_ports_and_formal_test_doubles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_mock_config(Path(temporary)))
            specs = demo._specs(config)
            self.assertTrue(config.is_newcomer_mock)
            self.assertEqual(config.lmstudio_server_port, 29134)
            self.assertEqual(config.adapter_ports, (29080, 29081))
            self.assertEqual(config.resident_invoke_url, "http://127.0.0.1:29765/invoke")
            self.assertEqual(config.viewer_health_url, "http://127.0.0.1:29010/health")
            self.assertEqual(specs["mock_android"].ports, (29012,))
            self.assertIn("mock_resident_server.py", " ".join(demo._service_argv(config, "resident")))
            self.assertIn("mock_lmstudio_server.py", " ".join(demo._service_argv(config, "lmstudio")))

    def test_production_defaults_remain_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            self.assertEqual(config.profile, "production")
            self.assertEqual(config.expected_git_branch, "main")
            self.assertEqual(config.lifecycle_ports, (1234, 1883, 8080, 8081, 8765, 8010, 8011))
            self.assertEqual(config.resident_invoke_url, "http://127.0.0.1:8765/invoke")

    def test_lifecycle_lock_rejects_concurrent_holder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            with demo._lifecycle_lock(config):
                with self.assertRaisesRegex(demo.DemoError, "LOCK_BUSY"):
                    with demo._lifecycle_lock(config):
                        pass

    def test_source_gate_allows_both_index_and_worktree_memory_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
        source = {
            "branch": "main",
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
            self.assertEqual(demo._validate_source(config), source)

    def test_source_gate_rejects_stale_branch_and_accepts_explicitly_disabled_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = demo.load_config(self.make_config(root))
            disabled = demo.load_config(self.make_mock_config(root))
            stale = {"branch": "codex/stale", "head": "test", "tree": []}
            detached = {"branch": "", "head": "test", "tree": []}
            with mock.patch.object(demo, "_git", return_value=""):
                with mock.patch.object(demo, "_source_record", return_value=stale):
                    with self.assertRaisesRegex(demo.DemoError, "unexpected branch"):
                        demo._validate_source(production)
                with mock.patch.object(demo, "_source_record", return_value=detached):
                    with self.assertRaisesRegex(demo.DemoError, "detached HEAD"):
                        demo._validate_source(production)
                    self.assertEqual(demo._validate_source(disabled), detached)

    def test_source_gate_rejects_a_generated_external_checkout_difference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_mock_config(Path(temporary)))
        source = {"branch": "", "head": "test", "tree": [" M hermes-agent"]}
        with (
            mock.patch.object(demo, "_source_record", return_value=source),
            mock.patch.object(demo, "_git", return_value=""),
        ):
            with self.assertRaisesRegex(demo.DemoError, "non-runtime dirty files"):
                demo._validate_source(config)

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
                mock.patch.object(demo, "_validate_source", return_value={"branch": "main", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", side_effect=lambda port: 1 if port == 1883 else 0),
                mock.patch.object(
                    demo,
                    "_http_health",
                    side_effect=lambda url: (
                        {"data": [{"id": "google/gemma-4-31b"}]} if url.endswith("/v1/models") else {"status": "ok", "media_tool_enabled": True, "media_fast_path_enabled": True},
                        "HEALTHY",
                        "test health",
                    ),
                ),
                mock.patch.object(demo, "_http_json", return_value={"status": "ok", "media_tool_enabled": True, "media_fast_path_enabled": True, "media_tool_names": list(demo.MEDIA_TOOLS)}),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 2, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(result["summary"]["FAIL"], 0)

    def test_doctor_marks_required_external_endpoint_unavailable_as_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "main", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", return_value=1),
                mock.patch.object(demo, "_http_health", return_value=(None, "ENDPOINT_UNAVAILABLE", "unavailable")),
                mock.patch.object(demo, "_http_json", return_value=None),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 0, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == "lm_studio")
        self.assertEqual(item["status"], "FAIL")
        self.assertEqual(item["code"], "ENDPOINT_UNAVAILABLE")
        self.assertTrue(item["required"])

    def test_doctor_marks_required_external_endpoint_timeout_as_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "main", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", return_value=1),
                mock.patch.object(demo, "_http_health", return_value=(None, "ENDPOINT_TIMEOUT", "timed out")),
                mock.patch.object(demo, "_http_json", return_value=None),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 0, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == "lm_studio")
        self.assertEqual((item["status"], item["code"]), ("FAIL", "ENDPOINT_TIMEOUT"))

    def test_doctor_marks_a_missing_required_entrypoint_as_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_mock_config(Path(temporary)))
            missing = ROOT / "tools" / "mocks" / "mock_resident_server.py"
            original_is_file = Path.is_file

            def is_file(path: Path) -> bool:
                return False if path == missing else original_is_file(path)

            with mock.patch.object(Path, "is_file", autospec=True, side_effect=is_file):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == "entrypoints")
        self.assertEqual((item["status"], item["code"]), ("FAIL", "ENTRYPOINT_MISSING"))
        self.assertTrue(item["required"])

    def test_doctor_mock_endpoint_healthy_and_optional_items_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_mock_config(Path(temporary)))
            def health(url: str) -> tuple[dict[str, object], str, str]:
                if url.endswith("/v1/models"):
                    return {"data": [{"id": config.lmstudio_api_identifier}]}, "HEALTHY", "ok"
                if url.endswith("/health") and ":29012/" in url:
                    return {"ok": True, "test_double": "android"}, "HEALTHY", "ok"
                if url.endswith("/health") and ":29013/" in url:
                    return {"ok": True, "test_double": "discord"}, "HEALTHY", "ok"
                if url.endswith("/health") and ":29010/" in url:
                    return {
                        "ok": True,
                        "source_connected": True,
                        "llama_server_ready": True,
                        "components": {
                            "viewer_core": {"status": "healthy"},
                            "event_ingestion": {"status": "healthy"},
                            "frame_state": {"status": "healthy"},
                            "real_discord": {"status": "disabled"},
                            "demo_notification_mock": {"status": "healthy"},
                        },
                    }, "HEALTHY", "ok"
                return {"status": "ok", "media_tool_enabled": True, "media_fast_path_enabled": True}, "HEALTHY", "ok"
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", side_effect=lambda port: 1 if port == config.mqtt_port else 0),
                mock.patch.object(demo, "_http_health", side_effect=health),
                mock.patch.object(demo, "_http_json", return_value={"status": "ok", "media_tool_enabled": True, "media_fast_path_enabled": True, "media_tool_names": list(demo.MEDIA_TOOLS)}),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 0, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
        for check in result["checks"]:
            self.assertEqual(set(check), {"name", "status", "code", "message", "required"})
        self.assertEqual(next(check for check in result["checks"] if check["name"] == "lm_studio")["status"], "PASS")
        self.assertEqual(next(check for check in result["checks"] if check["name"] == "gateway")["status"], "SKIPPED")
        self.assertEqual(next(check for check in result["checks"] if check["name"] == "viewer")["status"], "PASS")

    def test_doctor_rejects_malformed_required_health(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "main", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", return_value=1),
                mock.patch.object(demo, "_http_health", return_value=({}, "HEALTHY", "response")),
                mock.patch.object(demo, "_http_json", return_value=None),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 0, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == "lm_studio")
        self.assertEqual((item["status"], item["code"]), ("FAIL", "HEALTH_MALFORMED"))

    def test_doctor_detects_an_unowned_port_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_mock_config(Path(temporary)))
            healthy = {"status": "ok", "media_tool_enabled": True, "media_fast_path_enabled": True, "media_tool_names": list(demo.MEDIA_TOOLS)}
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "", "head": "test"}),
                mock.patch.object(demo, "_git", return_value=""),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_listener_count", side_effect=lambda port: 1 if port in {config.mqtt_port, config.adapter_vision_port} else 0),
                mock.patch.object(demo, "_http_health", return_value=({"data": [{"id": config.lmstudio_api_identifier}]}, "HEALTHY", "ok")),
                mock.patch.object(demo, "_http_json", return_value=healthy),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 0, "remote_sessions": 0}),
            ):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == f"port_{config.adapter_vision_port}")
        self.assertEqual((item["status"], item["code"]), ("FAIL", "PORT_CONFLICT"))

    def test_doctor_exit_code_fails_only_when_a_fail_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            warning_only = {"summary": {"PASS": 0, "WARNING": 1, "SKIPPED": 1, "FAIL": 0}}
            required_failure = {"summary": {"PASS": 0, "WARNING": 0, "SKIPPED": 0, "FAIL": 1}}
            with mock.patch.object(demo, "load_config", return_value=config):
                with mock.patch.object(demo, "doctor", return_value=warning_only):
                    self.assertEqual(demo.main(["--config", str(config.config_path), "doctor"]), 0)
                with mock.patch.object(demo, "doctor", return_value=required_failure):
                    self.assertEqual(demo.main(["--config", str(config.config_path), "doctor"]), 1)

    def test_trace_export_requires_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with self.assertRaisesRegex(demo.DemoError, "no lifecycle state"):
                demo.trace_export(config)


    def test_starting_record_is_atomically_persisted_before_health_wait(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_mock_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            record = {
                "name": "viewer",
                "leader": {"pid": 777, "start_ticks": 1},
                "members": [],
                "ports": [config.viewer_http_port],
                "log_path": str(config.runtime_root / "logs" / "trace" / "viewer.log"),
            }
            state = {"status": demo.STATE_STARTING, "services": {}}
            observed: list[dict[str, object]] = []
            original_atomic = demo._atomic_json
            def record_atomic(path: Path, payload: object) -> None:
                observed.append(deepcopy(payload))
                original_atomic(path, payload)
            with (
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_atomic_json", side_effect=record_atomic),
            ):
                demo._persist_starting_record(config, state, "viewer", record, ["viewer", "--port", "29010"])
        self.assertEqual(observed[0]["status"], demo.STATE_STARTING)
        stored = observed[0]["services"]["viewer"]
        self.assertEqual(stored["process_start_identity"]["pid"], 777)
        self.assertIn("command_fingerprint", stored)
        self.assertIn("spawned_at", stored)

    def test_main_returns_nonzero_for_stop_incomplete_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            result = {"state": "STOP_INCOMPLETE_OWNERSHIP", "already_stopped": False, "findings": [{"service": "viewer"}]}
            with (
                mock.patch.object(demo, "load_config", return_value=config),
                mock.patch.object(demo, "stop", return_value=result),
            ):
                self.assertEqual(demo.main(["--config", str(config.config_path), "stop"]), 2)

    def test_failure_code_classifies_health_gate_failures(self) -> None:
        self.assertEqual(demo._failure_code("HEALTH GATE: viewer did not pass health"), "SERVICE_HEALTH_FAILED")

    def test_doctor_reports_unwritable_state_pid_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_config(Path(temporary)))
            with mock.patch.object(demo, "_has_writable_existing_parent", return_value=False):
                result = demo.doctor(config)
        item = next(check for check in result["checks"] if check["name"] == "state_pid_root")
        self.assertEqual((item["status"], item["code"]), ("FAIL", "STATE_PID_ROOT_UNWRITABLE"))

    def test_failed_health_retains_starting_ownership_and_archives_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_mock_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            spec = demo.ServiceSpec(
                "viewer", ROOT, "mock_viewer_server.py", (config.viewer_http_port,),
                config.runtime_root / "logs" / "trace" / "viewer.log",
            )
            record = {
                "name": "viewer",
                "ownership": "owned",
                "leader": {"pid": 778, "start_ticks": 2},
                "members": [],
                "ports": [config.viewer_http_port],
                "log_path": str(spec.log_path),
            }
            snapshots: list[dict[str, object]] = []
            original_atomic = demo._atomic_json

            def record_atomic(path: Path, payload: object) -> None:
                snapshots.append(deepcopy(payload))
                original_atomic(path, payload)

            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "", "head": "test", "tree": []}),
                mock.patch.object(demo, "_specs", return_value={"viewer": spec}),
                mock.patch.object(demo, "_validate_resource_manifest", return_value={}),
                mock.patch.object(demo, "_reconcile_archived_callback_socket"),
                mock.patch.object(demo, "_assert_start_ports_clear"),
                mock.patch.object(demo, "_external_dependency_ready"),
                mock.patch.object(demo, "_base_env", return_value={}),
                mock.patch.object(demo, "_start_process", return_value=record),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_wait_for", return_value=False),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
                mock.patch.object(demo, "_atomic_json", side_effect=record_atomic),
            ):
                with self.assertRaisesRegex(demo.DemoError, "viewer did not pass"):
                    demo.start(config)
            current = demo._read_json(config.state_path)
            archived = demo._read_json(config.last_run_path)

        self.assertEqual(snapshots[0]["status"], demo.STATE_STARTING)
        self.assertIn("viewer", snapshots[0]["services"])
        stop_record.assert_called_once_with(record, timeout_seconds=20)
        self.assertEqual(current["status"], demo.STATE_START_FAILED)
        self.assertEqual(archived["status"], demo.STATE_START_FAILED)
        self.assertEqual(current["rollback"][0]["service"], "viewer")

    def test_stop_refuses_success_when_live_managed_like_process_has_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_mock_config(Path(temporary)))
            with mock.patch.object(demo, "_managed_like_unrecorded_services", return_value=[{"service": "viewer", "ports": [config.viewer_http_port]}]):
                result = demo.stop(config)

        self.assertEqual(result["state"], "STOP_INCOMPLETE_OWNERSHIP")
        self.assertFalse(result["already_stopped"])
        self.assertEqual(result["findings"][0]["service"], "viewer")

    def test_atomic_json_fsyncs_file_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "state" / "current.json"
            with mock.patch.object(demo.os, "fsync", wraps=demo.os.fsync) as fsync:
                demo._atomic_json(destination, {"status": "test"})

        self.assertGreaterEqual(fsync.call_count, 2)

    def test_lifecycle_reset_replaces_stale_identity_without_deleting_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_dir = root / "identity-state"
            state_dir.mkdir()
            current = state_dir / "current.json"
            current.write_text(json.dumps({"identity_status": "father", "process_scoped": True}) + "\n", encoding="utf-8")
            config = mock.Mock(identity_state_dir=state_dir, robot_id="temi-01")

            self.assertTrue(demo._reset_ephemeral_demo_identity(config))
            payload = json.loads(current.read_text(encoding="utf-8"))

        self.assertEqual(payload["identity_status"], "unknown")
        self.assertTrue(payload["process_scoped"])
        self.assertTrue(payload["lifecycle_reset"])
        self.assertEqual(payload["robot_id"], "temi-01")

    def test_lifecycle_reset_is_noop_when_identity_is_disabled(self) -> None:
        config = mock.Mock(identity_state_dir=None, robot_id="temi-01")
        self.assertFalse(demo._reset_ephemeral_demo_identity(config))


class MqttOnlyLifecycleTests(unittest.TestCase):
    """No-broker tests for MQTT-only parser, ownership and readiness gates."""

    config_tests = DemoLifecycleConfigTests()

    def make_managed_config(self, root: Path, *, broker_config: Path | None = None) -> Path:
        return self.config_tests.make_managed_config(root, broker_config=broker_config)

    def make_record(self, config: demo.DemoConfig) -> dict[str, object]:
        leader = {
            "pid": 41001,
            "ppid": 41000,
            "start_ticks": 41,
            "cwd": str(demo.ROOT),
            "executable": "/usr/bin/python3.12",
            "cmdline": [
                "/usr/bin/python3",
                str(demo.ROOT / "tools" / "managed_mosquitto_supervisor.py"),
                "--config",
                str(config.mqtt_config_path),
                "--run-id",
                "mqtt-test",
            ],
            "cmdline_sha256": "leader-digest",
        }
        return {
            "name": "mqtt",
            "ownership": "owned",
            "leader": leader,
            "members": [],
            "ports": [config.mqtt_port],
            "log_path": str(config.mqtt_log_path),
            "process_start_identity": dict(leader),
            "command_fingerprint": demo._command_fingerprint(leader["cmdline"]),
            "lifecycle_run_id": "mqtt-test",
        }

    def make_child(self, config: demo.DemoConfig) -> dict[str, object]:
        executable, executable_sha256 = demo._mosquitto_executable_identity()
        self.assertIsNotNone(executable)
        self.assertIsNotNone(executable_sha256)
        return {
            "schema_version": "temiagent.mosquitto_child.v1",
            "run_id": "mqtt-test",
            "supervisor_pid": 41001,
            "pid": 41002,
            "ppid": 41001,
            "start_ticks": 42,
            "executable": executable,
            "executable_sha256": executable_sha256,
            "cmdline": [executable, "-c", str(config.mqtt_config_path)],
            "cmdline_sha256": "child-digest",
        }

    def make_evidence(
        self,
        config: demo.DemoConfig,
        *,
        listener_count: int = 0,
        address: str = "127.0.0.1",
        pids: list[int] | None = None,
        tcp_ready: bool = False,
        supervisor_valid: bool = False,
        listener_lineage_valid: bool = False,
        ready: bool = False,
    ) -> dict[str, object]:
        listeners = (
            []
            if listener_count == 0
            else [{"address": address, "port": config.mqtt_port, "pids": pids or []}]
        )
        return {
            "expected_address": address,
            "expected_port": config.mqtt_port,
            "listeners": listeners,
            "listener_count": listener_count,
            "bind_address_valid": listener_count == 1 and address == "127.0.0.1",
            "port_valid": True,
            "tcp_ready": tcp_ready,
            "supervisor_valid": supervisor_valid,
            "supervisor_pid": 41001 if supervisor_valid else None,
            "listener_pids": pids or [],
            "mosquitto_pids": pids or [] if listener_lineage_valid else [],
            "listener_lineage_valid": listener_lineage_valid,
            "ready": ready,
        }

    def write_state(
        self,
        config: demo.DemoConfig,
        *,
        status: str,
        record: dict[str, object] | None = None,
    ) -> dict[str, object]:
        state: dict[str, object] = {
            "schema_version": "temiagent.demo_lifecycle.v2",
            "scope": "mqtt",
            "status": status,
            "run_id": "mqtt-test",
            "services": {"mqtt": record} if record is not None else {},
        }
        demo._atomic_json(config.mqtt_state_path, state)
        return state

    def test_parser_accepts_mqtt_operations_and_rejects_unknown_operation(self) -> None:
        with self.assertRaises(SystemExit):
            demo.main(["mqtt", "invalid"])
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            evidence = self.make_evidence(config)
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence):
                for operation in ("start", "status", "stop"):
                    if operation == "status":
                        result = demo.mqtt_only_command(config, operation)
                        self.assertEqual(result["state"], demo.STATE_STOPPED)
                    else:
                        self.assertTrue(callable(getattr(demo, f"mqtt_only_{operation}")))

    def test_mqtt_status_is_read_only_and_never_dispatches_full_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_managed_config(Path(temporary))
            config = demo.load_config(config_path)
            evidence = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence),
                mock.patch.object(demo, "_start_process") as start_process,
                mock.patch.object(demo, "start") as full_start,
            ):
                result = demo.main(["--config", str(config_path), "mqtt", "status"])
        self.assertEqual(result, 0)
        start_process.assert_not_called()
        full_start.assert_not_called()

    def test_mqtt_parser_dispatches_only_mqtt_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_managed_config(Path(temporary))
            config = demo.load_config(config_path)
            with (
                mock.patch.object(demo, "load_config", return_value=config),
                mock.patch.object(demo, "ensure_runtime_layout"),
                mock.patch.object(demo, "_lifecycle_lock", return_value=nullcontext()),
                mock.patch.object(demo, "mqtt_only_command", return_value={"state": demo.MQTT_STATE_RUNNING}) as mqtt_command,
                mock.patch.object(demo, "start") as full_start,
            ):
                result = demo.main(["--config", str(config_path), "mqtt", "start"])
        self.assertEqual(result, 0)
        mqtt_command.assert_called_once_with(config, "start")
        full_start.assert_not_called()

    def test_mqtt_parser_dispatches_only_mqtt_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_managed_config(Path(temporary))
            config = demo.load_config(config_path)
            with (
                mock.patch.object(demo, "load_config", return_value=config),
                mock.patch.object(demo, "ensure_runtime_layout"),
                mock.patch.object(demo, "_lifecycle_lock", return_value=nullcontext()),
                mock.patch.object(demo, "mqtt_only_command", return_value={"state": demo.STATE_STOPPED}) as mqtt_command,
                mock.patch.object(demo, "stop") as full_stop,
            ):
                result = demo.main(["--config", str(config_path), "mqtt", "stop"])
        self.assertEqual(result, 0)
        mqtt_command.assert_called_once_with(config, "stop")
        full_stop.assert_not_called()

    def test_stopped_without_state_has_none_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=self.make_evidence(config)):
                result = demo.mqtt_only_status(config)
        self.assertEqual((result["state"], result["ownership"]), (demo.STATE_STOPPED, "NONE"))
        self.assertEqual(result["reason"], "NO_CANONICAL_OWNERSHIP")
        self.assertFalse(result["foreign_listener"])

    def test_foreign_listener_is_stopped_none_and_never_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            evidence = self.make_evidence(config, listener_count=1, pids=[49999], tcp_ready=True)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence),
                mock.patch.object(demo, "_stop_record") as stop_record,
            ):
                result = demo.mqtt_only_status(config)
                stopped = demo.mqtt_only_stop(config)
        for payload in (result, stopped):
            self.assertEqual((payload["state"], payload["ownership"]), (demo.STATE_STOPPED, "NONE"))
            self.assertTrue(payload["foreign_listener"])
        stop_record.assert_not_called()

    def test_mqtt_start_refuses_foreign_listener_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            foreign = self.make_evidence(config, listener_count=1, pids=[49999], tcp_ready=True)
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=foreign),
                mock.patch.object(demo, "_start_process") as start_process,
            ):
                with self.assertRaisesRegex(demo.DemoError, "FOREIGN_LISTENER"):
                    demo.mqtt_only_start(config)
        start_process.assert_not_called()

    def test_mqtt_start_refuses_unattributed_listener_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            foreign = self.make_evidence(config, listener_count=1, pids=[], tcp_ready=True)
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=foreign),
                mock.patch.object(demo, "_start_process") as start_process,
            ):
                with self.assertRaisesRegex(demo.DemoError, "FOREIGN_LISTENER"):
                    demo.mqtt_only_start(config)
        start_process.assert_not_called()

    def test_valid_starting_state_is_degraded_until_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            self.write_state(config, status=demo.STATE_STARTING, record=record)
            evidence = self.make_evidence(
                config,
                listener_count=0,
                tcp_ready=False,
                supervisor_valid=True,
            )
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence):
                result = demo.mqtt_only_status(config)
        self.assertEqual((result["state"], result["ownership"]), (demo.STATE_STARTING, "managed"))
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "READINESS_PENDING")
        self.assertEqual(result["supervisor_pid"], 41001)

    def test_stale_starting_without_live_pid_reconciles_to_stopped_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            self.write_state(config, status=demo.STATE_STARTING)
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=self.make_evidence(config)):
                result = demo.mqtt_only_status(config)
            state_remains = config.mqtt_state_path.exists()
        self.assertEqual((result["state"], result["ownership"]), (demo.STATE_STOPPED, "NONE"))
        self.assertEqual(result["reason"], "STALE_STARTING_NO_LIVE_OWNER")
        self.assertTrue(state_remains)

    def test_unpersisted_startup_intent_can_stop_exact_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            state = self.write_state(config, status=demo.STATE_STARTING)
            state["startup"] = {
                "run_id": "mqtt-test",
                "cwd": "/tmp/reviewed-operational-checkout",
                "argv": self.make_record(config)["leader"]["cmdline"],
            }
            demo._atomic_json(config.mqtt_state_path, state)
            record = self.make_record(config)
            owned = self.make_evidence(config, supervisor_valid=True)
            stopped = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_unpersisted_startup_record", return_value=record),
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=[owned, stopped]),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
            ):
                result = demo.mqtt_only_stop(config)
        self.assertEqual(result["state"], demo.STATE_STOPPED)
        stop_record.assert_called_once_with(record, timeout_seconds=30)
        self.assertFalse(config.mqtt_state_path.exists())

    def test_recorded_child_can_be_stopped_after_supervisor_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = {
                "pid": 41002,
                "ppid": 41001,
                "start_ticks": 42,
                "cwd": "/tmp/reviewed-operational-checkout",
                "executable": "/usr/sbin/mosquitto",
                "cmdline": ["mosquitto", "-c", str(config.mqtt_config_path)],
                "cmdline_sha256": "child-digest",
            }
            record["members"] = [child]
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=record)
            occupied = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=False,
                listener_lineage_valid=False,
            )
            stopped = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=[occupied, stopped]),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(
                    demo,
                    "_identity",
                    return_value={
                        **child,
                        "ppid": 1,
                    },
                ),
                mock.patch.object(demo, "_wait_for", return_value=True),
                mock.patch.object(demo, "_listener_count", return_value=0),
                mock.patch.object(demo.os, "kill") as kill,
            ):
                result = demo.mqtt_only_stop(config)
        self.assertEqual(result["state"], demo.STATE_STOPPED)
        kill.assert_called_once_with(41002, demo.signal.SIGTERM)
        self.assertFalse(config.mqtt_state_path.exists())

    def test_live_member_outside_supervisor_lineage_is_not_signalled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            record["members"] = [{
                "pid": 41002,
                "ppid": 41000,
                "start_ticks": 42,
                "cwd": str(demo.ROOT),
                "executable": "/usr/sbin/mosquitto",
                "cmdline": ["mosquitto", "-c", str(config.mqtt_config_path)],
                "cmdline_sha256": "child-digest",
            }]
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=record)
            occupied = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=True,
            )
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=occupied),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_identity", return_value={"pid": 41002, "ppid": 1}),
                mock.patch.object(demo, "_stop_record") as stop_record,
            ):
                with self.assertRaisesRegex(demo.DemoError, "OWNERSHIP_UNRESOLVED"):
                    demo.mqtt_only_stop(config)
        stop_record.assert_not_called()

    def test_running_state_requires_all_readiness_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=record)
            evidence = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=False,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=False,
            )
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence):
                result = demo.mqtt_only_status(config)
        self.assertEqual((result["state"], result["ownership"]), (demo.STATE_UNHEALTHY, "managed"))
        self.assertFalse(result["tcp_ready"])
        self.assertFalse(result["ready"])

    def test_dead_running_pid_is_not_reported_as_running(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=self.make_record(config))
            evidence = self.make_evidence(config, listener_count=0)
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence):
                result = demo.mqtt_only_status(config)
        self.assertEqual((result["state"], result["ownership"]), (demo.STATE_STOPPED, "NONE"))
        self.assertEqual(result["reason"], "STALE_OWNERSHIP")

    def test_start_persists_intent_before_spawn_and_only_records_mqtt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            no_listener = self.make_evidence(config)
            ready = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=True,
            )
            snapshots: list[dict[str, object]] = []
            original_atomic = demo._atomic_json

            def observe_atomic(path: Path, payload: object) -> None:
                if path == config.mqtt_state_path:
                    snapshots.append(deepcopy(payload))
                original_atomic(path, payload)

            def spawn(spec: object, argv: list[str], env: dict[str, str]) -> dict[str, object]:
                state = demo._read_json(config.mqtt_state_path)
                self.assertEqual(state["status"], demo.STATE_STARTING)
                self.assertEqual(state["services"], {})
                return record

            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=lambda _config, record=None: no_listener if record is None else ready),
                mock.patch.object(demo, "_start_process", side_effect=spawn) as start_process,
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_wait_for", return_value=True),
                mock.patch.object(demo, "_atomic_json", side_effect=observe_atomic),
            ):
                result = demo.mqtt_only_start(config)
        self.assertEqual(result["state"], demo.MQTT_STATE_RUNNING)
        self.assertEqual(result["ownership"], "managed")
        self.assertEqual(snapshots[0]["status"], demo.STATE_STARTING)
        self.assertEqual(snapshots[0]["services"], {})
        self.assertEqual(snapshots[1]["services"]["mqtt"]["leader"]["pid"], 41001)
        start_process.assert_called_once()

    def test_success_persists_supervisor_child_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            record["mqtt_child"] = child
            no_listener = self.make_evidence(config)
            ready = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=True,
            )
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=lambda _config, record=None: no_listener if record is None else ready),
                mock.patch.object(demo, "_start_process", return_value=record),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_wait_for", return_value=True),
            ):
                result = demo.mqtt_only_start(config)
            stored = demo._read_json(config.mqtt_state_path)
        self.assertEqual(result["state"], demo.MQTT_STATE_RUNNING)
        self.assertEqual(stored["services"]["mqtt"]["mqtt_child"], child)

    def test_start_failure_rolls_back_exact_record_and_retains_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            spawned = deepcopy(record)
            no_listener = self.make_evidence(config)
            not_ready = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=False,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=False,
            )

            def spawn(_spec: object, argv: list[str], _env: dict[str, str]) -> dict[str, object]:
                spawned["leader"]["cmdline"] = list(argv)
                spawned["process_start_identity"] = dict(spawned["leader"])
                spawned["command_fingerprint"] = demo._command_fingerprint(argv)
                run_id_index = argv.index("--run-id") + 1
                spawned["lifecycle_run_id"] = argv[run_id_index]
                return spawned

            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=lambda _config, record=None: no_listener if record is None else not_ready),
                mock.patch.object(demo, "_start_process", side_effect=spawn),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_wait_for", return_value=False),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
            ):
                with self.assertRaisesRegex(demo.DemoError, "readiness gate"):
                    demo.mqtt_only_start(config)
            current = demo._read_json(config.mqtt_state_path)
            archived = demo._read_json(config.mqtt_last_run_path)
        self.assertEqual(current["status"], demo.STATE_START_FAILED)
        self.assertEqual(archived["status"], demo.STATE_START_FAILED)
        self.assertEqual(current["rollback"][0]["service"], "mqtt")
        stop_record.assert_called_once_with(spawned, timeout_seconds=20)

    def test_interrupt_after_spawn_before_pid_record_recovers_exact_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            no_listener = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=no_listener),
                mock.patch.object(demo, "_start_process", side_effect=KeyboardInterrupt),
                mock.patch.object(demo, "_mqtt_unpersisted_startup_record", return_value=record),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
            ):
                with self.assertRaisesRegex(demo.DemoError, "MQTT_ONLY_START_FAILED"):
                    demo.mqtt_only_start(config)
        stop_record.assert_called_once_with(record, timeout_seconds=20)

    def test_interrupt_during_pid_persistence_recovers_exact_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            no_listener = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=no_listener),
                mock.patch.object(demo, "_start_process", return_value=record),
                mock.patch.object(demo, "_persist_starting_record", side_effect=KeyboardInterrupt),
                mock.patch.object(demo, "_mqtt_supervisor_valid", side_effect=[False, True]) as supervisor_valid,
                mock.patch.object(demo, "_mqtt_unpersisted_startup_record", return_value=record) as recover,
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
            ):
                with self.assertRaisesRegex(demo.DemoError, "MQTT_ONLY_START_FAILED"):
                    demo.mqtt_only_start(config)
        recover.assert_called_once()
        self.assertEqual(supervisor_valid.call_count, 2)
        stop_record.assert_called_once_with(record, timeout_seconds=20)

    def test_start_and_stop_do_not_touch_other_component_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            full_state = {"status": demo.STATE_HEALTHY, "services": {"resident": {"leader": {"pid": 7}}}}
            demo._atomic_json(config.state_path, full_state)
            record = self.make_record(config)
            no_listener = self.make_evidence(config)
            ready = self.make_evidence(config, listener_count=1, pids=[41002], tcp_ready=True, supervisor_valid=True, listener_lineage_valid=True, ready=True)
            with (
                mock.patch.object(demo, "_validate_mqtt_only_source", return_value={"root": "test"}),
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=lambda _config, record=None: no_listener if record is None else ready),
                mock.patch.object(demo, "_start_process", return_value=record),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_wait_for", return_value=True),
            ):
                demo.mqtt_only_start(config)
            self.assertEqual(demo._read_json(config.state_path), full_state)
            demo._atomic_json(config.mqtt_state_path, {"schema_version": "temiagent.demo_lifecycle.v2", "scope": "mqtt", "status": demo.MQTT_STATE_RUNNING, "services": {"mqtt": record}})
            stop_evidence = self.make_evidence(config, listener_count=1, pids=[41002], tcp_ready=True, supervisor_valid=True, listener_lineage_valid=True, ready=True)
            final_evidence = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=[stop_evidence, final_evidence]),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term"),
            ):
                demo.mqtt_only_stop(config)
            self.assertEqual(demo._read_json(config.state_path), full_state)

    def test_listener_config_and_bind_address_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_managed_config(root)
            config = demo.load_config(config_path)
            with mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "0.0.0.0", "port": 1883, "pids": []}]):
                evidence = demo._mqtt_listener_evidence(config)
            self.assertTrue(evidence["bind_address_valid"] is False)
            broker = root / "wildcard.conf"
            broker.write_text("listener 1883 0.0.0.0\n", encoding="utf-8")
            broker.chmod(0o600)
            config_path = self.make_managed_config(root / "wildcard", broker_config=broker)
            broker.write_text("listener 1883 0.0.0.0\n", encoding="utf-8")
            broker.chmod(0o600)
            config = demo.load_config(config_path)
            with mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "[::]", "port": 1883, "pids": []}]):
                evidence = demo._mqtt_listener_evidence(config)
        self.assertTrue(evidence["bind_address_valid"])

    def test_listener_config_port_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.make_managed_config(root)
            broker = root / "mosquitto.conf"
            broker.write_text("listener 1884 127.0.0.1\n", encoding="utf-8")
            broker.chmod(0o600)
            config = demo.load_config(config_path)
            with self.assertRaisesRegex(demo.DemoError, "PORT_MISMATCH"):
                demo._mqtt_listener_evidence(config)

    def test_tcp_ready_is_required_even_when_listener_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": [41002]}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=False),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_identity", return_value={"pid": 41002, "ppid": 41001, "executable": "/usr/sbin/mosquitto", "cmdline": ["mosquitto", "-c", str(config.mqtt_config_path)]}),
            ):
                evidence = demo._mqtt_readiness_evidence(config, record)
        self.assertTrue(evidence["listener_count"] == 1)
        self.assertFalse(evidence["tcp_ready"])
        self.assertFalse(evidence["ready"])

    def test_exact_supervisor_child_lineage_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            record["mqtt_child"] = child
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": [41002]}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=child),
            ):
                evidence = demo._mqtt_readiness_evidence(config, record)
            child["ppid"] = 41003
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": [41002]}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=child),
            ):
                foreign = demo._mqtt_readiness_evidence(config, record)
        self.assertTrue(evidence["listener_lineage_valid"])
        self.assertTrue(evidence["ready"])
        self.assertFalse(foreign["listener_lineage_valid"])
        self.assertFalse(foreign["ready"])

    def test_mqtt_start_requests_supervisor_child_pid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            argv = demo._service_argv(config, "mqtt", run_id="mqtt-test")
        self.assertEqual(
            argv[-2:],
            ["--child-state-path", str(config.mqtt_state_path.with_name("mqtt-child.json"))],
        )

    def test_child_contract_rejects_unexpected_executable_or_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            child = self.make_child(config)
            with mock.patch.object(
                demo,
                "_mosquitto_executable_identity",
                return_value=(child["executable"], child["executable_sha256"]),
            ):
                self.assertTrue(
                    demo._mqtt_child_contract_shape(
                        config,
                        child,
                        supervisor_pid=41001,
                        run_id="mqtt-test",
                    )
                )
                unexpected_path = {**child, "executable": "/tmp/unexpected-mosquitto"}
                unexpected_digest = {**child, "executable_sha256": "0" * 64}
                self.assertFalse(
                    demo._mqtt_child_contract_shape(
                        config,
                        unexpected_path,
                        supervisor_pid=41001,
                        run_id="mqtt-test",
                    )
                )
                self.assertFalse(
                    demo._mqtt_child_contract_shape(
                        config,
                        unexpected_digest,
                        supervisor_pid=41001,
                        run_id="mqtt-test",
                    )
                )

    def test_child_contract_rejects_pid_start_command_and_command_hash_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            child = self.make_child(config)
            with (
                mock.patch.object(
                    demo,
                    "_mosquitto_executable_identity",
                    return_value=(child["executable"], child["executable_sha256"]),
                ),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=child),
            ):
                for field, value in (
                    ("pid", 41003),
                    ("ppid", 41003),
                    ("start_ticks", 43),
                    ("cmdline", [child["executable"], "-c", "/tmp/other.conf"]),
                    ("cmdline_sha256", "different-child-digest"),
                ):
                    with self.subTest(field=field):
                        candidate = {**child, field: value}
                        self.assertFalse(
                            demo._mqtt_child_contract_live(
                                config,
                                candidate,
                                require_direct=True,
                            )
                        )

    def test_full_stack_mqtt_start_requires_child_contract_for_listener_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            spec = demo.ServiceSpec(
                "mqtt",
                demo.ROOT,
                "managed_mosquitto_supervisor.py",
                (config.mqtt_port,),
                config.mqtt_log_path,
            )
            record = self.make_record(config)
            evidence = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=True,
                listener_lineage_valid=True,
                ready=True,
            )
            with (
                mock.patch.object(demo, "_validate_source", return_value={"branch": "main", "head": "test", "tree": []}),
                mock.patch.object(demo, "_specs", return_value={"mqtt": spec}),
                mock.patch.object(demo, "_validate_resource_manifest", return_value={}),
                mock.patch.object(demo, "_reconcile_archived_callback_socket"),
                mock.patch.object(demo, "_assert_start_ports_clear"),
                mock.patch.object(demo, "_external_dependency_ready"),
                mock.patch.object(demo, "_base_env", return_value={}),
                mock.patch.object(demo, "_start_process", return_value=record) as start_process,
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_record_mqtt_child_contract", return_value=self.make_child(config)) as child_contract,
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence),
                mock.patch.object(demo, "_wait_for", return_value=True),
                mock.patch.object(demo, "_attach_listeners") as attach_listeners,
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "runtime_health", return_value={"readiness": "BACKEND_READY_WAITING_ANDROID"}),
            ):
                result = demo.start(config)

        self.assertEqual(result["state"], "BACKEND_READY_WAITING_ANDROID")
        argv = start_process.call_args.args[1]
        self.assertIn("--run-id", argv)
        self.assertIn("--child-state-path", argv)
        child_contract.assert_called_once_with(config, record)
        attach_listeners.assert_called_once_with(record, config=config)

    def test_mqtt_listener_attachment_rejects_unverified_listener(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            evidence = self.make_evidence(
                config,
                listener_count=1,
                pids=[],
                tcp_ready=True,
                supervisor_valid=True,
                listener_lineage_valid=False,
                ready=False,
            )
            with mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=evidence):
                with self.assertRaisesRegex(demo.DemoError, "exact child"):
                    demo._attach_listeners(record, config=config)

    def test_owned_child_contract_survives_unreadable_proc_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            demo._atomic_json(demo._mqtt_child_state_path(config), child)
            current_child = {**child, "identity_source": "limited_proc"}
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": []}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_identity", side_effect=PermissionError),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=current_child),
            ):
                evidence = demo._mqtt_readiness_evidence(config, record)
        self.assertTrue(evidence["listener_lineage_valid"])
        self.assertTrue(evidence["ready"])
        self.assertTrue(evidence["listener_pid_matches_child"])
        self.assertEqual(evidence["listener_pids"], [])
        self.assertEqual(evidence["mosquitto_pids"], [])
        self.assertEqual(evidence["child_pid"], 41002)

    def test_listener_pid_must_match_the_recorded_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            record["mqtt_child"] = child
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": [41003]}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=child),
            ):
                evidence = demo._mqtt_readiness_evidence(config, record)
        self.assertFalse(evidence["listener_lineage_valid"])
        self.assertFalse(evidence["ready"])
        self.assertEqual(evidence["listener_pids"], [41003])
        self.assertEqual(evidence["mosquitto_pids"], [])

    def test_dead_recorded_child_cannot_pass_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            record["mqtt_child"] = child
            with (
                mock.patch.object(demo, "_listener_endpoints", return_value=[{"address": "127.0.0.1", "port": 1883, "pids": [41002]}]),
                mock.patch.object(demo, "_mqtt_tcp_ready", return_value=True),
                mock.patch.object(demo, "_identity_matches", return_value=True),
                mock.patch.object(demo, "_mqtt_limited_identity", side_effect=FileNotFoundError),
            ):
                evidence = demo._mqtt_readiness_evidence(config, record)
        self.assertFalse(evidence["child_contract_valid"])
        self.assertFalse(evidence["ready"])

    def test_recorded_child_contract_can_be_stopped_after_supervisor_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            child = self.make_child(config)
            record["mqtt_child"] = child
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=record)
            occupied = self.make_evidence(
                config,
                listener_count=1,
                pids=[41002],
                tcp_ready=True,
                supervisor_valid=False,
                listener_lineage_valid=False,
            )
            stopped = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=[occupied, stopped]),
                mock.patch.object(demo, "_identity_matches", return_value=False),
                mock.patch.object(demo, "_mqtt_limited_identity", return_value=child),
                mock.patch.object(demo, "_wait_for", return_value=True),
                mock.patch.object(demo, "_listener_count", return_value=0),
                mock.patch.object(demo.os, "kill") as kill,
            ):
                result = demo.mqtt_only_stop(config)
        self.assertEqual(result["state"], demo.STATE_STOPPED)
        kill.assert_called_once_with(41002, demo.signal.SIGTERM)
        self.assertFalse(config.mqtt_state_path.exists())

    def test_starting_stop_terminates_only_recorded_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            self.write_state(config, status=demo.STATE_STARTING, record=record)
            owned = self.make_evidence(config, listener_count=0, supervisor_valid=True)
            stopped = self.make_evidence(config)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", side_effect=[owned, stopped]),
                mock.patch.object(demo, "_attach_descendants"),
                mock.patch.object(demo, "_stop_record", return_value="stopped_term") as stop_record,
            ):
                result = demo.mqtt_only_stop(config)
        self.assertEqual(result["state"], demo.STATE_STOPPED)
        stop_record.assert_called_once_with(record, timeout_seconds=30)
        self.assertFalse(config.mqtt_state_path.exists())

    def test_invalid_live_record_is_preserved_for_manual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            record["leader"]["cmdline"] = ["/usr/bin/python3", "/tmp/other.py"]
            self.write_state(config, status=demo.MQTT_STATE_RUNNING, record=record)
            with (
                mock.patch.object(demo, "_mqtt_readiness_evidence", return_value=self.make_evidence(config)),
                mock.patch.object(demo, "_identity_matches", return_value=True),
            ):
                with self.assertRaisesRegex(demo.DemoError, "OWNERSHIP_UNRESOLVED"):
                    demo.mqtt_only_stop(config)
            state_remains = config.mqtt_state_path.exists()
        self.assertTrue(state_remains)

    def test_unsupported_state_is_preserved_for_manual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            demo._atomic_json(
                config.mqtt_state_path,
                {
                    "schema_version": "temiagent.demo_lifecycle.v2",
                    "scope": "mqtt",
                    "status": "AMBIGUOUS",
                    "services": {},
                },
            )
            with self.assertRaisesRegex(demo.DemoError, "MQTT_STATE_STATUS_UNSUPPORTED"):
                demo.mqtt_only_stop(config)
            state_remains = config.mqtt_state_path.exists()
        self.assertTrue(state_remains)

    def test_supervisor_identity_requires_exact_script_and_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            record = self.make_record(config)
            with mock.patch.object(demo, "_identity_matches", return_value=True):
                self.assertTrue(demo._mqtt_supervisor_valid(config, record))
                record["leader"]["cmdline"][1] = "/tmp/other/tools/managed_mosquitto_supervisor.py"
                self.assertFalse(demo._mqtt_supervisor_valid(config, record))

    def test_mqtt_source_policy_allows_unrelated_docs_but_full_policy_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(self.make_managed_config(Path(temporary)))
            source = {"root": str(demo.ROOT), "branch": "main", "head": "test"}
            with (
                mock.patch.object(demo, "_mqtt_only_source_roots", return_value=[demo.ROOT.resolve()]),
                mock.patch.object(demo, "_source_record_at", return_value=source),
                mock.patch.object(demo, "_git_status_paths", return_value={"docs/README.md"}),
            ):
                validated = demo._validate_mqtt_only_source(config)
        self.assertEqual(validated["checked_roots"][0]["checked_files"], sorted(demo.MQTT_ONLY_RUNTIME_FILES))
        dirty_source = {"branch": "main", "head": "test", "tree": [" M docs/README.md"]}
        with (
            mock.patch.object(demo, "_source_record", return_value=dirty_source),
            mock.patch.object(demo, "_git", return_value=""),
        ):
            with self.assertRaisesRegex(demo.DemoError, "non-runtime dirty files"):
                demo._validate_source(config)

    def test_mqtt_source_policy_rejects_each_critical_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base_config = demo.load_config(self.make_managed_config(Path(temporary)))
            source = {"root": str(demo.ROOT), "branch": "main", "head": "test"}
            for path in (*demo.MQTT_ONLY_RUNTIME_FILES, "mqtt/mosquitto.conf"):
                with self.subTest(path=path):
                    config = (
                        replace(base_config, mqtt_config_path=demo.ROOT / "mqtt" / "mosquitto.conf")
                        if path == "mqtt/mosquitto.conf"
                        else base_config
                    )
                    with (
                        mock.patch.object(demo, "_mqtt_only_source_roots", return_value=[demo.ROOT.resolve()]),
                        mock.patch.object(demo, "_source_record_at", return_value=source),
                        mock.patch.object(demo, "_git_status_paths", return_value={path}),
                    ):
                        with self.assertRaisesRegex(demo.DemoError, "MQTT_ONLY_SOURCE_DIRTY"):
                            demo._validate_mqtt_only_source(config)

    def test_primary_worktree_is_the_mqtt_default_authority(self) -> None:
        self.assertEqual(
            demo.canonical_mqtt_runtime_root(),
            demo.CANONICAL_MQTT_SOURCE_ROOT / ".runtime" / "demo",
        )
        self.assertEqual(
            demo.canonical_mqtt_config_path(),
            demo.canonical_mqtt_runtime_root() / "demo.env",
        )

    def test_custom_private_config_cannot_reuse_canonical_mqtt_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_managed_config(Path(temporary))
            content = config_path.read_text(encoding="utf-8")
            content = content.replace(
                f"TEMIAGENT_RUNTIME_ROOT={Path(temporary) / 'runtime'}",
                f"TEMIAGENT_RUNTIME_ROOT={demo.canonical_mqtt_runtime_root()}",
            )
            config_path.write_text(content, encoding="utf-8")
            config_path.chmod(0o600)
            with self.assertRaisesRegex(demo.DemoError, "canonical MQTT runtime"):
                demo.load_config(config_path, mqtt_only=True)

    def test_mqtt_only_rejects_an_executing_worktree_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.make_managed_config(Path(temporary))
            executing_runtime = Path(temporary) / "executing-worktree" / ".runtime" / "demo"
            primary_runtime = Path(temporary) / "primary-worktree" / ".runtime" / "demo"
            with (
                mock.patch.object(demo, "CANONICAL_RUNTIME_ROOT", executing_runtime),
                mock.patch.object(demo, "CANONICAL_CONFIG_PATH", executing_runtime / "demo.env"),
                mock.patch.object(demo, "CANONICAL_MQTT_RUNTIME_ROOT", primary_runtime),
                mock.patch.object(demo, "CANONICAL_MQTT_CONFIG_PATH", primary_runtime / "demo.env"),
            ):
                content = config_path.read_text(encoding="utf-8").replace(
                    str(Path(temporary) / "runtime"),
                    str(demo.canonical_runtime_root()),
                )
                config_path.write_text(content, encoding="utf-8")
                config_path.chmod(0o600)
                with self.assertRaisesRegex(demo.DemoError, "MQTT-only runtime"):
                    demo.load_config(config_path, mqtt_only=True)


class DemoLifecycleRecordTests(unittest.TestCase):
    def test_pre_restart_evidence_preserves_exact_owned_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            expected_services = {
                "bridge": {"name": "bridge", "leader": {"pid": 741, "start_ticks": 12}, "members": [], "ports": []}
            }
            demo._atomic_json(
                config.state_path,
                {"run_id": "demo-existing", "status": "running", "services": expected_services},
            )
            with (
                mock.patch.object(demo, "_source_record", return_value={"branch": "main", "head": "test"}),
                mock.patch.object(demo, "_listener_identities", return_value=[]),
                mock.patch.object(demo, "_broker_sessions", return_value={"loopback_sessions": 1, "remote_sessions": 1}),
                mock.patch.object(demo, "_http_json", return_value={"status": "ok"}),
            ):
                path = demo._write_pre_restart_evidence(config)
            evidence = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["owned_processes_before_stop"], {"run_id": "demo-existing", "status": "running", "services": expected_services})

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

    def test_trace_export_manifest_can_reconcile_its_recorded_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = demo.load_config(DemoLifecycleConfigTests().make_config(Path(temporary)))
            demo.ensure_runtime_layout(config)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(config.callback_socket))
            try:
                manifest = config.runtime_root / "state" / "last-run" / "exports" / "older" / "manifest.json"
                demo._atomic_json(manifest, {"health": {"callback_socket": {"path": str(config.callback_socket)}}, "process_inventory": {"bridge": {"name": "bridge", "leader": {"pid": 736}, "members": []}}})
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
