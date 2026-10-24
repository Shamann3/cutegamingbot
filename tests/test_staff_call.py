"""Точное «админы» и /report с упоминаниями."""

from bot.funcs.staff_call import is_exact_admins, mention_chunks, report_note, without_spamblock
from bot.admins.mute import _is_staff_roster_command
from bot.games.invoke import command_line


def test_spamblock_is_not_called():
    people = without_spamblock(
        {1: "Анна", 2: "Борис", 3: "Пётр"},
        blocked={2},
        author_id=3,
    )
    assert people == [(1, "Анна")]


def test_admins_word_is_exact():
    assert is_exact_admins(command_line("админы"))
    assert is_exact_admins(command_line("  Админы  "))
    assert is_exact_admins(command_line("/админы"))
    assert is_exact_admins(command_line("/админы@CuteBot"))
    assert not is_exact_admins(command_line("админы привет"))
    assert not is_exact_admins(command_line("админы (рандомный текст)"))
    assert not is_exact_admins(command_line("привет админы"))
    assert _is_staff_roster_command("админы")
    assert not _is_staff_roster_command("админы привет")
    assert _is_staff_roster_command("кто админ")
    assert _is_staff_roster_command("/staff")


def test_report_keeps_optional_text():
    assert report_note(command_line("/report")) == ""
    assert report_note(command_line("/report спасите")) == "спасите"
    assert report_note(command_line("/report@CuteBot текст")) == "текст"
    assert report_note(command_line("репорт")) is None
    assert report_note(command_line("админы")) is None


def _kind(entity) -> str:
    kind = entity.type
    return getattr(kind, "value", kind)


def _slice(text: str, entity) -> str:
    raw = text.encode("utf-16-le")
    return raw[entity.offset * 2:(entity.offset + entity.length) * 2].decode("utf-16-le")


def test_mentions_cover_each_name():
    chunks = mention_chunks(
        [(7, "Анна"), (8, "Борис")],
        note="спам в чате",
        author_name="Пётр",
        author_username="petr",
    )
    text, entities = chunks[0]
    assert "Репорт" in text
    assert "Кто написал" in text
    assert "Пётр" in text
    assert "@petr" in text
    assert "Кого зовём" in text
    quotes = [entity for entity in entities if _kind(entity) == "blockquote"]
    assert len(quotes) == 1
    assert _slice(text, quotes[0]) == "спам в чате"
    mentions = [entity for entity in entities if _kind(entity) == "text_mention"]
    assert [_slice(text, entity) for entity in mentions] == ["Анна", "Борис"]
    assert [entity.user.id for entity in mentions] == [7, 8]


def test_report_without_text_still_shows_a_quote():
    text, entities = mention_chunks(
        [(1, "Анна")],
        note="",
        author_name="Пётр",
    )[0]
    quotes = [entity for entity in entities if _kind(entity) == "blockquote"]
    assert len(quotes) == 1
    assert "Без текста" in _slice(text, quotes[0])
    assert "Анна" in text


def test_long_list_repeats_the_request_on_the_next_message():
    people = [(index, f"Имя{index}") for index in range(1, 27)]
    chunks = mention_chunks(people, note="нужен админ прямо сейчас", author_name="Пётр")
    assert len(chunks) == 2
    second, entities = chunks[1]
    assert "Ещё зовём" in second
    quotes = [entity for entity in entities if _kind(entity) == "blockquote"]
    assert _slice(second, quotes[0]) == "нужен админ прямо сейчас"
