#!/usr/bin/env python3
"""Create a canonical ASR event with tiny JPEG frames for local tests."""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path


JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/"
    "8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/"
    "xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/"
    "xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/"
    "xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IR//2gAMAwEAAgADAAAAEP/"
    "EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//"
    "EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


FRAME_FILES = {
    "t_minus_1000": ("frame_t_minus_1000.jpg", -1000),
    "t_minus_500": ("frame_t_minus_500.jpg", -500),
    "t": ("frame_t.jpg", 0),
}


def build_event(
    *,
    shared_root: Path,
    bridge_root: str,
    robot_id: str,
    event_id: str,
    conversation_id: str,
    text: str,
    language: str,
    timestamp_ms: int,
) -> dict:
    """Write mock image files and return a schema-valid ASR event payload."""
    event_dir = shared_root / "events" / robot_id / event_id
    event_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for name, (filename, offset_ms) in FRAME_FILES.items():
        path = event_dir / filename
        path.write_bytes(JPEG_1X1)
        bridge_path = f"{bridge_root.rstrip('/')}/events/{robot_id}/{event_id}/{filename}"
        frames.append(
            {
                "name": name,
                "ts_ms": timestamp_ms + offset_ms,
                "path": bridge_path,
                "mime_type": "image/jpeg",
            }
        )

    event = {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": robot_id,
        "conversation_id": conversation_id,
        "type": "asr.final",
        "timestamp_ms": timestamp_ms,
        "speech_end_ts_ms": timestamp_ms,
        "language": language,
        "asr": {"text": text, "confidence": 0.92},
        "vision": {"sampling_policy": "T-1000,T-500,T", "frames": frames},
        "context": {
            "source": "mock_test",
            "wake_word_detected": True,
            "interaction_mode": "voice",
            "requires_response": True,
        },
    }
    (event_dir / "metadata.json").write_text(json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8")
    return event


def main() -> int:
    """Parse CLI arguments and generate the mock event fixture."""
    parser = argparse.ArgumentParser(description="Create mock Temi event images and ASR payload.")
    parser.add_argument("--shared-root", default="temi_shared", help="Host/shared root to write images into.")
    parser.add_argument("--bridge-root", default="/var/lib/temi_shared", help="Path as seen by HermesTemiBridge.")
    parser.add_argument("--robot-id", default="temi-01")
    parser.add_argument("--event-id", default="evt_bridge_test_001")
    parser.add_argument("--conversation-id", default="conv_test_001")
    parser.add_argument("--text", default="幫我看看桌上的東西是什麼")
    parser.add_argument("--language", default="zh-TW")
    parser.add_argument("--timestamp-ms", type=int, default=None)
    parser.add_argument("--print-event", action="store_true", help="Print the ASR event JSON to stdout.")
    args = parser.parse_args()

    timestamp_ms = args.timestamp_ms if args.timestamp_ms is not None else int(time.time() * 1000)
    event = build_event(
        shared_root=Path(args.shared_root),
        bridge_root=args.bridge_root,
        robot_id=args.robot_id,
        event_id=args.event_id,
        conversation_id=args.conversation_id,
        text=args.text,
        language=args.language,
        timestamp_ms=timestamp_ms,
    )
    if args.print_event:
        print(json.dumps(event, ensure_ascii=False))
    else:
        event_dir = Path(args.shared_root) / "events" / args.robot_id / args.event_id
        print(event_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
