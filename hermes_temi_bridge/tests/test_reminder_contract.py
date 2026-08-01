"""Focused reminder completion contract tests."""

import unittest

from hermes_temi_bridge.hermes_client import format_care_context_block
from hermes_temi_bridge.main import FALLBACKS, _action_validation_fallback_text, _reminder_without_active_match


class ReminderContractTests(unittest.TestCase):
    def test_care_context_prompt_requires_exact_id_and_unique_match(self) -> None:
        prompt = format_care_context_block(
            {
                "active_reminders": [
                    {"reminder_id": "breakfast-medication", "title": "早餐後用藥", "status": "active"}
                ]
            }
        )

        self.assertIn("exact non-empty reminder_id", prompt)
        self.assertIn("If exactly one active reminder clearly matches", prompt)
        self.assertIn("breakfast-medication", prompt)
        self.assertIn("more than one reminder could match", prompt)

    def test_missing_id_uses_resident_friendly_fallback_without_internal_code(self) -> None:
        text = _action_validation_fallback_text("missing_reminder_id")

        self.assertEqual(
            _action_validation_fallback_text("missing_event_type", care_context={"active_reminders": []}),
            FALLBACKS["missing_reminder_id"],
        )
        self.assertTrue(
            _reminder_without_active_match("我吃完藥了", {"active_reminders": [], "active_resident": {"resident_id": "father"}}, [{"type": "log_event"}])
        )
        self.assertFalse(
            _reminder_without_active_match("我吃完藥了", {"active_reminders": ["reminder-1"], "active_resident": {"resident_id": "father"}}, [{"type": "log_event"}])
        )
        self.assertEqual(text, FALLBACKS["missing_reminder_id"])
        self.assertNotIn("missing_reminder_id", text)
