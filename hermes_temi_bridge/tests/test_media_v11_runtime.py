import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hermes_temi_bridge.config import BridgeConfig
from hermes_temi_bridge.logging_utils import EventJsonlLogger
from hermes_temi_bridge.main import HermesTemiBridgeService
from hermes_temi_bridge.media_contract import (
    MediaContractError,
    build_media_command_request,
    validate_media_command_request,
    validate_media_command_result,
)
from hermes_temi_bridge.media_registry import MediaSessionRegistry


class RecordingMqtt:
    def __init__(self):
        self.published = []

    def publish_command(self, robot_id, payload):
        self.published.append((robot_id, payload))


class FailingMqtt:
    def publish_command(self, robot_id, payload):
        raise RuntimeError("synthetic publish failure")


class UnusedHermes:
    pass


def command(action="play_video", command_id="cmd_play_001", **overrides):
    payload = build_media_command_request(
        event_id="evt_media_001",
        robot_id="temi-01",
        resident_id="resident_father",
        action=action,
        video_id="exercise_upper_body_01",
        target_playback_session_id=(
            None if action == "play_video" else "session_media_001"
        ),
        parameters={},
        command_id=command_id,
        timestamp="2026-07-26T10:00:00Z",
    )
    payload.update(overrides)
    return payload


def result(request, status, **overrides):
    action = request["action"]
    session_id = overrides.pop(
        "playback_session_id",
        "session_media_001" if status not in {"rejected"} else None,
    )
    state = {
        "accepted": None,
        "started": "playing",
        "completed": "completed",
        "cancelled": "cancelled",
        "succeeded": {
            "pause_video": "paused",
            "resume_video": "playing",
            "stop_video": "cancelled",
        }.get(action),
        "failed": "failed" if session_id else None,
        "rejected": None,
    }[status]
    payload = {
        "schema_version": "1.1",
        "message_type": "video.command_result",
        "command_id": request["command_id"],
        "request_id": request["request_id"],
        "event_id": request["event_id"],
        "robot_id": request["robot_id"],
        "command_action": action,
        "video_id": request["video_id"],
        "status": status,
        "terminal": status not in {"accepted", "started"},
        "playback_session_id": session_id,
        "target_playback_session_id": request["target_playback_session_id"],
        "active_playback_session_id": None,
        "playback_state": state,
        "cancelled_by_command_id": None,
        "cancel_reason": None,
        "actor": "remote_command",
        "result_delivery": "original",
        "error_code": None,
        "error_message": None,
        "timestamp": "2026-07-26T10:00:01Z",
    }
    payload.update(overrides)
    return payload


class MediaContractRuntimeTests(unittest.TestCase):
    def test_action_execution_class_is_derived_and_tampering_is_rejected(self):
        play = command()
        pause = command("pause_video", "cmd_pause_001")
        self.assertEqual(play["execution_class"], "serialized_execution")
        self.assertEqual(pause["execution_class"], "active_playback_control")
        with self.assertRaisesRegex(MediaContractError, "requires execution_class"):
            validate_media_command_request(
                {**pause, "execution_class": "serialized_execution"}
            )

    def test_unknown_action_and_strict_extra_field_are_rejected(self):
        with self.assertRaises(MediaContractError) as action_error:
            build_media_command_request(
                event_id="evt_media_001",
                robot_id="temi-01",
                resident_id="resident_father",
                action="seek_video",
                video_id="exercise_upper_body_01",
            )
        self.assertEqual(action_error.exception.code, "UNSUPPORTED_MEDIA_ACTION")
        with self.assertRaisesRegex(MediaContractError, "fields do not match"):
            validate_media_command_request({**command(), "unexpected": True})

    def test_result_validator_rejects_unknown_action_and_schema(self):
        play = command()
        with self.assertRaises(MediaContractError):
            validate_media_command_result(
                {**result(play, "accepted"), "command_action": "seek_video"}
            )
        with self.assertRaises(MediaContractError):
            validate_media_command_result(
                {**result(play, "accepted"), "schema_version": "9.0"}
            )

    def test_restart_cancellation_accepts_reconciliation_and_cached_replay_only(self):
        play = command()
        restart = result(
            play,
            "cancelled",
            cancel_reason="app_process_restart",
            actor="app_process",
            result_delivery="restart_reconciliation",
        )
        validate_media_command_result(restart)
        validate_media_command_result(
            {**restart, "result_delivery": "cached_replay"}
        )
        for invalid in (
            {**restart, "result_delivery": "original"},
            {**restart, "result_delivery": "cached_replay", "actor": "remote_command"},
            {
                **restart,
                "result_delivery": "cached_replay",
                "cancelled_by_command_id": "cmd_stop_invalid",
            },
            {**result(play, "started"), "result_delivery": "cached_replay"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(MediaContractError):
                    validate_media_command_result(invalid)

    def test_restart_failure_accepts_reconciliation_and_cached_replay_only(self):
        play = command()
        restart_failure = result(
            play,
            "failed",
            actor="app_process",
            result_delivery="restart_reconciliation",
            error_code="APP_PROCESS_RESTART",
            error_message="Playback cannot resume after application restart.",
        )
        validate_media_command_result(restart_failure)
        validate_media_command_result(
            {**restart_failure, "result_delivery": "cached_replay"}
        )
        for invalid in (
            {**restart_failure, "result_delivery": "original"},
            {**restart_failure, "result_delivery": "cached_replay", "actor": "remote_command"},
            {
                **restart_failure,
                "result_delivery": "cached_replay",
                "playback_session_id": None,
                "playback_state": None,
            },
            {
                **restart_failure,
                "result_delivery": "cached_replay",
                "cancel_reason": "app_process_restart",
            },
            {
                **restart_failure,
                "status": "rejected",
                "result_delivery": "cached_replay",
                "playback_session_id": None,
                "playback_state": None,
            },
            {
                **result(play, "started"),
                "actor": "app_process",
                "result_delivery": "restart_reconciliation",
                "error_code": "APP_PROCESS_RESTART",
                "error_message": "Playback cannot resume after application restart.",
            },
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(MediaContractError):
                    validate_media_command_result(invalid)


class MediaRegistryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.registry = MediaSessionRegistry()
        self.play = command()
        self.registry.register_published(self.play)

    def accept_and_start(self):
        accepted = self.registry.consume_result(result(self.play, "accepted"))
        started = self.registry.consume_result(result(self.play, "started"))
        return accepted, started

    def test_accepted_result_creates_session_mapping_and_started_is_nonterminal(self):
        accepted, started = self.accept_and_start()
        self.assertTrue(accepted.side_effect_applied)
        self.assertEqual(self.registry.active_session_id("temi-01"), "session_media_001")
        state = self.registry.command_state(self.play["command_id"])
        self.assertEqual(state.status, "started")
        self.assertFalse(state.terminal)
        self.assertEqual(started.originating_play_command_id, self.play["command_id"])

    def test_control_before_accepted_is_rejected(self):
        with self.assertRaises(MediaContractError) as caught:
            self.registry.register_published(command("pause_video", "cmd_pause_001"))
        self.assertEqual(caught.exception.code, "MEDIA_SESSION_NOT_FOUND")

    def test_pause_and_resume_are_terminal_but_play_remains_active(self):
        self.accept_and_start()
        pause = command("pause_video", "cmd_pause_001")
        self.registry.register_published(pause)
        pause_disposition = self.registry.consume_result(result(pause, "succeeded"))
        play_state = self.registry.command_state(self.play["command_id"])
        self.assertTrue(pause_disposition.command_terminal)
        self.assertFalse(play_state.terminal)
        self.assertEqual(play_state.playback_state, "paused")

        resume = command("resume_video", "cmd_resume_001")
        self.registry.register_published(resume)
        self.registry.consume_result(result(resume, "succeeded"))
        play_state = self.registry.command_state(self.play["command_id"])
        self.assertFalse(play_state.terminal)
        self.assertEqual(play_state.playback_state, "playing")

    def test_stop_success_and_play_cancellation_are_linked(self):
        self.accept_and_start()
        stop = command("stop_video", "cmd_stop_001")
        self.registry.register_published(stop)
        self.registry.consume_result(result(stop, "succeeded"))
        cancellation = result(
            self.play,
            "cancelled",
            cancelled_by_command_id=stop["command_id"],
            cancel_reason="remote_stop",
        )
        disposition = self.registry.consume_result(cancellation)
        self.assertTrue(disposition.command_terminal)
        self.assertIsNone(self.registry.active_session_id("temi-01"))

    def test_invalid_stop_linkage_is_rejected_and_play_stays_active(self):
        self.accept_and_start()
        with self.assertRaises(MediaContractError) as caught:
            self.registry.consume_result(
                result(
                    self.play,
                    "cancelled",
                    cancelled_by_command_id="cmd_stop_unknown",
                    cancel_reason="remote_stop",
                )
            )
        self.assertEqual(caught.exception.code, "MEDIA_CONTROL_CONFLICT")
        self.assertEqual(self.registry.active_session_id("temi-01"), "session_media_001")

    def test_invalid_session_linkage_is_rejected(self):
        self.registry.consume_result(result(self.play, "accepted"))
        with self.assertRaises(MediaContractError) as caught:
            self.registry.consume_result(
                result(self.play, "started", playback_session_id="session_other")
            )
        self.assertEqual(caught.exception.code, "MEDIA_CONTROL_CONFLICT")

    def test_concurrent_play_rejection_is_consumed_without_new_session(self):
        second = command(command_id="cmd_play_002")
        self.registry.register_published(second)
        self.registry.consume_result(result(self.play, "accepted"))
        rejected = result(
            second,
            "rejected",
            active_playback_session_id="session_media_001",
            error_code="MEDIA_SESSION_ACTIVE",
            error_message="Another playback session is active.",
        )
        disposition = self.registry.consume_result(rejected)
        self.assertTrue(disposition.command_terminal)
        self.assertEqual(self.registry.active_session_id("temi-01"), "session_media_001")

    def test_duplicate_terminal_and_cached_replay_do_not_reapply_state(self):
        self.accept_and_start()
        completed = result(self.play, "completed")
        first = self.registry.consume_result(completed)
        duplicate = self.registry.consume_result(completed)
        cached = self.registry.consume_result(
            {**completed, "result_delivery": "cached_replay"}
        )
        self.assertTrue(first.side_effect_applied)
        self.assertFalse(duplicate.side_effect_applied)
        self.assertEqual(duplicate.disposition, "duplicate_terminal")
        self.assertFalse(cached.side_effect_applied)
        self.assertEqual(cached.disposition, "cached_replay")

    def test_active_reference_does_not_create_another_session(self):
        accepted = result(self.play, "accepted")
        self.registry.consume_result(accepted)
        replay = self.registry.consume_result(
            {**accepted, "result_delivery": "active_reference"}
        )
        self.assertFalse(replay.side_effect_applied)
        self.assertEqual(replay.disposition, "active_reference")
        self.assertEqual(self.registry.active_session_id("temi-01"), "session_media_001")

    def test_active_reference_can_establish_the_first_observed_session_mapping(self):
        accepted = result(
            self.play,
            "accepted",
            result_delivery="active_reference",
        )
        disposition = self.registry.consume_result(accepted)
        self.assertTrue(disposition.side_effect_applied)
        self.assertEqual(disposition.disposition, "active_reference_applied")
        self.assertEqual(self.registry.active_session_id("temi-01"), "session_media_001")

    def test_cached_replay_can_supply_the_first_observed_terminal_result(self):
        completed = result(
            self.play,
            "completed",
            result_delivery="cached_replay",
        )
        disposition = self.registry.consume_result(completed)
        self.assertTrue(disposition.side_effect_applied)
        self.assertEqual(disposition.disposition, "cached_replay_applied")
        state = self.registry.command_state(self.play["command_id"])
        self.assertTrue(state.terminal)
        self.assertEqual(state.playback_session_id, "session_media_001")
        self.assertIsNone(self.registry.active_session_id("temi-01"))

    def test_app_restart_reconciliation_is_terminal(self):
        self.accept_and_start()
        restart = result(
            self.play,
            "cancelled",
            cancel_reason="app_process_restart",
            actor="app_process",
            result_delivery="restart_reconciliation",
        )
        disposition = self.registry.consume_result(restart)
        self.assertTrue(disposition.command_terminal)
        self.assertIsNone(self.registry.active_session_id("temi-01"))

    def test_fresh_registry_applies_restart_replay_once_then_deduplicates(self):
        replay = result(
            self.play,
            "cancelled",
            cancel_reason="app_process_restart",
            actor="app_process",
            result_delivery="cached_replay",
        )
        first = self.registry.consume_result(replay)
        first_replay = self.registry.consume_result(replay)
        second_replay = self.registry.consume_result(replay)
        self.assertTrue(first.command_terminal)
        self.assertTrue(first.side_effect_applied)
        self.assertEqual(first.disposition, "cached_replay_applied")
        self.assertEqual(first_replay.disposition, "cached_replay")
        self.assertFalse(first_replay.side_effect_applied)
        self.assertEqual(second_replay.disposition, "cached_replay")
        self.assertFalse(second_replay.side_effect_applied)
        state = self.registry.command_state(self.play["command_id"])
        self.assertEqual(state.playback_session_id, "session_media_001")
        self.assertIsNone(self.registry.active_session_id("temi-01"))
        with self.assertRaises(MediaContractError):
            self.registry.consume_result(
                {**replay, "playback_session_id": "session_media_other"}
            )
        with self.assertRaises(MediaContractError):
            self.registry.consume_result(
                {
                    **replay,
                    "command_id": "cmd_play_other",
                    "request_id": "cmd_play_other",
                }
            )
        with self.assertRaises(MediaContractError):
            self.registry.consume_result(
                {
                    **replay,
                    "command_action": "pause_video",
                    "status": "succeeded",
                    "target_playback_session_id": "session_media_001",
                    "playback_state": "paused",
                    "cancel_reason": None,
                    "actor": "remote_command",
                }
            )


class MediaBridgeServiceTests(unittest.TestCase):
    def make_service(self, root, *, enabled):
        mqtt = RecordingMqtt()
        service = HermesTemiBridgeService(
            BridgeConfig(
                log_dir=(root / "logs").as_posix(),
                memory_dir=(root / "memory").as_posix(),
                media_v11_enabled=enabled,
            ),
            mqtt,
            UnusedHermes(),
            event_logger=EventJsonlLogger(root / "logs"),
        )
        return service, mqtt

    def test_feature_gate_blocks_media_publication_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, mqtt = self.make_service(Path(tmp), enabled=False)
            with self.assertRaises(MediaContractError):
                service.publish_media_play(
                    event_id="evt_media_001",
                    robot_id="temi-01",
                    resident_id="resident_father",
                    video_id="exercise_upper_body_01",
                )
            self.assertEqual(mqtt.published, [])

    def test_feature_gate_can_be_enabled_from_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"MEDIA_V11_ENABLED": "true"}):
                config = BridgeConfig.from_env(Path(tmp) / "missing.env")
        self.assertTrue(config.media_v11_enabled)

    def test_v1_command_result_behavior_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _ = self.make_service(root, enabled=True)
            disposition = service.handle_command_result(
                "temi/temi-01/cmd/result",
                {
                    "schema_version": "1.0",
                    "command_id": "cmd_v1",
                    "event_id": "evt_v1",
                    "robot_id": "temi-01",
                    "status": "success",
                    "results": [],
                },
            )
            self.assertEqual(disposition, {"status": "recorded", "schema_version": "1.0"})
            records = read_trace(root / "logs", "evt_v1")
            self.assertEqual(records[-1]["stage"], "command_result_received")

    def test_successful_command_id_is_not_republished(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, mqtt = self.make_service(Path(tmp), enabled=True)
            fields = {
                "event_id": "evt_media_001",
                "robot_id": "temi-01",
                "resident_id": "resident_father",
                "video_id": "exercise_upper_body_01",
                "command_id": "cmd_play_001",
            }
            service.publish_media_play(**fields)
            with self.assertRaises(MediaContractError) as caught:
                service.publish_media_play(**fields)
            self.assertEqual(caught.exception.code, "MEDIA_CONTROL_CONFLICT")
            self.assertEqual(len(mqtt.published), 1)

    def test_publish_failure_rolls_back_unpublished_command_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = HermesTemiBridgeService(
                BridgeConfig(
                    log_dir=(root / "logs").as_posix(),
                    memory_dir=(root / "memory").as_posix(),
                    media_v11_enabled=True,
                ),
                FailingMqtt(),
                UnusedHermes(),
            )
            with self.assertRaisesRegex(RuntimeError, "synthetic publish failure"):
                service.publish_media_play(
                    event_id="evt_media_001",
                    robot_id="temi-01",
                    resident_id="resident_father",
                    video_id="exercise_upper_body_01",
                    command_id="cmd_publish_failure_001",
                )
            self.assertIsNone(
                service.media_registry.command_state("cmd_publish_failure_001")
            )

    def test_service_publishes_control_only_after_acceptance_and_traces_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, mqtt = self.make_service(root, enabled=True)
            play = service.publish_media_play(
                event_id="evt_media_001",
                robot_id="temi-01",
                resident_id="resident_father",
                video_id="exercise_upper_body_01",
                command_id="cmd_play_001",
                timestamp="2026-07-26T10:00:00Z",
            )
            with self.assertRaises(MediaContractError):
                service.publish_media_control(robot_id="temi-01", action="pause_video")
            service.handle_command_result(
                "temi/temi-01/cmd/result", result(play, "accepted")
            )
            service.handle_command_result(
                "temi/temi-01/cmd/result", result(play, "started")
            )
            pause = service.publish_media_control(
                robot_id="temi-01",
                action="pause_video",
                command_id="cmd_pause_001",
                timestamp="2026-07-26T10:00:02Z",
            )
            service.handle_command_result(
                "temi/temi-01/cmd/result", result(pause, "succeeded")
            )
            self.assertEqual(len(mqtt.published), 2)
            self.assertEqual(pause["target_playback_session_id"], "session_media_001")
            records = read_trace(root / "logs", "evt_media_001")
            stages = [record["stage"] for record in records]
            self.assertEqual(stages.count("command_request_published"), 2)
            self.assertEqual(stages.count("command_result_received"), 3)
            last = records[-1]["payload"]
            self.assertEqual(last["command_id"], "cmd_pause_001")
            self.assertEqual(last["playback_session_id"], "session_media_001")
            self.assertEqual(last["originating_play_command_id"], "cmd_play_001")

    def test_unknown_schema_is_rejected_without_v1_downgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self.make_service(Path(tmp), enabled=True)
            disposition = service.handle_command_result(
                "temi/temi-01/cmd/result",
                {
                    "schema_version": "9.0",
                    "event_id": "evt_unknown",
                    "robot_id": "temi-01",
                    "status": "success",
                },
            )
            self.assertEqual(disposition["status"], "rejected")
            self.assertEqual(disposition["error_code"], "unsupported_schema_version")


def read_trace(log_dir, event_id):
    path = Path(log_dir) / f"{event_id}.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
