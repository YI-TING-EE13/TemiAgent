---
name: temi-home-esi
description: Apply Home-ESI Lite risk classification for Temi home-care assistant events. Use to classify Normal, L3, L2, and L1 care risk from ASR text, visual context, robot state, reminders, and recent events. This skill provides decision policy only and must be used with Bridge-validated JSON actions.
---

# Temi Home-ESI Lite Skill

## Purpose

Use this skill when Hermes needs to classify home-care risk for a Temi interaction. The goal is not medical diagnosis. The goal is a conservative first-year demo policy for deciding whether the robot should respond normally, ask a care clarification, log an event, or request mock caregiver notification.

## Output Expectations

Hermes should include risk cognition in `cognitive_state` when the active schema allows it:

```json
{
  "home_esi_level": "L2",
  "risk_reason": "使用者表示不舒服，需要先追問症狀與安全狀態。",
  "next_step": "ask_clarification"
}
```

Do not expose private chain-of-thought. Use a short `risk_reason` and `reasoning_summary`.

## Level Summary

| Level | Meaning | Default next step |
|---|---|---|
| `L1` | 高風險，可能需要立即處置 | 安全確認、停止危險動作、mock 通知、記錄異常 |
| `L2` | 中風險，需要主動關懷 | 追問、建議休息或量測、記錄事件 |
| `L3` | 輕度事件或一般照護提醒 | 一般提醒、紀錄、必要時安排提醒 |
| `Normal` | 無明顯照護風險 | 正常對話或安全 action |

## Safety Policy

1. Do not make a medical diagnosis.
2. Do not claim real emergency services were contacted.
3. Prefer clarification for ambiguous discomfort.
4. Do not upgrade to L1 only because the resident says "不舒服"; use L2 unless there is stronger evidence.
5. Upgrade to L1 for fall, no response, explicit emergency request, severe symptoms, or Bridge-provided high-risk context.
6. For L1, include `notify_caregiver_mock` only as demo notification intent and always log the event.

Read `references/home_esi_lite.md` for the level rules and scenario examples.
