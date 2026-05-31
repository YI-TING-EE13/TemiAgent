---
name: temi-robot-control
description: Generate safe JSON-only Temi robot action plans for Hermes from Temi ASR text, robot_id, event_id, conversation context, and synchronized visual frame paths. Use for Temi visual question answering, clarification, speech replies, safe turn/navigation/stop/noop planning, and bridge-validated robot command output. Do not use to directly control hardware, publish MQTT, run shell commands, or execute Temi SDK calls.
---

# Temi Robot Control Skill

## Purpose

Use this skill when Hermes receives a single Temi robot interaction event from `HermesTemiBridge`.

This skill is an operation manual for decision making only. It must output one JSON object that the bridge can validate and dispatch. It must never directly control Temi hardware, publish MQTT messages, run scripts, or call the Temi SDK.

## Expected Input

The bridge should provide:

- `schema_version`
- `event_id`
- `robot_id`
- `conversation_id`
- `language`, usually `zh-TW`
- ASR final text from the user
- three synchronized image paths visible to the Hermes runtime:
  - `t_minus_1000`
  - `t_minus_500`
  - `t`

Example:

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
2. Do not output Markdown, fenced code blocks, comments, or prose outside JSON.
3. Do not execute shell commands or call scripts.
4. Do not publish or subscribe MQTT.
5. Do not directly control Temi hardware or the Temi SDK.
6. Do not invent robot capabilities.
7. Do not include private chain-of-thought. Use only a brief `reasoning_summary`.
8. Use `ask_clarification` when user intent, visual referent, destination, or safety is unclear.
9. Prefer `speak` when the task only requires answering.
10. Use `noop` when no safe or useful robot action is needed.

Read `references/safety_rules.md` when safety, ambiguity, motion, or unsupported requests matter.

## Visual Reasoning

Use the three frames as short temporal context:

- `t_minus_1000` shows context about one second before speech ended.
- `t_minus_500` may capture gestures, pointing, gaze, or object movement.
- `t` is closest to the end of the utterance.

For vague references such as "這個", "那個", "那邊", "你看到那個嗎", or pointing-related requests, compare all three frames. If the referent is not clear, do not guess; ask a clarification question.

## Allowed Actions

Output only these action types:

- `speak`
- `ask_clarification`
- `turn`
- `navigate`
- `stop`
- `noop`

Use `references/action_schema.json` as the source of truth for fields, required properties, allowlists, and limits.

## Output Contract

Return JSON only:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "robot_id": "temi-01",
  "confidence": 0.85,
  "reasoning_summary": "The user asks for visible object identification, so a spoken answer is sufficient.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上有幾個物品，可能包含杯子和筆電。",
      "language": "zh-TW"
    }
  ]
}
```

No text may appear before or after the JSON object.

## Decision Policy

1. If the user asks a question about what is visible, inspect the images and answer with `speak`.
2. If the user refers to "this", "that", "there", or points, use the three frames to infer the referent. If unclear, use `ask_clarification`.
3. If the user asks Temi to move to a known allowlisted location, use `navigate`.
4. If the user asks Temi to turn, use `turn` with the smallest useful allowed degree.
5. If the user asks Temi to stop, use `stop`.
6. If the request is unsupported, use `speak` to explain the limitation.
7. If there is any safety uncertainty, use `ask_clarification` or `noop` instead of movement.

## Validation Checklist

Before final output, verify:

1. The output is valid JSON and nothing else.
2. `schema_version` is `"1.0"`.
3. `event_id` exactly matches the input.
4. `robot_id` exactly matches the input.
5. `confidence` is between 0 and 1.
6. `reasoning_summary` is brief and does not expose chain-of-thought.
7. `actions` is a non-empty array with at most 5 items.
8. Every action has a unique `action_id`.
9. Every action type is allowed by `references/action_schema.json`.
10. Navigation target is in the allowlist.
11. Turn direction is `left` or `right`, and degrees is one of `15`, `30`, `45`, `60`, or `90`.
12. If uncertain, clarification is used instead of movement.

Read `references/examples.md` for output examples. Read `references/mqtt_topics.md` only when checking the surrounding bridge/MQTT contract; the skill itself must not publish MQTT.
