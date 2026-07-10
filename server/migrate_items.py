"""Миграция users.items → единый чистый JSON-формат {"\\u041a...": 5}.

Приводит все записи (в т.ч. старый «обёрнутый» формат и записи со старыми
ключами) к каноничному виду, который одинаково читают вебапп и основной бот.
"""

from __future__ import annotations

import asyncpg

from json_db_codec import encode_json_payload
from user_items import parse_items


async def migrate_all_users_items(pool: asyncpg.Pool) -> int:
    # Быстрый путь: если все items уже в каноничном JSON {…}, не сканируем
    # тысячи строк при каждом старте API/ботов.
    needs = await pool.fetchval(
        """
        SELECT 1 FROM users
        WHERE items IS NOT NULL AND items != ''
          AND TRIM(items) NOT LIKE '{%'
        LIMIT 1
        """
    )
    if not needs:
        return 0

    rows = await pool.fetch(
        """
        SELECT user_id, items
        FROM users
        WHERE items IS NOT NULL AND items != ''
        """
    )
    updated = 0
    async with pool.acquire() as conn:
        for row in rows:
            raw = row["items"]
            if raw is None:
                continue
            parsed = parse_items(raw)
            encoded = encode_json_payload(parsed)
            current = (raw or "").strip()
            if encoded == current:
                continue
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                row["user_id"],
                encoded,
            )
            updated += 1
    return updated
