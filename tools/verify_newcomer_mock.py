#!/usr/bin/env python3
"""Run the documented newcomer scenarios through the live isolated Bridge.

This runner is deliberately a verifier, not an orchestrator: services must
already be started by ``scripts/demo``.  It publishes only canonical test
events, calls the Bridge-owned media callback, observes canonical command
results, and writes all evidence below the configured external runtime root.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
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
from create_mock_event_images import build_event  # noqa: E402
from hermes_temi_bridge.media_callback_socket import invoke_media_callback_socket  # noqa: E402
from hermes_temi_bridge.memory_store import StructuredMemoryStore  # noqa: E402
from hermes_temi_bridge.abnormal_notification import AbnormalNotificationDispatcher  # noqa: E402


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
        if not bool(getattr(reason_code, "is_failure", reason_code != 0)):
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


def _inject_abnormal(
    config: demo.DemoConfig,
    *,
    event_type: str,
    run_id: str,
    scenario_id: str,
) -> str:
    """Use the documented injector rather than publishing an abnormal event directly."""
    completed = subprocess.run(
        [
            str(ROOT / "scripts" / "inject_demo_event"),
            "--config",
            str(config.config_path),
            "--event",
            event_type,
            "--resident-id",
            "test-resident",
            "--run-id",
            run_id,
            "--scenario-id",
            scenario_id,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScenarioFailure("formal abnormal injector returned invalid JSON") from exc
    event_id = payload.get("event_id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("status") != "published" or not isinstance(event_id, str):
        raise ScenarioFailure(f"formal abnormal injector rejected the event: {payload}")
    return event_id


def _wait_legacy(capture: Capture, event_id: str, *, timeout: float = 12) -> dict[str, Any]:
    _, payload = capture.wait_for(
        lambda topic, item: topic.endswith("/cmd/result")
        and item.get("schema_version") == "1.0"
        and item.get("event_id") == event_id,
        timeout=timeout,
    )
    return payload


def _wait_trace_contains(path: Path, needle: str, *, timeout: float = 8) -> None:
    """Wait for the asynchronous Bridge trace writer to persist one stage."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and needle in path.read_text(encoding="utf-8"):
            return
        time.sleep(0.05)
    raise ScenarioFailure(f"Bridge trace did not record {needle}")


def _wait_command_result_trace(path: Path, command_id: str, *, timeout: float = 8) -> None:
    """Wait until Bridge, rather than only the observer, has consumed a result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload") if isinstance(record, dict) else None
                result = payload.get("command_result") if isinstance(payload, dict) else None
                if record.get("stage") == "command_result_received" and isinstance(result, dict) and result.get("command_id") == command_id:
                    return
        time.sleep(0.05)
    raise ScenarioFailure(f"Bridge did not consume command result {command_id}")


def _seed_reminder(config: demo.DemoConfig) -> None:
    """Seed one synthetic reminder through the public Bridge memory-store API."""
    store = StructuredMemoryStore(config.memory_dir)
    store.seed_synthetic_demo(
        seed_id="newcomer-reminder-fixture-v1",
        profile={"schema_version": "1.0", "display_name": "Synthetic newcomer resident"},
        reminders={"schema_version": "1.0", "reminders": [{"reminder_id": "breakfast-medication", "title": "早餐後用藥", "status": "active", "synthetic": True}]},
        daily_state={"schema_version": "1.0", "active_reminders": ["breakfast-medication"], "synthetic": True},
        events=[],
    )


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
        expected_status = "started" if action == "play_video" else "succeeded"
        capture.wait_for(lambda topic, item, command_id=command_id, expected_status=expected_status: topic.endswith("/cmd/result") and item.get("command_id") == command_id and item.get("status") == expected_status)
        _wait_command_result_trace(config.bridge_log_dir / f"{event_id}.jsonl", str(command_id))


def _verify_discord_matrix(config: demo.DemoConfig, work_dir: Path) -> dict[str, Any]:
    """Exercise the Bridge transport adapter against only the local mock server."""
    if config.mock_discord_url is None:
        raise ScenarioFailure("mock Discord endpoint is not configured")
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    statuses = (204, 401, 403, 404, 429)
    results: dict[str, str] = {}
    for status in statuses:
        credential = work_dir / f"discord-{status}.env"
        credential.write_text(
            f"DISCORD_WEBHOOK_URL={config.mock_discord_url}?status={status}\n",
            encoding="utf-8",
        )
        credential.chmod(0o600)
        bridge_config = replace(
            demo_bridge_config(config),
            abnormal_notification_mode="discord_webhook",
            abnormal_notification_discord_env_path=credential.as_posix(),
        )
        dispatcher = AbnormalNotificationDispatcher(bridge_config)
        receipt = dispatcher.dispatch(
            stage="initial_alert",
            event_id=f"evt-discord-{status}",
            event_type="falls_down",
            robot_id=config.robot_id,
            resident_id="test-resident",
            detected_timestamp_ms=int(time.time() * 1000),
            run_id=None,
            scenario_id=None,
            is_test=False,
        )
        expected = "delivered" if status == 204 else "failed"
        if receipt.get("status") != expected:
            raise ScenarioFailure(f"Bridge Discord adapter did not classify HTTP {status}: {receipt}")
        results[str(status)] = str(receipt.get("failure_code"))
    timeout_credential = work_dir / "discord-timeout.env"
    timeout_credential.write_text(
        f"DISCORD_WEBHOOK_URL={config.mock_discord_url}?delay=2\n",
        encoding="utf-8",
    )
    timeout_credential.chmod(0o600)
    timeout_config = replace(
        demo_bridge_config(config),
        abnormal_notification_mode="discord_webhook",
        abnormal_notification_discord_env_path=timeout_credential.as_posix(),
        abnormal_notification_timeout_seconds=1,
    )
    timeout_receipt = AbnormalNotificationDispatcher(timeout_config).dispatch(
        stage="initial_alert",
        event_id="evt-discord-timeout",
        event_type="falls_down",
        robot_id=config.robot_id,
        resident_id="test-resident",
        detected_timestamp_ms=int(time.time() * 1000),
        run_id=None,
        scenario_id=None,
        is_test=False,
    )
    results["timeout"] = str(timeout_receipt.get("failure_code"))
    connection_credential = work_dir / "discord-connection.env"
    connection_credential.write_text(
        "DISCORD_WEBHOOK_URL=http://127.0.0.1:1/connection-refused\n",
        encoding="utf-8",
    )
    connection_credential.chmod(0o600)
    connection_config = replace(
        demo_bridge_config(config),
        abnormal_notification_mode="discord_webhook",
        abnormal_notification_discord_env_path=connection_credential.as_posix(),
        abnormal_notification_timeout_seconds=1,
    )
    connection_receipt = AbnormalNotificationDispatcher(connection_config).dispatch(
        stage="initial_alert",
        event_id="evt-discord-connection",
        event_type="falls_down",
        robot_id=config.robot_id,
        resident_id="test-resident",
        detected_timestamp_ms=int(time.time() * 1000),
        run_id=None,
        scenario_id=None,
        is_test=False,
    )
    if connection_receipt.get("failure_code") != "DISCORD_CONNECTION_FAILED":
        raise ScenarioFailure(f"Bridge Discord adapter did not classify connection failure: {connection_receipt}")
    results["connection"] = str(connection_receipt.get("failure_code"))
    return results


def demo_bridge_config(config: demo.DemoConfig):
    """Build the minimal BridgeConfig used only by the loopback HTTP matrix."""
    from hermes_temi_bridge.config import BridgeConfig

    return BridgeConfig(
        robot_id_allowlist=(config.robot_id,),
        abnormal_notification_test_recipient_authorized=False,
    )


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
    run_id = f"newcomer-{uuid.uuid4().hex[:12]}"
    try:
        # S1 general ASR -> Bridge -> HTTP resident -> validated speak -> mock Android -> cmd/result.
        s1 = f"{run_id}-s1_general"
        capture.publish("asr/final", _event(config, s1, "你好，請說一句測試語音"))
        _wait_legacy(capture, s1)
        results["S1_general_asr_tts"] = "PASS"

        # S2 memory action remains Bridge-owned while Android receives only speak.
        _seed_reminder(config)
        s2 = f"{run_id}-s2_reminder"
        capture.publish("asr/final", _event(config, s2, "我吃完早餐後的藥了"))
        _wait_legacy(capture, s2)
        reminders = json.loads((config.memory_dir / "reminders.json").read_text(encoding="utf-8"))
        if not any(item.get("reminder_id") == "breakfast-medication" and item.get("status") == "completed" for item in reminders.get("reminders", [])):
            raise ScenarioFailure("reminder completion did not create isolated Bridge memory evidence")
        capture.publish("asr/final", _event(config, s2, "我吃完早餐後的藥了"))
        _wait_trace_contains(config.bridge_log_dir / f"{s2}.jsonl", "duplicate_event_ignored")
        results["S2_reminder_completion"] = "PASS"

        s3 = f"{run_id}-s3_discomfort"
        capture.publish("asr/final", _event(config, s3, "我有點不舒服，頭有點暈"))
        _wait_legacy(capture, s3)
        results["S3_discomfort_care_first"] = "PASS"

        # S4 uses the formal injector for every canonical abnormal category.
        for index, category in enumerate(("falls_down", "lies_on_floor", "fight"), start=1):
            event_id = _inject_abnormal(
                config,
                event_type=category,
                run_id=run_id,
                scenario_id=f"S4{index}",
            )
            _wait_legacy(capture, event_id)
            for suffix in ("okay", "confirmed"):
                response_id = f"{event_id}_{suffix}"
                capture.publish("asr/final", _event(config, response_id, "我沒事"))
                _wait_legacy(capture, response_id)
        results["S4_abnormal_care_first"] = "PASS"

        # S5 reuses the initial Bridge-owned mock receipt for an assistance reply.
        s5 = _inject_abnormal(
            config,
            event_type="falls_down",
            run_id=run_id,
            scenario_id="S5",
        )
        _wait_legacy(capture, s5)
        s5_yes = f"{run_id}-s5_affirmative_followup"
        capture.publish("asr/final", _event(config, s5_yes, "我有點不舒服，需要幫忙"))
        _wait_legacy(capture, s5_yes)
        for suffix in ("okay", "confirmed"):
            response_id = f"{run_id}-s5_{suffix}"
            capture.publish("asr/final", _event(config, response_id, "我沒事"))
            _wait_legacy(capture, response_id)
        results["S5_affirmative_notification"] = "PASS"

        s6 = _inject_abnormal(
            config,
            event_type="fight",
            run_id=run_id,
            scenario_id="S6",
        )
        _wait_legacy(capture, s6)
        for suffix in ("okay", "confirmed"):
            response_id = f"{run_id}-s6_{suffix}"
            capture.publish("asr/final", _event(config, response_id, "不用，我沒事"))
            _wait_legacy(capture, response_id)
        results["S6_decline"] = "PASS"

        s7 = _inject_abnormal(
            config,
            event_type="lies_on_floor",
            run_id=run_id,
            scenario_id="S7",
        )
        _wait_legacy(capture, s7)
        ambiguous = f"{run_id}-s7_ambiguous"
        capture.publish("asr/final", _event(config, ambiguous, "嗯"))
        _wait_legacy(capture, ambiguous)
        _wait_legacy(capture, f"{s7}:follow-up", timeout=30)
        _wait_legacy(capture, f"{s7}:escalation", timeout=30)
        _wait_trace_contains(config.bridge_log_dir / f"{s7}.jsonl", "escalation_notification_finished", timeout=30)
        results["S7_ambiguous_timeout"] = "PASS"

        _media(config, capture, f"{run_id}-s8_media")
        results["S8_media_v11"] = "PASS"

        results["S9_discord_failure_matrix"] = _verify_discord_matrix(config, artifacts / "discord")

        s10 = f"{run_id}-s10_unsupported"
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
    parser.add_argument("--config", help="optional absolute owner-only Demo config path")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    config = demo.load_config(demo.resolve_config_path(args.config))
    artifacts = args.artifacts or config.runtime_root / "state" / "newcomer-acceptance"
    try:
        print(json.dumps(run(config, artifacts), ensure_ascii=False, indent=2))
        return 0
    except (ScenarioFailure, demo.DemoError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
