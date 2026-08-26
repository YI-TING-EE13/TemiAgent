# Demo Structured Memory

最後更新日期：2026-08-26

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
  profile.json          # Demo persona；目前使用 synthetic-resident-001
  daily_state.json      # 今日狀態、active reminders、recent event ids
  reminders.json        # Demo reminders 與完成狀態
  event_log.jsonl       # 追加式事件紀錄；一行一個 JSON object
  abnormal_events/      # L1 或重要 L2 的詳細 mock artifact
  summaries/            # Demo 結束後產生的每日照護摘要
```

## Demo 使用原則

- 所有資料皆為合成資料，不代表真實個案。
- 不存真實身份資訊、電話、地址或可識別個資。
- 影像不直接複製到 memory；fixture 只使用相對的 synthetic placeholder path，不指向 `temi_shared/` 或真實影像。
- Hermes 可讀取 memory 摘要與輸出 memory actions。
- 實際寫入 JSON / JSONL 由 Bridge 或後續 memory tool 負責。

## Provenance and publication boundary

- `provenance_status`: `SYNTHETIC_FIXTURE_GENERATED_FOR_GATE1A`
- `data_origin`: newly generated synthetic placeholders for Gate 1A publication-boundary verification.
- `real_person_data`: `NO`.
- `consent_or_source_record`: `NOT_APPLICABLE_SYNTHETIC`.
- `production_runtime_data`: `MUST_NOT_BE_COMMITTED`.
- This declaration applies to the current tracked fixtures only; it does not make a provenance claim about any prior fixture contents.
- Regenerate or edit these files only with clearly synthetic identifiers, narratives, paths and contact targets. Do not copy logs, care records, credentials, media or production state into this directory.
- Runtime state remains outside the publication boundary in `.runtime/`, `logs/`, `temi_shared/`, caches and other ignored locations.

## 對應 Demo

| Demo case | 主要讀寫 |
|---|---|
| 日常提醒 | `profile.json`、`reminders.json`、`event_log.jsonl` |
| 不適求助 L2 | `profile.json`、`daily_state.json`、`event_log.jsonl` |
| 疑似跌倒 L1 | `event_log.jsonl`、`abnormal_events/`、`summaries/` |
