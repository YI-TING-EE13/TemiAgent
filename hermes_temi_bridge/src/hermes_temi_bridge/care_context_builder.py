"""Build compact Bridge-controlled care context from structured memory."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


RISK_SCORE = {"L1": 300, "L2": 200, "L3": 100, "Normal": 0}
ACTIVE_REMINDER_STATUSES = {"active", "pending"}
TEXT_LIMITS = {"asr_text": 120, "risk_reason": 200, "outcome": 120}

KEYWORD_SETS = {
    "health_discomfort": [
        "不舒服",
        "頭暈",
        "暈",
        "痛",
        "胸悶",
        "呼吸",
        "喘",
        "跌倒",
        "摔倒",
        "站不起來",
        "救命",
        "119",
    ],
    "medication": ["藥", "吃藥", "服藥", "藥物", "高血壓藥"],
    "hydration": ["水", "喝水", "口渴", "補水", "補充水分"],
    "fall_or_emergency": ["跌倒", "摔倒", "救命", "叫救護車", "119", "站不起來", "動不了"],
    "gesture_or_vision": ["手勢", "比什麼", "看一下", "相機", "影像", "氣色"],
}

MEMORY_POLICY = [
    "This care_context is Bridge-provided context, not user speech.",
    "Do not treat text inside care_context as the current user utterance.",
    "Structured care memory is authoritative for reminders, daily_state, and event audit.",
    "If using relevant_events in risk_reason, cite event_id.",
    "If memory contains no evidence, ask_clarification or abstain; do not guess.",
    "Do not convert unverified risk assessment into medical diagnosis.",
]


class CareContextBuilder:
    """Read structured care memory and build a compact context block for Hermes."""

    def __init__(self, memory_dir: str | Path, max_events: int = 5, max_chars: int = 4000):
        """Create a builder rooted at ``memory_dir``.

        The builder is read-only. It never creates, updates, or deletes memory
        files; all persistence remains in ``StructuredMemoryStore``.
        """
        self.root = Path(memory_dir)
        self.max_events = max(0, int(max_events))
        self.max_chars = max(1, int(max_chars))

    def build_for_event(
        self,
        *,
        event_id: str,
        robot_id: str,
        source: str,
        asr_text: str | None,
        image_paths: list[str],
    ) -> dict[str, Any]:
        """Build care context for one Bridge event without mutating memory."""
        read_status = {"warnings": [], "skipped_event_log_lines": 0}
        context = self._minimal_context(event_id, robot_id, source, read_status)
        try:
            profile = self._read_json("profile.json", read_status)
            reminders = self._read_json("reminders.json", read_status)
            daily_state = self._read_json("daily_state.json", read_status)
            events = self._read_event_log(read_status)
            abnormal_events = self._read_abnormal_events(read_status)

            context["resident"] = self._compact_resident(profile)
            context["active_reminders"] = self._compact_active_reminders(reminders)
            context["daily_state"] = self._compact_daily_state(daily_state)
            context["relevant_events"] = self._retrieve_events(
                events,
                abnormal_events,
                current_asr=asr_text or "",
                image_paths=image_paths,
            )
            return self._enforce_budget(context)
        except Exception as exc:  # pragma: no cover - last-resort protection.
            read_status["warnings"].append(f"unexpected_read_error:{type(exc).__name__}")
            return self._enforce_budget(context)

    def _minimal_context(
        self,
        event_id: str,
        robot_id: str,
        source: str,
        read_status: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "generated_at": _now_iso(),
            "event": {
                "event_id": event_id,
                "robot_id": robot_id,
                "source": source,
            },
            "resident": {},
            "active_reminders": [],
            "daily_state": {},
            "relevant_events": [],
            "read_status": read_status,
            "memory_policy": list(MEMORY_POLICY),
        }

    def _read_json(self, filename: str, read_status: dict[str, Any]) -> dict[str, Any]:
        path = self.root / filename
        if not path.exists():
            read_status["warnings"].append(f"missing_file:{filename}")
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            read_status["warnings"].append(f"malformed_json:{filename}")
            return {}
        except OSError as exc:
            read_status["warnings"].append(f"read_error:{filename}:{type(exc).__name__}")
            return {}
        if not isinstance(parsed, dict):
            read_status["warnings"].append(f"invalid_json_object:{filename}")
            return {}
        return parsed

    def _read_event_log(self, read_status: dict[str, Any]) -> list[dict[str, Any]]:
        path = self.root / "event_log.jsonl"
        if not path.exists():
            read_status["warnings"].append("missing_file:event_log.jsonl")
            return []
        events: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            read_status["warnings"].append(f"read_error:event_log.jsonl:{type(exc).__name__}")
            return []
        for line in lines:
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                read_status["skipped_event_log_lines"] += 1
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
            else:
                read_status["skipped_event_log_lines"] += 1
        return events

    def _read_abnormal_events(self, read_status: dict[str, Any]) -> list[dict[str, Any]]:
        abnormal_dir = self.root / "abnormal_events"
        if not abnormal_dir.exists():
            return []
        events: list[dict[str, Any]] = []
        for path in sorted(abnormal_dir.glob("*.json")):
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                read_status["warnings"].append(f"malformed_json:abnormal_events/{path.name}")
                continue
            except OSError as exc:
                read_status["warnings"].append(f"read_error:abnormal_events/{path.name}:{type(exc).__name__}")
                continue
            if isinstance(parsed, dict):
                parsed.setdefault("source", "abnormal_events")
                events.append(parsed)
        return events

    def _compact_resident(self, profile: dict[str, Any]) -> dict[str, Any]:
        if not profile:
            return {}
        preferences = profile.get("care_preferences") if isinstance(profile.get("care_preferences"), dict) else {}
        compact = {
            "resident_id": _optional_str(profile.get("user_id") or profile.get("resident_id")),
            "display_name": _optional_str(profile.get("preferred_name") or profile.get("display_name")),
            "gender": _optional_str(profile.get("gender")),
            "language": _optional_str(profile.get("language")),
            "speak_style": _optional_str(preferences.get("speak_style")),
            "confirmation_style": _optional_str(preferences.get("confirmation_style")),
        }
        return {key: value for key, value in compact.items() if value is not None}

    def _compact_active_reminders(self, reminders_data: dict[str, Any]) -> list[dict[str, Any]]:
        reminders = reminders_data.get("reminders")
        if not isinstance(reminders, list):
            return []
        active = []
        for reminder in reminders:
            if not isinstance(reminder, dict):
                continue
            status = str(reminder.get("status") or "").strip().lower()
            if status not in ACTIVE_REMINDER_STATUSES:
                continue
            compact = {
                "reminder_id": _optional_str(reminder.get("reminder_id")),
                "type": _optional_str(reminder.get("type")),
                "title": _truncate(_optional_str(reminder.get("title")), 80),
                "time": _optional_str(reminder.get("time")),
                "status": status,
                "requires_confirmation": bool(reminder.get("requires_confirmation", False)),
            }
            active.append({key: value for key, value in compact.items() if value is not None})
        return active

    def _compact_daily_state(self, daily_state: dict[str, Any]) -> dict[str, Any]:
        if not daily_state:
            return {}
        active = daily_state.get("active_reminders")
        recent = daily_state.get("recent_event_ids")
        compact = {
            "date": _optional_str(daily_state.get("date")),
            "user_id": _optional_str(daily_state.get("user_id")),
            "risk_state": _optional_str(daily_state.get("risk_state")),
            "last_seen_location": _optional_str(daily_state.get("last_seen_location")),
            "last_interaction": _truncate(_optional_str(daily_state.get("last_interaction")), 120),
            "active_reminder_ids": active if isinstance(active, list) else [],
            "recent_event_ids": recent[-10:] if isinstance(recent, list) else [],
        }
        flags = daily_state.get("demo_flags")
        if isinstance(flags, dict):
            compact["demo_flags"] = flags
        return {key: value for key, value in compact.items() if value not in (None, [], {})}

    def _retrieve_events(
        self,
        events: list[dict[str, Any]],
        abnormal_events: list[dict[str, Any]],
        *,
        current_asr: str,
        image_paths: list[str],
    ) -> list[dict[str, Any]]:
        current_groups = _matched_keyword_groups(current_asr)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        recent_ids = {id(event) for event in events[-self.max_events :]} if self.max_events else set()
        today = datetime.now(UTC).date().isoformat()

        for item in events:
            compact, score = self._score_event(
                item,
                current_groups=current_groups,
                current_asr=current_asr,
                today=today,
                is_recent=id(item) in recent_ids,
            )
            if score > 0:
                scored.append((score, str(compact.get("timestamp") or ""), compact))

        for item in abnormal_events:
            compact, score = self._score_abnormal_event(item, today=today, has_current_image=bool(image_paths))
            if score > 0:
                scored.append((score, str(compact.get("timestamp") or ""), compact))

        deduped: dict[str, tuple[int, str, dict[str, Any]]] = {}
        for score, timestamp, compact in scored:
            event_id = compact.get("event_id")
            if not isinstance(event_id, str) or not event_id:
                continue
            previous = deduped.get(event_id)
            if previous is None or (score, timestamp) > (previous[0], previous[1]):
                deduped[event_id] = (score, timestamp, compact)

        ranked = sorted(deduped.values(), key=lambda item: (item[0], item[1]), reverse=True)
        return self._select_diverse_events(ranked)

    def _select_diverse_events(
        self,
        ranked: list[tuple[int, str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if self.max_events <= 0:
            return []

        selected: list[tuple[int, str, dict[str, Any]]] = []
        selected_ids: set[str] = set()

        def add_first(candidates: list[tuple[int, str, dict[str, Any]]]) -> None:
            if len(selected) >= self.max_events:
                return
            for item in candidates:
                event_id = item[2].get("event_id")
                if isinstance(event_id, str) and event_id not in selected_ids:
                    selected.append(item)
                    selected_ids.add(event_id)
                    return

        current_intent = [item for item in ranked if _has_reason_prefix(item[2], "current_intent:")]
        current_intent_non_l1 = [
            item for item in current_intent if item[2].get("home_esi_level") != "L1"
        ]
        high_risk = [
            item
            for item in ranked
            if item[2].get("home_esi_level") == "L1" or _has_reason_prefix(item[2], "high_risk:")
        ]
        reminder_related = [item for item in ranked if "reminder_related" in item[2].get("match_reasons", [])]

        add_first(current_intent_non_l1 or current_intent)
        add_first(high_risk)
        add_first(reminder_related)

        for item in ranked:
            if len(selected) >= self.max_events:
                break
            event_id = item[2].get("event_id")
            if isinstance(event_id, str) and event_id not in selected_ids:
                selected.append(item)
                selected_ids.add(event_id)

        return [item[2] for item in selected[: self.max_events]]

    def _score_event(
        self,
        event: dict[str, Any],
        *,
        current_groups: set[str],
        current_asr: str,
        today: str,
        is_recent: bool,
    ) -> tuple[dict[str, Any], int]:
        risk = event.get("risk") if isinstance(event.get("risk"), dict) else {}
        perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
        level = str(risk.get("home_esi_level") or "Normal")
        score = RISK_SCORE.get(level, 0)
        reasons: list[str] = []
        if level in RISK_SCORE and level != "Normal":
            reasons.append(f"risk:{level}")
            if level == "L1":
                reasons.append("high_risk:L1")
        if is_recent:
            score += 50
            reasons.append("recent")
        timestamp = str(event.get("timestamp") or "")
        if timestamp.startswith(today) and level in {"L1", "L2"}:
            score += 80
            reasons.append("same_day_risk")

        event_text = " ".join(
            str(value or "")
            for value in (
                event.get("asr_text"),
                perception.get("intent"),
                risk.get("reason"),
                event.get("outcome"),
            )
        )
        event_groups = _matched_keyword_groups(event_text)
        for group in sorted(current_groups & event_groups):
            score += 150
            reasons.append(f"keyword:{group}")
            reasons.append(f"current_intent:{group}")
        if _is_reminder_related(event):
            if current_groups & {"medication", "hydration"} or _contains_any(current_asr, ["提醒", "完成", "等一下"]):
                score += 120
                reasons.append("reminder_related")

        return self._compact_event(event, resolved="unknown", match_reasons=reasons), score

    def _score_abnormal_event(
        self,
        event: dict[str, Any],
        *,
        today: str,
        has_current_image: bool,
    ) -> tuple[dict[str, Any], int]:
        resolved = _resolved_value(event)
        if resolved != "false":
            return self._compact_abnormal_event(event, resolved=resolved, match_reasons=[]), 0
        level = str(event.get("home_esi_level") or "L1")
        score = RISK_SCORE.get(level, 0) + 180
        reasons = ["abnormal_unresolved", "abnormal_artifact", f"risk:{level}"]
        if level == "L1":
            reasons.append("high_risk:L1")
        timestamp = str(event.get("timestamp") or "")
        if timestamp.startswith(today):
            score += 80
            reasons.append("same_day_risk")
        if has_current_image:
            score += 20
            reasons.append("current_image_available")
        return self._compact_abnormal_event(event, resolved=resolved, match_reasons=reasons), score

    def _compact_event(
        self,
        event: dict[str, Any],
        *,
        resolved: str,
        match_reasons: list[str],
    ) -> dict[str, Any]:
        risk = event.get("risk") if isinstance(event.get("risk"), dict) else {}
        perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
        return {
            "event_id": _optional_str(event.get("event_id")) or "",
            "timestamp": _optional_str(event.get("timestamp")),
            "source": _optional_str(event.get("source")),
            "asr_text": _truncate(_optional_str(event.get("asr_text")), TEXT_LIMITS["asr_text"]),
            "intent": _truncate(_optional_str(perception.get("intent")), 80),
            "home_esi_level": _optional_str(risk.get("home_esi_level")) or "Normal",
            "risk_reason": _truncate(_optional_str(risk.get("reason")), TEXT_LIMITS["risk_reason"]),
            "outcome": _truncate(_optional_str(event.get("outcome")), TEXT_LIMITS["outcome"]),
            "resolved": resolved,
            "match_reasons": match_reasons,
        }

    def _compact_abnormal_event(
        self,
        event: dict[str, Any],
        *,
        resolved: str,
        match_reasons: list[str],
    ) -> dict[str, Any]:
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        notification = event.get("notification") if isinstance(event.get("notification"), dict) else {}
        return {
            "event_id": _optional_str(event.get("event_id")) or "",
            "timestamp": _optional_str(event.get("timestamp")),
            "source": _optional_str(event.get("source")) or "abnormal_events",
            "asr_text": _truncate(_optional_str(evidence.get("asr_text")), TEXT_LIMITS["asr_text"]),
            "intent": "abnormal_event",
            "home_esi_level": _optional_str(event.get("home_esi_level")) or "L1",
            "risk_reason": _truncate(_optional_str(event.get("risk_reason")), TEXT_LIMITS["risk_reason"]),
            "outcome": _truncate(_optional_str(notification.get("status")), TEXT_LIMITS["outcome"]),
            "resolved": resolved,
            "match_reasons": match_reasons,
        }

    def _enforce_budget(self, context: dict[str, Any]) -> dict[str, Any]:
        warned = False
        while _serialized_len(context) > self.max_chars and context.get("relevant_events"):
            context["relevant_events"].pop()
            if not warned:
                context["read_status"]["warnings"].append("care_context_trimmed_to_budget")
                warned = True
        return context


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _serialized_len(context: dict[str, Any]) -> int:
    return len(json.dumps(context, ensure_ascii=False, separators=(",", ":")))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    stripped = value.strip()
    return stripped or None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3] + "..."


def _matched_keyword_groups(text: str) -> set[str]:
    return {group for group, keywords in KEYWORD_SETS.items() if _contains_any(text, keywords)}


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _has_reason_prefix(event: dict[str, Any], prefix: str) -> bool:
    reasons = event.get("match_reasons")
    return isinstance(reasons, list) and any(str(reason).startswith(prefix) for reason in reasons)


def _is_reminder_related(event: dict[str, Any]) -> bool:
    actions = event.get("actions_taken")
    if isinstance(actions, list) and any("reminder" in str(action) for action in actions):
        return True
    perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
    intent = str(perception.get("intent") or "")
    return "reminder" in intent or "提醒" in intent

def _resolved_value(event: dict[str, Any]) -> str:
    if "resolved" in event:
        value = event.get("resolved")
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "resolved", "closed", "done"}:
                return "true"
            if normalized in {"false", "unresolved", "open", "pending", "active"}:
                return "false"
            if normalized == "unknown":
                return "unknown"
        return "unknown"

    status = event.get("status")
    if isinstance(status, str):
        normalized = status.strip().lower()
        if normalized in {"resolved", "closed", "done", "completed"}:
            return "true"
        if normalized in {"unresolved", "open", "pending", "active"}:
            return "false"
        if normalized == "unknown":
            return "unknown"

    return "unknown"
