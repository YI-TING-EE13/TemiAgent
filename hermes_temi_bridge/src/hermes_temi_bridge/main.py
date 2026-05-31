"""Service entry point for routing Temi ASR events through Hermes."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from .action_validator import ActionValidationError, validate_action_output
from .command_dispatcher import build_command_request, fallback_command
from .config import BridgeConfig
from .event_models import ASRFinalEvent, EventValidationError
from .hermes_client import (
    HermesClient,
    HttpHermesClient,
    HermesInvocationError,
    MockHermesClient,
    HermesOutputError,
    HermesRequest,
    HermesTimeoutError,
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
    ):
        """Create a Bridge service with injectable clients for tests."""
        self.config = config
        self.mqtt_client = mqtt_client
        self.hermes_client = hermes_client
        self.event_cache = event_cache or TTLProcessedEventCache(config.event_dedup_ttl_seconds)
        self.event_logger = event_logger or EventJsonlLogger(config.log_dir)
        self.memory_store = memory_store or StructuredMemoryStore(config.memory_dir)

    def start(self) -> None:
        """Start the MQTT runtime and block forever."""
        self.mqtt_client.set_asr_handler(self.handle_asr_payload)
        self.mqtt_client.set_result_handler(self.handle_command_result)
        self.mqtt_client.connect()
        self.mqtt_client.loop_forever()

    def handle_asr_payload(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle one canonical ASR event payload from MQTT."""
        event_id = str(payload.get("event_id") or "unknown_event")
        robot_id = str(payload.get("robot_id") or _robot_id_from_topic(topic) or "unknown_robot")
        try:
            event = ASRFinalEvent.from_payload(payload, self.config.robot_id_allowlist)
            if self.event_cache.seen(event.event_id):
                self.event_logger.write(
                    event.event_id,
                    "duplicate_event_ignored",
                    {"status": "ignored", "reason": "duplicate_event_id"},
                )
                return {"status": "ignored", "reason": "duplicate_event_id"}

            self.event_logger.write(
                event.event_id,
                "asr_event_received",
                {
                    "event_id": event.event_id,
                    "robot_id": event.robot_id,
                    "conversation_id": event.conversation_id,
                    "asr_text": event.asr_text,
                    "image_paths": [frame.path for frame in event.frames],
                },
            )

            for frame in event.frames:
                validate_image_file(frame.path, self.config.max_image_size_mb)
            translated_frames = translate_frames(
                event.frames,
                self.config.temi_shared_bridge_path,
                self.config.temi_shared_hermes_path,
            )
            hermes_request = HermesRequest(
                event_id=event.event_id,
                robot_id=event.robot_id,
                conversation_id=event.conversation_id,
                language=event.language,
                asr_text=event.asr_text,
                frames=translated_frames,
            )
            self.event_logger.write(event.event_id, "hermes_invocation_start", {})
            hermes_response = self.hermes_client.invoke(hermes_request)
            raw_path = self.event_logger.write(
                event.event_id,
                "hermes_invocation_end",
                {
                    "hermes_latency_ms": hermes_response.latency_ms,
                    "raw_hermes_output": hermes_response.raw_output,
                },
            )
            parsed_output = parse_hermes_output(hermes_response.raw_output)
            validated_output = validate_action_output(
                parsed_output,
                expected_event_id=event.event_id,
                expected_robot_id=event.robot_id,
                max_actions=self.config.max_actions_per_event,
            )
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
            command = None
            if validated_output.robot_actions:
                command = build_command_request(validated_output)
                self.mqtt_client.publish_command(event.robot_id, command)
            self.event_cache.mark_seen(event.event_id)
            self.event_logger.write(
                event.event_id,
                "event_completed",
                {
                    "validated_actions": validated_output.actions,
                    "robot_actions": validated_output.robot_actions,
                    "memory_action_results": memory_results,
                    "published_command_id": command["command_id"] if command else None,
                    "raw_hermes_output_path": str(raw_path),
                },
            )
            result = {"status": "success", "memory_action_results": memory_results}
            if command:
                result["command_id"] = command["command_id"]
            return result
        except EventValidationError as exc:
            text = FALLBACKS.get(exc.reason, FALLBACKS["generic"])
            return self._fail_with_fallback(event_id, robot_id, exc.reason, text, exc.details)
        except ImageValidationError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["missing_image"],
                {"missing_path": exc.path},
            )
        except HermesTimeoutError:
            return self._fail_with_fallback(
                event_id, robot_id, "hermes_timeout", FALLBACKS["hermes_timeout"]
            )
        except HermesOutputError as exc:
            return self._fail_with_fallback(
                event_id,
                robot_id,
                exc.reason,
                FALLBACKS["invalid_hermes_json"],
                {"raw_output": exc.raw_output},
            )
        except ActionValidationError as exc:
            return self._fail_with_fallback(
                event_id, robot_id, exc.reason, FALLBACKS["unsafe_action"], exc.details
            )
        except MemoryActionError as exc:
            return self._fail_with_fallback(
                event_id, robot_id, exc.reason, FALLBACKS["generic"], exc.details
            )
        except HermesInvocationError as exc:
            return self._fail_with_fallback(
                event_id, robot_id, "hermes_invocation_failed", FALLBACKS["generic"], {"error": str(exc)}
            )
        except Exception as exc:  # pragma: no cover - last-resort service protection
            LOGGER.exception("unexpected failure while handling ASR event")
            return self._fail_with_fallback(
                event_id, robot_id, "unexpected_error", FALLBACKS["generic"], {"error": str(exc)}
            )

    def handle_command_result(self, topic: str, payload: dict[str, Any]) -> None:
        """Persist command result notifications for later inspection."""
        event_id = str(payload.get("event_id") or "unknown_event")
        self.event_logger.write(event_id, "command_result", {"topic": topic, "command_result": payload})

    def _fail_with_fallback(
        self,
        event_id: str,
        robot_id: str,
        reason: str,
        text: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish a safe fallback speak command and record the failure."""
        command = fallback_command(event_id, robot_id, text, reason=reason)
        try:
            self.mqtt_client.publish_command(robot_id, command)
        except Exception:
            LOGGER.exception("failed to publish fallback command")
        self.event_logger.write(
            event_id,
            "event_failed",
            {
                "status": "failed",
                "reason": reason,
                "details": details or {},
                "fallback_command": command,
            },
        )
        return {"status": "failed", "reason": reason, **(details or {})}


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
