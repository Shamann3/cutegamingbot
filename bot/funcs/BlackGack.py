from main import *
gamesblack = []






async def delete_message_after_delay(chat_id, message_id, delay, user_id):
    await asyncio.sleep(delay)
    await bot1.delete_message(chat_id=chat_id, message_id=message_id)
    if user_id in gamesblack:
        del gamesblack[user_id]

@dp.message()
async def black(message: Message):
    user_id = message.from_user.id

    if 'рулетка' in message.text.lower().split()[0] and len(message.text.split()) > 1:
        if privates:

            return
        if user_id in gamesblack:
            await message.reply("⚠️ Вы уже участвуете в игре.")
            return

        bet = message.text.split()[1]

        if bet is not None and bet.isdigit():
            bet = int(bet)
            balance = await db.get_user_balance(user_id)

            if bet > balance:
                from bot.funcs.help import callbaYTRWEQck_main
                button = InlineKeyboardButton(text=f"Как заработать кут?" , callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result , float) and result.is_integer() else str(result)
                bet_amount_win_formated = "{:,.0f}".format(bet).replace("," , ".")
                bot_username = await get_bot_username_by_token(TOKEN)
                user_id = message.from_user.id
                pending_context [ user_id ] = {"stars_amount": bet_amount_str , "sent": False}
                button1 = InlineKeyboardButton(
                    text=f"💫 Купить {bet_amount_win_formated} кут 💰" , url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button1 ] , [ button ] ])

                await message.reply(
                    "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>" , reply_markup=keyboard , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                await asyncio.sleep(timeoutdonate)

                if user_id in pending_context and not pending_context [ user_id ] [ "sent" ]:
                    stars_amount = pending_context [ user_id ] [ "stars_amount" ]
                    invoice_message = await send_invoice_to_user(message , stars_amount)

                    # сохраним id сообщения
                    pending_context [ user_id ] [ "manual_message_id" ] = invoice_message.message_id
                return

            random_number = random.randint(0, 18)
            user_data = {'user_id': user_id , 'bet': bet , 'random_number': random_number}
            gamesblack.append(user_data)
            print(gamesblack)

            roulette_keyboard = InlineKeyboardMarkup(row_width=6)

            numbers = [
                [3, 6, 9, 12, 15, 18],
                [2, 5, 8, 11, 14, 17],
                [1, 4, 7, 10, 13, 16]
            ]

            red_numbers = {1, 3, 5, 9, 7, 11, 15, 13, 17}

            for row in numbers:
                row_buttons = []
                for num in row:
                    color = '🔴' if num in red_numbers else '⚫️'
                    text = f"{num} {color}"
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"number_{num}"))
                roulette_keyboard.row(*row_buttons)

            new_buttons_row1 = [
                InlineKeyboardButton(text="1-ая треть", callback_data="1st6"),
                InlineKeyboardButton(text="2-ая треть", callback_data="2nd6"),
                InlineKeyboardButton(text="3-ья треть", callback_data="3rd6")
            ]
            new_buttons_row2 = [
                InlineKeyboardButton(text="1to9", callback_data="1to9"),
                InlineKeyboardButton(text="Четное", callback_data="EVEN"),
                InlineKeyboardButton(text="🔴", callback_data="red"),
                InlineKeyboardButton(text="⚫️", callback_data="black"),
                InlineKeyboardButton(text="Нечет", callback_data="ODD"),
                InlineKeyboardButton(text="9to18", callback_data="9to18")
            ]

            roulette_keyboard.row(*new_buttons_row1)
            roulette_keyboard.row(*new_buttons_row2)

            sent_message = await message.reply(f"🎩 Выберите число или комбинацию", reply_markup=roulette_keyboard)
            asyncio.create_task(delete_message_after_delay(sent_message.chat.id, sent_message.message_id, 100, user_id))
        else:
            await message.reply("⚠️ Неверный формат ставки")


async def check_result(user_id, user_choice, callback_query):
    game = next((game for game in gamesblack if game['user_id'] == user_id), None)

    if not game:
        await callback_query.answer("Это не ваша игра")
        return

    # Проверка на соответствие идентификатора пользователя
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша игра")
        return

    # Проверка на соответствие идентификатора пользователя из списка gamesblack
    if game['user_id'] != user_id:
        await callback_query.answer("Ошибка: идентификатор пользователя не совпадает с текущей игрой")
        return

    random_number = game['random_number']
    bet = game['bet']
    balance = await db.get_user_balance(user_id)

    result_message = f"🪄 Выпало число <b>{random_number}</b>"
    red_numbers = {1, 3, 5, 9, 7, 11, 15, 13, 17}

    if random_number % 2 == 0:
        number_type = "Четное"
    else:
        number_type = "Нечетное"

    color_emoji = '🔴' if random_number in red_numbers else '⚫️'

    result_message += f" [{number_type} {color_emoji}]"
    result_message += f'\n✨ Позиция {user_choice}\n'

    win = False
    multiplier = 1

    if user_choice == str(random_number):
        win = True
        multiplier = 18
    elif user_choice == '1st6' and 1 <= random_number <= 6:
        win = True
        multiplier = 2.5
    elif user_choice == '2nd6' and 7 <= random_number <= 12:
        win = True
        multiplier = 2.5
    elif user_choice == '3rd6' and 13 <= random_number <= 18:
        win = True
        multiplier = 2.5
    elif user_choice == '1to9' and 1 <= random_number <= 9:
        win = True
        multiplier = 1.7
    elif user_choice == 'EVEN' and random_number % 2 == 0:
        win = True
        multiplier = 1.7
    elif user_choice == 'red' and random_number in red_numbers:
        win = True
        multiplier = 1.7
    elif user_choice == 'black' and random_number not in red_numbers:
        win = True
        multiplier = 1.7
    elif user_choice == 'ODD' and random_number % 2 == 1:
        win = True
        multiplier = 1.7
    elif user_choice == '9to18' and 9 <= random_number <= 18:
        win = True
        multiplier = 1.7
    elif user_choice.startswith('1st') and user_choice[3:] == str((random_number - 1) // 6 + 1):
        win = True
        multiplier = 1.7

    if random_number == 0:
        # Если выпало 0, пользователь проигрывает в любом случае
        result_message += "🔥 Проигрыш"
        new_balance = balance - bet
        #await db.add_commissionblack(user_id)
    elif win:
        win_amount = bet * multiplier
        win_amount_formatted = "{:,.0f}".format(win_amount).replace(",", ".")
        result_message += f"✅ Вы выиграли {win_amount_formatted} кут"
        new_balance = balance + win_amount
        #await db.add_commissionblack(user_id)
    else:
        result_message += f"🔥 Проигрыш"
        new_balance = balance - bet
        #await db.add_commissionblack(user_id)

    win_amount_rounded = round(new_balance)
    await db.update_user_balance(user_id, win_amount_rounded)

    result_msg = await bot1.send_message(
        chat_id=callback_query.message.chat.id, text=result_message, parse_mode="HTML")

    # Удаляем пользователя из списка игр
    gamesblack.remove(game)
async def update_keyboard(callback_query, user_choice):
    markup = callback_query.message.reply_markup
    for row in markup.inline_keyboard:
        for button in row:
            if button.callback_data == user_choice:
                button.text = "🟢"

    await bot1.edit_message_reply_markup(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, reply_markup=markup)

@dp.callback_query(lambda c: c.data.startswith('number_'))
async def number_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game = next((game for game in gamesblack if game['user_id'] == user_id), None)

    if game:
        number = callback_query.data.split('_')[1]
        await update_keyboard(callback_query, f"number_{number}")
        await check_result(user_id, number, callback_query)
    else:
        await callback_query.answer("Это не ваша игра")

@dp.callback_query(lambda c: c.data in ['1st6', '2nd6', '3rd6', '1to9', 'EVEN', 'red', 'black', 'ODD', '9to18'])
async def range_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game = next((game for game in gamesblack if game['user_id'] == user_id), None)

    if game:
        choice = callback_query.data
        await update_keyboard(callback_query, choice)
        await check_result(user_id, choice, callback_query)
    else:
        await callback_query.answer("Это не ваша игра")