from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_application_needs_the_rules_mark_not_a_channel_scrape():
    src = (ROOT / "server/group_realm.py").read_text(encoding="utf-8")
    start = src.index("async def group_apply")
    chunk = src[start:src.index("async def group_official")]
    assert "Сначала отметьте, что вы знаете правила" in chunk
    assert "load_channel_rules" not in chunk
    assert "notify_owners" in chunk
    assert "Вы уже администратор этой группы" not in chunk
    assert "Ключ кабинета уже есть" in chunk
    assert "holds_this" in chunk
    apps = src[src.index("async def group_applications"):src.index("async def group_decide")]
    assert "WHERE a.status = 'pending'" not in apps
    assert "already_seated" in apps
    status = src[src.index("async def cabinet_entry"):src.index("async def _issue_key")]
    assert "holds_seat" in status
    assert "has_key" in status
    routes = (ROOT / "server/admin_routes.py").read_text(encoding="utf-8")
    door = routes[routes.index("async def admin_auth_status"):routes.index("async def admin_register_start")]
    assert 'groupCanEnter": is_owner or bool(entry["hasKey"])' in door
    assert "groupHoldsSeat" in door
    assert "len(groups)" not in door
    decide = src[src.index("async def group_decide"):src.index("async def load_activity")]
    assert "send_telegram_message" in decide
    assert "Ваш ключ:" in decide
