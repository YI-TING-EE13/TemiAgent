# Logs 模組 README

最後更新日期：2026-05-19

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
