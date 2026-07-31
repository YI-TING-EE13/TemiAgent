# AI6 Demo Operations Runbook

Status: retained expert reference, Demo-only. This compact runbook preserves
historical expert terminology and Android-evidence background. The authoritative
current procedure is the [Demo 新手操作手冊](DEMO_OPERATOR_GUIDE.md), with the
[configuration reference](demo_configuration_reference.md) and
[quick reference](DEMO_QUICK_REFERENCE.md). Do not use this document as a
second lifecycle contract.

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

## Current operator lifecycle

```bash
./scripts/demo --config <private-demo-config> doctor
./scripts/demo --config <private-demo-config> start
./scripts/demo --config <private-demo-config> status
./scripts/demo --config <private-demo-config> trace-export
./scripts/demo --config <private-demo-config> stop
```

Use `doctor` before `start`. `start` emits `DEMO_READY` only after all backend
health gates and a fresh remote Android MQTT session are observed; otherwise a
healthy backend is `BACKEND_READY_WAITING_ANDROID`. `stop` is idempotent and
emits `DEMO_STOPPED`; it stops only current-run owned processes. `deploy` is a
compatibility alias retained for historical evidence, not a current instruction.

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

## Historical expert aliases

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

These aliases remain for compatibility with historical evidence. Do not create
new operational procedures from them. `reset --publish-unknown` remains
fail-closed because there is no reviewed Bridge IPC for that publish operation.

## Recovery evidence

Use `doctor` before any manual intervention. It is read-only and reports
`PASS`／`PENDING`／`WARNING`／`FAIL` with suggested recovery. For a stale PID,
unknown listener, failed rollback, or retained external service, follow
[safe service operations](safe_service_operations.md); do not delete ownership
records or use broad process-kill commands.

Hardware, Android runtime export, GPU service availability, and external Broker
supervisor checks remain environment-dependent. Do not claim full Demo acceptance
from backend-only evidence.
