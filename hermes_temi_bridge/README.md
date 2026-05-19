# Hermes Temi Bridge

`hermes_temi_bridge` connects Temi Android ASR events to Hermes Agent decisions.
It receives lightweight MQTT events, validates the three synchronized image references,
invokes Hermes with the `temi-robot-control` skill, validates JSON actions, then publishes
safe Temi command requests.

## Architecture

```text
Temi Android Client
  └─ publish temi/{robot_id}/asr/final
       ↓
HermesTemiBridge
  ├─ validate ASR event and image files
  ├─ translate /var/lib/temi_shared paths to /shared/temi paths
  ├─ invoke Hermes CLI with temi-robot-control instructions
  ├─ parse and validate Hermes JSON actions
  └─ publish temi/{robot_id}/cmd/request
       ↓
Temi Android Client
  └─ publish temi/{robot_id}/cmd/result
       ↓
HermesTemiBridge logs result
```

## MQTT Topics

- Subscribe: `temi/+/asr/final`
- Subscribe: `temi/+/cmd/result`
- Publish: `temi/{robot_id}/cmd/request`

## Payload Examples

ASR event:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "conversation_id": "conv_20260511_a",
  "type": "asr.final",
  "timestamp_ms": 1778499000200,
  "speech_end_ts_ms": 1778499000123,
  "language": "zh-TW",
  "asr": { "text": "幫我看看桌上的東西是什麼", "confidence": 0.92 },
  "vision": {
    "sampling_policy": "T-1000,T-500,T",
    "frames": [
      {
        "name": "t_minus_1000",
        "ts_ms": 1778498999123,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t_minus_1000.jpg",
        "mime_type": "image/jpeg"
      },
      {
        "name": "t_minus_500",
        "ts_ms": 1778498999623,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t_minus_500.jpg",
        "mime_type": "image/jpeg"
      },
      {
        "name": "t",
        "ts_ms": 1778499000123,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t.jpg",
        "mime_type": "image/jpeg"
      }
    ]
  }
}
```

Command request:

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_evt_20260511_000001_1778499001200",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "source": "hermes_temi_bridge",
  "created_at_ms": 1778499001200,
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上可能有一個杯子和一台筆電。",
      "language": "zh-TW"
    }
  ]
}
```

## Docker Volumes

Mount the same host directory into both containers:

```yaml
services:
  hermes:
    image: hermes-agent:latest
    volumes:
      - ./temi_shared:/shared/temi

  hermes-temi-bridge:
    build: ./hermes_temi_bridge
    volumes:
      - ./temi_shared:/var/lib/temi_shared
    environment:
      MQTT_BROKER_HOST: mosquitto
      MQTT_BROKER_PORT: "1883"
      TEMI_SHARED_BRIDGE_PATH: /var/lib/temi_shared
      TEMI_SHARED_HERMES_PATH: /shared/temi
```

## Environment

Copy `.env.example` to `.env` and adjust:

```env
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
ROBOT_ID_ALLOWLIST=temi-01
TEMI_SHARED_BRIDGE_PATH=/var/lib/temi_shared
TEMI_SHARED_HERMES_PATH=/shared/temi
HERMES_CLI_COMMAND=hermes -z {prompt}
HERMES_MOCK_RESPONSE_TEXT=這是 Bridge mock 測試
HERMES_TIMEOUT_SECONDS=60
MAX_ACTIONS_PER_EVENT=5
MAX_IMAGE_SIZE_MB=8
EVENT_DEDUP_TTL_SECONDS=600
```

## Start Bridge

```powershell
uv venv .venv
uv pip install -e '.[mqtt]'
uv run hermes-temi-bridge --env-file .env
```

If your Hermes invocation uses a longer command, set `HERMES_CLI_COMMAND`, for example:

```env
HERMES_CLI_COMMAND=hermes chat --toolsets skills
```

The bridge appends `-q "<prompt>"` unless the command contains `{prompt}`.
For Hermes Agent v0.12, prefer `hermes -z {prompt}` because oneshot mode prints only the final response.

For MQTT and Bridge integration tests that should not call a real model, set:

```env
HERMES_INVOKE_MODE=mock
```

Mock mode returns a deterministic `speak` action using `HERMES_MOCK_RESPONSE_TEXT`.

For lower-latency real Hermes experiments, run the resident Hermes server once:

```powershell
python ../tools/hermes_resident_server.py --host 127.0.0.1 --port 8765
```

Then start the Bridge in HTTP mode:

```env
HERMES_INVOKE_MODE=http
HERMES_HTTP_URL=http://127.0.0.1:8765/invoke
```

HTTP mode avoids starting a new `hermes -z` process for every ASR event. The resident server keeps a Hermes `AIAgent` instance loaded and preloads the `temi-robot-control` skill into the system prompt. When launched with system `python3`, the resident server reexecs into `/TemiAgent/hermes-agent/venv/bin/python3` if that interpreter exists.

Latest local measurements:

- CLI Hermes mode: about `96,940 ms`.
- Resident smoke invocation after warmup: about `6,979 ms`.
- Bridge validation through resident HTTP mode: about `8,384 ms`.

## Install Skill

The version-controlled skill lives at:

```text
../skills/temi-robot-control/
```

Install or mirror it to Hermes' skill directory:

```powershell
New-Item -ItemType Directory -Force "$HOME\.hermes\skills"
Copy-Item -Recurse -Force ..\skills\temi-robot-control "$HOME\.hermes\skills\temi-robot-control"
```

## Test

This project uses only the Python standard library for unit tests.

```powershell
uv venv .venv
uv run python -m unittest discover -s tests
Remove-Item -Recurse -Force .venv
```

## Troubleshooting

- `paho-mqtt is required`: install runtime MQTT support with `uv pip install -e '.[mqtt]'`.
- `missing_image`: Temi published an image path the bridge container cannot read.
- `path is outside bridge shared root`: check `TEMI_SHARED_BRIDGE_PATH`.
- `invalid_hermes_json`: Hermes returned Markdown, prose, or malformed JSON.
- `navigation_target_not_allowed`: update the allowlist in `action_validator.py` and the skill schema only after the Temi map location exists.
- Duplicate event ignored: the event id is still inside `EVENT_DEDUP_TTL_SECONDS`.
