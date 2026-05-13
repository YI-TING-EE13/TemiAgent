import json
from pathlib import Path
import unittest

from hermes_temi_bridge.hermes_client import HermesOutputError, parse_hermes_output

FIXTURES = Path(__file__).parent / "fixtures"


class HermesOutputParsingTests(unittest.TestCase):
    def test_valid_json_should_parse(self):
        raw = (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")
        parsed = parse_hermes_output(raw)
        self.assertEqual(parsed["actions"][0]["type"], "speak")

    def test_markdown_wrapped_json_should_parse(self):
        raw = (FIXTURES / "hermes_output_markdown_wrapped.json").read_text(encoding="utf-8")
        parsed = parse_hermes_output(raw)
        self.assertEqual(parsed["event_id"], "evt_20260511_000001")

    def test_invalid_output_should_fail(self):
        with self.assertRaises(HermesOutputError):
            parse_hermes_output("Here is the result but no JSON")


if __name__ == "__main__":
    unittest.main()
