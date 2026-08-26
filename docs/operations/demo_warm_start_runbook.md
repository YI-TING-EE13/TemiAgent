# Demo 暖啟動與真機 Media 驗收手冊

最後更新日期：2026-07-29

狀態：Maintained Demo-only runbook。適用於 LM Studio 已載入模型且 MQTT broker 已可用的
AI6 Demo。這份手冊不重啟 LM Studio；健康且 endpoint 未變的 broker 也會保留。

Canonical lifecycle vocabulary and ownership remain in the
[current Demo operator guide](DEMO_OPERATOR_GUIDE.md). This is a supplemental
warm-start and real-Temi Media evidence procedure, not a second lifecycle authority.
[current Demo operator guide](DEMO_OPERATOR_GUIDE.md). This is a supplemental
warm-start and real-Temi Media evidence procedure, not a second lifecycle authority.

## 事前條件

在指定 container 中執行：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

準備 Git worktree 外的 private env，mode 必須是 `0600`，並設定一個 worktree 外、mode
`0700` 的 `TEMIAGENT_RUNTIME_ROOT`。該 env 必須把所有 writable runtime path 放在 root 內：

```text
TEMIAGENT_RUNTIME_ROOT=<external-runtime-root>
LOG_DIR=<external-runtime-root>/logs/bridge
MEMORY_DIR=<external-runtime-root>/data/care-memory
TEMI_SHARED_BRIDGE_PATH=<external-runtime-root>/data/shared
TEMI_SHARED_HERMES_PATH=<external-runtime-root>/data/shared
HERMES_MEDIA_CALLBACK_SOCKET=<external-runtime-root>/tmp/sockets/bridge_media_callback.sock
```

Media route 的三個 flags 必須是 `true`；tracked `.env.example` 的 defaults 維持 `false`。
Generic playback 可維持所有 care/visual flags `false`，因為它在 `unknown` resident 下也只可
播放 allowlisted `elderly_hand_exercise`。這不放寬 Mother dialysis-care 的 identity、症狀與
同意 gate。

### Optional controlled identity and repeated-discomfort route

Only for this bounded Demo, add these private values under the same external root:

```text
RESIDENT_IDENTITY_ENABLED=true
HERMES_DEMO_IDENTITY_TOOL_ENABLED=true
HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true
CARE_MEMORY_V2_ENABLED=true
DEMO_REPEATED_DISCOMFORT_ENABLED=true
DEMO_CARE_SCENARIO_PROMPT_ENABLED=true
DEMO_CARE_MEMORY_ROOT=<external-runtime-root>/data/care-memory
HERMES_DEMO_IDENTITY_CALLBACK_SOCKET=<external-runtime-root>/tmp/sockets/bridge_demo_identity_callback.sock
HERMES_DEMO_CARE_CALLBACK_SOCKET=<external-runtime-root>/tmp/sockets/bridge_demo_care_callback.sock
DEMO_IDENTITY_STATE_DIR=<external-runtime-root>/state/demo-identity
DEMO_IDENTITY_REFRESH_SECONDS=10
DEMO_IDENTITY_MAX_DURATION_SECONDS=900
```

The two callback paths are Unix sockets owned by Bridge, not MQTT credentials or Android paths.
The operator selection is process-scoped; it refreshes a canonical existing identity v1.0 result
every 10 seconds and expires to `unknown` after 900 seconds. Restart never restores an old
selection. No generic phrase, self-identification, name, or appearance selects a resident.

若本次需要 abnormal viewer，設定 `DEMO_ACTION_VIEWER_ENABLED=true` 與其必要 model paths。
除非當次人類明確授權自動 alert/notification，以下三個 private values 必須是 `disabled`：

```text
DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH=disabled
DEMO_ACTION_VIEWER_DISCORD_NOTIFY=disabled
DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK=disabled
```

## Lifecycle

先執行 read-only doctor：

```bash
./scripts/demo --config <private-demo-env> doctor
```

doctor 檢查 branch、HEAD、dirty files（允許三個既有 memory runtime files）、nested Hermes、
private env mode、external runtime root、entrypoints、broker listener/transport、LM Studio、port
conflict、effective flags、socket parent、runtime path 權限及 fresh Android MQTT activity。它不建立
directory、停止 process 或發布 MQTT。

首次在沒有既有 Demo process 的情況下啟動：

```bash
./scripts/demo --config <private-demo-env> start
```

將既有的本 Demo adapter/resident/Bridge/viewer 切換到 current HEAD 時，只使用：

```bash
./scripts/demo --config <private-demo-env> restart
```

restart 先在 external runtime root 保存 process、health、flags、socket、port 與 source evidence。
它只對以 exact PID start identity、cwd、executable、command line 及 listener 確認的 service
送 `TERM`，順序是 Bridge、resident、adapter、viewer；之後依 Adapter、resident、Bridge、
viewer 啟動。它不使用 `pkill`、`killall` 或 raw MQTT，並保留 LM Studio 和 reviewed external
broker。每個新 service 的 stdout/stderr、PID ownership、last-run、socket 與 trace 都在 external
runtime root。

每次確認 readiness：

```bash
./scripts/demo --config <private-demo-env> status
```

`status` 回報 source branch/commit、runtime root、private env path（不輸出 credentials）、PID
identity、effective flags、Resident health/media toolset、fast path、Bridge callback socket、broker
session、robot id、latest trace 與 log paths。`BACKEND_READY_WAITING_ANDROID` 表示 backend 已就緒
但尚未觀察到 fresh remote Android MQTT session；只有 remote session evidence 才能顯示
`DEMO_READY`。這兩者都不能取代 Android command result。

## 真實 Temi Media E2E

使用 private env 載入 host、port 與 robot id，開啟 ASR、cmd/request、cmd/result observer：

```bash
set -a
. <private-demo-env>
set +a
robot_id="${ROBOT_ID_ALLOWLIST%%,*}"

mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" -t "temi/$robot_id/asr/final" -v
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" -t "temi/$robot_id/cmd/request" -v
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" -t "temi/$robot_id/cmd/result" -v
```

在另一個 terminal 檢視 current Bridge trace：

```bash
python3 /TemiAgent/tools/show_temi_trace.py --log-dir "$LOG_DIR" --latest --full
```

對 Temi 依序說：

```text
小安小安，請幫我播放手部運動影片。
小安小安，請暫停影片。
小安小安，請繼續播放影片。
小安小安，請停止影片。
```

play 必須顯示 canonical `video.command` v1.1 request，並至少有
`action=play_video` 與 `video_id=elderly_hand_exercise`。確認鏈條是：fresh ASR → Resident
`deterministic_media_fast_path` → native Media tool → Unix callback accepted → Bridge validation →
cmd/request → Android `accepted` → Android `started`/`playing` → 實際畫面。記錄 Android playback
session ID。pause、resume、stop 分別確認 `paused`、`playing`、control `succeeded`，以及 original
play session 的 `cancelled`/`remote_stop` linkage。

缺少任何一段時，依最後成功 stage 分類：`ASR_NOT_RECEIVED`、`FAST_PATH_NOT_MATCHED`、
`NATIVE_TOOL_NOT_LOADED`、`MEDIA_CALLBACK_SOCKET_MISSING`、`MEDIA_CALLBACK_REJECTED`、
`BRIDGE_MEDIA_DISABLED`、`CMD_REQUEST_NOT_PUBLISHED`、`ANDROID_NO_ACCEPTED_RESULT`、
`ANDROID_ACCEPTED_NOT_STARTED`、`ANDROID_PLAYER_MAPPING_FAILURE` 或
`PAUSE_RESUME_STOP_FAILURE`。保留 timestamp、command ID、session ID、trace 和最後成功 stage；
不得以 raw publish 偽造結果。

若 observer 顯示 legacy ASR 將「手部運動」轉寫成「首都運動」或「守護運動」，current fast
path 對這三個已審查表面詞和固定播放句型建立有限組合，並且仍固定 dispatch 到
`elderly_hand_exercise`。它也接受已驗收的縮寫「播放影片」。任何其他錯轉寫（例如「背部運動」）
不匹配，會保留一般 LLM route；不要以泛用讀音／fuzzy matching 或 raw MQTT 擴張 allowlist。

## Controlled identity and repeated-discomfort E2E

After `restart` returns ready, use the Bridge callback rather than raw MQTT to establish the Demo
context, then seed the synthetic private partitions:

```bash
./scripts/demo --config <private-demo-env> identity father
./scripts/demo --config <private-demo-env> identity status
./scripts/demo --config <private-demo-env> seed repeated-discomfort
./scripts/demo --config <private-demo-env> verify repeated-discomfort
```

Observe the existing identity result topic in addition to ASR and command topics:

```bash
set -a
. <private-demo-env>
set +a
robot_id="${ROBOT_ID_ALLOWLIST%%,*}"
mosquitto_sub -h "$MQTT_BROKER_HOST" -p "$MQTT_BROKER_PORT" \
  -t "temi/$robot_id/resident/identity/result" -v
```

Optional voice verification of the same root-owned skill (after a start or restart) accepts only
the exact commands `Demo切換為爸爸` / `Demo設定為爸爸`, corresponding mother forms, the two clear
forms, and the two status forms. `我是爸爸` must not change identity. For the father sequence, say:

```text
小安小安，我又不舒服了。
對。
血壓128/78。
```

Evidence must show: ASR → `deterministic_repeated_discomfort_fast_path` → native callback →
father-only synthetic prior event retrieval → confirmation → `StructuredMemoryStore` append.
The final acknowledgement is valid only when callback status is `recorded`; it records a
user-provided number and is not a clinical assessment. A mother or unknown context must not reach
that callback or read any father data.

## Evidence、停止與回復

匯出 owner-only evidence bundle：

```bash
./scripts/demo --config <private-demo-env> trace-export
```

bundle 包含 branch/commit、recorded processes、flags（不含 credentials）、Bridge/Resident/adapter/
viewer logs、Bridge traces、最近 ASR metadata、checksums 與 archive SHA-256；不複製影像 binaries。

正常停止：

```bash
./scripts/demo --config <private-demo-env> stop
```

stop 是 idempotent，只停止 lifecycle current ownership record；不停止 LM Studio、external Broker
或 Android App。若 restart/start health gate 失敗，lifecycle 只 rollback 本次剛啟動的 exact PID。
它只會在 recorded Bridge 的 exact PID 已全數停止且 callback path 是 Unix socket 時清除自己的
stale callback socket；任何 unknown 或 non-socket path 都會保留並 fail closed。若 identity、
socket 或 port 無法安全確認，停止擴大操作並依
[安全服務操作](safe_service_operations.md) 保留 evidence 後調查。

Demo 錄製後才處理完整 runtime/canonical worktree decoupling，包括正式 Broker ownership、
Android runtime exporter、runtime retention/cleanup、historical worktree cleanup，以及將 external
runtime policy 提煉成長期 release procedure。這些工作不是本次快速 Media 驗收的前置條件。
