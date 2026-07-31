# Verification and Acceptance Guide

Status: maintained. Last reviewed: 2026-07-31.

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
bash -n scripts/demo scripts/bootstrap scripts/bootstrap_hermes.sh
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
dependencies, and starts no service. For a clean source checkout, the separate
operator/maintainer action is `./scripts/bootstrap --hermes`; it must not be
combined with an unreviewed nested-gitlink change.

## Software-only newcomer acceptance

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
./scripts/bootstrap --hermes
./scripts/bootstrap --hermes

cd hermes_temi_bridge && uv sync --frozen --extra mqtt
cd ../anomaly_detection && uv sync --frozen
cd ..

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
acceptance_root="/tmp/temiagent_newcomer_acceptance_${run_id}"
umask 077
mkdir -p "$acceptance_root/config"
sed "s#<RUN_ID>#${run_id}#g" config/demo.mock.env.example > "$acceptance_root/config/demo.mock.env"
chmod 600 "$acceptance_root/config/demo.mock.env"
config="$acceptance_root/config/demo.mock.env"

./scripts/demo --config "$config" --json doctor
./scripts/demo --config "$config" --json start
./scripts/demo --config "$config" --json start
./scripts/demo --config "$config" --json status
./scripts/verify_newcomer_mock --config "$config"
./scripts/demo --config "$config" --json restart
./scripts/demo --config "$config" --json stop
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
| Demo lifecycle/resident wrapper | `cd /TemiAgent && python3 -m unittest discover -s tools/tests` | Lifecycle config/identity records, resident health and LM Studio helper behavior. |
| Action viewer parser/unit behavior | `cd /TemiAgent/anomaly_detection && .venv/bin/python -m unittest discover -s tests -p 'test_temi_action_viewer.py'` | Viewer parsing, receipts and local test seams; no model service starts. |
| Root mock E2E | `cd /TemiAgent && python3 tools/e2e_test_runner.py` | Local mock canonical event-to-command route. |
| Media v1.1 fake Android | `cd /TemiAgent && python3 tools/media_v11_fake_e2e.py` | Request/result correlation, lifecycle, replay and trace in-process. |
| Pinned Hermes compressor | `cd /TemiAgent/hermes-agent && venv/bin/python -m pytest tests/agent/test_context_compressor.py` | Nested overlay compressor behavior, when the pre-existing nested environment is provisioned. |

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
