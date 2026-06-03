"""Configuration helpers for the TemiAgent backend runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SYSTEM_PROMPT = """You are Temi, an embodied AI robot.

Return only a JSON array of action objects after considering the user's speech
and the supplied camera frames. Supported actions are:
- {"action": "speak", "parameters": {"text": "...", "continue_listening": false}}
- {"action": "navigate", "parameters": {"target_location": "..."}}
"""


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean value from an environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read an integer value from an environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def discover_prompt_file() -> Path | None:
    """Locate the Temi skill prompt when the backend lives inside TemiAgent."""
    explicit_path = os.getenv("TEMI_SKILLS_PROMPT_FILE")
    if explicit_path:
        path = Path(explicit_path).expanduser()
        return path if path.exists() else None

    current = Path(__file__).resolve()
    candidate_suffixes = [
        ("skills", "temi_control", "SKILL.md"),
        ("skills", "temi-robot-control", "SKILL.md"),
    ]
    for parent in current.parents:
        for suffix in candidate_suffixes:
            candidate = parent.joinpath(*suffix)
            if candidate.exists():
                return candidate
    return None


@dataclass(frozen=True)
class AgentConfig:
    """Runtime configuration for MQTT, vision streaming, and the local VLM."""

    mqtt_broker: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_client_id: str = "temi-backend-brain"
    vision_host: str = "0.0.0.0"
    vision_port: int = 8080
    enable_frame_broadcast: bool = True
    frame_broadcast_host: str = "0.0.0.0"
    frame_broadcast_port: int = 8081
    frame_broadcast_jpeg_quality: int = 80
    lm_base_url: str = "http://localhost:1234/v1"
    lm_api_key: str = "lm-studio"
    lm_model: str = "local-model"
    debug_frames_dir: Path = Path("debug_frames")
    enable_debug_frames: bool = True
    system_prompt_file: Path | None = None

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Build configuration from environment variables with safe defaults."""
        return cls(
            mqtt_broker=os.getenv("TEMI_MQTT_BROKER", "127.0.0.1"),
            mqtt_port=_env_int("TEMI_MQTT_PORT", 1883),
            mqtt_client_id=os.getenv("TEMI_MQTT_CLIENT_ID", "temi-backend-brain"),
            vision_host=os.getenv("TEMI_VISION_HOST", "0.0.0.0"),
            vision_port=_env_int("TEMI_VISION_PORT", 8080),
            enable_frame_broadcast=_env_bool("TEMI_ENABLE_FRAME_BROADCAST", True),
            frame_broadcast_host=os.getenv("TEMI_FRAME_BROADCAST_HOST", "0.0.0.0"),
            frame_broadcast_port=_env_int("TEMI_FRAME_BROADCAST_PORT", 8081),
            frame_broadcast_jpeg_quality=_env_int("TEMI_FRAME_BROADCAST_JPEG_QUALITY", 80),
            lm_base_url=os.getenv("TEMI_LM_BASE_URL", "http://localhost:1234/v1"),
            lm_api_key=os.getenv("TEMI_LM_API_KEY", "lm-studio"),
            lm_model=os.getenv("TEMI_LM_MODEL", "local-model"),
            debug_frames_dir=Path(os.getenv("TEMI_DEBUG_FRAMES_DIR", "debug_frames")),
            enable_debug_frames=_env_bool("TEMI_ENABLE_DEBUG_FRAMES", True),
            system_prompt_file=discover_prompt_file(),
        )

    def load_system_prompt(self) -> str:
        """Load the configured skill prompt or return a built-in safe fallback."""
        if self.system_prompt_file and self.system_prompt_file.exists():
            return self.system_prompt_file.read_text(encoding="utf-8")
        return DEFAULT_SYSTEM_PROMPT
