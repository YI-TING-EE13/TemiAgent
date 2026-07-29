"""Root-owned native Hermes Media tools for the resident Temi worker.

This module is loaded dynamically by ``hermes_resident_server.py``.  It uses
the upstream Hermes registry API without modifying the nested checkout and
forwards every tool call to the Bridge's local callback socket; it never
imports MQTT or publishes a command itself.
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import json
from pathlib import Path
import sys
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SRC = ROOT / "hermes_temi_bridge" / "src"
if BRIDGE_SRC.as_posix() not in sys.path:
    sys.path.insert(0, BRIDGE_SRC.as_posix())

from hermes_temi_bridge.media_callback_socket import invoke_media_callback_socket


TOOLSET = "temi-demo-media"
VIDEO_ID = "elderly_hand_exercise"
_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "temi_resident_media_context", default=None
)
_callback_socket: str | None = None


def media_tool_schemas() -> list[dict[str, Any]]:
    """Return the exact native function schemas exposed to Hermes."""
    return [
        {
            "name": "play_video",
            "description": "Request the allowlisted elderly hand exercise video through the Temi Bridge.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["video_id"],
                "properties": {"video_id": {"type": "string", "enum": [VIDEO_ID]}},
            },
        },
        {
            "name": "pause_video",
            "description": "Pause the active allowlisted Temi video session through the Bridge.",
            "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
        },
        {
            "name": "resume_video",
            "description": "Resume the active allowlisted Temi video session through the Bridge.",
            "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
        },
        {
            "name": "stop_video",
            "description": "Stop the active allowlisted Temi video session through the Bridge.",
            "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
        },
    ]


def install_media_tools(*, callback_socket: str) -> list[str]:
    """Register the root-owned toolset into the resident process only."""
    global _callback_socket
    if not callback_socket or not Path(callback_socket).is_absolute():
        raise ValueError("HERMES_MEDIA_CALLBACK_SOCKET must be an absolute Unix socket path")
    _callback_socket = callback_socket
    from tools.registry import registry

    for schema in media_tool_schemas():
        action = schema["name"]
        registry.register(
            name=action,
            toolset=TOOLSET,
            schema=schema,
            handler=lambda args, _action=action, **_kwargs: _handle_media_tool(_action, args),
            description=schema["description"],
            emoji="🎬",
            max_result_size_chars=600,
        )
    return [schema["name"] for schema in media_tool_schemas()]


@contextmanager
def invocation_context(context: dict[str, str]) -> Iterator[None]:
    """Bind only the current Bridge event metadata to native tool callbacks."""
    token = _context.set(dict(context))
    try:
        yield
    finally:
        _context.reset(token)


def invoke_registered_media_tool(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Invoke the same reviewed handler used by the native Hermes registry.

    The deterministic Resident fast path uses this function rather than the
    Bridge API, keeping its route identical to an upstream Hermes tool call.
    """
    if action not in {"play_video", "pause_video", "resume_video", "stop_video"}:
        return {"status": "rejected", "error_code": "MEDIA_TOOL_INVALID_ACTION"}
    if not isinstance(args, dict):
        return {"status": "rejected", "error_code": "MEDIA_TOOL_INVALID_ARGUMENTS"}
    if action == "play_video":
        if args != {"video_id": VIDEO_ID}:
            return {"status": "rejected", "error_code": "VIDEO_ID_NOT_ALLOWED"}
    elif args:
        return {"status": "rejected", "error_code": "MEDIA_TOOL_INVALID_ARGUMENTS"}
    try:
        result = json.loads(_handle_media_tool(action, args))
    except json.JSONDecodeError:
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_RESPONSE"}
    if not isinstance(result, dict):
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_RESPONSE"}
    return result


def _handle_media_tool(action: str, args: dict[str, Any]) -> str:
    context = _context.get()
    if context is None or _callback_socket is None:
        return json.dumps({"status": "rejected", "error_code": "MEDIA_CALLBACK_CONTEXT_UNAVAILABLE"}, ensure_ascii=False)
    if not isinstance(args, dict):
        return json.dumps({"status": "rejected", "error_code": "MEDIA_TOOL_INVALID_ARGUMENTS"}, ensure_ascii=False)
    if action == "play_video":
        video_id = args.get("video_id")
    else:
        video_id = VIDEO_ID if not args else None
    payload = {
        "event_id": context.get("event_id", ""),
        "robot_id": context.get("robot_id", ""),
        "resident_id": context.get("resident_id", ""),
        "action": action,
        "video_id": video_id,
    }
    result = invoke_media_callback_socket(_callback_socket, payload)
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
