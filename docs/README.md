# TemiAgent Documentation Index

最後審查日期：2026-08-29

## Gate 5 and L4 final evidence handover entry points

Gate 5 host runtime acceptance is closed with the adopted Retry #4 evidence.
The current claim is bounded to the exact publication/runtime contract recorded
in [CURRENT_STATUS](CURRENT_STATUS.md); LAB606 has closed Android artifact
provenance and the adopted L4.7B record closes the exact canonical TTS
physical boundary. Broader Android/media behavior and Gate 6 functionality
remain outside that acceptance; Gate 6 is ready for release/handover work.

For a new student, use this short path rather than browsing the full document
inventory:

1. [CURRENT_STATUS](CURRENT_STATUS.md)
2. [REPOSITORY_MAP](REPOSITORY_MAP.md)
3. [Developer setup](operations/developer_setup.md)
4. [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md)
5. [Deployment handover](operations/demo_deployment_handover.md)
6. [Configuration reference](operations/demo_configuration_reference.md)
7. [Verification and acceptance](operations/verification_and_acceptance.md)
8. [Troubleshooting](operations/demo_troubleshooting.md)
9. [Student handover](project/STUDENT_HANDOVER.md)

[DOCUMENT_AUTHORITY_MAP.md](DOCUMENT_AUTHORITY_MAP.md) is the complete
classification inventory. It records one current prose authority per major
topic and identifies supplemental, historical and legacy material.

`docs/` 保存跨模組架構、契約、操作流程、專案範圍與 reader-facing schema。模組自己的執行、設定與測試方式應留在該模組 README。

## Classification

```text
docs/
  architecture/   architecture, data flow, boundaries and contracts
  operations/     startup, shutdown, health, debugging, recovery and runbooks
  project/        project scope, research context, handoff and Demo definition
  schemas/        human-readable copies of runtime schemas
  archive/        superseded documents retained for reference
```

Runtime-owned schemas under `hermes_temi_bridge/schemas/` remain authoritative. `docs/schemas/` is not an independent contract source.

## Reading order and status labels

New maintainers should read these documents in order: root [`README.md`](../README.md),
[`CURRENT_STATUS.md`](CURRENT_STATUS.md), [project overview](architecture/project_overview.md),
[contract traceability](architecture/contract_traceability.md), bootstrap and configuration
references, the [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md), verification and
troubleshooting, module READMEs, then legacy or experimental references.

`CURRENT` is the maintained source for a topic. `HARDWARE_FREE_VERIFIED` means that the
specified unit, mock or fake path actually passed; it does not prove a live device or
external service. `HOST_LIVE_VERIFIED` means that the exact bounded Gate 5 host contract passed,
without proving unrelated Android/Temi physical boundaries, general GPU/viewer
readiness or portable environment reproducibility. `L4_ANDROID_TEMI_E2E=CLOSED_PASS`
is limited to the one adopted canonical TTS transaction. `LIVE_NOT_VERIFIED` means that no current live claim
is made for that boundary. `LEGACY`
means retained for history or compatibility and not a current procedure. `EXPERIMENTAL`
means opt-in, non-canonical work.

## Authority hierarchy

1. **Current entrypoint:** root `README.md` and the five primary `scripts/demo` lifecycle operations; the parser also exposes setup, compatibility and feature selectors documented in the operator guide.
2. **Current authoritative detail:** runtime schemas, executable validators, lifecycle code
   and owning service configuration; prose cannot override them.
3. **Current module references:** module READMEs, `CURRENT_STATUS.md`, `REPOSITORY_MAP.md`
   and the current operator/integration supplements.
4. **Historical / legacy references:** dated, direct-service, machine-specific runbooks and
   handovers retained for evidence with the exact legacy notice; they are not current commands.
5. **Experimental / non-canonical references:** opt-in local inference, optional perception
   and research material; physical presence does not create canonical ownership.

## Canonical coverage map

Use this table to find the current source of explanation before consulting a dated
handover, planning record, or reference mirror. Runtime code and schemas remain
authoritative when any prose conflicts with them.

| Surface | Current document | Owner / verification boundary |
|---|---|---|
| Repository entry, scope, module map | [`README.md`](../README.md) | Root maintainers; hardware-free checks only unless recorded otherwise. |
| Current implementation, verification and release blockers | [CURRENT_STATUS.md](CURRENT_STATUS.md) | Maintainer snapshot; includes adopted Gate 5 host evidence, closed L4 artifact provenance and exact canonical TTS E2E, plus remaining Android/media/Gate 6 boundaries. |
| Repository layout and publication boundary | [REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Maintainer map; physical presence is not canonical ownership. |
| Data flow, module boundary and capability classification | [project overview](architecture/project_overview.md) | Architecture; sections 6–13 are historical planning material. |
| Cross-module topic, schema and update-together rule | [contract traceability](architecture/contract_traceability.md) | Bridge and contract owners; runtime schemas are authoritative. |
| Demo lifecycle and operator workflow | [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md) | Demo operator; `scripts/demo` is the only current lifecycle. |
| Private Demo configuration and ownership | [Demo configuration reference](operations/demo_configuration_reference.md) | Canonical ignored owner-only `.runtime/demo/demo.env`, initializer, production and isolated `newcomer_mock` profiles; never commit values or credentials. |
| Incident diagnosis and recovery boundary | [Demo troubleshooting](operations/demo_troubleshooting.md) | Exact-PID investigation; no broad process control. |
| Test selection and acceptance claims | [Verification and acceptance](operations/verification_and_acceptance.md) | Maintainer; includes adopted Gate 5 host evidence, Android provenance and one closed canonical TTS E2E. Media/camera, viewer/GPU general and Discord remain separate external gates. |
| Bridge-owned abnormal alert, follow-up, and Demo injection | [Immediate abnormal-care flow](operations/immediate_abnormal_care_flow.md) | Bridge owner; formal injector is synthetic-only and real Discord remains an authorization-gated external path. |
| Module commands and artifacts | Each module README in the root module index | Owning module; do not infer contracts from a README alone. |
| External source bootstrap | [`third_party/hermes/`](../third_party/hermes/README.md) and [`third_party/llama_cpp/`](../third_party/llama_cpp/README.md) | Hermes is a formal team-remote submodule plus root-owned patches; llama.cpp remains an ignored generated checkout reconstructed from its manifest. |
| Final Demo release reconciliation | [2026-07-31 consolidation record](project/final_demo_release_consolidation_20260731.md) | Release owner; retained worktree commits, owner disposition, and clean-clone delivery boundary. |

## Architecture

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [project_overview.md](architecture/project_overview.md) | Maintained mixed overview; historical plan sections labeled | Project architecture | Module map, canonical data flow and payload narrative. |
| [contract_traceability.md](architecture/contract_traceability.md) | Maintained | Bridge and contract owners | Authoritative source, producer, consumer, test and synchronization matrix. |
| [canonical_cross_service_contract.md](architecture/canonical_cross_service_contract.md) | Media Bridge runtime feature-gated; other integrations pending | Bridge contract owner | Identity, video and care-report topics, schemas, correlation, safety and migration. |
| [android_cross_service_contract.md](architecture/android_cross_service_contract.md) | Implementation handoff; artifact provenance and exact TTS E2E CLOSED_PASS; media E2E pending | Bridge contract owner and Android owner | LAB606 Android parser, state, privacy and test requirements. |

## Operations

> `DEMO_OPERATOR_GUIDE.md` is the sole current Demo lifecycle authority.
> `DEMO_QUICK_REFERENCE.md` is its compact companion. The warm-start and
> integration runbooks are supplemental procedures, not second lifecycle
> contracts. Direct-service, dated and machine-specific documents retain
> historical evidence and must not be used as the current operator workflow.

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [developer_setup.md](operations/developer_setup.md) | CURRENT authority | Maintainers | Ordered clean-clone setup, environment matrix, external artifacts and pin gaps. |
| [safe_service_operations.md](operations/safe_service_operations.md) | Maintained policy | All service owners | Exact PID/port targeting, rollback, restore, retention and incident evidence. |
| [DEMO_OPERATOR_GUIDE.md](operations/DEMO_OPERATOR_GUIDE.md) | CURRENT; Demo-only | Demo operator | Sole canonical `scripts/demo` lifecycle, bootstrap/check, logs, failures, Media boundary and live observers. |
| [demo_configuration_reference.md](operations/demo_configuration_reference.md) | Maintained, Demo-only | Demo operator | Complete non-secret `config/demo.env.example` key groups, ownership and feature gates. |
| [demo_troubleshooting.md](operations/demo_troubleshooting.md) | Maintained, Demo-only | Demo operator | Symptom-to-evidence troubleshooting without unowned process or runtime-data changes. |
| [verification_and_acceptance.md](operations/verification_and_acceptance.md) | Maintained | Maintainers | Hardware-free checks, external acceptance gates and evidence vocabulary. |
| [demo_deployment_handover.md](operations/demo_deployment_handover.md) | Maintained, Demo-only | Demo operator | Bootstrap, private configuration, managed/external ownership, resource manifest and handover limits. |
| [demo_temporary_content_inventory_20260730.md](operations/demo_temporary_content_inventory_20260730.md) | Dated integration inventory | Demo maintainer | Retention-only classification of `/tmp/temiagent*` Demo artifacts and local archive policy. |
| [DEMO_QUICK_REFERENCE.md](operations/DEMO_QUICK_REFERENCE.md) | CURRENT companion; Demo-only | Demo operator | Compact copy of current commands, status meanings and recovery first actions; not a second authority. |
| [demo_operations_runbook.md](operations/demo_operations_runbook.md) | LEGACY reference; Demo-only | Demo operator | Retained expert aliases and Android-evidence background; explicit legacy notice, not a current procedure. |
| [temi_integration_runbook.md](operations/temi_integration_runbook.md) | CURRENT supplemental | Integration | Hardware-free integration checks and external acceptance boundaries; no lifecycle ownership. |
| [lmstudio_headless_3gpu_hdd_manual.md](operations/lmstudio_headless_3gpu_hdd_manual.md) | Supplemental historical, machine-dependent | LM Studio runtime | Historical provider notes only; production ownership/readiness is defined by the current operator guide. |
| [lmstudio_gpu_selection.md](operations/lmstudio_gpu_selection.md) | Experimental evidence | ML runtime | GPU selection observations; not a portable default. |
| [temi_streaming_manual.md](operations/temi_streaming_manual.md) | LEGACY external-Android reference | Temi streaming | Historical Android build, ADB and streaming procedure; not the current lifecycle. |
| [temi_streaming_local_runbook.md](operations/temi_streaming_local_runbook.md) | LEGACY machine-specific reference | Temi streaming | Local ADB, MQTT and WebSocket observations; historical evidence only. |
| [temi_e2e_stack_validation_manual.md](operations/temi_e2e_stack_validation_manual.md) | LEGACY direct-service reference | Integration | Superseded full-stack restart script and manual service commands. |
| [demo_warm_start_runbook.md](operations/demo_warm_start_runbook.md) | CURRENT supplemental; Demo-only | Demo operator | External runtime layout, exact-PID restart, health gates and real Temi Media evidence; not a second lifecycle authority. |
| [first_year_demo_runbook.md](operations/first_year_demo_runbook.md) | LEGACY Demo reference | Demo operator | Dated first-year scenario startup and fallback. |
| [first_year_demo_e2e_operation_manual.md](operations/first_year_demo_e2e_operation_manual.md) | LEGACY Demo reference | Demo operator | Dated detailed Demo and recording procedure. |

Machine-specific documents may record historical observations. New reusable commands SHOULD use environment variables or placeholders rather than private addresses and user-specific host paths.

## Project and Research Scope

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [STUDENT_HANDOVER.md](project/STUDENT_HANDOVER.md) | CURRENT authority | Maintainers | New-student reading order, 40-question handover matrix and release handover. |
| [hermes_care_assistant_task_readme.md](project/hermes_care_assistant_task_readme.md) | Maintained Demo scope | Care assistant | Task scope and acceptance boundaries. |
| [hermes_care_assistant_handoff.md](project/hermes_care_assistant_handoff.md) | Handoff reference | Care assistant | Full cognitive-assistant context and limitations. |
| [continuous_vision_abnormal_behavior_handoff.md](project/continuous_vision_abnormal_behavior_handoff.md) | Experimental handoff | Anomaly detection | Streaming perception design and known gaps. |
| [first_year_demo_phase_tasks.md](project/first_year_demo_phase_tasks.md) | Planning record | Demo owner | P0–P5 task and artifact plan. |
| [first_year_demo_system_design_20260601.md](project/first_year_demo_system_design_20260601.md) | Dated design snapshot | Demo owner | Implemented state and decisions at the stated date. |
| [first_year_demo_scenario_script.md](project/first_year_demo_scenario_script.md) | Demo-only | Demo operator | Scenario narration and evidence mapping. |
| [first_year_demo_acceptance_checklist.md](project/first_year_demo_acceptance_checklist.md) | Demo-only checklist | Demo operator | Pre-Demo acceptance evidence. |
| [system_handover.md](project/system_handover.md) | LEGACY handoff; verify against current module docs | Project | Broad historical handoff; current handover starts from `CURRENT_STATUS.md` and the current operator guide. |
| [p2_structured_memory_phase1_report_materials.md](project/p2_structured_memory_phase1_report_materials.md) | Dated report material | Care memory | Phase evidence. |
| [phase1_care_context_builder_read_path.md](project/phase1_care_context_builder_read_path.md) | Dated implementation note | Care memory | Context-builder read path. |
| [phase1_care_context_demo_package.md](project/phase1_care_context_demo_package.md) | Demo package | Care memory | Phase 1 Demo evidence. |

## Repository and publication boundary

[`REPOSITORY_MAP.md`](REPOSITORY_MAP.md) is the high-density source and ownership map;
[`CURRENT_STATUS.md`](CURRENT_STATUS.md) is the dated implementation, verification and
release-blocker snapshot. Together they explain what belongs to canonical V1, what is
external or generated, and what is local runtime state.

The publication boundary includes reviewed source, contracts, tests, configuration
templates and synthetic fixtures. It excludes real care or user data, runtime logs and
images, credentials, model caches, downloaded weights, recordings, and owner-only
`.runtime/` state. Models are not implied by a clean clone. `third_party/hermes/`
records the original upstream, team remote, formal submodule pin, license
identity and root-owned patch series. `hermes-agent/` is the external submodule
worktree rather than TemiAgent root source; `third_party/llama_cpp/` still
describes an ignored generated checkout. `計劃書/` is research/reference
material, not runtime source.

For Hermes, initialize the root submodule from the team remote and run the
documented bootstrap to apply patches `0001`–`0010`. The final patched tree is
verified by content identity; generated local submodule commit IDs are not
dependency authority. If the team remote is unavailable, stop without falling
back to the original upstream, a local checkout, a file URL or Git alternates.

## Schemas

| Reader copy | Authoritative runtime schema | Status |
|---|---|---|
| [asr_final_event.schema.json](schemas/asr_final_event.schema.json) | `hermes_temi_bridge/schemas/asr_final_event.schema.json` | Synchronized |
| [hermes_output.schema.json](schemas/hermes_output.schema.json) | `hermes_temi_bridge/schemas/hermes_action_output.schema.json` | Synchronized |
| [command_request.schema.json](schemas/command_request.schema.json) | `hermes_temi_bridge/schemas/temi_command_request.schema.json` | Synchronized |
| [command_result.schema.json](schemas/command_result.schema.json) | `hermes_temi_bridge/schemas/temi_command_result.schema.json` | Synchronized |

Any schema change MUST update both mapped files, producers, consumers, tests and related README/runbook content in the same change.

## Archive

`archive/` retains superseded material. Every archived document SHOULD identify its replacement. Do not use archived instructions for current operation without checking the maintained index.

## Maintenance Rules

- Add a document only when it has a clear owner and durable responsibility.
- Move cross-module procedures to `operations/`; keep module-only commands in module README files.
- Mark implemented, verified, unverified, Demo-only, planned, deprecated and archived states explicitly.
- After a move or rename, use `rg` to remove stale paths.
- Validate relative links, code fences, reader schema copies and the documentation index before handoff.
