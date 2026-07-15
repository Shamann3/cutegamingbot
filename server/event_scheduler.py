"""Фоновый планировщик событий.



Запускается в lifespan FastAPI как asyncio task.

Каждые 30 сек:

  1. Активирует/деактивирует временные квесты.

  2. Продвигает окна повторяющихся квестов (recurrence).

  3. Запускает отложенные рассылки (status='scheduled', scheduled_at<=now).

  4. Purge старых game_events (раз в сутки).

"""



from __future__ import annotations



import asyncio

import logging

from datetime import datetime, timedelta, timezone



logger = logging.getLogger(__name__)



_UTC = timezone.utc

_TICK_SECONDS = 30





async def event_scheduler_loop(stop_event: asyncio.Event) -> None:

    logger.info("Event scheduler started (tick=%ss)", _TICK_SECONDS)

    while not stop_event.is_set():

        try:

            await _tick()

        except Exception:

            logger.exception("Event scheduler tick error")

        try:

            await asyncio.wait_for(stop_event.wait(), timeout=_TICK_SECONDS)

        except asyncio.TimeoutError:

            pass





async def _tick() -> None:

    await _fire_scheduled_broadcasts()

    await _fire_daily_rotation_broadcast()

    await _fire_group_post_campaigns()

    await _advance_recurring_quests()

    await _send_harvest_notifications()

    from game_events_maintenance import maybe_purge_old_game_events

    await maybe_purge_old_game_events()


async def _fire_group_post_campaigns() -> None:
    from group_posts import _fire_group_post_campaigns as _run
    await _run()





# ---------------------------------------------------------------------------

# Harvest notifications

# ---------------------------------------------------------------------------



async def _send_harvest_notifications() -> None:
    """Отправляет уведомление в Telegram когда урожай готов."""
    from config import BOT_TOKEN
    if not BOT_TOKEN:
        return

    from db import db
    import aiohttp

    # Находим готовые грядки у игроков с включёнными уведомлениями
    rows = await db.pool.fetch(
        """
        SELECT fp.user_id, COUNT(*) AS ready_count,
               u.first_name
        FROM farm_plots fp
        JOIN users u ON u.user_id = fp.user_id
        WHERE fp.status = 'GROWING'
          AND fp.ripe_at <= NOW()
          AND fp.harvest_notified = FALSE
          AND u.harvest_notify = TRUE
          AND u.banned = FALSE
        GROUP BY fp.user_id, u.first_name
        LIMIT 100
        """
    )

    if not rows:
        return

    async with aiohttp.ClientSession() as session:
        for row in rows:
            user_id = int(row["user_id"])
            count = int(row["ready_count"])
            name = row["first_name"] or "Фермер"

            if count == 1:
                text = f"<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>{name}, урожай созрел!\nПроверьте ферму</b>"
            else:
                text = f"<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>{name}, {count} грядки готовы к сбору!\nЗайдите на ферму и не дайте им засохнуть.</b>"

            try:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
                    timeout=aiohttp.ClientTimeout(total=8),
                )
            except Exception as e:
                logger.warning("harvest notify failed user_id=%s: %s", user_id, e)

            # Помечаем как уведомлённые
            await db.pool.execute(
                """
                UPDATE farm_plots
                SET harvest_notified = TRUE
                WHERE user_id = $1
                  AND status = 'GROWING'
                  AND ripe_at <= NOW()
                  AND harvest_notified = FALSE
                """,
                user_id,
            )

    if rows:
        logger.info("harvest_notify: sent to %d users", len(rows))



# ---------------------------------------------------------------------------

# Scheduled broadcasts

# ---------------------------------------------------------------------------



async def _fire_scheduled_broadcasts() -> None:

    from db import db

    from admin_broadcast import schedule_broadcast_run



    now = datetime.now(_UTC)

    rows = await db.pool.fetch(

        """

        UPDATE broadcast_runs

        SET status = 'pending'

        WHERE status = 'scheduled'

          AND scheduled_at IS NOT NULL

          AND scheduled_at <= $1

        RETURNING id

        """,

        now,

    )

    for row in rows:

        run_id = int(row["id"])

        schedule_broadcast_run(run_id)

        logger.info("Fired scheduled broadcast run_id=%s", run_id)



# ---------------------------------------------------------------------------

# Daily rotation broadcast - раз в день, случайный шаблон из DAILY_ROTATION_TEMPLATES,
# случайной части игроков (sampleRate), у которых не было этой рассылки последние
# cooldown_days дней (cooldownDays) - не всем сразу и не каждый день одному и тому же.
# Время (daily_broadcast_hour/minute) - в UTC, как всё в этом модуле
# (datetime.now(_UTC)). Атомарный claim через WHERE next_fire_at = <прочитанное
# значение> - тот же паттерн, что и у recurring quests, безопасен при нескольких
# тиках/воркерах.

# ---------------------------------------------------------------------------



def _next_daily_slot(now: datetime, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


async def _fire_daily_rotation_broadcast() -> None:

    from db import db
    from admin_broadcast import start_daily_rotation_broadcast

    settings = await db.pool.fetchrow(
        """
        SELECT daily_broadcast_enabled, daily_broadcast_hour, daily_broadcast_minute,
               daily_broadcast_next_fire_at, daily_broadcast_cooldown_days,
               daily_broadcast_sample_rate
        FROM system_settings WHERE id = 1
        """
    )
    if not settings or not settings["daily_broadcast_enabled"]:
        return

    now = datetime.now(_UTC)
    hour = int(settings["daily_broadcast_hour"] or 12)
    minute = int(settings["daily_broadcast_minute"] or 0)
    next_fire_at = settings["daily_broadcast_next_fire_at"]

    if next_fire_at is None:
        # Первый тик после деплоя/включения - не стреляем сразу, только выставляем расписание.
        await db.pool.execute(
            """
            UPDATE system_settings
            SET daily_broadcast_next_fire_at = $1
            WHERE id = 1 AND daily_broadcast_next_fire_at IS NULL
            """,
            _next_daily_slot(now, hour, minute),
        )
        return

    if next_fire_at > now:
        return

    claimed = await db.pool.fetchrow(
        """
        UPDATE system_settings
        SET daily_broadcast_next_fire_at = $2
        WHERE id = 1 AND daily_broadcast_next_fire_at = $1
        RETURNING id
        """,
        next_fire_at,
        _next_daily_slot(now, hour, minute),
    )
    if not claimed:
        return  # другой тик/воркер уже забрал этот запуск

    cooldown_days = int(settings["daily_broadcast_cooldown_days"] or 2)
    sample_rate = float(settings["daily_broadcast_sample_rate"] or 0.5)

    try:
        result = await start_daily_rotation_broadcast(
            cooldown_days=cooldown_days, sample_rate=sample_rate,
        )
        logger.info(
            "Daily rotation broadcast fired: run_id=%s recipients=%s",
            result.get("runId"), result.get("recipientCount"),
        )
    except ValueError as e:
        logger.warning("Daily rotation broadcast skipped (nobody eligible today): %s", e)
    except Exception:
        logger.exception("Daily rotation broadcast failed")




# ---------------------------------------------------------------------------

# Recurring quests — atomic claim per quest row (safe with multiple workers)

# ---------------------------------------------------------------------------



async def _advance_recurring_quests() -> None:

    from db import db

    from quest_registry import reload_quest_registry



    now = datetime.now(_UTC)



    rows = await db.pool.fetch(

        """

        SELECT id, key, active_from, active_until, recurrence, recurrence_end

        FROM quests

        WHERE enabled = TRUE

          AND recurrence IS NOT NULL

          AND active_until IS NOT NULL

          AND active_until <= $1

        """,

        now,

    )

    if not rows:

        return



    changed = False

    for row in rows:

        quest_id = int(row["id"])

        active_from = row["active_from"]

        active_until = row["active_until"]

        recurrence = row["recurrence"]

        recurrence_end = row["recurrence_end"]



        duration = active_until - active_from if active_from else timedelta(days=1)

        delta = timedelta(days=1) if recurrence == "daily" else timedelta(weeks=1)



        next_from = active_from or active_until

        while next_from + duration <= now:

            next_from = next_from + delta

        next_until = next_from + duration



        if recurrence_end and next_from > recurrence_end:

            result = await db.pool.fetchrow(

                """

                UPDATE quests

                SET enabled = FALSE,

                    recurrence = NULL,

                    updated_at = NOW()

                WHERE id = $1

                  AND active_until <= $2

                RETURNING id

                """,

                quest_id,

                now,

            )

            if result:

                logger.info(

                    "Quest %s (id=%s) recurrence ended, disabled",

                    row["key"], quest_id,

                )

                changed = True

        else:

            result = await db.pool.fetchrow(

                """

                UPDATE quests

                SET active_from = $3,

                    active_until = $4,

                    updated_at = NOW()

                WHERE id = $1

                  AND active_until <= $2

                RETURNING id

                """,

                quest_id,

                now,

                next_from,

                next_until,

            )

            if result:

                logger.info(

                    "Quest %s (id=%s) advanced: %s → %s",

                    row["key"], quest_id, next_from.isoformat(), next_until.isoformat(),

                )

                changed = True



    if changed:

        await reload_quest_registry(db.pool)


