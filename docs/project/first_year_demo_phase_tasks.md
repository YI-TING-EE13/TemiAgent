# 第一年度 Demo 階段任務規劃

最後更新日期：2026-05-31

## 文件目的

本文件把第一年度 Demo 拆成可驗收的階段任務。Demo 目標是展示 Temi App、Local LLM/VLM、Hermes Agent、Bridge safety layer、Discord/gateway Temi 入口與結構化照護記憶如何形成一個可解釋的居家照護助理雛形。

本文件不追求完整產品化，也不回到知識圖譜路線。第一年度 Demo 先採用 JSON / JSONL structured memory，讓系統能在三個固定照護情境中讀取背景、記錄事件、輸出風險分級與生成摘要。

## Demo 主軸

第一年度 Demo 的核心流程：

```text
Temi App ASR / picture streaming
  -> MQTT / shared image paths
  -> temi_backend legacy route or Overview adapter
  -> Hermes / LM Studio local reasoning
  -> JSON action plan
  -> HermesTemiBridge validation
  -> TTS / optional navigation / memory update
  -> event log and summary artifacts
```

## P0：硬體與基礎互動鏈路驗收

狀態：先前已跑過，視為 Demo 前需重新 smoke test 的基礎項。

驗收項目：

- Temi App 能 publish ASR final text。
- Temi App 能接收 TTS command 並成功說話。
- Picture streaming 能連上 PC，ASR 結束時可取得三張同步影像。
- MQTT broker、legacy topics 與 canonical topics 可互通。
- `temi_backend` + LM Studio route 可完成 ASR + image + response。
- Bridge 可收到 event、驗證 image path、發布 command request。

Demo 佐證：

- 一份 ASR event payload。
- 三張 keyframe path。
- 一份 command request / command result。
- 一段 Temi 成功說話或互動的觀察紀錄。

## P1：Structured Memory Demo State

狀態：已建立最小版 Demo state，服務三個固定照護情境；後續 P2 需接上 Bridge memory actions。

目的：

- 取代第一年原規劃中的大型知識圖譜雛形，用可讀、可驗證的 structured memory 支撐 Demo。
- 讓 Hermes/Bridge 可以讀取長者稱呼、照護偏好、提醒狀態、當日狀態與事件紀錄。
- 讓 Demo 結束時能展示 event log 與今日摘要。

交付檔案：

```text
memory/
  README.md
  profile.json
  daily_state.json
  reminders.json
  event_log.jsonl
  abnormal_events/
  summaries/
```

驗收項目：

- `profile.json` 使用男性 Demo persona，稱呼為 `王先生`。
- `reminders.json` 至少包含一個服藥提醒與一個飲水提醒。
- `daily_state.json` 能表示今日風險狀態、active reminders 與 recent event ids。
- `event_log.jsonl` 可追加 JSONL event，不放真實個資。
- `abnormal_events/` 與 `summaries/` 有 README 或 placeholder，方便後續生成 artifact。

## P2：Bridge Memory Actions 與 Home-ESI Schema

狀態：已完成最小實作；待三個 Demo case 實測。

目的：

- 讓 Hermes output 不只控制 robot，也能要求 Bridge 記錄照護事件。
- 保證每次照護判斷都有 Home-ESI 風險等級與理由。

建議新增或允許的非 robot actions：

```text
log_event
mark_reminder_done
generate_summary
notify_caregiver_mock
```

驗收項目：

- Bridge validator 強制檢查 `cognitive_state.home_esi_level` 與 `cognitive_state.risk_reason`。
- Memory actions 只由 Bridge 內部處理，不 publish 給 Temi。
- `log_event` 可追加到 `memory/event_log.jsonl`。
- `mark_reminder_done` 可更新 `memory/reminders.json` 與 `daily_state.json`。
- `generate_summary` 可寫入 `memory/summaries/{date}.md`。
- `notify_caregiver_mock` 可寫入 abnormal event，且明確標示 demo mock。

## P3：三個照護 Demo Case

狀態：deterministic runner 已完成；真 Temi / real Hermes 現場流程仍待實測。

工具：`tools/demo_case_runner.py`。

固定情境：

1. 日常提醒：Temi 提醒王先生早餐後服藥，使用者確認後寫入 reminder done 與 event log。
2. 不適求助 L2：使用者說「我有點不舒服」，Hermes 判斷 L2，Temi 追問並記錄事件。
3. 疑似跌倒 L1：影像或 mock event 顯示疑似跌倒/無回應，Hermes 判斷 L1，Temi 先確認，再 mock notify caregiver。
4. Discord/gateway 手勢入口：使用者要求「看我的手勢」時，Hermes 先找圖片附件或 Temi frame paths；沒有影像則要求觸發/傳送 camera event。

每個 case 的 artifact：

- Input event JSON。
- Image path list。
- Hermes raw output。
- Parsed output。
- Command request。
- Command result。
- Memory diff 或 event log entry。
- Run summary：`run_summary.json`。

驗收方式：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

通過條件：三個 case 均回傳 `status: success`，最終 memory state 具有 reminder done、L2 event log、L1 abnormal event 與每日摘要。

## P4：Navigation 加分整合

狀態：本輪先跳過；保留為加分整合，不擋第一年度 Demo 主線。

目的：

- 展示 Temi 不只會回話，也能根據語音或情境移動。
- 對應 temi skills 中已預留的 `navigate` action。

驗收項目：

- Temi App 可接收 navigation command。
- 至少一個 allowlisted target 可成功執行。
- Bridge 能拒絕不在 allowlist 的 target。
- Adapter 對 navigation result 有清楚 command result。

備註：若 Demo 時間有限，Navigation 可以是加分情境，不擋 P1-P3 主線。

## P5：Demo Rehearsal 與展示素材

狀態：已整理 runbook、scenario script 與 acceptance checklist。

目的：

- 讓第一年度成果可被非工程觀眾理解。
- 把「計畫書原目標」與「第一年實際可展示系統」對齊。

交付項目：

- Demo runbook：`docs/project/first_year_demo_runbook.md`。
- 端到端串接操作手冊：`docs/project/first_year_demo_e2e_operation_manual.md`。
- 三個 scenario 的固定 script：`docs/project/first_year_demo_scenario_script.md`。
- Acceptance checklist：`docs/project/first_year_demo_acceptance_checklist.md`。
- Artifact 產生工具：`tools/demo_case_runner.py`。
- 系統架構圖與風險聲明已寫入 runbook。

## 優先順序

建議順序：

1. P1 structured memory demo state。
2. P2 Bridge memory actions 與 Home-ESI schema。
3. P3 三個照護 Demo case。
4. P5 展示素材整理。
5. P4 Navigation。

P0 在 Demo 前重新 smoke test 即可，不必先擴大重做。P4 Navigation 本輪先跳過，Demo 主線以 P1-P3/P5 為準。
