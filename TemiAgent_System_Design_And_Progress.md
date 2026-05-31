# TemiAgent Architecture Whitepaper: Building a Deterministic Embodied AI

> Date: 2026-05-07
> Status: Stable Release (Phase 5 Completed)
> Architecture: Asynchronous Edge-Cloud Decoupling with Vision-Language Models (VLM)

## Executive Summary
TemiAgent is designed to bypass the traditional limitations of integrated robotics by completely decoupling sensory intake and physical actuation (Edge) from high-level cognitive reasoning (Cloud/PC Backend). This document serves as a technical whitepaper detailing the core engineering philosophies, mathematical models, and architectural decisions that guarantee system determinism, safety, and fluidity in Human-Robot Interaction (HRI).

---

## A. Time-Series Manifold Alignment & Asymmetric Sampling

In physical Embodied AI, human intents are rarely conveyed through speech alone. Deictic gestures (e.g., pointing) provide critical spatial context. The kinematics of such gestures typically consist of three phases:
1. **Stroke (Preparation)**: The arm begins to move.
2. **Apex (Hold)**: The finger rests at the target location.
3. **Retraction**: The arm returns to a resting state.

### The Fallacy of Symmetrical Sampling
When the robot's Automatic Speech Recognition (ASR) triggers the completion of an utterance (let's denote this timestamp as $T_{asr}$), the human gesture has often already passed its Apex. Symmetrical sampling (e.g., $[T-500ms, T, T+500ms]$) inherently captures the retraction phase in the future frames, feeding the VLM with decaying spatial context, which drastically increases the entropy of intent prediction.

### Asymmetric Backward Sampling
To solve this, TemiAgent enforces **Asymmetric Backward Sampling**. When $T_{asr}$ is received, the backend's `VisionBuffer` extracts a deterministic multi-frame grid:
- **$T - 1000ms$**: Captures the *Stroke* phase, allowing the VLM to observe the gesture's origin and velocity vector.
- **$T - 500ms$**: Captures the *Apex* phase, locking onto the precise spatial target.
- **$T$**: Captures the acoustic conclusion, confirming the semantic end of the request.

This $3$-frame sequence effectively projects the temporal dynamics of the human's gesture onto a 2D spatial manifold (Time-Series Manifold Alignment), allowing models like Qwen2-VL or Pixtral to perform accurate cross-modal grounding without being confused by post-speech retractions.

---

## B. Deterministic Event Sourcing & Relative Clock Lock

A critical failure point in distributed robotics is the attempt to synchronize clocks across disparate networks (e.g., via NTP). 

### The Network Transmission Equation
Let $T_{robot}$ be the true time an event occurs on the robot, and $T_{pc}$ be the time the PC receives it.
The relationship is $T_{pc} = T_{robot} + \Delta_{network} + Jitter$.
Since $Jitter$ is stochastic (random network fluctuations), relying on $T_{pc}$ to align a video stream with an ASR event leads to catastrophic phase shifts. A 200ms lag could mean the difference between pointing at a cup and resting a hand on the table.

### Single Source of Truth (SSoT) Architecture
TemiAgent abandons PC-side clocking entirely. 
1. **Video Telemetry**: During the Android `H264Encoder` lifecycle, an 8-byte Big-Endian timestamp (`System.currentTimeMillis()`) is prepended to *every single* NAL unit before WebSocket transmission.
2. **Event Telemetry**: The ASR MQTT payload also attaches the exact hardware timestamp of when the speech processing concluded.

The PC Backend's `VisionBuffer` simply stores tuples of `(Temi_Timestamp, Frame)`. When an ASR event arrives, the system queries the buffer using the Temi timestamp. This **Relative Clock Lock** mechanism mathematically eliminates $\Delta_{network}$ and $Jitter$ from the alignment equation, guaranteeing deterministic frame extraction regardless of network degradation.

---

## C. Embodied Prompting & Cognitive Routing

Allowing an LLM to generate raw Python code (Code Interpreter mode) for physical actuation introduces unacceptable risks, including infinite loops, syntax crashes, and physically dangerous navigation commands.

### JSON Schema Routing
To guarantee the robot's action boundaries, TemiAgent utilizes **Cognitive Routing**. The VLM is strictly constrained by `Skills.md` (the System Prompt) to output a predefined JSON Schema array. The `agent_core.py` acts as a firewall and router:
1. **Validation**: It parses the JSON, discarding hallucinations or malformed syntax via robust Regex extraction.
2. **Execution**: It maps safe, validated parameters to pre-compiled hardware APIs in `mqtt_bridge.py` (`publish_speak`, `publish_navigate`).

### Cross-Modal Fusion via Chain of Thought (CoT)
The `Skills.md` forces the Agent to emit a `<think>...</think>` block prior to action execution. This is not merely for explainability. In VLM architecture, early tokens dictate attention for later tokens. By forcing the model to explicitly describe the spatial relationships observed in the 3-frame grid *before* generating the JSON, we ensure **Cross-modal Fusion**. The spatial features in the image embeddings are successfully mapped to the semantic tokens in the text prompt, vastly reducing hallucinations in object referencing.

---

## D. State Machine Preemption & Latency Masking

In Human-Robot Interaction (HRI), silence is deadly. When a VLM takes 3-7 seconds to process a multi-image prompt and generate its First Token (Time-To-First-Token, TTFT), the user may assume the robot is broken and repeat the command, causing cascading state failures.

### Latency Masking
TemiAgent employs a `THINKING` transitional state. Immediately upon capturing the ASR event, the Android client triggers a non-blocking TTS request (e.g., "Let me take a look"). This ~1.5-second auditory feedback perfectly masks the TTFT of the cloud-based VLM, creating an illusion of immediate, embodied awareness.

### Thread-Safe Watchdogs, Subtitles & Global Preemption
If the VLM crashes or network connectivity is lost, the robot cannot remain paralyzed. 
- **The Watchdog**: The `WAITING` state activates a rigid 60,000ms timer. If the backend fails to reply via MQTT within this window, the State Machine aborts, apologizes ("Connection timed out"), and returns to `IDLE`.
- **TTS Subtitle Mirror**: Backend-driven `speak` actions are mirrored into a compact bottom subtitle overlay. The app tracks the active `TtsRequest` id so completion from an older request cannot accidentally clear a newer subtitle.
- **Interrupt Transition**: Linear state machines fail in dynamic environments. TemiAgent binds the Android root view (`android.R.id.content`) to a global `interrupt()` method. A single physical touch on the robot's screen instantly triggers `robot.cancelAllTtsRequests()` and `robot.stopMovement()`, purging the Watchdog and forcing a state reset. This guarantees that humans maintain ultimate physical authority over the agent's actions at all times.

---

## Development Milestones

- **Phase 1**: Android edge-cloud decoupling, SDK integration, and JDK 21 build system migration.
- **Phase 2**: Bidirectional communication verification (MQTT action routing, PyAV H.264 decoding).
- **Phase 3**: Implementation of the `AgentStateMachine` with preemption and latency masking.
- **Phase 4**: Development of the thread-safe `VisionBuffer` and implementation of Asymmetric Backward Sampling.
- **Phase 5**: Integration of LMStudio/Hermes Agent via OpenAI standard APIs, utilizing `Skills.md` for deterministic JSON Cognitive Routing.
