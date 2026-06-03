#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/TemiAgent}"
PC_IP="${PC_IP:-192.168.50.236}"
MQTT_PORT="${MQTT_PORT:-1883}"
VISION_PORT="${VISION_PORT:-8080}"
FRAME_BROADCAST_PORT="${FRAME_BROADCAST_PORT:-8081}"

if ss -ltn | grep -q ":$MQTT_PORT "; then
  echo "MQTT port $MQTT_PORT is already listening."
else
  echo "Starting Mosquitto on 0.0.0.0:$MQTT_PORT..."
  mosquitto -c "$ROOT/mqtt/mosquitto.conf" -d
fi

echo "Starting Temi backend on ws://0.0.0.0:$VISION_PORT and MQTT $PC_IP:$MQTT_PORT..."
cd "$ROOT/temi_backend"
exec env \
  TEMI_MQTT_BROKER="$PC_IP" \
  TEMI_MQTT_PORT="$MQTT_PORT" \
  TEMI_VISION_HOST=0.0.0.0 \
  TEMI_VISION_PORT="$VISION_PORT" \
  TEMI_ENABLE_FRAME_BROADCAST="${TEMI_ENABLE_FRAME_BROADCAST:-true}" \
  TEMI_FRAME_BROADCAST_HOST=0.0.0.0 \
  TEMI_FRAME_BROADCAST_PORT="$FRAME_BROADCAST_PORT" \
  TEMI_LM_BASE_URL="${TEMI_LM_BASE_URL:-http://127.0.0.1:1234/v1}" \
  TEMI_DEBUG_FRAMES_DIR="$ROOT/temi_backend/debug_frames" \
  uv run temi-backend
