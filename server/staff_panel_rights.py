"""Право банфулл для бана из вкладки «Игроки».

Бан в этой вкладке закрывает человека во всём проекте.
Считается только столбец banfull. Цепочка ban → mute его не заменяет.
"""
from __future__ import annotations

import logging

import staff_rules

log = logging.getLogger("staff_panel_rights")

# Столбцы наказаний, которыми управляет матрица в «Админ панель».
PUNISH_COLUMNS: tuple[str, ...] = (
    "mute",
    "muteall",
    "unmute",
    "kick",
    "kickall",
    "warn",
    "warnall",
    "warnfull",
    "ban",
    "banall",
    "banfull",
)


def purge_allowed(*, actor_is_creator: bool, target_is_creator: bool) -> str | None:
    if not actor_is_creator:
        return "Полный сброс допуска может сделать только создатель проекта"
    if target_is_creator:
        return "Создателя проекта убрать нельзя"
    return None


def column_granted(permissions: dict | None, column: str) -> bool:
    if not permissions:
        return False
    want = (column or "").strip().lower()
    if not want:
        return False
    for key, value in permissions.items():
        if str(key).strip().lower() == want and bool(value):
            return True
    return False


async def _rule_for_user(user_id: int):
    from db import db

    pool = db.pool
    if pool is None:
        return None, None
    try:
        account = await staff_rules.fetch_account(pool, int(user_id))
        if not account or not account.role:
            return account, None
        rules, _schema = await staff_rules.load(pool)
    except Exception as exc:
        log.warning("staff_rules for %s unavailable: %s", user_id, exc)
        return None, None
    return account, rules.get(account.role.strip().lower())


async def actor_has_banfull(user_id: int) -> bool:
    return "banfull" in await actor_staff_perms(user_id)


async def actor_staff_perms(user_id: int) -> list[str]:
    """Список включённых столбцов staff_rules для текущего сотрудника."""
    account, rule = await _rule_for_user(user_id)
    if not account or not rule:
        return []
    if not account.is_operational(rule):
        return []
    return rule.granted()
