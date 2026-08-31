# AI6 TemiAgent Student Handover

Status: CURRENT_AUTHORITY; D2B consolidated on 2026-08-31.

This is the newcomer handover for the public TemiAgent publication. Runtime
schemas, executable validators, module READMEs and [AGENTS.md](../../AGENTS.md)
remain authoritative when prose differs. The one current operator procedure is
[DEMO_OPERATOR_GUIDE.md](../operations/DEMO_OPERATOR_GUIDE.md).

## The first rule

Do not use the dirty canonical development worktree as an operator workspace
and do not commit unknown dirty files to make a readiness check pass.

The portable source is a clean clone of public <code>main</code>:

| Field | Current authority |
|---|---|
| Public repository | <code>https://github.com/YI-TING-EE13/TemiAgent</code> |
| Public branch | <code>main</code> |
| Public HEAD | <code>8fead49d66ab0a9d016a7dfe495b336146bbe957</code> |
| Public tree | <code>e5fa932b01cc1f885cd36023464a18f11bdf060a</code> |
| Root license | <code>NO_LICENSE</code>; no root <code>LICENSE</code> file is present |
| Protected canonical development worktree | Host path withheld from publication docs; designated-container <code>/TemiAgent</code>, HEAD <code>12aff3bfdfe526c17a25a2681aea2afad7112b33</code>, intentionally dirty |
| Validated AI6 operator workspace | <code>/opt/TemiAgent-operator</code> |
| Validated AI6 private runtime root | <code>/opt/TemiAgent-operator/.runtime/demo</code> |

The <code>/opt/TemiAgent-operator</code> row is
<code>VALIDATED_AI6_OPERATOR_WORKSPACE</code> evidence from D2A. It is not a
universal portable path. A new student creates a clean public-main clone and
supplies a private runtime root for that clone. Never edit, commit, stash,
reset, clean, merge, rebase or checkout over the protected canonical worktree.

## Current gate disposition

<code>D2A_STATUS=CLOSED_PASS</code>. D2A validated one bounded operator
lifecycle in the AI6 workspace and preserved LM Studio and MQTT.
<code>Gate 5=CLOSED_PASS</code>, <code>ANDROID_PROVENANCE=CLOSED_PASS</code>,
<code>L4_FINAL=CLOSED_PASS</code>, and <code>Gate 6=CLOSED_PASS</code> at their
stated boundaries. Gate closure does not imply that a clean clone contains
external dependencies, model bytes, an Android device, or a push to the public
repository.

The accepted Android boundary is one canonical TTS transaction. General
camera, microphone, media playback, viewer/GPU, Discord, perception and other
physical actions remain separate or unverified. The installed Android artifact
is package <code>com.robotemi.agent</code>, version <code>1.0.2 (3)</code>,
SHA-256
<code>c0f54cd46930c05caf2f556a2e4e1e26570b8401c0034546b57c6faca27c043</code>.
The observed launcher is <code>16405-usa / 16405</code>, below the documented
minimum <code>18024</code>; this is a deployment limitation, not a proven
direct cause of the historical TTS timeout.

## Newcomer path

Read and follow these documents in order:

1. [README](../../README.md) for scope and safety boundaries.
2. [CURRENT_STATUS](../CURRENT_STATUS.md) for evidence and limitations.
3. [REPOSITORY_MAP](../REPOSITORY_MAP.md) for source, generated and runtime boundaries.
4. [Developer setup](../operations/developer_setup.md) for clean-clone provisioning.
5. [Configuration reference](../operations/demo_configuration_reference.md) for private keys and ownership.
6. [DEMO_OPERATOR_GUIDE](../operations/DEMO_OPERATOR_GUIDE.md) for the only current lifecycle.
7. [Verification and acceptance](../operations/verification_and_acceptance.md) for test claims.
8. [Troubleshooting](../operations/demo_troubleshooting.md) for read-only failure handling.

All project reads, setup, tests and later authorized operations occur in the
designated container:

~~~bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd <clean-clone-root>
pwd
git rev-parse --show-toplevel
git status --short
~~~

The container path is a command boundary, not a license to use the protected
<code>/TemiAgent</code> mount. A clean clone may use any owner-approved
<code>REPO_ROOT</code>.

## Seventeen newcomer questions

### 1. What is TemiAgent?

It is a safety-bounded Temi integration: legacy ASR/video compatibility,
canonical event adaptation, Hermes JSON-only reasoning, Bridge validation and
allowlisted command publication, optional perception, and an external Android
executor. It is not a medical device, emergency service, guaranteed fall
detector or autonomous care system.

### 2. Which repository and ref are authoritative?

The public repository and branch are the exact values in the table above. A
clean clone of public <code>main</code> is the portable publication and
operator source. The canonical local development mount is a protected,
intentionally dirty workspace; its files are not a student deployment
baseline.

### 3. How do I create the workspace?

Inside the designated container, clone the public branch into a new directory:

~~~bash
export TEMIAGENT_REPO_URL='https://github.com/YI-TING-EE13/TemiAgent.git'
export CLONE_PARENT='<owner-approved-parent>'
export REPO_ROOT="$CLONE_PARENT/TemiAgent"
git clone --branch main "$TEMIAGENT_REPO_URL" "$REPO_ROOT"
cd "$REPO_ROOT"
git status --short
~~~

Do not use a local checkout URL, Git alternates, an old release ref or the
canonical dirty mount as a substitute.

### 4. How is Hermes reconstructed?

Initialize the formal submodule from the team source
<code>https://github.com/YI-TING-EE13/hermes-agent.git</code>, whose pinned base
is <code>a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2</code> and base tree is
<code>bda69c575e65725bf9264dd1288a63093cea3cc3</code>. Then run
<code>./scripts/bootstrap --hermes</code> or
<code>./scripts/bootstrap --sources</code>. The root overlay applies patches
<code>0001</code> through <code>0010</code> and must produce final tree
<code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>.

The original <code>NousResearch/hermes-agent</code> repository is provenance
for the upstream project only. It is not the active TemiAgent source and is
never a fallback. Generated local Hermes commit IDs are not dependency
identity.

### 5. How are Python environments provisioned?

Use the checked-in locks without changing them:

~~~bash
(cd hermes_temi_bridge && uv sync --frozen --extra mqtt)
(cd temi_backend && uv sync --frozen)
(cd anomaly_detection && uv sync --frozen)
cd hermes-agent
uv sync --frozen
cd ..
~~~

The root source bootstrap reconstructs sources but does not install the Hermes
environment or build llama.cpp. Hermes source evidence declares Python
<code>>=3.11</code> and a <code>hermes</code> console script.
<code>hermes-agent/venv/bin/python3</code> and
<code>hermes-agent/venv/bin/hermes</code> must exist and be executable before a
production-oriented readiness check can pass. The required install/build
authority is the owner-approved container and the checked-in lockfiles; do not
invent a replacement environment.

### 6. What is required for the viewer?

The source dependency is llama.cpp commit
<code>0b7154066e8544ed88d92ae2132cc1e055cf6304</code>, tree
<code>1020a771795f406b8891d18ee607b4da3783fa7f</code>, reconstructed by
<code>./scripts/bootstrap --llama-cpp</code>. A separately approved build
creates the ignored <code>build/bin/llama-server</code>; source bootstrap alone
does not build it.

The observed AI6 build evidence is <code>Release</code>, <code>Ninja</code>,
<code>GGML_CUDA=ON</code> and
<code>CMAKE_CUDA_ARCHITECTURES=native</code>. Toolchain and build flags are
observed environment inputs, not portable pins. The D2A operator artifact was:

~~~text
/opt/TemiAgent-operator/anomaly_detection/third_party/llama.cpp/build/bin/llama-server
SHA-256: 6827638842194c9903da14662737b1e5c7d35effa6353506a329d31f85029585
~~~

The optional pose model was not provisioned. Do not claim pose availability.
Viewer embedded UI absence is non-blocking when the health contract otherwise
passes.

### 7. Where does private configuration live?

Use an absolute owner-only private config outside the source tree, or the
ignored runtime path created by the initializer for that clone. The file mode
must be <code>0600</code>; its parent/runtime directories must be owner-only,
normally <code>0700</code>. The configuration must point to runtime data below
its private runtime root and must not contain secrets in tracked templates.

For the validated AI6 deployment, the private runtime root was
<code>/opt/TemiAgent-operator/.runtime/demo</code>. The operator-specific
viewer setting was:

`DEMO_ACTION_VIEWER_LLAMA_SERVER=/opt/TemiAgent-operator/anomaly_detection/third_party/llama.cpp/build/bin/llama-server
`

Inspect path values and file modes without printing secret values. A private
config is not permission to use an executable or runtime artifact from
the protected canonical dirty worktree.

### 8. What does bootstrap check?

After submodule/source reconstruction and dependency provisioning, run:

~~~bash
./scripts/bootstrap --check
./scripts/demo --config <private-production-config> --json doctor
~~~

<code>bootstrap --check</code> verifies source pins, licenses, required
commands, the Hermes executables, the anomaly environment, the generated
llama-server and tracked resource/config files. It is a readiness gate, not a
deployment operation. If the Hermes venv, llama-server or another required
artifact is missing, stop with
<code>AI6_TEMIAGENT_D2A_DEPENDENCY_PROVISIONING_REQUIRED</code>. Report the
missing artifact, the provision method named by the publication documents,
expected location, source/lockfile impact, network/install/build need and
maintainer-authorization need. Do not use canonical dependencies, unknown old
environments, source edits or a mock profile to bypass the gate.

### 9. What does doctor mean?

<code>doctor</code> is read-only. A production pre-start result may return rc0
with <code>BACKEND_NOT_READY</code> and zero required failures; rc0 alone does
not mean <code>DEMO_READY</code>. Required failures must be zero, source and
dependency checks must pass, private config/ownership must be valid, and
external prerequisites must be ready before start is considered.

After start, accepted status values are <code>DEMO_READY</code> or
<code>BACKEND_READY_WAITING_ANDROID</code>. Do not operate Android or Temi to
manufacture <code>DEMO_READY</code>. After stop,
<code>BACKEND_NOT_READY / NO_OWNERSHIP</code> is expected when no managed
service remains.

### 10. What is the one current lifecycle?

Only an authorized operator may run exactly one bounded sequence using the
selected private config:

~~~bash
./scripts/demo --config <private-production-config> start
./scripts/demo --config <private-production-config> --json status
./scripts/demo --config <private-production-config> stop
~~~

Each command is a lifecycle operation, not a suggestion to retry.
<code>restart</code> and <code>mqtt start|stop</code> are compatibility or
service-specific selectors, not part of the current external-MQTT production
sequence. The lifecycle records exact process identity and stops only its own
verified records.

### 11. Who owns each service?

In the validated AI6 deployment, adapter, resident, Bridge, gateway, viewer and
their generated children were operator-managed and isolated under the operator
workspace. LM Studio and MQTT were external/reused dependencies. Android and
Temi were external. Ownership is selected by private config and must be
revalidated from process identity, cwd, executable and listener evidence; a
free port is not proof of readiness.

### 12. What is the LM Studio contract?

LM Studio is external-only in production. Verify the API at
<code>http://127.0.0.1:1234</code>, expected API identifier
<code>google/gemma-4-31b</code>, accepted local model identity
<code>temi/gemma-4-31b-it-qat</code>, and context <code>64000</code> from
runtime metadata. The lifecycle never starts, stops, restarts, loads, unloads,
reconfigures or invokes <code>lms</code>. Do not run <code>lms</code> commands
as an audit or recovery shortcut. Preserve the existing provider and escalate
ownership ambiguity.

### 13. What is the MQTT contract?

MQTT ownership is explicit. The validated AI6 deployment used a healthy
external/reused broker on port <code>1883</code>, without lifecycle mutation. A
managed broker may be started or stopped only under the exact managed lineage
contract and an authorized private config. Never adopt, stop or restart an
occupied external/unknown listener, and never use <code>pkill</code>,
<code>killall</code> or name-wide termination. Bridge remains the command
publication boundary.

### 14. How is runtime source isolation checked?

Every operator-managed process must have cwd, command line, executable and
artifact identity rooted in the selected operator workspace. The viewer llama
child must execute the configured operator binary and match the D2A observed
SHA when that validated deployment is being reproduced. No managed process may
fall back to <code>/TemiAgent/...</code> or the protected canonical dirty
worktree. External LM model cache paths are
allowed only as declared external inputs.

The following D2A invariants are evidence fields, not new runtime commands:
<code>ACTIVE_OPERATOR_CANONICAL_PATH_LEAK_COUNT=0</code>,
<code>CANONICAL_LLAMA_BINARY_USED=NO</code>, and all managed runtime artifacts
belonged to <code>/opt/TemiAgent-operator</code>.

### 15. What is safe to do when a check fails?

Preserve redacted JSON, exact PID/cwd/executable/parent/listener evidence and
private logs. Follow [safe service operations](../operations/safe_service_operations.md).
Use graceful termination only for the same verified identity under an explicit
authorization. Do not broaden a PID target, substitute a new PID, delete
runtime state, reset the Git tree, modify source, or retry past a stated
bounded authorization.

### 16. What Android/Temi claim is actually closed?

L4 provenance and the exact canonical TTS transaction are
<code>CLOSED_PASS</code>, based on the accepted external Android artifact and
one bounded real transaction. That evidence does not prove general media
playback, camera/microphone, continuous perception, Discord delivery,
navigation, movement or other physical actions. Android source, APK
installation and ADB are outside the normal software-only operator lifecycle.

### 17. What may be published or changed?

The root publication has <code>NO_LICENSE</code>; do not add a license claim.
Do not publish secrets, private LAN addresses, user paths, runtime data, model
caches, weights, recordings, checkpoints or real resident data. Cross-module
contract changes must update runtime authority, producers, consumers, tests,
module docs and reader-schema copies together. A documentation-only D2B change
may be reviewed in its isolated branch, but it does not push public
<code>main</code> or modify the canonical dirty worktree.

## Known limitations and escalation

- Hermes venv and llama-server are owner-provisioned generated artifacts; a
  clean clone does not contain them.
- LM Studio, model/cache/GPU, MQTT external ownership, Android and optional
  pose assets are outside the portable source contract.
- The canonical TTS route is accepted once; broader Android/media and viewer/GPU
  behavior remain separately bounded.
- <code>SECONDARY_TTS_DIAGNOSTIC_WARNING=NON_BLOCKING_KNOWN_ISSUE</code> is
  retained as a known state-machine diagnostic; it is not the historical
  timeout root cause.
- If a required dependency is absent, stop and report
  <code>AI6_TEMIAGENT_D2A_DEPENDENCY_PROVISIONING_REQUIRED</code>; do not
  improvise.

The current document inventory and retention rationale are in
[DOCUMENT_AUTHORITY_MAP.md](../DOCUMENT_AUTHORITY_MAP.md). Historical and
superseded runbooks remain available for evidence, but their top banner says
not to use them as current operator procedures.
