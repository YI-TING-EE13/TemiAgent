# TemiAgent Demo 操作入口

最後更新日期：2026-08-29

狀態：CURRENT；Demo-only。`scripts/demo` 是目前 checkout 唯一的 canonical lifecycle。private env 為每個
service 明確宣告 `managed`、`external` 或 `disabled` ownership；`managed` 服務會由同一
lifecycle 啟動、記錄 exact PID identity、health-check 與停止，`external` 服務只 health-check
且永不由 lifecycle 停止。Production LM Studio is required but externally
managed; only the `newcomer_mock` profile manages a local LM test double.
The production lifecycle can manage Mosquitto, Overview adapter, resident
Hermes, Bridge, Hermes gateway and viewer; Android 預設 external。

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

For new maintainers, use the [developer setup](developer_setup.md) first and
the [deployment handover](demo_deployment_handover.md) for the host/service
matrix. The [configuration reference](demo_configuration_reference.md) is the
single key and secret inventory. This guide owns lifecycle actions;
documentation evidence does not by itself authorize a future live transition.
Any service operation remains separately authorized and must follow the
exact-PID safety policy.

## Current canonical lifecycle

Canonical config is the ignored, owner-only `/TemiAgent/.runtime/demo/demo.env`;
`./scripts/demo init-config` creates it and the paired runtime root without a
credential. It defaults to the safe `newcomer_mock` profile. Use an explicit
absolute `--config` only for a separately owned custom deployment.

From a clean source checkout, initialize the formal Hermes submodule, then
reconstruct the reviewed external source pins. These commands do not install
dependencies or start a service:

```bash
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --sources
```

After the documented Hermes and module environments exist, check those pins and
runtime prerequisites:

```bash
./scripts/bootstrap --check
```

Create or select the private configuration:

```bash
./scripts/demo init-config
./scripts/demo init-config --profile production --force
```

The five primary full-stack lifecycle operations are:

```bash
./scripts/demo doctor
./scripts/demo start
./scripts/demo status
./scripts/demo restart
./scripts/demo stop
```

For a broker-only transition, use the separate MQTT command group:

```bash
./scripts/demo mqtt start
./scripts/demo mqtt status
./scripts/demo mqtt stop
```

The parser also exposes the following supported setup, compatibility and
feature selectors. They are not a second operator sequence:

| Selector | Purpose and boundary |
|---|---|
| <code>init-config [--force] [--profile newcomer_mock\|production]</code> | Setup of the ignored private config; <code>--force</code> can replace that private file and is not a routine check. |
| <code>doctor</code> | Read-only source, config, artifact, port, ownership and health diagnostics. |
| <code>start</code>, <code>restart</code>, <code>stop [--dry-run]</code> | Full lifecycle transitions; only exact recorded/validated identities may be operated. |
| <code>status</code> | Read-only lifecycle summary. |
| <code>mqtt {start|status|stop}</code> | The only service-specific lifecycle selector; MQTT-only start/stop is not a full-stack transition and there is no <code>mqtt restart</code>. |
| <code>trace-export</code> | Writes a bounded owner-only evidence bundle; it is not a service transition. |
| <code>up</code>, <code>down</code> | Compatibility aliases for full start/stop retained by the parser; use the five primary names in new procedures. |
| <code>deploy [--backend-only]</code> | Specialized compatibility/deployment helper; use only with a separately reviewed deployment plan. |
| <code>identity {father|mother|unknown|status}</code> | Controlled Demo identity callback helper; it can change private Demo state and is not visual identity. |
| <code>seed repeated-discomfort</code>, <code>verify repeated-discomfort</code> | Synthetic private care fixture helper and read-only verification; Demo-only and not a live care claim. |

The exact grammar is implemented by <code>tools/demo_lifecycle.py</code>.
Global <code>--config</code> and <code>--json</code> options appear before the
selector, for example
<code>./scripts/demo --config &lt;private-demo-env&gt; --json doctor</code>.

### Production LM Studio ownership

Production configuration must set `LMSTUDIO_OWNERSHIP=external`. The LM
provider and its model/cache/GPU setup belong to the external runtime owner.
Before `scripts/demo start`, `doctor` or the explicit preflight must show one
configured LM API listener and a ready HTTP model-list response containing the
configured `LMSTUDIO_API_IDENTIFIER` (normally `google/gemma-4-31b`). The
lifecycle never invokes `lms`, starts a real LM process, loads or unloads a
model, or stops/reconfigures a provider. It fails closed when the endpoint is
absent, malformed, duplicated or not model-compatible.

The production stop path does not stop LM Studio. A legacy LM record is
preserved and produces `STOP_INCOMPLETE_OWNERSHIP`; an external provider that
was already running remains running. Direct `lms ls`, `lms ps`, `lms unload
--all`, `lms server stop`, and `lms daemon down` commands are not read-only
audits and must not be used as routine recovery. The retained LM helper names
are compatibility guards that fail closed. The local `newcomer_mock` profile
is the only profile allowed to manage the tracked mock LM server.

The MQTT-only commands use the primary worktree's canonical private config and
`/TemiAgent/.runtime/demo` owner-only runtime root. They operate only the
managed Mosquitto broker on `1883`; they never dispatch the full Demo lifecycle
or touch LM Studio, Hermes, Bridge, resident, viewer, gateway, adapter or
Android. `mqtt status` is read-only. Start refuses a listener that cannot be
proven to be the exact managed child, and stop signals only the recorded exact
supervisor/child lineage.

The managed supervisor launches the resolved absolute Mosquitto executable
with the canonical broker config and records an owner-only child contract:
supervisor PID, child PID, direct PPID, process start ticks, exact command
line, executable path, executable SHA-256 and command-line SHA-256. The
readiness gate also requires the configured listener address/port and a
successful local TCP probe. Mosquitto can drop privileges, so `ss -p` may have
no listener PID; missing PID metadata is acceptable only with a live matching
child contract. A visible contradictory PID, executable/path/digest mismatch,
wrong bind or port, or failed TCP probe is a failure, and a foreign broker is
never adopted or killed by name.

### Gate 5 host acceptance snapshot

Gate 5B Retry #4 is the current bounded host-runtime evidence. It passed
L0–L3 and L5, reused the existing MQTT broker without restart, and preserved
external LM Studio. Production LM is <code>EXTERNAL_ONLY</code>; the accepted
API identifier is <code>google/gemma-4-31b</code>, the provisioned model is
<code>temi/gemma-4-31b-it-qat</code>, and runtime context <code>64000</code>
was verified from runtime metadata. Hermes reconstruction is the pinned base
plus patches <code>0001</code>–<code>0010</code>, producing tree
<code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>.

The accepted request budget is <code>L1=0; L2=0; L3=0; L5=1</code>. L2 is
an inference-impossible malformed resident request returning HTTP 400 before
invocation. L3 is a Bridge callback to a validated identity-result topic with
no physical side effect. L5 returned HTTP 200 with one validated
<code>speak</code> action; resident health remained healthy and no compression,
response-boundary or unexpected-runtime failure occurred. Rollback removed
all Gate-owned processes/listeners and preserved LM/MQTT. This is
<code>HOST_LIVE_VERIFIED</code> for the exact host contract only. The exact
canonical Android/Temi TTS boundary is separately
<code>L4_ANDROID_TEMI_E2E=CLOSED_PASS</code> from the adopted L4.7B evidence;
viewer/GPU general behavior, video/media playback, camera/microphone, broader
Android behavior and other physical actions remain separate.
<code>READY_FOR_GATE6=YES</code> means Gate 6 is release/handover-only.

### L4.3 Android artifact provenance snapshot

LAB606 accepted the external Android final artifact as
<code>ANDROID_PROVENANCE=CLOSED_PASS</code>. The accepted package is
<code>com.robotemi.agent</code>, version <code>1.0.2 (3)</code>, at
<code>temi-agent-android-public/app/build/outputs/apk/demo/app-demo.apk</code>,
with SHA-256
<code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>.
The external source is revision
<code>3e2fc0376e5b5ca3992e697fc030cdc08173c639</code>, based on accepted
baseline <code>8c458888657efca5384c6d51e5ec57e8b385d987</code>. The installed
package, signer, embedded revision and whole APK matched exactly
(<code>EXACT_APK_MATCH</code>); the existing install was accepted as-is.

The observed target <code>&lt;observed-private-deployment-address&gt;:5555</code> is classified
<code>OBSERVED_AI6_DEPLOYMENT</code> and is evidence only, never a portable
default. This snapshot does not authorize ADB, installation, replacement,
reinstall, data reset, Android/Temi operation, MQTT, service operation or
inference. The exact canonical TTS physical boundary is now closed by the
adopted L4.7B evidence; video/media playback, camera/microphone and broader
device behavior remain outside that acceptance. Use the
[verification guide](verification_and_acceptance.md) for the authoritative
criteria and remaining boundary.

`doctor` 與 `status` 不啟停 service，也不發布 MQTT。`restart` 只會採用已記錄、或在此明確
restart 中以 cwd、command line、PID start identity 與 listener 驗證過的既有 Demo process。
`init-config` is setup, and `trace-export` is an evidence-export helper; neither is a lifecycle
state transition. The parser retains older compatibility names for historical evidence, but they
do not belong in a current operator procedure.

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

## L4 final physical acceptance snapshot

The final L4 disposition is <code>L4_FINAL=CLOSED_PASS</code> and
<code>L4_ANDROID_TEMI_E2E=CLOSED_PASS</code>. The adopted
<code>L4.7B_POST_REBOOT_SINGLE_CANONICAL_TTS</code> evidence records one
explicit speak dispatch, one terminal <code>COMPLETED</code> TTS callback and
one successful correlated AI6 result using the accepted Android 1.0.2 (3)
artifact. Android ingress, validation and executor execution passed; model
requests, movement, navigation, notification, duplicate execution and
retained command were zero/none. Rollback passed, with LM, MQTT, Android state
and canonical source preserved. No additional physical L4 run is required.

The same evidence classifies the earlier timeout as
<code>VENDOR_RUNTIME_TRANSIENT_STATE_REGRESSION</code>: a strongly evidenced
transient vendor runtime state failure, with the exact internal component
unproven. The device uses SDK <code>1.134.1</code> with observed launcher
<code>16405-usa / 16405</code>, below the documented minimum
<code>18024</code>. This is an unsupported/below-minimum deployment
limitation, not the proven direct cause, and does not require an update for
the current handover.

After successful completion, the Android log also emitted
<code>Canonical TTS resolved without an active speech action</code>. Because
there was no second dispatch, terminalization or result, classify it as
<code>SECONDARY_TTS_DIAGNOSTIC_WARNING=NON_BLOCKING_KNOWN_ISSUE</code>, possibly
a <code>STATE_MACHINE_DIAGNOSTIC_DEFECT</code>. Do not treat it as the timeout
root cause or remediate it in this gate.

## Status, logs and common failures

`status` is the read-only lifecycle summary. It reports readiness, ownership, listeners,
callback sockets, latest trace and the private log paths; it is not a service log viewer.
Use the trace viewer for a bounded, de-identified timeline:

```bash
./scripts/demo --config <private-demo-env> --json status
python3 tools/show_temi_trace.py --log-dir <bridge-log-dir> --latest --json
python3 tools/show_temi_trace.py --log-dir <bridge-log-dir> --latest --full
```

Do not copy raw logs, images, full prompts, credentials or production care data into the
repository. Keep `DEBUG_TRACE_FULL=false` for normal Demo operation.

| Result or failure code | First safe check |
|---|---|
| `BACKEND_NOT_READY` | Run `doctor`, inspect the first required `FAIL` or unavailable managed endpoint, then preserve the evidence. |
| `BACKEND_READY_WAITING_ANDROID` | Check the fresh Android MQTT session and `cmd/result`; backend health is not device playback evidence. |
| `CONFIG_INVALID` | Check private env mode `0600`, runtime-root containment and the accepted profile values. |
| `PORT_IN_USE_EXTERNAL` or `BROKER_START_FAILED` | Inspect the exact listener and configured ownership; do not adopt or kill by name. |
| `SERVICE_HEALTH_FAILED` or `MODEL_LOAD_FAILED` | Read the named service health response and its private log path; do not relabel a missing model as ready. |
| `PID_IDENTITY_MISMATCH` or `STOP_INCOMPLETE_OWNERSHIP` | Preserve state, verify PID/cwd/executable/command line, and follow [safe service operations](safe_service_operations.md). |
| `STOP_TIMEOUT` | Recheck the same verified PID and protected listeners; do not use `pkill` or `killall`. |

### Canonical TTS timeout recovery boundary

If an authorized canonical TTS attempt times out while Android MQTT remains
connected, the speak dispatch is confirmed and no terminal callback arrives:

1. Do not immediately reinstall TemiAgent.
2. Do not immediately increase the timeout.
3. Inspect the vendor launcher health and ANR evidence.
4. If an operational owner authorizes it, use one normal bounded Temi reboot.
5. Verify package, accepted APK identity and Android data preservation.
6. Perform one bounded TTS probe and record the callback/result evidence.

Repeated reboot loops are not an accepted recovery strategy. The L4.7B
evidence classifies the prior incident as a transient vendor runtime state
failure; the below-minimum launcher is a documented limitation, not a proven
direct cause. The post-success
<code>Canonical TTS resolved without an active speech action</code> message is
a non-blocking known diagnostic issue, not a callback-timeout explanation.

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

正常停止順序為 viewer → gateway → Bridge → resident → adapter → MQTT。Production LM Studio
is external and is intentionally absent from this sequence. 每一項
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
