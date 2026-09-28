import os

from bot.funcs.webapp_links import (
    mini_app_url,
    section_button_fields,
    webapp_page_url,
)


def test_group_button_is_a_direct_link_to_the_section():
    fields = section_button_fields("Открыть биржу", "market", private=False, icon="1")
    assert fields["url"] == "https://t.me/CuteGamingBot?startapp=market"
    assert fields["url"] == mini_app_url("market")
    assert "/cute" not in fields["url"]
    assert "web_app_url" not in fields
    assert fields["text"] == "Открыть биржу"


def test_private_button_opens_the_app_on_that_section(monkeypatch):
    monkeypatch.setenv("WEBAPP_URL", "https://cutegaming-ridbh.ondigitalocean.app/play")
    fields = section_button_fields("Открыть биржу", "market", private=True, icon="1")
    assert fields["web_app_url"] == "https://cutegaming-ridbh.ondigitalocean.app/play?startapp=market"
    assert "url" not in fields


def test_missing_webapp_url_falls_back_to_the_public_app(monkeypatch):
    monkeypatch.delenv("WEBAPP_URL", raising=False)
    assert webapp_page_url("farm") == "https://cutegaming-ridbh.ondigitalocean.app/?startapp=farm"


def test_removed_host_is_not_used_for_the_button(monkeypatch):
    monkeypatch.setenv("WEBAPP_URL", "https://cutegaming-mobet.ondigitalocean.app/")
    assert webapp_page_url("market") == "https://cutegaming-ridbh.ondigitalocean.app/?startapp=market"


def test_ngrok_url_is_not_used_for_the_button(monkeypatch):
    monkeypatch.setenv("WEBAPP_URL", "https://demo.ngrok.io/app")
    assert webapp_page_url("shop").startswith("https://cutegaming-ridbh.ondigitalocean.app/")
    assert os.getenv("WEBAPP_URL") == "https://demo.ngrok.io/app"
