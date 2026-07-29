"""Paho MQTT runtime wrapper for HermesTemiBridge."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .config import BridgeConfig

LOGGER = logging.getLogger(__name__)


class MqttUnavailableError(RuntimeError):
    """Raised when the optional paho-mqtt dependency is unavailable."""


class TemiMqttClient:
    """Subscribe to ASR/result topics and publish command requests."""

    def __init__(self, config: BridgeConfig):
        """Create a runtime MQTT client from Bridge configuration."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise MqttUnavailableError(
                "paho-mqtt is required for MQTT runtime. Install with: uv pip install -e '.[mqtt]'"
            ) from exc

        self._mqtt = mqtt
        self.config = config
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "hermes-temi-bridge")
        if config.mqtt_username:
            self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._asr_handler: Callable[[str, dict[str, Any]], None] | None = None
        self._abnormal_handler: Callable[[str, dict[str, Any]], None] | None = None
        self._result_handler: Callable[[str, dict[str, Any]], None] | None = None
        self._identity_handler: Callable[[str, dict[str, Any]], None] | None = None

    def set_asr_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """Register the callback for canonical ASR final events."""
        self._asr_handler = handler

    def set_abnormal_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """Register the callback for abnormal perception events."""
        self._abnormal_handler = handler

    def set_result_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """Register the callback for command result events."""
        self._result_handler = handler

    def set_identity_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """Register the callback for the existing canonical identity result topic."""
        self._identity_handler = handler

    def connect(self) -> None:
        """Connect to the configured MQTT broker."""
        self.client.connect(self.config.mqtt_broker_host, self.config.mqtt_broker_port, 60)

    def loop_forever(self) -> None:
        """Enter Paho's blocking network loop."""
        self.client.loop_forever()

    def stop(self) -> None:
        """Disconnect from the broker."""
        self.client.disconnect()

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Publish one command request for a specific robot id."""
        topic = f"temi/{robot_id}/cmd/request"
        self.client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        LOGGER.info("published command to %s", topic)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        """Subscribe to Bridge topics after a successful connection."""
        if not _is_success_reason_code(reason_code):
            LOGGER.error("failed to connect to MQTT broker: %s", reason_code)
            return
        LOGGER.info("connected to MQTT broker")
        client.subscribe("temi/+/asr/final", qos=1)
        client.subscribe("temi/+/perception/abnormal", qos=1)
        client.subscribe("temi/+/cmd/result", qos=1)
        client.subscribe("temi/+/resident/identity/result", qos=1)

    def _on_message(self, client, userdata, msg) -> None:
        """Decode MQTT JSON and dispatch it to the registered handler."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.exception("invalid JSON payload on %s", msg.topic)
            return
        if not isinstance(payload, dict):
            LOGGER.warning("ignored non-object payload on %s", msg.topic)
            return
        if msg.topic.endswith("/asr/final") and self._asr_handler:
            self._asr_handler(msg.topic, payload)
        elif msg.topic.endswith("/perception/abnormal") and self._abnormal_handler:
            self._abnormal_handler(msg.topic, payload)
        elif msg.topic.endswith("/cmd/result") and self._result_handler:
            self._result_handler(msg.topic, payload)
        elif msg.topic.endswith("/resident/identity/result") and self._identity_handler:
            self._identity_handler(msg.topic, payload)


def _is_success_reason_code(reason_code: Any) -> bool:
    """Handle Paho reason code differences across callback API versions."""
    if reason_code == 0:
        return True
    return str(reason_code).lower() == "success"
