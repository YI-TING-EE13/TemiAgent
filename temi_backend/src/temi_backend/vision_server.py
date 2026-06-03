"""WebSocket H.264 receiver, rolling vision buffer, and decoded-frame broadcaster."""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import struct
import threading
from typing import Any

import av
import cv2
import numpy as np
import websockets

LOGGER = logging.getLogger(__name__)


class VisionBuffer:
    """Thread-safe rolling cache of timestamped OpenCV frames."""

    def __init__(self, max_seconds: int = 10, fps: int = 30) -> None:
        """Create a bounded buffer sized by expected retention time and FPS."""
        self.buffer: collections.deque[tuple[int, np.ndarray]] = collections.deque(maxlen=max_seconds * fps)
        self.lock = threading.Lock()

    def push(self, timestamp_ms: int, frame: np.ndarray) -> None:
        """Append one decoded frame using Temi's hardware timestamp."""
        with self.lock:
            self.buffer.append((timestamp_ms, frame))

    def get_keyframes(self, target_ms: int) -> list[dict[str, Any]]:
        """Return frames nearest to T-1000 ms, T-500 ms, and T."""
        offsets = (-1000, -500, 0)
        results: list[dict[str, Any]] = []

        with self.lock:
            if not self.buffer:
                LOGGER.warning("VisionBuffer is empty.")
                return []

            for offset in offsets:
                target_time = target_ms + offset
                actual_time, frame = min(self.buffer, key=lambda item: abs(item[0] - target_time))
                results.append(
                    {
                        "target_t": target_time,
                        "actual_t": actual_time,
                        "frame": frame.copy(),
                    }
                )
        return results

    def latest(self) -> dict[str, Any] | None:
        """Return a copy of the most recent frame and timestamp, if available."""
        with self.lock:
            if not self.buffer:
                return None
            timestamp_ms, frame = self.buffer[-1]
            return {"actual_t": timestamp_ms, "frame": frame.copy()}


class JpegFrameBroadcaster:
    """Broadcast decoded frames to downstream WebSocket subscribers as JPEG messages."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8081,
        jpeg_quality: int = 80,
        queue_size: int = 2,
    ) -> None:
        """Configure a non-blocking decoded-frame broadcast endpoint.

        Each outbound binary WebSocket message is:
        - 8 bytes: signed big-endian frame timestamp in milliseconds
        - 8 bytes: unsigned big-endian sequence number
        - remaining bytes: JPEG image
        """
        self.host = host
        self.port = port
        self.jpeg_quality = max(1, min(100, jpeg_quality))
        self.queue_size = max(1, queue_size)
        self.clients: set[asyncio.Queue[bytes]] = set()
        self.sequence = 0

    def encode_frame(self, timestamp_ms: int, frame: np.ndarray) -> bytes:
        """Encode one frame into the broadcast binary payload format."""
        self.sequence += 1
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if not ok:
            raise ValueError("OpenCV failed to encode frame as JPEG.")
        header = struct.pack(">qQ", int(timestamp_ms), self.sequence)
        return header + buffer.tobytes()

    def publish(self, timestamp_ms: int, frame: np.ndarray) -> None:
        """Queue one decoded frame for all subscribers without blocking ingest."""
        if not self.clients:
            return
        try:
            payload = self.encode_frame(timestamp_ms, frame)
        except ValueError:
            LOGGER.exception("failed to encode decoded frame for broadcast")
            return

        for queue in list(self.clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                LOGGER.debug("dropping frame for a slow broadcast subscriber")

    async def stream_handler(self, websocket: Any) -> None:
        """Send decoded JPEG frames to one downstream subscriber."""
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=self.queue_size)
        self.clients.add(queue)
        LOGGER.info("Frame broadcast subscriber connected.")
        try:
            await websocket.send(
                json.dumps(
                    {
                        "type": "temi.frame_stream.v1",
                        "encoding": "jpeg",
                        "binary_header": "int64_be timestamp_ms + uint64_be sequence",
                    }
                )
            )
            while True:
                await websocket.send(await queue.get())
        except websockets.exceptions.ConnectionClosed:
            LOGGER.info("Frame broadcast subscriber disconnected.")
        finally:
            self.clients.discard(queue)

    async def start(self) -> Any:
        """Start the decoded-frame broadcast WebSocket server."""
        server = await websockets.serve(self.stream_handler, self.host, self.port)
        LOGGER.info("Frame broadcast server listening on ws://%s:%s", self.host, self.port)
        return server


class VisionServer:
    """Receive Temi WebSocket video frames and decode them into a VisionBuffer."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        buffer: VisionBuffer | None = None,
        rotate_180: bool = True,
        frame_broadcaster: JpegFrameBroadcaster | None = None,
    ) -> None:
        """Configure the WebSocket listener.

        Args:
            host: Bind address for incoming robot streams.
            port: Bind port for incoming robot streams.
            buffer: Optional buffer instance, mainly used by tests.
            rotate_180: Rotate decoded frames to compensate for Temi camera orientation.
            frame_broadcaster: Optional decoded-frame output endpoint for downstream
                consumers such as abnormal behavior detectors.
        """
        self.host = host
        self.port = port
        self.buffer = buffer or VisionBuffer()
        self.rotate_180 = rotate_180
        self.frame_broadcaster = frame_broadcaster

    def decode_message(self, codec: Any, message: bytes) -> int:
        """Decode one timestamp-prefixed H.264 WebSocket message.

        Args:
            codec: PyAV H.264 codec context.
            message: Binary WebSocket message with an 8-byte big-endian timestamp
                followed by H.264 bytes.

        Returns:
            Number of decoded frames written to the rolling buffer.
        """
        if len(message) < 8:
            return 0

        timestamp_ms = struct.unpack(">q", message[:8])[0]
        packets = codec.parse(message[8:])
        decoded_count = 0

        for packet in packets:
            for frame in codec.decode(packet):
                image = frame.to_ndarray(format="bgr24")
                if self.rotate_180:
                    image = cv2.rotate(image, cv2.ROTATE_180)
                self.buffer.push(timestamp_ms, image)
                if self.frame_broadcaster:
                    self.frame_broadcaster.publish(timestamp_ms, image)
                decoded_count += 1
        return decoded_count

    async def stream_handler(self, websocket: Any) -> None:
        """Handle a single robot WebSocket connection until it closes."""
        LOGGER.info("Vision stream connected.")
        codec = av.CodecContext.create("h264", "r")

        try:
            async for message in websocket:
                if not isinstance(message, bytes):
                    continue
                try:
                    self.decode_message(codec, message)
                except av.error.InvalidDataError:
                    # H.264 streams often need the next keyframe before decoding is possible.
                    continue
                except Exception as exc:
                    LOGGER.error("Failed to decode video frame: %s", exc)
        except websockets.exceptions.ConnectionClosed:
            LOGGER.info("Vision stream disconnected.")

    async def start(self) -> None:
        """Start the ingest WebSocket server and optional broadcast server forever."""
        vision_server = await websockets.serve(self.stream_handler, self.host, self.port)
        broadcast_server = await self.frame_broadcaster.start() if self.frame_broadcaster else None
        try:
            LOGGER.info("Vision ingest server listening on ws://%s:%s", self.host, self.port)
            await asyncio.Future()
        finally:
            vision_server.close()
            await vision_server.wait_closed()
            if broadcast_server:
                broadcast_server.close()
                await broadcast_server.wait_closed()

    def run_in_background(self) -> threading.Thread:
        """Run the WebSocket server in a daemon thread and return the thread."""

        def run_loop() -> None:
            """Create and run an event loop inside the background thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())

        thread = threading.Thread(target=run_loop, daemon=True, name="temi-vision-server")
        thread.start()
        return thread
