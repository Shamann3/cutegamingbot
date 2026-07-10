from main import *


async def update_chat_information(chat_id , chat_title , chat_username , user_id):
    """Получает и обновляет информацию о чате без получения администраторов."""

    # Получаем только данные о чате без администраторов
    chat = await measure_time(
        bot1.get_chat(chat_id) , "Получение информации о чате")

    # Формируем ссылку на чат и тип группы
    chatlink = f"https://t.me/{chat_username}" if chat_username != "нет" else chat.invite_link or "Приватная ссылка не найдена"
    description = chat.description or ""
    channel_id = chat.linked_chat_id
    supergroup = "Супергруппа" if chat.type in [ ChatType.SUPERGROUP , ChatType.GROUP ] else "Приватная"

    # Получаем данные о связанном канале (если есть)
    channel_link = ""
    if channel_id:
        linked_channel = await bot1.get_chat(channel_id)
        channel_link = linked_channel.invite_link or f"https://t.me/{linked_channel.username}"

    # Обновляем или добавляем информацию о чате в базе данных без данных администраторов
    current_date = time.strftime('%Y-%m-%d %H:%M:%S')  # Текущая дата
    await measure_time(
        db.update_or_insert_chat_opt(
            chat_id=chat.id , namechat=chat.title , usernamechat=chat.username , chatlink=chatlink ,
            description=description , channel=channel_link , supergroup=supergroup ,
            members_count=await bot1.get_chat_member_count(chat_id) , current_date=current_date) ,
        "Обновление информации о чате")

@dp.message()
async def updatechat(message: Message):
    if message.text.lower() in ["обновить группу","обновить группы","обновить чат","обновить чаты","обновить информацию чатов","обновить информацию групп","обновление групп","обновление чатов","обнова групп","обнова чатов", "update chat info","update chat"]:
        user_id = message.from_user.id
        if user_id == 6801702632:
            chat_id = message.chat.id
            chat_title = message.chat.title
            chat_username = message.chat.username if message.chat.username else "нет"


            # Вызываем асинхронную функцию для обновления информации о чате
            await update_chat_information(chat_id, chat_title, chat_username, user_id)
            print("Информация о чате была обновлена.")
