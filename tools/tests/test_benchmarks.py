"""Hardware-free tests for shared cases and the reasoning benchmark protocol."""

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout, redirect_stderr

from tools.benchmarks import test_reasoning as bench
from tools.benchmarks import test_action_selection as action
from tools.benchmarks.dataset import DEFAULT_DATASET, load_cases


def good_trace():
    return [
        {"stage": "hermes_invocation_finished", "status": "ok", "payload": {"hermes_latency_ms": 100}},
        {"stage": "hermes_output_validated", "status": "ok"},
        {"stage": "event_completed", "status": "ok"},
    ]


class FakeCapture:
    def __init__(self, *args):
        self.commands = {}
        self.received_times = {}
        self.published_times = {}
        self.stopped = False

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def publish(self, event):
        event_id = event["event_id"]
        self.published_times[event_id] = 1.0
        self.received_times[event_id] = 1.125
        self.commands[event_id] = {"event_id": event_id, "actions": [{"type": "speak", "text": "已記錄。"}]}

    def wait_for_event(self, event_id, timeout):
        return self.commands[event_id]


class BenchmarkTests(unittest.TestCase):
    def test_shared_dataset_and_rejected_extensions(self):
        cases = load_cases()
        manifest = json.loads(DEFAULT_DATASET.with_name("dataset.json").read_text())
        self.assertEqual(len(cases), manifest["case_count"])
        self.assertEqual([case.case_id for case in cases], [f"BP-{i:02d}" for i in range(1, 21)] + [f"SYM-{i:02d}" for i in range(1, 4)])
        self.assertEqual(cases[7].text, "幫我記錄影壓舒張壓93，心跳91")
        original = json.loads(DEFAULT_DATASET.read_text().splitlines()[0])
        for change in ("duplicate", "multiturn", "empty", "path", "state", "malformed"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                item = copy.deepcopy(original)
                if change == "multiturn":
                    item["turns"].append({"role": "user", "text": "下一句"})
                elif change == "empty":
                    item["turns"][0]["text"] = " "
                elif change == "path":
                    item["case_id"] = "../../escape"
                elif change == "state":
                    item["preconditions"] = {"memory": "ignored?"}
                content = json.dumps(item)
                if change == "duplicate":
                    content += "\n" + content
                elif change == "malformed":
                    content = "not json"
                path = Path(temporary) / "cases.jsonl"
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_cases(path)

    def test_default_offline_and_live_missing_metadata_do_not_publish(self):
        for arguments, expected in (([], 0), (["--live"], 2), (["--repeat", "0"], 2)):
            with self.subTest(arguments=arguments), mock.patch.object(bench, "run_benchmark") as live, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(bench.main(arguments), expected)
                live.assert_not_called()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            bench.build_parser().parse_args(["--compare", "old-run"])
        self.assertEqual(error.exception.code, 2)

    def test_subscriber_waits_for_subscription_ack_and_preserves_first_receipt(self):
        capture = object.__new__(action.CommandCapture)
        capture.ready = mock.Mock()
        capture.robot_id = "test-robot"
        capture.messages = []
        capture.received_times = {}
        client = mock.Mock()
        capture._on_connect(client, None, None, 0, None)
        client.subscribe.assert_called_once_with("temi/test-robot/cmd/request", qos=1)
        capture.ready.set.assert_not_called()
        capture._on_subscribe(client, None, 1, [type("Code", (), {"is_failure": False})()], None)
        capture.ready.set.assert_called_once()
        message = type("Message", (), {"payload": b'{"event_id":"evt_1","actions":[]}'})()
        with mock.patch.object(action.time, "perf_counter", side_effect=[1.25, 2.5]):
            capture._on_message(client, None, message)
            capture._on_message(client, None, message)
        self.assertEqual(capture.received_times["evt_1"], 1.25)

    def test_measurement_separates_fallback_validation_and_dispatch(self):
        row = {"event_id": "evt_1", "response_action_consistency": "CONSISTENT"}
        capture = FakeCapture()
        capture.publish({"event_id": "evt_1"})
        measured = bench.measurement(row, capture, good_trace())
        self.assertTrue(measured["valid_output"])
        self.assertEqual(measured["dispatch_latency_ms"], 125)
        self.assertEqual(measured["hermes_latency_ms"], 100)
        for change in ("fallback", "failed", "missing", "fastpath", "invalid_latency"):
            with self.subTest(change=change):
                trace = copy.deepcopy(good_trace())
                capture.commands["evt_1"].pop("fallback_reason", None)
                if change == "fallback":
                    capture.commands["evt_1"]["fallback_reason"] = "missing_event_type"
                elif change == "failed":
                    trace.append({"stage": "event_failed", "payload": {"failed_stage": "memory_actions_completed"}})
                elif change == "missing":
                    trace = []
                elif change == "fastpath":
                    trace[0]["payload"]["resident_dispatch"] = {"intent": "fixed"}
                elif change == "invalid_latency":
                    trace[0]["payload"]["hermes_latency_ms"] = float("nan")
                self.assertFalse(bench.measurement(row, capture, trace)["valid_output"])

    def runtime_fixtures(self, root):
        args = bench.build_parser().parse_args([
            "--live", "--model", "alias", "--model-key", "loaded-key", "--reasoning-effort", "none",
            "--resident-pid", "123", "--bridge-pid", "456", "--broker", "localhost",
            "--shared-root", str(root), "--bridge-root", str(root), "--trace-dir", str(root / "trace")])
        identity = {"pid": 123, "cwd": str(root), "exe": "python", "start_ticks": "100"}
        env = {"HERMES_INVOKE_MODE": "http", "HERMES_HTTP_URL": "http://127.0.0.1:8765/invoke",
               "CARE_CONTEXT_ENABLED": "false", "LOG_DIR": str(root / "trace"),
               "TEMI_SHARED_BRIDGE_PATH": str(root)}
        health = {"status": "ok", "model": "alias", "context_length": 64000,
                  "compression_context_length": 64000, "base_url": "http://127.0.0.1:1234/v1"}
        native = {"models": [{"key": "loaded-key", "type": "llm", "loaded_instances": [
            {"id": "alias", "config": {"context_length": 64000}}]}]}
        return args, identity, env, health, native

    def test_preflight_accepts_only_matching_live_evidence(self):
        for change in (None, "auto", "effort", "model", "context", "care_context", "listener", "loaded", "multiple"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                args, identity, env, health, native = self.runtime_fixtures(Path(temporary))
                effort = "default" if change == "effort" else "none"
                if change == "auto":
                    args.model = args.model_key = args.context_length = args.reasoning_effort = None
                elif change == "model":
                    health["model"] = "wrong"
                elif change == "context":
                    native["models"][0]["loaded_instances"][0]["config"]["context_length"] = 4096
                elif change == "care_context":
                    env["CARE_CONTEXT_ENABLED"] = "true"
                elif change == "loaded":
                    native["models"][0]["loaded_instances"] = []
                elif change == "multiple":
                    native["models"][0]["loaded_instances"] *= 2
                with (
                    mock.patch.object(bench, "process", side_effect=[(identity, ["--reasoning-effort", effort], {}), (identity, [], env)]),
                    mock.patch.object(bench, "get_json", side_effect=[health, native]),
                    mock.patch.object(bench.subprocess, "check_output", return_value="LISTEN users:((python,pid=999,fd=1))\n" if change == "listener" else "LISTEN users:((python,pid=123,fd=1))\n"),
                ):
                    if change not in (None, "auto"):
                        with self.assertRaises(ValueError):
                            bench.verify_runtime(args)
                    else:
                        observed = bench.verify_runtime(args)
                        self.assertEqual(observed["loaded_model"]["id"], "loaded-key")
                        self.assertEqual(observed["reasoning_effort"], "none")
                        self.assertEqual(observed["context_length"], 64000)

    def test_fake_end_to_end_warmup_repetitions_and_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, *_ = self.runtime_fixtures(root)
            args.output_root = root / "output"
            args.shared_root = root / "shared"
            args.repeat = 2
            args.delay = 0
            cases = load_cases()[:2]
            metadata = {"loaded_model": {"id": "loaded-key"}, "reasoning_effort": "none", "context_length": 64000}
            with (
                mock.patch.object(bench, "verify_runtime", return_value=metadata),
                mock.patch.object(bench, "TimedCapture", FakeCapture),
                mock.patch.object(bench, "read_trace", return_value=good_trace()),
                redirect_stdout(io.StringIO()),
            ):
                directory = bench.run_benchmark(args, cases)
            rows = [json.loads(line) for line in (directory / "results.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual(sum(row["warmup"] for row in rows), 1)
            self.assertEqual(len({row["event_id"] for row in rows}), 5)
            summary = json.loads((directory / "metadata.json").read_text())["summary"]
            self.assertEqual(summary["valid_outputs"], 4)
            self.assertAlmostEqual(summary["hermes"]["mean_s"], .1)
            self.assertTrue((directory / "results.csv").is_file())
            self.assertTrue((directory / "summary.md").is_file())

    def test_failure_retains_partial_results_and_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, *_ = self.runtime_fixtures(root)
            args.output_root = root / "output"
            with (
                mock.patch.object(bench, "verify_runtime", return_value={}),
                mock.patch.object(action, "run_live", side_effect=KeyboardInterrupt),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    bench.run_benchmark(args, load_cases()[:1])
            directory = next(args.output_root.iterdir())
            self.assertEqual(json.loads((directory / "metadata.json").read_text())["status"], "interrupted")
            self.assertTrue((directory / "summary.md").exists())

    def test_summary_excludes_warmup_and_invalid_outputs(self):
        base = {"warmup": False, "valid_output": True, "inference_completed": True,
                "response_action_consistency": "CONSISTENT", "hermes_latency_ms": 1000, "dispatch_latency_ms": 1100}
        rows = [base, {**base, "warmup": True, "hermes_latency_ms": 10000},
                {**base, "valid_output": False, "hermes_latency_ms": 1}]
        summary = bench.summarize(rows)
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["hermes"]["n"], 1)
        self.assertEqual(summary["hermes"]["mean_s"], 1)


if __name__ == "__main__":
    unittest.main()
