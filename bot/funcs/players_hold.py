"""Отдельный счётчик игр, пока у лучших игроков открыта копия.

Пока срок копии не кончился, победы и проигрыши пишутся в epsilon_players_hold.
users.wins, users.loose и user_games_day в это время не растут.
Когда срок кончился — или создатель снимает новую копию, или убирает текущую —
строки отдельного счётчика прибавляются к основной статистике и удаляются.
"""
from __future__ import annotations

from datetime import date, timedelta

try:
    from server.stat_lens import hold_destination
except ImportError:  # панель запускается с server/ в пути импорта
    from stat_lens import hold_destination

# Один замок на запись игры и на сложение счётчиков. Совпадает у бота и у панели.
HOLD_LOCK = 872343


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


async def add_held_game(connection, user_id: int, day: date, *, wins: int = 0, loose: int = 0) -> None:
    won = int(wins or 0)
    lost = int(loose or 0)
    games = won + lost
    if won == 0 and lost == 0:
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
        games,
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
