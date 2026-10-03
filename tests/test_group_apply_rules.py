from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_application_needs_the_rules_mark_not_a_channel_scrape():
    src = (ROOT / "server/group_realm.py").read_text(encoding="utf-8")
    start = src.index("async def group_apply")
    chunk = src[start:src.index("async def group_official")]
    assert "Сначала отметьте, что вы знаете правила" in chunk
    assert "load_channel_rules" not in chunk
    assert "notify_owners" in chunk
    decide = src[src.index("async def group_decide"):src.index("async def load_activity")]
    assert "send_telegram_message" in decide
    assert "Ваш ключ:" in decide
