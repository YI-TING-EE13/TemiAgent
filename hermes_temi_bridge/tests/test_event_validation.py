import copy
import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.event_models import ASRFinalEvent, EventValidationError
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


if __name__ == "__main__":
    unittest.main()
