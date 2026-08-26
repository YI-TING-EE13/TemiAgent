# TemiAgent 智慧居家照護系統交接文件

> Historical / legacy reference. Do not use as the current canonical Demo lifecycle.
> Current handover starts with [`CURRENT_STATUS.md`](../CURRENT_STATUS.md),
> [`REPOSITORY_MAP.md`](../REPOSITORY_MAP.md), and the [current Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md).

> Status: legacy handover snapshot dated 2026-07-22. Its branch names, worktree
> paths, historical acceptance claims and command examples are not the current
> source of truth. Start with the root [`README.md`](../../README.md), the
> [documentation coverage map](../README.md#canonical-coverage-map), and the
> maintained [Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md). Keep
> this file only as historical context; do not copy its private-path or
> worktree instructions into a current Demo.

## 文件資訊

* **文件用途：** 提供後續接手 TemiAgent 專案的研究生、開發者與維護人員閱讀
* **整理日期：** 2026-07-22
* **目前開發分支：** `new-demo-v1`
* **AI6 文件里程碑 HEAD：** `666533ff2bf58215385b56b914030b32e53d16d4`
* **Android App 交付方式：** 原始碼將上傳至專案 GitHub repository；本文件不交接或記錄私人開發電腦資訊
* **目前整合狀態：** `CROSS_MACHINE_MEDIA_MILESTONE=PASS`
* **文件狀態：** 依目前已驗證結果整理；標示「待確認」的項目必須由接手者重新檢查專案內容或現場環境

---

# 1. 系統用途與開發背景

TemiAgent 是以 Temi 機器人為具身互動載體的智慧居家照護研究原型。系統透過 Temi 的麥克風、相機、螢幕與喇叭取得語音與影像資訊，再由部署於 AI6 工作站上的本地大型語言模型、Hermes Agent、結構化記憶及安全驗證模組進行照護情境理解、風險判斷與動作規劃。

第一年度原始 Demo 主要驗證：

1. Temi 語音及影像輸入。
2. Hermes Agent 的照護情境理解。
3. 結構化照護記憶。
4. 居家風險分級。
5. 經 Bridge 驗證後的 TTS 或機器人動作。
6. 可追蹤的事件 Trace。

目前的 `new-demo-v1` 在原架構上進一步加入：

* 同一家庭中的多位 Resident。
* Father 與 Mother 的獨立資料及照護計畫。
* 執行中切換 Active Resident。
* 時間型、星期型及條件型 Care Plan。
* 洗腎後特殊照護。
* 午睡時間門檻。
* 手部與腿部運動影片。
* Android 端 command validation 與防重複執行。
* AI6 至真實 Temi 的跨機器端到端驗證。

目前系統仍屬研究及展示原型，不是醫療器材、臨床診斷系統或正式緊急通報服務。

---

# 2. 系統目前完成狀況

## 2.1 整體狀態

| 子系統                         | 目前狀態                    | 說明                                                |
| --------------------------- | ----------------------- | ------------------------------------------------- |
| Temi Android App            | 已完成主要 Demo 能力           | ASR、Camera、MQTT、WebSocket、TTS、字幕、影片播放、結果回傳        |
| Overview Adapter            | 已完成                     | 將 Android legacy ASR 與 Camera 整合成 canonical event |
| Multi-Resident              | 已完成                     | Father、Mother 資料隔離與 runtime switching             |
| Care Plan Engine            | 已完成主要規則                 | 時間、星期、條件型任務與完成狀態                                  |
| Structured Memory           | 已完成                     | Resident-scoped JSON／JSONL 記憶                     |
| Care Context                | 已完成                     | 依 Active Resident 擷取相關歷史資料                        |
| Resident Hermes             | 已完成主要整合                 | 透過本地 LM Studio 產生 JSON action plan                |
| Bridge Validation           | 已完成主要 Demo contract     | 驗證輸入、Hermes output、memory action 與 robot action   |
| TTS                         | 已完成真機驗證                 | 以 Temi callback 判定完成，而非呼叫 API 後立即完成               |
| Exercise Media              | 已完成真機驗證                 | 手部與腿部運動影片                                         |
| Command Idempotency         | 已完成 process-lifetime 版本 | 相同 `command_id` 不重複執行硬體動作                         |
| Trace / Audit               | 已完成                     | Resident attribution、command result 與 lifecycle   |
| Abnormal Event Path         | 已完成主要路徑                 | `perception.abnormal` 進入 Bridge；直接 pre-alert 預設關閉 |
| Full-Day Demo Orchestration | 尚未完成                    | 尚未整理為一鍵或半自動完整一日展示流程                               |
| 正式照護產品化                     | 尚未開始                    | 尚無帳號系統、正式資料庫、權限管理、部署監控等產品能力                       |

## 2.2 已完成的真實跨機器驗證

已由 AI6 後端、Temi Android App 與真實 Temi 完成：

1. Father 日常手部運動。
2. Mother 日常腿部運動。
3. Mother 洗腎回家後手部運動。
4. Daily hand 與 post-dialysis hand 的完成狀態分離。
5. Unknown Resident 不讀取 Father 或 Mother 個人化資料。
6. Unknown Resident 不執行個人化影片。
7. TTS callback-grounded completion。
8. 相同 media command 不重複播放。
9. AI6 MQTT broker 真實連線。
10. AI6 WebSocket endpoint 真實連線。
11. `cmd/result` 回傳 AI6。
12. AI6 Trace 記錄 Resident、task、media 與執行結果。
13. 測試期間沒有執行 navigation 或 turn。

---

# 3. 整體架構與主要技術

## 3.1 系統元件的責任分工

### AI6

AI6 負責：

* Mosquitto MQTT broker。
* Overview Adapter。
* Frame broadcaster。
* Resident Resolver。
* Care Plan Engine。
* Care Context Builder。
* Resident Hermes。
* LM Studio 本地模型。
* HermesTemiBridge。
* Structured Memory。
* Home-ESI 風險推理。
* Action validation。
* Trace / Audit。
* Anomaly backend 與 technical viewer。

### Temi Android App

Temi Android App 負責：

* Android App。
* Temi SDK。
* 自訂喚醒詞。
* Temi ASR callback。
* Camera 串流。
* MQTT／WebSocket clients。
* TTS。
* 字幕。
* 運動影片播放。
* Android 端 command validation。
* Command idempotency。
* `cmd/result` 發布。
* APK build、安裝與真機除錯。

## 3.2 Canonical 系統流程

```text
Temi Android App
    │
    ├─ legacy ASR: temi/event/asr
    └─ Camera H.264 WebSocket stream
            │
            ▼
AI6 Overview Adapter
    │
    ├─ speech-aligned frame snapshot
    └─ canonical temi/{robot_id}/asr/final
            │
            ▼
Mosquitto MQTT
            │
            ▼
HermesTemiBridge
    │
    ├─ Event validation
    ├─ Resident resolution
    ├─ Care Plan / Due Task
    ├─ Care Context retrieval
    ├─ Resident Hermes invocation
    ├─ Action validation
    ├─ Memory action execution
    └─ canonical cmd/request
            │
            ▼
Temi Android App
    │
    ├─ TTS
    ├─ Subtitle
    ├─ play_media
    ├─ stop / safe action
    └─ cmd/result
            │
            ▼
AI6 Trace / Resident Memory
```

## 3.3 主要技術

### AI6

* Linux container。
* Python 3.12。
* `uv` Python dependency manager。
* Paho MQTT。
* Mosquitto。
* LM Studio OpenAI-compatible API。
* Google Gemma 4 31B local model。
* Hermes Agent。
* JSON／JSONL。
* `websockets`。
* PyAV。
* OpenCV。
* `aiohttp`。
* llama.cpp／視覺異常分類相關元件。

### Android App

* Android Studio JBR 21。
* Gradle Wrapper。
* Android SDK。
* Java／Android。
* Temi SDK `com.robotemi:sdk:1.134.1`。
* Android `SpeechRecognizer`。
* CameraX／H.264 encoding。
* MQTT client。
* WebSocket client。
* Android `VideoView`。
* ADB over network。

---

# 4. 專案工作目錄與 Git 基線

## 4.1 AI6

### 原始工作目錄

```text
/TemiAgent
```

Host 對應位置：

```text
<host-workspace>
```

此目錄存在歷史 dirty changes，不可任意執行：

```bash
git reset --hard
git clean -fd
git stash
```

### New Demo 專用 worktree

```text
/TemiAgent/.git/codex-worktrees/new-demo-v1
```

建議每次工作前設定：

```bash
export ACTIVE_ROOT=/TemiAgent/.git/codex-worktrees/new-demo-v1
cd "$ACTIVE_ROOT"
git status --short --branch
```

目前文件里程碑 HEAD：

```text
666533ff2bf58215385b56b914030b32e53d16d4
```

所有 AI6 檔案操作、測試、服務啟動與除錯原則上都應在：

```text
yiting.TemiAgent_gpu_all
```

container 中執行。

**待確認：** 進入該 container 的正式 Docker 指令目前沒有在本交接資料中完整確認。請檢查 AI6 的 `AGENTS.md`、Docker scripts 或既有 shell history。

## 4.2 Android App 原始碼交付

Android App 原始碼將上傳至專案 GitHub repository，作為接手、建置與後續維護的權威來源。接手者應從 repository clone 或 checkout 對應版本，不需要取得原開發者的私人電腦、工作目錄或本機備份。

Repository URL、分支、tag 或 commit 應在上傳完成後填入：

```text
Repository: 待補
Revision: 待補
```

私人開發環境的電腦名稱、IP、磁碟路徑、worktree、備份位置及其他本機資訊不屬於交接內容，也不應寫入本文件或提交至 GitHub。

---

# 5. 主要模組、服務及元件

## 5.1 Temi Android App

主要入口：

```text
app/src/main/java/com/robotemi/agent/MainActivity.java
```

主要責任：

* Android Activity lifecycle。
* Temi robot lifecycle。
* 自訂喚醒詞。
* 呼叫 `robot.wakeup(...)`。
* 接收 Temi ASR。
* Camera 串流。
* MQTT／WebSocket 連線。
* Command validation。
* TTS。
* 字幕。
* Media playback。
* Command result。
* UI status。

重要相關檔案：

```text
app/src/main/java/com/robotemi/agent/MainActivity.java
app/src/main/java/com/robotemi/agent/agent/AgentStateMachine.java
app/src/main/java/com/robotemi/agent/mqtt/MqttManager.java
app/src/main/java/com/robotemi/agent/mqtt/MqttTopics.java
app/src/main/java/com/robotemi/agent/CanonicalCommandValidator.java
app/src/main/java/com/robotemi/agent/CanonicalMediaTracker.java
app/src/main/AndroidManifest.xml
app/src/main/res/layout/activity_main.xml
app/src/main/res/values/strings.xml
```

實際 package：

```text
com.robotemi.agent
```

Main Activity：

```text
com.robotemi.agent/.MainActivity
```

## 5.2 Android AgentStateMachine

主要責任：

* `IDLE`、`LISTENING`、`THINKING`、`WAITING`、`EXECUTING` 等狀態。
* 對話流程控制。
* 60 秒 `WAITING` watchdog。
* 中斷與恢復。
* 避免互動狀態重疊。

目前 watchdog 超時會回到 `IDLE`，並可播放連線逾時提示。這不代表所有 TTS 執行都有 terminal callback timeout。

## 5.3 自訂喚醒詞

目前使用 Android `SpeechRecognizer` 偵測：

```text
小安
```

並包含多種辨識變體。

這是測試型實作，不是 production-grade keyword spotting。單獨說「小安」的穩定度低於：

```text
小安你好
你好小安
```

Temi 系統喚醒詞目前無法完全關閉，因此程式使用：

```text
acceptingTemiAsr
```

避免未經 App 主動喚醒的 ASR 被處理。

## 5.4 Camera 與 WebSocket

Android App 將 Camera 畫面編碼為 H.264，傳送至設定的後端 WebSocket endpoint。實際主機位址由部署環境設定，不應硬編碼私人開發電腦的 IP。

Overview Adapter 在 AI6 接收 Camera stream，並依語音時間建立 speech-aligned frame evidence。

影像本身不透過 MQTT 傳 binary；MQTT 事件傳遞影像檔案路徑。

## 5.5 MQTT

Android App 連線至部署環境設定的 MQTT broker。Broker 位址應透過 ignored local configuration 或安全的部署設定提供，不應將私人開發電腦 IP 寫入 repository 或交接文件。

Android UI 會顯示 MQTT 連線狀態；實際 endpoint 數量依部署設定而定。

主要 topic：

```text
temi/event/asr
temi/{robot_id}/asr/final
temi/{robot_id}/perception/abnormal
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
```

其中：

* Android 目前仍發布 `temi/event/asr`。
* Canonical `asr/final` 由 AI6 Overview Adapter 建立。
* Canonical robot command 由 AI6 Bridge 發布。
* Android 執行後發布 `cmd/result`。

## 5.6 Overview Adapter

主要檔案：

```text
tools/temi_overview_adapter.py
```

主要責任：

* 接收 legacy ASR。
* 接收 Camera stream。
* 建立 speech-aligned frame。
* 儲存 snapshot。
* 發布 canonical `asr/final`。
* 提供 frame broadcaster。

Overview Adapter 不應轉發 robot command，避免多個 command publisher。

啟動時 `shared-root` 與 `bridge-root` 必須使用目前 active worktree 對應的正確絕對路徑。使用錯誤相對路徑會導致 Bridge 正確拒絕越界 frame path。

## 5.7 Resident Resolver

主要責任：

* 決定本次 event 屬於哪一位 Resident。
* 建立 immutable `ResidentExecutionContext`。
* 確保一個 event 只解析一次 Resident。
* 防止 Father／Mother memory、reminder、history 互相污染。

目前 stable IDs：

```text
father
mother
```

Resident assignment 不從 ASR 文字猜測，也不交給 Hermes 猜測。

切換工具：

```bash
python3 tools/set_active_resident.py --resident father
python3 tools/set_active_resident.py --resident mother
python3 tools/set_active_resident.py --clear
```

Unknown Resident 時：

* 不讀取個人化 memory。
* 不建立 Father 或 Mother Care Context。
* 不執行個人化 `play_media`。
* 不呼叫個人化 Hermes 流程。
* 產生安全 fallback 與 trace reason。

## 5.8 Care Plan Engine

主要檔案：

```text
hermes_temi_bridge/src/hermes_temi_bridge/care_plan.py
```

主要概念：

* `ResidentCarePlan`
* `CareTaskDefinition`
* `DueTask`
* Active reminder
* Completion record
* Runtime state

主要 state files：

```text
care_active_reminders.json
care_task_completions.jsonl
care_runtime_state.json
```

目前 task IDs：

```text
morning_blood_pressure
evening_blood_pressure
daily_hand_exercise
daily_leg_exercise
afternoon_nutrition
dialysis_session
post_dialysis_hand_exercise
calcium_reminder
nap_session
nap_duration_reminder
```

### Father

* 早晨血壓提醒。
* 晚間血壓提醒。
* 日常手部運動。
* 日常腿部運動。
* 15:00 糖尿病配方營養補充。
* 午睡時間管理。

### Mother

* 早晨血壓提醒。
* 晚間血壓提醒。
* 日常手部運動。
* 日常腿部運動。
* 15:00 洗腎配方營養補充。
* 洗腎日。
* 洗腎回家後手部運動。
* 鈣片提醒。
* 午睡時間管理。

Scheduling 預設使用：

```text
Asia/Taipei
```

Naive datetime 會被拒絕。

Mother 的 dialysis weekdays 由設定提供；目前真實星期尚未確認。Demo fixture 曾使用 `0,2,4`，不能當成真實醫療安排。

午睡提醒需要 explicit：

```text
nap_started
```

目前沒有自主睡眠辨識。

## 5.9 Care Context Builder

主要檔案：

```text
hermes_temi_bridge/src/hermes_temi_bridge/care_context_builder.py
```

主要責任：

* 從 Resident-scoped memory 擷取 relevant events。
* 取得 reminder state、daily state、profile 與 Care Plan context。
* 將資料放入 `<care_context>`。
* 控制 context budget。
* 確保歷史資料不是當前使用者語句。

現有歷史 retrieval 最多約五筆 relevant events，並優先保留重要風險、當前意圖及提醒相關資料。

## 5.10 Resident Hermes

主要入口：

```text
tools/hermes_resident_server.py
```

主要責任：

* 接收 Bridge HTTP invoke。
* 載入 Temi 相關 skills。
* 呼叫本地 LM Studio。
* 回傳 JSON action plan。

目前主要 skills：

```text
hermes-skills/temi-robot-control
hermes-skills/temi-care-memory
hermes-skills/temi-home-esi
hermes-skills/temi-discord-care-assistant
```

Hermes 不得：

* 直接控制 Temi SDK。
* 直接 publish MQTT。
* 直接寫入 structured memory。
* 自行修改 Care Plan schedule。
* 自行診斷或調整用藥。

## 5.11 HermesTemiBridge

主要目錄：

```text
hermes_temi_bridge/
```

主要責任：

1. 驗證 incoming event。
2. 驗證 image path。
3. Resident resolution。
4. Care Plan 計算。
5. Care Context 建立。
6. 呼叫 Resident Hermes。
7. 解析 JSON。
8. 驗證 cognitive state 與 actions。
9. 分離 robot actions 與 memory actions。
10. 執行 structured memory actions。
11. 建立 canonical command。
12. 發布 `cmd/request`。
13. 接收 `cmd/result`。
14. 寫入 trace。

主要檔案：

```text
hermes_temi_bridge/src/hermes_temi_bridge/main.py
hermes_temi_bridge/src/hermes_temi_bridge/action_validator.py
hermes_temi_bridge/src/hermes_temi_bridge/care_context_builder.py
hermes_temi_bridge/src/hermes_temi_bridge/care_plan.py
hermes_temi_bridge/src/hermes_temi_bridge/hermes_client.py
hermes_temi_bridge/src/hermes_temi_bridge/command_result.py
hermes_temi_bridge/src/hermes_temi_bridge/media_contract.py
```

## 5.12 Structured Memory

目前不是關聯式資料庫，也沒有獨立 database server。

權威資料以 JSON／JSONL 儲存：

```text
memory/residents/{resident_id}/
```

包含：

* Profile。
* Reminders。
* Daily state。
* Event log。
* Summary。
* Care Plan runtime state。
* Completion history。
* Abnormal personalized records。

Hermes 只提出 memory intent，Bridge 才能執行寫入。

目前 runtime 支援的主要 memory actions：

```text
log_event
mark_reminder_done
generate_summary
notify_caregiver_mock
```

下列 actions 目前未正式支援：

```text
set_reminder
update_memory
```

## 5.13 Trace Log

Trace 使用 JSONL。

主要階段包括：

```text
event_received
input_validated
resident_resolved
care_context_built
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

目前可記錄：

* Event ID。
* Resident ID。
* Intent。
* Risk reason。
* Reasoning summary。
* Actions。
* Command ID。
* Media ID。
* Completed／failed／cancelled 分類。
* Duplicate cached result。

Trace 不應保存 private chain-of-thought。

## 5.14 Home-ESI Risk

Home-ESI 是研究用居家安全風險分類，不是臨床診斷。

限制：

* 不得診斷疾病。
* 不得自行開藥。
* 不得修改劑量。
* 不得宣稱真的聯絡 119、醫院或照護者。
* 目前高風險通知為 mock。
* 模糊「不舒服」應先確認與澄清。

## 5.15 Anomaly Detection

Canonical anomaly path：

```text
frame stream
→ anomaly classifier
→ perception.abnormal
→ Bridge
→ Resident Hermes
→ validated command
```

直接 pre-alert speech 已預設：

```text
disabled
```

避免同一異常事件由 Action Viewer 與 Bridge 各說一次。

目前 anomaly clean-head 仍有 dependency gap：

* `requests` 未完整宣告。
* 部分舊測試曾依賴 untracked tester。

此問題目前未阻塞主要 ASR／Care Plan／Media Demo。

## 5.16 `play_media`

Canonical action：

```json
{
  "action_id": "act_media_001",
  "type": "play_media",
  "media_id": "elderly_hand_exercise"
}
```

允許：

```text
elderly_hand_exercise
elderly_leg_exercise
```

拒絕：

* URL。
* Filesystem path。
* Content URI。
* Unknown media ID。
* 缺少 `media_id`。

Care Plan mapping：

```text
daily_hand_exercise
→ elderly_hand_exercise

daily_leg_exercise
→ elderly_leg_exercise

post_dialysis_hand_exercise
→ elderly_hand_exercise
```

Daily hand 與 post-dialysis hand 雖使用相同影片，但 task、reminder 與 completion state 獨立。

---

# 6. 前端、後端、資料庫與外部服務關係

## 6.1 前端

主要 Resident-facing frontend 是 Temi Android App：

* 狀態文字。
* 自訂喚醒詞狀態。
* TTS 字幕。
* 運動影片 overlay。
* Stop button。

目前沒有獨立的正式 Web 前端或照護者 Dashboard。

Anomaly Action Viewer 是技術展示與測試介面，不是一般 Resident 使用介面。

## 6.2 後端

AI6 後端包括：

* Overview Adapter。
* MQTT broker。
* Resident Hermes。
* HermesTemiBridge。
* Care Plan。
* Care Context。
* Structured Memory。
* Trace。
* Anomaly backend。

## 6.3 資料儲存

系統目前使用本地檔案：

```text
JSON
JSONL
Markdown summary
Image snapshots
Trace files
```

沒有 PostgreSQL、MySQL、MongoDB 或雲端資料庫。

## 6.4 外部或獨立服務

| 服務                        | 用途                                    | 必要性                                  |
| ------------------------- | ------------------------------------- | ------------------------------------ |
| Temi SDK                  | 控制 Temi 硬體                            | 真機 Demo 必要                           |
| LM Studio                 | 本地 LLM inference                      | 真 Hermes Demo 必要                     |
| Mosquitto                 | MQTT message broker                   | Canonical Demo 必要                    |
| Google RecognitionService | Android hotword SpeechRecognizer 可能依賴 | 現行語音設計需要                             |
| Discord Gateway           | 選用的人工作業入口                             | Canonical Resident ASR 主線非必要         |
| llama.cpp anomaly service | 視覺異常分類                                | 只有 anomaly Demo 需要                   |
| Internet                  | 一般 canonical local Demo 原則上不必依賴       | Google RecognitionService 的實際需求待現場確認 |

---

# 7. 主要操作流程與資料流

## 7.1 語音互動流程

```text
使用者說「小安你好」
→ Android SpeechRecognizer 偵測自訂喚醒詞
→ App 呼叫 robot.wakeup(ZH_TW)
→ Temi ASR callback
→ Android 發布 temi/event/asr
→ Overview Adapter 對齊 Camera frame
→ 發布 temi/{robot_id}/asr/final
→ Bridge 驗證
→ Resident resolution
→ Care Context
→ Resident Hermes
→ Action validation
→ cmd/request
→ Android TTS／Media
→ cmd/result
→ AI6 Trace
```

## 7.2 Resident 切換流程

```bash
python3 tools/set_active_resident.py --resident father
```

之後的新事件屬於 Father。

```bash
python3 tools/set_active_resident.py --resident mother
```

之後的新事件屬於 Mother。

```bash
python3 tools/set_active_resident.py --clear
```

之後個人化 event 應進入 unknown-resident safe fallback。

## 7.3 運動影片流程

```text
Care Plan due task
→ Hermes / deterministic mapping
→ play_media
→ Bridge allowlist validation
→ cmd/request
→ Android validation
→ VideoView playback
→ STARTED
→ COMPLETED / FAILED / CANCELLED
→ cmd/result
→ Trace
```

## 7.4 異常事件流程

```text
Camera frame
→ Anomaly classifier
→ perception.abnormal
→ Bridge
→ Resident resolution
→ Care Context
→ Hermes risk reasoning
→ validated action
→ Temi
```

直接 pre-alert command 預設關閉。

---

# 8. 環境建置方式

## 8.1 AI6 環境

### 既有需求

* Linux。
* Docker container：`yiting.TemiAgent_gpu_all`。
* NVIDIA GPU。
* 目前 LM Studio 使用 GPU `0,1,2`。
* Python 3.12。
* `uv`。
* Mosquitto。
* LM Studio CLI。
* 專案 worktree。

### 建議檢查

```bash
python3 --version
uv --version
mosquitto -h
lms --version
nvidia-smi
git worktree list
```

### Python dependencies

各 module 的 dependency authority 應以：

```text
pyproject.toml
uv.lock
```

為準。

**待確認：** 接手環境從零建立時，各 module 的正式 `uv sync` 指令與 optional extras。請由 Codex 逐一檢查：

```text
hermes_temi_bridge/pyproject.toml
temi_backend/pyproject.toml
anomaly_detection/pyproject.toml
```

不可直接以舊 shell history 取代 lockfile。

## 8.2 Android App 建置環境

Android App repository 目前已驗證的建置 baseline：

* Android Studio JBR 21。
* Gradle 8.13。
* Android Gradle Plugin 8.13.2。
* Java bytecode target 1.8。
* Android min SDK 23。
* target SDK 30。
* compile SDK 34。
* Temi SDK 1.134.1。
* ADB。

接手者可在自己的支援環境中使用 Android Studio 或 Gradle Wrapper 建置。JDK 與 Android SDK 的實際安裝路徑屬本機設定，不寫入 repository 或交接文件。

## 8.3 Android `local.properties`

`local.properties` 不可 commit。

至少需要：

```properties
sdk.dir=<本機 Android SDK 路徑>
robot.id=temi-01
mqtt.broker.urls=<部署環境 MQTT broker URL>
ws.server.urls=<部署環境 WebSocket URL>
```

實際 key 與格式應以：

```text
app/local.properties.example
app/build.gradle
```

為準。

不要將私人開發電腦 IP 或其他本機敏感資訊提交至 GitHub。

## 8.4 ADB 單一持有者規則

Temi wireless ADB 一次只能由一個開發環境穩定持有。切換操作者或電腦前，原持有者應先執行 `adb disconnect ${TEMI_HOST}:5555`；不要讓多個 ADB client 同時搶占連線。

目前操作基線：

```text
TEMI_HOST=<temi-ip>
wireless ADB target=<temi-ip>:5555
MQTT/WebSocket backend endpoints=<pc-ip>,<secondary-pc-ip>
```

ADB target 的變更不會自動改動已設定的 MQTT／WebSocket backend endpoints。

---

# 9. 系統啟動方式

以下為目前已知 canonical startup。接手者第一次執行前，應再與：

```text
docs/operations/temi_integration_runbook.md
```

逐項比對。

## 9.1 啟動前準備

AI6：

```bash
export ACTIVE_ROOT=/TemiAgent/.git/codex-worktrees/new-demo-v1
cd "$ACTIVE_ROOT"
git status --short --branch

: "${AI6_HOST:?請先由部署環境設定 AI6_HOST}"
: "${TEMI_HOST:?請先由部署環境設定 TEMI_HOST}"
```

確認：

* Worktree clean。
* AI6 服務位址與目前部署環境一致。
* Temi 與 AI6 位於可互通網路。
* 不啟動 legacy backend。
* Direct anomaly pre-alert 保持 disabled。
* 使用絕對 shared path。

## 9.2 啟動 LM Studio

執行目錄：

```text
$ACTIVE_ROOT
```

指令：

```bash
LMSTUDIO_MODEL_ID=google/gemma-4-31b \
LMSTUDIO_API_IDENTIFIER=google/gemma-4-31b \
LMSTUDIO_CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1,2 \
./tools/start_lmstudio_3gpu.sh
```

用途：

* 啟動本地 LM Studio inference server。
* 載入 `google/gemma-4-31b`。
* Context length 設為 64000。
* 只使用 GPU 0、1、2。

成功判定：

* LM Studio server 正常啟動。
* 模型載入成功。
* Hermes health 可取得 model identifier。

## 9.3 啟動 MQTT Broker

執行目錄：

```text
$ACTIVE_ROOT
```

指令：

```bash
mosquitto -c "$ACTIVE_ROOT/mqtt/mosquitto.conf" -d
```

成功判定：

```bash
ss -ltnp | grep ':1883'
```

預期：

```text
0.0.0.0:1883 LISTEN
```

## 9.4 啟動 Overview Adapter

執行目錄：

```text
$ACTIVE_ROOT/temi_backend
```

指令：

```bash
cd "$ACTIVE_ROOT/temi_backend"

uv run python "$ACTIVE_ROOT/tools/temi_overview_adapter.py" \
  --broker "$AI6_HOST" \
  --port 1883 \
  --vision-port 8080 \
  --frame-broadcast-port 8081 \
  --shared-root "$ACTIVE_ROOT/temi_shared" \
  --bridge-root "$ACTIVE_ROOT/temi_shared" \
  --conversation-id conv_new_demo_v1
```

成功判定：

```bash
ss -ltnp | grep -E ':8080|:8081'
```

預期：

```text
0.0.0.0:8080 LISTEN
0.0.0.0:8081 LISTEN
```

注意：

* `shared-root` 與 `bridge-root` 必須是正確絕對路徑。
* Legacy backend 也可能使用 8080，不可同時啟動。

## 9.5 啟動 Resident Hermes

執行目錄：

```text
$ACTIVE_ROOT
```

指令：

```bash
cd "$ACTIVE_ROOT"

python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path "$ACTIVE_ROOT/hermes-skills/temi-robot-control" \
  --skill-path "$ACTIVE_ROOT/hermes-skills/temi-care-memory" \
  --skill-path "$ACTIVE_ROOT/hermes-skills/temi-home-esi" \
  --skill-path "$ACTIVE_ROOT/hermes-skills/temi-discord-care-assistant"
```

成功判定：

```bash
curl -s http://127.0.0.1:8765/health
```

預期至少包含：

```json
{
  "status": "ok"
}
```

**待確認：** 目前最新版 server 是否還需要額外 model、config 或 Hermes home 參數。請以 `--help` 與 integration runbook 為準。

## 9.6 啟動 Bridge

執行目錄：

```text
$ACTIVE_ROOT/hermes_temi_bridge
```

指令：

```bash
cd "$ACTIVE_ROOT/hermes_temi_bridge"

MQTT_BROKER_HOST="$AI6_HOST" \
MQTT_BROKER_PORT=1883 \
TEMI_SHARED_BRIDGE_PATH="$ACTIVE_ROOT/temi_shared" \
TEMI_SHARED_HERMES_PATH="$ACTIVE_ROOT/temi_shared" \
HERMES_INVOKE_MODE=http \
HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
HERMES_TIMEOUT_SECONDS=180 \
MEMORY_DIR="$ACTIVE_ROOT/memory" \
LOG_DIR="$ACTIVE_ROOT/logs/overview_bridge_resident" \
uv run --extra mqtt hermes-temi-bridge \
  --env-file "$ACTIVE_ROOT/hermes_temi_bridge/.env.example"
```

成功判定：

* Bridge 顯示已連上 MQTT。
* 沒有 schema 或 shared path error。
* Resident Hermes health 正常。

## 9.7 啟動 Temi Android App

ADB target：

```text
${TEMI_HOST}:5555
```

由目前持有 Temi ADB 連線的開發環境執行：

```bash
adb connect "${TEMI_HOST}:5555"
adb devices -l
adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity
```

成功判定：

```text
${TEMI_HOST}:5555 device
```

App 畫面應顯示 MQTT 已連線；連線數量依部署設定而定。

AI6 應可觀察到 Temi 與 MQTT、WebSocket 服務的連線已建立。

## 9.8 選用：啟動 Anomaly Viewer

只有展示異常視覺情境時才需要。

```bash
cd "$ACTIVE_ROOT/anomaly_detection"
PRE_ALERT_SPEAK=disabled ./restart_action_viewer_8010.sh
```

注意：

* Direct pre-alert 必須維持 disabled。
* `perception.abnormal` 仍可由 viewer 發布至 Bridge。
* 既有 anomaly dependency gap 可能影響 clean environment。

---

# 10. 重要設定檔與環境變數

## 10.1 AI6

| 設定                         | 用途                         | 目前範例／注意事項                      |
| -------------------------- | -------------------------- | ------------------------------ |
| `ACTIVE_ROOT`              | 指向 clean worktree          | Shell helper，不一定是程式正式 env      |
| `LMSTUDIO_MODEL_ID`        | LM Studio 載入模型             | `google/gemma-4-31b`           |
| `LMSTUDIO_API_IDENTIFIER`  | API model identifier       | 應與模型設定一致                       |
| `LMSTUDIO_CONTEXT_LENGTH`  | Context length             | `64000`                        |
| `LMSTUDIO_VISIBLE_GPUS`    | 可見 GPU                     | `0,1,2`                        |
| `MQTT_BROKER_HOST`         | Bridge broker              | 依部署環境設定                     |
| `MQTT_BROKER_PORT`         | MQTT port                  | `1883`                         |
| `TEMI_SHARED_BRIDGE_PATH`  | Bridge 影像／事件 shared path   | 必須使用正確絕對路徑                     |
| `TEMI_SHARED_HERMES_PATH`  | Hermes 可見 shared path      | 目前與 Bridge path 相同             |
| `HERMES_INVOKE_MODE`       | Hermes 呼叫方式                | Canonical Demo 使用 `http`       |
| `HERMES_HTTP_URL`          | Resident Hermes endpoint   | `http://127.0.0.1:8765/invoke` |
| `HERMES_TIMEOUT_SECONDS`   | Hermes request timeout     | 目前範例 `180`                     |
| `MEMORY_DIR`               | Structured memory root     | 建議位於 active worktree           |
| `LOG_DIR`                  | Bridge trace root          | 建議位於 active worktree           |
| `MOTHER_DIALYSIS_WEEKDAYS` | Mother 洗腎星期設定              | 真實值尚待教授確認                      |
| `PRE_ALERT_SPEAK`          | Action Viewer 直接 pre-alert | Canonical 必須 `disabled`        |
| Scheduling timezone        | Care Plan timezone         | 預設 `Asia/Taipei`；確切 env 名稱待確認  |

## 10.2 Android App

| 設定                       | 用途                              | 注意事項                          |
| ------------------------ | ------------------------------- | ----------------------------- |
| `sdk.dir`                | Android SDK 路徑                  | 寫在 ignored `local.properties` |
| `robot.id`               | Temi robot ID                   | 目前 `temi-01`                  |
| `mqtt.broker.urls`       | MQTT broker URL                  | 依部署環境設定；不可包含私人電腦 IP          |
| `ws.server.urls`         | Camera WebSocket URL             | 依部署環境設定；不可包含私人電腦 IP          |
| `android.useAndroidX`    | AndroidX build                  | 以目前 `gradle.properties` 為準    |
| `android.enableJetifier` | Legacy dependency compatibility | 以目前 `gradle.properties` 為準    |
| `JAVA_HOME`              | Build JDK                       | Android Studio JBR 21         |

---

# 11. Android Build 與部署

執行目錄：

```text
Android App repository root
```

先依自己的作業系統設定 JDK 21 與 Android SDK。相關本機安裝路徑不應 commit。

完整 build、test、lint：

```powershell
.\gradlew.bat `
  :app:assembleDebug `
  :app:compileDebugJavaWithJavac `
  :app:testDebugUnitTest `
  :app:lintDebug `
  --rerun-tasks `
  --console=plain
```

目前已驗證：

```text
36 tests
0 failures
0 errors
```

目前 lint：

```text
1 pre-existing error
23 warnings
```

Pre-existing error 為 ChromeOS Camera `uses-feature` 相關 finding。

APK：

```text
app\build\outputs\apk\debug\app-debug.apk
```

目前驗證 baseline SHA-256：

```text
E2DD1CABE7032DD73B65AA6CB451F48906FAA87F7633D7C7739AC5971DA94A11
```

此 hash 只代表目前已驗證 APK；任何重新 build 都可能改變。

部署：

```powershell
adb connect "$($env:TEMI_HOST):5555"
adb install -r app\build\outputs\apk\debug\app-debug.apk

adb shell pm grant com.robotemi.agent android.permission.CAMERA
adb shell pm grant com.robotemi.agent android.permission.RECORD_AUDIO

adb shell pm grant com.google.android.googlequicksearchbox android.permission.RECORD_AUDIO
adb shell appops set com.google.android.googlequicksearchbox RECORD_AUDIO allow

adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity
```

---

# 12. 功能完成、未完成與停用狀態

## 12.1 已完成

### AI6

* Canonical ASR final event。
* Image path validation。
* Resident resolution。
* Father／Mother runtime switching。
* Resident-scoped memory。
* Resident-scoped Care Context。
* Care Plan。
* Asia/Taipei schedule。
* Configurable dialysis weekdays。
* Nap threshold。
* Home-ESI policy。
* Hermes HTTP invocation。
* Robot／memory action separation。
* `play_media` validation。
* Completed／failed／cancelled result classification。
* Trace。
* Unknown Resident fallback。
* Duplicate cached result trace。
* Direct anomaly pre-alert default disabled。

### Android App

* Android custom wake word。
* Temi ASR。
* Camera streaming。
* MQTT dual broker。
* WebSocket dual endpoint。
* Canonical command envelope validation。
* TTS callback lifecycle。
* Subtitle。
* Process-lifetime command idempotency。
* Motion allowlists。
* Invalid motion rejection。
* Hand exercise video。
* Leg exercise video。
* Media cancel。
* Unknown media rejection。
* `cmd/result`。
* Real Temi acceptance。

## 12.2 部分完成

* Anomaly visual classifier：有程式與測試，但 clean environment dependency 尚不完整。
* Daily summary：已有基礎能力，但內容與展示方式仍有限。
* Blood pressure：只有提醒與紀錄，沒有自動量測裝置。
* Nap：只有 explicit event 與時間門檻，沒有睡眠偵測。
* Dialysis schedule：機制完成，真實星期未確認。
* Navigation／turn：有 allowlist 與 dispatch capability，但目前 Demo 不使用，且尚未驗證實際到達或物理完成。
* Discord gateway：可選，非 canonical Resident Demo 必要元件。

## 12.3 暫時停用或非 canonical

* Legacy backend。
* Direct anomaly pre-alert speech。
* Manual legacy TTS route。
* Manual dispatcher 作為正式 ASR 主線。
* Autonomous navigation。
* Arbitrary URL／path media。
* `set_reminder`。
* `update_memory`。

## 12.4 尚未完成

* Full-Day Demo Orchestrator。
* Resident-facing Android selector。
* Face recognition。
* Speaker recognition。
* 正式帳號與權限系統。
* Caregiver production dashboard。
* 真實照護者通知。
* 真實醫院或 119 整合。
* 自動血壓量測。
* 自主睡眠偵測。
* Restart-persistent command deduplication。
* 正式資料庫。
* Production deployment、monitoring、backup、migration。
* 全部照護情境的真機一鍵 Demo。

---

# 13. 已知限制、技術債與風險

## 13.1 Android

1. `SpeechRecognizer` 不是正式 wake-word engine。
2. 短詞「小安」辨識較不穩定。
3. Temi 系統 wake 無法完全關閉，不能移除 `acceptingTemiAsr` gate。
4. Command registry 只在 process lifetime 有效。
5. Registry capacity 為 1,024。
6. App restart 後不保留 dedup history。
7. Temi 若永遠不回 TTS terminal callback，目前沒有完整自動 timeout。
8. Navigation arrival 未驗證。
9. Turn physical completion 未驗證。
10. Lint 有既有 ChromeOS camera error。
11. 目前只有兩部 bundled media。
12. 無 Android Resident selector。

## 13.2 AI6

1. 原 `/TemiAgent` 是 dirty tree，不可直接清理。
2. 必須使用 clean worktree。
3. Overview Adapter 必須使用正確 absolute shared root。
4. Legacy backend 與 Overview Adapter 可能同占 8080，不可同時啟動。
5. Action Viewer direct pre-alert 必須維持 disabled。
6. Anomaly clean-head dependency gap 尚未處理。
7. Mother 真實 dialysis weekdays 尚未確認。
8. Nap 依賴 explicit event。
9. Care Plan 不應由 Hermes 任意修改。
10. Structured memory 目前是 file-based，缺少 transaction、migration 與 production backup。
11. 真實模型輸出仍可能具有非 deterministic 行為。
12. Scenario runner 的 11/11 使用 mock Hermes、mock MQTT 與 simulated clock，不能當成 11 個真機 E2E。

## 13.3 跨機器

1. Temi ADB 一次只應由一個開發環境持有。
2. MQTT 與 WebSocket endpoint 應依實際部署環境設定，不應依賴私人開發電腦。
3. 後端服務未啟動時會出現 connection refused，不代表 Android routing 錯誤。
4. Cross-machine completion 必須同時有：

   * AI6 command evidence。
   * Android received／started／completed evidence。
   * Returned `cmd/result`。
   * AI6 trace。
5. 只看到 MQTT publish 不能宣稱硬體已執行。
6. AI6 repository 與 Android App GitHub repository 分別是各自元件的權威程式碼來源；私人工作副本不屬於交接資產。

---

# 14. 建議優先閱讀的檔案與目錄

## 14.1 AI6 閱讀順序

1. `AGENTS.md`
2. `README.md`
3. `docs/project/new_demo_v1_milestone.md`
4. `docs/architecture/new_demo_v1_decisions.md`
5. `docs/operations/temi_integration_runbook.md`
6. `hermes_temi_bridge/README.md`
7. `memory/README.md`
8. `logs/README.md`
9. `tools/README.md`
10. `hermes_temi_bridge/src/hermes_temi_bridge/main.py`
11. `resident_resolver`／assignment store 相關檔案
12. `care_plan.py`
13. `care_context_builder.py`
14. `action_validator.py`
15. `command_result.py`
16. `media_contract.py`
17. `tools/set_active_resident.py`
18. `tools/new_demo_v1_scenario_runner.py`
19. `tools/temi_overview_adapter.py`
20. `tools/hermes_resident_server.py`

## 14.2 Android App 閱讀順序

1. `TemiAgent/AGENTS.md`
2. `TemiAgent/README.md`
3. `docs/new_demo_v1_android_baseline.md`
4. `docs/play_media_contract.md`
5. `app/build.gradle`
6. `gradle.properties`
7. `app/local.properties.example`
8. `app/src/main/AndroidManifest.xml`
9. `MainActivity.java`
10. `AgentStateMachine.java`
11. `MqttManager.java`
12. `MqttTopics.java`
13. `CanonicalCommandValidator.java`
14. `CanonicalMediaTracker.java`
15. Android JVM tests
16. `activity_main.xml`
17. `strings.xml`

---

# 15. 常用開發、維護及排查指令

## 15.1 AI6 Git 狀態

```bash
export ACTIVE_ROOT=/TemiAgent/.git/codex-worktrees/new-demo-v1
cd "$ACTIVE_ROOT"

git status --short --branch
git log -5 --oneline
git diff --check
git worktree list
```

## 15.2 AI6 Bridge tests

```bash
cd "$ACTIVE_ROOT/hermes_temi_bridge"
uv run python -m unittest discover -s tests
```

目前文件基線：

```text
118/118 PASS
```

## 15.3 AI6 runners

```bash
cd "$ACTIVE_ROOT"

python3 tools/e2e_test_runner.py
python3 tools/demo_case_runner.py
python3 tools/phase1_care_context_demo_runner.py
python3 tools/new_demo_v1_scenario_runner.py
```

目前文件基線：

```text
Mock E2E: PASS
Old Demo: PASS
Phase 1 Care Context: 4/4 PASS
New Demo deterministic runner: 11/11 PASS
```

New Demo runner 必須標示：

```text
mock_hermes=true
mock_mqtt=true
simulated_clock=true
```

## 15.4 Resident switching

```bash
python3 tools/set_active_resident.py --resident father
python3 tools/set_active_resident.py --resident mother
python3 tools/set_active_resident.py --clear
```

## 15.5 Service health

```bash
ss -ltnp | grep -E ':1883|:8080|:8081|:8765'
curl -s http://127.0.0.1:8765/health
```

## 15.6 Trace

```bash
python3 tools/show_temi_trace.py \
  --log-dir "$ACTIVE_ROOT/logs/overview_bridge_resident" \
  --latest
```

**待確認：** `show_temi_trace.py` 最新參數是否與上述完全一致，請先執行：

```bash
python3 tools/show_temi_trace.py --help
```

## 15.7 Android App build

```powershell
Set-Location $env:ANDROID_APP_ROOT

.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testDebugUnitTest
.\gradlew.bat :app:lintDebug
```

## 15.8 ADB

```powershell
adb connect "$($env:TEMI_HOST):5555"
adb devices -l

adb shell pidof com.robotemi.agent
adb shell dumpsys activity activities
adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity

adb disconnect "$($env:TEMI_HOST):5555"
```

## 15.9 Permission check

```powershell
adb shell dumpsys package com.robotemi.agent |
  findstr /C:"RECORD_AUDIO" /C:"CAMERA"

adb shell appops get com.robotemi.agent RECORD_AUDIO
adb shell appops get com.google.android.googlequicksearchbox RECORD_AUDIO
```

## 15.10 Android logs

```powershell
adb logcat -d -v time |
  Select-String "MainActivity|AgentStateMachine|RecognitionService|Hotword|Canonical|MQTT|WebSocket|TTS|MEDIA"
```

---

# 16. 常見問題與排查方向

## 16.1 AI6 看見 Temi ADB `offline`

可能原因：

* 另一個開發環境仍持有 ADB。
* ADB server 有 stale session。

請先在原持有端執行 `adb disconnect ${TEMI_HOST}:5555`，再於目前環境重新連線：

```bash
adb kill-server
adb start-server
adb connect "${TEMI_HOST}:5555"
adb devices -l
```

## 16.2 AI6 MQTT connection refused

先確認 AI6 broker 是否啟動：

```bash
ss -ltnp | grep ':1883'
```

如果沒有 listener，先啟動 Mosquitto。不要立刻修改 Android endpoint。

## 16.3 AI6 WebSocket connection refused

確認 Overview Adapter 是否啟動：

```bash
ss -ltnp | grep ':8080'
```

檢查：

* Legacy backend 是否占用 8080。
* Adapter 啟動目錄。
* `shared-root`。
* `bridge-root`。

## 16.4 Bridge 拒絕 frame path

常見原因：

* Adapter 使用相對路徑。
* Adapter 與 Bridge 使用不同 root。
* Frame 不在 allowed shared path。

使用同一個絕對路徑：

```text
$ACTIVE_ROOT/temi_shared
```

## 16.5 MQTT 未連線

確認 App 的部署設定與目前 AI6 MQTT broker 位址及連接埠一致，並檢查 broker、網路路由與防火牆。不要以私人開發電腦位址作為備援 endpoint。

## 16.6 自訂喚醒詞不穩

嘗試：

```text
小安你好
你好小安
```

檢查：

* App microphone permission。
* Google RecognitionService permission。
* `RecognitionService#onStartListening`。
* `acceptingTemiAsr`。
* Activity 是否 resumed。

## 16.7 相同影片播放兩次

檢查：

* 是否重用了不同 `command_id`。
* Android process 是否重啟。
* 是否同時啟動 legacy／manual publisher。
* Direct anomaly pre-alert 是否被錯誤開啟。
* 是否有兩個 command publisher。

Process restart 後 idempotency cache 會消失。

## 16.8 TTS 一直 pending

可能原因：

* Temi 沒有回 terminal callback。
* Android TTS listener 狀態異常。
* App lifecycle 被中斷。

目前沒有完整的 terminal-callback timeout，需查看 logcat 並重新啟動 App。

---

# 17. 接手者第一週建議工作

1. 閱讀 AI6 與 Android App repositories 各自的 `AGENTS.md`、README 及建置文件。
2. 確認兩個 repositories 的交付 revision。
3. 確認原始 dirty tree 未被修改。
4. 在 AI6 跑 118 個 Bridge tests。
5. 跑 11 個 New Demo scenarios。
6. 從 GitHub clone Android App，跑 36 個 JVM tests 與 Android build。
7. 確認 Temi ADB ownership。
8. 啟動 AI6 canonical stack。
9. 確認 Android MQTT 狀態為已連線。
10. 重跑一個 TTS 與一個 exercise media。
11. 檢查 AI6 trace。
12. 再開始 Full-Day Demo Orchestration，不要先重構底層架構。

---

# 18. 待確認事項

以下資訊目前不能僅依現有交接資料百分之百確認：

1. 進入 `yiting.TemiAgent_gpu_all` container 的正式指令。
2. 各 Python module 從零建立環境的完整 `uv sync` 指令。
3. Resident assignment JSON state file 的正式位置及可設定 env 名稱。
4. Care Plan timezone 對應的確切 env／config key。
5. Nap threshold 對應的確切 config key。
6. Resident Hermes 最新 CLI 是否需要額外參數。
7. Action Viewer 最新 script 的完整依賴及 clean install 流程。
8. AI6 全部服務的正式 shutdown script。
9. Full-Day Demo 是否已有尚未寫入文件的 operator script。
10. Google RecognitionService 在無網路環境下的實際可用性。
11. 重新 build 後 APK 的最新 SHA-256。
12. Mother 實際洗腎星期。
13. 現場 Demo 的 AI6 MQTT 與 WebSocket endpoint 配置。
14. Android App GitHub repository URL 與交付 revision。

確認方式：

* 優先讀取各環境 `AGENTS.md`。
* 檢查 `docs/operations/temi_integration_runbook.md`。
* 以 `--help` 驗證 CLI。
* 以 `pyproject.toml`、`uv.lock`、`build.gradle`、`local.properties.example` 為設定依據。
* 在 clean worktree 執行非破壞性測試。
* 不以舊 README 或歷史報告單獨判定目前狀態。
