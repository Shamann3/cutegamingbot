"""«Кто ты» не пишет баланс и рефералов.

Человека, которого ещё нет в Куте, он сохраняет через ensure_punishment_profile:
имя из Telegram, пригласитель не назначается.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = (ROOT / "bot" / "funcs" / "profile.py").read_text(encoding="utf-8")
LOOKUP = (ROOT / "bot" / "funcs" / "who_lookup.py").read_text(encoding="utf-8")

WRITES = (
    "INSERT",
    "UPDATE ",
    "DELETE ",
    "add_data(",
    "add_or_update_user_info",
    "vgs_safe_add_or_update",
    "_adopt_person",
    "ADOPT_USER_SQL",
    "user_update_fields",
    "check_user_id_in_users",
    "add_ref",
    "update_or_insert_chatall",
)


def _between(start: str, end: str) -> str:
    a = PROFILE.index(start)
    return PROFILE[a:PROFILE.index(end, a)]


def _who_code() -> str:
    return "\n".join((
        _between("async def _who_chat_people", "# PROFILE STATE / RENDER HELPERS"),
        _between("async def _cute_profile_exists", "# OWN PROFILE COMMAND"),
        _between(
            "async def profile_pick_callback",
            '@dp.callback_query(lambda c: c.data and c.data.startswith("profwarn:"))',
        ),
    ))


def test_who_are_you_does_not_write_balance_or_referrals():
    code = _who_code() + LOOKUP
    for marker in WRITES:
        assert marker not in code, marker
    assert "ensure_punishment_profile" in code
    assert "add_ref" not in code
    assert "refferer" not in code


def test_person_outside_cute_is_saved_and_still_has_a_telegram_card():
    info = _between("async def get_user_information_in_who_are_you", "# OWN PROFILE COMMAND")
    assert "_who_save_from_telegram" in info
    assert "_who_show_outside_profile" in info
    outside = _between("async def _who_show_outside_profile", "async def get_user_information_in_who_are_you")
    assert "_who_telegram_card" in outside
    assert "Этого пользователя нет в нашем боте" not in PROFILE


def test_who_are_you_never_touches_the_withdraw_userbot():
    assert "withdraw" not in LOOKUP.lower()
    assert "withdraw" not in _who_code().lower()
    assert "main_userbot_client" in LOOKUP


def _trigger_parser():
    """profile.py тянет боевую базу, поэтому берём из него только две чистые функции."""
    tree = ast.parse(PROFILE)
    wanted = {"_normalize_spaces", "_extract_trigger_and_arg"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "profile.py", "exec"), namespace)
    return namespace["_extract_trigger_and_arg"]


@pytest.mark.parametrize("text,expected", [
    ("кто ты", ("кто ты", "")),
    ("Кто ты?", ("кто ты", "")),
    ("кто ты?!", ("кто ты", "")),
    ("ктоты", ("ктоты", "")),
    ("кто ты @vasya", ("кто ты", "@vasya")),
    ("кто ты, Вася", ("кто ты", "Вася")),
    ("кто  ты   Вася Пупкин", ("кто ты", "Вася Пупкин")),
    ("кто тыква", (None, "")),
    ("стоп кто ты", (None, "")),
])
def test_trigger_understands_punctuation(text, expected):
    assert _trigger_parser()(text) == expected


def test_pick_buttons_reach_the_hot_router():
    from bot.runtime.callback_registry_generated import PREFIX_HANDLERS

    assert PREFIX_HANDLERS["whopick:"] == ("bot.funcs.profile", "profile_pick_callback")
    assert 'c.data.startswith("whopick:")' in PROFILE
    assert 'WHO_PICK_PREFIX = "whopick"' in PROFILE
