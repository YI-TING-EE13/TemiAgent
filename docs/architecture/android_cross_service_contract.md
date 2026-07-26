# Temi Android Cross-Service Contract 摘要

最後審查日期：2026-07-26

本文件提供 LAB606 Temi Android App 實作者需要的最小 contract。完整語意、範例與
相容性規則見 [canonical cross-service contract](canonical_cross_service_contract.md)；
runtime schemas 位於 `hermes_temi_bridge/schemas/`。AI6 repository 不包含 Android
source，本文件不代表 Android 功能已實作或通過真機驗證。

## Topic 與 direction

| Topic | App responsibility |
|---|---|
| `temi/{robot_id}/resident/identity/result` | Subscribe；驗證後顯示 `father`、`mother` 或 `unknown`。Manual selection 可產生相同 schema 的 result，source 必須是 `manual_selection`。 |
| `temi/{robot_id}/cmd/request` | 保留 v1.0 parser；新增 v1.1 `video.command` parser 與 allowlisted player state machine。 |
| `temi/{robot_id}/cmd/result` | 對 v1.1 video request 發布 lifecycle results；原樣回傳 correlation fields。 |
| `temi/{robot_id}/care/report` | Subscribe；依 resident authorization 顯示 report 或明確 incomplete/error state。 |
| `temi/{robot_id}/care/report/interaction/result` | 使用者完成 viewed/acknowledged 操作後 publish；network delivery 不得改寫使用者 action。 |

所有 MQTT payload 使用 UTF-8 JSON object、QoS 1、`retain=false`。App 必須在 side effect
前完成 schema、robot ID、resident ID、request ID、action、video ID 與 state validation。

## Parser dispatch

| Schema | Discriminator | Required handling |
|---|---|---|
| Command v1.0 | `schema_version=1.0`、`actions[]` | 保留現行 command behavior。 |
| Video command v1.1 | `schema_version=1.1`、`message_type=video.command` | 僅接受四個 video actions；`command_id` 必須等於 `request_id`。 |
| Video result v1.1 | `schema_version=1.1`、`message_type=video.command_result` | 依 player callback 發布 lifecycle，不得以 publish success 當 playback success。 |
| Identity v1.0 | identity schema | `unknown` 必須保持 unknown，不得選最近 resident。 |
| Care report v1.0 | report schema | 以 `status` 與 `data_completeness` 顯示完整、部分、無紀錄或 error。 |
| Interaction v1.0 | interaction schema | `viewed` 與 `acknowledged` 是不同 user actions。 |

未知 `schema_version` 或 `message_type` 必須拒絕。App 不得猜測新版本欄位或把新 payload
交給 v1.0 parser。

## Video state 與 result

App 必須以 `request_id` 去重，並使用 allowlisted `video_id` 對應 bundled/deployed media。
App 不得執行 payload 中的 URL 或 filesystem path。建議的最小 state transition：

```text
idle --play_video--> accepted --> started --> completed
playing --pause_video--> paused
paused --resume_video--> resumed
playing|paused --stop_video--> stopped
invalid transition --> rejected|failed + invalid_video_state
```

App 可以為同一 request 發布多個 lifecycle results。每個 result 必須原樣回傳
`command_id`、`request_id`、`event_id`、`robot_id` 與 `video_id`。`rejected` 或 `failed`
必須提供 allowlisted error code 與安全 error message；其他 status 的 error fields 必須為
null。

## Identity 與 resident data isolation

- UI label 只允許 `father`、`mother`、`unknown`。
- `vision_gender_fallback` 是第一年度 Demo 暫行映射，不是 face recognition。
- `unknown` 必須使用 null resident ID，且不得開啟 father 或 mother 的 report、reminder、
  cached view 或 player personalization。
- App cache、ViewModel state、saved state 與 report lookup 必須以 stable `resident_id`
  分區。切換 resident 時必須清除前一 resident 的 sensitive view state。
- App 不得只用 display label 作 storage key。

## Report UI 與 interaction

App 必須分別呈現：`complete`、`partial`、`no_records`、`identity_unknown`、
`date_not_found`、`unsupported_schema_version`。Empty section 不代表資料完整；App 必須
讀取 `data_completeness`。

App 顯示 report 後才可建立 `viewed`。只有明確的使用者確認操作才可建立
`acknowledged`。App 不得以收到 report、開啟頁面前的 prefetch、MQTT publish success
或 timeout fallback 代替 acknowledged。

## LAB606 implementation checklist

- 保留 v1.0 command/result JVM tests，新增 v1.1 legal/boundary/invalid parser tests。
- 新增 player state transition、unknown video ID、duplicate request、late callback、conflict
  terminal result tests。
- 新增 unknown identity 與 father/mother cache isolation tests。
- 新增 report completeness、unknown identity、date not found、unsupported version tests。
- 新增 viewed/acknowledged user-action tests與 publish retry/idempotency tests。
- 真機驗證必須同時保存 AI6 request、Android received/player callback、MQTT result 與 AI6
  trace；只有 publish evidence 不代表影片已播放。
- Android repository 必須同步自己的 `AGENTS.md`、README、schema/contract copy 與 build
  evidence；AI6 不代替 Android source authority。
