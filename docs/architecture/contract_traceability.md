# Cross-Module Contract Traceability

最後審查日期：2026-07-26

This document identifies the authoritative source, producers, consumers, validation owner, tests and synchronization rule for TemiAgent cross-module contracts. It does not replace runtime code or schemas.

## Authority Rule

The executable runtime definition is authoritative. A README or file under `docs/schemas/` explains that definition but MUST NOT introduce behavior independently.

When no single generated contract package exists, the producer and consumer implementations jointly define current behavior. Such duplication is a governance risk and requires cross-module review.

## Contract Matrix

| Contract | Capability state | Authoritative source | Producers | Consumers and validation | Tests/evidence | Update together |
|---|---|---|---|---|---|---|
| Canonical MQTT topics | ASR, abnormal, command request/result implemented; state topic reserved | `hermes_temi_bridge/src/hermes_temi_bridge/mqtt_client.py`, `tools/temi_overview_adapter.py`, Android behavior documented externally | Overview adapter, Bridge, Temi App, anomaly producer | Bridge MQTT client and Temi App | Bridge tests, `tools/e2e_test_runner.py`, hardware runbooks | Producer/consumer code, `mqtt/README.md`, architecture, Android contract and integration tests |
| Legacy MQTT topics | Verified legacy Demo route | `temi_backend/src/temi_backend/mqtt_bridge.py` | Temi App and legacy backend | Legacy backend and Temi App | `temi_backend/tests/`, manual hardware checks | Backend, Android contract, module README and tests |
| ASR final event v1.0 | Implemented; hardware-free verified | `hermes_temi_bridge/schemas/asr_final_event.schema.json` plus enforcement in `event_models.py` and `image_resolver.py` | Overview adapter and mock publisher | Bridge | `test_event_validation.py`, image/path tests, `e2e_test_runner.py` | Runtime schema, adapter, Bridge validation/tests, reader copy, `temi_shared/README.md` |
| Abnormal perception event v1.0 | Experimental Demo | Enforcement in `event_models.py` and `image_resolver.py`; no standalone runtime JSON schema | Action viewer and video tester | Bridge | Bridge abnormal-event tests and manual viewer checks | Producer, Bridge parser/path tests, anomaly README and architecture |
| Hermes action output v1.0 | Implemented; Bridge validation verified | `hermes_temi_bridge/schemas/hermes_action_output.schema.json` and `action_validator.py` | Hermes runtime or mock client | Bridge | `test_action_validation.py`, client tests and fixtures | Schema, validator, Hermes prompt/skills, tests and reader copy |
| Command request v1.0 | Implemented; hardware-free verified | `hermes_temi_bridge/schemas/temi_command_request.schema.json` and `command_dispatcher.py` | Bridge; manual dispatcher after reusing validator/builder; action-viewer pre-alert is a known Demo-only exception | Temi App | dispatcher/Bridge tests, mock E2E and real-device runbook | Schema, dispatcher, Temi App, tests, reader copy and MQTT docs |
| Command result v1.0 | Implemented | `hermes_temi_bridge/schemas/temi_command_result.schema.json` and result handler | Temi App or mock publisher | Bridge trace/result handler | Bridge result/trace tests and mock E2E | Schema, Android producer, Bridge consumer/tests and reader copy |
| Resident identity result v1.0 | Contract defined; runtime integration pending | `hermes_temi_bridge/schemas/resident_identity_result.schema.json` | Future identity adapter; Temi App manual selection | Temi App, future report pipeline and Bridge integration | `test_cross_service_contract_schemas.py`; Android/integration tests pending | Runtime schema, all producers/consumers, Android contract, reader copy and privacy tests |
| Video command/result v1.1 | Ordering/session/idempotency contract defined; runtime integration pending | v1.1 subtypes in `temi_command_request.schema.json` and `temi_command_result.schema.json` | Future validated Bridge/remote producer; Temi App owns session creation, execution and result publishing | Temi App validates schema/semantics/active target before execution; Bridge validates result/correlation and traces it | Schema lifecycle, control, cancellation, concurrent play, duplicate/restart and v1.0 compatibility tests; Android/real-device tests pending | Both command schemas, common errors, semantic validators, Android persistence/state machine, Bridge result handling, tests, reader copies and runbooks |
| Care report v1.0 | Contract defined; report service not implemented | `hermes_temi_bridge/schemas/care_report.schema.json` | Future report producer behind Bridge/memory boundary | Temi App and authorized reviewer | Schema tests; producer/consumer/privacy tests pending | Runtime schema, report producer/consumer, identity isolation, reader copy and contract docs |
| Care report interaction result v1.0 | Contract defined; runtime integration pending | `hermes_temi_bridge/schemas/care_report_interaction_result.schema.json` | Temi App or authorized reviewer | Future report owner and Bridge trace adapter | Schema tests; interaction/integration tests pending | Runtime schema, publisher/consumer, idempotency/trace tests, reader copy and Android contract |
| New cross-service error codes | Contract defined for identity/video/report only | `hermes_temi_bridge/schemas/cross_service_common.schema.json` | New contract producers | New contract consumers | `$ref` compilation and invalid error-state tests | Common schema, every reference, reader copy and error documentation |
| Robot action allowlist | Implemented; Bridge validation verified | `action_validator.py`, `hermes_action_output.schema.json` and command builder | Hermes plans | Bridge | `test_action_validation.py` | Validator, runtime schema, command builder, Temi skills, tests and docs |
| Shared event path layout | Implemented; path validation verified | `image_resolver.py`, Bridge config and writer behavior in Overview adapter | Overview adapter, snapshot/anomaly tools | Bridge and Hermes prompt | image resolver/event tests and mock E2E | Writer, resolver, config, Docker mounts, tests and `temi_shared/README.md` |
| Bridge environment variables | Implemented | `hermes_temi_bridge/src/hermes_temi_bridge/config.py` | Operator/configuration | Bridge | config tests and module startup | `config.py`, `.env.example`, Bridge README and runbooks |
| Service ports | Implemented defaults; environment-dependent | Owning service config or CLI parser: Bridge config, resident server, backend config, action viewer and startup scripts | Service owners | Operators and downstream clients | Health probes and integration runbooks | Owning code/config, scripts, module README and cross-module runbook |
| Model input/output | Research/Demo | Prompt construction in `hermes_client.py`; output enforcement in `action_validator.py`; anomaly parser in `temi_action_viewer.py` | Hermes or specialist model | Bridge validator or anomaly parser | Bridge client/action tests; anomaly manual/model tests | Prompt, parser/validator, model revision/config, tests, skills and capability claims |
| Care memory formats | Demo-only synthetic data | `memory_store.py` and `care_context_builder.py` | Bridge memory actions | Bridge/Hermes context builder | memory and context-builder tests | Code, tests, `memory/README.md`, skill contract and retention rules |
| Bridge trace/event-log format | Implemented for v1.0; v1.1 media fields contract-defined | `logging_utils.py` and `hermes_temi_bridge/README.md`; media payload fields come from command-result schema | Bridge | Maintainers and `tools/show_temi_trace.py` | `test_trace_logging.py`; media trace integration pending | Writer, viewer, result schema/consumer, tests, README and retention/privacy policy |
| Health endpoints | Implemented per service | Owning endpoint implementation or server wrapper | Backend/resident/viewer services | Operators and validation scripts | service tests or runbook probes | Endpoint implementation, startup/validation scripts and module/runbook docs |
| Runtime artifact layout | Implemented but incompletely governed | Owning writers, `.gitignore`, `logs/README.md`, `memory/README.md`, `temi_shared/README.md` | All runtime modules | Maintainers | Git/private-artifact scan | Writer, ignore rules, retention/access documentation and cleanup procedure |

## Canonical Topics

```text
temi/{robot_id}/asr/final
temi/{robot_id}/perception/abnormal
temi/{robot_id}/cmd/request
temi/{robot_id}/cmd/result
```

Contract-defined topics without active runtime publishers/subscribers:

```text
temi/{robot_id}/resident/identity/result
temi/{robot_id}/care/report
temi/{robot_id}/care/report/interaction/result
```

Video v1.1 reuses `cmd/request` and `cmd/result`; it does not create a parallel hardware
command route. Serialized play and validated active-session controls share the request topic;
queue priority is an execution policy after validation, not a transport route. Current Bridge and
Android behavior remains v1.0 until consumer validation, producer wiring and integration tests are
implemented. Direction, owner and rollout rules are defined in
[canonical_cross_service_contract.md](canonical_cross_service_contract.md).

The current topic strings are repeated across modules. No generated, single-source topic library exists. A topic change therefore requires an explicit repository-wide search and coordinated producer/consumer review.

`temi/{robot_id}/state` is reserved in existing documentation, but the 2026-07-26
runtime search found no active producer or consumer. Treat it as planned/unverified
until code and tests establish ownership.

## Schema Copy Mapping

```text
hermes_temi_bridge/schemas/asr_final_event.schema.json
  -> docs/schemas/asr_final_event.schema.json

hermes_temi_bridge/schemas/hermes_action_output.schema.json
  -> docs/schemas/hermes_output.schema.json

hermes_temi_bridge/schemas/temi_command_request.schema.json
  -> docs/schemas/command_request.schema.json

hermes_temi_bridge/schemas/temi_command_result.schema.json
  -> docs/schemas/command_result.schema.json

hermes_temi_bridge/schemas/cross_service_common.schema.json
  -> docs/schemas/cross_service_common.schema.json

hermes_temi_bridge/schemas/resident_identity_result.schema.json
  -> docs/schemas/resident_identity_result.schema.json

hermes_temi_bridge/schemas/care_report.schema.json
  -> docs/schemas/care_report.schema.json

hermes_temi_bridge/schemas/care_report_interaction_result.schema.json
  -> docs/schemas/care_report_interaction_result.schema.json
```

The filenames differ for three reader copies. Compare the mapped files by content; do not infer drift from filename differences.

## Service Port Ownership

| Port | Owner and purpose | Current source |
|---:|---|---|
| `1234` | LM Studio OpenAI-compatible API | `tools/start_lmstudio_3gpu.sh` and LM Studio runbook |
| `1883` | Mosquitto MQTT | `mqtt/mosquitto.conf`, Compose and scripts |
| `8000` | Experimental live viewer HTTP | `anomaly_detection/README.md` and CLI |
| `8010` | Action viewer HTTP/health | action viewer CLI and restart script |
| `8011` | Managed llama.cpp API for action viewer | action viewer/restart configuration |
| `8080` | Temi H.264 WebSocket ingest | backend/adapter configuration |
| `8081` | Decoded JPEG frame broadcast | backend/adapter configuration |
| `8765` | Resident Hermes HTTP `/health` and `/invoke` in current integration | Bridge `.env.example`, resident script and integration runbooks |

`8766` may be used for an explicitly selected alternate resident instance, but it is not the current integration default.

## Capability Classification

- **Implemented and verified without hardware:** Bridge validators and unit tests, backend unit tests, local mock E2E.
- **Implemented but environment-dependent:** resident Hermes, MQTT integration, streaming endpoints and health probes.
- **Demo-only:** Home-ESI care scenarios, synthetic memory actions, mock caregiver notification and manual/demo action dispatch.
- **Experimental:** continuous abnormal perception and model-driven action classification.
- **Deprecated compatibility route:** none formally removed; legacy MQTT route remains supported for Demo verification.
- **Contract defined; integration pending:** first-year resident identity result, video command lifecycle, care report and report interaction result.
- **Planned/future:** real notification workflow, clinical validation, production identity/access controls and a centralized generated topic contract.

Do not rewrite a planned or experimental item as an implemented, verified or regulated capability.

## Known Governance Gaps

1. Action-viewer pre-alert publish bypasses the Bridge service. Disable or redesign it behind the safety boundary before treating the perception route as an approved hardware-control path.
2. Abnormal perception input has validation code but no standalone runtime JSON schema.
3. Topic strings and some service defaults are duplicated across modules.
4. `.env.example` does not list every `BridgeConfig` setting.
5. Runtime synthetic memory output and a model checkpoint are already tracked by Git.
   Ignoring or removing them requires a separately reviewed repository-artifact
   change; `.gitignore` alone would not untrack existing files.
6. `tools/check_temi_connection.sh`, `tools/validate_temi_e2e_stack.sh`,
   `tools/start_temi_pc_services.sh`, `tools/start_temi_pc_services_background.sh`
   and `tools/temi_overview_adapter.py` contain machine-specific private-network
   defaults. Operators can override them through environment variables or CLI
   arguments, but portable defaults require a separately authorized code change.

These gaps require separate code, contract or repository-history changes and are outside a documentation-only governance pass.
