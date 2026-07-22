# Structured Care Memory Contract

Hermes may reason over structured memory, but HermesTemiBridge or an approved memory tool is responsible for actual persistence.

## Authoritative Files

```text
memory/profile.json
memory/daily_state.json
memory/reminders.json
memory/event_log.jsonl
memory/summaries/<YYYY-MM-DD>.md
memory/abnormal_events/<event_id>.json
```

## File Responsibilities

- `profile.json`: resident identity, preferred name, language, communication preferences, reminder defaults, mock caregiver contacts.
- `daily_state.json`: current date, risk state, last seen location, last interaction, active reminder IDs, recent event IDs.
- `reminders.json`: scheduled and active reminders; reminder completion state is authoritative here.
- `event_log.jsonl`: append-only audit log for important interactions, reminders, risk decisions, and outcomes.
- `summaries/`: generated daily care summaries.
- `abnormal_events/`: expanded records for L1 or notable L2 events.

## Hermes Action Expectations

When Hermes needs memory persistence, it should output JSON actions rather than writing files directly.

Use `log_event` for:

- completed reminders
- user discomfort or help requests
- possible fall or no-response events
- mock notification attempts
- generated summaries

Use `mark_reminder_done` only when the resident has clearly confirmed completion by voice, gesture, or Bridge-provided context.

Use `update_memory` for stable resident facts, not for every event. Examples:

- resident prefers shorter prompts
- resident prefers a particular reminder wording
- caregiver mock contact changed

Use `generate_summary` at demo end or when asked what happened today.

Use `notify_caregiver_mock` only for demo notification intent. It must be logged as mock.

## Holographic Provider Sync

The Holographic memory provider may receive compact facts derived from structured events. Recommended tags:

```text
resident:elder_001
care_profile
reminder
event_summary
abnormal_event
home_esi:L1
home_esi:L2
```

Do not sync full raw event payloads or image bytes to Holographic memory. Sync short summaries that improve later recall.
