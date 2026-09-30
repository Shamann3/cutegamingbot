"""staff_rules без пакета bot: разбор как у бота, права сотрудника, правка флагов."""
import asyncio
import sys
import types
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import staff_rules
from staff_panel_rights import PUNISH_COLUMNS, actor_has_banfull, actor_staff_perms
from staff_rules import (
    MISSING_TABLE,
    NO_FLAGS,
    StaffAccount,
    build_update,
    detect_schema,
    flag_on,
    parse_rule,
)

COLUMNS = [
    ("id", "integer", "int4"),
    ("roles", "text", "text"),
    ("description", "text", "text"),
    ("importance", "integer", "int4"),
    ("mute", "text", "text"),
    ("ban", "integer", "int4"),
    ("banfull", "boolean", "bool"),
    ("created_at", "timestamp with time zone", "timestamptz"),
]

SENIOR = {
    "id": 1,
    "roles": " Senior_Admin ",
    "description": "Старший админ",
    "importance": "4",
    "mute": "1",
    "ban": 0,
    "banfull": True,
}


@pytest.fixture(autouse=True)
def _fresh_cache():
    staff_rules.invalidate()
    yield
    staff_rules.invalidate()


def test_schema_reads_flags_like_the_bot():
    schema = detect_schema(COLUMNS)
    assert schema.role_column == "roles"
    assert schema.description_column == "description"
    assert schema.importance_column == "importance"
    assert schema.permission_columns == ("mute", "ban", "banfull")
    assert schema.problem is None


def test_schema_explains_a_missing_table_or_missing_flags():
    assert detect_schema([]).problem == MISSING_TABLE
    only_text = detect_schema([("roles", "text", "text"), ("description", "text", "text")])
    assert only_text.problem == NO_FLAGS
    assert only_text.permission_columns == ()


def test_row_becomes_a_rule_with_bot_truthiness():
    rule = parse_rule(SENIOR, detect_schema(COLUMNS))
    assert rule.role == "senior_admin"
    assert rule.title == "Старший админ"
    assert rule.importance == 4
    assert dict(rule.permissions) == {"mute": True, "ban": False, "banfull": True}
    assert rule.granted() == ["mute", "banfull"]


def test_rule_without_description_gets_a_readable_title():
    row = {**SENIOR, "description": "  "}
    assert parse_rule(row, detect_schema(COLUMNS)).title == "Senior Admin"
    assert parse_rule({**SENIOR, "roles": " "}, detect_schema(COLUMNS)) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (1, True), (1.0, True), ("1", True), ("да", True), (" T ", True),
     (False, False), (0, False), (2, False), ("0", False), ("false", False), (None, False)],
)
def test_flag_values_match_the_bot(value, expected):
    assert flag_on(value) is expected


def test_account_on_leave_or_without_role_cannot_punish():
    now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    active = StaffAccount(1, "moderator", "active", "active")
    assert active.is_operational(now=now)
    assert not StaffAccount(1, None, "active", "active").is_operational(now=now)
    assert not StaffAccount(1, "moderator", "", "active").is_operational(now=now)
    away = StaffAccount(1, "moderator", "active", "away", now + timedelta(hours=1))
    assert not away.is_operational(now=now)
    back = StaffAccount(1, "moderator", "active", "away", (now - timedelta(hours=1)).replace(tzinfo=None))
    assert back.is_operational(now=now)
    strict = parse_rule({**SENIOR, "required_status": "active"}, detect_schema(
        COLUMNS + [("required_status", "text", "text")]
    ))
    assert not StaffAccount(1, "senior_admin", "pending", "active").is_operational(strict, now=now)


def test_update_writes_each_column_in_its_own_type():
    sql, values = build_update(detect_schema(COLUMNS), " Senior_Admin ", {
        "Mute": False, "mute": True, "banfull": False, "can_fly": True,
    }, PUNISH_COLUMNS)
    assert sql == (
        'UPDATE staff_rules SET "mute" = $1::text::"text", "banfull" = $2::text::"bool" '
        'WHERE lower(btrim("roles"::text)) = $3'
    )
    assert values == ["1", "0", "senior_admin"]


def test_update_ignores_columns_outside_the_punish_list():
    schema = detect_schema(COLUMNS + [("can_fly", "boolean", "bool")])
    assert build_update(schema, "moderator", {"can_fly": True, "rename": True}, PUNISH_COLUMNS) is None


def test_update_quotes_odd_identifiers():
    schema = detect_schema([('role"x', "text", "text"), ("ban", "integer", "int4")])
    sql, _ = build_update(schema, "moderator", {"ban": True}, PUNISH_COLUMNS)
    assert 'lower(btrim("role""x"::text))' in sql


class _Conn:
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows

    async def fetch(self, sql, *args):
        if "information_schema" in sql:
            return [{"column_name": n, "data_type": t, "udt_name": u} for n, t, u in self.columns]
        return self.rows


class _Pool:
    def __init__(self, account, rows, columns=COLUMNS):
        self.account = account
        self.rows = rows
        self.columns = columns
        self.reads = 0

    @asynccontextmanager
    async def acquire(self):
        self.reads += 1
        yield _Conn(self.columns, self.rows)

    async def fetchrow(self, sql, *args):
        assert "$1::bigint" in sql
        return self.account


def _use_pool(monkeypatch, pool):
    monkeypatch.setitem(sys.modules, "db", types.SimpleNamespace(db=types.SimpleNamespace(pool=pool)))


def _account(role="senior_admin", until=None):
    return {"user_id": 7555666259, "role": role, "status": "active",
            "availability": "active", "availability_until": until}


def test_staff_perms_come_from_the_server_without_bot(monkeypatch):
    pool = _Pool(_account(), [SENIOR])
    _use_pool(monkeypatch, pool)
    assert asyncio.run(actor_staff_perms(7555666259)) == ["mute", "banfull"]
    assert asyncio.run(actor_has_banfull(7555666259)) is True
    assert pool.reads == 1


def test_staff_on_leave_gets_no_punishments(monkeypatch):
    later = datetime.now(timezone.utc) + timedelta(days=1)
    _use_pool(monkeypatch, _Pool(_account(until=later), [SENIOR]))
    assert asyncio.run(actor_staff_perms(1)) == []
    assert asyncio.run(actor_has_banfull(1)) is False


def test_role_without_a_rules_row_or_without_db_gets_nothing(monkeypatch):
    _use_pool(monkeypatch, _Pool(_account(role="moderator"), [SENIOR]))
    assert asyncio.run(actor_staff_perms(1)) == []
    _use_pool(monkeypatch, None)
    assert asyncio.run(actor_staff_perms(1)) == []
