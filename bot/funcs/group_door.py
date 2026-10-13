# -*- coding: utf-8 -*-
"""Открытый вход в группу с балансом.

Положить куты можно всегда. Снять и играть можно, когда группа
публичная и заявки на вступление выключены. Если вход закрыт три
дня подряд и предупреждение уже дошло, куты уходят в технические
группы. Новое пополнение не обнуляет уже идущий срок.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

GRACE = timedelta(days=3)
DAY = timedelta(days=1)

# Лица, которые прислал создатель. Новые id сюда не придумываем.
FACE = {
    "now": ("5355076502960520182", "⚫️"),
    "rule": ("5355148005576058505", "⚫️"),
    "keep": ("5357287178462346359", "⚫️"),
    "warn": ("5357421327470866510", "⚫️"),
    "day": ("5357319626940261522", "⚫️"),
    "play": ("5357162761849717032", "⚫️"),
}

_CACHE: dict[int, tuple[float, dict]] = {}
_CACHE_SEC = 90
_started = False
_sweep_after: int | None = None
SWEEP_PAGE = 400


def mark(key: str) -> str:
    eid, face = FACE[key]
    return f"<tg-emoji emoji-id='{eid}'>{face}</tg-emoji>"


def public_username(value) -> str | None:
    text = str(value or "").strip()
    if text.startswith("@"):
        text = text[1:].strip()
    if len(text) < 4:
        return None
    if text.casefold() in {"username отсутствует", "none", "null"}:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]+", text):
        return None
    return text


def classify_door(username, join_by_request: bool) -> dict:
    reasons = []
    if not public_username(username):
        reasons.append("private")
    if join_by_request:
        reasons.append("requests")
    return {"open": not reasons, "reasons": reasons, "username": public_username(username)}


def human_left(delta: timedelta) -> str:
    seconds = max(0, int(delta.total_seconds()))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    if days >= 2:
        word = "дня" if days in (2, 3, 4) else "дней"
        return f"{days} {word}"
    if days == 1:
        return "1 день"
    if hours >= 5:
        return f"{hours} часов"
    if hours >= 2:
        return f"{hours} часа"
    if hours == 1:
        return "1 час"
    return "меньше часа"


def next_step(elapsed: timedelta, warned: int, told: bool) -> str | None:
    if not told or warned < 1:
        return "start"
    if elapsed >= GRACE and warned >= 1 and told:
        return "seize"
    if elapsed >= DAY * 2 and warned < 3:
        return "day2"
    if elapsed >= DAY and warned < 2:
        return "day1"
    return None


def may_seize(told: bool, elapsed: timedelta) -> bool:
    return bool(told) and elapsed >= GRACE


def split_pots(amount: int, tills: list[int]) -> list[tuple[int, int]]:
    amount = int(amount)
    tills = [int(item) for item in tills]
    if amount <= 0 or not tills:
        return []
    base, extra = divmod(amount, len(tills))
    out = []
    for index, till in enumerate(tills):
        part = base + (1 if index < extra else 0)
        if part > 0:
            out.append((till, part))
    return out


def dots(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return str(value)


def action_blocked(kind: str) -> bool:
    """Пополнить можно при закрытом входе. Снять и играть — нет."""
    return kind in {"play", "withdraw"}


def sweep_batch(due: list[int], page: list[int], page_size: int) -> tuple[list[int], bool]:
    """Сначала уже идущие сроки, потом следующая страница всех балансов.

    Короткая страница означает, что круг закончился и следующий начнётся сначала.
    """
    seen: list[int] = []
    have: set[int] = set()
    for cid in list(due) + list(page):
        cid = int(cid)
        if cid in have:
            continue
        have.add(cid)
        seen.append(cid)
    return seen, len(page) < int(page_size)


def why_lines(reasons: list[str]) -> str:
    lines = []
    if "requests" in reasons:
        lines.append(
            f"{mark('rule')} <b>Включены заявки на вступление. "
            f"Другие пользователи не смогут зайти в эту группу. "
            f"Это нарушает правила содержания группы</b>"
        )
    if "private" in reasons:
        lines.append(
            f"{mark('rule')} <b>Группа является приватной. "
            f"Группа закрыта для тех, кто в ней не состоит. "
            f"Это нарушает правила содержания группы</b>"
        )
    return "\n".join(lines)


def steps_line() -> str:
    return (
        f"{mark('keep')} <b>Для того чтобы сохранить ваши куты на балансе группы - "
        f"группа должна быть публичной и должны отсутствовать заявки на вступления</b>"
    )


def warn_block() -> str:
    return (
        f"{mark('warn')} <b>Если через 3 дня требования для свободного входа в вашу группу "
        f"будет всё ещё закрыт - куты с вашего баланса группы уйдут в технические группы проекта. "
        f"Система напишет вам когда останется 2 дня до снятия кут, и ещё раз за сутки.</b>\n"
        f"<blockquote><b>Это сообщение - предупреждение</b></blockquote>"
    )


def start_text(reasons: list[str], amount: int) -> str:
    return (
        f"{mark('now')} Сейчас в этой группе <b>{dots(amount)} кут.</b> "
        f"Снять их и играть на них можно, пока в группу может войти кто угодно.\n\n"
        f"{why_lines(reasons)}\n\n"
        f"{steps_line()}\n"
        f"{warn_block()}"
    )


def day1_text(reasons: list[str], amount: int) -> str:
    return (
        f"{mark('day')} <b>На балансе группы ещё {dots(amount)} кут. "
        f"Осталось 2 дня до их изъятия. в случае не выполнения нужных требований "
        f"для свободного входа в других пользователей в группу.</b>\n"
        f"{why_lines(reasons)}\n"
        f"{steps_line()}"
    )


def day2_text(reasons: list[str], amount: int) -> str:
    return (
        f"{mark('warn')} <b>Остались сутки. На балансе группы {dots(amount)} кут. "
        f"Завтра они уйдут в технические группы проекта, если требования для свободного входа "
        f"всё ещё не будут выполнены. Новые куты, положенные сегодня, уйдут вместе с ними: "
        f"срок заново не начинается.</b>\n"
        f"{why_lines(reasons)}\n"
        f"{steps_line()}\n"
        f"<blockquote><b>После перевода вернуть эту сумму сюда нельзя</b></blockquote>"
    )


def seize_text(reasons: list[str], amount: int, since: datetime | None, warned: int = 1) -> str:
    when = ""
    if since is not None:
        stamp = since.astimezone(timezone.utc).strftime("%d.%m")
        when = f" Срок шёл с {stamp}."
    reason = "включены заявки на вступление" if reasons == ["requests"] else (
        "группа является приватной" if reasons == ["private"] else
        "группа приватная и включены заявки на вступление"
    )
    sent = ["в начале срока"]
    if warned >= 2:
        sent.append("через сутки")
    if warned >= 3:
        sent.append("за сутки до перевода")
    history = "Предупреждение уже стояло в чате: " + sent[0] + "."
    if len(sent) > 1:
        history = "Предупреждения уже стояли в чате: " + ", ".join(sent) + "."
    return (
        f"{mark('now')} <b>{dots(amount)} кут с баланса группы переведены в технические группы.</b>\n\n"
        f"Три дня требования для свободного входа не выполнялись: {reason}.{when}\n"
        f"{history}\n\n"
        f"{steps_line()}\n"
        f"<b>Новые куты на закрытый баланс снова получат три дня и те же предупреждения. "
        f"Положить их можно. Снять и играть можно, только когда в группу сможет войти кто угодно.</b>"
    )


def recovered_text(username: str | None) -> str:
    name = f"@{username}" if username else "публичное имя"
    return (
        f"{mark('keep')} <b>Вход открыт. Куты остаются в группе.</b>\n"
        f"{name} на месте, заявки на вступление выключены. Срок снят. Снять и играть снова можно."
    )


def clock_line(amount: int, left: str) -> str:
    if int(amount or 0) <= 0:
        return ""
    return (
        f"\n{mark('warn')} <b>На балансе {dots(amount)} кут. "
        f"Если требования не выполнят, через {left} они уйдут в технические группы.</b>"
    )


def block_text(kind: str, reasons: list[str], amount: int, left: str) -> str:
    if kind == "withdraw":
        lead = (
            f"<b>{mark('keep')} Снять куты с баланса группы сейчас нельзя. "
            f"из-за невыполнений правил по содержанию группы</b>"
        )
    else:
        lead = (
            f"{mark('play')} <b>Играть в этой группе сейчас нельзя "
            f"из-за невыполнений правил по содержанию группы создателем</b>"
        )
    return (
        f"{lead}\n"
        f"{why_lines(reasons)}\n"
        f"{steps_line()}"
        f"{clock_line(amount, left)}\n"
        f"Положить куты на баланс по-прежнему можно."
    )


def banner_html(reasons: list[str], amount: int, left: str) -> str:
    return (
        f"{mark('now')} Сейчас в этой группе <b>{dots(amount)} кут.</b> "
        f"Снять их и играть на них можно, пока в группу может войти кто угодно.\n"
        f"{why_lines(reasons)}\n"
        f"{steps_line()}\n"
        f"{mark('warn')} <b>До изъятия осталось {left}.</b>\n"
        f"<blockquote><b>Это сообщение - предупреждение</b></blockquote>"
    )


def deposit_note(reasons: list[str], amount: int, left: str) -> str:
    return (
        f"{mark('now')} <b>Куты легли на баланс. Срок не начался заново: "
        f"до изъятия осталось {left}. На балансе сейчас {dots(amount)} кут.</b>\n"
        f"{why_lines(reasons)}\n"
        f"{steps_line()}\n"
        f"{mark('play')} <b>Снять и играть сейчас нельзя. "
        f"Положить ещё можно, срок от этого не сдвинется.</b>"
    )


def protected_ids() -> set[int]:
    """Кассы проекта. Тестовая группа сюда не входит: на ней проверяют вход."""
    from server.py.cases.design import fund_ids
    ids = {int(item) for item in fund_ids()}
    try:
        from bot.config.config import TECHNICAL_CHAT_IDS, test_id
        ids.update(int(item) for item in TECHNICAL_CHAT_IDS)
        ids.discard(int(test_id))
    except Exception:
        pass
    return ids


def _reasons(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part for part in str(raw).split(",") if part in {"private", "requests"}]


async def ensure_table(db) -> None:
    async with db.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_door (
                chat_id BIGINT PRIMARY KEY,
                bad_since TIMESTAMPTZ,
                reason TEXT,
                warned INTEGER NOT NULL DEFAULT 0,
                told BOOLEAN NOT NULL DEFAULT FALSE,
                seized_at TIMESTAMPTZ
            )
            """
        )


async def read_door(bot, chat_id: int, *, fresh: bool = False) -> dict:
    now = asyncio.get_running_loop().time()
    cached = _CACHE.get(int(chat_id))
    if not fresh and cached and now - cached[0] < _CACHE_SEC:
        return dict(cached[1])
    try:
        chat = await asyncio.wait_for(bot.get_chat(int(chat_id)), timeout=4)
    except Exception as exc:
        print(f"[DOOR] getChat fail chat={chat_id} {type(exc).__name__}")
        return {"known": False, "open": True, "reasons": [], "username": None, "title": ""}
    username = getattr(chat, "username", None)
    requests = bool(getattr(chat, "join_by_request", False))
    door = classify_door(username, requests)
    door["known"] = True
    door["title"] = str(getattr(chat, "title", "") or "")
    _CACHE[int(chat_id)] = (now, dict(door))
    if not door["open"]:
        print(f"[DOOR] closed chat={chat_id} reasons={','.join(door['reasons'])}")
    return door


async def _row(db, chat_id: int):
    async with db.acquire() as conn:
        return await conn.fetchrow(
            "SELECT chat_id, bad_since, reason, warned, told, seized_at FROM group_door WHERE chat_id = $1",
            int(chat_id),
        )


async def _balance(db, chat_id: int) -> int:
    async with db.acquire() as conn:
        value = await conn.fetchval(
            "SELECT COALESCE(chatbalance, 0) FROM chat WHERE chat_id = $1",
            int(chat_id),
        )
    return int(value or 0)


def _left_from(since: datetime | None) -> str:
    if since is None:
        return human_left(GRACE)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return human_left(GRACE - (datetime.now(timezone.utc) - since))


async def mark_told(db, chat_id: int, warned: int) -> bool:
    """True, если предупреждение засчитано впервые."""
    async with db.acquire() as conn:
        fresh = await conn.fetchval(
            """
            UPDATE group_door
            SET told = TRUE, warned = GREATEST(warned, $2)
            WHERE chat_id = $1 AND told = FALSE
            RETURNING chat_id
            """,
            int(chat_id), int(warned),
        )
        if fresh:
            return True
        await conn.execute(
            "UPDATE group_door SET warned = GREATEST(warned, $2) WHERE chat_id = $1",
            int(chat_id), int(warned),
        )
        return False


async def dm_creator(bot, db, chat_id: int, text: str) -> bool:
    try:
        creator = await db.get_creator_id(int(chat_id))
    except Exception:
        return False
    if not creator or int(creator) == int(chat_id):
        return False
    return await _say(bot, int(creator), text)


async def sync(bot, db, chat_id: int, *, fresh: bool = False, announce: bool = False) -> dict:
    await ensure_table(db)
    chat_id = int(chat_id)
    if chat_id in protected_ids():
        return {"known": True, "open": True, "reasons": [], "amount": 0, "left": "", "step": None}
    door = await read_door(bot, chat_id, fresh=fresh)
    if not door.get("known"):
        door.update(amount=0, left="", step=None, notice="")
        return door
    if door.get("open"):
        row = await _row(db, chat_id)
        notice = ""
        if row and row["bad_since"] and int(row["warned"] or 0) > 0:
            notice = recovered_text(door.get("username"))
            if announce:
                await _send(bot, db, chat_id, notice)
        if row:
            async with db.acquire() as conn:
                await conn.execute("DELETE FROM group_door WHERE chat_id = $1", chat_id)
        door.update(amount=0, left="", step=None, notice=notice if not announce else "")
        return door
    amount = await _balance(db, chat_id)
    door["amount"] = amount
    if amount <= 0:
        async with db.acquire() as conn:
            await conn.execute("DELETE FROM group_door WHERE chat_id = $1 AND seized_at IS NULL", chat_id)
        door.update(left="", step=None)
        return door
    reason = ",".join(door.get("reasons") or [])
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO group_door (chat_id, bad_since, reason, warned, told)
            VALUES ($1, NOW(), $2, 0, FALSE)
            ON CONFLICT (chat_id) DO UPDATE
            SET reason = EXCLUDED.reason,
                bad_since = COALESCE(group_door.bad_since, NOW()),
                seized_at = NULL,
                warned = CASE WHEN group_door.bad_since IS NULL THEN 0 ELSE group_door.warned END,
                told = CASE WHEN group_door.bad_since IS NULL THEN FALSE ELSE group_door.told END
            """,
            chat_id, reason,
        )
    row = await _row(db, chat_id)
    since = row["bad_since"] if row else datetime.now(timezone.utc)
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - since
    warned = int(row["warned"] or 0) if row else 0
    told = bool(row["told"]) if row else False
    step = next_step(elapsed, warned, told)
    if step == "seize" and not may_seize(told, elapsed):
        step = "start"
    door.update(left=_left_from(since), step=step, since=since, told=told, warned=warned)
    if announce and step:
        await _announce(bot, db, chat_id, door, step)
    return door


async def _announce(bot, db, chat_id: int, door: dict, step: str) -> bool:
    amount = int(door.get("amount") or 0)
    reasons = list(door.get("reasons") or [])
    if step == "start":
        text = start_text(reasons, amount)
        warned = 1
    elif step == "day1":
        text = day1_text(reasons, amount)
        warned = 2
    elif step == "day2":
        text = day2_text(reasons, amount)
        warned = 3
    elif step == "seize":
        return await _seize(bot, db, chat_id, door)
    else:
        return False
    ok = await _send(bot, db, chat_id, text)
    if ok:
        await mark_told(db, chat_id, warned)
    return ok


async def _send(bot, db, chat_id: int, text: str) -> bool:
    group_ok = await _say(bot, int(chat_id), text)
    dm_ok = False
    try:
        creator = await db.get_creator_id(int(chat_id))
        if creator:
            title = ""
            try:
                title = str((await read_door(bot, chat_id)).get("title") or "")
            except Exception:
                title = ""
            head = f"{mark('now')} <b>{title or 'Группа'}</b>\n" if title else ""
            dm_ok = await _say(bot, int(creator), head + text)
    except Exception as exc:
        print(f"[DOOR] dm fail chat={chat_id} {type(exc).__name__}")
    return bool(group_ok or dm_ok)


async def _say(bot, chat_id: int, text: str) -> bool:
    try:
        from bot.funcs.group_balance_level import strip_tg_emoji
        await bot.send_message(int(chat_id), text, parse_mode="HTML", disable_web_page_preview=True)
        return True
    except Exception as exc:
        err = str(exc)
        if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
            try:
                await bot.send_message(
                    int(chat_id), strip_tg_emoji(text),
                    parse_mode="HTML", disable_web_page_preview=True,
                )
                return True
            except Exception as second:
                print(f"[DOOR] send fail chat={chat_id} {type(second).__name__}")
                return False
        print(f"[DOOR] send fail chat={chat_id} {type(exc).__name__}")
        return False


async def _seize(bot, db, chat_id: int, door: dict) -> bool:
    amount = int(door.get("amount") or 0)
    if amount <= 0:
        return False
    row = await _row(db, chat_id)
    if not row or not row["told"]:
        return False
    since = row["bad_since"]
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if since is None or datetime.now(timezone.utc) - since < GRACE:
        return False
    from server.py.cases.design import fund_ids
    ordered = [int(item) for item in fund_ids() if int(item) != int(chat_id)]
    parts = split_pots(amount, ordered)
    if not parts:
        return False
    snap = await db.update_chat_balance_minus(chat_id, amount)
    if snap is None:
        print(f"[DOOR] seize skipped chat={chat_id} amount={amount}")
        return False
    credited = []
    try:
        for till, part in parts:
            ok = await db.update_chat_balance(bot, till, part)
            if not ok:
                raise RuntimeError(f"credit {till}")
            credited.append((till, part))
    except Exception as exc:
        print(f"[DOOR] seize refund chat={chat_id} {type(exc).__name__}")
        await db.update_chat_balance(bot, chat_id, amount)
        for till, part in credited:
            try:
                await db.update_chat_balance_minus(till, part)
            except Exception:
                pass
        return False
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE group_door
            SET seized_at = NOW(), warned = 4, told = TRUE, bad_since = NULL
            WHERE chat_id = $1
            """,
            int(chat_id),
        )
    _CACHE.pop(int(chat_id), None)
    text = seize_text(
        list(door.get("reasons") or _reasons(row["reason"])),
        amount,
        since,
        int(row["warned"] or 1),
    )
    await _send(bot, db, chat_id, text)
    print(f"[DOOR] seized chat={chat_id} amount={amount}")
    return True


async def guard_action(message, kind: str) -> bool:
    """True — действие останавливаем и человек уже видит, что сделать."""
    if not action_blocked(kind):
        return False
    chat = getattr(message, "chat", None)
    if chat is None or str(getattr(chat, "type", "") or "") == "private":
        return False
    chat_id = int(chat.id)
    if chat_id in protected_ids():
        return False
    bot = getattr(message, "bot", None)
    if bot is None:
        from main import bot1 as bot
    from main import db
    try:
        door = await sync(bot, db, chat_id, announce=False)
    except Exception as exc:
        print(f"[DOOR] guard fail chat={chat_id} {type(exc).__name__}")
        return False
    if not door.get("known") or door.get("open"):
        if door.get("notice"):
            try:
                await message.reply(door["notice"], parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                pass
        return False
    text = block_text(kind, list(door.get("reasons") or []), int(door.get("amount") or 0), door.get("left") or human_left(GRACE))
    try:
        await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
        if await mark_told(db, chat_id, max(1, int(door.get("warned") or 0))):
            await dm_creator(bot, db, chat_id, text)
        return True
    except Exception as exc:
        err = str(exc)
        if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
            from bot.funcs.group_balance_level import strip_tg_emoji
            try:
                await message.reply(strip_tg_emoji(text), parse_mode="HTML", disable_web_page_preview=True)
                if await mark_told(db, chat_id, max(1, int(door.get("warned") or 0))):
                    await dm_creator(bot, db, chat_id, text)
                return True
            except Exception as second:
                print(f"[DOOR] reply fail {type(second).__name__}")
                return False
        print(f"[DOOR] reply fail {type(exc).__name__}")
        return False


async def after_deposit(message) -> None:
    """После зачисления: если вход закрыт, человек сразу видит срок.

    Первое пополнение запускает предупреждение. Следующие не сдвигают срок
    и получают короткую записку, что эти куты уйдут вместе с уже лежащими.
    """
    chat = getattr(message, "chat", None)
    if chat is None or str(getattr(chat, "type", "") or "") == "private":
        return
    chat_id = int(chat.id)
    if chat_id in protected_ids():
        return
    bot = getattr(message, "bot", None)
    if bot is None:
        from main import bot1 as bot
    from main import db
    try:
        door = await sync(bot, db, chat_id, fresh=True, announce=True)
    except Exception as exc:
        print(f"[DOOR] deposit note fail chat={chat_id} {type(exc).__name__}")
        return
    if door.get("notice"):
        return
    if not door.get("known") or door.get("open") or door.get("step"):
        return
    if int(door.get("amount") or 0) <= 0:
        return
    text = deposit_note(
        list(door.get("reasons") or []),
        int(door["amount"]),
        door.get("left") or human_left(GRACE),
    )
    try:
        await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        err = str(exc)
        if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
            from bot.funcs.group_balance_level import strip_tg_emoji
            try:
                await message.reply(strip_tg_emoji(text), parse_mode="HTML", disable_web_page_preview=True)
            except Exception as second:
                print(f"[DOOR] deposit reply fail {type(second).__name__}")
        else:
            print(f"[DOOR] deposit reply fail {type(exc).__name__}")


async def screen_banner(bot, db, chat_id: int) -> str:
    try:
        door = await sync(bot, db, int(chat_id), announce=False)
    except Exception as exc:
        print(f"[DOOR] banner fail {type(exc).__name__}")
        return ""
    if door.get("notice"):
        return door["notice"]
    if not door.get("known") or door.get("open") or int(door.get("amount") or 0) <= 0:
        return ""
    text = banner_html(list(door.get("reasons") or []), int(door["amount"]), door.get("left") or human_left(GRACE))
    return text


async def sweep(bot, db) -> None:
    global _sweep_after
    await ensure_table(db)
    skip = list(protected_ids())
    async with db.acquire() as conn:
        due = await conn.fetch(
            """
            SELECT g.chat_id
            FROM group_door g
            JOIN chat c ON c.chat_id = g.chat_id
            WHERE g.bad_since IS NOT NULL
              AND COALESCE(c.chatbalance, 0) > 0
              AND NOT (g.chat_id = ANY($1::bigint[]))
            """,
            skip,
        )
        page = await conn.fetch(
            """
            SELECT chat_id
            FROM chat
            WHERE COALESCE(chatbalance, 0) > 0
              AND ($2::bigint IS NULL OR chat_id > $2)
              AND NOT (chat_id = ANY($1::bigint[]))
            ORDER BY chat_id
            LIMIT $3
            """,
            skip, _sweep_after, SWEEP_PAGE,
        )
    ids, wrapped = sweep_batch(
        [int(row["chat_id"]) for row in due],
        [int(row["chat_id"]) for row in page],
        SWEEP_PAGE,
    )
    if wrapped or not page:
        _sweep_after = None
    else:
        _sweep_after = int(page[-1]["chat_id"])
    for chat_id in ids:
        try:
            await sync(bot, db, chat_id, fresh=True, announce=True)
        except Exception as exc:
            print(f"[DOOR] sweep chat={chat_id} {type(exc).__name__}")
        await asyncio.sleep(0.35)


def start(bot) -> None:
    global _started
    if _started:
        return
    _started = True

    async def _loop():
        await asyncio.sleep(45)
        from main import db
        while True:
            try:
                await sweep(bot, db)
            except Exception as exc:
                print(f"[DOOR] loop {type(exc).__name__}")
            await asyncio.sleep(20 * 60)

    asyncio.create_task(_loop())
