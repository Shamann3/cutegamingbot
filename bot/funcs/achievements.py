# -*- coding: utf-8 -*-
"""Система достижений профиля: официальные + свободные.

Хранение выдач: users.profile_achievements (JSONB).
Каталог официальных: таблица official_achievements.
"""

from __future__ import annotations

import html
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

SHOWCASE_LIMIT = 3
MAX_ITEMS_PER_USER = 200
MAX_TITLE_HTML_LEN = 500
MAX_DESCRIPTION_LEN = 400
JSONB_VERSION = 1

# Premium fallback / default icons
DEFAULT_ICON_EMOJI_ID = "5404534885324988233"
DEFAULT_ICON_FALLBACK = "⭐"
ACHIEVEMENTS_HEADER_EMOJI = "5318892863780579996"

ALLOWED_ENTITY_TYPES = frozenset({
    "bold", "italic", "underline", "strikethrough", "spoiler",
    "code", "pre", "custom_emoji",
})
DENIED_ENTITY_TYPES = frozenset({
    "url", "text_link", "text_mention", "blockquote", "expandable_blockquote",
    "mention", "hashtag", "cashtag", "bot_command", "email", "phone_number",
})

GBL_OFFICIAL_SEEDS: List[Dict[str, Any]] = [
    {
        "code": "gbl_level_1",
        "title": "Спонсор группы",
        "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
        "icon_fallback": "⭐",
        "description": "Открыл 1-й уровень баланса группы",
        "rarity": 1,
        "sort": 10,
    },
    {
        "code": "gbl_level_2",
        "title": "Меценат сообщества",
        "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
        "icon_fallback": "⭐",
        "description": "Открыл 2-й уровень баланса группы",
        "rarity": 2,
        "sort": 20,
    },
    {
        "code": "gbl_level_3",
        "title": "Архитектор баланса",
        "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
        "icon_fallback": "⭐",
        "description": "Открыл 3-й уровень баланса группы",
        "rarity": 3,
        "sort": 30,
    },
    {
        "code": "gbl_level_4",
        "title": "Покровитель круга",
        "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
        "icon_fallback": "⭐",
        "description": "Открыл 4-й уровень баланса группы",
        "rarity": 4,
        "sort": 40,
    },
    {
        "code": "gbl_level_5",
        "title": "Легенда баланса",
        "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
        "icon_fallback": "⭐",
        "description": "Открыл 5-й уровень баланса группы",
        "rarity": 5,
        "sort": 50,
    },
]


# ──────────────────────────────────────────────────────────────────────
# HTML / entities
# ──────────────────────────────────────────────────────────────────────

def _entity_type_name(ent: Any) -> str:
    t = getattr(ent, "type", None)
    if t is None:
        return ""
    if hasattr(t, "value"):
        return str(t.value).lower()
    return str(t).lower().replace("messageentitytype.", "")


def _wrap_entity(typ: str, inner: str, ent: Any) -> str:
    if typ == "bold":
        return f"<b>{inner}</b>"
    if typ == "italic":
        return f"<i>{inner}</i>"
    if typ == "underline":
        return f"<u>{inner}</u>"
    if typ == "strikethrough":
        return f"<s>{inner}</s>"
    if typ == "spoiler":
        return f"<tg-spoiler>{inner}</tg-spoiler>"
    if typ == "code":
        return f"<code>{inner}</code>"
    if typ == "pre":
        return f"<pre>{inner}</pre>"
    if typ == "custom_emoji":
        eid = getattr(ent, "custom_emoji_id", None) or ""
        if eid:
            return f"<tg-emoji emoji-id='{eid}'>{inner or DEFAULT_ICON_FALLBACK}</tg-emoji>"
        return inner
    return inner


def sanitize_achievement_html(
    text: str,
    entities: Optional[Sequence[Any]] = None,
    *,
    max_len: int = MAX_TITLE_HTML_LEN,
) -> Tuple[str, Optional[str], str]:
    """Текст + entities → sanitized HTML.

    Returns: (title_html, primary_custom_emoji_id, icon_fallback_char)
    Запрещены ссылки и blockquote; custom_emoji сохраняются с id.
    """
    raw = (text or "").strip()
    if not raw:
        return "", None, DEFAULT_ICON_FALLBACK

    ents = list(entities or [])
    # Оставляем только разрешённые; запрещённые превращаются в plain text
    usable = []
    primary_emoji_id: Optional[str] = None
    icon_fallback = DEFAULT_ICON_FALLBACK
    for ent in ents:
        typ = _entity_type_name(ent)
        if typ in DENIED_ENTITY_TYPES:
            continue
        if typ not in ALLOWED_ENTITY_TYPES:
            continue
        usable.append(ent)
        if typ == "custom_emoji" and primary_emoji_id is None:
            eid = getattr(ent, "custom_emoji_id", None)
            if eid:
                primary_emoji_id = str(eid)
                off = int(getattr(ent, "offset", 0) or 0)
                length = int(getattr(ent, "length", 0) or 0)
                # Telegram offsets are UTF-16 code units
                try:
                    icon_fallback = _utf16_slice(raw, off, length) or DEFAULT_ICON_FALLBACK
                except Exception:
                    icon_fallback = DEFAULT_ICON_FALLBACK

    if not usable:
        plain = html.escape(raw)[:max_len]
        return plain, primary_emoji_id, icon_fallback

    # Build with nested entity stacking (UTF-16 aware)
    u16 = raw.encode("utf-16-le")
    n_units = len(u16) // 2

    opens: Dict[int, List[Any]] = {}
    closes: Dict[int, List[Any]] = {}
    for ent in usable:
        off = max(0, int(getattr(ent, "offset", 0) or 0))
        length = max(0, int(getattr(ent, "length", 0) or 0))
        end = min(n_units, off + length)
        opens.setdefault(off, []).append(ent)
        closes.setdefault(end, []).append(ent)

    stack: List[Any] = []
    out: List[str] = []
    i = 0
    while i <= n_units:
        if i in closes:
            for ent in reversed(closes[i]):
                if stack and stack[-1] is ent:
                    stack.pop()
                    typ = _entity_type_name(ent)
                    # close tag already applied when we wrapped chunks — use marker approach instead
                    pass
        if i == n_units:
            break
        if i in opens:
            for ent in opens[i]:
                stack.append(ent)
        # emit one UTF-16 unit as char(s)
        ch = u16[i * 2:(i + 1) * 2].decode("utf-16-le")
        escaped = html.escape(ch)
        # wrap with current stack from outside-in each char is expensive;
        # better rebuild ranges. Fall through to simpler algorithm below.
        out.append(escaped)
        i += 1

    # Simpler reliable algorithm: apply non-overlapping / nested via recursive ranges
    title_html = _entities_to_html(raw, usable)
    if len(title_html) > max_len:
        title_html = title_html[:max_len]
    return title_html, primary_emoji_id, icon_fallback


def _utf16_slice(text: str, offset: int, length: int) -> str:
    encoded = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    return encoded[start:end].decode("utf-16-le")


def _entities_to_html(text: str, entities: List[Any]) -> str:
    """Convert text+entities to HTML with nesting support."""
    if not entities:
        return html.escape(text)

    encoded = text.encode("utf-16-le")
    n = len(encoded) // 2

    # events: (pos, kind, ent) kind: 0=close 1=open; close before open at same pos
    events: List[Tuple[int, int, Any]] = []
    for ent in entities:
        off = max(0, int(getattr(ent, "offset", 0) or 0))
        length = max(0, int(getattr(ent, "length", 0) or 0))
        end = min(n, off + length)
        if end <= off:
            continue
        events.append((off, 1, ent))
        events.append((end, 0, ent))
    events.sort(key=lambda x: (x[0], x[1], -int(getattr(x[2], "length", 0) or 0)))

    parts: List[str] = []
    cursor = 0
    stack: List[Any] = []

    def emit_plain(a: int, b: int) -> None:
        if b <= a:
            return
        chunk = encoded[a * 2:b * 2].decode("utf-16-le")
        parts.append(html.escape(chunk))

    for pos, kind, ent in events:
        if pos > cursor:
            emit_plain(cursor, pos)
            cursor = pos
        if kind == 1:
            stack.append(ent)
            typ = _entity_type_name(ent)
            if typ == "bold":
                parts.append("<b>")
            elif typ == "italic":
                parts.append("<i>")
            elif typ == "underline":
                parts.append("<u>")
            elif typ == "strikethrough":
                parts.append("<s>")
            elif typ == "spoiler":
                parts.append("<tg-spoiler>")
            elif typ == "code":
                parts.append("<code>")
            elif typ == "pre":
                parts.append("<pre>")
            elif typ == "custom_emoji":
                eid = getattr(ent, "custom_emoji_id", None) or ""
                parts.append(f"<tg-emoji emoji-id='{eid}'>")
        else:
            typ = _entity_type_name(ent)
            if typ == "bold":
                parts.append("</b>")
            elif typ == "italic":
                parts.append("</i>")
            elif typ == "underline":
                parts.append("</u>")
            elif typ == "strikethrough":
                parts.append("</s>")
            elif typ == "spoiler":
                parts.append("</tg-spoiler>")
            elif typ == "code":
                parts.append("</code>")
            elif typ == "pre":
                parts.append("</pre>")
            elif typ == "custom_emoji":
                parts.append("</tg-emoji>")
            if stack and stack[-1] is ent:
                stack.pop()
            elif ent in stack:
                stack.remove(ent)

    if cursor < n:
        emit_plain(cursor, n)
    return "".join(parts)


def strip_tg_emoji(html_text: str) -> str:
    return re.sub(
        r"<tg-emoji[^>]*>(.*?)</tg-emoji>",
        r"\1",
        html_text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )


def icon_html(emoji_id: Optional[str], fallback: str = DEFAULT_ICON_FALLBACK) -> str:
    fb = html.escape(fallback or DEFAULT_ICON_FALLBACK)
    if emoji_id:
        return f"<tg-emoji emoji-id='{emoji_id}'>{fb}</tg-emoji>"
    return fb


def format_granted_at(ts: float) -> str:
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone()
    except Exception:
        dt = datetime.now().astimezone()
    return dt.strftime("%d.%m.%Y | %H.%M.%S")


def granter_link_html(user_id: Optional[int], name: str) -> str:
    safe = html.escape((name or "Администратор").strip() or "Администратор")
    if user_id:
        return f"<a href='tg://user?id={int(user_id)}'>{safe}</a>"
    return safe


# ──────────────────────────────────────────────────────────────────────
# JSONB document helpers
# ──────────────────────────────────────────────────────────────────────

def empty_doc() -> Dict[str, Any]:
    return {"v": JSONB_VERSION, "order": [], "items": {}}


def _normalize_doc(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return empty_doc()
    items = raw.get("items")
    order = raw.get("order")
    if not isinstance(items, dict):
        items = {}
    if not isinstance(order, list):
        order = list(items.keys())
    # drop missing
    order = [str(i) for i in order if str(i) in items]
    for k in list(items.keys()):
        if str(k) not in order:
            order.append(str(k))
    return {"v": JSONB_VERSION, "order": order, "items": {str(k): v for k, v in items.items() if isinstance(v, dict)}}


def _new_instance_id() -> str:
    return uuid.uuid4().hex[:16]


def sorted_items_for_display(doc: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Официальные первыми (в user order), затем свободные (в user order)."""
    doc = _normalize_doc(doc)
    items = doc["items"]
    order = doc["order"]
    official = [(iid, items[iid]) for iid in order if items.get(iid, {}).get("kind") == "official"]
    free = [(iid, items[iid]) for iid in order if items.get(iid, {}).get("kind") != "official"]
    return official + free


def showcase_items(doc: Dict[str, Any], limit: int = SHOWCASE_LIMIT) -> List[Tuple[str, Dict[str, Any]]]:
    """Витрина: первые N из пользовательского порядка (украшение профиля)."""
    doc = _normalize_doc(doc)
    out: List[Tuple[str, Dict[str, Any]]] = []
    for iid in doc["order"]:
        it = doc["items"].get(iid)
        if not it:
            continue
        out.append((iid, it))
        if len(out) >= limit:
            break
    return out


def format_showcase_blockquote(doc: Dict[str, Any]) -> str:
    rows = showcase_items(doc, SHOWCASE_LIMIT)
    if not rows:
        return ""
    lines = []
    for _iid, it in rows:
        ic = icon_html(it.get("icon_emoji_id"), it.get("icon_fallback") or DEFAULT_ICON_FALLBACK)
        title = it.get("title_html") or html.escape(str(it.get("title") or "Достижение"))
        lines.append(f"{ic} {title}")
    body = "\n".join(lines)
    return (
        f"<blockquote>"
        f"<tg-emoji emoji-id='{ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Достижения</b>\n{body}"
        f"</blockquote>"
    )


def format_full_achievements_html(
    doc: Dict[str, Any],
    *,
    owner_name: str = "",
) -> str:
    rows = sorted_items_for_display(doc)
    if not rows:
        return (
            f"<tg-emoji emoji-id='{ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Достижения</b>\n\n"
            f"Пока пусто — скоро здесь появится первая награда."
        )
    parts = [
        f"<tg-emoji emoji-id='{ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Все достижения</b>"
        + (f"\n{html.escape(owner_name)}" if owner_name else ""),
        "",
    ]
    official = [(i, x) for i, x in rows if x.get("kind") == "official"]
    free = [(i, x) for i, x in rows if x.get("kind") != "official"]

    def _card(iid: str, it: Dict[str, Any]) -> str:
        ic = icon_html(it.get("icon_emoji_id"), it.get("icon_fallback") or DEFAULT_ICON_FALLBACK)
        title = it.get("title_html") or html.escape(str(it.get("title") or "Достижение"))
        when = format_granted_at(it.get("granted_at") or time.time())
        who = granter_link_html(it.get("granted_by"), str(it.get("granted_by_name") or "Система"))
        return (
            f"{ic} {title}\n"
            f"<blockquote>"
            f"{when}\n"
            f"Выдал(-а): {who}"
            f"</blockquote>"
        )

    if official:
        parts.append("<b>Официальные</b>")
        for iid, it in official:
            parts.append(_card(iid, it))
            parts.append("")
    if free:
        parts.append("<b>Свободные</b>")
        for iid, it in free:
            parts.append(_card(iid, it))
            parts.append("")
    return "\n".join(parts).strip()


def move_item(doc: Dict[str, Any], instance_id: str, direction: int) -> Dict[str, Any]:
    """direction: -1 вверх, +1 вниз в едином order (витрина)."""
    doc = _normalize_doc(doc)
    order = list(doc["order"])
    iid = str(instance_id)
    if iid not in order:
        return doc
    idx = order.index(iid)
    j = idx + int(direction)
    if j < 0 or j >= len(order):
        return doc
    order[idx], order[j] = order[j], order[idx]
    doc["order"] = order
    return doc


def remove_free_item(doc: Dict[str, Any], instance_id: str) -> Tuple[Dict[str, Any], bool]:
    doc = _normalize_doc(doc)
    iid = str(instance_id)
    it = doc["items"].get(iid)
    if not it or it.get("kind") != "free":
        return doc, False
    doc["items"].pop(iid, None)
    doc["order"] = [x for x in doc["order"] if x != iid]
    return doc, True


def admin_remove_item(doc: Dict[str, Any], instance_id: str) -> Tuple[Dict[str, Any], bool]:
    doc = _normalize_doc(doc)
    iid = str(instance_id)
    if iid not in doc["items"]:
        return doc, False
    doc["items"].pop(iid, None)
    doc["order"] = [x for x in doc["order"] if x != iid]
    return doc, True


def grant_free(
    doc: Dict[str, Any],
    *,
    title_html: str,
    icon_emoji_id: Optional[str],
    icon_fallback: str,
    granted_by: int,
    granted_by_name: str,
) -> Tuple[Dict[str, Any], str]:
    doc = _normalize_doc(doc)
    if len(doc["items"]) >= MAX_ITEMS_PER_USER:
        raise ValueError("limit")
    iid = _new_instance_id()
    doc["items"][iid] = {
        "kind": "free",
        "title_html": (title_html or "")[:MAX_TITLE_HTML_LEN],
        "icon_emoji_id": icon_emoji_id,
        "icon_fallback": icon_fallback or DEFAULT_ICON_FALLBACK,
        "granted_at": time.time(),
        "granted_by": int(granted_by),
        "granted_by_name": (granted_by_name or "")[:64],
        "source": "admin",
    }
    doc["order"].append(iid)
    return doc, iid


def grant_official(
    doc: Dict[str, Any],
    *,
    official_id: int,
    title_html: str,
    icon_emoji_id: Optional[str],
    icon_fallback: str,
    granted_by: Optional[int],
    granted_by_name: str,
    source: str = "admin",
    unique_code: Optional[str] = None,
) -> Tuple[Dict[str, Any], str, bool]:
    """Returns (doc, instance_id, already_had).

    unique_code: если задан — не дублируем (например gbl_level_3).
    """
    doc = _normalize_doc(doc)
    if unique_code:
        for iid, it in doc["items"].items():
            if it.get("kind") == "official" and it.get("unique_code") == unique_code:
                return doc, iid, True
    if len(doc["items"]) >= MAX_ITEMS_PER_USER:
        raise ValueError("limit")
    iid = _new_instance_id()
    item = {
        "kind": "official",
        "official_id": int(official_id),
        "title_html": (title_html or "")[:MAX_TITLE_HTML_LEN],
        "icon_emoji_id": icon_emoji_id,
        "icon_fallback": icon_fallback or DEFAULT_ICON_FALLBACK,
        "granted_at": time.time(),
        "granted_by": int(granted_by) if granted_by else None,
        "granted_by_name": (granted_by_name or "Система")[:64],
        "source": source,
    }
    if unique_code:
        item["unique_code"] = str(unique_code)
    doc["items"][iid] = item
    # Вставить после последних official в order
    insert_at = 0
    for i, existing in enumerate(doc["order"]):
        if doc["items"].get(existing, {}).get("kind") == "official":
            insert_at = i + 1
    doc["order"].insert(insert_at, iid)
    return doc, iid, False


# ──────────────────────────────────────────────────────────────────────
# DB ops (asyncpg pool via Database instance)
# ──────────────────────────────────────────────────────────────────────

ENSURE_SQL = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_achievements JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS official_achievements (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    title_html TEXT NOT NULL DEFAULT '',
    icon_emoji_id TEXT,
    icon_fallback TEXT NOT NULL DEFAULT '⭐',
    description TEXT NOT NULL DEFAULT '',
    rarity INT NOT NULL DEFAULT 1 CHECK (rarity >= 1 AND rarity <= 5),
    sort INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS official_achievements_enabled_sort_idx
    ON official_achievements (enabled, sort, id);
"""


async def ensure_achievements_schema(db) -> None:
    if not await db.ensure_pool():
        raise RuntimeError("pool not ready")
    await db.pool.execute(ENSURE_SQL)
    await seed_gbl_official_if_needed(db)
    try:
        await migrate_legacy_gbl_badges(db)
    except Exception as e:
        print(f"[ACH] migrate gbl badges: {e!r}")


async def migrate_legacy_gbl_badges(db) -> None:
    """Перенос JSON-меток бч в users.profile_achievements (один раз на пользователя/уровень)."""
    try:
        from bot.funcs.group_balance_level import _user_badges, badge_title_for_level
    except Exception:
        return
    try:
        items = list(_user_badges.items())
    except Exception:
        return
    for uid_s, row in items:
        try:
            uid = int(uid_s)
        except Exception:
            continue
        badges = (row or {}).get("badges") or {}
        if not isinstance(badges, dict):
            continue
        for _k, badge in badges.items():
            try:
                lvl = int((badge or {}).get("level") or 0)
            except Exception:
                continue
            if lvl < 1 or lvl > 5:
                continue
            title = str((badge or {}).get("title") or badge_title_for_level(lvl))
            await grant_gbl_level_achievement(
                db, user_id=uid, level=lvl, title_override=title,
            )


async def seed_gbl_official_if_needed(db) -> None:
    for seed in GBL_OFFICIAL_SEEDS:
        title = seed["title"]
        title_html = html.escape(title)
        await db.pool.execute(
            """
            INSERT INTO official_achievements
                (code, title, title_html, icon_emoji_id, icon_fallback, description, rarity, sort, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
            ON CONFLICT (code) DO NOTHING
            """,
            seed["code"],
            title,
            title_html,
            seed.get("icon_emoji_id"),
            seed.get("icon_fallback") or DEFAULT_ICON_FALLBACK,
            seed.get("description") or "",
            int(seed.get("rarity") or 1),
            int(seed.get("sort") or 0),
        )


async def get_user_achievements_doc(db, user_id: int) -> Dict[str, Any]:
    row = await db.pool.fetchrow(
        "SELECT profile_achievements FROM users WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        return empty_doc()
    raw = row["profile_achievements"]
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return _normalize_doc(raw)


async def save_user_achievements_doc(db, user_id: int, doc: Dict[str, Any]) -> None:
    import json
    payload = _normalize_doc(doc)
    await db.pool.execute(
        """
        UPDATE users
        SET profile_achievements = $2::jsonb
        WHERE user_id = $1
        """,
        int(user_id),
        json.dumps(payload, ensure_ascii=False),
    )


async def list_official(
    db,
    *,
    enabled_only: bool = True,
    query: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    lim = max(1, min(200, int(limit)))
    if query:
        q = f"%{query.strip().lower()}%"
        rows = await db.pool.fetch(
            """
            SELECT * FROM official_achievements
            WHERE ($1::bool = FALSE OR enabled = TRUE)
              AND (lower(code) LIKE $2 OR lower(title) LIKE $2)
            ORDER BY sort ASC, id ASC
            LIMIT $3
            """,
            enabled_only,
            q,
            lim,
        )
    else:
        rows = await db.pool.fetch(
            """
            SELECT * FROM official_achievements
            WHERE ($1::bool = FALSE OR enabled = TRUE)
            ORDER BY sort ASC, id ASC
            LIMIT $2
            """,
            enabled_only,
            lim,
        )
    return [dict(r) for r in rows]


async def get_official_by_id(db, official_id: int) -> Optional[Dict[str, Any]]:
    row = await db.pool.fetchrow(
        "SELECT * FROM official_achievements WHERE id = $1",
        int(official_id),
    )
    return dict(row) if row else None


async def get_official_by_code(db, code: str) -> Optional[Dict[str, Any]]:
    row = await db.pool.fetchrow(
        "SELECT * FROM official_achievements WHERE code = $1",
        str(code),
    )
    return dict(row) if row else None


async def find_official(db, needle: str) -> Optional[Dict[str, Any]]:
    n = (needle or "").strip()
    if not n:
        return None
    if n.isdigit():
        return await get_official_by_id(db, int(n))
    by_code = await get_official_by_code(db, n.lower().replace(" ", "_"))
    if by_code:
        return by_code
    row = await db.pool.fetchrow(
        """
        SELECT * FROM official_achievements
        WHERE enabled = TRUE AND lower(title) = lower($1)
        ORDER BY id ASC LIMIT 1
        """,
        n,
    )
    if row:
        return dict(row)
    row = await db.pool.fetchrow(
        """
        SELECT * FROM official_achievements
        WHERE enabled = TRUE AND lower(title) LIKE lower($1)
        ORDER BY sort ASC, id ASC LIMIT 1
        """,
        f"%{n}%",
    )
    return dict(row) if row else None


async def upsert_official(db, data: Dict[str, Any], *, actor_id: Optional[int] = None) -> Dict[str, Any]:
    code = str(data.get("code") or "").strip().lower().replace(" ", "_")
    if not code:
        raise ValueError("code_required")
    title = str(data.get("title") or "").strip()[:80]
    if not title:
        raise ValueError("title_required")
    title_html = str(data.get("title_html") or html.escape(title))[:MAX_TITLE_HTML_LEN]
    icon_emoji_id = data.get("icon_emoji_id")
    if icon_emoji_id is not None:
        icon_emoji_id = str(icon_emoji_id).strip() or None
    icon_fallback = str(data.get("icon_fallback") or DEFAULT_ICON_FALLBACK)[:8]
    description = str(data.get("description") or "")[:MAX_DESCRIPTION_LEN]
    rarity = max(1, min(5, int(data.get("rarity") or 1)))
    sort = int(data.get("sort") or 0)
    enabled = bool(data.get("enabled", True))
    oid = data.get("id")
    if oid:
        row = await db.pool.fetchrow(
            """
            UPDATE official_achievements SET
                code = $2, title = $3, title_html = $4,
                icon_emoji_id = $5, icon_fallback = $6, description = $7,
                rarity = $8, sort = $9, enabled = $10, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            int(oid), code, title, title_html, icon_emoji_id, icon_fallback,
            description, rarity, sort, enabled,
        )
    else:
        row = await db.pool.fetchrow(
            """
            INSERT INTO official_achievements
                (code, title, title_html, icon_emoji_id, icon_fallback, description,
                 rarity, sort, enabled, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                title_html = EXCLUDED.title_html,
                icon_emoji_id = EXCLUDED.icon_emoji_id,
                icon_fallback = EXCLUDED.icon_fallback,
                description = EXCLUDED.description,
                rarity = EXCLUDED.rarity,
                sort = EXCLUDED.sort,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING *
            """,
            code, title, title_html, icon_emoji_id, icon_fallback,
            description, rarity, sort, enabled, actor_id,
        )
    return dict(row)


async def delete_official(db, official_id: int) -> bool:
    tag = await db.pool.execute(
        "DELETE FROM official_achievements WHERE id = $1",
        int(official_id),
    )
    return tag.endswith("1")


# ──────────────────────────────────────────────────────────────────────
# Permissions (bot-side, mirrors panel matrix)
# ──────────────────────────────────────────────────────────────────────

PERM_MANAGE = "manage_achievements"
PERM_GRANT_OFFICIAL = "grant_official_achievements"
PERM_GRANT_FREE = "grant_free_achievements"

_ACH_SECTION_PERMS = {
    "achievements": {PERM_MANAGE, PERM_GRANT_OFFICIAL, PERM_GRANT_FREE},
    "achievements.catalog": {PERM_MANAGE},
    "achievements.grantOfficial": {PERM_GRANT_OFFICIAL},
    "achievements.grantFree": {PERM_GRANT_FREE},
}


async def admin_has_perm(db, user_id: int, permission: str) -> bool:
    """Проверка права выдачи/каталога через admin_accounts + матрицу панели."""
    try:
        if not await db.ensure_pool():
            return False
        row = await db.pool.fetchrow(
            "SELECT role, status FROM admin_accounts WHERE user_id = $1",
            int(user_id),
        )
        if not row:
            return False
        if str(row["status"] or "") != "active":
            return False
        role = str(row["role"] or "")
        if role == "owner":
            return True

        # Role defaults + user overrides (same tables as panel)
        defaults = await db.pool.fetch(
            "SELECT section_id, enabled FROM admin_panel_role_defaults WHERE role = $1",
            role,
        )
        role_map = {r["section_id"]: bool(r["enabled"]) for r in defaults}
        overrides = await db.pool.fetch(
            "SELECT section_id, allowed FROM admin_panel_user_access WHERE user_id = $1",
            int(user_id),
        )
        over_map = {r["section_id"]: bool(r["allowed"]) for r in overrides}

        def key_enabled(key: str) -> bool:
            if key in over_map:
                return over_map[key]
            if key in role_map:
                return role_map[key]
            # builtin: section achievements off by default for non-owner unless role has perm
            return False

        # Parent section must be on for child keys
        if not key_enabled("achievements") and "achievements" not in over_map:
            # If parent never seeded, check if any child explicitly allowed
            any_child = any(
                key_enabled(k) for k in (
                    "achievements.catalog",
                    "achievements.grantOfficial",
                    "achievements.grantFree",
                )
            )
            if not any_child:
                return False
        elif not key_enabled("achievements"):
            return False

        for key, perms in _ACH_SECTION_PERMS.items():
            if permission in perms and key_enabled(key):
                return True
        return False
    except Exception as e:
        print(f"[ACH] admin_has_perm fail: {e!r}")
        return False


async def grant_official_to_user(
    db,
    *,
    target_user_id: int,
    official: Dict[str, Any],
    granted_by: Optional[int],
    granted_by_name: str,
    source: str = "admin",
    unique_code: Optional[str] = None,
) -> Dict[str, Any]:
    doc = await get_user_achievements_doc(db, target_user_id)
    title_html = official.get("title_html") or html.escape(str(official.get("title") or ""))
    doc, iid, already = grant_official(
        doc,
        official_id=int(official["id"]),
        title_html=title_html,
        icon_emoji_id=official.get("icon_emoji_id"),
        icon_fallback=str(official.get("icon_fallback") or DEFAULT_ICON_FALLBACK),
        granted_by=granted_by,
        granted_by_name=granted_by_name,
        source=source,
        unique_code=unique_code or official.get("code"),
    )
    await save_user_achievements_doc(db, target_user_id, doc)
    return {"ok": True, "instance_id": iid, "already": already, "doc": doc}


async def grant_free_to_user(
    db,
    *,
    target_user_id: int,
    title_html: str,
    icon_emoji_id: Optional[str],
    icon_fallback: str,
    granted_by: int,
    granted_by_name: str,
) -> Dict[str, Any]:
    doc = await get_user_achievements_doc(db, target_user_id)
    doc, iid = grant_free(
        doc,
        title_html=title_html,
        icon_emoji_id=icon_emoji_id,
        icon_fallback=icon_fallback,
        granted_by=granted_by,
        granted_by_name=granted_by_name,
    )
    await save_user_achievements_doc(db, target_user_id, doc)
    return {"ok": True, "instance_id": iid, "doc": doc}


async def grant_gbl_level_achievement(
    db,
    *,
    user_id: int,
    level: int,
    title_override: Optional[str] = None,
) -> None:
    level = max(1, min(5, int(level)))
    code = f"gbl_level_{level}"
    official = await get_official_by_code(db, code)
    if not official:
        await seed_gbl_official_if_needed(db)
        official = await get_official_by_code(db, code)
    if not official:
        return
    if title_override:
        official = dict(official)
        official["title"] = title_override
        official["title_html"] = html.escape(title_override)
    try:
        await grant_official_to_user(
            db,
            target_user_id=int(user_id),
            official=official,
            granted_by=None,
            granted_by_name="Баланс группы",
            source="gbl",
            unique_code=code,
        )
    except Exception as e:
        print(f"[ACH] gbl grant fail: {e!r}")


def help_admin_html() -> str:
    return (
        f"<tg-emoji emoji-id='{ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Достижения — гайд для команды</b>\n\n"
        f"<b>Свободная награда</b>\n"
        f"1. Ответьте на сообщение игрока\n"
        f"2. Напишите: <code>наградить ваш текст</code>\n"
        f"Можно с premium-эмодзи и жирным/курсивом — всё сохранится.\n\n"
        f"Или без реплая:\n"
        f"<code>наградить @user текст</code>\n"
        f"<code>наградить 123456 текст</code>\n\n"
        f"<b>Официальная награда</b>\n"
        f"<code>наградить официально код</code>\n"
        f"или просто <code>наградить</code> → выберите из списка.\n\n"
        f"<b>Снять</b>\n"
        f"<code>снять достижение</code> (реплай) — список для снятия.\n\n"
        f"<i>Ссылки и blockquote в тексте награды запрещены.</i>\n"
        f"Синонимы: выдать достижение · дать ачивку · забрать ачивку"
    )
