#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/TemiAgent/anomaly_detection}"
PORT="${PORT:-8010}"
HOST="${HOST:-0.0.0.0}"
SOURCE_URL="${SOURCE_URL:-ws://127.0.0.1:8081}"
MODEL="${MODEL:-gemma-4-e4b-finetuned@q8_0}"
GGUF_MODEL_PATH="${GGUF_MODEL_PATH:-/TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.Q8_0.gguf}"
MMPROJ_PATH="${MMPROJ_PATH:-/TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.BF16-mmproj.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server}"
LLAMA_API_BASE_URL="${LLAMA_API_BASE_URL:-}"
LLAMA_SERVER_PORT="${LLAMA_SERVER_PORT:-8011}"
POSE_MODE="${POSE_MODE:-auto}"
POSE_MODEL="${POSE_MODEL:-yolo26x-pose.pt}"
POSE_DEVICE="${POSE_DEVICE:-0}"
YOLO_CONFIG_DIR="${YOLO_CONFIG_DIR:-/tmp/Ultralytics}"
MAX_OUTPUT_TOKENS="${MAX_OUTPUT_TOKENS:-96}"
INFERENCE_INTERVAL="${INFERENCE_INTERVAL:-4}"
STARTUP_WAIT_SECONDS="${STARTUP_WAIT_SECONDS:-12}"
LOG_FILE="$ROOT/action_viewer.log"
PID_FILE="$ROOT/action_viewer.pid"

cd "$ROOT"

pid="$(ss -ltnp "sport = :$PORT" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)"
if [ -n "$pid" ]; then
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  cwd="$(readlink -f "/proc/$pid/cwd")"
  if [[ "$cmdline" != *"temi_action_viewer.py"* || "$cwd" != "$ROOT" ]]; then
    echo "Refusing to stop PID $pid; it is not the expected action viewer." >&2
    echo "cwd: $cwd" >&2
    echo "cmd: $cmdline" >&2
    exit 1
  fi
  echo "Stopping exact $PORT action viewer PID: $pid"
  kill -TERM "$pid"
  for _ in $(seq 1 20); do
    if kill -0 "$pid" 2>/dev/null; then
      sleep 0.25
    else
      break
    fi
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "PID $pid did not exit after TERM; using KILL on the same verified PID only."
    kill -KILL "$pid"
    sleep 1
  fi
fi

: > "$LOG_FILE"
export YOLO_CONFIG_DIR
setsid .venv/bin/python ./temi_action_viewer.py \
  --host "$HOST" \
  --port "$PORT" \
  --source-url "$SOURCE_URL" \
  --model "$MODEL" \
  --gguf-model-path "$GGUF_MODEL_PATH" \
  --mmproj-path "$MMPROJ_PATH" \
  --llama-server "$LLAMA_SERVER" \
  --llama-api-base-url "$LLAMA_API_BASE_URL" \
  --llama-server-port "$LLAMA_SERVER_PORT" \
  --pose-mode "$POSE_MODE" \
  --pose-model "$POSE_MODEL" \
  --pose-device "$POSE_DEVICE" \
  --max-output-tokens "$MAX_OUTPUT_TOKENS" \
  --inference-interval "$INFERENCE_INTERVAL" \
  > "$LOG_FILE" 2>&1 < /dev/null &
new_pid="$!"
echo "$new_pid" > "$PID_FILE"

for _ in $(seq 1 "$STARTUP_WAIT_SECONDS"); do
  if ss -ltnp "sport = :$PORT" | grep -q "pid=$new_pid"; then
    break
  fi
  sleep 1
done

if ! ss -ltnp "sport = :$PORT" | grep -q "pid=$new_pid"; then
  echo "Action viewer failed to listen on $PORT; check $LOG_FILE" >&2
  exit 1
fi

python3 - <<PY_HEALTH
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:${PORT}/health", timeout=5) as response:
    print(response.status, response.read().decode("utf-8", "replace"))
PY_HEALTH

echo "Action viewer restarted on port $PORT with PID $new_pid"
