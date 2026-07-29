"""Synthetic, idempotent care-memory seed for the controlled Demo only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .memory_store import StructuredMemoryStore


DEMO_RESIDENTS = {
    "father": {
        "display_name": "王先生",
        "demo_age": 90,
        "care_context": "高血壓照護",
    },
    "mother": {
        "display_name": "王太太",
        "demo_age": 85,
        "care_context": "血液透析照護",
    },
}
DEMO_SEED_ID = "temiagent_demo_care_seed_v1"


class DemoCareMemoryError(ValueError):
    """Raised when a caller tries to use the synthetic seed unsafely."""


def resident_memory_dir(root: str | Path, resident_id: str) -> Path:
    """Resolve a private partition for a confirmed Demo resident only."""
    if resident_id not in DEMO_RESIDENTS:
        raise DemoCareMemoryError("private_demo_memory_requires_confirmed_resident")
    return Path(root) / resident_id


def seed_demo_care_memory(root: str | Path, *, session_at: datetime | None = None) -> dict[str, Any]:
    """Upsert synthetic Demo records through the Bridge-owned writer.

    The existing StructuredMemoryStore remains the single persistence owner.
    Partitioned directories prevent father/mother retrieval from mixing.  The
    payload is regenerated from the current Demo session date, never a fixed
    real-world date, and repeated invocations replace the same synthetic seed
    instead of appending duplicate events.
    """
    root_path = Path(root)
    if not root_path.is_absolute():
        raise DemoCareMemoryError("demo_care_memory_root_must_be_absolute")
    now = (session_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    results: dict[str, Any] = {"seed_id": DEMO_SEED_ID, "session_at": now.isoformat(), "residents": {}}
    for resident_id in ("father", "mother"):
        store = StructuredMemoryStore(resident_memory_dir(root_path, resident_id))
        result = store.seed_synthetic_demo(
            seed_id=DEMO_SEED_ID,
            profile=_profile(resident_id),
            reminders=_reminders(resident_id),
            daily_state=_daily_state(resident_id, now),
            events=_events(resident_id, now),
        )
        results["residents"][resident_id] = result
    return results


def verify_demo_care_memory(root: str | Path) -> dict[str, Any]:
    """Return a bounded, read-only verification result for the seed layout."""
    root_path = Path(root)
    verification: dict[str, Any] = {"seed_id": DEMO_SEED_ID, "residents": {}}
    for resident_id in ("father", "mother"):
        partition = resident_memory_dir(root_path, resident_id)
        profile = StructuredMemoryStore.read_seed_marker(partition)
        store = StructuredMemoryStore(partition)
        expected = profile.get("seed_id") == DEMO_SEED_ID and profile.get("resident_id") == resident_id
        synthetic_headache = (
            store.find_latest_synthetic_headache(
                seed_id=DEMO_SEED_ID,
                event_id="demo_father_headache_two_days_ago",
            )
            if resident_id == "father"
            else None
        )
        verification["residents"][resident_id] = {
            "status": "ok" if expected and (resident_id != "father" or synthetic_headache is not None) else "missing_or_invalid",
            "path": partition.as_posix(),
            "synthetic_headache_present": synthetic_headache is not None,
        }
    return verification


def _profile(resident_id: str) -> dict[str, Any]:
    resident = DEMO_RESIDENTS[resident_id]
    care_plan: list[str]
    if resident_id == "mother":
        care_plan = [
            "依既定日程提醒血液透析。",
            "洗腎返家後詢問頭暈、明顯疲倦、疼痛、呼吸不適或其他不舒服。",
            "只有本人明確沒有不適且同意時，才可提出低強度手部運動。",
            "鈣片與洗腎配方提醒僅依既定照護計畫；不提供劑量、診斷或治療決策。",
        ]
    else:
        care_plan = [
            "早晚血壓量測提醒；Temi 不自行量測血壓。",
            "手部與腿部運動提醒僅依既定照護計畫。",
            "既定時間的用藥或營養提醒不修改藥物、劑量或療程。",
        ]
    return {
        "user_id": resident_id,
        "preferred_name": resident["display_name"],
        "care_preferences": {"speak_style": "calm", "confirmation_style": "explicit"},
        "demo_metadata": {
            "synthetic": True,
            "seed_id": DEMO_SEED_ID,
            "demo_age": resident["demo_age"],
            "care_context": resident["care_context"],
        },
        "care_plan": care_plan,
    }


def _reminders(resident_id: str) -> dict[str, Any]:
    if resident_id == "mother":
        reminders = [
            {"reminder_id": "mother_dialysis_schedule", "type": "care_plan", "title": "血液透析既定日程提醒", "status": "active", "requires_confirmation": True},
            {"reminder_id": "mother_calcium_plan", "type": "care_plan", "title": "鈣片與洗腎配方既定提醒", "status": "active", "requires_confirmation": True},
        ]
    else:
        reminders = [
            {"reminder_id": "father_bp_morning", "type": "care_plan", "title": "早晨血壓量測提醒", "time": "morning", "status": "active", "requires_confirmation": True},
            {"reminder_id": "father_bp_evening", "type": "care_plan", "title": "晚上血壓量測提醒", "time": "evening", "status": "active", "requires_confirmation": True},
        ]
    return {"schema_version": "1.0", "demo_metadata": {"synthetic": True, "seed_id": DEMO_SEED_ID}, "reminders": reminders}


def _daily_state(resident_id: str, now: datetime) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "user_id": resident_id,
        "date": now.date().isoformat(),
        "risk_state": "Normal",
        "active_reminders": [item["reminder_id"] for item in _reminders(resident_id)["reminders"]],
        "demo_flags": {"synthetic": True, "seed_id": DEMO_SEED_ID},
    }


def _events(resident_id: str, now: datetime) -> list[dict[str, Any]]:
    if resident_id != "father":
        return []
    prior = (now - timedelta(days=2)).replace(hour=17, minute=0, second=0)
    return [
        {
            "event_id": "demo_father_headache_two_days_ago",
            "timestamp": prior.isoformat(),
            "source": "synthetic_demo_seed",
            "asr_text": "王先生回報頭痛。",
            "perception": {"intent": "report_discomfort", "visual_status": "not_available", "image_paths": []},
            "risk": {"home_esi_level": "L3", "reason": "Synthetic Demo history only; ask whether current discomfort is also headache."},
            "reasoning_summary": "Synthetic Demo event. Not a medical record.",
            "actions_taken": ["log_event"],
            "outcome": "Synthetic historical headache report for Demo retrieval.",
            "details": {"synthetic": True, "seed_id": DEMO_SEED_ID, "resident_id": "father"},
        }
    ]
