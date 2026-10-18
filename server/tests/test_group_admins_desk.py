"""Доступ к вкладке «Администраторы групп»."""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from group_realm import (
    _can_manage_group_admins_desk,
    _require_creator,
    _require_group_admins_desk,
    create_position,
    decide_admin_drop,
    group_appoint,
    group_applications,
    group_decide,
    group_dismiss,
    list_admin_drops,
    rights_board,
)


def test_creator_can_open_group_admins_desk():
    async def run():
        with patch("group_realm._is_creator", return_value=True):
            assert await _can_manage_group_admins_desk(42) is True
            await _require_group_admins_desk(42)

    asyncio.run(run())


def test_staff_with_tab_can_open_group_admins_desk():
    account = {
        "status": "active",
        "panelTabs": {"staff": ["groupAdmins", "applications"]},
    }

    async def run():
        with patch("group_realm._is_creator", return_value=False), patch(
            "admin_permissions.get_admin_account_security",
            new=AsyncMock(return_value=account),
        ):
            assert await _can_manage_group_admins_desk(7) is True

    asyncio.run(run())


def test_staff_without_tab_cannot_open_group_admins_desk():
    account = {
        "status": "active",
        "panelTabs": {"staff": ["applications"]},
    }

    async def run():
        with patch("group_realm._is_creator", return_value=False), patch(
            "admin_permissions.get_admin_account_security",
            new=AsyncMock(return_value=account),
        ):
            assert await _can_manage_group_admins_desk(7) is False
            with pytest.raises(HTTPException) as err:
                await _require_group_admins_desk(7)
            assert err.value.status_code == 403

    asyncio.run(run())


def test_operational_routes_use_group_admins_desk_gate():
    from group_realm import group_member_check

    for handler in (
        rights_board,
        group_applications,
        group_decide,
        list_admin_drops,
        group_appoint,
        group_dismiss,
        group_member_check,
    ):
        source = inspect.getsource(handler)
        assert "_require_group_admins_desk" in source
        assert "_require_creator(user_id)" not in source


def test_appoint_accepts_spamblock_term_fields():
    from group_realm import AppointBody

    body = AppointBody(
        chat_id=-100,
        user_id=1,
        position_id=2,
        term_start="2026-01-01",
        term_end="2026-12-31",
    )
    assert body.term_end == "2026-12-31"


def test_board_schedules_foreign_title_cleanup():
    source = inspect.getsource(rights_board)
    assert "schedule_title_reconcile" in source
    assert "titleCleanup" in source


def test_reconcile_rotates_and_strips_foreign_tags():
    from group_realm import reconcile_stale_admin_titles

    source = inspect.getsource(reconcile_stale_admin_titles)
    assert "_RECONCILE_CURSOR" in source
    assert "_strip_foreign_admin" in source
    assert "custom_title" in source or "тег" in source.lower() or "title" in source


def test_position_create_stays_creator_only():
    source = inspect.getsource(create_position)
    assert "_require_creator(user_id)" in source


def test_decide_admin_drop_uses_desk_gate():
    source = inspect.getsource(decide_admin_drop)
    assert "_can_manage_group_admins_desk" in source
    assert "_is_creator(int(decider_id))" not in source


def test_require_creator_still_blocks_non_creators():
    with patch("group_realm._is_creator", return_value=False):
        with pytest.raises(HTTPException) as err:
            _require_creator(99)
        assert err.value.status_code == 403


def test_staff_role_prefixes_fit_telegram_limit():
    from group_realm import STAFF_ROLE_PREFIXES, staff_role_prefix

    assert staff_role_prefix("senior_admin") == "Ст.Админ/проекта"
    assert staff_role_prefix("junior_admin") == "Мл.Админ/проекта"
    assert staff_role_prefix("moderator") == "Модер/проекта"
    assert staff_role_prefix("owner") == ""
    for title in STAFF_ROLE_PREFIXES.values():
        assert 0 < len(title) <= 16
