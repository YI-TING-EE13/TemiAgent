"""Logging helpers for human-readable service logs and JSONL event traces."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def configure_logging(level: str) -> None:
    """Configure process-wide structured-enough console logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class EventJsonlLogger:
    """Append per-event JSON lines for offline debugging and latency review."""

    def __init__(self, log_dir: str | Path):
        """Create the log directory if needed."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, event_id: str, record_type: str, payload: dict[str, Any]) -> Path:
        """Append one event-scoped record and return the JSONL path."""
        path = self.log_dir / f"{event_id}.jsonl"
        record = {"type": record_type, **payload}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return path
