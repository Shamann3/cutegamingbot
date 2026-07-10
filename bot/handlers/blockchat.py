from main import *


@dp.message()
async def blockchat(message: Message):
    parts = message.text.split()

    if len(parts) >= 2 and parts [ 0 ] in [ "разблокировать" , "Разблокировать" ]:
        target_group_info = parts [ 1 ]  # Информация о группе или пользователе
        target_group_id = None
        user_id = message.from_user.id

        # Проверка прав
        if user_id != 6801702632:
            await message.reply("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверка формата ID или username
        if target_group_info.isdigit():  # Если это ID (пользователь или группа)
            target_group_id = int(target_group_info)

        elif target_group_info.startswith("@"):  # Если это username
            username = target_group_info [ 1: ]  # Извлекаем username
            target_group_id = await db.get_user_id_by_username(username)  # Получаем ID

        elif target_group_info.startswith("https://t.me/"):  # Если это ссылка на пользователя или группу
            username = target_group_info.replace("https://t.me/" , "")
            username = username.split("/") [ 0 ]  # Удаляем дополнительные параметры
            target_group_id = await db.get_user_id_by_username(username)  # Получаем ID

        # Проверка на ID группы (начинается с '-' или '-100' для групп)
        elif target_group_info.startswith("-") or target_group_info.startswith("-100"):
            target_group_id = int(target_group_info)  # Приводим к типу int

        # Проверка формата ID
        if target_group_id is not None:
            try:
                # Проверка, является ли ID группой (ID группы начинается с '-')
                if str(target_group_id).startswith("-"):
                    print(f"Целевой ID группы: {target_group_id}")  # Отладка: выводим целевой ID группы

                    # Проверка, заблокирована ли группа
                    is_banned = await db.is_group_banned(target_group_id)
                    if not is_banned:
                        await message.reply(
                            f"💭 <b>Группа с ID <code>{target_group_id}</code> не заблокирована.</b>" ,
                            parse_mode="HTML")
                        return  # Прекращаем выполнение, если группа не заблокирована

                    # Удаляем группу из таблицы banchat
                    await db.unban_group(target_group_id)  # Разблокируем группу

                    # Получаем имя группы по ID (если требуется)
                    name = await db.get_firstname_by_user_id(target_group_id)

                    # Форматируем имя группы для ответа
                    group_display = target_group_info
                    if target_group_info.startswith("@"):
                        group_display = f'<a href="tg://user?id={target_group_id}">{name}</a>'

                    if name is None:
                        name = "Неизвестная группа"

                    await message.reply(
                        f"⚜️ <b>{name} | {group_display} | <code>{target_group_id}</code>\n🔰 Разблокирована.</b>" ,
                        parse_mode="HTML" , disable_web_page_preview=True)

                    try:
                        await bot1.send_message(
                            chat_id=target_group_id ,
                            text=f"⚜️ <b>Вы разблокированы в боте.</b>\n\n🔰 <a href='https://t.me/HelperCute'>Поддержка бота</a>" ,
                            parse_mode="HTML" , disable_web_page_preview=True)
                    except Exception as e:
                        print(f"Не удалось отправить сообщение группе {target_group_id}: {e}")
                else:
                    # Обработка обычных пользователей
                    print(f"Целевой ID пользователя: {target_group_id}")  # Отладка

                    # Проверка на заблокирован ли пользователь
                    is_banned = await db.is_user_banned(target_group_id)
                    if not is_banned:
                        await message.reply(
                            f"💭 <b>Пользователь с ID <code>{target_group_id}</code> не заблокирован.</b>" ,
                            parse_mode="HTML")
                        return  # Прекращаем выполнение, если пользователь не заблокирован

                    # Разблокируем пользователя
                    await db.unban_user(target_group_id)

                    name = await db.get_firstname_by_user_id(target_group_id)  # Получаем имя пользователя
                    if name is None:
                        name = "Неизвестный пользователь"

                    await message.reply(
                        f"⚜️ <b>{name} | <code>{target_group_id}</code>\n🔰 Разблокирован.</b>" ,
                        parse_mode="HTML")

            except Exception as e:
                print(f"Ошибка при разблокировке: {e}")
                await message.reply(
                    f"❌ Не удалось разблокировать объект с ID <code>{target_group_id}</code>." ,
                    parse_mode="HTML")

        else:
            await message.reply("🛠 Неверный формат ID или не найден объект.")
    # Проверка на корректность команды
    if len(parts) >= 2 and parts [ 0 ] in [ "заблокировать" , "блок" , "Заблокировать" , "Блок" ]:
        target_user_info = parts [ 1 ]  # Информация о пользователе
        reason = ' '.join(parts [ 2: ]) if len(parts) > 2 else None  # Причина блокировки, если указана
        target_user_id = None

        user_id = message.from_user.id
        # Проверка, является ли пользователь создателем
        if user_id != 6801702632:
            return  # Если не создатель, прекращаем выполнение

        # Проверка формата ID или username
        if target_user_info.isdigit():  # Если это ID
            target_user_id = int(target_user_info)




        elif target_user_info.startswith("@"):  # Если это username
            username = target_user_info [ 1: ]  # Извлекаем username
            target_user_id = await db.get_user_id_by_username(username)  # Приводим к нижнему регистру

        elif target_user_info.startswith("https://t.me/"):  # Если это ссылка на пользователя
            username = target_user_info.replace("https://t.me/" , "")
            username = username.split("/") [ 0 ]  # Удаляем дополнительные параметры, если они есть
            target_user_id = await db.get_user_id_by_username(username)  # Приводим к нижнему регистру
        elif target_user_info.startswith(("-" , "-100")):  # Если это ID группы
            target_user_id = int(target_user_info)  # Приводим к типу int
        # Проверка формата ID группы
        print(target_user_id)
        if target_user_id is not None:
            if str(target_user_id).startswith("-"):
                try:
                    print(f"Целевой ID группы: {target_user_id}")  # Отладка: выводим целевой ID группы

                    # Проверка, заблокирована ли группа
                    is_banned = await db.is_group_banned(
                        target_user_id)  # Метод для проверки, заблокирована ли группа
                    if is_banned:
                        await message.reply(
                            f"⚠️ <b>Группа с ID <code>{target_user_id}</code> уже заблокирована.</b>" ,
                            parse_mode="HTML")
                        return  # Прекращаем выполнение, если группа уже заблокирована

                    # Блокируем группу, добавляем в базу данных
                    await db.ban_group(target_user_id)  # Блокируем группу

                    # Отправляем сообщение в группу о том, что она заблокирована
                    try:
                        await bot1.send_message(
                            chat_id=target_user_id , text="⚠️ <b>Группа была заблокирована администратором.</b>" ,
                            parse_mode="HTML")
                    except Exception as e:
                        print(f"Не удалось отправить сообщение в группу {target_user_id}: {e}")

                    # Выход из группы
                    try:
                        await bot1.leave_chat(target_user_id)
                    except Exception as e:
                        print(f"Не удалось выйти из группы {target_user_id}: {e}")

                    await message.reply(
                        f"⚜️ <b>Группа с ID <code>{target_user_id}</code> заблокирована.</b>" ,
                        parse_mode="HTML")
                    return
                except Exception as e:
                    print(f"Ошибка при блокировке группы {target_user_id}: {e}")
                    await message.reply(
                        f"💭 Не удалось заблокировать группу с ID <code>{target_user_id}</code>." ,
                        parse_mode="HTML")
            else:
                print(f"Целевой ID пользователя: {target_user_id}")  # Отладка: выводим целевой ID пользователя
                if await db.is_user_banned(target_user_id):
                    await message.reply(
                        f"💭 <b>Пользователь {target_user_info} уже заблокирован.</b>" , parse_mode="HTML")
                else:
                    # Получаем имя пользователя по ID
                    name = await db.get_firstname_by_user_id(target_user_id)
                    username34 = await db.get_username_by_id(target_user_id)

                    # Форматируем имя пользователя для ответа
                    user_display = target_user_info
                    if target_user_info.startswith("@"):
                        user_display = f'<a href="tg://user?id={target_user_id}">{name}</a>'

                    if name is None:
                        name = "Неизвестный"

                    if username34 is None:
                        username34 = ''

                    # Вызов функции ban_user с правильными аргументами
                    await db.ban_user(user_id=target_user_id , username=username34 , name=name , reason=reason)

                    await message.reply(
                        f"⚜️ <b>{name} | {user_display} | <code>{target_user_id}</code> | {reason or 'Не указана'}\n🔰 Заблокирован.</b>" ,
                        parse_mode="HTML")
                    try:
                        await bot1.send_message(
                            chat_id=target_user_id ,
                            text=f"💭 <b>Вы заблокированы в боте. Бот игнорирует ваши запросы.</b>\n📚 <b>Причина: <i>{reason or 'Не указана'}</i></b>\n\n🔰 <a href='https://t.me/HelperCute'>Поддержка бота</a>" ,
                            parse_mode="HTML" , disable_web_page_preview=True)
                    except Exception as e:
                        print(f"Не удалось отправить сообщение пользователю {target_user_id}: {e}")
        else:
            await message.reply("🛠 Пользователь не найден или указан неверный формат.")

