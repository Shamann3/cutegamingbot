import asyncio

from bot.funcs.translate_gate import (
    reset_translate_state,
    translate_async,
    translate_blocking,
    translate_many_blocking,
)


def setup_function():
    reset_translate_state()


def _clock_sleeper():
    state = {"n": 0.0, "sleeps": []}

    def clock():
        return state["n"]

    def sleeper(delay):
        state["sleeps"].append(delay)
        state["n"] += delay

    return state, clock, sleeper


def test_same_phrase_is_translated_once():
    calls = []

    def translate(text, source, target):
        calls.append(text)
        return "мир"

    state, clock, sleeper = _clock_sleeper()
    kwargs = dict(translate=translate, clock=clock, sleeper=sleeper)
    assert translate_blocking("hello", "ru", "en", **kwargs) == "мир"
    assert translate_blocking("hello", "ru", "en", **kwargs) == "мир"
    assert calls == ["hello"]
    assert state["sleeps"] == []


def test_second_different_phrase_waits_for_the_rate_gap():
    def translate(text, source, target):
        return text

    state, clock, sleeper = _clock_sleeper()
    kwargs = dict(translate=translate, clock=clock, sleeper=sleeper)
    translate_blocking("a", "ru", "en", **kwargs)
    translate_blocking("b", "ru", "en", **kwargs)
    assert state["sleeps"] == [0.25]


def test_rate_limit_retries_once_and_then_returns_the_translation():
    calls = []

    def translate(text, source, target):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("Server Error: You made too many requests to the server")
        return "готово"

    _, clock, sleeper = _clock_sleeper()
    result = translate_blocking("hi", "ru", "en", translate=translate, clock=clock, sleeper=sleeper)
    assert result == "готово"
    assert len(calls) == 2


def test_rate_limit_twice_returns_the_original_text():
    def translate(text, source, target):
        raise RuntimeError("too many requests")

    _, clock, sleeper = _clock_sleeper()
    assert translate_blocking("hi", "ru", "en", translate=translate, clock=clock, sleeper=sleeper) == "hi"


def test_empty_and_same_language_do_not_call_google():
    def translate(text, source, target):
        raise AssertionError("network")

    assert translate_blocking("   ", "ru", "en", translate=translate) == "   "
    assert translate_blocking("уже русский", "ru", "ru", translate=translate) == "уже русский"


def test_batch_translates_misses_in_one_call():
    seen = []

    def batch(texts, source, target):
        seen.append(list(texts))
        return ["один", "два"]

    def single(text, source, target):
        raise AssertionError("single")

    result = translate_many_blocking(
        ["one", "", "two"],
        "ru",
        "en",
        translate_batch=batch,
        translate=single,
    )
    assert result == ["один", "", "два"]
    assert seen == [["one", "two"]]
    again = translate_many_blocking(
        ["one", "two"],
        "ru",
        "en",
        translate_batch=batch,
        translate=single,
    )
    assert again == ["один", "два"]
    assert seen == [["one", "two"]]


def test_batch_failure_falls_back_to_single_calls():
    def batch(texts, source, target):
        raise RuntimeError("batch down")

    def single(text, source, target):
        return text.upper()

    _, clock, sleeper = _clock_sleeper()
    result = translate_many_blocking(
        ["a", "b"],
        "ru",
        "en",
        translate_batch=batch,
        translate=single,
        clock=clock,
        sleeper=sleeper,
    )
    assert result == ["A", "B"]


def test_async_wrapper_runs_the_blocking_translator():
    # Обёртка без подмены зовёт Google, поэтому проверяем только что цикл не рвётся
    # на пустой строке: сеть не нужна.
    assert asyncio.run(translate_async("  ", "ru", "en")) == "  "
