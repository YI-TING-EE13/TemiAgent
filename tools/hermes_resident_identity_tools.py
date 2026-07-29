"""Root-owned native operator identity tools for the resident Hermes worker."""

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


TOOLSET = "temi-demo-identity"
_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("temi_resident_identity_context", default=None)
_callback_socket: str | None = None


def identity_tool_schemas() -> list[dict[str, Any]]:
    """Return the bounded identity native-tool schemas exposed to Hermes."""
    return [
        {
            "name": "start_demo_identity",
            "description": "Controlled Demo operator command to select father or mother; never infer identity from speech.",
            "parameters": {"type": "object", "additionalProperties": False, "required": ["identity_status"], "properties": {"identity_status": {"type": "string", "enum": ["father", "mother"]}}},
        },
        {
            "name": "stop_demo_identity",
            "description": "Clear the controlled Demo identity to canonical unknown.",
            "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
        },
        {
            "name": "get_demo_identity_status",
            "description": "Read process-local controlled Demo identity status without inferring identity.",
            "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
        },
    ]


def install_identity_tools(*, callback_socket: str) -> list[str]:
    """Register root-owned tools without modifying the nested Hermes checkout."""
    global _callback_socket
    if not callback_socket or not Path(callback_socket).is_absolute():
        raise ValueError("HERMES_DEMO_IDENTITY_CALLBACK_SOCKET must be an absolute Unix socket path")
    _callback_socket = callback_socket
    from tools.registry import registry

    for schema in identity_tool_schemas():
        action = schema["name"]
        registry.register(
            name=action,
            toolset=TOOLSET,
            schema=schema,
            handler=lambda args, _action=action, **_kwargs: _handle_identity_tool(_action, args),
            description=schema["description"],
            emoji="🪪",
            max_result_size_chars=600,
        )
    return [schema["name"] for schema in identity_tool_schemas()]


@contextmanager
def invocation_context(context: dict[str, str]) -> Iterator[None]:
    token = _context.set(dict(context))
    try:
        yield
    finally:
        _context.reset(token)


def invoke_registered_identity_tool(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Invoke the same socket-only handler used by the native tool registry."""
    if action not in {"start_demo_identity", "stop_demo_identity", "get_demo_identity_status"}:
        return {"status": "rejected", "error_code": "DEMO_IDENTITY_TOOL_INVALID_ACTION"}
    if not isinstance(args, dict):
        return {"status": "rejected", "error_code": "DEMO_IDENTITY_TOOL_INVALID_ARGUMENTS"}
    if action == "start_demo_identity":
        if args.get("identity_status") not in {"father", "mother"} or set(args) != {"identity_status"}:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_TOOL_INVALID_ARGUMENTS"}
    elif args:
        return {"status": "rejected", "error_code": "DEMO_IDENTITY_TOOL_INVALID_ARGUMENTS"}
    try:
        parsed = json.loads(_handle_identity_tool(action, args))
    except json.JSONDecodeError:
        return {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}
    return parsed if isinstance(parsed, dict) else {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}


def _handle_identity_tool(action: str, args: dict[str, Any]) -> str:
    context = _context.get()
    if context is None or _callback_socket is None:
        return json.dumps({"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_CONTEXT_UNAVAILABLE"}, ensure_ascii=False)
    payload: dict[str, Any] = {"action": action, "event_id": context.get("event_id", ""), "robot_id": context.get("robot_id", "")}
    if action == "start_demo_identity":
        payload["identity_status"] = args.get("identity_status")
    return json.dumps(invoke_demo_callback_socket(_callback_socket, payload), ensure_ascii=False, separators=(",", ":"))
