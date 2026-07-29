import importlib.util
import json
from pathlib import Path
import statistics
import tempfile
import threading
import unittest
from contextlib import contextmanager
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

    def test_unknown_resident_can_publish_generic_media_without_private_memory_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, callback, mqtt = self.make_callback(Path(tmp))
            service.resident_context = ResidentContextStore(ttl_seconds=300)
            callback._resident_context = service.resident_context
            published = callback.invoke(
                {
                    "event_id": "evt_asr_001",
                    "robot_id": "temi-01",
                    "resident_id": "unknown",
                    "action": "play_video",
                    "video_id": "elderly_hand_exercise",
                }
            )
            self.assertEqual(published["status"], "published")
            self.assertEqual(mqtt.published[0][1]["resident_id"], "unknown")
            with self.assertRaisesRegex(Exception, "unknown_resident_memory_forbidden"):
                service._memory_store_for(service._active_resident("temi-01"))

    def test_mother_care_route_keeps_confirmed_resident_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, callback, mqtt = self.make_callback(Path(tmp))
            rejected = callback.invoke(
                {
                    "event_id": "evt_asr_001",
                    "robot_id": "temi-01",
                    "resident_id": "father",
                    "action": "play_video",
                    "video_id": "elderly_hand_exercise",
                }
            )
            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(mqtt.published, [])
            overlay = resident_server._demo_care_overlay(True)
            self.assertIn("validated care-memory action", overlay)
            self.assertIn("explicit no-discomfort response", overlay)
            self.assertIn("explicit consent", overlay)

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

    def test_native_tool_to_unix_socket_to_bridge_uses_no_direct_mqtt(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, callback, mqtt = self.make_callback(Path(tmp))
            socket_path = Path(tmp) / "callback.sock"
            server = MediaCallbackSocketServer(socket_path, callback)
            server.start()
            try:
                media_tools = resident_server._load_resident_media_tools()
                media_tools._callback_socket = socket_path.as_posix()
                with media_tools.invocation_context(
                    {"event_id": "evt_native_001", "robot_id": "temi-01", "resident_id": "unknown"}
                ):
                    result = media_tools.invoke_registered_media_tool(
                        "play_video", {"video_id": "elderly_hand_exercise"}
                    )
            finally:
                server.stop()
        self.assertEqual(result["status"], "published")
        self.assertEqual(mqtt.published[0][1]["message_type"], "video.command")
        source = (ROOT / "tools" / "hermes_resident_media_tools.py").read_text(encoding="utf-8")
        self.assertNotIn("import paho", source)
        self.assertNotIn("publish_command", source)


class FakeNativeMediaTools:
    def __init__(self, response):
        self.response = response
        self.calls = []

    @contextmanager
    def invocation_context(self, context):
        self.current_context = dict(context)
        yield
        self.current_context = None

    def invoke_registered_media_tool(self, action, arguments):
        self.calls.append((action, arguments, self.current_context))
        return dict(self.response)


class FakeAgent:
    def __init__(self):
        self.calls = []

    def chat(self, prompt):
        self.calls.append(prompt)
        return "model-path-output"


def resident_for_fast_path(*, enabled=True, callback=None):
    resident = object.__new__(resident_server.ResidentHermes)
    resident._lock = threading.Lock()
    resident.request_count = 0
    resident.media_fast_path_enabled = enabled
    resident._media_tools = FakeNativeMediaTools(
        callback or {"status": "published", "command_id": "cmd_fast_001"}
    )
    resident._agent = FakeAgent()
    return resident


class DeterministicMediaFastPathTests(unittest.TestCase):
    def test_matcher_handles_reviewed_variants_and_exact_normalization_only(self):
        cases = {
            "小安小安，請幫我播放手部運動影片。": "play_video",
            "播放手部運動影片": "play_video",
            "我要做手部運動": "play_video",
            "暫停影片": "pause_video",
            "先暫停": "pause_video",
            "繼續播放影片": "resume_video",
            "恢復播放": "resume_video",
            "停止影片": "stop_video",
            "不要播了": "stop_video",
        }
        for transcript, action in cases.items():
            with self.subTest(transcript=transcript):
                intent = resident_server.match_media_intent(transcript)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.action, action)
                self.assertEqual(intent.video_id, "elderly_hand_exercise")
        for transcript in (
            "播放新聞",
            "播放 https://example.invalid/video.mp4",
            "播放 /sdcard/video.mp4",
            "播放腿部運動影片",
            "幫我找一部影片",
        ):
            with self.subTest(transcript=transcript):
                self.assertIsNone(resident_server.match_media_intent(transcript))

    def test_fast_path_uses_native_tool_before_model_and_acknowledges_only_after_publish(self):
        resident = resident_for_fast_path()
        result = resident.invoke(
            "full prompt that must not reach the model",
            {"event_id": "evt_fast_001", "robot_id": "temi-01", "resident_id": "unknown"},
            asr_text="小安小安，請幫我播放手部運動影片。",
        )
        output = json.loads(result["raw_output"])
        self.assertEqual(resident._agent.calls, [])
        self.assertEqual(resident._media_tools.calls[0][0], "play_video")
        self.assertEqual(resident._media_tools.calls[0][1], {"video_id": "elderly_hand_exercise"})
        self.assertEqual(output["actions"][0]["text"], "好的，現在為您播放手部運動影片。")
        self.assertEqual(result["dispatch_metadata"]["dispatch_mode"], "deterministic_media_fast_path")
        self.assertEqual(result["dispatch_metadata"]["callback_status"], "published")
        self.assertEqual(result["dispatch_metadata"]["bridge_command_id"], "cmd_fast_001")

    def test_fast_path_rejection_never_claims_playback(self):
        resident = resident_for_fast_path(callback={"status": "rejected", "error_code": "VIDEO_ID_NOT_ALLOWED"})
        result = resident.invoke(
            "ignored on matched fast path",
            {"event_id": "evt_fast_002", "robot_id": "temi-01", "resident_id": "unknown"},
            asr_text="播放手部運動影片",
        )
        output = json.loads(result["raw_output"])
        self.assertEqual(output["actions"][0]["text"], "抱歉，目前無法播放影片，請稍後再試。")
        self.assertEqual(result["dispatch_metadata"]["callback_status"], "rejected")
        self.assertIsNone(result["dispatch_metadata"]["bridge_command_id"])

    def test_flags_fail_closed_and_nonmatches_keep_model_flow(self):
        disabled = resident_for_fast_path(enabled=False)
        result = disabled.invoke(
            "llm prompt", {"event_id": "evt_fast_003", "robot_id": "temi-01"}, asr_text="播放手部運動影片"
        )
        self.assertEqual(result["raw_output"], "model-path-output")
        self.assertEqual(disabled._media_tools.calls, [])
        unavailable = resident_for_fast_path(enabled=True)
        unavailable._media_tools = None
        unavailable_result = unavailable.invoke(
            "llm prompt",
            {"event_id": "evt_fast_003b", "robot_id": "temi-01"},
            asr_text="播放手部運動影片",
        )
        self.assertEqual(unavailable_result["raw_output"], "model-path-output")
        enabled = resident_for_fast_path(enabled=True)
        nonmatch = enabled.invoke(
            "llm prompt", {"event_id": "evt_fast_004", "robot_id": "temi-01"}, asr_text="播放新聞"
        )
        self.assertEqual(nonmatch["raw_output"], "model-path-output")
        self.assertEqual(enabled._media_tools.calls, [])

    def test_fake_native_callback_latency_p95_is_below_target(self):
        resident = resident_for_fast_path()
        samples = []
        for index in range(50):
            result = resident.invoke(
                "ignored",
                {"event_id": f"evt_latency_{index}", "robot_id": "temi-01", "resident_id": "unknown"},
                asr_text="播放手部運動影片",
            )
            samples.append(result["dispatch_metadata"]["dispatch_latency_ms"])
        p95 = statistics.quantiles(samples, n=20, method="inclusive")[18]
        self.assertLess(p95, 300, f"fake-callback p95={p95}ms")


if __name__ == "__main__":
    unittest.main()
