---
name: temi-care-memory
description: Guide Hermes in using Bridge-managed structured care memory for Temi home-care events, reminders, daily state, event logs, summaries, and synchronization with Hermes memory providers. Use with temi-robot-control and temi-home-esi. This skill defines planning and JSON action intent only; it must not directly write files, publish MQTT, or control Temi hardware.
---

# Temi Care Memory Skill

## Purpose

Use this skill when Hermes handles a Temi home-care interaction that may need resident profile context, reminders, event logging, daily state updates, abnormal event records, or daily summaries.

This skill defines how Hermes should reason about care memory and what JSON actions it may request. Hermes must not directly edit memory files, call the Temi SDK, publish MQTT, or bypass HermesTemiBridge. The Bridge or an approved tool layer performs all actual writes.

## Memory Layers

Use three memory layers with clear responsibility:

1. Hermes builtin memory stores stable, compact background facts such as resident preferences and communication style.
2. Hermes Holographic provider stores searchable local facts and care summaries.
3. Structured JSON / JSONL files are the authority for reminders, daily state, event logs, abnormal events, and generated summaries.

Structured care memory is expected at:

```text
memory/
  profile.json
  daily_state.json
  reminders.json
  event_log.jsonl
  summaries/
  abnormal_events/
```

## Planning Rules

1. Treat structured memory supplied by HermesTemiBridge as authoritative for current reminders and daily state.
2. Use Hermes memory/provider recall as background context, not as the source of truth for reminder completion or event audit.
3. For meaningful care interactions, request `log_event`.
4. For completed reminders, request `mark_reminder_done` and `log_event`.
5. For changes to stable profile facts, request `update_memory` and include a short reason.
6. For end-of-demo or explicit summary requests, request `generate_summary`.
7. For high-risk events, request `notify_caregiver_mock` only as a mock/demo action and also request `log_event`.
8. Never claim a real caregiver, clinic, emergency service, or 119 has been contacted unless the Bridge result explicitly says so.

## Recommended Action Intent

Hermes output should remain JSON-only and should be compatible with the active Bridge schema. Memory-related actions are intent for Bridge-managed execution:

- `log_event`
- `update_memory`
- `set_reminder`
- `mark_reminder_done`
- `generate_summary`
- `notify_caregiver_mock`

Robot-facing actions such as `speak` and `ask_clarification` are still governed by `temi-robot-control`.

## Data Hygiene

Keep care-memory action payloads concise:

- Include `event_type`, `home_esi_level`, `risk_reason`, and `outcome` when relevant.
- Do not include private chain-of-thought.
- Do not store raw image data in memory actions.
- Prefer image paths or event IDs over duplicating large payloads.
- Store only the minimum information needed for demo audit and later care summary.

Read `references/structured_memory_contract.md` for the structured memory contract.
