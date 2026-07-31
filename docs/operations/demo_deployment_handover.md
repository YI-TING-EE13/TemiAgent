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
# Required source reconstruction for a clean clone; no dependency install.
./scripts/bootstrap --hermes
# Run only after the documented Hermes and module environments exist:
./scripts/bootstrap --check
# Only when dependency environments need repair:
./scripts/bootstrap --sync
```

`--hermes` is the clean-clone source-reconstruction step: it initializes an
independent nested checkout, fetches the public upstream base, verifies the
tracked patch SHA-256 values, creates the local-only
`temiagent/integration` branch and verifies the expected tree hash. It starts
no service and installs no dependency. `--check` makes no credentials, starts
no service, and changes no runtime state, but it is a readiness gate that
requires the documented Hermes and module environments to already exist.
`--sync` uses each existing project's `uv sync --frozen`; it does not update
lockfiles. The gitlink remains a local historical reference; reproducibility is defined by
[`third_party/hermes/manifest.json`](../../third_party/hermes/manifest.json)
and its patch series, so no unavailable private Hermes commit or remote push is
required.

## Private configuration and runtime data

Copy `config/demo.env.example` to `<PRIVATE_CONFIG_PATH>` outside every Git
worktree, set mode `0600`, and keep its parent directory owner-only. The
private config names a separate owner-only Discord env file. That file contains
only `DISCORD_WEBHOOK_URL=<private value>` and is never printed, committed, or
copied into a handover bundle.

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
| Action viewer | managed when enabled | lifecycle | viewer `/health` booleans |
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

The lifecycle emits JSON service results. It uses stable failure codes including
`CONFIG_INVALID`, `LOCK_BUSY`, `PORT_IN_USE_EXTERNAL`, `MODEL_LOAD_FAILED`,
`MODEL_CONTEXT_MISMATCH`, `GPU_POLICY_MISMATCH`, `BROKER_START_FAILED`,
`GATEWAY_START_FAILED`, `PID_IDENTITY_MISMATCH`, and `STOP_TIMEOUT`.

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
| Viewer | local model paths, CUDA/pose settings, abnormal and Discord flags, and an owner-only credential env path. |
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

The abnormal route remains care-first: detector event → Bridge supportive TTS
and consent question → optional notification path. Viewer pre-alert TTS does
not bypass Bridge. Discord is best-effort only; gateway health or webhook
configuration never proves delivery and is not an emergency service.

## Recovery and limits

If `doctor`, `status`, or `stop` reports an unknown listener, stale callback,
or identity mismatch, preserve evidence and stop. Inspect the exact PID, cwd,
executable, command line, parent, and listener before any manual signal. Use
the service-specific manager first, signal only the verified PID, then verify
dependent services and ports. Do not delete stale runtime roots or reset the
Git tree to recover a Demo.

The acceptance bundle is runtime evidence, not source. It should contain
masked configuration inventories, process/port snapshots, memory hashes,
lifecycle results, and test logs with mode `0600`. Retain it under the local
runtime policy; do not attach raw care records, images, recordings, webhooks,
or credentials to a public handover.
