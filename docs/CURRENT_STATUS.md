# TemiAgent Current Status

狀態：CURRENT；governance snapshot：2026-08-29。

This page is the maintained status snapshot for implementation, verification,
runtime honesty and publication blockers. It is not a runtime health endpoint and
does not replace the runtime schemas, module READMEs or the
[canonical Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).

## Gate 5 final evidence adoption (current authority)

Review date: 2026-08-29. This section adopts the separately completed Gate 5B
Retry #4 evidence; it is a documentation/evidence freeze and does not rerun
the live acceptance. The publication baseline for the evidence candidate was
<code>release/github-v1@59d568b079ce260e2144c410b0f9397d8b026913</code>.

### Frozen gate disposition

| Gate / boundary | Final status | Boundary |
|---|---|---|
| Gate 5A | <code>CLOSED_PASS</code> | Read-only environment and publication/runtime reconciliation is retained as historical evidence. |
| Gate 5A.1 runtime delta reconciliation | <code>CLOSED_PASS</code> | The intended publication/runtime delta is reviewed and adopted in the publication candidate. |
| Gate 5B.1 LM ownership remediation | <code>CLOSED_PASS</code> | Production LM Studio is external-only; the lifecycle has no real-provider start/stop/unload/daemon-down path. |
| Gate 5B.3 Hermes compression remediation | <code>CLOSED_PASS</code> | Patch 0010 and the structured resident failure boundary are included in the accepted Hermes reconstruction. |
| Gate 5B.5 resident probe safety | <code>CLOSED_PASS</code> | L2 validation is inference-impossible and client disconnects do not trigger a second response. |
| Gate 5B live runtime acceptance | <code>CLOSED_PASS</code> | Retry #4 passed the bounded host L0–L3 and L5 contract; L4 was not run by scope. |
| Gate 5 host runtime | <code>CLOSED_PASS</code> | The exact publication/runtime contract is host-live accepted, not a physical-device or portable-environment claim. |
| L4 Android artifact provenance | <code>CLOSED_PASS</code> | LAB606 evidence identifies the installed Android APK as the accepted final 1.0.2 (3) artifact; this does not claim physical execution. |
| L4 Temi physical/E2E acceptance | <code>NOT_RUN_BY_SCOPE / SEPARATE_GATE</code> | Android behavior, device session, physical playback and physical observation remain external. |
| Gate 6 | <code>NOT_STARTED</code> | No Gate 6 work is implied by this adoption. |

### Accepted host evidence

| Contract | Accepted observation |
|---|---|
| Hermes reconstruction | Pinned base plus patches <code>0001</code>–<code>0010</code>; patch <code>0010</code> SHA-256 <code>6588e4227d82a83f9189c6aada977e5018e79a43134139a8361a857d59967272</code>; final tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>. |
| Production LM ownership | <code>EXTERNAL_ONLY</code>; expected model <code>google/gemma-4-31b</code> for model API identity, provisioned model <code>temi/gemma-4-31b-it-qat</code>; runtime context <code>64000</code>; observed model maximum <code>262144</code>. |
| LM lifecycle safety | External LM was ready before Demo start and was preserved; the lifecycle did not start, stop, unload, daemon-down, server-stop or globally mutate it. Context was verified from runtime metadata, not configuration alone. |
| MQTT | Existing broker was reused and not restarted; one accepted listener was <code>0.0.0.0:1883</code>. Explicit broker configuration and independent ownership remain mandatory. |
| Layer results | L0 PASS; L1 PASS; L2 PASS; L3 PASS; L4 Android provenance CLOSED_PASS; L4 Temi E2E NOT_RUN_BY_SCOPE; L5 PASS. |
| Model-request budget | <code>L1=0; L2=0; L3=0; L5=1</code>, recorded invariant <code>0 → 0 → 0 → 1</code>. |
| L2 malformed probe | Controlled HTTP 400 validation failure before resident invocation; inference calls <code>0</code>. |
| L3 no-op path | Bridge Unix callback produced validated MQTT identity-result publication on <code>temi/temi-01/resident/identity/result</code>; physical side effect <code>NO</code>. |
| L5 bounded request | HTTP 200; approximately <code>14.225686 s</code> curl time and <code>14222 ms</code> resident time; response validation PASS with one <code>speak</code> action. |
| L5 failure guards | No context overflow, compression exhaustion, <code>final_response</code> KeyError, BrokenPipe, secondary 500 or unexpected runtime error; resident health after the request PASS. |
| Rollback | Gate-owned processes and listeners remaining: <code>0</code>; LM and canonical MQTT were preserved; canonical source was preserved. |

### Failed attempts retained as causal history

The failed attempts remain important because they explain the frozen contract:

1. Attempt 1 failed LM ownership safety because the managed lifecycle issued
   global LM operations against pre-existing <code>llmster</code> state. The
   resolution was production <code>EXTERNAL_ONLY</code> ownership.
2. Attempt 2 passed L0–L3 but failed L5 because the external runtime context
   was <code>4096</code> while Hermes/resident required <code>64000</code>; an
   approximately <code>11508</code>-token request exhausted compression and
   exposed the missing <code>final_response</code> contract. The resolution was
   external reprovisioning, patch 0010 and the structured resident failure
   boundary.
3. Attempt 3 exposed an acceptance-harness defect: its supposed malformed
   probe contained a valid prompt and triggered inference. The five-second
   disconnect then exposed the BrokenPipe/secondary-500 boundary. The
   resolution was the inference-impossible L2 probe, disconnect hardening and
   the exact one-request L5 budget.
4. Attempt 4 is the final host acceptance and passed L0–L3 and L5.

Two setup-only starts before the accepted run also failed safely because the
Hermes virtual-environment executable was missing and an AF_UNIX socket path
was too long. Both rolled back before acceptance, changed no tracked
source/config and are troubleshooting prerequisites, not final runtime
failures. Verify <code>hermes-agent/venv/bin/python3</code> and
<code>hermes-agent/venv/bin/hermes</code> before a start, and choose a short
owner-only runtime/socket root that satisfies Unix-domain socket limits.

### Portable versus transient evidence

PIDs, run IDs, temporary worktrees and transient runtime directories are
<code>ACCEPTANCE_EVIDENCE_ONLY</code>; they are not universal requirements.
The portable contract is external-only production LM ownership, runtime
metadata context <code>64000</code>, the expected model identifier, the Hermes
base-plus-ten-patch tree, private runtime-root permissions, explicit broker
configuration and the exact request-budget boundary. The lifecycle stops only
processes it owns; pre-existing LM/MQTT processes are foreign or external
unless positive identity evidence proves otherwise.

This adoption changed documentation/evidence only. It did not change runtime
source, runtime behavior, configuration values, Hermes patches, model context,
MQTT state or canonical <code>main</code>. No service operation, inference,
MQTT publish/subscribe, Android/Temi action, push, merge, rebase or history
rewrite was performed by the adoption gate.

## L4.3 Android provenance adoption (current authority)

Review date: 2026-08-29. This documentation/evidence adoption records the
authoritative LAB606 result <code>LAB606_ANDROID_FINAL_ARTIFACT_PROVENANCE_CONFIRMED</code>.
It does not run ADB, install or replace an APK, reset device data, operate
Android, operate Temi, operate MQTT, or change Android source. The Android
source repository and artifact were supplied as external evidence; the exact
host-local source path is intentionally not reproduced here.

### Final artifact and installation match

| Field | Accepted evidence |
|---|---|
| External source | Repository <code>temi-agent-android-public</code>, branch <code>main</code>, current revision <code>3e2fc0376e5b5ca3992e697fc030cdc08173c639</code>; accepted baseline <code>8c458888657efca5384c6d51e5ec57e8b385d987</code> is an ancestor, with no post-baseline implementation, build-config or signing changes. |
| Artifact | <code>temi-agent-android-public/app/build/outputs/apk/demo/app-demo.apk</code>; package <code>com.robotemi.agent</code>; version <code>1.0.2 (3)</code>. |
| APK SHA-256 | <code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>. |
| Signing | SHA-256 certificate <code>4D:A8:46:1B:45:B0:2F:AD:CB:04:2F:63:15:1F:EE:05:D5:6E:BD:51:05:EB:72:1D:7D:62:E3:0B:88:51:3A:7F</code>; schemes v1 and v2; debuggable <code>NO</code>. |
| Embedded revision | Accepted baseline <code>8c458888657efca5384c6d51e5ec57e8b385d987</code>. |
| Observed target | <code>192.168.50.204:5555</code>, classification <code>OBSERVED_AI6_DEPLOYMENT</code>; this is evidence only and is not a portable default or tracked configuration. |
| Installed package | Package, version, APK hash, signer and embedded revision exactly match the final artifact; whole-APK match <code>YES</code>; relation <code>EXACT_APK_MATCH</code>. |

The final disposition is <code>ANDROID_PROVENANCE=CLOSED_PASS</code> and the
existing install was <code>ACCEPTED_AS_IS</code>; no replacement, reinstall or
data reset occurred. The earlier
<code>AI6_TEMIAGENT_L4_2_ANDROID_IMPLEMENTATION_MISMATCH</code> correctly
reported that the installed 1.0.2 payload differed from the then-used E2DD
reference, but that reference was later classified as the legacy 1.0.0 (1)
acceptance artifact. It is superseded by
<code>SUPERSEDED_BY_AUTHORITATIVE_LAB606_PROVENANCE_RECOVERY</code>, not erased
from historical records.

<code>L4_ANDROID_PROVENANCE=CLOSED_PASS</code> and
<code>READY_FOR_L4_E2E=YES</code>. Temi physical execution, playback, device
observation and the complete L4 E2E remain <code>NOT_YET_RUN</code>;
<code>READY_FOR_GATE6=NO</code>. The accepted Gate 5 host runtime remains
bounded to L0–L3 and L5.

## Gate 4.1 handover repair candidate (historical)

The rejected Gate 4 documentation candidate is
<code>d0e6a4ebe162363e58dcc3146d80d679151d2a75</code>, derived from
<code>release/github-v1@d66a046395aed21712b00cba43d4ea1b2d9f23de</code>.
Gate 4.1 repairs its documentation-contract findings and restores the protected
synthetic fixture to the publication-base bytes in the isolated
Gate 4.1 handover-repair worktree on branch
<code>codex/github-v1-handover-contract-fix</code>. The repair changes
documentation and that protected fixture only. It does not advance
<code>release/github-v1</code>, modify canonical <code>main</code>, operate
services, publish MQTT or push.

## Gate 5A live environment audit (historical pre-live snapshot)

Audit date: 2026-08-28. The facts in this section are an observed deployment
snapshot, not portable version pins and not the final live-acceptance claim;
the current bounded host acceptance is recorded above. Project
commands were run in the designated <code>yiting.TemiAgent_gpu_all</code>
container at <code>/TemiAgent</code>. Host environment and Docker metadata
inspections were the explicit host-side provenance exception; they read
metadata only.

### Observed deployment provenance

| Boundary | Observed fact | Contract interpretation |
|---|---|---|
| Canonical checkout | Host checkout path is withheld from public docs; it is mounted at <code>/TemiAgent</code>; root branch <code>main</code>; HEAD <code>12aff3bfdfe526c17a25a2681aea2afad7112b33</code>. | Deployment callout only; generic clones use the maintainer-supplied <code>REPO_ROOT</code>. |
| Host | Ubuntu 22.04.5 LTS, kernel <code>5.15.0-190-generic</code>, x86_64; 224 logical CPUs; 251 GiB RAM; the checkout is on an XFS filesystem. | Host provisioning is external and not pinned by AI6. |
| Container | Image <code>pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel</code>; observed image ID <code>sha256:aa15d38ee3a80d13fedc574c5505e6ea173af546b61d5161d674c17e8641961d</code>; host network mode; read-write project bind mount; all GPUs requested. | The image ID/digest is evidence for this deployment, not a checked-in image pin. |
| Host Docker | Docker client/server <code>29.3.0</code>. | Host-owned prerequisite; no Docker CLI is installed in the project container. |

Observed container toolchain: Python <code>3.12.3</code>, uv
<code>0.10.12</code>, Git <code>2.43.0</code>, Bash <code>5.2.21</code>,
Mosquitto <code>2.0.18</code>, curl <code>8.5.0</code>, iproute2/ss
<code>6.1.0</code>, CMake <code>4.2.3</code>, Ninja
<code>1.13.0.git.kitware.jobserver-pipe-1</code>, Make <code>4.3</code>, and
GCC/G++ <code>13.3.0</code>. jq, lsof and clang were not installed in the
container. These are observed values; only the Python floors and checked-in
lockfiles are repository contracts.

The container exposed four NVIDIA GeForce RTX 5090 devices, each reporting
32607 MiB, compute capability 12.0, driver <code>580.142</code> and CUDA
<code>13.0</code>; nvcc reported <code>13.0.88</code>. The production template
names LM Studio devices <code>0,1</code> and viewer/pose device
<code>3</code>; the observed container had <code>NVIDIA_VISIBLE_DEVICES=all</code>
and no explicit <code>CUDA_VISIBLE_DEVICES</code>. No inference was run.
GPU, driver, CUDA and model policy remain environment pin gaps.

### Source, environment and artifact readiness

| Area | Gate 5A observation | Status |
|---|---|---|
| Source bootstrap | <code>./scripts/bootstrap --check</code>, <code>./scripts/bootstrap_hermes.sh --check</code> and <code>./scripts/bootstrap_llama_cpp.sh --check</code> passed in the canonical container. Hermes final tree is <code>968f1668a05fafd09461c17a835198421f14a48f</code>; llama.cpp is commit <code>0b7154066e8544ed88d92ae2132cc1e055cf6304</code>, tree <code>1020a771795f406b8891d18ee607b4da3783fa7f</code>. | Source readiness PASS for the canonical deployed checkout. |
| Hermes runtime | <code>hermes-agent/venv</code> uses Python <code>3.11.15</code>; the reconstructed checkout is clean. | Environment exists; runtime version is not a portable pin. |
| llama.cpp build | Existing cache reports Release/Ninja, <code>GGML_CUDA=ON</code>, CUDA compiler <code>/usr/local/cuda/bin/nvcc</code> and native CUDA architecture; the configured <code>llama-server</code> executable exists. No build or rebuild was run. | Binary/build evidence observed; build flags remain an environment reproducibility input. |
| Model assets | The configured Gemma GGUF, <code>mmproj-F32.gguf</code>, optional pose weight and llama-server binary are present in the local runtime. Model/cache and pose provenance are external; no model inference was run. | Artifact presence PASS; provenance/live behavior NOT_VERIFIED. |
| Private configuration | The canonical ignored Demo env and runtime Mosquitto config were present with mode <code>0600</code>; values were not printed. No private value is part of this candidate. | Private-file boundary PASS. |

The canonical production template still requires externally provisioned LM
Studio/model state, the Hermes environment, viewer model files and optional
pose provenance. A clean clone does not imply any of those bytes.

### Runtime observation and safety incident

The read-only canonical MQTT selector reported <code>RUNNING / READY</code>:
one valid managed broker listener on <code>0.0.0.0:1883</code>, successful
local TCP readiness, and a valid recorded supervisor/child contract. No MQTT
restart is required for this audit, and the broker must remain untouched while
the publication delta is reviewed.

The full-stack <code>./scripts/demo doctor</code> reported
<code>BACKEND_NOT_READY</code>. Its required repository check reflects the
pre-existing dirty canonical worktree; LM Studio <code>1234</code>, resident
<code>8765</code> and viewer <code>8010</code> were not available, while the
full-profile port check sees the already-running MQTT-only listener as a
full-profile conflict. This is not evidence to stop or restart MQTT. Android,
physical Temi, live model behavior, real perception and Discord delivery were
not verified.

Audit incident: an attempted non-inference model inventory command,
<code>/TemiAgent/.lmstudio-data/bin/lms ls</code>, unexpectedly woke the
packaged <code>llmster</code> internal component. No LM Studio API listener
appeared on <code>1234</code>, no inference or MQTT publish/subscribe occurred,
and no explicit service-start command was issued. The process was intentionally
left for a separately authorized operator decision because this gate forbids
stopping LM Studio. No further <code>lms</code> command is part of this audit.

The incident record is intentionally redacted to public-safe identity and
paths:

| Field | Record |
|---|---|
| <code>incident_id</code> | <code>AI6-GATE5A-LMSTUDIO-PROBE-20260828</code> |
| <code>start_time_utc</code> | <code>2026-08-28 03:34:00Z</code> observed process start |
| <code>environment</code> | Designated AI6 container and canonical project root |
| <code>affected_service_and_users</code> | Packaged LM Studio internal component; no Android, Temi or MQTT consumer impact observed |
| <code>event_id / trace_id / run_id</code> | None for the probe; the MQTT-only run identity remains in private lifecycle state |
| <code>confirmed_symptoms</code> | <code>lms ls</code> returned after waking <code>llmster</code>; it owned loopback <code>127.0.0.1:41343</code>, while API <code>1234</code> remained unavailable |
| <code>exact_identity</code> | <code>comm=llmster</code>, owner <code>root</code>, PPID <code>1</code>, executable/cwd under <code>/TemiAgent/.lmstudio-data/llmster/0.0.15-2</code>; its <code>systemresourcesworker</code> child was also observed |
| <code>containment</code> | No further LM Studio CLI calls; no signal, inference, MQTT publication/subscription or hardware action |
| <code>rollback_or_recovery</code> | Not executed; stopping the exact process requires a separately authorized operation |
| <code>post_recovery_verification</code> | No recovery is claimed; read-only checks confirmed no <code>1234</code> listener and MQTT remained <code>RUNNING / READY</code> |
| <code>protected_services_checked</code> | MQTT exact lineage/status, listener inventory, and production ports were checked; no MQTT transition was performed |
| <code>evidence_paths</code> | Private lifecycle state/log paths under <code>&lt;runtime-root&gt;</code> plus the redacted audit command transcript; no raw payload or credential was retained in Git |
| <code>root_cause</code> | The packaged <code>lms</code> inventory command has a daemon-wake side effect |
| <code>contributing_factors</code> | Its side effect was not apparent from the read-only audit intent or command name |
| <code>preventive_work</code> | Gate 5B must use HTTP model-list health and lifecycle evidence only; no <code>lms</code> CLI inventory probe in a read-only gate |
| <code>unverified_gaps</code> | LM Studio semantic version, API/model readiness, and final operator disposition of the resident internal component |

### Publication/runtime parity

The commit trees <code>main@12aff3bfdfe526c17a25a2681aea2afad7112b33</code>
and <code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>
are not the same lineage and differ in 82 paths. The publication contains a
behavior-affecting runtime delta, so the classification is
<code>C — PUBLICATION_HAS_BEHAVIORAL_RUNTIME_DELTA</code>. The focused delta
includes:

- <code>tools/temi_overview_adapter.py</code>: the broker must be supplied by
  <code>--broker</code> or <code>TEMI_MQTT_BROKER</code>; the private-LAN default
  is removed and missing input fails closed.
- <code>tools/start_temi_pc_services.sh</code> and its background helper:
  <code>PC_IP</code> is required instead of defaulting to a private LAN address.
- <code>config/demo_resources.json</code>, <code>.gitmodules</code> and the
  <code>hermes-agent</code> gitlink: external resource and formal-submodule
  contracts are present in the publication.
- The Hermes/llama bootstrap manifests and bounded-process/source-verification
  tools are publication inputs; the canonical <code>main</code> tree does not
  contain all of those files.

The exact 21 executable/runtime/config/dependency/test paths in that commit-tree
delta are:

| Boundary | Exact paths |
|---|---|
| Publication boundary and external artifact removal | <code>.gitignore</code>; <code>anomaly_detection/yolo26x-pose.pt</code> (removed from the publication tree) |
| Formal Hermes and llama source/reconstruction | <code>.gitmodules</code>; <code>hermes-agent</code> gitlink; <code>scripts/bootstrap_hermes.sh</code>; <code>scripts/bootstrap_llama_cpp.sh</code>; <code>third_party/hermes/manifest.json</code>; <code>third_party/llama_cpp/manifest.json</code> |
| Runtime/config behavior | <code>config/demo_resources.json</code>; <code>tools/temi_overview_adapter.py</code>; <code>tools/start_temi_pc_services.sh</code>; <code>tools/start_temi_pc_services_background.sh</code> |
| Bounded source-verification helpers | <code>tools/bounded_process.py</code>; <code>tools/run_bounded_process.py</code>; <code>tools/verify_hermes_license.py</code>; <code>tools/verify_hermes_submodule.py</code> |
| Test-only coverage | <code>temi_backend/tests/test_overview_adapter.py</code>; <code>tools/tests/test_bounded_process.py</code>; <code>tools/tests/test_external_dependency_publication.py</code>; <code>tools/tests/test_hermes_license.py</code>; <code>tools/tests/test_hermes_submodule.py</code> |

All other paths in the 82-path comparison are documentation/governance or
reviewed memory-fixture changes; they do not add executable runtime behavior.

The MQTT lifecycle implementation, tracked broker configuration and MQTT-only
status contract are unchanged in the inspected runtime delta. Reusing the
currently healthy MQTT broker as an external Gate 5B dependency is therefore
the safe default; do not restart it merely to align other publication files.

### Gate 5B strategy and blockers (not executed here)

The initial Gate 5A plan named an isolated clone/worktree of
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>.
Gate 5A.1 supersedes that source-root instruction: any later Gate 5B run must
use the final reviewed Gate 5A.1 candidate commit in an isolated worktree,
while retaining the release ref as the reviewed publication baseline.
Reconstruct Hermes and llama.cpp from their manifests, install the locked
module environments, and retain the candidate separate from canonical
<code>main</code>. Before any authorized service operation, capture exact
source/config/port/PID evidence and provision LM Studio/model/GPU externally.
The API model-list check must identify <code>google/gemma-4-31b</code> with
context <code>64000</code> and the configured GPU policy; a process or model
file alone is insufficient.

The sequence is: read-only preflight; LM Studio health/model-list gate; reuse
the existing MQTT broker without restart (or use a separately isolated
high-port broker); adapter; resident; Bridge; gateway; viewer; then synthetic
software-only/no-op contract checks. Physical Android/Temi actions, real
notification delivery and model inference require their own explicit owner
authorization and evidence. Rollback must use the lifecycle's recorded exact
identities in reverse order and preserve the canonical MQTT service.

#### Gate 5B dependency graph

~~~text
approved container + locked module environments
  -> Hermes submodule base + root-owned overlay -> patched Hermes runtime ─┐
LM Studio model/API + GPU policy ──────────────────────────────────────────┼-> resident Hermes health/invoke
                  -> HermesTemiBridge validation and dispatch
                      -> MQTT command request
                          -> external Temi Android executor
                              -> MQTT command result -> Bridge trace
MQTT broker -> Overview adapter -> canonical ASR event -> Bridge
adapter frame broadcast + viewer GGUF/mmproj + llama-server
  -> optional experimental action viewer -> abnormal event -> Bridge
patched Hermes runtime + external provider credentials
  -> optional Hermes gateway (health is not notification delivery)
~~~

The default broker dependency is the already verified external listener on
<code>0.0.0.0:1883</code>; it is not restarted for Gate 5B. If broker
ownership itself must be tested, use a disposable, separately reviewed
<code>newcomer_mock</code> configuration with its isolated loopback
<code>29183</code> listener and a separate runtime root. Do not silently
override the production port or attach a second owner to <code>1883</code>.

#### Gate 5B acceptance and rollback matrix

| Stage / owner | Required evidence before advancing | Side effect and rollback boundary |
|---|---|---|
| Source/config preflight — maintainer | Isolated clean candidate at the reviewed release ref; formal Hermes/llama tree and license checks; frozen environments; private config metadata; no alternate objects | No service or MQTT operation. Discard only the isolated candidate after evidence review. |
| LM Studio — external LM/runtime owner | <code>GET /v1/models</code> succeeds; identifier <code>google/gemma-4-31b</code>, context <code>64000</code>, configured GPU policy, and exactly one compatible listener on port <code>1234</code> agree | AI6 does not start, stop, unload, or reconfigure production LM Studio. Preserve external state and create a fresh ownership ledger on any future retry. |
| MQTT — AI6 operator | Either read-only <code>./scripts/demo --json mqtt status</code> proves the external <code>1883</code> lineage, or the disposable <code>29183</code> profile proves its own exact managed lineage and TCP readiness | Default has no transition. An isolated broker may be stopped only through its exact owner record, never by name or port alone. |
| Adapter/resident/Bridge — AI6 service owner | Adapter listeners <code>8080/8081</code>, resident <code>/health</code> on <code>8765</code>, Bridge callback socket, exact PIDs, and redacted logs all pass; synthetic no-op route remains validator-bound | Start in canonical order only after authorization. Roll back in reverse exact-PID order; do not bypass Bridge with raw commands. |
| Gateway/viewer — optional owners | Gateway health/status, viewer <code>/health</code> on <code>8010</code>, llama listener <code>8011</code> and model/resource checks pass when enabled | Optional and no Discord claim. Stop exact recorded identities in reverse order; keep the main route separately classified. |
| Synthetic software-only acceptance — verification owner | Canonical event/trace and no-op contract checks pass without physical Android, real notification or unrestricted model inference | Use the isolated runtime/evidence root only; no raw MQTT command/result fabrication and no change to canonical MQTT. |
| Android/Temi acceptance — device owner | Fresh Android session, subscription, accepted/started or playing result, and physical observation for each authorized action | Separate hardware authorization and device-owner rollback. A Bridge publish alone cannot advance this stage. |
| Rollback — lifecycle owner | Final redacted status, protected-port inventory, exact lifecycle records and retained evidence | Reverse order: viewer, gateway, Bridge, resident, adapter and isolated MQTT. Production LM Studio and the canonical external MQTT broker remain running. |

Gate 5B remains blocked by the missing root publication URL/remote, the
unavailable LM Studio API and unpinned LM Studio version, the full-stack
services not being live, absent physical Android/Temi acceptance, external
model/pose provenance, and the unresolved <code>llmster</code> audit incident.
The local llama build cache reduces uncertainty but does not create a portable
build pin.

Gate 5A records facts for Gate 5B; it does not close any of these blockers,
advance <code>release/github-v1</code>, push, or authorize a service operation.

## Gate 5A.1 publication/runtime delta reconciliation (historical candidate)

Review date: 2026-08-28. This section is the Gate 5A.1 candidate contract. It
does not adopt or move <code>release/github-v1</code>, change canonical
<code>main</code>, or authorize Gate 5B.

The initial Gate 5A result was
<code>AI6_TEMIAGENT_GATE5A_RUNTIME_DELTA_REMEDIATION_REQUIRED</code> with
classification <code>C</code>: the publication tree intentionally contained
security/publication-boundary deltas, but the formal Hermes submodule
reconstruction exposed a lifecycle compatibility gap. After reconciliation,
the candidate result is
<code>AI6_TEMIAGENT_GATE5A_1_RUNTIME_DELTA_RECONCILED</code> with
classification <code>C_ACCEPTED_INTENDED_DELTA</code>. The candidate-only
remediation is limited to the lifecycle source gate and its regression test:

- <code>tools/demo_lifecycle.py</code> accepts the exact root status
  <code> M hermes-agent</code> only when
  <code>tools/verify_hermes_submodule.py</code> returns success with
  <code>state=RECONSTRUCTED</code>.
- <code>tools/tests/test_demo_lifecycle.py</code> proves that verified formal
  reconstruction is accepted and an unverified generated external checkout
  difference is still rejected.
- A nested <code>hermes-agent</code> checkout must remain clean. An index
  change, any other dirty path, an absent verifier/manifest, an unverified
  tree, a base-only tree or a dirty nested checkout still fails closed.

This is a publication/runtime compatibility correction for an intended formal
submodule state, not permission to ignore repository changes. The reviewed
publication ref remains the immutable baseline
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>. The
candidate branch is <code>codex/github-v1-live-environment-audit</code>; its
final commit is recorded by the Gate 5A.1 evidence and is not yet adopted.

### Path-by-path baseline comparison

The fixed comparison is canonical
<code>main@12aff3bfdfe526c17a25a2681aea2afad7112b33</code> against
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>.
There are 82 changed paths, of which 21 are executable/runtime,
configuration, dependency or test paths. The following object pairs are the
exact non-documentation/non-memory portion of that comparison; a dash means
the path is absent on that side.

| Path | Canonical object | Publication object | Category | Behavioral? | Live validation? | Intended? | Source gate | Risk |
|---|---|---|---|---|---|---|---|---|
| <code>.gitignore</code> | <code>7ef7c8e6651d683875dc53a911e89ac3f6217042</code> | <code>daa6ff7eee8fd6511bab5e1c5464a92c09c49f80</code> | PORTABILITY_HARDENING | NO | NO | YES | publication scan | LOW |
| <code>.gitmodules</code> | — | <code>fd770e5901e3bfb999240f69bbba788bd1fe01e9</code> | DEPENDENCY_GOVERNANCE | NO | YES | YES | submodule verifier | HIGH |
| <code>config/demo_resources.json</code> | <code>e2138d0bd65e5406eb7eaeb65c7b2f0d5e6027e4</code> | <code>3c09c7b3106eb4048b41b39b00c5cde95ec0486e</code> | CONFIGURATION_CONTRACT | YES | YES | YES | resource manifest/doctor | MEDIUM |
| <code>anomaly_detection/yolo26x-pose.pt</code> | <code>d1fa01ade8358577cde976874ccf6abfa94eb9fa</code> | — | SECURITY_HARDENING | NO | NO | YES | blob/path scan | MEDIUM |
| <code>hermes-agent</code> | — | <code>a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2</code> | DEPENDENCY_GOVERNANCE | YES | YES | YES | submodule/bootstrap verifier | HIGH |
| <code>scripts/bootstrap_hermes.sh</code> | <code>ae39dc08dba5878c00fc3bf7c64878596fd6cb1d</code> | <code>872ebcbf05cd49af2e924020999ee71a4e5a86a0</code> | BOOTSTRAP | NO | YES | YES | bootstrap check/tests | MEDIUM |
| <code>scripts/bootstrap_llama_cpp.sh</code> | <code>ba7512f53ac47ec99dff581abfab30b709814aa8</code> | <code>fd599537429df1b3a4d984edd570fa24c9e8730d</code> | BOOTSTRAP | NO | YES | YES | bootstrap check/tests | MEDIUM |
| <code>temi_backend/tests/test_overview_adapter.py</code> | <code>908a1448f36e8182479f3b0b61008f1f3a35ec18</code> | <code>24b70dbbc486e68dacfb8eccf19bef54bbf6236f</code> | TEST_ONLY | NO | NO | YES | backend suite | LOW |
| <code>third_party/hermes/manifest.json</code> | <code>0cff78c0be7759efbc124a09861b00acaa24eb02</code> | <code>7248e858e2a2336ee2e3f546cb5ec0de42dcdeef</code> | DEPENDENCY_GOVERNANCE | NO | YES | YES | Hermes verifier | HIGH |
| <code>third_party/llama_cpp/manifest.json</code> | <code>b432bf4942fb3635b60a6a7ad4c2eed3f6e324b2</code> | <code>6eee32ecdd43f0984108acd006ea08a4e3278c22</code> | DEPENDENCY_GOVERNANCE | NO | YES | YES | llama bootstrap/tests | HIGH |
| <code>tools/bounded_process.py</code> | — | <code>2354ae606f649707f78c34e920359ecaf3c2a5bd</code> | PORTABILITY_HARDENING | NO | NO | YES | bounded-process tests | MEDIUM |
| <code>tools/run_bounded_process.py</code> | — | <code>80bf4cf385b4dd1ff44d80056b4452978867d640</code> | PORTABILITY_HARDENING | NO | NO | YES | bounded-process tests | MEDIUM |
| <code>tools/start_temi_pc_services.sh</code> | <code>78522a00ecf2228008a38dca8b73f3ca718458cc</code> | <code>742d007b5f07036c609847b6a3cd6d9a66e7fb26</code> | SECURITY_HARDENING | YES | YES | YES | shell/adapter tests | HIGH |
| <code>tools/start_temi_pc_services_background.sh</code> | <code>9fc57d3b983f1b73e0d20a469858ed610a4d5657</code> | <code>73771a443577bbd28abd15afdebea825358fc5</code> | SECURITY_HARDENING | YES | YES | YES | shell/adapter tests | HIGH |
| <code>tools/temi_overview_adapter.py</code> | <code>a71a28da334def32ba47d8d4a10b42e0f79af9c9</code> | <code>2cb852c4718543e0eb14ca2a4781941976a3afcf</code> | SECURITY_HARDENING | YES | YES | YES | adapter/backend tests | HIGH |
| <code>tools/tests/test_bounded_process.py</code> | — | <code>7c1684f9ed0fd0fa7597941157110f436e78821a</code> | TEST_ONLY | NO | NO | YES | tools suite | LOW |
| <code>tools/tests/test_external_dependency_publication.py</code> | — | <code>48d37acb53aeb3bfc4052e69e684f47a36717713</code> | TEST_ONLY | NO | NO | YES | tools suite | LOW |
| <code>tools/tests/test_hermes_license.py</code> | — | <code>c87e232afc82a08db88b96cbf7b677327a2f43bb</code> | TEST_ONLY | NO | NO | YES | tools suite | LOW |
| <code>tools/tests/test_hermes_submodule.py</code> | — | <code>7f565df9be6be92bb190b1a039ed0d14991a1b51</code> | TEST_ONLY | NO | NO | YES | tools suite | LOW |
| <code>tools/verify_hermes_license.py</code> | — | <code>0b22151d2cda14fd8bf3be471a1e3e27f7d4b699</code> | DEPENDENCY_GOVERNANCE | NO | YES | YES | license verifier | HIGH |
| <code>tools/verify_hermes_submodule.py</code> | — | <code>68f071696c04a0636786c111cef9fbd16f7a7d63</code> | DEPENDENCY_GOVERNANCE | NO | YES | YES | submodule verifier | HIGH |

The MQTT lifecycle implementation, tracked broker configuration and
MQTT-only status contract are byte-identical between the two baseline trees.
The publication-only adapter, legacy PC-IP and dependency deltas are
therefore accepted as intended. The only additional Gate 5A.1 runtime code
change is the narrowly scoped formal-submodule source-gate compatibility
fix described above.

For the final classification count, four of the 21 paths are direct
behavioral/configuration or security-hardening inputs
(<code>config/demo_resources.json</code>, the two PC starter scripts and the
overview adapter); the remaining 17 are intentional publication-boundary,
dependency/bootstrap, bounded-process or test support. All 21 are intended
publication deltas and zero are accidental runtime regressions.

### Broker, PC-IP and resource contracts

The Gate 5B broker input must be private configuration, never a checked-in
address. The canonical lifecycle resolves <code>MQTT_BROKER_HOST</code> and
<code>MQTT_BROKER_PORT</code> from the owner-only Demo env and passes the
resolved host explicitly to the adapter. The adapter precedence is:
explicit <code>--broker</code>, then <code>TEMI_MQTT_BROKER</code>, then a
parse-time failure; it has no private-LAN fallback. The two legacy PC starter
scripts require non-empty <code>PC_IP</code> and export it as
<code>TEMI_MQTT_BROKER</code>; they do not validate or publish a default
deployment address. A missing value fails before a client listener is
created.

<code>BROKER_CONFIG_INPUT</code> is the owner-only
<code>MQTT_BROKER_HOST</code>/<code>MQTT_BROKER_PORT</code> pair in the
resolved Demo env; <code>BROKER_CONFIG_PRECEDENCE</code> at the adapter is
<code>--broker &gt; TEMI_MQTT_BROKER &gt; fail</code>;
<code>MISSING_CONFIG_BEHAVIOR</code> is parse-time exit before client/listener
creation; and <code>EXPECTED_GATE5B_VALUE_SOURCE</code> is the operator's
private deployment input, never a tracked default.

For Gate 5B the operator must provide a deployment-specific Temi-facing
endpoint in the private runtime input. The candidate documentation and
tracked templates intentionally contain no private LAN default. The safe
default for this Gate 5B plan is <code>MQTT_OWNERSHIP=external</code> and
read-only proof of the already healthy managed broker on its configured
production listener; no broker restart or MQTT publish/subscribe is part of
Gate 5A.1.
<code>MQTT_RESTART_REQUIRED=NO</code>.

#### PC_IP contract

<code>PC_IP_REQUIRED_BY</code>: <code>tools/start_temi_pc_services.sh</code>
and <code>tools/start_temi_pc_services_background.sh</code>, including the
legacy adapter/video child commands they assemble. The canonical
<code>scripts/demo</code> lifecycle uses explicit
<code>MQTT_BROKER_HOST</code> and does not synthesize <code>PC_IP</code>.

<code>PC_IP_SEMANTICS</code>: the Temi-facing AI6 host address used by the
legacy MQTT/video client route; it is not a bind-all address, a robot address
or a public repository default. <code>PC_IP_VALIDATION</code> is currently
non-empty shell parameter validation only. There is no IP-format, route or
reachability validation in those legacy starters.

<code>MISSING_PC_IP_BEHAVIOR</code>: the shell parameter expansion fails before
the child process is launched. <code>GATE5B_VALUE</code> is the observed AI6
deployment address classified as <code>OBSERVED_AI6_DEPLOYMENT</code>, not
<code>PORTABLE_DEFAULT</code>; the value is intentionally omitted from this
tracked candidate and may be placed only in the owner-only ephemeral Gate 5B
input after an operator confirms the active interface. The
<code>GATE5B_VALUE_SOURCE</code> is the read-only
<code>ip -4 addr</code>/<code>ip route</code> observation recorded in the
Gate 5A evidence, not a checked-in template.

#### Resource runtime mapping

| Resource | Purpose | Publication contract | Actual AI6 location | Present? | Validation | Portable? | Secret? | Gate 5B required? |
|---|---|---|---|---|---|---|---|---|
| <code>elderly_hand_exercise</code> | Android-deployed logical media | Required logical resource; no media bytes in Git | External Temi Android application/device asset | NOT_VERIFIED | Bridge allowlist, fake Android/media tests, then device-owner observation | NO; device-owned | NO | YES only at L4 device acceptance |
| <code>temi_discord_care_skill</code> | Resident Hermes skill | Required relative path <code>hermes-agent/skills/temi-discord-care-assistant/SKILL.md</code> | <code>/TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md</code> after reconstruction | YES in canonical/fresh preflight | Resource manifest, formal Hermes verifier, nested clean check | YES after bounded bootstrap | NO | YES for resident L1 |
| <code>anomaly_pose_model</code> | Optional pose preprocessing for action viewer | Manifest-only optional path; model blob removed from publication | Observed canonical external path <code>/TemiAgent/anomaly_detection/yolo26x-pose.pt</code>; absent from publication clone | CANONICAL_ONLY | Manifest size/hash plus maintainer source/license/restriction approval | NO until provenance is closed | NO | NO by default; optional viewer only |
| <code>Gemma GGUF</code> | LM Studio/resident model bytes | External configured cache; tracked identifier only | <code>/TemiAgent/.lmstudio-data/models/...</code> in the observed deployment | YES canonical; external in clone | LM Studio <code>/v1/models</code>, model identifier/context/GPU policy | NO; provider/cache-owned | NO; credentials separate | YES for production L1/L5 |
| <code>mmproj-F32.gguf</code> | Optional viewer projection | External configured path; not tracked | <code>/TemiAgent/.lmstudio-data/models/...</code> in the observed deployment | YES canonical; external in clone | Viewer resource/path and llama readiness checks | NO until supplied | NO; credentials separate | NO unless viewer is explicitly enabled |
| <code>llama-server</code> | Optional viewer inference server | External build output under ignored path | <code>/TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server</code> | YES canonical; external in clone | Executable/build/source checks and viewer health | NO; build environment-owned | NO | NO by default |
| <code>hermes-agent/venv</code> | Hermes resident/gateway runtime | External ignored environment; source is the formal submodule plus overlay | <code>/TemiAgent/hermes-agent/venv</code> in observed deployment | YES canonical; supplied externally in clone | Locked environment setup and resident health | NO; environment-owned | NO | YES for resident L1 |
| <code>TEMIAGENT_RUNTIME_ROOT</code> | Logs, memory, shared metadata, PID/state/socket files | Absolute owner-only external root | New Gate 5B private runtime root, outside source Git state | NOT_CREATED in this gate | Mode/owner/path checks and lifecycle state checks | YES as a layout, not as retained data | Logs/payloads may be sensitive | YES |
| <code>MQTT_CONFIG_PATH</code> | Managed broker configuration when lifecycle owns MQTT | Private file only; reuse plan sets MQTT external | Canonical private Mosquitto config in observed deployment | YES canonical; not copied | MQTT status/lineage/config identity | NO; deployment-owned | YES; never print | NO for external reuse |

### Hermes reconstructed layout and publication preflight

The exact Gate 5B source root is the final reviewed Gate 5A.1 candidate
worktree at its recorded final commit, not canonical <code>main</code> and not
the mutable release ref. From that root, the bounded sequence is:

~~~text
git submodule update --init --recursive --depth=1
./scripts/bootstrap_hermes.sh --bootstrap
./scripts/bootstrap_llama_cpp.sh --bootstrap
./scripts/bootstrap --check
python3 tools/verify_hermes_submodule.py \
  --root . --manifest third_party/hermes/manifest.json
python3 tools/verify_hermes_license.py \
  --manifest third_party/hermes/manifest.json \
  --checkout hermes-agent \
  --base-commit a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2
~~~

The formal Hermes layout after reconstruction is: root gitlink at the
manifest base commit, a clean nested checkout, the root-owned nine-patch
overlay applied into that checkout, final tree
<code>968f1668a05fafd09461c17a835198421f14a48f</code>, and the required MIT
license. The llama.cpp check records commit
<code>0b7154066e8544ed88d92ae2132cc1e055cf6304</code> and tree
<code>1020a771795f406b8891d18ee607b4da3783fa7f</code>. Generated build
directories, venvs, model caches and runtime files remain external/ignored.

The live-layout fields are explicit:
<code>SUBMODULE_BASE=hermes-agent@a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2</code>;
<code>PATCHED_WORKTREE=hermes-agent</code> at final tree
<code>968f1668a05fafd09461c17a835198421f14a48f</code> with nine tracked root
patches; <code>VENV=hermes-agent/venv</code> supplied by the environment;
<code>SKILLS=hermes-agent/skills/temi-robot-control,
temi-care-memory,temi-home-esi,temi-discord-care-assistant</code>;
<code>CONFIG=config/demo_resources.json</code> plus the private
<code>GATE5B_RUNTIME_CONFIG</code> and safe Bridge template;
<code>MEMORY=&lt;TEMIAGENT_RUNTIME_ROOT&gt;/data/care-memory</code>; and
<code>RUNTIME_STATE=&lt;TEMIAGENT_RUNTIME_ROOT&gt;/state</code> with private
logs, PID/ownership records, sockets and shared metadata. No resident or
Hermes process is started by this gate.

Gate 5A.1 publication preflight was run in a disposable clone without
starting a service: bounded recursive submodule initialization, Hermes
bootstrap, llama bootstrap, source/license checks, and the documentation
validator passed. A newcomer configuration was materialized in that
disposable root. No MQTT publication/subscription, model inference, Android
operation, GPU mutation, or full-stack start was performed. The final
disposable-clone result showed the reconstructed-submodule source gate as
PASS, with no service transition, before Gate 5B was considered.

### Gate 5B exact source root and ephemeral inputs

The exact Gate 5B source identity is fixed by a maintainer-supplied
non-tracked handover value, while its filesystem path is transient. Set
<code>GATE5B_SOURCE_ROOT</code> to the absolute path of the isolated worktree
checked out at <code>codex/github-v1-live-environment-audit</code>. The
handover input/evidence must supply the concrete
<code>GATE5B_EXPECTED_HEAD</code> recorded by this Gate 5A.1 review; do not
derive it from the worktree under test or silently replace it with a branch
tip.

Before reading private configuration or starting any process, require:

~~~text
test -n "$GATE5B_EXPECTED_HEAD"
test "$(git -C "$GATE5B_SOURCE_ROOT" rev-parse --show-toplevel)" = "$GATE5B_SOURCE_ROOT"
test "$(git -C "$GATE5B_SOURCE_ROOT" rev-parse HEAD)" = "$GATE5B_EXPECTED_HEAD"
test "$GATE5B_SOURCE_ROOT" != "/TemiAgent"
~~~

The Gate 5A.1 candidate worktree used for this evidence is the source-root
owner; an operator may materialize the same reviewed commit at any isolated
absolute path, but must record that path and the two identity checks above.
The source must never silently fall back to canonical <code>main</code>.

<code>GATE5B_RUNTIME_INPUT_LOCATION=/tmp/ai6-gate5b-runtime-input.env</code>
is the planned owner-only mode-0600 env file; it is not created or tracked by
Gate 5A.1. <code>TEMIAGENT_RUNTIME_ROOT=/tmp/ai6-gate5b-runtime-root</code> is
the planned new owner-only runtime root and must be created separately from
the source checkout. An operator may choose a different private path only
when recording its exact path before start.

<code>DEMO_GIT_BRANCH_POLICY=disabled</code> is permitted only because the
reviewed candidate branch is not named <code>main</code>; exact HEAD, root
dirty-path and nested-Hermes checks remain mandatory. Any configuration that
disables those checks is invalid.

The explicit non-secret key contract for the Gate 5B input is:
<code>GATE5B_EXPECTED_HEAD</code> (source-preflight identity, supplied by the
owner), <code>DEMO_PROFILE</code>, <code>DEMO_GIT_BRANCH_POLICY</code>,
<code>TEMIAGENT_RUNTIME_ROOT</code>, <code>LOG_DIR</code>,
<code>MEMORY_DIR</code>, <code>DEMO_CARE_MEMORY_ROOT</code>,
<code>TEMI_SHARED_BRIDGE_PATH</code>, <code>TEMI_SHARED_HERMES_PATH</code>,
<code>HERMES_MEDIA_CALLBACK_SOCKET</code>,
<code>HERMES_DEMO_IDENTITY_CALLBACK_SOCKET</code>,
<code>HERMES_DEMO_CARE_CALLBACK_SOCKET</code>,
<code>DEMO_IDENTITY_STATE_DIR</code>, <code>LMSTUDIO_OWNERSHIP</code>,
<code>LMSTUDIO_TARGET_DIR</code>, <code>LMSTUDIO_MODEL_ID</code>,
<code>LMSTUDIO_API_IDENTIFIER</code>, <code>LMSTUDIO_SERVER_PORT</code>,
<code>CONTEXT_LENGTH</code>, <code>LMSTUDIO_CONTEXT_LENGTH</code>,
<code>LMSTUDIO_VISIBLE_GPUS</code>, <code>MQTT_OWNERSHIP</code>,
<code>MQTT_BROKER_HOST</code>, <code>MQTT_BROKER_PORT</code>,
<code>ROBOT_ID_ALLOWLIST</code>, <code>HERMES_INVOKE_MODE</code>,
<code>HERMES_HTTP_URL</code>, <code>HERMES_TIMEOUT_SECONDS</code>,
<code>TRACE_ENABLED</code>, <code>TRACE_INCLUDE_ASR_TEXT</code>,
<code>DEBUG_TRACE_FULL</code>, <code>MEDIA_V11_ENABLED</code>,
<code>HERMES_MEDIA_TOOL_ENABLED</code>,
<code>HERMES_MEDIA_FAST_PATH_ENABLED</code>,
<code>HERMES_GATEWAY_ENABLED</code>,
<code>HERMES_GATEWAY_OWNERSHIP</code>, <code>MANAGE_ANDROID</code>,
<code>DEMO_ACTION_VIEWER_ENABLED</code>,
<code>DEMO_ACTION_VIEWER_MODEL</code>,
<code>DEMO_ACTION_VIEWER_GGUF_MODEL_PATH</code>,
<code>DEMO_ACTION_VIEWER_MMPROJ_PATH</code>,
<code>DEMO_ACTION_VIEWER_LLAMA_SERVER</code>,
<code>DEMO_ACTION_VIEWER_LLAMA_SERVER_PORT</code>,
<code>DEMO_ACTION_VIEWER_CUDA_VISIBLE_DEVICES</code>,
<code>DEMO_ACTION_VIEWER_POSE_MODE</code>,
<code>DEMO_ACTION_VIEWER_POSE_MODEL</code>,
<code>DEMO_ACTION_VIEWER_POSE_DEVICE</code>,
<code>DEMO_ACTION_VIEWER_MAX_OUTPUT_TOKENS</code>,
<code>DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH</code>,
<code>DEMO_ACTION_VIEWER_DISCORD_NOTIFY</code>,
<code>DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK</code>,
<code>ABNORMAL_CARE_EPISODE_ENABLED</code>,
<code>ABNORMAL_CARE_FIRST_RESPONSE_TIMEOUT_SECONDS</code>,
<code>ABNORMAL_CARE_SECOND_RESPONSE_TIMEOUT_SECONDS</code>,
<code>ABNORMAL_CARE_TIMEOUT_POLL_SECONDS</code>,
<code>ABNORMAL_NOTIFICATION_MODE</code>,
<code>ABNORMAL_NOTIFICATION_TIMEOUT_SECONDS</code>,
<code>ABNORMAL_NOTIFICATION_TEST_RECIPIENT_AUTHORIZED</code>,
<code>DEMO_NOTIFICATION_MOCK_ENABLED</code>,
<code>DEMO_NOTIFICATION_RECEIPT_ENABLED</code>,
<code>DEMO_TEST_EVENT_INGRESS_ENABLED</code>,
<code>DEMO_TEST_RESIDENT_ALLOWLIST</code> and
<code>DEMO_START_TIMEOUT_SECONDS</code>. <code>PC_IP</code> is an additional
legacy-starter input when that route is selected. Credential values and
credential-file contents are not part of this public key list.

When the corresponding optional/managed route is enabled, also carry
<code>EXPECTED_GIT_BRANCH</code>, <code>MQTT_CONFIG_PATH</code>,
<code>ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH</code>,
<code>DEMO_OPERATOR_IDENTITY_ENABLED</code>,
<code>RESIDENT_IDENTITY_ENABLED</code>,
<code>HERMES_DEMO_IDENTITY_TOOL_ENABLED</code>,
<code>HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED</code>,
<code>DEMO_REPEATED_DISCOMFORT_ENABLED</code>,
<code>DEMO_CARE_SCENARIO_PROMPT_ENABLED</code>,
<code>DEMO_RESIDENT_VISUAL_ROUTING_ENABLED</code>,
<code>CARE_CONTEXT_ENABLED</code>, <code>DEMO_IDENTITY_REFRESH_SECONDS</code>
and <code>DEMO_IDENTITY_MAX_DURATION_SECONDS</code>. The complete source
of truth for this key set is the tracked production template
<code>config/demo.env.example</code>; the Gate 5B input must not invent
additional keys or secret values.

The private input must define the broker endpoint/ownership, model/API
ownership, required production ports, runtime paths, resource paths and
notification mode. Credentials remain in separately referenced owner-only
files. No ephemeral input is committed, printed, copied into a log or
retained as a public fixture.

### LM Studio, MQTT and process ledger

LM Studio is an external Gate 5B readiness boundary. The first check is
read-only HTTP <code>GET /v1/models</code> on configured port
<code>1234</code>, requiring the configured
<code>google/gemma-4-31b</code> identifier, context <code>64000</code> and
GPU policy. A process, model file or cached build alone is not readiness.
Production uses <code>LMSTUDIO_OWNERSHIP=external</code>: the lifecycle
requires one listener and a compatible model-list response, then starts only
the other explicitly managed AI6 services. It never starts, stops, unloads,
loads or reconfigures the real LM provider.

<code>LMS_CLI_READ_ONLY_SAFE=NO</code>. Direct <code>lms</code> inventory and
global cleanup are unsafe and are not part of any lifecycle or audit path.
<code>LMS_CLI_ALLOWED_GATE5B=NO</code> for the production lifecycle; the
retained supervisor and startup-helper names are fail-closed compatibility
guards only.
<code>LM_STUDIO_EXPECTED_PORT=1234</code>,
<code>LM_STUDIO_READINESS_ENDPOINT=http://127.0.0.1:1234/v1/models</code>
and <code>LM_STUDIO_LOG_LOCATION=&lt;TEMIAGENT_RUNTIME_ROOT&gt;/logs/lmstudio/lmstudio.log</code>
are the non-secret contract locations. The current API is unavailable, so
no model readiness or inference is claimed. The newcomer mock may use the
managed high-port test double; it is not a real LM provider.

The observed <code>llmster</code> process has PPID 1 and owns a separate
loopback listener, but no lifecycle record proves it is the LM Studio API
service child. Classify it as
<code>PREEXISTING_DAEMON_INFRASTRUCTURE_OR_UNKNOWN</code>, foreign to the
Gate 5B ownership set and not adoptable. It remains preserved. Only a
supervisor/process record created by Gate 5B may be stopped, and only after
the API readiness gate and exact identity checks.

The following ledger is the pre-start preservation record. PIDs are observed
evidence, not portable requirements:

| PID | Service | Pre-existing? | Owned by Gate 5B? | May Gate 5B stop? | Expected preservation |
|---:|---|---|---|---|---|
| <code>924834</code> | Managed MQTT supervisor | YES | NO | NO | Preserve exact supervisor, command, cwd, config and child contract. |
| <code>924835</code> | Mosquitto broker child | YES | NO | NO | Preserve exact broker child, listener <code>0.0.0.0:1883</code> and TCP readiness. |
| <code>1051985</code> | Packaged <code>llmster</code> daemon/infrastructure candidate | YES; prior Gate 5A audit side effect | NO | NO | Preserve; not an API-service child proven by lifecycle evidence. |
| <code>1051997</code> | <code>llmster</code> system-resources child | YES; child of prior side effect | NO | NO | Preserve with parent; no broad or guessed stop. |
| — | Adapter, resident, Bridge, gateway, viewer | YES as “not started/owned by this gate” | NO before explicit start | NO before exact Gate 5B record | Capture cwd, command, executable, start identity, ports and logs before any later start/stop. |

The MQTT state is reused only when its exact supervisor/child contract,
configured listener, lineage and local TCP probe still pass. Gate 5B must
record a fresh pre-start ledger because PIDs and service state are
time-dependent; the values above are evidence, not portable identifiers.

The collision plan checks, before any authorized start, ports
<code>1234</code> (LM Studio), <code>1883</code> (MQTT),
<code>8080/8081</code> (adapter), <code>8765</code> (resident),
<code>8010/8011</code> (viewer) and any configured gateway callback. A
foreign listener, duplicate listener, wrong bind or unverified owner blocks
the phase. An isolated newcomer broker may use its checked-in high-port
profile (for example <code>29183</code>) with a separate runtime root; it
must never be attached to or silently replace production <code>1883</code>.

| Service | Expected port | Current listener | Collision? | Strategy |
|---|---:|---|---|---|
| LM Studio | <code>1234</code> | Absent in the read-only audit | NO currently; readiness still FAIL until API responds | <code>BLOCKED</code> until the external model/API owner proves readiness; AI6 lifecycle start is not an option. |
| MQTT | <code>1883</code> | One verified <code>0.0.0.0:1883</code> listener | YES for a new owner; NO for verified reuse | <code>REUSE_EXISTING</code>; never start a second broker. |
| Overview adapter | <code>8080/8081</code> | No Gate 5B listener | NO currently | <code>START_ON_CANONICAL_PORT</code> only after exact collision scan. |
| Hermes resident | <code>8765</code> | No Gate 5B listener | NO currently | <code>START_ON_CANONICAL_PORT</code> after Hermes/LM/MQTT preconditions. |
| Bridge callback/transport | Private runtime callback plus configured transport | No Gate 5B listener | NO current Gate 5B owner | <code>START_ON_CANONICAL_PORT</code> through lifecycle after resident. |
| Gateway | Provider/executable-defined; no minimum production listener in this plan | Not checked as a Gate 5B owner | NOT_APPLICABLE | <code>DO_NOT_START</code> unless separately reviewed and owned. |
| Action viewer/llama | <code>8010/8011</code> | No Gate 5B listener | NO currently | <code>DO_NOT_START</code> by default; optional isolated owner only. |
| Pre-existing <code>llmster</code> | Loopback <code>41343</code> | One observed loopback listener | Not an AI6 service-port collision | <code>DO_NOT_STOP</code>; preserve as outside Gate 5B ownership. |

### Gate 5B start order, rollback and staged acceptance

Gate 5A.1 does not execute this sequence. After explicit Gate 5B
authorization, the planned minimum production order is:

~~~text
L0 source/config/port preflight
  -> L1 minimum service readiness
  -> L2 local functional path without physical side effect
  -> L3 cross-service synthetic/no-op path without physical side effect
  -> L4 Android/Temi E2E only with separate device authorization
  -> L5 one bounded model/inference request after model readiness
~~~

The newcomer mock lifecycle start order is
<code>lmstudio(mock) → mqtt → adapter → resident → bridge → mock_android →
mock_discord → gateway → viewer</code>. Production uses external LM readiness
as a precondition, then starts only the managed MQTT/adapter/resident/Bridge
path selected by its private config; the real LM provider has no lifecycle
service spec. Gate 5B's minimum profile therefore leaves LM external, reuses
the existing MQTT listener, and leaves gateway, viewer, mock Android and mock
Discord disabled. The planned command, never executed here, is:

~~~text
./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" start
~~~

#### Gate 5B service start contract

Every managed row below is started only by the one lifecycle command above;
the internal argv is listed to make the owner and executable unambiguous.
External rows have no start command.

| Step/service | Precondition | Exact start command or decision | Readiness check | Side effect | Rollback | Owner |
|---|---|---|---|---|---|---|
| L0/preflight | Candidate HEAD <code>$GATE5B_EXPECTED_HEAD</code>, manifests/licenses, private config and all ports verified | Read-only <code>git</code>, <code>./scripts/bootstrap --check</code>, <code>./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" --json doctor</code> | Source gate PASS, private paths safe, no collision | None | Do not start; discard only isolated candidate/input | Maintainer |
| L1/LM Studio | External API already passes; model/GPU inputs are provisioned by its owner | <code>DO_NOT_START</code>; production lifecycle has no real-LM start command | One configured listener and <code>curl --fail --silent http://127.0.0.1:1234/v1/models</code> contains the configured ID; context/GPU policy is checked as external configuration | None by AI6; no global model/daemon mutation | <code>DO_NOT_STOP</code>; preserve external/legacy state and escalate ambiguous ownership | LM/runtime owner |
| L1/MQTT | Existing canonical <code>RUNNING/READY</code>, exact lineage and TCP probe pass | <code>DO_NOT_START</code>; read-only <code>./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" --json mqtt status</code> | One external listener, supervisor/child contract and local TCP probe | None for reuse | None; never stop canonical MQTT | AI6 operator |
| L1/adapter | LM, MQTT and runtime root ready; adapter ports clear | Lifecycle command; internal executable is <code>uv run python tools/temi_overview_adapter.py --broker "$MQTT_BROKER_HOST" --port "$MQTT_BROKER_PORT"</code> with configured ports/paths | Exact process record plus listeners <code>8080/8081</code>; no private default | Opens client/listener sockets; no test publish | Lifecycle stop exact adapter record; preserve redacted log | AI6 service owner |
| L1/resident | Reconstructed Hermes final tree, clean nested checkout, venv and required skill paths ready | Lifecycle command; internal executable is <code>hermes-agent/venv/bin/python3 tools/hermes_resident_server.py --host 127.0.0.1 --port 8765</code> with four required skill paths | <code>/health</code> reports media/tool contract and exact owner | Opens loopback HTTP service; no hardware action | Lifecycle stop exact resident record; preserve log | Hermes/runtime owner |
| L1/Bridge | Locked Bridge env and callback/runtime paths ready; resident healthy | Lifecycle command; internal executable is <code>uv run --extra mqtt hermes-temi-bridge --env-file hermes_temi_bridge/.env.example</code> | Callback/health, exact process identity, trace directory and validator state | Opens callback/transport boundary; dispatch remains validator-bound | Lifecycle stop exact Bridge record; preserve trace/log evidence | Bridge owner |
| L2/local path | L1 all pass | Use existing software-only resident/Bridge health and local callback/no-op contract; no raw MQTT command | Valid schema/trace transition with no physical executor | Nonphysical local event/trace only | Stop progression; reverse exact owned records | Verification owner |
| L3/cross-service no-op | L2 pass and synthetic/no-op fixture authorized | Use the existing canonical synthetic event/trace acceptance harness; no direct raw publish | Adapter/resident/Bridge contract and synthetic result correlate by run/trace ID | Nonphysical synthetic transport only | Stop progression; reverse exact owned records | Verification owner |
| L4/Android/Temi | L3 pass plus separate device-owner authorization | <code>DO_NOT_START</code> from AI6; use the Android owner’s separately authorized session | Fresh Android subscription, accepted/started or playing result and physical observation | Physical device action | Device-owner rollback; AI6 stops only its exact owned processes | Android/Temi owner |
| L5/model inference | L1 model readiness, L2/L3 pass, explicit bounded inference approval | One bounded non-sensitive request through the resident contract; no unrestricted prompt | Valid bounded Hermes JSON response and validator result within timeout | Model inference only; no automatic physical action | Stop progression; reverse exact owned records | Model/verification owner |
| Optional gateway/viewer | Not required by minimum path; resources/owners separately ready | <code>DO_NOT_START</code> by default; enable only in a separately reviewed config | Gateway health or viewer/llama/resource health when explicitly enabled | Additional service/listener and optional perception path | Stop exact optional records before L3 records | Optional-service owner |

#### Gate 5B exact stop and rollback contract

The primary stop command is
<code>./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" stop</code>. It
signals only lifecycle records created by this Gate 5B run and performs
reverse-order cleanup. If a recorded process does not match its stored cwd,
command, executable, start identity, process group and port evidence, the
lifecycle refuses to signal it. Only after the same exact identity is
revalidated may the owner use <code>TERM</code>, wait the bounded grace
period, then <code>KILL</code> against that same exact process group.
<code>pkill</code>, <code>killall</code>, name matching, reboot and deletion
of runtime evidence are forbidden.

| Reverse order | Gate 5B-owned stop command | Fallback/ownership proof | Logs/evidence |
|---|---|---|---|
| Viewer/gateway (only if enabled) | Lifecycle <code>stop</code> | Exact lifecycle record, cwd/argv/start identity/listener; same-PID bounded TERM/KILL only | Preserve private viewer/gateway logs and health evidence. |
| Bridge | Lifecycle <code>stop</code> | Exact Bridge record and callback identity; same-PID bounded TERM/KILL only | Preserve Bridge trace/logs. |
| Resident | Lifecycle <code>stop</code> | Exact resident record and port <code>8765</code>; same-PID bounded TERM/KILL only | Preserve redacted resident log. |
| Adapter | Lifecycle <code>stop</code> | Exact adapter record and ports <code>8080/8081</code>; same-PID bounded TERM/KILL only | Preserve redacted adapter log. |
| Isolated MQTT (only if separately selected) | <code>./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" mqtt stop</code> | Exact isolated broker supervisor/child record; same-PID bounded TERM/KILL only | Preserve private broker log/state. |
| LM Studio | <code>DO_NOT_STOP</code> | External owner and HTTP readiness contract; no AI6 LM supervisor record | Preserve external provider evidence and never touch pre-existing <code>llmster</code>. |
| Canonical MQTT / pre-existing llmster | <code>DO_NOT_STOP</code> | Outside Gate 5B ownership | Preserve existing evidence unchanged. |

#### Gate 5B acceptance layers

Each layer is a gate, not a suggestion; failure stops progression and invokes
only the rollback boundary owned by the current run.

| Layer | Entry gate | Check | Expected | Fail action | Rollback |
|---|---|---|---|---|---|
| L0 preflight | Exact candidate HEAD/source root and private input metadata recorded | Bootstrap/verifier/license checks, source dirty-path check, port collision scan, redacted doctor | All required source/config/resource checks PASS; no service mutation | Stop before any start and preserve evidence | None; discard only isolated candidate/input. |
| L1 service readiness | L0 PASS; LM/MQTT ownership decisions made | LM API/model/context/GPU gate; MQTT status/lineage/TCP; adapter/resident/Bridge health and exact PID records | Minimum publication services ready, with MQTT reused | Do not advance; mark failed owner and retain logs | Stop only exact Gate 5B-owned records in reverse; canonical MQTT/llmster untouched. |
| L2 local functional path | L1 PASS | Local resident/Bridge callback, schema and no-op validation with synthetic input | Valid local trace and bounded response; no physical executor | Block cross-service tests and retain redacted trace | Reverse exact owned software records. |
| L3 cross-service functional path | L2 PASS and synthetic/no-op fixture approved | Adapter/resident/Bridge event/trace correlation and validator-bound synthetic result | Cross-service contract passes without Android/Temi side effect | Block device/model acceptance | Reverse exact owned software records; no raw MQTT fabrication. |
| L4 Android/Temi E2E | L3 PASS plus explicit device-owner authorization | Fresh Android subscription, accepted/started or playing result, Bridge trace and physical observation | Device result and observation agree for each authorized action | Stop device test and record device-owner recovery; do not relabel software evidence | Device-owner rollback plus reverse exact AI6-owned software records. |
| L5 model/inference | L1-L3 PASS, API readiness PASS and explicit bounded request approval | One synthetic non-sensitive request with timeout, valid Hermes JSON and validator result | Model functionality is proven separately from service readiness; no automatic physical action | Block acceptance, preserve redacted evidence and classify model failure | Reverse exact AI6-owned records; never stop pre-existing external processes. |

If a later Gate 5B run fails, rollback is the reverse of the records created
by that run: viewer, gateway, Bridge, resident, adapter and any isolated
broker. Production LM Studio, the canonical MQTT supervisor and the
pre-existing <code>llmster</code> audit process are external to that ownership
set and remain untouched.
No name-based kill, broad pattern, reboot or runtime-data deletion is allowed.

### Physical side effects and model readiness

L0-L3 remain software-only. L4 is physical Android/Temi acceptance only with
separate device-owner authorization and observation; L5 is nonphysical by
default and requires its own bounded model approval. No Android command,
physical Temi motion, notification delivery or real-care action may be used
as an unapproved smoke test. A separate device owner must authorize and observe
Android/Temi acceptance,
including accepted/started or playing result evidence and the corresponding
Bridge trace. A Bridge publish alone is not physical proof.

Real model inference is also a separate acceptance boundary. After LM API
readiness, resident health and Bridge validation pass, the model owner may
authorize one bounded synthetic, non-sensitive input with a timeout and
redacted logs. The expected result is a valid bounded Hermes JSON plan
accepted by the resident/Bridge contract; any action must remain allowlisted
and validator-bound. No hardware action, unrestricted prompt, real care
record, credential, raw payload or model output is retained in public
evidence. Model failure blocks the next stage and rolls back only exact
Gate 5B-owned processes.

The explicit model acceptance fields are:
<code>MODEL_TEST_INPUT=one synthetic non-sensitive request with no real care
record, credential or unrestricted prompt</code>;
<code>EXPECTED_RESPONSE_CLASS=valid bounded Hermes JSON plan accepted by the
resident/Bridge validator</code>; <code>TIMEOUT=HERMES_TIMEOUT_SECONDS
(production template 60 seconds)</code>;
<code>LOG_CAPTURE=private owner-only lifecycle/Bridge logs with payloads,
credentials and model text redacted</code>; and
<code>GPU_OBSERVATION=read-only nvidia-smi before/after, with no GPU
reconfiguration</code>. A timeout, malformed output, validator rejection,
unexpected physical side effect or unredacted evidence is a hard failure and
blocks progression.

The Gate 5B command side-effect policy is explicit:

| Layer | Policy | Allowed operation |
|---|---|---|
| L0 | <code>NO_SIDE_EFFECT</code> | Source/config/port inspection only. |
| L1 | <code>NONPHYSICAL</code> | Start only explicitly authorized software services; production LM Studio is externally managed and not mutated by AI6, and no robot/device action is allowed. |
| L2 | <code>NONPHYSICAL</code> | Local callback/health/no-op checks only. |
| L3 | <code>NONPHYSICAL</code> | Synthetic cross-service trace/no-op only; no physical executor. |
| L4 | <code>PHYSICAL</code> | Separate Android/Temi owner authorization and observation are mandatory; AI6 does not start the device. |
| L5 | <code>NONPHYSICAL</code> by default | One bounded model request after readiness; any physical action is forbidden unless separately authorized and reclassified. |

### Gate 5A.1 verification and security matrix

The following evidence is for the final candidate source. The fresh
disposable-clone source preflight reconstructed the formal dependencies and
showed the candidate source gate PASS with root status
<code> M hermes-agent</code>, nested Hermes status clean, and newcomer doctor
<code>FAIL=0</code>. The amended final commit changes documentation only after
the code/test matrix, so those unchanged-source results remain valid under
the repository evidence-reuse rule.

| Check | Command/evidence | Result |
|---|---|---|
| Tools/configuration/lifecycle | <code>python3 -m unittest discover -s tools/tests</code> | PASS: 134/134 |
| Backend/adapter | <code>cd temi_backend &amp;&amp; uv run --locked --offline pytest</code> | PASS: 25/25; adapter focused subset 7/7 |
| Bridge/schema/validator | <code>cd hermes_temi_bridge &amp;&amp; uv run --locked --offline python -m unittest discover -s tests</code> | PASS: 166/166 |
| External dependency/bootstrap/license | Fresh clone bounded submodule init, <code>bootstrap_hermes.sh --bootstrap</code>, <code>bootstrap_llama_cpp.sh --bootstrap</code>, <code>bootstrap --check</code>, both verifiers, and the dependency tests in the tools suite | PASS |
| Documentation | <code>python3 tools/validate_documentation.py</code> and <code>python3 -m unittest tools.tests.test_validate_documentation</code> | PASS: 74 Markdown files, 8 schema mappings |
| Syntax | <code>bash -n $(git ls-files "*.sh")</code>; <code>python3 -m py_compile</code> on changed/verifier Python files | PASS |
| Diff hygiene | <code>git diff --check</code> | PASS |
| Security/publication scan | No tracked private LAN default, secret/key/token/webhook value, dependency <code>file://</code>, Git alternate, pose path/blob or blob at least 50/100 MiB | PASS: 0 for every required count |
| Live service/MQTT/model/device | Full-stack start, MQTT publish/subscribe, inference, Android/Temi and physical acceptance | SKIPPED: forbidden/deferred by Gate 5A.1 |

### Gate 5A.1 handover partials and remaining blockers

Partials <code>#4</code>, <code>#10</code>, <code>#11</code>,
<code>#32</code> and <code>#38</code> remain partial. Gate 5A.1 adds these
facts without pretending they are portable pins:

- <code>#4</code>: the root publication URL/remote is still absent; the
  local release ref is evidence only.
- <code>#10</code>/<code>#11</code>: the observed container/toolchain,
  CUDA/driver, LM Studio and model environment remain deployment facts, not
  approved image/provider/version pins.
- <code>#32</code>: no Android/Temi, physical, microphone/camera or real
  inference acceptance occurred.
- <code>#38</code>: the candidate is isolated and unadopted; neither
  <code>release/github-v1</code> nor canonical <code>main</code> changed, and
  no push occurred.

Gate 5B therefore remains deferred for the missing public root remote,
environment/provider pins, LM Studio API/model readiness, physical Android/
Temi evidence, external artifact provenance and the unresolved redacted
<code>llmster</code> incident disposition. This Gate 5A.1 candidate is
review-ready only; it is not a live acceptance and must not be described as
production-ready until the separate Gate 5B contract is authorized and
executed.

## Gate 5B failure and Gate 5B.1 LM ownership remediation (historical remediation)

Review date: 2026-08-28. Gate 5B stopped at the L1 ownership-safety gate with
<code>AI6_TEMIAGENT_GATE5B_RUNTIME_SAFETY_FAILED</code>. L0 and individual
endpoint health passed; L1 ownership protection failed. L2, L3 and L5 were
skipped, L4 was not run by scope, and the model request count was zero. No
physical Temi action, Android action, MQTT publication/subscription or external
notification occurred. All Gate 5B-owned processes were rolled back and the
canonical MQTT broker was preserved.

The root cause was the former managed real-LM startup/rollback path issuing
global <code>lms unload --all</code>, <code>lms server stop</code> and
<code>lms daemon down</code>. Those commands cannot establish exclusive
ownership of a global LM Studio daemon, server or model state. They affected
historical pre-Gate5B <code>llmster</code> evidence: parent PID
<code>1051985</code>, child PID <code>1051997</code>, and internal listener
<code>127.0.0.1:41343</code>. These are incident records only. They must not be
recreated, restored or treated as current required PIDs.

Gate 5B.1 selects <code>EXTERNAL_MANAGEMENT</code> for production LM Studio
and is labeled <code>IMPLEMENTATION_REMEDIATED_NONLIVE</code>. The corrected
invariant is:

- a pre-existing or foreign LM process/model/listener is not owned by the
  lifecycle and is never stopped, unloaded or globally cleaned up;
- a lifecycle process is owned only after positive identity/readiness proof;
- production start requires one configured LM listener and a compatible
  <code>/v1/models</code> response, then starts only other explicitly managed
  AI6 services;
- production stop excludes LM Studio. A legacy/ambiguous LM record is
  preserved and returns <code>STOP_INCOMPLETE_OWNERSHIP</code> rather than
  signalling a PID;
- the newcomer mock remains the only lifecycle-managed LM implementation, on
  its isolated high port and with fake-provider tests.

The retired real-LM supervisor and startup helper are fail-closed compatibility
guards. They do not invoke <code>lms</code> or start a provider. Direct
<code>lms ls</code>/<code>lms ps</code> inventory is not a read-only audit and
must not be used to recover this incident. A future Gate 5B retry must capture
a new process ledger from the state that exists at that time; it must not reuse
this historical ledger.

The accepted private-input pattern is a mode <code>0700</code> runtime root
containing the mode <code>0600</code> runtime config. A config placed directly
under a shared parent such as <code>/tmp</code> remains invalid. No live LM
verification is part of Gate 5B.1.

## Gate 5B.1 non-live verification evidence

The isolated remediation candidate was based on
<code>release/github-v1</code> at
<code>0a104d3200f6619b4120b357ca2c17fa8728057e</code>. All project commands
below ran inside <code>yiting.TemiAgent_gpu_all</code>; none started or stopped
LM Studio, MQTT, Hermes, Bridge, resident, viewer, gateway or adapter, and
none published/subscribed MQTT or contacted Android, Discord or a physical
Temi.

| Check | Result |
|---|---|
| Focused lifecycle and LM helper tests | PASS: <code>python3 -m unittest tools.tests.test_demo_lifecycle tools.tests.test_lmstudio_start_helper</code>; 113 tests |
| Complete tools suite | PASS: <code>python3 -m unittest discover -s tools/tests</code>; 147 tests |
| HermesTemiBridge suite | PASS: 166 tests |
| temi_backend suite | PASS: 25 tests, including the 7 adapter tests |
| anomaly_detection suite | PASS: 34 tests; negative MQTT/viewer diagnostics are expected fixtures |
| Mock and media fake E2E | PASS: software-only command route and media replay/cached-replay evidence |
| External dependency tests/verifiers | PASS: 23 tests; reconstructed Hermes state, MIT license, and llama.cpp manifest checks |
| Source bootstrap | PASS: <code>./scripts/bootstrap --hermes</code> and <code>./scripts/bootstrap --llama-cpp</code> reconstructed the reviewed trees |
| Full <code>./scripts/bootstrap --check</code> | FAIL/ENVIRONMENT_GAP: source checks pass, but the fresh candidate lacks the externally provisioned Hermes virtual environment and generated llama-server binary; the LM Studio CLI is no longer a prerequisite |
| Documentation, shell and Python checks | PASS: 74 Markdown files/8 schema mappings; changed shell syntax; changed Python compilation; <code>git diff --check</code> |
| Publication/security scans | PASS for changed active source/config: no new private-LAN default, secret value, private user path, file URL, generated checkout, alternate or pose path/blob; the historical deleted pose object remains known history evidence |
| Live LM/MQTT/service/device acceptance | SKIPPED by Gate 5B.1 scope; no live readiness or inference claim follows |

The environment gap is a provisioning/readiness result, not a reason to
weaken the external LM ownership contract. The implementation result remains
<code>IMPLEMENTATION_REMEDIATED_NONLIVE</code>; a future live Gate 5B retry
requires a new process ledger and separate authorization.

## Gate 5B.3 Hermes compression failure-path remediation (historical remediation)

Review date: 2026-08-28. The second Gate 5B attempt passed L0, L1, L2 and L3,
then failed L5 after one resident <code>/invoke</code> request. The observed
resident result was HTTP 500 after the log sequence
<code>Context compression failed after 3 attempts</code> followed by
<code>KeyError: 'final_response'</code>. Gate 5B rollback passed; the external
LM process and canonical MQTT broker were preserved. No physical Temi or
Android action occurred. Gate 5B.3 did not rerun live Gate 5B.

### Failure trace and root-cause classification

| Required observation | Gate 5B.3 result |
|---|---|
| Failure entry | <code>AIAgent.run_conversation</code> sent the synthetic request to the OpenAI-compatible LM endpoint; the context-overflow branch entered bounded recovery. |
| Compression trigger | The context-overflow classifier handled the provider rejection and called <code>AIAgent._compress_context</code>. |
| Compression retry | <code>AIAgent.run_conversation</code> retried the provider request after each bounded compression attempt and stopped after three recovery attempts. |
| Failed result shape before the fix | A dict with <code>messages</code>, <code>completed</code>, <code>api_calls</code>, <code>error</code>, <code>partial</code>, <code>failed</code> and <code>compression_exhausted</code>, but no <code>final_response</code>. |
| Unsafe access | <code>AIAgent.chat</code> unconditionally evaluated <code>result["final_response"]</code>, masking the original failure with a KeyError. |
| Resident boundary | <code>RequestHandler.do_POST</code> caught the secondary exception and returned the generic HTTP 500 path. |
| Compression trigger root cause | <code>MODEL/API_CONFIGURATION_MISMATCH</code>. Hermes/resident were configured for a 64,000-token context, while the retained external LM evidence rejected an approximately 11,508-token request at an available 4,096-token context. |
| Session/state classification | Not stale state: the resident used <code>temi-resident</code>, started with zero history, loaded no memory and loaded no checkpoint. |

The deterministic prompt audit measured a roughly 9,717-token pre-request
composition from the six resident skill inputs, the synthetic care overlay,
the Hermes system prompt, ten native tool schemas and the synthetic user
request. It was below Hermes's configured 32,000-token compression threshold,
so proactive compression did not trigger. The backend rejected the request
only after it was sent because its actual available context was 4,096. The
one-turn message set had no removable middle; all three recovery attempts
therefore preserved the same message shape and did not call the auxiliary
compression model. The trigger is consequently an external provider-context
mismatch, not an oversized memory or skill payload, incorrect session reuse,
token-threshold bug or incorrect Hermes-side limit.

### Remediation contract and evidence

Patch <code>0010-fix-temi-compression-failure-contract.patch</code> adds
<code>HermesConversationError</code>, makes exhausted compression results carry
<code>final_response: null</code> plus bounded failure metadata, and makes
<code>AIAgent.chat</code> raise the typed error rather than index a missing
field. The resident maps that typed error to HTTP 500 with only an allowlisted
error class, original failure category and retryable flag. It does not return
provider error text, prompts, payloads or a traceback. Normal empty and
non-empty successful responses remain unchanged.

The failure-path tests also assert that the one-turn compressor returns the
input unchanged without invoking the summary model. The source-level fix is
therefore owned by the Temi-specific Hermes overlay and the resident boundary;
the external context mismatch is explicitly classified as an environment
provisioning prerequisite rather than silently changing the configured limit.
The implementation state is <code>IMPLEMENTED_NONLIVE</code>, not
<code>LIVE_VERIFIED</code>. A future live retry requires external evidence that
the loaded model context is compatible with the configured Hermes context.

### Gate 5B.3 non-live verification matrix

| Check | Result |
|---|---|
| Hermes compression/failure contract | PASS: 6/6 with mocked provider failures, missing response field, success responses, parser-category preservation and one-turn compression no-op. |
| Hermes compressor regression | PASS: 72/72; <code>tests/agent/test_context_compressor.py</code>. |
| Hermes agent-loop regression | PASS: 22/22; mocked tool/text loop and tool-pool behavior. |
| Resident contract | PASS: 6/6; direct success output, HTTP success response, typed HTTP 500 failure response, health after failure and no raw provider text. |
| Root tools/lifecycle suite | PASS: 150/150. |
| HermesTemiBridge suite | PASS: 166/166. |
| temi_backend and adapter | PASS: 25/25, including adapter-focused 7/7. |
| anomaly_detection suite | PASS: 34/34. |
| Mock E2E and Media fake E2E | PASS: both software-only routes. |
| External dependency, submodule and license tests | PASS: 23/23; formal team URL, pinned base, ten patch hashes, new tree and MIT license. |
| Fresh Hermes A/B reconstruction | PASS: both initialized from the team remote at the pinned base, applied 0001–0010, passed second bootstrap, matched final tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>, had clean nested checkouts and no alternates. |
| Source bootstrap | PASS: <code>./scripts/bootstrap --sources</code> twice; Hermes and llama source pins reconstructed. |
| Full <code>./scripts/bootstrap --check</code> | FAIL/ENVIRONMENT_GAP: source and license checks passed; the candidate environment does not contain the separately provisioned generated <code>llama-server</code> binary. |
| Documentation, shell and Python checks | PASS: 74 first-party Markdown files, 8 schema mappings, changed shell syntax, changed Python compilation and <code>git diff --check</code>. |
| Security/publication scan | PASS: 0 active private-LAN defaults, 0 tracked secret matches, 0 file-URL dependencies, no current pose path/blob, 0 reachable blobs at or above 50/100 MiB and no Git alternates. |
| Full upstream Hermes test inventory | INCOMPLETE/ENVIRONMENT_BASELINE: the 19,736-case runner exposed unrelated existing failures and did not complete within the bounded observation; focused Hermes compressor, agent-loop and 0010 suites passed. |
| Live LM/MQTT/service/device acceptance | SKIPPED: Gate 5B.3 forbids a live retry, model inference, service operation, MQTT publication/subscription, Android/Temi and physical action. |

## Gate 5B.5 resident probe safety and client-disconnect remediation (historical remediation)

Review date: 2026-08-28. This is a non-live remediation on the publication
candidate based at <code>release/github-v1@657b39e0064c45c2346f0cdff35581eb01e01d08</code>.
The candidate does not rerun Gate 5B, start or stop a service, invoke LM Studio,
publish or subscribe MQTT, or contact Android/Temi.

Gate 5B Retry #3's intended malformed L2 request was actually:

```json
{"prompt":"synthetic-invalid-active-resident"}
```

The request was an HTTP <code>POST</code> to <code>/invoke</code> with a
non-empty string prompt, no <code>active_resident</code> field, and a five-second
client timeout. The current handler treats <code>active_resident</code> as
optional, so validation passed and the resident called Hermes/model. The
resident request count changed <code>0 -&gt; 1</code> before the client
disconnected. The correct classification is
<code>L2_PROBE_FAILURE_CLASS=ACCEPTANCE_HARNESS_DEFECT</code>; it is not a
resident validation defect and is not L5 acceptance evidence.

The old response path caught the first <code>BrokenPipeError</code> from the
successful response write in the broad invocation exception handler, then
attempted a second HTTP 500 write. That write raised another
<code>BrokenPipeError</code> and emitted an unhandled request-thread traceback.
The resident boundary now catches only expected client transport disconnects
while emitting a response, records the exception class without payloads, and
does not retry a response on a closed socket. The resident does not invent
cancellation; an already-started inference may finish. Other response-writer
exceptions remain visible.

The exact future inference-impossible L2 request is:

```bash
cd /TemiAgent
curl -sS --max-time 5 -D - \
  -H 'Content-Type: application/json' \
  --data '{"prompt":"gate5b5-malformed-active-resident-probe","active_resident":"malformed"}' \
  http://127.0.0.1:8765/invoke
```

It must return HTTP <code>400</code> with <code>invalid active_resident</code>
before <code>ResidentHermes.invoke()</code>, with zero resident inference and
zero LM HTTP calls. A future L5 request alone may use a 60-second timeout and
the total future retry budget is exactly one model request; L2 and L3 remain at
zero. This contract is documented for a separately authorized retry only.

### Gate 5B.5 non-live verification matrix

| Check | Result |
|---|---|
| Resident HTTP boundary | PASS: 5/5 focused tests; malformed probe rejected before invoke, valid prompt compatibility preserved, BrokenPipe/ConnectionReset handling covered, delayed client disconnect leaves health available, and normal writer errors remain visible. The combined HTTP and health command ran 8/8. |
| Hermes compression failure contract | PASS: 6/6 inherited focused tests; no Hermes source or patch changed. |
| Root tools/lifecycle suite | PASS: 155 tests. |
| HermesTemiBridge suite | PASS: 166 tests. |
| temi_backend and adapter | PASS: 25 tests and focused adapter 7 tests. |
| anomaly_detection suite | PASS: 34 tests. |
| Mock E2E and Media fake E2E | PASS: both software-only routes. |
| External dependency/publication tests | PASS: 23 tests; formal Hermes verifier reports the pinned base, ten patches and final tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>. |
| Documentation, shell and Python checks | PASS: documentation validator, required shell syntax, changed-file compilation and <code>git diff --check</code>. |
| Live LM/MQTT/service/device acceptance | SKIPPED: this gate forbids live inference, lifecycle operations, MQTT publication/subscription, Android/Temi and physical action. |

## Snapshot (historical Gate 5A.1 baseline)

| Item | Snapshot | Meaning |
|---|---|---|
| Project root | `/TemiAgent` in `yiting.TemiAgent_gpu_all` | Canonical project command boundary. |
| Root branch | `main` | Canonical root branch; Gate 3.4 work runs in an isolated candidate worktree. |
| Root HEAD | `12aff3bfdfe526c17a25a2681aea2afad7112b33` | Canonical HEAD is unchanged during Gate 5A.1. |
| Configured root remotes | None in the canonical local snapshot | Root publication push was not performed; the separate Hermes team remote was independently verified. |
| Lifecycle status | `RUNNING`; `reason=READY` | Read-only `./scripts/demo --json mqtt status` found the canonical MQTT broker healthy at `0.0.0.0:1883`. |
| Canonical listeners | One listener on `0.0.0.0:1883` | This is a read-only runtime observation, not a Gate 5A.1 service operation. |
| Service operation | No service was started, stopped or restarted for Gate 5A.1. The prior Gate 5A <code>lms ls</code> wake-up remains recorded as an incident. | Hardware, MQTT and external-service state were not intentionally transitioned by this gate. |

The canonical worktree contains pre-existing Gate 1A, synthetic-fixture and
documentation changes. Gate 5A.1 changes are isolated in the candidate
worktree; the candidate does not modify the canonical runtime or publication
branch. A running MQTT status is reported only as the read-only Phase 0
observation.

## Canonical V1 flow and ownership

```text
Temi Android ASR/camera
  -> tools/temi_overview_adapter.py
  -> canonical ASR/perception events plus allowlisted paths
  -> HermesTemiBridge validation
  -> resident Hermes JSON-only reasoning
  -> HermesTemiBridge action validation and dispatch
  -> temi/{robot_id}/cmd/request
  -> Temi Android executor
  -> temi/{robot_id}/cmd/result and Bridge trace
```

`hermes_temi_bridge/` is the canonical safety boundary: it validates event
identity, evidence paths, Hermes JSON and actions before command publication.
Hermes returns a structured JSON-only plan and does not publish MQTT or control
hardware. Anomaly perception is optional and event-producing only; it does not
become a general dispatcher. Android source and hardware execution are external
to this workspace.

## Capability state

`IMPLEMENTED` means code exists. `HARDWARE_FREE_VERIFIED` means the named unit,
mock or fake path actually passed. `HOST_LIVE_VERIFIED` means the exact bounded
Gate 5 deployment contract passed in the designated host; it does not prove
physical Android/Temi execution, general viewer/GPU behavior or portable
environment reproducibility. `LIVE_NOT_VERIFIED` means no current live claim is
made for that boundary. `LEGACY`, `EXPERIMENTAL` and `DEMO_ONLY` are scope
labels, not stronger verification levels.

| Capability | State | Evidence boundary |
|---|---|---|
| Bridge validation, schemas and dispatch boundary | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; HOST_LIVE_VERIFIED` | Gate 5 L3 exercised the validated callback/publication path without physical side effect; real Android execution remains external. |
| Canonical ASR adapter route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Adapter and Bridge software paths are tested; Temi microphone/session evidence is not current. |
| Media v1.1 command/result route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Fake Android media lifecycle is tested; real playback is not verified. |
| Resident Hermes wrapper/mock route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; HOST_LIVE_VERIFIED` | Gate 5 accepted resident health, inference-impossible L2 and one bounded L5 request with external-only LM; Android/Temi remains external. |
| Immediate abnormal-care Bridge route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Synthetic event, bounded notification, Hermes follow-up and action validation are tested; real recipient/device execution is not. |
| Gate 5 host runtime: external LM, MQTT, resident and Bridge | `HOST_LIVE_VERIFIED` | Exact publication/runtime candidate passed L0–L3 and L5; MQTT was reused, LM was preserved, and L4 physical acceptance was not run. |
| Structured care memory | `DEMO_ONLY; HARDWARE_FREE_VERIFIED` | Tracked memory is synthetic/de-identified fixture material; runtime and production data are excluded. |
| Legacy ASR/video/local-VLM route | `LEGACY; LIVE_NOT_VERIFIED` | `temi_backend/` remains for compatibility; historical hardware observations are not current evidence. |
| Continuous abnormal perception viewer | `EXPERIMENTAL; LIVE_NOT_VERIFIED` | Optional viewer/event producer; model output is not medical or fall-detection certification. |
| Temi Android, physical camera/microphone/playback, viewer/GPU general behavior, Discord and real perception | `LIVE_NOT_VERIFIED` | External hardware/provider boundaries remain separate or unverified; Gate 5 host evidence must not be generalized. |

## External, generated and optional artifacts

- `third_party/hermes/` records the original upstream URL, the team-controlled
  remote, the formal `hermes-agent/` submodule path and URL, the pinned base
  commit/tree, the ordered ten-patch series, the expected final tree and the
  verified license identity. The historical local integration commit
  `126aa304cda027679fc84212925bbd5329ada20b` remains historical; generated local
  final commit IDs are not dependency authority.
- Gate 3.4 independently fetched the exact pinned object from
  `https://github.com/YI-TING-EE13/hermes-agent.git` and verified base tree
  `bda69c575e65725bf9264dd1288a63093cea3cc3`. The manifest records `VERIFIED`
  MIT license identity for `LICENSE`; `tools/verify_hermes_license.py` checks
  both the pinned Git blob and the checked-out file.
- `HERMES_DEPENDENCY_GOVERNANCE: TEAM_REMOTE_AND_SUBMODULE_VERIFIED`. The root
  gitlink stays at the pinned base while bootstrap applies patches `0001`–`0010`
  in the submodule worktree and verifies final tree
  `47e9f1411e585769c055d0c6ee4417bebcdc6f70`. The clean-clone A/B acceptance is
  recorded in the Gate 3.4 section below.
- `hermes-agent/` is a formal external submodule, not TemiAgent root source or
  vendored source. The root `hermes-skills/` directory remains a reviewable
  mirror; resident Hermes reads the patched submodule skill paths. No manual
  copy is used.
- Gate 3.3 changed-bootstrap reachability is Hermes-only:
  `scripts/bootstrap_hermes.sh` invokes the new bounded-process and Hermes license
  tools, while `scripts/bootstrap_llama_cpp.sh` remains independent and invokes neither.
  `LLAMA_REGRESSION_REQUIRED: NO` for Gate 3.4 because no llama reconstruction
  path or shared bootstrap helper changed. Gate 3.3 evidence is carried forward:
  two independent final-candidate publication clones each passed first and second llama-only
  bootstraps with matching evidence: A and B both produced
  `HEAD=0b7154066e8544ed88d92ae2132cc1e055cf6304` and
  `TREE=1020a771795f406b8891d18ee607b4da3783fa7f`, with clean roots.
- `third_party/llama_cpp/` holds the manifest and README; bootstrap materializes
  the generated external checkout at `anomaly_detection/third_party/llama.cpp/`.
  Neither path is TemiAgent root source, and the clone does not imply a model
  binary or model weights.
- `yolo26x-pose.pt` is an optional external weight expected by the resource manifest;
  the manifest records local size/hash expectations only. Source, version, license
  and redistribution restrictions require maintainer confirmation. No download URL
  is asserted.
- A clean clone must not be expected to contain downloaded models, checkpoints,
  caches, recordings, runtime images or private configuration.

## Publication and release blockers

1. This local root has no configured remote. A maintainer must choose and configure
   the team-accessible publication target before claiming clean-clone delivery.
2. The historical HEAD contains the large pose checkpoint. Gate 1A removes it from
   the current index while preserving history; Gate 1B performs no history rewrite.
3. Pose model provenance, version, license and redistribution restrictions remain
   unresolved; do not publish or redistribute the local weight until confirmed.
4. Local credential-bearing environment files are owner-only and excluded from Git;
   owner handling/rotation remains outside this documentation gate.
5. The Hermes team remote and formal submodule contract are verified from Gate
   3.4. Gate 5 final evidence adoption advances the local
   <code>release/github-v1</code> ref from the documented publication baseline
   to the bounded documentation/evidence commit under an old-value guard. No
   root publication push is performed here; the public URL and push target
   remain maintainer-owned external facts.

## Documentation authority

Use the root [README](../README.md), this status page, the
[repository map](REPOSITORY_MAP.md), [project overview](architecture/project_overview.md),
[contract traceability](architecture/contract_traceability.md) and the sole current
[Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md) in that order. The
[quick reference](operations/DEMO_QUICK_REFERENCE.md) is a compact companion, not
a second lifecycle authority. Dated, machine-specific and direct-service material
is explicitly marked legacy in the documentation index and retained only as evidence.

For the current handover, start with [developer setup](operations/developer_setup.md),
[deployment handover](operations/demo_deployment_handover.md), [configuration
reference](operations/demo_configuration_reference.md), [verification and
acceptance](operations/verification_and_acceptance.md) and
[student handover](project/STUDENT_HANDOVER.md). The complete document
classification is in [DOCUMENT_AUTHORITY_MAP](DOCUMENT_AUTHORITY_MAP.md).

## Verification snapshot (historical baseline)

The final Gate 1B verification below was run after the documentation changes. It
remains hardware-free and did not start a long-running service:

| Check | Result |
|---|---|
| `./scripts/bootstrap --check` | PASS |
| `cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests` | 166 PASS |
| `cd temi_backend && uv run --locked --offline pytest` | HISTORICAL Gate 1B evidence; the current accepted baseline is 25/25 PASS in the Gate 4.1 section below. |
| `cd anomaly_detection && uv run --locked --offline python -m unittest discover -s tests` | 34 PASS |
| `python3 -m unittest discover -s tools/tests` | HISTORICAL Gate 1B evidence; the current accepted baseline is 133/133 PASS in the Gate 4.1 section below. |
| `python3 tools/e2e_test_runner.py` | PASS; `status:ok` with mock command topic |
| `python3 tools/media_v11_fake_e2e.py` | PASS; 4 request traces, 7 result traces, cached replay confirmed |
| `python3 tools/validate_documentation.py` | HISTORICAL Gate 1B evidence; the current inventory definition and count are maintained in <code>DOCUMENT_AUTHORITY_MAP.md</code>. |
| Live Temi/Android/MQTT/LM Studio/GPU/Discord/perception gates | SKIPPED / LIVE_NOT_VERIFIED |

No service was started merely to validate documentation.

The bootstrap row above is historical Gate 1B evidence and does not replace the
fresh Gate 3.4 Hermes evidence below.

## Gate 3.3 standards-remediation evidence

The following checks were run in the isolated candidate at
`43c0c7c18a4b119f807b5dd04ef197272e43bbdd` (before this documentation-only
evidence update). No Hermes public fetch, service operation, MQTT publish, or
full Gate 3 run was performed.

| Command or evidence | Result |
|---|---|
| `python3 -m py_compile tools/bounded_process.py tools/run_bounded_process.py tools/verify_hermes_license.py tools/tests/test_bounded_process.py tools/tests/test_hermes_license.py tools/tests/test_external_dependency_publication.py` | PASS |
| `python3 -m unittest tools.tests.test_bounded_process tools.tests.test_hermes_license tools.tests.test_external_dependency_publication tools.tests.test_validate_documentation` | PASS; 15 tests |
| `python3 tools/validate_documentation.py` | HISTORICAL Gate 3.3 evidence; the current inventory definition and count are maintained in <code>DOCUMENT_AUTHORITY_MAP.md</code>. |
| `bash -n scripts/bootstrap scripts/bootstrap_hermes.sh scripts/bootstrap_llama_cpp.sh` | PASS |
| `git diff --check 2efcd7bc2668dafcbccc5461b9bc4ac275a2606d..HEAD` | PASS |
| Private-LAN, private-path/embedded-URL, secret, generated-source, pose-path/blob and large-object scans | PASS; 0 private-LAN defaults, no current pose path/blob, no tracked generated checkouts, no blobs >= 50 MiB |
| `python3 -m unittest discover -s tools/tests` | HISTORICAL Gate 3.3 environment evidence; the incomplete environment was superseded by the reconstructed 133/133 Gate 3.4 evidence and the current Gate 4.1 run below. |
| Two independent `git clone --no-local` publication clones, each running `./scripts/bootstrap --llama-cpp` twice | PASS; both roots clean, llama HEAD `0b7154066e8544ed88d92ae2132cc1e055cf6304`, tree `1020a771795f406b8891d18ee607b4da3783fa7f` |

## Gate 3.4 formal Hermes submodule evidence

Gate 3.4 was executed from the exact clean Gate 3.3 candidate at
`6dae2429064c3af54af5b7004db9e1755412b2f1` in an isolated worktree. The team
remote, exact pinned object, pinned base tree and pinned MIT license were fetched
and independently verified before adoption:

| Contract | Result |
|---|---|
| Team remote `https://github.com/YI-TING-EE13/hermes-agent.git` reachable | PASS; `git ls-remote` returned `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` for `refs/heads/main`. |
| Pinned commit `a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` available from team remote | PASS |
| Pinned base tree | PASS; `bda69c575e65725bf9264dd1288a63093cea3cc3` |
| Pinned license | PASS; `LICENSE`, MIT, `Copyright (c) 2025 Nous Research`, verified Git blob and SHA-256. |
| Formal root submodule | PASS; `.gitmodules` and the `hermes-agent` gitlink use the team URL and pinned base commit; no floating branch. |
| Root-owned overlay | PASS; manifest order and SHA-256 values for patches `0001`–`0009` produce final tree `968f1668a05fafd09461c17a835198421f14a48f`. |

The canonical setup is one bounded submodule initialization followed by
`./scripts/bootstrap --hermes` (or `./scripts/bootstrap --sources` for the
combined source flow). Bootstrap verifies the formal submodule and license, then
applies the root-owned patches in the submodule worktree. It does not clone,
fetch, use the original upstream, use a local checkout, use a file URL or use
Git alternates. A second invocation is a final-tree verification no-op.

Two independent Fresh A/B root clones were created with `git clone --no-local`
from Gate 3.4 commit `551790e0553ce58490f2883b857cd246db20058c`. Each initialized
the submodule from the team remote with the documented bounded depth-1 command,
verified the same base commit/tree, reconstructed the nine patches, verified the
same final tree and license, ran the setup a second time, and found all required
Temi skills. A/B patch aggregate hash was
`d793be62374675de58c51d3a4d9d62753026ddb56a8410de57d92352b5462698`; both
submodules were clean and had no alternates. The generated local final commit
IDs differed, as expected; content identity did not drift.

The complete reconstructed-candidate command
`python3 -m unittest discover -s tools/tests` passed `133/133`. This includes
the lifecycle, external-dependency, Hermes license, formal-submodule, bootstrap,
skills, documentation, shell/compile, root hardware-free mock-E2E and media fake
checks. `git diff --check` passed. Gate 3.3's independent llama A/B evidence is
carried forward because Gate 3.4 changed no llama reconstruction path or shared
bootstrap helper; no runtime service, MQTT publish/subscribe, model inference,
Android operation or hardware operation was performed.

## Gate 4.1 repair verification

The current repair candidate is verified with the same source-backed,
hardware-free baseline used for Gate 4. The test counts below are current
candidate evidence; historical snapshots above are not current baselines.

| Check | Result |
|---|---|
| <code>python3 tools/validate_documentation.py</code> | PASS; 74 active first-party Markdown documents and 8 schema mappings |
| <code>python3 -m unittest discover -s tools/tests</code> | PASS; 133/133 |
| <code>cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests</code> | PASS; 166/166 |
| <code>cd temi_backend && uv run --locked --offline pytest</code> | PASS; 25/25 |
| External dependency, Hermes submodule and license tests | PASS; 23/23 |
| Shell syntax, Python compilation and <code>git diff --check</code> | PASS |
| Live Temi/Android/MQTT/LM Studio/GPU/Discord/perception gates | SKIPPED; not authorized by Gate 4.1 |

No service was started, stopped or restarted for Gate 4.1. No MQTT message was
published or subscribed.

## Gate 4 disposition (historical)

Gate 3 external dependency reproducibility is closed PASS. Gate 4.1's
documentation repair was reviewed in isolation, and the Gate 4 final retry
adopted it locally at
<code>release/github-v1=654110f621c6eff5e4defaa54f0722b2a916f50a</code>; Gate
5A leaves that ref unchanged. Real Android, Temi, broker, model/GPU, Discord
and perception verification require their own authorized operational gate.
Gate 4.1 performed no service operation or MQTT publication. Gate 5A performed
no authorized or intentional lifecycle service operation and no MQTT
publication; its unintended LM Studio process wake-up is recorded above.
Neither gate pushed the root repository.
