"""Бот поддержки — принимает обращения от игроков, передаёт в админку."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import SUPPORT_BOT_TOKEN, ADMIN_BOT_TOKEN, owner_user_ids
from telegram_notify import send_telegram_message
from db import db

logger = logging.getLogger("cute-farm.support-bot")

# Простое in-memory хранилище состояний: user_id → 'write:<topic_key>'
_user_state: dict[int, str] = {}


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать обращение", callback_data="create",icon_custom_emoji_id="5778299625370817409")],
    ])


def _topic_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ошибка / баг",        callback_data="topic:bug",icon_custom_emoji_id="5397976749436842796")],
        [InlineKeyboardButton(text="Проблема с балансом",  callback_data="topic:balance",icon_custom_emoji_id="5397822319592750565")],
        [InlineKeyboardButton(text="Проблема с аккаунтом", callback_data="topic:account",icon_custom_emoji_id="5226579383635970881")],
        [InlineKeyboardButton(text="Вопрос",               callback_data="topic:question",icon_custom_emoji_id="5397674675796985688")],
        [InlineKeyboardButton(text="Другое",               callback_data="topic:other",icon_custom_emoji_id="5397981293512243749")],
        [InlineKeyboardButton(text="← Назад",                callback_data="back")],
    ])


def _ticket_open_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статус обращения",  callback_data="status",icon_custom_emoji_id="6021405408663445899")],
        [InlineKeyboardButton(text="Закрыть обращение", callback_data="close",icon_custom_emoji_id="5429405838345265327")],
    ])


def _new_ticket_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать новое обращение", callback_data="create",icon_custom_emoji_id="5400289821253990206")],
    ])


TOPIC_LABELS: dict[str, str] = {
    "bug":      "Ошибка / баг",
    "balance":  "Проблема с балансом",
    "account":  "Проблема с аккаунтом",
    "question": "Вопрос",
    "other":    "Другое",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _notify_admins(text: str) -> None:
    if not ADMIN_BOT_TOKEN:
        return
    for uid in owner_user_ids():
        try:
            await send_telegram_message(text, chat_id=str(uid), token=ADMIN_BOT_TOKEN)
        except Exception:
            logger.exception("notify owner failed (uid=%s)", uid)


async def _get_open_ticket(user_id: int) -> dict | None:
    try:
        row = await db.pool.fetchrow(
            "SELECT id, status, subject, created_at FROM support_tickets "
            "WHERE user_id = $1 AND status = 'open' "
            "ORDER BY created_at DESC LIMIT 1",
            user_id,
        )
        return dict(row) if row else None
    except Exception:
        logger.exception("_get_open_ticket failed for user_id=%s", user_id)
        return None


def _display_name(user: types.User) -> str:
    return user.first_name or (f"@{user.username}" if user.username else f"ID {user.id}")


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

async def run_support_bot() -> None:
    if not SUPPORT_BOT_TOKEN:
        logger.warning("SUPPORT_BOT_TOKEN не задан — support-бот не запускается")
        return

    from aiogram.client.session.aiohttp import AiohttpSession

    # Локально на Windows часто ловим WinError 121 (таймаут семафора) —
    # короткий timeout aiohttp убивает старт. Держим запас.
    session = AiohttpSession(timeout=120.0)
    bot = Bot(
        token=SUPPORT_BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        me = await bot.get_me()
        logger.info("Support bot: @%s (id=%s)", me.username, me.id)
    except TelegramUnauthorizedError:
        await bot.session.close()
        raise RuntimeError(
            "SUPPORT_BOT_TOKEN отклонён Telegram. Создай бота в @BotFather и "
            "вставь токен как SUPPORT_BOT_TOKEN в server/.env"
        ) from None

    dp = Dispatcher()

    # Мэджик: все inline-кнопки support-бота
    try:
        from bot.magic import install_magic

        install_magic(dp, start_health=False)
    except Exception as _magic_err:
        logger.warning("Magic not attached to support bot: %r", _magic_err)

    # Бот поддержки — только личные сообщения. Без этого глобального фильтра
    # ни один из хендлеров ниже не проверял chat.type, поэтому если бота
    # добавляли в группу, он реагировал на ЛЮБОЕ сообщение в чате как на
    # обращение/апелляцию (F.text/F.photo ловят всё подряд). Фильтр на
    # dp.message применяется сразу ко всем @dp.message(...) хендлерам ниже.
    dp.message.filter(F.chat.type == "private")

    await bot.set_my_commands([
        types.BotCommand(command="start",  description="Главное меню"),
        types.BotCommand(command="status", description="Статус обращения"),
        types.BotCommand(command="close",  description="Закрыть обращение"),
    ])

    # ------------------------------------------------------------------
    # /start
    # ------------------------------------------------------------------
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message) -> None:
        _user_state.pop(message.from_user.id, None)
        user_id = message.from_user.id

        # Параметр start=appeal — игрок пришёл с экрана бана
        args = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split()) > 1 else ""
        if args.strip().lower() == "appeal":
            await _start_appeal_flow(message)
            return

        try:
            ticket = await _get_open_ticket(user_id)
        except Exception:
            ticket = None

        if ticket:
            await message.answer(
                "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Служба поддержки Cute</b>\n\n"
                f"<b>У вас есть открытое обращение #{ticket['id']}</b>.\n"
                f"<b>Тема : {ticket.get('subject') or '—'}\n\n</b>"
                "<b><i>Напишите дополнительное сообщение или воспользуйтесь кнопками :</i></b>",
                reply_markup=_ticket_open_kb(),
            )
        else:
            await message.answer(
                "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Служба поддержки Cute</b>\n\n"
                "<b>Мы поможем с вопросами об игре, проблемами с аккаунтом и ошибками.</b>\n\n"
                "<b><i>Нажмите кнопку чтобы создать обращение :</i></b>",
                reply_markup=_main_menu_kb(),
            )

    async def _start_appeal_flow(message: types.Message) -> None:
        user_id = message.from_user.id

        # Проверяем активную апелляцию
        try:
            existing = await db.pool.fetchrow(
                "SELECT id, status FROM ban_appeals WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
                user_id,
            )
        except Exception:
            existing = None

        if existing and existing["status"] in ("pending", "taken"):
            status_text = "рассматривается" if existing["status"] == "taken" else "ожидает рассмотрения"
            await message.answer(
                f"<tg-emoji emoji-id='5213452215527677338'>⏳</tg-emoji> <b>Ваша апелляция уже {status_text}</b>\n\n"
                f"<b>Номер : #{existing['id']}</b>\n\n"
                "<b><i>Дождитесь ответа администратора - вы получите уведомление здесь.</i></b>"
            )
            return

        # Проверяем что пользователь реально забанен
        try:
            row = await db.pool.fetchrow(
                "SELECT banned, banned_reason FROM users WHERE user_id = $1", user_id,
            )
        except Exception:
            row = None

        if not row or not row["banned"]:
            await message.answer(
                "<tg-emoji emoji-id='5260463209562776385'>✅</tg-emoji> <b>Ваш аккаунт не заблокирован</b>\n\n"
                "<b>Если у вас другой вопрос - напишите /start</b>",
                reply_markup=_main_menu_kb(),
            )
            return

        ban_reason = row["banned_reason"] or ""
        _user_state[user_id] = f"appeal:{ban_reason}"

        reason_line = f"\n<tg-emoji emoji-id='6021435576513730578'>📋</tg-emoji> <b>Причина бана : {ban_reason}</b>" if ban_reason else ""

        await message.answer(
            "<tg-emoji emoji-id='4929524417354007168'>🗃</tg-emoji> <b>Подача апелляции</b>\n"
            f"{reason_line}\n\n"
            "<b>Опишите ситуацию подробно - почему вы считаете бан несправедливым?</b>\n\n"
            "<blockquote><b><i>Напишите ваш ответ следующим сообщением (до 1000 символов) :</i></b></blockquote>"
        )

    # ------------------------------------------------------------------
    # /status
    # ------------------------------------------------------------------
    @dp.message(Command("status"))
    async def cmd_status(message: types.Message) -> None:
        ticket = await _get_open_ticket(message.from_user.id)
        if not ticket:
            await message.answer(
                "<tg-emoji emoji-id='5388591472800986666'>✌</tg-emoji> <b>У вас нет открытых обращений.\nНапишите /start чтобы создать новое.</b>",
                reply_markup=_main_menu_kb(),
            )
            return
        await message.answer(
            f"<tg-emoji emoji-id='6021435576513730578'>📋</tg-emoji> <b>Обращение #{ticket['id']}</b>\n"
            f"<b>Тема : {ticket.get('subject') or '—'}\n</b>"
            f"<b>Статус : <b>открыто</b>\n</b>"
            f"<b>Создано : {ticket['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n</b>"
            "<blockquote><b><i>Можете добавить уточнения просто напишите сообщение.</i></b></blockquote>",
            reply_markup=_ticket_open_kb(),
        )

    # ------------------------------------------------------------------
    # /close
    # ------------------------------------------------------------------
    @dp.message(Command("close"))
    async def cmd_close(message: types.Message) -> None:
        _user_state.pop(message.from_user.id, None)
        ticket = await _get_open_ticket(message.from_user.id)
        if not ticket:
            await message.answer("Нет открытых обращений.", reply_markup=_main_menu_kb())
            return
        from support_db import close_ticket as db_close_ticket
        await db_close_ticket(ticket["id"])
        await message.answer(
            f"<tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> <b>Обращение #{ticket['id']} закрыто.</b>\n\n"
            "<b>Если понадобится помощь - создайте новое обращение :</b>",
            reply_markup=_new_ticket_kb(),
        )

    # ------------------------------------------------------------------
    # Callback: create
    # ------------------------------------------------------------------
    @dp.callback_query(F.data == "create")
    async def cb_create(call: types.CallbackQuery) -> None:
        ticket = await _get_open_ticket(call.from_user.id)
        if ticket:
            await call.answer("У вас уже есть открытое обращение", show_alert=True)
            return
        _user_state[call.from_user.id] = "choose_topic"
        await call.message.edit_text(
            "<tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> <b>Выберите тему обращения :</b>",
            reply_markup=_topic_kb(),
        )
        await call.answer()

    # ------------------------------------------------------------------
    # Callback: topic:*
    # ------------------------------------------------------------------
    @dp.callback_query(F.data.startswith("topic:"))
    async def cb_topic(call: types.CallbackQuery) -> None:
        topic_key = call.data.split(":", 1)[1]
        topic_label = TOPIC_LABELS.get(topic_key, "📝 Другое")
        _user_state[call.from_user.id] = f"write:{topic_key}"
        await call.message.edit_text(
            f"<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Тема : <b>{topic_label}</b>\n\n"
            "<b>Опишите проблему или вопрос - отправьте следующим сообщением :</b>"
        )
        await call.answer()

    # ------------------------------------------------------------------
    # Callback: status
    # ------------------------------------------------------------------
    @dp.callback_query(F.data == "status")
    async def cb_status(call: types.CallbackQuery) -> None:
        ticket = await _get_open_ticket(call.from_user.id)
        if not ticket:
            await call.answer("Нет открытых обращений", show_alert=True)
            return
        from support_db import get_messages
        msgs = await get_messages(ticket["id"])
        admin_replies = sum(1 for m in msgs if not m["from_user"])
        await call.answer(
            f"Обращение #{ticket['id']} · {len(msgs)} сообщ. · {admin_replies} ответов от команды",
            show_alert=True,
        )

    # ------------------------------------------------------------------
    # Callback: close
    # ------------------------------------------------------------------
    @dp.callback_query(F.data == "close")
    async def cb_close(call: types.CallbackQuery) -> None:
        ticket = await _get_open_ticket(call.from_user.id)
        if not ticket:
            await call.answer("Нет открытых обращений", show_alert=True)
            return
        _user_state.pop(call.from_user.id, None)
        from support_db import close_ticket as db_close_ticket
        await db_close_ticket(ticket["id"])
        await call.message.edit_text(
            f"<tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> <b>Обращение #{ticket['id']} закрыто.</b>\n\n"
            "<b>Спасибо! Если нужна помощь - создайте новое обращение :</b>",
            reply_markup=_new_ticket_kb(),
        )
        await call.answer("Обращение закрыто")

    # ------------------------------------------------------------------
    # Callback: back
    # ------------------------------------------------------------------
    @dp.callback_query(F.data == "back")
    async def cb_back(call: types.CallbackQuery) -> None:
        _user_state.pop(call.from_user.id, None)
        await call.message.edit_text(
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Служба поддержки Cute</b>\n\n"
            "Нажмите кнопку чтобы создать обращение :",
            reply_markup=_main_menu_kb(),
        )
        await call.answer()

    # ------------------------------------------------------------------
    # Фото от игрока
    # ------------------------------------------------------------------
    @dp.message(F.photo)
    async def handle_photo(message: types.Message) -> None:
        from support_db import get_or_create_ticket, add_user_message
        user = message.from_user
        state = _user_state.get(user.id, "")

        # Берём file_id наибольшего размера
        file_id = message.photo[-1].file_id
        caption = (message.caption or "").strip()

        # Нельзя прикрепить фото к апелляции или при выборе темы
        if state.startswith("appeal:") or state.startswith("write:"):
            await message.answer(
                "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Сначала отправьте текстовое описание, потом можно прикрепить фото.</b>",
            )
            return

        ticket = await _get_open_ticket(user.id)
        if not ticket:
            await message.answer(
                "<b><tg-emoji emoji-id='5388591472800986666'>✌</tg-emoji> У вас нет открытых обращений. Сначала создайте обращение :</b>",
                reply_markup=_main_menu_kb(),
            )
            return

        try:
            await add_user_message(ticket["id"], caption, photo_file_id=file_id)
        except Exception:
            logger.exception("add_user_message (photo) failed user_id=%s", user.id)
            await message.answer("<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> Не удалось сохранить фото. Попробуйте ещё раз.")
            return

        await message.answer("<tg-emoji emoji-id='5766879414704935108'>🖼</tg-emoji> <b>Фото добавлено к обращению.</b>", reply_markup=_ticket_open_kb())

        name = _display_name(user)
        preview = f"[фото]{(' — ' + caption) if caption else ''}"
        await _notify_admins(
            f"<tg-emoji emoji-id='5766879414704935108'>🖼</tg-emoji> <b>Фото в тикете #{ticket['id']}</b>\n"
            f"<b>От : {name}\n{preview}</b>"
        )

    # ------------------------------------------------------------------
    # Текстовые сообщения
    # ------------------------------------------------------------------
    @dp.message(F.text)
    async def handle_text(message: types.Message) -> None:
        from support_db import get_or_create_ticket, add_user_message
        user = message.from_user
        state = _user_state.get(user.id, "")

        # Апелляция бана
        if state.startswith("appeal:"):
            ban_reason = state.split(":", 1)[1]
            appeal_text = (message.text or "").strip()
            _user_state.pop(user.id, None)

            if len(appeal_text) < 10:
                await message.answer(
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Слишком короткое сообщение. Опишите ситуацию подробнее :</b>"
                )
                _user_state[user.id] = state
                return

            if len(appeal_text) > 1000:
                await message.answer("<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Максимум 1.000 символов. Сократите текст :</b>")
                _user_state[user.id] = state
                return

            try:
                from admin_appeals import submit_appeal as _submit_appeal
                result = await _submit_appeal(
                    user.id,
                    appeal_text,
                    username=user.username or "",
                    first_name=user.first_name or "",
                    ban_reason=ban_reason,
                )
                await message.answer(
                    f"<tg-emoji emoji-id='5400289821253990206'>📝</tg-emoji> <b>Апелляция #{result['id']} отправлена!</b>\n\n"
                    "<b>Старший Админ-состав рассмотрит её в ближайшее время.</b>\n"
                    "<b>Вы получите уведомление в личные сообщения когда будет принято окончательное решение.</b>\n\n"
                    "<blockquote><b><i>Среднее время ответа : до 24 часов.</i></b></blockquote>"
                )
            except ValueError as e:
                await message.answer(f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> {e}")
            except Exception as exc:
                logger.exception("appeal submit failed user_id=%s", user.id)
                await message.answer("<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Техническая ошибка. Попробуйте позже или напишите /start. Если ошибка останется, напишите одному из разработчиков проекта @JerichoCute / @mentyrha</b>")
            return

        # Ждём описание для нового тикета
        if state.startswith("write:"):
            topic_key = state.split(":", 1)[1]
            topic_label = TOPIC_LABELS.get(topic_key, "<tg-emoji emoji-id='6021435576513730578'>📋</tg-emoji> Другое")
            _user_state.pop(user.id, None)

            try:
                ticket_id = await get_or_create_ticket(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    subject=topic_label,
                )
                await add_user_message(ticket_id, message.text)
            except Exception as exc:
                logger.exception("Ошибка создания тикета user_id=%s", user.id)
                await message.answer(
                    f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Техническая ошибка : <code>{type(exc).__name__}: {str(exc)[:300]}</code>\n\n</b>"
                    "<b>Сообщите эту ошибку администратору.</b>"
                )
                return

            await message.answer(
                f"<tg-emoji emoji-id='5260463209562776385'>✅</tg-emoji> <b>Обращение #{ticket_id} создано!</b>\n"
                f"<b>Тема : {topic_label}\n\n</b>"
                "<blockquote><b>Мы ответим как можно скорее. Можете добавить уточнения просто напишите.</b></blockquote>",
                reply_markup=_ticket_open_kb(),
            )

            name = _display_name(user)
            preview = message.text[:150] + ("…" if len(message.text) > 150 else "")
            await _notify_admins(
                f"<tg-emoji emoji-id='4929524417354007168'>🗃</tg-emoji> <b>Новое обращение #{ticket_id}</b>\n"
                f"<b>От : {name}</b>"
                + (f"<b> (@{user.username})</b>" if user.username else "") + "\n"
                f"<b>Тема : {topic_label}\n\n</b>"
                f"<b>{preview}\n\n</b>"
                "<blockquote><i>Раздел «Поддержка» в панели администратора.</i></blockquote>"
            )
            return

        # Добавляем к существующему открытому тикету
        ticket = await _get_open_ticket(user.id)
        if ticket:
            try:
                await add_user_message(ticket["id"], message.text)
            except Exception as exc:
                logger.exception("add_user_message failed")
                await message.answer(f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Ошибка : <code>{type(exc).__name__}: {str(exc)[:300]}</code></b>")
                return

            await message.answer(
                "<tg-emoji emoji-id='5472239203590888751'>📩</tg-emoji> <b>Сообщение добавлено к обращению.</b>",
                reply_markup=_ticket_open_kb(),
            )
            name = _display_name(user)
            preview = message.text[:150] + ("…" if len(message.text) > 150 else "")
            await _notify_admins(
                f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> <b>Новое сообщение в тикете #{ticket['id']}</b>\n"
                f"<b>От : {name}\n\n{preview}</b>"
            )
        else:
            await message.answer(
                "<b><tg-emoji emoji-id='5391143319029968523'>🤙</tg-emoji> У вас нет открытых обращений. Создайте новое :</b>",
                reply_markup=_main_menu_kb(),
            )

    from bot_polling import run_polling
    await run_polling(
        dp, bot,
        label="support-bot",
        allowed_updates=["message", "callback_query"],
    )
