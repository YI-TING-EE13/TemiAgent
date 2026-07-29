"""Temi action viewer using 8081 decoded frames and a llama.cpp vision model."""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import logging
import os
import shutil
import socket
import struct
import subprocess
import textwrap
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests
from aiohttp import ClientSession, WSMsgType, web


LOGGER = logging.getLogger("temi_action_viewer")
BOUNDARY = "temiaction"
DEFAULT_GGUF_MODEL_PATH = (
    "/TemiAgent/.lmstudio-data/models/lmstudio-community/"
    "gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.Q8_0.gguf"
)
DEFAULT_MMPROJ_PATH = (
    "/TemiAgent/.lmstudio-data/models/lmstudio-community/"
    "gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.BF16-mmproj.gguf"
)
DEFAULT_LLAMA_SERVER_PATH = "/TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server"
TARGET_ACTIONS = [
    "blows nose or sneezes",
    "cleans",
    "does no action",
    "eats",
    "falls down",
    "fights",
    "lies on the floor",
    "sits down",
    "stands up",
    "walks",
    "watches tv",
]
ALERT_ACTIONS = {"falls down", "fights", "lies on the floor"}
PRE_ALERT_SPEAK_TEXT = {
    "falls down": "我偵測到可能有人跌倒了，已將過程發送給 Discord。",
    "lies on the floor": "我偵測到有人可能躺在地上，已將過程發送給 Discord。",
    "fights": "我偵測到可能有肢體衝突，請注意安全，已將過程發送給 Discord。",
}
DEFAULT_DISCORD_ENV_PATH = "/TemiAgent/anomaly_detection/.env"
DISCORD_WEBHOOK_ENV_VAR = "DISCORD_WEBHOOK_URL"
DISCORD_USERNAME = "HABD-Agent"
DISCORD_DELIVERY_TEST_MESSAGE = (
    "[TEST] TemiAgent abnormal-event Discord delivery verification.\n"
    "No real care incident occurred."
)


class DiscordDeliveryError(RuntimeError):
    """A safe, machine-readable Discord delivery failure."""

    def __init__(
        self,
        failure_code: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        detail: str | None = None,
    ) -> None:
        self.failure_code = failure_code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.detail = detail
        parts = [failure_code]
        if status_code is not None:
            parts.append(f"HTTP {status_code}")
        if retry_after_seconds is not None:
            parts.append(f"retry_after_seconds={retry_after_seconds:g}")
        if detail:
            parts.append(detail)
        super().__init__("; ".join(parts))


@dataclass(frozen=True)
class BufferedFrame:
    """One decoded JPEG frame from the 8081 broadcaster."""

    timestamp_ms: int
    sequence: int
    received_at: float
    jpeg: bytes
    image: np.ndarray


@dataclass(frozen=True)
class InferenceTiming:
    """Timing breakdown for one multimodal model request."""

    pose_ms: float
    payload_ms: float
    request_ms: float
    response_read_ms: float
    json_parse_ms: float
    extract_ms: float
    total_ms: float


@dataclass(frozen=True)
class ParsedAction:
    """Structured action result parsed from the model response."""

    action_name: str
    reason: str
    raw_response: str

    def to_overlay_text(self) -> str:
        """Format the parsed action for the viewer overlay."""
        if self.reason:
            return f"Action: {self.action_name}\nEvidence/Reason: {self.reason}"
        return f"Action: {self.action_name}"

    def to_dict(self) -> dict[str, str]:
        """Return the parsed action fields for health checks and events."""
        return {
            "action_name": self.action_name,
            "reason": self.reason,
            "raw_response": self.raw_response,
        }


@dataclass
class ActionState:
    """Shared state for frame display and action prediction."""

    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    frames: deque[BufferedFrame] = field(default_factory=deque)
    history_queue: deque[BufferedFrame] = field(default_factory=deque)
    current_second_frames: list[BufferedFrame] = field(default_factory=list)
    current_second_key: int | None = None
    latest_frame: BufferedFrame | None = None
    latest_prediction: str = "waiting for prediction"
    latest_action: ParsedAction | None = None
    prediction_age: float | None = None
    prediction_count: int = 0
    total_inference_ms: float = 0.0
    latest_inference_ms: float | None = None
    latest_timing: InferenceTiming | None = None
    total_timing_ms: dict[str, float] = field(default_factory=dict)
    inference_in_flight: bool = False
    last_inferred_signature: tuple[int, ...] | None = None
    frame_count: int = 0
    source_connected: bool = False
    source_error: str | None = None
    inference_error: str | None = None
    latest_abnormal_event: dict[str, Any] | None = None
    abnormal_publish_count: int = 0
    abnormal_publish_error: str | None = None
    backend_status: dict[str, Any] = field(default_factory=dict)
    pose_status: dict[str, Any] = field(default_factory=dict)

    async def add_frame(
        self,
        frame: BufferedFrame,
        retention_seconds: float,
        history_seconds: int,
        current_second_samples: int,
    ) -> None:
        """Store one frame and notify browser streams."""
        cutoff = frame.received_at - retention_seconds
        async with self.condition:
            self.frames.append(frame)
            while self.frames and self.frames[0].received_at < cutoff:
                self.frames.popleft()
            self._add_sampler_frame_locked(frame, history_seconds, current_second_samples)
            self.latest_frame = frame
            self.frame_count += 1
            self.condition.notify_all()

    def _add_sampler_frame_locked(
        self,
        frame: BufferedFrame,
        history_seconds: int,
        current_second_samples: int,
    ) -> None:
        """Update the 3-history + current-second sampler state."""
        second_key = int(frame.received_at)
        if self.current_second_key is None:
            self.current_second_key = second_key
        elif second_key != self.current_second_key:
            self._promote_current_second_locked(history_seconds, current_second_samples)
            self.current_second_key = second_key
            self.current_second_frames = []

        self.current_second_frames.append(frame)

    def _promote_current_second_locked(self, history_seconds: int, current_second_samples: int) -> None:
        """Store the reference representative frame from the completed second as history."""
        if not self.current_second_frames:
            return
        sampled = sample_uniform_frames(self.current_second_frames, min(current_second_samples, len(self.current_second_frames)))
        representative = sampled[1] if len(sampled) > 1 else sampled[0]
        self.history_queue.append(representative)
        while len(self.history_queue) > history_seconds:
            self.history_queue.popleft()

    def _ready_batch_locked(self, history_seconds: int, current_second_samples: int) -> list[BufferedFrame]:
        """Return a ready 8-frame batch ordered as history then current second."""
        if len(self.history_queue) < history_seconds:
            return []
        if len(self.current_second_frames) < current_second_samples:
            return []
        return list(self.history_queue)[-history_seconds:] + sample_uniform_frames(
            self.current_second_frames,
            current_second_samples,
        )

    async def prepare_inference_batch(
        self,
        history_seconds: int,
        current_second_samples: int,
    ) -> list[BufferedFrame]:
        """Reserve a new inference batch if one is ready and not already running."""
        async with self.condition:
            if self.inference_in_flight:
                return []
            frames = self._ready_batch_locked(history_seconds, current_second_samples)
            if not frames:
                return []
            signature = tuple(frame.sequence for frame in frames)
            if signature == self.last_inferred_signature:
                return []
            self.inference_in_flight = True
            self.last_inferred_signature = signature
            return frames

    async def finish_inference(self) -> None:
        """Mark the current inference request complete and wake the scheduler."""
        async with self.condition:
            self.inference_in_flight = False
            self.condition.notify_all()

    async def set_source_status(self, connected: bool, error: str | None = None) -> None:
        """Update frame-source connection state."""
        async with self.condition:
            self.source_connected = connected
            self.source_error = error
            self.condition.notify_all()

    async def set_backend_status(self, status: dict[str, Any]) -> None:
        """Update inference backend status for health checks."""
        async with self.condition:
            self.backend_status = status
            self.condition.notify_all()

    async def set_pose_status(self, status: dict[str, Any]) -> None:
        """Update pose preprocessing status for health checks."""
        async with self.condition:
            self.pose_status = status
            self.condition.notify_all()

    async def set_prediction(
        self,
        prediction: str | ParsedAction,
        error: str | None = None,
        timing: InferenceTiming | None = None,
    ) -> None:
        """Update the current action label."""
        async with self.condition:
            if isinstance(prediction, ParsedAction):
                self.latest_action = prediction
                self.latest_prediction = prediction.to_overlay_text().strip() or "unknown action"
            else:
                self.latest_action = None
                self.latest_prediction = prediction.strip() or "unknown action"
            self.prediction_age = time.time()
            if timing is not None:
                self.prediction_count += 1
                self.latest_inference_ms = timing.total_ms
                self.total_inference_ms += timing.total_ms
                self.latest_timing = timing
                for key, value in timing.__dict__.items():
                    self.total_timing_ms[key] = self.total_timing_ms.get(key, 0.0) + value
            self.inference_error = error
            self.condition.notify_all()

    async def set_abnormal_publish_status(
        self,
        event: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        """Record the latest abnormal event publishing status."""
        async with self.condition:
            if event is not None:
                self.latest_abnormal_event = event
                self.abnormal_publish_count += 1
            self.abnormal_publish_error = error
            self.condition.notify_all()

    async def snapshot(self, history_seconds: int = 3, current_second_samples: int = 5) -> dict[str, Any]:
        """Return a shallow state snapshot."""
        async with self.condition:
            return {
                "latest_frame": self.latest_frame,
                "frames": list(self.frames),
                "latest_prediction": self.latest_prediction,
                "latest_action": None if self.latest_action is None else self.latest_action.to_dict(),
                "prediction_age": self.prediction_age,
                "prediction_count": self.prediction_count,
                "average_inference_ms": (
                    None if self.prediction_count == 0 else self.total_inference_ms / self.prediction_count
                ),
                "latest_inference_ms": self.latest_inference_ms,
                "latest_timing_ms": None if self.latest_timing is None else dict(self.latest_timing.__dict__),
                "average_timing_ms": (
                    None
                    if self.prediction_count == 0
                    else {key: value / self.prediction_count for key, value in self.total_timing_ms.items()}
                ),
                "history_frames": len(self.history_queue),
                "current_second_frames": len(self.current_second_frames),
                "sampled_current_second_frames": min(len(self.current_second_frames), current_second_samples),
                "ready_for_inference": bool(
                    self._ready_batch_locked(history_seconds, current_second_samples)
                    and not self.inference_in_flight
                ),
                "inference_in_flight": self.inference_in_flight,
                "frame_count": self.frame_count,
                "source_connected": self.source_connected,
                "source_error": self.source_error,
                "inference_error": self.inference_error,
                "latest_abnormal_event": self.latest_abnormal_event,
                "abnormal_publish_count": self.abnormal_publish_count,
                "abnormal_publish_error": self.abnormal_publish_error,
                "backend_status": dict(self.backend_status),
                "pose_status": dict(self.pose_status),
            }


def find_free_port(start: int = 8010, end: int = 8999) -> int:
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


def parse_broadcast_payload(payload: bytes) -> tuple[int, int, bytes]:
    """Parse 8081 payload: timestamp, sequence, JPEG bytes."""
    if len(payload) <= 16:
        raise ValueError("frame payload too short")
    timestamp_ms, sequence = struct.unpack(">qQ", payload[:16])
    return timestamp_ms, sequence, payload[16:]


def decode_jpeg(jpeg: bytes) -> np.ndarray:
    """Decode JPEG bytes into an OpenCV BGR image."""
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("failed to decode JPEG frame")
    return image


def encode_jpeg(image: np.ndarray, jpeg_quality: int) -> bytes:
    """Encode an OpenCV BGR image as JPEG."""
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise RuntimeError("OpenCV failed to encode JPEG")
    return encoded.tobytes()


def sample_uniform_frames(frames: list[BufferedFrame], count: int) -> list[BufferedFrame]:
    """Return count frames spread uniformly across a chronological list."""
    if count <= 0 or not frames:
        return []
    if len(frames) <= count:
        return list(frames)
    if count == 1:
        return [frames[len(frames) // 2]]
    indexes = [round(i * (len(frames) - 1) / (count - 1)) for i in range(count)]
    return [frames[index] for index in indexes]


def resize_long_side(image: np.ndarray, long_side: int) -> np.ndarray:
    """Resize an image while preserving aspect ratio."""
    if long_side <= 0:
        return image
    h, w = image.shape[:2]
    current_long_side = max(h, w)
    if current_long_side <= long_side:
        return image
    scale = long_side / current_long_side
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def resolve_pose_model_path(pose_model: str, root: str = "/TemiAgent/anomaly_detection") -> str | None:
    """Resolve the pose model path using the documented search order."""
    candidates: list[Path]
    requested = Path(pose_model)
    if requested.is_absolute():
        candidates = [requested]
    else:
        candidates = [
            Path(root) / "models" / pose_model,
            Path.cwd() / pose_model,
        ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


class PosePreprocessor:
    """Optional YOLO pose skeleton renderer for model input frames."""

    def __init__(self, mode: str, pose_model: str, device: str) -> None:
        self.mode = mode
        self.pose_model_request = pose_model
        self.device = device
        self.pose_model_path: str | None = None
        self.warning: str | None = None
        self.enabled = False
        self._model: Any | None = None

    def initialize(self) -> None:
        """Load YOLO pose when available or required."""
        if self.mode == "off":
            self.warning = "pose preprocessing disabled"
            return

        self.pose_model_path = resolve_pose_model_path(self.pose_model_request)
        if self.pose_model_path is None:
            self.warning = f"pose model not found: {self.pose_model_request}"
            if self.mode == "on":
                raise RuntimeError(self.warning)
            return

        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except Exception as exc:
            self.warning = f"ultralytics import failed: {exc}"
            if self.mode == "on":
                raise RuntimeError(self.warning) from exc
            return

        self._model = YOLO(self.pose_model_path)
        self.enabled = True
        self.warning = None

    def status(self) -> dict[str, Any]:
        """Return health status for the pose preprocessor."""
        return {
            "pose_mode": self.mode,
            "pose_enabled": self.enabled,
            "pose_model_path": self.pose_model_path,
            "pose_device": self.device,
            "pose_warning": self.warning,
        }

    def render(self, frame: BufferedFrame) -> np.ndarray:
        """Return the frame image with pose skeleton drawn when enabled."""
        if not self.enabled or self._model is None:
            return frame.image
        results = self._model.predict(
            source=frame.image,
            imgsz=640,
            conf=0.25,
            device=self.device,
            verbose=False,
        )
        return results[0].plot(boxes=False, labels=False)


def calculate_fps(frames: list[BufferedFrame], now: float, window_seconds: float = 3.0) -> float:
    """Calculate input FPS over a recent time window."""
    cutoff = now - window_seconds
    recent = [frame for frame in frames if frame.received_at >= cutoff]
    if len(recent) < 2:
        return 0.0
    duration = max(0.001, recent[-1].received_at - recent[0].received_at)
    return (len(recent) - 1) / duration


def overlay_prediction(
    frame: BufferedFrame,
    prediction: str,
    inference_error: str | None,
    jpeg_quality: int,
    average_inference_ms: float | None,
    latest_timing_ms: dict[str, float] | None,
    fps: float,
) -> bytes:
    """Draw the latest prediction in the top-left corner and return JPEG bytes."""
    image = frame.image.copy()
    h, w = image.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    inference_label = "-" if average_inference_ms is None else f"{average_inference_ms / 1000:.1f}s"
    title = f"Action | avg {inference_label} | {fps:.1f} fps"
    prediction_text = prediction or "waiting for prediction"
    if inference_error:
        prediction_text = f"{prediction_text} ({inference_error[:80]})"
    lines = [title, *textwrap.wrap(prediction_text, width=34)]
    if latest_timing_ms:
        lines.append(
            "last "
            f"payload {latest_timing_ms['payload_ms'] / 1000:.2f}s | "
            f"http {latest_timing_ms['request_ms'] / 1000:.2f}s | "
            f"parse {(latest_timing_ms['json_parse_ms'] + latest_timing_ms['extract_ms']) / 1000:.2f}s"
        )
    lines = lines[:5]

    font_scale = max(0.55, min(0.9, w / 1500))
    thickness = 2
    line_height = int(28 * font_scale) + 10
    box_w = min(w - 24, max(320, int(w * 0.38)))
    box_h = 18 + line_height * len(lines)

    overlay = image.copy()
    cv2.rectangle(overlay, (12, 12), (12 + box_w, 12 + box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.62, image, 0.38, 0, image)
    cv2.rectangle(image, (12, 12), (12 + box_w, 12 + box_h), (100, 210, 255), 2)

    y = 12 + line_height
    for idx, line in enumerate(lines):
        color = (130, 220, 255) if idx == 0 else (255, 255, 255)
        cv2.putText(image, line, (26, y), font, font_scale, color, thickness, cv2.LINE_AA)
        y += line_height

    cv2.putText(
        image,
        f"seq {frame.sequence}",
        (26, min(h - 18, 22 + box_h)),
        font,
        max(0.42, font_scale * 0.72),
        (210, 220, 230),
        1,
        cv2.LINE_AA,
    )
    return encode_jpeg(image, jpeg_quality)


def build_llamacpp_payload(
    model: str,
    frames: list[BufferedFrame],
    frame_jpegs: list[bytes],
    max_tokens: int,
    history_seconds: int,
    current_second_samples: int,
) -> dict[str, Any]:
    """Build an OpenAI-compatible multimodal chat completion payload."""
    target_actions = ", ".join(TARGET_ACTIONS)
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are an expert action recognition assistant.\n"
                "The images are video frames in chronological order.\n"
                f"The first {history_seconds} frames summarize the previous {history_seconds} seconds. "
                f"The last {current_second_samples} frames are from the current second.\n\n"
                "Analyze the sequence of video frames and identify the action taking place.\n"
                f"The target action categories to detect are: {target_actions}.\n\n"
                "Respond in the exact following format and nothing else:\n"
                "Action: <one target action category, or No person visible>\n"
                "Evidence/Reason: <brief visual evidence>\n"
            ),
        }
    ]
    for idx, (frame, jpeg) in enumerate(zip(frames, frame_jpegs, strict=True), start=1):
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        content.append({"type": "text", "text": f"Frame {idx}: sequence={frame.sequence}"})
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict human action classifier. "
                    "Return only two lines: Action:... and Evidence/Reason:... "
                    "Your response must begin with Action:. "
                    "Do not reason aloud. Do not include markdown."
                ),
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "top_k": 1,
        "top_p": 1,
        "max_tokens": max_tokens,
        "stream": False,
    }


def build_inference_jpegs(
    frames: list[BufferedFrame],
    pose_preprocessor: PosePreprocessor,
    jpeg_quality: int,
    long_side: int,
) -> list[bytes]:
    """Apply optional pose skeleton rendering and encode model input JPEGs."""
    jpegs: list[bytes] = []
    for frame in frames:
        image = pose_preprocessor.render(frame)
        image = resize_long_side(image, long_side)
        jpegs.append(encode_jpeg(image, jpeg_quality))
    return jpegs


async def call_llamacpp(
    session: ClientSession,
    api_base: str,
    model: str,
    frames: list[BufferedFrame],
    pose_preprocessor: PosePreprocessor,
    max_tokens: int,
    history_seconds: int,
    current_second_samples: int,
    inference_jpeg_quality: int,
    inference_long_side: int,
) -> tuple[ParsedAction | str, InferenceTiming]:
    """Call llama.cpp's OpenAI-compatible chat completions endpoint."""
    url = api_base.rstrip("/") + "/chat/completions"
    total_start = time.perf_counter()

    pose_start = time.perf_counter()
    frame_jpegs = build_inference_jpegs(frames, pose_preprocessor, inference_jpeg_quality, inference_long_side)
    pose_ms = (time.perf_counter() - pose_start) * 1000

    payload_start = time.perf_counter()
    payload = build_llamacpp_payload(
        model,
        frames,
        frame_jpegs,
        max_tokens,
        history_seconds,
        current_second_samples,
    )
    payload_ms = (time.perf_counter() - payload_start) * 1000

    request_start = time.perf_counter()
    async with session.post(url, json=payload, timeout=90) as response:
        request_ms = (time.perf_counter() - request_start) * 1000
        read_start = time.perf_counter()
        text = await response.text()
        response_read_ms = (time.perf_counter() - read_start) * 1000
        if response.status >= 400:
            raise RuntimeError(f"llama.cpp HTTP {response.status}: {text[:240]}")
        parse_start = time.perf_counter()
        data = json.loads(text)
        json_parse_ms = (time.perf_counter() - parse_start) * 1000
    extract_start = time.perf_counter()
    choice = data["choices"][0]
    content = str(choice["message"].get("content") or "").strip()
    if content:
        prediction = parse_action_response(content)
    elif choice.get("finish_reason") == "length":
        prediction = "Output truncated"
    else:
        prediction = "No action output"
    extract_ms = (time.perf_counter() - extract_start) * 1000
    total_ms = (time.perf_counter() - total_start) * 1000
    timing = InferenceTiming(
        pose_ms=pose_ms,
        payload_ms=payload_ms,
        request_ms=request_ms,
        response_read_ms=response_read_ms,
        json_parse_ms=json_parse_ms,
        extract_ms=extract_ms,
        total_ms=total_ms,
    )
    return prediction, timing


@dataclass
class LlamaCppBackend:
    """Manage a dedicated llama.cpp server or an existing llama.cpp endpoint."""

    args: argparse.Namespace
    process: asyncio.subprocess.Process | None = None
    ready: bool = False
    error: str | None = None

    @property
    def api_base(self) -> str:
        """Return the OpenAI-compatible API base URL."""
        if self.args.llama_api_base_url:
            return self.args.llama_api_base_url.rstrip("/")
        return f"http://{self.args.llama_server_host}:{self.args.llama_server_port}/v1"

    @property
    def health_url(self) -> str:
        """Return the llama-server health URL."""
        if self.args.llama_api_base_url:
            return self.args.llama_api_base_url.rstrip().removesuffix("/v1") + "/health"
        return f"http://{self.args.llama_server_host}:{self.args.llama_server_port}/health"

    def status(self) -> dict[str, Any]:
        """Return backend health status."""
        return {
            "inference_backend": "llama.cpp",
            "llama_server_url": self.api_base,
            "llama_server_ready": self.ready,
            "llama_server_error": self.error,
            "llama_server_path": self.args.llama_server,
            "gguf_model_path": self.args.gguf_model_path,
            "mmproj_path": self.args.mmproj_path,
        }

    async def start(self) -> None:
        """Start or validate the llama.cpp server."""
        self.ready = False
        self.error = None
        if self.args.llama_api_base_url:
            await self._wait_until_ready()
            return

        executable = self._resolve_llama_server()
        if executable is None:
            self.error = f"llama-server not found: {self.args.llama_server}"
            return
        if not Path(self.args.gguf_model_path).exists():
            self.error = f"GGUF model not found: {self.args.gguf_model_path}"
            return
        if not Path(self.args.mmproj_path).exists():
            self.error = f"mmproj not found: {self.args.mmproj_path}"
            return
        if await self._health_ready_once():
            self.ready = True
            self.error = None
            return

        command = [
            executable,
            "-m",
            self.args.gguf_model_path,
            "--mmproj",
            self.args.mmproj_path,
            "-c",
            str(self.args.llama_ctx_size),
            "-t",
            str(self.args.llama_threads),
            "-ngl",
            self.args.llama_gpu_layers,
            "--host",
            self.args.llama_server_host,
            "--port",
            str(self.args.llama_server_port),
            "--jinja",
            "--no-webui",
            "--cache-prompt",
            "--temp",
            "0",
            "--top-k",
            "1",
            "--top-p",
            "1",
            "--verbosity",
            "1",
        ]
        LOGGER.info("starting llama.cpp server: %s", " ".join(command))
        env = None
        if self.args.llama_cuda_visible_devices:
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = self.args.llama_cuda_visible_devices
            LOGGER.info(
                "starting llama.cpp server with CUDA_VISIBLE_DEVICES=%s",
                self.args.llama_cuda_visible_devices,
            )
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        await self._wait_until_ready()

    def _resolve_llama_server(self) -> str | None:
        """Resolve llama-server from explicit path or PATH."""
        requested = self.args.llama_server
        if requested:
            path = Path(requested)
            if path.exists() and os.access(path, os.X_OK):
                return str(path)
        return shutil.which("llama-server")

    async def _wait_until_ready(self) -> None:
        """Poll the backend health endpoint."""
        deadline = time.time() + self.args.llama_startup_timeout
        async with ClientSession() as session:
            while time.time() < deadline:
                if self.process is not None and self.process.returncode is not None:
                    self.error = f"llama-server exited with code {self.process.returncode}"
                    return
                try:
                    async with session.get(self.health_url, timeout=2) as response:
                        if response.status < 500:
                            self.ready = True
                            self.error = None
                            return
                except Exception as exc:
                    self.error = str(exc)
                await asyncio.sleep(0.5)
        self.error = f"llama-server not ready after {self.args.llama_startup_timeout:.1f}s"

    async def _health_ready_once(self) -> bool:
        """Return whether an existing llama-server is already ready."""
        try:
            async with ClientSession() as session:
                async with session.get(self.health_url, timeout=1) as response:
                    return response.status < 500
        except Exception:
            return False

    async def stop(self) -> None:
        """Stop a managed llama.cpp server."""
        if self.process is None:
            return
        self.process.terminate()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.process.wait(), timeout=5)
        if self.process.returncode is None:
            self.process.kill()
            await self.process.wait()


def parse_action_response(content: str) -> ParsedAction:
    """Parse the model's Action/Evidence response into structured fields."""
    action_name = ""
    reason = ""
    lowered = content.lower()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        key, sep, value = line.partition(":")
        if not sep:
            continue
        normalized_key = key.strip().lower()
        if normalized_key in {"action_name", "action"} and not action_name:
            action_name = _clean_field_value(value)
        elif normalized_key in {"reason", "evidence/reason", "evidence", "evidence_reason"} and not reason:
            reason = _clean_field_value(value)
    if not action_name:
        action_name = _clean_field_value(_extract_field_after_marker(content, "Action:"))
    if not action_name:
        action_name = _clean_field_value(_extract_field_after_marker(content, "action_name:"))
    if not reason:
        reason = _clean_field_value(_extract_field_after_marker(content, "Evidence/Reason:"))
    if not reason:
        reason = _clean_field_value(_extract_field_after_marker(content, "reason:"))
    if not action_name and "no person" in lowered:
        action_name = "No person visible"
    if not action_name:
        action_name = _clean_field_value(content) or "unknown action"
    return ParsedAction(action_name=action_name, reason=reason, raw_response=content)


def normalize_action_response(content: str) -> str:
    """Normalize model output for legacy callers and overlay tests."""
    return parse_action_response(content).to_overlay_text()


def normalize_action_name(action_name: str) -> str:
    """Normalize action labels for allowlist comparisons."""
    normalized = action_name.strip().lower().replace("_", " ")
    if normalized.startswith("person "):
        normalized = normalized[len("person ") :]
    return " ".join(normalized.split())


def should_publish_abnormal_event(action: ParsedAction) -> bool:
    """Return whether the parsed action should produce an abnormal event."""
    return normalize_action_name(action.action_name) in ALERT_ACTIONS


def abnormal_cooldown_elapsed(last_published_at: float, now: float, cooldown_seconds: float) -> bool:
    """Return whether a new global abnormal event may be published."""
    if last_published_at <= 0.0:
        return True
    return now - last_published_at >= max(0.0, cooldown_seconds)


def build_abnormal_event(
    action: ParsedAction,
    frame_paths: list[str],
    event_id: str | None = None,
    robot_id: str = "temi-01",
    timestamp_ms: int | None = None,
    source: str = "temi_action_viewer",
) -> dict[str, Any]:
    """Build the minimal abnormal event payload from parsed model output."""
    now_ms = int(time.time() * 1000)
    return {
        "schema_version": "1.0",
        "event_id": event_id or f"evt_abnormal_{now_ms}",
        "robot_id": robot_id,
        "type": "perception.abnormal",
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else now_ms,
        "observation": {
            "action_name": action.action_name,
            "reason": action.reason,
        },
        "evidence": {
            "frame_paths": frame_paths,
        },
        "context": {
            "source": source,
        },
    }


def save_abnormal_evidence_frames(
    frames: list[BufferedFrame],
    shared_root: str,
    robot_id: str,
    event_id: str,
) -> list[str]:
    """Persist original JPEG frames for an abnormal event and return their paths."""
    event_dir = Path(shared_root) / "abnormal_events" / robot_id / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, frame in enumerate(frames):
        path = event_dir / f"frame_{index:03d}.jpg"
        path.write_bytes(frame.jpeg)
        paths.append(path.as_posix())
    return paths


def publish_abnormal_event_mqtt(
    event: dict[str, Any],
    broker: str,
    port: int,
    topic: str,
) -> None:
    """Publish one abnormal event with mosquitto_pub."""
    message = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    subprocess.run(
        ["mosquitto_pub", "-h", broker, "-p", str(port), "-t", topic, "-m", message],
        check=True,
        capture_output=True,
        text=True,
    )


def build_pre_alert_speak_command(
    action: ParsedAction,
    event_id: str,
    robot_id: str,
    language: str = "zh-TW",
    created_at_ms: int | None = None,
) -> dict[str, Any]:
    """Build a canonical speak command for immediate abnormal pre-alerts."""
    now_ms = created_at_ms if created_at_ms is not None else int(time.time() * 1000)
    normalized_action = normalize_action_name(action.action_name)
    text = PRE_ALERT_SPEAK_TEXT.get(
        normalized_action,
        "我偵測到可能有異常狀況，已將過程發送給 Discord。",
    )
    return {
        "schema_version": "1.0",
        "command_id": f"cmd_prealert_{event_id}_{now_ms}",
        "event_id": event_id,
        "robot_id": robot_id,
        "source": "temi_action_viewer_pre_alert",
        "created_at_ms": now_ms,
        "actions": [
            {
                "action_id": "pre_alert_speak",
                "type": "speak",
                "text": text,
                "language": language,
            }
        ],
    }


def publish_pre_alert_speak(
    command: dict[str, Any],
    broker: str,
    port: int,
    robot_id: str,
) -> str:
    """Publish one canonical pre-alert speak command and return the topic."""
    topic = f"temi/{robot_id}/cmd/request"
    message = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
    subprocess.run(
        ["mosquitto_pub", "-h", broker, "-p", str(port), "-t", topic, "-m", message],
        check=True,
        capture_output=True,
        text=True,
    )
    return topic


def maybe_publish_pre_alert_speak(
    action: ParsedAction,
    event_id: str,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    """Publish an immediate speak warning before sending the event to Hermes."""
    if getattr(args, "pre_alert_speak", "disabled") == "disabled":
        return None
    command = build_pre_alert_speak_command(
        action,
        event_id,
        args.robot_id,
        getattr(args, "pre_alert_language", "zh-TW"),
    )
    topic = publish_pre_alert_speak(command, args.mqtt_broker, args.mqtt_port, args.robot_id)
    return {"topic": topic, "payload": command}


def format_publish_error(exc: Exception) -> str:
    """Return a concise publish error without echoing the full MQTT payload."""
    if isinstance(exc, subprocess.CalledProcessError):
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            return f"{exc.cmd[0]} exited with {exc.returncode}: {detail}"
        return f"{exc.cmd[0]} exited with {exc.returncode}"
    return str(exc)


def _discord_failure_code_for_http_status(status_code: int) -> str:
    """Map a Discord webhook HTTP status to a stable, non-secret failure code."""
    return {
        401: "DISCORD_UNAUTHORIZED",
        403: "DISCORD_FORBIDDEN",
        404: "DISCORD_WEBHOOK_NOT_FOUND",
        429: "DISCORD_RATE_LIMITED",
    }.get(status_code, "DISCORD_BAD_RESPONSE")


def _discord_retry_after_seconds(response: requests.Response) -> float | None:
    """Return a non-negative Retry-After value when Discord provides one."""
    raw_value = str(getattr(response, "headers", {}).get("Retry-After", "")).strip()
    if not raw_value:
        return None
    try:
        value = float(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None


def notify_discord_webhook(
    message: str,
    file_paths: list[str],
    env_path: str,
    max_files: int,
) -> dict[str, Any]:
    """Send an abnormal event notification to Discord using a webhook from .env."""
    webhook_url = load_env_value(env_path, DISCORD_WEBHOOK_ENV_VAR)
    if not webhook_url:
        raise DiscordDeliveryError("DISCORD_WEBHOOK_UNSET")
    if not message.strip():
        raise DiscordDeliveryError("DISCORD_BAD_RESPONSE", detail="empty message")
    paths = [Path(path) for path in file_paths[: max(0, max_files)]]
    for path in paths:
        if not path.is_file():
            raise DiscordDeliveryError("DISCORD_BAD_RESPONSE", detail="evidence file unavailable")

    payload = {"username": DISCORD_USERNAME, "content": message.strip()}
    try:
        if paths:
            with contextlib.ExitStack() as stack:
                files = {
                    f"files[{index}]": (path.name, stack.enter_context(path.open("rb")))
                    for index, path in enumerate(paths)
                }
                response = requests.post(
                    webhook_url,
                    data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                    files=files,
                    timeout=60,
                )
        else:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
    except requests.Timeout as exc:
        raise DiscordDeliveryError("DISCORD_TIMEOUT") from exc
    except requests.ConnectionError as exc:
        raise DiscordDeliveryError("DISCORD_CONNECTION_FAILED") from exc
    except requests.RequestException as exc:
        raise DiscordDeliveryError("DISCORD_CONNECTION_FAILED") from exc
    if not 200 <= response.status_code < 300:
        raise DiscordDeliveryError(
            _discord_failure_code_for_http_status(response.status_code),
            status_code=response.status_code,
            retry_after_seconds=_discord_retry_after_seconds(response),
        )
    return {
        "failure_code": "DISCORD_DELIVERED",
        "status_code": response.status_code,
        "file_count": len(paths),
    }


def load_env_value(env_path: str, key: str) -> str:
    """Read one KEY=value from the process environment or a simple .env file."""
    value = os.getenv(key)
    if value:
        return value
    path = Path(env_path)
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        if name.strip() == key:
            return raw_value.strip().strip('"').strip("'")
    return ""


def notification_health(args: argparse.Namespace) -> dict[str, bool]:
    """Return safe direct-webhook readiness booleans without disclosing the webhook."""
    return {
        "abnormal_publish_enabled": getattr(args, "abnormal_publish", "disabled") == "enabled",
        "discord_notify_enabled": getattr(args, "discord_notify", "disabled") == "enabled",
        "discord_webhook_configured": bool(
            load_env_value(getattr(args, "discord_env_path", DEFAULT_DISCORD_ENV_PATH), DISCORD_WEBHOOK_ENV_VAR)
        ),
    }


def run_discord_delivery_test(args: argparse.Namespace) -> dict[str, Any]:
    """Send one clearly marked test using the production Discord sender only."""
    if getattr(args, "discord_notify", "disabled") != "enabled":
        return {"failure_code": "DISCORD_DISABLED", "file_count": 0}
    return notify_discord_webhook(
        DISCORD_DELIVERY_TEST_MESSAGE,
        [],
        getattr(args, "discord_env_path", DEFAULT_DISCORD_ENV_PATH),
        0,
    )


def build_discord_abnormal_message(event: dict[str, Any], topic: str) -> str:
    """Build a compact Discord message for one abnormal perception event."""
    observation = event.get("observation") if isinstance(event.get("observation"), dict) else {}
    action_name = str(observation.get("action_name") or "")
    reason = str(observation.get("reason") or "")
    return textwrap.dedent(
        f"""\
        Temi abnormal event detected
        robot_id: {event.get("robot_id", "")}
        event_id: {event.get("event_id", "")}
        mqtt_topic: {topic}
        action: {action_name}
        reason: {reason}
        """
    ).strip()


def maybe_notify_discord(event: dict[str, Any], topic: str, args: argparse.Namespace) -> dict[str, Any] | None:
    """Send a best-effort Discord notification for an abnormal event."""
    if getattr(args, "discord_notify", "disabled") == "disabled":
        return None
    frame_paths = []
    evidence = event.get("evidence")
    if isinstance(evidence, dict):
        raw_paths = evidence.get("frame_paths")
        if isinstance(raw_paths, list):
            frame_paths = [path for path in raw_paths if isinstance(path, str)]
    message = build_discord_abnormal_message(event, topic)
    return notify_discord_webhook(
        message,
        frame_paths,
        getattr(args, "discord_env_path", DEFAULT_DISCORD_ENV_PATH),
        getattr(args, "discord_max_files", 8),
    )


def maybe_publish_abnormal_event(
    action: ParsedAction,
    frames: list[BufferedFrame],
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    """Persist and publish an abnormal event if publishing is enabled."""
    if args.abnormal_publish == "disabled":
        return None
    if not should_publish_abnormal_event(action):
        return None
    event_id = f"evt_abnormal_{int(time.time() * 1000)}"
    frame_paths = save_abnormal_evidence_frames(frames, args.shared_root, args.robot_id, event_id)
    event = build_abnormal_event(
        action,
        frame_paths,
        event_id=event_id,
        robot_id=args.robot_id,
        source=args.abnormal_source,
    )
    topic = f"temi/{args.robot_id}/perception/abnormal"
    published_event: dict[str, Any] = {"topic": topic, "payload": event}
    try:
        pre_alert = maybe_publish_pre_alert_speak(action, event_id, args)
        if pre_alert is not None:
            published_event["pre_alert_speak"] = pre_alert
    except Exception as exc:
        pre_alert_error = format_publish_error(exc)
        LOGGER.warning("failed to publish pre-alert speak command: %s", pre_alert_error)
        published_event["pre_alert_speak_error"] = pre_alert_error
    try:
        publish_abnormal_event_mqtt(event, args.mqtt_broker, args.mqtt_port, topic)
        published_event["mqtt"] = {"status": "ok"}
    except Exception as exc:
        mqtt_error = format_publish_error(exc)
        LOGGER.warning("failed to publish abnormal event to MQTT: %s", mqtt_error)
        published_event["mqtt_error"] = mqtt_error
    try:
        discord = maybe_notify_discord(event, topic, args)
        if discord is not None:
            published_event["discord"] = discord
    except Exception as exc:
        LOGGER.exception("failed to send abnormal event Discord notification")
        published_event["discord_error"] = str(exc)
    return published_event


def _extract_field_after_marker(content: str, marker: str) -> str:
    """Extract a single-line value after a marker appearing anywhere in text."""
    index = content.lower().find(marker.lower())
    if index < 0:
        return ""
    value = content[index + len(marker) :].strip()
    if not value:
        return ""
    return value.splitlines()[0].strip()


def _clean_field_value(value: str) -> str:
    """Reject copied placeholders and return a displayable field value."""
    cleaned = value.strip().strip("`").strip()
    lowered = cleaned.lower()
    if not cleaned:
        return ""
    if "<" in cleaned or ">" in cleaned:
        return ""
    if "short english" in lowered or "action label" in lowered or "max 20 words" in lowered:
        return ""
    return cleaned


async def frame_source_loop(state: ActionState, args: argparse.Namespace) -> None:
    """Continuously receive decoded JPEG frames from the 8081 broadcaster."""
    while True:
        try:
            async with ClientSession() as session:
                async with session.ws_connect(args.source_url, max_msg_size=args.max_message_mb * 1024 * 1024) as ws:
                    await state.set_source_status(True, None)
                    LOGGER.info("connected to frame source %s", args.source_url)
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            LOGGER.info("frame source hello: %s", msg.data)
                            continue
                        if msg.type != WSMsgType.BINARY:
                            continue
                        try:
                            timestamp_ms, sequence, jpeg = parse_broadcast_payload(msg.data)
                            image = decode_jpeg(jpeg)
                            frame = BufferedFrame(
                                timestamp_ms=timestamp_ms,
                                sequence=sequence,
                                received_at=time.time(),
                                jpeg=jpeg,
                                image=image,
                            )
                            await state.add_frame(
                                frame,
                                args.retention_seconds,
                                args.history_seconds,
                                args.current_second_samples,
                            )
                        except Exception as exc:
                            LOGGER.warning("failed to process broadcast frame: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("frame source disconnected: %s", exc)
            await state.set_source_status(False, str(exc))
            await asyncio.sleep(args.reconnect_seconds)


async def inference_loop(
    state: ActionState,
    args: argparse.Namespace,
    backend: LlamaCppBackend,
    pose_preprocessor: PosePreprocessor,
) -> None:
    """Classify the visible human action whenever a fresh 8-frame batch is ready."""
    last_abnormal_published_at = 0.0
    async with ClientSession() as session:
        while True:
            if not backend.ready:
                await state.set_backend_status(backend.status())
                await state.set_prediction("Inference unavailable", backend.error)
                await asyncio.sleep(2.0)
                continue

            frames = await state.prepare_inference_batch(args.history_seconds, args.current_second_samples)
            if not frames:
                snapshot = await state.snapshot(args.history_seconds, args.current_second_samples)
                ready_count = snapshot["history_frames"] + snapshot["sampled_current_second_frames"]
                if not snapshot["inference_in_flight"] and snapshot["prediction_count"] == 0:
                    await state.set_prediction(f"Waiting for frames ({ready_count}/8)", None)
                async with state.condition:
                    await state.condition.wait()
                continue
            try:
                prediction, timing = await call_llamacpp(
                    session,
                    backend.api_base,
                    args.model,
                    frames,
                    pose_preprocessor,
                    args.max_output_tokens,
                    args.history_seconds,
                    args.current_second_samples,
                    args.inference_jpeg_quality,
                    args.inference_long_side,
                )
                await state.set_prediction(prediction, None, timing)
                LOGGER.info("prediction: %s timings_ms=%s", prediction, timing)
                if isinstance(prediction, ParsedAction) and should_publish_abnormal_event(prediction):
                    now = time.time()
                    if abnormal_cooldown_elapsed(last_abnormal_published_at, now, args.abnormal_cooldown_seconds):
                        try:
                            published_event = maybe_publish_abnormal_event(prediction, frames, args)
                            if published_event is not None:
                                last_abnormal_published_at = now
                                await state.set_abnormal_publish_status(published_event, None)
                                LOGGER.info("published abnormal event to %s", published_event["topic"])
                        except Exception as exc:
                            LOGGER.exception("failed to publish abnormal event")
                            await state.set_abnormal_publish_status(None, str(exc))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.exception("action inference failed")
                await state.set_prediction("Inference failed", str(exc))
            finally:
                await state.finish_inference()


def build_app(args: argparse.Namespace) -> web.Application:
    """Build the browser app."""
    state = ActionState()
    pose_preprocessor = PosePreprocessor(args.pose_mode, args.pose_model, args.pose_device)
    backend = LlamaCppBackend(args)
    app = web.Application()
    app["state"] = state
    app["args"] = args
    app["pose_preprocessor"] = pose_preprocessor
    app["backend"] = backend
    app["tasks"] = []

    async def on_startup(app_: web.Application) -> None:
        pose_preprocessor.initialize()
        await state.set_pose_status(pose_preprocessor.status())
        await backend.start()
        await state.set_backend_status(backend.status())
        app_["tasks"] = [
            asyncio.create_task(frame_source_loop(state, args)),
            asyncio.create_task(inference_loop(state, args, backend, pose_preprocessor)),
        ]

    async def on_cleanup(app_: web.Application) -> None:
        for task in app_["tasks"]:
            task.cancel()
        await asyncio.gather(*app_["tasks"], return_exceptions=True)
        await backend.stop()

    async def index(request: web.Request) -> web.Response:
        html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Temi Action Viewer</title>
  <style>
    body { margin: 0; background: #0b0f14; color: #edf2f7; font-family: system-ui, sans-serif; }
    main { min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }
    header { padding: 12px 16px; background: #171c23; display: flex; gap: 16px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid #2a3340; }
    h1 { margin: 0; font-size: 16px; }
    code { color: #7dd3fc; }
    img { width: 100%; height: calc(100vh - 58px); object-fit: contain; background: #050607; display: block; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Temi Action Viewer</h1>
      <span>Stream: <code>/stream.mjpg</code></span>
      <span>Status: <code>/health</code></span>
    </header>
    <img src="/stream.mjpg" alt="Temi action stream">
  </main>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def stream(request: web.Request) -> web.StreamResponse:
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
            async with state.condition:
                await state.condition.wait_for(lambda: state.frame_count != last_count)
                latest_frame = state.latest_frame
                prediction = state.latest_prediction
                inference_error = state.inference_error
                average_inference_ms = (
                    None if state.prediction_count == 0 else state.total_inference_ms / state.prediction_count
                )
                fps = calculate_fps(list(state.frames), time.time())
                last_count = state.frame_count

            if latest_frame is None:
                await asyncio.sleep(0.05)
                continue

            jpeg = overlay_prediction(
                latest_frame,
                prediction,
                inference_error,
                args.jpeg_quality,
                average_inference_ms,
                None if state.latest_timing is None else dict(state.latest_timing.__dict__),
                fps,
            )
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
        snapshot_data = await state.snapshot(args.history_seconds, args.current_second_samples)
        latest_frame = snapshot_data["latest_frame"]
        if latest_frame is None:
            return web.Response(status=404, text="no frame received yet\n")
        jpeg = overlay_prediction(
            latest_frame,
            snapshot_data["latest_prediction"],
            snapshot_data["inference_error"],
            args.jpeg_quality,
            snapshot_data["average_inference_ms"],
            snapshot_data["latest_timing_ms"],
            calculate_fps(snapshot_data["frames"], time.time()),
        )
        return web.Response(body=jpeg, content_type="image/jpeg")

    async def health(request: web.Request) -> web.Response:
        snapshot_data = await state.snapshot(args.history_seconds, args.current_second_samples)
        prediction_age_ms = None
        if snapshot_data["prediction_age"] is not None:
            prediction_age_ms = int((time.time() - snapshot_data["prediction_age"]) * 1000)
        return web.json_response(
            {
                "ok": True,
                "source_url": args.source_url,
                "source_connected": snapshot_data["source_connected"],
                "source_error": snapshot_data["source_error"],
                "frame_count": snapshot_data["frame_count"],
                "buffered_frames": len(snapshot_data["frames"]),
                "history_frames": snapshot_data["history_frames"],
                "current_second_frames": snapshot_data["current_second_frames"],
                "sampled_current_second_frames": snapshot_data["sampled_current_second_frames"],
                "ready_for_inference": snapshot_data["ready_for_inference"],
                "inference_in_flight": snapshot_data["inference_in_flight"],
                **snapshot_data["backend_status"],
                **snapshot_data["pose_status"],
                "model": args.model,
                "latest_prediction": snapshot_data["latest_prediction"],
                "latest_action": snapshot_data["latest_action"],
                "latest_abnormal_event": snapshot_data["latest_abnormal_event"],
                "abnormal_publish_count": snapshot_data["abnormal_publish_count"],
                "abnormal_publish_error": snapshot_data["abnormal_publish_error"],
                "abnormal_publish": args.abnormal_publish,
                "abnormal_cooldown_seconds": args.abnormal_cooldown_seconds,
                "discord_notify": args.discord_notify,
                "discord_env_path": args.discord_env_path,
                "discord_max_files": args.discord_max_files,
                **notification_health(args),
                "prediction_count": snapshot_data["prediction_count"],
                "prediction_age_ms": prediction_age_ms,
                "average_inference_ms": snapshot_data["average_inference_ms"],
                "latest_inference_ms": snapshot_data["latest_inference_ms"],
                "latest_timing_ms": snapshot_data["latest_timing_ms"],
                "average_timing_ms": snapshot_data["average_timing_ms"],
                "fps": calculate_fps(snapshot_data["frames"], time.time()),
                "inference_error": snapshot_data["inference_error"],
            }
        )

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/", index)
    app.router.add_get("/stream.mjpg", stream)
    app.router.add_get("/snapshot.jpg", snapshot)
    app.router.add_get("/health", health)
    return app


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="Predict visible human action from Temi 8081 frame broadcast.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010, help="HTTP port. Use 0 to auto-pick 8010-8999.")
    parser.add_argument("--source-url", default="ws://127.0.0.1:8081")
    parser.add_argument(
        "--lmstudio-base-url",
        default="http://127.0.0.1:1234/v1",
        help="Deprecated; llama.cpp backend uses --llama-api-base-url or managed --llama-server.",
    )
    parser.add_argument("--model", default="gemma-4-e4b-finetuned@q8_0")
    parser.add_argument("--gguf-model-path", default=DEFAULT_GGUF_MODEL_PATH)
    parser.add_argument("--mmproj-path", default=DEFAULT_MMPROJ_PATH)
    parser.add_argument("--llama-server", default=DEFAULT_LLAMA_SERVER_PATH)
    parser.add_argument("--llama-api-base-url", default="")
    parser.add_argument("--llama-server-host", default="127.0.0.1")
    parser.add_argument("--llama-server-port", type=int, default=8011)
    parser.add_argument("--llama-ctx-size", type=int, default=8192)
    parser.add_argument("--llama-threads", type=int, default=8)
    parser.add_argument("--llama-gpu-layers", default="all")
    parser.add_argument(
        "--llama-cuda-visible-devices",
        default="",
        help="CUDA_VISIBLE_DEVICES applied only to managed llama-server, e.g. 3.",
    )
    parser.add_argument("--llama-startup-timeout", type=float, default=30.0)
    parser.add_argument("--pose-mode", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--pose-model", default="yolo26x-pose.pt")
    parser.add_argument("--pose-device", default="0", help="Ultralytics device for YOLO pose, e.g. 0, cuda:0, or cpu.")
    parser.add_argument(
        "--inference-interval",
        type=float,
        default=4.0,
        help="Deprecated; inference is now event-driven and starts after the previous result returns.",
    )
    parser.add_argument("--history-seconds", type=int, default=3)
    parser.add_argument("--current-second-samples", type=int, default=5)
    parser.add_argument("--max-output-tokens", type=int, default=96)
    parser.add_argument("--inference-jpeg-quality", type=int, default=92)
    parser.add_argument("--inference-long-side", type=int, default=896)
    parser.add_argument("--retention-seconds", type=float, default=6.0)
    parser.add_argument("--reconnect-seconds", type=float, default=2.0)
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--max-message-mb", type=int, default=8)
    parser.add_argument("--robot-id", default="temi-01")
    parser.add_argument("--mqtt-broker", default="127.0.0.1")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--abnormal-publish", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--abnormal-cooldown-seconds", type=float, default=30.0)
    parser.add_argument("--abnormal-source", default="temi_action_viewer")
    parser.add_argument("--shared-root", default="/TemiAgent/temi_shared")
    parser.add_argument("--discord-notify", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--discord-env-path", default=DEFAULT_DISCORD_ENV_PATH)
    parser.add_argument("--discord-max-files", type=int, default=8)
    parser.add_argument(
        "--discord-delivery-test",
        action="store_true",
        help="Send one [TEST] Discord webhook message without detector, MQTT, TTS, or care-memory activity.",
    )
    parser.add_argument("--pre-alert-speak", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--pre-alert-language", default="zh-TW")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    """Run the action viewer."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    if args.port == 0:
        args.port = find_free_port()
    if not 8000 <= args.port <= 8999:
        raise SystemExit("--port must be in the 8000-8999 range")
    if args.history_seconds < 1:
        raise SystemExit("--history-seconds must be at least 1")
    if args.current_second_samples < 1:
        raise SystemExit("--current-second-samples must be at least 1")
    if args.history_seconds + args.current_second_samples != 8:
        raise SystemExit("--history-seconds plus --current-second-samples must equal 8")
    if not 1 <= args.inference_jpeg_quality <= 100:
        raise SystemExit("--inference-jpeg-quality must be in 1-100")
    if args.inference_long_side < 0:
        raise SystemExit("--inference-long-side must be non-negative")
    if args.discord_delivery_test:
        try:
            result = run_discord_delivery_test(args)
        except DiscordDeliveryError as exc:
            result: dict[str, Any] = {"test": "discord_delivery", "failure_code": exc.failure_code}
            if exc.status_code is not None:
                result["status_code"] = exc.status_code
            if exc.retry_after_seconds is not None:
                result["retry_after_seconds"] = exc.retry_after_seconds
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            raise SystemExit(1) from exc
        result["test"] = "discord_delivery"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if result["failure_code"] != "DISCORD_DELIVERED":
            raise SystemExit(1)
        return

    app = build_app(args)
    LOGGER.info("open http://127.0.0.1:%s/ to view action predictions", args.port)
    LOGGER.info("reading frames from %s", args.source_url)
    LOGGER.info("using llama.cpp model %s via %s", args.model, args.llama_api_base_url or args.llama_server)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
