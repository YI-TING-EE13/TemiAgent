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
BRIDGE_SRC = ROOT / "hermes_temi_bridge" / "src"
if BRIDGE_SRC.as_posix() not in sys.path:
    sys.path.insert(0, BRIDGE_SRC.as_posix())

from hermes_temi_bridge.demo_callback_socket import invoke_demo_callback_socket
from hermes_temi_bridge.demo_care_memory import seed_demo_care_memory, verify_demo_care_memory

EXPECTED_BRANCH = "codex/media-v11-bridge-runtime"
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


class DemoError(RuntimeError):
    """Raised for a lifecycle precondition or ownership failure."""


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


def _ownership(values: dict[str, str], name: str, *, default: str) -> str:
    """Return one explicit ownership mode without guessing from a live PID."""
    value = values.get(name, default).strip().lower()
    if value not in {"managed", "external", "disabled"}:
        raise DemoError(f"{name} must be managed, external, or disabled")
    return value


@dataclass(frozen=True)
class DemoConfig:
    config_path: Path
    runtime_root: Path
    values: dict[str, str]
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
    mqtt_ownership: str
    mqtt_config_path: Path | None
    gateway_ownership: str
    gateway_enabled: bool
    manage_android: bool
    viewer_discord_env_path: Path | None
    viewer_discord_enabled: bool

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
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise DemoError("--config must be an absolute private env path")
    if path.is_symlink() or not path.is_file():
        raise DemoError("--config must be a regular private env file")
    _outside_worktrees(path, label="private env")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600:
        raise DemoError(f"private env mode must be 0600, got {mode:03o}")
    if path.stat().st_uid != os.geteuid():
        raise DemoError("private env must be owned by the lifecycle user")
    values = _read_env(path)
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
    try:
        lmstudio_server_port = int(values.get("LMSTUDIO_SERVER_PORT", "1234"))
    except ValueError as exc:
        raise DemoError("LMSTUDIO_SERVER_PORT must be an integer") from exc
    if lmstudio_server_port != 1234:
        raise DemoError("LMSTUDIO_SERVER_PORT must be 1234 for the current Demo contract")
    lmstudio_target_dir = Path(
        values.get("LMSTUDIO_TARGET_DIR", str(ROOT / ".lmstudio-data"))
    )
    if not lmstudio_target_dir.is_absolute():
        raise DemoError("LMSTUDIO_TARGET_DIR must be absolute")
    runtime_root = Path(_require(values, "TEMIAGENT_RUNTIME_ROOT"))
    if not runtime_root.is_absolute():
        raise DemoError("TEMIAGENT_RUNTIME_ROOT must be absolute")
    _outside_worktrees(runtime_root, label="runtime root")
    try:
        mqtt_port = int(_require(values, "MQTT_BROKER_PORT"))
    except ValueError as exc:
        raise DemoError("MQTT_BROKER_PORT must be an integer") from exc
    if not 1 <= mqtt_port <= 65535:
        raise DemoError("MQTT_BROKER_PORT is outside the TCP port range")
    mqtt_config_path = None
    if mqtt_ownership == "managed":
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
    _require(values, "HERMES_HTTP_URL")
    for flag in MEDIA_FLAGS:
        if not _truthy(_require(values, flag)):
            raise DemoError(f"{flag} must be true for this Media Demo")
    viewer_enabled = _truthy(values.get("DEMO_ACTION_VIEWER_ENABLED", "false"))
    viewer_discord_enabled = values.get("DEMO_ACTION_VIEWER_DISCORD_NOTIFY", "disabled").strip().lower() == "enabled"
    viewer_discord_env_path = None
    if viewer_enabled:
        for name in (
            "DEMO_ACTION_VIEWER_MODEL",
            "DEMO_ACTION_VIEWER_GGUF_MODEL_PATH",
            "DEMO_ACTION_VIEWER_MMPROJ_PATH",
            "DEMO_ACTION_VIEWER_LLAMA_SERVER",
        ):
            _require(values, name)
        if viewer_discord_enabled:
            viewer_discord_env_path = Path(_require(values, "DEMO_ACTION_VIEWER_DISCORD_ENV_PATH"))
            if (
                not viewer_discord_env_path.is_absolute()
                or viewer_discord_env_path.is_symlink()
                or not viewer_discord_env_path.is_file()
                or stat.S_IMODE(viewer_discord_env_path.stat().st_mode) != 0o600
            ):
                raise DemoError("DEMO_ACTION_VIEWER_DISCORD_ENV_PATH must be an owner-only regular file")
            _outside_worktrees(viewer_discord_env_path, label="Discord credential env")
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
        mqtt_ownership=mqtt_ownership,
        mqtt_config_path=mqtt_config_path.resolve() if mqtt_config_path is not None else None,
        gateway_ownership=gateway_ownership,
        gateway_enabled=gateway_enabled,
        manage_android=manage_android,
        viewer_discord_env_path=viewer_discord_env_path.resolve() if viewer_discord_env_path is not None else None,
        viewer_discord_enabled=viewer_discord_enabled,
    )


def _mkdir_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _has_writable_existing_parent(path: Path) -> bool:
    """Check the nearest existing parent without making doctor mutate runtime state."""
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def ensure_runtime_layout(config: DemoConfig) -> None:
    _mkdir_private(config.runtime_root)
    for path in (
        config.runtime_root / "config",
        config.runtime_root / "state" / "pid",
        config.runtime_root / "state" / "ownership",
        config.runtime_root / "state" / "last-run",
        config.runtime_root / "state" / "android-evidence",
        config.runtime_root / "data" / "care-memory",
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
    if stat.S_IMODE(config.config_path.parent.stat().st_mode) & (stat.S_IRWXG | stat.S_IRWXO):
        raise DemoError("private config parent directory must be owner-only")


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
    finally:
        if temporary.exists():
            temporary.unlink()


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
    payload = _http_json(f"http://127.0.0.1:{config.lmstudio_server_port}/v1/models")
    if payload is None:
        return False
    models = payload.get("data")
    if not isinstance(models, list):
        # This branch keeps no-hardware tests focused on endpoint behavior. A
        # real OpenAI-compatible response is checked below when available.
        return True
    return any(
        isinstance(item, dict) and item.get("id") == config.lmstudio_api_identifier
        for item in models
    )


def _lmstudio_context_ready(config: DemoConfig) -> bool:
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
            "managed_lmstudio_supervisor.py",
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
        "adapter": ServiceSpec("adapter", ROOT / "temi_backend", "temi_overview_adapter.py", (8080, 8081), config.runtime_root / "logs" / "asr" / "overview_adapter.log"),
        "resident": ServiceSpec("resident", ROOT, "tools/hermes_resident_server.py", (8765,), config.runtime_root / "logs" / "hermes" / "resident.log"),
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
        specs["viewer"] = ServiceSpec("viewer", ROOT / "anomaly_detection", "temi_action_viewer.py", (8010, 8011), config.runtime_root / "logs" / "trace" / "action_viewer.log")
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
        "ports": {str(port): _listener_identities(port) for port in (1234, 1883, 8080, 8081, 8765, 8010, 8011)},
        "broker_sessions": _broker_sessions(config),
        "resident_health": _http_json("http://127.0.0.1:8765/health"),
        "viewer_health": _http_json("http://127.0.0.1:8010/health"),
        "flags": config.flags,
        "callback_socket_exists": config.callback_socket.exists(),
        "callback_sockets": {str(path): path.exists() for path in config.callback_sockets},
    }
    path = config.runtime_root / "state" / "last-run" / f"before-restart-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    _atomic_json(path, evidence)
    return path


def _resident_health() -> dict[str, Any] | None:
    return _http_json("http://127.0.0.1:8765/health")


def _resident_ready(config: DemoConfig) -> bool:
    health = _resident_health()
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


def _viewer_ready() -> bool:
    health = _http_json("http://127.0.0.1:8010/health")
    return bool(
        health
        and health.get("ok") is True
        and health.get("source_connected") is True
        and health.get("llama_server_ready") is True
    )


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


def _service_argv(config: DemoConfig, name: str) -> list[str]:
    skills = ROOT / "hermes-agent" / "skills"
    if name == "lmstudio":
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
            "--vision-port", "8080",
            "--frame-broadcast-port", "8081",
            "--shared-root", str(config.shared_root),
            "--bridge-root", str(config.shared_root),
            "--conversation-id", "conv_first_year_demo",
        ]
    if name == "resident":
        argv = [
            str(ROOT / "hermes-agent" / "venv" / "bin" / "python3"),
            str(ROOT / "tools" / "hermes_resident_server.py"),
            "--host", "127.0.0.1", "--port", "8765",
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
        return [
            str(ROOT / "anomaly_detection" / ".venv" / "bin" / "python"),
            str(ROOT / "anomaly_detection" / "temi_action_viewer.py"),
            "--host", "0.0.0.0", "--port", "8010",
            "--source-url", "ws://127.0.0.1:8081",
            "--model", config.values["DEMO_ACTION_VIEWER_MODEL"],
            "--gguf-model-path", config.values["DEMO_ACTION_VIEWER_GGUF_MODEL_PATH"],
            "--mmproj-path", config.values["DEMO_ACTION_VIEWER_MMPROJ_PATH"],
            "--llama-server", config.values["DEMO_ACTION_VIEWER_LLAMA_SERVER"],
            "--llama-server-port", config.values.get("DEMO_ACTION_VIEWER_LLAMA_SERVER_PORT", "8011"),
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
            "--discord-notify", config.values.get("DEMO_ACTION_VIEWER_DISCORD_NOTIFY", "disabled"),
            "--discord-env-path", str(config.viewer_discord_env_path) if config.viewer_discord_env_path is not None else "/dev/null",
            "--pre-alert-speak", config.values.get("DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK", "disabled"),
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
    env["TRACE_RUN_ID"] = run_id
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _validate_source() -> dict[str, Any]:
    source = _source_record()
    if source["branch"] != EXPECTED_BRANCH:
        raise DemoError(f"unexpected branch {source['branch']}; expected {EXPECTED_BRANCH}")
    unexpected = [line for line in source["tree"] if line[3:] not in ALLOWED_DIRTY_FILES]
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
    source = _validate_source()
    ensure_runtime_layout(config)
    existing = _read_json(config.state_path)
    if existing and existing.get("status") == "running":
        health = runtime_health(config, existing)
        if health["backend_ready"]:
            return {"state": health["readiness"], "reused": True, "run_id": existing.get("run_id"), "health": health}
        raise DemoError("an owned Demo run exists but is unhealthy; use restart after inspecting status")
    specs = _specs(config)
    _validate_resource_manifest()
    _reconcile_archived_callback_socket(config)
    _assert_start_ports_clear(config, specs)
    _external_dependency_ready(config)
    run_id = f"demo-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    state: dict[str, Any] = {
        "schema_version": "temiagent.demo_lifecycle.v1",
        "status": "starting",
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
            "android": "external" if not config.manage_android else "managed",
        },
    }
    env = _base_env(config, run_id)
    started: list[dict[str, Any]] = []
    try:
        for name in ("lmstudio", "mqtt", "adapter", "resident", "bridge", "gateway", "viewer"):
            spec = specs.get(name)
            if spec is None:
                continue
            record = _start_process(spec, _service_argv(config, name), env)
            record["config_sha256"] = _sha256(config.config_path)
            record["started_at"] = _utc_now()
            record["lifecycle_run_id"] = run_id
            started.append(record)
            state["services"][name] = record
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
                ok = _wait_for(lambda: _listener_count(8080) == 1 and _listener_count(8081) == 1, 30)
            elif name == "resident":
                ok = _wait_for(lambda: _resident_ready(config), config.timeout_seconds)
            elif name == "bridge":
                ok = _wait_for(lambda: _identity_matches(record["leader"]) and _socket_ready(config), 30)
            elif name == "gateway":
                ok = _wait_for(lambda: _identity_matches(record["leader"]) and _gateway_ready(config), 30)
            else:
                ok = _wait_for(_viewer_ready, config.timeout_seconds)
            if not ok:
                raise DemoError(f"{name} did not pass its health gate; inspect {spec.log_path}")
            _attach_listeners(record)
            _attach_descendants(record)
        state["status"] = "running"
        state["ready_state"] = runtime_health(config, state)["readiness"]
        state["updated_at"] = _utc_now()
        _atomic_json(config.state_path, state)
        return {"state": state["ready_state"], "reused": False, "run_id": run_id, "health": runtime_health(config, state)}
    except Exception:
        for record in reversed(started):
            try:
                _stop_record(record, timeout_seconds=20)
            except DemoError:
                pass
        state["status"] = "failed_rolled_back"
        state["updated_at"] = _utc_now()
        if started:
            _atomic_json(config.last_run_path, state)
        else:
            _atomic_json(
                config.runtime_root / "state" / "last-run" / f"start-failure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
                state,
            )
        raise


def stop(config: DemoConfig, *, adopt_for_restart: bool = False, dry_run: bool = False) -> dict[str, Any]:
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
        return {"state": "DEMO_STOPPED", "already_stopped": True, "results": []}
    records = _state_records(state)
    results: list[dict[str, str]] = []
    for name in ("viewer", "gateway", "bridge", "resident", "adapter", "mqtt", "lmstudio"):
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
    state["status"] = "stopped"
    state["stopped_at"] = _utc_now()
    state["stop_results"] = results
    _atomic_json(config.last_run_path, state)
    config.state_path.unlink(missing_ok=True)
    return {"state": "DEMO_STOPPED", "already_stopped": False, "results": results}


def restart(config: DemoConfig) -> dict[str, Any]:
    source = _validate_source()
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
    state = state or _read_json(config.state_path) or {}
    records = _state_records(state) if state else {}
    service_identity = {name: _identity_matches(record.get("leader", {})) for name, record in records.items()}
    resident = _resident_health()
    viewer = _http_json("http://127.0.0.1:8010/health") if config.viewer_enabled else None
    listeners = {str(port): _listener_count(port) for port in (config.lmstudio_server_port, config.mqtt_port, 8080, 8081, 8765, 8010, 8011)}
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
    adapter_ok = listeners["8080"] == 1 and listeners["8081"] == 1 and service_identity.get("adapter", False)
    resident_ok = _resident_ready(config) and service_identity.get("resident", False)
    bridge_ok = service_identity.get("bridge", False) and _socket_ready(config) and mqtt_ok
    viewer_ok = (not config.viewer_enabled) or bool(
        viewer
        and viewer.get("ok")
        and viewer.get("source_connected")
        and viewer.get("llama_server_ready")
        and (not config.viewer_discord_enabled or viewer.get("discord_notify_enabled") is True)
        and (not config.viewer_discord_enabled or viewer.get("discord_webhook_configured") is True)
        and service_identity.get("viewer", False)
    )
    backend_ready = bool(lmstudio_ok and mqtt_ok and adapter_ok and resident_ok and bridge_ok and gateway_ok and viewer_ok)
    android_observed = broker["remote_sessions"] > 0
    readiness = "DEMO_READY" if backend_ready and android_observed else "BACKEND_READY_WAITING_ANDROID" if backend_ready else "BACKEND_NOT_READY"
    return {
        "readiness": readiness,
        "backend_ready": backend_ready,
        "android_connection_observed": android_observed,
        "source": state.get("source") if state else _source_record(),
        "runtime_root": str(config.runtime_root),
        "private_env": str(config.config_path),
        "context": {
            "context_length": config.context_length,
            "lmstudio_context_length": config.lmstudio_context_length,
            "lmstudio_visible_gpus": config.lmstudio_visible_gpus,
        },
        "ownership": {
            "lmstudio": config.lmstudio_ownership,
            "mqtt": config.mqtt_ownership,
            "gateway": config.gateway_ownership,
            "android": "external" if not config.manage_android else "managed",
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
        "callback_socket": {"path": str(config.callback_socket), "exists": config.callback_socket.exists() and stat.S_ISSOCK(config.callback_socket.stat().st_mode)},
        "callback_sockets": {str(path): path.exists() and stat.S_ISSOCK(path.stat().st_mode) for path in config.callback_sockets},
        "demo_identity_status": _demo_identity_status(config),
        "latest_trace": _latest_trace(config.bridge_log_dir),
        "log_paths": {"bridge": str(config.bridge_log_dir), "hermes": str(config.runtime_root / "logs" / "hermes"), "asr": str(config.runtime_root / "logs" / "asr"), "trace": str(config.runtime_root / "logs" / "trace"), "lmstudio": str(config.runtime_root / "logs" / "lmstudio"), "mqtt": str(config.runtime_root / "logs" / "mqtt"), "gateway": str(config.runtime_root / "logs" / "gateway")},
    }


def doctor(config: DemoConfig) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def check(name: str, operation: Callable[[], str]) -> None:
        try:
            checks.append({"name": name, "status": "PASS", "detail": operation()})
        except Exception as exc:
            checks.append({"name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    check("repository", lambda: f"branch={_validate_source()['branch']} head={_validate_source()['head']}")
    check("private_env", lambda: f"mode={stat.S_IMODE(config.config_path.stat().st_mode):03o} outside_worktree=true")
    check("runtime_root", lambda: f"outside_worktree=true exists={config.runtime_root.is_dir()} mode={stat.S_IMODE(config.runtime_root.stat().st_mode):03o}")
    check("runtime_paths", lambda: "all required writable paths are under the external runtime root" if all(_has_writable_existing_parent(path) for path in (config.bridge_log_dir / "x", config.memory_dir / "x", *config.callback_sockets, *((config.identity_state_dir / "x",) if config.identity_state_dir is not None else ()))) else "required runtime parent is not writable")
    check("entrypoints", lambda: "all current source entrypoints exist" if all(path.exists() for path in (ROOT / "tools" / "temi_overview_adapter.py", ROOT / "tools" / "hermes_resident_server.py", ROOT / "hermes_temi_bridge" / ".venv" / "bin" / "hermes-temi-bridge")) else "a required entrypoint is missing")
    check("resource_manifest", lambda: json.dumps(_validate_resource_manifest(), sort_keys=True))
    check(
        "mqtt_broker",
        lambda: (
            f"ownership={config.mqtt_ownership}; endpoint reachable with exactly one listener"
            if _mqtt_tcp_ready(config) and _listener_count(config.mqtt_port) == 1
            else "ownership=managed; verified config is ready for lifecycle start"
            if config.mqtt_ownership == "managed" and config.mqtt_config_path is not None
            else "broker endpoint unavailable or listener count is not one"
        ),
    )
    check(
        "lm_studio",
        lambda: (
            f"ownership={config.lmstudio_ownership}; health endpoint reachable"
            if _lmstudio_ready(config)
            else "ownership=managed; CLI and startup script are ready for lifecycle start"
            if config.lmstudio_ownership == "managed"
            and (config.lmstudio_target_dir / "bin" / "lms").is_file()
            and (ROOT / "tools" / "start_lmstudio_3gpu.sh").is_file()
            else "LM Studio health endpoint unavailable"
        ),
    )
    check(
        "gateway",
        lambda: (
            f"ownership={config.gateway_ownership}; gateway ready"
            if _gateway_ready(config)
            else "ownership=managed; gateway entrypoint is ready for lifecycle start"
            if config.gateway_ownership == "managed"
            and (ROOT / "hermes-agent" / "venv" / "bin" / "hermes").is_file()
            else "Hermes gateway unavailable"
        ),
    )
    check("context_config", lambda: f"model={config.lmstudio_api_identifier} context={config.context_length} lmstudio_context={config.lmstudio_context_length} gpus={config.lmstudio_visible_gpus}")
    check("feature_flags", lambda: json.dumps(config.flags, sort_keys=True))
    check("nested_hermes", lambda: "clean" if not _git("status", "--short", cwd=ROOT / "hermes-agent") else "dirty")
    health = runtime_health(config)
    for port in (8080, 8081, 8765, 8010, 8011):
        if health["listeners"][str(port)]:
            checks.append({"name": f"port_{port}", "status": "WARNING", "detail": "active listener; start will reuse only a recorded healthy run or restart exact ownership"})
    checks.append({"name": "android_activity", "status": "PASS" if health["android_connection_observed"] else "PENDING", "detail": "fresh remote MQTT session observed" if health["android_connection_observed"] else "no fresh remote Android MQTT session observed"})
    summary = {status: sum(item["status"] == status for item in checks) for status in ("PASS", "PENDING", "WARNING", "FAIL")}
    return {"checks": checks, "summary": summary, "readiness": health["readiness"]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trace_export(config: DemoConfig) -> dict[str, Any]:
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


def _failure_code(message: str) -> str:
    normalized = message.upper()
    if "LOCK_BUSY" in normalized:
        return "LOCK_BUSY"
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
    parser = argparse.ArgumentParser(description="Operate the current TemiAgent Demo backend by exact process ownership.")
    parser.add_argument("--config", required=True, help="absolute owner-only private Demo env file")
    parser.add_argument("--json", action="store_true", help="emit full machine-readable status")
    commands = parser.add_subparsers(dest="command", required=True)
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
        config = load_config(args.config)
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
