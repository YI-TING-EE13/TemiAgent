#!/usr/bin/env python3
"""Lifecycle-managed viewer/LLM health test double for newcomer acceptance."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = json.dumps({"ok": True, "test_double": "viewer", "source_connected": True, "llama_server_ready": True}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
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
    args = parser.parse_args()
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
