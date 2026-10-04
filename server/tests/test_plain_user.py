"""Обычный игрок не остаётся создателем, владельцем или сотрудником панели."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_db import _PLAIN_ACCESS_SQL
from admin_soft_restart import is_project_creator
from config import PLAIN_USER_IDS, is_plain_user, public_creator_id
from deed_sort import _blocked_ids_sql

PLAIN = 6908672757


def test_listed_person_is_a_plain_user():
    assert PLAIN in PLAIN_USER_IDS
    assert is_plain_user(PLAIN) is True
    assert is_plain_user(6801702632) is False


def test_plain_user_is_not_creator_even_if_the_id_is_configured(monkeypatch):
    import config

    monkeypatch.setattr(config, "PROJECT_CREATOR_ID", PLAIN)
    assert is_project_creator(PLAIN) is False
    assert public_creator_id() == 6801702632
    assert public_creator_id() != PLAIN


def test_owner_and_admin_lists_drop_the_plain_user(monkeypatch):
    import config

    monkeypatch.setattr(config, "OWNER_USER_IDS", "6801702632,6908672757")
    monkeypatch.setattr(config, "ADMIN_USER_IDS", "6908672757,6488580935")
    assert PLAIN not in config.owner_user_ids()
    assert 6801702632 in config.owner_user_ids()
    assert PLAIN not in config.admin_user_ids()
    assert 6488580935 in config.admin_user_ids()


def test_owner_list_of_only_the_plain_user_does_not_promote_everyone(monkeypatch):
    import config

    monkeypatch.setattr(config, "OWNER_USER_IDS", "6908672757")
    monkeypatch.setattr(config, "ADMIN_USER_IDS", "6488580935")
    assert config.owner_user_ids() == frozenset()


def test_sort_chain_blocks_the_plain_user():
    assert str(PLAIN) in _blocked_ids_sql()


def test_startup_strip_removes_access_rows_only():
    joined = "\n".join(_PLAIN_ACCESS_SQL)
    assert "DELETE FROM admin_accounts" in joined
    assert "DELETE FROM epsilon_group_keys" in joined
    assert "DELETE FROM epsilon_seats" in joined
    assert "users" not in joined
    assert "staff_actions" not in joined
