import copy
import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.care_confirmation import PendingCareConfirmationStore, classify_care_confirmation_response
from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.hermes_client import HermesResponse
from hermes_temi_bridge.idempotency import TTLProcessedEventCache
from hermes_temi_bridge.main import HermesTemiBridgeService


FIXTURES = Path(__file__).parent / "fixtures"


class MockMqtt:
    def __init__(self):
        self.published = []

    def publish_command(self, robot_id, payload):
        self.published.append((robot_id, payload))


class MockHermes:
    def __init__(self):
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        return HermesResponse(
            raw_output=json.dumps(
                {
                    "schema_version": "1.0",
                    "event_id": request.event_id,
                    "robot_id": request.robot_id,
                    "confidence": 1.0,
                    "cognitive_state": {"home_esi_level": "Normal", "risk_reason": "test"},
                    "reasoning_summary": "test",
                    "actions": [{"action_id": "act_001", "type": "speak", "text": "一般回覆"}],
                },
                ensure_ascii=False,
            ),
            latency_ms=0,
        )


def make_abnormal(root: Path, event_id: str = "evt_abnormal_care") -> dict:
    paths = []
    for index in range(2):
        path = root / "abnormal_events" / "temi-01" / event_id / f"frame_{index:03d}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpeg")
        paths.append(path.as_posix())
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": "temi-01",
        "type": "perception.abnormal",
        "timestamp_ms": 1_700_000_000_000,
        "observation": {"action_name": "falls down", "reason": "person on the floor"},
        "evidence": {"frame_paths": paths},
    }


def make_asr(root: Path, event_id: str, text: str, confidence: float = 0.95) -> dict:
    payload = json.loads((FIXTURES / "asr_final_valid.json").read_text(encoding="utf-8"))
    payload["event_id"] = event_id
    payload["asr"]["text"] = text
    payload["asr"]["confidence"] = confidence
    for frame in payload["vision"]["frames"]:
        path = root / "events" / "temi-01" / event_id / f"{frame['name']}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpeg")
        frame["path"] = path.as_posix()
    return payload


class AbnormalCareConfirmationTests(unittest.TestCase):
    def make_service(self, root: Path):
        mqtt = MockMqtt()
        hermes = MockHermes()
        service = HermesTemiBridgeService(
            BridgeConfig(
                temi_shared_bridge_path=root.as_posix(),
                temi_shared_hermes_path="/shared/temi",
                memory_dir=(root / "memory").as_posix(),
                log_dir=(root / "logs").as_posix(),
                abnormal_care_confirmation_ttl_seconds=60,
            ),
            mqtt,
            hermes,
            TTLProcessedEventCache(600),
        )
        return service, mqtt, hermes

    def test_first_turn_for_all_canonical_categories_is_one_care_speak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, category in enumerate(("falls down", "lies on the floor", "fights")):
                service, mqtt, hermes = self.make_service(root / str(index))
                payload = make_abnormal(root / str(index), f"evt_care_{index}")
                payload["observation"]["action_name"] = category
                result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", payload)
                self.assertEqual(result["care_confirmation"], "pending")
                self.assertEqual(hermes.requests, [])
                self.assertEqual([action["type"] for action in mqtt.published[0][1]["actions"]], ["speak"])
                self.assertNotIn("不支援", mqtt.published[0][1]["actions"][0]["text"])

    def test_affirmative_receipt_uses_existing_alert_without_duplicate_notification_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, hermes = self.make_service(root)
            abnormal = make_abnormal(root)
            abnormal["notification"] = {
                "immediate_alert": {"transport": "discord_webhook", "status": "delivered", "target_class": "unverified_direct_alert"}
            }
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            result = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_yes", "請通知家人")
            )
            self.assertEqual(result["care_confirmation"], "notification_already_sent")
            self.assertEqual(hermes.requests, [])
            self.assertEqual(len(mqtt.published), 2)
            self.assertEqual([action["type"] for action in mqtt.published[-1][1]["actions"]], ["speak"])

    def test_decline_and_ambiguous_answers_resolve_without_notification_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, _ = self.make_service(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", make_abnormal(root))
            ambiguous = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_ambiguous", "嗯")
            )
            self.assertEqual(ambiguous["care_confirmation"], "pending")
            declined = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_no", "不用了")
            )
            self.assertEqual(declined["care_confirmation"], "declined")
            self.assertTrue(all(action["type"] == "speak" for _, command in mqtt.published for action in command["actions"]))

    def test_low_confidence_is_not_treated_as_consent_and_unrelated_asr_reaches_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _, hermes = self.make_service(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", make_abnormal(root))
            low_confidence = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_low_confidence", "要", confidence=0.1)
            )
            self.assertEqual(low_confidence["care_confirmation"], "pending")
            unrelated = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_unrelated", "今天天氣如何")
            )
            self.assertEqual(unrelated["status"], "success")
            self.assertEqual(len(hermes.requests), 1)

    def test_store_expiry_and_classification_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PendingCareConfirmationStore(Path(tmp), ttl_seconds=1)
            store.create(
                event_id="evt_expired", robot_id="temi-01", abnormal_category="falls down",
                event_timestamp_ms=1, immediate_alert=None, created_at_ms=1,
            )
            self.assertIsNone(store.active_for_robot("temi-01", at_ms=2_000))
            self.assertEqual(classify_care_confirmation_response("要", 0.1, 0.7), "ambiguous")
            self.assertEqual(classify_care_confirmation_response("不用了", 0.9, 0.7), "declined")
            self.assertEqual(classify_care_confirmation_response("請通知家人", 0.9, 0.7), "accepted")


if __name__ == "__main__":
    unittest.main()
