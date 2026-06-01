# 第一年度 Demo 端到端串接操作手冊

最後更新日期：2026-06-01

## 目的

本手冊用於進行「Temi 端收到語音或影像後，交由 Hermes 對話推理，再回到 Temi 語音回應」的端到端串接測試。主線路徑採用目前已安裝在 Temi 上的 legacy Android app，加上 `tools/temi_overview_adapter.py` 轉成 canonical Overview contract，最後由 HermesTemiBridge 呼叫 resident Hermes。2026-06-01 起，adapter 只負責 ASR 與 camera，不再轉發 command；Temi app 直接執行 canonical `cmd/request`。

本手冊假設所有指令都在 container 內執行。若是在 host terminal，先進入 container：

```bash
docker exec -it 3f9799248a6c bash
cd /TemiAgent
```

## 測試主線

```text
Temi App ASR + Picture Streaming
  -> legacy MQTT topics + WebSocket frames
  -> tools/temi_overview_adapter.py
  -> temi/temi-01/asr/final + temi_shared image paths
  -> HermesTemiBridge
  -> resident Hermes HTTP worker
  -> validated robot actions + memory actions
  -> temi/temi-01/cmd/request
  -> Temi app directly executes TTS/action
  -> temi/temi-01/cmd/result
```

## 事前條件

- PC IP：`192.168.50.236`。
- Temi IP：`192.168.50.205`。
- MQTT broker：`192.168.50.236:1883`。
- Picture Streaming WebSocket：`192.168.50.236:8080`。
- Temi Android app package：`com.robotemi.agent`。
- LM Studio / Hermes provider 已可被 Hermes 使用。
- 所有操作在 `/TemiAgent` container 內執行；修改文件或 skills 也應進 container，避免 host 權限與 root/nobody owner 不一致。

## 重要注意

Overview / Hermes 主線要讓 `tools/temi_overview_adapter.py` 佔用 `8080` 接收 Picture Streaming。因此不要同時執行 `./tools/start_temi_pc_services.sh` 與 adapter，否則 `temi_backend` 和 adapter 會搶同一個 WebSocket port。

- 主線測試：只啟動 MQTT broker，讓 adapter 負責 `8080`。
- 備援展示：才使用 `./tools/start_temi_pc_services.sh` 跑 legacy backend + LM Studio/VLM route。

## Terminal 0：快速確認環境

用途：確認 PC、Temi、ADB 與常用 port 狀態。這一步先抓硬體與網路問題，避免後面誤判是 Hermes 或 Bridge 問題。

```bash
cd /TemiAgent
./tools/check_temi_connection.sh
```

判讀方式：

- `192.168.50.205:5555 device`：Temi ADB 可用。
- `1883 open`：MQTT broker 已啟動。
- `8080 open`：目前已有 WebSocket receiver；若尚未啟動 adapter，這裡可能暫時是 refused。

注意事項：

- 若 ADB 顯示 `offline`，需要在 Temi 螢幕上重新允許 USB debugging，或重啟 Temi 的 wireless ADB。
- 若 `1883` 不通，先執行 Terminal 1 啟動 MQTT。
- 若 `8080` 被 `temi_backend` 佔用，請停止 legacy backend 後再啟動 adapter。

## Terminal 1：啟動 MQTT broker

用途：MQTT 是 Temi、adapter、Bridge 之間的事件匯流排。主線只需要 broker，不先啟動 `temi_backend`。

```bash
cd /TemiAgent
if ss -ltn | grep -q ':1883 '; then
  echo 'MQTT port 1883 is already listening.'
else
  mosquitto -c /TemiAgent/mqtt/mosquitto.conf -d
fi
```

確認：

```bash
ss -ltnp | grep ':1883'
```

注意事項：

- `mosquitto -d` 會背景執行，可以保留 terminal 做其他檢查。
- 若 broker 已經存在，不需要重複啟動。

## Terminal 2：啟動 Temi App 與觀察 Android log

用途：確認 Temi app 已啟動、MQTT 已連線、WebSocket 影像有送出、ASR 狀態正常。

```bash
adb connect 192.168.50.205:5555
adb shell am start -n com.robotemi.agent/.MainActivity
adb logcat '*:I' | grep -E 'MainActivity|WebSocketClient|MqttManager|CameraManager|AgentStateMachine'
```

成功時常見 log：

```text
MqttManager: Connected successfully.
AgentStateMachine: Transitioned to: ASR_LISTENING
Video packets sent
MainActivity: ACTION_SPEAK: "..."
```

注意事項：

- 若看不到 `Video packets sent`，adapter 無法產生三張同步影像，後續 canonical ASR event 可能被拒絕或回覆「看不到畫面」。
- 若 app 沒進入聆聽狀態，可用 Terminal 3 的 MQTT monitor 確認是否有 ASR topic。

## Terminal 3：開 MQTT 全域監看

用途：觀察整條鏈路上的 topic，這是端到端 debug 最重要的視窗。

```bash
mosquitto_sub -h 192.168.50.236 -p 1883 -t '#' -v
```

測試過程中應依序看到：

```text
temi/event/asr {...}
temi/temi-01/asr/final {...}
temi/temi-01/cmd/request {...}
temi/temi-01/cmd/result {...}
```

判讀方式：

- 只看到 `temi/event/asr`：Temi ASR 有進來，但 adapter 沒轉 canonical event。
- 看到 `asr/final` 但沒有 `cmd/request`：Bridge 或 Hermes 沒成功產生 action。
- 看到 `cmd/request` 但沒有 `cmd/result` 或 Temi 沒說話：Temi app MQTT subscription、robot id、command schema 或 TTS 端有問題。
- Canonical 主線中若同一次回應又出現 `temi/action/speak`，代表有舊 adapter/backend 重複轉發 command，應停止它。

## Terminal 4：啟動 Overview adapter

用途：銜接目前 Temi App 的 legacy ASR 與 camera stream 到本專案 canonical Overview ASR event。它會開 `0.0.0.0:8080` 接收 Picture Streaming，從 frame buffer 取三張影像，寫入 `temi_shared/events/...`，再把 image paths 放進 ASR event；它不訂閱或轉發 command。

```bash
cd /TemiAgent/temi_backend
uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker 192.168.50.236 \
  --port 1883 \
  --vision-port 8080 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared \
  --conversation-id conv_first_year_demo
```

成功時應看到 adapter connected 訊息；當使用者對 Temi 說話時，Terminal 3 會看到 `temi/temi-01/asr/final`。

注意事項：

- 若 `8080` 已被佔用，先確認是否有 `temi_backend` 還在跑。
- `--shared-root` 是 container 實際寫檔位置。
- `--bridge-root` 是 Bridge 驗證 image path 時看到的路徑；目前 container 內同樣使用 `/TemiAgent/temi_shared`。
- 若 adapter log 顯示 no aligned vision frames，代表 ASR 時間點附近沒有足夠的影像 frame；adapter 不會用 TTS fallback，以免造成重複說話。

## Terminal 5：啟動 resident Hermes

用途：把 Hermes 常駐成 HTTP worker，避免每次 ASR 都重新啟動 CLI 造成過長延遲。Demo 主線優先使用此模式。

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md
```

確認 worker 存活：

```bash
curl -s http://127.0.0.1:8765/health
```

成功時應回傳健康狀態 JSON。

注意事項：

- 第一次呼叫可能較慢，建議正式 Demo 前先講一句測試語音預熱。
- 若要展示 Hermes persistent memory，可加上 `--hermes-home /root/.hermes/profiles/care-assistant --enable-memory --toolsets memory`，但 smoke test 先不開會比較快。
- 若 Demo 透過 Discord/gateway 請 Hermes「看手勢 / 看相機」，確認 `.hermes.md`、`docker/SOUL.md` 與 `temi-discord-care-assistant` 已在目前 profile 可見；沒有 image attachment 或 frame path 時，Hermes 應要求觸發/傳送 Temi camera event。
- Hermes output 必須是 JSON action plan；若 resident server 回自然語言，Bridge 會拒絕。

## Terminal 6：啟動 HermesTemiBridge HTTP mode

用途：Bridge 訂閱 canonical ASR event，呼叫 resident Hermes，驗證 JSON schema 與 action，再發布 canonical command request；memory actions 會寫入 `MEMORY_DIR`，不直接發給 Temi。

```bash
cd /TemiAgent/hermes_temi_bridge
MQTT_BROKER_HOST=192.168.50.236 \
MQTT_BROKER_PORT=1883 \
TEMI_SHARED_BRIDGE_PATH=/TemiAgent/temi_shared \
TEMI_SHARED_HERMES_PATH=/TemiAgent/temi_shared \
HERMES_INVOKE_MODE=http \
HERMES_HTTP_URL=http://127.0.0.1:8765/invoke \
HERMES_TIMEOUT_SECONDS=180 \
MEMORY_DIR=/TemiAgent/memory \
LOG_DIR=/TemiAgent/logs/overview_bridge_resident \
uv run --extra mqtt hermes-temi-bridge --env-file /TemiAgent/hermes_temi_bridge/.env.example
```

成功時：

- Terminal 3 會看到 `temi/temi-01/cmd/request`。
- Temi app 會直接執行 `cmd/request` 中的 robot action。
- Terminal 3 會看到 Temi app 發回 `temi/temi-01/cmd/result`。
- Temi 會說出 Hermes 規劃的回應。
- `logs/overview_bridge_resident/*.jsonl` 會記錄 ASR event、Hermes latency、command result。
- `memory/event_log.jsonl`、`memory/abnormal_events/` 或 `memory/summaries/` 可能被更新，視 Hermes output actions 而定。

注意事項：

- `HERMES_TIMEOUT_SECONDS=180` 是為了容忍 real Hermes 較慢；Demo 時仍應先預熱。
- `TEMI_SHARED_BRIDGE_PATH` 與 adapter 的 `--bridge-root` 必須一致，否則 Bridge 會找不到 image path。
- 若 Bridge 印出 schema validation error，優先檢查 Hermes 是否輸出 `cognitive_state.home_esi_level` 與 `risk_reason`。

## 觸發測試

### A. 使用真 Temi 語音

對 Temi 說：

```text
王先生今天吃完藥了
```

或：

```text
我有點不舒服
```

預期：

- Terminal 3 看到 legacy ASR 與 canonical ASR。
- Bridge 呼叫 Hermes 後發布 `cmd/request`。
- Temi app 直接執行 canonical command，並回 `cmd/result`。
- Temi 用中文回應。

### B. 手動測 TTS 回路

用途：若 Hermes 鏈路還沒通，先確認 PC 到 Temi 的 speak command 可用。

```bash
cd /TemiAgent/temi_backend
uv run python scripts/manual_tts.py \
  --broker 192.168.50.236 \
  --port 1883 \
  --text '這是 Temi MQTT 語音測試' \
  --language ZH_TW
```

預期 Temi 直接說出測試句。

### C. 無硬體備援測試

用途：確認 Bridge schema、Hermes mock route、memory action 與 artifacts 沒壞；不代表真 Temi 已接通。

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
python3 tools/demo_case_runner.py --keep-artifacts
```

預期：

```text
e2e_test_runner.py -> status ok
demo_case_runner.py -> three cases success
```

## Legacy backend 備援路線

若 real Hermes 或 Overview 主線當天不穩，可以改走先前已驗證的 legacy backend + LM Studio/VLM route。這條路線仍可展示 Temi ASR、Picture Streaming、Local VLM 與 TTS 閉環，但不是本手冊主線。

```bash
cd /TemiAgent
./tools/start_temi_pc_services.sh
```

注意：使用此備援路線時，請不要同時啟動 `tools/temi_overview_adapter.py`，因為兩者都會使用 `8080`。

## 成功驗收標準

一次完整端到端測試至少要能證明：

- Temi 語音進入 `temi/event/asr`。
- Adapter 產生 `temi/temi-01/asr/final`，且含三張 `vision.frames` image paths。
- Bridge 成功呼叫 resident Hermes。
- Hermes output 通過 Bridge validation。
- Bridge 發布 `temi/temi-01/cmd/request`。
- Temi app 直接執行 `temi/temi-01/cmd/request`。
- Temi 實際說出回應並發布 `cmd/result`。
- Bridge log 或 memory artifact 可追溯該次互動。

## 常見問題與處理

| 現象 | 優先檢查 |
|---|---|
| Temi 沒有 ASR topic | App 是否啟動、ADB 是否 online、Temi 是否在聆聽狀態。 |
| 有 ASR 但 adapter 不發 canonical event | 是否有三張同步影像、`8080` 是否收到 video frames。 |
| Adapter 無法啟動 | `8080` 是否已被 `temi_backend` 或其他服務佔用。 |
| Bridge 沒反應 | Bridge 是否訂閱同一個 broker、topic 是否為 `temi/temi-01/asr/final`。 |
| Hermes 很慢 | 使用 resident mode、先預熱一次、確認不是 CLI mode。 |
| Bridge 拒絕 Hermes output | 檢查 JSON-only、`actions`、`cognitive_state.home_esi_level`、`risk_reason`。 |
| Temi 沒說話 | 是否有 `temi/temi-01/cmd/request`、Temi app 是否仍 connected to MQTT、robot id 是否一致、是否有 `cmd/result`。 |
| memory 沒更新 | Hermes 是否輸出 memory actions、Bridge 是否設定 `MEMORY_DIR=/TemiAgent/memory`。 |

## Demo 現場建議

- 先跑一次 Terminal 3 MQTT monitor，讓問題能立即定位。
- 先用 `manual_tts.py` 確認 Temi 能說話，再進入 Hermes 主線。
- Real Hermes 第一次呼叫可能慢，正式展示前先用一句簡單語音預熱。
- 若 real route 延遲過高，切換到 `tools/demo_case_runner.py` artifacts 展示照護記憶與 Home-ESI 結果。
- P4 Navigation 本輪先跳過，不納入端到端主線驗收。
