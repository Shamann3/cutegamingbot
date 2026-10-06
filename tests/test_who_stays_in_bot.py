from pathlib import Path


def test_who_are_you_says_the_person_is_not_in_the_bot_and_does_not_call_telegram():
    root = Path(__file__).resolve().parents[1]
    text = (root / "bot" / "funcs" / "profile.py").read_text(encoding="utf-8")
    marker = text.index("NOT_IN_BOT_HTML = ")
    start = text.index("async def get_user_who_are_you")
    end = text.index("# OWN PROFILE COMMAND")
    chunk = text[marker:end]
    assert start > marker
    assert "Этого пользователя нет в нашем боте" in chunk
    assert "NOT_IN_BOT_HTML" in text[start:end]
    assert "get_chat" not in chunk
    assert "getChat" not in chunk
    assert "INSERT INTO users" not in chunk
