from __future__ import annotations

import asyncio
import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from bot.config.config import (
    DATABASE_MODE,
    KING_STATS_INTERVAL_FORCE_NEW_ROUND,
    KING_STATS_PAYOUT_MODE,
    KING_STATS_PERIOD_KIND,
    KING_STATS_WORKER_INTERVAL_SEC,
)


_MSK_TZ = timezone(timedelta(hours=3))
_KING_WORKER_STARTED = False
_KING_WORKER_LOCK = asyncio.Lock()
_KING_WORKER_CFG = {
    "payout_mode": "period_change",
    "period_kind": "day",
    "interval_sec": 120,
    "interval_force_new_round": True,
}
_NO_EFFECT_CHAT_IDS: set[int] = set()

# Telegram visual effects (Barnum-style presentation).
_BARNUM_EFFECT_MAIN = "5046509860389126442"
_BARNUM_EFFECT_ALT = "5107584321108051014"

_PARTIAL_SUPPORT_LINK = "@CuteGamingSupportBot"


def _msk_today() -> date:
    return datetime.now(_MSK_TZ).date()


def _norm_payout_mode(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"period_change", "interval_seconds"}:
        return token
    return "period_change"


def _norm_period_kind(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"day", "week", "month"}:
        return token
    return "day"


def _safe_interval_sec(value: Any, default: int = 120) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(5, parsed)


def _to_msk_dt(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_MSK_TZ)


def _week_bounds(anchor: date) -> tuple[date, date]:
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_bounds(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    end = next_month - timedelta(days=1)
    return start, end


def _format_period_title(period_type: str, period_from: date, period_to: date) -> tuple[str, str]:
    token = _norm_period_kind(period_type)
    if token == "week":
        title = f"Царь недели {period_from.strftime('%d.%m')}–{period_to.strftime('%d.%m')}"
        label = f"неделя {period_from.strftime('%d.%m.%Y')} - {period_to.strftime('%d.%m.%Y')}"
        return title, label
    if token == "month":
        title = f"Царь месяца {period_from.strftime('%m.%Y')}"
        label = f"месяц {period_from.strftime('%m.%Y')}"
        return title, label
    title = f"Царь дня {period_from.strftime('%d.%m')}"
    label = f"день {period_from.strftime('%d.%m.%Y')}"
    return title, label


def _runtime_worker_cfg_snapshot() -> dict[str, Any]:
    interval = _safe_interval_sec(_KING_WORKER_CFG.get("interval_sec"), default=KING_STATS_WORKER_INTERVAL_SEC)
    # В test-режиме делаем более частые тики, чтобы можно было полноценно
    # проверить завершение конкурса и автовыплаты без долгого ожидания.
    if str(DATABASE_MODE or "").strip().lower() == "test":
        interval = min(interval, 10)
    payout_mode = _norm_payout_mode(_KING_WORKER_CFG.get("payout_mode"))
    period_kind = _norm_period_kind(_KING_WORKER_CFG.get("period_kind"))
    force_new_round = bool(_KING_WORKER_CFG.get("interval_force_new_round"))
    return {
        "interval_sec": interval,
        "payout_mode": payout_mode,
        "period_kind": period_kind,
        "interval_force_new_round": force_new_round,
    }


def resolve_current_king_context(
    *,
    payout_mode: str | None = None,
    period_kind: str | None = None,
    interval_sec: int | None = None,
    interval_force_new_round: bool | None = None,
    now_dt: datetime | None = None,
) -> dict[str, Any]:
    now = now_dt or datetime.now(_MSK_TZ)
    mode = _norm_payout_mode(payout_mode if payout_mode is not None else KING_STATS_PAYOUT_MODE)
    period = _norm_period_kind(period_kind if period_kind is not None else KING_STATS_PERIOD_KIND)
    interval = _safe_interval_sec(
        interval_sec if interval_sec is not None else KING_STATS_WORKER_INTERVAL_SEC,
        default=KING_STATS_WORKER_INTERVAL_SEC,
    )
    force_round = (
        bool(interval_force_new_round)
        if interval_force_new_round is not None
        else bool(KING_STATS_INTERVAL_FORCE_NEW_ROUND)
    )

    if mode == "period_change":
        if period == "day":
            period_from = now.date() - timedelta(days=1)
            period_to = period_from
            period_key = period_from.isoformat()
        elif period == "week":
            current_week_start, _ = _week_bounds(now.date())
            period_from = current_week_start - timedelta(days=7)
            period_to = period_from + timedelta(days=6)
            period_key = f"{period_from.isoformat()}..{period_to.isoformat()}"
        else:
            month_start = now.date().replace(day=1)
            period_to = month_start - timedelta(days=1)
            period_from = period_to.replace(day=1)
            period_key = period_from.strftime("%Y-%m")

        title, label = _format_period_title(period, period_from, period_to)
        return {
            "mode": mode,
            "period_type": period,
            "period_key": period_key,
            "period_from": period_from,
            "period_to": period_to,
            "stat_date": period_to,
            "count_day_win": period == "day",
            "title": title,
            "period_label": label,
        }

    # interval_seconds: используем текущий период, а при force_new_round
    # считаем каждый интервал отдельным раундом для быстрых тестов.
    if period == "day":
        period_from = now.date()
        period_to = period_from
        base_key = period_from.isoformat()
    elif period == "week":
        period_from, period_to = _week_bounds(now.date())
        base_key = f"{period_from.isoformat()}..{period_to.isoformat()}"
    else:
        period_from, period_to = _month_bounds(now.date())
        base_key = period_from.strftime("%Y-%m")

    round_suffix = ""
    if force_round:
        bucket_start = int(now.timestamp()) - (int(now.timestamp()) % interval)
        bucket_dt = datetime.fromtimestamp(bucket_start, tz=_MSK_TZ)
        round_suffix = bucket_dt.strftime("%Y%m%d%H%M%S")
        period_key = f"{period}:{round_suffix}"
    else:
        period_key = f"{period}:{base_key}"

    title, label = _format_period_title(period, period_from, period_to)
    if round_suffix:
        view_round = datetime.strptime(round_suffix, "%Y%m%d%H%M%S").strftime("%H:%M:%S")
        title = f"{title} • тест {view_round}"
        label = f"{label} (тест {view_round})"

    return {
        "mode": mode,
        "period_type": period,
        "period_key": period_key,
        "period_from": period_from,
        "period_to": period_to,
        "stat_date": now.date(),
        "count_day_win": False,
        "title": title,
        "period_label": label,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _reward_short(reward: dict[str, Any]) -> str:
    parts: list[str] = []
    kut = int(reward.get("kut") or 0)
    if kut > 0:
        parts.append(f"{kut} кут")
    for row in reward.get("items") or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("item_id") or "").strip()
        amount = int(row.get("amount") or 0)
        if item_id and amount > 0:
            parts.append(f"{item_id}x{amount}")
    return " + ".join(parts) if parts else "без награды"


def _display_name(user_id: int, names_bulk: dict[int, tuple[Any, Any]]) -> str:
    first_name, username = names_bulk.get(int(user_id), (None, None))
    if username:
        uname = str(username).strip().lstrip("@")
        if uname:
            return f"@{html.escape(uname)}"
    if first_name:
        return html.escape(str(first_name))
    return f"id{int(user_id)}"


def _chat_link_from_meta(meta: dict[str, Any]) -> str:
    chat_id = _safe_int(meta.get("chat_id"))
    name = html.escape(str(meta.get("namechat") or f"Группа {chat_id}"))
    chatlink = str(meta.get("chatlink") or "").strip()
    username = str(meta.get("usernamechat") or "").strip()
    if chatlink and chatlink.startswith("http"):
        safe_url = html.escape(chatlink, quote=True)
        return f"<a href='{safe_url}'>{name}</a>"
    if username and username.lower() != "username отсутствует":
        uname = username.lstrip("@")
        if uname:
            safe_url = html.escape(f"https://t.me/{uname}", quote=True)
            return f"<a href='{safe_url}'>{name}</a>"
    return f"{name} (<code>{chat_id}</code>)"


def _plain_text_from_html(text: str) -> str:
    raw = str(text or "")
    no_tags = re.sub(r"</?[^>]+>", "", raw)
    return html.unescape(no_tags)


async def _send_with_barnum_effect(bot, chat_id: int, text: str, *, effect_id: str = _BARNUM_EFFECT_MAIN) -> bool:
    chat_id_i = int(chat_id)
    can_try_effect = chat_id_i > 0 and chat_id_i not in _NO_EFFECT_CHAT_IDS
    try:
        payload = {
            "chat_id": chat_id_i,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if can_try_effect:
            payload["message_effect_id"] = effect_id
        await bot.send_message(**payload)
        return True
    except TypeError:
        # В старых aiogram параметр message_effect_id может отсутствовать.
        try:
            await bot.send_message(
                chat_id=chat_id_i,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            err = str(e).lower()
            if "can't parse entities" in err:
                try:
                    await bot.send_message(
                        chat_id=chat_id_i,
                        text=_plain_text_from_html(text),
                        disable_web_page_preview=True,
                    )
                    return True
                except Exception as plain_err:
                    print(f"[KING][SEND][WARN] chat_id={chat_id}: {type(plain_err).__name__}: {plain_err}")
                    return False
            print(f"[KING][SEND][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
            return False
    except Exception as e:
        err = str(e).lower()
        if "can't use message effects in the chat" in err:
            _NO_EFFECT_CHAT_IDS.add(chat_id_i)
        if "can't parse entities" in err:
            try:
                await bot.send_message(
                    chat_id=chat_id_i,
                    text=_plain_text_from_html(text),
                    disable_web_page_preview=True,
                )
                return True
            except Exception as plain_err:
                print(f"[KING][SEND][WARN] chat_id={chat_id}: {type(plain_err).__name__}: {plain_err}")
                return False
        try:
            await bot.send_message(
                chat_id=chat_id_i,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            print(f"[KING][SEND][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
            return False


async def _deduct_user_balance_up_to(db, user_id: int, amount: int) -> int:
    need = max(0, int(amount))
    if need <= 0:
        return 0

    total_deducted = 0
    for _ in range(6):
        remain = need - total_deducted
        if remain <= 0:
            break

        current_balance = _safe_int(await db.get_user_balance(int(user_id)), 0)
        candidate = min(remain, max(0, current_balance))
        if candidate <= 0:
            break

        result = await db.update_user_balance(int(user_id), f"-{candidate}")
        if result is None:
            # Мягкий retry на случай гонки баланса.
            await asyncio.sleep(0)
            continue
        total_deducted += int(candidate)

    return int(total_deducted)


def _allocate_partial_kut(winners: list[dict[str, Any]], available_kut: int) -> dict[int, int]:
    available = max(0, int(available_kut))
    planned_total = sum(max(0, _safe_int(w.get("planned_kut"), 0)) for w in winners)
    planned_by_uid = {int(w["user_id"]): max(0, _safe_int(w.get("planned_kut"), 0)) for w in winners}
    allocations: dict[int, int] = {int(w["user_id"]): 0 for w in winners}

    if available <= 0 or planned_total <= 0:
        return allocations
    if available >= planned_total:
        for w in winners:
            allocations[int(w["user_id"])] = max(0, _safe_int(w.get("planned_kut"), 0))
        return allocations

    fractional: list[tuple[float, int, int]] = []  # (fraction, place, user_id)
    distributed = 0
    for w in winners:
        uid = int(w["user_id"])
        place = int(w["place"])
        planned = max(0, _safe_int(w.get("planned_kut"), 0))
        if planned <= 0:
            allocations[uid] = 0
            continue
        raw = (available * planned) / planned_total
        base = min(planned, int(raw))
        allocations[uid] = base
        distributed += base
        fractional.append((raw - base, place, uid))

    remainder = max(0, available - distributed)
    for _, _, uid in sorted(fractional, key=lambda x: (-x[0], x[1])):
        if remainder <= 0:
            break
        planned_uid = planned_by_uid.get(uid, 0)
        if allocations[uid] >= planned_uid:
            continue
        allocations[uid] += 1
        remainder -= 1

    return allocations


async def _collect_kut_for_chat_rewards(
    db,
    *,
    source_chat_id: int,
    creator_id: int | None,
    required_kut: int,
) -> dict[str, Any]:
    required = max(0, int(required_kut))
    result = {
        "required_kut": required,
        "collected_kut": 0,
        "remaining_kut": required,
        "uses": [],
    }
    if required <= 0:
        return result

    # 1) Сначала баланс самой группы.
    group_spend = await db.deduct_chatbalance_up_to(source_chat_id, required)
    taken_from_group = _safe_int(group_spend.get("deducted"), 0)
    if taken_from_group > 0:
        source_meta = await db.get_chat_meta_basic(source_chat_id)
        result["uses"].append(
            {
                "type": "source_group",
                "chat_id": int(source_chat_id),
                "taken": taken_from_group,
                "meta": source_meta,
            }
        )
        result["collected_kut"] += taken_from_group
        result["remaining_kut"] = max(0, required - result["collected_kut"])

    if result["remaining_kut"] <= 0:
        return result

    if creator_id is None:
        return result

    creator_id_i = int(creator_id)

    # 2) Затем личный баланс создателя.
    from_creator_wallet = await _deduct_user_balance_up_to(db, creator_id_i, result["remaining_kut"])
    if from_creator_wallet > 0:
        result["uses"].append(
            {
                "type": "creator_wallet",
                "creator_id": creator_id_i,
                "taken": from_creator_wallet,
                "meta": None,
            }
        )
        result["collected_kut"] += from_creator_wallet
        result["remaining_kut"] = max(0, required - result["collected_kut"])

    if result["remaining_kut"] <= 0:
        return result

    # 3) Если не хватило — добираем с других групп создателя.
    creator_groups = await db.list_creator_groups_with_positive_balance(
        creator_id_i,
        exclude_chat_id=source_chat_id,
    )
    for grp in creator_groups:
        if result["remaining_kut"] <= 0:
            break

        chat_id = _safe_int(grp.get("chat_id"), 0)
        if not chat_id:
            continue

        spend = await db.deduct_chatbalance_up_to(chat_id, result["remaining_kut"])
        taken = _safe_int(spend.get("deducted"), 0)
        if taken <= 0:
            continue

        result["uses"].append(
            {
                "type": "creator_group",
                "chat_id": chat_id,
                "taken": taken,
                "meta": grp,
            }
        )
        result["collected_kut"] += taken
        result["remaining_kut"] = max(0, required - result["collected_kut"])

    return result


async def _notify_creator_about_funding(
    bot,
    *,
    creator_id: int,
    source_chat_meta: dict[str, Any],
    stat_date: date,
    period_label: str | None = None,
    funding_info: dict[str, Any],
) -> None:
    uses = funding_info.get("uses") or []
    winner_payouts = list(funding_info.get("winner_payouts") or [])
    if not uses and not winner_payouts:
        return

    period_view = html.escape(str(period_label or stat_date.strftime("%d.%m.%Y")))
    lines = [
        f"<tg-emoji emoji-id='5229011542011299168'>👑</tg-emoji> <b>Отчёт по выплатам «Царя статистики»</b>",
        f"<b><tg-emoji emoji-id='5472235990955334730'>👋</tg-emoji> Период : {period_view}</b>",
        f"<b><tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> Группа : {_chat_link_from_meta(source_chat_meta)}</b>",
        "",
    ]

    if winner_payouts:
        lines.append("Кто и что получил:")
        for row in winner_payouts:
            place = _safe_int(row.get("place"), 0)
            name_ref = str(row.get("name_ref") or f"id{_safe_int(row.get('user_id'), 0)}")
            messages = _safe_int(row.get("messages"), 0)
            planned_kut = _safe_int(row.get("planned_kut"), 0)
            actual_kut = _safe_int(row.get("actual_kut"), 0)
            items_partial = bool(row.get("items_partial"))
            reward_info = html.escape(str(row.get("reward_info") or "без награды"))
            partial_notes: list[str] = []
            if planned_kut > 0 and actual_kut < planned_kut:
                partial_notes.append(f"выплата {actual_kut}/{planned_kut} кут")
            if items_partial:
                partial_notes.append("предметы частично")

            partial_tail = f", {'; '.join(partial_notes)}" if partial_notes else ""
            if planned_kut > 0 and actual_kut < planned_kut:
                lines.append(
                    f"• {place} место : {name_ref} - {messages} сооб. "
                    f"(награда : {reward_info}{partial_tail})"
                )
            else:
                lines.append(
                    f"• {place} место : {name_ref} - {messages} сооб. "
                    f"(награда : {reward_info}{partial_tail})"
                )
        lines.append("")

    if uses:
        lines.append("Откуда были сняты куты:")
        for use in uses:
            taken = _safe_int(use.get("taken"), 0)
            if taken <= 0:
                continue
            use_type = str(use.get("type") or "")
            if use_type == "creator_wallet":
                lines.append(f"• С личного баланса: <b>{taken}</b> кут")
            elif use_type in {"creator_group", "source_group"}:
                meta = use.get("meta") or {}
                lines.append(f"• С {_chat_link_from_meta(meta)} : <b>{taken}</b> кут")
            else:
                lines.append(f"• Источник {html.escape(use_type)} : <b>{taken}</b> кут")
        lines.append("")
    else:
        lines.append("Откуда были сняты куты: списаний кут не было.")
        lines.append("")

    total = _safe_int(funding_info.get("collected_kut"), 0)
    remain = _safe_int(funding_info.get("remaining_kut"), 0)
    lines.append(f"Итого собрано на выплаты: <b>{total}</b> кут")
    if remain > 0:
        lines.append(f"Недостача: <b>{remain}</b> кут (выплата будет частичной)")
    if bool(funding_info.get("auto_disabled_no_funds")):
        lines.append("Система автоматически выключена: не хватает кут для полной выплаты.")

    sent = await _send_with_barnum_effect(bot, creator_id, "\n".join(lines), effect_id=_BARNUM_EFFECT_ALT)
    if sent:
        return

    # fallback: если ЛС закрыт, уведомляем в исходной группе.
    source_chat_id = _safe_int(source_chat_meta.get("chat_id"), 0)
    if source_chat_id:
        mention = f"<a href='tg://user?id={int(creator_id)}'>создателю</a>"
        await _send_with_barnum_effect(
            bot,
            source_chat_id,
            f"<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Не получилось отправить ЛС {mention} по списаниям выплат.</b>",
            effect_id=_BARNUM_EFFECT_ALT,
        )


async def _notify_creator_sources_breakdown(
    bot,
    *,
    creator_id: int,
    source_chat_meta: dict[str, Any],
    stat_date: date,
    period_label: str | None = None,
    funding_info: dict[str, Any],
) -> None:
    uses = list(funding_info.get("uses") or [])
    if not uses:
        return

    period_view = html.escape(str(period_label or stat_date.strftime("%d.%m.%Y")))
    lines = [
        "<tg-emoji emoji-id='5229011542011299168'>👑</tg-emoji> <b>С каких источников списаны куты</b>",
        f"<b><tg-emoji emoji-id='5472235990955334730'>👋</tg-emoji> Период : {period_view}</b>",
        f"<b><tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> Группа : {_chat_link_from_meta(source_chat_meta)}</b>",
        "",
    ]

    group_uses = [u for u in uses if str(u.get("type") or "") in {"source_group", "creator_group"}]
    wallet_uses = [u for u in uses if str(u.get("type") or "") == "creator_wallet"]

    if group_uses:
        lines.append("<b>С групп:</b>")
    for use in group_uses:
        taken = _safe_int(use.get("taken"), 0)
        if taken <= 0:
            continue
        meta = use.get("meta") or {}
        lines.append(f"• <tg-emoji emoji-id='5229011542011299168'>👑</tg-emoji> {_chat_link_from_meta(meta)}: <b>{taken}</b> кут")

    if wallet_uses:
        lines.append("")
        lines.append("<b>С личного баланса:</b>")
    for use in wallet_uses:
        taken = _safe_int(use.get("taken"), 0)
        if taken <= 0:
            continue
        lines.append(f"• <tg-emoji emoji-id='5397627572890668488'>🎅</tg-emoji> Личный баланс: <b>{taken}</b> кут")

    total = _safe_int(funding_info.get("collected_kut"), 0)
    lines.append("")
    lines.append(f"<b><tg-emoji emoji-id='5224257782013769471'>🧪</tg-emoji> Итого списано: {total} кут</b>")

    await _send_with_barnum_effect(
        bot,
        creator_id,
        "\n".join(lines),
        effect_id=_BARNUM_EFFECT_ALT,
    )


async def _notify_winner_partial(
    bot,
    *,
    user_id: int,
    source_chat_meta: dict[str, Any],
    place: int,
    planned_kut: int,
    actual_kut: int,
    stat_date: date,
    period_label: str | None = None,
) -> None:
    if actual_kut >= planned_kut:
        return

    group_ref = _chat_link_from_meta(source_chat_meta)
    label_view = html.escape(str(period_label or stat_date.strftime("%d.%m.%Y")))
    text = (
        f"<tg-emoji emoji-id='5229011542011299168'>👑</tg-emoji> <b>Частичная выплата по «Царю статистики»</b>\n"
        f"<b><tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> Группа : {group_ref}</b>\n"
        f"<b><tg-emoji emoji-id='5472235990955334730'>👋</tg-emoji> Период : {label_view}</b>\n"
        f"<b><tg-emoji emoji-id='5276089339967716971'>📣</tg-emoji> Место : {place}</b>\n"
        f"<b><tg-emoji emoji-id='5397627572890668488'>🎅</tg-emoji> Должно было прийти : {planned_kut}</b> кут\n"
        f"<b><tg-emoji emoji-id='5228947933545635555'>😫</tg-emoji> Фактически зачислено : {actual_kut}</b> кут\n\n"
        f"<b><tg-emoji emoji-id='5253478042256308885'>❤️</tg-emoji> Причина : в группе/у владельца не хватило средств для полной выплаты.</b>\n"
        f"<b><tg-emoji emoji-id='5425094988260188065'>💪</tg-emoji> Если нужно, можно подать жалобу : {_PARTIAL_SUPPORT_LINK}</b>"
    )
    await _send_with_barnum_effect(bot, user_id, text, effect_id=_BARNUM_EFFECT_ALT)


async def _load_king_top_rows(
    db,
    *,
    chat_id: int,
    period_type: str,
    period_from: date,
    period_to: date,
) -> tuple[list[Any], int]:
    if period_type == "day":
        day_str = period_from.strftime("%Y-%m-%d")
        top_rows_raw = await db.get_top_users_by_day(chat_id, day_str, limit=3)
        total_messages = int(await db.get_total_messages_by_day(chat_id, day_str) or 0)
        return list(top_rows_raw or []), total_messages

    start_str = period_from.strftime("%Y-%m-%d")
    end_str = period_to.strftime("%Y-%m-%d")
    top_rows_raw = await db.get_top_users_by_period(chat_id, start_str, end_str, limit=3)
    total_messages = int(await db.get_total_messages_by_period(chat_id, start_str, end_str) or 0)
    return list(top_rows_raw or []), total_messages


async def finalize_chat_king_day(
    db,
    bot,
    chat_id: int,
    stat_date: date,
    *,
    period_type: str = "day",
    period_key: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
    count_day_win: bool = True,
    period_title: str | None = None,
    period_label: str | None = None,
    allow_expired_run: bool = False,
) -> dict[str, Any]:
    chat_id = int(chat_id)
    period_type_s = _norm_period_kind(period_type)
    period_from_d = period_from or stat_date
    period_to_d = period_to or period_from_d
    if period_from_d > period_to_d:
        period_from_d, period_to_d = period_to_d, period_from_d

    default_title, default_label = _format_period_title(period_type_s, period_from_d, period_to_d)
    period_title_s = str(period_title or default_title)
    period_label_s = str(period_label or default_label)

    if period_key is not None:
        period_key_s = str(period_key).strip()
    elif period_type_s == "day":
        period_key_s = period_from_d.isoformat()
    else:
        period_key_s = f"{period_type_s}:{period_from_d.isoformat()}..{period_to_d.isoformat()}"
    if not period_key_s:
        return {"ok": False, "error": "empty_period_key"}

    await db.ensure_king_stats_schema()
    settings = await db.get_chat_king_reward_settings(chat_id)
    if not bool(settings.get("enabled")):
        return {"ok": True, "skipped": "disabled"}

    now_msk = datetime.now(_MSK_TZ)
    start_at_ts = _to_msk_dt(settings.get("start_at_ts"))
    if start_at_ts is not None and now_msk < start_at_ts:
        return {"ok": True, "skipped": "scheduled_not_started"}

    active_until_ts = _to_msk_dt(settings.get("active_until_ts"))
    if active_until_ts is not None and now_msk >= active_until_ts and not bool(allow_expired_run):
        try:
            await db.set_chat_king_enabled(
                chat_id,
                False,
                creator_id=int(settings.get("creator_id")) if settings.get("creator_id") is not None else None,
            )
        except Exception:
            pass
        return {"ok": True, "skipped": "expired"}

    if await db.has_chat_king_period_result(chat_id, period_type_s, period_key_s):
        return {"ok": True, "skipped": "already_processed"}

    min_messages = max(0, int(settings.get("min_messages") or 0))
    top_rows_raw, total_messages = await _load_king_top_rows(
        db,
        chat_id=chat_id,
        period_type=period_type_s,
        period_from=period_from_d,
        period_to=period_to_d,
    )

    top_rows: list[tuple[int, int]] = []
    for row in top_rows_raw:
        try:
            uid = int(row["user_id"])
            cnt = int(row["total_messages"] or 0)
        except Exception:
            continue
        if min_messages <= 0 or cnt >= min_messages:
            top_rows.append((uid, cnt))

    winner_id = top_rows[0][0] if top_rows else None
    top_json = [{"user_id": uid, "messages": cnt} for uid, cnt in top_rows]
    created = await db.create_chat_king_period_result(
        chat_id=chat_id,
        stat_date=stat_date,
        period_type=period_type_s,
        period_key=period_key_s,
        period_from=period_from_d,
        period_to=period_to_d,
        winner_user_id=winner_id,
        top_rows=top_json,
        total_messages=total_messages,
    )
    if not created:
        return {"ok": True, "skipped": "already_processed"}

    source_meta = await db.get_chat_meta_basic(chat_id)
    creator_id = settings.get("creator_id")
    if creator_id is None:
        creator_id = await db.get_group_creator(chat_id)
    creator_id = int(creator_id) if creator_id is not None else None

    winners: list[dict[str, Any]] = []
    for idx, (uid, msg_cnt) in enumerate(top_rows[:3], start=1):
        reward_plan = settings.get(f"place_{idx}") or {}
        winners.append(
            {
                "user_id": int(uid),
                "place": int(idx),
                "messages": int(msg_cnt),
                "planned_kut": max(0, int(reward_plan.get("kut") or 0)),
                "planned_items": list(reward_plan.get("items") or []),
            }
        )

    item_alloc_result = {
        "ok": True,
        "alloc_by_user": {},
        "missing_by_user": {},
    }
    try:
        if hasattr(db, "allocate_creator_item_rewards"):
            item_alloc_result = await db.allocate_creator_item_rewards(
                creator_id=creator_id,
                winners=winners,
            )
    except Exception as e:
        item_alloc_result = {
            "ok": False,
            "error": str(e),
            "alloc_by_user": {},
            "missing_by_user": {},
        }
        print(f"[KING][ITEM-ALLOC][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
    item_alloc_by_user: dict[int, list[dict[str, Any]]] = {
        int(uid): list(rows)
        for uid, rows in (item_alloc_result.get("alloc_by_user") or {}).items()
    }
    item_missing_by_user: dict[int, list[dict[str, Any]]] = {
        int(uid): list(rows)
        for uid, rows in (item_alloc_result.get("missing_by_user") or {}).items()
    }

    total_required_kut = sum(int(w["planned_kut"]) for w in winners)
    funding = await _collect_kut_for_chat_rewards(
        db,
        source_chat_id=chat_id,
        creator_id=creator_id,
        required_kut=total_required_kut,
    )
    collected_kut = int(funding.get("collected_kut") or 0)
    kut_alloc = _allocate_partial_kut(winners, collected_kut)
    is_partial = collected_kut < total_required_kut

    names_bulk = await db.get_names_bulk([w["user_id"] for w in winners])
    winner_payouts: list[dict[str, Any]] = []
    place_badges = {1: "<tg-emoji emoji-id='5280735858926822987'>🥇</tg-emoji>", 2: "<tg-emoji emoji-id='5283195573812340110'>🥈</tg-emoji>", 3: "<tg-emoji emoji-id='5282750778409233531'>🥉</tg-emoji>"}
    summary_lines = [f"<tg-emoji emoji-id='5425094988260188065'>💪</tg-emoji> <b>{html.escape(period_title_s)}</b>"]
    if min_messages > 0:
        summary_lines.append(f"<tg-emoji emoji-id='5397627572890668488'>🎅</tg-emoji> <b>Порог : {min_messages} сообщений</b>")
    else:
        summary_lines.append("<tg-emoji emoji-id='5397627572890668488'>🎅</tg-emoji> <b>Порог : выкл</b>")

    if not winners:
        if min_messages > 0:
            summary_lines.append("Никто не прошёл порог.")
        else:
            summary_lines.append("За период нет активных сообщений.")
    else:
        for w in winners:
            uid = int(w["user_id"])
            place = int(w["place"])
            planned_kut = int(w["planned_kut"])
            actual_kut = int(kut_alloc.get(uid, 0))
            planned_items = list(w["planned_items"] or [])
            items = list(item_alloc_by_user.get(uid, []))
            missing_items = list(item_missing_by_user.get(uid, []))

            reward_payload = {"kut": actual_kut, "items": items}
            award = await db.award_chat_king_reward(
                chat_id=chat_id,
                stat_date=stat_date,
                user_id=uid,
                place=place,
                reward_payload=reward_payload,
                details_extra={
                    "period_type": period_type_s,
                    "period_key": period_key_s,
                    "period_from": period_from_d.isoformat(),
                    "period_to": period_to_d.isoformat(),
                    "planned_kut": planned_kut,
                    "planned_items": planned_items,
                    "partial": bool(actual_kut < planned_kut),
                    "items_partial": bool(missing_items),
                    "missing_items": missing_items,
                    "source_chat_id": chat_id,
                    "funding_collected_kut": collected_kut,
                    "funding_required_kut": total_required_kut,
                    "funding_uses": funding.get("uses") or [],
                },
                period_type=period_type_s,
                period_key=period_key_s,
            )

            if place == 1 and bool(count_day_win) and period_type_s == "day":
                # Учитываем "царя дня" только в дневном зачёте и только в боевом ритме.
                try:
                    await db.increment_user_day_king_win(user_id=uid, stat_date=stat_date, chat_id=chat_id)
                except Exception as e:
                    print(f"[KING][WIN-COUNT][WARN] uid={uid}: {type(e).__name__}: {e}")

            name_ref = _display_name(uid, names_bulk)
            reward_info = _reward_short({"kut": actual_kut, "items": items})
            winner_payouts.append(
                {
                    "user_id": uid,
                    "place": place,
                    "messages": int(w["messages"]),
                    "name_ref": name_ref,
                    "planned_kut": planned_kut,
                    "actual_kut": actual_kut,
                    "reward_info": reward_info,
                    "items_partial": bool(missing_items),
                    "missing_items": missing_items,
                }
            )
            place_badge = place_badges.get(place, f"{place}.")
            reward_info_view = html.escape(reward_info)
            partial_flags: list[str] = []
            if planned_kut > 0 and actual_kut < planned_kut:
                partial_flags.append(f"<b>выплата : {actual_kut}/{planned_kut} кут</b>")
            if missing_items:
                partial_flags.append("предметы частично")

            if partial_flags:
                summary_lines.append(
                    f"<b>{place_badge} {name_ref} - {w['messages']} сообщений </b>"
                    f"<b>(награда : {reward_info_view}, {', '.join(partial_flags)})</b>"
                )
            else:
                summary_lines.append(
                    f"<b>{place_badge} {name_ref} - {w['messages']} сообщений (награда : {reward_info_view})</b>"
                )

            if planned_kut > actual_kut:
                await _notify_winner_partial(
                    bot,
                    user_id=uid,
                    source_chat_meta=source_meta,
                    place=place,
                    planned_kut=planned_kut,
                    actual_kut=actual_kut,
                    stat_date=stat_date,
                    period_label=period_label_s,
                )

            if not award.get("ok"):
                print(
                    f"[KING][AWARD][WARN] chat_id={chat_id} uid={uid} place={place} "
                    f"error={award.get('error')}"
                )
                if actual_kut > 0:
                    try:
                        refunded = await db.add_to_chatbalance(bot, chat_id, actual_kut)
                        print(
                            f"[KING][AWARD][REFUND] chat_id={chat_id} uid={uid} "
                            f"kut={actual_kut} refunded={bool(refunded)}"
                        )
                    except Exception as refund_err:
                        print(
                            f"[KING][AWARD][REFUND][WARN] chat_id={chat_id} uid={uid} "
                            f"kut={actual_kut} err={type(refund_err).__name__}: {refund_err}"
                        )
                if items and creator_id is not None:
                    for item_row in items:
                        item_name = str(item_row.get("item_id") or "").strip()
                        item_amount = max(0, int(item_row.get("amount") or 0))
                        if not item_name or item_amount <= 0:
                            continue
                        try:
                            await db.set_items(int(creator_id), item_name, item_amount)
                        except Exception as item_refund_err:
                            print(
                                f"[KING][AWARD][REFUND][ITEM][WARN] chat_id={chat_id} uid={uid} "
                                f"item={item_name} amount={item_amount} "
                                f"err={type(item_refund_err).__name__}: {item_refund_err}"
                            )

    # Не отправляем "пустой" отчёт, если за период вообще нет активности.
    # Результат периода при этом уже сохранён (create_chat_king_period_result),
    # поэтому повторной отправки не будет.
    if not winners and int(total_messages) <= 0:
        return {
            "ok": True,
            "chat_id": chat_id,
            "stat_date": stat_date.isoformat(),
            "period_type": period_type_s,
            "period_key": period_key_s,
            "period_from": period_from_d.isoformat(),
            "period_to": period_to_d.isoformat(),
            "winner_user_id": winner_id,
            "top_count": len(top_rows),
            "announced": False,
            "required_kut": total_required_kut,
            "collected_kut": collected_kut,
            "partial": is_partial,
            "auto_disabled_no_funds": False,
            "skipped": "no_activity",
        }

    if is_partial and total_required_kut > 0:
        summary_lines.append("")
        summary_lines.append(
            f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Выплата частичная : удалось собрать {collected_kut}/{total_required_kut} кут.</b>"
        )
        summary_lines.append(f"<b><tg-emoji emoji-id='5229163064162525129'>😟</tg-emoji> У создателя группы не хватило денег на выплату за активность царей статистики. Если есть вопросы по выплате : {_PARTIAL_SUPPORT_LINK}</b>")

    auto_disabled_no_funds = False

    summary_lines.append(f"<tg-emoji emoji-id='5467470746215292572'>🕶️</tg-emoji> <b>Всего сообщений : {total_messages}</b>")

    text = "\n".join(summary_lines)
    sent_ok = await _send_with_barnum_effect(bot, chat_id, text, effect_id=_BARNUM_EFFECT_MAIN)

    if sent_ok:
        await db.mark_chat_king_period_announced(chat_id, period_type_s, period_key_s)

    if creator_id is not None:
        funding["winner_payouts"] = winner_payouts
        funding["auto_disabled_no_funds"] = auto_disabled_no_funds
        funding["item_alloc_ok"] = bool(item_alloc_result.get("ok", True))
        funding["item_missing_by_user"] = item_missing_by_user
        await _notify_creator_about_funding(
            bot,
            creator_id=creator_id,
            source_chat_meta=source_meta,
            stat_date=stat_date,
            period_label=period_label_s,
            funding_info=funding,
        )
        await _notify_creator_sources_breakdown(
            bot,
            creator_id=creator_id,
            source_chat_meta=source_meta,
            stat_date=stat_date,
            period_label=period_label_s,
            funding_info=funding,
        )

    return {
        "ok": True,
        "chat_id": chat_id,
        "stat_date": stat_date.isoformat(),
        "period_type": period_type_s,
        "period_key": period_key_s,
        "period_from": period_from_d.isoformat(),
        "period_to": period_to_d.isoformat(),
        "winner_user_id": winner_id,
        "top_count": len(top_rows),
        "announced": sent_ok,
        "required_kut": total_required_kut,
        "collected_kut": collected_kut,
        "partial": is_partial,
        "auto_disabled_no_funds": auto_disabled_no_funds,
    }


async def run_king_stats_tick(db, bot) -> dict[str, Any]:
    await db.ensure_king_stats_schema()
    cfg = _runtime_worker_cfg_snapshot()
    try:
        chat_profiles = await db.list_enabled_chat_king_profiles()
    except Exception:
        chat_ids_fallback = await db.list_chat_ids_with_king_enabled()
        chat_profiles = [{"chat_id": int(cid), "period_kind": cfg["period_kind"]} for cid in chat_ids_fallback]

    processed = 0
    last_context: dict[str, Any] | None = None
    now_msk = datetime.now(_MSK_TZ)
    for profile in chat_profiles:
        chat_id = int(profile.get("chat_id") or 0)
        if not chat_id:
            continue
        chat_period_kind = _norm_period_kind(profile.get("period_kind") or cfg["period_kind"])
        start_at_ts = _to_msk_dt(profile.get("start_at_ts"))
        active_until_ts = _to_msk_dt(profile.get("active_until_ts"))

        # Если задана дата старта и она ещё не наступила — пропускаем.
        if start_at_ts is not None and now_msk < start_at_ts:
            continue

        # Если задан срок конкурса, то выплата выполняется в момент его завершения
        # (однократно), после чего система для группы выключается.
        if active_until_ts is not None:
            if now_msk < active_until_ts:
                continue

            end_context = resolve_current_king_context(
                payout_mode="interval_seconds",
                period_kind=chat_period_kind,
                interval_sec=cfg["interval_sec"],
                interval_force_new_round=False,
                now_dt=active_until_ts,
            )
            contest_end_key = f"contest_end:{active_until_ts.strftime('%Y%m%d%H%M%S')}"
            last_context = end_context
            should_disable = False
            try:
                result = await finalize_chat_king_day(
                    db=db,
                    bot=bot,
                    chat_id=int(chat_id),
                    stat_date=end_context["stat_date"],
                    period_type=end_context["period_type"],
                    period_key=contest_end_key,
                    period_from=end_context["period_from"],
                    period_to=end_context["period_to"],
                    count_day_win=end_context["count_day_win"],
                    period_title=end_context["title"],
                    period_label=end_context["period_label"],
                    allow_expired_run=True,
                )
                should_disable = bool(result.get("ok"))
                if result.get("ok") and not result.get("skipped"):
                    processed += 1
            except Exception as e:
                print(f"[KING][TICK][END][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
            if should_disable:
                try:
                    await db.set_chat_king_enabled(int(chat_id), False)
                except Exception:
                    pass
            continue

        # Авто-финализация только по завершению реального периода (day/week/month).
        # Интервальный режим не должен отправлять отчёты "просто так".
        context = resolve_current_king_context(
            payout_mode="period_change",
            period_kind=chat_period_kind,
            interval_sec=cfg["interval_sec"],
            interval_force_new_round=cfg["interval_force_new_round"],
        )
        last_context = context
        try:
            result = await finalize_chat_king_day(
                db=db,
                bot=bot,
                chat_id=int(chat_id),
                stat_date=context["stat_date"],
                period_type=context["period_type"],
                period_key=context["period_key"],
                period_from=context["period_from"],
                period_to=context["period_to"],
                count_day_win=context["count_day_win"],
                period_title=context["title"],
                period_label=context["period_label"],
            )
            if result.get("ok") and not result.get("skipped"):
                processed += 1
        except Exception as e:
            print(f"[KING][TICK][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")

    return {
        "ok": True,
        "stat_date": (last_context["stat_date"].isoformat() if last_context else _msk_today().isoformat()),
        "period_type": (last_context["period_type"] if last_context else cfg["period_kind"]),
        "period_key": (last_context["period_key"] if last_context else ""),
        "mode": cfg["payout_mode"],
        "default_period_kind": cfg["period_kind"],
        "total_enabled_chats": len(chat_profiles),
        "processed": processed,
    }


def start_king_stats_worker(
    db,
    bot,
    *,
    interval_sec: int | None = None,
    payout_mode: str | None = None,
    period_kind: str | None = None,
    interval_force_new_round: bool | None = None,
) -> None:
    global _KING_WORKER_STARTED
    if _KING_WORKER_STARTED:
        return
    _KING_WORKER_CFG["interval_sec"] = _safe_interval_sec(
        interval_sec if interval_sec is not None else KING_STATS_WORKER_INTERVAL_SEC,
        default=KING_STATS_WORKER_INTERVAL_SEC,
    )
    _KING_WORKER_CFG["payout_mode"] = _norm_payout_mode(
        payout_mode if payout_mode is not None else KING_STATS_PAYOUT_MODE
    )
    _KING_WORKER_CFG["period_kind"] = _norm_period_kind(
        period_kind if period_kind is not None else KING_STATS_PERIOD_KIND
    )
    _KING_WORKER_CFG["interval_force_new_round"] = (
        bool(interval_force_new_round)
        if interval_force_new_round is not None
        else bool(KING_STATS_INTERVAL_FORCE_NEW_ROUND)
    )

    _KING_WORKER_STARTED = True

    async def _loop() -> None:
        while True:
            try:
                async with _KING_WORKER_LOCK:
                    await run_king_stats_tick(db, bot)
            except Exception as e:
                print(f"[KING][LOOP][WARN] {type(e).__name__}: {e}")
            cfg_now = _runtime_worker_cfg_snapshot()
            await asyncio.sleep(int(cfg_now["interval_sec"]))

    asyncio.create_task(_loop())
    cfg = _runtime_worker_cfg_snapshot()
    print(
        "[KING] ✅ worker started "
        f"(mode={cfg['payout_mode']}, default_period={cfg['period_kind']}, interval={cfg['interval_sec']}s, "
        f"force_round={bool(cfg['interval_force_new_round'])})"
    )

