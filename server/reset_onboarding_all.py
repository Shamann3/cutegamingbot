"""Сброс обучения для всех пользователей."""

from __future__ import annotations

import asyncio
import sys

import asyncpg

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, db_ssl_mode


async def reset_all_onboarding(pool: asyncpg.Pool) -> tuple[int, int]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            users_result = await conn.execute(
                """
                UPDATE users
                SET onboarding_done = FALSE,
                    onboarding_active = FALSE,
                    onboarding_seed_granted = 0,
                    onboarding_demo_logs = 0,
                    onboarding_step = 0
                """
            )
            plots_result = await conn.execute(
                """
                UPDATE farm_plots
                SET status = 'EMPTY',
                    planted_at = NULL,
                    ripe_at = NULL,
                    dry_at = NULL,
                    needs_water = FALSE,
                    wilt_at = NULL,
                    waters_remaining = 0
                WHERE plot_id = 1
                """
            )

    users_count = int(users_result.split()[-1]) if users_result else 0
    plots_count = int(plots_result.split()[-1]) if plots_result else 0
    return users_count, plots_count


async def main() -> int:
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        ssl=db_ssl_mode(),
        min_size=1,
        max_size=2,
    )
    try:
        users_count, plots_count = await reset_all_onboarding(pool)
        print(f"Сброшено обучение у пользователей: {users_count}")
        print(f"Очищена грядка №1: {plots_count}")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
