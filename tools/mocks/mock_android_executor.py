#!/usr/bin/env python3
"""MQTT-only Android test double for lifecycle-managed newcomer acceptance.

It consumes canonical ``cmd/request`` payloads, rejects unknown action shapes,
and returns canonical ``cmd/result`` payloads.  It never controls a real Temi
or makes a network connection beyond the configured loopback test broker.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any

import paho.mqtt.client as mqtt


ROBOT_ACTIONS = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}


class Executor:
    """Validate a bounded command surface and publish deterministic results."""

    def __init__(self, *, broker: str, port: int, robot_id: str, trace_path: Path) -> None:
        self.broker = broker
        self.port = port
        self.robot_id = robot_id
        self.trace_path = trace_path
        self.command_count = 0
        self.rejected_count = 0
        self.play_request: dict[str, Any] | None = None
        self.session_id = "newcomer_mock_session_001"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"newcomer-mock-android-{robot_id}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any) -> None:
        if int(reason_code) == 0:
            client.subscribe(f"temi/{self.robot_id}/cmd/request", qos=1)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            if payload.get("robot_id") != self.robot_id:
                raise ValueError("robot id mismatch")
            if payload.get("schema_version") == "1.1" and payload.get("message_type") == "video.command":
                self._handle_media(payload)
            else:
                self._handle_legacy(payload)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.rejected_count += 1
            self._trace({"kind": "rejected_request", "reason": str(exc), "test_double": True})

    def _handle_legacy(self, payload: dict[str, Any]) -> None:
        actions = payload.get("actions")
        if payload.get("schema_version") != "1.0" or not isinstance(actions, list) or not actions:
            raise ValueError("unsupported legacy command contract")
        action_types = [item.get("type") for item in actions if isinstance(item, dict)]
        if len(action_types) != len(actions) or any(action not in ROBOT_ACTIONS for action in action_types):
            raise ValueError("unknown robot action")
        self.command_count += 1
        self._trace({"kind": "command_request", "test_double": True, "command_id": payload.get("command_id"), "event_id": payload.get("event_id"), "actions": action_types})
        result = {
            "schema_version": "1.0",
            "command_id": payload["command_id"],
            "event_id": payload["event_id"],
            "robot_id": self.robot_id,
            "status": "success",
            "results": [{"action_id": action["action_id"], "status": "success"} for action in actions],
            "finished_at_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "test_double": True,
        }
        self._publish_result(result)

    def _handle_media(self, request: dict[str, Any]) -> None:
        action = request.get("action")
        if action not in {"play_video", "pause_video", "resume_video", "stop_video"}:
            raise ValueError("unknown media action")
        self.command_count += 1
        self._trace({"kind": "media_request", "test_double": True, "command_id": request.get("command_id"), "action": action, "video_id": request.get("video_id")})
        if action == "play_video":
            self.play_request = request
            self._publish_result(self._media_result(request, "accepted", None))
            self._publish_result(self._media_result(request, "started", "playing"))
            return
        states = {"pause_video": "paused", "resume_video": "playing", "stop_video": "cancelled"}
        self._publish_result(self._media_result(request, "succeeded", states[action]))
        if action == "stop_video" and self.play_request is not None:
            self._publish_result(
                self._media_result(
                    self.play_request,
                    "cancelled",
                    "cancelled",
                    cancelled_by=request["command_id"],
                    cancel_reason="remote_stop",
                )
            )
            self.play_request = None

    def _media_result(self, request: dict[str, Any], status: str, playback_state: str | None, *, cancelled_by: str | None = None, cancel_reason: str | None = None) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "message_type": "video.command_result",
            "command_id": request["command_id"],
            "request_id": request["request_id"],
            "event_id": request["event_id"],
            "robot_id": self.robot_id,
            "command_action": request["action"],
            "video_id": request["video_id"],
            "status": status,
            "terminal": status not in {"accepted", "started"},
            "playback_session_id": self.session_id,
            "target_playback_session_id": request["target_playback_session_id"],
            "active_playback_session_id": None,
            "playback_state": playback_state,
            "cancelled_by_command_id": cancelled_by,
            "cancel_reason": cancel_reason,
            "actor": "remote_command",
            "result_delivery": "original",
            "error_code": None,
            "error_message": None,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def _publish_result(self, result: dict[str, Any]) -> None:
        self.client.publish(f"temi/{self.robot_id}/cmd/result", json.dumps(result, ensure_ascii=False), qos=1)
        self._trace({"kind": "command_result", "test_double": True, "command_id": result["command_id"], "status": result["status"], "action": result.get("command_action")})

    def _trace(self, payload: dict[str, Any]) -> None:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), **payload}, ensure_ascii=False) + "\n")


def _health_handler(executor: Executor) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = json.dumps({"ok": True, "test_double": "android", "command_count": executor.command_count, "rejected_count": executor.rejected_count}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the newcomer MQTT Android test double.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--health-port", type=int, required=True)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--mqtt-port", type=int, required=True)
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--trace-path", type=Path, required=True)
    args = parser.parse_args()
    executor = Executor(broker=args.broker, port=args.mqtt_port, robot_id=args.robot_id, trace_path=args.trace_path)
    health = ThreadingHTTPServer((args.host, args.health_port), _health_handler(executor))
    worker = threading.Thread(target=health.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    worker.start()
    try:
        executor.client.connect(args.broker, args.mqtt_port, keepalive=15)
        executor.client.loop_forever()
    finally:
        executor.client.disconnect()
        health.shutdown()
        health.server_close()
        worker.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
