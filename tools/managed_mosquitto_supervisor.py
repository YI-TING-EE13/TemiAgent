#!/usr/bin/env python3
"""Keep managed Mosquitto lifecycle ownership verifiable across its UID drop.

The broker may intentionally drop from the lifecycle user to ``mosquitto``.
This small parent stays alive, relays TERM only to its direct child, and lets
the caller verify one exact parent PID before it requests a graceful stop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time


CHILD_STATE_SCHEMA = "temiagent.mosquitto_child.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_mosquitto_executable() -> tuple[str, str]:
    """Resolve and fingerprint the exact broker binary before spawning it."""
    executable = shutil.which("mosquitto")
    if executable is None:
        raise RuntimeError("mosquitto executable was not found on PATH")
    resolved = Path(os.path.realpath(executable))
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError("mosquitto executable is not an executable regular file")
    return str(resolved), _sha256(resolved)


def _limited_child_identity(pid: int) -> dict[str, object]:
    """Read the child fields that remain visible after Mosquitto drops UID."""
    proc = Path("/proc") / str(pid)
    stat_text = (proc / "stat").read_text(encoding="utf-8")
    end = stat_text.rfind(")")
    if end < 0:
        raise RuntimeError(f"PID {pid} has an invalid /proc stat record")
    fields = stat_text[end + 2 :].split()
    if len(fields) < 20:
        raise RuntimeError(f"PID {pid} has an incomplete /proc stat record")
    raw_cmdline = (proc / "cmdline").read_bytes()
    command = [part.decode("utf-8", "replace") for part in raw_cmdline.split(b"\0") if part]
    if not command:
        raise RuntimeError(f"PID {pid} has an empty command line")
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "start_ticks": int(fields[19]),
        "cmdline": command,
        "cmdline_sha256": hashlib.sha256(raw_cmdline).hexdigest(),
    }


def _write_child_state(path: Path, payload: dict[str, object]) -> None:
    """Atomically publish one owner-only child contract for the lifecycle."""
    if not path.is_absolute() or not path.parent.is_dir():
        raise RuntimeError("--child-state-path must be an absolute path in an existing directory")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError("--child-state-path must not be a symlink or non-file")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def _abort_child(child: subprocess.Popen[object]) -> None:
    """Terminate only the exact Popen child if contract publication fails."""
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    """Supervise one Mosquitto child while preserving an exact parent identity."""

    parser = argparse.ArgumentParser(description="Supervise one managed Mosquitto child.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", help="opaque lifecycle startup correlation marker")
    parser.add_argument("--child-state-path", help="private lifecycle path for the exact child contract")
    args = parser.parse_args(argv)
    config = Path(args.config)
    if not config.is_absolute() or not config.is_file() or config.is_symlink():
        parser.error("--config must be an existing absolute regular file")
    if bool(args.run_id) != bool(args.child_state_path):
        parser.error("--run-id and --child-state-path must be supplied together")

    try:
        mosquitto_executable, executable_sha256 = _resolve_mosquitto_executable()
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    child_command = [mosquitto_executable, "-c", str(config)]
    child = subprocess.Popen(child_command)
    if args.child_state_path is not None:
        try:
            child_identity = _limited_child_identity(child.pid)
            if (
                child_identity.get("pid") != child.pid
                or child_identity.get("ppid") != os.getpid()
                or child_identity.get("cmdline") != child_command
            ):
                raise RuntimeError("Mosquitto child did not match the direct-child contract")
            _write_child_state(
                Path(args.child_state_path),
                {
                    "schema_version": CHILD_STATE_SCHEMA,
                    "run_id": args.run_id,
                    "supervisor_pid": os.getpid(),
                    "executable": mosquitto_executable,
                    "executable_sha256": executable_sha256,
                    **child_identity,
                },
            )
        except BaseException:
            _abort_child(child)
            raise

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
