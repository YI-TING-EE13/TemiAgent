import unittest

from hermes_temi_bridge.mqtt_client import TemiMqttClient, _is_success_reason_code


class MqttRuntimeTests(unittest.TestCase):
    def test_paho_v1_numeric_success_code(self):
        self.assertTrue(_is_success_reason_code(0))

    def test_paho_v2_success_reason_code_text(self):
        self.assertTrue(_is_success_reason_code("Success"))

    def test_non_success_reason_code(self):
        self.assertFalse(_is_success_reason_code("Not authorized"))

    def test_on_connect_subscribes_abnormal_topic(self):
        class FakeClient:
            def __init__(self):
                self.subscriptions = []

            def subscribe(self, topic, qos=0):
                self.subscriptions.append((topic, qos))

        client = FakeClient()
        runtime = TemiMqttClient.__new__(TemiMqttClient)

        runtime._on_connect(client, None, None, "Success", None)

        self.assertIn(("temi/+/asr/final", 1), client.subscriptions)
        self.assertIn(("temi/+/perception/abnormal", 1), client.subscriptions)
        self.assertIn(("temi/+/cmd/result", 1), client.subscriptions)

    def test_on_message_dispatches_abnormal_payload(self):
        class Msg:
            topic = "temi/temi-01/perception/abnormal"
            payload = b'{"event_id":"evt_abnormal_001"}'

        runtime = TemiMqttClient.__new__(TemiMqttClient)
        runtime._asr_handler = None
        runtime._result_handler = None
        captured = []
        runtime._abnormal_handler = lambda topic, payload: captured.append((topic, payload))

        runtime._on_message(None, None, Msg())

        self.assertEqual(captured, [("temi/temi-01/perception/abnormal", {"event_id": "evt_abnormal_001"})])


if __name__ == "__main__":
    unittest.main()
