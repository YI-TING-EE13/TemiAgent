#!/usr/bin/env python3
"""Run a resident Hermes worker for low-latency Temi Bridge invocations.

The standard Bridge CLI mode starts a new ``hermes -z`` process for every ASR
event. This server keeps one Hermes ``AIAgent`` instance loaded and exposes a
small localhost-only HTTP API:

- ``GET /health`` reports loaded model/provider metadata.
- ``POST /invoke`` accepts ``{"prompt": "..."}`` and returns raw Hermes text.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HERMES_AGENT_ROOT = ROOT / "hermes-agent"
DEFAULT_SKILL_PATH = HERMES_AGENT_ROOT / "skills" / "temi-robot-control" / "SKILL.md"
DEFAULT_SKILL_PATHS = [DEFAULT_SKILL_PATH]
MEDIA_TOOL_MODULE_PATH = ROOT / "tools" / "hermes_resident_media_tools.py"
IDENTITY_TOOL_MODULE_PATH = ROOT / "tools" / "hermes_resident_identity_tools.py"
REPEATED_DISCOMFORT_TOOL_MODULE_PATH = ROOT / "tools" / "hermes_resident_repeated_discomfort_tools.py"
TOOLS_ROOT = ROOT / "tools"
if TOOLS_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, TOOLS_ROOT.as_posix())

from hermes_demo_identity_fast_path import (
    DISPATCH_MODE as IDENTITY_DISPATCH_MODE,
    DemoIdentityIntent,
    match_demo_identity_intent,
)
from hermes_media_fast_path import DISPATCH_MODE, MediaIntent, match_media_intent
from hermes_repeated_discomfort_fast_path import (
    DISPATCH_MODE as REPEATED_DISCOMFORT_DISPATCH_MODE,
    RepeatedDiscomfortIntent,
    match_repeated_discomfort_intent,
)


def _ensure_hermes_import_path() -> None:
    """Place the local hermes-agent checkout before site packages."""
    root = HERMES_AGENT_ROOT.as_posix()
    if root not in sys.path:
        sys.path.insert(0, root)


def _reexec_with_hermes_python_if_available() -> None:
    """Restart under Hermes' virtualenv so runtime dependencies are available."""
    hermes_python = HERMES_AGENT_ROOT / "venv" / "bin" / "python3"
    if os.environ.get("HERMES_RESIDENT_REEXECED") == "1":
        return
    if not hermes_python.exists():
        return
    if Path(sys.executable).resolve() == hermes_python.resolve():
        return
    env = dict(os.environ)
    env["HERMES_RESIDENT_REEXECED"] = "1"
    os.execve(hermes_python.as_posix(), [hermes_python.as_posix(), *sys.argv], env)


def _clarify_callback(question: str, choices: Any = None) -> str:
    """Return a deterministic non-interactive clarification response."""
    if choices:
        return (
            "[resident Temi mode: no interactive user is available. Pick the safest "
            f"option from {choices} and continue.]"
        )
    return "[resident Temi mode: make the safest reasonable assumption and continue.]"


def _read_skill_prompt(paths: list[Path]) -> str:
    """Load one or more Temi skills as resident-only system prompt context."""
    loaded: list[str] = []
    for path in paths:
        if not path.exists():
            logging.warning("Configured resident skill path does not exist: %s", path)
            continue
        content = path.read_text(encoding="utf-8")
        loaded.append(f"## Skill: {path.as_posix()}\n\n{content}")

    if not loaded:
        logging.warning("No resident skill prompts were loaded")
        return ""

    combined = "\n\n---\n\n".join(loaded)
    return (
        "Preloaded Hermes skills for this resident Temi robot service:\n\n"
        f"{combined}\n\n"
        "For every request, follow these skills together and return only the JSON action object."
    )


def _demo_care_overlay(enabled: bool) -> str:
    """Return the production-loaded Demo overlay only when explicitly enabled."""
    if not enabled:
        return ""
    return """
## Controlled resident-care Demo overlay

This is a controlled home-care Demo. The Bridge supplies an active_resident
context derived from a separately validated upstream visual identity result.
Never infer or replace resident identity from speech, names, self-description,
or text. When active_resident.resident_id is unknown, do not read or write the
private care memory of father or mother.

The Demo residents are father (王先生, 90, hypertension care context) and mother
(王太太, 85, dialysis care context). Care plan information is Bridge-provided;
do not diagnose, recommend dosages, or make treatment decisions.

For father: if he says he is unwell again, use only father-provided relevant
care context. The synthetic Demo history may contain a prior headache report;
ask whether the current discomfort is also headache. Do not read or mention
mother's care context.

For mother: when she says dialysis has finished or she has returned home, use
the validated care-memory action to record the event, then ask about dizziness,
marked fatigue, pain, breathing discomfort, or other discomfort. Only after an
explicit no-discomfort response and her explicit consent may you call play_video
with video_id elderly_hand_exercise. A tool result with status=published only
means the Bridge accepted the command; playback is confirmed only by the Android
cmd/result lifecycle. Do not claim success when a tool returns rejected.
""".strip()


def _load_resident_tool_module(module_name: str, path: Path) -> Any:
    """Load one root-owned registration module without editing Hermes upstream."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load root-owned resident tool module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_resident_media_tools() -> Any:
    """Load the root-owned Media tool registration module."""
    return _load_resident_tool_module("temi_resident_media_tools", MEDIA_TOOL_MODULE_PATH)


def _load_resident_identity_tools() -> Any:
    """Load the root-owned operator identity tool registration module."""
    return _load_resident_tool_module("temi_resident_identity_tools", IDENTITY_TOOL_MODULE_PATH)


def _load_resident_repeated_discomfort_tools() -> Any:
    """Load the root-owned repeated-discomfort tool registration module."""
    return _load_resident_tool_module(
        "temi_resident_repeated_discomfort_tools", REPEATED_DISCOMFORT_TOOL_MODULE_PATH
    )


class ResidentHermes:
    """Own one preloaded Hermes AIAgent and serialize invocations through it."""

    def __init__(
        self,
        *,
        model: str | None,
        provider: str | None,
        toolsets: list[str],
        skill_paths: list[Path],
        cwd: Path,
        hermes_home: Path | None = None,
        enable_memory: bool = False,
        media_tool_enabled: bool | None = None,
        media_v11_enabled: bool | None = None,
        media_fast_path_enabled: bool | None = None,
        media_callback_socket: str | None = None,
        demo_operator_identity_enabled: bool | None = None,
        demo_repeated_discomfort_enabled: bool | None = None,
        identity_callback_socket: str | None = None,
        repeated_discomfort_callback_socket: str | None = None,
    ):
        """Create and warm the resident Hermes runtime.

        Args:
            model: Optional model override. Defaults to Hermes config/env.
            provider: Optional provider override. Defaults to Hermes config/env.
            toolsets: Explicit Hermes toolsets. Empty keeps the path lightweight.
            skill_paths: Paths to Temi skill markdown files loaded into the resident prompt.
            cwd: Working directory used while initializing Hermes.
            hermes_home: Optional Hermes profile/home path to use for config and memory.
            enable_memory: Enable Hermes builtin/external memory for this resident worker.
        """
        if hermes_home is not None:
            os.environ["HERMES_HOME"] = hermes_home.as_posix()
        os.chdir(cwd)
        _ensure_hermes_import_path()

        from hermes_cli.config import load_config
        from hermes_cli.models import detect_provider_for_model
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from run_agent import AIAgent

        os.environ["HERMES_YOLO_MODE"] = "1"
        os.environ["HERMES_ACCEPT_HOOKS"] = "1"

        cfg = load_config()
        model_cfg = cfg.get("model") or {}
        if isinstance(model_cfg, str):
            configured_model = model_cfg
            configured_provider = None
        else:
            configured_model = str(model_cfg.get("default") or model_cfg.get("model") or "")
            configured_provider = model_cfg.get("provider")

        effective_model = (model or os.getenv("HERMES_INFERENCE_MODEL") or configured_model).strip()
        requested_provider = (provider or os.getenv("HERMES_INFERENCE_PROVIDER") or "").strip() or None
        if requested_provider is None and model:
            detected = detect_provider_for_model(model, str(configured_provider or "auto"))
            if detected:
                requested_provider, effective_model = detected

        runtime = resolve_runtime_provider(
            requested=requested_provider or configured_provider,
            target_model=effective_model or None,
        )

        self._lock = threading.Lock()
        self.model = effective_model
        self.provider = runtime.get("provider")
        self.base_url = runtime.get("base_url")
        configured_media_tool = (
            os.getenv("HERMES_MEDIA_TOOL_ENABLED", "").lower() in {"1", "true", "yes", "on"}
            if media_tool_enabled is None
            else media_tool_enabled
        )
        configured_media_v11 = (
            os.getenv("MEDIA_V11_ENABLED", "").lower() in {"1", "true", "yes", "on"}
            if media_v11_enabled is None
            else media_v11_enabled
        )
        self.demo_care_scenario_prompt_enabled = os.getenv(
            "DEMO_CARE_SCENARIO_PROMPT_ENABLED", ""
        ).lower() in {"1", "true", "yes", "on"}
        self.media_tool_enabled = configured_media_tool and configured_media_v11
        configured_media_fast_path = (
            os.getenv("HERMES_MEDIA_FAST_PATH_ENABLED", "").lower()
            in {"1", "true", "yes", "on"}
            if media_fast_path_enabled is None
            else media_fast_path_enabled
        )
        self.media_fast_path_enabled = configured_media_fast_path and self.media_tool_enabled
        legacy_identity_enabled = _env_truthy("DEMO_OPERATOR_IDENTITY_ENABLED")
        configured_identity = _env_truthy_with_legacy(
            "RESIDENT_IDENTITY_ENABLED", legacy_identity_enabled
        )
        configured_identity_tool = _env_truthy_with_legacy(
            "HERMES_DEMO_IDENTITY_TOOL_ENABLED", legacy_identity_enabled
        )
        configured_identity_fast_path = _env_truthy_with_legacy(
            "HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED", legacy_identity_enabled
        )
        if demo_operator_identity_enabled is not None:
            configured_identity = demo_operator_identity_enabled
            configured_identity_tool = demo_operator_identity_enabled
            configured_identity_fast_path = demo_operator_identity_enabled
        configured_repeated_discomfort = (
            os.getenv("DEMO_REPEATED_DISCOMFORT_ENABLED", "").lower() in {"1", "true", "yes", "on"}
            if demo_repeated_discomfort_enabled is None
            else demo_repeated_discomfort_enabled
        )
        self.resident_identity_enabled = configured_identity
        self.identity_tool_enabled = configured_identity and configured_identity_tool
        self.demo_operator_identity_enabled = self.identity_tool_enabled
        self.identity_fast_path_enabled = configured_identity_fast_path and self.identity_tool_enabled
        self.care_memory_v2_enabled = _env_truthy("CARE_MEMORY_V2_ENABLED")
        self.demo_repeated_discomfort_enabled = (
            configured_repeated_discomfort
            and self.demo_operator_identity_enabled
            and self.care_memory_v2_enabled
        )
        self.repeated_discomfort_fast_path_enabled = self.demo_repeated_discomfort_enabled
        self.media_tool_names: list[str] = []
        self.identity_tool_names: list[str] = []
        self.repeated_discomfort_tool_names: list[str] = []
        self._media_tools = None
        self._identity_tools = None
        self._repeated_discomfort_tools = None
        effective_toolsets = list(toolsets)
        if self.media_tool_enabled:
            resolved_socket = media_callback_socket or os.getenv("HERMES_MEDIA_CALLBACK_SOCKET", "")
            self._media_tools = _load_resident_media_tools()
            self.media_tool_names = self._media_tools.install_media_tools(
                callback_socket=resolved_socket
            )
            effective_toolsets.append(self._media_tools.TOOLSET)
        if self.identity_tool_enabled:
            resolved_identity_socket = identity_callback_socket or os.getenv("HERMES_DEMO_IDENTITY_CALLBACK_SOCKET", "")
            self._identity_tools = _load_resident_identity_tools()
            self.identity_tool_names = self._identity_tools.install_identity_tools(
                callback_socket=resolved_identity_socket
            )
            effective_toolsets.append(self._identity_tools.TOOLSET)
        if self.demo_repeated_discomfort_enabled:
            resolved_care_socket = repeated_discomfort_callback_socket or os.getenv("HERMES_DEMO_CARE_CALLBACK_SOCKET", "")
            self._repeated_discomfort_tools = _load_resident_repeated_discomfort_tools()
            self.repeated_discomfort_tool_names = self._repeated_discomfort_tools.install_repeated_discomfort_tools(
                callback_socket=resolved_care_socket
            )
            effective_toolsets.append(self._repeated_discomfort_tools.TOOLSET)
        self.toolsets = effective_toolsets
        self.skill_paths = skill_paths
        self.hermes_home = os.environ.get("HERMES_HOME", "")
        self.memory_enabled = enable_memory
        self.started_at = time.time()
        self.request_count = 0
        self._agent = AIAgent(
            api_key=runtime.get("api_key"),
            base_url=runtime.get("base_url"),
            provider=runtime.get("provider"),
            api_mode=runtime.get("api_mode"),
            model=effective_model,
            enabled_toolsets=effective_toolsets,
            quiet_mode=True,
            platform="temi-resident",
            session_id="temi-resident",
            ephemeral_system_prompt=_combine_system_prompt(
                _read_skill_prompt(skill_paths),
                _demo_care_overlay(self.demo_care_scenario_prompt_enabled),
            ),
            clarify_callback=_clarify_callback,
            credential_pool=runtime.get("credential_pool"),
            skip_context_files=True,
            skip_memory=not enable_memory,
        )
        self._agent.suppress_status_output = True
        self._agent.stream_delta_callback = None
        self._agent.tool_gen_callback = None
        self.context_length, self.compression_context_length = _effective_context_lengths(self._agent)

    def invoke(
        self,
        prompt: str,
        invocation_context: dict[str, str] | None = None,
        *,
        asr_text: str = "",
    ) -> dict[str, Any]:
        """Run a reviewed fast path or one prompt through the resident agent."""
        started = time.monotonic()
        context = invocation_context or {}
        with self._lock:
            self.request_count += 1
            identity_intent = match_demo_identity_intent(asr_text) if getattr(self, "identity_fast_path_enabled", False) else None
            if identity_intent is not None and self._identity_tools is not None:
                return self._invoke_deterministic_identity_intent(identity_intent, context, started)
            repeated_intent = (
                match_repeated_discomfort_intent(asr_text)
                if getattr(self, "repeated_discomfort_fast_path_enabled", False)
                and context.get("resident_id") == "father"
                else None
            )
            if repeated_intent is not None and self._repeated_discomfort_tools is not None:
                return self._invoke_deterministic_repeated_discomfort_intent(
                    repeated_intent, context, started, asr_text
                )
            intent = match_media_intent(asr_text) if self.media_fast_path_enabled else None
            if intent is not None and self._media_tools is not None:
                return self._invoke_deterministic_media_intent(intent, context, started)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr), ExitStack() as callbacks:
                if self._media_tools is not None:
                    callbacks.enter_context(self._media_tools.invocation_context(context))
                if getattr(self, "_identity_tools", None) is not None:
                    callbacks.enter_context(self._identity_tools.invocation_context(context))
                if getattr(self, "_repeated_discomfort_tools", None) is not None:
                    callbacks.enter_context(self._repeated_discomfort_tools.invocation_context(context))
                raw_output = self._agent.chat(prompt) or ""
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "ok",
            "raw_output": raw_output,
            "latency_ms": latency_ms,
            "request_count": self.request_count,
        }

    def _invoke_deterministic_media_intent(
        self,
        intent: MediaIntent,
        context: dict[str, str],
        started: float,
    ) -> dict[str, Any]:
        """Invoke the registered native tool without calling the language model."""
        assert self._media_tools is not None
        with self._media_tools.invocation_context(context):
            callback = self._media_tools.invoke_registered_media_tool(
                intent.action, intent.arguments
            )
        callback_status = str(callback.get("status") or "rejected")
        command_id = callback.get("command_id")
        accepted = callback_status == "published" and isinstance(command_id, str) and bool(command_id)
        latency_ms = int((time.monotonic() - started) * 1000)
        dispatch = {
            "dispatch_mode": DISPATCH_MODE,
            "intent": intent.action,
            "video_id": intent.video_id,
            "resident_id": context.get("resident_id") or "unknown",
            "callback_status": callback_status,
            "bridge_command_id": command_id if isinstance(command_id, str) else None,
            "dispatch_latency_ms": latency_ms,
        }
        return {
            "status": "ok",
            "raw_output": json.dumps(
                _fast_path_action_output(
                    event_id=context.get("event_id", ""),
                    robot_id=context.get("robot_id", ""),
                    action=intent.action,
                    accepted=accepted,
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "latency_ms": latency_ms,
            "request_count": self.request_count,
            "dispatch_metadata": dispatch,
        }

    def _invoke_deterministic_identity_intent(
        self,
        intent: DemoIdentityIntent,
        context: dict[str, str],
        started: float,
    ) -> dict[str, Any]:
        """Invoke the identity native tool before LLM inference."""
        assert self._identity_tools is not None
        arguments = {"identity_status": intent.identity_status} if intent.identity_status else {}
        with self._identity_tools.invocation_context(context):
            callback = self._identity_tools.invoke_registered_identity_tool(intent.action, arguments)
        status = str(callback.get("status") or "rejected")
        selected = str(callback.get("identity_status") or intent.identity_status or "unknown")
        text = {
            "father": "Demo 身分已切換為爸爸。",
            "mother": "Demo 身分已切換為媽媽。",
            "unknown": "Demo 身分已清除。",
        }.get(selected, "Demo 身分目前為未知。")
        if intent.action == "get_demo_identity_status":
            text = {"father": "Demo 目前身分為爸爸。", "mother": "Demo 目前身分為媽媽。", "unknown": "Demo 目前沒有已選定的身分。"}.get(selected, "Demo 身分目前為未知。")
        accepted = status in {"published", "ok"}
        return _deterministic_callback_response(
            event_id=context.get("event_id", ""), robot_id=context.get("robot_id", ""), text=text,
            accepted=accepted, dispatch_mode=IDENTITY_DISPATCH_MODE, intent=intent.action,
            callback_status=status, started=started,
        )

    def _invoke_deterministic_repeated_discomfort_intent(
        self,
        intent: RepeatedDiscomfortIntent,
        context: dict[str, str],
        started: float,
        asr_text: str,
    ) -> dict[str, Any]:
        """Invoke the father-only synthetic-memory flow before LLM inference."""
        assert self._repeated_discomfort_tools is not None
        arguments: dict[str, Any] = {}
        if intent.action == "record_repeated_blood_pressure":
            arguments = {"systolic": intent.systolic, "diastolic": intent.diastolic, "asr_text": asr_text}
        with self._repeated_discomfort_tools.invocation_context(context):
            callback = self._repeated_discomfort_tools.invoke_registered_repeated_discomfort_tool(intent.action, arguments)
        status = str(callback.get("status") or "rejected")
        text = {
            "confirmed": "好的，請告訴我這次量到的血壓，例如血壓128/78。",
            "recorded": "已記錄您目前頭痛，以及剛才提供的血壓數值。請先停止手邊工作並坐著休息；若症狀持續、加重，或出現其他不適，請聯絡照護者或醫療人員。",
        }.get(status, "抱歉，目前無法完成這個 Demo 記錄，請稍後再試。")
        if status == "retrieved":
            text = _retrieved_discomfort_text(callback)
        return _deterministic_callback_response(
            event_id=context.get("event_id", ""), robot_id=context.get("robot_id", ""), text=text,
            accepted=status in {"retrieved", "confirmed", "recorded"},
            dispatch_mode=REPEATED_DISCOMFORT_DISPATCH_MODE, intent=intent.action,
            callback_status=status, started=started,
        )

    def health(self) -> dict[str, Any]:
        """Return health and configuration metadata for operational checks."""
        return {
            "status": "ok",
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "context_length": getattr(self, "context_length", None),
            "compression_context_length": getattr(self, "compression_context_length", None),
            "toolsets": self.toolsets,
            "skill_path": self.skill_paths[0].as_posix() if self.skill_paths else "",
            "skill_paths": [path.as_posix() for path in self.skill_paths],
            "hermes_home": self.hermes_home,
            "memory_enabled": self.memory_enabled,
            "demo_care_scenario_prompt_enabled": self.demo_care_scenario_prompt_enabled,
            "media_tool_enabled": self.media_tool_enabled,
            "media_tool_names": self.media_tool_names,
            "media_fast_path_enabled": self.media_fast_path_enabled,
            "demo_operator_identity_enabled": self.demo_operator_identity_enabled,
            "resident_identity_enabled": self.resident_identity_enabled,
            "identity_tool_enabled": self.identity_tool_enabled,
            "identity_tool_names": self.identity_tool_names,
            "identity_fast_path_enabled": self.identity_fast_path_enabled,
            "care_memory_v2_enabled": self.care_memory_v2_enabled,
            "demo_repeated_discomfort_enabled": self.demo_repeated_discomfort_enabled,
            "repeated_discomfort_tool_names": self.repeated_discomfort_tool_names,
            "repeated_discomfort_fast_path_enabled": self.repeated_discomfort_fast_path_enabled,
            "uptime_seconds": int(time.time() - self.started_at),
            "request_count": self.request_count,
        }


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the resident worker API."""

    server_version = "HermesResidentTemi/0.1"

    def do_GET(self) -> None:
        """Serve health metadata."""
        if self.path != "/health":
            self._write_json(404, {"status": "error", "error": "not found"})
            return
        self._write_json(200, self.server.resident.health())  # type: ignore[attr-defined]

    def do_POST(self) -> None:
        """Serve prompt invocation requests."""
        if self.path != "/invoke":
            self._write_json(404, {"status": "error", "error": "not found"})
            return
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._write_json(400, {"status": "error", "error": "invalid content length"})
                return
            if length <= 0:
                self._write_json(400, {"status": "error", "error": "empty request body"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                self._write_json(400, {"status": "error", "error": "request body must be a JSON object"})
                return
            prompt = payload.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                self._write_json(400, {"status": "error", "error": "missing prompt"})
                return
            active_resident = payload.get("active_resident")
            if active_resident is not None and not isinstance(active_resident, dict):
                self._write_json(400, {"status": "error", "error": "invalid active_resident"})
                return
            invocation_context = {
                "event_id": str(payload.get("event_id") or ""),
                "robot_id": str(payload.get("robot_id") or ""),
                "resident_id": str((active_resident or {}).get("resident_id") or ""),
            }
            asr_text = payload.get("asr_text", "")
            if not isinstance(asr_text, str):
                self._write_json(400, {"status": "error", "error": "invalid asr_text"})
                return
            result = self.server.resident.invoke(  # type: ignore[attr-defined]
                prompt, invocation_context, asr_text=asr_text
            )
            self._write_json(200, result)
        except Exception as exc:
            structured = _structured_failure_response(exc)
            if structured is not None:
                logging.error(
                    "resident Hermes invocation failed: %s",
                    structured["failure"]["error_class"],
                )
                self._write_json(500, structured)
                return
            logging.exception("resident Hermes invocation failed")
            self._write_json(500, {"status": "error", "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        """Route BaseHTTPRequestHandler access logs through logging."""
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> bool:
        """Write a UTF-8 JSON response unless the client has disconnected."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            logging.info(
                "resident client disconnected before response delivery (%s)",
                type(exc).__name__,
            )
            return False
        return True


class ResidentServer(ThreadingHTTPServer):
    """Threading HTTP server carrying the ResidentHermes dependency."""

    def __init__(self, server_address: tuple[str, int], resident: ResidentHermes):
        """Attach a resident Hermes instance to the HTTP server."""
        super().__init__(server_address, RequestHandler)
        self.resident = resident


def _parse_toolsets(raw: str) -> list[str]:
    """Parse a comma-separated toolset list."""
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


_RESIDENT_FAILURE_MESSAGES = {
    "hermes_compression_exhausted": (
        "Hermes could not produce a response after bounded context recovery."
    ),
    "hermes_conversation_failed": "Hermes could not produce a response.",
    "hermes_missing_final_response": "Hermes completed without a final response.",
}
_SAFE_FAILURE_CATEGORY_RE = re.compile(r"^[a-z0-9_]{1,80}$")


def _structured_failure_response(exc: BaseException) -> dict[str, Any] | None:
    """Convert a typed Hermes failure into a bounded, non-sensitive HTTP payload."""
    to_dict = getattr(exc, "to_dict", None)
    if not callable(to_dict):
        return None
    try:
        metadata = to_dict()
    except Exception:
        return None
    if not isinstance(metadata, dict):
        return None

    error_class = metadata.get("error_class")
    if not isinstance(error_class, str) or error_class not in _RESIDENT_FAILURE_MESSAGES:
        return None
    category = metadata.get("original_failure_category")
    if not isinstance(category, str) or _SAFE_FAILURE_CATEGORY_RE.fullmatch(category) is None:
        return None
    retryable = metadata.get("retryable")
    if not isinstance(retryable, bool):
        return None

    return {
        "status": "error",
        "error": _RESIDENT_FAILURE_MESSAGES[error_class],
        "failure": {
            "error_class": error_class,
            "original_failure_category": category,
            "retryable": retryable,
        },
    }


def _combine_system_prompt(base: str, overlay: str) -> str:
    """Combine optional production prompt components without empty separators."""
    return "\n\n---\n\n".join(item for item in (base, overlay) if item)


def _env_truthy(name: str) -> bool:
    """Read one explicit boolean feature flag from the process environment."""
    return os.getenv(name, "").lower() in {"1", "true", "yes", "on"}


def _env_truthy_with_legacy(name: str, legacy_value: bool) -> bool:
    """Prefer an explicit flag while preserving old private Demo configs temporarily."""
    return _env_truthy(name) if name in os.environ else legacy_value


def _effective_context_lengths(agent: Any) -> tuple[int, int]:
    """Return the required primary and auxiliary compression context limits.

    The Demo must not silently fall back to a provider metadata default: both
    values are explicit in the private Hermes configuration and must agree.
    """
    compressor = getattr(agent, "context_compressor", None)
    model_context = getattr(compressor, "context_length", None)
    compression_context = getattr(agent, "_aux_compression_context_length_config", None)
    try:
        model_context = int(model_context)
        compression_context = int(compression_context)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Hermes config must set positive model and compression context lengths"
        ) from exc
    if model_context <= 0 or compression_context <= 0:
        raise RuntimeError("Hermes config must set positive model and compression context lengths")
    if model_context != compression_context:
        raise RuntimeError("Hermes model and compression context lengths must match")
    return model_context, compression_context


def _retrieved_discomfort_text(callback: dict[str, Any]) -> str:
    """Describe only the timestamp returned by the canonical retrieval callback."""
    prior = callback.get("prior_event")
    if not isinstance(prior, dict) or prior.get("event_id") != "demo_father_headache_two_days_ago":
        return "我目前無法取得先前的照護紀錄。請告訴我現在是哪裡不舒服。"
    raw_timestamp = prior.get("timestamp")
    if not isinstance(raw_timestamp, str):
        return "我目前無法取得先前的照護紀錄。請告訴我現在是哪裡不舒服。"
    try:
        occurred_at = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "我目前無法取得先前的照護紀錄。請告訴我現在是哪裡不舒服。"
    local_occurred_at = occurred_at.astimezone()
    local_today = datetime.now().astimezone().date()
    days_ago = (local_today - local_occurred_at.date()).days
    if days_ago == 0:
        relative = "今天"
    elif days_ago == 1:
        relative = "昨天"
    elif days_ago == 2:
        relative = "前天"
    elif days_ago > 2:
        relative = f"{days_ago} 天前"
    else:
        relative = local_occurred_at.strftime("%Y 年 %m 月 %d 日")
    hour = local_occurred_at.hour
    period = "上午" if hour < 12 else "下午"
    display_hour = hour % 12 or 12
    return (
        f"王先生，紀錄顯示您{relative}{period} {display_hour}:{local_occurred_at.minute:02d}"
        "曾回報頭痛。請問您現在也是頭痛嗎？"
    )


def _deterministic_callback_response(
    *,
    event_id: str,
    robot_id: str,
    text: str,
    accepted: bool,
    dispatch_mode: str,
    intent: str,
    callback_status: str,
    started: float,
) -> dict[str, Any]:
    """Build a normal Bridge-validated speak acknowledgement after a callback."""
    latency_ms = int((time.monotonic() - started) * 1000)
    output = {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": robot_id,
        "confidence": 1.0 if accepted else 0.0,
        "cognitive_state": {
            "intent": intent,
            "home_esi_level": "Normal",
            "risk_reason": "Native Demo callback accepted the reviewed request." if accepted else "Native Demo callback rejected the reviewed request.",
            "next_step": "acknowledge_demo_callback" if accepted else "report_demo_callback_unavailable",
        },
        "reasoning_summary": "Resident Hermes deterministic Demo callback dispatch.",
        "actions": [{"action_id": "act_001", "type": "speak", "text": text, "language": "zh-TW"}],
    }
    return {
        "status": "ok",
        "raw_output": json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        "latency_ms": latency_ms,
        "request_count": 0,
        "dispatch_metadata": {"dispatch_mode": dispatch_mode, "intent": intent, "callback_status": callback_status, "dispatch_latency_ms": latency_ms},
    }


def _fast_path_action_output(
    *, event_id: str, robot_id: str, action: str, accepted: bool
) -> dict[str, Any]:
    """Build a normal Bridge-validated acknowledgement after callback completion."""
    success_text = {
        "play_video": "好的，現在為您播放手部運動影片。",
        "pause_video": "好的，已暫停影片。",
        "resume_video": "好的，已繼續播放影片。",
        "stop_video": "好的，已停止影片。",
    }[action]
    text = success_text if accepted else "抱歉，目前無法播放影片，請稍後再試。"
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "robot_id": robot_id,
        "confidence": 1.0 if accepted else 0.0,
        "cognitive_state": {
            "intent": action,
            "home_esi_level": "Normal",
            "risk_reason": "Native Media callback accepted the reviewed request."
            if accepted
            else "Native Media callback rejected the reviewed request.",
            "next_step": "acknowledge_media_request" if accepted else "report_media_unavailable",
        },
        "reasoning_summary": "Resident Hermes deterministic Media dispatch.",
        "actions": [
            {
                "action_id": "act_001",
                "type": "speak",
                "text": text,
                "language": "zh-TW",
            }
        ],
    }


def _resolve_skill_paths(raw_paths: list[str] | None) -> list[Path]:
    """Return configured skill paths, falling back to the default Temi control skill."""
    if raw_paths:
        return [Path(path) for path in raw_paths]
    return list(DEFAULT_SKILL_PATHS)


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and serve the resident worker until interrupted."""
    _reexec_with_hermes_python_if_available()

    parser = argparse.ArgumentParser(description="Run a resident Hermes worker for Temi.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument(
        "--toolsets",
        default=os.getenv("HERMES_RESIDENT_TOOLSETS", ""),
        help="Comma-separated Hermes toolsets. Empty keeps the Temi path lightweight.",
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        default=None,
        help=(
            "Path to a SKILL.md file to preload. Repeat this option to load multiple "
            "skills. Defaults to temi-robot-control when omitted."
        ),
    )
    parser.add_argument("--cwd", default=ROOT.as_posix())
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--hermes-home",
        default=os.getenv("HERMES_RESIDENT_HERMES_HOME", ""),
        help="Optional HERMES_HOME/profile path for resident config and memory.",
    )
    parser.add_argument(
        "--enable-memory",
        action="store_true",
        default=os.getenv("HERMES_RESIDENT_ENABLE_MEMORY", "").lower() in {"1", "true", "yes"},
        help="Enable Hermes builtin and configured external memory providers.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    resident = ResidentHermes(
        model=args.model,
        provider=args.provider,
        toolsets=_parse_toolsets(args.toolsets),
        skill_paths=_resolve_skill_paths(args.skill_path),
        cwd=Path(args.cwd),
        hermes_home=Path(args.hermes_home) if args.hermes_home else None,
        enable_memory=args.enable_memory,
    )
    server = ResidentServer((args.host, args.port), resident)
    logging.info(
        (
            "Hermes resident server ready on http://%s:%s model=%s provider=%s "
            "toolsets=%s skill_paths=%s memory_enabled=%s hermes_home=%s"
        ),
        args.host,
        args.port,
        resident.model,
        resident.provider,
        resident.toolsets,
        [path.as_posix() for path in resident.skill_paths],
        resident.memory_enabled,
        resident.hermes_home,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping Hermes resident server")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
