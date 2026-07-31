# HermesTemiBridge 模組 README

最後更新日期：2026-07-31

## 本文件維護規則

這份 README 是 `hermes_temi_bridge/` 的快速入口。只要 MQTT contract、Hermes invocation mode、action schema、path translation、log format 或測試方式改變，都要同步更新本文件，讓後續維護者可以只讀本模組 README 就進入狀況。

## 模組定位

HermesTemiBridge 是 Temi 與 Hermes 之間的安全邊界。它不是高階推理核心，也不是 Temi Android App；它負責接收 Temi 事件、驗證資料、呼叫 Hermes、驗證 Hermes JSON output，最後只把安全的 command request 發回 MQTT。

```text
Temi Android + ASR/camera-only Overview Adapter
  -> MQTT temi/{robot_id}/asr/final
  -> HermesTemiBridge
  -> Hermes CLI / Resident HTTP / Mock Hermes
  -> validated temi/{robot_id}/cmd/request
  -> Temi Android directly executes command
  -> MQTT temi/{robot_id}/cmd/result
```

Continuous vision abnormal events use the same Bridge safety boundary:

```text
Temi Action Viewer / Video Action Tester
  -> MQTT temi/{robot_id}/perception/abnormal
  -> HermesTemiBridge validation + persistent care episode
  -> one Bridge-owned notification receipt attempt
  -> Resident Hermes constrained care response
  -> validated temi/{robot_id}/cmd/request (speak only for the care flow)
  -> Temi Android cmd/result + reply/timeout follow-up
```

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `mqtt/` | Bridge subscribe ASR/result topics，publish command request；command 不經 adapter 二次轉發。 |
| `temi_shared/` | Bridge 讀取 ASR event 內的三張影像路徑，並做 Bridge path 到 Hermes path 的轉換。 |
| `hermes-agent/` | CLI mode 與 resident HTTP mode 會呼叫本地 Hermes runtime。 |
| `hermes-skills/` / `hermes-agent/skills/temi-*` | Hermes prompt 的 robot action、care memory、Home-ESI 規則來源。 |
| `docs/schemas/` | 文件用 schema 副本；本模組執行時以 `hermes_temi_bridge/schemas/` 為準。 |
| `tools/hermes_resident_server.py` | 提供低延遲 HTTP invocation endpoint。 |

## 核心職責

- 連線到 MQTT broker。
- Subscribe `temi/+/asr/final`、`temi/+/perception/abnormal`、`temi/+/cmd/result` 與既有
  `temi/+/resident/identity/result` contract。
- 驗證 ASR event schema 與 robot allowlist。
- 驗證三張影像存在、大小合理，且位於 shared root 內。
- 驗證 abnormal event 內的 evidence frame paths 存在、大小合理，且位於 shared root 內。
- 對 abnormal event 建立 bounded、atomic、restart-safe care episode；先保留 notification
  stage，再呼叫 Resident Hermes，並透過既有 action validator 發出 speak command。
- 在下一個同 robot 的高信心 ASR 先處理明確同意／拒絕；模糊回答最多重問一次。第一與第二
  monotonic timeout 分別觸發一次 Hermes recheck 與一次 deduplicated escalation。
- 將 `/var/lib/temi_shared/...` 轉成 Hermes 可讀的 `/shared/temi/...` 或本機等價路徑。
- 建立 Hermes prompt。
- 支援 `mock`、`cli`、`http` 三種 Hermes invocation mode。
- 解析 Hermes JSON-only output，容忍常見 Markdown code fence 包裝。
- 驗證 action schema 與安全限制。
- 將 robot actions 發布到 `temi/{robot_id}/cmd/request`。
- 執行 Bridge-internal memory/demo actions，包含 event log、reminder done、summary 與 mock caregiver notification。
- 記錄 raw output、parsed output、robot command request、memory action result、command result 與錯誤。
- 在 `MEDIA_V11_ENABLED=true` 時提供獨立 media v1.1 request API，並嚴格驗證 result、
  command/session correlation、lifecycle 與 replay disposition。
- 僅在 `MEDIA_V11_ENABLED=true`、`HERMES_MEDIA_TOOL_ENABLED=true` 與 private Unix
  callback socket 都已設定時，接受 resident Hermes 的 root-owned native Media tool callback。
  Resident process 不擁有 MQTT publisher。
- Resident 的 `HERMES_MEDIA_FAST_PATH_ENABLED=true` 僅啟用受控中文 phrase 的 deterministic
  generic Media dispatch；它在 LLM inference 前重用 native tool → Unix callback → Bridge，
  預設為 `false`，不恢復 Bridge 外部 fallback。
- `RESIDENT_IDENTITY_ENABLED=true`、`HERMES_DEMO_IDENTITY_TOOL_ENABLED=true` 與 `HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true` 時，root resident 才接受固定的示範管理 phrase，經 native tool 和 private Unix callback 呼叫 Bridge。Bridge 以現有 identity v1.0 schema 建構、驗證後才以 QoS 1 / `retain=false` 發布 `resident/identity/result`；它不從一般語句推論身分。選擇為 process-scoped，10 秒 refresh 與 max duration 都由 private env 明定，restart 不會 restore 舊身分。
- `CARE_MEMORY_V2_ENABLED=true` 與 `DEMO_REPEATED_DISCOMFORT_ENABLED=true` 時，只有 active `father` 的三段精確語句可經
  native callback 讀取固定 synthetic prior-headache event、確認、再以 canonical
  `StructuredMemoryStore` 寫入使用者提供的血壓數值。它不讀 mother / unknown partition，也不
  做醫療判斷。

## 目前狀態與限制

2026-05-31 盤點：

- Hardware-free path 使用 `uv run python -m unittest discover -s tests` 驗證；完成報告必須
  記錄當次實際 test count 與結果。
- Root local mock E2E 已驗證：`python3 tools/e2e_test_runner.py` 回傳 `status: ok`。
- HTTP resident mode 已完成 client 與 server wiring；實機紀錄顯示 warm resident latency 約 7-8 秒級，比 CLI cold start 約 97 秒明顯降低。
- Action validator 會強制檢查 `cognitive_state.home_esi_level` 與 `cognitive_state.risk_reason`。
- Robot-facing actions：`speak`、`ask_clarification`、`turn`、`navigate`、`stop`、`noop`。
- Bridge-internal memory/demo actions：`log_event`、`mark_reminder_done`、`generate_summary`、`notify_caregiver_mock`。
- 只有 robot-facing actions 會 publish 到 `temi/{robot_id}/cmd/request`；memory/demo actions 只寫入 `MEMORY_DIR`。
- Canonical abnormal events include `event_type`, `observation`, `evidence.frame_paths`, and
  `context.source`. Formal test events additionally require `test`, `resident_id`, `request_id`,
  `run_id`, and `scenario_id`; they do not carry image bytes, model confidence, or severity.
- The Bridge, never the viewer, owns Discord or Demo mock delivery. `mock_delivered` means an
  explicit Demo mock route recorded a receipt; real Discord is delivered only after HTTP 204.
- Episode state is written atomically to `MEMORY_DIR/abnormal_care_episodes.json`. It stores only
  bounded IDs, monotonic deadlines, transitions, and redacted receipt fields; it excludes raw ASR,
  prompts, evidence, recipient details, webhook URLs, and hidden reasoning.
- 當 feature-gated private Care Memory 因 resident 為 `unknown` 而拒絕存取時，Bridge 保留
  `unknown_resident_memory_forbidden` error code、絕不讀寫任何 resident partition，並改發一個
  speak-only 關懷提示；它不會把拒絕說成已完成照護或通知。
- Identity、care report 與 report interaction 已有 canonical runtime schema 與 schema tests。
  Visual route 只在 `DEMO_RESIDENT_VISUAL_ROUTING_ENABLED=true` 時接受
  `vision_gender_fallback`；另有預設關閉的 Demo operator route 才接受相同 existing schema 的
  `manual_selection`。無結果、衝突、低信心或過期都會變成 `unknown`。本 checkout 仍沒有上游
  VLM/Identity Provider producer，也不把 Demo operator selection 當作 face recognition。
- Video v1.1 沿用 `cmd/request`/`cmd/result` topic。Media 不會擴張 generic
  `action_validator.py` allowlist；native tool callback 先經獨立 allowlist（目前僅
  `elderly_hand_exercise`），再呼叫既有 `publish_media_play()`／`publish_media_control()`。
- Generic direct request 可使用 `resident_id=unknown`，但僅限這個 allowlisted video，且不會
  建立、讀取或寫入 private Care Memory；confirmed father/mother care policy 仍維持原 identity
  binding 與 care-prompt gate。
- Video v1.1 保留 `play_video`、`pause_video`、`resume_video`、`stop_video`。Play 是
  serialized execution；controls 只有完成 schema、semantic validator 與 active-session
  target validation 後才可優先處理。既有 generic robot `stop` 不具 media session 語意。
- Bridge 已實作預設關閉的 media v1.1 producer/result consumer、in-memory correlation
  registry 與 fake Android E2E。這不代表 Android、Hermes video tool 或真機已支援。

## Bridge 設計檢視

目前 Bridge 的職責邊界是清楚且專業的：它是 canonical event/action 的安全閘門，負責 schema validation、path validation、Hermes invocation、action validation、idempotency、memory/demo side effects 與 command dispatch。ASR/camera compatibility 放在 adapter，硬體執行放在 Temi app，推理放在 Hermes；這個分工讓每個模組都容易單測與替換。

本輪刻意移除 adapter command forwarding，避免同一個 `speak` action 同時經 `cmd/request` 與 legacy `temi/action/speak` 觸發。後續若要降低複雜度，應維持以下原則：Bridge 不做影像推理、不碰 Temi SDK、不直接執行任意工具；adapter 不做 command dispatcher；Hermes 不直接 publish MQTT。

## 不負責的事

- 不自行做照護推理或意圖判斷。
- 不直接操作 Temi SDK 或硬體。
- 不把 command request 轉成 legacy `temi/action/speak`；新版 Temi app 直接執行 canonical command。
- 不把圖片 binary 放入 MQTT。
- 不信任 Hermes 任意輸出；所有 action 都必須通過 schema validation。
- 不執行 shell command 或任意工具呼叫。

## 主要檔案

```text
hermes_temi_bridge/
  src/hermes_temi_bridge/
    main.py                 # CLI 入口與 runtime wiring
    mqtt_client.py          # MQTT subscribe/publish
    event_models.py         # ASR and abnormal event parsing/validation
    image_resolver.py       # shared path validation and translation
    hermes_client.py        # mock/cli/http Hermes invocation
    action_validator.py     # Hermes action contract validation
    command_dispatcher.py   # command request publishing
    idempotency.py          # event_id dedup
    hermes_media_tool.py    # native Hermes media callback validation/dispatch adapter
    media_callback_socket.py # private local transport between resident and Bridge
    demo_callback_socket.py  # private local transport for identity/care callbacks
    identity_contract.py     # existing identity v1.0 builder and validator
    demo_identity.py         # process-scoped operator selection / refresh controller
    demo_repeated_discomfort.py # father-only synthetic retrieval / confirm / record flow
    hermes_demo_tools.py     # Bridge callback adapters for resident native tools
    resident_context.py     # canonical identity-result to active resident, fail closed
    demo_care_memory.py     # private synthetic Demo seed and resident partitions
    media_contract.py       # media v1.1 builder and strict boundary validation
    media_registry.py       # command/session lifecycle and replay correlation
  schemas/                  # runtime JSON schemas
  tests/                    # hardware-free unittest suite
```

## 常用模式

### Abnormal perception route

Bridge accepts abnormal perception events on:

```text
temi/{robot_id}/perception/abnormal
```

Expected payload shape:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_abnormal_...",
  "robot_id": "temi-01",
  "type": "perception.abnormal",
  "event_type": "falls_down",
  "timestamp_ms": 1780000000000,
  "observation": {
    "action_name": "falls down",
    "reason": "The person transitions from sitting to lying flat on the floor."
  },
  "evidence": {
    "frame_paths": [
      "/TemiAgent/temi_shared/abnormal_events/temi-01/evt_abnormal_.../frame_000.jpg"
    ]
  },
  "context": {
    "source": "temi_action_viewer",
    "test": true,
    "resident_id": "test-resident",
    "request_id": "req_abnormal_...",
    "run_id": "run_...",
    "scenario_id": "A1"
  }
}
```

The authoritative schema is `schemas/perception_abnormal_event.schema.json`.
Bridge validates that every evidence path is under `TEMI_SHARED_BRIDGE_PATH`, exists, is readable, and is below `MAX_IMAGE_SIZE_MB`. The Hermes prompt receives:

- `source_type: perception.abnormal`
- `action_name`
- model `reason`
- translated evidence frame paths

The Bridge still requires Hermes to return the normal validated JSON action plan before any robot command is published. The perception event itself must not include image bytes, confidence, confidence_source, or severity.

### Mock mode

最快的整合測試模式，不呼叫真模型。

```bash
cd /TemiAgent/hermes_temi_bridge
HERMES_INVOKE_MODE=mock \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/shared/temi \
uv run --extra mqtt hermes-temi-bridge --env-file .env.example
```

### CLI mode

每個 ASR event 啟動一次 `hermes -z`，功能最直覺但 cold start 較慢。

```bash
HERMES_INVOKE_MODE=cli \
HERMES_CLI_COMMAND="hermes -z {prompt}" \
uv run --extra mqtt hermes-temi-bridge --env-file .env.example
```

### Resident HTTP mode

Demo 優先路線。Hermes 常駐，Bridge 呼叫 HTTP endpoint。

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md
```

```bash
cd /TemiAgent/hermes_temi_bridge
HERMES_INVOKE_MODE=http \
HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
uv run --extra mqtt hermes-temi-bridge --env-file .env.example
```

## 重要環境變數

The complete non-secret private Demo profile, ownership modes and feature-gate
relationships are documented in the [Demo configuration reference](../docs/operations/demo_configuration_reference.md).
This table describes Bridge-level inputs; runtime source and `BridgeConfig`
remain authoritative.

| Variable | Purpose |
|---|---|
| `MQTT_BROKER_HOST` / `MQTT_BROKER_PORT` | MQTT broker 位置。 |
| `ROBOT_ID_ALLOWLIST` | 允許處理的 robot id，逗號分隔。 |
| `TEMI_SHARED_BRIDGE_PATH` | Bridge 可讀的 shared root。 |
| `TEMI_SHARED_HERMES_PATH` | prompt 中給 Hermes 使用的 shared root。 |
| `HERMES_INVOKE_MODE` | `mock`、`cli` 或 `http`。 |
| `HERMES_CLI_COMMAND` | CLI mode 的 Hermes 指令，可包含 `{prompt}`。 |
| `HERMES_HTTP_URL` | HTTP mode endpoint。 |
| `HERMES_TIMEOUT_SECONDS` | 呼叫 Hermes 的 timeout。 |
| `LOG_DIR` | event JSONL 與 debug logs 位置。 |
| `TRACE_ENABLED` | 是否啟用 Bridge event trace，預設 `true`。 |
| `DEBUG_TRACE_FULL` | 是否保存 full prompt、full care_context、full raw Hermes output，預設 `false`。 |
| `TRACE_INCLUDE_ASR_TEXT` | 摘要模式是否保存完整 ASR text，預設 `true`；設為 `false` 時只保留 excerpt/hash/length。 |
| `TRACE_RUN_ID` | 手動指定 run id；空值時自動產生。 |
| `TRACE_MAX_FIELD_CHARS` | excerpt 最大字元數，預設 `2000`。 |
| `MEMORY_DIR` | structured memory root，預設 `memory`。 |
| `ABNORMAL_CARE_CONFIRMATION_ENABLED` | 啟用 Bridge-owned abnormal care confirmation；預設 `true`。 |
| `ABNORMAL_CARE_CONFIRMATION_TTL_SECONDS` | pending care question 的 expiry；預設 `120`。 |
| `ABNORMAL_CARE_CONFIRMATION_MIN_ASR_CONFIDENCE` | affirmative answer 可自動接受的最小 ASR confidence；預設 `0.70`。 |
| `ABNORMAL_CARE_EPISODE_ENABLED` | 啟用 Bridge-owned immediate abnormal alert、Resident Hermes、reply/timeout episode；預設 `true`。 |
| `ABNORMAL_CARE_FIRST_RESPONSE_TIMEOUT_SECONDS` / `ABNORMAL_CARE_SECOND_RESPONSE_TIMEOUT_SECONDS` | 兩個 positive monotonic response deadlines；各預設 `120`。 |
| `ABNORMAL_NOTIFICATION_MODE` | `disabled`、`demo_mock` 或 `discord_webhook`；預設 `disabled`。 |
| `DEMO_NOTIFICATION_MOCK_ENABLED` / `DEMO_NOTIFICATION_RECEIPT_ENABLED` | `demo_mock` 必須同時為 `true`；預設皆為 `false`，且不接觸網路收件者。 |
| `DEMO_TEST_EVENT_INGRESS_ENABLED` / `DEMO_TEST_RESIDENT_ALLOWLIST` | 控制 synthetic formal injector 與可接受的 test resident；預設 ingress 為 `false`。 |
| `MEDIA_V11_ENABLED` | 啟用 isolated media v1.1 producer/consumer；預設 `false`。 |
| `HERMES_MEDIA_TOOL_ENABLED` | 接受 root-owned native tool callback；預設 `false`。 |
| `HERMES_MEDIA_FAST_PATH_ENABLED` | Resident-only exact Media matcher；需兩個 Media flag，預設 `false`。 |
| `RESIDENT_IDENTITY_ENABLED` | Bridge Demo-only `manual_selection` admission；需 identity callback 與 state dir，預設 `false`。 |
| `HERMES_DEMO_IDENTITY_TOOL_ENABLED` | Resident root-owned identity native tool registration；預設 `false`。 |
| `HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED` | Resident deterministic exact operator matcher；預設 `false`。 |
| `DEMO_OPERATOR_IDENTITY_ENABLED` | Deprecated private-config compatibility fallback；新 Demo 應使用三個 canonical identity flags，預設 `false`。 |
| `HERMES_DEMO_IDENTITY_CALLBACK_SOCKET` | Root resident → Bridge identity Unix socket；必須是 private absolute path。 |
| `DEMO_IDENTITY_STATE_DIR` | Process-scoped operator identity status artifact directory；restart 不讀回舊值。 |
| `DEMO_IDENTITY_REFRESH_SECONDS` / `DEMO_IDENTITY_MAX_DURATION_SECONDS` | Canonical identity refresh 與 bounded session duration；預設 `10` / `900`。 |
| `CARE_MEMORY_V2_ENABLED` | Enables the canonical private Care Memory v2 Demo store; default `false`. |
| `DEMO_REPEATED_DISCOMFORT_ENABLED` | Father-only synthetic repeated-discomfort callback flow；需 canonical identity 與 Care Memory v2，預設 `false`。 |
| `HERMES_DEMO_CARE_CALLBACK_SOCKET` | Root resident → Bridge repeated-discomfort Unix socket；必須是 private absolute path。 |
| `DEMO_CARE_MEMORY_ROOT` | Private father/mother partition root；repeated-discomfort seed/read/write 都經 `StructuredMemoryStore`。 |

## Trace log schema

Bridge writes append-only JSONL traces to:

```text
{LOG_DIR}/{event_id}.jsonl
{LOG_DIR}/_index.jsonl
```

`_index.jsonl` is append-only. The same `event_id` may have `started`、`completed`、`failed`、`ignored` records. Treat it as an audit index, not the only source of operational status: a duplicate attempt can append `ignored` after the original event already completed. The CLI viewer resolves summary status from the event timeline: `event_failed` wins, then `event_completed`, and `duplicate_event_ignored` is counted as `duplicate_attempts` without overwriting `failed` or `completed`.

Trace record fields:

```text
schema_version, timestamp, run_id, seq, level, component,
event_id, robot_id, source_type, record_type, stage, status,
duration_ms, payload
```

Fixed stage enum:

```text
event_received
input_validated
care_context_built
abnormal_care_confirmation_created
abnormal_care_follow_up_resolved
initial_notification_finished
episode_awaiting_first_response
hermes_follow_up_failed
escalation_notification_finished
hermes_request_prepared
hermes_invocation_finished
hermes_output_validated
memory_actions_completed
command_request_published
command_result_received
event_completed
event_failed
duplicate_event_ignored
```

`seq` is monotonic within each event timeline. `duration_ms` on a stage record means that stage's duration; `event_completed.payload.total_duration_ms` is the whole event duration. `command_result_received` may arrive later and is appended to the same event timeline.

Video v1.1 不新增 trace stage。Media result consumer 在既有
`command_result_received.payload` 保留 `command_action`、`terminal`、三種 session ID、
`playback_state`、`result_delivery`、`cancelled_by_command_id`、`cancel_reason` 與 `actor`。
Trace 另記 `result_disposition`、`side_effect_applied` 與 originating play command。拒絕的
schema、correlation 或 lifecycle result 也使用相同 stage，且不改變 registry state。

Resident deterministic Media dispatch 同樣不新增 trace stage；Bridge 在
`hermes_invocation_finished.payload.resident_dispatch` 記錄 `dispatch_mode`、`intent`、
`video_id`、`resident_id`、`callback_status`、`bridge_command_id` 與
`dispatch_latency_ms`。`callback_status=published` 只表示 Bridge 接受 publication；真實播放
仍須 Android `cmd/result` lifecycle 證據。

All payloads pass through the shared sanitizer in `logging_utils.py`. Hashes use SHA-256. Excerpts use `TRACE_MAX_FIELD_CHARS` and include `truncated=true|false`. Summary mode records prompt/raw output/care context only as length/hash/excerpt; full debug mode is required to store full prompt, full care_context, and full raw Hermes output. Image bytes are never stored; traces only record paths, frame metadata, and validation result.

Failure records include `failed_stage`、`error_code`、`error_message`、`fallback_generated`、`fallback_command_published`、`fallback_command_id` even when a fallback is not produced. The Bridge only records Hermes' explicit JSON fields such as `reasoning_summary`、`cognitive_state`、`risk_reason`、`next_step`、`actions`; it does not record or claim hidden chain-of-thought.

CLI viewer:

```bash
cd /TemiAgent
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --event-id <event_id>
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --full
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --json
```

`--json` prints machine-readable JSON only on stdout.

Common summary fields:

- `completed`: the Bridge validated Hermes output and finished the event path.
- `failed`: validation, Hermes invocation, or output handling failed; inspect `event_failed.payload`.
- `duplicate_attempts`: number of later duplicate event attempts; these do not change the original completed/failed status.
- `command_result`: latest robot command result status appended to the timeline.
- `late_result`: `true` when a command result arrived after the terminal `event_completed` or `event_failed` record.

Privacy and retention:

- Use summary mode (`DEBUG_TRACE_FULL=false`) for normal Demo runs.
- Use full debug mode only for short local debugging. It may store full prompt, full care context, full raw Hermes output, and raw inbound payload.
- Do not use full debug logs as long-term fixtures or report attachments before de-identification.
- Clean up old `LOG_DIR` folders regularly; full debug logs should not be retained long term.

## 測試

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

根目錄整合 smoke test：

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
python3 tools/media_v11_fake_e2e.py
```

## 常見問題

- `missing_image`：ASR event 指向的影像不存在，先檢查 `temi_shared/events/{robot_id}/{event_id}/`。
- `path is outside bridge shared root`：Temi 或 adapter 發出的 path 不在 `TEMI_SHARED_BRIDGE_PATH` 下。
- `invalid_hermes_json`：Hermes 回傳 Markdown、自然語言或破碎 JSON。
- `navigation_target_not_allowed`：導航目標尚未加入 Bridge allowlist 與 skill schema。
- 重複事件被忽略：相同 `event_id` 還在 `EVENT_DEDUP_TTL_SECONDS` 內。

## Lifecycle and Health

Bridge 本身目前沒有獨立 HTTP health endpoint。操作人員應確認：

- process command、working directory 與 PID 屬於本模組；
- MQTT broker 可連線；
- subscribe topics 與 publish result 有對應 event ID；
- trace timeline 出現預期 stage 或明確 `event_failed`；
- resident mode 的 `HERMES_HTTP_URL` health 端點可用。

服務操作必須遵守 [safe service operations](../docs/operations/safe_service_operations.md)。
不要把 resident Hermes 的 `/health` 誤報為 Bridge health。

## Contract Authority and Update-Together Rule

Runtime schema authority：

```text
schemas/asr_final_event.schema.json
schemas/hermes_action_output.schema.json
schemas/temi_command_request.schema.json
schemas/temi_command_result.schema.json
schemas/cross_service_common.schema.json
schemas/resident_identity_result.schema.json
schemas/care_report.schema.json
schemas/care_report_interaction_result.schema.json
```

`docs/schemas/` 是 reader copy。修改任何 payload、action、path、timeout、dedup、trace
或 memory format 時，必須同步更新 parser/validator、producer、consumer、tests、
reader schema、Temi skills、module README 與 operation notes。完整 mapping 見
[contract traceability](../docs/architecture/contract_traceability.md)。
Identity、video 與 care report 的欄位、topic、correlation、privacy 與 migration 見
[canonical cross-service contract](../docs/architecture/canonical_cross_service_contract.md)。

## Known Limitations

- Abnormal perception event 目前由 `event_models.py` 驗證，但沒有獨立 runtime JSON schema。
- `.env.example` 未列出 `BridgeConfig` 的每個 optional care-context setting；以 `config.py` 為實作依據。
- CLI、HTTP、MQTT、Hermes 與 Temi App failure 都可能使事件進入 degraded state；trace completion 不等同 robot action 成功，必須檢查 command result。
- Bridge 只支援 Demo／研究照護流程，不提供醫療診斷或真實緊急通報。
- Bridge consumes (but does not produce) the established identity result topic only when the
  visual-routing Demo flag is enabled. It still does not implement a VLM/identity producer or
  care-report runtime.
- Media registry 只保存目前 Bridge process 的 correlation；Android 仍須依 contract 持久化
  command idempotency 與 restart reconciliation。Bridge restart 不還原既有 session。
- Media producer and native Hermes entry are default-off. Their controlled Demo route additionally
  needs a fresh canonical visual identity result and Android media mapping/result evidence; without
  either, it fails closed and does not publish a media command.
