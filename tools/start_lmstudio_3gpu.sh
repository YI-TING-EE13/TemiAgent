#!/usr/bin/env bash
set -euo pipefail

LMSTUDIO_PROJECT_ROOT="${LMSTUDIO_PROJECT_ROOT:-/TemiAgent}"
LMSTUDIO_TARGET_DIR="${LMSTUDIO_TARGET_DIR:-/TemiAgent/.lmstudio-data}"
LMSTUDIO_MODEL_ID="${LMSTUDIO_MODEL_ID:-google/gemma-4-31b}"
LMSTUDIO_CONTEXT_LENGTH="${LMSTUDIO_CONTEXT_LENGTH:-64000}"
LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0,1,2}"
LMSTUDIO_SERVER_PORT="${LMSTUDIO_SERVER_PORT:-1234}"

export LMSTUDIO_PROJECT_ROOT
export LMSTUDIO_TARGET_DIR
export PATH="$LMSTUDIO_TARGET_DIR/bin:$PATH"

hash -r

echo "[LM Studio] Using lms:"
which lms
readlink -f "$(which lms)"
lms --version

echo "[LM Studio] Unloading existing models..."
lms unload --all || true

echo "[LM Studio] Stopping server..."
lms server stop || true

echo "[LM Studio] Stopping daemon..."
lms daemon down || true

echo "[LM Studio] Starting daemon with GPU(s): $LMSTUDIO_VISIBLE_GPUS"
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up

echo "[LM Studio] Starting server on port $LMSTUDIO_SERVER_PORT..."
lms server start --port "$LMSTUDIO_SERVER_PORT"

echo "[LM Studio] Loading $LMSTUDIO_MODEL_ID with context $LMSTUDIO_CONTEXT_LENGTH..."
lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max

echo "[LM Studio] Current loaded models:"
lms ps

echo "[LM Studio] API models:"
curl -sS "http://127.0.0.1:$LMSTUDIO_SERVER_PORT/v1/models" || true
echo

echo "[LM Studio] Done."
