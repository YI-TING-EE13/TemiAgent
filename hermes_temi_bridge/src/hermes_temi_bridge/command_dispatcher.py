"""Command payload builders for the Temi MQTT command topic."""

from __future__ import annotations

import time
from typing import Any

from .action_validator import ValidatedActionOutput


def now_ms() -> int:
    """Return the current Unix time in milliseconds."""
    return int(time.time() * 1000)


def build_command_request(
    output: ValidatedActionOutput,
    command_id: str | None = None,
    created_at_ms: int | None = None,
) -> dict[str, Any]:
    """Build a canonical command request from validated Hermes actions."""
    if not output.robot_actions:
        raise ValueError("cannot build command request without robot actions")
    return {
        "schema_version": "1.0",
        "command_id": command_id or make_command_id(output.event_id),
        "event_id": output.event_id,
        "robot_id": output.robot_id,
        "source": "hermes_temi_bridge",
        "created_at_ms": created_at_ms or now_ms(),
        "actions": output.robot_actions,
    }


def make_command_id(event_id: str) -> str:
    """Create a stable, MQTT-safe command id prefix from an event id."""
    safe_event_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in event_id)
    return f"cmd_{safe_event_id}_{now_ms()}"


def fallback_command(
    event_id: str,
    robot_id: str,
    text: str,
    language: str = "zh-TW",
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a speak fallback command used when event handling fails safely."""
    action = {
        "action_id": "fallback_speak",
        "type": "speak",
        "text": text,
        "language": language,
    }
    payload = {
        "schema_version": "1.0",
        "command_id": make_command_id(event_id),
        "event_id": event_id,
        "robot_id": robot_id,
        "source": "hermes_temi_bridge",
        "created_at_ms": now_ms(),
        "actions": [action],
    }
    if reason:
        payload["fallback_reason"] = reason
    return payload
