# Demo Troubleshooting Guide

Status: maintained, Demo-only. Last reviewed: 2026-07-31.

This guide maps a symptom to read-only evidence and the smallest safe next
decision. It does not authorize service restart, raw MQTT publication, Discord
test delivery, model changes, runtime-data deletion, or Android control. The
only current lifecycle is `scripts/demo`; use the
[Demo operator guide](DEMO_OPERATOR_GUIDE.md) and
[safe service operations](safe_service_operations.md) before an authorized
state change.

## First evidence, before intervention

Run inside the designated container and project root:

```bash
cd /TemiAgent
./scripts/demo --config <private-demo-env> doctor
./scripts/demo --config <private-demo-env> status
python3 tools/show_temi_trace.py --log-dir <bridge-log-dir> --latest --json
```

Record the returned `run_id`, `event_id`, error code, exact PID identity, and
listener state. Do not print or attach private env values, credentials, raw
care records, images, or full debug traces.

## Triage map

| Symptom | Read-only evidence | Meaning / safe next decision |
|---|---|---|
| `doctor` fails before a service check | `doctor` failure item and private-env mode/parent checks. | Fix ownership, placeholder, path-root or source-precondition issue in an authorized configuration task; do not create a replacement config in Git. |
| `status` is `BACKEND_NOT_READY` | Per-service health, exact recorded PID identity, listener count, callback-socket state. | Find the first failed managed or declared-external service. Preserve evidence; a restart needs explicit authorization. |
| `BACKEND_READY_WAITING_ANDROID` | `status.broker.remote_sessions` and Android evidence. | Backend can be healthy without a current Android MQTT session. This is not a playback or TTS success claim. |
| Unknown listener, stale PID, or PID identity mismatch | `doctor`, `ss -ltnp`, `/proc/<pid>/cwd`, `/proc/<pid>/cmdline`, lifecycle state. | Stop and follow the exact-PID procedure. Never adopt by name, `pkill`, `killall`, state-file deletion, or port-only assumption. |
| Bootstrap check fails | `./scripts/bootstrap --check` output and `third_party/hermes/manifest.json`. | Resolve missing environment/dependency separately. Do not stage a generated nested gitlink. |
| Resident health fails | Resident health response, recorded process identity, resident log path. | Health only covers the wrapper. Check skill preload/config alignment before changing model or hooks. |
| Bridge cannot accept an event | Trace `event_received`, `input_validated`, and `event_failed` records. | Use the error stage to distinguish allowlist, schema, image path, invocation, validation, or dispatch; do not invent a new event to probe it. |
| Bridge rejects a path or image | Trace error code, shared-root paths and file metadata. | Check producer/consumer root mapping and allowlisted location. Do not relax `image_resolver` or copy private frames into source. |
| Hermes output is rejected | `hermes_invocation_finished` and `hermes_output_validated` trace summaries. | Fix a real contract issue only with coordinated schema/skill/test review; do not weaken the validator. |
| No Temi action is observed | `command_request_published`, `cmd/result`, Android subscription/session evidence. | A Bridge publish is not proof of Android execution. Verify command result and device observation separately. |
| Abnormal event produces care TTS but no memory update | Abnormal-care trace stage and active resident status. | This may be intentional: `unknown_resident_memory_forbidden` prevents resident-memory access and must produce a speak-only care response, not an identity guess. |
| Abnormal event has neither care response nor trace | Viewer receipt/event ID, Bridge trace index, Bridge health and listener evidence. | Identify whether the viewer published, Bridge accepted, or input validation failed. Do not re-trigger the detection during a recording. |
| Gateway is healthy but no Discord message appears | Gateway health, viewer health booleans, existing Bridge/viewer delivery receipt, Discord provider-side evidence if available. | Gateway connectivity and webhook configuration are not delivery acknowledgement. Treat it as best effort; do not claim notification success. |
| Discord notification says delivered but target is unclear | Existing receipt fields and operator-provided target evidence. | Do not infer a caregiver, channel, or emergency recipient from a generic delivery result. |
| Viewer health fails | Viewer `/health` booleans, exact PID identity, managed llama-server listener, viewer log path. | Diagnose model asset/config/precondition under the optional viewer scope; do not restart shared LM Studio as a shortcut. |
| Media request is published but nothing plays | Bridge media trace, Android `accepted`/`started`/`playing` result, screen observation. | Publication or native callback acceptance is insufficient. Android asset mapping and device playback are external acceptance gates. |
| Repeated-discomfort route does not persist | Identity status, feature-gate inventory, Bridge callback/trace outcome. | Verify confirmed father and exact synthetic flow. Unknown/mother denial is an intended privacy boundary. |

## Stage-oriented evidence for the canonical route

For an individual event, interpret the first failing or last successful trace
stage. A later duplicate `ignored` record does not replace the original terminal
result.

```text
event_received
  -> input_validated
  -> care_context_built
  -> hermes_request_prepared
  -> hermes_invocation_finished
  -> hermes_output_validated
  -> memory_actions_completed
  -> command_request_published
  -> command_result_received
  -> event_completed | event_failed
```

Abnormal events can instead start with
`abnormal_care_confirmation_created` and later resolve through
`abnormal_care_follow_up_resolved`. The first care prompt is Bridge-owned and
speak-only; no Discord receipt or memory action should be presented as an
emergency response.

## Escalation boundary

Only after an operator explicitly authorizes recovery may a service operation
be planned. That plan must name the target service, expected executable, working
directory, pre-operation health, exact PID, protected dependencies, verification
step, and rollback/containment. A valid repair never uses broad process matching
or deletes state merely to clear an error.

For a suspected documentation mismatch, record the source file, command,
observed output, and contract impact. Correct prose in a focused documentation
change; do not silently change source, validators, schemas, private config, or
runtime artifacts to make a document appear true.
