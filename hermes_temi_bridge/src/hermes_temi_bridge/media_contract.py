"""Canonical media v1.1 request builders and boundary validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid


MEDIA_ACTION_EXECUTION_CLASS = {
    "play_video": "serialized_execution",
    "pause_video": "active_playback_control",
    "resume_video": "active_playback_control",
    "stop_video": "active_playback_control",
}
MEDIA_CONTROL_ACTIONS = {"pause_video", "resume_video", "stop_video"}
MEDIA_RESULT_STATUSES = {
    "accepted",
    "started",
    "succeeded",
    "completed",
    "cancelled",
    "rejected",
    "failed",
}
MEDIA_ERROR_CODES = {
    "MEDIA_SESSION_ACTIVE",
    "MEDIA_SESSION_NOT_FOUND",
    "MEDIA_SESSION_NOT_PLAYING",
    "MEDIA_SESSION_NOT_PAUSED",
    "VIDEO_ID_NOT_ALLOWED",
    "MEDIA_CONTROL_CONFLICT",
    "UNSUPPORTED_MEDIA_ACTION",
    "APP_PROCESS_RESTART",
    "LOCAL_USER_STOP",
    "INTERNAL_ERROR",
}
MEDIA_RESULT_DELIVERIES = {
    "original",
    "active_reference",
    "cached_replay",
    "restart_reconciliation",
}
MEDIA_PLAYBACK_STATES = {"playing", "paused", "completed", "cancelled", "failed"}
MEDIA_ACTORS = {"remote_command", "local_user", "app_process"}
MEDIA_CANCEL_REASONS = {"remote_stop", "local_user_stop", "app_process_restart"}

MEDIA_REQUEST_FIELDS = {
    "schema_version",
    "message_type",
    "command_id",
    "request_id",
    "event_id",
    "robot_id",
    "resident_id",
    "action",
    "execution_class",
    "target_playback_session_id",
    "video_id",
    "parameters",
    "source",
    "timestamp",
}
MEDIA_RESULT_FIELDS = {
    "schema_version",
    "message_type",
    "command_id",
    "request_id",
    "event_id",
    "robot_id",
    "command_action",
    "video_id",
    "status",
    "terminal",
    "playback_session_id",
    "target_playback_session_id",
    "active_playback_session_id",
    "playback_state",
    "cancelled_by_command_id",
    "cancel_reason",
    "actor",
    "result_delivery",
    "error_code",
    "error_message",
    "timestamp",
}


class MediaContractError(ValueError):
    """Raised when a media request or result violates the v1.1 contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def build_media_command_request(
    *,
    event_id: str,
    robot_id: str,
    resident_id: str,
    action: str,
    video_id: str,
    target_playback_session_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    command_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build and validate one canonical media v1.1 request."""
    execution_class = MEDIA_ACTION_EXECUTION_CLASS.get(action)
    if execution_class is None:
        raise MediaContractError(
            "UNSUPPORTED_MEDIA_ACTION",
            f"unsupported media action: {action!r}",
            details={"action": action},
        )
    resolved_command_id = command_id or make_media_command_id(event_id, action)
    request = {
        "schema_version": "1.1",
        "message_type": "video.command",
        "command_id": resolved_command_id,
        "request_id": resolved_command_id,
        "event_id": event_id,
        "robot_id": robot_id,
        "resident_id": resident_id,
        "action": action,
        "execution_class": execution_class,
        "target_playback_session_id": target_playback_session_id,
        "video_id": video_id,
        "parameters": dict(parameters or {}),
        "source": "hermes_temi_bridge",
        "timestamp": timestamp or _now_iso(),
    }
    validate_media_command_request(request)
    return request


def validate_media_command_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the strict v1.1 request shape and action-derived execution class."""
    _require_exact_fields(payload, MEDIA_REQUEST_FIELDS, "media request")
    _require_const(payload, "schema_version", "1.1")
    _require_const(payload, "message_type", "video.command")
    for field in (
        "command_id",
        "request_id",
        "event_id",
        "robot_id",
        "resident_id",
        "action",
        "execution_class",
        "video_id",
        "source",
        "timestamp",
    ):
        _require_nonempty_string(payload, field)
    if payload["command_id"] != payload["request_id"]:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "command_id must equal request_id",
        )
    action = payload["action"]
    expected_class = MEDIA_ACTION_EXECUTION_CLASS.get(action)
    if expected_class is None:
        raise MediaContractError(
            "UNSUPPORTED_MEDIA_ACTION",
            f"unsupported media action: {action!r}",
        )
    if payload["execution_class"] != expected_class:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{action} requires execution_class={expected_class}",
            details={
                "action": action,
                "execution_class": payload["execution_class"],
                "expected_execution_class": expected_class,
            },
        )
    target = payload["target_playback_session_id"]
    if action == "play_video":
        if target is not None:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "play_video must not target an existing playback session",
            )
    elif not isinstance(target, str) or not target:
        raise MediaContractError(
            "MEDIA_SESSION_NOT_FOUND",
            f"{action} requires target_playback_session_id",
        )
    parameters = payload["parameters"]
    if not isinstance(parameters, dict) or len(parameters) > 16:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "parameters must be an object with at most 16 properties",
        )
    if payload["source"] not in {
        "hermes_temi_bridge",
        "temi_app_manual",
        "remote_operator",
    }:
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", "unsupported media request source")
    return dict(payload)


def validate_media_command_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the strict v1.1 result shape and lifecycle combinations."""
    _require_exact_fields(payload, MEDIA_RESULT_FIELDS, "media result")
    _require_const(payload, "schema_version", "1.1")
    _require_const(payload, "message_type", "video.command_result")
    for field in (
        "command_id",
        "request_id",
        "event_id",
        "robot_id",
        "command_action",
        "video_id",
        "status",
        "actor",
        "result_delivery",
        "timestamp",
    ):
        _require_nonempty_string(payload, field)
    if payload["command_id"] != payload["request_id"]:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "command_id must equal request_id",
        )
    action = payload["command_action"]
    if action not in MEDIA_ACTION_EXECUTION_CLASS:
        raise MediaContractError(
            "UNSUPPORTED_MEDIA_ACTION",
            f"unsupported media result action: {action!r}",
        )
    status = payload["status"]
    if status not in MEDIA_RESULT_STATUSES:
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", f"unsupported result status: {status!r}")
    if not isinstance(payload["terminal"], bool):
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", "terminal must be a boolean")
    expected_terminal = status not in {"accepted", "started"}
    if payload["terminal"] is not expected_terminal:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"status={status} requires terminal={str(expected_terminal).lower()}",
        )
    for field in (
        "playback_session_id",
        "target_playback_session_id",
        "active_playback_session_id",
        "cancelled_by_command_id",
    ):
        _require_nullable_nonempty_string(payload, field)
    _require_nullable_enum(payload, "playback_state", MEDIA_PLAYBACK_STATES)
    _require_nullable_enum(payload, "cancel_reason", MEDIA_CANCEL_REASONS)
    if payload["actor"] not in MEDIA_ACTORS:
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", "unsupported result actor")
    delivery = payload["result_delivery"]
    if delivery not in MEDIA_RESULT_DELIVERIES:
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", "unsupported result_delivery")

    is_error = status in {"rejected", "failed"}
    if is_error:
        if payload["error_code"] not in MEDIA_ERROR_CODES:
            raise MediaContractError("MEDIA_CONTROL_CONFLICT", "invalid media error_code")
        message = payload["error_message"]
        if not isinstance(message, str) or not message or len(message) > 500:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "rejected or failed result requires a bounded error_message",
            )
    elif payload["error_code"] is not None or payload["error_message"] is not None:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "non-error result must use null error fields",
        )

    target = payload["target_playback_session_id"]
    session_id = payload["playback_session_id"]
    state = payload["playback_state"]
    if action == "play_video":
        if target is not None or status == "succeeded":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "play result has invalid target or status",
            )
    else:
        if not isinstance(target, str) or not target:
            raise MediaContractError(
                "MEDIA_SESSION_NOT_FOUND",
                "control result requires target_playback_session_id",
            )
        if status not in {"succeeded", "rejected", "failed"}:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "control result has a non-terminal lifecycle status",
            )

    _validate_result_state(payload, action, status, session_id, state)
    _validate_cancellation(payload, status)

    active_session_id = payload["active_playback_session_id"]
    is_active_rejection = status == "rejected" and payload["error_code"] == "MEDIA_SESSION_ACTIVE"
    if is_active_rejection:
        if session_id is not None or not active_session_id:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "MEDIA_SESSION_ACTIVE requires only active_playback_session_id",
            )
    elif active_session_id is not None:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "active_playback_session_id is only valid for MEDIA_SESSION_ACTIVE",
        )

    if delivery == "active_reference" and (
        action != "play_video" or status not in {"accepted", "started"} or payload["terminal"]
    ):
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "active_reference must reference a non-terminal play result",
        )
    if delivery == "cached_replay" and not payload["terminal"]:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "cached_replay must reference a terminal result",
        )
    if delivery == "restart_reconciliation" and (
        not payload["terminal"] or payload["actor"] != "app_process"
    ):
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "restart_reconciliation must be terminal and emitted by app_process",
        )
    return dict(payload)


def make_media_command_id(event_id: str, action: str) -> str:
    """Create an opaque command ID without reusing event or session identity."""
    safe_event_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in event_id)
    safe_action = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in action)
    return f"cmd_media_{safe_event_id}_{safe_action}_{uuid.uuid4().hex[:12]}"


def _validate_result_state(
    payload: dict[str, Any],
    action: str,
    status: str,
    session_id: Any,
    state: Any,
) -> None:
    if status == "accepted":
        if not session_id or state is not None:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "accepted play requires a session ID and null playback_state",
            )
    elif status == "started":
        if not session_id or state != "playing":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "started play requires session state playing",
            )
    elif status == "completed":
        if not session_id or state != "completed":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "completed play requires session state completed",
            )
    elif status == "cancelled":
        if action != "play_video" or not session_id or state != "cancelled":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "cancelled is a terminal play result",
            )
    elif status == "succeeded":
        expected_state = {
            "pause_video": "paused",
            "resume_video": "playing",
            "stop_video": "cancelled",
        }.get(action)
        if not session_id or state != expected_state:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                f"{action} success requires playback_state={expected_state}",
            )


def _validate_cancellation(payload: dict[str, Any], status: str) -> None:
    reason = payload["cancel_reason"]
    cancelled_by = payload["cancelled_by_command_id"]
    actor = payload["actor"]
    if status != "cancelled":
        if reason is not None or cancelled_by is not None:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "only cancelled play results may contain cancellation linkage",
            )
        return
    if reason == "remote_stop":
        if not cancelled_by or actor != "remote_command":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "remote_stop requires a cancelling command and remote_command actor",
            )
    elif reason == "local_user_stop":
        if cancelled_by is not None or actor != "local_user":
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "local_user_stop must not reference a remote command",
            )
    elif reason == "app_process_restart":
        if (
            cancelled_by is not None
            or actor != "app_process"
            or payload["result_delivery"]
            not in {"restart_reconciliation", "cached_replay"}
        ):
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "app_process_restart requires restart reconciliation or cached replay "
                "without a command link",
            )
    else:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            "cancelled play requires an allowlisted cancel_reason",
        )


def _require_exact_fields(payload: dict[str, Any], fields: set[str], label: str) -> None:
    if not isinstance(payload, dict):
        raise MediaContractError("MEDIA_CONTROL_CONFLICT", f"{label} must be an object")
    missing = sorted(fields - set(payload))
    extra = sorted(set(payload) - fields)
    if missing or extra:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{label} fields do not match the canonical schema",
            details={"missing_fields": missing, "extra_fields": extra},
        )


def _require_const(payload: dict[str, Any], field: str, expected: str) -> None:
    if payload.get(field) != expected:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{field} must equal {expected}",
        )


def _require_nonempty_string(payload: dict[str, Any], field: str) -> None:
    if not isinstance(payload.get(field), str) or not payload[field]:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{field} must be a non-empty string",
        )


def _require_nullable_nonempty_string(payload: dict[str, Any], field: str) -> None:
    value = payload.get(field)
    if value is not None and (not isinstance(value, str) or not value):
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{field} must be null or a non-empty string",
        )


def _require_nullable_enum(payload: dict[str, Any], field: str, values: set[str]) -> None:
    value = payload.get(field)
    if value is not None and value not in values:
        raise MediaContractError(
            "MEDIA_CONTROL_CONFLICT",
            f"{field} has an unsupported value",
        )


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
