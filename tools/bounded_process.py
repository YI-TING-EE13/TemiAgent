"""Run one external command in an owned process group with bounded cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class BoundedProcessResult:
    """Result and cleanup evidence for one bounded external command."""

    command: tuple[str, ...]
    returncode: int
    output: str
    timed_out: bool
    term_sent: bool
    hard_kill_sent: bool
    process_group_id: int


def _send_process_group_signal(process_group_id: int, signum: signal.Signals) -> bool:
    """Signal only the process group created for the task-owned command."""

    try:
        os.killpg(process_group_id, signum)
    except ProcessLookupError:
        return False
    return True


def _process_group_exists(process_group_id: int) -> bool:
    """Check whether the exact task-owned process group still exists."""

    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def _decode_output(output_file: tempfile._TemporaryFileWrapper[bytes]) -> str:
    """Read bounded command output from a regular temporary file."""

    output_file.seek(0)
    return output_file.read().decode("utf-8", errors="replace")


def run_bounded_command(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    kill_grace_seconds: float = 1.0,
) -> BoundedProcessResult:
    """Run one command with an isolated session and bounded cleanup.

    The child starts a new session, making its process group task-owned. On
    timeout the helper sends TERM to that group, waits a bounded grace period,
    then sends KILL to the same group before reaping the direct child. Output
    is redirected to a regular temporary file so an escaped pipe holder cannot
    make cleanup wait indefinitely.
    """

    normalized_command = tuple(str(part) for part in command)
    if not normalized_command:
        raise ValueError("bounded command must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if kill_grace_seconds <= 0:
        raise ValueError("kill_grace_seconds must be positive")

    with tempfile.TemporaryFile() as output_file:
        process = subprocess.Popen(
            normalized_command,
            stdin=subprocess.DEVNULL,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        timed_out = False
        term_sent = False
        hard_kill_sent = False

        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            term_sent = _send_process_group_signal(process.pid, signal.SIGTERM)

            grace_deadline = time.monotonic() + kill_grace_seconds
            while time.monotonic() < grace_deadline:
                if process.poll() is not None:
                    # Reap the direct child before checking whether a
                    # descendant still keeps this task-owned group alive.
                    process.wait()
                    break
                time.sleep(min(0.01, grace_deadline - time.monotonic()))

            # Do this before reaping the direct child so its PID cannot be
            # reused while the task-owned process group is being cleaned.
            if _process_group_exists(process.pid):
                hard_kill_sent = _send_process_group_signal(
                    process.pid, signal.SIGKILL
                )
            try:
                process.wait(timeout=kill_grace_seconds)
            except subprocess.TimeoutExpired:
                # This is still the exact Popen-owned PID, never a name
                # pattern. The group kill above remains the normal cleanup.
                process.kill()
                process.wait(timeout=max(kill_grace_seconds, 0.1))

        return BoundedProcessResult(
            command=normalized_command,
            returncode=process.returncode,
            output=_decode_output(output_file),
            timed_out=timed_out,
            term_sent=term_sent,
            hard_kill_sent=hard_kill_sent,
            process_group_id=process.pid,
        )
