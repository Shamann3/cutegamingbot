"""Поток «кто ты» из profile.py на поддельных боте, сообщении и базе.

profile.py тянет боевую базу, поэтому функции «кто ты» берём из него по AST
и выполняем с заглушками вокруг.
"""
import ast
import asyncio
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.funcs import who_lookup as who

PROFILE = Path(__file__).resolve().parents[1] / "bot" / "funcs" / "profile.py"
VIEWER = 100
CHAT = -1001


def _load(**stubs):
    tree = ast.parse(PROFILE.read_text(encoding="utf-8"))
    funcs = {
        "_normalize_spaces", "_extract_trigger_and_arg", "_clean_username_candidate",
        "_try_find_user_id_by_username", "_who_chat_people", "_who_global_people",
        "_who_pick_cb", "_who_send_picker", "_resolve_reply_target_user_id",
        "_cute_profile_exists", "get_user_who_are_you", "_who_bot", "_who_remember_card",
        "_who_reply", "_who_reply_person", "_who_tg_call", "_who_telegram_card",
        "_who_username_in_telegram", "_who_show_telegram_username", "_who_show_name",
        "get_user_information_in_who_are_you",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in funcs:
            nodes.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id.startswith("WHO_") for t in targets):
                nodes.append(node)
    assert funcs <= {n.name for n in nodes if hasattr(n, "name")}

    profiles = []

    async def build_caption(*, viewer_id, target_user_id, db, chat_id):
        profiles.append(target_user_id)
        return f"PROFILE {target_user_id}"

    async def send_caption(factory, caption, *, uid=None):
        return await factory(caption)

    namespace = {
        "asyncio": asyncio, "re": re, "time": time, "who": who,
        "Message": object, "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "Tuple": Tuple,
        "InlineKeyboardButton": InlineKeyboardButton, "InlineKeyboardMarkup": InlineKeyboardMarkup,
        "PROFILE_TG_TIMEOUT": 1.0, "bot1": None, "stop_who_are_you_flags": {},
        "_who_dbg": lambda *a, **k: None, "_who_info_dbg": lambda *a, **k: None,
        "_profile_get_message_meta": lambda mid: {},
        "_profile_safe_str": lambda v, d="": str(v or d),
        "_build_profile_caption_for_target": build_caption,
        "_profile_target_has_warns": lambda uid: asyncio.sleep(0, result=False),
        "_profile_build_who_markup": lambda **kw: None,
        "_profile_send_caption": send_caption,
        "_profile_store_message_meta": lambda *a, **k: None,
    }
    namespace.update(stubs)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PROFILE), "exec"), namespace)
    namespace["profiles"] = profiles
    return namespace


class Pool:
    def __init__(self, users=None, chat_people=None):
        self.users = users or {}
        self.chat_people = chat_people or []
        self.sql = []

    async def fetchval(self, sql, *args):
        self.sql.append(sql)
        return 1 if args[0] in self.users else None

    async def fetch(self, sql, *args):
        self.sql.append(sql)
        if "FROM chatall" in sql:
            return [{"user_id": u, "first_name": self.users[u][0], "username": self.users[u][1]} for u in self.chat_people]
        if "first_name ILIKE" in sql:
            return [
                {"user_id": u, "first_name": n, "username": un}
                for u, (n, un) in self.users.items() if n.casefold() == args[0].casefold()
            ]
        return []


class DB:
    def __init__(self, pool):
        self.pool = pool

    async def get_user_id_by_username(self, username):
        self.pool.sql.append("SELECT username")
        for uid, (_, un) in self.pool.users.items():
            if un and un.casefold() == username.casefold():
                return uid
        return None


class Bot:
    id = 999

    def __init__(self, chats=None, members=None):
        self.chats = chats or {}
        self.members = members or {}
        self.calls = []

    async def get_chat(self, chat_id):
        self.calls.append(("get_chat", chat_id))
        if chat_id not in self.chats:
            raise RuntimeError("Bad Request: chat not found")
        return self.chats[chat_id]

    async def get_chat_member(self, chat_id, user_id):
        self.calls.append(("get_chat_member", user_id))
        if user_id not in self.members:
            raise RuntimeError("Bad Request: PARTICIPANT_ID_INVALID")
        return self.members[user_id]


class Msg(SimpleNamespace):
    async def reply(self, text, **kw):
        self.replies.append((text, kw))
        return SimpleNamespace(chat=self.chat, message_id=5000 + len(self.replies))


def _user(uid, first, username=None, **kw):
    return SimpleNamespace(id=uid, first_name=first, last_name=None, username=username,
                           is_bot=kw.pop("is_bot", False), is_premium=kw.pop("is_premium", None), **kw)


def _msg(text, *, bot, reply_to=None, entities=None, chat_id=CHAT):
    return Msg(
        text=text, entities=entities, bot=bot, replies=[], message_id=1,
        from_user=_user(VIEWER, "Я", "me_viewer"),
        chat=SimpleNamespace(id=chat_id, type="supergroup" if chat_id < 0 else "private"),
        reply_to_message=reply_to,
    )


def _run(ns, message, pool):
    asyncio.run(ns["get_user_who_are_you"](message, DB(pool)))


@pytest.fixture(autouse=True)
def fresh_budget(monkeypatch):
    monkeypatch.setattr(who, "USERNAME_BUDGET", who.UsernameBudget())
    monkeypatch.setattr(who, "find_userbot", lambda: None)


def _only_reads(pool):
    return all(sql.lstrip().upper().startswith("SELECT") for sql in pool.sql)


def test_cute_player_by_username_opens_the_profile():
    ns = _load()
    pool = Pool(users={7: ("Вася", "vasya")})
    bot = Bot()
    _run(ns, _msg("кто ты @Vasya", bot=bot), pool)
    assert ns["profiles"] == [7]
    assert bot.calls == []


class User(SimpleNamespace):
    """Так Telethon называет человека."""


def test_stranger_found_by_userbot_gets_a_telegram_card(monkeypatch):
    stranger = User(id=55, first_name="Аня", last_name=None, username="anya_tg", usernames=None,
                    premium=True, bot=False, deleted=False, scam=False, fake=False, verified=False)

    class Client:
        async def get_input_entity(self, username):
            return "peer"

        async def get_entity(self, peer):
            return stranger

    monkeypatch.setattr(who, "find_userbot", lambda: Client())
    ns = _load()
    pool = Pool(users={7: ("Вася", "vasya")})
    member = SimpleNamespace(status="member", user=_user(55, "Аня", "anya_tg", is_premium=True))
    bot = Bot(chats={55: SimpleNamespace(type="private", id=55, first_name="Аня", username="anya_tg", bio="Пеку торты")},
              members={55: member})
    message = _msg("кто ты @anya_tg", bot=bot)
    _run(ns, message, pool)
    text = message.replies[0][0]
    assert "<a href='https://t.me/anya_tg'>Аня</a>" in text
    assert "⭐️ <b>Telegram Premium</b>" in text
    assert "👥 <b>Состоит в этой группе</b>" in text
    assert "Пеку торты" in text
    assert "Профиля в Куте пока нет" in text
    assert ns["profiles"] == []
    assert _only_reads(pool)


def test_unknown_username_without_userbot_says_what_to_do():
    ns = _load()
    pool = Pool()
    bot = Bot()
    message = _msg("кто ты @ghost_user", bot=bot)
    _run(ns, message, pool)
    assert message.replies[0][0] == who.username_unchecked_html("ghost_user")
    assert ("get_chat", "@ghost_user") in bot.calls
    assert _only_reads(pool)


def test_username_of_a_channel_is_not_a_person():
    ns = _load()
    bot = Bot(chats={"@news_room": SimpleNamespace(type="channel", title="Новости", username="news_room")})
    message = _msg("кто ты t.me/news_room", bot=bot)
    _run(ns, message, Pool())
    assert message.replies[0][0] == "📢 <b>@news_room — это канал «Новости», а не человек</b>"


def test_name_with_several_people_in_the_chat_offers_buttons():
    ns = _load()
    pool = Pool(users={1: ("Вася Пупкин", "vp"), 2: ("Петя", None), 3: ("Вася Иванов", None)}, chat_people=[3, 2, 1])
    message = _msg("кто ты Вася", bot=Bot())
    _run(ns, message, pool)
    text, kw = message.replies[0]
    assert "нашёл несколько человек в этой группе" in text
    buttons = [row[0] for row in kw["reply_markup"].inline_keyboard]
    assert [b.text for b in buttons] == ["Вася Иванов", "Вася Пупкин · @vp"]
    assert [b.callback_data for b in buttons] == [f"whopick:{VIEWER}:3", f"whopick:{VIEWER}:1"]
    assert _only_reads(pool)


def test_one_person_by_first_name_opens_right_away():
    ns = _load()
    pool = Pool(users={1: ("Вася Пупкин", None), 2: ("Петя", None)}, chat_people=[1, 2])
    _run(ns, _msg("кто ты вася", bot=Bot()), pool)
    assert ns["profiles"] == [1]


def test_name_nobody_has_explains_how_to_find_the_person():
    ns = _load()
    message = _msg("кто ты Григорий", bot=Bot())
    _run(ns, message, Pool(users={1: ("Вася", None)}, chat_people=[1]))
    assert message.replies[0][0] == who.name_missing_html("Григорий")


def test_reply_to_a_stranger_shows_his_telegram_card():
    ns = _load()
    pool = Pool()
    author = _user(77, "Оля", None, is_premium=False)
    bot = Bot(members={77: SimpleNamespace(status="administrator", custom_title="Модер", user=author)})
    message = _msg("кто ты", bot=bot, reply_to=SimpleNamespace(message_id=9, from_user=author, sender_chat=None))
    _run(ns, message, pool)
    text = message.replies[0][0]
    assert "<a href='tg://user?id=77'>Оля</a>" in text
    assert "🛡 <b>Администратор этой группы</b> · «Модер»" in text
    assert _only_reads(pool)

    again = _msg("кто ты", bot=bot, reply_to=SimpleNamespace(message_id=5001, from_user=_user(999, "Кут", is_bot=True), sender_chat=None))
    _run(ns, again, pool)
    assert "<a href='tg://user?id=77'>Оля</a>" in again.replies[0][0]


def test_reply_to_a_channel_post_is_not_a_person():
    ns = _load()
    post = SimpleNamespace(message_id=9, from_user=_user(136817688, "Channel", is_bot=True),
                           sender_chat=SimpleNamespace(id=-100777, type="channel", title="Канал"))
    message = _msg("кто ты?", bot=Bot(), reply_to=post)
    _run(ns, message, Pool())
    assert message.replies[0][0] == "📢 <b>Это сообщение от канала «Канал», а не от человека</b>"


def test_mention_without_username_finds_the_person():
    ns = _load()
    user = _user(88, "Дима", None, is_premium=True)
    entity = SimpleNamespace(type="text_mention", offset=7, length=4, user=user)
    message = _msg("кто ты Дима", bot=Bot(), entities=[entity])
    _run(ns, message, Pool(users={1: ("Дима", None)}, chat_people=[1]))
    assert "<a href='tg://user?id=88'>Дима</a>" in message.replies[0][0]


def test_id_telegram_does_not_show_gets_a_clear_answer():
    ns = _load()
    message = _msg("кто ты 123456", bot=Bot())
    _run(ns, message, Pool())
    assert message.replies[0][0] == who.id_missing_html(123456)


def test_new_viewer_asking_about_himself_is_told_the_profile_is_coming():
    ns = _load()
    message = _msg("кто ты", bot=Bot())
    _run(ns, message, Pool())
    assert "Это вы" in message.replies[0][0]


def test_who_are_you_such_is_the_same_question():
    ns = _load()
    pool = Pool(users={VIEWER: ("Я", "me_viewer")})
    _run(ns, _msg("кто ты такой", bot=Bot()), pool)
    assert ns["profiles"] == [VIEWER]
