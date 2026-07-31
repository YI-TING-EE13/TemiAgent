#!/usr/bin/env python3
"""Run the documented newcomer scenarios through the live isolated Bridge.

This runner is deliberately a verifier, not an orchestrator: services must
already be started by ``scripts/demo``.  It publishes only canonical test
events, calls the Bridge-owned media callback, observes canonical command
results, and writes all evidence below the configured external runtime root.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable
from urllib.request import Request, urlopen
import uuid

import paho.mqtt.client as mqtt


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import demo_lifecycle as demo  # noqa: E402
from create_mock_event_images import JPEG_1X1, build_event  # noqa: E402
from hermes_temi_bridge.media_callback_socket import invoke_media_callback_socket  # noqa: E402


class ScenarioFailure(RuntimeError):
    """Raised when a required live newcomer scenario has no contract evidence."""


class Capture:
    """Observe only canonical request/result traffic from the isolated broker."""

    def __init__(self, config: demo.DemoConfig) -> None:
        self.config = config
        self.messages: list[tuple[str, dict[str, Any]]] = []
        self.ready = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"newcomer-verify-{uuid.uuid4().hex[:12]}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self) -> None:
        self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=15)
        self.client.loop_start()
        if not self.ready.wait(10):
            raise ScenarioFailure("scenario observer did not connect to the isolated broker")

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, suffix: str, payload: dict[str, Any]) -> None:
        result = self.client.publish(f"temi/{self.config.robot_id}/{suffix}", json.dumps(payload, ensure_ascii=False), qos=1)
        result.wait_for_publish(timeout=10)

    def wait_for(self, predicate: Callable[[str, dict[str, Any]], bool], *, timeout: float = 12) -> tuple[str, dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for topic, payload in list(self.messages):
                if predicate(topic, payload):
                    return topic, payload
            time.sleep(0.05)
        raise ScenarioFailure("timed out waiting for canonical command evidence")

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any) -> None:
        if int(reason_code) == 0:
            client.subscribe(f"temi/{self.config.robot_id}/cmd/#", qos=1)
            self.ready.set()

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            self.messages.append((message.topic, payload))


def _event(config: demo.DemoConfig, event_id: str, text: str) -> dict[str, Any]:
    return build_event(
        shared_root=config.shared_root,
        bridge_root=str(config.shared_root),
        robot_id=config.robot_id,
        event_id=event_id,
        conversation_id="newcomer_acceptance",
        text=text,
        language="zh-TW",
        timestamp_ms=int(time.time() * 1000),
    )


def _abnormal(config: demo.DemoConfig, event_id: str, action_name: str, *, delivered: bool = False) -> dict[str, Any]:
    evidence = config.shared_root / "events" / config.robot_id / event_id / "abnormal.jpg"
    evidence.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence.write_bytes(JPEG_1X1)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "type": "perception.abnormal",
        "event_id": event_id,
        "robot_id": config.robot_id,
        "timestamp_ms": int(time.time() * 1000),
        "observation": {"action_name": action_name, "reason": "newcomer deterministic abnormal test"},
        "evidence": {"frame_paths": [str(evidence)]},
    }
    if delivered:
        payload["notification"] = {"immediate_alert": {"transport": "discord_webhook", "status": "delivered", "target_class": "newcomer_mock"}}
    return payload


def _wait_legacy(capture: Capture, event_id: str) -> dict[str, Any]:
    _, payload = capture.wait_for(lambda topic, item: topic.endswith("/cmd/result") and item.get("schema_version") == "1.0" and item.get("event_id") == event_id)
    return payload


def _post_mock_discord(config: demo.DemoConfig) -> None:
    if config.mock_discord_url is None:
        raise ScenarioFailure("mock Discord endpoint is not configured")
    request = Request(config.mock_discord_url, data=b'{"content":"[TEST] newcomer receipt"}', headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=5) as response:
        if response.status != 204 or response.headers.get("X-Newcomer-Mock") != "discord":
            raise ScenarioFailure("mock Discord did not produce the expected local receipt")


def _media(config: demo.DemoConfig, capture: Capture, event_id: str) -> None:
    for action in ("play_video", "pause_video", "resume_video", "stop_video"):
        response = invoke_media_callback_socket(
            config.callback_socket,
            {
                "event_id": event_id,
                "robot_id": config.robot_id,
                "resident_id": "unknown",
                "action": action,
                "video_id": "elderly_hand_exercise",
            },
        )
        if response.get("status") != "published":
            raise ScenarioFailure(f"media callback rejected {action}: {response}")
        command_id = response.get("command_id")
        capture.wait_for(lambda topic, item, command_id=command_id: topic.endswith("/cmd/result") and item.get("command_id") == command_id)


def _verify_discord_matrix(config: demo.DemoConfig, work_dir: Path) -> dict[str, Any]:
    if config.mock_discord_url is None:
        raise ScenarioFailure("mock Discord endpoint is not configured")
    completed = subprocess.run(
        [str(ROOT / "anomaly_detection" / ".venv" / "bin" / "python"), str(ROOT / "tools" / "mocks" / "verify_discord_delivery.py"), "--endpoint", config.mock_discord_url, "--work-dir", str(work_dir)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=35,
    )
    if completed.returncode:
        raise ScenarioFailure(f"Discord failure matrix failed: {completed.stderr.strip() or completed.stdout.strip()}")
    return json.loads(completed.stdout)


def run(config: demo.DemoConfig, artifacts: Path) -> dict[str, Any]:
    """Execute S1–S10 against already-running isolated lifecycle services."""
    if not config.is_newcomer_mock:
        raise ScenarioFailure("verify_newcomer_mock requires DEMO_PROFILE=newcomer_mock")
    health = demo.runtime_health(config)
    if not health["backend_ready"]:
        raise ScenarioFailure("newcomer lifecycle is not healthy; run scripts/demo start first")
    artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
    capture = Capture(config)
    capture.start()
    results: dict[str, Any] = {}
    try:
        # S1 general ASR -> Bridge -> HTTP resident -> validated speak -> mock Android -> cmd/result.
        s1 = "s1_general"
        capture.publish("asr/final", _event(config, s1, "你好，請說一句測試語音"))
        _wait_legacy(capture, s1)
        results["S1_general_asr_tts"] = "PASS"

        # S2 memory action remains Bridge-owned while Android receives only speak.
        s2 = "s2_reminder"
        capture.publish("asr/final", _event(config, s2, "我吃完早餐後的藥了"))
        _wait_legacy(capture, s2)
        if not (config.memory_dir / "reminders.json").is_file():
            raise ScenarioFailure("reminder completion did not create isolated Bridge memory evidence")
        results["S2_reminder_completion"] = "PASS"

        s3 = "s3_discomfort"
        capture.publish("asr/final", _event(config, s3, "我有點不舒服，頭有點暈"))
        _wait_legacy(capture, s3)
        results["S3_discomfort_care_first"] = "PASS"

        # S4 uses the Bridge's existing consent-first abnormal handler, not the resident double.
        for index, category in enumerate(("falls_down", "lies_on_floor", "fight"), start=1):
            event_id = f"s4_{index}_{category}"
            capture.publish("perception/abnormal", _abnormal(config, event_id, category))
            _wait_legacy(capture, event_id)
            decline_id = f"{event_id}_decline"
            capture.publish("asr/final", _event(config, decline_id, "不用，我沒事"))
            _wait_legacy(capture, decline_id)
        results["S4_abnormal_care_first"] = "PASS"

        # S5 records a real local mock receipt before the existing Bridge follows up.
        _post_mock_discord(config)
        s5 = "s5_affirmative_abnormal"
        capture.publish("perception/abnormal", _abnormal(config, s5, "falls_down", delivered=True))
        _wait_legacy(capture, s5)
        s5_yes = "s5_affirmative_followup"
        capture.publish("asr/final", _event(config, s5_yes, "要，請通知家人"))
        _wait_legacy(capture, s5_yes)
        results["S5_affirmative_notification"] = "PASS"

        s6 = "s6_decline_abnormal"
        capture.publish("perception/abnormal", _abnormal(config, s6, "fight"))
        _wait_legacy(capture, s6)
        s6_no = "s6_decline_followup"
        capture.publish("asr/final", _event(config, s6_no, "不用，我沒事"))
        _wait_legacy(capture, s6_no)
        results["S6_decline"] = "PASS"

        s7 = "s7_ambiguous_abnormal"
        capture.publish("perception/abnormal", _abnormal(config, s7, "lies_on_floor"))
        _wait_legacy(capture, s7)
        for suffix, text in (("once", "嗯"), ("expire", "不確定")):
            followup = f"s7_{suffix}"
            capture.publish("asr/final", _event(config, followup, text))
            _wait_legacy(capture, followup)
        results["S7_ambiguous_timeout"] = "PASS"

        _media(config, capture, "s8_media")
        results["S8_media_v11"] = "PASS"

        results["S9_discord_failure_matrix"] = _verify_discord_matrix(config, artifacts / "discord")

        s10 = "s10_unsupported"
        capture.publish("asr/final", _event(config, s10, "__unsupported_action__"))
        _wait_legacy(capture, s10)
        android_trace = config.runtime_root / "logs" / "mock" / "android-events.jsonl"
        if "unknown_robot_action" in android_trace.read_text(encoding="utf-8"):
            raise ScenarioFailure("unsupported action reached the Android test double")
        results["S10_unsupported_action_defense"] = "PASS"
    finally:
        capture.stop()
    summary = {"status": "PASS", "profile": config.profile, "completed_at": datetime.now(timezone.utc).isoformat(), "results": results}
    (artifacts / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    config = demo.load_config(args.config)
    artifacts = args.artifacts or config.runtime_root / "state" / "newcomer-acceptance"
    try:
        print(json.dumps(run(config, artifacts), ensure_ascii=False, indent=2))
        return 0
    except (ScenarioFailure, demo.DemoError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
