"""Наказание из панели сотрудника.

Право решают столбцы staff_rules с теми же запасными столбцами, что в боте:
что матрица включила роли, то сотрудник и выдаёт. Кабинет группы проверяет
должность, а здесь — только сотрудника проекта.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import punish_rights
import staff_rules
from human_actor import MACHINE_ADMIN_IDS

log = logging.getLogger("staff_punish")

# Короче 35 секунд Telegram считает ограничение вечным — как в кабинете группы.
MIN_HOLD_SEC = 35
MAX_HOLD_SEC = 366 * 24 * 3600

NO_DB = "База данных не подключена. Повторите через минуту."
NO_RULES = "Не удалось прочитать staff_rules из базы. Повторите через минуту."
NOT_STAFF = "Вы не сотрудник проекта"
NO_ROLE_RULES = "Для вашей должности не настроены права на наказания"
NOTHING_GRANTED = "Ваша должность пока не выдаёт наказаний. Их включает создатель проекта."
ON_LEAVE = "Учётная запись временно недоступна для модерации"
NOT_READY = "Учётная запись сейчас не готова к модерации"


class PunishRefused(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _pool():
    from db import db

    return db.pool


def _is_creator(user_id: int) -> bool:
    from admin_soft_restart import is_project_creator

    return bool(is_project_creator(int(user_id)))


async def _load_rules(pool):
    try:
        return await staff_rules.load(pool)
    except Exception as exc:
        log.warning("staff_rules read failed: %s", exc)
        raise PunishRefused(503, NO_RULES) from exc


async def actor_grants(actor_id: int, action: str) -> bool:
    """Это право сотрудника проекта. Должность в группе его не отменяет и не сужает.

    Голос и прочие действия кабинета, которых нет в панели сотрудника, сюда не входят.
    Создатель проекта в кабинете группы идёт своей дорогой, здесь для него False.
    """
    if punish_rights.staff_panel_action(action) is None:
        return False
    if _is_creator(int(actor_id)):
        return False
    pool = _pool()
    if pool is None:
        raise PunishRefused(503, NO_DB)
    account, rule, _rules_map, schema = await _actor_rule(pool, int(actor_id))
    if schema.problem:
        raise PunishRefused(503, schema.problem)
    if account_refusal(account, rule):
        return False
    return punish_rights.staff_allows(rule.permissions, action, schema.permission_columns)


async def staff_act_catalog(actor_id: int) -> list[dict[str, Any]]:
    """Наказания, которые сотрудник выдаёт поверх своей должности в группе."""
    try:
        if _is_creator(int(actor_id)) or _pool() is None:
            return []
        account, rule, _rules_map, schema = await _actor_rule(_pool(), int(actor_id))
    except PunishRefused:
        return []
    if schema.problem or account_refusal(account, rule):
        return []
    return punish_rights.staff_panel_actions(rule.permissions, schema.permission_columns)


def account_refusal(account, rule) -> Optional[str]:
    """Почему этот сотрудник сейчас не наказывает. None — может."""
    if account is None or not account.role:
        return NOT_STAFF
    if rule is None:
        return NO_ROLE_RULES
    if not account.is_operational(rule):
        return ON_LEAVE if account.availability_until else NOT_READY
    return None


async def official_groups() -> list[dict[str, Any]]:
    """Группы, где можно наказывать: те же, что бот считает официальными."""
    from admin_groups import official_chat_ids

    ids = list(dict.fromkeys(int(chat) for chat in await official_chat_ids()))
    titles: dict[int, str] = {}
    try:
        rows = await _pool().fetch(
            "SELECT chat_id, title FROM epsilon_official_groups WHERE is_official",
        )
        titles = {int(row["chat_id"]): str(row["title"] or "").strip() for row in rows}
    except Exception as exc:
        log.warning("official group titles unavailable: %s", exc)
    groups = [{"chatId": chat, "title": titles.get(chat) or f"Группа {chat}"} for chat in ids]
    groups.sort(key=lambda item: item["title"].lower())
    return groups


async def _actor_rule(pool, actor_id: int):
    rules_map, schema = await _load_rules(pool)
    try:
        account = await staff_rules.fetch_account(pool, int(actor_id))
    except Exception as exc:
        log.warning("admin account %s unavailable: %s", actor_id, exc)
        raise PunishRefused(503, NO_DB) from exc
    rule = rules_map.get(account.role.strip().lower()) if account and account.role else None
    return account, rule, rules_map, schema


async def punish_options(actor_id: int, *, preview_role: Optional[str] = None) -> dict[str, Any]:
    """Группы и наказания, которые этот сотрудник может выдать из панели.

    Создатель видит всё. С preview_role он видит панель глазами этой роли.
    """
    pool = _pool()
    if pool is None:
        raise PunishRefused(503, NO_DB)
    creator = _is_creator(actor_id)
    account, rule, rules_map, schema = await _actor_rule(pool, actor_id)
    groups = await official_groups()
    out: dict[str, Any] = {"groups": groups, "actions": [], "why": None, "preview": False}
    if schema.problem:
        out["why"] = schema.problem
        return out
    columns = schema.permission_columns
    if creator and preview_role:
        seen = rules_map.get(preview_role.strip().lower())
        out["preview"] = True
        out["actions"] = punish_rights.staff_panel_actions(seen.permissions, columns) if seen else []
        out["why"] = None if out["actions"] else NOTHING_GRANTED
        return out
    if creator:
        out["actions"] = punish_rights.staff_panel_actions({}, columns, creator=True)
        return out
    why = account_refusal(account, rule)
    if why:
        out["why"] = why
        return out
    out["actions"] = punish_rights.staff_panel_actions(rule.permissions, columns)
    out["why"] = None if out["actions"] else NOTHING_GRANTED
    return out


def telegram_refusal(result: dict[str, Any]) -> str:
    raw = str(result.get("telegram") or result.get("detail") or "").strip()
    low = raw.lower()
    if "administrator" in low or "owner" in low:
        return "Telegram не даёт наказать администратора этого чата"
    if "not enough rights" in low or "have no rights" in low:
        return "У бота в этой группе нет прав на это действие"
    if "user not found" in low or "participant_id_invalid" in low or "user_id_invalid" in low:
        return "Telegram не нашёл этого человека"
    if "chat not found" in low:
        return "Бот не видит эту группу"
    return f"Telegram отказал: {raw}" if raw else "Telegram не принял наказание"


async def punish(
    actor_id: int,
    *,
    chat_id: int,
    user_id: int,
    action: str,
    until_sec: Optional[int],
    reason: str,
) -> dict[str, Any]:
    item = punish_rights.staff_panel_action(action)
    if item is None:
        raise PunishRefused(400, "Такого наказания в панели нет")
    key = item["id"]
    lift = key in punish_rights.LIFT_ACTIONS
    text = " ".join((reason or "").split())
    if len(text) < 2:
        raise PunishRefused(400, "Напишите причину")
    pool = _pool()
    if pool is None:
        raise PunishRefused(503, NO_DB)

    if not _is_creator(actor_id):
        account, rule, _rules_map, schema = await _actor_rule(pool, actor_id)
        if schema.problem:
            raise PunishRefused(409, schema.problem)
        why = account_refusal(account, rule)
        if why:
            raise PunishRefused(403, why)
        if not punish_rights.staff_allows(rule.permissions, key, schema.permission_columns):
            raise PunishRefused(403, f"Должность «{rule.title}» не даёт права: {item['label'].lower()}")

    target = int(user_id)
    if target == int(actor_id):
        raise PunishRefused(400, "Снять наказание с самого себя нельзя" if lift else punish_rights.SELF_BLOCK)
    if target in punish_rights.PROTECTED_CREATOR_IDS or _is_creator(target):
        raise PunishRefused(403, punish_rights.PROTECTED_BLOCK)
    if target in MACHINE_ADMIN_IDS:
        raise PunishRefused(400, "Бота проекта наказать нельзя")

    groups = await official_groups()
    group = next((g for g in groups if int(g["chatId"]) == int(chat_id)), None)
    if group is None:
        raise PunishRefused(400, "Эта группа не отмечена официальной")

    hold: Optional[int] = None
    if item["needsUntil"]:
        if until_sec is None or not 0 < int(until_sec) <= MAX_HOLD_SEC:
            raise PunishRefused(400, "Укажите срок больше нуля и не дольше 366 дней")
        hold = max(MIN_HOLD_SEC, int(until_sec))

    from admin_groups import moderate_action

    result = await moderate_action(
        chat_id=int(group["chatId"]),
        user_id=target,
        action=key,
        until_sec=hold,
        reason=text,
        admin_id=int(actor_id),
    )
    if not result.get("ok"):
        raise PunishRefused(400, telegram_refusal(result))
    return {
        "ok": True,
        "action": key,
        "label": item["label"],
        "scope": item["scope"],
        "chatId": group["chatId"],
        "chatTitle": group["title"],
        "untilSec": hold,
    }
