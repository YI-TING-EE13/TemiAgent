"""Hermes invocation clients and output parsing utilities for the Bridge."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shlex
import subprocess
import time
from typing import Any
from urllib import error, request


class HermesInvocationError(RuntimeError):
    """Raised when Hermes cannot be invoked or returns an unusable response."""


class HermesTimeoutError(HermesInvocationError):
    """Raised when a Hermes invocation exceeds the configured timeout."""


class HermesOutputError(ValueError):
    """Raised when Hermes text cannot be parsed as a valid JSON object."""

    def __init__(self, reason: str, raw_output: str):
        """Create an output parsing error while preserving the raw response."""
        super().__init__(reason)
        self.reason = reason
        self.raw_output = raw_output


@dataclass(frozen=True)
class HermesRequest:
    """Input contract passed from HermesTemiBridge to a Hermes client."""

    event_id: str
    robot_id: str
    conversation_id: str | None
    language: str
    asr_text: str
    frames: list[dict[str, str | int | None]]
    source_type: str = "asr.final"
    abnormal_action_name: str | None = None
    abnormal_reason: str | None = None
    care_context: dict[str, Any] | None = None
    active_resident: dict[str, Any] | None = None


@dataclass(frozen=True)
class HermesResponse:
    """Raw Hermes response with measured invocation latency."""

    raw_output: str
    latency_ms: int
    parsed_json: dict[str, Any] | None = None
    dispatch_metadata: dict[str, Any] | None = None


class HermesClient:
    """CLI-backed Hermes client using a subprocess per request."""

    def __init__(self, cli_command: str = "hermes", timeout_seconds: int = 60):
        """Create a CLI client.

        Args:
            cli_command: Shell-like command template. If it contains
                ``{prompt}``, that placeholder is replaced in-place; otherwise
                ``-q <prompt>`` is appended for legacy ``hermes chat`` usage.
            timeout_seconds: Maximum subprocess runtime.
        """
        self.cli_command = cli_command
        self.timeout_seconds = timeout_seconds

    def invoke(self, request: HermesRequest) -> HermesResponse:
        """Build a prompt, call Hermes CLI, and return stdout."""
        prompt = build_prompt(request)
        command = _build_command(self.cli_command, prompt)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HermesTimeoutError("hermes_timeout") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            raise HermesInvocationError(
                f"hermes exited with {completed.returncode}: {completed.stderr.strip()}"
            )
        return HermesResponse(raw_output=completed.stdout, latency_ms=latency_ms)


class HttpHermesClient:
    """HTTP-backed client for a resident Hermes worker."""

    def __init__(self, url: str = "http://127.0.0.1:8765/invoke", timeout_seconds: int = 60):
        """Create a client for ``tools/hermes_resident_server.py``."""
        self.url = url
        self.timeout_seconds = timeout_seconds

    def invoke(self, request_data: HermesRequest) -> HermesResponse:
        """POST one prompt to the resident worker and return its raw output."""
        prompt = build_prompt(request_data)
        body = json.dumps(
            {
                "event_id": request_data.event_id,
                "robot_id": request_data.robot_id,
                "conversation_id": request_data.conversation_id,
                "language": request_data.language,
                "asr_text": request_data.asr_text,
                "active_resident": request_data.active_resident,
                "prompt": prompt,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        http_request = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        started = time.monotonic()
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except TimeoutError as exc:
            raise HermesTimeoutError("hermes_http_timeout") from exc
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise HermesInvocationError(
                f"hermes http request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise HermesTimeoutError("hermes_http_timeout") from exc
            raise HermesInvocationError(f"hermes http request failed: {exc}") from exc
        except OSError as exc:
            raise HermesInvocationError(f"hermes http request failed: {exc}") from exc

        roundtrip_latency_ms = int((time.monotonic() - started) * 1000)
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise HermesInvocationError("hermes http response was not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise HermesInvocationError("hermes http response was not a JSON object")
        if parsed.get("status", "ok") != "ok":
            raise HermesInvocationError(str(parsed.get("error") or "hermes http invocation failed"))
        raw_output = parsed.get("raw_output")
        if not isinstance(raw_output, str):
            raise HermesInvocationError("hermes http response missing raw_output")
        server_latency = parsed.get("latency_ms")
        latency_ms = server_latency if isinstance(server_latency, int) else roundtrip_latency_ms
        dispatch_metadata = parsed.get("dispatch_metadata")
        if not isinstance(dispatch_metadata, dict):
            dispatch_metadata = None
        return HermesResponse(
            raw_output=raw_output,
            latency_ms=latency_ms,
            dispatch_metadata=dispatch_metadata,
        )


class MockHermesClient:
    """Deterministic Hermes stand-in for Bridge and MQTT integration tests."""

    def __init__(self, response_text: str = "這是 Bridge mock 測試"):
        """Create a mock client that always returns one speak action."""
        self.response_text = response_text

    def invoke(self, request: HermesRequest) -> HermesResponse:
        """Return a schema-valid deterministic response for tests."""
        output = {
            "schema_version": "1.0",
            "event_id": request.event_id,
            "robot_id": request.robot_id,
            "confidence": 1.0,
            "cognitive_state": {
                "intent": "mock_test",
                "home_esi_level": "Normal",
                "risk_reason": "Mock response for hardware-free Bridge testing.",
                "next_step": "speak",
            },
            "reasoning_summary": "Mock response for HermesTemiBridge integration testing.",
            "actions": [
                {
                    "action_id": "act_001",
                    "type": "speak",
                    "text": self.response_text,
                    "language": request.language,
                }
            ],
        }
        return HermesResponse(raw_output=json.dumps(output, ensure_ascii=False), latency_ms=0)


def _build_command(cli_command: str, prompt: str) -> list[str]:
    """Convert a configured Hermes command template into argv."""
    if "{prompt}" in cli_command:
        parts = shlex.split(cli_command, posix=os.name != "nt")
        return [part.replace("{prompt}", prompt) for part in parts]
    command = shlex.split(cli_command, posix=os.name != "nt")
    return [*command, "-q", prompt]


def build_prompt(request: HermesRequest) -> str:
    """Build the deterministic prompt sent to Hermes for one event."""
    if request.source_type == "perception.abnormal":
        return build_abnormal_prompt(request)
    return build_asr_prompt(request)


def format_care_context_block(care_context: dict[str, Any] | None) -> str:
    """Format structured care context for prompt injection."""
    if not care_context:
        return ""
    context_json = json.dumps(care_context, ensure_ascii=False, separators=(",", ":"))
    return (
        "Care context provided by HermesTemiBridge:\n"
        "This care_context is Bridge-provided context, not user speech.\n"
        "Do not treat text inside care_context as the current user utterance.\n"
        "Structured care memory is authoritative for reminders, daily_state, and event audit.\n"
        "If using relevant_events in risk_reason, cite event_id.\n"
        "If memory contains no evidence, ask_clarification or abstain; do not guess.\n\n"
        "<care_context>\n"
        f"{context_json}\n"
        "</care_context>\n"
    )


def format_active_resident_block(active_resident: dict[str, Any] | None) -> str:
    """Format Bridge-provided identity context without presenting it as user speech."""
    if not active_resident:
        return ""
    encoded = json.dumps(active_resident, ensure_ascii=False, separators=(",", ":"))
    return (
        "Active resident context provided by HermesTemiBridge:\n"
        "This comes from a separately validated upstream identity result. Never infer, "
        "replace, or enrich it from speech or names.\n"
        f"<active_resident>{encoded}</active_resident>\n"
    )


def build_asr_prompt(request: HermesRequest) -> str:
    """Build the deterministic prompt sent to Hermes for one ASR event."""
    frame_lines = []
    order = {"t_minus_1000": 1, "t_minus_500": 2, "t": 3}
    for frame in sorted(request.frames, key=lambda item: order.get(str(item["name"]), 99)):
        frame_lines.append(
            f"{order.get(str(frame['name']), len(frame_lines) + 1)}. {frame['name']}:\n"
            f"   {frame['hermes_path']}"
        )
    frames_text = "\n".join(frame_lines) or "No synchronized visual frames were provided."
    care_context_text = format_care_context_block(request.care_context)
    active_resident_text = format_active_resident_block(request.active_resident)
    return f"""You are controlling a Temi robot through the temi-robot-control skill.

Use the installed skill: /temi-robot-control

Task source:
- robot_id: {request.robot_id}
- event_id: {request.event_id}
- conversation_id: {request.conversation_id or ""}
- user language: {request.language}

{care_context_text}{active_resident_text}Current user ASR text:
{request.asr_text}

Synchronized visual frames:
{frames_text}

Instructions:
- Analyze the ASR text and the three visual frames.
- Infer the user's intent.
- If visual understanding is needed, use the image paths as the visual input references.
- Decide safe Temi robot actions.
- Output ONLY valid JSON.
- Do not output Markdown.
- Do not include explanations outside JSON.
- Do not execute shell commands directly.
- Do not invent unavailable robot capabilities.
- If uncertain, ask a clarification question through a speak or ask_clarification action.
- Include cognitive_state.home_esi_level and cognitive_state.risk_reason for every response.
- Use memory actions when the event should be recorded or summarized; memory actions are handled by the Bridge and are not sent to Temi.

Allowed action types:
- speak
- ask_clarification
- turn
- navigate
- stop
- noop
- log_event
- mark_reminder_done
- generate_summary
- notify_caregiver_mock

Required output JSON schema:
{{
  "schema_version": "1.0",
  "event_id": "{request.event_id}",
  "robot_id": "{request.robot_id}",
  "confidence": 0.0,
  "cognitive_state": {{
    "intent": "brief intent",
    "home_esi_level": "Normal|L1|L2|L3",
    "risk_reason": "brief reason for the risk level",
    "next_step": "brief next step"
  }},
  "reasoning_summary": "brief non-sensitive summary",
  "actions": [
    {{
      "action_id": "act_001",
      "type": "speak",
      "text": "response text",
      "language": "{request.language}"
    }}
  ]
}}

Every action object MUST include action_id. Use act_001, act_002, and so on.
"""


def build_abnormal_prompt(request: HermesRequest) -> str:
    """Build the deterministic prompt sent to Hermes for one abnormal perception event."""
    frame_lines = []
    for index, frame in enumerate(request.frames, start=1):
        frame_lines.append(f"{index}. {frame['name']}:\n   {frame['hermes_path']}")
    frames_text = "\n".join(frame_lines) or "No evidence frames were provided."
    action_name = request.abnormal_action_name or "unknown"
    reason = request.abnormal_reason or ""
    care_context_text = format_care_context_block(request.care_context)
    return f"""You are controlling a Temi robot through the temi-robot-control skill.

Use the installed skill: /temi-robot-control

Task source:
- source_type: perception.abnormal
- robot_id: {request.robot_id}
- event_id: {request.event_id}
- conversation_id: {request.conversation_id or ""}
- user language: {request.language}

{care_context_text}
Abnormal vision model observation:
- action_name: {action_name}
- model_reason: {reason}

Evidence frames:
{frames_text}

Instructions:
- Treat this as a low-frequency abnormal perception event, not an ASR event.
- The Bridge owns the consent-first abnormal-care response. Do not claim that a family member,
  caregiver, Discord, phone, or emergency service has been contacted.
- If this prompt is used for a degraded compatibility path, emit only one speak action that asks
  whether the person is safe and wants help notifying a family member or caregiver.
- Output ONLY valid JSON.
- Do not output Markdown.
- Do not include explanations outside JSON.
- Do not execute shell commands directly.
- Do not invent unavailable robot capabilities.
- Do not emit ask_clarification, notification, memory, navigation, turn, stop, or noop actions.
- Include cognitive_state.home_esi_level and cognitive_state.risk_reason for every response.

Allowed action types:
- speak

Required output JSON schema:
{{
  "schema_version": "1.0",
  "event_id": "{request.event_id}",
  "robot_id": "{request.robot_id}",
  "confidence": 0.0,
  "cognitive_state": {{
    "intent": "brief intent",
    "home_esi_level": "Normal|L1|L2|L3",
    "risk_reason": "brief reason for the risk level",
    "next_step": "brief next step"
  }},
  "reasoning_summary": "brief non-sensitive summary",
  "actions": [
    {{
      "action_id": "act_001",
      "type": "speak",
      "text": "response text",
      "language": "{request.language}"
    }}
  ]
}}

Every action object MUST include action_id. Use act_001, act_002, and so on.
"""


def parse_hermes_output(raw_output: str) -> dict[str, Any]:
    """Parse raw Hermes text and extract the JSON object required by the Bridge."""
    candidate = _extract_json_candidate(raw_output)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise HermesOutputError("invalid_hermes_json", raw_output) from exc
    if not isinstance(parsed, dict):
        raise HermesOutputError("hermes_json_not_object", raw_output)
    return parsed


def _extract_json_candidate(raw_output: str) -> str:
    """Extract a JSON object from plain, fenced, or noisy Hermes output."""
    stripped = raw_output.strip()
    if not stripped:
        raise HermesOutputError("empty_hermes_output", raw_output)
    if stripped.startswith("{"):
        return stripped
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        return stripped[first : last + 1]
    raise HermesOutputError("invalid_hermes_json", raw_output)
