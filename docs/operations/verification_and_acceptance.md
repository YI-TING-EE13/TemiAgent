# Verification and Acceptance Guide

Status: <code>CURRENT_AUTHORITY</code>. Last reviewed for Gate 5 final evidence,
L4.3 Android provenance adoption and L4 final evidence adoption: 2026-08-29.

This guide distinguishes executable hardware-free verification from external
acceptance. Run every project command in the designated container from
<code>/TemiAgent</code>. This guide retains the Gate 5B.1, 5B.3 and 5B.5
non-live remediation records and also adopts the separately completed Gate 5B
Retry #4 host acceptance and L4.7B post-reboot physical TTS acceptance: their
live evidence remains bounded to the exact contracts recorded below. The
current documentation change itself does not operate services, send
MQTT/Discord messages, run inference, alter private configuration, or use a
robot. The historical remediation tests use
fake/stub providers and do not start LM Studio or any other long-running Demo
service. Do not turn a skipped external gate into a PASS claim.

## Gate 5 final host-runtime acceptance

Gate 5B Retry #4 is accepted as <code>GATE5_HOST_RUNTIME=CLOSED_PASS</code>.
This record is adopted from prior execution and is not rerun by this
documentation gate.

| Evidence | Accepted result |
|---|---|
| Publication/runtime source | Candidate started from <code>release/github-v1@59d568b079ce260e2144c410b0f9397d8b026913</code>; Hermes pinned base plus patches <code>0001</code>–<code>0010</code> reconstructs tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>. |
| LM Studio ownership | <code>EXTERNAL_ONLY</code>; API identifier <code>google/gemma-4-31b</code>; provisioned model <code>temi/gemma-4-31b-it-qat</code>; runtime context <code>64000</code>, verified from runtime metadata; observed model maximum <code>262144</code>. |
| MQTT | Existing broker reused, not restarted; accepted listener <code>0.0.0.0:1883</code>; explicit broker configuration remained mandatory. |
| Layer disposition | L0 PASS; L1 PASS; L2 PASS; L3 PASS; L4 Android provenance CLOSED_PASS; L4 canonical TTS E2E CLOSED_PASS; L5 PASS. |
| Request budget | <code>L1=0; L2=0; L3=0; L5=1</code>. |
| L2 | Inference-impossible malformed resident request returned HTTP 400 before invocation; inference calls <code>0</code>. |
| L3 | Bridge Unix callback produced a validated identity-result publication on <code>temi/temi-01/resident/identity/result</code>; physical side effect <code>NO</code>. |
| L5 | HTTP 200; approximately <code>14.225686 s</code> curl and <code>14222 ms</code> resident latency; response validation PASS; one <code>speak</code> action. |
| Failure/rollback | No context overflow, compression exhaustion, final_response KeyError, BrokenPipe, secondary 500 or unexpected runtime error; resident health after PASS; Gate-owned processes/listeners remaining <code>0</code>; LM/MQTT preserved. |

The required frozen contract is production external-only LM management, model
API identity <code>google/gemma-4-31b</code>, runtime context
<code>64000</code>, context verification from runtime metadata, reusable
independently managed MQTT, no tracked private-LAN fallback for
<code>PC_IP</code>, inference-impossible L2 validation, and exact ownership
boundaries for stop. PIDs, run IDs, temporary worktrees and transient runtime
directories are <code>ACCEPTANCE_EVIDENCE_ONLY</code>, not portable setup
requirements. LAB606 Android artifact provenance and the exact canonical TTS
physical boundary are now closed as separate L4 evidence items; camera/
microphone, video/media playback, viewer/GPU general readiness, Discord
delivery, broader Android behavior and other hardware actions remain separate
or unverified.

## L4.3 Android artifact provenance adoption

LAB606 result <code>LAB606_ANDROID_FINAL_ARTIFACT_PROVENANCE_CONFIRMED</code> is
adopted here as <code>ANDROID_PROVENANCE=CLOSED_PASS</code>. This is a
documentation/evidence record only: no ADB, installation, replacement,
reinstall, data reset, Android operation, Temi operation, MQTT operation or
Android-source change occurred in this gate.

| Field | Accepted evidence |
|---|---|
| External source | Repository <code>temi-agent-android-public</code>, branch <code>main</code>, current revision <code>3e2fc0376e5b5ca3992e697fc030cdc08173c639</code>; accepted baseline <code>8c458888657efca5384c6d51e5ec57e8b385d987</code> is an ancestor and no post-baseline implementation, build-config or signing changes were found. |
| Final artifact | <code>temi-agent-android-public/app/build/outputs/apk/demo/app-demo.apk</code>; package <code>com.robotemi.agent</code>; version <code>1.0.2 (3)</code>; SHA-256 <code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>. |
| Signing/build facts | Certificate SHA-256 <code>4D:A8:46:1B:45:B0:2F:AD:CB:04:2F:63:15:1F:EE:05:D5:6E:BD:51:05:EB:72:1D:7D:62:E3:0B:88:51:3A:7F</code>; schemes v1/v2; debuggable <code>NO</code>; embedded revision is the accepted baseline. |
| Observed target | <code>&lt;observed-private-deployment-address&gt;:5555</code>, classified <code>OBSERVED_AI6_DEPLOYMENT</code>; the address is intentionally redacted and is evidence only, not a portable default or tracked configuration. |
| Installed match | Package, version, hash, signer, embedded revision and whole APK match exactly: <code>EXACT_APK_MATCH</code>; existing install <code>ACCEPTED_AS_IS</code>. |
| Historical correction | E2DD is retained as the legacy 1.0.0 (1) acceptance artifact, not final 1.0.2 authority; L4.2 is <code>SUPERSEDED_BY_AUTHORITATIVE_LAB606_PROVENANCE_RECOVERY</code>. |

This closes Android artifact provenance and was the prerequisite for the later
L4 final adoption. The exact canonical TTS physical boundary is recorded in
the next section; broader Temi media/device behavior remains separate.

## L4 final physical acceptance adoption

The cumulative L4 evidence satisfies all 32 mandatory criteria. The adopted
source is <code>L4.7B_POST_REBOOT_SINGLE_CANONICAL_TTS</code>, whose final
status was <code>AI6_TEMIAGENT_L4_7B_POST_REBOOT_TTS_RESTORED</code>. No new
physical run is required and this documentation gate does not execute TTS,
MQTT, ADB, inference or any service operation.

The accepted artifact is package <code>com.robotemi.agent</code>, version
<code>1.0.2 (3)</code>, SHA-256
<code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>.
The existing installation was accepted as-is. L4.7B recorded current Android
MQTT session, LM <code>READY</code> with context <code>64000</code>, MQTT
<code>READY / REUSED</code>, and <code>HOST_L1=PASS</code>. One explicit
canonical speak action dispatched exactly once; Android ingress and validation
passed, one executor run produced one terminal <code>COMPLETED</code> TTS
callback, and the AI6 result was <code>success</code> with correlation
<code>PASS</code>. Model requests, movement, navigation, notification,
duplicate execution and retained command were all <code>0</code>/<code>NO</code>.
Rollback passed with zero host-owned processes and zero orphan listeners, and
LM, MQTT, Android state and canonical source were preserved.

The adopted decision is:

<code>FINAL_L4_CRITERIA_TOTAL=32</code>,
<code>FINAL_L4_CRITERIA_PASS=32</code>,
<code>FINAL_L4_CRITERIA_FAIL=0</code>,
<code>FINAL_L4_CRITERIA_UNRESOLVED=0</code>,
<code>L4_ANDROID_PROVENANCE=CLOSED_PASS</code>,
<code>L4_ANDROID_TEMI_E2E=CLOSED_PASS</code>,
<code>L4_FINAL=CLOSED_PASS</code>,
<code>ADDITIONAL_PHYSICAL_L4_RUN_REQUIRED=NO</code>.

The earlier TTS timeout and the successful post-reboot transaction used the
same SDK <code>1.134.1</code>, launcher <code>16405-usa / 16405</code>, accepted
APK and 30-second timeout; historical evidence also showed the same
SDK/launcher architecture completing TTS before the failed attempt. Vendor
ANR/runtime instability preceded the failure. A single normal human-performed
reboot restored vendor health and the terminal callback without an APK, SDK or
launcher change. The root-cause class is
<code>VENDOR_RUNTIME_TRANSIENT_STATE_REGRESSION</code>: strongly evidenced as
a transient vendor runtime state failure, with the exact internal vendor
component not directly observable.

The observed launcher is below the documented minimum
<code>18024</code>, so this is an
<code>UNSUPPORTED_OR_BELOW_DOCUMENTED_MINIMUM_DEPLOYMENT</code>. It is a
documented compatibility limitation, not the proven direct cause of this
regression. The evidence does not claim official compatibility and does not
require a Temi update for this handover; future deployments should prefer
vendor-supported launcher compatibility when feasible.

After the successful completion, Android emitted
<code>Canonical TTS resolved without an active speech action</code>. No second
dispatch, terminalization or result occurred. Classify this as
<code>SECONDARY_TTS_DIAGNOSTIC_WARNING=NON_BLOCKING_KNOWN_ISSUE</code>, possibly
a <code>STATE_MACHINE_DIAGNOSTIC_DEFECT</code>; it is not the timeout root
cause and is not remediated in this gate.

Only the exact canonical TTS physical boundary is closed. Future Android
actions require their own fresh evidence; video/media playback, camera/
microphone, general viewer/GPU behavior, Discord delivery, live perception
and other physical actions remain separate or unverified. Gate 6 readiness is
<code>READY_FOR_GATE6=YES</code> for release/handover work only.

## Preconditions and evidence vocabulary

Before a change, record branch, HEAD, worktree status, and the container root:

```bash
cd /TemiAgent
git branch --show-current
git rev-parse HEAD
git status --short
```

| Result | Meaning |
|---|---|
| PASS | The documented command completed successfully in the designated container. |
| FAIL | The command failed or showed a mismatch; preserve its concise evidence. |
| SKIPPED | The command needs unavailable hardware, credentials, a live external service, or explicit authorization. |
| NOT RUN | Intentionally outside this change's scope; it is not evidence. |

## Authoritative test matrix

Run project commands inside the designated container. The current
documentation/evidence adoption does not authorize live services, MQTT
publication, Android control, inference or Discord delivery. The adopted Gate 5
host result above is prior evidence, not a reason to rerun it.

| Test | Purpose | Command | Hardware required? | Network required? | GPU required? | Expected baseline | Failure meaning |
|---|---|---|---|---|---|---|---|
| Resident HTTP boundary tests | Inference-impossible malformed probe, valid-request compatibility, client disconnect and response-writer error boundaries. | <code>python3 -m unittest tools.tests.test_hermes_resident_http</code> | No | No | No | PASS with fake resident and local socket pairs only. | Resident validation or client-disconnect regression; no LM or service operation is authorized. |
| Tools suite | Cross-module helpers, lifecycle, bounded processes and test contracts. | <code>python3 -m unittest discover -s tools/tests</code> | No | No for the hardware-free tests | No | PASS for the current checkout and available external fixtures. | Preserve the first failing test; distinguish missing external checkout/environment from a regression. |
| Lifecycle unit tests | Config parsing, ownership, readiness, exact-PID and MQTT-only semantics. | <code>python3 -m unittest tools.tests.test_demo_lifecycle tools.tests.test_managed_mosquitto_supervisor</code> | No | No | No | PASS; no long-running service is required. | Lifecycle contract or fixture mismatch; do not repair by changing runtime state. |
| External dependency publication tests | Manifest, source boundary, generated checkout and no-fallback rules. | <code>python3 -m unittest tools.tests.test_external_dependency_publication</code> | No | No | No | PASS against tracked manifests and scripts. | Publication/reconstruction contract drift. |
| Bootstrap-focused tests | Bounded command behavior and source bootstrap safety. | <code>python3 -m unittest tools.tests.test_bounded_process tools.tests.test_external_dependency_publication tools.tests.test_hermes_submodule</code> | No | No | No | PASS; actual source bootstrap is a separate clean-clone operation. | Bootstrap safety or dependency-source regression. |
| Hermes submodule tests | Team URL, pinned gitlink/base/final tree and alternate-object policy. | <code>python3 -m unittest tools.tests.test_hermes_submodule</code> | No | No | No | PASS when the formal submodule contract is available. | Stop at the exact source identity failure; no upstream/local fallback. |
| Hermes license tests | Pinned license blob and checked-out license identity. | <code>python3 -m unittest tools.tests.test_hermes_license</code> | No | No | No | PASS for the manifest-declared MIT license. | Dependency is not publication-ready until provenance is resolved. |
| Bridge suite | Schemas, validation, path safety, action dispatch and contract behavior. | <code>cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests</code> | No | No | No | PASS with the locked Bridge environment. | Bridge/runtime contract or dependency issue; do not bypass validators. |
| Backend suite | Legacy ASR/video/VLM compatibility behavior. | <code>cd temi_backend && uv run --locked --offline pytest</code> | No | No | No | PASS with the locked backend environment. | Legacy module regression; it does not authorize a canonical lifecycle change. |
| Anomaly suite | Optional viewer/event-producer tests. | <code>cd anomaly_detection && uv run --locked --offline python -m unittest discover -s tests</code> | No | No | No | PASS with the locked anomaly environment. | Optional experimental path or dependency issue; no medical claim follows. |
| Mock E2E | Hardware-free Bridge/backend smoke route. | <code>python3 tools/e2e_test_runner.py</code> | No | No | No | PASS with local bounded doubles. | Software integration failure; it is not real Android acceptance. |
| Media fake E2E | Media v1.1 lifecycle, result linkage and replay with fake Android. | <code>python3 tools/media_v11_fake_e2e.py</code> | No | No | No | PASS with in-memory/local fakes. | Contract or fake-consumer regression; no real playback claim follows. |
| Documentation validation | Relative links, fences and reader-schema byte equality. | <code>python3 tools/validate_documentation.py</code> | No | No | No | PASS with zero broken links/schema drift. | Fix the referenced document or schema mapping; do not suppress the finding. |
| Shell syntax | Tracked shell parser validation. | <code>bash -n scripts/demo scripts/bootstrap scripts/bootstrap_hermes.sh scripts/bootstrap_llama_cpp.sh tools/start_lmstudio_3gpu.sh tools/validate_temi_e2e_stack.sh</code> | No | No | No | PASS for the checked entrypoints. | Shell syntax regression. |
| Python compilation | Syntax-only check for changed Python tools. | <code>python3 -m py_compile tools/hermes_resident_server.py tools/tests/test_hermes_resident_http.py tools/validate_documentation.py</code> | No | No | No | PASS without importing services. | Python syntax regression. |
| Clean-clone source bootstrap | Formal submodule plus ten-patch and llama reconstruction, including idempotency. | <code>./scripts/bootstrap --sources</code> twice after bounded submodule initialization | No | Yes for source acquisition | No | PASS in two independent clean clones; Gate 3 evidence is carried forward. | Missing publication URL, team source, environment or manifest identity; do not fall back. |
| Full production readiness | External LM Studio, Hermes, generated binaries, ports and configured runtime. | <code>./scripts/bootstrap --check</code> and read-only <code>./scripts/demo --json doctor</code> | No for checks; external service may be required | Provisioning-dependent | Production model path may require GPU | PASS only when every required check is healthy. | A missing external prerequisite is not a documentation or hardware-free test failure. |

Hardware-free PASS means only that the named software path passed. The adopted
L4 record separately closes one exact canonical Android/Temi TTS transaction;
camera/microphone, video/media playback, LM Studio model behavior, GPU
inference, Discord recipient delivery and live perception remain separate
external acceptance gates.

The preceding external-gate statement refers to general or separate
capabilities. The exact bounded Gate 5 host request and the separately adopted
single canonical TTS transaction are accepted above; neither generalizes to
camera/microphone, video/media playback, viewer/GPU behavior, Discord
recipient delivery or live perception.

## Gate 5B.1 non-live LM ownership remediation (historical)

Gate 5B stopped at its L1 ownership-safety gate after the managed LM path
issued global provider commands. The remediation selects external management
for production LM Studio because the local CLI/runtime cannot prove exclusive
ownership of a global daemon, server or model state. The corrected invariant is:

- pre-existing or foreign LM state is not owned by the lifecycle and is never
  stopped or globally cleaned up;
- lifecycle-owned processes exist only for the isolated newcomer mock, after
  positive process/port/readiness proof;
- production start requires one configured LM listener and a compatible HTTP
  model-list response, then starts only the other explicitly managed services;
- production stop preserves external/legacy LM records and fails closed with
  `STOP_INCOMPLETE_OWNERSHIP` when ownership is ambiguous.

The retired real-LM supervisor and startup helper are compatibility guards that
return a non-zero result without invoking `lms`. The fake-LM tests log attempted
subcommands and verify that normal start/stop and rejected compatibility paths
issue zero global cleanup commands. Historical Gate 5B PIDs are incident
evidence only; a future live retry must create a new process ledger. This
implementation status is `IMPLEMENTATION_REMEDIATED_NONLIVE`, not live proof.

## Gate 5B.3 Hermes compression failure-path remediation (historical)

Gate 5B's second attempt passed L0, L1, L2 and L3, then failed L5 after one
resident `/invoke` request. The retained failure evidence is: model request
count `0 -> 1` at the resident boundary, HTTP 500, three bounded compression
recovery attempts, and a missing `final_response` KeyError. No new live retry is
authorized by Gate 5B.3.

The source and deterministic measurements classify the trigger as
`MODEL/API_CONFIGURATION_MISMATCH`, not stale session state, oversized memory,
or a compression-threshold bug. Hermes was configured for a 64,000-token
context with a 32,000-token compression threshold, while the external LM
backend rejected an approximately 11,508-token request because its available
context was 4,096. The synthetic resident process used session
`temi-resident`, loaded no memory or checkpoint, and began with zero history.
Its one-turn message set had no removable middle; each of the three recovery
attempts therefore left the input unchanged and did not call the compression
summary model.

Patch `0010` gives exhausted compression results an explicit
`final_response: null` and typed bounded failure metadata. `AIAgent.chat()` now
raises that typed error rather than indexing a missing field. The resident
`/invoke` handler converts the typed error into an HTTP 500 response containing
only the allowlisted error class, original failure category and retryable flag;
provider text, prompts, payloads and tracebacks do not cross the boundary. The
normal successful response remains unchanged. This result is
`IMPLEMENTED_NONLIVE`, not `LIVE_VERIFIED`; an external owner must provision a
backend context compatible with Hermes before a separately authorized Gate 5B
retry.

## Gate 5B.5 resident probe and client-disconnect boundary (historical)

Gate 5B Retry #3 did not execute a valid malformed L2 probe. The exact request
was an HTTP `POST` to `/invoke` with `Content-Type: application/json`, a
five-second client timeout, and this body:

```json
{"prompt":"synthetic-invalid-active-resident"}
```

The body contained a valid non-empty `prompt` and omitted the optional
`active_resident` field. The resident therefore accepted the request, built an
invocation context with an empty resident ID, and called
`RequestHandler.do_POST()` → `ResidentHermes.invoke()` → Hermes/model. The
resident request count changed from `0` to `1`; the client disconnected before
the valid request completed. This event is
`L2_PROBE_FAILURE_CLASS=ACCEPTANCE_HARNESS_DEFECT`, not
`RESIDENT_VALIDATION_DEFECT`, and it is not L5 acceptance evidence. The event
must not be counted as a malformed-probe rejection or as a successful L5
model-request budget result.

The resident response path previously wrote the successful response, caught
the resulting `BrokenPipeError` in the broad invocation handler, logged an
invocation traceback, and attempted a second HTTP 500 response. The second
write raised another `BrokenPipeError`, producing an unhandled request-thread
traceback. The remediation catches only expected client transport disconnects
around the response emission, records a bounded log entry, and does not retry a
response on a closed socket. The resident does not cancel or roll back an
inference that already started. A normal response-writer exception remains an
error.

For a separately authorized future live retry, use the exact malformed request
below for L2. Its expected result is HTTP `400` with
`invalid active_resident`; validation must occur before
`ResidentHermes.invoke()`, with resident inference count `0` and LM HTTP call
count `0`:

```bash
cd /TemiAgent
curl -sS --max-time 5 -D - \
  -H 'Content-Type: application/json' \
  --data '{"prompt":"gate5b5-malformed-active-resident-probe","active_resident":"malformed"}' \
  http://127.0.0.1:8765/invoke
```

The future retry must use a 60-second timeout only for a valid L5 inference
request. Its model-request budget is exactly one request: L2 and L3 remain at
zero, and L5 may increase the count from zero to one. This Gate 5B.5 task does
not run that retry, start any resident, or contact LM Studio/MQTT.

## Documentation and source-structure checks

Run these for a documentation or comment-only change:

```bash
cd /TemiAgent
python3 tools/validate_documentation.py
git diff --check
git status --short
```

`validate_documentation.py` verifies tracked Markdown relative links, fenced
code blocks, and byte-equivalence of every mapped reader schema copy. It is not
a live command, model, Android, or Discord test.

Check shell syntax only for changed shell entrypoints:

```bash
bash -n scripts/demo scripts/bootstrap scripts/bootstrap_hermes.sh scripts/bootstrap_llama_cpp.sh
bash -n anomaly_detection/restart_action_viewer_8010.sh anomaly_detection/stop_action_viewer_8010.sh
```

Check changed Python files without importing or starting services:

```bash
python3 -m py_compile \
  tools/hermes_resident_server.py \
  tools/tests/test_hermes_resident_http.py \
  tools/validate_documentation.py
```

## Bootstrap and dependency boundary

```bash
cd /TemiAgent
./scripts/bootstrap --check
```

`--check` verifies the existing reconstructed source and provisioned dependency
environment. It is not a clean-clone source reconstruction, does not install
dependencies, and starts no service. For a clean source checkout, initialize
the formal Hermes submodule with the bounded `git submodule update --init
--recursive` command documented in the Hermes handover, then run
`./scripts/bootstrap --sources`. The command reconstructs the reviewed external
checkouts from manifests and must not be combined with an unreviewed
nested-checkout change.

## Software-only newcomer acceptance

The canonical ten-step clone and environment order is
[developer_setup.md](developer_setup.md). The acceptance sequence below is
the separate, explicitly authorized software-only runtime test after that setup
has completed; it is not a replacement setup path.

This is the reproducible, fresh-clone acceptance for a maintainer with no
prior conversation context. It uses the tracked `newcomer_mock` sample and the
same `scripts/demo` lifecycle as the normal profile. It is not real Temi,
Android, GPU, camera, model, or Discord acceptance.

In a disposable clone, run the documentation check *before* reconstructing
Hermes, then bootstrap twice to prove idempotency. Substitute the canonical
repository URL only at clone time; do not place a private URL in the sample.

```bash
git clone <canonical-repository-url> TemiAgent-newcomer
cd TemiAgent-newcomer
python3 tools/validate_documentation.py
python3 tools/run_bounded_process.py --timeout-seconds 120 --kill-grace-seconds 2 -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --sources
./scripts/bootstrap --sources

cd hermes_temi_bridge && uv sync --frozen --extra mqtt
cd ../anomaly_detection && uv sync --frozen
cd ..

./scripts/demo init-config
./scripts/demo --json doctor
./scripts/demo --json start
./scripts/demo --json start
./scripts/demo --json status
./scripts/verify_newcomer_mock
./scripts/demo --json restart
./scripts/demo --json stop
```

`verify_newcomer_mock` is a verifier, not an orchestrator: it requires the
already-started lifecycle services, submits canonical events to the existing
Bridge, invokes the Bridge media callback, observes canonical command results,
and writes its evidence below the configured acceptance root. Its scenarios
cover general ASR-to-TTS, reminder completion, discomfort and abnormal
care-first responses, affirmative/decline/timeout consent, media
play/pause/resume/stop, the local Discord failure matrix, and unsupported
action defense. A second `start` must report reused ownership. `restart` must
archive pre-restart evidence and reuse the same exact-PID ownership rules;
`stop` must leave every configured mock port without a listener.

### Production reminder acceptance precondition

The production reminder phrase is valid only after the operator seeds one isolated synthetic active reminder in the confirmed resident partition and confirms `CARE_CONTEXT_ENABLED=true`.
The authoritative action contract still requires the exact non-empty `reminder_id`; the Bridge never resolves an arbitrary ID from speech.

Focused cases:

- R2: one matching active reminder. Expect `mark_reminder_done` with that exact ID, one `log_event`, a speak command/result, and status `completed`.
- R3: no active reminder, or multiple possible matches. Expect a resident-friendly clarification speak command/result and no memory mutation.
- A run without the R2 seed is `INVALID_ACCEPTANCE_PRECONDITION`, not a reminder-contract or Android transport failure.

### Viewer lifecycle failure fixture

Run this fixture only in a disposable `newcomer_mock` acceptance root after the
normal successful start/stop sequence. It deliberately makes the mock viewer
return `/health` HTTP 500; it does not start a real viewer, model, broker,
Android App, or Discord route. The expected result is a non-zero `start`, a
persisted `START_FAILED` lifecycle state with rollback evidence, and no
listener on any configured mock port after the rollback and after `stop`.

```bash
failure_config="$acceptance_root/config/demo.mock.viewer-health-failure.env"
cp "$config" "$failure_config"
printf '%s\n' 'DEMO_TEST_FORCE_HEALTH_FAILURE_SERVICE=viewer' >> "$failure_config"
chmod 600 "$failure_config"

set +e
./scripts/demo --config "$failure_config" --json start
start_rc=$?
set -e
test "$start_rc" -ne 0
./scripts/demo --config "$failure_config" --json status
./scripts/demo --config "$failure_config" --json stop

for port in 29134 29183 29080 29081 29765 29010 29011 29012 29013; do
  ! ss -ltn "sport = :${port}" | grep -q LISTEN
done
```

`DEMO_TEST_FORCE_HEALTH_FAILURE_SERVICE=viewer` is accepted only for the
`newcomer_mock` viewer fixture. It is not a production configuration option.
Do not remove the retained `START_FAILED` state before collecting its redacted
ownership and rollback evidence.

Bootstrap reconstructs the reviewed Hermes integration branch and the pinned
llama.cpp checkout from tracked manifests. Both generated checkouts are ignored
external dependencies, so a successful fresh-clone reconstruction leaves the
root repository clean. The lifecycle rejects every non-runtime source
difference; nested checkout cleanliness and manifest tree verification remain
separate bootstrap gates.

Record the JSON results, scenario summary, exact PID records, and a final
loopback-port inventory in the private acceptance root. Do not delete the root
to conceal a failure, and do not convert mock delivery to a claim about a real
Discord recipient.

## Hardware-free test matrix

Run the narrowest relevant command first, then the wider checks appropriate to
the changed area.

| Area | Command | What it covers |
|---|---|---|
| Bridge contracts and safety validation | `cd /TemiAgent/hermes_temi_bridge && uv run python -m unittest discover -s tests` | Event/path/action validation, traces, memory/demo boundaries, media contract and mock integrations. |
| Legacy backend | `cd /TemiAgent/temi_backend && uv run pytest` | Backend, MQTT bridge, overview adapter and frame-buffer behavior. |
| Demo lifecycle/resident wrapper | `cd /TemiAgent && python3 -m unittest discover -s tools/tests` | Lifecycle config, atomic `STARTING` ownership records, health-gate rollback, stop ownership refusal, doctor checks, resident health and LM Studio helper behavior. |
| Action viewer parser/unit behavior | `cd /TemiAgent/anomaly_detection && uv run python -m unittest discover -s tests` | Viewer notification normalization, component health, internal-error safety, receipts and local test seams; no model service starts. |
| Root mock E2E | `cd /TemiAgent && python3 tools/e2e_test_runner.py` | Local mock canonical event-to-command route. |
| Media v1.1 fake Android | `cd /TemiAgent && python3 tools/media_v11_fake_e2e.py` | Request/result correlation, lifecycle, replay and trace in-process. |
| Pinned Hermes compressor | `cd /TemiAgent/hermes-agent && venv/bin/python -m pytest tests/agent/test_context_compressor.py` | Nested overlay compressor behavior, when the pre-existing nested environment is provisioned. |

## Immediate abnormal-care validation

The abnormal-care flow is implemented in the Bridge and has separate
hardware-free and external evidence requirements. Run the focused test before
the wider matrix when the episode, notification, schema, or viewer boundary
changes:

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest \
  tests.test_care_episode \
  tests.test_abnormal_notification \
  tests.test_abnormal_care_confirmation \
  tests.test_event_validation \
  tests.test_cross_service_contract_schemas
```

The focused suite verifies canonical abnormal types, persistent episode and
stage deduplication, Resident Hermes invocation, validated speak commands,
mock receipts, restart handling, no-response escalation, and the isolated
HTTP 204/401/403/404/429/timeout/connection matrix. It does not establish
real Android execution or real Discord delivery.

For a Demo mock lifecycle run, start the configured lifecycle and use the
formal injector instead of publishing an MQTT command by hand:

```bash
cd /TemiAgent
./scripts/demo --config <PRIVATE_CONFIG> doctor
./scripts/demo --config <PRIVATE_CONFIG> start
./scripts/inject_demo_event \
  --config <PRIVATE_CONFIG> \
  --event falls_down \
  --resident-id <TEST_RESIDENT> \
  --run-id <RUN_ID> \
  --scenario-id A1
./scripts/verify_newcomer_mock --config <PRIVATE_CONFIG>
./scripts/demo --config <PRIVATE_CONFIG> stop
```

The private configuration MUST select the explicit Demo mock notification
route and test ingress. Retain the Bridge trace, episode state, mock receipt,
canonical `cmd/request`, matching mock Android `cmd/result`, and final
lifecycle stop evidence below the private acceptance root. A mock receipt is
not real Discord delivery evidence.

The operator should record command output, test count when available, and any
environment prerequisite. A passed mock E2E is not a claim that the robot,
camera, model, or Discord was live.

## External acceptance gates

These are separate, authorization- and dependency-dependent activities:

| Gate | Required evidence | Do not infer from |
|---|---|---|
| LM Studio / GPU | Service health plus the configured model/context/GPU policy. | A script existing or a unit test passing. |
| MQTT / resident / Bridge | Exact lifecycle identity, endpoint health, and relevant trace. | A listener alone. |
| Android artifact provenance | External source revision, final APK identity/hash/signer, installed-package match and explicit artifact-vs-device disposition. | A binary mismatch against an incorrectly classified historical artifact, a Bridge publish, or a browser/terminal log. |
| Exact canonical TTS command execution | The adopted L4.7B evidence: current Android MQTT session, one speak dispatch, terminal TTS callback, successful `cmd/result`, correlation and device observation. | Bridge publish or a browser/terminal log without Android execution evidence. |
| Future Android command execution | A fresh Android MQTT session, `cmd/result` lifecycle response and device observation for each newly authorized action. | The adopted single TTS transaction, a Bridge publish or a browser/terminal log. |
| Media playback | Accepted/started or playing result plus visible device playback. | Native callback acceptance or request publication. |
| Viewer perception | Authorized model/input run and bounded evidence. | Parser tests or a health endpoint. |
| Discord side channel | Provider-side delivery acknowledgement and approved target context. | Gateway health, credential configured, or a webhook request attempt. |

Mark every unavailable external gate `SKIPPED`, including reasons such as no
robot, no Android owner, no private credential, no live broker, no GPU/model,
or no explicit authorization. Discord and caregiver notification remain
best-effort Demo behavior, never emergency-service evidence.

## Handoff checklist

- Verify the README/module documentation matches the executed code and sample
  configuration.
- Compare every authoritative schema with its reader copy.
- Search changed documentation for secrets, personal paths, obsolete worktree
  instructions, and unsupported capability claims.
- Inspect the complete diff, `git diff --check`, and final `git status --short`.
- State files changed, source/runtime scope left untouched, actual PASS/FAIL/
  SKIPPED commands, coverage gaps, branch, HEAD, and commit IDs.
