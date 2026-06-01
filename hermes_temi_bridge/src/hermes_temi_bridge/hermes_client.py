from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shlex
import subprocess
import time
from typing import Any


class HermesInvocationError(RuntimeError):
    pass


class HermesTimeoutError(HermesInvocationError):
    pass


class HermesOutputError(ValueError):
    def __init__(self, reason: str, raw_output: str):
        super().__init__(reason)
        self.reason = reason
        self.raw_output = raw_output


@dataclass(frozen=True)
class HermesRequest:
    event_id: str
    robot_id: str
    conversation_id: str | None
    language: str
    asr_text: str
    frames: list[dict[str, str | int | None]]


@dataclass(frozen=True)
class HermesResponse:
    raw_output: str
    latency_ms: int
    parsed_json: dict[str, Any] | None = None


class HermesClient:
    def __init__(self, cli_command: str = "hermes", timeout_seconds: int = 60):
        self.cli_command = cli_command
        self.timeout_seconds = timeout_seconds

    def invoke(self, request: HermesRequest) -> HermesResponse:
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


def _build_command(cli_command: str, prompt: str) -> list[str]:
    if "{prompt}" in cli_command:
        rendered = cli_command.replace("{prompt}", prompt)
        return shlex.split(rendered, posix=os.name != "nt")
    command = shlex.split(cli_command, posix=os.name != "nt")
    return [*command, "-q", prompt]


def build_prompt(request: HermesRequest) -> str:
    frame_lines = []
    order = {"t_minus_1000": 1, "t_minus_500": 2, "t": 3}
    for frame in sorted(request.frames, key=lambda item: order.get(str(item["name"]), 99)):
        frame_lines.append(
            f"{order.get(str(frame['name']), len(frame_lines) + 1)}. {frame['name']}:\n"
            f"   {frame['hermes_path']}"
        )
    frames_text = "\n".join(frame_lines) or "No current visual frames are available for this event."
    return f"""You are controlling a Temi robot through the temi-robot-control skill.

Use the installed skill: /temi-robot-control

Task source:
- robot_id: {request.robot_id}
- event_id: {request.event_id}
- conversation_id: {request.conversation_id or ""}
- user language: {request.language}

User ASR text:
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

Allowed action types:
- speak
- ask_clarification
- turn
- navigate
- stop
- noop

Required output JSON schema:
{{
  "schema_version": "1.0",
  "event_id": "{request.event_id}",
  "robot_id": "{request.robot_id}",
  "confidence": 0.0,
  "reasoning_summary": "brief non-sensitive summary",
  "actions": []
}}
"""


def parse_hermes_output(raw_output: str) -> dict[str, Any]:
    candidate = _extract_json_candidate(raw_output)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise HermesOutputError("invalid_hermes_json", raw_output) from exc
    if not isinstance(parsed, dict):
        raise HermesOutputError("hermes_json_not_object", raw_output)
    return parsed


def _extract_json_candidate(raw_output: str) -> str:
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
