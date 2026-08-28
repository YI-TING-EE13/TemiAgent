# Demo Troubleshooting Guide

Status: <code>CURRENT_AUTHORITY</code>; Demo-only. Last reviewed for Gate 5B.1:
2026-08-28.

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

## Required symptom contract

The first response to every symptom is read-only evidence. The safe action
never adopts an unknown process, weakens a validator, deletes runtime state,
prints a credential or uses broad process control.

| Symptom | Check | Likely cause | Safe action | Escalation / do not do |
|---|---|---|---|---|
| MQTT not running | <code>./scripts/demo --json mqtt status</code>; inspect expected port, listener count, TCP result and ownership state. | No managed owner, broker start failure, stale state or the wrong private config. | Preserve the JSON and broker log path; compare the config and source identity with the operator contract. | An authorized operator may plan exact-owner recovery. Do not start a full stack or infer readiness from a port alone. |
| MQTT foreign listener | MQTT status plus <code>ss -ltnp</code> for the configured port and exact PID/cwd/cmdline evidence. | Another broker/process owns the port or the recorded child no longer matches. | Record the listener owner and return the foreign-listener failure unchanged. | Escalate the exact PID to the owner. Do not adopt, signal by name, or use broad process matching. |
| Temi cannot connect | Verify broker bind/port in MQTT status, Android endpoint configuration, fresh Android snapshot and network reachability evidence. | Endpoint is not the deployment broker, firewall/routing is wrong, or Android is not running. | Keep AI6 client defaults loopback and request the Android owner to verify its private endpoint. | Android owner handles device/network changes. Do not add a lab address to tracked docs or reconfigure the broker in this gate. |
| Temi connected but command/result is absent | Compare Bridge trace <code>command_request_published</code>, Android subscription/session evidence and <code>cmd/result</code>. | Bridge validation failed, Android did not subscribe, or device execution is outside AI6 evidence. | Classify publication, receipt and execution as separate events; preserve event/request IDs. | Do not claim execution from publish success and do not fabricate a result. Escalate with both AI6 and Android evidence. |
| LM Studio unavailable | Run <code>doctor</code>; inspect the configured listener count and redacted <code>/v1/models</code> evidence for the expected identifier. | LM Studio is absent, the model/cache is not provisioned, GPU policy differs or the external service is down. | Preserve the external dependency failure and ask the LM/runtime owner to restore readiness. | Production LM is external: do not invoke <code>lms</code>, change model/context/GPU policy, reclaim port <code>1234</code>, or start/stop the provider. |
| LM Studio CLI audit wakes an internal daemon or a legacy LM record is present | Preserve the exact redacted process/port evidence and run only the lifecycle status/doctor checks. | LM Studio CLI has global side effects and the lifecycle cannot prove ownership of legacy provider state. | Classify the provider as external/unknown, leave it untouched, and escalate to the LM/runtime owner. A future Gate 5B retry must create a fresh process ledger. | Never use <code>lms ls</code>, <code>lms ps</code>, <code>lms unload --all</code>, <code>lms server stop</code>, <code>lms daemon down</code>, <code>pkill</code> or <code>killall</code> as recovery. |
| Bridge unavailable | Run <code>doctor</code>; inspect exact Bridge PID, private callback sockets and bounded Bridge log. | Missing locked environment, MQTT dependency, invalid config or failed process health. | Check the named error stage and source/config identity without altering runtime state. | Do not bypass the Bridge with raw command publication or direct Android control. |
| Hermes unavailable | Check required <code>hermes-agent/venv/bin/python3</code>, <code>hermes-agent/venv/bin/hermes</code>, resident health and the exact error. | External Hermes environment is not provisioned or the resident wrapper cannot load required skills. | Follow the external dependency README and preserve the failing check. | Do not substitute original upstream, local checkout, fallback CLI or direct Hermes MQTT publication. |
| Hermes submodule/bootstrap failure | Run <code>git submodule status --recursive</code>, the manifest verifier and the bounded bootstrap output. | Team remote is unreachable, gitlink is not at the pinned base, patch hash/tree differs or an alternate source was used. | Stop source reconstruction at the named failure and retain the exact commit/tree evidence. | Do not use a file URL, Git alternate, local checkout or unreviewed patch. |
| License verification failure | Run the Hermes or llama license verifier named by the manifest and record only hashes/status. | Declared license file, pinned object or checked-out content differs. | Treat the dependency as unavailable for publication until the owner resolves provenance. | Do not publish, redistribute or bypass the verifier. |
| Adapter unavailable | Inspect lifecycle listener counts for ports <code>8080</code>/<code>8081</code>, adapter identity and private adapter log. | Legacy input source is absent, port is occupied or adapter process failed. | Preserve the first failing listener/identity result; the adapter is not a command dispatcher. | Do not route commands through the adapter or use a historical direct-service script as a fix. |
| Resident unavailable | Check <code>GET /health</code> on the configured local resident endpoint, exact PID and log. | Hermes environment/skill preload or config/port failure. | Inspect the health payload and source/config evidence; keep the Bridge boundary intact. | Do not claim Hermes reasoning readiness from a process alone or alter prompts to hide a failure. |
| Anomaly backend unavailable | Inspect viewer <code>/health</code>, source/frame/llama component fields, configured files and exact identity. | Optional viewer, frame stream, llama server or external model/pose weight is missing. | Disable or defer the optional experimental path and classify the main backend separately. | Do not call it a medical detector, hardware dispatcher or production readiness gate. |
| Model or artifact missing | Compare the resource manifest, private config path, regular-file/executable check and external provenance. | Model/cache/weight/Android logical asset was not provisioned or lacks approved provenance. | Keep the feature unavailable and ask the named owner to provision it through an approved channel. | Do not download unreviewed weights, copy real data into Git or mark a placeholder as ready. |
| Port occupied | Check the exact configured port with <code>ss -ltnp</code> and lifecycle/doctor evidence. | Foreign process, stale service, duplicate profile or a second test run. | Preserve PID/cwd/command evidence and choose an authorized isolated profile/run root. | Do not kill by process name, reuse a foreign listener or silently move production ports. |
| Stale runtime ownership | Inspect owner-only state, recorded start identity, exact live PID and status code. | Interrupted startup/stop or state from a prior run. | Follow the exact-PID recovery policy and leave unresolved ownership visible. | Do not delete state to make <code>doctor</code> pass or adopt by port/name. |
| Tests fail after a fresh clone | Run the failing command from [developer setup](developer_setup.md), verify submodule/tree/license and locked environments. | Missing source reconstruction, locked dependency, external binary or unsupported environment. | Preserve the first failure and classify it as source, dependency, environment or test defect. | Do not loosen lockfiles, replace pins, use a local checkout or claim clean-clone success. |
| Discord/webhook unavailable | Check Bridge notification mode, redacted stage receipt and owner-only credential-file metadata; never print the value. | Disabled route, invalid credential file, provider error, timeout or no authorization. | Keep notification status as disabled/failed and continue only with an explicitly authorized provider plan. | Do not enable viewer-owned Discord flags, retry a real recipient blindly or call it emergency delivery. |

## Triage map

| Symptom | Read-only evidence | Meaning / safe next decision |
|---|---|---|
| `doctor` fails before a service check | `doctor` failure item and private-env mode/parent checks. | Fix ownership, placeholder, path-root or source-precondition issue in an authorized configuration task; do not create a replacement config in Git. |
| `doctor` has `ENTRYPOINT_MISSING`, `ENDPOINT_UNAVAILABLE`, `ENDPOINT_TIMEOUT`, `HEALTH_MALFORMED`, or `PORT_CONFLICT` | The JSON item’s `name`, `code`, `required`, message, and exact listener/PID evidence. | These are required `FAIL` states and the command exits non-zero. Restore the tracked entrypoint or resolve the exact configured dependency; do not relabel the check as PASS or adopt a listener. |
| `doctor` reports `MANAGED_ENDPOINT_NOT_STARTED` | The item is `WARNING`, `required=false`, and has no recorded exact owned process. | This applies to managed test doubles/services, not production LM Studio. Production LM readiness is a required external precondition and never gets an LM lifecycle start command. |
| `doctor` reports `LIFECYCLE_RECOVERY_REQUIRED` or `STATE_PID_ROOT_UNWRITABLE` | `lifecycle_state` or `state_pid_root` item, the owner-only lifecycle state, and the private runtime-root parent. | `STARTING`, `START_FAILED`, or `UNHEALTHY` requires exact-owner recovery. Preserve the state. Repair an unwritable state/PID parent before any authorized start; never delete state to bypass the check. |
| `stop` returns `STOP_INCOMPLETE_OWNERSHIP` | Returned `findings` plus separate read-only lifecycle/doctor evidence: exact listener/PID identity, cwd and command line where available. | The lifecycle did not signal a PID because the process is absent from an applicable ownership state, including an external/legacy LM record. The non-zero result is intentional. For an external/legacy LM record, the result intentionally returns only the service/port finding; collect any exact process evidence separately and do not adopt or kill by name. |
| Lifecycle state reports an invalid ownership record | The read-only `doctor`/stop error, state record name and private state-file mode; no provider or PID control call. | A record is malformed, lacks positive ownership, or lacks an exact leader identity. Preserve the state and obtain fresh exact evidence before any authorized recovery; a malformed record is never adopted. Do not delete the state file, infer ownership from a port/name, or signal a PID. |
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
