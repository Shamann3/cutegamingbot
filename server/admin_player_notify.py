"""Сообщения игрокам от админки — Telegram DM через игрового бота."""

from __future__ import annotations

import html
from typing import Any

from user_notify import schedule_player_telegram_dm


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _send(user_id: int, text: str) -> None:
    schedule_player_telegram_dm(user_id, text)


def notify_market_listing_removed(
    user_id: int,
    *,
    listing_id: int,
    item_name: str,
    emoji: str,
    quantity: int,
    reason: str = "",
) -> None:
    lines = [
        "<b><tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> Лот снят с биржи</b>",
        f"Лот #{_esc(listing_id)} : {_esc(emoji)} {_esc(item_name)} ×{_esc(quantity)}",
        "<blockquote><b>Предметы возвращены в инвентарь.</b></blockquote>",
    ]
    reason_clean = (reason or "").strip()
    if reason_clean:
        lines.append(f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {_esc(reason_clean)}")
    _send(user_id, "\n".join(lines))


def notify_bulk_kut_grant(
    user_id: int,
    *,
    delta: int,
    balance_after: int,
    note: str = "",
) -> None:
    sign = "+" if delta > 0 else ""
    lines = [
        "<b><tg-emoji emoji-id='5391209710634433397'>🎁</tg-emoji> Ивент от Администрации</b>",
        f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> Баланс до : {sign}{_esc(delta)} кут",
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> Баланс после : {_esc(balance_after)} кут",
    ]
    note_clean = (note or "").strip()
    if note_clean:
        lines.append(f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {_esc(note_clean)}")
    _send(user_id, "\n".join(lines))


def notify_balance_adjustment(
    user_id: int,
    *,
    delta: int,
    balance_after: int,
    note: str,
) -> None:
    sign = "+" if delta > 0 else ""
    lines = [
        "<b><tg-emoji emoji-id='5391209710634433397'>🎁</tg-emoji> Изменение баланса</b>",
        f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> {sign}{_esc(delta)} кут",
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> Сейчас : {_esc(balance_after)} кут",
        f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {_esc(note.strip())}",
    ]
    _send(user_id, "\n".join(lines))


def notify_item_adjustment(
    user_id: int,
    *,
    item_name: str,
    emoji: str,
    delta: int,
    count_after: int,
    note: str,
) -> None:
    sign = "+" if delta > 0 else ""
    lines = [
        "<b><tg-emoji emoji-id='5319009880164570032'>🎒</tg-emoji> Изменение инвентаря</b>",
        f"<code>{_esc(emoji)}</code> {_esc(item_name)}: {sign}{_esc(delta)}",
        f"<tg-emoji emoji-id='4958506272551863292'>📊</tg-emoji> Сейчас : {_esc(count_after)}",
        f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {_esc(note.strip())}",
    ]
    _send(user_id, "\n".join(lines))


def notify_banned(user_id: int, *, reason: str = "") -> None:
    lines = ["<b><tg-emoji emoji-id='5260483378729208732'>⛔️</tg-emoji> Аккаунт заблокирован</b>"]
    reason_clean = (reason or "").strip()
    if reason_clean:
        lines.append(f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {_esc(reason_clean)}")
    else:
        lines.append("<blockquote><b>Обратитесь к администрации, если это ошибка.</b></blockquote>")
    _send(user_id, "\n".join(lines))


def notify_unbanned(user_id: int) -> None:
    _send(user_id, "<b><tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> Блокировка снята\nМожно снова играть.</b>")


def notify_onboarding_reset(user_id: int) -> None:
    _send(user_id, "<b><tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> Обучение сброшено\nПри следующем входе пройдёте его заново.</b>")
