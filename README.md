# TemiAgent: Embodied AI Integration Framework

TemiAgent turns a Temi robot into a VLM-driven embodied AI agent. The Android app stays close to the robot hardware and Temi SDK, while the PC backend handles vision buffering, multimodal reasoning, and safe action routing.

## Key Features

- **Vision-language interaction**: Streams H.264 camera frames from the robot to a PC backend and pairs them with user ASR events.
- **Timestamp-aligned frame sampling**: Uses robot-side timestamps to sample visual context around the end of speech, such as `T-1000ms`, `T-500ms`, and `T`.
- **MQTT command bridge**: Sends ASR events from Android to the backend and receives validated robot actions such as speak, navigate, stop, and wakeup.
- **State-machine control**: Uses `AgentStateMachine` to manage `IDLE`, `WAKEUP_TRIGGERED`, `ASR_LISTENING`, `THINKING`, `WAITING`, and `EXECUTING` states.
- **Multicast telemetry**: Supports multiple WebSocket and MQTT backend endpoints for parallel backends or Hermes integration.
- **Temi built-in voice suppression**: The Android app declares NLU/conversation-layer ownership and suppresses Temi Launcher conversation output before playing backend-generated TTS.

## Architecture

### Android Client

Located in `app/`.

Responsibilities:

- Connect to the Temi SDK.
- Listen for wake word and ASR events.
- Stream camera frames through WebSocket.
- Publish ASR events through MQTT.
- Execute backend commands through Temi SDK APIs.
- Reduce duplicate speech by suppressing Temi built-in NLU/conversation output.

Important files:

- `app/src/main/java/com/robotemi/agent/MainActivity.java`
- `app/src/main/java/com/robotemi/agent/agent/AgentStateMachine.java`
- `app/src/main/java/com/robotemi/agent/mqtt/MqttTopics.java`
- `app/src/main/AndroidManifest.xml`

### PC Backend

Located in `temi_backend/`.

Responsibilities:

- Receive H.264 video frames.
- Maintain a timestamped rolling vision buffer.
- Receive ASR events over MQTT.
- Build multimodal prompts for a local OpenAI-compatible VLM endpoint.
- Validate and publish robot actions back to the Android app.

Important files:

- `temi_backend/src/temi_backend/vision_server.py`
- `temi_backend/src/temi_backend/mqtt_bridge.py`
- `temi_backend/src/temi_backend/agent_core.py`
- `skills/temi-robot-control/SKILL.md`

## Voice Ownership and Duplicate Reply Mitigation

TemiAgent still uses Temi's wake word and ASR pipeline, but the app now takes ownership of the NLU/conversation side so the robot does not normally speak both the built-in Temi answer and the backend-generated answer.

Current Android-side safeguards:

- `AndroidManifest.xml` declares `com.robotemi.sdk.metadata.OVERRIDE_NLU`.
- `AndroidManifest.xml` declares `com.robotemi.sdk.metadata.OVERRIDE_CONVERSATION_LAYER`.
- `MainActivity` registers `Robot.NlpListener` so Temi Launcher can detect an active app-side NLU owner.
- When ASR arrives, the app calls `finishConversation()` and clears queued TTS before forwarding the event to the backend.
- Backend-driven TTS uses `TtsRequest.create(text, false, language)` so speech is not shown through Temi's conversation layer.

If a Temi firmware or Launcher version still speaks a built-in reply before the app can suppress it, the next stronger approach is to bypass Temi ASR entirely and use an app-owned hotword/STT stack. That is more invasive, but it gives full control of the conversation lifecycle.

## Prerequisites

- JDK 21 or the JDK bundled with Android Studio.
- Android SDK configured in `local.properties`.
- A physical Temi robot with developer access.
- `adb` available on PATH.
- Python 3.10+ and `uv` for the PC backend.
- MQTT broker, such as Mosquitto, reachable from both the robot and PC.
- A local OpenAI-compatible VLM service, such as LM Studio or a Hermes-backed service.

## Android Setup

1. Configure `local.properties`:

   ```properties
   sdk.dir=C:\\path\\to\\Android\\Sdk
   ws.server.urls=ws://192.168.50.233:8080
   mqtt.broker.urls=tcp://192.168.50.233:1883
   mqtt.client.id=temi-agent
   ```

   Multiple endpoints are comma-separated:

   ```properties
   ws.server.urls=ws://192.168.50.233:8080,ws://192.168.50.236:8080
   mqtt.broker.urls=tcp://192.168.50.233:1883,tcp://192.168.50.236:1883
   ```

2. Build the debug APK:

   ```powershell
   .\gradlew.bat :app:assembleDebug
   ```

3. Connect to Temi:

   ```powershell
   adb connect <temi_ip>
   adb devices
   ```

4. Install the APK:

   ```powershell
   adb install -r app\build\outputs\apk\debug\app-debug.apk
   ```

## Backend Setup

1. Start the MQTT broker.

2. Install backend dependencies:

   ```powershell
   cd temi_backend
   uv sync
   ```

3. Start the backend:

   ```powershell
   uv run python -m temi_backend.agent_core
   ```

4. Optional manual TTS test:

   ```powershell
   uv run python scripts\manual_tts.py --broker 127.0.0.1 --text "Hello, I am Temi." --language EN_US
   ```

## Validation Checklist

- `adb devices` shows the Temi robot as connected.
- `.\gradlew.bat :app:assembleDebug` succeeds.
- `app\build\outputs\apk\debug\app-debug.apk` exists.
- Android app status shows connected WebSocket and MQTT endpoints.
- Backend receives `temi/event/asr`.
- Backend publishes `temi/action/speak`.
- Temi speaks only the backend answer in normal operation.

## Troubleshooting

- **No device in `adb devices`**: Confirm Temi developer mode, same network, and run `adb connect <temi_ip>`.
- **Backend does not receive ASR**: Check MQTT broker IP, port `1883`, firewall rules, and `mqtt.broker.urls`.
- **No video stream**: Check `ws.server.urls`, backend WebSocket listener port, and camera permission.
- **Temi still speaks twice**: Confirm the installed APK includes the current manifest metadata and `MainActivity` NLU listener changes. If the built-in reply happens before app callbacks, consider moving to app-owned hotword/STT.
- **Build warnings about Java 8 target**: Current build still succeeds. The warning can be cleaned up later by updating Java toolchain or compile options.

## License

MIT License
