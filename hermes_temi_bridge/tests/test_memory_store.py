import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.action_validator import validate_action_output
from hermes_temi_bridge.memory_store import EventContext, StructuredMemoryStore

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StructuredMemoryStoreTests(unittest.TestCase):
    def test_executes_reminder_and_log_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reminders.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "reminders": [
                            {
                                "reminder_id": "rem_morning_medication",
                                "status": "active",
                                "last_completed_at": None,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "daily_state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "active_reminders": ["rem_morning_medication"],
                        "recent_event_ids": [],
                        "demo_flags": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = validate_action_output(
                load_fixture("hermes_output_valid_memory_actions.json"),
                "evt_20260511_000001",
                "temi-01",
            )

            results = StructuredMemoryStore(root).execute(
                output,
                EventContext(
                    asr_text="我吃完藥了",
                    image_paths=["/TemiAgent/temi_shared/events/temi-01/evt/frame_t.jpg"],
                    conversation_id="conv_test",
                ),
            )

            self.assertEqual([result["type"] for result in results], ["mark_reminder_done", "log_event"])
            reminders = json.loads((root / "reminders.json").read_text(encoding="utf-8"))
            self.assertEqual(reminders["reminders"][0]["status"], "completed")
            daily = json.loads((root / "daily_state.json").read_text(encoding="utf-8"))
            self.assertNotIn("rem_morning_medication", daily["active_reminders"])
            event_lines = (root / "event_log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(event_lines), 1)
            event = json.loads(event_lines[0])
            self.assertEqual(event["risk"]["home_esi_level"], "L3")

    def test_notify_caregiver_mock_writes_abnormal_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = load_fixture("hermes_output_valid_speak.json")
            payload["cognitive_state"]["home_esi_level"] = "L1"
            payload["cognitive_state"]["risk_reason"] = "疑似跌倒且無回應。"
            payload["actions"] = [
                {"action_id": "act_001", "type": "notify_caregiver_mock", "message": "Demo mock notify"}
            ]
            output = validate_action_output(payload, "evt_20260511_000001", "temi-01")

            results = StructuredMemoryStore(root).execute(
                output,
                EventContext(asr_text="", image_paths=["/tmp/frame.jpg"]),
            )

            self.assertEqual(results[0]["type"], "notify_caregiver_mock")
            artifact = json.loads((root / "abnormal_events" / "evt_20260511_000001.json").read_text())
            self.assertEqual(artifact["notification"]["status"], "mock_sent")
            self.assertEqual(artifact["home_esi_level"], "L1")


if __name__ == "__main__":
    unittest.main()
