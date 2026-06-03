#!/usr/bin/env python3
"""Adapt the installed Temi Android app topics to the project overview contract.

The Android app available on this PC still publishes legacy ASR on
``temi/event/asr`` while the newer app directly subscribes to canonical command
requests such as ``temi/{robot_id}/cmd/request``. This adapter owns only the
legacy ASR and camera-frame side of the translation layer: it hosts the video
WebSocket, samples synchronized keyframes, and publishes canonical ASR events.
It intentionally does not forward command requests, so Temi does not speak twice.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "temi_backend" / "src"))

from temi_backend.vision_server import JpegFrameBroadcaster, VisionServer  # noqa: E402


LOGGER = logging.getLogger("temi_overview_adapter")

LEGACY_ASR_TOPIC = "temi/event/asr"
OVERVIEW_ASR_TOPIC_TEMPLATE = "temi/{robot_id}/asr/final"


def now_ms() -> int:
    """Return current Unix time in milliseconds."""
    return int(time.time() * 1000)


def build_event_id(timestamp_ms: int) -> str:
    """Create a deterministic event id from an ASR timestamp."""
    return f"evt_temi_{timestamp_ms}"


class OverviewAdapter:
    """Bridge legacy Temi ASR/camera input into canonical ASR events."""

    def __init__(
        self,
        *,
        robot_id: str,
        broker: str,
        port: int,
        vision_host: str,
        vision_port: int,
        shared_root: Path,
        bridge_root: str,
        conversation_id: str,
        frame_broadcast_host: str = "0.0.0.0",
        frame_broadcast_port: int = 8081,
        enable_frame_broadcast: bool = True,
    ) -> None:
        """Configure MQTT translation and the local video receiver."""
        self.robot_id = robot_id
        self.broker = broker
        self.port = port
        frame_broadcaster = (
            JpegFrameBroadcaster(host=frame_broadcast_host, port=frame_broadcast_port)
            if enable_frame_broadcast
            else None
        )
        self.vision = VisionServer(host=vision_host, port=vision_port, frame_broadcaster=frame_broadcaster)
        self.shared_root = shared_root
        self.bridge_root = bridge_root.rstrip("/")
        self.conversation_id = conversation_id
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "temi-overview-adapter")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start_mqtt(self) -> None:
        """Connect to MQTT and start the background network loop."""
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def stop_mqtt(self) -> None:
        """Stop MQTT networking and disconnect from the broker."""
        self.client.loop_stop()
        self.client.disconnect()

    async def run(self) -> None:
        """Run MQTT translation and the video WebSocket server together."""
        self.start_mqtt()
        try:
            await self.vision.start()
        finally:
            self.stop_mqtt()

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        """Subscribe to legacy ASR only; Temi consumes canonical commands directly."""
        if reason_code == 0 or str(reason_code).lower() == "success":
            LOGGER.info("connected to MQTT broker at %s:%s", self.broker, self.port)
            client.subscribe(LEGACY_ASR_TOPIC, qos=1)
            return
        LOGGER.error("failed to connect to MQTT broker: %s", reason_code)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Decode JSON MQTT payloads and dispatch by topic shape."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.exception("ignored invalid JSON on %s", msg.topic)
            return
        if not isinstance(payload, dict):
            LOGGER.warning("ignored non-object payload on %s", msg.topic)
            return

        if msg.topic == LEGACY_ASR_TOPIC:
            self.handle_legacy_asr(payload)

    def handle_legacy_asr(self, payload: dict[str, Any]) -> None:
        """Convert one legacy ASR payload into a canonical Overview ASR event."""
        text = str(payload.get("text") or "").strip()
        if not text:
            LOGGER.warning("ignored empty legacy ASR payload")
            return
        timestamp_ms = int(payload.get("timestamp_ms") or now_ms())
        language = str(payload.get("language") or "zh-TW")
        if language.upper() == "SYSTEM":
            language = "zh-TW"
        event_id = str(payload.get("event_id") or build_event_id(timestamp_ms))
        event_dir = self.shared_root / "events" / self.robot_id / event_id
        event_dir.mkdir(parents=True, exist_ok=True)

        keyframes = self.vision.buffer.get_keyframes(timestamp_ms)
        if len(keyframes) != 3:
            LOGGER.error("cannot create Overview ASR event; no aligned vision frames for %s", event_id)
            return

        frame_specs = [
            ("t_minus_1000", "frame_t_minus_1000.jpg"),
            ("t_minus_500", "frame_t_minus_500.jpg"),
            ("t", "frame_t.jpg"),
        ]
        frames: list[dict[str, Any]] = []
        for spec, keyframe in zip(frame_specs, keyframes, strict=True):
            name, filename = spec
            path = event_dir / filename
            if not cv2.imwrite(str(path), keyframe["frame"]):
                raise RuntimeError(f"failed to write frame: {path}")
            frames.append(
                {
                    "name": name,
                    "ts_ms": int(keyframe["actual_t"]),
                    "path": f"{self.bridge_root}/events/{self.robot_id}/{event_id}/{filename}",
                    "mime_type": "image/jpeg",
                }
            )

        overview_event = {
            "schema_version": "1.0",
            "event_id": event_id,
            "robot_id": self.robot_id,
            "conversation_id": self.conversation_id,
            "type": "asr.final",
            "timestamp_ms": now_ms(),
            "speech_end_ts_ms": timestamp_ms,
            "language": language,
            "asr": {"text": text, "confidence": payload.get("confidence", 1.0)},
            "vision": {"sampling_policy": "T-1000,T-500,T", "frames": frames},
            "context": {
                "source": "temi_overview_adapter",
                "wake_word_detected": True,
                "interaction_mode": "voice",
                "requires_response": True,
            },
        }
        (event_dir / "metadata.json").write_text(
            json.dumps(overview_event, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        topic = OVERVIEW_ASR_TOPIC_TEMPLATE.format(robot_id=self.robot_id)
        self.client.publish(topic, json.dumps(overview_event, ensure_ascii=False), qos=1)
        LOGGER.info("published Overview ASR event %s from legacy ASR text: %s", event_id, text)



def parse_args() -> argparse.Namespace:
    """Parse CLI flags for the local adapter process."""
    parser = argparse.ArgumentParser(description="Adapt legacy Temi app topics to the Overview MQTT contract.")
    parser.add_argument("--robot-id", default="temi-01")
    parser.add_argument("--broker", default="192.168.50.236")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--vision-host", default="0.0.0.0")
    parser.add_argument("--vision-port", type=int, default=8080)
    parser.add_argument("--frame-broadcast-host", default="0.0.0.0")
    parser.add_argument("--frame-broadcast-port", type=int, default=8081)
    parser.add_argument("--disable-frame-broadcast", action="store_true")
    parser.add_argument("--shared-root", default="/TemiAgent/temi_shared")
    parser.add_argument("--bridge-root", default="/TemiAgent/temi_shared")
    parser.add_argument("--conversation-id", default="conv_temi_live")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    """Run the adapter until interrupted by SIGINT or SIGTERM."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    adapter = OverviewAdapter(
        robot_id=args.robot_id,
        broker=args.broker,
        port=args.port,
        vision_host=args.vision_host,
        vision_port=args.vision_port,
        frame_broadcast_host=args.frame_broadcast_host,
        frame_broadcast_port=args.frame_broadcast_port,
        enable_frame_broadcast=not args.disable_frame_broadcast,
        shared_root=Path(args.shared_root),
        bridge_root=args.bridge_root,
        conversation_id=args.conversation_id,
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)
    task = loop.create_task(adapter.run())
    try:
        loop.run_forever()
    finally:
        task.cancel()
        adapter.stop_mqtt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
