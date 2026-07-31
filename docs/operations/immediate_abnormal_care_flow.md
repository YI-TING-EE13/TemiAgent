# Immediate abnormal-care flow

Status: Demo-only implementation. Last reviewed: 2026-07-31.

The Bridge owns the abnormal-care workflow. It is not a medical diagnosis,
emergency service, guaranteed fall detector, or a substitute for an existing
human emergency process.

## Flow and ownership

```text
validated perception.abnormal event
  -> Bridge persists DETECTED episode
  -> Bridge sends one immediate notification stage
  -> Bridge invokes Resident Hermes
  -> Bridge validates Hermes JSON and publishes canonical cmd/request
  -> Temi Android publishes canonical cmd/result
  -> Bridge processes reply, timeout, or one escalation stage
```

The viewer and formal injector only publish `temi/{robot_id}/perception/abnormal`.
They never publish `cmd/request`, `cmd/result`, or a Discord webhook. Hermes
returns a JSON plan only. The Bridge validates the event, evidence paths,
Hermes plan, action types, and Android-facing command.

## Canonical event and episode contract

The authoritative schema is
[`hermes_temi_bridge/schemas/perception_abnormal_event.schema.json`](../../hermes_temi_bridge/schemas/perception_abnormal_event.schema.json).
The reader copy is byte-identical at
[`docs/schemas/perception_abnormal_event.schema.json`](../schemas/perception_abnormal_event.schema.json).

Supported event types are `falls_down`, `lies_on_floor`, `fight`, and
`other_allowlisted`. A Demo injector event must include `test=true`,
`resident_id`, `request_id`, `run_id`, and `scenario_id`. The Bridge rejects a
test resident absent from `DEMO_TEST_RESIDENT_ALLOWLIST` before notification or
Hermes invocation.

Episode states are:

```text
DETECTED -> INITIAL_ALERT_SENT -> AWAITING_FIRST_RESPONSE
  -> RESIDENT_RESPONDED -> RESOLVED
  -> FOLLOW_UP_REQUIRED -> NO_RESPONSE -> ESCALATION_SENT | EXPIRED
```

`MEMORY_DIR/abnormal_care_episodes.json` holds bounded, atomic operational
state: IDs, the detected timestamp, test metadata, monotonic deadlines, state
transitions, and redacted stage receipts. It excludes raw ASR, evidence,
prompts, recipient details, webhook URLs, and credentials. A notification
stage is reserved on disk before external I/O; a restart therefore does not
send it again if the process exits before a receipt is recorded.

The Bridge sends `initial_alert` immediately after validation. A resident reply
creates one deduplicated `status_update`; an assistance reply or an okay reply
keeps Hermes in the care dialogue, and a second okay reply may resolve the
episode. Ambiguous speech receives at most one clarification and remains
active for the timeout path. The first monotonic timeout emits a single
Hermes-generated recheck; the second timeout attempts one deduplicated
`escalation` notification, then sends the final care TTS only after a receipt.
A delivery is never claimed unless the receipt is `mock_delivered` in the
explicit Demo mock route or `delivered` after Discord HTTP 204 in the real
route.

## Notification modes

| Mode | Required settings | Delivery claim |
|---|---|---|
| `disabled` | Default production-safe state. | No notification is sent. |
| `demo_mock` | `DEMO_NOTIFICATION_MOCK_ENABLED=true` and `DEMO_NOTIFICATION_RECEIPT_ENABLED=true`. | `mock_delivered`; no network recipient is contacted. |
| `discord_webhook` | Owner-only `0600` credential file plus an authorized recipient. | Only HTTP 204 is `delivered`; 401/403/404/429/timeout/connection errors are failures. A test event additionally requires the explicit authorized-recipient flag. |

`DEMO_TEST_EVENT_INGRESS_ENABLED` defaults to `false`. A test event using a
real Discord route also requires
`ABNORMAL_NOTIFICATION_TEST_RECIPIENT_AUTHORIZED=true`; operators must not
infer this from a production caregiver webhook.

## Formal Demo injection

Only run this after `scripts/demo doctor` and `scripts/demo start` report the
documented lifecycle readiness. The private config must be an owner-only `0600`
file outside every worktree and must explicitly select the Demo mock route.

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
./scripts/inject_demo_event \
  --config <PRIVATE_CONFIG> \
  --event falls_down \
  --resident-id <TEST_RESIDENT> \
  --run-id <RUN_ID> \
  --scenario-id A1
```

The injector writes three synthetic JPEGs below the configured external
runtime root and publishes only the canonical abnormal topic. Do not replace it
with `cmd/request`, a Resident private method, or a fabricated Android result.

## Verification and recovery

Run the focused, hardware-free checks in the designated container:

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest tests.test_care_episode tests.test_abnormal_notification tests.test_abnormal_care_confirmation tests.test_event_validation tests.test_cross_service_contract_schemas
```

The isolated lifecycle E2E verifier covers canonical event ingress, Resident
Hermes, Bridge validation, mock Android command/result, restart-safe dedup,
and local loopback Discord HTTP classifications. It never contacts a real
recipient. Stop only through `./scripts/demo --config <PRIVATE_CONFIG> stop`;
that command targets recorded lifecycle PIDs and preserves externally owned
services.
