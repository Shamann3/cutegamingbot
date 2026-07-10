from main import *
user_message_crash = {}
@dp.message()
async def crash(message: Message):
    if message.text [ :4 ] in [ "/cra" , "краш34123412" , "Краш34123412" , "/краш34123412" , "🚀 Краш34123412" ]:

        if len(message.text.split()) > 2:

            username = message.from_user.username
            user_id = message.from_user.id
            balance = await db.get_user_balance(user_id)  # Получаем баланс пользователя

            # Получаем ставки и удаляем запятые и точки для корректного преобразования
            bet_amount1_str = message.text.split() [ 2 ].replace(',' , '').replace('.' , '')
            bet_amount_str = message.text.split() [ 1 ].replace(',' , '').replace('.' , '')

            if bet_amount1_str.isdigit() and bet_amount_str.isdigit():
                bet_amount1 = int(bet_amount1_str)
                bet_amount = int(bet_amount_str)
            else:
                await message.reply("⚠️ Неверный формат ставки")
                return

            print(bet_amount)
            print(balance)

            if balance >= bet_amount1:

                # Если у пользователя достаточно средств, размещаем ставку
                db.set_bet(user_id , bet_amount)

                if bet_amount <= 1:
                    await message.reply("⚠️ Коэффициент должен быть больше 1")
                    return

                # Генерация случайного числа от 0 до 600
                if random.random() < 0.35:
                    print('[КРАШ] Плохой рандом')
                    random_coefficient = random.uniform(0.1 , 1.5)
                else:
                    print('[КРАШ] Хороший рандом')
                    random_value = random.randint(0 , 400)
                    random_coefficient = random_value / 100 if random_value != 0 else 0

                # Вывод значения для отладки с форматированием до одного знака после запятой
                print(f"[Краш] Рандом: {random_coefficient:.1f}")

                # Увеличиваем вероятность выпадения маленьких чисел
                if random_coefficient <= 3 or random.random() < 0.6:
                    random_coefficient = min(random_coefficient , 3)  # Ограничиваем максимальное значение в 3

                if db.user_exists(user_id):
                    db.set_koef(user_id , random_coefficient)
                    db.set_koef_from_user(user_id , bet_amount1)

                    dice = bet_amount1
                    formatted_dice = "{:,.0f}".format(dice).replace(',' , '.')
                    winnings_str = "{:,.0f}".format(bet_amount).replace("," , ".")

                    sent_crash = await message.reply(
                        f"🚀 Подготовка к старту\n✨ Ставка: {formatted_dice}\n📯 {winnings_str}" ,
                        reply_markup=start_markup)

                    user_message_crash [ user_id ] = sent_crash.message_id
                    print(user_message_crash)

                    if bet_amount1 > random_coefficient:
                        print(f"[Краш]: {username} проиграл.")
                    else:
                        print(f"[Краш]: {username} выиграл.")

                else:
                    db.add_user_crash(user_id , random_coefficient , bet_amount1 , bet_amount)
                    await message.reply(
                        f"🚀 Ждём запуска\n💫 Коэфициент: {bet_amount1}" , reply_markup=start_markup)

                    if bet_amount1 > random_coefficient:
                        print(f"[Краш] {username} выиграл.")
                    else:
                        print(f"[Краш] {username} проиграл.")

            else:
                await message.reply(f"🔥 Недостаточно денег")

        else:
            print("[Краш] Сообщение для краша неправильно.")





user_coefficients = {}

@dp.callback_query(lambda c: c.data.startswith('start_btn'))
async def accept(call: types.CallbackQuery):
    user_id = call.from_user.id
    users = await db.get_data_users()
    random_coefficient = 0
    user_coefficient = 0
    message_id = call.message.message_id

    #randommessagehelp1 = random.choice(randommessagehelp)
    #if user_id not in user_message_crash or user_message_crash [ user_id ] != message_id:
    #    await call.answer(randommessagehelp1)
    #    return



    for row in users:
        if row [ 0 ] == user_id:
            random_coefficient = float(row [ 1 ])
            user_coefficient = float(row [ 3 ])
            break

    current_value = 1.0
    last_message = None
    kommission_crash = kommission_crash1

    rocket_message = await call.message.answer("🚀")  # Эмодзи с анимацией перед сообщением

    if user_coefficient >= 10:
        await call.message.reply('⚠️ Максимальный коэффициент 10')

    if user_coefficient <= 1.9:
        kommission_crash = 0.10

    while current_value <= random_coefficient:
        if int(current_value * 10) % 10 == 0:
            try:
                new_message = f"🚀 Ракета в полёте ~ <b>{current_value:.1f}</b>\n📯 {user_coefficient:.1f}"
                if new_message != last_message:
                    await call.message.edit_text(text=new_message , parse_mode="HTML")
                    last_message = new_message
            except aiogram.utils.exceptions.RetryAfter as e:
                await asyncio.sleep(e.timeout)
                continue
        current_value += 0.3
        await asyncio.sleep(0.80)

        try:
            new_message = f"🚀 Ракета в полёте ~ <b>{current_value:.1f}</b>\n📯 {user_coefficient:.1f}"
            if new_message != last_message:
                await call.message.edit_text(text=new_message , parse_mode="HTML")
                last_message = new_message
        except aiogram.utils.exceptions.RetryAfter as e:
            await asyncio.sleep(e.timeout)
            continue

    print("[КРАШ] Коэффициент пользователя :" , user_coefficient)

    if 1.1 <= user_coefficient <= 1.9:
        warning_message = "\n⚠️ 1.1-1.9 = большая комиссия"
    else:
        warning_message = ""

    if current_value >= user_coefficient:
        print("Пользователь выиграл!")
        for row in await db.get_data_users():
            if int(row [ 0 ]) == user_id:
                for row1 in await db.get_data_users():
                    if user_id == int(row1 [ 0 ]):
                        total_winnings = float(row1 [ 2 ]) * user_coefficient
                        commission = total_winnings * kommission_crash
                        total_winnings -= commission
                        await db.update_user_balance(int(row [ 0 ]) , int(row [ 1 ]) + int(total_winnings) - int(row1 [ 2 ]))
                        total = total_winnings - int(row1 [ 2 ])
                        print(f"Ставка пользователя: {int(row1 [ 2 ])}")
                        print(f"Комиссия: {commission}")
                        print(f"Выигрыш с учетом комиссии: {total_winnings}")
                        win_amount_rounded1111 = round(total)

                        #await db.add_commissioncrash(user_id , win_amount_rounded1111 , winner='user')

        total_winnings_formatted = "{:,.2f}".format(total_winnings).replace(',' , '.').rstrip('0').rstrip('.')

        # Не изменяем эмодзи в случае выигрыша
        await db.add_xp_to_games(user_id)
        if warning_message:
            message_text = f"✅ Успешный полёт ~ <b>{current_value:.1f}</b>\n💸 Выигрыш <b>{total_winnings_formatted}</b>\n📯 {user_coefficient:.1f}{warning_message}"
        else:
            message_text = f"✅ Успешный полёт ~ <b>{current_value:.1f}</b>\n💸 Выигрыш <b>{total_winnings_formatted}</b>\n📯 {user_coefficient:.1f}"

        await call.message.edit_text(
            text=message_text , parse_mode="HTML")
    else:
        print("Пользователь проиграл!")
        # Изменяем эмодзи в случае проигрыша
        await rocket_message.edit_text("💥")
        for row in await db.get_data_users():
            if int(row [ 0 ]) == user_id:
                for row1 in await db.get_data_users():
                    if user_id == int(row1 [ 0 ]):
                        await db.update_user_balance(int(row [ 0 ]) , int(row [ 1 ]) - int(row1 [ 2 ]))

                        #await db.add_commissioncrash(user_id , int(row1 [ 2 ]) , winner='bot')

        await call.message.edit_text(
            text=f"💥 Ракета разбилась ~ <b>{current_value:.1f}</b>\n📯 {user_coefficient:.1f}{warning_message}" ,
            parse_mode="HTML")


