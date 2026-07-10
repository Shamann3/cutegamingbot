"""Быстрая проверка подключения к PostgreSQL. Запуск: python scripts/test_db_connection.py

Тест подключается к БД напрямую через asyncpg и НЕ импортирует игровой слой
(bot.db_create.db / pklcode), чтобы не тратить время на биндинг Redis.
Профиль/расположение БД берётся из ЕДИНОГО источника (bot.config.db_config),
т.е. из config.py -> DATABASE_MODE/DATABASE_LOCATION (с запасом на .env).

Отличия от простого connect():
  • если сервер требует/запрещает SSL, пробуем несколько режимов SSL
    (configured -> prefer -> disable), а не падаем на первом же;
  • при ошибке печатаем ПОНЯТНЫЙ диагноз и что именно сделать
    (start-0-postgres-cutebase.bat / set-mode.bat main / правка .env).
"""

import asyncio
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg

from bot.config.db_config import (
    ACTIVE_DB_PROFILE,
    DB_HOST,
    DB_LOCATION,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    bootstrap_database_env,
    build_db_settings,
    db_connect_target,
    db_connected_line,
    db_debug_log,
)


def _ssl_variants(base):
    """Упорядоченный список (label, value) попыток SSL.

    Сначала — режим из конфигурации, затем разумные запасные, чтобы сервер,
    который ТРЕБУЕТ SSL (или наоборот его не поддерживает), всё равно подключился,
    а не обрывал рукопожатие."""
    variants = []
    seen = set()

    def push(label, value):
        if label in seen:
            return
        seen.add(label)
        variants.append((label, value))

    if base is False:
        push("disable", False)
        push("prefer", "prefer")
    elif base is None:
        push("prefer", "prefer")
        push("disable", False)
    elif isinstance(base, str):
        push(base, base)
        push("prefer", "prefer")
        push("disable", False)
    else:  # ssl.SSLContext (DB_SSL=true)
        push("require", base)
        push("prefer", "prefer")
        push("disable", False)
    return variants


async def _try_connect(ssl_value):
    return await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
        ssl=ssl_value,
        timeout=10,
    )


def _print_diagnosis(exc) -> None:
    where = "СЕРВЕР CuteHost (SSH :15432)" if DB_LOCATION == "remote" else "локальный PostgreSQL (:5432)"
    name = type(exc).__name__
    msg = str(exc).lower()
    print("")
    print(f"   [диагностика] цель: {ACTIVE_DB_PROFILE}/{DB_NAME}@{DB_HOST}:{DB_PORT} ({where})")

    if isinstance(exc, asyncpg.InvalidPasswordError) or "password authentication failed" in msg:
        print(f"   Причина: НЕВЕРНЫЙ ПАРОЛЬ для пользователя '{DB_USER}'.")
        if DB_LOCATION == "remote":
            print("   -> Проверь DB_PASSWORD_MAIN (и SSH_PASSWORD) в корневом .env.")
        else:
            print(f"   -> Проверь DB_PASSWORD_{ACTIVE_DB_PROFILE.upper()} в корневом .env "
                  "(пароль локального PostgreSQL).")
        return

    if isinstance(exc, asyncpg.InvalidCatalogNameError) or ("does not exist" in msg and "database" in msg):
        print(f"   Причина: базы '{DB_NAME}' нет на этом сервере.")
        print(f'   -> Создай её:  psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -c "CREATE DATABASE {DB_NAME};"')
        if DB_LOCATION == "local":
            print("   -> Проще: запусти start-0-postgres-cutebase.bat (создаст/проверит cutebase).")
        return

    if isinstance(exc, ConnectionRefusedError) or "refused" in msg or "1225" in msg:
        print(f"   Причина: на {DB_HOST}:{DB_PORT} НИКТО не слушает (PostgreSQL/туннель не запущен).")
        if DB_LOCATION == "remote":
            print("   -> Подними SSH-туннель (start_all.bat делает это сам) или проверь SSH_* в .env.")
        else:
            print("   -> Запусти локальный PostgreSQL:  start-0-postgres-cutebase.bat")
            print("   -> Либо переключись на серверную БД:  set-mode.bat main")
        return

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in msg:
        print(f"   Причина: таймаут подключения к {DB_HOST}:{DB_PORT}.")
        if DB_LOCATION == "remote":
            print("   -> Туннель есть, но БД не отвечает — проверь сервер CuteHost.")
        else:
            print("   -> Локальный PostgreSQL завис/стартует — проверь службу postgresql.")
        return

    if isinstance(exc, asyncpg.ConnectionDoesNotExistError) or "closed in the middle" in msg:
        print(f"   Причина: сервер оборвал соединение на рукопожатии.")
        print(f"            Порт {DB_PORT} занят, но это НЕ рабочий PostgreSQL, либо нужен другой SSL,")
        print("            либо там висит чужой/сломанный сервис.")
        print("   (уже пробовали ssl=disable и ssl=prefer — не помогло)")
        if DB_LOCATION == "local":
            print("   Частые причины на :5432 — старый SSH-туннель, Docker-Postgres на другую базу,")
            print("   недозапущенный PostgreSQL 17. Что делать:")
            print("     1) освободи :5432 и запусти start-0-postgres-cutebase.bat, ИЛИ")
            print("     2) переключись на серверную БД:  set-mode.bat main")
        else:
            print("   -> Проверь, что туннель :15432 ведёт на реальный PostgreSQL сервера CuteHost.")
        return

    print(f"   Причина не распознана ({name}). Полный лог: logs\\db-test.log")
    print("   Быстрый обходной путь — серверная БД:  set-mode.bat main")


async def main() -> int:
    bootstrap_database_env()
    db_debug_log(f"[test_db] target={db_connect_target()}")

    settings = build_db_settings()
    variants = _ssl_variants(settings["ssl"])

    # Эти ошибки SSL-переключением не лечатся — сразу диагностируем.
    hard_stop = (
        asyncpg.InvalidPasswordError,
        asyncpg.InvalidAuthorizationSpecificationError,
        asyncpg.InvalidCatalogNameError,
        ConnectionRefusedError,
        asyncio.TimeoutError,
        TimeoutError,
        socket.gaierror,
    )

    conn = None
    used_label = None
    last_exc = None
    for label, value in variants:
        try:
            conn = await _try_connect(value)
            used_label = label
            break
        except hard_stop as exc:
            last_exc = exc
            break
        except OSError as exc:
            # "actively refused" и т.п. — сеть, SSL не поможет.
            last_exc = exc
            if "refused" in str(exc).lower() or "1225" in str(exc):
                break
            db_debug_log(f"[test_db] ssl='{label}': {type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            # ConnectionDoesNotExistError, ssl-ошибки и пр. — пробуем следующий SSL.
            last_exc = exc
            db_debug_log(f"[test_db] ssl='{label}' не подошёл: {type(exc).__name__}: {exc}")
            continue

    if conn is None:
        print(f"[test_db] FAIL - {type(last_exc).__name__}: {last_exc}")
        _print_diagnosis(last_exc)
        return 1

    try:
        current_db = await conn.fetchval("SELECT current_database()")
        db_debug_log(db_connected_line(current_db))

        if settings["ssl"] is False and used_label != "disable":
            print(f"[test_db] ВНИМАНИЕ: подключение удалось только с ssl='{used_label}'.")
            print(f"          Бот/сервер берут SSL из .env — поставь "
                  f"DB_SSL_{ACTIVE_DB_PROFILE.upper()}=true в корневом .env,")
            print("          иначе бот и WebApp-сервер не подключатся к этой базе.")

        users = 0
        has_users = await conn.fetchval(
            "SELECT EXISTS("
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='users')"
        )
        if has_users:
            users = await conn.fetchval("SELECT COUNT(*)::int FROM users") or 0
        print(f"[test_db] OK - {current_db} users={users} (ssl={used_label})")
        return 0
    except Exception as e:
        print(f"[test_db] FAIL - {type(e).__name__}: {e}")
        return 1
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
