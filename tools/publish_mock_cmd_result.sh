#!/usr/bin/env bash
set -euo pipefail

# Explicit test publisher for a mock command result; it is not Android execution evidence.

BROKER="${BROKER:-localhost}"
PORT="${PORT:-1883}"
ROBOT_ID="${ROBOT_ID:-temi-01}"
EVENT_ID="${EVENT_ID:-evt_bridge_test_001}"
COMMAND_ID="${COMMAND_ID:-cmd_manual_result_001}"

payload="$(
  python3 - "$ROBOT_ID" "$EVENT_ID" "$COMMAND_ID" <<'PY'
import json
import sys
import time

robot_id, event_id, command_id = sys.argv[1:4]
print(json.dumps({
    "schema_version": "1.0",
    "command_id": command_id,
    "event_id": event_id,
    "robot_id": robot_id,
    "status": "success",
    "results": [
        {"action_id": "act_001", "type": "speak", "status": "success", "message": "mock result"}
    ],
    "finished_at_ms": int(time.time() * 1000),
}, ensure_ascii=False))
PY
)"

mosquitto_pub -h "$BROKER" -p "$PORT" -t "temi/$ROBOT_ID/cmd/result" -m "$payload"
echo "published temi/$ROBOT_ID/cmd/result event_id=$EVENT_ID command_id=$COMMAND_ID"
