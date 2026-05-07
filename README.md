# TemiAgent: Embodied AI Integration Framework

**TemiAgent** is an open-source framework designed to transform the Temi robot into a fully autonomous, Embodied AI agent driven by Vision-Language Models (VLMs). It features a robust, decoupled architecture that isolates hardware control on the Android client while delegating high-level cognitive processes to a PC-based backend.

## 🌟 Key Features

- **Asymmetric Multi-frame Sampling**: Extracts deterministic visual keyframes `[T-1000ms, T-500ms, T]` precisely synchronized with the end of user speech. This ensures that transient gestures (e.g., pointing) are captured accurately within their kinematics lifecycle (stroke, apex, retraction), facilitating perfect time-series manifold alignment for the VLM.
- **Deterministic Event Sourcing & Relative Clock Lock**: Bypasses network transmission jitter completely. The system uses the robot's local hardware clock as the Single Source of Truth (SSoT), embedding an 8-byte Big-Endian timestamp directly into every H.264 video NAL unit header.
- **State Machine Preemption**: Implements a robust state machine (`AgentStateMachine`) handling the complete dialogue lifecycle (`IDLE`, `THINKING`, `WAITING`, `EXECUTING`). Features global preemption, allowing users to interrupt the robot at any time via touch, instantly resetting all states, canceling hardware actions, and clearing the 15-second timeout watchdog.
- **Cognitive Skill Routing**: Utilizes strict JSON Schema tool calling. The VLM is constrained by `Skills.md` to output structured JSON arrays after a Chain of Thought (`<think>`) reasoning phase. The JSON is parsed and validated by a dedicated `SkillRouter`, guaranteeing safe execution of hardware APIs.

## 🏗️ Architecture Overview

The system is decoupled into two primary components:

### 1. Android Client (Temi Robot)
- **Sensory Intake**: Captures high-resolution video streams (transmitted via WebSocket) and handles wake words and Automatic Speech Recognition (ASR).
- **Execution Engine**: Manages the State Machine and executes MQTT commands (Text-To-Speech, Navigation) safely.
- **Latency Masking**: Implements non-blocking TTS transitions (e.g., "Let me take a look") to mask the VLM's Time-To-First-Token (TTFT) latency, enhancing the human-robot interaction experience.

### 2. PC-B Backend (Python + LMStudio / Hermes Agent)
- **`vision_server.py`**: Maintains a thread-safe `VisionBuffer`, acting as a 10-second rolling cache of decoded H.264 frames paired tightly with their true hardware timestamps.
- **`mqtt_bridge.py`**: Manages telemetry and command events between the PC and the robot.
- **`agent_core.py`**: The orchestrator. It receives ASR events, samples the vision buffer, constructs a multi-modal context, invokes the VLM (via OpenAI compatible APIs like LMStudio), and dispatches hardware commands using the `SkillRouter`.

## 🚀 Getting Started

### Prerequisites
- JDK 21+ (For building the Android Application)
- Python 3.10+ and `uv` package manager
- An MQTT Broker (e.g., Mosquitto) running on port `1883`
- LMStudio or Hermes Agent for serving the local VLM (e.g., Qwen2-VL, Pixtral)

### 1. Android Client Setup
1. Clone the repository and open it in Android Studio.
2. Modify `local.properties` to add your backend's IP address:
   ```properties
   PC_IP="192.168.X.X"
   ```
3. Build and deploy the application to your physical Temi robot:
   ```bash
   ./gradlew assembleDebug
   adb connect <temi_ip>
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```

### 2. Python Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd temi_backend
   ```
2. Install dependencies using `uv`:
   ```bash
   uv add av websockets opencv-python paho-mqtt openai
   ```
3. Start the Agent Core:
   ```bash
   uv run agent_core.py
   ```

## 🧠 Integrating with Hermes Agent
To integrate with the Hermes Agent framework, provide the `Skills.md` file as the system prompt. It contains the exact JSON Schema definitions and sensory constraints required for the VLM to operate the robot successfully.

## 🤝 Contributing
Contributions are welcome. Please ensure that all API documentation and code comments adhere to professional English standards and follow the PEP 257 docstring conventions for Python.

## 📄 License
MIT License
