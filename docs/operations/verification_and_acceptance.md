# Verification and Acceptance Guide

Status: <code>CURRENT_AUTHORITY</code>. Last reviewed for Gate 4: 2026-08-27.

This guide distinguishes executable hardware-free verification from external
acceptance. Run every project command in the designated container from
`/TemiAgent`. None of the commands below intentionally starts a long-running
Demo service, sends MQTT/Discord messages, alters private configuration, or
uses a robot. Do not turn a skipped external gate into a PASS claim.

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

Run project commands inside the designated container. The Gate 4 documentation
change does not authorize live services, MQTT publication, Android control,
GPU inference or Discord delivery.

| Test | Purpose | Command | Hardware required? | Network required? | GPU required? | Expected baseline | Failure meaning |
|---|---|---|---|---|---|---|---|
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
| Shell syntax | Tracked shell parser validation. | <code>bash -n scripts/demo scripts/bootstrap scripts/bootstrap_hermes.sh scripts/bootstrap_llama_cpp.sh</code> | No | No | No | PASS for unchanged entrypoints. | Shell syntax regression. |
| Python compilation | Syntax-only check for changed Python tools. | <code>python3 -m py_compile tools/demo_lifecycle.py tools/validate_documentation.py</code> | No | No | No | PASS without importing services. | Python syntax regression. |
| Clean-clone source bootstrap | Formal submodule plus nine-patch and llama reconstruction, including idempotency. | <code>./scripts/bootstrap --sources</code> twice after bounded submodule initialization | No | Yes for source acquisition | No | PASS in two independent clean clones; Gate 3 evidence is carried forward. | Missing publication URL, team source, environment or manifest identity; do not fall back. |
| Full production readiness | External LM Studio, Hermes, generated binaries, ports and configured runtime. | <code>./scripts/bootstrap --check</code> and read-only <code>./scripts/demo --json doctor</code> | No for checks; external service may be required | Provisioning-dependent | Production model path may require GPU | PASS only when every required check is healthy. | A missing external prerequisite is not a documentation or hardware-free test failure. |

Hardware-free PASS means only that the named software path passed. Real
Android/Temi, camera/microphone, physical playback, LM Studio model behavior,
GPU inference, Discord recipient delivery and live perception remain separate
external acceptance gates.

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
python3 -m py_compile tools/demo_lifecycle.py tools/validate_documentation.py
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
| Android command execution | Fresh Android MQTT session, `cmd/result` lifecycle response, and device observation. | Bridge publish or a browser/terminal log. |
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
