# MQTT 模組 README

最後更新日期：2026-05-19

## 本文件維護規則

這份 README 是 `mqtt/` 的快速入口。只要 broker 設定、topic contract、port、auth/TLS 或本地測試方式改變，都要同步更新本文件。

## 模組定位

`mqtt/` 保存本專案本地開發用 Mosquitto broker 設定。MQTT 是 Temi、Bridge、Backend 與 adapter 之間的事件匯流排，只傳遞輕量 JSON event 和 command，不傳圖片 binary。

## Topic contract

Canonical Overview route：

```text
temi/{robot_id}/asr/final
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
temi/{robot_id}/state
```

Legacy Android route：

```text
temi/event/asr
temi/action/speak
temi/action/navigate
temi/action/wakeup
```

`tools/temi_overview_adapter.py` 負責 legacy topics 與 canonical topics 的轉換。

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `docker-compose.yml` | 掛載 `mqtt/mosquitto.conf` 啟動 broker。 |
| `hermes_temi_bridge/` | Subscribe canonical ASR/result，publish canonical command。 |
| `temi_backend/` | Legacy route 使用 MQTT 驗證 ASR/TTS/navigation。 |
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
