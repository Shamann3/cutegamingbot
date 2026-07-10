
from main import bot1, db, dp, types,InlineKeyboardMarkup,InlineKeyboardButton # Импортируйте только необходимые элементы


chat_id_sub = -1002314697460
async def check_sub_channel(user_id):
    try:
        chat_member = await bot1.get_chat_member(chat_id_sub, user_id)
        is_subscribed = chat_member.status in [types.ChatMemberStatus.MEMBER, types.ChatMemberStatus.ADMINISTRATOR, types.ChatMemberStatus.CREATOR]
        return is_subscribed
    except Exception as e:
        return False

async def check_sub_channel(user_id):
    try:
        chat_member = await bot1.get_chat_member(chat_id_sub, user_id)  # Проверка статуса подписки пользователя
        is_subscribed = chat_member.status in [
            types.ChatMemberStatus.MEMBER,
            types.ChatMemberStatus.ADMINISTRATOR,
            types.ChatMemberStatus.CREATOR
        ]
        #if is_subscribed:
            #print(f"Пользователь с ID {user_id} подписан на группу.")
        #else:
            #print(f"Пользователь с ID {user_id} НЕ подписан на группу.")
        return is_subscribed
    except Exception as e:
        print(f"Ошибка при проверке подписки для пользователя {user_id}: {str(e)}")
        return False
@dp.callback_query(lambda c: c.data == 'subcutechat3')
async def close_bonus_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    user_sub = await db.get_user_subscription(user_id)  # Получаем значение подписки пользователя
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте")
        return
    if user_sub is None:
        await callback_query.message.answer("Ошибка: Не удалось получить информацию о подписке.")
        print("Ошибка: Не удалось получить информацию о подписке пользователя.")
        return

    if user_sub == 1:
        await callback_query.message.answer(
            "🛠 <b>Вы уже получили бесплатные куты за подписку.</b>" ,
            parse_mode="HTML")
        print(f"Пользователь {user_id} не может использовать функцию, так как подписка = 1.")
        return

    # Если подписка = 0, продолжаем выполнение функции
    group_username = await db.get_group_username(chat_id_sub)  # Получаем username группы по chat_id


    # Создаем инлайн-кнопки с названием группы
    inline_keyboard = InlineKeyboardMarkup()
    inline_keyboard.add(InlineKeyboardButton("👻 Присоединиться" , url=f"https://t.me/CuteGamingNews"))
    inline_keyboard.add(InlineKeyboardButton("Проверить" , callback_data='donesub'))
    inline_keyboard.add(InlineKeyboardButton("✖️" , callback_data="9close_bonus"))

    #await callback_query.message.answer('💰')
    await callback_query.message.edit_text(
        "💰 <b>Чтобы получить бесплатные 1 кут - зайдите в наш канал!</b>" ,
        parse_mode="HTML" , reply_markup=inline_keyboard)


@dp.callback_query(lambda c: c.data == 'donesub')
async def sub_channel_done(callback: types.CallbackQuery):

    user_id = callback.from_user.id
    print(f"Пользователь {user_id} запросил проверку подписки.")

    if await check_sub_channel(user_id):
        await callback.answer()
        new_bonus = 1
        await callback.message.edit_text(f"<b>✅ Готово! Вы получили {new_bonus} Кут за подписку на нашу группу!</b>", parse_mode="HTML")  # Изменяем текст сообщения на "Все готово!"
        balance = await db.get_user_balance(user_id)
        win = balance + new_bonus

        await db.update_user_balance(user_id , win)
        await db.cutehistory_plus(user_id , win , "sub за подписку на нашу группу")

        await db.update_subscription(user_id)
        print(f"Пользователь {user_id} подтвердил подписку. Сообщение обновлено.")
    else:
        await callback.answer("⚙️ Для получения награды вам необходимо быть участником нашего канала" , show_alert=True)
        print(f"Пользователь {user_id} не подписан на группу. Показано сообщение об ошибке.")

    #user_id = callback.from_user.id
    #print(f"Пользователь {user_id} запросил проверку подписки.")

    # Проверяем подписку пользователя на каналы
    #subscriptions = await check_user_subscription(user_id)

    # Проверяем, на какие каналы пользователь не подписан
    #not_subscribed_channels = [ (chat_id , "𝐍𝐞𝐰𝐬 | 𝐂𝐮𝐭𝐞" , "CuteGamingNews") if chat_id == -1002314697460 else (
    #    chat_id , "𝐅𝐚𝐦𝐢𝐥𝐲 𝐂𝐮𝐭𝐞 | 𝐆𝐫𝐨𝐮𝐩𝐬" , "FamilyCuteGroups") for chat_id , is_subscribed in subscriptions.items() if
    #                            not is_subscribed ]

    # Очистка памяти после использования словаря
    #del subscriptions

    # Если пользователь подписан на все каналы
    #if not not_subscribed_channels:
        #await callback.answer()
        #new_bonus = 1
        #await callback.message.edit_text(
        #    f"<b>✅ Готово! Вы получили {new_bonus} Кут за подписку! Спасибо!</b>" ,
        #    reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("✖️" , callback_data="9close_bonus")) ,
        #    parse_mode="HTML")
        #balance = await db.get_user_balance(user_id)
        #win = balance + new_bonus

        #await db.update_user_balance(user_id , win)
        #await db.cutehistory_plus(user_id , win , "donesub за подписку на нашу группу")
        #await db.update_subscription(user_id)
        #print(f"Пользователь {user_id} подтвердил подписку. Сообщение обновлено.")

    #else:
        # Если не подписан на все каналы, показываем ошибку и изменяем клавиатуру
        #await callback.answer("⚙️ Для получения награды вам необходимо быть участником нашего канала" , show_alert=True)
        #print(f"Пользователь {user_id} не подписан на все каналы. Показано сообщение об ошибке.")

        # Создаем инлайн-кнопки для каналов, на которые пользователь не подписан
        #buttons = [ ]

        #for chat_id , channel_name , channel_username in not_subscribed_channels:
            #channel_url = f"https://t.me/{channel_username}"
            #button = InlineKeyboardButton(text=channel_name , url=channel_url)
            #buttons.append([ button ])  # Wrap each button in a list for inline_keyboard format

        # Создаем клавиатуру с кнопками
        #keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Добавляем кнопки "Проверить" и "Закрыть" вручную в inline_keyboard
        #check_button = InlineKeyboardButton(text="☁️ Проверить ☁️" , callback_data='donesub')
        #close_button = InlineKeyboardButton(text=" " , callback_data="9close_bonus", style="default" ,
                #icon_custom_emoji_id="5226660202035554522")
        #keyboard.inline_keyboard.append([ check_button ])  # Первая кнопка в своем ряду
        #keyboard.inline_keyboard.append([ close_button ])  # Вторая кнопка в своем ряду

        # Главная клавиатура

        #try:
            #await callback.message.edit_text(
                #"💰 <b>Чтобы получить 1 бесплатный кут - присоединитесь в наши каналы!</b>" , parse_mode="HTML" ,
                #reply_markup=keyboard)
        #except TelegramAPIError as e:
            # Игнорируем ошибку, если контент сообщения не изменился
            #print(f"Пользователь {user_id} пытался обновить сообщение, но оно не было изменено.")

        # Очистка списка после использования
        #del not_subscribed_channels