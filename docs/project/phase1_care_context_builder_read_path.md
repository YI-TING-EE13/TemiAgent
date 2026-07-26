# Phase 1 Structured Care Memory Read Path

Last updated: 2026-06-10

## Purpose

Phase 1 adds a Bridge-side structured memory read path for the TemiAgent / Hermes care assistant Demo. The goal is to let Hermes see compact, evidence-based care context before producing a JSON action plan, without giving Hermes direct ownership of structured care memory.

The accepted design boundary is:

- Hermes can propose.
- Bridge validates and executes.
- Structured memory remains authoritative.
- CareContextBuilder only reads structured memory.
- Memory writes still go through `action_validator` and `StructuredMemoryStore`.

This read path was added because the P2 write path was already able to record care events, reminder completion, summaries, and mock notifications, but Hermes did not automatically receive `profile`, `reminders`, `daily_state`, or recent events before each turn.

## Architecture

Runtime flow:

```text
ASR / abnormal event
  -> HermesTemiBridge validates event and image paths
  -> CareContextBuilder reads structured memory
  -> Bridge attaches care_context to HermesRequest
  -> build_asr_prompt() / build_abnormal_prompt() injects <care_context>
  -> Hermes outputs JSON action plan
  -> Bridge validates robot_actions / memory_actions
  -> Bridge dispatches robot_actions and executes memory_actions
```

Implementation anchors:

- `hermes_temi_bridge/src/hermes_temi_bridge/care_context_builder.py`
- `hermes_temi_bridge/src/hermes_temi_bridge/hermes_client.py`
- `hermes_temi_bridge/src/hermes_temi_bridge/main.py`
- `hermes_temi_bridge/src/hermes_temi_bridge/config.py`

`HermesRequest.care_context` is optional. If care context is disabled or unavailable, the Bridge can still invoke Hermes using the existing event prompt.

For deterministic demo and regression validation, see `docs/project/phase1_care_context_demo_package.md` and `tools/phase1_care_context_demo_runner.py`.
For architecture/report material drafting, see `docs/project/p2_structured_memory_phase1_report_materials.md`.

## Memory Authority

Hermes does not directly own structured care memory. It should not freely edit `memory/*.json` or `memory/*.jsonl`.

Authority split:

| Component | Responsibility |
|---|---|
| `CareContextBuilder` | Read-only context construction from structured memory. |
| Hermes | Understand context and propose JSON actions. |
| `action_validator.py` | Validate action plan schema and allowed action types. |
| `StructuredMemoryStore` | Execute approved memory actions and persist JSON / JSONL changes. |
| Temi / MQTT | Receive only robot-facing actions, never memory actions. |

Hermes built-in memory and external memory providers must not be treated as the authority for reminders, daily state, event audit, or abnormal-event records. They may be used later for stable background preferences, but not as the source of truth for care state.

## CareContext Contents

`care_context` is JSON serialized into the prompt between XML-like delimiters:

```text
<care_context>
{ JSON here }
</care_context>
```

The prompt explicitly states that the block is Bridge-provided context and not current user speech.

Current fields:

- `schema_version`
- `generated_at` using timezone-aware UTC ISO 8601
- `event`
- `resident`
- `active_reminders`
- `daily_state`
- `relevant_events`
- `read_status`
- `memory_policy`

Memory sources:

| care_context field | Source |
|---|---|
| `resident` | `memory/profile.json` |
| `active_reminders` | `memory/reminders.json`, active / pending only |
| `daily_state` | `memory/daily_state.json` |
| `relevant_events` | `memory/event_log.jsonl` and selected `memory/abnormal_events/*.json` |
| `read_status` | Builder read warnings and skipped JSONL count |
| `memory_policy` | Hard-coded Phase 1 safety policy |

Error handling is conservative:

- missing file -> safe empty default plus warning
- malformed JSON -> skip file plus warning
- malformed JSONL line -> skip line and increment `skipped_event_log_lines`
- unexpected read error -> minimal context plus warning
- missing `resolved` -> `unknown`
- `unknown` is not treated as unresolved

## Retrieval Strategy

Phase 1 uses deterministic rule-based retrieval only. It does not use embeddings, graph memory, Hermes MemoryProvider, or semantic search.

Risk ordering is explicit:

```text
L1 > L2 > L3 > Normal
```

Keyword groups include health discomfort, medication, hydration, fall/emergency, and gesture/vision terms. Event snippets are bounded to avoid oversized prompts.

Selection is diversity-aware rather than pure global score sorting. With `max_events=5`, the builder reserves room for:

- `current_intent` matched events, such as prior L2 discomfort when current ASR is `我又不舒服`
- high-risk safety events, such as L1 fall or abnormal events
- reminder-related events when medication or hydration context is relevant
- recent fallback events by score and recency

This prevents repeated discomfort recall from being buried by multiple L1 abnormal events while still preserving safety context.

Important `match_reasons` examples:

```text
current_intent:health_discomfort
keyword:health_discomfort
risk:L2
high_risk:L1
```
