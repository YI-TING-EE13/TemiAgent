"""Bounded repeated-discomfort retrieval and write flow for the synthetic Demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .demo_care_memory import DEMO_SEED_ID, resident_memory_dir
from .memory_store import MemoryActionError, StructuredMemoryStore
from .resident_context import ActiveResident


_HEADACHE_EVENT_ID = "demo_father_headache_two_days_ago"


@dataclass(frozen=True)
class _PendingFlow:
    prior_event_id: str
    stage: str


class DemoRepeatedDiscomfortController:
    """Keep one in-memory father-only flow; clear it on resident changes."""

    def __init__(
        self,
        *,
        memory_root: str | Path,
        active_resident: Callable[[str], ActiveResident],
    ) -> None:
        self.memory_root = Path(memory_root)
        self._active_resident = active_resident
        self._pending: dict[str, _PendingFlow] = {}
        self._last_resident: dict[str, str] = {}

    def identity_changed(self, robot_id: str, resident: ActiveResident) -> None:
        """Invalidate a pending confirmation whenever resident scope changes."""
        previous = self._last_resident.get(robot_id)
        if previous is not None and previous != resident.resident_id:
            self._pending.pop(robot_id, None)
        if resident.resident_id != "father":
            self._pending.pop(robot_id, None)
        self._last_resident[robot_id] = resident.resident_id

    def retrieve(self, *, robot_id: str) -> dict[str, Any]:
        """Retrieve only the seed's exact father headache event."""
        rejected = self._require_father(robot_id)
        if rejected is not None:
            return rejected
        store = self._father_store()
        prior = store.find_latest_synthetic_headache(seed_id=DEMO_SEED_ID, event_id=_HEADACHE_EVENT_ID)
        if prior is None:
            return {"status": "rejected", "error_code": "DEMO_PRIOR_HEADACHE_NOT_FOUND"}
        self._pending[robot_id] = _PendingFlow(prior_event_id=prior["event_id"], stage="await_confirmation")
        return {"status": "retrieved", "prior_event": prior, "next_step": "await_confirmation"}

    def confirm(self, *, robot_id: str) -> dict[str, Any]:
        """Advance only an existing father flow to user-provided BP capture."""
        rejected = self._require_father(robot_id)
        if rejected is not None:
            return rejected
        pending = self._pending.get(robot_id)
        if pending is None or pending.stage != "await_confirmation":
            return {"status": "rejected", "error_code": "DEMO_REPEATED_DISCOMFORT_CONFIRMATION_NOT_PENDING"}
        self._pending[robot_id] = _PendingFlow(prior_event_id=pending.prior_event_id, stage="await_blood_pressure")
        return {"status": "confirmed", "next_step": "await_blood_pressure"}

    def record(
        self,
        *,
        robot_id: str,
        event_id: str,
        asr_text: str,
        systolic: int,
        diastolic: int,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Write only after confirmation and only when the memory API succeeds."""
        rejected = self._require_father(robot_id)
        if rejected is not None:
            return rejected
        pending = self._pending.get(robot_id)
        if pending is None or pending.stage != "await_blood_pressure":
            return {"status": "rejected", "error_code": "DEMO_BLOOD_PRESSURE_NOT_PENDING"}
        try:
            recorded = self._father_store().record_repeated_discomfort(
                event_id=event_id,
                conversation_id=conversation_id,
                asr_text=asr_text,
                prior_event_id=pending.prior_event_id,
                systolic=systolic,
                diastolic=diastolic,
            )
        except MemoryActionError as exc:
            return {"status": "rejected", "error_code": exc.reason}
        self._pending.pop(robot_id, None)
        return {**recorded, "status": "recorded"}

    def _require_father(self, robot_id: str) -> dict[str, Any] | None:
        resident = self._active_resident(robot_id)
        self.identity_changed(robot_id, resident)
        if resident.resident_id != "father":
            return {"status": "rejected", "error_code": "DEMO_FATHER_IDENTITY_REQUIRED"}
        return None

    def _father_store(self) -> StructuredMemoryStore:
        return StructuredMemoryStore(resident_memory_dir(self.memory_root, "father"))
