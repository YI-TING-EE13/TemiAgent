# Temi Backend

> This is the repository's local/reference backend. The deployed canonical
> backend, Resident resolution, Care Plan, Care Context, Hermes, Bridge,
> memory, trace, and action generation/validation are AI6-owned. Current
> Android command semantics are documented in
> `../docs/new_demo_v1_android_baseline.md`; the exact media contract is
> `../docs/play_media_contract.md`.

Portable Python backend and verification suite for the TemiAgent robot.

The backend receives Temi's WebSocket H.264 video stream, listens for ASR events over MQTT, sends aligned speech-and-vision context to a local OpenAI-compatible VLM endpoint, and publishes safe robot actions back to Temi over MQTT.

## Project Layout

- `src/temi_backend/` - importable backend package.
- `tests/` - hardware-free pytest unit tests.
- `scripts/` - manual integration checks that require MQTT, Temi, or video streaming.
- `debug_frames/` - generated ASR-aligned frame snapshots, ignored by git.

## Requirements

- Python 3.12 or newer.
- `uv` package manager.
- Mosquitto or another MQTT broker reachable by the PC and Temi.
- LM Studio, Hermes, or another OpenAI-compatible local VLM endpoint.
- Temi Android client configured to publish MQTT events and stream video to this backend.

## Setup On A New Computer

```powershell
cd TemiAgent\temi_backend
uv sync --group dev
uv run pytest
```

If `uv` is not installed yet, install it first from the official Astral documentation or with your team's approved package manager.

## Configuration

The backend works with defaults for local development. Override these environment variables when needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEMI_MQTT_BROKER` | `127.0.0.1` | MQTT broker host. |
| `TEMI_MQTT_PORT` | `1883` | MQTT broker port. |
| `TEMI_MQTT_CLIENT_ID` | `temi-backend-brain` | Backend MQTT client id. |
| `TEMI_VISION_HOST` | `0.0.0.0` | WebSocket bind host. |
| `TEMI_VISION_PORT` | `8080` | WebSocket bind port. |
| `TEMI_LM_BASE_URL` | `http://localhost:1234/v1` | OpenAI-compatible VLM base URL. |
| `TEMI_LM_API_KEY` | `lm-studio` | API key placeholder for local VLM servers. |
| `TEMI_LM_MODEL` | `local-model` | Model name sent to the VLM endpoint. |
| `TEMI_SKILLS_PROMPT_FILE` | auto-discovered | Optional explicit path to the Temi skill prompt. |
| `TEMI_DEBUG_FRAMES_DIR` | `debug_frames` | Directory for saved ASR-aligned frames. |
| `TEMI_ENABLE_DEBUG_FRAMES` | `true` | Save or skip debug frames. |

## Run The Backend

```powershell
uv run temi-backend
```

Equivalent source wrapper:

```powershell
uv run python main.py
```

Expected ports:

- MQTT broker: `tcp://<backend-ip>:1883`
- Video stream receiver: `ws://<backend-ip>:8080`
- Local VLM: `http://localhost:1234/v1`

## Automated Tests

Run the unit test suite without Temi hardware:

```powershell
uv run pytest
```

These tests validate MQTT payloads, VLM action routing, timestamp-aligned vision buffering, and the `AgentCore` orchestration path with fake dependencies.

## Manual Verification

Use these scripts after the MQTT broker and Android Temi client are configured.

Monitor ASR events from Temi:

```powershell
uv run python scripts\manual_asr_monitor.py --broker 127.0.0.1 --port 1883
```

Send one TTS command:

```powershell
uv run python scripts\manual_tts.py --broker 127.0.0.1 --text "Hello, I am Temi." --language EN_US
```

Send one navigation command:

```powershell
uv run python scripts\manual_navigate.py --broker 127.0.0.1 --target home_base
```

Display the incoming camera stream:

```powershell
uv run python scripts\manual_video_receiver.py --host 0.0.0.0 --port 8080
```

## API Notes

The public Python APIs are documented with professional English docstrings:

- `AgentConfig` loads runtime configuration and skill prompts.
- `MqttBridge` owns MQTT subscriptions and command publishing.
- `VisionBuffer` stores timestamped frames and returns asymmetric keyframes.
- `VisionServer` receives and decodes Temi WebSocket H.264 frames.
- `SkillRouter` parses VLM JSON actions and executes only supported robot commands.
- `AgentCore` coordinates ASR, visual context, VLM calls, and action routing.

## Troubleshooting

- `ConnectionRefusedError` from MQTT: confirm the broker is running and reachable from both PC and Temi.
- No ASR events: confirm the Android app points to this PC's broker IP and that Temi is on the same network.
- No video frames: confirm the Android app uses `ws://<backend-ip>:8080` and Windows Firewall allows inbound traffic.
- VLM errors: start LM Studio or your OpenAI-compatible server and confirm `TEMI_LM_BASE_URL`.
- Empty `debug_frames/`: verify that ASR events and video frames arrive with comparable Temi timestamps.
