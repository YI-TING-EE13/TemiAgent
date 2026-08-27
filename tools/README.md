# Tools 模組 README

最後更新日期：2026-07-31

## 本文件維護規則

這份 README 是 `tools/` 的快速入口。只要新增腳本、改 CLI 參數、改啟動順序或改測試責任，都要同步更新本文件。

## 模組定位

`tools/` 收納跨模組開發、測試與 Demo 操作用腳本。這些腳本不是核心服務本體，但負責把 MQTT、Bridge、Temi backend、shared volume、resident Hermes 串起來。

## 腳本索引

| Script | 用途 |
|---|---|
| `hermes_resident_server.py` | 啟動低延遲 resident Hermes HTTP worker，供 Bridge `HERMES_INVOKE_MODE=http` 使用。 |
| `hermes_media_fast_path.py` | Resident-only pure exact matcher；只在 private Demo flag 開啟時將受控中文 Media phrase 送入既有 native tool。 |
| `hermes_demo_identity_fast_path.py` / `hermes_resident_identity_tools.py` | Demo-only exact operator identity matcher and root native tool; local Unix callback only. |
| `hermes_repeated_discomfort_fast_path.py` / `hermes_resident_repeated_discomfort_tools.py` | Father-only exact three-step synthetic-memory matcher and root native tool; local Unix callback only. |
| `demo_lifecycle.py` / `scripts/demo` | Canonical Demo lifecycle; explicit managed/external ownership, exact-PID records, health gates, status and trace export. |
| `verify_newcomer_mock.py` / `scripts/verify_newcomer_mock` | Verifies the already-running isolated newcomer profile through canonical Bridge events, callback media, command results and local test doubles; it does not start or own services. |
| `temi_overview_adapter.py` | ASR/camera-only adapter：接 legacy `temi/event/asr` 與 WebSocket camera frames，產生 canonical `temi/{robot_id}/asr/final` 與三張 keyframe path；不轉發 command。 |
| `e2e_test_runner.py` | 不需硬體的本地 mock E2E smoke test。 |
| `media_v11_fake_e2e.py` | 以 in-memory MQTT 與 fake Android 驗證 media v1.1 lifecycle、stop linkage、replay 與 trace。 |
| `demo_case_runner.py` | 跑第一年度 Demo 三個固定照護案例並輸出 artifacts。 |
| `create_mock_event_images.py` | 產生 ASR event 測試用三張 mock images。 |
| `publish_mock_asr_event.sh` | 發送 canonical mock ASR event。 |
| `subscribe_cmd_request.sh` | 訂閱 canonical command request，方便觀察 Bridge output。 |
| `publish_mock_cmd_result.sh` | 發送 mock command result。 |
| `inject_demo_event.py` / `scripts/inject_demo_event` | 以 owner-only config 建立 synthetic evidence 並發布 canonical Demo abnormal event；不發 command、result 或 Discord webhook。 |
| `dispatch_hermes_action_output.py` | 將 Hermes skill action JSON 驗證、包成 `temi/{robot_id}/cmd/request`，並可 publish 到 MQTT，供 Discord/manual TTS 執行使用。 |
| `capture_temi_live_snapshot.py` | 從 `8081` decoded JPEG broadcast 按需擷取目前畫面，存到 `temi_shared/live_snapshots/`，輸出 Hermes/Skills 可分析的 frame path JSON。 |
| `start_temi_pc_services.sh` | 啟動 PC 端 Temi legacy services。 |
| `start_temi_pc_services_background.sh` | 背景啟動 PC 端 services。 |
| `check_temi_connection.sh` | 檢查 Temi ADB、MQTT、WebSocket 等連線狀態。 |
| `validate_documentation.py` | 唯讀檢查 tracked Markdown links、fences 與 reader-schema copies；不啟動服務。 |

## 常用流程

### 本地 mock E2E

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

Media v1.1 isolated fake Android E2E：

```bash
cd /TemiAgent
python3 tools/media_v11_fake_e2e.py
```

此腳本將 `MEDIA_V11_ENABLED` 只套用在 process 內的 test service，並使用 temporary
directory。腳本不啟動 MQTT broker、Hermes、Android 或 robot，也不保留 trace artifact。

### Canonical Demo lifecycle

`scripts/demo` 是 current branch 的唯一 lifecycle。預設 private env 是 Git-ignore、mode
`0600` 的 `/TemiAgent/.runtime/demo/demo.env`，由 `init-config` 建立；只有這個 exact
worktree-local path 可作為預設。`TEMIAGENT_RUNTIME_ROOT`、Bridge `LOG_DIR`、memory、shared
ASR artifact、PID、socket、logs 和 trace 都必須在該 owner-only root。每項服務使用 `managed`、`external` 或
`disabled` ownership；managed profile 可管理 LM Studio、MQTT、adapter、resident、Bridge、
gateway 和 viewer，而 external service 只會 health-check。stop 僅接受 recorded exact PID
identity，並以 viewer → gateway → Bridge → resident → adapter → MQTT → LM Studio 順序執行。

After each verified managed spawn, the lifecycle immediately persists an
owner-only `STARTING` record with exact process identity, command fingerprint,
and timestamp before waiting on the next health gate. A completed run becomes
`HEALTHY`. A failed health gate first records `UNHEALTHY`, then rolls back only
the recorded services in reverse order and persists `START_FAILED` when that
rollback succeeds. A rollback failure remains `UNHEALTHY`. `status` exposes
the recorded lifecycle state. If `stop` finds a managed-like process that is
not in the ownership state, it returns `STOP_INCOMPLETE_OWNERSHIP` and exits
non-zero without signalling any PID. Preserve the state and inspect the exact
PID evidence; do not delete the state file or use a broad kill.

```bash
cd /TemiAgent
./scripts/demo init-config
./scripts/demo doctor
./scripts/demo start
./scripts/demo restart
./scripts/demo status
./scripts/demo trace-export
./scripts/demo stop
```

For a broker-only lifecycle transition, use the dedicated MQTT command group:

```bash
cd /TemiAgent
./scripts/demo mqtt start
./scripts/demo mqtt status
./scripts/demo mqtt stop
```

These commands resolve the canonical private configuration from the primary
`/TemiAgent` worktree and use its owner-only runtime root at
`/TemiAgent/.runtime/demo`. They manage or inspect only the configured MQTT
broker on port `1883`; they do not start, stop or restart LM Studio, Hermes,
Bridge, resident, viewer, gateway, adapter or Android. `mqtt status` is
read-only. `mqtt start` refuses any existing listener unless it is the exact
managed broker startup, and `mqtt stop` signals only the recorded exact owner.

Managed Mosquitto runs under a lifecycle supervisor. The supervisor launches
the resolved absolute broker executable with the canonical config, then
publishes an owner-only child contract containing the supervisor PID, child
PID, direct PPID, process start ticks, exact command line, executable path,
executable SHA-256 and command-line SHA-256. Readiness revalidates that
contract, the configured listener address and port, and a local TCP probe.
Mosquitto may drop privileges, so `ss -p` may expose no listener PID; missing
PID metadata alone is not treated as unowned when the child contract is live.
A visible contradictory listener PID, a wrong bind or port, a failed TCP probe,
or an executable/path/digest mismatch fails closed. A foreign broker is never
adopted or killed by name.

When the private Demo flags explicitly enable identity and repeated discomfort, these commands
remain inside the same Bridge callback / memory boundary and do not raw-publish MQTT:

```bash
./scripts/demo --config <private-demo-env> identity father
./scripts/demo --config <private-demo-env> identity mother
./scripts/demo --config <private-demo-env> identity unknown
./scripts/demo --config <private-demo-env> identity status
./scripts/demo --config <private-demo-env> seed repeated-discomfort
./scripts/demo --config <private-demo-env> verify repeated-discomfort
```

`restart` 只在 current user-authorized transition 中採用已由 cwd、command line、start identity
及 listener 驗證的 existing Demo process；它不使用 broad kill。詳細的 private config、Android
evidence、Media phrase 和故障定位在 `docs/operations/demo_warm_start_runbook.md`。

### Software-only newcomer profile

The tracked `config/demo.mock.env.example` is the isolated acceptance profile
used by the default initializer. Materialize the canonical ignored config,
start it through `scripts/demo`, and then run the verifier without a path:

```bash
./scripts/demo init-config
./scripts/verify_newcomer_mock
```

The verifier is not a mock orchestrator. It drives the existing Bridge with
canonical events and checks the command/result and media callback contracts;
the lifecycle retains service specs, locks, health checks, exact-PID records,
restart and stop. See the [verification guide](../docs/operations/verification_and_acceptance.md#software-only-newcomer-acceptance)
for the complete fresh-clone sequence and external-acceptance limits.

### Demo case runner

```bash
cd /TemiAgent
python3 tools/demo_case_runner.py --keep-artifacts
```

輸出包含三個 case 的 input event、Hermes raw output、parsed output、command request/result、memory snapshot 與 run summary。若指定 `--output-dir logs/demo_cases/<name>`，artifact 會保留在該目錄。

### Active live camera snapshot

當 Hermes/Discord 需要「現在看一下」但當回合沒有 ASR 對齊影像時，可按需擷取目前 decoded camera frame：

```bash
cd /TemiAgent
python3 tools/capture_temi_live_snapshot.py \
  --source-url ws://127.0.0.1:8081 \
  --robot-id temi-01 \
  --pretty
```

輸出會包含 `source_type: live.snapshot`、`request_id`、`frames[].path` 與 `metadata_path`。圖片會存到 `temi_shared/live_snapshots/{robot_id}/{request_id}/`。這個工具只做低頻 snapshot，不取代 ASR 三張 frame route，也不應用於 continuous abnormal detection。

### Manual Hermes action dispatch

當 Hermes 在 Discord/CLI 只產生 action JSON，而沒有經過 ASR -> Bridge invocation 時，可用 dispatcher 把 JSON 送進 Temi command path：

```bash
cd /TemiAgent
python3 tools/dispatch_hermes_action_output.py --publish --json '{"schema_version":"1.0","event_id":"manual_greet_20260601","robot_id":"temi-01","confidence":1.0,"reasoning_summary":"Manual TTS greeting.","actions":[{"action_id":"act_001","type":"speak","text":"嗨 King！","language":"zh-TW"}]}'
```

這個工具會重用 Bridge validator 與 command builder；舊的 manual TTS JSON 若缺 `cognitive_state`，會補 `Normal` 預設值。

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

在 private Demo env 同時設 `MEDIA_V11_ENABLED=true`、`HERMES_MEDIA_TOOL_ENABLED=true`、
`HERMES_MEDIA_FAST_PATH_ENABLED=true` 與絕對 Unix callback socket 後，Resident 會在 LLM 前只
匹配受控手部運動播放／暫停／繼續／停止字句。這條路仍是 native tool → local Unix socket →
Bridge，不得改為 raw MQTT 或 Bridge 外部 fallback；完整啟動與真機觀察步驟見
`docs/operations/demo_warm_start_runbook.md`。

2026-07-29 真機 ASR 曾將「手部運動」轉寫為「首都運動」或「守護運動」，也曾縮成
「播放影片」。`hermes_media_fast_path.py` 對三個已審查表面詞、四個固定播放句型建立有限
組合，仍固定到 `elderly_hand_exercise`；它不做泛用讀音／模糊比對、語意改寫或任意影片搜尋。
例如「背部運動」不會命中 hand-exercise allowlist。

`RESIDENT_IDENTITY_ENABLED=true`、`HERMES_DEMO_IDENTITY_TOOL_ENABLED=true` 與 `HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED=true` 會載入 repo-root 的 `hermes-skills/temi-demo-identity/SKILL.md`，接受受控的完整示範管理句型；它不從「我是爸爸」、姓名或自然談話推論 identity。`CARE_MEMORY_V2_ENABLED=true` 與 `DEMO_REPEATED_DISCOMFORT_ENABLED=true` 會再載入
`temi-demo-repeated-discomfort`，但只有 Bridge 確認 active resident 是 father 時，才將「我又
不舒服了」→「對」→「血壓128/78」送往 canonical memory callback。兩者都不讓 resident publish
MQTT 或直接讀寫 memory files。

### Legacy ASR/camera to canonical contract

```bash
cd /TemiAgent/temi_backend
export PC_IP='<pc-ip>'
uv run python /TemiAgent/tools/temi_overview_adapter.py \
  --broker $PC_IP \
  --port 1883 \
  --vision-port 8080 \
  --shared-root /TemiAgent/temi_shared \
  --bridge-root /TemiAgent/temi_shared
```

## 維護注意

- `temi_overview_adapter.py` 只負責 ASR 與 camera；不要在 adapter 重新加入 `cmd/request` -> `temi/action/speak` 轉發，否則新版 Temi app 會重複說話。
- 腳本應保持可從 `/TemiAgent` 絕對路徑執行，方便 runbook 複製。
- 修改 topic、schema 或 path mapping 時，必須同步更新 `hermes_temi_bridge/README.md` 與 `docs/operations/` runbooks。
- Demo 用 IP、機器人狀態與臨時結果應放 runbook，不要硬編到 reusable scripts。

## Non-responsibilities

- `tools/` 不擁有照護 domain policy、runtime schema 或 Android hardware behavior。
- Adapter 不 dispatch canonical command。
- Manual dispatcher 不取代完整 Bridge service route；只可用於已驗證 JSON 的人工／Demo 操作。
- Test runner 產生的 logs、images、memory snapshots 與 JSONL 都是 runtime artifacts。

## Configuration and Failure Behavior

Reusable scripts 應以 CLI 或 environment 接收 broker、port、shared root、model endpoint
與 robot ID。不要加入 private IP、secret 或 user-specific host path 作新預設值。
External dependency failure 必須產生 non-zero status 或明確 error artifact；不得把
best-effort publish、Discord delivery 或缺少 command result 報為成功。

## Verification

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

Documentation-only changes first run:

```bash
cd /TemiAgent
python3 tools/validate_documentation.py
```

其他 script 應使用 `--help`、相鄰 unit test 或對應 runbook 的 bounded smoke procedure。
需要 MQTT、model、GPU、Android 或 Discord 的檢查在依賴不可用時標記 `SKIPPED`，
不能用 static inspection 取代。

## Contract and Change Checklist

修改 script CLI、topic、port、path、health endpoint、artifact layout 或 service order
時，同步更新 owning module code/tests、此 README、
[contract traceability](../docs/architecture/contract_traceability.md) 與跨模組 runbook。
