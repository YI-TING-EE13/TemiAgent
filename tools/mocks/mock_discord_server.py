#!/usr/bin/env python3
"""Local Discord-webhook test double with explicit deterministic responses."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse


def _append(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _handler(trace_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/health":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._respond(HTTPStatus.OK, {"ok": True, "test_double": "discord"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/webhook":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            query = parse_qs(parsed.query)
            delay = float(query.get("delay", ["0"])[0])
            if delay:
                time.sleep(min(delay, 20.0))
            status = int(query.get("status", ["204"])[0])
            _append(trace_path, {"timestamp": datetime.now(timezone.utc).isoformat(), "test_double": True, "status": status, "content_length": int(self.headers.get("Content-Length", "0"))})
            self.send_response(status)
            self.send_header("X-Newcomer-Mock", "discord")
            if status == 429:
                self.send_header("Retry-After", "0")
            self.end_headers()

        def _respond(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local newcomer Discord webhook test double.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--trace-path", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), _handler(args.trace_path))
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
