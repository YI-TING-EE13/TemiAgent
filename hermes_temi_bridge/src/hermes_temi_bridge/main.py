"""Service entry point for routing Temi ASR events through Hermes."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import time
from typing import Any

from .action_validator import ActionValidationError, validate_action_output
from .care_context_builder import CareContextBuilder
from .command_dispatcher import build_command_request, fallback_command
from .config import BridgeConfig
from .event_models import ASRFinalEvent, EventValidationError, PerceptionAbnormalEvent
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
from .image_resolver import ImageValidationError, translate_frames, validate_image_file
from .logging_utils import EventJsonlLogger, configure_logging
from .memory_store import EventContext, MemoryActionError, StructuredMemoryStore
from .mqtt_client import TemiMqttClient

LOGGER = logging.getLogger(__name__)

FALLBACKS = {
    "missing_image": "我目前看不到剛才的畫面，請再說一次或讓我重新看一下。",
    "empty_asr_text": "我沒有聽清楚，請再說一次。",
    "invalid_hermes_json": "抱歉，我剛剛沒有理解清楚，請再說一次。",
    "unsafe_action": "這個動作目前不支援，我可以改用其他方式協助你。",
    "hermes_timeout": "我還在思考，但目前需要多一點時間。請稍後再試一次。",
    "generic": "抱歉，我剛剛沒有理解清楚，請再說一次。",
}


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
        care_context_builder: CareContextBuilder | None = None,
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

    def start(self) -> None:
        """Start the MQTT runtime and block forever."""
        self.mqtt_client.set_asr_handler(self.handle_asr_payload)
        self.mqtt_client.set_abnormal_handler(self.handle_abnormal_payload)
        self.mqtt_client.set_result_handler(self.handle_command_result)
        self.mqtt_client.connect()
        self.mqtt_client.loop_forever()

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
            care_context = self._build_care_context(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source="asr.final",
                asr_text=event.asr_text,
                image_paths=[frame.path for frame in event.frames],
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
                memory_results = self.memory_store.execute(
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
                FALLBACKS["generic"],
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
            care_context = self._build_care_context(
                event_id=event.event_id,
                robot_id=event.robot_id,
                source="perception.abnormal",
                asr_text="",
                image_paths=[frame.path for frame in event.frames],
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
                memory_results = self.memory_store.execute(
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
                FALLBACKS["generic"],
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


    def _build_care_context(
        self,
        *,
        event_id: str,
        robot_id: str,
        source: str,
        asr_text: str | None,
        image_paths: list[str],
    ) -> dict[str, Any] | None:
        """Build structured care context if the read path is enabled."""
        if self.care_context_builder is None:
            return None
        return self.care_context_builder.build_for_event(
            event_id=event_id,
            robot_id=robot_id,
            source=source,
            asr_text=asr_text,
            image_paths=image_paths,
        )

    def handle_command_result(self, topic: str, payload: dict[str, Any]) -> None:
        """Persist command result notifications for later inspection."""
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        self.event_logger.write_trace(
            event_id=event_id,
            robot_id=robot_id,
            source_type=str(payload.get("source_type") or "command.result"),
            stage="command_result_received",
            record_type="command_result",
            status=str(payload.get("status") or "received"),
            component="mqtt",
            payload={"topic": topic, "command_result": payload},
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
