# Temi + Hermes Agent 整合專案總覽文件

> 文件狀態：CURRENT architecture narrative，最後治理審查日期為 2026-08-29。
>
> 本文件包含初期驗證計畫、里程碑與 Coding Agent 任務。第 7–13 節是歷史規劃與
> 驗收設計，不代表所有項目目前均已實作或驗證。現況能力以根目錄 `README.md`、
> 各模組 README、runtime code、tests 與實際驗證紀錄為準。

## Authoritative Sources

- Cross-module contract authority、producer、consumer、tests 與同步規則：
  [contract_traceability.md](contract_traceability.md)
- Runtime JSON schemas：`hermes_temi_bridge/schemas/`
- Reader schema copies：`docs/schemas/`
- Cross-module operations：[docs/operations/](../operations/)
- Demo/research scope：[docs/project/](../project/)

Architecture narrative 不得取代 runtime validator、schema 或 owning module config。
若本文與 executable source 不一致，先保留 runtime 行為並把差異列入治理修正。

## Canonical V1 boundary

The canonical flow is:

```text
Temi Android ASR/camera
  -> tools/temi_overview_adapter.py
  -> canonical ASR/perception events plus allowlisted paths
  -> HermesTemiBridge validation
  -> resident Hermes JSON-only reasoning
  -> HermesTemiBridge action validation and command request
  -> Temi Android executor
  -> command result and Bridge trace
```

`hermes_temi_bridge/` is the safety and dispatch boundary. It validates robot IDs,
schemas, shared paths, Hermes JSON output and actions before publishing a canonical
command request. Hermes returns JSON-only plans and never publishes MQTT or controls
hardware. The optional anomaly viewer produces perception events only; it is not a
general hardware dispatcher. Temi Android is an external consumer. The current Gate 5
host evidence classifies the exact reused MQTT and one external-model/resident/Bridge
host path as `HOST_LIVE_VERIFIED`; Android/Temi execution, general model/GPU/viewer
behavior and live perception remain `LIVE_NOT_VERIFIED`.

Canonical V1 includes the root scripts/tools, Bridge, legacy backend compatibility
route, canonical configuration and schemas, MQTT configuration, reviewable skills,
source manifests/patches, and documentation. The `hermes-agent/` formal submodule
is pinned to the team remote; bootstrap applies the root-owned Temi patch series
in its worktree. The generated `anomaly_detection/third_party/llama.cpp/` checkout
remains an ignored external dependency reconstructed from its manifest. Neither
dependency is root source or vendored source. `memory/` contains only reviewed synthetic fixtures;
runtime state, real care data, images, logs and checkpoints are not publication data.

## Experimental / non-canonical local inference

`local_inference/` and `sub2/` may be physically present in a development mount, but
they are excluded from canonical V1 and are not required by `./scripts/demo`.
`local_inference/` is an opt-in DeepSeek/llama.cpp service on loopback `1235`;
`sub2/` is an isolated emotion-recognition experiment. Neither owns the canonical
MQTT topic, Bridge validation or Temi hardware route. The optional `yolo26x-pose.pt`
weight is an external model asset with expected path/hash metadata only; source,
version, license and redistribution restrictions require maintainer confirmation.

## Current reading order

Read the root [`README.md`](../../README.md),
[`CURRENT_STATUS.md`](../CURRENT_STATUS.md), [`REPOSITORY_MAP.md`](../REPOSITORY_MAP.md),
[contract traceability](contract_traceability.md), and the owning module README
before operating or changing the system. The current Demo lifecycle, private
configuration and incident boundaries are in
[`docs/operations/`](../operations/), especially the
[Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md). Sections 6–13
below are retained architecture, planning and validation history. They explain
how the design evolved, but their commands, deployment examples and milestones
are not the current operator contract.

## Current Demo lifecycle ownership

`tools/demo_lifecycle.py` owns Demo service orchestration, while each service
retains its own health endpoint and runtime behavior. The lifecycle uses one
owner-only state record and exact process identity; it does not infer ownership
from a port or process name. After a verified managed spawn, it atomically
persists `STARTING` with start identity and command fingerprint before waiting
for health. When no `--config` is supplied, it resolves only the ignored
owner-only `/TemiAgent/.runtime/demo/demo.env` and its paired runtime root;
`init-config` creates that layout and never discovers a legacy temporary config.
The final successful state is `HEALTHY`.

On a health-gate failure, the lifecycle records `UNHEALTHY`, stops only the
recorded services in reverse start order, records rollback outcomes, and leaves
`START_FAILED` if every recorded stop succeeds. A failed rollback remains
`UNHEALTHY` for recovery. `status` reports the lifecycle state. If no ownership
state exists for a managed-like process, `stop` returns
`STOP_INCOMPLETE_OWNERSHIP` and sends no signal. This lifecycle state is an
operations contract, not a Bridge, MQTT, Android, model, or hardware-control
contract.

## Current abnormal-care route

The current abnormal route is `perception.abnormal -> Bridge -> Resident Hermes
-> Bridge validator -> canonical Temi command`. The Bridge validates the
authoritative abnormal-event schema and evidence paths, persists an episode,
reserves one immediate notification stage, invokes Resident Hermes, and then
publishes only a validator-approved command. The Temi Android App remains the
only hardware executor and publishes the matching command result.

The episode uses explicit states `DETECTED`, `INITIAL_ALERT_SENT`,
`AWAITING_FIRST_RESPONSE`, `RESIDENT_RESPONDED`, `FOLLOW_UP_REQUIRED`,
`NO_RESPONSE`, `ESCALATION_SENT`, `RESOLVED`, and `EXPIRED`. Notification-stage
dedup is persisted before external I/O, so a process restart does not replay a
delivery attempt. Viewer, injector, and Hermes never call a Discord webhook or
publish a robot command directly. See the executable operator boundary in
[immediate abnormal-care flow](../operations/immediate_abnormal_care_flow.md).

## 0. 文件目的

本文件整理目前已落地與仍待驗證的模組邊界；它不是對 live、醫療或完整照護能力的保證。

系統目標是讓 Temi robot 成為具備語音理解、視覺感知、Agent 推理與受驗證行動邊界的 embodied AI research/demo platform。

當使用者對 Temi 說話時，系統應能完成以下流程：

```text
使用者對 Temi 說話
  ↓
Temi Android App 取得 ASR final text
  ↓
Temi / Vision Backend 準備三張同步圖片
  ↓
透過 MQTT 發送 ASR event 與圖片 path
  ↓
HermesTemiBridge 接收事件
  ↓
HermesTemiBridge 呼叫 Hermes Agent
  ↓
Hermes Agent 使用 temi-robot-control Skill 推理
  ↓
Hermes Agent 輸出 JSON actions
  ↓
HermesTemiBridge 驗證 JSON actions
  ↓
HermesTemiBridge 透過 MQTT 發送 command 給 Temi
  ↓
Temi Android App 執行說話、轉向、導航、停止等動作
```

***

# 1. 系統總覽

## 1.1 核心設計理念

本專案採用 **分層解耦架構**。

每一層只負責自己的事情，不混雜其他層的邏輯。

```text
Temi Android App
  = 感測與硬體執行層

MQTT Broker
  = 事件與命令通訊層

Vision Server / Image Buffer
  = 視覺資料暫存與取樣層

HermesTemiBridge
  = 大腦輸入橋樑與命令轉發層

Hermes Agent
  = 推理與決策層

Agent Skill: temi-robot-control
  = Hermes 操作 Temi 的知識與規則層
```

這種架構的好處是：

1.  Temi Android 不需要知道 Hermes 的內部實作。
2.  Hermes 不需要直接控制 Temi robot。
3.  MQTT 只負責事件與命令，不傳大圖片。
4.  圖片以檔案 path / shared volume / URL 傳遞，方便 debug。
5.  Bridge 是唯一負責串接 Hermes 與 Temi 的地方。
6.  Skill 是 Hermes 的操作說明，不是長駐服務。
7.  後續若要換 VLM、換 Hermes invocation 方式、換 robot，都比較容易。

***

# 2. 系統模組與職責

## 2.1 Temi Android App

### 角色

Temi Android App 是 robot 端的主要程式。

它負責：

*   監聽使用者語音。
*   取得 ASR final text。
*   偵測 speech end timestamp。
*   接收或取得影像 frame。
*   發送 ASR event 到 MQTT。
*   訂閱 command topic。
*   執行 Hermes 回傳的動作。

### 主要輸出

Temi Android App 應 publish：

```text
temi/{robot_id}/asr/final
```

Payload 包含：

*   `event_id`
*   `robot_id`
*   `conversation_id`
*   `asr.text`
*   `speech_end_ts_ms`
*   三張圖片 path 或 image URI
*   language
*   interaction mode

### 主要輸入

Temi Android App 應 subscribe：

```text
temi/{robot_id}/cmd/request
```

收到 command 後執行：

*   `speak`
*   `ask_clarification`
*   `turn`
*   `navigate`
*   `stop`
*   `noop`

執行完後 publish：

```text
temi/{robot_id}/cmd/result
```

Identity 與 care report 是 contract-defined future integration。Bridge media v1.1 runtime
已由預設關閉的 feature gate 隔離並通過 fake Android 測試；現行 Android App 不得被描述為
已支援 media 或其他新 schema。LAB606 實作要求見
[Android cross-service contract](android_cross_service_contract.md)。

***

## 2.2 MQTT Broker

### 角色

MQTT Broker 是整個系統的事件匯流排。

建議使用 Mosquitto。

它負責：

*   接收 Temi 的 ASR event。
*   將 ASR event 轉送給 HermesTemiBridge。
*   接收 HermesTemiBridge 的 command。
*   將 command 轉送給 Temi。
*   接收 Temi 的 command result。

### 必要 topics

```text
temi/{robot_id}/asr/final
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
temi/{robot_id}/state
```

Contract-defined、runtime integration pending：

```text
temi/{robot_id}/resident/identity/result
temi/{robot_id}/care/report
temi/{robot_id}/care/report/interaction/result
```

Video command/result 沿用 `temi/{robot_id}/cmd/request` 與
`temi/{robot_id}/cmd/result`，使用 v1.1 discriminator；v1.0 command route 不變。
完整 contract 見 [canonical_cross_service_contract.md](canonical_cross_service_contract.md)。

### 可選 topics

```text
temi/{robot_id}/vision/frame_ready
temi/{robot_id}/agent/request
temi/{robot_id}/agent/response
temi/{robot_id}/debug
```

***

## 2.3 Vision Server / Image Provider

### 角色

Vision Server 或 Image Provider 負責提供三張與使用者語音結束時間同步的圖片。

建議取樣時間點：

```text
T - 1000ms
T - 500ms
T
```

其中 `T` 是：

```text
speech_end_ts_ms
```

### 圖片命名規則

建議使用：

```text
frame_t_minus_1000.jpg
frame_t_minus_500.jpg
frame_t.jpg
```

### 圖片存放位置

建議使用 shared volume：

```text
temi_shared/
└── events/
    └── {robot_id}/
        └── {event_id}/
            ├── frame_t_minus_1000.jpg
            ├── frame_t_minus_500.jpg
            ├── frame_t.jpg
            └── metadata.json
```

Bridge container 中看到：

```text
/var/lib/temi_shared/events/{robot_id}/{event_id}/frame_t.jpg
```

Hermes container 中看到：

```text
/shared/temi/events/{robot_id}/{event_id}/frame_t.jpg
```

***

## 2.4 HermesTemiBridge

**目錄位置**：`hermes_temi_bridge/`
**目前狀態**：已完成 hardware-free unit/mock E2E 驗證、resident Hermes wrapper 與 Bridge-validated Demo helper；目前 Gate snapshot 沒有 real Temi/Android live evidence。2026-06-01 起 Overview adapter 僅負責 ASR/camera，不再轉發 command；Temi app 直接執行 `temi/{robot_id}/cmd/request`，避免重複 TTS。

### 角色

HermesTemiBridge 是本專案整合的核心。

它不是 Hermes Skill，也不是 Temi Android App。

它是：

```text
事件接收器 + 圖片 path resolver + Hermes caller + JSON validator + command dispatcher
```

### 職責

HermesTemiBridge 負責：

1.  連接 MQTT broker。
2.  Subscribe `temi/+/asr/final`。
3.  驗證 ASR event payload。
4.  驗證三張圖片是否存在。
5.  將 Bridge path 轉成 Hermes path。
6.  建立 Hermes prompt。
7.  呼叫 Hermes Agent。
8.  取得 Hermes raw output。
9.  解析 JSON。
10. 驗證 action schema。
11. 發送 command 到 `temi/{robot_id}/cmd/request`。
12. 接收 `cmd/result`。
13. 記錄完整 log。
14. 錯誤時記錄可追蹤 log；robot-facing fallback 仍需通過 action schema。

### Bridge 不應該做的事

Bridge 不應該：

*   自己做高階推理。
*   自己判斷複雜使用者意圖。
*   直接控制 Temi SDK。
*   重新把 canonical command 轉成 legacy `temi/action/speak`。
*   把圖片 binary 塞進 MQTT。
*   直接相信 Hermes 的 output。
*   執行 Hermes 回傳的任意 shell command。

***

## 2.5 Hermes Agent

**目錄位置**：`hermes-agent/`
**目前狀態**：Resident wrapper、mock path 與 Bridge integration tests 已存在；Gate 5
已驗證 exact host resident/provider contract（<code>HOST_LIVE_VERIFIED</code>），
包括 external-only LM、runtime context <code>64000</code> 與一個 bounded request。
Android/Temi physical execution、general GPU/viewer behavior 與 portable provider
environment 仍不是此 evidence 的範圍。

### 角色

Hermes Agent 是大腦。

它負責：

*   讀取 Bridge 提供的 prompt。
*   理解 ASR text。
*   理解三張圖片。
*   根據 `temi-robot-control` Skill 做推理。
*   輸出結構化 JSON actions。

### Hermes 不直接做的事

Hermes 不應該：

*   直接 subscribe MQTT。
*   直接 publish MQTT。
*   直接控制 Temi hardware。
*   直接執行未驗證 command。
*   回傳自由格式文字給 Temi。

Hermes 應只輸出 JSON。

***

## 2.6 Agent Skill：`temi-robot-control`

### 角色

這是 Hermes 的操作知識文件。

它告訴 Hermes：

*   什麼時候使用 Temi robot control 能力。
*   如何理解 ASR + 三張圖片。
*   可以輸出哪些 action。
*   不可以輸出哪些 action。
*   不確定時如何詢問。
*   安全規則是什麼。
*   JSON output schema 是什麼。

### Skill 應放置於

```text
~/.hermes/skills/temi-robot-control/
```

建議結構：

```text
~/.hermes/skills/temi-robot-control/
├── SKILL.md
├── references/
│   ├── action_schema.json
│   ├── examples.md
│   ├── safety_rules.md
│   └── mqtt_topics.md
└── scripts/
    └── validate_temi_action.py
```

***

## 2.7 舊版測試環境：Temi Backend

**目錄位置**：`temi_backend/`
**目前狀態與用途**：LEGACY route。保留早期 Temi App 的 ASR、camera、VLM 與 MQTT 相容程式；目前只以 module tests 與歷史紀錄作為背景，不把歷史 live 結果當成目前驗收證據。

***

# 3. 系統通訊流程

## 3.1 正常端到端流程

```text
[1] User speaks
    ↓
[2] Temi Android ASR final
    ↓
[3] Temi prepares or references 3 images
    ↓
[4] Temi publishes MQTT ASR event
    topic: temi/{robot_id}/asr/final
    ↓
[5] HermesTemiBridge receives event
    ↓
[6] Bridge validates event and images
    ↓
[7] Bridge builds Hermes prompt
    ↓
[8] Bridge invokes Hermes Agent
    ↓
[9] Hermes uses temi-robot-control Skill
    ↓
[10] Hermes returns JSON actions
    ↓
[11] Bridge validates JSON actions
    ↓
[12] Bridge publishes command
    topic: temi/{robot_id}/cmd/request
    ↓
[13] Temi Android executes command
    ↓
[14] Temi publishes result
    topic: temi/{robot_id}/cmd/result
    ↓
[15] Bridge logs result
```

***

# 4. MQTT Topic 規格

## 4.1 ASR final topic

```text
temi/{robot_id}/asr/final
```

由 Temi publish。

Bridge subscribe：

```text
temi/+/asr/final
```

***

## 4.2 Command request topic

```text
temi/{robot_id}/cmd/request
```

由 Bridge publish。

Temi subscribe。

***

## 4.3 Command result topic

```text
temi/{robot_id}/cmd/result
```

由 Temi publish。

Bridge subscribe：

```text
temi/+/cmd/result
```

***

## 4.4 Robot state topic

```text
temi/{robot_id}/state
```

由 Temi publish。

可用於 debug 與 UI 顯示。

狀態可包含：

```text
idle
listening
thinking
speaking
navigating
executing
error
```

***

# 5. Payload 規格

## 5.1 ASR Final Event

Temi publish：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "conversation_id": "conv_20260511_a",
  "type": "asr.final",
  "timestamp_ms": 1778499000200,
  "speech_end_ts_ms": 1778499000123,
  "language": "zh-TW",
  "asr": {
    "text": "幫我看看桌上的東西是什麼",
    "confidence": 0.92
  },
  "vision": {
    "sampling_policy": "T-1000,T-500,T",
    "frames": [
      {
        "name": "t_minus_1000",
        "ts_ms": 1778498999123,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t_minus_1000.jpg",
        "mime_type": "image/jpeg"
      },
      {
        "name": "t_minus_500",
        "ts_ms": 1778498999623,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t_minus_500.jpg",
        "mime_type": "image/jpeg"
      },
      {
        "name": "t",
        "ts_ms": 1778499000123,
        "path": "/var/lib/temi_shared/events/temi-01/evt_20260511_000001/frame_t.jpg",
        "mime_type": "image/jpeg"
      }
    ]
  },
  "context": {
    "source": "temi_android",
    "wake_word_detected": true,
    "interaction_mode": "voice",
    "requires_response": true
  }
}
```

***

## 5.2 Hermes Output

Hermes 應只輸出：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "confidence": 0.86,
  "reasoning_summary": "User asks the robot to identify visible objects. A verbal response is sufficient.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上可能有一個杯子和一台筆電。",
      "language": "zh-TW"
    }
  ]
}
```

***

## 5.3 Command Request

Bridge publish：

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_20260511_000001",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "source": "hermes_temi_bridge",
  "created_at_ms": 1778499001200,
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上可能有一個杯子和一台筆電。",
      "language": "zh-TW"
    }
  ]
}
```

***

## 5.4 Command Result

Temi publish：

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_20260511_000001",
  "event_id": "evt_20260511_000001",
  "robot_id": "temi-01",
  "status": "success",
  "results": [
    {
      "action_id": "act_001",
      "type": "speak",
      "status": "success",
      "message": "TTS completed"
    }
  ],
  "finished_at_ms": 1778499005200
}
```

***

# 6. Historical Docker / Runtime 架構

> Historical architecture example. Do not use this section to choose a current
> lifecycle, private path, service ownership or configuration value; use the
> maintained Demo operations documents instead.
>
> `docker-compose.yml` is an optional secondary/development example. It is not
> invoked by `./scripts/demo` and must not be treated as a parallel production
> lifecycle or source of current ownership.

## 6.1 真實運行時需要啟動的服務

真實運行時至少要有：

```text
1. Temi Android App / Temi robot
2. MQTT Broker
3. Hermes Agent / Hermes container
4. HermesTemiBridge
5. Vision Server / Image Provider
```

如果 Vision Server 功能已經包含在既有 backend 中，則不需要獨立開一個服務。

***

## 6.2 建議啟動順序

```text
1. MQTT Broker
2. Vision Server / Image Provider
3. Hermes Agent / Hermes container
4. HermesTemiBridge
5. Temi Android App
```

原因：

*   Broker 要先起來，其他服務才能連接。
*   Vision 要先準備，才有圖片資料。
*   Hermes 要先可用，Bridge 才能呼叫。
*   Bridge 要先訂閱 MQTT，Temi publish event 時才不會漏接。
*   Temi 最後啟動，方便完整端到端測試。

***

## 6.3 Shared volume 建議

Host：

```text
./temi_shared
```

Bridge：

```text
/var/lib/temi_shared
```

Hermes：

```text
/shared/temi
```

範例 Docker Compose 概念：

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:latest
    ports:
      - "1883:1883"

  hermes:
    image: hermes-agent:latest
    volumes:
      - ./temi_shared:/shared/temi

  hermes-temi-bridge:
    build: ./hermes_temi_bridge
    environment:
      MQTT_BROKER_HOST: mosquitto
      MQTT_BROKER_PORT: "1883"
      TEMI_SHARED_BRIDGE_PATH: /var/lib/temi_shared
      TEMI_SHARED_HERMES_PATH: /shared/temi
      HERMES_INVOKE_MODE: cli
      HERMES_TIMEOUT_SECONDS: "60"
    volumes:
      - ./temi_shared:/var/lib/temi_shared
```

***

# 7. Historical Validation Plan

> Historical validation examples. The maintained verification command set and
> the distinction between hardware-free and external acceptance live in
> [`verification_and_acceptance.md`](../operations/verification_and_acceptance.md).

這一段非常重要。  
請先不要一開始就測整套系統，應該先確認每個模組獨立正常。

***

# 7.1 MQTT Broker 驗證

## 目標

確認 MQTT broker 可以 publish / subscribe。

## 啟動 broker

例如：

```bash
docker run --rm -it -p 1883:1883 eclipse-mosquitto
```

或使用既有 Mosquitto。

## 測試 subscribe

Terminal A：

```bash
mosquitto_sub -h localhost -p 1883 -t "temi/+/asr/final" -v
```

## 測試 publish

Terminal B：

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "temi/temi-01/asr/final" \
  -m '{"event_id":"evt_test","robot_id":"temi-01","asr":{"text":"hello"}}'
```

## 通過條件

Terminal A 應看到：

```text
temi/temi-01/asr/final {"event_id":"evt_test","robot_id":"temi-01","asr":{"text":"hello"}}
```

***

# 7.2 Shared Volume / Image Path 驗證

## 目標

確認 Bridge 與 Hermes 都能讀到同一批圖片。

## 建立測試圖片目錄

```bash
mkdir -p ./temi_shared/events/temi-01/evt_test_001
touch ./temi_shared/events/temi-01/evt_test_001/frame_t_minus_1000.jpg
touch ./temi_shared/events/temi-01/evt_test_001/frame_t_minus_500.jpg
touch ./temi_shared/events/temi-01/evt_test_001/frame_t.jpg
```

實務上 `touch` 只能測路徑存在。  
若要測真圖片，應放入有效 `.jpg`。

## Bridge container 中確認

```bash
ls -l /var/lib/temi_shared/events/temi-01/evt_test_001/
```

## Hermes container 中確認

```bash
ls -l /shared/temi/events/temi-01/evt_test_001/
```

## 通過條件

Bridge 與 Hermes 都看得到：

```text
frame_t_minus_1000.jpg
frame_t_minus_500.jpg
frame_t.jpg
```

***

# 7.3 Temi Android App MQTT 驗證

## 目標

確認 Temi Android App 可以：

1.  publish ASR final event。
2.  subscribe command request。
3.  publish command result。

## 測試 ASR publish

在 PC 端：

```bash
mosquitto_sub -h <broker_ip> -t "temi/+/asr/final" -v
```

對 Temi 說話，例如：

```text
幫我看看桌上的東西是什麼
```

## 通過條件

PC 端應收到：

```text
temi/temi-01/asr/final {...}
```

且 payload 應包含：

*   `event_id`
*   `robot_id`
*   `asr.text`
*   `speech_end_ts_ms`
*   `vision.frames`

***

## 測試 command subscribe

PC 端 publish command：

```bash
mosquitto_pub -h <broker_ip> \
  -t "temi/temi-01/cmd/request" \
  -m '{
    "schema_version": "1.0",
    "command_id": "cmd_test_001",
    "event_id": "evt_test_001",
    "robot_id": "temi-01",
    "source": "manual_test",
    "actions": [
      {
        "action_id": "act_001",
        "type": "speak",
        "text": "這是 MQTT 指令測試",
        "language": "zh-TW"
      }
    ]
  }'
```

## 通過條件

Temi 應說：

```text
這是 MQTT 指令測試
```

並 publish result：

```text
temi/temi-01/cmd/result
```

***

# 7.4 Vision Server / Image Provider 驗證

## 目標

確認系統可以根據 `speech_end_ts_ms` 取得三張圖片。

## 測試方式

人工或 mock 產生一個 event：

```text
event_id = evt_test_vision_001
speech_end_ts_ms = T
```

期望產出：

```text
frame_t_minus_1000.jpg
frame_t_minus_500.jpg
frame_t.jpg
```

## 檢查項目

1.  三張圖片是否存在。
2.  圖片是否為有效 JPEG。
3.  圖片是否可以被 Bridge 讀取。
4.  圖片是否可以被 Hermes container 讀取。
5.  圖片 timestamp 是否接近預期。
6.  檔案命名是否符合規範。

## 通過條件

目錄中存在：

```text
/var/lib/temi_shared/events/{robot_id}/{event_id}/frame_t_minus_1000.jpg
/var/lib/temi_shared/events/{robot_id}/{event_id}/frame_t_minus_500.jpg
/var/lib/temi_shared/events/{robot_id}/{event_id}/frame_t.jpg
```

***

# 7.5 Hermes Agent 驗證

## 目標

確認 Hermes Agent 能正常啟動，且能透過 CLI 或 API 被呼叫。

## 基本測試

```bash
hermes --help
```

或：

```bash
hermes chat -q "請回覆 JSON：{\"ok\": true}"
```

## 通過條件

Hermes 應能回應，不應出現：

*   command not found
*   model not configured
*   API key missing
*   provider unavailable
*   permission error

***

# 7.6 Agent Skill 驗證

## 目標

確認 `temi-robot-control` Skill 已被 Hermes 載入。

## 檢查 Skill 目錄

```bash
ls -l ~/.hermes/skills/temi-robot-control/
```

應包含：

```text
SKILL.md
references/action_schema.json
references/examples.md
references/safety_rules.md
```

## 測試 Hermes 是否看得到 Skill

可以問 Hermes：

```text
你有哪些 skills？請確認是否包含 temi-robot-control。
```

或直接呼叫：

```text
/temi-robot-control
```

## 通過條件

Hermes 能辨識 `temi-robot-control`，並能依照 skill 要求輸出 JSON。

***

# 7.7 HermesTemiBridge 單體驗證

## 目標

確認 Bridge 在沒有真 Temi 的情況下也能工作。

## 測試準備

建立測試圖片：

```text
./temi_shared/events/temi-01/evt_bridge_test_001/
├── frame_t_minus_1000.jpg
├── frame_t_minus_500.jpg
└── frame_t.jpg
```

啟動 Bridge：

```bash
python -m hermes_temi_bridge.main
```

或：

```bash
docker compose up hermes-temi-bridge
```

## 發送 mock ASR event

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "temi/temi-01/asr/final" \
  -m '{
    "schema_version": "1.0",
    "event_id": "evt_bridge_test_001",
    "robot_id": "temi-01",
    "conversation_id": "conv_test_001",
    "type": "asr.final",
    "timestamp_ms": 1778499000200,
    "speech_end_ts_ms": 1778499000123,
    "language": "zh-TW",
    "asr": {
      "text": "幫我看看桌上的東西是什麼",
      "confidence": 0.92
    },
    "vision": {
      "sampling_policy": "T-1000,T-500,T",
      "frames": [
        {
          "name": "t_minus_1000",
          "ts_ms": 1778498999123,
          "path": "/var/lib/temi_shared/events/temi-01/evt_bridge_test_001/frame_t_minus_1000.jpg",
          "mime_type": "image/jpeg"
        },
        {
          "name": "t_minus_500",
          "ts_ms": 1778498999623,
          "path": "/var/lib/temi_shared/events/temi-01/evt_bridge_test_001/frame_t_minus_500.jpg",
          "mime_type": "image/jpeg"
        },
        {
          "name": "t",
          "ts_ms": 1778499000123,
          "path": "/var/lib/temi_shared/events/temi-01/evt_bridge_test_001/frame_t.jpg",
          "mime_type": "image/jpeg"
        }
      ]
    },
    "context": {
      "source": "mock_test",
      "wake_word_detected": true,
      "interaction_mode": "voice",
      "requires_response": true
    }
  }'
```

同時開另一個 terminal 監聽 command：

```bash
mosquitto_sub -h localhost -p 1883 -t "temi/temi-01/cmd/request" -v
```

## 通過條件

應看到 Bridge publish command：

```text
temi/temi-01/cmd/request {...}
```

且 payload 中有合法 actions。

***

# 8. 串聯整合驗證計畫

當所有單體模組都通過後，才開始整合測試。

***

# 8.1 Integration Test 1：MQTT + Bridge

## 目的

不啟動 Hermes，先測 Bridge 是否能收到 event。

## 方法

將 Bridge 設成 mock Hermes mode。

例如：

```env
HERMES_INVOKE_MODE=mock
```

Mock Hermes 固定回：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_test",
  "robot_id": "temi-01",
  "confidence": 1.0,
  "reasoning_summary": "Mock response.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "這是 Bridge mock 測試",
      "language": "zh-TW"
    }
  ]
}
```

## 通過條件

Bridge 能收到 ASR event，並 publish command。

***

# 8.2 Integration Test 2：Bridge + Hermes

## 目的

不使用真 Temi，只測 Bridge 呼叫 Hermes 是否成功。

## 方法

使用 mock MQTT event。

Bridge 收到 event 後呼叫真 Hermes。

## 通過條件

1.  Hermes 被成功呼叫。
2.  Hermes 使用 `temi-robot-control` Skill。
3.  Hermes 回傳 JSON。
4.  Bridge 驗證 JSON 成功。
5.  Bridge publish command。

***

# 8.3 Integration Test 3：Temi + MQTT command

## 目的

不使用 Hermes，只測 Temi 是否能執行 command。

## 方法

人工 publish command：

```bash
mosquitto_pub -h <broker_ip> \
  -t "temi/temi-01/cmd/request" \
  -m '{
    "schema_version": "1.0",
    "command_id": "cmd_integration_001",
    "event_id": "evt_manual_001",
    "robot_id": "temi-01",
    "source": "manual_test",
    "actions": [
      {
        "action_id": "act_001",
        "type": "speak",
        "text": "Temi 指令整合測試成功",
        "language": "zh-TW"
      }
    ]
  }'
```

## 通過條件

1.  Temi 成功說話。
2.  Temi publish `cmd/result`。
3.  Bridge 或 monitor 能收到 result。

***

# 8.4 Integration Test 4：Temi ASR + Bridge + Mock Hermes

## 目的

確認 Temi 真實 ASR event 能打到 Bridge。

## 方法

1.  啟動 Temi Android App。
2.  啟動 MQTT。
3.  啟動 Bridge mock Hermes mode。
4.  對 Temi 說：

```text
幫我看看桌上的東西
```

## 通過條件

1.  Temi publish ASR final event。
2.  Bridge 收到 event。
3.  Bridge mock 出 command。
4.  Temi 執行 command。
5.  Temi publish result。

***

# 8.5 Integration Test 5：完整端到端 E2E

## 目的

驗證完整系統。

## 啟動服務

```text
1. MQTT Broker
2. Vision Server / Image Provider
3. Hermes Agent
4. HermesTemiBridge
5. Temi Android App
```

## 測試語句

### Case 1：純說話回答

對 Temi 說：

```text
你現在可以聽到我嗎？
```

預期：

```text
Temi 回答使用者。
```

***

### Case 2：視覺辨識

對 Temi 說：

```text
幫我看看桌上的東西是什麼
```

預期：

```text
Temi 根據圖片回答看到的物品。
```

***

### Case 3：模糊指涉

對 Temi 說：

```text
你看到那個嗎？
```

如果圖片無法明確判斷，預期：

```text
Temi 詢問澄清問題。
```

***

### Case 4：轉向

對 Temi 說：

```text
往左轉一點
```

預期：

```text
Hermes output turn action。
Temi 向左轉。
```

***

### Case 5：導航

對 Temi 說：

```text
去會議室
```

預期：

```text
Hermes output navigate action。
Temi 導航到 meeting_room。
```

***

### Case 6：停止

對 Temi 說：

```text
停下來
```

預期：

```text
Hermes output stop action。
Temi 停止目前動作。
```

***

# 9. 系統驗收標準

完整系統應符合以下條件。

## 9.1 功能驗收

*   Temi 可成功 publish ASR final event。
*   Bridge 可收到 ASR event。
*   Bridge 可驗證三張圖片。
*   Bridge 可呼叫 Hermes。
*   Hermes 可使用 `temi-robot-control` Skill。
*   Hermes 可輸出合法 JSON。
*   Bridge 可驗證 JSON actions。
*   Bridge 可 publish command。
*   Temi 可執行 command。
*   Temi 可回傳 command result。

***

## 9.2 安全驗收

*   Hermes 回傳非法 action 時，Bridge 必須拒絕。
*   Hermes 回傳非 JSON 時，Bridge 必須 fallback。
*   導航 target 不在白名單時，Bridge 必須拒絕。
*   turn degrees 超出範圍時，Bridge 必須拒絕。
*   圖片不存在時，Bridge 不可呼叫 Hermes 或需 fallback。
*   ASR text 空白時，Bridge 應回覆「我沒有聽清楚」。
*   Bridge 不可 crash。

***

## 9.3 可靠性驗收

*   重複 event\_id 不會重複執行。
*   Hermes timeout 時，Bridge 會 fallback。
*   MQTT reconnect 後 Bridge 可恢復訂閱。
*   Temi command result timeout 會被記錄。
*   每個 event 都有 log。

***

# 10. Log 與 Debug 規格

## 10.1 每個 event 應記錄

```text
event_id
robot_id
conversation_id
asr_text
speech_end_ts_ms
image_paths_bridge
image_paths_hermes
hermes_prompt_path
hermes_raw_output_path
validated_actions
command_id
cmd_result
latency_ms
error_reason
```

## 10.2 建議 log 結構

```text
logs/
└── events/
    └── {event_id}/
        ├── asr_event.json
        ├── hermes_prompt.txt
        ├── hermes_raw_output.txt
        ├── hermes_parsed_output.json
        ├── command_request.json
        ├── command_result.json
        └── trace.jsonl
```

***

# 11. 常見錯誤與排查

## 11.1 Bridge 收不到 ASR event

檢查：

```bash
mosquitto_sub -h <broker_ip> -t "temi/+/asr/final" -v
```

可能原因：

*   Temi MQTT broker IP 設錯。
*   topic 不一致。
*   MQTT broker 沒有開。
*   防火牆阻擋 1883。
*   Bridge subscribe topic 寫錯。

***

## 11.2 Bridge 找不到圖片

檢查：

```bash
ls -l /var/lib/temi_shared/events/{robot_id}/{event_id}/
```

可能原因：

*   Temi 傳的是 host path，不是 Bridge container path。
*   Docker volume mount 錯。
*   Vision server 尚未寫入圖片。
*   event\_id 目錄命名不一致。
*   圖片產生時間晚於 ASR event。

***

## 11.3 Hermes 看不到圖片

檢查 Hermes container：

```bash
ls -l /shared/temi/events/{robot_id}/{event_id}/
```

可能原因：

*   Hermes container 沒有 mount shared volume。
*   Bridge 沒有做 path translation。
*   prompt 裡傳的是 Bridge path，不是 Hermes path。

***

## 11.4 Hermes 回傳不是 JSON

可能原因：

*   Skill 沒有被載入。
*   prompt 約束不夠強。
*   Hermes model 不遵守格式。
*   沒有使用 JSON schema / output contract。

處理：

*   加強 prompt。
*   Skill 中明確要求 `Output JSON only`。
*   Bridge 支援從 Markdown fenced code block 抽取 JSON。
*   若仍失敗，fallback speak。

***

## 11.5 Temi 沒有執行 command

檢查：

```bash
mosquitto_sub -h <broker_ip> -t "temi/temi-01/cmd/request" -v
```

可能原因：

*   Temi 沒 subscribe。
*   robot\_id 不一致。
*   command schema 不符合 Temi Android parser。
*   action type 未支援。
*   Temi Android App 狀態不是可執行狀態。

***

# 12. 建議開發里程碑

## Milestone 1：通訊基礎完成

完成：

*   MQTT broker 啟動。
*   Temi 可 publish ASR。
*   Temi 可 subscribe command。
*   PC 可用 mosquitto\_pub/sub 測試。

驗收：

```text
PC 可以收到 Temi ASR event。
Temi 可以執行人工 publish 的 speak command。
```

***

## Milestone 2：圖片 path 機制完成

完成：

*   三張圖片產出。
*   shared volume 建立。
*   Bridge 與 Hermes 都能讀取圖片。

驗收：

```text
Bridge container 和 Hermes container 都能 ls 到三張圖片。
```

***

## Milestone 3：Bridge MVP 完成

完成：

*   Bridge subscribe ASR event。
*   Validate payload。
*   Validate images。
*   Mock Hermes output。
*   Publish command。

驗收：

```text
Mock event → Bridge → command request 成功。
```

***

## Milestone 4：Hermes Skill 完成

完成：

*   `temi-robot-control` Skill。
*   action schema。
*   examples。
*   safety rules。

驗收：

```text
Hermes 能根據測試 prompt 輸出合法 JSON actions。
```

***

## Milestone 5：Bridge + Hermes 串接完成

完成：

*   Bridge 呼叫 Hermes。
*   Hermes 回 JSON。
*   Bridge parse + validate。
*   Bridge publish command。

驗收：

```text
Mock ASR event → Bridge → Hermes → Bridge → command request。
```

***

## Milestone 6：Temi 真機 E2E

完成：

*   Temi 真實 ASR。
*   真實三張圖片。
*   真實 Hermes reasoning。
*   真實 command execution。

驗收：

```text
使用者對 Temi 說話 → Hermes 回應 → Temi 執行。
```

***

# 13. Coding Agent 任務清單

以下可以直接交給 Coding Agent。

## Task 1：整理專案目錄

建立或確認以下模組：

```text
project-root/
├── android-temi-client/
├── vision-backend/
├── hermes_temi_bridge/
├── hermes-skills/
│   └── temi-robot-control/
├── docker-compose.yml
├── temi_shared/
└── docs/
```

***

## Task 2：完成 MQTT schema

建立：

```text
docs/schemas/
├── asr_final_event.schema.json
├── hermes_output.schema.json
├── command_request.schema.json
└── command_result.schema.json
```

***

## Task 3：完成 HermesTemiBridge

Bridge 必須實作：

```text
config loader
mqtt subscriber
mqtt publisher
event validator
image path validator
path translator
prompt builder
hermes client
json parser
action validator
command dispatcher
idempotency cache
event logger
fallback handler
```

***

## Task 4：完成 Agent Skill

建立：

```text
hermes-skills/temi-robot-control/
├── SKILL.md
├── references/
│   ├── action_schema.json
│   ├── examples.md
│   ├── safety_rules.md
│   └── mqtt_topics.md
└── scripts/
    └── validate_temi_action.py
```

***

## Task 5：完成測試工具

建立：

```text
tools/
├── publish_mock_asr_event.sh
├── subscribe_cmd_request.sh
├── publish_mock_cmd_result.sh
├── create_mock_event_images.py
└── e2e_test_runner.py
```

***

## Task 6：完成 README

README 需包含：

1.  系統架構。
2.  啟動方式。
3.  MQTT topics。
4.  Payload examples。
5.  Docker volume 說明。
6.  Skill 安裝方式。
7.  單體測試。
8.  整合測試。
9.  E2E 測試。
10. troubleshooting。

***

# 14. 最終整合心智模型

你可以把整套系統想成：

```text
Temi Android App
  是身體、耳朵、嘴巴、腳

Vision Server
  是眼睛與短期視覺記憶

MQTT
  是神經傳導線

HermesTemiBridge
  是腦幹與感覺輸入橋樑

Hermes Agent
  是大腦

temi-robot-control Skill
  是大腦裡關於「如何安全操作 Temi」的操作手冊
```

完整運行時必須確保：

```text
身體有開
神經線有通
眼睛有畫面
橋樑有接上
大腦有啟動
操作手冊有載入
```

也就是：

```text
Temi Android App ✅
MQTT Broker ✅
Vision Server / Image Provider ✅
HermesTemiBridge ✅
Hermes Agent ✅
temi-robot-control Skill ✅
```

***

# 15. 最重要的實作原則

最後請 Coding Agent 特別注意：

1.  **不要用 MQTT 傳圖片 binary。**
2.  **不要讓 Hermes 直接控制 Temi。**
3.  **不要相信 Hermes raw output。**
4.  **所有 Hermes actions 都必須 schema validate。**
5.  **Bridge 是唯一負責 Temi ↔ Hermes 串接的服務。**
6.  **Skill 是 Hermes 的操作說明，不是 daemon。**
7.  **先做單體驗證，再做整合驗證。**
8.  **先 mock Hermes，再接真 Hermes。**
9.  **先 mock Temi，再接真 Temi。**
10. **所有 event 都要有 event\_id，方便追 log。**

如果依照這份文件實作，整合順序應該是：

```text
MQTT 通了
  ↓
Temi ASR 通了
  ↓
Temi command 通了
  ↓
圖片 path 通了
  ↓
Bridge mock 通了
  ↓
Hermes Skill 通了
  ↓
Bridge + Hermes 通了
  ↓
Temi + Bridge + Hermes 全系統通了
```

這樣會比一開始直接把全部服務一起開起來測穩很多，也比較容易定位問題。
