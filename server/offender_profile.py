# -*- coding: utf-8 -*-
"""Человек для наказания, которого ещё нет в users.

Команды бота спрашивают юзербота. Панели живут отдельным процессом и видят
только Bot API: getChat и, если известен чат, getChatMember.
«Нет в этой группе» не значит, что аккаунта нет. Явный отказ Telegram
наказание останавливает. Молчание при длинном id карточку всё равно создаёт,
чтобы архив, «кто ты» и вкладка наказаний говорили об одном человеке.
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Optional

from cute_identity import (
    ADOPT_USER_SQL,
    account_id_can_be_saved,
    name_is_placeholder,
    needs_telegram_profile,
    normalize_username,
    person_from_chat_member,
    person_from_telegram_chat,
    profile_when_telegram_is_silent,
)

TgApi = Callable[..., Awaitable[dict]]

SHORT = "Короткое число человеком не считается. Укажите ID из Telegram или @username."
DENIED = "Пользователь {user_id} не найден в Telegram. Проверьте ID."
BOT = "Это бот. Наказания выдаются людям."
PLACE = "@{name} — это {what}. Укажите человека."
NAME_ONLY = "По имени панель ищет только игроков Кута. Для человека вне базы укажите ID или @username."
UNCHECKED = (
    "В Куте нет @{name}. Бот его ещё не видел, поэтому панель не знает ID. "
    "Вставьте числовой ID или напишите команду в группе: бот спросит Telegram сам."
)
GLANCE_OUTSIDE = "В Куте этого человека ещё нет. Наказание добавит его в базу."
GLANCE_SILENT = "В Куте его нет, и Telegram имя не отдал. Наказание запишет карточку по этому ID."
SAVED_NAMED = "В Куте этого человека ещё не было. Записали его, чтобы наказание легло на карточку."
SAVED_SILENT = "Telegram имя не отдал. В карточке пока ID, наказание можно выдать."
BAD_LINK = "Такую ссылку панель не разбирает. Укажите ID или @username."
EMPTY = "Укажите ID или @username."

_DENIED_MARKERS = ("USER_ID_INVALID", "PEER_ID_INVALID")
_ABSENT_MARKERS = (
    "PARTICIPANT_ID_INVALID",
    "USER_NOT_PARTICIPANT",
    "MEMBER_NOT_FOUND",
    "USER_NOT_FOUND",
)
_CACHE_TTL = 45.0
_seen: dict[str, tuple[float, dict]] = {}


class OffenderRefused(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def account_missing_text(detail: str) -> bool:
    """Telegram прямо сказал, что такого аккаунта нет."""
    folded = str(detail or "").lower().replace(" ", "_")
    return any(marker.lower() in folded for marker in _DENIED_MARKERS) or "user_not_found" in folded


def _description(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("description") or "").upper().replace(" ", "_")


def _denied(payload: Any) -> bool:
    text = _description(payload)
    return any(marker in text for marker in _DENIED_MARKERS)


def _named(person: Optional[dict], user_id: int) -> Optional[dict]:
    if not person:
        return None
    if name_is_placeholder(person.get("first_name"), user_id):
        return None
    return person


def read_telegram_answer(user_id: int, chat_payload: Any, member_payload: Any) -> dict:
    """Ответ Bot API → person | bot | place | denied | silent.

    getChat «chat not found» и getChatMember «нет в группе» сюда приходят как silent:
    аккаунт при этом может быть настоящим.
    """
    if _denied(chat_payload):
        return {"kind": "denied", "person": None, "place": ""}
    person = None
    if isinstance(chat_payload, dict) and chat_payload.get("ok"):
        result = chat_payload.get("result") or {}
        if bool(result.get("is_bot")):
            return {"kind": "bot", "person": None, "place": ""}
        kind = str(result.get("type") or "")
        if kind and kind != "private":
            place = "channel" if kind == "channel" else "group"
            return {"kind": "place", "person": None, "place": place}
        person = person_from_telegram_chat(result)
    named = _named(person, user_id)
    if named:
        return {"kind": "person", "person": named, "place": ""}
    if _denied(member_payload):
        return {"kind": "denied", "person": None, "place": ""}
    if isinstance(member_payload, dict) and member_payload.get("ok"):
        result = member_payload.get("result") or {}
        user = result.get("user") if isinstance(result.get("user"), dict) else {}
        if bool(user.get("is_bot")):
            return {"kind": "bot", "person": None, "place": ""}
        member = person_from_chat_member(result)
        richer = _named(member, user_id)
        if richer:
            return {"kind": "person", "person": richer, "place": ""}
        if member and person is None:
            person = member
    if person:
        return {"kind": "person", "person": person, "place": ""}
    return {"kind": "silent", "person": None, "place": ""}


def parse_offender_query(raw: str) -> dict:
    """id, @username, t.me или tg://user. Обычное имя остаётся именем."""
    text = " ".join(str(raw or "").split())
    if not text:
        return {"kind": "empty"}
    lowered = text.lower()
    if lowered.startswith("tg://user"):
        tail = text.split("id=", 1)[-1].split("&", 1)[0]
        if tail.isdigit():
            text = tail
    elif "t.me/" in lowered or "telegram.me/" in lowered:
        marker = "t.me/" if "t.me/" in lowered else "telegram.me/"
        body = text[lowered.find(marker) + len(marker):]
        body = body.split("?")[0].split("#")[0].strip().strip("/")
        if not body or body.startswith("+") or body.lower().startswith(("c/", "joinchat")):
            return {"kind": "bad"}
        text = body.split("/")[0].strip().lstrip("@")
        if not text:
            return {"kind": "bad"}
    if text.startswith("@"):
        text = text[1:]
    if text.isdigit():
        if len(text) > 16:
            return {"kind": "bad"}
        try:
            uid = int(text)
        except ValueError:
            return {"kind": "bad"}
        if uid <= 0 or uid > 9223372036854775807:
            return {"kind": "bad"}
        return {"kind": "id", "user_id": uid}
    username = normalize_username(text if text.startswith("@") else f"@{text}" if text[:1].isalpha() else text)
    if not username and text[:1].isalpha():
        username = normalize_username(text)
    if username:
        return {"kind": "username", "username": username}
    if text[:1].isalpha() or any(ch.isalpha() for ch in text):
        return {"kind": "name"}
    return {"kind": "bad"}


def _cache_get(key: str) -> Optional[dict]:
    item = _seen.get(key)
    if not item or time.time() - item[0] > _CACHE_TTL:
        return None
    return item[1]


def _cache_put(key: str, value: dict) -> dict:
    _seen[key] = (time.time(), value)
    if len(_seen) > 500:
        now = time.time()
        for old, (stamp, _) in list(_seen.items()):
            if now - stamp > _CACHE_TTL:
                _seen.pop(old, None)
    return value


def _preview(user_id: int, first_name: str, username: Optional[str], *, outside: bool, silent: bool, balance: int = 0, banned: bool = False) -> dict:
    shown = " ".join(str(first_name or "").split())
    if not shown or shown == str(user_id):
        shown = f"ID {user_id}"
    payload = {
        "userId": int(user_id),
        "username": username or None,
        "displayName": shown,
        "balance": None if outside else int(balance or 0),
        "banned": bool(banned),
        "outside": bool(outside),
        "silent": bool(silent),
    }
    return payload


def _refusal_for(kind: str, user_id: int = 0, *, username: str = "", place: str = "") -> str:
    if kind == "short":
        return SHORT
    if kind == "denied":
        return DENIED.format(user_id=int(user_id))
    if kind == "bot":
        return BOT
    if kind == "place":
        what = "канал" if place == "channel" else "группа"
        return PLACE.format(name=username or "ссылка", what=what)
    if kind == "name":
        return NAME_ONLY
    if kind == "unchecked":
        return UNCHECKED.format(name=username)
    if kind == "bad":
        return BAD_LINK
    return EMPTY


async def _call(tg: TgApi, method: str, **params) -> dict:
    try:
        data = await tg(method, **params)
    except Exception as exc:
        return {"ok": False, "description": str(exc)}
    if not isinstance(data, dict):
        return {"ok": False, "description": "bad response"}
    return data


async def _default_tg(method: str, **params) -> dict:
    from admin_groups import _tg_api

    return await _tg_api(method, **params)


async def ask_telegram_id(user_id: int, chat_id: Optional[int] = None, *, tg_api: Optional[TgApi] = None) -> dict:
    uid = int(user_id)
    probe = int(chat_id or 0)
    key = f"id:{uid}:{probe}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    tg = tg_api or _default_tg
    chat = await _call(tg, "getChat", chat_id=uid, _timeout=6)
    member = None
    looked = read_telegram_answer(uid, chat, None)
    if looked["kind"] not in ("person", "bot", "denied", "place") and probe < 0:
        member = await _call(tg, "getChatMember", chat_id=probe, user_id=uid, _timeout=6)
        looked = read_telegram_answer(uid, chat, member)
    return _cache_put(key, looked)


async def ask_telegram_username(username: str, *, tg_api: Optional[TgApi] = None) -> dict:
    clean = normalize_username(username)
    if not clean:
        return {"kind": "unchecked", "person": None, "place": "", "username": ""}
    key = f"name:{clean.casefold()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    tg = tg_api or _default_tg
    chat = await _call(tg, "getChat", chat_id=f"@{clean}", _timeout=6)
    if isinstance(chat, dict) and chat.get("ok"):
        result = chat.get("result") or {}
        try:
            uid = int(result.get("id") or 0)
        except (TypeError, ValueError):
            uid = 0
        looked = read_telegram_answer(uid or 0, chat, None)
    elif _denied(chat):
        looked = {"kind": "denied", "person": None, "place": ""}
    else:
        looked = {"kind": "unchecked", "person": None, "place": ""}
    looked = {**looked, "username": clean}
    return _cache_put(key, looked)


async def _load_row(user_id: int):
    from db import db

    pool = getattr(db, "pool", None)
    if pool is None:
        return None
    return await pool.fetchrow(
        "SELECT user_id, first_name, username, balance, banned FROM users WHERE user_id = $1",
        int(user_id),
    )


async def _load_username(username: str):
    from db import db

    pool = getattr(db, "pool", None)
    if pool is None:
        return None
    return await pool.fetchrow(
        """
        SELECT user_id, first_name, username, balance, banned
        FROM users
        WHERE lower(username) = lower($1)
        LIMIT 1
        """,
        username,
    )


async def _save_person(person: dict) -> None:
    from db import db

    pool = getattr(db, "pool", None)
    if pool is None:
        return
    await pool.execute(
        ADOPT_USER_SQL,
        int(person["user_id"]),
        person["first_name"],
        person.get("username"),
    )


def _from_row(row) -> dict:
    return {
        "user_id": int(row["user_id"]),
        "first_name": row["first_name"] or "",
        "username": row["username"] or None,
        "balance": int(row["balance"] or 0),
        "banned": bool(row["banned"]),
    }


async def prepare_offender(
    user_id: int,
    chat_id: Optional[int] = None,
    *,
    tg_api: Optional[TgApi] = None,
    load_row: Optional[Callable[[int], Awaitable[Any]]] = None,
    save_person: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> dict:
    """Строка users перед наказанием из панели.

    ok=False — наказание надо остановить, текст в refusal.
    created — строки не было, мы её добавили.
    placeholder — имени нет, в карточке id.
    """
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        uid = 0
    loader = load_row or _load_row
    saver = save_person or _save_person
    row = None
    if uid > 0:
        try:
            row = await loader(uid)
        except Exception:
            row = None
    stored = _from_row(row) if row is not None else None
    if stored and not needs_telegram_profile(True, stored["first_name"], uid):
        return {
            "ok": True,
            "refusal": "",
            "user_id": uid,
            "first_name": stored["first_name"],
            "username": stored["username"],
            "created": False,
            "outside": False,
            "placeholder": False,
            "message": "",
        }
    if uid <= 0 or (stored is None and not account_id_can_be_saved(uid)):
        return {
            "ok": False,
            "refusal": SHORT,
            "user_id": uid,
            "first_name": "",
            "username": None,
            "created": False,
            "outside": False,
            "placeholder": False,
            "message": "",
        }
    looked = await ask_telegram_id(uid, chat_id, tg_api=tg_api)
    kind = looked["kind"]
    if kind in ("denied", "bot", "place"):
        return {
            "ok": False,
            "refusal": _refusal_for(kind, uid, place=str(looked.get("place") or "")),
            "user_id": uid,
            "first_name": "",
            "username": None,
            "created": False,
            "outside": stored is None,
            "placeholder": False,
            "message": "",
        }
    person = looked.get("person")
    if person is None:
        person = profile_when_telegram_is_silent(uid, telegram_denied=False)
    if person is None:
        if stored:
            label = " ".join(str(stored["first_name"] or "").split()) or str(uid)
            return {
                "ok": True,
                "refusal": "",
                "user_id": uid,
                "first_name": label,
                "username": stored.get("username"),
                "created": False,
                "outside": False,
                "placeholder": name_is_placeholder(label, uid),
                "message": "",
            }
        return {
            "ok": False,
            "refusal": SHORT,
            "user_id": uid,
            "first_name": "",
            "username": None,
            "created": False,
            "outside": False,
            "placeholder": False,
            "message": "",
        }
    if stored and stored.get("username") and not person.get("username"):
        person = {**person, "username": stored["username"]}
    try:
        await saver(person)
    except Exception:
        if stored is None:
            return {
                "ok": True,
                "refusal": "",
                "user_id": uid,
                "first_name": person["first_name"],
                "username": person.get("username"),
                "created": False,
                "outside": True,
                "placeholder": name_is_placeholder(person["first_name"], uid),
                "message": "",
            }
    placeholder = name_is_placeholder(person["first_name"], uid)
    created = stored is None
    message = ""
    if created and placeholder:
        message = SAVED_SILENT
    elif created:
        message = SAVED_NAMED
    return {
        "ok": True,
        "refusal": "",
        "user_id": int(person["user_id"]),
        "first_name": person["first_name"],
        "username": person.get("username"),
        "created": created,
        "outside": created,
        "placeholder": placeholder,
        "message": message,
    }


async def glance_person(
    query: str,
    chat_id: Optional[int] = None,
    *,
    tg_api: Optional[TgApi] = None,
    load_row: Optional[Callable[[int], Awaitable[Any]]] = None,
    load_username: Optional[Callable[[str], Awaitable[Any]]] = None,
) -> dict:
    """Подсказка в поле поиска. В базу ничего не пишет."""
    parsed = parse_offender_query(query)
    kind = parsed.get("kind")
    if kind in ("empty", "bad", "name"):
        return {"status": kind if kind != "empty" else "empty", "user": None, "message": _refusal_for(kind or "empty")}
    by_id = load_row or _load_row
    by_name = load_username or _load_username
    if kind == "id":
        uid = int(parsed["user_id"])
        row = None
        try:
            row = await by_id(uid)
        except Exception:
            row = None
        if row is None and not account_id_can_be_saved(uid):
            return {"status": "short", "user": None, "message": SHORT}
        if row is not None:
            saved = _from_row(row)
            return {
                "status": "in_db",
                "user": _preview(saved["user_id"], saved["first_name"], saved["username"], outside=False, silent=False, balance=saved["balance"], banned=saved["banned"]),
                "message": "",
            }
        looked = await ask_telegram_id(uid, chat_id, tg_api=tg_api)
        return _glance_from_telegram(uid, looked, username="")
    username = parsed["username"]
    try:
        row = await by_name(username)
    except Exception:
        row = None
    if row is not None:
        saved = _from_row(row)
        return {
            "status": "in_db",
            "user": _preview(saved["user_id"], saved["first_name"], saved["username"], outside=False, silent=False, balance=saved["balance"], banned=saved["banned"]),
            "message": "",
        }
    looked = await ask_telegram_username(username, tg_api=tg_api)
    person = looked.get("person")
    uid = int(person["user_id"]) if person else 0
    return _glance_from_telegram(uid, looked, username=username)


def _glance_from_telegram(user_id: int, looked: dict, *, username: str) -> dict:
    kind = looked.get("kind")
    person = looked.get("person")
    if kind == "person" and person:
        silent = name_is_placeholder(person.get("first_name"), int(person["user_id"]))
        return {
            "status": "silent" if silent else "outside",
            "user": _preview(
                int(person["user_id"]),
                person.get("first_name") or "",
                person.get("username"),
                outside=True,
                silent=silent,
            ),
            "message": GLANCE_SILENT if silent else GLANCE_OUTSIDE,
        }
    if kind == "silent" and account_id_can_be_saved(user_id):
        return {
            "status": "silent",
            "user": _preview(user_id, "", username or None, outside=True, silent=True),
            "message": GLANCE_SILENT,
        }
    if kind == "unchecked":
        return {"status": "unchecked", "user": None, "message": UNCHECKED.format(name=username or "username")}
    if kind in ("denied", "bot", "place"):
        return {
            "status": kind,
            "user": None,
            "message": _refusal_for(kind, user_id, username=username, place=str(looked.get("place") or "")),
        }
    if kind == "silent":
        return {"status": "unchecked" if username else "denied", "user": None, "message": _refusal_for("unchecked" if username else "denied", user_id, username=username)}
    return {"status": "unchecked", "user": None, "message": UNCHECKED.format(name=username or str(user_id or "username"))}


async def adopt_query(
    query: str,
    chat_id: Optional[int] = None,
    *,
    tg_api: Optional[TgApi] = None,
) -> dict:
    """Создаёт строку users и возвращает результат prepare_offender."""
    parsed = parse_offender_query(query)
    kind = parsed.get("kind")
    if kind != "id" and kind != "username":
        raise OffenderRefused(_refusal_for(kind or "empty"))
    if kind == "username":
        looked = await ask_telegram_username(parsed["username"], tg_api=tg_api)
        person = looked.get("person")
        if not person:
            raise OffenderRefused(_refusal_for(
                looked.get("kind") if looked.get("kind") in ("bot", "place", "denied") else "unchecked",
                username=parsed["username"],
                place=str(looked.get("place") or ""),
            ))
        prepared = await prepare_offender(int(person["user_id"]), chat_id, tg_api=tg_api)
    else:
        prepared = await prepare_offender(int(parsed["user_id"]), chat_id, tg_api=tg_api)
    if not prepared["ok"]:
        raise OffenderRefused(prepared["refusal"] or EMPTY)
    return prepared


def failure_text(result: dict) -> str:
    spoken = str((result or {}).get("spoken") or "").strip()
    if spoken:
        return spoken
    from staff_punish import telegram_refusal

    return telegram_refusal(result or {})
