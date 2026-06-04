#!/usr/bin/env python3
"""Capture current decoded Temi camera frame(s) from the 8081 JPEG broadcast.

This helper is intentionally small and dependency-free so Discord/gateway or
manual Hermes workflows can ask for a low-frequency live visual snapshot without
pulling raw stream handling into HermesTemiBridge or Hermes skills.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import sys
import time
from typing import Any
from urllib.parse import urlparse


DEFAULT_SOURCE_URL = "ws://127.0.0.1:8081"
DEFAULT_SHARED_ROOT = "/TemiAgent/temi_shared"
DEFAULT_BRIDGE_ROOT = "/TemiAgent/temi_shared"


class SnapshotCaptureError(RuntimeError):
    """Raised when the live snapshot source cannot produce usable frames."""


class WebSocketConnection:
    """Minimal WebSocket client for receiving broadcast text/binary frames."""

    def __init__(self, url: str, timeout_seconds: float) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.sock: socket.socket | None = None
        self._buffer = b""

    def __enter__(self) -> "WebSocketConnection":
        self.sock = self._connect()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.sock is not None:
            with suppress_socket_errors():
                self.sock.close()
            self.sock = None

    def _connect(self) -> socket.socket:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"ws", "wss"}:
            raise SnapshotCaptureError(f"unsupported WebSocket scheme: {parsed.scheme}")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        raw_sock = socket.create_connection((host, port), timeout=self.timeout_seconds)
        raw_sock.settimeout(self.timeout_seconds)
        sock: socket.socket
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(raw_sock, server_hostname=host)
        else:
            sock = raw_sock

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._read_http_response(sock)
        status_line, headers = parse_http_upgrade_response(response)
        if " 101 " not in status_line:
            raise SnapshotCaptureError(f"WebSocket upgrade failed: {status_line}")
        expected_accept = websocket_accept_key(key)
        actual_accept = headers.get("sec-websocket-accept", "")
        if actual_accept != expected_accept:
            raise SnapshotCaptureError("WebSocket upgrade failed: invalid Sec-WebSocket-Accept")
        return sock

    def _read_http_response(self, sock: socket.socket) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while b"\r\n\r\n" not in b"".join(chunks):
            chunk = sock.recv(1024)
            if not chunk:
                raise SnapshotCaptureError("socket closed during WebSocket upgrade")
            chunks.append(chunk)
            total += len(chunk)
            if total > 16384:
                raise SnapshotCaptureError("WebSocket upgrade response too large")
        data = b"".join(chunks)
        header, self._buffer = data.split(b"\r\n\r\n", 1)
        return header + b"\r\n\r\n"

    def _read_exact(self, size: int) -> bytes:
        """Read bytes, preserving any payload buffered after the HTTP upgrade."""
        if self.sock is None:
            raise SnapshotCaptureError("WebSocket is not connected")
        chunks: list[bytes] = []
        if self._buffer:
            chunks.append(self._buffer[:size])
            self._buffer = self._buffer[size:]
        remaining = size - sum(len(chunk) for chunk in chunks)
        if remaining > 0:
            chunks.append(read_exact(self.sock, remaining))
        return b"".join(chunks)

    def receive_message(self) -> tuple[int, bytes] | None:
        """Receive one complete WebSocket message as ``(opcode, payload)``."""
        if self.sock is None:
            raise SnapshotCaptureError("WebSocket is not connected")
        fragments: list[bytes] = []
        message_opcode: int | None = None
        while True:
            frame = read_ws_frame_from_reader(self._read_exact)
            if frame is None:
                return None
            fin, opcode, payload = frame
            if opcode == 0x8:  # close
                return None
            if opcode == 0x9:  # ping; this read-only helper does not need to keep long sessions alive.
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode in {0x1, 0x2}:
                message_opcode = opcode
                fragments = [payload]
            elif opcode == 0x0 and message_opcode is not None:
                fragments.append(payload)
            else:
                continue
            if fin:
                return message_opcode, b"".join(fragments)


class suppress_socket_errors:
    """Context manager that ignores socket close errors."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return isinstance(exc, OSError)


def websocket_accept_key(key: str) -> str:
    """Return the expected Sec-WebSocket-Accept value for a client key."""
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + magic).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def parse_http_upgrade_response(response: bytes) -> tuple[str, dict[str, str]]:
    """Parse a WebSocket HTTP upgrade response."""
    header_bytes = response.split(b"\r\n\r\n", 1)[0]
    lines = header_bytes.decode("iso-8859-1").split("\r\n")
    status_line = lines[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return status_line, headers


def read_exact(sock: socket.socket, size: int) -> bytes:
    """Read exactly ``size`` bytes from a socket."""
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise SnapshotCaptureError("socket closed while reading WebSocket frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_ws_frame(sock: socket.socket) -> tuple[bool, int, bytes] | None:
    """Read one WebSocket frame from a connected socket."""
    return read_ws_frame_from_reader(lambda size: read_exact(sock, size))


def read_ws_frame_from_reader(read_fn: Any) -> tuple[bool, int, bytes] | None:
    """Read one WebSocket frame using a function that returns exact bytes."""
    header = read_fn(2)
    first, second = header[0], header[1]
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack(">H", read_fn(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", read_fn(8))[0]
    mask_key = read_fn(4) if masked else b""
    payload = read_fn(length) if length else b""
    if masked:
        payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    return fin, opcode, payload


def parse_broadcast_payload(payload: bytes) -> dict[str, Any]:
    """Parse the 8081 binary payload into timestamp, sequence, and JPEG bytes."""
    if len(payload) <= 16:
        raise SnapshotCaptureError("broadcast payload too short")
    timestamp_ms, sequence = struct.unpack(">qQ", payload[:16])
    jpeg = payload[16:]
    if not is_probable_jpeg(jpeg):
        raise SnapshotCaptureError("broadcast payload does not contain JPEG bytes")
    return {"timestamp_ms": timestamp_ms, "sequence": sequence, "jpeg": jpeg}


def is_probable_jpeg(data: bytes) -> bool:
    """Return True when bytes look like a JPEG image."""
    return len(data) >= 4 and data.startswith(b"\xff\xd8") and data.rstrip().endswith(b"\xff\xd9")


def now_ms() -> int:
    """Return Unix time in milliseconds."""
    return int(time.time() * 1000)


def build_request_id(prefix: str) -> str:
    """Create a filesystem-safe request id."""
    return f"{prefix}_{now_ms()}"


def capture_live_snapshots(args: argparse.Namespace) -> dict[str, Any]:
    """Capture one or more current frames from the decoded JPEG broadcast."""
    if args.count < 1:
        raise SnapshotCaptureError("--count must be >= 1")
    request_id = args.request_id or build_request_id(args.request_prefix)
    output_dir = Path(args.shared_root) / "live_snapshots" / args.robot_id / request_id
    output_dir.mkdir(parents=True, exist_ok=True)

    frames: list[dict[str, Any]] = []
    deadline = time.monotonic() + args.timeout_seconds
    with WebSocketConnection(args.source_url, args.timeout_seconds) as websocket:
        while len(frames) < args.count:
            if time.monotonic() > deadline:
                raise SnapshotCaptureError(f"timed out before capturing {args.count} frame(s)")
            message = websocket.receive_message()
            if message is None:
                raise SnapshotCaptureError("frame broadcast closed before a JPEG frame was received")
            opcode, payload = message
            if opcode != 0x2:
                continue
            parsed = parse_broadcast_payload(payload)
            frame_index = len(frames)
            frame_name = "current" if args.count == 1 else f"frame_{frame_index:03d}"
            filename = "frame_current.jpg" if args.count == 1 else f"frame_{frame_index:03d}.jpg"
            frame_path = output_dir / filename
            frame_path.write_bytes(parsed["jpeg"])
            bridge_path = f"{args.bridge_root.rstrip('/')}/live_snapshots/{args.robot_id}/{request_id}/{filename}"
            frames.append(
                {
                    "name": frame_name,
                    "ts_ms": parsed["timestamp_ms"],
                    "sequence": parsed["sequence"],
                    "path": bridge_path,
                    "local_path": frame_path.as_posix(),
                    "mime_type": "image/jpeg",
                }
            )

    result = {
        "schema_version": "1.0",
        "source_type": "live.snapshot",
        "status": "captured",
        "request_id": request_id,
        "robot_id": args.robot_id,
        "source_url": args.source_url,
        "created_at_ms": now_ms(),
        "sampling_policy": "current" if args.count == 1 else f"latest_{args.count}_frames",
        "frames": frames,
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["metadata_path"] = f"{args.bridge_root.rstrip('/')}/live_snapshots/{args.robot_id}/{request_id}/metadata.json"
    result["metadata_local_path"] = metadata_path.as_posix()
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Capture live Temi snapshot frame(s) from ws://<pc-ip>:8081.")
    parser.add_argument("--source-url", default=os.getenv("TEMI_FRAME_BROADCAST_URL", DEFAULT_SOURCE_URL))
    parser.add_argument("--robot-id", default=os.getenv("ROBOT_ID", "temi-01"))
    parser.add_argument("--request-id", help="Optional stable request id for the snapshot directory.")
    parser.add_argument("--request-prefix", default="snap_live")
    parser.add_argument("--count", type=int, default=1, help="Number of latest broadcast frames to save.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--shared-root", default=os.getenv("TEMI_SHARED_ROOT", DEFAULT_SHARED_ROOT))
    parser.add_argument("--bridge-root", default=os.getenv("TEMI_SHARED_BRIDGE_ROOT", DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def main() -> int:
    """CLI entrypoint."""
    args = build_parser().parse_args()
    try:
        result = capture_live_snapshots(args)
    except (OSError, TimeoutError, SnapshotCaptureError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
