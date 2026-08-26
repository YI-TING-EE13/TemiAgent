# Summaries

此目錄保存第一年度 Demo 結束後生成的每日照護摘要。

目前的 tracked 摘要是 synthetic fixture，不是正式照護紀錄。後續 `generate_summary` 完成後，只可在去識別且合成的 fixture policy 下新增：

```text
memory/summaries/2026-05-31.md
```

摘要應包含：

- 今日提醒完成狀態。
- 不適或異常事件。
- Home-ESI 風險分級結果。
- mock notification 狀態。
- Demo 限制聲明。

摘要不得包含真實個案資料、production runtime state、聯絡方式、憑證或可識別媒體路徑。
