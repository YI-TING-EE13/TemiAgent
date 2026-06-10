# Hermes 居家照護助理大腦交接文件

給接手 TemiAgent / Hermes 電腦上的 Codex：

這份文件說明我們希望把現有 Hermes agent、Harness/MCP/Skills 機制，以及 Temi 機器人整合成符合國科會計畫子計畫三目標的「居家照護助理大腦」。目前先不追求完整產品化，而是要做出第一年度 Demo 可展示、可解釋、可繼續擴充的認知架構。

任務維護入口：後續實作決策、skill 分工、resident mode 啟動方式與更新紀錄請同步維護在 `docs/project/hermes_care_assistant_task_readme.md`。

## 1. 最終目標

我們要讓 Hermes 不只是聊天機器人，而是 Temi 居家照護機器人的認知核心。它需要能：

1. 理解使用者語音、影像快照與機器人狀態所代表的照護情境。
2. 查詢與更新長者的個人資料、日常事件、提醒狀態與異常紀錄。
3. 根據情境判斷照護風險，例如正常、需要關懷、需要通報。
4. 透過 Bridge / MCP / Skills 安全地發出行動，例如說話、詢問、提醒、停止、導航、紀錄或模擬通報。
5. 將事件累積成可回顧的照護記憶，並產生今日摘要或健康報告草稿。

一句話：Hermes 負責「理解、記憶、判斷、規劃」，Temi 負責「看、聽、說、移動」，HermesTemiBridge 負責「驗證與安全執行」。Discord/gateway 對話也必須保留這個身份，不可把「看手勢 / 看相機」誤判成一般聊天能力限制。

## 2. 目前系統現況

目前第一年 Demo 的硬體載具改為 Temi 機器人。舊計畫書與早期簡報中提到的 AGV / Hello Robot / 知識圖譜，不再是第一年實作重點。

現有 TemiAgent 系統大致分成三條路線：

| 路線 | 狀態 | 用途 |
|---|---|---|
| Legacy live route | 已驗證 | Temi ASR + WebSocket 影像 + `temi_backend` + LMStudio/VLM，適合快速 Demo |
| Overview contract route | 已可運作 | Adapter 將舊 topic 轉成 `temi/temi-01/asr/final`，再由 HermesTemiBridge 呼叫 Hermes |
| Resident Hermes HTTP mode | 已驗證 | 避免 Hermes CLI cold start，實測約 8 秒級，較適合真實 Hermes Demo |

關鍵元件責任：

| 元件 | 責任 |
|---|---|
| Temi Android App | ASR、camera、TTS、navigation、基本硬體互動 |
| MQTT Broker | 傳遞 ASR event、command request、command result |
| Overview Adapter | 將目前 Android app 的 legacy topic 轉成 Overview contract |
| HermesTemiBridge | 驗證事件、影像路徑、Hermes JSON、action schema，並發布 command |
| Hermes Agent | 使用 skill / tool 進行情境理解與 action 規劃 |
| `temi-robot-control` Skill | 規範 Hermes 可以輸出的安全 robot actions |
| `temi-discord-care-assistant` Skill | 讓 Discord/gateway 對話知道 Hermes 可使用 Temi camera/gesture/care skills |

重要限制：

1. Hermes 不應直接碰硬體、不應直接 publish MQTT、不應繞過 Bridge。
2. 所有 robot action 都必須是 JSON，並由 Bridge schema validate。
3. Real Hermes CLI mode 太慢，不適合第一年現場展示；優先使用 resident HTTP mode。
4. Android app 原始碼在另一台電腦，這裡文件與規劃需可對接目前已安裝在 Temi 上的 app。

## 3. 計畫書要求如何轉換成新架構

原計畫書要求仍要達成，但技術路線可以更新。

| 計畫書要求 | 新架構對應 |
|---|---|
| 多模態異常行為偵測 | Temi camera snapshots + VLM/vision backend + Hermes 情境判斷 |
| 個人化日常提醒 | `reminders.json` + `profile.json` + Hermes planner |
| 智慧行程管理 | Reminder tool / MCP resource + daily state |
| 隱私保護資料庫 | 本地 event log、影像路徑、必要時去識別化，避免雲端裸傳個資 |
| 資料檢索 | MCP resources / memory tools / structured log retrieval |
| 緊急通報機制 | Home-ESI v2 decision-tree policy skill + notify/log/ask actions |
| 個人健康報告 | event log + daily summary + report generator |
| 知識圖譜 | 不做傳統 KG，改用 structured memory + retrieval + skills |

接手時不要把時間花在建立大型知識圖譜。現在比較合理的作法是把記憶拆成清楚、可驗證、可被 Hermes 查詢與更新的結構化檔案或 resource。

## 4. Hermes 認知模組建議架構

請將 Hermes 大腦拆成五個邏輯模組，不一定要寫成五個服務，但 prompt、skill、tool、schema 要能反映這些責任。

### 4.1 Situation Perception

目的：理解這次事件發生了什麼。

輸入：

- ASR final text
- 三張影像快照路徑：T-1000、T-500、T
- Temi state
- 最近事件摘要
- 可用工具列表

輸出：

- 使用者意圖：閒聊、詢問、提醒確認、求助、拒絕、導航、停止等
- 視覺狀態：是否有人、是否疑似跌倒、是否需要更多資訊
- 事件類型：normal_interaction、care_reminder、possible_distress、emergency_candidate

### 4.2 Care Memory

目的：記住長者個人資料、日常狀態、提醒與事件。

不要使用重型知識圖譜。第一版使用 JSON / JSONL 即可。

建議資料結構：

```text
memory/
  profile.json
  daily_state.json
  reminders.json
  event_log.jsonl
  summaries/
    2026-05-19.md
  abnormal_events/
    evt_xxx.json
```

`profile.json` 範例：

```json
{
  "user_id": "elder_001",
  "preferred_name": "阿嬤",
  "language": "zh-TW",
  "care_preferences": {
    "speak_style": "溫和、簡短、清楚",
    "confirmation_style": "需要使用者口頭或手勢確認"
  },
  "medication_schedule": [
    {
      "name": "morning_medicine",
      "time": "08:30",
      "instruction": "早餐後服藥"
    }
  ],
  "caregiver_contacts": [
    {
      "name": "家屬",
      "role": "primary",
      "channel": "demo_mock"
    }
  ]
}
```

`daily_state.json` 範例：

```json
{
  "date": "2026-05-19",
  "risk_state": "normal",
  "last_seen_location": "客廳",
  "last_interaction": "提醒吃藥，使用者以 OK 手勢確認",
  "active_reminders": [],
  "recent_event_ids": ["evt_001"]
}
```

`event_log.jsonl` 範例：

```json
{
  "event_id": "evt_001",
  "timestamp": "2026-05-19T09:12:00+08:00",
  "source": "temi_asr_vision",
  "asr_text": "我有點不舒服",
  "perception": {
    "intent": "possible_help_request",
    "visual_status": "seated"
  },
  "risk": {
    "home_esi_level": "L2",
    "reason": "使用者表示不適，但未觀察到跌倒或無反應"
  },
  "actions_taken": ["ask_clarification", "log_event"],
  "outcome": "waiting_for_user_response"
}
```

### 4.3 Risk Cognition

目的：做照護風險分級。

第一年不需要完整醫療分診，但要有 Home-ESI v2 decision-tree policy。

Home-ESI v2 延續 **Home Emergency Severity Index Lite**（居家版簡化急診嚴重度分級）的 demo 定位，並改為明確 decision-tree policy。它是本計畫為居家照護情境自訂的風險分級規則，概念參考醫療急診常見的 **Emergency Severity Index, ESI**，但不是正式醫療分診系統，也不能取代醫師、護理師或 119 的判斷。它的用途是讓 Hermes 在 Demo 中能用一致、可解釋的方式判斷「現在應該一般回應、主動關懷，還是進入緊急通報流程」。

| 等級 | 意義 | 行動 |
|---|---|---|
| L1 | 高風險，可能需要立即處置 | 停止/靠近前先安全確認、詢問狀況、模擬通知家屬或 119、寫入異常事件 |
| L2 | 中風險，需要主動關懷 | 詢問、提醒、建議休息或量測、通知家屬可選、寫入事件 |
| L3 | 輕度事件或一般提醒 | 一般回應、紀錄、必要時安排提醒 |
| Normal | 無照護風險 | 正常對話或執行安全 action |

請把 Home-ESI v2 decision-tree 規則做成 self-contained skill，並保留完整 reference 供審查；不要只寫在 Bridge prompt 裡。Hermes 應該可以明確輸出：

```json
{
  "home_esi_level": "L2",
  "risk_reason": "使用者主動表示不舒服，需要追問但尚未達立即通報條件",
  "required_action": "ask_clarification"
}
```

### 4.4 Care Planner

目的：根據 perception + memory + risk 產生下一步行動。

可用 actions 應由 Bridge / skill schema 控制。第一年建議支援：

- `speak`
- `ask_clarification`
- `navigate`
- `turn`
- `stop`
- `log_event`
- `update_memory`
- `set_reminder`
- `mark_reminder_done`
- `generate_summary`
- `notify_caregiver_mock`
- `noop`

Hermes action 輸出必須 JSON-only。不要輸出 Markdown、解釋文字或 shell command。

建議 Hermes output 加上 `cognitive_state`，方便 debug：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "robot_id": "temi-01",
  "confidence": 0.86,
  "cognitive_state": {
    "intent": "possible_help_request",
    "home_esi_level": "L2",
    "memory_updates": ["event_log"],
    "next_step": "ask_clarification"
  },
  "reasoning_summary": "使用者表示不舒服，需要先追問狀況並記錄事件。",
  "actions": [
    {
      "action_id": "act_001",
      "type": "ask_clarification",
      "text": "你是哪裡不舒服？會頭暈、胸悶，還是剛剛有跌倒嗎？",
      "language": "zh-TW"
    },
    {
      "action_id": "act_002",
      "type": "log_event",
      "event_type": "possible_distress",
      "home_esi_level": "L2"
    }
  ]
}
```

### 4.5 Reflection / Summary

目的：把事件整理成長期照護記憶。

需要做兩種摘要：

1. 即時事件摘要：每次異常或提醒完成後寫入 event log。
2. 每日照護摘要：可以在 Demo 結束時生成，回答「今天發生了什麼」。

每日摘要範例：

```markdown
# 2026-05-19 照護摘要

- 今日提醒：早餐後服藥提醒 1 次，使用者已確認。
- 異常事件：09:12 使用者表示不舒服，系統判定 L2，已追問並記錄。
- 互動狀態：語音互動正常，未出現無回應或跌倒確認事件。
- 建議：若下午再次表示不適，建議通知家屬確認。
```

## 5. 第一年度 Demo 目標

第一年 Demo 不要做得太散。請聚焦三個可展示 scenario。

### Scenario A：日常提醒

流程：

1. Hermes 查詢 reminder。
2. Temi 說：「阿嬤，現在是早餐後服藥時間。」
3. 使用者用語音或 OK 手勢確認。
4. Hermes 更新 `reminders.json` 與 `event_log.jsonl`。
5. Demo 可查詢：「今天吃藥提醒完成了嗎？」

驗收：

- Temi 能說出提醒。
- Hermes 能記錄提醒已完成。
- 事件可被查詢並生成摘要。

### Scenario B：不適/求助

流程：

1. 使用者說：「我有點不舒服。」
2. Hermes 查 profile、recent events、影像狀態。
3. Hermes 判斷 L2。
4. Temi 追問：「哪裡不舒服？需要我通知家人嗎？」
5. Hermes 記錄事件。

驗收：

- Hermes 不應直接假設 L1。
- 需要先追問，除非影像/語音/生理訊號支持高風險。
- event log 中要包含風險等級與理由。

### Scenario C：疑似跌倒/高風險

流程：

1. 影像或 mock event 表示使用者跌倒/無回應。
2. Hermes 判斷 L1。
3. Temi 先語音確認狀態。
4. 若無回應或明確求救，輸出 `notify_caregiver_mock`。
5. 寫入 abnormal event。

驗收：

- `home_esi_level` 為 L1。
- 有明確 `risk_reason`。
- 有 `notify_caregiver_mock` 或等價 demo action。
- 有異常事件紀錄與摘要。

## 6. 建議接手實作任務

請依序完成，不要一開始就重構全部系統。

### Task 1：建立照護記憶 schema

新增或確認：

```text
memory/
  profile.json
  daily_state.json
  reminders.json
  event_log.jsonl
```

若已有相似資料夾，沿用既有位置，但請補文件。

### Task 2：新增 memory MCP tools 或等價 Harness tools

至少需要：

```text
memory.read_profile
memory.read_daily_state
memory.list_recent_events
memory.append_event
memory.update_daily_state
memory.list_reminders
memory.mark_reminder_done
summary.generate_daily_summary
```

如果目前 Harness 不方便新增正式 MCP tool，可以先在 resident Hermes server 或 Bridge 側提供等價 function calling layer。

### Task 3：擴充 `temi-robot-control` Skill

Skill 需加入：

1. 居家照護助理角色定義。
2. Home-ESI v2 decision-tree 分級規則。
3. 記憶讀寫規則。
4. JSON-only output contract。
5. 安全規則：不直接下醫療診斷、不自行宣稱已通知真實 119，Demo 一律使用 mock notify。
6. 行動優先序：安全 > 釐清 > 記錄 > 一般對話。

### Task 4：擴充 Hermes output schema

在不破壞現有 Bridge 的情況下，加入或允許：

```json
{
  "cognitive_state": {
    "intent": "string",
    "home_esi_level": "Normal|L1|L2|L3",
    "risk_reason": "string",
    "memory_updates": ["event_log", "daily_state"],
    "next_step": "string"
  }
}
```

並支援 action types：

```text
log_event
update_memory
set_reminder
mark_reminder_done
generate_summary
notify_caregiver_mock
```

若 Bridge 現階段只允許 robot commands，則先讓這些 memory actions 在 Bridge 內部執行，不轉發給 Temi。

### Task 5：完成三個 Demo case

請建立 mock event 或 test runner：

```text
demo_case_daily_reminder
demo_case_user_discomfort
demo_case_possible_fall
```

每個 case 都要產生：

1. Hermes raw output
2. parsed output
3. command request
4. memory diff 或 event log
5. final summary

### Task 6：延遲與模式選擇

Real Hermes CLI mode 太慢。請優先使用：

```text
HERMES_INVOKE_MODE=http
resident Hermes server
```

第一年 Demo 可以分成兩種模式：

| 模式 | 用途 |
|---|---|
| Mock / fast mode | 展示完整 Temi 動作閉環 |
| Resident Hermes mode | 展示真正 Hermes 認知能力 |

若現場 Demo 時延遲仍過高，可以讓感知/記憶/決策用 mock 或預熱 resident mode，但文件上要清楚說明真實路線。

## 7. 驗收標準

接手後請以以下標準判斷是否「Hermes 已成為居家照護助理大腦」。

### 必須通過

1. Hermes 能根據 ASR + context 產生符合 schema 的 JSON actions。
2. Hermes 能查詢 profile/reminders/recent events。
3. Hermes 能把每次重要互動寫入 event log。
4. Hermes 能對不適/跌倒情境輸出 Home-ESI 風險等級與理由。
5. Bridge 能驗證並安全執行 robot actions。
6. Demo 結束後能生成今日照護摘要。

### 不要求第一年完成

1. 完整醫療級診斷。
2. 真實撥打 119。
3. 大型知識圖譜。
4. 完整長期病歷系統。
5. 所有模型都在 Temi 本地端即時推論。

## 8. 建議對教授說法

可以這樣描述目前技術調整：

> 原計畫書中以知識圖譜描述個人化情境與照護決策，但因近期香港 Agent / MCP / Skill 機制快速成熟，我們將知識圖譜調整為更可落地的 structured care memory 與 tool-based cognition。Hermes agent 負責照護情境理解、記憶檢索、風險判斷與行動規劃；Temi 機器人負責實體互動；HermesTemiBridge 則負責安全驗證與執行。此設計仍符合計畫書中多模態異常感知、個人化提醒、緊急應變與健康報告生成的目標，且更適合第一年度 Demo 快速驗證。

## 9. 最小成功版本

如果時間很緊，請至少完成這個最小版本：

1. `profile.json`
2. `reminders.json`
3. `event_log.jsonl`
4. Hermes prompt/skill 能讀取上述記憶。
5. Hermes output 包含 `cognitive_state.home_esi_level`。
6. 支援 `speak`、`ask_clarification`、`log_event`、`mark_reminder_done`。
7. 可跑三個 Demo：
   - 提醒吃藥並確認
   - 使用者表示不舒服並追問
   - 疑似跌倒並 mock 通報
8. 可產生一份今日照護摘要。

做到這些，再加上 Discord/gateway 透過 `.hermes.md`、`SOUL.md` 與 `temi-discord-care-assistant` 能辨識 Temi camera/gesture 請求，就已經能合理宣稱 Hermes 具備第一年度居家照護助理大腦雛形。
