# TemiAgent Documentation Index

最後審查日期：2026-07-31

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

## Canonical coverage map

Use this table to find the current source of explanation before consulting a dated
handover, planning record, or reference mirror. Runtime code and schemas remain
authoritative when any prose conflicts with them.

| Surface | Current document | Owner / verification boundary |
|---|---|---|
| Repository entry, scope, module map | [`README.md`](../README.md) | Root maintainers; hardware-free checks only unless recorded otherwise. |
| Data flow, module boundary and capability classification | [project overview](architecture/project_overview.md) | Architecture; sections 6–13 are historical planning material. |
| Cross-module topic, schema and update-together rule | [contract traceability](architecture/contract_traceability.md) | Bridge and contract owners; runtime schemas are authoritative. |
| Demo lifecycle and operator workflow | [Demo operator guide](operations/DEMO_OPERATOR_GUIDE.md) | Demo operator; `scripts/demo` is the only current lifecycle. |
| Private Demo configuration and ownership | [Demo configuration reference](operations/demo_configuration_reference.md) | Operator-supplied owner-only env; never commit values or credentials. |
| Incident diagnosis and recovery boundary | [Demo troubleshooting](operations/demo_troubleshooting.md) | Exact-PID investigation; no broad process control. |
| Test selection and acceptance claims | [Verification and acceptance](operations/verification_and_acceptance.md) | Maintainer; hardware, Android, GPU and Discord remain external gates. |
| Module commands and artifacts | Each module README in the root module index | Owning module; do not infer contracts from a README alone. |
| Hermes integration overlay | [`third_party/hermes/`](../third_party/hermes/README.md) and reconstructed `hermes-agent/README.TemiAgent.md` | Tracked manifest/patches; do not stage the generated nested gitlink. |

## Architecture

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [project_overview.md](architecture/project_overview.md) | Maintained mixed overview; historical plan sections labeled | Project architecture | Module map, canonical data flow and payload narrative. |
| [contract_traceability.md](architecture/contract_traceability.md) | Maintained | Bridge and contract owners | Authoritative source, producer, consumer, test and synchronization matrix. |
| [canonical_cross_service_contract.md](architecture/canonical_cross_service_contract.md) | Media Bridge runtime feature-gated; other integrations pending | Bridge contract owner | Identity, video and care-report topics, schemas, correlation, safety and migration. |
| [android_cross_service_contract.md](architecture/android_cross_service_contract.md) | Implementation handoff; Android verification pending | Bridge contract owner and Android owner | LAB606 Android parser, state, privacy and test requirements. |

## Operations

> `DEMO_QUICK_REFERENCE.md` 與 `demo_operations_runbook.md` 是
> `codex/demo-operations-v1` 的 reference mirror。current branch 的唯一 lifecycle 是
> `./scripts/demo`；請使用 `DEMO_OPERATOR_GUIDE.md` 與
> `demo_warm_start_runbook.md`，不要套用 reference mirror 的舊 config contract。

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [safe_service_operations.md](operations/safe_service_operations.md) | Maintained policy | All service owners | Exact PID/port targeting, rollback, restore, retention and incident evidence. |
| [DEMO_OPERATOR_GUIDE.md](operations/DEMO_OPERATOR_GUIDE.md) | Maintained, Demo-only | Demo operator | Canonical `scripts/demo` lifecycle, Media capability boundary and live observers. |
| [demo_configuration_reference.md](operations/demo_configuration_reference.md) | Maintained, Demo-only | Demo operator | Complete non-secret `config/demo.env.example` key groups, ownership and feature gates. |
| [demo_troubleshooting.md](operations/demo_troubleshooting.md) | Maintained, Demo-only | Demo operator | Symptom-to-evidence troubleshooting without unowned process or runtime-data changes. |
| [verification_and_acceptance.md](operations/verification_and_acceptance.md) | Maintained | Maintainers | Hardware-free checks, external acceptance gates and evidence vocabulary. |
| [demo_deployment_handover.md](operations/demo_deployment_handover.md) | Maintained, Demo-only | Demo operator | Bootstrap, private configuration, managed/external ownership, resource manifest and handover limits. |
| [demo_temporary_content_inventory_20260730.md](operations/demo_temporary_content_inventory_20260730.md) | Dated integration inventory | Demo maintainer | Retention-only classification of `/tmp/temiagent*` Demo artifacts and local archive policy. |
| [DEMO_QUICK_REFERENCE.md](operations/DEMO_QUICK_REFERENCE.md) | Maintained compact reference; Demo-only | Demo operator | Current canonical commands, status meanings and recovery first actions. |
| [demo_operations_runbook.md](operations/demo_operations_runbook.md) | Retained expert reference; Demo-only | Demo operator | Historical expert aliases and Android-evidence background; not the newcomer procedure. |
| [temi_integration_runbook.md](operations/temi_integration_runbook.md) | Maintained | Integration | Hardware-free through real-device integration sequence. |
| [lmstudio_headless_3gpu_hdd_manual.md](operations/lmstudio_headless_3gpu_hdd_manual.md) | Maintained, machine-dependent | LM Studio runtime | Headless model service startup, health and recovery. |
| [lmstudio_gpu_selection.md](operations/lmstudio_gpu_selection.md) | Experimental evidence | ML runtime | GPU selection observations; not a portable default. |
| [temi_streaming_manual.md](operations/temi_streaming_manual.md) | Maintained, environment-dependent | Temi streaming | Android/PC streaming deployment. |
| [temi_streaming_local_runbook.md](operations/temi_streaming_local_runbook.md) | Machine-specific evidence | Temi streaming | Local ADB, MQTT and WebSocket observations. |
| [temi_e2e_stack_validation_manual.md](operations/temi_e2e_stack_validation_manual.md) | Maintained, environment-dependent | Integration | Full-stack validation and evidence collection. |
| [demo_warm_start_runbook.md](operations/demo_warm_start_runbook.md) | Maintained, Demo-only | Demo operator | External runtime layout, exact-PID restart, health gates and real Temi Media evidence. |
| [first_year_demo_runbook.md](operations/first_year_demo_runbook.md) | Demo-only | Demo operator | Cross-module Demo startup and fallback. |
| [first_year_demo_e2e_operation_manual.md](operations/first_year_demo_e2e_operation_manual.md) | Demo-only | Demo operator | Detailed Demo and recording procedure. |

Machine-specific documents may record historical observations. New reusable commands SHOULD use environment variables or placeholders rather than private addresses and user-specific host paths.

## Project and Research Scope

| Document | Status | Owner | Purpose |
|---|---|---|---|
| [hermes_care_assistant_task_readme.md](project/hermes_care_assistant_task_readme.md) | Maintained Demo scope | Care assistant | Task scope and acceptance boundaries. |
| [hermes_care_assistant_handoff.md](project/hermes_care_assistant_handoff.md) | Handoff reference | Care assistant | Full cognitive-assistant context and limitations. |
| [continuous_vision_abnormal_behavior_handoff.md](project/continuous_vision_abnormal_behavior_handoff.md) | Experimental handoff | Anomaly detection | Streaming perception design and known gaps. |
| [first_year_demo_phase_tasks.md](project/first_year_demo_phase_tasks.md) | Planning record | Demo owner | P0–P5 task and artifact plan. |
| [first_year_demo_system_design_20260601.md](project/first_year_demo_system_design_20260601.md) | Dated design snapshot | Demo owner | Implemented state and decisions at the stated date. |
| [first_year_demo_scenario_script.md](project/first_year_demo_scenario_script.md) | Demo-only | Demo operator | Scenario narration and evidence mapping. |
| [first_year_demo_acceptance_checklist.md](project/first_year_demo_acceptance_checklist.md) | Demo-only checklist | Demo operator | Pre-Demo acceptance evidence. |
| [system_handover.md](project/system_handover.md) | Legacy handoff; verify against current module docs | Project | Broad historical handoff. |
| [p2_structured_memory_phase1_report_materials.md](project/p2_structured_memory_phase1_report_materials.md) | Dated report material | Care memory | Phase evidence. |
| [phase1_care_context_builder_read_path.md](project/phase1_care_context_builder_read_path.md) | Dated implementation note | Care memory | Context-builder read path. |
| [phase1_care_context_demo_package.md](project/phase1_care_context_demo_package.md) | Demo package | Care memory | Phase 1 Demo evidence. |

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
