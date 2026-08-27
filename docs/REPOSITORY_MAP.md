# TemiAgent Repository Map

狀態：CURRENT；high-density source and publication map：2026-08-26。

Use this map with [CURRENT_STATUS.md](CURRENT_STATUS.md) and the
[documentation index](README.md). A directory can be physically present in a
development mount without being canonical V1 source, a current contract owner or
publication material.

## Canonical V1 source and runtime boundaries

| Area | Role | Boundary and authority |
|---|---|---|
| `scripts/` | Entry scripts | `scripts/demo` exposes the five-command lifecycle; `scripts/bootstrap` handles source reconstruction and readiness checks. |
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
| `third_party/hermes/` | Manifest, patches and technical reconstruction instructions | External generated dependency; not root source, not vendored, and not a current root submodule. Root handover remains blocked until the `AGENTS.md` team-accessible remote, formal submodule URL and clean-clone gate exist. |
| `hermes-agent/` | Local nested checkout | External generated runtime state; nested source is not root-owned and must not be edited by this task. Its presence is not ownership or handover evidence. |
| `third_party/llama_cpp/` | Tracked manifest and bootstrap README | Defines the external pin; bootstrap materializes `anomaly_detection/third_party/llama.cpp/`. |
| `anomaly_detection/third_party/llama.cpp/` | Ignored generated upstream checkout | External source only; not root source, and no model binary or weight is implied by the clone. |
| Model caches, downloaded weights and checkpoints | External artifacts | Keep outside publication until provenance, license and redistribution rules are confirmed. |

The Hermes manifest and patch series describe a technical public-upstream
reconstruction. They do not replace the repository-mandated team-accessible
fork/remote, formal Git submodule and clean-clone verification required before
root publication or handover.

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

- Lifecycle: [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).
- Architecture: [project overview](architecture/project_overview.md).
- Contract ownership: [contract traceability](architecture/contract_traceability.md).
- Private configuration: [configuration reference](operations/demo_configuration_reference.md).
- Recovery and exact-PID policy: [safe service operations](operations/safe_service_operations.md).
- Verification boundary: [verification and acceptance](operations/verification_and_acceptance.md).

Do not infer canonical ownership from directory names, local process availability,
a historical command, an ignored checkout or a model file on disk. Update this map
when a maintained module boundary, external source pin or publication rule changes.
