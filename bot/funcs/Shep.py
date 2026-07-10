from main import *

# Временное хранилище шепотов (receiver_id -> whisper_data)


# Асинхронная функция для хранения шепота с автоочисткой
async def store_temp_whisper(sender_id: int, receiver_id: int, message: str, ttl: int = 180):
    temp_whispers[receiver_id] = {
        'sender_id': sender_id,
        'message': message
    }

    await asyncio.sleep(ttl)
    temp_whispers.pop(receiver_id, None)



@dp.message()
async def shep3412(message: Message):
    if message.reply_to_message:
        text = message.text.lower().strip()
        if text.startswith(("прошептать", "шепнуть")):
            receiver_id = message.reply_to_message.from_user.id
            sender_id = message.from_user.id
            whisper_message = text.replace("прошептать", "").replace("шепнуть", "").strip()

            sender_name = await db.get_user_first_name(sender_id)
            receiver_name = await db.get_user_first_name(receiver_id)
            receiver_username = await db.get_username_by_user_id(receiver_id)
            sender_username = await db.get_username_by_user_id(sender_id)

            # Сохраняем шепот с временем
            temp_whispers[receiver_id] = {
                'sender_id': sender_id,
                'message': whisper_message,
                'timestamp': time.time()
            }

            # Генерация ссылок и клавиатуры

            name_link1 = await create_user_link(receiver_id, receiver_name, receiver_username)
            name_link2 = await create_user_link(sender_id, sender_name, sender_username)

            button = InlineKeyboardButton(
                text="Посмотреть сообщение",
                callback_data=f"view_message_{receiver_id}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

            button_temp_whispers[receiver_id] = {'keyboard_join': keyboard}

            message_text = (
                f"💬 <b>{name_link1}, <i>вам отправили скрытое сообщение</i></b>\n"
                f"<b>👨‍💻 от </b><b>{name_link2}</b>"
            )

            await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
            await message.delete()
    button_temp_whispers.save()
    temp_whispers.save()

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
