# Temi Action Examples

These examples show valid Hermes output for common Temi events. Preserve the input `event_id` and `robot_id` exactly.

## Visual Question

Input ASR:

```text
幫我看看桌上的東西是什麼
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "robot_id": "temi-01",
  "confidence": 0.82,
  "reasoning_summary": "The user asks for visible object description. A verbal response is sufficient.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "speak",
      "text": "我看到桌上有幾個物品，可能包含杯子和筆電。",
      "language": "zh-TW"
    }
  ]
}
```

## Ambiguous Pointing

Input ASR:

```text
幫我拿那個
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_002",
  "robot_id": "temi-01",
  "confidence": 0.45,
  "reasoning_summary": "The referenced object is ambiguous, and Temi cannot safely manipulate objects.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "ask_clarification",
      "text": "我還不確定你指的是哪個物品，可以請你再說明一下嗎？",
      "language": "zh-TW"
    }
  ]
}
```

## Navigation

Input ASR:

```text
去會議室
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_003",
  "robot_id": "temi-01",
  "confidence": 0.9,
  "reasoning_summary": "The user clearly requested navigation to a known destination.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "navigate",
      "target": "meeting_room"
    }
  ]
}
```

## Unknown Destination

Input ASR:

```text
去小房間
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_004",
  "robot_id": "temi-01",
  "confidence": 0.62,
  "reasoning_summary": "The requested destination is not in the known navigation target list.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "ask_clarification",
      "text": "我目前不知道小房間的位置。你可以指定會議室、客廳、廚房或充電座嗎？",
      "language": "zh-TW"
    }
  ]
}
```

## Turn

Input ASR:

```text
往左轉一點
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_005",
  "robot_id": "temi-01",
  "confidence": 0.88,
  "reasoning_summary": "The user requested a small left turn.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "turn",
      "direction": "left",
      "degrees": 15
    }
  ]
}
```

## Stop

Input ASR:

```text
停下來
```

Output:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_006",
  "robot_id": "temi-01",
  "confidence": 0.95,
  "reasoning_summary": "The user clearly requested the robot to stop.",
  "actions": [
    {
      "action_id": "act_001",
      "type": "stop"
    }
  ]
}
```
