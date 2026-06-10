import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.care_context_builder import CareContextBuilder


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def append_event(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def event(
    event_id,
    *,
    timestamp="2026-06-10T10:00:00+00:00",
    asr_text="",
    intent="normal_interaction",
    level="Normal",
    reason="No care risk.",
    outcome="recorded",
    actions=None,
):
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "source": "hermes_temi_bridge",
        "asr_text": asr_text,
        "perception": {"intent": intent, "visual_status": "not_available"},
        "risk": {"home_esi_level": level, "reason": reason},
        "actions_taken": actions or ["log_event"],
        "outcome": outcome,
    }


class CareContextBuilderTests(unittest.TestCase):
    def build(self, root: Path, **kwargs):
        builder = CareContextBuilder(root, **kwargs)
        return builder.build_for_event(
            event_id="evt_current",
            robot_id="temi-01",
            source="asr.final",
            asr_text="我有點不舒服",
            image_paths=["/tmp/frame.jpg"],
        )

    def test_handles_missing_memory_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = self.build(Path(tmp))

        self.assertEqual(context["resident"], {})
        self.assertEqual(context["active_reminders"], [])
        self.assertEqual(context["daily_state"], {})
        self.assertEqual(context["relevant_events"], [])
        self.assertGreaterEqual(len(context["read_status"]["warnings"]), 4)
        self.assertEqual(context["read_status"]["skipped_event_log_lines"], 0)

    def test_handles_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile.json").write_text("{not-json", encoding="utf-8")
            write_json(root / "reminders.json", {"schema_version": "1.0", "reminders": []})

            context = self.build(root)

        self.assertEqual(context["resident"], {})
        self.assertTrue(
            any("profile.json" in warning and "malformed_json" in warning for warning in context["read_status"]["warnings"])
        )

    def test_skips_malformed_jsonl_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "event_log.jsonl").write_text(
                "{bad-json\n"
                + json.dumps(
                    event(
                        "evt_valid",
                        asr_text="我昨天不舒服",
                        intent="report_discomfort",
                        level="L2",
                    ),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            context = self.build(root)

        self.assertEqual(context["read_status"]["skipped_event_log_lines"], 1)
        self.assertEqual([item["event_id"] for item in context["relevant_events"]], ["evt_valid"])

    def test_active_reminders_are_included_and_completed_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "reminders.json",
                {
                    "schema_version": "1.0",
                    "reminders": [
                        {
                            "reminder_id": "rem_morning_medication",
                            "type": "medication",
                            "title": "早餐後服藥",
                            "time": "08:30",
                            "status": "active",
                            "requires_confirmation": True,
                        },
                        {
                            "reminder_id": "rem_hydration",
                            "type": "hydration",
                            "title": "補充水分",
                            "status": "completed",
                        },
                    ],
                },
            )

            context = self.build(root)

        self.assertEqual([item["reminder_id"] for item in context["active_reminders"]], ["rem_morning_medication"])

    def test_recent_event_log_entries_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            for index in range(6):
                append_event(
                    log,
                    event(
                        f"evt_{index}",
                        timestamp=f"2026-06-10T10:0{index}:00+00:00",
                        asr_text=f"一般互動 {index}",
                    ),
                )

            context = self.build(root, max_events=3)

        self.assertEqual([item["event_id"] for item in context["relevant_events"]], ["evt_5", "evt_4", "evt_3"])

    def test_l1_l2_events_rank_above_normal_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            append_event(log, event("evt_l2", timestamp="2026-06-10T08:00:00+00:00", asr_text="我不舒服", level="L2"))
            append_event(log, event("evt_normal", timestamp="2026-06-10T11:00:00+00:00", asr_text="今天天氣很好", level="Normal"))
            append_event(log, event("evt_l1", timestamp="2026-06-10T07:00:00+00:00", asr_text="救命我跌倒了", level="L1"))

            context = self.build(root, max_events=2)

        event_ids = [item["event_id"] for item in context["relevant_events"]]
        self.assertIn("evt_l1", event_ids)
        self.assertIn("evt_l2", event_ids)
        self.assertNotIn("evt_normal", event_ids)

    def test_keyword_matching_includes_prior_discomfort_and_medication_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            append_event(log, event("evt_old_discomfort", timestamp="2026-06-01T08:00:00+00:00", asr_text="我頭暈不舒服", level="L2"))
            append_event(log, event("evt_old_medication", timestamp="2026-06-01T09:00:00+00:00", asr_text="我吃藥了", level="L3", actions=["mark_reminder_done", "log_event"]))
            append_event(log, event("evt_unrelated", timestamp="2026-06-10T11:00:00+00:00", asr_text="看電視", level="Normal"))

            builder = CareContextBuilder(root, max_events=5)
            context = builder.build_for_event(
                event_id="evt_current",
                robot_id="temi-01",
                source="asr.final",
                asr_text="我又不舒服，剛剛吃藥了",
                image_paths=[],
            )

        event_ids = {item["event_id"] for item in context["relevant_events"]}
        self.assertIn("evt_old_discomfort", event_ids)
        self.assertIn("evt_old_medication", event_ids)

    def test_care_context_is_bounded_by_max_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            for index in range(20):
                append_event(
                    log,
                    event(
                        f"evt_long_{index}",
                        timestamp=f"2026-06-10T10:{index:02d}:00+00:00",
                        asr_text="不舒服" * 200,
                        level="L2",
                        reason="需要追問症狀" * 200,
                        outcome="waiting_for_user_response" * 50,
                    ),
                )

            context = self.build(root, max_events=20, max_chars=1200)

        serialized = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        self.assertLessEqual(len(serialized), 1200)

    def test_abnormal_events_do_not_break_event_log_retrieval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_event(
                root / "event_log.jsonl",
                event(
                    "evt_prior_l2",
                    timestamp="2026-06-10T08:00:00+00:00",
                    asr_text="我現在有點不舒服",
                    intent="report_discomfort",
                    level="L2",
                    reason="使用者表示不舒服，需要追問症狀。",
                ),
            )
            write_json(
                root / "abnormal_events" / "evt_abnormal_unknown.json",
                {
                    "schema_version": "1.0",
                    "event_id": "evt_abnormal_unknown",
                    "timestamp": "2026-06-10T09:00:00+00:00",
                    "home_esi_level": "L1",
                    "risk_reason": "疑似跌倒，但 resolved 欄位缺失。",
                    "evidence": {"image_paths": ["/tmp/frame.jpg"]},
                },
            )

            context = self.build(root, max_events=5)

        self.assertFalse(
            any("unexpected_read_error" in warning for warning in context["read_status"]["warnings"])
        )
        event_ids = [item["event_id"] for item in context["relevant_events"]]
        self.assertIn("evt_prior_l2", event_ids)
        self.assertNotIn("evt_abnormal_unknown", event_ids)

    def test_abnormal_event_unknown_status_is_not_treated_as_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "abnormal_events" / "evt_abnormal_unknown_status.json",
                {
                    "schema_version": "1.0",
                    "event_id": "evt_abnormal_unknown_status",
                    "timestamp": "2026-06-10T09:00:00+00:00",
                    "status": "unknown",
                    "home_esi_level": "L1",
                    "risk_reason": "狀態未知。",
                },
            )

            context = self.build(root, max_events=5)

        self.assertFalse(
            any("unexpected_read_error" in warning for warning in context["read_status"]["warnings"])
        )
        self.assertEqual(context["relevant_events"], [])


    def test_repeated_discomfort_not_buried_by_l1_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            append_event(
                log,
                event(
                    "evt_prior_discomfort_l2",
                    timestamp="2026-06-01T08:00:00+00:00",
                    asr_text="我現在有點不舒服",
                    intent="report_discomfort",
                    level="L2",
                    reason="使用者表示不舒服，需要追問症狀。",
                ),
            )
            for index in range(7):
                append_event(
                    log,
                    event(
                        f"evt_fall_l1_{index}",
                        timestamp=f"2026-06-10T10:{index:02d}:00+00:00",
                        asr_text="跌倒在地上",
                        intent="fall_detection",
                        level="L1",
                        reason="偵測到跌倒，屬於高風險。",
                    ),
                )

            context = self.build(root, max_events=5)

        by_id = {item["event_id"]: item for item in context["relevant_events"]}
        self.assertIn("evt_prior_discomfort_l2", by_id)
        self.assertTrue(
            {
                "current_intent:health_discomfort",
                "keyword:health_discomfort",
            }
            & set(by_id["evt_prior_discomfort_l2"]["match_reasons"])
        )

    def test_high_risk_context_is_preserved_with_discomfort_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            append_event(log, event("evt_prior_discomfort_l2", timestamp="2026-06-01T08:00:00+00:00", asr_text="我不舒服", level="L2"))
            for index in range(4):
                append_event(log, event(f"evt_fall_l1_{index}", timestamp=f"2026-06-10T10:{index:02d}:00+00:00", asr_text="跌倒", intent="fall_detection", level="L1"))

            context = self.build(root, max_events=5)

        levels = {item["home_esi_level"] for item in context["relevant_events"]}
        event_ids = {item["event_id"] for item in context["relevant_events"]}
        self.assertIn("evt_prior_discomfort_l2", event_ids)
        self.assertIn("L1", levels)

    def test_no_matching_discomfort_does_not_invent_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "event_log.jsonl"
            for index in range(3):
                append_event(log, event(f"evt_fall_l1_{index}", timestamp=f"2026-06-10T10:{index:02d}:00+00:00", asr_text="跌倒", intent="fall_detection", level="L1"))

            context = self.build(root, max_events=5)

        self.assertFalse(
            any("unexpected_read_error" in warning for warning in context["read_status"]["warnings"])
        )
        self.assertTrue(context["relevant_events"])
        self.assertTrue(all(item["event_id"].startswith("evt_fall_l1_") for item in context["relevant_events"]))


if __name__ == "__main__":
    unittest.main()
