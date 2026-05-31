import json
from pathlib import Path
import unittest

from hermes_temi_bridge.action_validator import ActionValidationError, validate_action_output

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ActionValidationTests(unittest.TestCase):
    def validate(self, payload):
        return validate_action_output(payload, "evt_20260511_000001", "temi-01", max_actions=5)

    def test_valid_speak_action(self):
        output = self.validate(load_fixture("hermes_output_valid_speak.json"))
        self.assertEqual(output.actions[0]["type"], "speak")
        self.assertEqual(output.cognitive_state["home_esi_level"], "Normal")
        self.assertEqual(output.robot_actions[0]["type"], "speak")
        self.assertEqual(output.memory_actions, [])

    def test_valid_navigate_action(self):
        output = self.validate(load_fixture("hermes_output_valid_navigate.json"))
        self.assertEqual(output.actions[0]["target"], "meeting_room")

    def test_valid_memory_actions_are_separated_from_robot_actions(self):
        output = self.validate(load_fixture("hermes_output_valid_memory_actions.json"))
        self.assertEqual([action["type"] for action in output.robot_actions], ["speak"])
        self.assertEqual(
            [action["type"] for action in output.memory_actions],
            ["mark_reminder_done", "log_event"],
        )


    def test_memory_action_accepts_payload_parameters(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        payload["cognitive_state"] = {
            "intent": "report_discomfort",
            "home_esi_level": "L2",
            "risk_reason": "使用者表示身體不舒服，需要追問症狀。",
        }
        payload["actions"] = [
            {
                "action_id": "act_001",
                "type": "ask_clarification",
                "text": "您是哪裡不舒服？",
                "language": "zh-TW",
            },
            {
                "action_id": "act_002",
                "type": "log_event",
                "payload": {
                    "event_type": "health_discomfort",
                    "home_esi_level": "L2",
                    "description": "使用者主訴身體有一點不舒服",
                    "outcome": "已追問症狀",
                },
            },
        ]

        output = self.validate(payload)

        self.assertEqual(output.memory_actions[0]["event_type"], "health_discomfort")
        self.assertEqual(output.memory_actions[0]["outcome"], "已追問症狀")
        self.assertEqual(
            output.memory_actions[0]["details"]["description"],
            "使用者主訴身體有一點不舒服",
        )

    def test_missing_cognitive_state_is_rejected(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        del payload["cognitive_state"]
        with self.assertRaisesRegex(ActionValidationError, "missing_cognitive_state"):
            self.validate(payload)

    def test_invalid_home_esi_level_is_rejected(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        payload["cognitive_state"]["home_esi_level"] = "Critical"
        with self.assertRaisesRegex(ActionValidationError, "invalid_home_esi_level"):
            self.validate(payload)

    def test_invalid_action_type(self):
        with self.assertRaisesRegex(ActionValidationError, "invalid_action_type"):
            self.validate(load_fixture("hermes_output_invalid_action.json"))

    def test_navigate_target_not_in_whitelist(self):
        payload = load_fixture("hermes_output_valid_navigate.json")
        payload["actions"][0]["target"] = "server_room"
        with self.assertRaisesRegex(ActionValidationError, "navigation_target_not_allowed"):
            self.validate(payload)

    def test_turn_degrees_out_of_range(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        payload["actions"] = [
            {"action_id": "act_001", "type": "turn", "direction": "left", "degrees": 120}
        ]
        with self.assertRaisesRegex(ActionValidationError, "invalid_turn_degrees"):
            self.validate(payload)

    def test_too_many_actions(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        payload["actions"] = [
            {"action_id": f"act_{index}", "type": "noop", "reason": "No safe action is required."}
            for index in range(6)
        ]
        with self.assertRaisesRegex(ActionValidationError, "too_many_actions"):
            self.validate(payload)

    def test_missing_action_id(self):
        payload = load_fixture("hermes_output_valid_speak.json")
        del payload["actions"][0]["action_id"]
        with self.assertRaisesRegex(ActionValidationError, "missing_action_id"):
            self.validate(payload)


if __name__ == "__main__":
    unittest.main()
