# TemiAgent Repository Map

狀態：CURRENT；D2B source, publication and operator map：2026-08-31。

Use this map with [CURRENT_STATUS.md](CURRENT_STATUS.md) and the
[documentation index](README.md). A directory can be physically present in a
development mount without being canonical V1 source, a current contract owner or
publication material.

The public repository's `main` branch is the publication authority. The
previous public baseline was
`https://github.com/YI-TING-EE13/TemiAgent`, branch `main`, HEAD
`8fead49d66ab0a9d016a7dfe495b336146bbe957`, tree
`e5fa932b01cc1f885cd36023464a18f11bdf060a`; the documentation lineage
includes the completed D2B and D2B.2 remediation. The root license policy is
`NO_LICENSE`. A clean clone of the current public branch is the portable
operator source. The mounted `/TemiAgent` checkout is a protected development
workspace and may be dirty; it is not a portable operator default.

`/opt/TemiAgent-operator` is the `VALIDATED_AI6_OPERATOR_WORKSPACE` observed
for D2A. Its private runtime root is
`/opt/TemiAgent-operator/.runtime/demo`. These absolute paths and all runtime
artifact hashes are AI6 deployment evidence, not universal requirements.

For handover navigation, use [developer setup](operations/developer_setup.md),
[STUDENT_HANDOVER](project/STUDENT_HANDOVER.md) and the complete
[DOCUMENT_AUTHORITY_MAP](DOCUMENT_AUTHORITY_MAP.md). This map describes
repository ownership; it is not a substitute for runtime schemas or lifecycle
source.

## Canonical V1 source and runtime boundaries

| Area | Role | Boundary and authority |
|---|---|---|
| `scripts/` | Entry scripts | `scripts/demo` exposes the five primary lifecycle operations `doctor`, `start`, `status`, `stop` and the compatibility `restart`; `scripts/bootstrap` handles source reconstruction and readiness checks. |
| `tools/` | Cross-module adapters, lifecycle, health and test helpers | `tools/demo_lifecycle.py` owns lifecycle behavior; adapters do not own command dispatch. |
| `hermes_temi_bridge/` | Canonical safety boundary | Owns event/path/Hermes/action validation, dispatch, schemas and Bridge tests. Runtime schemas are authoritative. |
| `temi_backend/` | Legacy ASR, video, local VLM and MQTT route | Compatibility/legacy surface; not the canonical Hermes V1 ownership path. |
| `anomaly_detection/` | Optional perception viewer and event producer | Experimental, event-only boundary; never a general hardware dispatcher. |
| `hermes-skills/` | Reviewable Temi-specific skill mirror | Review/reference material; resident runtime uses the external Hermes skill tree. |
| `config/` | Non-secret templates and resource manifest | Configuration shape and optional asset expectations; private values stay outside Git. |
| `mqtt/` | Local Mosquitto configuration and topic index | Transport only; Bridge and producers/consumers own validation and semantics. |
| `memory/` | Tracked synthetic fixture documentation/data | Synthetic/de-identified Demo evidence only; runtime memory and production data never enter Git. |
| `temi_shared/` | Runtime image/event artifact layout | Shared runtime paths and metadata contract; actual images/data are non-source and non-publication. |

## External and generated source

| Area | Classification | Publication rule |
|---|---|---|
| `third_party/hermes/` | Manifest, ten patches and technical reconstruction instructions | Root-owned Hermes dependency contract: original upstream identity, team remote, license evidence and patched-tree target. The directory does not vendor Hermes source. |
| `hermes-agent/` | Formal Git submodule and generated patched worktree | Team remote is authoritative for the pinned base gitlink. Bootstrap applies root patches in this worktree; generated final commit IDs are not root dependency identity. |
| `third_party/llama_cpp/` | Tracked manifest and bootstrap README | Defines the external pin; bootstrap materializes `anomaly_detection/third_party/llama.cpp/`. |
| `anomaly_detection/third_party/llama.cpp/` | Ignored generated upstream checkout | External source only; not root source, and no model binary or weight is implied by the clone. |
| Model caches, downloaded weights and checkpoints | External artifacts | Keep outside publication until provenance, license and redistribution rules are confirmed. |

The Hermes manifest, formal submodule and patch series describe one
`PINNED_BASE_PLUS_PATCHED_WORKTREE` contract. The submodule must initialize from
`https://github.com/YI-TING-EE13/hermes-agent.git` at
`a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2`; the root-owned patches then produce
the expected final tree
`47e9f1411e585769c055d0c6ee4417bebcdc6f70`. A clean clone must use the team
remote and verify both identities before handover. No original-upstream,
local-checkout, file-URL or alternate-object fallback is allowed.

## Operator source isolation

The current operator sequence is owned by
[DEMO_OPERATOR_GUIDE.md](operations/DEMO_OPERATOR_GUIDE.md). It requires a
clean public-main clone, a separately provisioned dependency set, an owner-only
private config and a runtime root outside the source tree. The validated AI6
deployment used the following observed artifact contract:

| Artifact | Observed AI6 evidence | Portable interpretation |
|---|---|---|
| Hermes | Team fork base `a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` plus patches `0001`–`0010`, final tree `47e9f1411e585769c055d0c6ee4417bebcdc6f70` | Reconstruct from the team submodule and root patch manifest; do not use the original upstream or a local fallback. |
| llama.cpp | Generated operator executable under `/opt/TemiAgent-operator/anomaly_detection/third_party/llama.cpp/build/bin/llama-server`; observed SHA-256 `6827638842194c9903da14662737b1e5c7d35effa6353506a329d31f85029585` | Source commit/tree are pinned; build output, toolchain and binary hash are observed deployment evidence. |
| LM Studio | External API on `127.0.0.1:1234`, expected API identifier `google/gemma-4-31b`, context `64000` | External owner provisions and keeps it running; the lifecycle never starts, stops, unloads or reconfigures it. |
| MQTT | External/reused broker in the validated AI6 deployment | Ownership must be declared by the private config; never stop or adopt an occupied external listener. |
| Pose model | Not provisioned | Optional and not a readiness prerequisite; do not claim pose availability. |

Do not infer deployment readiness from a free port, a generated binary, a
historical PID or a dirty nested checkout. `bootstrap --check` and the
selected private-config `doctor` must both pass before an authorized lifecycle
operation.

## Experimental and local-only areas

| Area | Classification | Contract status |
|---|---|---|
| `local_inference/` | Ignored local DeepSeek/llama.cpp experiment | Loopback `1235`; not canonical V1 and not required by `scripts/demo`. |
| `sub2/` | Ignored local emotion-recognition experiment | Noncanonical; no Bridge, MQTT command or hardware ownership. |
| Optional pose inference | External model-assisted perception | `yolo26x-pose.pt` is optional; expected path/hash metadata does not establish provenance or publication permission. |
| `計劃書/` | Research and reference material | Not runtime source, deployment input or contract authority. |

## Runtime, deployment and historical boundaries

| Area | Classification | Rule |
|---|---|---|
| `.runtime/` | Ignored owner-only lifecycle state | Contains private config, PID/ownership state, logs and runtime data; never publish. |
| `logs/` | Runtime traces and diagnostics | Keep bounded/de-identified; not source or publication evidence by itself. |
| `temi_shared/` runtime contents | Images and metadata | MQTT carries allowlisted metadata/paths, not image binaries; real images remain outside Git. |
| `docker-compose.yml` | Optional secondary/development configuration | Not invoked by the canonical `scripts/demo` lifecycle and not a parallel production entrypoint. |
| `docs/` | Maintained architecture, operations, project and reader schemas | Start at `docs/README.md`; runtime schemas remain authoritative over prose copies. |
| Legacy runbooks and handovers | Historical/reference documents | Retained with the exact legacy notice; do not use as the current Demo lifecycle. |

## Contract navigation

- New-student setup and environment: [developer setup](operations/developer_setup.md).
- Handover questions and release routing: [STUDENT_HANDOVER](project/STUDENT_HANDOVER.md).
- Complete document authority inventory: [DOCUMENT_AUTHORITY_MAP](DOCUMENT_AUTHORITY_MAP.md).
- Host/service responsibility: [deployment handover](operations/demo_deployment_handover.md).

- Lifecycle: [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).
- Architecture: [project overview](architecture/project_overview.md).
- Contract ownership: [contract traceability](architecture/contract_traceability.md).
- Private configuration: [configuration reference](operations/demo_configuration_reference.md).
- Recovery and exact-PID policy: [safe service operations](operations/safe_service_operations.md).
- Verification boundary: [verification and acceptance](operations/verification_and_acceptance.md).

Do not infer canonical ownership from directory names, local process availability,
a historical command, an ignored checkout or a model file on disk. Update this map
when a maintained module boundary, external source pin or publication rule changes.
