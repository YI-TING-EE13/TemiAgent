# TemiAgent Demo 新手操作手冊

狀態：Demo-only。此手冊只操作既有 `./scripts/demo` lifecycle，不建立平行
launcher、不發布 Demo MQTT event，也不改變 Android、Bridge、Hermes、ASR、Care
schema 或 feature defaults。

## 先看結論

完整 Demo 的唯一新手指令是：

```bash
./scripts/demo deploy
```

只有在 backend、static Android artifact 與 fresh Android runtime evidence 全部
通過時，它才會在成功的 human output 中只印出：

```text
DEMO_READY
```

若 Android 尚未可用，改用：

```bash
./scripts/demo deploy --backend-only
```

成功時固定印出：

```text
BACKEND_READY_WAITING_ANDROID
```

它不會把 backend-only 狀態寫成 `DEMO_READY`。

## 安全邊界與 ownership

在指定 container 的 project root 中執行所有命令。以下是可攜的 placeholder：

```bash
docker exec -it <designated-container> bash
cd <project-root>
```

| Component | Port | Lifecycle owner | `stop` 行為 |
|---|---:|---|---|
| LM Studio | `1234` | 既有 model service 或本輪 tool-owned record | 只停止本輪 exact-PID record；保留既有 service。 |
| MQTT Broker | `1883` | `tool_owned` 或顯式 `reviewed_external` | 外部 Broker 永遠是 `preserved_external`。 |
| Overview ASR adapter | `8080`, `8081` | 本輪 Demo | exact PID、start time、cwd、executable、command line 驗證後停止。 |
| resident Hermes | `8765` | 本輪 Demo | exact-PID stop。 |
| Bridge 與 canonical trace writer | 無對外 HTTP port | 本輪 Demo | exact-PID stop；保留 trace evidence。 |
| Care Memory v2 | SQLite store | 私有 runtime store | `reset`／`seed`／`verify` 使用既有 v2 tool，不改 schema。 |

禁止使用 `pkill`、`killall` 或名稱比對停止服務。`./scripts/demo stop` 與
`./scripts/demo down` 只處理 active run 中可證明 ownership 的 service。

## 第一次設定

先複製 template 到 repository 外的 ignored private config，並限制為 owner-only：

```bash
cp config/demo.env.example <private-demo-config>
chmod 0600 <private-demo-config>
```

之後每次使用相同 config：

```bash
./scripts/demo --config <private-demo-config> doctor
```

至少填入以下群組；所有真實 endpoint、artifact 路徑、hash、manager identifier
都只能留在 private config。

| Group | Required purpose |
|---|---|
| Backend baseline | `DEMO_EXPECTED_BACKEND_COMMIT`。 |
| Broker contract | Host、port、robot ID；若是外部 supervisor，明確設為 `reviewed_external`、manager 與 endpoint fingerprint。 |
| LM Studio | 固定 model、API identifier、context `64000`、GPU `0,1`、空 fallback。 |
| Static Android artifact | APK path／SHA-256、canonical evidence path／fingerprint。 |
| Android source pin | `DEMO_ANDROID_ARTIFACT_BRANCH` 與 `DEMO_ANDROID_ARTIFACT_HEAD` 必須成對填入，才能作出完整 `DEMO_READY` claim。 |
| Live Android evidence | 不同於 static evidence 的 `DEMO_ANDROID_LIVE_EVIDENCE_PATH`，以及 `DEMO_ANDROID_LIVE_EVIDENCE_MAX_AGE_SECONDS`。 |
| Runtime／Care | repository 外、owner-only 的 runtime root 與 Care store。 |

`DEMO_BROKER_MODE=reviewed_external` 只能用在已由人工審查的外部 Broker。它
不會自動接管、不會建立第二個 Broker，也不會在 `stop` 時停止它。

## Android evidence：兩份資料、兩種責任

### Static artifact evidence

`DEMO_ANDROID_CANONICAL_EVIDENCE_PATH` 是可長期保存的 artifact contract。parser
驗證 exact canonical UTF-8 text 的 SHA-256、normalized endpoint／robot／canonical
topic contract 與 APK SHA-256。它不使用 `observed_at` 判定 freshness；舊 timestamp
本身不會使 artifact 失效。

若 private config pin branch／HEAD，static evidence 的 `metadata.android_branch` 與
`metadata.android_head` 必須完全相符。branch、HEAD、APK hash、endpoint、robot ID、
canonical text、fingerprint 或 topic contract 任一變更時，需重新交付並驗證 artifact。

`canonical.normalized.subscriptions` 的五個值是 **canonical endpoint topic
contract**，不是 Android Paho 實際 subscribe 清單；其中可包含 publish destination。
實際 Paho subscription 是否 active 由下一節的 live evidence 表達。

最小 static JSON 的欄位名稱如下。`metadata` 可有其他 handoff metadata；parser 不把
未列出的 metadata 當成 runtime readiness 欄位。

```json
{
  "schema_version": "1.0",
  "observed_at": "<artifact-export-time-with-offset>",
  "canonical": {
    "text": "<exact-Android-canonical-UTF-8-text>",
    "fingerprint_sha256": "<sha256-of-exact-text>",
    "normalized": {
      "mqtt_host": "<private-config-host>",
      "mqtt_port": 1883,
      "robot_id": "<robot-id>",
      "subscriptions": [
        "temi/<robot-id>/cmd/request",
        "temi/<robot-id>/cmd/result",
        "temi/<robot-id>/resident/identity/result",
        "temi/<robot-id>/care/report",
        "temi/<robot-id>/care/report/interaction/result"
      ]
    }
  },
  "metadata": {
    "android_branch": "<Android-branch>",
    "android_head": "<40-character-Android-Git-commit>",
    "apk_sha256": "<APK-SHA-256>"
  }
}
```

### Fresh Android runtime evidence

每一次 `deploy` 與 `ready` 都會嘗試讀取另一份 owner-only live snapshot。它必須是
Android 在目前 runtime 產生的資料，不能指向或複製 static evidence，也不能以舊的
dynamic fields 宣稱 ready。檔案必須是 mode `0600`，且 `observed_at` 必須在 private
config 的 bounded age 內。

最小 live JSON schema 是：

```json
{
  "schema_version": "demo_operations.android_runtime.v1",
  "observed_at": "<current-UTC-ISO-8601-with-offset>",
  "canonical": {
    "fingerprint_sha256": "<same-canonical-fingerprint>",
    "normalized": {
      "mqtt_host": "<private-config-host>",
      "mqtt_port": 1883,
      "robot_id": "<robot-id>",
      "subscriptions": [
        "temi/<robot-id>/cmd/request",
        "temi/<robot-id>/cmd/result",
        "temi/<robot-id>/resident/identity/result",
        "temi/<robot-id>/care/report",
        "temi/<robot-id>/care/report/interaction/result"
      ]
    }
  },
  "connection": {
    "connected": true,
    "subscriptions_active": true
  },
  "state": {
    "identity": "unknown",
    "media_active_session": null,
    "media_outbox": 0,
    "care_outbox": 0
  },
  "runtime": {
    "fatal_count": 0,
    "rejected_execution_exception_count": 0
  }
}
```

`DEMO_READY` 需要所有 live fields 都符合上例。`subscriptions_active` 是 Android
runtime 對實際 Paho subscription 的 boolean observation；它不改寫 canonical topic
contract，也不推測未交付的 Android state。

## 標準操作流程

### 1. 先診斷，不改動任何服務

```bash
./scripts/demo --config <private-demo-config> doctor
```

`doctor` 是 read-only：不建立 runtime directory、不 seed Care store、不啟停 service。
它列出 `PASS`、`PENDING`、`WARNING`、`FAIL`，並為每一項附上 recovery action。它會檢查
source、private config mode、Android artifact、live evidence、LM Studio、Broker、Hermes、
ASR、Bridge、Care、ports、PID ownership 與 latest runtime error，同時 redacts private
endpoint 與 path。

### 2. 完整 Demo deploy

```bash
./scripts/demo --config <private-demo-config> deploy
```

順序是 `preflight`、`up`、backend health，再等待 bounded 的 fresh Android runtime
evidence。重複執行會重用同一個 healthy run，不建立重複服務或第二個 Demo MQTT client。
如果本輪新啟動的 run 因 Android live gate timeout 失敗，工具會 rollback 本輪 owned
process；pre-existing external LM Studio／Broker 保持不變。

### 3. Backend-only 準備

```bash
./scripts/demo --config <private-demo-config> deploy --backend-only
```

這條路徑仍會取得 live evidence 的目前診斷，但不要求它通過。成功只能是
`BACKEND_READY_WAITING_ANDROID`。

### 4. 查看與匯出

```bash
./scripts/demo --config <private-demo-config> status
./scripts/demo --config <private-demo-config> trace-export
```

`status` 顯示 run、service ownership、health、port、artifact／live evidence 摘要與 latest
error；不顯示 private host、path、canonical text 或 credential。`trace-export` 只輸出既有
de-identified trace summary，不發布 MQTT event。

### 5. 安全停止

```bash
./scripts/demo --config <private-demo-config> stop
```

`stop` 是新手版 `down`。已停止時仍為成功且輸出 `DEMO_STOPPED`。它保留外部 LM Studio
與 `preserved_external` Broker，不偽造 PID ownership。

## 完整 command reference

| Command | Purpose | Expected successful state |
|---|---|---|
| `./scripts/demo deploy` | 完整 bounded lifecycle 與 Android live gate。 | `DEMO_READY` |
| `./scripts/demo deploy --backend-only` | 啟動 backend，不要求 Android live gate。 | `BACKEND_READY_WAITING_ANDROID` |
| `./scripts/demo doctor` | 唯讀診斷與 recovery 建議。 | 可能有 `PENDING`／`WARNING`；`FAIL` exit nonzero。 |
| `./scripts/demo stop` | 新手安全停止。 | `DEMO_STOPPED` |
| `./scripts/demo preflight` | 列出靜態與 runtime prerequisites。 | 無 `FAIL` 時 exit zero。 |
| `./scripts/demo up` | low-level backend start／reuse。 | backend state；不等同完整 Demo。 |
| `./scripts/demo ready` | 讀取 backend 與 fresh Android gate。 | `DEMO_READY` 或 `BACKEND_READY_WAITING_ANDROID` |
| `./scripts/demo ready --require-android` | 要求完整 Android live gate。 | 只有 `DEMO_READY` exit zero。 |
| `./scripts/demo status` | 唯讀 runtime snapshot。 | `down` 或 active state。 |
| `./scripts/demo trace-export` | 匯出 de-identified trace summary。 | JSON summary。 |
| `./scripts/demo down` | low-level exact-PID shutdown。 | JSON result。 |
| `./scripts/demo reset` | 既有 Care v2 reset／seed／verify flow。 | JSON result；不發布 `unknown`。 |

Machine-readable output 把 global flag 放在 command 前：

```bash
./scripts/demo --config <private-demo-config> --json doctor
./scripts/demo --config <private-demo-config> --json deploy
```

## Status 判讀

| State | Meaning | Operator action |
|---|---|---|
| `DEMO_READY` | backend 與 fresh Android runtime evidence 全通過。 | 可開始受控 Demo；保留 `status` 與 trace evidence。 |
| `BACKEND_READY_WAITING_ANDROID` | backend 健康，但 Android static 或 live gate 未完成。 | 匯出 fresh live evidence，或使用 backend-only 做非 Android 工作。 |
| `NOT_READY` | 前置條件、健康或 required Android gate 失敗。 | 先執行 `doctor`，依 recovery 修正後重跑。 |
| `BACKEND_NOT_RUNNING` | 沒有 active backend run。 | 使用 `deploy` 或 `deploy --backend-only`。 |
| `DEMO_STOPPED` | owned service 已停止或本來就停止。 | 確認 external service 仍 preserved。 |

## Troubleshooting

| Symptom | Meaning | Safe recovery |
|---|---|---|
| `source` 或 `git_clean` 為 `FAIL` | branch、baseline、root 或 nested repository 不符合。 | 先處理 source state；不要以 `deploy` 蓋過未提交改動。 |
| `private_config` 為 `FAIL` | config 非 owner-only 或欄位不完整。 | 修正 ignored config，設為 mode `0600`。 |
| `android_apk` 為 `FAIL` | APK 缺失、symlink 或 SHA-256 不符。 | 重新交付受審核 artifact；不要修改 tracked config。 |
| `android_artifact` 為 `WARNING` | static artifact 有效，但 branch／HEAD 未 pin。 | 在 private config 成對填入 source reference 後再做 full deploy。 |
| `android_live_runtime` 為 `PENDING` | 沒有 path、檔案不存在或 `observed_at` 過期。 | 由 Android 重新產生 owner-only live snapshot。 |
| `android_live_runtime` 為 `FAIL` | schema、fingerprint、endpoint contract 或 field type 不符。 | 修正 exporter；不要把 static JSON 當 live JSON。 |
| live state 不為 ready | disconnected、subscriptions inactive、identity 非 `unknown`、session／outbox 不為空、fatal 或 rejected count 非零。 | 先在 Android 完成清理並重新匯出 snapshot。 |
| LM Studio 為 `FAIL` | exact model、context、GPU limit 或 health 不符。 | 依既有 LM Studio runbook 人工恢復固定 model；不要改 model default。 |
| Broker 為 `FAIL` | tool-owned port 被占用，或 external contract 不可驗證。 | 找出真正 owner；external 模式必須顯式設定，且不接管未知 listener。 |
| ASR／Hermes／Bridge 為 `FAIL` | active run 的 health 或 exact process identity 不符。 | 使用 `stop` 後重新 `deploy`；不要 broad-kill。 |
| Care store 為 `FAIL` | parent 或 SQLite file mode／owner 不安全。 | 修復 owner-only parent `0700` 與 store `0600`，再用 lifecycle seed／verify。 |
| `deploy` timeout 後 `NOT_READY` | 本輪無法取得合格 live evidence。 | 確認 rollback 結果，重新匯出 live snapshot，再重試。 |
| `stop` 後 external service 還在 | 預期行為。 | 確認 state 為 `preserved_external`；不得手動宣稱它被 Demo 管理。 |

## Filming checklist

1. 在開始前保存 `doctor`、`deploy`、`status` 的 redacted output。
2. 只在 `deploy` human output 為 `DEMO_READY` 時開始完整 Android filming。
3. 確認 `status` 中的 Broker ownership 正確，外部 service 顯示 `preserved_external`。
4. 確認 Android live snapshot 的 connected、subscriptions、identity、session、outbox、fatal 與
   rejected count 全部符合 readiness。
5. 確認 Care verification 與 cross-resident isolation 已由 lifecycle 通過。
6. 不在拍攝中手動發送 Demo MQTT event；保留 trace-export 作為事後 de-identified evidence。
7. 結束後執行 `stop`，再確認 owned listeners 消失、外部 LM Studio／Broker 保持不變。

## 安全停止與恢復

正常結束只使用 `./scripts/demo stop`。若 `doctor` 顯示 stale PID 或 unknown listener，
不要刪除 runtime record 或猜測 process owner；依 `doctor` 的 recovery 指示與
[safe service operations](safe_service_operations.md) 進行 exact-PID investigation。下一次
Demo 前再次執行 `doctor`，確認 repository 與 nested checkout clean。
