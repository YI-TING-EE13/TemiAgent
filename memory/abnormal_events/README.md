# Abnormal Events

此目錄保存第一年度 Demo 中 L1 或重要 L2 事件的詳細 mock artifact。

目前尚未有真實 Demo abnormal event。後續 `notify_caregiver_mock` 或疑似跌倒流程完成後，可新增：

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
