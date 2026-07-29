import copy
import json
from pathlib import Path
import tempfile
import unittest

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.hermes_client import HermesResponse
from hermes_temi_bridge.idempotency import TTLProcessedEventCache
from hermes_temi_bridge.logging_utils import EventJsonlLogger, TRACE_STAGES
from hermes_temi_bridge.main import HermesTemiBridgeService


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def rewrite_frame_paths(payload: dict, bridge_root: Path) -> dict:
    event_id = payload["event_id"]
    for frame in payload["vision"]["frames"]:
        filename = {
            "t_minus_1000": "frame_t_minus_1000.jpg",
            "t_minus_500": "frame_t_minus_500.jpg",
            "t": "frame_t.jpg",
        }[frame["name"]]
        frame["path"] = (bridge_root / "events" / payload["robot_id"] / event_id / filename).as_posix()
    return payload


def create_images_for_payload(payload: dict) -> None:
    for frame in payload["vision"]["frames"]:
        path = Path(frame["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-jpeg")


def write_seed_memory(memory_root: Path) -> None:
    memory_root.mkdir(parents=True, exist_ok=True)
    (memory_root / "reminders.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "reminders": [
                    {
                        "reminder_id": "rem_morning_medication",
                        "status": "active",
                        "last_completed_at": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (memory_root / "daily_state.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "active_reminders": ["rem_morning_medication"],
                "recent_event_ids": [],
                "demo_flags": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (memory_root / "event_log.jsonl").write_text("", encoding="utf-8")


class MockMqtt:
    def __init__(self):
        self.published = []

    def publish_command(self, robot_id, payload):
        self.published.append((robot_id, payload))


class MockHermes:
    def __init__(self, raw_output, dispatch_metadata=None):
        self.raw_output = raw_output
        self.dispatch_metadata = dispatch_metadata

    def invoke(self, request):
        return HermesResponse(
            raw_output=self.raw_output,
            latency_ms=7,
            dispatch_metadata=self.dispatch_metadata,
        )


class Unstringable:
    def __str__(self):
        raise RuntimeError("str failed")

    def __repr__(self):
        raise RuntimeError("repr failed")


class TraceLoggingTests(unittest.TestCase):
    def test_resident_deterministic_dispatch_uses_existing_trace_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            dispatch = {
                "dispatch_mode": "deterministic_media_fast_path",
                "intent": "play_video",
                "video_id": "elderly_hand_exercise",
                "resident_id": "unknown",
                "callback_status": "published",
                "bridge_command_id": "cmd_fast_trace_001",
                "dispatch_latency_ms": 4,
            }
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                MockMqtt(),
                MockHermes(
                    (FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8"),
                    dispatch,
                ),
                TTLProcessedEventCache(600),
            )

            service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            records = read_trace(root / "logs", payload["event_id"])
            invocation = next(item for item in records if item["stage"] == "hermes_invocation_finished")
            self.assertEqual(invocation["payload"]["resident_dispatch"], dispatch)

    def test_trace_records_are_ordered_and_completed_summary_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                    trace_run_id="run_test",
                ),
                mqtt,
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            records = read_trace(root / "logs", payload["event_id"])
            seqs = [record["seq"] for record in records]
            self.assertEqual(seqs, sorted(seqs))
            self.assertTrue(all(record["stage"] in TRACE_STAGES for record in records))
            completed = records[-1]
            self.assertEqual(completed["stage"], "event_completed")
            self.assertEqual(completed["payload"]["home_esi_level"], "Normal")
            self.assertEqual(completed["payload"]["robot_action_types"], ["speak"])
            self.assertEqual(completed["payload"]["command_status"], "published")
            self.assertIsInstance(completed["payload"]["total_duration_ms"], int)

    def test_summary_mode_does_not_store_full_prompt_raw_output_or_asr_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                    trace_include_asr_text=False,
                    trace_max_field_chars=8,
                ),
                MockMqtt(),
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            records = read_trace(root / "logs", payload["event_id"])
            by_stage = {record["stage"]: record for record in records}
            asr_summary = by_stage["input_validated"]["payload"]["asr_text"]
            self.assertNotIn("text", asr_summary)
            self.assertEqual(asr_summary["excerpt"], "幫我看看桌上的東")
            self.assertTrue(asr_summary["truncated"])
            prompt_summary = by_stage["hermes_request_prepared"]["payload"]["prompt"]
            raw_summary = by_stage["hermes_invocation_finished"]["payload"]["raw_hermes_output"]
            self.assertNotIn("text", prompt_summary)
            self.assertNotIn("text", raw_summary)
            self.assertIn("sha256", prompt_summary)
            self.assertLessEqual(len(prompt_summary["excerpt"]), 8)

    def test_full_debug_stores_full_prompt_care_context_and_raw_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                    debug_trace_full=True,
                ),
                MockMqtt(),
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            by_stage = {record["stage"]: record for record in read_trace(root / "logs", payload["event_id"])}
            self.assertIn("text", by_stage["hermes_request_prepared"]["payload"]["prompt"])
            self.assertIn(
                "text",
                by_stage["hermes_invocation_finished"]["payload"]["raw_hermes_output"],
            )
            care_context = by_stage["care_context_built"]["payload"]["care_context"]
            self.assertIn("value", care_context)

    def test_trace_disabled_preserves_bridge_behavior_without_trace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                    trace_enabled=False,
                ),
                mqtt,
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(len(mqtt.published), 1)
            self.assertFalse((root / "logs").exists())

    def test_invalid_hermes_json_records_complete_failure_payload_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                mqtt,
                MockHermes("not json"),
                TTLProcessedEventCache(600),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "failed")
            self.assertEqual(len(mqtt.published), 1)
            failed = read_trace(root / "logs", payload["event_id"])[-1]
            self.assertEqual(failed["stage"], "event_failed")
            failure_payload = failed["payload"]
            self.assertEqual(failure_payload["failed_stage"], "hermes_output_validated")
            self.assertEqual(failure_payload["error_code"], "invalid_hermes_json")
            self.assertEqual(failure_payload["error_message"], "invalid_hermes_json")
            self.assertTrue(failure_payload["fallback_generated"])
            self.assertTrue(failure_payload["fallback_command_published"])
            self.assertIsNotNone(failure_payload["fallback_command_id"])
            self.assertIn("fallback_command", failure_payload)
            self.assertIn("raw_output", failure_payload["details"])

    def test_command_result_received_can_append_after_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                mqtt,
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )
            service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))
            max_seq = max(record["seq"] for record in read_trace(root / "logs", payload["event_id"]))
            late_service = HermesTemiBridgeService(
                BridgeConfig(log_dir=(root / "logs").as_posix()),
                MockMqtt(),
                MockHermes("{}"),
                TTLProcessedEventCache(600),
                EventJsonlLogger(root / "logs"),
            )

            late_service.handle_command_result(
                "temi/temi-01/cmd/result",
                {
                    "schema_version": "1.0",
                    "command_id": mqtt.published[0][1]["command_id"],
                    "event_id": payload["event_id"],
                    "robot_id": "temi-01",
                    "status": "success",
                    "results": [{"action_id": "act_001", "type": "speak", "status": "success"}],
                },
            )

            records = read_trace(root / "logs", payload["event_id"])
            self.assertEqual(records[-1]["stage"], "command_result_received")
            self.assertEqual(records[-1]["seq"], max_seq + 1)

    def test_trace_file_write_failure_does_not_block_publish_or_memory_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_log_dir = root / "not_a_directory"
            bad_log_dir.write_text("blocks directory creation", encoding="utf-8")
            memory_root = root / "memory"
            write_seed_memory(memory_root)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=bad_log_dir.as_posix(),
                    memory_dir=memory_root.as_posix(),
                ),
                mqtt,
                MockHermes((FIXTURES / "hermes_output_valid_memory_actions.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(len(mqtt.published), 1)
            self.assertEqual([item["type"] for item in result["memory_action_results"]], ["mark_reminder_done", "log_event"])
            self.assertTrue((memory_root / "event_log.jsonl").read_text(encoding="utf-8").strip())

    def test_trace_index_write_failure_does_not_block_event_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_dir = root / "logs"
            (log_dir / "_index.jsonl").mkdir(parents=True)
            logger = EventJsonlLogger(log_dir)

            path = logger.write_trace(
                event_id="evt_index_failure",
                robot_id="temi-01",
                source_type="asr.final",
                stage="event_received",
                status="started",
                payload={"asr_text": "hello"},
                index_status="started",
                index_summary={"asr_text": "hello"},
            )

            self.assertTrue(path.exists())
            records = read_trace(log_dir, "evt_index_failure")
            self.assertEqual(records[0]["stage"], "event_received")

    def test_sanitizer_failure_does_not_block_bridge_main_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = rewrite_frame_paths(load_fixture("asr_final_valid.json"), root / "temi_shared")
            payload["context"]["unserializable"] = Unstringable()
            create_images_for_payload(payload)
            mqtt = MockMqtt()
            service = HermesTemiBridgeService(
                BridgeConfig(
                    temi_shared_bridge_path=(root / "temi_shared").as_posix(),
                    temi_shared_hermes_path="/shared/temi",
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                ),
                mqtt,
                MockHermes((FIXTURES / "hermes_output_valid_speak.json").read_text(encoding="utf-8")),
                TTLProcessedEventCache(600),
            )

            result = service.handle_asr_payload("temi/temi-01/asr/final", copy.deepcopy(payload))

            self.assertEqual(result["status"], "success")
            self.assertEqual(len(mqtt.published), 1)
            records = read_trace(root / "logs", payload["event_id"])
            self.assertEqual(records[-1]["stage"], "event_completed")


def read_trace(log_dir: Path, event_id: str) -> list[dict]:
    path = log_dir / f"{event_id}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
