# server/panel_access.py
"""Доступ к разделам админ-панели: дефолты по роли + персональные оверрайды.

Только владелец управляет матрицей. Владелец всегда видит все разделы,
включая «Админ панель» (panelAccess).
"""
from __future__ import annotations

import time

from admin_permissions import (
    ALL_PERMISSIONS,
    PERMISSIONS_BY_ROLE,
    ROLE_JUNIOR,
    ROLE_MODERATOR,
    ROLE_OWNER,
    ROLE_SENIOR,
    ROLE_LABELS,
)
from db import db

# Каталог разделов (синхрон с admin/src/constants/panelNav.js).
# permissions: API-права, которые открывает раздел. Пустой список — раздел
# только для навигации (скрытие не режет чужие permission-гейты).
PANEL_SECTION_DEFS: list[dict] = [
    {"id": "dashboard", "label": "Главная", "group": "overview", "permissions": []},
    {"id": "users", "label": "Игроки", "group": "people", "permissions": ["view_players"]},
    {"id": "accounts", "label": "Пользователи", "group": "people", "permissions": ["view_accounts"]},
    {
        "id": "moderation",
        "label": "Архив",
        "group": "people",
        "permissions": ["moderate_ban", "moderate_unban", "manage_appeals", "adjust_balance", "give_items"],
    },
    {"id": "economy", "label": "Экономика", "group": "economy", "permissions": ["manage_economy"]},
    {"id": "market", "label": "Биржа", "group": "economy", "permissions": ["view_market", "market_cancel"]},
    {"id": "farm", "label": "Ферма", "group": "economy", "permissions": ["manage_farm"]},
    {"id": "content", "label": "Контент", "group": "content", "permissions": ["manage_content"]},
    {"id": "giveaways", "label": "Розыгрыши", "group": "content", "permissions": ["manage_content"]},
    {"id": "events", "label": "Ивенты", "group": "content", "permissions": ["manage_events"]},
    {"id": "broadcast", "label": "Рассылка", "group": "content", "permissions": ["manage_broadcast"]},
    {
        "id": "staff",
        "label": "Стафф",
        "group": "team",
        "permissions": [
            "review_applications",
            "assign_roles",
            "manage_staff",
            "set_salary",
            "approve_salary",
            "pay_salary",
        ],
    },
    {"id": "support", "label": "Поддержка", "group": "team", "permissions": []},
    {"id": "analytics", "label": "Аналитика", "group": "insights", "permissions": ["view_analytics"]},
    {"id": "logs", "label": "Логи", "group": "insights", "permissions": ["view_logs"]},
    {"id": "chronicle", "label": "Хронология", "group": "insights", "permissions": []},
    {"id": "settings", "label": "Настройки", "group": "system", "permissions": ["manage_settings"]},
    {"id": "security", "label": "Доступ", "group": "system", "permissions": ["manage_security"]},
    {
        "id": "panelAccess",
        "label": "Админ панель",
        "group": "system",
        "permissions": ["manage_panel_access"],
        "ownerOnly": True,
    },
]

SECTION_BY_ID = {s["id"]: s for s in PANEL_SECTION_DEFS}
ALL_SECTION_IDS = [s["id"] for s in PANEL_SECTION_DEFS]
CONFIGURABLE_SECTION_IDS = [s["id"] for s in PANEL_SECTION_DEFS if not s.get("ownerOnly")]

# Роли, для которых настраиваются дефолты (не owner / не кандидаты).
CONFIGURABLE_ROLES = (ROLE_SENIOR, ROLE_JUNIOR, ROLE_MODERATOR)

_TABLES_READY = False
# Короткий in-memory кэш дефолтов ролей — снимает лишние SELECT при кликах.
_ROLE_DEFAULTS_CACHE: tuple[float, dict[str, dict[str, bool]]] | None = None
_ROLE_DEFAULTS_TTL_SEC = 8.0


def invalidate_role_defaults_cache() -> None:
    global _ROLE_DEFAULTS_CACHE
    _ROLE_DEFAULTS_CACHE = None


async def ensure_panel_access_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_panel_role_defaults (
            role TEXT NOT NULL,
            section_id TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by BIGINT,
            PRIMARY KEY (role, section_id)
        );
        CREATE TABLE IF NOT EXISTS admin_panel_user_access (
            user_id BIGINT NOT NULL,
            section_id TEXT NOT NULL,
            allowed BOOLEAN NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by BIGINT,
            PRIMARY KEY (user_id, section_id)
        );
        CREATE INDEX IF NOT EXISTS admin_panel_user_access_user_idx
            ON admin_panel_user_access (user_id);
        """
    )
    await _seed_role_defaults_if_empty()
    _TABLES_READY = True


def _builtin_default_enabled(role: str, section_id: str) -> bool:
    """Дефолт «из коробки» — как прежняя видимость по правам роли."""
    sec = SECTION_BY_ID.get(section_id)
    if not sec:
        return False
    if sec.get("ownerOnly"):
        return role == ROLE_OWNER
    if role == ROLE_OWNER:
        return True
    role_perms = PERMISSIONS_BY_ROLE.get(role, set())
    perms = sec.get("permissions") or []
    if not perms:
        # Разделы без permission раньше были видны всем активным админам.
        return role in (ROLE_SENIOR, ROLE_JUNIOR, ROLE_MODERATOR, ROLE_OWNER)
    return any(p in role_perms for p in perms)


async def _seed_role_defaults_if_empty() -> None:
    count = await db.pool.fetchval("SELECT COUNT(*) FROM admin_panel_role_defaults")
    if count and int(count) > 0:
        return
    rows = []
    for role in CONFIGURABLE_ROLES:
        for sid in CONFIGURABLE_SECTION_IDS:
            rows.append((role, sid, _builtin_default_enabled(role, sid)))
    if rows:
        await db.pool.executemany(
            """
            INSERT INTO admin_panel_role_defaults (role, section_id, enabled)
            VALUES ($1, $2, $3)
            ON CONFLICT (role, section_id) DO NOTHING
            """,
            rows,
        )


async def get_role_defaults_map(*, force: bool = False) -> dict[str, dict[str, bool]]:
    global _ROLE_DEFAULTS_CACHE
    now = time.monotonic()
    if (
        not force
        and _ROLE_DEFAULTS_CACHE is not None
        and (now - _ROLE_DEFAULTS_CACHE[0]) < _ROLE_DEFAULTS_TTL_SEC
    ):
        return _ROLE_DEFAULTS_CACHE[1]

    await ensure_panel_access_tables()
    rows = await db.pool.fetch(
        "SELECT role, section_id, enabled FROM admin_panel_role_defaults"
    )
    out: dict[str, dict[str, bool]] = {r: {} for r in CONFIGURABLE_ROLES}
    for row in rows:
        role = row["role"]
        if role not in out:
            continue
        out[role][row["section_id"]] = bool(row["enabled"])
    # Дозаполнить отсутствующие секции builtin-значениями
    for role in CONFIGURABLE_ROLES:
        for sid in CONFIGURABLE_SECTION_IDS:
            if sid not in out[role]:
                out[role][sid] = _builtin_default_enabled(role, sid)
    _ROLE_DEFAULTS_CACHE = (now, out)
    return out


async def get_user_overrides(user_id: int) -> dict[str, bool]:
    await ensure_panel_access_tables()
    rows = await db.pool.fetch(
        "SELECT section_id, allowed FROM admin_panel_user_access WHERE user_id = $1",
        user_id,
    )
    return {r["section_id"]: bool(r["allowed"]) for r in rows}


def effective_sections_from_maps(
    role: str,
    role_defaults: dict[str, dict[str, bool]],
    overrides: dict[str, bool],
) -> list[str]:
    """Чистый расчёт без БД — для overview и optimistic-патчей."""
    if role == ROLE_OWNER:
        return list(ALL_SECTION_IDS)
    role_map = role_defaults.get(role) or {
        sid: _builtin_default_enabled(role, sid) for sid in CONFIGURABLE_SECTION_IDS
    }
    enabled: list[str] = []
    for sid in CONFIGURABLE_SECTION_IDS:
        if sid in overrides:
            allowed = overrides[sid]
        else:
            allowed = bool(role_map.get(sid, _builtin_default_enabled(role, sid)))
        if allowed:
            enabled.append(sid)
    return enabled


async def effective_panel_sections(role: str, user_id: int) -> list[str]:
    """Итоговый список section_id для навигации."""
    if role == ROLE_OWNER:
        return list(ALL_SECTION_IDS)
    defaults = await get_role_defaults_map()
    overrides = await get_user_overrides(user_id)
    return effective_sections_from_maps(role, defaults, overrides)


def permissions_for_sections(role: str, section_ids: list[str]) -> list[str]:
    """Права API = пересечение «права роли» с «правами открытых разделов»,
    плюс права открытых разделов, которые owner явно выдал сверх роли
    (через открытие вкладки, которой у роли раньше не было).
    """
    if role == ROLE_OWNER:
        return sorted(ALL_PERMISSIONS)

    role_perms = set(PERMISSIONS_BY_ROLE.get(role, set()))
    section_set = set(section_ids)
    # Права, которые «принадлежат» хотя бы одному открытому разделу
    granted_by_sections: set[str] = set()
    # Все права, привязанные к каталогу (чтобы отрезать закрытые разделы)
    catalog_perms: set[str] = set()
    for sec in PANEL_SECTION_DEFS:
        for p in sec.get("permissions") or []:
            catalog_perms.add(p)
            if sec["id"] in section_set:
                granted_by_sections.add(p)

    # Непривязанные к разделам права роли оставляем как есть
    unbound = role_perms - catalog_perms
    # Из привязанных — только те, что открыты разделами; плюс явный grant
    # через открытую вкладку (даже если роль раньше не имела permission).
    bound = (role_perms & catalog_perms & granted_by_sections) | (
        granted_by_sections - role_perms
    )
    # view_player_sensitive остаётся только у owner (в ALL)
    result = unbound | bound
    result.discard("manage_panel_access")
    result.discard("view_player_sensitive")
    return sorted(result)


async def resolve_account_access(role: str, user_id: int, status: str) -> tuple[list[str], list[str]]:
    """(permissions, panelSections) для активного аккаунта."""
    if status != "active":
        return [], []
    sections = await effective_panel_sections(role, user_id)
    perms = permissions_for_sections(role, sections)
    return perms, sections


async def set_role_default(role: str, section_id: str, enabled: bool, updated_by: int) -> None:
    await ensure_panel_access_tables()
    if role not in CONFIGURABLE_ROLES:
        raise ValueError("Роль нельзя настраивать")
    if section_id not in CONFIGURABLE_SECTION_IDS:
        raise ValueError("Раздел недоступен для настройки")
    await db.pool.execute(
        """
        INSERT INTO admin_panel_role_defaults (role, section_id, enabled, updated_at, updated_by)
        VALUES ($1, $2, $3, NOW(), $4)
        ON CONFLICT (role, section_id) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by
        """,
        role,
        section_id,
        bool(enabled),
        updated_by,
    )
    invalidate_role_defaults_cache()


async def set_user_override(
    user_id: int,
    section_id: str,
    allowed: bool | None,
    updated_by: int,
) -> None:
    """allowed=None — сброс оверрайда (вернуться к дефолту роли)."""
    await ensure_panel_access_tables()
    if section_id not in CONFIGURABLE_SECTION_IDS:
        raise ValueError("Раздел недоступен для настройки")
    if allowed is None:
        await db.pool.execute(
            "DELETE FROM admin_panel_user_access WHERE user_id = $1 AND section_id = $2",
            user_id,
            section_id,
        )
        return
    await db.pool.execute(
        """
        INSERT INTO admin_panel_user_access (user_id, section_id, allowed, updated_at, updated_by)
        VALUES ($1, $2, $3, NOW(), $4)
        ON CONFLICT (user_id, section_id) DO UPDATE
        SET allowed = EXCLUDED.allowed,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by
        """,
        user_id,
        section_id,
        bool(allowed),
        updated_by,
    )


async def set_user_overrides_batch(
    items: list[dict],
    updated_by: int,
) -> int:
    """Пакетная запись оверрайдов. item: {userId, sectionId, allowed|reset}.

    Один round-trip на upsert и один на delete — вместо N последовательных PUT.
    """
    await ensure_panel_access_tables()
    upserts: list[tuple[int, str, bool, int]] = []
    deletes: list[tuple[int, str]] = []
    for raw in items:
        uid = int(raw["userId"])
        sid = str(raw["sectionId"])
        if sid not in CONFIGURABLE_SECTION_IDS:
            raise ValueError(f"Раздел недоступен: {sid}")
        if raw.get("reset"):
            deletes.append((uid, sid))
        else:
            if "allowed" not in raw or raw["allowed"] is None:
                raise ValueError("Укажите allowed или reset")
            upserts.append((uid, sid, bool(raw["allowed"]), updated_by))

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if deletes:
                await conn.executemany(
                    "DELETE FROM admin_panel_user_access WHERE user_id = $1 AND section_id = $2",
                    deletes,
                )
            if upserts:
                await conn.executemany(
                    """
                    INSERT INTO admin_panel_user_access
                        (user_id, section_id, allowed, updated_at, updated_by)
                    VALUES ($1, $2, $3, NOW(), $4)
                    ON CONFLICT (user_id, section_id) DO UPDATE
                    SET allowed = EXCLUDED.allowed,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                    """,
                    upserts,
                )
    return len(upserts) + len(deletes)


async def list_panel_access_overview() -> dict:
    """Данные для вкладки владельца — без N+1 по каждому сотруднику."""
    await ensure_panel_access_tables()
    defaults = await get_role_defaults_map()
    members = await db.pool.fetch(
        """
        SELECT user_id, username, first_name, role, status
        FROM admin_accounts
        WHERE status = 'active'
          AND role = ANY($1::text[])
        ORDER BY
          CASE role
            WHEN 'senior_admin' THEN 1
            WHEN 'junior_admin' THEN 2
            WHEN 'moderator' THEN 3
            ELSE 9
          END,
          COALESCE(first_name, username, user_id::text)
        """,
        list(CONFIGURABLE_ROLES),
    )
    member_ids = [int(m["user_id"]) for m in members]
    override_rows = await db.pool.fetch(
        """
        SELECT user_id, section_id, allowed
        FROM admin_panel_user_access
        WHERE user_id = ANY($1::bigint[])
        """,
        member_ids or [0],
    )
    overrides_by_user: dict[int, dict[str, bool]] = {}
    for r in override_rows:
        uid = int(r["user_id"])
        overrides_by_user.setdefault(uid, {})[r["section_id"]] = bool(r["allowed"])

    items = []
    for m in members:
        uid = int(m["user_id"])
        role = m["role"]
        ov = overrides_by_user.get(uid, {})
        items.append(
            {
                "userId": uid,
                "username": m["username"],
                "firstName": m["first_name"],
                "role": role,
                "roleLabel": ROLE_LABELS.get(role, role),
                "overrides": ov,
                "effectiveSections": effective_sections_from_maps(role, defaults, ov),
            }
        )

    return {
        "sections": [
            {
                "id": s["id"],
                "label": s["label"],
                "group": s["group"],
                "ownerOnly": bool(s.get("ownerOnly")),
                "configurable": s["id"] in CONFIGURABLE_SECTION_IDS,
            }
            for s in PANEL_SECTION_DEFS
        ],
        "roles": [
            {"id": r, "label": ROLE_LABELS.get(r, r)} for r in CONFIGURABLE_ROLES
        ],
        "roleDefaults": defaults,
        "members": items,
    }
