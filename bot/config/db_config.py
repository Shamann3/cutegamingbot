"""Единая, простая конфигурация базы данных для бота и WebApp.

Один переключатель APP_MODE в .env:
    APP_MODE=test  →  локальная cutebase   @ localhost:5432        (без SSH)
    APP_MODE=main  →  боевая  cutebase      @ 127.0.0.1:15432      (SSH-туннель)

Дополнительно:
    MAIN_DB_TARGET=remote  →  main идёт через SSH-туннель на CuteHost (порт 15432)
    MAIN_DB_TARGET=local   →  main идёт в локальный PostgreSQL (SSH не нужен)

Значения для каждого профиля берутся из .env по суффиксу профиля:
    DB_HOST_TEST / DB_PORT_TEST / DB_NAME_TEST / DB_USER_TEST / DB_PASSWORD_TEST / DB_SSL_TEST
    DB_HOST_MAIN / DB_PORT_MAIN / DB_NAME_MAIN / DB_USER_MAIN / DB_PASSWORD_MAIN / DB_SSL_MAIN

Этот модуль единственный источник правды. И бот, и WebApp, и скрипты
импортируют настройки отсюда, поэтому все всегда смотрят в одну и ту же БД.
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
#  Пути к .env
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = PROJECT_ROOT / ".env"
SERVER_ENV_FILE = PROJECT_ROOT / "server" / ".env"

# --------------------------------------------------------------------------- #
#  Чтение DOTENV_B64 (НОВОЕ УЛУЧШЕНИЕ)
# --------------------------------------------------------------------------- #
def _load_dotenv_b64_into_env(env_dict: Dict[str, str]) -> None:
    """Декодирует DOTENV_B64 и загружает ключи прямо в словарь env_dict."""
    b64_val = os.environ.get("DOTENV_B64", "")
    if not b64_val:
        return  # Если переменной нет (например, локально) - пропускаем

    try:
        decoded_str = base64.b64decode(b64_val).decode("utf-8")
        for line in decoded_str.splitlines():
            line = line.strip().replace('\r', '')  # Защита от Windows
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env_dict[key.strip()] = value.strip()
    except Exception as e:
        print(f"[DB_CONFIG][ERROR] Не удалось декодировать DOTENV_B64: {e}", file=sys.stderr)

# --------------------------------------------------------------------------- #
#  Парсер .env
# --------------------------------------------------------------------------- #
def _parse_env_file(path: Path) -> Dict[str, str]:
    """Мини-парсер .env без внешних зависимостей (KEY=VALUE, снимает кавычки)."""
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


def _load_file_env() -> Dict[str, str]:
    """server/.env читается первым, корневой .env перекрывает его (главный)."""
    merged: Dict[str, str] = {}
    merged.update(_parse_env_file(SERVER_ENV_FILE))
    merged.update(_parse_env_file(ROOT_ENV_FILE))
    # Добавляем DOTENV_B64 поверх всех файлов (высший приоритет)
    _load_dotenv_b64_into_env(merged)
    return merged


_FILE_ENV: Dict[str, str] = _load_file_env()


def _file_env(key: str, default: str = "") -> str:
    """Значение из .env (приоритет) или из окружения процесса."""
    if key in _FILE_ENV and _FILE_ENV[key] != "":
        return _FILE_ENV[key].strip()
    return os.environ.get(key, default).strip()


def _safe_log(msg: str) -> None:
    """Печать без падений на Windows-консоли (эмодзи/кириллица)."""
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
#  Профиль (test / main) и цель main (local / remote)
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
#   local  → прямой локальный PostgreSQL (:5432) или прямое подключение к DigitalOcean
#   remote → сервер CuteHost через SSH-туннель (:15432)
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


# Поиск файла конфигурации (поддержка и db.py, и config.py)
_CONFIG_PY_FILE = Path(__file__).resolve().parent / "db.py"
if not _CONFIG_PY_FILE.is_file():
    _CONFIG_PY_FILE = Path(__file__).resolve().parent / "config.py"


def _read_config_var(name: str) -> str:
    """Читает строковую переменную (DATABASE_MODE/DATABASE_LOCATION) из db.py или config.py
    БЕЗ импорта модуля. Парсинг файла чтобы и бот, и сервер читали одно и то же
    значение независимо от sys.path. Возвращает сырое значение (нижний регистр) или ''.
    """
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    m = re.search(rf'^\s*{name}\s*=\s*["\']([^"\']*)["\']', raw, re.MULTILINE)
    if not m:
        return ""
    return m.group(1).strip().lower()


# Значения главных переключателей из config.py (высший приоритет).
_CONFIG_PY_MODE: str = _APP_MODE_ALIASES.get(_read_config_var("DATABASE_MODE"), "")
_CONFIG_PY_LOCATION: str = _MAIN_TARGET_ALIASES.get(_read_config_var("DATABASE_LOCATION"), "")


def _resolve_app_mode() -> str:
    # 1) Главный переключатель проекта: DATABASE_MODE в bot/config/db.py (или config.py).
    if _CONFIG_PY_MODE:
        return _CONFIG_PY_MODE
    # 2) Запасной способ: APP_MODE в .env.
    raw = _file_env("APP_MODE").lower()
    return _APP_MODE_ALIASES.get(raw, "test")


def _resolve_location() -> str:
    """Где база: local / remote. Применяется к ЛЮБОМУ профилю (main или test)."""
    # 1) config.py DATABASE_LOCATION
    if _CONFIG_PY_LOCATION:
        return _CONFIG_PY_LOCATION
    # 2) .env DB_LOCATION
    raw = _file_env("DB_LOCATION").lower()
    if raw in _MAIN_TARGET_ALIASES:
        return _MAIN_TARGET_ALIASES[raw]
    # 3) .env MAIN_DB_TARGET (совместимость со старой схемой)
    raw = _file_env("MAIN_DB_TARGET").lower()
    if raw in _MAIN_TARGET_ALIASES:
        return _MAIN_TARGET_ALIASES[raw]
    # 4) авто: main → сервер (remote), test → локально (local)
    return "remote" if APP_MODE == "main" else "local"


# host/port/ssl зависят от РАСПОЛОЖЕНИЯ (local:5432 / remote:15432 через туннель),
# а name/user/password от ПРОФИЛЯ (это идентичность и креды самой базы).
_LOCATION_KEYS = frozenset({"host", "port", "ssl"})


def resolve_db_field(profile: str, location: str, key: str) -> str:
    """Значение параметра БД для конкретной пары (профиль, расположение).

    Точечный ключ DB_<KEY>_<PROFILE>_<LOCATION> всегда имеет высший приоритет.
    Далее:
      • host/port/ssl  →  DB_<KEY>_<LOCATION>  →  дефолт расположения
      • name/user/pass →  DB_<KEY>_<PROFILE>   →  DB_<KEY>_<LOCATION>  →  дефолт
    """
    up = key.upper()
    prof = profile.upper()
    loc = location.upper()
    if key in _LOCATION_KEYS:
        order = (f"DB_{up}_{prof}_{loc}", f"DB_{up}_{loc}")
    else:
        order = (f"DB_{up}_{prof}_{loc}", f"DB_{up}_{prof}", f"DB_{up}_{loc}")
    for env_key in order:
        value = _file_env(env_key)
        if value != "":
            return value
    return _DB_DEFAULTS[(profile, location)][key]


def _profile_value(key: str) -> str:
    """Значение для АКТИВНОЙ пары (ACTIVE_DB_PROFILE, DB_LOCATION)."""
    return resolve_db_field(ACTIVE_DB_PROFILE, DB_LOCATION, key)


APP_MODE: str = _resolve_app_mode()
APP_MODE_IS_EXPLICIT: bool = bool(_CONFIG_PY_MODE) or _file_env("APP_MODE") != ""
ACTIVE_DB_PROFILE: str = APP_MODE  # профиль == режим (test/main)
DB_LOCATION: str = _resolve_location()
MAIN_DB_TARGET: str = DB_LOCATION  # обратная совместимость (старое имя = расположение)

DB_HOST: str = _profile_value("host")
DB_PORT: int = int(_profile_value("port") or "5432")
DB_NAME: str = _profile_value("name")
DB_USER: str = _profile_value("user")
DB_PASSWORD: str = _profile_value("password")
DB_SSL: str = _profile_value("ssl").lower() or "auto"


# --------------------------------------------------------------------------- #
#  SSL / пул
# --------------------------------------------------------------------------- #
def db_ssl_mode():
    """False без SSL (локально), контекст для явного DB_SSL=true, иначе авто."""
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
#  Человекочитаемые описания «куда подключаемся»
# --------------------------------------------------------------------------- #
def db_connect_target() -> str:
    """Короткая цель подключения: main/cutebase@127.0.0.1:15432"""
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


# Совместимое имя, которое ожидает bot/db_create/db.py
db_mode_summary = app_mode_summary


def validate_database_profile() -> List[str]:
    """Мягкие предупреждения о подозрительной конфигурации (не роняют старт)."""
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
    """Готовит окружение и один раз печатает выбранную БД (идемпотентно)."""
    global _BANNER_SHOWN

    # Пробрасываем ключи .env в окружение процесса чтобы дочерние процессы
    # (например, plink для SSH-туннеля) и сторонний код видели те же значения.
    for key, value in _FILE_ENV.items():
        os.environ.setdefault(key, value)

    # Главный переключатель из config.py имеет приоритет: жёстко выставляем
    # APP_MODE в окружении, чтобы дочерние процессы и любой сторонний код
    # (SSH-туннель, скрипты) видели ровно ту же выбранную базу.
    if _CONFIG_PY_MODE:
        os.environ["APP_MODE"] = _CONFIG_PY_MODE

    if _BANNER_SHOWN:
        return
    _BANNER_SHOWN = True

    bar = "#" * 64
    loc_word = "СЕРВЕР CuteHost" if DB_LOCATION == "remote" else "ЛОКАЛЬНО"
    if APP_MODE == "main":
        headline = f">>> MAIN ({loc_word}) БОЕВАЯ БАЗА (живые игроки!) <<<"
    else:
        headline = f">>> TEST ({loc_word}) тестовая песочница <<<"

    # Крупный блок сверху переключатель базы невозможно не заметить.
    _safe_log("")
    _safe_log(bar)
    _safe_log(f"##  {headline}")
    _safe_log(f"##  {db_connect_target()}   (расположение={DB_LOCATION})")
    src_mode = "config.py" if _CONFIG_PY_MODE else ".env"
    src_loc = "config.py" if _CONFIG_PY_LOCATION else ".env/авто"
    _safe_log(f"##  DATABASE_MODE={ACTIVE_DB_PROFILE} (из {src_mode}) | "
              f"DATABASE_LOCATION={DB_LOCATION} (из {src_loc})")
    _safe_log(f"##  сменить: config.py -> DATABASE_MODE и DATABASE_LOCATION")
    _safe_log(bar)

    # Матрица 2×2 видно все доступные комбинации и какая активна.
    _safe_log("  БАЗА ДАННЫХ матрица профиль × расположение:")
    for profile in ("test", "main"):
        for location in ("local", "remote"):
            active = (profile == ACTIVE_DB_PROFILE and location == DB_LOCATION)
            marker = "  <== АКТИВНАЯ" if active else ""
            host = resolve_db_field(profile, location, "host")
            port = resolve_db_field(profile, location, "port")
            name = resolve_db_field(profile, location, "name")
            _safe_log(f"  {profile:4} + {location:6} : {host}:{port}/{name}{marker}")
    _safe_log("")
    _safe_log(f"  {app_mode_summary()}")
    for warn in validate_database_profile():
        _safe_log(f"  [ВНИМАНИЕ] {warn}")
    _safe_log(bar)