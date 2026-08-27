# TemiAgent

TemiAgent 是以 Temi robot 為實體載具、Hermes Agent 為認知核心的 embodied AI 居家照護研究與 Demo 專案。Temi 提供語音、影像與硬體互動；Hermes 負責情境理解、照護記憶推理、Home-ESI 風險分類與行動規劃；HermesTemiBridge 驗證跨模組事件、路徑與行動後才發布 robot command。

本專案不是醫療器材、診斷系統或正式緊急通報服務。照護分級、異常偵測與 caregiver notification 均屬研究或 Demo 範圍，不能取代專業判斷、人工確認或既有緊急流程。

## Current Scope

| Capability | State | Evidence and limits |
|---|---|---|
| Legacy live route | LEGACY; LIVE_NOT_VERIFIED | `temi_backend/` 保留 legacy ASR、影像、local VLM 與 MQTT 相容路線；目前 Gate snapshot 只有硬體無關測試，歷史真機紀錄不是目前 live evidence。 |
| Canonical ASR route | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Overview adapter 產生 canonical ASR event，Bridge 驗證事件、路徑與 Hermes output 後發布 command；Temi Android live path 尚未驗證。 |
| Canonical media v1.1 Bridge route | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Bridge 與 fake Android 已驗證 play/control lifecycle；Android、Hermes video entry 與真機播放仍是外部驗收。 |
| Resident Hermes HTTP mode | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | `tools/hermes_resident_server.py` 提供 `/health` 與 `/invoke`；wrapper 與 mock route 可測，live provider/model 尚未驗證。 |
| Structured care memory | DEMO_ONLY; HARDWARE_FREE_VERIFIED | `memory/` 只保存已去識別的合成 fixture；runtime memory、production data 與正式病歷不在 publication scope。 |
| Continuous abnormal perception | EXPERIMENTAL; LIVE_NOT_VERIFIED | `anomaly_detection/` 可產生 abnormal event；模型結果未經醫療或安全認證，且 viewer 不得 dispatch hardware command。 |
| Immediate abnormal-care flow | IMPLEMENTED; HARDWARE_FREE_VERIFIED; LIVE_NOT_VERIFIED | Bridge validates an abnormal event, records one notification-stage receipt, invokes Resident Hermes, validates the resulting speak command, and persists a bounded follow-up episode. Real recipient delivery and real-device execution remain unverified. |

狀態標籤的意思是：`IMPLEMENTED` 代表程式已存在；`HARDWARE_FREE_VERIFIED` 只代表指定的
unit、mock 或 fake 路徑實際通過；`LIVE_NOT_VERIFIED` 代表本文件沒有宣稱目前有 live
listener、真機、GPU/model、Discord 或真實 perception evidence；`LEGACY` 與
`EXPERIMENTAL` 不屬於 canonical V1 主線。最新治理 snapshot 見
[`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md)。

異常 perception 的 notification、care-first TTS、timeout 與 escalation 都由 Bridge 擁有；
action viewer 不再直接發布 `cmd/request`、`cmd/result` 或 Discord webhook。Demo mock
receipt 不會聯絡任何收件者；真實 Discord 只有 HTTP 204 receipt 才可稱為 delivered。詳見
[immediate abnormal-care flow](docs/operations/immediate_abnormal_care_flow.md) 與
[contract traceability](docs/architecture/contract_traceability.md)。

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
| `hermes-agent/` | External nested Hermes runtime reconstructed from public base plus tracked patches | `tools/hermes_resident_server.py` for Temi Demo | [Bootstrap overlay](third_party/hermes/README.md) | Bootstrap and Bridge/resident integration checks |
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

The canonical Demo entry point is `./scripts/demo`. Its one default private
configuration is Git-ignored at `/TemiAgent/.runtime/demo/demo.env` and its
runtime root is `/TemiAgent/.runtime/demo`. The initializer creates both with
owner-only permissions and never asks for a Discord credential.

```bash
cd /TemiAgent
./scripts/bootstrap --sources
./scripts/bootstrap --check
./scripts/demo init-config
./scripts/demo doctor
./scripts/demo start
./scripts/demo status
./scripts/demo restart
./scripts/demo stop
```

The default `init-config` selects the safe `newcomer_mock` profile. Use
`./scripts/demo init-config --profile production --force` only for the reviewed
production profile. An explicit absolute `--config` remains available for a
separately owned custom deployment, but the lifecycle never searches or adopts
legacy `/tmp` configs.

```bash
cd /TemiAgent
./scripts/demo --config <PRIVATE_CONFIG_PATH> doctor
./scripts/demo --config <PRIVATE_CONFIG_PATH> start
./scripts/demo --config <PRIVATE_CONFIG_PATH> status
./scripts/demo --config <PRIVATE_CONFIG_PATH> stop
```

`start` and `stop` manage only services whose private config sets
`<SERVICE>_OWNERSHIP=managed`; external ownership is health-checked but never
stopped. The checked-in [resource manifest](config/demo_resources.json) lists
the logical media and skill assets. From a clean clone, run
`./scripts/bootstrap --sources` once to reconstruct the reviewed Hermes overlay
and the pinned optional llama.cpp source checkout from public upstream. Run
`./scripts/bootstrap --check` only after the documented dependency environments
have been provisioned. Neither command starts services or creates credentials.
The Hermes manifest and patch series provide technical reconstruction only;
`AGENTS.md` still requires a team-accessible Hermes fork or remote, the pinned
commit, a formal Git submodule URL and clean-clone submodule verification before
root publication or handover can be called ready.
`docker-compose.yml` is an optional secondary/development configuration; it is
not a parallel production entrypoint and is not the canonical lifecycle.

- Cross-module startup, health checks and debugging: [Temi integration runbook](docs/operations/temi_integration_runbook.md)
- Canonical current Demo lifecycle and real-device Media checks: [Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md)
- Current implementation, verification and blocker snapshot: [CURRENT_STATUS.md](docs/CURRENT_STATUS.md)
- High-density source and publication boundary: [REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md)
- Private configuration keys, ownership modes and feature-gate invariants: [Demo configuration reference](docs/operations/demo_configuration_reference.md)
- Symptom-driven diagnosis that preserves protected services: [Demo troubleshooting](docs/operations/demo_troubleshooting.md)
- Hardware-free and external acceptance boundaries: [Verification and acceptance guide](docs/operations/verification_and_acceptance.md)
- Fresh-clone, software-only newcomer acceptance: [Verification and acceptance guide](docs/operations/verification_and_acceptance.md#software-only-newcomer-acceptance)
- Deployment, configuration, ownership and handover: [Demo deployment handover](docs/operations/demo_deployment_handover.md)
- LM Studio headless operation: [LM Studio runbook](docs/operations/lmstudio_headless_3gpu_hdd_manual.md)
- Safe service targeting, rollback and incident evidence: [Safe service operations](docs/operations/safe_service_operations.md)
- First-year Demo execution: [Demo runbook](docs/operations/first_year_demo_runbook.md)
- Documentation index: [docs/README.md](docs/README.md)

Runbooks may contain environment-specific placeholders. Supply private IP addresses and secrets at runtime through environment variables or local ignored files; do not add them to reusable scripts or new committed documentation.

## Change Synchronization

- Contract changes MUST update the authoritative runtime definition, producers, consumers, tests, module README files, reader schema copies and operational notes together.
- Documentation-only changes MUST not redefine runtime behavior.
- Program changes MUST update the owning module README when commands, configuration, contracts, artifacts or limitations change.
- Files under `logs/`, `temi_shared/`, model caches, checkpoints, local datasets and non-synthetic care data MUST NOT enter Git.
- Commit, push, merge, release and deployment remain human maintainer decisions unless a task explicitly authorizes them.

## Known Limitations

- The Android App source is not maintained in this workspace; Android behavior requires separate source and real-device verification.
- The canonical topic strings are repeated across producer and consumer code rather than generated from one contract package.
- Several runbooks capture machine-specific Demo history. Treat observed values as evidence snapshots, not portable defaults.
- The root publication boundary retains only reviewed synthetic memory fixtures; runtime memory must remain outside Git. The historical HEAD contains a pose checkpoint, while the Gate 1A publication change removes that weight from the current index; source, version, license and redistribution status remain unresolved.
- No capability in this repository establishes medical-grade accuracy, guaranteed fall detection, real emergency notification or autonomous unsupervised care.
