"""Deterministic pending-confirmation state for abnormal care events.

The Bridge owns this small, structured state so an abnormal perception event
can receive one explicit user answer without asking a reasoning model to
invent a robot or notification action. It deliberately contains no raw ASR
text or model chain-of-thought.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import time
from typing import Any


CARE_QUESTION = "我注意到你可能需要協助。你還好嗎？需要我幫忙通知家人或照護者嗎？"
CARE_REASK = "我想再確認一次：你需要我幫忙通知家人或照護者嗎？"
CARE_DECLINED = "好的。如果你之後感到不舒服，再告訴我，我會繼續留意。"
CARE_UNRESOLVED = "我還無法確認你的意思。如果需要協助，請直接告訴我。"
CARE_EXISTING_ALERT_DELIVERED = "我已確認既有通知管道已送出提醒，請先不要勉強移動。"
CARE_NOTIFICATION_UNAVAILABLE = "我目前無法確認通知是否送出。請附近的人協助，或再告訴我一次。"

AFFIRMATIVE_TERMS = ("幫我通知", "請通知", "通知家人", "通知照護者", "需要", "可以", "要", "好")
NEGATIVE_TERMS = ("不要通知", "不用了", "不需要", "不用", "我沒事", "沒事", "不要")
AMBIGUOUS_TERMS = ("不知道", "不確定", "等一下", "可能", "嗯")
MAX_RECORDS = 100


def now_ms() -> int:
    """Return the current Unix time in milliseconds."""
    return int(time.time() * 1000)


def classify_care_confirmation_response(
    text: str,
    confidence: float | None,
    minimum_confidence: float,
) -> str:
    """Classify a short answer without treating low-confidence speech as consent."""
    if confidence is None or confidence < minimum_confidence:
        return "ambiguous"
    normalized = re.sub(r"[\s，。！？、,.!?]", "", text).lower()
    if any(term in normalized for term in NEGATIVE_TERMS):
        return "declined"
    if any(term in normalized for term in AFFIRMATIVE_TERMS):
        return "accepted"
    if any(term in normalized for term in AMBIGUOUS_TERMS):
        return "ambiguous"
    return "unrelated"


@dataclass(frozen=True)
class PendingCareConfirmation:
    """A privacy-bounded, auditable abnormal-care confirmation record."""

    event_id: str
    robot_id: str
    conversation_id: str
    abnormal_category: str
    event_timestamp_ms: int
    prompt_timestamp_ms: int
    pending_question_type: str
    notification_target_class: str
    status: str
    expires_at_ms: int
    dedup_key: str
    clarification_count: int = 0
    prompt_command_id: str | None = None
    immediate_alert: dict[str, Any] | None = None
    failure_code: str | None = None
    updated_at_ms: int | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PendingCareConfirmation":
        """Read one persisted record while rejecting incomplete state."""
        required = (
            "event_id", "robot_id", "conversation_id", "abnormal_category",
            "event_timestamp_ms", "prompt_timestamp_ms", "pending_question_type",
            "notification_target_class", "status", "expires_at_ms", "dedup_key",
        )
        if any(key not in value for key in required):
            raise ValueError("invalid_care_confirmation_record")
        return cls(
            event_id=str(value["event_id"]), robot_id=str(value["robot_id"]),
            conversation_id=str(value["conversation_id"]),
            abnormal_category=str(value["abnormal_category"]),
            event_timestamp_ms=int(value["event_timestamp_ms"]),
            prompt_timestamp_ms=int(value["prompt_timestamp_ms"]),
            pending_question_type=str(value["pending_question_type"]),
            notification_target_class=str(value["notification_target_class"]),
            status=str(value["status"]), expires_at_ms=int(value["expires_at_ms"]),
            dedup_key=str(value["dedup_key"]), clarification_count=int(value.get("clarification_count", 0)),
            prompt_command_id=_optional_str(value.get("prompt_command_id")),
            immediate_alert=value.get("immediate_alert") if isinstance(value.get("immediate_alert"), dict) else None,
            failure_code=_optional_str(value.get("failure_code")),
            updated_at_ms=value.get("updated_at_ms") if isinstance(value.get("updated_at_ms"), int) else None,
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize only explicit operational state."""
        return {
            "event_id": self.event_id, "robot_id": self.robot_id,
            "conversation_id": self.conversation_id, "abnormal_category": self.abnormal_category,
            "event_timestamp_ms": self.event_timestamp_ms, "prompt_timestamp_ms": self.prompt_timestamp_ms,
            "pending_question_type": self.pending_question_type,
            "notification_target_class": self.notification_target_class, "status": self.status,
            "expires_at_ms": self.expires_at_ms, "dedup_key": self.dedup_key,
            "clarification_count": self.clarification_count, "prompt_command_id": self.prompt_command_id,
            "immediate_alert": self.immediate_alert, "failure_code": self.failure_code,
            "updated_at_ms": self.updated_at_ms,
        }


class PendingCareConfirmationStore:
    """Atomic, bounded persistence for one active care question per robot."""

    def __init__(self, memory_dir: str | Path, ttl_seconds: int) -> None:
        self.root = Path(memory_dir)
        self.path = self.root / "pending_care_confirmations.json"
        self.ttl_ms = ttl_seconds * 1000

    def create(
        self,
        *,
        event_id: str,
        robot_id: str,
        abnormal_category: str,
        event_timestamp_ms: int | None,
        immediate_alert: dict[str, Any] | None,
        created_at_ms: int | None = None,
    ) -> tuple[PendingCareConfirmation, bool]:
        """Create a deduplicated pending question and supersede an older one."""
        timestamp = created_at_ms if created_at_ms is not None else now_ms()
        dedup_key = f"abnormal-care:{event_id}"
        records = self._load()
        for record in records:
            if record.dedup_key == dedup_key:
                return record, False
        updated: list[PendingCareConfirmation] = []
        for record in records:
            if record.robot_id == robot_id and record.status == "pending":
                updated.append(self._replace(record, status="superseded", updated_at_ms=timestamp))
            else:
                updated.append(record)
        target_class = "unverified_direct_alert"
        if immediate_alert and immediate_alert.get("target_class") == "caregiver":
            target_class = "caregiver"
        record = PendingCareConfirmation(
            event_id=event_id, robot_id=robot_id, conversation_id=f"care-{event_id}",
            abnormal_category=abnormal_category,
            event_timestamp_ms=event_timestamp_ms if event_timestamp_ms is not None else timestamp,
            prompt_timestamp_ms=timestamp, pending_question_type="notify_family_or_caregiver",
            notification_target_class=target_class, status="pending", expires_at_ms=timestamp + self.ttl_ms,
            dedup_key=dedup_key, immediate_alert=immediate_alert, updated_at_ms=timestamp,
        )
        updated.append(record)
        self._save(updated)
        return record, True

    def active_for_robot(self, robot_id: str, at_ms: int | None = None) -> PendingCareConfirmation | None:
        """Return the current question, expiring stale state before routing ASR."""
        timestamp = at_ms if at_ms is not None else now_ms()
        records = self._load()
        changed = False
        active: PendingCareConfirmation | None = None
        updated: list[PendingCareConfirmation] = []
        for record in records:
            current = record
            if record.status == "pending" and record.expires_at_ms <= timestamp:
                current = self._replace(record, status="expired", failure_code="ABNORMAL_CONFIRMATION_EXPIRED", updated_at_ms=timestamp)
                changed = True
            if current.robot_id == robot_id and current.status == "pending":
                active = current
            updated.append(current)
        if changed:
            self._save(updated)
        return active

    def update(
        self,
        event_id: str,
        *,
        status: str | None = None,
        clarification_count: int | None = None,
        prompt_command_id: str | None = None,
        failure_code: str | None = None,
        updated_at_ms: int | None = None,
    ) -> PendingCareConfirmation | None:
        """Atomically update one record without overwriting unrelated incidents."""
        records = self._load()
        updated: list[PendingCareConfirmation] = []
        matched: PendingCareConfirmation | None = None
        for record in records:
            if record.event_id != event_id:
                updated.append(record)
                continue
            matched = self._replace(
                record, status=status if status is not None else record.status,
                clarification_count=clarification_count if clarification_count is not None else record.clarification_count,
                prompt_command_id=prompt_command_id if prompt_command_id is not None else record.prompt_command_id,
                failure_code=failure_code if failure_code is not None else record.failure_code,
                updated_at_ms=updated_at_ms if updated_at_ms is not None else now_ms(),
            )
            updated.append(matched)
        if matched is not None:
            self._save(updated)
        return matched

    def update_by_command_result(
        self, command_id: str, result_status: str, at_ms: int | None = None
    ) -> PendingCareConfirmation | None:
        """Record initial-question execution evidence without retrying a failed command."""
        for record in self._load():
            if record.prompt_command_id == command_id:
                code = None if result_status in {"success", "partial_success"} else "ABNORMAL_CARE_PROMPT_EXECUTION_FAILED"
                return self.update(
                    record.event_id,
                    status="prompt_execution_failed" if code else record.status,
                    failure_code=code,
                    updated_at_ms=at_ms,
                )
        return None

    def _load(self) -> list[PendingCareConfirmation]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = raw.get("records") if isinstance(raw, dict) else None
        if not isinstance(entries, list):
            return []
        records: list[PendingCareConfirmation] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                records.append(PendingCareConfirmation.from_dict(entry))
            except (TypeError, ValueError):
                continue
        return records[-MAX_RECORDS:]

    def _save(self, records: list[PendingCareConfirmation]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "1.0", "records": [record.as_dict() for record in records[-MAX_RECORDS:]]}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _replace(record: PendingCareConfirmation, **changes: Any) -> PendingCareConfirmation:
        value = record.as_dict()
        value.update(changes)
        return PendingCareConfirmation.from_dict(value)


def direct_alert_from_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Read a non-secret direct-alert receipt carried by the abnormal event."""
    notification = payload.get("notification")
    if not isinstance(notification, dict):
        return None
    alert = notification.get("immediate_alert")
    if not isinstance(alert, dict):
        return None
    allowed = {"transport", "status", "failure_code", "target_class"}
    return {key: alert[key] for key in allowed if isinstance(alert.get(key), str)}


def direct_alert_delivered(record: PendingCareConfirmation) -> bool:
    """Require an explicit receipt; readiness flags and assumptions are insufficient."""
    alert = record.immediate_alert or {}
    return alert.get("transport") == "discord_webhook" and alert.get("status") == "delivered"


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
