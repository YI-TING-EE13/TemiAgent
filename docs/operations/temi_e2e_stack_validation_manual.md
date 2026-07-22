# TemiAgent 服務重啟與端到端驗證操作手冊

最後更新日期：2026-06-04

## 1. 測試目的與適用情境

本文件用來讓操作員在沒有 Codex 協助時，可以自行完成 TemiAgent 全系統重啟、健康檢查與端到端驗證。測試範圍涵蓋 LM Studio、Hermes resident server、HermesTemiBridge、MQTT、Temi Android app、影像串流 adapter、action viewer，以及 mock 與真機路徑。

適用情境：

- 重新開機、容器重啟、服務異常後，需要恢復 TemiAgent。
- LM Studio 模型、context length、GPU 設定調整後，需要確認 Hermes 是否正確讀取模型。
- Demo 或實驗前，需要確認語音事件、Hermes 推理、MQTT 指令、Temi TTS、影像串流與 action viewer 都正常。
- Debug 端到端問題時，需要逐層定位是模型、Bridge、MQTT、Temi app、網路或影像串流出問題。

本文件的所有指令都必須在指定容器內執行。不要直接在 host `/home/yiting/TemiAgent` 修改或啟動專案服務，避免產生檔案權限與 runtime path 不一致問題。

## 2. 環境與前置條件

### 2.1 進入指定容器

在 host 只執行進入容器的指令：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

用途與參數：

- `docker exec -it`：進入已啟動的容器並開互動 shell。
- `yiting.TemiAgent_gpu_all`：TemiAgent 指定容器名稱。
- `cd /TemiAgent`：切到容器內專案根目錄。

正常結果：提示字元進入容器，且 `pwd` 顯示 `/TemiAgent`。

### 2.2 固定網路與服務資訊

目前預設值如下：

| 項目 | 預設值 |
|---|---|
| 專案容器路徑 | `/TemiAgent` |
| Host 專案路徑 | `/home/yiting/TemiAgent` |
| 容器/PC IP | `192.168.50.236` |
| 使用者電腦 IP | `192.168.50.233` |
| Temi IP | `192.168.50.205` |
| Robot ID | `temi-01` |
| LM Studio API | `http://127.0.0.1:1234/v1` |
| Hermes resident | `http://127.0.0.1:8765` |
| MQTT | `192.168.50.236:1883` |
| Vision ingest | `192.168.50.236:8080` |
| Frame broadcast | `192.168.50.236:8081` |
| Action viewer | `http://192.168.50.236:8010` |
| Action viewer llama-server | `127.0.0.1:8011` |

目前預設模型：

| 項目 | 預設值 |
|---|---|
| Model identifier | `google/gemma-4-31b` |
| Context length | `64000` |
| LM Studio data dir | `/TemiAgent/.lmstudio-data` |
| LM Studio visible GPUs | `0` by default; override with `0,1` or `0,1,2` |

未來如果要更換模型或 context length，優先改環境變數，不要硬改多個服務檔：

```bash
export LMSTUDIO_MODEL_ID='temi/gemma-4-31b-it-qat'
export LMSTUDIO_API_IDENTIFIER='google/gemma-4-31b'
export LMSTUDIO_CONTEXT_LENGTH='64000'
export MODEL_LOAD_ID='temi/gemma-4-31b-it-qat'
export MODEL_IDENTIFIER='google/gemma-4-31b'
export CONTEXT_LENGTH='64000'
```

用途與參數：

- `LMSTUDIO_MODEL_ID`：LM Studio 要載入的模型權重 key，例如 `temi/gemma-4-31b-it-qat`。
- `LMSTUDIO_API_IDENTIFIER`：LM Studio API/Hermes 使用的模型名稱，例如 `google/gemma-4-31b`。
- `LMSTUDIO_CONTEXT_LENGTH`：LM Studio 載入模型時使用的 context length。
- `MODEL_LOAD_ID`：一鍵測試腳本重啟 LM Studio 時要載入的模型權重 key。
- `MODEL_IDENTIFIER`：一鍵測試腳本驗證時期待看到的 API model identifier。
- `CONTEXT_LENGTH`：一鍵測試腳本驗證時期待看到的 context length。

## 3. 手動測試流程

### 3.1 檢查 Temi 與本機網路

```bash
cd /TemiAgent
TEMI_IP=192.168.50.205 PC_IP=192.168.50.236 ./tools/check_temi_connection.sh
```

用途與參數：

- `TEMI_IP`：Temi 機器人的 IP。
- `PC_IP`：容器/PC 對 Temi 提供服務的 IP。
- `check_temi_connection.sh`：列出本機網卡、路由、服務 port、Temi TCP probe、ADB 狀態與 MQTT 監看提示。

正常結果：

- `nc` 對 `192.168.50.205:5555` 成功，代表 ADB over TCP 可連線。
- `nc` 對 `192.168.50.236:1883`、`:8080`、`:8081` 成功或在後續服務啟動後成功。
- `adb devices -l` 看到 `192.168.50.205:5555`。

### 3.2 重啟 LM Studio 並載入預設模型

```bash
cd /TemiAgent
LMSTUDIO_MODEL_ID='temi/gemma-4-31b-it-qat' \
LMSTUDIO_API_IDENTIFIER='google/gemma-4-31b' \
LMSTUDIO_CONTEXT_LENGTH='64000' \
LMSTUDIO_VISIBLE_GPUS='0' \
./tools/start_lmstudio_3gpu.sh
```

用途與參數：

- `LMSTUDIO_MODEL_ID`：要載入的模型權重 key，例如 `temi/gemma-4-31b-it-qat`。
- `LMSTUDIO_API_IDENTIFIER`：API/Hermes 使用的模型名稱，例如 `google/gemma-4-31b`。
- `LMSTUDIO_CONTEXT_LENGTH`：模型 context length，目前預設 `64000`。
- `LMSTUDIO_VISIBLE_GPUS`：LM Studio daemon 可見 GPU，預設單卡 `0`；可改 `0,1` 或 `0,1,2` 測試多卡。
- `start_lmstudio_3gpu.sh`：卸載既有模型、停止 server/daemon、用指定 GPU 重啟 daemon、啟動 OpenAI-compatible API server、載入模型。

正常結果：

- `lms ps` 只看到 `google/gemma-4-31b`，context 為 `64000`。
- `curl http://127.0.0.1:1234/v1/models` 可以看到模型列表。
- `google/gemma-4-31b:2` 不應該在正常預設載入後仍存在；若出現通常代表先前同模型重複載入，請用 `lms unload --all` 後重跑啟動腳本。

### 3.3 啟動 MQTT broker

```bash
pkill -f 'mosquitto -c /TemiAgent/mqtt/mosquitto.conf' || true
mosquitto -c /TemiAgent/mqtt/mosquitto.conf -d
ss -ltnp | grep ':1883'
```

用途與參數：

- `pkill -f`：停止目前由專案設定檔啟動的 mosquitto。
- `mosquitto -c`：指定 MQTT broker 設定檔。
- `-d`：daemon mode，讓 broker 在背景執行。
- `ss -ltnp`：確認 TCP port 是否正在 listen。

正常結果：`ss` 顯示 `0.0.0.0:1883` 或等價 listen 狀態。

### 3.4 啟動 Overview adapter 與影像轉發

```bash
mkdir -p /TemiAgent/logs/manual_stack
cd /TemiAgent/temi_backend
setsid uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker 192.168.50.236 \
  --port 1883 \
  --vision-port 8080 \
  --frame-broadcast-port 8081 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared \
  --conversation-id conv_first_year_demo \
  > /TemiAgent/logs/manual_stack/temi-overview-adapter.log 2>&1 < /dev/null &
```

用途與參數：

- `setsid`：讓服務脫離目前 terminal session，關閉 shell 後仍可持續執行。
- `uv run python`：用 `temi_backend` 的 uv 環境啟動 adapter。
- `--broker`：MQTT broker IP。
- `--port`：MQTT broker port。
- `--vision-port`：Temi Android app WebSocket 影像/事件送入 port。
- `--frame-broadcast-port`：action viewer 讀取 frame stream 的 WebSocket port。
- `--shared-root`：adapter 寫入圖片與 shared artifacts 的容器路徑。
- `--bridge-root`：Bridge 讀取同一批 shared artifacts 的路徑。
- `--conversation-id`：本次 session 的 conversation id。

正常結果：

```bash
ss -ltnp | grep -E ':8080|:8081'
```

應看到 `0.0.0.0:8080` 與 `0.0.0.0:8081` 正在 listen。

### 3.5 啟動 Hermes resident server

```bash
mkdir -p /TemiAgent/logs/manual_stack
cd /TemiAgent
setsid python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md \
  > /TemiAgent/logs/manual_stack/hermes_resident.log 2>&1 < /dev/null &
```

用途與參數：

- `--host 127.0.0.1`：只讓容器內本機呼叫 resident Hermes。
- `--port 8765`：Hermes resident HTTP port。
- `--skill-path`：預載 Temi 控制、照護記憶、居家 ESI、Discord care assistant skills。

正常結果：

```bash
curl -sS http://127.0.0.1:8765/health
```

應看到 JSON 中至少包含：

- `"status": "ok"`
- `"provider": "custom"`
- `"base_url": "http://localhost:1234/v1"`
- `"model": "google/gemma-4-31b"`

目前 `/health` 不一定輸出 `context_length`。context 需用 `lms ps` 與 `/root/.hermes/config.yaml` 交叉確認：

```bash
PATH=/TemiAgent/.lmstudio-data/bin:$PATH lms ps
grep -E 'default:|context_length:' /root/.hermes/config.yaml
```

正常結果應看到 LM Studio context `64000`，Hermes config 中 `model.default: google/gemma-4-31b`、`model.context_length: 64000`，以及 `auxiliary.compression.context_length: 64000`。

### 3.6 啟動 HermesTemiBridge

```bash
mkdir -p /TemiAgent/logs/manual_stack /TemiAgent/logs/overview_bridge_resident
cd /TemiAgent/hermes_temi_bridge
setsid env \
  MQTT_BROKER_HOST=192.168.50.236 \
  MQTT_BROKER_PORT=1883 \
  TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
  TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
  HERMES_INVOKE_MODE=http \
  HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
  HERMES_TIMEOUT_SECONDS=180 \
  MEMORY_DIR=/TemiAgent/memory \
  LOG_DIR=/TemiAgent/logs/overview_bridge_resident \
  uv run --extra mqtt hermes-temi-bridge --env-file /TemiAgent/hermes_temi_bridge/.env.example \
  > /TemiAgent/logs/manual_stack/bridge_runtime.log 2>&1 < /dev/null &
```

用途與參數：

- `MQTT_BROKER_HOST` / `MQTT_BROKER_PORT`：Bridge 要連線的 MQTT broker。
- `TEMI_SHARED_BRIDGE_PATH`：Bridge 讀取圖片 artifacts 的路徑。
- `TEMI_SHARED_HERMES_PATH`：傳給 Hermes 的圖片路徑。
- `HERMES_INVOKE_MODE=http`：Bridge 透過 HTTP 呼叫 resident Hermes。
- `HERMES_HTTP_URL`：resident Hermes invoke endpoint。
- `HERMES_TIMEOUT_SECONDS`：Hermes 推理最長等待秒數。
- `MEMORY_DIR`：照護記憶檔案目錄。
- `LOG_DIR`：Bridge event log 目錄。
- `--extra mqtt`：讓 uv 安裝/啟用 MQTT runtime dependency extra。
- `--env-file`：載入 Bridge 預設環境設定，再由前方 `env` 覆蓋重要值。

正常結果：Bridge log 應顯示已連線 MQTT 並訂閱 ASR topic。可用下列指令確認：

```bash
tail -n 80 /TemiAgent/logs/manual_stack/bridge_runtime.log
```

### 3.7 重新開啟 Temi Android app

```bash
adb connect 192.168.50.205:5555
adb shell am force-stop com.robotemi.agent
adb shell am start -n com.robotemi.agent/.MainActivity
```

用途與參數：

- `adb connect`：連到 Temi Android debug port。
- `am force-stop`：停止目前 TemiAgent Android app。
- `am start -n`：啟動指定 package/activity。

正常結果：Temi app logcat 應看到：

- WebSocket 嘗試連 `http://192.168.50.236:8080/`。
- `WebSocket connected.`
- MQTT 嘗試連 `tcp://192.168.50.236:1883`。
- `Connected successfully.`
- 訂閱 `temi/temi-01/cmd/request`。

快速確認連線：

```bash
ss -tn state established | grep -E '192.168.50.205.*:(1883|8080)|:(1883|8080).*192.168.50.205'
```

正常結果應看到 Temi IP `192.168.50.205` 到本機 `1883` 與 `8080` 的 established TCP connection。

### 3.8 重啟 action viewer

```bash
cd /TemiAgent/anomaly_detection
./restart_action_viewer_8010.sh
```

用途與參數：

- 啟動 action viewer HTTP UI/API on `8010`。
- 同時啟動 llama-server on `8011`，預設使用 GPU `3`，避免和 LM Studio 目前使用的 GPU 組合打架；預設 LM Studio 用 GPU `0`，action viewer 用 GPU `3`。
- 預設讀取 `ws://127.0.0.1:8081` 的 frame broadcast。

正常結果：

```bash
curl -sS http://127.0.0.1:8010/health
```

應看到：

- `"ok": true`
- `"source_connected": true`
- `"frame_count"` 持續增加
- `"llama_server_ready": true`
- `"prediction_count"` 在等待一段時間後增加

## 4. 自動化測試與端到端驗證

### 4.1 Bridge unit tests

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

用途：驗證 Bridge event parsing、schema validation、MQTT runtime、Hermes client 與 command publication 邏輯。

正常結果：目前應為 `Ran 49 tests` 並顯示 `OK`。

### 4.2 temi_backend tests

```bash
cd /TemiAgent/temi_backend
uv run pytest
```

用途：驗證 overview adapter、backend helpers 與相關整合邏輯。

正常結果：目前應為 `22 passed`。

### 4.3 anomaly_detection tests

```bash
cd /TemiAgent/anomaly_detection
uv run python -m unittest discover -s tests
```

用途：驗證 action viewer 與異常辨識相關邏輯。

正常結果：目前應為 `Ran 22 tests` 並顯示 `OK`。

注意：此模組目前 `pytest` executable 可能不存在，因此使用 `python -m unittest` 是穩定路徑。

### 4.4 Local mock E2E

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

用途：不需要 Temi 硬體，直接用 mock ASR event、mock Hermes client 與 in-memory MQTT 驗證 Bridge 主要流程。

正常結果：JSON 中包含 `"status": "ok"`，並顯示 publish topic `temi/temi-01/cmd/request`。

### 4.5 Demo case runner

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

用途：跑第一年度 demo 的三個主要案例，並保留 artifacts 供檢查。

正常結果：JSON 中包含 `"status": "ok"`，且三個 cases 都是 success。

### 4.6 真機 ASR event 到 Temi TTS 閉環測試

先開兩個 MQTT 訂閱視窗，或用一鍵腳本自動處理。手動方式如下。

視窗 A：監看 Temi command request。

```bash
timeout 240 mosquitto_sub -h 192.168.50.236 -p 1883 -t 'temi/temi-01/cmd/request' -C 1 -v
```

視窗 B：監看 Temi command result。

```bash
timeout 240 mosquitto_sub -h 192.168.50.236 -p 1883 -t 'temi/temi-01/cmd/result' -C 1 -v
```

視窗 C：發送 canonical mock ASR event。

```bash
cd /TemiAgent
BROKER=192.168.50.236 \
PORT=1883 \
ROBOT_ID=temi-01 \
EVENT_ID=evt_live_route_$(date +%s) \
SHARED_ROOT=/TemiAgent/temi_shared \
BRIDGE_ROOT=/TemiAgent/temi_shared \
TEXT='請你說系統端到端測試成功' \
./tools/publish_mock_asr_event.sh
```

用途與參數：

- `mosquitto_sub -t 'temi/temi-01/cmd/request'`：確認 Bridge 有把 Hermes 回應轉成 Temi command。
- `mosquitto_sub -t 'temi/temi-01/cmd/result'`：確認 Temi Android app 有執行 command 並回報結果。
- `-C 1`：收到一則訊息就退出。
- `timeout 240`：最多等待 240 秒，避免操作卡住。
- `BROKER` / `PORT`：mock ASR 要發布到哪個 MQTT broker。
- `ROBOT_ID`：目標 robot id。
- `EVENT_ID`：本次測試事件 id，建議每次唯一。
- `SHARED_ROOT`：mock event 圖片 artifacts 寫入路徑。
- `BRIDGE_ROOT`：payload 裡給 Bridge 讀取 artifacts 的路徑。
- `TEXT`：模擬 Temi ASR 最終辨識文字。

正常結果：

- request topic 收到 JSON，`actions[0].type` 應為 `speak`。
- request text 應包含 `系統端到端測試成功` 或等價 TTS 內容。
- result topic 收到 JSON，`status` 應為 `success`，且 action completed。
- Temi 實機應說出測試句。

## 5. 一鍵測試腳本

主要流程可直接執行：

```bash
cd /TemiAgent
./tools/validate_temi_e2e_stack.sh
```

常用調整：

```bash
# 不重載大型 LM Studio 模型，只檢查目前服務
RESTART_LMSTUDIO=0 ./tools/validate_temi_e2e_stack.sh

# 只做服務與健康檢查，不跑 unit/mock/live 測試
RUN_UNIT_TESTS=0 RUN_LIVE_E2E=0 ./tools/validate_temi_e2e_stack.sh

# 更換載入權重、API identifier、context length 與 GPU 組合
MODEL_LOAD_ID='temi/gemma-4-31b-it-qat' MODEL_IDENTIFIER='google/gemma-4-31b' CONTEXT_LENGTH='64000' LMSTUDIO_VISIBLE_GPUS='0' ./tools/validate_temi_e2e_stack.sh

# Temi 或 PC IP 改變時
PC_IP=192.168.50.236 TEMI_IP=192.168.50.205 ./tools/validate_temi_e2e_stack.sh
```

腳本會輸出每個階段的 PASS/FAIL，並把服務 log、測試 log、MQTT request/result 存在：

```text
/TemiAgent/logs/e2e_stack_validation_<timestamp>/
```

## 6. 常見錯誤、原因與排除方式

| 錯誤現象 | 可能原因 | 排除方式 |
|---|---|---|
| 檔案變成奇怪 owner，或 host/容器權限錯亂 | 在 host 直接修改 `/home/yiting/TemiAgent` 或啟動服務 | 只在容器 `yiting.TemiAgent_gpu_all` 的 `/TemiAgent` 操作；必要時請管理員修正 owner。 |
| `google/gemma-4-31b` 和 `google/gemma-4-31b:2` 同時出現 | 同一模型被 LM Studio 重複載入，LM Studio 自動加 suffix 區分 instance | 執行 `lms unload --all` 後重跑 `/TemiAgent/tools/start_lmstudio_3gpu.sh`。 |
| `lms ps` 或 Hermes config 顯示 context 不是 `64000` | `/root/.hermes/config.yaml` 或 LM Studio 載入參數仍是舊值 | 確認 Hermes config 的 `model.context_length` 與 `auxiliary.compression.context_length`，並用 `LMSTUDIO_CONTEXT_LENGTH=64000` 重啟 LM Studio。 |
| LM Studio 顯示 `Invalid passkey` 或找不到 daemon | `PATH` 或 `LMSTUDIO_TARGET_DIR` 指到錯的 lms/資料目錄 | 使用 `/TemiAgent/tools/start_lmstudio_3gpu.sh`，確認 `LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data`。 |
| `curl http://127.0.0.1:8765/health` 失敗 | Hermes resident 沒啟動，或 LM Studio API 未就緒 | 先確認 `curl http://127.0.0.1:1234/v1/models`，再重啟 resident server。 |
| Bridge 沒有發布 command request | MQTT broker host 錯、Bridge 沒訂閱 ASR、Hermes invoke 失敗、mock event path 不一致 | 檢查 `/TemiAgent/logs/manual_stack/bridge_runtime.log`，確認 `MQTT_BROKER_HOST=192.168.50.236`、`HERMES_HTTP_URL=http://127.0.0.1:8765/invoke`、`TEMI_SHARED_*=/TemiAgent/temi_shared`。 |
| Temi 沒有 command result | Temi app 未連到 MQTT，或沒有訂閱 `cmd/request` | 用 ADB 重啟 app，檢查 logcat 是否有 `Connected successfully` 與 subscribed `temi/temi-01/cmd/request`。 |
| 影像串流沒有 frame | Temi app 沒連到 `192.168.50.236:8080`，adapter 沒啟動，或 PC IP 設錯 | 檢查 `ss -tn state established` 是否有 Temi 到 `8080`，並看 adapter log。 |
| action viewer health `source_connected=false` | `8081` frame broadcast 未啟動或 viewer 連錯 source URL | 先重啟 overview adapter，再跑 `/TemiAgent/anomaly_detection/restart_action_viewer_8010.sh`。 |
| action viewer `llama_server_ready=false` | llama-server 尚未完成載入，或 GPU/模型路徑錯 | 等 1-2 分鐘後重查 health；若仍失敗，檢查 `/TemiAgent/anomaly_detection/action_viewer.log`。 |
| `uv run pytest` 在 anomaly_detection 找不到 pytest | 該模組未安裝 pytest executable | 使用 `uv run python -m unittest discover -s tests`。 |
| live E2E timeout | Temi 未在線、MQTT topic 不通、Hermes 推理逾時、Bridge 沒發布 command | 逐層檢查 MQTT、Hermes health、Bridge log、Temi established connection。 |

## 7. 測試完成後的正常功能確認

測試通過時，應同時滿足下列條件：

- `lms ps` 顯示 `google/gemma-4-31b`，context 為 `64000`，沒有多餘 `:2` instance。
- `curl http://127.0.0.1:8765/health` 顯示 `status=ok`，model/base_url 符合預期；context 用 `lms ps` 與 `/root/.hermes/config.yaml` 確認。
- `ss -ltnp` 顯示 `1234`、`1883`、`8080`、`8081`、`8765`、`8010`、`8011` 需要的 port 已 listen。
- Temi `192.168.50.205` 與本機 `192.168.50.236:1883`、`:8080` 有 established connection。
- Bridge unit tests、temi_backend tests、anomaly_detection tests、local mock E2E、demo case runner 全部通過。
- action viewer `/health` 顯示 `ok=true`、`source_connected=true`、`frame_count` 增加、`llama_server_ready=true`。
- live E2E 的 `cmd/request` 與 `cmd/result` 都收到，且 result `status=success`。
- Temi 實機能說出測試句 `系統端到端測試成功`。

自然語音測試需要現場人員對 Temi 說話，因此本文件的一鍵腳本使用 canonical mock ASR event 來驗證 ASR 之後的硬體閉環。如果要測自然語音，請在上述服務都通過後，現場對 Temi 說出測試句，再用 MQTT 與 logcat 確認後續 command/result。
