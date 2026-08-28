#!/usr/bin/env bash
set -euo pipefail

# Retained as a compatibility entrypoint. Real LM Studio is externally managed.

CONTEXT_LENGTH="${CONTEXT_LENGTH:-64000}"
LMSTUDIO_CONTEXT_LENGTH="${LMSTUDIO_CONTEXT_LENGTH:-$CONTEXT_LENGTH}"
LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0,1}"

if [[ ! "$CONTEXT_LENGTH" =~ ^[1-9][0-9]*$ ]]; then
  echo "[LM Studio] CONTEXT_LENGTH must be a positive integer." >&2
  exit 2
fi

if [[ ! "$LMSTUDIO_CONTEXT_LENGTH" =~ ^[1-9][0-9]*$ ]]; then
  echo "[LM Studio] LMSTUDIO_CONTEXT_LENGTH must be a positive integer." >&2
  exit 2
fi

if [[ "$CONTEXT_LENGTH" != "$LMSTUDIO_CONTEXT_LENGTH" ]]; then
  echo "[LM Studio] CONTEXT_LENGTH and LMSTUDIO_CONTEXT_LENGTH must match." >&2
  exit 2
fi

if [[ "$LMSTUDIO_VISIBLE_GPUS" != "0,1" ]]; then
  echo "[LM Studio] Demo GPU policy requires LMSTUDIO_VISIBLE_GPUS=0,1." >&2
  exit 2
fi

echo "[LM Studio] Real provider lifecycle control is disabled; LM Studio is externally managed." >&2
echo "[LM Studio] Supply a ready external HTTP API; no provider process was started." >&2
exit 2
