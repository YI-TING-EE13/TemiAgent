#!/usr/bin/env python3
"""Exercise Bridge media v1.1 against an in-memory fake Android client."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes_temi_bridge" / "src"))

from hermes_temi_bridge.config import BridgeConfig  # noqa: E402
from hermes_temi_bridge.logging_utils import EventJsonlLogger  # noqa: E402
from hermes_temi_bridge.main import HermesTemiBridgeService  # noqa: E402
from hermes_temi_bridge.media_contract import validate_media_command_request  # noqa: E402


class InMemoryMqtt:
    """Capture canonical command publications for the fake Android client."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
        self.published.append((f"temi/{robot_id}/cmd/request", dict(payload)))


class FakeAndroidClient:
    """Validate Bridge requests and emit deterministic schema-valid results."""

    def __init__(self, service: HermesTemiBridgeService, robot_id: str) -> None:
        self.service = service
        self.robot_id = robot_id
        self.session_id = "session_fake_android_001"
        self.play_request: dict[str, Any] | None = None

    def accept_and_start(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        validate_media_command_request(request)
        self.play_request = request
        return [
            self._deliver(self._result(request, "accepted", playback_state=None)),
            self._deliver(self._result(request, "started", playback_state="playing")),
        ]

    def succeed_control(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_media_command_request(request)
        state = {
            "pause_video": "paused",
            "resume_video": "playing",
            "stop_video": "cancelled",
        }[request["action"]]
        return self._deliver(self._result(request, "succeeded", playback_state=state))

    def cancel_play_for_stop(
        self,
        stop_request: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.play_request is None:
            raise AssertionError("fake Android has no active play request")
        cancellation = self._result(
            self.play_request,
            "cancelled",
            playback_state="cancelled",
            cancelled_by_command_id=stop_request["command_id"],
            cancel_reason="remote_stop",
        )
        original = self._deliver(cancellation)
        cached = self._deliver({**cancellation, "result_delivery": "cached_replay"})
        return original, cached

    def _deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.handle_command_result(
            f"temi/{self.robot_id}/cmd/result",
            payload,
        )

    def _result(
        self,
        request: dict[str, Any],
        status: str,
        *,
        playback_state: str | None,
        cancelled_by_command_id: str | None = None,
        cancel_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "message_type": "video.command_result",
            "command_id": request["command_id"],
            "request_id": request["request_id"],
            "event_id": request["event_id"],
            "robot_id": request["robot_id"],
            "command_action": request["action"],
            "video_id": request["video_id"],
            "status": status,
            "terminal": status not in {"accepted", "started"},
            "playback_session_id": self.session_id,
            "target_playback_session_id": request["target_playback_session_id"],
            "active_playback_session_id": None,
            "playback_state": playback_state,
            "cancelled_by_command_id": cancelled_by_command_id,
            "cancel_reason": cancel_reason,
            "actor": "remote_command",
            "result_delivery": "original",
            "error_code": None,
            "error_message": None,
            "timestamp": "2026-07-26T10:00:01Z",
        }


class UnusedHermes:
    """Placeholder proving this isolated path does not invoke Hermes."""


def run(work_root: Path) -> dict[str, Any]:
    """Run play, controls, linked cancellation, replay, and trace assertions."""
    robot_id = "temi-01"
    event_id = "evt_media_fake_e2e_001"
    mqtt = InMemoryMqtt()
    service = HermesTemiBridgeService(
        BridgeConfig(
            robot_id_allowlist=(robot_id,),
            log_dir=(work_root / "logs").as_posix(),
            memory_dir=(work_root / "memory").as_posix(),
            media_v11_enabled=True,
        ),
        mqtt,
        UnusedHermes(),
        event_logger=EventJsonlLogger(work_root / "logs"),
    )
    android = FakeAndroidClient(service, robot_id)

    play = service.publish_media_play(
        event_id=event_id,
        robot_id=robot_id,
        resident_id="unknown",
        video_id="elderly_hand_exercise",
        command_id="cmd_fake_play_001",
        timestamp="2026-07-26T10:00:00Z",
    )
    android.accept_and_start(play)

    pause = service.publish_media_control(
        robot_id=robot_id,
        action="pause_video",
        command_id="cmd_fake_pause_001",
        timestamp="2026-07-26T10:00:02Z",
    )
    android.succeed_control(pause)
    resume = service.publish_media_control(
        robot_id=robot_id,
        action="resume_video",
        command_id="cmd_fake_resume_001",
        timestamp="2026-07-26T10:00:03Z",
    )
    android.succeed_control(resume)
    stop = service.publish_media_control(
        robot_id=robot_id,
        action="stop_video",
        command_id="cmd_fake_stop_001",
        timestamp="2026-07-26T10:00:04Z",
    )
    android.succeed_control(stop)
    cancellation, cached = android.cancel_play_for_stop(stop)

    if service.media_registry.active_session_id(robot_id) is not None:
        raise AssertionError("playback session remained active after linked cancellation")
    if cancellation["originating_play_command_id"] != play["command_id"]:
        raise AssertionError("play cancellation lost the originating play correlation")
    if cached["disposition"] != "cached_replay" or cached["side_effect_applied"]:
        raise AssertionError("cached terminal result was not handled idempotently")

    records = _read_trace(work_root / "logs", event_id)
    request_records = [item for item in records if item["stage"] == "command_request_published"]
    result_records = [item for item in records if item["stage"] == "command_result_received"]
    if len(request_records) != 4 or len(result_records) != 7:
        raise AssertionError("trace does not contain the expected media request/result timeline")
    if result_records[-1]["payload"]["result_disposition"] != "cached_replay":
        raise AssertionError("trace does not record cached replay disposition")

    return {
        "status": "ok",
        "published_topic": mqtt.published[0][0],
        "event_id": event_id,
        "play_command_id": play["command_id"],
        "stop_command_id": stop["command_id"],
        "playback_session_id": android.session_id,
        "request_trace_count": len(request_records),
        "result_trace_count": len(result_records),
        "cached_replay_disposition": cached["disposition"],
    }


def _read_trace(log_dir: Path, event_id: str) -> list[dict[str, Any]]:
    path = log_dir / f"{event_id}.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", help="Optional output root; defaults to a temporary directory.")
    args = parser.parse_args()
    if args.work_root:
        result = run(Path(args.work_root).resolve())
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
