# -*- coding: utf-8 -*-
import asyncio

from bot.funcs.motivation_diary import (
    LOCAL,
    open_diary,
    page_html,
    quote_from_payload,
    read_quote,
)


def test_zenquotes_payload_becomes_a_quote():
    found = quote_from_payload([{
        "q": "Success and failure come and go, but don't let them define you.",
        "a": "Kamal Ravikant",
        "h": "<blockquote>ignore</blockquote>",
    }])
    assert found == (
        "Success and failure come and go, but don't let them define you.",
        "Kamal Ravikant",
    )


def test_dummyjson_payload_becomes_a_quote():
    found = quote_from_payload({
        "id": 3,
        "quote": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
    })
    assert found[0].startswith("The only way")
    assert found[1] == "Steve Jobs"


def test_empty_and_broken_payloads_are_skipped():
    assert quote_from_payload(None) is None
    assert quote_from_payload([]) is None
    assert quote_from_payload({"quote": "short"}) is None
    assert quote_from_payload([{"q": "   ", "a": "X"}]) is None


def test_second_source_is_used_when_the_first_is_down():
    async def fetch(url):
        if "zenquotes" in url:
            raise RuntimeError("ssl")
        return 200, {"quote": "Keep going when it is hard to keep going.", "author": "Ada"}

    found = asyncio.run(read_quote(fetch))
    assert found == ("Keep going when it is hard to keep going.", "Ada")


def test_diary_translates_a_found_quote():
    async def fetch(url):
        return 200, {"q": "Believe you can and you are halfway there.", "a": "Theodore Roosevelt"}

    async def translate(text):
        return "Верь, что сможешь, и ты уже на полпути."

    page = asyncio.run(open_diary(fetch=fetch, translate=translate))
    assert "Верь, что сможешь" in page
    assert "Theodore Roosevelt" in page
    assert "<b>" in page
    assert "Не удалось" not in page


def test_diary_uses_a_russian_page_when_nothing_answers():
    async def fetch(url):
        return 500, None

    async def translate(text):
        raise AssertionError("translate")

    page = asyncio.run(open_diary(fetch=fetch, translate=translate))
    assert any(line in page for line, _author in LOCAL)
    assert "<b>" in page


def test_second_translator_saves_the_found_quote():
    async def fetch(url):
        return 200, {"q": "Believe you can and you are halfway there.", "a": "Roosevelt"}

    async def translate(text):
        return text

    def memory(text):
        return "Верь, что сможешь, и ты уже на полпути."

    page = asyncio.run(open_diary(fetch=fetch, translate=translate, memory=memory))
    assert "Верь, что сможешь" in page
    assert "Roosevelt" in page
    assert "Believe you can" not in page


def test_untranslated_english_does_not_reach_the_player():
    async def fetch(url):
        return 200, {"q": "Believe you can and you are halfway there.", "a": "Roosevelt"}

    async def translate(text):
        return text

    def memory(text):
        return text

    page = asyncio.run(open_diary(fetch=fetch, translate=translate, memory=memory))
    assert "Believe you can" not in page
    assert any(line in page for line, _author in LOCAL)


def test_page_escapes_markup():
    assert "<script>" not in page_html("Держись <script>", "Аня & Ко")
    assert "&lt;script&gt;" in page_html("Держись <script>", "Аня & Ко")
