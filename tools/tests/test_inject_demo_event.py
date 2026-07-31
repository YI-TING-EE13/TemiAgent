from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("inject_demo_event", ROOT / "tools" / "inject_demo_event.py")
assert SPEC is not None and SPEC.loader is not None
inject_demo_event = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inject_demo_event)


class InjectDemoEventTests(unittest.TestCase):
    def test_build_event_has_required_test_metadata_and_synthetic_jpegs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                event="falls_down",
                resident_id="test-resident",
                run_id="run-acceptance",
                scenario_id="A1",
                robot_id="temi-01",
                timestamp_ms=1785600000000,
            )
            topic, payload = inject_demo_event.build_event(args, Path(temporary))
            self.assertEqual(topic, "temi/temi-01/perception/abnormal")
            self.assertEqual(payload["event_type"], "falls_down")
            self.assertTrue(payload["context"]["test"])
            self.assertEqual(payload["context"]["run_id"], "run-acceptance")
            paths = payload["evidence"]["frame_paths"]
            self.assertEqual(len(paths), 3)
            self.assertTrue(all(Path(path).read_bytes().startswith(b"\xff\xd8") for path in paths))

    def test_build_event_rejects_unsafe_run_identifier(self) -> None:
        args = argparse.Namespace(
            event="fight",
            resident_id="test-resident",
            run_id="run/unsafe",
            scenario_id="A3",
            robot_id="temi-01",
            timestamp_ms=None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "run_id"):
                inject_demo_event.build_event(args, Path(temporary))


if __name__ == "__main__":
    unittest.main()
