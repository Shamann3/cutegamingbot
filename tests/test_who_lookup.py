import asyncio
import sys
from types import SimpleNamespace

import pytest

from bot.funcs import who_lookup as who


class User(SimpleNamespace):
    pass


class Channel(SimpleNamespace):
    pass


class Chat(SimpleNamespace):
    pass


def _tg_user(**kw):
    base = dict(
        id=5, first_name="Вася", last_name=None, username="vasya", usernames=None,
        premium=False, bot=False, deleted=False, scam=False, fake=False, verified=False,
    )
    base.update(kw)
    return User(**base)


def _balanced(text: str) -> bool:
    return all(text.count(f"<{t}>") == text.count(f"</{t}>") for t in ("b", "code", "blockquote"))


# --- кого спросили ----------------------------------------------------------

@pytest.mark.parametrize("arg,kind,value", [
    ("", "none", ""),
    ("такой", "none", ""),
    ("Такая?", "none", ""),
    ("6801702632", "id", "6801702632"),
    ("@Vasya_Pupkin", "username", "Vasya_Pupkin"),
    ("@vasya,", "username", "vasya"),
    ("@vasya пожалуйста", "username", "vasya"),
    ("https://t.me/vasya_pupkin", "username", "vasya_pupkin"),
    ("t.me/vasya_pupkin?start=1", "username", "vasya_pupkin"),
    ("такой @vasya", "username", "vasya"),
    ("Вася", "name", "Вася"),
    ("Вася Пупкин?", "name", "Вася Пупкин"),
    ("1234567890123456789", "name", "1234567890123456789"),
])
def test_reads_who_was_asked(arg, kind, value):
    ask = who.parse_who(arg)
    assert (ask.kind, ask.value) == (kind, value)


def test_one_latin_word_may_be_a_username_too():
    assert who.parse_who("vasya").maybe_username == "vasya"
    assert who.parse_who("Вася").maybe_username == ""
    assert who.parse_who("vasya pupkin").maybe_username == ""


def test_mention_without_username_is_the_person_himself():
    user = SimpleNamespace(id=77, first_name="Аня", last_name="Ким", username=None, is_premium=True, is_bot=False)
    entity = SimpleNamespace(type="text_mention", user=user)
    ask = who.parse_who("Аня", [entity])
    assert ask.kind == "person"
    assert ask.person == who.TgPerson(77, "Аня", "Ким", "", is_premium=True)


def test_links_in_text_point_to_the_person():
    by_id = SimpleNamespace(type=SimpleNamespace(value="text_link"), url="tg://user?id=777")
    by_name = SimpleNamespace(type="text_link", url="https://t.me/someone_here")
    other = SimpleNamespace(type="text_link", url="https://example.com/x")
    assert who.parse_who("тут", [by_id]) == who.WhoAsk("id", "777")
    assert who.parse_who("тут", [by_name]) == who.WhoAsk("username", "someone_here")
    assert who.parse_who("Вася", [other]).kind == "name"


# --- поиск по имени ----------------------------------------------------------

@pytest.mark.parametrize("query,name,username,rank", [
    ("Вася Пупкин", "вася пупкин 🐱", "", 0),
    ("Алёна", "Алена", "", 0),
    ("vasya_pupkin", "Кто-то", "Vasya_Pupkin", 0),
    ("вася", "Вася Пупкин", "", 1),
    ("пупкин", "Вася Пупкин", "", 2),
    ("вас", "Вася", "", None),
    ("петя", "Вася Пупкин", "", None),
    ("", "Вася", "", None),
    ("!!!", "Вася", "", None),
])
def test_name_rank(query, name, username, rank):
    assert who.name_rank(query, name, username) == rank


def test_people_are_ranked_by_closeness_then_by_activity():
    people = [
        who.Candidate(1, "Вася Пупкин"),
        who.Candidate(2, "Петя"),
        who.Candidate(3, "Вася"),
        who.Candidate(1, "Вася Пупкин"),
        who.Candidate(4, "Иван Вася"),
    ]
    ranked = who.rank_people("Вася", people)
    assert [(rank, p.user_id) for rank, p in ranked] == [(0, 3), (1, 1), (2, 4)]


def test_sure_pick_only_when_there_is_no_doubt():
    one = [(1, who.Candidate(1, "Вася Пупкин"))]
    assert who.sure_pick("вася", one).user_id == 1
    many = [(0, who.Candidate(3, "Вася")), (1, who.Candidate(1, "Вася Пупкин"))]
    assert who.sure_pick("вася", many) is None
    full = [(0, who.Candidate(1, "Вася Пупкин")), (1, who.Candidate(2, "Вася Пупкин Младший"))]
    assert who.sure_pick("Вася Пупкин", full).user_id == 1
    twins = [(0, who.Candidate(1, "Вася Пупкин")), (0, who.Candidate(2, "Вася Пупкин"))]
    assert who.sure_pick("Вася Пупкин", twins) is None


def test_pick_label_is_short_and_shows_username():
    assert who.pick_label(who.Candidate(1, "Вася", "vasya")) == "Вася · @vasya"
    assert who.pick_label(who.Candidate(9, "")) == "9"
    long = who.pick_label(who.Candidate(1, "Очень " * 20, "someone_long"))
    assert len(long) <= who.PICK_LABEL_LIMIT
    assert long.endswith("… · @someone_long")


# --- карточка из Telegram ------------------------------------------------------

def test_card_looks_like_the_head_of_a_profile():
    person = who.TgPerson(5, "Вася", "Пупкин", "vasya", is_premium=True)
    card = who.tg_card_html(person, bio="Люблю <кубики> & шашки", member=who.member_line("member"))
    assert card.startswith("🎩 <b><a href='https://t.me/vasya'>Вася Пупкин</a></b>\n")
    assert "👤 <code>@vasya</code>" in card
    assert "🆔 <code>5</code>" in card
    assert "⭐️ <b>Telegram Premium</b>" in card
    assert "👥 <b>Состоит в этой группе</b>" in card
    assert "<blockquote>Люблю &lt;кубики&gt; &amp; шашки</blockquote>" in card
    assert "Профиля в Куте пока нет" in card
    assert "None" not in card
    assert _balanced(card)


def test_card_without_username_links_by_id_and_hides_unknown_premium():
    card = who.tg_card_html(who.TgPerson(42, "<b>Хакер</b>"))
    assert "<a href='tg://user?id=42'>&lt;b&gt;Хакер&lt;/b&gt;</a>" in card
    assert "👤" not in card
    assert "Premium" not in card
    assert "None" not in card
    assert _balanced(card)


def test_card_notes_for_self_bot_and_deleted():
    assert "Это вы" in who.tg_card_html(who.TgPerson(1, "Я"), is_self=True)
    bot_card = who.tg_card_html(who.TgPerson(2, "Робот", is_bot=True))
    assert "🤖 <b>Бот</b>" in bot_card and "у ботов не бывает" in bot_card
    gone = who.tg_card_html(who.TgPerson(3, deleted=True))
    assert "Удалённый аккаунт" in gone and "Аккаунт удалён" in gone


def test_card_warns_about_scam_and_fake():
    card = who.tg_card_html(who.TgPerson(4, "Подарки", scam=True, fake=True, verified=True))
    assert "мошеннический" in card and "фейковый" in card and "Подтверждённый" in card


def test_long_bio_is_clipped():
    card = who.tg_card_html(who.TgPerson(5, "Вася"), bio="а" * 500)
    assert "а" * who.BIO_LIMIT not in card
    assert "…</blockquote>" in card


@pytest.mark.parametrize("status,kw,text", [
    ("creator", {}, "👑 <b>Создатель этой группы</b>"),
    ("administrator", {"custom_title": "Модер"}, "🛡 <b>Администратор этой группы</b> · «Модер»"),
    ("administrator", {}, "🛡 <b>Администратор этой группы</b>"),
    ("member", {}, "👥 <b>Состоит в этой группе</b>"),
    ("restricted", {"is_member": True}, "🔇 <b>В этой группе с ограничениями</b>"),
    ("restricted", {"is_member": False}, "🚪 <b>Не состоит в этой группе</b>"),
    ("left", {}, "🚪 <b>Не состоит в этой группе</b>"),
    ("kicked", {}, "🚫 <b>Заблокирован в этой группе</b>"),
    ("weird", {}, ""),
])
def test_member_line(status, kw, text):
    assert who.member_line(status, **kw) == text


def test_fill_person_takes_what_telegram_added():
    person = who.TgPerson(5, "Вася")
    member_user = SimpleNamespace(id=5, first_name="Вася", last_name=None, username="vasya", is_premium=True)
    chat = SimpleNamespace(id=5, type="private", first_name="Вася", last_name="П", username="vasya_new")
    filled = who.fill_person(person, member_user=member_user, chat=chat)
    assert filled.is_premium is True
    assert filled.username == "vasya"
    stranger = SimpleNamespace(id=6, first_name="Чужой", username="chuzhoi", is_premium=True)
    assert who.fill_person(person, member_user=stranger) == person


# --- тексты ------------------------------------------------------------------

def test_answers_explain_what_to_do_next():
    assert who.username_missing_html("vasya") == "<b>😔 В Telegram нет пользователя @vasya</b>"
    unchecked = who.username_unchecked_html("vasya")
    assert "Не нашёл @vasya среди игроков Кута" in unchecked and "<code>кто ты</code>" in unchecked
    assert "<code>12345</code>" in who.id_missing_html(12345)
    missing = who.name_missing_html("<Вася>")
    assert "«&lt;Вася&gt;»" in missing and "кто ты @username" in missing
    for text in (unchecked, who.id_missing_html(1), missing):
        assert _balanced(text)


def test_places_are_not_people():
    assert who.place_html("news", who.TgPlace("channel", "Новости", "news")) == (
        "📢 <b>@news — это канал «Новости», а не человек</b>"
    )
    assert "это группа «Чат»" in who.place_html("chat", who.TgPlace("group", "Чат"))
    anon = who.sender_chat_html(SimpleNamespace(id=-100, type="supergroup", title="Чат"), same_chat=True)
    assert "анонимный администратор" in anon
    channel = who.sender_chat_html(SimpleNamespace(id=-200, type="channel", title="Канал"), same_chat=False)
    assert channel == "📢 <b>Это сообщение от канала «Канал», а не от человека</b>"
    group = who.sender_chat_html(SimpleNamespace(id=-300, type="supergroup", title=""), same_chat=False)
    assert group == "👥 <b>Это сообщение от группы, а не от человека</b>"


def test_picker_says_where_it_searched():
    assert "в этой группе" in who.picker_html("Саша", 3, 3, in_chat=True)
    wide = who.picker_html("Саша", 8, 20, in_chat=False)
    assert "среди игроков Кута" in wide and "первые 8 из 20" in wide
    assert _balanced(wide)


# --- username через Telegram --------------------------------------------------

def test_from_telethon_knows_people_channels_and_groups():
    person = who.from_telethon(_tg_user(
        username=None,
        usernames=[SimpleNamespace(username="old_name", active=False), SimpleNamespace(username="vasya_nft", active=True)],
        premium=True, scam=True,
    ))
    assert person == who.TgPerson(5, "Вася", "", "vasya_nft", is_premium=True, scam=True)
    assert who.from_telethon(Channel(title="Новости", username="news", megagroup=False)) == who.TgPlace("channel", "Новости", "news")
    assert who.from_telethon(Channel(title="Чат", username=None, megagroup=True)).kind == "group"
    assert who.from_telethon(Chat(title="Старая группа")) == who.TgPlace("group", "Старая группа")
    assert who.from_telethon(object()) is None


def test_from_bot_chat():
    assert who.from_bot_chat(SimpleNamespace(type="private", id=5, first_name="Вася", username="vasya")).username == "vasya"
    assert who.from_bot_chat(SimpleNamespace(type="channel", title="Н", username="news")).kind == "channel"
    assert who.from_bot_chat(SimpleNamespace(type="supergroup", title="Ч", username=None)).kind == "group"
    assert who.from_bot_chat(SimpleNamespace(type="")) is None


def test_owns_username_checks_every_active_name():
    assert who.owns_username(_tg_user(username="Vasya"), "vasya")
    assert who.owns_username(_tg_user(username=None, usernames=[SimpleNamespace(username="Second")]), "second")
    assert not who.owns_username(_tg_user(username="other"), "vasya")
    assert not who.owns_username(_tg_user(), "")


class FakeClient:
    def __init__(self, *, entity=None, error=None, resolved=None):
        self.entity, self.error, self.resolved = entity, error, resolved
        self.requests = []

    async def get_input_entity(self, username):
        if self.error is not None:
            raise self.error
        return ("peer", username)

    async def get_entity(self, peer):
        return self.entity

    async def __call__(self, request):
        self.requests.append(request)
        return self.resolved


def _resolve(client, username="vasya"):
    return asyncio.run(who.resolve_with_userbot(client, username))


def test_userbot_finds_the_person():
    kind, person = _resolve(FakeClient(entity=_tg_user(premium=True)))
    assert kind == "person"
    assert person.user_id == 5 and person.is_premium is True


def test_userbot_rechecks_a_username_that_moved_to_someone_else():
    fresh = _tg_user(id=9, username="vasya")
    client = FakeClient(
        entity=_tg_user(id=5, username="now_other"),
        resolved=SimpleNamespace(peer=SimpleNamespace(user_id=9), users=[fresh], chats=[]),
    )
    kind, person = _resolve(client)
    assert (kind, person.user_id) == ("person", 9)
    assert type(client.requests[0]).__name__ == "ResolveUsernameRequest"
    assert client.requests[0].username == "vasya"


def test_userbot_answers_for_missing_flood_channel_and_failure():
    from telethon import errors

    assert _resolve(FakeClient(error=ValueError('No user has "vasya" as username'))) == ("missing", None)
    assert _resolve(FakeClient(error=errors.FloodWaitError(request=None, capture=42))) == ("flood", 42)
    assert _resolve(FakeClient(error=RuntimeError("disconnected"))) == ("unknown", None)
    kind, place = _resolve(FakeClient(entity=Channel(id=1, title="Новости", username="vasya", megagroup=False)))
    assert (kind, place.kind) == ("place", "channel")
    gone = FakeClient(
        entity=_tg_user(username="now_other"),
        resolved=SimpleNamespace(peer=SimpleNamespace(user_id=9), users=[], chats=[]),
    )
    assert _resolve(gone) == ("missing", None)


class UserEmpty:
    def __init__(self, id):
        self.id = id


def test_numeric_id_asks_telegram_when_the_session_has_no_hash():
    class Bare(FakeClient):
        async def get_entity(self, peer):
            raise ValueError("Could not find the input entity")

    client = Bare(resolved=[_tg_user(id=8827084733, first_name="Ира", username="ira_k")])
    kind, person = asyncio.run(who.resolve_user_id(client, 8827084733))
    assert kind == "person"
    assert person.first_name == "Ира"
    assert person.username == "ira_k"
    assert client.requests

    empty = Bare(resolved=[UserEmpty(8827084733)])
    assert asyncio.run(who.resolve_user_id(empty, 8827084733)) == ("unknown", None)

    cached = FakeClient(entity=_tg_user(id=8827084733, first_name="Ира", username="ira_k"))
    kind, person = asyncio.run(who.resolve_user_id(cached, 8827084733))
    assert kind == "person" and person.first_name == "Ира"
    assert cached.requests == []


def test_find_userbot_uses_only_a_connected_main_client(monkeypatch):
    class Client:
        def __init__(self, connected):
            self.connected = connected

        def is_connected(self):
            return self.connected

    live = Client(True)
    monkeypatch.setattr(sys.modules["__main__"], "main_userbot_client", Client(False), raising=False)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(main_userbot_client=live))
    assert who.find_userbot() is live
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(main_userbot_client=None))
    assert who.find_userbot() is None


# --- бюджет юзербота -------------------------------------------------------------

def test_budget_spaces_out_one_viewer():
    budget = who.UsernameBudget(per_viewer=5)
    assert budget.allow(1, 0)
    budget.spend(1, 0)
    assert not budget.allow(1, 1)
    assert budget.allow(2, 1)
    assert budget.allow(1, 5)


def test_budget_caps_the_window_and_the_day():
    budget = who.UsernameBudget(per_viewer=0, window=600, window_max=3, day_max=4)
    for viewer in range(3):
        budget.spend(viewer, 0)
    assert not budget.allow(9, 10)
    assert budget.allow(9, 600)
    budget.spend(9, 600)
    assert not budget.allow(10, 1300)
    assert budget.allow(10, 86400)


def test_budget_waits_out_a_flood():
    budget = who.UsernameBudget(per_viewer=0)
    budget.pause(30, 0)
    assert not budget.allow(1, 10)
    assert budget.allow(1, 30)


def test_budget_remembers_answers_for_a_while():
    budget = who.UsernameBudget(found_ttl=100, missing_ttl=10, cache_max=2)
    person = who.TgPerson(5, "Вася")
    budget.remember("Vasya", "person", person, 0)
    budget.remember("ghost", "missing", None, 0)
    assert budget.cached("vasya", 50) == ("person", person)
    assert budget.cached("ghost", 5) == ("missing", None)
    assert budget.cached("ghost", 10) is None
    assert budget.cached("vasya", 100) is None
    for i in range(5):
        budget.remember(f"user{i}", "missing", None, 200)
    assert len(budget._cache) <= 2
