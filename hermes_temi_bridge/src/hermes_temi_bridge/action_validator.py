from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_ACTION_TYPES = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}
ALLOWED_TURN_DIRECTIONS = {"left", "right"}
ALLOWED_TURN_DEGREES = {15, 30, 45, 60, 90}
DEFAULT_NAVIGATION_TARGETS = {"home_base", "kitchen", "living_room", "meeting_room"}


class ActionValidationError(ValueError):
    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class ValidatedActionOutput:
    schema_version: str
    event_id: str
    robot_id: str
    confidence: float
    reasoning_summary: str
    actions: list[dict[str, Any]]
    raw: dict[str, Any]


def validate_action_output(
    payload: dict[str, Any],
    expected_event_id: str,
    expected_robot_id: str,
    max_actions: int = 5,
    navigation_targets: set[str] | None = None,
) -> ValidatedActionOutput:
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
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ActionValidationError("missing_actions")
    if len(actions) > max_actions:
        raise ActionValidationError("too_many_actions", {"max_actions": max_actions})

    validated_actions = [_validate_action(action, targets) for action in actions]
    return ValidatedActionOutput(
        schema_version="1.0",
        event_id=expected_event_id,
        robot_id=expected_robot_id,
        confidence=float(confidence),
        reasoning_summary=reasoning_summary.strip(),
        actions=validated_actions,
        raw=payload,
    )


def _validate_action(action: Any, navigation_targets: set[str]) -> dict[str, Any]:
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

    reason = action.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ActionValidationError("missing_noop_reason", {"action_id": action_id})
    return {"action_id": action_id, "type": "noop", "reason": reason.strip()}
