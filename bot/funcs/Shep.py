from main import *

from bot.funcs.whisper_open import keep_whisper, present_whisper, whisper_body


async def store_temp_whisper(sender_id: int, receiver_id: int, message: str, ttl: int = 180):
    """Старый ящик. Новые шёпоты живут в whisper_open."""
    temp_whispers[receiver_id] = {
        'sender_id': sender_id,
        'message': message
    }
    await asyncio.sleep(ttl)
    temp_whispers.pop(receiver_id, None)


@dp.message()
async def shep3412(message: Message):
    if not message.reply_to_message or not message.text or message.from_user is None:
        return
    body = whisper_body(message.text)
    if body is None:
        return
    target = message.reply_to_message.from_user
    if target is None:
        return
    if not body:
        await message.reply("Напишите текст после «прошептать».")
        return

    receiver_id = target.id
    sender_id = message.from_user.id
    sender_name = await db.get_user_first_name(sender_id)
    receiver_name = await db.get_user_first_name(receiver_id)
    receiver_username = await db.get_username_by_user_id(receiver_id)
    sender_username = await db.get_username_by_user_id(sender_id)
    token = await keep_whisper(
        sender_id=sender_id,
        receiver_id=receiver_id,
        sender_name=sender_name or message.from_user.first_name or "",
        text=body,
    )
    name_link1 = await create_user_link(receiver_id, receiver_name, receiver_username)
    name_link2 = await create_user_link(sender_id, sender_name, sender_username)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Прочитать шёпот", callback_data=f"wh:{token}")
    ]])
    message_text = (
        f"💬 <b>{name_link1}, вам шепнули</b>\n"
        f"<i>от {name_link2}</i>"
    )
    await message.answer(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    try:
        await message.delete()
    except Exception:
        pass


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
