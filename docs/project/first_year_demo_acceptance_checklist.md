# 第一年度 Demo 驗收 Checklist

最後更新日期：2026-06-12

## 驗收狀態摘要

| 階段 | 狀態 | 備註 |
|---|---|---|
| P0 硬體與基礎互動鏈路 | Demo 前需 smoke test | Temi App ASR/TTS/Picture Streaming。 |
| P1 Structured Memory | 已完成 | `memory/` demo state，男性 persona `王先生`。 |
| P2 Bridge Memory Actions | 已完成最小實作 | Home-ESI validation + memory/demo actions。 |
| P3 三個 Demo Case | 已完成 deterministic runner | 真 Temi / real Hermes 現場流程需當天短測。 |
| P4 Navigation | 先跳過 | 加分項，不擋第一年度主線。 |
| P5 展示素材 | 已整理 | Runbook、E2E manual、scenario script、checklist。 |

## Demo 前必勾項

### 系統與服務

- [ ] 已進入 `yiting.TemiAgent_gpu_all` container，工作目錄是 `/TemiAgent`。
- [ ] 已用一鍵腳本重啟正式 Demo stack。
- [ ] `lms ps` 顯示 `google/gemma-4-31b`，context 是 `64000`。
- [ ] `curl http://127.0.0.1:1234/v1/models` 可看到模型。
- [ ] `curl http://127.0.0.1:8765/health` 回 `status: ok`。
- [ ] `curl http://127.0.0.1:8010/health` 回 OK，且 `abnormal_cooldown_seconds = 180.0`。
- [ ] MQTT broker `1883` listening。
- [ ] Overview adapter `8080` listening，且沒有 legacy backend 搶 port。
- [ ] Temi App 已啟動並能送出 ASR。
- [ ] Picture Streaming 連上 PC 端 WebSocket。
- [ ] 手動 TTS command 可讓 Temi 說話。
- [ ] Hermes resident preload 包含 `temi-robot-control`、`temi-care-memory`、`temi-home-esi`、`temi-discord-care-assistant`。
- [ ] Hermes Discord gateway 已啟動，`hermes gateway status` 顯示 running，且 `gateway_state.json` 中 `discord.state = connected`。
- [ ] Bridge 使用 `MEMORY_DIR=/TemiAgent/memory`。
- [ ] MQTT monitor 可看到 `temi/event/asr`、`temi/temi-01/asr/final`、`temi/temi-01/cmd/request`、`temi/temi-01/cmd/result`。

### 正式錄影

- [ ] `adb devices -l` 看到 `192.168.50.205:5555 device`。
- [ ] `scrcpy --version` 可用。
- [ ] `/TemiAgent/logs/demo_recordings/` 已建立。
- [ ] 已做 `scrcpy` 8 秒短測，MP4 不是 0 byte，也不是只有數百 byte 的 header。
- [ ] 若 `scrcpy` 不穩，已準備 ADB fallback：`screenrecord --bugreport --size 720x1280 --bit-rate 2000000`。
- [ ] 若需要 1280x720 橫向影片，已先短測畫面沒有裁切；否則採 `720x1280` 完整錄影後製。
- [ ] 錄影停止後已 `ls -lh /TemiAgent/logs/demo_recordings/*.mp4` 確認檔案大小合理。

### Deterministic artifacts

- [ ] `python3 tools/demo_case_runner.py --keep-artifacts` 成功。
- [ ] `run_summary.json` 三個 case 都是 `success`。
- [ ] `daily_reminder` 產生 `mark_reminder_done`。
- [ ] `discomfort_l2` 產生 `home_esi_level = L2`。
- [ ] `possible_fall_l1` 產生 `home_esi_level = L1`。
- [ ] abnormal event JSON 中 `notification.type = demo_mock`。
- [ ] summary Markdown 已產生。

### 文件與口頭說明

- [ ] 能指到 `docs/project/first_year_demo_e2e_operation_manual.md` 作為完整操作與 debug 文件。
- [ ] 能指到 `docs/project/first_year_demo_runbook.md` 作為 Demo day 快速摘要。
- [ ] 能指到 `docs/project/first_year_demo_scenario_script.md` 作為三個情境主持稿。
- [ ] 能說明為何第一年不做大型知識圖譜，改用 structured memory。
- [ ] 能說明 Hermes 不直接控制硬體，Bridge 是安全邊界。
- [ ] 能說明 Home-ESI v2 decision-tree 是 Demo risk policy，不是醫療分診。
- [ ] 能展示 `memory/profile.json` 中男性 persona `王先生`。
- [ ] 能展示 event log / abnormal event / summary artifact。

## 三個 Scenario 驗收

| Scenario | 輸入 | 預期 Home-ESI | 預期動作 | 驗收 artifact |
|---|---|---:|---|---|
| 日常提醒 | `我吃完早餐後的藥了。` | L3 | `speak` + `mark_reminder_done` + `log_event` | reminder completed + event log |
| 不適求助 | `我有點不舒服，頭有點暈。` | L2 | `ask_clarification` + `log_event` | L2 event log |
| 疑似跌倒 | `救命，我跌倒了，站不起來。` | L1 | `ask_clarification` + `notify_caregiver_mock` + `log_event` + `generate_summary` | abnormal event + summary |

## 不納入本次主線驗收

- Navigation 實機移動。
- 真實家屬或 119 通報。
- 醫療級診斷或正式分診。
- 完整健康報告模板。
- 邊緣模型輕量化。

## Demo 後保存素材

建議每次排練保存一份：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --output-dir logs/demo_cases/rehearsal_YYYYMMDD_HHMM
```

需要保存的核心檔案：

```text
logs/demo_recordings/temi-demo-*.mp4
logs/e2e_stack_validation_*/
logs/demo_cases/*/run_summary.json
logs/demo_cases/*/cases/*/parsed_output.json
logs/demo_cases/*/cases/*/command_request.json
logs/demo_cases/*/cases/*/memory_state_after.json
memory/event_log.jsonl
memory/abnormal_events/*.json
memory/summaries/*.md
```
