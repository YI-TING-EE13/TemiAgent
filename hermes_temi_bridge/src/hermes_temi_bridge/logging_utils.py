"""Logging helpers for human-readable service logs and JSONL event traces."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import threading
from typing import Any
import uuid

LOGGER = logging.getLogger(__name__)

TRACE_SCHEMA_VERSION = "1.0"

TRACE_STAGES = (
    "event_received",
    "input_validated",
    "care_context_built",
    "hermes_request_prepared",
    "hermes_invocation_finished",
    "hermes_output_validated",
    "memory_actions_completed",
    "command_request_published",
    "command_result_received",
    "event_completed",
    "event_failed",
    "duplicate_event_ignored",
)
TRACE_STAGE_SET = set(TRACE_STAGES)
INDEX_STATUSES = {"started", "completed", "failed", "ignored"}

LEGACY_RECORD_STAGE = {
    "asr_event_received": "event_received",
    "abnormal_event_received": "event_received",
    "hermes_invocation_start": "hermes_request_prepared",
    "hermes_invocation_end": "hermes_invocation_finished",
    "command_result": "command_result_received",
    "event_completed": "event_completed",
    "event_failed": "event_failed",
    "duplicate_event_ignored": "duplicate_event_ignored",
}

TEXT_SUMMARY_KEYS = {"asr_text", "prompt", "raw_hermes_output", "raw_output"}
JSON_SUMMARY_KEYS = {"care_context", "raw_inbound_payload"}


def configure_logging(level: str) -> None:
    """Configure process-wide structured-enough console logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class EventJsonlLogger:
    """Fail-soft append-only event trace writer for Bridge debugging."""

    def __init__(
        self,
        log_dir: str | Path,
        *,
        enabled: bool = True,
        run_id: str | None = None,
        full_debug: bool = False,
        include_asr_text: bool = True,
        max_field_chars: int = 2000,
    ):
        """Create an event trace writer.

        Trace logging is intentionally fail-soft: callers should never depend on
        a successful write for Bridge control flow.
        """
        self.log_dir = Path(log_dir)
        self.enabled = enabled
        self.run_id = run_id or _make_run_id()
        self.sanitizer = TracePayloadSanitizer(
            full_debug=full_debug,
            include_asr_text=include_asr_text,
            max_field_chars=max_field_chars,
        )
        self._seq_by_event: dict[str, int] = {}
        self._lock = threading.Lock()
        if self.enabled:
            self._ensure_log_dir()

    def write(self, event_id: str, record_type: str, payload: dict[str, Any]) -> Path:
        """Append a legacy-compatible trace record and return the event path."""
        stage = LEGACY_RECORD_STAGE.get(record_type, "event_completed")
        status = str(payload.get("status") or "ok") if isinstance(payload, dict) else "ok"
        return self.write_trace(
            event_id=event_id,
            robot_id=_optional_str(payload.get("robot_id")) if isinstance(payload, dict) else None,
            source_type=_optional_str(payload.get("source_type")) if isinstance(payload, dict) else None,
            stage=stage,
            record_type=record_type,
            status=status,
            payload=payload,
        )

    def write_trace(
        self,
        *,
        event_id: str,
        robot_id: str | None = None,
        source_type: str | None = None,
        stage: str,
        record_type: str | None = None,
        status: str = "ok",
        payload: dict[str, Any] | None = None,
        level: str = "INFO",
        component: str = "bridge",
        duration_ms: int | None = None,
        index_status: str | None = None,
        index_summary: dict[str, Any] | str | None = None,
    ) -> Path:
        """Append one schema-versioned trace record.

        All filesystem and JSON serialization failures are caught and logged as
        warnings so tracing cannot interrupt robot safety flows.
        """
        event_key = _safe_event_id(event_id)
        path = self.log_dir / f"{event_key}.jsonl"
        if not self.enabled:
            return path
        if stage not in TRACE_STAGE_SET:
            LOGGER.warning("trace write skipped for %s: invalid stage %s", event_id, stage)
            return path

        try:
            timestamp = _now_iso()
            sanitized_payload = self.sanitizer.sanitize_payload(payload or {})
            seq = self._next_seq(event_key, path)
            record = {
                "schema_version": TRACE_SCHEMA_VERSION,
                "timestamp": timestamp,
                "run_id": self.run_id,
                "seq": seq,
                "level": level.upper(),
                "component": component,
                "event_id": event_id,
                "robot_id": robot_id,
                "source_type": source_type,
                "record_type": record_type or stage,
                "stage": stage,
                "status": status,
                "duration_ms": duration_ms,
                "payload": sanitized_payload,
            }
            self._ensure_log_dir()
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception as exc:  # pragma: no cover - fail-soft protection
            LOGGER.warning("trace write failed for event %s stage %s: %s", event_id, stage, exc)
            return path

        if index_status:
            self.write_index(
                event_id=event_id,
                robot_id=robot_id,
                source_type=source_type,
                status=index_status,
                summary=index_summary or {},
                timestamp=timestamp,
            )
        return path

    def write_index(
        self,
        *,
        event_id: str,
        robot_id: str | None,
        source_type: str | None,
        status: str,
        summary: dict[str, Any] | str,
        timestamp: str | None = None,
    ) -> None:
        """Append one run/event index record without mutating prior records."""
        if not self.enabled:
            return
        if status not in INDEX_STATUSES:
            LOGGER.warning("trace index write skipped for %s: invalid status %s", event_id, status)
            return
        try:
            record = {
                "schema_version": TRACE_SCHEMA_VERSION,
                "timestamp": timestamp or _now_iso(),
                "run_id": self.run_id,
                "event_id": event_id,
                "robot_id": robot_id,
                "source_type": source_type,
                "status": status,
                "summary": self.sanitizer.sanitize_payload({"summary": summary})["summary"],
            }
            self._ensure_log_dir()
            with (self.log_dir / "_index.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception as exc:  # pragma: no cover - fail-soft protection
            LOGGER.warning("trace index write failed for event %s: %s", event_id, exc)

    def _ensure_log_dir(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - fail-soft protection
            LOGGER.warning("trace log directory setup failed for %s: %s", self.log_dir, exc)

    def _next_seq(self, event_key: str, path: Path) -> int:
        with self._lock:
            if event_key not in self._seq_by_event:
                self._seq_by_event[event_key] = self._read_existing_max_seq(path)
            self._seq_by_event[event_key] += 1
            return self._seq_by_event[event_key]

    def _read_existing_max_seq(self, path: Path) -> int:
        if not path.exists():
            return 0
        max_seq = 0
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                parsed = json.loads(line)
                seq = parsed.get("seq") if isinstance(parsed, dict) else None
                if isinstance(seq, int) and seq > max_seq:
                    max_seq = seq
        except Exception as exc:  # pragma: no cover - fail-soft protection
            LOGGER.warning("trace seq scan failed for %s: %s", path, exc)
        return max_seq


class TracePayloadSanitizer:
    """Normalize trace payloads and summaries consistently."""

    def __init__(
        self,
        *,
        full_debug: bool,
        include_asr_text: bool,
        max_field_chars: int,
    ):
        """Configure trace payload redaction and excerpt behavior."""
        self.full_debug = full_debug
        self.include_asr_text = include_asr_text
        self.max_field_chars = max(0, int(max_field_chars))

    def sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Sanitize one trace payload through a shared policy."""
        return self._sanitize_value(payload, key=None)

    def text_summary(self, text: str, *, include_text: bool = False) -> dict[str, Any]:
        """Return a stable sha256/excerpt/length summary for text."""
        excerpt = text[: self.max_field_chars]
        summary: dict[str, Any] = {
            "length": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "excerpt": excerpt,
            "truncated": len(text) > self.max_field_chars,
        }
        if include_text:
            summary["text"] = text
        return summary

    def json_summary(self, value: Any, *, include_value: bool = False) -> dict[str, Any]:
        """Return a stable summary for a JSON-like value."""
        encoded = _stable_json(value)
        summary = self.text_summary(encoded, include_text=False)
        if include_value:
            summary["value"] = self._sanitize_value(value, key=None, allow_summary=False)
        return summary

    def _sanitize_value(
        self,
        value: Any,
        *,
        key: str | None,
        allow_summary: bool = True,
    ) -> Any:
        if key == "asr_text" and isinstance(value, str):
            return self.text_summary(
                value,
                include_text=self.full_debug or self.include_asr_text,
            )
        if key in {"prompt", "raw_hermes_output", "raw_output"} and isinstance(value, str):
            return self.text_summary(value, include_text=self.full_debug)
        if key in JSON_SUMMARY_KEYS:
            summary_value = self._sanitize_json_summary_value(value, raw_inbound=key == "raw_inbound_payload")
            summary = self.json_summary(summary_value, include_value=False)
            if self.full_debug:
                summary["value"] = self._json_safe_value(value)
            return summary
        if isinstance(value, dict):
            return {
                _safe_string(item_key): self._sanitize_value(item_value, key=_safe_string(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize_value(item, key=None) for item in value]
        if isinstance(value, tuple):
            return [self._sanitize_value(item, key=None) for item in value]
        if isinstance(value, str):
            if allow_summary and len(value) > self.max_field_chars:
                return self.text_summary(value, include_text=False)
            return value
        if value is None or isinstance(value, bool | int | float):
            return value
        return _safe_string(value)

    def _sanitize_json_summary_value(self, value: Any, *, raw_inbound: bool) -> Any:
        if raw_inbound:
            return self._sanitize_raw_inbound_payload(value)
        return self._sanitize_value(value, key=None, allow_summary=False)

    def _sanitize_raw_inbound_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized = {}
            for item_key, item_value in value.items():
                if item_key == "asr" and isinstance(item_value, dict):
                    asr = dict(item_value)
                    text = asr.get("text")
                    if isinstance(text, str):
                        asr["text"] = self.text_summary(
                            text,
                            include_text=self.full_debug or self.include_asr_text,
                        )
                    sanitized[item_key] = self._sanitize_value(asr, key=None, allow_summary=False)
                else:
                    sanitized[_safe_string(item_key)] = self._sanitize_raw_inbound_payload(item_value)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_raw_inbound_payload(item) for item in value]
        return self._sanitize_value(value, key=None, allow_summary=False)

    def _json_safe_value(self, value: Any) -> Any:
        try:
            return json.loads(_stable_json(value))
        except Exception:
            return _safe_string(value)


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return json.dumps(_safe_string(value), ensure_ascii=False)


def _safe_string(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        try:
            return repr(value)
        except Exception:
            return f"<unserializable:{type(value).__name__}>"


def _make_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_event_id(event_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(event_id))
    return safe or "unknown_event"


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
