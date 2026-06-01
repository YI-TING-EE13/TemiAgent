from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .config import BridgeConfig

LOGGER = logging.getLogger(__name__)


class MqttUnavailableError(RuntimeError):
    pass


class TemiMqttClient:
    def __init__(self, config: BridgeConfig):
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
        self._result_handler: Callable[[str, dict[str, Any]], None] | None = None

    def set_asr_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        self._asr_handler = handler

    def set_result_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        self._result_handler = handler

    def connect(self) -> None:
        self.client.connect(self.config.mqtt_broker_host, self.config.mqtt_broker_port, 60)

    def loop_forever(self) -> None:
        self.client.loop_forever()

    def stop(self) -> None:
        self.client.disconnect()

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        topic = f"temi/{robot_id}/cmd/request"
        self.client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        LOGGER.info("published command to %s", topic)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if int(reason_code) != 0:
            LOGGER.error("failed to connect to MQTT broker: %s", reason_code)
            return
        LOGGER.info("connected to MQTT broker")
        client.subscribe("temi/+/asr/final", qos=1)
        client.subscribe("temi/event/asr", qos=1)
        client.subscribe("temi/+/cmd/result", qos=1)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.exception("invalid JSON payload on %s", msg.topic)
            return
        if not isinstance(payload, dict):
            LOGGER.warning("ignored non-object payload on %s", msg.topic)
            return
        if (msg.topic.endswith("/asr/final") or msg.topic == "temi/event/asr") and self._asr_handler:
            self._asr_handler(msg.topic, payload)
        elif msg.topic.endswith("/cmd/result") and self._result_handler:
            self._result_handler(msg.topic, payload)
