from main import *

from bot.funcs.whisper_open import (
    BOT_OPEN,
    arm_wait,
    ask_text,
    claim_wait,
    group_has_secret,
    keep_whisper,
    present_whisper,
    split_address,
    waiting,
    wait_owner,
    whisper_body,
)


async def store_temp_whisper(sender_id: int, receiver_id: int, message: str, ttl: int = 180):
    """Старый ящик. Новые шёпоты живут в whisper_open."""
    temp_whispers[receiver_id] = {
        'sender_id': sender_id,
        'message': message
    }
    await asyncio.sleep(ttl)
    temp_whispers.pop(receiver_id, None)


async def _person_id(kind: str, value: str):
    if kind == "id":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return await db.get_user_id_by_username(str(value or "").lstrip("@").lower())


@dp.message()
async def shep3412(message: Message):
    if not message.text or message.from_user is None:
        return
    body = whisper_body(message.text)
    if body is None:
        return
    reply_user = getattr(getattr(message, "reply_to_message", None), "from_user", None)
    target, secret = split_address(body, plain=reply_user is None)
    if target is None and reply_user is None:
        await message.reply("Напишите: шепнуть @имя текст")
        return
    if target is None:
        receiver_id = reply_user.id
        receiver_name = await db.get_user_first_name(receiver_id) or reply_user.first_name or ""
    else:
        receiver_id = await _person_id(target[0], target[1])
        if not receiver_id:
            await message.reply("Такого человека нет. Напишите @имя, ссылку или id.")
            return
        receiver_name = await db.get_user_first_name(receiver_id) or ""
    sender_id = message.from_user.id
    sender_name = await db.get_user_first_name(sender_id) or message.from_user.first_name or ""
    if secret:
        try:
            await _post_card(message.bot, {
                "sender_id": sender_id,
                "receiver_id": int(receiver_id),
                "sender_name": sender_name,
                "receiver_name": receiver_name,
                "chat_id": message.chat.id,
            }, secret)
        except Exception as exc:
            print(f"[WHISPER] card fail {type(exc).__name__}")
            await message.reply("Шёпот не отправился. Напишите его ещё раз.")
            return
        try:
            await message.delete()
        except Exception:
            pass
        return
    leaked = group_has_secret(secret)
    token = arm_wait(
        sender_id=sender_id,
        receiver_id=receiver_id,
        sender_name=sender_name,
        receiver_name=receiver_name,
        chat_id=message.chat.id,
    )
    try:
        await message.delete()
    except Exception:
        pass
    note = ask_text(receiver_name, leaked=leaked)
    try:
        await message.bot.send_message(sender_id, note, parse_mode="HTML")
        return
    except Exception:
        pass
    button = InlineKeyboardButton(text="Написать шёпот", url=f"{BOT_OPEN}?start=whis_{token}")
    await message.answer(
        "Напишите шёпот боту в личные сообщения. В группе текста не будет.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


async def _post_card(bot, row: dict, text: str) -> None:
    sender_id = int(row["sender_id"]) if "sender_id" in row else 0
    receiver_id = int(row["receiver_id"])
    sender_name = row.get("sender_name") or ""
    receiver_name = row.get("receiver_name") or ""
    receiver_username = await db.get_username_by_user_id(receiver_id)
    sender_username = await db.get_username_by_user_id(sender_id) if sender_id else None
    kept = await keep_whisper(
        sender_id=sender_id,
        receiver_id=receiver_id,
        sender_name=sender_name,
        text=text,
    )
    name_link1 = await create_user_link(receiver_id, receiver_name, receiver_username)
    name_link2 = await create_user_link(sender_id, sender_name, sender_username)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Прочитать шёпот", callback_data=f"wh:{kept}")
    ]])
    await bot.send_message(
        int(row["chat_id"]),
        f"💬 <b>{name_link1}, вам шепнули</b>\n<i>от {name_link2}</i>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


async def accept_whisper_private(message: Message) -> bool:
    """Личный текст шёпота. В группу он не попадает."""
    if message.chat.type != "private" or not message.text or message.from_user is None:
        return False
    if message.text.startswith("/"):
        return False
    if waiting(message.from_user.id) is None:
        return False
    text = message.text.strip()
    if text.lower() in {"прошептать", "шепнуть", "шептнуть"}:
        await message.answer("Напишите сам текст шёпота.")
        return True
    row = claim_wait(message.from_user.id)
    if row is None:
        return False
    row["sender_id"] = message.from_user.id
    try:
        await _post_card(message.bot, row, text)
    except Exception as exc:
        print(f"[WHISPER] card fail {type(exc).__name__}")
        await message.answer("Шёпот не отправился. Напишите его ещё раз.")
        arm_wait(
            sender_id=message.from_user.id,
            receiver_id=row["receiver_id"],
            sender_name=row.get("sender_name") or "",
            receiver_name=row.get("receiver_name") or "",
            chat_id=row["chat_id"],
        )
        return True
    await message.answer("Шёпот отправлен. В группе только карточка, без текста.")
    return True


async def remind_whisper_wait(message: Message, token: str) -> bool:
    owner = wait_owner(token)
    if owner is None or message.from_user is None or int(message.from_user.id) != owner:
        return False
    row = waiting(owner)
    if row is None:
        return False
    await message.answer(ask_text(row.get("receiver_name") or "", leaked=False), parse_mode="HTML")
    return True


@dp.callback_query(lambda c: c.data and c.data.startswith("wh:"))
async def open_whisper_button(callback_query: types.CallbackQuery):
    await present_whisper(callback_query)

@dp.callback_query(lambda c: c.data.startswith('view_message_'))
async def asdasdview_message(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    receiver_id = int(callback_query.data.split('_')[-1])

    if user_id == receiver_id:
        whisper_data = temp_whispers.get(receiver_id)

        if whisper_data:
            whisper_message = whisper_data['message']
            # Не удаляем здесь! Удаление происходит в фоновом очистителе
            await callback_query.answer(whisper_message, show_alert=True)
        else:
            await callback_query.answer("⏰ Срок действия сообщения истёк", show_alert=True)
    else:
        await callback_query.answer("🤷🏽 Это сообщение не для вас")
