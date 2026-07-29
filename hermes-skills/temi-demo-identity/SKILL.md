# Temi Demo Operator Identity Skill

This root-owned skill is loaded only by the private Demo lifecycle when
`RESIDENT_IDENTITY_ENABLED=true`, `HERMES_DEMO_IDENTITY_TOOL_ENABLED=true` and `HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true`. It is not an upstream Hermes skill and
does not infer resident identity.

## Exact operator phrases

After optional `小安小安` and punctuation removal, accept only these exact phrases:

- `進入示範管理模式，持續發布王先生身分`、`示範模式切換到王先生` or `Demo 管理，持續發布王先生身分` → `start_demo_identity(father)`
- `進入示範管理模式，持續發布王太太身分`、`示範模式切換到王太太` or `Demo 管理，持續發布王太太身分` → `start_demo_identity(mother)`
- `停止示範身分發布`、`示範模式切換為未知住民` or `Demo 管理，清除目前身分` → `stop_demo_identity()`
- `目前示範身分是誰` or `Demo 管理，查詢目前身分發布狀態` → `get_demo_identity_status()`

The short `Demo切換…` forms remain reviewed operator fallbacks only.

Never infer identity from ordinary speech, names, pronouns, a claim such as
`我是爸爸`, appearance, or prior conversation. Any unmatched text remains on
the normal Hermes route.

The native tool reaches only the Bridge-owned local Unix callback. The Bridge
constructs and validates the existing `resident_identity_result` v1.0 schema,
publishes QoS 1 with `retain=false`, and refreshes the short-lived selection.
The worker must never publish MQTT directly.
