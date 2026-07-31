"""Service entry point for routing Temi ASR events through Hermes."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any

from .action_validator import ActionValidationError, validate_action_output
from .abnormal_notification import AbnormalNotificationDispatcher
from .care_episode import (
    AWAITING_FIRST_RESPONSE,
    ESCALATION_SENT,
    EXPIRED,
    FOLLOW_UP_REQUIRED,
    INITIAL_ALERT_SENT,
    NO_RESPONSE,
    RESIDENT_RESPONDED,
    RESOLVED,
    CareEpisode,
    CareEpisodeStore,
)
from .care_confirmation import (
    CARE_DECLINED,
    CARE_EXISTING_ALERT_DELIVERED,
    CARE_NOTIFICATION_UNAVAILABLE,
    CARE_QUESTION,
    CARE_REASK,
    CARE_UNRESOLVED,
    PendingCareConfirmationStore,
    classify_care_episode_response,
    classify_care_confirmation_response,
    direct_alert_delivered,
    direct_alert_from_event,
)
from .care_context_builder import CareContextBuilder
from .command_dispatcher import build_command_request, fallback_command
from .config import BridgeConfig
from .demo_callback_socket import DemoCallbackSocketServer
from .demo_care_memory import resident_memory_dir
from .demo_identity import DemoIdentityController
from .demo_repeated_discomfort import DemoRepeatedDiscomfortController
from .event_models import ASRFinalEvent, EventValidationError, PerceptionAbnormalEvent
from .hermes_demo_tools import HermesDemoIdentityToolCallback, HermesRepeatedDiscomfortToolCallback
from .hermes_client import (
    HermesClient,
    HttpHermesClient,
    HermesInvocationError,
    MockHermesClient,
    HermesOutputError,
    HermesRequest,
    HermesTimeoutError,
    build_prompt,
    parse_hermes_output,
)
from .idempotency import TTLProcessedEventCache
from .hermes_media_tool import HermesMediaToolCallback
from .identity_contract import IdentityContractError, build_demo_identity_result
from .image_resolver import ImageValidationError, translate_frames, validate_image_file
from .logging_utils import EventJsonlLogger, configure_logging
from .media_contract import MediaContractError, build_media_command_request
from .media_callback_socket import MediaCallbackSocketServer
from .media_registry import MediaSessionRegistry
from .memory_store import EventContext, MemoryActionError, StructuredMemoryStore
from .mqtt_client import TemiMqttClient
from .resident_context import ActiveResident, ResidentContextStore

LOGGER = logging.getLogger(__name__)

FALLBACKS = {
    "missing_image": "我目前看不到剛才的畫面，請再說一次或讓我重新看一下。",
    "empty_asr_text": "我沒有聽清楚，請再說一次。",
    "invalid_hermes_json": "抱歉，我剛剛沒有理解清楚，請再說一次。",
    "unsafe_action": "我目前無法執行這個要求，但可以用安全的方式繼續協助你。",
    "unknown_resident_memory": "我先關心您：您現在還好嗎？如果感到不舒服或需要身邊的人協助，請直接告訴我。",
    "hermes_timeout": "我還在思考，但目前需要多一點時間。請稍後再試一次。",
    "generic": "抱歉，我剛剛沒有理解清楚，請再說一次。",
}


def _memory_action_failure_fallback_text(reason: str) -> str:
    """Keep private-memory refusal machine-readable while caring for the person."""
    if reason == "unknown_resident_memory_forbidden":
        return FALLBACKS["unknown_resident_memory"]
    return FALLBACKS["generic"]


class HermesTemiBridgeService:
    """Coordinate event validation, Hermes invocation, action validation, and MQTT dispatch."""

    def __init__(
        self,
        config: BridgeConfig,
        mqtt_client: Any,
        hermes_client: HermesClient | HttpHermesClient | MockHermesClient,
        event_cache: TTLProcessedEventCache | None = None,
        event_logger: EventJsonlLogger | None = None,
        memory_store: StructuredMemoryStore | None = None,
        care_confirmation_store: PendingCareConfirmationStore | None = None,
        care_episode_store: CareEpisodeStore | None = None,
        abnormal_notification_dispatcher: AbnormalNotificationDispatcher | None = None,
        care_context_builder: CareContextBuilder | None = None,
        media_registry: MediaSessionRegistry | None = None,
        resident_context: ResidentContextStore | None = None,
    ):
        """Create a Bridge service with injectable clients for tests."""
        self.config = config
        self.mqtt_client = mqtt_client
        self.hermes_client = hermes_client
        self.event_cache = event_cache or TTLProcessedEventCache(config.event_dedup_ttl_seconds)
        self.event_logger = event_logger or EventJsonlLogger(
            config.log_dir,
            enabled=config.trace_enabled,
            run_id=config.trace_run_id,
            full_debug=config.debug_trace_full,
            include_asr_text=config.trace_include_asr_text,
            max_field_chars=config.trace_max_field_chars,
        )
        self.memory_store = memory_store or StructuredMemoryStore(config.memory_dir)
        self.care_confirmation_store = care_confirmation_store or PendingCareConfirmationStore(
            config.memory_dir,
            config.abnormal_care_confirmation_ttl_seconds,
        )
        self.care_episode_store = care_episode_store or CareEpisodeStore(
            config.memory_dir,
            first_response_timeout_seconds=config.abnormal_care_first_response_timeout_seconds,
            second_response_timeout_seconds=config.abnormal_care_second_response_timeout_seconds,
        )
        self.abnormal_notification_dispatcher = (
            abnormal_notification_dispatcher or AbnormalNotificationDispatcher(config)
        )
        self._episode_timeout_stop = threading.Event()
        self._episode_timeout_thread: threading.Thread | None = None
        self.care_context_builder = (
            care_context_builder
            if care_context_builder is not None
            else CareContextBuilder(
                config.memory_dir,
                max_events=config.care_context_max_events,
                max_chars=config.care_context_max_chars,
            )
            if config.care_context_enabled
            else None
        )
        self.media_registry = media_registry or MediaSessionRegistry()
        self.resident_context = resident_context or ResidentContextStore(
            ttl_seconds=config.demo_resident_context_ttl_seconds,
            minimum_confidence=config.demo_resident_visual_minimum_confidence,
        )
        self._media_callback_server: MediaCallbackSocketServer | None = None
        self._identity_callback_server: DemoCallbackSocketServer | None = None
        self._care_callback_server: DemoCallbackSocketServer | None = None
        self._identity_controller: DemoIdentityController | None = None
        self._repeated_discomfort_controller: DemoRepeatedDiscomfortController | None = None
        self._demo_operator_identity_event_ids: dict[str, set[str]] = {}
        if config.hermes_media_tool_enabled:
            callback = HermesMediaToolCallback(
                self,
                self.resident_context,
                media_v11_enabled=config.media_v11_enabled,
                hermes_media_tool_enabled=config.hermes_media_tool_enabled,
                visual_routing_enabled=config.demo_resident_visual_routing_enabled,
            )
            self._media_callback_server = MediaCallbackSocketServer(
                config.hermes_media_callback_socket,
                callback,
            )
        if config.demo_operator_identity_enabled:
            demo_robot_id = config.robot_id_allowlist[0]
            self._identity_controller = DemoIdentityController(
                robot_id=demo_robot_id,
                state_dir=config.demo_identity_state_dir,
                publish=lambda status, reason, trigger_event_id: self.publish_demo_identity_result(
                    robot_id=demo_robot_id,
                    identity_status=status,
                    reason=reason,
                    trigger_event_id=trigger_event_id,
                ),
                refresh_seconds=config.demo_identity_refresh_seconds,
                max_duration_seconds=config.demo_identity_max_duration_seconds,
            )
            self._identity_callback_server = DemoCallbackSocketServer(
                config.hermes_demo_identity_callback_socket,
                HermesDemoIdentityToolCallback(
                    self._identity_controller,
                    allowed_robot_ids=(demo_robot_id,),
                ),
            )
        if config.demo_repeated_discomfort_enabled:
            self._repeated_discomfort_controller = DemoRepeatedDiscomfortController(
                memory_root=config.demo_care_memory_root,
                active_resident=self._active_resident,
            )
            self._care_callback_server = DemoCallbackSocketServer(
                config.hermes_demo_care_callback_socket,
                HermesRepeatedDiscomfortToolCallback(
                    self._repeated_discomfort_controller,
                    allowed_robot_ids=(config.robot_id_allowlist[0],),
                    trace_callback=self._trace_repeated_discomfort_callback,
                ),
            )

    def start(self) -> None:
        """Start the MQTT runtime and block forever."""
        self.mqtt_client.set_asr_handler(self.handle_asr_payload)
        self.mqtt_client.set_abnormal_handler(self.handle_abnormal_payload)
        self.mqtt_client.set_result_handler(self.handle_command_result)
        self.mqtt_client.set_identity_handler(self.handle_identity_payload)
        if self._media_callback_server is not None:
            self._media_callback_server.start()
        if self._identity_callback_server is not None:
            self._identity_callback_server.start()
        if self._care_callback_server is not None:
            self._care_callback_server.start()
        if self.config.abnormal_care_episode_enabled:
            self._episode_timeout_stop.clear()
            self._episode_timeout_thread = threading.Thread(
                target=self._episode_timeout_loop,
                name="abnormal-care-episode-timeouts",
                daemon=True,
            )
            self._episode_timeout_thread.start()
        try:
            self.mqtt_client.connect()
            self.mqtt_client.loop_forever()
        finally:
            self._episode_timeout_stop.set()
            if self._episode_timeout_thread is not None:
                self._episode_timeout_thread.join(timeout=self.config.abnormal_care_timeout_poll_seconds + 1)
                self._episode_timeout_thread = None
            if self._identity_controller is not None:
                self._identity_controller.shutdown()
            if self._care_callback_server is not None:
                self._care_callback_server.stop()
            if self._identity_callback_server is not None:
                self._identity_callback_server.stop()
            if self._media_callback_server is not None:
                self._media_callback_server.stop()

    def _trace_repeated_discomfort_callback(
        self,
        action: str,
        event_id: str,
        robot_id: str,
        result: dict[str, Any],
    ) -> None:
        """Record callback evidence without storing the spoken blood-pressure values in trace."""
        trace_payload: dict[str, Any] = {
            "callback_action": action,
            "callback_status": result.get("status"),
        }
        prior = result.get("prior_event")
        if isinstance(prior, dict) and isinstance(prior.get("event_id"), str):
            trace_payload["retrieval_event_id"] = prior["event_id"]
        if isinstance(result.get("prior_event_id"), str):
            trace_payload["retrieval_event_id"] = result["prior_event_id"]
        if action == "record_repeated_blood_pressure" and isinstance(result.get("event_id"), str):
            trace_payload["new_event_id"] = result["event_id"]
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type="resident.demo_care.callback",
            stage="event_completed",
            record_type="demo_repeated_discomfort_callback",
            status=str(result.get("status") or "rejected"),
            component="bridge",
            payload=trace_payload,
        )

    def handle_identity_payload(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Consume the already-canonical identity result; never run inference here."""
        robot_id = _robot_id_from_topic(topic)
        if robot_id is None or robot_id not in self.config.robot_id_allowlist:
            return {"status": "ignored", "reason": "topic_robot_mismatch"}
        resident = self.resident_context.update_from_identity_result(
            robot_id=robot_id,
            payload=payload,
            enabled=self.config.demo_resident_visual_routing_enabled,
            operator_identity_enabled=(
                self.config.demo_operator_identity_enabled
                and (
                    payload.get("source") != "manual_selection"
                    or str(payload.get("event_id") or "")
                    in self._demo_operator_identity_event_ids.get(robot_id, set())
                )
            ),
        )
        if self._repeated_discomfort_controller is not None:
            self._repeated_discomfort_controller.identity_changed(robot_id, resident)
        self.event_logger.write_trace(
            event_id=str(payload.get("event_id") or "identity_unknown"),
            robot_id=robot_id,
            source_type="resident.identity.result",
            stage="event_completed",
            record_type="active_resident_updated",
            status="ok" if resident.is_confirmed else "unknown",
            component="bridge",
            payload={"active_resident": resident.as_prompt_context(), "topic": topic},
        )
        return {"status": "updated", "active_resident": resident.as_prompt_context()}

    def publish_demo_identity_result(
        self,
        *,
        robot_id: str,
        identity_status: str,
        reason: str,
        trigger_event_id: str | None,
    ) -> dict[str, Any]:
        """Validate, publish, and immediately apply one Demo identity result."""
        if not self.config.demo_operator_identity_enabled:
            return {"status": "rejected", "error_code": "DEMO_OPERATOR_IDENTITY_DISABLED"}
        if robot_id not in self.config.robot_id_allowlist:
            return {"status": "rejected", "error_code": "DEMO_IDENTITY_ROBOT_NOT_ALLOWED"}
        try:
            payload = build_demo_identity_result(
                identity_status=identity_status,
                reason=reason,
                event_id=trigger_event_id,
            )
        except IdentityContractError as exc:
            return {"status": "rejected", "error_code": str(exc)}
        allowed_event_ids = self._demo_operator_identity_event_ids.setdefault(robot_id, set())
        allowed_event_ids.add(payload["event_id"])
        try:
            self.mqtt_client.publish_identity_result(robot_id, payload)
        except Exception:
            allowed_event_ids.discard(payload["event_id"])
            raise
        topic = f"temi/{robot_id}/resident/identity/result"
        active = self.handle_identity_payload(topic, payload)
        self.event_logger.write_trace(
            event_id=payload["event_id"],
            robot_id=robot_id,
            source_type="resident.identity.result",
            stage="event_completed",
            record_type="demo_identity_result_published",
            status="published",
            component="bridge",
            payload={"topic": topic, "identity_result": payload, "active_resident": active.get("active_resident")},
        )
        return {"status": "published", "identity_result": payload}

    def handle_asr_payload(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle one canonical ASR event payload from MQTT."""
        total_started = time.monotonic()
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        source_type = "asr.final"
        failed_stage = "event_received"
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=source_type,
            stage="event_received",
            status="started",
            payload={
                "topic": topic,
                "raw_inbound_payload": payload,
                "asr_text": _payload_asr_text(payload),
                "image_paths": _payload_asr_image_paths(payload),
            },
            index_status="started",
            index_summary={"topic": topic, "asr_text": _payload_asr_text(payload)},
        )
        try:
            stage_started = time.monotonic()
            failed_stage = "input_validated"
            event = ASRFinalEvent.from_payload(payload, self.config.robot_id_allowlist)
            if self.event_cache.seen(event.event_id):
                self.event_logger.write_trace(
                    event_id=event.event_id,
                    robot_id=event.robot_id,
                    source_type=source_type,
                    stage="duplicate_event_ignored",
                    record_type="duplicate_event_ignored",
                    status="ignored",
                    level="WARNING",
                    duration_ms=_duration_ms(stage_started),
                    payload={"reason": "duplicate_event_id"},
                    index_status="ignored",
                    index_summary={"reason": "duplicate_event_id"},
                )
                return {"status": "ignored", "reason": "duplicate_event_id"}

            care_followup = self._handle_pending_care_confirmation(event)
            if care_followup is not None:
                self.event_cache.mark_seen(event.event_id)
                return care_followup

            image_validation = []
            for frame in event.frames:
                validate_image_file(frame.path, self.config.max_image_size_mb)
                image_validation.append(
                    {
                        "name": frame.name,
                        "path": frame.path,
                        "ts_ms": frame.ts_ms,
                        "mime_type": frame.mime_type,
                        "status": "valid",
                    }
                )
            translated_frames = translate_frames(
                event.frames,
                self.config.temi_shared_bridge_path,
                self.config.temi_shared_hermes_path,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "event_id": event.event_id,
                    "robot_id": event.robot_id,
                    "conversation_id": event.conversation_id,
                    "language": event.language,
                    "asr_text": event.asr_text,
                    "frame_count": len(event.frames),
                    "frames": [_frame_metadata(frame) for frame in event.frames],
                    "image_validation": image_validation,
                    "translated_frames": translated_frames,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "care_context_built"
            active_resident = self._active_resident(event.robot_id)
            care_context = self._build_care_context(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source="asr.final",
                asr_text=event.asr_text,
                image_paths=[frame.path for frame in event.frames],
                active_resident=active_resident,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="care_context_built",
                status="ok" if care_context is not None else "skipped",
                duration_ms=_duration_ms(stage_started),
                payload=_care_context_trace_payload(care_context),
            )
            hermes_request = HermesRequest(
                event_id=event.event_id,
                robot_id=event.robot_id,
                conversation_id=event.conversation_id,
                language=event.language,
                asr_text=event.asr_text,
                frames=translated_frames,
                care_context=care_context,
                active_resident=active_resident.as_prompt_context(),
            )
            stage_started = time.monotonic()
            failed_stage = "hermes_request_prepared"
            prompt = build_prompt(hermes_request)
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_request_prepared",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "prompt": prompt,
                    "frame_count": len(translated_frames),
                    "hermes_frame_paths": [frame.get("hermes_path") for frame in translated_frames],
                    "care_context_available": care_context is not None,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "hermes_invocation_finished"
            hermes_response = self.hermes_client.invoke(hermes_request)
            raw_path = self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_invocation_finished",
                status="ok",
                duration_ms=hermes_response.latency_ms,
                payload={
                    "measured_stage_duration_ms": _duration_ms(stage_started),
                    "hermes_latency_ms": hermes_response.latency_ms,
                    "raw_hermes_output": hermes_response.raw_output,
                    "resident_dispatch": hermes_response.dispatch_metadata,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "hermes_output_validated"
            parsed_output = parse_hermes_output(hermes_response.raw_output)
            validated_output = validate_action_output(
                parsed_output,
                expected_event_id=event.event_id,
                expected_robot_id=event.robot_id,
                max_actions=self.config.max_actions_per_event,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_output_validated",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload=_validated_output_trace_payload(validated_output),
            )

            stage_started = time.monotonic()
            failed_stage = "memory_actions_completed"
            memory_results = []
            if validated_output.memory_actions:
                memory_results = self._memory_store_for(active_resident).execute(
                    validated_output,
                    EventContext(
                        asr_text=event.asr_text,
                        image_paths=[frame.path for frame in event.frames],
                        conversation_id=event.conversation_id,
                    ),
                )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="memory_actions_completed",
                status="ok" if validated_output.memory_actions else "skipped",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "memory_action_types": [action["type"] for action in validated_output.memory_actions],
                    "memory_action_results": memory_results,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "command_request_published"
            command = None
            command_status = "not_required"
            if validated_output.robot_actions:
                command = build_command_request(validated_output)
                self.mqtt_client.publish_command(event.robot_id, command)
                command_status = "published"
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="command_request_published",
                status=command_status,
                duration_ms=_duration_ms(stage_started),
                payload={
                    "command_status": command_status,
                    "command_id": command["command_id"] if command else None,
                    "robot_action_types": [action["type"] for action in validated_output.robot_actions],
                    "command_request": command,
                },
            )
            self.event_cache.mark_seen(event.event_id)
            total_duration_ms = _duration_ms(total_started)
            completion_summary = _completion_summary(
                validated_output=validated_output,
                command_status=command_status,
                total_duration_ms=total_duration_ms,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="event_completed",
                status="completed",
                payload={
                    **completion_summary,
                    "validated_actions": validated_output.actions,
                    "robot_actions": validated_output.robot_actions,
                    "memory_action_results": memory_results,
                    "published_command_id": command["command_id"] if command else None,
                    "raw_hermes_output_path": str(raw_path),
                },
                index_status="completed",
                index_summary=completion_summary,
            )
            result = {"status": "success", "memory_action_results": memory_results}
            if command:
                result["command_id"] = command["command_id"]
            return result
        except EventValidationError as exc:
            text = FALLBACKS.get(exc.reason, FALLBACKS["generic"])
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                text,
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except ImageValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["missing_image"],
                {"missing_path": exc.path},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except HermesTimeoutError:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "hermes_timeout",
                FALLBACKS["hermes_timeout"],
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message="Hermes invocation timed out",
            )
        except HermesOutputError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["invalid_hermes_json"],
                {"raw_output": exc.raw_output},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except ActionValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["unsafe_action"],
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except MemoryActionError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                _memory_action_failure_fallback_text(exc.reason),
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except HermesInvocationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "hermes_invocation_failed",
                FALLBACKS["generic"],
                {"error": str(exc)},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - last-resort service protection
            LOGGER.exception("unexpected failure while handling ASR event")
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "unexpected_error",
                FALLBACKS["generic"],
                {"error": str(exc)},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )

    def handle_abnormal_payload(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Start the immediate-alert, Hermes-led care flow for one abnormal event."""
        if self.config.abnormal_care_episode_enabled:
            return self._handle_abnormal_care_episode(topic, payload)
        if not self.config.abnormal_care_confirmation_enabled:
            return self._handle_abnormal_via_hermes_legacy(topic, payload)
        total_started = time.monotonic()
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        source_type = "perception.abnormal"
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=source_type,
            stage="event_received",
            status="started",
            payload={
                "topic": topic,
                "raw_inbound_payload": payload,
                "image_paths": _payload_abnormal_image_paths(payload),
                "observation": payload.get("observation") if isinstance(payload.get("observation"), dict) else {},
            },
            index_status="started",
            index_summary={"topic": topic},
        )
        try:
            event = PerceptionAbnormalEvent.from_payload(payload, self.config.robot_id_allowlist)
            if self.event_cache.seen(event.event_id):
                self.event_logger.write_trace(
                    event_id=event.event_id,
                    robot_id=event.robot_id,
                    source_type=source_type,
                    stage="duplicate_event_ignored",
                    record_type="duplicate_event_ignored",
                    status="ignored",
                    level="WARNING",
                    payload={"reason": "duplicate_event_id"},
                    index_status="ignored",
                    index_summary={"reason": "duplicate_event_id"},
                )
                return {"status": "ignored", "reason": "duplicate_event_id"}

            evidence_status = "valid"
            evidence_error = None
            try:
                for frame in event.frames:
                    validate_image_file(frame.path, self.config.max_image_size_mb)
            except ImageValidationError as exc:
                evidence_status = "degraded"
                evidence_error = exc.reason
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status=evidence_status,
                payload={
                    "event_id": event.event_id,
                    "robot_id": event.robot_id,
                    "action_name": event.action_name,
                    "evidence_status": evidence_status,
                    "evidence_error": evidence_error,
                },
            )
            pending, created = self.care_confirmation_store.create(
                event_id=event.event_id,
                robot_id=event.robot_id,
                abnormal_category=event.action_name,
                event_timestamp_ms=event.timestamp_ms,
                immediate_alert=direct_alert_from_event(event.raw),
            )
            if not created:
                return {"status": "ignored", "reason": "abnormal_care_confirmation_duplicate"}
            command = fallback_command(event.event_id, event.robot_id, CARE_QUESTION)
            self.mqtt_client.publish_command(event.robot_id, command)
            self.care_confirmation_store.update(
                event.event_id,
                prompt_command_id=str(command["command_id"]),
                failure_code="ABNORMAL_CARE_PROMPT_CREATED",
            )
            self.event_cache.mark_seen(event.event_id)
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="abnormal_care_confirmation_created",
                status="created",
                payload={
                    "failure_code": "ABNORMAL_PENDING_CONFIRMATION",
                    "abnormal_category": event.action_name,
                    "conversation_id": pending.conversation_id,
                    "expires_at_ms": pending.expires_at_ms,
                    "notification_target_class": pending.notification_target_class,
                    "immediate_alert_status": (pending.immediate_alert or {}).get("status"),
                },
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="command_request_published",
                status="published",
                payload={
                    "command_status": "published",
                    "command_id": command["command_id"],
                    "robot_action_types": ["speak"],
                    "command_request": command,
                },
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="event_completed",
                status="completed",
                payload={
                    "failure_code": "ABNORMAL_CARE_PROMPT_CREATED",
                    "command_status": "published",
                    "robot_action_types": ["speak"],
                    "memory_action_types": [],
                    "total_duration_ms": _duration_ms(total_started),
                },
                index_status="completed",
                index_summary={"command_status": "published", "failure_code": "ABNORMAL_PENDING_CONFIRMATION"},
            )
            return {"status": "success", "command_id": command["command_id"], "care_confirmation": "pending"}
        except EventValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "ABNORMAL_CARE_FALLBACK_USED",
                CARE_QUESTION,
                {"cause": exc.reason, **exc.details},
                failed_stage="input_validated",
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except Exception as exc:
            LOGGER.exception("abnormal care flow failed")
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "ABNORMAL_CARE_FALLBACK_USED",
                CARE_QUESTION,
                {"cause": type(exc).__name__},
                failed_stage="abnormal_care_confirmation_created",
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )

    def _handle_abnormal_care_episode(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate, alert, invoke Hermes, and persist one abnormal-care episode."""
        source_type = "perception.abnormal"
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        total_started = time.monotonic()
        try:
            event = PerceptionAbnormalEvent.from_payload(payload, self.config.robot_id_allowlist)
        except EventValidationError as exc:
            self.event_logger.write_trace(
                event_id=event_id,
                robot_id=robot_id,
                source_type=source_type,
                stage="input_validated",
                status="rejected",
                level="WARNING",
                payload={"reason": exc.reason, "details": exc.details},
            )
            return {"status": "rejected", "reason": exc.reason, **exc.details}
        try:
            for frame in event.frames:
                validate_image_file(frame.path, self.config.max_image_size_mb)
        except ImageValidationError as exc:
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status="rejected",
                level="WARNING",
                payload={"reason": exc.reason, "missing_path": exc.path},
            )
            return {"status": "rejected", "reason": exc.reason, "missing_path": exc.path}
        if event.is_test and not self.config.demo_test_event_ingress_enabled:
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status="rejected",
                level="WARNING",
                payload={"reason": "test_event_ingress_disabled"},
            )
            return {"status": "rejected", "reason": "test_event_ingress_disabled"}
        if event.is_test and event.resident_id not in self.config.demo_test_resident_allowlist:
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status="rejected",
                level="WARNING",
                payload={"reason": "unknown_test_resident"},
            )
            return {"status": "rejected", "reason": "unknown_test_resident"}
        now_monotonic_ms = _monotonic_ms()
        episode, created = self.care_episode_store.create(
            event_id=event.event_id,
            robot_id=event.robot_id,
            event_type=event.event_type,
            resident_id=event.resident_id,
            detected_timestamp_ms=event.timestamp_ms,
            request_id=event.request_id,
            run_id=event.run_id,
            scenario_id=event.scenario_id,
            is_test=event.is_test,
            now_monotonic_ms=now_monotonic_ms,
        )
        if not created:
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="duplicate_event_ignored",
                record_type="duplicate_event_ignored",
                status="ignored",
                level="WARNING",
                payload={"reason": "persistent_care_episode_duplicate"},
            )
            return {"status": "ignored", "reason": "duplicate_event_id", "episode_status": episode.status}

        self.event_logger.write_trace(
            event_id=event.event_id,
            robot_id=event.robot_id,
            source_type=source_type,
            stage="input_validated",
            status="ok",
            payload={
                "event_type": event.event_type,
                "is_test": event.is_test,
                "run_id": event.run_id,
                "scenario_id": event.scenario_id,
                "request_id": event.request_id,
                "evidence_frame_count": len(event.frames),
            },
        )
        receipt = self._dispatch_episode_notification(episode, "initial_alert")
        self.care_episode_store.transition(
            event.event_id,
            INITIAL_ALERT_SENT,
            now_monotonic_ms=_monotonic_ms(),
            reason="initial_alert_attempted",
        )
        self.event_logger.write_trace(
            event_id=event.event_id,
            robot_id=event.robot_id,
            source_type=source_type,
            stage="initial_notification_finished",
            status=str(receipt.get("status") or "failed"),
            payload={"notification_receipt": receipt},
        )

        # The legacy implementation below is the existing validated Hermes ->
        # action-validator -> canonical-command path.  It is intentionally
        # reused here instead of letting this episode layer build a command.
        hermes_result = self._handle_abnormal_via_hermes_legacy(topic, payload)
        self.care_episode_store.transition(
            event.event_id,
            AWAITING_FIRST_RESPONSE,
            now_monotonic_ms=_monotonic_ms(),
            reason="resident_hermes_invoked",
        )
        self.event_logger.write_trace(
            event_id=event.event_id,
            robot_id=event.robot_id,
            source_type=source_type,
            stage="episode_awaiting_first_response",
            status="pending",
            payload={
                "first_response_timeout_seconds": self.config.abnormal_care_first_response_timeout_seconds,
                "hermes_status": hermes_result.get("status"),
                "total_duration_ms": _duration_ms(total_started),
            },
        )
        return {
            **hermes_result,
            "care_episode": AWAITING_FIRST_RESPONSE,
            "notification_receipt": receipt,
        }

    def _dispatch_episode_notification(
        self,
        episode: CareEpisode,
        stage: str,
        *,
        resident_status: str | None = None,
    ) -> dict[str, Any]:
        """Reserve a stage before external I/O and return its persisted receipt."""
        now_monotonic_ms = _monotonic_ms()
        if not self.care_episode_store.reserve_notification_stage(
            episode.event_id, stage, now_monotonic_ms=now_monotonic_ms
        ):
            current = self.care_episode_store.get(episode.event_id)
            stages = current.notification_stages if current is not None else {}
            existing = stages.get(stage, {}) if isinstance(stages, dict) else {}
            receipt = existing.get("receipt") if isinstance(existing, dict) else None
            return dict(receipt) if isinstance(receipt, dict) else {
                "status": "unconfirmed_after_restart",
                "failure_code": "NOTIFICATION_STAGE_ALREADY_RESERVED",
                "stage": stage,
            }
        receipt = self.abnormal_notification_dispatcher.dispatch(
            stage=stage,
            event_id=episode.event_id,
            event_type=episode.event_type,
            robot_id=episode.robot_id,
            resident_id=episode.resident_id,
            detected_timestamp_ms=episode.detected_timestamp_ms,
            run_id=episode.run_id,
            scenario_id=episode.scenario_id,
            is_test=episode.is_test,
            resident_status=resident_status,
        )
        self.care_episode_store.complete_notification_stage(
            episode.event_id,
            stage,
            receipt,
            now_monotonic_ms=_monotonic_ms(),
        )
        return receipt

    def _handle_pending_care_confirmation(self, event: ASRFinalEvent) -> dict[str, Any] | None:
        """Resolve only an explicit answer before routing unrelated ASR to Hermes."""
        if self.config.abnormal_care_episode_enabled:
            return self._handle_care_episode_reply(event)
        if not self.config.abnormal_care_confirmation_enabled:
            return None
        pending = self.care_confirmation_store.active_for_robot(event.robot_id)
        if pending is None:
            return None
        response = classify_care_confirmation_response(
            event.asr_text,
            event.asr_confidence,
            self.config.abnormal_care_confirmation_min_asr_confidence,
        )
        if response == "unrelated":
            return None
        status = ""
        failure_code = ""
        if response == "accepted":
            if direct_alert_delivered(pending):
                status, failure_code, text = "notification_already_sent", "ABNORMAL_NOTIFICATION_ALREADY_SENT", CARE_EXISTING_ALERT_DELIVERED
            else:
                status, failure_code, text = "notification_unavailable", "ABNORMAL_NOTIFICATION_FAILED", CARE_NOTIFICATION_UNAVAILABLE
        elif response == "declined":
            status, failure_code, text = "declined", "ABNORMAL_CONFIRMATION_DECLINED", CARE_DECLINED
        elif pending.clarification_count >= 1:
            status, failure_code, text = "expired", "ABNORMAL_CONFIRMATION_EXPIRED", CARE_UNRESOLVED
        else:
            status, failure_code, text = "pending", "ABNORMAL_CONFIRMATION_AMBIGUOUS", CARE_REASK

        command = fallback_command(event.event_id, event.robot_id, text)
        self.mqtt_client.publish_command(event.robot_id, command)
        clarification_count = pending.clarification_count + 1 if response == "ambiguous" and status == "pending" else pending.clarification_count
        self.care_confirmation_store.update(
            pending.event_id,
            status=status,
            clarification_count=clarification_count,
            failure_code=failure_code,
        )
        self.event_logger.write_trace(
            event_id=pending.event_id,
            robot_id=event.robot_id,
            source_type="asr.final",
            stage="abnormal_care_follow_up_resolved",
            status=status,
            payload={
                "follow_up_event_id": event.event_id,
                "response_class": response,
                "failure_code": failure_code,
                "command_id": command["command_id"],
                "notification_delivery_verified": direct_alert_delivered(pending),
            },
        )
        return {"status": "success", "command_id": command["command_id"], "care_confirmation": status, "failure_code": failure_code}

    def _handle_care_episode_reply(self, event: ASRFinalEvent) -> dict[str, Any] | None:
        """Route one explicit care reply through Hermes without replaying notification I/O."""
        episode = self.care_episode_store.active_for_robot(event.robot_id)
        if episode is None:
            return None
        response = classify_care_episode_response(
            event.asr_text,
            event.asr_confidence,
            self.config.abnormal_care_confirmation_min_asr_confidence,
        )
        if response == "unrelated":
            return None
        now_monotonic_ms = _monotonic_ms()
        if response == "ambiguous" and episode.clarification_count >= 1:
            response = "unresolved"
        self.care_episode_store.transition(
            episode.event_id,
            RESIDENT_RESPONDED,
            now_monotonic_ms=now_monotonic_ms,
            reason=f"resident_reply:{response}",
        )
        status_receipt = self._dispatch_episode_notification(
            episode,
            "status_update",
            resident_status=response,
        )
        command_id = self._publish_episode_hermes_speak(
            episode,
            event_id=event.event_id,
            robot_id=event.robot_id,
            response_class=response,
            notification_status=str(status_receipt.get("status") or "unconfirmed"),
        )
        okay_already_rechecked = any(
            transition.get("reason") == "resident_reply:okay"
            for transition in episode.transitions
            if isinstance(transition, dict)
        )
        if response == "okay" and okay_already_rechecked:
            next_status = RESOLVED
            clarification_count = episode.clarification_count
        elif response in {"okay", "ambiguous", "unresolved", "needs_assistance"}:
            next_status = AWAITING_FIRST_RESPONSE
            clarification_count = (
                episode.clarification_count + 1
                if response in {"okay", "ambiguous"}
                else episode.clarification_count
            )
        else:
            next_status = EXPIRED
            clarification_count = episode.clarification_count
        updated = self.care_episode_store.transition(
            episode.event_id,
            next_status,
            now_monotonic_ms=_monotonic_ms(),
            reason=f"resident_reply_processed:{response}",
            clarification_count=clarification_count,
        )
        self.event_logger.write_trace(
            event_id=episode.event_id,
            robot_id=event.robot_id,
            source_type="asr.final",
            stage="abnormal_care_follow_up_resolved",
            status=updated.status,
            payload={
                "follow_up_event_id": event.event_id,
                "response_class": response,
                "command_id": command_id,
                "clarification_count": updated.clarification_count,
                "notification_receipt": status_receipt,
            },
        )
        return {
            "status": "success",
            "command_id": command_id,
            "care_episode": updated.status,
            "response_class": response,
            "notification_receipt": status_receipt,
        }

    def _publish_episode_hermes_speak(
        self,
        episode: CareEpisode,
        *,
        event_id: str,
        robot_id: str,
        response_class: str,
        notification_status: str | None = None,
    ) -> str:
        """Invoke resident Hermes, validate its speak-only action, and publish it."""
        initial_status = _episode_notification_status(episode, "initial_alert")
        request = HermesRequest(
            event_id=event_id,
            robot_id=robot_id,
            conversation_id=f"care-{episode.event_id}",
            language="zh-TW",
            asr_text="",
            frames=[],
            source_type="care.follow_up",
            care_context={
                "response_class": response_class,
                "initial_notification_status": initial_status,
                "notification_status": notification_status or initial_status,
                "originating_event_type": episode.event_type,
            },
        )
        try:
            hermes_response = self.hermes_client.invoke(request)
            parsed = parse_hermes_output(hermes_response.raw_output)
            validated = validate_action_output(
                parsed,
                expected_event_id=event_id,
                expected_robot_id=robot_id,
                max_actions=1,
            )
            if not validated.robot_actions or any(action["type"] != "speak" for action in validated.robot_actions):
                raise ActionValidationError("care_follow_up_requires_speak")
            command = build_command_request(validated)
            self.mqtt_client.publish_command(robot_id, command)
            status = "published"
        except (HermesInvocationError, HermesOutputError, ActionValidationError) as exc:
            validated = validate_action_output(
                _episode_fallback_output(
                    event_id,
                    robot_id,
                    response_class,
                    notification_status=notification_status,
                ),
                expected_event_id=event_id,
                expected_robot_id=robot_id,
                max_actions=1,
            )
            command = build_command_request(validated)
            self.mqtt_client.publish_command(robot_id, command)
            status = "fallback_after_hermes_failure"
            self.event_logger.write_trace(
                event_id=episode.event_id,
                robot_id=robot_id,
                source_type="care.follow_up",
                stage="hermes_follow_up_failed",
                status="failed",
                level="WARNING",
                payload={"failure_code": type(exc).__name__},
            )
        self.event_logger.write_trace(
            event_id=episode.event_id,
            robot_id=robot_id,
            source_type="care.follow_up",
            stage="command_request_published",
            status=status,
            payload={"command_id": command["command_id"], "command_request": command},
        )
        return str(command["command_id"])

    def _episode_timeout_loop(self) -> None:
        """Run bounded episode timeout checks without blocking MQTT message processing."""
        while not self._episode_timeout_stop.wait(self.config.abnormal_care_timeout_poll_seconds):
            try:
                self.process_abnormal_episode_timeouts()
            except Exception:  # pragma: no cover - runtime containment
                LOGGER.exception("abnormal care episode timeout processing failed")

    def process_abnormal_episode_timeouts(self, *, now_monotonic_ms: int | None = None) -> None:
        """Advance due episodes through one Hermes recheck and one deduplicated escalation."""
        now_ms = _monotonic_ms() if now_monotonic_ms is None else now_monotonic_ms
        for episode in self.care_episode_store.due_first_response(now_ms):
            self.care_episode_store.transition(
                episode.event_id,
                FOLLOW_UP_REQUIRED,
                now_monotonic_ms=now_ms,
                reason="first_response_timeout",
            )
            self._publish_episode_hermes_speak(
                episode,
                event_id=f"{episode.event_id}:follow-up",
                robot_id=episode.robot_id,
                response_class="timeout",
            )
            self.care_episode_store.transition(
                episode.event_id,
                NO_RESPONSE,
                now_monotonic_ms=_monotonic_ms(),
                reason="follow_up_requested",
            )
        for episode in self.care_episode_store.due_escalation(now_ms):
            receipt = self._dispatch_episode_notification(episode, "escalation")
            status = str(receipt.get("status") or "failed")
            final_state = ESCALATION_SENT if status in {"delivered", "mock_delivered"} else EXPIRED
            command_id = None
            if final_state == ESCALATION_SENT:
                command_id = self._publish_episode_hermes_speak(
                    episode,
                    event_id=f"{episode.event_id}:escalation",
                    robot_id=episode.robot_id,
                    response_class="escalated",
                    notification_status=status,
                )
            self.care_episode_store.transition(
                episode.event_id,
                final_state,
                now_monotonic_ms=_monotonic_ms(),
                reason="second_response_timeout",
            )
            self.event_logger.write_trace(
                event_id=episode.event_id,
                robot_id=episode.robot_id,
                source_type="care.episode",
                stage="escalation_notification_finished",
                status=status,
                payload={
                    "notification_receipt": receipt,
                    "episode_status": final_state,
                    "command_id": command_id,
                },
            )

    def _handle_abnormal_via_hermes_legacy(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle one abnormal perception event payload from MQTT."""
        total_started = time.monotonic()
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        source_type = "perception.abnormal"
        failed_stage = "event_received"
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=source_type,
            stage="event_received",
            status="started",
            payload={
                "topic": topic,
                "raw_inbound_payload": payload,
                "image_paths": _payload_abnormal_image_paths(payload),
                "observation": payload.get("observation") if isinstance(payload.get("observation"), dict) else {},
            },
            index_status="started",
            index_summary={
                "topic": topic,
                "observation": payload.get("observation") if isinstance(payload.get("observation"), dict) else {},
            },
        )
        try:
            stage_started = time.monotonic()
            failed_stage = "input_validated"
            event = PerceptionAbnormalEvent.from_payload(payload, self.config.robot_id_allowlist)
            if self.event_cache.seen(event.event_id):
                self.event_logger.write_trace(
                    event_id=event.event_id,
                    robot_id=event.robot_id,
                    source_type=source_type,
                    stage="duplicate_event_ignored",
                    record_type="duplicate_event_ignored",
                    status="ignored",
                    level="WARNING",
                    duration_ms=_duration_ms(stage_started),
                    payload={"reason": "duplicate_event_id"},
                    index_status="ignored",
                    index_summary={"reason": "duplicate_event_id"},
                )
                return {"status": "ignored", "reason": "duplicate_event_id"}

            image_validation = []
            for frame in event.frames:
                validate_image_file(frame.path, self.config.max_image_size_mb)
                image_validation.append(
                    {
                        "name": frame.name,
                        "path": frame.path,
                        "ts_ms": frame.ts_ms,
                        "mime_type": frame.mime_type,
                        "status": "valid",
                    }
                )
            translated_frames = translate_frames(
                event.frames,
                self.config.temi_shared_bridge_path,
                self.config.temi_shared_hermes_path,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="input_validated",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "event_id": event.event_id,
                    "robot_id": event.robot_id,
                    "action_name": event.action_name,
                    "reason": event.reason,
                    "frame_count": len(event.frames),
                    "frames": [_frame_metadata(frame) for frame in event.frames],
                    "image_validation": image_validation,
                    "translated_frames": translated_frames,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "care_context_built"
            active_resident = self._active_resident(event.robot_id)
            care_context = self._build_care_context(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source="perception.abnormal",
                asr_text="",
                image_paths=[frame.path for frame in event.frames],
                active_resident=active_resident,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="care_context_built",
                status="ok" if care_context is not None else "skipped",
                duration_ms=_duration_ms(stage_started),
                payload=_care_context_trace_payload(care_context),
            )
            hermes_request = HermesRequest(
                event_id=event.event_id,
                robot_id=event.robot_id,
                conversation_id=None,
                language="zh-TW",
                asr_text="",
                frames=translated_frames,
                care_context=care_context,
                active_resident=active_resident.as_prompt_context(),
                source_type="perception.abnormal",
                abnormal_action_name=event.action_name,
                abnormal_reason=event.reason,
            )
            stage_started = time.monotonic()
            failed_stage = "hermes_request_prepared"
            prompt = build_prompt(hermes_request)
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_request_prepared",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "prompt": prompt,
                    "frame_count": len(translated_frames),
                    "hermes_frame_paths": [frame.get("hermes_path") for frame in translated_frames],
                    "care_context_available": care_context is not None,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "hermes_invocation_finished"
            hermes_response = self.hermes_client.invoke(hermes_request)
            raw_path = self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_invocation_finished",
                status="ok",
                duration_ms=hermes_response.latency_ms,
                payload={
                    "measured_stage_duration_ms": _duration_ms(stage_started),
                    "hermes_latency_ms": hermes_response.latency_ms,
                    "raw_hermes_output": hermes_response.raw_output,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "hermes_output_validated"
            parsed_output = parse_hermes_output(hermes_response.raw_output)
            validated_output = validate_action_output(
                parsed_output,
                expected_event_id=event.event_id,
                expected_robot_id=event.robot_id,
                max_actions=self.config.max_actions_per_event,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="hermes_output_validated",
                status="ok",
                duration_ms=_duration_ms(stage_started),
                payload=_validated_output_trace_payload(validated_output),
            )

            stage_started = time.monotonic()
            failed_stage = "memory_actions_completed"
            memory_results = []
            if validated_output.memory_actions:
                memory_results = self._memory_store_for(active_resident).execute(
                    validated_output,
                    EventContext(
                        asr_text="",
                        image_paths=[frame.path for frame in event.frames],
                        conversation_id=None,
                    ),
                )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="memory_actions_completed",
                status="ok" if validated_output.memory_actions else "skipped",
                duration_ms=_duration_ms(stage_started),
                payload={
                    "memory_action_types": [action["type"] for action in validated_output.memory_actions],
                    "memory_action_results": memory_results,
                },
            )

            stage_started = time.monotonic()
            failed_stage = "command_request_published"
            command = None
            command_status = "not_required"
            if validated_output.robot_actions:
                command = build_command_request(validated_output)
                self.mqtt_client.publish_command(event.robot_id, command)
                command_status = "published"
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="command_request_published",
                status=command_status,
                duration_ms=_duration_ms(stage_started),
                payload={
                    "command_status": command_status,
                    "command_id": command["command_id"] if command else None,
                    "robot_action_types": [action["type"] for action in validated_output.robot_actions],
                    "command_request": command,
                },
            )
            self.event_cache.mark_seen(event.event_id)
            total_duration_ms = _duration_ms(total_started)
            completion_summary = _completion_summary(
                validated_output=validated_output,
                command_status=command_status,
                total_duration_ms=total_duration_ms,
            )
            self.event_logger.write_trace(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source_type=source_type,
                stage="event_completed",
                status="completed",
                payload={
                    **completion_summary,
                    "validated_actions": validated_output.actions,
                    "robot_actions": validated_output.robot_actions,
                    "memory_action_results": memory_results,
                    "published_command_id": command["command_id"] if command else None,
                    "raw_hermes_output_path": str(raw_path),
                },
                index_status="completed",
                index_summary=completion_summary,
            )
            result = {"status": "success", "memory_action_results": memory_results}
            if command:
                result["command_id"] = command["command_id"]
            return result
        except EventValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["generic"],
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except ImageValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["missing_image"],
                {"missing_path": exc.path},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except HermesTimeoutError:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "hermes_timeout",
                FALLBACKS["hermes_timeout"],
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message="Hermes invocation timed out",
            )
        except HermesOutputError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["invalid_hermes_json"],
                {"raw_output": exc.raw_output},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except ActionValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["unsafe_action"],
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except MemoryActionError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                _memory_action_failure_fallback_text(exc.reason),
                exc.details,
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except HermesInvocationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "hermes_invocation_failed",
                FALLBACKS["generic"],
                {"error": str(exc)},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - last-resort service protection
            LOGGER.exception("unexpected failure while handling abnormal event")
            return self._fail_with_fallback(
                event_id,
                robot_id,
                "unexpected_error",
                FALLBACKS["generic"],
                {"error": str(exc)},
                failed_stage=failed_stage,
                source_type=source_type,
                total_started=total_started,
                error_message=str(exc),
            )


    def _active_resident(self, robot_id: str) -> ActiveResident:
        """Resolve only a validated visual or explicitly enabled operator context."""
        return self.resident_context.resolve(
            robot_id,
            enabled=self.config.demo_resident_visual_routing_enabled,
            operator_identity_enabled=self.config.demo_operator_identity_enabled,
        )

    def _memory_store_for(self, active_resident: ActiveResident) -> StructuredMemoryStore:
        """Choose an isolated Demo partition or preserve the legacy default path."""
        if not self.config.demo_care_scenario_prompt_enabled:
            return self.memory_store
        if not active_resident.is_confirmed:
            raise MemoryActionError("unknown_resident_memory_forbidden")
        return StructuredMemoryStore(
            resident_memory_dir(self.config.demo_care_memory_root, active_resident.resident_id)
        )

    def _build_care_context(
        self,
        *,
        event_id: str,
        robot_id: str,
        source: str,
        asr_text: str | None,
        image_paths: list[str],
        active_resident: ActiveResident | None = None,
    ) -> dict[str, Any] | None:
        """Build structured care context if the read path is enabled."""
        if self.care_context_builder is None:
            return None
        if not self.config.demo_care_scenario_prompt_enabled:
            return self.care_context_builder.build_for_event(
                event_id=event_id,
                robot_id=robot_id,
                source=source,
                asr_text=asr_text,
                image_paths=image_paths,
            )
        active = active_resident or self._active_resident(robot_id)
        if not active.is_confirmed:
            return {
                "schema_version": "1.0",
                "event": {"event_id": event_id, "robot_id": robot_id, "source": source},
                "active_resident": active.as_prompt_context(),
                "resident": {},
                "active_reminders": [],
                "daily_state": {},
                "relevant_events": [],
                "read_status": {"warnings": ["unknown_resident_private_memory_not_read"]},
                "memory_policy": ["unknown resident cannot access father or mother private memory"],
            }
        builder = CareContextBuilder(
            resident_memory_dir(self.config.demo_care_memory_root, active.resident_id),
            max_events=self.config.care_context_max_events,
            max_chars=self.config.care_context_max_chars,
        )
        context = builder.build_for_event(
            event_id=event_id,
            robot_id=robot_id,
            source=source,
            asr_text=asr_text,
            image_paths=image_paths,
        )
        context["active_resident"] = active.as_prompt_context()
        return context

    def publish_media_play(
        self,
        *,
        event_id: str,
        robot_id: str,
        resident_id: str,
        video_id: str,
        parameters: dict[str, Any] | None = None,
        command_id: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Publish one feature-gated serialized play request."""
        self._require_media_v11(robot_id)
        request = build_media_command_request(
            event_id=event_id,
            robot_id=robot_id,
            resident_id=resident_id,
            action="play_video",
            video_id=video_id,
            parameters=parameters,
            command_id=command_id,
            timestamp=timestamp,
        )
        return self._publish_media_request(request, originating_play_command_id=None)

    def publish_media_control(
        self,
        *,
        robot_id: str,
        action: str,
        parameters: dict[str, Any] | None = None,
        command_id: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Publish a control only for the known active playback session."""
        self._require_media_v11(robot_id)
        play_request = self.media_registry.active_play_request(robot_id)
        session_id = self.media_registry.active_session_id(robot_id)
        if play_request is None or session_id is None:
            raise MediaContractError(
                "MEDIA_SESSION_NOT_FOUND",
                "cannot publish a media control before play acceptance",
                details={"robot_id": robot_id, "action": action},
            )
        request = build_media_command_request(
            event_id=play_request["event_id"],
            robot_id=robot_id,
            resident_id=play_request["resident_id"],
            action=action,
            video_id=play_request["video_id"],
            target_playback_session_id=session_id,
            parameters=parameters,
            command_id=command_id,
            timestamp=timestamp,
        )
        return self._publish_media_request(
            request,
            originating_play_command_id=play_request["command_id"],
        )

    def _publish_media_request(
        self,
        request: dict[str, Any],
        *,
        originating_play_command_id: str | None,
    ) -> dict[str, Any]:
        """Register, publish, and trace a validated media request."""
        command_id = request["command_id"]
        self.media_registry.register_published(request)
        try:
            self.mqtt_client.publish_command(request["robot_id"], request)
        except Exception:
            self.media_registry.unregister_unpublished(command_id)
            raise
        self.event_logger.write_trace(
            event_id=request["event_id"],
            robot_id=request["robot_id"],
            source_type="video.command",
            stage="command_request_published",
            status="published",
            component="bridge",
            payload={
                "command_status": "published",
                "command_id": command_id,
                "request_id": request["request_id"],
                "command_action": request["action"],
                "execution_class": request["execution_class"],
                "target_playback_session_id": request["target_playback_session_id"],
                "originating_play_command_id": originating_play_command_id,
                "command_request": request,
            },
        )
        return request

    def handle_command_result(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Strictly dispatch v1.0 and media v1.1 command results."""
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        schema_version = payload.get("schema_version")
        if schema_version == "1.0":
            result_status = str(payload.get("status") or "received")
            care_record = self.care_confirmation_store.update_by_command_result(
                str(payload.get("command_id") or ""), result_status
            )
            self._trace_command_result(
                topic,
                payload,
                status=result_status,
                extra={
                    "care_confirmation_event_id": care_record.event_id if care_record else None,
                    "care_confirmation_status": care_record.status if care_record else None,
                    "care_confirmation_failure_code": care_record.failure_code if care_record else None,
                },
            )
            result = {"status": "recorded", "schema_version": "1.0"}
            if care_record is not None:
                result["care_confirmation_status"] = care_record.status
            return result

        if schema_version != "1.1" or payload.get("message_type") != "video.command_result":
            return self._reject_command_result(
                topic,
                payload,
                "unsupported_schema_version",
                "command result discriminator is not supported",
            )
        if not self.config.media_v11_enabled:
            return self._reject_command_result(
                topic,
                payload,
                "media_v11_disabled",
                "MEDIA_V11_ENABLED is false",
            )
        topic_robot_id = _robot_id_from_topic(topic)
        if topic_robot_id is None or topic_robot_id != robot_id:
            return self._reject_command_result(
                topic,
                payload,
                "MEDIA_CONTROL_CONFLICT",
                "result robot_id does not match the MQTT topic",
            )
        try:
            disposition = self.media_registry.consume_result(payload)
        except MediaContractError as exc:
            return self._reject_command_result(topic, payload, exc.code, str(exc), exc.details)
        trace_payload = {
            "topic": topic,
            "command_id": payload["command_id"],
            "request_id": payload["request_id"],
            "command_action": payload["command_action"],
            "terminal": payload["terminal"],
            "playback_session_id": payload["playback_session_id"],
            "target_playback_session_id": payload["target_playback_session_id"],
            "active_playback_session_id": payload["active_playback_session_id"],
            "playback_state": payload["playback_state"],
            "cancelled_by_command_id": payload["cancelled_by_command_id"],
            "cancel_reason": payload["cancel_reason"],
            "actor": payload["actor"],
            "result_delivery": payload["result_delivery"],
            "result_disposition": disposition.disposition,
            "side_effect_applied": disposition.side_effect_applied,
            "originating_play_command_id": disposition.originating_play_command_id,
            "command_result": payload,
        }
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type="video.command_result",
            stage="command_result_received",
            record_type="command_result",
            status=str(payload["status"]),
            component="mqtt",
            payload=trace_payload,
        )
        return {"status": "processed", **disposition.as_dict()}

    def _trace_command_result(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        status: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Write one existing command_result trace record."""
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=str(payload.get("message_type") or payload.get("source_type") or "command.result"),
            stage="command_result_received",
            record_type="command_result",
            status=status,
            component="mqtt",
            payload={"topic": topic, "command_result": payload, **(extra or {})},
        )

    def _reject_command_result(
        self,
        topic: str,
        payload: dict[str, Any],
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trace and return a fail-closed result disposition."""
        self._trace_command_result(
            topic,
            payload,
            status="rejected",
            extra={
                "result_disposition": "rejected",
                "side_effect_applied": False,
                "error_code": code,
                "error_message": message,
                "details": details or {},
            },
        )
        return {"status": "rejected", "error_code": code, "error_message": message}

    def _require_media_v11(self, robot_id: str) -> None:
        """Enforce the rollout gate and robot allowlist before publication."""
        if not self.config.media_v11_enabled:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "MEDIA_V11_ENABLED is false; media requests are not published",
            )
        if robot_id not in self.config.robot_id_allowlist:
            raise MediaContractError(
                "MEDIA_CONTROL_CONFLICT",
                "robot_id is not allowlisted for Bridge publication",
                details={"robot_id": robot_id},
            )

    def _fail_with_fallback(
        self,
        event_id: str,
        robot_id: str,
        reason: str,
        text: str,
        details: dict[str, Any] | None = None,
        *,
        failed_stage: str = "event_failed",
        source_type: str | None = None,
        total_started: float | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Publish a safe fallback speak command and record the failure."""
        command = fallback_command(event_id, robot_id, text, reason=reason)
        fallback_command_published = False
        try:
            self.mqtt_client.publish_command(robot_id, command)
            fallback_command_published = True
        except Exception:
            LOGGER.exception("failed to publish fallback command")
        payload = {
            "failed_stage": failed_stage,
            "error_code": reason,
            "error_message": error_message or reason,
            "details": details or {},
            "fallback_generated": True,
            "fallback_command_published": fallback_command_published,
            "fallback_command_id": command.get("command_id"),
            "fallback_command": command,
            "total_duration_ms": _duration_ms(total_started) if total_started is not None else None,
        }
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=source_type,
            stage="event_failed",
            status="failed",
            level="ERROR",
            payload=payload,
            index_status="failed",
            index_summary={
                "failed_stage": failed_stage,
                "error_code": reason,
                "fallback_command_published": fallback_command_published,
            },
        )
        return {"status": "failed", "reason": reason, **(details or {})}


def _duration_ms(started: float | None) -> int | None:
    """Return elapsed milliseconds from a monotonic start time."""
    if started is None:
        return None
    return int((time.monotonic() - started) * 1000)


def _monotonic_ms() -> int:
    """Return the process-independent monotonic time basis used by care episodes."""
    return int(time.monotonic() * 1000)


def _episode_notification_status(episode: CareEpisode, stage: str) -> str:
    """Read a persisted notification status without revealing transport configuration."""
    stages = episode.notification_stages or {}
    value = stages.get(stage) if isinstance(stages, dict) else None
    return str(value.get("status") or "unconfirmed") if isinstance(value, dict) else "unconfirmed"


def _episode_fallback_output(
    event_id: str,
    robot_id: str,
    response_class: str,
    *,
    notification_status: str | None = None,
) -> dict[str, Any]:
    """Build a validator-bound fallback only after a resident Hermes invocation failed."""
    texts = {
        "okay": "好的，我知道了。我再確認一次：您現在有沒有頭暈、疼痛或需要協助？",
        "ambiguous": CARE_REASK,
        "unresolved": CARE_UNRESOLVED,
        "timeout": "我想再確認你是否安全。如果需要協助，請直接告訴我。",
    }
    receipt_confirmed = notification_status in {"delivered", "mock_delivered"}
    if response_class == "needs_assistance":
        text = (
            "我知道了，請先不要勉強移動。我已將需要協助的情況通知照護人員，會繼續陪著您。"
            if receipt_confirmed
            else "我知道了，請先不要勉強移動。我目前無法確認通知是否送出，會繼續陪著您。"
        )
    elif response_class == "escalated":
        text = (
            "我目前沒有收到您的回應，已通知照護人員前來確認。我會繼續留意您的狀況。"
            if receipt_confirmed
            else "我目前沒有收到您的回應，也無法確認通知是否送出。我會繼續留意您的狀況。"
        )
    else:
        text = texts.get(response_class, CARE_UNRESOLVED)
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": robot_id,
        "confidence": 0.0,
        "cognitive_state": {
            "intent": "abnormal_care_follow_up",
            "home_esi_level": "L2",
            "risk_reason": "Resident Hermes follow-up was unavailable; Bridge used a bounded care fallback.",
            "next_step": "speak",
        },
        "reasoning_summary": "Bounded care follow-up fallback after a failed Hermes invocation.",
        "actions": [
            {
                "action_id": "act_001",
                "type": "speak",
                "text": text,
                "language": "zh-TW",
            }
        ],
    }


def _payload_asr_text(payload: dict[str, Any]) -> str:
    """Extract ASR text from a raw payload for trace summaries."""
    asr = payload.get("asr")
    if isinstance(asr, dict):
        return str(asr.get("text") or "")
    return ""


def _payload_asr_image_paths(payload: dict[str, Any]) -> list[str]:
    """Extract ASR frame paths from a raw payload without image bytes."""
    vision = payload.get("vision")
    frames = vision.get("frames") if isinstance(vision, dict) else None
    if not isinstance(frames, list):
        return []
    paths = []
    for frame in frames:
        if isinstance(frame, dict):
            path = frame.get("path") or frame.get("uri")
            if isinstance(path, str):
                paths.append(path)
    return paths


def _payload_abnormal_image_paths(payload: dict[str, Any]) -> list[str]:
    """Extract abnormal evidence frame paths from a raw payload."""
    evidence = payload.get("evidence")
    frame_paths = evidence.get("frame_paths") if isinstance(evidence, dict) else None
    return [path for path in frame_paths if isinstance(path, str)] if isinstance(frame_paths, list) else []


def _frame_metadata(frame: Any) -> dict[str, Any]:
    """Return trace-safe frame metadata without image bytes."""
    return {
        "name": frame.name,
        "ts_ms": frame.ts_ms,
        "path": frame.path,
        "mime_type": frame.mime_type,
    }


def _care_context_trace_payload(care_context: dict[str, Any] | None) -> dict[str, Any]:
    """Build a compact care context trace payload."""
    if care_context is None:
        return {"care_context_available": False, "care_context": None}
    read_status = care_context.get("read_status") if isinstance(care_context.get("read_status"), dict) else {}
    relevant_events = care_context.get("relevant_events")
    active_reminders = care_context.get("active_reminders")
    return {
        "care_context_available": True,
        "relevant_event_count": len(relevant_events) if isinstance(relevant_events, list) else 0,
        "active_reminder_count": len(active_reminders) if isinstance(active_reminders, list) else 0,
        "read_warnings": read_status.get("warnings", []),
        "care_context": care_context,
    }


def _validated_output_trace_payload(validated_output: Any) -> dict[str, Any]:
    """Build a trace payload for Hermes' explicit JSON output."""
    cognitive_state = validated_output.cognitive_state
    return {
        "confidence": validated_output.confidence,
        "reasoning_summary": validated_output.reasoning_summary,
        "cognitive_state": {
            "intent": cognitive_state.get("intent"),
            "home_esi_level": cognitive_state.get("home_esi_level"),
            "risk_reason": cognitive_state.get("risk_reason"),
            "next_step": cognitive_state.get("next_step"),
        },
        "action_types": [action["type"] for action in validated_output.actions],
        "robot_action_types": [action["type"] for action in validated_output.robot_actions],
        "memory_action_types": [action["type"] for action in validated_output.memory_actions],
        "actions": validated_output.actions,
    }


def _completion_summary(
    *,
    validated_output: Any,
    command_status: str,
    total_duration_ms: int | None,
) -> dict[str, Any]:
    """Build the required final event summary payload."""
    cognitive_state = validated_output.cognitive_state
    return {
        "home_esi_level": cognitive_state.get("home_esi_level"),
        "robot_action_types": [action["type"] for action in validated_output.robot_actions],
        "memory_action_types": [action["type"] for action in validated_output.memory_actions],
        "command_status": command_status,
        "total_duration_ms": total_duration_ms,
    }


def _robot_id_from_topic(topic: str) -> str | None:
    """Extract the robot id from a topic shaped like ``temi/<robot_id>/...``."""
    parts = topic.split("/")
    if len(parts) >= 2 and parts[0] == "temi":
        return parts[1]
    return None


def create_hermes_client(config: BridgeConfig) -> HermesClient | HttpHermesClient | MockHermesClient:
    """Instantiate the configured Hermes client implementation."""
    mode = config.hermes_invoke_mode.strip().lower()
    if mode == "cli":
        return HermesClient(config.hermes_cli_command, config.hermes_timeout_seconds)
    if mode == "http":
        return HttpHermesClient(config.hermes_http_url, config.hermes_timeout_seconds)
    if mode == "mock":
        return MockHermesClient(config.hermes_mock_response_text)
    raise ValueError(f"unsupported HERMES_INVOKE_MODE: {config.hermes_invoke_mode!r}")


def main(argv: list[str] | None = None) -> int:
    """Run the Bridge CLI."""
    parser = argparse.ArgumentParser(description="Run the Hermes Temi Bridge service.")
    parser.add_argument("--env-file", default=".env", help="Path to .env file.")
    parser.add_argument(
        "--validate-json",
        help="Validate a single ASR event JSON file and print the resulting status.",
    )
    args = parser.parse_args(argv)

    config = BridgeConfig.from_env(args.env_file)
    configure_logging(config.log_level)
    hermes_client = create_hermes_client(config)

    if args.validate_json:
        class DryRunMqtt:
            """MQTT test double used by --validate-json."""

            def publish_command(self, robot_id: str, payload: dict[str, Any]) -> None:
                """Print the command that would have been published to MQTT."""
                print(json.dumps({"topic": f"temi/{robot_id}/cmd/request", "payload": payload}, ensure_ascii=False))

        payload = json.loads(Path(args.validate_json).read_text(encoding="utf-8"))
        service = HermesTemiBridgeService(config, DryRunMqtt(), hermes_client)
        print(json.dumps(service.handle_asr_payload("temi/local/asr/final", payload), ensure_ascii=False))
        return 0

    mqtt_client = TemiMqttClient(config)
    service = HermesTemiBridgeService(config, mqtt_client, hermes_client)
    service.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
