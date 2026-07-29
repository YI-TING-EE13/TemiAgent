"""Structured demo memory actions for the Temi care assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .action_validator import ValidatedActionOutput


class MemoryActionError(RuntimeError):
    """Raised when a Bridge-internal memory action cannot be completed."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        """Create an error with a machine-readable reason and optional details."""
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class EventContext:
    """Care-memory context derived from the ASR event."""

    asr_text: str
    image_paths: list[str]
    conversation_id: str | None = None


class StructuredMemoryStore:
    """Execute Demo memory actions against JSON / JSONL files."""

    def __init__(self, memory_dir: str | Path):
        """Create a memory store rooted at ``memory_dir``."""
        self.root = Path(memory_dir)

    def execute(
        self,
        output: ValidatedActionOutput,
        context: EventContext,
    ) -> list[dict[str, Any]]:
        """Execute all Bridge-internal memory actions from a validated response."""
        self._ensure_layout()
        results: list[dict[str, Any]] = []
        for action in output.memory_actions:
            action_type = action["type"]
            if action_type == "log_event":
                results.append(self._log_event(output, context, action))
            elif action_type == "mark_reminder_done":
                results.append(self._mark_reminder_done(output, action))
            elif action_type == "notify_caregiver_mock":
                results.append(self._notify_caregiver_mock(output, context, action))
            elif action_type == "generate_summary":
                results.append(self._generate_summary(output, action))
            else:  # pragma: no cover - validator prevents this.
                raise MemoryActionError("unsupported_memory_action", {"type": action_type})
        return results

    def seed_synthetic_demo(
        self,
        *,
        seed_id: str,
        profile: dict[str, Any],
        reminders: dict[str, Any],
        daily_state: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Idempotently replace one explicitly synthetic Demo seed.

        This is a narrow Bridge-owned writer API for a private Demo store.  It
        does not target the default runtime memory directory unless an operator
        explicitly passes it, and it never appends seed events: each call writes
        the same bounded synthetic fixture for the supplied ``seed_id``.
        """
        if not isinstance(seed_id, str) or not seed_id.strip():
            raise MemoryActionError("invalid_demo_seed_id")
        if not isinstance(profile, dict) or not isinstance(reminders, dict) or not isinstance(daily_state, dict):
            raise MemoryActionError("invalid_demo_seed_payload")
        if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
            raise MemoryActionError("invalid_demo_seed_events")
        self._ensure_layout()
        marker = {"synthetic": True, "seed_id": seed_id.strip()}
        profile_payload = dict(profile)
        profile_payload["demo_seed"] = marker
        reminders_payload = dict(reminders)
        reminders_payload["demo_seed"] = marker
        daily_payload = dict(daily_state)
        daily_payload["demo_seed"] = marker
        event_lines = []
        for event in events:
            seeded_event = dict(event)
            details = dict(seeded_event.get("details") or {})
            details.update(marker)
            seeded_event["details"] = details
            event_lines.append(json.dumps(seeded_event, ensure_ascii=False, separators=(",", ":")))

        self._write_json(self.root / "profile.json", profile_payload)
        self._write_json(self.root / "reminders.json", reminders_payload)
        self._write_json(self.root / "daily_state.json", daily_payload)
        (self.root / "event_log.jsonl").write_text(
            "\n".join(event_lines) + ("\n" if event_lines else ""),
            encoding="utf-8",
        )
        return {
            "status": "seeded",
            "seed_id": seed_id.strip(),
            "memory_dir": self.root.as_posix(),
            "event_count": len(events),
        }

    @staticmethod
    def read_seed_marker(memory_dir: str | Path) -> dict[str, Any]:
        """Read the narrow seed marker without constructing a writer."""
        path = Path(memory_dir) / "profile.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        marker = payload.get("demo_seed")
        if not isinstance(marker, dict):
            return {}
        return {
            "seed_id": marker.get("seed_id"),
            "resident_id": payload.get("user_id"),
        }

    def find_latest_synthetic_headache(self, *, seed_id: str, event_id: str) -> dict[str, Any] | None:
        """Read one bounded synthetic headache record for the controlled Demo.

        This is deliberately narrower than a general event search: callers
        cannot query arbitrary residents, dates, fields, or free text.  The
        partition has already been selected by the Bridge before this API is
        constructed.
        """
        if not isinstance(seed_id, str) or not seed_id.strip():
            raise MemoryActionError("invalid_demo_seed_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise MemoryActionError("invalid_demo_seed_event_id")
        candidates = [
            item
            for item in self._read_event_log()
            if item.get("event_id") == event_id
            and item.get("source") == "synthetic_demo_seed"
            and isinstance(item.get("details"), dict)
            and item["details"].get("synthetic") is True
            and item["details"].get("seed_id") == seed_id
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: str(item.get("timestamp") or ""))
        return {
            "event_id": latest["event_id"],
            "timestamp": latest.get("timestamp"),
            "asr_text": latest.get("asr_text"),
        }

    def record_repeated_discomfort(
        self,
        *,
        event_id: str,
        conversation_id: str | None,
        asr_text: str,
        prior_event_id: str,
        systolic: int,
        diastolic: int,
    ) -> dict[str, Any]:
        """Append the post-confirmation Demo observation through the memory API.

        The method records user-provided numbers only.  It intentionally makes
        no clinical interpretation, diagnosis, measurement claim, or alert.
        """
        if not isinstance(event_id, str) or not event_id.strip():
            raise MemoryActionError("invalid_repeated_discomfort_event_id")
        if not isinstance(asr_text, str) or not asr_text.strip():
            raise MemoryActionError("invalid_repeated_discomfort_asr_text")
        if not isinstance(prior_event_id, str) or not prior_event_id.strip():
            raise MemoryActionError("invalid_repeated_discomfort_prior_event")
        if isinstance(systolic, bool) or isinstance(diastolic, bool):
            raise MemoryActionError("invalid_blood_pressure")
        if not isinstance(systolic, int) or not isinstance(diastolic, int):
            raise MemoryActionError("invalid_blood_pressure")
        if not (70 <= systolic <= 250 and 40 <= diastolic <= 150 and systolic > diastolic):
            raise MemoryActionError("invalid_blood_pressure")
        self._ensure_layout()
        if any(item.get("event_id") == event_id for item in self._read_event_log()):
            raise MemoryActionError("duplicate_memory_event_id", {"event_id": event_id})
        entry = {
            "event_id": event_id,
            "timestamp": _now_iso(),
            "source": "hermes_temi_bridge",
            "conversation_id": conversation_id,
            "asr_text": asr_text,
            "perception": {"intent": "repeated_discomfort_blood_pressure", "visual_status": "not_available", "image_paths": []},
            "risk": {"home_esi_level": "Normal", "reason": "Demo-only user-provided record; no clinical assessment was made."},
            "reasoning_summary": "Controlled Demo repeated-discomfort record after explicit confirmation.",
            "actions_taken": ["log_event"],
            "outcome": "Recorded user-provided blood-pressure values for the controlled Demo.",
            "details": {
                "demo": {"flow": "repeated_discomfort", "prior_event_id": prior_event_id},
                "blood_pressure": {"systolic": systolic, "diastolic": diastolic, "unit": "mmHg", "source": "user_reported"},
            },
        }
        log_path = self.root / "event_log.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._update_daily_recent_event(event_id)
        return {"status": "success", "event_id": event_id, "prior_event_id": prior_event_id, "path": log_path.as_posix()}

    def _ensure_layout(self) -> None:
        """Create memory directories expected by the Demo."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "abnormal_events").mkdir(exist_ok=True)
        (self.root / "summaries").mkdir(exist_ok=True)

    def _log_event(
        self,
        output: ValidatedActionOutput,
        context: EventContext,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Append one care event to event_log.jsonl."""
        entry = self._event_entry(output, context, action)
        log_path = self.root / "event_log.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._update_daily_recent_event(output.event_id)
        return {
            "action_id": action["action_id"],
            "type": "log_event",
            "status": "success",
            "path": log_path.as_posix(),
        }

    def _event_entry(
        self,
        output: ValidatedActionOutput,
        context: EventContext,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the canonical event log entry for a memory action."""
        cognitive_state = output.cognitive_state
        return {
            "event_id": output.event_id,
            "timestamp": _now_iso(),
            "source": "hermes_temi_bridge",
            "conversation_id": context.conversation_id,
            "asr_text": context.asr_text,
            "perception": {
                "intent": cognitive_state.get("intent") or action.get("event_type"),
                "visual_status": "image_paths_available" if context.image_paths else "not_available",
                "image_paths": context.image_paths,
            },
            "risk": {
                "home_esi_level": cognitive_state["home_esi_level"],
                "reason": cognitive_state["risk_reason"],
            },
            "reasoning_summary": output.reasoning_summary,
            "actions_taken": [item["type"] for item in output.actions],
            "outcome": action.get("outcome") or cognitive_state.get("next_step") or "recorded",
            "details": action.get("details") or {},
        }

    def _mark_reminder_done(
        self,
        output: ValidatedActionOutput,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Mark one reminder as completed."""
        reminders_path = self.root / "reminders.json"
        data = self._read_json(reminders_path, default={"schema_version": "1.0", "reminders": []})
        reminders = data.get("reminders")
        if not isinstance(reminders, list):
            raise MemoryActionError("invalid_reminders_file", {"path": reminders_path.as_posix()})

        reminder_id = action["reminder_id"]
        completed_at = action.get("completed_at") or _now_iso()
        for reminder in reminders:
            if isinstance(reminder, dict) and reminder.get("reminder_id") == reminder_id:
                reminder["status"] = "completed"
                reminder["last_completed_at"] = completed_at
                self._write_json(reminders_path, data)
                self._update_daily_after_reminder(output.event_id, reminder_id)
                return {
                    "action_id": action["action_id"],
                    "type": "mark_reminder_done",
                    "status": "success",
                    "reminder_id": reminder_id,
                }

        raise MemoryActionError("reminder_not_found", {"reminder_id": reminder_id})

    def _notify_caregiver_mock(
        self,
        output: ValidatedActionOutput,
        context: EventContext,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Write a demo-only caregiver notification artifact."""
        path = self.root / "abnormal_events" / f"{_safe_filename(output.event_id)}.json"
        payload = {
            "schema_version": "1.0",
            "event_id": output.event_id,
            "timestamp": _now_iso(),
            "home_esi_level": output.cognitive_state["home_esi_level"],
            "risk_reason": output.cognitive_state["risk_reason"],
            "evidence": {
                "asr_text": context.asr_text,
                "image_paths": context.image_paths,
            },
            "actions_taken": [item["type"] for item in output.actions],
            "notification": {
                "type": "demo_mock",
                "target": action["target"],
                "message": action.get("message") or output.cognitive_state["risk_reason"],
                "status": "mock_sent",
            },
        }
        self._write_json(path, payload)
        self._set_daily_flag("caregiver_mock_notified", True)
        return {
            "action_id": action["action_id"],
            "type": "notify_caregiver_mock",
            "status": "success",
            "path": path.as_posix(),
        }

    def _generate_summary(
        self,
        output: ValidatedActionOutput,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a compact Markdown daily summary from the JSONL event log."""
        date = action.get("date") or _today()
        events = self._read_event_log()
        matching = [event for event in events if str(event.get("timestamp", "")).startswith(date)]
        high_risk = [
            event for event in matching if (event.get("risk") or {}).get("home_esi_level") == "L1"
        ]
        reminders_done = [
            event for event in matching if "mark_reminder_done" in event.get("actions_taken", [])
        ]
        path = self.root / "summaries" / f"{date}.md"
        lines = [
            f"# {date} 照護摘要",
            "",
            f"- 今日事件：{len(matching)} 筆。",
            f"- 提醒完成：{len(reminders_done)} 筆。",
            f"- 高風險事件：{len(high_risk)} 筆。",
            f"- 最新風險狀態：{output.cognitive_state['home_esi_level']}。",
            "- 備註：本摘要為第一年度 Demo 產生，不取代正式醫療判斷。",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        self._set_daily_flag("summary_generated", True)
        return {
            "action_id": action["action_id"],
            "type": "generate_summary",
            "status": "success",
            "path": path.as_posix(),
        }

    def _read_event_log(self) -> list[dict[str, Any]]:
        """Read event_log.jsonl, ignoring blank lines."""
        path = self.root / "event_log.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    events.append(parsed)
        return events

    def _update_daily_recent_event(self, event_id: str) -> None:
        """Add an event id to daily_state.recent_event_ids."""
        daily_path = self.root / "daily_state.json"
        daily = self._read_json(daily_path, default={"schema_version": "1.0"})
        recent = daily.setdefault("recent_event_ids", [])
        if isinstance(recent, list) and event_id not in recent:
            recent.append(event_id)
        risk_state = daily.setdefault("demo_flags", {})
        if isinstance(risk_state, dict):
            risk_state.setdefault("summary_generated", False)
        self._write_json(daily_path, daily)

    def _update_daily_after_reminder(self, event_id: str, reminder_id: str) -> None:
        """Update daily state after completing a reminder."""
        daily_path = self.root / "daily_state.json"
        daily = self._read_json(daily_path, default={"schema_version": "1.0"})
        active = daily.get("active_reminders")
        if isinstance(active, list) and reminder_id in active:
            active.remove(reminder_id)
        recent = daily.setdefault("recent_event_ids", [])
        if isinstance(recent, list) and event_id not in recent:
            recent.append(event_id)
        daily["last_interaction"] = f"Reminder completed: {reminder_id}"
        self._write_json(daily_path, daily)

    def _set_daily_flag(self, name: str, value: Any) -> None:
        """Set one flag in daily_state.demo_flags."""
        daily_path = self.root / "daily_state.json"
        daily = self._read_json(daily_path, default={"schema_version": "1.0"})
        flags = daily.setdefault("demo_flags", {})
        if isinstance(flags, dict):
            flags[name] = value
        self._write_json(daily_path, daily)

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        """Read a JSON object or return a copy of ``default``."""
        if not path.exists():
            return dict(default)
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise MemoryActionError("invalid_json_object", {"path": path.as_posix()})
        return parsed

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        """Write a stable UTF-8 JSON object."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    """Return an ISO timestamp for memory records."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _today() -> str:
    """Return today's UTC date."""
    return datetime.now(UTC).date().isoformat()


def _safe_filename(value: str) -> str:
    """Return a filesystem-safe filename stem."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
