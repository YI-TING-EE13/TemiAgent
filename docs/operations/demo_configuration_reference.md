# Demo Configuration Reference

Status: maintained, Demo-only. Last reviewed: 2026-07-31.

This is the non-secret reference for the complete key set in
[`config/demo.env.example`](../../config/demo.env.example). The default private
file is the exact ignored owner-only `/TemiAgent/.runtime/demo/demo.env`, made
by `scripts/demo init-config`; explicit custom configs remain outside every
worktree. `tools/demo_lifecycle.py` and Bridge `BridgeConfig` are authoritative.

Never copy a private env, Discord env, token, webhook, account name, real
endpoint, user-specific host path, care record, or runtime export into Git.
`doctor` and `status` may inspect a private config but must not print its secret
values.

## Preparation and source of truth

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --sources
./scripts/demo init-config
./scripts/demo doctor
```

The initializer is idempotent and will not overwrite the canonical config
without `--force`. The normal command path is in the [Demo operator guide](DEMO_OPERATOR_GUIDE.md);
this reference does not authorize a start, restart, notification test, raw MQTT publish, or hardware
action.

## Rules that apply to every group

| Rule | Meaning |
|---|---|
| Private-file ownership | The private env and its parent are owned only by the lifecycle user; the env mode is exactly `0600`. |
| Canonical runtime root | Default mutable paths are below ignored `/TemiAgent/.runtime/demo`; explicit custom roots remain outside every Git worktree and owner-only. |
| Ownership vocabulary | `managed` means `scripts/demo` owns start, exact-PID recording and stop; `external` is health-checked only; `disabled` applies only to optional services. |
| No implicit adoption | A listener or PID that is not an expected recorded identity fails closed; the lifecycle does not kill by process name. |
| Defaults are not proof | A configured endpoint, gateway connection or webhook presence does not prove Android execution or notification delivery. |

## Runtime paths

| Key | Required form / purpose | Constraint |
|---|---|---|
| `TEMIAGENT_RUNTIME_ROOT` | Owner-only canonical root for all lifecycle state. | Default is exact ignored `/TemiAgent/.runtime/demo`; custom roots must be outside every Git worktree. |
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

## Profile and branch policy

`DemoConfig` resolves one profile before the lifecycle constructs service
specifications, commands, health probes, ownership records, or ports. A
profile is therefore not a second orchestrator and must not be assembled by
ad-hoc shell commands.

| Key / profile | Production contract | `newcomer_mock` contract |
|---|---|---|
| `DEMO_PROFILE` | Omit it or set `production`. | Set exactly `newcomer_mock` in the tracked [`config/demo.mock.env.example`](../../config/demo.mock.env.example). |
| Git policy | `DEMO_GIT_BRANCH_POLICY=required` and `EXPECTED_GIT_BRANCH=main` by default. A different branch or detached HEAD fails source validation. | The sample sets `DEMO_GIT_BRANCH_POLICY=disabled` deliberately, so a disposable clone may be detached. This disables only the branch-name gate, not clean-source, resource, Bridge, or exact-PID checks. |
| Model and broker | LM Studio `1234`; MQTT `1883`. | Local test doubles at `29134` and `29183`; neither contacts a GPU model or a real broker outside the profile. |
| Adapter, resident, viewer | Adapter `8080/8081`, resident `8765`, viewer `8010/8011`. | Adapter `29080/29081`, resident `29765`, viewer `29010/29011`; Android and Discord test doubles use `29012` and `29013`. |
| Runtime data | Ignored canonical root after `init-config --profile production --force`. | Ignored canonical root after the default `init-config`; no temporary config discovery occurs. |

All mock ports are loopback high ports. `DemoConfig` rejects a production-port
drift, a low or duplicate mock port, a mock URL not derived from the resolved
ports, a non-loopback mock broker, or a mock gateway/Android ownership change.
The production defaults remain model `google/gemma-4-31b`, context `64000`,
GPUs `0,1`, and `MANAGE_ANDROID=0`.

The mock resident returns only structured action plans to the existing Bridge;
it never publishes MQTT or commands. The mock Android executor consumes the
canonical Bridge command topic and publishes canonical results. Consequently
action validation, Bridge dispatch, service specs, locks, health, status,
restart, stop, and exact-PID ownership are the same lifecycle path as the
production profile.

Use `doctor` as a machine-readable readiness report, not as an assertion that
an unchecked service works. Every check has `name`, `status`, `code`,
`message`, and `required`. A required unavailable endpoint, timeout, malformed
health payload, missing entrypoint, or unowned listener is `FAIL` and makes the
CLI exit non-zero. A not-yet-started managed endpoint is `WARNING`; a profile
or real-device exclusion is `SKIPPED`; neither makes the command fail.

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
| Visual routing / care context | `DEMO_RESIDENT_VISUAL_ROUTING_ENABLED`, `CARE_CONTEXT_ENABLED`. | Keep visual routing disabled. Production reminder acceptance requires `CARE_CONTEXT_ENABLED=true` so active reminders reach Hermes; the generic unknown-resident route remains disabled. |
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
| `DEMO_ACTION_VIEWER_DISCORD_NOTIFY` | Retired viewer-owned Discord flag. | Must remain `disabled`; lifecycle rejects `enabled` because the Bridge owns notification delivery. |
| `DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK` | Legacy viewer pre-alert switch. | Viewer records Bridge-owned handling; it does not bypass Bridge command ownership. |
| `DEMO_START_TIMEOUT_SECONDS` | Bounded managed-service start wait. | Must remain in the lifecycle's accepted range. |

The viewer health surface does not prove notification delivery. Use Bridge trace
and the abnormal-care episode receipt to classify an observed result.

### Viewer health and normalized notification route

`tools/demo_lifecycle.py` normalizes the notification route and passes complete
typed metadata to `temi_action_viewer.py`. The viewer records only
redacted route state; it does not open the credential file or send Discord.
The typed fields are `discord_notify_enabled`, `discord_env_path`,
`discord_test_mode`, `demo_notification_mock_enabled`, and
`demo_notification_mock_receipt_enabled`. `discord_env_path` is not included
in `/health` output.

The viewer `/health` response contains these component objects:
`viewer_core`, `event_ingestion`, `frame_state`, `real_discord`, and
`demo_notification_mock`. With `ABNORMAL_NOTIFICATION_MODE=disabled`, health
returns HTTP 200 with real Discord and the Demo mock marked disabled. With
`ABNORMAL_NOTIFICATION_MODE=demo_mock` and both mock flags enabled, health
returns HTTP 200 and marks the mock receipt route available. With
`ABNORMAL_NOTIFICATION_MODE=discord_webhook`, the lifecycle validates the
credential file before start; a healthy viewer marks real Discord
`skipped_by_viewer` because the Bridge alone owns delivery.

An unexpected health-snapshot exception returns HTTP 503 with
`VIEWER_HEALTH_INTERNAL_ERROR`. That response and lifecycle/doctor output MUST
not expose a credential value or a full private credential path. The `viewer`
doctor check requires all five component objects as well as the normal source
and llama readiness fields.

## Immediate abnormal-care and notification route

The Bridge requires `ABNORMAL_CARE_EPISODE_ENABLED=true` for the current
abnormal-care route. `ABNORMAL_CARE_FIRST_RESPONSE_TIMEOUT_SECONDS`,
`ABNORMAL_CARE_SECOND_RESPONSE_TIMEOUT_SECONDS`, and
`ABNORMAL_CARE_TIMEOUT_POLL_SECONDS` must be positive and define the persisted
monotonic state-machine deadlines.

| Key | Role | Constraint |
|---|---|---|
| `ABNORMAL_NOTIFICATION_MODE` | Bridge notification adapter. | `disabled` by default; only `demo_mock` or `discord_webhook` enable an attempt. |
| `DEMO_NOTIFICATION_MOCK_ENABLED` and `DEMO_NOTIFICATION_RECEIPT_ENABLED` | Demo mock receipt gate. | Both must be `true` with `ABNORMAL_NOTIFICATION_MODE=demo_mock`; this route has no network recipient. |
| `ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH` | Owner-only Discord credential env. | Required for `discord_webhook`; an absolute regular non-symlink, lifecycle-user-owned, exact mode `0600`, outside every Git worktree, and containing `DISCORD_WEBHOOK_URL`. |
| `ABNORMAL_NOTIFICATION_TEST_RECIPIENT_AUTHORIZED` | Explicit test-recipient gate. | A test event cannot use real Discord unless this is `true`; never infer authorization from a caregiver webhook. |
| `DEMO_TEST_EVENT_INGRESS_ENABLED` | Formal synthetic abnormal injector gate. | Default `false`; set `true` only for a bounded Demo mock run. |
| `DEMO_TEST_RESIDENT_ALLOWLIST` | Accepted synthetic resident identifiers. | Test event metadata outside this allowlist is rejected before notification/Hermes. |

For compatibility, a private Bridge env may set
`ABNORMAL_EVENT_PUBLISH_ENABLED=true`, `DISCORD_NOTIFY_ENABLED=true`, and
`DISCORD_ENV_FILE=<owner-only credential env>`. The Bridge maps that complete
legacy trio to `discord_webhook`. The credential env, not the lifecycle env,
contains `DISCORD_WEBHOOK_URL`; the webhook value is never read from a command
line or written to a trace. New configuration SHOULD use the
`ABNORMAL_NOTIFICATION_*` keys above.

Use `scripts/inject_demo_event` rather than publishing a command or an Android
result. The complete synthetic-event and receipt boundary is in
[immediate abnormal-care flow](immediate_abnormal_care_flow.md).

## Change checklist

- Update the sample key list, lifecycle parser, Bridge config, README/runbook,
  and tests together when a configuration contract changes.
- Do not write an actual secret, private address, account, or local runtime
  path into a reusable document.
- Run `python3 tools/validate_documentation.py` after documentation changes;
  use the [verification guide](verification_and_acceptance.md) for the wider
  test set.
