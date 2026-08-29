# Developer Setup and Environment Contract

Status: <code>CURRENT_AUTHORITY</code>; last reviewed for Gate 5 final evidence:
2026-08-29.

This is the one current clean-clone setup path for a new TemiAgent maintainer.
It prepares source, locked Python environments, private configuration and
hardware-free evidence. It does not start a service, publish MQTT, operate
Android, or claim that a real Temi, GPU model or Discord recipient is ready.
The [Demo operator guide](DEMO_OPERATOR_GUIDE.md) is the authority for any
later, separately authorized service operation.

The repository has no configured root publication URL in the audited local
snapshot. <code>TEMIAGENT_REPO_URL</code> below is therefore a required
maintainer input; it is deliberately not replaced with a guessed URL.

## Execution boundary and state labels

Run project commands inside the designated container. Generic fresh-clone steps
use <code>REPO_ROOT</code> for the user-selected clone root. The canonical AI6
deployment uses <code>REPO_ROOT=/TemiAgent</code>; that deployment-specific
value is not required by the generic setup below.

~~~bash
docker exec -it yiting.TemiAgent_gpu_all bash
# Set REPO_ROOT to the root of the fresh clone before running repository commands.
~~~

The host owns Docker/container availability and the mount. The container owns
project reads, source reconstruction, dependency environments, tests and
runtime commands. The observed container versions are evidence snapshots,
not project pins:

| Tool | Observed snapshot | Repository contract |
|---|---:|---|
| Python | 3.12.3 | Python <code>>=3.12</code> in all three Python projects. |
| uv | 0.10.12 | Required for the locked project environments; version is not pinned. |
| Git | 2.43.0 | Required for the root repository, Hermes submodule and source manifests; version is not pinned. |
| Bash | 5.2.21 | Required by the tracked shell scripts; minimum version is not declared. |
| Mosquitto | 2.0.18 | Required for the managed MQTT runtime; package/image version is not pinned. |
| Node/npm | 18.19.1 / 9.2.0 | Not required by the current <code>scripts/demo</code> lifecycle. |
| Docker CLI | host-owned | Required on the host to provide the designated container; no image digest is pinned. |

<code>VERIFIED_CURRENT</code> means the claim is grounded in tracked source,
manifests or tests. <code>VERIFIED_EXTERNAL</code> means the item is
intentionally supplied outside the root repository. <code>LIVE_NOT_VERIFIED</code>
means no current live claim is made for that boundary.
<code>HOST_LIVE_VERIFIED</code> means the exact bounded Gate 5 host contract
passed without proving physical Android/Temi execution or portable environment
reproducibility.
<code>ENVIRONMENT_PIN_GAP</code> means the repository does not currently pin an
important environment dependency. <code>HANDOVER_RUNTIME_GAP</code> means a
truthful operator prerequisite is not yet supplied by a portable repository
command.

## Gate 5 final handoff boundary

Gate 5B Retry #4 closed the bounded host-runtime acceptance. The accepted
deployment uses external-only production LM Studio with API identifier
<code>google/gemma-4-31b</code>, provisioned model
<code>temi/gemma-4-31b-it-qat</code>, and runtime context
<code>64000</code> verified from provider metadata. It reuses MQTT without
restart and reconstructs Hermes base plus patches <code>0001</code>–<code>0010</code>
to tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>.

This is <code>HOST_LIVE_VERIFIED</code> for the exact host contract only. The
accepted request budget is <code>L1=0; L2=0; L3=0; L5=1</code>. The exact
canonical Android/Temi TTS physical boundary is separately
<code>L4_FINAL=CLOSED_PASS</code> from adopted L4.7B evidence; broader
Android/media acceptance remains separate, and Gate 6 is ready for
release/handover work only.
PIDs, run IDs, temporary worktrees and runtime roots from the acceptance are
transient evidence, not clean-clone requirements. This documentation gate
does not rerun live acceptance or operate any service.

## Ordered clean-clone path

Use these steps in order. The commands are safe for a new clone; they do not
delete an existing directory or overwrite a private configuration. Replace the
two angle-bracket values before running the relevant command.

### 1. Clone the repository

The root repository URL must be supplied by the maintainer who owns the
publication target:

~~~bash
export TEMIAGENT_REPO_URL='<maintainer-provided-root-repository-url>'
export TEMIAGENT_CLONE_PARENT='<user-selected-clone-parent>'
export REPO_ROOT="$TEMIAGENT_CLONE_PARENT/TemiAgent"
mkdir -p "$TEMIAGENT_CLONE_PARENT"
git clone "$TEMIAGENT_REPO_URL" "$REPO_ROOT"
cd "$REPO_ROOT"
~~~

Do not use a local checkout URL or Git alternate as a
substitute for the publication URL. The clone should be a clean root checkout
before setup.

### 2. Initialize formal submodules

Hermes is a formal submodule because its pinned base and the root-owned overlay
are separate, reviewable dependency inputs. Initialize it from the team remote
with the bounded wrapper:

~~~bash
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
git submodule status --recursive
~~~

The expected root gitlink is <code>hermes-agent</code> at base commit
<code>a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2</code>. The team URL, base/final
tree identities, ordered patch hashes and MIT license contract are maintained in
[third_party/hermes/README.md](../../third_party/hermes/README.md) and its
manifest. A submodule fetch failure is a real setup failure; do not fall back
to the original upstream or a local source tree.

### 3. Install or verify prerequisite tooling

The supported install unit is the designated container. Its image, Docker
engine, CUDA driver and host mount are externally provisioned and are not
currently pinned by this repository. Verify the tools before changing the
checkout:

~~~bash
python3 --version
uv --version
git --version
bash --version
mosquitto -h
~~~

If the designated container is unavailable, stop and obtain the maintainer's
approved container/image instructions. Do not add an ad-hoc package manager
recipe to the repository: the missing image digest, Docker version, Mosquitto
package version, CUDA/driver version and LM Studio version are
<code>ENVIRONMENT_PIN_GAP</code>s.

### 4. Reconstruct external sources and locked Python environments

The source bootstrap is intentionally separate from dependency installation.
It never starts a service and never downloads a model:

~~~bash
./scripts/bootstrap --sources
(cd hermes_temi_bridge && uv sync --frozen --extra mqtt)
(cd temi_backend && uv sync --frozen)
(cd anomaly_detection && uv sync --frozen)
~~~

<code>--sources</code> verifies the formal Hermes submodule, applies patches
<code>0001</code>–<code>0010</code> in the submodule worktree, and reconstructs
the ignored llama.cpp checkout from its manifest. The expected llama.cpp commit
is <code>0b7154066e8544ed88d92ae2132cc1e055cf6304</code> and the expected tree
is <code>1020a771795f406b8891d18ee607b4da3783fa7f</code>. The
<code>uv sync --frozen</code> commands use the checked-in lockfiles; they do
not update dependency declarations or lockfiles.

The Python dependency floors and lockfiles are:

| Project | Declared Python floor | Locked environment | Purpose |
|---|---:|---|---|
| <code>hermes_temi_bridge/</code> | <code>>=3.12</code> | <code>hermes_temi_bridge/uv.lock</code> | Bridge, MQTT client and contract tests; use the <code>mqtt</code> extra. |
| <code>temi_backend/</code> | <code>>=3.12</code> | <code>temi_backend/uv.lock</code> | Legacy ASR/video/local-VLM compatibility route and tests. |
| <code>anomaly_detection/</code> | <code>>=3.12</code> | <code>anomaly_detection/uv.lock</code> | Optional perception viewer and fake/test utilities. |

The external Hermes runtime environment and LM Studio CLI are not created by
the root <code>uv</code> commands. Their provisioning is described in the
external dependency and deployment contracts below.

### 5. Create private/local configuration

Create the safe local newcomer profile:

~~~bash
./scripts/demo init-config
stat -c '%a %U %n' "$REPO_ROOT/.runtime/demo/demo.env"
~~~

This creates the ignored owner-only
<code>$REPO_ROOT/.runtime/demo/demo.env</code> with mode <code>0600</code> and
the private runtime root with owner-only directories. The default profile is
<code>newcomer_mock</code>; its LM Studio, MQTT, resident, Android and Discord
components are local test doubles and use isolated high ports. It does not
contact a real robot, GPU model or Discord endpoint.

Production is a separate, explicit configuration choice and requires the
operator to supply the external LM Studio/model/GPU prerequisites:

~~~bash
./scripts/demo init-config --profile production --force
~~~

Run the production initializer only against a fresh or explicitly disposable
private runtime root. The <code>--force</code> option replaces that private
config; it does not belong in a routine status check.

For the complete key inventory, ownership rules and secret procedure, use
[demo_configuration_reference.md](demo_configuration_reference.md). Never
put a real endpoint, credential, private path or private LAN address in a
tracked template.

### 6. Provision external models and artifacts

The repository records identity and location contracts, not unrestricted model
downloads. <code>--sources</code> already reconstructs llama.cpp; this
idempotent command may be used when only that source is needed:

~~~bash
./scripts/bootstrap --llama-cpp
~~~

Provision the following through the owner-approved external systems:

| Artifact | Required for | Provisioning truth | Ready evidence |
|---|---|---|---|
| Hermes <code>venv/bin/python3</code> and <code>venv/bin/hermes</code> | Production resident/gateway | Team-owned Hermes runtime environment; no root installer or version pin exists. | Executables exist and <code>./scripts/bootstrap --check</code> passes the Hermes checks. |
| LM Studio and <code>temi/gemma-4-31b-it-qat</code> | Production LM route | External LM Studio installation, model/cache and GPU owner; no portable download recipe or version pin is tracked. The lifecycle does not invoke <code>lms</code>. | Exactly one configured listener, <code>/v1/models</code>, identifier <code>google/gemma-4-31b</code>, and runtime metadata context <code>64000</code> with the external context/GPU policy pass. |
| llama.cpp <code>llama-server</code> build | Production action viewer | Build the generated pinned checkout using the approved environment; build flags are not pinned by the root manifest. | Configured executable exists and viewer health reports <code>llama_server_ready</code>. |
| Viewer GGUF/mmproj | Production action viewer | External model/cache provision; source and redistribution authority are external. | Configured regular files exist and viewer health passes. |
| <code>yolo26x-pose.pt</code> | Optional pose preprocessing | Optional external weight; the resource manifest records size/hash observations only. Source, version, license and redistribution restrictions remain maintainer inputs. | Maintainer-approved provenance plus configured file; otherwise keep the optional viewer path disabled. |
| <code>elderly_hand_exercise</code> | Real Android media playback | Android owner deploys the allowlisted logical asset. AI6 has no APK asset mapping. | Fake Android media tests pass; real playback still needs Android evidence. |

Do not treat a clean clone as containing models, caches, recordings, checkpoints,
runtime images, Android assets or private care data.

### 7. Validate the environment

Run the source/dependency readiness check only after the preceding provisioning:

~~~bash
./scripts/bootstrap --check
./scripts/demo --config "$REPO_ROOT/.runtime/demo/demo.env" --json doctor
git submodule status --recursive
~~~

<code>./scripts/bootstrap --check</code> is a production-oriented readiness
gate. It checks the Hermes environment, anomaly <code>.venv</code>, generated
llama-server, Mosquitto, the tracked broker config and resource/config manifests.
It deliberately does not require or invoke an LM Studio CLI: production LM
Studio is externally managed and its API/listener readiness is checked by the
selected Demo lifecycle profile. A missing provisioned environment or generated
binary remains a readiness failure; it must not be hidden by changing the
documentation or by claiming that a mock profile is production-ready.

<code>doctor</code> is read-only. Before any authorized service operation it
should report the private configuration, source, entrypoints, artifact, port and
ownership evidence required by the selected profile.

### 8. Run hardware-free tests

Run the narrow checks first, then the complete available matrix when the
environments are present:

~~~bash
python3 -m unittest tools.tests.test_validate_documentation
python3 -m unittest \
  tools.tests.test_external_dependency_publication \
  tools.tests.test_hermes_submodule \
  tools.tests.test_hermes_license
(cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests)
(cd temi_backend && uv run --locked --offline pytest)
(cd anomaly_detection && uv run --locked --offline python -m unittest discover -s tests)
python3 -m unittest discover -s tools/tests
python3 tools/e2e_test_runner.py
python3 tools/media_v11_fake_e2e.py
~~~

These checks may create bounded temporary test data or subprocesses owned by
the test, but they do not establish a live Temi, Android, LM Studio, GPU,
Discord or real perception claim. Do not start the full Demo stack merely to
validate documentation.

### 9. Determine whether the runtime is ready

Use read-only evidence; do not infer readiness from a listening port alone:

~~~bash
./scripts/demo --config "$REPO_ROOT/.runtime/demo/demo.env" --json doctor
./scripts/demo --config "$REPO_ROOT/.runtime/demo/demo.env" --json status
~~~

Before an authorized start, a newly initialized profile is normally not ready.
For production, <code>status</code> must agree with exact ownership, configured
ports, health endpoints, runtime state and external Android evidence. A backend
that is healthy without a fresh Android MQTT session is
<code>BACKEND_READY_WAITING_ANDROID</code>, not <code>DEMO_READY</code>.
MQTT-only readiness requires exactly one expected listener, a successful TCP
probe and a valid recorded supervisor/child contract; see the
[operator guide](DEMO_OPERATOR_GUIDE.md).

### 10. Continue to deployment

Read these entry points in order:

1. [CURRENT_STATUS.md](../CURRENT_STATUS.md) for verified, external,
   experimental and unverified capability state.
2. [demo_deployment_handover.md](demo_deployment_handover.md) for the
   host/container/Temi responsibility map and service ownership.
3. [DEMO_OPERATOR_GUIDE.md](DEMO_OPERATOR_GUIDE.md) for the exact lifecycle
   grammar and safe process semantics.
4. [demo_troubleshooting.md](demo_troubleshooting.md) for symptom-driven
   evidence and escalation.
5. [verification_and_acceptance.md](verification_and_acceptance.md) for
   hardware, Android, GPU and external-provider gates.

Starting, stopping, restarting, publishing MQTT, operating Android, enabling
real Discord delivery and running GPU inference require a separate authorized
operation. This setup document does not authorize them.

## Environment matrix

The following matrix is the authoritative minimum contract. A blank minimum
means that the repository has a functional dependency but does not declare a
portable version floor; that is an <code>ENVIRONMENT_PIN_GAP</code>, not an
invitation to invent one.

| Component | Purpose | Required / optional | Minimum or pinned version | Install/provision source | Validation command | Notes |
|---|---|---|---|---|---|---|
| Linux host | Docker host and approved mount | Required | Not pinned: <code>ENVIRONMENT_PIN_GAP</code> | Maintainer/container platform | <code>docker exec -it yiting.TemiAgent_gpu_all bash</code> | Host-side platform owns Docker; project commands remain in the container. |
| <code>yiting.TemiAgent_gpu_all</code> | Designated isolated execution environment | Required | Image tag/digest not pinned: <code>ENVIRONMENT_PIN_GAP</code> | Maintainer-provided container | <code>docker inspect yiting.TemiAgent_gpu_all</code> on host | Do not substitute another container for official evidence. |
| Python | Root tools and project runtimes | Required | <code>>=3.12</code> | Container image plus <code>uv</code> | <code>python3 --version</code> | Three <code>pyproject.toml</code> files declare the floor; no patch-level pin. |
| uv | Locked Python environment manager | Required | 0.10.12 observed; not pinned | Approved container/tooling | <code>uv --version</code> | Use <code>uv sync --frozen</code>; do not update locks during setup. |
| Git | Root/submodule/source reconstruction | Required | 2.43.0 observed; not pinned | Approved container/tooling | <code>git --version</code> | Hermes source acquisition is through the formal submodule only. |
| Bash | Tracked bootstrap/lifecycle scripts | Required | 5.2.21 observed; minimum not declared | Approved container/tooling | <code>bash --version</code> | Scripts require modern Bash features such as <code>mapfile</code>. |
| Mosquitto and client tools | Managed local MQTT broker | Required for MQTT/full runtime | 2.0.18 observed; package/image not pinned | Container package or approved image | <code>mosquitto -h</code> | Tracked <code>mqtt/mosquitto.conf</code> is local Demo configuration; listener exposure is deployment-controlled. |
| Python lockfiles | Bridge/backend/anomaly dependencies | Required for corresponding suites | Lockfile pins are authoritative | <code>uv sync --frozen</code> in each project | Commands in step 8 | Project dependency floors are not substitutes for the lockfiles. |
| Formal Hermes submodule | Resident/gateway source base | Required for production and Hermes tests | Base commit and final tree pinned in manifest | <code>git submodule update</code> then <code>./scripts/bootstrap --hermes</code> | <code>./scripts/bootstrap --check</code> | External team remote plus root-owned patches; no fallback. |
| Hermes virtual environment | Resident/gateway execution | Required for production | Version not pinned: <code>ENVIRONMENT_PIN_GAP</code> | Maintainer-approved Hermes setup | <code>test -x hermes-agent/venv/bin/hermes</code> | Root bootstrap verifies presence but does not install it. |
| LM Studio API | Production external model service | Required for production; not needed by fake E2E | Version not pinned: <code>ENVIRONMENT_PIN_GAP</code> | External owner provisions the installed application and model cache | External owner’s API readiness; AI6 checks one listener and <code>/v1/models</code> and never invokes the CLI | Model/cache/license are external; no model is published or lifecycle-owned. |
| CUDA driver/GPU | Production LM Studio and optional viewer | Required for production model/viewer paths | GPU/driver/CUDA not pinned: <code>ENVIRONMENT_PIN_GAP</code> | Host/maintainer provisioning | Lifecycle GPU policy check | Production policy names visible devices <code>0,1</code>; viewer config names device <code>3</code>; Gate 5 accepted one bounded L5 request, not general viewer/GPU readiness. |
| llama.cpp | Optional action viewer server | Optional feature, but current bootstrap check expects its binary | Commit <code>0b715406...</code>; tree <code>1020a771...</code> | <code>./scripts/bootstrap --llama-cpp</code>, then approved build | <code>test -x anomaly_detection/third_party/llama.cpp/build/bin/llama-server</code> | Generated ignored checkout; build toolchain/flags are not pinned. |
| Android/Temi dependencies | Device-side executor and asset mapping | External acceptance gate | AI6 does not own Android version pins | Android repository/device owner | Android owner’s tests and fresh runtime snapshot | AI6 defines only the cross-system MQTT/schema boundary. |
| Node/npm | Other repository tooling | Not required by current lifecycle | Observed only | Not installed for this contract | None | Do not add it to a new-student prerequisite list without a source-backed feature. |

## External artifact and provenance contract

| Artifact or state | Tracked? | External/provision method | Expected location | Required? | Hash/version authority | License/provenance status |
|---|---|---|---|---|---|---|
| Hermes base plus overlay | Gitlink, manifest, patches and README | Formal team submodule, then root patch bootstrap | <code>hermes-agent/</code> | Production resident/gateway | Pinned base <code>a0fedfbb...</code>; final tree <code>47e9f141...</code>; ten patch SHA-256 values | MIT license is verified by the manifest/verifier. |
| llama.cpp source | Manifest and README only | Public pinned source bootstrap | <code>anomaly_detection/third_party/llama.cpp/</code> | Viewer path only | Commit <code>0b715406...</code>; tree <code>1020a771...</code>; MIT license hash in manifest | Generated checkout is ignored; no model binary is implied. |
| LM Studio model/cache | No | External LM Studio provisioning | <code>.lmstudio-data/</code> | Production LM route | Model ID <code>temi/gemma-4-31b-it-qat</code>, API identifier <code>google/gemma-4-31b</code>; no weight hash | Provider/cache license and model redistribution are external. |
| Viewer GGUF and mmproj | No | External approved model/cache provisioning | Path values in private Demo env | Viewer only | No root hash/version authority | Provenance and redistribution terms require maintainer confirmation. |
| <code>yolo26x-pose.pt</code> | No; only manifest observation | External approved artifact if optional viewer needs it | <code>anomaly_detection/yolo26x-pose.pt</code> | Optional | Manifest records size <code>126242553</code> and SHA-256; source/version unresolved | Do not publish or redistribute until source, version, license and restrictions are confirmed. |
| <code>elderly_hand_exercise</code> | No AI6 binary | Android owner deploys logical allowlisted media | Android app/device | Real media only | Logical ID in resource/schema contracts; no AI6 hash | Fake Android route is verified; real asset mapping/playback is external. |
| Datasets, recordings and real images | No | Owner-approved local/external storage | Outside source tree/runtime publication | Optional/feature-specific | No publication hash | Consent, de-identification, retention and access are external; never commit real care data. |
| Logs, PID/state, caches, checkpoints | No | Lifecycle/runtime or external provider | Owner-only <code>.runtime/</code>, <code>.lmstudio-data/</code> or external cache | Runtime only | Runtime IDs/digests are evidence, not source | Keep bounded/redacted; never publish credentials or payload-bearing artifacts. |

Gate 3 evidence carried into this contract proves that the pose path and pose
blob are unreachable from the publication candidate, and that the root
publication history contains no blob at or above 50 MiB. The same checks must
be rerun when a candidate changes source history or artifact policy.

## Dependency update contract

1. Change the owning <code>pyproject.toml</code> and lockfile together using the
   repository's <code>uv</code> workflow.
2. Re-run the affected module tests, tools tests and documentation validation.
3. Re-run external source, license and clean-clone checks if a manifest,
   submodule, bootstrap script or external artifact contract changes.
4. Update the relevant module README, authority map and current status.
5. Have a maintainer review the candidate before adopting a publication ref.

Do not casually switch Hermes remotes, regenerate a submodule commit, replace a
manifest pin, update a Docker image tag or add a model download shortcut.
Those are contract changes requiring provenance, license, reproducibility and
security review.
