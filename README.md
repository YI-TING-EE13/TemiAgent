# TemiAgent

最後更新日期：2026-05-31

TemiAgent 是一套以 Temi robot 為實體載具、Hermes Agent 為認知核心的 embodied AI 居家照護助理專案。目標是讓 Temi 能聽見使用者語音、取得同步影像、透過 Hermes 進行情境理解與照護風險判斷，再由安全橋接層把通過驗證的行動發回 robot。

第一年度 Demo 聚焦在可展示、可解釋、可擴充的照護認知架構，而不是一次完成醫療級產品化。

## 目前狀態快照

2026-05-31 盤點結果：

- `temi_backend` legacy live route 已完成硬體實測，可展示 Temi ASR、WebSocket 影像、LM Studio/VLM 與 MQTT speak 閉環。
- `tools/temi_overview_adapter.py` 已可把目前 Android app 的 legacy topics 轉成 canonical Overview contract。
- `hermes_temi_bridge` 的 mock/unit/E2E 路線可在 container 內通過，並支援 mock、CLI、resident HTTP 三種 Hermes invocation mode。
- `tools/hermes_resident_server.py` 已支援多 `--skill-path` preload、`--hermes-home` 與 `--enable-memory`，適合後續真 Hermes Demo。
- 第一年度照護助理 Demo 的三個 scenario 已完成 scope 與 skill 設計；P1 structured memory demo state 已建立，P2 Bridge memory actions 與 Home-ESI output validation 已完成最小實作，P5 Demo 素材已整理；P4 Navigation 本輪先跳過。

## 快速入口

| 需求 | 文件 |
|---|---|
| 全系統架構與 MQTT / payload contract | [docs/architecture/project_overview.md](docs/architecture/project_overview.md) |
| 照護助理任務 scope 與驗收 | [docs/project/hermes_care_assistant_task_readme.md](docs/project/hermes_care_assistant_task_readme.md) |
| 第一年度 Demo 階段任務 | [docs/project/first_year_demo_phase_tasks.md](docs/project/first_year_demo_phase_tasks.md) |
| Demo runbook / 端到端操作 / 腳本 / checklist | [docs/project/first_year_demo_runbook.md](docs/project/first_year_demo_runbook.md)、[docs/project/first_year_demo_e2e_operation_manual.md](docs/project/first_year_demo_e2e_operation_manual.md)、[docs/project/first_year_demo_scenario_script.md](docs/project/first_year_demo_scenario_script.md)、[docs/project/first_year_demo_acceptance_checklist.md](docs/project/first_year_demo_acceptance_checklist.md) |
| 照護助理完整交接背景 | [docs/project/hermes_care_assistant_handoff.md](docs/project/hermes_care_assistant_handoff.md) |
| 本地整合 runbook | [docs/operations/temi_integration_runbook.md](docs/operations/temi_integration_runbook.md) |
| 目前機器的 Temi streaming 狀態 | [docs/operations/temi_streaming_local_runbook.md](docs/operations/temi_streaming_local_runbook.md) |
| Agent 開發者摘要 | [Agent.md](Agent.md) |

## 系統目標

本專案把傳統「機器人 app + 後端模型」拆成清楚的安全邊界：

- Temi 負責看、聽、說、移動等硬體互動。
- MQTT 負責事件與命令傳遞。
- Shared volume 負責傳遞 ASR 對齊影像路徑。
- HermesTemiBridge 負責驗證事件、影像、Hermes JSON 與 action schema。
- Hermes Agent 負責理解情境、讀取照護記憶、判斷 Home-ESI 風險等級與規劃下一步。

核心原則：

- Hermes 不直接控制硬體。
- Hermes 不直接 publish MQTT。
- 圖片不塞進 MQTT，只傳 path。
- 所有 robot actions 都必須是 JSON，並由 Bridge 驗證後才執行。
- 第一版緊急通知只做 mock notification，不宣稱真實通報 119。

## 模組索引

| 模組 | README | 職責 |
|---|---|---|
| `hermes_temi_bridge/` | [hermes_temi_bridge/README.md](hermes_temi_bridge/README.md) | Canonical MQTT event receiver、Hermes caller、JSON/action validator、command dispatcher。 |
| `hermes-agent/` | [hermes-agent/README.TemiAgent.md](hermes-agent/README.TemiAgent.md) | Hermes 認知核心與 resident runtime；上游說明見 `hermes-agent/README.md`。 |
| `hermes-skills/` | [hermes-skills/README.md](hermes-skills/README.md) | Temi 專用 skill mirror：robot control、care memory、Home-ESI。 |
| `temi_backend/` | [temi_backend/README.md](temi_backend/README.md) | 已驗證 legacy route：WebSocket 影像、ASR、LM Studio/VLM、MQTT actions。 |
| `mqtt/` | [mqtt/README.md](mqtt/README.md) | Mosquitto broker 設定與 MQTT topic contract。 |
| `memory/` | [memory/README.md](memory/README.md) | Demo structured memory：男性 persona、提醒、當日狀態、event log、summary artifacts。 |
| `temi_shared/` | [temi_shared/README.md](temi_shared/README.md) | ASR event 對齊影像與 metadata shared volume。 |
| `tools/` | [tools/README.md](tools/README.md) | Resident Hermes、Overview adapter、mock E2E、連線檢查與 Demo scripts。 |
| `docs/` | [docs/README.md](docs/README.md) | 架構、操作、計畫交接、schema 與歷史文件。 |
| `logs/` | [logs/README.md](logs/README.md) | Runtime logs 與 Demo observation artifacts。 |
| `計劃書/` | [計劃書/README.md](計劃書/README.md) | 原始研究計畫書與專案背景資料。 |

## 整體流程

```text
User speaks to Temi
  -> Temi Android ASR final + video frames
  -> MQTT ASR event
  -> shared event images in temi_shared/
  -> HermesTemiBridge validates event and image paths
  -> Hermes Agent reasons with Temi skills
  -> Bridge validates JSON action plan
  -> MQTT command request
  -> Temi speaks / turns / navigates / stops
  -> command result and logs
```

目前實作同時保留三條路線：

| 路線 | 狀態 | 用途 |
|---|---|---|
| Legacy live route | 已驗證 | `temi_backend` + LM Studio/VLM，適合快速展示 Temi ASR、影像與 TTS 閉環。 |
| Overview canonical route | 已可運作 | Legacy topics 經 `tools/temi_overview_adapter.py` 轉成 canonical ASR event，再由 Bridge 呼叫 Hermes。 |
| Resident Hermes HTTP mode | 已驗證 | 避免 Hermes CLI cold start，Demo 優先使用。 |

## 照護助理 Demo Scope

第一年度 Demo 聚焦三個 scenario。這裡是目標 scope；實作驗收會在下一階段補齊 structured memory 與 memory action 執行層。

| Scenario | 目標 | 期望輸出 |
|---|---|---|
| 日常提醒 | 個人化提醒與完成紀錄 | `speak`、`mark_reminder_done`、`log_event`。 |
| 不適 / 求助 | 中風險主動關懷 | `cognitive_state.home_esi_level = L2`、`ask_clarification`、`log_event`。 |
| 疑似跌倒 / 高風險 | 高風險確認與 mock 通報 | `home_esi_level = L1`、安全確認、`notify_caregiver_mock`、abnormal event。 |

照護認知使用三個 Hermes skills：

- `temi-robot-control`：robot action contract 與安全限制。
- `temi-care-memory`：structured care memory 讀寫規則。
- `temi-home-esi`：Home-ESI Lite 風險分級。

## 常用指令

Bridge unit tests：

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

Backend tests：

```bash
cd /TemiAgent/temi_backend
uv run pytest
```

Local mock E2E：

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

First-year Demo cases：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

Resident Hermes：

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md
```

Docker mock stack：

```bash
cd /TemiAgent
docker compose up --build
```

## 文件維護規則

- 根 README 只保留系統入口、模組索引與穩定工作流。
- 模組實作細節寫在各模組 README。
- 跨模組操作流程寫在 `docs/operations/`。
- 架構與 payload contract 寫在 `docs/architecture/`。
- 照護任務與計畫背景寫在 `docs/project/`。
- 搬移或重新命名文件後，請用 `rg` 搜尋舊路徑並同步更新引用。
