import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "dispatch_hermes_action_output.py"
SPEC = importlib.util.spec_from_file_location("dispatch_hermes_action_output", SCRIPT)
dispatcher = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(dispatcher)


class ManualActionDispatcherTests(unittest.TestCase):
    def test_extracts_json_before_chat_separator(self):
        payload = dispatcher._extract_first_json_object('{"a": 1}\n---\nnotes')
        self.assertEqual(payload, {"a": 1})

    def test_fills_cognitive_state_for_manual_tts(self):
        payload = {
            "schema_version": "1.0",
            "event_id": "manual_greet_20260601",
            "robot_id": "temi-01",
            "confidence": 1.0,
            "reasoning_summary": "Manual TTS greeting.",
            "actions": [
                {
                    "action_id": "act_001",
                    "type": "speak",
                    "text": "嗨 King！",
                    "language": "zh-TW",
                }
            ],
        }
        args = dispatcher.build_parser().parse_args(["--json", json.dumps(payload, ensure_ascii=False)])
        result = dispatcher.dispatch_action(args)
        self.assertEqual(result["status"], "validated")
        self.assertTrue(result["filled_cognitive_state"])
        self.assertEqual(result["topic"], "temi/temi-01/cmd/request")
        self.assertEqual(result["command"]["event_id"], "manual_greet_20260601")
        self.assertEqual(result["command"]["actions"][0]["type"], "speak")

    def test_strict_mode_rejects_missing_cognitive_state(self):
        payload = {
            "schema_version": "1.0",
            "event_id": "manual_greet_20260601",
            "robot_id": "temi-01",
            "confidence": 1.0,
            "reasoning_summary": "Manual TTS greeting.",
            "actions": [{"action_id": "act_001", "type": "speak", "text": "嗨"}],
        }
        args = dispatcher.build_parser().parse_args([
            "--json",
            json.dumps(payload, ensure_ascii=False),
            "--strict-cognitive-state",
        ])
        with self.assertRaisesRegex(Exception, "missing_cognitive_state"):
            dispatcher.dispatch_action(args)


if __name__ == "__main__":
    unittest.main()
