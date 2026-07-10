#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# CuteUpdate1 full Linux launcher (start_all.bat analogue)
#
# Starts (by default):
#   1) API server (FastAPI/uvicorn)
#   2) WebApp preview (Vite)
#   3) Main bot (main.py)
#   4) Farm bots (server/bots_runner.py)
#
# Commands:
#   ./start_all_linux.sh start
#   ./start_all_linux.sh stop
#   ./start_all_linux.sh restart
#   ./start_all_linux.sh status
#   ./start_all_linux.sh logs
# ============================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
ROOT_ENV_FILE="$ROOT_DIR/.env"
RUN_DIR="$ROOT_DIR/.run/linux"
LOG_DIR="$ROOT_DIR/logs/linux"

LOCK_FILE="/var/lock/cute_start_all_linux.lock"

API_PID_FILE="$RUN_DIR/api.pid"
PREVIEW_PID_FILE="$RUN_DIR/preview.pid"
MAIN_PID_FILE="$RUN_DIR/main.pid"
FARM_BOTS_PID_FILE="$RUN_DIR/farm-bots.pid"

MASTER_LOG="$LOG_DIR/start_all.log"
API_LOG="$LOG_DIR/api.log"
PREVIEW_LOG="$LOG_DIR/preview.log"
MAIN_LOG="$LOG_DIR/main.log"
FARM_BOTS_LOG="$LOG_DIR/farm-bots.log"

# -------------------- runtime config --------------------
COMMAND="${1:-restart}"

API_ENABLE=1
PREVIEW_ENABLE=1
MAIN_ENABLE=1
FARM_BOTS_ENABLE=1

SKIP_INSTALL=0

API_PORT="${API_PORT:-8000}"
PREVIEW_PORT="${PREVIEW_PORT:-5173}"

# main.py is often in a separate root venv on servers
MAIN_PYTHON="${MAIN_PYTHON:-/root/myenv/bin/python3}"
MAIN_SCRIPT="${MAIN_SCRIPT:-$ROOT_DIR/main.py}"

# API/farm-bots run from server venv
SERVER_PYTHON="${SERVER_PYTHON:-$SERVER_DIR/.venv/bin/python}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

log() {
  printf "[start_all] %s | %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$MASTER_LOG" >/dev/null
}
ok()   { log "[OK]   $*"; }
warn() { log "[WARN] $*"; }
fail() { log "[FAIL] $*"; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  ./start_all_linux.sh start [options]
  ./start_all_linux.sh stop
  ./start_all_linux.sh restart [options]
  ./start_all_linux.sh status
  ./start_all_linux.sh logs

Options:
  --skip-install      Skip pip/npm install
  --skip-api          Do not start API
  --skip-preview      Do not start WebApp preview
  --skip-main         Do not start main.py
  --skip-farm-bots    Do not start server/bots_runner.py
  --api-port <port>   API port (default: 8000)
  --preview-port <p>  Preview port (default: 5173)
  -h, --help          Show help
EOF
}

read_env_value() {
  local key="$1"
  [[ -f "$ROOT_ENV_FILE" ]] || { printf ''; return 0; }
  awk -F= -v k="$key" '
    $0 ~ "^[[:space:]]*" k "[[:space:]]*=" {
      val = $0
      sub("^[[:space:]]*" k "[[:space:]]*=[[:space:]]*", "", val)
      gsub(/\r$/, "", val)
      if ((val ~ /^".*"$/) || (val ~ /^'\''.*'\''$/)) {
        val = substr(val, 2, length(val) - 2)
      }
      print val
    }
  ' "$ROOT_ENV_FILE" | tail -n 1
}

print_https_links_banner() {
  local farm_https admin_https
  farm_https="$(read_env_value "WEBAPP_URL")"
  admin_https="$(read_env_value "ADMIN_WEBAPP_URL")"

  if [[ -z "$farm_https" ]]; then
    farm_https="(not set, add WEBAPP_URL in .env)"
  fi
  if [[ -z "$admin_https" ]]; then
    admin_https="(not set, add ADMIN_WEBAPP_URL in .env)"
  fi

  local banner
  banner="$(cat <<EOF

======================================================================
!!! IMPORTANT HTTPS LINKS (farm + admin) !!!
FARM HTTPS  : $farm_https
ADMIN HTTPS : $admin_https
======================================================================

EOF
)"

  printf "%s" "$banner"
  printf "%s" "$banner" >> "$MASTER_LOG"
}

parse_args() {
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-install)   SKIP_INSTALL=1 ;;
      --skip-api)       API_ENABLE=0 ;;
      --skip-preview)   PREVIEW_ENABLE=0 ;;
      --skip-main)      MAIN_ENABLE=0 ;;
      --skip-farm-bots) FARM_BOTS_ENABLE=0 ;;
      --api-port)
        shift
        API_PORT="${1:-$API_PORT}"
        ;;
      --preview-port)
        shift
        PREVIEW_PORT="${1:-$PREVIEW_PORT}"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

with_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    fail "Another start/stop/restart is already running"
  fi
}

is_pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local f="$1"
  [[ -f "$f" ]] && tr -d '[:space:]' < "$f" || true
}

cleanup_stale_pid_file() {
  local f="$1"
  local pid
  pid="$(read_pid "$f")"
  if [[ -n "$pid" ]] && ! is_pid_alive "$pid"; then
    rm -f "$f"
  fi
}

stop_from_pid_file() {
  local name="$1"
  local pid_file="$2"
  cleanup_stale_pid_file "$pid_file"

  local pid
  pid="$(read_pid "$pid_file")"
  if [[ -z "$pid" ]]; then
    return 0
  fi

  if is_pid_alive "$pid"; then
    log "Stopping $name (PID $pid) with TERM"
    kill -TERM "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      if ! is_pid_alive "$pid"; then
        break
      fi
      sleep 0.5
    done
    if is_pid_alive "$pid"; then
      warn "$name PID $pid still alive, sending KILL"
      kill -KILL "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$pid_file" || true
}

stop_by_pattern() {
  local pattern="$1"
  if command -v pkill >/dev/null 2>&1; then
    pkill -f -- "$pattern" 2>/dev/null || true
  else
    pgrep -af -- "$pattern" 2>/dev/null | awk '{print $1}' | xargs -r -n 20 kill -TERM 2>/dev/null || true
  fi
  sleep 1
  pgrep -af -- "$pattern" 2>/dev/null | awk '{print $1}' | xargs -r -n 20 kill -KILL 2>/dev/null || true
}

wait_http_ok() {
  local url="$1"
  local timeout="$2"
  if ! command -v curl >/dev/null 2>&1; then
    warn "curl not found, skip HTTP check: $url"
    return 0
  fi
  local start_ts
  start_ts="$(date +%s)"
  while true; do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( "$(date +%s)" - start_ts >= timeout )); then
      return 1
    fi
    sleep 1
  done
}

ensure_server_venv() {
  if [[ ! -x "$SERVER_PYTHON" ]]; then
    command -v python3 >/dev/null 2>&1 || fail "python3 not found"
    log "Creating server virtualenv in $SERVER_DIR/.venv"
    python3 -m venv "$SERVER_DIR/.venv"
  fi

  if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    log "Installing server dependencies..."
    "$SERVER_PYTHON" -m pip install --upgrade pip >/dev/null
    "$SERVER_PYTHON" -m pip install -r "$SERVER_DIR/requirements-server.txt"
  else
    warn "Skipping dependency installation (--skip-install)"
  fi
}

run_db_debug_checks() {
  log "Checking unified DB config..."
  "$SERVER_PYTHON" "$ROOT_DIR/scripts/verify_unified_db.py"
  log "Checking PostgreSQL connectivity..."
  "$SERVER_PYTHON" "$ROOT_DIR/scripts/test_db_connection.py"
}

start_component() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  local workdir="$4"
  shift 4
  local cmd=( "$@" )

  : > "$log_file"
  log "Starting $name: ${cmd[*]}"
  (
    cd "$workdir"
    nohup "${cmd[@]}" >> "$log_file" 2>&1 &
    echo $! > "$pid_file"
  )

  sleep 3

  local pid
  pid="$(read_pid "$pid_file")"
  if [[ -z "$pid" ]] || ! is_pid_alive "$pid"; then
    warn "$name failed to start, last log lines:"
    tail -n 80 "$log_file" | tee -a "$MASTER_LOG" >/dev/null || true
    return 1
  fi

  ok "$name started (PID=$pid)"
  return 0
}

stop_all() {
  log "=== STOP sequence started ==="
  stop_from_pid_file "Preview" "$PREVIEW_PID_FILE"
  stop_by_pattern "vite preview --host 0.0.0.0 --port $PREVIEW_PORT --strictPort"

  stop_from_pid_file "Farm bots" "$FARM_BOTS_PID_FILE"
  stop_by_pattern "$SERVER_PYTHON $SERVER_DIR/bots_runner.py"

  stop_from_pid_file "Main bot" "$MAIN_PID_FILE"
  stop_by_pattern "$MAIN_PYTHON $MAIN_SCRIPT"

  stop_from_pid_file "API" "$API_PID_FILE"
  stop_by_pattern "$SERVER_PYTHON -m uvicorn app:app --host 0.0.0.0 --port $API_PORT"
  log "=== STOP sequence finished ==="
}

start_all() {
  [[ -f "$ROOT_DIR/.env" ]] || fail "Root .env not found: $ROOT_DIR/.env"
  [[ -f "$MAIN_SCRIPT" ]] || fail "Main bot script not found: $MAIN_SCRIPT"

  log "=== START sequence started ==="
  log "ROOT_DIR=$ROOT_DIR"
  log "API_PORT=$API_PORT PREVIEW_PORT=$PREVIEW_PORT"
  log "MAIN_PYTHON=$MAIN_PYTHON"

  ensure_server_venv
  run_db_debug_checks

  if [[ "$API_ENABLE" -eq 1 ]]; then
    start_component "API" "$API_PID_FILE" "$API_LOG" "$SERVER_DIR" \
      env PYTHONUNBUFFERED=1 "$SERVER_PYTHON" -m uvicorn app:app --host 0.0.0.0 --port "$API_PORT" || fail "API start failed"
    if wait_http_ok "http://127.0.0.1:$API_PORT/health" 90; then
      ok "API health OK: http://127.0.0.1:$API_PORT/health"
    else
      tail -n 120 "$API_LOG" | tee -a "$MASTER_LOG" >/dev/null || true
      fail "API health check timeout"
    fi
  else
    warn "API skipped"
  fi

  if [[ "$PREVIEW_ENABLE" -eq 1 ]]; then
    if ! command -v npm >/dev/null 2>&1; then
      warn "npm not found. WebApp preview skipped (install Node.js to enable)."
    else
      if [[ "$SKIP_INSTALL" -eq 0 ]]; then
        if [[ ! -d "$ROOT_DIR/node_modules" ]]; then
          log "Installing frontend dependencies..."
          (cd "$ROOT_DIR" && npm ci)
        fi
        log "Building frontend..."
        (cd "$ROOT_DIR" && npm run build)
      fi

      start_component "Preview" "$PREVIEW_PID_FILE" "$PREVIEW_LOG" "$ROOT_DIR" \
        env NODE_ENV=production npm run preview -- --host 0.0.0.0 --port "$PREVIEW_PORT" --strictPort || warn "Preview start failed"

      if wait_http_ok "http://127.0.0.1:$PREVIEW_PORT/" 60; then
        ok "WebApp preview OK: http://127.0.0.1:$PREVIEW_PORT/"
      else
        warn "WebApp preview health timeout (see $PREVIEW_LOG)"
      fi
    fi
  else
    warn "WebApp preview skipped"
  fi

  if [[ "$MAIN_ENABLE" -eq 1 ]]; then
    if [[ ! -x "$MAIN_PYTHON" ]]; then
      fail "MAIN_PYTHON is not executable: $MAIN_PYTHON"
    fi
    start_component "Main bot" "$MAIN_PID_FILE" "$MAIN_LOG" "$ROOT_DIR" \
      env PYTHONUNBUFFERED=1 "$MAIN_PYTHON" "$MAIN_SCRIPT" || fail "Main bot start failed"
  else
    warn "Main bot skipped"
  fi

  if [[ "$FARM_BOTS_ENABLE" -eq 1 ]]; then
    start_component "Farm bots" "$FARM_BOTS_PID_FILE" "$FARM_BOTS_LOG" "$SERVER_DIR" \
      env PYTHONUNBUFFERED=1 CF_DB_LIGHT_CONNECT=1 "$SERVER_PYTHON" "$SERVER_DIR/bots_runner.py" || fail "Farm bots start failed"
  else
    warn "Farm bots skipped"
  fi

  log "=== START sequence finished ==="
  print_https_links_banner
}

show_status() {
  local row_name row_pid_file row_log_file pid status

  printf "\n%-14s %-8s %-10s %s\n" "Component" "Status" "PID" "Log"
  printf "%-14s %-8s %-10s %s\n" "---------" "------" "---" "---"

  while IFS='|' read -r row_name row_pid_file row_log_file; do
    cleanup_stale_pid_file "$row_pid_file"
    pid="$(read_pid "$row_pid_file")"
    if [[ -n "$pid" ]] && is_pid_alive "$pid"; then
      status="RUNNING"
    else
      status="STOPPED"
      pid="-"
    fi
    printf "%-14s %-8s %-10s %s\n" "$row_name" "$status" "$pid" "$row_log_file"
  done <<EOF
API|$API_PID_FILE|$API_LOG
Preview|$PREVIEW_PID_FILE|$PREVIEW_LOG
MainBot|$MAIN_PID_FILE|$MAIN_LOG
FarmBots|$FARM_BOTS_PID_FILE|$FARM_BOTS_LOG
EOF
  printf "\n"
  print_https_links_banner
}

follow_logs() {
  touch "$API_LOG" "$PREVIEW_LOG" "$MAIN_LOG" "$FARM_BOTS_LOG"
  log "Following logs (Ctrl+C to stop):"
  tail -n 80 -f "$API_LOG" "$PREVIEW_LOG" "$MAIN_LOG" "$FARM_BOTS_LOG"
}

main() {
  case "$COMMAND" in
    start|restart|stop|status|logs|help|-h|--help) ;;
    *)
      usage
      fail "Unknown command: $COMMAND"
      ;;
  esac

  if [[ "$COMMAND" == "help" || "$COMMAND" == "-h" || "$COMMAND" == "--help" ]]; then
    usage
    exit 0
  fi

  parse_args "$@"
  with_lock

  case "$COMMAND" in
    restart)
      stop_all
      show_status
      start_all
      show_status
      ;;
    start)
      start_all
      show_status
      ;;
    stop)
      stop_all
      show_status
      ;;
    status)
      show_status
      ;;
    logs)
      follow_logs
      ;;
  esac
}

main "$@"

