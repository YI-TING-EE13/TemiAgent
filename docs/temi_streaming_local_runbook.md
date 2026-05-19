# Temi Streaming Local Runbook

This is the local version of `temi_streaming_manual.md` for this machine.

## Local Paths And IPs

- Workspace: `/TemiAgent`
- Backend: `/TemiAgent/temi_backend`
- PC IP: `192.168.50.236`
- Temi IP: `192.168.50.205`
- MQTT broker: `tcp://192.168.50.236:1883`
- Video receiver: `ws://192.168.50.236:8080`
- Android package: `com.robotemi.agent`

## Current Verification Status

Verified on this machine:

- ADB: `192.168.50.205:5555 device`
- Android package installed: `com.robotemi.agent`
- Camera permission: granted
- MQTT from Temi to PC: connected to `tcp://192.168.50.236:1883`
- MQTT command PC to Temi: `temi/action/speak` received and executed
- Wakeup command: `temi/action/wakeup` triggers `ASR_LISTENING`
- WebSocket video: Temi connects to `192.168.50.236:8080`
- Video packets: Temi logs `Video packets sent`
- Backend keyframes: saved into `/TemiAgent/temi_backend/debug_frames`
- LMStudio/VLM route: ASR + frames produces a speak action
- End-to-end test: user speech -> ASR MQTT -> keyframes -> VLM -> MQTT speak -> Temi speaks
- Overview adapter path: legacy `temi/event/asr` -> `temi/temi-01/asr/final` with three image paths -> HermesTemiBridge -> `temi/temi-01/cmd/request` -> legacy `temi/action/speak` -> `temi/temi-01/cmd/result`
- Overview mock Bridge path after Temi restart: passed
- Overview real Hermes path after Temi restart: passed functionally, but Hermes latency was about 97 seconds

Observed successful real ASR examples:

```text
temi/event/asr {"text":"你聽得到我講話","language":"SYSTEM","timestamp_ms":1778574627720}
temi/action/speak {"text":"是的，我聽得到您說話。", ...}

temi/event/asr {"text":"我在做手勢","language":"SYSTEM","timestamp_ms":1778574674637}
temi/action/speak {"text":"我看到了，你在比耶！", ...}
```

## Installed Tools

The machine now has:

- `adb`
- `mosquitto`
- `mosquitto_sub`
- `mosquitto_pub`
- `ip`
- `nc`
- `nmap`

## Start PC Services

```bash
cd /TemiAgent
./tools/start_temi_pc_services.sh
```

This starts:

- Mosquitto on `0.0.0.0:1883`
- `temi-backend` vision WebSocket server on `0.0.0.0:8080`
- legacy MQTT ASR listener on `temi/event/asr`

If `./tools/check_temi_connection.sh` shows `8080` refused, the backend is not running. Start it again with the command above.

## Check Connectivity

```bash
cd /TemiAgent
./tools/check_temi_connection.sh
```

Healthy ADB should show:

```text
192.168.50.205:5555 device
```

Current observed blocker:

```text
192.168.50.205:5555 offline
```

`offline` means the Temi ADB daemon is reachable, but this PC is not authorized or the Temi ADB daemon is stuck.

## Fix ADB Offline

On Temi:

1. Unlock/open the Android screen.
2. Look for an `Allow USB debugging?` prompt.
3. Check `Always allow from this computer`.
4. Tap `Allow`.

If no prompt appears:

1. Open Android developer options on Temi.
2. Toggle USB debugging off and on.
3. Toggle wireless debugging / network ADB off and on, if available.
4. Reboot Temi if needed.
5. Run:

```bash
adb disconnect 192.168.50.205:5555
adb kill-server
adb start-server
adb connect 192.168.50.205:5555
adb devices -l
```

## After ADB Works

Start the installed app:

```bash
adb shell am start -n com.robotemi.agent/.MainActivity
```

Watch logs:

```bash
adb logcat '*:I' | grep -E 'MainActivity|WebSocketClient|MqttManager|CameraManager|AgentStateMachine'
```

Monitor MQTT:

```bash
mosquitto_sub -h 192.168.50.236 -p 1883 -t '#' -v
```

Send a legacy speak command:

```bash
cd /TemiAgent/temi_backend
uv run python scripts/manual_tts.py --broker 192.168.50.236 --port 1883 --text '這是 Temi MQTT 測試' --language ZH_TW
```

Expected Temi-side log:

```text
MqttManager: Connected successfully.
MainActivity: ACTION_SPEAK: "這是 Temi MQTT 測試"
```

Expected video-side log:

```text
Vision stream connected.
```

## Overview Integration Notes

The current Android app still uses legacy topics:

```text
temi/event/asr
temi/action/speak
temi/action/navigate
temi/action/wakeup
```

To test the `Overview.md` contract without changing the Android app, run the adapter:

```bash
cd /TemiAgent/temi_backend
uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker 192.168.50.236 \
  --port 1883 \
  --vision-port 8080 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared
```

Mock Bridge:

```bash
cd /TemiAgent/hermes_temi_bridge
MQTT_BROKER_HOST=192.168.50.236 \
MQTT_BROKER_PORT=1883 \
HERMES_INVOKE_MODE=mock \
HERMES_MOCK_RESPONSE_TEXT='重啟後 Overview 快速測試成功。' \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
LOG_DIR=/TemiAgent/logs/overview_bridge_mock_after_restart \
uv run --extra mqtt hermes-temi-bridge --env-file /TemiAgent/hermes_temi_bridge/.env.example
```

Real Hermes Bridge:

```bash
cd /TemiAgent/hermes_temi_bridge
MQTT_BROKER_HOST=192.168.50.236 \
MQTT_BROKER_PORT=1883 \
HERMES_INVOKE_MODE=cli \
HERMES_CLI_COMMAND='hermes -z {prompt}' \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
HERMES_TIMEOUT_SECONDS=120 \
LOG_DIR=/TemiAgent/logs/overview_bridge_real_after_restart \
uv run --extra mqtt hermes-temi-bridge --env-file /TemiAgent/hermes_temi_bridge/.env.example
```

Latest real Hermes result:

```text
ASR: 你現在可以聽到我嗎
Hermes latency: 96940 ms
Temi spoke: 可以，我能聽到您說話。
```

This proves the full `Overview.md` chain works, but real Hermes is currently slower than the Android app's 15-second `WAITING` watchdog. For responsive demos, use mock Bridge or the legacy `temi_backend` LMStudio route; for the Overview architecture, optimize Hermes latency or increase the Android watchdog.

## Resident Hermes latency experiment

The first real Hermes path used `HERMES_INVOKE_MODE=cli`, which starts a new `hermes -z`
process for every ASR event. To remove this cold-start cost, run Hermes as a resident
local HTTP worker:

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md
```

`--skill-path` can be repeated. The resident worker preloads the skills in the
order provided, so `temi-robot-control` should stay first as the robot action
contract, followed by care memory and Home-ESI policy.

For the care-assistant profile/memory path, add:

```bash
  --hermes-home /root/.hermes/profiles/care-assistant \
  --enable-memory \
  --toolsets memory
```

Keep memory disabled for the fastest smoke tests; enable it when demonstrating
Hermes' persistent memory behavior.

Health check:

```bash
curl -s http://127.0.0.1:8765/health
```

Then start the Bridge with HTTP mode:

```bash
cd /TemiAgent/hermes_temi_bridge
MQTT_BROKER_HOST=192.168.50.236 \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
HERMES_INVOKE_MODE=http \
HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
HERMES_TIMEOUT_SECONDS=180 \
LOG_DIR=/TemiAgent/logs/overview_bridge_resident \
uv run --extra mqtt hermes-temi-bridge --env-file /TemiAgent/hermes_temi_bridge/.env.example
```

Expected result: the Bridge still publishes `temi/temi-01/cmd/request`, but the
Hermes process is already loaded. Compare `hermes_latency_ms` in
`/TemiAgent/logs/overview_bridge_resident/*.jsonl` with the earlier 96,940 ms CLI result.

Validated resident results on this machine:

- First resident smoke invocation: about 19,886 ms.
- Second warm resident smoke invocation: about 6,979 ms.
- Bridge `--validate-json` through resident HTTP mode: about 8,384 ms.

The resident worker auto-reexecs itself with `/TemiAgent/hermes-agent/venv/bin/python3`
when launched with system `python3`, so Hermes runtime dependencies such as `httpx`
are available.

## Android Source Status

This copied workspace currently does not contain the Android Gradle project:

- no `gradlew`
- no `settings.gradle`
- no `app/build/outputs/apk/debug/app-debug.apk`
- no `AndroidManifest.xml`

Because of that, this machine cannot rebuild or reinstall the Android app yet. Once the Android project is copied into `/TemiAgent`, create `/TemiAgent/local.properties` with:

```properties
ws.server.urls=ws://192.168.50.236:8080
mqtt.broker.urls=tcp://192.168.50.236:1883
mqtt.client.id=temi-agent
```

Then build/install with:

```bash
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
