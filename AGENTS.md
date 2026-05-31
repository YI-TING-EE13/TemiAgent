# AGENTS.md

This file is the handoff guide for future coding agents working on this TemiAgent project.

## Project Identity

- Current working project: `F:\sdk\TemiAgent`
- GitHub/backup working tree used previously: `F:\TemiAgent`
- Android package: `com.robotemi.agent`
- Main Android entry point: `app/src/main/java/com/robotemi/agent/MainActivity.java`
- Temi ADB target used in local testing: `192.168.50.205:5555`
- Default backend endpoints are configured in `local.properties`, which is intentionally ignored by Git.

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

From `F:\sdk\TemiAgent`:

```powershell
.\gradlew.bat :app:assembleDebug
adb connect 192.168.50.205:5555
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell pm grant com.robotemi.agent android.permission.CAMERA
adb shell pm grant com.robotemi.agent android.permission.RECORD_AUDIO
adb shell pm grant com.google.android.googlequicksearchbox android.permission.RECORD_AUDIO
adb shell appops set com.google.android.googlequicksearchbox RECORD_AUDIO allow
adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity
```

Expected build state: `:app:assembleDebug` succeeds. Warnings about Java 8 source/target and deprecated APIs are currently non-blocking.

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
  - `triggerCustomWakeWord()`
  - `wakeupWithoutBuiltInResponse()`
  - `onWakeupWord(...)`
  - `onAsrResult(...)`
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

## Git and Workspace Notes

- `F:\sdk` has unrelated changes from the broader SDK workspace. Do not reset or clean it.
- `F:\sdk\TemiAgent` is the active working copy used for implementation and robot deployment.
- `F:\TemiAgent` is the separate GitHub/backup working tree. If asked to push, sync `F:\sdk\TemiAgent` into `F:\TemiAgent` while preserving `F:\TemiAgent\.git` and excluding local/build artifacts.
- Do not commit `local.properties`, `.gradle`, `.idea`, `build`, APK files, cache folders, or debug frames.

Recommended sync command for the GitHub working tree:

```powershell
robocopy F:\sdk\TemiAgent F:\TemiAgent /MIR /XD .git .gradle .idea build .venv venv __pycache__ .pytest_cache debug_frames /XF local.properties *.apk *.ap_ *.dex *.class /R:2 /W:2
```

Then run Git from `F:\TemiAgent`. If Git reports dubious ownership, use a one-shot safe directory override instead of changing global config:

```powershell
git -c safe.directory=F:/TemiAgent -C F:\TemiAgent status --short --branch
```
