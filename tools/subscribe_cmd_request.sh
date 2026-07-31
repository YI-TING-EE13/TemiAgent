#!/usr/bin/env bash
set -euo pipefail

# Read-only MQTT observer for canonical command requests.

BROKER="${BROKER:-localhost}"
PORT="${PORT:-1883}"
ROBOT_ID="${ROBOT_ID:-temi-01}"

mosquitto_sub -h "$BROKER" -p "$PORT" -t "temi/$ROBOT_ID/cmd/request" -v
