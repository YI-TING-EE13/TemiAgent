# TemiAgent Current Status

狀態：CURRENT；governance snapshot：2026-08-28。

This page is the maintained status snapshot for implementation, verification,
runtime honesty and publication blockers. It is not a runtime health endpoint and
does not replace the runtime schemas, module READMEs or the
[canonical Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).

## Gate 4.1 handover repair candidate

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

## Gate 5A live environment audit (read-only)

Audit date: 2026-08-28. The facts in this section are an observed deployment
snapshot, not portable version pins and not a live-acceptance claim. Project
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
| LM Studio — LM/runtime owner | <code>GET /v1/models</code> succeeds; identifier <code>google/gemma-4-31b</code>, context <code>64000</code>, configured GPU policy, exact lifecycle identity and port <code>1234</code> agree | Requires separate authorization. Stop only the recorded exact LM Studio identity; preserve MQTT and dependent state. |
| MQTT — AI6 operator | Either read-only <code>./scripts/demo --json mqtt status</code> proves the external <code>1883</code> lineage, or the disposable <code>29183</code> profile proves its own exact managed lineage and TCP readiness | Default has no transition. An isolated broker may be stopped only through its exact owner record, never by name or port alone. |
| Adapter/resident/Bridge — AI6 service owner | Adapter listeners <code>8080/8081</code>, resident <code>/health</code> on <code>8765</code>, Bridge callback socket, exact PIDs, and redacted logs all pass; synthetic no-op route remains validator-bound | Start in canonical order only after authorization. Roll back in reverse exact-PID order; do not bypass Bridge with raw commands. |
| Gateway/viewer — optional owners | Gateway health/status, viewer <code>/health</code> on <code>8010</code>, llama listener <code>8011</code> and model/resource checks pass when enabled | Optional and no Discord claim. Stop exact recorded identities in reverse order; keep the main route separately classified. |
| Synthetic software-only acceptance — verification owner | Canonical event/trace and no-op contract checks pass without physical Android, real notification or unrestricted model inference | Use the isolated runtime/evidence root only; no raw MQTT command/result fabrication and no change to canonical MQTT. |
| Android/Temi acceptance — device owner | Fresh Android session, subscription, accepted/started or playing result, and physical observation for each authorized action | Separate hardware authorization and device-owner rollback. A Bridge publish alone cannot advance this stage. |
| Rollback — lifecycle owner | Final redacted status, protected-port inventory, exact lifecycle records and retained evidence | Reverse order: viewer, gateway, Bridge, resident, adapter, isolated MQTT, LM Studio. The canonical external MQTT broker remains running. |

Gate 5B remains blocked by the missing root publication URL/remote, the
unavailable LM Studio API and unpinned LM Studio version, the full-stack
services not being live, absent physical Android/Temi acceptance, external
model/pose provenance, and the unresolved <code>llmster</code> audit incident.
The local llama build cache reduces uncertainty but does not create a portable
build pin.

Gate 5A records facts for Gate 5B; it does not close any of these blockers,
advance <code>release/github-v1</code>, push, or authorize a service operation.

## Gate 5A.1 publication/runtime delta reconciliation

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
  reconstruction is accepted and an ordinary generated external checkout
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

| Path | Canonical object | Publication object | Intent and live-risk classification |
|---|---|---|---|
| <code>.gitignore</code> | <code>7ef7c8e6651d683875dc53a911e89ac3f6217042</code> | <code>daa6ff7eee8fd6511bab5e1c5464a92c09c49f80</code> | Ignore generated/private artifacts; intended publication boundary. |
| <code>.gitmodules</code> | — | <code>fd770e5901e3bfb999240f69bbba788bd1fe01e9</code> | Formal Hermes team submodule; intended source contract. |
| <code>config/demo_resources.json</code> | <code>e2138d0bd65e5406eb7eaeb65c7b2f0d5e6027e4</code> | <code>3c09c7b3106eb4048b41b39b00c5cde95ec0486e</code> | External resource manifest and optional pose mapping; intended artifact boundary. |
| <code>anomaly_detection/yolo26x-pose.pt</code> | <code>d1fa01ade8358577cde976874ccf6abfa94eb9fa</code> | — | Remove large model bytes from publication; intended privacy/provenance boundary. |
| <code>hermes-agent</code> | — | <code>a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2</code> | Gitlink to team-owned base; intended external-source contract. |
| <code>scripts/bootstrap_hermes.sh</code> | <code>ae39dc08dba5878c00fc3bf7c64878596fd6cb1d</code> | <code>872ebcbf05cd49af2e924020999ee71a4e5a86a0</code> | Reconstruct formal submodule plus nine root patches; intended reproducibility behavior. |
| <code>scripts/bootstrap_llama_cpp.sh</code> | <code>ba7512f53ac47ec99dff581abfab30b709814aa8</code> | <code>fd599537429df1b3a4d984edd570fa24c9e8730d</code> | Pin/check llama source and license; intended reproducibility behavior. |
| <code>temi_backend/tests/test_overview_adapter.py</code> | <code>908a1448f36e8182479f3b0b61008f1f3a35ec18</code> | <code>24b70dbbc486e68dacfb8eccf19bef54bbf6236f</code> | Cover broker input boundary; test-only intended coverage. |
| <code>third_party/hermes/manifest.json</code> | <code>0cff78c0be7759efbc124a09861b00acaa24eb02</code> | <code>7248e858e2a2336ee2e3f546cb5ec0de42dcdeef</code> | Record team remote, base, patches, final tree and license; intended source contract. |
| <code>third_party/llama_cpp/manifest.json</code> | <code>b432bf4942fb3635b60a6a7ad4c2eed3f6e324b2</code> | <code>6eee32ecdd43f0984108acd006ea08a4e3278c22</code> | Record llama commit/tree/license; intended source contract. |
| <code>tools/bounded_process.py</code> | — | <code>2354ae606f649707f78c34e920359ecaf3c2a5bd</code> | Bound subprocess lifetime and exact process group; intended safety helper. |
| <code>tools/run_bounded_process.py</code> | — | <code>80bf4cf385b4dd1ff44d80056b4452978867d640</code> | CLI wrapper for bounded operations; intended safety helper. |
| <code>tools/start_temi_pc_services.sh</code> | <code>78522a00ecf2228008a38dca8b73f3ca718458cc</code> | <code>742d007b5f07036c609847b6a3cd6d9a66e7fb26</code> | Require operator-provided <code>PC_IP</code>; intended removal of a private default. |
| <code>tools/start_temi_pc_services_background.sh</code> | <code>9fc57d3b983f1b73e0d20a469858ed610a4d5657</code> | <code>73771a443577bbd28abd15afdebea825358fc5</code> | Require operator-provided <code>PC_IP</code>; intended removal of a private default. |
| <code>tools/temi_overview_adapter.py</code> | <code>a71a28da334def32ba47d8d4a10b42e0f79af9c9</code> | <code>2cb852c4718543e0eb14ca2a4781941976a3afcf</code> | Require explicit broker CLI/env input; intended fail-closed security behavior. |
| <code>tools/tests/test_bounded_process.py</code> | — | <code>7c1684f9ed0fd0fa7597941157110f436e78821a</code> | Cover bounded process groups; test-only intended coverage. |
| <code>tools/tests/test_external_dependency_publication.py</code> | — | <code>48d37acb53aeb3bfc4052e69e684f47a36717713</code> | Cover external publication manifests; test-only intended coverage. |
| <code>tools/tests/test_hermes_license.py</code> | — | <code>c87e232afc82a08db88b96cbf7b677327a2f43bb</code> | Cover Hermes license boundary; test-only intended coverage. |
| <code>tools/tests/test_hermes_submodule.py</code> | — | <code>7f565df9be6be92bb190b1a039ed0d14991a1b51</code> | Cover formal submodule/base/final-tree contract; test-only intended coverage. |
| <code>tools/verify_hermes_license.py</code> | — | <code>0b22151d2cda14fd8bf3be471a1e3e27f7d4b699</code> | Verify reconstructed Hermes license; intended source gate. |
| <code>tools/verify_hermes_submodule.py</code> | — | <code>68f071696c04a0636786c111cef9fbd16f7a7d63</code> | Verify gitlink, base, final tree, nested cleanliness and no alternates; intended source gate. |

The MQTT lifecycle implementation, tracked broker configuration and
MQTT-only status contract are byte-identical between the two baseline trees.
The publication-only adapter, legacy PC-IP and dependency deltas are
therefore accepted as intended. The only additional Gate 5A.1 runtime code
change is the narrowly scoped formal-submodule source-gate compatibility
fix described above.

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

For Gate 5B the operator must provide a deployment-specific Temi-facing
endpoint in the private runtime input. The candidate documentation and
tracked templates intentionally contain no private LAN default. The safe
default for this Gate 5B plan is <code>MQTT_OWNERSHIP=external</code> and
read-only proof of the already healthy managed broker on its configured
production listener; no broker restart or MQTT publish/subscribe is part of
Gate 5A.1.

| Resource | Source/layout contract | Gate 5B requirement |
|---|---|---|
| MQTT broker | External owner; configured private host/port and managed Mosquitto evidence | Reuse verified listener; one owner, exact lineage and TCP probe. |
| Hermes base/overlay | <code>hermes-agent</code> formal gitlink plus root patch overlay under <code>third_party/hermes/patches/</code> | Bounded submodule init, manifest verification, nine patches, final tree/license, nested clean. |
| Hermes environment | External <code>hermes-agent/venv</code>; Python 3.11 was observed | Provision from the locked Hermes project environment; do not treat an ignored local venv as source. |
| llama.cpp | Pinned manifest commit/tree and external build output | Reconstruct/check source; use an externally provisioned executable only after path and model checks. |
| Gemma GGUF/mmproj | External LM Studio/model cache; tracked identifiers, not model bytes | LM Studio API/model/context/GPU gate before resident start. |
| Optional pose weight | Logical path <code>anomaly_detection/yolo26x-pose.pt</code>; removed from publication and provenance not closed | Optional viewer path only; provenance/license must be approved before enabling. |
| Android/Temi | External application and physical device | Separate device-owner acceptance; no software-only result advances it. |
| Runtime state | Private <code>TEMIAGENT_RUNTIME_ROOT</code> containing logs, memory, shared metadata, PID/state/socket files | Fresh owner-only root per run; no runtime artifacts in Git or source root. |

### Hermes reconstructed layout and publication preflight

The exact Gate 5B source root is the final reviewed Gate 5A.1 candidate
worktree at its recorded final commit, not canonical <code>main</code> and not
the mutable release ref. From that root, the bounded sequence is:

~~~text
git submodule update --init --recursive --depth=1
./scripts/bootstrap_hermes.sh --bootstrap
./scripts/bootstrap_llama_cpp.sh --bootstrap
./scripts/bootstrap --check
./tools/verify_hermes_submodule.py
./tools/verify_hermes_license.py
~~~

The formal Hermes layout after reconstruction is: root gitlink at the
manifest base commit, a clean nested checkout, the root-owned nine-patch
overlay applied into that checkout, final tree
<code>968f1668a05fafd09461c17a835198421f14a48f</code>, and the required MIT
license. The llama.cpp check records commit
<code>0b7154066e8544ed88d92ae2132cc1e055cf6304</code> and tree
<code>1020a771795f406b8891d18ee607b4da3783fa7f</code>. Generated build
directories, venvs, model caches and runtime files remain external/ignored.

Gate 5A.1 publication preflight was run in a disposable clone without
starting a service: bounded recursive submodule initialization, Hermes
bootstrap, llama bootstrap, source/license checks, and the documentation
validator passed. A newcomer configuration was materialized in that
disposable root. No MQTT publication/subscription, model inference, Android
operation, GPU mutation, or full-stack start was performed. The final
disposable-clone result must additionally show the reconstructed-submodule
source gate as PASS before Gate 5B is considered.

### Gate 5B exact source root and ephemeral inputs

Before Gate 5B, the operator must record:

- <code>GATE5B_SOURCE_ROOT</code>: an isolated checkout of
  <code>codex/github-v1-live-environment-audit</code> at the reviewed
  candidate commit recorded in the Gate 5A.1 handoff.
- <code>GATE5B_EXPECTED_HEAD</code>: the exact candidate commit; verify it
  before reading private configuration or starting any process.
- <code>GATE5B_RUNTIME_CONFIG</code>: a new owner-only mode-0600 absolute env
  file outside Git, not created during this gate.
- <code>TEMIAGENT_RUNTIME_ROOT</code>: a new owner-only runtime root separate
  from the source checkout.
- <code>DEMO_GIT_BRANCH_POLICY=disabled</code> only because the reviewed
  candidate branch is not named <code>main</code>; exact HEAD and dirty-path
  checks remain mandatory. Any configuration that disables those checks is
  invalid.

The private input must define the broker endpoint/ownership, model/API
ownership, required production ports, runtime paths, resource paths and
notification mode. Credentials remain in separately referenced owner-only
files. No ephemeral input is committed, printed, copied into a log or
retained as a public fixture.

### LM Studio, MQTT and process ledger

LM Studio is a separate Gate 5B readiness boundary. The first check is
read-only HTTP <code>GET /v1/models</code> on configured port
<code>1234</code>, requiring the configured
<code>google/gemma-4-31b</code> identifier, context <code>64000</code> and
GPU policy. A process, model file or cached build alone is not readiness.
If LM Studio is managed, the authorized lifecycle path is the managed
supervisor, which invokes the existing three-GPU loader and performs
mutating LM Studio control. The <code>lms</code> CLI is not a read-only
inspection tool and must not be invoked during Gate 5A.1.

The following ledger is the pre-start preservation record:

| Process/service | Observed state | Ownership for Gate 5B | Stop policy |
|---|---|---|---|
| Managed MQTT supervisor/child | Supervisor PID <code>924834</code>, child PID <code>924835</code>; <code>RUNNING/READY</code>; listener <code>0.0.0.0:1883</code> | Pre-existing canonical owner; never Gate 5B-owned | Preserve; no signal or restart. |
| Packaged <code>llmster</code> internal component | PID <code>1051985</code>, child <code>1051997</code>; loopback listener <code>127.0.0.1:41343</code>; API <code>1234</code> absent | Pre-existing audit side effect; not Gate 5B-owned | Preserve during this gate; no broad or guessed stop. |
| Adapter, resident, Bridge, gateway, viewer | No Gate 5A.1 start operation; no new ownership record | Gate 5B may own only exact records created after authorization | Capture cwd, command, executable, start identity, ports and logs before any stop. |

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

### Gate 5B start order, rollback and staged acceptance

Gate 5A.1 does not execute this sequence. After explicit Gate 5B
authorization, the planned minimum production order is:

~~~text
L0 source/config/port preflight
  -> L1 LM Studio API/model/GPU readiness (managed LM may be started here)
  -> L2 reuse and verify external MQTT; do not restart it
  -> L3 adapter -> resident -> Bridge
  -> L4 optional gateway/viewer after their resources and health checks
  -> L5 software-only trace/no-op acceptance
  -> separate Android/Temi and model-inference acceptance
~~~

The actual lifecycle start order for managed components is
<code>lmstudio → mqtt → adapter → resident → bridge → mock_android →
mock_discord → gateway → viewer</code>; external ownership means the
lifecycle health-checks instead of starting that component. Production
Gate 5B must configure MQTT as external when reusing the observed broker,
disable optional gateway/viewer until their own owners and resources are
ready, and use the candidate's private config. The planned command, never
executed here, is:

~~~text
./scripts/demo --config "$GATE5B_RUNTIME_CONFIG" start
~~~

| Level | Entry evidence | Required result | Rollback boundary |
|---|---|---|---|
| L0 | Exact candidate HEAD, source status, manifests/licenses, private config metadata, collision scan | No unowned dirty path, alternate object, invalid path or secret exposure | No service transition; discard only isolated candidate/runtime input. |
| L1 | LM API/model/context/GPU and exact managed identity | Model service is ready or external ownership is proven | Stop only the exact Gate 5B-owned LM identity; never touch the pre-existing <code>llmster</code>. |
| L2 | MQTT JSON status, supervisor/child lineage, listener and TCP probe | One verified external broker owner | No transition for reuse; an isolated broker is stopped only by its exact record. |
| L3 | Adapter ports, resident <code>/health</code>, Bridge callback/health, exact PIDs and redacted logs | Canonical validation/dispatch path is healthy | Stop exact Gate 5B records in reverse order: Bridge, resident, adapter. |
| L4 | Optional gateway/viewer health, resource/model checks and exact listeners | Optional path is separately ready | Stop exact viewer/gateway records before L3 components. |
| L5 | Synthetic non-sensitive event, canonical trace/no-op contract and redacted evidence | Software-only route passes without physical side effect | Reverse exact owned records; do not publish raw MQTT or claim device acceptance. |

If a later Gate 5B run fails, rollback is the reverse of the records created
by that run: viewer, gateway, Bridge, resident, adapter, any isolated broker,
then the Gate 5B-owned LM supervisor. The canonical MQTT supervisor and the
pre-existing <code>llmster</code> audit process are outside that ownership set.
No name-based kill, broad pattern, reboot or runtime-data deletion is allowed.

### Physical side effects and model readiness

Levels L0-L5 remain software-only. No Android command, physical Temi motion,
notification delivery or real-care action may be used as a smoke test. A
separate device owner must authorize and observe Android/Temi acceptance,
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

## Snapshot

| Item | Snapshot | Meaning |
|---|---|---|
| Project root | `/TemiAgent` in `yiting.TemiAgent_gpu_all` | Canonical project command boundary. |
| Root branch | `main` | Canonical root branch; Gate 3.4 work runs in an isolated candidate worktree. |
| Root HEAD | `12aff3bfdfe526c17a25a2681aea2afad7112b33` | Canonical HEAD is unchanged during Gate 4. |
| Configured root remotes | None in the canonical local snapshot | Root publication push was not performed; the separate Hermes team remote was independently verified. |
| Lifecycle status | `RUNNING`; `reason=READY` | Read-only `./scripts/demo --json mqtt status` found the canonical MQTT broker healthy at `0.0.0.0:1883`. |
| Canonical listeners | One listener on `0.0.0.0:1883` | This is a read-only runtime observation, not a Gate 4 service operation. |
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
mock or fake path actually passed. `LIVE_NOT_VERIFIED` means there is no current
claim for a real Temi, Android session, MQTT broker, LM Studio/model service,
GPU, Discord recipient or real perception stream. `LEGACY`, `EXPERIMENTAL` and
`DEMO_ONLY` are scope labels, not stronger verification levels.

| Capability | State | Evidence boundary |
|---|---|---|
| Bridge validation, schemas and dispatch boundary | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Bridge unit/integration tests and fake routes pass; real Android execution is external. |
| Canonical ASR adapter route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Adapter and Bridge software paths are tested; Temi microphone/session evidence is not current. |
| Media v1.1 command/result route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Fake Android media lifecycle is tested; real playback is not verified. |
| Resident Hermes wrapper/mock route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Local wrapper and mock integration are testable; live provider, model and GPU are not verified. |
| Immediate abnormal-care Bridge route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Synthetic event, bounded notification, Hermes follow-up and action validation are tested; real recipient/device execution is not. |
| Structured care memory | `DEMO_ONLY; HARDWARE_FREE_VERIFIED` | Tracked memory is synthetic/de-identified fixture material; runtime and production data are excluded. |
| Legacy ASR/video/local-VLM route | `LEGACY; LIVE_NOT_VERIFIED` | `temi_backend/` remains for compatibility; historical hardware observations are not current evidence. |
| Continuous abnormal perception viewer | `EXPERIMENTAL; LIVE_NOT_VERIFIED` | Optional viewer/event producer; model output is not medical or fall-detection certification. |
| Temi Android, real MQTT, LM Studio, GPU, Discord and real camera stream | `LIVE_NOT_VERIFIED` | External dependencies and hardware gates were not authorized or available in this snapshot. |

## External, generated and optional artifacts

- `third_party/hermes/` records the original upstream URL, the team-controlled
  remote, the formal `hermes-agent/` submodule path and URL, the pinned base
  commit/tree, the ordered nine-patch series, the expected final tree and the
  verified license identity. The historical local integration commit
  `126aa304cda027679fc84212925bbd5329ada20b` remains historical; generated local
  final commit IDs are not dependency authority.
- Gate 3.4 independently fetched the exact pinned object from
  `https://github.com/YI-TING-EE13/hermes-agent.git` and verified base tree
  `bda69c575e65725bf9264dd1288a63093cea3cc3`. The manifest records `VERIFIED`
  MIT license identity for `LICENSE`; `tools/verify_hermes_license.py` checks
  both the pinned Git blob and the checked-out file.
- `HERMES_DEPENDENCY_GOVERNANCE: TEAM_REMOTE_AND_SUBMODULE_VERIFIED`. The root
  gitlink stays at the pinned base while bootstrap applies patches `0001`–`0009`
  in the submodule worktree and verifies final tree
  `968f1668a05fafd09461c17a835198421f14a48f`. The clean-clone A/B acceptance is
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
   3.4. <code>release/github-v1</code> contains the adopted Gate 3 dependency
   chain and the Gate 4 final-retry handover adoption at
   <code>654110f621c6eff5e4defaa54f0722b2a916f50a</code>. No root publication
   push is performed here.

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

## Verification snapshot

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

## Gate 4 disposition

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
