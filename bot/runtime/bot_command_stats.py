"""Счётчики вызовов команд бота — лёгкая запись в БД без нагрузки на хендлеры.

Пишем в таблицу bot_command_day_counts (день → число вызовов).
Хендлеры только +1 в памяти; flush пакетом (UPSERT) раз в ~1с или по порогу.
Админка читает агрегаты day/week/month/year одним лёгким SELECT.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("cute.bot-command-stats")

MSK = timezone(timedelta(hours=3))

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bot_command_day_counts (
    day DATE PRIMARY KEY,
    commands BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bot_command_day_counts_day_idx
    ON bot_command_day_counts (day DESC);

CREATE TABLE IF NOT EXISTS bot_game_wager_day_totals (
    day DATE PRIMARY KEY,
    kut BIGINT NOT NULL DEFAULT 0,
    plays BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE bot_game_wager_day_totals ADD COLUMN IF NOT EXISTS kut_lost BIGINT NOT NULL DEFAULT 0;
ALTER TABLE bot_game_wager_day_totals ADD COLUMN IF NOT EXISTS kut_won  BIGINT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS bot_game_wager_day_totals_day_idx
    ON bot_game_wager_day_totals (day DESC);
"""

# Буферы: day → pending increment (event-loop single-threaded)
_pending: dict[date, int] = {}
_pending_wager: dict[date, list[int]] = {}
_flush_lock = asyncio.Lock()
_flush_task: Optional[asyncio.Task] = None
_schema_ready = False
_FLUSH_INTERVAL_SEC = 1.0
_FLUSH_THRESHOLD = 40


def _today_msk() -> date:
    return datetime.now(MSK).date()


def _schedule_flush() -> None:
    """Ставит flush на ближайший тик и поддерживает фоновый цикл."""
    global _flush_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    pending_total = sum(_pending.values()) + len(_pending_wager)
    if pending_total >= _FLUSH_THRESHOLD:
        loop.create_task(flush_bot_command_counts())
    if _flush_task is None or _flush_task.done():
        _flush_task = loop.create_task(_flush_loop())


def note_bot_command(n: int = 1, *, day: date | None = None) -> None:
    """Синхронно +N в буфер. Не блокирует, не await."""
    if n <= 0:
        return
    d = day or _today_msk()
    _pending[d] = _pending.get(d, 0) + int(n)
    _schedule_flush()


def note_game_wager(amount, *, won: bool = False, day: date | None = None) -> None:
    """Синхронно +amount кут к обороту за день. Не блокирует, не await.

    Буфер на день: [оборот, число операций, проиграно, выиграно].
    """
    try:
        value = int(abs(float(amount)))
    except (TypeError, ValueError):
        return
    if value <= 0:
        return
    d = day or _today_msk()
    bucket = _pending_wager.get(d)
    if bucket is None:
        bucket = [0, 0, 0, 0]
        _pending_wager[d] = bucket
    bucket[0] += value
    bucket[1] += 1
    bucket[3 if won else 2] += value
    _schedule_flush()


async def _flush_loop() -> None:
    try:
        while True:
            await asyncio.sleep(_FLUSH_INTERVAL_SEC)
            if not _pending and not _pending_wager:
                # Тихий выход — перезапустится при следующем note
                return
            await flush_bot_command_counts()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("bot_command flush loop crashed")


async def ensure_bot_command_stats_schema(pool) -> None:
    global _schema_ready
    if _schema_ready or pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(_SCHEMA_SQL)
            # Одноразовый бэкап истории из game_events, если счётчики пусты
            empty = await conn.fetchval("SELECT NOT EXISTS (SELECT 1 FROM bot_command_day_counts)")
            if empty:
                await conn.execute(
                    """
                    INSERT INTO bot_command_day_counts (day, commands, updated_at)
                    SELECT (created_at AT TIME ZONE 'Europe/Moscow')::date AS day,
                           COUNT(*)::bigint,
                           NOW()
                    FROM game_events
                    WHERE created_at >= NOW() - INTERVAL '400 days'
                    GROUP BY 1
                    ON CONFLICT (day) DO NOTHING
                    """
                )
        _schema_ready = True
    except Exception:
        logger.exception("ensure bot_command_day_counts failed")

    await backfill_game_wager_totals(pool)


# Хвост cutehistory для одноразового бэкфилла — скан ограничен по PK.
_WAGER_BACKFILL_ROWS = 400_000

_WAGER_BACKFILL_SQL = """
INSERT INTO bot_game_wager_day_totals (day, kut, plays, kut_lost, kut_won, updated_at)
SELECT to_date(split_part(h.data, ' ', 2), 'DD.MM.YYYY')                       AS day,
       COALESCE(SUM(COALESCE(h."-", 0) + COALESCE(h."+", 0)), 0)::bigint       AS kut,
       COUNT(*)::bigint                                                        AS plays,
       COALESCE(SUM(COALESCE(h."-", 0)), 0)::bigint                            AS kut_lost,
       COALESCE(SUM(COALESCE(h."+", 0)), 0)::bigint                            AS kut_won
     , NOW()
FROM cutehistory h
WHERE h.id > GREATEST((SELECT COALESCE(MAX(id), 0) FROM cutehistory) - $1::bigint, 0)
  AND h.data ~ '^[0-9]{2}:[0-9]{2} [0-9]{2}\\.[0-9]{2}\\.[0-9]{4}$'
  AND h.cause ILIKE ANY ($2::text[])
  AND h.cause NOT ILIKE '%перевод%'
  AND h.cause NOT ILIKE '%sypher%'
GROUP BY 1
ON CONFLICT (day) DO NOTHING
"""

_wager_backfill_done = False


async def backfill_game_wager_totals(pool) -> None:
    """Одноразово поднимает историю оборота из хвоста cutehistory.

    Нужен, чтобы карточка не показывала ноль до первой сыгранной партии.
    Скан ограничен последними _WAGER_BACKFILL_ROWS строками по первичному ключу.
    """
    global _wager_backfill_done
    if _wager_backfill_done or pool is None:
        return
    _wager_backfill_done = True
    try:
        async with pool.acquire() as conn:
            empty = await conn.fetchval(
                "SELECT NOT EXISTS (SELECT 1 FROM bot_game_wager_day_totals)"
            )
            if not empty:
                return
            patterns = [f"%{word}%" for word in _GAME_CAUSE_WORDS]
            await conn.execute(
                _WAGER_BACKFILL_SQL, _WAGER_BACKFILL_ROWS, patterns, timeout=25,
            )
    except Exception:
        logger.exception("backfill bot_game_wager_day_totals failed")


def _requeue(commands: dict[date, int], wagers: dict[date, list[int]]) -> None:
    for d, n in commands.items():
        _pending[d] = _pending.get(d, 0) + n
    for d, values in wagers.items():
        bucket = _pending_wager.get(d)
        if bucket is None:
            _pending_wager[d] = list(values)
        else:
            for i, v in enumerate(values):
                bucket[i] += v


async def flush_bot_command_counts(pool=None) -> None:
    """Сброс буферов в БД. При ошибке дельты возвращаются в буфер."""
    global _pending, _pending_wager
    if not _pending and not _pending_wager:
        return
    async with _flush_lock:
        if not _pending and not _pending_wager:
            return
        snapshot = _pending
        wager_snapshot = _pending_wager
        _pending = {}
        _pending_wager = {}

        if pool is None:
            pool = _resolve_pool()
        if pool is None:
            # Вернём — попробуем позже
            _requeue(snapshot, wager_snapshot)
            return

        await ensure_bot_command_stats_schema(pool)
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for d, n in snapshot.items():
                        if n <= 0:
                            continue
                        await conn.execute(
                            """
                            INSERT INTO bot_command_day_counts (day, commands, updated_at)
                            VALUES ($1, $2, NOW())
                            ON CONFLICT (day) DO UPDATE SET
                              commands = bot_command_day_counts.commands + EXCLUDED.commands,
                              updated_at = NOW()
                            """,
                            d,
                            int(n),
                        )
                    for d, (kut, plays, lost, won) in wager_snapshot.items():
                        if kut <= 0:
                            continue
                        await conn.execute(
                            """
                            INSERT INTO bot_game_wager_day_totals
                                (day, kut, plays, kut_lost, kut_won, updated_at)
                            VALUES ($1, $2, $3, $4, $5, NOW())
                            ON CONFLICT (day) DO UPDATE SET
                              kut = bot_game_wager_day_totals.kut + EXCLUDED.kut,
                              plays = bot_game_wager_day_totals.plays + EXCLUDED.plays,
                              kut_lost = bot_game_wager_day_totals.kut_lost + EXCLUDED.kut_lost,
                              kut_won = bot_game_wager_day_totals.kut_won + EXCLUDED.kut_won,
                              updated_at = NOW()
                            """,
                            d,
                            int(kut),
                            int(plays),
                            int(lost),
                            int(won),
                        )
        except Exception:
            logger.exception("flush bot stats counters failed — requeue")
            _requeue(snapshot, wager_snapshot)


def _resolve_pool():
    try:
        from db import db as server_db  # type: ignore
        if getattr(server_db, "pool", None):
            return server_db.pool
    except Exception:
        pass
    try:
        # bot process
        import main as main_mod  # type: ignore
        db_obj = getattr(main_mod, "db", None)
        if db_obj is not None and getattr(db_obj, "pool", None):
            return db_obj.pool
    except Exception:
        pass
    return None


def _empty_periods() -> dict:
    return {
        "day": {"current": 0, "previous": 0},
        "week": {"current": 0, "previous": 0},
        "month": {"current": 0, "previous": 0},
        "year": {"current": 0, "previous": 0},
    }


def _sum_range(by_day: dict[date, int], start: date, end: date) -> int:
    """Inclusive start, exclusive end."""
    total = 0
    d = start
    while d < end:
        total += int(by_day.get(d, 0))
        d += timedelta(days=1)
    return total


def _period_bounds(today: date) -> dict[str, tuple[date, date, date, date]]:
    """period → (cur_start, cur_end_excl, prev_start, prev_end_excl)."""
    day_cur_s, day_cur_e = today, today + timedelta(days=1)
    day_prev_s, day_prev_e = today - timedelta(days=1), today

    # ISO week: Monday start (Postgres date_trunc('week') behavior)
    week_cur_s = today - timedelta(days=today.weekday())
    week_cur_e = week_cur_s + timedelta(days=7)
    week_prev_s = week_cur_s - timedelta(days=7)
    week_prev_e = week_cur_s

    month_cur_s = today.replace(day=1)
    if month_cur_s.month == 12:
        month_cur_e = date(month_cur_s.year + 1, 1, 1)
    else:
        month_cur_e = date(month_cur_s.year, month_cur_s.month + 1, 1)
    if month_cur_s.month == 1:
        month_prev_s = date(month_cur_s.year - 1, 12, 1)
    else:
        month_prev_s = date(month_cur_s.year, month_cur_s.month - 1, 1)
    month_prev_e = month_cur_s

    year_cur_s = date(today.year, 1, 1)
    year_cur_e = date(today.year + 1, 1, 1)
    year_prev_s = date(today.year - 1, 1, 1)
    year_prev_e = year_cur_s

    return {
        "day": (day_cur_s, day_cur_e, day_prev_s, day_prev_e),
        "week": (week_cur_s, week_cur_e, week_prev_s, week_prev_e),
        "month": (month_cur_s, month_cur_e, month_prev_s, month_prev_e),
        "year": (year_cur_s, year_cur_e, year_prev_s, year_prev_e),
    }


async def fetch_bot_command_periods(pool) -> dict:
    """Агрегаты вызовов: day/week/month/year (+ previous). Учитывает pending-буфер."""
    out = _empty_periods()
    if pool is None:
        return out
    await ensure_bot_command_stats_schema(pool)
    today = _today_msk()
    since = date(today.year - 1, 1, 1)
    by_day: dict[date, int] = {}
    try:
        rows = await pool.fetch(
            """
            SELECT day, commands::bigint AS commands
            FROM bot_command_day_counts
            WHERE day >= $1
            """,
            since,
        )
        for r in rows:
            by_day[r["day"]] = int(r["commands"] or 0)
    except Exception:
        logger.exception("fetch bot_command_day_counts failed")
        return out

    # Добавляем ещё не сброшенный буфер (realtime без ожидания flush)
    for d, n in list(_pending.items()):
        by_day[d] = by_day.get(d, 0) + int(n)

    bounds = _period_bounds(today)
    for key, (cs, ce, ps, pe) in bounds.items():
        out[key] = {
            "current": _sum_range(by_day, cs, ce),
            "previous": _sum_range(by_day, ps, pe),
        }
    return out


async def fetch_game_wager_periods(pool) -> dict:
    """Оборот кут: day/week/month/year (+ previous, проиграно, выиграно)."""
    out = _empty_periods()
    if pool is None:
        return out
    await ensure_bot_command_stats_schema(pool)
    today = _today_msk()
    since = date(today.year - 1, 1, 1)
    total_by_day: dict[date, int] = {}
    lost_by_day: dict[date, int] = {}
    won_by_day: dict[date, int] = {}
    try:
        rows = await pool.fetch(
            """
            SELECT day, kut::bigint AS kut, kut_lost::bigint AS lost, kut_won::bigint AS won
            FROM bot_game_wager_day_totals
            WHERE day >= $1
            """,
            since,
        )
        for r in rows:
            total_by_day[r["day"]] = int(r["kut"] or 0)
            lost_by_day[r["day"]] = int(r["lost"] or 0)
            won_by_day[r["day"]] = int(r["won"] or 0)
    except Exception:
        logger.exception("fetch bot_game_wager_day_totals failed")
        return out

    for d, bucket in list(_pending_wager.items()):
        total_by_day[d] = total_by_day.get(d, 0) + int(bucket[0])
        lost_by_day[d] = lost_by_day.get(d, 0) + int(bucket[2])
        won_by_day[d] = won_by_day.get(d, 0) + int(bucket[3])

    for key, (cs, ce, ps, pe) in _period_bounds(today).items():
        out[key] = {
            "current": _sum_range(total_by_day, cs, ce),
            "previous": _sum_range(total_by_day, ps, pe),
            "lost": _sum_range(lost_by_day, cs, ce),
            "won": _sum_range(won_by_day, cs, ce),
        }
    return out


# ─── Detection helpers (shared with middleware) ─────────────────────────────

# Названия игр, встречающиеся в cause у cutehistory (+/-).
# Переводы, донаты и служебные списания сюда намеренно не попадают.
_GAME_CAUSE_WORDS = (
    "шашки", "мемори", "бинго", "фортуна", "кости", "дуэль",
    "орел", "орёл", "решка", "кнб", "мины", "крестики", "нолики",
    "башня", "риск", "плиты", "бомбы", "трейд", "шарик", "провода",
    "слоты", "баскетбол", "футбол", "боулинг", "дартс", "куб",
    "рулетка", "слова", "инлайн кн",
)


def is_game_cause(cause: Any) -> bool:
    """True, если запись в cutehistory относится к игре (ставка или выплата)."""
    try:
        text = str(cause or "").strip().lower()
    except Exception:
        return False
    if not text:
        return False
    if "перевод" in text or "sypher" in text:
        return False
    return any(word in text for word in _GAME_CAUSE_WORDS)


def note_game_cause_amount(cause: Any, amount, *, won: bool = False) -> None:
    """Хук для cutehistory: считает оборот, только если cause — игровой."""
    if is_game_cause(cause):
        note_game_wager(amount, won=won)




_BOT_COMMAND_EXACT = frozenset({
    "топ", "стата", "статистика", "вся стата", "вся статистика",
    "баланс", "мой баланс", "б", "профиль", "проф", "инвентарь", "инвент",
    "рюкзак", "магазин", "shop", "задания", "задание", "хелп", "help", "помощь",
    "царь", "king", "бонус", "донат", "donate", "кут", "бот",
    "брак", "мой брак", "развод", "клан", "мой клан",
    "трейд", "рулетка", "кости", "башня", "мемори", "бинго", "дуэль",
    "мины", "бомбы", "риск", "плиты", "шар", "шарик", "куб", "кубик",
    "спин", "слоты", "слот", "футбол", "баскет", "боулинг", "дартс",
})

_BOT_COMMAND_PREFIXES = (
    "/", "!", ".",
    "царь ", "king ", "топ ", "стата ", "статистика ",
    "хелп ", "help ", "профиль", "магазин", "задания",
    "дать ", "sypher", "кут ", "кут,", "баланс ",
    "трейд ", "рулетка ", "кости ", "башня ", "мемори ",
    "бинго ", "дуэль ", "мины ", "бомбы ", "риск ", "плиты ",
    "шар ", "шарик ", "куп ", "купить ", "отправить ", "передать ",
)


def is_bot_command_message(message: Any) -> bool:
    """True, если сообщение — вызов команды/функции бота (не обычный чат)."""
    try:
        from_user = getattr(message, "from_user", None)
        if from_user is not None and bool(getattr(from_user, "is_bot", False)):
            return False

        entities = list(getattr(message, "entities", None) or []) + list(
            getattr(message, "caption_entities", None) or []
        )
        for ent in entities:
            if str(getattr(ent, "type", "")).lower() == "bot_command":
                return True

        raw = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        normalized = " ".join(str(raw).strip().lower().split())
        if not normalized:
            return False

        if normalized.startswith("/") or normalized.startswith("!") or normalized.startswith("."):
            return True
        if normalized in _BOT_COMMAND_EXACT:
            return True
        if any(normalized.startswith(p) for p in _BOT_COMMAND_PREFIXES):
            return True

        try:
            from bot.funcs.king_stats import is_king_stats_command
            if is_king_stats_command(normalized):
                return True
        except Exception:
            pass

        try:
            from bot.funcs.best_players import is_best_players_command
            if is_best_players_command(normalized):
                return True
        except Exception:
            pass

        return False
    except Exception:
        return False
