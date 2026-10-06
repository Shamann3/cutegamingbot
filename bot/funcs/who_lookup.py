"""«Кто ты» о человеке, которого нет в Куте: кого искать и что показать.

Здесь правила и текст. Запросы к Telegram и к базе живут в profile.py.
«Кто ты» ничего не записывает в users: строка появляется, только когда человек
сам напишет при боте, поэтому реферальная ссылка остаётся за тем, кто его пригласит.
"""
from __future__ import annotations

import html
import re
import sys
from collections import deque
from dataclasses import dataclass, replace
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK = re.compile(r"^(?:https?://)?(?:t|telegram)\.me/([A-Za-z0-9_]{4,32})/?(?:[?#].*)?$", re.I)
_TG_USER = re.compile(r"^tg://user\?id=(\d{1,15})$", re.I)
_NAME_JUNK = re.compile(r"[\W_]+")
# «кто ты такой» — тот же вопрос, что «кто ты».
_FILLER = frozenset({"такой", "такая", "такое", "таков", "такова"})
_MAX_ID_DIGITS = 15
BIO_LIMIT = 200
PICK_LABEL_LIMIT = 40


@dataclass(frozen=True)
class TgPerson:
    user_id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    is_premium: Optional[bool] = None  # None — Telegram этого не сказал
    is_bot: bool = False
    deleted: bool = False
    scam: bool = False
    fake: bool = False
    verified: bool = False

    @property
    def full_name(self) -> str:
        parts = (" ".join(str(p or "").split()) for p in (self.first_name, self.last_name))
        return " ".join(p for p in parts if p)

    @classmethod
    def from_user(cls, obj: Any) -> Optional["TgPerson"]:
        """User из aiogram или ChatFullInfo личного чата."""
        if obj is None:
            return None
        try:
            uid = int(getattr(obj, "id", 0) or 0)
        except (TypeError, ValueError):
            return None
        if uid <= 0:
            return None
        premium = getattr(obj, "is_premium", None)
        return cls(
            user_id=uid,
            first_name=str(getattr(obj, "first_name", "") or ""),
            last_name=str(getattr(obj, "last_name", "") or ""),
            username=clean_username(getattr(obj, "username", "")),
            is_premium=None if premium is None else bool(premium),
            is_bot=bool(getattr(obj, "is_bot", False)),
        )


@dataclass(frozen=True)
class TgPlace:
    kind: str  # "channel" или "group"
    title: str = ""
    username: str = ""


@dataclass(frozen=True)
class WhoAsk:
    kind: str  # "none" | "person" | "id" | "username" | "name"
    value: str = ""
    person: Optional[TgPerson] = None
    maybe_username: str = ""  # одно латинское слово: может быть и именем, и username


@dataclass(frozen=True)
class Candidate:
    user_id: int
    name: str = ""
    username: str = ""


def clean_username(value: Any) -> str:
    text = str(value or "").strip().lstrip("@").strip(" ,.;:!?\"'`()[]{}<>")
    return text if _USERNAME.match(text) else ""


def username_from_link(value: Any) -> str:
    match = _LINK.match(str(value or "").strip())
    return clean_username(match.group(1)) if match else ""


def _entity_kind(entity: Any) -> str:
    raw = getattr(entity, "type", "")
    return str(getattr(raw, "value", raw) or "")


def parse_who(arg: str, entities: Iterable[Any] = ()) -> WhoAsk:
    """Кого спросили после «кто ты»."""
    for entity in entities or ():
        kind = _entity_kind(entity)
        if kind == "text_mention":
            person = TgPerson.from_user(getattr(entity, "user", None))
            if person is not None:
                return WhoAsk("person", str(person.user_id), person)
        elif kind == "text_link":
            url = str(getattr(entity, "url", "") or "").strip()
            by_id = _TG_USER.match(url)
            if by_id:
                return WhoAsk("id", by_id.group(1))
            by_link = username_from_link(url)
            if by_link:
                return WhoAsk("username", by_link)

    words = str(arg or "").split()
    while words and fold_name(words[0]) in _FILLER:
        words = words[1:]
    if not words:
        return WhoAsk("none")
    head = words[0]
    if head.isdigit() and len(head) <= _MAX_ID_DIGITS:
        return WhoAsk("id", head)
    if head.startswith("@"):
        name = clean_username(head)
        if name:
            return WhoAsk("username", name)
    by_link = username_from_link(head)
    if by_link:
        return WhoAsk("username", by_link)
    text = " ".join(words).strip(" ?!.,…")
    if not fold_name(text):
        return WhoAsk("none")
    maybe = clean_username(text) if len(words) == 1 else ""
    return WhoAsk("name", text, maybe_username=maybe)


# --- поиск по имени ------------------------------------------------------

def fold_name(text: Any) -> str:
    """Имя для сравнения: регистр, ё, эмодзи и знаки не важны."""
    folded = str(text or "").casefold().replace("ё", "е")
    return " ".join(_NAME_JUNK.sub(" ", folded).split())


def name_rank(query: str, name: str, username: str = "") -> Optional[int]:
    """0 — то же имя целиком, 1 — имя начинается так, 2 — совпала фамилия."""
    want = fold_name(query)
    have = fold_name(name)
    if not want:
        return None
    if username and username.casefold() == str(query or "").strip().lstrip("@").casefold():
        return 0
    if not have:
        return None
    if have == want:
        return 0
    words, asked = have.split(), want.split()
    if words[: len(asked)] == asked:
        return 1
    if len(asked) == 1 and asked[0] in words:
        return 2
    return None


def rank_people(query: str, people: Sequence[Candidate]) -> List[Tuple[int, Candidate]]:
    """Подходящие люди: сначала точнее, при равенстве — в исходном порядке."""
    scored = []
    seen = set()
    for order, person in enumerate(people):
        if person.user_id in seen:
            continue
        rank = name_rank(query, person.name, person.username)
        if rank is not None:
            seen.add(person.user_id)
            scored.append((rank, order, person))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [(rank, person) for rank, _, person in scored]


def sure_pick(query: str, ranked: Sequence[Tuple[int, Candidate]]) -> Optional[Candidate]:
    """Один подходящий — сразу он. Полное имя из двух слов и одно точное совпадение — тоже."""
    if len(ranked) == 1:
        return ranked[0][1]
    exact = [person for rank, person in ranked if rank == 0]
    if len(exact) == 1 and len(fold_name(query).split()) >= 2:
        return exact[0]
    return None


def pick_label(person: Candidate) -> str:
    name = " ".join(str(person.name or "").split()) or str(person.user_id)
    tail = f" · @{person.username}" if person.username else ""
    room = max(8, PICK_LABEL_LIMIT - len(tail))
    if len(name) > room:
        name = name[: room - 1].rstrip() + "…"
    return name + tail


# --- текст ----------------------------------------------------------------

def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def member_line(status: Any, *, custom_title: Any = "", is_member: Any = None) -> str:
    """Положение человека в этой группе по ответу getChatMember."""
    key = str(getattr(status, "value", status) or "")
    if key == "creator":
        return "👑 <b>Создатель этой группы</b>"
    if key == "administrator":
        title = " ".join(str(custom_title or "").split())
        suffix = f" · «{_esc(title)}»" if title else ""
        return f"🛡 <b>Администратор этой группы</b>{suffix}"
    if key == "member":
        return "👥 <b>Состоит в этой группе</b>"
    if key == "restricted":
        if is_member is False:
            return "🚪 <b>Не состоит в этой группе</b>"
        return "🔇 <b>В этой группе с ограничениями</b>"
    if key == "left":
        return "🚪 <b>Не состоит в этой группе</b>"
    if key == "kicked":
        return "🚫 <b>Заблокирован в этой группе</b>"
    return ""


def _note(person: TgPerson, *, is_self: bool) -> str:
    if person.deleted:
        return "Аккаунт удалён в Telegram."
    if person.is_bot:
        return "Это бот — профиля в Куте у ботов не бывает."
    if is_self:
        return (
            "🌱 Это вы. Профиль в Куте создаётся прямо сейчас — "
            "напишите <code>профиль</code> через пару секунд."
        )
    return (
        "🌱 Профиля в Куте пока нет — показываю данные из Telegram.\n"
        "Он появится, как только человек напишет в чате с ботом."
    )


def tg_card_html(person: TgPerson, *, bio: str = "", member: str = "", is_self: bool = False) -> str:
    """Карточка человека из Telegram — в том же виде, что начало профиля."""
    name = person.full_name or ("Удалённый аккаунт" if person.deleted else "Без имени")
    if person.username:
        link = f"<a href='https://t.me/{_esc(person.username)}'>{_esc(name)}</a>"
    else:
        link = f"<a href='tg://user?id={int(person.user_id)}'>{_esc(name)}</a>"
    lines = [f"🎩 <b>{link}</b>"]
    if person.username:
        lines.append(f"👤 <code>@{_esc(person.username)}</code>")
    lines.append(f"🆔 <code>{int(person.user_id)}</code>")

    marks = []
    if person.is_bot:
        marks.append("🤖 <b>Бот</b>")
    if person.is_premium:
        marks.append("⭐️ <b>Telegram Premium</b>")
    if person.verified:
        marks.append("✅ <b>Подтверждённый аккаунт</b>")
    if person.scam:
        marks.append("⚠️ <b>Telegram пометил аккаунт как мошеннический</b>")
    if person.fake:
        marks.append("⚠️ <b>Telegram пометил аккаунт как фейковый</b>")
    if member:
        marks.append(member)
    if marks:
        lines.extend(["", *marks])

    about = " ".join(str(bio or "").split())
    if about:
        if len(about) > BIO_LIMIT:
            about = about[: BIO_LIMIT - 1].rstrip() + "…"
        lines.extend(["", f"<blockquote>{_esc(about)}</blockquote>"])

    lines.extend(["", f"<blockquote>{_note(person, is_self=is_self)}</blockquote>"])
    return "\n".join(lines)


def place_html(username: str, place: TgPlace) -> str:
    what = "канал" if place.kind == "channel" else "группа"
    title = f" «{_esc(' '.join(place.title.split()))}»" if place.title.strip() else ""
    icon = "📢" if place.kind == "channel" else "👥"
    return f"{icon} <b>@{_esc(username)} — это {what}{title}, а не человек</b>"


_REPLY_HINT = "ответьте командой <code>кто ты</code> на сообщение этого человека"
_FIND_HINT = (
    "Ответьте командой <code>кто ты</code> на сообщение этого человека "
    "или напишите <code>кто ты @username</code>."
)


def username_missing_html(username: str) -> str:
    return f"<b>😔 В Telegram нет пользователя @{_esc(username)}</b>"


def username_unchecked_html(username: str) -> str:
    return (
        f"<b>😔 Не нашёл @{_esc(username)} среди игроков Кута</b>\n"
        "<blockquote>Проверить его в Telegram сейчас не получилось. "
        f"Попробуйте через минуту или {_REPLY_HINT} — покажу данные из Telegram.</blockquote>"
    )


def id_missing_html(user_id: Any) -> str:
    return (
        f"<b>😔 Не нашёл пользователя с ID <code>{_esc(user_id)}</code></b>\n"
        "<blockquote>Telegram показывает боту только тех, кого бот уже видел. "
        f"{_FIND_HINT}</blockquote>"
    )


def sender_chat_html(chat: Any, *, same_chat: bool) -> str:
    """Ответ на сообщение, которое написали от имени канала или группы."""
    if same_chat:
        return (
            "🕶 <b>Это написал анонимный администратор</b>\n"
            "<blockquote>Telegram не показывает, кто именно пишет от имени группы.</blockquote>"
        )
    place = from_bot_chat(chat)
    group = isinstance(place, TgPlace) and place.kind == "group"
    title = " ".join(str(getattr(chat, "title", "") or "").split())
    named = f" «{_esc(title)}»" if title else ""
    if group:
        return f"👥 <b>Это сообщение от группы{named}, а не от человека</b>"
    return f"📢 <b>Это сообщение от канала{named}, а не от человека</b>"


def name_missing_html(name: str) -> str:
    return (
        f"<b>😔 Не нашёл «{_esc(name)}» среди игроков Кута</b>\n"
        f"<blockquote>По имени Telegram людей не ищет. {_FIND_HINT}</blockquote>"
    )


def picker_html(query: str, shown: int, total: int, *, in_chat: bool) -> str:
    where = "в этой группе" if in_chat else "среди игроков Кута"
    head = f"<b>🔎 По запросу «{_esc(query)}» нашёл несколько человек {where} — выберите:</b>"
    if total > shown:
        head += (
            f"\n<blockquote>Показаны первые {shown} из {total}. "
            "Уточните имя или напишите @username.</blockquote>"
        )
    return head


# --- username через Telegram -----------------------------------------------

def owns_username(entity: Any, username: str) -> bool:
    want = str(username or "").casefold()
    if not want:
        return False
    names = [getattr(entity, "username", None)]
    names.extend(getattr(item, "username", None) for item in (getattr(entity, "usernames", None) or ()))
    return any(str(name or "").casefold() == want for name in names)


def from_telethon(entity: Any) -> Any:
    """User, Channel или Chat из Telethon — человек, канал или группа."""
    kind = type(entity).__name__
    if kind == "User":
        username = getattr(entity, "username", None) or next(
            (getattr(item, "username", "") for item in (getattr(entity, "usernames", None) or ())
             if getattr(item, "active", True)),
            "",
        )
        try:
            uid = int(getattr(entity, "id", 0) or 0)
        except (TypeError, ValueError):
            return None
        if uid <= 0:
            return None
        return TgPerson(
            user_id=uid,
            first_name=str(getattr(entity, "first_name", "") or ""),
            last_name=str(getattr(entity, "last_name", "") or ""),
            username=clean_username(username),
            is_premium=bool(getattr(entity, "premium", False)),
            is_bot=bool(getattr(entity, "bot", False)),
            deleted=bool(getattr(entity, "deleted", False)),
            scam=bool(getattr(entity, "scam", False)),
            fake=bool(getattr(entity, "fake", False)),
            verified=bool(getattr(entity, "verified", False)),
        )
    if kind in ("Channel", "ChannelForbidden"):
        group = bool(getattr(entity, "megagroup", False))
        return TgPlace(
            "group" if group else "channel",
            str(getattr(entity, "title", "") or ""),
            clean_username(getattr(entity, "username", "")),
        )
    if kind in ("Chat", "ChatForbidden"):
        return TgPlace("group", str(getattr(entity, "title", "") or ""))
    return None


def from_bot_chat(chat: Any) -> Any:
    """Ответ Bot API getChat: личный чат — человек, остальное — канал или группа."""
    raw = getattr(chat, "type", "")
    kind = str(getattr(raw, "value", raw) or "")
    if kind == "private":
        return TgPerson.from_user(chat)
    if kind == "channel":
        return TgPlace("channel", str(getattr(chat, "title", "") or ""), clean_username(getattr(chat, "username", "")))
    if kind in ("group", "supergroup"):
        return TgPlace("group", str(getattr(chat, "title", "") or ""), clean_username(getattr(chat, "username", "")))
    return None


def _resolved_entity(result: Any) -> Any:
    peer = getattr(result, "peer", None)
    wanted = None
    for attr in ("user_id", "channel_id", "chat_id"):
        wanted = getattr(peer, attr, None)
        if wanted:
            break
    for item in [*(getattr(result, "users", None) or ()), *(getattr(result, "chats", None) or ())]:
        if getattr(item, "id", None) == wanted:
            return item
    return None


async def resolve_with_userbot(client: Any, username: str) -> Tuple[str, Any]:
    """("person", TgPerson) | ("place", TgPlace) | ("missing", None) | ("flood", секунды) | ("unknown", None)."""
    try:
        from telethon import errors, functions
    except Exception:
        return "unknown", None
    try:
        peer = await client.get_input_entity(username)
        entity = await client.get_entity(peer)
        if not owns_username(entity, username):
            # В кэше сессии username мог остаться за прежним владельцем.
            entity = _resolved_entity(await client(functions.contacts.ResolveUsernameRequest(username)))
    except errors.FloodWaitError as exc:
        return "flood", int(getattr(exc, "seconds", 0) or 60)
    except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError, ValueError):
        return "missing", None
    except Exception:
        return "unknown", None
    if entity is None or not owns_username(entity, username):
        return "missing", None
    found = from_telethon(entity)
    if isinstance(found, TgPerson):
        return "person", found
    if isinstance(found, TgPlace):
        return "place", found
    return "unknown", None


def find_userbot() -> Any:
    """Основной юзербот, если он запущен в этом процессе и на связи."""
    for name in ("__main__", "main"):
        client = getattr(sys.modules.get(name), "main_userbot_client", None)
        if client is None:
            continue
        try:
            if client.is_connected():
                return client
        except Exception:
            continue
    return None


class UsernameBudget:
    """Сколько раз юзербот может спросить Telegram о username.

    ResolveUsername у Telegram ограничен; юзербот нужен и рассылкам, поэтому
    ходим редко, помним ответы и замолкаем на время FloodWait.
    """

    def __init__(
        self,
        *,
        per_viewer: float = 5.0,
        window: float = 600.0,
        window_max: int = 25,
        day_max: int = 150,
        found_ttl: float = 2 * 3600.0,
        missing_ttl: float = 1800.0,
        cache_max: int = 2000,
    ) -> None:
        self.per_viewer = per_viewer
        self.window = window
        self.window_max = window_max
        self.day_max = day_max
        self.found_ttl = found_ttl
        self.missing_ttl = missing_ttl
        self.cache_max = cache_max
        self._cache: Dict[str, Tuple[float, str, Any]] = {}
        self._viewer_at: Dict[int, float] = {}
        self._spent: Deque[float] = deque()
        self._paused_until = 0.0

    def cached(self, username: str, now: float) -> Optional[Tuple[str, Any]]:
        key = str(username or "").casefold()
        hit = self._cache.get(key)
        if hit is None:
            return None
        expires, kind, value = hit
        if now >= expires:
            self._cache.pop(key, None)
            return None
        return kind, value

    def remember(self, username: str, kind: str, value: Any, now: float) -> None:
        ttl = self.missing_ttl if kind == "missing" else self.found_ttl
        if len(self._cache) >= self.cache_max:
            for key in [k for k, (expires, _, _) in self._cache.items() if expires <= now]:
                self._cache.pop(key, None)
            while len(self._cache) >= self.cache_max:
                self._cache.pop(next(iter(self._cache)))
        self._cache[str(username or "").casefold()] = (now + ttl, kind, value)

    def allow(self, viewer_id: int, now: float) -> bool:
        if now < self._paused_until:
            return False
        last = self._viewer_at.get(int(viewer_id))
        if last is not None and now - last < self.per_viewer:
            return False
        while self._spent and now - self._spent[0] >= 86400.0:
            self._spent.popleft()
        if len(self._spent) >= self.day_max:
            return False
        recent = sum(1 for at in self._spent if now - at < self.window)
        return recent < self.window_max

    def spend(self, viewer_id: int, now: float) -> None:
        self._spent.append(now)
        self._viewer_at[int(viewer_id)] = now
        if len(self._viewer_at) > 4096:
            for key in [k for k, at in self._viewer_at.items() if now - at >= self.per_viewer]:
                self._viewer_at.pop(key, None)

    def pause(self, seconds: float, now: float) -> None:
        self._paused_until = max(self._paused_until, now + max(1.0, float(seconds or 0)))


USERNAME_BUDGET = UsernameBudget()


def fill_person(person: TgPerson, *, member_user: Any = None, chat: Any = None) -> TgPerson:
    """Дополняет карточку тем, что Telegram сказал в getChatMember и getChat."""
    extra = TgPerson.from_user(member_user)
    full = TgPerson.from_user(chat)
    updates: Dict[str, Any] = {}
    for source in (extra, full):
        if source is None or source.user_id != person.user_id:
            continue
        if person.is_premium is None and source.is_premium is not None and "is_premium" not in updates:
            updates["is_premium"] = source.is_premium
        if not person.full_name and source.full_name and "first_name" not in updates:
            updates["first_name"] = source.first_name
            updates["last_name"] = source.last_name
        if not person.username and source.username and "username" not in updates:
            updates["username"] = source.username
    return replace(person, **updates) if updates else person
