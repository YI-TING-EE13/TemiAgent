"""Tests for task-owned process groups and bounded timeout cleanup."""

from __future__ import annotations

import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from tools.bounded_process import run_bounded_command


def python_command(source: str, *arguments: str) -> list[str]:
    return [sys.executable, "-c", textwrap.dedent(source), *arguments]


def wait_for_pid_to_exit(pid: int, timeout_seconds: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not Path(f"/proc/{pid}").exists():
            return True
        time.sleep(0.02)
    return not Path(f"/proc/{pid}").exists()


class BoundedProcessTests(unittest.TestCase):
    def test_successful_command_returns_output_without_cleanup_signals(self) -> None:
        result = run_bounded_command(
            python_command("print('bounded-success')"),
            timeout_seconds=1,
            kill_grace_seconds=0.1,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.output, "bounded-success\n")
        self.assertFalse(result.timed_out)
        self.assertFalse(result.term_sent)
        self.assertFalse(result.hard_kill_sent)

    def test_failed_command_preserves_exit_status(self) -> None:
        result = run_bounded_command(
            python_command("raise SystemExit(17)"),
            timeout_seconds=1,
            kill_grace_seconds=0.1,
        )

        self.assertEqual(result.returncode, 17)
        self.assertFalse(result.timed_out)

    def test_timeout_uses_hard_kill_for_term_resistant_child_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temiagent-bounded-process-") as temp:
            child_pid_path = Path(temp) / "child.pid"
            command = python_command(
                """
                import signal
                import subprocess
                import sys
                import time
                child = subprocess.Popen([
                    sys.executable,
                    "-c",
                    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
                ])
                with open(sys.argv[1], "w", encoding="ascii") as handle:
                    handle.write(str(child.pid))
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                while True:
                    time.sleep(1)
                """,
                str(child_pid_path),
            )
            sentinel = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"]
            )
            try:
                result = run_bounded_command(
                    command,
                    timeout_seconds=0.3,
                    kill_grace_seconds=0.1,
                )

                self.assertTrue(result.timed_out)
                self.assertTrue(result.term_sent)
                self.assertTrue(result.hard_kill_sent)
                self.assertEqual(result.returncode, -signal.SIGKILL)
                self.assertTrue(child_pid_path.exists())
                child_pid = int(child_pid_path.read_text(encoding="ascii"))
                self.assertTrue(wait_for_pid_to_exit(child_pid))
                self.assertIsNone(sentinel.poll())
            finally:
                sentinel.terminate()
                sentinel.wait(timeout=2)

    def test_cooperative_timeout_needs_no_hard_kill(self) -> None:
        result = run_bounded_command(
            python_command("import time; time.sleep(30)"),
            timeout_seconds=0.1,
            kill_grace_seconds=0.2,
        )

        self.assertTrue(result.timed_out)
        self.assertTrue(result.term_sent)
        self.assertFalse(result.hard_kill_sent)
        self.assertLess(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
