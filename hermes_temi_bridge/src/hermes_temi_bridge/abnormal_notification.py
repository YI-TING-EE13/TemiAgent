"""Bridge-owned notification adapter for abnormal-care episodes.

The adapter never exposes a webhook URL in a receipt or trace.  Demo mock
delivery is an explicit non-network route; real Discord delivery is accepted
only after Discord returns HTTP 204.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import time
from typing import Callable
from urllib import error, request
import uuid

from .config import BridgeConfig


PostJson = Callable[[str, dict[str, str], int], tuple[int, dict[str, str]]]


class AbnormalNotificationDispatcher:
    """Deliver a privacy-bounded abnormal-alert stage through one configured route."""

    def __init__(self, config: BridgeConfig, post_json: PostJson | None = None) -> None:
        self.config = config
        self.post_json = post_json or _post_json

    def dispatch(
        self,
        *,
        stage: str,
        event_id: str,
        event_type: str,
        robot_id: str,
        resident_id: str | None,
        detected_timestamp_ms: int | None,
        run_id: str | None,
        scenario_id: str | None,
        is_test: bool,
        resident_status: str | None = None,
    ) -> dict[str, str | int | None]:
        """Return a redacted receipt without retrying an externally visible alert."""
        notification_id = f"notification-{uuid.uuid4().hex}"
        base: dict[str, str | int | None] = {
            "receipt_id": notification_id,
            "notification_id": notification_id,
            "stage": stage,
            "deduplication_key": f"abnormal-care:{event_id}:{stage}",
            "event_id": event_id,
            "event_type": event_type,
            "robot_id": robot_id,
            "resident_id": resident_id or "unknown",
            "detected_timestamp_ms": detected_timestamp_ms,
            "run_id": run_id,
            "scenario_id": scenario_id,
        }
        if self.config.abnormal_notification_mode == "disabled":
            return {**base, "status": "disabled", "failure_code": "ABNORMAL_NOTIFICATION_DISABLED"}
        if self.config.abnormal_notification_mode == "demo_mock":
            if not (self.config.demo_notification_mock_enabled and self.config.demo_notification_receipt_enabled):
                return {**base, "status": "failed", "failure_code": "DEMO_NOTIFICATION_MOCK_DISABLED"}
            return {
                **base,
                "status": "mock_delivered",
                "failure_code": "DEMO_MOCK_DELIVERED",
                "delivered_at_ms": int(time.time() * 1000),
            }
        if is_test and not self.config.abnormal_notification_test_recipient_authorized:
            return {**base, "status": "failed", "failure_code": "DISCORD_TEST_RECIPIENT_NOT_AUTHORIZED"}
        try:
            webhook = _read_owner_only_webhook(self.config.abnormal_notification_discord_env_path)
        except ValueError as exc:
            return {**base, "status": "failed", "failure_code": str(exc)}
        message = _message(
            stage=stage,
            event_id=event_id,
            event_type=event_type,
            robot_id=robot_id,
            resident_id=resident_id,
            detected_timestamp_ms=detected_timestamp_ms,
            run_id=run_id,
            scenario_id=scenario_id,
            is_test=is_test,
            resident_status=resident_status,
        )
        try:
            status_code, headers = self.post_json(webhook, {"content": message}, self.config.abnormal_notification_timeout_seconds)
        except TimeoutError:
            return {**base, "status": "failed", "failure_code": "DISCORD_TIMEOUT"}
        except OSError:
            return {**base, "status": "failed", "failure_code": "DISCORD_CONNECTION_FAILED"}
        if status_code == 204:
            return {
                **base,
                "status": "delivered",
                "failure_code": "DISCORD_DELIVERED",
                "status_code": status_code,
                "delivered_at_ms": int(time.time() * 1000),
            }
        failure = {401: "DISCORD_UNAUTHORIZED", 403: "DISCORD_FORBIDDEN", 404: "DISCORD_WEBHOOK_NOT_FOUND", 429: "DISCORD_RATE_LIMITED"}.get(status_code, "DISCORD_BAD_RESPONSE")
        receipt = {**base, "status": "failed", "failure_code": failure, "status_code": status_code}
        retry_after = headers.get("Retry-After") if isinstance(headers, dict) else None
        if retry_after:
            receipt["retry_after_seconds"] = retry_after
        return receipt


def _message(
    *,
    stage: str,
    event_id: str,
    event_type: str,
    robot_id: str,
    resident_id: str | None,
    detected_timestamp_ms: int | None,
    run_id: str | None,
    scenario_id: str | None,
    is_test: bool,
    resident_status: str | None,
) -> str:
    prefix = "[TEST] " if is_test else ""
    stage_status = {
        "initial_alert": "event detected; Temi is checking the resident",
        "status_update": f"resident response: {resident_status or 'unknown'}",
        "escalation": "no response after care follow-up; human review needed",
    }.get(stage, resident_status or "event status updated")
    lines = [
        f"{prefix}[異常事件通知] TemiAgent abnormal-care alert",
        f"stage: {stage}",
        f"robot_id: {robot_id}",
        f"resident_id: {resident_id or 'unknown'}",
        f"event_id: {event_id}",
        f"event_type: {event_type}",
        f"detected_at_ms: {detected_timestamp_ms if detected_timestamp_ms is not None else 'unknown'}",
        f"status: {stage_status}",
    ]
    if is_test:
        lines.extend([f"run_id: {run_id}", f"scenario_id: {scenario_id}", "No real care incident occurred."])
    return "\n".join(lines)


def _read_owner_only_webhook(raw_path: str) -> str:
    if not raw_path:
        raise ValueError("DISCORD_WEBHOOK_UNSET")
    path = Path(raw_path)
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ValueError("DISCORD_WEBHOOK_UNSET") from exc
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ValueError("DISCORD_CREDENTIAL_FILE_UNSAFE")
    if metadata.st_uid != os.geteuid():
        raise ValueError("DISCORD_CREDENTIAL_FILE_UNSAFE")
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("DISCORD_WEBHOOK_URL="):
            value = raw.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    raise ValueError("DISCORD_WEBHOOK_UNSET")


def _post_json(webhook: str, payload: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_data = request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(request_data, timeout=timeout_seconds) as response:
            return int(response.status), dict(response.headers.items())
    except error.HTTPError as exc:
        return int(exc.code), dict(exc.headers.items()) if exc.headers else {}
