"""Цепочка проверки наказаний.

Один администратор группы отвечает первым. Ответ — любой, включая
«непонятно», — закрывает этап: остальные администраторы эту карточку
больше не видят. Дальше её может взять один сотрудник проекта.

Создателю хватает любого уже готового ответа: администратора или сотрудника.
Карточку, которую ещё никто не открыл, он может проверить сам. «Подходит»
сразу пишет зарплату тому, кто выдал — администратор это или сотрудник.

Если на этапе некому проверять, карточка перескакивает дальше сама.
Заявка на разблокировку остаётся у создателя, пока он её не решит.

В зарплату попадает тот, чей ответ совпал с решением создателя.
«Непонятно» — это не ответ, за него не платят.
"""

from __future__ import annotations

from human_actor import human_actor_sql

VERDICT_CLEAR = "clear"
VERDICT_WRONG = "wrong"
VERDICT_WEAK = "weak"
VERDICTS = (VERDICT_CLEAR, VERDICT_WRONG, VERDICT_WEAK)

VERDICT_LABELS = {
    VERDICT_CLEAR: "Подходит",
    VERDICT_WRONG: "Наказание выдано неправильно",
    VERDICT_WEAK: "Непонятно",
}

STAGE_ADMIN = "admin"
STAGE_STAFF = "staff"
CLAIM_SECONDS = 75

CHECK_ADMIN = "check_admin"
CHECK_STAFF = "check_staff"
CHECK_RATES = (
    (CHECK_ADMIN, "Проверки администраторов"),
    (CHECK_STAFF, "Проверки сотрудников"),
)

STAFF_ROLES = ("senior_admin", "junior_admin", "moderator")
CREDIT_ROLES = ("issue", "admin", "staff")

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

# Раньше «непонятно» не закрывало этап и копилось отдельно.
# Теперь у карточки один ответ: берём самый ранний и закрываем им этап.
FOLD_UNCLEAR_SQL = """
INSERT INTO epsilon_deed_sorts (action_id, verdict, sorter_id, sorted_at)
SELECT DISTINCT ON (u.action_id) u.action_id, 'weak', u.sorter_id, u.marked_at
FROM epsilon_deed_unclear u
WHERE NOT EXISTS (
    SELECT 1 FROM epsilon_deed_sorts s WHERE s.action_id = u.action_id
)
ORDER BY u.action_id, u.marked_at ASC
ON CONFLICT (action_id) DO NOTHING
"""

CREATE_STAFF_SQL = """
CREATE TABLE IF NOT EXISTS epsilon_deed_staff (
    action_id BIGINT PRIMARY KEY,
    verdict TEXT NOT NULL,
    lift_ask BOOLEAN NOT NULL DEFAULT FALSE,
    lift_status TEXT,
    staff_id BIGINT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lift_decided_at TIMESTAMPTZ,
    lift_decided_by BIGINT
)
"""

CREATE_CLAIMS_SQL = """
CREATE TABLE IF NOT EXISTS epsilon_deed_claims (
    action_id BIGINT NOT NULL,
    stage TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    until_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (action_id, stage)
)
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

# Сначала живая заявка на разблокировку: человек может быть наказан зря.
# Потом согласие обоих, потом спор, потом «непонятно», в конце пропуски.
CREATOR_ORDER_SQL = """
CASE
  WHEN COALESCE(st.lift_ask, FALSE) AND st.lift_status = 'pending' THEN 0
  WHEN ds.verdict = 'clear' AND st.verdict = 'clear' THEN 1
  WHEN ds.verdict = 'wrong' AND st.verdict = 'wrong' THEN 2
  WHEN ds.verdict IN ('clear', 'wrong') AND st.verdict IN ('clear', 'wrong')
       AND ds.verdict <> st.verdict THEN 3
  WHEN ds.verdict = 'weak' OR st.verdict = 'weak' THEN 4
  WHEN ds.verdict = 'clear' OR st.verdict = 'clear' THEN 1
  WHEN ds.verdict = 'wrong' OR st.verdict = 'wrong' THEN 2
  ELSE 5
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
        VERDICT_CLEAR: 1,
        VERDICT_WRONG: 2,
        VERDICT_WEAK: 4,
    }.get(str(verdict or ""), 5)


def pick_credits(
    status: str,
    people: list[tuple[str, int, str]],
    asked: set[tuple[str, int]] | None,
) -> list[tuple[str, int]]:
    """Кого засчитать. asked is None — всех, чей ответ совпал. Пустой набор — никого."""
    eligible = [
        (role, int(user_id))
        for role, user_id, verdict in people
        if int(user_id or 0) > 0 and credit_eligible(status, role, verdict or "")
    ]
    if asked is None:
        return eligible
    return [pair for pair in eligible if pair in asked]


def self_settle(verdict: str, issuer_id: int) -> tuple[str, list[tuple[str, int]]]:
    """Проверка самого создателя сразу закрывает зарплату.

    «Подходит» засчитывает тому, кто выдал. Кто он — администратор группы
    или сотрудник проекта — для записи не важно. «Неправильно» и «непонятно»
    никого не оплачивают: выдавать было нельзя или твёрдого ответа нет.
    """
    issuer = int(issuer_id or 0)
    if verdict == VERDICT_CLEAR and issuer > 0:
        return "kept", [("issue", issuer)]
    return "dropped", []


def credit_eligible(status: str, role: str, verdict: str) -> bool:
    """Совпал ли ответ человека с решением создателя.

    Выдавшему платят только когда наказание признано верным.
    Проверившему — когда его «подходит» или «неправильно» совпало.
    «Непонятно» не совпадает ни с чем.
    """
    if role == "issue":
        return status == "kept"
    if verdict == VERDICT_CLEAR:
        return status == "kept"
    if verdict == VERDICT_WRONG:
        return status == "dropped"
    return False


def lift_actions(action_type: str, scope: str | None) -> tuple[str, ...] | None:
    """Чем снять ровно то, что выдали. None — снять нельзя (кик)."""
    action = (action_type or "").strip().lower()
    span = (scope or "chat").strip().lower() or "chat"
    if span not in ("chat", "all", "full"):
        span = "chat"
    table = {
        ("ban", "chat"): ("unban",),
        ("ban", "all"): ("unbanall",),
        ("ban", "full"): ("unbanall", "bot_unban"),
        ("mute", "chat"): ("unmute",),
        ("mute", "all"): ("unmuteall",),
        ("mute", "full"): ("unmuteall",),
        ("warn", "chat"): ("unwarn_chat",),
        ("warn", "all"): ("unwarn_all",),
        ("warn", "full"): ("unwarn_all",),
    }
    if action == "kick":
        return None
    return table.get((action, span))


def can_apply_lift(
    action_type: str,
    scope: str | None,
    chat_id: int | None,
    target_id: int | None,
) -> tuple[bool, str]:
    if not target_id:
        return False, "В архиве нет игрока, снять наказание некого."
    actions = lift_actions(action_type, scope)
    if not actions:
        if (action_type or "").strip().lower() == "kick":
            return False, "Кик уже выполнен: вернуть человека в группу нельзя."
        return False, "Такое наказание снять нельзя."
    span = (scope or "chat").strip().lower() or "chat"
    needs_chat = span == "chat" and any(
        name in actions for name in ("unban", "unmute", "unwarn_chat")
    )
    if needs_chat and not chat_id:
        return False, "В архиве не записана группа, поэтому снять наказание в ней нельзя."
    return True, ""


def verdict_of_sql(action_id_sql: str) -> str:
    """Ответ администратора группы для архива. Один на карточку."""
    return (
        f"(SELECT ds.verdict FROM epsilon_deed_sorts ds "
        f"WHERE ds.action_id = {action_id_sql})"
    )


def _blocked_ids_sql() -> str:
    from config import PLAIN_USER_IDS, owner_user_ids, public_creator_id

    ids = {int(item) for item in owner_user_ids()}
    ids.add(int(public_creator_id()))
    ids.update(int(item) for item in PLAIN_USER_IDS)
    if not ids:
        ids.add(0)
    return ", ".join(str(item) for item in sorted(ids))


def _role_list_sql() -> str:
    return ", ".join(f"'{role}'" for role in STAFF_ROLES)


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
    """Есть другой администратор архива, который может взять эту карточку."""
    blocked = _blocked_ids_sql()
    return f"""
      EXISTS (
        SELECT 1
        FROM epsilon_seats o
        JOIN epsilon_positions p ON p.id = o.position_id
        WHERE o.user_id <> COALESCE({action}.admin_user_id, 0)
          AND o.user_id NOT IN ({blocked})
          AND {_live_archive_seat("o", "p")}
          AND (
            (COALESCE({action}.chat_id, 0) <> 0 AND o.chat_id = {action}.chat_id)
            OR COALESCE({action}.chat_id, 0) = 0
          )
      )
    """


def self_can_sort(action: str = "s", user_sql: str = "$2") -> str:
    """Этот человек проверяет чужое дело в своей группе."""
    blocked = _blocked_ids_sql()
    return f"""
      EXISTS (
        SELECT 1
        FROM epsilon_seats me
        JOIN epsilon_positions mp ON mp.id = me.position_id
        WHERE me.user_id = {user_sql}
          AND me.user_id <> COALESCE({action}.admin_user_id, 0)
          AND me.user_id NOT IN ({blocked})
          AND {_live_archive_seat("me", "mp")}
          AND (
            (COALESCE({action}.chat_id, 0) <> 0 AND me.chat_id = {action}.chat_id)
            OR COALESCE({action}.chat_id, 0) = 0
          )
      )
    """


def self_is_staff(user_sql: str = "$2") -> str:
    roles = _role_list_sql()
    blocked = _blocked_ids_sql()
    return f"""
      EXISTS (
        SELECT 1 FROM admin_accounts me
        WHERE me.user_id = {user_sql}
          AND me.user_id NOT IN ({blocked})
          AND me.status = 'active'
          AND me.role IN ({roles})
      )
    """


def staff_available_sql(action: str = "s") -> str:
    """Есть сотрудник, который ещё не проверял эту карточку.

    В запросе нужен ds: тот, кто уже ответил как администратор, второй раз
    не считается. Создатель и владелец на этом этапе не работают.
    """
    roles = _role_list_sql()
    blocked = _blocked_ids_sql()
    return f"""
      EXISTS (
        SELECT 1 FROM admin_accounts me
        WHERE me.status = 'active'
          AND me.role IN ({roles})
          AND me.user_id NOT IN ({blocked})
          AND me.user_id <> COALESCE({action}.admin_user_id, 0)
          AND me.user_id <> COALESCE(ds.sorter_id, 0)
      )
    """


def claim_free_sql(stage: str, user_sql: str, action: str = "s") -> str:
    """Карточку уже держит другой человек этого же этапа — не показываем."""
    if stage not in (STAGE_ADMIN, STAGE_STAFF):
        raise ValueError("unknown stage")
    return f"""
      NOT EXISTS (
        SELECT 1 FROM epsilon_deed_claims cl
        WHERE cl.action_id = {action}.id
          AND cl.stage = '{stage}'
          AND cl.user_id <> {user_sql}
          AND cl.until_at > NOW()
      )
    """


def admin_stage_done_sql(action: str = "s") -> str:
    return f"(ds.action_id IS NOT NULL OR NOT ({other_sorter_exists(action)}))"


def staff_stage_done_sql(action: str = "s") -> str:
    return f"(st.action_id IS NOT NULL OR NOT ({staff_available_sql(action)}))"


def creator_waiting_sql() -> str:
    return """(
      v.action_id IS NULL
      OR (COALESCE(st.lift_ask, FALSE) AND st.lift_status = 'pending')
    )"""


def creator_ready_sql(action: str = "s") -> str:
    """Создателю хватает ответа администратора или сотрудника.

    Ждать второй проверки не нужно. Если не ответил никто и проверять
    было некому — карточка тоже его. Заявка на разблокировку остаётся,
    даже если зарплата уже записана. В запросе нужны v, ds и st.
    """
    return f"""(
      {creator_waiting_sql()}
      AND (
        v.action_id IS NOT NULL
        OR ds.action_id IS NOT NULL
        OR st.action_id IS NOT NULL
        OR (
          NOT ({other_sorter_exists(action)})
          AND NOT ({staff_available_sql(action)})
        )
      )
    )"""


def creator_open_sql(action: str = "s", user_sql: str = "$2") -> str:
    """Ещё никто не ответил, и администратор или сотрудник ещё могут взять карточку.

    Пока создатель её держит, колоды других её не показывают.
    """
    return f"""(
      v.action_id IS NULL
      AND ds.action_id IS NULL
      AND st.action_id IS NULL
      AND (
        {other_sorter_exists(action)}
        OR {staff_available_sql(action)}
      )
      AND {claim_free_sql(STAGE_ADMIN, user_sql, action)}
      AND {claim_free_sql(STAGE_STAFF, user_sql, action)}
    )"""


def _marks_sql() -> str:
    return """
    marks AS (
      SELECT action_id, sorter_id AS user_id, verdict, sorted_at AS at
      FROM epsilon_deed_sorts
      UNION ALL
      SELECT action_id, staff_id AS user_id, verdict, checked_at AS at
      FROM epsilon_deed_staff
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
    """Кто проверяет чужие наказания, и сколько каждый уже ответил.

    Живой кабинет с правом архива и живой сотрудник проекта остаются в списке
    даже с нулём. Кто отвечал раньше и место потерял, тоже остаётся.
    """
    blocked = _blocked_ids_sql()
    roles = _role_list_sql()
    live = _live_archive_seat("o", "p")
    return f"""
    WITH live_admin AS (
      SELECT o.user_id, MAX(p.title) AS title
      FROM epsilon_seats o
      JOIN epsilon_positions p ON p.id = o.position_id
      WHERE o.user_id NOT IN ({blocked})
        AND {live}
      GROUP BY o.user_id
    ),
    live_staff AS (
      SELECT a.user_id,
             CASE a.role
               WHEN 'senior_admin' THEN 'Старший администратор'
               WHEN 'junior_admin' THEN 'Младший администратор'
               WHEN 'moderator' THEN 'Модератор'
               ELSE ''
             END AS title
      FROM admin_accounts a
      WHERE a.status = 'active'
        AND a.role IN ({roles})
        AND a.user_id NOT IN ({blocked})
    ),
    {_marks_sql()},
    stats AS (
      SELECT
        m.user_id AS sorter_id,
        COUNT(*)::int AS reviewed,
        COUNT(*) FILTER (WHERE m.verdict = 'clear')::int AS clear_n,
        COUNT(*) FILTER (WHERE m.verdict = 'wrong')::int AS wrong_n,
        COUNT(*) FILTER (WHERE m.verdict = 'weak')::int AS weak_n,
        COUNT(*) FILTER (WHERE dr.status = 'kept')::int AS kept_n,
        COUNT(*) FILTER (WHERE dr.status = 'dropped')::int AS dropped_n,
        COUNT(*) FILTER (WHERE dr.action_id IS NULL)::int AS open_n,
        MAX(m.at) AS last_at
      {_marks_from_sql()}
      GROUP BY m.user_id
    )
    SELECT
      people.user_id AS id,
      COALESCE(NULLIF(btrim(u.first_name), ''), NULLIF(btrim(u.username), ''), '') AS name,
      COALESCE(u.username, '') AS username,
      COALESCE(NULLIF(live_admin.title, ''), live_staff.title, '') AS title,
      COALESCE(stats.reviewed, 0) AS reviewed,
      COALESCE(stats.clear_n, 0) AS clear_n,
      COALESCE(stats.wrong_n, 0) AS wrong_n,
      COALESCE(stats.weak_n, 0) AS weak_n,
      COALESCE(stats.kept_n, 0) AS kept_n,
      COALESCE(stats.dropped_n, 0) AS dropped_n,
      COALESCE(stats.open_n, 0) AS open_n,
      stats.last_at
    FROM (
      SELECT user_id FROM live_admin
      UNION
      SELECT user_id FROM live_staff
      UNION
      SELECT sorter_id AS user_id FROM stats
    ) people
    LEFT JOIN live_admin ON live_admin.user_id = people.user_id
    LEFT JOIN live_staff ON live_staff.user_id = people.user_id
    LEFT JOIN stats ON stats.sorter_id = people.user_id
    LEFT JOIN users u ON u.user_id = people.user_id
    WHERE people.user_id IS NOT NULL
      AND people.user_id <> 0
      AND people.user_id NOT IN ({blocked})
    ORDER BY COALESCE(stats.reviewed, 0) DESC, stats.last_at DESC NULLS LAST, people.user_id ASC
    """


def reviewer_totals_sql() -> str:
    """Итог по карточкам: одно наказание считается один раз."""
    blocked = _blocked_ids_sql()
    return f"""
    WITH {_marks_sql().strip()}
    SELECT
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.status = 'kept')::int AS kept_n,
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.status = 'dropped')::int AS dropped_n,
      COUNT(DISTINCT m.action_id) FILTER (WHERE dr.action_id IS NULL)::int AS open_n
    {_marks_from_sql()}
      AND m.user_id NOT IN ({blocked})
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
            await conn.execute(FOLD_UNCLEAR_SQL)
            await conn.execute(CREATE_STAFF_SQL)
            await conn.execute(CREATE_CLAIMS_SQL)
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS epsilon_deed_sorts_sorter_idx
                    ON epsilon_deed_sorts (sorter_id, sorted_at DESC)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS epsilon_deed_staff_staff_idx
                    ON epsilon_deed_staff (staff_id, checked_at DESC)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS epsilon_deed_claims_until_idx
                    ON epsilon_deed_claims (stage, until_at)
                """
            )
    _READY = True
