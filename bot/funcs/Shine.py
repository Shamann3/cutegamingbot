from main import *


user_shine_requests = {}



timeshine = 18000



@dp.message()
async def Shine(message: Message):
    if message.text.lower() in [ "шайн34123412" ]:
        allowed_users = [ 6801702632 , 6488580935 ]
        user_id = message.from_user.id

        if not await check_user_name_for_bot(user_id, message.from_user.first_name, message.from_user.last_name):
            await message.reply(
                "<b>🟡 Чтобы получить косметический предмет из шайна, в нике должно бытьупоминание бота. Например 'Cute' или '@CutegGamingBot'</b>" ,
                parse_mode="HTML", disable_web_page_preview=True)
            return

        current_time = time.time()  # Получаем время в формате Unix-время (float)


        last_open_time , data_open = await db.get_historygames_times(user_id)

        print(f"Время последнего открытия бонуса: {last_open_time}, Время окончания бонуса: {data_open}")

        # Проверяем, есть ли данные о бонусах для пользователя
        if last_open_time is None or data_open is None:
            # Если данных нет, сообщаем, что для получения бонуса нужно выиграть в игре
            print(f"Пользователь {user_id} не найден в таблице historygames.")
            await message.answer(
                "<b>⚠️ Чтобы открыть шайн, нужно победить в любой игре против других игроков\n<blockquote><code>хелп игры</code></blockquote></b>" ,
                parse_mode="HTML")
            return
        # Проверяем время последнего запроса
        try:
            last_open_time , data_open = await db.get_shine_times(user_id)

            if last_open_time and data_open:
                if isinstance(last_open_time , str):
                    last_open_time = datetime.strptime(last_open_time , "%Y-%m-%d %H:%M:%S")
                if isinstance(data_open , str):
                    data_open = datetime.strptime(data_open , "%Y-%m-%d %H:%M:%S")

                if current_time < data_open.timestamp():  # Конвертируем в timestamp
                    wait_time = int((data_open.timestamp() - current_time))  # Время ожидания в секундах

                    # Формируем сообщение о времени ожидания
                    hours , remainder = divmod(wait_time , 3600)
                    minutes , seconds = divmod(remainder , 60)

                    if hours > 0:
                        time_message = f"<i>{hours}</i> часов, <i>{minutes}</i> минут"
                    elif minutes > 0:
                        time_message = f"<i>{minutes}</i> минут и <i>{seconds}</i> секунд"
                    else:
                        time_message = f"<i>{seconds}</i> секунд"

                    await message.reply(
                        f"⌚️ <b>Подождите {time_message}.</b>" , parse_mode="HTML")
                    return

        except Exception as e:
            await message.reply(f"Ошибка: {str(e)}")
            return

        # Генерация кнопок бонуса
        keyboard = InlineKeyboardMarkup(row_width=5)
        textfraza = [ "Нажми и получи блеск!" , "Твое украшение ждет!" , "Добавь яркости – жми!" ,
                      "Каждый клик - драгоценность!" , "Жми и получи сияние!" , "Лови шанс на украшение!" ,
                      "Укрась день - нажми!" , "Блеск в одном клике!" , "Твоя драгоценность рядом!" ,
                      "Драгоценность ждет тебя!" , "Жми и сияй!" , "Укрась себя нажатием!" , "Нажми - получи блеск!" ,
                      "Твоя награда в одном клике!" , "Подарок в каждом клике!" ]

        try:
            shine_items = await db.get_items_with_shine_value(1)
            emojis = [ item [ 1 ] for item in shine_items ]
            random.shuffle(emojis)
            randomemoji = random.choice(emojis)
            randomtextfraza = random.choice(textfraza)

            num_buttons = random.randint(5 , 13)
            selected_emojis = emojis [ :num_buttons ]
            buttons = [ InlineKeyboardButton(emoji , callback_data="shineshine") for emoji in selected_emojis ]
            keyboard.add(*buttons)

            close_button = InlineKeyboardButton(" " , callback_data="close_shine", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
            keyboard.add(close_button)

            send_message_shine = await message.reply(
                f"🦋 <b><i>{randomtextfraza}</i></b>" , parse_mode="HTML" , reply_markup=keyboard)

            # Сохраняем ID сообщения для отслеживания
            message_id = send_message_shine.message_id
            user_shine_requests.setdefault(user_id , [ ]).append(message_id)

        except Exception as e:
            await message.reply(f"Ошибка при генерации кнопок: {str(e)}")

    @dp.callback_query(lambda c: c.data == "shineshine")
    async def process_callback(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id
        chat_id = callback_query.message.chat.id
        chat_name = callback_query.message.chat.full_name

        # Получаем текущее время в формате строки "YYYY-MM-DD HH:MM:SS"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if user_id not in user_shine_requests or message_id not in user_shine_requests [ user_id ]:
            randommessagebonus1 = random.choice(randommessagehelp)
            print("qqqqq19")
            await callback_query.answer(randommessagebonus1)
            return

        # Получаем время последнего открытия и следующее открытие из базы
        last_open_time , data_open = await db.get_shine_times(user_id)

        # Если времени последнего открытия нет, устанавливаем новое
        if last_open_time is None or data_open is None:
            last_open_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем в строку
            # Следующее открытие - это текущее время + время бонуса
            next_open_time = datetime.now() + timedelta(seconds=timeshine)  # Следующее время как объект datetime
            data_open = next_open_time.strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем в строку

            user_name = await db.get_firstname_by_user_id(user_id)

            # Проверка имени пользователя на упоминание бота
            if not await check_user_name_for_bot(user_id, message.from_user.first_name, message.from_user.last_name):
                await callback_query.message.edit_text(
                    "🟡 <b>Ник должен содержать упоминание бота. Обновите и попробуйте снова.</b>" ,
                    parse_mode="HTML")
                return

            # Добавление записи в базу данных с текущим и следующими временными метками
            await db.add_shine(
                chat_id , chat_name , user_id , user_name , last_open_time , data_open)
        else:
            try:
                # Проверка на таймер
                if datetime.now().strftime('%Y-%m-%d %H:%M:%S') < data_open:
                    await callback_query.answer("🟡 Вы уже получили свой шайн!")
                    return
            except TypeError:
                return

        # Получаем предметы с shine = 1 из базы данных
        shine_items = await db.get_items_with_shine_value(1)

        if not shine_items:
            await callback_query.answer("🟡 Нет предметов для выдачи в системе")
            return

        # Получаем имя пользователя
        user_name = await db.get_firstname_by_user_id(user_id)

        # Проверка имени на упоминание бота
        if await check_user_name_for_bot(user_id , first_name=callback_query.from_user.first_name , last_name=callback_query.from_user.last_name ):
            # Случайно выбираем предмет из доступных
            selected_item = random.choice(shine_items)

            # Эмодзи и название предмета
            emojiitem = selected_item [ 1 ]  # Эмодзи предмета
            item_name = selected_item [ 2 ]  # Название предмета

            # Добавляем предмет пользователю
            await db.set_items(user_id , item_name , 1)

            # Формируем сообщение о бонусе
            aasjidajsdka = random.choice(
                [ "Повезло!" , "Приз твой!" , "Удача!" , "Поздравляю!" , "Шайн кормит!" , "Ты везунчик!" ])
            double_name = f"🦋 <b>{aasjidajsdka}</b>\n<code>{emojiitem}</code> <b>{item_name}</b>"

            # Обновляем сообщение с бонусом
            await callback_query.message.edit_text(
                f"{double_name}" , parse_mode="HTML")

            # Обновляем время для следующего открытия
            last_open_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            next_open_time = datetime.now() + timedelta(seconds=timeshine)
            data_open = next_open_time.strftime('%Y-%m-%d %H:%M:%S')

            # Сохраняем в базу данных
            await db.add_shinebet(
                user_id , user_name , 0 ,  # Количество или значение бонуса
                chat_id , chat_name , data_open  # Передаем время как строку в нужном формате
            )

            # Удаляем ID сообщения из активных запросов
            user_shine_requests [ user_id ].remove(message_id)
            if not user_shine_requests [ user_id ]:
                del user_shine_requests [ user_id ]
        else:
            # Если в имени пользователя нет упоминания бота
            await callback_query.message.edit_text(
                "🟡 <b>Ник должен содержать упоминание бота. Обновите и попробуйте снова.</b>" ,
                parse_mode="HTML")

    @dp.callback_query(lambda c: c.data == 'close_shine')
    async def close_bonus_callback(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id
        if user_id not in user_shine_requests or message_id not in user_shine_requests [ user_id ]:
            randommessagebonus1 = random.choice(randommessagehelp)
            print("qqqqq20")
            await callback_query.answer(randommessagebonus1)
            return
        try:
            # Удаляем текущее сообщение
            await callback_query.answer("❕ Сообщение с бонусом удалено.")
            await callback_query.message.delete()
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            await callback_query.answer(
                "🛠 Не удалось удалить сообщение, возможно, оно уже было удалено." , show_alert=True)
        except Exception as e:
            print(f"Произошла ошибка: {str(e)}")
            await callback_query.answer("🛠 Произошла ошибка при удалении сообщения." , show_alert=True)