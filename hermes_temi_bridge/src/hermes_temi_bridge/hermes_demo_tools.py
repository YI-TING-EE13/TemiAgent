"""Bridge-owned callbacks for root resident Demo native tools."""

from __future__ import annotations

from typing import Any, Callable

from .demo_identity import DemoIdentityController
from .demo_repeated_discomfort import DemoRepeatedDiscomfortController


def _valid_context(payload: dict[str, Any], *, require_resident: bool) -> tuple[str, str] | None:
    event_id = payload.get("event_id")
    robot_id = payload.get("robot_id")
    if not isinstance(event_id, str) or not event_id.strip() or not isinstance(robot_id, str) or not robot_id.strip():
        return None
    if require_resident and payload.get("resident_id") != "father":
        return None
    return event_id, robot_id


class HermesDemoIdentityToolCallback:
    """Validate a tiny operator-tool surface before calling the controller."""

    def __init__(self, controller: DemoIdentityController, *, allowed_robot_ids: tuple[str, ...]) -> None:
        self._controller = controller
        self._allowed_robot_ids = set(allowed_robot_ids)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_INVALID_PAYLOAD"}
        action = payload.get("action")
        required = {"action", "event_id", "robot_id"}
        if action == "start_demo_identity":
            required.add("identity_status")
        if set(payload) != required:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_INVALID_FIELDS"}
        context = _valid_context(payload, require_resident=False)
        if context is None:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_INVALID_CONTEXT"}
        event_id, robot_id = context
        if robot_id not in self._allowed_robot_ids:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_ROBOT_NOT_ALLOWED"}
        if action == "start_demo_identity":
            return self._controller.start(str(payload.get("identity_status")), trigger_event_id=event_id)
        if action == "stop_demo_identity":
            return self._controller.stop(trigger_event_id=event_id)
        if action == "get_demo_identity_status":
            return self._controller.status()
        return {"status": "rejected", "error_code": "DEMO_IDENTITY_CALLBACK_ACTION_NOT_ALLOWED"}


class HermesRepeatedDiscomfortToolCallback:
    """Validate father-only native tool calls before isolated memory access."""

    def __init__(
        self,
        controller: DemoRepeatedDiscomfortController,
        *,
        allowed_robot_ids: tuple[str, ...],
        trace_callback: Callable[[str, str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._controller = controller
        self._allowed_robot_ids = set(allowed_robot_ids)
        self._trace_callback = trace_callback

    def _trace(self, action: str, event_id: str, robot_id: str, result: dict[str, Any]) -> None:
        if self._trace_callback is not None:
            self._trace_callback(action, event_id, robot_id, result)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_INVALID_PAYLOAD"}
        action = payload.get("action")
        required = {"action", "event_id", "robot_id", "resident_id"}
        if action == "record_repeated_blood_pressure":
            required.update({"systolic", "diastolic", "asr_text"})
        if set(payload) != required:
            return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_INVALID_FIELDS"}
        context = _valid_context(payload, require_resident=True)
        if context is None:
            return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_FATHER_IDENTITY_REQUIRED"}
        event_id, robot_id = context
        if robot_id not in self._allowed_robot_ids:
            return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_ROBOT_NOT_ALLOWED"}
        if action == "retrieve_repeated_discomfort":
            result = self._controller.retrieve(robot_id=robot_id)
        elif action == "confirm_repeated_headache":
            result = self._controller.confirm(robot_id=robot_id)
        elif action == "record_repeated_blood_pressure":
            systolic = payload.get("systolic")
            diastolic = payload.get("diastolic")
            asr_text = payload.get("asr_text")
            if isinstance(systolic, bool) or isinstance(diastolic, bool) or not isinstance(systolic, int) or not isinstance(diastolic, int) or not isinstance(asr_text, str):
                return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_INVALID_BLOOD_PRESSURE"}
            result = self._controller.record(
                robot_id=robot_id,
                event_id=event_id,
                asr_text=asr_text,
                systolic=systolic,
                diastolic=diastolic,
            )
        else:
            return {"status": "rejected", "error_code": "DEMO_CARE_CALLBACK_ACTION_NOT_ALLOWED"}
        self._trace(str(action), event_id, robot_id, result)
        return result
