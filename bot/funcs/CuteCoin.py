from main import *


cutecoinlist = {}
sellcutelist = {}
@dp.message()
async def cutecoin(message: Message):
    words = message.text.lower().split()

    if len(words) > 2 and words [ 0 ] == "купить":
        print("Обнаружено слово 'купить'")
        try:
            if words[1].isdigit() and words[2] in ["ктк"]:
                print('1')
                if "ктк" in words and words.index("ктк") == 2:
                    amount_to_buy = float(words [ 1 ])
                    print(f"Обнаружено количество: {amount_to_buy}, и 'ктк' на третьем месте")

                    user_id = message.from_user.id
                    current_balance = await db.get_user_balance(user_id)
                    current_cutecoin_rate = db.get_current_price()

                    if current_cutecoin_rate is not None:
                        if amount_to_buy > current_balance:
                            await message.reply("⚠️ Недостаточно средств для покупки")
                            return

                        total_cost = amount_to_buy * current_cutecoin_rate
                        win_amount_rounded = round(amount_to_buy)
                        abc = current_cutecoin_rate * win_amount_rounded
                        abc1 = abc - total_cost

                        total_cost1 = total_cost + abc1

                        loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                        loss_formatted = "{:,.0f}".format(total_cost).replace("," , ".")
                        amount_to_buy_formatted = "{:,.0f}".format(amount_to_buy).replace("," , ".")
                        keyboard = InlineKeyboardMarkup(row_width=2)
                        keyboard.add(
                            InlineKeyboardButton("Отмена" , callback_data="cancel3412_purchase") , InlineKeyboardButton(
                                "Купить" , callback_data=f"kow_purchase:{amount_to_buy}:{total_cost1}"))

                        sent_messagektk2 = await message.reply(
                            f"💠 За один Ктк : {loss_formatted1} кут\n💰 В итоге : {loss_formatted} кут"
                             , reply_markup=keyboard)

                        cutecoinlist [ user_id ] = sent_messagektk2.message_id

                        user_purchase_info [ user_id ] = {'amount_to_buy': amount_to_buy , 'total_cost': total_cost ,
                            'abc': abc}
                    else:
                        await message.reply("⚠️ Текущая цена куткоина недоступна. Пожалуйста, попробуйте позже.")
                    return
                else:
                    print("Некорректное использование 'ктк' в сообщении")




            elif words [ 1 ] in [ "ктк" , "куткоин" ] and words [ 2 ].isdigit():
                print('2')
                # Вариант: купить ктк (число)
                amount_to_buy = float(words [ 2 ])
                print(f"Обнаружено количество: {amount_to_buy}, и 'ктк' на третьем месте")

                user_id = message.from_user.id
                current_balance = await db.get_user_balance(user_id)
                current_cutecoin_rate = db.get_current_price()

                if current_cutecoin_rate is not None:
                    if current_cutecoin_rate <= amount_to_buy:
                        await message.reply("⚠️ Недостаточно средств для покупки")
                        return
                    if amount_to_buy <= current_balance:
                        total_cost = amount_to_buy * current_cutecoin_rate
                        win_amount_rounded = round(amount_to_buy)
                        abc = current_cutecoin_rate * win_amount_rounded
                        abc1 = abc - total_cost

                        total_cost1 = total_cost + abc1

                        loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                        loss_formatted = "{:,.0f}".format(total_cost).replace("," , ".")
                        amount_to_buy_formatted = "{:,.0f}".format(amount_to_buy).replace("," , ".")
                        keyboard = InlineKeyboardMarkup(row_width=2)
                        keyboard.add(
                            InlineKeyboardButton("Отмена" , callback_data="cancel3412_purchase") , InlineKeyboardButton(
                                "Купить" , callback_data=f"kow_purchase:{amount_to_buy}:{total_cost1}"))

                        sent_messagektk2 = await message.reply(
                            f"💠 За один Ктк : {loss_formatted1} кут\n💰 В итоге : {loss_formatted} кут\n" , reply_markup=keyboard)

                        cutecoinlist [ user_id ] = sent_messagektk2.message_id

                        user_purchase_info [ user_id ] = {'amount_to_buy': amount_to_buy , 'total_cost': total_cost ,
                                                          'abc': abc}
                    else:
                        await message.reply("⚠️ Недостаточно средств для покупки")
                else:
                    await message.reply("⚠️ Текущая цена куткоина недоступна. Пожалуйста, попробуйте позже.")
                return

            elif len(words) > 3 and words [ 0 ] == "купить" and words [ 1 ] in [ "кткоин" , "кт коин" , "кут коин" ,
                                                                               "коин" , "ктк" , "кт" ] and words [ 2 ] == "на" and words [ 3 ].isdigit():

                print("Обнаружено слово 'купить ктк на число'")
                amount_to_spend = float(words [ 3 ])
                print(f"Обнаружена сумма: {amount_to_spend}, и 'ктк' с 'на' на втором и третьем месте")

                # Логика для покупки на сумму
                user_id = message.from_user.id
                current_balance = await db.get_user_balance(user_id)
                current_cutecoin_rate = db.get_current_price()

                print(f"Баланс пользователя: {current_balance}")
                print(f"Текущая цена куткоина: {current_cutecoin_rate}")

                if current_cutecoin_rate is not None:
                    if amount_to_spend > current_balance:
                        await message.reply("⚠️ Недостаточно средств для покупки")
                        print("Недостаточно средств на балансе пользователя для покупки")
                        return

                    amount_to_buy = amount_to_spend / current_cutecoin_rate
                    print(f"Количество куткоинов к покупке: {amount_to_buy}")


                    win_amount_rounded = round(amount_to_buy)
                    abc = current_cutecoin_rate * win_amount_rounded
                    abc1 = abc - amount_to_spend

                    print(f"Округленное количество куткоинов: {win_amount_rounded}")
                    print(f"Стоимость покупки: {abc}")
                    print(f"Разница стоимости: {abc1}")


                    if abc == 0:
                        await message.reply("⚠️ Невозможно купить 0 КутКоинов")

                        return


                    total_cost1 = amount_to_spend + abc1

                    loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                    loss_formatted = "{:,.0f}".format(abc).replace("," , ".")
                    amount_to_buy_formatted = "{:,.0f}".format(amount_to_buy).replace("," , ".")
                    keyboard = InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        InlineKeyboardButton("Отмена" , callback_data="cancel3412_purchase") , InlineKeyboardButton(
                            "Купить" , callback_data=f"confirm3412_purchase:{amount_to_buy}:{total_cost1}"))

                    sent_messagektk2 = await message.reply(
                        f"💠 За один Ктк : {loss_formatted1} кут\n💰 В итоге : {loss_formatted} кут\n"
                        f"🪄 Возможно купить : {amount_to_buy_formatted} ктк" , reply_markup=keyboard)

                    cutecoinlist [ user_id ] = sent_messagektk2.message_id
                    print(f"Сообщение пользователю: {sent_messagektk2}")
                    print(f"Обновленный список сообщений: {cutecoinlist}")

                    # Сохранение данных о покупке пользователя
                    user_purchase_info [ user_id ] = {'amount_to_buy': amount_to_buy , 'total_cost': amount_to_spend ,
                                                      'abc': abc}
                    print(f"Информация о покупке пользователя: {user_purchase_info [ user_id ]}")
                else:
                    await message.reply("⚠️ Текущая цена куткоина недоступна. Пожалуйста, попробуйте позже.")
                    print("Текущая цена куткоина недоступна")
                return


        except (ValueError , IndexError) as e:
            print(f"Ошибка обработки: {e}")
            pass


    # Проверяем, содержит ли сообщение фразу "продать куткоин" или "Продать куткоин"
    words = message.text.lower().split()

    if "продать" in words and (
            "ктк" in words or any(word in words for word in [ "кткоин" , "кт коин" , "кут коин" , "коин" , "кт" ])):

        # Первый вариант: продать ктк (количество)
        pattern1 = r"^продать\s+ктк\s+(\d+)$"
        match1 = re.match(pattern1 , message.text , re.IGNORECASE)

        if match1:
            try:
                amount_to_sell = int(match1.group(1))

                user_id = message.from_user.id
                current_cutecoin_balance = db.get_user_cutecoin_balance(user_id)
                current_balance = await db.get_user_balance(user_id)
                current_cutecoin_rate = db.get_current_price()

                if current_cutecoin_balance >= amount_to_sell:
                    total_sale_amount = amount_to_sell * current_cutecoin_rate

                    # Создаем клавиатуру с кнопками "Отменить" и "Продать"
                    keyboard = types.InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        types.InlineKeyboardButton("Отмена" , callback_data="cancel_sell") ,
                        types.InlineKeyboardButton(
                            "Продать" , callback_data=f"confirm_sell:{amount_to_sell}:{total_sale_amount}"))

                    # Форматирование для вывода
                    loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                    loss_formatted = "{:,.0f}".format(total_sale_amount).replace("," , ".")
                    amount_to_sell_formatted = "{:,.0f}".format(amount_to_sell).replace("," , ".")

                    # Отправляем сообщение с клавиатурой
                    sent_sellcute = await message.reply(
                        f"🪄 Продажа <b>{amount_to_sell_formatted}</b> ктк\n💠 Стоимость ктк : {loss_formatted1}\n💰 Итого : {loss_formatted} кут" ,
                        parse_mode="HTML" , reply_markup=keyboard)

                    sellcutelist [ user_id ] = sent_sellcute.message_id
                    print(sellcutelist)

                else:
                    await message.reply("⚠️ Недостаточно ктк для продажи")
            except ValueError:
                pass

        # Второй вариант: продать (количество) ктк
        elif len(words) > 2 and words [ 0 ] == "продать" and words [ 1 ].isdigit() and (
                "ктк" in words or any(word in words for word in [ "кткоин" , "кт коин" , "кут коин" , "коин" , "кт" ])):
            try:
                amount_to_sell = int(words [ 1 ])

                user_id = message.from_user.id
                current_cutecoin_balance = db.get_user_cutecoin_balance(user_id)
                current_balance = await db.get_user_balance(user_id)
                current_cutecoin_rate = db.get_current_price()

                if current_cutecoin_balance >= amount_to_sell:
                    total_sale_amount = amount_to_sell * current_cutecoin_rate

                    # Создаем клавиатуру с кнопками "Отменить" и "Продать"
                    keyboard = types.InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        types.InlineKeyboardButton("Отмена" , callback_data="cancel_sell") ,
                        types.InlineKeyboardButton(
                            "Продать" , callback_data=f"confirm_sell:{amount_to_sell}:{total_sale_amount}"))

                    # Форматирование для вывода
                    loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                    loss_formatted = "{:,.0f}".format(total_sale_amount).replace("," , ".")
                    amount_to_sell_formatted = "{:,.0f}".format(amount_to_sell).replace("," , ".")

                    # Отправляем сообщение с клавиатурой
                    sent_sellcute = await message.reply(
                        f"🪄 Продажа <b>{amount_to_sell_formatted}</b> ктк\n💠 Стоимость ктк : {loss_formatted1}\n💰 Итого : {loss_formatted} кут" ,
                        parse_mode="HTML" , reply_markup=keyboard)
                    sellcutelist [ user_id ] = sent_sellcute.message_id
                    print(sellcutelist)
                else:
                    await message.reply("⚠️ Недостаточно ктк для продажи")
            except ValueError:
                pass

    @dp.callback_query(lambda c: c.data == 'cancel_sell')
    async def cancel_sell(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id



        randommessagehelp1 = random.choice(randommessagehelp)
        print("qqqqsqmdqosq1")


        if user_id not in sellcutelist or sellcutelist [ user_id ] != message_id:
            await callback_query.answer(randommessagehelp1)
            print("qqqqq15")
            return
        await callback_query.answer("Продажа ктк отменена.")
        await callback_query.message.delete()

    @dp.callback_query(lambda c: c.data.startswith('confirm_sell'))
    async def confirm_sell(callback_query: types.CallbackQuery):

        try:
            user_id = callback_query.from_user.id
            message_id = callback_query.message.message_id


            randommessagehelp1 = random.choice(randommessagehelp)
            print("qqqqq16")

            if user_id not in sellcutelist or sellcutelist [ user_id ] != message_id:
                await callback_query.answer(randommessagehelp1)
                return

            # Извлекаем данные из callback_data
            data = callback_query.data.split(':')
            amount_to_sell = int(data [ 1 ])
            total_sale_amount = float(data [ 2 ])

            # Получаем текущий баланс ктк пользователя
            current_cutecoin_balance = db.get_user_cutecoin_balance(user_id)
            current_balance = await db.get_user_balance(user_id)
            current_cutecoin_rate = db.get_current_price()

            item_to_sell = "💠 CuteCoin"
            quantity_to_sell = amount_to_sell

            # Получаем текущий инвентарь ктк пользователя из базы данных
            inventory = await db.get_user_inventorycutecoin(user_id)

            if item_to_sell in inventory and inventory [ item_to_sell ] >= quantity_to_sell:
                # Вычитаем проданные ктк из инвентаря
                inventory [ item_to_sell ] -= quantity_to_sell
                if inventory [ item_to_sell ] == 0:
                    del inventory [ item_to_sell ]

                # Обновляем инвентарь в базе данных
                await db.increase_item_quantity(item_to_sell , quantity_to_sell)
                await db.set_user_inventorycutecoin(user_id , inventory)

                # Обновляем балансы и количество ктк
                db.update_user_cutecoin_balance(user_id , - amount_to_sell)
                await db.update_user_balance(user_id , current_balance + total_sale_amount)

                # Форматирование для вывода
                loss_formatted1 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
                loss_formatted = "{:,.0f}".format(total_sale_amount).replace("," , ".")
                amount_to_sell_formatted = "{:,.0f}".format(amount_to_sell).replace("," , ".")

                # Отправляем сообщение о продаже ктк и увеличении баланса
                await callback_query.message.edit_text(
                    f"💠 Вы продали <b>{amount_to_sell_formatted}</b> ктк\n🦋 За один ктк : {loss_formatted1}\n💰 Итого : {loss_formatted} кут" ,
                    parse_mode="HTML")

                # Уведомляем пользователя через callback_query.answer
                await callback_query.answer("Продажа ктк выполнена успешно.")

            else:
                await callback_query.answer("⚠️ Недостаточно ктк для продажи.")

        except (ValueError , IndexError , KeyError):
            await callback_query.answer("Произошла ошибка при обработке запроса.")




    if message.text.lower() in [ "курс куткоина" , "Курс куткоина" , "курс кут коина" , "Курс кут коина" , "курс" ,
                                 "Курс" , "курс кткоина" , "Курс кткоина" , "курс кт коина" , "Курс кт коина" ,
                                 "Курс кт" , "курс кт" , "Курс ктк" , "курс ктк" ]:
        # Получаем текущую цену из базы данных
        current_cutecoin_rate = db.get_current_price()
        if current_cutecoin_rate is not None:
            loss_formatted11 = "{:,.0f}".format(current_cutecoin_rate).replace("," , ".")
            # Отправляем сообщение с текущей ценой куткоина
            await message.reply(
                f"💱 Текущий курс КтКоина: <b>{loss_formatted11}</b> кут" , parse_mode="HTML")
        else:
            await message.reply("❌ Текущий курс КтКоина не доступен.")
#ошибка тут
    async def price_updater():
        while True:
            # Проверяем, было ли обновление базовой цены
            await asyncio.sleep(120)
            if db.base_price_updated:
                #db_cointime.base_price_updated = False  # Сбрасываем флаг обновления
                continue  # Пропускаем генерацию новой цены

            # Генерация новой цены
            random_change = random.randint(CuteCoinM , CuteCoinP)
            #new_price = db_cointime.base_price + random_change
            # Обновление цены в базе данных
            #db_cointime.update_price(new_price)

            # Ожидание 10 секунд


    # Создаем задачу для асинхронной функции price_updater
    price_updater_task = asyncio.create_task(price_updater())

    # Обработка сообщений пользователя

    parts = message.text.lower().split()
    if len(parts) > 2 and parts [ 0 ] == "новый" and parts [ 1 ] == "курс":
        if message.from_user.id == 999884389:
            try:
                # Получаем новую базовую цену из сообщения
                new_base_price = float(parts [ 2 ])
                # Обновляем базовую цену в объекте базы данных
                #db_cointime.base_price = new_base_price
                #db_cointime.base_price_updated = True  # Устанавливаем флаг обновления
                # Отправляем сообщение об успешном обновлении базовой цены
                await message.reply("✅ Базовая цена успешно обновлена.")
                # Отменяем предыдущую задачу и запускаем новую
                price_updater_task.cancel()
                price_updater_task = asyncio.create_task(price_updater())
            except ValueError:
                # Если введена некорректная цена, отправляем сообщение об ошибке
                await message.reply("❌ Некорректная цена.")




@dp.callback_query(lambda c: c.data.startswith('cancel3412_purchase'))
async def process_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id




    randommessagehelp1 = random.choice(randommessagehelp)
    print("qqqqq17")

    if user_id not in cutecoinlist or cutecoinlist [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer("Сообщение с покупкой КТкоинов удалено")
    await callback_query.message.delete()
    del user_purchase_info [ user_id ]


@dp.callback_query(lambda c: c.data.startswith('confirm3412_purchase'))
async def process_callback(callback_query: types.CallbackQuery):


    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id




    randommessagehelp1 = random.choice(randommessagehelp)
    print("qqqqq18")

    if user_id not in cutecoinlist or cutecoinlist [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    # Check if the user initiated a purchase

    purchase_data = user_purchase_info [ user_id ]



    amount_to_buy = user_purchase_info [ user_id ] [ 'amount_to_buy' ]
    total_cost = user_purchase_info [ user_id ] [ 'total_cost' ]
    current_balance = await db.get_user_balance(user_id)

    if amount_to_buy > 500:
        await callback_query.message.edit_text("⚠️ Вы не можете купить больше 500 КтКоинов за один раз.")
        return

    if current_balance >= total_cost:
        abc = user_purchase_info [ user_id ] [ 'abc' ]
        await db.update_user_balance(user_id , current_balance - abc)  # Обновление баланса после покупки
        win_amount_rounded = round(amount_to_buy)

        item_index = 1  # Замените на индекс вашего предмета
        item_name , bought_quantity = await db.buy_item(item_index , win_amount_rounded)

        # Добавляем купленный предмет "💠 CuteCoin" в инвентарь пользователя
        if item_name == "💠 CuteCoin" and bought_quantity is not None and bought_quantity > 0:
            await db.set_items(user_id , item_name , bought_quantity)  # Добавляем купленное количество CuteCoin
            db.update_user_cutecoin_balance(
                user_id , win_amount_rounded)
            loss_formatted = "{:,.0f}".format(abc).replace("," , ".")  # Выводим стоимость покупки
            loss_formatted1 = "{:,.0f}".format(amount_to_buy).replace("," , ".")
            await callback_query.answer("Успешная покупка")
            await callback_query.message.edit_text(
                f"💠 Вы купили <b>{loss_formatted1}</b> КТкоинов\n💰 Цена покупки : {loss_formatted} кут" ,
                parse_mode="HTML")

    else:
        await callback_query.message.answer("⚠️ Недостаточно средств для покупки")

    # Clear the user's purchase data
    del user_purchase_info [ user_id ]




@dp.callback_query(lambda c: c.data.startswith('kow_purchase'))
async def process_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    # Проверяем, что пользователь имеет доступ к покупке
    if user_id not in cutecoinlist or cutecoinlist[user_id] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    purchase_data = user_purchase_info[user_id]

    amount_to_buy = int(purchase_data['amount_to_buy'])  # Преобразуем в целое число
    total_cost = purchase_data['total_cost']
    current_balance = await db.get_user_balance(user_id)

    # Ограничиваем количество покупаемых КТкоинов до максимума в 100
    if amount_to_buy > 500:
        await callback_query.message.edit_text("⚠️ Вы не можете купить больше 500 КтКоинов за один раз.")
        return

    if current_balance >= total_cost:
        # Вычитаем стоимость покупки из баланса пользователя
        new_balance = current_balance - total_cost
        await db.update_user_balance(user_id, new_balance)

        # Пытаемся купить предмет
        item_index = 1  # Замените на индекс вашего предмета
        item_name, bought_quantity = await db.buy_item(item_index, amount_to_buy)

        # Добавляем купленный предмет "💠 CuteCoin" в инвентарь пользователя
        if item_name == "💠 CuteCoin" and bought_quantity is not None and bought_quantity > 0:
            await db.set_items(user_id, item_name, bought_quantity)  # Добавляем купленное количество CuteCoin

            # Обновляем баланс CuteCoin пользователя (необязательный шаг)
            db.update_user_cutecoin_balance(user_id, amount_to_buy)

            loss_formatted = "{:,.0f}".format(total_cost).replace(",", ".")
            loss_formatted1 = "{:,.0f}".format(amount_to_buy).replace(",", ".")
            await callback_query.answer("Успешная покупка")
            await callback_query.message.edit_text(
                f"💠 Вы купили <b>{loss_formatted1}</b> КтКоинов\n💰 Цена покупки : {loss_formatted} кут",
                parse_mode="HTML")
        else:
            await callback_query.message.edit_text("⚠️ КтК нет в наличии магазина")
    else:
        await callback_query.message.edit_text("⚠️ Недостаточно средств для покупки")

    # Очищаем данные о покупке пользователя
    del user_purchase_info[user_id]


