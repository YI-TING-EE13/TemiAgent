# TemiAgent Agent Guide

## Container-First Rule

All TemiAgent project file edits, service commands, runtime checks, and debugging operations must be performed inside the `yiting.TemiAgent_gpu_all` container unless the user explicitly requests host-side work. This prevents host/container ownership drift and permission problems. Start with:

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

TemiAgent is an embodied AI home-care assistant project for a Temi robot. The robot handles sensing and physical interaction, while Hermes Agent is the cognitive core for situation understanding, care memory reasoning, risk classification, and action planning.

## Core Architecture

- `temi_backend/` provides the verified legacy route: Temi ASR, WebSocket video frames, local VLM reasoning, and MQTT robot actions.
- `tools/temi_overview_adapter.py` adapts the installed Android app's legacy MQTT topics into the canonical project contract.
- `hermes_temi_bridge/` is the safety boundary. It validates ASR events, image paths, Hermes JSON output, and action schemas before publishing robot commands.
- `hermes-agent/` is the Hermes runtime. Read `hermes-agent/README.TemiAgent.md` before touching the upstream Hermes codebase.
- `hermes-agent/skills/temi-*` and `hermes-skills/temi-*` define robot control, care memory, Home-ESI Lite risk policy, and the Discord/gateway Temi entry skill for camera or gesture requests.
- `temi_shared/` stores ASR-aligned image snapshots and event metadata. MQTT carries paths, not image binaries.

## Safety Rules

Hermes must not directly control hardware, publish MQTT messages, or bypass the Bridge. It should return JSON-only action plans. The Bridge is responsible for validation and dispatch. Emergency notification is demo-only unless a future task explicitly implements a real notification workflow.

## Runtime Defaults

Run maintenance commands inside the GPU container unless a document explicitly says otherwise. All TemiAgent file edits and operational commands should be performed from inside `yiting.TemiAgent_gpu_all` to avoid host/container ownership drift.

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent
```

LM Studio headless defaults:

```bash
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID=google/gemma-4-31b
export LMSTUDIO_CONTEXT_LENGTH=64000
export LMSTUDIO_VISIBLE_GPUS=0,1,2
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
```

Hermes config lives at `/root/.hermes/config.yaml` in the container. The local LM Studio provider should match the loaded model:

```yaml
model:
  provider: custom
  base_url: http://localhost:1234/v1
  default: google/gemma-4-31b
  context_length: 64000
auxiliary:
  compression:
    context_length: 64000
```

If changing model or context length, update both LM Studio load parameters and Hermes config. Keep `model.context_length` and `auxiliary.compression.context_length` synchronized so Hermes does not reject a local model due to a 4096-token auto-detection fallback.

## LM Studio Restart

Canonical runbook: `docs/operations/lmstudio_headless_3gpu_hdd_manual.md`.

Preferred restart command:

```bash
cd /TemiAgent
./tools/start_lmstudio_3gpu.sh
```

To change the model or context for one run:

```bash
LMSTUDIO_MODEL_ID=your/model-id LMSTUDIO_CONTEXT_LENGTH=32768 ./tools/start_lmstudio_3gpu.sh
```

Short restart sequence:

```bash
cd /TemiAgent
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID=${LMSTUDIO_MODEL_ID:-google/gemma-4-31b}
export LMSTUDIO_CONTEXT_LENGTH=${LMSTUDIO_CONTEXT_LENGTH:-64000}
export LMSTUDIO_VISIBLE_GPUS=${LMSTUDIO_VISIBLE_GPUS:-0,1,2}
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
hash -r

lms unload --all
lms server stop
lms daemon down
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
lms server start --port 1234
lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max
lms ps
```

The expected default `lms ps` row is `google/gemma-4-31b` with context `64000`. If LM Studio shows `google/gemma-4-31b:2`, it means another same-name instance was already loaded. Use `lms unload --all` and reload if the unsuffixed default identifier is desired.

## Health Checks

LM Studio:

```bash
which lms
readlink -f "$(which lms)"
ps auxeww | grep -i "llmster" | grep -v grep | grep CUDA_VISIBLE_DEVICES
curl http://127.0.0.1:1234/v1/models
lms ps
nvidia-smi
```

Hermes resident probe:

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8766 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md
```

Then verify from another shell:

```bash
curl http://127.0.0.1:8766/health
```

Expected fields include `status: ok`, `model: google/gemma-4-31b`, `provider: custom`, and `base_url: http://localhost:1234/v1`.

## Primary Docs

- Project README: `README.md`
- Docs index: `docs/README.md`
- Architecture: `docs/architecture/project_overview.md`
- LM Studio headless runbook: `docs/operations/lmstudio_headless_3gpu_hdd_manual.md`
- Integration runbook: `docs/operations/temi_integration_runbook.md`
- Care assistant task scope: `docs/project/hermes_care_assistant_task_readme.md`
- Full handoff: `docs/project/hermes_care_assistant_handoff.md`

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

For real Hermes demos, prefer resident HTTP mode via `tools/hermes_resident_server.py` and configure the Bridge with `HERMES_INVOKE_MODE=http`.
