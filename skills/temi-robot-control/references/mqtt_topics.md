# MQTT Topics

This file describes the surrounding bridge contract. The skill must not publish or subscribe MQTT directly.

## Topics

- Temi publishes ASR final events to `temi/{robot_id}/asr/final`.
- `HermesTemiBridge` subscribes to `temi/+/asr/final`.
- `HermesTemiBridge` publishes validated command requests to `temi/{robot_id}/cmd/request`.
- Temi publishes command execution results to `temi/{robot_id}/cmd/result`.
- Temi may publish robot state to `temi/{robot_id}/state`.

Compatibility note:

- The current Android app also publishes legacy text-only ASR events to `temi/event/asr`.
- `HermesTemiBridge` accepts that legacy topic for non-visual control and speech responses.
- Visual tasks still require a PC-side frame assembler to publish `temi/{robot_id}/asr/final` with readable frame paths.

## Boundary

Hermes and this skill only produce the JSON action plan. `HermesTemiBridge` is responsible for:

- MQTT connection management
- event validation
- image path translation
- Hermes invocation
- JSON parsing
- schema validation
- command wrapping
- publishing command requests
- logging and fallback handling
