# P2 Structured Memory Phase 1 Report Materials

> Status: HISTORICAL report material. It is retained as phase evidence, not a
> current data, care or deployment contract.

## 1. Architecture Diagram Specification

Suggested diagram title:

```text
Bridge-Controlled Structured Care Memory for TemiAgent / Hermes
```

Recommended horizontal zones:

```text
[Temi Robot / Sensors]
[HermesTemiBridge Safety Boundary]
[Structured Care Memory]
[Hermes Agent Reasoning]
```

Required nodes:

```text
Temi ASR / abnormal event
  - ASR final text
  - synchronized image paths
  - perception.abnormal evidence paths

Bridge event validation
  - schema validation
  - robot_id allowlist
  - image path validation
  - duplicate event check

CareContextBuilder
  - read-only
  - deterministic retrieval
  - risk-aware / diversity-aware event selection

Structured care memory
  - profile.json
  - reminders.json
  - daily_state.json
  - event_log.jsonl
  - abnormal_events/*.json

care_context
  - resident
  - active_reminders
  - daily_state
  - relevant_events
  - read_status
  - memory_policy

Hermes Agent
  - local LLM reasoning
  - persona / care policy
  - JSON action planning

JSON action plan
  - cognitive_state
  - robot_actions
  - memory_actions

action_validator
  - schema validation
  - allowed actions
  - required Home-ESI fields

robot_actions
  - speak
  - ask_clarification
  - turn / navigate / stop / noop

memory_actions
  - log_event
  - mark_reminder_done
  - generate_summary
  - notify_caregiver_mock

MQTT
  - sends robot actions to Temi app

StructuredMemoryStore
  - writes approved memory actions
```

Main arrows:

```text
Temi ASR / abnormal event
  -> Bridge event validation
  -> CareContextBuilder

CareContextBuilder
  -> reads structured care memory

Structured care memory
  -> CareContextBuilder

CareContextBuilder
  -> care_context

care_context
  -> Hermes Agent

Hermes Agent
  -> JSON action plan

JSON action plan
  -> action_validator

action_validator
  -> robot_actions
  -> MQTT

action_validator
  -> memory_actions
  -> StructuredMemoryStore
  -> structured care memory
```

The diagram should explicitly label these three principles:

```text
Hermes can propose.
Bridge validates and executes.
Structured memory remains authoritative.
```

Suggested visual annotations:

- Mark `CareContextBuilder -> structured care memory` as read-only.
- Mark `StructuredMemoryStore -> structured care memory` as write.
- Do not draw a direct write arrow from Hermes to memory, or draw it as a blocked path labeled `No direct memory write`.
- Use a bold boundary around the Bridge zone to emphasize the safety boundary.

## 2. Demo Flow Diagram Specification

Suggested diagram title:

```text
Phase 1 Structured Care Memory Demo Flows
```

Recommended layout: four swimlanes, one per demo case. Each lane follows the same sequence:

```text
Input -> care_context evidence -> Hermes JSON output -> Bridge result
```

### Case 1: First Discomfort

```text
Input:
  ASR text = 我不舒服

care_context evidence:
  resident = 王先生
  active_reminders = medication, hydration
  relevant_events = []

Hermes output:
  home_esi_level = L2
  action = ask_clarification
  memory_action = log_event

Bridge memory result:
  event_log.jsonl writes evt_live_discomfort_001
  risk.home_esi_level = L2
```

### Case 2: Repeated Discomfort

```text
Input:
  ASR text = 我又不舒服

care_context evidence:
  relevant_events includes evt_live_discomfort_001
  match_reasons include current_intent:health_discomfort / keyword:health_discomfort

Hermes output:
  home_esi_level = L2
  risk_reason cites evt_live_discomfort_001
  action = ask_clarification
  memory_action = log_event

Bridge memory result:
  second discomfort event is logged
  prior event_id remains auditable evidence
```

### Case 3: Medication Reminder Done

```text
Input:
  ASR text = 我吃過藥了

care_context evidence:
  active_reminders includes rem_morning_medication

Hermes output:
  home_esi_level = L3
  memory_action = mark_reminder_done
  memory_action = log_event

Bridge memory result:
  reminders.json updates rem_morning_medication active -> completed
  last_completed_at is recorded
  next-turn active_reminders excludes rem_morning_medication
```

### Case 4: perception.abnormal

```text
Input:
  source = perception.abnormal
  action_name = fall_like_motion
  evidence = image file paths

care_context evidence:
  event.source = perception.abnormal
  resident / reminders / daily_state present
  relevant prior events available if selected

Hermes output:
  JSON action plan
  risk-aware response or log_event in demo-safe mock flow

Bridge memory result:
  event can be logged through StructuredMemoryStore
  image evidence remains file paths only
  no raw image bytes in MQTT / memory context
```

## 3. Report Text

Phase 1 completes a Bridge-controlled structured care memory read path for the TemiAgent / Hermes care assistant. In the original system, structured memory writes such as event logging and reminder completion were already handled by the Bridge, but Hermes did not consistently receive compact care state before each reasoning turn. Phase 1 adds a `CareContextBuilder` that reads authoritative structured memory, including resident profile, active reminders, daily state, recent care events, and abnormal event records, then injects a bounded `care_context` into the Hermes prompt before action planning.

This design is important because care memory should not behave like an unconstrained natural-language note system. In home-care interaction, memory must be evidence-based, auditable, and tied to validated observations and state transitions. Hermes can reason over the provided context and propose actions, but it does not directly edit the care record. The Bridge validates Hermes output, separates robot actions from memory actions, and writes approved memory updates through `StructuredMemoryStore`.

Compared with generic LLM memory, this architecture emphasizes care state authority rather than personalization alone. Generic memory often focuses on remembering user preferences or conversation history. Here, memory is structured around resident state, reminders, Home-ESI risk context, event IDs, timestamps, and validated action outcomes. The Phase 1 demo verifies this through repeated discomfort recall, medication reminder completion, and abnormal visual-event context injection, showing that the robot assistant can preserve care continuity while maintaining a clear safety boundary.

## 4. Speaker Notes

這一階段我們完成的是 structured care memory 的 read path。簡單說，Hermes 不再只是看到當下使用者說了什麼，而是由 Bridge 在呼叫 Hermes 前，先把照護系統裡可信的結構化記憶整理成 `care_context`。

這個設計有三個原則：Hermes 可以提出建議，Bridge 負責驗證與執行，structured memory 才是照護狀態的權威來源。所以 Hermes 不會直接改 `memory/*.json`，它只能輸出 JSON action plan。真正的記憶寫入，例如紀錄事件、完成提醒，仍然由 Bridge 驗證後交給 `StructuredMemoryStore`。

Demo 裡我們驗證四件事：第一次說不舒服會寫入 L2 事件；第二次說又不舒服時，系統會把前一次 L2 event_id 帶進 context；使用者說吃過藥後，提醒會從 active 變 completed；另外 abnormal vision event 也能取得同一套 care context。這讓 temi 從單次反應變成有照護連續性的助理，同時保留安全邊界與可追溯性。

## 5. Research Contribution Framing

### Problem

Embodied home-care LLM agents need memory continuity, but unconstrained LLM memory is not sufficient for care scenarios. Care memory must distinguish between raw observation, inferred risk, reminder state, and validated memory writes. It must also support auditability and avoid letting the language model directly mutate authoritative care records.

### Method

We introduce a Bridge-controlled structured memory read path. A `CareContextBuilder` reads authoritative structured care memory and constructs a compact `care_context` containing resident profile, active reminders, daily state, relevant events, read status, and memory policy. This context is injected into Hermes prompts as Bridge-provided context, separate from current user speech. Hermes produces a JSON action plan, which is validated by the Bridge before robot actions or memory actions are executed.

### Engineering Contribution

The implementation provides:

```text
- read-only CareContextBuilder
- optional HermesRequest.care_context
- ASR and abnormal-route prompt injection
- deterministic rule-based retrieval
- diversity-aware retrieval ranking
- event_id-based repeated discomfort recall
- reminder completion continuity
- mock-safe demo/regression runner
```

It also preserves the existing write-path boundary:

```text
Hermes JSON action plan
  -> action_validator
  -> StructuredMemoryStore
```

### Limitation

Current Phase 1 retrieval is deterministic and rule-based. It does not include embedding retrieval, graph memory, Hermes MemoryProvider integration, or clinically validated triage. The demo runner uses mock Hermes and mock MQTT, so it validates system memory behavior rather than live LLM quality or real robot execution.

### Next Step

The recommended next step is to prepare architecture diagrams, Demo slides, and evaluation materials before adding new functionality. After the Phase 1 baseline is clearly documented, Phase 2 can consider one focused direction: demo hardening, memory evaluation suite, or retrieval enhancement.
