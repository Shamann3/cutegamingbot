"""Права Telegram сотрудников проекта и восстановление при возврате в группу."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from group_realm import (
    STAFF_GROUP_ADMIN_TG_RIGHTS,
    STAFF_SENIOR_TG_DENIED,
    STAFF_SENIOR_TG_RIGHTS,
    _promote_body,
    apply_staff_project_prefix,
    restore_staff_admin_on_join,
    staff_role_prefix,
    staff_role_tg_rights,
    strip_staff_project_prefix,
)


def test_senior_project_admin_matches_telegram_screenshot():
    rights = set(STAFF_SENIOR_TG_RIGHTS)
    assert "can_delete_messages" in rights
    assert "can_restrict_members" in rights
    assert "can_pin_messages" in rights
    assert "can_manage_video_chats" in rights
    assert "can_promote_members" in rights  # теги + назначение админов
    assert "can_manage_chat" in rights
    for denied in STAFF_SENIOR_TG_DENIED:
        assert denied not in rights
    body = _promote_body(-100, 1, list(STAFF_SENIOR_TG_RIGHTS))
    assert body["is_anonymous"] is False
    assert body["can_change_info"] is False
    assert body["can_invite_users"] is False
    assert body["can_delete_messages"] is True
    assert body["can_restrict_members"] is True
    assert body["can_promote_members"] is True


def test_other_staff_match_group_administrator_tg_flags():
    junior = set(staff_role_tg_rights("junior_admin"))
    moderator = set(staff_role_tg_rights("moderator"))
    custom = set(staff_role_tg_rights("custom_helper"))
    group_admin = set(STAFF_GROUP_ADMIN_TG_RIGHTS)
    assert junior == group_admin
    assert moderator == group_admin
    assert custom == group_admin
    # У админа группы шире, чем у старшего проекта: инфо и инвайты.
    assert "can_change_info" in group_admin
    assert "can_invite_users" in group_admin
    assert "can_delete_messages" in group_admin
    assert "can_promote_members" in group_admin


def test_staff_prefixes_fit_telegram_limit():
    for role in ("senior_admin", "junior_admin", "moderator"):
        title = staff_role_prefix(role)
        assert 0 < len(title) <= 16


def test_owner_and_empty_get_no_tg_staff_pack():
    assert staff_role_tg_rights("owner") == []
    assert staff_role_tg_rights("") == []
    assert staff_role_tg_rights("applicant") == []


def test_restore_skips_non_official_chat():
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=None)

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm.ensure_tables", new=AsyncMock()
        ), patch("group_realm.db") as db_mod:
            db_mod.pool = pool
            result = await restore_staff_admin_on_join(-1001, 42)
        assert result["restored"] is False
        assert result["reason"] == "not_official"

    asyncio.run(run())


def test_restore_staff_role_calls_apply_for_official_chat():
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=1)
    apply = AsyncMock(return_value={"ok": True, "applied": 1, "prefix": "Ст.Админ/проекта", "faults": []})

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm.ensure_tables", new=AsyncMock()
        ), patch("group_realm.db") as db_mod, patch(
            "group_realm._active_staff_seat_chats", new=AsyncMock(return_value=set())
        ), patch(
            "group_realm._resolve_active_staff_role",
            new=AsyncMock(return_value="senior_admin"),
        ), patch("group_realm.apply_staff_project_prefix", new=apply):
            db_mod.pool = pool
            result = await restore_staff_admin_on_join(-1002, 77)
        assert result["ok"] is True
        assert result["restored"] is True
        assert result["via"] == "staff"
        apply.assert_awaited_once_with(77, "senior_admin", chat_ids=[-1002])

    asyncio.run(run())


def test_restore_seat_takes_priority_over_staff_role():
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=1)
    seat_restore = AsyncMock(return_value="В группе стоит префикс «Админ».")

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm.ensure_tables", new=AsyncMock()
        ), patch("group_realm.db") as db_mod, patch(
            "group_realm._active_staff_seat_chats",
            new=AsyncMock(return_value={-1003}),
        ), patch("group_realm._restore_seat_admin_in_chat", new=seat_restore), patch(
            "group_realm.apply_staff_project_prefix", new=AsyncMock()
        ) as apply:
            db_mod.pool = pool
            result = await restore_staff_admin_on_join(-1003, 88)
        assert result["via"] == "seat"
        assert result["restored"] is True
        seat_restore.assert_awaited_once_with(-1003, 88)
        apply.assert_not_awaited()

    asyncio.run(run())


def test_apply_staff_uses_senior_rights_pack():
    apply_title = AsyncMock(return_value="В группе стоит префикс «Ст.Админ/проекта».")

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm._is_creator", return_value=False
        ), patch("group_realm.ensure_tables", new=AsyncMock()), patch(
            "group_realm._active_staff_seat_chats", new=AsyncMock(return_value=set())
        ), patch(
            "group_realm._resolve_active_staff_role",
            new=AsyncMock(return_value="senior_admin"),
        ), patch("group_realm._apply_chat_title", new=apply_title):
            result = await apply_staff_project_prefix(11, "senior_admin", chat_ids=[-55])
        assert result["applied"] == 1
        assert set(result["rights"]) == set(STAFF_SENIOR_TG_RIGHTS)
        apply_title.assert_awaited_once()
        args = apply_title.await_args
        assert args.args[0] == -55
        assert args.args[2] == "Ст.Админ/проекта"
        assert set(args.kwargs["rights"]) == set(STAFF_SENIOR_TG_RIGHTS)

    asyncio.run(run())


def test_apply_staff_refreshes_seat_when_person_holds_group_post():
    seat_restore = AsyncMock(return_value="В группе стоит префикс «Админ».")
    apply_title = AsyncMock(return_value="В группе стоит префикс «Ст.Админ/проекта».")

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm._is_creator", return_value=False
        ), patch("group_realm.ensure_tables", new=AsyncMock()), patch(
            "group_realm._active_staff_seat_chats", new=AsyncMock(return_value={-10})
        ), patch(
            "group_realm._resolve_active_staff_role",
            new=AsyncMock(return_value="senior_admin"),
        ), patch("group_realm._restore_seat_admin_in_chat", new=seat_restore), patch(
            "group_realm._apply_chat_title", new=apply_title
        ):
            result = await apply_staff_project_prefix(11, "senior_admin", chat_ids=[-10, -20])
        assert result["applied"] == 2
        assert result["skippedSeats"] == 1
        seat_restore.assert_awaited_once_with(-10, 11)
        apply_title.assert_awaited_once()
        assert apply_title.await_args.args[0] == -20

    asyncio.run(run())


def test_strip_staff_skips_seated_chats_and_demotes_others():
    strip = AsyncMock(return_value="Админка снята.")

    async def run():
        with patch("group_realm.is_plain_user", return_value=False), patch(
            "group_realm._is_creator", return_value=False
        ), patch("group_realm.ensure_tables", new=AsyncMock()), patch(
            "group_realm._active_staff_seat_chats", new=AsyncMock(return_value={-10})
        ), patch("group_realm._strip_to_member", new=strip):
            result = await strip_staff_project_prefix(11, chat_ids=[-10, -20])
        assert result["stripped"] == 1
        assert result["skippedSeats"] == 1
        strip.assert_awaited_once_with(-20, 11)

    asyncio.run(run())
