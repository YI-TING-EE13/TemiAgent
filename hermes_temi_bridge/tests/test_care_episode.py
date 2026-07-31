from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.care_episode import (
    AWAITING_FIRST_RESPONSE,
    ESCALATION_SENT,
    FOLLOW_UP_REQUIRED,
    INITIAL_ALERT_SENT,
    NO_RESPONSE,
    CareEpisodeStore,
)


class CareEpisodeStoreTests(unittest.TestCase):
    def test_persisted_event_and_stage_dedup_survive_a_new_store_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = CareEpisodeStore(root, first_response_timeout_seconds=10, second_response_timeout_seconds=20)
            episode, created = store.create(
                event_id="evt-fall-1",
                robot_id="temi-01",
                event_type="falls_down",
                resident_id="test-resident",
                detected_timestamp_ms=1_700_000_000_000,
                request_id="req-fall-1",
                run_id="run-1",
                scenario_id="A1",
                is_test=True,
                now_monotonic_ms=1_000,
            )
            self.assertTrue(created)
            self.assertEqual(episode.status, "DETECTED")
            self.assertTrue(store.reserve_notification_stage("evt-fall-1", "initial_alert", now_monotonic_ms=1_001))
            store.complete_notification_stage(
                "evt-fall-1",
                "initial_alert",
                {"status": "mock_delivered", "receipt_id": "mock-1"},
                now_monotonic_ms=1_002,
            )
            store.transition("evt-fall-1", INITIAL_ALERT_SENT, now_monotonic_ms=1_003)
            store.transition("evt-fall-1", AWAITING_FIRST_RESPONSE, now_monotonic_ms=1_004)

            restarted = CareEpisodeStore(root, first_response_timeout_seconds=10, second_response_timeout_seconds=20)
            duplicate, duplicate_created = restarted.create(
                event_id="evt-fall-1",
                robot_id="temi-01",
                event_type="falls_down",
                resident_id="test-resident",
                detected_timestamp_ms=1_700_000_000_000,
                request_id="req-fall-1",
                run_id="run-1",
                scenario_id="A1",
                is_test=True,
                now_monotonic_ms=1_005,
            )
            self.assertFalse(duplicate_created)
            self.assertEqual(duplicate.status, AWAITING_FIRST_RESPONSE)
            self.assertFalse(restarted.reserve_notification_stage("evt-fall-1", "initial_alert", now_monotonic_ms=1_006))

    def test_timeout_progression_and_escalation_stage_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CareEpisodeStore(Path(temporary), first_response_timeout_seconds=10, second_response_timeout_seconds=20)
            store.create(
                event_id="evt-timeout-1",
                robot_id="temi-01",
                event_type="lies_on_floor",
                resident_id="test-resident",
                detected_timestamp_ms=1_700_000_000_000,
                request_id="req-timeout-1",
                run_id="run-1",
                scenario_id="A8",
                is_test=True,
                now_monotonic_ms=0,
            )
            store.transition("evt-timeout-1", INITIAL_ALERT_SENT, now_monotonic_ms=1)
            store.transition("evt-timeout-1", AWAITING_FIRST_RESPONSE, now_monotonic_ms=2)
            self.assertEqual([episode.event_id for episode in store.due_first_response(10_001)], ["evt-timeout-1"])
            store.transition("evt-timeout-1", FOLLOW_UP_REQUIRED, now_monotonic_ms=10_001)
            store.transition("evt-timeout-1", NO_RESPONSE, now_monotonic_ms=10_002)
            self.assertEqual([episode.event_id for episode in store.due_escalation(30_003)], ["evt-timeout-1"])
            self.assertTrue(store.reserve_notification_stage("evt-timeout-1", "escalation", now_monotonic_ms=30_003))
            store.complete_notification_stage(
                "evt-timeout-1",
                "escalation",
                {"status": "mock_delivered", "receipt_id": "mock-2"},
                now_monotonic_ms=30_004,
            )
            final = store.transition("evt-timeout-1", ESCALATION_SENT, now_monotonic_ms=30_004)
            self.assertEqual(final.status, ESCALATION_SENT)


if __name__ == "__main__":
    unittest.main()
