# -*- coding: utf-8 -*-
"""Расхождения живой схемы, которые CREATE / ADD COLUMN IF NOT EXISTS не чинят."""
from __future__ import annotations

import logging

# Таблицы персонала и панели. Все их *_id и *_by в schema.sql объявлены BIGINT:
# Telegram ID давно вышли за int4, а старые копии таблиц создавались с INTEGER.
STAFF_TABLES: tuple[str, ...] = (
    "admin_accounts",
    "admin_register_pending",
    "admin_applications",
    "admin_activity",
    "admin_audit_log",
    "admin_panel_role_defaults",
    "admin_panel_user_access",
    "staff_salaries",
    "salary_payments",
    "salary_appeals",
    "pending_payouts",
    "staff_role_history",
    "staff_notes",
    "staff_strikes",
    "staff_shifts",
    "staff_actions",
    "staff_complaints",
    "staff_payout_settings",
    "staff_bonuses",
    "bonus_payments",
    "staff_star_payouts",
)

_NARROW_INT_TYPES = frozenset({"smallint", "integer"})

_NARROW_COLUMNS_SQL = """
    SELECT c.table_name, c.column_name, c.data_type
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = current_schema()
      AND t.table_type = 'BASE TABLE'
      AND c.table_name = ANY($1::text[])
      AND c.data_type IN ('smallint', 'integer')
    ORDER BY c.table_name, c.ordinal_position
"""


def needs_bigint(column: str, data_type: str) -> bool:
    name = (column or "").strip().lower()
    if name == "id" or (data_type or "").strip().lower() not in _NARROW_INT_TYPES:
        return False
    return name.endswith("_id") or name.endswith("_by")


def _ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def widen_sql(table: str, column: str) -> str:
    return f"ALTER TABLE {_ident(table)} ALTER COLUMN {_ident(column)} TYPE BIGINT"


async def widen_staff_ids(conn, log: logging.Logger) -> list[str]:
    """Переводит узкие ID-столбцы таблиц персонала в BIGINT. Идемпотентно."""
    rows = await conn.fetch(_NARROW_COLUMNS_SQL, list(STAFF_TABLES))
    widened: list[str] = []
    for row in rows:
        table, column, data_type = row["table_name"], row["column_name"], row["data_type"]
        if not needs_bigint(column, data_type):
            continue
        try:
            # ALTER переписывает таблицу под эксклюзивной блокировкой: не ждём бота вечно.
            async with conn.transaction():
                await conn.execute("SET LOCAL lock_timeout = '5s'")
                await conn.execute(widen_sql(table, column))
        except Exception as exc:
            log.warning("%s.%s stays %s: %s", table, column, data_type, exc)
            continue
        widened.append(f"{table}.{column}")
    if widened:
        log.warning("Telegram ID columns widened to BIGINT: %s", ", ".join(widened))
    return widened
