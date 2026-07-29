import copy
import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.event_models import ASRFinalEvent, EventValidationError, PerceptionAbnormalEvent
from hermes_temi_bridge.hermes_client import HermesResponse
from hermes_temi_bridge.idempotency import TTLProcessedEventCache
from hermes_temi_bridge.image_resolver import ImageValidationError, validate_image_file
from hermes_temi_bridge.logging_utils import EventJsonlLogger
from hermes_temi_bridge.main import HermesTemiBridgeService

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def rewrite_frame_paths(payload, bridge_root: Path):
    event_id = payload["event_id"]
    for frame in payload["vision"]["frames"]:
        filename = {
            "t_minus_1000": "frame_t_minus_1000.jpg",
            "t_minus_500": "frame_t_minus_500.jpg",
            "t": "frame_t.jpg",
        }[frame["name"]]
        frame_path = bridge_root / "events" / payload["robot_id"] / event_id / filename
        frame["path"] = frame_path.as_posix()
    return payload


def create_images_for_payload(payload):
    for frame in payload["vision"]["frames"]:
        path = Path(frame["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-jpeg")


def make_abnormal_payload(bridge_root: Path, event_id: str = "evt_abnormal_001"):
    frame_paths = []
    event_dir = bridge_root / "abnormal_events" / "temi-01" / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    for index in range(8):
        path = event_dir / f"frame_{index:03d}.jpg"
        path.write_bytes(b"fake-jpeg")
        frame_paths.append(path.as_posix())
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": "temi-01",
        "type": "perception.abnormal",
        "timestamp_ms": 1778499000200,
        "observation": {
            "action_name": "fights",
            "reason": "Two people are striking each other across multiple frames.",
        },
        "evidence": {
            "frame_paths": frame_paths,
        },
        "context": {
            "source": "temi_video_action_tester",
        },
    }


def write_seed_memory(memory_root: Path):
    memory_root.mkdir(parents=True, exist_ok=True)
    (memory_root / "profile.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "user_id": "elder_demo_001",
                "preferred_name": "王先生",
                "gender": "male",
                "language": "zh-TW",
                "care_preferences": {"speak_style": "溫和、簡短、清楚"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (memory_root / "reminders.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "reminders": [
                    {
                        "reminder_id": "rem_morning_medication",
                        "type": "medication",
                        "title": "早餐後服藥",
                        "time": "08:30",
                        "status": "active",
                        "requires_confirmation": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (memory_root / "daily_state.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "date": "2026-06-10",
                "risk_state": "normal",
                "active_reminders": ["rem_morning_medication"],
                "recent_event_ids": ["evt_prior_l2"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with (memory_root / "event_log.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_id": "evt_prior_l2",
                    "timestamp": "2026-06-10T08:00:00+00:00",
                    "source": "hermes_temi_bridge",
                    "asr_text": "我有點不舒服",
                    "perception": {"intent": "report_discomfort"},
                    "risk": {"home_esi_level": "L2", "reason": "使用者表示不舒服，需要追問。"},
                    "actions_taken": ["ask_clarification", "log_event"],
                    "outcome": "waiting_for_user_response",
                },
                ensure_ascii=False,
            )
            + "\n"
        )


class MockMqtt:
    def __init__(self):
        self.published = []

    def publish_command(self, robot_id, payload):
        self.published.append((robot_id, payload))


class MockHermes:
    def __init__(self, raw_output):
        self.raw_output = raw_output
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        return HermesResponse(raw_output=self.raw_output, latency_ms=12)


class EventValidationTests(unittest.TestCase):
    def test_valid_asr_event_should_pass(self):
        payload = load_fixture("asr_final_valid.json")
        event = ASRFinalEvent.from_payload(payload, ("temi-01",))
        self.assertEqual(event.event_id, "evt_20260511_000001")
        self.assertEqual(event.asr_text, "幫我看看桌上的東西是什麼")
        self.assertEqual({frame.name for frame in event.frames}, {"t_minus_1000", "t_minus_500", "t"})

    def test_valid_abnormal_event_should_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_abnormal_payload(Path(tmp) / "temi_shared")
            event = PerceptionAbnormalEvent.from_payload(payload, ("temi-01",))

            self.assertEqual(event.event_id, "evt_abnormal_001")
            self.assertEqual(event.action_name, "fights")
            self.assertIn("striking", event.reason)
            self.assertEqual(len(event.frames), 8)

    def test_abnormal_event_missing_reason_should_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_abnormal_payload(Path(tmp) / "temi_shared")
            del payload["observation"]["reason"]
            with self.assertRaisesRegex(EventValidationError, "missing_reason"):
                PerceptionAbnormalEvent.from_payload(payload, ("temi-01",))

    def test_missing_event_id_should_fail(self):
        payload = load_fixture("asr_final_valid.json")
        del payload["event_id"]
        with self.assertRaisesRegex(EventValidationError, "missing_event_id"):
            ASRFinalEvent.from_payload(payload, ("temi-01",))

    def test_empty_asr_text_should_fail(self):
        payload = load_fixture("asr_final_valid.json")
        payload["asr"]["text"] = "   "
        with self.assertRaisesRegex(EventValidationError, "empty_asr_text"):
            ASRFinalEvent.from_payload(payload, ("temi-01",))

    def test_missing_image_should_fail(self):
        with self.assertRaises(ImageValidationError) as context:
            validate_image_file("/var/lib/temi_shared/events/missing.jpg", 8)
        self.assertEqual(context.exception.reason, "missing_image")

    def test_duplicated_event_id_should_be_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), bridge_root)
            create_images_for_payload(payload)
            hermes_raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
            mqtt = MockMqtt()
            config = BridgeConfig(
                temi_shared_bridge_path=bridge_root.as_posix(),
                temi_shared_hermes_path="/shared/temi",
                log_dir=(root / "logs").as_posix(),
            )
            service = HermesTemiBridgeService(
                config,
                mqtt,
                MockHermes(hermes_raw),
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )
            first = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))
            second = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))
            self.assertEqual(first["status"], "success")
            self.assertEqual(second, {"status": "ignored", "reason": "duplicate_event_id"})
            self.assertEqual(len(mqtt.published), 1)

    def test_abnormal_event_creates_pending_care_speak_without_invoking_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            payload = make_abnormal_payload(bridge_root)
            hermes_raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
            hermes_raw = hermes_raw.replace("evt_20260511_000001", payload["event_id"])
            mqtt = MockMqtt()
            hermes = MockHermes(hermes_raw)
            config = BridgeConfig(
                temi_shared_bridge_path=bridge_root.as_posix(),
                temi_shared_hermes_path="/shared/temi",
                log_dir=(root / "logs").as_posix(),
                memory_dir=(root / "memory").as_posix(),
            )
            service = HermesTemiBridgeService(
                config,
                mqtt,
                hermes,
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(hermes.requests, [])
            self.assertEqual(len(mqtt.published), 1)
            command = mqtt.published[0][1]
            self.assertEqual([action["type"] for action in command["actions"]], ["speak"])
            self.assertIn("需要我幫忙通知", command["actions"][0]["text"])

    def test_abnormal_event_duplicate_should_be_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            payload = make_abnormal_payload(bridge_root)
            hermes_raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
            hermes_raw = hermes_raw.replace("evt_20260511_000001", payload["event_id"])
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=bridge_root.as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                mqtt,
                MockHermes(hermes_raw),
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            first = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", copy.deepcopy(payload))
            second = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", copy.deepcopy(payload))

            self.assertEqual(first["status"], "success")
            self.assertEqual(second, {"status": "ignored", "reason": "duplicate_event_id"})
            self.assertEqual(len(mqtt.published), 1)

    def test_abnormal_event_missing_image_uses_care_safe_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            payload = make_abnormal_payload(bridge_root)
            Path(payload["evidence"]["frame_paths"][0]).unlink()
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=bridge_root.as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                mqtt,
                MockHermes("{}"),
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", payload)

            self.assertEqual(result["status"], "success")
            self.assertEqual([action["type"] for action in mqtt.published[0][1]["actions"]], ["speak"])


    def test_asr_event_builds_care_context_before_hermes_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            memory_root = root / "memory"
            write_seed_memory(memory_root)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), bridge_root)
            payload["asr"]["text"] = "我又不舒服"
            create_images_for_payload(payload)
            hermes_raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
            mqtt = MockMqtt()
            hermes = MockHermes(hermes_raw)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=bridge_root.as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=memory_root.as_posix(),
                ),
                mqtt,
                hermes,
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(len(hermes.requests), 1)
            care_context = hermes.requests[0].care_context
            self.assertIsNotNone(care_context)
            self.assertEqual(care_context["resident"]["display_name"], "王先生")
            self.assertEqual(care_context["active_reminders"][0]["reminder_id"], "rem_morning_medication")
            self.assertEqual(care_context["relevant_events"][0]["event_id"], "evt_prior_l2")

    def test_abnormal_event_keeps_care_context_and_model_out_of_first_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            memory_root = root / "memory"
            write_seed_memory(memory_root)
            payload = make_abnormal_payload(bridge_root)
            hermes_raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
            hermes_raw = hermes_raw.replace("evt_20260511_000001", payload["event_id"])
            mqtt = MockMqtt()
            hermes = MockHermes(hermes_raw)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=bridge_root.as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=memory_root.as_posix(),
                ),
                mqtt,
                hermes,
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(hermes.requests, [])
            self.assertEqual(len(mqtt.published), 1)

    def test_memory_actions_are_not_published_to_mqtt_with_care_context_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_root = root / "temi_shared"
            memory_root = root / "memory"
            write_seed_memory(memory_root)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), bridge_root)
            payload["asr"]["text"] = "我吃完藥了"
            create_images_for_payload(payload)
            hermes_raw = (FIXTURES / "hermes_output_valid_memory_actions.json").read_text(encoding="utf-8")
            mqtt = MockMqtt()
            hermes = MockHermes(hermes_raw)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=bridge_root.as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=memory_root.as_posix(),
                ),
                mqtt,
                hermes,
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual([item["type"] for item in result["memory_action_results"]], ["mark_reminder_done", "log_event"])
            self.assertEqual(len(mqtt.published), 1)
            published_actions = mqtt.published[0][1]["actions"]
            self.assertEqual([action["type"] for action in published_actions], ["speak"])
            self.assertIsNotNone(hermes.requests[0].care_context)


if __name__ == "__main__":
    unittest.main()
