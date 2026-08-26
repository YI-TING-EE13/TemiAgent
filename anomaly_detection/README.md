# Temi 異常偵測串流 Viewer

狀態：EXPERIMENTAL；viewer 與 abnormal perception event producer 可用於 Demo/研究，
但目前沒有真機、GPU、外部模型服務或 production perception 的 live verification claim。
viewer 只產生受 Bridge 驗證的 perception event，不擁有 canonical hardware dispatch。

這個資料夾是一個獨立的 `uv` 專案，用來測試 Temi camera 的持續影像接收。

viewer 會在 `8000` port 提供瀏覽器頁面。

瀏覽器頁面可以直接連到已解碼 JPEG frame 的 broadcast endpoint：

```text
ws://<pc-ip>:8081
```

它也仍可接收 Temi timestamp-prefixed H.264 WebSocket stream，並在同一個 HTTP port 提供瀏覽器可看的 MJPEG preview。

## 執行

```bash
cd /TemiAgent/anomaly_detection
uv sync
uv run temi-live-viewer --host 0.0.0.0 --port 8000
```

開啟：

```text
http://127.0.0.1:8000/
```

預設情況下，頁面會連到：

```text
ws://<same-host-as-page>:8081
```

頁面會用 JavaScript 解碼 `8081` 的 binary frame 格式：

```text
bytes 0..7    int64 big-endian timestamp_ms
bytes 8..15   uint64 big-endian sequence
bytes 16..    JPEG image bytes
```

`8081` 必須由 TemiAgent 的 `JpegFrameBroadcaster` 提供；它不是 HTTP 頁面。

Temi 的 video WebSocket target 可以指到以下其中之一：

```text
ws://<container-or-host-ip>:8000/
ws://<container-or-host-ip>:8000/ws
```

## Endpoints

- `/`：瀏覽器頁面，用於觀看 `8081` decoded JPEG broadcast；當 request 是 WebSocket upgrade 時也可作為 WebSocket intake。
- `/ws`：明確的 WebSocket intake path。
- `/stream.mjpg`：瀏覽器用 MJPEG stream。
- `/snapshot.jpg`：最新 frame 的 JPEG。
- `/health`：JSON 狀態。

## 動作預測 Viewer

`temi_action_viewer.py` 會從 `8081` 讀取 decoded JPEG frames，取樣八張影像，可選擇先畫 YOLO pose skeleton 作為模型輸入，再送到 llama.cpp multimodal server，最後把目前可見人體動作預測疊在畫面左上角。

取樣策略：

- 前三個一秒區間各取一張 frame。
- 最新一秒區間取五張 frame。
- 每次預測總共八張依時間排序的 frames。
- 當前秒會在推論時均勻取樣。
- 已完成秒的 history 代表幀，若可取樣數量足夠，使用第二張 sampled frame；否則使用第一張。

執行：

```bash
cd /TemiAgent/anomaly_detection
.venv/bin/python temi_action_viewer.py \
  --host 0.0.0.0 \
  --port 8010 \
  --source-url ws://127.0.0.1:8081 \
  --model gemma-4-e4b-finetuned@q8_0 \
  --gguf-model-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.Q8_0.gguf \
  --mmproj-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.BF16-mmproj.gguf
```

action viewer 預設期待 `llama-server` 位於：

```text
/TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server
```

如果 binary 不存在，瀏覽器 viewer 仍會啟動，`/health` 會回報 `llama_server_ready: false` 並顯示缺少的路徑。若要連到已經在跑的 llama.cpp server，而不是由 viewer 啟動，請傳入：

```bash
--llama-api-base-url http://127.0.0.1:8011/v1
```

YOLO pose 前處理由以下參數控制：

```bash
--pose-mode auto --pose-model yolo26x-pose.pt --pose-device 0
```

`auto` 會在 `ultralytics` 和 pose model 檔案都可用時套用 skeleton overlay。`on` 會在 dependency 或模型檔缺失時 fail fast。`off` 會送原始 frames。
`--pose-device 0` 會強制 YOLO pose inference 使用 GPU 0；只有 debug 時才建議用 `cpu`。

`yolo26x-pose.pt` 是 optional external model asset，預期位置與 size/hash 只由
`config/demo_resources.json` 記錄；它不是 Git 依賴，也沒有在本文件發明下載 URL。
目前 source、version、license 與 redistribution restrictions 尚待 maintainer confirmation。
`--pose-mode off` 不需要 pose weight；`auto` 可在缺少 weight 時略過 skeleton，`on` 則會
對缺少的 dependency 或模型明確失敗。模型結果本身不是醫療、安全或跌倒保證。

managed llama.cpp server 可以指定到特定實體 GPU，而不影響整個 viewer process：

```bash
--llama-cuda-visible-devices 3
```

專用 restart script 目前預設：

```text
LLAMA_CUDA_VISIBLE_DEVICES=3
POSE_DEVICE=3
```

也就是說，透過 `restart_action_viewer_8010.sh` 啟動時，finetuned Gemma 4 E4B Q8 llama.cpp server 和 YOLO pose 預設都會使用 GPU 3。

開啟：

```text
http://127.0.0.1:8010/
```

Endpoints：

- `/`：帶 prediction overlay 的瀏覽器頁面。
- `/stream.mjpg`：帶 overlay 的 MJPEG stream。
- `/snapshot.jpg`：最新 overlay frame。
- `/health`：JSON 狀態。

模型 prompt 要求模型精確輸出：

```text
Action: ...
Evidence/Reason: ...
```

parser 也相容舊格式 `action_name:` 和 `reason:`。

當 `Action` 是 `falls down`、`lies on the floor` 或 `fights` 其中之一時，viewer 可以把原始八張 evidence frames 存到 `/TemiAgent/temi_shared/abnormal_events/{robot_id}/{event_id}/`，並發布 structured event 到：

```text
temi/{robot_id}/perception/abnormal
```

MQTT payload 只包含 JSON metadata 和 frame paths。不包含 image bytes、confidence、confidence_source 或 severity。

viewer 不再直接發布 `cmd/request` pre-alert、`cmd/result` 或 Discord webhook。偵測到
canonical abnormal event 後，Bridge 驗證 evidence、保留 notification stage、呼叫 Resident
Hermes，並只在 action validator 通過後發布 speak command。這避免 perception bypass
action validation，也讓 reply、timeout 與 escalation 有可重啟的 episode evidence。

舊的 `--pre-alert-speak enabled` 僅會在 event result 記錄
`ABNORMAL_PRE_ALERT_BRIDGE_OWNED`；它不會發送 MQTT command。新 Demo 預設為
`--pre-alert-speak disabled`。

為了避免同一次跌倒或躺地狀態讓 Bridge/Hermes 被連續呼叫，action viewer 有 abnormal event cooldown。`restart_action_viewer_8010.sh` 正式 Demo 預設為 180 秒，也就是第一次緊急狀態發布後，3 分鐘內不會再發布新的 abnormal event；畫面 overlay 和模型推論仍會繼續更新。若要臨時調整：

```bash
cd /TemiAgent/anomaly_detection
ABNORMAL_COOLDOWN_SECONDS=300 ./restart_action_viewer_8010.sh
```

這個 cooldown 是全域 emergency cooldown，不依 action 類別分開計算；因此 `falls down` 和 `lies on the floor` 在 3 分鐘內互相切換時，也不會重複觸發 Hermes。

The viewer has no Discord delivery route. `--discord-delivery-test` returns
`DISCORD_BRIDGE_OWNED`, and lifecycle rejects
`DEMO_ACTION_VIEWER_DISCORD_NOTIFY=enabled`. Bridge configuration selects
`disabled`, `demo_mock`, or an authorized `discord_webhook` route. Demo mock
receipts never contact a recipient; real delivery is accepted only after HTTP
204. See [the immediate abnormal-care flow](../docs/operations/immediate_abnormal_care_flow.md).

When started by `scripts/demo`, the viewer receives complete, typed,
Bridge-owned notification metadata. `/health` reports redacted components for
`viewer_core`, `event_ingestion`, `frame_state`, `real_discord`, and
`demo_notification_mock`; it never returns a webhook or a credential path.
Disabled mode reports both notification components as disabled. Demo mock mode
reports the local receipt route only when both mock flags are enabled. A real
Discord configuration reports `real_discord=skipped_by_viewer`: credential
validation and delivery remain lifecycle/Bridge responsibilities. An internal
health-snapshot error returns HTTP 503 with `VIEWER_HEALTH_INTERNAL_ERROR`.

The viewer health endpoint is an availability contract, not proof of a model
result, MQTT publication, Bridge acceptance, Discord delivery, or Android
execution.

## 影片動作測試工具

`temi_video_action_tester.py` 會在本機影片檔上執行同一套八幀推論策略：

- 前三個已完成秒：每秒一張代表幀。
- 當前秒：五張均勻取樣 frames。
- 模型輸入在進 llama.cpp inference 前，會先經過同一個 YOLO pose renderer 前處理。
- evidence files 會從原始影片 frames 儲存，不是 pose overlay。

不發布 MQTT 的 dry run：

```bash
cd /TemiAgent/anomaly_detection
.venv/bin/python temi_video_action_tester.py \
  --video /path/to/video.mp4 \
  --no-publish \
  --output-jsonl /tmp/temi_video_predictions.jsonl
```

發布 abnormal detections 給 Bridge/Hermes：

```bash
cd /TemiAgent/anomaly_detection
.venv/bin/python temi_video_action_tester.py \
  --video /path/to/video.mp4 \
  --publish \
  --robot-id temi-01 \
  --mqtt-broker 127.0.0.1 \
  --mqtt-port 1883
```

若只是單一 alert smoke test，可以在第一個 abnormal window 後停止，避免一支短 fall video 連續送出多筆 Discord/MQTT 通知：

```bash
cd /TemiAgent/anomaly_detection
.venv/bin/python temi_video_action_tester.py \
  --video /path/to/video.mp4 \
  --publish \
  --stop-after-first-alert \
  --output-jsonl /tmp/temi_video_predictions.jsonl
```

發布後的 JSONL result 只包含 perception MQTT publication status。Notification receipt、
Hermes request、validated command、Android result 和 episode transition 由 Bridge trace 保存。

完整 Bridge/Hermes route 需要以下 companion services：

- `1883` 上的 MQTT broker。
- `8080` 和 `8081` 上的 `tools/temi_overview_adapter.py`。
- `8765` 上的 Hermes resident server。
- HTTP mode 的 `hermes_temi_bridge`。

目前預設 abnormal route 在 Bridge 驗證後建立 episode、記錄 notification stage，並呼叫
Resident Hermes。Bridge 仍擁有 action validation、command publication 與 private Care
Memory boundary；viewer 不會因偵測結果直接控制硬體或通知收件者。legacy route 只供相容性
測試，不是正式 Demo acceptance route。

## 注意事項

- MQTT 不用於傳送 image bytes。
- server 在記憶體中只保留最新 JPEG frame。
- 這是測試 viewer，不是最終版異常行為模型 pipeline。

## 8010 安全重啟

不要用 `pkill -f` 或寬鬆的 process-name pattern 重啟這個服務。像 `pkill -f "temi_action_viewer.py ..."` 這類 pattern 可能會 match 到正在執行 restart command 的 shell，導致 shell 在服務重新啟動前先殺掉自己。

請改用專用 restart script：

```bash
cd /TemiAgent/anomaly_detection
./restart_action_viewer_8010.sh
```

這個 script 只會檢查目前 listen 在 `8010` port 的 process，確認該 PID 是從 `/TemiAgent/anomaly_detection` 執行的 `temi_action_viewer.py`，然後只停止該 PID 並啟動新的 viewer。它不會碰 MQTT、8080 ingest、8081 frame broadcast、Hermes resident server、Bridge，或 8000 live viewer。

正式 Demo 預設 `ABNORMAL_COOLDOWN_SECONDS=180`。重啟後可以用以下指令確認：

```bash
curl -sS http://127.0.0.1:8010/health | grep abnormal_cooldown_seconds
```

## 一鍵關閉 anomaly_detection 服務

若要只關閉 `/TemiAgent/anomaly_detection` 目前管理的 action viewer 服務，使用：

```bash
cd /TemiAgent/anomaly_detection
./stop_action_viewer_8010.sh
```

這個 script 會：

- 停止 listen 在 `8010` 的 `temi_action_viewer.py`。
- 停止該 viewer 啟動的 managed `llama-server` child。
- 若 `8011` 仍有 anomaly_detection 的 managed llama-server，也會安全停止。
- 移除 stale `action_viewer.pid`。

它只會停止經過路徑與 command line 驗證的 anomaly_detection process；不會停止 MQTT `1883`、Temi ingest `8080`、decoded frame broadcast `8081`、Hermes resident `8765`、HermesTemiBridge、Discord/gateway，或其他模組服務。

## Responsibility and Non-responsibility

本模組負責 experimental frame viewing、sampling、pose preprocessing、specialist model
inference、prediction overlay 與 abnormal perception event production。

本模組不負責：

- 醫療診斷、保證性跌倒偵測或無人監督照護；
- Home-ESI policy、Hermes reasoning 或正式 caregiver notification；
- 一般 robot command dispatch；
- 長期保存 image、video、model output 或照護資料。

## Known Safety Exception

異常 care TTS policy 與 command dispatch 由 Bridge 擁有。viewer 只產生 perception
event，不能直接控制 Temi、讀取或送出 Discord credential、宣稱 Discord target 是照護者，
或將 notification action 放進 robot command。

## Configuration and Artifacts

Runtime configuration 來自 CLI、environment 與 ignored `.env`。`DISCORD_WEBHOOK_URL`
屬 secret，不能寫入 README、log、fixture 或 Git。Downloaded weights、`*.pt`、
`*.gguf`、test video、prediction JSONL、evidence frames、logs 與 PID files 都是
runtime/local artifacts。

## Tests and Health

```bash
cd /TemiAgent/anomaly_detection
uv run python -m unittest discover -s tests
```

`/health` 只證明 viewer 狀態；model、source、MQTT、Discord 與 downstream command
必須分別檢查。真實影像、GPU、Discord 或 Temi acceptance 需要 manual QA 與
event/trace evidence。

## Failure and Change Rules

慢速 inference 不得阻塞 `8081` ingest；sampling、queue/drop、timeout、cooldown 與
duplicate behavior 必須保持明確。MQTT 或 Discord failure 應個別記錄，不能互相冒充
成功。

修改 frame binary format、action labels、event payload、model revision、port、
cooldown、pre-alert、artifact layout 或 notification behavior 時，必須同步更新
producer/consumer、Bridge parser/path tests、model evaluation evidence、本 README、
[contract traceability](../docs/architecture/contract_traceability.md) 與 runbook。
