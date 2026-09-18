"""Врезка учёта себестоимости в игровые точки — проверки по исходникам.

Живая БД этого проекта — продакшн, поэтому точки движения предметов
проверяем статически: что вызов учёта стоит ВНУТРИ той же транзакции,
что и изменение инвентаря, и что игровые правила рядом не поехали.
"""

import ast
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SERVER = _ROOT / "server"
for _path in (str(_ROOT), str(_SERVER)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

SERVER_DB = (_SERVER / "db.py").read_text(encoding="utf-8")
SHOP = (_ROOT / "bot" / "funcs" / "shop.py").read_text(encoding="utf-8")


def method_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"метод {name} не найден")


# --- отчисления в «фоновые заработки» ---------------------------------------


def test_background_earnings_chat_is_its_own_config_name():
    import config as server_config

    from bot.config.config import BACKGROUND_EARNINGS_CHAT_ID as bot_target
    from bot.config.config import TECH_CHAT_ID as bot_tech

    assert server_config.BACKGROUND_EARNINGS_CHAT_ID == -1004318525471
    assert bot_target == -1004318525471
    # Чёрный рынок остаётся отдельной сущностью — накопленное не переезжает.
    assert server_config.TECH_CHAT_ID == -1003855337972
    assert bot_tech == -1003855337972
    assert server_config.BACKGROUND_EARNINGS_CHAT_ID != server_config.TECH_CHAT_ID


def test_market_commission_goes_to_background_earnings():
    body = method_source(SERVER_DB, "buy_market_listing")
    assert "update_chat_balance(BACKGROUND_EARNINGS_CHAT_ID, commission)" in body
    assert "TECH_CHAT_ID" not in body


def test_shop_deposits_go_to_background_earnings():
    assert "SHOP_DEPOSIT_CHAT_ID = BACKGROUND_EARNINGS_CHAT_ID" in SHOP
    assert "-1003855337972" not in SHOP
    assert SHOP.count("target_chat_id=SHOP_DEPOSIT_CHAT_ID") == 3


# --- учёт стоит в той же транзакции, что и инвентарь ------------------------


@pytest.mark.parametrize(
    "method, call",
    [
        ("buy_shop_item", "item_lots.record_acquire_parts"),
        ("execute_craft", "item_lots.record_craft"),
        ("create_market_listing", "item_lots.escrow_hold"),
        ("buy_market_listing", "item_lots.record_acquire"),
        ("buy_market_listing", "item_lots.escrow_settle_sale"),
        ("cancel_market_listing", "item_lots.escrow_return"),
        ("plant_seed", "item_lots.record_consume"),
        ("water_plot", "item_lots.record_consume"),
        ("install_autowater", "item_lots.record_consume"),
        ("harvest_plot", "item_lots.record_acquire"),
        ("harvest_plot", "item_lots.record_consume"),
        ("claim_daily_seed", "item_lots.record_acquire"),
        ("claim_quest_reward", "item_lots.record_inventory_gain"),
        ("_try_grant_starter_pack", "item_lots.record_inventory_gain"),
    ],
)
def test_point_is_covered_inside_its_transaction(method, call):
    body = method_source(SERVER_DB, method)
    assert call in body, f"{method}: нет вызова {call}"
    if method == "_try_grant_starter_pack":
        return  # работает на conn, переданном уже открытой транзакцией
    tx_at = body.index("conn.transaction()")
    assert body.index(call) > tx_at, f"{method}: учёт вне транзакции"


@pytest.mark.parametrize(
    "module, method, call",
    [
        ("admin_users.py", "admin_adjust_item", "item_lots.record_acquire"),
        ("admin_users.py", "admin_adjust_item", "item_lots.record_consume"),
        ("admin_market.py", "admin_cancel_listing", "item_lots.escrow_return"),
        ("admin_farm.py", "_admin_force_harvest", "item_lots.record_inventory_gain"),
    ],
)
def test_admin_points_are_covered_inside_their_transaction(module, method, call):
    source = (_SERVER / module).read_text(encoding="utf-8")
    body = method_source(source, method)
    assert call in body
    assert body.index(call) > body.index("conn.transaction()")


def test_sanitize_drops_lots_together_with_items():
    body = method_source(SERVER_DB, "sanitize_user_items_against_dex")
    assert "item_lots.record_inventory_loss" in body


def test_craft_failure_is_logged_as_destroyed_items():
    body = method_source(SERVER_DB, "execute_craft")
    assert "success=rolled_success" in body
    # Игровое правило не тронуто: бросок по-прежнему secrets.randbelow(100).
    assert "secrets.randbelow(100) < success_percent" in body


def test_harvest_lots_are_unknown_cost_not_zero():
    body = method_source(SERVER_DB, "harvest_plot")
    assert "unit_cost=None" in body
    assert "source=item_lots.SOURCE_HARVEST" in body


def test_rewards_are_zero_cost_with_explicit_source():
    for method in ("claim_quest_reward", "claim_daily_seed", "_try_grant_starter_pack"):
        body = method_source(SERVER_DB, method)
        assert "unit_cost=0" in body
        assert "SOURCE_REWARD" in body


def test_shop_lot_uses_actually_paid_amount_not_list_price():
    body = method_source(SERVER_DB, "buy_shop_item")
    assert "item_lots.split_cost(cost, buy_qty)" in body
    assert "split_cost(full_cost" not in body


# --- инвариант «игрок ничего не заметил» ------------------------------------


def test_schema_is_created_in_lifespan_not_in_request_handler():
    app_src = (_SERVER / "app.py").read_text(encoding="utf-8")
    assert "ensure_item_cost_schema(db.pool)" in app_src
    lifespan = app_src.index("async def lifespan")
    assert app_src.index("ensure_item_cost_schema(db.pool)") > lifespan
    # DDL не должно быть ни в одной точке движения предметов.
    for method in ("buy_shop_item", "execute_craft", "buy_market_listing", "harvest_plot"):
        body = method_source(SERVER_DB, method)
        assert "CREATE TABLE" not in body
        assert "CREATE INDEX" not in body


def test_accounting_never_raises_into_game_code():
    src = (_SERVER / "item_lots.py").read_text(encoding="utf-8")
    # Ни одного немого глотания ошибок.
    assert not re.search(r"except Exception:\s*\n\s*pass", src)
    # Каждая публичная операция проходит через savepoint-обёртку.
    assert src.count("_guarded(") >= 8


def test_bot_shop_writes_inventory_and_lot_in_one_transaction():
    bot_db = (_ROOT / "bot" / "db_create" / "db.py").read_text(encoding="utf-8")
    body = method_source(bot_db, "_set_items_tx")
    assert "connection.transaction()" in body
    assert body.index("UPDATE users SET items") < body.index("record_acquire_parts")
    wrapper = method_source(bot_db, "set_items_with_cost")
    assert "_set_items_tx(" in wrapper
    assert SHOP.count("db.set_items_with_cost(") == 3


def test_bot_schema_bootstrap_runs_on_connect_not_per_query():
    bot_db = (_ROOT / "bot" / "db_create" / "db.py").read_text(encoding="utf-8")
    body = method_source(bot_db, "connect")
    assert "item_lots.ensure_item_cost_schema(self.pool)" in body


def test_reconciler_is_read_only():
    body = method_source(SERVER_DB, "reconcile_item_lots")
    assert "UPDATE users" not in body
    assert "reconcile_user" in body and "reconcile_and_report" in body
