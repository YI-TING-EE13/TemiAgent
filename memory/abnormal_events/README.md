# Abnormal Events

此目錄保存第一年度 Demo 中 L1 或重要 L2 事件的詳細 mock artifact。

目前追蹤的 event 是 synthetic fixture；此目錄不得保存真實個案或 production abnormal event。後續 `notify_caregiver_mock` 流程若需新增 fixture，只能使用明確合成值：

```text
memory/abnormal_events/{event_id}.json
```

內容應包含：

- `event_id`
- `timestamp`
- `home_esi_level`
- `risk_reason`
- `evidence.image_paths`
- `actions_taken`
- `notification.type = demo_mock`

`evidence.image_paths` 必須是相對的 synthetic placeholder path，不得指向真實影像、`temi_shared/` runtime data 或絕對路徑。
