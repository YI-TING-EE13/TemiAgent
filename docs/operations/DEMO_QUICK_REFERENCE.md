# TemiAgent Demo 快速參考

狀態：`CURRENT_REFERENCE`；完整 lifecycle 只以
[Demo 操作入口](DEMO_OPERATOR_GUIDE.md) 為準。
最後審查日期：2026-08-31（D2B）。

本頁是 current operator guide 的 compact companion，不是第二個 lifecycle
authority。Portable operation starts from a clean clone of public `main` at
`8fead49d66ab0a9d016a7dfe495b336146bbe957`
(tree `e5fa932b01cc1f885cd36023464a18f11bdf060a`). The protected dirty
`/TemiAgent` mount and the observed
`/opt/TemiAgent-operator` deployment are not generic student workspaces.
The published root has no `LICENSE` file: `ROOT_LICENSE_POLICY=NO_LICENSE`.

## 最短 current flow

Provision the documented dependencies and private configuration first, then
run the following from the designated container. `<REPO_ROOT>` must identify
the clean public-main clone and `<PRIVATE_CONFIG>` must be an owner-only
private configuration file outside the worktree.

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
export REPO_ROOT=<clean-public-main-clone>
cd "$REPO_ROOT"
./scripts/bootstrap --check
./scripts/demo --config <PRIVATE_CONFIG> --json doctor
./scripts/demo --config <PRIVATE_CONFIG> start
./scripts/demo --config <PRIVATE_CONFIG> --json status
./scripts/demo --config <PRIVATE_CONFIG> stop
```

This is one bounded `start → status → stop` rehearsal. Do not retry a failed
operation or substitute a different PID, executable, worktree or dependency
source. Inspect the failure and follow the [safe service policy](safe_service_operations.md)
before any separately authorized recovery.

## 結果判讀

| Command | Meaning |
|---|---|
| `bootstrap --check` | Reconstructed source, locked environments, generated artifacts and required external prerequisites are ready. |
| `doctor` | Read-only machine-readable preflight. `PASS`, `WARNING`, `FAIL` and `SKIPPED` are the current check statuses. |
| `start` | Starts only positively owned managed services and waits for their health gates. |
| `status` | Read-only ownership and health summary. After start, `DEMO_READY` or `BACKEND_READY_WAITING_ANDROID` is valid. |
| `stop` | Stops only recorded managed identities and preserves external services. A clean stop reports no owned processes or orphan listeners. |

A pre-start doctor may return rc0 with `BACKEND_NOT_READY` and zero required
failures when a managed service is simply stopped or Android is not connected.
That does not mean `DEMO_READY`. Missing provisioned artifacts, invalid
configuration, malformed health, failed required readiness or an unowned
listener is a blocking `FAIL`. Do not operate Android or Temi to manufacture
`DEMO_READY`.

## Ownership and safety boundary

- Production LM Studio is `external` and must already be READY. The lifecycle
  checks its configured API/model identity and never invokes `lms`, starts,
  stops, unloads, restarts or reconfigures the provider.
- MQTT is either explicitly `managed` or explicitly `external`. The accepted
  AI6 deployment reused an external healthy broker; it was not adopted by
  port. Never stop or replace an external broker from this flow.
- Stop uses recorded exact-PID identity and fails closed on unknown listeners,
  stale state or identity mismatch. Never use `pkill`, `killall`, name-wide
  termination or port-only adoption.
- No model request, MQTT robot command, TTS, movement, navigation, media
  action, Android/ADB operation or external notification is part of this
  software-only rehearsal.

The operator guide records the AI6-only llama-server path/hash and the D2A
runtime-isolation evidence. Those observed values are acceptance evidence,
not portable defaults or permission to fall back to canonical dirty-worktree
artifacts.

## Failure first actions

| Output | First action |
|---|---|
| `BACKEND_NOT_READY` | Read the JSON doctor/status findings; fix only an explicitly authorized dependency or configuration issue. |
| Required `FAIL` | Preserve the named check and stop. Do not bypass it by changing source, ports, lockfiles or runtime ownership. |
| `BACKEND_READY_WAITING_ANDROID` | Treat the software backend as ready while Android remains an external boundary; do not issue device commands. |
| Unknown listener or stale PID | Capture exact PID, start identity, cwd and command line, then follow the safe service policy. |
| `DEMO_STOPPED` | Confirm owned processes/listeners are gone and LM/MQTT remain untouched. |

For feature-specific details, use the [configuration reference](demo_configuration_reference.md),
[troubleshooting](demo_troubleshooting.md), and [verification guide](verification_and_acceptance.md).
