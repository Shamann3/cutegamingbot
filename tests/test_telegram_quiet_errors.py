# -*- coding: utf-8 -*-
"""Штатный отказ Telegram не должен выглядеть как авария с трейсом."""
import asyncio
import logging

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.utils.telegram_api_logger import TelegramApiLogger, _is_quiet_error


def _forbidden(text: str) -> TelegramForbiddenError:
    return TelegramForbiddenError(method=None, message=text)


def _bad(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=None, message=text)


def test_unreachable_people_and_chats_are_quiet():
    samples = [
        _forbidden("Forbidden: bot can't initiate conversation with a user"),
        _forbidden("Forbidden: bot was blocked by the user"),
        _forbidden("Forbidden: user is deactivated"),
        _forbidden("Forbidden: bot was kicked from the supergroup chat"),
        _forbidden("Forbidden: bot is not a member of the channel chat"),
        _forbidden("Forbidden: the group chat was deleted"),
        _forbidden("Forbidden: bot can't send messages to bots"),
        _bad("Bad Request: group chat was upgraded to a supergroup chat"),
        _bad("Bad Request: chat not found"),
    ]
    for error in samples:
        assert _is_quiet_error(error), str(error)


def test_a_real_api_mistake_still_counts_as_a_failure():
    assert _is_quiet_error(_bad("Bad Request: message text is empty")) is False
    assert _is_quiet_error(RuntimeError("bot can't initiate conversation with a user")) is False


class _Send:
    pass


def test_send_to_a_closed_chat_is_one_line_and_still_raises():
    seen = []

    class _List(logging.Handler):
        def emit(self, record):
            seen.append(record)

    handler = _List()
    log = logging.getLogger("telegram_api")
    log.addHandler(handler)

    async def run():
        async def refuse(bot, method):
            raise _forbidden("Forbidden: bot can't initiate conversation with a user")

        with pytest.raises(TelegramForbiddenError):
            await TelegramApiLogger()(refuse, None, _Send())

    try:
        asyncio.run(run())
    finally:
        log.removeHandler(handler)

    lines = [record.getMessage() for record in seen]
    assert any("EXPECTED" in line and "initiate conversation" in line for line in lines)
    assert not any("FAIL" in line for line in lines)
    assert not any(record.exc_info for record in seen)
