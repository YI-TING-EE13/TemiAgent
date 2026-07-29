# TemiAgent Demo 快速參考

完整說明請看 [Demo 新手操作手冊](DEMO_OPERATOR_GUIDE.md)。所有 `<...>` 都是 operator
自行提供的 placeholder；不要把真實 endpoint、path、hash 或 account 寫入 tracked file。

## 最短流程

```bash
docker exec -it <designated-container> bash
cd <project-root>
./scripts/demo --config <private-demo-config> doctor
./scripts/demo --config <private-demo-config> deploy
./scripts/demo --config <private-demo-config> status
./scripts/demo --config <private-demo-config> stop
```

`deploy` 成功時 human output 只有 `DEMO_READY`。沒有 fresh Android runtime evidence 時，
不要重複期待 `DEMO_READY`；改用：

```bash
./scripts/demo --config <private-demo-config> deploy --backend-only
```

成功時是 `BACKEND_READY_WAITING_ANDROID`。

## 每個指令

| Command | What it does | Safe result |
|---|---|---|
| `doctor` | 唯讀診斷 source、config、artifact、live evidence、service、Care、port 與 PID。 | `PASS`／`PENDING`／`WARNING`／`FAIL` 加 recovery。 |
| `deploy` | `preflight` → `up` → health → bounded Android live gate。 | 僅完整成功時 `DEMO_READY`。 |
| `deploy --backend-only` | backend lifecycle，但不要求 Android ready。 | `BACKEND_READY_WAITING_ANDROID`。 |
| `status` | 唯讀 ownership／health／artifact／live summary。 | 不輸出 private host 或 path。 |
| `trace-export` | 匯出既有 de-identified trace summary。 | 不發布 MQTT event。 |
| `stop` | 停止 active run 的 owned process。 | `DEMO_STOPPED`；external services preserved。 |
| `preflight`、`up`、`ready`、`down`、`reset` | 保留的 low-level expert commands。 | 依各自 JSON／state。 |

JSON output：

```bash
./scripts/demo --config <private-demo-config> --json doctor
./scripts/demo --config <private-demo-config> --json deploy
```

## Android evidence 一句話

- static canonical artifact：驗證 APK、exact canonical text、fingerprint、endpoint／robot／topic
  contract；其 `observed_at` 不決定 freshness。
- live runtime evidence：每個 `deploy`／`ready` 都必須是新 snapshot，驗證 connected、實際
  subscriptions active、identity `unknown`、null media session、兩個空 outbox、fatal `0` 與
  `RejectedExecutionException` count `0`。
- `canonical.normalized.subscriptions` 是 canonical endpoint topic contract，不是 Paho
  subscribe 清單。
- branch／HEAD 需在 private config pin，才可作完整 `DEMO_READY` claim。

## 失敗時先做什麼

| Output | First action |
|---|---|
| `NOT_READY` | 執行 `doctor`，只處理列出的 `FAIL`／`PENDING`。 |
| Android live `PENDING` | 由 Android 匯出 fresh owner-only runtime snapshot。 |
| Android live `FAIL` | 修正 schema／fingerprint／contract；不要重用 static JSON。 |
| Broker／PID `FAIL` | 不要 broad-kill；確認 selected ownership mode。 |
| Care permission `FAIL` | 修正 private parent `0700` 與 store `0600`。 |
| `DEMO_STOPPED` | 確認 owned listener 消失；外部 LM Studio／Broker 留在原狀是正確結果。 |

遇到 stale PID、unknown listener 或 rollback 異常時，依
[safe service operations](safe_service_operations.md) 做 exact-PID investigation。
