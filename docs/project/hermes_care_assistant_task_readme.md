# Hermes 居家照護助理大腦任務 README

最後更新日期：2026-05-31

## 本文件維護規則

這份文件是 Hermes 居家照護助理大腦改造任務的快速入口，不取代 `docs/project/hermes_care_assistant_handoff.md`。之後只要本任務的 scope、skill 分工、記憶策略、resident 啟動方式、Demo scenario 或驗收標準有變更，都要同步更新本文件，讓後續維護者可以不用重讀完整對話就快速進入狀況。

## 任務目標

把 Hermes 從一般對話 agent 調整成 Temi 居家照護機器人的認知核心。第一年度 Demo 目標不是完整產品化，而是做出可展示、可解釋、可擴充的照護認知架構。

責任分工：

- Hermes：理解情境、讀取記憶、判斷風險、規劃下一步。
- HermesTemiBridge：驗證事件、影像路徑、Hermes JSON、action schema，並安全執行或記錄。
- Temi：負責看、聽、說、移動等硬體互動。

安全邊界：

- Hermes 不直接控制硬體。
- Hermes 不直接 publish MQTT。
- Hermes 不直接寫照護權威資料；它輸出 JSON action plan，由 Bridge 執行。
- 真實通知家屬或 119 不在第一版 scope；Demo 一律使用 mock notification。

## 目前實作狀態

2026-05-31 盤點：

已完成：

- `temi_backend` legacy route 已完成實機路線驗證，適合作為快速展示備援。
- Overview adapter 已能將 legacy Android topics 轉成 canonical ASR event，並輸出三張影像 path。
- HermesTemiBridge 已支援 ASR event validation、image path validation、Hermes JSON parsing、action validation、command publish、event dedup 與 result logging。
- Bridge mock/unit/local E2E 在 container 中通過：Bridge unittest 33 tests、backend pytest 14 tests、root mock E2E `status: ok`。
- Resident Hermes HTTP server 已支援多 skill preload，並可選擇開啟 Hermes memory/profile。
- 三個 Temi care 核心 skills 與 `temi-discord-care-assistant` 入口 skill 已存在於 `hermes-agent/skills/temi-*`；mirror 同步於 `hermes-skills/`。
- Discord/gateway 對話已補上 Temi 身份與 skill 路由文件：`/TemiAgent/.hermes.md`、`hermes-agent/docker/SOUL.md`、`hermes-agent/skills/temi-discord-care-assistant/`。
- 第一年度 Demo 階段任務已整理為 P0-P5，見 `docs/project/first_year_demo_phase_tasks.md`。
- P1 structured memory demo state 已建立於 `memory/`，目前 persona 設定為男性 Demo 長者 `王先生`。
- P2 Bridge memory actions 已完成最小實作：`log_event`、`mark_reminder_done`、`generate_summary`、`notify_caregiver_mock`。
- P3 deterministic Demo case runner 已完成，P5 runbook / e2e operation manual / scenario script / checklist 已整理。
- Bridge validator 已強制要求 `cognitive_state.home_esi_level` 與 `cognitive_state.risk_reason`。

尚未完成，留待 Demo 驗收階段：

- `update_memory`、`set_reminder` 尚未接成 Bridge 內部 actions；第一年度 Demo 先以 `log_event` 與 `mark_reminder_done` 覆蓋必要流程。
- 三個 Demo case 尚未產生完整的 raw output、parsed output、command request、memory diff/event log 與 daily summary。

## Skill 分工

第一版採三個核心 skill 分層，避免把照護規則、記憶規則與 robot action contract 混在同一份 prompt；另加一個 Discord/gateway 入口 skill，負責把自然語句導向核心 Temi skills。

| Skill | 角色 | 主要內容 |
|---|---|---|
| `temi-robot-control` | Robot action contract | Temi 可執行 action、JSON-only output、安全動作限制 |
| `temi-care-memory` | 照護記憶操作規則 | structured care memory、Hermes memory/provider 同步、提醒與事件資料流 |
| `temi-home-esi` | 風險分級規則 | Home-ESI Lite 的 `Normal/L3/L2/L1` 判斷與行動優先序 |
| `temi-discord-care-assistant` | Discord/gateway 入口提示 | 讓 Hermes 在 Discord 遇到手勢、相機、指物、照護語句時知道要載入 Temi skills |

Skill 路徑規劃：

```text
hermes-agent/skills/temi-robot-control/
hermes-agent/skills/temi-care-memory/
hermes-agent/skills/temi-home-esi/
hermes-agent/skills/temi-discord-care-assistant/

hermes-skills/temi-robot-control/
hermes-skills/temi-care-memory/
hermes-skills/temi-home-esi/
hermes-skills/temi-discord-care-assistant/
```

`hermes-agent/skills/` 是 resident Hermes 主要讀取位置；`hermes-skills/` 是 repo root mirror，維持目前 `temi-robot-control` 的雙路徑慣例。

### Discord/gateway 補充

Discord gateway 不一定會走 `tools/hermes_resident_server.py` 的 `--skill-path` preload；它通常依賴 `$HERMES_HOME/SOUL.md`、工作目錄 project context 與 skills index。為了讓 Hermes 知道自己仍是 Temi 居家照護助理，本專案新增：

- `/TemiAgent/.hermes.md`：project context，列出 Temi role、三個核心 skills、相機/手勢處理規則。
- `hermes-agent/docker/SOUL.md`：新 Docker/gateway profile 的預設身份。
- `hermes-agent/skills/temi-discord-care-assistant/`：可被 skills index 搜尋的 Discord/gesture/camera 路由 skill。

使用者在 Discord 說「看我的手勢」、「看一下相機」、「我指的是什麼」時，Hermes 應先找圖片附件、`temi_shared/` path 或 Bridge frame paths；有影像才分析，沒有影像就請使用者觸發/傳送 Temi camera event 或附圖，不要虛構畫面。

## 記憶分層

本任務採 Hermes memory + structured memory 混合架構。

| 層級 | 用途 | 權威性 |
|---|---|---|
| Hermes builtin memory | 穩定偏好、長期角色背景、照護互動風格 | 背景知識，不作為事件權威紀錄 |
| Holographic provider | 本地 SQLite fact recall、可搜尋照護事實 | 語意檢索層，不取代 event log |
| JSON / JSONL | profile、daily state、reminders、event log、abnormal events、summary | 權威照護狀態與 Demo 驗收來源 |

建議資料位置：

```text
memory/
  profile.json
  daily_state.json
  reminders.json
  event_log.jsonl
  summaries/
  abnormal_events/
```

Hermes 可以透過 Bridge 注入的摘要理解這些資料，也可以輸出 memory 類 actions，例如 `log_event`、`mark_reminder_done`、`generate_summary`、`notify_caregiver_mock`。實際寫入 JSON/JSONL 目前由 Bridge structured memory store 完成；Holographic provider 或 MCP memory tools 可留到 Demo 穩定後再接。

目前 P1 Demo state 已建立：

| 檔案 | Demo 用途 |
|---|---|
| `memory/profile.json` | 男性合成 persona，稱呼 `王先生`，不含真實個資。 |
| `memory/reminders.json` | 早餐後服藥與補充水分兩個 active reminders。 |
| `memory/daily_state.json` | 今日風險狀態、active reminders、recent event ids。 |
| `memory/event_log.jsonl` | 追加式事件紀錄；目前包含初始化紀錄。 |
| `memory/abnormal_events/` | 後續 L1 / 重要 L2 mock artifact。 |
| `memory/summaries/` | 後續每日照護摘要 artifact。 |

## Resident Server 實作注意

現有 resident mode 是第一年度 Demo 的優先真實 Hermes 路線，因為它避免每次 ASR event 都重新啟動 `hermes -z`。

本任務需要 resident server 支援多個 skill preload：

```bash
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md
```

後續啟用 `care-assistant` Hermes profile 與 memory 時，resident mode 不應固定 `skip_memory=True`。建議改成可設定：

```text
--enable-memory
--hermes-home /root/.hermes/profiles/care-assistant
--toolsets memory
```

目前 resident server 支援 multi-skill preload，也支援用 `--hermes-home` 與 `--enable-memory` 明確開啟 care-assistant profile/memory。預設仍保持 memory disabled，方便快速 smoke test。

## Demo Scenario

### Scenario A：日常提醒

目標：展示個人化提醒與完成紀錄。

期望流程：

1. Bridge 注入目前 active reminders。
2. Hermes 產生提醒用 `speak` action。
3. 使用者語音或手勢確認。
4. Hermes 輸出 `mark_reminder_done` 與 `log_event`。
5. Bridge 更新 reminders 與 event log。

### Scenario B：不適 / 求助 L2

目標：展示中風險主動關懷，不過度升級。

期望流程：

1. 使用者說「我有點不舒服」。
2. Hermes 根據 ASR、recent events、影像狀態判斷 `home_esi_level: L2`。
3. Hermes 輸出 `ask_clarification` 與 `log_event`。
4. Bridge 記錄 risk reason。

### Scenario C：疑似跌倒 / 高風險 L1

目標：展示高風險分級與 mock 通報。

期望流程：

1. 影像或 mock event 表示疑似跌倒、無回應或明確求救。
2. Hermes 判斷 `home_esi_level: L1`。
3. Hermes 先輸出安全確認語句。
4. 若無回應或明確求救，輸出 `notify_caregiver_mock`。
5. Bridge 寫入 abnormal event 與 event log。

## 驗收標準

必須完成：

- Hermes output 包含 `cognitive_state.home_esi_level`。
- Bridge 能驗證 JSON-only action plan。
- Robot actions 只發布 Temi 支援的安全 actions。
- Memory actions 由 Bridge 內部處理，不轉發給 Temi。
- 三個 Demo scenario 都能產生 raw output、parsed output、command request、memory diff 或 event log。
- Demo 結束後可產生今日照護摘要。

不要求第一版完成：

- 醫療級診斷。
- 真實撥打 119。
- 大型知識圖譜。
- 完整病歷系統。
- 所有模型都在 Temi 本機即時推論。

## 測試清單

文件測試：

- 本 README path 存在。
- `docs/project/hermes_care_assistant_handoff.md` 有連到本 README。
- 本 README 包含 skill 分工、記憶分層、resident multi-skill path、更新規則。

程式測試：

- resident server 單一 `--skill-path` 仍相容。
- resident server 多個 `--skill-path` 會按 CLI 順序全部注入 prompt。
- resident server 預設仍停用 memory；加上 `--enable-memory` 時才載入 Hermes memory。
- skill path 不存在時有清楚 warning，不靜默成功。
- Bridge validator 強制檢查 `cognitive_state.home_esi_level`。
- Bridge memory store 可更新 reminder、追加 event log、寫入 mock abnormal event。

整合測試：

- 使用四個 skills 啟動 resident server。
- Bridge resident HTTP mode 仍能取得 JSON-only Hermes output。
- 三個 Demo case 的 output 都包含 `cognitive_state.home_esi_level`。
- `tools/demo_case_runner.py` 可產生三個固定 Demo case artifacts。

## 後續更新紀錄

- 2026-05-31：新增第一年度 Demo P0-P5 階段任務文件；完成 P1 structured memory demo state，男性 persona 設定為 `王先生`。
- 2026-05-31：完成 P2 最小實作，Bridge 支援 Home-ESI schema validation 與四個 memory/demo actions。
- 2026-05-31：完成 P3 deterministic Demo case runner，可產生提醒、不適 L2、疑似跌倒 L1 三個案例 artifacts。
- 2026-05-31：整理 P5 展示素材，新增 Demo runbook、端到端串接操作手冊、scenario script 與 acceptance checklist；P4 Navigation 本輪先跳過。
- 2026-05-30：補上目前實作狀態；確認整合底座已通過 container 內測試，照護記憶與 Demo actions 留待下一階段。
- 2026-05-31：補上 Discord/gateway Temi 身份與 `temi-discord-care-assistant` skill，讓「看手勢 / 看相機」可導向 Temi camera/vision skills。
- 2026-05-19：建立本任務 README，記錄三 skill 分工、混合記憶策略與 resident multi-skill preload 需求。
