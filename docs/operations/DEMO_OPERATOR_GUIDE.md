# TemiAgent Demo 操作入口

最後更新日期：2026-07-31

狀態：Demo-only。`scripts/demo` 是目前 checkout 的唯一 lifecycle。private env 為每個
service 明確宣告 `managed`、`external` 或 `disabled` ownership；`managed` 服務會由同一
lifecycle 啟動、記錄 exact PID identity、health-check 與停止，`external` 服務只 health-check
且永不由 lifecycle 停止。正式 software-only profile 可管理 LM Studio、Mosquitto、Overview
adapter、resident Hermes、Bridge、Hermes gateway 與 viewer；Android 預設 external。

所有操作必須在指定 container 的 `/TemiAgent` 執行：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

## Current documentation boundary

This is the formal current operator workflow. Use the
[configuration reference](demo_configuration_reference.md) to prepare the
private env, [troubleshooting guide](demo_troubleshooting.md) for a symptom and
evidence path, and [verification and acceptance guide](verification_and_acceptance.md)
to classify a result. `DEMO_QUICK_REFERENCE.md` is a compact companion;
`demo_operations_runbook.md`, dated project handovers, and temporary-content
inventories are reference material, not substitute lifecycle contracts.

## 唯一操作指令

Canonical config is the ignored, owner-only `/TemiAgent/.runtime/demo/demo.env`;
`./scripts/demo init-config` creates it and the paired runtime root without a
credential. It defaults to the safe `newcomer_mock` profile. Use an explicit
absolute `--config` only for a separately owned custom deployment.

```bash
./scripts/bootstrap --sources
```

```bash
./scripts/demo init-config
./scripts/demo doctor
./scripts/demo start
./scripts/demo restart
./scripts/demo status
./scripts/demo stop
./scripts/demo trace-export
```

相容 alias `up`、`down` 與 `deploy --backend-only` 存在，但操作文件只使用上述六個指令。
`doctor` 與 `status` 不啟停 service，也不發布 MQTT。`restart` 只會採用已記錄、或在此明確
restart 中以 cwd、command line、PID start identity 與 listener 驗證過的既有 Demo process。

## Private runtime layout

The default config fixes `TEMIAGENT_RUNTIME_ROOT` at the ignored owner-only
`/TemiAgent/.runtime/demo` root. Explicit custom config roots remain outside
every Git worktree. Lifecycle writes only below the selected root:

```text
<runtime-root>/
  config/                 private config copy or reference parent
  state/{pid,ownership,last-run,android-evidence,viewer,notifications,media}/
  data/{care-memory,test-memory,shared}/
  logs/{bridge,hermes,asr,trace}/
  tmp/sockets/
```

`LOG_DIR`、`MEMORY_DIR`、`TEMI_SHARED_BRIDGE_PATH`、`TEMI_SHARED_HERMES_PATH` 和
`HERMES_MEDIA_CALLBACK_SOCKET` 都必須在該 root 之下。adapter 產生的 ASR keyframe 與
metadata 會寫到 private `data/shared`；lifecycle 不寫入 repository 的 `temi_shared/`、`logs/`
或 `memory/`。

受控 Media Demo 的 effective flags 必須都是 `true`：

```text
MEDIA_V11_ENABLED=true
HERMES_MEDIA_TOOL_ENABLED=true
HERMES_MEDIA_FAST_PATH_ENABLED=true
```

generic hand-exercise 仍可保持：

```text
DEMO_CARE_SCENARIO_PROMPT_ENABLED=false
DEMO_RESIDENT_VISUAL_ROUTING_ENABLED=false
CARE_CONTEXT_ENABLED=false
```

這條 generic route 可在 `resident_id=unknown` 下執行，固定只允許
`elderly_hand_exercise`，且不讀寫 Care Memory。Mother dialysis-care playback 是另一條
workflow：它仍需要 confirmed `mother`、已記錄 dialysis-return、無不適與本人明確同意。

## Controlled identity 與 repeated-discomfort Demo

以下是額外的、預設關閉的 Demo 路線；它不替代 visual identity，也不是 face recognition。
private env 必須把所有新增 path 放在同一 external runtime root，並只在要驗收本功能時設為：

```text
RESIDENT_IDENTITY_ENABLED=true
HERMES_DEMO_IDENTITY_TOOL_ENABLED=true
HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true
CARE_MEMORY_V2_ENABLED=true
DEMO_REPEATED_DISCOMFORT_ENABLED=true
DEMO_CARE_SCENARIO_PROMPT_ENABLED=true
DEMO_CARE_MEMORY_ROOT=<runtime-root>/data/care-memory
HERMES_DEMO_IDENTITY_CALLBACK_SOCKET=<runtime-root>/tmp/sockets/bridge_demo_identity_callback.sock
HERMES_DEMO_CARE_CALLBACK_SOCKET=<runtime-root>/tmp/sockets/bridge_demo_care_callback.sock
DEMO_IDENTITY_STATE_DIR=<runtime-root>/state/demo-identity
DEMO_IDENTITY_REFRESH_SECONDS=10
DEMO_IDENTITY_MAX_DURATION_SECONDS=900
```

先經 lifecycle 的同一個 Bridge callback 選擇身分，不要手刻 MQTT identity payload：

```bash
./scripts/demo --config <private-demo-env> identity father
./scripts/demo --config <private-demo-env> identity status
./scripts/demo --config <private-demo-env> seed repeated-discomfort
./scripts/demo --config <private-demo-env> verify repeated-discomfort
```

語音 operator 指令只接受以下精確句型（可有開頭 `小安小安` 與標點）：`進入示範管理模式，持續發布王先生身分`、`示範模式切換到王先生`、`Demo 管理，持續發布王先生身分`、對應的王太太三句、`停止示範身分發布`、`示範模式切換為未知住民`、`Demo 管理，清除目前身分`、`目前示範身分是誰`，以及 `Demo 管理，查詢目前身分發布狀態`。短句 `Demo切換為爸爸` 等同樣是受審查的 operator fallback。`我是爸爸`、名字或一般談話絕不選擇身分。Bridge 以現有 identity v1.0 schema 驗證後才發布 `temi/{robot_id}/resident/identity/result`，QoS 1、`retain=false`；selection 每 10 秒 refresh、最多 900 秒，而且 restart 不會恢復前一個 selection。

father 已選定並 seed 完成後，依序對 Temi 說：

1. `小安小安，我又不舒服了。`
2. 等它問「這次也是頭痛嗎？」後說：`對。`
3. 等它要求血壓後說：`血壓128/78。`

這條路只讀 father partition 的固定 synthetic headache event；確認後才接受血壓格式並經
canonical memory API append 一筆新的 father event。它不讀 mother 或 unknown partition，且只
記錄使用者提供的數字，不作醫療判斷。

## Readiness

成功的 backend restart 會顯示 `BACKEND_READY_WAITING_ANDROID`；只有 lifecycle 在 broker
觀察到 fresh remote Android MQTT session，才會顯示 `DEMO_READY`。兩種狀態都不代表影片已
播放。真機播放必須有 `cmd/result` 的 Android `accepted`／`started` 或 `playing`，再加上
畫面觀察。

Resident health 的必要欄位是：

```text
media_tool_names: play_video, pause_video, resume_video, stop_video
media_fast_path_enabled: true
```

fast path 是 deterministic phrase dispatch，在 LLM inference 前呼叫既有 native Media tool；
它不是 LLM tool selection。Resident 不 publish MQTT；Bridge 仍是唯一 command publisher。

## 真機操作與觀察

先在三個只讀 terminal 開 observer。host、port 和 robot id 必須從 verified private env 載入，
不要將其實值寫回文件：

```bash
set -a
. <private-demo-env>
set +a
robot_id="${ROBOT_ID_ALLOWLIST%%,*}"

mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" \
  -t "temi/$robot_id/asr/final" -v
```

```bash
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" \
  -t "temi/$robot_id/cmd/request" -v
```

```bash
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" \
  -t "temi/$robot_id/cmd/result" -v
```

若驗收 identity，另開 observer：

```bash
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" \
  -t "temi/$robot_id/resident/identity/result" -v
```

另開一個 terminal：

```bash
./scripts/demo --config <private-demo-env> status
python3 /TemiAgent/tools/show_temi_trace.py --log-dir "$LOG_DIR" --latest --full
```

依序對 Temi 說下列語句，且每一步都等待 Android lifecycle result 再繼續：

1. `小安小安，請幫我播放手部運動影片。`
2. `小安小安，請暫停影片。`
3. `小安小安，請繼續播放影片。`
4. `小安小安，請停止影片。`

播放的 `cmd/request` 必須是 Media v1.1：`schema_version="1.1"`、
`message_type="video.command"`、`action="play_video"`、
`video_id="elderly_hand_exercise"`。實際播放必須依序確認：ASR、
`deterministic_media_fast_path` trace、native callback accepted、Bridge validation、
request published、Android accepted、Android started/playing、螢幕播放。pause 應得到
`paused`；resume 應得到 `playing`；stop control 應 `succeeded` 並使原 play session
`cancelled`／`remote_stop`。不要用 `mosquitto_pub` 手刻 request 或 result 取代語音驗收。

## Viewer 與安全停止

設定 `DEMO_ACTION_VIEWER_ENABLED=true` 才會管理 viewer。lifecycle 只將
`DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH` 與 legacy
`DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK` 傳入 viewer；
`DEMO_ACTION_VIEWER_DISCORD_NOTIFY=enabled` 會被 lifecycle 拒絕。即使 legacy
`PRE_ALERT_SPEAK` 被設為 enabled，viewer 也只記錄
`ABNORMAL_PRE_ALERT_BRIDGE_OWNED`，不會直接發送 command。Bridge 是異常
notification 與 care TTS 的唯一 owner。

異常 notification 的操作入口是
[immediate abnormal-care flow](immediate_abnormal_care_flow.md)。operator 先以
`scripts/demo doctor` 確認私有設定，再以 `scripts/inject_demo_event` 發布唯一允許的
synthetic abnormal event。viewer `/health` 的
`abnormal_publish_enabled=true` 只代表 event publication 已啟用；
`notification_bridge_owned=true` 表示 viewer 不讀取 webhook、也不送出 Discord。不要執行
viewer `--discord-delivery-test`，它會明確拒絕，且不會測試任何 delivery route。

正常停止順序為 viewer → gateway → Bridge → resident → adapter → MQTT → LM Studio。每一項
只接受 lifecycle state 裡同時匹配 PID、start time、cwd、executable 與 command digest 的
record；stale 或不明 PID 會 fail closed，不會以 name-based kill 處理。

結束 Demo 的唯一停止指令是：

```bash
./scripts/demo --config <private-demo-env> stop
```

若 `doctor` 報 unknown listener、stale socket 或 PID identity mismatch，不要刪除 state、
不要 broad kill；保留 evidence，依 [安全服務操作](safe_service_operations.md) 處理。lifecycle
只有在 recorded Bridge 的全部 exact PID 已停止、且 callback path 確實是 Unix socket 時才會刪除
自己的 stale socket；unknown 或非-socket path 仍會 fail closed。使用
`trace-export` 會在 external runtime root 建立 owner-only bundle、SHA-256 manifest 與 archive。

`MANAGE_ANDROID=0` 是目前 canonical profile 的預設。只有 Android owner 提供正式 App
lifecycle contract 與明確授權後，才可把 Android 納入 managed profile；一般 `start` 不會啟動
錄影、TTS、測試 alert 或任何 abnormal event。Discord gateway 可以連線，但本 lifecycle 不會
發布 Discord 測試或照護通知。
