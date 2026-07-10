from main import *
from bot.db_create.items_codec import decode_items, encode_items
import emoji




emoji_pattern = re.compile(
    "(?:"
    "[\U0001F600-\U0001F64F"  # Смайлы и эмоции
    "\U0001F300-\U0001F5FF"  # Символы и пиктограммы
    "\U0001F680-\U0001F6FF"  # Символы транспорта и карт
    "\U0001F1E0-\U0001F1FF"  # Флаги
    "\U0001F700-\U0001F77F"  # Алхимические символы
    "\U0001F780-\U0001F7FF"  # Дополнительные геометрические формы
    "\U0001F800-\U0001F8FF"  # Дополнительные стрелки
    "\U0001F900-\U0001F9FF"  # Дополнительные символы и пиктограммы
    "\U0001FA00-\U0001FA6F"  # Шахматные символы
    "\U0001FA70-\U0001FAFF"  # Символы и пиктограммы-А
    "\U00002700-\U000027BF"  # Декоративные элементы
    "]"
    "[\U0000200D\U0000FE0F]*"  # Необязательные zero-width joiner и вариационные селекторы
    ")+"
)


async def is_emoji(item_emoji):
    """Проверяет, является ли строка эмодзи, включая составные эмодзи.

    Args:
        item_emoji (str): Строка для проверки.

    Returns:
        bool: True, если строка является эмодзи (одиночным или составным), иначе False.
    """
    print(f"[DEBUG] Проверка значения: {item_emoji}")

    # Проверка, что передано строковое значение
    if not isinstance(item_emoji , str):
        print("[ERROR] Ошибка: входное значение не является строкой.")
        return False

    print("[DEBUG] Входное значение является строкой.")

    # Проверка на пустую строку
    if len(item_emoji) == 0:
        print("[ERROR] Ошибка: пустая строка.")
        return False

    # Проверка на одиночное эмодзи
    if emoji.is_emoji(item_emoji):
        print(f"[SUCCESS] Строка '{item_emoji}' является эмодзи.")
        return True

    # Проверка на составное эмодзи (эмодзи с несколькими символами)
    # Перебираем каждый символ строки и проверяем, является ли он эмодзи
    for char in item_emoji:
        if not emoji.is_emoji(char):
            print(f"[WARNING] Символ '{char}' не является эмодзи.")
            return False

    print(f"[SUCCESS] Строка '{item_emoji}' является составным эмодзи.")
    return True

async def generate_reset_button(column_name: str, user_id: int) -> InlineKeyboardMarkup:
    print('💭💭💭💭💭💭💭', column_name)

    reset_button = InlineKeyboardButton(
        text="Сбросить строку",
        callback_data=f"reset_row:{column_name}:{user_id}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[reset_button]])  # <-- вот здесь исправлено
    return keyboard
@dp.message()
async def editprofile(message: Message):
    message_parts = message.text.split()  # Разделяем сообщение по пробелам

    print(f"Получено сообщение: {message.text}")
    print(f"Разделено на части: {message_parts}")

    # Проверяем, что на 0 индексе слово "ид", а на 1 индексе есть эмодзи
    if len(message_parts) == 2:
        print(f"Количество частей в сообщении: {len(message_parts)}")

        if message_parts [ 0 ].lower() == "профильид":
            print(f"Первое слово в сообщении: 'ид', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]
            print(item_emoji)

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных с использованием асинхронного метода
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "idemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Используем асинхронную функцию для получения инвентаря
            user_items = await db.get_user_items_editprofile(user_id)

            if user_items:
                user_inventory = decode_items(user_items)
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)

                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b> Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)
        if message_parts [ 0 ].lower() == "профильюз":
            print(f"Первое слово в сообщении: 'юз', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "usernameemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)

            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)

        if message_parts [ 0 ].lower() == "профильимя":
            print(f"Первое слово в сообщении: 'имя', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "nameemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)

            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)

        if message_parts [ 0 ].lower() == "профильбаланс":
            print(f"Первое слово в сообщении: 'баланс', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "balanceemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)
        if message_parts [ 0 ].lower() == "профильвыиграно":
            print(f"Первое слово в сообщении: 'баланс', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "winamountemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)
        if message_parts [ 0 ].lower() == "профильбрак":
            print(f"Первое слово в сообщении: 'брак', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "marryemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)

        if message_parts [ 0 ].lower() == "профильреп3412":
            print(f"Первое слово в сообщении: 'реп3412', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "repemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем значение эмодзи из указанного столбца
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML",
                    reply_markup=keyboard)

        if message_parts [ 0 ].lower() == "профильлимит":
            print(f"Первое слово в сообщении: 'лимит', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "limitemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем текущее эмодзи из базы данных
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML", reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)
        if message_parts [ 0 ].lower() == "профильреф":
            print(f"Первое слово в сообщении: 'реф', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "refemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем текущее эмодзи из базы данных
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML",
                    reply_markup=keyboard)

        if message_parts [ 0 ].lower() == "профильпригласитель3412":
            print(
                f"Первое слово в сообщении: 'пригласитель3412', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]

            # Проверяем, является ли второй элемент эмодзи
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "prglemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя из базы данных
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем текущее эмодзи из базы данных
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)
        if message_parts [ 0 ].lower() == "профильдата":
            print(f"Первое слово в сообщении: 'дата', проверяем эмодзи на втором индексе: {message_parts [ 1 ]}")

            item_emoji = message_parts [ 1 ]
            print(f"На втором индексе найдено эмодзи: {item_emoji}")

            # Получаем инвентарь пользователя из базы данных
            print("Получаем текущий инвентарь пользователя")
            user_id = message.from_user.id
            column_name = "dataemo"  # Место для указания имени столбца
            keyboard = await generate_reset_button(column_name , user_id)

            # Получаем инвентарь пользователя
            user_inventory = await db.get_user_items(user_id)
            if user_inventory:
                print(f"Инвентарь пользователя: {user_inventory}")

                # Ищем название предмета по эмодзи в таблице dex
                item_name = await db.get_item_name_by_emoji(item_emoji)
                if item_name:
                    print(f"Название предмета для использования: {item_name}")

                    # Проверяем, есть ли предмет в инвентаре пользователя
                    if item_name in user_inventory:
                        print(f"Предмет {item_name} найден в инвентаре пользователя")

                        # Получаем эмодзи предмета через его название
                        emojiitem = await db.get_emoji_for_item(item_name)
                        print(f"Полученное эмодзи для предмета {item_name}: {emojiitem}")

                        if emojiitem == item_emoji:
                            print(f"Эмодзи предмета совпадает с указанным эмодзи: {emojiitem}")

                            # Получаем текущее эмодзи из базы данных
                            current_emoji = await db.get_current_emoji(user_id , column_name)
                            if current_emoji:
                                print(f"Текущее эмодзи в базе данных: {current_emoji}")

                                # Ищем название предмета по текущему эмодзи
                                current_item_name = await db.get_item_name_by_emoji(current_emoji)
                                if current_item_name:
                                    print(
                                        f"Название предмета для текущего эмодзи ({current_emoji}): {current_item_name}")
                                else:
                                    print(f"Название предмета для эмодзи {current_emoji} не найдено.")
                                    current_item_name = "Неизвестный предмет"

                                # Если эмодзи совпадает с текущим, не меняем
                                if current_emoji == item_emoji:
                                    await message.reply(
                                        f"❕ <b>У вас уже установлен эмодзи <code>{item_emoji}</code></b>" ,
                                        parse_mode="HTML" , reply_markup=keyboard)
                                    return  # Прерываем выполнение функции

                                # Возвращаем старое эмодзи обратно в инвентарь
                                await db.set_items(user_id , current_item_name , 1)
                                print(
                                    f"Возвращено старое эмодзи в инвентарь пользователя: {current_emoji} (Предмет: {current_item_name})")

                            # Обновляем эмодзи на новый
                            await db.update_emoji(user_id , item_emoji , column_name)
                            print(f"Эмодзи обновлено на: {item_emoji}")
                            await db.delete_user_inventory1(user_id , item_name)
                            await message.reply(
                                f"✅ <b>Эмодзи успешно обновлено на <code>{item_emoji}</code></b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                        else:
                            print(f"Эмодзи {item_emoji} не совпадает с эмодзи предмета {emojiitem}")
                            await message.reply(
                                f"🩶 <b>Эмодзи <code>{item_emoji}</code> не совпадает с предметом <code>{emojiitem}</code>.</b>" ,
                                parse_mode="HTML" , reply_markup=keyboard)
                    else:
                        print(f"Предмет {item_name} не найден в инвентаре пользователя")
                        await message.reply(
                            f"<code>{item_emoji}</code> <b>Предмет не найден в вашем инвентаре.</b>" ,
                            parse_mode="HTML")
                else:
                    print(f"Предмет с эмодзи {item_emoji} не найден в таблице dex")
                    await message.reply(
                        f"<code>{item_emoji}</code> <b>Предмет не найден в системе.</b>" ,
                        parse_mode="HTML" , reply_markup=keyboard)
            else:
                print(f"Инвентарь для пользователя с ID {user_id} не найден в базе данных")
                await message.reply(
                    "🩶 <b>Ваш инвентарь не найден в базе данных.</b>" , parse_mode="HTML" ,
                    reply_markup=keyboard)

@dp.callback_query(lambda call: call.data.startswith('reset_row'))
async def reset_row_handler(call: types.CallbackQuery):
    try:
        # Извлекаем column_name и user_id из callback_data
        parts = call.data.split(":")
        if len(parts) != 3:
            await call.answer("Неверный формат данных. Попробуйте снова.")
            return

        _, column_name, user_id = parts
        user_id = int(user_id)  # Преобразуем user_id в целое число для безопасности
        print(f"🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️🐻‍❄️  Получено column_name: {column_name}, user_id: {user_id}")

        # Получаем эмодзи из столбца для пользователя
        emoji = await db.fetch_column_value(user_id, column_name)

        if emoji:  # Если эмодзи найдено
            emoji = str(emoji).strip()  # Убираем лишние пробелы, если есть

            # Получаем название предмета по эмодзи
            item_name = await db.find_item_name_by_emoji(emoji)

            # Выдаем предмет пользователю
            await db.set_items(user_id, item_name, 1)
            result_message = await db.reset_column_value_if_exists(user_id, column_name)
            result_message += f"\nПредмет найден и выдан: {item_name}."
            print(result_message)  # Логирование результата

            # Уведомляем пользователя об успешном сбросе
            await call.message.edit_text(
                f"<b>✅ Эмодзи строки успешно сброшено</b>", parse_mode="HTML"
            )
        else:
            # Если эмодзи не найдено
            await call.answer("Эмодзи не найдено или уже сброшено.")
    except ValueError:
        await call.answer("Ошибка преобразования user_id. Убедитесь, что данные корректны.")
    except Exception as e:
        print(f"Ошибка: {e}")
        await call.answer("Произошла ошибка при сбросе строки. Попробуйте снова.")