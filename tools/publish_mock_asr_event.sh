#!/usr/bin/env bash
set -euo pipefail

BROKER="${BROKER:-localhost}"
PORT="${PORT:-1883}"
ROBOT_ID="${ROBOT_ID:-temi-01}"
EVENT_ID="${EVENT_ID:-evt_bridge_test_001}"
SHARED_ROOT="${SHARED_ROOT:-temi_shared}"
BRIDGE_ROOT="${BRIDGE_ROOT:-/var/lib/temi_shared}"
TEXT="${TEXT:-幫我看看桌上的東西是什麼}"

payload="$(
  python3 "$(dirname "$0")/create_mock_event_images.py" \
    --shared-root "$SHARED_ROOT" \
    --bridge-root "$BRIDGE_ROOT" \
    --robot-id "$ROBOT_ID" \
    --event-id "$EVENT_ID" \
    --text "$TEXT" \
    --print-event
)"

mosquitto_pub -h "$BROKER" -p "$PORT" -t "temi/$ROBOT_ID/asr/final" -m "$payload"
echo "published temi/$ROBOT_ID/asr/final event_id=$EVENT_ID"
