"""Счётчики главной админки: вызовы бота и оборот кут в играх.

Без Postgres: пул и соединение подменяются фейками, которые запоминают запросы.
"""
from __future__ import annotations

import ast
import asyncio
import pathlib
from datetime import date, timedelta

import pytest

from bot.runtime import bot_command_stats as stats_mod

_ROOT = pathlib.Path(__file__).resolve().parents[1]

TODAY = date(2026, 9, 30)  # среда
YESTERDAY = TODAY - timedelta(days=1)
MONDAY = date(2026, 9, 28)
LAST_WEEK = date(2026, 9, 22)
LAST_MONTH = date(2026, 8, 15)
LAST_YEAR = date(2025, 5, 1)


# ─── Фейки asyncpg ────────────────────────────────────────────────────────────


class _Ctx:
    def __init__(self, value=None):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, pool: "FakePool"):
        self._pool = pool

    async def execute(self, sql, *args, **kwargs):
        self._pool.executed.append((" ".join(sql.split()), args, kwargs))
        if self._pool.fail_execute:
            raise RuntimeError("db down")
        return "OK"

    async def fetchval(self, sql, *args):
        return self._pool.fetchval_result

    def transaction(self):
        return _Ctx()


class FakePool:
    def __init__(self, rows=None, *, fail_execute=False, fail_fetch=False, fetchval_result=False):
        self.rows = rows or []
        self.fail_execute = fail_execute
        self.fail_fetch = fail_fetch
        self.fetchval_result = fetchval_result
        self.executed: list[tuple[str, tuple, dict]] = []
        self.fetch_calls: list[tuple] = []

    def acquire(self):
        return _Ctx(FakeConn(self))

    async def fetch(self, sql, *args):
        self.fetch_calls.append(args)
        if self.fail_fetch:
            raise RuntimeError("db down")
        return self.rows

    def upserts(self, table: str):
        return [args for sql, args, _ in self.executed if f"INSERT INTO {table}" in sql]


@pytest.fixture
def stats(monkeypatch):
    """Модуль с чистыми буферами и «готовой» схемой."""
    monkeypatch.setattr(stats_mod, "_pending", {})
    monkeypatch.setattr(stats_mod, "_pending_wager", {})
    monkeypatch.setattr(stats_mod, "_schema_ready", True)
    monkeypatch.setattr(stats_mod, "_wager_backfill_done", True)
    monkeypatch.setattr(stats_mod, "_flush_task", None)
    monkeypatch.setattr(stats_mod, "_flush_lock", asyncio.Lock())
    monkeypatch.setattr(stats_mod, "_today_msk", lambda: TODAY)
    return stats_mod


# ─── Что считается игрой ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cause",
    ["- кости", "+ рулетка", "инлайн кн сдача", "Мины: выигрыш", "  БАШНЯ  ", "орёл и решка"],
)
def test_game_causes_are_counted(cause):
    assert stats_mod.is_game_cause(cause) is True


@pytest.mark.parametrize(
    "cause",
    [
        "инлайн перевод (отправитель)",
        "перевод кости другу",
        "sypherснять",
        "положено на баланс группы",
        "донат",
        "",
        None,
        12345,
    ],
)
def test_non_game_causes_are_ignored(cause):
    assert stats_mod.is_game_cause(cause) is False


def test_server_and_bot_use_the_same_game_words():
    """Бэкфилл сервера и живой счётчик бота должны считать одни и те же игры."""
    tree = ast.parse((_ROOT / "server" / "admin_db.py").read_text(encoding="utf-8"))
    server_words = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_GAME_CAUSE_WORDS" for t in node.targets
        ):
            server_words = ast.literal_eval(node.value)
    assert server_words is not None
    assert set(server_words) == set(stats_mod._GAME_CAUSE_WORDS)


# ─── Буферы (синхронно, без event loop) ───────────────────────────────────────


def test_note_game_wager_splits_lost_and_won(stats):
    stats.note_game_wager(100)
    stats.note_game_wager(40, won=True)
    stats.note_game_wager(-25)
    assert stats._pending_wager == {TODAY: [165, 3, 125, 40]}


def test_note_game_wager_ignores_junk(stats):
    for junk in (0, None, "abc", "", float("nan")):
        try:
            stats.note_game_wager(junk)
        except ValueError:
            pytest.fail(f"note_game_wager не должен падать на {junk!r}")
    assert stats._pending_wager == {}


def test_note_game_wager_accepts_numeric_strings(stats):
    stats.note_game_wager("25.9")
    assert stats._pending_wager[TODAY] == [25, 1, 25, 0]


def test_note_game_wager_keeps_days_apart(stats):
    stats.note_game_wager(10, day=YESTERDAY)
    stats.note_game_wager(20)
    assert stats._pending_wager == {YESTERDAY: [10, 1, 10, 0], TODAY: [20, 1, 20, 0]}


def test_note_game_cause_amount_only_for_games(stats):
    stats.note_game_cause_amount("- кости", 50)
    stats.note_game_cause_amount("+ кости", 80, won=True)
    stats.note_game_cause_amount("инлайн перевод", 1_000_000)
    assert stats._pending_wager == {TODAY: [130, 2, 50, 80]}


def test_note_bot_command_accumulates(stats):
    stats.note_bot_command()
    stats.note_bot_command(4)
    stats.note_bot_command(0)
    stats.note_bot_command(-3)
    stats.note_bot_command(2, day=YESTERDAY)
    assert stats._pending == {TODAY: 5, YESTERDAY: 2}


def test_requeue_merges_with_fresh_increments(stats):
    stats._pending[TODAY] = 2
    stats._pending_wager[TODAY] = [5, 1, 5, 0]
    stats._requeue({TODAY: 3, YESTERDAY: 1}, {TODAY: [10, 2, 4, 6], YESTERDAY: [7, 1, 0, 7]})
    assert stats._pending == {TODAY: 5, YESTERDAY: 1}
    assert stats._pending_wager == {TODAY: [15, 3, 9, 6], YESTERDAY: [7, 1, 0, 7]}


def test_requeue_does_not_alias_snapshot_lists(stats):
    snapshot = {TODAY: [1, 1, 1, 0]}
    stats._requeue({}, snapshot)
    stats._pending_wager[TODAY][0] += 100
    assert snapshot[TODAY][0] == 1


# ─── Flush ────────────────────────────────────────────────────────────────────


def test_flush_writes_both_counters_and_clears_buffers(stats):
    stats.note_bot_command(3)
    stats.note_game_wager(100)
    stats.note_game_wager(40, won=True)
    pool = FakePool()

    asyncio.run(stats.flush_bot_command_counts(pool))

    assert pool.upserts("bot_command_day_counts") == [(TODAY, 3)]
    assert pool.upserts("bot_game_wager_day_totals") == [(TODAY, 140, 2, 100, 40)]
    assert stats._pending == {}
    assert stats._pending_wager == {}


def test_flush_upsert_adds_to_existing_day(stats):
    stats.note_game_wager(10)
    pool = FakePool()
    asyncio.run(stats.flush_bot_command_counts(pool))
    sql = next(sql for sql, _, _ in pool.executed if "bot_game_wager_day_totals" in sql)
    assert "ON CONFLICT (day) DO UPDATE" in sql
    assert "kut_lost = bot_game_wager_day_totals.kut_lost + EXCLUDED.kut_lost" in sql
    assert "kut_won = bot_game_wager_day_totals.kut_won + EXCLUDED.kut_won" in sql


def test_flush_failure_requeues_everything(stats):
    stats.note_bot_command(7)
    stats.note_game_wager(90, won=True)
    pool = FakePool(fail_execute=True)

    asyncio.run(stats.flush_bot_command_counts(pool))

    assert stats._pending == {TODAY: 7}
    assert stats._pending_wager == {TODAY: [90, 1, 0, 90]}


def test_flush_without_pool_keeps_data(stats, monkeypatch):
    monkeypatch.setattr(stats, "_resolve_pool", lambda: None)
    stats.note_bot_command(2)
    stats.note_game_wager(5)

    asyncio.run(stats.flush_bot_command_counts())

    assert stats._pending == {TODAY: 2}
    assert stats._pending_wager == {TODAY: [5, 1, 5, 0]}


def test_flush_with_empty_buffers_touches_nothing(stats):
    pool = FakePool()
    asyncio.run(stats.flush_bot_command_counts(pool))
    assert pool.executed == []


def test_threshold_triggers_flush_inside_event_loop(stats, monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(stats, "_resolve_pool", lambda: pool)
    monkeypatch.setattr(stats, "_FLUSH_INTERVAL_SEC", 0.01)

    async def scenario():
        stats.note_bot_command(stats._FLUSH_THRESHOLD)
        for _ in range(20):
            await asyncio.sleep(0.01)
            if not stats._pending and pool.executed:
                break
        task = stats._flush_task
        if task is not None and not task.done():
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())

    assert pool.upserts("bot_command_day_counts") == [(TODAY, stats._FLUSH_THRESHOLD)]
    assert stats._pending == {}


def test_flush_loop_exits_quietly_when_idle(stats, monkeypatch):
    monkeypatch.setattr(stats, "_FLUSH_INTERVAL_SEC", 0)
    asyncio.run(asyncio.wait_for(stats._flush_loop(), timeout=1))


# ─── Бэкфилл оборота из cutehistory ───────────────────────────────────────────


def test_backfill_runs_once_on_empty_table(stats, monkeypatch):
    monkeypatch.setattr(stats, "_wager_backfill_done", False)
    pool = FakePool(fetchval_result=True)

    asyncio.run(stats.backfill_game_wager_totals(pool))
    asyncio.run(stats.backfill_game_wager_totals(pool))

    assert len(pool.executed) == 1
    sql, args, kwargs = pool.executed[0]
    assert "FROM cutehistory" in sql
    assert "NOT ILIKE '%перевод%'" in sql
    assert args[0] == stats._WAGER_BACKFILL_ROWS
    assert "%кости%" in args[1]
    assert kwargs.get("timeout")


def test_backfill_skips_when_totals_exist(stats, monkeypatch):
    monkeypatch.setattr(stats, "_wager_backfill_done", False)
    pool = FakePool(fetchval_result=False)
    asyncio.run(stats.backfill_game_wager_totals(pool))
    assert pool.executed == []


def test_backfill_failure_does_not_raise(stats, monkeypatch):
    monkeypatch.setattr(stats, "_wager_backfill_done", False)
    pool = FakePool(fetchval_result=True, fail_execute=True)
    asyncio.run(stats.backfill_game_wager_totals(pool))


# ─── Периоды ──────────────────────────────────────────────────────────────────


def test_period_bounds_midweek():
    b = stats_mod._period_bounds(TODAY)
    assert b["day"] == (TODAY, TODAY + timedelta(days=1), YESTERDAY, TODAY)
    assert b["week"] == (MONDAY, MONDAY + timedelta(days=7), MONDAY - timedelta(days=7), MONDAY)
    assert b["month"] == (date(2026, 9, 1), date(2026, 10, 1), date(2026, 8, 1), date(2026, 9, 1))
    assert b["year"] == (date(2026, 1, 1), date(2027, 1, 1), date(2025, 1, 1), date(2026, 1, 1))


def test_period_bounds_january_rolls_back_to_december():
    b = stats_mod._period_bounds(date(2026, 1, 15))
    assert b["month"] == (date(2026, 1, 1), date(2026, 2, 1), date(2025, 12, 1), date(2026, 1, 1))


def test_period_bounds_december_rolls_forward_to_january():
    b = stats_mod._period_bounds(date(2025, 12, 10))
    assert b["month"] == (date(2025, 12, 1), date(2026, 1, 1), date(2025, 11, 1), date(2025, 12, 1))


def test_period_bounds_monday_starts_its_own_week():
    b = stats_mod._period_bounds(MONDAY)
    assert b["week"][0] == MONDAY


def test_sum_range_is_end_exclusive():
    by_day = {TODAY: 5, YESTERDAY: 3}
    assert stats_mod._sum_range(by_day, YESTERDAY, TODAY) == 3
    assert stats_mod._sum_range(by_day, YESTERDAY, TODAY + timedelta(days=1)) == 8


def _wager_row(day, kut, lost, won):
    return {"day": day, "kut": kut, "lost": lost, "won": won}


def test_wager_periods_merge_db_and_pending(stats):
    pool = FakePool(
        rows=[
            _wager_row(TODAY, 100, 60, 40),
            _wager_row(YESTERDAY, 50, 20, 30),
            _wager_row(LAST_WEEK, 70, 70, 0),
            _wager_row(LAST_MONTH, 1000, 400, 600),
            _wager_row(LAST_YEAR, 9, 9, 0),
        ]
    )
    stats.note_game_wager(10)
    stats.note_game_wager(5, won=True)

    out = asyncio.run(stats.fetch_game_wager_periods(pool))

    assert out["day"] == {"current": 115, "previous": 50, "lost": 70, "won": 45}
    assert out["week"] == {"current": 165, "previous": 70, "lost": 90, "won": 75}
    assert out["month"] == {"current": 235, "previous": 1000, "lost": 160, "won": 75}
    assert out["year"] == {"current": 1235, "previous": 9, "lost": 560, "won": 675}
    assert pool.fetch_calls == [(date(2025, 1, 1),)]


def test_wager_periods_are_consistent(stats):
    """Проиграно + выиграно = оборот за тот же период."""
    pool = FakePool(rows=[_wager_row(TODAY, 100, 60, 40), _wager_row(LAST_MONTH, 30, 10, 20)])
    stats.note_game_wager(7, won=True)
    out = asyncio.run(stats.fetch_game_wager_periods(pool))
    for period in out.values():
        assert period["lost"] + period["won"] == period["current"]


def test_wager_periods_db_error_returns_zeros(stats):
    out = asyncio.run(stats.fetch_game_wager_periods(FakePool(fail_fetch=True)))
    assert all(v == {"current": 0, "previous": 0} for v in out.values())


def test_wager_periods_without_pool(stats):
    out = asyncio.run(stats.fetch_game_wager_periods(None))
    assert out["day"] == {"current": 0, "previous": 0}


def test_command_periods_merge_db_and_pending(stats):
    pool = FakePool(
        rows=[
            {"day": TODAY, "commands": 10},
            {"day": YESTERDAY, "commands": 4},
            {"day": LAST_WEEK, "commands": 6},
            {"day": LAST_YEAR, "commands": 100},
        ]
    )
    stats.note_bot_command(3)

    out = asyncio.run(stats.fetch_bot_command_periods(pool))

    assert out["day"] == {"current": 13, "previous": 4}
    assert out["week"] == {"current": 17, "previous": 6}
    assert out["year"] == {"current": 23, "previous": 100}


def test_command_periods_db_error_returns_zeros(stats):
    out = asyncio.run(stats.fetch_bot_command_periods(FakePool(fail_fetch=True)))
    assert out == stats._empty_periods()
