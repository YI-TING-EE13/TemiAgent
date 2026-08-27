# TemiAgent Agent Guide

This file defines the mandatory collaboration boundary for human contributors and AI agents working on TemiAgent.

## Container-First Rule

All project reads, searches, edits, dependency operations, tests, builds, runtime inspection, debugging and service commands MUST run inside:

```text
DESIGNATED_CONTAINER=yiting.TemiAgent_gpu_all
PROJECT_ROOT_IN_CONTAINER=/TemiAgent
DEFAULT_SHELL_COMMAND=docker exec -it yiting.TemiAgent_gpu_all bash
```

Enter the environment with:

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
pwd
whoami
git rev-parse --show-toplevel
git status --short
```

Do not edit the mounted repository from the host, use another container, or present host-side tests as official evidence. Host work is allowed only when the user explicitly requests it or when the operation inherently manages or repairs the container itself. Report every host-side exception.

## Efficient Orchestration and Token Control

### Event-driven reporting

Do not poll delegated agents solely to produce progress messages. Remain silent while a delegated task is running unless one of the following occurs:

- a meaningful implementation milestone completes;
- a reproducible failure or blocker is found;
- authorization or user input is genuinely required;
- scope, safety boundary, repository state, or acceptance status changes;
- a stop condition is triggered; or
- final evidence is ready.

Progress messages MUST contain at least one new fact, such as changed files, a test command and result, a newly identified defect, a resolved review finding, a commit or artifact identifier, a changed authorization state, or the next concrete gate. Combine related results into one report. Do not send messages solely to indicate continued activity. Messages such as "still waiting," "no ADB used," "no side effect," or "tests are still running" are not progress reports unless they also state a new decision or state change.

### Polling

Prefer a blocking wait or task join over repeated status checks. When blocking wait is unavailable, use the longest practical wait interval, suppress user-facing messages for unchanged state, avoid inspecting the same state repeatedly without a new event, and stop polling after completion, failure, or a required decision is detected.

### Test reruns and evidence reuse

Do not rerun an unchanged test suite unless relevant source, tests, build configuration, dependencies, or generated inputs changed; the previous run was incomplete or nondeterministic; clean-build or release provenance requires a rerun; or an acceptance requirement explicitly requires independent repetition. Record the source digest or commit associated with every material test result and reuse valid evidence when relevant inputs are unchanged.

### Long-running task checkpoints

For a long-running task, maintain a concise machine-readable checkpoint in a task-local ignored location. The checkpoint MUST record:

- baseline commit;
- current phase;
- completed gates;
- unresolved findings;
- the last relevant source digest;
- valid test evidence;
- current permissions and prohibitions; and
- the exact next action.

Read the checkpoint before rereading broad project documentation or repeating completed analysis.

### Safety-state reporting

Safety restrictions remain in force until explicitly changed. Do not repeat unchanged restrictions in every update. Report ADB ownership, service state, APK installation permission, broker permission, or another operational boundary only when the state changes, a violation is detected, the next action depends on that boundary, or the final handoff requires the state.

### Review convergence

After fixing a finding:

1. Run the smallest deterministic test that proves the fix.
2. Run the required affected regression matrix once.
3. Review the final diff.
4. Proceed to the next gate.

Do not repeatedly reopen an approved design or rerun a valid matrix unless relevant inputs changed.

## Required Reading Before Modification

Read the following before changing project-wide behavior or documentation:

1. `README.md`
2. `AGENTS.md`
3. `docs/README.md`
4. `docs/architecture/project_overview.md`
5. `docs/architecture/contract_traceability.md`
6. The target module README
7. Relevant runtime schemas, configuration, tests and runbooks

Read `hermes-agent/README.TemiAgent.md` before changing Temi-specific integration around the upstream Hermes checkout. Read the nested `hermes-agent/AGENTS.md` before any authorized upstream Hermes modification.

## Architecture and Safety Boundaries

- `temi_backend/` owns the verified legacy ASR, video, local VLM and legacy MQTT route.
- `tools/temi_overview_adapter.py` adapts legacy ASR and camera frames to canonical ASR events. It does not own command dispatch.
- `hermes_temi_bridge/` is the canonical safety boundary. It validates inbound events, robot IDs, paths, Hermes JSON and actions before publishing command requests.
- `hermes-agent/` owns reasoning runtime behavior. Hermes returns JSON-only action plans and MUST NOT publish MQTT or control hardware directly.
- `hermes-skills/` mirrors Temi-specific skills for review; the resident runtime uses `hermes-agent/skills/temi-*`.
- `anomaly_detection/` produces experimental perception events. A perception model MUST NOT become a general hardware dispatcher.
- `temi_shared/` holds runtime images and event metadata. MQTT carries metadata and allowlisted paths, not image binaries.
- The Temi Android App owns hardware execution. Its source is outside this workspace unless a task provides and authorizes that source.

Do not bypass `event_models.py`, `image_resolver.py`, `action_validator.py`, the runtime schemas or the Bridge dispatch boundary. The existing action-viewer pre-alert direct publish is a documented Demo-only safety gap, not an approved pattern for new code.

Emergency notification, medical diagnosis, guaranteed fall detection and unsupervised autonomous care are not implemented or verified capabilities. `notify_caregiver_mock` is Demo-only. Discord webhook delivery is a best-effort side channel, not an emergency service.

## Contract Ownership and Synchronization

`docs/architecture/contract_traceability.md` maps every cross-module contract to its authoritative source, producers, consumers and tests.

Runtime JSON schemas under `hermes_temi_bridge/schemas/` are authoritative. Files under `docs/schemas/` are reader copies and MUST remain byte-equivalent to their mapped runtime schema even when filenames differ.

A contract change MUST update, in one reviewable change:

- the authoritative runtime definition;
- every producer and consumer;
- validation and compatibility behavior;
- producer, consumer and invalid-input tests;
- the relevant module README;
- the reader schema copy and architecture/operations documentation.

Do not change topics, payloads, shared paths, environment variables, service ports, action types, model I/O, memory formats, health endpoints or runtime artifact layouts from documentation alone.

## Authorized and Protected Files

The current task defines the exact writable scope. An agent MUST list intended files before a multi-file change and preserve unrelated working-tree changes.

Without explicit task authorization, do not modify:

- Android App source or installed packages;
- upstream Hermes code;
- Bridge core behavior or validators;
- model algorithms, prompts that change safety policy, training loops or inference results;
- MQTT runtime behavior, payload behavior or service ports;
- dependencies, lockfiles, images or environment versions;
- runtime memory, logs, images, datasets, caches, checkpoints or user data.

Never delete or overwrite a file that has not been read and classified. Never use `git reset --hard`, `git clean`, checkout-based discard, rebase or broad formatting to hide unrelated changes.

## Runtime Data, Privacy and Secrets

Treat the following as non-source artifacts unless a reviewed, de-identified fixture policy says otherwise:

- `logs/`, PID files and trace output;
- `temi_shared/` images and metadata;
- `memory/` state, event logs and summaries;
- local datasets, video, screenshots and recordings;
- `.env` files, credentials and gateway state;
- model caches, downloaded weights and checkpoints.

Do not commit secrets, webhook URLs, credentials, private keys, real care records, identifiable images, private network addresses or user-specific host paths. Use environment-variable names, placeholders and ignored local configuration. Logs MUST avoid full sensitive payloads and unrestricted media, and SHOULD include timestamp, module, severity and event/request/run/trace identifiers.

Any retained fixture MUST document source, consent or synthetic status, de-identification, purpose, retention and access rules.

## Service and High-Risk Operations

Do not start, stop or restart a long-running service unless the task explicitly authorizes service operation.

Before an authorized process operation:

1. Record the target service, port, expected executable and working directory.
2. Record pre-operation health.
3. Resolve the exact PID from the port or service manager.
4. Verify `/proc/<pid>/cmdline`, `/proc/<pid>/cwd` and executable ownership.
5. Prefer the project script or service manager.
6. Send `TERM` only to the verified PID.
7. Use `KILL` only against the same verified PID after a bounded wait.
8. Verify target health and protected dependent services.

Broad process patterns are prohibited:

```text
pkill -f <pattern>
pkill python
killall python
killall <service-class>
```

Follow `docs/operations/safe_service_operations.md` for restart, rollback, restore and incident evidence. Bulk data changes, migrations, permissions, secrets, network rules, personal/care data, model thresholds, automated notifications and hardware control require explicit human confirmation and an executable rollback or containment plan.

## Verification

Use repository commands, not a generic test stack. Run the narrowest relevant check first and broader checks when impact warrants them.

Common hardware-free checks:

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

```bash
cd /TemiAgent/temi_backend
uv run pytest
```

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

Documentation changes also require:

- relative-link validation;
- stale-path search;
- schema-copy comparison;
- Markdown code-fence validation;
- private-path and secret scan;
- documented command/path/port/topic/model/environment consistency review;
- `git diff --check`;
- final `git status --short`.

Do not start long-running services merely to validate documentation. Mark hardware, GPU, Android, Discord or external-service checks `SKIPPED` when the task does not authorize or provide those dependencies.

## Git and Delivery

Before editing, record branch, HEAD and `git status --short`. After editing, inspect `git diff --stat`, the complete relevant diff and final status.

Do not commit, push, merge, rebase, reset, clean or tag unless the user explicitly requests that Git action. A dirty tree belongs to the user; preserve unrelated changes and identify pre-existing changes separately from task changes.

`hermes-agent/` is an external Git repository recorded by the root repository as
a formal submodule. The root gitlink pins the verified team-controlled base
commit; Temi-specific integration remains in the root repository's ordered
patch series and is applied in the submodule worktree. Before the first
root-repository publication, a maintainer MUST use a team-accessible Hermes
fork or remote containing the pinned commit, configure the formal submodule URL,
and verify `git submodule update --init --recursive` from a clean clone. Until
that clean-clone check passes, the root repository MUST NOT be described as
fully reproducible outside this workspace.

The final report MUST include:

1. Scope completed and protected scope left unchanged.
2. Files added, modified, moved and deleted.
3. Contract, compatibility and safety decisions.
4. Commands actually run with PASS, FAIL or SKIPPED.
5. Evidence and remaining coverage gaps.
6. Deferred work with repository evidence.
7. Branch, HEAD, pre-existing changes, final changed files, `git diff --check` and `git status --short`.

Never claim completion from inspection alone when the requested result requires executable evidence.
