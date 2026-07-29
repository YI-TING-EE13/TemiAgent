"""Bridge-owned validation and construction for existing identity result v1.0.

The Android-facing JSON schema is intentionally unchanged.  This module gives
the Demo operator route one reusable, fail-closed validator before its result
is published and before it is admitted as active resident context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


IDENTITY_STATUSES = {"father", "mother", "unknown"}
IDENTITY_SOURCES = {"vision_gender_fallback", "manual_selection", "unknown"}
_EXPECTED_FIELDS = {
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


class IdentityContractError(ValueError):
    """Raised when a payload does not satisfy the existing identity contract."""


def build_demo_identity_result(
    *,
    identity_status: str,
    reason: str,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build the only Demo-operator payload accepted by the existing schema."""
    if identity_status not in IDENTITY_STATUSES:
        raise IdentityContractError("identity_status_not_allowed")
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "event_id": event_id or f"demo_identity_{uuid4().hex}",
        "resident_id": identity_status if identity_status in {"father", "mother"} else None,
        "display_name": identity_status,
        "identity_status": identity_status,
        "confidence": 1.0 if identity_status in {"father", "mother"} else 0.0,
        "source": "manual_selection" if identity_status in {"father", "mother"} else "unknown",
        "reason": reason,
        "timestamp": timestamp or datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    return validate_identity_result(payload)


def validate_identity_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate all fields required by resident_identity_result.schema.json.

    The project deliberately avoids a second schema copy or a permissive
    adapter here.  Returned data is a shallow copy suitable for MQTT publish.
    """
    if not isinstance(payload, dict) or set(payload) != _EXPECTED_FIELDS:
        raise IdentityContractError("invalid_identity_result_fields")
    status = payload.get("identity_status")
    if status not in IDENTITY_STATUSES:
        raise IdentityContractError("invalid_identity_status")
    if payload.get("schema_version") != "1.0" or payload.get("display_name") != status:
        raise IdentityContractError("invalid_identity_result_identity")
    source = payload.get("source")
    if source not in IDENTITY_SOURCES:
        raise IdentityContractError("invalid_identity_source")
    event_id = payload.get("event_id")
    reason = payload.get("reason")
    timestamp = payload.get("timestamp")
    confidence = payload.get("confidence")
    if (
        not isinstance(event_id, str)
        or not event_id.strip()
        or not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 500
        or not isinstance(timestamp, str)
        or not timestamp.strip()
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= float(confidence) <= 1
    ):
        raise IdentityContractError("invalid_identity_result_value")
    if status == "unknown":
        if payload.get("resident_id") is not None or source != "unknown":
            raise IdentityContractError("invalid_unknown_identity_result")
    elif payload.get("resident_id") != status:
        raise IdentityContractError("invalid_confirmed_identity_result")
    return dict(payload)
