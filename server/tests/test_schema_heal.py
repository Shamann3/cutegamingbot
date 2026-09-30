"""Старые таблицы персонала с INTEGER вместо BIGINT для Telegram ID."""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schema_heal import STAFF_TABLES, needs_bigint, widen_sql, widen_staff_ids


def test_only_narrow_id_columns_need_bigint():
    assert needs_bigint("resolved_by", "integer")
    assert needs_bigint("admin_user_id", "integer")
    assert needs_bigint("user_id", "smallint")
    assert needs_bigint("complaint_id", "integer")
    assert not needs_bigint("id", "integer")
    assert not needs_bigint("amount", "integer")
    assert not needs_bigint("rules_version", "integer")
    assert not needs_bigint("resolved_by", "bigint")
    assert not needs_bigint("target_id", "text")


def test_scope_is_staff_tables_only():
    assert "staff_complaints" in STAFF_TABLES
    assert "admin_audit_log" in STAFF_TABLES
    for game_table in ("users", "cutehistory", "farm_plots", "group_positions", "support_messages"):
        assert game_table not in STAFF_TABLES


def test_widen_sql_quotes_names():
    assert widen_sql("staff_complaints", "resolved_by") == (
        'ALTER TABLE "staff_complaints" ALTER COLUMN "resolved_by" TYPE BIGINT'
    )


class _Conn:
    def __init__(self, rows, broken=()):
        self.rows = rows
        self.broken = set(broken)
        self.executed = []
        self.fetch_args = None

    async def fetch(self, sql, *args):
        self.fetch_args = args
        return self.rows

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, sql):
        self.executed.append(sql)
        if any(f'"{name}"' in sql for name in self.broken):
            raise RuntimeError("cannot alter type of a column used by a view or rule")


def _row(table, column, data_type="integer"):
    return {"table_name": table, "column_name": column, "data_type": data_type}


def test_widening_skips_non_ids_and_survives_a_stuck_column(caplog):
    conn = _Conn(
        [
            _row("staff_complaints", "id"),
            _row("staff_complaints", "resolved_by"),
            _row("staff_salaries", "amount"),
            _row("staff_notes", "author_id"),
            _row("admin_audit_log", "admin_user_id"),
        ],
        broken={"author_id"},
    )
    with caplog.at_level(logging.WARNING):
        widened = asyncio.run(widen_staff_ids(conn, logging.getLogger("test-heal")))

    assert widened == ["staff_complaints.resolved_by", "admin_audit_log.admin_user_id"]
    assert conn.fetch_args == (list(STAFF_TABLES),)
    alters = [sql for sql in conn.executed if sql.startswith("ALTER")]
    assert alters == [
        widen_sql("staff_complaints", "resolved_by"),
        widen_sql("staff_notes", "author_id"),
        widen_sql("admin_audit_log", "admin_user_id"),
    ]
    assert conn.executed.count("SET LOCAL lock_timeout = '5s'") == 3
    assert "staff_notes.author_id stays integer" in caplog.text
    assert "staff_complaints.resolved_by" in caplog.text


def test_widening_is_quiet_when_nothing_is_narrow(caplog):
    conn = _Conn([])
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(widen_staff_ids(conn, logging.getLogger("test-heal"))) == []
    assert conn.executed == []
    assert caplog.text == ""
