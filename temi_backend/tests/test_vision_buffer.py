"""Unit tests for timestamp-aligned frame buffering."""

from __future__ import annotations

import numpy as np

from temi_backend.vision_server import VisionBuffer


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
