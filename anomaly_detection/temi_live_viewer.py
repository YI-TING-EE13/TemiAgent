"""Live Temi camera viewer for anomaly detection stream testing."""

from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Any

import av
import cv2
from aiohttp import WSMsgType, web


LOGGER = logging.getLogger("temi_live_viewer")
BOUNDARY = "temiframe"


@dataclass
class FrameStore:
    """In-memory holder for the most recent decoded camera frame."""

    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    latest_jpeg: bytes | None = None
    latest_timestamp_ms: int | None = None
    latest_received_at: float | None = None
    frame_count: int = 0
    websocket_count: int = 0
    decode_errors: int = 0

    async def update(self, timestamp_ms: int, image: Any, jpeg_quality: int) -> None:
        """Encode and publish one decoded OpenCV BGR frame."""
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if not ok:
            raise RuntimeError("OpenCV failed to encode frame as JPEG")

        async with self.condition:
            self.latest_jpeg = encoded.tobytes()
            self.latest_timestamp_ms = timestamp_ms
            self.latest_received_at = time.time()
            self.frame_count += 1
            self.condition.notify_all()

    async def snapshot(self) -> tuple[bytes | None, int | None, float | None, int]:
        """Return the latest JPEG and metadata."""
        async with self.condition:
            return self.latest_jpeg, self.latest_timestamp_ms, self.latest_received_at, self.frame_count


def find_free_port(start: int = 8000, end: int = 8999) -> int:
    """Return the first bindable TCP port in the requested range."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free TCP port found in {start}-{end}")


def decode_temiframe_message(codec: Any, message: bytes, rotate_180: bool) -> list[tuple[int, Any]]:
    """Decode one Temi timestamp-prefixed H.264 WebSocket message."""
    if len(message) < 8:
        return []

    timestamp_ms = struct.unpack(">q", message[:8])[0]
    decoded: list[tuple[int, Any]] = []
    for packet in codec.parse(message[8:]):
        for frame in codec.decode(packet):
            image = frame.to_ndarray(format="bgr24")
            if rotate_180:
                image = cv2.rotate(image, cv2.ROTATE_180)
            decoded.append((timestamp_ms, image))
    return decoded


def build_app(args: argparse.Namespace) -> web.Application:
    """Create the aiohttp app with browser and WebSocket endpoints."""
    store = FrameStore()
    app = web.Application()
    app["store"] = store
    app["args"] = args

    async def index(request: web.Request) -> web.StreamResponse:
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return await websocket_intake(request)

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Temi Live Viewer</title>
  <style>
    body {{ margin: 0; background: #101214; color: #eef1f4; font-family: system-ui, sans-serif; }}
    main {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }}
    header {{ padding: 12px 16px; background: #1b2026; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: 16px; font-weight: 650; }}
    code {{ color: #a5d6ff; }}
    .stage {{ display: grid; place-items: center; padding: 16px; }}
    img {{ width: min(100%, 1280px); max-height: calc(100vh - 88px); object-fit: contain; background: #050607; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Temi Live Viewer</h1>
      <span>Video input: <code>ws://HOST:{args.port}/</code> or <code>/ws</code></span>
      <span>Status: <code>/health</code></span>
    </header>
    <section class="stage">
      <img src="/stream.mjpg" alt="Waiting for Temi camera stream">
    </section>
  </main>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def websocket_intake(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=args.max_message_mb * 1024 * 1024)
        await ws.prepare(request)
        codec = av.CodecContext.create("h264", "r")
        store.websocket_count += 1
        LOGGER.info("Temi video WebSocket connected from %s", request.remote)

        try:
            async for msg in ws:
                if msg.type != WSMsgType.BINARY:
                    continue
                try:
                    for timestamp_ms, image in decode_temiframe_message(codec, msg.data, args.rotate_180):
                        await store.update(timestamp_ms, image, args.jpeg_quality)
                except av.error.InvalidDataError:
                    continue
                except Exception:
                    store.decode_errors += 1
                    LOGGER.exception("failed to decode Temi video message")
        finally:
            store.websocket_count = max(0, store.websocket_count - 1)
            LOGGER.info("Temi video WebSocket disconnected from %s", request.remote)
        return ws

    async def mjpeg_stream(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
        await response.prepare(request)
        last_count = -1

        while True:
            async with store.condition:
                await store.condition.wait_for(lambda: store.frame_count != last_count)
                jpeg = store.latest_jpeg
                last_count = store.frame_count

            if jpeg is None:
                await asyncio.sleep(0.1)
                continue

            header = (
                f"--{BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg)}\r\n\r\n"
            ).encode("ascii")
            try:
                await response.write(header + jpeg + b"\r\n")
            except (ConnectionResetError, asyncio.CancelledError):
                break
        return response

    async def snapshot(request: web.Request) -> web.Response:
        jpeg, _, _, _ = await store.snapshot()
        if jpeg is None:
            return web.Response(status=404, text="no frame received yet\n")
        return web.Response(body=jpeg, content_type="image/jpeg")

    async def health(request: web.Request) -> web.Response:
        jpeg, timestamp_ms, received_at, frame_count = await store.snapshot()
        age_ms = None if received_at is None else int((time.time() - received_at) * 1000)
        return web.json_response(
            {
                "ok": True,
                "has_frame": jpeg is not None,
                "frame_count": frame_count,
                "latest_timestamp_ms": timestamp_ms,
                "latest_frame_age_ms": age_ms,
                "websocket_count": store.websocket_count,
                "decode_errors": store.decode_errors,
            }
        )

    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_intake)
    app.router.add_get("/stream.mjpg", mjpeg_stream)
    app.router.add_get("/snapshot.jpg", snapshot)
    app.router.add_get("/health", health)
    return app


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Receive Temi H.264 WebSocket video and show it in a browser.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=0, help="HTTP/WebSocket port. Use 0 to auto-pick 8000-8999.")
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--max-message-mb", type=int, default=8)
    parser.add_argument("--no-rotate-180", action="store_false", dest="rotate_180")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    """Run the live viewer."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    if args.port == 0:
        args.port = find_free_port()
    if not 8000 <= args.port <= 8999:
        raise SystemExit("--port must be in the 8000-8999 range")

    app = build_app(args)
    LOGGER.info("open http://127.0.0.1:%s/ to view the stream", args.port)
    LOGGER.info("configure Temi video WebSocket to ws://HOST:%s/ or ws://HOST:%s/ws", args.port, args.port)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
