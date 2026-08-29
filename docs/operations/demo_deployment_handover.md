# Demo Deployment and Handover

Status: <code>CURRENT_AUTHORITY</code>; Demo-only. Last reviewed for Gate 5 final
evidence and L4.3 Android provenance adoption: 2026-08-29. This document
describes the canonical software
stack in `<TEMIAGENT_ROOT>` and does not authorize real care, emergency, or
Discord notification tests.

Use [DEMO_OPERATOR_GUIDE.md](DEMO_OPERATOR_GUIDE.md) as the sole current
lifecycle authority. This handover explains source reconstruction, ownership and
deployment boundaries; its lifecycle snippets are supplemental and do not define
another command vocabulary.

## Canonical source and bootstrap

Run every project operation in the designated container, from `/TemiAgent`.
The source bind mount must resolve to the approved canonical workspace.
`hermes-agent` is the formal submodule pinned to the team-controlled Hermes
fork. The reviewed Temi overlay is reconstructed in that submodule worktree
from the pinned base plus the ten root-owned patches before any Demo service
starts.

```bash
cd /TemiAgent
# Required bounded submodule initialization for a clean clone.
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
# Required external-source reconstruction; no dependency install.
./scripts/bootstrap --sources
# Run only after the documented Hermes and module environments exist:
./scripts/bootstrap --check
# Only when dependency environments need repair:
./scripts/bootstrap --sync
```

`git submodule update --init --recursive` is the only Hermes source-acquisition
step. It must initialize `hermes-agent` from the team URL recorded in
`.gitmodules` and the root gitlink must resolve to the pinned base commit.
`--sources` then verifies the formal submodule, verifies the tracked patch
SHA-256 values, creates the local-only `temiagent/integration` branch, and
verifies the expected patched tree. It also reconstructs the optional llama.cpp
checkout at the exact public upstream commit recorded in
[`third_party/llama_cpp/manifest.json`](../../third_party/llama_cpp/manifest.json).
It starts no service, installs no dependency, downloads no model, and does not
build `llama-server`. `--hermes` and `--llama-cpp` remain focused source-only
commands. `--check` makes no credentials, starts no service, and changes no
runtime state, but it is a readiness gate that requires the documented Hermes
and module environments to already exist. `--sync` uses each existing project's
`uv sync --frozen`; it does not update lockfiles. The Hermes submodule remains
formally tracked at the base gitlink while its generated patched worktree is
local state; a post-bootstrap ` m hermes-agent` status line is expected. The
llama.cpp checkout remains ignored. If the team remote cannot be reached, retain
the submodule failure and stop; no original-upstream, local-checkout, file-URL,
cache or alternate-object fallback is allowed.

## Responsibility topology

| Boundary | Owns | Does not own |
|---|---|---|
| AI6 host | Docker engine, the designated container, source mount and host-level resource availability. | Bridge validation, MQTT payloads, Android execution or care decisions. |
| AI6 container | TemiAgent source, locked Python environments, lifecycle supervisors, MQTT broker, adapter, resident wrapper, Bridge, optional gateway and viewer. | The Android APK, physical robot motion, unprovisioned model bytes or external provider policy. |
| Temi robot / Android App | Device-side MQTT connection, command/result parser, allowlists, media asset mapping, player state and physical execution. | AI6 process ownership, Bridge validation source or AI6 private runtime state. |
| LAB606 development host | Human development/control surface and, where approved, the Docker invocation that enters the AI6 container. | A required product data path. LAB606 TCP-to-AI6-MQTT is not a product requirement. |
| External services and owners | Team Hermes remote, public llama.cpp source, LM Studio/model cache, optional Discord provider and Android source/device credentials. | A guarantee that an external service is reachable or that a published command was physically executed. |

The product path is Temi Android to the deployment-configured AI6 MQTT broker.
The AI6 client defaults remain loopback and the tracked broker configuration
does not contain a developer-specific private LAN address. A deployment-specific
endpoint belongs in the Android owner’s private configuration and must never be
copied into a tracked template.

## Service responsibility matrix (historical pre-Gate 5 baseline)

The command column names the canonical lifecycle entry, not a permission to
operate it during documentation work. The rows below preserve the pre-Gate 5
deployment snapshot; the accepted current host disposition is recorded in the
next section. A status of <code>LIVE_NOT_VERIFIED</code> remains valid for
boundaries not covered by the accepted host contract.

| Service | Runs on | Started by | Canonical command | Port / interface | Health check | Log location | Stop command | Dependencies | Current status |
|---|---|---|---|---|---|---|---|---|---|
| LM Studio | AI6 container, with external model/cache and GPU | External LM/runtime owner | <code>DO_NOT_START</code> from <code>scripts/demo</code>; provision separately | <code>127.0.0.1:1234</code> | One listener plus HTTP <code>/v1/models</code> containing the configured identifier; no CLI inventory | External owner’s private provider logs | <code>DO_NOT_STOP</code> from <code>scripts/demo</code> | External LM owner, configured model/cache and GPU/driver | <code>LIVE_NOT_VERIFIED</code>; Gate 5B.3 retained a backend-context mismatch and did not operate it. |
| Mosquitto MQTT broker | AI6 container | <code>scripts/demo start</code> or the MQTT-only selector | <code>./scripts/demo mqtt start</code> | Canonical broker config listener <code>0.0.0.0:1883</code> | <code>./scripts/demo --json mqtt status</code>: one listener, expected bind/port, TCP ready and valid supervisor/child lineage | <code>&lt;runtime-root&gt;/logs/mqtt/mosquitto.log</code> | <code>./scripts/demo mqtt stop</code> | Python supervisor, Mosquitto, tracked broker config and private ownership state | Canonical main snapshot <code>RUNNING/READY</code>; candidate not operated. |
| Overview adapter | AI6 container | <code>scripts/demo</code> | <code>./scripts/demo start</code> | <code>8080</code> vision; <code>8081</code> frame broadcast | Lifecycle listener count and adapter/Bridge evidence | <code>&lt;runtime-root&gt;/logs/asr/overview_adapter.log</code> | <code>./scripts/demo stop</code> | MQTT, legacy ASR/camera inputs, shared runtime root | <code>LIVE_NOT_VERIFIED</code>; not operated by Gate 5B.3. |
| Resident Hermes | AI6 container | <code>scripts/demo</code> | <code>./scripts/demo start</code> | <code>127.0.0.1:8765</code>; <code>/health</code> and <code>/invoke</code> | HTTP health plus exact lifecycle identity | <code>&lt;runtime-root&gt;/logs/hermes/resident.log</code> | <code>./scripts/demo stop</code> | Patched Hermes runtime, required skills and Bridge contract | <code>LIVE_NOT_VERIFIED</code>; not operated by Gate 5B.3; typed failure boundary is hardware-free tested. |
| HermesTemiBridge | AI6 container | <code>scripts/demo</code> | <code>./scripts/demo start</code> | No public TCP listener; private callback Unix sockets | Exact process identity, callback socket and MQTT readiness | <code>&lt;runtime-root&gt;/logs/bridge/bridge.log</code> | <code>./scripts/demo stop</code> | MQTT, resident Hermes, schemas, validators and private shared root | <code>LIVE_NOT_VERIFIED</code>; not operated by Gate 5B.3. |
| Hermes gateway | AI6 container when enabled | <code>scripts/demo</code> | <code>./scripts/demo start</code> | No fixed AI6 service port in the lifecycle contract | <code>hermes gateway status</code> plus exact process identity | <code>&lt;runtime-root&gt;/logs/gateway/gateway.log</code> | <code>./scripts/demo stop</code> | Patched Hermes runtime and external provider credentials if used | Disabled in newcomer; real provider live-unverified. |
| Action viewer | AI6 container when enabled | <code>scripts/demo</code> | <code>./scripts/demo start</code> | <code>8010</code> HTTP; <code>8011</code> llama server in production | Viewer <code>/health</code> source/llama readiness and five redacted component objects | <code>&lt;runtime-root&gt;/logs/trace/action_viewer.log</code> | <code>./scripts/demo stop</code> | Adapter frame stream, external GGUF/mmproj, generated llama server and optional pose weight | Experimental and live-unverified; not operated by Gate 5B.3. |
| Newcomer mock LM/resident/viewer | AI6 container | <code>scripts/demo</code> under <code>newcomer_mock</code> | <code>./scripts/demo start</code> | <code>29134</code>, <code>29765</code>, <code>29010/29011</code> | Mock HTTP health and exact lifecycle identities | <code>&lt;runtime-root&gt;/logs/{lmstudio,hermes,trace}/</code> | <code>./scripts/demo stop</code> | Tracked mock servers and high-port profile | Not started by Gate 5B.3; software-only path is hardware-free. |
| Newcomer mock Android/Discord | AI6 container | <code>scripts/demo</code> under <code>newcomer_mock</code> | <code>./scripts/demo start</code> | <code>29012</code> Android health; <code>29013</code> Discord mock | Mock health and canonical fake event/result evidence | <code>&lt;runtime-root&gt;/logs/mock/</code> | <code>./scripts/demo stop</code> | MQTT, Bridge, isolated mock profile | Not started by Gate 5B.3; no real device/provider contact. |
| Temi Android App | Temi robot/device | Android owner, outside AI6 lifecycle | Android owner’s application procedure; none in AI6 | Deployment-configured broker endpoint; command/result topics | Fresh Android runtime snapshot, subscriptions, command/result evidence and physical observation | Android owner’s private evidence store | Android owner’s controlled app/device procedure | Android source/APK, device and broker reachability | External and live-unverified. |
| Discord provider | External provider | Bridge notification path only when explicitly authorized | No AI6 direct start command | Provider HTTPS endpoint, not an AI6 listener | Bridge redacted receipt; real success requires provider HTTP 204 evidence | Bridge notification receipt under private runtime | External owner/provider procedure | Owner-only credential env and explicit authorization | Disabled by default; live-unverified. |

<code>&lt;runtime-root&gt;</code> is a documentation placeholder. The canonical
private root is <code>/TemiAgent/.runtime/demo</code>; custom roots must be
absolute, owner-only and outside Git worktrees. The operator guide and
configuration reference define the exact command grammar and validation rules.

## Gate 5 accepted host disposition

Gate 5B Retry #4 is the accepted bounded host-runtime evidence. The
publication/runtime candidate passed L0–L3 and L5, then rolled back its
Gate-owned services. It reused MQTT without restart and preserved external LM
Studio. This table updates the historical matrix above without changing
ownership semantics:

| Boundary | Gate 5 disposition | Scope limit |
|---|---|---|
| Production LM Studio | <code>HOST_LIVE_VERIFIED; EXTERNAL_ONLY</code>; model API identifier <code>google/gemma-4-31b</code>, provisioned model <code>temi/gemma-4-31b-it-qat</code>, runtime context <code>64000</code> verified from metadata. | AI6 never starts/stops/unloads or globally mutates the provider; general GPU/model behavior remains separately bounded. |
| MQTT broker | <code>HOST_LIVE_VERIFIED; REUSED; NOT_RESTARTED</code>; accepted configured listener <code>0.0.0.0:1883</code>. | Explicit broker configuration remains mandatory; no foreign listener adoption. |
| Overview adapter | <code>HOST_LIVE_VERIFIED</code> for the accepted L0–L3 host path; Gate-owned process removed during rollback. | No claim for a Temi microphone/camera session or legacy route. |
| Resident Hermes | <code>HOST_LIVE_VERIFIED</code> for health, inference-impossible L2 and one bounded L5 request; Gate-owned process removed during rollback. | Hermes base plus patches <code>0001</code>–<code>0010</code> must produce tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>; no Android claim. |
| HermesTemiBridge | <code>HOST_LIVE_VERIFIED</code> for the validated L3 callback/publication path; Gate-owned processes removed during rollback. | The L3 physical side effect was <code>NO</code>; Android command execution remains L4. |
| Gateway/viewer | <code>LIVE_NOT_VERIFIED</code> / not required by the accepted minimum path. | Optional provider, viewer/GPU and perception acceptance remain separate. |
| Temi Android artifact provenance | <code>CLOSED_PASS</code>; LAB606 accepted the final 1.0.2 (3) artifact and exact installed-APK match. | Artifact identity does not prove physical execution, playback or device observation. |
| Temi physical/E2E | <code>NOT_RUN_BY_SCOPE</code> / external. | No physical execution, playback or complete L4 E2E acceptance was accepted. |
| Discord | <code>NOT_RUN_BY_SCOPE</code> / external. | No real notification delivery was accepted. |

The accepted request budget is <code>L1=0; L2=0; L3=0; L5=1</code>. PIDs,
run IDs, temporary worktrees and transient runtime directories are
<code>ACCEPTANCE_EVIDENCE_ONLY</code>, not deployment pins or handover
requirements. See [verification and acceptance](verification_and_acceptance.md)
for the redacted result and retained failure history.

## L4.3 Android provenance handover

LAB606 evidence closes artifact provenance only. The accepted external source is
at revision <code>3e2fc0376e5b5ca3992e697fc030cdc08173c639</code> on branch
<code>main</code>, based on accepted baseline
<code>8c458888657efca5384c6d51e5ec57e8b385d987</code>. The final artifact is
<code>temi-agent-android-public/app/build/outputs/apk/demo/app-demo.apk</code>,
package <code>com.robotemi.agent</code>, version <code>1.0.2 (3)</code>,
SHA-256 <code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>.
Installed package, signer, embedded revision and whole APK matched exactly;
the existing install was accepted as-is. The observed target
<code>192.168.50.204:5555</code> is classified
<code>OBSERVED_AI6_DEPLOYMENT</code>, not a portable endpoint or tracked
configuration. E2DD remains the legacy 1.0.0 (1) artifact, and the prior L4.2
mismatch is superseded by
<code>SUPERSEDED_BY_AUTHORITATIVE_LAB606_PROVENANCE_RECOVERY</code>.

Do not use this record to authorize ADB, installation, replacement, data reset,
Android/Temi operation, MQTT, service operation or inference. Complete Temi
physical/E2E acceptance remains a separate gate and
<code>READY_FOR_GATE6=NO</code>.

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
| LM Studio | external in production; managed only as a newcomer mock | External LM owner; lifecycle has no real-LM start/stop owner | `/v1/models`, configured identifier, one listener and immutable context/GPU policy |
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
Production LM Studio is different: the provider is external and immutable to
this lifecycle. Readiness is established through one configured listener and
the HTTP model-list contract. The lifecycle never invokes `lms`, never loads or
unloads models, and never stops a provider process. The compatibility helper
files fail closed if called directly. The newcomer mock remains lifecycle-owned
on its isolated high port for software-only acceptance.

The configured Hermes context is a requirement, not proof by itself of the
loaded provider context. Gate 5B.3 historically exposed a mismatch: Hermes
and the resident were configured for `64000` while the external backend
reported an available `4096` context for an approximately `11508`-token
request. Gate 5 final subsequently accepted external runtime metadata showing
context `64000` and a model maximum of `262144` before the one bounded L5
request. This is deployment evidence, not a portable provider version or
model pin; AI6 still does not change external provider state.

```bash
./scripts/demo --config <PRIVATE_CONFIG_PATH> doctor
./scripts/demo --config <PRIVATE_CONFIG_PATH> start
./scripts/demo --config <PRIVATE_CONFIG_PATH> status
./scripts/demo --config <PRIVATE_CONFIG_PATH> restart
./scripts/demo --config <PRIVATE_CONFIG_PATH> stop
```

For production, external LM readiness is a precondition, followed by the
managed start order MQTT, adapter, resident, Bridge, gateway, viewer. The
newcomer mock adds its managed LM test double before MQTT. The production stop
order is viewer, gateway, Bridge, resident, adapter, MQTT; external LM is not
stopped. The lifecycle uses an owner-only `flock` and records every
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
