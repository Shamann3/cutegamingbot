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
_NOTE_LIMIT = 700
_EXCERPT_LIMIT = 90
_OFFICER_EMOJI = "5316887736823591263"
_last_report: Dict[Tuple[int, int], float] = {}

_PRIVATE = (
    "<b><tg-emoji emoji-id='5316887736823591263'>👮</tg-emoji> "
    "Напишите <code>/report</code> в группе.</b>\n"
    "<blockquote><i>Бот ответит на сообщение и позовёт администраторов и сотрудников.</i></blockquote>"
)
_WAIT = (
    "<b><tg-emoji emoji-id='5316887736823591263'>👮</tg-emoji> Состав уже звали.</b>\n"
    "<blockquote><i>Подождите немного и напишите ещё раз, если никто не ответил.</i></blockquote>"
)
_FAIL = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Не получилось собрать состав.</b>\n"
    "<blockquote><i>Напишите ещё раз чуть позже.</i></blockquote>"
)
_EMPTY = (
    "<b><tg-emoji emoji-id='5316887736823591263'>👮</tg-emoji> Сейчас некого позвать.</b>\n"
    "<blockquote><i>В этой группе нет администраторов и сотрудников проекта.</i></blockquote>"
)
_NO_NOTE = "Без текста. Посмотрите сообщение, на которое это ответ."


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


def _people_word(count: int) -> str:
    n = abs(int(count)) % 100
    tail = n % 10
    if 11 <= n <= 14 or tail == 0 or tail >= 5:
        word = "человек"
    elif tail == 1:
        word = "человек"
    else:
        word = "человека"
    return f"{count} {word}"


class _Card:
    """Текст и сущности вместе: жирный, цитата и пинг не сбивают друг другу позиции."""

    def __init__(self) -> None:
        self.text = ""
        self.entities: List[MessageEntity] = []

    def add(
        self,
        text: str,
        *kinds: str,
        user: Optional[User] = None,
        emoji_id: str = "",
    ) -> None:
        if not text:
            return
        offset = _utf16_len(self.text)
        self.text += text
        length = _utf16_len(text)
        for kind in kinds:
            extra = {}
            if kind == "text_mention":
                extra["user"] = user
            if kind == "custom_emoji":
                extra["custom_emoji_id"] = emoji_id
            self.entities.append(MessageEntity(
                type=kind, offset=offset, length=length, **extra,
            ))


def _title(card: _Card, words: str) -> None:
    line = f"👮 {words}"
    offset = _utf16_len(card.text)
    card.text += line
    card.entities.append(MessageEntity(type="bold", offset=offset, length=_utf16_len(line)))
    card.entities.append(MessageEntity(
        type="custom_emoji",
        offset=offset,
        length=_utf16_len("👮"),
        custom_emoji_id=_OFFICER_EMOJI,
    ))


def _section(card: _Card, title: str) -> None:
    if card.text:
        card.add("\n\n")
    card.add(title, "bold")
    card.add("\n")


def _excerpt(note: str) -> str:
    flat = " ".join(note.split())
    if len(flat) <= _EXCERPT_LIMIT:
        return flat
    return flat[: _EXCERPT_LIMIT - 1].rstrip() + "…"


def mention_chunks(
    people: List[Tuple[int, str]],
    *,
    note: str,
    author_name: str,
    author_username: str = "",
) -> List[Tuple[str, List[MessageEntity]]]:
    """Карточка репорта. Текст просьбы — отдельная цитата, имена зовут через text_mention."""
    clean_note = "\n".join(line.rstrip() for line in (note or "").splitlines()).strip()
    shown = clean_note or _NO_NOTE
    name = _label(author_name, "Участник")
    username = (author_username or "").lstrip("@").strip()
    batch = people[: _MENTIONS_PER_MESSAGE * 4]
    chunks: List[Tuple[str, List[MessageEntity]]] = []
    for start in range(0, len(batch), _MENTIONS_PER_MESSAGE):
        piece = batch[start:start + _MENTIONS_PER_MESSAGE]
        card = _Card()
        if start == 0:
            _title(card, "Репорт")
            _section(card, "Кто написал")
            card.add(name, "bold")
            if username:
                card.add("  ·  ")
                card.add(f"@{username}", "code")
            _section(card, "Текст")
            card.add(shown, "bold", "blockquote")
            _section(card, f"Кого зовём  ·  {_people_word(len(batch))}")
        else:
            _title(card, "Ещё зовём")
            if clean_note:
                _section(card, "Текст")
                card.add(_excerpt(clean_note), "italic", "blockquote")
            _section(card, "Кого зовём")
        for index, (uid, person) in enumerate(piece):
            if index:
                card.add("  ·  ")
            label = _label(person, "сотрудник")
            card.add(
                label,
                "text_mention",
                user=User(id=int(uid), is_bot=False, first_name=label[:64] or "сотрудник"),
            )
        chunks.append((card.text, card.entities))
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


def without_spamblock(
    found: Dict[int, str],
    blocked: set,
    author_id: Optional[int] = None,
) -> List[Tuple[int, str]]:
    """Автор репорта и люди со спам-блоком в список вызова не попадают."""
    skip = {int(uid) for uid in blocked if uid}
    if author_id:
        skip.add(int(author_id))
    kept = ((uid, name) for uid, name in found.items() if int(uid) not in skip)
    return sorted(kept, key=lambda item: item[0])


async def _targets(chat_id: int, author_id: Optional[int]) -> List[Tuple[int, str]]:
    from bot.admins.mute import _db

    pool = _db().pool
    if pool is None:
        return []
    found: Dict[int, str] = {}
    blocked: set = set()
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
            JOIN epsilon_positions p ON p.id = s.position_id
            LEFT JOIN users u ON u.user_id = s.user_id
            WHERE s.chat_id = $1
              AND s.user_id IS NOT NULL
              AND p.kind = 'post'
            """,
            int(chat_id),
        )
        for row in seats:
            uid = int(row["user_id"])
            if uid > 0:
                found.setdefault(uid, row["name"] or "админ")
        # Спам-блок в любой группе: такого человека не зовём, даже если он в составе.
        held = await conn.fetch(
            """
            SELECT s.user_id
            FROM epsilon_seats s
            JOIN epsilon_positions p ON p.id = s.position_id
            WHERE p.kind = 'spamblock' AND s.user_id IS NOT NULL
            """
        )
        for row in held:
            uid = int(row["user_id"])
            if uid > 0:
                blocked.add(uid)
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
    return without_spamblock(found, blocked, author_id)


async def handle_report(message: Message) -> None:
    """Ответ на /report: пинг администраторов группы и сотрудников проекта."""
    chat = message.chat
    if chat is None or int(chat.id) >= 0:
        await message.reply(_PRIVATE, parse_mode="HTML", disable_web_page_preview=True)
        return
    user = message.from_user
    author = getattr(user, "id", None)
    if author is None:
        return
    if not _remember(int(chat.id), int(author), time.monotonic()):
        await message.reply(_WAIT, parse_mode="HTML", disable_web_page_preview=True)
        return
    note = report_note(message.text or message.caption or "") or ""
    try:
        people = await _targets(int(chat.id), int(author))
    except Exception:
        await message.reply(_FAIL, parse_mode="HTML", disable_web_page_preview=True)
        return
    if not people:
        await message.reply(_EMPTY, parse_mode="HTML", disable_web_page_preview=True)
        return
    author_name = " ".join(
        part for part in (
            getattr(user, "first_name", "") or "",
            getattr(user, "last_name", "") or "",
        ) if part
    )
    chunks = mention_chunks(
        people,
        note=note,
        author_name=author_name,
        author_username=getattr(user, "username", "") or "",
    )
    for index, (text, entities) in enumerate(chunks):
        kwargs = {
            "disable_web_page_preview": True,
            "entities": entities,
        }
        if index == 0:
            await message.reply(text, **kwargs)
        else:
            await message.answer(text, **kwargs)
