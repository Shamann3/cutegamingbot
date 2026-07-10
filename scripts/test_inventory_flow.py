"""Симуляция полного потока .инвентарь для одного user_id."""
import asyncio
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bot" / "db_create"))

import asyncpg
from bot.config.db_config import build_db_settings, bootstrap_database_env
from bot.db_create.db import Database
from bot.db_create.items_codec import decode_items
from bot.funcs.shop import generate_inventory_page, ITEMS_PER_PAGE, get_inventory_navigation_buttons

UID = 6801702632


async def main():
    bootstrap_database_env()
    db = Database()
    await db.connect()
    try:
        inv = await db.get_user_inventory(UID)
        print("get_user_inventory:", type(inv), len(inv) if inv else 0, inv)
        items = decode_items(inv)
        print("decode_items keys:", len(items))
        if not items:
            print("EMPTY -> would show 'Инвентарь пуст'")
            return
        page = 0
        total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
        print("ITEMS_PER_PAGE=", ITEMS_PER_PAGE, "total_pages=", total_pages)
        try:
            inv_list = await generate_inventory_page(items, page)
            print("generate_inventory_page OK, len=", len(inv_list))
            print(inv_list[:500])
        except Exception as e:
            print("generate_inventory_page FAILED:", type(e).__name__, e)
            raise
        nav = get_inventory_navigation_buttons(page, total_pages)
        print("nav buttons:", len(nav))
    finally:
        await db.pool.close()


if __name__ == "__main__":
    asyncio.run(main())
