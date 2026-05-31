# HermesTemiBridge 模組 README

最後更新日期：2026-05-31

## 本文件維護規則

這份 README 是 `hermes_temi_bridge/` 的快速入口。只要 MQTT contract、Hermes invocation mode、action schema、path translation、log format 或測試方式改變，都要同步更新本文件，讓後續維護者可以只讀本模組 README 就進入狀況。

## 模組定位

HermesTemiBridge 是 Temi 與 Hermes 之間的安全邊界。它不是高階推理核心，也不是 Temi Android App；它負責接收 Temi 事件、驗證資料、呼叫 Hermes、驗證 Hermes JSON output，最後只把安全的 command request 發回 MQTT。

```text
Temi Android / Overview Adapter
  -> MQTT temi/{robot_id}/asr/final
  -> HermesTemiBridge
  -> Hermes CLI / Resident HTTP / Mock Hermes
  -> validated temi/{robot_id}/cmd/request
  -> Temi Android
```

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `mqtt/` | Bridge subscribe ASR/result topics，publish command request。 |
| `temi_shared/` | Bridge 讀取 ASR event 內的三張影像路徑，並做 Bridge path 到 Hermes path 的轉換。 |
| `hermes-agent/` | CLI mode 與 resident HTTP mode 會呼叫本地 Hermes runtime。 |
| `hermes-skills/` / `hermes-agent/skills/temi-*` | Hermes prompt 的 robot action、care memory、Home-ESI 規則來源。 |
| `docs/schemas/` | 文件用 schema 副本；本模組執行時以 `hermes_temi_bridge/schemas/` 為準。 |
| `tools/hermes_resident_server.py` | 提供低延遲 HTTP invocation endpoint。 |

## 核心職責

- 連線到 MQTT broker。
- Subscribe `temi/+/asr/final` 與 `temi/+/cmd/result`。
- 驗證 ASR event schema 與 robot allowlist。
- 驗證三張影像存在、大小合理，且位於 shared root 內。
- 將 `/var/lib/temi_shared/...` 轉成 Hermes 可讀的 `/shared/temi/...` 或本機等價路徑。
- 建立 Hermes prompt。
- 支援 `mock`、`cli`、`http` 三種 Hermes invocation mode。
- 解析 Hermes JSON-only output，容忍常見 Markdown code fence 包裝。
- 驗證 action schema 與安全限制。
- 將 robot actions 發布到 `temi/{robot_id}/cmd/request`。
- 執行 Bridge-internal memory/demo actions，包含 event log、reminder done、summary 與 mock caregiver notification。
- 記錄 raw output、parsed output、robot command request、memory action result、command result 與錯誤。

## 目前狀態與限制

2026-05-31 盤點：

- Hardware-free path 已驗證：`uv run python -m unittest discover -s tests` 通過 38 tests。
- Root local mock E2E 已驗證：`python3 tools/e2e_test_runner.py` 回傳 `status: ok`。
- HTTP resident mode 已完成 client 與 server wiring；實機紀錄顯示 warm resident latency 約 7-8 秒級，比 CLI cold start 約 97 秒明顯降低。
- Action validator 會強制檢查 `cognitive_state.home_esi_level` 與 `cognitive_state.risk_reason`。
- Robot-facing actions：`speak`、`ask_clarification`、`turn`、`navigate`、`stop`、`noop`。
- Bridge-internal memory/demo actions：`log_event`、`mark_reminder_done`、`generate_summary`、`notify_caregiver_mock`。
- 只有 robot-facing actions 會 publish 到 `temi/{robot_id}/cmd/request`；memory/demo actions 只寫入 `MEMORY_DIR`。

## 不負責的事

- 不自行做照護推理或意圖判斷。
- 不直接操作 Temi SDK 或硬體。
- 不把圖片 binary 放入 MQTT。
- 不信任 Hermes 任意輸出；所有 action 都必須通過 schema validation。
- 不執行 shell command 或任意工具呼叫。

## 主要檔案

```text
hermes_temi_bridge/
  src/hermes_temi_bridge/
    main.py                 # CLI 入口與 runtime wiring
    mqtt_client.py          # MQTT subscribe/publish
    event_models.py         # ASR event parsing/validation
    image_resolver.py       # shared path validation and translation
    hermes_client.py        # mock/cli/http Hermes invocation
    action_validator.py     # Hermes action contract validation
    command_dispatcher.py   # command request publishing
    idempotency.py          # event_id dedup
  schemas/                  # runtime JSON schemas
  tests/                    # hardware-free unittest suite
```

## 常用模式

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
| `MEMORY_DIR` | structured memory root，預設 `memory`。 |

## 測試

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

根目錄整合 smoke test：

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

## 常見問題

- `missing_image`：ASR event 指向的影像不存在，先檢查 `temi_shared/events/{robot_id}/{event_id}/`。
- `path is outside bridge shared root`：Temi 或 adapter 發出的 path 不在 `TEMI_SHARED_BRIDGE_PATH` 下。
- `invalid_hermes_json`：Hermes 回傳 Markdown、自然語言或破碎 JSON。
- `navigation_target_not_allowed`：導航目標尚未加入 Bridge allowlist 與 skill schema。
- 重複事件被忽略：相同 `event_id` 還在 `EVENT_DEDUP_TTL_SECONDS` 內。
