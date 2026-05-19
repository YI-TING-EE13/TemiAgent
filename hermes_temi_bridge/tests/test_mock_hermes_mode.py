import unittest

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.hermes_client import (
    HermesRequest,
    HttpHermesClient,
    MockHermesClient,
    parse_hermes_output,
)
from hermes_temi_bridge.main import create_hermes_client


class MockHermesModeTests(unittest.TestCase):
    def test_create_mock_client_from_config(self):
        client = create_hermes_client(
            BridgeConfig(hermes_invoke_mode="mock", hermes_mock_response_text="mock ok")
        )
        self.assertIsInstance(client, MockHermesClient)

    def test_create_http_client_from_config(self):
        client = create_hermes_client(
            BridgeConfig(hermes_invoke_mode="http", hermes_http_url="http://127.0.0.1:8765/invoke")
        )
        self.assertIsInstance(client, HttpHermesClient)

    def test_mock_response_matches_event_and_robot(self):
        client = MockHermesClient("mock ok")
        response = client.invoke(
            HermesRequest(
                event_id="evt_mock",
                robot_id="temi-01",
                conversation_id="conv_mock",
                language="zh-TW",
                asr_text="測試",
                frames=[],
            )
        )
        parsed = parse_hermes_output(response.raw_output)
        self.assertEqual(parsed["event_id"], "evt_mock")
        self.assertEqual(parsed["robot_id"], "temi-01")
        self.assertEqual(parsed["actions"][0]["text"], "mock ok")

    def test_unknown_invoke_mode_fails_fast(self):
        with self.assertRaisesRegex(ValueError, "unsupported HERMES_INVOKE_MODE"):
            create_hermes_client(BridgeConfig(hermes_invoke_mode="api"))


if __name__ == "__main__":
    unittest.main()
