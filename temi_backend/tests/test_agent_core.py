"""Unit tests for AgentCore orchestration behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from temi_backend.agent_core import AgentCore
from temi_backend.config import AgentConfig


class FakeMqttBridge:
    """Small fake MQTT bridge used to inspect published messages."""

    def __init__(self) -> None:
        self.asr_callback = None
        self.speak_calls: list[tuple[str, str, bool]] = []

    def set_asr_callback(self, callback):
        self.asr_callback = callback

    def publish_speak(self, text: str, language: str = "ZH_TW", continue_listening: bool = False) -> None:
        self.speak_calls.append((text, language, continue_listening))


class FakeRouter:
    """Capture routed model responses."""

    def __init__(self) -> None:
        self.responses: list[str] = []

    def route(self, llm_response: str) -> int:
        self.responses.append(llm_response)
        return 1


def make_client(response_text: str):
    """Create an OpenAI-compatible fake chat client."""
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=response_text),
                )
            ]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, captured


def test_on_asr_event_without_frames_publishes_recovery_message(tmp_path: Path) -> None:
    frame_buffer = SimpleNamespace(get_keyframes=lambda timestamp_ms: [])
    vision = SimpleNamespace(buffer=frame_buffer)
    mqtt = FakeMqttBridge()
    client, _captured = make_client("[]")
    config = AgentConfig(debug_frames_dir=tmp_path, enable_debug_frames=False)

    core = AgentCore(config=config, vision=vision, mqtt_bridge=mqtt, lm_client=client, router=FakeRouter())
    core.on_asr_event({"text": "hello", "timestamp_ms": 1234})

    assert mqtt.speak_calls == [
        ("I could not find recent camera frames. Please try again.", "EN_US", False)
    ]


def test_call_vlm_sends_multimodal_content_and_routes_response(tmp_path: Path) -> None:
    mqtt = FakeMqttBridge()
    router = FakeRouter()
    client, captured = make_client('[{"action":"speak","parameters":{"text":"ok"}}]')
    config = AgentConfig(debug_frames_dir=tmp_path, enable_debug_frames=False, lm_model="unit-test-model")
    vision = SimpleNamespace(buffer=SimpleNamespace(get_keyframes=lambda timestamp_ms: []))
    core = AgentCore(config=config, vision=vision, mqtt_bridge=mqtt, lm_client=client, router=router)

    core.call_vlm("what is this", ["a", "b", "c"])

    assert captured["model"] == "unit-test-model"
    assert captured["messages"][0]["role"] == "system"
    user_content = captured["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert [item["type"] for item in user_content[1:]] == ["image_url", "image_url", "image_url"]
    assert router.responses == ['[{"action":"speak","parameters":{"text":"ok"}}]']


def test_image_to_base64_returns_jpeg_payload(tmp_path: Path) -> None:
    mqtt = FakeMqttBridge()
    client, _captured = make_client("[]")
    config = AgentConfig(debug_frames_dir=tmp_path, enable_debug_frames=False)
    vision = SimpleNamespace(buffer=SimpleNamespace(get_keyframes=lambda timestamp_ms: []))
    core = AgentCore(config=config, vision=vision, mqtt_bridge=mqtt, lm_client=client, router=FakeRouter())

    encoded = core.image_to_base64(np.zeros((4, 4, 3), dtype=np.uint8))

    assert isinstance(encoded, str)
    assert len(encoded) > 0
