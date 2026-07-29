# TemiAgent Demo 操作入口

最後更新日期：2026-07-29

`./scripts/demo` 與 `demo_operations/` **不在目前 checkout**。先前引用它們的操作說明
不適用於此 branch；不要自行建立平行 launcher，也不要複製舊 branch 的 lifecycle script。

目前唯一受維護的啟動、停止、健康檢查與 viewer 操作來源是：

- [Demo 暖啟動操作手冊](demo_warm_start_runbook.md)
- [安全服務操作](safe_service_operations.md)
- [Android cross-service contract](../architecture/android_cross_service_contract.md)

## 目前 Media Demo 的能力界線

AI6 端可在所有 feature flags 開啟時提供這條受控路徑：

```text
canonical ASR
→ resident Hermes native Media tool
→ root-owned private Unix callback
→ Bridge Media v1.1 validator/builder
→ temi/{robot_id}/cmd/request
```

Bridge 是唯一 MQTT command publisher；resident Hermes 不直接連 MQTT。第一個 allowlisted
video ID 是 `elderly_hand_exercise`。`play_video`、`pause_video`、`resume_video` 與
`stop_video` 都使用既有 v1.1 contract 和 Android-generated playback session ID。

這不是 Android 播放完成的證明。Android source、asset/URI mapping 及 fresh 真機
`cmd/result` evidence 均不在此 checkout。更重要的是：目前沒有上游 VLM／Identity Provider
runtime producer。若沒有 fresh canonical `resident/identity/result`（受控 visual routing 只
接受 `source=vision_gender_fallback` 的 confirmed father/mother），active resident 會是
`unknown`，且 callback 會拒絕 private memory 和 Media command。

## 實際操作

依 [Demo 暖啟動操作手冊](demo_warm_start_runbook.md) 完成：

1. 指定 container 中的唯讀 port/PID 預檢。
2. repository 外 private config 的 feature flags 與 private care-memory root。
3. `tools/seed_demo_care_context.py` 的 synthetic seed／verify。
4. adapter、resident Hermes、Bridge、gateway、action viewer 的現有 entrypoint。
5. `mosquitto_sub` 與 `tools/show_temi_trace.py` 的只讀監看。

不得用 `mosquitto_pub` 直接製造 identity、video command 或 command result，作為自然語言
Hermes route 或 Android 真機播放的替代證據。
