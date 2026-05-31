---
name: temi-control-legacy
description: Deprecated legacy Temi direct-control prototype. Do not use for the Temi + Hermes bridge architecture; use `temi-robot-control` instead. This folder is retained only for historical reference and should not be installed as an active skill.
---

# Deprecated Legacy Temi Control Skill

This skill is intentionally disabled as an active robot-control instruction set.

Use `../temi-robot-control/` for the current architecture. The current project requires Hermes to output JSON actions only, while `HermesTemiBridge` validates those actions and publishes MQTT commands to Temi.

Do not run scripts from this legacy folder as part of Hermes reasoning. Do not ask the model to emit shell commands, Python commands, private reasoning blocks, or direct hardware-control instructions.
