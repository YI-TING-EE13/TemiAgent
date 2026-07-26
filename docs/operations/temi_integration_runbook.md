# Temi + Hermes Integration Runbook

This runbook follows `docs/architecture/project_overview.md`: validate each layer first, then connect the full system.

## 1. Unit Tests

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests

cd /TemiAgent/temi_backend
uv run pytest
```

Expected result: all tests pass.

## 2. Local Mock E2E Without Hardware

This tests:

- ASR event validation
- three image paths
- Bridge path translation
- mock Hermes JSON output
- action validation
- command request publishing
- duplicate `event_id` protection
- command result logging

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

Expected result: JSON with `"status": "ok"`.

Inspect the generated trace with:

```bash
cd /TemiAgent
python3 tools/show_temi_trace.py --log-dir <log_dir_from_result> --latest
python3 tools/show_temi_trace.py --log-dir <log_dir_from_result> --latest --full
python3 tools/show_temi_trace.py --log-dir <log_dir_from_result> --latest --json
```

`--json` writes clean machine-readable JSON to stdout. Default output is a compact timeline; `--full` prints stage payload detail.

## 3. MQTT + Bridge With Mock Hermes

Terminal A:

```bash
mosquitto -c mqtt/mosquitto.conf
```

Terminal B:

```bash
cd hermes_temi_bridge
HERMES_INVOKE_MODE=mock \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/shared/temi \
TRACE_ENABLED=true \
DEBUG_TRACE_FULL=false \
TRACE_INCLUDE_ASR_TEXT=true \
uv run hermes-temi-bridge --env-file .env
```

Terminal C:

```bash
./tools/subscribe_cmd_request.sh
```

Terminal D:

```bash
BRIDGE_ROOT=/TemiAgent/temi_shared ./tools/publish_mock_asr_event.sh
```

Expected result: Terminal C receives `temi/temi-01/cmd/request` with a `speak` action.

## 4. Hermes CLI Smoke Test

```bash
hermes --help
hermes -z '請只回覆 JSON：{"ok": true}'
```

Expected result: Hermes starts and returns without provider/config errors. If this fails, fix Hermes provider/model setup before enabling `HERMES_INVOKE_MODE=cli`.

## 5. Bridge + Real Hermes

Start MQTT, subscribe to command requests, then run:

```bash
cd hermes_temi_bridge
HERMES_INVOKE_MODE=cli \
HERMES_CLI_COMMAND="hermes -z {prompt}" \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/shared/temi \
uv run hermes-temi-bridge --env-file .env
```

Publish the mock event:

```bash
BRIDGE_ROOT=/TemiAgent/temi_shared ./tools/publish_mock_asr_event.sh
```

Expected result: Bridge validates Hermes JSON and publishes `temi/temi-01/cmd/request`.

## Bridge Trace Reference

Bridge trace records live in `{LOG_DIR}/{event_id}.jsonl`, with an append-only `{LOG_DIR}/_index.jsonl`.
`_index.jsonl` may contain multiple records for the same `event_id`; use the CLI viewer's timeline summary for operational status, because a later duplicate attempt can append `ignored` after a completed event.

Record schema:

```text
schema_version, timestamp, run_id, seq, level, component,
event_id, robot_id, source_type, record_type, stage, status,
duration_ms, payload
```

Fixed stage enum:

```text
event_received
input_validated
care_context_built
hermes_request_prepared
hermes_invocation_finished
hermes_output_validated
memory_actions_completed
command_request_published
command_result_received
event_completed
event_failed
duplicate_event_ignored
```

Important env config:

```text
TRACE_ENABLED=true
DEBUG_TRACE_FULL=false
TRACE_INCLUDE_ASR_TEXT=true
TRACE_RUN_ID=
TRACE_MAX_FIELD_CHARS=2000
```

Trace config:

- `TRACE_ENABLED`: enable or disable Bridge trace logging. When `false`, Bridge processing still runs without trace files.
- `DEBUG_TRACE_FULL`: when `true`, stores full prompt, full care context, full raw Hermes output, and raw inbound payload for short local debugging.
- `TRACE_INCLUDE_ASR_TEXT`: when `false`, ASR text is stored only as excerpt/hash/length in summary mode.
- `TRACE_RUN_ID`: optional run id override; empty value generates one automatically.
- `TRACE_MAX_FIELD_CHARS`: excerpt length limit used by the shared sanitizer.

Summary mode stores prompt/raw output/care context as SHA-256 hash, length, excerpt, and `truncated`. Full prompt, full care context, and full raw Hermes output are stored only when `DEBUG_TRACE_FULL=true`. Traces never store raw image bytes.

Common viewer commands:

```bash
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --event-id <event_id>
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --full
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --json
```

Common summary fields:

- `completed`: the event reached the normal terminal stage.
- `failed`: the event reached `event_failed`; inspect `failed_stage`, `error_code`, `error_message`, and fallback fields.
- `duplicate_attempts`: count of later duplicate attempts; duplicates do not overwrite completed/failed status.
- `command_result`: latest command result status appended to the event timeline.
- `late_result`: command result arrived after `event_completed` or `event_failed`.

Retention / cleanup:

- Normal Demo runs should use summary mode (`DEBUG_TRACE_FULL=false`).
- Full debug mode is for short local tests only; do not attach or preserve full debug logs long term before de-identification.
- Clean up old `LOG_DIR` folders regularly, especially logs containing user speech, raw model output, or identifiable filesystem paths.

## 6. Temi Hardware Checks

These need the robot and Android app online.

Monitor ASR:

```bash
mosquitto_sub -h <broker_ip> -p 1883 -t "temi/+/asr/final" -v
```

Send a direct speak command:

```bash
mosquitto_pub -h <broker_ip> -p 1883 -t "temi/temi-01/cmd/request" -m '{
  "schema_version": "1.0",
  "command_id": "cmd_manual_001",
  "event_id": "evt_manual_001",
  "robot_id": "temi-01",
  "source": "manual_test",
  "created_at_ms": 1778499001200,
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "Temi 指令整合測試成功",
      "language": "zh-TW"
    }
  ]
}'
```

Expected result: Temi speaks and publishes `temi/temi-01/cmd/result`.

## Schemas And Skill

- Canonical Bridge schemas: `/TemiAgent/hermes_temi_bridge/schemas/`
- Documentation copies: `/TemiAgent/docs/schemas/`
- Hermes skill source: `/TemiAgent/hermes-agent/skills/temi-robot-control/`
- Root skill mirror: `/TemiAgent/hermes-skills/temi-robot-control/`

Contract-only schema validation（不啟動 service、不控制 hardware）：

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest tests.test_cross_service_contract_schemas -v
```

Identity、video lifecycle、care report 與 report interaction 目前只有 schema contract。
不得把上述 test 當成 Android、Hermes video tool、MQTT live flow、report generation 或
real-device acceptance。實作與 rollout gate 見
[canonical cross-service contract](../architecture/canonical_cross_service_contract.md)。
