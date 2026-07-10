"""Запуск игрового и admin-бота параллельно с одним пулом БД."""

from __future__ import annotations

import asyncio
import logging
import sys

from config import ADMIN_BOT_TOKEN, ADMIN_ENABLED, SUPPORT_BOT_TOKEN
from admin_bot import run_admin_bot
from game_bot import main as run_game_bot
from support_bot import run_support_bot
from db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cute-farm.bots")


def _boot(msg: str) -> None:
    """Ранний маркер старта — виден в farm-bots.log для start-all.ps1."""
    line = f"[FARM-BOTS] {msg}"
    print(line, flush=True)
    logger.info(msg)


async def main() -> None:
    _boot("starting game + admin + support bots...")
    await db.ensure_connected()
    _boot("database ready — launching pollers...")
    try:
        tasks = [run_game_bot(manage_db=False)]
        if ADMIN_ENABLED and ADMIN_BOT_TOKEN:
            tasks.append(run_admin_bot())
        else:
            logger.warning(
                "Admin bot не запущен — задай ADMIN_ENABLED=true и ADMIN_BOT_TOKEN в .env"
            )
        if SUPPORT_BOT_TOKEN:
            tasks.append(run_support_bot())
        else:
            logger.warning("Support bot не запущен — задай SUPPORT_BOT_TOKEN в .env")
        _boot(f"pollers starting ({len(tasks)} bot(s))...")
        await asyncio.gather(*tasks)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _boot("stopped by user")
        sys.exit(0)
