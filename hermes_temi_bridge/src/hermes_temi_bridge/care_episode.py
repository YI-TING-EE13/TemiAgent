"""Persistent, deduplicated abnormal-care episode state owned by the Bridge.

The store contains only operational identifiers and notification receipts.  It
does not persist raw ASR, evidence frames, model prompts, or recipient details.
``time.monotonic`` values make the timer deterministic in tests and prevent wall
clock changes from extending a live response window.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


DETECTED = "DETECTED"
INITIAL_ALERT_SENT = "INITIAL_ALERT_SENT"
AWAITING_FIRST_RESPONSE = "AWAITING_FIRST_RESPONSE"
RESIDENT_RESPONDED = "RESIDENT_RESPONDED"
FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
NO_RESPONSE = "NO_RESPONSE"
ESCALATION_SENT = "ESCALATION_SENT"
RESOLVED = "RESOLVED"
EXPIRED = "EXPIRED"

TERMINAL_STATES = {ESCALATION_SENT, RESOLVED, EXPIRED}
ACTIVE_RESPONSE_STATES = {AWAITING_FIRST_RESPONSE, FOLLOW_UP_REQUIRED, NO_RESPONSE}
MAX_EPISODES = 200


@dataclass(frozen=True)
class CareEpisode:
    """One privacy-bounded abnormal-care workflow instance."""

    event_id: str
    robot_id: str
    event_type: str
    resident_id: str | None
    detected_timestamp_ms: int | None
    request_id: str | None
    run_id: str | None
    scenario_id: str | None
    is_test: bool
    status: str
    created_monotonic_ms: int
    updated_monotonic_ms: int
    first_response_deadline_monotonic_ms: int
    escalation_deadline_monotonic_ms: int | None
    clarification_count: int = 0
    notification_stages: dict[str, dict[str, Any]] | None = None
    transitions: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CareEpisode":
        required = (
            "event_id",
            "robot_id",
            "event_type",
            "is_test",
            "status",
            "created_monotonic_ms",
            "updated_monotonic_ms",
            "first_response_deadline_monotonic_ms",
        )
        if any(key not in value for key in required):
            raise ValueError("invalid_care_episode")
        stages = value.get("notification_stages")
        if stages is not None and not isinstance(stages, dict):
            raise ValueError("invalid_care_episode_notification_stages")
        transitions = value.get("transitions", [])
        if not isinstance(transitions, list) or not all(isinstance(item, dict) for item in transitions):
            raise ValueError("invalid_care_episode_transitions")
        return cls(
            event_id=str(value["event_id"]),
            robot_id=str(value["robot_id"]),
            event_type=str(value["event_type"]),
            resident_id=_optional_string(value.get("resident_id")),
            detected_timestamp_ms=(
                int(value["detected_timestamp_ms"])
                if isinstance(value.get("detected_timestamp_ms"), int)
                else None
            ),
            request_id=_optional_string(value.get("request_id")),
            run_id=_optional_string(value.get("run_id")),
            scenario_id=_optional_string(value.get("scenario_id")),
            is_test=bool(value["is_test"]),
            status=str(value["status"]),
            created_monotonic_ms=int(value["created_monotonic_ms"]),
            updated_monotonic_ms=int(value["updated_monotonic_ms"]),
            first_response_deadline_monotonic_ms=int(value["first_response_deadline_monotonic_ms"]),
            escalation_deadline_monotonic_ms=(
                int(value["escalation_deadline_monotonic_ms"])
                if isinstance(value.get("escalation_deadline_monotonic_ms"), int)
                else None
            ),
            clarification_count=int(value.get("clarification_count", 0)),
            notification_stages=stages or {},
            transitions=tuple(transitions[-40:]),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize only bounded operational state."""
        return {
            "event_id": self.event_id,
            "robot_id": self.robot_id,
            "event_type": self.event_type,
            "resident_id": self.resident_id,
            "detected_timestamp_ms": self.detected_timestamp_ms,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "is_test": self.is_test,
            "status": self.status,
            "created_monotonic_ms": self.created_monotonic_ms,
            "updated_monotonic_ms": self.updated_monotonic_ms,
            "first_response_deadline_monotonic_ms": self.first_response_deadline_monotonic_ms,
            "escalation_deadline_monotonic_ms": self.escalation_deadline_monotonic_ms,
            "clarification_count": self.clarification_count,
            "notification_stages": self.notification_stages or {},
            "transitions": list(self.transitions[-40:]),
        }


class CareEpisodeStore:
    """Atomic store for abnormal-care episode state and notification-stage dedup."""

    def __init__(
        self,
        memory_dir: str | Path,
        *,
        first_response_timeout_seconds: int,
        second_response_timeout_seconds: int,
    ) -> None:
        self.root = Path(memory_dir)
        self.path = self.root / "abnormal_care_episodes.json"
        self.first_response_timeout_ms = first_response_timeout_seconds * 1000
        self.second_response_timeout_ms = second_response_timeout_seconds * 1000

    def create(
        self,
        *,
        event_id: str,
        robot_id: str,
        event_type: str,
        resident_id: str | None,
        detected_timestamp_ms: int | None,
        request_id: str | None,
        run_id: str | None,
        scenario_id: str | None,
        is_test: bool,
        now_monotonic_ms: int,
    ) -> tuple[CareEpisode, bool]:
        """Create one event-idempotent episode without superseding another event."""
        episodes = self._load()
        for episode in episodes:
            if episode.event_id == event_id:
                return episode, False
        episode = CareEpisode(
            event_id=event_id,
            robot_id=robot_id,
            event_type=event_type,
            resident_id=resident_id,
            detected_timestamp_ms=detected_timestamp_ms,
            request_id=request_id,
            run_id=run_id,
            scenario_id=scenario_id,
            is_test=is_test,
            status=DETECTED,
            created_monotonic_ms=now_monotonic_ms,
            updated_monotonic_ms=now_monotonic_ms,
            first_response_deadline_monotonic_ms=now_monotonic_ms + self.first_response_timeout_ms,
            escalation_deadline_monotonic_ms=None,
            notification_stages={},
            transitions=(
                {"from": None, "to": DETECTED, "at_monotonic_ms": now_monotonic_ms, "reason": "event_validated"},
            ),
        )
        self._save([*episodes, episode])
        return episode, True

    def get(self, event_id: str) -> CareEpisode | None:
        """Return one episode by its immutable originating event identifier."""
        return next((episode for episode in self._load() if episode.event_id == event_id), None)

    def active_for_robot(self, robot_id: str) -> CareEpisode | None:
        """Return the newest non-terminal episode that may accept a reply."""
        active = [
            episode
            for episode in self._load()
            if episode.robot_id == robot_id and episode.status in ACTIVE_RESPONSE_STATES
        ]
        return active[-1] if active else None

    def due_first_response(self, now_monotonic_ms: int) -> list[CareEpisode]:
        """Return episodes that need one Hermes-generated recheck."""
        return [
            episode
            for episode in self._load()
            if episode.status == AWAITING_FIRST_RESPONSE
            and episode.first_response_deadline_monotonic_ms <= now_monotonic_ms
        ]

    def due_escalation(self, now_monotonic_ms: int) -> list[CareEpisode]:
        """Return episodes whose second response deadline elapsed."""
        return [
            episode
            for episode in self._load()
            if episode.status == NO_RESPONSE
            and episode.escalation_deadline_monotonic_ms is not None
            and episode.escalation_deadline_monotonic_ms <= now_monotonic_ms
        ]

    def transition(
        self,
        event_id: str,
        status: str,
        *,
        now_monotonic_ms: int,
        reason: str = "",
        clarification_count: int | None = None,
    ) -> CareEpisode:
        """Persist one explicit state transition and its time basis."""
        episodes = self._load()
        updated: list[CareEpisode] = []
        target: CareEpisode | None = None
        for episode in episodes:
            if episode.event_id != event_id:
                updated.append(episode)
                continue
            if episode.status in TERMINAL_STATES and episode.status != status:
                raise ValueError(f"cannot transition terminal care episode {episode.status}")
            escalation_deadline = episode.escalation_deadline_monotonic_ms
            if status == NO_RESPONSE and escalation_deadline is None:
                escalation_deadline = now_monotonic_ms + self.second_response_timeout_ms
            transitions = (*episode.transitions, {
                "from": episode.status,
                "to": status,
                "at_monotonic_ms": now_monotonic_ms,
                "reason": reason,
            })[-40:]
            target = CareEpisode(
                **{
                    **episode.as_dict(),
                    "status": status,
                    "updated_monotonic_ms": now_monotonic_ms,
                    "escalation_deadline_monotonic_ms": escalation_deadline,
                    "clarification_count": clarification_count if clarification_count is not None else episode.clarification_count,
                    "transitions": transitions,
                }
            )
            updated.append(target)
        if target is None:
            raise KeyError(f"unknown care episode: {event_id}")
        self._save(updated)
        return target

    def reserve_notification_stage(self, event_id: str, stage: str, *, now_monotonic_ms: int) -> bool:
        """Atomically reserve a stage before external I/O, preventing restart duplicates."""
        episode = self.get(event_id)
        if episode is None:
            raise KeyError(f"unknown care episode: {event_id}")
        stages = dict(episode.notification_stages or {})
        if stage in stages:
            return False
        stages[stage] = {"reserved_at_monotonic_ms": now_monotonic_ms, "status": "reserved"}
        self._replace_episode(event_id, notification_stages=stages, updated_monotonic_ms=now_monotonic_ms)
        return True

    def complete_notification_stage(
        self,
        event_id: str,
        stage: str,
        receipt: dict[str, Any],
        *,
        now_monotonic_ms: int,
    ) -> CareEpisode:
        """Attach one redacted transport receipt to a reserved notification stage."""
        episode = self.get(event_id)
        if episode is None:
            raise KeyError(f"unknown care episode: {event_id}")
        stages = dict(episode.notification_stages or {})
        reservation = stages.get(stage)
        if not isinstance(reservation, dict):
            raise ValueError(f"unreserved notification stage: {stage}")
        stages[stage] = {
            **reservation,
            "completed_at_monotonic_ms": now_monotonic_ms,
            "status": str(receipt.get("status") or "failed"),
            "receipt": dict(receipt),
        }
        return self._replace_episode(event_id, notification_stages=stages, updated_monotonic_ms=now_monotonic_ms)

    def _replace_episode(self, event_id: str, **changes: Any) -> CareEpisode:
        episodes = self._load()
        updated: list[CareEpisode] = []
        target: CareEpisode | None = None
        for episode in episodes:
            if episode.event_id != event_id:
                updated.append(episode)
                continue
            value = episode.as_dict()
            value.update(changes)
            target = CareEpisode.from_dict(value)
            updated.append(target)
        if target is None:
            raise KeyError(f"unknown care episode: {event_id}")
        self._save(updated)
        return target

    def _load(self) -> list[CareEpisode]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = payload.get("episodes") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []
        episodes: list[CareEpisode] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                episodes.append(CareEpisode.from_dict(entry))
            except (TypeError, ValueError):
                continue
        return episodes[-MAX_EPISODES:]

    def _save(self, episodes: list[CareEpisode]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "episodes": [episode.as_dict() for episode in episodes[-MAX_EPISODES:]],
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
