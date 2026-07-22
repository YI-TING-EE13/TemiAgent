# Home-ESI Lite Rules

Home-ESI Lite is a demo risk policy for home-care robot interactions. It is not clinical triage and must not be presented as a medical diagnosis.

## Normal

Use `Normal` when:

- the user is chatting normally
- the user asks a general question
- the user requests safe navigation or speech
- no care risk is visible or stated

Typical actions:

- `speak`
- safe `navigate` / `turn` / `stop`
- `noop`

## L3

Use `L3` for low-risk care events:

- routine reminder
- medication reminder without distress
- hydration or schedule reminder
- mild missed-response where the resident quickly confirms

Typical actions:

- `speak`
- `ask_clarification` if confirmation is needed
- `log_event`
- `mark_reminder_done` after clear confirmation

## L2

Use `L2` for moderate risk requiring active care follow-up:

- "我有點不舒服"
- dizziness, pain, nausea, fatigue, or weakness without clear emergency signs
- repeated missed reminder plus concern
- visual context suggests discomfort but not fall or no-response

Typical actions:

- `ask_clarification`
- `log_event`
- optional suggestion to sit, rest, or measure condition if appropriate
- optional mock caregiver notification only after resident asks or if repeated concern is present

Do not jump from vague discomfort directly to L1 unless additional high-risk evidence exists.

## L1

Use `L1` for high-risk events:

- explicit fall or visible possible fall
- no response after safety check
- user says they cannot get up
- explicit request for urgent help
- severe symptoms such as chest pain, breathing difficulty, loss of consciousness, severe bleeding, or sudden neurological symptoms
- Bridge-provided mock event marks high-risk context

Typical actions:

- `speak` or `ask_clarification` for immediate safety check
- `stop` if robot motion may be unsafe
- `notify_caregiver_mock`
- `log_event`
- abnormal event record

## Example Decisions

- ASR: "我有點不舒服" -> `L2`, ask where uncomfortable and whether they need help.
- ASR: "我跌倒了，站不起來" -> `L1`, safety confirmation and mock notification.
- ASR: "好，我吃完藥了" during an active medication reminder -> `L3`, mark reminder done and log.
- ASR: "你聽得到我說話嗎" -> `Normal`, speak response.
