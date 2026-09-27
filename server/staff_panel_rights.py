"""Право банфулл для бана из вкладки «Игроки».

Бан в этой вкладке закрывает человека во всём проекте.
Считается только столбец banfull. Цепочка ban → mute его не заменяет.
"""
from __future__ import annotations

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
    try:
        from bot.admins.mute import get_admin_account, get_staff_rule
    except Exception:
        return None, None
    try:
        account = await get_admin_account(int(user_id))
    except Exception:
        return None, None
    if not account or not account.role:
        return account, None
    try:
        rule = await get_staff_rule(account.role)
    except Exception:
        return account, None
    return account, rule


async def actor_has_banfull(user_id: int) -> bool:
    account, rule = await _rule_for_user(user_id)
    if not account or not rule:
        return False
    if not account.is_operational(rule):
        return False
    return column_granted(rule.permissions, "banfull")


async def actor_staff_perms(user_id: int) -> list[str]:
    """Список включённых столбцов staff_rules для текущего сотрудника."""
    account, rule = await _rule_for_user(user_id)
    if not account or not rule:
        return []
    if not account.is_operational(rule):
        return []
    out: list[str] = []
    for key, value in (rule.permissions or {}).items():
        if bool(value):
            out.append(str(key).strip().lower())
    return out
