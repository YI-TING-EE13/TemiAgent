#!/usr/bin/env bash
set -euo pipefail

# Legacy machine-specific background starter; use scripts/demo for the canonical lifecycle.

ROOT="${ROOT:-/TemiAgent}"
: "${PC_IP:?Set PC_IP to the Temi-facing MQTT/video host address.}"
MQTT_PORT="${MQTT_PORT:-1883}"
VISION_PORT="${VISION_PORT:-8080}"
FRAME_BROADCAST_PORT="${FRAME_BROADCAST_PORT:-8081}"
LOG_DIR="$ROOT/logs"
BACKEND_LOG="$LOG_DIR/temi-backend.log"
BACKEND_PID="$LOG_DIR/temi-backend.pid"

mkdir -p "$LOG_DIR"

if ! ss -ltn | grep -q ":$MQTT_PORT "; then
  mosquitto -c "$ROOT/mqtt/mosquitto.conf" -d
fi

if ss -ltn | grep -q ":$VISION_PORT "; then
  echo "Vision/backend port $VISION_PORT is already listening."
else
  cd "$ROOT/temi_backend"
  setsid env \
    TEMI_MQTT_BROKER="$PC_IP" \
    TEMI_MQTT_PORT="$MQTT_PORT" \
    TEMI_VISION_HOST=0.0.0.0 \
    TEMI_VISION_PORT="$VISION_PORT" \
    TEMI_ENABLE_FRAME_BROADCAST="${TEMI_ENABLE_FRAME_BROADCAST:-true}" \
    TEMI_FRAME_BROADCAST_HOST=0.0.0.0 \
    TEMI_FRAME_BROADCAST_PORT="$FRAME_BROADCAST_PORT" \
    TEMI_LM_BASE_URL="${TEMI_LM_BASE_URL:-http://127.0.0.1:1234/v1}" \
    TEMI_DEBUG_FRAMES_DIR="$ROOT/temi_backend/debug_frames" \
    uv run temi-backend >> "$BACKEND_LOG" 2>&1 &
  echo "$!" > "$BACKEND_PID"
  sleep 2
fi

ss -ltnp | grep -E ":$MQTT_PORT|:$VISION_PORT|:$FRAME_BROADCAST_PORT|:5037" || true
echo "Backend log: $BACKEND_LOG"
