# MQTT 模組 README

最後更新日期：2026-06-01

## 本文件維護規則

這份 README 是 `mqtt/` 的快速入口。只要 broker 設定、topic contract、port、auth/TLS 或本地測試方式改變，都要同步更新本文件。

## 模組定位

`mqtt/` 保存本專案本地開發用 Mosquitto broker 設定。MQTT 是 Temi、Bridge、Backend 與 adapter 之間的事件匯流排，只傳遞輕量 JSON event 和 command，不傳圖片 binary。

## Topic contract

Canonical implemented routes：

```text
temi/{robot_id}/asr/final
temi/{robot_id}/perception/abnormal
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
```

Reserved topic，尚未確認 active producer／consumer：

```text
temi/{robot_id}/state
```

Legacy Android route：

```text
temi/event/asr
temi/action/speak
temi/action/navigate
temi/action/wakeup
```

`tools/temi_overview_adapter.py` 只負責 legacy ASR/camera 到 canonical ASR event 的轉換。新版 Temi app 直接訂閱 `temi/{robot_id}/cmd/request`，因此 adapter 不再把 command 轉成 `temi/action/speak` 或合成 `cmd/result`。

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `docker-compose.yml` | 掛載 `mqtt/mosquitto.conf` 啟動 broker。 |
| `hermes_temi_bridge/` | Subscribe canonical ASR/result，publish canonical command。 |
| `temi_backend/` | Legacy route 使用 MQTT 驗證 ASR/TTS/navigation；canonical Demo 主線僅重用其 vision buffer。 |
| `tools/` | 提供 publish/subscribe smoke test scripts。 |

## 啟動方式

Docker Compose：

```bash
cd /TemiAgent
docker compose up mosquitto
```

本機 Mosquitto：

```bash
mosquitto -c mqtt/mosquitto.conf
```

## Smoke test

Terminal A：

```bash
mosquitto_sub -h localhost -p 1883 -t "temi/#" -v
```

Terminal B：

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "temi/temi-01/cmd/request" \
  -m '{"schema_version":"1.0","command_id":"cmd_test","event_id":"evt_test","robot_id":"temi-01","source":"manual_test","actions":[{"action_id":"act_001","type":"speak","text":"MQTT test","language":"zh-TW"}]}'
```

## 維護注意

- 開發預設是 unauthenticated local broker；上線或跨網段展示時請另外評估帳密、ACL 與 TLS。
- 圖片只用 path/URL 傳遞，影像檔本體放在 `temi_shared/`。
- Topic 改動必須同步更新 `docs/schemas/`、Bridge tests、skills reference 與 Android/adapter 端。
- Canonical route 中若同一次 TTS 同時出現 `temi/{robot_id}/cmd/request` 與 adapter 發出的 `temi/action/speak`，代表 command 被重複轉發，應回頭檢查 adapter。

## Non-responsibilities

- Broker 不驗證照護語意、action safety 或 image path。
- Broker 不儲存 image bytes、secret、完整照護內容或無界 retained message。
- `mqtt/` 不擁有 Android hardware execution 或 Bridge policy。

## Configuration, Health and Stop

Authoritative local broker configuration is `mqtt/mosquitto.conf`; Compose 和 scripts 只應
引用該設定或明確記錄差異。確認 listener：

```bash
ss -ltnp 'sport = :1883'
```

Publish/subscribe smoke test 只能證明 broker transport；它不能證明 Bridge validation、
Hermes reasoning 或 Temi execution。停止或重啟前必須確認精準 PID、command line、
working directory 與 protected consumers，並遵守
[safe service operations](../docs/operations/safe_service_operations.md)。

## Failure and Security Limits

目前設定只適用受控本地 Demo。Unauthenticated broker 不應暴露到不受信任網段。
Broker 中斷時，producer/consumer 必須使用 bounded retry、timeout 或明確 degraded
state；不得把 publish attempt 當成 command success。Command success 以
`cmd/result` 與 trace evidence 判斷。

## Contract and Change Checklist

Topic、QoS、retain、port、auth、ACL 或 TLS 變更必須同步更新 producer、consumer、
Android App、Bridge tests、tools、module README、architecture 與 operations。
Canonical topic 目前分散於多個模組，沒有 generated single source；完整 owner matrix 見
[contract traceability](../docs/architecture/contract_traceability.md)。
