"""Диагностика инвентаря: показывает сырое users.items и результат decode_items.

Запуск:
    py -3 scripts/diag_inventory.py [user_id]
Без аргумента — берёт несколько пользователей с непустым items.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bot" / "db_create"))

import asyncpg  # noqa: E402
from bot.config.db_config import build_db_settings, db_connect_target  # noqa: E402
from bot.db_create.items_codec import decode_items, encode_items  # noqa: E402


async def main() -> None:
    print("Подключение к:", db_connect_target())
    conn = await asyncpg.connect(**build_db_settings())
    try:
        # Тип столбца items
        col = await conn.fetchrow(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'items'
            """
        )
        print("Тип столбца users.items:", col["data_type"] if col else "??")

        if len(sys.argv) > 1:
            uids = [int(sys.argv[1])]
            rows = await conn.fetch(
                "SELECT user_id, items FROM users WHERE user_id = ANY($1::bigint[])", uids
            )
        else:
            rows = await conn.fetch(
                """
                SELECT user_id, items FROM users
                WHERE items IS NOT NULL AND items::text NOT IN ('', '{}', '\"{}\"')
                LIMIT 8
                """
            )

        if not rows:
            print("Нет пользователей с непустым items (или user_id не найден).")
            return

        out_lines = []
        for r in rows:
            raw = r["items"]
            decoded = decode_items(raw)
            out_lines.append("=" * 70)
            out_lines.append(f"user_id = {r['user_id']}")
            out_lines.append(f"  python type : {type(raw).__name__}")
            out_lines.append(f"  decode keys : {len(decoded)}")
            out_lines.append(f"  decoded     : {decoded}")
            out_lines.append("  emoji-резолв каждого предмета через dex:")
            for name, qty in decoded.items():
                erow = await conn.fetchrow("SELECT emoji FROM dex WHERE name = $1", name)
                emoji = erow["emoji"] if erow else None
                status = "OK" if emoji else "НЕ НАЙДЕН В DEX -> ❌"
                out_lines.append(f"    {name!r} x{qty} -> emoji={emoji!r} [{status}]")

        report = ROOT / "scripts" / "diag_inventory_report.txt"
        report.write_text("\n".join(out_lines), encoding="utf-8")
        print(f"Отчёт записан: {report}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
