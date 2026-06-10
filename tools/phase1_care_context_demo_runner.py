#!/usr/bin/env python3
"""Run deterministic Phase 1 CareContext demo validation cases.

This runner is demo-safe: it uses temporary structured memory, fake image
files, mock Hermes output, and an in-memory MQTT recorder. It exercises the
real HermesTemiBridgeService, CareContextBuilder, action validation, and
StructuredMemoryStore paths without contacting a live broker or robot.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from create_mock_event_images import JPEG_1X1, build_event  # noqa: E402
from hermes_temi_bridge.care_context_builder import CareContextBuilder  # noqa: E402
from hermes_temi_bridge.config import BridgeConfig  # noqa: E402
from hermes_temi_bridge.hermes_client import HermesRequest, HermesResponse, build_prompt  # noqa: E402
from hermes_temi_bridge.idempotency import TTLProcessedEventCache  # noqa: E402
from hermes_temi_bridge.logging_utils import EventJsonlLogger  # noqa: E402
from hermes_temi_bridge.main import HermesTemiBridgeService  # noqa: E402
from hermes_temi_bridge.memory_store import StructuredMemoryStore  # noqa: E402

ROBOT_ID = "temi-01"
LANGUAGE = "zh-TW"
TEMP_PREFIX = "phase1-live-validation-"
ROBOT_ACTION_TYPES = {"speak", "ask_clarification", "turn", "navigate", "stop", "noop"}


class InMemoryMqtt:
    """MQTT test double that records command publications without network I/O."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Record a command publication using the real topic convention."""
        self.published.append((f"temi/{robot_id}/cmd/request", payload))


class ScenarioHermesClient:
    """Deterministic Hermes stand-in for Phase 1 memory-read scenarios."""

    def __init__(self) -> None:
        self.requests: list[HermesRequest] = []
        self.prompts: list[str] = []
        self.outputs: list[dict[str, Any]] = []

    def invoke(self, request: HermesRequest) -> HermesResponse:
        """Build the prompt, capture it, and return deterministic JSON."""
        self.requests.append(request)
        self.prompts.append(build_prompt(request))
        output = self._output_for(request)
        self.outputs.append(output)
        return HermesResponse(raw_output=json.dumps(output, ensure_ascii=False), latency_ms=0)

    def _output_for(self, request: HermesRequest) -> dict[str, Any]:
        text = request.asr_text or ""
        relevant_events = (request.care_context or {}).get("relevant_events", [])
        prior_l2 = next((event for event in relevant_events if event.get("home_esi_level") == "L2"), None)

        if request.source_type == "perception.abnormal":
            return self._make_output(
                request,
                level="L1",
                intent="abnormal_visual_event",
                risk_reason="abnormal route validation fixture; no hardware dispatch required.",
                actions=[
                    {
                        "action_id": "act_001",
                        "type": "log_event",
                        "event_type": "abnormal_visual_event",
                        "summary": "abnormal route care_context validation",
                        "outcome": "validated_in_demo_safe_mode",
                    }
                ],
            )

        if "吃" in text and "藥" in text:
            return self._make_output(
                request,
                level="L3",
                intent="medication_confirmation",
                risk_reason="使用者表示已完成服藥，屬於低風險提醒確認。",
                actions=[
                    {
                        "action_id": "act_001",
                        "type": "speak",
                        "text": "好的，我幫你記錄已經吃過藥了。",
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
                        "event_type": "medication_confirmation",
                        "summary": "使用者確認已吃過藥",
                        "outcome": "reminder_completed",
                    },
                ],
            )

        if "又" in text and "不舒服" in text and prior_l2:
            prior_id = str(prior_l2["event_id"])
            return self._make_output(
                request,
                level="L2",
                intent="repeated_discomfort",
                risk_reason=f"使用者再次表示不舒服，且 care_context 中有前一次 L2 事件 {prior_id}，需要追問症狀。",
                actions=[
                    {
                        "action_id": "act_001",
                        "type": "ask_clarification",
                        "text": "你又不舒服了，請問是頭暈、胸悶、疼痛，還是哪裡不舒服？",
                        "language": LANGUAGE,
                    },
                    {
                        "action_id": "act_002",
                        "type": "log_event",
                        "event_type": "health_report",
                        "summary": f"使用者再次表示不舒服，參考前次事件 {prior_id}",
                        "outcome": "waiting_for_user_response",
                    },
                ],
            )

        if "不舒服" in text:
            return self._make_output(
                request,
                level="L2",
                intent="first_discomfort",
                risk_reason="使用者表示不舒服，但尚無更明確症狀，需要追問。",
                actions=[
                    {
                        "action_id": "act_001",
                        "type": "ask_clarification",
                        "text": "你哪裡不舒服？有頭暈、胸悶或疼痛嗎？",
                        "language": LANGUAGE,
                    },
                    {
                        "action_id": "act_002",
                        "type": "log_event",
                        "event_type": "health_report",
                        "summary": "使用者表示不舒服，需追問症狀",
                        "outcome": "waiting_for_user_response",
                    },
                ],
            )

        return self._make_output(
            request,
            level="Normal",
            intent="validation_fallback",
            risk_reason="validation fallback",
            actions=[{"action_id": "act_001", "type": "noop"}],
        )

    def _make_output(
        self,
        request: HermesRequest,
        *,
        level: str,
        intent: str,
        risk_reason: str,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "event_id": request.event_id,
            "robot_id": request.robot_id,
            "confidence": 0.9,
            "cognitive_state": {
                "intent": intent,
                "home_esi_level": level,
                "risk_reason": risk_reason,
                "next_step": "execute_validated_actions",
            },
            "reasoning_summary": risk_reason,
            "actions": actions,
        }


def write_json(path: Path, payload: Any) -> None:
    """Write a UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object."""
    return json.loads(path.read_text(encoding="utf-8"))


def read_event_log(path: Path) -> list[dict[str, Any]]:
    """Read JSONL event log entries."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def seed_memory(memory_root: Path) -> None:
    """Create isolated Phase 1 seed memory under the temporary workspace."""
    memory_root.mkdir(parents=True, exist_ok=True)
    write_json(
        memory_root / "profile.json",
        {
            "schema_version": "1.0",
            "user_id": "elder_demo_001",
            "preferred_name": "王先生",
            "gender": "male",
            "language": "zh-TW",
            "care_preferences": {"speak_style": "溫和、簡短、清楚"},
        },
    )
    write_json(
        memory_root / "reminders.json",
        {
            "schema_version": "1.0",
            "user_id": "elder_demo_001",
            "reminders": [
                {
                    "reminder_id": "rem_morning_medication",
                    "type": "medication",
                    "title": "早餐後服藥",
                    "time": "08:30",
                    "instruction": "早餐後服用高血壓藥",
                    "status": "active",
                    "requires_confirmation": True,
                    "last_completed_at": None,
                },
                {
                    "reminder_id": "rem_hydration",
                    "type": "hydration",
                    "title": "補充水分",
                    "time": "10:30",
                    "instruction": "提醒王先生喝水",
                    "status": "active",
                    "requires_confirmation": True,
                    "last_completed_at": None,
                },
            ],
        },
    )
    write_json(
        memory_root / "daily_state.json",
        {
            "schema_version": "1.0",
            "date": "2026-06-10",
            "user_id": "elder_demo_001",
            "risk_state": "normal",
            "active_reminders": ["rem_morning_medication", "rem_hydration"],
            "recent_event_ids": [],
            "demo_flags": {"home_esi_level": "Normal"},
        },
    )
    (memory_root / "event_log.jsonl").write_text("", encoding="utf-8")


def build_asr_payload(shared_root: Path, *, event_id: str, text: str, timestamp_ms: int) -> dict[str, Any]:
    """Build one ASR final payload with tiny fake JPEG files."""
    return build_event(
        shared_root=shared_root,
        bridge_root=shared_root.as_posix(),
        robot_id=ROBOT_ID,
        event_id=event_id,
        conversation_id=f"conv_{event_id}",
        text=text,
        language=LANGUAGE,
        timestamp_ms=timestamp_ms,
    )


def build_abnormal_payload(shared_root: Path, *, event_id: str, timestamp_ms: int) -> dict[str, Any]:
    """Build one abnormal perception payload with fake JPEG evidence paths."""
    frame_paths = []
    event_dir = shared_root / "abnormal_events" / ROBOT_ID / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    for index in range(8):
        path = event_dir / f"frame_{index:03d}.jpg"
        path.write_bytes(JPEG_1X1)
        frame_paths.append(path.as_posix())
    payload = {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": ROBOT_ID,
        "type": "perception.abnormal",
        "timestamp_ms": timestamp_ms,
        "observation": {
            "action_name": "fall_like_motion",
            "reason": "Person appears to lose balance across evidence frames.",
        },
        "evidence": {"frame_paths": frame_paths},
        "context": {"source": "phase1_care_context_demo_runner"},
    }
    write_json(event_dir / "metadata.json", payload)
    return payload


def create_service(root: Path) -> tuple[HermesTemiBridgeService, ScenarioHermesClient, InMemoryMqtt]:
    """Create the Bridge service with mock Hermes and mock MQTT."""
    shared_root = root / "temi_shared"
    memory_root = root / "memory"
    log_root = root / "logs"
    seed_memory(memory_root)
    hermes = ScenarioHermesClient()
    mqtt = InMemoryMqtt()
    config = BridgeConfig(
        robot_id_allowlist=(ROBOT_ID,),
        temi_shared_bridge_path=shared_root.as_posix(),
        temi_shared_hermes_path=shared_root.as_posix(),
        hermes_invoke_mode="mock",
        log_dir=log_root.as_posix(),
        memory_dir=memory_root.as_posix(),
        care_context_enabled=True,
        care_context_max_events=5,
        care_context_max_chars=4000,
        max_actions_per_event=6,
    )
    service = HermesTemiBridgeService(
        config=config,
        mqtt_client=mqtt,
        hermes_client=hermes,
        event_cache=TTLProcessedEventCache(600),
        event_logger=EventJsonlLogger(log_root),
        memory_store=StructuredMemoryStore(memory_root),
    )
    return service, hermes, mqtt


def assert_item(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    """Create an assertion report item."""
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def case_status(assertions: list[dict[str, Any]]) -> str:
    """Return PASS only when every assertion passed."""
    return "PASS" if all(item["status"] == "PASS" for item in assertions) else "FAIL"


def compact_care_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Return a bounded care_context excerpt for reports."""
    context = context or {}
    return {
        "event": context.get("event"),
        "resident": context.get("resident"),
        "active_reminders": context.get("active_reminders", [])[:3],
        "daily_state": context.get("daily_state"),
        "relevant_events": context.get("relevant_events", [])[:5],
        "read_status": context.get("read_status"),
    }


def compact_hermes_output(output: dict[str, Any]) -> dict[str, Any]:
    """Return the Hermes output fields that matter for this demo."""
    return {
        "event_id": output.get("event_id"),
        "cognitive_state": output.get("cognitive_state"),
        "actions": output.get("actions", []),
    }


def prompt_separation_excerpt(prompt: str) -> dict[str, Any]:
    """Report whether care_context and current ASR text are separate prompt blocks."""
    care_start = prompt.find("<care_context>")
    care_end = prompt.find("</care_context>")
    asr_start = prompt.find("Current user ASR text:")
    return {
        "has_care_context_block": care_start != -1 and care_end != -1,
        "has_current_asr_block": asr_start != -1,
        "care_context_before_asr": care_start != -1 and care_end != -1 and asr_start != -1 and care_end < asr_start,
        "excerpt": (prompt[care_start : min(care_start + 700, len(prompt))] if care_start != -1 else prompt[:700]),
        "current_user_asr_excerpt": (prompt[asr_start : asr_start + 80] if asr_start != -1 else ""),
    }


def run_asr_case(
    service: HermesTemiBridgeService,
    root: Path,
    *,
    event_id: str,
    text: str,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run one ASR payload through the Bridge."""
    payload = build_asr_payload(root / "temi_shared", event_id=event_id, text=text, timestamp_ms=timestamp_ms)
    result = service.handle_asr_payload(f"temi/{ROBOT_ID}/asr/final", payload)
    return {"payload": payload, "result": result}


def scenario_report(
    *,
    name: str,
    status: str,
    input_payload: Any,
    care_context: dict[str, Any] | None,
    hermes_output: dict[str, Any],
    memory_result: dict[str, Any],
    assertions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one JSON scenario report."""
    return {
        "name": name,
        "status": status,
        "input": input_payload,
        "care_context_excerpt": compact_care_context(care_context),
        "hermes_output_excerpt": compact_hermes_output(hermes_output),
        "memory_result_excerpt": memory_result,
        "assertions": assertions,
    }


def run_case1(
    service: HermesTemiBridgeService,
    hermes: ScenarioHermesClient,
    root: Path,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run first discomfort case."""
    run = run_asr_case(service, root, event_id="evt_live_discomfort_001", text="我不舒服", timestamp_ms=timestamp_ms)
    request = hermes.requests[-1]
    output = hermes.outputs[-1]
    event_log = read_event_log(root / "memory" / "event_log.jsonl")
    tail = event_log[-1] if event_log else {}
    active_ids = {item.get("reminder_id") for item in (request.care_context or {}).get("active_reminders", [])}
    assertions = [
        assert_item("resident_display_name", (request.care_context or {}).get("resident", {}).get("display_name") == "王先生"),
        assert_item(
            "active_reminders_include_medication_and_hydration",
            {"rem_morning_medication", "rem_hydration"}.issubset(active_ids),
            sorted(active_ids),
        ),
        assert_item("relevant_events_initially_empty", (request.care_context or {}).get("relevant_events") == []),
        assert_item("hermes_level_l2", output.get("cognitive_state", {}).get("home_esi_level") == "L2"),
        assert_item("hermes_actions_include_log_event", any(action.get("type") == "log_event" for action in output.get("actions", []))),
        assert_item("event_log_contains_first_event", tail.get("event_id") == "evt_live_discomfort_001", tail.get("event_id")),
        assert_item("event_risk_is_l2", tail.get("risk", {}).get("home_esi_level") == "L2", tail.get("risk")),
    ]
    return scenario_report(
        name="case1_first_discomfort",
        status=case_status(assertions),
        input_payload="我不舒服",
        care_context=request.care_context,
        hermes_output=output,
        memory_result={"bridge_result": run["result"], "event_log_tail": tail},
        assertions=assertions,
    )


def run_case2(
    service: HermesTemiBridgeService,
    hermes: ScenarioHermesClient,
    root: Path,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run repeated discomfort recall case."""
    run = run_asr_case(service, root, event_id="evt_live_discomfort_002", text="我又不舒服", timestamp_ms=timestamp_ms)
    request = hermes.requests[-1]
    output = hermes.outputs[-1]
    prompt_info = prompt_separation_excerpt(hermes.prompts[-1])
    relevant_events = (request.care_context or {}).get("relevant_events", [])
    prior = next((event for event in relevant_events if event.get("event_id") == "evt_live_discomfort_001"), None)
    match_reasons = set(prior.get("match_reasons", [])) if prior else set()
    risk_reason = output.get("cognitive_state", {}).get("risk_reason", "")
    assertions = [
        assert_item("care_context_contains_prior_l2_event", prior is not None, relevant_events),
        assert_item(
            "match_reasons_include_health_discomfort",
            bool({"current_intent:health_discomfort", "keyword:health_discomfort"} & match_reasons),
            sorted(match_reasons),
        ),
        assert_item("prompt_has_care_context_block", prompt_info["has_care_context_block"]),
        assert_item(
            "prompt_has_current_user_asr_separate",
            prompt_info["has_current_asr_block"] and prompt_info["care_context_before_asr"],
            prompt_info,
        ),
        assert_item("risk_reason_cites_prior_event_id", "evt_live_discomfort_001" in risk_reason, risk_reason),
    ]
    report = scenario_report(
        name="case2_repeated_discomfort",
        status=case_status(assertions),
        input_payload="我又不舒服",
        care_context=request.care_context,
        hermes_output=output,
        memory_result={"bridge_result": run["result"], "prior_event_id": prior.get("event_id") if prior else None},
        assertions=assertions,
    )
    report["hermes_output_excerpt"]["prompt_separation"] = prompt_info
    return report


def run_case3(
    service: HermesTemiBridgeService,
    hermes: ScenarioHermesClient,
    root: Path,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run medication reminder completion case."""
    memory_root = root / "memory"
    initial_reminders = read_json(memory_root / "reminders.json")["reminders"]
    run = run_asr_case(service, root, event_id="evt_live_medication_001", text="我吃過藥了", timestamp_ms=timestamp_ms)
    request = hermes.requests[-1]
    output = hermes.outputs[-1]
    updated_reminders = read_json(memory_root / "reminders.json")["reminders"]
    next_context = CareContextBuilder(memory_root).build_for_event(
        event_id="evt_live_next_turn_001",
        robot_id=ROBOT_ID,
        source="asr.final",
        asr_text="下一輪檢查",
        image_paths=[],
    )
    pre_active_ids = {item.get("reminder_id") for item in (request.care_context or {}).get("active_reminders", [])}
    updated_by_id = {item.get("reminder_id"): item for item in updated_reminders}
    next_active_ids = {item.get("reminder_id") for item in next_context.get("active_reminders", [])}
    memory_actions = [action for action in output.get("actions", []) if action.get("type") not in ROBOT_ACTION_TYPES]
    assertions = [
        assert_item("pre_context_includes_medication_reminder", "rem_morning_medication" in pre_active_ids, sorted(pre_active_ids)),
        assert_item(
            "hermes_actions_include_mark_reminder_done",
            any(action.get("type") == "mark_reminder_done" and action.get("reminder_id") == "rem_morning_medication" for action in memory_actions),
            memory_actions,
        ),
        assert_item(
            "medication_reminder_completed",
            updated_by_id.get("rem_morning_medication", {}).get("status") == "completed",
            updated_by_id.get("rem_morning_medication"),
        ),
        assert_item(
            "last_completed_at_present",
            bool(updated_by_id.get("rem_morning_medication", {}).get("last_completed_at")),
            updated_by_id.get("rem_morning_medication"),
        ),
        assert_item("hydration_remains_active", updated_by_id.get("rem_hydration", {}).get("status") == "active", updated_by_id.get("rem_hydration")),
        assert_item("next_turn_excludes_medication_reminder", "rem_morning_medication" not in next_active_ids, sorted(next_active_ids)),
    ]
    report = scenario_report(
        name="case3_medication_reminder_done",
        status=case_status(assertions),
        input_payload="我吃過藥了",
        care_context=request.care_context,
        hermes_output=output,
        memory_result={
            "bridge_result": run["result"],
            "initial_reminders": initial_reminders,
            "updated_reminders": updated_reminders,
            "next_turn_active_reminders": next_context.get("active_reminders", []),
        },
        assertions=assertions,
    )
    report["hermes_output_excerpt"]["memory_actions"] = memory_actions
    return report


def run_case4(
    service: HermesTemiBridgeService,
    hermes: ScenarioHermesClient,
    mqtt: InMemoryMqtt,
    root: Path,
    timestamp_ms: int,
) -> dict[str, Any]:
    """Run abnormal route care_context case."""
    published_before = len(mqtt.published)
    payload = build_abnormal_payload(root / "temi_shared", event_id="evt_live_abnormal_001", timestamp_ms=timestamp_ms)
    result = service.handle_abnormal_payload(f"temi/{ROBOT_ID}/perception/abnormal", payload)
    request = hermes.requests[-1]
    output = hermes.outputs[-1]
    context = request.care_context or {}
    evidence_paths = payload.get("evidence", {}).get("frame_paths", [])
    published_after = len(mqtt.published)
    assertions = [
        assert_item("care_context_source_is_perception_abnormal", context.get("event", {}).get("source") == "perception.abnormal", context.get("event")),
        assert_item("resident_present", bool(context.get("resident", {}).get("display_name")), context.get("resident")),
        assert_item("daily_state_present", bool(context.get("daily_state")), context.get("daily_state")),
        assert_item("active_reminders_field_present", isinstance(context.get("active_reminders"), list), context.get("active_reminders")),
        assert_item("prior_events_available_if_selected", isinstance(context.get("relevant_events"), list), context.get("relevant_events")),
        assert_item("evidence_uses_file_paths_only", all(isinstance(path, str) and not path.startswith("data:") for path in evidence_paths), evidence_paths[:2]),
        assert_item("mock_mqtt_no_abnormal_robot_command", published_after == published_before, {"before": published_before, "after": published_after}),
        assert_item("bridge_result_success", result.get("status") == "success", result),
    ]
    return scenario_report(
        name="case4_abnormal_route_care_context",
        status=case_status(assertions),
        input_payload={
            "source": payload.get("type"),
            "action_name": payload.get("observation", {}).get("action_name"),
            "frame_path_count": len(evidence_paths),
        },
        care_context=request.care_context,
        hermes_output=output,
        memory_result={"bridge_result": result, "evidence_paths_are_paths_only": True},
        assertions=assertions,
    )


def run_demo(artifact_root: Path) -> dict[str, Any]:
    """Run all Phase 1 scenarios and return the report."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    service, hermes, mqtt = create_service(artifact_root)
    timestamp_ms = int(time.time() * 1000)
    cases = [
        run_case1(service, hermes, artifact_root, timestamp_ms),
        run_case2(service, hermes, artifact_root, timestamp_ms + 1000),
        run_case3(service, hermes, artifact_root, timestamp_ms + 2000),
        run_case4(service, hermes, mqtt, artifact_root, timestamp_ms + 3000),
    ]
    report = {
        "overall_status": "PASS" if all(case["status"] == "PASS" for case in cases) else "FAIL",
        "artifact_root": artifact_root.as_posix(),
        "mock_hermes": True,
        "mock_mqtt": True,
        "production_memory_used": False,
        "cases": cases,
    }
    write_json(artifact_root / "phase1_care_context_demo_report.json", report)
    return report


def print_human_summary(report: dict[str, Any], *, artifact_retained: bool) -> None:
    """Print the compact required human-readable summary."""
    print(f"PHASE1_DEMO_STATUS={report['overall_status']}")
    print(f"artifact_root={report['artifact_root']}")
    print(f"artifact_retained={'true' if artifact_retained else 'false'}")
    for index, case in enumerate(report["cases"], start=1):
        print(f"case{index}={case['status']}")
    print("mock_hermes=true")
    print("mock_mqtt=true")
    print("production_memory_used=false")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run deterministic Phase 1 CareContext demo validation.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report instead of a short summary.")
    parser.add_argument("--output", help="Write the full JSON report to this path.")
    parser.add_argument("--keep-artifacts", action="store_true", help="Keep the temporary workspace for inspection.")
    return parser.parse_args()


def main() -> int:
    """Run the Phase 1 demo package."""
    args = parse_args()
    artifact_root = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
    keep_artifacts = bool(args.keep_artifacts)
    try:
        report = run_demo(artifact_root)
        report["artifact_retained"] = keep_artifacts
        if args.output:
            write_json(Path(args.output).resolve(), report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_human_summary(report, artifact_retained=keep_artifacts)
        return 0 if report["overall_status"] == "PASS" else 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
