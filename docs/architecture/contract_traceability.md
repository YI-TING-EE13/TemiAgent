# Cross-Module Contract Traceability

最後審查日期：2026-07-31

This document identifies the authoritative source, producers, consumers, validation owner, tests and synchronization rule for TemiAgent cross-module contracts. It does not replace runtime code or schemas.

## Authority Rule

The executable runtime definition is authoritative. A README or file under `docs/schemas/` explains that definition but MUST NOT introduce behavior independently.

When no single generated contract package exists, the producer and consumer implementations jointly define current behavior. Such duplication is a governance risk and requires cross-module review.

For current lifecycle, private configuration and acceptance evidence, use the
[Demo operator guide](../operations/DEMO_OPERATOR_GUIDE.md),
[configuration reference](../operations/demo_configuration_reference.md), and
[verification guide](../operations/verification_and_acceptance.md). These
documents do not replace the runtime sources named in this matrix.

## Contract Matrix

| Contract | Capability state | Authoritative source | Producers | Consumers and validation | Tests/evidence | Update together |
|---|---|---|---|---|---|---|
| Canonical MQTT topics | ASR, abnormal, command request/result implemented; state topic reserved | `hermes_temi_bridge/src/hermes_temi_bridge/mqtt_client.py`, `tools/temi_overview_adapter.py`, Android behavior documented externally | Overview adapter, Bridge, Temi App, anomaly producer | Bridge MQTT client and Temi App | Bridge tests, `tools/e2e_test_runner.py`, hardware runbooks | Producer/consumer code, `mqtt/README.md`, architecture, Android contract and integration tests |
| Legacy MQTT topics | Verified legacy Demo route | `temi_backend/src/temi_backend/mqtt_bridge.py` | Temi App and legacy backend | Legacy backend and Temi App | `temi_backend/tests/`, manual hardware checks | Backend, Android contract, module README and tests |
| ASR final event v1.0 | Implemented; hardware-free verified | `hermes_temi_bridge/schemas/asr_final_event.schema.json` plus enforcement in `event_models.py` and `image_resolver.py` | Overview adapter and mock publisher | Bridge | `test_event_validation.py`, image/path tests, `e2e_test_runner.py` | Runtime schema, adapter, Bridge validation/tests, reader copy, `temi_shared/README.md` |
| Abnormal perception event v1.0 | Experimental Demo; immediate Bridge-owned alert and Hermes care follow-up implemented | `hermes_temi_bridge/schemas/perception_abnormal_event.schema.json`, `event_models.py`, `image_resolver.py`, `care_episode.py`, and `abnormal_notification.py` | Viewer, video tester, and `scripts/inject_demo_event` | Bridge validates evidence and test metadata, persists event/stage dedup, attempts one notification, invokes Resident Hermes, validates the speak command, and correlates reply/timeout state | schema, episode, notification, Bridge, viewer, injector, lifecycle, and isolated E2E tests | Runtime schema and reader copy, all producers/consumers, config, docs, and tests |
| Hermes action output v1.0 | Implemented; Bridge validation verified | `hermes_temi_bridge/schemas/hermes_action_output.schema.json` and `action_validator.py` | Hermes runtime or mock client | Bridge | `test_action_validation.py`, client tests and fixtures | Schema, validator, Hermes prompt/skills, tests and reader copy |
| Command request v1.0 | Implemented; hardware-free verified | `hermes_temi_bridge/schemas/temi_command_request.schema.json` and `command_dispatcher.py` | Bridge; viewer no longer publishes abnormal pre-alert commands | Temi App | dispatcher/Bridge tests, mock E2E and real-device runbook | Schema, dispatcher, Temi App, tests, reader copy and MQTT docs |
| Command result v1.0 | Implemented | `hermes_temi_bridge/schemas/temi_command_result.schema.json` and result handler | Temi App or mock publisher | Bridge trace/result handler | Bridge result/trace tests and mock E2E | Schema, Android producer, Bridge consumer/tests and reader copy |
| Resident identity result v1.0 | Feature-gated Bridge consumer plus Demo-only manual-selection producer; real visual acceptance pending | `hermes_temi_bridge/schemas/resident_identity_result.schema.json`, `identity_contract.py`, `resident_context.py`, `demo_identity.py` | External VLM/identity provider; Temi App manual selection; root resident identity native tool via Bridge callback | Visual route consumes fresh `vision_gender_fallback`; explicitly gated operator route alone admits existing-schema `manual_selection`; Bridge validates/publishes QoS 1 retain=false, Android/report remain external | schema tests, `test_demo_resident_media_runtime.py`, `test_demo_identity_repeated_discomfort.py`; no VLM/Android E2E evidence | Runtime schema, all producers/consumers, Android contract, reader copy and privacy tests |
| Video command/result v1.1 | Feature-gated Bridge runtime plus root-owned resident Hermes native tool callback; real consumer pending | Schemas plus `media_contract.py`, `media_registry.py`, `hermes_media_tool.py` and service result dispatch | Bridge explicit API via local callback; Temi App owns session creation/execution/results | Bridge validates tool allowlist, active resident, request semantics, result correlation/lifecycle/replay; Android validation remains external | `test_media_v11_runtime.py`, `test_demo_resident_media_runtime.py`, schema tests and fake E2E; Android/real-device tests pending | Both schemas, common errors, callback/Bridge validator/registry/service, Android persistence/state machine, tests, reader copies and runbooks |
| Care report v1.0 | Contract defined; report service not implemented | `hermes_temi_bridge/schemas/care_report.schema.json` | Future report producer behind Bridge/memory boundary | Temi App and authorized reviewer | Schema tests; producer/consumer/privacy tests pending | Runtime schema, report producer/consumer, identity isolation, reader copy and contract docs |
| Care report interaction result v1.0 | Contract defined; runtime integration pending | `hermes_temi_bridge/schemas/care_report_interaction_result.schema.json` | Temi App or authorized reviewer | Future report owner and Bridge trace adapter | Schema tests; interaction/integration tests pending | Runtime schema, publisher/consumer, idempotency/trace tests, reader copy and Android contract |
| New cross-service error codes | Contract defined for identity/video/report only | `hermes_temi_bridge/schemas/cross_service_common.schema.json` | New contract producers | New contract consumers | `$ref` compilation and invalid error-state tests | Common schema, every reference, reader copy and error documentation |
| Robot action allowlist | Implemented; Bridge validation verified | `action_validator.py`, `hermes_action_output.schema.json` and command builder | Hermes plans | Bridge | `test_action_validation.py` | Validator, runtime schema, command builder, Temi skills, tests and docs |
| Shared event path layout | Implemented; path validation verified | `image_resolver.py`, Bridge config and writer behavior in Overview adapter | Overview adapter, snapshot/anomaly tools | Bridge and Hermes prompt | image resolver/event tests and mock E2E | Writer, resolver, config, Docker mounts, tests and `temi_shared/README.md` |
| Bridge environment variables | Implemented | `hermes_temi_bridge/src/hermes_temi_bridge/config.py` | Operator/configuration | Bridge | config tests and module startup | `config.py`, `.env.example`, Bridge README and runbooks |
| Service ports | Implemented defaults; environment-dependent | Owning service config or CLI parser: Bridge config, resident server, backend config, action viewer and startup scripts | Service owners | Operators and downstream clients | Health probes and integration runbooks | Owning code/config, scripts, module README and cross-module runbook |
| Model input/output | Research/Demo | Prompt construction in `hermes_client.py`; output enforcement in `action_validator.py`; anomaly parser in `temi_action_viewer.py` | Hermes or specialist model | Bridge validator or anomaly parser | Bridge client/action tests; anomaly manual/model tests | Prompt, parser/validator, model revision/config, tests, skills and capability claims |
| Care memory formats | Demo-only synthetic data; per-resident private seed is feature-gated | `memory_store.py`, `care_context_builder.py`, `demo_care_memory.py`, `demo_repeated_discomfort.py`, `care_confirmation.py` | Bridge memory actions, explicit local seed tool, father-only native callback flow and bounded abnormal confirmation store | Bridge/Hermes context builder; pending state stores no raw ASR or hidden reasoning and expires before unrelated ASR reaches Hermes | memory/context tests, `test_demo_resident_media_runtime.py`, `test_demo_identity_repeated_discomfort.py`, `test_abnormal_care_confirmation.py` | Code, tests, `memory/README.md`, skill contract and retention rules |
| Bridge trace/event-log format | Implemented for v1.0 and feature-gated v1.1 media flow | `logging_utils.py`, service media trace calls and `hermes_temi_bridge/README.md` | Bridge | Maintainers and `tools/show_temi_trace.py` | trace tests plus media runtime/fake E2E | Writer, viewer, result schema/consumer, tests, README and retention/privacy policy |
| Health endpoints | Implemented per service | Owning endpoint implementation or server wrapper | Backend/resident/viewer services | Operators and `tools/demo_lifecycle.py` | service tests or runbook probes | Endpoint implementation, lifecycle health contract, startup/validation scripts and module/runbook docs |
| Demo lifecycle ownership state | Implemented; hardware-free and mock-fixture verified | `tools/demo_lifecycle.py` state model and atomic writer | lifecycle start/restart/stop | lifecycle status, doctor, and exact-PID stop logic | `tools/tests/test_demo_lifecycle.py`, newcomer mock success/failure fixtures | lifecycle source, state/health/rollback tests, tools README, operations docs, and architecture note |
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
temi/{robot_id}/care/report
temi/{robot_id}/care/report/interaction/result
```

Video v1.1 reuses `cmd/request` and `cmd/result`; it does not create a parallel hardware
command route. Serialized play and validated active-session controls share the request topic;
queue priority is an execution policy after validation, not a transport route. Bridge media
publication is isolated behind `MEDIA_V11_ENABLED=false` by default. Android behavior remains v1.0
until its parser, persistence, player state machine and integration tests are implemented.
Direction, owner and rollout rules are defined in
[canonical_cross_service_contract.md](canonical_cross_service_contract.md).

The current topic strings are repeated across modules. No generated, single-source topic library exists. A topic change therefore requires an explicit repository-wide search and coordinated producer/consumer review.

`temi/{robot_id}/state` is reserved in existing documentation, but the 2026-07-26
runtime search found no active producer or consumer. Treat it as planned/unverified
until code and tests establish ownership.

## Schema Copy Mapping

```text
hermes_temi_bridge/schemas/asr_final_event.schema.json
  -> docs/schemas/asr_final_event.schema.json

hermes_temi_bridge/schemas/perception_abnormal_event.schema.json
  -> docs/schemas/perception_abnormal_event.schema.json

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

- **Implemented and verified without hardware:** Bridge validators and unit tests, backend unit tests, local mock E2E, and feature-gated media v1.1 with fake Android.
- **Implemented but environment-dependent:** resident Hermes, MQTT integration, streaming endpoints and health probes.
- **Demo-only:** Home-ESI care scenarios, synthetic memory actions, mock caregiver notification and manual/demo action dispatch.
- **Experimental:** continuous abnormal perception and model-driven action classification.
- **Deprecated compatibility route:** none formally removed; legacy MQTT route remains supported for Demo verification.
- **Contract defined; integration pending:** care report and report interaction result; an upstream visual identity producer remains pending.
- **Feature-gated integration:** Bridge media v1.1 runtime, root resident native media entry, and Demo-only manual identity/repeated-discomfort callbacks; Android identity/media mapping and real-device acceptance remain pending.
- **Planned/future:** real notification workflow, clinical validation, production identity/access controls and a centralized generated topic contract.

Do not rewrite a planned or experimental item as an implemented, verified or regulated capability.

## Known Governance Gaps

1. No abnormal perception contract gap is currently known: the runtime schema and reader copy are checked together. Real device, real recipient, and care outcome validation remain external acceptance work.
2. Topic strings and some service defaults are duplicated across modules.
3. `.env.example` does not list every `BridgeConfig` setting.
4. Runtime synthetic memory output and a model checkpoint are already tracked by Git.
   Ignoring or removing them requires a separately reviewed repository-artifact
   change; `.gitignore` alone would not untrack existing files.
5. `tools/check_temi_connection.sh`, `tools/validate_temi_e2e_stack.sh`,
   `tools/start_temi_pc_services.sh`, `tools/start_temi_pc_services_background.sh`
   and `tools/temi_overview_adapter.py` contain machine-specific private-network
   defaults. Operators can override them through environment variables or CLI
   arguments, but portable defaults require a separately authorized code change.

These gaps require separate code, contract or repository-history changes and are outside a documentation-only governance pass.
