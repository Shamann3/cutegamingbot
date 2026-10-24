# -*- coding: utf-8 -*-
"""Бонус +: ролл наград и покупка предмета за счёт технических групп."""
from __future__ import annotations

import json
import random
import re
from typing import Any

from flame_bonus_plus_copy import HISTORY_BUY, HISTORY_PROJECT, item_got
from flame_engine import _pick_weighted


# Те же 9, что сейчас стоят на поле Бонуса + (порядок: слева направо, сверху вниз).
DEFAULT_BOARD_CELLS = (
    {"id": "5321218545621706269", "alt": "🎈"},
    {"id": "5316569385257702225", "alt": "🎒"},
    {"id": "5355073951749927916", "alt": "🍭"},
    {"id": "5285257694985352512", "alt": "💍"},
    {"id": "5438458242130806642", "alt": "🎁"},
    {"id": "5310214083495103551", "alt": "🎁"},
    {"id": "5424987025667293801", "alt": "🐰"},
    {"id": "5427103061564752778", "alt": "🐰"},
    {"id": "5424861140175849850", "alt": "🎂"},
)
_CELL_TAG = re.compile(
    r"<tg-emoji\b[^>]*emoji-id\s*=\s*['\"](\d{5,32})['\"][^>]*>(.*?)</tg-emoji>",
    re.IGNORECASE | re.DOTALL,
)
_CELL_ID = re.compile(r"^\d{5,32}$")


def _clean_alt(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(raw or ""))
    text = " ".join(text.split()).replace("<", "").replace(">", "")
    return (text[:8] or "🎁")


def parse_cell_paste(text: str) -> list[dict]:
    """Один или несколько премиум-эмодзи из вставки: тег tg-emoji или голый id."""
    src = str(text or "").strip()
    if not src:
        return []
    tagged = [
        {"id": match.group(1), "alt": _clean_alt(match.group(2))}
        for match in _CELL_TAG.finditer(src)
    ]
    if tagged:
        return tagged[:9]
    if _CELL_ID.fullmatch(src):
        return [{"id": src, "alt": "🎁"}]
    if re.fullmatch(r"[\d\s,;]+", src):
        ids = re.findall(r"(?<!\d)(\d{5,32})(?!\d)", src)
        return [{"id": item, "alt": "🎁"} for item in ids[:9]]
    return []


def _coerce_cells(raw) -> list:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return parse_cell_paste(text)
        return parsed if isinstance(parsed, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _one_cell(raw, fallback: dict) -> dict:
    if isinstance(raw, dict):
        emoji_id = str(raw.get("id") or raw.get("emojiId") or raw.get("emoji_id") or "").strip()
        alt = raw.get("alt") if raw.get("alt") not in (None, "") else raw.get("fallback") or ""
        if _CELL_ID.fullmatch(emoji_id):
            return {"id": emoji_id, "alt": _clean_alt(alt)}
        pasted = parse_cell_paste(emoji_id or str(alt or ""))
        if pasted:
            return pasted[0]
        return {"id": fallback["id"], "alt": fallback["alt"]}
    pasted = parse_cell_paste(str(raw or ""))
    if pasted:
        return pasted[0]
    return {"id": fallback["id"], "alt": fallback["alt"]}


def board_cells(raw=None) -> list[dict]:
    """Ровно 9 клеток. Пустое и битое место остаётся эмодзи по умолчанию на этой позиции."""
    items = _coerce_cells(raw)
    out = []
    for index, fallback in enumerate(DEFAULT_BOARD_CELLS):
        piece = items[index] if index < len(items) else None
        out.append(dict(fallback) if piece is None else _one_cell(piece, fallback))
    return out


def canon_board_cells(raw=None) -> str:
    return json.dumps(board_cells(raw), ensure_ascii=False, separators=(",", ":"))


def board_cell_faces(raw=None) -> list[str]:
    """Теги для кнопок 3×3. Порядок тот же, что в сетке вкладки."""
    return [
        f"<tg-emoji emoji-id='{cell['id']}'>{cell['alt']}</tg-emoji>"
        for cell in board_cells(raw)
    ]


def _pick(raw: dict, *keys, default=None):
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return default


def gift_plus_defaults(settings: dict | None = None) -> dict:
    raw = settings or {}
    return {
        "enabled": bool(_pick(raw, "enabled", "gift_enabled", default=True)),
        "mult": max(1, min(10, int(_pick(raw, "mult", "gift_mult", default=1) or 1))),
        "kuty_min": max(1, int(_pick(raw, "kuty_min", "gift_kuty_min", default=1) or 1)),
        "kuty_max": max(1, int(_pick(raw, "kuty_max", "gift_kuty_max", default=3) or 3)),
        "extra_kuty_on": bool(_pick(raw, "extra_kuty_on", "gift_extra_kuty_on", default=True)),
        "extra_kuty_chance": max(0, min(100, int(_pick(raw, "extra_kuty_chance", "gift_extra_kuty_chance", default=35) or 0))),
        "extra_kuty_min": max(0, int(_pick(raw, "extra_kuty_min", "gift_extra_kuty_min", default=5) or 0)),
        "extra_kuty_max": max(0, int(_pick(raw, "extra_kuty_max", "gift_extra_kuty_max", default=25) or 0)),
        "item_on": bool(_pick(raw, "item_on", "gift_item_on", default=True)),
        "item_chance": max(0, min(100, int(_pick(raw, "item_chance", "gift_item_chance", default=40) or 0))),
        "item_count": max(1, min(5, int(_pick(raw, "item_count", "gift_item_count", default=1) or 1))),
        "fallback_pct": max(1, min(100, int(_pick(raw, "fallback_pct", "gift_fallback_pct", default=30) or 30))),
        "drops": list(raw.get("drops") or []),
    }


def _clamp_range(lo: int, hi: int) -> tuple[int, int]:
    a = max(0, int(lo or 0))
    b = max(a, int(hi or 0))
    return a, b


def roll_board_kuty(conf: dict) -> int:
    lo, hi = _clamp_range(conf.get("kuty_min"), conf.get("kuty_max"))
    lo = max(1, lo)
    hi = max(lo, hi)
    mult = max(1, int(conf.get("mult") or 1))
    return random.randint(lo, hi) * mult


def _item_rows(drops: list) -> list[dict]:
    rows = []
    for row in drops or []:
        name = str(row.get("item_name") or row.get("itemName") or "").strip()
        if str(row.get("kind") or "") != "item" or not name:
            continue
        rows.append({
            "kind": "item",
            "item_name": name,
            "weight": max(1, int(row.get("weight") or 1)),
        })
    return rows


def _names_with_fallback(preferred: str, pool_rows: list[dict]) -> list[str]:
    names = []
    if preferred:
        names.append(preferred)
    for row in pool_rows:
        name = str(row.get("item_name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def roll_extra_bundle(conf: dict) -> dict:
    """Независимые шансы: доп. куты и до N предметов могут выпасть вместе."""
    conf = gift_plus_defaults(conf)
    out = {
        "extra_kuty": 0,
        "want_item": False,
        "item_names": [],
        "item_picks": [],
    }
    if conf["extra_kuty_on"] and conf["extra_kuty_chance"] > 0:
        if random.randint(1, 100) <= conf["extra_kuty_chance"]:
            lo, hi = _clamp_range(conf["extra_kuty_min"], conf["extra_kuty_max"])
            if hi >= 1:
                out["extra_kuty"] = random.randint(max(1, lo), hi)
    if conf["item_on"] and conf["item_chance"] > 0 and conf["drops"]:
        remaining = _item_rows(conf["drops"])
        all_rows = list(remaining)
        slots = max(1, int(conf["item_count"] or 1))
        for _ in range(slots):
            if not remaining:
                break
            if random.randint(1, 100) > conf["item_chance"]:
                continue
            preferred = _pick_weighted(remaining)
            if not preferred:
                break
            name = preferred["item_name"]
            out["item_picks"].append(_names_with_fallback(name, all_rows))
            remaining = [row for row in remaining if row["item_name"] != name]
        out["want_item"] = bool(out["item_picks"])
        if out["item_picks"]:
            out["item_names"] = list(out["item_picks"][0])
    # Старый формат: weighted kuty drops в таблице тоже учитываем как доп. куты
    # только если отдельный extra_kuty выключен и выпал kuty-дроп.
    if not conf["extra_kuty_on"]:
        kuty_rows = [row for row in conf["drops"] if str(row.get("kind") or "") == "kuty"]
        if kuty_rows:
            picked = _pick_weighted([
                {
                    "kind": "kuty",
                    "amount_min": int(row.get("amount_min") or row.get("amountMin") or 1),
                    "amount_max": int(row.get("amount_max") or row.get("amountMax") or 1),
                    "weight": max(1, int(row.get("weight") or 1)),
                }
                for row in kuty_rows
            ])
            if picked and random.random() < 0.5:
                a = max(1, int(picked.get("amount_min") or 1))
                b = max(a, int(picked.get("amount_max") or a))
                out["extra_kuty"] = random.randint(a, b)
    return out


async def _take_technical(conn, amount: int) -> int:
    need = max(0, int(amount or 0))
    if need < 1:
        return 0
    rows = await conn.fetch(
        """
        SELECT chat_id, COALESCE(chatbalance, 0) AS bal
        FROM chat
        WHERE COALESCE(is_technical, FALSE) = TRUE
          AND COALESCE(chatbalance, 0) > 0
        ORDER BY chatbalance DESC
        FOR UPDATE
        """
    )
    left = need
    taken = 0
    for row in rows:
        if left < 1:
            break
        bal = int(row["bal"] or 0)
        if bal < 1:
            continue
        bite = min(bal, left)
        await conn.execute(
            "UPDATE chat SET chatbalance = chatbalance - $2 WHERE chat_id = $1",
            int(row["chat_id"]),
            bite,
        )
        taken += bite
        left -= bite
    return taken


async def _dex_by_name(conn, name: str) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT id, name, name1, emoji, COALESCE(price, 0) AS price, COALESCE(remains, 0) AS remains
        FROM dex
        WHERE name = $1 OR name1 = $1
        ORDER BY CASE WHEN name = $1 THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        str(name or "").strip(),
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "name": str(row["name"] or "").strip() or str(name),
        "name1": str(row["name1"] or "").strip(),
        "emoji": str(row["emoji"] or "").strip() or "🎁",
        "price": max(0, int(row["price"] or 0)),
        "remains": int(row["remains"] or 0),
    }


def _codec():
    try:
        from bot.db_create.items_codec import decode_items, encode_items
        return decode_items, encode_items
    except Exception:
        import json

        def decode_items(raw):
            if isinstance(raw, dict):
                return {str(k): v for k, v in raw.items()}
            if not raw:
                return {}
            try:
                data = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:
                return {}
            return data if isinstance(data, dict) else {}

        def encode_items(items):
            return json.dumps({str(k): int(v or 0) for k, v in (items or {}).items() if int(v or 0) > 0}, ensure_ascii=False)

        return decode_items, encode_items


async def _add_item(conn, user_id: int, name: str, qty: int = 1) -> None:
    decode_items, encode_items = _codec()
    row = await conn.fetchrow("SELECT items FROM users WHERE user_id = $1 FOR UPDATE", int(user_id))
    bag = decode_items(row["items"] if row else None)
    bag[name] = int(bag.get(name) or 0) + max(1, int(qty))
    await conn.execute(
        "UPDATE users SET items = $1 WHERE user_id = $2",
        encode_items(bag),
        int(user_id),
    )


async def _credit_kuty(conn, user_id: int, amount: int) -> None:
    add = max(0, int(amount or 0))
    if add < 1:
        return
    await conn.execute(
        "UPDATE users SET balance = COALESCE(balance, 0) + $2 WHERE user_id = $1",
        int(user_id),
        add,
    )


async def _refund_tech(conn, amount: int) -> None:
    if amount < 1:
        return
    rich = await conn.fetchrow(
        """
        SELECT chat_id FROM chat
        WHERE COALESCE(is_technical, FALSE) = TRUE
        ORDER BY COALESCE(chatbalance, 0) DESC
        LIMIT 1
        """
    )
    if rich:
        await conn.execute(
            "UPDATE chat SET chatbalance = chatbalance + $2 WHERE chat_id = $1",
            int(rich["chat_id"]),
            int(amount),
        )


async def _buy_from_shop(conn, user_id: int, dex: dict) -> dict | None:
    name = dex["name"]
    price = max(0, int(dex["price"] or 0))
    if int(dex["remains"] or 0) < 1:
        return None
    paid = 0
    if price > 0:
        paid = await _take_technical(conn, price)
        if paid < price:
            await _refund_tech(conn, paid)
            return None
    updated = await conn.fetchrow(
        """
        UPDATE dex
        SET remains = remains - 1
        WHERE id = $1 AND remains >= 1
        RETURNING id
        """,
        int(dex["id"]),
    )
    if not updated:
        await _refund_tech(conn, paid)
        return None
    await _add_item(conn, user_id, name, 1)
    return {
        "ok": True,
        "source": "shop",
        "item_name": name,
        "emoji": dex["emoji"],
        "price": price,
        "paid": price,
        "line": item_got(dex["emoji"], name),
    }


async def _buy_from_market(conn, user_id: int, dex: dict) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT l.id, l.seller_id, l.item_id, l.quantity, l.price
        FROM market_listings l
        WHERE l.status = 'active'
          AND l.quantity > 0
          AND l.item_id = $1
          AND l.seller_id <> $2
        ORDER BY l.price ASC, l.id ASC
        LIMIT 1
        FOR UPDATE OF l
        """,
        str(dex["id"]),
        int(user_id),
    )
    if not row:
        return None
    unit = max(0, int(row["price"] or 0))
    total = unit
    try:
        from market_rules import calc_market_commission, calc_market_seller_payout
        commission = calc_market_commission(total)
        seller_payout = calc_market_seller_payout(total)
    except Exception:
        commission = 0
        seller_payout = total
    paid = 0
    if total > 0:
        paid = await _take_technical(conn, total)
        if paid < total:
            await _refund_tech(conn, paid)
            return None
    seller_id = int(row["seller_id"])
    if seller_payout > 0:
        await conn.execute(
            "UPDATE users SET balance = COALESCE(balance, 0) + $2 WHERE user_id = $1",
            seller_id,
            seller_payout,
        )
    _ = commission  # уже внутри total, остаётся в техгруппах как разница
    qty_left = int(row["quantity"] or 0) - 1
    if qty_left <= 0:
        await conn.execute(
            "UPDATE market_listings SET quantity = 0, status = 'sold' WHERE id = $1",
            int(row["id"]),
        )
    else:
        await conn.execute(
            "UPDATE market_listings SET quantity = $2 WHERE id = $1",
            int(row["id"]),
            qty_left,
        )
    await _add_item(conn, user_id, dex["name"], 1)
    return {
        "ok": True,
        "source": "market",
        "item_name": dex["name"],
        "emoji": dex["emoji"],
        "price": unit,
        "paid": total,
        "line": item_got(dex["emoji"], dex["name"]),
    }


async def acquire_bonus_item(pool, user_id: int, names: list[str], fallback_pct: int) -> dict:
    """Купить один из предметов за техгруппы или выдать запасные куты."""
    wanted = [str(n).strip() for n in (names or []) if str(n).strip()]
    if not wanted:
        return {"ok": False}
    pct = max(1, min(100, int(fallback_pct or 30)))
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1) Предпочтительный порядок: shop, потом market для каждого имени.
            for name in wanted:
                dex = await _dex_by_name(conn, name)
                if not dex:
                    continue
                got = await _buy_from_shop(conn, int(user_id), dex)
                if got:
                    got["history"] = HISTORY_BUY
                    return got
                got = await _buy_from_market(conn, int(user_id), dex)
                if got:
                    got["history"] = HISTORY_BUY
                    return got
            # 2) Ничего нет — запасные куты = pct% от реальной цены предмета.
            # Без цены и без остатка на техгруппах ничего не выдаём «из воздуха».
            ref_price = 0
            for name in wanted:
                dex = await _dex_by_name(conn, name)
                if dex and int(dex["price"] or 0) > 0:
                    ref_price = int(dex["price"])
                    break
            if ref_price < 1:
                return {"ok": False}
            gift = max(1, int(round(ref_price * pct / 100.0)))
            paid = await _take_technical(conn, gift)
            if paid < 1:
                return {"ok": False}
            credit = min(gift, paid)
            await _credit_kuty(conn, int(user_id), credit)
            return {
                "ok": True,
                "source": "project_kuty",
                "item_name": "",
                "emoji": "",
                "price": ref_price,
                "paid": credit,
                "project_kuty": credit,
                "line": "",
                "history": HISTORY_PROJECT,
            }


async def acquire_bonus_items(
    pool,
    user_id: int,
    picks: list[list[str]],
    fallback_pct: int,
) -> list[dict]:
    """Купить несколько слотов предметов подряд. Каждый слот — свой список предпочтений."""
    results = []
    for names in picks or []:
        got = await acquire_bonus_item(pool, int(user_id), list(names or []), int(fallback_pct or 30))
        if got.get("ok"):
            results.append(got)
    return results


async def pay_user_from_tech(pool, user_id: int, amount: int) -> int:
    """Снять с техгрупп и начислить пользователю. Возвращает реально выданное."""
    need = max(0, int(amount or 0))
    if need < 1:
        return 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            paid = await _take_technical(conn, need)
            if paid < 1:
                return 0
            await _credit_kuty(conn, int(user_id), paid)
            return paid


def board_range(conf: dict) -> tuple[int, int]:
    conf = gift_plus_defaults(conf)
    lo = max(1, int(conf["kuty_min"])) * conf["mult"]
    hi = max(lo, int(conf["kuty_max"]) * conf["mult"])
    return lo, hi


def preview_show_names(conf: dict | None) -> list[str]:
    """Имена предметов, отмеченных галочкой «показать в Что можно получить?»."""
    conf = gift_plus_defaults(conf or {})
    if not conf.get("item_on"):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for row in conf.get("drops") or []:
        show = row.get("show_preview")
        if show is None:
            show = row.get("showPreview")
        if not show:
            continue
        if str(row.get("kind") or "") != "item":
            continue
        name = str(row.get("item_name") or row.get("itemName") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def preview_kuty_lines(conf: dict | None) -> list[str]:
    """Строки про куты — те же числа, что во вкладке «Бонус +»."""
    conf = gift_plus_defaults(conf or {})
    lo, hi = board_range(conf)
    if lo == hi:
        lines = [f"С выбранной клетки: <b>+{lo}</b> кут"]
    else:
        lines = [f"С выбранной клетки: <b>+{lo}…{hi}</b> кут"]
    if not conf.get("extra_kuty_on"):
        return lines
    chance = int(conf.get("extra_kuty_chance") or 0)
    if chance < 1:
        return lines
    a = max(0, int(conf.get("extra_kuty_min") or 0))
    b = max(a, int(conf.get("extra_kuty_max") or 0))
    if b < 1:
        return lines
    a = max(1, a)
    b = max(a, b)
    bit = f"<b>+{a}</b> кут" if a == b else f"<b>+{a}…{b}</b> кут"
    if chance >= 100:
        lines.append(f"ещё {bit} — дополнительно к клетке")
    else:
        lines.append(f"иногда ещё {bit} — не в каждом открытии")
    return lines


def preview_hidden_names(conf: dict | None) -> list[str]:
    """Предметы пула без галочки: могут выпасть, в списке игрока их нет."""
    conf = gift_plus_defaults(conf or {})
    if not conf.get("item_on"):
        return []
    shown = set(preview_show_names(conf))
    hidden: list[str] = []
    seen: set[str] = set()
    for row in conf.get("drops") or []:
        if str(row.get("kind") or "") != "item":
            continue
        name = str(row.get("item_name") or row.get("itemName") or "").strip()
        if not name or name in seen or name in shown:
            continue
        seen.add(name)
        hidden.append(name)
    return hidden


def preview_max_gifts(conf: dict | None) -> int:
    conf = gift_plus_defaults(conf or {})
    if not conf.get("item_on"):
        return 0
    names = preview_show_names(conf)
    if not names:
        return 0
    return min(int(conf.get("item_count") or 1), len(names))


def preview_has_content(conf: dict | None) -> bool:
    """Кнопка «Что можно получить?» — всегда, пока Бонус + включён."""
    conf = gift_plus_defaults(conf or {})
    return bool(conf.get("enabled", True))
