# -*- coding: utf-8 -*-
"""staff_rules на API-сервере: должности, права сотрудника, правка флагов.

Бот читает ту же таблицу в bot/admins/mute.py, но пакета bot в образе API нет.
Разбор столбцов и значений должен совпадать с ботом один в один: что панель
показывает включённым, то бот и разрешает.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

MISSING_TABLE = "В базе нет таблицы staff_rules: бот не знает, кому можно наказывать."
NO_FLAGS = "В staff_rules нет столбцов наказаний (mute, ban и других)."

CACHE_SEC = 15.0

_SKIP_COLUMNS = frozenset({"id", "created_at", "updated_at"})
_IMPORTANCE_NAMES = ("importance", "priority", "rank", "weight", "level", "seniority", "sort_order")
_METADATA_COLUMNS = frozenset({
    "description", "roles", "role",
    "required_status", "account_status", "status_required",
    "required_availability", "account_availability", "availability_required",
    *_IMPORTANCE_NAMES,
})
_NAMED_FLAGS = frozenset({
    "mute", "muteall", "unmute", "ban", "banall", "banfull",
    "kick", "kickall", "warn", "warnall", "warnfull",
})
_FLAG_TYPE_PREFIXES = ("int", "smallint", "bigint", "bool", "bit")
_STATUS_COLUMNS = ("required_status", "account_status", "status_required")
_AVAILABILITY_COLUMNS = ("required_availability", "account_availability", "availability_required")

_COLUMNS_SQL = """
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'staff_rules'
    ORDER BY ordinal_position
"""


@dataclass(frozen=True)
class RulesSchema:
    role_column: str
    description_column: Optional[str]
    importance_column: Optional[str]
    permission_columns: tuple[str, ...]
    udt: Mapping[str, str] = field(default_factory=dict, compare=False, hash=False)
    problem: Optional[str] = None

    def column(self, name: str) -> Optional[str]:
        want = (name or "").strip().lower()
        for col in self.permission_columns:
            if col.lower() == want:
                return col
        return None


@dataclass(frozen=True)
class StaffRule:
    role: str
    title: str
    permissions: Mapping[str, bool] = field(default_factory=dict, compare=False, hash=False)
    importance: Optional[int] = None
    required_status: Optional[str] = None
    required_availability: Optional[str] = None

    def granted(self) -> list[str]:
        return [str(col).strip().lower() for col, on in self.permissions.items() if on]


@dataclass(frozen=True)
class StaffAccount:
    user_id: int
    role: Optional[str]
    status: str
    availability: str
    availability_until: Optional[datetime] = None

    def is_operational(self, rule: Optional[StaffRule] = None, now: Optional[datetime] = None) -> bool:
        if not self.role:
            return False
        if rule is not None:
            if rule.required_status and self.status != rule.required_status:
                return False
            if rule.required_availability and self.availability != rule.required_availability:
                return False
        until = self.availability_until
        if until is not None:
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > (now or datetime.now(timezone.utc)):
                return False
        return bool(self.status)


def flag_on(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value).strip().lower() in ("1", "true", "yes", "да", "t")


def _named(names: Sequence[str], *candidates: str) -> Optional[str]:
    targets = {c.lower() for c in candidates}
    for name in names:
        if name.lower() in targets:
            return name
    return None


def _is_metadata(name: str) -> bool:
    low = name.lower()
    if low in _METADATA_COLUMNS or low in _SKIP_COLUMNS:
        return True
    return any(h in low for h in ("title", "label", "display")) and low not in ("roles", "role")


def _is_flag(name: str, data_type: str) -> bool:
    if _is_metadata(name):
        return False
    low = name.lower()
    if low in _NAMED_FLAGS or low.startswith("can_") or low.endswith("_allowed"):
        return True
    return (data_type or "").lower().startswith(_FLAG_TYPE_PREFIXES)


def detect_schema(columns: Iterable[Sequence[Any]]) -> RulesSchema:
    """Столбцы staff_rules из information_schema: (имя, data_type, udt_name)."""
    cols = [
        (str(c[0]), str(c[1] or ""), str(c[2] or "") if len(c) > 2 else "")
        for c in columns
    ]
    if not cols:
        return RulesSchema("roles", "description", None, (), problem=MISSING_TABLE)
    names = [name for name, _, _ in cols]
    flags = [name for name, data_type, _ in cols if _is_flag(name, data_type)]
    return RulesSchema(
        role_column=_named(names, "roles", "role") or names[0],
        description_column=_named(names, "description"),
        importance_column=_named(names, *_IMPORTANCE_NAMES),
        permission_columns=tuple(dict.fromkeys(flags)),
        udt={name: udt for name, _, udt in cols},
        problem=None if flags else NO_FLAGS,
    )


def _present(row: Mapping[str, Any], columns: Sequence[str]) -> Optional[str]:
    for col in columns:
        val = row.get(col)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _importance(row: Mapping[str, Any], schema: RulesSchema) -> Optional[int]:
    if not schema.importance_column:
        return None
    raw = row.get(schema.importance_column)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def parse_rule(row: Mapping[str, Any], schema: RulesSchema) -> Optional[StaffRule]:
    raw_role = row.get(schema.role_column)
    if raw_role is None or not str(raw_role).strip():
        return None
    role = str(raw_role).strip().lower()
    title = _present(row, (schema.description_column,)) if schema.description_column else None
    return StaffRule(
        role=role,
        title=title or role.replace("_", " ").strip().title(),
        permissions={col: flag_on(row.get(col)) for col in schema.permission_columns},
        importance=_importance(row, schema),
        required_status=_present(row, _STATUS_COLUMNS),
        required_availability=_present(row, _AVAILABILITY_COLUMNS),
    )


def _ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def build_update(
    schema: RulesSchema,
    role: str,
    flags: Mapping[str, Any],
    allowed: Iterable[str],
) -> Optional[tuple[str, list[Any]]]:
    """UPDATE одной строки staff_rules. Столбцы бывают int, bool и text с '1'/'0'."""
    allow = {str(a).strip().lower() for a in allowed}
    chosen: dict[str, bool] = {}
    for key, on in flags.items():
        want = str(key).strip().lower()
        col = schema.column(want) if want in allow else None
        if col:
            chosen[col] = bool(on)
    if not chosen:
        return None
    sets: list[str] = []
    values: list[Any] = []
    for col, on in chosen.items():
        values.append("1" if on else "0")
        sets.append(f"{_ident(col)} = ${len(values)}::text::{_ident(schema.udt.get(col) or 'text')}")
    values.append(role.strip().lower())
    sql = (
        f"UPDATE staff_rules SET {', '.join(sets)} "
        f"WHERE lower(btrim({_ident(schema.role_column)}::text)) = ${len(values)}"
    )
    return sql, values


_cache: Optional[tuple[float, dict[str, StaffRule], RulesSchema]] = None


def invalidate() -> None:
    global _cache
    _cache = None


async def load(pool, *, fresh: bool = False) -> tuple[dict[str, StaffRule], RulesSchema]:
    global _cache
    now = time.monotonic()
    if not fresh and _cache is not None and now - _cache[0] < CACHE_SEC:
        return _cache[1], _cache[2]
    async with pool.acquire() as conn:
        cols = await conn.fetch(_COLUMNS_SQL)
        schema = detect_schema((c["column_name"], c["data_type"], c["udt_name"]) for c in cols)
        rows = [] if schema.problem else await conn.fetch("SELECT * FROM staff_rules")
    rules: dict[str, StaffRule] = {}
    for row in rows:
        rule = parse_rule(dict(row), schema)
        if rule:
            rules[rule.role] = rule
    _cache = (now, rules, schema)
    return rules, schema


async def fetch_account(pool, user_id: int) -> Optional[StaffAccount]:
    row = await pool.fetchrow(
        """
        SELECT user_id, role, status, availability, availability_until
        FROM admin_accounts
        WHERE user_id = $1::bigint
        """,
        int(user_id),
    )
    if not row:
        return None
    return StaffAccount(
        user_id=int(row["user_id"]),
        role=row["role"],
        status=row["status"] or "",
        availability=row["availability"] or "",
        availability_until=row["availability_until"],
    )
