# 第一年度 Demo 情境腳本

最後更新日期：2026-05-31

## 角色設定

- 示範長者：男性，Demo persona 稱呼為 `王先生`。
- Temi：居家照護助理，語氣溫和、簡短、清楚。
- 系統邊界：Demo 使用 mock caregiver notification，不做真實 119 或家屬通報。

## 開場說明

建議口述：

> 本 Demo 將原計畫中多模態異常行為偵測、個人化提醒、隱私保護資料庫與緊急應變，落地成 Temi 機器人上的本地 Agent 系統。Temi App 負責 ASR、TTS 與影像串流；Hermes / LM Studio 在本地端推理；Bridge 負責驗證與安全執行；照護紀錄則以 structured memory 保存，不使用大型知識圖譜。

## Scenario A：日常提醒與完成紀錄

目標：展示個人化提醒與 structured memory 更新。

示範台詞：

1. 系統或主持人說明：現在模擬早餐後服藥提醒。
2. Temi 說：`王先生，現在是早餐後服藥時間。`
3. 示範者說：`我吃完藥了。`
4. 系統回應：`好的，王先生，我已經幫您記錄早餐後服藥完成。`

預期 artifact：

- `cognitive_state.home_esi_level = L3`
- `mark_reminder_done(rem_morning_medication)`
- `log_event(event_type=care_reminder)`
- `memory/reminders.json` 中 `rem_morning_medication.status = completed`
- `memory/event_log.jsonl` 新增提醒完成事件

## Scenario B：不適 / 求助 L2

目標：展示中風險主動關懷，不直接升級成高風險。

示範台詞：

1. 示範者說：`我有點不舒服。`
2. Temi 回應：`王先生，您是哪裡不舒服？會頭暈、胸悶，還是剛剛有跌倒嗎？`

預期 artifact：

- `cognitive_state.home_esi_level = L2`
- `risk_reason` 說明「使用者表示不適，但尚無明確跌倒或無回應證據」
- robot action：`ask_clarification`
- memory action：`log_event(event_type=possible_distress)`
- `memory/event_log.jsonl` 新增 L2 事件

## Scenario C：疑似跌倒 / 高風險 L1

目標：展示高風險確認、mock notification 與 abnormal event artifact。

示範台詞：

1. 示範者說：`救命，我跌倒了。`
2. Temi 回應：`王先生，我聽到您說跌倒了。請您先不要勉強移動，我會先幫您做模擬通知家屬。`

預期 artifact：

- `cognitive_state.home_esi_level = L1`
- robot action：`ask_clarification`
- memory actions：`notify_caregiver_mock`、`log_event`、`generate_summary`
- `memory/abnormal_events/{event_id}.json` 明確標示 `notification.type = demo_mock`
- `memory/summaries/{date}.md` 生成 Demo 摘要

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
logs/demo_cases/rehearsal_001/cases/discomfort_l2/parsed_output.json
logs/demo_cases/rehearsal_001/cases/possible_fall_l1/memory_state_after.json
logs/demo_cases/rehearsal_001/memory/event_log.jsonl
logs/demo_cases/rehearsal_001/memory/abnormal_events/evt_demo_possible_fall_l1_001.json
logs/demo_cases/rehearsal_001/memory/summaries/2026-05-31.md
```

## 收尾說明

建議口述：

> 這套系統目前完成第一年度 Demo 所需的感知輸入、Agent 推理、安全驗證、照護記憶與風險分級雛形。Navigation 與更完整的手勢辨識、正式通報、健康報告模板可作為後續年度與下一階段整合。
