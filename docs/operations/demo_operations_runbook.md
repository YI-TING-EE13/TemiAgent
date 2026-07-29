# AI6 Demo Operations Runbook

Status: maintained, Demo-only backend lifecycle. This compact runbook preserves the
expert command sequence; the authoritative newcomer procedure is the
[Demo 新手操作手冊](DEMO_OPERATOR_GUIDE.md), with a
[quick reference](DEMO_QUICK_REFERENCE.md).

## Safety contract

Run only inside the designated container and project root. The operator supplies
all environment-specific values through an ignored mode `0600` private config:

```bash
./scripts/demo --config <private-demo-config> doctor
```

The tool may start or reuse only its reviewed services. It records exact PID,
start time, cwd, executable, and command line before stopping an owned process.
It preserves a pre-existing LM Studio service and an explicitly configured
`reviewed_external` Broker. It never adopts an unknown listener, uses no broad
process pattern, and publishes no Demo MQTT event.

## Beginner lifecycle

```bash
./scripts/demo --config <private-demo-config> deploy
./scripts/demo --config <private-demo-config> deploy --backend-only
./scripts/demo --config <private-demo-config> status
./scripts/demo --config <private-demo-config> trace-export
./scripts/demo --config <private-demo-config> stop
```

The first command runs `preflight`, `up`, backend health, and a bounded fresh
Android live-evidence wait. It emits `DEMO_READY` only after every full gate
passes. `deploy --backend-only` emits only `BACKEND_READY_WAITING_ANDROID`.
`stop` is idempotent and emits `DEMO_STOPPED`; it stops only current-run owned
processes.

## Android gates

The static canonical artifact evidence validates immutable delivery information:
APK checksum, exact canonical text fingerprint, endpoint, robot ID, and canonical
topic contract. Its timestamp is not a runtime freshness check. A complete
`DEMO_READY` also requires the private Android branch/HEAD pin to match static
artifact metadata.

The separate live evidence path must be owner-only and fresh. It proves current
connection, subscriptions active, `unknown` identity, null Media session, empty
Media/Care outboxes, zero fatal count, and zero
`RejectedExecutionException` count. Static evidence can never substitute for
live evidence.

## Expert commands

```bash
./scripts/demo --config <private-demo-config> preflight
./scripts/demo --config <private-demo-config> up --dry-run
./scripts/demo --config <private-demo-config> up
./scripts/demo --config <private-demo-config> ready
./scripts/demo --config <private-demo-config> ready --require-android
./scripts/demo --config <private-demo-config> down --dry-run
./scripts/demo --config <private-demo-config> down
./scripts/demo --config <private-demo-config> reset
```

`ready` may return `BACKEND_READY_WAITING_ANDROID` for a healthy backend while
the Android gates are incomplete. `ready --require-android` exits nonzero unless
the state is `DEMO_READY`. `reset --publish-unknown` remains fail-closed because
there is no reviewed Bridge IPC for that publish operation.

## Recovery evidence

Use `doctor` before any manual intervention. It is read-only and reports
`PASS`／`PENDING`／`WARNING`／`FAIL` with suggested recovery. For a stale PID,
unknown listener, failed rollback, or retained external service, follow
[safe service operations](safe_service_operations.md); do not delete ownership
records or use broad process-kill commands.

Hardware, Android runtime export, GPU service availability, and external Broker
supervisor checks remain environment-dependent. Do not claim full Demo acceptance
from backend-only evidence.
