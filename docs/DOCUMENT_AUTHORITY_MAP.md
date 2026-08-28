# TemiAgent Documentation Authority Map

Status: <code>CURRENT_AUTHORITY</code>; Gate 5B.1 inventory reviewed:
2026-08-28.

This is the complete first-party Markdown inventory for the publication
candidate. Each active Markdown document appears exactly once below and has
one classification. Runtime code, runtime schemas and executable validators
remain authoritative over prose. A supplemental document must defer to the
current authority named here; historical and legacy documents are retained for
context, not current operating instructions.

Inventory command used in the candidate:

~~~bash
git ls-files -co --exclude-standard -- '*.md'
~~~

<code>ACTIVE_FIRST_PARTY_MARKDOWN_DOCUMENTS</code> means the root-repository
Markdown paths emitted by the command above. It includes tracked paths and
non-ignored Markdown paths in the root worktree, excludes ignored runtime or
generated artifacts, and does not recurse into nested Git repositories or
submodule contents. The Gate 5B.1 remediation candidate has
<code>MARKDOWN_COUNT_ACTUAL=74</code> under this definition.

The unreferenced
<code>docs/archive/README.redirect.html</code> was classified as
<code>DELETE_CANDIDATE</code> and removed from this candidate because it was
an obsolete generated redirect containing private deployment data. Git
history preserves it; it is not part of the active document count.

## Authority rules

| Classification | Meaning | Required treatment |
|---|---|---|
| <code>CURRENT_AUTHORITY</code> | Maintained prose authority for its stated topic or owning module. | Keep source-backed, link it from the relevant index and update it when the contract changes. |
| <code>SUPPLEMENTAL</code> | Useful detail, implementation handoff, skill mirror or policy companion. | Link back to its authority; do not introduce a second current lifecycle or configuration contract. |
| <code>HISTORICAL</code> | Dated design, evidence, planning or release record. | Retain context and date; do not present its commands or status as current. |
| <code>LEGACY</code> | Superseded operating/handover procedure or compatibility reference. | Keep the legacy notice and point readers to the current authority. |
| <code>DEPRECATED</code> | Explicitly retired document or contract still retained for migration context. | Do not extend; replace references with the current authority. |
| <code>DELETE_CANDIDATE</code> | Redundant or unsafe artifact with no current owner or inbound reference. | Delete only after classification and reference scan; history is the retention mechanism. |

## Complete inventory

| Document path | Classification | Purpose | Authoritative for | Overlaps with | Contradictions | Action required |
|---|---|---|---|---|---|---|
| <code>.hermes.md</code> | SUPPLEMENTAL | Historical/runtime context for Hermes work. | No handover topic; patched Hermes tree and dependency README win. | Hermes README and skill mirror. | Generic workspace placeholders can be mistaken for deployment paths. | Keep supplemental label and defer to setup/dependency docs. |
| <code>AGENTS.md</code> | CURRENT_AUTHORITY | Repository governance, safety and collaboration rules. | Agent permissions, container boundary, protected files and delivery rules. | Root README and operational safety policy. | None after Gate 5B.1; executable policy still wins. | Keep required reading; change only through governance review. |
| <code>Agent.md</code> | SUPPLEMENTAL | Older agent brief and project orientation. | None; not the current governance entry. | <code>AGENTS.md</code> and root README. | Older paths or duplicated boundaries may drift. | Retain as reference and point readers to <code>AGENTS.md</code> and this map. |
| <code>README.md</code> | CURRENT_AUTHORITY | Repository entrypoint, scope and module map. | Project identity, capability limits and first reading route. | Current status, repository map and student handover. | None after Gate 5B.1. | Link the current setup and handover entry points. |
| <code>anomaly_detection/README.md</code> | CURRENT_AUTHORITY | Owning module reference for optional perception/viewer. | Anomaly module scope, commands and experimental boundary. | Project overview and viewer operations docs. | Direct viewer commands are not the managed Demo lifecycle. | Keep an explicit experimental/module boundary. |
| <code>docs/CURRENT_STATUS.md</code> | CURRENT_AUTHORITY | Dated implementation, evidence and publication status snapshot. | Current/verified/external/experimental/live-unverified claims. | README, repository map and release record. | None after release and candidate status correction. | Refresh only when evidence or publication state changes. |
| <code>docs/DOCUMENT_AUTHORITY_MAP.md</code> | CURRENT_AUTHORITY | Complete document inventory and conflict-prevention map. | Document classification and prose authority routing. | <code>docs/README.md</code> and student handover authority table. | None; runtime source/schema still outranks prose. | Maintain one row per active first-party Markdown file. |
| <code>docs/README.md</code> | CURRENT_AUTHORITY | Documentation index, reading order and classification rules. | Documentation navigation and authority hierarchy. | This map and student handover. | None after new entry points are linked. | Keep links and status labels synchronized. |
| <code>docs/REPOSITORY_MAP.md</code> | CURRENT_AUTHORITY | High-density source, generated and runtime boundary map. | Repository layout and publication boundary. | README and current status. | None after Gate 5B.1 link/status update. | Update when source ownership or external pins change. |
| <code>docs/architecture/android_cross_service_contract.md</code> | SUPPLEMENTAL | Android implementer-facing cross-system contract. | No Android internal handover; AI6/Android interface detail only. | Canonical cross-service contract and runtime schemas. | Android source/APK remains external; live implementation is not implied. | Defer to runtime schemas and traceability; keep external boundary explicit. |
| <code>docs/architecture/canonical_cross_service_contract.md</code> | SUPPLEMENTAL | Detailed media, identity, care and correlation contract. | Feature-specific cross-service semantics. | Android contract, schemas and Bridge README. | Feature-gated or future producers must not be described as live. | Keep implementation status beside examples and defer to schemas. |
| <code>docs/architecture/contract_traceability.md</code> | CURRENT_AUTHORITY | Cross-module contract ownership and synchronization matrix. | Producer/consumer/schema/test ownership. | Runtime schemas and module READMEs. | None after status labels are respected. | Update every coordinated contract change. |
| <code>docs/architecture/project_overview.md</code> | CURRENT_AUTHORITY | Architecture, data flow and capability classification. | Project-level architecture and module boundaries. | README, repository map and historical design sections. | Historical sections must remain labeled; no current command authority. | Preserve historical labels and link current operations. |
| <code>docs/operations/DEMO_OPERATOR_GUIDE.md</code> | CURRENT_AUTHORITY | Canonical Demo operator workflow. | <code>scripts/demo</code> lifecycle, ownership, readiness and operator safety. | Quick reference, warm-start and legacy runbooks. | None after compatibility aliases are separated from the current sequence. | Keep the only current lifecycle command vocabulary. |
| <code>docs/operations/DEMO_QUICK_REFERENCE.md</code> | SUPPLEMENTAL | Compact operator companion. | No independent topic; command summary only. | Demo operator guide and troubleshooting. | Placeholder container/root was previously ambiguous. | Use exact designated container and defer all lifecycle detail. |
| <code>docs/operations/developer_setup.md</code> | CURRENT_AUTHORITY | Ordered clean-clone setup and environment matrix. | Student prerequisites, locked environments, source bootstrap and external artifacts. | Deployment handover and external dependency READMEs. | Root publication URL and environment pins are explicit external gaps, not invented. | Keep ten-step order and environment gap labels current. |
| <code>docs/operations/demo_configuration_reference.md</code> | CURRENT_AUTHORITY | Configuration, ownership, ports and secret contract. | Lifecycle config inputs, private runtime locations and validation. | Operator guide, Bridge <code>.env.example</code> and backend config. | Direct module templates are not alternate lifecycle configs. | Maintain complete key inventory and secret rules. |
| <code>docs/operations/demo_deployment_handover.md</code> | CURRENT_AUTHORITY | Host/service responsibility and deployment handover. | AI6 host/container, Temi, LAB606 and external service ownership. | Operator guide, setup and integration runbook. | None after LAB606 TCP-to-MQTT is explicitly non-required. | Keep service table aligned with lifecycle source. |
| <code>docs/operations/demo_operations_runbook.md</code> | LEGACY | Expert historical aliases and evidence procedure. | None; historical compatibility reference only. | Demo operator guide and old direct-service docs. | Legacy commands must not be copied as current procedure. | Keep legacy banner and current-guide link. |
| <code>docs/operations/demo_temporary_content_inventory_20260730.md</code> | HISTORICAL | Dated temporary artifact retention inventory. | Its stated historical inventory only. | Runtime/data policy and current repository map. | Dates and local artifact observations are not current status. | Retain date and do not use as setup instructions. |
| <code>docs/operations/demo_troubleshooting.md</code> | CURRENT_AUTHORITY | Symptom-driven diagnostics and safe escalation. | Current Demo failure checks, safe actions and do-not-do rules. | Safe service operations and operator guide. | None after all required symptom classes are explicit. | Keep every row read-only first and exact-PID safe. |
| <code>docs/operations/demo_warm_start_runbook.md</code> | SUPPLEMENTAL | Detailed warm-start evidence and external runtime notes. | Warm-start detail after operator authority. | Operator guide, deployment handover and safe operations. | It must not add a second lifecycle grammar. | Link back to operator guide and mark supplemental. |
| <code>docs/operations/first_year_demo_e2e_operation_manual.md</code> | LEGACY | Dated first-year Demo and recording procedure. | None; historical scenario evidence. | Current Demo operator and project scenario docs. | Direct service/recording assumptions are not current. | Preserve for history with legacy notice. |
| <code>docs/operations/first_year_demo_runbook.md</code> | LEGACY | Dated first-year scenario startup/fallback. | None; historical Demo reference. | Current operator guide and scenario script. | Historical ports/commands cannot override current lifecycle. | Keep legacy notice and replacement link. |
| <code>docs/operations/immediate_abnormal_care_flow.md</code> | SUPPLEMENTAL | Bridge-owned abnormal-care flow detail. | Feature detail under Bridge/runtime contracts. | Troubleshooting, Bridge README and canonical cross-service contract. | Demo-only notification is not emergency delivery. | Defer to Bridge code/schema and keep capability limits visible. |
| <code>docs/operations/lmstudio_gpu_selection.md</code> | SUPPLEMENTAL | Machine-specific GPU selection evidence. | No portable environment topic. | LM Studio deployment manual and current status. | Observations must not become version or GPU defaults. | Keep experimental/machine-specific notice. |
| <code>docs/operations/lmstudio_headless_3gpu_hdd_manual.md</code> | SUPPLEMENTAL | Machine-dependent LM Studio startup and recovery notes. | External LM Studio owner procedure only. | Operator guide and developer environment matrix. | It cannot establish a portable GPU or model pin. | Defer to lifecycle ownership and mark machine-dependent. |
| <code>docs/operations/safe_service_operations.md</code> | CURRENT_AUTHORITY | Exact-PID service safety and recovery policy. | Process targeting, rollback, restore and incident evidence. | Operator guide and troubleshooting. | None; no broad process control is allowed. | Keep safety policy synchronized with lifecycle identity checks. |
| <code>docs/operations/temi_e2e_stack_validation_manual.md</code> | LEGACY | Superseded direct-service full-stack validation. | None; historical validation evidence. | Current lifecycle and verification matrix. | Direct restart scripts are not current ownership. | Keep legacy notice and do not extend. |
| <code>docs/operations/temi_integration_runbook.md</code> | SUPPLEMENTAL | Hardware-free integration and external acceptance detail. | Integration-specific checks below current operator authority. | Verification guide and Android contract. | No real-device result is implied by software checks. | Defer to testing/acceptance authority. |
| <code>docs/operations/temi_streaming_local_runbook.md</code> | LEGACY | Local ADB/MQTT/WebSocket historical observations. | None; machine-specific historical evidence. | Streaming manual and current deployment map. | Private host/device assumptions are not portable defaults. | Retain with legacy notice. |
| <code>docs/operations/temi_streaming_manual.md</code> | LEGACY | Historical Android build, ADB and streaming procedure. | None; external Android reference. | Android contract and integration runbook. | It is not the current AI6 lifecycle. | Retain for history and external ownership context. |
| <code>docs/operations/verification_and_acceptance.md</code> | CURRENT_AUTHORITY | Test matrix and evidence/acceptance boundary. | Hardware-free suites and external gates. | Module READMEs, current status and integration runbook. | None after live/hardware claims remain explicitly external. | Keep commands tied to current test files. |
| <code>docs/project/continuous_vision_abnormal_behavior_handoff.md</code> | SUPPLEMENTAL | Experimental perception handoff. | Optional anomaly design detail. | Anomaly README and current status. | No medical/fall-detection or dispatcher claim is allowed. | Keep experimental boundary and source link. |
| <code>docs/project/final_demo_release_consolidation_20260731.md</code> | HISTORICAL | Dated release reconciliation record. | Its historical commit/evidence record. | Current status and publication branch. | Its date-specific state is not a current release command. | Preserve as immutable evidence; link current release handover. |
| <code>docs/project/first_year_demo_acceptance_checklist.md</code> | HISTORICAL | Dated first-year Demo checklist. | Historical scenario evidence only. | Verification/acceptance and scenario script. | Checklist claims require current evidence before reuse. | Retain dated; use current testing authority. |
| <code>docs/project/first_year_demo_phase_tasks.md</code> | HISTORICAL | P0–P5 planning and artifact record. | Historical project planning only. | Current status and release records. | Planned work is not implemented capability. | Retain as planning history. |
| <code>docs/project/first_year_demo_scenario_script.md</code> | HISTORICAL | Dated Demo narration and evidence mapping. | Historical scenario presentation. | Acceptance checklist and project handover. | Scenario narration is not runtime proof. | Retain dated and use current status for claims. |
| <code>docs/project/first_year_demo_system_design_20260601.md</code> | HISTORICAL | Dated design snapshot. | Design decisions at its stated date. | Project overview and current contracts. | Later implementation may differ. | Retain with date and no current command authority. |
| <code>docs/project/hermes_care_assistant_handoff.md</code> | SUPPLEMENTAL | Domain/cognitive assistant handoff. | Care-domain context below runtime safety contracts. | Hermes skills and Bridge README. | Domain narrative cannot broaden capability or care claims. | Keep supplemental and defer to current boundaries. |
| <code>docs/project/hermes_care_assistant_task_readme.md</code> | SUPPLEMENTAL | Maintained task scope and Demo care context. | Task-specific context only. | Student handover and current status. | Demo-only features are not general care service guarantees. | Link current status and keep limits explicit. |
| <code>docs/project/p2_structured_memory_phase1_report_materials.md</code> | HISTORICAL | Phase report materials and evidence. | Historical structured-memory evidence. | Memory module README and current status. | Phase evidence is not a current data contract. | Retain as dated report material. |
| <code>docs/project/phase1_care_context_builder_read_path.md</code> | HISTORICAL | Phase 1 implementation note. | Historical care-context read path. | Bridge/runtime contract docs. | Current code/schema must be checked before reuse. | Retain dated; do not use as operator setup. |
| <code>docs/project/phase1_care_context_demo_package.md</code> | HISTORICAL | Phase 1 Demo package description. | Historical Demo evidence package. | Current status and memory docs. | Package contents do not establish production readiness. | Retain as dated evidence. |
| <code>docs/project/STUDENT_HANDOVER.md</code> | CURRENT_AUTHORITY | New-student reading order, authority map and 40-question gap matrix. | Student onboarding and release handover procedure. | README, current status, setup and operator docs. | None; partial answers name external owners. | Keep <code>MISSING=0</code> and update questions with contract changes. |
| <code>docs/project/system_handover.md</code> | LEGACY | Broad historical system handover. | None; old handover reference. | Student handover, deployment and current status. | Older command/path assumptions are superseded. | Keep legacy banner and replacement links. |
| <code>hermes-skills/README.md</code> | CURRENT_AUTHORITY | Root skill mirror module index. | Mirror purpose, runtime-vs-review path and skill ownership. | Hermes dependency README and individual skills. | Mirror is not a second Hermes source checkout. | Keep runtime submodule distinction explicit. |
| <code>hermes-skills/temi-care-memory/SKILL.md</code> | SUPPLEMENTAL | Temi care-memory skill policy mirror. | Skill-specific prompt/policy detail after Hermes bootstrap. | Hermes runtime skill and memory docs. | Skill text cannot bypass Bridge validators or privacy rules. | Keep mirror label and sync through reviewed patch flow. |
| <code>hermes-skills/temi-care-memory/references/structured_memory_contract.md</code> | SUPPLEMENTAL | Structured-memory skill reference. | Skill implementation detail only. | Memory README and phase reports. | It does not authorize real care data. | Defer to runtime/schema ownership. |
| <code>hermes-skills/temi-demo-identity/SKILL.md</code> | SUPPLEMENTAL | Demo-only identity skill mirror. | Controlled identity helper semantics. | Cross-service identity contract and Bridge code. | Fallback is not verified identity or recognition. | Keep Demo-only and feature-gated labels. |
| <code>hermes-skills/temi-demo-repeated-discomfort/SKILL.md</code> | SUPPLEMENTAL | Synthetic repeated-discomfort skill mirror. | Bounded Demo scenario semantics. | Care flow docs and Bridge callback code. | Synthetic scenario is not a care guarantee. | Keep synthetic-only boundary. |
| <code>hermes-skills/temi-discord-care-assistant/SKILL.md</code> | SUPPLEMENTAL | Discord/care assistant skill mirror. | Skill prompt policy and gateway context. | Hermes dependency and notification docs. | Discord is best-effort and not emergency delivery. | Keep secret/provider boundary explicit. |
| <code>hermes-skills/temi-discord-care-assistant/references/discord_temi_context.md</code> | SUPPLEMENTAL | Discord skill context reference. | Skill-specific context only. | Notification troubleshooting and Hermes README. | No credential or delivery guarantee. | Retain as reference; defer to Bridge notification contract. |
| <code>hermes-skills/temi-home-esi/SKILL.md</code> | SUPPLEMENTAL | Home-ESI skill mirror. | Skill behavior and safety wording. | Hermes dependency and project overview. | Skill cannot broaden hardware/medical claims. | Sync only through reviewed Hermes overlay. |
| <code>hermes-skills/temi-home-esi/references/home_esi_lite.md</code> | SUPPLEMENTAL | Home-ESI reference material. | Skill-specific reference only. | Home-ESI skill and care handoff. | Reference is not an operator or device contract. | Retain supplemental. |
| <code>hermes-skills/temi-robot-control/SKILL.md</code> | SUPPLEMENTAL | Robot-control policy mirror. | Skill policy below Bridge/action validation. | MQTT topics, safety rules and Bridge README. | Hermes cannot publish/control hardware directly. | Keep safety boundary and runtime mirror relationship. |
| <code>hermes-skills/temi-robot-control/references/examples.md</code> | SUPPLEMENTAL | Robot-control examples. | Illustrative skill examples only. | MQTT topic reference and schemas. | Examples do not override validators or allowlists. | Mark illustrative and keep source-backed links. |
| <code>hermes-skills/temi-robot-control/references/mqtt_topics.md</code> | SUPPLEMENTAL | Skill-facing MQTT topic reference. | Skill topic vocabulary only. | MQTT README and runtime client. | Runtime topics/QoS are owned by code and contracts. | Defer to MQTT/traceability authority. |
| <code>hermes-skills/temi-robot-control/references/safety_rules.md</code> | SUPPLEMENTAL | Robot-control safety rules. | Skill policy detail. | AGENTS, action validator and operator safety. | No skill can bypass Bridge safety boundary. | Retain and sync with safety review. |
| <code>hermes-skills/temi-robot-control/scripts/README.md</code> | SUPPLEMENTAL | Skill helper-script notes. | Skill-local scripts only. | Tools README and operator guide. | Direct helper use may not be the canonical lifecycle. | Keep module-local scope explicit. |
| <code>hermes_temi_bridge/README.md</code> | CURRENT_AUTHORITY | Bridge module architecture, commands and tests. | Bridge-owned validation, schemas and dispatch module reference. | Contract traceability and operator guide. | Direct module run is not the managed lifecycle. | Keep module command details and lifecycle deferral. |
| <code>logs/README.md</code> | CURRENT_AUTHORITY | Runtime log directory privacy/retention reference. | Log artifact classification and redaction boundary. | Safe operations and deployment handover. | None after runtime-only status is explicit. | Keep logs non-source and bounded. |
| <code>memory/README.md</code> | CURRENT_AUTHORITY | Tracked synthetic/de-identified memory boundary. | Memory fixture/data privacy rules. | Care handoff and runtime config. | Tracked memory is not production care data. | Keep fixture provenance and exclusion rules. |
| <code>memory/abnormal_events/README.md</code> | CURRENT_AUTHORITY | Abnormal-event fixture directory reference. | Synthetic fixture classification and validation. | Abnormal-care flow and testing docs. | Fixture presence is not live notification evidence. | Keep source/consent/synthetic status explicit. |
| <code>memory/summaries/2026-06-02.md</code> | HISTORICAL | Dated synthetic summary snapshot. | Its stated historical fixture only. | Memory README and phase reports. | Date-specific content is not current resident state. | Retain as dated fixture evidence. |
| <code>memory/summaries/README.md</code> | CURRENT_AUTHORITY | Summary fixture directory policy. | Summary fixture format and privacy boundary. | Memory README and dated summaries. | None after dated files are labeled historical. | Keep fixture policy synchronized. |
| <code>mqtt/README.md</code> | CURRENT_AUTHORITY | MQTT transport configuration and topic index. | Broker transport reference and topic vocabulary. | Bridge MQTT client, skill topic reference and operator guide. | Direct broker commands are reference/smoke only, not lifecycle authority. | Keep canonical lifecycle deferral explicit. |
| <code>temi_backend/README.md</code> | CURRENT_AUTHORITY | Legacy backend module reference. | Legacy ASR/video/local-VLM module commands and limits. | Repository map and historical streaming docs. | Legacy module is not canonical Hermes V1 lifecycle. | Keep legacy boundary banner. |
| <code>temi_shared/README.md</code> | CURRENT_AUTHORITY | Shared runtime image/metadata path policy. | Shared artifact layout and privacy boundary. | Bridge README and deployment handover. | Paths/data are runtime artifacts, not source inputs. | Keep allowlisted-path rule current. |
| <code>third_party/hermes/README.md</code> | CURRENT_AUTHORITY | Hermes submodule, patch, license and reconstruction contract. | External Hermes source identity and overlay. | Developer setup, Hermes skills and current status. | No fallback source acquisition is allowed. | Update only with dependency governance review. |
| <code>third_party/llama_cpp/README.md</code> | CURRENT_AUTHORITY | llama.cpp manifest and generated-source contract. | External llama.cpp source identity and bootstrap. | Developer setup, anomaly README and current status. | Generated checkout is not root source and does not include models. | Keep pin/license/build caveats current. |
| <code>tools/README.md</code> | CURRENT_AUTHORITY | Cross-module script index and helper ownership. | Tool purpose, canonical lifecycle entry and test helpers. | Operator guide and module READMEs. | Direct legacy scripts must not become current lifecycle. | Mark legacy/reference helpers and link handover docs. |
| <code>計劃書/README.md</code> | HISTORICAL | Research/reference directory index. | Research material organization only. | Project overview and historical plans. | Research text is not runtime or deployment authority. | Retain as reference and keep out of current reading path. |
| <code>計劃書/子計畫三_分年工作項目整理.md</code> | HISTORICAL | Dated research plan and yearly work items. | Historical planning only. | First-year phase tasks and project docs. | Planned work is not implementation evidence. | Retain dated and non-operational. |

## Major-topic routing check

The required major topics each have one current prose authority:

| Topic | Authority |
|---|---|
| Project overview | <code>README.md</code> |
| Current status | <code>docs/CURRENT_STATUS.md</code> |
| Repository map | <code>docs/REPOSITORY_MAP.md</code> |
| Architecture | <code>docs/architecture/project_overview.md</code> |
| Developer setup | <code>docs/operations/developer_setup.md</code> |
| External dependencies | <code>docs/operations/developer_setup.md</code> (with source-specific manifests and READMEs) |
| Configuration and secrets | <code>docs/operations/demo_configuration_reference.md</code> |
| Demo operator | <code>docs/operations/DEMO_OPERATOR_GUIDE.md</code> |
| Deployment | <code>docs/operations/demo_deployment_handover.md</code> |
| Service lifecycle | <code>docs/operations/DEMO_OPERATOR_GUIDE.md</code> |
| MQTT | <code>mqtt/README.md</code>, with runtime code/schema authority |
| Bridge | <code>hermes_temi_bridge/README.md</code>, with runtime code/schema authority |
| Hermes | <code>third_party/hermes/README.md</code> |
| Anomaly backend | <code>anomaly_detection/README.md</code> |
| Troubleshooting | <code>docs/operations/demo_troubleshooting.md</code> |
| Testing | <code>docs/operations/verification_and_acceptance.md</code> |
| Handover | <code>docs/project/STUDENT_HANDOVER.md</code> |
| Release process | Release section of <code>docs/project/STUDENT_HANDOVER.md</code> |

Current-document contradiction result for this candidate:
<code>CURRENT_DOC_CONTRADICTIONS=0</code>. This means the current and
supplemental prose has been routed and labeled consistently; it does not
override executable source, schemas or a future runtime change.
