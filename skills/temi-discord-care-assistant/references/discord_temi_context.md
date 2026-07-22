# Discord Temi Context Notes

Hermes gateway sessions may arrive from Discord without the same structured ASR
event envelope used by HermesTemiBridge. In that case, Hermes should still
recognize TemiAgent intent from the user wording and choose the right Temi
skill.

## Expected Behavior

- If Discord includes an uploaded image, use vision analysis before answering a
  visual question.
- If Discord includes a file path under `temi_shared`, `/TemiAgent/temi_shared`,
  or `/shared/temi`, treat it as a candidate Temi frame path.
- If the user asks about a gesture or pointing but no image is present, ask for
  a current Temi frame/event instead of saying Temi has no camera capability.
- If the user reports discomfort, a fall, no response, or an emergency, use
  `temi-home-esi` and `temi-care-memory` in addition to robot response planning.

## Skill Routing

| User intent | Primary skill | Additional skill |
|---|---|---|
| Camera, visible object, hand gesture, pointing | `temi-robot-control` | none |
| Reminder or care record | `temi-care-memory` | `temi-robot-control` |
| Discomfort, fall, emergency-like situation | `temi-home-esi` | `temi-care-memory`, `temi-robot-control` |
