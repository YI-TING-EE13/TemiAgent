# 第一年度 Demo 系統設計與本次調整說明

> Status: HISTORICAL design snapshot. Check current source, schemas and status
> before reusing any design or command detail.

最後更新日期：2026-06-01

## 目的

本文件是本次 Demo 的最新說明文件，整理目前系統設計、已實作功能、Bridge 設計檢視，以及 2026-06-01 為避免 Temi 重複說話所做的 adapter 調整。

## 目前系統設計

```text
Temi Android app
  -> legacy ASR: temi/event/asr
  -> WebSocket camera frames: ws://$PC_IP:8080
  -> ASR/camera-only Overview adapter
  -> canonical ASR event: temi/temi-01/asr/final + temi_shared image paths
  -> HermesTemiBridge
  -> resident Hermes / CLI Hermes / mock Hermes
  -> validated command request: temi/temi-01/cmd/request
  -> Temi Android app executes speak / turn / navigate / stop
  -> command result: temi/temi-01/cmd/result
```

分工原則：

- Temi app 負責硬體能力：聽、看、說、移動。
- `tools/temi_overview_adapter.py` 只負責 ASR 與 camera compatibility，將 legacy ASR 和 camera frames 轉成 canonical ASR event。
- HermesTemiBridge 是安全邊界，負責 schema validation、image path validation、Hermes invocation、action validation、memory/demo side effects 與 command dispatch。
- Hermes Agent 負責照護情境理解、Home-ESI v2 decision-tree 風險判斷與 action planning。
- MQTT 只傳輕量 JSON；影像檔放在 `temi_shared/events/...`，MQTT payload 只放 path。

## 已實作功能

- Temi app 可連到 MQTT broker `$PC_IP:1883`。
- Temi app 可透過 WebSocket 將 camera frames 送到 PC `$PC_IP:8080`。
- Adapter 可在 ASR final 時取 T-1000、T-500、T 三張 keyframes，寫入 `temi_shared/`，並發布 `temi/temi-01/asr/final`。
- `tools/capture_temi_live_snapshot.py` 可在沒有 ASR event 時按需從 `8081` 擷取目前畫面，寫入 `temi_shared/live_snapshots/`，讓 Hermes 進行低頻主動視覺分析。
- Bridge 支援 mock、CLI、resident HTTP 三種 Hermes invocation mode。
- Bridge 驗證 Hermes JSON-only output、robot-facing actions、`cognitive_state.home_esi_level` 與 `risk_reason`。
- Bridge 會將通過驗證的 robot actions 發布到 `temi/{robot_id}/cmd/request`。
- Temi app 已可直接執行 canonical `cmd/request` 並發布 `cmd/result`。
- Discord/manual TTS 若只得到 Hermes action JSON，可用 `tools/dispatch_hermes_action_output.py --publish` 驗證並送入 canonical command path。
- Hermes 文件與 skills 已補上 Temi embodied mapping：看 = camera/vision，聽 = ASR/microphone，說 = Temi TTS。

## 本次調整

本次調整將 adapter 改成「只負責 ASR 與 camera，不再轉發 command」。原因是新版 Temi app 已直接訂閱 canonical `temi/{robot_id}/cmd/request`；若 adapter 同時把同一個 command 轉成 legacy `temi/action/speak`，Temi 會收到兩條 speak 路徑而重複說話。

修改內容：

- 移除 adapter 對 `temi/+/cmd/request` 的訂閱。
- 移除 adapter 對 `temi/action/speak`、`temi/action/navigate` 的 publish。
- 移除 adapter 合成 `temi/{robot_id}/cmd/result` 的邏輯。
- 移除 missing keyframes 時的 speak fallback，改為只記錄錯誤，避免在看不到畫面時額外觸發 TTS。
- 新增 backend 測試，確認 adapter 只訂閱 legacy ASR、沒有 command forwarder、缺影像不會 publish speak fallback、有效 keyframes 會發布 canonical ASR event。

## Bridge 設計檢視

目前 Bridge 的架構是清楚且可維護的。它把高風險責任集中在安全邊界：輸入事件驗證、影像 path 驗證、Hermes output 驗證、action schema 驗證、idempotency、memory side effects 與 command publishing。這些職責彼此相關，放在 Bridge 中合理。

目前不建議把以下責任加入 Bridge：

- 不做 video decode 或 heavy vision inference，避免 ASR handler 變成影像服務；主動視覺使用受控 snapshot helper，continuous abnormal detection 仍由獨立 worker 處理。
- 不直接操作 Temi SDK 或 Android app，硬體仍由 app 負責。
- 不直接讓 Hermes publish MQTT，避免繞過 validation。
- 不把 legacy compatibility 的 command forwarding 放回 adapter，避免重複 TTS。

後續若要擴充異常行為辨識，建議新增獨立 worker 或靠近 vision stream 的服務，輸出已整理過的 abnormal event，再由 Bridge 或照護 flow 消費。

## Demo 驗證重點

一次完整實機 Demo 應看到：

```text
temi/event/asr
temi/temi-01/asr/final
temi/temi-01/cmd/request
temi/temi-01/cmd/result
```

同一次 canonical TTS 不應再看到 adapter 產生的 `temi/action/speak`。若出現，代表仍有舊 backend 或舊 adapter 在轉發 command，需停止或更新。

## 本次驗證紀錄

- `temi_backend` adapter unit test：`uv run pytest tests/test_overview_adapter.py` 通過。
- 實機 canonical command path 測試：`cmd/request` 與 `cmd/result` 出現，`temi/action/speak count: 0`，Android log 中 `ACTION_SPEAK count: 1`。
- 這表示 Temi 只透過 canonical command path 說話，重複 TTS 問題已被移除。
