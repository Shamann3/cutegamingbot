"""Вкладки панели сотрудника: карта роли и личное исключение, без базы."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_permissions import ROLE_JUNIOR, ROLE_MODERATOR, ROLE_OWNER
from panel_access import (
    access_for_maps,
    effective_sections_from_maps,
    effective_tabs_from_maps,
    permissions_for_sections,
)


def test_role_map_opens_and_closes_pages():
    defaults = {ROLE_JUNIOR: {"users": True, "economy": False}}
    sections = effective_sections_from_maps(ROLE_JUNIOR, defaults, {})
    assert "users" in sections
    assert "economy" not in sections


def test_personal_override_closes_a_page_the_role_has():
    defaults = {ROLE_MODERATOR: {"users": True, "moderation": True}}
    sections = effective_sections_from_maps(ROLE_MODERATOR, defaults, {"users": False})
    assert "users" not in sections
    assert "moderation" in sections


def test_closed_page_hides_its_inner_tabs():
    defaults = {ROLE_JUNIOR: {"staff": False, "staff.salaries": True}}
    tabs = effective_tabs_from_maps(ROLE_JUNIOR, defaults, {})
    assert "staff" not in tabs


def test_open_page_keeps_only_chosen_inner_tabs():
    defaults = {
        ROLE_JUNIOR: {
            "staff": True,
            "staff.salaries": True,
            "staff.applications": False,
        }
    }
    tabs = effective_tabs_from_maps(ROLE_JUNIOR, defaults, {})
    assert "salaries" in tabs["staff"]
    assert "applications" not in tabs["staff"]


def test_owner_keeps_every_page():
    sections = effective_sections_from_maps(ROLE_OWNER, {ROLE_OWNER: {"users": False}}, {"users": False})
    assert "users" in sections
    assert "panelAccess" in sections


def test_closed_players_page_drops_player_permission():
    opened = permissions_for_sections(ROLE_JUNIOR, ["users"])
    closed = permissions_for_sections(ROLE_JUNIOR, [])
    assert "view_players" in opened
    assert "view_players" not in closed


def test_panel_pages_never_grant_project_ban():
    perms = permissions_for_sections(ROLE_JUNIOR, ["users", "moderation", "economy"])
    assert "banfull" not in perms


def test_preview_matches_login_for_the_role():
    defaults = {ROLE_JUNIOR: {"users": True, "staff": True, "staff.salaries": False}}
    access = access_for_maps(ROLE_JUNIOR, defaults, {})
    sections = effective_sections_from_maps(ROLE_JUNIOR, defaults, {})
    assert access["sections"] == sections
    assert access["tabs"] == effective_tabs_from_maps(ROLE_JUNIOR, defaults, {}, sections)
    assert access["permissions"] == permissions_for_sections(ROLE_JUNIOR, sections)
    assert "salaries" not in access["tabs"]["staff"]


def test_personal_override_changes_preview_permissions():
    defaults = {ROLE_MODERATOR: {"users": True}}
    role_view = access_for_maps(ROLE_MODERATOR, defaults, {})
    person_view = access_for_maps(ROLE_MODERATOR, defaults, {"users": False})
    assert "view_players" in role_view["permissions"]
    assert "users" not in person_view["sections"]
    assert "view_players" not in person_view["permissions"]
