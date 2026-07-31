#!/usr/bin/env python3
"""Lifecycle-managed OpenAI model-list test double for newcomer acceptance.

It exposes only a deterministic health/model surface. It never loads a model,
uses a GPU, accepts inference, or contacts a production endpoint.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


def _handler(model_id: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/v1/models":
                self._send({"object": "list", "data": [{"id": model_id, "object": "model", "test_double": True}]})
            elif self.path == "/health":
                self._send({"ok": True, "test_double": "lmstudio", "model_id": model_id})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _send(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the newcomer LM Studio test double.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model-id", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), _handler(args.model_id))
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
