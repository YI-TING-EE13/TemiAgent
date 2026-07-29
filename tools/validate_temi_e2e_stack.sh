#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${ROOT:-/TemiAgent}"
: "${PC_IP:?Set PC_IP to the MQTT/video host address.}"
: "${TEMI_IP:?Set TEMI_IP to the Temi robot address.}"
ROBOT_ID="${ROBOT_ID:-temi-01}"
MODEL_IDENTIFIER="${MODEL_IDENTIFIER:-google/gemma-4-31b}"
MODEL_LOAD_ID="${MODEL_LOAD_ID:-temi/gemma-4-31b-it-qat}"
CONTEXT_LENGTH="${CONTEXT_LENGTH:-64000}"
LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0,1}"
MQTT_PORT="${MQTT_PORT:-1883}"
VISION_PORT="${VISION_PORT:-8080}"
FRAME_BROADCAST_PORT="${FRAME_BROADCAST_PORT:-8081}"
HERMES_PORT="${HERMES_PORT:-8765}"
ACTION_VIEWER_PORT="${ACTION_VIEWER_PORT:-8010}"
LLAMA_SERVER_PORT="${LLAMA_SERVER_PORT:-8011}"
START_GATEWAY="${START_GATEWAY:-1}"
GATEWAY_CONNECT_TIMEOUT_SECONDS="${GATEWAY_CONNECT_TIMEOUT_SECONDS:-90}"
HERMES_BIN="${HERMES_BIN:-$ROOT/hermes-agent/venv/bin/hermes}"
RESTART_SERVICES="${RESTART_SERVICES:-1}"
RESTART_LMSTUDIO="${RESTART_LMSTUDIO:-1}"
RUN_HARDWARE_CHECKS="${RUN_HARDWARE_CHECKS:-1}"
RUN_UNIT_TESTS="${RUN_UNIT_TESTS:-1}"
RUN_LOCAL_E2E="${RUN_LOCAL_E2E:-1}"
RUN_DEMO_CASES="${RUN_DEMO_CASES:-1}"
RUN_LIVE_E2E="${RUN_LIVE_E2E:-1}"
LIVE_E2E_TIMEOUT_SECONDS="${LIVE_E2E_TIMEOUT_SECONDS:-240}"
LIVE_E2E_TEXT="${LIVE_E2E_TEXT:-請你說系統端到端測試成功}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/e2e_stack_validation_$(date +%Y%m%d_%H%M%S)}"

mkdir -p "$LOG_ROOT"

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

fail() {
  printf '\n[FAIL] %s\n' "$*" >&2
  printf '[INFO] Logs: %s\n' "$LOG_ROOT" >&2
  exit 1
}

run_logged() {
  local name="$1"
  shift
  log "$name"
  "$@" > "$LOG_ROOT/$name.log" 2>&1 || {
    tail -n 80 "$LOG_ROOT/$name.log" >&2 || true
    fail "$name failed; see $LOG_ROOT/$name.log"
  }
}

wait_http() {
  local url="$1"
  local seconds="$2"
  local name="$3"
  for _ in $(seq 1 "$seconds"); do
    if curl -fsS "$url" > /dev/null 2>&1; then
      log "$name is ready: $url"
      return 0
    fi
    sleep 1
  done
  fail "$name did not become ready: $url"
}

pid_matches_process() {
  local pid="$1"
  local expected_cwd="$2"
  shift 2
  local cwd
  local cmdline
  local token

  [ -d "/proc/$pid" ] || return 1
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  if [ -n "$expected_cwd" ] && [ "$cwd" != "$expected_cwd" ]; then
    return 1
  fi
  for token in "$@"; do
    [[ "$cmdline" == *"$token"* ]] || return 1
  done
}

stop_verified_processes() {
  local label="$1"
  local expected_cwd="$2"
  shift 2
  local search_token="$1"
  local pid
  local cwd
  local cmdline
  local -a verified_pids=()

  : > "$LOG_ROOT/${label}_before_stop.log"
  while read -r pid; do
    [ -n "$pid" ] || continue
    [ "$pid" != "$$" ] || continue
    [ -d "/proc/$pid" ] || continue
    pid_matches_process "$pid" "$expected_cwd" "$@" || continue
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    printf 'pid=%s cwd=%s cmd=%s\n' "$pid" "$cwd" "$cmdline" \
      >> "$LOG_ROOT/${label}_before_stop.log"
    verified_pids+=("$pid")
  done < <(pgrep -f -- "$search_token" 2>/dev/null || true)

  if [ "${#verified_pids[@]}" -eq 0 ]; then
    log "$label was not running"
    return 0
  fi

  for pid in "${verified_pids[@]}"; do
    pid_matches_process "$pid" "$expected_cwd" "$@" || continue
    log "Stopping verified $label PID $pid"
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 2
  for pid in "${verified_pids[@]}"; do
    if pid_matches_process "$pid" "$expected_cwd" "$@"; then
      log "Forcing verified $label PID $pid to stop"
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
}

require_cmd() {
  local command_name="$1"
  command -v "$command_name" > /dev/null 2>&1 || fail "Missing command: $command_name"
}

wait_gateway() {
  local seconds="$1"
  local status_file="$LOG_ROOT/gateway_status.log"
  local state_file="/root/.hermes/gateway_state.json"
  for _ in $(seq 1 "$seconds"); do
    if "$HERMES_BIN" gateway status > "$status_file" 2>&1 && grep -q "Gateway is running" "$status_file"; then
      if python3 - "$state_file" <<'INNERPY'
import json
import sys
from pathlib import Path
state_path = Path(sys.argv[1])
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(1)
platforms = state.get("platforms") or {}
discord = platforms.get("discord") or {}
sys.exit(0 if discord.get("state") == "connected" else 1)
INNERPY
      then
        cp "$state_file" "$LOG_ROOT/gateway_state.json" 2>/dev/null || true
        log "Hermes gateway is ready: Discord connected"
        return 0
      fi
    fi
    sleep 1
  done
  "$HERMES_BIN" gateway status > "$status_file" 2>&1 || true
  cp "$state_file" "$LOG_ROOT/gateway_state.json" 2>/dev/null || true
  cat "$status_file" >&2 || true
  cat "$LOG_ROOT/gateway_state.json" >&2 || true
  fail "Hermes gateway did not report Discord connected within $seconds seconds"
}

cd "$ROOT" || fail "Cannot cd to $ROOT"

log "TemiAgent E2E stack validation started"
log "Project root: $ROOT"
log "Logs: $LOG_ROOT"
log "PC_IP=$PC_IP TEMI_IP=$TEMI_IP ROBOT_ID=$ROBOT_ID MODEL=$MODEL_IDENTIFIER LOAD=$MODEL_LOAD_ID CONTEXT=$CONTEXT_LENGTH"

require_cmd curl
require_cmd ss
require_cmd mosquitto_pub
require_cmd mosquitto_sub
require_cmd python3

if [ "$RESTART_LMSTUDIO" = "1" ]; then
  run_logged start_lmstudio env \
    LMSTUDIO_MODEL_ID="$MODEL_LOAD_ID" \
    LMSTUDIO_API_IDENTIFIER="$MODEL_IDENTIFIER" \
    LMSTUDIO_CONTEXT_LENGTH="$CONTEXT_LENGTH" \
    LMSTUDIO_VISIBLE_GPUS="$LMSTUDIO_VISIBLE_GPUS" \
    "$ROOT/tools/start_lmstudio_3gpu.sh"
else
  log "Skipping LM Studio restart because RESTART_LMSTUDIO=$RESTART_LMSTUDIO"
fi

wait_http "http://127.0.0.1:1234/v1/models" 120 "LM Studio API"
export PATH="$ROOT/.lmstudio-data/bin:$PATH"
if command -v lms > /dev/null 2>&1; then
  lms ps > "$LOG_ROOT/lms_ps.log" 2>&1 || true
  if ! grep -q "$MODEL_IDENTIFIER" "$LOG_ROOT/lms_ps.log"; then
    cat "$LOG_ROOT/lms_ps.log" >&2 || true
    fail "LM Studio does not show expected model: $MODEL_IDENTIFIER"
  fi
  if ! grep -q "$CONTEXT_LENGTH" "$LOG_ROOT/lms_ps.log"; then
    cat "$LOG_ROOT/lms_ps.log" >&2 || true
    fail "LM Studio does not show expected context length: $CONTEXT_LENGTH"
  fi
  if grep -q "${MODEL_IDENTIFIER}:2" "$LOG_ROOT/lms_ps.log"; then
    cat "$LOG_ROOT/lms_ps.log" >&2 || true
    fail "Duplicate LM Studio model instance detected: ${MODEL_IDENTIFIER}:2"
  fi
fi

if [ "$RESTART_SERVICES" = "1" ]; then
  if [ "$START_GATEWAY" = "1" ]; then
    stop_verified_processes "hermes_gateway" "$ROOT" "$HERMES_BIN" "gateway" "run"
  fi
  stop_verified_processes "bridge" "$ROOT/hermes_temi_bridge" "hermes-temi-bridge"
  stop_verified_processes "hermes_resident" "$ROOT" \
    "tools/hermes_resident_server.py"
  stop_verified_processes "temi_overview_adapter" "$ROOT/temi_backend" \
    "$ROOT/tools/temi_overview_adapter.py"
  stop_verified_processes "mosquitto" "" \
    "mosquitto" "-c" "$ROOT/mqtt/mosquitto.conf"

  log "Starting MQTT broker"
  mosquitto -c "$ROOT/mqtt/mosquitto.conf" -d
  sleep 1

  log "Starting Overview adapter"
  (cd "$ROOT/temi_backend" && setsid uv run python "$ROOT/tools/temi_overview_adapter.py" \
    --broker "$PC_IP" \
    --port "$MQTT_PORT" \
    --vision-port "$VISION_PORT" \
    --frame-broadcast-port "$FRAME_BROADCAST_PORT" \
    --shared-root "$ROOT/temi_shared" \
    --bridge-root "$ROOT/temi_shared" \
    --conversation-id conv_first_year_demo \
    > "$LOG_ROOT/temi-overview-adapter.log" 2>&1 < /dev/null &)

  log "Starting Hermes resident server"
  (cd "$ROOT" && setsid python3 tools/hermes_resident_server.py \
    --host 127.0.0.1 \
    --port "$HERMES_PORT" \
    --skill-path "$ROOT/hermes-agent/skills/temi-robot-control/SKILL.md" \
    --skill-path "$ROOT/hermes-agent/skills/temi-care-memory/SKILL.md" \
    --skill-path "$ROOT/hermes-agent/skills/temi-home-esi/SKILL.md" \
    --skill-path "$ROOT/hermes-agent/skills/temi-discord-care-assistant/SKILL.md" \
    > "$LOG_ROOT/hermes_resident.log" 2>&1 < /dev/null &)

  log "Starting HermesTemiBridge"
  mkdir -p "$ROOT/logs/overview_bridge_resident" "$ROOT/memory"
  (cd "$ROOT/hermes_temi_bridge" && setsid env \
    MQTT_BROKER_HOST="$PC_IP" \
    MQTT_BROKER_PORT="$MQTT_PORT" \
    TEMI_SHARED_BRIDGE_PATH="$ROOT/temi_shared" \
    TEMI_SHARED_HERMES_PATH="$ROOT/temi_shared" \
    HERMES_INVOKE_MODE=http \
    HERMES_HTTP_URL="http://127.0.0.1:$HERMES_PORT/invoke" \
    HERMES_TIMEOUT_SECONDS=180 \
    MEMORY_DIR="$ROOT/memory" \
    LOG_DIR="$ROOT/logs/overview_bridge_resident" \
    uv run --extra mqtt hermes-temi-bridge --env-file "$ROOT/hermes_temi_bridge/.env.example" \
    > "$LOG_ROOT/bridge_runtime.log" 2>&1 < /dev/null &)


  if [ "$START_GATEWAY" = "1" ]; then
    if [ ! -x "$HERMES_BIN" ]; then
      fail "Hermes gateway binary is not executable: $HERMES_BIN"
    fi
    log "Starting Hermes gateway"
    (cd "$ROOT" && setsid env HERMES_ACCEPT_HOOKS=1 "$HERMES_BIN" gateway run \
      > "$LOG_ROOT/hermes_gateway.log" 2>&1 < /dev/null &)
  else
    log "Skipping Hermes gateway start because START_GATEWAY=$START_GATEWAY"
  fi

  log "Restarting action viewer"
  (cd "$ROOT/anomaly_detection" && ./restart_action_viewer_8010.sh > "$LOG_ROOT/action_viewer_restart.log" 2>&1) || {
    tail -n 80 "$LOG_ROOT/action_viewer_restart.log" >&2 || true
    fail "Action viewer restart failed"
  }
else
  log "Skipping service restart because RESTART_SERVICES=$RESTART_SERVICES"
fi

wait_http "http://127.0.0.1:$HERMES_PORT/health" 120 "Hermes resident"
if [ "$START_GATEWAY" = "1" ]; then
  wait_gateway "$GATEWAY_CONNECT_TIMEOUT_SECONDS"
fi
wait_http "http://127.0.0.1:$ACTION_VIEWER_PORT/health" 120 "Action viewer"

curl -fsS "http://127.0.0.1:$HERMES_PORT/health" > "$LOG_ROOT/hermes_health.json"
if ! grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' "$LOG_ROOT/hermes_health.json"; then
  cat "$LOG_ROOT/hermes_health.json" >&2
  fail "Hermes health did not report status ok"
fi
if ! grep -q "$MODEL_IDENTIFIER" "$LOG_ROOT/hermes_health.json"; then
  cat "$LOG_ROOT/hermes_health.json" >&2
  fail "Hermes health did not report expected model $MODEL_IDENTIFIER"
fi
if [ -f /root/.hermes/config.yaml ]; then
  cp /root/.hermes/config.yaml "$LOG_ROOT/hermes_config.yaml"
  if ! grep -q "default:[[:space:]]*$MODEL_IDENTIFIER" "$LOG_ROOT/hermes_config.yaml"; then
    cat "$LOG_ROOT/hermes_config.yaml" >&2
    fail "Hermes config does not set model.default to $MODEL_IDENTIFIER"
  fi
  if ! grep -q "context_length:[[:space:]]*$CONTEXT_LENGTH" "$LOG_ROOT/hermes_config.yaml"; then
    cat "$LOG_ROOT/hermes_config.yaml" >&2
    fail "Hermes config does not contain expected context_length $CONTEXT_LENGTH"
  fi
else
  log "Hermes config /root/.hermes/config.yaml not found; context was verified from LM Studio only"
fi

curl -fsS "http://127.0.0.1:$ACTION_VIEWER_PORT/health" > "$LOG_ROOT/action_viewer_health.json"
if ! grep -q '"ok"[[:space:]]*:[[:space:]]*true' "$LOG_ROOT/action_viewer_health.json"; then
  cat "$LOG_ROOT/action_viewer_health.json" >&2
  fail "Action viewer health did not report ok=true"
fi

ss -ltnp > "$LOG_ROOT/listening_ports.txt" || true
for port in 1234 "$MQTT_PORT" "$VISION_PORT" "$FRAME_BROADCAST_PORT" "$HERMES_PORT" "$ACTION_VIEWER_PORT" "$LLAMA_SERVER_PORT"; do
  if ! grep -q ":$port" "$LOG_ROOT/listening_ports.txt"; then
    cat "$LOG_ROOT/listening_ports.txt" >&2
    fail "Expected port is not listening: $port"
  fi
done

if [ "$RUN_HARDWARE_CHECKS" = "1" ]; then
  run_logged check_temi_connection env TEMI_IP="$TEMI_IP" PC_IP="$PC_IP" "$ROOT/tools/check_temi_connection.sh"
  if command -v adb > /dev/null 2>&1; then
    run_logged adb_connect adb connect "$TEMI_IP:5555"
    adb shell am start -n com.robotemi.agent/.MainActivity > "$LOG_ROOT/adb_start_app.log" 2>&1 || true
    sleep 10
  else
    log "adb not found; skipping app start"
  fi
  ss -tn state established > "$LOG_ROOT/established_connections.txt" || true
  if grep -Eq "$TEMI_IP.*:($MQTT_PORT|$VISION_PORT)|:($MQTT_PORT|$VISION_PORT).*$TEMI_IP" "$LOG_ROOT/established_connections.txt"; then
    log "Temi established connection detected"
  else
    log "No Temi established connection detected yet; continuing because hardware connection may need manual app restart"
  fi
else
  log "Skipping hardware checks because RUN_HARDWARE_CHECKS=$RUN_HARDWARE_CHECKS"
fi

if [ "$RUN_UNIT_TESTS" = "1" ]; then
  run_logged bridge_unittest bash -lc "cd '$ROOT/hermes_temi_bridge' && uv run python -m unittest discover -s tests"
  run_logged temi_backend_pytest bash -lc "cd '$ROOT/temi_backend' && uv run pytest"
  run_logged anomaly_detection_unittest bash -lc "cd '$ROOT/anomaly_detection' && uv run python -m unittest discover -s tests"
else
  log "Skipping unit tests because RUN_UNIT_TESTS=$RUN_UNIT_TESTS"
fi

if [ "$RUN_LOCAL_E2E" = "1" ]; then
  run_logged local_mock_e2e bash -lc "cd '$ROOT' && python3 tools/e2e_test_runner.py"
else
  log "Skipping local mock E2E because RUN_LOCAL_E2E=$RUN_LOCAL_E2E"
fi

if [ "$RUN_DEMO_CASES" = "1" ]; then
  run_logged demo_case_runner bash -lc "cd '$ROOT' && python3 tools/demo_case_runner.py --keep-artifacts"
else
  log "Skipping demo case runner because RUN_DEMO_CASES=$RUN_DEMO_CASES"
fi

if [ "$RUN_LIVE_E2E" = "1" ]; then
  log "Running live ASR-event to Temi command/result E2E"
  request_file="$LOG_ROOT/live_cmd_request.log"
  result_file="$LOG_ROOT/live_cmd_result.log"
  : > "$request_file"
  : > "$result_file"

  timeout "$LIVE_E2E_TIMEOUT_SECONDS" mosquitto_sub -h "$PC_IP" -p "$MQTT_PORT" -t "temi/$ROBOT_ID/cmd/request" -C 1 -v > "$request_file" 2> "$LOG_ROOT/live_cmd_request.err" &
  req_pid="$!"
  timeout "$LIVE_E2E_TIMEOUT_SECONDS" mosquitto_sub -h "$PC_IP" -p "$MQTT_PORT" -t "temi/$ROBOT_ID/cmd/result" -C 1 -v > "$result_file" 2> "$LOG_ROOT/live_cmd_result.err" &
  res_pid="$!"
  sleep 1

  event_id="evt_validation_$(date +%s)"
  run_logged publish_mock_asr env \
    BROKER="$PC_IP" \
    PORT="$MQTT_PORT" \
    ROBOT_ID="$ROBOT_ID" \
    EVENT_ID="$event_id" \
    SHARED_ROOT="$ROOT/temi_shared" \
    BRIDGE_ROOT="$ROOT/temi_shared" \
    TEXT="$LIVE_E2E_TEXT" \
    "$ROOT/tools/publish_mock_asr_event.sh"

  wait "$req_pid" || fail "Did not receive cmd/request within $LIVE_E2E_TIMEOUT_SECONDS seconds"
  wait "$res_pid" || fail "Did not receive cmd/result within $LIVE_E2E_TIMEOUT_SECONDS seconds"

  if ! grep -q 'cmd/request' "$request_file"; then
    cat "$request_file" >&2
    fail "cmd/request message was empty or malformed"
  fi
  if ! grep -q '"speak"' "$request_file"; then
    cat "$request_file" >&2
    fail "cmd/request did not include a speak action"
  fi
  if ! grep -q '"status"[[:space:]]*:[[:space:]]*"success"' "$result_file"; then
    cat "$result_file" >&2
    fail "cmd/result did not report status success"
  fi
  log "Live E2E received command request and success result"
else
  log "Skipping live E2E because RUN_LIVE_E2E=$RUN_LIVE_E2E"
fi

log "Validation completed successfully"
printf '\n[PASS] TemiAgent E2E stack validation completed. Logs: %s\n' "$LOG_ROOT"
