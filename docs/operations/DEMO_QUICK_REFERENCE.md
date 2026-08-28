# TemiAgent Demo 快速參考

狀態：CURRENT companion；完整 lifecycle 只以 [Demo 操作入口](DEMO_OPERATOR_GUIDE.md) 為準。
最後審查日期：2026-08-28

完整說明請看 [Demo 新手操作手冊](DEMO_OPERATOR_GUIDE.md)、
[設定參考](demo_configuration_reference.md)與
[troubleshooting](demo_troubleshooting.md)。所有 `<...>` 都是 operator 自行提供的
placeholder；不要把真實 endpoint、path、hash 或 account 寫入 tracked file。

新手的完整 clone/environment 順序見 [developer setup](developer_setup.md)，
責任拓撲見 [deployment handover](demo_deployment_handover.md)；本頁只是
companion，不是第二個 lifecycle authority。

## 最短流程

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
./scripts/demo --config <private-demo-config> doctor
./scripts/demo --config <private-demo-config> start
./scripts/demo --config <private-demo-config> status
./scripts/demo --config <private-demo-config> restart
./scripts/demo --config <private-demo-config> stop
```

`start` 成功後請以 `status` 判讀 readiness。沒有 fresh Android MQTT session 時，正確結果是
`BACKEND_READY_WAITING_ANDROID`，不是失敗；只有 backend healthy 且 broker 觀察到 fresh remote
Android session 時才是 `DEMO_READY`。

## 每個指令

| Command | What it does | Safe result |
|---|---|---|
| `doctor` | 唯讀診斷 source、config、artifact、live evidence、service、Care、port 與 PID。 | `PASS`／`PENDING`／`WARNING`／`FAIL` 加 recovery。 |
| `start` | 以 recorded ownership 啟動 managed services，並執行 health gates。 | `DEMO_READY` 或 `BACKEND_READY_WAITING_ANDROID`。 |
| `restart` | 先保存 pre-restart evidence，再只停止並重啟已驗證的 Demo processes。 | 同 `start`；不處理 unknown listener。 |
| `status` | 唯讀 ownership／health／artifact／live summary。 | 不輸出 credential；owner-only paths remain private。 |
| `trace-export` | 匯出既有 de-identified trace summary。 | 不發布 MQTT event。 |
| `stop` | 停止 active run 的 owned process。 | `DEMO_STOPPED`；external services preserved。 |
| `identity`、`seed`、`verify` | 已明確啟用的 synthetic identity/care Demo helper。 | 只在正式 guide 的 feature gates 都成立時使用。 |

Compatibility parser names and historical lifecycle terminology are documented only in the
[legacy operations reference](demo_operations_runbook.md); do not copy them into a current
operator command sequence.

JSON output：

```bash
./scripts/demo --config <private-demo-config> --json doctor
./scripts/demo --config <private-demo-config> --json start
```

## Android evidence 一句話

- static canonical artifact：驗證 APK、exact canonical text、fingerprint、endpoint／robot／topic
  contract；其 `observed_at` 不決定 freshness。
- live runtime evidence：每次授權的 `start`／`restart` 都必須是新 snapshot，驗證 connected、實際
  subscriptions active、identity `unknown`、null media session、兩個空 outbox、fatal `0` 與
  `RejectedExecutionException` count `0`。
- `canonical.normalized.subscriptions` 是 canonical endpoint topic contract，不是 Paho
  subscribe 清單。
- branch／HEAD 需在 private config pin，才可作完整 `DEMO_READY` claim；目前沒有 live claim。

## 失敗時先做什麼

| Output | First action |
|---|---|
| `BACKEND_NOT_READY` | 執行 `doctor`，只處理列出的 `FAIL`／`PENDING`。 |
| Android live `PENDING` | 由 Android 匯出 fresh owner-only runtime snapshot。 |
| Android live `FAIL` | 修正 schema／fingerprint／contract；不要重用 static JSON。 |
| Broker／PID `FAIL` | 不要 broad-kill；確認 selected ownership mode。 |
| Care permission `FAIL` | 修正 private parent `0700` 與 store `0600`。 |
| `DEMO_STOPPED` | 確認 owned listener 消失；外部 LM Studio／Broker 留在原狀是正確結果。 |

遇到 stale PID、unknown listener 或 rollback 異常時，依
[safe service operations](safe_service_operations.md) 做 exact-PID investigation。
