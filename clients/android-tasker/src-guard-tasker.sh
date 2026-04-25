#!/usr/bin/env sh
set -eu

CONFIG_FILE="${SRC_GUARD_CONFIG:-${HOME}/.config/src-guard-tasker.env}"

if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

GUARD_URL="${GUARD_URL:-}"
TOKEN="${TOKEN:-}"

detect_client_name() {
  name=""
  if command -v settings >/dev/null 2>&1; then
    name="$(settings get global device_name 2>/dev/null | sed -n '1p' || true)"
    [ "$name" = "null" ] && name=""
  fi
  if [ -z "$name" ] && command -v getprop >/dev/null 2>&1; then
    name="$(getprop ro.product.model 2>/dev/null | sed -n '1p' || true)"
  fi
  if [ -z "$name" ]; then
    name="$(hostname 2>/dev/null | sed -n '1p' || true)"
  fi
  [ -n "$name" ] || name="android-device"
  printf '%s' "$name"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

CLIENT="${CLIENT:-$(detect_client_name)}"
DURATION="${DURATION:-360}"
HOLD_SECONDS="${HOLD_SECONDS:-45}"
STATE_DIR="${STATE_DIR:-${HOME}/.local/state/src-guard-tasker}"
CURL="${CURL:-curl}"

GENERATION_FILE="${STATE_DIR}/generation"
MODE_FILE="${STATE_DIR}/mode"

usage() {
  cat <<'EOF'
Usage: src-guard-tasker.sh <action>

Actions:
  start              Notify guard and cancel any pending stop.
  refresh            Renew the guard lock through the start webhook.
  refresh-if-active  Renew only when the local client is in playing mode.
  hold-stop          Wait HOLD_SECONDS, then stop if start did not happen again.
  stop               Stop immediately.
  status             Print guard status.

Config:
  Copy src-guard-tasker.env.example to ~/.config/src-guard-tasker.env and edit it.
EOF
}

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_config() {
  [ -n "$GUARD_URL" ] || fail "GUARD_URL is required"
  [ -n "$TOKEN" ] || fail "TOKEN is required"
  [ -n "$CLIENT" ] || fail "CLIENT is required"
}

ensure_state_dir() {
  mkdir -p "$STATE_DIR"
}

new_generation() {
  printf '%s-%s\n' "$(date +%s)" "$$"
}

write_state() {
  ensure_state_dir
  printf '%s\n' "$1" >"$GENERATION_FILE"
  printf '%s\n' "$2" >"$MODE_FILE"
}

clear_state() {
  rm -f "$GENERATION_FILE" "$MODE_FILE"
}

read_generation() {
  [ -f "$GENERATION_FILE" ] && sed -n '1p' "$GENERATION_FILE" || true
}

read_mode() {
  [ -f "$MODE_FILE" ] && sed -n '1p' "$MODE_FILE" || true
}

request() {
  endpoint="$1"
  body="$2"

  if [ "${SRC_GUARD_DRY_RUN:-0}" = "1" ]; then
    printf 'POST %s%s\n%s\n' "$GUARD_URL" "$endpoint" "$body"
    return 0
  fi

  "$CURL" -fsS \
    -X POST "${GUARD_URL}${endpoint}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$body"
}

get_request() {
  endpoint="$1"

  if [ "${SRC_GUARD_DRY_RUN:-0}" = "1" ]; then
    printf 'GET %s%s\n' "$GUARD_URL" "$endpoint"
    return 0
  fi

  "$CURL" -fsS \
    -H "Authorization: Bearer ${TOKEN}" \
    "${GUARD_URL}${endpoint}"
}

start_playing() {
  require_config
  write_state "$(new_generation)" "playing"
  client_json="$(json_escape "$CLIENT")"
  request "/webhook/play/start" "{\"client\":\"${client_json}\",\"duration\":${DURATION}}"
}

refresh_playing() {
  require_config
  client_json="$(json_escape "$CLIENT")"
  request "/webhook/play/start" "{\"client\":\"${client_json}\",\"duration\":${DURATION}}"
}

refresh_if_active() {
  if [ "$(read_mode)" = "playing" ]; then
    refresh_playing
  else
    printf 'SRC Guard client is not in playing mode; renewal skipped.\n'
  fi
}

stop_now() {
  require_config
  client_json="$(json_escape "$CLIENT")"
  request "/webhook/play/stop" "{\"client\":\"${client_json}\"}"
  clear_state
}

finish_hold_stop() {
  require_config
  expected_generation="${SRC_GUARD_EXPECTED_GENERATION:-}"
  [ -n "$expected_generation" ] || fail "SRC_GUARD_EXPECTED_GENERATION is required"

  sleep "$HOLD_SECONDS"

  current_generation="$(read_generation)"
  current_mode="$(read_mode)"
  if [ "$current_generation" = "$expected_generation" ] && [ "$current_mode" = "pending-stop" ]; then
    stop_now
  else
    printf 'SRC Guard pending stop was cancelled.\n'
  fi
}

hold_stop() {
  require_config
  generation="$(read_generation)"
  mode="$(read_mode)"
  if [ -z "$generation" ] || [ "$mode" != "playing" ]; then
    printf 'SRC Guard client is not in playing mode; hold-stop skipped.\n'
    return 0
  fi

  write_state "$generation" "pending-stop"

  if [ "${SRC_GUARD_FOREGROUND_HOLD:-0}" = "1" ]; then
    SRC_GUARD_EXPECTED_GENERATION="$generation" finish_hold_stop
    return 0
  fi

  nohup env \
    SRC_GUARD_CONFIG="$CONFIG_FILE" \
    SRC_GUARD_EXPECTED_GENERATION="$generation" \
    GUARD_URL="$GUARD_URL" \
    TOKEN="$TOKEN" \
    CLIENT="$CLIENT" \
    DURATION="$DURATION" \
    HOLD_SECONDS="$HOLD_SECONDS" \
    STATE_DIR="$STATE_DIR" \
    CURL="$CURL" \
    "$0" finish-hold-stop >/dev/null 2>&1 &
  printf 'SRC Guard stop scheduled after %s seconds.\n' "$HOLD_SECONDS"
}

action="${1:-}"

case "$action" in
  start)
    start_playing
    ;;
  refresh)
    refresh_playing
    ;;
  refresh-if-active)
    refresh_if_active
    ;;
  hold-stop)
    hold_stop
    ;;
  finish-hold-stop)
    finish_hold_stop
    ;;
  stop)
    stop_now
    ;;
  status)
    require_config
    get_request "/status"
    ;;
  "" | -h | --help | help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
