# TemiAgent

TemiAgent 是以 Temi robot 為實體載具、Hermes Agent 為認知核心的 embodied AI 居家照護研究與 Demo 專案。Temi 提供語音、影像與硬體互動；Hermes 負責情境理解、照護記憶推理、Home-ESI 風險分類與行動規劃；HermesTemiBridge 驗證跨模組事件、路徑與行動後才發布 robot command。

本專案不是醫療器材、診斷系統或正式緊急通報服務。照護分級、異常偵測與 caregiver notification 均屬研究或 Demo 範圍，不能取代專業判斷、人工確認或既有緊急流程。

## Current Scope

| Capability | State | Evidence and limits |
|---|---|---|
| Legacy live route | Verified Demo route | `temi_backend/` 已用於 Temi ASR、影像、local VLM 與 MQTT action 閉環；保留作相容路線。 |
| Canonical ASR route | Implemented; hardware-free path verified | Overview adapter 產生 canonical ASR event，Bridge 驗證 Hermes output 後發布 command。 |
| Canonical media v1.1 Bridge route | Feature-gated; fake Android verified | Bridge 可建立 play/control request、消費 session lifecycle/result 並寫 trace；預設關閉，Android、Hermes video entry 與真機尚未驗證。 |
| Resident Hermes HTTP mode | Implemented; Demo route verified | `tools/hermes_resident_server.py` 提供 `/health` 與 `/invoke`；預設整合 port 為 `8765`。 |
| Structured care memory | Demo-only | `memory/` 只應保存合成 Demo 資料；不是病歷或正式個資儲存系統。 |
| Continuous abnormal perception | Experimental Demo | `anomaly_detection/` 可產生 abnormal event；模型結果未經醫療或安全認證。 |
| Immediate abnormal-care flow | Demo-only; hardware-free and isolated mock E2E verified | Bridge validates an abnormal event, records one notification-stage receipt, invokes Resident Hermes, validates the resulting speak command, and persists a bounded follow-up episode. Real recipient delivery still requires a separately authorized credential and real-device evidence. |

異常 perception 的 notification、care-first TTS、timeout 與 escalation 都由 Bridge 擁有；
action viewer 不再直接發布 `cmd/request`、`cmd/result` 或 Discord webhook。Demo mock
receipt 不會聯絡任何收件者；真實 Discord 只有 HTTP 204 receipt 才可稱為 delivered。詳見
[immediate abnormal-care flow](docs/operations/immediate_abnormal_care_flow.md) 與
[contract traceability](docs/architecture/contract_traceability.md)。

## Architecture

```text
Temi Android ASR and camera
  -> legacy MQTT and WebSocket input
  -> tools/temi_overview_adapter.py
  -> canonical ASR event plus allowlisted image paths
  -> HermesTemiBridge validation
  -> Hermes JSON-only reasoning
  -> HermesTemiBridge action validation
  -> canonical MQTT command
  -> Temi Android hardware execution
  -> command result and trace
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
| `hermes-agent/` | Hermes runtime and upstream code | `tools/hermes_resident_server.py` for Temi Demo | [Bootstrap overlay](third_party/hermes/README.md) | Bridge/resident integration checks |
| `hermes-skills/` | Reviewable mirror of Temi-specific Hermes skills | `SKILL.md` files | [README](hermes-skills/README.md) | Mirror diff and skill validators |
| `temi_backend/` | Verified legacy ASR, video and VLM route | `uv run temi-backend` | [README](temi_backend/README.md) | `uv run pytest` |
| `anomaly_detection/` | Experimental stream viewer and abnormal-event producer | `temi_action_viewer.py` | [README](anomaly_detection/README.md) | Module tests or documented manual QA |
| `mqtt/` | Local Mosquitto configuration and topic index | `mosquitto.conf` | [README](mqtt/README.md) | Publish/subscribe smoke test |
| `temi_shared/` | Runtime image and event-artifact layout | writer/reader contract | [README](temi_shared/README.md) | Bridge path tests and mock event generator |
| `tools/` | Cross-module adapters, health probes and test runners | individual scripts | [README](tools/README.md) | Script-specific checks |
| `docs/` | Maintained architecture, operations, project and schema documents | `docs/README.md` | [Documentation index](docs/README.md) | Link, path and consistency checks |

`memory/` and `logs/` are runtime or Demo-data areas rather than independently deployed services. Their README files define data restrictions.

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

The canonical Demo entry point is `./scripts/demo`. Create an owner-only
private env from [config/demo.env.example](config/demo.env.example), keep it
outside every Git worktree, and run the same lifecycle for start, health, and
stop:

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
`./scripts/bootstrap --hermes` once to reconstruct the reviewed local Hermes
overlay from public upstream and tracked patches. Run
`./scripts/bootstrap --check` only after the documented dependency environments
have been provisioned. Neither command starts services or creates credentials.

- Cross-module startup, health checks and debugging: [Temi integration runbook](docs/operations/temi_integration_runbook.md)
- Canonical current Demo lifecycle and real-device Media checks: [Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md)
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
- The repository currently tracks some synthetic memory outputs and a model checkpoint. Removing or relocating tracked artifacts requires a separately reviewed migration.
- No capability in this repository establishes medical-grade accuracy, guaranteed fall detection, real emergency notification or autonomous unsupervised care.
