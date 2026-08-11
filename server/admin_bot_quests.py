"""Owner-only: задания подписки (+задание) и челленджи (+заданиеч) для Telegram-бота."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from db import db

_USERNAME_RE = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", re.IGNORECASE)
_schema_ready = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value).replace(",", ".").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError("Некорректная награда") from e


def _as_positive_int(value, *, field: str) -> int:
    try:
        n = int(str(value).replace(" ", "").replace(",", ".").split(".", 1)[0])
    except (TypeError, ValueError) as e:
        raise ValueError(f"Некорректное значение: {field}") from e
    if n <= 0:
        raise ValueError(f"{field} должно быть > 0")
    return n


def normalize_chat_ref(raw: Optional[str]) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = _USERNAME_RE.search(raw)
    if m:
        return f"@{m.group(1)}"
    if raw.startswith("@"):
        return raw
    if raw.replace("-", "").isdigit():
        return raw
    return f"@{raw.lstrip('@')}"


async def ensure_bot_quest_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_tasks (
              id              BIGSERIAL PRIMARY KEY,
              chat_ref        TEXT NOT NULL,
              reward          NUMERIC(18,2) NOT NULL,
              active          BOOLEAN NOT NULL DEFAULT TRUE,
              total_cap       INTEGER,
              ttl_expires_at  TIMESTAMPTZ,
              starts_at       TIMESTAMPTZ,
              created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_quest_tasks_chat_ref ON quest_tasks (chat_ref);
            ALTER TABLE quest_tasks ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ;
            CREATE INDEX IF NOT EXISTS ix_quest_tasks_starts_at ON quest_tasks (starts_at);

            CREATE TABLE IF NOT EXISTS quest_done (
              id          BIGSERIAL PRIMARY KEY,
              user_id     BIGINT NOT NULL,
              chat_ref    TEXT   NOT NULL,
              action      TEXT   NOT NULL,
              reward      NUMERIC(18,2) NOT NULL DEFAULT 0,
              created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            -- Старые БД: таблица могла быть без id / created_at
            ALTER TABLE quest_done ADD COLUMN IF NOT EXISTS id BIGINT;
            ALTER TABLE quest_done ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
            CREATE SEQUENCE IF NOT EXISTS quest_done_id_seq;
            ALTER TABLE quest_done ALTER COLUMN id SET DEFAULT nextval('quest_done_id_seq');
            UPDATE quest_done SET id = nextval('quest_done_id_seq') WHERE id IS NULL;
            SELECT setval(
              'quest_done_id_seq',
              GREATEST(1, COALESCE((SELECT MAX(id) FROM quest_done), 1))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_quest_done_user_chat ON quest_done (user_id, chat_ref);
            CREATE INDEX IF NOT EXISTS ix_quest_done_action_created
              ON quest_done (action, created_at DESC NULLS LAST);

            CREATE TABLE IF NOT EXISTS z_game_challenge_templates (
                id BIGSERIAL PRIMARY KEY,
                start_amount BIGINT NOT NULL,
                target_amount BIGINT NOT NULL,
                reward_amount BIGINT NOT NULL,
                betlimit BIGINT,
                max_users BIGINT,
                completed_users BIGINT NOT NULL DEFAULT 0 CHECK (completed_users >= 0),
                target_chat_id BIGINT,
                target_chat_ref TEXT,
                free TEXT,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
                starts_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            ALTER TABLE z_game_challenge_templates ADD COLUMN IF NOT EXISTS free TEXT;
            ALTER TABLE z_game_challenge_templates ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ;
            CREATE INDEX IF NOT EXISTS ix_gc_templates_starts_at ON z_game_challenge_templates (starts_at);
            """
        )
    _schema_ready = True


async def _resolve_gc_chat(raw_ref: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    raw = (raw_ref or "").strip()
    if not raw:
        return None, None
    digits = raw.replace(" ", "")
    if digits.replace("-", "").isdigit():
        try:
            return int(digits), raw
        except ValueError:
            return None, raw

    m = _USERNAME_RE.search(raw)
    token = m.group(1) if m else (raw[1:] if raw.startswith("@") else raw)
    token_l = token.lower()
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT chat_id, usernamechat FROM chat WHERE LOWER(usernamechat) = LOWER($1) LIMIT 1",
            token_l,
        )
        if row:
            uname = row["usernamechat"]
            return int(row["chat_id"]), f"@{uname}" if uname else raw
        row = await conn.fetchrow(
            """
            SELECT chat_id, usernamechat, chatlink FROM chat
             WHERE LOWER(chatlink) = LOWER($1)
                OR LOWER(chatlink) LIKE '%' || LOWER($2) || '%'
             LIMIT 1
            """,
            raw,
            token_l,
        )
        if row:
            uname = row["usernamechat"]
            return int(row["chat_id"]), (f"@{uname}" if uname else (row["chatlink"] or raw))
    return None, normalize_chat_ref(raw) or raw


def _task_effective(row: dict, subs: int, now: datetime) -> dict[str, Any]:
    ttl = row.get("ttl_expires_at")
    cap = row.get("total_cap")
    starts = row.get("starts_at")
    ttl_ok = ttl is None or ttl > now
    cap_ok = cap is None or subs < int(cap)
    started = starts is None or starts <= now
    scheduled = bool(starts and starts > now)
    active_flag = bool(row.get("active"))
    live = active_flag and ttl_ok and cap_ok and started
    return {
        "effectiveActive": live,
        "scheduled": scheduled,
        "started": started,
        "ttlOk": ttl_ok,
        "capOk": cap_ok,
    }


async def _stats_for_task(conn, chat_ref: str) -> dict[str, Any]:
    clicks = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT qc.user_id)::int
          FROM quest_clicks qc
          JOIN quest_tasks qt ON qt.id = qc.task_id
         WHERE qt.chat_ref = $1
        """,
        chat_ref,
    )
    sub_row = await conn.fetchrow(
        """
        SELECT COUNT(*)::int AS subs, COALESCE(SUM(reward), 0) AS reward_total
          FROM quest_done
         WHERE chat_ref = $1 AND action = 'sub'
        """,
        chat_ref,
    )
    skips = await conn.fetchval(
        "SELECT COUNT(*)::int FROM quest_done WHERE chat_ref = $1 AND action = 'skip'",
        chat_ref,
    )
    return {
        "clicks": int(clicks or 0),
        "subs": int(sub_row["subs"] if sub_row else 0),
        "skips": int(skips or 0),
        "rewardTotal": str(sub_row["reward_total"] if sub_row else 0),
    }


def _task_to_dict(row: dict, stats: dict, now: datetime) -> dict[str, Any]:
    eff = _task_effective(row, stats["subs"], now)
    return {
        "id": int(row["id"]),
        "chatRef": row["chat_ref"],
        "reward": str(row["reward"]),
        "active": bool(row["active"]),
        "totalCap": row["total_cap"],
        "ttlExpiresAt": _iso(row.get("ttl_expires_at")),
        "startsAt": _iso(row.get("starts_at")),
        "createdAt": _iso(row.get("created_at")),
        "updatedAt": _iso(row.get("updated_at")),
        "stats": stats,
        **eff,
    }


def _gc_to_dict(row: dict, now: datetime) -> dict[str, Any]:
    starts = row.get("starts_at")
    scheduled = bool(starts and starts > now)
    started = starts is None or starts <= now
    status = row.get("status") or "active"
    max_users = row.get("max_users")
    taken = int(row.get("completed_users") or 0)
    slots_ok = max_users is None or taken < int(max_users)
    live = status == "active" and started and slots_ok
    free = (row.get("free") or "-").strip()
    return {
        "id": int(row["id"]),
        "startAmount": int(row["start_amount"]),
        "targetAmount": int(row["target_amount"]),
        "rewardAmount": int(row["reward_amount"]),
        "betLimit": int(row["betlimit"]) if row.get("betlimit") is not None else None,
        "maxUsers": int(max_users) if max_users is not None else None,
        "completedUsers": taken,
        "targetChatId": int(row["target_chat_id"]) if row.get("target_chat_id") is not None else None,
        "targetChatRef": row.get("target_chat_ref"),
        "free": "+" if free == "+" else "-",
        "status": status,
        "startsAt": _iso(starts),
        "createdAt": _iso(row.get("created_at")),
        "scheduled": scheduled,
        "started": started,
        "slotsOk": slots_ok,
        "effectiveActive": live,
    }


_GC_REWARD_CAUSES = (
    "+ награда за задание",
    "+ награда за бесплатное задание",
)


def _gc_cause_match_sql(alias: str = "") -> str:
    col = f'{alias}."cause"' if alias else "cause"
    return f"({col} = ANY($1::text[]) OR {col} ILIKE '%награда%задани%')"


async def _table_exists(conn, name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = $1
            )
            """,
            name,
        )
    )


async def _sum_gc_rewards_paid(conn) -> Decimal:
    """Сумма выданных кут за челленджи: берём максимум из источников (без двойного сложения)."""
    hist = Decimal("0")
    log_sum = Decimal("0")
    try:
        val = await conn.fetchval(
            f"""
            SELECT COALESCE(SUM("+"), 0)
              FROM cutehistory
             WHERE {_gc_cause_match_sql()}
            """,
            list(_GC_REWARD_CAUSES),
        )
        hist = Decimal(str(val or 0))
    except Exception:
        hist = Decimal("0")
    try:
        if await _table_exists(conn, "user_balance_log"):
            val = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                  FROM user_balance_log
                 WHERE note = 'gc_task_reward'
                """
            )
            log_sum = Decimal(str(val or 0))
    except Exception:
        log_sum = Decimal("0")
    return hist if hist >= log_sum else log_sum


async def _count_gc_rewards_paid(conn) -> int:
    hist_n = 0
    log_n = 0
    try:
        hist_n = int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*)::int FROM cutehistory
                 WHERE {_gc_cause_match_sql()}
                """,
                list(_GC_REWARD_CAUSES),
            )
            or 0
        )
    except Exception:
        hist_n = 0
    try:
        if await _table_exists(conn, "user_balance_log"):
            log_n = int(
                await conn.fetchval(
                    "SELECT COUNT(*)::int FROM user_balance_log WHERE note = 'gc_task_reward'"
                )
                or 0
            )
    except Exception:
        log_n = 0
    return max(hist_n, log_n)


async def get_overview() -> dict[str, Any]:
    await ensure_bot_quest_schema()
    now = _utcnow()
    async with db.pool.acquire() as conn:
        sub_rows = await conn.fetch(
            "SELECT id, active, total_cap, ttl_expires_at, starts_at FROM quest_tasks"
        )
        gc_rows = await conn.fetch(
            "SELECT id, status, max_users, completed_users, starts_at FROM z_game_challenge_templates"
        )
        sub_payout = await conn.fetchval(
            "SELECT COALESCE(SUM(reward), 0) FROM quest_done WHERE action = 'sub'"
        )
        gc_payout = await _sum_gc_rewards_paid(conn)
        sub_count = await conn.fetchval(
            "SELECT COUNT(*)::int FROM quest_done WHERE action = 'sub'"
        )
        gc_count = await _count_gc_rewards_paid(conn)

    sub_active = sub_scheduled = 0
    for r in sub_rows:
        starts = r["starts_at"]
        ttl = r["ttl_expires_at"]
        if starts and starts > now:
            sub_scheduled += 1
        elif (
            r["active"]
            and (ttl is None or ttl > now)
            and (starts is None or starts <= now)
        ):
            sub_active += 1

    gc_active = gc_scheduled = gc_disabled = 0
    for r in gc_rows:
        if r["status"] == "disabled":
            gc_disabled += 1
            continue
        starts = r["starts_at"]
        if starts and starts > now:
            gc_scheduled += 1
        else:
            max_u = r["max_users"]
            taken = int(r["completed_users"] or 0)
            if max_u is None or taken < int(max_u):
                gc_active += 1

    sub_total = Decimal(str(sub_payout or 0))
    gc_total = Decimal(str(gc_payout or 0))
    return {
        "subTasks": {
            "total": len(sub_rows),
            "active": sub_active,
            "scheduled": sub_scheduled,
        },
        "challenges": {
            "total": len(gc_rows),
            "active": gc_active,
            "scheduled": gc_scheduled,
            "disabled": gc_disabled,
        },
        "subRewardPaidTotal": str(sub_total),
        "gcRewardPaidTotal": str(gc_total),
        "rewardPaidTotal": str(sub_total + gc_total),
        "subPayoutCount": int(sub_count or 0),
        "gcPayoutCount": int(gc_count or 0),
        "now": _iso(now),
    }


def _parse_cutehistory_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%H:%M %d.%m.%Y", "%H:%M:%S %d.%m.%Y", "%d.%m.%Y %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _dedupe_gc_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Если есть и log, и cutehistory — не дублируем одну выплату."""
    preferred = sorted(
        items,
        key=lambda it: (
            0 if str(it.get("id", "")).startswith("gc-log-") else 1,
            it.get("createdAt") or "",
        ),
    )
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for it in preferred:
        day = (it.get("createdAt") or it.get("createdAtLabel") or "")[:16]
        key = (int(it.get("userId") or 0), str(it.get("reward") or "0"), day)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


async def list_quest_payouts(
    *,
    kind: str = "all",
    query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Единая лента: кто / когда / сколько получил с подписок и челленджей."""
    await ensure_bot_quest_schema()
    kind_n = (kind or "all").strip().lower()
    if kind_n not in ("all", "sub", "gc"):
        kind_n = "all"
    q = (query or "").strip()
    q_like = f"%{q.lstrip('@')}%" if q else None
    q_id = int(q.lstrip("@")) if q and q.lstrip("@").isdigit() else None
    try:
        limit_i = max(1, min(200, int(limit)))
    except Exception:
        limit_i = 50
    try:
        offset_i = max(0, int(offset))
    except Exception:
        offset_i = 0

    items: list[dict[str, Any]] = []
    async with db.pool.acquire() as conn:
        has_qd_id = await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='quest_done' AND column_name='id'
            )
            """
        )

        if kind_n in ("all", "sub"):
            id_expr = "qd.id::text" if has_qd_id else "qd.ctid::text"
            if q_like is not None:
                sub_rows = await conn.fetch(
                    f"""
                    SELECT {id_expr} AS rid, qd.user_id, qd.chat_ref, qd.reward, qd.created_at,
                           COALESCE(u.username, '') AS username,
                           COALESCE(u.first_name, '') AS first_name
                      FROM quest_done qd
                      LEFT JOIN users u ON u.user_id = qd.user_id
                     WHERE qd.action = 'sub'
                       AND (
                         qd.chat_ref ILIKE $1
                         OR COALESCE(u.username, '') ILIKE $1
                         OR COALESCE(u.first_name, '') ILIKE $1
                         OR ($2::bigint IS NOT NULL AND qd.user_id = $2)
                       )
                     ORDER BY qd.created_at DESC NULLS LAST
                     LIMIT 2000
                    """,
                    q_like,
                    q_id,
                )
            else:
                sub_rows = await conn.fetch(
                    f"""
                    SELECT {id_expr} AS rid, qd.user_id, qd.chat_ref, qd.reward, qd.created_at,
                           COALESCE(u.username, '') AS username,
                           COALESCE(u.first_name, '') AS first_name
                      FROM quest_done qd
                      LEFT JOIN users u ON u.user_id = qd.user_id
                     WHERE qd.action = 'sub'
                     ORDER BY qd.created_at DESC NULLS LAST
                     LIMIT 2000
                    """
                )
            for r in sub_rows:
                created = _aware(r["created_at"])
                items.append({
                    "id": f"sub-{r['rid']}",
                    "kind": "sub",
                    "userId": int(r["user_id"]),
                    "username": r["username"] or None,
                    "firstName": r["first_name"] or None,
                    "reward": str(r["reward"] or 0),
                    "title": r["chat_ref"],
                    "detail": f"Подписка · {r['chat_ref']}",
                    "createdAt": _iso(created),
                    "createdAtLabel": None,
                    "wallet": "quebalance",
                    "sortTs": created.timestamp() if created else 0,
                })

        if kind_n in ("all", "gc"):
            gc_items: list[dict[str, Any]] = []

            # 1) user_balance_log — точные timestamps
            try:
                if await _table_exists(conn, "user_balance_log"):
                    if q_like is not None:
                        log_rows = await conn.fetch(
                            """
                            SELECT l.id, l.user_id, l.amount, l.created_at,
                                   COALESCE(u.username, '') AS username,
                                   COALESCE(u.first_name, '') AS first_name
                              FROM user_balance_log l
                              LEFT JOIN users u ON u.user_id = l.user_id
                             WHERE l.note = 'gc_task_reward'
                               AND (
                                 COALESCE(u.username, '') ILIKE $1
                                 OR COALESCE(u.first_name, '') ILIKE $1
                                 OR ($2::bigint IS NOT NULL AND l.user_id = $2)
                               )
                             ORDER BY l.created_at DESC
                             LIMIT 2000
                            """,
                            q_like,
                            q_id,
                        )
                    else:
                        log_rows = await conn.fetch(
                            """
                            SELECT l.id, l.user_id, l.amount, l.created_at,
                                   COALESCE(u.username, '') AS username,
                                   COALESCE(u.first_name, '') AS first_name
                              FROM user_balance_log l
                              LEFT JOIN users u ON u.user_id = l.user_id
                             WHERE l.note = 'gc_task_reward'
                             ORDER BY l.created_at DESC
                             LIMIT 2000
                            """
                        )
                    for r in log_rows:
                        created = _aware(r["created_at"])
                        gc_items.append({
                            "id": f"gc-log-{r['id']}",
                            "kind": "gc",
                            "userId": int(r["user_id"]),
                            "username": r["username"] or None,
                            "firstName": r["first_name"] or None,
                            "reward": str(r["amount"] or 0),
                            "title": "Челлендж",
                            "detail": "Награда за челлендж → основной баланс",
                            "createdAt": _iso(created),
                            "createdAtLabel": None,
                            "wallet": "balance",
                            "free": None,
                            "sortTs": created.timestamp() if created else 0,
                        })
            except Exception:
                pass

            # 2) cutehistory — полный журнал наград за задания
            try:
                if q_like is not None:
                    hist_rows = await conn.fetch(
                        f"""
                        SELECT c.ctid::text AS rid, c.user_id, c.username, c.first_name,
                               c."+" AS reward, c.cause, c.data,
                               COALESCE(u.username, c.username, '') AS u_username,
                               COALESCE(u.first_name, c.first_name, '') AS u_first_name
                          FROM cutehistory c
                          LEFT JOIN users u ON u.user_id = c.user_id
                         WHERE {_gc_cause_match_sql('c')}
                           AND (
                             COALESCE(c.username, '') ILIKE $2
                             OR COALESCE(c.first_name, '') ILIKE $2
                             OR COALESCE(u.username, '') ILIKE $2
                             OR COALESCE(u.first_name, '') ILIKE $2
                             OR c.cause ILIKE $2
                             OR ($3::bigint IS NOT NULL AND c.user_id = $3)
                           )
                         ORDER BY COALESCE(
                           to_timestamp(c.data, 'HH24:MI DD.MM.YYYY'),
                           '1970-01-01'::timestamptz
                         ) DESC
                         LIMIT 2000
                        """,
                        list(_GC_REWARD_CAUSES),
                        q_like,
                        q_id,
                    )
                else:
                    hist_rows = await conn.fetch(
                        f"""
                        SELECT c.ctid::text AS rid, c.user_id, c.username, c.first_name,
                               c."+" AS reward, c.cause, c.data,
                               COALESCE(u.username, c.username, '') AS u_username,
                               COALESCE(u.first_name, c.first_name, '') AS u_first_name
                          FROM cutehistory c
                          LEFT JOIN users u ON u.user_id = c.user_id
                         WHERE {_gc_cause_match_sql('c')}
                         ORDER BY COALESCE(
                           to_timestamp(c.data, 'HH24:MI DD.MM.YYYY'),
                           '1970-01-01'::timestamptz
                         ) DESC
                         LIMIT 2000
                        """,
                        list(_GC_REWARD_CAUSES),
                    )
            except Exception:
                hist_rows = []

            for r in hist_rows:
                cause = (r["cause"] or "").strip()
                is_free = "бесплатн" in cause.lower()
                parsed = _parse_cutehistory_dt(r["data"])
                uname = (r["u_username"] or r["username"] or "").strip() or None
                fname = (r["u_first_name"] or r["first_name"] or "").strip() or None
                gc_items.append({
                    "id": f"gc-hist-{r['rid']}",
                    "kind": "gc",
                    "userId": int(r["user_id"]) if r["user_id"] is not None else 0,
                    "username": uname,
                    "firstName": fname,
                    "reward": str(r["reward"] or 0),
                    "title": "Бесплатный челлендж" if is_free else "Обычный челлендж",
                    "detail": (cause[1:].strip() if cause.startswith("+") else cause) or "Награда за челлендж",
                    "createdAt": _iso(parsed) if parsed else None,
                    "createdAtLabel": r["data"],
                    "free": "+" if is_free else "-",
                    "wallet": "balance",
                    "sortTs": parsed.timestamp() if parsed else 0,
                })

            items.extend(_dedupe_gc_items(gc_items))

    items.sort(key=lambda it: (it.get("sortTs") or 0, it.get("createdAt") or ""), reverse=True)
    for it in items:
        it.pop("sortTs", None)

    total = len(items)
    page = items[offset_i: offset_i + limit_i]

    page_sum = Decimal("0")
    for it in page:
        try:
            page_sum += Decimal(str(it.get("reward") or 0))
        except Exception:
            pass
    all_sum = Decimal("0")
    for it in items:
        try:
            all_sum += Decimal(str(it.get("reward") or 0))
        except Exception:
            pass

    return {
        "items": page,
        "total": total,
        "limit": limit_i,
        "offset": offset_i,
        "hasMore": offset_i + limit_i < total,
        "filteredSum": str(all_sum),
        "pageSum": str(page_sum),
    }


# ─── Subscription tasks ─────────────────────────────────────────────────────


async def list_sub_tasks() -> list[dict]:
    await ensure_bot_quest_schema()
    now = _utcnow()
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, chat_ref, reward, active, total_cap, ttl_expires_at,
                   starts_at, created_at, updated_at
              FROM quest_tasks
             ORDER BY id DESC
            """
        )
        out = []
        for row in rows:
            d = dict(row)
            stats = await _stats_for_task(conn, d["chat_ref"])
            out.append(_task_to_dict(d, stats, now))
        return out


def _parse_limit_mode(
    *,
    limitMode: Optional[str],
    totalCap: Any,
    ttlValue: Any,
    ttlUnit: Optional[str],
    ttlExpiresAt: Optional[datetime],
) -> tuple[Optional[int], Optional[datetime]]:
    mode = (limitMode or "unlimited").strip().lower()
    if mode in ("", "unlimited", "none"):
        return None, None
    if mode in ("cap", "people", "чел"):
        cap = int(totalCap or 0)
        if cap <= 0:
            raise ValueError("Лимит людей должен быть > 0")
        return cap, None
    if mode in ("ttl", "expires"):
        if ttlExpiresAt is not None:
            return None, ttlExpiresAt
        try:
            n = int(ttlValue or 0)
        except (TypeError, ValueError) as e:
            raise ValueError("TTL: укажите число") from e
        if n <= 0:
            raise ValueError("TTL должен быть > 0")
        unit = (ttlUnit or "h").strip().lower()
        delta = {
            "s": timedelta(seconds=n),
            "m": timedelta(minutes=n),
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
        }.get(unit)
        if not delta:
            raise ValueError("TTL unit: s/m/h/d")
        return None, _utcnow() + delta
    raise ValueError("limitMode: unlimited | cap | ttl")


async def upsert_sub_task(
    *,
    chat_ref: str,
    reward,
    limit_mode: str = "unlimited",
    total_cap=None,
    ttl_value=None,
    ttl_unit: str = "h",
    ttl_expires_at: Optional[datetime] = None,
    starts_at: Optional[datetime] = None,
    active: bool = True,
) -> dict:
    await ensure_bot_quest_schema()
    cref = normalize_chat_ref(chat_ref)
    if not cref:
        raise ValueError("Укажите канал/чат (@username, ссылку или id)")
    reward_d = _as_decimal(reward)
    if reward_d <= 0:
        raise ValueError("Награда должна быть > 0")
    cap, expires = _parse_limit_mode(
        limitMode=limit_mode,
        totalCap=total_cap,
        ttlValue=ttl_value,
        ttlUnit=ttl_unit,
        ttlExpiresAt=ttl_expires_at,
    )
    if starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if starts_at and expires and starts_at >= expires:
        raise ValueError("Время начала должно быть раньше окончания (TTL)")

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO quest_tasks (chat_ref, reward, active, total_cap, ttl_expires_at, starts_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            ON CONFLICT (chat_ref) DO UPDATE SET
              reward = EXCLUDED.reward,
              active = EXCLUDED.active,
              total_cap = EXCLUDED.total_cap,
              ttl_expires_at = EXCLUDED.ttl_expires_at,
              starts_at = EXCLUDED.starts_at,
              updated_at = now()
            RETURNING id, chat_ref, reward, active, total_cap, ttl_expires_at, starts_at, created_at, updated_at
            """,
            cref,
            reward_d,
            bool(active),
            cap,
            expires,
            starts_at,
        )
        stats = await _stats_for_task(conn, cref)
        return _task_to_dict(dict(row), stats, _utcnow())


async def bulk_upsert_sub_tasks(items: list[dict]) -> dict[str, Any]:
    created, errors = [], []
    for idx, item in enumerate(items or []):
        try:
            row = await upsert_sub_task(
                chat_ref=item.get("chatRef") or item.get("chat_ref") or "",
                reward=item.get("reward"),
                limit_mode=item.get("limitMode") or item.get("limit_mode") or "unlimited",
                total_cap=item.get("totalCap", item.get("total_cap")),
                ttl_value=item.get("ttlValue", item.get("ttl_value")),
                ttl_unit=item.get("ttlUnit") or item.get("ttl_unit") or "h",
                ttl_expires_at=item.get("ttlExpiresAt") or item.get("ttl_expires_at"),
                starts_at=item.get("startsAt") or item.get("starts_at"),
                active=item.get("active", True) is not False,
            )
            created.append(row)
        except Exception as e:
            errors.append({"index": idx, "error": str(e), "item": item})
    return {"created": created, "errors": errors, "ok": len(created), "failed": len(errors)}


async def patch_sub_task(task_id: int, patch: dict) -> dict:
    await ensure_bot_quest_schema()
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM quest_tasks WHERE id = $1", int(task_id))
        if not row:
            raise ValueError("Задание не найдено")
        d = dict(row)

        if "chatRef" in patch or "chat_ref" in patch:
            cref = normalize_chat_ref(patch.get("chatRef") or patch.get("chat_ref"))
            if not cref:
                raise ValueError("Пустой chat_ref")
            d["chat_ref"] = cref
        if "reward" in patch and patch["reward"] is not None:
            d["reward"] = _as_decimal(patch["reward"])
        if "active" in patch and patch["active"] is not None:
            d["active"] = bool(patch["active"])

        if any(k in patch for k in ("limitMode", "limit_mode", "totalCap", "total_cap", "ttlValue", "ttlUnit", "ttlExpiresAt")):
            cap, expires = _parse_limit_mode(
                limitMode=patch.get("limitMode") or patch.get("limit_mode") or (
                    "cap" if d.get("total_cap") else ("ttl" if d.get("ttl_expires_at") else "unlimited")
                ),
                totalCap=patch.get("totalCap", patch.get("total_cap", d.get("total_cap"))),
                ttlValue=patch.get("ttlValue", patch.get("ttl_value")),
                ttlUnit=patch.get("ttlUnit") or patch.get("ttl_unit") or "h",
                ttlExpiresAt=patch.get("ttlExpiresAt") or patch.get("ttl_expires_at"),
            )
            d["total_cap"] = cap
            d["ttl_expires_at"] = expires

        if "startsAt" in patch or "starts_at" in patch:
            starts = patch.get("startsAt", patch.get("starts_at"))
            if starts is None or starts == "":
                d["starts_at"] = None
            else:
                d["starts_at"] = starts
                if isinstance(starts, datetime) and starts.tzinfo is None:
                    d["starts_at"] = starts.replace(tzinfo=timezone.utc)

        if "activateNow" in patch and patch["activateNow"]:
            d["starts_at"] = None
            d["active"] = True

        updated = await conn.fetchrow(
            """
            UPDATE quest_tasks SET
              chat_ref = $2,
              reward = $3,
              active = $4,
              total_cap = $5,
              ttl_expires_at = $6,
              starts_at = $7,
              updated_at = now()
            WHERE id = $1
            RETURNING id, chat_ref, reward, active, total_cap, ttl_expires_at, starts_at, created_at, updated_at
            """,
            int(task_id),
            d["chat_ref"],
            d["reward"],
            bool(d["active"]),
            d.get("total_cap"),
            d.get("ttl_expires_at"),
            d.get("starts_at"),
        )
        stats = await _stats_for_task(conn, updated["chat_ref"])
        return _task_to_dict(dict(updated), stats, _utcnow())


async def delete_sub_task(task_id: int) -> dict:
    await ensure_bot_quest_schema()
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM quest_tasks WHERE id = $1 RETURNING id, chat_ref",
            int(task_id),
        )
        if not row:
            raise ValueError("Задание не найдено")
        return {"ok": True, "deletedId": int(row["id"]), "chatRef": row["chat_ref"]}


# ─── Game challenges ────────────────────────────────────────────────────────


async def list_challenges(*, include_disabled: bool = True) -> list[dict]:
    await ensure_bot_quest_schema()
    now = _utcnow()
    async with db.pool.acquire() as conn:
        if include_disabled:
            rows = await conn.fetch(
                """
                SELECT id, start_amount, target_amount, reward_amount, betlimit,
                       max_users, completed_users, target_chat_id, target_chat_ref,
                       free, status, starts_at, created_at
                  FROM z_game_challenge_templates
                 ORDER BY id DESC
                 LIMIT 300
                """
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, start_amount, target_amount, reward_amount, betlimit,
                       max_users, completed_users, target_chat_id, target_chat_ref,
                       free, status, starts_at, created_at
                  FROM z_game_challenge_templates
                 WHERE status <> 'disabled'
                 ORDER BY id DESC
                 LIMIT 300
                """
            )
    return [_gc_to_dict(dict(r), now) for r in rows]


async def create_challenge(
    *,
    start_amount,
    target_amount,
    reward_amount,
    max_bet=None,
    chat_ref: Optional[str] = None,
    max_users=None,
    free: str = "-",
    starts_at: Optional[datetime] = None,
) -> dict:
    await ensure_bot_quest_schema()
    start = _as_positive_int(start_amount, field="старт")
    target = _as_positive_int(target_amount, field="цель")
    reward = _as_positive_int(reward_amount, field="награда")
    if target <= start:
        raise ValueError("Цель должна быть больше старта")

    betlimit = None
    if max_bet is not None and str(max_bet).strip() != "":
        mb = int(max_bet)
        if mb > 0:
            betlimit = mb

    slots = None
    if max_users is not None and str(max_users).strip() != "":
        mu = int(max_users)
        if mu > 0:
            slots = mu

    # Тот же контракт, что create_gc_template_record в боте (+заданиеч)
    free_norm = "+" if str(free).strip() == "+" else "-"
    chat_ref_raw = (chat_ref or "").strip() or None
    chat_id, chat_canon = await _resolve_gc_chat(chat_ref_raw)
    dup_ref = chat_canon or chat_ref_raw

    if starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    async with db.pool.acquire() as conn:
        similar = await conn.fetchrow(
            """
            SELECT id FROM z_game_challenge_templates
             WHERE status = 'active'
               AND COALESCE(target_chat_ref, '') = COALESCE($1, '')
               AND start_amount = $2
               AND target_amount = $3
               AND COALESCE(free, '-') = $4
             LIMIT 1
            """,
            dup_ref,
            start,
            target,
            free_norm,
        )
        if similar:
            raise ValueError(f"Дубликат: уже есть челлендж #{similar['id']} с такими параметрами")

        # INSERT как у бота (+ starts_at из админки)
        row = await conn.fetchrow(
            """
            INSERT INTO z_game_challenge_templates
              (start_amount, target_amount, reward_amount, betlimit, max_users,
               completed_users, target_chat_id, target_chat_ref, free, status, starts_at, created_at)
            VALUES ($1,$2,$3,$4,$5,0,$6,$7,$8,'active',$9, NOW())
            RETURNING id, start_amount, target_amount, reward_amount, betlimit,
                      max_users, completed_users, target_chat_id, target_chat_ref,
                      free, status, starts_at, created_at
            """,
            start,
            target,
            reward,
            betlimit,
            slots,
            chat_id,
            dup_ref,
            free_norm,
            starts_at,
        )
        return _gc_to_dict(dict(row), _utcnow())


async def bulk_create_challenges(items: list[dict]) -> dict[str, Any]:
    created, errors = [], []
    for idx, item in enumerate(items or []):
        try:
            starts = item.get("startsAt") or item.get("starts_at")
            row = await create_challenge(
                start_amount=item.get("startAmount", item.get("start_amount")),
                target_amount=item.get("targetAmount", item.get("target_amount")),
                reward_amount=item.get("rewardAmount", item.get("reward_amount")),
                max_bet=item.get("maxBet", item.get("max_bet")),
                chat_ref=item.get("chatRef") or item.get("chat_ref"),
                max_users=item.get("maxUsers", item.get("max_users")),
                free=item.get("free") or "-",
                starts_at=starts,
            )
            created.append(row)
        except Exception as e:
            errors.append({"index": idx, "error": str(e), "item": item})
    return {"created": created, "errors": errors, "ok": len(created), "failed": len(errors)}


async def patch_challenge(template_id: int, patch: dict) -> dict:
    await ensure_bot_quest_schema()
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM z_game_challenge_templates WHERE id = $1", int(template_id)
        )
        if not row:
            raise ValueError("Челлендж не найден")
        d = dict(row)

        if "startAmount" in patch or "start_amount" in patch:
            d["start_amount"] = _as_positive_int(
                patch.get("startAmount", patch.get("start_amount")), field="старт"
            )
        if "targetAmount" in patch or "target_amount" in patch:
            d["target_amount"] = _as_positive_int(
                patch.get("targetAmount", patch.get("target_amount")), field="цель"
            )
        if "rewardAmount" in patch or "reward_amount" in patch:
            d["reward_amount"] = _as_positive_int(
                patch.get("rewardAmount", patch.get("reward_amount")), field="награда"
            )
        if d["target_amount"] <= d["start_amount"]:
            raise ValueError("Цель должна быть больше старта")

        if "maxBet" in patch or "max_bet" in patch or "betLimit" in patch:
            mb = patch.get("maxBet", patch.get("max_bet", patch.get("betLimit")))
            if mb is None or str(mb).strip() == "" or int(mb) <= 0:
                d["betlimit"] = None
            else:
                d["betlimit"] = int(mb)

        if "maxUsers" in patch or "max_users" in patch:
            mu = patch.get("maxUsers", patch.get("max_users"))
            if mu is None or str(mu).strip() == "" or int(mu) <= 0:
                d["max_users"] = None
            else:
                d["max_users"] = int(mu)

        if "chatRef" in patch or "chat_ref" in patch:
            chat_id, chat_canon = await _resolve_gc_chat(
                patch.get("chatRef") or patch.get("chat_ref")
            )
            d["target_chat_id"] = chat_id
            d["target_chat_ref"] = chat_canon

        if "free" in patch and patch["free"] is not None:
            d["free"] = "+" if str(patch["free"]).strip() == "+" else "-"

        if "status" in patch and patch["status"] in ("active", "disabled"):
            d["status"] = patch["status"]

        if "startsAt" in patch or "starts_at" in patch:
            starts = patch.get("startsAt", patch.get("starts_at"))
            if starts is None or starts == "":
                d["starts_at"] = None
            else:
                d["starts_at"] = starts
                if isinstance(starts, datetime) and starts.tzinfo is None:
                    d["starts_at"] = starts.replace(tzinfo=timezone.utc)

        if patch.get("activateNow"):
            d["starts_at"] = None
            d["status"] = "active"

        if patch.get("disable"):
            d["status"] = "disabled"

        updated = await conn.fetchrow(
            """
            UPDATE z_game_challenge_templates SET
              start_amount = $2,
              target_amount = $3,
              reward_amount = $4,
              betlimit = $5,
              max_users = $6,
              target_chat_id = $7,
              target_chat_ref = $8,
              free = $9,
              status = $10,
              starts_at = $11
            WHERE id = $1
            RETURNING id, start_amount, target_amount, reward_amount, betlimit,
                      max_users, completed_users, target_chat_id, target_chat_ref,
                      free, status, starts_at, created_at
            """,
            int(template_id),
            d["start_amount"],
            d["target_amount"],
            d["reward_amount"],
            d.get("betlimit"),
            d.get("max_users"),
            d.get("target_chat_id"),
            d.get("target_chat_ref"),
            d.get("free") or "-",
            d.get("status") or "active",
            d.get("starts_at"),
        )
        return _gc_to_dict(dict(updated), _utcnow())


async def disable_challenge(template_id: int) -> dict:
    return await patch_challenge(template_id, {"disable": True})


async def delete_challenge(template_id: int) -> dict:
    await ensure_bot_quest_schema()
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM z_game_challenge_templates WHERE id = $1 RETURNING id",
            int(template_id),
        )
        if not row:
            raise ValueError("Челлендж не найден")
        return {"ok": True, "deletedId": int(row["id"])}


# ─── Recommended pack (@CuteGamingChat) ──────────────────────────────────────
# 1 кут = 1 Stars → награды очень скромные (~2–3% от пути цель−старт).
# Пути длиннее: задание должно чувствоваться как работа, а не раздача.

DEFAULT_QUEST_CHAT = "@CuteGamingChat"

# Старые «жирные» варианты — выключаем при сиде, чтобы не висели в эфире.
LEGACY_CHALLENGE_SIGNATURES: list[dict[str, Any]] = [
    {"startAmount": 50, "targetAmount": 150, "free": "+"},
    {"startAmount": 100, "targetAmount": 300, "free": "+"},
    {"startAmount": 100, "targetAmount": 400, "free": "+"},
    {"startAmount": 20, "targetAmount": 80, "free": "-"},
    {"startAmount": 100, "targetAmount": 500, "free": "-"},
    {"startAmount": 200, "targetAmount": 800, "free": "-"},
    {"startAmount": 100, "targetAmount": 500, "free": "+"},
    {"startAmount": 500, "targetAmount": 2000, "free": "-"},
    {"startAmount": 1000, "targetAmount": 5000, "free": "-"},
    {"startAmount": 50, "targetAmount": 200, "free": "+"},
    {"startAmount": 30, "targetAmount": 100, "free": "+"},
    {"startAmount": 75, "targetAmount": 225, "free": "+"},
    {"startAmount": 40, "targetAmount": 140, "free": "-"},
    {"startAmount": 60, "targetAmount": 200, "free": "-"},
    {"startAmount": 120, "targetAmount": 400, "free": "+"},
    {"startAmount": 150, "targetAmount": 550, "free": "-"},
    {"startAmount": 250, "targetAmount": 900, "free": "-"},
    {"startAmount": 400, "targetAmount": 1500, "free": "-"},
    {"startAmount": 800, "targetAmount": 3500, "free": "-"},
    {"startAmount": 25, "targetAmount": 80, "free": "+"},
]

# Актуальный пакет: сложнее путь, награда ≈ 2–3% от (цель − старт)
RECOMMENDED_CHALLENGES: list[dict[str, Any]] = [
    # Нулевые / вход (бесплатные)
    {"startAmount": 30, "targetAmount": 150, "rewardAmount": 4, "maxUsers": 50, "free": "+", "label": "zero-micro"},
    {"startAmount": 50, "targetAmount": 250, "rewardAmount": 6, "maxUsers": 40, "free": "+", "label": "zero-a"},
    {"startAmount": 100, "targetAmount": 500, "rewardAmount": 12, "maxUsers": 25, "free": "+", "label": "zero-b"},
    # Мелкие платные
    {"startAmount": 25, "targetAmount": 120, "rewardAmount": 3, "maxBet": 12, "free": "-", "label": "small-paid-a"},
    {"startAmount": 50, "targetAmount": 250, "rewardAmount": 6, "maxBet": 25, "free": "-", "label": "small-paid-b"},
    {"startAmount": 80, "targetAmount": 400, "rewardAmount": 10, "maxBet": 40, "free": "-", "label": "small-paid-c"},
    # Средние
    {"startAmount": 100, "targetAmount": 600, "rewardAmount": 15, "maxBet": 50, "free": "-", "label": "mid-paid-a"},
    {"startAmount": 150, "targetAmount": 800, "rewardAmount": 20, "maxBet": 75, "free": "-", "label": "mid-paid-b"},
    {"startAmount": 200, "targetAmount": 1200, "rewardAmount": 30, "maxBet": 100, "free": "-", "label": "mid-paid-c"},
    {"startAmount": 300, "targetAmount": 1800, "rewardAmount": 40, "maxBet": 150, "free": "-", "label": "mid-paid-d"},
    # Средние бесплатные (разгрузка, но путь длинный)
    {"startAmount": 100, "targetAmount": 650, "rewardAmount": 14, "free": "+", "label": "mid-free-a"},
    {"startAmount": 120, "targetAmount": 750, "rewardAmount": 16, "free": "+", "label": "mid-free-b"},
    # Крупные
    {"startAmount": 400, "targetAmount": 2200, "rewardAmount": 50, "maxBet": 200, "maxUsers": 10, "free": "-", "label": "upper-mid"},
    {"startAmount": 500, "targetAmount": 3000, "rewardAmount": 60, "maxBet": 250, "maxUsers": 8, "free": "-", "label": "whale-a"},
    {"startAmount": 800, "targetAmount": 4500, "rewardAmount": 90, "maxBet": 350, "maxUsers": 6, "free": "-", "label": "whale-mid"},
    {"startAmount": 1000, "targetAmount": 5000, "rewardAmount": 100, "maxBet": 400, "maxUsers": 5, "free": "-", "label": "whale-b"},
    {"startAmount": 2000, "targetAmount": 10000, "rewardAmount": 180, "maxBet": 800, "maxUsers": 3, "free": "-", "label": "whale-hard"},
    # Спящие
    {"startAmount": 25, "targetAmount": 150, "rewardAmount": 4, "maxUsers": 40, "free": "+", "label": "sleep-micro"},
    {"startAmount": 40, "targetAmount": 220, "rewardAmount": 5, "maxUsers": 35, "free": "+", "label": "sleep"},
    {"startAmount": 60, "targetAmount": 350, "rewardAmount": 8, "free": "+", "label": "sleep-plus"},
]


def recommended_challenge_payloads() -> list[dict[str, Any]]:
    """Тела как у обычного POST /bot-quests/challenges (форма админки)."""
    out = []
    for item in RECOMMENDED_CHALLENGES:
        out.append({
            "startAmount": int(item["startAmount"]),
            "targetAmount": int(item["targetAmount"]),
            "rewardAmount": int(item["rewardAmount"]),
            "maxBet": item.get("maxBet"),
            "maxUsers": item.get("maxUsers"),
            "free": "+" if item.get("free") == "+" else "-",
            "chatRef": DEFAULT_QUEST_CHAT,
            "startsAt": None,
            "label": item.get("label"),
        })
    return out


async def _find_similar_challenge(
    *,
    chat_ref: Optional[str],
    start_amount: int,
    target_amount: int,
    free: str,
    include_disabled: bool = False,
) -> Optional[dict]:
    free_norm = "+" if str(free).strip() == "+" else "-"
    _chat_id, chat_canon = await _resolve_gc_chat(chat_ref)
    status_sql = "TRUE" if include_disabled else "status = 'active'"
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT id, start_amount, target_amount, reward_amount, betlimit,
                   max_users, completed_users, target_chat_id, target_chat_ref,
                   free, status, starts_at, created_at
              FROM z_game_challenge_templates
             WHERE {status_sql}
               AND COALESCE(target_chat_ref, '') = COALESCE($1, '')
               AND start_amount = $2
               AND target_amount = $3
               AND COALESCE(free, '-') = $4
             ORDER BY id DESC
             LIMIT 1
            """,
            chat_canon,
            int(start_amount),
            int(target_amount),
            free_norm,
        )
    return _gc_to_dict(dict(row), _utcnow()) if row else None


async def seed_recommended_pack() -> dict[str, Any]:
    """
    1) Выключает старые жирные челленджи пакета.
    2) Создаёт/синхронизирует новый скромный пакет через create_challenge.
    """
    await ensure_bot_quest_schema()

    disabled: list[dict] = []
    for sig in LEGACY_CHALLENGE_SIGNATURES:
        # Не трогаем сигнатуры, которые совпадают с новым пакетом
        keep = any(
            int(n["startAmount"]) == int(sig["startAmount"])
            and int(n["targetAmount"]) == int(sig["targetAmount"])
            and (("+" if n.get("free") == "+" else "-") == ("+" if sig.get("free") == "+" else "-"))
            for n in RECOMMENDED_CHALLENGES
        )
        if keep:
            continue
        existing = await _find_similar_challenge(
            chat_ref=DEFAULT_QUEST_CHAT,
            start_amount=sig["startAmount"],
            target_amount=sig["targetAmount"],
            free=sig["free"],
        )
        if not existing:
            continue
        try:
            row = await patch_challenge(int(existing["id"]), {"disable": True})
            disabled.append(row)
        except Exception:
            pass

    sub = await upsert_sub_task(
        chat_ref=DEFAULT_QUEST_CHAT,
        reward=1,
        limit_mode="unlimited",
        active=True,
        starts_at=None,
    )

    created: list[dict] = []
    updated: list[dict] = []
    errors: list[dict] = []

    for payload in recommended_challenge_payloads():
        label = payload.pop("label", None)
        try:
            row = await create_challenge(
                start_amount=payload["startAmount"],
                target_amount=payload["targetAmount"],
                reward_amount=payload["rewardAmount"],
                max_bet=payload.get("maxBet"),
                chat_ref=payload["chatRef"],
                max_users=payload.get("maxUsers"),
                free=payload["free"],
                starts_at=None,
            )
            created.append({**row, "label": label})
        except ValueError as e:
            msg = str(e)
            if "Дубликат" not in msg:
                errors.append({"label": label, "error": msg, **payload})
                continue
            existing = await _find_similar_challenge(
                chat_ref=payload["chatRef"],
                start_amount=payload["startAmount"],
                target_amount=payload["targetAmount"],
                free=payload["free"],
            )
            if not existing:
                errors.append({"label": label, "error": msg, **payload})
                continue
            try:
                synced = await patch_challenge(
                    int(existing["id"]),
                    {
                        "rewardAmount": payload["rewardAmount"],
                        "maxBet": payload.get("maxBet"),
                        "maxUsers": payload.get("maxUsers"),
                        "chatRef": DEFAULT_QUEST_CHAT,
                        "free": payload["free"],
                        "status": "active",
                        "startsAt": None,
                        "activateNow": True,
                    },
                )
                updated.append({**synced, "label": label})
            except Exception as patch_err:
                errors.append({"label": label, "error": str(patch_err), **payload})
        except Exception as e:
            errors.append({"label": label, "error": str(e), **payload})

    return {
        "chat": DEFAULT_QUEST_CHAT,
        "subTask": sub,
        "created": created,
        "updated": updated,
        "disabled": disabled,
        "errors": errors,
        "ok": len(created),
        "updatedCount": len(updated),
        "disabledCount": len(disabled),
        "failed": len(errors),
        "skippedCount": 0,
    }
