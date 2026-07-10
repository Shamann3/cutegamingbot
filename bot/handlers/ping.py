from main import *



@dp.message()
async def ping(message: Message):
    # Проверяем, что текст начинается с "пинг" и есть текст после него
    if message.text.lower().startswith("пинг3333 "):
        mention_text = message.text[5:]  # Текст после слова "пинг"

        try:
            # Получаем пользователей из таблицы memberchat по chat_id
            chat_id = message.chat.id
            users = await db.get_users_by_chat_id(chat_id)

            if not users:
                await message.answer("В этой группе нет пользователей в базе данных.")
                return

            print(f"Найдено {len(users)} пользователей в базе данных.")  # Отладка: количество пользователей

            # Создаем список упоминаний с текстом, но без имен пользователей
            mentions = [
                f'<a href="tg://user?id={user_id}">{mention_text}</a>'
                for user_id, name in users
            ]

            # Объединяем упоминания через запятую
            final_message = ", ".join(mentions)

            # Отправляем сообщение с упоминаниями
            await message.answer(final_message, parse_mode="HTML")

        except Exception as e:
            print(f"Ошибка: {e}")  # Отладка: ошибка
            await message.answer("Произошла ошибка при обработке запроса.")

