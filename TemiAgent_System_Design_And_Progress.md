# TemiAgent System Design and Current Progress

> Last verified: 2026-07-22
> Android package: `com.robotemi.agent`
> Current milestone: `CROSS_MACHINE_MEDIA_MILESTONE=PASS`

## System boundary

LAB606 owns the Temi hardware and Android/device side:

- ASR capture and camera streaming
- MQTT and WebSocket clients
- Android canonical validation
- TTS, media, and safe hardware execution
- command results
- APK build and deployment

AI6 owns the canonical backend and reasoning side:

- Overview Adapter and Resident resolution
- Care Plan and Care Context
- Hermes and Bridge
- memory and trace
- action generation and backend validation

The integration boundary is intentionally narrow:

```text
AI6 temi/{robot_id}/cmd/request
-> LAB606 validation and execution
-> LAB606 temi/{robot_id}/cmd/result
-> AI6 trace
```

## Android voice and vision flow

1. Android listens for the custom Mandarin wake word `小安` using
   `SpeechRecognizer`.
2. A matched wake word causes the App to call `robot.wakeup(...)`; unsolicited
   Temi system wake events remain gated.
3. Temi supplies final ASR to Android.
4. Android publishes the compatibility text ASR event over MQTT and streams
   timestamped H.264 camera frames over WebSocket.
5. The AI6/PC-side stack can assemble canonical ASR-final events with
   synchronized `T-1000`, `T-500`, and `T` frame references.
6. AI6 publishes a canonical command request; Android validates and executes
   it and returns a correlated result.

Android does not yet publish the full canonical ASR-final event with frame
paths by itself. Visual assembly remains PC/AI6-side.

## Network topology

The App preserves both backend endpoint pairs:

```text
MQTT
tcp://192.168.50.233:1883
tcp://192.168.50.236:1883

WebSocket
ws://192.168.50.233:8080
ws://192.168.50.236:8080
```

`.233` passed LAB606-side acceptance. After the AI6 canonical stack was
started, `.236:1883` and `.236:8080` both established successfully.
`MQTT: 2/2` is the healthy target state.

## Canonical safety and idempotency

Android validates schema version, command ID, event ID, robot ID, actions
array, and action-specific fields before dispatch. Motion allowlists are:

- turn direction: `left`, `right`
- turn degrees: `15`, `30`, `45`, `60`, `90`
- navigation target: `home_base`, `kitchen`, `living_room`, `meeting_room`

Invalid motion is rejected before Temi movement APIs are called.

Command idempotency uses a synchronized process-lifetime registry with a
capacity of 1,024 unique command IDs. A pending duplicate performs zero
additional execution and receives the eventual result. A completed duplicate
receives the exact cached result. The registry is not restart-persistent.

## TTS lifecycle

Canonical TTS is callback-grounded:

```text
received
-> validated
-> robot.speak(...)
-> pending
-> COMPLETED -> completed
   ERROR     -> failed
```

API dispatch is never reported as completion. Real Temi acceptance verified
audible output, terminal-callback correlation, and duplicate suppression.

## Exercise media

Android supports a single canonical `play_media` action with two IDs:

- `elderly_hand_exercise`
- `elderly_leg_exercise`

Both videos are bundled in `app/src/main/res/raw`, use H.264 Constrained
Baseline at 960 x 540 and 15 fps, and run for 10 seconds. Caller-provided URLs,
filesystem paths, content URIs, and unknown IDs are rejected.

Playback follows:

```text
received
-> prepared/started
-> completed | failed | cancelled
```

Completion cannot occur before start. The stop button returns `cancelled`, a
stale completion callback after cancellation is ignored, and duplicate command
IDs do not replay media.

## Verified progress

### Local verification

- Android assemble and Java compile: PASS
- JVM tests: 36/36 PASS
- Media APK SHA-256:
  `E2DD1CABE7032DD73B65AA6CB451F48906FAA87F7633D7C7739AC5971DA94A11`

The hash identifies the accepted APK artifact and is not a permanent release
identifier.

### Real Temi

- canonical audible TTS: PASS
- callback-grounded TTS result: PASS
- duplicate TTS suppression: PASS
- invalid turn/navigation rejection: PASS
- hand exercise playback: PASS
- leg exercise playback: PASS
- stop/cancel without later completion: PASS
- unknown media rejection: PASS
- no crash during acceptance: PASS

### Cross-machine AI6 x LAB606

- Father daily hand exercise: PASS
- Mother daily leg exercise: PASS
- Mother post-dialysis hand exercise: PASS
- unknown Resident fail-safe: PASS
- duplicate media suppression: PASS
- TTS regression: PASS

## Deployment and ADB ownership

The current Temi wireless ADB target is `192.168.50.204:5555`. Only one
computer may hold wireless ADB at a time:

```text
LAB606 device work
-> LAB606 holds ADB
-> adb disconnect 192.168.50.204:5555
-> AI6 integration work connects
```

Build and deployment details are maintained in `README.md` and `AGENTS.md`.

## Remaining limitations

- Command deduplication does not survive App restart and is limited to 1,024
  unique IDs per process.
- Canonical TTS has no separate timeout if Temi never supplies a terminal
  callback.
- Navigation arrival and physical turn completion are not observed; the
  current Demo does not use autonomous navigation.
- Android has no Resident selector UI; Resident resolution is AI6-owned.
- Android does not yet publish the complete canonical ASR-final event.
- Only the two bundled exercise media IDs are accepted.
- Android `SpeechRecognizer` is a pragmatic wake-word implementation, not a
  production keyword-spotting engine.
- The pre-existing ChromeOS camera lint finding remains.
