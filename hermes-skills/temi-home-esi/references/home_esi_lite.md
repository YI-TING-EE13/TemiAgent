# Home-ESI v2 Decision Tree Reference

This file keeps the legacy `home_esi_lite.md` path for compatibility, but the policy content is Home-ESI v2. Use it as the detailed audit/reference version of the concise, self-contained `SKILL.md`.

## Table of Contents

1. [Purpose](#1-purpose)
2. [Non-clinical Scope and Safety Constraints](#2-non-clinical-scope-and-safety-constraints)
3. [Evidence Inputs](#3-evidence-inputs)
4. [Decision Priority](#4-decision-priority)
5. [Decision Tree](#5-decision-tree)
6. [Escalation Rules](#6-escalation-rules)
7. [Output Expectations](#7-output-expectations)
8. [Allowed Action Patterns by Level](#8-allowed-action-patterns-by-level)
9. [Recommended Response Templates](#9-recommended-response-templates)
10. [Example Decisions](#10-example-decisions)
11. [Testing Checklist](#11-testing-checklist)
12. [Core Policy Sentence](#12-core-policy-sentence)

---

## 1. Purpose

Use this skill when Hermes needs to classify home-care interaction risk for a Temi-based elderly home-care assistant.

The goal is **not** medical diagnosis, clinical triage, or replacement of emergency services. The goal is to support a conservative, explainable, first-stage home-care demo policy for deciding whether the robot should:

* respond normally,
* provide a routine care reminder,
* ask care-related clarification,
* log an event,
* stop unsafe movement,
* or request mock caregiver notification through Bridge-validated actions.

Home-ESI v2 classifies interaction risk into four levels:

| Level    | Meaning                                           | Default system stance                                                                                  |
| -------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `L1`     | High-risk event; possible immediate safety threat | Immediate safety confirmation, stop unsafe motion, mock caregiver notification, abnormal event logging |
| `L2`     | Moderate care concern; requires active follow-up  | Ask clarification, suggest safe rest/checking, log event, optionally ask whether to notify caregiver   |
| `L3`     | Low-risk care event or routine reminder           | Reminder, confirmation, log event, update reminder state                                               |
| `Normal` | No visible or stated care risk                    | Normal dialogue or safe robot action                                                                   |

---

## 2. Non-clinical Scope and Safety Constraints

Hermes must follow these constraints:

1. Do **not** make a medical diagnosis.
2. Do **not** claim that real emergency services were contacted.
3. Use `notify_caregiver_mock` only as a demo notification intent.
4. Do **not** classify vague discomfort as `L1` unless additional high-risk evidence exists.
5. Prefer `L2` + clarification when the resident says vague statements such as:

   * 「我有點不舒服」
   * 「怪怪的」
   * 「有點頭暈」
   * 「今天很累」
6. Upgrade to `L1` when there is explicit high-risk evidence:

   * fall with inability to get up,
   * visible possible fall with no response,
   * explicit urgent help request,
   * severe symptoms,
   * acute confusion or no response,
   * critical vital status with dangerous symptoms,
   * or Bridge-provided high-risk context.
7. For `L1`, always include an abnormal event log intent.
8. For `L1`, stop or avoid robot movement if robot motion may worsen safety.
9. If evidence is conflicting, prioritize user safety while avoiding unnecessary alarm escalation:

   * strong high-risk evidence overrides lower-risk evidence,
   * vague discomfort alone remains `L2`,
   * routine reminder alone remains `L3`.

---

## 3. Evidence Inputs

When classifying Home-ESI level, use all available evidence, not only ASR text.

Expected evidence channels may include:

```json
{
  "asr_text": "我有點頭暈",
  "visual_context": {
    "posture": "seated_upright",
    "location": "living_room",
    "motion_state": "low_activity",
    "fall_detected": false,
    "face_expression": "uncomfortable"
  },
  "vital_status": {
    "status": "unknown | normal | abnormal_non_critical | critical",
    "signals": ["heart_rate_high", "blood_pressure_high"],
    "source": "bridge | sensor | unavailable"
  },
  "robot_state": {
    "is_moving": false,
    "current_task": "reminder | navigation | conversation | idle"
  },
  "reminder_state": {
    "active_reminder": "medication | hydration | rehab | schedule | none",
    "missed_count": 0,
    "last_confirmation": "confirmed | denied | no_response | unknown"
  },
  "recent_events": [
    "missed_medication_reminder",
    "low_activity_2h",
    "fall_warning"
  ],
  "bridge_flags": [
    "high_risk_context",
    "fall_detected_high_confidence",
    "mock_event"
  ]
}
```

When a channel is unavailable, explicitly mark it as unavailable or unknown in the evidence summary. Do not hallucinate missing data.

---

## 4. Decision Priority

Home-ESI v2 uses a priority-based decision tree.

Always classify in this order:

1. Check `L1` override triggers.
2. If no `L1`, check `L2` active-care triggers.
3. If no `L2`, check `L3` routine-care triggers.
4. If none apply, classify as `Normal`.

High-risk evidence overrides low-risk evidence.

---

## 5. Decision Tree

### Step 0 — Confirm available evidence

Before assigning a level, identify:

* What did the resident say?
* What does the visual context show?
* Is the resident responsive?
* Is there a fall or possible fall?
* Is the robot moving or near the resident?
* Is there an active reminder?
* Are there recent repeated missed responses?
* Are vital signs unavailable, normal, abnormal, or critical?
* Did Bridge provide a high-risk flag?

If key evidence is missing, classify based on available evidence and include `missing_information`.

---

### Step 1 — L1 override: possible immediate safety threat

Classify as `L1` if **any** of the following is true.

#### L1-A. Explicit fall with danger evidence

Use `L1` when the resident says or the system detects:

* 「我跌倒了」
* 「我摔倒了」
* 「我滑倒了」
* 「我撞到頭」
* 「我站不起來」
* 「我爬不起來」
* 「我動不了」
* 「我在地上」
* visible fall or possible fall,
* lying on the floor,
* abnormal posture after sudden movement,
* fall-like event followed by no response.

Strong L1 examples:

* ASR: 「我跌倒了，站不起來」
* ASR: 「我滑倒了，頭撞到」
* Visual: resident lying on bathroom floor + no response
* Visual: sudden fall motion + long inactivity

#### L1-B. No response after safety check

Use `L1` when:

* resident does not respond after repeated safety checks,
* possible fall + no response,
* abnormal posture + no response,
* urgent event sound or impact + no response,
* resident cannot answer simple safety questions.

Suggested safety check sequence:

1. 「你聽得到我說話嗎？」
2. 「你可以說話、揮手，或按一下平板嗎？」
3. 「你現在可以動嗎？」

If no response after repeated safety checks and there is any risk context, classify as `L1`.

#### L1-C. Explicit urgent help request

Use `L1` when the resident says:

* 「救命」
* 「快來幫我」
* 「幫我叫救護車」
* 「幫我叫 119」
* 「快通知家人」
* 「我不行了」
* 「我快昏倒了」
* 「我喘不過氣」
* 「我胸口很痛」

#### L1-D. Severe symptom statement

Use `L1` when the resident reports symptoms that may indicate immediate danger, especially:

* chest pain or chest pressure,
* breathing difficulty,
* cannot speak normally due to breathlessness,
* loss of consciousness or near-fainting,
* severe bleeding,
* severe head injury,
* sudden confusion,
* sudden one-sided weakness,
* face drooping,
* slurred speech,
* sudden vision change,
* sudden loss of balance,
* sudden severe headache,
* seizure-like event.

Do not diagnose the condition. The classification is based on safety risk only.

#### L1-E. Critical vital status with dangerous context

Use `L1` when Bridge or sensors report `vital_status.status = "critical"` and at least one of the following is present:

* no response,
* altered consciousness,
* chest pain,
* breathing difficulty,
* fall or possible fall,
* severe weakness,
* explicit urgent help request.

If critical vital status is present but the context is unclear, classify as `L1` unless Bridge explicitly marks the reading as unreliable.

#### L1-F. Bridge-provided high-risk context

Use `L1` when Bridge provides one of:

* `high_risk_context`,
* `fall_detected_high_confidence`,
* `no_response_after_safety_check`,
* `critical_vital_status`,
* `emergency_mock_event`.

Bridge high-risk flags should override ambiguous ASR.

---

### Step 2 — L2: moderate care concern requiring active follow-up

If no L1 trigger is present, classify as `L2` if any active-care concern exists.

#### L2-A. Vague discomfort without L1 evidence

Use `L2` for statements such as:

* 「我有點不舒服」
* 「怪怪的」
* 「今天身體不太對」
* 「有點頭暈」
* 「有點想吐」
* 「很累」
* 「沒力氣」
* 「有點喘」
* 「肚子痛」
* 「頭痛」
* 「腳痛」
* 「胸口有點悶」 without severe or persistent context

Default response: ask clarification and check for L1 symptoms.

Suggested clarification:

「你是哪裡不舒服？有胸痛、呼吸不順、快昏倒、站不穩，或剛剛跌倒嗎？」

#### L2-B. Pain or injury concern without immediate danger

Use `L2` when:

* resident reports pain but can respond clearly,
* resident reports minor bump or discomfort,
* visual context suggests discomfort but no fall/no response,
* resident is walking unsteadily but can answer,
* resident is holding furniture or wall for support.

Ask:

「你現在可以安全坐下嗎？有沒有跌倒、撞到頭，或痛到不能走？」

#### L2-C. Repeated missed reminder with concern

Use `L2` when:

* medication reminder missed 2 or more times,
* hydration reminder missed repeatedly,
* rehab reminder missed repeatedly,
* resident does not confirm after repeated reminder attempts,
* missed reminder combines with low activity, fatigue, or vague discomfort.

Do not classify as L1 unless no response is combined with fall, abnormal posture, or high-risk context.

#### L2-D. Behavior pattern concern

Use `L2` when recent events or memory suggest unusual behavior patterns:

* long inactivity compared with baseline,
* prolonged bathroom stay,
* unusual nighttime wandering,
* repeated missed medication,
* unusually low food intake,
* unusually low hydration,
* unusually low activity,
* new confusion in daily schedule,
* repeated request for help with basic tasks,
* repeated cancellation of routine activities due to fatigue.

If the behavior pattern is mild and isolated, consider L3. If repeated, prolonged, or combined with discomfort, use L2.

#### L2-E. Non-critical abnormal vital status

Use `L2` when `vital_status.status = "abnormal_non_critical"` and no L1 symptom is present.

Examples:

* heart rate higher than usual but resident is responsive,
* blood pressure higher than usual but no chest pain or breathing difficulty,
* blood glucose warning but resident is responsive,
* SpO2 warning marked non-critical by Bridge.

Ask about symptoms and suggest safe rest or measurement if appropriate.

#### L2-F. Possible fall risk but not confirmed fall

Use `L2` when:

* near-fall detected,
* unstable gait detected,
* resident says 「差點跌倒」,
* resident says 「我剛剛有點站不穩」,
* visual context shows imbalance but resident responds normally.

Ask whether help is needed and log the event.

---

### Step 3 — L3: low-risk care event or routine reminder

If no L1 or L2 trigger exists, classify as `L3` for routine care workflow.

#### L3-A. Routine reminder

Use `L3` for:

* medication reminder without distress,
* hydration reminder,
* schedule reminder,
* rehab or stretching reminder,
* sleep reminder,
* measurement reminder.

Examples:

* 「提醒我三點做伸展」
* 「該吃藥了」
* 「該喝水了」
* 「晚上八點提醒我量血壓」

#### L3-B. Reminder completion

Use `L3` when the resident clearly confirms completion:

* 「好，我吃完藥了」
* 「我喝水了」
* 「我做完伸展了」
* 「不用提醒了，我已經完成了」

Typical action:

* `mark_reminder_done`
* `log_event`
* short confirmation response

#### L3-C. Mild missed response quickly resolved

Use `L3` when:

* first reminder was missed but resident quickly confirms,
* resident says 「等一下」,
* resident asks to postpone reminder,
* resident declines reminder without distress.

If this repeats multiple times, upgrade to L2.

#### L3-D. Low-risk care preference update

Use `L3` when resident updates routine preferences:

* change reminder time,
* add schedule,
* postpone hydration reminder,
* request routine daily check-in,
* ask for exercise video without discomfort.

---

### Step 4 — Normal: no care risk

Use `Normal` when no care risk is visible or stated.

Examples:

* casual conversation,
* general question,
* normal navigation command,
* safe turn/stop command,
* robot status question,
* entertainment request,
* no active care event.

Examples:

* 「你聽得到我嗎？」
* 「今天天氣怎麼樣？」
* 「去客廳」
* 「轉過來」
* 「播放音樂」
* 「你叫什麼名字？」

If a normal command is combined with risk context, classify based on the risk context.

Example:

* 「停下來」 alone → `Normal`
* 「停下來，你快撞到我了」 → at least `L2`; may be `L1` if immediate collision danger exists.

---

## 6. Escalation Rules

### 6.1 L3 → L2

Upgrade from `L3` to `L2` when:

* the same reminder is missed repeatedly,
* routine reminder is combined with discomfort,
* resident gives confused or inconsistent answers,
* resident confirms but visual context suggests discomfort,
* recent events show repeated deviation from baseline,
* Bridge marks repeated care concern.

Examples:

* Medication reminder missed 3 times → `L2`
* Hydration reminder missed + resident says 「很累」 → `L2`
* Rehab reminder missed for several days → `L2`

### 6.2 L2 → L1

Upgrade from `L2` to `L1` when clarification reveals:

* cannot get up,
* cannot walk,
* cannot speak normally,
* breathing difficulty,
* chest pain or pressure,
* fainting or loss of consciousness,
* sudden one-sided weakness,
* slurred speech,
* face drooping,
* severe bleeding,
* head injury with confusion, vomiting, or severe dizziness,
* explicit emergency request,
* no response after safety check,
* Bridge high-risk flag.

Example:

Initial ASR: 「我有點頭暈」 → `L2`

Follow-up answer: 「我站不起來，快昏倒了」 → `L1`

### 6.3 L2 → L3

Downgrade from `L2` to `L3` when:

* resident clearly confirms they are safe,
* no L1 symptoms are present,
* visual context is normal,
* the care task is completed,
* the concern was a minor reminder issue.

Example:

ASR: 「我只是有點累，剛剛已經坐下休息，沒有胸痛也沒有喘」 → `L3` with log event.

### 6.4 L1 de-escalation

Do not immediately downgrade `L1` in the same turn unless there is strong corrective evidence from Bridge or a clear false-positive confirmation.

Example:

* Visual model: possible fall.
* Resident clearly says: 「我沒事，我是在地上做伸展。」
* Visual context confirms intentional floor exercise.
* Then classify as `L2` or `L3`, log potential false-positive, and avoid mock caregiver notification.

When uncertain, keep `L1` and ask immediate safety confirmation.

---

## 7. Output Expectations

When the active schema allows, Hermes should include Home-ESI risk cognition in `cognitive_state`.

Recommended structure:

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

### Required cognitive_state fields

| Field                 | Required              | Meaning                                            |
| --------------------- | --------------------- | -------------------------------------------------- |
| `home_esi_level`      | Yes                   | One of `L1`, `L2`, `L3`, `Normal`                  |
| `risk_reason`         | Yes                   | Short explanation without private chain-of-thought |
| `next_step`           | Yes                   | Primary next step                                  |
| `recommended_actions` | Yes                   | Bridge-valid action intents                        |
| `evidence_summary`    | Recommended           | Short evidence object                              |
| `risk_triggers`       | Recommended           | Matched rule categories                            |
| `missing_information` | Recommended for L1/L2 | What should be clarified                           |
| `confidence`          | Recommended           | `high`, `medium`, or `low`                         |

Do not expose private chain-of-thought. Use concise `risk_reason` and `reasoning_summary`.

---

## 8. Allowed Action Patterns by Level

### Normal

Typical actions:

* `speak`
* `navigate`
* `turn`
* `stop`
* `noop`

### L3

Typical Bridge-valid actions:

* `speak`
* `ask_clarification` if confirmation is needed
* `log_event`
* `mark_reminder_done`

For reminder postponement or schedule-update intent, use `speak` plus `log_event` unless Bridge adds a dedicated scheduling action.

### L2

Typical Bridge-valid actions:

* `ask_clarification`
* `speak`
* `log_event`
* `notify_caregiver_mock` only if resident requests, repeated concern exists, or Bridge policy allows

Suggestions such as resting, sitting safely, measuring condition, or arranging follow-up should be expressed in the `speak` / `ask_clarification` text and recorded through `log_event`; do not invent unsupported action types.

### L1

Typical Bridge-valid actions:

* `stop` if robot motion may be unsafe
* `speak` or `ask_clarification` for immediate safety check
* `notify_caregiver_mock`
* `log_event` with abnormal event details

L1 should always include event logging. L1 should include mock notification unless Bridge policy or demo mode explicitly disables it.

---

## 9. Recommended Response Templates

### L1 safety confirmation

「我偵測到可能有危險狀況。你現在聽得到我說話嗎？如果你無法回應，我會通知家屬確認你的安全。」

### L1 explicit fall

「我知道你可能跌倒了。請先不要勉強起身。你現在可以說話或揮手回應我嗎？我會通知家屬來確認你的狀況。」

### L2 vague discomfort

「你說有點不舒服，我想先確認你的安全。你現在是頭暈、胸悶、呼吸不順，還是哪裡不舒服？你可以先坐下休息嗎？」

### L2 missed medication reminder

「我注意到你剛剛沒有確認吃藥提醒。你是已經吃藥了、想晚一點吃，還是需要我通知家人協助確認？」

### L3 reminder completion

「好的，我已經記錄你完成了。」

### Normal response

Respond normally and keep the robot action safe.

---

## 10. Example Decisions

| Scenario                                               | Level        | Reason                                           | Next step                                                            |
| ------------------------------------------------------ | ------------ | ------------------------------------------------ | -------------------------------------------------------------------- |
| ASR: 「我跌倒了，站不起來」                                       | `L1`         | Explicit fall + cannot get up                    | Safety confirmation, mock caregiver notification, log abnormal event |
| Visual: resident lying on bathroom floor + no response | `L1`         | Possible fall + no response + high-risk location | Stop, safety check, mock caregiver notification, log                 |
| ASR: 「救命，幫我叫救護車」                                       | `L1`         | Explicit urgent help request                     | Mock caregiver notification, log, safety confirmation                |
| ASR: 「我胸口很痛，喘不過氣」                                      | `L1`         | Severe symptoms                                  | Safety confirmation, mock caregiver notification, log                |
| ASR: 「我有點頭暈」, visual normal                            | `L2`         | Subjective discomfort without L1 evidence        | Ask clarification, suggest sitting/resting, log                      |
| ASR: 「我今天很累，不想吃飯」                                      | `L2`         | Fatigue + appetite/behavior concern              | Ask clarification, log                                               |
| Medication reminder missed 3 times                     | `L2`         | Repeated missed care task                        | Ask clarification, log                                               |
| Visual: unstable gait, resident responsive             | `L2`         | Possible fall risk without confirmed fall        | Ask if help is needed, log                                           |
| ASR: 「好，我吃完藥了」                                         | `L3`         | Reminder completed                               | Mark reminder done, log                                              |
| ASR: 「等一下再喝水」                                          | `L3`         | Routine reminder postponement                    | Reschedule, log                                                      |
| ASR: 「你聽得到我嗎？」                                         | `Normal`     | General interaction                              | Speak                                                                |
| ASR: 「去客廳」 with no risk context                        | `Normal`     | Safe navigation request                          | Navigate if Bridge validates safety                                  |
| ASR: 「停下來，你快撞到我了」                                      | `L2` or `L1` | Possible immediate robot safety concern          | Stop first, then assess risk                                         |
| ASR: 「我沒事，我是在地上做伸展」 after visual possible fall         | `L2` or `L3` | Possible false-positive; still log               | Confirm safety, log false-positive                                   |

---

## 11. Testing Checklist

Before deployment, evaluate the skill with a test set covering:

1. Clear L1 events:

   * fall and cannot get up,
   * no response,
   * explicit urgent help,
   * chest pain and breathing difficulty,
   * stroke-like symptoms,
   * severe bleeding,
   * Bridge high-risk flag.

2. Clear L2 events:

   * vague discomfort,
   * dizziness,
   * pain,
   * nausea,
   * fatigue,
   * repeated missed reminder,
   * abnormal but non-critical vital status,
   * behavior pattern deviation.

3. Clear L3 events:

   * routine medication reminder,
   * hydration reminder,
   * reminder completed,
   * reminder postponed,
   * schedule update.

4. Clear Normal events:

   * casual chat,
   * safe navigation,
   * robot status question,
   * entertainment request.

5. Boundary cases:

   * visual possible fall but resident says they are exercising,
   * resident says 「不舒服」 but no L1 evidence,
   * resident says 「沒事」 but visual shows no response or floor posture,
   * sensor abnormal but ASR normal,
   * ASR urgent but visual unavailable,
   * reminder missed once vs missed repeatedly.

Recommended evaluation metrics:

* L1 recall,
* L1 false-positive rate,
* L2-to-L1 escalation correctness,
* reminder completion accuracy,
* action validity after Bridge validation,
* explanation completeness,
* response latency,
* caregiver-perceived usefulness in demo review.

---

## 12. Core Policy Sentence

Use this sentence as the governing principle:

**Classify L1 only when there is explicit or strongly supported evidence of immediate safety threat. Classify vague discomfort as L2 unless combined with fall, no response, inability to get up, severe symptoms, acute confusion, critical vital status, explicit emergency request, or Bridge-provided high-risk context. Use L3 for routine care workflows and Normal for non-care-risk interaction.**
