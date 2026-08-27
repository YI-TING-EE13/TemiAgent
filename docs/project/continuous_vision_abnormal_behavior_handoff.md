# 持續影像串流與異常行為辨識交接文件

> Status: SUPPLEMENTAL EXPERIMENTAL handoff. It describes a research path, not
> a current medical, emergency or hardware-dispatch capability.

最後更新日期：2026-06-01

## 1. 文件目的

這份文件提供給後續接手 TemiAgent 專案的人員，用來理解目前系統架構，以及如何將現有「ASR 事件觸發後取三張影像快照」的處理方式，擴充為可支援「持續接收影像並串接異常行為辨識模型」的架構。

本文件不取代既有文件，而是補上 continuous vision / abnormal behavior 這條新需求的設計與交接。接手者應同時閱讀：

- `README.md`
- `Agent.md`
- `docs/architecture/project_overview.md`
- `docs/project/hermes_care_assistant_task_readme.md`
- `docs/operations/temi_streaming_local_runbook.md`
- `hermes_temi_bridge/README.md`
- `temi_backend/README.md`

## 2. 目前系統架構現況

### 2.1 核心分層

目前 TemiAgent 採分層解耦架構：

| 層級 | 主要模組 | 責任 |
|---|---|---|
| Robot sensing / actuation | Temi Android App | ASR、camera、TTS、navigation、硬體互動 |
| Event bus | MQTT / Mosquitto | 傳遞 ASR event、command request、command result |
| Vision receiver | `temi_backend/src/temi_backend/vision_server.py` | 接收 WebSocket H.264 影像、解碼、放入 rolling buffer |
| ASR/camera compatibility adapter | `tools/temi_overview_adapter.py` | 將 legacy ASR 與 WebSocket camera frames 轉成 canonical ASR event；不轉發 command |
| Safety bridge | `hermes_temi_bridge/` | 驗證事件、影像 path、Hermes JSON、action schema，發布安全 command |
| Cognitive core | `hermes-agent/` + `hermes-skills/` | 情境理解、照護記憶、Home-ESI 風險判斷、action planning |
| Runtime data | `temi_shared/`, `memory/`, `logs/` | 存放事件影像、metadata、structured memory 與驗證 artifact |

### 2.2 目前影像處理方式

目前實作已具備「持續接收影像」的底層能力，但高層消費方式仍是事件觸發：

```text
Temi Android camera
  -> WebSocket H.264 stream
  -> VisionServer.decode_message()
  -> VisionBuffer.push(timestamp_ms, frame)
  -> ASR final arrives on MQTT
  -> OverviewAdapter.handle_legacy_asr()
  -> VisionBuffer.get_keyframes(speech_end_ts_ms)
  -> write T-1000/T-500/T JPEG files into temi_shared/events/
  -> publish temi/{robot_id}/asr/final with image paths
  -> HermesTemiBridge validates three images and invokes Hermes
```

相關程式位置：

| 檔案 | 現況 |
|---|---|
| `temi_backend/src/temi_backend/vision_server.py` | `VisionServer` 持續接收影像；`VisionBuffer` 保存最近數秒 frame；`get_keyframes()` 取 ASR 對齊三張圖。 |
| `tools/temi_overview_adapter.py` | 收到 legacy ASR 後，從 buffer 取三張圖並寫入 `temi_shared/events/{robot_id}/{event_id}/`，再發布 canonical ASR event；command 由 Temi app 直接吃 `cmd/request`。 |
| `hermes_temi_bridge/src/hermes_temi_bridge/event_models.py` | `ASRFinalEvent` 強制要求三張 frame：`t_minus_1000`、`t_minus_500`、`t`。 |
| `hermes_temi_bridge/src/hermes_temi_bridge/image_resolver.py` | 驗證圖片存在、可讀、大小合理，並做 Bridge path 到 Hermes path 的轉換。 |
| `hermes_temi_bridge/src/hermes_temi_bridge/main.py` | 只處理 canonical ASR final event，不處理 continuous vision event。 |

### 2.3 目前架構限制

現有設計適合「使用者說話時，拿語音結束點附近的視覺上下文給 Hermes」；不適合「模型需要持續收到影像才能判斷異常行為」。

主要限制：

- `HermesTemiBridge.handle_asr_payload()` 是單次事件處理，不應承擔長時間影像流推論。
- `ASRFinalEvent` schema 固定要求三張圖片，不適合承載連續影像 window。
- MQTT contract 明確避免傳 image binary，只傳輕量 JSON 與 path。
- Hermes invocation 有 latency，尤其 CLI mode 曾達約 97 秒，不適合逐 frame 或高頻推論。
- 異常行為辨識需要穩定的 frame sampling、windowing、threshold、cooldown 與 evidence 保存，這些不屬於 ASR handler 的職責。

## 3. 新需求說明

使用者提出的需求是：Bridge 對影像串流的處理方式需改為持續串流，因為後續會串接一個需要持續接收影像的異常行為辨識模型。

本需求實際上不建議理解成「把 Bridge 改成直接吃 raw video stream」。較合理的需求拆解是：

1. 保留目前 ASR 對齊三張 snapshot 的路線，避免破壞既有 Hermes 語音互動。
2. 在現有 continuous video receiver 旁新增一條 continuous vision analytics pipeline。
3. 讓異常行為模型持續或準持續地接收 frame/window。
4. 異常模型只輸出結構化 perception event，不直接控制 robot。
5. HermesTemiBridge 擴充為可接收、驗證與處理 `perception.abnormal` 事件。
6. 另提供低頻 active snapshot helper，讓 Hermes 在沒有 ASR event 時可按需擷取目前畫面；此能力不取代 continuous abnormal worker。


## 3.1 2026-06-01 問題回報與已採取修正

共同開發者回報：`8080` 是原程式接收 Temi 上傳影像的 WebSocket input，不是對外廣播影像的 HTTP/stream endpoint；資料進到該 process 後不會自動給其他程式旁聽或讀取。這個判斷正確。

已採取修正：

- 保留 `ws://<pc-ip>:8080` 作為 Temi Android 上傳 timestamp-prefixed H.264 packets 的 ingest endpoint。
- 新增 decoded frame broadcast endpoint：`ws://<pc-ip>:8081`。
- `VisionServer` decode 出 OpenCV frame 後，仍寫入 `VisionBuffer`，並同步把 JPEG payload 推給 `JpegFrameBroadcaster`。
- 下游異常行為模型或其他程式應連 `8081`，不要連 `8080` 嘗試旁聽。
- ASR 三張 snapshot 路線維持不變，避免破壞既有 Hermes 語音互動。

`8081` binary message 格式：

```text
bytes 0..7    int64 big-endian timestamp_ms
bytes 8..15   uint64 big-endian sequence
bytes 16..    JPEG image bytes
```

手動驗證方式：

```bash
cd /TemiAgent/temi_backend
uv run python scripts/manual_frame_broadcast_receiver.py \
  --url ws://127.0.0.1:8081 \
  --output-dir debug_frames/broadcast \
  --max-frames 5
```


## 3.2 2026-06-01 8010 action viewer restart incident

共同開發者回報：重啟 8010 action viewer 時，`pkill` 的 pattern 掃到 shell 自己，導致 8010 服務暫時停止。這類問題通常發生在使用 `pkill -f "some command pattern"` 時，因為 `-f` 會比對完整 command line；執行重啟命令的 shell / wrapper command line 也可能含有同一段 pattern，於是 shell 被誤殺，後續 start command 沒有機會執行。

本次允許操作範圍：只允許處理 port `8010` 的 `temi_action_viewer.py`。不得重啟或終止 MQTT `1883`、Temi video ingest `8080`、decoded frame broadcast `8081`、Hermes resident `8765`、HermesTemiBridge、Discord/gateway 或其他正在運作的服務。

安全處理結果：

- 先確認 `8010` 對應 PID、工作目錄與 command line。
- 使用 `/health` 確認服務狀態。
- 重啟時不使用 `pkill`、不使用 process-name pattern。
- 只針對 `ss -ltnp "sport = :8010"` 找到且已驗證為 `/TemiAgent/anomaly_detection/temi_action_viewer.py` 的精準 PID 發送訊號。
- `TERM` 未結束時，才對同一個已驗證 PID 使用 `KILL`；不得對 pattern 或整類 Python process 使用 `KILL`。
- 重啟後確認 `8010 /health` 回 200，並確認 `1883`、`8080`、`8081`、`8765` 仍在 listen。

後續若需重啟 8010，請使用：

```bash
cd /TemiAgent/anomaly_detection
./restart_action_viewer_8010.sh
```

禁止使用：

```bash
pkill -f temi_action_viewer
pkill -f 8010
pkill python
killall python
```

若 `8010` 問題無法由上述 script 解決，先回報目前 PID、`/health` 結果、`action_viewer.log` tail 與 `ss -ltnp` 結果，不要擴大重啟範圍。

## 4. 建議修改後架構

### 4.1 目標架構

```text
Temi Android video stream
  -> ws://<pc-ip>:8080 VisionServer ingest
  -> VisionServer continuous decoder
  -> VisionBuffer + ws://<pc-ip>:8081 decoded JPEG broadcaster
       -> ASR Snapshot Sampler
            -> T-1000/T-500/T images
            -> temi/{robot_id}/asr/final
            -> HermesTemiBridge ASR route
       -> ActiveSnapshotHelper subscribes briefly to ws://<pc-ip>:8081
            -> temi_shared/live_snapshots/{robot_id}/{request_id}/frame_current.jpg
            -> Hermes on-demand visual analysis
       -> AbnormalBehaviorWorker subscribes to ws://<pc-ip>:8081
            -> frame sampling / temporal window
            -> abnormal behavior model
            -> evidence frame or clip paths
            -> temi/{robot_id}/perception/abnormal
            -> HermesTemiBridge abnormal route
            -> policy / Hermes / command dispatch
```

### 4.2 模組責任調整

| 模組 | 修改方向 | 設計理由 |
|---|---|---|
| `VisionServer` / `VisionBuffer` | 新增 frame consumer 或 FrameBus 機制 | 讓多個消費者可同時吃同一條影像流，避免 ASR sampler 與異常模型互相干擾。 |
| `tools/temi_overview_adapter.py` | 保留 ASR snapshot sampler；可啟動 abnormal worker | 目前 adapter 是 legacy ASR/camera 與 canonical ASR event 的邊界；仍不應承擔 command forwarding。 |
| `temi_backend/` | 新增 abnormal behavior worker / model adapter | heavy vision inference 應靠近影像流，不應放進 Bridge ASR handler。 |
| `hermes_temi_bridge/` | 新增 perception abnormal event parser、validator、handler | Bridge 仍是安全邊界，負責驗證與轉成安全 action。 |
| `docs/schemas/` 與 `hermes_temi_bridge/schemas/` | 新增 abnormal event schema | 所有跨模組 payload 都要有 schema，避免未來 contract 漂移。 |
| `temi_shared/` | 新增 abnormal evidence layout | 保存異常事件佐證 frame/clip，MQTT 仍只傳 path。 |
| `memory/abnormal_events/` | 保存結構化異常事件紀錄 | 供 Demo 驗收、每日摘要與後續照護記憶使用。 |

### 4.3 建議資料流

異常行為辨識模型不應逐 frame 直接觸發 Hermes。建議使用 temporal window：

- input sampling：5 FPS 起步，依模型需求調整。
- window size：2 到 5 秒起步。
- stride：0.5 到 1 秒起步。
- debounce：同一類事件在 cooldown 內不重複觸發。
- evidence：只保存觸發事件前後少量 frame 或短 clip。
- output：只發布結構化 abnormal event。

## 5. 建議新增 Contract

### 5.1 MQTT topic

新增 topic：

```text
temi/{robot_id}/perception/abnormal
```

由 abnormal behavior worker publish，由 HermesTemiBridge subscribe。

後續若有一般視覺狀態，也可另外規劃：

```text
temi/{robot_id}/perception/state
```

第一版不建議讓高頻 state 全部進 Bridge；Bridge 只需要接收低頻、經 threshold 過濾後的 abnormal event。

### 5.2 Abnormal event payload 草案

```json
{
  "schema_version": "1.0",
  "event_id": "evt_abnormal_1780000000000",
  "robot_id": "temi-01",
  "type": "perception.abnormal",
  "timestamp_ms": 1780000000000,
  "window": {
    "start_ts_ms": 1779999995000,
    "end_ts_ms": 1780000000000,
    "sample_fps": 5,
    "frame_count": 25
  },
  "observation": {
    "label": "fall_suspected",
    "confidence": 0.87,
    "severity": "high",
    "model_name": "abnormal-behavior-v1"
  },
  "evidence": {
    "frame_paths": [
      "/var/lib/temi_shared/abnormal_events/temi-01/evt_abnormal_1780000000000/frame_000.jpg"
    ],
    "clip_path": null
  },
  "context": {
    "source": "abnormal_behavior_worker",
    "requires_response": true
  }
}
```

### 5.3 建議 evidence layout

```text
temi_shared/
  abnormal_events/
    {robot_id}/
      {event_id}/
        frame_000.jpg
        frame_001.jpg
        metadata.json
        clip.mp4              # optional
```

`memory/abnormal_events/` 則保存去識別化或結構化事件紀錄：

```text
memory/
  abnormal_events/
    {event_id}.json
```

### 5.4 Bridge 行為草案

Bridge 收到 `perception.abnormal` 後應執行：

1. 驗證 schema version、event id、robot id、type。
2. 驗證 robot allowlist。
3. 驗證 label / severity / confidence 合法範圍。
4. 驗證 evidence path 位於 `TEMI_SHARED_BRIDGE_PATH` 下，且檔案存在、可讀、大小合理。
5. 檢查 event dedup 與 abnormal cooldown。
6. 寫入 event log。
7. 根據 severity / confidence 決定處理方式：
   - high severity：走固定安全 policy 或呼叫 Hermes 做照護風險判斷。
   - medium severity：可先詢問使用者狀態。
   - low severity：只記錄或等待下一個 window。
8. 所有 robot action 仍必須走既有 action schema validator。

## 6. 修改原因與設計考量

### 6.1 為什麼不直接改 ASR event schema

ASR event 的核心語意是「一次語音互動」，三張圖是語音上下文。若把 continuous video window 塞進同一個 schema，會造成：

- 原本 ASR unit tests 失效。
- Hermes prompt 變得過大且不穩定。
- 語音互動 latency 被 continuous inference 拖慢。
- 後續難以分辨「使用者說話觸發」與「感知模型觸發」的事件來源。

因此應新增 perception event route，而不是改壞 ASR route。

### 6.2 為什麼不讓 Bridge 跑 heavy model

Bridge 的定位是安全邊界：

- 驗證輸入。
- 呼叫 Hermes。
- 驗證 Hermes output。
- 發布 command。
- 記錄事件。

Bridge 不應變成影像推論服務。heavy model 若放進 Bridge，會讓 Bridge 的安全職責、MQTT runtime、Hermes invocation 與 GPU/CPU inference 綁死在一起，也會增加 crash blast radius。

### 6.3 為什麼 MQTT 不傳影像 binary

本專案既有原則是「MQTT 傳輕量 event 和 path，不傳圖片 binary」。持續影像更應遵守這點，否則會造成：

- Broker 負載不穩定。
- topic debugging 困難。
- retained / QoS 行為可能誤保留敏感影像。
- privacy 與 storage 邊界不清楚。

影像本體應透過 WebSocket、shared memory、shared volume 或模型服務內部 queue 傳遞；MQTT 只傳 metadata 與 evidence path。

### 6.4 為什麼要保留三張 snapshot

三張 snapshot 是目前 Hermes 語音互動、手勢判斷、指物問答與 Demo artifact 的既有 contract。保留它可以確保：

- `temi-robot-control` skill 不需大改。
- `ASRFinalEvent` tests 繼續有效。
- `temi_shared/events/` artifact 仍可追蹤。
- legacy live route 與 Overview canonical route 都有回退能力。

## 7. 建議實作順序

### Phase 0：文件與 contract

- 新增 `perception_abnormal_event.schema.json` 到 `docs/schemas/`。
- 若 Bridge runtime 需要 schema 檢查，也同步放到 `hermes_temi_bridge/schemas/`。
- 更新 `mqtt/README.md`、`temi_shared/README.md`、`hermes_temi_bridge/README.md`。
- 明確定義 labels、severity、confidence threshold、cooldown。

### Phase 1：FrameBus / consumer abstraction

- 在 `VisionBuffer` 或 `VisionServer` 旁新增 consumer 機制。
- 保留現有 `push()`、`get_keyframes()`、`latest()` API。
- 新增測試確認多 consumer 不會改動原 frame reference。
- 確保慢 consumer 不會卡住 WebSocket decode loop。

建議概念：

```text
DecodedFrame(timestamp_ms, frame, robot_id?, sequence?)
FrameBus.publish(decoded_frame)
FrameConsumer.on_frame(decoded_frame)
```

第一版可以用 bounded queue；queue 滿時丟棄舊 frame，而不是阻塞 decoder。

### Phase 2：AbnormalBehaviorWorker

- 新增 worker，從 FrameBus 取樣。
- 實作 window accumulator。
- 先做 mock model adapter，輸出固定 label/confidence，讓 pipeline 可測。
- 接真模型時以 adapter interface 包起來。
- 加入 cooldown、threshold 與 evidence writer。

### Phase 3：Bridge abnormal event route

- `TemiMqttClient` subscribe `temi/+/perception/abnormal`。
- `HermesTemiBridgeService` 新增 `handle_abnormal_payload()`。
- 新增 `AbnormalEvent` dataclass / parser。
- 驗證 evidence path 與 schema。
- 寫入 `memory/abnormal_events/` 與 event log。
- 視策略呼叫 Hermes 或直接發布安全詢問 command。

### Phase 4：Hermes skill / prompt 擴充

- 更新 `temi-home-esi`，讓 L1/L2 可以接收 abnormal event evidence。
- 更新 `temi-care-memory`，加入 abnormal event memory contract。
- 更新 `temi-robot-control`，說明 perception abnormal event 的處理原則。

### Phase 5：整合驗證與 Demo artifacts

- 新增 deterministic mock abnormal event runner。
- 保留 raw input、Bridge parsed event、published command、memory diff、evidence files。
- 在 Demo checklist 補上 continuous vision route 驗收項目。

## 8. 開發時應避免的行為

以下行為容易破壞既有架構，請避免：

1. 不要把 raw image binary 放進 MQTT payload。
2. 不要把 `8080` 當成對外影像串流 endpoint；`8080` 只給 Temi 上傳 H.264，其他程式要用 `8081` decoded frame broadcast。
3. 不要把異常模型推論寫進 `handle_asr_payload()`。
4. 不要讓 Hermes 直接 subscribe MQTT 或 publish robot command。
5. 不要讓異常模型直接控制 Temi、直接發 TTS、直接導航或停止。
6. 不要修改 ASR event 三張 frame contract 來承載 continuous window。
7. 不要移除 `VisionBuffer.get_keyframes()` 或改變它的回傳語意。
8. 不要讓 frame consumer 阻塞 WebSocket decode loop。
9. 不要無限制保存所有 frame；必須有 retention、sampling、cleanup 策略。
10. 不要在沒有 cooldown 的情況下對同一異常連續發 command。
11. 不要把 memory event log 當成可任意覆寫的狀態檔；事件應追加、狀態檔才可更新。
12. 不要繞過 Bridge action validator。
13. 不要宣稱第一版具備醫療級診斷或真實緊急通報能力。
14. 不要在未更新 schema、README、tests 的情況下改 MQTT contract。
15. 不要在 repo 中提交大量 runtime 影像、個資或未去識別化資料。
16. 不要破壞 legacy route；它仍是硬體展示與 debug 的重要備援。

## 9. 修改後驗證方式

### 9.1 Unit tests

Bridge：

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

Backend：

```bash
cd /TemiAgent/temi_backend
uv run pytest
```

應新增測試重點：

- `AbnormalEvent.from_payload()` 正常解析。
- 缺少 `event_id`、`robot_id`、`observation.label`、`confidence` 時失敗。
- confidence 超出 0 到 1 時失敗。
- unknown severity / label 的行為符合規格。
- evidence path 不在 shared root 時失敗。
- evidence file 不存在時 fallback 或 reject。
- duplicate abnormal event 被忽略。
- cooldown 內同類事件不重複觸發 command。
- ASR event 三張 frame route 不受 abnormal route 影響。

### 9.2 Pipeline tests

建議新增 hardware-free pipeline test：

1. 建立 mock frames。
2. 將 frames publish 到 FrameBus。
3. AbnormalBehaviorWorker 以 mock model 回傳 `fall_suspected`。
4. Worker 寫入 evidence frame。
5. Worker publish `temi/{robot_id}/perception/abnormal` payload。
6. Bridge handler 驗證 payload。
7. Bridge 發出安全詢問 command 或 memory action。

### 9.3 Local mock E2E

既有 smoke test 仍需通過：

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

新增 abnormal route 後，建議新增類似：

```bash
cd /TemiAgent
python3 tools/publish_mock_abnormal_event.py
```

此 script 應建立 evidence files、publish abnormal event，並確認 Bridge 產出 expected command / memory artifact。

### 9.4 實機驗證

實機驗證順序：

1. 確認 Temi ADB / MQTT / WebSocket 狀態，參考 `docs/operations/temi_streaming_local_runbook.md`。
2. 啟動 Mosquitto。
3. 啟動 Overview adapter / VisionServer。
4. 確認 WebSocket 影像流持續進來。
5. 啟動 abnormal worker mock mode，確認能定期取樣。
6. publish mock high-confidence abnormal observation。
7. 確認 Bridge 收到 `perception.abnormal` 並寫 log。
8. 確認 Temi 收到安全詢問 TTS。
9. 再測 ASR 語音互動，確認三張 snapshot flow 未被破壞。

### 9.5 驗收 artifacts

每次整合驗收至少保存：

- abnormal event raw JSON。
- evidence frame 或 clip path。
- Bridge event log。
- published command request。
- command result。
- `memory/abnormal_events/{event_id}.json`。
- 若有呼叫 Hermes，保存 raw Hermes output 與 parsed action output。

## 10. 測試重點

### 10.1 功能正確性

- continuous stream 不因 ASR event 才開始。
- ASR snapshot sampler 仍能正確取得 `T-1000/T-500/T`。
- abnormal worker 可在沒有 ASR 的情況下觸發 event。
- event_id dedup 有效。
- cooldown 有效。
- severity / confidence threshold 可設定。

### 10.2 安全性

- evidence path 不能跳出 shared root。
- robot_id 必須符合 allowlist。
- action 必須通過 schema validator。
- 高風險事件不應自動執行危險導航。
- 真實通報仍為 mock，除非未來明確實作與驗證。

### 10.3 效能與穩定性

- WebSocket decoder 不被模型推論阻塞。
- queue 滿時有丟棄策略。
- memory / disk 不會因長時間 streaming 無限制成長。
- worker crash 不應拖垮 Bridge ASR route。
- 模型 latency 不應影響 Temi 基本 TTS command route。

### 10.4 可觀測性

- 每個 abnormal event 都有 event_id。
- logs 可追蹤從 model output 到 Bridge command 的完整路徑。
- evidence frame 可定位到原始事件。
- threshold / cooldown decision 要能在 log 中看見。

## 11. 專案開發規範與流程

### 11.1 架構原則

- Hermes 負責理解與規劃，不直接控制硬體。
- Bridge 負責驗證、安全邊界與 command dispatch。
- Vision backend 負責影像接收、buffer、sampling 與模型推論。
- MQTT 傳 event metadata，不傳影像 binary。
- Shared volume 傳 evidence path，不傳不受控任意路徑。
- Schema 與 README 必須跟 code 一起更新。

### 11.2 實作流程

建議每次功能修改遵守：

1. 先確認 contract：topic、payload、schema、path layout。
2. 先寫或更新 tests。
3. 實作最小可測功能。
4. 跑 unit tests。
5. 跑 mock E2E。
6. 更新 README / runbook / handoff。
7. 實機驗證前先用 mock model 跑通。
8. 實機驗證後保存 artifacts。

### 11.3 Git / workspace 注意

- 目前 repo 可能有 runtime memory 或 logs 的未提交變動，修改前後都要確認不要覆蓋他人資料。
- 不要使用 destructive git command 清除工作區。
- 不要把大量 runtime images、logs 或含個資資料提交。
- 若只改 continuous vision 文件或 schema，不應順手重構 Hermes upstream。

### 11.4 文件維護規範

若有任何以下變更，必須同步更新文件：

- MQTT topic 改動。
- payload schema 改動。
- shared volume path layout 改動。
- Bridge validation 行為改動。
- abnormal model labels / severity / threshold 改動。
- 啟動方式或環境變數改動。
- Demo 驗收流程改動。

優先更新位置：

- `docs/project/continuous_vision_abnormal_behavior_handoff.md`
- `docs/architecture/project_overview.md`
- `docs/operations/temi_streaming_local_runbook.md`
- `hermes_temi_bridge/README.md`
- `temi_backend/README.md`
- `mqtt/README.md`
- `temi_shared/README.md`

## 12. 建議新增檔案清單

後續實作時可考慮新增：

```text
docs/schemas/perception_abnormal_event.schema.json
hermes_temi_bridge/schemas/perception_abnormal_event.schema.json
hermes_temi_bridge/src/hermes_temi_bridge/abnormal_event_models.py
hermes_temi_bridge/tests/test_abnormal_event_validation.py
temi_backend/src/temi_backend/frame_bus.py
temi_backend/src/temi_backend/abnormal_worker.py
temi_backend/tests/test_frame_bus.py
temi_backend/tests/test_abnormal_worker.py
tools/publish_mock_abnormal_event.py
tools/run_mock_abnormal_pipeline.py
```

是否把 abnormal worker 放在 `temi_backend/` 或獨立服務，取決於模型部署方式。第一版為了降低整合成本，建議先放在 `temi_backend/` 或由 `tools/temi_overview_adapter.py` 啟動；等模型穩定後再拆服務。

## 13. 接手者優先順序

若下一位開發者時間有限，建議順序如下：

1. 不動現有 ASR route，先補 abnormal event schema。
2. 寫 Bridge abnormal event parser/validator 的 unit tests。
3. 用 mock payload 打通 Bridge abnormal route。
4. 再做 FrameBus 與 mock AbnormalBehaviorWorker。
5. 最後才接真模型。

先把 contract 和安全邊界穩住，再追求模型效果。這會讓系統在 Demo、debug 與後續研究擴充時更可靠。
