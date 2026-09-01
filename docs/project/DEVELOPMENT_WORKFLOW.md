# AI6 TemiAgent Academic-Lab Development Workflow

Status: `CURRENT_AUTHORITY`; initial publication: 2026-09-01.

This document defines the normal future-development process for successor
students working on TemiAgent as an academic research project. It complements
the [student handover](STUDENT_HANDOVER.md), [repository governance](../../AGENTS.md),
[developer setup](../operations/developer_setup.md), and [verification guide](../operations/verification_and_acceptance.md).

The workflow governs repository work. It does not replace runtime schemas,
executable validators, module READMEs, the current Demo operator guide, or the
safe-service policy. A research Issue or Pull Request does not authorize a
service operation, MQTT publication, Android/Temi action, model inference,
credential operation, or destructive repository/data change.

## Operating model

`PROJECT-01` provides research direction, priorities, important constraints,
the expected high-level outcome, feedback on proposed direction, and a final
lightweight review. The repository maintainer makes the technical decisions
needed to deliver the accepted direction. `PROJECT-01` is not expected to
design every class or function, debug routine implementation, approve every
commit, run every test, manage routine branch operations, or supervise each
implementation step.

The normal development flow is:

```text
Research direction
  -> Issue / task definition
  -> Change classification
  -> Feature / fix / experiment branch
  -> Maintainer-owned implementation
  -> Verification / experiment evidence
  -> Pull Request
  -> CI / review
  -> PROJECT-01 lightweight final review
  -> Merge
  -> Runtime/integration acceptance when required
  -> Status / experiment record update
  -> Issue closure
```

The maintainer may move through the flow independently for routine repository
work. The consultation rules below add review or authorization only when the
change class requires it.

## Roles

Role IDs identify responsibilities, not permanent people. A project may assign
one person to several roles or change the assignment without changing this
workflow.

| Role ID | Responsibility | Consult when |
|---|---|---|
| `PROJECT-01` | Research direction, priorities, constraints, high-level outcome, feedback, and final lightweight research/governance decision. | The objective, research direction, major architecture, or final acceptance decision needs confirmation. |
| `AI6-01` | Primary TemiAgent / AI6 repository maintainer; decomposes Issues, designs within contracts, implements, tests, records evidence, updates docs, and prepares PRs. | Any change owned by the root repository or any cross-module change without a more specific owner. |
| `MQTT-01` | MQTT boundary, broker-ownership, topic and transport maintenance. | A change affects MQTT topics, payloads, broker ownership, listener behavior, or compatibility. |
| `HERMES-01` | Hermes source integration, patch overlay, skills, prompts, and Hermes environment contract. | A change affects Hermes source, patches, skills, model I/O, or source bootstrap. |
| `BRIDGE-01` | HermesTemiBridge schemas, validators, action boundary, dispatch and trace behavior. | A change affects Bridge validation, command contracts, event paths, or dispatch. |
| `LMSTUDIO-01` | External local-model runtime, model identity, context and GPU-provider boundary. | A change affects external model readiness, model identity, context policy or provider ownership. |
| `STREAM-01` | Streaming, viewer and perception runtime behavior. | A change affects frame streaming, viewer health, llama-server integration or perception output. |
| `ANDROID-01` | External Android repository, app-side schemas, execution and device integration. | A change affects Android behavior, APKs, app-side persistence or cross-repository contracts. |
| `TEMI-01` | Physical Temi/device acceptance and bounded hardware observation. | A change requires real-device execution or physical acceptance evidence. |

## Issue as the unit of work

For non-trivial development, a GitHub Issue SHOULD be the unit of work. A
trivial typo-only correction MAY proceed without an Issue when repository
practice does not benefit from one.

An Issue records the objective and acceptance boundary, not a line-by-line
implementation order from `PROJECT-01`. The assigned maintainer is responsible
for decomposition and technical design.

Each non-trivial Issue should state:

- objective or research question;
- motivation;
- scope;
- non-goals;
- repository and module owner;
- expected interface or contract impact;
- acceptance criteria;
- required evidence;
- external dependencies;
- cross-repository impact;
- risk/change class; and
- open decisions.

The maintainer should link the eventual branch, Pull Request, evidence and
final commit back to the Issue.

## Change classes

Classify the work before substantial implementation. The class controls the
amount of direction, contract review and authorization required.

### Class A — `REPO_LOCAL`

Examples include an internal bug fix, refactor, test, documentation change or
module-local implementation. `AI6-01` MAY design and implement the change
autonomously within existing contracts and safety boundaries. No mandatory
`PROJECT-01` pre-implementation approval is required.

### Class B — `RESEARCH_OR_ARCHITECTURE`

Examples include a new model, reasoning approach, perception method, major
subsystem or research-method change. Before substantial implementation,
`AI6-01` SHOULD summarize the proposed approach, expected evidence and known
limitations. `PROJECT-01` reviews the research direction and outcome; the
maintainer retains low-level implementation decisions.

### Class C — `CROSS_REPO_CONTRACT`

Examples include an Android-to-AI6 payload, MQTT schema, canonical command,
WebSocket contract or shared feature flag. The maintainers MUST agree on a
short contract/design summary before merging an incompatible implementation.
Use one shared Change ID in both repositories and Issues/PRs; see
[Cross-repository changes](#cross-repository-changes).

### Class D — `HIGH_RISK_OPERATION`

Examples include production runtime mutation, a service-ownership change,
model/runtime replacement, real Temi action, data deletion,
credential/signing operation or safety-notification behavior. The maintainer
MUST obtain explicit authorization and follow the existing runbook, exact
targeting and rollback rules. A Class D Issue or PR alone is not authorization.

## Branch and worktree rules

Normal development starts from the current public `main` in a clean,
owner-approved development clone or worktree. Use the designated container and
the clean-clone setup in [developer setup](../operations/developer_setup.md):

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd <clean-clone-root>
git fetch origin
git switch --create feat/<issue>-<short-topic> origin/main
git status --short
```

Suggested branch prefixes are:

```text
feat/<issue>-<short-topic>
fix/<issue>-<short-topic>
experiment/<issue>-<short-topic>
docs/<issue>-<short-topic>
```

Do not develop directly on `main`. Do not use the protected dirty canonical
worktree as the feature branch, operator workspace, dependency source or
fallback. Keep commits logically scoped and do not mix unrelated cleanup with
research implementation. A maintainer should be able to revert or review the
change as one coherent patch boundary.

## Maintainer-owned implementation

`AI6-01` owns source inspection, impact analysis, design within accepted
contracts, implementation, tests, regression selection, reproducibility
evidence, documentation updates, PR preparation and responses to review
findings. The responsible specialist role participates when a module,
dependency or external contract is affected.

The maintainer MUST preserve existing ownership and safety boundaries. In
particular:

- Hermes MUST remain a JSON-only reasoning component and MUST NOT publish MQTT
  or control hardware directly.
- The Bridge MUST remain the validation and dispatch boundary.
- Perception and analytics components MUST NOT become general hardware
  dispatchers.
- Runtime schemas remain authoritative; prose cannot change a payload or
  interface by itself.
- Runtime data, private configuration, credentials, model caches, recordings,
  real resident data and prohibited large artifacts MUST remain outside the
  publication boundary.

## Research experiment lifecycle

Research evidence and accepted system behavior use separate states:

| State | Meaning |
|---|---|
| `EXPERIMENTAL` | An exploratory method or result exists; repeatability or integration is not established. |
| `REPRODUCED` | The result can be repeated with recorded inputs and configuration. |
| `IMPLEMENTED` | The method is integrated into repository code. |
| `VERIFIED` | The required automated or integration evidence passes. |
| `ACCEPTED` | The result has passed the required project, runtime or device acceptance boundary. |

A promising metric or one successful run MUST NOT be described as `ACCEPTED`.
The experiment record or Issue should state the current state, the evidence
that supports it, the next transition, and the limitations that remain.

When relevant, record enough metadata to reproduce the result without
committing prohibited artifacts:

- dataset or fixture identity and data split;
- model identity and version;
- source commit;
- configuration and important hyperparameters;
- random seed;
- evaluation metric and baseline;
- hardware/runtime assumptions; and
- known limitations or failed runs that affect interpretation.

Datasets, model weights, private recordings and resident information remain
subject to the existing privacy, consent, retention and publication rules.

## Verification and evidence

Use the smallest relevant deterministic check first, then run the regression
scope warranted by the impact. Reuse valid evidence only when the relevant
source, configuration, dependency and generated inputs are unchanged, as
per [AGENTS.md](../../AGENTS.md).

Every PR MUST distinguish the evidence level:

| Evidence level | What it proves | Typical owner |
|---|---|---|
| `SOURCE / UNIT` | Static checks and isolated behavior in the changed module. | `AI6-01` or module owner |
| `INTEGRATION` | A cross-module route using real contracts and bounded fixtures or services. | Affected module owners |
| `RUNTIME` | A configured service, process-ownership and health boundary in an authorized environment. | Runtime owner and `AI6-01` |
| `DEVICE / EXTERNAL` | Android, Temi, provider, GPU or recipient behavior observed through its external owner. | `ANDROID-01`, `TEMI-01` or relevant provider owner |
| `NOT VERIFIED` | A required boundary whose dependency, authorization or evidence is unavailable. | Maintainer records the reason |

Do not start a production or shared service merely because a source change
exists. Hardware, GPU, Android, external-provider and notification checks are
separate gates. Mark an unavailable gate `SKIPPED` with its reason rather than
upgrading a mock or unit result to a live claim. Use the current
[verification and acceptance guide](../operations/verification_and_acceptance.md)
for repository commands and acceptance vocabulary.

## Pull Request review packet

Every non-trivial PR SHOULD give reviewers a compact, answer-first packet:

| Field | Required content |
|---|---|
| Goal | Problem or research objective addressed. |
| What changed | Implementation, experiment, contract or documentation changes. |
| Evidence | Tests, metrics, reproduction steps, runtime or device evidence, each labeled by evidence level. |
| Known limitations | Claims that remain unproven, failed cases and deferred work. |
| Cross-repo impact | `NONE` or the exact repository, Change ID and contract affected. |
| Decision needed | `NONE` or the precise `PROJECT-01` decision required. |

The PR also includes the linked Issue, changed modules, complete test commands
and results, documentation impact, and a rollback or containment note when the
change can affect runtime, data or an external boundary. The packet should let
`PROJECT-01` review the direction and evidence without reconstructing the
implementation.

## PROJECT-01 final review

`PROJECT-01` performs a lightweight final review when the change class or Issue
requires it. The review asks:

- Does the result still address the intended research or project problem?
- Is the evidence appropriate for the claim?
- Is the scope controlled?
- Are limitations stated honestly?
- Is a cross-repository or safety decision unresolved?
- Is the proposed next step reasonable?

`PROJECT-01` is not expected to perform a line-by-line implementation audit
for every routine repository-local change. A Class A change may proceed through
normal repository review once its direction and evidence are sound.

## Merge gate

Before merge, the maintainer confirms:

- the PR scope is coherent;
- required CI and tests pass;
- review findings are resolved;
- current documentation is updated when current truth changes;
- no prohibited or private artifact entered the change;
- cross-repository contracts have coordinated evidence; and
- the required `PROJECT-01` review is complete for the change class.

Prefer a squash merge for a normal feature PR unless repository history
requires another documented method. Merging, release and deployment remain
maintainer decisions. A merged PR does not automatically authorize runtime or
device acceptance.

## Post-merge and Issue closure

When an accepted current system state changes, update the authoritative status
or verification document named by the [document authority map](../DOCUMENT_AUTHORITY_MAP.md).
Update the relevant experiment record when an experiment advances, fails or
produces a useful null result.

Close the Issue with:

- final result;
- accepted evidence level;
- known limitations;
- follow-up work; and
- relevant PR and commit.

An Issue MAY close with a documented research failure or null result when the
record helps the laboratory avoid repeating an invalid conclusion.

## Cross-repository changes

For a change involving both `YI-TING-EE13/TemiAgent` and
`YI-TING-EE13/temi-agent-android`, create one shared Change ID, for example:

```text
CR-YYYYMMDD-short-topic
```

Reference the same Change ID in both Issues and PRs. Each repository
maintainer modifies only the repository they own. The recommended order is:

1. define the contract;
2. identify a backwards-compatible transition when feasible;
3. update producer and consumer tests;
4. implement each repository independently;
5. pass each repository's CI;
6. merge in an explicitly documented safe order;
7. perform bounded integration/device acceptance only when required; and
8. record final evidence in each repository at the correct evidence level.

Do not make one repository depend on an unmerged, undocumented payload change
in the other repository.

## When `PROJECT-01` must be consulted before action

Retain the stronger existing safety rules. Obtain explicit direction or
authorization before:

- changing a cross-repository contract;
- making a major architecture change;
- changing the research objective;
- changing production runtime ownership;
- performing a real-device high-risk operation;
- changing safety policy;
- handling credentials or signing material; or
- performing destructive data or repository operations.

Routine repo-local implementation does not require repeated approval. An Issue,
PR, free port, passing unit test or successful mock does not grant a stronger
permission than the existing safety/runbook contract.

## Keep the process lightweight

This workflow is for an academic research laboratory. It requires traceable
Issues, coherent branches, evidence and review, but it does not require Scrum
ceremonies, daily reports, story points, complex approval chains or a separate
approval for every routine implementation decision. Add a new record or review
step only when it protects a research claim, contract, safety boundary,
reproducibility requirement or maintainer handoff.
