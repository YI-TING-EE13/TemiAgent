# New Demo v1 Android Baseline

Milestone status:

```text
ANDROID_MEDIA_CAPABILITY_READY
CROSS_MACHINE_MEDIA_MILESTONE=PASS
```

## Documentation authority

- This document is authoritative for the current Android canonical-command
  behavior, validation, lifecycle semantics, verification evidence, and known
  limitations.
- `docs/play_media_contract.md` is authoritative for the exact `play_media`
  action and result contract.
- `README.md` is the user-facing build, deployment, and runtime guide.
- `AGENTS.md` is the operational handoff for future LAB606 agents,
  including ADB ownership and workspace rules.
- The root SDK README and generated `docs/sdk/**` pages describe the upstream
  Temi SDK; they are not the LAB606 App runbook.

## Scope and ownership

LAB606 owns the Temi hardware, Android App, ASR capture, camera streaming,
MQTT/WebSocket clients, TTS, media playback, local Android validation, command
execution, command results, APK build, and device deployment.

AI6 owns the canonical backend, Overview Adapter, Resident resolution, Care
Plan, Care Context, Hermes, Bridge, memory, trace, and action generation and
validation. Cross-machine integration follows:

```text
AI6 cmd/request
-> LAB606 validation and execution
-> LAB606 cmd/result
-> AI6 trace
```

Cross-machine acceptance proves that the two systems interoperate. It does not
transfer ownership of AI6 internals into this repository.

## Current Android and deployment identity

- Android package: `com.robotemi.agent`
- Version name: `1.0.0`
- Version code: `1`
- Temi wireless ADB target: `192.168.50.204:5555`
- Verified media APK SHA-256:
  `E2DD1CABE7032DD73B65AA6CB451F48906FAA87F7633D7C7739AC5971DA94A11`

The hash identifies the APK used for this milestone. It is a verification
baseline, not a permanent release identifier; any rebuild can produce a new
hash and must be recorded separately.

The portable clean-build configuration commits AndroidX, Jetifier, and Gradle
JVM arguments. JDK and Android SDK locations remain external, and
`local.properties` remains ignored and machine-local.

## Network topology

The App retains both configured backend endpoint pairs:

```text
MQTT
tcp://192.168.50.233:1883
tcp://192.168.50.236:1883

WebSocket
ws://192.168.50.233:8080
ws://192.168.50.236:8080
```

`.233` completed LAB606-side command and media acceptance. After the AI6
canonical stack started, real connections to `.236:1883` and `.236:8080` were
both established and passed cross-machine integration. `MQTT: 2/2` is the
healthy target state. Earlier observations that `.236` refused connections
described a service-down moment and must not be treated as a permanent
topology limitation.

## Canonical command contract and validation

```text
request: temi/{robot_id}/cmd/request
result:  temi/{robot_id}/cmd/result
```

Android parses and validates the complete envelope before hardware dispatch.
Validation covers `schema_version`, `command_id`, `event_id`, `robot_id`, a
non-empty `actions` array of at most five items, and action-specific fields.
Malformed commands execute no actions. When command and event correlation are
available, Android publishes a correlated failure result; otherwise it logs an
explicit rejection.

Android action validation includes:

- `speak` and `ask_clarification`: non-empty text, maximum 500 characters.
- `turn`: direction `left` or `right`; degrees `15`, `30`, `45`, `60`, or `90`.
- `navigate`: target `home_base`, `kitchen`, `living_room`, or `meeting_room`.
- `play_media`: `elderly_hand_exercise` or `elderly_leg_exercise` only.
- `stop`: stops movement and TTS.
- `noop`: records completion without invoking hardware.

Unsupported, non-object, or invalid motion actions are rejected before
`robot.turnBy(...)` or `robot.goTo(...)` can be called.

## Idempotency semantics

- A synchronized, thread-safe process-memory registry retains up to 1,024
  unique `command_id` values without eviction.
- The first delivery executes once.
- A pending duplicate executes zero additional hardware or media action and is
  queued for the identical eventual result.
- A completed duplicate executes nothing and immediately replays the exact
  cached result payload.
- When capacity is exhausted, unseen commands fail with
  `command_registry_capacity_exhausted`; older IDs are not evicted.
- The registry is process-lifetime only. It is not persistent exactly-once and
  does not survive App restart.

## TTS lifecycle

Canonical speech uses Temi terminal callbacks:

```text
received
-> validated
-> robot.speak(...)
-> pending
-> Temi callback
   COMPLETED -> completed
   ERROR     -> failed
```

`robot.speak(...)` dispatch is not completion. Later actions in the same
command remain serialized behind pending speech. Real Temi acceptance verified
audible output, callback-grounded completion, and duplicate TTS suppression.

## Exercise media capability and lifecycle

The exact action contract is in `docs/play_media_contract.md`. Android maps the
two allowlisted IDs directly to bundled `res/raw` files; caller-supplied URLs,
filesystem paths, content URIs, and unknown IDs are rejected.

Both bundled videos use H.264 Constrained Baseline, 960 x 540 resolution,
15 fps, and a 10-second duration. Playback follows:

```text
received
-> prepared/started
-> completed | failed | cancelled
```

- Completion is impossible before the `STARTED` state.
- Playback errors produce `failed`.
- The on-screen stop button produces `cancelled`.
- A stale completion callback after cancellation is ignored.
- Duplicate command IDs do not replay video.
- Command, event, action, and media correlation is retained in results.

## Verification evidence

### JVM and build

- JVM tests: `36/36 PASS` with zero failures, errors, or skipped tests.
- Android assemble, Java compile, unit-test, and lint tasks: `PASS`.
- Current lint baseline: one pre-existing ChromeOS camera feature error and
  23 warnings. No media correctness error was introduced.

### Real Temi

- Audible canonical TTS and terminal-callback result: `PASS`.
- Duplicate TTS suppression: `PASS`.
- Invalid turn and navigate rejection without hardware dispatch: `PASS`.
- Hand exercise: `RECEIVED -> STARTED -> COMPLETED`.
- Leg exercise: `RECEIVED -> STARTED -> COMPLETED`.
- Stop control: `RECEIVED -> STARTED -> CANCELLED`, with no later completion.
- Unknown media: rejected with no playback.
- No App crash during acceptance.

### Cross-machine AI6 x LAB606

`CROSS_MACHINE_MEDIA_MILESTONE=PASS` covers:

- Father daily hand exercise.
- Mother daily leg exercise.
- Mother post-dialysis hand exercise.
- Unknown Resident fail-safe behavior.
- Duplicate media suppression.
- TTS regression.
- Real `.236` MQTT and WebSocket integration.

These entries are integration evidence only; Resident resolution, care policy,
Bridge behavior, and trace internals remain AI6-owned.

## Exact remaining limitations

- Command deduplication is process-lifetime only and not restart-persistent.
- The registry accepts at most 1,024 unique command IDs per App process.
- A canonical speech command can remain pending indefinitely if Temi never
  supplies a terminal TTS callback; there is no separate TTS terminal timeout.
- Navigation arrival and physical turn completion are not observed; accepted
  actions currently report API dispatch rather than physical completion.
- The current Demo does not use autonomous navigation.
- The pre-existing ChromeOS camera hardware lint finding remains.
- Android has no Resident selector UI; Resident resolution is AI6-owned.
- Android does not yet publish the full canonical ASR-final event with
  synchronized frame paths; the compatibility text event remains available.
- Media input is deliberately non-extensible at runtime: no arbitrary source
  is allowed, and only two bundled exercise IDs are supported.
- The legacy `temi/action/*` compatibility topics retain their pre-existing
  handlers and are outside the canonical-path milestone.
