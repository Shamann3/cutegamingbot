import os
import ssl
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

# Единый источник: КОРНЕВОЙ .env (БД, SSH, токены, CORS, farm — всё здесь).
# server/.env — пустая заглушка для обратной совместимости.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(__file__).resolve().parent / ".env"
ROOT_ENV_FILE = PROJECT_ROOT / ".env"


def _merge_env_files(*paths: Path) -> dict[str, str]:
    merged: dict[str, str] = {}
    for env_path in paths:
        if not env_path.is_file():
            continue
        for key, value in dotenv_values(env_path).items():
            if value is not None:
                merged[key] = str(value).strip()
    return merged


# ЕДИНЫЙ ИСТОЧНИК: корневой .env АВТОРИТЕТНЫЙ. server/.env читается только
# как fallback (сейчас это пустая заглушка) — так конфигурация бота и сервера
# физически не может разойтись. В _merge_env_files побеждает последний файл,
# поэтому ROOT_ENV_FILE идёт ПОСЛЕ ENV_FILE.
_FILE_ENV: dict[str, str] = _merge_env_files(ENV_FILE, ROOT_ENV_FILE)

if ENV_FILE.is_file():
    load_dotenv(ENV_FILE, override=False)
load_dotenv(ROOT_ENV_FILE, override=True)


def _file_env(key: str, default: str = "") -> str:
    """Значение конфигурации: сперва из .env-файлов, затем из окружения процесса.

    Локально авторитетен корневой .env; на хостинге (DigitalOcean и т.п.) файла
    нет — тогда берём переменную окружения, заданную в панели.
    """
    val = _FILE_ENV.get(key)
    if val is None or val == "":
        env_val = os.environ.get(key, "")
        val = env_val if env_val != "" else default
    return val.strip()


# Чистим ТОЛЬКО «системные» PG*-переменные, которые asyncpg/libpq могли бы
# подхватить неявно. DATABASE_URL и PRODUCTION НЕ трогаем — на хостинге это
# легитимный способ передать конфигурацию через окружение.
for _sys_key in (
    "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD",
):
    if _sys_key not in _FILE_ENV or not _FILE_ENV.get(_sys_key):
        os.environ.pop(_sys_key, None)

_APP_MODE_ALIASES = {
    "test": "test",
    "dev": "test",
    "local": "test",
    "main": "main",
    "work": "main",
    "live": "main",
    "prod": "main",
    "production": "main",
}


_CONFIG_PY_FILE = PROJECT_ROOT / "bot" / "config" / "config.py"


def _read_config_database_mode() -> str:
    """Главный переключатель проекта: DATABASE_MODE из bot/config/config.py.

    Читаем файл напрямую (без импорта пакета bot) — сервер-процесс не зависит
    от sys.path бота, а бот и сервер всегда читают ОДНО и то же значение.
    """
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    import re
    m = re.search(r'^\s*DATABASE_MODE\s*=\s*["\']([^"\']*)["\']', raw, re.MULTILINE)
    if not m:
        return ""
    return _APP_MODE_ALIASES.get(m.group(1).strip().lower(), "")


_CONFIG_PY_MODE = _read_config_database_mode()


def _read_config_py_token() -> str:
    """Токен бота модерации (получает фото-пруфы): bot/config/config.py → TOKEN.

    Как и DATABASE_MODE, читаем файл напрямую (без импорта пакета bot) — сервер
    берёт токен из ТОГО ЖЕ источника, что и main.py. Поэтому при смене TOKEN в
    одном месте и бот, и админ-панель сразу используют новый токен: архив
    продолжает скачивать доказательства ботом, который их принял.

    Важно: Telegram file_id привязан к БОТУ (bot_id), а не к строке токена, —
    перевыпущенный в BotFather токен того же бота качает и старые file_id.
    Поэтому читать актуальный TOKEN из конфига достаточно и для старых пруфов.
    """
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    import re
    # ^TOKEN = "..." (не EDEN_TOKEN / TOKENtest / закомментированные строки).
    m = re.search(r'^\s*TOKEN\s*=\s*["\']([^"\']+)["\']', raw, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _resolve_app_mode() -> str:
    # 1) Главный переключатель проекта: DATABASE_MODE в bot/config/config.py.
    if _CONFIG_PY_MODE:
        return _CONFIG_PY_MODE
    # 2) Запасные способы (совместимость со старым поведением).
    raw = _file_env("APP_MODE").lower()
    if raw in _APP_MODE_ALIASES:
        return _APP_MODE_ALIASES[raw]
    if _file_env("PRODUCTION").lower() == "true":
        return "main"
    profile = _file_env("DB_PROFILE").lower()
    if profile in ("test", "main"):
        return profile
    return "test"


APP_MODE = _resolve_app_mode()
APP_MODE_IS_EXPLICIT = bool(_CONFIG_PY_MODE) or bool(_file_env("APP_MODE"))

if APP_MODE_IS_EXPLICIT:
    PRODUCTION = APP_MODE == "main"
    ALLOW_DEV_AUTH = APP_MODE == "test"
else:
    ALLOW_DEV_AUTH = _file_env("ALLOW_DEV_AUTH", "false").lower() == "true"
    PRODUCTION = _file_env("PRODUCTION", "false").lower() == "true"

_DB_PROFILE_KEYS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_SSL",
    "DATABASE_URL",
)
def _mk_defaults(port: str) -> dict:
    return {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": port,
        "DB_NAME": "cutebase",
        "DB_USER": "postgres",
        "DB_PASSWORD": "",
        "DB_SSL": "false",
        "DATABASE_URL": "",
    }


# Матрица 2×2: (профиль, расположение). local → :5432, remote → :15432 (SSH-туннель).
_DB_PROFILE_DEFAULTS = {
    ("test", "local"):  _mk_defaults("5432"),
    ("test", "remote"): _mk_defaults("15432"),
    ("main", "local"):  _mk_defaults("5432"),
    ("main", "remote"): _mk_defaults("15432"),
}

_MAIN_DB_TARGET_ALIASES = {
    "local": "local",
    "pg17": "local",
    "localhost": "local",
    "remote": "remote",
    "cutehost": "remote",
    "ssh": "remote",
    "server": "remote",
}


def _read_config_database_location() -> str:
    """DATABASE_LOCATION из bot/config/config.py (читаем файл, без импорта)."""
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    import re
    m = re.search(r'^\s*DATABASE_LOCATION\s*=\s*["\']([^"\']*)["\']', raw, re.MULTILINE)
    if not m:
        return ""
    return _MAIN_DB_TARGET_ALIASES.get(m.group(1).strip().lower(), "")


_CONFIG_PY_LOCATION = _read_config_database_location()


def _resolve_main_db_target() -> str:
    """Где база: local / remote. Применяется к любому профилю (main/test)."""
    # 1) config.py DATABASE_LOCATION (высший приоритет — синхронно с ботом)
    if _CONFIG_PY_LOCATION:
        return _CONFIG_PY_LOCATION
    # 2) .env DB_LOCATION
    raw = _file_env("DB_LOCATION").lower()
    if raw in _MAIN_DB_TARGET_ALIASES:
        return _MAIN_DB_TARGET_ALIASES[raw]
    # 3) .env MAIN_DB_TARGET (совместимость)
    raw = _file_env("MAIN_DB_TARGET").lower()
    if raw in _MAIN_DB_TARGET_ALIASES:
        return _MAIN_DB_TARGET_ALIASES[raw]
    # 4) авто
    if APP_MODE == "main":
        return "remote"
    return "local"


MAIN_DB_TARGET = _resolve_main_db_target()
DB_LOCATION = MAIN_DB_TARGET


def active_db_profile() -> str:
    """test = local sandbox DB, main = production cutebase."""
    if APP_MODE_IS_EXPLICIT:
        return APP_MODE
    profile = _file_env("DB_PROFILE").lower()
    if profile in ("test", "main"):
        return profile
    return "main" if PRODUCTION else "test"


def _profile_db_config_present() -> bool:
    for suffix in ("TEST", "MAIN"):
        for key in _DB_PROFILE_KEYS:
            if _file_env(f"{key}_{suffix}"):
                return True
    return False


# host/port/ssl зависят от РАСПОЛОЖЕНИЯ, name/user/password/url — от ПРОФИЛЯ.
_LOCATION_KEYS = frozenset({"DB_HOST", "DB_PORT", "DB_SSL"})


def _resolve_db_value(key: str) -> str:
    # DATABASE_URL — прямой сигнал «подключайся по строке к managed-базе».
    # Раньше APP_MODE_IS_EXPLICIT (ниже) обрывал резолвинг ДО того, как эта
    # переменная вообще проверялась, поэтому заданный на хостинге DATABASE_URL
    # тихо игнорировался и подключение уезжало на SSH-туннель по DB_HOST/PORT
    # профиля (main+remote) — те могли указывать на давно удалённый сервер.
    # Проверяем DATABASE_URL первым делом, с высшим приоритетом, независимо
    # от APP_MODE.
    if key == "DATABASE_URL":
        direct = _file_env("DATABASE_URL")
        if direct:
            return direct

    profile = active_db_profile()
    loc = DB_LOCATION
    prof_up = profile.upper()
    loc_up = loc.upper()

    # test DB_PASSWORD: пустое значение = подключение без пароля (trust на localhost).
    if profile == "test" and key == "DB_PASSWORD":
        for k in (f"DB_PASSWORD_{prof_up}_{loc_up}", f"DB_PASSWORD_{prof_up}"):
            if k in _FILE_ENV:
                return _FILE_ENV[k].strip().strip('"')

    # Точечный ключ (профиль+расположение) — всегда первый.
    if key in _LOCATION_KEYS:
        order = (f"{key}_{prof_up}_{loc_up}", f"{key}_{loc_up}")
    else:
        order = (f"{key}_{prof_up}_{loc_up}", f"{key}_{prof_up}", f"{key}_{loc_up}")
    for env_key in order:
        value = _file_env(env_key)
        if value:
            return value

    if APP_MODE_IS_EXPLICIT:
        return _DB_PROFILE_DEFAULTS[(profile, loc)][key]

    if not _profile_db_config_present():
        legacy = _file_env(key)
        if legacy:
            return legacy

    return _DB_PROFILE_DEFAULTS[(profile, loc)][key]


ACTIVE_DB_PROFILE = active_db_profile()
DATABASE_URL = _resolve_db_value("DATABASE_URL")
DB_HOST = _resolve_db_value("DB_HOST")
DB_PORT = int(_resolve_db_value("DB_PORT") or "5432")
DB_NAME = _resolve_db_value("DB_NAME")
DB_USER = _resolve_db_value("DB_USER")
DB_PASSWORD = _resolve_db_value("DB_PASSWORD")
DB_SSL = _resolve_db_value("DB_SSL").lower() or "auto"

# Эти проверки актуальны только для «раздельной» конфигурации (host/user/pass).
# Когда задан DATABASE_URL (managed-база на хостинге), подключение идёт по строке —
# host/name/password из профиля не используются, поэтому guardrail'ы пропускаем.
if not DATABASE_URL:
    if APP_MODE == "main" and DB_LOCATION == "remote" and not DB_PASSWORD:
        raise RuntimeError(
            "main + remote: задай DB_PASSWORD_MAIN в корневом .env (пароль от cutebase на CuteHost)."
        )
    if APP_MODE == "main" and DB_NAME.lower() != "cutebase":
        raise RuntimeError(
            f"APP_MODE=main: ожидается DB_NAME_MAIN=cutebase, сейчас '{DB_NAME}'."
        )


def db_connection_label() -> str:
    if DATABASE_URL:
        return f"DATABASE_URL ({ACTIVE_DB_PROFILE})"
    return f"{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} ({ACTIVE_DB_PROFILE})"


def app_mode_summary() -> str:
    auth = "dev-auth" if ALLOW_DEV_AUTH else "telegram"
    if DB_LOCATION == "remote":
        where = f"CuteHost remote :{DB_PORT} (SSH)"
    else:
        where = f"local PostgreSQL :{DB_PORT} (no SSH)"
    auth_note = "no password" if APP_MODE == "test" and not DB_PASSWORD else auth
    base = (f"APP_MODE={APP_MODE} | location={DB_LOCATION} | "
            f"DB={DB_NAME} @ {DB_HOST}:{DB_PORT} ({where}) | {auth}")
    if APP_MODE == "test" and not DB_PASSWORD:
        return f"{base} | {auth_note}"
    return base


def validate_database_profile() -> list[str]:
    warnings: list[str] = []
    name = DB_NAME.strip().lower()
    test_names = frozenset({"postgres", "cutefarmer", "template1"})
    if ACTIVE_DB_PROFILE == "main" and name in test_names:
        warnings.append(
            f"Рабочий режим (main), но БД '{DB_NAME}' похожа на тестовую. "
            "Поставь APP_MODE=main и DB_NAME_MAIN=cutebase."
        )
    if ACTIVE_DB_PROFILE == "test" and name in ("postgres", "cutefarmer", "template1"):
        warnings.append(
            f"Тестовый режим, но БД '{DB_NAME}' без таблиц. "
            "Поставь DB_NAME_TEST=cutebase."
        )
    if DB_LOCATION == "local" and DB_PORT == 15432:
        warnings.append(
            "Расположение=local, но порт :15432 (порт SSH-туннеля). Локально обычно :5432."
        )
    if DB_LOCATION == "remote" and DB_HOST not in ("127.0.0.1", "localhost", "::1"):
        warnings.append(
            f"Расположение=remote идёт через SSH-туннель на localhost, сейчас host={DB_HOST}."
        )
    return warnings


def db_ssl_mode():
    if DB_SSL == "true":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if DB_SSL == "false":
        return False
    if DB_HOST in ("localhost", "127.0.0.1", "::1"):
        return False
    return None

# =============================================================================
# ТОКЕНЫ TELEGRAM-БОТОВ (корневой .env — единственный источник)
# =============================================================================
# Не путать между собой — у каждого бота свой токен и своё назначение:
#
#   BOT_TOKEN          — WebApp «ферма» + initData игрового мини-приложения (server/).
#   ADMIN_BOT_TOKEN    — ОТДЕЛЬНЫЙ admin-бот: кнопка панели, initData регистрации/входа.
#                        Проверка подписи WebApp и TOTP НЕ связаны с BOT_TOKEN!
#   SUPPORT_BOT_TOKEN  — бот поддержки (тикеты), если включён.
#
#   bot/config/config.py → TOKEN      — Python-бот main.py (игры, модерация в чатах).
#   bot/config/config.py → EDEN_TOKEN  — платёжный/Eden-бот.
#
# Как менять ADMIN_BOT_TOKEN:
#   1. @BotFather → выбери admin-бота → API Token.
#   2. В корневом .env: ADMIN_BOT_TOKEN=<id>:<secret>
#   3. Перезапусти server (uvicorn) и admin_bot.py (если запущен отдельно).
#   4. Пользователи должны открывать панель именно через admin-бота, не через игрового.
#
# Ожидаемый numeric id admin-бота (первая часть до «:»). Пусто = bot_id из ADMIN_BOT_TOKEN.

BOT_TOKEN = _file_env("BOT_TOKEN")
WEBAPP_URL = _file_env("WEBAPP_URL")
ADMIN_BOT_TOKEN = _file_env("ADMIN_BOT_TOKEN")
_admin_bot_expected_raw = _file_env("ADMIN_BOT_EXPECTED_ID")
ADMIN_BOT_EXPECTED_ID = (
    _admin_bot_expected_raw
    or (ADMIN_BOT_TOKEN.split(":", 1)[0].strip() if ":" in (ADMIN_BOT_TOKEN or "") else "")
    or "8630275843"
)
ADMIN_WEBAPP_URL = _file_env("ADMIN_WEBAPP_URL")
# Токен бота модерации (bot/config/config.py → TOKEN): именно им приняты
# фото-доказательства, поэтому только он (или его свежая версия того же bot_id)
# может их скачать для архива. Берём из канонического файла — устойчиво к смене
# токена (правится в одном месте, сервер подхватывает без правок .env).
MODERATION_BOT_TOKEN = _read_config_py_token()
SUPPORT_BOT_TOKEN = _file_env("SUPPORT_BOT_TOKEN")
SUPPORT_BOT_URL = _file_env("SUPPORT_BOT_URL")  # https://t.me/your_support_bot
ADMIN_LOGIN_KEY = _file_env("ADMIN_LOGIN_KEY")
INTERNAL_API_KEY = _file_env("INTERNAL_API_KEY")
ADMIN_TOTP_SECRET = _file_env("ADMIN_TOTP_SECRET")

# TOTP при регистрации/входе: окно ±N интервалов по 30 сек (8 ≈ ±4 мин на рассинхрон часов).
ADMIN_TOTP_VALID_WINDOW = max(1, int(_file_env("ADMIN_TOTP_VALID_WINDOW", "8")))

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
ADMIN_FRONTEND_ORIGIN = os.getenv("ADMIN_FRONTEND_ORIGIN", "http://localhost:5174")
ADMIN_ENABLED = os.getenv("ADMIN_ENABLED", "true").lower() == "true"
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "").strip()
# Владельцы (я и друг) — получают роль owner/active автоматически.
# Если пусто — владельцами считаются все из ADMIN_USER_IDS.
OWNER_USER_IDS = os.getenv("OWNER_USER_IDS", "").strip()
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "").strip()
ADMIN_SESSION_MINUTES = int(os.getenv("ADMIN_SESSION_MINUTES", "60"))
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
DEFAULT_BALANCE = int(os.getenv("DEFAULT_BALANCE", "100"))

# Онлайн: heartbeat + окно без пинга (сек), если leave не дошёл
ONLINE_WINDOW_SECONDS = int(os.getenv("ONLINE_WINDOW_SECONDS", "30"))
ONLINE_SNAPSHOT_INTERVAL_SECONDS = int(os.getenv("ONLINE_SNAPSHOT_INTERVAL_SECONDS", "60"))
PRESENCE_TOUCH_INTERVAL_SECONDS = int(os.getenv("PRESENCE_TOUCH_INTERVAL_SECONDS", "10"))
ANALYTICS_TZ = os.getenv("ANALYTICS_TZ", "Europe/Moscow")

# Биржа: кэш каталога (сек). 0 = без кэша. Баланс kut всегда свежий.
SHOP_CATALOG_CACHE_SECONDS = int(os.getenv("SHOP_CATALOG_CACHE_SECONDS", "45"))

# Логи покупок и баланса (БД + уведомления в Telegram-группу)
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "false").lower() == "true"
AUDIT_TELEGRAM_CHAT_ID = os.getenv("AUDIT_TELEGRAM_CHAT_ID", "").strip()

def _parse_optional_int(value: str) -> int | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return int(raw)

AUDIT_TELEGRAM_THREAD_ID = _parse_optional_int(os.getenv("AUDIT_TELEGRAM_THREAD_ID", ""))

# Ошибки → отдельная тема в группе
ERROR_REPORT_ENABLED = os.getenv("ERROR_REPORT_ENABLED", "false").lower() == "true"
ERROR_TELEGRAM_CHAT_ID = os.getenv("ERROR_TELEGRAM_CHAT_ID", AUDIT_TELEGRAM_CHAT_ID).strip()
ERROR_TELEGRAM_THREAD_ID = _parse_optional_int(
    os.getenv("ERROR_TELEGRAM_THREAD_ID", "")
)

# Безопасность
INIT_DATA_MAX_AGE = int(os.getenv("INIT_DATA_MAX_AGE", "3600"))  # сек, initData из Telegram
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "80"))  # запросов на user_id в окне

# PostgreSQL connection pool (per uvicorn worker process)
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "3"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Uvicorn workers (production). Keep at 1–2 on a single Droplet without Redis.
UVICORN_WORKERS = int(os.getenv("UVICORN_WORKERS", "2"))

# SSE: max simultaneous notification streams across all users in this process.
NOTIFICATION_SSE_MAX_TOTAL = int(os.getenv("NOTIFICATION_SSE_MAX_TOTAL", "500"))
NOTIFICATION_SSE_MAX_PER_USER = int(os.getenv("NOTIFICATION_SSE_MAX_PER_USER", "2"))

# How long to cache ban status in memory (seconds) to avoid DB hit on every request.
BAN_CHECK_CACHE_SECONDS = int(os.getenv("BAN_CHECK_CACHE_SECONDS", "60"))

# Throttle Telegram profile sync (seconds) — only on presence ping, not every API call.
PROFILE_SYNC_INTERVAL_SECONDS = int(os.getenv("PROFILE_SYNC_INTERVAL_SECONDS", "300"))

# Retention for game_events analytics table (days). Older rows are purged daily.
GAME_EVENTS_RETENTION_DAYS = int(os.getenv("GAME_EVENTS_RETENTION_DAYS", "90"))
GAME_EVENTS_MAX_PENDING = int(os.getenv("GAME_EVENTS_MAX_PENDING", "200"))
GAME_EVENTS_INSERT_CONCURRENCY = int(os.getenv("GAME_EVENTS_INSERT_CONCURRENCY", "12"))

MAX_PLOTS = 8
ADMIN_MAX_PLOTS = 100
PLOT_PRICE_STEP = 15

TREE_GROW_SECONDS = int(os.getenv("TREE_GROW_SECONDS", "1200"))  # 20 минут
TOBACCO_GROW_SECONDS = int(os.getenv("TOBACCO_GROW_SECONDS", "600"))  # 10 минут
WILT_GRACE_SECONDS = 120  # 2 минуты до засухи после «сухой земли»
WATER_INTERVAL_SECONDS = int(os.getenv("WATER_INTERVAL_SECONDS", "300"))  # 5 минут между поливами
CLEAR_COST = 10

# Чёрный рынок — технический чат, куда зачисляется комиссия с биржи
TECH_CHAT_ID = -1003855337972

SEED_ITEM_ID = os.getenv("SEED_ITEM_ID", "299")
TREE_ITEM_ID = os.getenv("TREE_ITEM_ID", "290")
TOBACCO_SEED_ITEM_ID = os.getenv("TOBACCO_SEED_ITEM_ID", "296")
TOBACCO_ITEM_ID = os.getenv("TOBACCO_ITEM_ID", "297")
AXE_ITEM_ID = os.getenv("AXE_ITEM_ID", "295")
WATER_ITEM_ID = os.getenv("WATER_ITEM_ID", "294")
AUTOWATER_ITEM_ID = os.getenv("AUTOWATER_ITEM_ID", "298")
COUPON_ITEM_ID = os.getenv("COUPON_ITEM_ID", "279")  # "Купон на скидку" в dex

# Разброс случайной скидки при использовании купона в магазине.
COUPON_DISCOUNT_MIN_PERCENT = int(os.getenv("COUPON_DISCOUNT_MIN_PERCENT", "20"))
COUPON_DISCOUNT_MAX_PERCENT = int(os.getenv("COUPON_DISCOUNT_MAX_PERCENT", "80"))
# Ключи в users.items — id из таблицы dex
SEED_ITEM_KEY = SEED_ITEM_ID
TREE_ITEM_KEY = TREE_ITEM_ID
TOBACCO_SEED_ITEM_KEY = TOBACCO_SEED_ITEM_ID
TOBACCO_ITEM_KEY = TOBACCO_ITEM_ID
AXE_ITEM_KEY = AXE_ITEM_ID
WATER_ITEM_KEY = WATER_ITEM_ID
AUTOWATER_ITEM_KEY = AUTOWATER_ITEM_ID
WATER_COST_PER_USE = 1
SEED_ITEM_KEYS = (SEED_ITEM_ID, "sajeneztree", "901284129481212412")
TOBACCO_SEED_ITEM_KEYS = (TOBACCO_SEED_ITEM_ID, "sajeneztabachok", "124124121424124115")
LOG_ITEM_KEYS = (TREE_ITEM_ID, "justtree", "124125898126")
AXE_ITEM_KEYS = (AXE_ITEM_ID, "124124121424124114")
WATER_ITEM_KEYS = (WATER_ITEM_ID, "124124121424124113")
AUTOWATER_ITEM_KEYS = (AUTOWATER_ITEM_ID, "124124121424124117")
TOBACCO_ITEM_KEYS = (TOBACCO_ITEM_ID, "124124121424124116")
AXE_WEAR_PER_TREE_HARVEST = 5
AXE_MAX_DURABILITY = 100


def _origin_from_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url.rstrip("/")


def _parse_id_csv(value: str) -> frozenset[int]:
    if not value:
        return frozenset()
    result: set[int] = set()
    for part in value.split(","):
        raw = part.strip()
        if raw:
            result.add(int(raw))
    return frozenset(result)


def admin_user_ids() -> frozenset[int]:
    return _parse_id_csv(ADMIN_USER_IDS)


def owner_user_ids() -> frozenset[int]:
    """Владельцы панели. Если OWNER_USER_IDS не задан все из ADMIN_USER_IDS."""
    owners = _parse_id_csv(OWNER_USER_IDS)
    return owners or admin_user_ids()


def cors_origins() -> list[str]:
    origins = {
        FRONTEND_ORIGIN,
        ADMIN_FRONTEND_ORIGIN,
    }
    if not PRODUCTION:
        origins.update({
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        })
    if WEBAPP_URL:
        origins.add(_origin_from_url(WEBAPP_URL))
    if ADMIN_WEBAPP_URL:
        origins.add(_origin_from_url(ADMIN_WEBAPP_URL))
    return list(origins)


_WEAK_ADMIN_KEYS = frozenset({"cute", "gaming", "admin", "password", "123456"})


def assert_security_startup() -> None:
    """Блокирует запуск на проде при критичных misconfig."""
    if not PRODUCTION:
        return

    fatal: list[str] = []
    if ALLOW_DEV_AUTH:
        fatal.append("PRODUCTION=true при ALLOW_DEV_AUTH=true")
    if not BOT_TOKEN:
        fatal.append("PRODUCTION без BOT_TOKEN")
    if ADMIN_ENABLED:
        if not admin_user_ids():
            fatal.append("ADMIN_ENABLED без ADMIN_USER_IDS")
        if not ADMIN_BOT_TOKEN:
            fatal.append("ADMIN_ENABLED без ADMIN_BOT_TOKEN")
        if not ADMIN_JWT_SECRET or len(ADMIN_JWT_SECRET) < 32:
            fatal.append("ADMIN_JWT_SECRET: нужен случайный секрет ≥32 символов")
        if not ADMIN_LOGIN_KEY or ADMIN_LOGIN_KEY.lower() in _WEAK_ADMIN_KEYS:
            fatal.append("ADMIN_LOGIN_KEY: задайте длинный случайный ключ")
    if FRONTEND_ORIGIN.startswith("http://localhost"):
        fatal.append("FRONTEND_ORIGIN указывает на localhost на проде")
    if ACTIVE_DB_PROFILE == "main" and DB_NAME.strip().lower() in ("postgres", "cutefarmer", "template1"):
        fatal.append(
            f"PRODUCTION/main подключён к тестовой БД '{DB_NAME}'. "
            "Задай DB_NAME_MAIN=cutebase."
        )

    if fatal:
        raise RuntimeError(
            "Критичные проблемы безопасности:\n" + "\n".join(f" - {x}" for x in fatal)
        )


def token_bot_id(token: str) -> str:
    """Numeric id бота — часть до «:» в токене BotFather."""
    raw = (token or "").strip()
    if ":" not in raw:
        return ""
    return raw.split(":", 1)[0].strip()


def token_fingerprint(token: str) -> str:
    """Маскированный отпечаток для логов: 8630275843:****hKIV8."""
    raw = (token or "").strip()
    if not raw:
        return "(пусто)"
    if ":" not in raw:
        return raw[:6] + "****"
    bot_id, secret = raw.split(":", 1)
    secret = secret.strip()
    if len(secret) <= 8:
        return f"{bot_id}:****"
    return f"{bot_id}:****{secret[-4:]}"


def _read_bot_config_py_tokens() -> dict[str, str]:
    """TOKEN и EDEN_TOKEN из bot/config/config.py (без импорта пакета bot)."""
    result: dict[str, str] = {}
    try:
        raw = _CONFIG_PY_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return result
    import re
    for var in ("TOKEN", "EDEN_TOKEN"):
        m = re.search(rf'^\s*{var}\s*=\s*["\']([^"\']+)["\']', raw, re.MULTILINE)
        if m:
            result[var] = m.group(1).strip()
    return result


def describe_bot_tokens() -> list[dict[str, str]]:
    """Справочник всех токенов: откуда читается, за что отвечает, текущий отпечаток."""
    cfg = _read_bot_config_py_tokens()
    entries = [
        {
            "key": "BOT_TOKEN",
            "source": "корневой .env",
            "role": "WebApp фермы, initData игрового мини-приложения, audit/error в Telegram",
            "fingerprint": token_fingerprint(BOT_TOKEN),
            "bot_id": token_bot_id(BOT_TOKEN) or "—",
        },
        {
            "key": "ADMIN_BOT_TOKEN",
            "source": "корневой .env",
            "role": "Admin-панель: кнопка Web App, подпись initData, регистрация TOTP",
            "fingerprint": token_fingerprint(ADMIN_BOT_TOKEN),
            "bot_id": token_bot_id(ADMIN_BOT_TOKEN) or "—",
        },
        {
            "key": "SUPPORT_BOT_TOKEN",
            "source": "корневой .env",
            "role": "Бот поддержки (тикеты), если модуль support включён",
            "fingerprint": token_fingerprint(SUPPORT_BOT_TOKEN),
            "bot_id": token_bot_id(SUPPORT_BOT_TOKEN) or "—",
        },
        {
            "key": "TOKEN",
            "source": "bot/config/config.py",
            "role": "Python-бот main.py: игры, модерация, команды в чатах (CuteTest)",
            "fingerprint": token_fingerprint(cfg.get("TOKEN", "")),
            "bot_id": token_bot_id(cfg.get("TOKEN", "")) or "—",
        },
        {
            "key": "EDEN_TOKEN",
            "source": "bot/config/config.py",
            "role": "Платёжный Eden-бот (отдельный процесс)",
            "fingerprint": token_fingerprint(cfg.get("EDEN_TOKEN", "")),
            "bot_id": token_bot_id(cfg.get("EDEN_TOKEN", "")) or "—",
        },
    ]
    return entries


def validate_bot_tokens() -> list[str]:
    """Предупреждения по токенам ботов (не блокирует запуск)."""
    warnings: list[str] = []
    if not ADMIN_BOT_TOKEN and ADMIN_ENABLED:
        warnings.append("ADMIN_BOT_TOKEN пуст — регистрация в панель через Telegram невозможна.")
    if ADMIN_BOT_TOKEN and ADMIN_BOT_EXPECTED_ID:
        actual = token_bot_id(ADMIN_BOT_TOKEN)
        if actual and actual != ADMIN_BOT_EXPECTED_ID:
            warnings.append(
                f"ADMIN_BOT_TOKEN bot_id={actual}, в .env ADMIN_BOT_EXPECTED_ID={ADMIN_BOT_EXPECTED_ID}. "
                f"Поставьте ADMIN_BOT_EXPECTED_ID={actual} или верните правильный ADMIN_BOT_TOKEN, "
                "затем перезапустите API и farm bots. Иначе вход в панель даст 401/500."
            )
    if BOT_TOKEN and ADMIN_BOT_TOKEN and BOT_TOKEN == ADMIN_BOT_TOKEN:
        warnings.append("BOT_TOKEN и ADMIN_BOT_TOKEN совпадают — admin-панель и ферма должны быть разными ботами.")
    cfg = _read_bot_config_py_tokens()
    game_token = cfg.get("TOKEN", "")
    if game_token and ADMIN_BOT_TOKEN and token_bot_id(game_token) == token_bot_id(ADMIN_BOT_TOKEN):
        warnings.append(
            "TOKEN (main.py) и ADMIN_BOT_TOKEN указывают на одного бота — "
            "регистрацию открывай только через admin-бота из ADMIN_BOT_TOKEN."
        )
    return warnings


async def verify_bot_token_telegram(token: str) -> dict | None:
    """getMe через Telegram API. None если токен пуст; dict с ok/username/id или error."""
    import asyncio
    import json
    from urllib.request import Request, urlopen

    raw = (token or "").strip()
    if not raw:
        return None
    url = f"https://api.telegram.org/bot{raw}/getMe"

    def _fetch() -> dict:
        req = Request(url, headers={"User-Agent": "CuteFarm/1.0"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    try:
        data = await asyncio.to_thread(_fetch)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not data.get("ok"):
        return {"ok": False, "error": data.get("description", "getMe failed")}
    r = data.get("result") or {}
    return {"ok": True, "id": r.get("id"), "username": r.get("username"), "first_name": r.get("first_name")}


async def log_bot_tokens_startup(logger) -> None:
    """При старте API: отпечатки токенов + getMe для ADMIN/BOT (без полных секретов)."""
    logger.info("--- Токены Telegram-ботов (см. server/config.py) ---")
    for entry in describe_bot_tokens():
        logger.info(
            "  %s [%s] id=%s fp=%s — %s",
            entry["key"],
            entry["source"],
            entry["bot_id"],
            entry["fingerprint"],
            entry["role"],
        )
    for label, token in (
        ("ADMIN_BOT_TOKEN", ADMIN_BOT_TOKEN),
        ("BOT_TOKEN", BOT_TOKEN),
    ):
        if not token:
            logger.info("  getMe %s: пропуск (токен пуст)", label)
            continue
        try:
            info = await verify_bot_token_telegram(token)
        except Exception as exc:
            logger.warning("  getMe %s: ошибка проверки — %s", label, exc)
            continue
        if info and info.get("ok"):
            logger.info(
                "  getMe %s: OK @%s (id=%s)",
                label,
                info.get("username") or "?",
                info.get("id"),
            )
        else:
            err = (info or {}).get("error", "unknown")
            logger.warning("  getMe %s: ОШИБКА — %s (fp=%s)", label, err, token_fingerprint(token))
    for w in validate_bot_tokens():
        logger.warning("  BOT TOKEN: %s", w)
    logger.info("--- конец блока токенов ---")


def validate_security_settings() -> list[str]:
    """Предупреждения при старте (не блокирует запуск)."""
    warnings: list[str] = []
    if PRODUCTION and ALLOW_DEV_AUTH:
        warnings.append("PRODUCTION=true, но ALLOW_DEV_AUTH=true отключите dev-режим на проде!")
    if PRODUCTION and not BOT_TOKEN:
        warnings.append("PRODUCTION без BOT_TOKEN — Web App не будет безопасен.")
    if PRODUCTION and FRONTEND_ORIGIN.startswith("http://localhost"):
        warnings.append("PRODUCTION с localhost FRONTEND_ORIGIN укажите реальный домен фронта.")
    if ALLOW_DEV_AUTH and WEBAPP_URL.startswith("https://"):
        warnings.append("ALLOW_DEV_AUTH=true при HTTPS WEBAPP_URL риск подделки user_id.")
    if not PRODUCTION and not ALLOW_DEV_AUTH and not BOT_TOKEN:
        warnings.append("Локальная разработка: задайте ALLOW_DEV_AUTH=true или BOT_TOKEN.")
    if AUDIT_LOG_ENABLED and not AUDIT_TELEGRAM_CHAT_ID:
        warnings.append("AUDIT_LOG_ENABLED=true, но AUDIT_TELEGRAM_CHAT_ID пуст уведомления в Telegram отключены.")
    if AUDIT_LOG_ENABLED and not BOT_TOKEN:
        warnings.append("AUDIT_LOG_ENABLED=true, но BOT_TOKEN пуст уведомления в Telegram отключены.")
    if ERROR_REPORT_ENABLED and not ERROR_TELEGRAM_CHAT_ID:
        warnings.append("ERROR_REPORT_ENABLED=true, но ERROR_TELEGRAM_CHAT_ID пуст тема ошибок отключена.")
    if ERROR_REPORT_ENABLED and not BOT_TOKEN:
        warnings.append("ERROR_REPORT_ENABLED=true, но BOT_TOKEN пуст тема ошибок отключена.")
    if ADMIN_ENABLED and not ADMIN_USER_IDS:
        warnings.append("ADMIN_ENABLED=true, но ADMIN_USER_IDS пуст вход в админку закрыт.")
    if ADMIN_ENABLED and not ADMIN_BOT_TOKEN:
        warnings.append("ADMIN_ENABLED=true, но ADMIN_BOT_TOKEN пуст admin-бот не запустится.")
    if ADMIN_ENABLED and not ADMIN_WEBAPP_URL:
        warnings.append("ADMIN_ENABLED=true, но ADMIN_WEBAPP_URL пуст кнопка Web App в admin-боте не появится.")
    if ADMIN_ENABLED and not ADMIN_LOGIN_KEY:
        warnings.append("ADMIN_LOGIN_KEY пуст вход в админку недоступен.")
    if ADMIN_ENABLED and PRODUCTION and not ADMIN_JWT_SECRET:
        warnings.append("ADMIN_ENABLED на проде без ADMIN_JWT_SECRET задайте длинный случайный секрет.")
    warnings.extend(validate_database_profile())
    warnings.extend(validate_bot_tokens())
    return warnings
