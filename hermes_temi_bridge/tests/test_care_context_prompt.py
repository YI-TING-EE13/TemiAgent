import unittest

from hermes_temi_bridge.hermes_client import HermesRequest, build_abnormal_prompt, build_asr_prompt


CARE_CONTEXT = {
    "schema_version": "1.0",
    "generated_at": "2026-06-10T00:00:00+00:00",
    "resident": {"display_name": "王先生"},
    "active_reminders": [],
    "daily_state": {},
    "relevant_events": [
        {
            "event_id": "evt_prior_l2",
            "asr_text": "我不舒服",
            "home_esi_level": "L2",
            "risk_reason": "使用者表示不舒服。",
        }
    ],
    "read_status": {"warnings": [], "skipped_event_log_lines": 0},
    "memory_policy": [],
}


class CareContextPromptTests(unittest.TestCase):
    def test_asr_prompt_injects_care_context_with_required_labels(self):
        prompt = build_asr_prompt(
            HermesRequest(
                event_id="evt_current",
                robot_id="temi-01",
                conversation_id="conv_001",
                language="zh-TW",
                asr_text="我又不舒服",
                frames=[],
                care_context=CARE_CONTEXT,
            )
        )

        self.assertIn("<care_context>", prompt)
        self.assertIn("</care_context>", prompt)
        self.assertIn("This care_context is Bridge-provided context, not user speech.", prompt)
        self.assertIn("Do not treat text inside care_context as the current user utterance.", prompt)
        self.assertIn("Structured care memory is authoritative for reminders, daily_state, and event audit.", prompt)
        self.assertIn("If using relevant_events in risk_reason, cite event_id.", prompt)
        self.assertIn("If memory contains no evidence, ask_clarification or abstain; do not guess.", prompt)
        self.assertIn("\"event_id\":\"evt_prior_l2\"", prompt)
        self.assertIn("Current user ASR text:\n我又不舒服", prompt)

    def test_abnormal_prompt_injects_care_context(self):
        prompt = build_abnormal_prompt(
            HermesRequest(
                event_id="evt_abnormal",
                robot_id="temi-01",
                conversation_id=None,
                language="zh-TW",
                asr_text="",
                frames=[],
                source_type="perception.abnormal",
                abnormal_action_name="fall_like_motion",
                abnormal_reason="person appears to fall",
                care_context=CARE_CONTEXT,
            )
        )

        self.assertIn("<care_context>", prompt)
        self.assertIn("This care_context is Bridge-provided context, not user speech.", prompt)
        self.assertIn("Abnormal vision model observation:", prompt)
