# Demo Configuration Reference

Status: <code>CURRENT_AUTHORITY</code>; Demo-only. Last reviewed for Gate 5 final
and L4 final evidence adoption: 2026-08-29.

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

## Gate 5 final observed runtime contract

Gate 5B Retry #4 is the accepted bounded host-runtime evidence. This section
records the values that must remain aligned in private configuration; it does
not authorize a start or change any runtime state.

| Boundary | Frozen requirement or observed evidence |
|---|---|
| Production LM ownership | <code>LMSTUDIO_OWNERSHIP=external</code>; the lifecycle must never start, stop, unload, daemon-down, server-stop or globally mutate production LM Studio. |
| External LM readiness | The provider is ready before Demo start; API identifier <code>google/gemma-4-31b</code>, provisioned model <code>temi/gemma-4-31b-it-qat</code>, and runtime context <code>64000</code> are checked from runtime metadata. Observed model maximum was <code>262144</code>; it is evidence for this deployment, not a portable pin. |
| MQTT | Explicit broker host/port/configuration is mandatory. The accepted run reused the independently managed broker without restart; a foreign listener is never adopted by port alone. |
| Hermes | Pinned base plus patches <code>0001</code>–<code>0010</code> must reconstruct final tree <code>47e9f1411e585769c055d0c6ee4417bebcdc6f70</code>. |
| Resident probe | L2 malformed input must fail validation before <code>ResidentHermes.invoke()</code>; it must be inference-impossible and produce HTTP 400. |
| Request budget | The accepted bounded run records exactly <code>L1=0; L2=0; L3=0; L5=1</code>. |
| Legacy broker endpoint input | <code>PC_IP</code> has no tracked private-LAN fallback; deployment-specific endpoints belong only in private owner configuration. |
| Ownership and portability | Lifecycle stop targets only positively owned identities. PIDs, run IDs, temporary roots and transient runtime directories are acceptance evidence only, not configuration requirements. |

The resulting state is <code>HOST_LIVE_VERIFIED</code> for this exact
publication/runtime contract. The adopted L4.7B record separately closes one
exact canonical Android/Temi TTS transaction as
<code>L4_FINAL=CLOSED_PASS</code>; video/media, camera/microphone, viewer/GPU
general readiness, Discord delivery and broader Android behavior remain
unverified. Gate 6 is ready for release/handover work only.

## Complete configuration inventory

Each token in the Keys covered column is one audited configuration input. The
classification is about where a value may come from:

| Classification | Meaning |
|---|---|
| <code>PUBLIC_DEFAULT</code> | A safe value or behavior defined by tracked source. |
| <code>PUBLIC_TEMPLATE</code> | A tracked non-secret template field that is intentionally replaced or resolved locally. |
| <code>REQUIRED_USER_INPUT</code> | A deployment, owner or maintainer value that cannot be guessed by the repository. |
| <code>PRIVATE_RUNTIME</code> | A value or path used only below the owner-only runtime root. |
| <code>SECRET</code> | A credential or token that belongs only in a private owner-controlled file. |
| <code>GENERATED_RUNTIME</code> | Set by lifecycle execution or written as state; not a template input. |
| <code>DEPRECATED</code> | Retained only for compatibility and not a new configuration surface. |

| Keys covered | Classification | Default or requirement | Tracked/example | Runtime location and validation |
|---|---|---|---|---|
| <code>DEMO_PROFILE</code>, <code>DEMO_GIT_BRANCH_POLICY</code>, <code>EXPECTED_GIT_BRANCH</code> | PUBLIC_TEMPLATE | Production uses required branch policy and <code>main</code>; newcomer mock disables branch-name enforcement. | <code>EXPECTED_GIT_BRANCH</code> is tracked in the production template; the newcomer mock intentionally omits it because its branch policy is disabled. | <code>tools/demo_lifecycle.py</code> reads and validates the expected branch when required; private env resolution validates profile and branch policy. |
| <code>TEMIAGENT_RUNTIME_ROOT</code>, <code>LOG_DIR</code>, <code>MEMORY_DIR</code>, <code>DEMO_CARE_MEMORY_ROOT</code> | PUBLIC_TEMPLATE / PRIVATE_RUNTIME | Template placeholders resolve below the owner-only runtime root. Care root is required only by the enabled care flow. | Placeholder paths only. | Private config and runtime root; lifecycle rejects relative, symlinked or out-of-root paths. |
| <code>TEMI_SHARED_BRIDGE_PATH</code>, <code>TEMI_SHARED_HERMES_PATH</code> | PUBLIC_TEMPLATE / PRIVATE_RUNTIME | Shared metadata root; canonical profile resolves both to the same private root. | Placeholder paths only. | Runtime data; lifecycle requires absolute matching roots under the selected runtime root. |
| <code>HERMES_MEDIA_CALLBACK_SOCKET</code>, <code>HERMES_DEMO_IDENTITY_CALLBACK_SOCKET</code>, <code>HERMES_DEMO_CARE_CALLBACK_SOCKET</code>, <code>DEMO_IDENTITY_STATE_DIR</code> | PRIVATE_RUNTIME | Private Unix sockets/state paths; identity/care paths are conditional. | Placeholder paths only. | Runtime state; required and checked when the corresponding feature gates are enabled. |
| <code>LMSTUDIO_OWNERSHIP</code>, <code>MQTT_OWNERSHIP</code>, <code>HERMES_GATEWAY_OWNERSHIP</code>, <code>MANAGE_ANDROID</code> | PUBLIC_TEMPLATE | Ownership is <code>managed</code>, <code>external</code> or <code>disabled</code>; Android is <code>0</code>. | Tracked safe values. | Private env; lifecycle requires ownership/enablement agreement and rejects Android management. |
| <code>LMSTUDIO_TARGET_DIR</code>, <code>LMSTUDIO_MODEL_ID</code>, <code>LMSTUDIO_API_IDENTIFIER</code>, <code>LMSTUDIO_SERVER_PORT</code> | REQUIRED_USER_INPUT / PUBLIC_DEFAULT | Production uses the external LM Studio location, canonical model ID, API identifier and port <code>1234</code>. | Identifier/default is tracked; local target is external/private. | External owner provisions the model/cache; lifecycle checks one listener and HTTP model-list readiness only. |
| <code>CONTEXT_LENGTH</code>, <code>LMSTUDIO_CONTEXT_LENGTH</code>, <code>LMSTUDIO_VISIBLE_GPUS</code> | PUBLIC_DEFAULT | <code>64000</code>, matching context values and visible devices <code>0,1</code>. | Tracked defaults. | Lifecycle rejects drift; GPU/driver remains an external pin gap. |
| <code>MQTT_BROKER_HOST</code>, <code>MQTT_BROKER_PORT</code>, <code>MQTT_CONFIG_PATH</code> | PUBLIC_DEFAULT / REQUIRED_USER_INPUT | Client default is loopback, port <code>1883</code>; managed production config must be an existing absolute broker config. | Host/port/config shape tracked; deployment endpoint is private. | Private env and broker supervisor; canonical MQTT-only mode additionally requires the tracked <code>mqtt/mosquitto.conf</code>. |
| <code>HERMES_GATEWAY_ENABLED</code> | PUBLIC_DEFAULT | Disabled in newcomer; production may explicitly enable it. | Tracked. | Lifecycle derives service inclusion; health is not Discord delivery proof. |
| <code>ROBOT_ID_ALLOWLIST</code>, <code>HERMES_INVOKE_MODE</code>, <code>HERMES_HTTP_URL</code>, <code>HERMES_TIMEOUT_SECONDS</code> | PUBLIC_TEMPLATE | Robot <code>temi-01</code>, HTTP invocation, resident loopback URL derived from port and bounded timeout. | Safe values/template. | Bridge/lifecycle config; robot allowlist and URL are validated before start. |
| <code>TRACE_ENABLED</code>, <code>TRACE_INCLUDE_ASR_TEXT</code>, <code>DEBUG_TRACE_FULL</code>, <code>TRACE_MAX_FIELD_CHARS</code> | PUBLIC_DEFAULT / PRIVATE_RUNTIME | Trace on, ASR text off in production sample, full debug off and bounded field size. | Safe values only. | Private logs/traces; content is runtime data and must remain redacted/bounded. |
| <code>ADAPTER_VISION_PORT</code>, <code>ADAPTER_FRAME_BROADCAST_PORT</code>, <code>RESIDENT_HTTP_PORT</code>, <code>VIEWER_HTTP_PORT</code>, <code>VIEWER_AUX_PORT</code> | PUBLIC_DEFAULT | Production <code>8080/8081/8765/8010/8011</code>; newcomer uses <code>29080/29081/29765/29010/29011</code>. | Safe port templates. | Lifecycle resolves and validates uniqueness/profile-specific ranges. |
| <code>MOCK_ANDROID_HEALTH_PORT</code>, <code>MOCK_DISCORD_PORT</code> | PUBLIC_DEFAULT | Newcomer-only high ports <code>29012/29013</code>. | Mock template only. | Lifecycle mock services; rejected outside the newcomer profile. |
| <code>MEDIA_V11_ENABLED</code>, <code>HERMES_MEDIA_TOOL_ENABLED</code>, <code>HERMES_MEDIA_FAST_PATH_ENABLED</code> | PUBLIC_TEMPLATE | All are true only in the reviewed media Demo templates. | Tracked safe defaults. | Bridge/runtime feature gates; native callback remains local and Android mapping is external. |
| <code>DEMO_OPERATOR_IDENTITY_ENABLED</code>, <code>RESIDENT_IDENTITY_ENABLED</code>, <code>HERMES_DEMO_IDENTITY_TOOL_ENABLED</code>, <code>HERMES_DEMO_IDENTITY_FAST_PATH_ENABLED</code> | PUBLIC_TEMPLATE | Disabled in newcomer; production sample enables the controlled Demo route. | Tracked flags. | Private identity state/callback; lifecycle requires compatible flags and never infers identity from speech. |
| <code>CARE_MEMORY_V2_ENABLED</code>, <code>DEMO_REPEATED_DISCOMFORT_ENABLED</code>, <code>DEMO_CARE_SCENARIO_PROMPT_ENABLED</code>, <code>CARE_CONTEXT_ENABLED</code>, <code>DEMO_RESIDENT_VISUAL_ROUTING_ENABLED</code> | PUBLIC_TEMPLATE | Newcomer disables care; production sample enables bounded synthetic care and keeps visual routing disabled. | Tracked flags. | Bridge/private memory; partial combinations fail closed. |
| <code>DEMO_IDENTITY_REFRESH_SECONDS</code>, <code>DEMO_IDENTITY_MAX_DURATION_SECONDS</code>, <code>DEMO_RESIDENT_CONTEXT_TTL_SECONDS</code>, <code>DEMO_RESIDENT_VISUAL_MINIMUM_CONFIDENCE</code> | PUBLIC_DEFAULT | Positive bounded identity/context values; confidence is not identity accuracy. | Safe defaults where present. | Bridge/runtime validation; no medical or recognition claim. |
| <code>DEMO_ACTION_VIEWER_ENABLED</code>, <code>DEMO_ACTION_VIEWER_MODEL</code>, <code>DEMO_ACTION_VIEWER_GGUF_MODEL_PATH</code>, <code>DEMO_ACTION_VIEWER_MMPROJ_PATH</code>, <code>DEMO_ACTION_VIEWER_LLAMA_SERVER</code>, <code>DEMO_ACTION_VIEWER_LLAMA_SERVER_PORT</code> | REQUIRED_USER_INPUT / PRIVATE_RUNTIME | Viewer is optional; production paths must identify externally provisioned model files and server. | Identifiers/templates tracked; actual paths external/private. | Viewer lifecycle and health; regular-file/executable checks apply. |
| <code>DEMO_ACTION_VIEWER_CUDA_VISIBLE_DEVICES</code>, <code>DEMO_ACTION_VIEWER_POSE_MODE</code>, <code>DEMO_ACTION_VIEWER_POSE_MODEL</code>, <code>DEMO_ACTION_VIEWER_POSE_DEVICE</code>, <code>DEMO_ACTION_VIEWER_MAX_OUTPUT_TOKENS</code> | PUBLIC_DEFAULT / REQUIRED_USER_INPUT | Viewer device/model settings are machine-dependent; output is bounded. | Safe shape only; pose provenance external. | Viewer process; GPU and optional weight remain external/pin-gap inputs. |
| <code>DEMO_ACTION_VIEWER_ABNORMAL_PUBLISH</code>, <code>DEMO_ACTION_VIEWER_PRE_ALERT_SPEAK</code>, <code>DEMO_ACTION_VIEWER_ABNORMAL_COOLDOWN_SECONDS</code> | PUBLIC_DEFAULT / DEPRECATED | Abnormal publication and pre-alert are disabled unless explicitly authorized; cooldown is bounded. | Tracked flags/defaults. | Viewer config; Bridge still owns command and notification boundaries. |
| <code>DEMO_ACTION_VIEWER_DISCORD_NOTIFY</code> | DEPRECATED | Must remain <code>disabled</code>; enabled is rejected. | Tracked retired switch. | Lifecycle validation; Bridge, not viewer, owns notification. |
| <code>ABNORMAL_CARE_CONFIRMATION_ENABLED</code>, <code>ABNORMAL_CARE_CONFIRMATION_TTL_SECONDS</code>, <code>ABNORMAL_CARE_CONFIRMATION_MIN_ASR_CONFIDENCE</code> | PUBLIC_DEFAULT / PRIVATE_RUNTIME | Bounded confirmation record and threshold. | Module template values are safe. | Bridge private memory/state; confirmation is not caregiver notification. |
| <code>ABNORMAL_CARE_EPISODE_ENABLED</code>, <code>ABNORMAL_CARE_FIRST_RESPONSE_TIMEOUT_SECONDS</code>, <code>ABNORMAL_CARE_SECOND_RESPONSE_TIMEOUT_SECONDS</code>, <code>ABNORMAL_CARE_TIMEOUT_POLL_SECONDS</code> | PUBLIC_TEMPLATE | Episode route and monotonic deadlines; disabled or enabled per profile. | Tracked values. | Bridge state machine; positive values are validated. |
| <code>ABNORMAL_NOTIFICATION_MODE</code>, <code>ABNORMAL_NOTIFICATION_TIMEOUT_SECONDS</code>, <code>ABNORMAL_NOTIFICATION_TEST_RECIPIENT_AUTHORIZED</code> | PUBLIC_DEFAULT / REQUIRED_USER_INPUT | <code>disabled</code> by default; <code>demo_mock</code> or real webhook requires explicit owner authorization. | No secret value tracked. | Bridge validates mode and bounded timeout; delivery is never inferred from configuration. |
| <code>DEMO_NOTIFICATION_MOCK_ENABLED</code>, <code>DEMO_NOTIFICATION_RECEIPT_ENABLED</code>, <code>DEMO_TEST_EVENT_INGRESS_ENABLED</code>, <code>DEMO_TEST_RESIDENT_ALLOWLIST</code> | PUBLIC_TEMPLATE | Mock receipt and formal test ingress are newcomer-only; real recipient is not used. | Tracked safe flags. | Bridge/lifecycle requires the complete mock combination and allowlist. |
| <code>ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH</code> | SECRET / REQUIRED_USER_INPUT | Required only for real webhook mode; never a value-bearing path in public output. | Empty in tracked templates. | Owner-only absolute regular non-symlink file, mode <code>0600</code>, outside worktrees. |
| <code>MQTT_USERNAME</code>, <code>MQTT_PASSWORD</code> | SECRET | Empty in examples; set only if the broker owner requires authentication. | Names only, no values. | Private env; never print or commit. |
| <code>DISCORD_WEBHOOK_URL</code> | SECRET | No default and never in the lifecycle template. | Only the variable name may appear in examples. | Separate private Discord env, owner-only mode <code>0600</code>; Bridge reads it only for the authorized route. |
| <code>TEMI_LM_API_KEY</code> | SECRET | Legacy local default may be a non-secret placeholder; any real provider key is private. | No real value tracked. | Legacy backend private environment only; never publish the placeholder as a credential. |
| <code>DEMO_START_TIMEOUT_SECONDS</code>, <code>DEMO_TEST_FORCE_HEALTH_FAILURE_SERVICE</code> | PUBLIC_DEFAULT / DEPRECATED | Start wait is bounded; forced viewer failure is test-only newcomer configuration. | Safe test values only. | Lifecycle validates range/profile; not a production feature. |
| <code>ABNORMAL_EVENT_PUBLISH_ENABLED</code>, <code>DISCORD_NOTIFY_ENABLED</code>, <code>DISCORD_ENV_FILE</code> | DEPRECATED | Legacy Bridge notification trio is accepted only for compatibility and maps to the new notification route. | Names may appear in module template; no credential value. | Bridge compatibility parser; use <code>ABNORMAL_NOTIFICATION_*</code> for new work. |
| <code>HERMES_CLI_COMMAND</code>, <code>HERMES_MOCK_RESPONSE_TEXT</code>, <code>MAX_ACTIONS_PER_EVENT</code>, <code>MAX_IMAGE_SIZE_MB</code>, <code>EVENT_DEDUP_TTL_SECONDS</code>, <code>LOG_LEVEL</code> | PUBLIC_TEMPLATE / PRIVATE_RUNTIME | Direct Bridge module inputs; mock text is synthetic and limits are bounded. | Tracked module template. | Bridge config; direct-module values are not a second lifecycle orchestrator. |
| <code>CARE_CONTEXT_MAX_CHARS</code>, <code>CARE_CONTEXT_MAX_EVENTS</code> | PUBLIC_TEMPLATE / PRIVATE_RUNTIME | Bounded Bridge context limits. | Names/defaults only. | Bridge config; values are bounded before context construction. |
| <code>TEMI_MQTT_BROKER</code>, <code>TEMI_MQTT_PORT</code>, <code>TEMI_MQTT_CLIENT_ID</code>, <code>TEMI_VISION_HOST</code>, <code>TEMI_VISION_PORT</code> | PUBLIC_DEFAULT / DEPRECATED | Direct legacy backend route; defaults are local and not the canonical Demo lifecycle. | Declared in legacy module source. | <code>temi_backend</code> private/direct module environment; use only with its legacy README. |
| <code>TEMI_ENABLE_FRAME_BROADCAST</code>, <code>TEMI_FRAME_BROADCAST_HOST</code>, <code>TEMI_FRAME_BROADCAST_PORT</code>, <code>TEMI_FRAME_BROADCAST_JPEG_QUALITY</code>, <code>TEMI_ENABLE_DEBUG_FRAMES</code>, <code>TEMI_DEBUG_FRAMES_DIR</code> | PUBLIC_DEFAULT / PRIVATE_RUNTIME / DEPRECATED | Legacy camera broadcast/debug controls; generated frames remain runtime data. | Source defaults; no private values. | Legacy backend runtime; paths must not point at tracked publication data. |
| <code>TEMI_LM_BASE_URL</code>, <code>TEMI_LM_MODEL</code>, <code>TEMI_SKILLS_PROMPT_FILE</code> | PUBLIC_DEFAULT / REQUIRED_USER_INPUT / DEPRECATED | Legacy local VLM URL/model/prompt inputs; not canonical resident Hermes config. | Source defaults; local paths external. | Legacy backend only; do not treat as current production model authority. |
| <code>HERMES_ACCEPT_HOOKS</code>, <code>LMSTUDIO_PROJECT_ROOT</code>, <code>TRACE_RUN_ID</code>, <code>PYTHONUNBUFFERED</code> | GENERATED_RUNTIME | Lifecycle-injected resolved values and run identity. | Not user templates. | Process environment/state; generated values must not be copied into public docs as private defaults. Resolved user keys are listed in their owning rows above. |

This inventory intentionally distinguishes the tracked production and newcomer
templates from direct Bridge/backend module inputs. The lifecycle may pass
resolved values to those modules, but direct module READMEs do not create an
alternate current deployment contract.

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

## Secret management contract

Allowed secret-bearing inputs are limited to credentials required by an
explicitly owned external service: MQTT username/password when the broker
requires authentication, a real LM Studio/provider API key for the legacy
route, and <code>DISCORD_WEBHOOK_URL</code> for an explicitly authorized
Bridge notification mode. Empty values and the local <code>lm-studio</code>
placeholder in examples are not real credentials.

| Secret material | Location | Permission and validation |
|---|---|---|
| Private lifecycle/config values | Ignored <code>/TemiAgent/.runtime/demo/demo.env</code> or an explicitly supplied absolute private env outside every worktree. | Lifecycle user owns the file, exact mode <code>0600</code>; parent/runtime directories are owner-only. |
| MQTT username/password | Private lifecycle or broker-owner env only. | Never print, commit or place in a command-line argument; blank tracked examples are safe placeholders. |
| Discord webhook | Separate private env named by <code>ABNORMAL_NOTIFICATION_DISCORD_ENV_PATH</code>. | Regular non-symlink file, lifecycle-user-owned, exact mode <code>0600</code>, outside all Git worktrees, with the variable name <code>DISCORD_WEBHOOK_URL</code>. |
| External model/provider keys | The external owner’s secret store or private env. | Do not add a token to a model path, URL, README, trace or fixture. |

Create local configuration with <code>./scripts/demo init-config</code>. Do not
copy a real private env into a tracked template. To audit whether a file has
entered the index without printing its contents, use:

~~~bash
git status --short --ignored
git ls-files --error-unmatch .runtime 2>/dev/null
git ls-files --error-unmatch .env 2>/dev/null
~~~

The two <code>git ls-files</code> checks should fail for ignored runtime/env
paths. If a secret-bearing path is tracked, stop publication review, preserve
the evidence and ask a maintainer to remove it through the repository’s
approved remediation process; do not paste the value into an issue or log.
Before handover, run the repository secret/private-path scan and inspect only
filenames, status and redacted diagnostics.

Never commit credentials, webhook URLs, private LAN addresses, user-specific
paths, raw care records, images, full prompts, runtime exports or payload-bearing
logs. Never use a credential as a public default, and never claim notification
delivery from the presence of a credential or a healthy viewer.

## Dependency profile

| Key | Canonical sample value / role | Validation boundary |
|---|---|---|
| `LMSTUDIO_OWNERSHIP` | `external` for production; `managed` only for the `newcomer_mock` LM test double. | Production lifecycle records no LM owner and never stops or reconfigures the provider. |
| `LMSTUDIO_TARGET_DIR` | External LM Studio installation/data location; mock data root for `newcomer_mock`. | Production lifecycle does not access or mutate this path. |
| `LMSTUDIO_MODEL_ID` | Logical Demo model ID. | Lifecycle checks the canonical model policy. |
| `LMSTUDIO_API_IDENTIFIER` | OpenAI-compatible model identifier. | Must match the reviewed Demo profile. |
| `LMSTUDIO_SERVER_PORT` | External LM Studio API listener, normally `1234`. | Production requires one listener and a compatible `/v1/models` response; the lifecycle never binds or reclaims the port. |
| `CONTEXT_LENGTH` / `LMSTUDIO_CONTEXT_LENGTH` | Both `64000` for the canonical Demo. | Must agree; the lifecycle rejects drift. The external owner provisions the model context. |
| `LMSTUDIO_VISIBLE_GPUS` | `0,1` for the canonical Demo. | The lifecycle rejects policy drift but does not assign or reconfigure GPUs. |
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
| Git policy | `DEMO_GIT_BRANCH_POLICY=required` and `EXPECTED_GIT_BRANCH=main` in the production template. A different branch or detached HEAD fails source validation when the required policy is enabled. | The sample sets `DEMO_GIT_BRANCH_POLICY=disabled` deliberately and omits <code>EXPECTED_GIT_BRANCH</code>, so a disposable clone may be detached. This disables only the branch-name gate, not clean-source, resource, Bridge, or exact-PID checks. |
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
