import asyncio
import unittest

import numpy as np

from temi_action_viewer import (
    ActionState,
    BufferedFrame,
    LlamaCppBackend,
    PosePreprocessor,
    build_llamacpp_payload,
    normalize_action_response,
    sample_uniform_frames,
)


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


class PromptParserTests(unittest.TestCase):
    def test_prompt_contains_reference_categories_and_fixed_format(self) -> None:
        frame = make_frame(1, 1.0)
        payload = build_llamacpp_payload("model", [frame], [b"jpeg"], 96, 3, 5)
        prompt = payload["messages"][1]["content"][0]["text"]

        self.assertIn("person_falls_down", prompt)
        self.assertIn("person_watches_tv", prompt)
        self.assertIn("action_name:<one target action category, or No person visible>", prompt)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["top_k"], 1)
        self.assertEqual(payload["top_p"], 1)

    def test_parser_accepts_action_name_format(self) -> None:
        parsed = normalize_action_response("action_name:person_walks\nreason:Leg motion is visible")
        self.assertEqual(parsed, "action_name:person_walks\nreason:Leg motion is visible")

    def test_parser_accepts_reference_format(self) -> None:
        parsed = normalize_action_response("Action: person_sits_down\nEvidence/Reason: The body lowers to a chair")
        self.assertEqual(parsed, "action_name:person_sits_down\nreason:The body lowers to a chair")


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
