import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hermes_temi_bridge.logging_utils import EventJsonlLogger


ROOT = Path(__file__).resolve().parents[2]
VIEWER = ROOT / "tools" / "show_temi_trace.py"


class TraceViewerTests(unittest.TestCase):
    def test_json_output_is_clean_machine_readable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = seed_trace(Path(tmp) / "logs")

            completed = subprocess.run(
                [
                    sys.executable,
                    VIEWER.as_posix(),
                    "--log-dir",
                    log_dir.as_posix(),
                    "--latest",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            parsed = json.loads(completed.stdout)
            self.assertEqual(parsed["event_id"], "evt_viewer")
            self.assertEqual(parsed["latest_status"], "completed")
            self.assertEqual(completed.stderr, "")

    def test_default_and_full_outputs_are_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = seed_trace(Path(tmp) / "logs")

            summary = subprocess.run(
                [
                    sys.executable,
                    VIEWER.as_posix(),
                    "--log-dir",
                    log_dir.as_posix(),
                    "--latest",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            full = subprocess.run(
                [
                    sys.executable,
                    VIEWER.as_posix(),
                    "--log-dir",
                    log_dir.as_posix(),
                    "--event-id",
                    "evt_viewer",
                    "--full",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("event_id: evt_viewer", summary.stdout)
            self.assertIn("event_completed", summary.stdout)
            self.assertIn("--- seq=", full.stdout)
            self.assertIn('"home_esi_level": "Normal"', full.stdout)

    def test_completed_status_survives_duplicate_attempt_and_late_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = seed_trace_with_duplicate_and_late_result(Path(tmp) / "logs")

            summary = subprocess.run(
                [
                    sys.executable,
                    VIEWER.as_posix(),
                    "--log-dir",
                    log_dir.as_posix(),
                    "--latest",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            json_output = subprocess.run(
                [
                    sys.executable,
                    VIEWER.as_posix(),
                    "--log-dir",
                    log_dir.as_posix(),
                    "--latest",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("status: completed", summary.stdout)
            self.assertIn("duplicate_attempts: 1", summary.stdout)
            self.assertIn("command_result: success late_result: true", summary.stdout)
            parsed = json.loads(json_output.stdout)
            self.assertEqual(parsed["latest_status"], "completed")
            self.assertEqual(parsed["summary"]["duplicate_attempts"], 1)
            self.assertEqual(parsed["summary"]["command_result"], "success")
            self.assertTrue(parsed["summary"]["late_result"])


def seed_trace(log_dir: Path) -> Path:
    logger = EventJsonlLogger(log_dir, run_id="run_viewer")
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="asr.final",
        stage="event_received",
        status="started",
        payload={"asr_text": "hello"},
        index_status="started",
        index_summary={"asr_text": "hello"},
    )
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="asr.final",
        stage="event_completed",
        status="completed",
        payload={
            "home_esi_level": "Normal",
            "robot_action_types": ["speak"],
            "memory_action_types": [],
            "command_status": "published",
            "total_duration_ms": 3,
        },
        index_status="completed",
        index_summary={"home_esi_level": "Normal", "command_status": "published"},
    )
    return log_dir


def seed_trace_with_duplicate_and_late_result(log_dir: Path) -> Path:
    logger = EventJsonlLogger(log_dir, run_id="run_viewer")
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="asr.final",
        stage="event_received",
        status="started",
        payload={"asr_text": "hello"},
        index_status="started",
        index_summary={"asr_text": "hello"},
    )
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="asr.final",
        stage="event_completed",
        status="completed",
        payload={
            "home_esi_level": "Normal",
            "robot_action_types": ["speak"],
            "memory_action_types": [],
            "command_status": "published",
            "total_duration_ms": 3,
        },
        index_status="completed",
        index_summary={"home_esi_level": "Normal", "command_status": "published"},
    )
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="asr.final",
        stage="duplicate_event_ignored",
        status="ignored",
        payload={"reason": "duplicate_event_id"},
        index_status="ignored",
        index_summary={"reason": "duplicate_event_id"},
    )
    logger.write_trace(
        event_id="evt_viewer",
        robot_id="temi-01",
        source_type="command.result",
        stage="command_result_received",
        status="success",
        payload={
            "topic": "temi/temi-01/cmd/result",
            "command_result": {
                "command_id": "cmd_evt_viewer",
                "event_id": "evt_viewer",
                "robot_id": "temi-01",
                "status": "success",
            },
        },
    )
    return log_dir


if __name__ == "__main__":
    unittest.main()
