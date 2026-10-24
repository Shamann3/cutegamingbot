"""Точное «админы» и /report с упоминаниями."""

from bot.funcs.staff_call import is_exact_admins, mention_chunks, report_note
from bot.admins.mute import _is_staff_roster_command
from bot.games.invoke import command_line


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


def test_mentions_cover_each_name():
    chunks = mention_chunks([(7, "Анна"), (8, "Борис")], note="спам")
    text, entities = chunks[0]
    assert "спам" in text
    assert len(entities) == 2
    for entity, name in zip(entities, ("Анна", "Борис")):
        raw = text.encode("utf-16-le")
        piece = raw[entity.offset * 2:(entity.offset + entity.length) * 2].decode("utf-16-le")
        assert piece == name
        assert entity.user.id in {7, 8}
