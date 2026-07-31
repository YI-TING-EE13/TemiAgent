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
./scripts/demo init-config
./scripts/demo doctor
./scripts/demo status
python3 tools/show_temi_trace.py --log-dir <bridge-log-dir> --latest --json
```

Record the returned `run_id`, `event_id`, error code, exact PID identity, and
listener state. Do not print or attach private env values, credentials, raw
care records, images, or full debug traces.

## Triage map

| Symptom | Read-only evidence | Meaning / safe next decision |
|---|---|---|
| `doctor` fails before a service check | `doctor` failure item and private-env mode/parent checks. | Fix ownership, placeholder, path-root or source-precondition issue in an authorized configuration task; do not create a replacement config in Git. |
| `doctor` has `ENTRYPOINT_MISSING`, `ENDPOINT_UNAVAILABLE`, `ENDPOINT_TIMEOUT`, `HEALTH_MALFORMED`, or `PORT_CONFLICT` | The JSON item’s `name`, `code`, `required`, message, and exact listener/PID evidence. | These are required `FAIL` states and the command exits non-zero. Restore the tracked entrypoint or resolve the exact configured dependency; do not relabel the check as PASS or adopt a listener. |
| `doctor` reports `MANAGED_ENDPOINT_NOT_STARTED` | The item is `WARNING`, `required=false`, and has no recorded exact owned process. | This is expected before `start`; it is not a healthy service. Start only when separately authorized, then require the live health check and exact-PID record. |
| `doctor` reports `LIFECYCLE_RECOVERY_REQUIRED` or `STATE_PID_ROOT_UNWRITABLE` | `lifecycle_state` or `state_pid_root` item, the owner-only lifecycle state, and the private runtime-root parent. | `STARTING`, `START_FAILED`, or `UNHEALTHY` requires exact-owner recovery. Preserve the state. Repair an unwritable state/PID parent before any authorized start; never delete state to bypass the check. |
| `stop` returns `STOP_INCOMPLETE_OWNERSHIP` | Returned `findings`, lifecycle state, exact listener/PID identity, cwd, and command line. | The lifecycle did not signal a PID because the managed-like process is absent from ownership state. The non-zero result is intentional. Escalate with the exact evidence; do not adopt or kill by name. |
| `newcomer_mock` reports `SKIPPED_BY_PROFILE` or `REAL_DEVICE_SKIPPED` | `DEMO_PROFILE`, profile-owned high ports, and the JSON item. | The local gateway exclusion and real Android exclusion are intentional. They do not weaken source, Bridge, validator, mock health, or port-ownership checks. |
| Production branch validation fails or detached HEAD is rejected | `repository` doctor item and `DEMO_GIT_BRANCH_POLICY` / `EXPECTED_GIT_BRANCH` from the private env. | Production defaults require `main`. Only the tracked newcomer sample explicitly disables the branch-name gate for disposable clone testing; do not silently disable it in a production configuration. |
| `status` is `BACKEND_NOT_READY` | Per-service health, exact recorded PID identity, listener count, callback-socket state. | Find the first failed managed or declared-external service. Preserve evidence; a restart needs explicit authorization. |
| `BACKEND_READY_WAITING_ANDROID` | `status.broker.remote_sessions` and Android evidence. | Backend can be healthy without a current Android MQTT session. This is not a playback or TTS success claim. |
| Unknown listener, stale PID, or PID identity mismatch | `doctor`, `ss -ltnp`, `/proc/<pid>/cwd`, `/proc/<pid>/cmdline`, lifecycle state. | Stop and follow the exact-PID procedure. Never adopt by name, `pkill`, `killall`, state-file deletion, or port-only assumption. |
| Bootstrap check fails | `./scripts/bootstrap --check` output and the manifests below `third_party/hermes/` and `third_party/llama_cpp/`. | Resolve missing environment/dependency separately. Do not alter a generated external checkout to conceal the failure. |
| Fresh newcomer acceptance cannot bind a mock port | `doctor` port item, `ss -ltnp` for that exact high port, and lifecycle state. | Preserve the external listener evidence and select a new unique acceptance run only after it is no longer owned elsewhere. Never kill by name or redirect the profile to a production port. |
| Resident health fails | Resident health response, recorded process identity, resident log path. | Health only covers the wrapper. Check skill preload/config alignment before changing model or hooks. |
| Bridge cannot accept an event | Trace `event_received`, `input_validated`, and `event_failed` records. | Use the error stage to distinguish allowlist, schema, image path, invocation, validation, or dispatch; do not invent a new event to probe it. |
| Bridge rejects a path or image | Trace error code, shared-root paths and file metadata. | Check producer/consumer root mapping and allowlisted location. Do not relax `image_resolver` or copy private frames into source. |
| Hermes output is rejected | `hermes_invocation_finished` and `hermes_output_validated` trace summaries. | Fix a real contract issue only with coordinated schema/skill/test review; do not weaken the validator. |
| No Temi action is observed | `command_request_published`, `cmd/result`, Android subscription/session evidence. | A Bridge publish is not proof of Android execution. Verify command result and device observation separately. |
| Abnormal event produces care TTS but no memory update | Abnormal-care trace stage and active resident status. | This may be intentional: `unknown_resident_memory_forbidden` prevents resident-memory access and must produce a speak-only care response, not an identity guess. |
| Abnormal event has neither care response nor trace | Viewer receipt/event ID, Bridge trace index, Bridge health and listener evidence. | Identify whether the viewer published, Bridge accepted, or input validation failed. Do not re-trigger the detection during a recording. |
| Immediate abnormal notification is `failed` or `disabled` | Bridge `initial_notification_finished` trace and the redacted stage receipt in `MEMORY_DIR/abnormal_care_episodes.json`. | The Bridge owns this route. `disabled`, `401`, `403`, `404`, `429`, timeout, and connection failure are not delivery. Check the selected Bridge mode and credential-file metadata; do not enable viewer Discord flags or claim a caregiver was notified. |
| Demo mock notification does not create a receipt | Bridge trace, `ABNORMAL_NOTIFICATION_MODE`, both Demo notification flags, and the persisted stage receipt. | `demo_mock` requires both explicit flags. Correct the private Demo configuration only; a missing receipt prohibits a success statement. |
| Duplicate abnormal event or restart appears to notify twice | Original `event_id`, episode `notification_stages`, transitions, and the post-restart Bridge trace. | The same event/stage must have one persisted reservation and receipt. Preserve the state file and trace for a contract defect; do not delete state to re-run the alert. |
| Gateway is healthy but no Discord message appears | Gateway health, Bridge stage receipt, and Discord provider-side evidence if available. | Gateway connectivity and credential configuration are not delivery acknowledgement. The viewer never owns Discord delivery. |
| Discord notification says delivered but target is unclear | Existing receipt fields and operator-provided target evidence. | Do not infer a caregiver, channel, or emergency recipient from a generic delivery result. |
| Viewer health fails or returns `VIEWER_HEALTH_INTERNAL_ERROR` | HTTP status; `viewer_core`, `event_ingestion`, `frame_state`, `real_discord`, and `demo_notification_mock`; exact PID identity; viewer log path. | HTTP 503 is an internal snapshot failure. A missing component is malformed health. Check the named component and viewer/llama prerequisites; never infer Discord delivery or expose a credential path. |
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

The current abnormal-care episode route records these additional stages:

```text
initial_notification_finished
  -> hermes_request_prepared
  -> hermes_invocation_finished
  -> hermes_output_validated
  -> command_request_published
  -> episode_awaiting_first_response
  -> abnormal_care_follow_up_resolved | escalation_notification_finished
```

`initial_notification_finished` records a redacted receipt for the immediate
stage. `abnormal_care_follow_up_resolved` records a deduplicated status update
when the resident replies. `escalation_notification_finished` records the
second-timeout result. A Bridge command publish remains distinct from Android
`cmd/result` evidence.

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
