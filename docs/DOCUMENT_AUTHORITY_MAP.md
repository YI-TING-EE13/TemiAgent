# TemiAgent Document Authority Map

Status: `CURRENT_AUTHORITY`; D2B consolidated on 2026-08-31.

This ledger is the one-file inventory for every retained tracked Markdown
document. Runtime code, runtime JSON schemas, manifests and lockfiles remain
authoritative for executable behavior; prose cannot override them.

`DOCUMENT_COUNT_BEFORE=74`
`DOCUMENT_COUNT_AFTER=73`
`AGENT_MD_ACTION=DELETED_AFTER_REFERENCE_SCAN_FULLY_SUBSUMED_BY_AGENTS_AND_CURRENT_DOCS`
`UNJUSTIFIED_RETAINED_DOCUMENT_COUNT=0`
`CURRENT_DOCUMENT_CONTRADICTIONS=0`

The removed `Agent.md` was an obsolete duplicate entry point. A repository-wide
reference scan found no current inbound dependency that was not already covered
by `AGENTS.md` and the current documentation set. No other document was
deleted, and historical evidence was not rewritten into a current procedure.

## Publication and workspace identity

The public repository's `main` branch is the publication authority. This
documentation lineage follows the previous public baseline
`8fead49d66ab0a9d016a7dfe495b336146bbe957` and tree
`e5fa932b01cc1f885cd36023464a18f11bdf060a`, and records the completed D2B
and D2B.2 documentation remediation. The root publication has no
`LICENSE` file: `ROOT_LICENSE_POLICY=NO_LICENSE`.

The portable operator begins from a clean public-main clone. The protected
canonical development checkout is the intentionally dirty designated-container
mount `/TemiAgent`; its host path is withheld from publication docs and it is
not an operator workspace.
`/opt/TemiAgent-operator` is the observed
`VALIDATED_AI6_OPERATOR_WORKSPACE` from D2A, with private runtime state below
`/opt/TemiAgent-operator/.runtime/demo`. Those absolute paths, PIDs, generated
artifacts and runtime directories are evidence, not portable defaults.

Gate 5, Android provenance, L4, Gate 6 and D2A are `CLOSED_PASS` at their
documented boundaries. D2B is documentation-only and performs no lifecycle,
model, MQTT, Android, Temi, notification or source-runtime operation.

## Status vocabulary and routing rules

| Status | Retention meaning |
|---|---|
| `CURRENT_AUTHORITY` | Maintained prose authority for the named topic. The executable owner or runtime schema still wins on behavior. |
| `CURRENT_REFERENCE` | Maintained supplemental explanation, contract, skill or research reference. It must link back to the relevant authority and cannot define a second operator lifecycle. |
| `HISTORICAL` | Dated evidence, planning, release or research material retained for provenance. It is not a current procedure. |
| `SUPERSEDED` | Legacy procedure or handover retained for traceability. Its top banner must say `DO NOT USE AS CURRENT OPERATOR PROCEDURE` and point to the replacement. |

There is one current operator primary: `docs/operations/DEMO_OPERATOR_GUIDE.md`.
The current newcomer route is clean public-main clone → identity/source
verification → dependency provisioning and reconstruction →
`./scripts/bootstrap --check` → read-only JSON `doctor` with zero required
failures → one authorized `start → status → stop`. A pre-start
`BACKEND_NOT_READY` with zero required failures is not `DEMO_READY`.
Production LM Studio is external-only; an explicitly external MQTT broker is
health-checked and preserved. Do not use `lms`, broad process termination,
canonical dirty-worktree fallback or unknown listener adoption.

## Topic authority map

| Topic | Primary authority | Supporting references |
|---|---|---|
| Repository scope and public publication | `README.md` | `docs/REPOSITORY_MAP.md` and `docs/CURRENT_STATUS.md` |
| Governance and contributor boundary | `AGENTS.md` | Current module READMEs |
| Current implementation and gate state | `docs/CURRENT_STATUS.md` | `docs/operations/verification_and_acceptance.md` |
| Architecture and module ownership | `docs/architecture/project_overview.md` | `docs/architecture/contract_traceability.md` |
| Cross-module contracts | Runtime schemas and `docs/architecture/contract_traceability.md` | Architecture contract supplements |
| Current Demo lifecycle | `docs/operations/DEMO_OPERATOR_GUIDE.md` | `DEMO_QUICK_REFERENCE.md` and troubleshooting |
| Configuration and ownership | `docs/operations/demo_configuration_reference.md` | Source parser and module READMEs |
| Setup and dependencies | `docs/operations/developer_setup.md` | Third-party dependency READMEs |
| Deployment handover | `docs/operations/demo_deployment_handover.md` | Operator guide and current status |
| Exact-PID service policy | `docs/operations/safe_service_operations.md` | Operator guide and troubleshooting |
| Verification claims | `docs/operations/verification_and_acceptance.md` | Current status and test owners |
| Student handover | `docs/project/STUDENT_HANDOVER.md` | Developer setup and operator guide |
| Hermes source and patched environment | `third_party/hermes/README.md` plus manifest and verifier | Developer setup and bootstrap scripts |
| llama.cpp source and generated build | `third_party/llama_cpp/README.md` plus manifest | Developer setup and operator guide |
| Module-local behavior | The owning module README and executable code | Root/docs references must not create a duplicate runtime contract |

## Complete retained-document ledger

Every retained tracked Markdown file appears exactly once below. The
`PRIMARY_AUTHORITY_FOR` column identifies the topic owned by the file; a dash
means the file is supplemental or historical rather than an authority.

| PATH | STATUS | ROLE | AUDIENCE | PRIMARY_AUTHORITY_FOR | SUPERSEDED_BY | HISTORICAL_DATE_IF_APPLICABLE | WHY_THIS_FILE_EXISTS | RETENTION |
|---|---|---|---|---|---|---|---|---|
| `計劃書/README.md` | `HISTORICAL` | Research index | Researchers | — | `docs/README.md` | Dated research material | Preserves the original planning context and links. | Historical evidence |
| `計劃書/子計畫三_分年工作項目整理.md` | `HISTORICAL` | Work-plan record | Researchers | — | `docs/CURRENT_STATUS.md` | Dated research material | Preserves the year-by-year planning record. | Historical evidence |
| `.hermes.md` | `CURRENT_REFERENCE` | Runtime context prompt | Hermes maintainers | Temi runtime context and capability limits | — | — | Supplies bounded cognitive-context guidance without expanding capability. | Current supplemental |
| `AGENTS.md` | `CURRENT_AUTHORITY` | Governance guide | Contributors and agents | Repository safety, ownership and verification rules | — | — | Defines the mandatory collaboration and preservation boundary. | Current authority |
| `README.md` | `CURRENT_AUTHORITY` | Repository entry point | All maintainers and students | Scope, architecture entry points and operator boundary | — | — | Gives the public-facing project orientation and links to authorities. | Current authority |
| `anomaly_detection/README.md` | `CURRENT_AUTHORITY` | Module README | Perception maintainers | Experimental viewer and perception-module behavior | — | — | Documents module contracts while deferring lifecycle ownership to `scripts/demo`. | Current authority |
| `docs/CURRENT_STATUS.md` | `CURRENT_AUTHORITY` | Status snapshot | Maintainers and reviewers | Current gates, evidence, blockers and portability | — | 2026-08-31 | Records accepted boundaries and remaining gaps without becoming a runtime endpoint. | Current authority |
| `docs/DOCUMENT_AUTHORITY_MAP.md` | `CURRENT_AUTHORITY` | Authority ledger | Maintainers and reviewers | Document inventory, status and routing | — | 2026-08-31 | Makes every retained document justified and routable. | Current authority |
| `docs/README.md` | `CURRENT_AUTHORITY` | Documentation index | All readers | Documentation taxonomy and reading order | — | 2026-08-31 | Provides the maintained index and authority hierarchy. | Current authority |
| `docs/REPOSITORY_MAP.md` | `CURRENT_AUTHORITY` | Repository and publication map | Maintainers and operators | Source layout, generated/external boundaries and publication identity | — | 2026-08-31 | Distinguishes canonical source, operator artifacts and external dependencies. | Current authority |
| `docs/architecture/android_cross_service_contract.md` | `CURRENT_REFERENCE` | Android integration contract | Bridge and Android owners | Android-side contract supplement | — | — | Preserves the external Android parser, state and acceptance handoff. | Current supplemental |
| `docs/architecture/canonical_cross_service_contract.md` | `CURRENT_REFERENCE` | Cross-service contract supplement | Bridge and integration owners | Media, identity and care contract design | — | — | Explains feature-gated cross-service contracts beside runtime schemas. | Current supplemental |
| `docs/architecture/contract_traceability.md` | `CURRENT_AUTHORITY` | Contract matrix | Contract owners | Producer, consumer, schema, test and synchronization ownership | — | — | Prevents prose-only contract drift and identifies update-together surfaces. | Current authority |
| `docs/architecture/project_overview.md` | `CURRENT_AUTHORITY` | Architecture overview | Maintainers and students | Module map, data flow and boundary narrative | — | — | Provides the maintained architecture map while labeling planning sections. | Current authority |
| `docs/operations/DEMO_OPERATOR_GUIDE.md` | `CURRENT_AUTHORITY` | Operator runbook | Authorized operators | Sole current `scripts/demo` lifecycle and readiness semantics | — | 2026-08-31 | Gives one executable, ownership-aware current operator procedure. | Current authority |
| `docs/operations/DEMO_QUICK_REFERENCE.md` | `CURRENT_REFERENCE` | Compact operator companion | Operators and students | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | 2026-08-31 | Gives the shortest current flow without creating a second authority. | Current supplemental |
| `docs/operations/demo_configuration_reference.md` | `CURRENT_AUTHORITY` | Configuration reference | Operators and maintainers | Complete non-secret key, ownership and feature-gate inventory | — | 2026-08-31 | Explains private configuration and readiness validation without secrets. | Current authority |
| `docs/operations/demo_deployment_handover.md` | `CURRENT_AUTHORITY` | Deployment handover | Operators and maintainers | Deployment topology, provisioning and ownership handoff | — | 2026-08-31 | Binds clean-clone setup to managed/external service responsibility. | Current authority |
| `docs/operations/demo_operations_runbook.md` | `SUPERSEDED` | Legacy operations runbook | Experienced maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated legacy runbook | Preserves expert aliases and earlier evidence for traceability. | Superseded reference |
| `docs/operations/demo_temporary_content_inventory_20260730.md` | `HISTORICAL` | Temporary-artifact inventory | Maintainers | — | `docs/DOCUMENT_AUTHORITY_MAP.md` | 2026-07-30 | Records retention decisions for old temporary Demo artifacts. | Historical evidence |
| `docs/operations/demo_troubleshooting.md` | `CURRENT_AUTHORITY` | Symptom-to-evidence guide | Operators and maintainers | Safe diagnosis and escalation | — | 2026-08-31 | Keeps troubleshooting read-only and exact-identity based. | Current authority |
| `docs/operations/demo_warm_start_runbook.md` | `CURRENT_REFERENCE` | Warm-start supplement | Authorized operators | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | — | Preserves detailed warm-start and real-device evidence boundaries. | Current supplemental |
| `docs/operations/developer_setup.md` | `CURRENT_AUTHORITY` | Clean-clone setup | New maintainers and students | Source, environment and dependency provisioning | — | 2026-08-31 | Defines the reproducible starting path and explicit pin gaps. | Current authority |
| `docs/operations/first_year_demo_e2e_operation_manual.md` | `SUPERSEDED` | Legacy E2E manual | Historical Demo operators | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | First-year Demo | Preserves a dated detailed execution record without current authority. | Superseded reference |
| `docs/operations/first_year_demo_runbook.md` | `SUPERSEDED` | Legacy Demo runbook | Historical Demo operators | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | First-year Demo | Preserves dated scenario startup and fallback material. | Superseded reference |
| `docs/operations/immediate_abnormal_care_flow.md` | `CURRENT_REFERENCE` | Feature-flow reference | Bridge and care maintainers | — | — | — | Explains the Bridge-owned abnormal-care route and notification boundary. | Current supplemental |
| `docs/operations/lmstudio_gpu_selection.md` | `CURRENT_REFERENCE` | Machine-specific GPU evidence | ML/runtime maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated machine evidence | Retains GPU observations while refusing portable defaults or provider control. | Current supplemental |
| `docs/operations/lmstudio_headless_3gpu_hdd_manual.md` | `CURRENT_REFERENCE` | Historical provider supplement | LM/runtime maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated machine procedure | Retains provider notes while current ownership remains external-only. | Current supplemental |
| `docs/operations/safe_service_operations.md` | `CURRENT_AUTHORITY` | Service safety policy | All operators | Exact-PID operation, rollback and evidence retention | — | — | Defines the common fail-closed process-operation policy. | Current authority |
| `docs/operations/temi_e2e_stack_validation_manual.md` | `SUPERSEDED` | Legacy direct-service manual | Historical integration maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated integration manual | Preserves the old direct-service validation record and its limitations. | Superseded reference |
| `docs/operations/temi_integration_runbook.md` | `CURRENT_REFERENCE` | Integration supplement | Integration maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | — | Covers hardware-free integration and external acceptance boundaries. | Current supplemental |
| `docs/operations/temi_streaming_local_runbook.md` | `SUPERSEDED` | Machine-specific streaming runbook | Historical integration maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated local runbook | Retains local ADB/MQTT/WebSocket observations without current commands. | Superseded reference |
| `docs/operations/temi_streaming_manual.md` | `SUPERSEDED` | Legacy streaming manual | Historical integration maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | Dated streaming manual | Retains the earlier Android streaming procedure for provenance. | Superseded reference |
| `docs/operations/verification_and_acceptance.md` | `CURRENT_AUTHORITY` | Verification guide | Maintainers and reviewers | Test matrix, evidence vocabulary and acceptance boundaries | — | 2026-08-31 | Separates executable software checks from external and physical acceptance. | Current authority |
| `docs/project/STUDENT_HANDOVER.md` | `CURRENT_AUTHORITY` | Student handover | New students and maintainers | Newcomer questions, reading order and safe lifecycle summary | — | 2026-08-31 | Gives a compact answer-first handoff aligned to the current publication. | Current authority |
| `docs/project/continuous_vision_abnormal_behavior_handoff.md` | `CURRENT_REFERENCE` | Experimental research handoff | Perception researchers | — | `anomaly_detection/README.md` | 2026-08-31 alignment; research content dated 2026-06-01 | Preserves continuous-vision design and known gaps without operator authority. | Current supplemental |
| `docs/project/final_demo_release_consolidation_20260731.md` | `HISTORICAL` | Release reconciliation record | Maintainers and reviewers | — | `docs/CURRENT_STATUS.md` | 2026-07-31 | Preserves release-candidate decisions and source-boundary evidence. | Historical evidence |
| `docs/project/first_year_demo_acceptance_checklist.md` | `HISTORICAL` | Dated acceptance checklist | Demo maintainers | — | `docs/operations/verification_and_acceptance.md` | First-year Demo | Preserves the earlier acceptance checklist and its scope. | Historical evidence |
| `docs/project/first_year_demo_phase_tasks.md` | `HISTORICAL` | Planning record | Project maintainers | — | `docs/CURRENT_STATUS.md` | First-year Demo | Preserves the P0–P5 task and artifact plan. | Historical evidence |
| `docs/project/first_year_demo_scenario_script.md` | `HISTORICAL` | Dated scenario script | Demo maintainers | — | `docs/operations/DEMO_OPERATOR_GUIDE.md` | First-year Demo | Preserves scenario narration and evidence mapping. | Historical evidence |
| `docs/project/first_year_demo_system_design_20260601.md` | `HISTORICAL` | Dated design snapshot | Project maintainers | — | `docs/architecture/project_overview.md` | 2026-06-01 | Preserves design decisions at the stated point in time. | Historical evidence |
| `docs/project/hermes_care_assistant_handoff.md` | `CURRENT_REFERENCE` | Care-assistant handoff | Hermes and care maintainers | — | `docs/CURRENT_STATUS.md` | — | Preserves cognitive context and care limitations for the current implementation. | Current supplemental |
| `docs/project/hermes_care_assistant_task_readme.md` | `CURRENT_REFERENCE` | Care-assistant task scope | Care maintainers | — | `docs/CURRENT_STATUS.md` | — | Records task scope, skills and acceptance boundaries. | Current supplemental |
| `docs/project/p2_structured_memory_phase1_report_materials.md` | `HISTORICAL` | Phase report material | Care-memory researchers | — | `memory/README.md` | Phase 1 | Preserves structured-memory report evidence and limitations. | Historical evidence |
| `docs/project/phase1_care_context_builder_read_path.md` | `HISTORICAL` | Implementation note | Care-memory maintainers | — | `memory/README.md` | Phase 1 | Preserves the earlier context-builder read-path analysis. | Historical evidence |
| `docs/project/phase1_care_context_demo_package.md` | `HISTORICAL` | Demo package record | Care-memory maintainers | — | `memory/README.md` | Phase 1 | Preserves phase-one Demo artifacts and acceptance context. | Historical evidence |
| `docs/project/system_handover.md` | `SUPERSEDED` | Legacy broad handover | Historical maintainers | — | `docs/project/STUDENT_HANDOVER.md` and current operator docs | Dated handover | Retains the broad historical handoff while routing current readers elsewhere. | Superseded reference |
| `hermes-skills/README.md` | `CURRENT_AUTHORITY` | Skills mirror index | Hermes and Bridge maintainers | Reviewable Temi skill mirror and synchronization boundary | — | — | Defines the reviewable skill mirror and its non-runtime ownership. | Current authority |
| `hermes-skills/temi-care-memory/SKILL.md` | `CURRENT_REFERENCE` | Hermes skill contract | Hermes maintainers | — | `hermes-agent/skills/temi-care-memory/SKILL.md` after reconstruction | — | Mirrors the care-memory skill for review and synchronization. | Current supplemental |
| `hermes-skills/temi-care-memory/references/structured_memory_contract.md` | `CURRENT_REFERENCE` | Skill reference contract | Hermes maintainers | — | `hermes-agent/skills/temi-care-memory/` after reconstruction | — | Explains the structured-memory input/output boundary. | Current supplemental |
| `hermes-skills/temi-demo-identity/SKILL.md` | `CURRENT_REFERENCE` | Demo identity skill | Hermes maintainers | — | `hermes-agent/skills/temi-demo-identity/SKILL.md` after reconstruction | — | Mirrors exact operator identity semantics for review. | Current supplemental |
| `hermes-skills/temi-demo-repeated-discomfort/SKILL.md` | `CURRENT_REFERENCE` | Demo care skill | Hermes maintainers | — | `hermes-agent/skills/temi-demo-repeated-discomfort/SKILL.md` after reconstruction | — | Mirrors the bounded synthetic repeated-discomfort flow. | Current supplemental |
| `hermes-skills/temi-discord-care-assistant/SKILL.md` | `CURRENT_REFERENCE` | Discord care skill | Hermes maintainers | — | `hermes-agent/skills/temi-discord-care-assistant/SKILL.md` after reconstruction | — | Mirrors the Discord care-assistant route and limits. | Current supplemental |
| `hermes-skills/temi-discord-care-assistant/references/discord_temi_context.md` | `CURRENT_REFERENCE` | Discord context reference | Hermes maintainers | — | `hermes-agent/skills/temi-discord-care-assistant/` after reconstruction | — | Provides the Temi-specific context used by the mirrored skill. | Current supplemental |
| `hermes-skills/temi-home-esi/SKILL.md` | `CURRENT_REFERENCE` | Home-ESI skill | Hermes maintainers | — | `hermes-agent/skills/temi-home-esi/SKILL.md` after reconstruction | — | Mirrors bounded Home-ESI classification guidance. | Current supplemental |
| `hermes-skills/temi-home-esi/references/home_esi_lite.md` | `CURRENT_REFERENCE` | Home-ESI reference | Hermes maintainers | — | `hermes-agent/skills/temi-home-esi/` after reconstruction | — | Defines the lite risk-category reference used by the skill. | Current supplemental |
| `hermes-skills/temi-robot-control/SKILL.md` | `CURRENT_REFERENCE` | Robot-control skill | Hermes maintainers | — | `hermes-agent/skills/temi-robot-control/SKILL.md` after reconstruction | — | Mirrors safe action-planning and hardware boundary guidance. | Current supplemental |
| `hermes-skills/temi-robot-control/references/examples.md` | `CURRENT_REFERENCE` | Skill examples | Hermes maintainers | — | `hermes-agent/skills/temi-robot-control/` after reconstruction | — | Provides reviewed examples without owning dispatch. | Current supplemental |
| `hermes-skills/temi-robot-control/references/mqtt_topics.md` | `CURRENT_REFERENCE` | MQTT topic reference | Hermes and Bridge maintainers | — | Runtime schemas and `hermes_temi_bridge/README.md` | — | Mirrors topic names for skill review; runtime contracts remain authoritative. | Current supplemental |
| `hermes-skills/temi-robot-control/references/safety_rules.md` | `CURRENT_REFERENCE` | Robot safety reference | Hermes maintainers | — | `AGENTS.md` and Bridge validators | — | Provides skill-level safety reminders without bypassing Bridge validation. | Current supplemental |
| `hermes-skills/temi-robot-control/scripts/README.md` | `CURRENT_REFERENCE` | Skill helper reference | Hermes maintainers | — | `tools/` and `DEMO_OPERATOR_GUIDE.md` | — | Documents helper intent and prevents it becoming a second operator path. | Current supplemental |
| `hermes_temi_bridge/README.md` | `CURRENT_AUTHORITY` | Bridge module README | Bridge maintainers | Bridge boundary, schemas, validation and tests | — | — | Documents the canonical safety boundary owned by the Bridge. | Current authority |
| `logs/README.md` | `CURRENT_AUTHORITY` | Runtime-data policy | All maintainers | Log retention, privacy and non-source boundary | — | — | Prevents logs and traces from being mistaken for publication source. | Current authority |
| `memory/README.md` | `CURRENT_AUTHORITY` | Memory-data policy | Care maintainers | Synthetic memory, privacy and retention rules | — | — | Defines the allowed memory fixture and runtime-data boundary. | Current authority |
| `memory/abnormal_events/README.md` | `CURRENT_AUTHORITY` | Abnormal-event data policy | Perception and care maintainers | Abnormal-event artifact layout and retention | — | — | Defines safe handling of event artifacts and sensitive media. | Current authority |
| `memory/summaries/2026-06-02.md` | `HISTORICAL` | Dated memory summary | Care-memory researchers | — | `memory/README.md` | 2026-06-02 | Retains a reviewed synthetic summary as historical fixture evidence. | Historical evidence |
| `memory/summaries/README.md` | `CURRENT_AUTHORITY` | Summary-data policy | Care maintainers | Summary fixture and retention rules | — | — | Defines the safe summary directory and fixture policy. | Current authority |
| `mqtt/README.md` | `CURRENT_AUTHORITY` | MQTT module README | Integration maintainers | Broker configuration and topic operational boundary | — | — | Explains broker ownership and client/topic limits. | Current authority |
| `temi_backend/README.md` | `CURRENT_AUTHORITY` | Legacy backend module README | Backend maintainers | Legacy ASR, video, VLM and MQTT compatibility route | — | — | Documents the retained legacy module without promoting it to canonical dispatch. | Current authority |
| `temi_shared/README.md` | `CURRENT_AUTHORITY` | Shared-artifact policy | Bridge and adapter maintainers | Runtime image and metadata path contract | — | — | Defines allowlisted shared paths and keeps binary data off MQTT. | Current authority |
| `third_party/hermes/README.md` | `CURRENT_AUTHORITY` | External dependency contract | Maintainers and operators | Hermes team source, base pin, patch overlay, license and venv provisioning | — | 2026-08-31 | Makes the patched source-native dependency reproducible and fail-closed. | Current authority |
| `third_party/llama_cpp/README.md` | `CURRENT_AUTHORITY` | External build contract | Viewer maintainers and operators | llama.cpp source pin, approved build and artifact identity | — | 2026-08-31 | Separates generated build output from portable source and records AI6 evidence. | Current authority |
| `tools/README.md` | `CURRENT_AUTHORITY` | Tools module README | Maintainers and operators | Cross-module scripts, lifecycle helper boundaries and verification commands | — | 2026-08-31 | Routes helper usage to the current lifecycle and preserves safety limits. | Current authority |

The ledger contains 29 `CURRENT_AUTHORITY` documents, 25
`CURRENT_REFERENCE` documents, 12 `HISTORICAL` documents and 7
`SUPERSEDED` documents, for 73 retained documents total. Every retained row
has a purpose and retention classification; therefore
`UNJUSTIFIED_RETAINED_DOCUMENT_COUNT=0`. Historical and superseded documents
are retained for provenance only and must not be used to infer current
operator commands, dependency paths, publication identity or readiness.
