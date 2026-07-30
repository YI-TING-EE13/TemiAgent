#!/usr/bin/env python3
"""Keep managed Mosquitto lifecycle ownership verifiable across its UID drop.

The broker may intentionally drop from the lifecycle user to ``mosquitto``.
This small parent stays alive, relays TERM only to its direct child, and lets
the caller verify one exact parent PID before it requests a graceful stop.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import subprocess
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supervise one managed Mosquitto child.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    config = Path(args.config)
    if not config.is_absolute() or not config.is_file() or config.is_symlink():
        parser.error("--config must be an existing absolute regular file")

    child = subprocess.Popen(["mosquitto", "-c", str(config)])

    def forward_term(_signum: int, _frame: object) -> None:
        if child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, forward_term)
    signal.signal(signal.SIGINT, forward_term)
    while child.poll() is None:
        time.sleep(0.1)
    return int(child.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
