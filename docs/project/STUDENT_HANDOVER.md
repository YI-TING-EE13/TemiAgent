# AI6 TemiAgent Student Handover

Status: <code>CURRENT_AUTHORITY</code>; last reviewed for Gate 5 final evidence
and L4.3 Android provenance adoption: 2026-08-29.

This page is the short handover contract for a new maintainer. Start here
after reading the [repository README](../../README.md), then follow the
[developer setup](../operations/developer_setup.md). It does not replace
runtime schemas, executable validators, module READMEs or the
[Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md).

## Gate 5 final evidence adoption

Gate 5 host runtime acceptance is closed by the separately completed Gate 5B
Retry #4. This documentation freeze adopts that evidence; it does not rerun
the live stack. The accepted publication baseline was
<code>release/github-v1@59d568b079ce260e2144c410b0f9397d8b026913</code>.

The frozen production contract is:

- LM Studio is <code>EXTERNAL_ONLY</code>. The lifecycle never starts, stops,
  unloads, daemon-downs, server-stops or globally mutates the provider.
- External readiness must be established before Demo start. The expected API
  identifier is <code>google/gemma-4-31b</code>, runtime context is
  <code>64000</code>, and context must be verified from runtime metadata.
- MQTT is independently managed/reusable; the accepted run reused the
  configured broker without restart. Explicit broker configuration remains
  mandatory and no tracked private-LAN fallback is allowed for <code>PC_IP</code>.
- Hermes reconstruction is the pinned base plus patches
  <code>0001</code>–<code>0010</code> producing tree
  <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>.
- L2 malformed input is inference-impossible. The accepted request budget is
  exactly <code>L1=0; L2=0; L3=0; L5=1</code>.
- Lifecycle stop targets only positively owned process identities. Pre-existing
  LM/MQTT processes remain foreign/external unless explicitly proven otherwise.

Gate status is <code>GATE5_HOST_RUNTIME=CLOSED_PASS</code>.
<code>L4_ANDROID_PROVENANCE=CLOSED_PASS</code> is adopted from LAB606 evidence;
the installed Android 1.0.2 (3) artifact is accepted as-is. Temi physical
execution, device playback, camera/microphone and complete L4 E2E remain
<code>NOT_YET_RUN</code>. <code>READY_FOR_L4_E2E=YES</code> and
<code>GATE6=NOT_STARTED</code>.

The accepted host evidence includes L0–L3 PASS, L5 PASS, L2 HTTP 400 before
inference, L3 validated identity-result publication without physical side
effect, and L5 HTTP 200 with one validated <code>speak</code> action. Rollback
left zero Gate-owned processes/listeners and preserved the external LM and
canonical MQTT broker. PIDs, run IDs, temporary worktrees and runtime
directories are <code>ACCEPTANCE_EVIDENCE_ONLY</code>, not portable
requirements. See [CURRENT_STATUS](../CURRENT_STATUS.md) and the
[verification guide](../operations/verification_and_acceptance.md) for the
complete redacted evidence and retained failed-attempt history.

## L4.3 Android provenance adoption

LAB606 reports <code>LAB606_ANDROID_FINAL_ARTIFACT_PROVENANCE_CONFIRMED</code>.
The external Android repository is on branch <code>main</code> at revision
<code>3e2fc0376e5b5ca3992e697fc030cdc08173c639</code>; accepted baseline
<code>8c458888657efca5384c6d51e5ec57e8b385d987</code> is an ancestor and no
post-baseline implementation, build-config or signing changes were found.

The accepted artifact is
<code>temi-agent-android-public/app/build/outputs/apk/demo/app-demo.apk</code>,
package <code>com.robotemi.agent</code>, version <code>1.0.2 (3)</code>, with
SHA-256 <code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>.
Its signer certificate digest is
<code>4D:A8:46:1B:45:B0:2F:AD:CB:04:2F:63:15:1F:EE:05:D5:6E:BD:51:05:EB:72:1D:7D:62:E3:0B:88:51:3A:7F</code>;
schemes v1/v2 are present, debuggable is <code>NO</code>, and the embedded
revision is the accepted baseline. The observed target
<code>192.168.50.204:5555</code> is classified
<code>OBSERVED_AI6_DEPLOYMENT</code> and is not a portable default.

Installed package, version, hash, signer, embedded revision and whole-APK
content match the accepted artifact: <code>EXACT_APK_MATCH</code>.
<code>ANDROID_PROVENANCE=CLOSED_PASS</code> and
<code>ACCEPTED_AS_IS</code> mean no replacement, reinstall or data reset was
performed. The earlier E2DD reference is retained only as the legacy 1.0.0 (1)
acceptance artifact; the L4.2 mismatch finding is superseded by
<code>SUPERSEDED_BY_AUTHORITATIVE_LAB606_PROVENANCE_RECOVERY</code>.

This closes artifact provenance only. It does not claim Android behavior,
physical playback, device observation or complete Temi E2E acceptance, and it
does not authorize ADB, MQTT, service or inference operations.

## Gate 5B.1 LM ownership repair (historical remediation)

Gate 5B stopped at the L1 ownership-safety gate because the former managed LM
path used global `lms` cleanup against pre-existing provider state. Production
LM Studio is now `LMSTUDIO_OWNERSHIP=external`: the lifecycle requires one
configured listener and a compatible HTTP `/v1/models` response, but never
starts, stops, unloads, or reconfigures the provider. Only the newcomer mock
LM server is lifecycle-managed. A legacy/unknown LM record is preserved and
causes `STOP_INCOMPLETE_OWNERSHIP`; a future live retry must create a fresh
process ledger. The historical PIDs `1051985` and `1051997` are incident
evidence only and must not be recreated or treated as current requirements.

This repair is `IMPLEMENTATION_REMEDIATED_NONLIVE`. Direct `lms ls`, `lms ps`,
`lms unload --all`, `lms server stop`, and `lms daemon down` are not read-only
audits. The accepted ephemeral-input security pattern remains a mode `0700`
private runtime root containing the mode `0600` config file.

## Gate 5B.3 Hermes compression failure repair (historical remediation)

The second Gate 5B attempt passed L0–L3 and failed L5 after one resident
request. The external LM backend rejected an approximately `11508`-token
request at an available `4096` context even though the configured Hermes and
resident context was `64000`; the first request plus three recovery retries
therefore exhausted compression. The resident began with session
`temi-resident`, zero history, no memory and no checkpoint, and the one-turn
prompt had no removable middle. This is classified as
`MODEL/API_CONFIGURATION_MISMATCH`, not stale session or memory pressure.

The ten-patch Hermes overlay now returns typed bounded failure metadata and
never assumes a failed result contains `final_response`. The resident maps
that error to a safe HTTP 500 response and remains healthy. Patch 0010 and the
new reconstructed tree are hardware-free verified; the result is
`IMPLEMENTED_NONLIVE`, not live model verification. A future Gate 5B retry
requires separately verified external provider context compatibility.

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
| Hermes integration | [Hermes dependency README](../../third_party/hermes/README.md) | Formal team submodule plus root-owned ten-patch overlay and bounded failure contract. |
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
| 8 | How do patches work? | ANSWERED | The pinned base commit is checked, patches <code>0001</code> through <code>0010</code> are applied in order, the final tree and license are verified, and generated local commit IDs are not dependency identity. |
| 9 | What external dependencies exist? | ANSWERED | Hermes source/runtime, llama.cpp source/build, LM Studio/model/cache, viewer models, optional pose weight, Android media/APK and optional Discord provider are external. See [developer setup](../operations/developer_setup.md). |
| 10 | What tools must be installed? | PARTIAL | The designated container must provide Python, uv, Git, Bash and Mosquitto; Docker/image availability is host-owned. Installation source for the container and several host tools is a maintainer dependency, documented as an environment pin gap. |
| 11 | Which versions matter? | PARTIAL | Python <code>>=3.12</code> and lockfiles are source-backed. Observed tool versions are recorded as snapshots; uv, Git, Bash, Mosquitto, container image, LM Studio and CUDA/driver versions are not pinned and are explicit <code>ENVIRONMENT_PIN_GAP</code>s. |
| 12 | How is the Python environment created? | ANSWERED | Run <code>uv sync --frozen</code> in each project, with <code>--extra mqtt</code> for <code>hermes_temi_bridge</code>; lockfiles must not be updated during setup. |
| 13 | Where do private configs go? | ANSWERED | The canonical ignored config is <code>/TemiAgent/.runtime/demo/demo.env</code>; custom configs are absolute owner-only files outside Git worktrees. |
| 14 | Where do secrets go? | ANSWERED | Credentials belong only in owner-only private env files, especially the separately referenced Discord env file; mode <code>0600</code>, owner-only parent, never tracked or printed. |
| 15 | What must never be committed? | ANSWERED | Real credentials, webhook URLs, private LAN addresses, user paths, real care records, images, logs, runtime state, model caches/weights, recordings, checkpoints and generated source checkouts. |
| 16 | Where do models go? | ANSWERED | LM Studio cache and viewer GGUF/mmproj are external under configured private locations; model identifiers are tracked, model bytes are not. Optional pose weights require provenance approval. |
| 17 | Which services exist? | ANSWERED | Production LM Studio is an external dependency; managed AI6 services include MQTT, overview adapter, resident Hermes, Bridge, optional gateway and viewer. The newcomer mock additionally manages local Android/Discord/model/resident/viewer doubles. |
| 18 | Which machine runs each service? | ANSWERED | The AI6 container runs the software stack; the AI6 host provides Docker/mount; Temi Android runs outside AI6; LAB606 is a development/control host; external providers own their services. See [deployment handover](../operations/demo_deployment_handover.md). |
| 19 | How do I check service status? | ANSWERED | Use read-only <code>./scripts/demo --json doctor</code>, <code>./scripts/demo --json status</code>, or the MQTT-only <code>./scripts/demo --json mqtt status</code> where its canonical production config applies. |
| 20 | How do I start services? | ANSWERED | Only an authorized operator may run <code>./scripts/demo start</code>; production LM readiness must already pass as an external precondition and the lifecycle starts no real LM provider. The exact contract is in [DEMO_OPERATOR_GUIDE](../operations/DEMO_OPERATOR_GUIDE.md). MQTT-only has its separate <code>mqtt start</code> selector. |
| 21 | How do I safely stop services? | ANSWERED | Use <code>./scripts/demo stop</code> or the exact MQTT-only <code>mqtt stop</code>; the lifecycle signals only recorded verified identities, refuses foreign/unowned processes, and never stops production LM Studio. |
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
| 32 | Which tests require hardware? | PARTIAL | LAB606 closed Android artifact provenance for the installed 1.0.2 (3) APK, but real Android/Temi session, playback, camera, microphone, device result and physical observation remain separate device-owner tests. |
| 33 | What is currently verified? | ANSWERED | Gate 3 recorded clean-clone Hermes/llama reproducibility, licenses, source manifests and the hardware-free matrix; Gate 5 closes the bounded host runtime contract and L4.3 closes final Android artifact provenance. Temi physical execution, viewer/GPU general readiness, Discord, real perception and complete L4 E2E remain separate or unverified. |
| 34 | What remains experimental? | ANSWERED | Optional anomaly viewer, pose preprocessing, local model/viewer deployment and feature-gated media/identity/care Demo paths remain bounded or external; see [CURRENT_STATUS](../CURRENT_STATUS.md). |
| 35 | What is legacy? | ANSWERED | Dated first-year, streaming, direct-service and broad historical runbooks are retained as evidence and marked <code>LEGACY</code>; current lifecycle authority remains <code>scripts/demo</code>. |
| 36 | Which docs are current authority? | ANSWERED | Use this authority map, [README](../../README.md), [CURRENT_STATUS](../CURRENT_STATUS.md), [REPOSITORY_MAP](../REPOSITORY_MAP.md), [developer setup](../operations/developer_setup.md), [operator guide](../operations/DEMO_OPERATOR_GUIDE.md), deployment, configuration, testing and troubleshooting. |
| 37 | How do I update dependencies? | ANSWERED | Change the owning project declaration and lockfile together, run affected tests and docs/security checks, update authority/status documentation, and obtain maintainer review. |
| 38 | How do I make a release? | ANSWERED | Prepare an isolated candidate from the exact publication ref, run the required validation, make one bounded documentation/evidence commit, and use an old-value-guarded local fast-forward; any root push remains separately authorized. Gate 5 final evidence adoption demonstrates this procedure. |
| 39 | How do I prove a fresh clone is healthy? | ANSWERED | Follow all ten [developer setup](../operations/developer_setup.md) steps, verify submodule/final trees and licenses, run the focused/full hardware-free matrix, then use read-only doctor/status. |
| 40 | What should I check before a Demo? | ANSWERED | Confirm branch/config/runtime ownership, <code>doctor</code>, status, exact ports/PIDs, external LM Studio model/API/GPU readiness if production, the adopted Android artifact provenance, and fresh Temi physical evidence before claiming <code>DEMO_READY</code>. Do not use the LM CLI as an audit. |

Handover result: <code>ANSWERED=36</code>,
<code>PARTIAL=4</code>, <code>MISSING=0</code>. Each partial answer has an
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
- <code>GATE5_OBSERVED_FACT</code>: Read-only <code>git remote -v</code> still returns no root remote. The local <code>release/github-v1</code> publication ref and the Gate 5 evidence baseline are local Git facts, not a public clone URL.
- <code>MISSING_FACT</code>: The maintainer-designated public repository URL and any access requirement.
- <code>OWNER</code>: Publication maintainer / repository owner.
- <code>FUTURE_GATE</code>: Final GitHub publication gate.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Request the maintainer URL, substitute it only for <code>TEMIAGENT_REPO_URL</code>, and never use a local checkout, file URL or Git alternate as the publication source.

### #10 — What tools must be installed?

- <code>QUESTION_NUMBER</code>: 10
- <code>QUESTION</code>: What tools must be installed?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: The repository requires a designated container and host Docker support but does not own their provisioning.
- <code>GATE5_OBSERVED_FACT</code>: The accepted host had the designated container and required runtime toolchain available for the bounded Gate 5 checks; the observed image/tool versions and absent optional tools remain deployment observations, not installation requirements or pins.
- <code>MISSING_FACT</code>: The approved container image, Docker host provisioning and installation source for the required container tools.
- <code>OWNER</code>: AI6 container/infrastructure maintainer.
- <code>FUTURE_GATE</code>: Gate 5 runtime/environment acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Use the designated container and record <code>python3 --version</code>, <code>uv --version</code>, <code>git --version</code>, <code>bash --version</code> and <code>mosquitto -h</code>; do not add an ad-hoc host or image recipe.

### #11 — Which versions matter?

- <code>QUESTION_NUMBER</code>: 11
- <code>QUESTION</code>: Which versions matter?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: Python floors and lockfiles are source-backed, but several host, container and provider versions remain unpinned.
- <code>GATE5_OBSERVED_FACT</code>: The accepted host evidence records the designated toolchain and external LM/model context, but observed Python/uv/Git/Bash/Mosquitto/CUDA/driver/provider versions remain deployment observations. None of these observations closes the environment-pin gap.
- <code>MISSING_FACT</code>: Approved versions or digests for uv, Git, Bash, Mosquitto, the container image, LM Studio and CUDA/driver software.
- <code>OWNER</code>: AI6 environment maintainer.
- <code>FUTURE_GATE</code>: Gate 5 runtime/environment acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Use the checked-in lockfiles and record observed tool versions as evidence; do not invent minimums or update lockfiles to hide an environment gap.

### #32 — Which tests require hardware?

- <code>QUESTION_NUMBER</code>: 32
- <code>QUESTION</code>: Which tests require hardware?
- <code>STATUS</code>: PARTIAL
- <code>WHY_PARTIAL</code>: Real Android/Temi sessions, physical playback, camera, microphone and device results cannot be verified by this repository alone.
- <code>GATE5_OBSERVED_FACT</code>: Gate 5 accepted one bounded host L5 model request and L0–L3 software path. L4.3 now accepts the final Android 1.0.2 (3) artifact provenance and exact installed-APK match, but no Android/Temi device action, camera/microphone session or physical playback was performed or accepted. General viewer/GPU and hardware behavior remain outside this evidence.
- <code>MISSING_FACT</code>: A fresh Android/Temi session with physical playback, device observation and the corresponding command/result evidence.
- <code>OWNER</code>: Temi Android/device integration owner.
- <code>FUTURE_GATE</code>: L4 Temi physical/E2E acceptance.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Run the hardware-free Bridge, backend, anomaly, tools and mock/fake checks, then request a separately authorized device acceptance record; do not label software evidence as live hardware evidence.

## Resolved handover records

### #38 — How do I make a release?

- <code>QUESTION_NUMBER</code>: 38
- <code>QUESTION</code>: How do I make a release?
- <code>STATUS</code>: RESOLVED for local evidence-ref adoption
- <code>RESOLUTION</code>: Gate 5 created an isolated candidate from the exact publication baseline, ran the required documentation/security/authority review, made one bounded documentation/evidence commit, and fast-forwarded <code>release/github-v1</code> with an old-value guard. Root publication push remains a separate maintainer action.
- <code>GATE5_OBSERVED_FACT</code>: The accepted local release procedure is now evidenced by this Gate 5 adoption. The root checkout still has no configured remote, and no push was performed.
- <code>OWNER</code>: Release maintainer / repository owner.
- <code>FUTURE_ACTION</code>: A maintainer may select/configure the public root remote and perform a separately authorized push; that action is not part of this local adoption.
- <code>WHAT_STUDENT_CAN_DO_NOW</code>: Reuse the isolated-candidate, validation and old-value-guard procedure; do not rewrite history, merge, rebase or push.

## Release handover

The historical Gate 4.1 repair candidate and Gate 5A/5A.1 candidates remain
dated evidence. The current release procedure is to create an isolated
candidate from the exact publication ref, validate only the allowed
documentation/evidence delta, obtain maintainer review, and use an atomic
old-value-guarded fast-forward for local <code>release/github-v1</code>.
No merge, rebase, squash, rewrite or push is part of that local adoption.

Gate 5 final evidence adoption completed that local procedure from
<code>release/github-v1@59d568b079ce260e2144c410b0f9397d8b026913</code>.
The exact evidence commit is reported in the task handoff; the candidate ended
clean and the canonical <code>main</code> checkout remained unchanged. The
root publication URL and any push target remain maintainer-owned external
facts.

## Gate 5A.1 review handover (historical candidate)

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

No public root remote, approved environment/provider pins or physical Android/
Temi acceptance was invented by this handover. LAB606 Android artifact
provenance is now adopted as <code>CLOSED_PASS</code>; the bounded Gate 5 host
runtime is accepted, complete L4 physical/E2E remains separate, and Gate 6 is
not started.
