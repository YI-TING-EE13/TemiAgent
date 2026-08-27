# TemiAgent Agent Brief

> Status: SUPPLEMENTAL legacy brief. Use <code>AGENTS.md</code>, the root
> <code>README.md</code> and <code>docs/project/STUDENT_HANDOVER.md</code> for
> current governance and onboarding.

TemiAgent is an embodied AI home-care assistant project for a Temi robot. The robot handles sensing and physical interaction, while Hermes Agent acts as the cognitive core for situation understanding, care memory reasoning, risk classification, and action planning.

## Core Architecture

- `temi_backend/` provides the verified legacy route: Temi ASR, WebSocket video frames, local VLM reasoning, and MQTT robot actions.
- `tools/temi_overview_adapter.py` adapts the installed Android app's legacy MQTT topics into the canonical project contract.
- `hermes_temi_bridge/` is the safety boundary. It validates ASR events, image paths, Hermes JSON output, and action schemas before publishing robot commands.
- `hermes-agent/` is the Hermes runtime. For this project, read `hermes-agent/README.TemiAgent.md` before touching the upstream Hermes codebase.
- `hermes-agent/skills/temi-*` and `hermes-skills/temi-*` define robot control, care memory, Home-ESI Lite risk policy, and the Discord/gateway Temi entry skill for camera or gesture requests.
- `temi_shared/` stores ASR-aligned image snapshots and event metadata. MQTT carries paths, not image binaries.

## Safety Rules

Hermes must not directly control hardware, publish MQTT messages, or bypass the Bridge. It should return JSON-only action plans. The Bridge is responsible for validation and dispatch. Emergency notification is demo-only unless a future task explicitly implements a real notification workflow.

## Primary Docs

- Project README: `README.md`
- Architecture: `docs/architecture/project_overview.md`
- Care assistant task scope: `docs/project/hermes_care_assistant_task_readme.md`
- Full handoff: `docs/project/hermes_care_assistant_handoff.md`
- Integration runbook: `docs/operations/temi_integration_runbook.md`

## Useful Commands

```bash
cd /TemiAgent/hermes_temi_bridge
uv run python -m unittest discover -s tests
```

```bash
cd /TemiAgent/temi_backend
uv run pytest
```

```bash
cd /TemiAgent
python3 tools/e2e_test_runner.py
```

For real Hermes demos, prefer resident HTTP mode via `tools/hermes_resident_server.py` and configure the Bridge with `HERMES_INVOKE_MODE=http`. Run maintenance commands from inside the `/TemiAgent` container as documented in `docs/operations/first_year_demo_e2e_operation_manual.md`, because several Temi skill mirrors are container-owned.
