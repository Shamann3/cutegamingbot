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


def test_admin_door_asks_for_the_cabinet_key():
    app = _text("admin/src/App.jsx")
    start = app.index("const openGroup")
    chunk = app[start:app.index("if (screen === 'group-apply')")]
    assert "setScreen('group-key')" in chunk
    assert "readGroupEntry()" in chunk
    assert "setScreen('group-resume')" in chunk
    assert "hasTelegramInitData()" not in chunk
    realm = _text("server/group_realm.py")
    check = realm[realm.index("async def group_key_check"):realm.index("async def group_key_enter")]
    assert "_open_key" in check
    assert 'needCode": False' not in check
    enter = realm[realm.index("async def group_key_enter"):realm.index("async def group_key_resume")]
    assert "_open_key" in enter
    assert "entryPass" in enter
    resume = realm[realm.index("async def group_key_resume"):realm.index("async def _key_row")]
    assert "_pass_key_hash" in resume
    assert "Вход не узнан" in resume
    opened = realm[realm.index("async def _open_key"):realm.index("async def group_key_check")]
    assert "_key_row" in opened


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
    assert "entry_key" in issue
    assert "totp_secret" not in issue


def test_creator_can_open_another_persons_key():
    db = _text("server/admin_db.py")
    member = db[db.index("async def member_login_key"):db.index("async def unsuspend_member")]
    assert "login_key" in member
    assert "role <> 'applicant'" in member
    routes = _text("server/admin_routes.py")
    show = routes[routes.index("async def staff_show_member_key"):routes.index("async def staff_purge_member")]
    assert "sr_is_creator" in show
    assert "loginKey" in show
    assert "log_admin_action" not in show
    realm = _text("server/group_realm.py")
    off = realm[realm.index("async def group_access_off"):realm.index("async def group_access_key")]
    assert "entry_key = ''" in off
    look = realm[realm.index("async def group_access_show"):realm.index("async def group_prefix")]
    assert "is_project_creator" in look
    assert 'detail="Свой ключ здесь не показывается"' in look
    staff = _text("admin/src/pages/sections/StaffSection.jsx")
    assert "showStaffKey" in staff
    assert "showGroupKey" in staff
    shell = _text("admin/src/pages/GroupShell.jsx")
    assert "showGroupKey" in shell
    assert "isProjectCreator" in shell
