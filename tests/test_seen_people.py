# -*- coding: utf-8 -*-
"""Каждое сообщение сразу пишет человека в users, без баланса и пригласителя."""
import asyncio
from types import SimpleNamespace

import bot.funcs.seen_people as seen


class Pool:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append((" ".join(str(sql).split()), args))


def _human(uid, name, username):
    return SimpleNamespace(id=uid, first_name=name, last_name="", username=username, is_bot=False)


def _message(chat_id, user, joined=None, left=None):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=user,
        new_chat_members=joined or [],
        left_chat_member=left,
    )


def _users(pool):
    return [args for sql, args in pool.calls if sql.startswith("INSERT INTO users")]


def _seen(pool):
    return [args for sql, args in pool.calls if "INSERT INTO chat_seen_people" in sql]


def test_a_message_writes_the_person_and_leaves_money_alone():
    asyncio.run(_message_writes())


async def _message_writes():
    pool = Pool()
    previous_pool = seen._pool
    previous_ready = seen._ready

    async def fake_pool():
        return pool

    seen._pool = fake_pool
    seen._ready = False
    try:
        await seen.remember_sight(_message(-100, _human(77, "Ann", "ann")))
        written = _users(pool)
        assert written == [(77, "Ann", "ann")]
        assert _seen(pool)[0][1] == 77
        account_sql = next(sql for sql, _args in pool.calls if sql.startswith("INSERT INTO users"))
        assert "balance" not in account_sql
        assert "usersref" not in account_sql

        pool.calls.clear()
        await seen.remember_sight(_message(5, _human(77, "Ann", "ann_new")))
        assert _users(pool) == [(77, "Ann", "ann_new")]
        assert _seen(pool) == []

        pool.calls.clear()
        bot = SimpleNamespace(id=9, first_name="Bot", last_name="", username="helper", is_bot=True)
        await seen.remember_sight(_message(-100, bot))
        anonymous = _message(-100, None)
        anonymous.sender_chat = SimpleNamespace(id=-200)
        await seen.remember_sight(anonymous)
        assert _users(pool) == []

        pool.calls.clear()
        await seen.remember_sight(_message(-50, None, joined=[_human(88, "In", "inuser")]))
        assert _users(pool) == [(88, "In", "inuser")]
        assert _seen(pool)[0][1] == 88
    finally:
        seen._pool = previous_pool
        seen._ready = previous_ready


def test_an_edit_and_a_join_are_written_too():
    asyncio.run(_edit_and_join())


async def _edit_and_join():
    pool = Pool()
    previous_pool = seen._pool
    previous_ready = seen._ready

    async def fake_pool():
        return pool

    seen._pool = fake_pool
    seen._ready = False
    try:
        edited = SimpleNamespace(
            message=None,
            edited_message=_message(-3, _human(5, "Ed", "ed")),
            channel_post=None,
            edited_channel_post=None,
        )
        await seen.remember_event(edited)
        assert _users(pool) == [(5, "Ed", "ed")]

        pool.calls.clear()
        joined = SimpleNamespace(
            message=None,
            edited_message=None,
            channel_post=None,
            edited_channel_post=None,
            chat_member=SimpleNamespace(
                chat=SimpleNamespace(id=-9),
                new_chat_member=SimpleNamespace(user=_human(15, "New", "new")),
            ),
            my_chat_member=None,
        )
        await seen.remember_event(joined)
        assert _users(pool) == [(15, "New", "new")]
        assert _seen(pool)[0][0] == -9
    finally:
        seen._pool = previous_pool
        seen._ready = previous_ready
