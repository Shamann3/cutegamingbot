"""Проверка единой конфигурации: бот и WebApp-API читают одну и ту же БД,
а перенесённые из server/.env серверные ключи (токены/админ) доступны серверу.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.config.db_config import (
    APP_MODE,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    DB_SSL,
    DB_LOCATION,
    MAIN_DB_TARGET,
    bootstrap_database_env,
    db_connect_target,
)

bootstrap_database_env()

import importlib.util

_server_cfg_path = ROOT / "server" / "config.py"
_spec = importlib.util.spec_from_file_location("server_config", _server_cfg_path)
server_config = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(server_config)

bot_target = db_connect_target()
server_target = (
    f"{server_config.ACTIVE_DB_PROFILE}/{server_config.DB_NAME}"
    f"@{server_config.DB_HOST}:{server_config.DB_PORT}"
)

# 1) Полное совпадение параметров ПОДКЛЮЧЕНИЯ (не только host/port/name).
conn_checks = {
    "APP_MODE": (APP_MODE, server_config.APP_MODE),
    "DB_HOST": (DB_HOST, server_config.DB_HOST),
    "DB_PORT": (DB_PORT, server_config.DB_PORT),
    "DB_NAME": (DB_NAME, server_config.DB_NAME),
    "DB_USER": (DB_USER, server_config.DB_USER),
    "DB_PASSWORD": (DB_PASSWORD, server_config.DB_PASSWORD),
    "DB_SSL": (DB_SSL, server_config.DB_SSL),
    "DB_LOCATION": (DB_LOCATION, server_config.DB_LOCATION),
    "MAIN_DB_TARGET": (MAIN_DB_TARGET, server_config.MAIN_DB_TARGET),
}

print(f"[verify] bot:    {bot_target} (APP_MODE={APP_MODE}, location={DB_LOCATION})")
print(f"[verify] server: {server_target} (APP_MODE={server_config.APP_MODE})")

mismatches = [name for name, (a, b) in conn_checks.items() if a != b]
for name in mismatches:
    a, b = conn_checks[name]
    print(f"[verify]   РАСХОЖДЕНИЕ {name}: bot={a!r} != server={b!r}")

# 2) Серверные ключи, перенесённые в корневой .env, должны читаться сервером.
server_keys = ("BOT_TOKEN", "ADMIN_BOT_TOKEN", "ADMIN_LOGIN_KEY", "ADMIN_JWT_SECRET")
missing_keys = [k for k in server_keys if not getattr(server_config, k, "")]
for k in missing_keys:
    print(f"[verify]   ВНИМАНИЕ: серверный ключ {k} не виден серверу (пуст).")

# 3) admin_auth должен находить ADMIN_LOGIN_KEY в корневом .env.
sys.path.insert(0, str(ROOT / "server"))
admin_key_ok = True
try:
    import admin_auth  # noqa: E402
    fresh = admin_auth._read_login_key_from_env_file()
    admin_key_ok = bool(fresh)
    src = admin_auth._ENV_FILE
    print(f"[verify] admin_auth ADMIN_LOGIN_KEY из: {src} → {'найден' if admin_key_ok else 'ПУСТО'}")
except Exception as e:  # pragma: no cover
    admin_key_ok = False
    print(f"[verify] admin_auth проверка не удалась: {type(e).__name__}: {e}")

if not mismatches and not missing_keys and admin_key_ok:
    print("[verify] OK — единая конфигурация: одна БД + серверные ключи в корневом .env")
    raise SystemExit(0)

print("[verify] FAIL — конфигурация не единая. Правьте ТОЛЬКО корневой .env и config.py")
raise SystemExit(1)
