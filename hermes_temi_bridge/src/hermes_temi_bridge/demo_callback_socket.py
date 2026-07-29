"""Bounded Unix-only transport for root resident Demo callbacks."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import socketserver
import threading
from typing import Any, Protocol


MAX_DEMO_CALLBACK_BYTES = 8192


class DemoCallback(Protocol):
    """Bridge-side callback surface exposed to a root-owned resident tool."""

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class DemoCallbackSocketError(RuntimeError):
    """Raised when a callback socket path is not safe to own."""


class _DemoCallbackRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_DEMO_CALLBACK_BYTES + 1)
        if len(raw) > MAX_DEMO_CALLBACK_BYTES:
            self._respond({"status": "rejected", "error_code": "DEMO_CALLBACK_PAYLOAD_TOO_LARGE"})
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond({"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_JSON"})
            return
        if not isinstance(payload, dict):
            self._respond({"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_PAYLOAD"})
            return
        callback: DemoCallback = self.server.callback  # type: ignore[attr-defined]
        self._respond(callback.invoke(payload))

    def _respond(self, payload: dict[str, Any]) -> None:
        self.wfile.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


class DemoCallbackSocketServer:
    """Own exactly one private Unix socket; never bind a TCP port."""

    def __init__(self, socket_path: str | Path, callback: DemoCallback) -> None:
        self.path = Path(socket_path)
        self.callback = callback
        self._server: _UnixServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.path.is_absolute():
            raise DemoCallbackSocketError("demo_callback_socket_must_be_absolute")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or self.path.is_socket():
            raise DemoCallbackSocketError("demo_callback_socket_path_already_exists")
        server = _UnixServer(self.path.as_posix(), _DemoCallbackRequestHandler)
        server.callback = self.callback  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True, name="temi-demo-callback")
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self.path.exists() and self.path.is_socket():
            self.path.unlink()


def invoke_demo_callback_socket(
    socket_path: str | Path,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Call a Bridge callback with a bounded local JSON message."""
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_DEMO_CALLBACK_BYTES:
        return {"status": "rejected", "error_code": "DEMO_CALLBACK_PAYLOAD_TOO_LARGE"}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout_seconds)
            client.connect(Path(socket_path).as_posix())
            client.sendall(encoded + b"\n")
            response = _recv_line(client)
    except OSError:
        return {"status": "rejected", "error_code": "DEMO_CALLBACK_UNAVAILABLE"}
    try:
        decoded = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}
    return decoded if isinstance(decoded, dict) else {"status": "rejected", "error_code": "DEMO_CALLBACK_INVALID_RESPONSE"}


def _recv_line(client: socket.socket) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_DEMO_CALLBACK_BYTES:
        chunk = client.recv(min(1024, MAX_DEMO_CALLBACK_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\n" in chunk:
            break
    return b"".join(chunks).split(b"\n", 1)[0]
