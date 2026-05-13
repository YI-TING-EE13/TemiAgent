---
name: temi-robot-control
description: Safely control a Temi robot from Hermes when input contains Temi ASR text, robot_id, event_id, conversation_id, and three synchronized visual frame paths. Use for Temi observation, visual question answering, safe turn/navigation/stop planning, clarification, and JSON-only robot action output for a bridge service.
metadata:
  version: 0.1.0
  platforms: [linux]
  hermes:
    tags: [robotics, temi, mqtt, vision, multimodal, automation]
    category: robotics
    requires_toolsets: [terminal]
---

# Temi Robot Control Skill

## Purpose

Use this skill when Hermes receives a task from a Temi robot interaction.

The input usually contains:

- `robot_id`
- `event_id`
- `conversation_id`
- user's ASR text
- three synchronized image paths:
  - `t_minus_1000`
  - `t_minus_500`
  - `t`
- user language, usually `zh-TW`

Infer the user's intent and output safe, validated JSON actions for the Temi robot.

This skill must not directly control hardware. It only outputs JSON actions. A separate bridge service validates and dispatches actions to the robot.

## Inputs

Expected input shape:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "robot_id": "temi-01",
  "conversation_id": "conv_001",
  "language": "zh-TW",
  "asr_text": "幫我看看桌上的東西是什麼",
  "frames": [
    {
      "name": "t_minus_1000",
      "path": "/shared/temi/events/temi-01/evt_001/frame_t_minus_1000.jpg"
    },
    {
      "name": "t_minus_500",
      "path": "/shared/temi/events/temi-01/evt_001/frame_t_minus_500.jpg"
    },
    {
      "name": "t",
      "path": "/shared/temi/events/temi-01/evt_001/frame_t.jpg"
    }
  ]
}
```

## Core Rules

1. Output exactly one JSON object.
2. Do not output Markdown.
3. Do not execute shell commands.
4. Do not directly control Temi hardware.
5. Do not invent robot capabilities.
6. Do not include private chain-of-thought. Use only a brief `reasoning_summary`.
7. Use `ask_clarification` when the user intent, visual referent, destination, or safety condition is unclear.
8. Prefer `speak` when the task only requires answering.
9. Use `noop` when no safe robot action is needed.

Detailed rules are in `references/safety_rules.md`.

## Visual Reasoning

Use the three frames as short temporal context:

- `t_minus_1000` shows context about one second before speech ended.
- `t_minus_500` may capture gestures, pointing, or gaze direction.
- `t` is closest to the end of the utterance.

When the user says "這個", "那個", "這裡", "那邊", or gives a pointing-related instruction, compare all three frames. If the referent is unclear, do not guess.

## Allowed Actions

You may output only:

- `speak`
- `ask_clarification`
- `turn`
- `navigate`
- `stop`
- `noop`

The full JSON schema is in `references/action_schema.json`.

## Output Contract

Return JSON only:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "robot_id": "temi-01",
  "confidence": 0.85,
  "reasoning_summary": "Brief summary of why these actions are appropriate.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上有一個杯子。",
      "language": "zh-TW"
    }
  ]
}
```

No text may appear before or after the JSON.

## Decision Policy

1. If the user asks a question about what is visible, inspect the images and answer with `speak`.
2. If the user refers to "this", "that", "there", or points, use the three frames to infer the referent. If unclear, use `ask_clarification`.
3. If the user asks Temi to move to a known location, use `navigate`.
4. If the user asks Temi to turn, use `turn`.
5. If the user asks Temi to stop, use `stop`.
6. If the request is unsupported, use `speak` to explain the limitation.
7. If there is any safety uncertainty, use `ask_clarification` or `noop`.

## Validation

Before final output, verify:

1. Output is valid JSON.
2. No Markdown is included.
3. `schema_version` is `"1.0"`.
4. `event_id` matches input.
5. `robot_id` matches input.
6. `confidence` is between 0 and 1.
7. `actions` is a non-empty array with at most 5 items.
8. Every action has `action_id`.
9. Every action type is allowed.
10. Navigation target is in the allowlist.
11. Turn degrees is one of `15`, `30`, `45`, `60`, or `90`.
12. If uncertain, clarification is used instead of movement.

See `references/examples.md` for output examples.
