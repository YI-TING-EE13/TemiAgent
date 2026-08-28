# 第一年度 Demo 端到端串接操作手冊

> Historical / legacy reference. Do not use as the current canonical Demo lifecycle.
> Use the [current Demo operator guide](DEMO_OPERATOR_GUIDE.md) for lifecycle commands.
> Its LM Studio CLI examples are historical only; production LM Studio is external and the
> current lifecycle never invokes `lms` or reclaims its port.

最後更新日期：2026-06-12

## 文件目的與分工

本手冊是第一年度 Demo 的完整 E2E 操作文件，目標是讓操作者能從零或從當機狀態重新建立整套服務，並能在任一段出問題時定位原因。正式 Demo 當天的短版流程請看 `docs/operations/first_year_demo_runbook.md`；三個 Demo 情境的台詞、展示重點與備援 artifact 請看 `docs/project/first_year_demo_scenario_script.md`。

本手冊分成五個層次：

1. 一鍵建立或重啟所有服務：Demo day 優先使用。
2. 暖啟動：保留既有 LM Studio 與 MQTT broker，只啟動 canonical Demo services。
3. 正式錄影：同時收錄 `scrcpy` 與 ADB `screenrecord` 的做法與 debug。
4. 分服務手動啟動：當一鍵腳本失敗或需要局部重啟時使用。
5. Debug 決策表：依照 topic、port、log 與 health endpoint 快速定位。

所有 TemiAgent 操作預設在 container 內執行，避免 host/container owner 與權限漂移。

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
export PC_IP='<pc-ip>'
export TEMI_IP='<temi-ip>'
```

## 端到端主線

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

2026-06-01 起，`tools/temi_overview_adapter.py` 只負責 ASR 與 camera，不轉發 command。Temi Android app 直接執行 canonical `temi/temi-01/cmd/request`，因此 canonical 主線中不應再看到 adapter 發 `temi/action/speak`。

## 固定環境

| 項目 | 值 |
|---|---|
| PC IP | `$PC_IP` |
| Temi IP | `$TEMI_IP` |
| MQTT broker | `$PC_IP:1883` |
| Picture Streaming WebSocket | `$PC_IP:8080` |
| Hermes resident health | `http://127.0.0.1:8765/health` |
| Hermes resident invoke | `http://127.0.0.1:8765/invoke` |
| Action viewer health | `http://127.0.0.1:8010/health` |
| Action viewer UI | `http://127.0.0.1:8010/` |
| Temi app package | `com.robotemi.agent` |
| Shared image/event root | `/TemiAgent/temi_shared` |
| Demo memory root | `/TemiAgent/memory` |
| Demo recording root | `/TemiAgent/logs/demo_recordings` |

重要限制：Overview / Hermes 主線要讓 adapter 佔用 `8080` 接收 Picture Streaming。不要同時執行 `./tools/start_temi_pc_services.sh` 與 adapter，否則 legacy backend 和 adapter 會搶同一個 WebSocket port。

如果 LM Studio 與 broker 已由其他受控流程啟動，而且操作者必須保留它們，請使用 [Demo 暖啟動操作手冊](demo_warm_start_runbook.md)。暖啟動會啟動 adapter、resident Hermes、Bridge、Discord gateway 與 action viewer，但不接管既有 `1234` 或 `1883` listener，也不執行 mock ASR／TTS 驗證。

## 第一部分：一鍵建立或重啟所有服務

一鍵腳本是正式 Demo 前的優先路徑。它會停止舊的 Bridge、Hermes resident、Overview adapter、MQTT broker、Hermes Discord gateway、action viewer，重新啟動 LM Studio、MQTT、adapter、resident Hermes、HermesTemiBridge、Hermes Discord gateway、action viewer，並依設定執行硬體檢查、unit tests、local E2E、demo cases 與 live E2E。

所有 log 會寫到：

```text
/TemiAgent/logs/e2e_stack_validation_<timestamp>/
```

### 1. 目前正式 Demo 建議：三卡非 QAT Gemma 4 31B

使用者目前指定正式 Demo 先用三卡、非 QAT 版本。Demo 前完整重啟與驗證使用這條：

```bash
cd /TemiAgent
MODEL_LOAD_ID=google/gemma-4-31b \
MODEL_IDENTIFIER=google/gemma-4-31b \
CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1 \
./tools/validate_temi_e2e_stack.sh
```

成功時最後應看到：

```text
[PASS] TemiAgent E2E stack validation completed. Logs: /TemiAgent/logs/e2e_stack_validation_<timestamp>
```

最低限度要確認：

```bash
lms ps
curl -sS http://127.0.0.1:1234/v1/models
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8010/health
/TemiAgent/hermes-agent/venv/bin/hermes gateway status
python3 -m json.tool /root/.hermes/gateway_state.json | grep -A8 '"discord"'
adb devices -l
ss -ltnp | grep -E ':(1234|1883|8080|8765|8010)'
```

預期模型狀態：

```text
google/gemma-4-31b
context 64000
LMSTUDIO_VISIBLE_GPUS=0,1
```

### 2. 現場救急快速重啟

Demo 已開始或時間有限時，用這條快速關閉舊服務並重啟 stack，跳過耗時測試：

```bash
cd /TemiAgent
MODEL_LOAD_ID=google/gemma-4-31b \
MODEL_IDENTIFIER=google/gemma-4-31b \
CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1 \
RUN_UNIT_TESTS=0 \
RUN_LOCAL_E2E=0 \
RUN_DEMO_CASES=0 \
RUN_LIVE_E2E=0 \
./tools/validate_temi_e2e_stack.sh
```

快速重啟後至少做一個 mock ASR 或真機語音測試，並確認 Temi 有 `cmd/result`。

### 3. 單卡 QAT 備案

若三卡非 QAT 載入失敗、VRAM 不穩，或現場需要回到先前備案，可切單卡 QAT：

```bash
cd /TemiAgent
MODEL_LOAD_ID=temi/gemma-4-31b-it-qat \
MODEL_IDENTIFIER=google/gemma-4-31b \
CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1 \
./tools/validate_temi_e2e_stack.sh
```

注意：Hermes config 的 provider default 仍應是 `google/gemma-4-31b`，不要把 QAT load id 直接寫成 Hermes model default，否則 provider/model identifier 可能不一致。

### 4. 一鍵腳本會啟動哪些服務

| 服務 | 目的 | 主要 log |
|---|---|---|
| LM Studio headless | 載入 Gemma 4 31B，提供 OpenAI-compatible API | `lmstudio*.log`、`lms ps` |
| MQTT broker | Temi、adapter、Bridge 的 event bus | `mosquitto*.log` |
| Overview adapter | legacy ASR/camera -> canonical ASR event | `overview_adapter.log` |
| Hermes resident | 常駐 Hermes HTTP worker | `hermes_resident.log` |
| HermesTemiBridge | 驗證 Hermes JSON output 並 dispatch command | `bridge.log` |
| Hermes Discord gateway | 讓 Hermes 在 Discord 在線上，處理 gateway skill | `hermes_gateway.log`、`gateway_state.json` |
| Action viewer | Demo UI / camera-action viewer；abnormal event 預設 180 秒全域 cooldown，避免跌倒後連續呼叫 Hermes | `action_viewer.log` |

若不需要 Discord，可加 `START_GATEWAY=0` 跳過 gateway；正式 Demo 建議保留 `START_GATEWAY=1`，避免 Discord 看不到 Hermes 在線上。

### 5. 一鍵腳本常見成功訊號

```text
LM Studio model loaded: google/gemma-4-31b
Hermes resident health ok
Hermes gateway is ready: Discord connected
Action viewer health ok
Bridge published command request
Temi command result received
```

如果腳本顯示沒有 Temi established connection，但 MQTT live E2E 或手動 TTS 成功，通常只是當下 TCP session 沒被偵測到。Demo 前仍建議重開 Temi App：

```bash
adb connect $TEMI_IP:5555
adb shell am start -n com.robotemi.agent/.MainActivity
```

## 第二部分：正式 Demo 錄影

正式錄影有兩條路：

1. `scrcpy`：優先嘗試，能 headless 錄影，沒有 Android `screenrecord` 常見的 180 秒單段限制；Temi Android 6.0.1 上通常只有畫面，不保證音訊。
2. ADB `screenrecord`：備援；Temi 原生解析度可能觸發 encoder failure，建議指定低解析度並加 `--bugreport` 做現場保底。

錄影和 Demo 服務本身沒有直接搶同一個 encoder。Demo PC 的 LM Studio、MQTT、Bridge、Hermes 不會使用 Android 螢幕錄影 encoder。若突然出現 encoder failed、0 frames、ADB offline，多半是 Temi Android 端的 ADB/adbd、Wi-Fi、Surface/H.264 encoder 狀態不穩，而不是 Demo 服務本身卡住。

### 1. 錄影前固定檢查

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
adb connect $TEMI_IP:5555
adb devices -l
scrcpy --version
```

通過條件：

```text
$TEMI_IP:5555 device product:rk3288 model:rk3288 device:rk3288
scrcpy 1.25
```

若 `adb devices -l` 看到多台 device，scrcpy 和 adb 指令都要指定 serial：

```bash
scrcpy --serial $TEMI_IP:5555 ...
adb -s $TEMI_IP:5555 ...
```

### 2. scrcpy headless 錄影

正式錄影建議用絕對路徑，避免相對路徑不存在造成 `Failed to open output file`：

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
scrcpy --serial $TEMI_IP:5555 \
  --no-display \
  --no-control \
  --max-size 1280 \
  --bit-rate 2M \
  --record "/TemiAgent/logs/demo_recordings/temi-demo-$(date +%Y%m%d_%H%M%S).mp4"
```

停止錄影：按 `Ctrl+C`。正常結束會看到：

```text
Recording complete to mp4 file: ...
```

錄完立即確認檔案大小：

```bash
ls -lh /TemiAgent/logs/demo_recordings/temi-demo-*.mp4
```

判讀：

- 幾 MB 以上：通常有實際畫面。
- 只有數百 byte 或小於 10 KB：多半只有 MP4 header，沒有 frame；不要當正式錄影，改用 ADB fallback 或外部錄影。
- `ERROR: Failed to open output file`：輸出目錄不存在或路徑不是 container 內可寫路徑；先 `mkdir -p /TemiAgent/logs/demo_recordings`，並使用絕對路徑。
- `adb: error: more than one device/emulator`：指令未指定 `--serial`，或 adb server 還保留其他 device；加 `--serial $TEMI_IP:5555`。
- `adb reverse failed, fallback to adb forward`：Temi Android 6.0.1 上可先視為 warning；只要後續有錄到 frame 即可。

8 秒短測：

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
timeout 8s scrcpy --serial $TEMI_IP:5555 \
  --no-display \
  --no-control \
  --max-size 1280 \
  --bit-rate 2M \
  --record "/TemiAgent/logs/demo_recordings/temi-scrcpy-test-$(date +%Y%m%d_%H%M%S).mp4"
ls -lh /TemiAgent/logs/demo_recordings/temi-scrcpy-test-*.mp4
```

`timeout` 回傳 124 是預期，只要 MP4 有實際大小即可。

### 3. ADB screenrecord fallback

Temi 原生直向解析度可能太高，曾出現 `Unable to get output buffers (err=-38)`、`encoder failed`、0 byte 檔案。不要直接使用未指定解析度的 `adb shell screenrecord /sdcard/temi-demo.mp4`。

較穩的直向備援：

```bash
cd /TemiAgent
mkdir -p /TemiAgent/logs/demo_recordings
adb -s $TEMI_IP:5555 shell screenrecord --bugreport --size 720x1280 --bit-rate 2000000 /sdcard/temi-demo.mp4
# Ctrl+C 停止後：
adb -s $TEMI_IP:5555 pull /sdcard/temi-demo.mp4 "/TemiAgent/logs/demo_recordings/temi-demo-adb-$(date +%Y%m%d_%H%M%S).mp4"
ls -lh /TemiAgent/logs/demo_recordings/temi-demo-adb-*.mp4
```

`--bugreport` 會加上螢幕資訊 overlay，畫面比較不乾淨，但實測在畫面更新少時比較容易產生非零 frame，適合正式 Demo 保底。

### 4. 橫向 1280x720 的做法

可以要求 Android encoder 直接輸出橫向尺寸：

```bash
adb -s $TEMI_IP:5555 shell screenrecord --bugreport --size 1280x720 --bit-rate 2000000 /sdcard/temi-demo-landscape.mp4
adb -s $TEMI_IP:5555 pull /sdcard/temi-demo-landscape.mp4 "/TemiAgent/logs/demo_recordings/temi-demo-landscape-$(date +%Y%m%d_%H%M%S).mp4"
```

但 Temi 實際螢幕是直向介面時，`1280x720` 可能會縮放、裁切或旋轉不如預期。正式 Demo 最保守策略是：

1. 現場錄 `720x1280`，確保內容完整。
2. Demo 後再用剪輯軟體或 `ffmpeg` 轉成 1280x720。
3. 若一定要現場輸出 1280x720，先做 8 秒短測並確認畫面沒有裁切重要 UI。

後製旋轉範例：

```bash
ffmpeg -i input.mp4 -vf "transpose=1,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" output-1280x720.mp4
```

### 5. 錄影 debug 表

| 現象 | 原因 | 處理 |
|---|---|---|
| `encoder failed` | Temi Android H.264 encoder 狀態或解析度不支援 | 重啟 Temi / 重新開 wireless ADB，改 `--size 720x1280 --bit-rate 2000000 --bugreport` |
| 0 byte MP4 | screenrecord 沒成功拿到 output buffer | 降低解析度，加 `--bugreport`，或改 scrcpy / 外部錄影 |
| scrcpy MP4 只有數百 byte | scrcpy server 啟動但沒有拿到 frame | 不用該檔，改 ADB fallback；重新 `adb connect` 後短測 |
| `more than one device/emulator` | ADB server 有多台 device | 全部指令加 `-s $TEMI_IP:5555` 或 `--serial $TEMI_IP:5555` |
| `Device disconnected` | Wi-Fi ADB 中斷或 Temi adbd 重啟 | `adb connect $TEMI_IP:5555`，必要時在 Temi 重開 wireless debugging |
| 錄影沒音軌 | Temi Android 6.0.1 / 權限限制 | 以外部麥克風或螢幕錄製軟體收音；ADB screenrecord 預期沒有原始麥克風音軌 |

## 第三部分：分服務手動啟動

當一鍵腳本失敗、只想重啟單一服務，或需要在多個 terminal 觀察 log 時，使用本段。所有 terminal 都先進 container：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

### Terminal 0：環境與 port 檢查

```bash
cd /TemiAgent
./tools/check_temi_connection.sh
adb devices -l
ss -ltnp | grep -E ':(1234|1883|8080|8765|8010)'
```

判讀：`$TEMI_IP:5555 device` 代表 Temi ADB 可用；`1883` 是 MQTT；`8080` 是 adapter 或 legacy backend；`8765` 是 Bridge 使用的 Hermes resident HTTP service；`8010` 是 action viewer。

### Terminal 1：LM Studio headless

優先使用專案腳本：

```bash
cd /TemiAgent
LMSTUDIO_MODEL_ID=google/gemma-4-31b \
LMSTUDIO_CONTEXT_LENGTH=64000 \
LMSTUDIO_VISIBLE_GPUS=0,1 \
./tools/start_lmstudio_3gpu.sh
```

手動重啟序列：

```bash
cd /TemiAgent
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID=${LMSTUDIO_MODEL_ID:-google/gemma-4-31b}
export LMSTUDIO_CONTEXT_LENGTH=${LMSTUDIO_CONTEXT_LENGTH:-64000}
export LMSTUDIO_VISIBLE_GPUS=${LMSTUDIO_VISIBLE_GPUS:-0,1}
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
hash -r

lms unload --all
lms server stop
lms daemon down
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
lms server start --port 1234
lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max
lms ps
curl -sS http://127.0.0.1:1234/v1/models
```

Debug：`lms ps` 顯示 `google/gemma-4-31b:2` 時用 `lms unload --all` 後重載；Hermes health 顯示 context 4096 時，同步 LM Studio load context 與 `/root/.hermes/config.yaml` 的 `model.context_length`、`auxiliary.compression.context_length` 到 64000。

### Terminal 2：MQTT broker

```bash
cd /TemiAgent
if ss -ltn | grep -q ':1883 '; then
  echo 'MQTT port 1883 is already listening.'
else
  mosquitto -c /TemiAgent/mqtt/mosquitto.conf -d
fi
ss -ltnp | grep ':1883'
```

監看所有 topic：

```bash
mosquitto_sub -h $PC_IP -p 1883 -t '#' -v
```

### Terminal 3：Temi App 與 Android log

```bash
adb connect $TEMI_IP:5555
adb devices -l
adb shell am start -n com.robotemi.agent/.MainActivity
adb logcat '*:I' | grep -E 'MainActivity|WebSocketClient|MqttManager|CameraManager|AgentStateMachine|ACTION_SPEAK'
```

成功時常見 log：

```text
MqttManager: Connected successfully.
AgentStateMachine: Transitioned to: ASR_LISTENING
Video packets sent
MainActivity: ACTION_SPEAK: "..."
```

### Terminal 4：Overview adapter

```bash
cd /TemiAgent/temi_backend
uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker $PC_IP \
  --port 1883 \
  --vision-port 8080 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared \
  --conversation-id conv_first_year_demo
```

成功後，對 Temi 說話時 MQTT monitor 應看到 `temi/event/asr` 與 `temi/temi-01/asr/final`。若 `8080 address already in use`，停止 `temi_backend` legacy route 或其他占用者。

### Terminal 5：resident Hermes

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

健康檢查：

```bash
curl -sS http://127.0.0.1:8765/health
```

預期包含 `status: ok`、`model: google/gemma-4-31b`、`provider: custom`、`base_url: http://localhost:1234/v1`。

### Terminal 6：HermesTemiBridge HTTP mode

```bash
cd /TemiAgent/hermes_temi_bridge
MQTT_BROKER_HOST=$PC_IP \
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

成功時 MQTT monitor 應看到 `asr/final`、`cmd/request`、`cmd/result`。Bridge 拒絕 output 時，優先檢查 `actions`、`cognitive_state.home_esi_level`、`risk_reason`、robot action schema。

### Terminal 7：Hermes Discord gateway

```bash
cd /TemiAgent
HERMES_ACCEPT_HOOKS=1 /TemiAgent/hermes-agent/venv/bin/hermes gateway run
```

另開 terminal 確認：

```bash
/TemiAgent/hermes-agent/venv/bin/hermes gateway status
python3 -m json.tool /root/.hermes/gateway_state.json | grep -A8 '"discord"'
```

成功時應看到 `Gateway is running`，且 `discord.state = connected`。正式一鍵腳本已包含 gateway；手動啟動時不要忘記這個 terminal。

### Terminal 8：Action viewer

```bash
cd /TemiAgent/anomaly_detection
./restart_action_viewer_8010.sh
curl -sS http://127.0.0.1:8010/health
```

正式 Demo 預設會以 `ABNORMAL_COOLDOWN_SECONDS=180` 啟動；第一次 `falls down`、`lies on the floor` 或 `fights` abnormal event 發布後，3 分鐘內不再重複發布給 Bridge/Hermes。若要臨時改成 5 分鐘：

```bash
cd /TemiAgent/anomaly_detection
ABNORMAL_COOLDOWN_SECONDS=300 ./restart_action_viewer_8010.sh
```

若 UI 沒畫面，先確認 `8010` health、`action_viewer.log`、Temi logcat 是否有 `Video packets sent`。

### Terminal 9：正式錄影

錄影可和上述服務並行。正式 Demo 前先做 8 秒短測，確認 MP4 有實際 frame，再開始正式錄影。詳見本手冊第二部分。

## 第四部分：觸發與驗證

### 1. 真 Temi 語音

三個正式情境詳見 `docs/project/first_year_demo_scenario_script.md`。最短測試句：

```text
我吃完早餐後的藥了。
我有點不舒服，頭有點暈。
救命，我跌倒了，站不起來。
```

第一句只在提醒前置條件成立時才宣稱 completion：先在已確認 resident 的
private partition 建立一筆 isolated synthetic active reminder（早餐後服藥），並確認
production config 的 `CARE_CONTEXT_ENABLED=true`。Bridge 只接受 Hermes 回傳的 exact
`reminder_id`；沒有 active reminder、住民不符或多筆可能匹配時，應收到 clarification
speak/result，且 `reminders.json` 不得被修改。未 seed 就測第一句的結果是
`INVALID_ACCEPTANCE_PRECONDITION`，不是 Android 或 MQTT failure。
預期 topic 順序：

```text
temi/event/asr
temi/temi-01/asr/final
temi/temi-01/cmd/request
temi/temi-01/cmd/result
```

### 2. 手動 TTS 回路

```bash
cd /TemiAgent/temi_backend
uv run python scripts/manual_tts.py \
  --broker $PC_IP \
  --port 1883 \
  --text '這是 Temi MQTT 語音測試' \
  --language ZH_TW
```

### 3. 無硬體 deterministic artifacts

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
python3 tools/demo_case_runner.py --keep-artifacts
```

Artifact 位置：

```text
logs/demo_cases/<run>/run_summary.json
logs/demo_cases/<run>/cases/*/parsed_output.json
logs/demo_cases/<run>/cases/*/command_request.json
logs/demo_cases/<run>/cases/*/memory_state_after.json
logs/demo_cases/<run>/memory/event_log.jsonl
logs/demo_cases/<run>/memory/abnormal_events/*.json
logs/demo_cases/<run>/memory/summaries/*.md
```

## 第五部分：Debug 決策表

| 現象 | 先看哪裡 | 下一步 |
|---|---|---|
| Temi 沒有 ASR topic | `adb devices -l`、logcat、MQTT monitor | 重開 Temi App，確認 ASR_LISTENING |
| 只有 `temi/event/asr` | adapter log、8080、`temi_shared/events` | 確認 Picture Streaming 有 frames，adapter 沒被 port 擋住 |
| 有 `asr/final` 沒有 `cmd/request` | Bridge log、resident Hermes health | 檢查 Hermes invoke、JSON validation、timeout |
| 有 fallback 回應 | Bridge log 的 `fallback_reason` | 依 reason 查 JSON schema、Hermes timeout、image path |
| 有 `cmd/request` 沒 `cmd/result` | logcat、Temi MQTT connection | 確認 robot id、command schema、Temi app subscription |
| Temi 不說話 | logcat `ACTION_SPEAK`、manual TTS | 先跑 `manual_tts.py`，再查 Temi app TTS |
| Discord 沒看到 Hermes online | `hermes gateway status`、`gateway_state.json` | 重啟 gateway，確認 `discord.state=connected` |
| Hermes context 變 4096 | `/root/.hermes/config.yaml`、`lms ps` | 同步 LM Studio context 與 Hermes config 到 64000 |
| 模型名稱出現 `:2` | `lms ps` | `lms unload --all` 後重載 |
| action viewer 沒畫面 | `8010/health`、Temi video log | 重啟 viewer，確認 adapter/Temi camera stream |
| 錄影失敗 | `adb devices -l`、MP4 size、scrcpy output | 改用 ADB `--bugreport --size 720x1280` 或外部錄影 |

## Demo 成功驗收標準

一次完整端到端測試至少要能證明：

- Temi 語音進入 `temi/event/asr`。
- Adapter 產生 `temi/temi-01/asr/final`，並包含 `vision.frames` image paths。
- Bridge 成功呼叫 resident Hermes。
- Hermes output 通過 Bridge validation。
- Bridge 發布 `temi/temi-01/cmd/request`。
- Temi app 執行 command 並發布 `cmd/result`。
- Temi 實際說出回應。
- `memory/event_log.jsonl`、`memory/abnormal_events/`、`memory/summaries/` 或 validation logs 可追溯該次互動。
- 正式錄影檔已保存到 `/TemiAgent/logs/demo_recordings/`，且不是 0 byte 或只有 header 的小檔案。

## Legacy backend 備援路線

若 real Hermes 或 Overview 主線當天不穩，可以改走先前已驗證的 legacy backend + LM Studio/VLM route。這條路線仍可展示 Temi ASR、Picture Streaming、Local VLM 與 TTS 閉環，但不是本手冊主線。

```bash
cd /TemiAgent
./tools/start_temi_pc_services.sh
```

注意：使用此備援路線時，請不要同時啟動 `tools/temi_overview_adapter.py`，因為兩者都會使用 `8080`。

## Demo 現場建議

- Demo 前先跑一鍵腳本，不要臨場手動拼服務。
- 開一個 MQTT monitor 留在畫面旁邊，端到端問題通常能從 topic 順序定位。
- Real Hermes 第一次呼叫可能慢，正式展示前先用一句簡單語音預熱。
- 錄影先做 8 秒短測，確認檔案大小合理。
- 如果 real route 延遲過高，切換到 `tools/demo_case_runner.py` artifacts 展示照護記憶與 Home-ESI 結果。
- P4 Navigation 本輪先跳過，不納入端到端主線驗收。
