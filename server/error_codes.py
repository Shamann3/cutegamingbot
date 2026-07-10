"""Коды ошибок Cute Farming — для логов в Telegram и отчётов с клиента."""

from __future__ import annotations

ERROR_CATALOG: dict[str, dict[str, str]] = {
    # --- Авторизация ---
    "ERR_AUTH_401": {
        "title": "Нет авторизации",
        "meaning": "Пользователь не передал Telegram initData или сессия истекла.",
    },
    "ERR_AUTH_403": {
        "title": "Доступ запрещён",
        "meaning": "Dev-режим с не-localhost или запрос с чужого домена.",
    },
    "ERR_AUTH_HASH": {
        "title": "Неверная подпись Telegram",
        "meaning": "initData подделан или BOT_TOKEN не совпадает с ботом Mini App.",
    },
    "ERR_AUTH_NO_BOT": {
        "title": "BOT_TOKEN не настроен",
        "meaning": "На сервере пустой BOT_TOKEN — авторизация невозможна.",
    },
    "ERR_AUTH_NO_USER": {
        "title": "Нет user в initData",
        "meaning": "Telegram не передал объект пользователя в initData.",
    },
    "ERR_AUTH_EXPIRED": {
        "title": "Сессия истекла",
        "meaning": "auth_date в initData старше INIT_DATA_MAX_AGE.",
    },
    # --- Сеть (клиент) ---
    "ERR_NET_TIMEOUT": {
        "title": "Таймаут API",
        "meaning": "Сервер не ответил за отведённое время (выключен или перегружен).",
    },
    "ERR_NET_OFFLINE": {
        "title": "Нет связи с API",
        "meaning": "fetch не дошёл до сервера: нет сети, неверный VITE_API_URL, ngrok упал.",
    },
    "ERR_NET_ABORT": {
        "title": "Запрос прерван",
        "meaning": "Клиент отменил запрос или оборвалось соединение.",
    },
    # --- API HTTP ---
    "ERR_API_400": {
        "title": "Некорректный запрос",
        "meaning": "Ошибка валидации или бизнес-правило (мало КУТ, нет семечка и т.д.).",
    },
    "ERR_API_422": {
        "title": "Неверное тело запроса",
        "meaning": "Pydantic не принял JSON: лишние поля, неверные типы.",
    },
    "ERR_API_429": {
        "title": "Слишком много запросов",
        "meaning": "Игрок превысил RATE_LIMIT_MAX за минуту.",
    },
    "ERR_API_500": {
        "title": "Внутренняя ошибка сервера",
        "meaning": "Необработанное исключение на бэкенде. Смотрите логи uvicorn.",
    },
    "ERR_API_503": {
        "title": "Технические работы",
        "meaning": "Включён MAINTENANCE_MODE или сервис недоступен.",
    },
    "ERR_API_UNKNOWN": {
        "title": "Неизвестный ответ API",
        "meaning": "Статус или формат ответа не распознан клиентом.",
    },
    # --- Ферма ---
    "ERR_FARM_STATE": {
        "title": "Не загрузилась ферма",
        "meaning": "GET /api/farm/state завершился ошибкой.",
    },
    "ERR_FARM_PLANT": {
        "title": "Ошибка посадки",
        "meaning": "Нет семечка, грядка занята или неверный plotId.",
    },
    "ERR_FARM_WATER": {
        "title": "Ошибка полива",
        "meaning": "Полив невозможен в текущем состоянии грядки.",
    },
    "ERR_FARM_HARVEST": {
        "title": "Ошибка сбора урожая",
        "meaning": "Урожай не готов или грядка в неверном статусе.",
    },
    "ERR_FARM_CLEAR": {
        "title": "Ошибка очистки грядки",
        "meaning": "Растение не засохло или не хватает КУТ на очистку.",
    },
    "ERR_FARM_BUY_PLOT": {
        "title": "Ошибка покупки грядки",
        "meaning": "Максимум грядок или недостаточно КУТ.",
    },
    "ERR_FARM_POLL": {
        "title": "Фоновый опрос фермы",
        "meaning": "Тихий poll фермы упал — UI может отставать от сервера.",
    },
    # --- Биржа ---
    "ERR_SHOP_CATALOG": {
        "title": "Не загрузился каталог",
        "meaning": "GET /api/shop/catalog завершился ошибкой.",
    },
    "ERR_SHOP_BUY": {
        "title": "Ошибка покупки",
        "meaning": "POST /api/shop/buy не прошёл (баланс, остаток, предмет).",
    },
    "ERR_SHOP_STOCK": {
        "title": "Товар закончился",
        "meaning": "remains в dex = 0 в момент покупки.",
    },
    "ERR_SHOP_BALANCE": {
        "title": "Недостаточно КУТ",
        "meaning": "Баланс меньше стоимости покупки.",
    },
    "ERR_SHOP_POLL": {
        "title": "Фоновый опрос биржи",
        "meaning": "Тихий poll биржи упал.",
    },
    # --- База данных ---
    "ERR_DB_CONNECT": {
        "title": "Нет подключения к PostgreSQL",
        "meaning": "Неверные DB_* креды, Postgres выключен или сеть.",
    },
    "ERR_DB_QUERY": {
        "title": "Ошибка SQL-запроса",
        "meaning": "Запрос к БД упал (схема, синтаксис, таймаут).",
    },
    "ERR_DB_TX": {
        "title": "Ошибка транзакции",
        "meaning": "Транзакция откатилась (deadlock, constraint, race).",
    },
    # --- Интерфейс ---
    "ERR_UI_CRASH": {
        "title": "Падение React",
        "meaning": "ErrorBoundary поймал необработанную ошибку в UI.",
    },
    "ERR_UI_STATUS": {
        "title": "Статус приложения",
        "meaning": "Не удалось получить /api/status при старте.",
    },
    # --- Безопасность / попытки взлома ---
    "ERR_SEC_HASH_FAIL": {
        "title": "Подделка initData",
        "meaning": "HMAC-подпись Telegram не совпала — возможная подделка сессии.",
    },
    "ERR_SEC_FAKE_INIT": {
        "title": "Фейковый initData",
        "meaning": "initData без hash, без user или с битым JSON.",
    },
    "ERR_SEC_EXPIRED_REPLAY": {
        "title": "Просроченный initData",
        "meaning": "Старый initData — replay или пользователь не перезашёл в Mini App.",
    },
    "ERR_SEC_NO_AUTH": {
        "title": "Запрос без авторизации",
        "meaning": "API вызван без Telegram initData и без разрешённого dev-режима.",
    },
    "ERR_SEC_PROD_BYPASS": {
        "title": "Обход prod-авторизации",
        "meaning": "На проде прислали X-Dev-User-Id — попытка выдать себя за другого.",
    },
    "ERR_SEC_DEV_SPOOF": {
        "title": "Dev-auth с чужого IP",
        "meaning": "X-Dev-User-Id не с localhost — попытка подменить user_id.",
    },
    "ERR_SEC_DEV_INVALID": {
        "title": "Неверный dev user id",
        "meaning": "X-Dev-User-Id не число или <= 0.",
    },
    "ERR_SEC_BODY_UID": {
        "title": "user_id в теле запроса",
        "meaning": "Попытка передать user_id/userId в JSON вместо Telegram initData.",
    },
    "ERR_SEC_BODY_BALANCE": {
        "title": "Подмена баланса в теле",
        "meaning": "В JSON передали balance/kut/amount — заблокировано.",
    },
    "ERR_SEC_EXTRA_FIELDS": {
        "title": "Лишние поля в запросе",
        "meaning": "Клиент прислал запрещённые поля (extra=forbid).",
    },
    "ERR_SEC_RATE_ABUSE": {
        "title": "Флуд запросами",
        "meaning": "Превышен rate limit — возможен бот или скрипт.",
    },
    "ERR_SEC_SCAN_PATH": {
        "title": "Сканирование путей",
        "meaning": "Запрос к /admin, /.env, /wp-admin и подобным — типичный сканер.",
    },
    "ERR_SEC_SQL_PROBE": {
        "title": "SQL-инъекция в URL",
        "meaning": "В query-параметрах найдены подозрительные SQL-паттерны.",
    },
    "ERR_SEC_SCANNER": {
        "title": "Подозрительный User-Agent",
        "meaning": "Запрос к API с UA сканера (sqlmap, curl, bot и т.д.).",
    },
    "ERR_SEC_INVALID_ITEM": {
        "title": "Подмена itemId",
        "meaning": "Нечисловой или пустой itemId при покупке.",
    },
    "ERR_SEC_REPORT_FLOOD": {
        "title": "Флуд report-error",
        "meaning": "Слишком много клиентских отчётов об ошибках от одного игрока.",
    },
    # --- Система ---
    "ERR_AUDIT_TG": {
        "title": "Audit Telegram",
        "meaning": "Не удалось отправить лог покупки в тему логов.",
    },
    "ERR_ERR_TG": {
        "title": "Error Telegram",
        "meaning": "Не удалось отправить отчёт об ошибке в тему ошибок.",
    },
    "ERR_CFG_STARTUP": {
        "title": "Предупреждение при старте",
        "meaning": "validate_security_settings нашёл риск в конфигурации.",
    },
    "ERR_UNK": {
        "title": "Неизвестная ошибка",
        "meaning": "Код не распознан — смотрите message и path в сообщении.",
    },
}


def resolve_error_code(code: str | None) -> str:
    raw = (code or "").strip().upper()
    if raw in ERROR_CATALOG:
        return raw
    return "ERR_UNK"


def error_title(code: str) -> str:
    entry = ERROR_CATALOG.get(resolve_error_code(code), ERROR_CATALOG["ERR_UNK"])
    return entry["title"]


def error_meaning(code: str) -> str:
    entry = ERROR_CATALOG.get(resolve_error_code(code), ERROR_CATALOG["ERR_UNK"])
    return entry["meaning"]


def code_from_http_status(status: int, detail: str = "") -> str:
    if status == 400:
        return "ERR_API_400"
    if status == 401:
        if "Сессия истекла" in detail:
            return "ERR_AUTH_EXPIRED"
        if "подпись" in detail.lower() or "авторизация" in detail.lower():
            return "ERR_AUTH_HASH"
        return "ERR_AUTH_401"
    if status == 403:
        return "ERR_AUTH_403"
    if status == 422:
        return "ERR_API_422"
    if status == 429:
        return "ERR_API_429"
    if status == 500:
        if "не настроен" in detail.lower():
            return "ERR_AUTH_NO_BOT"
        return "ERR_API_500"
    if status == 503:
        return "ERR_API_503"
    return "ERR_API_UNKNOWN"


SECURITY_CODES = frozenset(
    code for code in ERROR_CATALOG if code.startswith("ERR_SEC_")
)


def is_security_code(code: str) -> bool:
    return resolve_error_code(code) in SECURITY_CODES


def code_from_api_path(path: str, status: int) -> str:
    base = code_from_http_status(status)
    if "/farm/state" in path:
        return "ERR_FARM_STATE"
    if "/farm/plant" in path:
        return "ERR_FARM_PLANT"
    if "/farm/water" in path:
        return "ERR_FARM_WATER"
    if "/farm/harvest" in path:
        return "ERR_FARM_HARVEST"
    if "/farm/clear" in path:
        return "ERR_FARM_CLEAR"
    if "/farm/buy-plot" in path:
        return "ERR_FARM_BUY_PLOT"
    if "/shop/catalog" in path:
        return "ERR_SHOP_CATALOG"
    if "/shop/buy" in path and status == 400 and "предмет" in detail.lower():
        return "ERR_SEC_INVALID_ITEM"
    if "/shop/buy" in path:
        return "ERR_SHOP_BUY"
    return base
