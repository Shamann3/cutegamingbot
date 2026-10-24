"""Вызов состава: точное «админы» и /report с пингом.

«админы» открывает список только когда в сообщении нет других слов.
/report (текст по желанию) отвечает на это сообщение и упоминает
администраторов этой группы и сотрудников проекта.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from aiogram.types import Message, MessageEntity, User

_REPORT_PAUSE_SEC = 45
_MENTIONS_PER_MESSAGE = 25
_NOTE_LIMIT = 300
_last_report: Dict[Tuple[int, int], float] = {}


def _head(text: str) -> str:
    parts = (text or "").split()
    if not parts:
        return ""
    return parts[0].split("@", 1)[0].lower().replace("ё", "е")


def is_exact_admins(text: str) -> bool:
    """True только для «админы» или «/админы», без хвоста."""
    raw = (text or "").strip()
    if not raw or len(raw.split()) != 1:
        return False
    return _head(raw) in {"админы", "/админы"}


def report_note(text: str) -> Optional[str]:
    """Текст после /report. None — это не репорт. Пустая строка — репорт без текста."""
    raw = (text or "").strip()
    if not raw:
        return None
    parts = raw.split(maxsplit=1)
    if _head(parts[0]) != "/report":
        return None
    if len(parts) == 1:
        return ""
    return parts[1].strip()[:_NOTE_LIMIT]


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _label(name: str, fallback: str) -> str:
    clean = " ".join((name or "").split())
    if not clean:
        clean = fallback
    return clean[:32]


def mention_chunks(
    people: List[Tuple[int, str]],
    *,
    note: str,
) -> List[Tuple[str, List[MessageEntity]]]:
    """Сообщения с text_mention: Telegram зовёт человека даже без @username."""
    header = "Нужна помощь"
    if note:
        header = f"{header}\n{note}"
    header = f"{header}\n\n"
    chunks: List[Tuple[str, List[MessageEntity]]] = []
    batch = people[: _MENTIONS_PER_MESSAGE * 4]
    for start in range(0, len(batch), _MENTIONS_PER_MESSAGE):
        piece = batch[start:start + _MENTIONS_PER_MESSAGE]
        if start == 0:
            text = header
        else:
            text = "Ещё:\n"
        entities: List[MessageEntity] = []
        for index, (uid, name) in enumerate(piece):
            if index:
                text += " "
            label = _label(name, "сотрудник")
            offset = _utf16_len(text)
            text += label
            entities.append(MessageEntity(
                type="text_mention",
                offset=offset,
                length=_utf16_len(label),
                user=User(id=int(uid), is_bot=False, first_name=label[:64] or "сотрудник"),
            ))
        chunks.append((text, entities))
    return chunks


def _remember(chat_id: int, user_id: int, now: float) -> bool:
    """False, если этот человек уже звал состав в этом чате недавно."""
    key = (int(chat_id), int(user_id))
    prev = _last_report.get(key, 0.0)
    if now - prev < _REPORT_PAUSE_SEC:
        return False
    _last_report[key] = now
    if len(_last_report) > 400:
        cutoff = now - _REPORT_PAUSE_SEC
        stale = [k for k, ts in _last_report.items() if ts < cutoff]
        for k in stale:
            _last_report.pop(k, None)
    return True


async def _targets(chat_id: int, author_id: Optional[int]) -> List[Tuple[int, str]]:
    from bot.admins.mute import _db

    pool = _db().pool
    if pool is None:
        return []
    found: Dict[int, str] = {}
    async with pool.acquire() as conn:
        seats = await conn.fetch(
            """
            SELECT s.user_id,
                   COALESCE(
                     NULLIF(BTRIM(u.display_name), ''),
                     NULLIF(BTRIM(u.first_name), ''),
                     'админ'
                   ) AS name
            FROM epsilon_seats s
            LEFT JOIN users u ON u.user_id = s.user_id
            WHERE s.chat_id = $1 AND s.user_id IS NOT NULL
            """,
            int(chat_id),
        )
        for row in seats:
            uid = int(row["user_id"])
            if uid > 0:
                found.setdefault(uid, row["name"] or "админ")
        try:
            owner = await conn.fetchrow(
                "SELECT creator_id FROM chat WHERE chat_id = $1",
                int(chat_id),
            )
        except Exception:
            owner = None
        if owner and owner["creator_id"]:
            cid = int(owner["creator_id"])
            if cid > 0:
                found.setdefault(cid, "создатель")
        staff = await conn.fetch(
            """
            SELECT user_id,
                   COALESCE(
                     NULLIF(BTRIM(first_name), ''),
                     NULLIF(BTRIM(username), ''),
                     'сотрудник'
                   ) AS name,
                   role
            FROM admin_accounts
            WHERE role IS NOT NULL AND BTRIM(role) <> ''
            """
        )
        for row in staff:
            role = str(row["role"] or "").strip().lower()
            if role in {"", "applicant"}:
                continue
            uid = int(row["user_id"])
            if uid > 0:
                found.setdefault(uid, row["name"] or "сотрудник")
    if author_id:
        found.pop(int(author_id), None)
    return sorted(found.items(), key=lambda item: item[0])


async def handle_report(message: Message) -> None:
    """Ответ на /report: пинг администраторов группы и сотрудников проекта."""
    chat = message.chat
    if chat is None or int(chat.id) >= 0:
        await message.reply("Напишите /report в группе.", disable_web_page_preview=True)
        return
    author = getattr(message.from_user, "id", None)
    if author is None:
        return
    if not _remember(int(chat.id), int(author), time.monotonic()):
        await message.reply(
            "Состав уже звали. Подождите немного и напишите ещё раз, если никто не ответил.",
            disable_web_page_preview=True,
        )
        return
    note = report_note(message.text or message.caption or "") or ""
    try:
        people = await _targets(int(chat.id), int(author))
    except Exception:
        await message.reply("Не получилось собрать состав. Напишите ещё раз чуть позже.")
        return
    if not people:
        await message.reply("Сейчас некого позвать: в группе нет администраторов и сотрудников.")
        return
    chunks = mention_chunks(people, note=note)
    for index, (text, entities) in enumerate(chunks):
        kwargs = {
            "disable_web_page_preview": True,
            "entities": entities,
        }
        if index == 0:
            await message.reply(text, **kwargs)
        else:
            await message.answer(text, **kwargs)
