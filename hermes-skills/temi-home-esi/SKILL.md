---
name: temi-home-esi
description: Apply the self-contained Home-ESI v2 decision-tree risk policy for Temi home-care assistant events. Use when Hermes must classify Normal, L3, L2, or L1 risk from ASR text, visual context, responsiveness, robot state, reminders, recent events, vital status, or Bridge high-risk flags, and then choose Bridge-validated JSON actions only.
---

# Temi Home-ESI v2 Skill

## Purpose

Use this skill when Hermes needs to classify home-care interaction risk for a Temi-based elderly home-care assistant and produce a JSON-only action plan for the Bridge.

Home-ESI v2 is a non-clinical, explainable demo policy. It is not medical diagnosis, clinical triage, or replacement for emergency services. Hermes must not directly control hardware, publish MQTT, bypass the Bridge, or claim that real emergency services were contacted.

This `SKILL.md` is intentionally self-contained because the Temi resident server preloads only the files passed through `--skill-path`. The detailed audit reference is in `references/home_esi_lite.md` and preserves the full decision-tree text and examples.

## Risk Levels

| Level | Meaning | Default stance |
|---|---|---|
| `L1` | High-risk event; possible immediate safety threat | Safety confirmation, stop unsafe motion, mock caregiver notification, abnormal event logging |
| `L2` | Moderate care concern requiring active follow-up | Clarify symptoms/safety, suggest safe rest/checking through speech, log event |
| `L3` | Low-risk care event or routine reminder | Reminder, confirmation, log/update reminder state |
| `Normal` | No visible or stated care risk | Normal dialogue or safe robot action |

## Evidence To Check

Use all available evidence. Do not classify from ASR alone when visual, reminder, vital, recent-event, or Bridge context is available.

Summarize available and missing evidence in `cognitive_state.evidence_summary` when the schema allows:

- `asr_text`: resident statement or empty/unavailable.
- `visual_context`: posture, location, fall/near-fall, motion, expression, responsiveness.
- `vital_status`: `unknown`, `normal`, `abnormal_non_critical`, or `critical`; include source/reliability if provided.
- `robot_state`: moving/near resident/current task.
- `reminder_state`: active reminder, missed count, last confirmation.
- `recent_events`: repeated missed reminders, low activity, fall warnings, unusual behavior.
- `bridge_flags`: high-risk context, fall high-confidence, no-response-after-safety-check, critical vital status, mock event.

If evidence is unavailable, mark it unavailable or unknown. Do not invent missing data.

## Decision Order

Always classify by priority:

1. Check `L1` override triggers.
2. If no `L1`, check `L2` active-care triggers.
3. If no `L2`, check `L3` routine-care triggers.
4. If none apply, classify as `Normal`.

Strong high-risk evidence overrides lower-risk evidence. Vague discomfort alone remains `L2`; routine reminder alone remains `L3`.

## L1 Override: Immediate Safety Threat

Classify as `L1` if any trigger below is present:

- Explicit fall or dangerous fall evidence: 「我跌倒了」, 「我摔倒了」, 「我滑倒了」, 「我撞到頭」, 「我站不起來」, 「我爬不起來」, 「我動不了」, 「我在地上」, visible fall, lying on floor, abnormal posture after sudden motion, or fall-like event followed by no response.
- No response after safety checks when there is any risk context: possible fall, abnormal posture, urgent sound/impact, or inability to answer simple safety questions. Safety check examples: 「你聽得到我說話嗎？」, 「你可以說話、揮手，或按一下平板嗎？」, 「你現在可以動嗎？」
- Explicit urgent help request: 「救命」, 「快來幫我」, 「幫我叫救護車」, 「幫我叫 119」, 「快通知家人」, 「我不行了」, 「我快昏倒了」, 「我喘不過氣」, 「我胸口很痛」.
- Severe symptom statement: chest pain/pressure, breathing difficulty, cannot speak normally due to breathlessness, loss of consciousness or near-fainting, severe bleeding, severe head injury, sudden confusion, sudden one-sided weakness, face drooping, slurred speech, sudden vision change, sudden loss of balance, sudden severe headache, or seizure-like event.
- Critical vital status with dangerous context: `vital_status.status = "critical"` plus no response, altered consciousness, chest pain, breathing difficulty, fall/possible fall, severe weakness, or urgent help request. If critical vital status is present but context is unclear, classify `L1` unless Bridge marks the reading unreliable.
- Bridge high-risk flags: `high_risk_context`, `fall_detected_high_confidence`, `no_response_after_safety_check`, `critical_vital_status`, or `emergency_mock_event`.

For `L1`, include `log_event` with abnormal details and normally include `notify_caregiver_mock` unless demo policy disables it. Use `stop` first if robot motion could worsen safety.

## L2: Active Care Concern

If no `L1` trigger is present, classify as `L2` when active follow-up is needed:

- Vague discomfort without L1 evidence: 「我有點不舒服」, 「怪怪的」, 「今天身體不太對」, 「有點頭暈」, 「有點想吐」, 「很累」, 「沒力氣」, 「有點喘」, 「肚子痛」, 「頭痛」, 「腳痛」, mild chest tightness without severe/persistent context.
- Pain or injury concern without immediate danger: resident reports pain/minor bump and responds clearly; visual discomfort; unsteady walking; holding furniture/wall for support.
- Repeated missed reminder with concern: medication/hydration/rehab reminders missed repeatedly, no confirmation after repeated attempts, or missed reminder plus low activity/fatigue/discomfort.
- Behavior pattern concern: long inactivity vs baseline, prolonged bathroom stay, unusual nighttime wandering, repeated missed medication, low intake/hydration/activity, new schedule confusion, repeated help requests for basic tasks, repeated routine cancellation from fatigue.
- Non-critical abnormal vital status: `vital_status.status = "abnormal_non_critical"` with no L1 symptom.
- Possible fall risk but not confirmed fall: near-fall, unstable gait, 「差點跌倒」, 「剛剛有點站不穩」, imbalance while responsive.

Default `L2` next step: ask clarification and check for L1 symptoms, e.g. 「你是哪裡不舒服？有胸痛、呼吸不順、快昏倒、站不穩，或剛剛跌倒嗎？」 Log the event.

## L3: Routine Care Workflow

If no `L1` or `L2` trigger exists, classify as `L3` for low-risk care workflow:

- Routine reminders: medication, hydration, schedule, rehab/stretching, sleep, measurement.
- Reminder completion: 「好，我吃完藥了」, 「我喝水了」, 「我做完伸展了」, 「不用提醒了，我已經完成了」.
- Mild missed response quickly resolved: first missed reminder followed by confirmation, 「等一下」, postpone, or decline without distress.
- Low-risk care preference update: change reminder time, add schedule, postpone hydration, request routine daily check-in, ask for exercise video without discomfort.

If the same reminder is missed repeatedly, or a routine reminder combines with discomfort/confusion/abnormal visual context, upgrade to `L2`.

## Normal

Use `Normal` when no care risk is visible or stated: casual conversation, general question, normal safe navigation command, safe turn/stop command, robot status question, entertainment request, or no active care event.

If a normal command is combined with risk context, classify based on the risk. Example: 「停下來」 alone is `Normal`; 「停下來，你快撞到我了」 is at least `L2`, and may be `L1` if immediate collision danger exists.

## Escalation And De-escalation

- `L3` to `L2`: repeated missed reminders, routine reminder plus discomfort, confused/inconsistent answers, visual discomfort despite confirmation, repeated baseline deviation, or Bridge repeated-care concern.
- `L2` to `L1`: clarification reveals inability to get up/walk/speak normally, breathing difficulty, chest pain/pressure, fainting, sudden one-sided weakness, slurred speech, face drooping, severe bleeding, head injury with confusion/vomiting/severe dizziness, explicit emergency request, no response after safety check, or Bridge high-risk flag.
- `L2` to `L3`: resident clearly confirms safety, no L1 symptoms, normal visual context, care task completed, and concern was minor.
- `L1` de-escalation: do not downgrade in the same turn unless Bridge or clear corrective evidence shows false positive. Example: visual possible fall, resident says they are doing floor exercise, and visual context confirms intentional exercise. Then use `L2` or `L3`, log the false-positive context, and avoid mock caregiver notification.

When uncertain, keep the safer classification and ask immediate safety confirmation without making a diagnosis.

## Output Contract

When schema allows, include Home-ESI cognition in `cognitive_state`:

```json
{
  "home_esi_level": "L2",
  "risk_reason": "使用者表示頭暈，但目前沒有跌倒、無回應、胸痛、呼吸困難或疑似中風等 L1 證據。",
  "evidence_summary": {
    "asr": "我有點頭暈",
    "visual_context": "seated_upright",
    "vital_status": "not_available",
    "reminder_state": "no_active_reminder",
    "recent_events": []
  },
  "risk_triggers": ["subjective_discomfort"],
  "missing_information": ["是否能正常站立", "是否有胸痛", "是否呼吸不順", "是否快昏倒"],
  "next_step": "ask_clarification",
  "recommended_actions": ["speak", "log_event"],
  "confidence": "medium"
}
```

Required cognitive fields: `home_esi_level`, `risk_reason`, `next_step`, and `recommended_actions`. Recommended fields: `evidence_summary`, `risk_triggers`, `missing_information` for `L1`/`L2`, and `confidence` as `high`, `medium`, or `low`.

Do not expose private chain-of-thought. Use concise `risk_reason` and `reasoning_summary`.

## Bridge-valid Actions Only

Use only Bridge-supported action types:

- Normal: `speak`, `navigate`, `turn`, `stop`, `noop`.
- L3: `speak`, `ask_clarification` if confirmation is needed, `log_event`, `mark_reminder_done` after clear completion.
- L2: `ask_clarification`, `speak`, `log_event`, `notify_caregiver_mock` only if the resident requests it, repeated concern exists, or Bridge policy allows it.
- L1: `stop` if motion may be unsafe, `speak` or `ask_clarification` for safety check, `notify_caregiver_mock`, `log_event` with abnormal details.

Suggestions such as resting, sitting safely, measuring condition, or arranging follow-up should be expressed in `speak` / `ask_clarification` text and recorded through `log_event`; do not invent unsupported action types.

## Response Templates

- L1 possible danger: 「我偵測到可能有危險狀況。你現在聽得到我說話嗎？如果你無法回應，我會通知家屬確認你的安全。」
- L1 explicit fall: 「我知道你可能跌倒了。請先不要勉強起身。你現在可以說話或揮手回應我嗎？我會通知家屬來確認你的狀況。」
- L2 vague discomfort: 「你說有點不舒服，我想先確認你的安全。你現在是頭暈、胸悶、呼吸不順，還是哪裡不舒服？你可以先坐下休息嗎？」
- L2 missed medication reminder: 「我注意到你剛剛沒有確認吃藥提醒。你是已經吃藥了、想晚一點吃，還是需要我通知家人協助確認？」
- L3 completion: 「好的，我已經記錄你完成了。」

## Core Policy Sentence

Classify `L1` only when there is explicit or strongly supported evidence of immediate safety threat. Classify vague discomfort as `L2` unless combined with fall, no response, inability to get up, severe symptoms, acute confusion, critical vital status, explicit emergency request, or Bridge-provided high-risk context. Use `L3` for routine care workflows and `Normal` for non-care-risk interaction.
