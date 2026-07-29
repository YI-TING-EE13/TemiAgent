"""Fail-closed active-resident context derived from canonical identity results.

This module consumes the already-defined ``resident/identity/result`` contract.
It does not perform vision inference, infer identity from conversation text, or
write care memory.  The public display names live here rather than in the
canonical identity schema so the schema can retain its established values.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any


CANONICAL_RESIDENT_IDS = {"father", "mother", "unknown"}
DISPLAY_NAMES = {
    "father": "王先生",
    "mother": "王太太",
    "unknown": "未知住民／尚未確認",
}


@dataclass(frozen=True)
class ActiveResident:
    """A bounded, non-biometric context selected by the upstream provider."""

    resident_id: str
    display_name: str
    source: str
    identity_event_id: str | None = None

    @property
    def is_confirmed(self) -> bool:
        """Return whether this context may access a private Demo partition."""
        return self.resident_id in {"father", "mother"}

    def as_prompt_context(self) -> dict[str, str | None]:
        """Return only the fields appropriate for the Hermes request."""
        return {
            "resident_id": self.resident_id,
            "display_name": self.display_name,
            "source": self.source,
            "identity_event_id": self.identity_event_id,
        }


def unknown_resident(reason: str) -> ActiveResident:
    """Return the only safe state when visual identity is unavailable."""
    return ActiveResident(
        resident_id="unknown",
        display_name=DISPLAY_NAMES["unknown"],
        source=reason,
        identity_event_id=None,
    )


class ResidentContextStore:
    """Keep fresh canonical visual identity results per robot in memory only."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        minimum_confidence: float = 0.70,
        monotonic=time.monotonic,
    ) -> None:
        self._ttl_seconds = max(1, int(ttl_seconds))
        if not 0 <= float(minimum_confidence) <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self._minimum_confidence = float(minimum_confidence)
        self._monotonic = monotonic
        self._records: dict[str, tuple[float, ActiveResident]] = {}

    def update_from_identity_result(
        self,
        *,
        robot_id: str,
        payload: dict[str, Any],
        enabled: bool,
        operator_identity_enabled: bool = False,
    ) -> ActiveResident:
        """Validate a canonical result and update one robot's active resident.

        A normal visual route accepts only ``vision_gender_fallback``.  The
        separately gated Demo operator route may additionally accept the
        existing schema's ``manual_selection`` source.  Speech is never an
        identity source; this store sees only already-validated results.
        """
        if not enabled and not operator_identity_enabled:
            return unknown_resident("resident_identity_routing_disabled")
        if not isinstance(payload, dict):
            return self._store_unknown(robot_id, "invalid_identity_result")

        expected_fields = {
            "schema_version",
            "event_id",
            "resident_id",
            "display_name",
            "identity_status",
            "confidence",
            "source",
            "reason",
            "timestamp",
        }
        status = payload.get("identity_status")
        display_name = payload.get("display_name")
        source = payload.get("source")
        event_id = payload.get("event_id")
        confidence = payload.get("confidence")
        resident_id = payload.get("resident_id")
        allowed_sources = set()
        if enabled:
            allowed_sources.add("vision_gender_fallback")
        if operator_identity_enabled:
            allowed_sources.add("manual_selection")
        if (
            set(payload) != expected_fields
            or payload.get("schema_version") != "1.0"
            or status not in {"father", "mother"}
            or display_name != status
            or resident_id != status
            or source not in allowed_sources
            or not isinstance(event_id, str)
            or not event_id.strip()
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= float(confidence) <= 1
            or float(confidence) < self._minimum_confidence
        ):
            return self._store_unknown(robot_id, "identity_result_not_confirmed")

        resident = ActiveResident(
            resident_id=status,
            display_name=DISPLAY_NAMES[status],
            source=source,
            identity_event_id=event_id.strip(),
        )
        self._records[robot_id] = (self._monotonic(), resident)
        return resident

    def resolve(
        self,
        robot_id: str,
        *,
        enabled: bool,
        operator_identity_enabled: bool = False,
    ) -> ActiveResident:
        """Return a fresh confirmed context, otherwise fail closed to unknown."""
        if not enabled and not operator_identity_enabled:
            return unknown_resident("resident_identity_routing_disabled")
        record = self._records.get(robot_id)
        if record is None:
            return unknown_resident("missing_identity_result")
        observed_at, resident = record
        if self._monotonic() - observed_at > self._ttl_seconds:
            self._records.pop(robot_id, None)
            return unknown_resident("stale_identity_result")
        return resident

    def _store_unknown(self, robot_id: str, reason: str) -> ActiveResident:
        resident = unknown_resident(reason)
        self._records[robot_id] = (self._monotonic(), resident)
        return resident
