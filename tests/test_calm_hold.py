# -*- coding: utf-8 -*-
import asyncio

from bot.funcs.calm_hold import calm_state, drop_rules_cache


class Pool:
    def __init__(self, played):
        self.played = played
        self.sql = []

    async def execute(self, sql, *args):
        self.sql.append(sql)
        return "OK"

    async def fetchrow(self, sql, *args):
        self.sql.append(sql)
        if "balance_calm" in sql:
            return {"enabled": True, "games": 5, "hours": 24, "seconds": 86400}
        return {"played": self.played, "remain": 3600}


def _state(played):
    drop_rules_cache()
    db = type("DB", (), {"pool": Pool(played)})()
    return asyncio.run(calm_state(db, 77)), db


def test_enough_games_keep_the_balance_calm():
    state, db = _state(5)
    assert state["calm"] is True
    assert state["played"] == 5
    assert any("INTERVAL '1 second'" in sql for sql in db.pool.sql)


def test_too_few_games_leave_the_balance_open():
    state, _db = _state(4)
    assert state["calm"] is False


def test_creator_may_set_any_game_count():
    from water_games.design import CALM_MAX_GAMES, calm_need

    assert calm_need(1) == 1
    assert calm_need(500) == 500
    assert calm_need("50 000") == 50000
    assert calm_need(CALM_MAX_GAMES) == CALM_MAX_GAMES
    assert calm_need(CALM_MAX_GAMES + 9) == CALM_MAX_GAMES
    assert calm_need(0) == 1
    assert calm_need("нет") == 5
