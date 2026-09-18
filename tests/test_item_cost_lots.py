"""Учёт себестоимости предметов: FIFO, стоимость по цепочке, безопасность.

Боевая БД в этом проекте — продакшн, поэтому тесты идут против компактной
заглушки asyncpg, которая повторяет ровно те запросы, что шлёт item_lots,
и — важно — воспроизводит поведение Postgres «ошибка внутри транзакции
отравляет её целиком». Без этого нельзя доказать главное свойство слоя:
срыв учёта не должен ронять игровую операцию.
"""

import asyncio
import copy
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SERVER = _ROOT / "server"
for _path in (str(_ROOT), str(_SERVER)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import item_lots  # noqa: E402


DEX_ROWS = [
    {"id": 290, "name": "🪵 Бревно", "name1": "justtree", "emoji": "🪵"},
    {"id": 294, "name": "💧 Вода", "name1": "water", "emoji": "💧"},
    {"id": 295, "name": "🪓 Топор", "name1": "axe", "emoji": "🪓"},
    {"id": 299, "name": "🌱 Саженец", "name1": "sajeneztree", "emoji": "🌱"},
    {"id": 301, "name": "🔮 Шар", "name1": "orb", "emoji": "🔮"},
]


class FailedTransactionError(Exception):
    """Аналог asyncpg.InFailedSQLTransactionError."""


class InjectedError(Exception):
    pass


class _Tx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn._snapshots.append(copy.deepcopy(self.conn.tables))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        snapshot = self.conn._snapshots.pop()
        if exc_type is not None:
            # ROLLBACK TO SAVEPOINT: состояние откатано, транзакция снова живая.
            self.conn.tables = snapshot
            self.conn.aborted = False
            return False
        return False


class FakeConn:
    """Заглушка соединения: понимает только запросы item_lots."""

    def __init__(self, *, fail_on=None):
        self.tables = {
            "item_cost_lots": [],
            "item_cost_burns": [],
            "item_cost_escrow": [],
            "item_cost_anomalies": [],
        }
        self._seq = {"item_cost_lots": 0, "item_cost_escrow": 0, "item_cost_anomalies": 0}
        self._snapshots = []
        self.aborted = False
        self.fail_on = fail_on  # подстрока запроса, на которой падаем
        self.queries = []

    def transaction(self):
        return _Tx(self)

    def _next_id(self, table):
        self._seq[table] += 1
        return self._seq[table]

    def _guard(self, query):
        self.queries.append(query)
        if self.aborted:
            raise FailedTransactionError("current transaction is aborted")
        if self.fail_on and self.fail_on in query:
            self.aborted = True
            raise InjectedError("injected failure")

    async def fetch(self, query, *args):
        self._guard(query)
        if "FROM dex" in query:
            return list(DEX_ROWS)
        if "FROM item_cost_lots" in query and "SUM(qty_left)" in query:
            totals = {}
            for row in self.tables["item_cost_lots"]:
                if row["user_id"] == args[0] and row["qty_left"] > 0:
                    totals[row["item_id"]] = totals.get(row["item_id"], 0) + row["qty_left"]
            return [{"item_id": k, "qty": v} for k, v in totals.items()]
        if "FROM item_cost_lots" in query:
            rows = [
                r
                for r in self.tables["item_cost_lots"]
                if r["user_id"] == args[0] and r["item_id"] == args[1] and r["qty_left"] > 0
            ]
            rows.sort(key=lambda r: (r["created_at"], r["id"]))
            return rows[: int(args[2])]
        if "FROM item_cost_escrow" in query:
            rows = [
                r
                for r in self.tables["item_cost_escrow"]
                if r["holder_kind"] == args[0] and r["holder_id"] == args[1] and r["qty_left"] > 0
            ]
            rows.sort(key=lambda r: r["id"])
            return rows
        raise AssertionError(f"незнакомый fetch: {query}")

    async def fetchval(self, query, *args):
        self._guard(query)
        if "INSERT INTO item_cost_lots" in query:
            row_id = self._next_id("item_cost_lots")
            if "qty_initial, qty_left, unit_cost, source" in query:  # ленивый unknown-лот
                row = {
                    "id": row_id,
                    "user_id": args[0],
                    "item_id": args[1],
                    "qty_initial": args[2],
                    "qty_left": 0,
                    "unit_cost": None,
                    "source": args[3],
                    "ref_kind": "",
                    "ref_id": "",
                    "parent_lot_ids": [],
                    "created_at": row_id,
                }
            else:
                row = {
                    "id": row_id,
                    "user_id": args[0],
                    "item_id": args[1],
                    "qty_initial": args[2],
                    "qty_left": args[2],
                    "unit_cost": args[3],
                    "source": args[4],
                    "ref_kind": args[5],
                    "ref_id": args[6],
                    "parent_lot_ids": list(args[7]),
                    "created_at": row_id,
                }
            self.tables["item_cost_lots"].append(row)
            return row_id
        raise AssertionError(f"незнакомый fetchval: {query}")

    async def execute(self, query, *args):
        self._guard(query)
        if "UPDATE item_cost_lots" in query:
            for row in self.tables["item_cost_lots"]:
                if row["id"] == args[0]:
                    row["qty_left"] -= args[1]
            return "UPDATE 1"
        if "UPDATE item_cost_escrow" in query:
            for row in self.tables["item_cost_escrow"]:
                if row["id"] == args[0]:
                    row["qty_left"] -= args[1]
            return "UPDATE 1"
        if "INSERT INTO item_cost_burns" in query:
            self.tables["item_cost_burns"].append(
                {
                    "user_id": args[0],
                    "item_id": args[1],
                    "quantity": args[2],
                    "cost_total": args[3],
                    "unknown_qty": args[4],
                    "reason": args[5],
                    "destroyed": args[6],
                    "ref_kind": args[7],
                    "ref_id": args[8],
                }
            )
            return "INSERT 0 1"
        if "INSERT INTO item_cost_escrow" in query:
            self.tables["item_cost_escrow"].append(
                {
                    "id": self._next_id("item_cost_escrow"),
                    "holder_kind": args[0],
                    "holder_id": args[1],
                    "user_id": args[2],
                    "item_id": args[3],
                    "qty_left": args[4],
                    "unit_cost": args[5],
                }
            )
            return "INSERT 0 1"
        if "INSERT INTO item_cost_anomalies" in query:
            self.tables["item_cost_anomalies"].append(
                {"user_id": args[0], "item_id": args[1], "kind": args[2], "detail": args[3]}
            )
            return "INSERT 0 1"
        raise AssertionError(f"незнакомый execute: {query}")


@pytest.fixture(autouse=True)
def _fresh_state():
    item_lots.reset_state_for_tests()
    yield
    item_lots.reset_state_for_tests()


def run(coro):
    return asyncio.run(coro)


def lots_of(conn, user_id, item_id):
    return [
        r
        for r in conn.tables["item_cost_lots"]
        if r["user_id"] == user_id and r["item_id"] == item_id
    ]


# --- чистая арифметика -------------------------------------------------------


def test_split_cost_keeps_total_exact():
    parts = item_lots.split_cost(100, 3)
    assert sum(p.unit_cost * p.quantity for p in parts) == 100
    assert sum(p.quantity for p in parts) == 3


def test_split_cost_zero_paid_is_zero_not_unknown():
    parts = item_lots.split_cost(0, 4)
    assert [(p.unit_cost, p.quantity) for p in parts] == [(0, 4)]


def test_total_cost_is_none_when_any_unit_unknown():
    result = item_lots.ConsumeResult(
        parts=[item_lots.CostPart(5, 1), item_lots.CostPart(None, 1)],
        known_cost=5,
        unknown_qty=1,
        quantity=2,
    )
    assert result.total_cost is None


# --- ключ предмета -----------------------------------------------------------


def test_canonical_key_resolves_name_and_emoji_to_dex_id():
    conn = FakeConn()

    async def scenario():
        by_name = await item_lots.canonical_item_key(conn, "🪵 Бревно")
        by_emoji = await item_lots.canonical_item_key(conn, "🪵")
        by_alias = await item_lots.canonical_item_key(conn, "justtree")
        by_id = await item_lots.canonical_item_key(conn, "290")
        return by_name, by_emoji, by_alias, by_id

    assert run(scenario()) == ("290", "290", "290", "290")


def test_unknown_key_is_kept_as_is():
    conn = FakeConn()
    assert run(item_lots.canonical_item_key(conn, "чтототакое")) == "чтототакое"


# --- FIFO --------------------------------------------------------------------


def test_fifo_takes_oldest_lot_first():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 3, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_acquire(
            conn, 1, "290", 3, unit_cost=99, source=item_lots.SOURCE_SHOP
        )
        return await item_lots.record_consume(
            conn, 1, "290", 4, reason=item_lots.REASON_CRAFT_FAIL
        )

    result = run(scenario())
    assert [(p.unit_cost, p.quantity) for p in result.parts] == [(10, 3), (99, 1)]
    assert result.known_cost == 10 * 3 + 99
    assert result.unknown_qty == 0


def test_partial_lot_keeps_remainder():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 5, unit_cost=7, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_consume(conn, 1, "290", 2, reason=item_lots.REASON_FARM_PLANT)

    run(scenario())
    assert [r["qty_left"] for r in lots_of(conn, 1, "290")] == [3]


def test_missing_history_creates_lazy_unknown_lot_not_zero_cost():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        return await item_lots.record_consume(
            conn, 1, "290", 4, reason=item_lots.REASON_CRAFT_FAIL
        )

    result = run(scenario())
    assert result.known_cost == 10
    assert result.unknown_qty == 3
    assert result.total_cost is None
    lazy = [r for r in conn.tables["item_cost_lots"] if r["source"] == item_lots.SOURCE_UNKNOWN]
    assert len(lazy) == 1
    assert lazy[0]["unit_cost"] is None
    assert lazy[0]["qty_initial"] == 3


def test_burn_journal_records_reason_cost_and_unknown_split():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=25, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_consume(
            conn, 1, "290", 3, reason=item_lots.REASON_CRAFT_FAIL, ref_id="42"
        )

    run(scenario())
    burn = conn.tables["item_cost_burns"][0]
    assert burn["reason"] == item_lots.REASON_CRAFT_FAIL
    assert burn["quantity"] == 3
    assert burn["cost_total"] == 50
    assert burn["unknown_qty"] == 1
    assert burn["destroyed"] is True
    assert burn["ref_id"] == "42"


def test_consume_many_locks_items_in_sorted_order():
    """Одинаковый порядок блокировок у всех вызывающих = нет взаимоблокировок."""
    conn = FakeConn()

    async def scenario():
        for item_id in ("301", "290"):
            await item_lots.record_acquire(
                conn, 1, item_id, 1, unit_cost=1, source=item_lots.SOURCE_SHOP
            )
        await item_lots.record_consume_many(
            conn, 1, {"301": 1, "290": 1}, reason=item_lots.REASON_CRAFT_FAIL
        )

    run(scenario())
    order = [b["item_id"] for b in conn.tables["item_cost_burns"]]
    assert order == ["290", "301"]


# --- стоимость по цепочке ----------------------------------------------------


def test_gift_copies_cost_from_sender_lots_without_recursion():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=40, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_gift(conn, 1, 2, "290", 2)
        # Второе звено цепочки: получатель дарит дальше.
        await item_lots.record_gift(conn, 2, 3, "290", 2)

    run(scenario())
    third = sorted(
        (r["unit_cost"], r["qty_left"]) for r in lots_of(conn, 3, "290") if r["qty_left"] > 0
    )
    assert third == [(10, 1), (40, 1)]


def test_gift_is_not_counted_as_destroyed():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_gift(conn, 1, 2, "290", 1)

    run(scenario())
    assert conn.tables["item_cost_burns"][0]["destroyed"] is False


def test_craft_success_result_costs_sum_of_ingredients():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=15, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_acquire(
            conn, 1, "294", 1, unit_cost=5, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_craft(
            conn, 1, {"290": 2, "294": 1}, success=True, result_ref="301", ref_id="7"
        )

    run(scenario())
    result_lot = lots_of(conn, 1, "301")[0]
    assert result_lot["unit_cost"] == 35
    assert result_lot["source"] == item_lots.SOURCE_CRAFT
    assert all(b["destroyed"] is False for b in conn.tables["item_cost_burns"])


def test_craft_with_unknown_ingredient_gives_unknown_result_not_understated():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=15, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_craft(
            conn, 1, {"290": 1, "294": 1}, success=True, result_ref="301"
        )

    run(scenario())
    assert lots_of(conn, 1, "301")[0]["unit_cost"] is None


def test_craft_fail_burns_ingredients_and_makes_no_result():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=15, source=item_lots.SOURCE_SHOP
        )
        return await item_lots.record_craft(
            conn, 1, {"290": 2}, success=False, result_ref="301"
        )

    result = run(scenario())
    assert result.known_cost == 30
    assert lots_of(conn, 1, "301") == []
    burn = conn.tables["item_cost_burns"][0]
    assert burn["reason"] == item_lots.REASON_CRAFT_FAIL
    assert burn["destroyed"] is True


# --- биржа -------------------------------------------------------------------


def test_cancelled_listing_returns_original_cost():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=60, source=item_lots.SOURCE_SHOP
        )
        await item_lots.escrow_hold(conn, 1, "290", 2, holder_id=77)
        assert sum(r["qty_left"] for r in lots_of(conn, 1, "290")) == 0
        await item_lots.escrow_return(conn, 1, "290", 2, holder_id=77)

    run(scenario())
    live = [(r["unit_cost"], r["qty_left"]) for r in lots_of(conn, 1, "290") if r["qty_left"] > 0]
    assert live == [(60, 2)]


def test_sale_settles_seller_cost_and_is_not_a_burn():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=60, source=item_lots.SOURCE_SHOP
        )
        await item_lots.escrow_hold(conn, 1, "290", 1, holder_id=88)
        await item_lots.escrow_settle_sale(conn, 1, "290", 1, holder_id=88)
        await item_lots.record_acquire(
            conn,
            2,
            "290",
            1,
            unit_cost=100,
            source=item_lots.SOURCE_MARKET,
            ref_id="88",
        )

    run(scenario())
    sold = [b for b in conn.tables["item_cost_burns"] if b["reason"] == item_lots.REASON_MARKET_SOLD]
    assert sold[0]["cost_total"] == 60
    assert sold[0]["destroyed"] is False
    assert lots_of(conn, 2, "290")[0]["unit_cost"] == 100


# --- разница инвентаря -------------------------------------------------------


def test_inventory_gain_records_only_what_actually_increased():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_inventory_gain(
            conn,
            1,
            {"290": 2, "294": 1},
            {"290": 5, "294": 1, "301": 3},
            unit_cost=0,
            source=item_lots.SOURCE_REWARD,
            ref_kind="quest",
        )

    run(scenario())
    gained = {r["item_id"]: r["qty_initial"] for r in conn.tables["item_cost_lots"]}
    assert gained == {"290": 3, "301": 3}
    assert all(r["unit_cost"] == 0 for r in conn.tables["item_cost_lots"])


def test_inventory_gain_matches_keys_across_name_and_id_formats():
    """Бот пишет инвентарь именами, сервер — dex id; лот должен быть один."""
    conn = FakeConn()

    async def scenario():
        await item_lots.record_inventory_gain(
            conn,
            1,
            {"🪵 Бревно": 2},
            {"290": 3},
            unit_cost=0,
            source=item_lots.SOURCE_REWARD,
        )

    run(scenario())
    assert [(r["item_id"], r["qty_initial"]) for r in conn.tables["item_cost_lots"]] == [("290", 1)]


# --- главное требование владельца: учёт не может сломать игру ----------------


def test_failed_accounting_does_not_poison_outer_transaction():
    conn = FakeConn(fail_on="INSERT INTO item_cost_lots")

    async def scenario():
        async with conn.transaction():  # «игровая» транзакция
            result = await item_lots.record_acquire(
                conn, 1, "290", 1, unit_cost=10, source=item_lots.SOURCE_SHOP
            )
            assert result is None
            # Внешняя транзакция обязана остаться рабочей.
            assert conn.aborted is False
            conn.fail_on = None
            await item_lots.record_consume(conn, 1, "290", 1, reason=item_lots.REASON_FARM_PLANT)
        return True

    assert run(scenario()) is True
    assert conn.tables["item_cost_burns"][0]["quantity"] == 1


def test_failure_is_written_to_anomaly_log_not_swallowed():
    conn = FakeConn(fail_on="INSERT INTO item_cost_lots")

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=10, source=item_lots.SOURCE_SHOP
        )

    run(scenario())
    anomaly = conn.tables["item_cost_anomalies"][0]
    assert anomaly["kind"] == "acquire_failed"
    assert "InjectedError" in anomaly["detail"]


def test_consume_failure_reports_not_ok_and_treats_cost_as_unknown():
    conn = FakeConn(fail_on="FROM item_cost_lots")

    async def scenario():
        return await item_lots.record_consume(
            conn, 1, "290", 3, reason=item_lots.REASON_CRAFT_FAIL
        )

    result = run(scenario())
    assert result.ok is False
    assert result.total_cost is None
    assert result.unknown_qty == 3


def test_gift_with_broken_sender_side_still_gives_recipient_a_lot():
    conn = FakeConn(fail_on="FROM item_cost_lots")

    async def scenario():
        await item_lots.record_gift(conn, 1, 2, "290", 2)

    run(scenario())
    assert lots_of(conn, 2, "290")[0]["unit_cost"] is None


# --- сверка ------------------------------------------------------------------


def test_reconcile_marks_legacy_gap_separately_from_real_drift():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        await item_lots.record_acquire(
            conn, 1, "294", 5, unit_cost=1, source=item_lots.SOURCE_SHOP
        )
        return await item_lots.reconcile_user(conn, 1, {"290": 9, "294": 2})

    report = run(scenario())
    by_item = {r["itemId"]: r for r in report}
    assert by_item["290"]["kind"] == "legacy_uncovered"
    assert by_item["290"]["diff"] == -7
    assert by_item["294"]["kind"] == "lots_exceed_inventory"
    assert by_item["294"]["diff"] == 3


def test_reconcile_is_silent_when_layers_match():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "290", 2, unit_cost=10, source=item_lots.SOURCE_SHOP
        )
        return await item_lots.reconcile_user(conn, 1, {"🪵 Бревно": 2})

    assert run(scenario()) == []


def test_reconcile_and_report_logs_only_real_drift():
    conn = FakeConn()

    async def scenario():
        await item_lots.record_acquire(
            conn, 1, "294", 5, unit_cost=1, source=item_lots.SOURCE_SHOP
        )
        await item_lots.reconcile_and_report(conn, 1, {"294": 2, "290": 3})

    run(scenario())
    kinds = [a["kind"] for a in conn.tables["item_cost_anomalies"]]
    assert kinds == ["reconcile_drift"]


# --- схема -------------------------------------------------------------------


def test_schema_uses_timestamptz_everywhere_and_no_text_dates():
    sql = item_lots.SCHEMA_SQL
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in sql
    assert not re.search(r"created_at\s+TEXT", sql)
    assert sql.count("TIMESTAMPTZ") == 4


def test_growing_tables_have_indexes_for_their_hot_queries():
    sql = item_lots.SCHEMA_SQL
    assert "item_cost_lots_fifo_idx" in sql and "WHERE qty_left > 0" in sql
    for name in (
        "item_cost_burns_created_idx",
        "item_cost_burns_reason_idx",
        "item_cost_burns_user_idx",
        "item_cost_escrow_holder_idx",
        "item_cost_anomalies_created_idx",
    ):
        assert name in sql
    assert sql.count("CREATE TABLE IF NOT EXISTS") == 4
    assert "CREATE INDEX IF NOT EXISTS" in sql
    assert "CREATE INDEX ON" not in sql


def test_accounting_is_disabled_until_schema_is_ready():
    item_lots._schema_ready = False
    item_lots._disabled_until = 0.0
    try:
        assert item_lots.accounting_enabled() is False
        conn = FakeConn()
        assert run(item_lots.record_acquire(
            conn, 1, "290", 1, unit_cost=1, source=item_lots.SOURCE_SHOP
        )) is None
        assert conn.tables["item_cost_lots"] == []
    finally:
        item_lots.reset_state_for_tests()
