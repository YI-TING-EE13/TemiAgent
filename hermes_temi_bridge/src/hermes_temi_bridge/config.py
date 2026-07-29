"""Environment-backed configuration for HermesTemiBridge."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from an env file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get_int(values: dict[str, str], name: str, default: int) -> int:
    """Read an integer config value from the environment or env file."""
    raw = os.getenv(name, values.get(name, str(default)))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _get_float(values: dict[str, str], name: str, default: float) -> float:
    """Read a finite floating-point value from environment or env file."""
    raw = os.getenv(name, values.get(name, str(default)))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {raw!r}")
    return value


def _get_bool(values: dict[str, str], name: str, default: bool) -> bool:
    """Read a boolean config value from the environment or env file."""
    raw = os.getenv(name, values.get(name, str(default))).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _get_csv(values: dict[str, str], name: str, default: list[str]) -> list[str]:
    """Read a comma-separated config value from the environment or env file."""
    raw = os.getenv(name, values.get(name, ""))
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class BridgeConfig:
    """All runtime settings required by HermesTemiBridge."""

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    robot_id_allowlist: tuple[str, ...] = ("temi-01",)
    temi_shared_bridge_path: str = "/var/lib/temi_shared"
    temi_shared_hermes_path: str = "/shared/temi"
    hermes_invoke_mode: str = "cli"
    hermes_cli_command: str = "hermes -z {prompt}"
    hermes_http_url: str = "http://127.0.0.1:8765/invoke"
    hermes_mock_response_text: str = "這是 Bridge mock 測試"
    hermes_timeout_seconds: int = 60
    max_actions_per_event: int = 5
    max_image_size_mb: int = 8
    event_dedup_ttl_seconds: int = 600
    log_level: str = "INFO"
    log_dir: str = "logs/events"
    trace_enabled: bool = True
    debug_trace_full: bool = False
    trace_include_asr_text: bool = True
    trace_run_id: str | None = None
    trace_max_field_chars: int = 2000
    memory_dir: str = "memory"
    care_context_enabled: bool = True
    care_context_max_events: int = 5
    care_context_max_chars: int = 4000
    media_v11_enabled: bool = False
    hermes_media_tool_enabled: bool = False
    demo_care_scenario_prompt_enabled: bool = False
    demo_resident_visual_routing_enabled: bool = False
    demo_operator_identity_enabled: bool = False
    demo_repeated_discomfort_enabled: bool = False
    demo_care_memory_root: str = ""
    demo_resident_context_ttl_seconds: int = 300
    demo_resident_visual_minimum_confidence: float = 0.70
    hermes_media_callback_socket: str = ""
    hermes_demo_identity_callback_socket: str = ""
    hermes_demo_care_callback_socket: str = ""
    demo_identity_state_dir: str = ""
    demo_identity_refresh_seconds: int = 10
    demo_identity_max_duration_seconds: int = 900

    def __post_init__(self) -> None:
        """Reject partial Demo-media configuration before connecting to MQTT."""
        if self.hermes_media_tool_enabled and not self.media_v11_enabled:
            raise ValueError("HERMES_MEDIA_TOOL_ENABLED=true requires MEDIA_V11_ENABLED=true")
        if self.hermes_media_tool_enabled and not self.hermes_media_callback_socket:
            raise ValueError(
                "HERMES_MEDIA_TOOL_ENABLED=true requires HERMES_MEDIA_CALLBACK_SOCKET"
            )
        if self.demo_care_scenario_prompt_enabled and not self.demo_care_memory_root:
            raise ValueError(
                "DEMO_CARE_SCENARIO_PROMPT_ENABLED=true requires DEMO_CARE_MEMORY_ROOT"
            )
        if self.demo_operator_identity_enabled:
            if not self.hermes_demo_identity_callback_socket:
                raise ValueError("RESIDENT_IDENTITY_ENABLED=true requires HERMES_DEMO_IDENTITY_CALLBACK_SOCKET")
            if not self.demo_identity_state_dir:
                raise ValueError("RESIDENT_IDENTITY_ENABLED=true requires DEMO_IDENTITY_STATE_DIR")
        if self.demo_repeated_discomfort_enabled:
            if not self.demo_operator_identity_enabled:
                raise ValueError("DEMO_REPEATED_DISCOMFORT_ENABLED=true requires RESIDENT_IDENTITY_ENABLED=true")
            if not self.demo_care_memory_root:
                raise ValueError("DEMO_REPEATED_DISCOMFORT_ENABLED=true requires DEMO_CARE_MEMORY_ROOT")
            if not self.hermes_demo_care_callback_socket:
                raise ValueError("DEMO_REPEATED_DISCOMFORT_ENABLED=true requires HERMES_DEMO_CARE_CALLBACK_SOCKET")
        if self.demo_resident_context_ttl_seconds <= 0:
            raise ValueError("DEMO_RESIDENT_CONTEXT_TTL_SECONDS must be positive")
        if not 0 <= self.demo_resident_visual_minimum_confidence <= 1:
            raise ValueError("DEMO_RESIDENT_VISUAL_MINIMUM_CONFIDENCE must be between 0 and 1")
        if self.demo_identity_refresh_seconds <= 0:
            raise ValueError("DEMO_IDENTITY_REFRESH_SECONDS must be positive")
        if self.demo_identity_max_duration_seconds <= 0 or self.demo_identity_refresh_seconds > self.demo_identity_max_duration_seconds:
            raise ValueError("DEMO_IDENTITY_MAX_DURATION_SECONDS must be at least DEMO_IDENTITY_REFRESH_SECONDS")

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "BridgeConfig":
        """Build configuration from process environment and an optional env file."""
        values = _read_env_file(Path(env_file))
        username = os.getenv("MQTT_USERNAME", values.get("MQTT_USERNAME", "")) or None
        password = os.getenv("MQTT_PASSWORD", values.get("MQTT_PASSWORD", "")) or None
        legacy_operator_identity_enabled = _get_bool(
            values, "DEMO_OPERATOR_IDENTITY_ENABLED", cls.demo_operator_identity_enabled
        )
        resident_identity_enabled = _get_bool(
            values, "RESIDENT_IDENTITY_ENABLED", legacy_operator_identity_enabled
        )
        return cls(
            mqtt_broker_host=os.getenv(
                "MQTT_BROKER_HOST", values.get("MQTT_BROKER_HOST", cls.mqtt_broker_host)
            ),
            mqtt_broker_port=_get_int(values, "MQTT_BROKER_PORT", cls.mqtt_broker_port),
            mqtt_username=username,
            mqtt_password=password,
            robot_id_allowlist=tuple(
                _get_csv(values, "ROBOT_ID_ALLOWLIST", list(cls.robot_id_allowlist))
            ),
            temi_shared_bridge_path=os.getenv(
                "TEMI_SHARED_BRIDGE_PATH",
                values.get("TEMI_SHARED_BRIDGE_PATH", cls.temi_shared_bridge_path),
            ),
            temi_shared_hermes_path=os.getenv(
                "TEMI_SHARED_HERMES_PATH",
                values.get("TEMI_SHARED_HERMES_PATH", cls.temi_shared_hermes_path),
            ),
            hermes_invoke_mode=os.getenv(
                "HERMES_INVOKE_MODE", values.get("HERMES_INVOKE_MODE", cls.hermes_invoke_mode)
            ),
            hermes_cli_command=os.getenv(
                "HERMES_CLI_COMMAND", values.get("HERMES_CLI_COMMAND", cls.hermes_cli_command)
            ),
            hermes_http_url=os.getenv(
                "HERMES_HTTP_URL", values.get("HERMES_HTTP_URL", cls.hermes_http_url)
            ),
            hermes_mock_response_text=os.getenv(
                "HERMES_MOCK_RESPONSE_TEXT",
                values.get("HERMES_MOCK_RESPONSE_TEXT", cls.hermes_mock_response_text),
            ),
            hermes_timeout_seconds=_get_int(
                values, "HERMES_TIMEOUT_SECONDS", cls.hermes_timeout_seconds
            ),
            max_actions_per_event=_get_int(
                values, "MAX_ACTIONS_PER_EVENT", cls.max_actions_per_event
            ),
            max_image_size_mb=_get_int(values, "MAX_IMAGE_SIZE_MB", cls.max_image_size_mb),
            event_dedup_ttl_seconds=_get_int(
                values, "EVENT_DEDUP_TTL_SECONDS", cls.event_dedup_ttl_seconds
            ),
            log_level=os.getenv("LOG_LEVEL", values.get("LOG_LEVEL", cls.log_level)),
            log_dir=os.getenv("LOG_DIR", values.get("LOG_DIR", cls.log_dir)),
            trace_enabled=_get_bool(values, "TRACE_ENABLED", cls.trace_enabled),
            debug_trace_full=_get_bool(values, "DEBUG_TRACE_FULL", cls.debug_trace_full),
            trace_include_asr_text=_get_bool(
                values, "TRACE_INCLUDE_ASR_TEXT", cls.trace_include_asr_text
            ),
            trace_run_id=os.getenv("TRACE_RUN_ID", values.get("TRACE_RUN_ID", "")) or None,
            trace_max_field_chars=_get_int(
                values, "TRACE_MAX_FIELD_CHARS", cls.trace_max_field_chars
            ),
            memory_dir=os.getenv("MEMORY_DIR", values.get("MEMORY_DIR", cls.memory_dir)),
            care_context_enabled=_get_bool(
                values, "CARE_CONTEXT_ENABLED", cls.care_context_enabled
            ),
            care_context_max_events=_get_int(
                values, "CARE_CONTEXT_MAX_EVENTS", cls.care_context_max_events
            ),
            care_context_max_chars=_get_int(
                values, "CARE_CONTEXT_MAX_CHARS", cls.care_context_max_chars
            ),
            media_v11_enabled=_get_bool(values, "MEDIA_V11_ENABLED", cls.media_v11_enabled),
            hermes_media_tool_enabled=_get_bool(
                values, "HERMES_MEDIA_TOOL_ENABLED", cls.hermes_media_tool_enabled
            ),
            demo_care_scenario_prompt_enabled=_get_bool(
                values,
                "DEMO_CARE_SCENARIO_PROMPT_ENABLED",
                cls.demo_care_scenario_prompt_enabled,
            ),
            demo_resident_visual_routing_enabled=_get_bool(
                values,
                "DEMO_RESIDENT_VISUAL_ROUTING_ENABLED",
                cls.demo_resident_visual_routing_enabled,
            ),
            demo_operator_identity_enabled=resident_identity_enabled,
            demo_repeated_discomfort_enabled=_get_bool(
                values,
                "DEMO_REPEATED_DISCOMFORT_ENABLED",
                cls.demo_repeated_discomfort_enabled,
            ),
            demo_care_memory_root=os.getenv(
                "DEMO_CARE_MEMORY_ROOT",
                values.get("DEMO_CARE_MEMORY_ROOT", cls.demo_care_memory_root),
            ),
            demo_resident_context_ttl_seconds=_get_int(
                values,
                "DEMO_RESIDENT_CONTEXT_TTL_SECONDS",
                cls.demo_resident_context_ttl_seconds,
            ),
            demo_resident_visual_minimum_confidence=_get_float(
                values,
                "DEMO_RESIDENT_VISUAL_MINIMUM_CONFIDENCE",
                cls.demo_resident_visual_minimum_confidence,
            ),
            hermes_media_callback_socket=os.getenv(
                "HERMES_MEDIA_CALLBACK_SOCKET",
                values.get("HERMES_MEDIA_CALLBACK_SOCKET", cls.hermes_media_callback_socket),
            ),
            hermes_demo_identity_callback_socket=os.getenv(
                "HERMES_DEMO_IDENTITY_CALLBACK_SOCKET",
                values.get("HERMES_DEMO_IDENTITY_CALLBACK_SOCKET", cls.hermes_demo_identity_callback_socket),
            ),
            hermes_demo_care_callback_socket=os.getenv(
                "HERMES_DEMO_CARE_CALLBACK_SOCKET",
                values.get("HERMES_DEMO_CARE_CALLBACK_SOCKET", cls.hermes_demo_care_callback_socket),
            ),
            demo_identity_state_dir=os.getenv(
                "DEMO_IDENTITY_STATE_DIR",
                values.get("DEMO_IDENTITY_STATE_DIR", cls.demo_identity_state_dir),
            ),
            demo_identity_refresh_seconds=_get_int(
                values,
                "DEMO_IDENTITY_REFRESH_SECONDS",
                cls.demo_identity_refresh_seconds,
            ),
            demo_identity_max_duration_seconds=_get_int(
                values,
                "DEMO_IDENTITY_MAX_DURATION_SECONDS",
                cls.demo_identity_max_duration_seconds,
            ),
        )
