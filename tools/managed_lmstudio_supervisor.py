#!/usr/bin/env python3
"""Keep LM Studio lifecycle ownership verifiable after startup completes.

The existing startup script is intentionally retained as the reviewed model
loader. It exits after loading the model, so this parent remains alive as the
exact lifecycle PID and performs only the approved graceful ``lms`` shutdown.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import time


def _shutdown(target_dir: Path, identifier: str) -> None:
    executable = target_dir / "bin" / "lms"
    if not executable.is_file():
        return
    for args in (("unload", identifier), ("server", "stop"), ("daemon", "down")):
        try:
            subprocess.run([str(executable), *args], check=False, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supervise a managed LM Studio run.")
    parser.add_argument("--startup-script", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--identifier", required=True)
    args = parser.parse_args(argv)
    startup_script = Path(args.startup_script)
    target_dir = Path(args.target_dir)
    if not startup_script.is_absolute() or not startup_script.is_file() or startup_script.is_symlink():
        parser.error("--startup-script must be an existing absolute regular file")
    if not target_dir.is_absolute() or target_dir.is_symlink():
        parser.error("--target-dir must be an absolute non-symlink directory")

    stopping = False
    startup = subprocess.Popen([str(startup_script)], env=os.environ.copy())

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        if startup.poll() is None:
            startup.terminate()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while startup.poll() is None:
        time.sleep(0.1)
    if startup.returncode:
        return int(startup.returncode)
    while not stopping:
        time.sleep(0.1)
    _shutdown(target_dir, args.identifier)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
