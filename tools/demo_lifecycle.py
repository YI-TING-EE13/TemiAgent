#!/usr/bin/env python3
"""Safe, reproducible lifecycle for the current TemiAgent Demo backend.

This tool owns only the Adapter, resident Hermes worker, Bridge and the
optional observation-only action viewer that it records in an external runtime
root.  It deliberately preserves LM Studio and an already healthy MQTT broker.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import fcntl
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any, Callable, Iterable
from urllib.error import URLError
from urllib.request import urlopen
import uuid


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_ROOT = ROOT / ".runtime" / "demo"
CANONICAL_CONFIG_PATH = CANONICAL_RUNTIME_ROOT / "demo.env"
PRODUCTION_TEMPLATE_PATH = ROOT / "config" / "demo.env.example"
NEWCOMER_MOCK_TEMPLATE_PATH = ROOT / "config" / "demo.mock.env.example"
BRIDGE_SRC = ROOT / "hermes_temi_bridge" / "src"
if BRIDGE_SRC.as_posix() not in sys.path:
    sys.path.insert(0, BRIDGE_SRC.as_posix())

from hermes_temi_bridge.demo_callback_socket import invoke_demo_callback_socket
from hermes_temi_bridge.demo_care_memory import seed_demo_care_memory, verify_demo_care_memory

ALLOWED_DIRTY_FILES = {
    "memory/daily_state.json",
    "memory/event_log.jsonl",
    "memory/reminders.json",
}
MEDIA_FLAGS = (
    "MEDIA_V11_ENABLED",
    "HERMES_MEDIA_TOOL_ENABLED",
    "HERMES_MEDIA_FAST_PATH_ENABLED",
)
MEDIA_TOOLS = ("play_video", "pause_video", "resume_video", "stop_video")
IDENTITY_TOOLS = ("start_demo_identity", "stop_demo_identity", "get_demo_identity_status")
REPEATED_DISCOMFORT_TOOLS = (
    "retrieve_repeated_discomfort",
    "confirm_repeated_headache",
    "record_repeated_blood_pressure",
)
CANONICAL_CONTEXT_LENGTH = 64_000
CANONICAL_LMSTUDIO_VISIBLE_GPUS = "0,1"
CANONICAL_LMSTUDIO_MODEL = "temi/gemma-4-31b-it-qat"
CANONICAL_LMSTUDIO_IDENTIFIER = "google/gemma-4-31b"
RESOURCE_MANIFEST_PATH = ROOT / "config" / "demo_resources.json"
PROFILE_PRODUCTION = "production"
PROFILE_NEWCOMER_MOCK = "newcomer_mock"
BRANCH_POLICY_REQUIRED = "required"
BRANCH_POLICY_DISABLED = "disabled"
PRODUCTION_PORTS = {
    "lmstudio": 1234,
    "mqtt": 1883,
    "adapter_vision": 8080,
    "adapter_frame": 8081,
    "resident": 8765,
    "viewer": 8010,
    "viewer_aux": 8011,
}
NEWCOMER_MOCK_PORTS = {
    "lmstudio": 29134,
    "mqtt": 29183,
    "adapter_vision": 29080,
    "adapter_frame": 29081,
    "resident": 29765,
    "viewer": 29010,
    "viewer_aux": 29011,
    "mock_android": 29012,
    "mock_discord": 29013,
}
STATE_STARTING = "STARTING"
STATE_HEALTHY = "HEALTHY"
STATE_UNHEALTHY = "UNHEALTHY"
STATE_START_FAILED = "START_FAILED"
STATE_STOPPED = "STOPPED"
HEALTHY_STATE_VALUES = {STATE_HEALTHY, "running"}
RECOVERABLE_STATE_VALUES = {STATE_STARTING, STATE_UNHEALTHY, STATE_START_FAILED}


class DemoError(RuntimeError):
    """Raised for a lifecycle precondition or ownership failure."""


def canonical_runtime_root() -> Path:
    """Return the only repository-local runtime hierarchy used by default."""

    return CANONICAL_RUNTIME_ROOT


def canonical_config_path() -> Path:
    """Return the only config path considered when --config is omitted."""

    return CANONICAL_CONFIG_PATH


def _same_path(left: Path, right: Path) -> bool:
    """Compare lexical absolute paths without following an untrusted symlink."""

    return os.path.abspath(os.fspath(left)) == os.path.abspath(os.fspath(right))


def _is_canonical_config_path(path: Path) -> bool:
    return _same_path(path, canonical_config_path())


def _is_canonical_runtime_root(path: Path) -> bool:
    return _same_path(path, canonical_runtime_root())


def _validate_canonical_runtime_hierarchy() -> None:
    """Reject symlink redirection before trusting the ignored local hierarchy."""

    runtime_root = canonical_runtime_root()
    runtime_parent = runtime_root.parent
    for candidate in (runtime_parent, runtime_root):
        if candidate.exists() or candidate.is_symlink():
            if candidate.is_symlink():
                raise DemoError(f"canonical runtime hierarchy must not contain symlinks: {candidate}")


def _validate_private_location(path: Path, *, label: str, canonical: bool) -> None:
    """Allow the exact canonical ignored path or preserve external-config safety."""

    if canonical:
        _validate_canonical_runtime_hierarchy()
        return
    _outside_worktrees(path, label=label)


def resolve_config_path(raw_path: str | None) -> Path:
    """Resolve an explicit config or the single documented local default."""

    if raw_path:
        return Path(raw_path).expanduser()
    path = canonical_config_path()
    if not path.is_file() or path.is_symlink():
        raise DemoError(
            "Canonical Demo config not initialized. "
            f"Run: ./scripts/demo init-config. Expected path: {path}"
        )
    return path


def _template_path(profile: str) -> Path:
    if profile == PROFILE_PRODUCTION:
        return PRODUCTION_TEMPLATE_PATH
    if profile == PROFILE_NEWCOMER_MOCK:
        return NEWCOMER_MOCK_TEMPLATE_PATH
    raise DemoError("DEMO_PROFILE must be production or newcomer_mock")


def _write_private_config(path: Path, content: str, *, force: bool) -> None:
    """Write one owner-only env file without following a destination symlink."""

    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise DemoError("canonical config path must be a regular file")
        if not force:
            return
    descriptor, temporary_name = tempfile.mkstemp(prefix=".demo.env.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def initialize_canonical_config(*, profile: str, force: bool = False) -> dict[str, Any]:
    """Create or validate the documented ignored config and private runtime layout."""

    _validate_canonical_runtime_hierarchy()
    _mkdir_private(canonical_runtime_root().parent)
    _mkdir_private(canonical_runtime_root())
    config_path = canonical_config_path()
    existed = config_path.exists()
    if not existed or force:
        template = _template_path(profile)
        if not template.is_file():
            raise DemoError(f"canonical Demo config template is missing: {template.name}")
        content = template.read_text(encoding="utf-8").replace(
            "<CANONICAL_RUNTIME_ROOT>", str(canonical_runtime_root())
        )
        if "<CANONICAL_RUNTIME_ROOT>" in content:
            raise DemoError("canonical Demo config template has unresolved runtime placeholders")
        _write_private_config(config_path, content, force=force)
    config = load_config(config_path)
    ensure_runtime_layout(config)
    return {
        "state": "DEMO_CONFIG_INITIALIZED" if not existed or force else "DEMO_CONFIG_READY",
        "config_path": str(config.config_path),
        "runtime_root": str(config.runtime_root),
        "profile": config.profile,
        "created": not existed,
        "manual_secret_keys": [],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise DemoError(f"invalid private env line in {path.name}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            raise DemoError(f"invalid private env key: {key!r}")
        values[key] = value.strip().strip('"').strip("'")
    return values


def _git(*args: str, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if completed.returncode:
        raise DemoError(completed.stderr.strip() or "git command failed")
    # Preserve porcelain status columns: the first record may intentionally
    # begin with a space when only the worktree (not the index) is modified.
    return completed.stdout.rstrip()


def _worktrees() -> list[Path]:
    output = _git("worktree", "list", "--porcelain")
    roots = [ROOT.resolve()]
    for line in output.splitlines():
        if line.startswith("worktree "):
            candidate = Path(line.removeprefix("worktree ")).resolve()
            if candidate not in roots:
                roots.append(candidate)
    return roots


def _under(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _outside_worktrees(path: Path, *, label: str) -> None:
    resolved = path.resolve()
    for worktree in _worktrees():
        if _under(worktree, resolved):
            raise DemoError(f"{label} must be outside every Git worktree: {resolved}")


def _require(values: dict[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise DemoError(f"private env is missing {name}")
    return value


def _config_truthy(values: dict[str, str], name: str, fallback: bool) -> bool:
    """Read an explicit private flag, retaining a legacy fallback only when absent."""
    return _truthy(values[name]) if name in values else fallback


def _validate_discord_credential_file(raw_path: str) -> Path:
    """Validate the private Bridge credential without exposing its path or content."""
    path = Path(raw_path).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise DemoError("Discord credential file must be an absolute regular file")
    _outside_worktrees(path, label="Discord credential file")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.geteuid():
        raise DemoError("Discord credential file must be lifecycle-user-owned with mode 0600")
    values = _read_env(path)
    _require(values, "DISCORD_WEBHOOK_URL")
    return path.resolve()


def _ownership(values: dict[str, str], name: str, *, default: str) -> str:
    """Return one explicit ownership mode without guessing from a live PID."""
    value = values.get(name, default).strip().lower()
    if value not in {"managed", "external", "disabled"}:
        raise DemoError(f"{name} must be managed, external, or disabled")
    return value


def _port(values: dict[str, str], name: str, *, default: int) -> int:
    """Read one TCP port without accepting a partially parsed value."""
    try:
        value = int(values.get(name, str(default)))
    except ValueError as exc:
        raise DemoError(f"{name} must be an integer") from exc
    if not 1 <= value <= 65535:
        raise DemoError(f"{name} is outside the TCP port range")
    return value


@dataclass(frozen=True)
class DemoConfig:
    """Validated private configuration and derived paths for one Demo lifecycle."""

    config_path: Path
    runtime_root: Path
    values: dict[str, str]
    profile: str
    branch_policy: str
    expected_git_branch: str | None
    mqtt_host: str
    mqtt_port: int
    robot_id: str
    bridge_log_dir: Path
    memory_dir: Path
    shared_root: Path
    callback_socket: Path
    identity_callback_socket: Path | None
    care_callback_socket: Path | None
    identity_state_dir: Path | None
    operator_identity_enabled: bool
    identity_tool_enabled: bool
    identity_fast_path_enabled: bool
    care_memory_v2_enabled: bool
    repeated_discomfort_enabled: bool
    viewer_enabled: bool
    timeout_seconds: int
    context_length: int
    lmstudio_context_length: int
    lmstudio_visible_gpus: str
    lmstudio_ownership: str
    lmstudio_model_id: str
    lmstudio_api_identifier: str
    lmstudio_target_dir: Path
    lmstudio_server_port: int
    adapter_vision_port: int
    adapter_frame_broadcast_port: int
    resident_http_port: int
    viewer_http_port: int
    viewer_aux_port: int
    mqtt_ownership: str
    mqtt_config_path: Path | None
    gateway_ownership: str
    gateway_enabled: bool
    manage_android: bool
    mock_android_health_port: int | None
    mock_discord_port: int | None
    notification_mode: str
    discord_env_path: Path | None
    discord_test_mode: bool
    demo_notification_mock_enabled: bool
    demo_notification_mock_receipt_enabled: bool
    test_force_health_failure_service: str | None

    @property
    def is_newcomer_mock(self) -> bool:
        """Return whether this resolved config uses only newcomer test doubles."""
        return self.profile == PROFILE_NEWCOMER_MOCK

    @property
    def lmstudio_models_url(self) -> str:
        """Return the configured OpenAI-compatible model-list endpoint."""
        return f"http://127.0.0.1:{self.lmstudio_server_port}/v1/models"

    @property
    def resident_health_url(self) -> str:
        """Return the health URL derived from the resident port."""
        return f"http://127.0.0.1:{self.resident_http_port}/health"

    @property
    def resident_invoke_url(self) -> str:
        """Return the Bridge HTTP client URL derived from the resident port."""
        return f"http://127.0.0.1:{self.resident_http_port}/invoke"

    @property
    def viewer_health_url(self) -> str:
        """Return the viewer health URL derived from the viewer port."""
        return f"http://127.0.0.1:{self.viewer_http_port}/health"

    @property
    def mock_android_health_url(self) -> str | None:
        """Return the managed test Android health URL when the profile owns it."""
        if self.mock_android_health_port is None:
            return None
        return f"http://127.0.0.1:{self.mock_android_health_port}/health"

    @property
    def mock_discord_url(self) -> str | None:
        """Return the local test-only Discord endpoint when configured."""
        if self.mock_discord_port is None:
            return None
        return f"http://127.0.0.1:{self.mock_discord_port}/webhook"

    @property
    def adapter_ports(self) -> tuple[int, int]:
        """Return the two Overview adapter listeners in contract order."""
        return (self.adapter_vision_port, self.adapter_frame_broadcast_port)

    @property
    def lifecycle_ports(self) -> tuple[int, ...]:
        """Return every listener owned or inspected by this resolved lifecycle."""
        ports = [
            self.lmstudio_server_port,
            self.mqtt_port,
            *self.adapter_ports,
            self.resident_http_port,
            self.viewer_http_port,
            self.viewer_aux_port,
        ]
        if self.mock_android_health_port is not None:
            ports.append(self.mock_android_health_port)
        if self.mock_discord_port is not None:
            ports.append(self.mock_discord_port)
        return tuple(ports)

    @property
    def state_path(self) -> Path:
        return self.runtime_root / "state" / "ownership" / "current.json"

    @property
    def last_run_path(self) -> Path:
        return self.runtime_root / "state" / "last-run" / "last-run.json"

    @property
    def lock_path(self) -> Path:
        return self.runtime_root / "state" / "ownership" / "lifecycle.lock"

    @property
    def flags(self) -> dict[str, str]:
        keys = (
            *MEDIA_FLAGS,
            "DEMO_CARE_SCENARIO_PROMPT_ENABLED",
            "DEMO_RESIDENT_VISUAL_ROUTING_ENABLED",
            "DEMO_OPERATOR_IDENTITY_ENABLED",
            "RESIDENT_IDENTITY_ENABLED",
            "HERMES_DEMO_IDENTITY_TOOL_ENABLED",
            "HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED",
            "CARE_MEMORY_V2_ENABLED",
            "DEMO_REPEATED_DISCOMFORT_ENABLED",
            "CARE_CONTEXT_ENABLED",
            "ABNORMAL_CARE_EPISODE_ENABLED",
            "ABNORMAL_NOTIFICATION_MODE",
            "DEMO_NOTIFICATION_MOCK_ENABLED",
            "DEMO_NOTIFICATION_RECEIPT_ENABLED",
            "DEMO_TEST_EVENT_INGRESS_ENABLED",
        )
        return {key: self.values.get(key, "") for key in keys}

    @property
    def callback_sockets(self) -> tuple[Path, ...]:
        sockets = [self.callback_socket]
        if self.identity_callback_socket is not None:
            sockets.append(self.identity_callback_socket)
        if self.care_callback_socket is not None:
            sockets.append(self.care_callback_socket)
        return tuple(sockets)


def load_config(raw_path: str | Path) -> DemoConfig:
    """Validate a private env file and derive the fail-closed Demo configuration."""

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise DemoError("--config must be an absolute private env path")
    if path.is_symlink() or not path.is_file():
        raise DemoError("--config must be a regular private env file")
    is_canonical_config = _is_canonical_config_path(path)
    _validate_private_location(path, label="private env", canonical=is_canonical_config)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600:
        raise DemoError(f"private env mode must be 0600, got {mode:03o}")
    if path.stat().st_uid != os.geteuid():
        raise DemoError("private env must be owned by the lifecycle user")
    values = _read_env(path)
    profile = values.get("DEMO_PROFILE", PROFILE_PRODUCTION).strip().lower()
    if profile not in {PROFILE_PRODUCTION, PROFILE_NEWCOMER_MOCK}:
        raise DemoError("DEMO_PROFILE must be production or newcomer_mock")
    branch_policy = values.get("DEMO_GIT_BRANCH_POLICY", BRANCH_POLICY_REQUIRED).strip().lower()
    if branch_policy not in {BRANCH_POLICY_REQUIRED, BRANCH_POLICY_DISABLED}:
        raise DemoError("DEMO_GIT_BRANCH_POLICY must be required or disabled")
    expected_git_branch = values.get("EXPECTED_GIT_BRANCH", "main").strip()
    if branch_policy == BRANCH_POLICY_REQUIRED and not expected_git_branch:
        raise DemoError("EXPECTED_GIT_BRANCH is required when branch validation is enabled")
    if branch_policy == BRANCH_POLICY_DISABLED:
        expected_git_branch = None
    runtime_root = Path(_require(values, "TEMIAGENT_RUNTIME_ROOT"))
    if not runtime_root.is_absolute():
        raise DemoError("TEMIAGENT_RUNTIME_ROOT must be absolute")
    is_canonical_runtime = _is_canonical_runtime_root(runtime_root)
    if is_canonical_config and not is_canonical_runtime:
        raise DemoError("canonical Demo config must use the canonical runtime root")
    _validate_private_location(
        runtime_root, label="runtime root", canonical=is_canonical_runtime
    )
    port_defaults = PRODUCTION_PORTS if profile == PROFILE_PRODUCTION else NEWCOMER_MOCK_PORTS
    lmstudio_server_port = _port(values, "LMSTUDIO_SERVER_PORT", default=port_defaults["lmstudio"])
    mqtt_port = _port(values, "MQTT_BROKER_PORT", default=port_defaults["mqtt"])
    adapter_vision_port = _port(values, "ADAPTER_VISION_PORT", default=port_defaults["adapter_vision"])
    adapter_frame_broadcast_port = _port(
        values, "ADAPTER_FRAME_BROADCAST_PORT", default=port_defaults["adapter_frame"]
    )
    resident_http_port = _port(values, "RESIDENT_HTTP_PORT", default=port_defaults["resident"])
    viewer_http_port = _port(values, "VIEWER_HTTP_PORT", default=port_defaults["viewer"])
    viewer_aux_port = _port(values, "VIEWER_AUX_PORT", default=port_defaults["viewer_aux"])
    mock_android_health_port = (
        _port(values, "MOCK_ANDROID_HEALTH_PORT", default=NEWCOMER_MOCK_PORTS["mock_android"])
        if profile == PROFILE_NEWCOMER_MOCK
        else None
    )
    mock_discord_port = (
        _port(values, "MOCK_DISCORD_PORT", default=NEWCOMER_MOCK_PORTS["mock_discord"])
        if profile == PROFILE_NEWCOMER_MOCK
        else None
    )
    configured_ports = {
        "LMSTUDIO_SERVER_PORT": lmstudio_server_port,
        "MQTT_BROKER_PORT": mqtt_port,
        "ADAPTER_VISION_PORT": adapter_vision_port,
        "ADAPTER_FRAME_BROADCAST_PORT": adapter_frame_broadcast_port,
        "RESIDENT_HTTP_PORT": resident_http_port,
        "VIEWER_HTTP_PORT": viewer_http_port,
        "VIEWER_AUX_PORT": viewer_aux_port,
    }
    if profile == PROFILE_PRODUCTION:
        expected_ports = {
            "LMSTUDIO_SERVER_PORT": PRODUCTION_PORTS["lmstudio"],
            "MQTT_BROKER_PORT": PRODUCTION_PORTS["mqtt"],
            "ADAPTER_VISION_PORT": PRODUCTION_PORTS["adapter_vision"],
            "ADAPTER_FRAME_BROADCAST_PORT": PRODUCTION_PORTS["adapter_frame"],
            "RESIDENT_HTTP_PORT": PRODUCTION_PORTS["resident"],
            "VIEWER_HTTP_PORT": PRODUCTION_PORTS["viewer"],
            "VIEWER_AUX_PORT": PRODUCTION_PORTS["viewer_aux"],
        }
        for name, expected in expected_ports.items():
            if configured_ports[name] != expected:
                raise DemoError(f"{name} must be {expected} for the production Demo profile")
    else:
        configured_ports["MOCK_ANDROID_HEALTH_PORT"] = mock_android_health_port
        configured_ports["MOCK_DISCORD_PORT"] = mock_discord_port
        if any(port < 20_000 for port in configured_ports.values()):
            raise DemoError("newcomer_mock ports must be isolated high ports (>=20000)")
        if len(set(configured_ports.values())) != len(configured_ports):
            raise DemoError("newcomer_mock listener ports must be unique")
    try:
        context_length = int(values.get("CONTEXT_LENGTH", str(CANONICAL_CONTEXT_LENGTH)))
        lmstudio_context_length = int(values.get("LMSTUDIO_CONTEXT_LENGTH", str(context_length)))
    except ValueError as exc:
        raise DemoError("CONTEXT_LENGTH and LMSTUDIO_CONTEXT_LENGTH must be integers") from exc
    if context_length != CANONICAL_CONTEXT_LENGTH:
        raise DemoError(f"CONTEXT_LENGTH must be {CANONICAL_CONTEXT_LENGTH}")
    if lmstudio_context_length != context_length:
        raise DemoError("LMSTUDIO_CONTEXT_LENGTH must match CONTEXT_LENGTH")
    lmstudio_visible_gpus = values.get(
        "LMSTUDIO_VISIBLE_GPUS", CANONICAL_LMSTUDIO_VISIBLE_GPUS
    ).strip()
    if lmstudio_visible_gpus != CANONICAL_LMSTUDIO_VISIBLE_GPUS:
        raise DemoError(f"LMSTUDIO_VISIBLE_GPUS must be {CANONICAL_LMSTUDIO_VISIBLE_GPUS}")
    lmstudio_ownership = _ownership(values, "LMSTUDIO_OWNERSHIP", default="external")
    mqtt_ownership = _ownership(values, "MQTT_OWNERSHIP", default="external")
    gateway_enabled = _truthy(values.get("HERMES_GATEWAY_ENABLED", "false"))
    gateway_ownership = _ownership(
        values,
        "HERMES_GATEWAY_OWNERSHIP",
        default="managed" if gateway_enabled else "disabled",
    )
    if gateway_enabled != (gateway_ownership != "disabled"):
        raise DemoError("HERMES_GATEWAY_ENABLED must agree with HERMES_GATEWAY_OWNERSHIP")
    lmstudio_model_id = values.get("LMSTUDIO_MODEL_ID", CANONICAL_LMSTUDIO_MODEL).strip()
    lmstudio_api_identifier = values.get(
        "LMSTUDIO_API_IDENTIFIER", CANONICAL_LMSTUDIO_IDENTIFIER
    ).strip()
    if lmstudio_model_id != CANONICAL_LMSTUDIO_MODEL:
        raise DemoError(f"LMSTUDIO_MODEL_ID must be {CANONICAL_LMSTUDIO_MODEL}")
    if lmstudio_api_identifier != CANONICAL_LMSTUDIO_IDENTIFIER:
        raise DemoError(f"LMSTUDIO_API_IDENTIFIER must be {CANONICAL_LMSTUDIO_IDENTIFIER}")
    lmstudio_target_dir = Path(
        values.get(
            "LMSTUDIO_TARGET_DIR",
            str(ROOT / ".lmstudio-data") if profile == PROFILE_PRODUCTION else str(runtime_root / "data" / "mock-lmstudio"),
        )
    )
    if not lmstudio_target_dir.is_absolute():
        raise DemoError("LMSTUDIO_TARGET_DIR must be absolute")
    mqtt_config_path = None
    if mqtt_ownership == "managed":
        if profile == PROFILE_NEWCOMER_MOCK:
            mqtt_config_path = runtime_root / "config" / "mosquitto.conf"
            supplied_path = values.get("MQTT_CONFIG_PATH", "").strip()
            if supplied_path and Path(supplied_path) != mqtt_config_path:
                raise DemoError("newcomer_mock MQTT_CONFIG_PATH must be its derived runtime config path")
        else:
            mqtt_config_path = Path(_require(values, "MQTT_CONFIG_PATH"))
            if not mqtt_config_path.is_absolute() or not mqtt_config_path.is_file():
                raise DemoError("MQTT_CONFIG_PATH must be an existing absolute file for managed MQTT")
    robot_id = _require(values, "ROBOT_ID_ALLOWLIST").split(",", 1)[0].strip()
    if not robot_id:
        raise DemoError("ROBOT_ID_ALLOWLIST has no primary robot id")
    bridge_log_dir = Path(_require(values, "LOG_DIR"))
    memory_dir = Path(_require(values, "MEMORY_DIR"))
    shared_root = Path(_require(values, "TEMI_SHARED_BRIDGE_PATH"))
    hermes_shared_root = Path(_require(values, "TEMI_SHARED_HERMES_PATH"))
    callback_socket = Path(_require(values, "HERMES_MEDIA_CALLBACK_SOCKET"))
    legacy_operator_identity_enabled = _truthy(values.get("DEMO_OPERATOR_IDENTITY_ENABLED", "false"))
    operator_identity_enabled = _config_truthy(
        values, "RESIDENT_IDENTITY_ENABLED", legacy_operator_identity_enabled
    )
    identity_tool_enabled = _config_truthy(
        values, "HERMES_DEMO_IDENTITY_TOOL_ENABLED", legacy_operator_identity_enabled
    )
    identity_fast_path_enabled = _config_truthy(
        values, "HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED", legacy_operator_identity_enabled
    )
    care_memory_v2_enabled = _truthy(values.get("CARE_MEMORY_V2_ENABLED", "false"))
    repeated_discomfort_enabled = _truthy(values.get("DEMO_REPEATED_DISCOMFORT_ENABLED", "false"))
    if operator_identity_enabled and not identity_tool_enabled:
        raise DemoError("RESIDENT_IDENTITY_ENABLED=true requires HERMES_DEMO_IDENTITY_TOOL_ENABLED=true")
    if repeated_discomfort_enabled and not operator_identity_enabled:
        raise DemoError("DEMO_REPEATED_DISCOMFORT_ENABLED requires RESIDENT_IDENTITY_ENABLED=true")
    if repeated_discomfort_enabled and not care_memory_v2_enabled:
        raise DemoError("DEMO_REPEATED_DISCOMFORT_ENABLED requires CARE_MEMORY_V2_ENABLED=true")
    identity_callback_socket = Path(_require(values, "HERMES_DEMO_IDENTITY_CALLBACK_SOCKET")) if operator_identity_enabled else None
    care_callback_socket = Path(_require(values, "HERMES_DEMO_CARE_CALLBACK_SOCKET")) if repeated_discomfort_enabled else None
    identity_state_dir = Path(_require(values, "DEMO_IDENTITY_STATE_DIR")) if operator_identity_enabled else None
    demo_care_memory_root = Path(_require(values, "DEMO_CARE_MEMORY_ROOT")) if repeated_discomfort_enabled else None
    candidates = [
        ("LOG_DIR", bridge_log_dir),
        ("MEMORY_DIR", memory_dir),
        ("TEMI_SHARED_BRIDGE_PATH", shared_root),
        ("TEMI_SHARED_HERMES_PATH", hermes_shared_root),
        ("HERMES_MEDIA_CALLBACK_SOCKET", callback_socket),
    ]
    if identity_callback_socket is not None:
        candidates.append(("HERMES_DEMO_IDENTITY_CALLBACK_SOCKET", identity_callback_socket))
    if care_callback_socket is not None:
        candidates.append(("HERMES_DEMO_CARE_CALLBACK_SOCKET", care_callback_socket))
    if identity_state_dir is not None:
        candidates.append(("DEMO_IDENTITY_STATE_DIR", identity_state_dir))
    if demo_care_memory_root is not None:
        candidates.append(("DEMO_CARE_MEMORY_ROOT", demo_care_memory_root))
    for label, candidate in candidates:
        if not candidate.is_absolute() or not _under(runtime_root, candidate):
            raise DemoError(f"{label} must be an absolute path under TEMIAGENT_RUNTIME_ROOT")
    if shared_root.resolve() != hermes_shared_root.resolve():
        raise DemoError("the current single-container Demo requires matching Bridge/Hermes shared roots")
    if _require(values, "HERMES_INVOKE_MODE").strip().lower() != "http":
        raise DemoError("HERMES_INVOKE_MODE must be http for the resident Demo route")
    resident_invoke_url = f"http://127.0.0.1:{resident_http_port}/invoke"
    if _require(values, "HERMES_HTTP_URL") != resident_invoke_url:
        raise DemoError("HERMES_HTTP_URL must be derived from RESIDENT_HTTP_PORT")
    for flag in MEDIA_FLAGS:
        if not _truthy(_require(values, flag)):
            raise DemoError(f"{flag} must be true for this Media Demo")
    viewer_enabled = _truthy(values.get("DEMO_ACTION_VIEWER_ENABLED", "false"))
    viewer_discord_enabled = values.get("DEMO_ACTION_VIEWER_DISCORD_NOTIFY", "disabled").strip().lower() == "enabled"
    if viewer_discord_enabled:
        raise DemoError("DEMO_ACTION_VIEWER_DISCORD_NOTIFY is retired; the Bridge owns abnormal notification delivery")
    notification_mode = values.get("ABNORMAL_NOTIFICATION_MODE", "disabled").strip().lower()
    if notification_mode not in {"disabled", "discord_webhook", "demo_mock"}:
        raise DemoError("ABNORMAL_NOTIFICATION_MODE must be disabled, discord_webhook, or demo_mock")
    discord_env_path = None
    if notification_mode == "discord_webhook":
        discord_env_path = _validate_discord_credential_file(
            _require(values, "ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH")
        )
    discord_test_mode = _truthy(values.get("ABNORMAL_NOTIFICATION_TEST_RECIPIENT_AUTHORIZED", "false"))
    demo_notification_mock_enabled = _truthy(values.get("DEMO_NOTIFICATION_MOCK_ENABLED", "false"))
    demo_notification_receipt_enabled = _truthy(values.get("DEMO_NOTIFICATION_RECEIPT_ENABLED", "false"))
    if notification_mode == "demo_mock" and not (
        demo_notification_mock_enabled and demo_notification_receipt_enabled
    ):
        raise DemoError("ABNORMAL_NOTIFICATION_MODE=demo_mock requires both Demo notification mock flags")
    if demo_notification_mock_enabled and notification_mode != "demo_mock":
        raise DemoError("DEMO_NOTIFICATION_MOCK_ENABLED=true requires ABNORMAL_NOTIFICATION_MODE=demo_mock")
    if demo_notification_receipt_enabled and not demo_notification_mock_enabled:
        raise DemoError("DEMO_NOTIFICATION_RECEIPT_ENABLED=true requires DEMO_NOTIFICATION_MOCK_ENABLED=true")
    if notification_mode == "discord_webhook" and demo_notification_mock_enabled:
        raise DemoError("real Discord and Demo mock notification routes cannot be enabled together")
    if viewer_enabled and profile == PROFILE_PRODUCTION:
        for name in (
            "DEMO_ACTION_VIEWER_MODEL",
            "DEMO_ACTION_VIEWER_GGUF_MODEL_PATH",
            "DEMO_ACTION_VIEWER_MMPROJ_PATH",
            "DEMO_ACTION_VIEWER_LLAMA_SERVER",
        ):
            _require(values, name)
    if profile == PROFILE_NEWCOMER_MOCK:
        if lmstudio_ownership != "managed" or mqtt_ownership != "managed":
            raise DemoError("newcomer_mock must lifecycle-manage its LM and MQTT test doubles")
        if _require(values, "MQTT_BROKER_HOST") != "127.0.0.1":
            raise DemoError("newcomer_mock MQTT_BROKER_HOST must be loopback")
        if gateway_enabled or gateway_ownership != "disabled":
            raise DemoError("newcomer_mock must explicitly disable the Hermes gateway")
        if not viewer_enabled:
            raise DemoError("newcomer_mock requires DEMO_ACTION_VIEWER_ENABLED=true")
        if notification_mode == "discord_webhook":
            raise DemoError("newcomer_mock does not permit a real Discord credential route")
    test_force_health_failure_service = values.get("DEMO_TEST_FORCE_HEALTH_FAILURE_SERVICE", "").strip()
    if test_force_health_failure_service:
        if profile != PROFILE_NEWCOMER_MOCK or test_force_health_failure_service != "viewer":
            raise DemoError("DEMO_TEST_FORCE_HEALTH_FAILURE_SERVICE is limited to newcomer_mock viewer")
    manage_android = _truthy(values.get("MANAGE_ANDROID", "false"))
    if manage_android:
        raise DemoError("MANAGE_ANDROID=true is not supported by the canonical software-only lifecycle")
    try:
        timeout_seconds = int(values.get("DEMO_START_TIMEOUT_SECONDS", "180"))
    except ValueError as exc:
        raise DemoError("DEMO_START_TIMEOUT_SECONDS must be an integer") from exc
    if not 10 <= timeout_seconds <= 600:
        raise DemoError("DEMO_START_TIMEOUT_SECONDS must be between 10 and 600")
    return DemoConfig(
        config_path=path.resolve(),
        runtime_root=runtime_root.resolve(),
        values=values,
        profile=profile,
        branch_policy=branch_policy,
        expected_git_branch=expected_git_branch,
        mqtt_host=_require(values, "MQTT_BROKER_HOST"),
        mqtt_port=mqtt_port,
        robot_id=robot_id,
        bridge_log_dir=bridge_log_dir.resolve(),
        memory_dir=memory_dir.resolve(),
        shared_root=shared_root.resolve(),
        callback_socket=callback_socket.resolve(),
        identity_callback_socket=identity_callback_socket.resolve() if identity_callback_socket is not None else None,
        care_callback_socket=care_callback_socket.resolve() if care_callback_socket is not None else None,
        identity_state_dir=identity_state_dir.resolve() if identity_state_dir is not None else None,
        operator_identity_enabled=operator_identity_enabled,
        identity_tool_enabled=identity_tool_enabled,
        identity_fast_path_enabled=identity_fast_path_enabled,
        care_memory_v2_enabled=care_memory_v2_enabled,
        repeated_discomfort_enabled=repeated_discomfort_enabled,
        viewer_enabled=viewer_enabled,
        timeout_seconds=timeout_seconds,
        context_length=context_length,
        lmstudio_context_length=lmstudio_context_length,
        lmstudio_visible_gpus=lmstudio_visible_gpus,
        lmstudio_ownership=lmstudio_ownership,
        lmstudio_model_id=lmstudio_model_id,
        lmstudio_api_identifier=lmstudio_api_identifier,
        lmstudio_target_dir=lmstudio_target_dir.resolve(),
        lmstudio_server_port=lmstudio_server_port,
        adapter_vision_port=adapter_vision_port,
        adapter_frame_broadcast_port=adapter_frame_broadcast_port,
        resident_http_port=resident_http_port,
        viewer_http_port=viewer_http_port,
        viewer_aux_port=viewer_aux_port,
        mqtt_ownership=mqtt_ownership,
        mqtt_config_path=mqtt_config_path.resolve() if mqtt_config_path is not None else None,
        gateway_ownership=gateway_ownership,
        gateway_enabled=gateway_enabled,
        manage_android=manage_android,
        mock_android_health_port=mock_android_health_port,
        mock_discord_port=mock_discord_port,
        notification_mode=notification_mode,
        discord_env_path=discord_env_path,
        discord_test_mode=discord_test_mode,
        demo_notification_mock_enabled=demo_notification_mock_enabled,
        demo_notification_mock_receipt_enabled=demo_notification_receipt_enabled,
        test_force_health_failure_service=test_force_health_failure_service or None,
    )


def _mkdir_private(path: Path) -> None:
    if path.is_symlink():
        raise DemoError(f"owner-only runtime path must not be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise DemoError(f"owner-only runtime path must be a directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise DemoError(f"owner-only runtime path must be lifecycle-user-owned: {path}")
    os.chmod(path, 0o700)


def _has_writable_existing_parent(path: Path) -> bool:
    """Check the nearest existing parent without making doctor mutate runtime state."""
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def ensure_runtime_layout(config: DemoConfig) -> None:
    """Create only the owner-only external runtime directories required by a mutation."""

    _mkdir_private(config.runtime_root)
    for path in (
        config.runtime_root / "config",
        config.runtime_root / "state" / "pid",
        config.runtime_root / "state" / "ownership",
        config.runtime_root / "state" / "last-run",
        config.runtime_root / "state" / "android-evidence",
        config.runtime_root / "state" / "viewer",
        config.runtime_root / "state" / "notifications",
        config.runtime_root / "state" / "media",
        config.runtime_root / "data" / "care-memory",
        config.runtime_root / "data" / "test-memory",
        config.runtime_root / "data" / "shared",
        config.runtime_root / "logs" / "bridge",
        config.runtime_root / "logs" / "hermes",
        config.runtime_root / "logs" / "asr",
        config.runtime_root / "logs" / "trace",
        config.runtime_root / "logs" / "lmstudio",
        config.runtime_root / "logs" / "mqtt",
        config.runtime_root / "logs" / "gateway",
        config.runtime_root / "tmp" / "sockets",
        *( (config.identity_state_dir,) if config.identity_state_dir is not None else () ),
    ):
        _mkdir_private(path)
    config_parent_metadata = config.config_path.parent.stat()
    if config_parent_metadata.st_uid != os.geteuid() or (
        stat.S_IMODE(config_parent_metadata.st_mode) & (stat.S_IRWXG | stat.S_IRWXO)
    ):
        raise DemoError("private config parent directory must be owner-only")
    if config.is_newcomer_mock:
        _write_mock_mosquitto_config(config)


def _write_mock_mosquitto_config(config: DemoConfig) -> None:
    """Create the profile-derived, private broker config only during mutation."""
    if not config.is_newcomer_mock or config.mqtt_config_path is None:
        return
    content = (
        f"listener {config.mqtt_port} 127.0.0.1\n"
        "allow_anonymous true\n"
        "persistence false\n"
        "log_dest stdout\n"
    )
    descriptor = os.open(
        config.mqtt_config_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, content.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(config.mqtt_config_path, 0o600)


def _atomic_json(path: Path, payload: object) -> None:
    _mkdir_private(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def _reset_ephemeral_demo_identity(config: DemoConfig) -> bool:
    """Reset the lifecycle-owned Demo identity without deleting its state file."""
    state_dir = config.identity_state_dir
    if state_dir is None:
        return False
    if state_dir.is_symlink() or (state_dir.exists() and not state_dir.is_dir()):
        raise DemoError("Demo identity state directory must be a regular directory")
    current_path = state_dir / "current.json"
    if current_path.is_symlink() or (current_path.exists() and not current_path.is_file()):
        raise DemoError("Demo identity state must be a regular file")
    _atomic_json(
        current_path,
        {
            "schema_version": "temiagent.demo_identity.v1",
            "robot_id": config.robot_id,
            "identity_status": "unknown",
            "process_scoped": True,
            "lifecycle_reset": True,
            "updated_at": _utc_now(),
        },
    )
    return True


@contextmanager
def _lifecycle_lock(config: DemoConfig) -> Iterable[None]:
    """Serialize mutating lifecycle commands with an owner-only advisory lock."""
    _mkdir_private(config.lock_path.parent)
    descriptor = os.open(config.lock_path, os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DemoError("LOCK_BUSY: another lifecycle operation is active") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DemoError(f"invalid lifecycle state: {path}") from exc
    if not isinstance(parsed, dict):
        raise DemoError(f"invalid lifecycle state object: {path}")
    return parsed


def _identity(pid: int) -> dict[str, Any]:
    proc = Path("/proc") / str(pid)
    stat_text = (proc / "stat").read_text(encoding="utf-8")
    end = stat_text.rfind(")")
    fields = stat_text[end + 2 :].split()
    if end < 0 or len(fields) < 20:
        raise DemoError(f"PID {pid} has an invalid /proc stat record")
    raw_cmdline = (proc / "cmdline").read_bytes()
    argv = [part.decode("utf-8", "replace") for part in raw_cmdline.split(b"\0") if part]
    if not argv:
        raise DemoError(f"PID {pid} has an empty command line")
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "start_ticks": int(fields[19]),
        "cwd": os.path.realpath(proc / "cwd"),
        "executable": os.path.realpath(proc / "exe"),
        "cmdline": argv,
        "cmdline_sha256": hashlib.sha256(raw_cmdline).hexdigest(),
    }


def _identity_matches(record: dict[str, Any]) -> bool:
    try:
        current = _identity(int(record["pid"]))
    except (FileNotFoundError, PermissionError, ProcessLookupError, DemoError, ValueError):
        return False
    return all(current.get(key) == record.get(key) for key in ("pid", "start_ticks", "cwd", "executable", "cmdline_sha256"))


def _listener_pids(port: int) -> set[int]:
    completed = subprocess.run(
        ["ss", "-H", "-ltnp", f"sport = :{port}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        cursor = 0
        while True:
            marker = line.find("pid=", cursor)
            if marker < 0:
                break
            candidate = line[marker + 4 :].split(",", 1)[0]
            if candidate.isdigit():
                pids.add(int(candidate))
            cursor = marker + 4
    return pids


def _listener_count(port: int) -> int:
    completed = subprocess.run(
        ["ss", "-H", "-ltn", f"sport = :{port}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    if completed.returncode:
        raise DemoError(f"could not inspect port {port}")
    return len([line for line in completed.stdout.splitlines() if line.strip()])


def _listener_identities(port: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pid in sorted(_listener_pids(port)):
        try:
            records.append(_identity(pid))
        except (FileNotFoundError, PermissionError, ProcessLookupError, DemoError):
            continue
    return records


def _matching_identities(*, cwd: Path, token: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            identity = _identity(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError, DemoError):
            continue
        if identity["cwd"] == str(cwd.resolve()) and token in " ".join(identity["cmdline"]):
            matches.append(identity)
    return matches


def _parent_identity(identity: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _identity(int(identity["ppid"]))
    except (FileNotFoundError, PermissionError, ProcessLookupError, DemoError):
        return None


def _wait_for(predicate: Callable[[], bool], timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


def _http_json(url: str, timeout: int = 5) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _http_health(url: str, timeout: int = 5) -> tuple[dict[str, Any] | None, str, str]:
    """Fetch one health surface with a stable failure category for doctor."""
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        return None, "ENDPOINT_TIMEOUT", f"timed out calling {url}"
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return None, "ENDPOINT_TIMEOUT", f"timed out calling {url}"
        return None, "ENDPOINT_UNAVAILABLE", f"endpoint unavailable: {url}"
    except OSError:
        return None, "ENDPOINT_UNAVAILABLE", f"endpoint unavailable: {url}"
    except (ValueError, json.JSONDecodeError):
        return None, "HEALTH_MALFORMED", f"health response was not JSON: {url}"
    if not isinstance(payload, dict):
        return None, "HEALTH_MALFORMED", f"health response was not a JSON object: {url}"
    return payload, "HEALTHY", f"health endpoint responded: {url}"


def _mqtt_tcp_ready(config: DemoConfig) -> bool:
    try:
        with socket.create_connection((config.mqtt_host, config.mqtt_port), timeout=3):
            return True
    except OSError:
        return False


def _lmstudio_lms(config: DemoConfig, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    executable = config.lmstudio_target_dir / "bin" / "lms"
    if not executable.is_file():
        raise DemoError("LM Studio CLI is unavailable under LMSTUDIO_TARGET_DIR")
    return subprocess.run(
        [str(executable), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def _lmstudio_ready(config: DemoConfig) -> bool:
    payload, _, _ = _http_health(config.lmstudio_models_url)
    if payload is None:
        return False
    models = payload.get("data")
    if not isinstance(models, list):
        return False
    return any(
        isinstance(item, dict) and item.get("id") == config.lmstudio_api_identifier
        for item in models
    )


def _lmstudio_context_ready(config: DemoConfig) -> bool:
    if config.is_newcomer_mock:
        return _lmstudio_ready(config)
    try:
        completed = _lmstudio_lms(config, "ps", timeout=15)
    except (OSError, subprocess.TimeoutExpired, DemoError):
        return False
    if completed.returncode:
        return False
    return (
        config.lmstudio_api_identifier in completed.stdout
        and str(config.lmstudio_context_length) in completed.stdout
    )


def _gateway_ready(config: DemoConfig) -> bool:
    if not config.gateway_enabled:
        return True
    executable = ROOT / "hermes-agent" / "venv" / "bin" / "hermes"
    completed = subprocess.run(
        [str(executable), "gateway", "status"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    return completed.returncode == 0 and "running" in completed.stdout.lower()


def _validate_resource_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(RESOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError("required Demo resource manifest is invalid") from exc
    resources = payload.get("resources") if isinstance(payload, dict) else None
    if not isinstance(resources, list):
        raise DemoError("required Demo resource manifest has no resources list")
    indexed = {item.get("id"): item for item in resources if isinstance(item, dict)}
    media = indexed.get("elderly_hand_exercise")
    skill = indexed.get("temi_discord_care_skill")
    if not isinstance(media, dict) or media.get("required") is not True:
        raise DemoError("required media logical resource is missing")
    if not isinstance(skill, dict) or skill.get("required") is not True:
        raise DemoError("required resident skill resource is missing")
    relative_path = skill.get("relative_path")
    if not isinstance(relative_path, str) or not (ROOT / relative_path).is_file():
        raise DemoError("required resident skill resource path is missing")
    return {"resource_count": len(resources), "required_media": media["id"]}


def _broker_sessions(config: DemoConfig) -> dict[str, int]:
    completed = subprocess.run(
        ["ss", "-Htn", "state", "established", f"( sport = :{config.mqtt_port} or dport = :{config.mqtt_port} )"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    local = 0
    remote = 0
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        peer = fields[3]
        if peer.startswith("127.0.0.1:") or peer.startswith("[::1]:"):
            local += 1
        else:
            remote += 1
    return {"loopback_sessions": local, "remote_sessions": remote}


@dataclass(frozen=True)
class ServiceSpec:
    """Immutable expected identity and health surface for one lifecycle service."""

    name: str
    cwd: Path
    token: str
    ports: tuple[int, ...]
    log_path: Path


def _specs(config: DemoConfig) -> dict[str, ServiceSpec]:
    specs: dict[str, ServiceSpec] = {}
    if config.lmstudio_ownership == "managed":
        specs["lmstudio"] = ServiceSpec(
            "lmstudio",
            ROOT,
            "mock_lmstudio_server.py" if config.is_newcomer_mock else "managed_lmstudio_supervisor.py",
            (config.lmstudio_server_port,),
            config.runtime_root / "logs" / "lmstudio" / "lmstudio.log",
        )
    if config.mqtt_ownership == "managed":
        specs["mqtt"] = ServiceSpec(
            "mqtt",
            ROOT,
            "managed_mosquitto_supervisor.py",
            (config.mqtt_port,),
            config.runtime_root / "logs" / "mqtt" / "mosquitto.log",
        )
    specs.update({
        "adapter": ServiceSpec("adapter", ROOT / "temi_backend", "temi_overview_adapter.py", config.adapter_ports, config.runtime_root / "logs" / "asr" / "overview_adapter.log"),
        "resident": ServiceSpec("resident", ROOT, "mock_resident_server.py" if config.is_newcomer_mock else "tools/hermes_resident_server.py", (config.resident_http_port,), config.runtime_root / "logs" / "hermes" / "resident.log"),
        "bridge": ServiceSpec("bridge", ROOT / "hermes_temi_bridge", "hermes-temi-bridge", (), config.runtime_root / "logs" / "bridge" / "bridge.log"),
    })
    if config.gateway_ownership == "managed":
        specs["gateway"] = ServiceSpec(
            "gateway",
            ROOT,
            "gateway run",
            (),
            config.runtime_root / "logs" / "gateway" / "gateway.log",
        )
    if config.viewer_enabled:
        specs["viewer"] = ServiceSpec("viewer", ROOT if config.is_newcomer_mock else ROOT / "anomaly_detection", "mock_viewer_server.py" if config.is_newcomer_mock else "temi_action_viewer.py", (config.viewer_http_port, config.viewer_aux_port), config.runtime_root / "logs" / "trace" / "action_viewer.log")
    if config.is_newcomer_mock:
        assert config.mock_android_health_port is not None and config.mock_discord_port is not None
        specs["mock_android"] = ServiceSpec("mock_android", ROOT, "mock_android_executor.py", (config.mock_android_health_port,), config.runtime_root / "logs" / "mock" / "android.log")
        specs["mock_discord"] = ServiceSpec("mock_discord", ROOT, "mock_discord_server.py", (config.mock_discord_port,), config.runtime_root / "logs" / "mock" / "discord.log")
    return specs


def _source_record() -> dict[str, Any]:
    return {
        "root": str(ROOT),
        "branch": _git("branch", "--show-current"),
        "head": _git("rev-parse", "HEAD"),
        "tree": _git("status", "--short", "--ignore-submodules=none").splitlines(),
        "recorded_at": _utc_now(),
    }


def _write_pre_restart_evidence(config: DemoConfig) -> Path:
    previous_state = _read_json(config.state_path)
    previous_ownership = None
    if previous_state is not None:
        previous_ownership = {
            "run_id": previous_state.get("run_id"),
            "status": previous_state.get("status"),
            "services": _state_records(previous_state),
        }
    evidence = {
        "recorded_at": _utc_now(),
        "source": _source_record(),
        "owned_processes_before_stop": previous_ownership,
        "ports": {str(port): _listener_identities(port) for port in config.lifecycle_ports},
        "broker_sessions": _broker_sessions(config),
        "resident_health": _resident_health(config),
        "viewer_health": _http_json(config.viewer_health_url),
        "flags": config.flags,
        "callback_socket_exists": config.callback_socket.exists(),
        "callback_sockets": {str(path): path.exists() for path in config.callback_sockets},
    }
    path = config.runtime_root / "state" / "last-run" / f"before-restart-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    _atomic_json(path, evidence)
    return path


def _resident_health(config: DemoConfig) -> dict[str, Any] | None:
    return _http_json(config.resident_health_url)


def _resident_ready(config: DemoConfig) -> bool:
    health = _resident_health(config)
    if not (
        health
        and health.get("status") == "ok"
        and health.get("media_tool_enabled") is True
        and health.get("media_fast_path_enabled") is True
        and tuple(health.get("media_tool_names", ())) == MEDIA_TOOLS
    ):
        return False
    if config.operator_identity_enabled and not (
        health.get("demo_operator_identity_enabled") is True
        and health.get("resident_identity_enabled") is True
        and health.get("identity_tool_enabled") is True
        and health.get("identity_fast_path_enabled") is config.identity_fast_path_enabled
        and tuple(health.get("identity_tool_names", ())) == IDENTITY_TOOLS
    ):
        return False
    if config.repeated_discomfort_enabled and not (
        health.get("demo_repeated_discomfort_enabled") is True
        and health.get("care_memory_v2_enabled") is True
        and health.get("repeated_discomfort_fast_path_enabled") is True
        and tuple(health.get("repeated_discomfort_tool_names", ())) == REPEATED_DISCOMFORT_TOOLS
    ):
        return False
    return True


def _viewer_health_contract(health: dict[str, Any] | None) -> bool:
    """Require the viewer health partition without exposing notification secrets."""
    if not health or health.get("ok") is not True:
        return False
    components = health.get("components")
    if not isinstance(components, dict):
        return False
    return all(isinstance(components.get(name), dict) for name in (
        "viewer_core", "event_ingestion", "frame_state", "real_discord", "demo_notification_mock",
    ))


def _viewer_ready(config: DemoConfig) -> bool:
    health = _http_json(config.viewer_health_url)
    return bool(
        _viewer_health_contract(health)
        and health.get("source_connected") is True
        and health.get("llama_server_ready") is True
    )


def _mock_android_ready(config: DemoConfig) -> bool:
    """Verify the managed Android test double without claiming a real device."""
    if config.mock_android_health_url is None:
        return False
    health = _http_json(config.mock_android_health_url)
    return bool(health and health.get("ok") is True and health.get("test_double") == "android")


def _mock_discord_ready(config: DemoConfig) -> bool:
    """Verify the local notification test double without contacting Discord."""
    if config.mock_discord_url is None:
        return False
    health = _http_json(config.mock_discord_url.removesuffix("/webhook") + "/health")
    return bool(health and health.get("ok") is True and health.get("test_double") == "discord")


def _socket_ready(config: DemoConfig) -> bool:
    try:
        return all(stat.S_ISSOCK(path.stat().st_mode) for path in config.callback_sockets)
    except FileNotFoundError:
        return False


def _append_member(members: list[dict[str, Any]], identity: dict[str, Any]) -> None:
    if not any(existing.get("pid") == identity.get("pid") for existing in members):
        members.append(identity)


def _record_from_existing(spec: ServiceSpec) -> dict[str, Any] | None:
    if spec.ports:
        ports = {port: _listener_identities(port) for port in spec.ports}
        present = [record for records in ports.values() for record in records]
        if not present:
            return None
        if any(len(records) != 1 for records in ports.values()):
            raise DemoError(f"{spec.name} has a duplicate or incomplete listener set")
        leader = ports[spec.ports[0]][0]
        parent = _parent_identity(leader)
        if parent and parent["cwd"] == str(spec.cwd.resolve()) and spec.token in " ".join(parent["cmdline"]):
            leader = parent
        if leader["cwd"] != str(spec.cwd.resolve()) or spec.token not in " ".join(leader["cmdline"]):
            raise DemoError(f"{spec.name} listener does not match the current Demo entrypoint")
        members = [leader]
        for records in ports.values():
            _append_member(members, records[0])
    else:
        matches = _matching_identities(cwd=spec.cwd, token=spec.token)
        if not matches:
            return None
        child_pids = {candidate["ppid"] for candidate in matches}
        leaders = [candidate for candidate in matches if candidate["pid"] not in child_pids]
        if len(leaders) != 1:
            raise DemoError(f"{spec.name} has ambiguous current process ownership")
        leader = leaders[0]
        members = list(matches)
    return {
        "name": spec.name,
        "ownership": "adopted_for_explicit_restart",
        "leader": leader,
        "members": members,
        "ports": list(spec.ports),
        "log_path": str(spec.log_path),
    }


def _start_process(spec: ServiceSpec, argv: list[str], env: dict[str, str]) -> dict[str, Any]:
    _mkdir_private(spec.log_path.parent)
    descriptor = os.open(spec.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        process = subprocess.Popen(
            argv,
            cwd=spec.cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=descriptor,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        os.close(descriptor)
    os.chmod(spec.log_path, 0o600)
    time.sleep(0.1)
    if process.poll() is not None:
        raise DemoError(f"{spec.name} exited during startup; inspect {spec.log_path}")
    return {
        "name": spec.name,
        "ownership": "owned",
        "leader": _identity(process.pid),
        "members": [],
        "ports": list(spec.ports),
        "log_path": str(spec.log_path),
    }


def _command_fingerprint(argv: list[str]) -> str:
    """Return a stable fingerprint for the exact argv supplied to Popen."""
    return hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()


def _persist_starting_record(
    config: DemoConfig,
    state: dict[str, Any],
    name: str,
    record: dict[str, Any],
    argv: list[str],
) -> None:
    """Persist verified process ownership before the service health wait begins."""
    leader = record.get("leader")
    if not isinstance(leader, dict) or not _identity_matches(leader):
        raise DemoError(f"{name} failed exact-PID identity verification during startup")
    record["process_start_identity"] = dict(leader)
    record["command_fingerprint"] = _command_fingerprint(argv)
    record["supervisor"] = dict(leader) if name in {"lmstudio", "mqtt"} else None
    record["spawned_at"] = _utc_now()
    state["services"][name] = record
    state["status"] = STATE_STARTING
    state["updated_at"] = _utc_now()
    _atomic_json(config.state_path, state)


def _attach_listeners(record: dict[str, Any]) -> None:
    members = list(record.get("members", []))
    for port in record.get("ports", []):
        identities = _listener_identities(int(port))
        if len(identities) != 1:
            # Mosquitto intentionally drops privileges. The recorded root
            # supervisor remains the exact lifecycle owner and relays TERM to
            # that child; do not accept an unobservable listener otherwise.
            if (
                record["name"] == "mqtt"
                and _identity_matches(record["leader"])
                and _listener_count(int(port)) == 1
            ):
                continue
            raise DemoError(f"{record['name']} does not own exactly one listener on {port}")
        _append_member(members, identities[0])
    record["members"] = members


def _attach_descendants(record: dict[str, Any]) -> None:
    """Record direct/indirect children so a wrapper cannot leave an owned child behind."""
    leader = record.get("leader")
    if not isinstance(leader, dict):
        return
    known = {int(leader["pid"])}
    members = list(record.get("members", []))
    for member in members:
        if isinstance(member, dict) and isinstance(member.get("pid"), int):
            known.add(int(member["pid"]))
    changed = True
    while changed:
        changed = False
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                identity = _identity(int(proc.name))
            except (FileNotFoundError, PermissionError, ProcessLookupError, DemoError):
                continue
            if int(identity["ppid"]) in known and int(identity["pid"]) not in known:
                _append_member(members, identity)
                known.add(int(identity["pid"]))
                changed = True
    record["members"] = members


def _stop_record(record: dict[str, Any], *, timeout_seconds: int) -> str:
    name = str(record.get("name", "unknown"))
    identities = [record.get("leader"), *(record.get("members") or [])]
    valid: list[dict[str, Any]] = []
    for identity in identities:
        if isinstance(identity, dict) and identity.get("pid") is not None:
            if not any(item.get("pid") == identity.get("pid") for item in valid):
                valid.append(identity)
    leader = record.get("leader")
    if not isinstance(leader, dict):
        raise DemoError(f"{name} ownership record has no leader")
    if _identity_matches(leader):
        os.kill(int(leader["pid"]), signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not any(_identity_matches(identity) for identity in valid):
            break
        time.sleep(0.2)
    lingering = [identity for identity in valid if _identity_matches(identity)]
    if lingering:
        for identity in lingering:
            os.kill(int(identity["pid"]), signal.SIGTERM)
        if not _wait_for(lambda: not any(_identity_matches(identity) for identity in lingering), min(10, timeout_seconds)):
            raise DemoError(f"{name} exact PID did not stop after TERM; no KILL was sent")
    for port in record.get("ports", []):
        # A clean process exit can release a TCP listener a short time after
        # /proc no longer exposes the PID.  Wait only for that exact port;
        # never widen recovery to a name-based kill.
        if not _wait_for(lambda port=int(port): _listener_count(port) == 0, min(5, timeout_seconds)):
            raise DemoError(f"{name} listener remains on {port} after exact-PID stop")
    return "stopped_term"


def _remove_owned_callback_path(path: Path, record: dict[str, Any]) -> None:
    """Remove one verified Bridge-owned Unix callback socket after exact stop."""
    if record.get("name") != "bridge" or not path.exists():
        return
    identities = [record.get("leader"), *(record.get("members") or [])]
    if any(isinstance(identity, dict) and _identity_matches(identity) for identity in identities):
        raise DemoError("refusing to remove callback socket while a recorded Bridge PID is alive")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(mode):
        raise DemoError("refusing to remove a non-socket callback path")
    path.unlink()


def _remove_owned_callback_socket(config: DemoConfig, record: dict[str, Any]) -> None:
    """Compatibility helper for the original Media callback socket."""
    _remove_owned_callback_path(config.callback_socket, record)


def _remove_owned_callback_sockets(config: DemoConfig, record: dict[str, Any]) -> None:
    """Remove every verified private Bridge callback socket for this Demo run."""
    for path in config.callback_sockets:
        _remove_owned_callback_path(path, record)


def _viewer_notification_argv(config: DemoConfig) -> list[str]:
    """Pass the complete resolved route metadata without making viewer a sender."""
    argv = [
        "--notification-mode", config.notification_mode,
        "--discord-test-mode", "enabled" if config.discord_test_mode else "disabled",
        "--demo-notification-mock-enabled",
        "enabled" if config.demo_notification_mock_enabled else "disabled",
        "--demo-notification-mock-receipt-enabled",
        "enabled" if config.demo_notification_mock_receipt_enabled else "disabled",
    ]
    if config.discord_env_path is not None:
        argv.extend(["--discord-env-path", str(config.discord_env_path)])
    return argv


def _service_argv(config: DemoConfig, name: str) -> list[str]:
    skills = ROOT / "hermes-agent" / "skills"
    if name == "lmstudio":
        if config.is_newcomer_mock:
            return [
                sys.executable,
                str(ROOT / "tools" / "mocks" / "mock_lmstudio_server.py"),
                "--host", "127.0.0.1",
                "--port", str(config.lmstudio_server_port),
                "--model-id", config.lmstudio_api_identifier,
            ]
        return [
            sys.executable,
            str(ROOT / "tools" / "managed_lmstudio_supervisor.py"),
            "--startup-script",
            str(ROOT / "tools" / "start_lmstudio_3gpu.sh"),
            "--target-dir",
            str(config.lmstudio_target_dir),
            "--identifier",
            config.lmstudio_api_identifier,
        ]
    if name == "mqtt":
        if config.mqtt_config_path is None:
            raise DemoError("managed MQTT has no verified config path")
        return [
            sys.executable,
            str(ROOT / "tools" / "managed_mosquitto_supervisor.py"),
            "--config",
            str(config.mqtt_config_path),
        ]
    if name == "adapter":
        return [
            "uv", "run", "python", str(ROOT / "tools" / "temi_overview_adapter.py"),
            "--robot-id", config.robot_id,
            "--broker", config.mqtt_host,
            "--port", str(config.mqtt_port),
            "--vision-port", str(config.adapter_vision_port),
            "--frame-broadcast-port", str(config.adapter_frame_broadcast_port),
            "--shared-root", str(config.shared_root),
            "--bridge-root", str(config.shared_root),
            "--conversation-id", "conv_first_year_demo",
        ]
    if name == "resident":
        if config.is_newcomer_mock:
            return [
                sys.executable,
                str(ROOT / "tools" / "mocks" / "mock_resident_server.py"),
                "--host", "127.0.0.1",
                "--port", str(config.resident_http_port),
                "--state-dir", str(config.runtime_root / "data" / "mock-resident"),
            ]
        argv = [
            str(ROOT / "hermes-agent" / "venv" / "bin" / "python3"),
            str(ROOT / "tools" / "hermes_resident_server.py"),
            "--host", "127.0.0.1", "--port", str(config.resident_http_port),
        ]
        for skill in ("temi-robot-control", "temi-care-memory", "temi-home-esi", "temi-discord-care-assistant"):
            argv.extend(["--skill-path", str(skills / skill / "SKILL.md")])
        root_skills = ROOT / "hermes-skills"
        if config.operator_identity_enabled and config.identity_tool_enabled:
            argv.extend(["--skill-path", str(root_skills / "temi-demo-identity" / "SKILL.md")])
        if config.repeated_discomfort_enabled:
            argv.extend(["--skill-path", str(root_skills / "temi-demo-repeated-discomfort" / "SKILL.md")])
        return argv
    if name == "bridge":
        return ["uv", "run", "--extra", "mqtt", "hermes-temi-bridge", "--env-file", str(ROOT / "hermes_temi_bridge" / ".env.example")]
    if name == "gateway":
        return [
            str(ROOT / "hermes-agent" / "venv" / "bin" / "hermes"),
            "--accept-hooks",
            "gateway",
            "run",
        ]
    if name == "viewer":
        if config.is_newcomer_mock:
            return [
                sys.executable,
                str(ROOT / "tools" / "mocks" / "mock_viewer_server.py"),
                "--host", "127.0.0.1",
                "--port", str(config.viewer_http_port),
                "--aux-port", str(config.viewer_aux_port),
                *_viewer_notification_argv(config),
                *(["--health-status", "500"] if config.test_force_health_failure_service == "viewer" else []),
            ]
        return [
            str(ROOT / "anomaly_detection" / ".venv" / "bin" / "python"),
            str(ROOT / "anomaly_detection" / "temi_action_viewer.py"),
            "--host", "0.0.0.0", "--port", str(config.viewer_http_port),
            "--source-url", f"ws://127.0.0.1:{config.adapter_frame_broadcast_port}",
            "--model", config.values["DEMO_ACTION_VIEWER_MODEL"],
            "--gguf-model-path", config.values["DEMO_ACTION_VIEWER_GGUF_MODEL_PATH"],
            "--mmproj-path", config.values["DEMO_ACTION_VIEWER_MMPROJ_PATH"],
            "--llama-server", config.values["DEMO_ACTION_VIEWER_LLAMA_SERVER"],
            "--llama-server-port", str(config.viewer_aux_port),
            "--llama-cuda-visible-devices", config.values.get("DEMO_ACTION_VIEWER_CUDA_VISIBLE_DEVICES", "3"),
            "--pose-mode", config.values.get("DEMO_ACTION_VIEWER_POSE_MODE", "auto"),
            "--pose-model", config.values.get("DEMO_ACTION_VIEWER_POSE_MODEL", "yolo26x-pose.pt"),
            "--pose-device", config.values.get("DEMO_ACTION_VIEWER_POSE_DEVICE", "3"),
            "--max-output-tokens", config.values.get("DEMO_ACTION_VIEWER_MAX_OUTPUT_TOKENS", "96"),
            "--robot-id", config.robot_id,
            "--mqtt-broker", config.mqtt_host,
            "--mqtt-port", str(config.mqtt_port),
            "--shared-root", str(config.shared_root),
            "--abnormal-publish", config.values.get("DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH", "disabled"),
            "--abnormal-cooldown-seconds", config.values.get("DEMO_ACTION_VIEWER_ABNORMAL_COOLDOWN_SECONDS", "180"),
            "--pre-alert-speak", config.values.get("DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK", "disabled"),
            *_viewer_notification_argv(config),
        ]
    if name == "mock_android":
        assert config.mock_android_health_port is not None
        return [
            str(ROOT / "hermes_temi_bridge" / ".venv" / "bin" / "python"),
            str(ROOT / "tools" / "mocks" / "mock_android_executor.py"),
            "--host", "127.0.0.1",
            "--health-port", str(config.mock_android_health_port),
            "--broker", config.mqtt_host,
            "--mqtt-port", str(config.mqtt_port),
            "--robot-id", config.robot_id,
            "--trace-path", str(config.runtime_root / "logs" / "mock" / "android-events.jsonl"),
        ]
    if name == "mock_discord":
        assert config.mock_discord_port is not None
        return [
            sys.executable,
            str(ROOT / "tools" / "mocks" / "mock_discord_server.py"),
            "--host", "127.0.0.1",
            "--port", str(config.mock_discord_port),
            "--trace-path", str(config.runtime_root / "logs" / "mock" / "discord-events.jsonl"),
        ]
    raise DemoError(f"unknown Demo service: {name}")


def _base_env(config: DemoConfig, run_id: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(config.values)
    # Export resolved values so the Bridge also honors a legacy private config
    # while its tracked .env.example supplies safe false defaults.
    env["RESIDENT_IDENTITY_ENABLED"] = "true" if config.operator_identity_enabled else "false"
    env["HERMES_DEMO_IDENTITY_TOOL_ENABLED"] = "true" if config.identity_tool_enabled else "false"
    env["HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED"] = "true" if config.identity_fast_path_enabled else "false"
    env["CARE_MEMORY_V2_ENABLED"] = "true" if config.care_memory_v2_enabled else "false"
    env["HERMES_ACCEPT_HOOKS"] = "1"
    env["LMSTUDIO_PROJECT_ROOT"] = str(ROOT)
    env["LMSTUDIO_TARGET_DIR"] = str(config.lmstudio_target_dir)
    env["LMSTUDIO_MODEL_ID"] = config.lmstudio_model_id
    env["LMSTUDIO_API_IDENTIFIER"] = config.lmstudio_api_identifier
    env["CONTEXT_LENGTH"] = str(config.context_length)
    env["LMSTUDIO_CONTEXT_LENGTH"] = str(config.lmstudio_context_length)
    env["LMSTUDIO_VISIBLE_GPUS"] = config.lmstudio_visible_gpus
    env["LMSTUDIO_SERVER_PORT"] = str(config.lmstudio_server_port)
    env["MQTT_BROKER_HOST"] = config.mqtt_host
    env["MQTT_BROKER_PORT"] = str(config.mqtt_port)
    env["ADAPTER_VISION_PORT"] = str(config.adapter_vision_port)
    env["ADAPTER_FRAME_BROADCAST_PORT"] = str(config.adapter_frame_broadcast_port)
    env["RESIDENT_HTTP_PORT"] = str(config.resident_http_port)
    env["HERMES_HTTP_URL"] = config.resident_invoke_url
    env["VIEWER_HTTP_PORT"] = str(config.viewer_http_port)
    env["VIEWER_AUX_PORT"] = str(config.viewer_aux_port)
    env["DEMO_PROFILE"] = config.profile
    env["TRACE_RUN_ID"] = run_id
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _validate_source(config: DemoConfig) -> dict[str, Any]:
    source = _source_record()
    if config.branch_policy == BRANCH_POLICY_REQUIRED:
        if not source["branch"]:
            raise DemoError("detached HEAD is not allowed while branch validation is required")
        if source["branch"] != config.expected_git_branch:
            raise DemoError(
                f"unexpected branch {source['branch']}; expected {config.expected_git_branch}"
            )
    unexpected = [
        line
        for line in source["tree"]
        if line[3:] not in ALLOWED_DIRTY_FILES
    ]
    if unexpected:
        raise DemoError("repository has non-runtime dirty files: " + ", ".join(unexpected))
    nested = _git("status", "--short", cwd=ROOT / "hermes-agent")
    if nested:
        raise DemoError("nested hermes-agent checkout is dirty")
    return source


def _assert_start_ports_clear(config: DemoConfig, specs: dict[str, ServiceSpec]) -> None:
    for spec in specs.values():
        for port in spec.ports:
            if _listener_count(port):
                raise DemoError(f"refusing to start {spec.name}: port {port} is already occupied")
        if spec.name == "bridge" and _record_from_existing(spec) is not None:
            raise DemoError("refusing to start a second Bridge process")
    for callback_socket in config.callback_sockets:
        if callback_socket.exists():
            raise DemoError("callback socket already exists; inspect its exact owner before retrying")


def _state_records(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = state.get("services", {})
    if not isinstance(raw, dict):
        raise DemoError("lifecycle state has invalid service records")
    return {name: record for name, record in raw.items() if isinstance(record, dict)}


def _managed_like_unrecorded_services(
    specs: dict[str, ServiceSpec],
    records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find only current processes that match a managed entrypoint but lack state."""
    findings: list[dict[str, Any]] = []
    for name, spec in specs.items():
        if name in records:
            continue
        try:
            record = _record_from_existing(spec)
        except DemoError:
            continue
        if record is not None:
            findings.append({"service": name, "ports": list(spec.ports)})
    return findings


def _reconcile_archived_callback_socket(config: DemoConfig) -> None:
    """Recover only sockets linked to an archived, fully stopped Bridge record."""
    if not any(path.exists() for path in config.callback_sockets):
        return
    archived = _read_json(config.last_run_path)
    bridge = _state_records(archived).get("bridge") if archived is not None else None
    if bridge is None:
        exports = config.runtime_root / "state" / "last-run" / "exports"
        manifests = sorted(exports.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for manifest_path in manifests:
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            health = manifest.get("health") if isinstance(manifest.get("health"), dict) else {}
            callback = health.get("callback_socket") if isinstance(health.get("callback_socket"), dict) else {}
            callbacks = health.get("callback_sockets") if isinstance(health.get("callback_sockets"), dict) else {}
            inventory = manifest.get("process_inventory") if isinstance(manifest.get("process_inventory"), dict) else {}
            candidate = inventory.get("bridge") if isinstance(inventory.get("bridge"), dict) else None
            if (callback.get("path") == str(config.callback_socket) or any(str(path) in callbacks for path in config.callback_sockets)) and candidate is not None:
                bridge = candidate
                break
    if bridge is None:
        raise DemoError("callback socket has no archived Bridge ownership record")
    _remove_owned_callback_sockets(config, bridge)


def _external_dependency_ready(config: DemoConfig) -> None:
    if config.mqtt_ownership == "external" and (
        _listener_count(config.mqtt_port) != 1 or not _mqtt_tcp_ready(config)
    ):
        raise DemoError("external MQTT Broker endpoint is unavailable")
    if config.lmstudio_ownership == "external" and not _lmstudio_ready(config):
        raise DemoError("external LM Studio endpoint is unavailable")
    if config.gateway_ownership == "external" and not _gateway_ready(config):
        raise DemoError("external Hermes gateway is unavailable")


def _stop_lmstudio(config: DemoConfig) -> None:
    """Ask LM Studio to release its model, server and daemon before PID cleanup."""
    for args in (
        ("unload", config.lmstudio_api_identifier),
        ("server", "stop"),
        ("daemon", "down"),
    ):
        try:
            _lmstudio_lms(config, *args, timeout=30)
        except (OSError, subprocess.TimeoutExpired, DemoError):
            # Exact process cleanup below remains authoritative when the CLI
            # is already unavailable or the daemon is already gone.
            continue


def start(config: DemoConfig) -> dict[str, Any]:
    """Start or reuse only verified managed services in dependency order."""

    source = _validate_source(config)
    ensure_runtime_layout(config)
    existing = _read_json(config.state_path)
    if existing:
        existing_status = str(existing.get("status", ""))
        if existing_status in HEALTHY_STATE_VALUES:
            health = runtime_health(config, existing)
            if health["backend_ready"]:
                return {"state": health["readiness"], "reused": True, "run_id": existing.get("run_id"), "health": health}
            raise DemoError("an owned Demo run exists but is unhealthy; use restart after inspecting status")
        if existing_status in RECOVERABLE_STATE_VALUES:
            recovery = stop(config)
            if recovery["state"] != "DEMO_STOPPED":
                raise DemoError("incomplete ownership recovery did not stop recorded processes")
        else:
            raise DemoError(f"lifecycle state {existing_status or 'UNKNOWN'} requires exact-owner recovery")
    identity_state_reset = _reset_ephemeral_demo_identity(config)
    specs = _specs(config)
    _validate_resource_manifest()
    _reconcile_archived_callback_socket(config)
    _assert_start_ports_clear(config, specs)
    _external_dependency_ready(config)
    run_id = f"demo-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    state: dict[str, Any] = {
        "schema_version": "temiagent.demo_lifecycle.v2",
        "status": STATE_STARTING,
        "run_id": run_id,
        "started_at": _utc_now(),
        "source": source,
        "runtime_root": str(config.runtime_root),
        "private_env": str(config.config_path),
        "flags": config.flags,
        "services": {},
        "ownership": {
            "lmstudio": config.lmstudio_ownership,
            "mqtt": config.mqtt_ownership,
            "gateway": config.gateway_ownership,
            "android": "mock" if config.is_newcomer_mock else "external" if not config.manage_android else "managed",
        },
    }
    env = _base_env(config, run_id)
    started: list[dict[str, Any]] = []
    try:
        for name in ("lmstudio", "mqtt", "adapter", "resident", "bridge", "mock_android", "mock_discord", "gateway", "viewer"):
            spec = specs.get(name)
            if spec is None:
                continue
            argv = _service_argv(config, name)
            record = _start_process(spec, argv, env)
            record["config_sha256"] = _sha256(config.config_path)
            record["started_at"] = _utc_now()
            record["lifecycle_run_id"] = run_id
            started.append(record)
            _persist_starting_record(config, state, name, record, argv)
            if name == "lmstudio":
                ok = _wait_for(
                    lambda: _lmstudio_ready(config) and _lmstudio_context_ready(config),
                    config.timeout_seconds,
                )
            elif name == "mqtt":
                ok = _wait_for(
                    lambda: _listener_count(config.mqtt_port) == 1 and _mqtt_tcp_ready(config),
                    30,
                )
            elif name == "adapter":
                ok = _wait_for(
                    lambda: all(_listener_count(port) == 1 for port in config.adapter_ports), 30
                )
            elif name == "resident":
                ok = _wait_for(lambda: _resident_ready(config), config.timeout_seconds)
            elif name == "bridge":
                ok = _wait_for(lambda: _identity_matches(record["leader"]) and _socket_ready(config), 30)
            elif name == "gateway":
                ok = _wait_for(lambda: _identity_matches(record["leader"]) and _gateway_ready(config), 30)
            elif name == "mock_android":
                ok = _wait_for(
                    lambda: _identity_matches(record["leader"])
                    and _mock_android_ready(config),
                    30,
                )
            elif name == "mock_discord":
                ok = _wait_for(
                    lambda: _identity_matches(record["leader"])
                    and _mock_discord_ready(config),
                    30,
                )
            else:
                ok = _wait_for(lambda: _viewer_ready(config), config.timeout_seconds)
            if not ok:
                raise DemoError(f"{name} did not pass its health gate; inspect {spec.log_path}")
            _attach_listeners(record)
            _attach_descendants(record)
            state["updated_at"] = _utc_now()
            _atomic_json(config.state_path, state)
        state["status"] = STATE_HEALTHY
        state["ready_state"] = runtime_health(config, state)["readiness"]
        state["updated_at"] = _utc_now()
        _atomic_json(config.state_path, state)
        return {
            "state": state["ready_state"],
            "reused": False,
            "run_id": run_id,
            "identity_state_reset": identity_state_reset,
            "health": runtime_health(config, state),
        }
    except Exception as exc:
        state["status"] = STATE_UNHEALTHY
        state["failure"] = {
            "code": _failure_code(str(exc)),
            "service_count": len(started),
            "recorded_at": _utc_now(),
        }
        state["updated_at"] = _utc_now()
        _atomic_json(config.state_path, state)
        rollback: list[dict[str, str]] = []
        for record in reversed(started):
            try:
                outcome = _stop_record(record, timeout_seconds=20)
                if record.get("name") == "bridge":
                    _remove_owned_callback_sockets(config, record)
                    outcome += "+callback_sockets_removed"
                rollback.append({"service": str(record.get("name", "unknown")), "outcome": outcome})
            except DemoError as rollback_error:
                rollback.append({
                    "service": str(record.get("name", "unknown")),
                    "outcome": "rollback_failed",
                    "detail": str(rollback_error),
                })
        state["rollback"] = rollback
        state["status"] = (
            STATE_UNHEALTHY
            if any(item["outcome"] == "rollback_failed" for item in rollback)
            else STATE_START_FAILED
        )
        state["updated_at"] = _utc_now()
        _atomic_json(config.state_path, state)
        _atomic_json(config.last_run_path, state)
        raise


def stop(config: DemoConfig, *, adopt_for_restart: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Stop recorded exact process identities in reverse dependency order."""

    state = _read_json(config.state_path)
    specs = _specs(config)
    if state is None and adopt_for_restart:
        records: dict[str, dict[str, Any]] = {}
        for name, spec in specs.items():
            record = _record_from_existing(spec)
            if record is not None:
                records[name] = record
        state = {
            "status": "adopted_for_explicit_restart",
            "run_id": "preexisting",
            "services": records,
            "source": _source_record(),
        }
    if state is None:
        findings = _managed_like_unrecorded_services(specs, {})
        if findings:
            return {
                "state": "STOP_INCOMPLETE_OWNERSHIP",
                "already_stopped": False,
                "warning": "managed-like process exists without lifecycle ownership state; no PID was signalled",
                "findings": findings,
                "results": [],
            }
        identity_state_reset = False if dry_run else _reset_ephemeral_demo_identity(config)
        return {
            "state": "DEMO_STOPPED",
            "already_stopped": True,
            "identity_state_reset": identity_state_reset,
            "results": [],
        }
    records = _state_records(state)
    findings = _managed_like_unrecorded_services(specs, records)
    if findings:
        return {
            "state": "STOP_INCOMPLETE_OWNERSHIP",
            "already_stopped": False,
            "warning": "managed-like process is absent from lifecycle ownership state; no PID was signalled",
            "findings": findings,
            "results": [],
        }
    results: list[dict[str, str]] = []
    for name in ("viewer", "gateway", "mock_discord", "mock_android", "bridge", "resident", "adapter", "mqtt", "lmstudio"):
        record = records.get(name)
        if record is None:
            continue
        if dry_run:
            results.append({"service": name, "outcome": "would_stop_exact_owned_pid"})
            continue
        if name == "lmstudio":
            _stop_lmstudio(config)
        outcome = _stop_record(record, timeout_seconds=30)
        if name == "bridge":
            _remove_owned_callback_sockets(config, record)
            outcome += "+callback_sockets_removed"
        results.append({"service": name, "outcome": outcome})
    if dry_run:
        return {"state": "DRY_RUN", "already_stopped": False, "results": results}
    state["status"] = STATE_STOPPED
    state["stopped_at"] = _utc_now()
    state["stop_results"] = results
    _atomic_json(config.last_run_path, state)
    config.state_path.unlink(missing_ok=True)
    identity_state_reset = _reset_ephemeral_demo_identity(config)
    return {
        "state": "DEMO_STOPPED",
        "already_stopped": False,
        "identity_state_reset": identity_state_reset,
        "results": results,
    }


def restart(config: DemoConfig) -> dict[str, Any]:
    """Archive pre-restart evidence, then perform one verified stop/start transition."""

    source = _validate_source(config)
    ensure_runtime_layout(config)
    before = _write_pre_restart_evidence(config)
    stopped = stop(config, adopt_for_restart=True)
    started = start(config)
    return {"state": started["state"], "before_evidence": str(before), "stop": stopped, "start": started, "source": source}


def _latest_trace(log_dir: Path) -> dict[str, Any] | None:
    index = log_dir / "_index.jsonl"
    if not index.is_file():
        return None
    latest: dict[str, Any] | None = None
    for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            latest = {key: parsed.get(key) for key in ("timestamp", "event_id", "stage", "status", "run_id", "source_type")}
    return latest


def runtime_health(config: DemoConfig, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return non-mutating readiness, ownership, process, listener, and trace evidence."""

    state = state or _read_json(config.state_path) or {}
    records = _state_records(state) if state else {}
    lifecycle_state = str(state.get("status", "NO_OWNERSHIP")) if state else "NO_OWNERSHIP"
    service_identity = {name: _identity_matches(record.get("leader", {})) for name, record in records.items()}
    resident = _resident_health(config)
    viewer = _http_json(config.viewer_health_url) if config.viewer_enabled else None
    listeners = {str(port): _listener_count(port) for port in config.lifecycle_ports}
    broker = {"tcp_ready": _mqtt_tcp_ready(config), "listener_count": listeners[str(config.mqtt_port)], **_broker_sessions(config)}
    lmstudio_ok = _lmstudio_ready(config) and (
        config.lmstudio_ownership != "managed" or service_identity.get("lmstudio", False)
    )
    mqtt_ok = broker["tcp_ready"] and broker["listener_count"] == 1 and (
        config.mqtt_ownership != "managed" or service_identity.get("mqtt", False)
    )
    gateway_ok = (not config.gateway_enabled) or (
        _gateway_ready(config)
        and (config.gateway_ownership != "managed" or service_identity.get("gateway", False))
    )
    adapter_ok = all(listeners[str(port)] == 1 for port in config.adapter_ports) and service_identity.get("adapter", False)
    resident_ok = _resident_ready(config) and service_identity.get("resident", False)
    bridge_ok = service_identity.get("bridge", False) and _socket_ready(config) and mqtt_ok
    viewer_ok = (not config.viewer_enabled) or bool(
        _viewer_health_contract(viewer)
        and viewer.get("source_connected")
        and viewer.get("llama_server_ready")
        and service_identity.get("viewer", False)
    )
    mock_android_ok = (not config.is_newcomer_mock) or (
        _mock_android_ready(config) and service_identity.get("mock_android", False)
    )
    mock_discord_ok = (not config.is_newcomer_mock) or (
        _mock_discord_ready(config) and service_identity.get("mock_discord", False)
    )
    backend_ready = bool(
        lmstudio_ok
        and mqtt_ok
        and adapter_ok
        and resident_ok
        and bridge_ok
        and gateway_ok
        and viewer_ok
        and mock_android_ok
        and mock_discord_ok
        and lifecycle_state in HEALTHY_STATE_VALUES
    )
    android_observed = broker["remote_sessions"] > 0
    if config.is_newcomer_mock:
        readiness = "NEWCOMER_MOCK_READY" if backend_ready else "NEWCOMER_MOCK_NOT_READY"
    else:
        readiness = "DEMO_READY" if backend_ready and android_observed else "BACKEND_READY_WAITING_ANDROID" if backend_ready else "BACKEND_NOT_READY"
    return {
        "readiness": readiness,
        "profile": config.profile,
        "lifecycle_state": lifecycle_state,
        "backend_ready": backend_ready,
        "android_connection_observed": android_observed if not config.is_newcomer_mock else False,
        "mock_android_ready": mock_android_ok if config.is_newcomer_mock else None,
        "mock_discord_ready": mock_discord_ok if config.is_newcomer_mock else None,
        "source": state.get("source") if state else _source_record(),
        "runtime_root": str(config.runtime_root),
        "private_config": {"configured": True},
        "context": {
            "context_length": config.context_length,
            "lmstudio_context_length": config.lmstudio_context_length,
            "lmstudio_visible_gpus": config.lmstudio_visible_gpus,
        },
        "ownership": {
            "lmstudio": config.lmstudio_ownership,
            "mqtt": config.mqtt_ownership,
            "gateway": config.gateway_ownership,
            "android": "mock" if config.is_newcomer_mock else "external" if not config.manage_android else "managed",
        },
        "lmstudio": {
            "ready": lmstudio_ok,
            "model_id": config.lmstudio_api_identifier,
            "context_length": config.lmstudio_context_length,
            "visible_gpus": config.lmstudio_visible_gpus,
        },
        "gateway": {"enabled": config.gateway_enabled, "ready": gateway_ok},
        "flags": config.flags,
        "services": service_identity,
        "listeners": listeners,
        "broker": broker,
        "resident_health": resident,
        "viewer_health": viewer,
        "endpoints": {
            "lmstudio_models": config.lmstudio_models_url,
            "resident_health": config.resident_health_url,
            "resident_invoke": config.resident_invoke_url,
            "viewer_health": config.viewer_health_url,
            "mock_discord": config.mock_discord_url,
        },
        "callback_socket": {"path": str(config.callback_socket), "exists": config.callback_socket.exists() and stat.S_ISSOCK(config.callback_socket.stat().st_mode)},
        "callback_sockets": {str(path): path.exists() and stat.S_ISSOCK(path.stat().st_mode) for path in config.callback_sockets},
        "demo_identity_status": _demo_identity_status(config),
        "latest_trace": _latest_trace(config.bridge_log_dir),
        "log_paths": {"bridge": str(config.bridge_log_dir), "hermes": str(config.runtime_root / "logs" / "hermes"), "asr": str(config.runtime_root / "logs" / "asr"), "trace": str(config.runtime_root / "logs" / "trace"), "lmstudio": str(config.runtime_root / "logs" / "lmstudio"), "mqtt": str(config.runtime_root / "logs" / "mqtt"), "gateway": str(config.runtime_root / "logs" / "gateway")},
    }


def doctor(config: DemoConfig) -> dict[str, Any]:
    """Run non-mutating configuration, source, dependency, and ownership diagnostics."""

    checks: list[dict[str, Any]] = []
    state = _read_json(config.state_path) or {}
    records = _state_records(state) if state else {}

    def add(name: str, status: str, code: str, message: str, *, required: bool) -> None:
        if status not in {"PASS", "WARNING", "SKIPPED", "FAIL"}:
            raise DemoError(f"doctor emitted unsupported status {status}")
        checks.append(
            {"name": name, "status": status, "code": code, "message": message, "required": required}
        )

    def guarded(name: str, operation: Callable[[], str], *, required: bool = True) -> None:
        try:
            add(name, "PASS", "CHECK_PASSED", operation(), required=required)
        except Exception as exc:
            add(name, "FAIL", "CHECK_FAILED", f"{type(exc).__name__}: {exc}", required=required)

    if state and str(state.get("status", "")) in RECOVERABLE_STATE_VALUES:
        add("lifecycle_state", "FAIL", "LIFECYCLE_RECOVERY_REQUIRED", "recorded run is incomplete; exact-owner stop/recovery is required", required=True)
    elif state and str(state.get("status", "")) not in HEALTHY_STATE_VALUES:
        add("lifecycle_state", "WARNING", "LIFECYCLE_NOT_HEALTHY", "recorded lifecycle state is not healthy", required=False)
    else:
        add("lifecycle_state", "PASS", "LIFECYCLE_STATE_CLEAR", "no incomplete lifecycle ownership state", required=True)

    guarded(
        "repository",
        lambda: (
            f"branch={_validate_source(config)['branch'] or 'detached'} "
            f"head={_validate_source(config)['head']} policy={config.branch_policy}"
        ),
    )
    guarded(
        "private_env",
        lambda: f"mode={stat.S_IMODE(config.config_path.stat().st_mode):03o} canonical_ignored_path={_is_canonical_config_path(config.config_path)}",
    )
    if _is_canonical_config_path(config.config_path):
        canonical_layout = (
            config.runtime_root,
            config.runtime_root / "config",
            config.runtime_root / "state" / "pid",
            config.runtime_root / "state" / "ownership",
            config.runtime_root / "state" / "last-run",
            config.runtime_root / "state" / "android-evidence",
            config.runtime_root / "state" / "viewer",
            config.runtime_root / "state" / "notifications",
            config.runtime_root / "state" / "media",
            config.runtime_root / "data" / "care-memory",
            config.runtime_root / "data" / "test-memory",
            config.runtime_root / "data" / "shared",
            config.runtime_root / "logs" / "bridge",
            config.runtime_root / "tmp" / "sockets",
        )
        invalid_layout = [
            path for path in canonical_layout
            if not path.is_dir() or path.is_symlink() or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) != 0o700
        ]
        add(
            "canonical_runtime_layout",
            "FAIL" if invalid_layout else "PASS",
            "CANONICAL_RUNTIME_LAYOUT_INVALID" if invalid_layout else "CANONICAL_RUNTIME_LAYOUT_READY",
            "canonical owner-only runtime directories are initialized" if not invalid_layout else "canonical runtime layout is missing or has unsafe ownership or mode",
            required=True,
        )
    if config.runtime_root.is_dir():
        mode = stat.S_IMODE(config.runtime_root.stat().st_mode)
        if mode == 0o700 and config.runtime_root.stat().st_uid == os.geteuid():
            add("runtime_root", "PASS", "RUNTIME_ROOT_READY", "owner-only runtime root exists", required=True)
        else:
            add("runtime_root", "FAIL", "RUNTIME_ROOT_MODE_INVALID", f"runtime root mode is {mode:03o}, expected 700", required=True)
    elif _has_writable_existing_parent(config.runtime_root / "probe"):
        add("runtime_root", "WARNING", "RUNTIME_ROOT_WILL_BE_CREATED", "start will create the owner-only runtime root", required=False)
    else:
        add("runtime_root", "FAIL", "RUNTIME_ROOT_UNWRITABLE", "runtime root parent is not writable", required=True)
    runtime_paths = (
        config.bridge_log_dir / "x",
        config.memory_dir / "x",
        config.runtime_root / "state" / "pid" / "probe",
        *config.callback_sockets,
        *((config.identity_state_dir / "x",) if config.identity_state_dir is not None else ()),
    )
    if all(_has_writable_existing_parent(path) for path in runtime_paths):
        add("runtime_paths", "PASS", "RUNTIME_PATHS_WRITABLE", "all runtime paths resolve below writable external parents", required=True)
        add("state_pid_root", "PASS", "STATE_PID_ROOT_WRITABLE", "state PID root is writable or will be created privately", required=True)
    else:
        add("runtime_paths", "FAIL", "RUNTIME_PATH_UNWRITABLE", "a required runtime parent is not writable", required=True)
        add("state_pid_root", "FAIL", "STATE_PID_ROOT_UNWRITABLE", "state PID root parent is not writable", required=True)

    entrypoints = [ROOT / "tools" / "temi_overview_adapter.py", ROOT / "hermes_temi_bridge" / "pyproject.toml"]
    if config.is_newcomer_mock:
        entrypoints.extend(
            ROOT / "tools" / "mocks" / name
            for name in (
                "mock_lmstudio_server.py",
                "mock_resident_server.py",
                "mock_viewer_server.py",
                "mock_android_executor.py",
                "mock_discord_server.py",
            )
        )
    else:
        entrypoints.append(ROOT / "tools" / "hermes_resident_server.py")
        if config.viewer_enabled:
            entrypoints.append(ROOT / "anomaly_detection" / "temi_action_viewer.py")
    missing = [path.relative_to(ROOT).as_posix() for path in entrypoints if not path.is_file()]
    if missing:
        add("entrypoints", "FAIL", "ENTRYPOINT_MISSING", "missing: " + ", ".join(missing), required=True)
    else:
        add("entrypoints", "PASS", "ENTRYPOINTS_READY", "all profile entrypoints are present", required=True)
    add(
        "viewer_notification_config",
        "PASS",
        "VIEWER_NOTIFICATION_CONFIG_VALID",
        f"mode={config.notification_mode}; credential_path_redacted=true",
        required=True,
    )
    guarded("resource_manifest", lambda: json.dumps(_validate_resource_manifest(), sort_keys=True))

    def endpoint(name: str, url: str, validator: Callable[[dict[str, Any]], bool], *, ownership: str, managed_name: str | None = None) -> None:
        payload, code, message = _http_health(url)
        running = managed_name is not None and managed_name in records and _identity_matches(records[managed_name].get("leader", {}))
        if payload is None:
            if ownership == "managed" and not running:
                add(name, "WARNING", "MANAGED_ENDPOINT_NOT_STARTED", message, required=False)
            else:
                add(name, "FAIL", code, message, required=True)
            return
        if validator(payload):
            add(name, "PASS", "ENDPOINT_HEALTHY", message, required=True)
        else:
            add(name, "FAIL", "HEALTH_MALFORMED", f"health response failed the {name} contract", required=True)

    if _mqtt_tcp_ready(config) and _listener_count(config.mqtt_port) == 1:
        add("mqtt_broker", "PASS", "BROKER_READY", f"ownership={config.mqtt_ownership}; endpoint reachable", required=True)
    elif config.mqtt_ownership == "managed" and "mqtt" not in records:
        add("mqtt_broker", "WARNING", "MANAGED_ENDPOINT_NOT_STARTED", "managed broker is configured but not started", required=False)
    else:
        add("mqtt_broker", "FAIL", "BROKER_UNAVAILABLE", "broker endpoint unavailable or listener count is not one", required=True)
    endpoint(
        "lm_studio",
        config.lmstudio_models_url,
        lambda payload: isinstance(payload.get("data"), list) and any(
            isinstance(item, dict) and item.get("id") == config.lmstudio_api_identifier
            for item in payload["data"]
        ),
        ownership=config.lmstudio_ownership,
        managed_name="lmstudio" if config.lmstudio_ownership == "managed" else None,
    )
    endpoint(
        "resident",
        config.resident_health_url,
        lambda payload: payload.get("status") == "ok" and payload.get("media_tool_enabled") is True and payload.get("media_fast_path_enabled") is True,
        ownership="managed",
        managed_name="resident",
    )
    if config.viewer_enabled:
        endpoint(
            "viewer",
            config.viewer_health_url,
            lambda payload: _viewer_health_contract(payload) and payload.get("source_connected") is True and payload.get("llama_server_ready") is True,
            ownership="managed",
            managed_name="viewer",
        )
    if config.is_newcomer_mock:
        assert config.mock_android_health_url is not None and config.mock_discord_url is not None
        endpoint("mock_android", config.mock_android_health_url, lambda payload: payload.get("ok") is True and payload.get("test_double") == "android", ownership="managed", managed_name="mock_android")
        endpoint("mock_discord", config.mock_discord_url.removesuffix("/webhook") + "/health", lambda payload: payload.get("ok") is True and payload.get("test_double") == "discord", ownership="managed", managed_name="mock_discord")
        add("gateway", "SKIPPED", "SKIPPED_BY_PROFILE", "newcomer_mock explicitly disables the external gateway", required=False)
        add("real_android", "SKIPPED", "REAL_DEVICE_SKIPPED", "software-only acceptance uses the local Android test double", required=False)
    elif not config.gateway_enabled:
        add("gateway", "SKIPPED", "SKIPPED_BY_CONFIG", "gateway is explicitly disabled", required=False)
    elif _gateway_ready(config):
        add("gateway", "PASS", "GATEWAY_READY", f"ownership={config.gateway_ownership}; gateway ready", required=True)
    elif config.gateway_ownership == "managed" and "gateway" not in records:
        add("gateway", "WARNING", "MANAGED_ENDPOINT_NOT_STARTED", "managed gateway is configured but not started", required=False)
    else:
        add("gateway", "FAIL", "GATEWAY_UNAVAILABLE", "Hermes gateway is unavailable", required=True)
    add("context_config", "PASS", "CONTEXT_POLICY_VALID", f"model={config.lmstudio_api_identifier} context={config.context_length} lmstudio_context={config.lmstudio_context_length} gpus={config.lmstudio_visible_gpus}", required=True)
    add("feature_flags", "PASS", "FLAGS_VALID", json.dumps(config.flags, sort_keys=True), required=True)
    guarded("nested_hermes", lambda: "clean" if not _git("status", "--short", cwd=ROOT / "hermes-agent") else (_ for _ in ()).throw(DemoError("nested hermes-agent checkout is dirty")))

    specs = _specs(config)
    for name, spec in specs.items():
        for port in spec.ports:
            listeners = _listener_count(port)
            if listeners == 0:
                add(
                    f"port_{port}", "PASS", "PORT_CLEAR", f"{name} listener port is clear", required=True
                )
                continue
            record = records.get(name)
            if listeners == 1 and record is not None and _identity_matches(record.get("leader", {})):
                add(f"port_{port}", "PASS", "PORT_OWNED", f"{name} listener is recorded with exact PID ownership", required=True)
            else:
                add(f"port_{port}", "FAIL", "PORT_CONFLICT", f"{name} expected an unowned-clear port; found {listeners} listener(s)", required=True)
    health = runtime_health(config, state)
    if not config.is_newcomer_mock:
        if health["android_connection_observed"]:
            add("android_activity", "PASS", "ANDROID_ACTIVITY_OBSERVED", "fresh remote Android MQTT session observed", required=False)
        else:
            add("android_activity", "SKIPPED", "ANDROID_EXTERNAL_NOT_OBSERVED", "Android is external and no fresh remote session is observed", required=False)
    summary = {status: sum(item["status"] == status for item in checks) for status in ("PASS", "WARNING", "SKIPPED", "FAIL")}
    return {"profile": config.profile, "checks": checks, "summary": summary, "readiness": health["readiness"]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trace_export(config: DemoConfig) -> dict[str, Any]:
    """Export existing bounded runtime evidence into an owner-only local bundle."""

    state = _read_json(config.state_path) or _read_json(config.last_run_path)
    if state is None:
        raise DemoError("no lifecycle state is available for trace export")
    ensure_runtime_layout(config)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = config.runtime_root / "state" / "last-run" / "exports" / timestamp
    _mkdir_private(bundle)
    _atomic_json(bundle / "manifest.json", {"exported_at": _utc_now(), "source": state.get("source"), "flags": config.flags, "process_inventory": state.get("services"), "health": runtime_health(config, state)})
    copied: list[Path] = [bundle / "manifest.json"]
    for source_dir, label in ((config.bridge_log_dir, "bridge-trace"), (config.runtime_root / "logs" / "hermes", "resident-log"), (config.runtime_root / "logs" / "asr", "asr-log"), (config.runtime_root / "logs" / "trace", "viewer-log")):
        if not source_dir.is_dir():
            continue
        target_dir = bundle / label
        _mkdir_private(target_dir)
        for source in sorted(source_dir.glob("*.jsonl")) + sorted(source_dir.glob("*.log")):
            if source.is_symlink() or not source.is_file():
                continue
            target = target_dir / source.name
            shutil.copyfile(source, target)
            os.chmod(target, 0o600)
            copied.append(target)
    metadata = sorted(config.shared_root.glob("events/*/*/metadata.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:10]
    if metadata:
        target_dir = bundle / "asr-metadata"
        _mkdir_private(target_dir)
        for source in metadata:
            target = target_dir / f"{source.parent.name}.json"
            shutil.copyfile(source, target)
            os.chmod(target, 0o600)
            copied.append(target)
    checksums = {path.relative_to(bundle).as_posix(): _sha256(path) for path in copied}
    _atomic_json(bundle / "SHA256SUMS.json", checksums)
    archive = bundle.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(bundle, arcname=bundle.name, recursive=True)
    os.chmod(archive, 0o600)
    return {"bundle": str(bundle), "archive": str(archive), "archive_sha256": _sha256(archive), "files": sorted(checksums)}


def _demo_identity_status(config: DemoConfig) -> dict[str, Any] | None:
    """Read status only through the same Bridge-owned callback socket."""
    if not config.operator_identity_enabled or config.identity_callback_socket is None:
        return None
    return invoke_demo_callback_socket(
        config.identity_callback_socket,
        {"action": "get_demo_identity_status", "event_id": f"operator_status_{uuid.uuid4().hex}", "robot_id": config.robot_id},
    )


def identity_command(config: DemoConfig, operation: str) -> dict[str, Any]:
    """Use the canonical Bridge identity callback; never raw-publish MQTT."""
    if not config.operator_identity_enabled or config.identity_callback_socket is None:
        raise DemoError("RESIDENT_IDENTITY_ENABLED and HERMES_DEMO_IDENTITY_TOOL_ENABLED are required for identity commands")
    event_id = f"operator_identity_{uuid.uuid4().hex}"
    payload: dict[str, Any] = {"event_id": event_id, "robot_id": config.robot_id}
    if operation in {"father", "mother"}:
        payload.update({"action": "start_demo_identity", "identity_status": operation})
    elif operation == "unknown":
        payload["action"] = "stop_demo_identity"
    elif operation == "status":
        payload["action"] = "get_demo_identity_status"
    else:
        raise DemoError("identity operation is not allowed")
    result = invoke_demo_callback_socket(config.identity_callback_socket, payload)
    if result.get("status") == "rejected":
        raise DemoError(f"identity callback rejected request: {result.get('error_code', 'unknown')}")
    return {"state": "IDENTITY_CALLBACK_COMPLETED", "operation": operation, "result": result}


def seed_repeated_discomfort(config: DemoConfig) -> dict[str, Any]:
    """Seed the private synthetic partitions through the Bridge memory API."""
    if not config.repeated_discomfort_enabled:
        raise DemoError("DEMO_REPEATED_DISCOMFORT_ENABLED is required for this seed")
    return {"state": "REPEATED_DISCOMFORT_SEEDED", "seed": seed_demo_care_memory(config.values["DEMO_CARE_MEMORY_ROOT"])}


def verify_repeated_discomfort(config: DemoConfig) -> dict[str, Any]:
    """Read the bounded seed verification without publishing or starting services."""
    if not config.repeated_discomfort_enabled:
        raise DemoError("DEMO_REPEATED_DISCOMFORT_ENABLED is required for this verification")
    return {"state": "REPEATED_DISCOMFORT_VERIFIED", "verification": verify_demo_care_memory(config.values["DEMO_CARE_MEMORY_ROOT"])}


def _print(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    state = payload.get("state") or payload.get("readiness") or "OK"
    print(state)
    if "run_id" in payload:
        print(f"run_id={payload['run_id']}")
    if "before_evidence" in payload:
        print(f"before_evidence={payload['before_evidence']}")
    if "archive" in payload:
        print(f"archive={payload['archive']}")
        print(f"sha256={payload['archive_sha256']}")


    if "config_path" in payload:
        print("config_path=" + str(payload["config_path"]))
    if "runtime_root" in payload:
        print("runtime_root=" + str(payload["runtime_root"]))
    if "profile" in payload:
        print("profile=" + str(payload["profile"]))
    for check in payload.get("checks", ()):
        print(
            "{}[{}]: {} — {}".format(
                check["status"], check["code"], check["name"], check["message"]
            )
        )

def _failure_code(message: str) -> str:
    normalized = message.upper()
    if "STOP_INCOMPLETE_OWNERSHIP" in normalized:
        return "STOP_INCOMPLETE_OWNERSHIP"
    if "LOCK_BUSY" in normalized:
        return "LOCK_BUSY"
    if "HEALTH GATE" in normalized or "DID NOT PASS" in normalized:
        return "SERVICE_HEALTH_FAILED"
    if "CONTEXT" in normalized:
        return "MODEL_CONTEXT_MISMATCH"
    if "GPU" in normalized:
        return "GPU_POLICY_MISMATCH"
    if "MQTT" in normalized or "BROKER" in normalized:
        return "BROKER_START_FAILED"
    if "LM STUDIO" in normalized:
        return "MODEL_LOAD_FAILED"
    if "GATEWAY" in normalized:
        return "GATEWAY_START_FAILED"
    if "PORT" in normalized or "LISTENER" in normalized:
        return "PORT_IN_USE_EXTERNAL"
    if "PID" in normalized or "OWNERSHIP" in normalized:
        return "PID_IDENTITY_MISMATCH"
    if "STOP" in normalized:
        return "STOP_TIMEOUT"
    return "CONFIG_INVALID"


def main(argv: list[str] | None = None) -> int:
    """Parse the lifecycle command and map expected failures to stable results."""

    parser = argparse.ArgumentParser(description="Operate the current TemiAgent Demo backend by exact process ownership.")
    parser.add_argument("--config", help="optional absolute owner-only private Demo env file")
    parser.add_argument("--json", action="store_true", help="emit full machine-readable status")
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init-config")
    init_parser.add_argument("--force", action="store_true", help="replace the canonical config")
    init_parser.add_argument("--profile", choices=(PROFILE_NEWCOMER_MOCK, PROFILE_PRODUCTION), default=PROFILE_NEWCOMER_MOCK)
    commands.add_parser("doctor")
    commands.add_parser("start")
    commands.add_parser("restart")
    commands.add_parser("status")
    stop_parser = commands.add_parser("stop")
    stop_parser.add_argument("--dry-run", action="store_true")
    commands.add_parser("trace-export")
    commands.add_parser("up")
    commands.add_parser("down")
    deploy_parser = commands.add_parser("deploy")
    deploy_parser.add_argument("--backend-only", action="store_true")
    identity_parser = commands.add_parser("identity")
    identity_parser.add_argument("operation", choices=("father", "mother", "unknown", "status"))
    seed_parser = commands.add_parser("seed")
    seed_parser.add_argument("scenario", choices=("repeated-discomfort",))
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("scenario", choices=("repeated-discomfort",))
    args = parser.parse_args(argv)
    try:
        if args.command == "init-config":
            if args.config:
                raise DemoError("init-config always writes the canonical Demo config; do not pass --config")
            payload = initialize_canonical_config(profile=args.profile, force=args.force)
            _print(payload, args.json)
            return 0
        config = load_config(resolve_config_path(args.config))
        mutating = args.command in {"start", "up", "deploy", "restart", "stop", "down", "identity", "seed"}
        if mutating:
            ensure_runtime_layout(config)
        lock = _lifecycle_lock(config) if mutating else nullcontext()
        with lock:
            if args.command == "doctor":
                payload = doctor(config)
                _print(payload, args.json)
                return 1 if payload["summary"]["FAIL"] else 0
            if args.command in {"start", "up", "deploy"}:
                payload = start(config)
            elif args.command == "restart":
                payload = restart(config)
            elif args.command in {"stop", "down"}:
                payload = stop(config, dry_run=bool(getattr(args, "dry_run", False)))
                if payload["state"] == "STOP_INCOMPLETE_OWNERSHIP":
                    _print(payload, args.json)
                    return 2
            elif args.command == "status":
                payload = runtime_health(config)
                payload["state"] = payload.pop("readiness")
            elif args.command == "identity":
                payload = identity_command(config, args.operation)
            elif args.command == "seed":
                payload = seed_repeated_discomfort(config)
            elif args.command == "verify":
                payload = verify_repeated_discomfort(config)
            else:
                payload = trace_export(config)
                payload["state"] = "TRACE_EXPORTED"
        _print(payload, args.json)
        return 0
    except DemoError as exc:
        payload = {"state": "ERROR", "failure_code": _failure_code(str(exc)), "detail": str(exc)}
        if args.json:
            _print(payload, True)
        else:
            print(f"ERROR[{payload['failure_code']}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
