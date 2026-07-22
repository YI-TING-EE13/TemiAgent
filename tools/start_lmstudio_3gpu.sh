#!/usr/bin/env bash
set -euo pipefail

LMSTUDIO_PROJECT_ROOT="${LMSTUDIO_PROJECT_ROOT:-/TemiAgent}"
LMSTUDIO_TARGET_DIR="${LMSTUDIO_TARGET_DIR:-/TemiAgent/.lmstudio-data}"
LMSTUDIO_MODEL_ID="${LMSTUDIO_MODEL_ID:-temi/gemma-4-31b-it-qat}"
LMSTUDIO_API_IDENTIFIER="${LMSTUDIO_API_IDENTIFIER:-google/gemma-4-31b}"
LMSTUDIO_CONTEXT_LENGTH="${LMSTUDIO_CONTEXT_LENGTH:-64000}"
LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0}"
LMSTUDIO_SERVER_PORT="${LMSTUDIO_SERVER_PORT:-1234}"
LMSTUDIO_MODEL_DEFINITION_SOURCE="${LMSTUDIO_MODEL_DEFINITION_SOURCE:-$LMSTUDIO_PROJECT_ROOT/tools/lmstudio_model_definitions/gemma-4-31b-it-qat.model.yaml}"
LMSTUDIO_MODEL_DEFINITION_TARGET="${LMSTUDIO_MODEL_DEFINITION_TARGET:-$LMSTUDIO_TARGET_DIR/hub/models/temi/gemma-4-31b-it-qat/model.yaml}"

export LMSTUDIO_PROJECT_ROOT
export LMSTUDIO_TARGET_DIR
export LMSTUDIO_API_IDENTIFIER
export PATH="$LMSTUDIO_TARGET_DIR/bin:$PATH"

hash -r

if [[ "$LMSTUDIO_MODEL_ID" == "temi/gemma-4-31b-it-qat" ]]; then
  if [[ ! -f "$LMSTUDIO_MODEL_DEFINITION_SOURCE" ]]; then
    echo "[LM Studio] Missing model definition: $LMSTUDIO_MODEL_DEFINITION_SOURCE" >&2
    exit 1
  fi
  install -D -m 0644 "$LMSTUDIO_MODEL_DEFINITION_SOURCE" "$LMSTUDIO_MODEL_DEFINITION_TARGET"
  echo "[LM Studio] Installed Gemma 4 LM Studio compatibility definition."
fi

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
echo "[LM Studio] Loading $LMSTUDIO_MODEL_ID with context $LMSTUDIO_CONTEXT_LENGTH as $LMSTUDIO_API_IDENTIFIER..."
lms load "$LMSTUDIO_MODEL_ID" \
  --context-length "$LMSTUDIO_CONTEXT_LENGTH" \
  --gpu max \
  --identifier "$LMSTUDIO_API_IDENTIFIER"

echo "[LM Studio] Current loaded models:"
lms ps

echo "[LM Studio] API models:"
curl -sS "http://127.0.0.1:$LMSTUDIO_SERVER_PORT/v1/models" || true
echo

echo "[LM Studio] Done."
