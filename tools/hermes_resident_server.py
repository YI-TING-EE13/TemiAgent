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
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HERMES_AGENT_ROOT = ROOT / "hermes-agent"
DEFAULT_SKILL_PATH = HERMES_AGENT_ROOT / "skills" / "temi-robot-control" / "SKILL.md"
DEFAULT_SKILL_PATHS = [DEFAULT_SKILL_PATH]


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
        self.toolsets = toolsets
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
            enabled_toolsets=toolsets,
            quiet_mode=True,
            platform="temi-resident",
            session_id="temi-resident",
            ephemeral_system_prompt=_read_skill_prompt(skill_paths),
            clarify_callback=_clarify_callback,
            credential_pool=runtime.get("credential_pool"),
            skip_context_files=True,
            skip_memory=not enable_memory,
        )
        self._agent.suppress_status_output = True
        self._agent.stream_delta_callback = None
        self._agent.tool_gen_callback = None

    def invoke(self, prompt: str) -> dict[str, Any]:
        """Run one prompt through the resident agent and measure latency."""
        started = time.monotonic()
        with self._lock:
            self.request_count += 1
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                raw_output = self._agent.chat(prompt) or ""
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "ok",
            "raw_output": raw_output,
            "latency_ms": latency_ms,
            "request_count": self.request_count,
        }

    def health(self) -> dict[str, Any]:
        """Return health and configuration metadata for operational checks."""
        return {
            "status": "ok",
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "toolsets": self.toolsets,
            "skill_path": self.skill_paths[0].as_posix() if self.skill_paths else "",
            "skill_paths": [path.as_posix() for path in self.skill_paths],
            "hermes_home": self.hermes_home,
            "memory_enabled": self.memory_enabled,
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
            result = self.server.resident.invoke(prompt)  # type: ignore[attr-defined]
            self._write_json(200, result)
        except Exception as exc:
            logging.exception("resident Hermes invocation failed")
            self._write_json(500, {"status": "error", "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        """Route BaseHTTPRequestHandler access logs through logging."""
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        """Write a UTF-8 JSON response."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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
