"""Наказание за серию ошибок капчи. Одно на все официальные группы."""
from __future__ import annotations

from db import db

from group_realm import telegram_hold_seconds

PENALTIES = (
    ("mute", "Мут", "Этот чат", "Человек не может писать в группе, где ошибся.", True),
    ("ban", "Бан", "Этот чат", "Человек не может вернуться в эту группу, пока срок не кончится.", True),
    ("warn", "Варн", "Этот чат", "Предупреждение записывается в этом чате.", True),
    ("kick", "Кик", "Этот чат", "Человека убирают из этой группы. Срок не нужен.", False),
    ("voice", "Голос", "Этот чат", "В этой группе нельзя отправлять голосовые и кружки.", True),
    ("muteall", "Муталл", "Все официальные группы", "Мут в каждой официальной группе.", True),
    ("kickall", "Кикалл", "Все официальные группы", "Кик из каждой официальной группы.", False),
    ("warnall", "Варналл", "Все официальные группы", "Предупреждение во всех официальных группах.", True),
    ("banall", "Баналл", "Все официальные группы", "Бан в каждой официальной группе. Это ещё не бан всего проекта.", True),
    ("warnfull", "Варнфулл", "Весь проект", "Предупреждение на весь проект.", True),
    ("banfull", "Банфулл", "Весь проект", "Бан во всех официальных группах и блокировка во всём проекте.", True),
)

_BY_ID = {item[0]: item for item in PENALTIES}
_READY = False


def penalty_cards() -> list[dict]:
    return [
        {"id": key, "label": label, "place": place, "hint": hint, "needsUntil": needs}
        for key, label, place, hint, needs in PENALTIES
    ]


def penalty_needs_until(action: str) -> bool:
    item = _BY_ID.get((action or "").strip().lower())
    return bool(item and item[4])


def clean_penalty(raw: dict | None) -> dict:
    """Правило, которое можно сохранить. Пустое действие выключает наказание."""
    data = raw or {}
    action = str(data.get("action") or "").strip().lower()
    if action not in _BY_ID:
        action = ""
    try:
        strikes = int(data.get("strikes") or 5)
    except (TypeError, ValueError):
        strikes = 5
    strikes = max(1, min(20, strikes))
    seconds = telegram_hold_seconds(data.get("seconds")) if penalty_needs_until(action) else 0
    enabled = bool(data.get("enabled")) and bool(action)
    return {
        "enabled": enabled,
        "strikes": strikes,
        "action": action or "mute",
        "seconds": seconds,
    }


def penalty_fires(attempts: int, policy: dict | None, *, already: bool = False) -> bool:
    """Один раз, когда подряд ошибок стало не меньше порога."""
    rule = policy or {}
    if already or not rule.get("enabled"):
        return False
    action = str(rule.get("action") or "")
    if action not in _BY_ID:
        return False
    try:
        strikes = int(rule.get("strikes") or 0)
        count = int(attempts or 0)
    except (TypeError, ValueError):
        return False
    return strikes >= 1 and count >= strikes


def _span_text(seconds: int) -> str:
    n = int(seconds or 0)
    if n <= 0:
        return "навсегда"
    parts = []
    days, rem = divmod(n, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    for value, one, few, many in (
        (days, "день", "дня", "дней"),
        (hours, "час", "часа", "часов"),
        (minutes, "минута", "минуты", "минут"),
        (secs, "секунда", "секунды", "секунд"),
    ):
        if not value:
            continue
        tail = value % 100
        digit = value % 10
        if digit == 1 and tail != 11:
            word = one
        elif digit in (2, 3, 4) and tail not in (12, 13, 14):
            word = few
        else:
            word = many
        parts.append(f"{value} {word}")
    return " ".join(parts) or "навсегда"


def penalty_sentence(policy: dict | None) -> str:
    rule = clean_penalty(policy)
    if not (policy or {}).get("enabled"):
        return "Наказание выключено. Ошибки капчи только меняют карточку."
    item = _BY_ID.get(rule["action"])
    if not item:
        return "Наказание выключено. Ошибки капчи только меняют карточку."
    label, place = item[1], item[2]
    head = f"После {rule['strikes']} ошибок подряд — {label.lower()}. {place}."
    if item[4]:
        return f"{head} Срок: {_span_text(rule['seconds'])}."
    return head


async def ensure_penalty_table() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_captcha_penalty (
            id INT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            strikes INT NOT NULL DEFAULT 5,
            action TEXT NOT NULL DEFAULT 'mute',
            seconds INT NOT NULL DEFAULT 3600
        )
        """
    )
    await db.pool.execute(
        "INSERT INTO epsilon_captcha_penalty (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
    )
    _READY = True


def _from_row(row) -> dict:
    if not row:
        stored = {"enabled": False, "strikes": 5, "action": "mute", "seconds": 3600}
    else:
        stored = {
            "enabled": bool(row["enabled"]),
            "strikes": int(row["strikes"] or 5),
            "action": row["action"] or "mute",
            "seconds": int(row["seconds"] or 0),
        }
    clean = clean_penalty(stored)
    clean["enabled"] = bool(stored["enabled"]) and clean["action"] in _BY_ID
    return {
        **clean,
        "cards": penalty_cards(),
        "sentence": penalty_sentence({**clean, "enabled": clean["enabled"]}),
    }


async def load_penalty() -> dict:
    await ensure_penalty_table()
    row = await db.pool.fetchrow(
        "SELECT enabled, strikes, action, seconds FROM epsilon_captcha_penalty WHERE id = 1"
    )
    return _from_row(row)


async def save_penalty(raw: dict) -> dict:
    await ensure_penalty_table()
    clean = clean_penalty(raw)
    if raw.get("enabled") and not str(raw.get("action") or "").strip():
        raise ValueError("Выберите наказание")
    if raw.get("enabled"):
        clean["enabled"] = True
    await db.pool.execute(
        """
        INSERT INTO epsilon_captcha_penalty (id, enabled, strikes, action, seconds)
        VALUES (1, $1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
            enabled = EXCLUDED.enabled,
            strikes = EXCLUDED.strikes,
            action = EXCLUDED.action,
            seconds = EXCLUDED.seconds
        """,
        clean["enabled"],
        clean["strikes"],
        clean["action"],
        clean["seconds"],
    )
    return await load_penalty()
