#!/usr/bin/env python3
"""Validate and publish one Hermes Temi action JSON as a command request.

This is for manual/gateway use cases where Hermes produced the Bridge action
object in chat, but no ASR event route invoked HermesTemiBridge. The script
reuses the Bridge validator and command builder, then optionally publishes the
canonical command request to ``temi/{robot_id}/cmd/request``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))

from hermes_temi_bridge.action_validator import ActionValidationError, validate_action_output  # noqa: E402
from hermes_temi_bridge.command_dispatcher import build_command_request  # noqa: E402

DEFAULT_COGNITIVE_STATE = {
    "intent": "manual_robot_action",
    "home_esi_level": "Normal",
    "risk_reason": "Manual gateway dispatch for a robot action; no care risk was indicated.",
    "next_step": "dispatch_robot_action",
}


def _read_input(args: argparse.Namespace) -> str:
    if args.json_text:
        return args.json_text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --json, --file, or pipe Hermes action JSON on stdin.")


def _extract_first_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object from text that may include chat separators."""
    stripped = text.strip()
    start = stripped.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(stripped[start:])
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _with_manual_defaults(payload: dict[str, Any], strict_cognitive_state: bool) -> dict[str, Any]:
    """Fill the care cognition field for old manual TTS outputs when allowed."""
    normalized = dict(payload)
    if strict_cognitive_state or "cognitive_state" in normalized:
        return normalized
    normalized["cognitive_state"] = dict(DEFAULT_COGNITIVE_STATE)
    return normalized


def _publish_with_mosquitto(host: str, port: int, topic: str, payload: dict[str, Any]) -> None:
    message = json.dumps(payload, ensure_ascii=False)
    subprocess.run(
        ["mosquitto_pub", "-h", host, "-p", str(port), "-t", topic, "-m", message],
        check=True,
    )


def _host_part(endpoint: str) -> str:
    host, _, _port = endpoint.rpartition(":")
    return host.strip("[]")


def _local_ipv4_addresses() -> set[str]:
    addresses = {"127.0.0.1", "0.0.0.0", "::1"}
    try:
        completed = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return addresses
    for line in completed.stdout.splitlines():
        parts = line.split()
        if "inet" in parts:
            value = parts[parts.index("inet") + 1]
            addresses.add(value.split("/", 1)[0])
    return addresses


def _mqtt_connection_diagnostic(port: int) -> dict[str, Any]:
    """Best-effort check for a robot-side MQTT client on the local broker."""
    try:
        completed = subprocess.run(
            ["ss", "-tnH", "state", "established"],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"checked": False, "reason": str(exc)}

    local_addresses = _local_ipv4_addresses()
    broker_port = str(port)
    broker_connections: list[dict[str, str]] = []
    robot_like_clients: list[str] = []

    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_endpoint = parts[-2]
        peer_endpoint = parts[-1]
        local_port = local_endpoint.rpartition(":")[2]
        peer_port = peer_endpoint.rpartition(":")[2]
        if broker_port not in {local_port, peer_port}:
            continue
        client_endpoint = peer_endpoint if local_port == broker_port else local_endpoint
        client_host = _host_part(client_endpoint)
        broker_connections.append({"client": client_endpoint, "line": line})
        if client_host and client_host not in local_addresses:
            robot_like_clients.append(client_endpoint)

    return {
        "checked": True,
        "broker_port": port,
        "connection_count": len(broker_connections),
        "robot_like_clients": sorted(set(robot_like_clients)),
        "local_addresses": sorted(local_addresses),
    }


def dispatch_action(args: argparse.Namespace) -> dict[str, Any]:
    """Validate one manual Hermes plan and optionally publish its command request."""

    raw_text = _read_input(args)
    payload = _extract_first_json_object(raw_text)
    payload = _with_manual_defaults(payload, args.strict_cognitive_state)

    event_id = args.event_id or str(payload.get("event_id") or "")
    robot_id = args.robot_id or str(payload.get("robot_id") or "")
    if not event_id:
        raise ValueError("missing event_id; pass --event-id or include it in JSON")
    if not robot_id:
        raise ValueError("missing robot_id; pass --robot-id or include it in JSON")

    validated = validate_action_output(
        payload,
        expected_event_id=event_id,
        expected_robot_id=robot_id,
        max_actions=args.max_actions,
    )
    command = build_command_request(validated, command_id=args.command_id)
    if args.source:
        command["source"] = args.source

    topic = args.topic or f"temi/{robot_id}/cmd/request"
    result: dict[str, Any] = {
        "status": "validated",
        "topic": topic,
        "command": command,
        "filled_cognitive_state": "cognitive_state" not in _extract_first_json_object(raw_text),
    }
    if args.publish:
        _publish_with_mosquitto(args.broker, args.port, topic, command)
        result["status"] = "published"
        result["broker"] = args.broker
        result["port"] = args.port
        if not args.skip_mqtt_connection_check:
            diagnostic = _mqtt_connection_diagnostic(args.port)
            result["mqtt_connection_check"] = diagnostic
            if diagnostic.get("checked") and not diagnostic.get("robot_like_clients"):
                result["status"] = "published_no_robot_connection_detected"
                result["warning"] = (
                    "MQTT publish succeeded, but no non-local robot/app MQTT client is connected "
                    "to the broker. Do not claim Temi audibly spoke until the Android app is online."
                )
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit input, validation, and optional publication CLI."""

    parser = argparse.ArgumentParser(
        description="Validate Hermes Temi action JSON and optionally publish a command request."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--json", dest="json_text", help="Hermes action JSON string.")
    source.add_argument("--file", help="File containing Hermes action JSON.")
    parser.add_argument("--event-id", help="Expected event_id override.")
    parser.add_argument("--robot-id", help="Expected robot_id override.")
    parser.add_argument("--command-id", help="Optional command_id override.")
    parser.add_argument("--source", default="manual_hermes_action_dispatcher")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", "1883")))
    parser.add_argument("--topic", help="Override publish topic. Defaults to temi/{robot_id}/cmd/request.")
    parser.add_argument("--max-actions", type=int, default=5)
    parser.add_argument("--publish", action="store_true", help="Publish to MQTT after validation.")
    parser.add_argument(
        "--skip-mqtt-connection-check",
        action="store_true",
        help="Do not inspect local MQTT TCP connections after publishing.",
    )
    parser.add_argument(
        "--strict-cognitive-state",
        action="store_true",
        help="Reject payloads missing cognitive_state instead of filling a Normal manual default.",
    )
    return parser


def main() -> int:
    """Run the manual dispatcher and return a concise machine-readable result."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        result = dispatch_action(args)
    except (ValueError, ActionValidationError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
