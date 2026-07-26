"""In-memory Bridge correlation for canonical media v1.1 commands and results."""

from __future__ import annotations

from dataclasses import dataclass
import json
import threading
from typing import Any

from .media_contract import (
    MEDIA_CONTROL_ACTIONS,
    MediaContractError,
    validate_media_command_request,
    validate_media_command_result,
)


@dataclass
class MediaCommandState:
    """Bridge-owned state for one published media command."""

    request: dict[str, Any]
    status: str = "published"
    terminal: bool = False
    playback_session_id: str | None = None
    playback_state: str | None = None
    last_outcome: str | None = None
    stop_pending_by_command_id: str | None = None


@dataclass(frozen=True)
class MediaResultDisposition:
    """Outcome of consuming one validated media result."""

    disposition: str
    side_effect_applied: bool
    command_id: str
    playback_session_id: str | None
    command_status: str
    command_terminal: bool
    originating_play_command_id: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition,
            "side_effect_applied": self.side_effect_applied,
            "command_id": self.command_id,
            "playback_session_id": self.playback_session_id,
            "command_status": self.command_status,
            "command_terminal": self.command_terminal,
            "originating_play_command_id": self.originating_play_command_id,
        }


class MediaSessionRegistry:
    """Track Bridge command/session correlation without owning App persistence."""

    def __init__(self) -> None:
        self._commands: dict[str, MediaCommandState] = {}
        self._session_to_play_command: dict[str, str] = {}
        self._active_session_by_robot: dict[str, str] = {}
        self._lock = threading.RLock()

    def register_published(self, request: dict[str, Any]) -> MediaCommandState:
        """Register a request after semantic validation and before MQTT publication."""
        validated = validate_media_command_request(request)
        command_id = validated["command_id"]
        with self._lock:
            existing = self._commands.get(command_id)
            if existing is not None:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "command_id is already registered and must not be republished",
                    details={"same_request": existing.request == validated},
                )
            action = validated["action"]
            robot_id = validated["robot_id"]
            active_session = self._active_session_by_robot.get(robot_id)
            if action == "play_video" and active_session is not None:
                raise MediaContractError(
                    "MEDIA_SESSION_ACTIVE",
                    "an active playback session already exists",
                    details={"active_playback_session_id": active_session},
                )
            if action in MEDIA_CONTROL_ACTIONS:
                self._validate_control_target(validated)
            state = MediaCommandState(request=validated)
            self._commands[command_id] = state
            return state

    def unregister_unpublished(self, command_id: str) -> None:
        """Remove a newly registered command when MQTT publication fails."""
        with self._lock:
            state = self._commands.get(command_id)
            if state is not None and state.status == "published" and state.last_outcome is None:
                self._commands.pop(command_id, None)

    def consume_result(self, payload: dict[str, Any]) -> MediaResultDisposition:
        """Validate, correlate, and apply one media result exactly once."""
        result = validate_media_command_result(payload)
        command_id = result["command_id"]
        with self._lock:
            command = self._commands.get(command_id)
            if command is None:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "result references an unknown Bridge command",
                    details={"command_id": command_id},
                )
            self._validate_result_correlation(command, result)
            outcome = _outcome_key(result)
            replay = self._classify_replay(command, result, outcome)
            if replay is not None:
                return self._disposition(command, result, replay, False)

            if result["command_action"] == "play_video":
                self._apply_play_result(command, result)
            else:
                self._apply_control_result(command, result)
            command.last_outcome = outcome
            delivery = result["result_delivery"]
            applied_disposition = "applied" if delivery == "original" else f"{delivery}_applied"
            return self._disposition(command, result, applied_disposition, True)

    def active_session_id(self, robot_id: str) -> str | None:
        with self._lock:
            return self._active_session_by_robot.get(robot_id)

    def active_play_request(self, robot_id: str) -> dict[str, Any] | None:
        with self._lock:
            session_id = self._active_session_by_robot.get(robot_id)
            play_command_id = self._session_to_play_command.get(session_id or "")
            command = self._commands.get(play_command_id or "")
            return dict(command.request) if command is not None else None

    def command_state(self, command_id: str) -> MediaCommandState | None:
        """Return a detached command snapshot for tests and service correlation."""
        with self._lock:
            state = self._commands.get(command_id)
            if state is None:
                return None
            return MediaCommandState(
                request=dict(state.request),
                status=state.status,
                terminal=state.terminal,
                playback_session_id=state.playback_session_id,
                playback_state=state.playback_state,
                last_outcome=state.last_outcome,
                stop_pending_by_command_id=state.stop_pending_by_command_id,
            )

    def _validate_control_target(self, request: dict[str, Any]) -> None:
        target = request["target_playback_session_id"]
        active = self._active_session_by_robot.get(request["robot_id"])
        if active is None or target != active:
            raise MediaContractError(
                "MEDIA_SESSION_NOT_FOUND",
                "control target is not the active playback session",
                details={"target_playback_session_id": target, "active_playback_session_id": active},
            )
        play_command_id = self._session_to_play_command.get(target)
        play = self._commands.get(play_command_id or "")
        if play is None or play.terminal:
            raise MediaContractError(
                "MEDIA_SESSION_NOT_FOUND",
                "control target has no active play command",
            )
        if play.stop_pending_by_command_id is not None:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "the active session is awaiting linked stop cancellation",
                details={"stop_command_id": play.stop_pending_by_command_id},
            )
        if request["event_id"] != play.request["event_id"]:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "control event_id must match the originating play event",
            )
        if request["resident_id"] != play.request["resident_id"]:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "control resident_id must match the originating play",
            )
        if request["video_id"] != play.request["video_id"]:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "control video_id must match the active session",
            )
        action = request["action"]
        if action == "pause_video" and play.playback_state != "playing":
            raise MediaContractError(
                "MEDIA_SESSION_NOT_PLAYING",
                "pause_video requires a playing session",
            )
        if action == "resume_video" and play.playback_state != "paused":
            raise MediaContractError(
                "MEDIA_SESSION_NOT_PAUSED",
                "resume_video requires a paused session",
            )
        if action == "stop_video" and play.playback_state not in {"playing", "paused"}:
            raise MediaContractError(
                "MEDIA_SESSION_NOT_PLAYING",
                "stop_video requires a playing or paused session",
            )

    def _validate_result_correlation(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
    ) -> None:
        request = command.request
        expected = {
            "request_id": request["request_id"],
            "event_id": request["event_id"],
            "robot_id": request["robot_id"],
            "command_action": request["action"],
            "video_id": request["video_id"],
            "target_playback_session_id": request["target_playback_session_id"],
        }
        mismatches = {
            field: {"expected": value, "actual": result.get(field)}
            for field, value in expected.items()
            if result.get(field) != value
        }
        if mismatches:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "result correlation fields do not match the published request",
                details={"mismatches": mismatches},
            )
        target = request["target_playback_session_id"]
        session_id = result["playback_session_id"]
        if request["action"] in MEDIA_CONTROL_ACTIONS and session_id is not None and session_id != target:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "control result session does not match its target",
            )

    def _classify_replay(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
        outcome: str,
    ) -> str | None:
        delivery = result["result_delivery"]
        if command.terminal:
            if outcome != command.last_outcome:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "terminal result conflicts with the recorded terminal outcome",
                )
            return "cached_replay" if delivery == "cached_replay" else "duplicate_terminal"
        if delivery == "cached_replay":
            return None
        if delivery == "active_reference":
            return "active_reference" if outcome == command.last_outcome else None
        if outcome == command.last_outcome:
            return "duplicate_result"
        return None

    def _apply_play_result(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
    ) -> None:
        status = result["status"]
        session_id = result["playback_session_id"]
        robot_id = result["robot_id"]
        if status == "accepted":
            if command.status != "published":
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "accepted result is out of order",
                )
            mapped_command = self._session_to_play_command.get(session_id)
            if mapped_command not in {None, result["command_id"]}:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "playback session is already mapped to another command",
                )
            active = self._active_session_by_robot.get(robot_id)
            if active not in {None, session_id}:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "accepted result conflicts with the active playback session",
                )
            command.playback_session_id = session_id
            self._session_to_play_command[session_id] = result["command_id"]
            self._active_session_by_robot[robot_id] = session_id
        elif status == "started":
            self._require_play_session(command, result)
            if command.status != "accepted":
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    "started result requires an accepted play command",
                )
        elif status == "rejected":
            if result["error_code"] == "MEDIA_SESSION_ACTIVE":
                active = self._active_session_by_robot.get(robot_id)
                if active != result["active_playback_session_id"]:
                    raise MediaContractError(
                        "MEDIA_CONTROL_CONFLICT",
                        "concurrent play rejection references an unknown active session",
                    )
            command.terminal = True
        elif status == "failed":
            if session_id is not None:
                self._require_play_session(command, result)
            command.terminal = True
            self._clear_active_play(command)
        elif status in {"completed", "cancelled"}:
            self._require_play_session(command, result)
            if command.status not in {"accepted", "started"}:
                raise MediaContractError(
                    "MEDIA_CONTROL_CONFLICT",
                    f"{status} result requires an active play command",
                )
            if status == "cancelled" and result["cancel_reason"] == "remote_stop":
                self._validate_remote_stop_link(command, result)
            command.terminal = True
            self._clear_active_play(command)
        else:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                f"invalid play lifecycle status: {status}",
            )
        command.status = status
        command.playback_state = result["playback_state"]
        if session_id is not None:
            command.playback_session_id = session_id

    def _apply_control_result(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
    ) -> None:
        status = result["status"]
        target = result["target_playback_session_id"]
        play_command_id = self._session_to_play_command.get(target)
        play = self._commands.get(play_command_id or "")
        if status == "succeeded":
            if play is None or play.terminal or self._active_session_by_robot.get(result["robot_id"]) != target:
                raise MediaContractError(
                    "MEDIA_SESSION_NOT_FOUND",
                    "control success references a non-active play session",
                )
            action = result["command_action"]
            if action == "pause_video":
                if play.playback_state != "playing":
                    raise MediaContractError(
                        "MEDIA_SESSION_NOT_PLAYING",
                        "pause result conflicts with the current playback state",
                    )
                play.playback_state = "paused"
            elif action == "resume_video":
                if play.playback_state != "paused":
                    raise MediaContractError(
                        "MEDIA_SESSION_NOT_PAUSED",
                        "resume result conflicts with the current playback state",
                    )
                play.playback_state = "playing"
            elif action == "stop_video":
                play.stop_pending_by_command_id = result["command_id"]
        command.status = status
        command.terminal = True
        command.playback_session_id = result["playback_session_id"]
        command.playback_state = result["playback_state"]

    def _validate_remote_stop_link(
        self,
        play: MediaCommandState,
        result: dict[str, Any],
    ) -> None:
        stop_id = result["cancelled_by_command_id"]
        stop = self._commands.get(stop_id or "")
        if (
            stop is None
            or stop.request["action"] != "stop_video"
            or stop.request["target_playback_session_id"] != result["playback_session_id"]
            or stop.status != "succeeded"
            or play.stop_pending_by_command_id != stop_id
        ):
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "remote play cancellation is not linked to a successful stop command",
            )

    def _require_play_session(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
    ) -> None:
        session_id = result["playback_session_id"]
        if (
            not session_id
            or command.playback_session_id != session_id
            or self._session_to_play_command.get(session_id) != result["command_id"]
        ):
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "result playback session does not match the originating play command",
            )

    def _clear_active_play(self, command: MediaCommandState) -> None:
        session_id = command.playback_session_id
        robot_id = command.request["robot_id"]
        if session_id and self._active_session_by_robot.get(robot_id) == session_id:
            self._active_session_by_robot.pop(robot_id, None)

    def _disposition(
        self,
        command: MediaCommandState,
        result: dict[str, Any],
        disposition: str,
        side_effect_applied: bool,
    ) -> MediaResultDisposition:
        session_id = result["playback_session_id"] or result["active_playback_session_id"]
        play_command_id = None
        if session_id:
            play_command_id = self._session_to_play_command.get(session_id)
        if result["command_action"] == "play_video":
            play_command_id = result["command_id"]
        return MediaResultDisposition(
            disposition=disposition,
            side_effect_applied=side_effect_applied,
            command_id=result["command_id"],
            playback_session_id=session_id,
            command_status=command.status,
            command_terminal=command.terminal,
            originating_play_command_id=play_command_id,
        )


def _outcome_key(result: dict[str, Any]) -> str:
    fields = (
        "command_id",
        "request_id",
        "event_id",
        "robot_id",
        "command_action",
        "video_id",
        "status",
        "terminal",
        "playback_session_id",
        "target_playback_session_id",
        "active_playback_session_id",
        "playback_state",
        "cancelled_by_command_id",
        "cancel_reason",
        "actor",
        "error_code",
        "error_message",
    )
    return json.dumps(
        {field: result[field] for field in fields},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
