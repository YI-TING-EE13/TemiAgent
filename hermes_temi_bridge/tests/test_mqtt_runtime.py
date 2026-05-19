import unittest

from hermes_temi_bridge.mqtt_client import _is_success_reason_code


class MqttRuntimeTests(unittest.TestCase):
    def test_paho_v1_numeric_success_code(self):
        self.assertTrue(_is_success_reason_code(0))

    def test_paho_v2_success_reason_code_text(self):
        self.assertTrue(_is_success_reason_code("Success"))

    def test_non_success_reason_code(self):
        self.assertFalse(_is_success_reason_code("Not authorized"))


if __name__ == "__main__":
    unittest.main()
