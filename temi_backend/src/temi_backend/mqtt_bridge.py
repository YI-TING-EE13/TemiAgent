"""MQTT transport layer for TemiAgent robot events and commands."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

LOGGER = logging.getLogger(__name__)

TOPIC_ASR = "temi/event/asr"
TOPIC_SPEAK = "temi/action/speak"
TOPIC_NAVIGATE = "temi/action/navigate"


class MqttBridge:
    """Manage MQTT subscriptions and command publishing for a Temi robot."""

    def __init__(
        self,
        broker: str = "127.0.0.1",
        port: int = 1883,
        client_id: str = "temi-backend-brain",
        client: Any | None = None,
    ) -> None:
        """Create a bridge bound to one MQTT broker.

        Args:
            broker: Broker hostname or IP address.
            port: Broker TCP port.
            client_id: MQTT client identifier used by the backend process.
            client: Optional prebuilt Paho-compatible client for tests.
        """
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = client or mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
        self.on_asr_callback: Callable[[dict[str, Any]], None] | None = None

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def set_asr_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register the handler invoked when an ASR event arrives."""
        self.on_asr_callback = callback

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        """Subscribe to robot speech events after a successful broker connection."""
        if reason_code == 0 or str(reason_code).lower() == "success":
            LOGGER.info("Connected to MQTT broker at %s:%s.", self.broker, self.port)
            client.subscribe(TOPIC_ASR)
            return
        LOGGER.error("Failed to connect to MQTT broker, reason code: %s.", reason_code)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Decode inbound JSON payloads and dispatch supported robot events."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            LOGGER.error("Failed to parse MQTT payload on %s: %s", msg.topic, exc)
            return

        if msg.topic == TOPIC_ASR and self.on_asr_callback:
            self.on_asr_callback(payload)

    def publish_speak(
        self,
        text: str,
        language: str = "ZH_TW",
        continue_listening: bool = False,
    ) -> None:
        """Publish a text-to-speech command for the Android Temi client."""
        payload = {
            "text": text,
            "language": language,
            "continue_listening": continue_listening,
        }
        self.client.publish(TOPIC_SPEAK, json.dumps(payload), qos=1)
        LOGGER.info("Published TTS command: %s", text)

    def publish_navigate(self, target_location: str) -> None:
        """Publish a navigation command to a predefined Temi map location."""
        payload = {"target_location": target_location}
        self.client.publish(TOPIC_NAVIGATE, json.dumps(payload), qos=1)
        LOGGER.info("Published navigation command: %s", target_location)

    def start(self) -> None:
        """Connect to MQTT and start the Paho network loop in the background."""
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def stop(self) -> None:
        """Stop the Paho network loop and disconnect cleanly."""
        self.client.loop_stop()
        self.client.disconnect()
