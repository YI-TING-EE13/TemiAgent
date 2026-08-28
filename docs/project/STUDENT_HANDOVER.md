# AI6 TemiAgent Student Handover

Status: <code>CURRENT_AUTHORITY</code>; last reviewed for Gate 5A.1: 2026-08-28.

This page is the short handover contract for a new maintainer. Start here
after reading the [repository README](../../README.md), then follow the
[developer setup](../operations/developer_setup.md). It does not replace
runtime schemas, executable validators, module READMEs or the
[Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md).

## Start here

| Order | Read | Decision it answers |
|---:|---|---|
| 1 | [README](../../README.md) | What the repository is, what it is not, and where the canonical boundaries are. |
| 2 | [CURRENT_STATUS](../CURRENT_STATUS.md) | What is verified, external, experimental, historical or currently unverified. |
| 3 | [REPOSITORY_MAP](../REPOSITORY_MAP.md) | Which directories are source, generated, runtime-only or historical. |
| 4 | [Developer setup](../operations/developer_setup.md) | How to prepare a clean clone in the designated container. |
| 5 | [Contract traceability](../architecture/contract_traceability.md) | Which code/schema owns each cross-module contract. |
| 6 | [Deployment handover](../operations/demo_deployment_handover.md) | Which host, container, device or external provider owns each service. |
| 7 | [Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md) | The exact current lifecycle grammar and safe ownership semantics. |
| 8 | [Configuration reference](../operations/demo_configuration_reference.md) | Private paths, flags, ports, credentials and validation. |
| 9 | [Verification and acceptance](../operations/verification_and_acceptance.md) | Which checks are hardware-free and which require an external gate. |
| 10 | [Troubleshooting](../operations/demo_troubleshooting.md) | The symptom-to-evidence path when a check fails. |

## Authority map

The first document in this table is the current prose authority for the topic.
Executable source and runtime schemas remain the final authority when prose
conflicts with them. Supplemental documents must defer to these entries.

| Topic | Current authority | Source/verification boundary |
|---|---|---|
| Repository scope and entry | [README](../../README.md) | Root source and governance; no medical, emergency or autonomous-care claim. |
| Current implementation/status | [CURRENT_STATUS](../CURRENT_STATUS.md) | Maintainer snapshot; real devices, providers and GPU remain live-unverified unless fresh evidence is recorded. |
| Repository/publication layout | [REPOSITORY_MAP](../REPOSITORY_MAP.md) | Git paths, submodule/gitlink, generated source and runtime boundary. |
| Architecture | [project overview](../architecture/project_overview.md) | Module boundaries; runtime code and schemas win over historical sections. |
| Cross-module contracts | [contract traceability](../architecture/contract_traceability.md) | Runtime schemas under <code>hermes_temi_bridge/schemas/</code> are authoritative. |
| Developer setup/environment | [developer setup](../operations/developer_setup.md) | Container, submodule, locked environments, external artifacts and clean-clone order. |
| External dependencies | [developer setup](../operations/developer_setup.md) (with source-specific [Hermes](../../third_party/hermes/README.md) and [llama.cpp](../../third_party/llama_cpp/README.md) references) | One onboarding authority; source-specific manifests, pins, licenses and reconstruction scripts remain linked there. |
| Configuration | [configuration reference](../operations/demo_configuration_reference.md) | <code>tools/demo_lifecycle.py</code>, tracked templates and private runtime validation. |
| Secrets | [configuration reference](../operations/demo_configuration_reference.md) | Owner-only private env and credential file rules; no secret value is tracked. |
| Demo lifecycle | [Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md) | <code>scripts/demo</code> parser, exact process identity and readiness gates. |
| Deployment and host ownership | [deployment handover](../operations/demo_deployment_handover.md) | AI6 host/container, Temi/Android, LAB606 and external provider responsibilities. |
| Service safety/recovery | [safe service operations](../operations/safe_service_operations.md) | Exact PID, port, rollback and containment policy. |
| MQTT transport | [MQTT module README](../../mqtt/README.md) | Broker configuration and topic index; Bridge code/schema owns message validation. |
| Bridge | [Bridge README](../../hermes_temi_bridge/README.md) | Bridge module behavior; runtime schemas and validators are authoritative. |
| Hermes integration | [Hermes dependency README](../../third_party/hermes/README.md) | Formal team submodule plus root-owned nine-patch overlay. |
| Anomaly backend | [anomaly README](../../anomaly_detection/README.md) | Optional experimental event producer/viewer; never a general dispatcher. |
| Troubleshooting | [Demo troubleshooting](../operations/demo_troubleshooting.md) | Read-only evidence and safe escalation. |
| Testing/acceptance | [verification and acceptance](../operations/verification_and_acceptance.md) | Hardware-free suite matrix and external acceptance boundaries. |
| Student handover | This document | Reading order, questions and release handover. |
| Release process | The release section of this document | Candidate review/adoption is separate from root push; Gate 4's final retry adopted the reviewed ref locally, but did not push. |

## System boundary in one paragraph

Temi Android produces ASR/camera-side events and consumes allowlisted command
requests. The overview adapter adapts legacy inputs; it does not own command
dispatch. Hermes returns JSON-only plans. HermesTemiBridge validates events,
paths, Hermes output and actions, then owns command publication. The Android
application owns hardware execution and command results. Anomaly detection is
an optional event producer. The product path is Temi Android to the AI6 MQTT
broker; a LAB606 host TCP connection to the broker is not a required product
path.

The current Android-facing values are:

| Contract | Value |
|---|---|
| Robot ID used by the accepted AI6 contract | <code>temi-01</code> |
| Command topic | <code>temi/temi-01/cmd/request</code> |
| Result topic | <code>temi/temi-01/cmd/result</code> |
| Delivery | QoS 1, <code>retain=false</code> |
| Schema authority | <code>hermes_temi_bridge/schemas/</code> |
| Android source/APK | External to this repository; no AI6 claim of device implementation or live playback. |

The values above are contract values, not a public LAN endpoint. The tracked
production client default is loopback; the broker listener binds according to
the controlled local Mosquitto configuration. A deployment-specific Android
endpoint belongs in private configuration or the Android owner’s handover,
never in a public template.

## Forty-question handover gap matrix

<code>ANSWERED</code> means the AI6 repository gives a source-backed answer.
<code>PARTIAL</code> means the answer is explicit but requires the named
external owner or maintainer input. There are no <code>MISSING</code> items.

| # | Question | Status | Answer and authoritative path |
|---:|---|---|---|
| 1 | What is TemiAgent? | ANSWERED | AI6 is a safety-bounded Temi integration: adapter, Bridge validation/dispatch, Hermes reasoning boundary, optional perception and Android-facing contracts. Start with [README](../../README.md). |
| 2 | Which repository/branch is authoritative? | ANSWERED | The maintainer-designated canonical runtime checkout is on root branch <code>main</code>. In this audited deployment it is mounted inside the designated container as <code>/TemiAgent</code>. This is an explicitly labeled deployment callout; generic clones use the user-selected <code>REPO_ROOT</code> in [developer setup](../operations/developer_setup.md). See [CURRENT_STATUS](../CURRENT_STATUS.md). |
| 3 | What is publication versus runtime main? | ANSWERED | Runtime main is the maintained canonical checkout and may contain private dirty work. <code>release/github-v1</code> is the publication candidate/ref; Gate 4 used an isolated candidate and its final retry adopted the reviewed ref locally without pushing. |
| 4 | How do I clone it? | PARTIAL | Use step 1 of [developer setup](../operations/developer_setup.md). The root publication URL is not configured in the audited local checkout and must be supplied by the publication maintainer. |
| 5 | How do I initialize Hermes? | ANSWERED | Run the bounded <code>git submodule update --init --recursive --depth=1</code>, then <code>./scripts/bootstrap --hermes</code> or <code>./scripts/bootstrap --sources</code>; verify the manifest and license. |
| 6 | Why is Hermes a submodule? | ANSWERED | The team-owned base source is kept as a formal gitlink while TemiAgent keeps a reviewable root-owned patch overlay; source identity and integration changes remain separable. |
| 7 | What is the team Hermes fork? | ANSWERED | <code>https://github.com/YI-TING-EE13/hermes-agent.git</code>; it is recorded in <code>.gitmodules</code> and <code>third_party/hermes/manifest.json</code>. |
| 8 | How do patches work? | ANSWERED | The pinned base commit is checked, patches <code>0001</code> through <code>0009</code> are applied in order, the final tree and license are verified, and generated local commit IDs are not dependency identity. |
| 9 | What external dependencies exist? | ANSWERED | Hermes source/runtime, llama.cpp source/build, LM Studio/model/cache, viewer models, optional pose weight, Android media/APK and optional Discord provider are external. See [developer setup](../operations/developer_setup.md). |
| 10 | What tools must be installed? | PARTIAL | The designated container must provide Python, uv, Git, Bash and Mosquitto; Docker/image availability is host-owned. Installation source for the container and several host tools is a maintainer dependency, documented as an environment pin gap. |
| 11 | Which versions matter? | PARTIAL | Python <code>>=3.12</code> and lockfiles are source-backed. Observed tool versions are recorded as snapshots; uv, Git, Bash, Mosquitto, container image, LM Studio and CUDA/driver versions are not pinned and are explicit <code>ENVIRONMENT_PIN_GAP</code>s. |
| 12 | How is the Python environment created? | ANSWERED | Run <code>uv sync --frozen</code> in each project, with <code>--extra mqtt</code> for <code>hermes_temi_bridge</code>; lockfiles must not be updated during setup. |
| 13 | Where do private configs go? | ANSWERED | The canonical ignored config is <code>/TemiAgent/.runtime/demo/demo.env</code>; custom configs are absolute owner-only files outside Git worktrees. |
| 14 | Where do secrets go? | ANSWERED | Credentials belong only in owner-only private env files, especially the separately referenced Discord env file; mode <code>0600</code>, owner-only parent, never tracked or printed. |
| 15 | What must never be committed? | ANSWERED | Real credentials, webhook URLs, private LAN addresses, user paths, real care records, images, logs, runtime state, model caches/weights, recordings, checkpoints and generated source checkouts. |
| 16 | Where do models go? | ANSWERED | LM Studio cache and viewer GGUF/mmproj are external under configured private locations; model identifiers are tracked, model bytes are not. Optional pose weights require provenance approval. |
| 17 | Which services exist? | ANSWERED | Managed candidates are LM Studio, MQTT, overview adapter, resident Hermes, Bridge, optional gateway and viewer; newcomer mock adds local mock Android/Discord and model/resident/viewer doubles. |
| 18 | Which machine runs each service? | ANSWERED | The AI6 container runs the software stack; the AI6 host provides Docker/mount; Temi Android runs outside AI6; LAB606 is a development/control host; external providers own their services. See [deployment handover](../operations/demo_deployment_handover.md). |
| 19 | How do I check service status? | ANSWERED | Use read-only <code>./scripts/demo --json doctor</code>, <code>./scripts/demo --json status</code>, or the MQTT-only <code>./scripts/demo --json mqtt status</code> where its canonical production config applies. |
| 20 | How do I start services? | ANSWERED | Only an authorized operator may run <code>./scripts/demo start</code>; the exact ownership and readiness contract is in [DEMO_OPERATOR_GUIDE](../operations/DEMO_OPERATOR_GUIDE.md). MQTT-only has its separate <code>mqtt start</code> selector. |
| 21 | How do I safely stop services? | ANSWERED | Use <code>./scripts/demo stop</code> or the exact MQTT-only <code>mqtt stop</code>; the lifecycle signals only recorded verified identities and refuses foreign/unowned processes. |
| 22 | How do I diagnose failures? | ANSWERED | Preserve the read-only JSON, run the checks named in [troubleshooting](../operations/demo_troubleshooting.md), inspect exact PID/port/log evidence, and escalate without broad process control. |
| 23 | What ports/interfaces matter? | ANSWERED | Production defaults are LM Studio <code>1234</code>, MQTT <code>1883</code>, adapter <code>8080/8081</code>, resident <code>8765</code>, viewer <code>8010/8011</code>; newcomer uses isolated high ports. Unix callback sockets remain private runtime paths. |
| 24 | How does Temi reach MQTT? | ANSWERED | The Android app connects to the deployment-configured AI6 broker endpoint; AI6 client defaults are loopback and do not publish a lab address. The broker and Android owner must agree on reachability. |
| 25 | What is robot_id? | ANSWERED | The accepted AI6 robot identifier is <code>temi-01</code>; Bridge allowlists it and topic paths use the robot ID. Unknown or disallowed IDs are validation failures. |
| 26 | What are command/result topics? | ANSWERED | Requests use <code>temi/{robot_id}/cmd/request</code>; Android results use <code>temi/{robot_id}/cmd/result</code>; the concrete accepted ID is <code>temi-01</code>. |
| 27 | Where are schemas? | ANSWERED | Runtime authority is <code>hermes_temi_bridge/schemas/</code>; <code>docs/schemas/</code> is a synchronized reader copy. The traceability map owns the mapping and update-together rule. |
| 28 | How does Bridge fit in? | ANSWERED | It is the canonical safety boundary: validates inbound events, paths, Hermes JSON and actions, then owns command dispatch and trace evidence. |
| 29 | How does Hermes fit in? | ANSWERED | Hermes is a JSON-only reasoning runtime behind the resident wrapper; it does not publish MQTT or control hardware directly. |
| 30 | How does anomaly detection fit in? | ANSWERED | It is an optional experimental perception/event producer and viewer; it is not a general hardware dispatcher or medical/fall-detection service. |
| 31 | Which tests run without hardware? | ANSWERED | Bridge, backend, anomaly, tools, lifecycle, schema, external-dependency, docs, mock E2E and media-fake suites are hardware-free when their locked environments are present. |
| 32 | Which tests require hardware? | PARTIAL | Real Android/Temi session, playback, camera, microphone, device result and physical observation require the Android/device owner and are not AI6-local tests. |
| 33 | What is currently verified? | ANSWERED | Gate 3 recorded clean-clone Hermes/llama reproducibility, licenses, source manifests and the hardware-free matrix; current real Android, LM Studio/GPU, Discord, Temi and perception claims remain live-unverified. |
| 34 | What remains experimental? | ANSWERED | Optional anomaly viewer, pose preprocessing, local model/viewer deployment and feature-gated media/identity/care Demo paths remain bounded or external; see [CURRENT_STATUS](../CURRENT_STATUS.md). |
| 35 | What is legacy? | ANSWERED | Dated first-year, streaming, direct-service and broad historical runbooks are retained as evidence and marked <code>LEGACY</code>; current lifecycle authority remains <code>scripts/demo</code>. |
| 36 | Which docs are current authority? | ANSWERED | Use this authority map, [README](../../README.md), [CURRENT_STATUS](../CURRENT_STATUS.md), [REPOSITORY_MAP](../REPOSITORY_MAP.md), [developer setup](../operations/developer_setup.md), [operator guide](../operations/DEMO_OPERATOR_GUIDE.md), deployment, configuration, testing and troubleshooting. |
| 37 | How do I update dependencies? | ANSWERED | Change the owning project declaration and lockfile together, run affected tests and docs/security checks, update authority/status documentation, and obtain maintainer review. |
| 38 | How do I make a release? | PARTIAL | Prepare an isolated candidate from the publication ref, run the required validation, have a maintainer review/adopt the ref, then perform any separately authorized root push. Gate 4's final retry adopted the reviewed ref locally; root push remains separate and unauthorized here. |
| 39 | How do I prove a fresh clone is healthy? | ANSWERED | Follow all ten [developer setup](../operations/developer_setup.md) steps, verify submodule/final trees and licenses, run the focused/full hardware-free matrix, then use read-only doctor/status. |
| 40 | What should I check before a Demo? | ANSWERED | Confirm branch/config/runtime ownership, <code>doctor</code>, status, exact ports/PIDs, LM Studio/model/GPU if production, fresh Android evidence if claiming <code>DEMO_READY</code>, and the acceptance checklist. |

Handover result: <code>ANSWERED=35</code>,
<code>PARTIAL=5</code>, <code>MISSING=0</code>. Each partial answer has an
individual owner and future gate in the register below.

## Partial handover register

Each record identifies the fact that remains outside the portable repository
contract and the action a student can take without guessing or changing the
runtime boundary.

### #4 — How do I clone it?

- <code>QUESTION_NUMBER</code>: 4
- <code>QUESTION</code>: How do I clone it?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: The audited local snapshot does not contain the root publication URL, and a URL cannot be inferred safely.
- <code>GATE5A_OBSERVED_FACT</code>: Read-only <code>git remote -v</code> returned no root remote; the local <code>release/github-v1</code> ref is <code>654110f621c6eff5e4defaa54f0722b2a916f50a</code>. This does not supply a public clone URL.
- <code>MISSING_FACT</code>: The maintainer-designated public repository URL and any access requirement.
- <code>OWNER</code>: Publication maintainer / repository owner.
- <code>FUTURE_GATE</code>: Final GitHub publication gate.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Request the maintainer URL, substitute it only for <code>TEMIAGENT_REPO_URL</code>, and never use a local checkout, file URL or Git alternate as the publication source.

### #10 — What tools must be installed?

- <code>QUESTION_NUMBER</code>: 10
- <code>QUESTION</code>: What tools must be installed?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: The repository requires a designated container and host Docker support but does not own their provisioning.
- <code>GATE5A_OBSERVED_FACT</code>: The designated container used image <code>pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel</code> with host Docker <code>29.3.0</code>; Python, uv, Git, Bash, Mosquitto, CMake, Ninja and GCC were available, while jq, lsof and clang were absent. These are deployment observations, not installation requirements or pins.
- <code>MISSING_FACT</code>: The approved container image, Docker host provisioning and installation source for the required container tools.
- <code>OWNER</code>: AI6 container/infrastructure maintainer.
- <code>FUTURE_GATE</code>: Gate 5 runtime/environment acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Use the designated container and record <code>python3 --version</code>, <code>uv --version</code>, <code>git --version</code>, <code>bash --version</code> and <code>mosquitto -h</code>; do not add an ad-hoc host or image recipe.

### #11 — Which versions matter?

- <code>QUESTION_NUMBER</code>: 11
- <code>QUESTION</code>: Which versions matter?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: Python floors and lockfiles are source-backed, but several host, container and provider versions remain unpinned.
- <code>GATE5A_OBSERVED_FACT</code>: The container reported Python <code>3.12.3</code>, uv <code>0.10.12</code>, Git <code>2.43.0</code>, Bash <code>5.2.21</code>, Mosquitto <code>2.0.18</code>, CUDA <code>13.0</code> with driver <code>580.142</code>, and four RTX 5090 devices. Hermes <code>venv</code> uses Python <code>3.11.15</code>. None of these observations closes the environment-pin gap.
- <code>MISSING_FACT</code>: Approved versions or digests for uv, Git, Bash, Mosquitto, the container image, LM Studio and CUDA/driver software.
- <code>OWNER</code>: AI6 environment maintainer.
- <code>FUTURE_GATE</code>: Gate 5 runtime/environment acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Use the checked-in lockfiles and record observed tool versions as evidence; do not invent minimums or update lockfiles to hide an environment gap.

### #32 — Which tests require hardware?

- <code>QUESTION_NUMBER</code>: 32
- <code>QUESTION</code>: Which tests require hardware?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: Real Android/Temi sessions, physical playback, camera, microphone and device results cannot be verified by this repository alone.
- <code>GATE5A_OBSERVED_FACT</code>: Four host-visible RTX 5090 devices and the configured CUDA toolchain were observed, but no model inference, Android/Temi device action, camera/microphone session or physical playback was performed or accepted.
- <code>MISSING_FACT</code>: A fresh Android/Temi session with device observation and the corresponding command/result evidence.
- <code>OWNER</code>: Temi Android/device integration owner.
- <code>FUTURE_GATE</code>: Gate 5 runtime/environment acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Run the hardware-free Bridge, backend, anomaly, tools and mock/fake checks, then request a separately authorized device acceptance record; do not label software evidence as live hardware evidence.

### #38 — How do I make a release?

- <code>QUESTION_NUMBER</code>: 38
- <code>QUESTION</code>: How do I make a release?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: Release-ref adoption and root publication require maintainer authorization and a selected publication target.
- <code>GATE5A_OBSERVED_FACT</code>: The local <code>release/github-v1</code> ref is <code>654110f621c6eff5e4defaa54f0722b2a916f50a</code>; the root checkout has no configured remote and no push was performed. The Gate 5A.1 candidate, including its lifecycle source-gate compatibility fix, is <code>codex/github-v1-live-environment-audit</code> and remains unadopted.
- <code>MISSING_FACT</code>: Approval to adopt the reviewed release ref and the authorized root GitHub remote/push target.
- <code>OWNER</code>: Release maintainer / repository owner.
- <code>FUTURE_GATE</code>: Final GitHub publication gate after maintainer review and authorization.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Prepare an isolated candidate, run the required validation, and request review; do not modify <code>release/github-v1</code>, rewrite history or push.

## Release handover

The historical Gate 4.1 repair candidate is derived from
<code>release/github-v1@d66a046395aed21712b00cba43d4ea1b2d9f23de</code> in the
isolated worktree named by that task. Its reviewed handover repair was adopted
locally by the Gate 4 final retry at
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>.
Reviewers should inspect the candidate diff and its validation evidence, then
decide separately whether to perform any root publication push. The canonical
<code>main</code> checkout and the release ref are not handover targets for an
unreviewed documentation change. No root push is part of this gate.

Gate 5A created a separate, uncommitted documentation-only candidate on branch
<code>codex/github-v1-live-environment-audit</code>, based on
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>. It records
observed deployment provenance, runtime blockers, publication/runtime parity and
the safe Gate 5B strategy. Gate 5A.1 additionally reconciles the formal Hermes
submodule's expected root worktree status with the full-stack lifecycle source
gate: only verifier-confirmed <code>state=RECONSTRUCTED</code> plus a clean
nested checkout is accepted, while all other dirty paths still fail closed.
The candidate remains isolated and unadopted. It does not modify canonical
<code>main</code>, advance <code>release/github-v1</code>, or perform an
authorized/intentional lifecycle operation, MQTT publication or push; the
unintended Gate 5A audit wake-up is recorded in
<code>CURRENT_STATUS.md</code>.

## Gate 5A.1 review handover

The Gate 5A.1 candidate is the branch
<code>codex/github-v1-live-environment-audit</code> based on
<code>release/github-v1@654110f621c6eff5e4defaa54f0722b2a916f50a</code>.
Its intended result is
<code>AI6_TEMIAGENT_GATE5A_1_RUNTIME_DELTA_RECONCILED</code> with
<code>C_ACCEPTED_INTENDED_DELTA</code>. Review
[CURRENT_STATUS](../CURRENT_STATUS.md) for the exact 82-path comparison, the
21 executable/runtime/config/dependency/test paths, the object identities and
the Gate 5B source-root/start/rollback contract.

The candidate-only lifecycle correction accepts the expected root status
<code> M hermes-agent</code> after the formal nine-patch Hermes reconstruction
only when <code>verify_hermes_submodule.py</code> succeeds with
<code>state=RECONSTRUCTED</code>. It still rejects index changes, unverified or
base-only checkouts, dirty nested Hermes state and every other unexpected
path. The focused acceptance and full regression results belong to the
candidate evidence; no result here authorizes service operation.

For any later Gate 5B run, use the final reviewed candidate commit as the
isolated <code>GATE5B_SOURCE_ROOT</code>, verify its exact HEAD, and supply a
new owner-only runtime config and runtime root outside Git. Because the
candidate branch is not <code>main</code>, the private config may use
<code>DEMO_GIT_BRANCH_POLICY=disabled</code> only alongside exact-HEAD and
dirty-path verification. Reuse the verified external MQTT listener without a
restart; make LM Studio/API readiness, model/GPU policy, optional
gateway/viewer resources and Android/Temi acceptance separate gates.

No public root remote, approved environment/provider pins, LM Studio model/API
readiness, Android/Temi evidence or physical acceptance was invented by this
handover. The candidate is review-ready, not Gate 5B-live-accepted.
