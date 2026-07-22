# Temi Skills

Last reviewed: 2026-07-22

## Scope and authority

`skills/` is the TemiAgent repository's reviewable mirror of Temi-oriented
Hermes instructions and references. It is not the authority for the deployed
AI6 production stack. AI6 owns Resident resolution, Care Plan, Care Context,
Hermes, Bridge, memory, trace, and action generation/validation.

Do not treat a checked-in `SKILL.md` or JSON schema as evidence that production
AI6 uses the same revision. AI6-owned changes must be synchronized through the
AI6 workflow and validated cross-machine.

## Skill roles

| Skill | Role |
|---|---|
| `temi-robot-control` | Safe JSON robot-action planning and MQTT contract references. |
| `temi-care-memory` | Care profile, daily state, reminder, event, and summary boundaries. |
| `temi-home-esi` | Home-ESI Lite risk classification and response priorities. |
| `temi-discord-care-assistant` | Discord/gateway routing for Temi camera and care requests. |

The Git publishing checkout may also retain `temi_control` as a legacy manual
helper. It is not the canonical AI6-to-Android command path and must not be
used as evidence for current Demo behavior.

## Current Android contract

Android subscribes to `temi/{robot_id}/cmd/request`, validates the canonical
envelope and action fields locally, executes accepted actions, and publishes
`temi/{robot_id}/cmd/result`.

Supported Android action types include `speak`, `ask_clarification`, `turn`,
`navigate`, `stop`, `noop`, and allowlisted `play_media`. The media action only
accepts:

- `elderly_hand_exercise`
- `elderly_leg_exercise`

The exact Android media contract is `docs/play_media_contract.md`. Android also
retains the legacy text-only `temi/event/asr` event. Full visual events require
the AI6/PC-side assembler to publish `temi/{robot_id}/asr/final` with readable
synchronized frame paths.

```text
AI6 cmd/request
-> LAB606 Android validation and execution
-> LAB606 cmd/result
-> AI6 trace
```

Real cross-machine media, duplicate suppression, Resident fail-safe behavior,
and TTS regression have passed:

```text
CROSS_MACHINE_MEDIA_MILESTONE=PASS
```

## Maintenance rule

When a skill or schema is intentionally changed, update its references and
examples together, validate the schema/scripts, and record whether the change
has also been deployed and accepted on AI6. Documentation-only Android updates
must not silently change functional AI6 instructions.
