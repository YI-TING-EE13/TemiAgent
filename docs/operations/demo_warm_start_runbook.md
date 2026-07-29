# Demo 暖啟動操作手冊

最後更新日期：2026-07-29

## 適用情境與邊界

本手冊適用於 LM Studio 已經在 `127.0.0.1:1234` 載入模型，且 MQTT broker 已經在 `1883` 運作時，啟動第一年度 Demo 的 canonical 主線：Overview adapter、resident Hermes、HermesTemiBridge、Hermes Discord gateway 與 action viewer。

本手冊會保留既有的 LM Studio 與 broker，不會停止、重載或接管它們。若需要從零建立或完整重啟整套環境，使用 [第一年度 Demo 端到端串接操作手冊](first_year_demo_e2e_operation_manual.md) 的一鍵流程；該流程會重啟 LM Studio、broker 與其他 Demo service，不適合正在使用中的暖啟動情境。

本手冊不啟動 legacy `temi-backend`。canonical 主線的 Overview adapter 使用 `8080` 接收 Picture Streaming，並在 `8081` 提供 decoded JPEG frame broadcast；legacy backend 也會使用 `8080`，兩者不得同時啟動。

異常偵測是 Experimental Demo。action viewer 預設在判定 `falls down`、`lies on the floor` 或 `fights` 時發布 abnormal event、直接發布一則 Demo-only pre-alert `cmd/request`，並嘗試透過既有 Discord webhook 通知。這條 pre-alert 路徑是已知的 Demo-only safety gap，並未經 Bridge dispatch；Discord 是 best-effort side channel，不是緊急服務。操作員必須在啟動 viewer 前確認這些預設行為符合當次展示授權。

## 服務與啟動順序

| Component | Port | 本手冊動作 | 健康證據 |
|---|---:|---|---|
| LM Studio | `1234` | 保留既有 service | `/v1/models`、`lms ps` |
| MQTT broker | `1883` | 保留既有 listener | `mosquitto_pub` transport probe |
| Overview adapter | `8080`, `8081` | 啟動 | 兩個 listener；viewer frame source connected |
| resident Hermes | `8765` | 啟動 | `/health` 回傳 `status: ok` |
| HermesTemiBridge | 無 HTTP port | 啟動 | log 顯示已連線 MQTT |
| Hermes Discord gateway | gateway runtime | 若未在運作則啟動 | gateway status 與 `discord.state=connected` |
| action viewer | `8010`, `8011` | 啟動 | `/health`、llama.cpp backend ready |

執行中的 broker 如果不是目前 worktree 的 `mqtt/mosquitto.conf` 所啟動，或無法由 `ss` 取得 PID，視為 external listener。只驗證 transport；不要停止、重啟或替換它。

## 1. 進入指定容器

所有指令必須在指定 container 內執行：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
pwd
whoami
git rev-parse --show-toplevel
git status --short
```

預期工作目錄是 `/TemiAgent`。保留既有未提交修改；不要用 reset、clean 或 checkout 丟棄它們。

## 2. 唯讀預檢

先確認模型、broker 與將要使用的 port。以下 probe 不會發送 canonical ASR、command 或 abnormal event。

```bash
cd /TemiAgent
PATH=/TemiAgent/.lmstudio-data/bin:$PATH lms ps
curl --max-time 5 -fsS http://127.0.0.1:1234/v1/models

ss -ltnp 'sport = :1883' || true
ps -efww | rg '[m]osquitto' || true
timeout 5 mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'temi/demo-health/probe' \
  -m 'warm-start-probe'

for port in 8080 8081 8765 8010 8011; do
  echo "=== port $port ==="
  ss -ltnp "sport = :$port" || true
done
```

繼續前必須符合下列條件：

- LM Studio API 可回應，`lms ps` 顯示當次 Demo 要使用的 model identifier 與 context length。
- `1883` 有可連線的 broker，且 transport probe 成功。
- `8080`、`8081`、`8765`、`8010`、`8011` 沒有未知 listener。若任一 port 已被使用，先依 [safe service operations](safe_service_operations.md) 驗證 PID、command line、cwd 與 executable；不要啟動第二個 service，也不要用 `pkill` 或 `killall`。

若 Temi Android app 已連線，adapter 啟動後應使用 PC 對 Temi 可達的 IP 作為 Android MQTT 與 Picture Streaming endpoint。下方 PC 端 service 彼此使用 `127.0.0.1` 連 broker；這不會取代 Android 的網路設定。

## 3. 建立本次啟動的 log 目錄

每次暖啟動使用新的 log root。請在同一個 shell 保留 `DEMO_LOG_ROOT`，直到停止本次啟動的 services。

```bash
cd /TemiAgent
export DEMO_LOG_ROOT="/TemiAgent/logs/demo_runtime_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEMO_LOG_ROOT" /TemiAgent/logs/overview_bridge_resident
printf '%s\n' "$DEMO_LOG_ROOT"
```

## 4. 啟動 canonical Demo services

在執行下列區塊前，重跑 port 預檢並確認 `8080`、`8081`、`8765`、`8010`、`8011` 都沒有 listener。此區塊不碰 `1234` 或 `1883`。

### 4.1 Overview adapter：ASR 與 WebSocket frame route

```bash
cd /TemiAgent/temi_backend
setsid uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker 127.0.0.1 \
  --port 1883 \
  --vision-port 8080 \
  --frame-broadcast-port 8081 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared \
  --conversation-id conv_first_year_demo \
  > "$DEMO_LOG_ROOT/overview_adapter.log" 2>&1 < /dev/null &
echo $! > "$DEMO_LOG_ROOT/overview_adapter.pid"
```

adapter 只處理 legacy `temi/event/asr` 與 camera frames，並發布 canonical `temi/{robot_id}/asr/final`。它不會將 command 轉發到 legacy TTS route。

### 4.2 resident Hermes：HTTP reasoning worker

```bash
cd /TemiAgent
setsid python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md \
  > "$DEMO_LOG_ROOT/hermes_resident.log" 2>&1 < /dev/null &
echo $! > "$DEMO_LOG_ROOT/hermes_resident.pid"
```

### 4.3 HermesTemiBridge：canonical validation and dispatch boundary

```bash
cd /TemiAgent/hermes_temi_bridge
setsid env \
  MQTT_BROKER_HOST=127.0.0.1 \
  MQTT_BROKER_PORT=1883 \
  TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
  TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
  HERMES_INVOKE_MODE=http \
  HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
  HERMES_TIMEOUT_SECONDS=180 \
  MEMORY_DIR=/TemiAgent/memory \
  LOG_DIR=/TemiAgent/logs/overview_bridge_resident \
  uv run --extra mqtt hermes-temi-bridge \
  --env-file /TemiAgent/hermes_temi_bridge/.env.example \
  > "$DEMO_LOG_ROOT/bridge.log" 2>&1 < /dev/null &
echo $! > "$DEMO_LOG_ROOT/bridge.pid"
```

Bridge 沒有獨立 HTTP health endpoint。不要把 resident Hermes `/health` 當成 Bridge health；使用 MQTT connection log 與 event trace 檢查 Bridge。

### 4.4 Hermes Discord gateway

先確認 gateway 是否已經在運作。既有 gateway 視為 external service，保留它即可。

```bash
cd /TemiAgent
if /TemiAgent/hermes-agent/venv/bin/hermes gateway status 2>&1 | grep -q 'Gateway is running'; then
  echo 'Gateway is already running; preserving the existing process.'
else
  setsid env HERMES_ACCEPT_HOOKS=1 \
    /TemiAgent/hermes-agent/venv/bin/hermes gateway run \
    > "$DEMO_LOG_ROOT/hermes_gateway.log" 2>&1 < /dev/null &
  echo $! > "$DEMO_LOG_ROOT/hermes_gateway.pid"
fi
```

### 4.5 action viewer：實驗性異常偵測

確認本次 Demo 授權 pre-alert 與 Discord best-effort notification 後，以 GPU `3` 執行 managed llama.cpp server 與 pose preprocessing：

```bash
cd /TemiAgent/anomaly_detection
export YOLO_CONFIG_DIR=/tmp/Ultralytics
setsid .venv/bin/python ./temi_action_viewer.py \
  --host 0.0.0.0 \
  --port 8010 \
  --source-url ws://127.0.0.1:8081 \
  --model gemma-4-e4b-finetuned@q8_0 \
  --gguf-model-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.Q8_0.gguf \
  --mmproj-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.BF16-mmproj.gguf \
  --llama-server /TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server \
  --llama-server-port 8011 \
  --llama-cuda-visible-devices 3 \
  --pose-mode auto \
  --pose-model yolo26x-pose.pt \
  --pose-device 3 \
  --max-output-tokens 96 \
  --inference-interval 4 \
  --abnormal-cooldown-seconds 180 \
  --abnormal-publish enabled \
  --discord-notify enabled \
  --pre-alert-speak enabled \
  > "$DEMO_LOG_ROOT/action_viewer.log" 2>&1 < /dev/null &
echo $! > "$DEMO_LOG_ROOT/action_viewer.pid"
```

若當次展示只允許觀察影像，不允許自動 pre-alert 或 Discord notification，將最後三個參數改為：

```text
--abnormal-publish disabled
--discord-notify disabled
--pre-alert-speak disabled
```

`anomaly_detection/restart_action_viewer_8010.sh` 是已存在的 targeted restart utility。它適合在已驗證 `8010` listener 屬於正確 viewer 後使用；本手冊的 fresh-start command 避免把既有 listener 視為本次 service。

## 5. 健康檢查與可開始 Demo 的條件

等待 service 啟動後執行以下檢查：

```bash
cd /TemiAgent
curl --max-time 5 -fsS http://127.0.0.1:8765/health
curl --max-time 5 -fsS http://127.0.0.1:8010/health
ss -ltnp | rg ':(1234|1883|8080|8081|8765|8010|8011)'
tail -n 40 "$DEMO_LOG_ROOT/overview_adapter.log"
tail -n 40 "$DEMO_LOG_ROOT/bridge.log"
/TemiAgent/hermes-agent/venv/bin/hermes gateway status
```

viewer health 應至少滿足：

- `ok` 是 `true`。
- `source_connected` 是 `true`。
- `frame_count` 持續增加，表示 adapter 的 `8081` broadcast 有 frames。
- `llama_server_ready` 是 `true`。
- `abnormal_cooldown_seconds` 是 `180.0`。
- `abnormal_publish` 與 `discord_notify` 的設定符合當次授權。
- 啟動 command 中的 `--pre-alert-speak` 值符合當次授權；目前 viewer health 不回傳這個欄位。

Discord 狀態只讀取 state，不輸出設定內容或 credential：

```bash
python3 - <<'PY'
import json
from pathlib import Path

path = Path('/root/.hermes/gateway_state.json')
if not path.exists():
    print('gateway state file is absent')
else:
    state = json.loads(path.read_text(encoding='utf-8'))
    discord = (state.get('platforms') or {}).get('discord') or {}
    print('discord.state=' + str(discord.get('state')))
PY
```

只有 gateway status 顯示 running 且 `discord.state=connected` 時，Discord gateway 才算 ready。Bridge 只證明已連上 broker；本手冊不發布 mock ASR、TTS 或 command result，因此不把 service startup 宣稱為完整硬體 E2E。開始情境前，可先從 viewer health 確認 Temi camera frame 正在流入。

action viewer UI：`http://127.0.0.1:8010/`。若從其他裝置查看，使用當次 PC 對該裝置可達的 IP；不要把私人 IP 寫入 tracked documentation。

## 6. 正常停止與恢復

先停止 action viewer。現有 stop utility 會用 `8010`／`8011` listener、cwd 與 command line 確認目標，不會用 broad process pattern：

```bash
cd /TemiAgent/anomaly_detection
./stop_action_viewer_8010.sh
```

對本次由 `DEMO_LOG_ROOT` 記錄的 adapter、resident Hermes、Bridge 和 gateway，先驗證 PID 的 cwd 與 command line，再發送 `TERM`。以下 function 只接受同時符合預期 cwd 與 command token 的 PID：

```bash
stop_recorded_service() {
  local label="$1"
  local pid_file="$2"
  local expected_cwd="$3"
  local token="$4"
  local pid cwd cmdline

  [ -f "$pid_file" ] || { echo "$label was preserved or not started by this run"; return 0; }
  pid="$(cat "$pid_file")"
  [ -d "/proc/$pid" ] || { echo "$label PID $pid is already gone"; return 0; }
  cwd="$(readlink -f "/proc/$pid/cwd")"
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  if [ "$cwd" != "$expected_cwd" ] || [[ "$cmdline" != *"$token"* ]]; then
    echo "Refusing to stop $label PID $pid: identity mismatch" >&2
    return 1
  fi
  ps -p "$pid" -o pid,ppid,user,lstart,etime,args
  kill -TERM "$pid"
}

stop_recorded_service adapter \
  "$DEMO_LOG_ROOT/overview_adapter.pid" \
  /TemiAgent/temi_backend \
  temi_overview_adapter.py
stop_recorded_service resident_hermes \
  "$DEMO_LOG_ROOT/hermes_resident.pid" \
  /TemiAgent \
  tools/hermes_resident_server.py
stop_recorded_service bridge \
  "$DEMO_LOG_ROOT/bridge.pid" \
  /TemiAgent/hermes_temi_bridge \
  hermes-temi-bridge
stop_recorded_service gateway \
  "$DEMO_LOG_ROOT/hermes_gateway.pid" \
  /TemiAgent \
  'hermes gateway run'
```

Gateway 的 PID file 只會在本手冊啟動新 gateway 時建立；若 gateway 原本已在運作，停止流程會保留它。LM Studio 與 broker 沒有 PID file，必須保留。最後確認本次 service 的 listener 已消失，且保護中的 `1234` 和 `1883` 仍維持：

```bash
sleep 2
ss -ltnp | rg ':(1234|1883|8080|8081|8765|8010|8011)' || true
```

若任何 PID identity 不符、健康檢查失敗或 runtime service 表現異常，停止本次已驗證的 PID，保留 LM Studio／broker，並依 [safe service operations](safe_service_operations.md) 進行 recovery。不要刪除 runtime logs、發送測試 command 或用廣泛的 process kill 來掩蓋問題。

## 7. 已驗證範圍與限制

2026-07-29 在指定 container 內執行本手冊的流程時，已驗證：

- 既有 LM Studio API 可回應，resident Hermes health 回傳 `status: ok`。
- 既有 broker transport probe 成功；該 broker 被保留，沒有重啟。
- adapter 取得 Temi camera frames，`8080`、`8081` listener 可用。
- action viewer health 顯示 source connected、llama.cpp backend ready 與 pose enabled。
- Bridge log 顯示已連上 MQTT，Discord gateway status 為 running 且 Discord state 為 connected。

本次沒有發布 mock ASR、manual TTS 或 command result，也沒有執行 Android hardware E2E。因此，服務啟動與 camera ingest 已有 evidence；語音至 `cmd/result` 的完整硬體閉環仍需在獲得當次硬體操作授權後，依 [第一年度 Demo 端到端串接操作手冊](first_year_demo_e2e_operation_manual.md) 的驗證程序執行。
