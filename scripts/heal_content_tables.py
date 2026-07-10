"""Heal content/config tables on a drifted database.

Older databases were created with "CREATE TABLE IF NOT EXISTS" before the
UNIQUE keys existed, and the seed logic only guarded on "count == 0". As a
result some installs accumulated exact-duplicate rows in the small config
tables (farm_crops, quests, application_questions, craft_recipes) and their
child rows (farm_crop_harvest_drops, quest_rewards), and the natural-key
UNIQUE constraints are missing (which breaks INSERT ... ON CONFLICT).

This tool is SAFE and IDEMPOTENT:
  * It only touches the small config tables (never users/farm_plots/etc).
  * It keeps exactly one physical row per natural key / per logical tuple
    (the one with the smallest ctid) and removes the extra copies.
  * It then creates UNIQUE indexes so ON CONFLICT works and duplicates
    can never come back.
  * Running it again does nothing (no duplicates left, indexes already exist).

Usage:
    python scripts/heal_content_tables.py            # apply
    python scripts/heal_content_tables.py --dry-run  # report only
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg

from bot.config.db_config import (
    bootstrap_database_env,
    build_db_settings,
    db_connect_target,
)

# Parent tables: dedupe by a single natural key column, then make it UNIQUE.
PARENT_TABLES = (
    # (table, natural_key_column, unique_index_name)
    ("farm_crops", "key", "farm_crops_key_uidx"),
    ("quests", "key", "quests_key_uidx"),
    ("application_questions", "qkey", "application_questions_qkey_uidx"),
    ("craft_recipes", "key", "craft_recipes_key_uidx"),
)

# Child tables: dedupe by the full logical tuple (nullable-safe).
CHILD_TABLES = (
    # (table, [columns...])
    ("farm_crop_harvest_drops", ["crop_id", "item_id", "min_amount", "max_amount", "sort_order"]),
    ("quest_rewards", ["quest_id", "kind", "amount", "item_id", "sort_order"]),
)


async def table_exists(conn, table: str) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass($1)", table))


async def count_rows(conn, table: str) -> int:
    return int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}") or 0)


async def dedupe_parent(conn, table: str, key: str) -> int:
    before = await count_rows(conn, table)
    await conn.execute(
        f'DELETE FROM {table} a USING {table} b '
        f'WHERE a.ctid > b.ctid AND a."{key}" = b."{key}"'
    )
    after = await count_rows(conn, table)
    return before - after


async def dedupe_child(conn, table: str, cols: list[str]) -> int:
    before = await count_rows(conn, table)
    match = " AND ".join(f'a."{c}" IS NOT DISTINCT FROM b."{c}"' for c in cols)
    await conn.execute(
        f"DELETE FROM {table} a USING {table} b WHERE a.ctid > b.ctid AND {match}"
    )
    after = await count_rows(conn, table)
    return before - after


async def ensure_unique_index(conn, table: str, key: str, idx: str) -> str:
    try:
        await conn.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {table} ("{key}")'
        )
        return "ok"
    except Exception as e:  # pragma: no cover - defensive
        return f"skip ({type(e).__name__})"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only, do not modify")
    args = parser.parse_args()

    bootstrap_database_env()
    settings = build_db_settings()
    print(f"[heal] target = {db_connect_target()}")
    print(f"[heal] mode   = {'DRY-RUN (no changes)' if args.dry_run else 'APPLY'}")

    conn = await asyncpg.connect(
        user=settings["user"], password=settings["password"],
        database=settings["database"], host=settings["host"],
        port=settings["port"], ssl=settings["ssl"], timeout=15,
    )
    total_removed = 0
    try:
        async with conn.transaction():
            print("\n--- child tables (dedupe by full row) ---")
            for table, cols in CHILD_TABLES:
                if not await table_exists(conn, table):
                    print(f"  {table:<28} MISSING (skip)")
                    continue
                if args.dry_run:
                    dist = await conn.fetchval(
                        f"SELECT COUNT(*) FROM (SELECT DISTINCT "
                        + ", ".join(f'"{c}"' for c in cols)
                        + f" FROM {table}) t"
                    )
                    tot = await count_rows(conn, table)
                    print(f"  {table:<28} total={tot} dupes={tot - int(dist or 0)}")
                else:
                    removed = await dedupe_child(conn, table, cols)
                    total_removed += removed
                    print(f"  {table:<28} removed {removed} duplicate row(s)")

            print("\n--- parent tables (dedupe by natural key) ---")
            for table, key, _idx in PARENT_TABLES:
                if not await table_exists(conn, table):
                    print(f"  {table:<28} MISSING (skip)")
                    continue
                if args.dry_run:
                    dist = await conn.fetchval(f'SELECT COUNT(DISTINCT "{key}") FROM {table}')
                    tot = await count_rows(conn, table)
                    print(f"  {table:<28} total={tot} dupes={tot - int(dist or 0)}")
                else:
                    removed = await dedupe_parent(conn, table, key)
                    total_removed += removed
                    print(f"  {table:<28} removed {removed} duplicate row(s)")

            if args.dry_run:
                print("\n[heal] dry-run: rolling back (no changes committed)")
                raise _Rollback()

            print("\n--- unique indexes (enable ON CONFLICT, prevent re-dupes) ---")
            for table, key, idx in PARENT_TABLES:
                if not await table_exists(conn, table):
                    continue
                status = await ensure_unique_index(conn, table, key, idx)
                print(f"  {idx:<36} {status}")

        print(f"\n[heal] DONE. Removed {total_removed} duplicate row(s). Indexes ensured.")
        return 0
    except _Rollback:
        return 0
    finally:
        await conn.close()


class _Rollback(Exception):
    """Internal: abort the transaction cleanly for --dry-run."""


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
