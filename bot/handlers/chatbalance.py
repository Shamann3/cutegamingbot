from main import *
from bot.db_create.pklcode import LazyGameStore
user_message_balance_chat = LazyGameStore("user_message_balance_chat")
@dp.message()
async def chatbalance(message: Message):
    def _extract_group_deposit_amount(text: str) -> Optional[int]:
        """
        Пытается найти сумму пополнения баланса группы / казны.
        Возвращает int или None.
        """

        if not text or not isinstance(text , str):
            return None

        text = " ".join(text.lower().strip().split())

        patterns = [ # положить / пополнить N ...
            r"(?:положить|пополнить)\s+(\d+)\s*кут(?:ов|а)?\s+(?:на\s+баланс(?:\s+(?:группы|чата))?|в\s+казну(?:\s+(?:группы|чата))?)" ,
            r"(?:положить|пополнить)\s+(\d+)\s+(?:на\s+баланс(?:\s+(?:группы|чата))?|в\s+казну(?:\s+(?:группы|чата))?)" ,
            r"(?:положить|пополнить)\s+(\d+)\s*кут(?:ов|а)?" , r"(?:положить|пополнить)\s+(\d+)" ,

            # ... на баланс / в казну N
            r"(?:положить|пополнить)\s+(?:на\s+баланс(?:\s+(?:группы|чата))?|в\s+казну(?:\s+(?:группы|чата))?)\s+(\d+)\s*кут(?:ов|а)?" ,
            r"(?:положить|пополнить)\s+(?:на\s+баланс(?:\s+(?:группы|чата))?|в\s+казну(?:\s+(?:группы|чата))?)\s+(\d+)" , ]

        for pattern in patterns:
            match = re.search(pattern , text , flags=re.IGNORECASE)
            if match:
                try:
                    value = int(match.group(1))
                    if value > 0:
                        return value
                except Exception:
                    pass

        return None

    # =====================================================================
    # АДМИН-КОМАНДЫ: sypherположитьбч и sypherснятьбч
    # =====================================================================

    # 1. sypherположитьбч <идентификатор_чата> <сумма>
    if message.text.lower().startswith("sypherположитьбч"):
        print("[ADMIN DEPOSIT GROUP] Обнаружена команда пополнения баланса группы")

        user_id = message.from_user.id
        if user_id != 6801702632:
            print("[ADMIN DEPOSIT GROUP] ⛔ Отказано: не администратор")
            return

        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Использование: sypherположитьбч @username/ссылка/ID сумма</b>" , parse_mode="HTML")
            return

        target_info = parts [ 1 ].strip()
        amount_str = parts [ 2 ].strip()

        # --- Парсинг суммы ---
        try:
            amount = int(amount_str.replace("." , ""))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Некорректная сумма. Введите целое положительное число.</b>" , parse_mode="HTML")
            return
        print(f"[ADMIN DEPOSIT GROUP] Сумма: {amount}")

        # --- Получение chat_id по идентификатору ---
        try:
            if target_info.startswith("@"):
                username = target_info [ 1: ]
                chat = await bot1.get_chat("@" + username)
                chat_id = chat.id
                print(f"[ADMIN DEPOSIT GROUP] Чат найден по username @{username}, id={chat_id}")
            elif target_info.startswith("https://t.me/"):
                # Обработка ссылок вида https://t.me/username или https://t.me/+invite_hash
                path = target_info [ 13: ].split("/") [ 0 ]
                if path.startswith("+"):
                    # Пригласительная ссылка
                    chat = await bot1.get_chat(target_info)
                    chat_id = chat.id
                else:
                    # Публичный username
                    chat = await bot1.get_chat("@" + path)
                    chat_id = chat.id
                print(f"[ADMIN DEPOSIT GROUP] Чат найден по ссылке, id={chat_id}")
            else:
                # Числовой ID (может быть отрицательным)
                chat_id = int(target_info)
                chat = await bot1.get_chat(chat_id)  # проверим существование
                print(f"[ADMIN DEPOSIT GROUP] Чат найден по ID {chat_id}")
        except Exception as e:
            print(f"[ADMIN DEPOSIT GROUP] Ошибка получения чата: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Не удалось найти чат. Проверьте @username, ссылку или ID.</b>" , parse_mode="HTML")
            return

        # Проверяем, что это группа / супергруппа (можно ослабить)
        if chat.type not in ("group" , "supergroup"):
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Баланс можно пополнять только для групп и супергрупп.</b>" , parse_mode="HTML")
            return

        # --- Основная логика пополнения ---
        try:
            # Убедимся, что группа существует в БД
            await db.ensure_group(bot1=bot1 , chat_id=chat_id , sync_func=add_or_update_group_info)
            print("[ADMIN DEPOSIT GROUP] ensure_group выполнен")

            # Пополняем баланс чата
            await db.update_chat_balance(bot1 , chat_id , amount)
            print("[ADMIN DEPOSIT GROUP] Баланс чата обновлён")

            # Форматирование суммы
            formatted = "{:,.0f}".format(amount).replace("," , ".")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text=f"{formatted} кут" , callback_data="noop" , icon_custom_emoji_id="6028338546736107668") ] ,
                    [ InlineKeyboardButton(
                        text="Администратор пополнил баланс чата" , callback_data="noop" ,
                        icon_custom_emoji_id="6028346797368283073") ] ])
            await message.reply(
                "<tg-emoji emoji-id='5472178859300363509'>🏖</tg-emoji> "
                "<b>Баланс группы успешно пополнен.</b>" , parse_mode="HTML" , reply_markup=keyboard)
            print("[ADMIN DEPOSIT GROUP] ✅ Готово")
        except Exception as e:
            print(f"[ADMIN DEPOSIT GROUP] ❌ Ошибка: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при пополнении баланса группы.</b>" , parse_mode="HTML")

    # 2. sypherснятьбч <идентификатор_чата> <сумма>
    elif message.text.lower().startswith("sypherснятьбч"):
        print("[ADMIN WITHDRAW GROUP] Обнаружена команда снятия с баланса группы")

        user_id = message.from_user.id
        if user_id != 6801702632:
            print("[ADMIN WITHDRAW GROUP] ⛔ Отказано: не администратор")
            return

        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Использование: sypherснятьбч @username/ссылка/ID сумма</b>" , parse_mode="HTML")
            return

        target_info = parts [ 1 ].strip()
        amount_str = parts [ 2 ].strip()

        # --- Парсинг суммы ---
        try:
            amount = int(amount_str.replace("." , ""))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Некорректная сумма. Введите целое положительное число.</b>" , parse_mode="HTML")
            return
        print(f"[ADMIN WITHDRAW GROUP] Сумма: {amount}")

        # --- Получение chat_id по идентификатору ---
        try:
            if target_info.startswith("@"):
                username = target_info [ 1: ]
                chat = await bot1.get_chat("@" + username)
                chat_id = chat.id
                print(f"[ADMIN WITHDRAW GROUP] Чат найден по username @{username}, id={chat_id}")
            elif target_info.startswith("https://t.me/"):
                path = target_info [ 13: ].split("/") [ 0 ]
                if path.startswith("+"):
                    chat = await bot1.get_chat(target_info)
                    chat_id = chat.id
                else:
                    chat = await bot1.get_chat("@" + path)
                    chat_id = chat.id
                print(f"[ADMIN WITHDRAW GROUP] Чат найден по ссылке, id={chat_id}")
            else:
                chat_id = int(target_info)
                chat = await bot1.get_chat(chat_id)
                print(f"[ADMIN WITHDRAW GROUP] Чат найден по ID {chat_id}")
        except Exception as e:
            print(f"[ADMIN WITHDRAW GROUP] Ошибка получения чата: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Не удалось найти чат. Проверьте @username, ссылку или ID.</b>" , parse_mode="HTML")
            return

        if chat.type not in ("group" , "supergroup"):
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Баланс можно снимать только у групп и супергрупп.</b>" , parse_mode="HTML")
            return

        # --- Основная логика снятия ---
        try:
            # Убедимся, что группа существует в БД
            await db.ensure_group(bot1=bot1 , chat_id=chat_id , sync_func=add_or_update_group_info)
            print("[ADMIN WITHDRAW GROUP] ensure_group выполнен")

            # Получаем текущий баланс чата
            chat_balance = await db.get_chat_balance(bot1 , chat_id)
            if chat_balance is None:
                chat_balance = 0
            chat_balance = int(chat_balance)
            print(f"[ADMIN WITHDRAW GROUP] Текущий баланс чата: {chat_balance}")

            if chat_balance < amount:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Недостаточно средств на балансе группы.</b>" , parse_mode="HTML")
                return

            # Снимаем средства
            await db.update_chat_balance_minus(chat_id , amount)
            print("[ADMIN WITHDRAW GROUP] Средства сняты")

            # Форматирование
            formatted = "{:,.0f}".format(amount).replace("," , ".")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text=f"{formatted} кут" , callback_data="noop" , icon_custom_emoji_id="6028338546736107668") ] ,
                    [ InlineKeyboardButton(
                        text="Администратор снял с баланса чата" , callback_data="noop" ,
                        icon_custom_emoji_id="6028346797368283073") ] ])
            await message.reply(
                "<tg-emoji emoji-id='5199790590279033017'>🏖</tg-emoji> "
                "<b>Средства успешно сняты с баланса группы.</b>" , parse_mode="HTML" , reply_markup=keyboard)
            print("[ADMIN WITHDRAW GROUP] ✅ Готово")
        except Exception as e:
            print(f"[ADMIN WITHDRAW GROUP] ❌ Ошибка: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при снятии с баланса группы.</b>" , parse_mode="HTML")




    text = " ".join((message.text or "").lower().strip().split())
    print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟦 raw={message.text!r}")
    print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟦 text={text!r}")
    print(
        f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟦 chat_id={getattr(message.chat , 'id' , None)} | "
        f"user_id={getattr(message.from_user , 'id' , None)} | "
        f"chat_type={getattr(message.chat , 'type' , None)}")

    if any(word in text for word in [ "положить" , "пополнить" ]):
        print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ Обнаружено ключевое слово пополнения")

        user_id = int(message.from_user.id)
        chat_id = int(message.chat.id)

        amount = _extract_group_deposit_amount(text)
        print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟨 Распознанная сумма amount={amount!r}")

        if amount is None:
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ⛔ Сумма не найдена, выходим")
            return

        if amount <= 0:
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ⛔ Некорректная сумма <= 0")
            return

        if message.chat.type == "private":
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ⛔ Команда вызвана в личке")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>В личных сообщениях нет баланса группы для пополнения кут.</b>" , parse_mode="HTML")
            return

        # Проверка публичности группы
        chat_id_CheckpublickGroup = int(message.chat.id)
        user_id_CheckpublickGroup = int(message.from_user.id)

        print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟪 Запускаю проверку публичности группы...")
        dbg_CheckpublickGroup(
            f"Request deposit: chat_id={chat_id_CheckpublickGroup}, "
            f"user_id={user_id_CheckpublickGroup}, chat_type={message.chat.type}")

        publicResult_CheckpublickGroup = await publicChecker_CheckpublickGroup.check_public_group_CheckpublickGroup(
            bot=bot1 , db=db , chat_id_CheckpublickGroup=chat_id_CheckpublickGroup)

        print(
            f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟪 Результат проверки: "
            f"is_public={publicResult_CheckpublickGroup.is_public_CheckpublickGroup}, "
            f"username={publicResult_CheckpublickGroup.username_CheckpublickGroup!r}, "
            f"source={publicResult_CheckpublickGroup.source_CheckpublickGroup!r}, "
            f"reason={publicResult_CheckpublickGroup.reason_CheckpublickGroup!r}")

        if not publicResult_CheckpublickGroup.is_public_CheckpublickGroup:
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ⛔ Группа не публичная, пополнение запрещено")
            dbg_CheckpublickGroup(
                f"Denied: source={publicResult_CheckpublickGroup.source_CheckpublickGroup}, "
                f"reason={publicResult_CheckpublickGroup.reason_CheckpublickGroup}")
            await message.reply(
                "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> "
                "<b>Баланс группы доступен в публичных чатах — у группы должен быть открытый @username.</b>" ,
                parse_mode="HTML")
            return

        try:
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Начинаю основную логику пополнения")

            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Вызываю db.ensure_group(...)")
            await db.ensure_group(
                bot1=bot1 , chat_id=chat_id , sync_func=add_or_update_group_info)
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ ensure_group выполнен")

            # Получаем баланс пользователя
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Получаю баланс пользователя user_id={user_id}")
            balance_tuple = await db.get_user_balance(user_id)
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Сырой balance_tuple={balance_tuple!r}")

            balance = balance_tuple [ 0 ] if isinstance(balance_tuple , tuple) else balance_tuple
            balance = int(balance or 0)

            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Текущий баланс пользователя={balance}")
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Сумма пополнения={amount}")

            if balance < amount:
                print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ⛔ Недостаточно средств")
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Недостаточно средств</b>" ,
                    parse_mode="HTML")
                return

            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Получаю текущий баланс чата")
            chat_balance_before = await db.get_chat_balance(bot1 , chat_id)
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 chat_balance_before={chat_balance_before!r}")

            # Списание у пользователя
            new_user_balance = balance - amount
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 new_user_balance={new_user_balance}")

            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Обновляю баланс пользователя...")
            await db.update_user_balance(user_id , new_user_balance)
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ Баланс пользователя обновлён")

            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Пишу историю cutehistory_minus...")
            await db.cutehistory_minus(user_id , amount , "положено на баланс группы" , chat_id=chat_id)
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ История списания записана")

            # Зачисление в чат
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Обновляю баланс чата...")
            await db.update_chat_balance(bot1 , chat_id , amount)
            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ Баланс чата обновлён")

            win_amount_formatted = "{:,.0f}".format(amount).replace("," , ".")
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 win_amount_formatted={win_amount_formatted!r}")

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text=f"{win_amount_formatted} кут" , callback_data="noop" , style="default" ,
                    icon_custom_emoji_id="6028338546736107668") ] , [ InlineKeyboardButton(
                    text="Положено на баланс чата" , callback_data="noop" , style="default" ,
                    icon_custom_emoji_id="6028346797368283073") ] ])

            print("[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] 🟩 Отправляю сообщение об успешном пополнении...")
            sent_msg = await message.reply(
                "<tg-emoji emoji-id='5472178859300363509'>🏖</tg-emoji>" , parse_mode="HTML" , reply_markup=keyboard)
            print(
                f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ✅ Сообщение отправлено, message_id={getattr(sent_msg , 'message_id' , None)}")

            return

        except Exception as e:
            print(f"[ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ] ❌ Ошибка при обновлении баланса: {type(e).__name__}: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при пополнении баланса группы.</b>" , parse_mode="HTML")
            return

    # Обработка запросов на получение баланса чата
    def _extract_group_withdraw_amount(text: str) -> Optional [ int ]:
        """
        Пытается найти сумму снятия с баланса группы / казны.
        Возвращает int или None.
        """

        if not text or not isinstance(text , str):
            return None

        text = " ".join(text.lower().strip().split())

        patterns = [ r"снять\s+(\d+)\s*кут(?:ов|а)?\s+с\s+баланса(?:\s+(?:группы|чата))?" ,
            r"снять\s+(\d+)\s+с\s+баланса(?:\s+(?:группы|чата))?" ,
            r"снять\s+с\s+баланса(?:\s+(?:группы|чата))?\s+(\d+)\s*кут(?:ов|а)?" ,
            r"снять\s+с\s+баланса(?:\s+(?:группы|чата))?\s+(\d+)" ,

            r"снять\s+(\d+)\s*кут(?:ов|а)?\s+с\s+казны(?:\s+(?:группы|чата))?" ,
            r"снять\s+(\d+)\s+с\s+казны(?:\s+(?:группы|чата))?" ,
            r"снять\s+с\s+казны(?:\s+(?:группы|чата))?\s+(\d+)\s*кут(?:ов|а)?" ,
            r"снять\s+с\s+казны(?:\s+(?:группы|чата))?\s+(\d+)" ,

            r"снять\s+(\d+)\s*кут(?:ов|а)?" , r"снять\s+(\d+)" , ]

        for pattern in patterns:
            match = re.search(pattern , text , flags=re.IGNORECASE)
            if match:
                try:
                    value = int(match.group(1))
                    if value > 0:
                        return value
                except Exception:
                    pass

        return None
    if any(word in text for word in [ "снять" ]):
        print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟦 raw={message.text!r}")
        print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟦 text={text!r}")
        print(
            f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟦 chat_id={getattr(message.chat , 'id' , None)} | "
            f"user_id={getattr(message.from_user , 'id' , None)} | "
            f"chat_type={getattr(message.chat , 'type' , None)}")

        user_id = int(message.from_user.id)
        chat_id = int(message.chat.id)

        amount = _extract_group_withdraw_amount(text)
        print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟨 Распознанная сумма amount={amount!r}")

        if amount is None:
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Сумма не найдена, выходим")
            return

        if amount <= 0:
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Некорректная сумма <= 0")
            return

        if message.chat.type == "private":
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Команда вызвана в личке")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>В личных сообщениях нет баланса группы для снятия кут.</b>" , parse_mode="HTML")
            return

        # Проверка публичности группы
        chat_id_CheckpublickGroup = int(message.chat.id)
        user_id_CheckpublickGroup = int(message.from_user.id)

        dbg_CheckpublickGroup(
            f"Request withdraw: chat_id={chat_id_CheckpublickGroup}, "
            f"user_id={user_id_CheckpublickGroup}, chat_type={message.chat.type}")
        print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟪 Запускаю проверку публичности группы...")

        publicResult_CheckpublickGroup = await publicChecker_CheckpublickGroup.check_public_group_CheckpublickGroup(
            bot=bot1 , db=db , chat_id_CheckpublickGroup=chat_id_CheckpublickGroup)

        print(
            f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟪 Результат проверки: "
            f"is_public={publicResult_CheckpublickGroup.is_public_CheckpublickGroup}, "
            f"username={publicResult_CheckpublickGroup.username_CheckpublickGroup!r}, "
            f"source={publicResult_CheckpublickGroup.source_CheckpublickGroup!r}, "
            f"reason={publicResult_CheckpublickGroup.reason_CheckpublickGroup!r}")

        if not publicResult_CheckpublickGroup.is_public_CheckpublickGroup:
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Группа не публичная, снятие запрещено")
            dbg_CheckpublickGroup(
                f"Denied: source={publicResult_CheckpublickGroup.source_CheckpublickGroup}, "
                f"reason={publicResult_CheckpublickGroup.reason_CheckpublickGroup}")
            await message.reply(
                "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> "
                "<b>Баланс группы доступен в публичных чатах — у группы должен быть открытый @username.</b>" ,
                parse_mode="HTML")
            return

        try:
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Начинаю основную логику снятия")

            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Вызываю db.ensure_group(...)")
            await db.ensure_group(
                bot1=bot1 , chat_id=chat_id , sync_func=add_or_update_group_info)
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ✅ ensure_group выполнен")

            # Получение текущего баланса группы
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Получаю баланс группы...")
            chat_balance = await db.get_chat_balancebalance(bot1 , chat_id)
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Сырой chat_balance={chat_balance!r}")

            try:
                chat_balance = int(float(chat_balance)) if chat_balance not in (None , "") else 0
            except Exception:
                chat_balance = 0

            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 chat_balance(int)={chat_balance}")
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 amount={amount}")

            if chat_balance < amount:
                print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Недостаточно средств на балансе группы")
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Недостаточно средств на балансе группы.</b>" , parse_mode="HTML")
                return

            # Получение создателя группы
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Получаю creator_id...")
            creator_id = await db.get_creator_id(chat_id)
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 creator_id={creator_id!r}")
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 user_id={user_id}")

            if creator_id is None:
                print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ creator_id не найден")
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Не удалось определить создателя группы.</b>" , parse_mode="HTML")
                return

            if int(user_id) != int(creator_id):
                print(
                    f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] ⛔ Пользователь не создатель: user_id={user_id}, creator_id={creator_id}")
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Только создатель группы может снимать куты с баланса.</b>" , parse_mode="HTML")
                return

            # Снимаем с баланса группы
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Уменьшаю баланс группы...")
            new_chat_balance = chat_balance - amount
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 new_chat_balance={new_chat_balance}")

            await db.update_chat_balance_minus(chat_id , amount)
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ✅ Баланс группы уменьшен")

            # Получаем баланс создателя
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Получаю баланс создателя...")
            creator_balance_tuple = await db.get_user_balance(creator_id)
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 creator_balance_tuple={creator_balance_tuple!r}")

            creator_balance = creator_balance_tuple [ 0 ] if isinstance(
                creator_balance_tuple , tuple) else creator_balance_tuple
            creator_balance = int(creator_balance or 0)

            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 creator_balance={creator_balance}")

            # Начисляем создателю
            new_creator_balance = creator_balance + amount
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 new_creator_balance={new_creator_balance}")

            await db.update_user_balance(creator_id , new_creator_balance)
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ✅ Баланс создателя обновлён")

            await db.cutehistory_plus(creator_id , amount , "снято с баланса группы")
            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] ✅ История начисления записана")

            amount_formatted = "{:,.0f}".format(amount).replace("," , ".")
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 amount_formatted={amount_formatted!r}")

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text=f"{amount_formatted} кут" , callback_data="noop" , style="default" ,
                    icon_custom_emoji_id="6028338546736107668") ] , [ InlineKeyboardButton(
                    text="Снято с баланса чата" , callback_data="noop" , style="default" ,
                    icon_custom_emoji_id="6028346797368283073") ] ])

            print("[СНЯТИЕ С БАЛАНСА ГРУППЫ] 🟩 Отправляю сообщение об успешном снятии...")
            sent_msg = await message.reply(
                "<tg-emoji emoji-id='5199790590279033017'>🏖</tg-emoji>" , parse_mode="HTML" , reply_markup=keyboard)
            print(
                f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] ✅ Сообщение отправлено, message_id={getattr(sent_msg , 'message_id' , None)}")
            return

        except Exception as e:
            print(f"[СНЯТИЕ С БАЛАНСА ГРУППЫ] ❌ Ошибка при обновлении баланса: {type(e).__name__}: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при снятии с баланса группы.</b>" , parse_mode="HTML")
            return

    text = " ".join((message.text or "").lower().strip().split())
    print(f"[БАЛАНС ЧАТА] 🟦 Получено сообщение: raw={message.text!r}")
    print(f"[БАЛАНС ЧАТА] 🟦 Нормализованный text={text!r}")
    print(
        f"[БАЛАНС ЧАТА] 🟦 chat_id={getattr(message.chat , 'id' , None)} | "
        f"user_id={getattr(message.from_user , 'id' , None)} | "
        f"chat_type={getattr(message.chat , 'type' , None)}")

    if text in [ "баланс чата" , "баланс группы" , "балик чата" , "балик группы" , "бг" , "бч" , "казна" ]:
        print("[БАЛАНС ЧАТА] ✅ Команда баланса группы распознана")

        if message.chat.type == "private":
            print("[БАЛАНС ЧАТА] ⛔ Команда вызвана в личке")
            await message.reply(
                "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> "
                "<b>Баланс группы работает только в публичных группах.</b>" , parse_mode="HTML")
            return

        chat_id_CheckpublickGroup = int(message.chat.id)
        user_id_CheckpublickGroup = int(message.from_user.id)

        print(f"[БАЛАНС ЧАТА] 🟨 Начинаем обработку")
        print(f"[БАЛАНС ЧАТА] 🟨 chat_id={chat_id_CheckpublickGroup}")
        print(f"[БАЛАНС ЧАТА] 🟨 user_id={user_id_CheckpublickGroup}")

        publicResult_CheckpublickGroup = await publicChecker_CheckpublickGroup.check_public_group_CheckpublickGroup(
            bot=bot1 , db=db , chat_id_CheckpublickGroup=chat_id_CheckpublickGroup)

        print(
            f"[БАЛАНС ЧАТА] 🟪 Результат проверки: "
            f"is_public={publicResult_CheckpublickGroup.is_public_CheckpublickGroup}, "
            f"username={publicResult_CheckpublickGroup.username_CheckpublickGroup!r}, "
            f"source={publicResult_CheckpublickGroup.source_CheckpublickGroup!r}, "
            f"reason={publicResult_CheckpublickGroup.reason_CheckpublickGroup!r}")

        if not publicResult_CheckpublickGroup.is_public_CheckpublickGroup:
            await message.reply(
                "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> "
                "<b>Баланс группы доступен в публичных чатах — у группы должен быть открытый @username.</b>" ,
                parse_mode="HTML")
            return

        try:
            print("[БАЛАНС ЧАТА] 🟩 Переходим к получению баланса")

            chat_id = int(message.chat.id)
            user_id = int(message.from_user.id)

            await db.ensure_group(
                bot1=bot1 , chat_id=chat_id , sync_func=add_or_update_group_info)
            print("[БАЛАНС ЧАТА] ✅ ensure_group выполнен")

            chat_balance = await db.get_chat_balancebalance(bot1 , chat_id)

            print(f"[БАЛАНС ЧАТА] 🟩 Сырой chat_balance={chat_balance!r}")

            chat_balance = float(chat_balance) if chat_balance not in (None , "") else 0.0
            total_balance = chat_balance

            print(f"[БАЛАНС ЧАТА] 🟩 chat_balance={chat_balance}")
            print(f"[БАЛАНС ЧАТА] 🟩 total_balance={total_balance}")

            chat_balance_formatted = "{:,.0f}".format(chat_balance).replace("," , ".")
            total_balance_formatted = "{:,.0f}".format(total_balance).replace("," , ".")

            from bot.funcs.group_balance_level import (
                build_main_keyboard,
                build_main_screen_html,
                ensure_society_snapshot,
                strip_tg_emoji,
            )
            atmo_report = await ensure_society_snapshot(chat_id, db=db)
            atmo = float(atmo_report.get("pct") or 0)
            keyboard = build_main_keyboard(
                chat_id=chat_id, chat_balance=chat_balance, atmosphere_pct=atmo,
            )
            screen = build_main_screen_html(
                chat_id=chat_id,
                chat_balance=chat_balance,
                atmosphere_pct=atmo,
                atmosphere_report=atmo_report,
            )
            try:
                sent_message = await message.reply(
                    screen, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                err = str(e)
                if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
                    sent_message = await message.reply(
                        strip_tg_emoji(screen), reply_markup=keyboard, parse_mode="HTML")
                else:
                    raise

            user_message_balance_chat [ user_id ] = sent_message.message_id
            print(f"[БАЛАНС ЧАТА] ✅ Сообщение отправлено, message_id={sent_message.message_id}")
            return

        except Exception as e:
            print(f"[БАЛАНС ЧАТА] ❌ Ошибка при получении баланса чата: {type(e).__name__}: {e}")

            aahsodhas = random.choice(
                [ "Ошибка при получении кутов" , "Куты исчезли в облаке" , "Не удалось подсчитать куты" ,
                    "Куты ушли в отпуск" , "Произошла ошибка с кутами" , "Невозможно найти куты" ,
                    "Куты сбежали в другую вселенную" , "Ошибка баланса, куты не пришли" ,
                    "Куты не найдены, опять обман" , "Секундочку, куты на перезагрузке" ,
                    "Куты не хотят быть посчитаны" , "Баланс кутов исчез, попробуйте снова" ,
                    "Попробуй снова, куты не в сети" , "Куты потерялись в процессе" , "Чат решил не давать куты" ,
                    "Ошибка с кутами, ничего страшного" , "Куты покинули чат" ,
                    "Произошла ошибка с кутами, кто-то виноват" , "Куты на паузе" , "Баланс кутов в неопределённости" ,
                    "Что-то пошло не так с кутами" , "Куты спрятались от системы" , "Ошибка вычислений с кутами" ,
                    "Куты на выходных, ждите" , "Произошла ошибка при подсчете кутов" ,
                    "Куты не найдены, похоже, исчезли" , "Куты исчезли, надо перезагрузить" ,
                    "Процесс с кутами заблокирован" , "Куты ушли на обед" ])

            await message.reply(
                f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>{aahsodhas}</b>" , parse_mode="HTML")
            return
@dp.callback_query(lambda callback_query: callback_query.data.startswith("group_balance_details"))
async def show_balance_details(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_balance_chat or user_message_balance_chat [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    data = callback_query.data.split(":")
    if len(data) == 2:
        _ , chat_balance_str = data

        chat_balance = float(chat_balance_str)
        chat_id = int(callback_query.message.chat.id)

        from bot.funcs.group_balance_level import (
            build_details_html,
            build_details_keyboard,
            ensure_society_snapshot,
            strip_tg_emoji,
        )

        atmo_report = await ensure_society_snapshot(chat_id, db=db)
        atmo = float(atmo_report.get("pct") or 0)
        text = build_details_html(
            chat_balance=chat_balance,
            chat_id=chat_id,
            atmosphere_pct=atmo,
            atmosphere_report=atmo_report,
        )
        keyboard = build_details_keyboard(chat_id=chat_id)
        try:
            await callback_query.message.edit_text(
                text, parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            err = str(e)
            if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
                await callback_query.message.edit_text(
                    strip_tg_emoji(text), parse_mode="HTML", reply_markup=keyboard)
            else:
                raise
        try:
            await callback_query.answer()
        except Exception:
            pass
    else:
        await callback_query.answer(
            "Не удалось открыть подробности. Вернитесь к балансу и попробуйте снова.",
            show_alert=True,
        )

@dp.callback_query(lambda c: c.data == "back_to_balance")
async def back_to_balance(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_balance_chat or user_message_balance_chat [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    chat_id = callback_query.message.chat.id
    chat_balance = await db.get_chat_balancebalance(bot1,chat_id)
    chat_balance = float(chat_balance) if chat_balance else 0.0

    from bot.funcs.group_balance_level import (
        build_main_keyboard,
        build_main_screen_html,
        ensure_society_snapshot,
        strip_tg_emoji,
    )
    atmo_report = await ensure_society_snapshot(int(chat_id), db=db)
    atmo = float(atmo_report.get("pct") or 0)
    keyboard = build_main_keyboard(
        chat_id=int(chat_id), chat_balance=chat_balance, atmosphere_pct=atmo,
    )
    screen = build_main_screen_html(
        chat_id=int(chat_id),
        chat_balance=chat_balance,
        atmosphere_pct=atmo,
        atmosphere_report=atmo_report,
    )
    try:
        await callback_query.message.edit_text(
            screen, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        err = str(e)
        if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
            await callback_query.message.edit_text(
                strip_tg_emoji(screen), reply_markup=keyboard, parse_mode="HTML")
        else:
            raise


@dp.callback_query(lambda c: c.data == "gbl_raise")
async def gbl_raise_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_balance_chat or user_message_balance_chat[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    chat_id = int(callback_query.message.chat.id)
    from bot.funcs.group_balance_level import (
        build_raise_keyboard, build_raise_screen_html, get_settings, get_chat_level,
        ensure_society_snapshot, next_level_price, strip_tg_emoji,
    )
    cfg = get_settings()
    if not cfg.get("enabled", True):
        await callback_query.answer(
            "Уровни баланса группы временно недоступны. Загляните чуть позже.",
            show_alert=True,
        )
        return
    if get_chat_level(chat_id) >= 5:
        await callback_query.answer(
            "Группа уже на максимальном уровне — спасибо!",
            show_alert=True,
        )
        return

    await ensure_society_snapshot(chat_id, db=db)
    badge_title = None
    nxt = next_level_price(chat_id, cfg)
    if nxt:
        try:
            from bot.funcs.achievements import get_official_by_code
            row = await get_official_by_code(db, f"gbl_level_{nxt[0]}")
            if row and row.get("title"):
                badge_title = str(row["title"])
        except Exception:
            badge_title = None
    text = build_raise_screen_html(chat_id=chat_id, cfg=cfg, badge_title=badge_title)
    kb = build_raise_keyboard(chat_id=chat_id, cfg=cfg)
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        if "DOCUMENT_INVALID" in str(e):
            await callback_query.message.edit_text(
                strip_tg_emoji(text), reply_markup=kb, parse_mode="HTML")
        else:
            raise
    await callback_query.answer()


@dp.callback_query(lambda c: c.data and str(c.data).startswith("gbl_pay:"))
async def gbl_pay_handler(callback_query: CallbackQuery):
    """Зелёная кнопка: правим сообщение → мост в ЛС с deep-link на оплату."""
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_balance_chat or user_message_balance_chat[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    parts = str(callback_query.data).split(":")
    if len(parts) != 4:
        await callback_query.answer(
            "Не удалось подготовить оплату. Откройте экран ещё раз.",
            show_alert=True,
        )
        return
    try:
        chat_id = int(parts[1])
        to_level = int(parts[2])
        price = int(parts[3])
    except ValueError:
        await callback_query.answer(
            "Не удалось подготовить оплату. Откройте экран ещё раз.",
            show_alert=True,
        )
        return

    from bot.funcs.group_balance_level import (
        get_settings,
        next_level_price,
        ensure_society_snapshot,
        build_pay_dm_bridge_html,
        build_pay_dm_bridge_keyboard,
        strip_tg_emoji,
    )
    cfg = get_settings()
    if not cfg.get("enabled", True):
        await callback_query.answer(
            "Уровни баланса группы временно недоступны. Загляните чуть позже.",
            show_alert=True,
        )
        return

    await ensure_society_snapshot(chat_id, db=db)
    nxt = next_level_price(chat_id, cfg)
    if not nxt or nxt[0] != to_level or int(nxt[1]) != int(price):
        await callback_query.answer(
            "Уровень уже обновился. Вернитесь к балансу и откройте экран снова.",
            show_alert=True,
        )
        return

    bot_username = None
    try:
        bot_username = await get_bot_username_by_token(TOKEN)
    except Exception:
        bot_username = None
    if not bot_username:
        try:
            me = await bot1.get_me()
            bot_username = me.username
        except Exception:
            bot_username = "CuteGamingBot"

    text = build_pay_dm_bridge_html(
        chat_id=chat_id, to_level=to_level, price=price, cfg=cfg,
    )
    kb = build_pay_dm_bridge_keyboard(
        bot_username=bot_username,
        chat_id=chat_id,
        to_level=to_level,
        price=price,
        cfg=cfg,
    )
    try:
        await callback_query.message.edit_text(
            text, reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        err = str(e)
        if "DOCUMENT_INVALID" in err or "can't parse" in err.lower():
            await callback_query.message.edit_text(
                strip_tg_emoji(text), reply_markup=kb, parse_mode="HTML",
            )
        else:
            print(f"[GBL] pay bridge edit error: {e!r}")
            await callback_query.answer(
                "Не удалось открыть оплату. Попробуйте ещё раз.",
                show_alert=True,
            )
            return
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "group_balance_overview")
async def group_balance_overview(callback_query: CallbackQuery):
    """Тап по кнопке баланса — короткий статус уровня."""
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_balance_chat or user_message_balance_chat[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    chat_id = int(callback_query.message.chat.id)
    from bot.funcs.group_balance_level import (
        get_chat_level, stars_label, recommended_play_bet, effective_stake_cap,
        get_settings, ensure_society_snapshot,
    )
    cfg = get_settings()
    level = get_chat_level(chat_id)
    try:
        bal = float(await db.get_chat_balancebalance(bot1, chat_id) or 0)
    except Exception:
        bal = 0.0
    atmo_report = await ensure_society_snapshot(chat_id, db=db)
    atmo = float(atmo_report.get("pct") or 0)
    rec = recommended_play_bet(bal, chat_id=chat_id, atmosphere_pct=atmo, cfg=cfg)
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmo, cfg=cfg)
    lim = "без лимита" if cap is None else f"до {cap}"
    await callback_query.answer(
        f"Баланс группы · {stars_label(level)}\n"
        f"Ставки {lim}"
        + (f" · +{atmo:g}%" if atmo > 0.05 else "")
        + f"\nРекомендуем ≈ {rec}",
        show_alert=True,
    )
