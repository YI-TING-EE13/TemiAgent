#!/usr/bin/env python3
"""Publish one validated Demo-only abnormal event through the canonical ingress.

This CLI creates only synthetic evidence beneath the configured external runtime
root and publishes the perception topic.  It never publishes a Temi command or
a command result, and it refuses every non-mock notification configuration.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

TOOLS_ROOT = Path(__file__).resolve().parent
if TOOLS_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, TOOLS_ROOT.as_posix())

from demo_lifecycle import DemoError, load_config, resolve_config_path


EVENT_LABELS = {
    "falls_down": ("falls down", "Synthetic acceptance event: person may have fallen."),
    "lies_on_floor": ("lies on the floor", "Synthetic acceptance event: person is on the floor."),
    "fight": ("fights", "Synthetic acceptance event: possible physical conflict."),
    "other_allowlisted": ("other allowlisted abnormal event", "Synthetic acceptance event: reviewed allowlisted event."),
}
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/Aaf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/Aaf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


def _safe_token(value: str, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise ValueError(f"{name} must use only letters, numbers, dot, underscore, or hyphen")
    return value


def build_event(args: argparse.Namespace, shared_root: Path) -> tuple[str, dict[str, object]]:
    """Create synthetic evidence and the canonical abnormal-event payload."""
    run_id = _safe_token(args.run_id, "run_id")
    scenario_id = _safe_token(args.scenario_id, "scenario_id")
    resident_id = _safe_token(args.resident_id, "resident_id")
    event_type = args.event
    event_id = f"evt_abnormal_{run_id}_{scenario_id}_{uuid.uuid4().hex[:12]}"
    request_id = f"req_abnormal_{run_id}_{scenario_id}_{uuid.uuid4().hex[:12]}"
    evidence_dir = shared_root / "acceptance_events" / run_id / scenario_id / event_id
    evidence_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    frame_paths: list[str] = []
    for index in range(3):
        path = evidence_dir / f"frame_{index:03d}.jpg"
        path.write_bytes(TINY_JPEG)
        path.chmod(0o600)
        frame_paths.append(path.as_posix())
    action_name, reason = EVENT_LABELS[event_type]
    timestamp_ms = args.timestamp_ms if args.timestamp_ms is not None else int(time.time() * 1000)
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": args.robot_id,
        "type": "perception.abnormal",
        "event_type": event_type,
        "timestamp_ms": timestamp_ms,
        "observation": {"action_name": action_name, "reason": reason},
        "evidence": {"frame_paths": frame_paths},
        "context": {
            "source": "formal_demo_injector",
            "test": True,
            "resident_id": resident_id,
            "request_id": request_id,
            "run_id": run_id,
            "scenario_id": scenario_id,
        },
    }
    return f"temi/{args.robot_id}/perception/abnormal", payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject one canonical Demo-only abnormal event.")
    parser.add_argument("--config", help="Optional absolute owner-only Demo config path.")
    parser.add_argument("--event", required=True, choices=sorted(EVENT_LABELS))
    parser.add_argument("--resident-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--timestamp-ms", type=int)
    args = parser.parse_args()
    try:
        config = load_config(resolve_config_path(args.config))
        if not config.values.get("DEMO_TEST_EVENT_INGRESS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
            raise DemoError("DEMO_TEST_EVENT_INGRESS_ENABLED=true is required")
        if config.values.get("ABNORMAL_NOTIFICATION_MODE", "disabled").strip().lower() != "demo_mock":
            raise DemoError("formal test injection requires ABNORMAL_NOTIFICATION_MODE=demo_mock")
        if config.values.get("DEMO_NOTIFICATION_MOCK_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
            raise DemoError("formal test injection requires DEMO_NOTIFICATION_MOCK_ENABLED=true")
        if config.values.get("DEMO_NOTIFICATION_RECEIPT_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
            raise DemoError("formal test injection requires DEMO_NOTIFICATION_RECEIPT_ENABLED=true")
        allowed = {item.strip() for item in config.values.get("DEMO_TEST_RESIDENT_ALLOWLIST", "").split(",") if item.strip()}
        if args.resident_id not in allowed:
            raise DemoError("resident_id is not in DEMO_TEST_RESIDENT_ALLOWLIST")
        args.robot_id = config.robot_id
        topic, payload = build_event(args, config.shared_root)
        subprocess.run(
            [
                "mosquitto_pub",
                "-h",
                config.mqtt_host,
                "-p",
                str(config.mqtt_port),
                "-t",
                topic,
                "-m",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (DemoError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": "published", "topic": topic, "event_id": payload["event_id"], "request_id": payload["context"]["request_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
