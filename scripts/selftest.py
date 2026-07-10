"""Быстрый self-test всей системы. Запуск:

    python scripts/selftest.py              # проверить активный профиль (из .env APP_MODE)
    python scripts/selftest.py --api        # + проверить живой API/WebApp (если запущены)
    python scripts/selftest.py --deep        # + прогнать реальный слой server/db.py

Что проверяет:
  1. Какой профиль БД выбран (APP_MODE) и куда он указывает — для test И main.
  2. Живое подключение к активной БД (asyncpg напрямую, без тяжёлого игрового слоя).
     Печатает: имя реальной БД (current_database), число users, задержку в мс.
  3. Ключевые таблицы отвечают на запрос (COUNT по каждой).
  4. (--api) /health API и WebApp Vite.
  5. (--deep) реальный server/db.Database.connect() + пара read-методов.

В конце — таблица PASS/FAIL. Код выхода 0 = всё ок, 1 = есть падения.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from bot.config import db_config as dbc  # noqa: E402

# Таблицы, которые должны отвечать на запрос (ядро всех проектов).
CORE_TABLES = (
    "users",
    "farm_plots",
    "farm_crops",
    "quests",
    "craft_recipes",
    "application_questions",
)


class Report:
    """Собирает результаты и печатает финальную таблицу PASS/FAIL."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"  ->  {detail}" if detail else ""))

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.rows)

    def summary(self) -> None:
        passed = sum(1 for _, ok, _ in self.rows if ok)
        total = len(self.rows)
        print("\n" + "=" * 60)
        print(f"  SELF-TEST: {passed}/{total} passed")
        for name, ok, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            line = f"    {mark:4} | {name}"
            if detail:
                line += f" | {detail}"
            print(line)
        print("=" * 60)
        print("  RESULT:", "ALL OK" if self.ok else "SOME CHECKS FAILED")


def _profile_target(profile: str) -> str:
    """Куда указывает профиль test/main по .env (без подключения)."""
    p = profile.upper()

    def val(key: str, default: str) -> str:
        return dbc._file_env(f"{key}_{p}") or default

    host = val("DB_HOST", "127.0.0.1")
    port = val("DB_PORT", "5432" if profile == "test" else "15432")
    name = val("DB_NAME", "cutebase")
    user = val("DB_USER", "postgres")
    return f"{user}@{host}:{port}/{name}"


def print_config_banner() -> None:
    print("=" * 60)
    print("  DATABASE CONFIG (switch via APP_MODE in .env)")
    print("=" * 60)
    active = dbc.ACTIVE_DB_PROFILE
    for profile in ("test", "main"):
        marker = "  <== ACTIVE" if profile == active else ""
        print(f"  {profile:4} : {_profile_target(profile)}{marker}")
    print(f"\n  {dbc.app_mode_summary()}")
    print(f"  MAIN_DB_TARGET={dbc.MAIN_DB_TARGET}")
    for warn in dbc.validate_database_profile():
        print(f"  [WARN] {warn}")
    print()


async def check_live_db(report: Report) -> None:
    print("-- Live DB connection (active profile) --")
    settings = dbc.build_db_settings()
    t0 = time.perf_counter()
    try:
        conn = await asyncpg.connect(
            user=settings["user"],
            password=settings["password"],
            database=settings["database"],
            host=settings["host"],
            port=settings["port"],
            ssl=settings["ssl"],
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        report.add("db.connect", False, f"{type(exc).__name__}: {exc}")
        return

    connect_ms = (time.perf_counter() - t0) * 1000
    try:
        current_db = await conn.fetchval("SELECT current_database()")
        report.add(
            "db.connect",
            True,
            f"{current_db} @ {settings['host']}:{settings['port']} ({connect_ms:.0f} ms)",
        )

        # Задержка простого запроса (SELECT 1) — метрика "молниеносности".
        t1 = time.perf_counter()
        await conn.fetchval("SELECT 1")
        ping_ms = (time.perf_counter() - t1) * 1000
        report.add("db.ping (SELECT 1)", ping_ms < 500, f"{ping_ms:.1f} ms")

        # Ключевые таблицы отвечают на запрос.
        for table in CORE_TABLES:
            try:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    report.add(f"table:{table}", False, "missing")
                    continue
                count = await conn.fetchval(f'SELECT COUNT(*)::int FROM "{table}"')
                report.add(f"table:{table}", True, f"rows={count}")
            except Exception as exc:  # noqa: BLE001
                report.add(f"table:{table}", False, f"{type(exc).__name__}: {exc}")
    finally:
        await conn.close()


def check_api(report: Report) -> None:
    import json
    import urllib.request

    print("-- Live API / WebApp (optional) --")
    targets = (
        ("API /health", "http://127.0.0.1:8000/health", True),
        ("WebApp Vite", "http://127.0.0.1:5173/", False),
    )
    for name, url, want_json in targets:
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                body = resp.read(4096)
                if want_json:
                    data = json.loads(body.decode("utf-8", "replace"))
                    detail = (
                        f"app_mode={data.get('app_mode')} "
                        f"db={data.get('db_name')} ok={data.get('ok')}"
                    )
                    report.add(name, bool(data.get("ok")), detail)
                else:
                    report.add(name, resp.status == 200, f"HTTP {resp.status}")
        except Exception as exc:  # noqa: BLE001
            report.add(name, False, f"not reachable ({type(exc).__name__})")


async def check_deep(report: Report) -> None:
    """Прогон реального слоя server/db.py (импорт + connect + read)."""
    print("-- Deep: real server/db.py data layer --")
    server_dir = ROOT / "server"
    sys.path.insert(0, str(server_dir))
    try:
        import db as server_db  # type: ignore
    except Exception as exc:  # noqa: BLE001
        report.add("server.db import", False, f"{type(exc).__name__}: {exc}")
        return
    report.add("server.db import", True, "module loaded")
    try:
        await server_db.db.connect()
        report.add("server.db.connect", server_db.db.pool is not None, "pool ready")
    except Exception as exc:  # noqa: BLE001
        report.add("server.db.connect", False, f"{type(exc).__name__}: {exc}")
        return
    finally:
        try:
            await server_db.db.close()
        except Exception:  # noqa: BLE001
            pass


async def main() -> int:
    parser = argparse.ArgumentParser(description="System self-test")
    parser.add_argument("--api", action="store_true", help="also probe live API/WebApp")
    parser.add_argument("--deep", action="store_true", help="also import+connect server/db.py")
    args = parser.parse_args()

    dbc.bootstrap_database_env()
    print_config_banner()

    report = Report()
    await check_live_db(report)
    if args.api:
        check_api(report)
    if args.deep:
        await check_deep(report)

    report.summary()
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
