# Demo Structured Memory

最後更新日期：2026-05-31

## 定位

`memory/` 是第一年度 Demo 用的結構化照護記憶層。它不是知識圖譜、不是完整病歷系統，也不是正式醫療資料庫。

本目錄只保存 Demo 需要的最小狀態：

- 長者合成 persona 與照護偏好。
- 當日提醒與完成狀態。
- 當日互動與風險狀態。
- 可回放的照護事件紀錄。
- 高風險 mock event 與每日摘要 artifact。

## 檔案

```text
memory/
  profile.json          # Demo 長者 persona；目前設定為男性王先生
  daily_state.json      # 今日狀態、active reminders、recent event ids
  reminders.json        # Demo reminders 與完成狀態
  event_log.jsonl       # 追加式事件紀錄；一行一個 JSON object
  abnormal_events/      # L1 或重要 L2 的詳細 mock artifact
  summaries/            # Demo 結束後產生的每日照護摘要
```

## Demo 使用原則

- 所有資料皆為合成資料，不代表真實個案。
- 不存真實身份資訊、電話、地址或可識別個資。
- 影像不直接複製到 memory；只在 event log 中保存 `temi_shared/` path。
- Hermes 可讀取 memory 摘要與輸出 memory actions。
- 實際寫入 JSON / JSONL 由 Bridge 或後續 memory tool 負責。

## 對應 Demo

| Demo case | 主要讀寫 |
|---|---|
| 日常提醒 | `profile.json`、`reminders.json`、`event_log.jsonl` |
| 不適求助 L2 | `profile.json`、`daily_state.json`、`event_log.jsonl` |
| 疑似跌倒 L1 | `event_log.jsonl`、`abnormal_events/`、`summaries/` |
