from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_staff_disable_forgets_the_old_key():
    src = _text("server/admin_db.py")
    start = src.index("async def suspend_member")
    chunk = src[start:src.index("async def reissue_member_key")]
    assert "login_key = NULL" in chunk
    assert "status = 'suspended'" in chunk
    assert "role <> 'owner'" in chunk


def test_staff_reissue_only_while_access_is_off():
    src = _text("server/admin_db.py")
    start = src.index("async def reissue_member_key")
    chunk = src[start:src.index("async def unsuspend_member")]
    assert "login_key = $2" in chunk
    assert "status = 'active'" in chunk
    assert "status = 'suspended'" in chunk
    assert "role <> 'owner'" in chunk


def test_closed_login_does_not_restore_the_old_key():
    src = _text("server/admin_routes.py")
    start = src.index("async def _resolve_login_key_ok")
    chunk = src[start:src.index("def _login_status_guard")]
    assert 'account.get("status") == "active"' in chunk
    login = src[src.index("async def admin_login("):src.index("async def admin_login(") + 1800]
    assert login.index("_login_status_guard(account)") < login.index("_resolve_login_key_ok")


def test_group_access_off_kills_the_old_key_and_keeps_the_seat():
    src = _text("server/group_realm.py")
    assert "disabled BOOLEAN NOT NULL DEFAULT FALSE" in src
    assert "Доступ отключён. Нужен новый ключ от создателя" in src
    assert "k.disabled" in src
    off = src[src.index("async def group_access_off"):src.index("async def group_access_key")]
    assert "disabled = TRUE" in off
    assert "DELETE FROM epsilon_seats" not in off
    key = src[src.index("async def group_access_key"):src.index("async def group_prefix")]
    assert "_issue_key" in key
    issue = src[src.index("async def _issue_key"):src.index("async def _realm_log")]
    assert "disabled = FALSE" in issue
    assert "totp_secret" not in issue
