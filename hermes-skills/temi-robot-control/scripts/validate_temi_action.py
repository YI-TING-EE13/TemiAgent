from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_ACTION_TYPES = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}
ALLOWED_TARGETS = {"home_base", "kitchen", "living_room", "meeting_room"}
ALLOWED_TURN_DIRECTIONS = {"left", "right"}
ALLOWED_TURN_DEGREES = {15, 30, 45, 60, 90}
TOP_LEVEL_KEYS = {
    "schema_version",
    "event_id",
    "robot_id",
    "confidence",
    "reasoning_summary",
    "actions",
}

ACTION_KEYS = {
    "speak": {"action_id", "type", "text", "language"},
    "ask_clarification": {"action_id", "type", "text", "language"},
    "turn": {"action_id", "type", "direction", "degrees"},
    "navigate": {"action_id", "type", "target"},
    "stop": {"action_id", "type"},
    "noop": {"action_id", "type", "reason"},
}

REQUIRED_ACTION_KEYS = {
    "speak": {"action_id", "type", "text"},
    "ask_clarification": {"action_id", "type", "text"},
    "turn": {"action_id", "type", "direction", "degrees"},
    "navigate": {"action_id", "type", "target"},
    "stop": {"action_id", "type"},
    "noop": {"action_id", "type", "reason"},
}


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) not in {1, 2}:
        print(
            "usage: validate_temi_action.py <payload.json> or validate_temi_action.py <schema.json> <payload.json>",
            file=sys.stderr,
        )
        return 2

    payload_path = Path(args[-1])
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 1

    errors = validate(payload)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("ok")
    return 0


def validate(payload: Any) -> list[str]:
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    errors.extend(validate_top_level(payload))

    actions = payload.get("actions")
    if not isinstance(actions, list):
        errors.append("actions must be an array")
        return errors
    if not 1 <= len(actions) <= 5:
        errors.append("actions must contain 1 to 5 items")
        return errors

    seen_action_ids: set[str] = set()
    for index, action in enumerate(actions):
        errors.extend(validate_action(index, action, seen_action_ids))

    return errors


def validate_top_level(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = TOP_LEVEL_KEYS
    missing = sorted(required - payload.keys())
    extra = sorted(payload.keys() - TOP_LEVEL_KEYS)

    for key in missing:
        errors.append(f"missing required field: {key}")
    for key in extra:
        errors.append(f"unexpected top-level field: {key}")

    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")

    for key in ("event_id", "robot_id", "reasoning_summary"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")

    summary = payload.get("reasoning_summary")
    if isinstance(summary, str) and len(summary) > 500:
        errors.append("reasoning_summary must be at most 500 characters")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        errors.append("confidence must be a number between 0 and 1")
    elif not 0 <= confidence <= 1:
        errors.append("confidence must be between 0 and 1")

    return errors


def validate_action(index: int, action: Any, seen_action_ids: set[str]) -> list[str]:
    errors: list[str] = []
    prefix = f"actions[{index}]"

    if not isinstance(action, dict):
        return [f"{prefix} must be an object"]

    action_type = action.get("type")
    if action_type not in ALLOWED_ACTION_TYPES:
        errors.append(f"{prefix}.type is not allowed: {action_type}")
        return errors

    allowed_keys = ACTION_KEYS[action_type]
    required_keys = REQUIRED_ACTION_KEYS[action_type]

    for key in sorted(required_keys - action.keys()):
        errors.append(f"{prefix}.{key} is required")
    for key in sorted(action.keys() - allowed_keys):
        errors.append(f"{prefix}.{key} is not allowed for {action_type}")

    action_id = action.get("action_id")
    if not isinstance(action_id, str) or not action_id.strip():
        errors.append(f"{prefix}.action_id must be a non-empty string")
    elif action_id in seen_action_ids:
        errors.append(f"{prefix}.action_id is duplicated: {action_id}")
    else:
        seen_action_ids.add(action_id)

    if action_type in {"speak", "ask_clarification"}:
        errors.extend(validate_text_action(prefix, action))
    elif action_type == "turn":
        errors.extend(validate_turn_action(prefix, action))
    elif action_type == "navigate":
        errors.extend(validate_navigate_action(prefix, action))
    elif action_type == "noop":
        errors.extend(validate_noop_action(prefix, action))

    return errors


def validate_text_action(prefix: str, action: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = action.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{prefix}.text must be a non-empty string")
    elif len(text) > 500:
        errors.append(f"{prefix}.text must be at most 500 characters")

    language = action.get("language")
    if language is not None and (not isinstance(language, str) or not language.strip()):
        errors.append(f"{prefix}.language must be a non-empty string when present")

    return errors


def validate_turn_action(prefix: str, action: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if action.get("direction") not in ALLOWED_TURN_DIRECTIONS:
        errors.append(f"{prefix}.direction must be one of: left, right")
    if action.get("degrees") not in ALLOWED_TURN_DEGREES:
        errors.append(f"{prefix}.degrees must be one of: 15, 30, 45, 60, 90")
    return errors


def validate_navigate_action(prefix: str, action: dict[str, Any]) -> list[str]:
    target = action.get("target")
    if target not in ALLOWED_TARGETS:
        return [f"{prefix}.target is not allowed: {target}"]
    return []


def validate_noop_action(prefix: str, action: dict[str, Any]) -> list[str]:
    reason = action.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return [f"{prefix}.reason must be a non-empty string"]
    if len(reason) > 300:
        return [f"{prefix}.reason must be at most 300 characters"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
