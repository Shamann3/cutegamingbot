from __future__ import annotations

import re
import html as _html
import time
import ast
from datetime import date, datetime, timedelta, timezone
from typing import Any

from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from bot.db_create.pklcode import LazyGameStore

from bot.config.config import (
    KING_STATS_INTERVAL_FORCE_NEW_ROUND,
    KING_STATS_PAYOUT_MODE,
    KING_STATS_PERIOD_KIND,
    KING_STATS_WORKER_INTERVAL_SEC,
)
from bot.runtime.king_stats_worker import finalize_chat_king_day, resolve_current_king_context


_BARNUM_EFFECT_MAIN = "5046509860389126442"
_MSK_TZ = timezone(timedelta(hours=3))

_RU_MONTHS: dict[str, int] = {
    "январь": 1,
    "января": 1,
    "февраль": 2,
    "февраля": 2,
    "март": 3,
    "марта": 3,
    "апрель": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июнь": 6,
    "июня": 6,
    "июль": 7,
    "июля": 7,
    "август": 8,
    "августа": 8,
    "сентябрь": 9,
    "сентября": 9,
    "октябрь": 10,
    "октября": 10,
    "ноябрь": 11,
    "ноября": 11,
    "декабрь": 12,
    "декабря": 12,
}

_FOREVER_TOKENS = {
    "навсегда",
    "всегда",
    "бессрочно",
    "forever",
    "permanent",
}


def _norm_text(text: str | None) -> str:
    normalized = " ".join((text or "").strip().lower().split())
    normalized = re.sub(r"^[^0-9a-zа-яё]+", "", normalized, flags=re.IGNORECASE)
    return normalized


def _contains_any(text: str, parts: tuple[str, ...]) -> bool:
    return any(part in text for part in parts)


def _is_king_context(text: str) -> bool:
    if not text:
        return False
    if text.startswith("царь") or text.startswith("king"):
        return True
    if _contains_any(text, ("царь статист", "царя статист", "система царя статист", "king stats")):
        return True
    return _contains_any(text, ("царь", "царя", "king")) and _contains_any(text, ("стат", "statistics"))


def is_king_stats_command(text: str | None) -> bool:
    normalized = _norm_text(text)
    if not _is_king_context(normalized):
        return False
    if normalized.startswith("царь") or normalized.startswith("king"):
        return True
    return _contains_any(
        normalized,
        (
            "система",
            "меню",
            "панель",
            "управл",
            "включ",
            "выключ",
            "отключ",
            "деактив",
            "настрой",
            "наград",
            "порог",
            "мин",
            "период",
            "режим",
            "срок",
            "дата",
            "баланс",
            "распредел",
            "обнов",
            "подвед",
            "итог",
            "финал",
            "очист",
            "предмет",
            "кут",
            "помощ",
            "хелп",
            "help",
        ),
    )


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
            parts.append(f"{item_id} x{amount}")
    return " + ".join(parts) if parts else "не задано"


def _period_human(period_kind: str | None) -> str:
    token = str(period_kind or "").strip().lower()
    mapping = {
        "day": "день",
        "week": "неделя",
        "month": "месяц",
    }
    return mapping.get(token, "день")


def _to_msk_dt(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_MSK_TZ)


def _format_dt_short(value: datetime | None) -> str:
    dt = _to_msk_dt(value)
    if dt is None:
        return "не задано"
    return dt.strftime("%d.%m.%Y %H:%M")


def _duration_human(settings: dict[str, Any]) -> str:
    active_until = _to_msk_dt(settings.get("active_until_ts"))
    if active_until is None:
        return "навсегда"
    now = datetime.now(_MSK_TZ)
    if now >= active_until:
        return "истёк"
    return f"до {active_until.strftime('%d.%m.%Y %H:%M')}"


def _start_human(settings: dict[str, Any]) -> str:
    start_at = _to_msk_dt(settings.get("start_at_ts"))
    if start_at is None:
        return "сразу"
    return start_at.strftime("%d.%m.%Y %H:%M")


def _status_human(enabled: Any) -> str:
    return "включен" if bool(enabled) else "выключен"


def _settings_text(settings: dict[str, Any]) -> str:
    status = "ON" if bool(settings.get("enabled")) else "OFF"
    min_messages = max(0, int(settings.get("min_messages") or 0))
    period_kind = _period_human(settings.get("period_kind"))
    duration_view = _duration_human(settings)
    start_view = _start_human(settings)
    r1 = _reward_short(settings.get("place_1") or {})
    r2 = _reward_short(settings.get("place_2") or {})
    r3 = _reward_short(settings.get("place_3") or {})
    min_view = str(min_messages) if min_messages > 0 else "выкл"
    return (
        "<b><tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> Царь статистики</b>\n"
        f"<b>Статус : {status} | Период : {period_kind} | Мин : {min_view}</b>\n"
        f"<b>Старт : {start_view} | Срок : {duration_view}</b>\n"
        f"<tg-emoji emoji-id='5280735858926822987'>🥇</tg-emoji> <b>{r1}</b>\n"
        f"<tg-emoji emoji-id='5287582088336264294'>🥈</tg-emoji> <b>{r2}</b>\n"
        f"<tg-emoji emoji-id='5287277338931779754'>🥉</tg-emoji> <b>{r3}</b>"
    )


_HELP_TEXT = (
    "<b><tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> Царь статистики</b>\n"
    "Напишите : <code>система царя статистики</code>\n"
    "Дальше только кнопки : период, срок, дата старта, минимум, награды.\n"
    "Ручной ввод после кнопки «вручную»:\n"
    "• кут: <code>500</code>\n"
    "• предмет : <code>🚬 1</code>\n\n"
    "Срок системы: <code>30 мин</code>, <code>12 часов</code>, <code>2 месяца</code>, <code>навсегда</code>\n"
    "Старт с даты: <code>16.07.2026</code>, <code>16 июня</code>, <code>16 июня 2026</code>\n"
    "Если задан срок — выплата будет в конце конкурса (в test тоже).\n"
    "Распределение кут: бюджет -> 3 суммы -> «Все в порядке»\n"
    "Сброс: кнопка «Сбросить все настройки».\n"
    "Ожидание ручного ввода : 120 сек.\n"
    "Если формат неверный — бот даст кнопку «Отмена ввода».\n"
    "Минимум сообщений: кнопки 0/10/30/50 или свой.\n"
    "Кнопки работают только у создателя, который открыл меню."
)


_KING_MENU_PREFIX = "kingm"
_KING_STRICT_INLINE_ONLY = True
_KING_PENDING_INPUT_TIMEOUT_SEC = 120
# Состояние меню персистентное: контейнер перезапускается ежечасно, и без
# этого меню в ЛС умирало бы у пользователей по нескольку раз в день.
#
# ВАЖНО про ключи: GameStore._canon_key приводит ключ к str, поэтому кортеж
# (-100123, 456) лежит в сторе как строка '(-100123, 456)'. Чтение и запись
# тем же кортежем работают (канонизация двусторонняя), но ПЕРЕБОР стора
# отдаёт строки, а не кортежи. Поэтому прямой перебор запрещён: доступ только
# через хелперы ниже, а где перебор неизбежен (_clear_pending_input) -
# сравнение идёт через _pending_key_matches, понимающий оба вида ключа.
#
# Персистентность безопасна только вместе с исправлением
# _force_reload_from_redis_once в pklcode (мердж снапшота с памятью вместо
# clear()): иначе дебаунс записи 1000 мс против кулдауна перезалива 350 мс
# снова начнёт терять pending-ввод.

# (panel_chat_id, user_id) -> payload ожидания ручного ввода
_KING_PENDING_INPUTS: dict[tuple[int, int], dict[str, Any]] = LazyGameStore("_KING_PENDING_INPUTS")
# (panel_chat_id, message_id) -> user_id, кто открыл меню
_KING_MENU_OWNERS: dict[tuple[int, int], int] = LazyGameStore("_KING_MENU_OWNERS")
# (panel_chat_id, message_id) -> (text, signature), антидубль при edit_message_text
_KING_MENU_RENDER_STATE: dict[
    tuple[int, int],
    tuple[str, tuple[tuple[tuple[str, str, str, str, str], ...], ...]],
] = LazyGameStore("_KING_MENU_RENDER_STATE")
# (panel_chat_id, message_id) -> group_chat_id, какую группу настраивает это меню
_KING_MENU_TARGET: dict[tuple[int, int], int] = LazyGameStore("_KING_MENU_TARGET")
# (user_id, group_chat_id) -> message_id последнего меню этой группы в ЛС
_KING_DM_LAST_MENU: dict[tuple[int, int], int] = LazyGameStore("_KING_DM_LAST_MENU")

# Сообщение меню висит в чате неделями, а записи в сторе по умолчанию
# протухают через DEFAULT_EXPIRY_SECONDS = 7200 (2 часа). Именно поэтому
# «Меню устарело» вылезало у людей, которые никуда не уходили: сообщение на
# месте, а привязка к нему уже вычищена уборщиком. Держим привязки 30 дней.
# Ожидание ввода не трогаем: у него свой таймаут 120 секунд.
_KING_MENU_BINDING_TTL_SEC = 30 * 24 * 60 * 60


def _tune_menu_store_ttl() -> None:
    for store in (_KING_MENU_OWNERS, _KING_MENU_TARGET,
                  _KING_MENU_RENDER_STATE, _KING_DM_LAST_MENU):
        try:
            backing = store._load()
            if int(getattr(backing, "expiry_seconds", 0) or 0) < _KING_MENU_BINDING_TTL_SEC:
                backing.expiry_seconds = _KING_MENU_BINDING_TTL_SEC
                backing._rebuild_expire_heap()
        except Exception as tune_error:
            print(f"⚠️ [KING][TTL] не смог настроить срок хранения: "
                  f"{type(tune_error).__name__}: {tune_error}")


_tune_menu_store_ttl()


def _kc(*parts: Any) -> str:
    return ":".join([_KING_MENU_PREFIX, *[str(p) for p in parts]])


def _is_king_menu_open_intent(text: str) -> bool:
    if _contains_any(
        text,
        (
            "включ",
            "выключ",
            "отключ",
            "деактив",
            "наград",
            "кут",
            "предмет",
            "порог",
            "мин ",
            "миним",
            "период",
            "обнов",
            "подвед",
            "итог",
            "финал",
            "очист",
        ),
    ):
        return False
    if text in {
        "система царя статистики",
        "система царь статистики",
        "меню царя статистики",
        "панель царя статистики",
        "настройка царя статистики",
        "настройки царя статистики",
    }:
        return True
    return (
        _is_king_context(text)
        and _contains_any(text, ("система", "меню", "панель", "настрой"))
        and _contains_any(text, ("откры", "покажи", "настрой", "управл", "система"))
    )


def _group_line_text(group_button: tuple[str, str] | None) -> str:
    if not group_button:
        return ""
    name, url = group_button
    safe_name = _html.escape(str(name or "Группа"))
    safe_url = _html.escape(str(url or ""), quote=True)
    if not safe_url:
        return f"<b>Группа:</b> {safe_name}"
    return f"<b>Группа:</b> <a href='{safe_url}'>{safe_name}</a>"


def _king_menu_text(
    settings: dict[str, Any],
    *,
    group_button: tuple[str, str] | None = None,
) -> str:
    base = _settings_text(settings)
    group_line = _group_line_text(group_button)
    if not group_line:
        return base
    return f"{base}\n{group_line}"


def _safe_button_text(text: str, *, max_len: int = 56) -> str:
    value = str(text or "").strip()
    if not value:
        return "Открыть группу"
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def _normalize_tg_url(raw: Any) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return value
    if lowered.startswith("t.me/") or lowered.startswith("telegram.me/"):
        return f"https://{value}"
    if value.startswith("@"):
        value = value[1:].strip()
    if re.fullmatch(r"[A-Za-z0-9_]{4,}", value or ""):
        return f"https://t.me/{value}"
    return None


def _resolve_group_url(chat_id: int, meta: dict[str, Any] | None) -> str | None:
    meta = meta or {}
    from_link = _normalize_tg_url(meta.get("chatlink"))
    if from_link:
        return from_link

    username = str(meta.get("usernamechat") or "").strip()
    if username and username.lower() not in {"username отсутствует", "none", "null"}:
        from_username = _normalize_tg_url(username)
        if from_username:
            return from_username

    chat_id_s = str(int(chat_id))
    if chat_id_s.startswith("-100") and len(chat_id_s) > 4:
        return f"https://t.me/c/{chat_id_s[4:]}/1"
    if chat_id_s.startswith("-"):
        return f"https://t.me/c/{str(abs(int(chat_id)))}"
    return None


async def _resolve_group_menu_button(db, chat_id: int) -> tuple[str, str] | None:
    context = await _resolve_group_menu_context(db, chat_id)
    return context.get("button")


async def _resolve_group_menu_context(db, chat_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {"button": None, "balance": 0}
    if db is None or not hasattr(db, "get_chat_meta_basic"):
        return result
    try:
        meta = await db.get_chat_meta_basic(int(chat_id))
    except Exception:
        return result
    if not isinstance(meta, dict):
        meta = {}
    result["balance"] = max(0, int(meta.get("chatbalance") or 0))
    url = _resolve_group_url(int(chat_id), meta)
    if not url:
        return result
    name = str(meta.get("namechat") or "").strip() or f"Группа {int(chat_id)}"
    result["button"] = (_safe_button_text(name), url)
    return result


def _king_menu_keyboard(
    settings: dict[str, Any],
    *,
    group_button: tuple[str, str] | None = None,
    group_balance: int | None = None,
) -> types.InlineKeyboardMarkup:
    enabled = bool(settings.get("enabled"))
    period_kind = str(settings.get("period_kind") or "day")
    balance_view = max(0, int(group_balance or 0))
    duration_view = _duration_human(settings)
    start_view = _start_human(settings)
    on_icon = "5339112148175959615" if enabled else "5339113303522161846"
    off_icon = "5339113303522161846" if enabled else "5337017423906226569"
    period_active_icon = "5260463209562776385"
    period_inactive_icon = "5339113303522161846"
    day_icon = period_active_icon if period_kind == "day" else period_inactive_icon
    week_icon = period_active_icon if period_kind == "week" else period_inactive_icon
    month_icon = period_active_icon if period_kind == "month" else period_inactive_icon

    rows: list[list[types.InlineKeyboardButton]] = []
    rows.append(
        [
            types.InlineKeyboardButton(
                text=f"Баланс группы : {balance_view} кут",
                callback_data=_kc("noop"),
                style="default",
                icon_custom_emoji_id="5224257782013769471",
            )
        ]
    )

    rows.extend(
        [
            [
                types.InlineKeyboardButton(
                    text="Вкл",
                    callback_data=_kc("toggle", "on"),
                    style="default",
                    icon_custom_emoji_id=on_icon,
                ),
                types.InlineKeyboardButton(
                    text="Выкл",
                    callback_data=_kc("toggle", "off"),
                    style="default",
                    icon_custom_emoji_id=off_icon,
                ),
            ],
            [types.InlineKeyboardButton(text="Статистика за :", callback_data=_kc("noop"), style="default")],
            [
                types.InlineKeyboardButton(
                    text="День",
                    callback_data=_kc("period", "day"),
                    style="default",
                    icon_custom_emoji_id=day_icon,
                ),
                types.InlineKeyboardButton(
                    text="Неделя",
                    callback_data=_kc("period", "week"),
                    style="default",
                    icon_custom_emoji_id=week_icon,
                ),
                types.InlineKeyboardButton(
                    text="Месяц",
                    callback_data=_kc("period", "month"),
                    style="default",
                    icon_custom_emoji_id=month_icon,
                ),
            ],
            [types.InlineKeyboardButton(text="Награды за :", callback_data=_kc("noop"), style="default")],
            [
                types.InlineKeyboardButton(
                    text="1 место",
                    callback_data=_kc("place", "1"),
                    style="default",
                    icon_custom_emoji_id="5280735858926822987",
                ),
                types.InlineKeyboardButton(
                    text="2 место",
                    callback_data=_kc("place", "2"),
                    style="default",
                    icon_custom_emoji_id="5287582088336264294",
                ),
                types.InlineKeyboardButton(
                    text="3 место",
                    callback_data=_kc("place", "3"),
                    style="default",
                    icon_custom_emoji_id="5287277338931779754",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="Минимальное количество сообщений",
                    callback_data=_kc("min", "custom"),
                    style="default",
                    icon_custom_emoji_id="5222108309795908493",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=f"Срок системы : {duration_view}",
                    callback_data=_kc("duration", "custom"),
                    style="default",
                    icon_custom_emoji_id="5411520005386806155",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=f"Старт с даты : {start_view}",
                    callback_data=_kc("start", "custom"),
                    style="default",
                    icon_custom_emoji_id="5454409660473827001",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Распределить куты",
                    callback_data=_kc("budget", "alloc"),
                    style="default",
                    icon_custom_emoji_id="5258500400918587241",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Сбросить все настройки",
                    callback_data=_kc("reset", "all"),
                    style="default",
                    icon_custom_emoji_id="5253529465899739917",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Обновить сообщение",
                    callback_data=_kc("open"),
                    style="default",
                    icon_custom_emoji_id="5454409660473827001",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Подвести итоги",
                    callback_data=_kc("finalize"),
                    style="default",
                    icon_custom_emoji_id="5411520005386806155",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Закрыть",
                    callback_data=_kc("close"),
                    style="default",
                    icon_custom_emoji_id="5256110225848543598",
                )
            ],
        ]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _king_place_text(settings: dict[str, Any], place: int) -> str:
    reward = settings.get(f"place_{int(place)}") or {}
    return (
        f"<b><tg-emoji emoji-id='5409008750893734809'>🏆</tg-emoji> Место {place}</b>\n"
        f"<b>Сейчас : {_reward_short(reward)}</b>\n"
        "<b>Выберите, что получит победитель.</b>"
    )


def _king_place_keyboard(
    settings: dict[str, Any],
    place: int,
    *,
    show_input_cancel: bool = False,
) -> types.InlineKeyboardMarkup:
    p = int(place)
    reward = settings.get(f"place_{p}") or {}
    has_kut = int(reward.get("kut") or 0) > 0
    has_items = any(
        isinstance(row, dict) and int(row.get("amount") or 0) > 0 and str(row.get("item_id") or "").strip()
        for row in (reward.get("items") or [])
    )

    kut_title = "Награда в кутах"
    item_title = "Награда в предметах"
    if has_items and not has_kut:
        kut_title = "+Награда в кутах"
    if has_kut and not has_items:
        item_title = "+Награда в предметах"

    rows: list[list[types.InlineKeyboardButton]] = [
        [
            types.InlineKeyboardButton(
                text=kut_title,
                callback_data=_kc("place", p, "kut", "custom"),
                style="default",
                icon_custom_emoji_id="5258500400918587241",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=item_title,
                callback_data=_kc("place", p, "item", "custom"),
                style="default",
                icon_custom_emoji_id="5463172695132745432",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="Очистить",
                callback_data=_kc("place", p, "clear"),
                style="default",
                icon_custom_emoji_id="5253529465899739917",
            )
        ],
    ]
    if show_input_cancel:
        rows.append(
            [
                types.InlineKeyboardButton(
                    text="Отмена ввода",
                    callback_data=_kc("input", "cancel"),
                    style="default",
                    icon_custom_emoji_id="5305605746795225897",
                ),
                types.InlineKeyboardButton(text="В меню", callback_data=_kc("open"), style="default"),
            ]
        )
    else:
        rows.append([types.InlineKeyboardButton(text="В меню", callback_data=_kc("open"), style="default")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _pending_cancel_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Отмена ввода",
                    callback_data=_kc("input", "cancel"),
                    style="default",
                    icon_custom_emoji_id="5305605746795225897",
                )
            ]
        ]
    )


def _budget_confirm_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Все в порядке",
                    callback_data=_kc("budget", "confirm"),
                    style="default",
                    icon_custom_emoji_id="5411520005386806155",
                )
            ],
            list(_pending_cancel_keyboard().inline_keyboard[0]),
        ]
    )


def _king_menu_keyboard_with_pending_cancel(
    settings: dict[str, Any],
    *,
    group_button: tuple[str, str] | None = None,
    group_balance: int | None = None,
) -> types.InlineKeyboardMarkup:
    # По UX-требованию: в главном меню не показываем "Отмена ввода".
    return _king_menu_keyboard(settings, group_button=group_button, group_balance=group_balance)


def _main_menu_keyboard_for_user(
    settings: dict[str, Any],
    chat_id: int,
    user_id: int,
    *,
    group_button: tuple[str, str] | None = None,
    group_balance: int | None = None,
) -> types.InlineKeyboardMarkup:
    # Главная панель всегда без кнопки отмены ввода.
    return _king_menu_keyboard(settings, group_button=group_button, group_balance=group_balance)


def _help_keyboard_for_user(panel_chat_id: int, user_id: int) -> types.InlineKeyboardMarkup:
    rows: list[list[types.InlineKeyboardButton]] = [
        [types.InlineKeyboardButton(text="Назад", callback_data=_kc("open"), style="default")]
    ]
    if _get_pending_input(panel_chat_id, user_id) is not None:
        rows.append(list(_pending_cancel_keyboard().inline_keyboard[0]))
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


async def _resolve_item_name_for_reward(db, token: str) -> tuple[str | None, str]:
    raw = str(token or "").strip()
    if not raw:
        return None, ""
    try:
        if hasattr(db, "resolve_dex_item_token"):
            resolved = await db.resolve_dex_item_token(raw)
            if resolved and str(resolved.get("name") or "").strip():
                return str(resolved.get("name")).strip(), str(resolved.get("emoji") or "")
    except Exception:
        pass

    try:
        if hasattr(db, "get_item_name_by_emoji_use"):
            name = await db.get_item_name_by_emoji_use(raw)
            if name:
                return str(name), raw
    except Exception:
        pass

    try:
        if hasattr(db, "get_item_info_use"):
            info = await db.get_item_info_use(raw)
            if info and info.get("name"):
                return str(info.get("name")), str(info.get("emoji") or "")
    except Exception:
        pass

    return None, ""


def is_king_stats_callback(data: Any) -> bool:
    return isinstance(data, str) and data.startswith(f"{_KING_MENU_PREFIX}:")


def _pending_key(chat_id: int, user_id: int) -> tuple[int, int]:
    return int(chat_id), int(user_id)


def _menu_key(chat_id: int, message_id: int) -> tuple[int, int]:
    return int(chat_id), int(message_id)


def _store_discard(store: Any, key: Any) -> None:
    try:
        if key in store:
            del store[key]
    except Exception:
        pass


def _pending_key_matches(raw_key: Any, chat_id: int, user_id: int) -> bool:
    try:
        if isinstance(raw_key, tuple) and len(raw_key) == 2:
            return int(raw_key[0]) == int(chat_id) and int(raw_key[1]) == int(user_id)
    except Exception:
        pass
    raw = str(raw_key or "").strip()
    if not raw:
        return False
    if raw == str((int(chat_id), int(user_id))):
        return True
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, tuple) and len(parsed) == 2:
            return int(parsed[0]) == int(chat_id) and int(parsed[1]) == int(user_id)
    except Exception:
        pass
    return False


def _parse_pair_key(raw_key: Any) -> tuple[int, int] | None:
    """
    Ключи-кортежи хранятся в сторе как строки ('(555, 104)'), поэтому перебор
    отдаёт str. Возвращает пару чисел или None.
    """
    if isinstance(raw_key, tuple) and len(raw_key) == 2:
        try:
            return int(raw_key[0]), int(raw_key[1])
        except Exception:
            return None
    try:
        parsed = ast.literal_eval(str(raw_key or "").strip())
        if isinstance(parsed, tuple) and len(parsed) == 2:
            return int(parsed[0]), int(parsed[1])
    except Exception:
        pass
    return None


def _recover_menu_binding(message_id: int, user_id: int) -> int | None:
    """
    Восстанавливает группу для сообщения-меню, если привязка потерялась
    (сброс Redis, вытеснение). Ищем по обратной карте «последнее меню группы
    в ЛС»: ключ (user_id, group_chat_id) -> message_id.
    """
    target_message_id = int(message_id)
    target_user_id = int(user_id)
    try:
        for raw_key in list(_KING_DM_LAST_MENU):
            pair = _parse_pair_key(raw_key)
            if pair is None or pair[0] != target_user_id:
                continue
            try:
                stored_message_id = int(_KING_DM_LAST_MENU.get(raw_key) or 0)
            except Exception:
                continue
            if stored_message_id == target_message_id:
                return pair[1]
    except Exception as recover_error:
        print(f"⚠️ [KING][RECOVER] перебор не удался: "
              f"{type(recover_error).__name__}: {recover_error}")
    return None


def _button_signature(button: Any) -> tuple[str, str, str, str, str]:
    text = str(getattr(button, "text", "") or "")
    callback_data = str(getattr(button, "callback_data", "") or "")
    url = str(getattr(button, "url", "") or "")
    style = str(getattr(button, "style", "") or "")
    icon_custom_emoji_id = str(getattr(button, "icon_custom_emoji_id", "") or "")
    return text, callback_data, url, style, icon_custom_emoji_id


def _markup_signature(markup: Any) -> tuple[tuple[tuple[str, str, str, str, str], ...], ...]:
    rows = getattr(markup, "inline_keyboard", None) or []
    normalized_rows: list[tuple[tuple[str, str, str, str, str], ...]] = []
    for row in rows:
        row_sig = tuple(_button_signature(btn) for btn in (row or []))
        normalized_rows.append(row_sig)
    return tuple(normalized_rows)


def _plain_text_from_html(text: str) -> str:
    raw = str(text or "")
    no_tags = re.sub(r"</?[^>]+>", "", raw)
    return _html.unescape(no_tags)


def _remember_menu_state(chat_id: int, message_id: int, text: str, reply_markup: Any) -> None:
    _KING_MENU_RENDER_STATE[_menu_key(chat_id, message_id)] = (
        str(text or ""),
        _markup_signature(reply_markup),
    )


def _is_same_menu_state(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Any,
    *,
    current_message: types.Message | None = None,
) -> bool:
    key = _menu_key(chat_id, message_id)
    desired_text = str(text or "")
    desired_markup = _markup_signature(reply_markup)
    cached = _KING_MENU_RENDER_STATE.get(key)
    if cached and cached[0] == desired_text and cached[1] == desired_markup:
        return True

    if current_message is not None:
        current_plain = str(getattr(current_message, "text", "") or getattr(current_message, "caption", "") or "")
        desired_plain = _plain_text_from_html(desired_text)
        current_markup = _markup_signature(getattr(current_message, "reply_markup", None))
        if current_plain == desired_plain and current_markup == desired_markup:
            _remember_menu_state(chat_id, message_id, desired_text, reply_markup)
            return True
    return False


def _bind_menu_owner(chat_id: int, message_id: int, owner_user_id: int) -> None:
    _KING_MENU_OWNERS[_menu_key(chat_id, message_id)] = int(owner_user_id)


def _get_menu_owner(chat_id: int, message_id: int) -> int | None:
    value = _KING_MENU_OWNERS.get(_menu_key(chat_id, message_id))
    return int(value) if value is not None else None


def _unbind_menu_owner(panel_chat_id: int, message_id: int) -> None:
    key = _menu_key(panel_chat_id, message_id)
    _store_discard(_KING_MENU_OWNERS, key)
    _store_discard(_KING_MENU_RENDER_STATE, key)
    _store_discard(_KING_MENU_TARGET, key)


def _bind_menu_target(panel_chat_id: int, message_id: int, group_chat_id: int) -> None:
    """Запоминает, какую ГРУППУ настраивает меню, лежащее в panel_chat_id."""
    _KING_MENU_TARGET[_menu_key(panel_chat_id, message_id)] = int(group_chat_id)


def _get_menu_target(panel_chat_id: int, message_id: int) -> int | None:
    value = _KING_MENU_TARGET.get(_menu_key(panel_chat_id, message_id))
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _bind_menu_message(
    panel_chat_id: int,
    message_id: int,
    owner_user_id: int,
    group_chat_id: int,
) -> None:
    """Полная привязка сообщения-меню: владелец + целевая группа."""
    _bind_menu_owner(panel_chat_id, message_id, owner_user_id)
    _bind_menu_target(panel_chat_id, message_id, group_chat_id)


def _dm_menu_key(user_id: int, group_chat_id: int) -> tuple[int, int]:
    return int(user_id), int(group_chat_id)


def _remember_dm_menu(user_id: int, group_chat_id: int, message_id: int) -> None:
    _KING_DM_LAST_MENU[_dm_menu_key(user_id, group_chat_id)] = int(message_id)


def _get_dm_last_menu(user_id: int, group_chat_id: int) -> int | None:
    value = _KING_DM_LAST_MENU.get(_dm_menu_key(user_id, group_chat_id))
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _set_pending_input(
    panel_chat_id: int,
    user_id: int,
    payload: dict[str, Any],
    *,
    group_chat_id: int,
) -> None:
    data = dict(payload or {})
    # Группа, которую настраиваем, обязана ехать внутри payload: в ЛС её
    # неоткуда взять из самого сообщения пользователя.
    data["group_chat_id"] = int(group_chat_id)
    data["expires_at"] = int(time.time()) + int(_KING_PENDING_INPUT_TIMEOUT_SEC)
    _KING_PENDING_INPUTS[_pending_key(panel_chat_id, user_id)] = data


def _pending_group_chat_id(payload: dict[str, Any] | None, fallback: int) -> int:
    if isinstance(payload, dict):
        try:
            value = payload.get("group_chat_id")
            if value is not None:
                return int(value)
        except Exception:
            pass
    return int(fallback)


def _pending_seconds_left(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    expires_at = int(payload.get("expires_at") or 0)
    if expires_at <= 0:
        return int(_KING_PENDING_INPUT_TIMEOUT_SEC)
    return max(0, expires_at - int(time.time()))


def _get_pending_input(chat_id: int, user_id: int) -> dict[str, Any] | None:
    key = _pending_key(chat_id, user_id)
    payload = _KING_PENDING_INPUTS.get(key)
    if not isinstance(payload, dict):
        return None
    expires_at = int(payload.get("expires_at") or 0)
    if expires_at <= 0:
        payload = dict(payload)
        payload["expires_at"] = int(time.time()) + int(_KING_PENDING_INPUT_TIMEOUT_SEC)
        _KING_PENDING_INPUTS[key] = payload
        return payload
    if int(time.time()) >= expires_at:
        _store_discard(_KING_PENDING_INPUTS, key)
        return None
    return payload


def _clear_pending_input(chat_id: int, user_id: int) -> None:
    target_chat = int(chat_id)
    target_user = int(user_id)
    _store_discard(_KING_PENDING_INPUTS, _pending_key(target_chat, target_user))
    try:
        for raw_key in list(_KING_PENDING_INPUTS):
            if _pending_key_matches(raw_key, target_chat, target_user):
                _store_discard(_KING_PENDING_INPUTS, raw_key)
    except Exception:
        pass


def _is_valid_pending_payload_for_type(pending_type: str, raw_text: str) -> bool:
    text = str(raw_text or "").strip()
    normalized = _norm_text(text)
    if pending_type == "min_custom":
        if normalized in {"выкл", "off", "откл", "нет", "none"}:
            return True
        return re.fullmatch(r"\d{1,5}", text) is not None
    if pending_type == "duration_custom":
        if normalized in _FOREVER_TOKENS:
            return True
        return re.fullmatch(r"\d{1,9}\s*[a-zа-яё.]*", normalized) is not None
    if pending_type == "start_date_custom":
        if normalized in {"сразу", "сейчас", "now", "today", "выкл", "off", "none"}:
            return True
        if re.search(r"\d", normalized) and (
            "." in normalized
            or "-" in normalized
            or "/" in normalized
            or any(m in normalized for m in _RU_MONTHS.keys())
        ):
            return True
        return False
    if pending_type == "budget_total_custom":
        return re.search(r"\d", text) is not None
    if pending_type == "budget_split_custom":
        return len(re.findall(r"\d{1,12}", text)) >= 3
    if pending_type == "budget_confirm":
        return False
    if pending_type == "place_kut_custom":
        return re.fullmatch(r"\d{1,12}", text) is not None
    if pending_type == "place_item_custom":
        return re.fullmatch(r".+\s+\d{1,9}", text) is not None
    return False


def _should_route_pending_input_message(message: types.Message, pending: dict[str, Any] | None) -> bool:
    if not isinstance(pending, dict):
        return False

    raw_text = str(getattr(message, "text", "") or "").strip()
    if not raw_text:
        return False

    normalized = _norm_text(raw_text)
    if normalized in {"отмена", "cancel", "стоп"}:
        return True
    if is_king_stats_command(raw_text):
        return True

    pending_type = str(pending.get("type") or "").strip().lower()
    if _is_valid_pending_payload_for_type(pending_type, raw_text):
        return True

    panel_message_id = int(pending.get("panel_message_id") or 0)
    reply_to = getattr(message, "reply_to_message", None)
    reply_to_message_id = int(getattr(reply_to, "message_id", 0) or 0)
    return panel_message_id > 0 and reply_to_message_id == panel_message_id


def has_king_stats_pending_input(message: types.Message) -> bool:
    try:
        pending = _get_pending_input(int(message.chat.id), int(message.from_user.id))
        return _should_route_pending_input_message(message, pending)
    except Exception:
        return False


async def _reply_barnum(
    message: types.Message,
    text: str,
    *,
    reply_markup: types.InlineKeyboardMarkup | None = None,
) -> types.Message | None:
    chat_id = int(message.chat.id)
    can_use_effect = chat_id > 0
    try:
        payload = {
            "chat_id": message.chat.id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_to_message_id": message.message_id,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if can_use_effect:
            payload["message_effect_id"] = _BARNUM_EFFECT_MAIN
        return await message.bot.send_message(**payload)
    except Exception as primary_error:
        print(f"⚠️ [KING][SEND] основная отправка не прошла: {type(primary_error).__name__}: {primary_error}")
        try:
            return await message.reply(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        except Exception as fallback_error:
            # Раньше здесь была полная тишина: пользователь не получал ничего
            # и в логе тоже ничего не оставалось.
            print(f"🔥 [KING][SEND] запасная отправка тоже упала: {type(fallback_error).__name__}: {fallback_error}")
            return None


async def _resolve_bot_mention(bot) -> str:
    """@username бота для подсказки «запустите бота». Без имени - нейтральный текст."""
    try:
        me = await bot.get_me()
        username = str(getattr(me, "username", "") or "").strip()
        if username:
            return f"@{username}"
    except Exception:
        pass
    return "бота"


async def _reply_pending_input_error(
    message: types.Message,
    user_id: int,
    pending: dict[str, Any] | None,
    text: str,
    *,
    group_chat_id: int,
) -> types.Message | None:
    left_sec = _pending_seconds_left(pending)
    details = (
        f"{text}\n"
        f"<b>Осталось : {left_sec} сек.</b>\n"

    )
    markup = _pending_cancel_keyboard()
    sent = await _reply_barnum(message, details, reply_markup=markup)
    if sent is not None:
        panel_chat_id = int(sent.chat.id)
        message_id = int(sent.message_id)
        # У сообщения есть кнопка «Отмена ввода», значит по нему прилетит
        # колбэк - и ему нужна привязка к группе, иначе клик отвалится.
        _bind_menu_message(panel_chat_id, message_id, int(user_id), int(group_chat_id))
        _remember_menu_state(panel_chat_id, message_id, details, markup)
    return sent


async def _send_bound_menu_message(
    message: types.Message,
    settings: dict[str, Any],
    owner_user_id: int,
    *,
    group_chat_id: int,
    text: str | None = None,
    db=None,
    group_button: tuple[str, str] | None = None,
    group_balance: int | None = None,
) -> None:
    """Отвечает меню в том же чате, куда пришло сообщение (в новом потоке - ЛС)."""
    resolved_group_button = group_button
    resolved_group_balance = group_balance
    if resolved_group_button is None or resolved_group_balance is None:
        context = await _resolve_group_menu_context(db, int(group_chat_id))
        if resolved_group_button is None:
            resolved_group_button = context.get("button")
        if resolved_group_balance is None:
            resolved_group_balance = int(context.get("balance") or 0)
    desired_text = text or _king_menu_text(settings, group_button=resolved_group_button)
    desired_markup = _main_menu_keyboard_for_user(
        settings,
        int(group_chat_id),
        int(owner_user_id),
        group_button=resolved_group_button,
        group_balance=resolved_group_balance,
    )
    sent = await _reply_barnum(
        message,
        desired_text,
        reply_markup=desired_markup,
    )
    if sent is not None:
        panel_chat_id = int(sent.chat.id)
        message_id = int(sent.message_id)
        _bind_menu_message(panel_chat_id, message_id, int(owner_user_id), int(group_chat_id))
        _remember_menu_state(panel_chat_id, message_id, desired_text, desired_markup)
        _remember_dm_menu(int(owner_user_id), int(group_chat_id), message_id)


async def _deliver_menu_to_dm(message: types.Message, db, bot, *, group_chat_id: int) -> bool:
    """
    Команда пришла в группе: шлём меню в ЛС и отвечаем в группе.
    Всегда возвращает True - сообщение обработано в любом исходе.
    """
    user_id = int(message.from_user.id)
    if not await _ensure_creator_permissions(message, db, bot, group_chat_id=int(group_chat_id)):
        return True

    sent = await _open_menu_in_dm(bot, db, group_chat_id=int(group_chat_id), user_id=user_id)
    if sent is None:
        mention = await _resolve_bot_mention(bot)
        await _reply_barnum(
            message,
            "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> "
            "<b>Не могу написать вам в личные сообщения.</b>\n"
            f"<b>Откройте {_html.escape(mention)}, нажмите «Запустить», "
            "затем напишите эту команду в группе ещё раз.</b>",
        )
        return True

    await _reply_barnum(
        message,
        "<tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> "
        "<b>Настройки отправлены вам в личные сообщения.</b>",
    )
    return True


async def _open_menu_in_dm(bot, db, *, group_chat_id: int, user_id: int) -> types.Message | None:
    """
    Присылает меню настроек группы в ЛС пользователю.

    None - Telegram не даёт боту писать первым (пользователь не запускал бота
    или заблокировал его). Предыдущее меню ЭТОЙ ЖЕ группы удаляется, меню
    других групп остаются жить.
    """
    settings = await db.get_chat_king_reward_settings(int(group_chat_id))
    context = await _resolve_group_menu_context(db, int(group_chat_id))
    group_button = context.get("button")
    group_balance = int(context.get("balance") or 0)

    desired_text = _king_menu_text(settings, group_button=group_button)
    desired_markup = _main_menu_keyboard_for_user(
        settings,
        int(group_chat_id),
        int(user_id),
        group_button=group_button,
        group_balance=group_balance,
    )

    try:
        sent = await bot.send_message(
            chat_id=int(user_id),
            text=desired_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=desired_markup,
        )
    except TelegramForbiddenError:
        return None
    except Exception:
        return None

    if sent is None:
        return None

    # Старое меню этой же группы больше не нужно: иначе в ЛС копятся дубли,
    # каждый со своим состоянием отрисовки.
    previous_message_id = _get_dm_last_menu(int(user_id), int(group_chat_id))
    if previous_message_id and int(previous_message_id) != int(sent.message_id):
        await _delete_menu_message_by_id(bot, int(user_id), int(previous_message_id))

    panel_chat_id = int(sent.chat.id)
    message_id = int(sent.message_id)
    _bind_menu_message(panel_chat_id, message_id, int(user_id), int(group_chat_id))
    _remember_menu_state(panel_chat_id, message_id, desired_text, desired_markup)
    _remember_dm_menu(int(user_id), int(group_chat_id), message_id)
    return sent


async def _is_group_creator(db, bot, group_chat_id: int, user_id: int) -> tuple[bool, str | None]:
    """
    Единая проверка прав на ГРУППУ: (можно, причина_отказа).
    Принимает group_chat_id явно, потому что вызывается и из группы, и из ЛС,
    где чат сообщения группой не является.
    """
    try:
        await db.update_chat_creator_if_owner(bot, int(user_id), int(group_chat_id))
    except Exception:
        pass

    creator_id = await db.get_group_creator(int(group_chat_id))
    if creator_id is None:
        return False, "Не удалось определить создателя группы."
    if int(creator_id) != int(user_id):
        return False, "Только создатель группы."
    return True, None


async def _ensure_creator_permissions(message: types.Message, db, bot, *, group_chat_id: int) -> bool:
    ok, reason = await _is_group_creator(db, bot, int(group_chat_id), int(message.from_user.id))
    if ok:
        return True
    await _reply_barnum(
        message,
        "<tg-emoji emoji-id='5260483378729208732'>⛔️</tg-emoji> "
        f"<b>{_html.escape(reason or 'Нет доступа.')}</b>",
    )
    return False


async def _ensure_creator_permissions_callback(
    call: types.CallbackQuery, db, bot, *, group_chat_id: int
) -> bool:
    ok, reason = await _is_group_creator(db, bot, int(group_chat_id), int(call.from_user.id))
    if ok:
        return True
    await call.answer(reason or "Нет доступа.", show_alert=True)
    return False


async def _resolve_menu_callback_group(call: types.CallbackQuery, db, bot) -> int | None:
    """
    Проверяет права на клик и возвращает ГРУППУ, которую настраивает это меню.
    None - клик отклонён, пользователю уже отвечено.

    Порядок важен: сначала дешёвые проверки без БД (владелец, привязка),
    и только потом поход в БД за создателем.
    """
    msg = getattr(call, "message", None)
    if msg is None or getattr(msg, "chat", None) is None:
        await call.answer("Сообщение недоступно.", show_alert=True)
        return None

    panel_chat_id = int(msg.chat.id)
    message_id = int(msg.message_id)
    user_id = int(call.from_user.id)

    owner_id = _get_menu_owner(panel_chat_id, message_id)
    group_chat_id = _get_menu_target(panel_chat_id, message_id)

    # Привязка могла потеряться, хотя сообщение живо. Прежде чем отвечать
    # «Меню устарело», пробуем восстановить её по обратной карте.
    if owner_id is None or group_chat_id is None:
        recovered_group = _recover_menu_binding(message_id, user_id)
        if recovered_group is not None:
            print(f"♻️ [KING][RECOVER] восстановил привязку {panel_chat_id}/{message_id} "
                  f"-> группа {recovered_group}, владелец {user_id}")
            owner_id = user_id
            group_chat_id = recovered_group
            _bind_menu_message(panel_chat_id, message_id, user_id, recovered_group)

    if owner_id is None:
        await call.answer("Меню устарело. Откройте его командой в группе.", show_alert=True)
        return None
    if owner_id != user_id:
        await call.answer("Это меню открыл другой пользователь.", show_alert=True)
        return None

    if group_chat_id is None:
        # Меню, открытые до переезда в ЛС, лежали прямо в группе и привязки не
        # имеют: для них целевая группа - это и есть чат сообщения.
        if msg.chat.type != "private":
            group_chat_id = panel_chat_id
            _bind_menu_target(panel_chat_id, message_id, group_chat_id)
        else:
            await call.answer("Меню устарело. Откройте его командой в группе.", show_alert=True)
            return None

    if not await _ensure_creator_permissions_callback(call, db, bot, group_chat_id=group_chat_id):
        return None
    return int(group_chat_id)


async def _edit_king_menu_message(
    call: types.CallbackQuery,
    text: str,
    *,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    bind_owner_id: int | None = None,
) -> types.Message | None:
    msg = getattr(call, "message", None)
    if msg is None:
        return None
    chat_id = int(msg.chat.id)
    message_id = int(msg.message_id)
    # Если редактирование сорвётся и придётся слать НОВОЕ сообщение, оно должно
    # унаследовать привязку к группе - иначе его кнопки сразу станут «устаревшими».
    inherited_target = _get_menu_target(chat_id, message_id)
    if _is_same_menu_state(chat_id, message_id, text, reply_markup, current_message=msg):
        if bind_owner_id is not None:
            _bind_menu_owner(chat_id, message_id, int(bind_owner_id))
        return msg

    try:
        await msg.edit_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
        _remember_menu_state(chat_id, message_id, text, reply_markup)
        if bind_owner_id is not None:
            _bind_menu_owner(chat_id, message_id, int(bind_owner_id))
        return msg
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            _remember_menu_state(chat_id, message_id, text, reply_markup)
            if bind_owner_id is not None:
                _bind_menu_owner(chat_id, message_id, int(bind_owner_id))
            return msg
        try:
            sent = await msg.answer(
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            if sent is not None:
                sent_chat_id = int(sent.chat.id)
                sent_message_id = int(sent.message_id)
                _remember_menu_state(sent_chat_id, sent_message_id, text, reply_markup)
                if bind_owner_id is not None:
                    _bind_menu_owner(sent_chat_id, sent_message_id, int(bind_owner_id))
                if inherited_target is not None:
                    _bind_menu_target(sent_chat_id, sent_message_id, inherited_target)
            return sent
        except Exception:
            return None
    except Exception:
        try:
            sent = await msg.answer(
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            if sent is not None:
                sent_chat_id = int(sent.chat.id)
                sent_message_id = int(sent.message_id)
                if bind_owner_id is not None:
                    _bind_menu_owner(sent_chat_id, sent_message_id, int(bind_owner_id))
                    _remember_menu_state(sent_chat_id, sent_message_id, text, reply_markup)
                if inherited_target is not None:
                    _bind_menu_target(sent_chat_id, sent_message_id, inherited_target)
            return sent
        except Exception:
            return None


async def _edit_menu_message_by_id(
    bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    bind_owner_id: int | None = None,
) -> None:
    if _is_same_menu_state(chat_id, message_id, text, reply_markup):
        if bind_owner_id is not None:
            _bind_menu_owner(int(chat_id), int(message_id), int(bind_owner_id))
        return
    try:
        await bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(message_id),
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
        _remember_menu_state(int(chat_id), int(message_id), text, reply_markup)
        if bind_owner_id is not None:
            _bind_menu_owner(int(chat_id), int(message_id), int(bind_owner_id))
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            _remember_menu_state(int(chat_id), int(message_id), text, reply_markup)
            if bind_owner_id is not None:
                _bind_menu_owner(int(chat_id), int(message_id), int(bind_owner_id))
            return
    except Exception:
        pass


async def _delete_menu_message_by_id(bot, chat_id: int, message_id: int) -> None:
    """
    Привязку снимаем ТОЛЬКО после успешного удаления.

    Раньше unbind шёл первым, а падение delete_message проглатывалось. Если
    Telegram отказывался удалять (старое сообщение, снятые права), меню
    оставалось висеть в чате уже без привязки - и клик по нему отвечал
    «Меню устарело», хотя пользователь никуда не уходил.
    """
    mid = int(message_id or 0)
    if mid <= 0:
        return
    try:
        await bot.delete_message(chat_id=int(chat_id), message_id=mid)
    except Exception as delete_error:
        # Сообщение осталось в чате - значит его кнопки должны продолжать работать.
        print(f"⚠️ [KING][DEL] не удалил {chat_id}/{mid}, привязку сохраняю: "
              f"{type(delete_error).__name__}: {delete_error}")
        return
    _unbind_menu_owner(int(chat_id), mid)


async def handle_king_stats_callback(call: types.CallbackQuery, db, bot) -> bool:
    data = str(getattr(call, "data", "") or "")
    if not is_king_stats_callback(data):
        return False
    try:
        return await _handle_king_stats_callback_inner(call, db, bot)
    except Exception:
        import traceback
        msg = getattr(call, "message", None)
        panel_chat_id = int(getattr(getattr(msg, "chat", None), "id", 0) or 0)
        message_id = int(getattr(msg, "message_id", 0) or 0)
        print(
            f"🔥 [KING][CB][FAIL] data={data!r} panel_chat_id={panel_chat_id} "
            f"message_id={message_id} user_id={getattr(call.from_user, 'id', None)} "
            f"target={_get_menu_target(panel_chat_id, message_id)}"
        )
        traceback.print_exc()
        try:
            await call.answer("Не удалось выполнить. Откройте меню заново.", show_alert=True)
        except Exception:
            pass
        return True


async def _handle_king_stats_callback_inner(call: types.CallbackQuery, db, bot) -> bool:
    data = str(getattr(call, "data", "") or "")

    msg = getattr(call, "message", None)
    if msg is None or getattr(msg, "chat", None) is None:
        await call.answer("Сообщение недоступно.", show_alert=True)
        return True

    await db.ensure_king_stats_schema()
    # panel_chat_id - где лежит сообщение меню (в новом потоке это ЛС).
    # chat_id - какая ГРУППА настраивается. Дальше по функции chat_id всегда
    # означает группу, а операции над сообщением идут по panel_chat_id.
    panel_chat_id = int(msg.chat.id)
    resolved_group_id = await _resolve_menu_callback_group(call, db, bot)
    if resolved_group_id is None:
        return True
    chat_id = int(resolved_group_id)
    user_id = int(call.from_user.id)
    print(
        f"👑 [KING][CB] data={data!r} panel_chat_id={panel_chat_id} "
        f"group_chat_id={chat_id} user_id={user_id}"
    )
    settings = await db.get_chat_king_reward_settings(chat_id)
    group_context = await _resolve_group_menu_context(db, chat_id)
    group_button = group_context.get("button")
    group_balance = int(group_context.get("balance") or 0)
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else "open"

    if action == "noop":
        await call.answer()
        return True

    if action == "input" and len(parts) >= 3 and parts[2] == "cancel":
        pending_before_cancel = _get_pending_input(panel_chat_id, user_id)
        panel_message_id = (
            int(pending_before_cancel.get("panel_message_id") or 0)
            if isinstance(pending_before_cancel, dict)
            else 0
        )
        _clear_pending_input(panel_chat_id, user_id)
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_king_menu_keyboard(
                settings,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        if panel_message_id > 0 and panel_message_id != int(msg.message_id):
            await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
        await call.answer("Ввод отменён.")
        return True

    if action == "close":
        _clear_pending_input(panel_chat_id, user_id)
        _unbind_menu_owner(panel_chat_id, int(msg.message_id))
        try:
            await msg.delete()
        except Exception:
            pass
        await call.answer("Меню закрыто.")
        return True

    if action == "reset" and len(parts) >= 3 and str(parts[2]).lower() == "all":
        _clear_pending_input(panel_chat_id, user_id)
        settings = await db.reset_chat_king_settings(chat_id, creator_id=user_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer("Настройки сброшены.")
        return True

    if action in {"open", "refresh"}:
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer()
        return True

    if action == "help":
        await _edit_king_menu_message(
            call,
            _HELP_TEXT + "\n\nНазад - в меню.",
            reply_markup=_help_keyboard_for_user(panel_chat_id, user_id),
            bind_owner_id=user_id,
        )
        await call.answer()
        return True

    if action == "place":
        if len(parts) < 3:
            await call.answer("Некорректный формат кнопки.", show_alert=True)
            return True
        try:
            place = int(parts[2])
        except Exception:
            await call.answer("Некорректное место.", show_alert=True)
            return True
        if place not in {1, 2, 3}:
            await call.answer("Место должно быть 1, 2 или 3.", show_alert=True)
            return True

        # kingm:place:<p>
        if len(parts) == 3:
            await _edit_king_menu_message(
                call,
                _king_place_text(settings, place),
                reply_markup=_king_place_keyboard(settings, place),
                bind_owner_id=user_id,
            )
            await call.answer()
            return True

        sub_action = parts[3]
        if sub_action == "hint":
            await call.answer(
                "Пример : кут `500` | предмет `🚬 1`",
                show_alert=True,
            )
            return True

        if sub_action == "item" and len(parts) >= 5 and str(parts[4]).lower() == "custom":
            if not await _ensure_creator_permissions_callback(call, db, bot, group_chat_id=chat_id):
                return True
            _set_pending_input(
                panel_chat_id,
                int(call.from_user.id),
                {
                    "type": "place_item_custom",
                    "place": int(place),
                    "panel_message_id": int(msg.message_id),
                },
                group_chat_id=chat_id,
            )
            await _edit_king_menu_message(
                call,
                _king_place_text(settings, place)
                + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите : <code>предмет количество</code>\nПример : <code>🚬 1</code>\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
                reply_markup=_king_place_keyboard(settings, place, show_input_cancel=True),
                bind_owner_id=user_id,
            )
            await call.answer("Жду ввод предмета.", show_alert=True)
            return True

        if sub_action == "clear":
            settings = await db.clear_chat_king_place_reward(chat_id, place, creator_id=int(call.from_user.id))
            await _edit_king_menu_message(
                call,
                _king_place_text(settings, place),
                reply_markup=_king_place_keyboard(settings, place),
                bind_owner_id=user_id,
            )
            await call.answer("Награда очищена.")
            return True

        if sub_action == "kut" and len(parts) >= 5:
            if str(parts[4]).lower() == "custom":
                _set_pending_input(
                    panel_chat_id,
                    int(call.from_user.id),
                    {
                        "type": "place_kut_custom",
                        "place": int(place),
                        "panel_message_id": int(msg.message_id),
                    },
                    group_chat_id=chat_id,
                )
                await _edit_king_menu_message(
                    call,
                    _king_place_text(settings, place)
                    + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите сумму кут которую получит победитель на {place} месте\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
                    reply_markup=_king_place_keyboard(settings, place, show_input_cancel=True),
                    bind_owner_id=user_id,
                )
                await call.answer("Жду сумму.", show_alert=True)
                return True
            try:
                amount = int(parts[4])
            except Exception:
                await call.answer("Некорректная сумма кут.", show_alert=True)
                return True
            settings = await db.set_chat_king_place_kut_reward(
                chat_id,
                place,
                max(0, amount),
                creator_id=int(call.from_user.id),
            )
            await _edit_king_menu_message(
                call,
                _king_place_text(settings, place),
                reply_markup=_king_place_keyboard(settings, place),
                bind_owner_id=user_id,
            )
            await call.answer("Награда обновлена.")
            return True

        await call.answer("Неизвестная кнопка места.", show_alert=True)
        return True

    if action == "toggle" and len(parts) >= 3:
        enabled = str(parts[2]).lower() == "on"
        settings = await db.set_chat_king_enabled(chat_id, enabled, creator_id=user_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer("Готово.")
        return True

    if action == "period" and len(parts) >= 3:
        period_kind = str(parts[2]).lower()
        if period_kind not in {"day", "week", "month"}:
            await call.answer("Некорректный период.", show_alert=True)
            return True
        settings = await db.set_chat_king_period_kind(chat_id, period_kind, creator_id=user_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer("Период обновлён.")
        return True

    if action == "min" and len(parts) >= 3:
        raw_min = str(parts[2]).strip().lower()
        if raw_min == "custom":
            _set_pending_input(
                panel_chat_id,
                int(call.from_user.id),
                {
                    "type": "min_custom",
                    "panel_message_id": int(msg.message_id),
                },
                group_chat_id=chat_id,
            )
            settings = await db.get_chat_king_reward_settings(chat_id)
            await _edit_king_menu_message(
                call,
                _king_menu_text(settings, group_button=group_button)
                + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите минимальное количество сообщений для участвия\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
                reply_markup=_king_menu_keyboard_with_pending_cancel(
                    settings,
                    group_button=group_button,
                    group_balance=group_balance,
                ),
                bind_owner_id=user_id,
            )
            await call.answer("Жду минимум.", show_alert=True)
            return True

        try:
            min_messages = int(raw_min)
        except Exception:
            await call.answer("Некорректный минимум.", show_alert=True)
            return True

        settings = await db.set_chat_king_min_messages(
            chat_id,
            max(0, min_messages),
            creator_id=int(call.from_user.id),
        )
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        if int(settings.get("min_messages") or 0) <= 0:
            await call.answer("Минимум выключен.")
        else:
            await call.answer("Минимум обновлён.")
        return True

    if action == "duration" and len(parts) >= 3 and str(parts[2]).lower() == "custom":
        _set_pending_input(
            panel_chat_id,
            int(call.from_user.id),
            {
                "type": "duration_custom",
                "panel_message_id": int(msg.message_id),
            },
            group_chat_id=chat_id,
        )
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button)
            + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите срок работы: <code>30 мин</code>, <code>12 часов</code>, <code>2 месяца</code> или <code>навсегда</code>\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
            reply_markup=_king_menu_keyboard_with_pending_cancel(
                settings,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer("Жду срок.", show_alert=True)
        return True

    if action == "start" and len(parts) >= 3 and str(parts[2]).lower() == "custom":
        _set_pending_input(
            panel_chat_id,
            int(call.from_user.id),
            {
                "type": "start_date_custom",
                "panel_message_id": int(msg.message_id),
            },
            group_chat_id=chat_id,
        )
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button)
            + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите дату старта: <code>16.07.2026</code>, <code>16 июня</code>, <code>16 июня 2026</code> или <code>сразу</code>\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
            reply_markup=_king_menu_keyboard_with_pending_cancel(
                settings,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        await call.answer("Жду дату.", show_alert=True)
        return True

    if action == "budget" and len(parts) >= 3:
        budget_action = str(parts[2]).lower()
        if budget_action == "alloc":
            _set_pending_input(
                panel_chat_id,
                int(call.from_user.id),
                {
                    "type": "budget_total_custom",
                    "panel_message_id": int(msg.message_id),
                },
                group_chat_id=chat_id,
            )
            settings = await db.get_chat_king_reward_settings(chat_id)
            await _edit_king_menu_message(
                call,
                _king_menu_text(settings, group_button=group_button)
                + f"\n\n<tg-emoji emoji-id='5215327832040811010'>⏳</tg-emoji> <b>Введите общий бюджет кут для 1/2/3 места.\nПример : <code>1000</code>\nОжидание : {_KING_PENDING_INPUT_TIMEOUT_SEC} сек.</b>",
                reply_markup=_king_menu_keyboard_with_pending_cancel(
                    settings,
                    group_button=group_button,
                    group_balance=group_balance,
                ),
                bind_owner_id=user_id,
            )
            await call.answer("Жду бюджет.", show_alert=True)
            return True

        if budget_action == "confirm":
            pending = _get_pending_input(panel_chat_id, user_id)
            if not pending or str(pending.get("type") or "") != "budget_confirm":
                await call.answer("Сначала задайте распределение.", show_alert=True)
                return True
            p1 = max(0, int(pending.get("p1") or 0))
            p2 = max(0, int(pending.get("p2") or 0))
            p3 = max(0, int(pending.get("p3") or 0))
            panel_message_id = int(pending.get("panel_message_id") or 0)

            settings = await db.set_chat_king_place_kut_reward(chat_id, 1, p1, creator_id=user_id)
            settings = await db.set_chat_king_place_kut_reward(chat_id, 2, p2, creator_id=user_id)
            settings = await db.set_chat_king_place_kut_reward(chat_id, 3, p3, creator_id=user_id)
            _clear_pending_input(panel_chat_id, user_id)
            menu_text = _king_menu_text(settings, group_button=group_button)
            menu_markup = _main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            )
            current_menu_message_id = int(msg.message_id)
            await _delete_menu_message_by_id(bot, panel_chat_id, current_menu_message_id)
            if panel_message_id > 0 and panel_message_id != current_menu_message_id:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            sent = None
            try:
                sent = await msg.answer(
                    text=menu_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=menu_markup,
                )
            except Exception:
                sent = None
            if sent is not None:
                _bind_menu_message(int(sent.chat.id), int(sent.message_id), user_id, chat_id)
                _remember_menu_state(int(sent.chat.id), int(sent.message_id), menu_text, menu_markup)
            await call.answer("Распределение сохранено.")
            return True

    if action == "finalize":
        settings = await db.get_chat_king_reward_settings(chat_id)
        context = resolve_current_king_context(
            payout_mode=KING_STATS_PAYOUT_MODE,
            period_kind=str(settings.get("period_kind") or KING_STATS_PERIOD_KIND),
            interval_sec=KING_STATS_WORKER_INTERVAL_SEC,
            interval_force_new_round=KING_STATS_INTERVAL_FORCE_NEW_ROUND,
        )
        result = await finalize_chat_king_day(
            db=db,
            bot=bot,
            chat_id=chat_id,
            stat_date=context["stat_date"],
            period_type=context["period_type"],
            period_key=context["period_key"],
            period_from=context["period_from"],
            period_to=context["period_to"],
            count_day_win=context["count_day_win"],
            period_title=context["title"],
            period_label=context["period_label"],
        )
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _edit_king_menu_message(
            call,
            _king_menu_text(settings, group_button=group_button),
            reply_markup=_main_menu_keyboard_for_user(
                settings,
                chat_id,
                user_id,
                group_button=group_button,
                group_balance=group_balance,
            ),
            bind_owner_id=user_id,
        )
        if result.get("skipped") == "already_processed":
            await call.answer("Итоги уже есть.", show_alert=True)
        elif result.get("skipped") == "disabled":
            await call.answer("Система выключена.", show_alert=True)
        elif result.get("skipped") == "scheduled_not_started":
            await call.answer("Ещё не наступила дата старта.", show_alert=True)
        elif result.get("skipped") == "expired":
            await call.answer("Срок системы истёк.", show_alert=True)
        elif result.get("ok"):
            await call.answer("Итоги готовы.")
        else:
            await call.answer("Не удалось подвести итоги.", show_alert=True)
        return True

    await call.answer("Неизвестная кнопка меню.", show_alert=True)
    return True


def _parse_items_batch(raw: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    tokens = [part.strip() for part in str(raw or "").split(",") if part.strip()]
    for token in tokens:
        if ":" not in token:
            continue
        item_id, amount_raw = token.split(":", 1)
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        try:
            amount = int(amount_raw)
        except Exception:
            continue
        if amount <= 0:
            continue
        result.append((item_id, amount))
    return result


def _extract_first_int(text: str, *, min_value: int = 1, max_value: int = 10**12) -> int | None:
    m = re.search(r"\b(\d+)\b", text)
    if not m:
        return None
    value = int(m.group(1))
    if value < min_value or value > max_value:
        return None
    return value


def _parse_duration_target(raw_text: str, *, now_dt: datetime | None = None) -> tuple[str, datetime | None]:
    now = now_dt or datetime.now(_MSK_TZ)
    normalized = _norm_text(raw_text)
    if normalized in _FOREVER_TOKENS:
        return "forever", None

    m = re.fullmatch(r"(\d{1,9})\s*([a-zа-яё.]*)", normalized)
    if not m:
        return "invalid", None

    amount = int(m.group(1))
    unit = str(m.group(2) or "").strip().strip(".")
    if amount <= 0:
        return "invalid", None

    if unit in {"", "s", "sec", "second", "seconds", "сек", "секунда", "секунды", "секунд", "с"}:
        delta = timedelta(seconds=amount)
    elif unit in {"m", "min", "minute", "minutes", "мин", "минута", "минуты", "минут", "м"}:
        delta = timedelta(minutes=amount)
    elif unit in {"h", "hr", "hour", "hours", "ч", "час", "часа", "часов"}:
        delta = timedelta(hours=amount)
    elif unit in {"d", "day", "days", "д", "день", "дня", "дней"}:
        delta = timedelta(days=amount)
    elif unit in {"mo", "mon", "month", "months", "мес", "месяц", "месяца", "месяцев"}:
        delta = timedelta(days=30 * amount)
    elif unit in {"y", "yr", "year", "years", "год", "года", "лет"}:
        delta = timedelta(days=365 * amount)
    else:
        return "invalid", None

    return "until", now + delta


def _coerce_date(day: int, month: int, year: int) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def _parse_start_date_input(raw_text: str, *, now_dt: datetime | None = None) -> tuple[str, date | None]:
    now = now_dt or datetime.now(_MSK_TZ)
    normalized = _norm_text(raw_text)
    if normalized in {"сразу", "сейчас", "now", "today", "выкл", "off", "none"}:
        return "clear", None

    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", normalized)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        if year < 100:
            year += 2000
        parsed = _coerce_date(day, month, year)
        return ("date", parsed) if parsed is not None else ("invalid", None)

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if m:
        parsed = _coerce_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return ("date", parsed) if parsed is not None else ("invalid", None)

    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})", normalized)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        parsed = _coerce_date(day, month, now.year)
        if parsed is None:
            return "invalid", None
        if parsed < now.date():
            parsed = _coerce_date(day, month, now.year + 1)
        return ("date", parsed) if parsed is not None else ("invalid", None)

    m = re.fullmatch(
        r"(\d{1,2})\s+([a-zа-яё]+)(?:\s+(\d{4}))?(?:\s+г(?:од(?:а)?)?)?",
        normalized,
    )
    if m:
        day = int(m.group(1))
        month_name = str(m.group(2) or "").strip()
        month = _RU_MONTHS.get(month_name)
        if not month:
            return "invalid", None
        year = int(m.group(3)) if m.group(3) else now.year
        parsed = _coerce_date(day, month, year)
        if parsed is None:
            return "invalid", None
        if m.group(3) is None and parsed < now.date():
            parsed = _coerce_date(day, month, now.year + 1)
        return ("date", parsed) if parsed is not None else ("invalid", None)

    return "invalid", None


def _parse_kut_distribution(raw_text: str) -> tuple[int, int, int] | None:
    text = _norm_text(raw_text)
    p1_match = re.search(r"(?<!\d)(?:1|перв\w*)(?!\d)\s*(?:мест\w*)?[^\d]{0,12}(\d{1,12})", text)
    p2_match = re.search(r"(?<!\d)(?:2|втор\w*)(?!\d)\s*(?:мест\w*)?[^\d]{0,12}(\d{1,12})", text)
    p3_match = re.search(r"(?<!\d)(?:3|трет\w*)(?!\d)\s*(?:мест\w*)?[^\d]{0,12}(\d{1,12})", text)
    if p1_match and p2_match and p3_match:
        p1 = int(p1_match.group(1))
        p2 = int(p2_match.group(1))
        p3 = int(p3_match.group(1))
        if p1 >= 0 and p2 >= 0 and p3 >= 0:
            return p1, p2, p3

    values = [int(x) for x in re.findall(r"\d{1,12}", text)]
    if len(values) < 3:
        return None
    if len(values) >= 6 and values[0] == 1 and values[2] == 2 and values[4] == 3:
        p1, p2, p3 = values[1], values[3], values[5]
        return p1, p2, p3
    p1, p2, p3 = values[0], values[1], values[2]
    if p1 < 0 or p2 < 0 or p3 < 0:
        return None
    return p1, p2, p3


def _parse_period_kind_from_text(text: str) -> str | None:
    if _contains_any(text, ("недел", "week")):
        return "week"
    if _contains_any(text, ("месяц", "месяч", "month")):
        return "month"
    if _contains_any(text, ("день", "днев", "day")):
        return "day"
    return None


def _parse_place_from_text(text: str) -> int | None:
    m = re.search(r"(?:за|для)?\s*([123])\s*(?:место|места|месту|мест)\b", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:место|места|месту|мест)\s*([123])\b", text)
    if m:
        return int(m.group(1))

    mapping = {
        "перв": 1,
        "втор": 2,
        "трет": 3,
    }
    for token, place in mapping.items():
        if token in text and "мест" in text:
            return int(place)
    return None


async def handle_king_stats_command(message: types.Message, db, bot) -> bool:
    """
    Обёртка с диагностикой. Раньше любой сбой внутри выглядел для пользователя
    как полная тишина: _reply_barnum глотает исключения и возвращает None,
    а необработанное исключение уходило в лог aiogram без контекста.
    """
    try:
        return await _handle_king_stats_command_inner(message, db, bot)
    except Exception:
        import traceback
        panel_chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
        user_id = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
        pending = _get_pending_input(panel_chat_id, user_id)
        print(
            f"🔥 [KING][CMD][FAIL] panel_chat_id={panel_chat_id} user_id={user_id} "
            f"text={str(getattr(message, 'text', ''))[:64]!r} "
            f"pending_type={(pending or {}).get('type')} "
            f"group_chat_id={(pending or {}).get('group_chat_id')}"
        )
        traceback.print_exc()
        try:
            await _reply_barnum(
                message,
                "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> "
                "<b>Не удалось применить значение.</b>\n"
                "<b>Откройте меню командой в группе и попробуйте ещё раз.</b>",
            )
        except Exception:
            pass
        return True


async def _handle_king_stats_command_inner(message: types.Message, db, bot) -> bool:
    normalized = _norm_text(getattr(message, "text", ""))
    # panel_chat_id - куда пришло сообщение. chat_id - какую ГРУППУ настраиваем.
    # В группе они совпадают, в ЛС нет: там группа берётся из payload ожидания.
    panel_chat_id = int(message.chat.id)
    user_id = int(message.from_user.id)
    is_private = message.chat.type == "private"
    await db.ensure_king_stats_schema()

    pending = _get_pending_input(panel_chat_id, user_id)

    # Пока есть ожидание ввода - группу берём из payload: в ЛС из самого
    # сообщения её не вывести. Без ожидания настраиваем чат, куда пришла команда.
    chat_id = _pending_group_chat_id(pending, panel_chat_id)
    group_context = await _resolve_group_menu_context(db, chat_id)
    group_button = group_context.get("button")
    group_balance = int(group_context.get("balance") or 0)

    if pending is not None:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            _clear_pending_input(panel_chat_id, user_id)
            return True

        raw_text = str(getattr(message, "text", "") or "").strip()
        panel_message_id = int(pending.get("panel_message_id") or 0)
        print(
            f"👑 [KING][INPUT] type={pending.get('type')!r} text={raw_text[:48]!r} "
            f"panel_chat_id={panel_chat_id} group_chat_id={chat_id} "
            f"panel_message_id={panel_message_id}"
        )
        if not raw_text:
            await _reply_pending_input_error(
                message,
                user_id,
                pending,
                "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Я жду значение для настройки.</b>\n<b>Отправьте ввод в нужном формате.</b>",
                group_chat_id=chat_id,
            )
            return True

        if is_king_stats_command(raw_text):
            _clear_pending_input(panel_chat_id, user_id)
            settings = await db.get_chat_king_reward_settings(chat_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        if _norm_text(raw_text) in {"отмена", "cancel", "стоп"}:
            _clear_pending_input(panel_chat_id, user_id)
            settings = await db.get_chat_king_reward_settings(chat_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        pending_type = str(pending.get("type") or "").strip().lower()

        if pending_type == "min_custom":
            norm_input = _norm_text(raw_text)
            if norm_input in {"выкл", "off", "откл", "нет", "none"}:
                min_value = 0
            else:
                try:
                    min_value = int(raw_text)
                except Exception:
                    await _reply_pending_input_error(
                        message,
                        user_id,
                        pending,
                        "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял минимум сообщений.</b>\n<b>Введите число: <code>0</code> (выкл) или <code>30</code>.</b>",
                        group_chat_id=chat_id,
                    )
                    return True

            settings = await db.set_chat_king_min_messages(chat_id, max(0, min_value), creator_id=user_id)
            _clear_pending_input(panel_chat_id, user_id)
            min_now = int(settings.get("min_messages") or 0)
            min_view = "выкл" if min_now <= 0 else str(min_now)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                text=(
                    _king_menu_text(settings, group_button=group_button)
                    + f"\n\n<b>Минимум сообщений для участия : {min_view}</b>"
                ),
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        if pending_type == "duration_custom":
            mode, target_dt = _parse_duration_target(raw_text)
            if mode == "invalid":
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял срок.</b>\n<b>Примеры: <code>30 мин</code>, <code>12 часов</code>, <code>2 месяца</code>, <code>навсегда</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            if mode == "forever":
                settings = await db.set_chat_king_active_until(chat_id, None, creator_id=user_id)
            else:
                assert target_dt is not None
                settings = await db.set_chat_king_active_until(
                    chat_id,
                    target_dt.astimezone(timezone.utc),
                    creator_id=user_id,
                )
            _clear_pending_input(panel_chat_id, user_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        if pending_type == "start_date_custom":
            mode, target_date = _parse_start_date_input(raw_text)
            if mode == "invalid":
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял дату старта.</b>\n<b>Примеры: <code>16.07.2026</code>, <code>16 июня</code>, <code>16 июня 2026</code>, <code>сразу</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            if mode == "clear":
                settings = await db.set_chat_king_start_at(chat_id, None, creator_id=user_id)
            else:
                assert target_date is not None
                start_local = datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    0,
                    0,
                    0,
                    tzinfo=_MSK_TZ,
                )
                settings = await db.set_chat_king_start_at(
                    chat_id,
                    start_local.astimezone(timezone.utc),
                    creator_id=user_id,
                )
            _clear_pending_input(panel_chat_id, user_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        if pending_type == "budget_total_custom":
            total_kut = _extract_first_int(raw_text, min_value=1, max_value=10**12)
            if total_kut is None:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял общий бюджет.</b>\n<b>Введите число, например: <code>1000</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            next_payload = {
                "type": "budget_split_custom",
                "panel_message_id": 0,
                "total_kut": int(total_kut),
            }
            _set_pending_input(
                panel_chat_id,
                user_id,
                next_payload,
                group_chat_id=chat_id,
            )
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            sent = await _reply_pending_input_error(
                message,
                user_id,
                _get_pending_input(panel_chat_id, user_id),
                f"<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Теперь введите 3 суммы для мест:</b>\n<b><code>500 300 200</code> (сумма = {int(total_kut)}).</b>",
                group_chat_id=chat_id,
            )
            if sent is not None:
                next_payload["panel_message_id"] = int(sent.message_id)
                _set_pending_input(panel_chat_id, user_id, next_payload, group_chat_id=chat_id)
            return True

        if pending_type == "budget_split_custom":
            dist = _parse_kut_distribution(raw_text)
            total_kut = int(pending.get("total_kut") or 0)
            if dist is None:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял распределение.</b>\n<b>Нужно 3 числа: <code>500 300 200</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            p1, p2, p3 = dist
            if p1 + p2 + p3 != total_kut:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Сумма не сходится.</b>\n<b>Ожидается: {total_kut}, сейчас: {p1 + p2 + p3}.</b>",
                    group_chat_id=chat_id,
                )
                return True

            confirm_payload = {
                "type": "budget_confirm",
                "panel_message_id": 0,
                "total_kut": total_kut,
                "p1": int(p1),
                "p2": int(p2),
                "p3": int(p3),
            }
            _set_pending_input(panel_chat_id, user_id, confirm_payload, group_chat_id=chat_id)
            bet_amount_win_formated1 = "{:,.0f}".format(p1).replace("," , ".")
            bet_amount_win_formated2 = "{:,.0f}".format(p2).replace("," , ".")
            bet_amount_win_formated3 = "{:,.0f}".format(p3).replace("," , ".")
            confirm_text = (
                "<b>Проверьте распределение кут :</b>\n"
                f"<tg-emoji emoji-id='5280735858926822987'>🥇</tg-emoji> <b>{bet_amount_win_formated1}</b> | <tg-emoji emoji-id='5283195573812340110'>🥈</tg-emoji> <b>{bet_amount_win_formated2}</b> | <tg-emoji emoji-id='5287277338931779754'>🥉</tg-emoji> <b>{bet_amount_win_formated3}</b>\n"
                f"<b>Итого : {total_kut} кут</b>\n\n"
                "<b>Если всё верно, нажмите «Все в порядке».</b>"
            )
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            sent = await _reply_barnum(
                message,
                confirm_text,
                reply_markup=_budget_confirm_keyboard(),
            )
            if sent is not None:
                confirm_payload["panel_message_id"] = int(sent.message_id)
                _set_pending_input(panel_chat_id, user_id, confirm_payload, group_chat_id=chat_id)
                _bind_menu_owner(int(sent.chat.id), int(sent.message_id), user_id)
                _remember_menu_state(
                    int(sent.chat.id),
                    int(sent.message_id),
                    confirm_text,
                    _budget_confirm_keyboard(),
                )
            return True

        if pending_type == "place_kut_custom":
            place = int(pending.get("place") or 1)
            try:
                kut = int(raw_text)
            except Exception:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял сумму награды.</b>\n<b>Введите только число, например: <code>500</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            settings = await db.set_chat_king_place_kut_reward(chat_id, place, kut, creator_id=user_id)
            _clear_pending_input(panel_chat_id, user_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        if pending_type == "place_item_custom":
            place = int(pending.get("place") or 1)
            m = re.match(r"^(.+?)\s+(\d{1,9})$", raw_text)
            if not m:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не понял формат предмета.</b>\n<b>Нужно: <code>предмет количество</code>, пример: <code>🚬 1</code>.</b>",
                    group_chat_id=chat_id,
                )
                return True
            token = str(m.group(1) or "").strip()
            amount = int(m.group(2))
            resolved_name, resolved_emoji = await _resolve_item_name_for_reward(db, token)
            if not resolved_name:
                await _reply_pending_input_error(
                    message,
                    user_id,
                    pending,
                    f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Предмет не найден: {token}.</b>\n<b>Проверьте эмодзи / id / название.</b>",
                    group_chat_id=chat_id,
                )
                return True
            settings = await db.add_chat_king_place_item_reward(
                chat_id=chat_id,
                place=place,
                item_id=resolved_name,
                amount=amount,
                creator_id=user_id,
            )
            _clear_pending_input(panel_chat_id, user_id)
            if panel_message_id > 0:
                await _delete_menu_message_by_id(bot, panel_chat_id, panel_message_id)
            await _send_bound_menu_message(
                message,
                settings,
                user_id,
                db=db,
                group_button=group_button,
                group_balance=group_balance,
                group_chat_id=chat_id,
            )
            return True

        _clear_pending_input(panel_chat_id, user_id)
        await _reply_barnum(message, "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Режим ввода сброшен. Откройте меню заново.</b>")
        return True

    if not is_king_stats_command(normalized):
        return False

    show_help_aliases = {
        "царь",
        "царь статистики",
        "царь стата",
        "царь команды",
        "царь хелп",
        "царь help",
        "царь помощь",
        "king",
        "king help",
    }
    if normalized in show_help_aliases or (
        _is_king_context(normalized)
        and _contains_any(
            normalized,
            (
                "помощ",
                "хелп",
                "help",
                "команд",
                "инструкц",
                "как пользоваться",
                "как использовать",
                "что умеет",
            ),
        )
    ):
        await _reply_barnum(message, _HELP_TEXT)
        return True

    # Помощь выше отвечает где угодно, а настройки живут только в ЛС: из ЛС
    # непонятно, какую группу настраивать, поэтому просим написать в группе.
    if is_private:
        await _reply_barnum(
            message,
            "<tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> <b>Царь статистики</b>\n"
            "<b>Напишите эту команду в той группе, которую хотите настроить.</b>\n"
            "<b>Меню настроек я пришлю сюда, в личные сообщения.</b>",
        )
        return True

    # Открыть меню: и явное «система царя статистики», и любой другой
    # распознанный запрос - меню всегда уезжает в ЛС.
    if _is_king_menu_open_intent(normalized) or _KING_STRICT_INLINE_ONLY:
        return await _deliver_menu_to_dm(message, db, bot, group_chat_id=chat_id)

    show_settings_aliases = {
        "царь награды",
        "царь настройки",
        "царь статус",
        "царь инфо",
        "царь информация",
        "царь конфиг",
    }
    if normalized in show_settings_aliases or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("покажи", "показать", "посмотреть", "текущ"))
        and _contains_any(normalized, ("настрой", "конфиг", "статус", "наград"))
        and _parse_place_from_text(normalized) is None
        and not _contains_any(normalized, ("очист", "добав", "установ", "постав", "кут", "предмет"))
    ):
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _reply_barnum(message, _settings_text(settings))
        return True

    if normalized in {"царь период", "царь период?", "царь режим периода"} or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("какой период", "период группы", "текущий период"))
    ):
        settings = await db.get_chat_king_reward_settings(chat_id)
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> <b>Сейчас в группе период : {_period_human(settings.get('period_kind'))}</b>\n"
            "<b>Изменить может только создатель : <code>царь период день|неделя|месяц</code>.</b>",
        )
        return True

    enable_aliases = {
        "царь вкл",
        "царь включить",
        "царь старт",
        "царь on",
        "царь активировать",
        "включить систему царя статистики",
        "включи систему царя статистики",
        "включить царя статистики",
        "активировать систему царя статистики",
        "запустить систему царя статистики",
        "запусти систему царя статистики",
    }
    enable_intent = (
        normalized in enable_aliases
        or (
            _is_king_context(normalized)
            and _contains_any(normalized, ("включ", "активир", "запуст", "start", " on"))
            and not _contains_any(normalized, ("выключ", "деактив", "стоп", "stop", " off"))
        )
    )
    if enable_intent:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        settings = await db.set_chat_king_enabled(chat_id, True, creator_id=user_id)
        await _reply_barnum(message, "<b><tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> Система «Царь статистики» включена.</b>\n\n" + _settings_text(settings))
        return True

    disable_aliases = {
        "царь выкл",
        "царь выключить",
        "царь стоп",
        "царь off",
        "царь деактивировать",
        "выключить систему царя статистики",
        "выключи систему царя статистики",
        "отключить систему царя статистики",
        "деактивировать систему царя статистики",
        "остановить систему царя статистики",
    }
    disable_intent = (
        normalized in disable_aliases
        or (
            _is_king_context(normalized)
            and _contains_any(normalized, ("выключ", "отключ", "деактив", "останов", "stop", " off"))
        )
    )
    if disable_intent:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        settings = await db.set_chat_king_enabled(chat_id, False, creator_id=user_id)
        await _reply_barnum(message, "<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Система «Царь статистики» выключена.</b>\n\n" + _settings_text(settings))
        return True

    m = re.fullmatch(r"царь (?:период|режим) (day|week|month|день|неделя|месяц)", normalized)
    period_from_free_text = (
        _parse_period_kind_from_text(normalized)
        if _is_king_context(normalized) and _contains_any(normalized, ("период", "режим"))
        else None
    )
    if m or period_from_free_text:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        if m:
            raw = m.group(1)
            period_map = {
                "day": "day",
                "week": "week",
                "month": "month",
                "день": "day",
                "неделя": "week",
                "месяц": "month",
            }
            period_kind = period_map.get(raw, "day")
        else:
            period_kind = str(period_from_free_text or "day")
        settings = await db.set_chat_king_period_kind(chat_id, period_kind, creator_id=user_id)
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Период успешно изменен на : {_period_human(settings.get('period_kind'))}</b>.\n\n{_settings_text(settings)}",
        )
        return True

    finalize_aliases = {
        "царь обновить",
        "царь подвести",
        "царь итоги",
        "царь финал",
        "царь завершить день",
        "подвести итоги царя статистики",
        "обновить царя статистики",
        "пересчитать царя статистики",
    }
    finalize_intent = (
        normalized in finalize_aliases
        or (
            _is_king_context(normalized)
            and _contains_any(normalized, ("обнов", "подвед", "итог", "финал", "пересчит", "заверш"))
            and not _contains_any(normalized, ("наград", "кут", "предмет", "очист", "порог", "мин"))
        )
    )
    if finalize_intent:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        settings = await db.get_chat_king_reward_settings(chat_id)
        context = resolve_current_king_context(
            payout_mode=KING_STATS_PAYOUT_MODE,
            period_kind=str(settings.get("period_kind") or KING_STATS_PERIOD_KIND),
            interval_sec=KING_STATS_WORKER_INTERVAL_SEC,
            interval_force_new_round=KING_STATS_INTERVAL_FORCE_NEW_ROUND,
        )
        result = await finalize_chat_king_day(
            db=db,
            bot=bot,
            chat_id=chat_id,
            stat_date=context["stat_date"],
            period_type=context["period_type"],
            period_key=context["period_key"],
            period_from=context["period_from"],
            period_to=context["period_to"],
            count_day_win=context["count_day_win"],
            period_title=context["title"],
            period_label=context["period_label"],
        )
        if result.get("skipped") == "already_processed":
            await _reply_barnum(
                message,
                f"<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Итоги уже были подведены за период : {context['period_label']}</b>",
            )
        elif result.get("skipped") == "disabled":
            await _reply_barnum(message, "<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Система сейчас выключена. Включите : <code>царь вкл</code>.</b>")
        elif result.get("skipped") == "scheduled_not_started":
            await _reply_barnum(message, "<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>До старта ещё есть время.</b>")
        elif result.get("skipped") == "expired":
            await _reply_barnum(message, "<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Срок системы уже истёк.</b>")
        elif result.get("ok"):
            await _reply_barnum(message, f"<tg-emoji emoji-id='5260463209562776385'>✅</tg-emoji> <b>Итоги успешно подведены за : {context['period_label']}</b>")
        else:
            await _reply_barnum(message, "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не получилось подвести итоги. Попробуйте ещё раз.</b>")
        return True

    m = re.fullmatch(r"царь (?:мин|минимум|порог|min) (\d{1,5})", normalized)
    min_from_free_text = None
    if _is_king_context(normalized) and _contains_any(normalized, ("мин", "миним", "порог")):
        min_from_free_text = _extract_first_int(normalized, min_value=1, max_value=100000)
    if m or min_from_free_text is not None:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        min_value = int(m.group(1)) if m else int(min_from_free_text or 1)
        settings = await db.set_chat_king_min_messages(chat_id, min_value, creator_id=user_id)
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Минимум сообщений для участия : {int(settings.get('min_messages') or 0)}</b>",
        )
        return True

    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123]) очистить", normalized)
    place_clear = _parse_place_from_text(normalized) if _contains_any(normalized, ("очист", "сброс")) else None
    if m or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("очист", "сброс"))
        and place_clear is not None
        and not _contains_any(normalized, ("все", "всё"))
    ):
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        place = int(m.group(1)) if m else int(place_clear or 1)
        settings = await db.clear_chat_king_place_reward(chat_id, place, creator_id=user_id)
        reward = settings.get(f"place_{place}") or {}
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Награда для {place} места очищена.\nСейчас : {_reward_short(reward)}</b>",
        )
        return True

    if normalized in {"царь очистить все", "царь награды очистить все", "царь сброс наград"} or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("очист", "сброс"))
        and _contains_any(normalized, ("все", "всё"))
    ):
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        await db.clear_chat_king_place_reward(chat_id, 1, creator_id=user_id)
        await db.clear_chat_king_place_reward(chat_id, 2, creator_id=user_id)
        settings = await db.clear_chat_king_place_reward(chat_id, 3, creator_id=user_id)
        await _reply_barnum(message, "<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Награды для 1/2/3 места полностью очищены.</b>\n\n" + _settings_text(settings))
        return True

    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123]) кут (\d{1,12})", normalized)
    mk = re.search(r"(?:за|для)\s*([123])\s*мест[ао]\D+(\d{1,12})\s*кут", normalized)
    km = re.search(r"(\d{1,12})\s*кут\D+(?:за|для)\s*([123])\s*мест[ао]", normalized)
    if m or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("кут",))
        and _contains_any(normalized, ("наград", "приз", "мест"))
        and (mk is not None or km is not None)
    ):
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        if m:
            place = int(m.group(1))
            kut = int(m.group(2))
        elif mk:
            place = int(mk.group(1))
            kut = int(mk.group(2))
        else:
            place = int((km.group(2) if km else 1))
            kut = int((km.group(1) if km else 0))
        settings = await db.set_chat_king_place_kut_reward(chat_id, place, kut, creator_id=user_id)
        reward = settings.get(f"place_{place}") or {}
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Награда для {place} места обновлена.\nСейчас : {_reward_short(reward)}</b>.",
        )
        return True

    # Короткая форма: "царь награды 1 🚬 1"
    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123]) ([^\s]+) (\d{1,9})", normalized)
    if m:
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        place = int(m.group(1))
        token = str(m.group(2) or "").strip()
        amount = int(m.group(3))
        if token.lower() not in {"кут", "предмет", "предметы", "очистить", "очист", "clear"}:
            resolved_name, resolved_emoji = await _resolve_item_name_for_reward(db, token)
            if not resolved_name:
                await _reply_barnum(
                    message,
                    f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не нашёл предмет: {token}</b>\n"
                    "<b>Проверьте id/название/эмодзи предмета в магазине.</b>",
                )
                return True
            settings = await db.add_chat_king_place_item_reward(
                chat_id=chat_id,
                place=place,
                item_id=resolved_name,
                amount=amount,
                creator_id=user_id,
            )
            reward = settings.get(f"place_{place}") or {}
            shown = f"{resolved_emoji} {resolved_name}".strip()
            await _reply_barnum(
                message,
                f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Предмет {shown} добавлен в награду {place} места.</b>\n"
                f"<b>Сейчас : {_reward_short(reward)}</b>.",
            )
            return True

    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123]) предмет ([^\s]+) (\d{1,9})", normalized)
    mi1 = re.search(r"(?:за|для)\s*([123])\s*мест[ао].*?предмет\s+([^\s]+)\s+(\d{1,9})", normalized)
    mi2 = re.search(r"предмет\s+([^\s]+)\s+(\d{1,9}).*?(?:за|для)\s*([123])\s*мест[ао]", normalized)
    if m or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("предмет",))
        and (mi1 is not None or mi2 is not None)
    ):
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        if m:
            place = int(m.group(1))
            item_id = str(m.group(2)).strip()
            amount = int(m.group(3))
        elif mi1:
            place = int(mi1.group(1))
            item_id = str(mi1.group(2)).strip()
            amount = int(mi1.group(3))
        else:
            place = int((mi2.group(3) if mi2 else 1))
            item_id = str((mi2.group(1) if mi2 else "")).strip()
            amount = int((mi2.group(2) if mi2 else 0))
        resolved_name, resolved_emoji = await _resolve_item_name_for_reward(db, item_id)
        if not resolved_name:
            await _reply_barnum(
                message,
                f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не нашёл предмет : {item_id}</b>\n"
                "<b>Проверьте id/название/эмодзи предмета в магазине.</b>",
            )
            return True
        settings = await db.add_chat_king_place_item_reward(
            chat_id=chat_id,
            place=place,
            item_id=resolved_name,
            amount=amount,
            creator_id=user_id,
        )
        reward = settings.get(f"place_{place}") or {}
        shown = f"{resolved_emoji} {resolved_name}".strip()
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Предмет {shown} добавлен в награду {place} места.</b>\n"
            f"<b>Сейчас : {_reward_short(reward)}</b>",
        )
        return True

    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123]) предметы (.+)", normalized)
    mb1 = re.search(r"(?:за|для)\s*([123])\s*мест[ао].*?предметы\s+(.+)", normalized)
    mb2 = re.search(r"предметы\s+(.+?)\s*(?:за|для)\s*([123])\s*мест[ао]", normalized)
    if m or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("предметы",))
        and (mb1 is not None or mb2 is not None)
    ):
        if not await _ensure_creator_permissions(message, db, bot, group_chat_id=chat_id):
            return True
        if m:
            place = int(m.group(1))
            raw_items = m.group(2)
        elif mb1:
            place = int(mb1.group(1))
            raw_items = mb1.group(2)
        else:
            place = int((mb2.group(2) if mb2 else 1))
            raw_items = str(mb2.group(1) if mb2 else "")
        parsed_items = _parse_items_batch(raw_items)
        if not parsed_items:
            await _reply_barnum(
                message,
                "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Неверный формат списка предметов.</b>\n"
                "<b>Пример : <code>царь награды 1 предметы 290:1,299:2</code></b>",
            )
            return True

        settings = None
        for item_id, amount in parsed_items:
            resolved_name, _ = await _resolve_item_name_for_reward(db, item_id)
            if not resolved_name:
                await _reply_barnum(
                    message,
                    f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Не нашёл предмет : {item_id}</b>\n"
                    "<b>Проверьте id/название/эмодзи и попробуйте снова.</b>",
                )
                return True
            settings = await db.add_chat_king_place_item_reward(
                chat_id=chat_id,
                place=place,
                item_id=resolved_name,
                amount=amount,
                creator_id=user_id,
            )

        reward = (settings or {}).get(f"place_{place}") or {}
        await _reply_barnum(
            message,
            f"<tg-emoji emoji-id='5852871561983299073'>✅</tg-emoji> <b>Список предметов добавлен в награду {place} места.\nСейчас : {_reward_short(reward)}</b>",
        )
        return True

    # Быстрый просмотр только одного места: "царь награды 1"
    m = re.fullmatch(r"царь(?: награды| награда| место)? ([123])", normalized)
    place_view = _parse_place_from_text(normalized)
    if m or (
        _is_king_context(normalized)
        and _contains_any(normalized, ("наград", "приз"))
        and _contains_any(normalized, ("покажи", "показать", "посмотреть", "какая"))
        and place_view is not None
    ):
        place = int(m.group(1)) if m else int(place_view or 1)
        settings = await db.get_chat_king_reward_settings(chat_id)
        reward = settings.get(f"place_{place}") or {}
        await _reply_barnum(
            message,
            f"<b><tg-emoji emoji-id='5467406098367521267'>👑</tg-emoji> Награда для {place} места</b>\n{_reward_short(reward)}",
        )
        return True

    await _reply_barnum(
        message,
        "<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Команда не распознана.\n"
        "Проверьте формат или откройте меню : <code>система царя статистики</code>.\n"
        "Подсказка по командам : <code>царь</code>.</b>\n\n"
        + _HELP_TEXT,
    )
    return True

