"""Общая проверка наказаний.

Первый проход делает другой администратор архива: «подходит», «не подходит»
или «непонятно». Создатель видит уже проверенную очередь, и только его решение
входит в зарплату.

«Подходит» и «не подходит» закрывают первый проход. «Непонятно» его не закрывает:
наказание остаётся у остальных администраторов и сразу приходит создателю.
Кто первым ответит точно или решит сам создатель, тот и закрывает дело.

Порядок первого прохода: с фото, затем с причиной, пустые в конце.
Внутри стопки старые раньше новых.
Порядок второго прохода: подходит, не подходит, непонятно, затем те,
которые было некому проверить.
"""

from __future__ import annotations

from human_actor import human_actor_sql

VERDICT_CLEAR = "clear"
VERDICT_WRONG = "wrong"
VERDICT_WEAK = "weak"
VERDICTS = (VERDICT_CLEAR, VERDICT_WRONG, VERDICT_WEAK)

VERDICT_LABELS = {
    VERDICT_CLEAR: "Подходит",
    VERDICT_WRONG: "Не подходит",
    VERDICT_WEAK: "Непонятно",
}

BAND_PHOTO = "photo"
BAND_REASON = "reason"
BAND_EMPTY = "empty"

CREATE_SORTS_SQL = """
CREATE TABLE IF NOT EXISTS epsilon_deed_sorts (
    action_id BIGINT PRIMARY KEY,
    verdict TEXT NOT NULL,
    sorter_id BIGINT NOT NULL,
    sorted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

CREATE_UNCLEAR_SQL = """
CREATE TABLE IF NOT EXISTS epsilon_deed_unclear (
    action_id BIGINT NOT NULL,
    sorter_id BIGINT NOT NULL,
    marked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (action_id, sorter_id)
)
"""

# Раньше «непонятно» закрывало дело для всех. Такие пометки переезжают
# в общий список «непонятно», и дело снова видят остальные администраторы.
MOVE_OLD_UNCLEAR_SQL = """
WITH old AS (
  DELETE FROM epsilon_deed_sorts
  WHERE verdict = 'weak'
  RETURNING action_id, sorter_id, sorted_at
)
INSERT INTO epsilon_deed_unclear (action_id, sorter_id, marked_at)
SELECT action_id, sorter_id, sorted_at FROM old
ON CONFLICT (action_id, sorter_id) DO NOTHING
"""

ADMIN_ORDER_SQL = """
CASE
  WHEN COALESCE(s.proof_media_id, '') <> '' THEN 0
  WHEN btrim(COALESCE(s.reason, '')) <> '' THEN 1
  ELSE 2
END,
s.created_at ASC NULLS LAST,
s.id ASC
"""

CREATOR_ORDER_SQL = """
CASE
  WHEN ds.verdict = 'clear' THEN 0
  WHEN ds.verdict = 'wrong' THEN 1
  WHEN ds.verdict = 'weak' OR COALESCE(dq.n, 0) > 0 THEN 2
  ELSE 3
END,
s.created_at ASC NULLS LAST,
s.id ASC
"""

_READY = False


def evidence_band(has_proof: bool, reason: str) -> str:
    if has_proof:
        return BAND_PHOTO
    if str(reason or "").strip():
        return BAND_REASON
    return BAND_EMPTY


def creator_rank(verdict: str | None) -> int:
    return {
        VERDICT_CLEAR: 0,
        VERDICT_WRONG: 1,
        VERDICT_WEAK: 2,
    }.get(str(verdict or ""), 3)


def unclear_join_sql(action: str = "s") -> str:
    """Кто уже ответил «непонятно» на это наказание: dq.n и dq.names."""
    return f"""
    LEFT JOIN LATERAL (
      SELECT
        COUNT(*)::int AS n,
        COALESCE(
          array_agg(
            COALESCE(NULLIF(btrim(uu.first_name), ''), NULLIF(btrim(uu.username), ''), 'ID ' || du.sorter_id::text)
            ORDER BY du.marked_at
          ),
          ARRAY[]::text[]
        ) AS names
      FROM epsilon_deed_unclear du
      LEFT JOIN users uu ON uu.user_id = du.sorter_id
      WHERE du.action_id = {action}.id
    ) dq ON TRUE
    """


def verdict_of_sql(action_id_sql: str) -> str:
    """Пометка для архива: точный ответ, а если его нет — «непонятно»."""
    return f"""COALESCE(
      (SELECT ds.verdict FROM epsilon_deed_sorts ds WHERE ds.action_id = {action_id_sql}),
      (SELECT 'weak'::text FROM epsilon_deed_unclear du WHERE du.action_id = {action_id_sql} LIMIT 1)
    )"""


def _owner_ids_sql() -> str:
    from config import owner_user_ids

    ids = [int(item) for item in owner_user_ids()] or [0]
    return ", ".join(str(item) for item in ids)


def _live_archive_seat(seat: str, position: str) -> str:
    return f"""
      {position}.kind = 'post'
      AND {position}.rights @> '["view_archive"]'::jsonb
      AND ({seat}.term_end IS NULL OR {seat}.term_end > NOW())
      AND EXISTS (
        SELECT 1 FROM epsilon_group_keys k
        WHERE k.user_id = {seat}.user_id
          AND NOT k.disabled
          AND COALESCE(k.key_hash, '') <> ''
      )
    """


def other_sorter_exists(action: str = "s") -> str:
    """Есть другой администратор архива, который может проверить это дело."""
    owners = _owner_ids_sql()
    return f"""
      EXISTS (
        SELECT 1
        FROM epsilon_seats o
        JOIN epsilon_positions p ON p.id = o.position_id
        WHERE o.user_id <> COALESCE({action}.admin_user_id, 0)
          AND o.user_id NOT IN ({owners})
          AND {_live_archive_seat("o", "p")}
          AND (
            (COALESCE({action}.chat_id, 0) <> 0 AND o.chat_id = {action}.chat_id)
            OR COALESCE({action}.chat_id, 0) = 0
          )
      )
    """


def self_can_sort(action: str = "s", user_sql: str = "$2") -> str:
    """Этот человек проверяет чужое дело в своей группе."""
    owners = _owner_ids_sql()
    return f"""
      EXISTS (
        SELECT 1
        FROM epsilon_seats me
        JOIN epsilon_positions mp ON mp.id = me.position_id
        WHERE me.user_id = {user_sql}
          AND me.user_id <> COALESCE({action}.admin_user_id, 0)
          AND me.user_id NOT IN ({owners})
          AND {_live_archive_seat("me", "mp")}
          AND (
            (COALESCE({action}.chat_id, 0) <> 0 AND me.chat_id = {action}.chat_id)
            OR COALESCE({action}.chat_id, 0) = 0
          )
      )
    """


def creator_ready_sql(action: str = "s") -> str:
    """Создателю: уже проверенное, «непонятно» или то, что проверить некому.

    В запросе должны быть ds (точный ответ) и dq из unclear_join_sql.
    """
    return f"(ds.action_id IS NOT NULL OR COALESCE(dq.n, 0) > 0 OR NOT ({other_sorter_exists(action)}))"


_MARKS_SQL = """
    marks AS (
      SELECT action_id, sorter_id, verdict, sorted_at AS at
      FROM epsilon_deed_sorts
      UNION ALL
      SELECT action_id, sorter_id, 'weak' AS verdict, marked_at AS at
      FROM epsilon_deed_unclear
    )"""


def _marks_from_sql() -> str:
    return f"""
      FROM marks m
      JOIN staff_actions s ON s.id = m.action_id
      LEFT JOIN epsilon_deed_reviews dr ON dr.action_id = m.action_id
      WHERE s.action_type IN ('ban', 'mute', 'kick', 'warn')
        AND {human_actor_sql("s")}
    """


def reviewer_roster_sql() -> str:
    """Все, кто может проверять чужие наказания, и сколько каждый уже проверил.

    Живой кабинет с правом архива остаётся в списке даже с нулём.
    Кто проверял раньше и место потерял, тоже остаётся: его ответы уже в архиве.
    """
    owners = _owner_ids_sql()
    live = _live_archive_seat("o", "p")
    return f"""
    WITH live AS (
      SELECT o.user_id, MAX(p.title) AS title
      FROM epsilon_seats o
      JOIN epsilon_positions p ON p.id = o.position_id
      WHERE o.user_id NOT IN ({owners})
        AND {live}
      GROUP BY o.user_id
    ),
    {_MARKS_SQL},
    stats AS (
      SELECT
        m.sorter_id,
        COUNT(*)::int AS reviewed,
        COUNT(*) FILTER (WHERE m.verdict = 'clear')::int AS clear_n,
        COUNT(*) FILTER (WHERE m.verdict = 'wrong')::int AS wrong_n,
        COUNT(*) FILTER (WHERE m.verdict = 'weak')::int AS weak_n,
        COUNT(*) FILTER (WHERE dr.status = 'kept')::int AS kept_n,
        COUNT(*) FILTER (WHERE dr.status = 'dropped')::int AS dropped_n,
        COUNT(*) FILTER (WHERE dr.action_id IS NULL)::int AS open_n,
        MAX(m.at) AS last_at
      {_marks_from_sql()}
      GROUP BY m.sorter_id
    )
    SELECT
      people.user_id AS id,
      COALESCE(NULLIF(btrim(u.first_name), ''), NULLIF(btrim(u.username), ''), '') AS name,
      COALESCE(u.username, '') AS username,
      COALESCE(live.title, '') AS title,
      COALESCE(stats.reviewed, 0) AS reviewed,
      COALESCE(stats.clear_n, 0) AS clear_n,
      COALESCE(stats.wrong_n, 0) AS wrong_n,
      COALESCE(stats.weak_n, 0) AS weak_n,
      COALESCE(stats.kept_n, 0) AS kept_n,
      COALESCE(stats.dropped_n, 0) AS dropped_n,
      COALESCE(stats.open_n, 0) AS open_n,
      stats.last_at
    FROM (
      SELECT user_id FROM live
      UNION
      SELECT sorter_id AS user_id FROM stats
    ) people
    LEFT JOIN live ON live.user_id = people.user_id
    LEFT JOIN stats ON stats.sorter_id = people.user_id
    LEFT JOIN users u ON u.user_id = people.user_id
    WHERE people.user_id IS NOT NULL
      AND people.user_id <> 0
      AND people.user_id NOT IN ({owners})
    ORDER BY COALESCE(stats.reviewed, 0) DESC, stats.last_at DESC NULLS LAST, people.user_id ASC
    """


def reviewer_totals_sql() -> str:
    """Итог по всем: одно наказание считается один раз, даже если его смотрели двое."""
    owners = _owner_ids_sql()
    return f"""
    WITH {_MARKS_SQL.strip()}
    SELECT
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.status = 'kept')::int AS kept_n,
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.status = 'dropped')::int AS dropped_n,
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.action_id IS NULL)::int AS open_n
    {_marks_from_sql()}
      AND m.sorter_id NOT IN ({owners})
    """


async def ensure_deed_sorts() -> None:
    global _READY
    if _READY:
        return
    from db import db

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('epsilon_deed_sorts'))")
            await conn.execute(CREATE_SORTS_SQL)
            await conn.execute(CREATE_UNCLEAR_SQL)
            await conn.execute(MOVE_OLD_UNCLEAR_SQL)
    _READY = True
