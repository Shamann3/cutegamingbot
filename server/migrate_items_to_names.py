"""Миграция users.items: числовые ID → имена предметов из dex (Unicode-эскейпы).

Запуск:
    python migrate_items_to_names.py
"""

import asyncio
import asyncpg
import config
from dex_catalog import dex_catalog
from json_db_codec import decode_json_payload
from user_items import items_to_db


async def migrate():
    pool = await asyncpg.create_pool(
        f"postgresql://{config.DB_USER}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
    )

    await dex_catalog.load(pool)
    print(f"Dex загружен: {len(dex_catalog._by_id)} предметов")

    rows = await pool.fetch("SELECT user_id, items FROM users WHERE items IS NOT NULL")
    print(f"Всего пользователей с items: {len(rows)}")

    updated = 0
    skipped = 0
    errors = 0

    for row in rows:
        uid = row["user_id"]
        raw = row["items"]
        try:
            decoded = decode_json_payload(raw)
            if not decoded:
                skipped += 1
                continue

            new_encoded = items_to_db(decoded)

            if new_encoded == raw:
                skipped += 1
                continue

            await pool.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                uid, new_encoded,
            )
            print(f"  [{uid}] {raw!r}\n        → {new_encoded!r}")
            updated += 1

        except Exception as e:
            print(f"  ОШИБКА [{uid}]: {e}")
            errors += 1

    await pool.close()
    print(f"\nГотово: обновлено {updated}, пропущено {skipped}, ошибок {errors}")


if __name__ == "__main__":
    asyncio.run(migrate())
