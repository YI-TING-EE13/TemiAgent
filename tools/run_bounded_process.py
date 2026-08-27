#!/usr/bin/env python3
"""CLI wrapper for a task-owned, bounded external command."""

from __future__ import annotations

import argparse
import sys

from bounded_process import run_bounded_command


def parse_args() -> argparse.Namespace:
    """Parse timeout controls and the command after the separator."""

    parser = argparse.ArgumentParser(
        description="Run one command in an owned process group with bounded cleanup."
    )
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--kill-grace-seconds", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("provide a command after --")
    return args


def main() -> int:
    """Run the command and map a timeout to status 124."""

    args = parse_args()
    try:
        result = run_bounded_command(
            args.command,
            timeout_seconds=args.timeout_seconds,
            kill_grace_seconds=args.kill_grace_seconds,
        )
    except OSError as exc:
        print(f"BOUNDED_PROCESS_START_FAILED: {exc}", file=sys.stderr)
        return 127

    sys.stdout.write(result.output)
    if result.timed_out:
        print(
            "PROCESS_TIMEOUT: command exceeded "
            f"{args.timeout_seconds:g}s; TERM sent to process group "
            f"{result.process_group_id}",
            file=sys.stderr,
        )
        if result.hard_kill_sent:
            print(
                "PROCESS_HARD_KILL: KILL sent to the same task-owned process group",
                file=sys.stderr,
            )
        return 124
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
