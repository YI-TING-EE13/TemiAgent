# Demo Configuration Reference

Status: maintained, Demo-only. Last reviewed: 2026-07-31.

This is the non-secret reference for the complete key set in
[`config/demo.env.example`](../../config/demo.env.example). The private file is
an operator-owned `0600` regular file outside every Git worktree. It is loaded
by `tools/demo_lifecycle.py`; that implementation and Bridge `BridgeConfig`
remain authoritative if this guide disagrees with source.

Never copy a private env, Discord env, token, webhook, account name, real
endpoint, user-specific host path, care record, or runtime export into Git.
`doctor` and `status` may inspect a private config but must not print its secret
values.

## Preparation and source of truth

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
cp config/demo.env.example <private-demo-env>
chmod 600 <private-demo-env>
./scripts/demo --config <private-demo-env> doctor
```

Replace only placeholders in the private copy. The normal command path is in
the [Demo operator guide](DEMO_OPERATOR_GUIDE.md); this reference does not
authorize a start, restart, notification test, raw MQTT publish, or hardware
action.

## Rules that apply to every group

| Rule | Meaning |
|---|---|
| Private-file ownership | The private env and its parent are owned only by the lifecycle user; the env mode is exactly `0600`. |
| External runtime root | Mutable paths must be below `TEMIAGENT_RUNTIME_ROOT`, which is outside every Git worktree and owner-only. |
| Ownership vocabulary | `managed` means `scripts/demo` owns start, exact-PID recording and stop; `external` is health-checked only; `disabled` applies only to optional services. |
| No implicit adoption | A listener or PID that is not an expected recorded identity fails closed; the lifecycle does not kill by process name. |
| Defaults are not proof | A configured endpoint, gateway connection or webhook presence does not prove Android execution or notification delivery. |

## Runtime paths

| Key | Required form / purpose | Constraint |
|---|---|---|
| `TEMIAGENT_RUNTIME_ROOT` | Owner-only external root for all lifecycle state. | Must be outside every Git worktree. |
| `LOG_DIR` | Bridge trace root. | Must be below runtime root. |
| `MEMORY_DIR` | Bridge memory root. | Must be below runtime root; Demo data only. |
| `DEMO_CARE_MEMORY_ROOT` | Private synthetic care-memory partition root. | Required only by enabled care scenarios; below runtime root. |
| `TEMI_SHARED_BRIDGE_PATH` / `TEMI_SHARED_HERMES_PATH` | Bridge and resident view of shared ASR/media metadata. | Both are under the external root in the canonical profile. |
| `HERMES_MEDIA_CALLBACK_SOCKET` | Resident-to-Bridge Media Unix socket. | Private absolute socket path below runtime root; required when the Media tool is enabled. |
| `HERMES_DEMO_IDENTITY_CALLBACK_SOCKET` / `HERMES_DEMO_CARE_CALLBACK_SOCKET` | Private Demo identity/care callback sockets. | Required only with their corresponding enabled flows. |
| `DEMO_IDENTITY_STATE_DIR` | Process-scoped Demo identity status directory. | Below runtime root; restart never restores a prior resident selection. |

The lifecycle creates its own `state/`, `logs/`, `data/`, and `tmp/sockets/`
subdirectories. Repository `logs/`, `memory/`, and `temi_shared/` are not
current runtime targets.

## Managed dependency profile

| Key | Canonical sample value / role | Validation boundary |
|---|---|---|
| `LMSTUDIO_OWNERSHIP` | `managed` unless another documented owner is responsible. | Managed supervisor records its PID; external mode is never stopped. |
| `LMSTUDIO_TARGET_DIR` | LM Studio installation/data location. | Must support the reviewed startup helper. |
| `LMSTUDIO_MODEL_ID` | Logical Demo model ID. | Lifecycle checks the canonical model policy. |
| `LMSTUDIO_API_IDENTIFIER` | OpenAI-compatible model identifier. | Must match the reviewed Demo profile. |
| `LMSTUDIO_SERVER_PORT` | LM Studio API listener, normally `1234`. | Health is a service gate, not model-quality evidence. |
| `CONTEXT_LENGTH` / `LMSTUDIO_CONTEXT_LENGTH` | Both `64000` for the canonical Demo. | Must agree; the lifecycle rejects drift. |
| `LMSTUDIO_VISIBLE_GPUS` | `0,1` for the canonical Demo. | The lifecycle rejects a different GPU policy. |
| `MQTT_OWNERSHIP` | `managed` or explicitly `external`. | Exactly one reachable broker listener is required. |
| `MQTT_BROKER_HOST` / `MQTT_BROKER_PORT` | Broker endpoint and port, normally `1883`. | Do not commit a deployment-specific value. |
| `MQTT_CONFIG_PATH` | Managed Mosquitto config path. | Needed only when MQTT is managed. |
| `HERMES_GATEWAY_ENABLED` | Whether the optional Hermes gateway is included. | `false` disables it; do not infer Discord delivery from health. |
| `HERMES_GATEWAY_OWNERSHIP` | `managed`, `external`, or `disabled`. | Must agree with gateway enablement and operator responsibility. |
| `MANAGE_ANDROID` | `0` in the canonical software-only profile. | Android remains externally owned unless a separate contract authorizes management. |

## Bridge and resident contract

| Key | Role | Constraint |
|---|---|---|
| `ROBOT_ID_ALLOWLIST` | Comma-separated accepted robot IDs. | Must match actual intended robot routing; never use it to bypass Bridge validation. |
| `HERMES_INVOKE_MODE` | Bridge invocation mode, normally `http` for the Demo. | Validity is enforced by Bridge configuration and tests. |
| `HERMES_HTTP_URL` | Resident `/invoke` endpoint. | Treat endpoint location as private deployment detail. |
| `HERMES_TIMEOUT_SECONDS` | Bounded invoke timeout. | Changes need a source/config review, not a documentation-only edit. |
| `TRACE_ENABLED` | Enables Bridge trace records. | Trace content remains runtime data. |
| `TRACE_INCLUDE_ASR_TEXT` | Controls ASR content in summary trace. | Prefer `false` in care-sensitive Demo operation. |
| `DEBUG_TRACE_FULL` | Allows full debugging fields in trace. | Keep `false` outside short, authorized diagnostics. |

The lifecycle sets `HERMES_ACCEPT_HOOKS=1` only on its managed Hermes process;
it is not a private profile key to add casually. Gateway health only shows that
a gateway can run, not that Discord has delivered a message.

## Feature-gated Media and care flows

| Feature | Required keys | Default safety stance |
|---|---|---|
| Generic Media v1.1 | `MEDIA_V11_ENABLED`, `HERMES_MEDIA_TOOL_ENABLED`, `HERMES_MEDIA_FAST_PATH_ENABLED` all `true`; valid `HERMES_MEDIA_CALLBACK_SOCKET`. | The logical allowlist currently exposes only `elderly_hand_exercise`; Android mapping remains external. |
| Operator identity Demo | `DEMO_OPERATOR_IDENTITY_ENABLED`, `RESIDENT_IDENTITY_ENABLED`, `HERMES_DEMO_IDENTITY_TOOL_ENABLED`, `HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED`, identity socket and state dir. | Exact operator phrases only; no visual identity inference and no natural-language identity selection. |
| Repeated-discomfort Demo | `CARE_MEMORY_V2_ENABLED`, `DEMO_REPEATED_DISCOMFORT_ENABLED`, `DEMO_CARE_SCENARIO_PROMPT_ENABLED`, care root and care callback socket, plus the identity prerequisites. | Father-only synthetic flow; it does not diagnose or access unknown/mother partitions. |
| Visual routing / generic care context | `DEMO_RESIDENT_VISUAL_ROUTING_ENABLED`, `CARE_CONTEXT_ENABLED`. | Keep disabled unless the documented feature acceptance is in scope. |
| Identity bounds | `DEMO_IDENTITY_REFRESH_SECONDS`, `DEMO_IDENTITY_MAX_DURATION_SECONDS`. | Positive bounds; refresh cannot exceed duration. |

Do not enable a group by setting only some of its keys. `tools/demo_lifecycle.py`
and Bridge configuration reject partial combinations before they can become a
runtime route.

## Action viewer and Discord side channel

| Key | Role | Safe interpretation |
|---|---|---|
| `DEMO_ACTION_VIEWER_ENABLED` | Enables lifecycle ownership of the optional viewer. | Viewer is experimental perception, not a hardware dispatcher. |
| `DEMO_ACTION_VIEWER_MODEL` | Local model identifier. | Identifier only; model files remain external runtime assets. |
| `DEMO_ACTION_VIEWER_GGUF_MODEL_PATH` / `DEMO_ACTION_VIEWER_MMPROJ_PATH` | Local model asset locations. | Absolute private/operator paths; never commit actual values. |
| `DEMO_ACTION_VIEWER_LLAMA_SERVER` / `DEMO_ACTION_VIEWER_LLAMA_SERVER_PORT` | Local llama.cpp executable and service port. | Managed only through the canonical lifecycle when enabled. |
| `DEMO_ACTION_VIEWER_CUDA_VISIBLE_DEVICES` | Viewer GPU selection. | Separate from canonical LM Studio GPU policy. |
| `DEMO_ACTION_VIEWER_POSE_MODE` / `DEMO_ACTION_VIEWER_POSE_MODEL` / `DEMO_ACTION_VIEWER_POSE_DEVICE` | Optional pose backend selection. | Model/weights are runtime assets, not source evidence. |
| `DEMO_ACTION_VIEWER_MAX_OUTPUT_TOKENS` | Bounded model output. | Does not establish detection accuracy. |
| `DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH` | Explicit abnormal-event publication flag. | Keep `disabled` unless a human authorizes the Demo event path. |
| `DEMO_ACTION_VIEWER_DISCORD_NOTIFY` | Explicit Discord side-channel flag. | Keep `disabled` unless separately authorized; best-effort only. |
| `DEMO_ACTION_VIEWER_DISCORD_ENV_PATH` | Owner-only credential env containing `DISCORD_WEBHOOK_URL`. | The value is never printed, committed, or included in an export. |
| `DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK` | Legacy viewer pre-alert switch. | Viewer records Bridge-owned handling; it does not bypass Bridge command ownership. |
| `DEMO_START_TIMEOUT_SECONDS` | Bounded managed-service start wait. | Must remain in the lifecycle's accepted range. |

The viewer may expose boolean health fields such as credential configured or
notification enabled. They do not disclose a webhook or target and do not prove
delivery. Use [troubleshooting](demo_troubleshooting.md) and Bridge traces to
classify an observed notification result.

## Change checklist

- Update the sample key list, lifecycle parser, Bridge config, README/runbook,
  and tests together when a configuration contract changes.
- Do not write an actual secret, private address, account, or local runtime
  path into a reusable document.
- Run `python3 tools/validate_documentation.py` after documentation changes;
  use the [verification guide](verification_and_acceptance.md) for the wider
  test set.
