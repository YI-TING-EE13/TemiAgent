#!/usr/bin/env python3
"""Inspect HermesTemiBridge event trace JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


DEFAULT_LOG_DIR = Path("/TemiAgent/logs/overview_bridge_resident")


def parse_args() -> argparse.Namespace:
    """Parse command line flags."""
    parser = argparse.ArgumentParser(description="Show a Temi Bridge event trace timeline.")
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR.as_posix(), help="Bridge LOG_DIR.")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--latest", action="store_true", help="Show the latest indexed event.")
    selector.add_argument("--event-id", help="Show a specific event_id.")
    parser.add_argument("--full", action="store_true", help="Print full stage detail.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def main() -> int:
    """Load one trace and print it in the requested format."""
    args = parse_args()
    log_dir = Path(args.log_dir)
    event_id = args.event_id or latest_event_id(log_dir)
    if not event_id:
        print(f"No trace events found in {log_dir}", file=sys.stderr)
        return 1

    records = read_event_trace(log_dir, event_id)
    index = read_latest_index(log_dir).get(event_id)
    summary = summarize_timeline(records, index)
    document = {
        "event_id": event_id,
        "log_dir": log_dir.as_posix(),
        "index": index,
        "records": records,
        "latest_status": summary["status"],
        "summary": summary,
    }
    if args.json:
        print(json.dumps(document, ensure_ascii=False, indent=2))
        return 0
    if args.full:
        print_full(document)
    else:
        print_summary(document)
    return 0


def latest_event_id(log_dir: Path) -> str | None:
    """Return the most recent event id from the append-only index or mtime fallback."""
    last_event_id = None
    for record in read_jsonl(log_dir / "_index.jsonl"):
        event_id = record.get("event_id")
        if isinstance(event_id, str) and event_id:
            last_event_id = event_id
    if last_event_id:
        return last_event_id
    candidates = [path for path in log_dir.glob("*.jsonl") if path.name != "_index.jsonl"]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime).stem


def read_latest_index(log_dir: Path) -> dict[str, dict[str, Any]]:
    """Read index records and keep the last status for each event_id."""
    latest: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(log_dir / "_index.jsonl"):
        event_id = record.get("event_id")
        if isinstance(event_id, str) and event_id:
            latest[event_id] = record
    return latest


def read_event_trace(log_dir: Path, event_id: str) -> list[dict[str, Any]]:
    """Read one event trace ordered by seq when available."""
    path = log_dir / f"{safe_event_id(event_id)}.jsonl"
    records = read_jsonl(path)
    return sorted(records, key=lambda record: record.get("seq") if isinstance(record.get("seq"), int) else 0)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL objects, ignoring malformed or non-object lines."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def print_summary(document: dict[str, Any]) -> None:
    """Print a compact human-readable timeline."""
    index = document.get("index") if isinstance(document.get("index"), dict) else {}
    summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
    print(f"event_id: {document['event_id']}")
    print(f"status: {document.get('latest_status') or 'unknown'}")
    if index:
        print(f"run_id: {index.get('run_id')}")
        print(f"source_type: {index.get('source_type')}")
    print(f"duplicate_attempts: {summary.get('duplicate_attempts', 0)}")
    if summary.get("command_result") is not None:
        print(f"command_result: {summary.get('command_result')} late_result: {str(bool(summary.get('late_result'))).lower()}")
    print()
    for record in document["records"]:
        seq = record.get("seq", "?")
        stage = record.get("stage", "?")
        status = record.get("status", "?")
        duration = record.get("duration_ms")
        duration_text = f"{duration}ms" if isinstance(duration, int) else "-"
        print(f"{seq:>3}  {stage:<28} {status:<10} {duration_text:<8} {record_summary(record)}")


def print_full(document: dict[str, Any]) -> None:
    """Print human-readable stage details."""
    print_summary(document)
    print()
    for record in document["records"]:
        print(f"--- seq={record.get('seq')} stage={record.get('stage')} status={record.get('status')} ---")
        print(json.dumps(record.get("payload", {}), ensure_ascii=False, indent=2, sort_keys=True))


def record_summary(record: dict[str, Any]) -> str:
    """Return one concise summary line for a trace record."""
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    stage = record.get("stage")
    if stage == "event_received":
        asr = payload.get("asr_text")
        if isinstance(asr, dict):
            text = asr.get("excerpt") or ""
            return f"asr={text!r} images={len(payload.get('image_paths') or [])}"
        observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else {}
        observed = observation.get("action_name") or observation.get("reason") or ""
        return f"observation={observed!r}"
    if stage == "hermes_output_validated":
        cognitive = payload.get("cognitive_state") if isinstance(payload.get("cognitive_state"), dict) else {}
        return (
            f"home_esi={cognitive.get('home_esi_level')} "
            f"next={cognitive.get('next_step')} actions={payload.get('action_types')}"
        )
    if stage == "command_request_published":
        return f"command_status={payload.get('command_status')} command_id={payload.get('command_id')}"
    if stage == "command_result_received":
        result = payload.get("command_result") if isinstance(payload.get("command_result"), dict) else {}
        return f"command_id={result.get('command_id')} result_status={result.get('status')}"
    if stage == "event_completed":
        return (
            f"home_esi={payload.get('home_esi_level')} command={payload.get('command_status')} "
            f"total={payload.get('total_duration_ms')}ms"
        )
    if stage == "event_failed":
        return (
            f"failed_stage={payload.get('failed_stage')} error={payload.get('error_code')} "
            f"fallback_published={payload.get('fallback_command_published')}"
        )
    if stage == "duplicate_event_ignored":
        return f"reason={payload.get('reason')}"
    return ""


def summarize_timeline(records: list[dict[str, Any]], index: dict[str, Any] | None) -> dict[str, Any]:
    """Aggregate the user-facing status from timeline semantics."""
    failed = [record for record in records if record.get("stage") == "event_failed"]
    completed = [record for record in records if record.get("stage") == "event_completed"]
    duplicate_attempts = len(
        [record for record in records if record.get("stage") == "duplicate_event_ignored"]
    )
    command_results = [record for record in records if record.get("stage") == "command_result_received"]

    if failed:
        status = "failed"
        terminal_seq = _record_seq(failed[-1])
    elif completed:
        status = "completed"
        terminal_seq = _record_seq(completed[-1])
    elif isinstance(index, dict) and isinstance(index.get("status"), str):
        status = str(index["status"])
        terminal_seq = None
    else:
        status = _last_record_status(records) or "unknown"
        terminal_seq = None

    command_result = None
    late_result = False
    if command_results:
        latest_result = command_results[-1]
        payload = latest_result.get("payload") if isinstance(latest_result.get("payload"), dict) else {}
        result_payload = (
            payload.get("command_result") if isinstance(payload.get("command_result"), dict) else {}
        )
        command_result = result_payload.get("status") or latest_result.get("status")
        result_seq = _record_seq(latest_result)
        late_result = terminal_seq is not None and result_seq is not None and result_seq > terminal_seq

    return {
        "status": status,
        "duplicate_attempts": duplicate_attempts,
        "command_result": command_result,
        "late_result": late_result,
    }


def _last_record_status(records: list[dict[str, Any]]) -> str | None:
    if not records:
        return None
    status = records[-1].get("status")
    return status if isinstance(status, str) else None


def _record_seq(record: dict[str, Any]) -> int | None:
    seq = record.get("seq")
    return seq if isinstance(seq, int) else None


def safe_event_id(event_id: str) -> str:
    """Match EventJsonlLogger's filename-safe event id mapping."""
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(event_id))
    return safe or "unknown_event"


if __name__ == "__main__":
    raise SystemExit(main())
