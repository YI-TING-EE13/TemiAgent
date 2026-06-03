"""High-level TemiAgent orchestration and skill routing."""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import cv2
from openai import OpenAI

from temi_backend.config import AgentConfig
from temi_backend.mqtt_bridge import MqttBridge
from temi_backend.vision_server import JpegFrameBroadcaster, VisionServer

LOGGER = logging.getLogger(__name__)


class SkillRouter:
    """Validate and dispatch VLM action JSON to the robot command bridge."""

    def __init__(self, mqtt_bridge: MqttBridge) -> None:
        """Create a router backed by an MQTT command publisher."""
        self.mqtt = mqtt_bridge

    def _extract_actions(self, llm_response: str) -> list[dict[str, Any]]:
        """Extract a JSON action array from raw model text."""
        json_match = re.search(r"\[\s*\{.*?\}\s*\]", llm_response, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
        else:
            json_text = llm_response.split("</think>")[-1].strip()
            json_text = re.sub(r"^```(?:json)?", "", json_text.strip(), flags=re.IGNORECASE).strip()
            json_text = re.sub(r"```$", "", json_text).strip()

        actions = json.loads(json_text)
        if not isinstance(actions, list):
            raise ValueError("The model response must contain a JSON array of actions.")
        return actions

    def route(self, llm_response: str) -> int:
        """Parse and execute supported actions from a VLM response.

        Args:
            llm_response: Raw response text from the local VLM. The response may
                contain markdown fences or hidden reasoning blocks before the JSON.

        Returns:
            Number of supported actions that were executed.
        """
        try:
            actions = self._extract_actions(llm_response)
        except (json.JSONDecodeError, ValueError) as exc:
            LOGGER.error("Failed to parse VLM actions: %s", exc)
            return 0

        executed_count = 0
        for action_obj in actions:
            if not isinstance(action_obj, dict):
                LOGGER.warning("Skipping malformed action: %r", action_obj)
                continue

            action_name = action_obj.get("action")
            params = action_obj.get("parameters") or {}
            if not isinstance(params, dict):
                LOGGER.warning("Skipping action with invalid parameters: %r", action_obj)
                continue

            if action_name == "speak":
                self.mqtt.publish_speak(
                    text=str(params.get("text", "")),
                    language=str(params.get("language", "ZH_TW")),
                    continue_listening=bool(params.get("continue_listening", False)),
                )
                executed_count += 1
            elif action_name == "navigate":
                self.mqtt.publish_navigate(str(params.get("target_location", "")))
                executed_count += 1
            else:
                LOGGER.warning("Skipping unsupported action: %s", action_name)

        return executed_count


class AgentCore:
    """Coordinate speech events, visual context, VLM inference, and robot actions."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        vision: VisionServer | None = None,
        mqtt_bridge: MqttBridge | None = None,
        lm_client: Any | None = None,
        router: SkillRouter | None = None,
    ) -> None:
        """Initialize all runtime dependencies.

        Args:
            config: Runtime settings. Environment defaults are used when omitted.
            vision: Optional vision server dependency for tests or custom hosting.
            mqtt_bridge: Optional MQTT bridge dependency for tests.
            lm_client: Optional OpenAI-compatible client dependency for tests.
            router: Optional skill router dependency for tests.
        """
        self.config = config or AgentConfig.from_env()
        if vision:
            self.vision = vision
        else:
            frame_broadcaster = (
                JpegFrameBroadcaster(
                    host=self.config.frame_broadcast_host,
                    port=self.config.frame_broadcast_port,
                    jpeg_quality=self.config.frame_broadcast_jpeg_quality,
                )
                if self.config.enable_frame_broadcast
                else None
            )
            self.vision = VisionServer(
                self.config.vision_host,
                self.config.vision_port,
                frame_broadcaster=frame_broadcaster,
            )
        self.mqtt = mqtt_bridge or MqttBridge(
            self.config.mqtt_broker,
            self.config.mqtt_port,
            self.config.mqtt_client_id,
        )
        self.mqtt.set_asr_callback(self.on_asr_event)
        self.router = router or SkillRouter(self.mqtt)
        self.lm_client = lm_client or OpenAI(base_url=self.config.lm_base_url, api_key=self.config.lm_api_key)
        self.system_prompt = self.config.load_system_prompt()

        if self.config.enable_debug_frames:
            self.config.debug_frames_dir.mkdir(parents=True, exist_ok=True)

    def image_to_base64(self, frame: Any) -> str:
        """Encode an OpenCV BGR frame as a Base64 JPEG string."""
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            raise ValueError("OpenCV failed to encode the frame as JPEG.")
        return base64.b64encode(buffer).decode("utf-8")

    def _save_debug_frame(self, timestamp_ms: int, frame_index: int, frame: Any) -> None:
        """Persist one ASR-aligned frame for offline inspection."""
        if not self.config.enable_debug_frames:
            return

        suffixes = ("T-1000", "T-500", "T")
        suffix = suffixes[frame_index] if frame_index < len(suffixes) else f"T{frame_index}"
        filename = Path(self.config.debug_frames_dir) / f"asr_{timestamp_ms}_{suffix}.jpg"
        cv2.imwrite(str(filename), frame)

    def on_asr_event(self, payload: dict[str, Any]) -> None:
        """Handle a robot ASR event and ask the VLM for the next action."""
        user_text = str(payload.get("text", ""))
        timestamp_ms = int(payload.get("timestamp_ms", 0))
        LOGGER.info("Received ASR event at %s ms: %s", timestamp_ms, user_text)

        keyframes = self.vision.buffer.get_keyframes(timestamp_ms)
        if not keyframes:
            self.mqtt.publish_speak(
                "I could not find recent camera frames. Please try again.",
                language="EN_US",
                continue_listening=False,
            )
            return

        base64_images: list[str] = []
        for index, keyframe in enumerate(keyframes):
            frame = keyframe["frame"]
            base64_images.append(self.image_to_base64(frame))
            self._save_debug_frame(timestamp_ms, index, frame)

        self.call_vlm(user_text, base64_images)

    def call_vlm(self, user_text: str, base64_images: list[str]) -> None:
        """Send speech and aligned camera frames to the local VLM."""
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "User said: "
                    f"{user_text}\n"
                    "Frames are ordered as T-1000 ms, T-500 ms, and T."
                ),
            }
        ]
        for encoded_image in base64_images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                }
            )

        try:
            response = self.lm_client.chat.completions.create(
                model=self.config.lm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            llm_response = response.choices[0].message.content
            LOGGER.info("Received VLM response: %s", llm_response)
            self.router.route(llm_response)
        except Exception as exc:
            LOGGER.error("Failed to call local VLM: %s", exc)
            self.mqtt.publish_speak(
                "I could not reach the local vision model. Please check the backend.",
                language="EN_US",
                continue_listening=False,
            )

    def run(self) -> None:
        """Start vision, MQTT, and the blocking backend event loop."""
        self.vision.run_in_background()
        self.mqtt.start()
        LOGGER.info("TemiAgent backend is running. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            LOGGER.info("Stopping TemiAgent backend.")
            self.mqtt.stop()
