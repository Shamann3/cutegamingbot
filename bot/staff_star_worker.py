"""Фоновая обработка staff_star_payouts: Fragment / пост в канал для userbot."""

from __future__ import annotations

import asyncio
import logging
from html import escape
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("staff-star-worker")

# Тот же канал, что у выводов игроков в main.py (с запасным numeric id)
WITHDRAW_CHANNEL_PRIMARY = "@CurrencyCute"
WITHDRAW_CHANNEL_FALLBACK = -1002552723822
WITHDRAW_CHANNELS = (WITHDRAW_CHANNEL_PRIMARY, WITHDRAW_CHANNEL_FALLBACK)


async def refresh_star_gifts_cache(db, bot) -> int:
    """Синхронизирует каталог подарков (live + manual) в БД для админ-панели."""
    try:
        from bot.design.buttons import (
            _merge_live_and_manual_gifts,
            get_all_manual_gifts,
            get_available_gifts_fast,
        )
    except Exception:
        logger.exception("gift imports failed")
        return 0

    payload = []
    try:
        live = await get_available_gifts_fast(bot)
        manual = await get_all_manual_gifts()
        merged = _merge_live_and_manual_gifts(live, manual)
        for g in merged or []:
            try:
                if isinstance(g, dict):
                    gift_id = int(g.get("id") or 0)
                    stars = int(g.get("price") or g.get("stars") or 0)
                    emoji = g.get("emoji") or g.get("base_emoji") or "🎁"
                    custom = str(
                        g.get("manual_custom_emoji_id")
                        or g.get("custom_emoji_id")
                        or ""
                    )
                    has_up = bool(int(g.get("has_upgrade") or 0))
                    up_stars = int(g.get("upgrade_price") or 0)
                    source = "manual" if g.get("is_manual") else "live"
                else:
                    gift_id = int(getattr(g, "id", 0) or 0)
                    stars = int(
                        getattr(g, "star_count", None)
                        or getattr(g, "stars", None)
                        or 0
                    )
                    emoji = getattr(g, "emoji", None) or "🎁"
                    sticker = getattr(g, "sticker", None)
                    custom = ""
                    if sticker is not None:
                        custom = str(getattr(sticker, "custom_emoji_id", None) or "")
                    has_up = bool(getattr(g, "upgrade_star_count", None))
                    up_stars = int(getattr(g, "upgrade_star_count", None) or 0)
                    source = "live"
            except Exception:
                continue
            if gift_id <= 0 or stars <= 0:
                continue
            payload.append((gift_id, stars, emoji, custom or None, has_up, up_stars, source))
    except Exception:
        logger.exception("collect gifts for cache failed")
        return 0

    if not payload:
        return 0
    try:
        n = 0
        async with db.pool.acquire() as conn:
            for gift_id, stars, emoji, custom, has_up, up_stars, source in payload:
                await conn.execute(
                    """
                    INSERT INTO star_gifts_cache
                        (gift_id, stars, emoji, custom_emoji_id, has_upgrade, upgrade_stars, source, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (gift_id) DO UPDATE SET
                        stars = EXCLUDED.stars,
                        emoji = EXCLUDED.emoji,
                        custom_emoji_id = EXCLUDED.custom_emoji_id,
                        has_upgrade = EXCLUDED.has_upgrade,
                        upgrade_stars = EXCLUDED.upgrade_stars,
                        source = EXCLUDED.source,
                        updated_at = NOW()
                    """,
                    gift_id, stars, emoji, custom, has_up, up_stars, source,
                )
                n += 1
        return n
    except Exception:
        logger.exception("persist star gifts cache failed")
        return 0


async def refresh_fragment_health(db, fragment_client, seed_phrase: str) -> dict:
    """Пишет fragment_ok / ton в staff_payout_settings."""
    ton = None
    err = None
    ok = False
    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: fragment_client.get_balance(seed=seed_phrase),
        )
        raw = (res or {}).get("balance", 0)
        ton = int(raw) / 1e9 if raw is not None else 0.0
        ok = ton > 0
        if not ok:
            err = "Fragment TON ≤ 0"
    except Exception as e:
        err = str(e)[:300]
        ok = False
        logger.warning("fragment health check failed: %s", e)

    try:
        await db.pool.execute(
            """
            INSERT INTO staff_payout_settings
                (id, fragment_ok, fragment_ton, fragment_error, fragment_checked_at)
            VALUES (1, $1, $2, $3, NOW())
            ON CONFLICT (id) DO UPDATE SET
                fragment_ok = EXCLUDED.fragment_ok,
                fragment_ton = EXCLUDED.fragment_ton,
                fragment_error = EXCLUDED.fragment_error,
                fragment_checked_at = NOW()
            """,
            ok, ton, err,
        )
    except Exception:
        logger.exception("failed to persist fragment health")
    return {"ok": ok, "ton": ton, "error": err}


async def _claim_next(db) -> Optional[dict]:
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # Зависшие processing → снова в очередь
            await conn.execute(
                """
                UPDATE staff_star_payouts
                SET status = 'queued', updated_at = NOW(),
                    error = COALESCE(error, 'requeued: stuck processing')
                WHERE status = 'processing'
                  AND updated_at < NOW() - INTERVAL '3 minutes'
                """
            )
            row = await conn.fetchrow(
                """
                SELECT * FROM staff_star_payouts
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            if not row:
                return None
            await conn.execute(
                """
                UPDATE staff_star_payouts
                SET status = 'processing', updated_at = NOW()
                WHERE id = $1
                """,
                int(row["id"]),
            )
            return dict(row)


async def _mark(db, payout_id: int, status: str, *, error: str | None = None,
                txid: str | None = None, channel_message_id: int | None = None) -> None:
    await db.pool.execute(
        """
        UPDATE staff_star_payouts
        SET status = $2,
            error = COALESCE($3, error),
            txid = COALESCE($4, txid),
            channel_message_id = COALESCE($5, channel_message_id),
            completed_at = CASE WHEN $2 IN ('completed', 'failed', 'cancelled', 'refunded')
                                THEN NOW() ELSE completed_at END,
            updated_at = NOW()
        WHERE id = $1
        """,
        payout_id, status, error, txid, channel_message_id,
    )


async def _complete_salary_payment(db, row: dict, txid: str) -> None:
    """Помечает зарплату/премию оплаченной после успешной отправки звёзд."""
    source = row.get("source") or "salary"
    amount = int(row["amount"])
    user_id = int(row["user_id"])
    paid_by = int(row["requested_by"])
    kind = row.get("kind") or "payment"

    if source == "bonus" and row.get("bonus_id"):
        bonus_id = int(row["bonus_id"])
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                b = await conn.fetchrow(
                    "SELECT amount, paid_amount, status FROM staff_bonuses WHERE id = $1 FOR UPDATE",
                    bonus_id,
                )
                if not b or b["status"] not in ("approved", "partially_paid"):
                    return
                already = int(b["paid_amount"] or 0)
                total = int(b["amount"])
                pay = min(amount, max(0, total - already))
                if pay <= 0:
                    return
                await conn.execute(
                    """
                    INSERT INTO bonus_payments
                        (bonus_id, user_id, amount, method, kind, txid, paid_by)
                    VALUES ($1, $2, $3, 'stars', $4, $5, $6)
                    """,
                    bonus_id, user_id, pay, kind, txid, paid_by,
                )
                new_paid = already + pay
                new_status = "paid" if new_paid >= total else "partially_paid"
                await conn.execute(
                    """
                    UPDATE staff_bonuses
                    SET paid_amount = $2, status = $3, paid_by = $4, paid_at = NOW(),
                        txid = COALESCE($5, txid), updated_at = NOW()
                    WHERE id = $1
                    """,
                    bonus_id, new_paid, new_status, paid_by, txid,
                )
        return

    salary_id = int(row["salary_id"]) if row.get("salary_id") else None
    if not salary_id:
        return
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            s = await conn.fetchrow(
                "SELECT amount, paid_amount, status FROM staff_salaries WHERE id = $1 FOR UPDATE",
                salary_id,
            )
            if not s or s["status"] not in ("approved", "partially_paid"):
                return
            already = int(s["paid_amount"] or 0)
            total = int(s["amount"])
            pay = min(amount, max(0, total - already))
            if pay <= 0:
                return
            await conn.execute(
                """
                INSERT INTO salary_payments
                    (salary_id, user_id, amount, method, kind, txid, paid_by)
                VALUES ($1, $2, $3, 'stars', $4, $5, $6)
                """,
                salary_id, user_id, pay, kind, txid, paid_by,
            )
            new_paid = already + pay
            new_status = "paid" if new_paid >= total else "partially_paid"
            await conn.execute(
                """
                UPDATE staff_salaries
                SET paid_amount = $2, status = $3, paid_by = $4, paid_at = NOW(),
                    txid = COALESCE($5, txid), updated_at = NOW()
                WHERE id = $1
                """,
                salary_id, new_paid, new_status, paid_by, txid,
            )


async def _try_fragment(
    fragment_client,
    seed_phrase: str,
    username: str,
    amount: int,
) -> tuple[bool, str | None, str | None]:
    """Возвращает (ok, txid, error)."""
    loop = asyncio.get_running_loop()
    try:
        bal = await loop.run_in_executor(
            None, lambda: fragment_client.get_balance(seed=seed_phrase),
        )
        ton = int((bal or {}).get("balance", 0)) / 1e9
        if ton <= 0:
            return False, None, "Fragment недоступен (TON ≤ 0)"
    except Exception as e:
        return False, None, f"Fragment balance error: {e}"

    last_err = None
    for attempt in range(3):
        try:
            result = await loop.run_in_executor(
                None,
                lambda: fragment_client.buy_stars_without_kyc(
                    username=username, amount=int(amount), seed=seed_phrase,
                ),
            )
            tx = None
            if isinstance(result, dict):
                tx = result.get("tx_hash") or result.get("hash")
            return True, str(tx) if tx else f"fragment-ok-{attempt}", None
        except Exception as e:
            last_err = str(e)
            await asyncio.sleep(1.2)
    return False, None, last_err or "Fragment send failed"


async def _send_withdraw_channel_message(bot, *, text: str, reply_markup=None):
    """Пост в канал выводов строго как у игроков: сначала @CurrencyCute, потом numeric fallback."""
    last_err: Exception | None = None
    for chat_id in WITHDRAW_CHANNELS:
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                "salary channel post ok chat=%s message_id=%s",
                chat_id,
                getattr(msg, "message_id", None),
            )
            return msg, chat_id
        except Exception as e:
            last_err = e
            logger.warning("salary channel post failed chat=%s err=%r", chat_id, e)
    if last_err is not None:
        raise last_err
    raise RuntimeError("withdraw channel unavailable")


async def _resolve_salary_gift(db, row: dict) -> tuple[int, str, int]:
    """Подбирает gift_id по сумме, если владелец не указал подарок при назначении."""
    gift_id = int(row.get("gift_id") or 0)
    gift_emoji = (row.get("gift_emoji") or "⭐")[:16] or "⭐"
    has_upgrade = int(row.get("has_upgrade") or 0)
    if gift_id > 0:
        return gift_id, gift_emoji, has_upgrade
    amount = int(row["amount"])
    try:
        g = await db.pool.fetchrow(
            """
            SELECT gift_id, emoji, has_upgrade FROM star_gifts_cache
            WHERE stars = $1
            ORDER BY CASE WHEN source = 'live' THEN 0 ELSE 1 END, gift_id
            LIMIT 1
            """,
            amount,
        )
        if g:
            gift_id = int(g["gift_id"])
            gift_emoji = (g["emoji"] or gift_emoji)[:16] or gift_emoji
            has_upgrade = int(bool(g["has_upgrade"]))
            await db.pool.execute(
                """
                UPDATE staff_star_payouts
                SET gift_id = $2, gift_emoji = $3, has_upgrade = $4, updated_at = NOW()
                WHERE id = $1
                """,
                int(row["id"]), gift_id, gift_emoji, has_upgrade,
            )
            row["gift_id"] = gift_id
            row["gift_emoji"] = gift_emoji
            row["has_upgrade"] = has_upgrade
    except Exception:
        logger.exception("resolve salary gift failed payout=%s", row.get("id"))
    return gift_id, gift_emoji, has_upgrade


async def _post_salary_channel(
    bot,
    db,
    *,
    row: dict,
    first_name: str,
    build_keyboard: Callable[..., Any],
) -> int | None:
    """Пост в канал выводов как у игроков + явная пометка зарплаты администратора."""
    amount = int(row["amount"])
    user_id = int(row["user_id"])
    username = (row["stars_username"] or "").lstrip("@")
    rid = row.get("request_id") or f"salstar-{row['id']}"
    amount_str = "{:,.0f}".format(amount).replace(",", ".")
    name = escape(first_name or username or str(user_id))
    name_link = f'<a href="tg://user?id={user_id}">{name}</a>'
    gift_id, gift_emoji, has_upgrade = await _resolve_salary_gift(db, row)
    uname_txt = f" (@{escape(username)})" if username else ""

    channel_message = (
        f"<code>{escape(gift_emoji)}</code> "
        f"<b>{amount_str} кут в stars "
        f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji></b>\n"
        f"<b><tg-emoji emoji-id='5294026527850132517'>🍬</tg-emoji> "
        f"Для <i>{name_link}</i>{uname_txt}</b>\n"
        f"<b><tg-emoji emoji-id='5422818196031840237'>🌿</tg-emoji> "
        f"Заявка на выплату зарплаты администратору</b>\n\n"
        f"<blockquote><b>@CuteGamingBot</b></blockquote>"
    )

    keyboard = build_keyboard(
        request_id=str(rid),
        sender_user_id=user_id,
        sender_username=username,
        sender_first_name=first_name or "",
        recipient_user_id=user_id,
        recipient_username=username,
        recipient_first_name=first_name or "",
        amount=amount,
        result_flag="-",
        is_friend=False,
        channel_message_id_hint=0,
        gift_id=gift_id,
        gift_emoji=gift_emoji,
        has_upgrade=has_upgrade,
        extra={
            "is_salary": True,
            "star_payout_id": int(row["id"]),
            "salary_id": int(row["salary_id"]) if row.get("salary_id") else 0,
            "bonus_id": int(row["bonus_id"]) if row.get("bonus_id") else 0,
            "salary_source": row.get("source") or "salary",
        },
    )

    msg, _chat = await _send_withdraw_channel_message(
        bot,
        text=channel_message,
        reply_markup=keyboard,
    )
    return getattr(msg, "message_id", None)


async def process_one_payout(
    db,
    bot,
    fragment_client,
    seed_phrase: str,
    build_keyboard: Callable[..., Any],
    notify_user: Callable[[int, str], Awaitable[None]] | None = None,
) -> bool:
    """Обрабатывает одну queued-заявку. True если что-то взяли."""
    row = await _claim_next(db)
    if not row:
        return False

    payout_id = int(row["id"])
    method = (row.get("method") or "auto").lower()
    username = (row.get("stars_username") or "").lstrip("@")
    amount = int(row["amount"])
    user_id = int(row["user_id"])
    logger.info(
        "salary payout claim id=%s method=%s amount=%s user=%s username=%s",
        payout_id, method, amount, user_id, username,
    )
    print(
        f"[SALARY_STARS] claim id={payout_id} method={method} "
        f"amount={amount} user={user_id} @{username}"
    )

    first_name = ""
    try:
        fn = await db.pool.fetchval(
            "SELECT first_name FROM admin_accounts WHERE user_id = $1", user_id
        )
        first_name = fn or ""
    except Exception:
        pass

    async def do_channel(reason_prefix: str | None = None) -> None:
        """Пост в канал выводов с wdact — как заявка на вывод игрока."""
        try:
            mid = await _post_salary_channel(
                bot, db, row=row, first_name=first_name, build_keyboard=build_keyboard,
            )
        except Exception as e:
            logger.exception("salary channel post failed payout=%s", payout_id)
            await _mark(db, payout_id, "failed", error=f"channel post: {e}"[:400])
            if notify_user:
                await notify_user(
                    user_id,
                    (
                        f"<tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> "
                        f"<b>Не удалось отправить заявку зарплаты в канал</b>\n"
                        f"<code>{escape(str(e)[:200])}</code>\n"
                        f"<blockquote>Виво-Эпсилон</blockquote>"
                    ),
                )
            return
        await _mark(db, payout_id, "channel_pending",
                    error=reason_prefix, channel_message_id=mid)
        if notify_user:
            await notify_user(
                user_id,
                (
                    f"<tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> "
                    f"<b>Заявка на зарплату {amount}"
                    f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji> "
                    f"в канале выводов</b>\n"
                    f"<blockquote>Ожидайте подтверждения 👍 от владельца.\n"
                    f"Виво-Эпсилон</blockquote>"
                ),
            )

    try:
        # fragment — мгновенно через Fragment, без канала
        if method == "fragment":
            ok, txid, err = await _try_fragment(fragment_client, seed_phrase, username, amount)
            if ok:
                await _complete_salary_payment(db, row, txid or "fragment")
                await _mark(db, payout_id, "completed", txid=txid)
                try:
                    await _send_withdraw_channel_message(
                        bot,
                        text=(
                            f"<tg-emoji emoji-id='5395325195542078574'>🍀</tg-emoji> "
                            f"<b>Выплата зарплаты выполнена (Fragment)</b>\n"
                            f"<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
                            f"<b>{amount} кут в stars "
                            f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>\n\n"
                            f"<b><tg-emoji emoji-id='5294026527850132517'>🍬</tg-emoji> "
                            f"Для @{escape(username)}</b>\n"
                            f"<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> "
                            f"Зарплата администратора</b>\n\n"
                            f"<blockquote><b>@CuteGamingBot</b></blockquote>"
                        ),
                    )
                except Exception:
                    logger.exception("channel success log failed")
                if notify_user:
                    await notify_user(
                        user_id,
                        (
                            f"<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> "
                            f"<b>Зарплата {amount}"
                            f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji> "
                            f"отправлена на @{escape(username)}</b>\n"
                            f"<blockquote>Fragment · Виво-Эпсилон</blockquote>"
                        ),
                    )
                return True
            await _mark(db, payout_id, "failed", error=err)
            if notify_user:
                await notify_user(
                    user_id,
                    (
                        f"<tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> "
                        f"<b>Fragment: {escape(err or 'ошибка')}</b>\n"
                        f"<blockquote>Виво-Эпсилон</blockquote>"
                    ),
                )
            return True

        # auto / userbot — как вывод игрока: заявка в канал с кнопками 👎🥂👍
        await do_channel(
            reason_prefix="auto→channel" if method == "auto" else None,
        )
        return True
    except Exception as e:
        logger.exception("process star payout %s failed", payout_id)
        await _mark(db, payout_id, "failed", error=str(e)[:400])
        return True


async def staff_star_payout_loop(
    stop_event: asyncio.Event,
    db,
    bot,
    fragment_client,
    seed_phrase: str,
    build_keyboard: Callable[..., Any],
    notify_user: Callable[[int, str], Awaitable[None]] | None = None,
) -> None:
    """Раз в ~3 сек: health Fragment + каталог подарков + очередь зарплат → канал."""
    try:
        # Подхватить заявки, которые зависли / не ушли в канал
        await db.pool.execute(
            """
            UPDATE staff_star_payouts
            SET status = 'queued', error = NULL, updated_at = NOW()
            WHERE status IN ('failed', 'processing')
              AND created_at > NOW() - INTERVAL '72 hours'
            """
        )
        n_queued = await db.pool.fetchval(
            "SELECT COUNT(*) FROM staff_star_payouts WHERE status = 'queued'"
        )
        logger.info(
            "staff_star_payout_loop: started, queued=%s channels=%s",
            n_queued,
            WITHDRAW_CHANNELS,
        )
        print(
            f"✅ [SALARY_STARS] loop ready | queued={n_queued} "
            f"channels={WITHDRAW_CHANNELS}"
        )
    except Exception:
        logger.exception("startup requeue failed")

    ticks = 0
    while not stop_event.is_set():
        try:
            if ticks % 20 == 0:  # ~каждую минуту при sleep 3
                await refresh_fragment_health(db, fragment_client, seed_phrase)
                await refresh_star_gifts_cache(db, bot)
            # до 5 заявок за тик — быстрее уходит в канал
            for _ in range(5):
                got = await process_one_payout(
                    db, bot, fragment_client, seed_phrase, build_keyboard, notify_user,
                )
                if not got:
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("staff_star_payout_loop tick error")
        ticks += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
