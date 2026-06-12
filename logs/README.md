# Logs 模組 README

最後更新日期：2026-06-12

## 本文件維護規則

這份 README 是 `logs/` 的快速入口。只要 log layout、檔名規則、保留策略或 Demo artifact 規則改變，都要同步更新本文件。

## 模組定位

`logs/` 存放 Bridge、Overview adapter、resident Hermes 與 Demo 驗證過程產生的 runtime logs。它是 debug 與驗收佐證資料，不是 source code。

## 常見內容

```text
logs/
  events/                              # Bridge event processing logs
  overview_bridge_mock_after_restart/  # mock Bridge restart validation
  overview_bridge_real/                # real Hermes CLI validation
  overview_bridge_resident_validate/   # resident HTTP validation
```

## 使用原則

- 重要 Demo 證據可保留並在 runbook 中引用。
- 大量臨時 log、含個資的 raw output 或影像路徑應定期清理。
- 若 log 內容用於測試 fixture，請複製到明確的 fixture 目錄並去識別化。
- 新增長期保留的 log 子目錄時，請補充用途與產生方式。

## Bridge trace logs

HermesTemiBridge v1 trace logs 使用 append-only JSONL：

```text
{LOG_DIR}/{event_id}.jsonl
{LOG_DIR}/_index.jsonl
```

單一 event timeline 的 `seq` 會單調遞增；`_index.jsonl` 可對同一 `event_id` 追加 `started`、`completed`、`failed`、`ignored` 多筆狀態。`_index.jsonl` 是 audit index；操作狀態請以 `tools/show_temi_trace.py` 的 timeline 聚合為準，避免 duplicate attempt 追加的 `ignored` 誤蓋已完成事件。

查看方式：

```bash
cd /TemiAgent
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --event-id <event_id>
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --full
python3 tools/show_temi_trace.py --log-dir /TemiAgent/logs/overview_bridge_resident --latest --json
```

常見 summary 欄位：

- `completed`：Bridge 已完成 Hermes output validation、memory action 與 command publish 流程。
- `failed`：事件失敗；請看 `event_failed.payload` 的 `failed_stage`、`error_code`、fallback 欄位。
- `duplicate_attempts`：同一 `event_id` 的後續 duplicate 次數，不會覆蓋 `completed` 或 `failed`。
- `command_result`：最後一筆 robot command result 狀態。
- `late_result`：command result 在 terminal event record 後才到達。

Retention / cleanup 建議：

- 正常 Demo 使用 summary mode：`DEBUG_TRACE_FULL=false`。
- `DEBUG_TRACE_FULL=true` 只用於短期本機 debug，因為可能保存 full prompt、full care_context、full raw Hermes output 與 raw inbound payload。
- 定期清理舊的 run folders 與過期 `LOG_DIR`；full debug log 不應長期累積。
- 含使用者語音、raw model output 或可識別路徑的 log，不得未去識別化就作長期 fixture。
- trace 不保存 raw image bytes；只保存 image paths、frame metadata 與 validation result。
