"""Unit tests for the Overview adapter role boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "temi_overview_adapter.py"
SPEC = importlib.util.spec_from_file_location("temi_overview_adapter", SCRIPT)
overview_adapter = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(overview_adapter)


class FakeClient:
    """Capture subscriptions and publications from the adapter."""

    def __init__(self) -> None:
        self.subscriptions: list[tuple[str, int]] = []
        self.published: list[tuple[str, str, int]] = []

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append((topic, qos))

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))


def make_adapter(tmp_path: Path, keyframes: list[dict] | None = None):
    adapter = overview_adapter.OverviewAdapter(
        robot_id="temi-01",
        broker="127.0.0.1",
        port=1883,
        vision_host="127.0.0.1",
        vision_port=8080,
        shared_root=tmp_path,
        bridge_root="/TemiAgent/temi_shared",
        conversation_id="conv_test",
    )
    adapter.client = FakeClient()
    adapter.vision = SimpleNamespace(
        buffer=SimpleNamespace(get_keyframes=lambda timestamp_ms: keyframes or [])
    )
    return adapter


def test_connect_subscribes_only_to_legacy_asr(tmp_path: Path) -> None:
    adapter = make_adapter(tmp_path)
    client = FakeClient()

    adapter._on_connect(client, None, None, 0, None)

    assert client.subscriptions == [(overview_adapter.LEGACY_ASR_TOPIC, 1)]


def test_adapter_does_not_expose_command_forwarder() -> None:
    assert not hasattr(overview_adapter.OverviewAdapter, "handle_overview_command")


def test_missing_keyframes_does_not_publish_speak_fallback(tmp_path: Path) -> None:
    adapter = make_adapter(tmp_path, keyframes=[])

    adapter.handle_legacy_asr({"text": "hello", "timestamp_ms": 1234})

    assert adapter.client.published == []


def test_legacy_asr_with_keyframes_publishes_canonical_event(tmp_path: Path) -> None:
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    keyframes = [
        {"actual_t": 1000, "frame": frame},
        {"actual_t": 1500, "frame": frame},
        {"actual_t": 2000, "frame": frame},
    ]
    adapter = make_adapter(tmp_path, keyframes=keyframes)

    adapter.handle_legacy_asr(
        {
            "text": "午安",
            "timestamp_ms": 2000,
            "event_id": "evt_test",
            "language": "zh-TW",
            "confidence": 0.9,
        }
    )

    assert len(adapter.client.published) == 1
    topic, payload, qos = adapter.client.published[0]
    event = json.loads(payload)
    assert topic == "temi/temi-01/asr/final"
    assert qos == 1
    assert event["event_id"] == "evt_test"
    assert event["asr"]["text"] == "午安"
    assert [frame["name"] for frame in event["vision"]["frames"]] == [
        "t_minus_1000",
        "t_minus_500",
        "t",
    ]
    assert (tmp_path / "events" / "temi-01" / "evt_test" / "metadata.json").exists()
