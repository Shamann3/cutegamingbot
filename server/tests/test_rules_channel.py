import asyncio

from rules_channel import clear_rules_cache, collect_channel_rules, parse_rules_html

PAGE = """
<div data-post="CuteRules/2" class="tgme_widget_message">
  <div class="tgme_widget_message_text js-message_text" dir="auto">Второе правило.<br/>Пишите спокойно.</div>
</div>
<div data-post="CuteRules/1" class="tgme_widget_message">
  <div class="tgme_widget_message_text js-message_text" dir="auto">Первое &amp; главное.</div>
</div>
<div data-post="Other/9" class="tgme_widget_message">
  <div class="tgme_widget_message_text">Чужой канал.</div>
</div>
<div data-post="CuteRules/3" class="tgme_widget_message text_not_supported_wrap">
  <div class="message_media_not_supported">Please open Telegram to view this post</div>
</div>
"""


def test_parser_keeps_channel_text_in_order_and_counts_hidden():
    readable, hidden = parse_rules_html(PAGE)
    assert hidden == 1
    assert [item["id"] for item in readable] == [1, 2]
    assert readable[0]["text"] == "Первое & главное."
    assert "Пишите спокойно." in readable[1]["text"]


def test_collect_refuses_partial_when_a_post_hides_its_text():
    async def fetch(url, follow):
        if url.endswith("/1?embed=1"):
            return 200, url, '<div data-post="CuteRules/1" class="text_not_supported_wrap"><div class="message_media_not_supported"></div></div>'
        return 200, url, '<div class="tgme_widget_message_error">Post not found</div>'

    clear_rules_cache()
    payload = asyncio.run(collect_channel_rules(fetch))
    assert payload["messages"] == []
    assert payload["hidden"] >= 1
    assert "не отдал" in payload["error"]


def test_collect_returns_every_visible_post():
    async def fetch(url, follow):
        if url.endswith("/1?embed=1"):
            return 200, url, '<div data-post="CuteRules/1"><div class="tgme_widget_message_text">Не ругаться.</div></div>'
        if url.endswith("/2?embed=1"):
            return 200, url, '<div data-post="CuteRules/2"><div class="tgme_widget_message_text">Не врать.</div></div>'
        return 200, url, "Post not found"

    payload = asyncio.run(collect_channel_rules(fetch))
    assert [item["text"] for item in payload["messages"]] == ["Не ругаться.", "Не врать."]
    assert payload["error"] == ""
