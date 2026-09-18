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
    assert "CODE_EMPTY_LADDER" in engine
    assert "maybe_sample_universe" in engine
    assert "announce_tech_plus" in engine


def test_worker_heals_schema_and_does_not_die():
    worker = _read("bot", "runtime", "nika", "worker.py")
    assert "ensure_nika_schema" in worker
    assert "CancelledError" in worker
    assert "create_task(_loop())" in worker


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
    assert (_ROOT / "server" / "nika" / "policy.py").is_file()
    assert (_ROOT / "server" / "nika" / "ids.py").is_file()


def test_admin_nika_imports_when_bot_package_missing():
    import os
    import subprocess
    import sys

    server = str(_ROOT / "server")
    env = os.environ.copy()
    env["PYTHONPATH"] = server
    env.pop("PYTHONHOME", None)
    code = (
        "from nika.policy import SOURCE_LADDER, plan_topup, GroupPolicy; "
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
