"""Unit tests for the MQTT bridge transport wrapper."""

from __future__ import annotations

import json
from types import SimpleNamespace

from temi_backend.mqtt_bridge import MqttBridge, TOPIC_ASR, TOPIC_NAVIGATE, TOPIC_SPEAK


class FakeClient:
    """Minimal Paho-compatible client for publish and subscribe assertions."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str, int]] = []
        self.subscriptions: list[str] = []
        self.connected = False
        self.loop_started = False
        self.on_connect = None
        self.on_message = None

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))

    def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    def connect(self, broker: str, port: int, keepalive: int) -> None:
        self.connected = True

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def disconnect(self) -> None:
        self.connected = False


def test_publish_speak_uses_expected_topic_and_payload() -> None:
    client = FakeClient()
    bridge = MqttBridge(client=client)

    bridge.publish_speak("hello", language="EN_US", continue_listening=True)

    topic, payload, qos = client.published[0]
    assert topic == TOPIC_SPEAK
    assert qos == 1
    assert json.loads(payload) == {
        "text": "hello",
        "language": "EN_US",
        "continue_listening": True,
    }


def test_publish_navigate_uses_expected_topic_and_payload() -> None:
    client = FakeClient()
    bridge = MqttBridge(client=client)

    bridge.publish_navigate("home_base")

    topic, payload, qos = client.published[0]
    assert topic == TOPIC_NAVIGATE
    assert qos == 1
    assert json.loads(payload) == {"target_location": "home_base"}


def test_asr_message_is_decoded_and_forwarded() -> None:
    client = FakeClient()
    bridge = MqttBridge(client=client)
    received = []
    bridge.set_asr_callback(received.append)

    msg = SimpleNamespace(topic=TOPIC_ASR, payload=b'{"text":"go","timestamp_ms":42}')
    bridge._on_message(client, None, msg)

    assert received == [{"text": "go", "timestamp_ms": 42}]


def test_connect_subscribes_to_asr_topic() -> None:
    client = FakeClient()
    bridge = MqttBridge(client=client)

    bridge._on_connect(client, None, None, 0, None)

    assert client.subscriptions == [TOPIC_ASR]
