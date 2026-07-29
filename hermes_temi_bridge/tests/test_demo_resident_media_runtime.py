import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.demo_care_memory import seed_demo_care_memory
from hermes_temi_bridge.hermes_media_tool import (
    HermesMediaToolCallback,
    validate_media_tool_call,
)
from hermes_temi_bridge.main import HermesTemiBridgeService
from hermes_temi_bridge.media_callback_socket import (
    MediaCallbackSocketServer,
    invoke_media_callback_socket,
)
from hermes_temi_bridge.resident_context import ResidentContextStore


ROOT = Path(__file__).resolve().parents[2]
RESIDENT_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("demo_resident_server", RESIDENT_PATH)
resident_server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(resident_server)


class RecordingMqtt:
    def __init__(self):
        self.published = []

    def publish_command(self, robot_id, payload):
        self.published.append((robot_id, payload))


def identity(status: str, *, event_id: str = "evt_identity_001"):
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "resident_id": None if status == "unknown" else status,
        "display_name": status,
        "identity_status": status,
        "confidence": 0.95,
        "source": "unknown" if status == "unknown" else "vision_gender_fallback",
        "reason": "synthetic canonical identity result",
        "timestamp": "2026-07-29T10:00:00Z",
    }


def media_result(request, status, *, session_id="session_demo_001"):
    state = {"accepted": None, "started": "playing"}[status]
    return {
        "schema_version": "1.1",
        "message_type": "video.command_result",
        "command_id": request["command_id"],
        "request_id": request["request_id"],
        "event_id": request["event_id"],
        "robot_id": request["robot_id"],
        "command_action": request["action"],
        "video_id": request["video_id"],
        "status": status,
        "terminal": False,
        "playback_session_id": session_id,
        "target_playback_session_id": None,
        "active_playback_session_id": None,
        "playback_state": state,
        "cancelled_by_command_id": None,
        "cancel_reason": None,
        "actor": "remote_command",
        "result_delivery": "original",
        "error_code": None,
        "error_message": None,
        "timestamp": "2026-07-29T10:00:01Z",
    }


class DemoResidentContextTests(unittest.TestCase):
    def test_feature_flags_default_false_and_reject_partial_media_enablement(self):
        self.assertFalse(BridgeConfig().media_v11_enabled)
        self.assertFalse(BridgeConfig().hermes_media_tool_enabled)
        self.assertFalse(BridgeConfig().demo_care_scenario_prompt_enabled)
        self.assertFalse(BridgeConfig().demo_resident_visual_routing_enabled)
        with patch.dict(
            "os.environ",
            {"HERMES_MEDIA_TOOL_ENABLED": "true", "MEDIA_V11_ENABLED": "false"},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "requires MEDIA_V11_ENABLED"):
                BridgeConfig.from_env(Path("/tmp/nonexistent-demo.env"))

    def test_prompt_overlay_is_feature_gated(self):
        self.assertEqual(resident_server._demo_care_overlay(False), "")
        overlay = resident_server._demo_care_overlay(True)
        self.assertIn("王先生", overlay)
        self.assertIn("elderly_hand_exercise", overlay)
        self.assertIn("prior headache report", overlay)
        self.assertIn("Never infer", overlay)

    def test_only_canonical_visual_result_selects_resident(self):
        store = ResidentContextStore(ttl_seconds=300)
        mother = store.update_from_identity_result(
            robot_id="temi-01", payload=identity("mother"), enabled=True
        )
        self.assertEqual(mother.resident_id, "mother")
        self.assertEqual(mother.display_name, "王太太")
        unknown = store.update_from_identity_result(
            robot_id="temi-01",
            payload={**identity("father"), "source": "manual_selection"},
            enabled=True,
        )
        self.assertEqual(unknown.resident_id, "unknown")
        self.assertEqual(unknown.display_name, "未知住民／尚未確認")
        low_confidence = store.update_from_identity_result(
            robot_id="temi-01",
            payload={**identity("father"), "confidence": 0.2},
            enabled=True,
        )
        self.assertEqual(low_confidence.resident_id, "unknown")

    def test_synthetic_seed_partitions_memory_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private_demo_memory"
            first = seed_demo_care_memory(root)
            second = seed_demo_care_memory(root)
            self.assertEqual(first["residents"]["father"]["event_count"], 1)
            self.assertEqual(second["residents"]["father"]["event_count"], 1)
            father_log = (root / "father" / "event_log.jsonl").read_text(encoding="utf-8")
            mother_log = (root / "mother" / "event_log.jsonl").read_text(encoding="utf-8")
            self.assertIn("demo_father_headache_two_days_ago", father_log)
            self.assertEqual(mother_log, "")


class MediaToolCallbackTests(unittest.TestCase):
    def make_callback(self, root):
        mqtt = RecordingMqtt()
        context = ResidentContextStore(ttl_seconds=300)
        context.update_from_identity_result(
            robot_id="temi-01", payload=identity("mother"), enabled=True
        )
        config = BridgeConfig(
            media_v11_enabled=True,
            hermes_media_tool_enabled=True,
            hermes_media_callback_socket=(root / "media.sock").as_posix(),
            demo_care_scenario_prompt_enabled=True,
            demo_resident_visual_routing_enabled=True,
            demo_care_memory_root=(root / "care").as_posix(),
            log_dir=(root / "logs").as_posix(),
        )
        service = HermesTemiBridgeService(config, mqtt, object(), resident_context=context)
        callback = HermesMediaToolCallback(
            service,
            context,
            media_v11_enabled=True,
            hermes_media_tool_enabled=True,
            visual_routing_enabled=True,
        )
        return service, callback, mqtt

    def test_play_tool_uses_bridge_and_fake_broker(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, callback, mqtt = self.make_callback(Path(tmp))
            result = callback.invoke(
                {
                    "event_id": "evt_asr_001",
                    "robot_id": "temi-01",
                    "resident_id": "mother",
                    "action": "play_video",
                    "video_id": "elderly_hand_exercise",
                }
            )
            self.assertEqual(result["status"], "published")
            self.assertEqual(len(mqtt.published), 1)
            request = mqtt.published[0][1]
            self.assertEqual(request["message_type"], "video.command")
            self.assertEqual(request["schema_version"], "1.1")
            self.assertEqual(request["action"], "play_video")
            self.assertEqual(request["video_id"], "elderly_hand_exercise")

            service.handle_command_result(
                "temi/temi-01/cmd/result", media_result(request, "accepted")
            )
            service.handle_command_result(
                "temi/temi-01/cmd/result", media_result(request, "started")
            )
            paused = callback.invoke(
                {
                    "event_id": "evt_asr_002",
                    "robot_id": "temi-01",
                    "resident_id": "mother",
                    "action": "pause_video",
                    "video_id": "elderly_hand_exercise",
                }
            )
            self.assertEqual(paused["status"], "published")
            self.assertEqual(mqtt.published[-1][1]["action"], "pause_video")

    def test_unknown_or_unallowlisted_media_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, callback, mqtt = self.make_callback(Path(tmp))
            bad_url = callback.invoke(
                {
                    "event_id": "evt_asr_001",
                    "robot_id": "temi-01",
                    "resident_id": "mother",
                    "action": "play_video",
                    "video_id": "https://example.invalid/movie.mp4",
                }
            )
            self.assertEqual(bad_url["status"], "rejected")
            self.assertEqual(bad_url["error_code"], "VIDEO_ID_NOT_ALLOWED")
            self.assertEqual(mqtt.published, [])
            with self.assertRaisesRegex(Exception, "hermes_media_tool_disabled"):
                validate_media_tool_call({}, enabled=False)

    def test_unknown_resident_cannot_publish_or_access_private_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, callback, mqtt = self.make_callback(Path(tmp))
            service.resident_context = ResidentContextStore(ttl_seconds=300)
            callback._resident_context = service.resident_context
            blocked = callback.invoke(
                {
                    "event_id": "evt_asr_001",
                    "robot_id": "temi-01",
                    "resident_id": "mother",
                    "action": "play_video",
                    "video_id": "elderly_hand_exercise",
                }
            )
            self.assertEqual(blocked["status"], "rejected")
            self.assertEqual(mqtt.published, [])
            with self.assertRaisesRegex(Exception, "unknown_resident_memory_forbidden"):
                service._memory_store_for(service._active_resident("temi-01"))

    def test_local_socket_is_not_mqtt_and_has_bounded_request_contract(self):
        class Callback:
            def invoke(self, payload):
                return {"status": "published", "echo": payload["action"]}

        with tempfile.TemporaryDirectory() as tmp:
            socket_path = Path(tmp) / "callback.sock"
            server = MediaCallbackSocketServer(socket_path, Callback())
            server.start()
            try:
                response = invoke_media_callback_socket(socket_path, {"action": "play_video"})
            finally:
                server.stop()
        self.assertEqual(response, {"status": "published", "echo": "play_video"})


if __name__ == "__main__":
    unittest.main()
