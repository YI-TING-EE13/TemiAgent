# Canonical Cross-Service Contract：Identity、Video 與 Care Report

最後審查日期：2026-07-26

本文件定義第一年度新增功能的跨服務協議。`hermes_temi_bridge/schemas/` 是
runtime schema 的唯一權威來源；本文件只說明 message flow、責任、安全語意與
相容性。本階段只建立 contract 與 hardware-free schema tests，不代表 identity
推論、Hermes video action、Android 實作或 care report service 已完成。

## 現況盤點與決策

| 需求 | 既有能力 | 決策 | Capability state |
|---|---|---|---|
| Resident identity result | 沒有 canonical identity topic 或 schema；`memory/profile.json` 是 Demo-only 單一 persona，不可當 identity result | 新增獨立 identity result topic 與 schema | Contract defined；runtime 未實作 |
| Video command | `cmd/request` 已是唯一 robot command topic，但 v1.0 只有 `command_id` 與 `actions[]` | 沿用 topic，新增以 `schema_version=1.1`、`message_type=video.command` 辨識的 subtype | Contract defined；producer/consumer 未實作 |
| Video command result | `cmd/result` 已回傳 command 結果，但 v1.0 status 無法表達播放 lifecycle | 沿用 topic，新增 v1.1 video result subtype | Contract defined；Android/Bridge handling 未實作 |
| Care report | `generate_summary` 與 Markdown summary 是 Demo memory action/artifact，不是跨服務 report payload | 新增 care report topic 與 schema；不從 Demo 情境推導內容 | Contract defined；report service 未實作 |
| Report interaction | Trace 可記錄 command result，沒有 report viewed/acknowledged contract | 新增 interaction result topic 與 schema | Contract defined；runtime 未實作 |
| Error codes | 既有 code 分散在 validators 與 trace payload | 新 schema 使用 `cross_service_common.schema.json` 的 allowlist；既有錯誤碼不變 | New contracts only |

盤點發現 `docs/project/system_handover.md` 曾提到 `media_contract.py`、resident
resolution 與分 resident memory layout，但目前 branch 沒有那些 runtime files。
本 contract 以目前可執行 code、schema 與 tests 為準，不把 handover 中的未落地敘述
當成 implemented baseline。

## Canonical authority 與 message direction

所有 MQTT 訊息使用 UTF-8 JSON object、QoS 1、`retain=false`。Broker 不驗證 payload。
Publisher 在 publish 前驗證；subscriber 在處理前再次驗證。Schema governance owner
是 HermesTemiBridge module；domain producer 仍負責欄位正確性。

| Topic | Direction | Publisher | Subscriber | Runtime validation owner |
|---|---|---|---|---|
| `temi/{robot_id}/resident/identity/result` | identity result → consumers | 未來 identity adapter；manual selection 由 Temi App 產生 | Temi App、未來 report pipeline、Bridge integration | 各 subscriber；Bridge schema 是 authority |
| `temi/{robot_id}/cmd/request` | command producer → Temi App | Bridge。Remote gateway 必須把 authorized intent 交給 Bridge；Temi App manual UI 可直接重用本地 command handler | Temi App | Bridge publish boundary 與 Temi App boundary validator |
| `temi/{robot_id}/cmd/result` | Temi App → command producer/trace | Temi App | Bridge、request originator | Bridge/result consumer |
| `temi/{robot_id}/care/report` | report producer → reviewer UI | 未來 report producer behind Bridge/memory boundary | Temi App、authorized reviewer | 每個 report consumer |
| `temi/{robot_id}/care/report/interaction/result` | reviewer UI → report owner/trace | Temi App 或 authorized reviewer client | 未來 report owner、Bridge trace adapter | Report interaction consumer |

新 topic 目前沒有 active publisher 或 subscriber。實作者不得在 service code、Android
或 runbook 宣稱 message flow 可執行，直到 producer、consumer、validation 與 integration
tests 同時完成。

## Identifier responsibility 與 correlation

- `event_id` 由最早建立業務事件的 producer 產生，並在包含此欄位的 identity、command
  與 trace 訊息中保持不變。手動或遠端操作沒有上游 event 時，入口 adapter 必須產生新的
  `event_id`，不得重用前一次 ASR event。
- `request_id` 由 command 或 report interaction 的入口 producer 產生。同一 logical
  request 的 retry 必須重用 `request_id`；不同操作必須使用新值。
- Video v1.1 同時保留 `command_id` 供既有 command correlation。Publisher MUST 令
  `command_id == request_id`；subscriber 若兩者不同，必須以
  `MEDIA_CONTROL_CONFLICT` 拒絕。
- Video result MUST 原樣回傳 `request_id`、`command_id`、`event_id` 與 `video_id`。
  一個 request 可依序產生多個 lifecycle results。
- `report_id` 由 report producer 產生。Interaction result 必須原樣回傳 `report_id` 與
  `resident_id`；consumer 不得只用日期尋找 report。

Publisher 使用隨機或時間排序 ID 均可，但 ID 不得包含姓名、日期以外的照護內容、
裝置位址或其他敏感資料。

## Resident identity result v1.0

Authority：`hermes_temi_bridge/schemas/resident_identity_result.schema.json`。

`father` 與 `mother` 只是第一年度暫行 display mapping。`vision_gender_fallback` 表示
模型依有限視覺線索做 Demo fallback；它不是 face recognition、speaker recognition、
verified identity 或醫療判定。UI 必須顯示暫行狀態，不能把 `confidence` 呈現為認證準確率。

安全規則：

- `unknown` 必須使用 `resident_id=null`、`display_name=unknown`、`source=unknown`。
- `unknown` 不得 fallback 到最近使用者、father 或 mother 的 memory/report。
- `father` 與 `mother` 必須使用不同且穩定的 `resident_id`。Storage、cache、report、
  reminder 與 trace lookup 必須以 `resident_id` 分區，不得只用 `display_name`。
- Manual selection 必須保留 `source=manual_selection`，不得改寫成 vision result。

合法範例：

```json
{"schema_version":"1.0","event_id":"evt_identity_001","resident_id":"resident_father","display_name":"father","identity_status":"father","confidence":0.71,"source":"vision_gender_fallback","reason":"Temporary first-year mapping; not face recognition.","timestamp":"2026-07-26T10:00:00Z"}
```

邊界範例（安全 unknown）：

```json
{"schema_version":"1.0","event_id":"evt_identity_002","resident_id":null,"display_name":"unknown","identity_status":"unknown","confidence":0,"source":"unknown","reason":"No safe identity mapping is available.","timestamp":"2026-07-26T10:00:01Z"}
```

非法範例：`identity_status=mother` 但 `display_name=father`；schema 必須拒絕。

## Video command v1.1

Authority：`hermes_temi_bridge/schemas/temi_command_request.schema.json`。

Video subtype 使用 `message_type=video.command`，支援 `play_video`、`pause_video`、
`resume_video`、`stop_video`。`video_id` 只能是 Android 與 command producer 共同部署的
allowlisted logical ID；payload 不得包含 URL、absolute path、media bytes 或 private host。
`parameters` 是 bounded object；每個參數需由後續 Android contract revision 明確列入
allowlist 才能執行。

`execution_class` 定義 ordering，不建立新 topic：

| Action | `execution_class` | Session target | Ordering |
|---|---|---|---|
| `play_video` | `serialized_execution` | `target_playback_session_id=null` | 保留在一般 serialized command queue；不可插隊 |
| pause/resume/stop | `active_playback_control` | 必須指定非空 `target_playback_session_id` | 只有通過 schema、semantic/Action Validator 與 active-session target validation 後，才可繞過 serialized queue |

繞過 queue 只代表控制現有播放，不代表繞過 Bridge safety boundary。Generic robot action
`stop` 的既有語意與 schema 不變，也不能代替 `stop_video`。App 在接受新的 play 後建立
唯一 `playback_session_id`；request producer 不得預先指定該 ID。`command_id == request_id`
仍是 transport correlation invariant，兩者不是 playback session ID。
Control result 的 `playback_session_id` 與 `target_playback_session_id` 必須相等；此欄位
equality 與 request/session lookup 一樣由 semantic validation 執行。

合法範例：

```json
{"schema_version":"1.1","message_type":"video.command","command_id":"req_video_001","request_id":"req_video_001","event_id":"evt_video_001","robot_id":"temi-01","resident_id":"resident_father","action":"play_video","execution_class":"serialized_execution","target_playback_session_id":null,"video_id":"exercise_upper_body_01","parameters":{"start_position_ms":0},"source":"hermes_temi_bridge","timestamp":"2026-07-26T10:01:00Z"}
```

邊界範例：`stop_video` 使用 `execution_class=active_playback_control`、目前 active session
ID 與空的 `parameters={}`，且仍提供與 session 相符的 `video_id`。

非法範例：play 使用 control execution class、control 缺少 target session、
`action=seek_video`、缺少 `resident_id`，或 `command_id != request_id`。Schema 拒絕前四類；
JSON Schema 無法比較兩個欄位，ID equality 由 publisher 與 subscriber semantic validation
拒絕。Target session 不存在、不是目前 active session、`video_id` 不符或 state transition
不合法，也必須在任何 player side effect 前拒絕。

Hermes 目前不能輸出 video robot action：`hermes_action_output.schema.json` 與受保護的
`action_validator.py` 沒有 video allowlist。本階段不得讓 Hermes 直接 publish v1.1
command。後續實作必須先經獨立 safety review，同步 action schema、validator、skill、
builder、Android contract 與 producer/consumer tests。

## Video command result v1.1

Authority：`hermes_temi_bridge/schemas/temi_command_result.schema.json`。

Command status 是 `accepted`、`started`、`succeeded`、`completed`、`cancelled`、
`rejected`、`failed`；它與 `playback_state` 分離。`terminal=false` 只允許 play 的
`accepted`/`started`，其他結果均為 terminal。非 error status 的 error fields 為 null；
`rejected`/`failed` 必須使用 media error allowlist。

| Command | Result lifecycle | Playback session effect |
|---|---|---|
| play | `accepted` → `started` → `completed` / `cancelled` / `failed` | 同一 `playback_session_id`；只有最後一筆 terminal |
| pause | terminal `succeeded` / `rejected` / `failed` | 成功後 state=`paused`；原 play 仍 active、非 terminal |
| resume | terminal `succeeded` / `rejected` / `failed` | 成功後 state=`playing`；原 play 仍 active、非 terminal |
| stop | terminal `succeeded` / `rejected` / `failed` | 成功時另發布原 play 的 terminal `cancelled` |

Remote stop 產生兩筆結果：stop command 自身 `succeeded`，以及原 play 的
`status=cancelled`、`cancel_reason=remote_stop`、`cancelled_by_command_id=<stop command>`。
本機使用者停止只終止原 play，使用 `actor=local_user`、
`cancel_reason=local_user_stop`、`cancelled_by_command_id=null`；不得捏造 remote stop
command result。本機發起的 play 是 App telemetry，不使用 `cmd/result` 假裝收到 remote
command。

合法範例：

```json
{"schema_version":"1.1","message_type":"video.command_result","command_id":"req_video_001","request_id":"req_video_001","event_id":"evt_video_001","robot_id":"temi-01","command_action":"play_video","video_id":"exercise_upper_body_01","status":"started","terminal":false,"playback_session_id":"session_video_001","target_playback_session_id":null,"active_playback_session_id":null,"playback_state":"playing","cancelled_by_command_id":null,"cancel_reason":null,"actor":"remote_command","result_delivery":"original","error_code":null,"error_message":null,"timestamp":"2026-07-26T10:01:01Z"}
```

邊界範例（同時有 active session 時拒絕新的 play，不 queue、不 replace）：

```json
{"schema_version":"1.1","message_type":"video.command_result","command_id":"req_video_002","request_id":"req_video_002","event_id":"evt_video_002","robot_id":"temi-01","command_action":"play_video","video_id":"exercise_upper_body_01","status":"rejected","terminal":true,"playback_session_id":null,"target_playback_session_id":null,"active_playback_session_id":"session_video_001","playback_state":null,"cancelled_by_command_id":null,"cancel_reason":null,"actor":"remote_command","result_delivery":"original","error_code":"MEDIA_SESSION_ACTIVE","error_message":"Another playback session is active.","timestamp":"2026-07-26T10:01:02Z"}
```

非法範例：pause 使用非 terminal result、舊的 `status=paused`、local stop 帶有假的
`cancelled_by_command_id`，或 `MEDIA_SESSION_ACTIVE` 沒有 active session ID；schema 必須拒絕。

## Ordering、duplicate 與 restart

- 同一 active session 的 controls 依 App 接收並驗證完成後的 monotonic order 套用；互斥或
  stale control 回 `MEDIA_CONTROL_CONFLICT`，不得以 MQTT timestamp 重排已執行 action。
- 同時只能有一個 remote playback session。新的 play 遇到 active session 必須立即拒絕，
  不排隊、不取代，也不建立新 session。
- App 以 `command_id` 為 idempotency key，並檢查同 ID payload digest。相同 command 不得
  重播或建立新 session；不同 payload 使用同 ID 回 `MEDIA_CONTROL_CONFLICT`。
- Active duplicate 回目前結果與相同 session，`result_delivery=active_reference`；terminal
  duplicate 重送已保存 terminal result，`result_delivery=cached_replay`。不得建立第三個
  correlation ID。
- App 必須持久保存足以跨 process restart 去重的 command/request/event/session/video/action、
  payload digest、session state 與最後結果。Process restart 不自動續播；先前 active play
  必須以 `cancel_reason=app_process_restart` 產生 terminal cancelled，或以
  `APP_PROCESS_RESTART` 產生 failed，並保存 terminal result，避免 backend retry 重新播放。
- `result_delivery=restart_reconciliation` 標示 restart 補發。持久資料不得包含 media bytes、
  URL、private path 或 raw log。

Trace 沿用 `command_result_received`，不增加 record type/topic。Trace payload 必須保留
command/action、`terminal`、session IDs、playback state、result delivery 與 cancellation
link；consumer 不得因 late nonterminal result 將 terminal session 回退。

## Care report v1.0

Authority：`hermes_temi_bridge/schemas/care_report.schema.json`。

`status` 與 `data_completeness.status` 表達 `complete`、`partial`、`no_records`、
`identity_unknown`、`date_not_found`、`unsupported_schema_version`。Empty arrays 表示
該 section 沒有事件；它們不得被解讀成 data source 已完整讀取。只有
`data_completeness.status=complete` 且 `missing_sections=[]` 才表示所有定義中的來源已讀取。

合法範例：

```json
{"schema_version":"1.0","report_id":"report_001","resident_id":"resident_father","display_name":"father","report_date":"2026-07-26","generated_at":"2026-07-26T20:00:00Z","status":"complete","summary":"Synthetic contract example.","discomfort_events":[],"abnormal_events":[],"reminder_status":[],"important_changes":[],"follow_up_notes":[],"data_completeness":{"status":"complete","missing_sections":[]},"error_code":null,"error_message":null}
```

邊界範例（unknown identity）：

```json
{"schema_version":"1.0","report_id":"report_error_001","resident_id":null,"display_name":"unknown","report_date":"2026-07-26","generated_at":"2026-07-26T20:00:00Z","status":"identity_unknown","summary":"","discomfort_events":[],"abnormal_events":[],"reminder_status":[],"important_changes":[],"follow_up_notes":[],"data_completeness":{"status":"identity_unknown","missing_sections":["summary"]},"error_code":"unknown_resident","error_message":"Resident identity is unknown; no resident memory was read."}
```

非法範例：`status=complete` 但 `missing_sections` 非空；schema 必須拒絕。

不支援版本的回應仍使用本 consumer 可解析的 envelope `schema_version=1.0`，並設定
`status=unsupported_schema_version`、`error_code=unsupported_schema_version` 與
`data_completeness.requested_schema_version`。若直接把未知版本填入 `schema_version`，
consumer 無法安全解析 error response。

Report producer 只能讀取 `resident_id` 對應分區。`identity_unknown` 必須在任何
resident memory read 前返回。Report payload 不得包含 raw images、raw logs、完整 model
output、credentials、private endpoints 或未經審查的 identifiable data。
目前 unauthenticated local broker 只適用受控 Demo 網段；在建立 ACL、TLS、authorization
與 retention review 前，不得用此 transport 傳送真實照護資料。

## Care report interaction result v1.0

Authority：`hermes_temi_bridge/schemas/care_report_interaction_result.schema.json`。

第一階段 action 支援 `viewed` 與 `acknowledged`。`viewed` 只表示 authorized UI 已顯示
report；`acknowledged` 表示使用者明確執行確認操作。兩者都不是同意醫療判斷、完成
follow-up 或通知成功。

合法範例：

```json
{"schema_version":"1.0","request_id":"req_report_001","report_id":"report_001","resident_id":"resident_father","action":"viewed","status":"accepted","error_code":null,"error_message":null,"timestamp":"2026-07-26T20:05:00Z"}
```

邊界範例：`action=acknowledged` 與 `status=accepted`；consumer 必須以 request ID 去重。

非法範例：空的 `resident_id`、未知 action，或 `status=failed` 但 error fields 為 null；
schema 必須拒絕。

## 共用錯誤碼

Authority：`hermes_temi_bridge/schemas/cross_service_common.schema.json`。

小寫 codes 保留給既有 identity/report 與 pre-v1.1 compatibility；video v1.1
`rejected`/`failed` 只接受下列大寫 media allowlist。

| Code | Meaning |
|---|---|
| `invalid_message` | Payload 無法通過 schema 或 semantic validation |
| `unsupported_schema_version` | Receiver 不支援 caller 要求的版本 |
| `unknown_resident` | 沒有安全 resident mapping；不得讀取其他 resident 資料 |
| `video_not_found` | `video_id` 不在 deployed allowlist |
| `video_action_not_allowed` | Caller 或目前 policy 不允許該 video action |
| `invalid_video_state` | Action 不符合目前 player lifecycle |
| `request_conflict` | 相同 ID 對應不同內容或衝突 terminal result |
| `report_not_found` | 找不到指定 `report_id` |
| `report_no_records` | 指定 resident/date 沒有可報告紀錄 |
| `report_partial_data` | 至少一個必要 data source 缺失或讀取失敗 |
| `report_delivery_failed` | Report 無法傳送給指定 consumer |
| `internal_error` | Receiver 內部失敗且沒有更精確 allowlisted code |
| `MEDIA_SESSION_ACTIVE` | 新 play 被現有 active session 阻擋；附 active session ID |
| `MEDIA_SESSION_NOT_FOUND` | Control target 不存在或已終止 |
| `MEDIA_SESSION_NOT_PLAYING` | Pause/stop 需要 playing session，但 state 不符 |
| `MEDIA_SESSION_NOT_PAUSED` | Resume target 不是 paused |
| `VIDEO_ID_NOT_ALLOWED` | Logical video ID 不在 App allowlist |
| `MEDIA_CONTROL_CONFLICT` | ID/payload、control ordering 或 terminal state 衝突 |
| `UNSUPPORTED_MEDIA_ACTION` | v1.1 不支援 action |
| `APP_PROCESS_RESTART` | Restart reconciliation 選擇 failed 結果時使用 |
| `LOCAL_USER_STOP` | 需要以 error 表示本機停止衝突時使用；正常 local cancellation 的 error fields 仍為 null |
| `INTERNAL_ERROR` | Media handler 沒有更精確 code 的內部失敗 |

Error message 不得包含 secret、private path、raw care payload 或 stack trace。Transport
retry 只能針對明確 retryable failure 且必須 bounded；schema error、unknown resident 與
request conflict 不得自動改寫後重試。

## Compatibility 與 migration

- Command request/result v1.0 schema 保留原欄位、status 與 permissive additional
  properties；既有 Bridge serialization、Android parser 與 tests 不需改寫。
- Video 使用 v1.1 discriminator。舊 Android 若不支援 v1.1，必須拒絕並回傳明確 error；
  publisher 不得 fallback 成 `speak` 或任意 legacy media action。
- Starting commit `5c94cd3` 的 v1.1 `paused`/`resumed`/`stopped` result status 被本版的
  terminal `succeeded` + `playback_state` 取代。該 subtype 尚未接入 runtime，因此採
  pre-runtime schema refinement；實作者不得同時接受兩種 v1.1 語意。v1.0 完全不變。
- 新 identity/report topics 不改變 ASR、abnormal、command 或 legacy topics。
- MQTT 不使用 retained message。Deploy consumer validation 後才能 enable producer，
  rollback 時先 disable producer，再移除 consumer support。
- 本階段沒有 schema registry negotiation。版本支援必須由 deployment manifest 或
  integration evidence 確認，不能靠試送硬體 command 探測。

## Verification scope

`hermes_temi_bridge/tests/test_cross_service_contract_schemas.py` 使用指定容器既有的
Node.js Ajv Draft 2020-12 validator，覆蓋每個新 message 的合法、邊界與非法資料，並
確認舊 command request/result v1.0 仍合法。Android、MQTT live flow、Hermes video
action、report generation、identity model 與 real-device execution 均留待後續實作驗證。
