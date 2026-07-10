from main import *

TARGET_USER_ID = 6801702632
file = 'bunker'
MESSAGES = {
    "welcome": {
        "text": "🥂",
        "keyboard": InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💫 1 реф = 1 кут", callback_data="123refprofile1")
            ]
        ])
    },
    "promo": {
        "text": "<b>🧨 Вас заблокировали. По причине : 'Хорошее настроение'\n\nЭто шутка), Вы уже выводили куты в звезды?</b>",
        "keyboard": None},
    "custom": {
        "text": """🍹
        """,
        "keyboard": InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="ЗАБРАТЬ КУТ", callback_data='bonusstartbonus')
            ]
        ])
    },
    "custom1123": {
        "text": """🕊
        """,
        "keyboard": InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Играть", switch_inline_query="")],
                [InlineKeyboardButton(text="Добавить в чат", url="https://t.me/CuteGamingBot?startgroup=true")
            ]
        ])
    }
}
sending_active = False
sending_task = None
@dp.message()
async def reklama(message: Message):
    if message.text.lower() == "старт реклама":
        if message.from_user.id == 6801702632:
            global sending_task

            if sending_task:
                sending_task.cancel()
                try:
                    await sending_task
                except asyncio.CancelledError:
                    pass
                sending_task = None
                await message.answer("Рассылка остановлена.")
            else:
                async def send_messages_loop():
                    successful_count = 0
                    failed_count = 0
                    error_reasons = {}
                    successful_users = [ ]
                    failed_users = [ ]

                    start_time = time.time()

                    try:
                        user_ids = await db.get_active_users_last_10_days()  # Получаем только активных
                        total_users = len(user_ids)

                        for current_index , user_id in enumerate(user_ids):
                            try:
                                message_key = random.choice(list(MESSAGES.keys()))
                                if message_key not in MESSAGES:
                                    raise ValueError(f"Ключ сообщения '{message_key}' отсутствует в словаре")

                                custom_message = MESSAGES [ message_key ] [ "text" ]
                                inline_keyboard = MESSAGES [ message_key ].get("keyboard")
                                random_effect_id = random.choice(
                                    [ "5104841245755180586" , "5107584321108051014" , "5159385139981059251" ,
                                        "5046509860389126442" ])

                                kwargs = {"chat_id": user_id , "text": custom_message ,
                                    "message_effect_id": random_effect_id , "parse_mode": "HTML" ,
                                    "disable_web_page_preview": True}
                                if inline_keyboard:
                                    kwargs [ "reply_markup" ] = inline_keyboard

                                await bot1.send_message(**kwargs)

                                successful_count += 1
                                successful_users.append(user_id)

                            except (TelegramForbiddenError , TelegramBadRequest) as e:
                                reason = str(e)
                                print(f"Telegram-ошибка у пользователя {user_id}: {reason}")
                                failed_count += 1
                                failed_users.append((user_id , reason))
                                error_reasons [ reason ] = error_reasons.get(reason , 0) + 1

                            except Exception as e:
                                reason = str(e)
                                print(f"Другая ошибка у пользователя {user_id}: {reason}")
                                failed_count += 1
                                failed_users.append((user_id , reason))
                                error_reasons [ reason ] = error_reasons.get(reason , 0) + 1

                            await asyncio.sleep(0.50)  # Антифлуд

                    except asyncio.CancelledError:
                        print("Рассылка была остановлена.")
                        return

                    except Exception as e:
                        await message.answer("Произошла ошибка при рассылке.")
                        print(f"🔥 Ошибка при рассылке: {e}")

                    end_time = time.time()
                    total_time = end_time - start_time

                    print(
                        f"\n✅ Рассылка завершена.\n"
                        f"✅ Успешно: {successful_count}\n"
                        f"❌ Ошибок: {failed_count}\n"
                        f"🕒 Время выполнения: {total_time:.2f} сек\n")
                    await message.reply(
                        f"\n✅ Рассылка завершена.\n"
                        f"✅ Успешно: {successful_count}\n"
                        f"❌ Ошибок: {failed_count}\n"
                        f"🕒 Время выполнения: {total_time:.2f} сек\n")

                    if failed_count > 0:
                        print("❗ Отчёт об ошибках:")
                        for user_id , reason in failed_users:
                            print(f"Пользователь {user_id} - ошибка: {reason}")

                sending_task = asyncio.create_task(send_messages_loop())
                await message.answer("Рассылка на один круг запущена.")

#    if message.text.lower() == "старт реклама":
#        if message.from_user.id == 6801702632:
#            global sending_active , sending_task
#
#            if sending_active:
#                # Остановить рассылку
#                sending_active = False
#                if sending_task:
#                    sending_task.cancel()
#                    try:
#                        await sending_task
#                    except asyncio.CancelledError:
#                        pass
#                    sending_task = None
#                await message.answer("Зацикленность остановлена.")
#            else:
#                # Запустить рассылку
#                sending_active = True
#
#                async def send_messages_loop():
#                    successful_count = 0
#                    failed_count = 0
#                    error_reasons = {}
#                    successful_users = [ ]
#                    failed_users = [ ]
#
#                    start_time = time.time()

#                    try:
#                        user_ids = await db.get_active_users_last_10_days()  # Важное изменение!
#                        total_users = len(user_ids)
#                        current_index = 0
#
#                        while sending_active:
#                            if current_index >= total_users:
#                                current_index = 0  # Новый круг - можно, например, сменить сообщение или что-то ещё
#
#                            user_id = user_ids [ current_index ]
#                            current_index += 1
#
#                            try:
#                                message_key = random.choice(list(MESSAGES.keys()))
#                                if message_key not in MESSAGES:
#                                    raise ValueError(f"Ключ сообщения '{message_key}' отсутствует в словаре")
#
#                                custom_message = MESSAGES [ message_key ] [ "text" ]
#                                inline_keyboard = MESSAGES [ message_key ].get("keyboard")
#                                random_effect_id = random.choice(
#                                    [ "5104841245755180586" , "5107584321108051014" , "5159385139981059251" ,
#                                      "5046509860389126442" ])
#
#                                kwargs = {"chat_id": user_id , "text": custom_message ,
#                                    "message_effect_id": random_effect_id , "parse_mode": "HTML" ,
#                                    "disable_web_page_preview": True , }
#                                if inline_keyboard:
#                                    kwargs [ "reply_markup" ] = inline_keyboard
#
#                                await bot1.send_message(**kwargs)
#
#                                successful_count += 1
#                                successful_users.append(user_id)
#
#                            except (TelegramForbiddenError , TelegramBadRequest) as e:
#                                reason = str(e)
#                                print(f"Telegram-ошибка у пользователя {user_id}: {reason}")
#                                failed_count += 1
#                                failed_users.append((user_id , reason))
#                                error_reasons [ reason ] = error_reasons.get(reason , 0) + 1
#
#                            except Exception as e:
#                                reason = str(e)
#                                print(f"Другая ошибка у пользователя {user_id}: {reason}")
#                                failed_count += 1
 #                               failed_users.append((user_id , reason))
#                                error_reasons [ reason ] = error_reasons.get(reason , 0) + 1
#
    #                        await asyncio.sleep(1)  # Антифлуд
#
    #                except asyncio.CancelledError:
    #                    print("Рассылка была остановлена.")
    #                    return
#
    #                except Exception as e:
    #                    await message.answer("Произошла ошибка при рассылке.")
    #                    print(f"🔥 Ошибка при рассылке: {e}")
#
    #                end_time = time.time()
    #                total_time = end_time - start_time
#
    #                print(
    #                    f"\n✅ Рассылка завершена.\n"
    #                    f"✅ Успешно: {successful_count}\n"
    #                    f"❌ Ошибок: {failed_count}\n"
    #                    f"🕒 Время выполнения: {total_time:.2f} сек\n")
#
    #                if failed_count > 0:
    #                    print("❗ Отчёт об ошибках:")
    #                    for user_id , reason in failed_users:
    #                        print(f"Пользователь {user_id} - ошибка: {reason}")
    #            sending_task = asyncio.create_task(send_messages_loop())
    #            await message.answer("Зацикленность запущена.")


@dp.callback_query(lambda c: c.data.startswith('123refprofile1'))
async def process_callback_kb1btn1(call: types.CallbackQuery):

    link = await get_start_link(call.from_user.id)

    user_id = call.from_user.id
    print(user_id)
    button_id = call.data
    print(button_id)
    creator_id = button_creators.get(f"{button_id}{user_id}")
    print(creator_id)




    message_id = call.message.message_id




    randommessageprofile1 = random.choice(randommessagehelp)


    await call.answer()
    button = InlineKeyboardButton(text="Назад" , callback_data="back_to_menu1")

    # Создаем клавиатуру с указанным параметром inline_keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ button ] ])  # Важно: inline_keyboard должен быть списком списков

    await bot1.edit_message_text(
        message_id=call.message.message_id , chat_id=call.message.chat.id , text=f'''
<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка :</b> 

<code>{link}</code>

<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>1 друг = 1 кут </b>

<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>+ 25% с каждой покупки, которую совершит ваш реферал в магазине!</b>

<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>+ Каждый приглашённый - рост вашей реферальной статистики!</b>
'''  ,
        parse_mode="HTML")