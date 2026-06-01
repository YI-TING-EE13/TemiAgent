# Temi Backend 模組 README

最後更新日期：2026-06-01

## 本文件維護規則

這份 README 是 `temi_backend/` 的快速入口。只要 legacy MQTT topic、WebSocket 影像流程、LM Studio/VLM 路線、manual scripts 或 pytest 驗證方式改變，都要同步更新本文件。

## 模組定位

`temi_backend` 是早期已驗證的 PC 端 Temi 大腦與影像接收器。它可直接接收 Temi WebSocket H.264 影像、監聽 legacy MQTT ASR event，將語音與同步影像送到本地 OpenAI-compatible VLM endpoint，並透過 MQTT 發回安全 robot actions。

目前它有兩個用途：

- Legacy live route：最快驗證 Temi ASR、camera、TTS、navigation 與 LM Studio/VLM 閉環。
- Overview adapter support：`tools/temi_overview_adapter.py` 會重用本模組的 `VisionServer`，把 legacy ASR 與 camera frames 轉成 `docs/architecture/project_overview.md` 的 canonical ASR event；command 由 Temi app 直接訂閱 canonical topic，不再經 adapter 轉發。

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `mqtt/` | 使用 legacy topics 接收 ASR、發送 speak/navigation。 |
| `tools/temi_overview_adapter.py` | 匯入 `VisionServer`，產生 canonical ASR event 與三張影像；不處理 command。 |
| `temi_shared/` | Overview adapter 會把 keyframes 寫入 shared events 目錄。 |
| `hermes_temi_bridge/` | 新架構中由 Bridge 接手 Hermes 呼叫與 command validation。 |
| LM Studio / local VLM | Legacy route 的 OpenAI-compatible model endpoint。 |

## 核心職責

- 接收 Temi Android WebSocket H.264 video stream。
- 維護 timestamped vision buffer。
- 在 ASR final 時取出 T-1000、T-500、T 三張 keyframes。
- 呼叫本地 VLM endpoint 取得 action plan。
- 將 VLM output route 成支援的 Temi MQTT actions。
- 提供不需要硬體的 pytest unit tests。
- 提供 manual scripts 做 MQTT、TTS、navigation、video stream 驗證。

## 主要檔案

```text
temi_backend/
  src/temi_backend/
    config.py          # runtime env config
    vision_server.py   # WebSocket H.264 receiver and frame buffer
    mqtt_bridge.py     # legacy MQTT bridge
    agent_core.py      # ASR + vision + VLM orchestration
    cli.py             # package CLI entry
  scripts/
    manual_asr_monitor.py
    manual_tts.py
    manual_navigate.py
    manual_video_receiver.py
  tests/               # pytest suite
  debug_frames/        # generated frame snapshots; not source of truth
```

## Legacy topics

目前 Temi Android App 已驗證使用 legacy topics：

```text
temi/event/asr
temi/action/speak
temi/action/navigate
temi/action/wakeup
```

新架構 canonical topics：

```text
temi/{robot_id}/asr/final
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
```

其中 adapter 只發布 `asr/final`；Bridge 發布 `cmd/request`；Temi app 執行後發布 `cmd/result`。

## 安裝與測試

```bash
cd /TemiAgent/temi_backend
uv sync --group dev
uv run pytest
```

## 啟動 legacy backend

```bash
cd /TemiAgent/temi_backend
uv run temi-backend
```

等價 source wrapper：

```bash
uv run python main.py
```

預設服務：

- MQTT broker：`tcp://<pc-ip>:1883`
- Video receiver：`ws://<pc-ip>:8080`
- Local VLM：`http://localhost:1234/v1`

## 重要環境變數

| Variable | Default | Purpose |
|---|---:|---|
| `TEMI_MQTT_BROKER` | `127.0.0.1` | MQTT broker host。 |
| `TEMI_MQTT_PORT` | `1883` | MQTT broker port。 |
| `TEMI_VISION_HOST` | `0.0.0.0` | WebSocket bind host。 |
| `TEMI_VISION_PORT` | `8080` | WebSocket bind port。 |
| `TEMI_LM_BASE_URL` | `http://localhost:1234/v1` | OpenAI-compatible VLM endpoint。 |
| `TEMI_LM_MODEL` | `local-model` | VLM model name。 |
| `TEMI_DEBUG_FRAMES_DIR` | `debug_frames` | ASR-aligned snapshots 位置。 |

## Manual verification

```bash
uv run python scripts/manual_asr_monitor.py --broker 127.0.0.1 --port 1883
uv run python scripts/manual_tts.py --broker 127.0.0.1 --text "Temi MQTT test" --language EN_US
uv run python scripts/manual_navigate.py --broker 127.0.0.1 --target home_base
uv run python scripts/manual_video_receiver.py --host 0.0.0.0 --port 8080
```

## 維護注意

- `temi_backend` 是可展示的 legacy route，不要在還沒替代驗證前移除。
- Overview canonical contract 應優先放在 `hermes_temi_bridge/` 與 `docs/schemas/`，避免 legacy topic 污染新架構。
- 不要把 canonical command 轉發責任放回 `temi_backend` 或 adapter；這會讓新版 Temi app 與 legacy speak topic 同時觸發 TTS。
- `debug_frames/` 是 runtime artifact，不應被當成測試 fixture 或權威資料。
