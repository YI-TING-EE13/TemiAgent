# Canonical Exercise Media Contract

Status:

```text
ANDROID_MEDIA_CAPABILITY_READY
CROSS_MACHINE_MEDIA_MILESTONE=PASS
```

AI6 has emitted this contract successfully in real cross-machine acceptance.
Android remains the authority for local allowlist validation and playback;
AI6 remains the authority for Resident resolution, care context, action
generation, Bridge validation, and trace.

## Action

The Android hardware owner accepts one canonical media action:

```json
{
  "action_id": "act_media_001",
  "type": "play_media",
  "media_id": "elderly_hand_exercise"
}
```

Required fields are non-empty strings: `action_id`, `type`, and `media_id`.
`type` must equal `play_media`.

Allowed media IDs:

- `elderly_hand_exercise`
- `elderly_leg_exercise`

Android maps each ID directly to a bundled `res/raw` H.264 MP4. URLs,
filesystem paths, content URIs, and any media ID outside the allowlist are
rejected before playback.

Bundled media properties:

| Media ID | Codec/profile | Resolution | Frame rate | Duration |
|---|---|---:|---:|---:|
| `elderly_hand_exercise` | H.264 Constrained Baseline | 960 x 540 | 15 fps | 10 seconds |
| `elderly_leg_exercise` | H.264 Constrained Baseline | 960 x 540 | 15 fps | 10 seconds |

## Lifecycle and results

Playback follows:

```text
received -> prepared/started -> completed | failed | cancelled
```

- No `completed` result is produced before `VideoView` reports preparation and
  the media framework later calls the completion listener.
- Decode or playback errors produce `failed` with a concrete error string.
- The on-screen stop control produces `cancelled`. A later stale completion
  callback is ignored.
- Existing process-lifetime `command_id` deduplication prevents duplicate media
  execution and replays the identical eventual or cached command result.
- Command, event, action, and media identifiers remain correlated in the
  terminal result.

## Example request

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_media_001",
  "event_id": "evt_media_001",
  "robot_id": "temi-01",
  "source": "hermes_temi_bridge",
  "created_at_ms": 1783956000000,
  "actions": [
    {
      "action_id": "act_media_001",
      "type": "play_media",
      "media_id": "elderly_hand_exercise"
    }
  ]
}
```

## Example success result

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_media_001",
  "event_id": "evt_media_001",
  "robot_id": "temi-01",
  "status": "success",
  "finished_at_ms": 1783956010000,
  "results": [
    {
      "action_id": "act_media_001",
      "type": "play_media",
      "media_id": "elderly_hand_exercise",
      "status": "completed"
    }
  ]
}
```

## Example failure result

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_media_invalid_001",
  "event_id": "evt_media_invalid_001",
  "robot_id": "temi-01",
  "status": "failed",
  "finished_at_ms": 1783956000100,
  "results": [
    {
      "action_id": "act_media_invalid_001",
      "type": "play_media",
      "status": "failed",
      "error": "media_id_not_allowed"
    }
  ],
  "error": "media_id_not_allowed"
}
```

## Cross-machine acceptance

Real AI6 x LAB606 acceptance passed for Father daily hand exercise, Mother
daily leg exercise, Mother post-dialysis hand exercise, unknown Resident
fail-safe behavior, duplicate media suppression, and TTS regression.

```text
AI6 cmd/request
-> LAB606 Android validation and playback
-> LAB606 cmd/result
-> AI6 trace
```

This contract does not permit arbitrary media sources and does not modify the
shared MQTT envelope. Cross-machine acceptance does not make AI6 implementation
details LAB606-owned.
