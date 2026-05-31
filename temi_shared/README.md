# Temi Shared Data 模組 README

最後更新日期：2026-05-19

## 本文件維護規則

這份 README 是 `temi_shared/` 的快速入口。只要 shared volume layout、事件影像命名、metadata 格式或 runtime 清理規則改變，都要同步更新本文件。

## 模組定位

`temi_shared/` 是 Temi vision snapshots 與 event metadata 的 shared volume。MQTT event 只帶路徑；Bridge、Hermes、adapter 透過這個目錄讀取同一批 ASR 對齊影像。

## 目錄契約

```text
temi_shared/
  events/
    {robot_id}/
      {event_id}/
        frame_t_minus_1000.jpg
        frame_t_minus_500.jpg
        frame_t.jpg
        metadata.json
```

三張影像與 ASR `speech_end_ts_ms` 對齊：

| File | Meaning |
|---|---|
| `frame_t_minus_1000.jpg` | 語音結束前約 1000ms。 |
| `frame_t_minus_500.jpg` | 語音結束前約 500ms。 |
| `frame_t.jpg` | 語音結束時間點附近。 |
| `metadata.json` | canonical ASR event 副本，方便 debug。 |

## Path mapping

常見 mapping：

```text
Host:   /TemiAgent/temi_shared
Bridge: /var/lib/temi_shared
Hermes: /shared/temi
```

Bridge 會驗證 ASR event 中的 image path 位於 `TEMI_SHARED_BRIDGE_PATH` 內，再轉成 `TEMI_SHARED_HERMES_PATH` 提供給 Hermes prompt。

## 對外關係

| 關聯模組 | 關係 |
|---|---|
| `tools/temi_overview_adapter.py` | 從 legacy video buffer 寫入三張 keyframes 與 metadata。 |
| `hermes_temi_bridge/` | 驗證影像存在、做 path translation。 |
| `docker-compose.yml` | 把 host shared dir 掛載進 Bridge container。 |
| `docs/schemas/asr_final_event.schema.json` | 定義 event 中 `vision.frames[].path` 的資料形狀。 |

## Runtime 資料原則

- `temi_shared/events/` 是 runtime artifact，不是 source code。
- 可保留 Demo 重要案例作為手動驗證資料，但大量影像不建議提交版本控制。
- 若需要長期保存，應另建 `fixtures/` 或去識別化資料夾，並補 README 說明來源與用途。

## 建立 mock event images

```bash
cd /TemiAgent
python3 tools/create_mock_event_images.py \
  --root /TemiAgent/temi_shared \
  --robot-id temi-01 \
  --event-id evt_mock_001
```
