# AGENTS.md

This file is the handoff guide for future coding agents working on this TemiAgent project.

## Project Identity

- Active Android baseline branch: `new-demo-v1`
- Android module location: `TemiAgent/` inside the repository checkout
- Android package: `com.robotemi.agent`
- Current package version: `1.0.0` (`versionCode 1`)
- Main Android entry point: `app/src/main/java/com/robotemi/agent/MainActivity.java`
- Temi ADB target used in local testing: `192.168.50.204:5555`
- Current verified media APK SHA-256:
  `E2DD1CABE7032DD73B65AA6CB451F48906FAA87F7633D7C7739AC5971DA94A11`
- Default backend endpoints are configured in `local.properties`, which is intentionally ignored by Git.

The APK hash is the verified milestone baseline, not a permanent identifier.
Recompute and document it after every rebuild used for acceptance.

## Documentation Authority

- `README.md`: user-facing Android build, deployment, runtime, and
  troubleshooting guide.
- `docs/new_demo_v1_android_baseline.md`: authoritative canonical-command
  behavior, validation, lifecycle, evidence, and limitations.
- `docs/play_media_contract.md`: exact `play_media` action/result contract.
- This `AGENTS.md`: operational handoff, ADB ownership, and workspace safety.
- Repository-root SDK documentation and generated `docs/sdk/**` pages describe
  the upstream Temi SDK and must not be rewritten as App documentation.

## Current Voice Architecture

The current implementation uses option 2 from the design discussion:

1. The app owns the custom wake word.
2. Temi still provides ASR after the app explicitly calls `robot.wakeup(...)`.
3. Backend reasoning and responses are handled over MQTT/WebSocket.

The default wake word is the Mandarin phrase `小安`. In source code it is stored as Unicode escapes:

```java
private static final String CUSTOM_WAKE_WORD = "\u5c0f\u5b89";
```

Accepted hotword variants are defined in `CUSTOM_WAKE_WORD_VARIANTS`:

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

The listener uses Android `SpeechRecognizer`. This is a pragmatic test implementation, not a production-grade keyword spotting engine. Reliability improves when users say `小安你好` or `你好小安` instead of only `小安`.

Backend-driven TTS is displayed as a compact subtitle near the bottom of the Android UI. The subtitle is driven by `speakWithoutConversationLayer(...)`, tracked by the active `TtsRequest` id, and hidden when that request reaches `COMPLETED` or `ERROR`.

## Temi System Wake Behavior

`MainActivity.configureTemiVoiceOwnership()` calls:

- `robot.toggleWakeup(true)`
- `robot.setAsrLanguages(Collections.singletonList(SttLanguage.ZH_TW))`

On the tested Temi Launcher, `robot.isWakeupDisabled()` can still report `false` after `toggleWakeup(true)`, and the system wake phrase can still produce `onWakeupWord(...)`. The app therefore uses a defensive gate:

- `acceptingTemiAsr = true` is set only inside `wakeupWithoutBuiltInResponse()`.
- `onWakeupWord(...)` ignores unsolicited Temi system wake events.
- `onAsrResult(...)` ignores ASR results unless `acceptingTemiAsr` is true.

Do not remove this gate unless Temi Launcher behavior is verified to be different on the target robot.

## Permissions Required for Testing

The app requires:

- `android.permission.CAMERA`
- `android.permission.RECORD_AUDIO`

Grant after install:

```powershell
adb shell pm grant com.robotemi.agent android.permission.CAMERA
adb shell pm grant com.robotemi.agent android.permission.RECORD_AUDIO
```

The current `SpeechRecognizer` implementation binds to Google RecognitionService on the tested robot. If logcat shows microphone permission errors for `com.google.android.googlequicksearchbox`, grant:

```powershell
adb shell pm grant com.google.android.googlequicksearchbox android.permission.RECORD_AUDIO
adb shell appops set com.google.android.googlequicksearchbox RECORD_AUDIO allow
```

## Build and Deploy

From the active checkout's `TemiAgent` directory:

```powershell
.\gradlew.bat :app:assembleDebug
adb kill-server
adb start-server
adb connect 192.168.50.204:5555
adb devices -l
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell pm grant com.robotemi.agent android.permission.CAMERA
adb shell pm grant com.robotemi.agent android.permission.RECORD_AUDIO
adb shell pm grant com.google.android.googlequicksearchbox android.permission.RECORD_AUDIO
adb shell appops set com.google.android.googlequicksearchbox RECORD_AUDIO allow
adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity
```

Expected build state: `:app:assembleDebug` succeeds. Warnings about Java 8 source/target and deprecated APIs are currently non-blocking.

### ADB ownership and handoff

Temi wireless ADB may be held by only one computer at a time. Do not let AI6
and LAB606 compete for the same device connection.

```text
LAB606 Android/device-side work
-> LAB606 holds ADB

LAB606 completes device work
-> adb disconnect 192.168.50.204:5555

AI6 integration/E2E work
-> AI6 connects to 192.168.50.204:5555
```

When receiving ownership, connect explicitly and confirm that
`192.168.50.204:5555` is in `device` state. When handing ownership to AI6,
disconnect explicitly; do not merely close a terminal.

## Current Network Topology

Keep both endpoint pairs unless the system topology is intentionally changed:

```text
MQTT:     tcp://192.168.50.233:1883,tcp://192.168.50.236:1883
WebSocket: ws://192.168.50.233:8080,ws://192.168.50.236:8080
```

`.233` passed LAB606-side acceptance. After the AI6 canonical stack started,
real `.236:1883` MQTT and `.236:8080` WebSocket connections were established
and passed cross-machine integration. `MQTT: 2/2` is the healthy target state;
do not preserve an old claim that `.236` is permanently unavailable.

## UI Status Indicators

- `MQTT: connected/total` is the count of connected MQTT brokers versus configured brokers from `mqtt.broker.urls`.
- Example: `MQTT: 2/2` means both configured brokers are connected. Text ASR events are published to connected brokers, and Hermes command requests such as `temi/{robot_id}/cmd/request` can be received.
- The top-left status text shows the hotword/listening state, such as `Waiting for "小安"`.
- Backend TTS subtitles appear above the bottom status area with small white text and should clear automatically after speech ends.

## Timeout Behavior

The `WAITING` watchdog in `AgentStateMachine` is currently 60 seconds. If ASR is published but no backend action arrives over MQTT before the watchdog fires, the app says `連線逾時，請稍後再試` and returns to `IDLE`. This timeout is app-side behavior, not a Temi built-in ASR timeout.

## Canonical Command Runtime

The active contract is:

```text
temi/{robot_id}/cmd/request
-> Android validation and serialized execution
-> temi/{robot_id}/cmd/result
```

Envelope validation covers schema version, command ID, event ID, robot ID, and
the actions array. Action validation includes speech, motion, and media fields.
Invalid motion is rejected before `robot.turnBy(...)` or `robot.goTo(...)`.

Motion allowlists:

- turn direction: `left`, `right`
- turn degrees: `15`, `30`, `45`, `60`, `90`
- navigate target: `home_base`, `kitchen`, `living_room`, `meeting_room`

Idempotency uses a synchronized process-lifetime registry of 1,024 unique
command IDs. A pending duplicate executes no additional hardware action and
receives the eventual result; a completed duplicate receives the exact cached
payload. The registry is not persistent or restart-safe, and unseen commands
are rejected after capacity is exhausted.

Canonical TTS stays pending after `robot.speak(...)`. Only a Temi
`COMPLETED` callback produces `completed`; an `ERROR` callback produces
`failed`. There is currently no separate timeout if no terminal callback ever
arrives.

`play_media` accepts only `elderly_hand_exercise` and
`elderly_leg_exercise`. Playback is callback-grounded as
`received -> prepared/started -> completed | failed | cancelled`. The stop
button cancels playback, stale completion after cancellation is ignored, and a
duplicate command ID does not replay video.

## Validation Commands

Check device:

```powershell
adb devices
```

Check permissions:

```powershell
adb shell dumpsys package com.robotemi.agent | findstr /C:"RECORD_AUDIO" /C:"CAMERA"
adb shell appops get com.robotemi.agent RECORD_AUDIO
adb shell appops get com.google.android.googlequicksearchbox RECORD_AUDIO
```

Check hotword logs:

```powershell
adb logcat -d -v time | Select-String "MainActivity|AgentStateMachine|RecognitionService|Hotword|小安|Ignoring Temi|Custom wake word matched"
```

Expected logs while idle:

- `Temi built-in wake trigger disabled; custom wake word is 小安`
- `RecognitionService#onStartListening`

Expected logs when custom wake word works:

- `Custom wake word matched from phrase: ...`
- `Custom wake word triggered: 小安`
- `Temi ASR wakeup accepted: ...`

Expected logs when system wake phrase is ignored:

- `Ignoring Temi system wake word: ...`

## Important Code Locations

- `MainActivity.java`
  - `CUSTOM_WAKE_WORD`
  - `CUSTOM_WAKE_WORD_VARIANTS`
  - `containsCustomWakeWord(...)`
  - `normalizeHotwordText(...)`
  - `speakWithoutConversationLayer(...)`
  - subtitle helpers: `showSubtitle(...)`, `hideSubtitleForRequest(...)`, `hideSubtitle()`
  - `triggerCustomWakeWord()`
  - `wakeupWithoutBuiltInResponse()`
  - `onWakeupWord(...)`
  - `onAsrResult(...)`
  - `handleCommandRequest(...)`
  - `executeHermesAction(...)`
- `AgentStateMachine.java`
  - state definitions
  - 60 second watchdog
  - `interrupt()`
- `AndroidManifest.xml`
  - `RECORD_AUDIO`
  - `CAMERA`
  - `com.robotemi.sdk.metadata.KIOSK`
  - `com.robotemi.sdk.metadata.OVERRIDE_NLU`
  - `com.robotemi.sdk.metadata.OVERRIDE_CONVERSATION_LAYER`
- `temi_backend/src/temi_backend/`
  - PC-side VLM/MQTT/video orchestration.

## Known Issues

- Android `SpeechRecognizer` is not a true wake word engine. It has restart gaps and weaker accuracy on very short phrases.
- `小安` alone is less reliable than `小安你好` or `你好小安`.
- Temi system wake cannot be fully disabled on the currently tested Launcher, so ignore-gating is required.
- If the activity is stopped and resumed, ensure camera resources are recreated. `MainActivity` currently sets `cameraManager = null` after shutdown and recreates it in `startAllServices()`.
- Source files may contain older mojibake comments from prior encoding issues. Avoid touching unrelated comment blocks unless necessary.
- Command deduplication is process-lifetime only, has a 1,024-ID capacity, and
  does not survive restart.
- Navigation arrival and physical turn completion are not observed; the
  canonical result records dispatch rather than physical completion.
- The current Demo does not use autonomous navigation.
- Android has no Resident selector UI and does not yet publish the full
  canonical ASR-final event with synchronized frame paths.
- Media is intentionally limited to two bundled exercise IDs; arbitrary URLs,
  filesystem paths, and content URIs are rejected.
- Lint retains one pre-existing ChromeOS camera hardware finding and 23
  warnings.

## Current Verification Milestone

- JVM tests: `36/36 PASS`.
- Android build: `PASS`.
- Real Temi audible/callback-grounded TTS: `PASS`.
- Duplicate TTS and invalid-motion rejection: `PASS`.
- Hand video, leg video, stop/cancel, unknown-media rejection: `PASS`.
- AI6 x LAB606 media integration, duplicate suppression, Resident scenarios,
  TTS regression, and real `.236` connectivity:
  `CROSS_MACHINE_MEDIA_MILESTONE=PASS`.

LAB606 owns Android/device execution. AI6 owns Resident resolution, care
context, Hermes, Bridge, memory, trace, and action generation/validation.

## Git and Workspace Notes

- `F:\sdk` can contain unrelated changes from the broader SDK workspace. Do not reset or clean it.
- Work may use a dedicated Git worktree. Always confirm the Git top level,
  branch, HEAD, and `git status --short` before editing.
- The active Hermes command contract is `temi/{robot_id}/cmd/request` -> Android execution -> `temi/{robot_id}/cmd/result`. The legacy `temi/action/*` topics are still subscribed for manual scripts and the original backend.
- The Android app still publishes `temi/event/asr` as a text-only compatibility event. Visual Hermes events require a PC-side frame assembler to publish `temi/{robot_id}/asr/final` with frame paths under the shared Temi directory.
- `F:\TemiAgent` was historically used as a separate GitHub/backup working
  tree. Do not reuse the old split-tree procedure unless the current checkout
  and Git ownership have been verified explicitly.
- Do not commit `local.properties`, `.gradle`, `.idea`, `build`, APK files, cache folders, or debug frames.

Historical split-tree sync command, only after verifying that this layout is
still intentionally in use:

```powershell
robocopy F:\sdk\TemiAgent F:\TemiAgent /MIR /XD .git .gradle .idea build .venv venv __pycache__ .pytest_cache debug_frames /XF local.properties *.apk *.ap_ *.dex *.class /R:2 /W:2
```

Then run Git from `F:\TemiAgent`. If Git reports dubious ownership, use a one-shot safe directory override instead of changing global config:

```powershell
git -c safe.directory=F:/TemiAgent -C F:\TemiAgent status --short --branch
```
