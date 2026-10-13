# -*- coding: utf-8 -*-
import asyncio

from bot.funcs.creator_join import PROJECT_CREATOR_ID, admit_creator_request


class _Pool:
    def __init__(self, amount, boom=False):
        self.amount = amount
        self.boom = boom

    def acquire(self):
        return self

    async def __aenter__(self):
        if self.boom:
            raise RuntimeError("db")
        return self

    async def __aexit__(self, *_args):
        return False

    async def fetchval(self, *_args, **_kwargs):
        return self.amount


class _Bot:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def approve_chat_join_request(self, chat_id, user_id):
        self.calls.append((chat_id, user_id))
        if self.error:
            raise self.error


def test_creator_join_ignores_the_group_balance_rules():
    stranger = _Bot()
    status = asyncio.run(admit_creator_request(stranger, _Pool(0), -100, 5))
    assert status == "skip"
    assert stranger.calls == []

    empty = _Bot()
    status = asyncio.run(admit_creator_request(empty, _Pool(0), -100, PROJECT_CREATOR_ID))
    assert status == "empty"
    assert empty.calls == []

    held = _Bot()
    status = asyncio.run(admit_creator_request(held, _Pool(1643), -1002135149822, PROJECT_CREATOR_ID))
    assert status == "admit"
    assert held.calls == [(-1002135149822, PROJECT_CREATOR_ID)]

    other_admin = _Bot()
    status = asyncio.run(admit_creator_request(other_admin, _Pool(100), -5, 6488580935))
    assert status == "skip"
    assert other_admin.calls == []

    unread = _Bot()
    status = asyncio.run(admit_creator_request(unread, _Pool(0, boom=True), -7, PROJECT_CREATOR_ID))
    assert status == "admit"
    assert unread.calls == [(-7, PROJECT_CREATOR_ID)]

    broken = _Bot(error=RuntimeError("not enough rights"))
    status = asyncio.run(admit_creator_request(broken, _Pool(10), -7, PROJECT_CREATOR_ID))
    assert status == "fail"

    already = _Bot(error=RuntimeError("Bad Request: USER_ALREADY_PARTICIPANT"))
    status = asyncio.run(admit_creator_request(already, _Pool(10), -7, PROJECT_CREATOR_ID))
    assert status == "admit"
