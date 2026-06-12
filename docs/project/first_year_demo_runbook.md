# 第一年度 Demo Runbook

最後更新日期：2026-06-12

## 文件索引

這份 runbook 是 Demo day 快速摘要，只放當天最常用的順序、指令與說明。完整啟動、分服務操作與 debug 請看 `docs/project/first_year_demo_e2e_operation_manual.md`。三個情境的完整台詞、預期回應、後台 artifact 與備援說法請看 `docs/project/first_year_demo_scenario_script.md`。驗收勾選請看 `docs/project/first_year_demo_acceptance_checklist.md`。

## Demo 定位

本 Demo 展示「具備照護情境理解與安全邊界的 Temi 智慧助理雛形」。Temi App 負責 ASR、TTS 與 Picture Streaming；PC 端透過 MQTT 與 shared image paths 收到事件；Hermes / LM Studio 在本地推理；HermesTemiBridge 驗證 JSON output 與 action schema，再把通過驗證的 command 發到 canonical `temi/temi-01/cmd/request`。Structured memory 保存提醒、不適、疑似跌倒與摘要。

口頭邊界：這不是醫療診斷，不是真實 119 或家屬通報；`notify_caregiver_mock` 是 Demo artifact。

## Demo Day 最短流程

### 1. 進入 container

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

### 2. 一鍵重啟全部服務

目前正式 Demo 先用三卡非 QAT Gemma 4 31B：

```bash
cd /TemiAgent
MODEL_LOAD_ID=google/gemma-4-31b \
MODEL_IDENTIFIER=google/gemma-4-31b \
CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1,2 \
RUN_UNIT_TESTS=0 \
RUN_LOCAL_E2E=0 \
RUN_DEMO_CASES=0 \
RUN_LIVE_E2E=0 \
./tools/validate_temi_e2e_stack.sh
```

時間足夠時移除 `RUN_* = 0`，讓腳本跑完整硬體檢查、unit tests、local E2E、demo cases 與 live E2E。完整說明見 E2E 手冊「第一部分：一鍵建立或重啟所有服務」。

### 3. 快速確認服務狀態

```bash
lms ps
curl -sS http://127.0.0.1:1234/v1/models
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8010/health
/TemiAgent/hermes-agent/venv/bin/hermes gateway status
python3 -m json.tool /root/.hermes/gateway_state.json | grep -A8 '"discord"'
adb connect 192.168.50.205:5555
adb devices -l
```

最低通過條件：LM Studio 有 `google/gemma-4-31b`、Hermes health OK、Action viewer OK、Discord gateway connected、ADB 看到 `192.168.50.205:5555 device`。

### 4. 開始正式錄影

優先短測錄影，確認 MP4 不是只有 header。

`scrcpy` 路線：

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
scrcpy --serial 192.168.50.205:5555 \
  --no-display \
  --no-control \
  --max-size 1280 \
  --bit-rate 2M \
  --record "/TemiAgent/logs/demo_recordings/temi-demo-$(date +%Y%m%d_%H%M%S).mp4"
```

ADB fallback：

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
adb -s 192.168.50.205:5555 shell screenrecord --bugreport --size 720x1280 --bit-rate 2000000 /sdcard/temi-demo.mp4
# Ctrl+C 停止後
adb -s 192.168.50.205:5555 pull /sdcard/temi-demo.mp4 "/TemiAgent/logs/demo_recordings/temi-demo-adb-$(date +%Y%m%d_%H%M%S).mp4"
```

若要測 1280x720 橫向輸出，照 E2E 手冊「正式 Demo 錄影」先做短測；直向 `720x1280` 是保守保底。錄完務必 `ls -lh /TemiAgent/logs/demo_recordings/*.mp4` 確認檔案大小合理。

### 5. 進行三個正式情境

| 順序 | 情境 | 建議輸入 | 預期風險 | 展示重點 |
|---|---|---|---|---|
| 1 | 提醒吃藥 | `我吃完早餐後的藥了。` | L3 | reminder completed、event log |
| 2 | L2 不適 | `我有點不舒服，頭有點暈。` | L2 | 先追問，不過度通報 |
| 3 | L1 跌倒 | `救命，我跌倒了，站不起來。` | L1 | 不要求移動、mock notification、abnormal event、summary |

完整主持稿、Temi 預期回應與 artifact 展示順序見 `docs/project/first_year_demo_scenario_script.md`。

### 6. 後台證據

現場可展示：

```text
memory/reminders.json
memory/event_log.jsonl
memory/abnormal_events/*.json
memory/summaries/*.md
logs/demo_cases/<run>/run_summary.json
logs/demo_cases/<run>/cases/*/parsed_output.json
logs/demo_cases/<run>/cases/*/command_request.json
logs/demo_cases/<run>/cases/*/memory_state_after.json
```

若真機或 real Hermes 不穩，立即切 deterministic artifacts：

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

## 現場快速故障切換

| 問題 | 快速處理 | 詳細章節 |
|---|---|---|
| 服務像當機 | 重跑一鍵快速重啟指令 | E2E 第一部分 |
| Discord 沒看到 Hermes 在線上 | 重啟 gateway 或確認 `discord.state=connected` | E2E Terminal 7 |
| Temi 沒聽到語音 | `adb devices -l`、重開 Temi App、看 logcat | E2E Terminal 3 |
| 有 ASR 但沒回應 | 開 `mosquitto_sub -t '#' -v` 看 topic 卡在哪 | E2E Debug 決策表 |
| Temi 沒說話 | 先跑 `manual_tts.py` 確認 TTS 回路 | E2E 第四部分 |
| Hermes 很慢 | 確認 resident mode，先預熱，必要時切 artifacts | E2E Terminal 5 |
| 錄影失敗 | scrcpy 檔案太小就改 ADB `--bugreport --size 720x1280` | E2E 第二部分 |
| Real route 延遲過高 | 展示 `tools/demo_case_runner.py --keep-artifacts` 輸出的 artifacts | 情境腳本 Artifact 展示方式 |

## 展示順序建議

1. 用 30 秒說明架構：Temi 感知、Hermes 本地推理、Bridge 安全驗證、structured memory。
2. 說明 Demo 邊界：Home-ESI 是 Demo risk policy，不是醫療分診；通知是 mock。
3. 展示 L3 日常服藥提醒，打開 reminder/memory artifact。
4. 展示 L2 不適追問，強調系統克制、不直接通報。
5. 展示 L1 跌倒求救，強調安全語句、mock notification 與 abnormal event。
6. 收尾展示 summary，說明後續可擴充 navigation、健康報告與正式通知流程。

## 收尾保存

Demo 後確認保存：

```bash
ls -lh /TemiAgent/logs/demo_recordings/*.mp4
find /TemiAgent/logs -maxdepth 2 -type d -name 'e2e_stack_validation_*' | tail
find /TemiAgent/logs/demo_cases -maxdepth 2 -name run_summary.json | tail
```

核心素材：錄影檔、`e2e_stack_validation_*` logs、`memory/event_log.jsonl`、`memory/abnormal_events/*.json`、`memory/summaries/*.md`、demo case artifacts。
