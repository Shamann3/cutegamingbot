from main import *

user_message_history1 = {}
async def generate_buttons_moneyhistorygame(page_number , num_pages):
    navigation_buttons = [ ]

    if page_number == 1 and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜" , callback_data=f"next_pagemoneyhistorygame_{page_number + 1}"))
    elif page_number == num_pages and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙" , callback_data=f"prev_pagemoneyhistorygame_{page_number - 1}"))
    else:
        row_buttons = [ ]
        if page_number > 1:
            row_buttons.append(
                types.InlineKeyboardButton(
                    text="🔙" , callback_data=f"prev_pagemoneyhistorygame_{page_number - 1}"))
        if page_number < num_pages:
            row_buttons.append(
                types.InlineKeyboardButton(
                    text="🔜" , callback_data=f"next_pagemoneyhistorygame_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons
async def generate_buttons_moneyhistory(page_number , num_pages):
    navigation_buttons = [ ]

    if page_number == 1 and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜" , callback_data=f"next_pagemoneyhistory_{page_number + 1}"))
    elif page_number == num_pages and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙" , callback_data=f"prev_pagemoneyhistory_{page_number - 1}"))
    else:
        row_buttons = [ ]
        if page_number > 1:
            row_buttons.append(
                types.InlineKeyboardButton(text="🔙" , callback_data=f"prev_pagemoneyhistory_{page_number - 1}"))
        if page_number < num_pages:
            row_buttons.append(
                types.InlineKeyboardButton(text="🔜" , callback_data=f"next_pagemoneyhistory_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons
@dp.message()
async def history(message: Message):
    if message.text.lower() in [ 'история' , 'История','Просмотр истории','просмотр истории','просмотреть историю','Просмотреть историю' ]:
        user_id = message.from_user.id

        button = InlineKeyboardButton(text="Переводы" , callback_data="translationsgames")

        # Создаём клавиатуру с этой кнопкой
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
            #InlineKeyboardButton("Игры" , callback_data='gameshistory'))

        phrases = [ "📜 Великая тайна" , "📖 Страницы прошлого" , "🏺 Древние свитки" , "🔍 По следам прошлого" ,
            "🕰 Память веков" , "🗿 Памятные моменты" , "🕮 Записки времени" , "⏳ Взгляд в прошлое" ,
            "🌍 Исторический путь" , "🏛 Наследие эпохи" , "🎞 Исторический сюжет" , "📚 Книга времён" ,
            "🏹 Великие события" , "🌌 Хроники миров" , "🔮 Магия прошлого" ]

        # Выбираем случайную фразу
        selected_phrase = random.choice(phrases)

        # Отправляем сообщение с выбранной фразой
        s_m_h = await message.answer(f"⏳" , reply_markup=keyboard)

        user_message_history1 [ user_id ] = s_m_h.message_id
        print(user_message_history1)

    if message.text.lower() in [ 'история транзакций' , 'История транзакций' , 'история переводов' ,
                                 'История переводов' , 'Мои переводы' , 'мои переводы' , 'Мои транзакции' ,
                                 'мои транзакции' ]:
        user_id = message.from_user.id
        transactions = await db.get_transaction_history(user_id , limit=7 , offset=0)
        total_transactions = await db.get_transaction_count(user_id)
        num_pages = (total_transactions + 9) // 7  # Округляем вверх

        if not transactions:
            await message.reply(
                '⚠️ На данный момент у вас нет транзакций' , parse_mode="HTML" ,
                disable_web_page_preview=True)
            return

        history_text = "<b>📝 История ваших транзакций</b>\n\n"

        for transaction in transactions:
            if transaction [ 0 ] == user_id:
                transaction_type = "🚀 Отправлено"
                transaction1 = '📍 Получатель'
                other_user_id = transaction [ 1 ]
            else:
                transaction_type = "✅ Получено"
                transaction1 = '🍀 Отправитель'
                other_user_id = transaction [ 0 ]

            other_user_info = await db.get_user_info_by_id(other_user_id)
            first_name = other_user_info [ "first_name" ]
            username = await db.get_username_by_user_id(other_user_id)
            name_link = await create_user_link(other_user_id , first_name , username)
            other_user_link = f'{name_link}'


            history_text += (f"➖➖➖➖➖➖➖\n"
                             f"<b>{transaction_type} : {transaction [ 2 ]:,} кут</b>\n"
                             f"<b>{transaction1} : {other_user_link}</b>\n"
                             f"<b>⌚️ Дата : {transaction [ 3 ]}</b>\n\n")

        buttons = await generate_buttons_moneyhistory(1 , num_pages)
        markup = types.InlineKeyboardMarkup(row_width=2)
        deletehistorymoney = InlineKeyboardButton(text=" " , callback_data="deletehistorymoneybuttons", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        # Допустим, buttons - это список кнопок, который вы хотите добавить

        # Создаём клавиатуру, добавляем кнопки в строки
        markup = InlineKeyboardMarkup(
            inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                [ deletehistorymoney ]  # Кнопка для удаления истории в новой строке
            ])
        sent_message = await message.reply(
            history_text , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=markup)

        # Сохраняем ID сообщения и пользователя для дальнейшей проверки
        user_message_mapping [ user_id ] = sent_message.message_id
        print(user_message_mapping)

    if message.text.lower() in [ 'история игр34123412' , 'история игр34123412' ]:
        user_id = message.from_user.id

        # Извлечение истории игр с сортировкой по дате (новее первыми)
        games_history = await db.get_user_games_history(user_id , limit=7 , offset=0)
        total_games = await db.get_user_games_count(user_id)
        num_pages = (total_games + 6) // 7  # Округляем вверх

        if not games_history:
            await message.reply(
                '⚠️ Вы еще не играли в игры' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        history_text = "<b>📝 История ваших игр</b>\n\n"

        for game in games_history:
            game_info = [ ("Куб" , game [ 0 ] , game [ 1 ]) , ("Боулинг" , game [ 2 ] , game [ 3 ]) ,
                ("Баскетбол" , game [ 4 ] , game [ 5 ]) , ("Слоты" , game [ 6 ] , game [ 7 ]) ,
                ("Трейд" , game [ 8 ] , game [ 9 ]) , ("Краш" , game [ 10 ] , game [ 11 ]) ,
                ("Мины" , game [ 12 ] , game [ 13 ]) , ("Тропа" , game [ 14 ] , game [ 15 ]) ,
                ("Фортуна" , game [ 16 ] , game [ 17 ]) , ("Казино" , game [ 18 ] , game [ 19 ]) ,
                ("Лотерея" , game [ 20 ] , game [ 21 ]) , ("Шарик" , game [ 22 ] , game [ 23 ]) ,
                ("Камень-ножницы-бумага" , game [ 24 ] , game [ 25 ]) , ("Орёл или решка" , game [ 26 ] , game [ 27 ]) ,
                ("Дартс" , game [ 28 ] , game [ 29 ]) , ("Футбол" , game [ 30 ] , game [ 31 ]) ,
                ("Кости" , game [ 32 ] , game [ 33 ]) , ("Дуэль" , game [ 34 ] , game [ 35 ]) ,
                ("Бинго" , game [ 36 ] , game [ 37 ]),("Рулетка" , game [ 38 ] , game [ 39 ]),
                ("Орел или решка" , game [ 40 ] , game [ 41 ])]
            for g in game_info:
                if g [ 1 ] != 0:
                    win_amount_vin1 = "{:,.0f}".format(g [ 1 ]).replace("," , ".")
                    history_text += (f"🎮 Игра: {g [ 0 ]}\n"
                                     f"🍀 Выигрыш: {win_amount_vin1} кут\n"
                                     f"⌚️ Дата: {game [ 42 ]}\n"
                                     f"➖➖➖➖➖➖➖\n")
                if g [ 2 ] != 0:
                    win_amount_lose1 = "{:,.0f}".format(g [ 2 ]).replace("," , ".")
                    history_text += (f"🎮 Игра: {g [ 0 ]}\n"
                                     f"🚀 Проигрыш: {win_amount_lose1} кут\n"
                                     f"⌚️ Дата: {game [ 42 ]}\n"
                                     f"➖➖➖➖➖➖➖\n")

        buttons = await generate_buttons_moneyhistorygame(1 , num_pages)
        deletehistorygames = types.InlineKeyboardButton(text=" " , callback_data='deletehistorygameshistory', style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        # Создаём клавиатуру, добавляем кнопки в строки
        markup = InlineKeyboardMarkup(
            inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                [ deletehistorygames ]  # Кнопка для удаления истории в новой строке
            ])

        sent_message = await message.reply(
            history_text , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=markup)

        # Сохраняем ID сообщения и пользователя для дальнейшей проверки
        user_message_mapping [ user_id ] = sent_message.message_id
        print(user_message_mapping)



@dp.callback_query(lambda c: c.data.startswith('gameshistory'))
async def process_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagehelp1 = random.choice(randommessagehelp)

    print("qqqksfqklsfqqq1")

    # Проверка на уникальность сообщения
    if user_id not in user_message_history1 or user_message_history1[user_id] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer()


    # Получение истории игр
    games_history = await db.get_user_games_history(user_id, limit=7, offset=0)
    total_games = await db.get_user_games_count(user_id)
    num_pages = (total_games + 6) // 7  # Рассчитываем количество страниц

    # Если история пуста
    if not games_history:
        await callback_query.message.edit_text(
            '⚠️ Вы еще не играли в игры', parse_mode="HTML", disable_web_page_preview=True
        )
        return

    # Формирование текста истории
    history_text = "<b>📝 История ваших игр</b>\n\n"

    # Сопоставление информации о каждой игре
    for game in games_history:
        game_info = [
            ("Куб", game[0], game[1]), ("Боулинг", game[2], game[3]),
            ("Баскетбол", game[4], game[5]), ("Слоты", game[6], game[7]),
            ("Трейд", game[8], game[9]), ("Краш", game[10], game[11]),
            ("Мины", game[12], game[13]), ("Башня", game[14], game[15]),
            ("Рулетка", game[16], game[17]), ("Казино", game[18], game[19]),
            ("Лотерея", game[20], game[21]), ("Шарик", game[22], game[23]),
            ("Камень-ножницы-бумага", game[24], game[25]), ("Орёл или решка", game[26], game[27]),
            ("Дартс", game[28], game[29]), ("Футбол", game[30], game[31]),
            ("Кости", game[32], game[33]), ("Дуэль", game[34], game[35]),
            ("Бинго", game[36], game[37]), ("Рулетка", game[38], game[39]),
            ("Орел или решка", game[40], game[41]), ("Риск", game[42], game[43]),
            ("Плиты", game[44], game[45]), ("Бомбы", game[46], game[47])
        ]

        for g in game_info:
            if g[1] != 0:
                win_amount_vin1 = "{:,.0f}".format(g[1]).replace(",", ".")
                history_text += (f"🎮 Игра : {g[0]}\n"
                                 f"🍀 Выигрыш : {win_amount_vin1} кут\n"
                                 f"⌚️ Дата : {game[48]}\n"
                                 f"➖➖➖➖➖➖➖\n")
            if g[2] != 0:
                win_amount_lose1 = "{:,.0f}".format(g[2]).replace(",", ".")
                history_text += (f"🎮 Игра : {g[0]}\n"
                                 f"🚀 Проигрыш : {win_amount_lose1} кут\n"
                                 f"⌚️ Дата : {game[48]}\n"
                                 f"➖➖➖➖➖➖➖\n")

    # Создание кнопок навигации
    buttons = await generate_buttons_moneyhistorygame(1, num_pages)


    deletehistorygames = types.InlineKeyboardButton(text=" " , callback_data='deletehistorygameshistory1', style="default" ,
                icon_custom_emoji_id="5226660202035554522")
    # Создаём клавиатуру, добавляем кнопки в строки
    markup = InlineKeyboardMarkup(
        inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                          [ deletehistorygames ]  # Кнопка для удаления истории в новой строке
                          ])

    # Отправка обновленного сообщения
    sent_message = await callback_query.message.edit_text(
        history_text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
    )

    # Сохранение информации о сообщении для проверки
    user_message_mapping[user_id] = sent_message.message_id
    print(user_message_mapping)
@dp.callback_query(lambda c: c.data.startswith('translationsgames'))
async def process_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    print("qqqqqkoqsk1")
    if user_id not in user_message_history1 or user_message_history1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer()

    transactions = await db.get_transaction_history(user_id , limit=7 , offset=0)
    total_transactions = await db.get_transaction_count(user_id)
    num_pages = (total_transactions + 9) // 7  # Округляем вверх

    if not transactions:
        await callback_query.message.edit_text(
            '⚠️ На данный момент у вас нет транзакций' , parse_mode="HTML" ,
            disable_web_page_preview=True)
        return

    history_text = "<b>📝 История ваших транзакций</b>\n\n"

    for transaction in transactions:
        if transaction [ 0 ] == user_id:
            transaction_type = "🚀 Отправлено"
            transaction1 = '📍 Получатель'
            other_user_id = transaction [ 1 ]
        else:
            transaction_type = "✅ Получено"
            transaction1 = '🍀 Отправитель'
            other_user_id = transaction [ 0 ]

        other_user_info = await db.get_user_info_by_id(other_user_id)
        if other_user_info:
            other_user_link = f'<a href="tg://user?id={other_user_id}">{other_user_info [ "first_name" ]}</a>'
        else:
            other_user_link = str(other_user_id)

        history_text += (f"➖➖➖➖➖➖➖\n"
                         f"<b>{transaction_type} : {transaction [ 2 ]:,} кут</b>\n"
                         f"<b>{transaction1} : {other_user_link}</b>\n"
                         f"<b>⌚️ Дата : {transaction [ 3 ]}</b>\n\n")

    buttons = await generate_buttons_moneyhistory(1 , num_pages)


    deletehistorygames = types.InlineKeyboardButton(text=" " , callback_data='deletehistorygameshistory1', style="default" ,
                icon_custom_emoji_id="5226660202035554522")
    # Создаём клавиатуру, добавляем кнопки в строки
    markup = InlineKeyboardMarkup(
        inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                          [ deletehistorygames ]  # Кнопка для удаления истории в новой строке
                          ])

    sent_message = await callback_query.message.edit_text(
        history_text , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=markup)

    # Сохраняем ID сообщения и пользователя для дальнейшей проверки
    user_message_mapping [ user_id ] = sent_message.message_id
    print(user_message_mapping)












@dp.callback_query(lambda c: c.data.startswith('next_pagemoneyhistory_') or c.data.startswith('prev_pagemoneyhistory_'))
async def process_callback_button(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id


    messagesdanger1 = [ "Тебе не стоит этого делать" , "Неа, нельзя" , "Это не твоя кнопка" ,
                        "Сообщение вызвано другим пользователем" ]
    random_messagedanger = random.choice(randommessagehelp)
    print("qqqqsqkqq1")

    if user_id not in user_message_mapping or user_message_mapping [ user_id ] != message_id:
        await callback_query.answer(random_messagedanger)
        return
    await callback_query.answer()

    page_number = int(callback_query.data.split('_') [ -1 ])
    offset = (page_number - 1) * 7
    transactions = await db.get_transaction_history(user_id , limit=7 , offset=offset)
    total_transactions = await db.get_transaction_count(user_id)
    num_pages = (total_transactions + 9) // 7

    history_text = "<b>📝 История ваших транзакций</b>\n\n"

    for transaction in transactions:
        if transaction [ 0 ] == user_id:
            transaction_type = "🚀 Отправлено"
            transaction1 = '📍 Получатель'
            other_user_id = transaction [ 1 ]
        else:
            transaction_type = "✅ Получено"
            transaction1 = '🍀 Отправитель'
            other_user_id = transaction [ 0 ]

        other_user_info = await db.get_user_info_by_id(other_user_id)
        if other_user_info:
            other_user_link = f'<a href="tg://user?id={other_user_id}">{other_user_info [ "first_name" ]}</a>'
        else:
            other_user_link = str(other_user_id)

        history_text += (f"➖➖➖➖➖➖➖\n"
                        f"{transaction_type} : <b>{transaction [ 2 ]:,}</b> кут\n"
                        f"{transaction1} : {other_user_link}\n"
                        f"⌚️ Дата : {transaction [ 3 ]}\n\n")

    buttons = await generate_buttons_moneyhistory(page_number , num_pages)


    deletehistorymoney = types.InlineKeyboardButton(text=" " , callback_data='deletehistorymoneybuttons', style="default" ,
                icon_custom_emoji_id="5226660202035554522")
    # Создаём клавиатуру, добавляем кнопки в строки
    markup = InlineKeyboardMarkup(
        inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                          [ deletehistorymoney ]  # Кнопка для удаления истории в новой строке
                          ])

    await callback_query.message.edit_text(
        history_text , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=markup)



@dp.callback_query(
    lambda c: c.data.startswith('next_pagemoneyhistorygame_') or c.data.startswith('prev_pagemoneyhistorygame_'))
async def process_callback_button(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagehelp1 = random.choice(randommessagehelp)

    # Проверка на уникальность сообщения
    if user_id not in user_message_mapping or user_message_mapping [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer()

    # Извлечение номера страницы из данных callback
    page_number = int(callback_query.data.split('_') [ -1 ])
    offset = (page_number - 1) * 7  # Расчет смещения для пагинации

    # Получение истории игр пользователя
    games_history = await db.get_user_games_history(user_id , limit=7 , offset=offset)
    total_games = await db.get_user_games_count(user_id)
    num_pages = (total_games + 6) // 7  # Рассчитываем количество страниц

    # Если истории игр нет
    if not games_history:
        await callback_query.message.edit_text(
            '⚠️ У вас еще нет истории игр' , parse_mode="HTML" , disable_web_page_preview=True)
        return

    # Формирование текста с историей игр
    history_text = "<b>📝 История ваших игр</b>\n\n"

    for game in games_history:
        game_info = [ ("Куб" , game [ 0 ] , game [ 1 ]) , ("Боулинг" , game [ 2 ] , game [ 3 ]) ,
            ("Баскетбол" , game [ 4 ] , game [ 5 ]) , ("Слоты" , game [ 6 ] , game [ 7 ]) ,
            ("Трейд" , game [ 8 ] , game [ 9 ]) , ("Краш" , game [ 10 ] , game [ 11 ]) ,
            ("Мины" , game [ 12 ] , game [ 13 ]) , ("Башня" , game [ 14 ] , game [ 15 ]) ,
            ("Рулетка" , game [ 16 ] , game [ 17 ]) , ("Казино" , game [ 18 ] , game [ 19 ]) ,
            ("Лотерея" , game [ 20 ] , game [ 21 ]) , ("Шарик" , game [ 22 ] , game [ 23 ]) ,
            ("Камень-ножницы-бумага" , game [ 24 ] , game [ 25 ]) , ("Орёл или решка" , game [ 26 ] , game [ 27 ]) ,
            ("Дартс" , game [ 28 ] , game [ 29 ]) , ("Футбол" , game [ 30 ] , game [ 31 ]) ,
            ("Кости" , game [ 32 ] , game [ 33 ]) , ("Дуэль" , game [ 34 ] , game [ 35 ]) ,
            ("Бинго" , game [ 36 ] , game [ 37 ]) , ("Рулетка" , game [ 38 ] , game [ 39 ]) ,
            ("Орел или решка" , game [ 40 ] , game [ 41 ]) , ("Риск" , game [ 42 ] , game [ 43 ]) ,
            ("Плиты" , game [ 44 ] , game [ 45 ]) , ("Бомбы" , game [ 46 ] , game [ 47 ]) ]

        for g in game_info:
            if g [ 1 ] != 0:
                win_amount_vin1 = "{:,.0f}".format(g [ 1 ]).replace("," , ".")
                history_text += (f"🎮 Игра : {g [ 0 ]}\n"
                                 f"🍀 Выигрыш : {win_amount_vin1} кут\n"
                                 f"⌚️ Дата : {game [ 48 ]}\n"
                                 f"➖➖➖➖➖➖➖\n")
            if g [ 2 ] != 0:
                win_amount_lose1 = "{:,.0f}".format(g [ 2 ]).replace("," , ".")
                history_text += (f"🎮 Игра : {g [ 0 ]}\n"
                                 f"🚀 Проигрыш : {win_amount_lose1} кут\n"
                                 f"⌚️ Дата : {game [ 48 ]}\n"
                                 f"➖➖➖➖➖➖➖\n")

    # Генерация кнопок для навигации по истории
    buttons = await generate_buttons_moneyhistorygame(page_number , num_pages)


    deletehistorygames = types.InlineKeyboardButton(text=" " , callback_data='deletehistorygameshistory', style="default" ,
                icon_custom_emoji_id="5226660202035554522")
    # Создаём клавиатуру, добавляем кнопки в строки
    markup = InlineKeyboardMarkup(
        inline_keyboard=[ buttons ,  # Все кнопки из списка в первой строке
                          [ deletehistorygames ]  # Кнопка для удаления истории в новой строке
                          ])

    # Отправка обновленного текста с историей игр
    sent_message = await callback_query.message.edit_text(
        history_text , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=markup)

    # Сохранение ID сообщения для проверки в дальнейшем


random_messagedanger = random.choice(randommessagehelp)
print("qqsoqlqsqqq1")


@dp.callback_query(lambda c: c.data == 'deletehistorygameshistory1')
async def process_buy_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    print("qqpqlpqsqqq1")
    if user_id not in user_message_history1 or user_message_history1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return


    await callback_query.answer('сообщение с историей игр удалено')
    await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == 'deletehistorymoneybuttons1')
async def process_buy_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_message_history1 or user_message_history1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return


    await callback_query.answer('сообщение с историей переводов удалено')
    await callback_query.message.delete()


@dp.callback_query(lambda c: c.data == 'deletehistorygameshistory')
async def process_buy_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    random_messagedanger = random.choice(randommessagehelp)

    if user_id not in user_message_mapping or user_message_mapping [ user_id ] != message_id:
        await callback_query.answer(random_messagedanger)
        return


    await callback_query.answer('сообщение с историей игр удалено')
    await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == 'deletehistorymoneybuttons')
async def process_buy_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    random_messagedanger = random.choice(randommessagehelp)

    if user_id not in user_message_mapping or user_message_mapping [ user_id ] != message_id:
        await callback_query.answer(random_messagedanger)
        return


    await callback_query.answer('сообщение с историей переводов удалено')
    await callback_query.message.delete()