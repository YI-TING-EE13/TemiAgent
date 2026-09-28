"""Hardware-free tests for response/action consistency evaluation."""

from __future__ import annotations

import unittest

from tools.test_action_selection_cases import (
    CASES,
    evaluate_response_action_consistency,
    offline_summary,
    response_requires_reply,
)


class ResponseActionConsistencyTests(unittest.TestCase):
    def test_catalogue_does_not_declare_unenforced_expected_actions(self) -> None:
        self.assertEqual(len(CASES), 23)
        self.assertTrue(all(not hasattr(case, "expected_action") for case in CASES))

        summary = offline_summary(CASES)

        self.assertEqual(summary["catalogue_status"], "READY")
        self.assertTrue(
            any("does not assert scenario-level correctness" in item for item in summary["limitations"])
        )

    def test_response_requires_reply_recognizes_questions(self) -> None:
        for text in (
            "請問您現在感覺如何？",
            "有沒有頭暈或胸悶",
            "您的收縮壓是多少",
        ):
            with self.subTest(text=text):
                self.assertTrue(response_requires_reply(text))

    def test_response_requires_reply_rejects_complete_statements(self) -> None:
        for text in (
            "好的，我已經幫您記錄完成。",
            "請先坐下休息。",
        ):
            with self.subTest(text=text):
                self.assertFalse(response_requires_reply(text))

    def test_question_requires_ask_clarification(self) -> None:
        consistent, expected = evaluate_response_action_consistency(
            {"actions": [{"type": "ask_clarification", "text": "請問您現在感覺如何？"}]}
        )

        self.assertTrue(consistent)
        self.assertEqual(expected, ["ask_clarification"])

    def test_question_rejects_speak(self) -> None:
        consistent, expected = evaluate_response_action_consistency(
            {"actions": [{"type": "speak", "text": "請問您現在感覺如何？"}]}
        )

        self.assertFalse(consistent)
        self.assertEqual(expected, ["ask_clarification"])

    def test_complete_statement_requires_speak(self) -> None:
        consistent, expected = evaluate_response_action_consistency(
            {"actions": [{"type": "speak", "text": "好的，我已經幫您記錄完成。"}]}
        )

        self.assertTrue(consistent)
        self.assertEqual(expected, ["speak"])

    def test_complete_statement_rejects_ask_clarification(self) -> None:
        consistent, expected = evaluate_response_action_consistency(
            {"actions": [{"type": "ask_clarification", "text": "好的，我已經幫您記錄完成。"}]}
        )

        self.assertFalse(consistent)
        self.assertEqual(expected, ["speak"])


if __name__ == "__main__":
    unittest.main()
