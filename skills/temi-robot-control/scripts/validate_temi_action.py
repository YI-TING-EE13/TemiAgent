from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) != 2:
        print("usage: validate_temi_action.py <schema.json> <payload.json>", file=sys.stderr)
        return 2
    schema_path = Path(args[0])
    payload_path = Path(args[1])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    errors = validate(payload, schema)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok")
    return 0


def validate(payload: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in payload:
            errors.append(f"missing required field: {key}")
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("confidence must be between 0 and 1")
    actions = payload.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 5:
        errors.append("actions must contain 1 to 5 items")
        return errors
    allowed_types = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}
    allowed_targets = {"home_base", "kitchen", "living_room", "meeting_room"}
    allowed_degrees = {15, 30, 45, 60, 90}
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"actions[{index}] must be an object")
            continue
        action_type = action.get("type")
        if not action.get("action_id"):
            errors.append(f"actions[{index}].action_id is required")
        if action_type not in allowed_types:
            errors.append(f"actions[{index}].type is not allowed: {action_type}")
        if action_type in {"speak", "ask_clarification"} and not action.get("text"):
            errors.append(f"actions[{index}].text is required")
        if action_type == "navigate" and action.get("target") not in allowed_targets:
            errors.append(f"actions[{index}].target is not allowed")
        if action_type == "turn" and action.get("degrees") not in allowed_degrees:
            errors.append(f"actions[{index}].degrees is not allowed")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
