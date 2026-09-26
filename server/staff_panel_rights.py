"""Право банфулл для бана из вкладки «Игроки».

Бан в этой вкладке закрывает человека во всём проекте.
Считается только столбец banfull. Цепочка ban → mute его не заменяет.
"""
from __future__ import annotations


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


async def actor_has_banfull(user_id: int) -> bool:
    try:
        from bot.admins.mute import get_admin_account, get_staff_rule
    except Exception:
        return False
    try:
        account = await get_admin_account(int(user_id))
    except Exception:
        return False
    if not account or not account.role:
        return False
    try:
        rule = await get_staff_rule(account.role)
    except Exception:
        return False
    if not rule or not account.is_operational(rule):
        return False
    return column_granted(rule.permissions, "banfull")
