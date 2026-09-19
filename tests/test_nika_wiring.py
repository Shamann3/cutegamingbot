# -*- coding: utf-8 -*-
"""Ника: врезки в бота и самолечение — проверки по исходникам, без живой БД."""

import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_atomic_move_locks_and_updates_both_sides_in_one_transaction():
    engine = _read("bot", "runtime", "nika", "engine.py")
    assert "FOR UPDATE" in engine
    assert "SET chatbalance = chatbalance - $1" in engine
    assert "SET chatbalance = chatbalance + $1" in engine
    assert "WHERE chat_id = $2 AND chatbalance >= $1" in engine
    assert "invalidate_balance_cache" in engine
    assert "stale_pending_abandoned" in engine
    assert "UndefinedTableError" in engine
    assert "process_operator_commands" in engine
    assert "run_operator_pass" in engine
    assert "now_sweep" in engine
    assert "plan_drain_sweep" in engine
    assert "CODE_EMPTY_LADDER" in engine
    assert "maybe_sample_universe" in engine
    assert "announce_tech_plus" in engine
    assert "pick_sweep_dest" in engine
    assert "apply_sweep_speed" in engine


def test_worker_heals_schema_and_does_not_die():
    worker = _read("bot", "runtime", "nika", "worker.py")
    assert "ensure_nika_schema" in worker
    assert "CancelledError" in worker
    assert "create_task(_loop())" in worker
    assert "create_task(_command_loop())" in worker
    assert "run_operator_pass" in worker


def test_emergency_off_is_one_sql_update():
    store = _read("bot", "runtime", "nika", "store.py")
    assert "SET enabled = FALSE" in store
    assert "disable_system" in store


def test_main_starts_schema_and_worker():
    main = _read("main.py")
    assert "ensure_nika_schema" in main
    assert main.count("start_nika_worker") >= 2
    assert "set_group_sync_fn(add_or_update_group_info)" in main


def test_admin_nika_does_not_import_bot_package():
    text = _read("server", "admin_nika.py")
    assert "from bot." not in text
    assert "import bot" not in text
    assert "from nika.policy import" in text
    assert "await db.ensure_pool()" not in text
    assert (_ROOT / "server" / "nika" / "policy.py").is_file()
    assert (_ROOT / "server" / "nika" / "ids.py").is_file()
    assert (_ROOT / "server" / "nika" / "lookup.py").is_file()


def test_admin_nika_imports_when_bot_package_missing():
    import os
    import subprocess
    import sys

    server = str(_ROOT / "server")
    env = os.environ.copy()
    env["PYTHONPATH"] = server
    env.pop("PYTHONHOME", None)
    code = (
        "from nika.policy import SOURCE_LADDER, plan_topup, plan_drain_sweep, GroupPolicy, pick_sweep_dest, apply_sweep_speed; "
        "from nika.store import policy_from_row, forbidden_managed_ids; "
        "from nika.incidents import actions_for; "
        "from nika.schema import FIRST_MANAGED_TARGET; "
        "p = GroupPolicy(chat_id=1, target_balance=5000); "
        "print(len(SOURCE_LADDER), plan_topup(p, balance=0).action, FIRST_MANAGED_TARGET, "
        "actions_for('empty_ladder')[0]['id'], len(forbidden_managed_ids()), bool(policy_from_row))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=server,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "topup" in result.stdout
    assert "5000" in result.stdout


def test_balance_sync_fn_is_optional():
    src = _read("bot", "db_create", "db.py")
    assert "self.group_sync_fn = None" in src
    assert 'sync_fn = getattr(self, "group_sync_fn", None)' in src
    assert "if self.group_sync_fn is None:" not in src.split("async def __ensure_chatrow_exists__", 1)[1].split("async def", 1)[0]


def test_game_commission_goes_to_commission_cashbox():
    body = _read("bot", "funcs", "growth_fund.py")
    assert "GAME_COMMISSION_CHAT_ID" in body
    assert "commission_chat = int(getattr(cfg, \"GAME_COMMISSION_CHAT_ID\"" in body


def test_jericho_ignores_technical_groups():
    src = _read("bot", "db_create", "db.py")
    fn = src.split("async def get_group_economy_pressure_snapshot", 1)[1]
    fn = fn.split("async def get_jericho_mode_metrics", 1)[0]
    assert fn.count("COALESCE(is_technical, FALSE) = FALSE") >= 2


def test_schema_uses_timestamptz_and_idempotency():
    schema = _read("bot", "runtime", "nika", "schema.py")
    assert "TIMESTAMPTZ" in schema
    assert "uq_nika_transfer_idem" in schema
    assert "idx_nika_transfer_pending" in schema
    assert "FIRST_MANAGED_CHAT_ID = -1001612636292" in schema
    assert "FIRST_MANAGED_TARGET = 5000" in schema
    assert "sweep_speed" in schema
    assert "BETWEEN 15 AND 3600" in schema


def test_group_lookup_accepts_id_username_name_and_links():
    import sys

    server = str(_ROOT / "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    from nika.lookup import normalize_group_query, parse_group_ref, pick_resolved_hit

    assert normalize_group_query("https://t.me/CuteClub") == "CuteClub"
    assert normalize_group_query("@CuteClub") == "CuteClub"
    assert parse_group_ref("t.me/c/2574123456/12")["chat_id"] == -1002574123456
    assert parse_group_ref("-1001612636292")["kind"] == "id"
    assert parse_group_ref("https://telegram.me/joinchat/AAAA")["kind"] == "invite"
    assert parse_group_ref("Большая Чёрная")["kind"] == "name"

    hits = [
        {"chatId": 1, "name": "Большая Чёрная", "username": "bch", "forbidden": False},
        {"chatId": 2, "name": "Другая БЧ", "username": "other", "forbidden": False},
        {"chatId": 3, "name": "Служебная", "username": "tech", "forbidden": True},
    ]
    one = pick_resolved_hit(hits, "@bch")
    assert one["ok"] is True
    assert one["chatId"] == 1
    many = pick_resolved_hit(hits, "Чёрная")
    assert many["ok"] is False
    assert len(many["candidates"]) == 2
    named = pick_resolved_hit(hits, "Большая Чёрная")
    assert named["ok"] is True
    assert named["chatId"] == 1
