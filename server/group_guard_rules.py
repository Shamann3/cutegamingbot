"""Правила защиты официальной группы. Без базы и без Telegram."""
from __future__ import annotations

import re

LINK_RE = re.compile(r"(https?://|t\.me/|telegram\.me/)", re.I)
FLOOD_LIMIT = 6
FLOOD_WINDOW_SEC = 8.0
WARN_LIMIT = 3

def text_has_link(text: str | None) -> bool:
    return bool(LINK_RE.search(text or ""))


def entities_have_link(entities) -> bool:
    for item in entities or []:
        kind = getattr(item, "type", None)
        if kind is None and isinstance(item, dict):
            kind = item.get("type")
        name = str(kind or "").lower()
        if name in {"url", "text_link"} or name.endswith(".url") or name.endswith(".text_link"):
            return True
    return False


def flood_stamps(stamps: list[float], now: float, *, window: float = FLOOD_WINDOW_SEC) -> list[float]:
    fresh = [item for item in stamps if now - item <= window]
    fresh.append(now)
    return fresh[-12:]


def flood_tripped(stamps: list[float], *, limit: int = FLOOD_LIMIT) -> bool:
    return len(stamps) >= limit


def punish_receipt(position: str, action: str, warns: int | None) -> str:
    title = (position or "Администратор").strip() or "Администратор"
    names = {
        "mute": "Мут",
        "unmute": "Размут",
        "ban": "Бан",
        "unban": "Разбан",
        "kick": "Кик",
        "warn": "Варн",
    }
    act = names.get(action, "Наказание")
    line = f"{act} записан в архив официальной группы. Должность: {title}."
    if action == "warn" and warns is not None:
        line += f" Сейчас {int(warns)} из {WARN_LIMIT}."
        if int(warns) >= 2 and int(warns) < WARN_LIMIT:
            line += " Ещё одно предупреждение — бан."
        elif int(warns) >= WARN_LIMIT:
            line += " Лимит набран."
    return line


def effective_flags(*, custom: bool, links, flood, captcha, policy: dict) -> dict:
    """Своё правило группы важнее общего. Без своего — берётся общее."""
    if custom:
        return {"captcha": bool(captcha), "links": bool(links), "flood": bool(flood)}
    return {
        "captcha": bool(policy.get("captcha")),
        "links": bool(policy.get("links")),
        "flood": bool(policy.get("flood")),
    }


def morning_due(hour: int, *, enabled: bool, morning_hour: int) -> bool:
    if not enabled:
        return False
    slot = int(morning_hour)
    if slot < 0 or slot > 23:
        return False
    return int(hour) == slot


def morning_text(rows: list[dict]) -> str:
    lines = ["Смена официальных групп Кьюта."]
    for row in rows[:4]:
        title = row.get("title") or "Группа"
        today = row.get("today")
        yesterday = row.get("yesterday")
        close = int(row.get("close") or 0)
        today_s = "—" if today is None else str(int(today))
        y_s = "—" if yesterday is None else str(int(yesterday))
        lines.append(f"{title}: сегодня {today_s}, вчера {y_s}. На 2 из 3: {close}.")
    lines.append("Те же цифры на главной панели группы.")
    return "\n".join(lines)
