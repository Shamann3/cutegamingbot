from main import *
from bot.games.group_only import reject_if_private_game




@dp.message()
async def word(message: Message):
    group_id = message.chat.id
    creator_id = message.from_user.id
    text_parts = message.text.split(" ")

    #print(f"[DEBUG] Получено сообщение от пользователя: {message.from_user.first_name} ({creator_id}) в группе: {group_id}")
    #print(f"[DEBUG] Текст сообщения: {message.text}")


    # Если сообщение начинается с "слово", это попытка создать новую игру
    if len(text_parts) >= 2 and text_parts[0].lower() in ['слово34123412','слова34123412']:
        if await reject_if_private_game(message):
            return

        # Проверяем, что на 1 индексе есть хотя бы одно слово или ставка
        if len(text_parts) < 3 and text_parts[1].isdigit():
            await message.reply("🛠 После указания ставки нужно написать слово для отгадывания.")
            #print(f"[DEBUG] Ставка указана, но нет слова для отгадывания. Сообщение отправлено пользователю. 🛠")
            return

        # Если на 1 индексе ставка
        if text_parts[1].isdigit():
            bet = int(text_parts[1])
            word_to_guess = text_parts[2].lower()  # Слово на 2 индексе
            hint = " ".join(text_parts[3:]) if len(text_parts) > 3 else None
            #print(f"[DEBUG] Игра с установленной ставкой: {bet} 💰. Слово для отгадывания: {word_to_guess} 🔤. Подсказка: {hint}")
        else:
            # Если на 1 индексе слово
            word_to_guess = text_parts[1].lower()  # Слово на 1 индексе
            bet = 0  # Ставки нет
            hint = " ".join(text_parts[2:]) if len(text_parts) > 2 else None
            #print(f"[DEBUG] Игра без ставки. Слово для отгадывания: {word_to_guess} 🔤. Подсказка: {hint}")

        # Добавляем информацию об игре в словарь
        wordgames[group_id] = {'creator_id': creator_id, 'word_to_guess': word_to_guess, 'hint': hint, 'bet': bet, 'message_id': message.message_id}
        #print(f"[DEBUG] Игра успешно добавлена в словарь: {wordgames[group_id]} 🗃️")

        # Удаляем сообщение создателя игры с загадкой
        await bot1.delete_message(chat_id=group_id, message_id=message.message_id)
        #print(f"[DEBUG] Сообщение с загадкой от пользователя {message.from_user.first_name} удалено. 🗑️")

        # Отправляем информацию о начале игры
        cancel_button = InlineKeyboardButton(
            text="Отменить игру" , callback_data="wordcancel_game")

        # Создание клавиатуры с одной кнопкой
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ cancel_button ] ]  # Оборачиваем кнопку в список, чтобы передать её в inline_keyboard
        )
        creator_name = await db.get_firstname_by_user_id(creator_id)

        # Формирование строки со ставкой, если ставка больше 0
        win_amount_formatted = "{:,.0f}".format(bet).replace(",", ".")
        bet_line = f"\n💰 <b>{win_amount_formatted}</b> кут " if bet > 0 else ""
        hint_line = f'\n\n🧠 <b>Подсказка :</b> \n🌸 {hint}' if hint else ''

        # Итоговое сообщение
        response = f"⭐️ <b>Игра в слова началась!</b> ⭐️\n💫 <b><a href='tg://user?id={creator_id}'>{creator_name}</a></b>"
        response += f"{bet_line}" if bet_line else ""
        response += f"{hint_line}" if hint_line else ""

        # Отправка сообщения
        sent_message = await message.answer(response, reply_markup=keyboard, parse_mode="HTML")
        user_word[creator_id] = sent_message.message_id
        #print("[DEBUG] Сообщение о начале игры отправлено в чат. 📣")

    # Проверяем, есть ли активная игра в чате
    elif group_id in wordgames:
        #print("[DEBUG] Найдена активная игра в группе. 🎮")
        game = wordgames[group_id]
        user_id = message.from_user.id

        # Если игрок не является создателем игры
        if user_id != game [ 'creator_id' ]:
            user_guess = message.text.strip().lower()

            #print(f"[DEBUG] Попытка угадать слово от {message.from_user.first_name}: {user_guess} 🤔")

            # Удаляем нежелательные символы в конце, такие как '?'
            user_guess = user_guess.rstrip('?')

            # Проверяем, если слово угадано
            if user_guess == game [ 'word_to_guess' ].lower():
                # Логика для обработки правильного ответа
                #print(f"[DEBUG] {message.from_user.first_name} угадал слово! 🎉")


                # Игра окончена, сообщаем победителю
                from main import check_bet_and_set_item
                await check_bet_and_set_item(user_id , game [ 'bet' ])
                await message.reply(f"🏆 <b>Поздравляю, вы угадали правильное слово!</b>", parse_mode="HTML")

                # Изменяем сообщение о начале игры
                win_amount_formatted = "{:,.0f}".format(game [ 'bet' ]).replace("," , ".")
                win_name = await db.get_firstname_by_user_id(user_id)

                # Формируем сообщение о завершении игры
                end_response = f"⭐️ <b>Игра в слова закончена!</b> ⭐️\n🏆 <b>Победитель : <a href='tg://user?id={user_id}'>{win_name}</a></b>"

                # Добавляем строку с выигрышем только если сумма выигрыша больше 0
                if game [ 'bet' ] > 0:
                    end_response += f"\n💰 <b>Выигрыш {win_amount_formatted} кут</b>"

                await bot1.edit_message_text(end_response, chat_id=group_id, message_id=user_word[game['creator_id']], parse_mode="HTML")

                # Если есть ставка, раздаем приз
                if game['bet'] > 0:
                    winner_id = user_id
                    loser_id = game['creator_id']
                    winner_balance = await db.get_user_balance(winner_id)  # Получаем текущий баланс победителя
                    loser_balance = await db.get_user_balance(loser_id)  # Получаем текущий баланс проигравшего

                    new_winner_balance = winner_balance + game['bet']
                    new_loser_balance = loser_balance - game['bet']

                    await db.update_user_balance(winner_id, new_winner_balance)  # Обновляем баланс победителя
                    await db.update_user_wins(winner_id , 1, bot1, ref_coin)
                    await db.update_user_winamount(winner_id , game['bet'])#
                    await db.update_game_last_activity(winner_id)
                    await db.update_user_balance(loser_id, new_loser_balance)  # Обновляем баланс проигравшего
                    await db.cutehistory_plus(
                        winner_id , game['bet'] , "слова")
                    await db.cutehistory_minus(
                        loser_id , game [ 'bet' ] , "слова")

                    randommessagebonus1 = random.choice(["Супер","Отлично"])
                    await message.reply(f"💰 <b>{randommessagebonus1}! Вы получили {win_amount_formatted} кут</b> ", parse_mode="HTML")
                    #print(f"[DEBUG] Пользователь {message.from_user.first_name} выиграл {game['bet']} монет.")

                # Удаляем завершённую игру из словаря
                del wordgames[group_id]
                #print("[DEBUG] Игра завершена и удалена из словаря. ✅")
            #else:
                #print(f"[DEBUG] Попытка угадать слово не удалась. Пользователь {message.from_user.first_name} не угадал. ❌")
        #else:
            #print(f"[DEBUG] Попытка создателя игры ({message.from_user.first_name}) угадать слово. Игнорируем. 💤")

    #else:
        #print("[DEBUG] Активной игры в группе не найдено. ❌")


@dp.callback_query(lambda c: c.data == "wordcancel_game")
async def cancel_game(callback_query: types.CallbackQuery):
    group_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_word or user_word [ user_id ] != message_id:
        await callback_query.answer('🔒 Только создатель игры может её отменить.', show_alert=True)
        return

    # Удаляем игру из словаря, если она существует
    if group_id in wordgames:
        del wordgames[group_id]  # Удаляем игру
        await callback_query.message.edit_text("✅ <b>Игра в слова была отменена.</b>",parse_mode="HTML")
        print("[DEBUG] Игра отменена пользователем.")
    else:
        await callback_query.answer("❌ Нет активной игры для отмены.", show_alert=True)