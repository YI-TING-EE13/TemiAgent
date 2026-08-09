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

TemiAgent uses an app-owned custom wake word and then hands the speech session to Temi ASR. The default wake word is `小安`.

Current voice flow:

1. The Android app listens for `小安` through Android `SpeechRecognizer`.
2. When `小安` is detected, the app calls `robot.wakeup(Collections.singletonList(SttLanguage.ZH_TW))`.
3. Temi performs ASR and returns the final transcript through `Robot.AsrListener`.
4. The app publishes ASR text to the backend through MQTT.
5. The backend returns validated commands such as `temi/action/speak`.
6. The app executes TTS/navigation through Temi SDK.

This keeps Temi's ASR while avoiding normal use of Temi's built-in assistant wake word and response flow.

Accepted wake word phrases and near matches:

- `小安`
- `小安你好`
- `你好小安`
- `小恩`
- `小庵`
- `小鞍`
- `曉安`
- `曉恩`
- `曉庵`
- `校安`
- `笑安`

Current Android-side safeguards:

- `AndroidManifest.xml` declares `android.permission.RECORD_AUDIO` for the app-owned wake word listener.
- `MainActivity` disables the Temi built-in wake trigger with `robot.toggleWakeup(true)` in Kiosk mode.
- `AndroidManifest.xml` declares `com.robotemi.sdk.metadata.OVERRIDE_NLU`.
- `AndroidManifest.xml` declares `com.robotemi.sdk.metadata.OVERRIDE_CONVERSATION_LAYER`.
- `MainActivity` registers `Robot.NlpListener` so Temi Launcher can detect an active app-side NLU owner.
- When ASR arrives, the app calls `finishConversation()` and clears queued TTS before forwarding the event to the backend.
- Backend-driven TTS uses `TtsRequest.create(text, false, language)` so speech is not shown through Temi's conversation layer.
- Backend-driven TTS is also mirrored to a compact bottom subtitle overlay. The subtitle uses the active TTS request id and is cleared when that request completes or errors.
- The app ignores unsolicited Temi system wake events. Only app-triggered wakeups set the internal `acceptingTemiAsr` gate that allows ASR text to be forwarded to the backend.

Known limitation: on the currently tested Temi Launcher, `robot.toggleWakeup(true)` logs as requested but `robot.isWakeupDisabled()` can still report `false`, and the system phrase "Hi Temi" can still produce a wake event. The app defensively ignores those events, but the system UI may still briefly react.

The current wake word listener is implemented with Android `SpeechRecognizer`. It is good enough for testing but is not a true low-latency keyword spotting engine. For production-grade reliability, replace it with a dedicated local wake word engine and keep Temi only for ASR.

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

   On the robot UI, `MQTT: connected/total` shows how many configured MQTT brokers are currently connected. For example, `MQTT: 2/2` means both broker URLs above are connected and can receive ASR events or send robot actions.

2. Build the debug APK:

   ```powershell
   .\gradlew.bat :app:assembleDebug
   ```

   To benchmark the CPU-side 1280x720 YUV copy that runs before H.264 encoding:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\benchmark_yuv_copy.ps1 `
     -JavaHomePath 'C:\path\to\jdk-21'
   ```

   The benchmark verifies byte-for-byte output equality and reports median and
   p95 milliseconds per frame. Recorded results and measurement limits are in
   [`docs/performance/yuv-copy-optimization-2026-08-09.md`](docs/performance/yuv-copy-optimization-2026-08-09.md).

3. Connect to Temi:

   ```powershell
   adb connect <temi_ip>
   adb devices
   ```

4. Install the APK:

   ```powershell
   adb install -r app\build\outputs\apk\debug\app-debug.apk
   ```

5. Grant runtime permissions when deploying by ADB:

   ```powershell
   adb shell pm grant com.robotemi.agent android.permission.CAMERA
   adb shell pm grant com.robotemi.agent android.permission.RECORD_AUDIO
   ```

   The current Android `SpeechRecognizer` implementation uses Google RecognitionService on the tested Temi device. If the app logs `Hotword recognizer error: 9` or Google RecognitionService reports microphone permission denied, also grant:

   ```powershell
   adb shell pm grant com.google.android.googlequicksearchbox android.permission.RECORD_AUDIO
   adb shell appops set com.google.android.googlequicksearchbox RECORD_AUDIO allow
   ```

6. Restart the app:

   ```powershell
   adb shell am force-stop com.robotemi.agent
   adb shell am start -n com.robotemi.agent/.MainActivity
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

   When testing the Android app UI, send the command to one of the configured brokers, for example:

   ```powershell
   uv run python scripts\manual_tts.py --broker 192.168.50.233 --text "這是一段字幕測試。" --language ZH_TW
   ```

## Validation Checklist

- `adb devices` shows the Temi robot as connected.
- `.\gradlew.bat :app:assembleDebug` succeeds.
- `app\build\outputs\apk\debug\app-debug.apk` exists.
- Android app status shows connected WebSocket and MQTT endpoints.
- Android app status shows the expected MQTT count, such as `MQTT: 2/2` for two connected brokers.
- Logcat shows `Temi built-in wake trigger disabled; custom wake word is 小安`.
- Logcat shows `RecognitionService#onStartListening` while the app is idle.
- Saying `小安`, `小安你好`, or `你好小安` logs `Custom wake word matched`.
- Saying `Hi Temi` may still produce a Temi wake event, but the app should log `Ignoring Temi system wake word` unless it was triggered by the custom wake word flow.
- Backend receives `temi/event/asr`.
- Backend publishes `temi/action/speak`.
- Temi speaks only the backend answer in normal operation.
- During backend-driven TTS, a compact white subtitle appears near the bottom of the screen and disappears after TTS completion.

## Troubleshooting

- **No device in `adb devices`**: Confirm Temi developer mode, same network, and run `adb connect <temi_ip>`.
- **Backend does not receive ASR**: Check MQTT broker IP, port `1883`, firewall rules, and `mqtt.broker.urls`.
- **No video stream**: Check `ws.server.urls`, backend WebSocket listener port, and camera permission.
- **`MQTT: 0/N` or red MQTT status**: Check that each broker in `mqtt.broker.urls` is reachable from Temi on port `1883`.
- **TTS works but no subtitle appears**: Confirm the installed APK includes the subtitle overlay changes and that speech is triggered through `temi/action/speak` / `speakWithoutConversationLayer(...)`, not through a separate Temi system UI path.
- **ASR test says "連線逾時，請稍後再試"**: This is the app-side `WAITING` watchdog, not Temi's built-in ASR. It fires after 60 seconds if the backend does not publish a robot action, even if the backend received the ASR event.
- **Temi still speaks twice**: Confirm the installed APK includes the current manifest metadata, `MainActivity` NLU listener changes, and the `acceptingTemiAsr` gate. The expected path is app-owned hotword detection followed by Temi ASR only after `robot.wakeup(...)`; unsolicited Temi system wake events should be ignored by the app.
- **Custom wake word does not trigger**: Check logcat for `RecognitionService#onStartListening`. If `Hotword recognizer error: 9` appears, grant microphone permission to both `com.robotemi.agent` and `com.google.android.googlequicksearchbox`.
- **Custom wake word is inconsistent**: Prefer `小安你好` or `你好小安` over the two-character `小安`. Short Mandarin phrases are less reliable through Android `SpeechRecognizer`.
- **Build warnings about Java 8 target**: Current build still succeeds. The warning can be cleaned up later by updating Java toolchain or compile options.

Useful log command:

```powershell
adb logcat -d -v time | Select-String "MainActivity|AgentStateMachine|RecognitionService|Hotword|小安|Ignoring Temi"
```

## License

MIT License
