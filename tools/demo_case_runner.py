#!/usr/bin/env python3
"""Run deterministic first-year care Demo cases through HermesTemiBridge.

The runner does not call a real model or robot. It exercises the canonical Bridge
path with fixed Hermes JSON outputs and writes inspectable artifacts for the
three first-year Demo scenarios:

- daily reminder confirmation
- L2 discomfort / help request
- L1 possible fall / mock caregiver notification
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from create_mock_event_images import build_event  # noqa: E402
from hermes_temi_bridge.config import BridgeConfig  # noqa: E402
from hermes_temi_bridge.hermes_client import HermesRequest, HermesResponse, parse_hermes_output  # noqa: E402
from hermes_temi_bridge.idempotency import TTLProcessedEventCache  # noqa: E402
from hermes_temi_bridge.logging_utils import EventJsonlLogger  # noqa: E402
from hermes_temi_bridge.main import HermesTemiBridgeService  # noqa: E402
from hermes_temi_bridge.memory_store import StructuredMemoryStore  # noqa: E402


ROBOT_ID = "temi-01"
LANGUAGE = "zh-TW"


@dataclass(frozen=True)
class DemoCase:
    """One deterministic Demo case."""

    case_id: str
    event_id: str
    asr_text: str
    hermes_output: dict[str, Any]


class InMemoryMqtt:
    """MQTT test double that records command publications."""

    def __init__(self) -> None:
        """Initialize an empty publication list."""
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Record a command publication using the real topic convention."""
        self.published.append((f"temi/{robot_id}/cmd/request", payload))


class StaticHermesClient:
    """Hermes stand-in that returns fixed outputs keyed by event id."""

    def __init__(self, outputs: dict[str, dict[str, Any]]):
        """Store static Hermes outputs."""
        self.outputs = outputs
        self.raw_outputs: dict[str, str] = {}

    def invoke(self, request: HermesRequest) -> HermesResponse:
        """Return the configured output for this event."""
        payload = self.outputs[request.event_id]
        raw_output = json.dumps(payload, ensure_ascii=False, indent=2)
        self.raw_outputs[request.event_id] = raw_output
        return HermesResponse(raw_output=raw_output, latency_ms=0)


def build_cases() -> list[DemoCase]:
    """Return the three first-year Demo cases."""
    return [
        DemoCase(
            case_id="daily_reminder",
            event_id="evt_demo_daily_reminder_001",
            asr_text="我吃完藥了",
            hermes_output={
                "schema_version": "1.0",
                "event_id": "evt_demo_daily_reminder_001",
                "robot_id": ROBOT_ID,
                "confidence": 0.93,
                "cognitive_state": {
                    "intent": "care_reminder_confirmation",
                    "home_esi_level": "L3",
                    "risk_reason": "使用者確認完成日常服藥提醒，屬於低風險照護紀錄。",
                    "memory_updates": ["reminders", "event_log", "daily_state"],
                    "next_step": "mark_reminder_done",
                },
                "reasoning_summary": "王先生確認已完成早餐後服藥，需要回覆並更新提醒狀態。",
                "actions": [
                    {
                        "action_id": "act_001",
                        "type": "speak",
                        "text": "好的，王先生，我已經幫您記錄早餐後服藥完成。",
                        "language": LANGUAGE,
                    },
                    {
                        "action_id": "act_002",
                        "type": "mark_reminder_done",
                        "reminder_id": "rem_morning_medication",
                    },
                    {
                        "action_id": "act_003",
                        "type": "log_event",
                        "event_type": "care_reminder",
                        "outcome": "reminder_completed",
                    },
                ],
            },
        ),
        DemoCase(
            case_id="discomfort_l2",
            event_id="evt_demo_discomfort_l2_001",
            asr_text="我有點不舒服",
            hermes_output={
                "schema_version": "1.0",
                "event_id": "evt_demo_discomfort_l2_001",
                "robot_id": ROBOT_ID,
                "confidence": 0.87,
                "cognitive_state": {
                    "intent": "possible_help_request",
                    "home_esi_level": "L2",
                    "risk_reason": "使用者主動表示不舒服，但目前沒有明確跌倒或無回應證據，需要先追問。",
                    "memory_updates": ["event_log", "daily_state"],
                    "next_step": "ask_clarification",
                },
                "reasoning_summary": "使用者表示不舒服，應以中風險關懷流程追問症狀並記錄事件。",
                "actions": [
                    {
                        "action_id": "act_001",
                        "type": "ask_clarification",
                        "text": "王先生，您是哪裡不舒服？會頭暈、胸悶，還是剛剛有跌倒嗎？",
                        "language": LANGUAGE,
                    },
                    {
                        "action_id": "act_002",
                        "type": "log_event",
                        "event_type": "possible_distress",
                        "outcome": "waiting_for_user_response",
                    },
                ],
            },
        ),
        DemoCase(
            case_id="possible_fall_l1",
            event_id="evt_demo_possible_fall_l1_001",
            asr_text="救命，我跌倒了",
            hermes_output={
                "schema_version": "1.0",
                "event_id": "evt_demo_possible_fall_l1_001",
                "robot_id": ROBOT_ID,
                "confidence": 0.91,
                "cognitive_state": {
                    "intent": "emergency_candidate",
                    "home_esi_level": "L1",
                    "risk_reason": "使用者明確表示跌倒並求救，Demo 中應進入高風險確認與 mock 通知流程。",
                    "memory_updates": ["event_log", "abnormal_events", "summary"],
                    "next_step": "notify_caregiver_mock",
                },
                "reasoning_summary": "疑似跌倒且有明確求救語句，需要先語音確認並進行 Demo mock caregiver notification。",
                "actions": [
                    {
                        "action_id": "act_001",
                        "type": "ask_clarification",
                        "text": "王先生，我聽到您說跌倒了。請您先不要勉強移動，我會先幫您做模擬通知家屬。",
                        "language": LANGUAGE,
                    },
                    {
                        "action_id": "act_002",
                        "type": "notify_caregiver_mock",
                        "target": "caregiver_demo_primary",
                        "message": "Demo mock：王先生疑似跌倒並求救，請家屬確認狀況。",
                    },
                    {
                        "action_id": "act_003",
                        "type": "log_event",
                        "event_type": "emergency_candidate",
                        "outcome": "caregiver_mock_notified",
                    },
                    {
                        "action_id": "act_004",
                        "type": "generate_summary",
                    },
                ],
            },
        ),
    ]


def prepare_memory(seed_memory: Path, target_memory: Path) -> None:
    """Copy seed memory to an isolated artifact memory directory."""
    if target_memory.exists():
        shutil.rmtree(target_memory)
    shutil.copytree(seed_memory, target_memory)


def run_case(
    *,
    case: DemoCase,
    service: HermesTemiBridgeService,
    mqtt: InMemoryMqtt,
    static_client: StaticHermesClient,
    shared_root: Path,
    bridge_root: str,
    case_dir: Path,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run one case through the Bridge and write case artifacts."""
    case_dir.mkdir(parents=True, exist_ok=True)
    before_publish_count = len(mqtt.published)
    payload = build_event(
        shared_root=shared_root,
        bridge_root=bridge_root,
        robot_id=ROBOT_ID,
        event_id=case.event_id,
        conversation_id=f"conv_{case.case_id}",
        text=case.asr_text,
        language=LANGUAGE,
        timestamp_ms=timestamp_ms,
    )
    write_json(case_dir / "input_event.json", payload)

    result = service.handle_asr_payload(f"temi/{ROBOT_ID}/asr/final", payload)
    write_json(case_dir / "bridge_result.json", result)

    raw_output = static_client.raw_outputs[case.event_id]
    (case_dir / "hermes_raw_output.json").write_text(raw_output + "\n", encoding="utf-8")
    parsed_output = parse_hermes_output(raw_output)
    write_json(case_dir / "parsed_output.json", parsed_output)

    command_payload = None
    command_topic = None
    if len(mqtt.published) > before_publish_count:
        command_topic, command_payload = mqtt.published[-1]
        write_json(case_dir / "command_request.json", {"topic": command_topic, "payload": command_payload})
        command_result = build_command_result(command_payload)
        write_json(case_dir / "command_result.json", command_result)
        service.handle_command_result(f"temi/{ROBOT_ID}/cmd/result", command_result)

    memory_state = snapshot_memory(service.config.memory_dir)
    write_json(case_dir / "memory_state_after.json", memory_state)

    return {
        "case_id": case.case_id,
        "event_id": case.event_id,
        "status": result["status"],
        "command_topic": command_topic,
        "command_id": command_payload.get("command_id") if command_payload else None,
        "memory_action_results": result.get("memory_action_results", []),
        "artifact_dir": case_dir.as_posix(),
    }


def build_command_result(command: dict[str, Any]) -> dict[str, Any]:
    """Build a successful command result for the simulated Temi app."""
    return {
        "schema_version": "1.0",
        "command_id": command["command_id"],
        "event_id": command["event_id"],
        "robot_id": command["robot_id"],
        "status": "success",
        "results": [
            {"action_id": action["action_id"], "type": action["type"], "status": "success"}
            for action in command.get("actions", [])
        ],
        "finished_at_ms": int(time.time() * 1000),
    }


def snapshot_memory(memory_dir: str | Path) -> dict[str, Any]:
    """Return a compact memory state snapshot for artifacts."""
    root = Path(memory_dir)
    event_log_path = root / "event_log.jsonl"
    event_log_entries = []
    if event_log_path.exists():
        event_log_entries = [
            json.loads(line) for line in event_log_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    return {
        "profile": read_json(root / "profile.json"),
        "daily_state": read_json(root / "daily_state.json"),
        "reminders": read_json(root / "reminders.json"),
        "event_log_count": len(event_log_entries),
        "event_log_tail": event_log_entries[-3:],
        "abnormal_events": sorted(path.name for path in (root / "abnormal_events").glob("*.json")),
        "summaries": sorted(path.name for path in (root / "summaries").glob("*.md") if path.name != "README.md"),
    }


def read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON object if it exists."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write a UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(output_dir: Path, seed_memory: Path, keep_artifacts: bool) -> dict[str, Any]:
    """Run all Demo cases and return a compact summary."""
    artifact_root = output_dir.resolve()
    shared_root = artifact_root / "temi_shared"
    memory_root = artifact_root / "memory"
    bridge_log_root = artifact_root / "bridge_logs"
    prepare_memory(seed_memory, memory_root)

    cases = build_cases()
    static_client = StaticHermesClient({case.event_id: case.hermes_output for case in cases})
    mqtt = InMemoryMqtt()
    config = BridgeConfig(
        robot_id_allowlist=(ROBOT_ID,),
        temi_shared_bridge_path=shared_root.as_posix(),
        temi_shared_hermes_path=shared_root.as_posix(),
        hermes_invoke_mode="mock",
        log_dir=bridge_log_root.as_posix(),
        memory_dir=memory_root.as_posix(),
        max_actions_per_event=6,
    )
    service = HermesTemiBridgeService(
        config=config,
        mqtt_client=mqtt,
        hermes_client=static_client,
        event_cache=TTLProcessedEventCache(600),
        event_logger=EventJsonlLogger(bridge_log_root),
        memory_store=StructuredMemoryStore(memory_root),
    )

    timestamp_ms = int(time.time() * 1000)
    case_results = []
    for index, case in enumerate(cases):
        case_results.append(
            run_case(
                case=case,
                service=service,
                mqtt=mqtt,
                static_client=static_client,
                shared_root=shared_root,
                bridge_root=shared_root.as_posix(),
                case_dir=artifact_root / "cases" / case.case_id,
                timestamp_ms=timestamp_ms + (index * 1000),
            )
        )

    summary = {
        "status": "ok",
        "artifact_root": artifact_root.as_posix(),
        "case_results": case_results,
        "final_memory_state": snapshot_memory(memory_root),
    }
    write_json(artifact_root / "run_summary.json", summary)
    if keep_artifacts:
        print(f"artifacts: {artifact_root}")
    return summary


def main() -> int:
    """Parse CLI arguments and run the Demo cases."""
    parser = argparse.ArgumentParser(description="Run deterministic first-year Temi care Demo cases.")
    parser.add_argument("--output-dir", help="Artifact directory. Defaults to a temporary directory.")
    parser.add_argument("--seed-memory", default=(ROOT / "memory").as_posix())
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()

    seed_memory = Path(args.seed_memory).resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = run(output_dir, seed_memory, True)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.keep_artifacts:
        output_dir = Path(tempfile.mkdtemp(prefix="temi-demo-cases-"))
        summary = run(output_dir, seed_memory, True)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="temi-demo-cases-") as tmp:
        summary = run(Path(tmp), seed_memory, False)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
