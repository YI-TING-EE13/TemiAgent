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
  `command_id == request_id`；subscriber 若兩者不同，必須以 `request_conflict` 拒絕。
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

合法範例：

```json
{"schema_version":"1.1","message_type":"video.command","command_id":"req_video_001","request_id":"req_video_001","event_id":"evt_video_001","robot_id":"temi-01","resident_id":"resident_father","action":"play_video","video_id":"exercise_upper_body_01","parameters":{"start_position_ms":0},"source":"hermes_temi_bridge","timestamp":"2026-07-26T10:01:00Z"}
```

邊界範例：`stop_video` 可使用空的 `parameters={}`，但仍必須提供 `video_id`。

非法範例：`action=seek_video`、缺少 `resident_id`，或 `command_id != request_id`。前兩項
由 schema 拒絕；ID equality 由 producer/consumer semantic validation 拒絕。

Hermes 目前不能輸出 video robot action：`hermes_action_output.schema.json` 與受保護的
`action_validator.py` 沒有 video allowlist。本階段不得讓 Hermes 直接 publish v1.1
command。後續實作必須先經獨立 safety review，同步 action schema、validator、skill、
builder、Android contract 與 producer/consumer tests。

## Video command result v1.1

Authority：`hermes_temi_bridge/schemas/temi_command_result.schema.json`。

Lifecycle status：`accepted`、`started`、`paused`、`resumed`、`completed`、`stopped`、
`rejected`、`failed`。非 error status 的 `error_code` 與 `error_message` 必須為 `null`；
`rejected` 或 `failed` 必須提供 allowlisted `error_code` 與非空 message。

合法範例：

```json
{"schema_version":"1.1","message_type":"video.command_result","command_id":"req_video_001","request_id":"req_video_001","event_id":"evt_video_001","robot_id":"temi-01","video_id":"exercise_upper_body_01","status":"started","error_code":null,"error_message":null,"timestamp":"2026-07-26T10:01:01Z"}
```

邊界範例：

```json
{"schema_version":"1.1","message_type":"video.command_result","command_id":"req_video_001","request_id":"req_video_001","event_id":"evt_video_001","robot_id":"temi-01","video_id":"exercise_upper_body_01","status":"failed","error_code":"invalid_video_state","error_message":"Video is not active.","timestamp":"2026-07-26T10:01:02Z"}
```

非法範例：`status=failed` 且 `error_code=null`；schema 必須拒絕。

Result ordering 由 publisher timestamp 與 local monotonic sequence（若實作者增加）判定。
Consumer 不得因 late `accepted` 將 `completed` 狀態回退。重複的相同 status 可視為
idempotent delivery；同一 request 的衝突 terminal status 必須記錄 `request_conflict`。

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

Error message 不得包含 secret、private path、raw care payload 或 stack trace。Transport
retry 只能針對明確 retryable failure 且必須 bounded；schema error、unknown resident 與
request conflict 不得自動改寫後重試。

## Compatibility 與 migration

- Command request/result v1.0 schema 保留原欄位、status 與 permissive additional
  properties；既有 Bridge serialization、Android parser 與 tests 不需改寫。
- Video 使用 v1.1 discriminator。舊 Android 若不支援 v1.1，必須拒絕並回傳明確 error；
  publisher 不得 fallback 成 `speak` 或任意 legacy media action。
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
