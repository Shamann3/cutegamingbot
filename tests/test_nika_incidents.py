# -*- coding: utf-8 -*-
"""Ника: инциденты и админский контур — без живой БД."""

import pathlib

from bot.runtime.nika.incidents import (
    COMMAND_KINDS,
    MONEY_COMMANDS,
    actions_for,
    fingerprint_empty_ladder,
    fingerprint_refund,
)


_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_empty_ladder_has_money_and_pause_buttons():
    ids = {a["id"] for a in actions_for("empty_ladder")}
    assert {"force_tick", "force_topup", "pause_group", "pause_all"} <= ids


def test_refund_stuck_offers_return_not_print():
    ids = {a["id"] for a in actions_for("refund_stuck")}
    assert "retry_heal" in ids
    assert "force_topup" not in ids


def test_fingerprints_are_stable():
    assert fingerprint_empty_ladder(-1001612636292) == "empty_ladder:-1001612636292"
    assert fingerprint_refund(44) == "refund_stuck:44"


def test_money_commands_are_explicit_and_narrow():
    assert MONEY_COMMANDS <= set(COMMAND_KINDS)
    assert "pause_all" not in MONEY_COMMANDS
    assert "force_topup" in MONEY_COMMANDS


def test_schema_has_incident_tables_and_earnings_since():
    schema = _read("bot", "runtime", "nika", "schema.py")
    assert "CREATE TABLE IF NOT EXISTS nika_incidents" in schema
    assert "CREATE TABLE IF NOT EXISTS nika_operator_commands" in schema
    assert "earnings_since" in schema
    assert "nika_universe_sample" in schema
    assert "pause_all" in schema


def test_engine_raises_and_resolves_unfixable_only():
    engine = _read("bot", "runtime", "nika", "engine.py")
    assert "raise_incident" in engine
    assert "CODE_EMPTY_LADDER" in engine
    assert "process_operator_commands" in engine
    assert "FOR UPDATE SKIP LOCKED" not in engine  # claim живёт в store
    assert "invalidate_balance_cache" in engine


def test_store_claims_commands_with_skip_locked():
    store = _read("bot", "runtime", "nika", "store.py")
    assert "FOR UPDATE SKIP LOCKED" in store
    assert "maybe_sample_universe" in store
    assert "force_touch_group_action" in store


def test_admin_nika_never_updates_chatbalance():
    admin = _read("server", "admin_nika.py")
    assert "chatbalance" in admin  # читает
    assert "SET chatbalance" not in admin
    assert "UPDATE chat" not in admin
    assert "enqueue_command" in admin
    assert "_universe_now" in admin
    assert "ALL_BALANCES_EXCESS" in admin
    assert "days" in admin
    assert "_iter_buckets" in admin
    assert "extrema" in admin
    assert "hotList" in admin


def test_admin_routes_expose_pulse_and_actions():
    routes = _read("server", "admin_routes.py")
    assert '"/nika/pulse"' in routes
    assert '"/nika/action"' in routes
    assert "_require_project_creator(admin_id)" in routes


def test_panel_nav_nika_is_creator_only():
    nav = _read("admin", "src", "constants", "panelNav.js")
    assert "id: 'nika'" in nav
    assert "creatorOnly: true" in nav
    access = _read("server", "panel_access.py")
    assert '"id": "nika"' in access


def test_crisis_strip_exists():
    strip = _read("admin", "src", "components", "NikaCrisisStrip.jsx")
    assert "Критично" in strip
    assert "fetchNikaPulse" in strip
    shell = _read("admin", "src", "pages", "PanelShell.jsx")
    assert "NikaCrisisStrip" in shell
    assert "NikaSection" in shell
    section = _read("admin", "src", "pages", "sections", "NikaSection.jsx")
    assert "grp-page nika-page" in section
    assert "Все балансы" in section
    assert "NikaMoneyChart" in section
    assert "Только минусы" in section
    assert "NikaSpark" in section
    assert "Самый плюс" in section
    chart = _read("admin", "src", "components", "NikaMoneyChart.jsx")
    assert "все балансы" in chart
    css = _read("admin", "src", "styles", "nika.css")
    assert "nika-wallet" in css
    assert "nika-bar-plus" in css


def test_flow_calendar_and_extrema():
    import sys
    from datetime import datetime, timezone

    sys.path.insert(0, str(_ROOT / "server"))
    from admin_nika import _bucket_key, _extrema, _iter_buckets

    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 4, tzinfo=timezone.utc)
    days = _iter_buckets(start, end, "day")
    assert len(days) == 4
    assert _bucket_key(days[0], "day") == "2026-09-01"
    assert _bucket_key(days[-1], "day") == "2026-09-04"
    hours = _iter_buckets(
        datetime(2026, 9, 4, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 4, 12, tzinfo=timezone.utc),
        "hour",
    )
    assert [h.hour for h in hours] == [10, 11, 12]
    ext = _extrema([{"net": 10}, {"net": -4}, {"net": 0}])
    assert ext["plusBuckets"] == 1
    assert ext["minusBuckets"] == 1
    assert ext["best"]["net"] == 10
    assert ext["worst"]["net"] == -4
