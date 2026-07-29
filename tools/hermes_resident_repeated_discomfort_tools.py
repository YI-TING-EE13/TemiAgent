"""Root-owned native care tools for the controlled repeated-discomfort Demo."""

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

from hermes_temi_bridge.demo_callback_socket import invoke_demo_callback_socket


TOOLSET = "temi-demo-repeated-discomfort"
_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("temi_resident_repeated_discomfort_context", default=None)
_callback_socket: str | None = None


def repeated_discomfort_tool_schemas() -> list[dict[str, Any]]:
    """Return schemas with no free-text memory query or arbitrary records."""
    return [
        {"name": "retrieve_repeated_discomfort", "description": "Retrieve only the controlled Demo father's seeded prior headache event.", "parameters": {"type": "object", "additionalProperties": False, "properties": {}}},
        {"name": "confirm_repeated_headache", "description": "Advance only the active repeated-discomfort Demo confirmation.", "parameters": {"type": "object", "additionalProperties": False, "properties": {}}},
        {"name": "record_repeated_blood_pressure", "description": "Record explicit user-provided systolic and diastolic Demo values after confirmation.", "parameters": {"type": "object", "additionalProperties": False, "required": ["systolic", "diastolic", "asr_text"], "properties": {"systolic": {"type": "integer"}, "diastolic": {"type": "integer"}, "asr_text": {"type": "string", "maxLength": 80}}}},
    ]


def install_repeated_discomfort_tools(*, callback_socket: str) -> list[str]:
    """Register root-owned care tools that can only reach the Bridge socket."""
    global _callback_socket
    if not callback_socket or not Path(callback_socket).is_absolute():
        raise ValueError("HERMES_DEMO_CARE_CALLBACK_SOCKET must be an absolute Unix socket path")
    _callback_socket = callback_socket
    from tools.registry import registry

    for schema in repeated_discomfort_tool_schemas():
        action = schema["name"]
        registry.register(name=action, toolset=TOOLSET, schema=schema, handler=lambda args, _action=action, **_kwargs: _handle_repeated_discomfort_tool(_action, args), description=schema["description"], emoji="🧾", max_result_size_chars=600)
    return [schema["name"] for schema in repeated_discomfort_tool_schemas()]


@contextmanager
def invocation_context(context: dict[str, str]) -> Iterator[None]:
    token = _context.set(dict(context))
    try:
        yield
    finally:
        _context.reset(token)


def invoke_registered_repeated_discomfort_tool(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Use the native registry callback handler; no resident MQTT or file access."""
    expected = {
        "retrieve_repeated_discomfort": set(),
        "confirm_repeated_headache": set(),
        "record_repeated_blood_pressure": {"systolic", "diastolic", "asr_text"},
    }
    if action not in expected or not isinstance(args, dict) or set(args) != expected.get(action):
        return {"status": "rejected", "error_code": "DEMO_CARE_TOOL_INVALID_ARGUMENTS"}
    if action == "record_repeated_blood_pressure":
        if (
            any(isinstance(args.get(key), bool) or not isinstance(args.get(key), int) for key in ("systolic", "diastolic"))
            or not isinstance(args.get("asr_text"), str)
            or not args["asr_text"].strip()
            or len(args["asr_text"]) > 80
        ):
            return {"status": "rejected", "error_code": "DEMO_CARE_TOOL_INVALID_ARGUMENTS"}
    try:
        parsed = json.loads(_handle_repeated_discomfort_tool(action, args))
    except json.JSONDecodeError:
        return {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}
    return parsed if isinstance(parsed, dict) else {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}


def _handle_repeated_discomfort_tool(action: str, args: dict[str, Any]) -> str:
    context = _context.get()
    if context is None or _callback_socket is None:
        return json.dumps({"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_CONTEXT_UNAVAILABLE"}, ensure_ascii=False)
    payload: dict[str, Any] = {"action": action, "event_id": context.get("event_id", ""), "robot_id": context.get("robot_id", ""), "resident_id": context.get("resident_id", "")}
    payload.update(args)
    return json.dumps(invoke_demo_callback_socket(_callback_socket, payload), ensure_ascii=False, separators=(",", ":"))
