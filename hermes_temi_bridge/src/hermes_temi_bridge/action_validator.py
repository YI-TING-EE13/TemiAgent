"""Validation helpers for Hermes-produced Temi and care-memory actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROBOT_ACTION_TYPES = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}
MEMORY_ACTION_TYPES = {"log_event", "mark_reminder_done", "generate_summary", "notify_caregiver_mock"}
ALLOWED_ACTION_TYPES = ROBOT_ACTION_TYPES | MEMORY_ACTION_TYPES
ALLOWED_TURN_DIRECTIONS = {"left", "right"}
ALLOWED_TURN_DEGREES = {15, 30, 45, 60, 90}
DEFAULT_NAVIGATION_TARGETS = {"home_base", "kitchen", "living_room", "meeting_room"}
HOME_ESI_LEVELS = {"Normal", "L1", "L2", "L3"}


class ActionValidationError(ValueError):
    """Raised when Hermes returns an action payload that is unsafe or invalid."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        """Create an error with a machine-readable reason and optional details."""
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class ValidatedActionOutput:
    """A normalized, schema-checked Hermes action response."""

    schema_version: str
    event_id: str
    robot_id: str
    confidence: float
    reasoning_summary: str
    cognitive_state: dict[str, Any]
    actions: list[dict[str, Any]]
    robot_actions: list[dict[str, Any]]
    memory_actions: list[dict[str, Any]]
    raw: dict[str, Any]


def validate_action_output(
    payload: dict[str, Any],
    expected_event_id: str,
    expected_robot_id: str,
    max_actions: int = 5,
    navigation_targets: set[str] | None = None,
) -> ValidatedActionOutput:
    """Validate the top-level Hermes action JSON before MQTT dispatch.

    Args:
        payload: Parsed JSON object returned by Hermes.
        expected_event_id: Event id from the originating ASR event.
        expected_robot_id: Robot id from the originating ASR event.
        max_actions: Maximum number of actions accepted from one model response.
        navigation_targets: Optional allowlist of Temi map locations.

    Returns:
        A normalized action output object suitable for command construction.

    Raises:
        ActionValidationError: If the payload violates the Bridge contract.
    """
    targets = navigation_targets or DEFAULT_NAVIGATION_TARGETS
    if payload.get("schema_version") != "1.0":
        raise ActionValidationError("unsupported_action_schema_version")
    if payload.get("event_id") != expected_event_id:
        raise ActionValidationError("event_id_mismatch")
    if payload.get("robot_id") != expected_robot_id:
        raise ActionValidationError("robot_id_mismatch")
    confidence = payload.get("confidence")
    if not isinstance(confidence, int | float) or not 0 <= float(confidence) <= 1:
        raise ActionValidationError("invalid_confidence")
    reasoning_summary = payload.get("reasoning_summary")
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        raise ActionValidationError("missing_reasoning_summary")
    if len(reasoning_summary) > 500:
        raise ActionValidationError("reasoning_summary_too_long")
    cognitive_state = _validate_cognitive_state(payload.get("cognitive_state"))
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ActionValidationError("missing_actions")
    if len(actions) > max_actions:
        raise ActionValidationError("too_many_actions", {"max_actions": max_actions})

    validated_actions = [_validate_action(action, targets) for action in actions]
    robot_actions = [action for action in validated_actions if action["type"] in ROBOT_ACTION_TYPES]
    memory_actions = [action for action in validated_actions if action["type"] in MEMORY_ACTION_TYPES]
    return ValidatedActionOutput(
        schema_version="1.0",
        event_id=expected_event_id,
        robot_id=expected_robot_id,
        confidence=float(confidence),
        reasoning_summary=reasoning_summary.strip(),
        cognitive_state=cognitive_state,
        actions=validated_actions,
        robot_actions=robot_actions,
        memory_actions=memory_actions,
        raw=payload,
    )


def _validate_cognitive_state(value: Any) -> dict[str, Any]:
    """Validate the care cognition debug state required for the Demo."""
    if not isinstance(value, dict):
        raise ActionValidationError("missing_cognitive_state")
    home_esi_level = value.get("home_esi_level")
    if home_esi_level not in HOME_ESI_LEVELS:
        raise ActionValidationError("invalid_home_esi_level", {"home_esi_level": home_esi_level})
    risk_reason = value.get("risk_reason")
    if not isinstance(risk_reason, str) or not risk_reason.strip():
        raise ActionValidationError("missing_risk_reason")

    cognitive_state = dict(value)
    cognitive_state["home_esi_level"] = home_esi_level
    cognitive_state["risk_reason"] = risk_reason.strip()
    return cognitive_state


def _validate_action(action: Any, navigation_targets: set[str]) -> dict[str, Any]:
    """Validate and normalize one action object from a Hermes response."""
    if not isinstance(action, dict):
        raise ActionValidationError("invalid_action")
    action_id = action.get("action_id")
    if not isinstance(action_id, str) or not action_id.strip():
        raise ActionValidationError("missing_action_id")
    action_type = action.get("type")
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ActionValidationError("invalid_action_type", {"type": action_type})

    if action_type in {"speak", "ask_clarification"}:
        text = action.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ActionValidationError("missing_action_text", {"action_id": action_id})
        if len(text) > 500:
            raise ActionValidationError("action_text_too_long", {"action_id": action_id})
        return {
            "action_id": action_id,
            "type": action_type,
            "text": text.strip(),
            "language": action.get("language") or "zh-TW",
        }

    if action_type == "turn":
        direction = action.get("direction")
        degrees = action.get("degrees")
        if direction not in ALLOWED_TURN_DIRECTIONS:
            raise ActionValidationError("invalid_turn_direction", {"action_id": action_id})
        if degrees not in ALLOWED_TURN_DEGREES:
            raise ActionValidationError("invalid_turn_degrees", {"action_id": action_id})
        return {
            "action_id": action_id,
            "type": "turn",
            "direction": direction,
            "degrees": degrees,
        }

    if action_type == "navigate":
        target = action.get("target")
        if target not in navigation_targets:
            raise ActionValidationError(
                "navigation_target_not_allowed", {"action_id": action_id, "target": target}
            )
        return {"action_id": action_id, "type": "navigate", "target": target}

    if action_type == "stop":
        return {"action_id": action_id, "type": "stop"}

    if action_type == "noop":
        reason = action.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ActionValidationError("missing_noop_reason", {"action_id": action_id})
        return {"action_id": action_id, "type": "noop", "reason": reason.strip()}

    return _validate_memory_action(action_id, action_type, action)


def _validate_memory_action(action_id: str, action_type: str, action: dict[str, Any]) -> dict[str, Any]:
    """Validate a Bridge-internal memory/demo action."""
    data = _action_parameters(action)
    if action_type == "log_event":
        event_type = data.get("event_type")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ActionValidationError("missing_event_type", {"action_id": action_id})
        return {
            "action_id": action_id,
            "type": "log_event",
            "event_type": event_type.strip(),
            "outcome": _optional_str(data.get("outcome")),
            "details": _memory_details(data),
        }

    if action_type == "mark_reminder_done":
        reminder_id = data.get("reminder_id")
        if not isinstance(reminder_id, str) or not reminder_id.strip():
            raise ActionValidationError("missing_reminder_id", {"action_id": action_id})
        return {
            "action_id": action_id,
            "type": "mark_reminder_done",
            "reminder_id": reminder_id.strip(),
            "completed_at": _optional_str(data.get("completed_at")),
        }

    if action_type == "generate_summary":
        return {
            "action_id": action_id,
            "type": "generate_summary",
            "date": _optional_str(data.get("date")),
        }

    if action_type == "notify_caregiver_mock":
        message = data.get("message")
        return {
            "action_id": action_id,
            "type": "notify_caregiver_mock",
            "target": _optional_str(data.get("target")) or "caregiver_demo_primary",
            "message": message.strip() if isinstance(message, str) and message.strip() else "",
        }

    raise ActionValidationError("invalid_action_type", {"type": action_type})


def _action_parameters(action: dict[str, Any]) -> dict[str, Any]:
    """Return action parameters, accepting either flat fields or a payload object."""
    payload = action.get("payload")
    merged = dict(payload) if isinstance(payload, dict) else {}
    for key, value in action.items():
        if key not in {"payload", "action_id", "type"}:
            merged[key] = value
    return merged


def _memory_details(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize optional memory details while preserving useful model-provided context."""
    details = dict(data["details"]) if isinstance(data.get("details"), dict) else {}
    for key in ("description", "note"):
        value = _optional_str(data.get(key))
        if value:
            details[key] = value
    return details


def _optional_str(value: Any) -> str | None:
    """Return a stripped optional string."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_dict(value: Any) -> dict[str, Any]:
    """Return an optional details object."""
    return value if isinstance(value, dict) else {}
