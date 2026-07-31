import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

from temi_action_viewer import (
    ActionState,
    BufferedFrame,
    LlamaCppBackend,
    PosePreprocessor,
    ViewerConfigurationError,
    abnormal_cooldown_elapsed,
    build_abnormal_event,
    build_inference_jpegs,
    build_llamacpp_payload,
    maybe_publish_abnormal_event,
    notification_health,
    normalize_action_response,
    parse_action_response,
    run_discord_delivery_test,
    resolve_notification_config,
    sample_uniform_frames,
    save_abnormal_evidence_frames,
    should_publish_abnormal_event,
    viewer_health_response,
)
from temi_video_action_tester import build_video_inference_batches, parse_args


def make_frame(sequence: int, received_at: float) -> BufferedFrame:
    return BufferedFrame(
        timestamp_ms=sequence * 1000,
        sequence=sequence,
        received_at=received_at,
        jpeg=b"jpeg",
        image=np.zeros((8, 8, 3), dtype=np.uint8),
    )


class SamplerTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_second_second_sampled_frame_enters_history(self) -> None:
        state = ActionState()
        for index in range(6):
            await state.add_frame(make_frame(index, 100.0 + index * 0.1), 10.0, 3, 5)
        await state.add_frame(make_frame(99, 101.0), 10.0, 3, 5)
        snapshot = await state.snapshot(3, 5)

        self.assertEqual(snapshot["history_frames"], 1)
        self.assertEqual(list(state.history_queue)[0].sequence, 1)

    async def test_ready_batch_order_is_history_then_uniform_current(self) -> None:
        state = ActionState()
        for second in range(4):
            for index in range(6):
                sequence = second * 10 + index
                await state.add_frame(make_frame(sequence, 100.0 + second + index * 0.1), 10.0, 3, 5)
        batch = await state.prepare_inference_batch(3, 5)

        self.assertEqual([frame.sequence for frame in batch[:3]], [1, 11, 21])
        self.assertEqual([frame.sequence for frame in batch[3:]], [30, 31, 32, 34, 35])

    async def test_inference_does_not_reenter_same_signature(self) -> None:
        state = ActionState()
        for second in range(4):
            for index in range(6):
                sequence = second * 10 + index
                await state.add_frame(make_frame(sequence, 100.0 + second + index * 0.1), 10.0, 3, 5)

        first = await state.prepare_inference_batch(3, 5)
        second = await state.prepare_inference_batch(3, 5)
        await state.finish_inference()
        third = await state.prepare_inference_batch(3, 5)

        self.assertEqual(len(first), 8)
        self.assertEqual(second, [])
        self.assertEqual(third, [])

    def test_uniform_sampler(self) -> None:
        frames = [make_frame(index, float(index)) for index in range(8)]
        self.assertEqual([frame.sequence for frame in sample_uniform_frames(frames, 5)], [0, 2, 4, 5, 7])

    def test_video_batches_emit_once_per_complete_second(self) -> None:
        buckets = {}
        for second in range(6):
            buckets[second] = [
                make_frame(second * 10 + index, float(second) + index * 0.1)
                for index in range(6)
            ]

        batches = build_video_inference_batches(buckets, 3, 5)

        self.assertEqual(len(batches), 3)
        self.assertEqual([frame.sequence for frame in batches[0][:3]], [1, 11, 21])
        self.assertEqual([frame.sequence for frame in batches[0][3:]], [30, 31, 32, 34, 35])
        self.assertEqual([batch[-1].sequence for batch in batches], [35, 45, 55])


class VideoTesterCliTests(unittest.TestCase):
    def parse(self, *arguments: str):
        with mock.patch.object(sys, "argv", ["temi-video-action-tester", *arguments]):
            return parse_args()

    def test_default_mode_disables_abnormal_publication(self) -> None:
        args = self.parse("--video", "sample.mp4")

        self.assertFalse(args.publish)
        self.assertEqual(args.abnormal_publish, "disabled")

    def test_publish_mode_keeps_abnormal_publication_enabled(self) -> None:
        args = self.parse("--video", "sample.mp4", "--publish")

        self.assertTrue(args.publish)
        self.assertEqual(args.abnormal_publish, "enabled")

    def test_rejects_non_positive_fallback_fps(self) -> None:
        with self.assertRaisesRegex(SystemExit, "--fallback-fps must be positive"):
            self.parse("--video", "sample.mp4", "--fallback-fps", "0")

    def test_rejects_invalid_port(self) -> None:
        with self.assertRaisesRegex(SystemExit, "--mqtt-port must be in 1-65535"):
            self.parse("--video", "sample.mp4", "--mqtt-port", "70000")

    def test_rejects_invalid_evidence_quality(self) -> None:
        with self.assertRaisesRegex(SystemExit, "--evidence-jpeg-quality must be in 1-100"):
            self.parse("--video", "sample.mp4", "--evidence-jpeg-quality", "0")


class PromptParserTests(unittest.TestCase):
    def test_prompt_contains_reference_categories_and_fixed_format(self) -> None:
        frame = make_frame(1, 1.0)
        payload = build_llamacpp_payload("model", [frame], [b"jpeg"], 96, 3, 5)
        prompt = payload["messages"][1]["content"][0]["text"]

        self.assertIn("falls down", prompt)
        self.assertIn("watches tv", prompt)
        self.assertIn("Action: <one target action category, or No person visible>", prompt)
        self.assertIn("Evidence/Reason: <brief visual evidence>", prompt)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["top_k"], 1)
        self.assertEqual(payload["top_p"], 1)

    def test_parser_accepts_action_evidence_format(self) -> None:
        content = (
            "Action: blows nose or sneezes\n"
            "Evidence/Reason: The person raises their hand to their nose and face from Frame 2 through Frame 4."
        )
        parsed = parse_action_response(content)

        self.assertEqual(parsed.action_name, "blows nose or sneezes")
        self.assertEqual(
            parsed.reason,
            "The person raises their hand to their nose and face from Frame 2 through Frame 4.",
        )
        self.assertEqual(parsed.raw_response, content)

    def test_parser_preserves_long_fights_reason(self) -> None:
        parsed = parse_action_response(
            "Action: fights\n"
            "Evidence/Reason: Two individuals engage in physical contact; one person repeatedly strikes "
            "the other's upper body and head area. Rapid arm movements and shifting body postures "
            "indicate a struggle."
        )

        self.assertEqual(parsed.action_name, "fights")
        self.assertIn("repeatedly strikes", parsed.reason)

    def test_parser_missing_reason_uses_empty_string(self) -> None:
        parsed = parse_action_response("Action: fights")

        self.assertEqual(parsed.action_name, "fights")
        self.assertEqual(parsed.reason, "")

    def test_parser_keeps_action_name_format_as_compatibility(self) -> None:
        parsed = parse_action_response("action_name:person_walks\nreason:Leg motion is visible")

        self.assertEqual(parsed.action_name, "person_walks")
        self.assertEqual(parsed.reason, "Leg motion is visible")

    def test_parser_accepts_reference_format(self) -> None:
        parsed = normalize_action_response("Action: person_sits_down\nEvidence/Reason: The body lowers to a chair")
        self.assertEqual(parsed, "Action: person_sits_down\nEvidence/Reason: The body lowers to a chair")

    def test_abnormal_event_uses_only_parsed_action_and_reason(self) -> None:
        parsed = parse_action_response("Action: fights\nEvidence/Reason: Two people are striking each other.")
        event = build_abnormal_event(parsed, ["/shared/frame_000.jpg"])

        self.assertTrue(should_publish_abnormal_event(parsed))
        self.assertEqual(event["type"], "perception.abnormal")
        self.assertEqual(event["event_type"], "fight")
        self.assertEqual(event["schema_version"], "1.0")
        self.assertEqual(event["observation"]["action_name"], "fights")
        self.assertEqual(event["observation"]["reason"], "Two people are striking each other.")
        self.assertEqual(event["evidence"]["frame_paths"], ["/shared/frame_000.jpg"])
        self.assertNotIn("confidence", event)
        self.assertNotIn("confidence_source", event)
        self.assertNotIn("severity", event)
        self.assertNotIn("confidence", event["observation"])
        self.assertNotIn("confidence_source", event["observation"])
        self.assertNotIn("severity", event["observation"])

    def test_non_abnormal_action_does_not_publish_event(self) -> None:
        parsed = parse_action_response(
            "Action: blows nose or sneezes\n"
            "Evidence/Reason: The person keeps a hand near the nose."
        )

        self.assertFalse(should_publish_abnormal_event(parsed))

    def test_evidence_saves_original_jpeg_bytes(self) -> None:
        frames = [make_frame(index, float(index)) for index in range(2)]
        frames[0] = BufferedFrame(0, 0, 0.0, b"original-a", frames[0].image)
        frames[1] = BufferedFrame(1, 1, 1.0, b"original-b", frames[1].image)
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_abnormal_evidence_frames(frames, tmp, "temi-01", "evt_test")

            self.assertEqual(Path(paths[0]).read_bytes(), b"original-a")
            self.assertEqual(Path(paths[1]).read_bytes(), b"original-b")

    def test_notification_health_reports_bridge_ownership_without_credentials(self) -> None:
        class Args:
            abnormal_publish = "enabled"
        config = resolve_notification_config(
            SimpleNamespace(
                discord_notify="disabled",
                notification_mode="disabled",
                discord_env_path="",
                discord_test_mode="disabled",
                demo_notification_mock_enabled="disabled",
                demo_notification_mock_receipt_enabled="disabled",
            )
        )
        result = notification_health(Args, config)

        self.assertTrue(result["abnormal_publish_enabled"])
        self.assertTrue(result["notification_bridge_owned"])
        self.assertEqual(result["real_discord"]["status"], "disabled")
        self.assertNotIn("discord_env_path", result)

    def test_controlled_discord_delivery_test_is_rejected_as_bridge_owned(self) -> None:
        class Args:
            discord_notify = "enabled"
            discord_env_path = "/private/.env"

        result = run_discord_delivery_test(Args)

        self.assertEqual(result["failure_code"], "DISCORD_BRIDGE_OWNED")

    def test_disabled_abnormal_publish_skips_persistence_and_notification(self) -> None:
        class Args:
            abnormal_publish = "disabled"

        parsed = parse_action_response("Action: falls down\nEvidence/Reason: The person is on the floor.")
        with mock.patch("temi_action_viewer.save_abnormal_evidence_frames") as save:
            self.assertIsNone(maybe_publish_abnormal_event(parsed, [make_frame(1, 1.0)], Args))
        save.assert_not_called()

    def test_abnormal_publish_never_notifies_discord_when_mqtt_fails(self) -> None:
        class Args:
            abnormal_publish = "enabled"
            shared_root = ""
            robot_id = "temi-01"
            abnormal_source = "test"
            mqtt_broker = "127.0.0.1"
            mqtt_port = 1883

        parsed = parse_action_response("Action: falls down\nEvidence/Reason: The person is on the floor.")
        frames = [make_frame(index, float(index)) for index in range(2)]
        with tempfile.TemporaryDirectory() as tmp:
            Args.shared_root = tmp
            with mock.patch("temi_action_viewer.publish_abnormal_event_mqtt", side_effect=RuntimeError("mqtt down")):
                event = maybe_publish_abnormal_event(parsed, frames, Args)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertIn("mqtt_error", event)
        self.assertNotIn("discord", event)

    def test_abnormal_cooldown_blocks_second_emergency_within_window(self) -> None:
        self.assertTrue(abnormal_cooldown_elapsed(0.0, 100.0, 180.0))
        self.assertFalse(abnormal_cooldown_elapsed(100.0, 200.0, 180.0))
        self.assertTrue(abnormal_cooldown_elapsed(100.0, 280.0, 180.0))

    def test_abnormal_publish_marks_pre_alert_bridge_owned_and_carries_delivery_receipt(self) -> None:
        class Args:
            abnormal_publish = "enabled"
            shared_root = ""
            robot_id = "temi-01"
            abnormal_source = "test"
            mqtt_broker = "127.0.0.1"
            mqtt_port = 1883
            pre_alert_speak = "enabled"
            pre_alert_language = "zh-TW"

        parsed = parse_action_response("Action: falls down\nEvidence/Reason: The person is on the floor.")
        frames = [make_frame(index, float(index)) for index in range(2)]
        with tempfile.TemporaryDirectory() as tmp:
            Args.shared_root = tmp
            with mock.patch("temi_action_viewer.publish_abnormal_event_mqtt") as publish_event:
                event = maybe_publish_abnormal_event(parsed, frames, Args)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["pre_alert_speak"]["status"], "suppressed")
        self.assertEqual(event["pre_alert_speak"]["failure_code"], "ABNORMAL_PRE_ALERT_BRIDGE_OWNED")
        self.assertEqual(event["mqtt"]["status"], "ok")
        self.assertNotIn("discord", event)
        self.assertNotIn("notification", event["payload"])
        self.assertEqual(publish_event.call_count, 1)

    def test_inference_jpegs_use_pose_renderer(self) -> None:
        class FakePose:
            def __init__(self) -> None:
                self.calls = []

            def render(self, frame):
                self.calls.append(frame.sequence)
                return frame.image

        frames = [make_frame(index, float(index)) for index in range(3)]
        fake_pose = FakePose()

        jpegs = build_inference_jpegs(frames, fake_pose, 80, 0)

        self.assertEqual(fake_pose.calls, [0, 1, 2])
        self.assertEqual(len(jpegs), 3)


class ViewerHealthTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def args(**overrides: object) -> SimpleNamespace:
        values: dict[str, object] = {
            "source_url": "ws://127.0.0.1:8081",
            "model": "test-model",
            "abnormal_publish": "disabled",
            "abnormal_cooldown_seconds": 30.0,
            "history_seconds": 3,
            "current_second_samples": 5,
            "discord_notify": "disabled",
            "notification_mode": "disabled",
            "discord_env_path": "",
            "discord_test_mode": "disabled",
            "demo_notification_mock_enabled": "disabled",
            "demo_notification_mock_receipt_enabled": "disabled",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    async def test_disabled_route_health_is_200_without_a_credential_path(self) -> None:
        args = self.args()
        response = await viewer_health_response(
            ActionState(), args, resolve_notification_config(args)
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["components"]["viewer_core"]["status"], "healthy")
        self.assertEqual(payload["components"]["real_discord"]["status"], "disabled")
        self.assertNotIn("discord_env_path", payload)

    async def test_demo_mock_health_reports_its_receipt_route_without_real_discord(self) -> None:
        args = self.args(
            notification_mode="demo_mock",
            demo_notification_mock_enabled="enabled",
            demo_notification_mock_receipt_enabled="enabled",
        )
        response = await viewer_health_response(
            ActionState(), args, resolve_notification_config(args)
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(
            payload["components"]["demo_notification_mock"]["status"],
            "receipt_route_available",
        )
        self.assertEqual(payload["components"]["real_discord"]["status"], "disabled")

    async def test_real_discord_health_is_redacted_and_skipped_by_the_viewer(self) -> None:
        secret_path = "/private/real-discord.env"
        args = self.args(
            notification_mode="discord_webhook",
            discord_env_path=secret_path,
            discord_test_mode="enabled",
        )
        response = await viewer_health_response(
            ActionState(), args, resolve_notification_config(args)
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["components"]["real_discord"]["status"], "skipped_by_viewer")
        self.assertNotIn(secret_path, response.text)

    def test_malformed_notification_namespace_fails_deterministically(self) -> None:
        with self.assertRaisesRegex(ViewerConfigurationError, "missing notification_mode"):
            resolve_notification_config(SimpleNamespace(discord_notify="disabled"))

    async def test_unexpected_health_exception_is_redacted_and_unhealthy(self) -> None:
        class BrokenState:
            async def snapshot(self, *_args: object) -> dict[str, object]:
                raise RuntimeError("credential=/private/should-not-leak")

        args = self.args()
        response = await viewer_health_response(
            BrokenState(), args, resolve_notification_config(args)  # type: ignore[arg-type]
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status, 503)
        self.assertEqual(payload["error_code"], "VIEWER_HEALTH_INTERNAL_ERROR")
        self.assertNotIn("should-not-leak", response.text)


class PoseBackendTests(unittest.TestCase):
    def test_pose_off_does_not_load_model(self) -> None:
        preprocessor = PosePreprocessor("off", "missing.pt", "0")
        preprocessor.initialize()
        status = preprocessor.status()

        self.assertFalse(status["pose_enabled"])
        self.assertEqual(status["pose_mode"], "off")
        self.assertEqual(status["pose_device"], "0")

    def test_pose_on_fails_when_model_missing(self) -> None:
        preprocessor = PosePreprocessor("on", "missing.pt", "0")
        with self.assertRaises(RuntimeError):
            preprocessor.initialize()

    def test_missing_llama_server_reports_unready(self) -> None:
        class Args:
            llama_api_base_url = ""
            llama_server = "/definitely/missing/llama-server"
            llama_server_host = "127.0.0.1"
            llama_server_port = 8011
            llama_startup_timeout = 0.1
            gguf_model_path = "/missing/model.gguf"
            mmproj_path = "/missing/mmproj.gguf"

        backend = LlamaCppBackend(Args())
        asyncio.run(backend.start())
        status = backend.status()

        self.assertFalse(status["llama_server_ready"])
        self.assertIn("llama-server not found", status["llama_server_error"])


if __name__ == "__main__":
    unittest.main()
