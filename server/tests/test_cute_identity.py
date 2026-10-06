import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cute_identity import (
    ADOPT_USER_SQL,
    needs_telegram_profile,
    person_from_chat_member,
    person_from_telegram_chat,
)


def test_only_a_private_telegram_user_becomes_a_cute_profile():
    person = person_from_telegram_chat({
        "id": 42,
        "type": "private",
        "first_name": "Мира",
        "last_name": "К",
        "username": "@mira_k",
    })
    assert person == {"user_id": 42, "first_name": "Мира К", "username": "mira_k"}
    assert person_from_telegram_chat({"id": -100, "type": "supergroup", "title": "Чат"}) is None
    assert person_from_chat_member({
        "user": {"id": 7, "is_bot": True, "first_name": "Бот"},
    }) is None
    member = person_from_chat_member({
        "user": {"id": 7, "is_bot": False, "first_name": "Аня", "username": "anya"},
    })
    assert member["user_id"] == 7
    assert member["first_name"] == "Аня"
    assert member["username"] == "anya"


def test_telegram_is_asked_only_when_the_cute_profile_has_no_name():
    assert needs_telegram_profile(True, "Аня", 7) is False
    assert needs_telegram_profile(True, "", 7) is True
    assert needs_telegram_profile(True, "7", 7) is True
    assert needs_telegram_profile(False, "Аня", 7) is True


def test_adopt_writes_the_name_and_leaves_balance_alone():
    update = ADOPT_USER_SQL.upper().split("DO UPDATE", 1)[1]
    assert "FIRST_NAME" in update
    assert "USERNAME" in update
    assert "BALANCE" not in update
    assert "DATA" not in update
