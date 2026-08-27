# Phase 1 CareContext Demo Package

> Status: HISTORICAL Demo package. It contains no current production readiness
> or live device/provider evidence.

## Purpose

This demo package validates the Phase 1 structured care memory read path for TemiAgent / Hermes care assistant. It focuses on memory continuity and Bridge-controlled state handling: Hermes receives compact `care_context`, proposes a JSON action plan, and the Bridge validates and executes robot / memory actions.

The package is deterministic and demo-safe. It uses temporary structured memory, fake image files, mock Hermes output, and mock MQTT. It does not contact a live broker, robot, LM Studio, or Hermes runtime.

## What It Demonstrates

- First discomfort writes an L2 event.
- Repeated discomfort recalls the prior event ID through `care_context.relevant_events`.
- Medication reminder completion updates structured memory through the existing Bridge write path.
- The abnormal route receives `care_context` and uses image evidence file paths instead of raw image bytes.

## What It Does Not Demonstrate

- No clinical diagnosis.
- No medically validated triage.
- No real emergency notification.
- No real robot hardware.
- No live MQTT broker.
- No live Hermes / LM Studio inference.
- No embedding retrieval, graph retrieval, or Hermes MemoryProvider integration.
- No new memory write actions.

## Command

Preferred container command:

```bash
docker exec yiting.TemiAgent_gpu_all bash -lc '
cd /TemiAgent
python3 tools/phase1_care_context_demo_runner.py
'
```

Local command from the project root, if the Python environment is already available:

```bash
python3 tools/phase1_care_context_demo_runner.py
```

Full JSON output:

```bash
python3 tools/phase1_care_context_demo_runner.py --json
```

Save JSON report:

```bash
python3 tools/phase1_care_context_demo_runner.py --output /tmp/phase1_report.json
```

Keep temporary artifacts for inspection:

```bash
python3 tools/phase1_care_context_demo_runner.py --keep-artifacts
```

The short output has this shape:

```text
PHASE1_DEMO_STATUS=PASS
artifact_root=/tmp/phase1-live-validation-xxxx
artifact_retained=false
case1=PASS
case2=PASS
case3=PASS
case4=PASS
mock_hermes=true
mock_mqtt=true
production_memory_used=false
```

When artifacts are not kept, `artifact_root` is reported for traceability but is removed before the process exits. Use `--keep-artifacts` or `--output` when you need to inspect details after the run.

## Temporary Seed Memory

Every run creates an isolated workspace like this:

```text
/tmp/phase1-live-validation-xxxx/
  memory/
    profile.json
    reminders.json
    daily_state.json
    event_log.jsonl
  temi_shared/
    events/...
    abnormal_events/...
  logs/
```

Seed memory includes:

- `profile.json`: synthetic resident `王先生`, gender `male`, language `zh-TW`.
- `reminders.json`: active `rem_morning_medication` and active `rem_hydration`.
- `daily_state.json`: normal baseline, active reminder IDs, empty recent event IDs.
- `event_log.jsonl`: initially empty.

The runner does not read or write production `/TemiAgent/memory/*`.

## Scenario Checks

### Case 1: First Discomfort

Input:

```text
我不舒服
```

Expected behavior:

- `care_context.resident.display_name == 王先生`.
- `active_reminders` include medication and hydration reminders.
- `relevant_events` is initially empty.
- Hermes mock returns `home_esi_level == L2`.
- Hermes actions include `log_event`.
- Bridge writes `evt_live_discomfort_001` to temporary `event_log.jsonl`.
- The written event risk is `L2`.

### Case 2: Repeated Discomfort

Input:

```text
我又不舒服
```

Expected behavior:

- `care_context.relevant_events` contains `evt_live_discomfort_001`.
- `match_reasons` include `current_intent:health_discomfort` or `keyword:health_discomfort`.
- Prompt includes `<care_context>...</care_context>`.
- Prompt keeps `Current user ASR text:` separate from the context block.
- Hermes mock `risk_reason` cites `evt_live_discomfort_001`.

### Case 3: Medication Reminder Done

Input:

```text
我吃過藥了
```

Expected behavior:

- Pre-action `care_context.active_reminders` includes `rem_morning_medication`.
- Hermes mock proposes `mark_reminder_done`.
- Bridge updates `rem_morning_medication` from `active` to `completed`.
- `last_completed_at` is present.
- `rem_hydration` remains `active`.
- Next-turn `CareContextBuilder` output excludes `rem_morning_medication` from `active_reminders`.

### Case 4: Abnormal Route CareContext

Input fixture:

```text
source = perception.abnormal
action_name = fall_like_motion
fake evidence frame paths in temp dir
```

Expected behavior:

- `care_context.event.source == perception.abnormal`.
- Resident, reminders, and daily state are present.
- Relevant prior events are available if selected by deterministic retrieval.
- Evidence uses file paths only, not raw bytes.
- Mock MQTT is used; no live broker or hardware is contacted.

## Safety Boundary

The runner is intentionally bounded:

- Mock Hermes only.
- Mock MQTT only.
- Temporary memory only.
- Fake image files only.
- No production `memory/` access.
- No real robot command execution.
- No Phase 2 memory features.

The production write path remains unchanged:

```text
Hermes JSON action plan
  -> action_validator
  -> StructuredMemoryStore
```

## Acceptance Criteria

The run passes only if all scenario assertions pass:

- Case 1 writes an L2 `log_event` for first discomfort.
- Case 2 retrieves and cites the previous L2 event ID.
- Case 3 completes the medication reminder and removes it from next-turn active reminders.
- Case 4 builds abnormal-route `care_context` using file-path evidence and mock MQTT only.

A failed assertion appears in the JSON report under:

```text
cases[].assertions[]
```

Each assertion includes a `name`, `status`, and optional `detail`.

## Troubleshooting

If the container is not running:

```bash
docker ps --filter name=yiting.TemiAgent_gpu_all
```

If Python cannot import `hermes_temi_bridge`, run from the project root or use the container command above. The runner adds `hermes_temi_bridge/src` and `tools` to `sys.path` automatically.

If `uv` is missing, this runner can still be executed with `python3` because it uses the repository source tree directly. The broader bridge test suite still uses:

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

If a case fails, rerun with artifacts and JSON:

```bash
python3 tools/phase1_care_context_demo_runner.py --keep-artifacts --output /tmp/phase1_report.json
```

Then inspect:

```text
/tmp/phase1-live-validation-xxxx/phase1_care_context_demo_report.json
/tmp/phase1-live-validation-xxxx/memory/
/tmp/phase1-live-validation-xxxx/logs/
```
