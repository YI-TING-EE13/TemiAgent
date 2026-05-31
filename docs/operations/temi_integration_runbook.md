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
