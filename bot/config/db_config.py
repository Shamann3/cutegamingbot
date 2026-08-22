# -*- coding: utf-8 -*-
"""
Единая, простая конфигурация базы данных для бота и WebApp.

Главный переключатель (в порядке убывания приоритета):
1. Переменные окружения (из app.yaml или DigitalOcean UI).
2. Переменные из DOTENV_B64 (декодированный .env).
3. Файлы .env (server/.env и корневой .env) - для локальной разработки.
4. Файл bot/config/config.py (DATABASE_MODE / DATABASE_LOCATION) - главный переключатель!

Логика:
- APP_MODE = "main" | "test"
- DB_LOCATION = "remote" (SSH-туннель) | "local" (прямое подключение к DO)
"""

from __future__ import annotations

import os
import ssl as _ssl
import base64
import sys
import re
from pathlib import Path
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
#  Пути к .env (только для локальной разработки)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = PROJECT_ROOT / ".env"
SERVER_ENV_FILE = PROJECT_ROOT / "server" / ".env"


# --------------------------------------------------------------------------- #
#  Парсер .env (без внешних зависимостей)
# --------------------------------------------------------------------------- #
def _parse_env_file(path: Path) -> Dict[str, str]:
    """Мини-парсер .env (KEY=VALUE, снимает кавычки)."""
    data: Dict[str, str] = {}
    if not path.is_file():
        return data
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return data
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            data[key] = value
    return data


# --------------------------------------------------------------------------- #
#  Загрузка DOTENV_B64 (код из переменной окружения DigitalOcean)
# --------------------------------------------------------------------------- #
def _load_dotenv_b64_into_env(env_dict: Dict[str, str]) -> None:
    """Декодирует DOTENV_B64 и загружает ключи в словарь."""
    b64_val = os.environ.get("DOTENV_B64", "")
    if not b64_val:
        return
    try:
        decoded_str = base64.b64decode(b64_val).decode("utf-8")
        for line in decoded_str.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env_dict[key.strip()] = value.strip()
    except Exception as e:
        print(f"[DB_CONFIG][ERROR] Ошибка декодирования DOTENV_B64: {e}", file=sys.stderr)


def _file_env(key: str, default: str = "") -> str:
    """Значение из переменных окружения (высший приоритет), затем из DOTENV_B64, затем из файлов .env."""
    value = os.environ.get(key)
    if value:
        return value.strip()

    # Проверяем DOTENV_B64 (декодированный .env)
    dotenv_b64 = os.environ.get("DOTENV_B64", "")
    if dotenv_b64:
        try:
            decoded = base64.b64decode(dotenv_b64).decode("utf-8")
            for line in decoded.splitlines():
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass

    # Проверяем локальные файлы (если код запускается вне DigitalOcean)
    for env_path in (SERVER_ENV_FILE, ROOT_ENV_FILE):
        env_data = _parse_env_file(env_path)
        if key in env_data and env_data[key] != "":
            return env_data[key].strip()

    return default


def _safe_log(msg: str) -> None:
    """Печать без падений на Windows-консоли."""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def _is_true(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def db_debug_log(msg: str) -> None:
    """Лог только при DB_DEBUG=true (по умолчанию включён)."""
    if _file_env("DB_DEBUG", "true").lower() not in ("0", "false", "no", "off"):
        _safe_log(msg)


# --------------------------------------------------------------------------- #
#  Профиль (test / main) и цель (local / remote)
# --------------------------------------------------------------------------- #
_APP_MODE_ALIASES = {
    "test": "test", "dev": "test", "local": "test",
    "main": "main", "prod": "main", "production": "main", "live": "main", "work": "main",
}
_MAIN_TARGET_ALIASES = {
    "local": "local", "localhost": "local", "pg17": "local",
    "remote": "remote", "ssh": "remote", "server": "remote", "cutehost": "remote",
}

# Дефолты для матрицы 2×2: (профиль, расположение).
_DB_DEFAULTS = {
    ("test", "local"):  {"host": "127.0.0.1", "port": "5432",  "name": "cutebase",
                          "user": "postgres", "password": "", "ssl": "false"},
    ("test", "remote"): {"host": "127.0.0.1", "port": "15432", "name": "cutebase",
                          "user": "postgres", "password": "", "ssl": "false"},
    ("main", "local"):  {"host": "127.0.0.1", "port": "5432",  "name": "cutebase",
                          "user": "postgres", "password": "", "ssl": "false"},
    ("main", "remote"): {"host": "127.0.0.1", "port": "15432", "name": "cutebase",
                          "user": "postgres", "password": "", "ssl": "false"},
}


# --------------------------------------------------------------------------- #
#  Чтение config.py (высший приоритет для выбора базы)
# --------------------------------------------------------------------------- #
_CONFIG_PY_FILE = Path(__file__).resolve().parent / "config.py"
if not _CONFIG_PY_FILE.is_file():
    _CONFIG_PY_FILE = Path(__file__).resolve().parent / "db.py"


def _read_config_var(name: str) -> str:
    """Читает переменную из config.py без импорта модуля."""
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    m = re.search(rf'^\s*{name}\s*=\s*["\']([^"\']*)["\']', raw, re.MULTILINE)
    if not m:
        return ""
    return m.group(1).strip().lower()


_CONFIG_PY_MODE: str = _APP_MODE_ALIASES.get(_read_config_var("DATABASE_MODE"), "")
_CONFIG_PY_LOCATION: str = _MAIN_TARGET_ALIASES.get(_read_config_var("DATABASE_LOCATION"), "")


def _resolve_app_mode() -> str:
    # 1) Главный переключатель из config.py
    if _CONFIG_PY_MODE:
        return _CONFIG_PY_MODE
    # 2) Запасной способ из переменных окружения/.env
    raw = _file_env("APP_MODE").lower()
    return _APP_MODE_ALIASES.get(raw, "test")


def _resolve_location() -> str:
    """Где база: local / remote. Сначала config.py, потом переменные окружения."""
    # 1) config.py
    if _CONFIG_PY_LOCATION:
        return _CONFIG_PY_LOCATION
    # 2) Переменные окружения/.env
    raw = _file_env("DB_LOCATION").lower()
    if raw in _MAIN_TARGET_ALIASES:
        return _MAIN_TARGET_ALIASES[raw]
    raw = _file_env("MAIN_DB_TARGET").lower()
    if raw in _MAIN_TARGET_ALIASES:
        return _MAIN_TARGET_ALIASES[raw]
    # 3) Авто: main -> remote (SSH), test -> local
    return "remote" if _resolve_app_mode() == "main" else "local"


# --------------------------------------------------------------------------- #
#  Формирование параметров подключения
# --------------------------------------------------------------------------- #
def resolve_db_field(profile: str, location: str, key: str) -> str:
    """Возвращает значение параметра БД. Приоритет: DB_<KEY>_<PROFILE>_<LOCATION> -> DB_<KEY>_<LOCATION> -> DB_<KEY>_<PROFILE> -> дефолт."""
    up = key.upper()
    prof = profile.upper()
    loc = location.upper()

    order = (f"DB_{up}_{prof}_{loc}", f"DB_{up}_{loc}", f"DB_{up}_{prof}")
    for env_key in order:
        value = _file_env(env_key)
        if value != "":
            return value
    return _DB_DEFAULTS[(profile, location)][key]


APP_MODE: str = _resolve_app_mode()
ACTIVE_DB_PROFILE: str = APP_MODE
DB_LOCATION: str = _resolve_location()
MAIN_DB_TARGET: str = DB_LOCATION  # Обратная совместимость

DB_HOST: str = resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "host")
DB_PORT: int = int(resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "port") or "5432")
DB_NAME: str = resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "name")
DB_USER: str = resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "user")
DB_PASSWORD: str = resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "password")
DB_SSL: str = resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, "ssl").lower() or "auto"


# --------------------------------------------------------------------------- #
#  SSL / пул
# --------------------------------------------------------------------------- #
def db_ssl_mode():
    """False без SSL, контекст для DB_SSL=true, иначе авто."""
    if DB_SSL == "true":
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        return ctx
    if DB_SSL == "false":
        return False
    if DB_HOST in ("localhost", "127.0.0.1", "::1"):
        return False
    return None


def db_pool_min() -> int:
    try:
        return max(1, int(_file_env("DB_POOL_MIN", "1")))
    except ValueError:
        return 1


def db_pool_max() -> int:
    try:
        return max(db_pool_min(), int(_file_env("DB_POOL_MAX", "20")))
    except ValueError:
        return 20


def build_db_settings() -> Dict[str, Any]:
    """Готовый набор параметров для asyncpg.connect / create_pool."""
    return {
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "host": DB_HOST,
        "port": DB_PORT,
        "ssl": db_ssl_mode(),
    }


# --------------------------------------------------------------------------- #
#  Человекочитаемые описания
# --------------------------------------------------------------------------- #
def db_connect_target() -> str:
    """Короткая цель подключения: main/cutebase@host:port"""
    return f"{ACTIVE_DB_PROFILE}/{DB_NAME}@{DB_HOST}:{DB_PORT}"


def db_connected_line(current_db: str) -> str:
    return f"[DB][OK] подключено к '{current_db}' ({db_connect_target()})"


def app_mode_summary() -> str:
    if DB_LOCATION == "remote":
        where = f"сервер CuteHost (SSH-туннель :{DB_PORT})"
    else:
        where = "локальный PostgreSQL (без SSH)"
    passwd = "без пароля" if not DB_PASSWORD else "с паролем"
    return (f"APP_MODE={APP_MODE} | профиль={ACTIVE_DB_PROFILE} | расположение={DB_LOCATION} | "
            f"{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} ({where}) | {passwd}")


db_mode_summary = app_mode_summary


def validate_database_profile() -> List[str]:
    """Мягкие предупреждения (не роняют старт)."""
    warnings: List[str] = []
    name = DB_NAME.strip().lower()
    if APP_MODE == "main" and not DB_PASSWORD:
        warnings.append("APP_MODE=main без пароля: задай DB_PASSWORD_MAIN в .env.")
    if APP_MODE == "main" and name in ("postgres", "template1"):
        warnings.append(f"main подключён к служебной БД '{DB_NAME}', ожидается cutebase.")
    if DB_LOCATION == "remote" and DB_HOST not in ("127.0.0.1", "localhost", "::1"):
        warnings.append(f"remote идёт через SSH-туннель на localhost, сейчас host={DB_HOST}.")
    if DB_LOCATION == "local" and DB_PORT == 15432:
        warnings.append("local на порту :15432 это порт SSH-туннеля. Локально обычно :5432.")
    return warnings


# --------------------------------------------------------------------------- #
#  Инициализация окружения + баннер
# --------------------------------------------------------------------------- #
_BANNER_SHOWN = False


def bootstrap_database_env() -> None:
    """Готовит окружение и печатает выбранную БД (идемпотентно)."""
    global _BANNER_SHOWN

    # Пробрасываем ключи в окружение
    for key in ["APP_MODE", "DB_LOCATION", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSL"]:
        value = globals().get(key, "")
        if value:
            os.environ.setdefault(key, str(value))

    if _BANNER_SHOWN:
        return
    _BANNER_SHOWN = True

    bar = "#" * 64
    loc_word = "СЕРВЕР CuteHost" if DB_LOCATION == "remote" else "ЛОКАЛЬНО"
    if APP_MODE == "main":
        headline = f">>> MAIN ({loc_word}) БОЕВАЯ БАЗА (живые игроки!) <<<"
    else:
        headline = f">>> TEST ({loc_word}) тестовая песочница <<<"

    _safe_log("")
    _safe_log(bar)
    _safe_log(f"##  {headline}")
    _safe_log(f"##  {db_connect_target()}   (расположение={DB_LOCATION})")
    _safe_log(f"##  DATABASE_MODE={ACTIVE_DB_PROFILE} | DATABASE_LOCATION={DB_LOCATION}")
    _safe_log(f"##  сменить: config.py -> DATABASE_MODE и DATABASE_LOCATION")
    _safe_log(bar)

    for warn in validate_database_profile():
        _safe_log(f"  [ВНИМАНИЕ] {warn}")
    _safe_log(bar)