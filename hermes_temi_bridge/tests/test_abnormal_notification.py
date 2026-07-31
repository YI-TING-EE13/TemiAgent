from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from hermes_temi_bridge.abnormal_notification import AbnormalNotificationDispatcher
from hermes_temi_bridge.config import BridgeConfig


class AbnormalNotificationTests(unittest.TestCase):
    def test_legacy_discord_keys_select_the_owner_only_bridge_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "bridge.env"
            credential = Path(temporary) / "discord.env"
            config_path.write_text(
                "ABNORMAL_EVENT_PUBLISH_ENABLED=true\n"
                "DISCORD_NOTIFY_ENABLED=true\n"
                f"DISCORD_ENV_FILE={credential}\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                config = BridgeConfig.from_env(config_path)
            self.assertEqual(config.abnormal_notification_mode, "discord_webhook")
            self.assertEqual(config.abnormal_notification_discord_env_path, str(credential))

    def test_demo_mock_receipt_is_traceable_and_never_requires_a_webhook(self) -> None:
        dispatcher = AbnormalNotificationDispatcher(
            BridgeConfig(
                abnormal_notification_mode="demo_mock",
                demo_notification_mock_enabled=True,
                demo_notification_receipt_enabled=True,
            )
        )
        receipt = dispatcher.dispatch(
            stage="initial_alert",
            event_id="evt-1",
            event_type="falls_down",
            robot_id="temi-01",
            resident_id="test-resident",
            detected_timestamp_ms=1_700_000_000_000,
            run_id="run-1",
            scenario_id="A1",
            is_test=True,
        )
        self.assertEqual(receipt["status"], "mock_delivered")
        self.assertEqual(receipt["stage"], "initial_alert")
        self.assertEqual(receipt["run_id"], "run-1")
        self.assertEqual(receipt["deduplication_key"], "abnormal-care:evt-1:initial_alert")
        self.assertIn("delivered_at_ms", receipt)
        self.assertNotIn("webhook", receipt)

    def test_real_notification_requires_204_and_owner_only_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credential = Path(temporary) / "discord.env"
            credential.write_text("DISCORD_WEBHOOK_URL=http://127.0.0.1:9/webhook\n", encoding="utf-8")
            credential.chmod(0o600)
            calls: list[dict[str, object]] = []

            def post_json(url: str, payload: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, str]]:
                calls.append({"url": url, "payload": payload, "timeout_seconds": timeout_seconds})
                return 200, {}

            dispatcher = AbnormalNotificationDispatcher(
                BridgeConfig(
                    abnormal_notification_mode="discord_webhook",
                    abnormal_notification_discord_env_path=str(credential),
                ),
                post_json=post_json,
            )
            receipt = dispatcher.dispatch(
                stage="initial_alert",
                event_id="evt-2",
                event_type="fight",
                robot_id="temi-01",
                resident_id=None,
                detected_timestamp_ms=1_700_000_000_000,
                run_id=None,
                scenario_id=None,
                is_test=False,
            )
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["failure_code"], "DISCORD_BAD_RESPONSE")
            self.assertEqual(len(calls), 1)
            self.assertNotIn("test-resident", str(calls[0]["payload"]))

    def test_test_event_requires_explicit_authorized_real_recipient_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credential = Path(temporary) / "discord.env"
            credential.write_text("DISCORD_WEBHOOK_URL=http://127.0.0.1:9/webhook\n", encoding="utf-8")
            credential.chmod(0o600)
            dispatcher = AbnormalNotificationDispatcher(
                BridgeConfig(
                    abnormal_notification_mode="discord_webhook",
                    abnormal_notification_discord_env_path=str(credential),
                )
            )
            receipt = dispatcher.dispatch(
                stage="initial_alert",
                event_id="evt-3",
                event_type="falls_down",
                robot_id="temi-01",
                resident_id="test-resident",
                detected_timestamp_ms=1_700_000_000_000,
                run_id="run-3",
                scenario_id="A1",
                is_test=True,
            )
            self.assertEqual(receipt["failure_code"], "DISCORD_TEST_RECIPIENT_NOT_AUTHORIZED")

    def test_real_discord_receipt_matrix_accepts_only_204_and_redacts_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credential = Path(temporary) / "discord.env"
            webhook = "http://127.0.0.1:9/private-webhook"
            credential.write_text(f"DISCORD_WEBHOOK_URL={webhook}\n", encoding="utf-8")
            credential.chmod(0o600)
            cases: tuple[tuple[object, str], ...] = (
                (204, "DISCORD_DELIVERED"),
                (401, "DISCORD_UNAUTHORIZED"),
                (403, "DISCORD_FORBIDDEN"),
                (404, "DISCORD_WEBHOOK_NOT_FOUND"),
                (429, "DISCORD_RATE_LIMITED"),
                (TimeoutError(), "DISCORD_TIMEOUT"),
                (OSError("offline"), "DISCORD_CONNECTION_FAILED"),
            )
            for outcome, expected_code in cases:
                captured_payloads: list[dict[str, str]] = []

                def post_json(url: str, payload: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, str]]:
                    self.assertEqual(url, webhook)
                    self.assertEqual(timeout_seconds, 15)
                    captured_payloads.append(payload)
                    if isinstance(outcome, Exception):
                        raise outcome
                    return int(outcome), {"Retry-After": "3"} if outcome == 429 else {}

                with self.subTest(outcome=outcome):
                    receipt = AbnormalNotificationDispatcher(
                        BridgeConfig(
                            abnormal_notification_mode="discord_webhook",
                            abnormal_notification_discord_env_path=str(credential),
                        ),
                        post_json=post_json,
                    ).dispatch(
                        stage="initial_alert",
                        event_id="evt-matrix",
                        event_type="falls_down",
                        robot_id="temi-01",
                        resident_id="unknown",
                        detected_timestamp_ms=1_700_000_000_000,
                        run_id=None,
                        scenario_id=None,
                        is_test=False,
                    )
                self.assertEqual(receipt["failure_code"], expected_code)
                self.assertNotIn(webhook, repr(receipt))
                self.assertEqual(len(captured_payloads), 1)
                message = captured_payloads[0]["content"]
                self.assertIn("[異常事件通知]", message)
                self.assertIn("robot_id: temi-01", message)
                self.assertIn("resident_id: unknown", message)
                self.assertIn("detected_at_ms: 1700000000000", message)
                if outcome == 204:
                    self.assertEqual(receipt["status"], "delivered")
                    self.assertIn("delivered_at_ms", receipt)
                else:
                    self.assertEqual(receipt["status"], "failed")


if __name__ == "__main__":
    unittest.main()
