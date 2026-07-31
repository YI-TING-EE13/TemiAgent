"""Typed models and validation for canonical Overview ASR events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_SCHEMA_VERSION = "1.0"
REQUIRED_FRAME_NAMES = {"t_minus_1000", "t_minus_500", "t"}
CANONICAL_ABNORMAL_EVENT_TYPES = {
    "falls_down",
    "lies_on_floor",
    "fight",
    "other_allowlisted",
}
LEGACY_ABNORMAL_EVENT_TYPE_MAP = {
    "falls down": "falls_down",
    "lies on the floor": "lies_on_floor",
    "fights": "fight",
}


class EventValidationError(ValueError):
    """Raised when an inbound ASR event does not match the Bridge schema."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        """Create an error with a machine-readable reason and optional details."""
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class VisionFrame:
    """One timestamped image frame associated with an ASR final event."""

    name: str
    ts_ms: int | None
    path: str
    mime_type: str | None = None


@dataclass(frozen=True)
class ASRFinalEvent:
    """Canonical speech event consumed by HermesTemiBridge."""

    schema_version: str
    event_id: str
    robot_id: str
    conversation_id: str | None
    timestamp_ms: int | None
    speech_end_ts_ms: int | None
    language: str
    asr_text: str
    asr_confidence: float | None
    frames: tuple[VisionFrame, ...]
    raw: dict[str, Any]

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any], robot_id_allowlist: tuple[str, ...] = ()
    ) -> "ASRFinalEvent":
        """Parse and validate a raw MQTT payload into an ASRFinalEvent."""
        if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
            raise EventValidationError("unsupported_schema_version")

        event_id = _required_string(payload, "event_id")
        robot_id = _required_string(payload, "robot_id")
        if robot_id_allowlist and robot_id not in robot_id_allowlist:
            raise EventValidationError("robot_not_allowed", {"robot_id": robot_id})

        asr = payload.get("asr")
        if not isinstance(asr, dict):
            raise EventValidationError("missing_asr")
        asr_text = str(asr.get("text", "")).strip()
        if not asr_text:
            raise EventValidationError("empty_asr_text")

        vision = payload.get("vision")
        if not isinstance(vision, dict):
            raise EventValidationError("missing_vision")
        frames_payload = vision.get("frames")
        if not isinstance(frames_payload, list) or len(frames_payload) != 3:
            raise EventValidationError("invalid_frame_count")

        frames = tuple(_parse_frame(item) for item in frames_payload)
        names = {frame.name for frame in frames}
        if names != REQUIRED_FRAME_NAMES:
            raise EventValidationError(
                "invalid_frame_names",
                {"expected": sorted(REQUIRED_FRAME_NAMES), "actual": sorted(names)},
            )

        return cls(
            schema_version=SUPPORTED_SCHEMA_VERSION,
            event_id=event_id,
            robot_id=robot_id,
            conversation_id=_optional_string(payload, "conversation_id"),
            timestamp_ms=_optional_int(payload, "timestamp_ms"),
            speech_end_ts_ms=_optional_int(payload, "speech_end_ts_ms"),
            language=str(payload.get("language") or "zh-TW"),
            asr_text=asr_text,
            asr_confidence=_optional_float(asr, "confidence"),
            frames=frames,
            raw=payload,
        )


@dataclass(frozen=True)
class PerceptionAbnormalEvent:
    """Canonical abnormal perception event consumed by HermesTemiBridge."""

    schema_version: str
    event_id: str
    robot_id: str
    timestamp_ms: int | None
    event_type: str
    action_name: str
    reason: str
    frames: tuple[VisionFrame, ...]
    resident_id: str | None
    request_id: str | None
    is_test: bool
    run_id: str | None
    scenario_id: str | None
    raw: dict[str, Any]

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any], robot_id_allowlist: tuple[str, ...] = ()
    ) -> "PerceptionAbnormalEvent":
        """Parse and validate a raw MQTT payload into a PerceptionAbnormalEvent."""
        if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
            raise EventValidationError("unsupported_schema_version")
        if payload.get("type") != "perception.abnormal":
            raise EventValidationError("unsupported_event_type")

        event_id = _required_string(payload, "event_id")
        robot_id = _required_string(payload, "robot_id")
        if robot_id_allowlist and robot_id not in robot_id_allowlist:
            raise EventValidationError("robot_not_allowed", {"robot_id": robot_id})

        observation = payload.get("observation")
        if not isinstance(observation, dict):
            raise EventValidationError("missing_observation")
        action_name = _required_string(observation, "action_name")
        reason = _required_string(observation, "reason")
        event_type = _parse_abnormal_event_type(payload, action_name)

        evidence = payload.get("evidence")
        if not isinstance(evidence, dict):
            raise EventValidationError("missing_evidence")
        frame_paths = evidence.get("frame_paths")
        if not isinstance(frame_paths, list) or not frame_paths:
            raise EventValidationError("missing_frame_paths")
        frames = tuple(_parse_abnormal_frame(index, path) for index, path in enumerate(frame_paths))
        context = payload.get("context")
        if context is not None and not isinstance(context, dict):
            raise EventValidationError("invalid_context")
        context = context if isinstance(context, dict) else {}
        is_test = context.get("test") is True
        context_source = _optional_string(context, "source")
        resident_id = _optional_string(context, "resident_id")
        request_id = _optional_string(context, "request_id")
        run_id = _optional_string(context, "run_id")
        scenario_id = _optional_string(context, "scenario_id")
        timestamp_ms = _optional_int(payload, "timestamp_ms")
        if is_test:
            missing = [
                key
                for key, value in (
                    ("timestamp_ms", timestamp_ms),
                    ("resident_id", resident_id),
                    ("request_id", request_id),
                    ("run_id", run_id),
                    ("scenario_id", scenario_id),
                )
                if value is None
            ]
            if missing:
                raise EventValidationError("missing_test_metadata", {"missing": missing})
            if context_source != "formal_demo_injector":
                raise EventValidationError("unsupported_test_event_source")

        return cls(
            schema_version=SUPPORTED_SCHEMA_VERSION,
            event_id=event_id,
            robot_id=robot_id,
            timestamp_ms=timestamp_ms,
            event_type=event_type,
            action_name=action_name,
            reason=reason,
            frames=frames,
            resident_id=resident_id,
            request_id=request_id,
            is_test=is_test,
            run_id=run_id,
            scenario_id=scenario_id,
            raw=payload,
        )


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read a required non-empty string field from a payload."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EventValidationError(f"missing_{key}")
    return value.strip()


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    """Read an optional non-empty string field from a payload."""
    value = payload.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    """Read an optional integer field without coercing string values."""
    value = payload.get(key)
    return value if isinstance(value, int) else None


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    """Read an optional numeric field as a float."""
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else None


def _parse_frame(payload: Any) -> VisionFrame:
    """Parse one frame object from the event's vision block."""
    if not isinstance(payload, dict):
        raise EventValidationError("invalid_frame")
    name = payload.get("name")
    path = payload.get("path") or payload.get("uri")
    if not isinstance(name, str) or not name.strip():
        raise EventValidationError("missing_frame_name")
    if not isinstance(path, str) or not path.strip():
        raise EventValidationError("missing_frame_path", {"frame": name})
    return VisionFrame(
        name=name.strip(),
        ts_ms=_optional_int(payload, "ts_ms"),
        path=path.strip(),
        mime_type=_optional_string(payload, "mime_type"),
    )


def _parse_abnormal_frame(index: int, path: Any) -> VisionFrame:
    """Parse one abnormal evidence frame path."""
    if not isinstance(path, str) or not path.strip():
        raise EventValidationError("missing_frame_path", {"frame_index": index})
    return VisionFrame(
        name=f"frame_{index:03d}",
        ts_ms=None,
        path=path.strip(),
        mime_type="image/jpeg",
    )


def _parse_abnormal_event_type(payload: dict[str, Any], action_name: str) -> str:
    """Normalize reviewed legacy labels while requiring known canonical types."""
    raw_type = payload.get("event_type")
    if raw_type is None:
        legacy = LEGACY_ABNORMAL_EVENT_TYPE_MAP.get(action_name.strip().lower())
        if legacy is not None:
            return legacy
        raise EventValidationError("missing_event_type")
    if not isinstance(raw_type, str) or raw_type not in CANONICAL_ABNORMAL_EVENT_TYPES:
        raise EventValidationError("unsupported_abnormal_event_type", {"event_type": raw_type})
    return raw_type
