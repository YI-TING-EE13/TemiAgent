#!/usr/bin/env python3
"""Deterministic HTTP resident used only by the newcomer software-only profile.

The process returns JSON action plans to the existing Bridge HTTP client.  It
does not connect to MQTT, publish commands, read canonical memory, or control
hardware; the Bridge remains responsible for parsing, validation, memory
actions, dispatch and its normal safe fallback behavior.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any


def _plan(event_id: str, robot_id: str, language: str, text: str, prompt: str) -> dict[str, Any]:
    """Return one bounded, schema-shaped test plan from a known acceptance input."""
    action: list[dict[str, Any]]
    intent = "general_support"
    level = "Normal"
    reason = "Deterministic newcomer acceptance response."
    if "source_type: perception.abnormal" in prompt:
        intent = "abnormal_care_first"
        level = "L2"
        reason = "A test abnormal observation requires a consent-first safety question."
        action = [{"action_id": "act_001", "type": "speak", "text": "我注意到你可能需要協助。你現在安全嗎？需要我通知家人或照護者嗎？", "language": language}]
    elif text == "__unsupported_action__":
        # Deliberate failure injection: the Bridge validator must reject this
        # before it reaches the Android test double.
        action = [{"action_id": "act_001", "type": "unknown_robot_action", "text": "must be rejected"}]
    elif "吃完早餐後的藥" in text:
        intent = "reminder_completion"
        action = [
            {"action_id": "act_001", "type": "mark_reminder_done", "reminder_id": "breakfast-medication"},
            {"action_id": "act_002", "type": "speak", "text": "已記錄早餐後的藥已完成。", "language": language},
        ]
    elif "不舒服" in text or "頭有點暈" in text:
        intent = "discomfort_support"
        level = "L2"
        reason = "The user describes discomfort; the test response supports without diagnosis."
        action = [{"action_id": "act_001", "type": "speak", "text": "聽起來你不太舒服。我會陪你一起確認狀況；如果症狀加重或你需要協助，請告訴我。", "language": language}]
    elif "通知家人" in text or text.strip() in {"要", "好的"}:
        intent = "caregiver_confirmation"
        action = [
            {"action_id": "act_001", "type": "notify_caregiver_mock", "target": "caregiver_demo_primary", "message": "Newcomer mock notification requested after explicit confirmation."},
            {"action_id": "act_002", "type": "speak", "text": "我會透過測試通知流程聯絡照護者，完成後再告訴你結果。", "language": language},
        ]
    elif "不用" in text or "沒事" in text:
        intent = "caregiver_declined"
        action = [{"action_id": "act_001", "type": "speak", "text": "好的，我不會通知他人。如果你改變主意，隨時告訴我。", "language": language}]
    elif "嗯" == text.strip() or "不確定" in text:
        intent = "caregiver_ambiguous"
        action = [{"action_id": "act_001", "type": "ask_clarification", "text": "我想確認：你希望我通知家人或照護者嗎？請回答要或不用。", "language": language}]
    else:
        action = [{"action_id": "act_001", "type": "speak", "text": "我聽到了。這是 software-only newcomer acceptance 的安全測試回應。", "language": language}]
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": robot_id,
        "confidence": 1.0,
        "cognitive_state": {"intent": intent, "home_esi_level": level, "risk_reason": reason, "next_step": action[0]["type"]},
        "reasoning_summary": "Deterministic test-double response; Bridge contracts remain authoritative.",
        "actions": action,
    }


def _handler(state_dir: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send({"status": "ok", "test_double": "resident", "media_tool_enabled": True, "media_fast_path_enabled": True, "media_tool_names": ["play_video", "pause_video", "resume_video", "stop_video"]})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/invoke":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request is not an object")
                event_id = payload["event_id"]
                robot_id = payload["robot_id"]
                language = payload.get("language") or "zh-TW"
                text = payload.get("asr_text") or ""
                prompt = payload.get("prompt") or ""
                if not all(isinstance(value, str) and value for value in (event_id, robot_id, language, prompt)):
                    raise ValueError("required request fields are invalid")
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send({"status": "error", "error": f"invalid test request: {exc}"}, status=HTTPStatus.BAD_REQUEST)
                return
            plan = _plan(event_id, robot_id, language, text, prompt)
            state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (state_dir / "requests.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"test_double": True, "event_id": event_id, "asr_text": text}, ensure_ascii=False) + "\n")
            self._send({"status": "ok", "latency_ms": 0, "raw_output": json.dumps(plan, ensure_ascii=False), "dispatch_metadata": {"test_double": "resident"}})

        def _send(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic newcomer resident test double.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), _handler(args.state_dir))
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
