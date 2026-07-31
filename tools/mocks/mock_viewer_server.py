#!/usr/bin/env python3
"""Lifecycle-managed viewer/LLM health test double for newcomer acceptance."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

HEALTH_STATUS = HTTPStatus.OK
NOTIFICATION_HEALTH: dict[str, object] = {}

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = json.dumps(
            {"ok": HEALTH_STATUS == HTTPStatus.OK, "test_double": "viewer", "source_connected": True,
             "llama_server_ready": True, **NOTIFICATION_HEALTH}
        ).encode("utf-8")
        self.send_response(HEALTH_STATUS)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the newcomer viewer test double.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--aux-port", type=int, required=True)
    parser.add_argument("--notification-mode", choices=("disabled", "demo_mock", "discord_webhook"), default="disabled")
    parser.add_argument("--discord-test-mode", choices=("enabled", "disabled"), default="disabled")
    parser.add_argument("--demo-notification-mock-enabled", choices=("enabled", "disabled"), default="disabled")
    parser.add_argument("--demo-notification-mock-receipt-enabled", choices=("enabled", "disabled"), default="disabled")
    parser.add_argument("--health-status", type=int, choices=(200, 500), default=200)
    args = parser.parse_args()
    global HEALTH_STATUS, NOTIFICATION_HEALTH
    HEALTH_STATUS = HTTPStatus(args.health_status)
    demo_mock_enabled = args.demo_notification_mock_enabled == "enabled"
    receipt_enabled = args.demo_notification_mock_receipt_enabled == "enabled"
    NOTIFICATION_HEALTH = {
        "notification_bridge_owned": True,
        "notification_mode": args.notification_mode,
        "components": {
            "viewer_core": {"status": "healthy" if args.health_status == 200 else "unhealthy"},
            "event_ingestion": {"status": "connected"},
            "frame_state": {"status": "receiving", "frame_count": 1},
            "real_discord": {
                "status": "skipped_by_viewer" if args.notification_mode == "discord_webhook" else "disabled",
                "enabled": args.notification_mode == "discord_webhook",
                "test_mode": args.discord_test_mode == "enabled",
            },
            "demo_notification_mock": {
                "status": "receipt_route_available" if demo_mock_enabled and receipt_enabled else "disabled",
                "enabled": demo_mock_enabled,
                "receipt_enabled": receipt_enabled,
            },
        },
    }
    primary = ThreadingHTTPServer((args.host, args.port), _Handler)
    auxiliary = ThreadingHTTPServer((args.host, args.aux_port), _Handler)
    worker = threading.Thread(target=auxiliary.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    worker.start()
    try:
        primary.serve_forever(poll_interval=0.2)
    finally:
        primary.server_close()
        auxiliary.shutdown()
        auxiliary.server_close()
        worker.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
