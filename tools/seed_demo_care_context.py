#!/usr/bin/env python3
"""Seed or verify the private synthetic Demo resident-care memory partitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SRC = ROOT / "hermes_temi_bridge" / "src"
if BRIDGE_SRC.as_posix() not in sys.path:
    sys.path.insert(0, BRIDGE_SRC.as_posix())

from hermes_temi_bridge.demo_care_memory import (
    DemoCareMemoryError,
    seed_demo_care_memory,
    verify_demo_care_memory,
)


def _reject_tracked_memory(root: Path) -> None:
    """Keep the tool from ever targeting the repository's live memory directory."""
    if root.resolve() == (ROOT / "memory").resolve():
        raise DemoCareMemoryError("refusing_to_modify_tracked_runtime_memory")


def main(argv: list[str] | None = None) -> int:
    """Run an idempotent seed or read-only verification without service operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Private absolute Demo care-memory root.")
    parser.add_argument("--verify", action="store_true", help="Only inspect the expected seed markers.")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if not root.is_absolute():
            raise DemoCareMemoryError("demo_care_memory_root_must_be_absolute")
        _reject_tracked_memory(root)
        result = verify_demo_care_memory(root) if args.verify else seed_demo_care_memory(root)
    except DemoCareMemoryError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
