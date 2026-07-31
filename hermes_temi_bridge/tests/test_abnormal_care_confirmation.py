import copy
import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.care_confirmation import (
    PendingCareConfirmationStore,
    classify_care_confirmation_response,
    classify_care_episode_response,
)
from hermes_temi_bridge.care_episode import AWAITING_FIRST_RESPONSE, ESCALATION_SENT, NO_RESPONSE, RESOLVED
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
                abnormal_notification_mode="demo_mock",
                demo_notification_mock_enabled=True,
                demo_notification_receipt_enabled=True,
                demo_test_event_ingress_enabled=True,
            ),
            mqtt,
            hermes,
            TTLProcessedEventCache(600),
        )
        return service, mqtt, hermes

    def test_first_turn_for_all_canonical_categories_alerts_then_invokes_hermes_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, category in enumerate(("falls down", "lies on the floor", "fights")):
                service, mqtt, hermes = self.make_service(root / str(index))
                payload = make_abnormal(root / str(index), f"evt_care_{index}")
                payload["observation"]["action_name"] = category
                result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", payload)
                self.assertEqual(result["care_episode"], AWAITING_FIRST_RESPONSE)
                self.assertEqual(result["notification_receipt"]["status"], "mock_delivered")
                self.assertEqual(len(hermes.requests), 1)
                self.assertEqual([action["type"] for action in mqtt.published[0][1]["actions"]], ["speak"])
                self.assertNotIn("不支援", mqtt.published[0][1]["actions"][0]["text"])

    def test_resident_needs_assistance_creates_one_status_update_and_continues_care(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, hermes = self.make_service(root)
            abnormal = make_abnormal(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            result = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_yes", "請通知家人")
            )
            self.assertEqual(result["care_episode"], AWAITING_FIRST_RESPONSE)
            self.assertEqual(result["response_class"], "needs_assistance")
            self.assertEqual(result["notification_receipt"]["status"], "mock_delivered")
            self.assertEqual(len(hermes.requests), 2)
            self.assertEqual(len(mqtt.published), 2)
            self.assertEqual([action["type"] for action in mqtt.published[-1][1]["actions"]], ["speak"])
            episode = service.care_episode_store.get("evt_abnormal_care")
            self.assertEqual(episode.notification_stages["status_update"]["receipt"]["status"], "mock_delivered")

            duplicate_stage = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_need_again", "我還是需要幫忙")
            )
            self.assertEqual(duplicate_stage["notification_receipt"]["failure_code"], "DEMO_MOCK_DELIVERED")
            episode = service.care_episode_store.get("evt_abnormal_care")
            self.assertEqual(len(episode.notification_stages), 2)

    def test_ambiguous_and_okay_answers_keep_the_episode_active_until_a_short_recheck(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, _ = self.make_service(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", make_abnormal(root))
            ambiguous = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_ambiguous", "嗯")
            )
            self.assertEqual(ambiguous["care_episode"], AWAITING_FIRST_RESPONSE)
            okay = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_okay", "我沒事")
            )
            self.assertEqual(okay["care_episode"], AWAITING_FIRST_RESPONSE)
            confirmed = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_follow_okay_confirmed", "我真的沒事")
            )
            self.assertEqual(confirmed["care_episode"], RESOLVED)
            self.assertTrue(all(action["type"] == "speak" for _, command in mqtt.published for action in command["actions"]))

    def test_low_confidence_is_not_treated_as_consent_and_unrelated_asr_reaches_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _, hermes = self.make_service(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", make_abnormal(root))
            low_confidence = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_low_confidence", "要", confidence=0.1)
            )
            self.assertEqual(low_confidence["care_episode"], AWAITING_FIRST_RESPONSE)
            unrelated = service.handle_asr_payload(
                "temi/temi-01/asr/final", make_asr(root, "evt_unrelated", "今天天氣如何")
            )
            self.assertEqual(unrelated["status"], "success")
            self.assertEqual(len(hermes.requests), 3)

    def test_timeout_progression_rechecks_with_hermes_then_sends_one_mock_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, hermes = self.make_service(root)
            service.handle_abnormal_payload("temi/temi-01/perception/abnormal", make_abnormal(root))
            episode = service.care_episode_store.get("evt_abnormal_care")
            self.assertIsNotNone(episode)
            service.process_abnormal_episode_timeouts(
                now_monotonic_ms=episode.first_response_deadline_monotonic_ms
            )
            after_follow_up = service.care_episode_store.get("evt_abnormal_care")
            self.assertEqual(after_follow_up.status, NO_RESPONSE)
            self.assertEqual(len(hermes.requests), 2)
            service.process_abnormal_episode_timeouts(
                now_monotonic_ms=after_follow_up.escalation_deadline_monotonic_ms
            )
            escalated = service.care_episode_store.get("evt_abnormal_care")
            self.assertEqual(escalated.status, ESCALATION_SENT)
            self.assertEqual(escalated.notification_stages["escalation"]["receipt"]["status"], "mock_delivered")
            self.assertEqual(len(mqtt.published), 3)

    def test_unknown_test_resident_is_rejected_before_notification_or_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, hermes = self.make_service(root)
            abnormal = make_abnormal(root)
            abnormal["event_type"] = "falls_down"
            abnormal["context"] = {
                "source": "formal_demo_injector",
                "test": True,
                "resident_id": "unapproved-test-resident",
                "request_id": "req-unknown",
                "run_id": "run-unknown",
                "scenario_id": "A10",
            }
            result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            self.assertEqual(result, {"status": "rejected", "reason": "unknown_test_resident"})
            self.assertEqual(mqtt.published, [])
            self.assertEqual(hermes.requests, [])

    def test_test_event_ingress_is_rejected_when_the_explicit_gate_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt, hermes = self.make_service(root)
            service.config = BridgeConfig(
                **{
                    **service.config.__dict__,
                    "demo_test_event_ingress_enabled": False,
                }
            )
            abnormal = make_abnormal(root)
            abnormal["event_type"] = "falls_down"
            abnormal["context"] = {
                "source": "formal_demo_injector",
                "test": True,
                "resident_id": "test-resident",
                "request_id": "req-disabled",
                "run_id": "run-disabled",
                "scenario_id": "A1",
            }
            result = service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            self.assertEqual(result, {"status": "rejected", "reason": "test_event_ingress_disabled"})
            self.assertEqual(mqtt.published, [])
            self.assertEqual(hermes.requests, [])

    def test_restart_preserves_initial_receipt_and_replays_no_notification_or_speak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_service, first_mqtt, first_hermes = self.make_service(root)
            abnormal = make_abnormal(root, "evt_restart")
            first_service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            self.assertEqual(len(first_mqtt.published), 1)
            self.assertEqual(len(first_hermes.requests), 1)

            restarted_service, restarted_mqtt, restarted_hermes = self.make_service(root)
            replay = restarted_service.handle_abnormal_payload("temi/temi-01/perception/abnormal", abnormal)
            self.assertEqual(replay["status"], "ignored")
            self.assertEqual(restarted_mqtt.published, [])
            self.assertEqual(restarted_hermes.requests, [])

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
            self.assertEqual(classify_care_episode_response("我頭很暈，需要幫忙", 0.9, 0.7), "needs_assistance")
            self.assertEqual(classify_care_episode_response("我沒事", 0.9, 0.7), "okay")


if __name__ == "__main__":
    unittest.main()
