# 第一年度 Demo 驗收 Checklist

最後更新日期：2026-05-31

## 驗收狀態摘要

| 階段 | 狀態 | 備註 |
|---|---|---|
| P0 硬體與基礎互動鏈路 | 先前已跑過，Demo 前需 smoke test | Temi App ASR/TTS/Picture Streaming。 |
| P1 Structured Memory | 已完成 | `memory/` demo state，男性 persona `王先生`。 |
| P2 Bridge Memory Actions | 已完成最小實作 | Home-ESI validation + 4 個 memory/demo actions。 |
| P3 三個 Demo Case | 已完成 deterministic runner | 真 Temi / real Hermes 現場流程仍待排練。 |
| P4 Navigation | 先跳過 | 加分項，不擋第一年度主線。 |
| P5 展示素材 | 已整理 | Runbook、scenario script、checklist。 |

## 已執行測試

最近一次在 container 內驗證：

```text
hermes_temi_bridge unittest: 38 passed

temi_backend pytest: 14 passed

tools/e2e_test_runner.py: status ok

tools/demo_case_runner.py: three cases success

py_compile tools/demo_case_runner.py: ok

git diff --cached --check: ok
```

## Demo 前必勾項

### 系統與服務

- [ ] PC 與 Temi 在同一網路。
- [ ] MQTT broker 可連線。
- [ ] Temi App 已啟動並能送出 ASR。
- [ ] Picture Streaming 連上 PC 端 WebSocket。
- [ ] TTS command 可讓 Temi 說話。
- [ ] LM Studio 或 Hermes resident mode 已啟動。
- [ ] Resident Hermes preload 包含 `temi-robot-control`、`temi-care-memory`、`temi-home-esi`、`temi-discord-care-assistant`。
- [ ] Bridge 使用正確 `MEMORY_DIR`。

### Deterministic artifacts

- [ ] `python3 tools/demo_case_runner.py --keep-artifacts` 成功。
- [ ] `run_summary.json` 三個 case 都是 `success`。
- [ ] `daily_reminder` 產生 `mark_reminder_done`。
- [ ] `discomfort_l2` 產生 `home_esi_level = L2`。
- [ ] `possible_fall_l1` 產生 `home_esi_level = L1`。
- [ ] abnormal event JSON 中 `notification.type = demo_mock`。
- [ ] summary Markdown 已產生。

### 文件與口頭說明

- [ ] 能說明為何第一年不做大型知識圖譜，改用 structured memory。
- [ ] 能說明 Hermes 不直接控制硬體，Bridge 是安全邊界。
- [ ] 能說明 Home-ESI Lite 是 Demo risk policy，不是醫療分診。
- [ ] 能展示 `memory/profile.json` 中男性 persona `王先生`。
- [ ] 能展示 event log / abnormal event / summary artifact。

## 三個 Scenario 驗收

| Scenario | 輸入 | 預期 Home-ESI | 預期動作 | 驗收 artifact |
|---|---|---:|---|---|
| 日常提醒 | `我吃完藥了` | L3 | `speak` + `mark_reminder_done` + `log_event` | reminder completed + event log |
| 不適求助 | `我有點不舒服` | L2 | `ask_clarification` + `log_event` | L2 event log |
| 疑似跌倒 | `救命，我跌倒了` | L1 | `ask_clarification` + `notify_caregiver_mock` + `log_event` + `generate_summary` | abnormal event + summary |

## 不納入本次主線驗收

- Navigation 實機移動。
- 手勢辨識：Discord/gateway 需先確認有 image attachment、`temi_shared/` path 或 Bridge frame paths；沒有影像時 Hermes 要要求觸發/傳送 Temi camera event。
- 真實家屬或 119 通報。
- 完整健康報告模板。
- 醫療級診斷或正式分診。
- 邊緣模型輕量化。

## Demo 後保存素材

建議每次排練保存一份：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --output-dir logs/demo_cases/rehearsal_YYYYMMDD_HHMM
```

需要保存的核心檔案：

```text
run_summary.json
cases/*/parsed_output.json
cases/*/command_request.json
cases/*/memory_state_after.json
memory/event_log.jsonl
memory/abnormal_events/*.json
memory/summaries/*.md
```
