#!/usr/bin/env bash
set -euo pipefail

# Legacy exact-PID viewer stop helper; it refuses an unexpected process identity.

ROOT="${ROOT:-/TemiAgent/anomaly_detection}"
PORT="${PORT:-8010}"
LLAMA_SERVER_PORT="${LLAMA_SERVER_PORT:-8011}"
PID_FILE="$ROOT/action_viewer.pid"

stop_pid() {
  local pid="$1"
  local label="$2"

  if [ -z "$pid" ] || [ ! -d "/proc/$pid" ]; then
    return 0
  fi

  echo "Stopping $label PID: $pid"
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    if kill -0 "$pid" 2>/dev/null; then
      sleep 0.25
    else
      return 0
    fi
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "$label PID $pid did not exit after TERM; using KILL on the same verified PID only."
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

port_pid() {
  local port="$1"
  ss -ltnp "sport = :$port" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1
}

viewer_pid="$(port_pid "$PORT")"
if [ -z "$viewer_pid" ] && [ -f "$PID_FILE" ]; then
  candidate="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$candidate" =~ ^[0-9]+$ ]] && [ -d "/proc/$candidate" ]; then
    viewer_pid="$candidate"
  fi
fi

if [ -n "$viewer_pid" ] && [ -d "/proc/$viewer_pid" ]; then
  viewer_cmdline="$(tr '\0' ' ' < "/proc/$viewer_pid/cmdline")"
  viewer_cwd="$(readlink -f "/proc/$viewer_pid/cwd")"
  if [[ "$viewer_cmdline" != *"temi_action_viewer.py"* || "$viewer_cwd" != "$ROOT" ]]; then
    echo "Refusing to stop PID $viewer_pid; it is not the expected action viewer." >&2
    echo "cwd: $viewer_cwd" >&2
    echo "cmd: $viewer_cmdline" >&2
    exit 1
  fi

  child_pids="$(pgrep -P "$viewer_pid" || true)"
  stop_pid "$viewer_pid" "action viewer"
  for child_pid in $child_pids; do
    if [ -d "/proc/$child_pid" ]; then
      child_cmdline="$(tr '\0' ' ' < "/proc/$child_pid/cmdline")"
      if [[ "$child_cmdline" == *"$ROOT/third_party/llama.cpp"*"/llama-server"* ]]; then
        stop_pid "$child_pid" "managed llama-server child"
      fi
    fi
  done
else
  echo "No action viewer found on port $PORT."
fi

llama_pid="$(port_pid "$LLAMA_SERVER_PORT")"
if [ -n "$llama_pid" ] && [ -d "/proc/$llama_pid" ]; then
  llama_cmdline="$(tr '\0' ' ' < "/proc/$llama_pid/cmdline")"
  llama_cwd="$(readlink -f "/proc/$llama_pid/cwd")"
  if [[ "$llama_cmdline" == *"$ROOT/third_party/llama.cpp"*"/llama-server"* && "$llama_cwd" == "$ROOT" ]]; then
    stop_pid "$llama_pid" "managed llama-server on port $LLAMA_SERVER_PORT"
  else
    echo "Leaving PID $llama_pid on port $LLAMA_SERVER_PORT; it is not the managed anomaly_detection llama-server."
  fi
fi

rm -f "$PID_FILE"

echo "Remaining anomaly_detection listeners:"
ss -ltnp | grep -E ":$PORT|:$LLAMA_SERVER_PORT" || true
