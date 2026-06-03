"""Unit tests for timestamp-aligned frame buffering."""

from __future__ import annotations

import asyncio
import struct

import cv2
import numpy as np

from temi_backend.vision_server import JpegFrameBroadcaster, VisionBuffer


def test_get_keyframes_returns_nearest_asymmetric_frames() -> None:
    buffer = VisionBuffer(max_seconds=1, fps=10)
    for timestamp in (0, 500, 1000, 1500, 2000):
        buffer.push(timestamp, np.full((2, 2, 3), timestamp // 500, dtype=np.uint8))

    frames = buffer.get_keyframes(2000)

    assert [frame["target_t"] for frame in frames] == [1000, 1500, 2000]
    assert [frame["actual_t"] for frame in frames] == [1000, 1500, 2000]


def test_get_keyframes_returns_copies_not_original_frame_references() -> None:
    buffer = VisionBuffer(max_seconds=1, fps=10)
    original = np.ones((2, 2, 3), dtype=np.uint8)
    buffer.push(1000, original)

    frame = buffer.get_keyframes(1000)[0]["frame"]
    frame[0, 0, 0] = 99

    assert original[0, 0, 0] == 1


def test_empty_buffer_returns_empty_list() -> None:
    buffer = VisionBuffer()

    assert buffer.get_keyframes(1000) == []


def test_latest_returns_most_recent_frame_copy() -> None:
    buffer = VisionBuffer(max_seconds=1, fps=10)
    first = np.zeros((2, 2, 3), dtype=np.uint8)
    second = np.ones((2, 2, 3), dtype=np.uint8)
    buffer.push(1000, first)
    buffer.push(2000, second)

    latest = buffer.latest()

    assert latest is not None
    assert latest["actual_t"] == 2000
    latest["frame"][0, 0, 0] = 99
    assert second[0, 0, 0] == 1


def test_jpeg_frame_broadcaster_payload_contains_timestamp_sequence_and_jpeg() -> None:
    broadcaster = JpegFrameBroadcaster(jpeg_quality=90)
    frame = np.full((4, 4, 3), 128, dtype=np.uint8)

    payload = broadcaster.encode_frame(1234, frame)

    timestamp_ms, sequence = struct.unpack(">qQ", payload[:16])
    assert timestamp_ms == 1234
    assert sequence == 1
    decoded = cv2.imdecode(np.frombuffer(payload[16:], dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == frame.shape


def test_jpeg_frame_broadcaster_drops_oldest_frame_for_slow_subscriber() -> None:
    broadcaster = JpegFrameBroadcaster(queue_size=1)
    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
    broadcaster.clients.add(queue)

    broadcaster.publish(1000, np.zeros((2, 2, 3), dtype=np.uint8))
    broadcaster.publish(2000, np.ones((2, 2, 3), dtype=np.uint8))

    assert queue.qsize() == 1
    payload = queue.get_nowait()
    timestamp_ms, sequence = struct.unpack(">qQ", payload[:16])
    assert timestamp_ms == 2000
    assert sequence == 2
