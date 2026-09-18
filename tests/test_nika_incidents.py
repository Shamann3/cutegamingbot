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
    assert "Баланс этой группы" in section
    assert "CopyableId" in section
    assert "NikaMoneyChart" in section
    assert "Только минусы" in section
    assert "NikaSpark" in section
    assert "Самый плюс" in section
    assert "id: 'machine'" in section
    assert "nika-machine" in section
    assert "Следующая проверка" in section
    assert "Баланс групп" in section
    assert "Игры и кассы" in section
    assert "nika-meter" not in section
    assert "nika-src-track" not in section
    assert "слот" not in section.lower()
    assert "стол" not in section.lower()
    chart = _read("admin", "src", "components", "NikaMoneyChart.jsx")
    assert "все балансы" in chart.lower()
    assert "nika-chart-tip" in chart
    assert "Ближе" in chart
    assert "тыс" not in chart
    css = _read("admin", "src", "styles", "nika.css")
    assert "nika-wallet" in css
    assert "nika-bar-plus" in css
    assert "nika-machine" in css
    assert "nika-bal-value" in css
    assert "nika-flow-hero" in css
    assert "nika-chart-tip" in css
    assert "nika-id-line" in css
    assert "nika-meter" not in css
    assert "nika-src-track" not in css
    assert "filter: blur" not in css
    assert "flex-wrap: wrap" in css


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


def test_forecast_tick_paused_and_topup():
    import sys

    sys.path.insert(0, str(_ROOT / "server"))
    from admin_nika import forecast_tick
    from bot.config.config import GAME_COMMISSION_CHAT_ID
    from bot.runtime.nika.schema import FIRST_MANAGED_CHAT_ID, FIRST_MANAGED_TARGET

    paused = forecast_tick({"enabled": False}, [], [], [])
    assert paused["mode"] == "paused"
    assert paused["items"] == []

    row = {
        "chat_id": FIRST_MANAGED_CHAT_ID,
        "target_balance": FIRST_MANAGED_TARGET,
        "speed_mode": "medium",
        "dead_zone_pct": 0.05,
        "dead_zone_min": 100,
        "max_transfer": 1000,
        "max_daily_topup": 10000,
        "max_daily_sweep": 10000,
        "sweep_share": 0.25,
        "sweep_delay_sec": 3600,
        "sweep_cooldown_sec": 1800,
    }
    groups = [{
        "chatId": FIRST_MANAGED_CHAT_ID,
        "name": "Official",
        "balance": 0,
        "target": FIRST_MANAGED_TARGET,
        "gap": FIRST_MANAGED_TARGET,
        "enabled": True,
        "starving": True,
    }]
    ladder = [{"chatId": GAME_COMMISSION_CHAT_ID, "title": "комиссии игр", "balance": 800}]
    live = forecast_tick({"enabled": True, "dry_run": False}, [row], groups, ladder)
    assert live["mode"] == "live"
    assert live["items"][0]["action"] == "topup"
    assert 0 < live["items"][0]["amount"] < FIRST_MANAGED_TARGET
    assert "игры" in live["items"][0]["text"]

    dry_ladder = [{"chatId": GAME_COMMISSION_CHAT_ID, "title": "комиссии игр", "balance": 0}]
    blocked = forecast_tick({"enabled": True}, [row], groups, dry_ladder)
    assert blocked["items"][0]["action"] == "blocked"


class _FakeConn:
    async def execute(self, *_args, **_kwargs):
        return "OK"


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_exc):
        return False


class _FakePool:
    def acquire(self):
        return _Acquire(_FakeConn())


def test_ready_pool_accepts_admin_db_without_ensure_pool():
    import asyncio
    import sys

    sys.path.insert(0, str(_ROOT / "server"))
    from nika.schema import ensure_nika_schema, ready_nika_pool

    class AlreadyOpen:
        def __init__(self):
            self.pool = object()

    asyncio.run(ready_nika_pool(AlreadyOpen()))

    class Connects:
        def __init__(self):
            self.pool = None

        async def connect(self):
            self.pool = object()

    opened = Connects()
    asyncio.run(ready_nika_pool(opened))
    assert opened.pool is not None

    class Empty:
        pass

    try:
        asyncio.run(ready_nika_pool(Empty()))
    except RuntimeError as exc:
        assert "Пул соединений" in str(exc)
    else:
        raise AssertionError("пустой db должен падать")

    class AdminLike:
        def __init__(self):
            self.pool = _FakePool()

    asyncio.run(ensure_nika_schema(AdminLike()))


def test_admin_schema_ensure_is_once_and_duck_typed():
    admin = _read("server", "admin_nika.py")
    assert "await db.ensure_pool()" not in admin
    assert "_schema_ok" in admin
    assert "_SCHEMA_RETRY_SEC" in admin
    assert "ready_nika_pool" in _read("server", "nika", "schema.py")
    assert "ready_nika_pool" in _read("bot", "runtime", "nika", "schema.py")
    db_src = _read("server", "db.py")
    assert "async def ensure_pool" in db_src
    assert "ensure_nika_schema" in db_src
