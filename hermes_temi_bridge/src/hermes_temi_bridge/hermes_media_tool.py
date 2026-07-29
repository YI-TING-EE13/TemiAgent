"""Root-owned callback adapter for Hermes native Media tools.

The resident Hermes process never publishes MQTT.  It forwards a bounded tool
call over a local Unix socket to this adapter; only the Bridge calls the
existing Media v1.1 publish APIs after validation.
"""

from __future__ import annotations

from typing import Any, Protocol

from .action_validator import ActionValidationError
from .media_contract import MediaContractError
from .resident_context import ActiveResident, ResidentContextStore


MEDIA_TOOL_ACTIONS = {"play_video", "pause_video", "resume_video", "stop_video"}
MEDIA_TOOL_VIDEO_IDS = {"elderly_hand_exercise"}


class MediaToolBridge(Protocol):
    """Minimal Bridge surface used by the root-owned callback."""

    media_registry: Any

    def publish_media_play(
        self,
        *,
        event_id: str,
        robot_id: str,
        resident_id: str,
        video_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def publish_media_control(
        self,
        *,
        robot_id: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def validate_media_tool_call(payload: dict[str, Any], *, enabled: bool) -> dict[str, str]:
    """Validate the separate native-tool contract before the Media v1.1 builder.

    This intentionally does not expand the generic Hermes action schema.  A
    native tool has a separate fail-closed contract and cannot provide URLs,
    file paths, Android intents, parameters, or a caller-supplied session ID.
    """
    if not enabled:
        raise ActionValidationError("hermes_media_tool_disabled")
    if not isinstance(payload, dict):
        raise ActionValidationError("invalid_media_tool_call")
    expected = {"event_id", "robot_id", "resident_id", "action", "video_id"}
    if set(payload) != expected:
        raise ActionValidationError(
            "invalid_media_tool_call_fields",
            {"missing": sorted(expected - set(payload)), "unexpected": sorted(set(payload) - expected)},
        )
    action = payload.get("action")
    video_id = payload.get("video_id")
    for name in ("event_id", "robot_id", "resident_id"):
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
            raise ActionValidationError("invalid_media_tool_call", {"field": name})
    if action not in MEDIA_TOOL_ACTIONS:
        raise ActionValidationError("UNSUPPORTED_MEDIA_ACTION", {"action": action})
    if video_id not in MEDIA_TOOL_VIDEO_IDS:
        raise ActionValidationError("VIDEO_ID_NOT_ALLOWED", {"video_id": video_id})
    return {
        "event_id": payload["event_id"].strip(),
        "robot_id": payload["robot_id"].strip(),
        "resident_id": payload["resident_id"].strip(),
        "action": action,
        "video_id": video_id,
    }


class HermesMediaToolCallback:
    """Validate and dispatch native resident Hermes media tool calls."""

    def __init__(
        self,
        bridge: MediaToolBridge,
        resident_context: ResidentContextStore,
        *,
        media_v11_enabled: bool,
        hermes_media_tool_enabled: bool,
        visual_routing_enabled: bool,
    ) -> None:
        self._bridge = bridge
        self._resident_context = resident_context
        self._media_v11_enabled = media_v11_enabled
        self._hermes_media_tool_enabled = hermes_media_tool_enabled
        self._visual_routing_enabled = visual_routing_enabled

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call the canonical Bridge API or return a machine-readable rejection."""
        try:
            call = validate_media_tool_call(
                payload,
                enabled=self._media_v11_enabled and self._hermes_media_tool_enabled,
            )
            active = self._resident_context.resolve(
                call["robot_id"], enabled=self._visual_routing_enabled
            )
            self._require_active_resident(active, call["resident_id"])
            if call["action"] == "play_video":
                request = self._bridge.publish_media_play(
                    event_id=call["event_id"],
                    robot_id=call["robot_id"],
                    resident_id=call["resident_id"],
                    video_id=call["video_id"],
                    parameters={},
                )
            else:
                request = self._bridge.publish_media_control(
                    robot_id=call["robot_id"],
                    action=call["action"],
                    parameters={},
                )
            return {
                "status": "published",
                "action": call["action"],
                "command_id": request["command_id"],
                "message_type": request["message_type"],
                "playback_confirmation": "pending_android_cmd_result",
            }
        except (ActionValidationError, MediaContractError) as exc:
            code = getattr(exc, "reason", None) or getattr(exc, "code", None) or "MEDIA_CALLBACK_REJECTED"
            return {"status": "rejected", "error_code": code}
        except Exception:
            return {"status": "rejected", "error_code": "MEDIA_CALLBACK_INTERNAL_ERROR"}

    @staticmethod
    def _require_active_resident(active: ActiveResident, requested_resident_id: str) -> None:
        if not active.is_confirmed or active.resident_id != requested_resident_id:
            raise ActionValidationError(
                "media_tool_active_resident_mismatch",
                {"active_resident_id": active.resident_id, "requested_resident_id": requested_resident_id},
            )
