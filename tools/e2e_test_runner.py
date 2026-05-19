#!/usr/bin/env python3
"""Run a local mock E2E test for HermesTemiBridge without robot hardware."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from create_mock_event_images import build_event  # noqa: E402
from hermes_temi_bridge.config import BridgeConfig  # noqa: E402
from hermes_temi_bridge.hermes_client import MockHermesClient  # noqa: E402
from hermes_temi_bridge.idempotency import TTLProcessedEventCache  # noqa: E402
from hermes_temi_bridge.logging_utils import EventJsonlLogger  # noqa: E402
from hermes_temi_bridge.main import HermesTemiBridgeService  # noqa: E402


class InMemoryMqtt:
    """Minimal MQTT test double that records published command payloads."""

    def __init__(self) -> None:
        """Initialize an empty publication list."""
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Record a command publication using the real topic convention."""
        self.published.append((f"temi/{robot_id}/cmd/request", payload))


def assert_true(condition: bool, message: str) -> None:
    """Raise AssertionError with a concise message when condition is false."""
    if not condition:
        raise AssertionError(message)


def run(shared_root: Path, bridge_root: str, hermes_root: str, keep_artifacts: bool) -> dict[str, Any]:
    """Execute the Bridge mock path and return a compact result summary."""
    robot_id = "temi-01"
    event_id = "evt_local_e2e_001"
    now_ms = int(time.time() * 1000)
    payload = build_event(
        shared_root=shared_root,
        bridge_root=bridge_root,
        robot_id=robot_id,
        event_id=event_id,
        conversation_id="conv_local_e2e",
        text="幫我看看桌上的東西是什麼",
        language="zh-TW",
        timestamp_ms=now_ms,
    )

    mqtt = InMemoryMqtt()
    config = BridgeConfig(
        robot_id_allowlist=(robot_id,),
        temi_shared_bridge_path=bridge_root,
        temi_shared_hermes_path=hermes_root,
        hermes_invoke_mode="mock",
        log_dir=(shared_root / "_logs").as_posix(),
    )
    service = HermesTemiBridgeService(
        config=config,
        mqtt_client=mqtt,
        hermes_client=MockHermesClient("這是 Bridge mock 測試"),
        event_cache=TTLProcessedEventCache(600),
        event_logger=EventJsonlLogger(shared_root / "_logs"),
    )

    first = service.handle_asr_payload(f"temi/{robot_id}/asr/final", payload)
    assert_true(first["status"] == "success", f"expected success, got {first}")
    assert_true(len(mqtt.published) == 1, "Bridge did not publish exactly one command")
    topic, command = mqtt.published[0]
    assert_true(topic == f"temi/{robot_id}/cmd/request", f"unexpected publish topic: {topic}")
    assert_true(command["event_id"] == event_id, "command event_id mismatch")
    assert_true(command["actions"][0]["type"] == "speak", "mock command should be speak")

    duplicate = service.handle_asr_payload(f"temi/{robot_id}/asr/final", payload)
    assert_true(duplicate == {"status": "ignored", "reason": "duplicate_event_id"}, "duplicate event was not ignored")
    assert_true(len(mqtt.published) == 1, "duplicate event published another command")

    service.handle_command_result(
        f"temi/{robot_id}/cmd/result",
        {
            "schema_version": "1.0",
            "command_id": command["command_id"],
            "event_id": event_id,
            "robot_id": robot_id,
            "status": "success",
            "results": [{"action_id": "act_001", "type": "speak", "status": "success"}],
            "finished_at_ms": int(time.time() * 1000),
        },
    )

    log_path = shared_root / "_logs" / f"{event_id}.jsonl"
    assert_true(log_path.exists(), "event log was not written")
    if keep_artifacts:
        print(f"artifacts: {shared_root}")

    return {
        "status": "ok",
        "published_topic": topic,
        "command_id": command["command_id"],
        "log_path": log_path.as_posix(),
    }


def main() -> int:
    """Parse CLI arguments and run the local E2E check."""
    parser = argparse.ArgumentParser(description="Run local mock E2E for HermesTemiBridge.")
    parser.add_argument("--shared-root", help="Existing shared root. If omitted, a temporary directory is used.")
    parser.add_argument("--bridge-root", help="Bridge-visible shared root. Defaults to --shared-root.")
    parser.add_argument("--hermes-root", default="/shared/temi")
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()

    if args.shared_root:
        shared_root = Path(args.shared_root).resolve()
        shared_root.mkdir(parents=True, exist_ok=True)
        result = run(shared_root, args.bridge_root or shared_root.as_posix(), args.hermes_root, True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.keep_artifacts:
        shared_root = Path(tempfile.mkdtemp(prefix="temi-e2e-")) / "temi_shared"
        result = run(shared_root, args.bridge_root or shared_root.as_posix(), args.hermes_root, True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        shared_root = Path(tmp) / "temi_shared"
        result = run(shared_root, args.bridge_root or shared_root.as_posix(), args.hermes_root, False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
