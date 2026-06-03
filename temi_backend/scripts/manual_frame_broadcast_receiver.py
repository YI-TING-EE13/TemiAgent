#!/usr/bin/env python3
"""Receive decoded JPEG frames from the Temi frame broadcast WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
from pathlib import Path
from typing import Any

import websockets


def parse_args() -> argparse.Namespace:
    """Parse CLI options for the manual frame receiver."""
    parser = argparse.ArgumentParser(description="Receive JPEG frames from ws://<pc-ip>:8081.")
    parser.add_argument("--url", default="ws://127.0.0.1:8081")
    parser.add_argument("--output-dir", default="debug_frames/broadcast")
    parser.add_argument("--max-frames", type=int, default=5)
    return parser.parse_args()


async def receive_frames(url: str, output_dir: Path, max_frames: int) -> None:
    """Connect to the broadcast endpoint and save a small number of JPEG frames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    async with websockets.connect(url) as websocket:
        hello = await websocket.recv()
        if isinstance(hello, str):
            print(json.dumps(json.loads(hello), ensure_ascii=False, indent=2))
        saved = 0
        while saved < max_frames:
            payload: Any = await websocket.recv()
            if not isinstance(payload, bytes) or len(payload) <= 16:
                continue
            timestamp_ms, sequence = struct.unpack(">qQ", payload[:16])
            frame_path = output_dir / f"frame_{sequence:06d}_{timestamp_ms}.jpg"
            frame_path.write_bytes(payload[16:])
            print(frame_path)
            saved += 1


def main() -> int:
    """Run the manual receiver."""
    args = parse_args()
    asyncio.run(receive_frames(args.url, Path(args.output_dir), args.max_frames))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
