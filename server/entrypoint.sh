#!/bin/sh
# Точка входа контейнера. Если задан SSH_TUNNEL_HOST — перед запуском приложения
# поднимаем постоянный SSH-туннель к серверу с базой (CuteHost) и держим его живым.
# Приложение затем коннектится к 127.0.0.1:<LPORT>, туннель пробрасывает на Postgres.
# Пароль передаётся через SSH_ASKPASS (в контейнере нет TTY, sshpass не работает).
set -e

if [ -n "$SSH_TUNNEL_HOST" ]; then
  LPORT="${SSH_TUNNEL_LOCAL_PORT:-15432}"
  RHOST="${SSH_TUNNEL_REMOTE_HOST:-127.0.0.1}"
  RPORT="${SSH_TUNNEL_REMOTE_PORT:-5432}"
  SPORT="${SSH_TUNNEL_PORT:-22}"
  SUSER="${SSH_TUNNEL_USER:-root}"

  echo "[tunnel] ${SUSER}@${SSH_TUNNEL_HOST}:${SPORT}  forward 127.0.0.1:${LPORT} -> ${RHOST}:${RPORT}"

  # askpass-скрипт: отдаёт пароль из окружения без запроса в терминале.
  ASKPASS=/tmp/ssh_askpass.sh
  cat > "$ASKPASS" <<'EOF'
#!/bin/sh
printf '%s\n' "$SSH_TUNNEL_PASSWORD"
EOF
  chmod +x "$ASKPASS"

  # Фоновый цикл: держим туннель живым, при обрыве переподключаемся.
  (
    while true; do
      SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force ssh -v -N \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=20 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o ConnectTimeout=15 \
        -o PreferredAuthentications=password \
        -o PubkeyAuthentication=no \
        -o NumberOfPasswordPrompts=1 \
        -p "$SPORT" \
        -L "127.0.0.1:${LPORT}:${RHOST}:${RPORT}" \
        "${SUSER}@${SSH_TUNNEL_HOST}" 2>&1 | sed 's/^/[ssh] /'
      echo "[tunnel] ssh session ended, reconnect in 5s..."
      sleep 5
    done
  ) &

  echo "[tunnel] waiting for 127.0.0.1:${LPORT} ..."
  python - "$LPORT" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(40):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            print("[tunnel] up", flush=True)
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("[tunnel] WARNING: local port not reachable after 40s", flush=True)
PY
fi

exec "$@"
