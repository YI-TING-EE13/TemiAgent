# Safe Service Operations and Incident Evidence

最後審查日期：2026-08-31；D2B consolidated。

The current operator source is a clean clone of public `main`. The previous
public baseline was `8fead49d66ab0a9d016a7dfe495b336146bbe957`; the protected dirty
designated-container development mount is not a portable operator workspace.
The [Demo operator guide](DEMO_OPERATOR_GUIDE.md) owns the current
`doctor → start → status → stop` sequence; this policy owns exact identity,
rollback and containment rules.

This policy applies to TemiAgent startup, shutdown, restart, rollback, restore, retention and incident work. Module runbooks may add service-specific commands but MUST preserve these boundaries.

## Authorization Boundary

Documentation review and tests do not authorize service operations. Start, stop or restart a service only when the task explicitly includes that operation.

Before an authorized operation, record:

- designated container and `/TemiAgent` working directory;
- exact target service, port, expected command and executable;
- protected ports and dependent services;
- current health;
- expected outcome;
- rollback or disable path;
- required human approval.

Hardware control, personal/care data, permissions, secrets, network rules, model thresholds and automated notifications require explicit human confirmation.

## Exact PID and Port Procedure

Identify the listener without changing state:

```bash
ss -ltnp 'sport = :<port>'
```

Resolve the PID from the listener output, then verify the same PID:

```bash
ps -p <pid> -o pid,ppid,user,lstart,etime,args
readlink -f /proc/<pid>/cwd
readlink -f /proc/<pid>/exe
tr '\0' ' ' < /proc/<pid>/cmdline
```

Proceed only when port, command line, working directory and executable all match the authorized service. Prefer the owning module's stop/restart script or service manager.

For a manual stop:

```bash
kill -TERM <verified-pid>
```

Wait for a bounded interval and confirm the same PID and port state. Use `kill -KILL` only against that same previously verified PID when normal termination fails and the task authorizes escalation.

Never use:

```text
pkill -f <partial-command>
pkill python
killall python
killall <service-class>
```

## Current Port Map and Protected Dependencies

Use [contract_traceability.md](../architecture/contract_traceability.md) as the maintained port-owner map. Before changing one service, list the other active project ports that must remain unaffected.

Examples:

- An action-viewer operation on `8010` MUST preserve MQTT `1883`, video
  `8080`, frame broadcast `8081`, resident Hermes `8765` and Bridge processes.
- An LM Studio check on `1234` MUST be read-only and preserve MQTT, streaming,
  Bridge and viewer processes. Production LM Studio is external-only; do not
  start, stop, unload, restart or reconfigure it from the lifecycle.
- A Mosquitto operation on `1883` affects every event and command route. The
  validated AI6 broker is external/reused, so only read-only health checks are
  allowed there; managed broker transitions require explicit managed ownership
  and authorization.

## Startup and Health

Use the owning module README or maintained cross-module runbook. A successful process start is not sufficient evidence. Verify the advertised endpoint or protocol:

```bash
curl -fsS http://127.0.0.1:1234/v1/models
curl -fsS http://127.0.0.1:8765/health
curl -fsS http://127.0.0.1:8010/health
ss -ltnp 'sport = :1883'
ss -ltnp 'sport = :8080'
ss -ltnp 'sport = :8081'
```

Run only probes relevant to active, authorized services. A port listener does not prove end-to-end behavior; record real protocol or application evidence when required.

## Timeout, Retry and Degraded Mode

Every integration with a model service, broker, network, sensor, webhook or robot MUST define:

- a finite timeout;
- bounded retry and backoff;
- duplicate/idempotency behavior;
- queue limit or drop/backpressure behavior;
- fallback or explicit degraded mode;
- operator-visible error evidence.

Do not retry indefinitely. Do not convert stale perception or failed external notification into a successful care claim.

Current examples:

- Bridge bounds Hermes invocation with `HERMES_TIMEOUT_SECONDS`.
- Bridge deduplicates events with `EVENT_DEDUP_TTL_SECONDS`.
- Action viewer records MQTT and Discord failures independently.
- Discord delivery remains best-effort and MUST NOT be treated as emergency notification.

## Rollback and Restore

Before changing code or configuration, identify the prior Git state or exact configuration file and the verification needed after restoration. Do not use destructive Git cleanup to implement rollback in a dirty working tree.

For runtime configuration:

1. Save the prior non-secret values in an incident/change record.
2. Apply one bounded change.
3. Run focused health and dependency checks.
4. Restore the exact prior values when acceptance fails.
5. Verify the target and protected services after restoration.

A backup is not restore evidence. For persistent state or checkpoints, test restoration in a clean, isolated location when the task permits it. Record version compatibility, integrity checks and actual recovery gaps.

## Runtime Data, Retention and Cleanup

Runtime images, video, logs, caches, model output and care data MUST have an allowlisted root and bounded retention. Operators MUST NOT delete runtime evidence during an active incident.

Before cleanup:

1. Identify the exact allowlisted root.
2. Separate required incident evidence and reviewed fixtures.
3. Preview targets and counts.
4. Confirm retention and approval.
5. Delete only explicit targets.
6. Verify source files, permissions and protected artifacts afterward.

Do not commit runtime artifacts, real care data, private addresses or secrets. De-identify evidence before attaching it to reports.

## Incident Record

Record:

```text
incident_id:
start_time_utc:
environment:
affected service and users:
event_id / trace_id / run_id:
confirmed symptoms:
containment:
rollback or recovery:
post-recovery verification:
protected services checked:
evidence paths:
root cause:
contributing factors:
preventive work:
unverified gaps:
```

Contain impact before root-cause experiments:

```text
contain
-> disable, roll back or restore
-> verify recovery
-> investigate
-> add tests, logs and preventive controls
```

Do not claim recovery merely because a process restarted. Confirm the expected endpoint, protocol behavior and affected cross-module path.
