# -*- coding: utf-8 -*-
from bot.funcs.tasks_entry import (
    TASKS_ICON,
    TASKS_URL,
    is_tasks_ask,
    is_tasks_start,
    tasks_prompt_text,
)


def test_words_open_the_same_door():
    assert is_tasks_ask("задания")
    assert is_tasks_ask("  Челленжи ")
    assert is_tasks_ask("челленджи")
    assert not is_tasks_ask("задания бота")


def test_start_and_word_are_wired():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main = (root / "main.py").read_text(encoding="utf-8")
    balance = (root / "bot" / "funcs" / "balance.py").read_text(encoding="utf-8")
    assert "is_tasks_start(deep)" in main
    assert "async def _open_tasks_from_start" in main
    assert '"челленжи"' in main
    assert "is_tasks_ask(message.text)" in balance
    assert "TASKS_URL" in balance


def test_prompt_points_at_the_tasks_start():
    text = tasks_prompt_text()
    assert TASKS_ICON in text
    assert "<b>" in text
    assert is_tasks_start("tasks")
    assert is_tasks_start(" Tasks ")
    assert TASKS_URL.endswith("?start=tasks")
    assert not is_tasks_start("earn")
