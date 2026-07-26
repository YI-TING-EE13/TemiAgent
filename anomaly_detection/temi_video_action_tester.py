"""Run Temi action inference against a local video file."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import cv2
from aiohttp import ClientSession

from temi_action_viewer import (
    DEFAULT_GGUF_MODEL_PATH,
    DEFAULT_DISCORD_ENV_PATH,
    DEFAULT_LLAMA_SERVER_PATH,
    DEFAULT_MMPROJ_PATH,
    BufferedFrame,
    LlamaCppBackend,
    ParsedAction,
    PosePreprocessor,
    call_llamacpp,
    encode_jpeg,
    maybe_publish_abnormal_event,
    sample_uniform_frames,
    should_publish_abnormal_event,
)


LOGGER = logging.getLogger("temi_video_action_tester")


async def run_video_test(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Scan the video, run action inference, and optionally publish abnormal events."""
    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    capture = cv2.VideoCapture(video_path.as_posix())
    if not capture.isOpened():
        raise RuntimeError(f"failed to open video: {video_path}")

    backend = LlamaCppBackend(args)
    results: list[dict[str, Any]] = []
    try:
        pose_preprocessor = PosePreprocessor(args.pose_mode, args.pose_model, args.pose_device)
        pose_preprocessor.initialize()
        await backend.start()
        if not backend.ready:
            raise RuntimeError(backend.error or "llama.cpp backend unavailable")

        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = args.fallback_fps
        frame_index = 0
        second_buckets: dict[int, list[BufferedFrame]] = {}

        while True:
            ok, image = capture.read()
            if not ok:
                break
            pos_ms = capture.get(cv2.CAP_PROP_POS_MSEC)
            timestamp_ms = int(pos_ms) if pos_ms > 0 else int(frame_index * 1000 / fps)
            received_at = timestamp_ms / 1000.0
            jpeg = encode_jpeg(image, args.evidence_jpeg_quality)
            frame = BufferedFrame(
                timestamp_ms=timestamp_ms,
                sequence=frame_index,
                received_at=received_at,
                jpeg=jpeg,
                image=image,
            )
            second_buckets.setdefault(int(received_at), []).append(frame)
            frame_index += 1

        batches = build_video_inference_batches(
            second_buckets,
            args.history_seconds,
            args.current_second_samples,
        )
        async with ClientSession() as session:
            for batch in batches:
                prediction, timing = await call_llamacpp(
                    session,
                    backend.api_base,
                    args.model,
                    batch,
                    pose_preprocessor,
                    args.max_output_tokens,
                    args.history_seconds,
                    args.current_second_samples,
                    args.inference_jpeg_quality,
                    args.inference_long_side,
                )
                result: dict[str, Any] = {
                    "window_index": len(results),
                    "video": video_path.as_posix(),
                    "frame_sequences": [item.sequence for item in batch],
                    "timestamp_ms": batch[-1].timestamp_ms,
                    "timing_ms": dict(timing.__dict__),
                    "prediction": prediction.to_dict() if isinstance(prediction, ParsedAction) else prediction,
                    "published_event": None,
                }
                if isinstance(prediction, ParsedAction) and should_publish_abnormal_event(prediction):
                    result["is_abnormal"] = True
                    if args.publish:
                        event = maybe_publish_abnormal_event(prediction, batch, args)
                        result["published_event"] = event
                    if args.stop_after_first_alert:
                        results.append(result)
                        break
                else:
                    result["is_abnormal"] = False
                results.append(result)
                if args.max_windows and len(results) >= args.max_windows:
                    break
    finally:
        capture.release()
        await backend.stop()

    return results


def build_video_inference_batches(
    second_buckets: dict[int, list[BufferedFrame]],
    history_seconds: int,
    current_second_samples: int,
) -> list[list[BufferedFrame]]:
    """Build one inference batch per complete video second."""
    batches: list[list[BufferedFrame]] = []
    for second_key in sorted(second_buckets):
        current_frames = second_buckets[second_key]
        if len(current_frames) < current_second_samples:
            continue
        history: list[BufferedFrame] = []
        for history_second in range(second_key - history_seconds, second_key):
            frames = second_buckets.get(history_second)
            if not frames:
                history = []
                break
            history.append(completed_second_representative(frames, current_second_samples))
        if len(history) != history_seconds:
            continue
        batches.append(history + sample_uniform_frames(current_frames, current_second_samples))
    return batches


def completed_second_representative(
    frames: list[BufferedFrame],
    current_second_samples: int,
) -> BufferedFrame:
    """Return the same completed-second representative used by the live viewer."""
    sampled = sample_uniform_frames(frames, min(current_second_samples, len(frames)))
    return sampled[1] if len(sampled) > 1 else sampled[0]


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="Run Temi action prediction on a local video file.")
    parser.add_argument("--video", required=True, help="Path to a local video file.")
    publish_group = parser.add_mutually_exclusive_group()
    publish_group.add_argument("--publish", action="store_true", help="Publish abnormal events to MQTT.")
    publish_group.add_argument("--no-publish", action="store_true", help="Do not publish MQTT events.")
    parser.add_argument("--stop-after-first-alert", action="store_true")
    parser.add_argument("--max-windows", type=int, default=0, help="Optional test limit for inference windows.")
    parser.add_argument("--output-jsonl", default="", help="Optional path to write prediction JSONL.")
    parser.add_argument("--robot-id", default="temi-01")
    parser.add_argument("--mqtt-broker", default="127.0.0.1")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--abnormal-publish", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--abnormal-cooldown-seconds", type=float, default=0.0)
    parser.add_argument("--abnormal-source", default="temi_video_action_tester")
    parser.add_argument("--shared-root", default="/TemiAgent/temi_shared")
    parser.add_argument("--discord-notify", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--discord-env-path", default=DEFAULT_DISCORD_ENV_PATH)
    parser.add_argument("--discord-max-files", type=int, default=8)
    parser.add_argument("--pre-alert-speak", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--pre-alert-language", default="zh-TW")
    parser.add_argument("--model", default="gemma-4-e4b-finetuned@q8_0")
    parser.add_argument("--gguf-model-path", default=DEFAULT_GGUF_MODEL_PATH)
    parser.add_argument("--mmproj-path", default=DEFAULT_MMPROJ_PATH)
    parser.add_argument("--llama-server", default=DEFAULT_LLAMA_SERVER_PATH)
    parser.add_argument("--llama-api-base-url", default="")
    parser.add_argument("--llama-server-host", default="127.0.0.1")
    parser.add_argument("--llama-server-port", type=int, default=8011)
    parser.add_argument("--llama-ctx-size", type=int, default=8192)
    parser.add_argument("--llama-threads", type=int, default=8)
    parser.add_argument("--llama-gpu-layers", default="all")
    parser.add_argument("--llama-startup-timeout", type=float, default=30.0)
    parser.add_argument("--pose-mode", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--pose-model", default="yolo26x-pose.pt")
    parser.add_argument("--pose-device", default="0")
    parser.add_argument("--history-seconds", type=int, default=3)
    parser.add_argument("--current-second-samples", type=int, default=5)
    parser.add_argument("--max-output-tokens", type=int, default=96)
    parser.add_argument("--inference-jpeg-quality", type=int, default=92)
    parser.add_argument("--inference-long-side", type=int, default=896)
    parser.add_argument("--evidence-jpeg-quality", type=int, default=92)
    parser.add_argument("--retention-seconds", type=float, default=6.0)
    parser.add_argument("--fallback-fps", type=float, default=30.0)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    if args.max_windows < 0:
        raise SystemExit("--max-windows must be non-negative")
    if args.history_seconds < 1:
        raise SystemExit("--history-seconds must be at least 1")
    if args.current_second_samples < 1:
        raise SystemExit("--current-second-samples must be at least 1")
    if args.history_seconds + args.current_second_samples != 8:
        raise SystemExit("--history-seconds plus --current-second-samples must equal 8")
    if not 1 <= args.mqtt_port <= 65535:
        raise SystemExit("--mqtt-port must be in 1-65535")
    if not 1 <= args.llama_server_port <= 65535:
        raise SystemExit("--llama-server-port must be in 1-65535")
    if args.fallback_fps <= 0:
        raise SystemExit("--fallback-fps must be positive")
    if not 1 <= args.inference_jpeg_quality <= 100:
        raise SystemExit("--inference-jpeg-quality must be in 1-100")
    if not 1 <= args.evidence_jpeg_quality <= 100:
        raise SystemExit("--evidence-jpeg-quality must be in 1-100")
    if args.inference_long_side < 0:
        raise SystemExit("--inference-long-side must be non-negative")
    if not args.publish:
        args.abnormal_publish = "disabled"
    return args


def main() -> None:
    """Run the video tester."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    started = time.monotonic()
    results = asyncio.run(run_video_test(args))
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if args.output_jsonl:
        output_path = Path(args.output_jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    for result in results:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    LOGGER.info("processed %s inference windows in %sms", len(results), elapsed_ms)


if __name__ == "__main__":
    main()
