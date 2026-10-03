"""Отдельные счётчики, пока у статистики открыта копия.

Лучшие игроки, победы и проигрыши копируются по отдельности.
Пока открыта копия игр, новые игры пишутся в epsilon_players_hold
и не попадают в user_games_day. Победы и проигрыши при этом идут
в свои счётчики, только если открыта именно их копия.
Когда срок кончился — или создатель снимает новую копию, или убирает текущую —
отдельный счётчик прибавляется к основной статистике и удаляется.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

try:
    from server.stat_lens import hold_destination
except ImportError:  # панель запускается с server/ в пути импорта
    from stat_lens import hold_destination

# Один замок на запись игры и на сложение счётчиков. Совпадает у бота и у панели.
HOLD_LOCK = 872343
_MSK = timezone(timedelta(hours=3))
_OUTCOME_COLUMN = {"wins": "wins", "losses": "loose"}


async def ensure_players_hold(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_players_hold (
            user_id BIGINT NOT NULL,
            day DATE NOT NULL,
            wins BIGINT NOT NULL DEFAULT 0,
            loose BIGINT NOT NULL DEFAULT 0,
            games BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_games_day (
            user_id BIGINT NOT NULL,
            day DATE NOT NULL,
            games BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    await connection.execute(
        "ALTER TABLE user_games_day ADD COLUMN IF NOT EXISTS wins BIGINT NOT NULL DEFAULT 0"
    )
    await connection.execute(
        "ALTER TABLE user_games_day ADD COLUMN IF NOT EXISTS loose BIGINT NOT NULL DEFAULT 0"
    )
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_stat_season (
            metric TEXT NOT NULL,
            chat_id BIGINT NOT NULL DEFAULT 0,
            zero_from DATE NOT NULL,
            zero_until DATE NOT NULL,
            copied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            count_from TIMESTAMPTZ,
            PRIMARY KEY (metric, chat_id)
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_stat_hold (
            metric TEXT NOT NULL,
            user_id BIGINT NOT NULL,
            day DATE NOT NULL,
            amount BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (metric, user_id, day)
        )
        """
    )


async def _season(connection):
    return await connection.fetchrow(
        """
        SELECT zero_from, zero_until
        FROM epsilon_stat_season
        WHERE metric = 'players' AND chat_id = 0
        """
    )


async def _fold(connection) -> None:
    """Прибавить отдельный счётчик к users и user_games_day и очистить его."""
    await connection.execute(
        """
        UPDATE users AS u
        SET wins = COALESCE(u.wins, 0) + h.wins
        FROM (
            SELECT user_id, COALESCE(SUM(wins), 0)::bigint AS wins
            FROM epsilon_players_hold
            GROUP BY user_id
            HAVING COALESCE(SUM(wins), 0) <> 0
        ) AS h
        WHERE u.user_id = h.user_id
        """
    )
    await connection.execute(
        """
        UPDATE users AS u
        SET loose = COALESCE(u.loose, 0) + h.loose
        FROM (
            SELECT user_id, COALESCE(SUM(loose), 0)::bigint AS loose
            FROM epsilon_players_hold
            GROUP BY user_id
            HAVING COALESCE(SUM(loose), 0) <> 0
        ) AS h
        WHERE u.user_id = h.user_id
        """
    )
    await connection.execute(
        """
        INSERT INTO user_games_day (user_id, day, games, wins, loose)
        SELECT user_id,
               day,
               COALESCE(games, 0)::bigint,
               COALESCE(wins, 0)::bigint,
               COALESCE(loose, 0)::bigint
        FROM epsilon_players_hold
        WHERE COALESCE(games, 0) <> 0
           OR COALESCE(wins, 0) <> 0
           OR COALESCE(loose, 0) <> 0
        ON CONFLICT (user_id, day) DO UPDATE
        SET games = user_games_day.games + EXCLUDED.games,
            wins = COALESCE(user_games_day.wins, 0) + EXCLUDED.wins,
            loose = COALESCE(user_games_day.loose, 0) + EXCLUDED.loose
        """
    )
    await connection.execute("DELETE FROM epsilon_players_hold")


async def game_goes_to_hold(connection, today: date) -> bool:
    """True — эту игру писать в отдельный счётчик.

    Вызывать внутри транзакции, до записи победы или проигрыша.
    Если срок копии уже кончился, сначала складывает отдельный счётчик с основной статистикой.
    """
    await ensure_players_hold(connection)
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    row = await _season(connection)
    if row is None:
        return False
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "fold":
        await _fold(connection)
        return False
    return dest == "hold"


async def add_held_game(
    connection,
    user_id: int,
    day: date,
    *,
    wins: int = 0,
    loose: int = 0,
    games: int | None = None,
) -> None:
    won = int(wins or 0)
    lost = int(loose or 0)
    played = won + lost if games is None else int(games)
    if won == 0 and lost == 0 and played == 0:
        return
    await connection.execute(
        """
        INSERT INTO epsilon_players_hold (user_id, day, wins, loose, games)
        VALUES ($1::bigint, $2::date, $3::bigint, $4::bigint, $5::bigint)
        ON CONFLICT (user_id, day) DO UPDATE
        SET wins = epsilon_players_hold.wins + EXCLUDED.wins,
            loose = epsilon_players_hold.loose + EXCLUDED.loose,
            games = epsilon_players_hold.games + EXCLUDED.games
        """,
        int(user_id),
        day,
        won,
        lost,
        played,
    )


async def public_players_gate(connection, today: date) -> tuple[bool, bool, date | None]:
    """(спрятать топ, счётчик уже сложен, дата когда топ снова виден).

    Вызывать внутри транзакции перед показом топа.
    """
    await ensure_players_hold(connection)
    row = await _season(connection)
    if row is None or row["zero_from"] is None or row["zero_until"] is None:
        return False, False, None
    lift = row["zero_until"] + timedelta(days=1)
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "hold":
        return True, False, lift
    if dest != "fold":
        return False, False, lift
    pending = await connection.fetchval("SELECT 1 FROM epsilon_players_hold LIMIT 1")
    if not pending:
        return False, False, lift
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    row = await _season(connection)
    if row is None or row["zero_from"] is None or row["zero_until"] is None:
        pending = await connection.fetchval("SELECT 1 FROM epsilon_players_hold LIMIT 1")
        if pending:
            await _fold(connection)
            return False, True, None
        return False, False, None
    lift = row["zero_until"] + timedelta(days=1)
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "hold":
        return True, False, lift
    pending = await connection.fetchval("SELECT 1 FROM epsilon_players_hold LIMIT 1")
    if dest == "fold" and pending:
        await _fold(connection)
        return False, True, lift
    return False, False, lift


async def fold_held_games_now(connection) -> bool:
    """Сложить отдельный счётчик с основной статистикой, даже если срок копии ещё идёт.

    Нужно перед новой копией и когда создатель убирает копию раньше срока.
    Вызывать внутри транзакции.
    """
    await ensure_players_hold(connection)
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    pending = await connection.fetchval("SELECT 1 FROM epsilon_players_hold LIMIT 1")
    if not pending:
        return False
    await _fold(connection)
    return True


async def held_board(connection, *, viewer_id: int, start: date | None, end: date | None, limit: int) -> dict:
    """Топ по играм отдельного счётчика. Для людей это обычный топ, без пометки про копию.

    start и end пустые — все дни счётчика, то есть «за всё время» на экране.
    Иначе только дни выбранного срока.
    """
    viewer = int(viewer_id)
    cap = int(limit)
    if start is None or end is None:
        rows = await connection.fetch(
            """
            SELECT user_id, COALESCE(SUM(games), 0)::bigint AS games
            FROM epsilon_players_hold
            GROUP BY user_id
            HAVING COALESCE(SUM(games), 0) > 0
            ORDER BY games DESC, user_id ASC
            LIMIT $1
            """,
            cap,
        )
        viewer_games = int(await connection.fetchval(
            """
            SELECT COALESCE(SUM(games), 0)::bigint
            FROM epsilon_players_hold
            WHERE user_id = $1
            """,
            viewer,
        ) or 0)
        ahead = 0
        if viewer_games > 0:
            ahead = int(await connection.fetchval(
                """
                WITH totals AS (
                    SELECT user_id, SUM(games)::bigint AS games
                    FROM epsilon_players_hold
                    GROUP BY user_id
                    HAVING SUM(games) > 0
                )
                SELECT COUNT(*)::int
                FROM totals
                WHERE games > $1
                   OR (games = $1 AND user_id < $2)
                """,
                viewer_games,
                viewer,
            ) or 0)
    else:
        rows = await connection.fetch(
            """
            SELECT user_id, COALESCE(SUM(games), 0)::bigint AS games
            FROM epsilon_players_hold
            WHERE day >= $1::date AND day <= $2::date
            GROUP BY user_id
            HAVING COALESCE(SUM(games), 0) > 0
            ORDER BY games DESC, user_id ASC
            LIMIT $3
            """,
            start,
            end,
            cap,
        )
        viewer_games = int(await connection.fetchval(
            """
            SELECT COALESCE(SUM(games), 0)::bigint
            FROM epsilon_players_hold
            WHERE user_id = $1 AND day >= $2::date AND day <= $3::date
            """,
            viewer,
            start,
            end,
        ) or 0)
        ahead = 0
        if viewer_games > 0:
            ahead = int(await connection.fetchval(
                """
                WITH totals AS (
                    SELECT user_id, SUM(games)::bigint AS games
                    FROM epsilon_players_hold
                    WHERE day >= $2::date AND day <= $3::date
                    GROUP BY user_id
                    HAVING SUM(games) > 0
                )
                SELECT COUNT(*)::int
                FROM totals
                WHERE games > $1
                   OR (games = $1 AND user_id < $4)
                """,
                viewer_games,
                start,
                end,
                viewer,
            ) or 0)
    return {
        "rows": [(int(row["user_id"]), int(row["games"] or 0)) for row in rows],
        "place": (ahead + 1) if viewer_games > 0 else None,
        "viewer_games": viewer_games,
    }


async def held_totals(pool, *, start: date | None = None, end: date | None = None) -> dict[int, dict]:
    """Сколько игр лежит в отдельном счётчике. Пустой словарь, если таблицы ещё нет."""
    if pool is None:
        return {}
    try:
        if start is None or end is None:
            rows = await pool.fetch(
                """
                SELECT user_id,
                       COALESCE(SUM(wins), 0)::bigint AS wins,
                       COALESCE(SUM(loose), 0)::bigint AS losses,
                       COALESCE(SUM(games), 0)::bigint AS games
                FROM epsilon_players_hold
                GROUP BY user_id
                HAVING COALESCE(SUM(games), 0) <> 0
                    OR COALESCE(SUM(wins), 0) <> 0
                    OR COALESCE(SUM(loose), 0) <> 0
                """
            )
        else:
            rows = await pool.fetch(
                """
                SELECT user_id,
                       COALESCE(SUM(wins), 0)::bigint AS wins,
                       COALESCE(SUM(loose), 0)::bigint AS losses,
                       COALESCE(SUM(games), 0)::bigint AS games
                FROM epsilon_players_hold
                WHERE day >= $1::date AND day <= $2::date
                GROUP BY user_id
                HAVING COALESCE(SUM(games), 0) <> 0
                    OR COALESCE(SUM(wins), 0) <> 0
                    OR COALESCE(SUM(loose), 0) <> 0
                """,
                start,
                end,
            )
    except Exception:
        return {}
    return {
        int(row["user_id"]): {
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "games": int(row["games"] or 0),
        }
        for row in rows
    }


def _moscow_today() -> date:
    return datetime.now(_MSK).date()


class Played:
    """Куда легла одна игра: в отдельный счётчик или в основную статистику."""

    def __init__(self, games_held: bool, wins_held: bool, losses_held: bool):
        self.games_held = games_held
        self.wins_held = wins_held
        self.losses_held = losses_held


async def _outcome_season(connection, metric: str):
    return await connection.fetchrow(
        """
        SELECT zero_from, zero_until
        FROM epsilon_stat_season
        WHERE metric = $1 AND chat_id = 0
        """,
        metric,
    )


async def _fold_outcome(connection, metric: str) -> None:
    column = _OUTCOME_COLUMN[metric]
    await connection.execute(
        f"""
        UPDATE users AS u
        SET {column} = COALESCE(u.{column}, 0) + h.amount
        FROM (
            SELECT user_id, COALESCE(SUM(amount), 0)::bigint AS amount
            FROM epsilon_stat_hold
            WHERE metric = $1
            GROUP BY user_id
            HAVING COALESCE(SUM(amount), 0) <> 0
        ) AS h
        WHERE u.user_id = h.user_id
        """,
        metric,
    )
    await connection.execute("DELETE FROM epsilon_stat_hold WHERE metric = $1", metric)


async def outcome_goes_to_hold(connection, metric: str, today: date) -> bool:
    """True — эту победу или проигрыш писать в свой отдельный счётчик.

    Копия игр на это не влияет. Вызывать внутри транзакции.
    """
    if metric not in _OUTCOME_COLUMN:
        return False
    await ensure_players_hold(connection)
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    row = await _outcome_season(connection, metric)
    if row is None:
        return False
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "fold":
        await _fold_outcome(connection, metric)
        return False
    return dest == "hold"


async def add_outcome_hold(connection, metric: str, user_id: int, day: date, amount: int) -> None:
    gained = int(amount or 0)
    if metric not in _OUTCOME_COLUMN or gained == 0:
        return
    await connection.execute(
        """
        INSERT INTO epsilon_stat_hold (metric, user_id, day, amount)
        VALUES ($1, $2::bigint, $3::date, $4::bigint)
        ON CONFLICT (metric, user_id, day) DO UPDATE
        SET amount = epsilon_stat_hold.amount + EXCLUDED.amount
        """,
        metric,
        int(user_id),
        day,
        gained,
    )


async def place_played(connection, user_id: int, day: date, *, wins: int = 0, loose: int = 0) -> Played:
    """Разложить одну игру по открытым копиям.

    Копия лучших игроков забирает только число игр.
    Копия побед забирает только победы, копия проигрышей — только проигрыши.
    """
    won = int(wins or 0)
    lost = int(loose or 0)
    played = won + lost
    games_held = await game_goes_to_hold(connection, day)
    if games_held and played:
        await add_held_game(connection, int(user_id), day, games=played)
    wins_held = False
    losses_held = False
    if won:
        wins_held = await outcome_goes_to_hold(connection, "wins", day)
        if wins_held:
            await add_outcome_hold(connection, "wins", int(user_id), day, won)
    if lost:
        losses_held = await outcome_goes_to_hold(connection, "losses", day)
        if losses_held:
            await add_outcome_hold(connection, "losses", int(user_id), day, lost)
    return Played(games_held, wins_held, losses_held)


async def fold_outcome_now(connection, metric: str) -> bool:
    """Сложить отдельный счётчик побед или проигрышей, даже если срок ещё идёт."""
    if metric not in _OUTCOME_COLUMN:
        return False
    await ensure_players_hold(connection)
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    pending = await connection.fetchval(
        "SELECT 1 FROM epsilon_stat_hold WHERE metric = $1 LIMIT 1",
        metric,
    )
    if not pending:
        return False
    await _fold_outcome(connection, metric)
    return True


async def public_outcome_gate(connection, today: date, metric: str) -> tuple[bool, bool, date | None]:
    """(топ показывает отдельный счётчик, счётчик уже сложен, дата снятия)."""
    if metric not in _OUTCOME_COLUMN:
        return False, False, None
    await ensure_players_hold(connection)
    row = await _outcome_season(connection, metric)
    if row is None or row["zero_from"] is None or row["zero_until"] is None:
        return False, False, None
    lift = row["zero_until"] + timedelta(days=1)
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "hold":
        return True, False, lift
    if dest != "fold":
        return False, False, lift
    pending = await connection.fetchval(
        "SELECT 1 FROM epsilon_stat_hold WHERE metric = $1 LIMIT 1",
        metric,
    )
    if not pending:
        return False, False, lift
    await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)", HOLD_LOCK)
    row = await _outcome_season(connection, metric)
    if row is None or row["zero_from"] is None or row["zero_until"] is None:
        pending = await connection.fetchval(
            "SELECT 1 FROM epsilon_stat_hold WHERE metric = $1 LIMIT 1",
            metric,
        )
        if pending:
            await _fold_outcome(connection, metric)
            return False, True, None
        return False, False, None
    lift = row["zero_until"] + timedelta(days=1)
    dest = hold_destination(today, row["zero_from"], row["zero_until"])
    if dest == "hold":
        return True, False, lift
    pending = await connection.fetchval(
        "SELECT 1 FROM epsilon_stat_hold WHERE metric = $1 LIMIT 1",
        metric,
    )
    if dest == "fold" and pending:
        await _fold_outcome(connection, metric)
        return False, True, lift
    return False, False, lift


async def outcome_totals(pool, metric: str) -> dict[int, int]:
    """Сколько побед или проигрышей лежит в отдельном счётчике."""
    if pool is None or metric not in _OUTCOME_COLUMN:
        return {}
    try:
        rows = await pool.fetch(
            """
            SELECT user_id, COALESCE(SUM(amount), 0)::bigint AS amount
            FROM epsilon_stat_hold
            WHERE metric = $1
            GROUP BY user_id
            HAVING COALESCE(SUM(amount), 0) <> 0
            """,
            metric,
        )
    except Exception:
        return {}
    return {int(row["user_id"]): int(row["amount"] or 0) for row in rows}


async def public_outcome_rows(pool, metric: str):
    """Пары (user_id, число) для чата, пока открыта копия этой статистики.

    None — копии нет, чат читает основную колонку.
    Список — даже пустой — копия открыта. Основную колонку в этом случае не показывать.
    """
    if pool is None or metric not in _OUTCOME_COLUMN:
        return None
    hidden = False
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                hidden, _folded, _lift = await public_outcome_gate(connection, _moscow_today(), metric)
            if not hidden:
                return None
            rows = await connection.fetch(
                """
                SELECT user_id, COALESCE(SUM(amount), 0)::bigint AS amount
                FROM epsilon_stat_hold
                WHERE metric = $1
                GROUP BY user_id
                HAVING COALESCE(SUM(amount), 0) > 0
                ORDER BY amount DESC, user_id ASC
                """,
                metric,
            )
    except Exception:
        return [] if hidden else None
    return [(int(row["user_id"]), int(row["amount"] or 0)) for row in rows]
