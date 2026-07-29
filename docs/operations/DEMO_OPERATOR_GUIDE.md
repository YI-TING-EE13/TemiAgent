# TemiAgent Demo 操作入口

最後更新日期：2026-07-29

狀態：Demo-only。`scripts/demo` 是目前 checkout 的唯一 backend lifecycle。它只管理
Overview adapter、resident Hermes、HermesTemiBridge，以及 private env 明確啟用的 action
viewer；它不停止 LM Studio、既有健康的 MQTT broker、Android App 或 Hermes gateway。

所有操作必須在指定 container 的 `/TemiAgent` 執行：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

## 唯一操作指令

`<private-demo-env>` 必須是 Git worktree 外、owner-only（mode `0600`）的 private env。它不
能是 `hermes_temi_bridge/.env.example` 或其他 tracked env。

```bash
./scripts/demo --config <private-demo-env> doctor
./scripts/demo --config <private-demo-env> start
./scripts/demo --config <private-demo-env> restart
./scripts/demo --config <private-demo-env> status
./scripts/demo --config <private-demo-env> stop
./scripts/demo --config <private-demo-env> trace-export
```

相容 alias `up`、`down` 與 `deploy --backend-only` 存在，但操作文件只使用上述六個指令。
`doctor` 與 `status` 不啟停 service，也不發布 MQTT。`restart` 只會採用已記錄、或在此明確
restart 中以 cwd、command line、PID start identity 與 listener 驗證過的既有 Demo process。

## Private runtime layout

private env 必須設定 `TEMIAGENT_RUNTIME_ROOT` 到 Git worktree 外的 owner-only directory。
Lifecycle 只在這個 root 寫入：

```text
<runtime-root>/
  config/                 private config copy or reference parent
  state/{pid,ownership,last-run,android-evidence}/
  data/{care-memory,shared}/
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

設定 `DEMO_ACTION_VIEWER_ENABLED=true` 才會管理 viewer。lifecycle 將 viewer 的
`DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH`、`DEMO_ACTION_VIEWER_DISCORD_NOTIFY` 與
`DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK` 從 private env 傳入；沒有明確人類授權時三者必須是
`disabled`。這避免 action-viewer 的已知 Demo-only direct pre-alert gap 繞過 Bridge。

結束 Demo 的唯一停止指令是：

```bash
./scripts/demo --config <private-demo-env> stop
```

若 `doctor` 報 unknown listener、stale socket 或 PID identity mismatch，不要刪除 state、
不要 broad kill；保留 evidence，依 [安全服務操作](safe_service_operations.md) 處理。使用
`trace-export` 會在 external runtime root 建立 owner-only bundle、SHA-256 manifest 與 archive。
