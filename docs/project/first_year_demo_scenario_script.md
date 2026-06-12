# 第一年度 Demo 情境腳本

最後更新日期：2026-06-12

## 角色與 Demo 基調

- 示範長者：男性 Demo persona，稱呼為 `王先生`。
- Temi：居家照護助理，回應要短、慢、清楚，避免像醫療診斷。
- 主持人：負責把觀眾注意力從「機器有沒有說話」帶到「系統如何感知、推理、驗證、記錄」。
- 系統邊界：Demo 使用 mock caregiver notification，不做真實家屬或 119 通報。

三個情境建議用 L3 -> L2 -> L1 的節奏展示：先讓觀眾看到日常照護記憶，再看到中風險追問，最後展示高風險安全邊界與 mock 通報。每段都要保留一個可展示的後台證據，避免只像語音聊天。

## 開場說明

建議口述：

> 本 Demo 將原計畫中多模態異常行為偵測、個人化提醒、隱私保護資料庫與緊急應變，落地成 Temi 機器人上的本地 Agent 系統。Temi App 負責 ASR、TTS 與影像串流；Hermes / LM Studio 在本地端推理；HermesTemiBridge 是安全邊界，負責驗證 Hermes JSON output、檢查 action schema，再把通過驗證的動作送給 Temi。照護紀錄使用 structured memory 保存，第一年度 Demo 先不使用大型知識圖譜。

正式開始前先說明：

> 接下來三個情境會從一般提醒、身體不適，到疑似跌倒逐步升級。請注意 Temi 不會直接做醫療診斷，也不會真的通報 119；高風險情境會產生 demo mock notification artifact，展示系統設計上的安全邊界。

## Scenario 1：提醒吃藥與完成紀錄 L3

### 展示目標

展示日常照護情境中，Temi 能理解「早餐後服藥提醒」已完成，並由 Bridge 寫入 structured memory。這段要讓觀眾先建立信心：系統不是只回話，而是能更新可稽核的照護狀態。

### 情境背景

- 王先生早上有一筆 active reminder：早餐後服藥。
- 這是低風險日常照護情境，Home-ESI 應為 `L3`。
- 主要 action 是 `speak`、`mark_reminder_done`、`log_event`。

### 現場演法

主持人鋪陳：

> 第一個情境是最日常的照護提醒。系統記得王先生早餐後要吃藥，當他回報已完成後，Bridge 會把提醒狀態改成 completed，並留下 event log。

建議示範台詞二選一：

```text
我吃完早餐後的藥了。
```

或：

```text
我剛剛已經吃完藥了，幫我記錄一下。
```

Temi 預期回應方向：

```text
好的，王先生，我已經幫您記錄早餐後服藥完成。
```

若希望更像照護助理，可用：

```text
好的，王先生，早餐後服藥已經記錄完成。等一下如果有不舒服，請再告訴我。
```

### 後台證據

現場可展示：

```text
memory/reminders.json
memory/event_log.jsonl
logs/demo_cases/<run>/cases/daily_reminder/command_request.json
logs/demo_cases/<run>/cases/daily_reminder/memory_state_after.json
```

重點解釋：

- `home_esi_level = L3`，表示日常照護，不是緊急風險。
- `rem_morning_medication.status = completed`。
- event log 保留「誰、何時、因為哪個 ASR event、完成了哪個提醒」。
- Hermes 不直接寫 memory；Bridge 驗證 action 後才更新 structured memory。

### 現場備援

如果真機 ASR 沒收到，主持人可說：

> 現場語音鏈路偶爾會受環境音影響；這裡切到 deterministic artifact，看同一個事件通過 Bridge 後實際寫入的狀態。

然後開 `daily_reminder/memory_state_after.json` 或 `memory/event_log.jsonl`。

## Scenario 2：身體不適與 L2 中風險追問

### 展示目標

展示 Temi 遇到「不舒服」這種不明確求助時，不會直接升級成緊急通報，而是進入中風險關懷流程：先追問症狀、確認是否跌倒或有危急徵象，並記錄 L2 event。

### 情境背景

- 王先生表示身體不舒服，但沒有明確說跌倒、失去意識、胸痛、呼吸困難。
- Home-ESI 應為 `L2`。
- 主要 action 是 `ask_clarification`、`log_event`。

### 現場演法

主持人鋪陳：

> 第二個情境是中風險。使用者只說不舒服，這在居家照護裡不能忽略，但也不應該立刻假設是跌倒或急救事件。系統會先追問關鍵症狀，並把這次不適記錄下來。

建議示範台詞：

```text
我有點不舒服，頭有點暈。
```

Temi 預期回應方向：

```text
王先生，您現在是頭暈、胸悶，還是呼吸不舒服？剛剛有跌倒或撞到嗎？
```

若要多演一輪 follow-up，示範者可回答：

```text
沒有跌倒，我先坐一下。
```

Temi 第二輪回應方向：

```text
好的，請您先坐穩休息。我會幫您記錄這次不舒服；如果症狀加重，請立刻告訴我。
```

### 後台證據

現場可展示：

```text
logs/demo_cases/<run>/cases/discomfort_l2/parsed_output.json
logs/demo_cases/<run>/cases/discomfort_l2/command_request.json
memory/event_log.jsonl
```

重點解釋：

- `home_esi_level = L2`，理由應包含「不適但尚無明確跌倒或無回應證據」。
- robot action 應是追問或關懷，不是直接通知家屬。
- memory action 記錄 possible distress，保留後續照護連續性。
- 這段展示的是「風險分級的克制」：系統有警覺，但不過度宣稱。

### 現場備援

若 real Hermes 延遲過高，可先展示 `parsed_output.json`：

> 這裡可以看到 Hermes 的 cognitive_state 把事件分為 L2，而 Bridge 只允許追問與記錄，不會讓 LLM 直接做硬體或通知 side effect。

## Scenario 3：疑似跌倒與 L1 高風險 mock notification

### 展示目標

展示高風險情境下，系統能把明確求救與跌倒語句判為 `L1`，Temi 先要求使用者不要勉強移動，同時產生 demo mock caregiver notification、abnormal event 與 summary artifact。這段要特別強調：Demo 不做真實 119 通報。

### 情境背景

- 王先生明確說「救命」與「跌倒」。
- Home-ESI 應為 `L1`。
- 主要 action 是 `ask_clarification`、`notify_caregiver_mock`、`log_event`、`generate_summary`。

### 現場演法

主持人鋪陳：

> 第三個情境是高風險。這裡的關鍵不是讓 Temi 自行做醫療判斷，而是把明確求救和跌倒訊號送進安全流程：先安撫、要求不要移動、記錄事件，並產生 mock notification artifact。

建議示範台詞：

```text
救命，我跌倒了，站不起來。
```

Temi 預期回應方向：

```text
王先生，我聽到您說跌倒了。請先不要勉強移動，保持安全姿勢。我會先進行 Demo 模擬通知，並記錄這次高風險事件。
```

若要更像照護現場，可加一句：

```text
如果您可以回答，請告訴我現在有沒有流血、胸悶，或呼吸困難。
```

### 後台證據

現場可展示：

```text
logs/demo_cases/<run>/cases/possible_fall_l1/parsed_output.json
logs/demo_cases/<run>/cases/possible_fall_l1/command_request.json
logs/demo_cases/<run>/cases/possible_fall_l1/memory_state_after.json
memory/abnormal_events/*.json
memory/summaries/*.md
```

重點解釋：

- `home_esi_level = L1`，理由應包含「明確跌倒 + 求救」。
- `notify_caregiver_mock` 必須明確標示 demo mock，不是真實通報。
- abnormal event artifact 保留事件 ID、risk level、通知類型與摘要。
- summary artifact 展示 Demo 結束後可回顧今日照護事件。
- Hermes 只輸出 action plan；Bridge 才負責驗證與 dispatch。

### 現場備援

如果真機 TTS 或 MQTT command 沒回來，直接展示 abnormal event JSON：

> 高風險流程最重要的是安全邊界與可追溯 artifact。即使現場硬體語音鏈路不穩，這裡仍可看到 Bridge 產生的 mock notification 與事件記錄。

## 三段轉場詞

Scenario 1 結束後：

> 剛剛是 L3 的日常提醒，重點是照護記憶能被安全更新。接下來我們把情境升級成不舒服，但還不是明確緊急事件。

Scenario 2 結束後：

> 這段展示中風險的克制：系統先追問，不直接做緊急通報。最後我們示範明確跌倒求救時，系統如何進入 L1 高風險流程。

Scenario 3 結束後：

> 三個情境串起來後，可以看到同一個 Bridge safety layer 同時處理日常提醒、中風險追問與高風險 mock notification，並把結果保存在 structured memory 中供後續查詢與摘要。

## Artifact 展示方式

若不接真機，可用 deterministic runner 產生完整資料：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --output-dir logs/demo_cases/rehearsal_001
```

建議展示檔案：

```text
logs/demo_cases/rehearsal_001/run_summary.json
logs/demo_cases/rehearsal_001/cases/daily_reminder/command_request.json
logs/demo_cases/rehearsal_001/cases/daily_reminder/memory_state_after.json
logs/demo_cases/rehearsal_001/cases/discomfort_l2/parsed_output.json
logs/demo_cases/rehearsal_001/cases/possible_fall_l1/memory_state_after.json
logs/demo_cases/rehearsal_001/memory/event_log.jsonl
logs/demo_cases/rehearsal_001/memory/abnormal_events/evt_demo_possible_fall_l1_001.json
logs/demo_cases/rehearsal_001/memory/summaries/2026-06-12.md
```

展示順序建議：

1. `run_summary.json`：先證明三個 case 都成功。
2. `daily_reminder/memory_state_after.json`：展示提醒完成。
3. `discomfort_l2/parsed_output.json`：展示 L2 reasoning 與追問。
4. `possible_fall_l1/memory_state_after.json`：展示 L1 事件寫入。
5. `memory/abnormal_events/*.json`：展示 demo mock notification。
6. `memory/summaries/*.md`：展示照護摘要。

## 收尾說明

建議口述：

> 這套系統目前完成第一年度 Demo 所需的感知輸入、Agent 推理、安全驗證、照護記憶與風險分級雛形。它不宣稱取代醫療判斷；它展示的是居家照護機器人在面對日常照護、中風險不適與高風險跌倒時，如何以一致、可驗證、可追溯的方式協助照護者。
