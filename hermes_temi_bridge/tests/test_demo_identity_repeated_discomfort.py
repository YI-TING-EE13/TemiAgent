"""No-hardware tests for Demo identity and repeated-discomfort runtime wiring."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.demo_care_memory import seed_demo_care_memory
from hermes_temi_bridge.demo_identity import DemoIdentityController
from hermes_temi_bridge.hermes_demo_tools import (
    HermesDemoIdentityToolCallback,
    HermesRepeatedDiscomfortToolCallback,
)
from hermes_temi_bridge.main import HermesTemiBridgeService
from hermes_temi_bridge.memory_store import StructuredMemoryStore
from hermes_temi_bridge.mqtt_client import TemiMqttClient
from hermes_temi_bridge.resident_context import ResidentContextStore


ROOT = Path(__file__).resolve().parents[2]
RESIDENT_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("demo_identity_resident_server", RESIDENT_PATH)
resident_server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(resident_server)

LIFECYCLE_PATH = ROOT / "tools" / "demo_lifecycle.py"
LIFECYCLE_SPEC = importlib.util.spec_from_file_location("demo_identity_lifecycle", LIFECYCLE_PATH)
demo_lifecycle = importlib.util.module_from_spec(LIFECYCLE_SPEC)
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
sys.modules[LIFECYCLE_SPEC.name] = demo_lifecycle
LIFECYCLE_SPEC.loader.exec_module(demo_lifecycle)


class RecordingMqtt:
    def __init__(self) -> None:
        self.identity_results: list[tuple[str, dict]] = []
        self.commands: list[tuple[str, dict]] = []

    def publish_identity_result(self, robot_id: str, payload: dict) -> None:
        self.identity_results.append((robot_id, dict(payload)))

    def publish_command(self, robot_id: str, payload: dict) -> None:
        self.commands.append((robot_id, dict(payload)))


def manual_identity(status: str, event_id: str = "identity_001") -> dict:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "resident_id": None if status == "unknown" else status,
        "display_name": status,
        "identity_status": status,
        "confidence": 0.0 if status == "unknown" else 1.0,
        "source": "unknown" if status == "unknown" else "manual_selection",
        "reason": "controlled Demo test",
        "timestamp": "2026-07-29T10:00:00+00:00",
    }


class DemoIdentityBridgeTests(unittest.TestCase):
    def make_service(self, root: Path) -> tuple[HermesTemiBridgeService, RecordingMqtt]:
        mqtt = RecordingMqtt()
        config = BridgeConfig(
            log_dir=(root / "logs").as_posix(),
            care_context_enabled=False,
            demo_operator_identity_enabled=True,
            demo_repeated_discomfort_enabled=True,
            demo_care_memory_root=(root / "care").as_posix(),
            hermes_demo_identity_callback_socket=(root / "identity.sock").as_posix(),
            hermes_demo_care_callback_socket=(root / "care.sock").as_posix(),
            demo_identity_state_dir=(root / "identity-state").as_posix(),
            demo_identity_refresh_seconds=10,
            demo_identity_max_duration_seconds=60,
        )
        return HermesTemiBridgeService(config, mqtt, object()), mqtt

    def test_manual_selection_is_opt_in_and_publishes_existing_contract(self) -> None:
        payload = manual_identity("father")
        blocked = ResidentContextStore().update_from_identity_result(
            robot_id="temi-01", payload=payload, enabled=False
        )
        self.assertEqual(blocked.resident_id, "unknown")
        admitted = ResidentContextStore().update_from_identity_result(
            robot_id="temi-01", payload=payload, enabled=False, operator_identity_enabled=True
        )
        self.assertEqual(admitted.resident_id, "father")
        with tempfile.TemporaryDirectory() as temporary:
            service, mqtt = self.make_service(Path(temporary))
            externally_published = service.handle_identity_payload(
                "temi/temi-01/resident/identity/result", manual_identity("father", "external_manual")
            )
            self.assertEqual(externally_published["active_resident"]["resident_id"], "unknown")
            callback = HermesDemoIdentityToolCallback(
                service._identity_controller, allowed_robot_ids=("temi-01",)  # type: ignore[arg-type]
            )
            result = callback.invoke(
                {
                    "action": "start_demo_identity",
                    "event_id": "evt_operator_father",
                    "robot_id": "temi-01",
                    "identity_status": "father",
                }
            )
            self.assertEqual(result["status"], "published")
            self.assertEqual(mqtt.identity_results[0][0], "temi-01")
            published = mqtt.identity_results[0][1]
            self.assertEqual(published["source"], "manual_selection")
            self.assertEqual(published["identity_status"], "father")
            self.assertEqual(service._active_resident("temi-01").resident_id, "father")
            stopped = callback.invoke(
                {"action": "stop_demo_identity", "event_id": "evt_operator_unknown", "robot_id": "temi-01"}
            )
            self.assertEqual(stopped["identity_status"], "unknown")
            self.assertEqual(mqtt.identity_results[-1][1]["resident_id"], None)
            self.assertEqual(mqtt.identity_results[-1][1]["source"], "unknown")

    def test_controller_does_not_restore_stale_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            (state / "current.json").write_text('{"identity_status":"father"}\n', encoding="utf-8")
            published: list[tuple[str, str]] = []
            controller = DemoIdentityController(
                robot_id="temi-01",
                state_dir=state,
                publish=lambda status, reason, event_id: published.append((status, reason)) or {"status": "published"},
                refresh_seconds=10,
                max_duration_seconds=60,
            )
            self.assertEqual(controller.status()["identity_status"], "unknown")
            controller.start("father", trigger_event_id="evt_001")
            controller.stop(trigger_event_id="evt_002")
            self.assertEqual([item[0] for item in published], ["father", "unknown"])

    def test_repeated_discomfort_reads_father_only_and_writes_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_demo_care_memory(root / "care", session_at=datetime(2026, 7, 29, 12, tzinfo=UTC))
            service, _ = self.make_service(root)
            service.publish_demo_identity_result(
                robot_id="temi-01", identity_status="father", reason="test", trigger_event_id="identity_father"
            )
            callback_traces: list[tuple[str, dict]] = []
            callback = HermesRepeatedDiscomfortToolCallback(
                service._repeated_discomfort_controller,
                allowed_robot_ids=("temi-01",),
                trace_callback=lambda action, _event_id, _robot_id, result: callback_traces.append((action, result)),
            )
            base = {"robot_id": "temi-01", "resident_id": "father"}
            retrieved = callback.invoke({**base, "action": "retrieve_repeated_discomfort", "event_id": "evt_unwell"})
            self.assertEqual(retrieved["status"], "retrieved")
            self.assertEqual(retrieved["prior_event"]["event_id"], "demo_father_headache_two_days_ago")
            confirmed = callback.invoke({**base, "action": "confirm_repeated_headache", "event_id": "evt_confirm"})
            self.assertEqual(confirmed["status"], "confirmed")
            recorded = callback.invoke(
                {
                    **base,
                    "action": "record_repeated_blood_pressure",
                    "event_id": "evt_bp",
                    "systolic": 128,
                    "diastolic": 78,
                    "asr_text": "血壓128/78",
                }
            )
            self.assertEqual(recorded["status"], "recorded")
            self.assertEqual(recorded["prior_event_id"], "demo_father_headache_two_days_ago")
            self.assertEqual(callback_traces[0][1]["prior_event"]["event_id"], "demo_father_headache_two_days_ago")
            self.assertEqual(callback_traces[-1][1]["event_id"], "evt_bp")
            father_events = StructuredMemoryStore(root / "care" / "father")._read_event_log()
            mother_events = StructuredMemoryStore(root / "care" / "mother")._read_event_log()
            self.assertEqual(father_events[-1]["event_id"], "evt_bp")
            self.assertEqual(father_events[-1]["details"]["blood_pressure"], {"systolic": 128, "diastolic": 78, "unit": "mmHg", "source": "user_reported"})
            self.assertEqual(mother_events, [])
            rejected = callback.invoke({**base, "action": "record_repeated_blood_pressure", "event_id": "evt_again", "systolic": 128, "diastolic": 78, "asr_text": "血壓128/78"})
            self.assertEqual(rejected["error_code"], "DEMO_BLOOD_PRESSURE_NOT_PENDING")


class FakeTools:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    @contextmanager
    def invocation_context(self, context):
        yield

    def invoke_registered_identity_tool(self, action, args):
        self.calls.append((action, args))
        return dict(self.response)

    def invoke_registered_repeated_discomfort_tool(self, action, args):
        self.calls.append((action, args))
        return dict(self.response)


class FakeAgent:
    def chat(self, prompt):
        return "model output"


class ResidentFastPathTests(unittest.TestCase):
    def make_resident(self):
        resident = object.__new__(resident_server.ResidentHermes)
        resident._lock = threading.Lock()
        resident.request_count = 0
        resident.media_fast_path_enabled = False
        resident._media_tools = None
        resident.identity_fast_path_enabled = True
        resident.repeated_discomfort_fast_path_enabled = True
        resident._identity_tools = FakeTools({"status": "published", "identity_status": "father"})
        resident._repeated_discomfort_tools = FakeTools({"status": "retrieved", "prior_event": {"event_id": "demo_father_headache_two_days_ago", "timestamp": "2026-07-27T17:00:00+00:00"}})
        resident._agent = FakeAgent()
        return resident

    def test_exact_operator_and_father_flow_matchers_never_infer_identity(self) -> None:
        self.assertEqual(resident_server.match_demo_identity_intent("小安小安，Demo切換為爸爸。").identity_status, "father")
        self.assertEqual(resident_server.match_demo_identity_intent("小安小安，進入示範管理模式，持續發布王先生身分。").identity_status, "father")
        self.assertEqual(resident_server.match_demo_identity_intent("小安小安，示範模式切換到王太太。").identity_status, "mother")
        self.assertEqual(resident_server.match_demo_identity_intent("Demo 管理，清除目前身分。").action, "stop_demo_identity")
        self.assertEqual(resident_server.match_demo_identity_intent("小安小安，目前示範身分是誰？").action, "get_demo_identity_status")
        self.assertIsNone(resident_server.match_demo_identity_intent("我是王先生"))
        self.assertIsNone(resident_server.match_demo_identity_intent("切換為爸爸"))
        self.assertEqual(resident_server.match_repeated_discomfort_intent("今天又不太舒服").action, "retrieve_repeated_discomfort")
        self.assertEqual(resident_server.match_repeated_discomfort_intent("也是頭痛").action, "confirm_repeated_headache")
        for transcript in ("血壓128/78", "我量好了，血壓是 128/78", "我量到128跟78", "收縮壓128，舒張壓78"):
            blood_pressure = resident_server.match_repeated_discomfort_intent(transcript)
            self.assertEqual((blood_pressure.systolic, blood_pressure.diastolic), (128, 78))
        self.assertIsNone(resident_server.match_repeated_discomfort_intent("血壓大概128/78"))
        retrieval_text = resident_server._retrieved_discomfort_text({"prior_event": {"event_id": "demo_father_headache_two_days_ago", "timestamp": "2026-07-27T17:00:00+00:00"}})
        self.assertIn("5:00", retrieval_text)
        self.assertIn("頭痛", retrieval_text)

    def test_identity_and_repeated_routes_do_not_call_model(self) -> None:
        resident = self.make_resident()
        identity = resident.invoke("ignored", {"event_id": "evt_i", "robot_id": "temi-01"}, asr_text="Demo切換為爸爸")
        self.assertEqual(json.loads(identity["raw_output"])["actions"][0]["text"], "Demo 身分已切換為爸爸。")
        repeated = resident.invoke("ignored", {"event_id": "evt_r", "robot_id": "temi-01", "resident_id": "father"}, asr_text="我又不舒服了")
        self.assertIn("頭痛", json.loads(repeated["raw_output"])["actions"][0]["text"])
        no_father = resident.invoke("normal", {"event_id": "evt_u", "robot_id": "temi-01", "resident_id": "unknown"}, asr_text="我又不舒服了")
        self.assertEqual(no_father["raw_output"], "model output")


class DemoLifecycleFeatureConfigTests(unittest.TestCase):
    def test_private_config_requires_external_identity_and_care_callback_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime"
            config_path = root / "demo.env"
            config_path.write_text(
                "\n".join(
                    [
                        f"TEMIAGENT_RUNTIME_ROOT={runtime}",
                        "MQTT_BROKER_HOST=127.0.0.1",
                        "MQTT_BROKER_PORT=1883",
                        "ROBOT_ID_ALLOWLIST=temi-01",
                        f"TEMI_SHARED_BRIDGE_PATH={runtime}/data/shared",
                        f"TEMI_SHARED_HERMES_PATH={runtime}/data/shared",
                        "HERMES_INVOKE_MODE=http",
                        "HERMES_HTTP_URL=http://127.0.0.1:8765/invoke",
                        f"LOG_DIR={runtime}/logs/bridge",
                        f"MEMORY_DIR={runtime}/data/care-memory",
                        f"DEMO_CARE_MEMORY_ROOT={runtime}/data/care-memory",
                        f"HERMES_MEDIA_CALLBACK_SOCKET={runtime}/tmp/sockets/media.sock",
                        f"HERMES_DEMO_IDENTITY_CALLBACK_SOCKET={runtime}/tmp/sockets/identity.sock",
                        f"HERMES_DEMO_CARE_CALLBACK_SOCKET={runtime}/tmp/sockets/care.sock",
                        f"DEMO_IDENTITY_STATE_DIR={runtime}/state/demo-identity",
                        "MEDIA_V11_ENABLED=true",
                        "HERMES_MEDIA_TOOL_ENABLED=true",
                        "HERMES_MEDIA_FAST_PATH_ENABLED=true",
                        "RESIDENT_IDENTITY_ENABLED=true",
                        "HERMES_DEMO_IDENTITY_TOOL_ENABLED=true",
                        "HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true",
                        "CARE_MEMORY_V2_ENABLED=true",
                        "DEMO_REPEATED_DISCOMFORT_ENABLED=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config_path.chmod(0o600)
            config = demo_lifecycle.load_config(config_path)
            self.assertTrue(config.operator_identity_enabled)
            self.assertTrue(config.identity_tool_enabled)
            self.assertTrue(config.identity_fast_path_enabled)
            self.assertTrue(config.care_memory_v2_enabled)
            self.assertTrue(config.repeated_discomfort_enabled)
            self.assertEqual(len(config.callback_sockets), 3)
            demo_lifecycle.ensure_runtime_layout(config)
            self.assertTrue(config.identity_state_dir.is_dir())


class IdentityMqttPublicationTests(unittest.TestCase):
    def test_identity_result_uses_existing_topic_qos_one_and_no_retain(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.published: list[tuple[str, str, int, bool]] = []

            def publish(self, topic, payload, qos=0, retain=True) -> None:
                self.published.append((topic, payload, qos, retain))

        runtime = TemiMqttClient.__new__(TemiMqttClient)
        runtime.client = FakeClient()
        runtime.publish_identity_result("temi-01", {"schema_version": "1.0"})
        topic, _, qos, retain = runtime.client.published[0]
        self.assertEqual(topic, "temi/temi-01/resident/identity/result")
        self.assertEqual(qos, 1)
        self.assertFalse(retain)


if __name__ == "__main__":
    unittest.main()
