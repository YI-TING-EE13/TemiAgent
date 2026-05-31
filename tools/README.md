# Tools 模組 README

最後更新日期：2026-05-31

## 本文件維護規則

這份 README 是 `tools/` 的快速入口。只要新增腳本、改 CLI 參數、改啟動順序或改測試責任，都要同步更新本文件。

## 模組定位

`tools/` 收納跨模組開發、測試與 Demo 操作用腳本。這些腳本不是核心服務本體，但負責把 MQTT、Bridge、Temi backend、shared volume、resident Hermes 串起來。

## 腳本索引

| Script | 用途 |
|---|---|
| `hermes_resident_server.py` | 啟動低延遲 resident Hermes HTTP worker，供 Bridge `HERMES_INVOKE_MODE=http` 使用。 |
| `temi_overview_adapter.py` | 將已安裝 Android app 的 legacy topics 轉成 canonical Overview contract，並重用 `temi_backend` video buffer。 |
| `e2e_test_runner.py` | 不需硬體的本地 mock E2E smoke test。 |
| `demo_case_runner.py` | 跑第一年度 Demo 三個固定照護案例並輸出 artifacts。 |
| `create_mock_event_images.py` | 產生 ASR event 測試用三張 mock images。 |
| `publish_mock_asr_event.sh` | 發送 canonical mock ASR event。 |
| `subscribe_cmd_request.sh` | 訂閱 canonical command request，方便觀察 Bridge output。 |
| `publish_mock_cmd_result.sh` | 發送 mock command result。 |
| `start_temi_pc_services.sh` | 啟動 PC 端 Temi legacy services。 |
| `start_temi_pc_services_background.sh` | 背景啟動 PC 端 services。 |
| `check_temi_connection.sh` | 檢查 Temi ADB、MQTT、WebSocket 等連線狀態。 |

## 常用流程

### 本地 mock E2E

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

### Demo case runner

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

輸出包含三個 case 的 input event、Hermes raw output、parsed output、command request/result、memory snapshot 與 run summary。若指定 `--output-dir logs/demo_cases/<name>`，artifact 會保留在該目錄。

### Resident Hermes

```bash
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md
```

Health check：

```bash
curl -s http://127.0.0.1:8765/health
```

### Legacy app to canonical contract

```bash
cd /TemiAgent/temi_backend
uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker 192.168.50.236 \
  --port 1883 \
  --vision-port 8080 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared
```

## 維護注意

- 腳本應保持可從 `/TemiAgent` 絕對路徑執行，方便 runbook 複製。
- 修改 topic、schema 或 path mapping 時，必須同步更新 `hermes_temi_bridge/README.md` 與 `docs/operations/` runbooks。
- Demo 用 IP、機器人狀態與臨時結果應放 runbook，不要硬編到 reusable scripts。
