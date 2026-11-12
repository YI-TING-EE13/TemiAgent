# Benchmark 執行方式

最後更新日期：2026-11-11。

以下假設已在專案根目錄、使用既有 Bridge Python 環境，且相關服務已啟動。
Live 測試可能讓 Temi 說話及寫入記憶；請只在已授權的測試環境執行。

## Action 一致性測試

先設定好 `PC_IP`（目前 broker 位址）、`SHARED_ROOT`（Bridge 的 shared 路徑）、
`MEMORY_ROOT`（Bridge 實際使用的記憶目錄）。

執行全部 23 筆：

```bash
python3 tools/benchmarks/test_action_selection.py \
  --live --broker "$PC_IP" --port 1883 \
  --robot-id temi-01 \
  --shared-root "$SHARED_ROOT" --bridge-root "$SHARED_ROOT" \
  --timeout 180 \
  --cleanup-memory-after-case --memory-root "$MEMORY_ROOT"
```

- 只跑一筆：在指令後加 `--case BP-01`。
- 不呼叫模型、只列出測資：執行下列離線指令。
- 結果直接顯示於終端，包含回答、action、一致性判定與清理狀態。

```bash
python3 tools/benchmarks/test_action_selection.py --offline
```

## Reasoning 速度與回答測試

沿用上述三個變數，另設定目前的 `RESIDENT_PID`、`BRIDGE_PID`，
以及 `BRIDGE_LOG_DIR`（Bridge 的 trace 目錄）。需關閉對話 Context 原型與照護記憶檢索。

執行一次暖機及全部 23 筆正式測試：

```bash
python3 tools/benchmarks/test_reasoning.py \
  --live --broker "$PC_IP" --port 1883 \
  --robot-id temi-01 \
  --resident-pid "$RESIDENT_PID" --bridge-pid "$BRIDGE_PID" \
  --resident-url http://127.0.0.1:8765 \
  --trace-dir "$BRIDGE_LOG_DIR" \
  --shared-root "$SHARED_ROOT" --bridge-root "$SHARED_ROOT" \
  --timeout 180 --warmup 1 --repeat 1 \
  --cleanup-memory-after-case --memory-root "$MEMORY_ROOT"
```

- 只跑一筆：在指令後加 `--case BP-01`；仍會先暖機一次。
- 模型、context 與 effort 會自動辨識，不需手填。
- 測另一個 effort：透過既有啟動流程變更設定，更新 PID 後重跑；本工具不修改 effort 或切換模型。
- 終端顯示的 `EVIDENCE_ROOT` 是本次結果目錄；用 `results.csv` 看逐筆回答與耗時，
  用 `summary.md` 看統計，`metadata.json` 則記錄實際實驗設定。
- 不呼叫模型、只列出測資：

```bash
python3 tools/benchmarks/test_reasoning.py --offline
```

兩組範例使用 broker 1883、robot ID `temi-01`，速度測試使用 Resident 8765；
若環境不同，請替換成實際值。範例啟用本次事件的記憶備份與精準清理，不會清空整個記憶目錄。
