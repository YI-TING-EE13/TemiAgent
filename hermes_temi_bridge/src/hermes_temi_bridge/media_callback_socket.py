"""Bounded local Unix-socket transport for resident Hermes media callbacks."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import socketserver
import threading
from typing import Any, Protocol


MAX_CALLBACK_BYTES = 8192


class MediaCallback(Protocol):
    """Interface implemented by the Bridge-owned media callback adapter."""

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class MediaCallbackSocketError(RuntimeError):
    """Raised when an operator-provided callback socket is unsafe to use."""


class _CallbackRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_CALLBACK_BYTES + 1)
        if len(raw) > MAX_CALLBACK_BYTES:
            self._respond({"status": "rejected", "error_code": "MEDIA_CALLBACK_PAYLOAD_TOO_LARGE"})
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond({"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_JSON"})
            return
        if not isinstance(payload, dict):
            self._respond({"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_PAYLOAD"})
            return
        callback: MediaCallback = self.server.callback  # type: ignore[attr-defined]
        self._respond(callback.invoke(payload))

    def _respond(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.wfile.write(encoded + b"\n")


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


class MediaCallbackSocketServer:
    """Bridge-owned socket lifecycle; it never opens a network TCP port."""

    def __init__(self, socket_path: str | Path, callback: MediaCallback) -> None:
        self.path = Path(socket_path)
        self.callback = callback
        self._server: _UnixServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Bind exactly one new Unix socket after checking its filesystem type."""
        if not self.path.is_absolute():
            raise MediaCallbackSocketError("media_callback_socket_must_be_absolute")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or self.path.is_socket():
            raise MediaCallbackSocketError("media_callback_socket_path_already_exists")
        server = _UnixServer(self.path.as_posix(), _CallbackRequestHandler)
        server.callback = self.callback  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True, name="temi-media-callback")
        self._thread.start()

    def stop(self) -> None:
        """Stop only this server and remove its own verified socket path."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self.path.exists() and self.path.is_socket():
            self.path.unlink()


def invoke_media_callback_socket(
    socket_path: str | Path,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Call the local Bridge callback without giving Hermes MQTT access."""
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_CALLBACK_BYTES:
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_PAYLOAD_TOO_LARGE"}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout_seconds)
            client.connect(Path(socket_path).as_posix())
            client.sendall(encoded + b"\n")
            response = _recv_line(client)
    except OSError:
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_UNAVAILABLE"}
    try:
        decoded = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_RESPONSE"}
    if not isinstance(decoded, dict):
        return {"status": "rejected", "error_code": "MEDIA_CALLBACK_INVALID_RESPONSE"}
    return decoded


def _recv_line(client: socket.socket) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_CALLBACK_BYTES:
        chunk = client.recv(min(1024, MAX_CALLBACK_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\n" in chunk:
            break
    return b"".join(chunks).split(b"\n", 1)[0]
