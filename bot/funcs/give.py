from aiogram import Bot, Dispatcher, types

import random
import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from aiogram.types import InputFile
from datetime import datetime
from aiogram import types
import html

from datetime import datetime

import asyncio



from aiogram.types import InputFile




from bot.config.config import *
from bot.design.buttons import *
from bot.db_create.db import *

from bot.games.games import Cube122, Bowling34, Basketball34, Slots1, Trade,dart122,foot1
from bot.funcs.func import *
from aiogram.types import Message
from datetime import datetime, timedelta
from bot.config.config import *
from bot.design.buttons import *
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import datetime
from main import *


async def send_wait_message(wait_time, message, remaining_amount):
    """Отправляет сообщение с временем ожидания и оставшейся суммой для перевода."""
    remaining_text = (
        f"\n<b>💸 Вы ещё можете отправить : <i>{remaining_amount}</i> кут</b>."
        if remaining_amount > 0
        else ""
    )

    time_text = ""  # По умолчанию строка с временем пустая

    if wait_time > 0:  # Проверяем, что время больше 0
        if wait_time < 60:
            seconds_word = get_declension(wait_time, "секунда", "секунды", "секунд")
            time_text = f"\n🔰 До обнуления лимита : <i>{wait_time}</i> {seconds_word}."

        elif wait_time < 3600:
            minutes, seconds = divmod(wait_time, 60)
            minutes_word = get_declension(minutes, "минута", "минуты", "минут")
            seconds_word = get_declension(seconds, "секунда", "секунды", "секунд")
            time_text = (
                f"\n🔰 До обнуления лимита : <i>{minutes}</i> {minutes_word} и <i>{seconds}</i> {seconds_word}."
            )

        else:
            hours, remainder = divmod(wait_time, 3600)
            minutes, _ = divmod(remainder, 60)
            hours_word = get_declension(hours, "час", "часа", "часов")
            minutes_word = get_declension(minutes, "минута", "минуты", "минут")
            time_text = (
                f"\n🔰 До обнуления лимита : <i>{hours}</i> {hours_word} и <i>{minutes}</i> {minutes_word}."
            )

    # Отправляем сообщение с/без строки времени ожидания в зависимости от значения wait_time
    await message.reply(
        f"💰 <b>Вы превысили лимит"
        f"{time_text}{remaining_text}</b>"
        f"<pre>🧸 Для повышения лимита используйте <i>'<code>🎮</code> Геймпад' который можно получить побеждая в многопользовательских играх</i></pre>",
        parse_mode="HTML"
    )
@dp.message()
async def give(message: Message):
    if message.text.lower().startswith("sypherдатьпредмет"):
        try:
            user_id = message.from_user.id

            if user_id != 6801702632:
                return
            parts = message.text.split()
            if len(parts) < 2 or not parts [ 1 ]:
                #await message.reply(
                    #"⚠️ <b>Неправильный формат команды. Используйте: sypherдатьпредмет (эмодзи предмета) (количество)</b>" ,
                    #parse_mode="HTML" , disable_web_page_preview=True)
                return

            print(f"🛠️ [DEBUG] Обработка команды 'sypherдатьпредмет'. ID пользователя: {user_id}")

            emoji = parts [ 1 ]  # Эмодзи предмета
            quantity = 1  # Количество по умолчанию

            # Если указано количество, обновляем значение quantity
            if len(parts) > 2 and parts [ 2 ].isdigit():
                quantity = int(parts [ 2 ])

            print(f"🛠️ [DEBUG] Эмодзи: {emoji}, Количество: {quantity}")

            # Получаем имя предмета по эмодзи
            item_name = await db.get_item_name_by_emoji(emoji)
            if not item_name:
                await message.reply(
                    "⚠️ <b>Предмет с указанным эмодзи не найден.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                print(f"🛠️ [DEBUG] Эмодзи {emoji} не найдено в базе данных.")
                return

            print(f"🛠️ [DEBUG] Найден предмет: {item_name}")

            # Добавляем предмет в инвентарь пользователя
            await db.set_items(user_id , item_name , quantity)

            await message.reply(
                f"✅ <b>Пользователю выдано : {quantity}шт | <code>{emoji}</code> {item_name}</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print(f"🛠️ [DEBUG] Успешно добавлено {quantity} x {item_name} ({emoji}) пользователю {user_id}.")

        except Exception as e:
            await message.reply(
                "❌ <b>Произошла ошибка при обработке команды.</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print(f"🛠️ [DEBUG] Ошибка: {e}")

    if message.text.lower().startswith("sypherзабратьпредмет"):
        try:
            user_id = message.from_user.id
            if user_id != 6801702632:
                return
            parts = message.text.split()
            if len(parts) < 2 or not parts [ 1 ]:
            #    await message.reply(
            #        "⚠️ <b>Неправильный формат команды. Используйте: sypherзабратьпредмет (эмодзи предмета) (количество)</b>" ,
            #        parse_mode="HTML" , disable_web_page_preview=True)
                return

            print(f"🛠️ [DEBUG] Обработка команды 'sypherзабратьпредмет'. ID пользователя: {user_id}")

            emoji = parts [ 1 ]  # Эмодзи предмета
            quantity = 1  # Количество по умолчанию

            # Если указано количество, обновляем значение quantity
            if len(parts) > 2 and parts [ 2 ].isdigit():
                quantity = int(parts [ 2 ])

            print(f"🛠️ [DEBUG] Эмодзи: {emoji}, Количество: {quantity}")

            # Получаем имя предмета по эмодзи
            item_name = await db.get_item_name_by_emoji(emoji)
            if not item_name:
                await message.reply(
                    "⚠️ <b>Предмет с указанным эмодзи не найден.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                print(f"🛠️ [DEBUG] Эмодзи {emoji} не найдено в базе данных.")
                return

            print(f"🛠️ [DEBUG] Найден предмет: {item_name}")

            # Удаляем предмет из инвентаря пользователя
            await db.delete_user_inventory12(user_id , item_name , quantity)

            await message.reply(
                f"✅ <b>У пользователя изъято {quantity}шт | <code>{emoji}</code> {item_name}</b>" ,
                parse_mode="HTML" , disable_web_page_preview=True)
            print(f"🛠️ [DEBUG] Успешно изъято {quantity} x {item_name} ({emoji}) у пользователя {user_id}.")

        except Exception as e:
            await message.reply(
                "❌ <b>Произошла ошибка при обработке команды.</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print(f"🛠️ [DEBUG] Ошибка: {e}")

    if message.text.lower().startswith("sypherдать"):
        # Действия, если сообщение начинается с "сайфердать"
        current_time = datetime.now()
        user_id = message.from_user.id

        if user_id != 6801702632:
            return

        randomnumberrandom = random.randint(1, 100)
        if randomnumberrandom > 70:
            await message.answer(f"💰")


        print(f"[DEBUG] Сообщение начинается с 'дать': {message.text}")

        # Разделяем текст команды на части
        parts = message.text.split(maxsplit=2)
        print(f"[DEBUG] Разделенные данные: {parts}")

        if len(parts) >= 2:
            # Проверяем, является ли вторая часть ссылкой или @username
            recipient_info = parts [ 1 ].strip()
            amount_str = ""
            comment = ""

            if not recipient_info.startswith('@') and not recipient_info.startswith(
                    'https://t.me/') and not recipient_info.isdigit():
                recipient_info = '@' + recipient_info

            # Теперь можно обрабатывать
            if (recipient_info.startswith('@') or recipient_info.startswith('https://t.me/') or (
                    recipient_info.isdigit() and len(recipient_info) == 10)):
                if len(parts) >= 3:
                    rest = parts [ 2 ].split(maxsplit=1)
                    amount_str = rest [ 0 ].strip()
                    comment = rest [ 1 ].strip() if len(rest) > 1 else ""
                else:
                    amount_str = ''
                    comment = ''
            else:
                # Если это не ссылка и не @username, ставка будет во втором элементе
                print(parts)
                if len(parts) >= 2:
                    amount_str = parts [ 1 ].strip()
                    comment = parts [ 2 ].strip() if len(parts) == 3 else ""
            if comment:
                comment = f"\n💭 <b>Комментарий : <i>\"{comment}\"</i></b>"

            # Проверяем, что сумма перевода является числом

            print(amount_str)
            try:
                amount = int(amount_str.replace("." , ""))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply(
                    '💭 <b>Пожалуйста, укажите сумму больше нуля.</b>' , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            # Получаем идентификатор отправителя
            sender_id = message.from_user.id


            if message.reply_to_message:
                # Вариант 1: "дать (ставка) (комментарий необязательно)" в ответ на сообщение другого пользователя
                receiver_id = message.reply_to_message.from_user.id

                recerved_id111 = message.reply_to_message.from_user.id
                receiver_name = await db.get_firstname_by_user_id(recerved_id111)

                # Проверяем баланс отправителя
                sender_balance = await db.get_user_balance(sender_id)
                if sender_balance is None:
                    await message.reply(
                        '🛠 <b>Не удалось получить баланс отправителя.</b>' , parse_mode="HTML" ,
                        disable_web_page_preview=True)
                    return

                #if sender_balance < amount:
                    #await message.reply(
                        #'💰 <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" ,
                        #disable_web_page_preview=True)
                    #return

                # Проверяем, что получатель не является ботом
                if receiver_id == 7683193125:  # Замените 'bot_id' на фактический идентификатор вашего бота
                    await message.reply(
                        '😏 <b>Я не беру взятки</b>' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                sumgiveuser = await db.get_daily_give_sum(user_id)  # Сумма переводов за сегодня
                give_limit = await db.get_user_give_limit(user_id)
                if give_limit is None:
                    print("Лимит перевода не установлен.")
                    return  # Прекращаем выполнение, если лимит отсутствует

                # Получаем сумму отправлений за текущий день
                daily_sum = await db.get_daily_give_sum(user_id)
                current_time = datetime.now()

                # Проверка превышения лимита
                #if daily_sum + amount > give_limit:
                    #remaining_amount = give_limit - daily_sum
                    #if remaining_amount < 0:
                        #remaining_amount = 0

                    #print(f"Ошибка: лимит превышен. Вы можете отправить ещё максимум {remaining_amount}.")

                    # Проверка времени ожидания
                    #last_open_time , data_over = await db.get_give_times(user_id)
                    #if last_open_time and data_over:
                        #last_open_dt = datetime.strptime(last_open_time , "%Y-%m-%d %H:%M:%S")
                        #data_over_dt = datetime.strptime(data_over , "%Y-%m-%d %H:%M:%S")

                        #if current_time < data_over_dt:
                            #wait_time = int((data_over_dt - current_time).total_seconds())
                            #await send_wait_message(wait_time , message , remaining_amount)
                            #return  # Прекращаем выполнение, если срок ещё не истёк

                    # Если время истекло, но лимит всё ещё превышен
                    #await send_wait_message(0 , message , remaining_amount)
                    #return

                # Проверяем, есть ли пользователь в таблице givetime
                user_in_givetime = await db.check_user_in_givetime(user_id)

                if user_in_givetime:
                    user_daily_sum = await db.get_daily_give_sum(user_id)

                    if user_daily_sum < give_limit:
                        # Пользователь не использовал весь лимит, удаляем его из таблицы givetime
                        await db.remove_user_give(
                            user_id)  # Обновляем информацию о времени, если необходимо  # db.update_give_time(user_id, current_time)  # Не забудьте реализовать этот метод

                # Логика для выполнения перевода
                # Обновляем баланс отправителя и получателя
                receiver_balance = await db.get_user_balance(receiver_id)
                if receiver_balance is None:
                    await message.reply(
                        '🛠 Не удалось найти получателя..' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                # Проверяем, что отправитель не переводит деньги самому себе


                # Обновляем баланс
                #await db.update_user_balance(sender_id , sender_balance - amount)

                await db.update_user_balance(receiver_id , receiver_balance + amount)

                await db.cutehistory_plus(receiver_id , amount , "sypherдать" )
                await db.add_transaction(sender_id , receiver_id , amount)

                formatted_amount = '{:,.0f}'.format(amount).replace(',' , '.')
                sender_name = await db.get_firstname_by_user_id(sender_id)
                user_username = await db.get_username_by_id(sender_id)
                sender_username = await db.get_username_by_id(receiver_id)
                chat_id = message.chat.id
                chat_name = message.chat.title or "Личный чат"  # Название группы или чат
                await db.add_give_limit(
                    sender_id , sender_name , user_username , amount , chat_id , chat_name , time_to_remove_give)
                name_link = await create_user_link(receiver_id , receiver_name , sender_username)
                user_name = await db.get_firstname_by_user_id(user_id)

                sumgiveuser1 = await db.get_daily_give_sum(user_id)  # Сумма переводов за сегодня
                give_limit1 = await db.get_user_give_limit(user_id)  # Лимит перевода пользователя

                if sumgiveuser1 >= give_limit1:
                    last_open_time , data_over = await db.get_give_times(user_id)

                    if last_open_time is None or data_over is None:
                        # Если данных нет, создаем запись
                        last_open_time = get_current_time_formatted()
                        data_open = current_time + timedelta(seconds=time_to_remove_give)

                        # Вызов метода для добавления записи
                        await db.add_give_time(
                            chat_id , chat_name , user_id , user_name , user_username , last_open_time ,
                            data_open.strftime("%Y-%m-%d %H:%M:%S")  # Форматируем дату в строку
                        )
                    else:
                        print(f"У пользователя {user_id} уже есть активная запись до {data_over}.")
                emousdaddsq = f"<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>"
                emousdaddsq1 = f"<tg-emoji emoji-id='5438614231048025408'>🎁</tg-emoji>"
                emousdadds2q = f"<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji>"
                await message.reply(
                    f'{emousdaddsq} <b>{name_link} было переведено {formatted_amount} кут</b> {comment}' ,
                    parse_mode="HTML" , disable_web_page_preview=True)
            else:
                parts1 = message.text.lower().split()

                try:  # Разделяем текст сообщения на части
                    recipient = parts1 [ 1 ]  # Пытаемся получить получателя (второй элемент)
                    amount_str1 = parts1 [ 2 ]  # Пытаемся получить сумму (третий элемент)
                except IndexError:
                    # Если список слишком короткий, сообщаем о проблеме
                    return  # Завершаем выполнение, если аргументы некорректны

                # Проверяем, найден ли получатель
                if not recipient:
                    return  # Завершаем выполнение, если получатель не указан

                try:
                    amount1 = int(amount_str1.replace("." , ""))  # Преобразуем сумму в число
                except ValueError:
                    # Если сумма не число, игнорируем или отправляем сообщение
                    return
                user_id_found = False

                if recipient_info.startswith('@'):
                    receiver_username = recipient_info [ 1: ]  # Удаляем символ @ из юзернейма
                elif recipient_info.startswith('https://t.me/'):
                    receiver_username = recipient_info [ 13: ]  # Извлекаем юзернейм из ссылки
                elif recipient_info.isdigit():
                    receiver_id = int(recipient_info)  # Прямо присваиваем receiver_id
                    user_id_found = True  # Устанавливаем флаг, так как идентификатор найден
                else:
                    try:
                        receiver_id = int(recipient_info)  # Пытаемся интерпретировать как идентификатор
                        user_id_found = True  # Устанавливаем флаг, так как идентификатор найден
                    except ValueError:
                        await message.reply(
                            '⚠️ Неверный формат идентификатора пользователя. Пожалуйста, укажите корректный юзернейм, ссылку на профиль или ID.' ,
                            parse_mode="HTML" , disable_web_page_preview=True)
                        return

                # Если был указан receiver_id, пытаемся получить данные пользователя
                if user_id_found:
                    try:
                        receiver_data = await db.get_user_by_idgive(receiver_id)
                        receiver_username = receiver_data [ 1 ] if receiver_data else "Неизвестный пользователь"
                    except KeyError:
                        receiver_username = "Неизвестный пользователь"
                else:
                    # Если идентификатор не найден, пытаемся получить его по юзернейму
                    receiver_id = await db.get_user_id_by_username(receiver_username)
                # Проверяем баланс отправителя

                comment2 = " ".join(parts1 [ 3: ]) if len(parts1) > 3 else None

                if comment2:
                    comment1 = f"\n💭 <b>Комментарий : <i>\"{comment2}\"</i></b>"
                else:
                    comment1 = ""

                sender_balance = await db.get_user_balance(sender_id)
                if sender_balance is None:
                    await message.reply(
                        '🛠 Не удалось получить баланс отправителя.' , parse_mode="HTML" ,
                        disable_web_page_preview=True)
                    return

                #if sender_balance < amount1:
                    #await message.reply(
                        #'💰 <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" ,
                        #disable_web_page_preview=True)
                    #return

                # Получаем баланс получателя

                if receiver_id is None:
                    await message.reply(
                        '❕ Не удалось найти получателя...' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                receiver_balance = await db.get_user_balance(receiver_id)
                if receiver_balance is None:
                    await message.reply(
                        '❕ Не удалось найти получателя....' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                # Проверяем, что отправитель не переводит деньги самому себе


                # Обновляем баланс отправителя и получателя
                #await db.update_user_balance(sender_id , sender_balance - amount1)
                await db.update_user_balance(receiver_id , receiver_balance + amount1)

                await db.cutehistory_plus(receiver_id , amount1 , "sypherдать" )
                await db.add_transaction(sender_id , receiver_id , amount1)
                first = await db.get_firstname_by_user_id(receiver_id)

                formatted_amount = '{:,.0f}'.format(amount1).replace(',' , '.')
                sender_name = await db.get_firstname_by_user_id(sender_id)
                user_username = await db.get_username_by_id(sender_id)

                chat_id = message.chat.id
                chat_name = message.chat.title or "Личный чат"  # Название группы или чат
                sender_username = await db.get_username_by_id(receiver_id)
                receiver_name = await db.get_firstname_by_user_id(receiver_id)
                await db.add_give_limit(
                    sender_id , sender_name , user_username , amount1 , chat_id , chat_name , time_to_remove_give)
                name_link = await create_user_link(receiver_id , receiver_name , sender_username)
                user_name = await db.get_firstname_by_user_id(user_id)

                sumgiveuser1 = await db.get_daily_give_sum(sender_id)
                give_limit1 = await db.get_user_give_limit(sender_id)

                if sumgiveuser1 >= give_limit1:
                    last_open_time , data_over = await db.get_give_times(sender_id)

                    if last_open_time is None or data_over is None:
                        last_open_time = get_current_time_formatted()
                        data_open = current_time + timedelta(seconds=time_to_remove_give)

                        await db.add_give_time(
                            chat_id , chat_name , sender_id , user_name , user_username , last_open_time ,
                            data_open.strftime("%Y-%m-%d %H:%M:%S"))

                    else:
                        print(f"У пользователя {sender_id} уже есть активная запись до {data_over}.")
                sdjdidasod = f"<tg-emoji emoji-id='5292024162557129071'>💰</tg-emoji>"
                await message.reply(
                    f'{sdjdidasod} <b>{name_link} было переведено {formatted_amount} кут</b> {comment1}' ,
                    parse_mode="HTML" , disable_web_page_preview=True)

        else:
            await message.reply(
                '⚠️ Неверный формат для перевода кут' , parse_mode="HTML" , disable_web_page_preview=True)


    if message.text.lower().startswith("sypherснять" ):  # Проверяем, начинается ли сообщение с "дать"

        current_time = datetime.now()
        user_id = message.from_user.id
        if user_id != 6801702632:
            return
        randomnumberrandom = random.randint(1, 100)
        if randomnumberrandom > 70:
            await message.answer(f"💰")


        print(f"[DEBUG] Сообщение начинается с 'дать': {message.text}")

        # Разделяем текст команды на части
        parts = message.text.split(maxsplit=2)
        print(f"[DEBUG] Разделенные данные: {parts}")

        if len(parts) >= 2:
            # Проверяем, является ли вторая часть ссылкой или @username
            recipient_info = parts [ 1 ].strip()
            amount_str = ""
            comment = ""

            if not recipient_info.startswith('@') and not recipient_info.startswith(
                    'https://t.me/') and not recipient_info.isdigit():
                recipient_info = '@' + recipient_info

            # Теперь можно обрабатывать
            if (recipient_info.startswith('@') or recipient_info.startswith('https://t.me/') or (
                    recipient_info.isdigit() and len(recipient_info) == 10)):
                if len(parts) >= 3:
                    rest = parts [ 2 ].split(maxsplit=1)
                    amount_str = rest [ 0 ].strip()
                    comment = rest [ 1 ].strip() if len(rest) > 1 else ""
                else:
                    amount_str = ''
                    comment = ''
            else:
                # Если это не ссылка и не @username, ставка будет во втором элементе
                print(parts)
                if len(parts) >= 2:
                    amount_str = parts [ 1 ].strip()
                    comment = parts [ 2 ].strip() if len(parts) == 3 else ""
            if comment:
                comment = f"\n💭 <b>Комментарий : <i>\"{comment}\"</i></b>"

            # Проверяем, что сумма перевода является числом

            print(amount_str)
            try:
                amount = int(amount_str.replace("." , ""))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply(
                    '💭 <b>Пожалуйста, укажите сумму больше нуля.</b>' , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            # Получаем идентификатор отправителя
            sender_id = message.from_user.id


            if message.reply_to_message:
                # Вариант 1: "дать (ставка) (комментарий необязательно)" в ответ на сообщение другого пользователя
                receiver_id = message.reply_to_message.from_user.id

                recerved_id111 = message.reply_to_message.from_user.id
                receiver_name = await db.get_firstname_by_user_id(recerved_id111)

                # Проверяем баланс отправителя
                sender_balance = await db.get_user_balance(recerved_id111)
                if sender_balance is None:
                    await message.reply(
                        '🛠 <b>Не удалось получить баланс отправителя.</b>' , parse_mode="HTML" ,
                        disable_web_page_preview=True)
                    return

                #if sender_balance < amount:
                    #await message.reply(
                        #'💰 <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" ,
                        #disable_web_page_preview=True)
                    #return

                # Проверяем, что получатель не является ботом
                if receiver_id == 7683193125:  # Замените 'bot_id' на фактический идентификатор вашего бота
                    await message.reply(
                        '😏 <b>Я не беру взятки</b>' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                sumgiveuser = await db.get_daily_give_sum(user_id)  # Сумма переводов за сегодня
                give_limit = await db.get_user_give_limit(user_id)
                if give_limit is None:
                    print("Лимит перевода не установлен.")
                    return  # Прекращаем выполнение, если лимит отсутствует



                # Проверяем, есть ли пользователь в таблице givetime
                user_in_givetime = await db.check_user_in_givetime(user_id)

                if user_in_givetime:
                    user_daily_sum = await db.get_daily_give_sum(user_id)

                    if user_daily_sum < give_limit:
                        # Пользователь не использовал весь лимит, удаляем его из таблицы givetime
                        await db.remove_user_give(
                            user_id)  # Обновляем информацию о времени, если необходимо  # db.update_give_time(user_id, current_time)  # Не забудьте реализовать этот метод

                # Логика для выполнения перевода
                # Обновляем баланс отправителя и получателя
                receiver_balance = await db.get_user_balance(receiver_id)
                if receiver_balance is None:
                    await message.reply(
                        '🛠 Не удалось найти получателя.....' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                # Проверяем, что отправитель не переводит деньги самому себе


                # Обновляем баланс
                await db.update_user_balance(receiver_id , sender_balance - amount)

                await db.cutehistory_minus(receiver_id , amount , "sypherснять" )
                #await db.update_user_balance(receiver_id , receiver_balance + amount)
                await db.add_transaction(sender_id , receiver_id , amount)

                formatted_amount = '{:,.0f}'.format(amount).replace(',' , '.')
                sender_name = await db.get_firstname_by_user_id(sender_id)
                user_username = await db.get_username_by_id(sender_id)
                sender_username = await db.get_username_by_id(receiver_id)
                chat_id = message.chat.id
                chat_name = message.chat.title or "Личный чат"  # Название группы или чат
                await db.add_give_limit(
                    sender_id , sender_name , user_username , amount , chat_id , chat_name , time_to_remove_give)
                name_link = await create_user_link(receiver_id , receiver_name , sender_username)
                user_name = await db.get_firstname_by_user_id(user_id)

                sumgiveuser1 = await db.get_daily_give_sum(user_id)  # Сумма переводов за сегодня
                give_limit1 = await db.get_user_give_limit(user_id)  # Лимит перевода пользователя

                if sumgiveuser1 >= give_limit1:
                    last_open_time , data_over = await db.get_give_times(user_id)

                    if last_open_time is None or data_over is None:
                        # Если данных нет, создаем запись
                        last_open_time = get_current_time_formatted()
                        data_open = current_time + timedelta(seconds=time_to_remove_give)

                        # Вызов метода для добавления записи
                        await db.add_give_time(
                            chat_id , chat_name , user_id , user_name , user_username , last_open_time ,
                            data_open.strftime("%Y-%m-%d %H:%M:%S")  # Форматируем дату в строку
                        )
                    else:
                        print(f"У пользователя {user_id} уже есть активная запись до {data_over}.")

                await message.reply(
                    f'💰 <b>{name_link} было снято с баланса {formatted_amount} кут</b> {comment}' ,
                    parse_mode="HTML" , disable_web_page_preview=True)
            else:
                parts1 = message.text.lower().split()

                try:  # Разделяем текст сообщения на части
                    recipient = parts1 [ 1 ]  # Пытаемся получить получателя (второй элемент)
                    amount_str1 = parts1 [ 2 ]  # Пытаемся получить сумму (третий элемент)
                except IndexError:
                    # Если список слишком короткий, сообщаем о проблеме
                    return  # Завершаем выполнение, если аргументы некорректны

                # Проверяем, найден ли получатель
                if not recipient:
                    return  # Завершаем выполнение, если получатель не указан

                try:
                    amount1 = int(amount_str1.replace("." , ""))  # Преобразуем сумму в число
                except ValueError:
                    # Если сумма не число, игнорируем или отправляем сообщение
                    return
                user_id_found = False

                if recipient_info.startswith('@'):
                    receiver_username = recipient_info [ 1: ]  # Удаляем символ @ из юзернейма
                elif recipient_info.startswith('https://t.me/'):
                    receiver_username = recipient_info [ 13: ]  # Извлекаем юзернейм из ссылки
                elif recipient_info.isdigit():
                    receiver_id = int(recipient_info)  # Прямо присваиваем receiver_id
                    user_id_found = True  # Устанавливаем флаг, так как идентификатор найден
                else:
                    try:
                        receiver_id = int(recipient_info)  # Пытаемся интерпретировать как идентификатор
                        user_id_found = True  # Устанавливаем флаг, так как идентификатор найден
                    except ValueError:
                        await message.reply(
                            '⚠️ Неверный формат идентификатора пользователя. Пожалуйста, укажите корректный юзернейм, ссылку на профиль или ID.' ,
                            parse_mode="HTML" , disable_web_page_preview=True)
                        return

                # Если был указан receiver_id, пытаемся получить данные пользователя
                if user_id_found:
                    try:
                        receiver_data = await db.get_user_by_idgive(receiver_id)
                        receiver_username = receiver_data [ 1 ] if receiver_data else "Неизвестный пользователь"
                    except KeyError:
                        receiver_username = "Неизвестный пользователь"
                else:
                    # Если идентификатор не найден, пытаемся получить его по юзернейму
                    receiver_id = await db.get_user_id_by_username(receiver_username)
                # Проверяем баланс отправителя

                comment2 = " ".join(parts1 [ 3: ]) if len(parts1) > 3 else None

                if comment2:
                    comment1 = f"\n💭 <b>Комментарий : <i>\"{comment2}\"</i></b>"
                else:
                    comment1 = ""

                sender_balance = await db.get_user_balance(receiver_id)
                if sender_balance is None:
                    await message.reply(
                        '🛠 Не удалось получить баланс отправителя.' , parse_mode="HTML" ,
                        disable_web_page_preview=True)
                    return

                #if sender_balance < amount1:
                    #await message.reply(
                        #'💰 <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" ,
                        #disable_web_page_preview=True)
                    #return

                # Получаем баланс получателя

                #if receiver_id is None:
                    #await message.reply(
                    #    '❕ Не удалось найти получателя.' , parse_mode="HTML" , disable_web_page_preview=True)
                    #return

                receiver_balance = await db.get_user_balance(receiver_id)
                if receiver_balance is None:
                    await message.reply(
                        '❕ Не удалось найти получателя......' , parse_mode="HTML" , disable_web_page_preview=True)
                    return

                # Проверяем, что отправитель не переводит деньги самому себе



                # Обновляем баланс отправителя и получателя
                await db.update_user_balance(receiver_id , sender_balance - amount1)

                await db.cutehistory_minus(receiver_id , amount1 , "sypherснять" )
                await db.add_transaction(sender_id , receiver_id , amount1)
                first = await db.get_firstname_by_user_id(receiver_id)

                formatted_amount = '{:,.0f}'.format(amount1).replace(',' , '.')
                sender_name = await db.get_firstname_by_user_id(sender_id)
                user_username = await db.get_username_by_id(sender_id)
                sender_username = await db.get_username_by_id(receiver_id)
                chat_id = message.chat.id
                chat_name = message.chat.title or "Личный чат"  # Название группы или чат
                receiver_name = await db.get_firstname_by_user_id(receiver_id)
                await db.add_give_limit(
                    sender_id , sender_name , user_username , amount1 , chat_id , chat_name , time_to_remove_give)
                name_link = await create_user_link(receiver_id , receiver_name , sender_username)
                user_name = await db.get_firstname_by_user_id(user_id)

                sumgiveuser1 = await db.get_daily_give_sum(sender_id)
                give_limit1 = await db.get_user_give_limit(sender_id)

                if sumgiveuser1 >= give_limit1:
                    last_open_time , data_over = await db.get_give_times(sender_id)

                    if last_open_time is None or data_over is None:
                        last_open_time = get_current_time_formatted()
                        data_open = current_time + timedelta(seconds=time_to_remove_give)

                        await db.add_give_time(
                            chat_id , chat_name , sender_id , user_name , user_username , last_open_time ,
                            data_open.strftime("%Y-%m-%d %H:%M:%S"))

                    else:
                        print(f"У пользователя {sender_id} уже есть активная запись до {data_over}.")

                await message.reply(
                    f'💰 <b>{name_link} было снято с баланса {formatted_amount} кут</b> {comment1}' ,
                    parse_mode="HTML" , disable_web_page_preview=True)

        else:
            await message.reply(
                '⚠️ Неверный формат для перевода кут' , parse_mode="HTML" , disable_web_page_preview=True)

    # =========================================================
    # GIVE / TRANSFER HELPERS
    # =========================================================

    BOT_GIVE_BLOCK_ID = 7683193125  # ID самого бота, которому нельзя переводить

    def _escape_html(text: Any) -> str:
        return html.escape(str(text or ""))

    def _fmt_int(n: int) -> str:
        return f"{int(n):,}".replace("," , ".")

    def _normalize_spaces(text: str) -> str:
        return re.sub(r"\s+" , " " , str(text or "")).strip()

    def _is_amount_token(token: str) -> bool:
        """
        Поддержка:
        1000
        1.000
        1,000
        10_000
        """
        token = str(token or "").strip()
        if not token:
            return False
        cleaned = token.replace("." , "").replace("," , "").replace("_" , "").replace(" " , "")
        return cleaned.isdigit()

    def _parse_amount_token(token: str) -> Optional [ int ]:
        token = str(token or "").strip()
        if not token:
            return None

        cleaned = token.replace("." , "").replace("," , "").replace("_" , "").replace(" " , "")
        if not cleaned.isdigit():
            return None

        try:
            amount = int(cleaned)
            if amount <= 0:
                return None
            return amount
        except Exception:
            return None

    def _extract_username_from_link(value: str) -> Optional [ str ]:
        """
        Поддержка:
        - https://t.me/username
        - http://t.me/username
        - t.me/username
        - https://telegram.me/username
        """
        value = str(value or "").strip()

        patterns = [ r"^(?:https?://)?t\.me/([A-Za-z0-9_]{4,})/?$" ,
            r"^(?:https?://)?telegram\.me/([A-Za-z0-9_]{4,})/?$" , ]

        for pattern in patterns:
            m = re.match(pattern , value , flags=re.IGNORECASE)
            if m:
                return m.group(1)

        return None

    def _extract_user_id_from_tg_link(value: str) -> Optional [ int ]:
        """
        Поддержка:
        tg://user?id=123456789
        """
        value = str(value or "").strip()
        m = re.match(r"^tg://user\?id=(\d{5,20})$" , value , flags=re.IGNORECASE)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _looks_like_username(value: str) -> bool:
        """
        Поддержка:
        @username
        username
        """
        value = str(value or "").strip()

        if value.startswith("@"):
            value = value [ 1: ]

        return bool(re.fullmatch(r"[A-Za-z0-9_]{4,32}" , value))

    def _is_possible_user_id(value: str) -> bool:
        value = str(value or "").strip()
        return value.isdigit() and 5 <= len(value) <= 20

    def _parse_recipient_token(token: str) -> Optional [ Dict [ str , Any ] ]:
        """
        Возвращает:
        {
            "kind": "username" | "id",
            "username": "name",
            "user_id": 123
        }
        """
        token = str(token or "").strip()
        if not token:
            return None

        tg_id = _extract_user_id_from_tg_link(token)
        if tg_id is not None:
            return {"kind": "id" , "user_id": tg_id}

        username_from_link = _extract_username_from_link(token)
        if username_from_link:
            return {"kind": "username" , "username": username_from_link}

        if token.startswith("@") and _looks_like_username(token):
            return {"kind": "username" , "username": token [ 1: ]}

        if _looks_like_username(token) and not _is_amount_token(token):
            return {"kind": "username" , "username": token}

        if _is_possible_user_id(token):
            try:
                return {"kind": "id" , "user_id": int(token)}
            except Exception:
                return None

        return None

    def _get_random_give_emoji() -> str:
        """
        Рандомное emoji для сообщения о переводе.
        """
        give_emojis = [ "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>" ,
            "<tg-emoji emoji-id='5438614231048025408'>🎁</tg-emoji>" ,
            "<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji>" , ]
        return random.choice(give_emojis)

    def _parse_give_command_text(text: str , * , is_reply: bool = False) -> Dict [ str , Any ]:
        """
        Поддерживаемые варианты:
        1) дать @username 1000 комментарий
        2) дать 1000 @username комментарий
        3) дать https://t.me/username 1000 комментарий
        4) дать 123456789 1000 комментарий
        5) reply: дать 1000 комментарий
        6) reply: дать комментарий 1000
        """

        raw_text = _normalize_spaces(text)
        result = {"ok": False , "recipient": None , "amount": None , "comment": "" , "error": "" , }

        if not raw_text:
            result [ "error" ] = "Пустой текст команды."
            return result

        parts = raw_text.split()
        if not parts:
            result [ "error" ] = "Пустой текст команды."
            return result

        command = parts [ 0 ].lower().strip()
        if command != "дать":
            result [ "error" ] = "Это не команда 'дать'."
            return result

        tail = parts [ 1: ]
        if not tail:
            result [ "error" ] = "Не указаны аргументы команды."
            return result

        if raw_text.lower().strip() == "дать автограф":
            result [ "error" ] = "ignore_autograph"
            return result

        # -----------------------------------------------------
        # REPLY MODE
        # -----------------------------------------------------
        if is_reply:
            amount_idx = None
            amount_val = None

            for i , token in enumerate(tail):
                parsed_amount = _parse_amount_token(token)
                if parsed_amount is not None:
                    amount_idx = i
                    amount_val = parsed_amount
                    break

            if amount_idx is None or amount_val is None:
                result [ "error" ] = "Не удалось найти сумму перевода."
                return result

            comment_tokens = tail [ :amount_idx ] + tail [ amount_idx + 1: ]
            comment = " ".join(comment_tokens).strip()

            result [ "ok" ] = True
            result [ "recipient" ] = None
            result [ "amount" ] = amount_val
            result [ "comment" ] = comment
            return result

        # -----------------------------------------------------
        # DIRECT MODE
        # -----------------------------------------------------
        recipient_idx = None
        recipient_data = None

        amount_idx = None
        amount_val = None

        for i , token in enumerate(tail):
            if recipient_data is None:
                maybe_recipient = _parse_recipient_token(token)
                if maybe_recipient is not None:
                    recipient_idx = i
                    recipient_data = maybe_recipient
                    continue

            if amount_val is None:
                maybe_amount = _parse_amount_token(token)
                if maybe_amount is not None:
                    amount_idx = i
                    amount_val = maybe_amount
                    continue

        if recipient_data is None:
            result [ "error" ] = "Не удалось найти получателя."
            return result

        if amount_val is None:
            result [ "error" ] = "Не удалось найти сумму перевода."
            return result

        used_indexes = {recipient_idx , amount_idx}
        comment_tokens = [ token for idx , token in enumerate(tail) if idx not in used_indexes ]
        comment = " ".join(comment_tokens).strip()

        result [ "ok" ] = True
        result [ "recipient" ] = recipient_data
        result [ "amount" ] = amount_val
        result [ "comment" ] = comment
        return result

    async def _resolve_receiver_from_recipient_info(recipient_info: Dict [ str , Any ] , db) -> Tuple [
        Optional [ int ] , Optional [ str ] ]:
        """
        Возвращает:
        receiver_id, receiver_username
        """
        if not recipient_info:
            return None , None

        kind = recipient_info.get("kind")

        if kind == "id":
            receiver_id = int(recipient_info [ "user_id" ])
            receiver_username = None

            try:
                receiver_data = await db.get_user_by_idgive(receiver_id)
                if receiver_data:
                    try:
                        receiver_username = receiver_data [ 1 ]
                    except Exception:
                        receiver_username = None
            except Exception as e:
                print(f"[GIVE][RESOLVE][ID][ERROR] {e}")

            return receiver_id , receiver_username

        if kind == "username":
            receiver_username = str(recipient_info [ "username" ]).strip().lstrip("@")
            if not receiver_username:
                return None , None

            receiver_id = await db.get_user_id_by_username(receiver_username)
            return receiver_id , receiver_username

        return None , None

    async def _check_and_apply_give_limit(* , sender_id: int , amount: int , message , db ,
            time_to_remove_give: int) -> bool:
        """
        True  -> можно продолжать
        False -> уже отправлено сообщение пользователю
        """
        give_limit = await db.get_user_give_limit(sender_id)
        if give_limit is None:
            await message.reply(
                '<tg-emoji emoji-id="5314346928660554905">⚠️</tg-emoji> <b>Лимит перевода не установлен.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return False

        daily_sum = await db.get_daily_give_sum(sender_id)
        current_time = datetime.now()

        if daily_sum + amount > give_limit:
            remaining_amount = give_limit - daily_sum
            if remaining_amount < 0:
                remaining_amount = 0

            last_open_time , data_over = await db.get_give_times(sender_id)
            if last_open_time and data_over:
                try:
                    data_over_dt = datetime.strptime(data_over , "%Y-%m-%d %H:%M:%S")
                    if current_time < data_over_dt:
                        wait_time = int((data_over_dt - current_time).total_seconds())
                        await send_wait_message(wait_time , message , remaining_amount)
                        return False
                except Exception as e:
                    print(f"[GIVE][LIMIT][PARSE_TIME][ERROR] {e}")

            await send_wait_message(0 , message , remaining_amount)
            return False

        try:
            user_in_givetime = await db.check_user_in_givetime(sender_id)
            if user_in_givetime:
                user_daily_sum = await db.get_daily_give_sum(sender_id)
                if user_daily_sum < give_limit:
                    await db.remove_user_give(sender_id)
        except Exception as e:
            print(f"[GIVE][LIMIT][CLEANUP][ERROR] {e}")

        return True

    async def _finalize_give_limit_if_needed(* , sender_id: int , sender_name: str , sender_username: Optional [ str ] ,
            amount: int , chat_id: int , chat_name: str , user_name_for_givetime: str , current_time: datetime , db ,
            time_to_remove_give: int) -> None:
        await db.add_give_limit(
            sender_id , sender_name , sender_username , amount , chat_id , chat_name , time_to_remove_give)

        sumgiveuser1 = await db.get_daily_give_sum(sender_id)
        give_limit1 = await db.get_user_give_limit(sender_id)

        if give_limit1 is None:
            return

        if sumgiveuser1 >= give_limit1:
            last_open_time , data_over = await db.get_give_times(sender_id)

            if last_open_time is None or data_over is None:
                last_open_time = get_current_time_formatted()
                data_open = current_time + timedelta(seconds=time_to_remove_give)

                await db.add_give_time(
                    chat_id , chat_name , sender_id , user_name_for_givetime , sender_username , last_open_time ,
                    data_open.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                print(f"[GIVE][LIMIT] У пользователя {sender_id} уже есть активная запись до {data_over}.")

    async def _process_give_transfer(* , message , sender_id: int , receiver_id: int ,
            receiver_username: Optional [ str ] , amount: int , comment: str , db , time_to_remove_give: int):
        if sender_id == receiver_id:
            await message.reply(
                '<tg-emoji emoji-id="5467519850576354798">❕</tg-emoji> <b>Вы не можете передать деньги самому себе.</b>' , parse_mode="HTML" ,
                disable_web_page_preview=True)
            return

        if receiver_id == BOT_GIVE_BLOCK_ID:
            await message.reply(
                '<tg-emoji emoji-id="5474493399996308572">😏</tg-emoji> <b>Я не беру взятки</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        sender_balance = await db.get_user_balance(sender_id)
        if sender_balance is None:
            await message.reply(
                '<tg-emoji emoji-id="6021401276904905698">🛠</tg-emoji> <b>Не удалось получить баланс отправителя.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        if sender_balance < amount:
            await message.reply(
                '<tg-emoji emoji-id="5375312095346704820">💰</tg-emoji> <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        receiver_balance = await db.get_user_balance(receiver_id)
        if receiver_balance is None:
            await message.reply(
                '<tg-emoji emoji-id="5467519850576354798">❕</tg-emoji> <b>Не удалось найти получателя.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        allowed = await _check_and_apply_give_limit(
            sender_id=sender_id , amount=amount , message=message , db=db , time_to_remove_give=time_to_remove_give)
        if not allowed:
            return

        try:
            await db.transfer_currency(sender_id , receiver_id , amount , cause="дать")
        except InsufficientBalanceError:
            await message.reply(
                '<tg-emoji emoji-id="5375312095346704820">💰</tg-emoji> <b>Недостаточно кут для перевода.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        formatted_amount = _fmt_int(amount)
        sender_name = await db.get_firstname_by_user_id(sender_id)
        sender_username = await db.get_username_by_id(sender_id)

        receiver_name = await db.get_firstname_by_user_id(receiver_id)
        receiver_username_db = await db.get_username_by_id(receiver_id)

        chat_id = message.chat.id
        chat_name = message.chat.title or "Личный чат"
        current_time = datetime.now()

        await _finalize_give_limit_if_needed(
            sender_id=sender_id , sender_name=sender_name , sender_username=sender_username , amount=amount ,
            chat_id=chat_id , chat_name=chat_name , user_name_for_givetime=sender_name , current_time=current_time ,
            db=db , time_to_remove_give=time_to_remove_give)

        name_link = await create_user_link(receiver_id , receiver_name , receiver_username_db)

        comment_block = ""
        if comment:
            comment_block = f'\n<blockquote><b>{_escape_html(comment)}</b></blockquote>'

        money_emoji = _get_random_give_emoji()

        await message.reply(
            f"{money_emoji} <b>{name_link} было переведено {formatted_amount} кут</b>{comment_block}" ,
            parse_mode="HTML" , disable_web_page_preview=True)

    # =========================================================
    # GIVE COMMAND
    # =========================================================

    if (message.text or "").strip().lower().startswith("дать"):
        raw_text = (message.text or "").strip()

        if raw_text.lower() == "дать автограф":
            return

        user_id = message.from_user.id
        sender_id = user_id

        randomnumberrandom = random.randint(1 , 100)
        if randomnumberrandom > 70:
            await message.answer("<tg-emoji emoji-id='5264737672684907396'>🍻</tg-emoji>",parse_mode="HTML" , disable_web_page_preview=True)

        print(f"[GIVE][DEBUG] Входящее сообщение: {raw_text}")

        is_reply_mode = bool(message.reply_to_message)

        parsed = _parse_give_command_text(raw_text , is_reply=is_reply_mode)
        print(f"[GIVE][DEBUG] parsed={parsed}")

        if parsed.get("error") == "ignore_autograph":
            return

        if not parsed.get("ok"):
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неверный формат перевода.</b>\n"
                "<i>Примеры:</i>\n"
                "<code>дать @username 1000</code>\n"
                "<code>дать 1000 @username</code>\n"
                "<code>дать https://t.me/username 1000 спасибо</code>\n"
                "<code>дать 1000 спасибо</code> <i>(в ответ на сообщение)</i>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            return

        amount = parsed [ "amount" ]
        comment = (parsed.get("comment") or "").strip()

        if amount is None or amount <= 0:
            await message.reply(
                '<tg-emoji emoji-id="5465143921912846619">💭</tg-emoji> <b>Пожалуйста, укажите сумму больше нуля.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        # -----------------------------------------------------
        # ВАРИАНТ 1: reply
        # -----------------------------------------------------
        if is_reply_mode:
            receiver_id = message.reply_to_message.from_user.id

            if not receiver_id:
                await message.reply(
                    '<tg-emoji emoji-id="5467519850576354798">❕</tg-emoji> <b>Не удалось определить получателя по ответу на сообщение</b>' , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            receiver_username = None
            try:
                receiver_username = await db.get_username_by_id(receiver_id)
            except Exception as e:
                print(f"[GIVE][REPLY][USERNAME][ERROR] {e}")

            await _process_give_transfer(
                message=message , sender_id=sender_id , receiver_id=receiver_id , receiver_username=receiver_username ,
                amount=amount , comment=comment , db=db , time_to_remove_give=time_to_remove_give)
            return

        # -----------------------------------------------------
        # ВАРИАНТ 2: прямой получатель
        # -----------------------------------------------------
        recipient_info = parsed.get("recipient")
        if not recipient_info:
            await message.reply(
                '<tg-emoji emoji-id="5314346928660554905">⚠️</tg-emoji> <b>Не удалось определить получателя.</b>' , parse_mode="HTML" , disable_web_page_preview=True)
            return

        receiver_id , receiver_username = await _resolve_receiver_from_recipient_info(recipient_info , db)

        if receiver_id is None:
            await message.reply(
                '<tg-emoji emoji-id="5467519850576354798">❕</tg-emoji> <b>Не удалось найти получателя.</b>\n'
                '<i>Укажите корректный @username, ссылку, username или ID.</i>' , parse_mode="HTML" ,
                disable_web_page_preview=True)
            return

        await _process_give_transfer(
            message=message , sender_id=sender_id , receiver_id=receiver_id , receiver_username=receiver_username ,
            amount=amount , comment=comment , db=db , time_to_remove_give=time_to_remove_give)
        return





















    # ---------------------------------------------------------
    # НАСТРОЙКИ
    # ---------------------------------------------------------
    GROUP_BALANCE_ADMIN_IDS = {6801702632}


    # ---------------------------------------------------------
    # БАЗОВЫЕ ХЕЛПERS
    # ---------------------------------------------------------
    def _escape_html_group_admin(text: Any) -> str:
        return html.escape(str(text or ""))


    def _fmt_int_group_admin(n: Any) -> str:
        try:
            return f"{int(n):,}".replace(",", ".")
        except Exception:
            return "0"


    def _normalize_text_group_admin(text: str) -> str:
        return " ".join(str(text or "").strip().split())


    def _extract_tg_username_from_link_group_admin(value: str) -> Optional[str]:
        """
        Извлекает username из:
        - https://t.me/username
        - http://t.me/username
        - t.me/username
        - telegram.me/username
        """
        if not value:
            return None

        value = value.strip()

        match = re.search(
            r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{4,})/?$",
            value,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)

        return None


    def _is_private_invite_link_group_admin(value: str) -> bool:
        """
        Примеры:
        - https://t.me/+AbCdEf123
        - t.me/+AbCdEf123
        - https://t.me/joinchat/AbCdEf123
        """
        if not value:
            return False

        value = value.strip().lower()
        return (
            "t.me/+" in value
            or "t.me/joinchat/" in value
            or value.startswith("+")
        )


    def _extract_private_invite_token_group_admin(value: str) -> Optional[str]:
        if not value:
            return None

        value = value.strip()

        m1 = re.search(r"(?:https?://)?t\.me/\+([A-Za-z0-9_-]+)", value, flags=re.IGNORECASE)
        if m1:
            return m1.group(1)

        m2 = re.search(r"(?:https?://)?t\.me/joinchat/([A-Za-z0-9_-]+)", value, flags=re.IGNORECASE)
        if m2:
            return m2.group(1)

        if value.startswith("+") and len(value) > 1:
            return value[1:]

        return None


    def _extract_group_command_parts_group_admin(
        raw_text: str,
        command_name: str,
    ) -> Tuple[Optional[str], Optional[int], str]:
        """
        Возвращает:
        (group_target, amount, comment)

        Для команды вида:
        sypherchatдать <target> <amount> [comment]
        sypherchatснять <target> <amount> [comment]
        """
        if not raw_text:
            return None, None, ""

        raw_text = raw_text.strip()
        parts = raw_text.split(maxsplit=3)

        # Минимум: команда + цель + сумма
        if len(parts) < 3:
            return None, None, ""

        cmd = (parts[0] or "").lower().strip()
        if cmd != command_name.lower().strip():
            return None, None, ""

        group_target = (parts[1] or "").strip()
        amount_raw = (parts[2] or "").strip()
        comment = (parts[3] or "").strip() if len(parts) >= 4 else ""

        try:
            amount = int(str(amount_raw).replace(".", "").replace(" ", ""))
            if amount <= 0:
                return group_target, None, comment
        except Exception:
            return group_target, None, comment

        return group_target, amount, comment


    async def _call_db_method_if_exists_group_admin(db, method_names, *args, **kwargs):
        """
        Пытается вызвать первый существующий async-метод из списка.
        """
        for method_name in method_names:
            method = getattr(db, method_name, None)
            if callable(method):
                try:
                    return await method(*args, **kwargs)
                except TypeError:
                    continue
                except Exception as e:
                    print(f"[GROUP ADMIN][DB CALL] ❌ {method_name} failed: {type(e).__name__}: {e}")
                    continue
        return None


    async def _resolve_group_target_group_admin(bot1, db, raw_target: str) -> Optional[Dict[str, Any]]:
        """
        Пытается определить группу по:
        - chat_id
        - @username
        - public link
        - private invite link (только best-effort через БД / кеш / заранее сохранённые данные)

        Возвращает:
        {
            "chat_id": int,
            "title": str,
            "username": str,
            "invite_link": str,
            "resolved_via": str,
            "chat_obj": <Chat or None>
        }
        """
        raw_target = str(raw_target or "").strip()
        print(f"[GROUP ADMIN][RESOLVE] 🟦 raw_target={raw_target!r}")

        if not raw_target:
            print("[GROUP ADMIN][RESOLVE] ⛔ Пустая цель группы")
            return None

        # -----------------------------------------------------
        # 1) ID группы
        # -----------------------------------------------------
        if re.fullmatch(r"-?\d+", raw_target):
            try:
                target_chat_id = int(raw_target)
                print(f"[GROUP ADMIN][RESOLVE] 🟩 Похоже на chat_id={target_chat_id}")

                chat_obj = await bot1.get_chat(target_chat_id)
                title = getattr(chat_obj, "title", None) or "Группа"
                username = getattr(chat_obj, "username", None)
                invite_link = getattr(chat_obj, "invite_link", None)

                result = {
                    "chat_id": int(target_chat_id),
                    "title": str(title or "Группа"),
                    "username": str(username or ""),
                    "invite_link": str(invite_link or ""),
                    "resolved_via": "chat_id",
                    "chat_obj": chat_obj,
                }
                print(f"[GROUP ADMIN][RESOLVE] ✅ Успешно по chat_id: {result}")
                return result

            except Exception as e:
                print(f"[GROUP ADMIN][RESOLVE] ❌ Не удалось получить chat по id: {type(e).__name__}: {e}")

        # -----------------------------------------------------
        # 2) @username
        # -----------------------------------------------------
        if raw_target.startswith("@") and len(raw_target) > 1:
            username_no_at = raw_target[1:].strip()
            print(f"[GROUP ADMIN][RESOLVE] 🟩 Похоже на @username={username_no_at!r}")

            try:
                chat_obj = await bot1.get_chat(f"@{username_no_at}")
                title = getattr(chat_obj, "title", None) or "Группа"
                username = getattr(chat_obj, "username", None)
                invite_link = getattr(chat_obj, "invite_link", None)
                chat_id = getattr(chat_obj, "id", None)

                if chat_id is None:
                    raise ValueError("chat_id is None")

                result = {
                    "chat_id": int(chat_id),
                    "title": str(title or "Группа"),
                    "username": str(username or username_no_at or ""),
                    "invite_link": str(invite_link or ""),
                    "resolved_via": "@username",
                    "chat_obj": chat_obj,
                }
                print(f"[GROUP ADMIN][RESOLVE] ✅ Успешно по @username: {result}")
                return result

            except Exception as e:
                print(f"[GROUP ADMIN][RESOLVE] ❌ Не удалось получить chat по @username: {type(e).__name__}: {e}")

            # fallback через db
            db_result = await _call_db_method_if_exists_group_admin(
                db,
                [
                    "get_group_by_username",
                    "get_chat_by_username",
                    "get_group_info_by_username",
                    "find_group_by_username",
                    "get_group_by_public_username",
                ],
                username_no_at,
            )
            if db_result:
                print(f"[GROUP ADMIN][RESOLVE] ✅ Найдено через БД по username: {db_result!r}")
                try:
                    chat_id = int(
                        db_result.get("chat_id")
                        if isinstance(db_result, dict)
                        else db_result[0]
                    )
                    title = (
                        db_result.get("title", "Группа")
                        if isinstance(db_result, dict)
                        else "Группа"
                    )
                    username = (
                        db_result.get("username", username_no_at)
                        if isinstance(db_result, dict)
                        else username_no_at
                    )
                    invite_link = (
                        db_result.get("invite_link", "")
                        if isinstance(db_result, dict)
                        else ""
                    )
                    return {
                        "chat_id": chat_id,
                        "title": str(title or "Группа"),
                        "username": str(username or ""),
                        "invite_link": str(invite_link or ""),
                        "resolved_via": "db_username",
                        "chat_obj": None,
                    }
                except Exception as e:
                    print(f"[GROUP ADMIN][RESOLVE] ❌ Ошибка разбора db_result username: {type(e).__name__}: {e}")

        # -----------------------------------------------------
        # 3) Public link
        # -----------------------------------------------------
        username_from_link = _extract_tg_username_from_link_group_admin(raw_target)
        if username_from_link:
            print(f"[GROUP ADMIN][RESOLVE] 🟩 Похоже на public link username={username_from_link!r}")
            try:
                chat_obj = await bot1.get_chat(f"@{username_from_link}")
                title = getattr(chat_obj, "title", None) or "Группа"
                username = getattr(chat_obj, "username", None)
                invite_link = getattr(chat_obj, "invite_link", None)
                chat_id = getattr(chat_obj, "id", None)

                if chat_id is None:
                    raise ValueError("chat_id is None")

                result = {
                    "chat_id": int(chat_id),
                    "title": str(title or "Группа"),
                    "username": str(username or username_from_link or ""),
                    "invite_link": str(invite_link or ""),
                    "resolved_via": "public_link",
                    "chat_obj": chat_obj,
                }
                print(f"[GROUP ADMIN][RESOLVE] ✅ Успешно по public link: {result}")
                return result

            except Exception as e:
                print(f"[GROUP ADMIN][RESOLVE] ❌ Не удалось получить chat по public link: {type(e).__name__}: {e}")

            db_result = await _call_db_method_if_exists_group_admin(
                db,
                [
                    "get_group_by_username",
                    "get_chat_by_username",
                    "get_group_info_by_username",
                    "find_group_by_username",
                    "get_group_by_public_username",
                ],
                username_from_link,
            )
            if db_result:
                print(f"[GROUP ADMIN][RESOLVE] ✅ Найдено через БД по ссылке/username: {db_result!r}")
                try:
                    chat_id = int(
                        db_result.get("chat_id")
                        if isinstance(db_result, dict)
                        else db_result[0]
                    )
                    title = (
                        db_result.get("title", "Группа")
                        if isinstance(db_result, dict)
                        else "Группа"
                    )
                    username = (
                        db_result.get("username", username_from_link)
                        if isinstance(db_result, dict)
                        else username_from_link
                    )
                    invite_link = (
                        db_result.get("invite_link", raw_target)
                        if isinstance(db_result, dict)
                        else raw_target
                    )
                    return {
                        "chat_id": chat_id,
                        "title": str(title or "Группа"),
                        "username": str(username or ""),
                        "invite_link": str(invite_link or ""),
                        "resolved_via": "db_public_link",
                        "chat_obj": None,
                    }
                except Exception as e:
                    print(f"[GROUP ADMIN][RESOLVE] ❌ Ошибка разбора db_result public link: {type(e).__name__}: {e}")

        # -----------------------------------------------------
        # 4) Private invite link (best-effort через БД)
        # -----------------------------------------------------
        if _is_private_invite_link_group_admin(raw_target):
            print("[GROUP ADMIN][RESOLVE] 🟨 Похоже на приватную ссылку, пытаюсь найти через БД/кеш")
            invite_token = _extract_private_invite_token_group_admin(raw_target)

            # Полная ссылка
            db_result_full = await _call_db_method_if_exists_group_admin(
                db,
                [
                    "get_group_by_invite_link",
                    "get_chat_by_invite_link",
                    "find_group_by_invite_link",
                    "get_group_info_by_invite_link",
                ],
                raw_target,
            )
            if db_result_full:
                print(f"[GROUP ADMIN][RESOLVE] ✅ Найдено через БД по полной invite_link: {db_result_full!r}")
                try:
                    chat_id = int(
                        db_result_full.get("chat_id")
                        if isinstance(db_result_full, dict)
                        else db_result_full[0]
                    )
                    title = (
                        db_result_full.get("title", "Группа")
                        if isinstance(db_result_full, dict)
                        else "Группа"
                    )
                    username = (
                        db_result_full.get("username", "")
                        if isinstance(db_result_full, dict)
                        else ""
                    )
                    invite_link = (
                        db_result_full.get("invite_link", raw_target)
                        if isinstance(db_result_full, dict)
                        else raw_target
                    )
                    return {
                        "chat_id": chat_id,
                        "title": str(title or "Группа"),
                        "username": str(username or ""),
                        "invite_link": str(invite_link or raw_target),
                        "resolved_via": "db_private_invite_link",
                        "chat_obj": None,
                    }
                except Exception as e:
                    print(f"[GROUP ADMIN][RESOLVE] ❌ Ошибка разбора db_result private full: {type(e).__name__}: {e}")

            # Токен приглашения
            if invite_token:
                db_result_token = await _call_db_method_if_exists_group_admin(
                    db,
                    [
                        "get_group_by_invite_token",
                        "get_chat_by_invite_token",
                        "find_group_by_invite_token",
                    ],
                    invite_token,
                )
                if db_result_token:
                    print(f"[GROUP ADMIN][RESOLVE] ✅ Найдено через БД по invite_token: {db_result_token!r}")
                    try:
                        chat_id = int(
                            db_result_token.get("chat_id")
                            if isinstance(db_result_token, dict)
                            else db_result_token[0]
                        )
                        title = (
                            db_result_token.get("title", "Группа")
                            if isinstance(db_result_token, dict)
                            else "Группа"
                        )
                        username = (
                            db_result_token.get("username", "")
                            if isinstance(db_result_token, dict)
                            else ""
                        )
                        invite_link = (
                            db_result_token.get("invite_link", raw_target)
                            if isinstance(db_result_token, dict)
                            else raw_target
                        )
                        return {
                            "chat_id": chat_id,
                            "title": str(title or "Группа"),
                            "username": str(username or ""),
                            "invite_link": str(invite_link or raw_target),
                            "resolved_via": "db_private_invite_token",
                            "chat_obj": None,
                        }
                    except Exception as e:
                        print(f"[GROUP ADMIN][RESOLVE] ❌ Ошибка разбора db_result private token: {type(e).__name__}: {e}")

        print("[GROUP ADMIN][RESOLVE] ⛔ Не удалось определить группу")
        return None


    async def _get_group_balance_safe_group_admin(bot1, db, chat_id: int) -> int:
        """
        Безопасно получает баланс группы через доступные методы БД.
        """
        raw_balance = None

        # Сначала пробуем твои методы
        try:
            raw_balance = await db.get_chat_balance(bot1, chat_id)
            print(f"[GROUP ADMIN][BALANCE] 🟩 get_chat_balance -> {raw_balance!r}")
        except Exception as e:
            print(f"[GROUP ADMIN][BALANCE] 🟨 get_chat_balance failed: {type(e).__name__}: {e}")

        if raw_balance is None:
            try:
                raw_balance = await db.get_chat_balancebalance(bot1, chat_id)
                print(f"[GROUP ADMIN][BALANCE] 🟩 get_chat_balancebalance -> {raw_balance!r}")
            except Exception as e:
                print(f"[GROUP ADMIN][BALANCE] 🟨 get_chat_balancebalance failed: {type(e).__name__}: {e}")

        try:
            return int(float(raw_balance)) if raw_balance not in (None, "", False) else 0
        except Exception:
            return 0


    def _build_group_balance_result_kb_group_admin(
        amount: int,
        action_text: str,
    ) -> InlineKeyboardMarkup:
        amount_formatted = _fmt_int_group_admin(amount)

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{amount_formatted} кут",
                        callback_data="noop",
                        style="default",
                        icon_custom_emoji_id="6028338546736107668",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=action_text,
                        callback_data="noop",
                        style="default",
                        icon_custom_emoji_id="6028346797368283073",
                    )
                ],
            ]
        )


    # ---------------------------------------------------------
    # ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ИЗМЕНЕНИЯ БАЛАНСА ГРУПП
    # ---------------------------------------------------------
    async def admin_give_group_balance_sypherchat(
        message,
        bot1,
        db,
        group_target: str,
        amount: int,
        comment: str = "",
    ):
        """
        Админское начисление валюты на баланс группы.
        Использует:
        - db.ensure_group(...)
        - db.update_chat_balance(bot1, chat_id, amount)
        """
        print(f"[GROUP ADMIN GIVE] 🟦 group_target={group_target!r} amount={amount!r} comment={comment!r}")

        if amount is None or int(amount) <= 0:
            print("[GROUP ADMIN GIVE] ⛔ amount некорректный")
            await message.reply(
                "💭 <b>Пожалуйста, укажите сумму больше нуля.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        try:
            group_info = await _resolve_group_target_group_admin(bot1, db, group_target)
            if not group_info:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Не удалось определить группу. Укажи корректный chat_id, @username, ссылку или заранее известную приватную ссылку группы.</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return

            target_chat_id = int(group_info["chat_id"])
            target_title = str(group_info.get("title") or "Группа")
            target_username = str(group_info.get("username") or "")
            resolved_via = str(group_info.get("resolved_via") or "")

            print(
                f"[GROUP ADMIN GIVE] 🟩 resolved chat_id={target_chat_id} "
                f"title={target_title!r} username={target_username!r} via={resolved_via!r}"
            )

            # ensure_group
            print("[GROUP ADMIN GIVE] 🟩 Вызываю db.ensure_group(...)")
            await db.ensure_group(
                bot1=bot1,
                chat_id=target_chat_id,
                sync_func=add_or_update_group_info,
            )
            print("[GROUP ADMIN GIVE] ✅ ensure_group выполнен")

            balance_before = await _get_group_balance_safe_group_admin(bot1, db, target_chat_id)
            print(f"[GROUP ADMIN GIVE] 🟩 balance_before={balance_before}")

            # ВАЖНО: используем именно update_chat_balance(...)
            print("[GROUP ADMIN GIVE] 🟩 Вызываю db.update_chat_balance(...)")
            await db.update_chat_balance(bot1, target_chat_id, int(amount))
            print("[GROUP ADMIN GIVE] ✅ Баланс группы пополнен")

            balance_after = await _get_group_balance_safe_group_admin(bot1, db, target_chat_id)
            print(f"[GROUP ADMIN GIVE] 🟩 balance_after={balance_after}")

            comment_html = ""
            if comment:
                comment_html = (
                    f"\n💭 <b>Комментарий:</b> "
                    f"<i>«{_escape_html_group_admin(comment)}»</i>"
                )

            group_label = (
                f"@{_escape_html_group_admin(target_username)}"
                if target_username
                else _escape_html_group_admin(target_title)
            )

            keyboard = _build_group_balance_result_kb_group_admin(
                amount=int(amount),
                action_text="Зачислено на баланс группы",
            )

            await message.reply(
                f"<tg-emoji emoji-id='5472178859300363509'>🏖</tg-emoji> "
                f"<b>На баланс группы {group_label} зачислено {_fmt_int_group_admin(amount)} кут.</b>\n"
                f"💰 <b>Баланс до:</b> {_fmt_int_group_admin(balance_before)}\n"
                f"💰 <b>Баланс после:</b> {_fmt_int_group_admin(balance_after)}"
                f"{comment_html}",
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            return

        except Exception as e:
            print(f"[GROUP ADMIN GIVE] ❌ Ошибка: {type(e).__name__}: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при начислении валюты на баланс группы.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return


    async def admin_take_group_balance_sypherchat(
        message,
        bot1,
        db,
        group_target: str,
        amount: int,
        comment: str = "",
    ):
        """
        Админское снятие валюты с баланса группы.
        Использует:
        - db.ensure_group(...)
        - db.update_chat_balance_minus(chat_id, amount)
        """
        print(f"[GROUP ADMIN TAKE] 🟦 group_target={group_target!r} amount={amount!r} comment={comment!r}")

        if amount is None or int(amount) <= 0:
            print("[GROUP ADMIN TAKE] ⛔ amount некорректный")
            await message.reply(
                "💭 <b>Пожалуйста, укажите сумму больше нуля.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        try:
            group_info = await _resolve_group_target_group_admin(bot1, db, group_target)
            if not group_info:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Не удалось определить группу. Укажи корректный chat_id, @username, ссылку или заранее известную приватную ссылку группы.</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return

            target_chat_id = int(group_info["chat_id"])
            target_title = str(group_info.get("title") or "Группа")
            target_username = str(group_info.get("username") or "")
            resolved_via = str(group_info.get("resolved_via") or "")

            print(
                f"[GROUP ADMIN TAKE] 🟩 resolved chat_id={target_chat_id} "
                f"title={target_title!r} username={target_username!r} via={resolved_via!r}"
            )

            # ensure_group
            print("[GROUP ADMIN TAKE] 🟩 Вызываю db.ensure_group(...)")
            await db.ensure_group(
                bot1=bot1,
                chat_id=target_chat_id,
                sync_func=add_or_update_group_info,
            )
            print("[GROUP ADMIN TAKE] ✅ ensure_group выполнен")

            balance_before = await _get_group_balance_safe_group_admin(bot1, db, target_chat_id)
            print(f"[GROUP ADMIN TAKE] 🟩 balance_before={balance_before}")

            if balance_before < int(amount):
                print("[GROUP ADMIN TAKE] ⛔ Недостаточно средств на балансе группы")
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                    "<b>Недостаточно средств на балансе группы.</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return

            # ВАЖНО: используем именно update_chat_balance_minus(...)
            print("[GROUP ADMIN TAKE] 🟩 Вызываю db.update_chat_balance_minus(...)")
            await db.update_chat_balance_minus(target_chat_id, int(amount))
            print("[GROUP ADMIN TAKE] ✅ Баланс группы уменьшен")

            balance_after = await _get_group_balance_safe_group_admin(bot1, db, target_chat_id)
            print(f"[GROUP ADMIN TAKE] 🟩 balance_after={balance_after}")

            comment_html = ""
            if comment:
                comment_html = (
                    f"\n💭 <b>Комментарий:</b> "
                    f"<i>«{_escape_html_group_admin(comment)}»</i>"
                )

            group_label = (
                f"@{_escape_html_group_admin(target_username)}"
                if target_username
                else _escape_html_group_admin(target_title)
            )

            keyboard = _build_group_balance_result_kb_group_admin(
                amount=int(amount),
                action_text="Снято с баланса группы",
            )

            await message.reply(
                f"<tg-emoji emoji-id='5199790590279033017'>🏖</tg-emoji> "
                f"<b>С баланса группы {group_label} снято {_fmt_int_group_admin(amount)} кут.</b>\n"
                f"💰 <b>Баланс до:</b> {_fmt_int_group_admin(balance_before)}\n"
                f"💰 <b>Баланс после:</b> {_fmt_int_group_admin(balance_after)}"
                f"{comment_html}",
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            return

        except Exception as e:
            print(f"[GROUP ADMIN TAKE] ❌ Ошибка: {type(e).__name__}: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
                "<b>Произошла ошибка при снятии валюты с баланса группы.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return


    # ---------------------------------------------------------
    # ОБРАБОТЧИКИ КОМАНД ВНУТРИ ТВОЕГО ОСНОВНОГО message handler
    # ---------------------------------------------------------

    # =========================================================
    # sypherchatдать <group> <amount> [comment]
    # =========================================================
    if (message.text or "").lower().startswith("sypherchatдать"):
        current_time = datetime.now()
        user_id = int(message.from_user.id)

        print(f"[GROUP ADMIN GIVE CMD] 🟦 raw={message.text!r}")
        print(f"[GROUP ADMIN GIVE CMD] 🟦 user_id={user_id}")

        if user_id not in GROUP_BALANCE_ADMIN_IDS:
            print("[GROUP ADMIN GIVE CMD] ⛔ Нет доступа")
            return

        randomnumberrandom = random.randint(1, 100)
        if randomnumberrandom > 70:
            await message.answer("💰")

        group_target, amount, comment = _extract_group_command_parts_group_admin(
            raw_text=message.text,
            command_name="sypherchatдать",
        )

        print(
            f"[GROUP ADMIN GIVE CMD] 🟨 parsed group_target={group_target!r} "
            f"amount={amount!r} comment={comment!r}"
        )

        if not group_target or amount is None:
            await message.reply(
                "<b>Неверный формат команды.</b>\n\n"
                "<code>sypherchatдать @username 1000</code>\n"
                "<code>sypherchatдать -1001234567890 1000</code>\n"
                "<code>sypherchatдать https://t.me/groupname 1000</code>\n"
                "<code>sypherchatдать https://t.me/+xxxx 1000</code>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        await admin_give_group_balance_sypherchat(
            message=message,
            bot1=bot1,
            db=db,
            group_target=group_target,
            amount=amount,
            comment=comment,
        )
        return


    # =========================================================
    # sypherchatснять <group> <amount> [comment]
    # =========================================================
    if (message.text or "").lower().startswith("sypherchatснять"):
        current_time = datetime.now()
        user_id = int(message.from_user.id)

        print(f"[GROUP ADMIN TAKE CMD] 🟦 raw={message.text!r}")
        print(f"[GROUP ADMIN TAKE CMD] 🟦 user_id={user_id}")

        if user_id not in GROUP_BALANCE_ADMIN_IDS:
            print("[GROUP ADMIN TAKE CMD] ⛔ Нет доступа")
            return

        randomnumberrandom = random.randint(1, 100)
        if randomnumberrandom > 70:
            await message.answer("💰")

        group_target, amount, comment = _extract_group_command_parts_group_admin(
            raw_text=message.text,
            command_name="sypherchatснять",
        )

        print(
            f"[GROUP ADMIN TAKE CMD] 🟨 parsed group_target={group_target!r} "
            f"amount={amount!r} comment={comment!r}"
        )

        if not group_target or amount is None:
            await message.reply(
                "<b>Неверный формат команды.</b>\n\n"
                "<code>sypherchatснять @username 1000</code>\n"
                "<code>sypherchatснять -1001234567890 1000</code>\n"
                "<code>sypherchatснять https://t.me/groupname 1000</code>\n"
                "<code>sypherchatснять https://t.me/+xxxx 1000</code>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        await admin_take_group_balance_sypherchat(
            message=message,
            bot1=bot1,
            db=db,
            group_target=group_target,
            amount=amount,
            comment=comment,
        )
        return









