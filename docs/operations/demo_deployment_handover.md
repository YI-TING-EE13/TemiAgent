# Demo Deployment and Handover

Status: maintained, Demo-only. This document describes the canonical software
stack in `<TEMIAGENT_ROOT>` and does not authorize real care, emergency, or
Discord notification tests.

## Canonical source and bootstrap

Run every project operation in the designated container, from `/TemiAgent`.
The source bind mount must resolve to the approved canonical workspace.
`hermes-agent` remains an upstream checkout; the reviewed Temi overlay is
reconstructed from its public base plus tracked patches before any Demo service
starts.

```bash
cd /TemiAgent
# Required external-source reconstruction for a clean clone; no dependency install.
./scripts/bootstrap --sources
# Run only after the documented Hermes and module environments exist:
./scripts/bootstrap --check
# Only when dependency environments need repair:
./scripts/bootstrap --sync
```

`--sources` is the clean-clone source-reconstruction step. It initializes the
independent Hermes checkout, fetches its public upstream base, verifies the
tracked patch SHA-256 values, creates the local-only `temiagent/integration`
branch, and verifies the expected tree hash. It also reconstructs the optional
llama.cpp checkout at the exact public upstream commit recorded in
[`third_party/llama_cpp/manifest.json`](../../third_party/llama_cpp/manifest.json).
It starts no service, installs no dependency, downloads no model, and does not
build `llama-server`. `--hermes` and `--llama-cpp` remain focused source-only
commands. `--check` makes no credentials, starts no service, and changes no
runtime state, but it is a readiness gate that requires the documented Hermes
and module environments to already exist. `--sync` uses each existing project's
`uv sync --frozen`; it does not update lockfiles. Both generated checkouts are
ignored external dependencies; reproducibility is defined by their tracked
manifests and the Hermes patch series, not by an unmapped gitlink.

## Private configuration and runtime data

Run `./scripts/demo init-config` to create the ignored owner-only canonical
config `/TemiAgent/.runtime/demo/demo.env` and its runtime root. The default
is the local `newcomer_mock` profile; it requires no Discord credential and its
notification test double never contacts a real endpoint. Production is an
explicit `init-config --profile production --force` choice.

All mutable state must live below `TEMIAGENT_RUNTIME_ROOT`, outside the source
tree or in an explicitly ignored runtime root. The lifecycle creates these
owner-only areas:

```text
<runtime-root>/
  data/{care-memory,shared}/
  logs/{lmstudio,mqtt,asr,hermes,bridge,gateway,trace}/
  state/{ownership,last-run,android-evidence}/
  tmp/sockets/
```

`memory/`, `logs/`, `temi_shared/`, models, recordings, PID files, and private
env files are runtime data. They must not be committed. Existing runtime data
must be copied or backed up before changing its configured root; never delete a
temporary root merely because the new configuration no longer uses it.

## Ownership and lifecycle

Each service has an explicit ownership mode in the private config:

| Service | Default formal profile | Start/stop owner | Health evidence |
|---|---|---|---|
| LM Studio | managed | lifecycle-owned LM Studio supervisor → existing startup script | `/v1/models`, `lms ps`, model context and exact supervisor PID identity |
| MQTT | managed | lifecycle-owned Mosquitto supervisor | one listener, TCP probe and revalidated exact supervisor PID identity |
| Overview adapter | managed | lifecycle | ports 8080 and 8081 |
| Resident Hermes | managed | lifecycle | `GET /health` |
| HermesTemiBridge | managed | lifecycle | process identity and callback sockets |
| Hermes gateway | managed | lifecycle | `hermes gateway status` |
| Action viewer | managed when enabled | lifecycle | viewer `/health` source/llama readiness plus five redacted component objects |
| Temi Android App | external | Android owner | configured device/contract evidence |

`external` means lifecycle only verifies health and never stops the service.
`disabled` applies only to optional services such as the gateway. The standard
software-only profile keeps `MANAGE_ANDROID=0`; ordinary `start` never starts
recording, hardware activity, test abnormal events, or Discord delivery.
The managed broker keeps Mosquitto's normal privilege-drop behavior. A small
lifecycle-owned supervisor remains as the recorded root process, relays TERM
only to its direct broker child, and waits for the listener to close. This
preserves exact lifecycle ownership without running the broker itself as root.
LM Studio is similarly managed by a persistent lifecycle-owned supervisor: the
existing startup script performs its reviewed model load, then the supervisor
remains as the exact recorded PID until shutdown. It invokes the approved `lms`
unload/server/daemon sequence; it does not alter model, GPU or context policy.

```bash
./scripts/demo --config <PRIVATE_CONFIG_PATH> doctor
./scripts/demo --config <PRIVATE_CONFIG_PATH> start
./scripts/demo --config <PRIVATE_CONFIG_PATH> status
./scripts/demo --config <PRIVATE_CONFIG_PATH> restart
./scripts/demo --config <PRIVATE_CONFIG_PATH> stop
```

The start order is LM Studio, MQTT, adapter, resident, Bridge, gateway, viewer.
The stop order is the reverse: viewer, gateway, Bridge, resident, adapter,
MQTT, LM Studio. The lifecycle uses an owner-only `flock` and records every
managed process's PID, start ticks, cwd, executable, command digest, config
digest, log path, timestamp, and run ID. A stop operation targets only a
recorded identity; it never uses `pkill` or `killall`.

The lifecycle creates and atomically persists the run as `STARTING` before it
waits for a service health gate. Every persisted service record contains the
verified start identity, command fingerprint, timestamp, and supervisor
identity where applicable. A successful run becomes `HEALTHY`. On a health or
start failure, the lifecycle persists `UNHEALTHY`, stops only the recorded
services in reverse order, records each rollback outcome, and leaves
`START_FAILED` when all recorded stops succeed. If any rollback stop fails, it
leaves `UNHEALTHY` for exact-owner recovery. `status` reports the persisted
lifecycle state rather than claiming backend readiness from listeners alone.

When no ownership state exists but a managed-like process matches a lifecycle
service, `stop` returns `STOP_INCOMPLETE_OWNERSHIP` with non-zero exit status
and sends no signal. An operator must retain the evidence and inspect the
exact PID before an authorized recovery action.

The lifecycle emits JSON service results. It uses stable failure codes including
`CONFIG_INVALID`, `LOCK_BUSY`, `PORT_IN_USE_EXTERNAL`, `MODEL_LOAD_FAILED`,
`MODEL_CONTEXT_MISMATCH`, `GPU_POLICY_MISMATCH`, `BROKER_START_FAILED`,
`GATEWAY_START_FAILED`, `SERVICE_HEALTH_FAILED`, `PID_IDENTITY_MISMATCH`,
`STOP_INCOMPLETE_OWNERSHIP`, and `STOP_TIMEOUT`.

## Newcomer software-only profile

`config/demo.mock.env.example` is the tracked non-secret template for the
formal `DEMO_PROFILE=newcomer_mock` acceptance. The default `init-config`
materializes it as ignored mode `0600` `/TemiAgent/.runtime/demo/demo.env` and
creates its paired owner-only runtime root. The profile uses one resolved
`DemoConfig` and the canonical lifecycle, not a test-specific service manager.

| Service role | Production default | Newcomer mock replacement |
|---|---|---|
| LM/model endpoint | LM Studio on `1234` | Loopback model-list double on `29134`. |
| MQTT | Broker on `1883` | Lifecycle-owned loopback Mosquitto on `29183`. |
| Adapter/resident/viewer | `8080/8081`, `8765`, `8010/8011` | `29080/29081`, `29765`, `29010/29011`. |
| Android and Discord | External Android; best-effort external side channel | Local health/contract doubles on `29012` and `29013`; no real endpoint is contacted. |

The mock resident can return a structured plan but cannot publish MQTT. The
Bridge remains the validation and dispatch boundary, and the mock Android
executor is only a canonical command-result consumer. `start`, idempotent
`start`, `doctor`, `status`, `restart`, and `stop` retain the same lock,
service-spec, health and exact-PID rules. The explicit sample disables only
the production branch-name requirement so a detached disposable clone is
testable; it does not permit a dirty source, a validator bypass, or an
unrecorded service.

Use the exact fresh-clone sequence in the
[verification guide](verification_and_acceptance.md#software-only-newcomer-acceptance).
It creates runtime evidence under `/tmp`, including scenario summary,
pre-restart ownership evidence, and final stop evidence. Mock success is never
evidence of real Temi execution, GPU/model operation, camera behavior, or
Discord delivery.

## Required configuration groups

`config/demo.env.example` is the complete non-secret key list. Configure the
following groups together:

| Group | Keys and invariant |
|---|---|
| Runtime paths | `TEMIAGENT_RUNTIME_ROOT`, log, memory, shared, callback, and identity paths remain under the runtime root. |
| LM Studio | model `temi/gemma-4-31b-it-qat`, API identifier `google/gemma-4-31b`, context `64000`, GPUs `0,1`, port `1234`. |
| Hermes | HTTP resident endpoint, media flags, callback sockets, and canonical nested pin. |
| MQTT | broker endpoint, port, config path, robot allowlist, and ownership. |
| Gateway | `HERMES_GATEWAY_ENABLED` and ownership agree. |
| Viewer | local model paths, CUDA/pose settings, and the abnormal publication flag. The Viewer does not read or send Discord credentials. |
| Android | `MANAGE_ANDROID=0` unless a separate Android owner authorizes lifecycle control. |

The resident validates the active and compression contexts as `64000` before
accepting the Demo. Hermes's pinned compressor derives its threshold from the
active context at `0.50`, therefore the verified threshold is `32000`. This is
documented behavior, not a license to change the percentage without a reviewed
model-policy decision.

## Resource manifest and media boundary

`config/demo_resources.json` records logical required resources. The only
currently allowlisted generic video is `elderly_hand_exercise`. It is a logical
ID: Hermes and the Bridge never receive a media URL, filesystem path, Android
intent, or media bytes. The Android App owns the final deployed asset mapping.
Bridge tests verify the allowlist and command contract; a device-owner must
separately verify the actual Android asset after an App deployment.

The abnormal route is immediate-alert and care-first: detector event → Bridge
validation → Bridge notification-stage attempt → Resident Hermes supportive
TTS → canonical command request/result → reply or timeout follow-up. The
first notification does not wait for resident consent. Viewer pre-alert TTS
does not bypass Bridge. Discord is best-effort only; gateway health or webhook
configuration never proves delivery and is not an emergency service.

## Abnormal-care handover boundary

The Bridge persists each abnormal-care episode in
`MEMORY_DIR/abnormal_care_episodes.json`. The state contains identifiers,
monotonic deadlines, transitions, and redacted stage receipts; it does not
contain webhook URLs, credentials, raw ASR, or evidence images. Preserve that
file when handing over an active Demo issue because it prevents an initial
notification from being replayed after a restart.

The Bridge owns three notification stages: `initial_alert`, `status_update`,
and `escalation`. A real Discord receipt is `delivered` only for HTTP 204. A
Demo-only mock receipt is `mock_delivered` only when both Demo mock flags are
enabled. Any other result prohibits the care dialogue from claiming a
notification succeeded.

Before an authorized Demo run, the operator MUST verify
`ABNORMAL_NOTIFICATION_MODE`, the two Demo mock flags or the owner-only real
credential file, timeout values, test-ingress flag, and test-resident
allowlist. Use `scripts/inject_demo_event` for synthetic abnormal events; do
not substitute a raw command request or Android result. Stop the lifecycle
through `scripts/demo` after collecting the Bridge trace, stage receipts,
command/result evidence, and final port inventory.

## Recovery and limits

If `doctor`, `status`, or `stop` reports an unknown listener, stale callback,
or identity mismatch, preserve evidence and stop. Inspect the exact PID, cwd,
executable, command line, parent, and listener before any manual signal. Use
the service-specific manager first, signal only the verified PID, then verify
dependent services and ports. Do not delete stale runtime roots or reset the
Git tree to recover a Demo.

`START_FAILED` and `UNHEALTHY` are retained recovery states, not stale files.
`STOP_INCOMPLETE_OWNERSHIP` means no signal was sent. Both conditions require
the exact lifecycle-state and PID evidence before a separately authorized
recovery operation.

The acceptance bundle is runtime evidence, not source. It should contain
masked configuration inventories, process/port snapshots, memory hashes,
lifecycle results, and test logs with mode `0600`. Retain it under the local
runtime policy; do not attach raw care records, images, recordings, webhooks,
or credentials to a public handover.
