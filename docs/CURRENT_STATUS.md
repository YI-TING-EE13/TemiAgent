# TemiAgent Current Status

狀態：CURRENT；governance snapshot：2026-08-26。

This page is the maintained status snapshot for implementation, verification,
runtime honesty and publication blockers. It is not a runtime health endpoint and
does not replace the runtime schemas, module READMEs or the
[canonical Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).

## Snapshot

| Item | Snapshot | Meaning |
|---|---|---|
| Project root | `/TemiAgent` in `yiting.TemiAgent_gpu_all` | Canonical project command boundary. |
| Root branch | `main` | No branch operation was performed in this gate. |
| Root HEAD | `ff37462ca393993b0cf2d42384e474649b463e50` | HEAD is unchanged during Gate 1B. |
| Configured root remotes | None in this local snapshot | Publication still needs a maintainer-owned remote decision. |
| Lifecycle status | `BACKEND_NOT_READY`; `lifecycle_state=NO_OWNERSHIP` | Read-only `./scripts/demo --json status` found no owned run. |
| Canonical listeners | None on `1234`, `1883`, `8010`, `8011`, `8080`, `8081`, or `8765` | No production listener claim is made. |
| Service operation | No service was started, stopped or restarted for this documentation gate. | Hardware and external-service state was left unchanged. |

The worktree contains intentional Gate 1A publication and synthetic-fixture changes
plus this Gate 1B documentation work. `./scripts/demo doctor` reports a dirty
repository for that reason; its runtime layout, ownership and path checks pass,
while service-dependent checks remain unavailable. This is not evidence of a live Demo.

## Canonical V1 flow and ownership

```text
Temi Android ASR/camera
  -> tools/temi_overview_adapter.py
  -> canonical ASR/perception events plus allowlisted paths
  -> HermesTemiBridge validation
  -> resident Hermes JSON-only reasoning
  -> HermesTemiBridge action validation and dispatch
  -> temi/{robot_id}/cmd/request
  -> Temi Android executor
  -> temi/{robot_id}/cmd/result and Bridge trace
```

`hermes_temi_bridge/` is the canonical safety boundary: it validates event
identity, evidence paths, Hermes JSON and actions before command publication.
Hermes returns a structured JSON-only plan and does not publish MQTT or control
hardware. Anomaly perception is optional and event-producing only; it does not
become a general dispatcher. Android source and hardware execution are external
to this workspace.

## Capability state

`IMPLEMENTED` means code exists. `HARDWARE_FREE_VERIFIED` means the named unit,
mock or fake path actually passed. `LIVE_NOT_VERIFIED` means there is no current
claim for a real Temi, Android session, MQTT broker, LM Studio/model service,
GPU, Discord recipient or real perception stream. `LEGACY`, `EXPERIMENTAL` and
`DEMO_ONLY` are scope labels, not stronger verification levels.

| Capability | State | Evidence boundary |
|---|---|---|
| Bridge validation, schemas and dispatch boundary | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Bridge unit/integration tests and fake routes pass; real Android execution is external. |
| Canonical ASR adapter route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Adapter and Bridge software paths are tested; Temi microphone/session evidence is not current. |
| Media v1.1 command/result route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Fake Android media lifecycle is tested; real playback is not verified. |
| Resident Hermes wrapper/mock route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Local wrapper and mock integration are testable; live provider, model and GPU are not verified. |
| Immediate abnormal-care Bridge route | `IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED` | Synthetic event, bounded notification, Hermes follow-up and action validation are tested; real recipient/device execution is not. |
| Structured care memory | `DEMO_ONLY; HARDWARE_FREE_VERIFIED` | Tracked memory is synthetic/de-identified fixture material; runtime and production data are excluded. |
| Legacy ASR/video/local-VLM route | `LEGACY; LIVE_NOT_VERIFIED` | `temi_backend/` remains for compatibility; historical hardware observations are not current evidence. |
| Continuous abnormal perception viewer | `EXPERIMENTAL; LIVE_NOT_VERIFIED` | Optional viewer/event producer; model output is not medical or fall-detection certification. |
| Temi Android, real MQTT, LM Studio, GPU, Discord and real camera stream | `LIVE_NOT_VERIFIED` | External dependencies and hardware gates were not authorized or available in this snapshot. |

## External, generated and optional artifacts

- `third_party/hermes/` records the public upstream URL, base commit, ordered patch
  series, required paths, target-tree metadata and the
  `PINNED_BASE_PLUS_PATCHED_WORKTREE` contract used to reconstruct the nested
  `hermes-agent/` checkout. The historical local evidence is branch
  `temiagent/integration` at `126aa304cda027679fc84212925bbd5329ada20b`; it is
  not publication source and does not replace a fresh public reconstruction.
- The Hermes pinned commit is intended to be fetched directly from the public
  upstream. Gate 3.1 candidate fetches were bounded and remained unavailable
  because of upstream timeout and earlier HTTP 429 responses, so fresh Hermes
  A/B evidence and the manifest base-tree value remain pending. The current
  manifest also keeps Hermes license identity explicitly
  `UNVERIFIED_PENDING_PUBLIC_FETCH`; the bootstrap verifier fails closed until
  the pinned source is available and independently checked.
- `HERMES_DEPENDENCY_GOVERNANCE: BLOCKED / NOT YET SATISFIED`. Per
  `AGENTS.md`, a maintainer must provide a team-accessible Hermes fork or
  remote containing the pinned commit, configure the formal Git submodule URL,
  and verify `git submodule update --init --recursive` from a clean clone.
  This candidate has no such team-accessible remote or formal submodule.
  `HERMES_TEAM_FORK_REQUIRED: YES`; `HERMES_TEAM_FORK_AVAILABLE: NO`. The
  formal submodule is required as part of this handover model, not an alternative
  that removes the remote ownership requirement.
- `hermes-agent/` is generated external checkout state, not TemiAgent root source,
  vendored source or a current root submodule. Its nested working tree was left
  unchanged; the technical reconstruction manifest does not by itself establish
  ownership or handover readiness.
`third_party/llama_cpp/` holds the manifest and README; bootstrap materializes
  the generated external checkout at `anomaly_detection/third_party/llama.cpp/`.
  Neither path is TemiAgent root source, and the clone does not imply a model
  binary or model weights.
- `yolo26x-pose.pt` is an optional external weight expected by the resource manifest;
  the manifest records local size/hash expectations only. Source, version, license
  and redistribution restrictions require maintainer confirmation. No download URL
  is asserted.
- A clean clone must not be expected to contain downloaded models, checkpoints,
  caches, recordings, runtime images or private configuration.

## Publication and release blockers

1. This local root has no configured remote. A maintainer must choose and configure
   the team-accessible publication target before claiming clean-clone delivery.
2. The historical HEAD contains the large pose checkpoint. Gate 1A removes it from
   the current index while preserving history; Gate 1B performs no history rewrite.
3. Pose model provenance, version, license and redistribution restrictions remain
   unresolved; do not publish or redistribute the local weight until confirmed.
4. Local credential-bearing environment files are owner-only and excluded from Git;
   owner handling/rotation remains outside this documentation gate.
5. The nested Hermes source needs successful public pinned fetches plus the
   clean-clone reconstruction check before the root repository can be described
   as fully reproducible outside this workspace. In addition, `AGENTS.md`
   requires a team-accessible fork or remote containing the pinned commit, a
   formal Git submodule URL, and clean-clone submodule verification. The current
   technical reconstruction has none of those ownership artifacts:
   `HERMES_DEPENDENCY_GOVERNANCE: BLOCKED / NOT YET SATISFIED`.

## Documentation authority

Use the root [README](../README.md), this status page, the
[repository map](REPOSITORY_MAP.md), [project overview](architecture/project_overview.md),
[contract traceability](architecture/contract_traceability.md) and the sole current
[Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md) in that order. The
[quick reference](operations/DEMO_QUICK_REFERENCE.md) is a compact companion, not
a second lifecycle authority. Dated, machine-specific and direct-service material
is explicitly marked legacy in the documentation index and retained only as evidence.

## Verification snapshot

The final Gate 1B verification below was run after the documentation changes. It
remains hardware-free and did not start a long-running service:

| Check | Result |
|---|---|
| `./scripts/bootstrap --check` | PASS |
| `cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests` | 166 PASS |
| `cd temi_backend && uv run --locked --offline pytest` | 22 passed |
| `cd anomaly_detection && uv run --locked --offline python -m unittest discover -s tests` | 34 PASS |
| `python3 -m unittest discover -s tools/tests` | 62 PASS |
| `python3 tools/e2e_test_runner.py` | PASS; `status:ok` with mock command topic |
| `python3 tools/media_v11_fake_e2e.py` | PASS; 4 request traces, 7 result traces, cached replay confirmed |
| `python3 tools/validate_documentation.py` | PASS; 71 first-party Markdown files and 8 schema mappings |
| Live Temi/Android/MQTT/LM Studio/GPU/Discord/perception gates | SKIPPED / LIVE_NOT_VERIFIED |

No service was started merely to validate documentation.

The bootstrap row above is historical Gate 1B evidence, not fresh Gate 3.3
Hermes evidence. Gate 3.3 does not claim a Hermes reconstruction while the
manifest license status remains `UNVERIFIED_PENDING_PUBLIC_FETCH`.

## Next gate

After maintainer approval, perform the separately scoped history/publication
remediation. Then establish the team-accessible Hermes source boundary and run a
clean-clone reconstruction check. Real Android, Temi, broker, model/GPU, Discord
and perception verification require their own authorized operational gate.
