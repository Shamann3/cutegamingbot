#!/bin/sh
# Точка входа контейнера. Если задан SSH_TUNNEL_HOST — перед запуском приложения
# поднимаем постоянный SSH-туннель к серверу с базой (CuteHost) и держим его живым.
# Приложение затем коннектится к 127.0.0.1:<LPORT>, туннель пробрасывает на Postgres.
# Так порт Postgres НЕ нужно открывать наружу — наружу торчит только SSH (22).
set -e

if [ -n "$SSH_TUNNEL_HOST" ]; then
  LPORT="${SSH_TUNNEL_LOCAL_PORT:-15432}"
  RHOST="${SSH_TUNNEL_REMOTE_HOST:-127.0.0.1}"
  RPORT="${SSH_TUNNEL_REMOTE_PORT:-5432}"
  SPORT="${SSH_TUNNEL_PORT:-22}"
  SUSER="${SSH_TUNNEL_USER:-root}"

  echo "[tunnel] ${SUSER}@${SSH_TUNNEL_HOST}:${SPORT}  forward 127.0.0.1:${LPORT} -> ${RHOST}:${RPORT}"

  # Фоновый цикл: держим туннель живым, при обрыве переподключаемся.
  # sshpass передаёт пароль при КАЖДОМ переподключении (в отличие от autossh).
  (
    while true; do
      sshpass -p "$SSH_TUNNEL_PASSWORD" ssh -N \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=20 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -p "$SPORT" \
        -L "${LPORT}:${RHOST}:${RPORT}" \
        "${SUSER}@${SSH_TUNNEL_HOST}" || true
      echo "[tunnel] ssh exited, reconnect in 3s..."
      sleep 3
    done
  ) &

  echo "[tunnel] waiting for 127.0.0.1:${LPORT} ..."
  python - "$LPORT" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(30):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            print("[tunnel] up", flush=True)
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("[tunnel] WARNING: local port not reachable after 30s", flush=True)
PY
fi

exec "$@"
