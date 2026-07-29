"""Process-scoped, Demo-only manual identity selection and refresh loop."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable


class DemoIdentityController:
    """Publish short-lived manual identity results without restoring prior state."""

    def __init__(
        self,
        *,
        robot_id: str,
        state_dir: str | Path,
        publish: Callable[[str, str, str | None], dict[str, Any]],
        refresh_seconds: int,
        max_duration_seconds: int,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if refresh_seconds <= 0 or max_duration_seconds <= 0 or refresh_seconds > max_duration_seconds:
            raise ValueError("invalid_demo_identity_refresh_configuration")
        self.robot_id = robot_id
        self.state_dir = Path(state_dir)
        self._publish = publish
        self._refresh_seconds = refresh_seconds
        self._max_duration_seconds = max_duration_seconds
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._generation = 0
        self._active_status = "unknown"
        self._expires_at: float | None = None
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, identity_status: str, *, trigger_event_id: str | None = None) -> dict[str, Any]:
        """Start a new father/mother selection and replace any earlier session."""
        if identity_status not in {"father", "mother"}:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_STATUS_NOT_ALLOWED"}
        with self._lock:
            self._cancel_current_locked()
            result = self._publish(identity_status, "Controlled Demo operator identity selection.", trigger_event_id)
            if result.get("status") != "published":
                self._set_unknown_locked(persist=True)
                return result
            self._generation += 1
            generation = self._generation
            self._active_status = identity_status
            self._expires_at = self._monotonic() + self._max_duration_seconds
            cancel = threading.Event()
            self._cancel = cancel
            self._write_state_locked()
            self._thread = threading.Thread(
                target=self._refresh_loop,
                args=(generation, identity_status, cancel),
                daemon=True,
                name="temi-demo-identity-refresh",
            )
            self._thread.start()
            return {"status": "published", "operation": "start", "identity_status": identity_status, "expires_in_seconds": self._max_duration_seconds, **result}

    def stop(self, *, trigger_event_id: str | None = None, reason: str = "Controlled Demo operator identity cleared.") -> dict[str, Any]:
        """Clear active identity locally and publish the canonical unknown result."""
        with self._lock:
            self._cancel_current_locked()
            self._set_unknown_locked(persist=True)
            result = self._publish("unknown", reason, trigger_event_id)
            return {"operation": "stop", "identity_status": "unknown", **result}

    def status(self) -> dict[str, Any]:
        """Return process-local state only; never restore a previous process state."""
        with self._lock:
            remaining = 0
            if self._active_status in {"father", "mother"} and self._expires_at is not None:
                remaining = max(0, int(self._expires_at - self._monotonic()))
            return {"status": "ok", "identity_status": self._active_status, "expires_in_seconds": remaining, "process_scoped": True}

    def shutdown(self) -> None:
        """Fail closed during Bridge shutdown without loading any stale state."""
        with self._lock:
            self._cancel_current_locked()
            self._set_unknown_locked(persist=True)
            self._publish("unknown", "Demo identity controller shutdown.", None)

    def _refresh_loop(self, generation: int, identity_status: str, cancel: threading.Event) -> None:
        while True:
            if cancel.wait(self._refresh_seconds):
                return
            with self._lock:
                if generation != self._generation or cancel is not self._cancel:
                    return
                if self._expires_at is None or self._monotonic() >= self._expires_at:
                    self._set_unknown_locked(persist=True)
                    self._publish("unknown", "Controlled Demo identity session expired.", None)
                    return
                self._publish(identity_status, "Controlled Demo operator identity refresh.", None)

    def _cancel_current_locked(self) -> None:
        self._generation += 1
        self._cancel.set()

    def _set_unknown_locked(self, *, persist: bool) -> None:
        self._active_status = "unknown"
        self._expires_at = None
        if persist:
            self._write_state_locked()

    def _write_state_locked(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        state = {
            "schema_version": "temiagent.demo_identity.v1",
            "robot_id": self.robot_id,
            "identity_status": self._active_status,
            "process_scoped": True,
            "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }
        descriptor, temporary_name = tempfile.mkstemp(prefix=".identity.", dir=self.state_dir)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_dir / "current.json")
            os.chmod(self.state_dir / "current.json", 0o600)
        finally:
            if temporary.exists():
                temporary.unlink()
