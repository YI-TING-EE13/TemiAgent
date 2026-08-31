# TemiAgent

TemiAgent 是以 Temi robot 為實體載具、Hermes Agent 為認知核心的 embodied AI 居家照護研究與 Demo 專案。Temi 提供語音、影像與硬體互動；Hermes 負責情境理解、照護記憶推理、Home-ESI 風險分類與行動規劃；HermesTemiBridge 驗證跨模組事件、路徑與行動後才發布 robot command。

本專案不是醫療器材、診斷系統或正式緊急通報服務。照護分級、異常偵測與 caregiver notification 均屬研究或 Demo 範圍，不能取代專業判斷、人工確認或既有緊急流程。

## Publication and operator disposition

The public repository
`https://github.com/YI-TING-EE13/TemiAgent`, branch `main`, is the
publication authority. This documentation lineage follows the previous public
baseline `8fead49d66ab0a9d016a7dfe495b336146bbe957`, tree
`e5fa932b01cc1f885cd36023464a18f11bdf060a`, and includes the completed D2B
and D2B.2 documentation remediation. The root publication has no
`LICENSE` file: `ROOT_LICENSE_POLICY=NO_LICENSE`. Gate 5, Android provenance,
L4 and Gate 6 are `CLOSED_PASS` at their documented boundaries, and D2A is
`CLOSED_PASS` for the observed AI6 deployment.

The portable operator starting point is a clean clone of public `main`. The
protected canonical development workspace is the intentionally dirty
designated-container mount `/TemiAgent`; its host path is withheld from
publication docs and it must not be used as an operator workspace or source
fallback. The validated
`/opt/TemiAgent-operator` path and its private runtime state are
AI6-specific evidence, not portable defaults.

## Current Scope

| Capability | State | Evidence and limits |
|---|---|---|
| Legacy live route | LEGACY; LIVE_NOT_VERIFIED | `temi_backend/` 保留 legacy ASR、影像、local VLM 與 MQTT 相容路線；Gate 5 的 host acceptance 不替 legacy route 或歷史真機紀錄背書。 |
| Canonical ASR route | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Overview adapter 產生 canonical ASR event，Bridge 驗證事件、路徑與 Hermes output 後發布 command；Temi Android live path 尚未驗證。 |
| Canonical media v1.1 Bridge route | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Bridge 與 fake Android 已驗證 play/control lifecycle；Android、Hermes video entry 與真機播放仍是外部驗收。 |
| Resident Hermes HTTP mode | IMPLEMENTED; HARDWARE_FREE_VERIFIED; HOST_LIVE_VERIFIED; ANDROID_TEMI_NOT_VERIFIED | `tools/hermes_resident_server.py` 的 exact Gate 5 host contract 通過 L0–L3、L5；production LM remains external-only；broader Android/Temi behavior outside the exact L4 TTS route remains unverified。 |
| Gate 5 host runtime | CLOSED_PASS; HOST_LIVE_VERIFIED | Public `main` at the exact publication identity above is paired with bounded host evidence: external LM, reused MQTT, resident, Bridge and one bounded model request; this is not Android/Temi or portable-environment proof. |
| Structured care memory | DEMO_ONLY; HARDWARE_FREE_VERIFIED | `memory/` 只保存已去識別的合成 fixture；runtime memory、production data 與正式病歷不在 publication scope。 |
| Continuous abnormal perception | EXPERIMENTAL; LIVE_NOT_VERIFIED | `anomaly_detection/` 可產生 abnormal event；模型結果未經醫療或安全認證，且 viewer 不得 dispatch hardware command。 |
| Immediate abnormal-care flow | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Bridge validates an abnormal event, records one notification-stage receipt, invokes Resident Hermes, validates the resulting speak command, and persists a bounded follow-up episode. Real recipient delivery and real-device execution remain unverified. |
| L4 Android artifact provenance | CLOSED_PASS; EXACT_FINAL_ACCEPTED_ARTIFACT | LAB606 evidence identifies the installed Android APK as the accepted final 1.0.2 (3) artifact; the existing installation was accepted as-is. |
| L4 canonical Android/Temi TTS E2E | CLOSED_PASS; PHYSICAL_E2E_VERIFIED | The adopted post-reboot evidence proves one bounded canonical speak dispatch, terminal TTS callback, successful correlated result and rollback. Broader media, camera/microphone and general device behavior remain separate. |

狀態標籤的意思是：`IMPLEMENTED` 代表程式已存在；`HARDWARE_FREE_VERIFIED` 只代表指定的
unit、mock 或 fake 路徑實際通過；`HOST_LIVE_VERIFIED` 只代表 exact Gate 5 deployment
contract 在 designated host 通過，不代表未被明確驗收的 Android/Temi physical boundary、
viewer/GPU general acceptance、Discord 或 portable environment；`ANDROID_TEMI_NOT_VERIFIED`
代表 broader physical Android/Temi scope 尚未通過；`L4_ANDROID_PROVENANCE=CLOSED_PASS`
代表 APK provenance 已接受，而 `L4_ANDROID_TEMI_E2E=CLOSED_PASS` 僅代表 exact
canonical TTS route；`LIVE_NOT_VERIFIED` 代表該邊界沒有 current live claim；`LEGACY` 與
`EXPERIMENTAL` 不屬於 canonical V1 主線。最新治理 snapshot 見
[`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md)。

異常 perception 的 notification、care-first TTS、timeout 與 escalation 都由 Bridge 擁有；
action viewer 不再直接發布 `cmd/request`、`cmd/result` 或 Discord webhook。Demo mock
receipt 不會聯絡任何收件者；真實 Discord 只有 HTTP 204 receipt 才可稱為 delivered。詳見
[immediate abnormal-care flow](docs/operations/immediate_abnormal_care_flow.md) 與
[contract traceability](docs/architecture/contract_traceability.md)。

For a new maintainer, continue through
[CURRENT_STATUS](docs/CURRENT_STATUS.md),
[REPOSITORY_MAP](docs/REPOSITORY_MAP.md),
[developer setup](docs/operations/developer_setup.md) and
[STUDENT_HANDOVER](docs/project/STUDENT_HANDOVER.md). The complete document
authority inventory is [DOCUMENT_AUTHORITY_MAP](docs/DOCUMENT_AUTHORITY_MAP.md).
The current lifecycle and host responsibility contracts are the
[Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md) and
[deployment handover](docs/operations/demo_deployment_handover.md).

## Architecture

```text
Temi Android ASR/camera
  -> tools/temi_overview_adapter.py
  -> canonical ASR/perception events plus allowlisted paths
  -> HermesTemiBridge validation
  -> resident Hermes JSON-only reasoning
  -> HermesTemiBridge action validation and dispatch
  -> canonical MQTT command request
  -> Temi Android executor
  -> command result and Bridge trace
```

Dependency and safety rules:

- Hermes MUST return structured plans; Hermes MUST NOT publish MQTT or control hardware directly.
- Perception and analytics components MUST NOT become hardware dispatchers.
- Bridge owns event, path, Hermes-output and action validation for the canonical reasoning route.
- MQTT carries structured metadata and paths, not image binaries.
- Runtime schemas under `hermes_temi_bridge/schemas/` are authoritative. `docs/schemas/` contains synchronized reader copies with shorter filenames.
- High-frequency camera ingest, model inference, LLM reasoning and command dispatch remain separate stages.

The detailed module map and payload narrative are in [project_overview.md](docs/architecture/project_overview.md). The authoritative-source and consumer matrix is in [contract_traceability.md](docs/architecture/contract_traceability.md).

## Module Index

| Module | Responsibility | Entry point | README | Verification |
|---|---|---|---|---|
| `hermes_temi_bridge/` | Canonical safety boundary and command dispatcher | `hermes-temi-bridge` | [README](hermes_temi_bridge/README.md) | `uv run python -m unittest discover -s tests` |
| `hermes-agent/` | Formal Hermes submodule pinned to the team fork; bootstrap applies the tracked Temi overlay in its worktree | `tools/hermes_resident_server.py` for Temi Demo | [External dependency contract](third_party/hermes/README.md) | Submodule, bootstrap and Bridge/resident integration checks |
| `hermes-skills/` | Reviewable mirror of Temi-specific Hermes skills | `SKILL.md` files | [README](hermes-skills/README.md) | Mirror diff and skill validators |
| `temi_backend/` | Verified legacy ASR, video and VLM route | `uv run temi-backend` | [README](temi_backend/README.md) | `uv run pytest` |
| `anomaly_detection/` | Experimental stream viewer and abnormal-event producer | `temi_action_viewer.py` | [README](anomaly_detection/README.md) | Module tests or documented manual QA |
| `mqtt/` | Local Mosquitto configuration and topic index | `mosquitto.conf` | [README](mqtt/README.md) | Publish/subscribe smoke test |
| `temi_shared/` | Runtime image and event-artifact layout | writer/reader contract | [README](temi_shared/README.md) | Bridge path tests and mock event generator |
| `tools/` | Cross-module adapters, health probes and test runners | individual scripts | [README](tools/README.md) | Script-specific checks |
| `docs/` | Maintained architecture, operations, project and schema documents | `docs/README.md` | [Documentation index](docs/README.md) | Link, path and consistency checks |

`memory/` and `logs/` are runtime or Demo-data areas rather than independently deployed services. Their README files define data restrictions.

## Experimental and local-only areas

`local_inference/` and `sub2/` may exist in a development checkout, but they are
excluded from canonical V1 publication and are not required by `./scripts/demo`.
`local_inference/` is an opt-in DeepSeek/llama.cpp experiment on loopback port
`1235`; it is not part of the Temi/Hermes request path. `sub2/` is an isolated
emotion-recognition experiment and does not own the canonical MQTT or Bridge route.
Physical presence in a mounted workspace does not make either directory a canonical
module. Their local README, weights, caches and build products are not publication
evidence.

`.runtime/`, `logs/`, `temi_shared/`, model caches, downloaded weights, checkpoints
and recordings are runtime or external artifact boundaries. The generated
`anomaly_detection/third_party/llama.cpp/` checkout is reconstructed from its
manifest and is not root source. The optional `yolo26x-pose.pt` weight is an
external model asset with expected path/hash metadata only; its source, version,
license and redistribution restrictions still require maintainer confirmation.

## Container and Working Directory

All project edits, searches, tests, builds, runtime inspection and service operations MUST run inside the designated container:

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

Before changing the repository:

```bash
pwd
git rev-parse --show-toplevel
git status --short
```

Do not edit the mounted repository from the host. See [AGENTS.md](AGENTS.md) for the complete human and AI-agent collaboration policy.

## Verified Development Checks

These checks do not require the Temi robot or a long-running service:

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

Hardware, GPU, Discord and live-stream acceptance require their documented external dependencies. Do not report those paths as verified unless the corresponding check actually ran.

## Operations

The canonical Demo entry point is `./scripts/demo`. Operation begins in a
clean public-main clone inside the designated container. Provision the locked
Hermes environment and approved generated llama.cpp artifact using the
dependency documents before the readiness check; source bootstrap alone does
not create every owner-provisioned runtime dependency.

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
export REPO_ROOT=<clean-public-main-clone>
cd "$REPO_ROOT"
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --sources
(cd hermes-agent && ./setup-hermes.sh)
./scripts/bootstrap --check
./scripts/demo --config <PRIVATE_PRODUCTION_CONFIG> --json doctor
./scripts/demo --config <PRIVATE_PRODUCTION_CONFIG> start
./scripts/demo --config <PRIVATE_PRODUCTION_CONFIG> --json status
./scripts/demo --config <PRIVATE_PRODUCTION_CONFIG> stop
```

The Hermes setup command is owned by the reconstructed Hermes source and
creates the `hermes-agent/venv` layout checked by bootstrap. See
[third_party/hermes/README.md](third_party/hermes/README.md) for the
source-defined setup behavior. TemiAgent modules use their own project-local
`.venv` environments as described in [developer setup](docs/operations/developer_setup.md);
those layouts are not interchangeable.

The default `init-config` path is for the isolated `newcomer_mock` profile.
Production requires an owner-only private config outside the worktree. The
doctor may return rc0 with `BACKEND_NOT_READY` and zero required failures
before managed services or Android are present; that is not `DEMO_READY`.
After start, `DEMO_READY` or `BACKEND_READY_WAITING_ANDROID` is valid.
`start` and `stop` manage only positively owned services; external LM Studio
and an explicitly external MQTT broker are health-checked and preserved.
Never invoke `lms`, use broad process termination, adopt an unknown listener,
or operate Android/Temi to manufacture readiness.

The checked-in [resource manifest](config/demo_resources.json) lists logical
media and skill assets. Neither bootstrap command starts services or creates
credentials. See [third_party/hermes/README.md](third_party/hermes/README.md)
and [third_party/llama_cpp/README.md](third_party/llama_cpp/README.md) for
source pins, reconstruction, provisioning and no-fallback boundaries.
`docker-compose.yml` is an optional secondary/development configuration; it is
not a parallel production entrypoint or the canonical lifecycle.

- Cross-module startup, health checks and debugging: [Temi integration runbook](docs/operations/temi_integration_runbook.md)
- Canonical current Demo lifecycle and real-device Media checks: [Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md)
- Current implementation, verification and blocker snapshot: [CURRENT_STATUS.md](docs/CURRENT_STATUS.md)
- High-density source and publication boundary: [REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md)
- Private configuration keys, ownership modes and feature-gate invariants: [Demo configuration reference](docs/operations/demo_configuration_reference.md)
- Symptom-driven diagnosis that preserves protected services: [Demo troubleshooting](docs/operations/demo_troubleshooting.md)
- Hardware-free and external acceptance boundaries: [Verification and acceptance guide](docs/operations/verification_and_acceptance.md)
- Fresh-clone, software-only newcomer acceptance: [Verification and acceptance guide](docs/operations/verification_and_acceptance.md#software-only-newcomer-acceptance)
- Deployment, configuration, ownership and handover: [Demo deployment handover](docs/operations/demo_deployment_handover.md)
- New-student setup and environment contract: [Developer setup](docs/operations/developer_setup.md)
- Seventeen-question student handover and release routing: [STUDENT_HANDOVER](docs/project/STUDENT_HANDOVER.md)
- Complete document authority inventory: [DOCUMENT_AUTHORITY_MAP](docs/DOCUMENT_AUTHORITY_MAP.md)
- LM Studio external-provider notes: [LM Studio runbook](docs/operations/lmstudio_headless_3gpu_hdd_manual.md); production ownership/readiness is defined by the [Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md)
- Safe service targeting, rollback and incident evidence: [Safe service operations](docs/operations/safe_service_operations.md)
- Historical first-year Demo material: [Demo runbook](docs/operations/first_year_demo_runbook.md)
- Documentation index: [docs/README.md](docs/README.md)

Runbooks may contain environment-specific placeholders. Supply private IP addresses and secrets at runtime through environment variables or local ignored files; do not add them to reusable scripts or new committed documentation.

## Change Synchronization

- Contract changes MUST update the authoritative runtime definition, producers, consumers, tests, module README files, reader schema copies and operational notes together.
- Documentation-only changes MUST not redefine runtime behavior.
- Program changes MUST update the owning module README when commands, configuration, contracts, artifacts or limitations change.
- Files under `logs/`, `temi_shared/`, model caches, checkpoints, local datasets and non-synthetic care data MUST NOT enter Git.
- Commit, push, merge, release and deployment remain human maintainer decisions unless a task explicitly authorizes them.

## Known Limitations

- The Android App source is not maintained in this workspace. LAB606 provenance and the adopted L4.7B evidence accept the installed APK and one exact canonical TTS route; video/media playback, camera/microphone, general device behavior and other Android paths still require separate verification.
- The canonical topic strings are repeated across producer and consumer code rather than generated from one contract package.
- Several runbooks capture machine-specific Demo history. Treat observed values as evidence snapshots, not portable defaults.
- The root publication boundary retains only reviewed synthetic memory fixtures; runtime memory must remain outside Git. The historical HEAD contains a pose checkpoint, while the Gate 1A publication change removes that weight from the current index; source, version, license and redistribution status remain unresolved.
- No capability in this repository establishes medical-grade accuracy, guaranteed fall detection, real emergency notification or autonomous unsupervised care.
