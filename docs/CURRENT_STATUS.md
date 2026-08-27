# TemiAgent Current Status

狀態：CURRENT；governance snapshot：2026-08-27。

This page is the maintained status snapshot for implementation, verification,
runtime honesty and publication blockers. It is not a runtime health endpoint and
does not replace the runtime schemas, module READMEs or the
[canonical Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md).

## Gate 4 handover candidate

Gate 4 documentation work is isolated in
<code>/tmp/temiagent-worktrees/github-v1-handover-freeze</code> on branch
<code>codex/github-v1-handover-freeze</code>, derived from
<code>release/github-v1@d66a046395aed21712b00cba43d4ea1b2d9f23de</code>.
The candidate changes documentation and documentation validation only. It does
not advance <code>release/github-v1</code>, modify canonical <code>main</code>,
operate services, publish MQTT or push.

## Snapshot

| Item | Snapshot | Meaning |
|---|---|---|
| Project root | `/TemiAgent` in `yiting.TemiAgent_gpu_all` | Canonical project command boundary. |
| Root branch | `main` | Canonical root branch; Gate 3.4 work runs in an isolated candidate worktree. |
| Root HEAD | `12aff3bfdfe526c17a25a2681aea2afad7112b33` | Canonical HEAD is unchanged during Gate 4. |
| Configured root remotes | None in the canonical local snapshot | Root publication push was not performed; the separate Hermes team remote was independently verified. |
| Lifecycle status | `RUNNING`; `reason=READY` | Read-only `./scripts/demo --json mqtt status` found the canonical MQTT broker healthy at `0.0.0.0:1883`. |
| Canonical listeners | One listener on `0.0.0.0:1883` | This is a read-only runtime observation, not a Gate 4 service operation. |
| Service operation | No service was started, stopped or restarted for Gate 4. | Hardware and external-service state was left unchanged. |

The canonical worktree contains pre-existing Gate 1A, synthetic-fixture and
documentation changes. Gate 4 changes are isolated in
`/tmp/temiagent-worktrees/github-v1-handover-freeze`; the candidate does not
modify the canonical runtime or publication branch. A running MQTT status is
reported only as the read-only Phase 0 observation.

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

- `third_party/hermes/` records the original upstream URL, the team-controlled
  remote, the formal `hermes-agent/` submodule path and URL, the pinned base
  commit/tree, the ordered nine-patch series, the expected final tree and the
  verified license identity. The historical local integration commit
  `126aa304cda027679fc84212925bbd5329ada20b` remains historical; generated local
  final commit IDs are not dependency authority.
- Gate 3.4 independently fetched the exact pinned object from
  `https://github.com/YI-TING-EE13/hermes-agent.git` and verified base tree
  `bda69c575e65725bf9264dd1288a63093cea3cc3`. The manifest records `VERIFIED`
  MIT license identity for `LICENSE`; `tools/verify_hermes_license.py` checks
  both the pinned Git blob and the checked-out file.
- `HERMES_DEPENDENCY_GOVERNANCE: TEAM_REMOTE_AND_SUBMODULE_VERIFIED`. The root
  gitlink stays at the pinned base while bootstrap applies patches `0001`–`0009`
  in the submodule worktree and verifies final tree
  `968f1668a05fafd09461c17a835198421f14a48f`. The clean-clone A/B acceptance is
  recorded in the Gate 3.4 section below.
- `hermes-agent/` is a formal external submodule, not TemiAgent root source or
  vendored source. The root `hermes-skills/` directory remains a reviewable
  mirror; resident Hermes reads the patched submodule skill paths. No manual
  copy is used.
- Gate 3.3 changed-bootstrap reachability is Hermes-only:
  `scripts/bootstrap_hermes.sh` invokes the new bounded-process and Hermes license
  tools, while `scripts/bootstrap_llama_cpp.sh` remains independent and invokes neither.
  `LLAMA_REGRESSION_REQUIRED: NO` for Gate 3.4 because no llama reconstruction
  path or shared bootstrap helper changed. Gate 3.3 evidence is carried forward:
  two independent final-candidate publication clones each passed first and second llama-only
  bootstraps with matching evidence: A and B both produced
  `HEAD=0b7154066e8544ed88d92ae2132cc1e055cf6304` and
  `TREE=1020a771795f406b8891d18ee607b4da3783fa7f`, with clean roots.
- `third_party/llama_cpp/` holds the manifest and README; bootstrap materializes
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
5. The Hermes team remote and formal submodule contract are verified from Gate
   3.4. <code>release/github-v1</code> already contains the adopted Gate 3
   dependency chain at <code>d66a046395aed21712b00cba43d4ea1b2d9f23de</code>.
   Gate 4 adds a separate documentation candidate; no root publication push is
   performed here.

## Documentation authority

Use the root [README](../README.md), this status page, the
[repository map](REPOSITORY_MAP.md), [project overview](architecture/project_overview.md),
[contract traceability](architecture/contract_traceability.md) and the sole current
[Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md) in that order. The
[quick reference](operations/DEMO_QUICK_REFERENCE.md) is a compact companion, not
a second lifecycle authority. Dated, machine-specific and direct-service material
is explicitly marked legacy in the documentation index and retained only as evidence.

For the current handover, start with [developer setup](operations/developer_setup.md),
[deployment handover](operations/demo_deployment_handover.md), [configuration
reference](operations/demo_configuration_reference.md), [verification and
acceptance](operations/verification_and_acceptance.md) and
[student handover](project/STUDENT_HANDOVER.md). The complete document
classification is in [DOCUMENT_AUTHORITY_MAP](DOCUMENT_AUTHORITY_MAP.md).

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

The bootstrap row above is historical Gate 1B evidence and does not replace the
fresh Gate 3.4 Hermes evidence below.

## Gate 3.3 standards-remediation evidence

The following checks were run in the isolated candidate at
`43c0c7c18a4b119f807b5dd04ef197272e43bbdd` (before this documentation-only
evidence update). No Hermes public fetch, service operation, MQTT publish, or
full Gate 3 run was performed.

| Command or evidence | Result |
|---|---|
| `python3 -m py_compile tools/bounded_process.py tools/run_bounded_process.py tools/verify_hermes_license.py tools/tests/test_bounded_process.py tools/tests/test_hermes_license.py tools/tests/test_external_dependency_publication.py` | PASS |
| `python3 -m unittest tools.tests.test_bounded_process tools.tests.test_hermes_license tools.tests.test_external_dependency_publication tools.tests.test_validate_documentation` | PASS; 15 tests |
| `python3 tools/validate_documentation.py` | PASS; 71 first-party Markdown files and 8 schema mappings |
| `bash -n scripts/bootstrap scripts/bootstrap_hermes.sh scripts/bootstrap_llama_cpp.sh` | PASS |
| `git diff --check 2efcd7bc2668dafcbccc5461b9bc4ac275a2606d..HEAD` | PASS |
| Private-LAN, private-path/embedded-URL, secret, generated-source, pose-path/blob and large-object scans | PASS; 0 private-LAN defaults, no current pose path/blob, no tracked generated checkouts, no blobs >= 50 MiB |
| `python3 -m unittest discover -s tools/tests` | BLOCKED; 119/120 tests completed, one pre-existing production-doctor fixture requires the intentionally absent generated `hermes-agent/` checkout; the Gate 3.3 focused matrix above is green |
| Two independent `git clone --no-local` publication clones, each running `./scripts/bootstrap --llama-cpp` twice | PASS; both roots clean, llama HEAD `0b7154066e8544ed88d92ae2132cc1e055cf6304`, tree `1020a771795f406b8891d18ee607b4da3783fa7f` |

## Gate 3.4 formal Hermes submodule evidence

Gate 3.4 was executed from the exact clean Gate 3.3 candidate at
`6dae2429064c3af54af5b7004db9e1755412b2f1` in an isolated worktree. The team
remote, exact pinned object, pinned base tree and pinned MIT license were fetched
and independently verified before adoption:

| Contract | Result |
|---|---|
| Team remote `https://github.com/YI-TING-EE13/hermes-agent.git` reachable | PASS; `git ls-remote` returned `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` for `refs/heads/main`. |
| Pinned commit `a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` available from team remote | PASS |
| Pinned base tree | PASS; `bda69c575e65725bf9264dd1288a63093cea3cc3` |
| Pinned license | PASS; `LICENSE`, MIT, `Copyright (c) 2025 Nous Research`, verified Git blob and SHA-256. |
| Formal root submodule | PASS; `.gitmodules` and the `hermes-agent` gitlink use the team URL and pinned base commit; no floating branch. |
| Root-owned overlay | PASS; manifest order and SHA-256 values for patches `0001`–`0009` produce final tree `968f1668a05fafd09461c17a835198421f14a48f`. |

The canonical setup is one bounded submodule initialization followed by
`./scripts/bootstrap --hermes` (or `./scripts/bootstrap --sources` for the
combined source flow). Bootstrap verifies the formal submodule and license, then
applies the root-owned patches in the submodule worktree. It does not clone,
fetch, use the original upstream, use a local checkout, use a file URL or use
Git alternates. A second invocation is a final-tree verification no-op.

Two independent Fresh A/B root clones were created with `git clone --no-local`
from Gate 3.4 commit `551790e0553ce58490f2883b857cd246db20058c`. Each initialized
the submodule from the team remote with the documented bounded depth-1 command,
verified the same base commit/tree, reconstructed the nine patches, verified the
same final tree and license, ran the setup a second time, and found all required
Temi skills. A/B patch aggregate hash was
`d793be62374675de58c51d3a4d9d62753026ddb56a8410de57d92352b5462698`; both
submodules were clean and had no alternates. The generated local final commit
IDs differed, as expected; content identity did not drift.

The complete reconstructed-candidate command
`python3 -m unittest discover -s tools/tests` passed `133/133`. This includes
the lifecycle, external-dependency, Hermes license, formal-submodule, bootstrap,
skills, documentation, shell/compile, root hardware-free mock-E2E and media fake
checks. `git diff --check` passed. Gate 3.3's independent llama A/B evidence is
carried forward because Gate 3.4 changed no llama reconstruction path or shared
bootstrap helper; no runtime service, MQTT publish/subscribe, model inference,
Android operation or hardware operation was performed.

## Gate 4 disposition

Gate 3 external dependency reproducibility is closed PASS and its adopted chain
is at <code>release/github-v1=d66a046395aed21712b00cba43d4ea1b2d9f23de</code>.
Gate 4 leaves that ref unchanged and leaves the handover documentation in the
isolated candidate for maintainer review. Real Android, Temi, broker, model/GPU,
Discord and perception verification require their own authorized operational
gate. Gate 4 performed no service operation, MQTT publication or root push.
