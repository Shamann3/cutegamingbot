import sqlite3
import datetime
import aiogram.utils

from aiogram import Bot, Dispatcher, types

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.config import *
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from bot.design.buttons import *
from bot.db_create.db import *

import re


from main import *


async def create_user_link(user_id: int, first_name: str, username: str = None) -> str:
    """Создает ссылку на профиль пользователя."""
    if username:
        # Если есть username, создаем гиперссылку с именем
        user_hyperlink = f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name)}</a>"
    elif first_name:
        # Если username нет, используем имя без ссылки
        user_hyperlink = html.escape(first_name)
    else:
        # Если отсутствуют и имя, и username
        return "У пользователя нет имени."

    return user_hyperlink



@dp.callback_query(lambda c: c.data == 'cancelcancel_divorce')
async def cancel_divorce(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id  # Получаем ID пользователя из callback_query
    message = callback_query.message  # Получаем сообщение из callback_query
    message_id = callback_query.message.message_id
    chat_id = callback_query.message.chat.id
    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqq1")
    if user_id not in user_message_divorce or user_message_divorce [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    await callback_query.answer()
    await callback_query.message.edit_text("❤️ <b>Развод отменен</b>",parse_mode="HTML", show_alert=True)

# Обработка нажатия на кнопку "💔 Развестись"
@dp.callback_query(lambda c: c.data == 'proceedproceed_divorce')
async def proceed_divorce(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id  # Получаем ID пользователя из callback_query
    message = callback_query.message  # Получаем сообщение из callback_query
    message_id = callback_query.message.message_id
    chat_id = callback_query.message.chat.id
    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqq2")
    if user_id not in user_message_divorce or user_message_divorce [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    await callback_query.answer()

    await db.divorce(message, user_id)
@dp.message()
async def cmd_start(message: Message):
    if message.text.lower() in [ "развод3412" , "Развод3412","развестись3412","разорвать отношения3412","разорвать брак3412" ]:
        user_id = message.from_user.id

        # Проверяем, находится ли пользователь в браке
        is_in_marriage = await db.check_user_marriage_status34123412(user_id)

        if is_in_marriage:
            # Создаем кнопки для подтверждения развода
            cancel_button = InlineKeyboardButton(text="🌹 Нет" , callback_data="cancelcancel_divorce")
            divorce_button = InlineKeyboardButton(text="🥀 Да" , callback_data="proceedproceed_divorce")

            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ cancel_button , divorce_button ] ]  # Кнопки в одну строку
            )

            # Отправляем сообщение с клавиатурой
            msg = await message.reply(
                "💋 <b>Вы уверены, что хотите развестись?</b>" ,
                reply_markup=keyboard, parse_mode="HTML")

            user_message_divorce [ user_id ] = msg.message_id
        else:
            # Если пользователь не в браке, отправляем сообщение
            await message.reply(
                "🥀 <b>Вы не находитесь в браке</b>" , disable_web_page_preview=True ,
                parse_mode="HTML")

    elif message.text.startswith(('Инфо34123412' , 'инфо34123412')):

        try:
            text = message.text.split() [ 1 ]

            if text.startswith('@'):
                username = text [ 1: ]
            elif text.startswith('https://t.me/'):
                username = text.split('/') [ -1 ]
            else:
                return

            user_id = await db.get_user_id_by_username(username)
            if not user_id:
                raise ValueError("Пользователь не найден")
        except (IndexError , ValueError) as e:
            await message.answer(f"Ошибка: {e}")
            return

        marriage_info = await db.get_marriage_info(user_id)
        if not marriage_info:
            await message.answer(
                f"🔥 Пользователь <a href='https://t.me/{username}'>{username}</a> не состоит в браке." ,
                parse_mode="HTML")
            return

        partner_id = marriage_info [ 0 ] if marriage_info [ 0 ] != user_id else marriage_info [ 1 ]
        partner_data = await db.get_partner_data(partner_id)
        if not partner_data:
            await message.answer("Данные о партнере не найдены.")
            return

        partner_username = partner_data [ "username" ] if partner_data [ "username" ] else partner_data [ "first_name" ]
        marriage_status = "👰🏻‍♀️🤵 В браке" if marriage_info [ 2 ] == 1 else "⌚️ Ожидание подтверждения брака"
        marriage_datetime = marriage_info [ 3 ]
        marriage_start_time = datetime.strptime(str(marriage_datetime) , "%Y-%m-%d %H:%M:%S")
        marriage_duration = datetime.now() - marriage_start_time
        duration_str = str(marriage_duration).split('.') [ 0 ]

        message_text = (f"👨‍💻 Информация брака <a href='https://t.me/{username}'>{username}</a>:\n"
                        f"🗽 Статус: {marriage_status}\n"
                        f"👤 Партнер: <a href='https://t.me/{partner_username}'>{partner_username}</a>\n"
                        f"⌚️ Длительность: {marriage_datetime}\n"
                        f"️⌛ Дата создания: {duration_str}")

        await message.answer(message_text , disable_web_page_preview=True , parse_mode="HTML")

    if message.text.lower().startswith(('брак3412' , 'пожениться3412','поженится3412' , 'свадьба3412' , 'сделать предложение3412')):
        user_id = message.from_user.id
        print(f"Идентификатор пользователя: {user_id}")
        if "браки" in message.text.lower():
            return  # просто игнорируем и не продолжаем

        if await db.is_married(user_id):
            print("Пользователь уже состоит в браке.")
            await message.reply(
                "🌹 <b>Вы уже состоите в браке</b>" , parse_mode="HTML" , disable_web_page_preview=True)
            return

        try:
            text_parts = message.text.split()
            print(f"Разделение текста команды: {text_parts}")

            if message.reply_to_message:
                partner_id = message.reply_to_message.from_user.id
                print(f"Обнаружен ответ на сообщение. Идентификатор партнера: {partner_id}")
                comment = " ".join(text_parts [ 1: ]) if len(text_parts) > 1 else ""
            else:
                partner_id = None
                comment = ""
                for i , part in enumerate(text_parts [ 1: ]):
                    if part.startswith('@') or part.isdigit() or part.startswith('https://t.me/'):
                        recipient_info = part.strip()
                        comment = " ".join(text_parts [ i + 2: ]) if i + 2 < len(text_parts) else ""
                        break
                else:
                    raise ValueError("Не указан партнер")

                user_id_found = False
                if recipient_info.startswith('@'):
                    username = recipient_info [ 1: ]
                    partner_id = await db.get_user_id_by_username(username)
                elif recipient_info.startswith('https://t.me/'):
                    username = recipient_info.split('/') [ -1 ]
                    partner_id = await db.get_user_id_by_username(username)
                elif recipient_info.isdigit():
                    partner_id = int(recipient_info)
                    user_id_found = True
                else:
                    try:
                        partner_id = int(recipient_info)
                        user_id_found = True
                    except ValueError:
                        await message.reply(
                            '⚠️ Неверный формат. Укажите корректный юзернейм, ссылку или ID.' ,
                            parse_mode="HTML")
                        return

                print(f"Поиск пользователя по: {recipient_info}. Идентификатор партнера: {partner_id}")

            if partner_id == 0:
                raise ValueError("Пользователь не найден")

            if partner_id in [7683193125,7357700583]:  # Замените 'bot_id' на фактический идентификатор вашего бота
                await message.reply(
                    '😏 <b>Вы слишком красивы для меня</b>' , parse_mode="HTML" , disable_web_page_preview=True)
                return
            if await db.is_married(partner_id):
                print("Пользователь уже в браке.")
                await message.answer(
                    "❤️ <b>Пользователь уже находится в отношениях</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            if user_id == partner_id:
                print("Пользователь пытается предложить брак самому себе.")
                await message.answer("🥀 Вы не можете предложить брак самому себе")
                return

            if user_id == 1099022485 and partner_id != 6801702632:
                await message.reply(
                    "❌" ,
                    parse_mode="HTML")
                return
        except (IndexError , ValueError) as e:
            print(f"Ошибка при обработке команды 'брак': {e}")
            await message.reply(
                '⚠️ <b>Неверный формат. Напишите "Брак" в ответ на сообщение другого пользователя или укажите его юзернейм/ID.</b>' ,
                parse_mode="HTML")
            return

        print(f"Отправка запроса на брак. Комментарий: {comment}")
        await db.invite_to_marriage(message , partner_id , comment)


@dp.callback_query(lambda c: c.data == 'cancel')
async def process_callback_button_cancel(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id

    success = await db.cancel_marriage_request(user_id)
    phrases = [ "Обручальные кольца возвращаются в магазин." ,
        "Шагаем в сторону одиночества, свадьбы не будет." , "Запрос на брак отклонен!","Обручение отложено до лучших времен." ]
    random_phrase = random.choice(phrases)
    if success:

        await dp.bot.delete_message(
            chat_id=callback_query.message.chat.id , message_id=callback_query.message.message_id)

        await callback_query.message.edit_text(f"🕊 <b>{random_phrase}</b>" , parse_mode="HTML")

    else:
        await callback_query.answer("⚠️ Время ожидания истекло" , show_alert=True)
        await callback_query.message.delete()



@dp.callback_query(lambda c: c.data == 'reject')
async def process_callback_button_reject(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id

    # Получаем информацию о запросе на брак, к которому относится эта кнопка "отклонить"
    marriage_info = await db.get_marriage_request_info_by_chat_id(callback_query.message.chat.id)

    # Проверяем, является ли текущий пользователь тем, кому было отправлено предложение брака
    if marriage_info and user_id == marriage_info[1]:
        try:
            # Удаляем запрос на брак из базы данных
            await db.delete_marriage_request_by_chat_id(callback_query.message.chat.id)

            # Удаляем сообщение с кнопками
            #await dp.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)

            # Отправляем уведомление о отклонении предложения брака
            #await callback_query.message.answer("<b>🥀 Запрос на брак отклонен</b>")
            await callback_query.message.edit_text("<b>🥀 Запрос на брак отклонен</b>" , parse_mode="HTML")
        except Exception as e:
            print(f"[ERROR] Ошибка при отклонении запроса: {e}")
            await callback_query.answer("⚠️ Произошла ошибка при обработке вашего запроса.")
    else:
        # Если пользователь, нажавший кнопку "отклонить", не является тем, кому было предложено брака, отправляем уведомление через callback answer
        randommessagehelp1 = random.choice(randommessagehelp)
        print("qqqqq3")
        await callback_query.answer(f"{randommessagehelp1}")




@dp.callback_query(lambda c: c.data == 'reject2')
async def process_callback_button_reject(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id

    # Попробуем отклонить запрос на брак
    result = await db.reject_marriage_request(user_id)

    if result:
        user_id1, user_id2 = result
        print(f"Пользователь {user_id} отклонил запрос. Проверяем, кто именно нажал на кнопку:")
        print(f"user_id1: {user_id1}, user_id2: {user_id2}")

        # Проверяем, кто нажал на кнопку: user_id1 или user_id2
        if user_id == user_id2:
            # Если это user_id2, то отправляем сообщение user_id1
            try:
                await bot1.send_message(user_id1, "<b>🥀 Ваш запрос на брак был отклонен.</b>", parse_mode="HTML")
                print(f"Сообщение отправлено user_id1: {user_id1}")
            except Exception as e:
                print(f"Ошибка при отправке сообщения user_id1: {e}")

            # Удаляем сообщение с кнопками и отправляем уведомление об отклонении запроса
            await callback_query.message.edit_text("<b>🥀 Запрос на брак отклонен</b>", parse_mode="HTML")
        elif user_id == user_id1:
            # Если это user_id1, то отправляем сообщение user_id2
            try:
                await bot1.send_message(user_id2, "<b>🥀 Ваш запрос на брак был отклонен.</b>", parse_mode="HTML")
                print(f"Сообщение отправлено user_id2: {user_id2}")
            except Exception as e:
                print(f"Ошибка при отправке сообщения user_id2: {e}")

            # Удаляем сообщение с кнопками и отправляем уведомление об отклонении запроса
            await callback_query.message.edit_text("<b>🥀 Запрос на брак отклонен</b>", parse_mode="HTML")
        else:
            # Если не user_id1 и не user_id2 (например, если это какой-то другой пользователь)
            randommessagehelp1 = random.choice(randommessagehelp)
            print("qqqqq4")
            await callback_query.answer(f"{randommessagehelp1}")
    else:
        # Если не был найден запрос на брак для отклонения
        await callback_query.answer("⚠️ Время ожидания истекло", show_alert=True)
        await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == 'accept')
async def process_callback_button_accept(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id

    partner_info = await db.get_partner_info_for_accept(user_id)

    if partner_info:
        await callback_query.answer()
        partner_id, marriage_chat_id = partner_info
        await db.update_marriage_status(user_id)

        message_id = callback_query.message.message_id
        #try:
        #    await dp.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=message_id)
        #except aiogram.utils.exceptions.MessageToDeleteNotFound:
        #    print(f"Message with ID {message_id} not found or already deleted.")

        partner_data = await db.get_user_info_by_id(partner_id)
        partner_username = partner_data["username"] if partner_data["username"] else partner_data["first_name"]
        user_data = await db.get_user_info_by_id(user_id)
        user_username = user_data["username"] if user_data["username"] else user_data["first_name"]


        first_name = await db.get_firstname_by_user_id(partner_id)
        username = await db.get_username_by_user_id(partner_id)
        name_link111 = await create_user_link(partner_id , first_name , username)

        first_name1 = await db.get_firstname_by_user_id(user_id)
        username1 = await db.get_username_by_user_id(user_id)
        name_link1111 = await create_user_link(user_id , first_name1 , username1)
        randommessage = random.choice([
            f"<b>{name_link111} и {name_link1111} теперь вместе!</b>",
            f"<b>{name_link111} и {name_link1111} официально стали парой!</b>"])
        await callback_query.message.edit_text(
            f"💍 {randommessage}",
            parse_mode="HTML", disable_web_page_preview=True)
    else:
        randommessagehelp1 = random.choice(randommessagehelp)
        print("qqqqq5")
        await callback_query.answer(f"{randommessagehelp1}")




@dp.callback_query(lambda c: c.data == 'accept2')
async def process_callback_button_accept(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id  # ID пользователя, который нажал кнопку

    # Получаем информацию о партнере и чате
    partner_info = await db.get_partner_info_for_accept(user_id)

    if partner_info:
        await callback_query.answer()
        partner_id, marriage_chat_id = partner_info

        # Обновляем статус брака в базе данных
        await db.update_marriage_status(user_id)

        # Удаляем сообщение с кнопками
        await callback_query.message.delete()

        # Получаем информацию о пользователе, сделавшем предложение
        partner_data = await db.get_user_info_by_id(partner_id)
        partner_username = partner_data["username"] if partner_data["username"] else partner_data["first_name"]

        # Получаем информацию о пользователе, который принял предложение
        user_data = await db.get_user_info_by_id(user_id)
        user_username = user_data["username"] if user_data["username"] else user_data["first_name"]

        # Показываем уведомление о принятии

        # Создаем красивые ссылки на имена пользователей
        first_name_partner = await db.get_firstname_by_user_id(partner_id)
        username_partner = await db.get_username_by_user_id(partner_id)
        name_link_partner = await create_user_link(partner_id, first_name_partner, username_partner)

        first_name_user = await db.get_firstname_by_user_id(user_id)
        username_user = await db.get_username_by_user_id(user_id)
        name_link_user = await create_user_link(user_id, first_name_user, username_user)

        # Отправляем сообщение в чат о том, что пара образовалась
        await callback_query.message.answer(
            f"💍 <b>{name_link_user} и {name_link_partner} теперь вместе!</b>",
            parse_mode="HTML", disable_web_page_preview=True
        )

        await bot1.send_message(
            marriage_chat_id,
            f"💍 <b>{name_link_partner} и {name_link_user} официально стали парой!</b>",
            parse_mode="HTML", disable_web_page_preview=True
        )

        # Определяем, кому именно отправить ЛС (тому, кто НЕ нажал кнопку)
        receiver_id = partner_id if user_id != partner_id else user_id

        await bot1.send_message(
            receiver_id,
            "<b>🥂 Ваше предложение принято!</b>",
            parse_mode="HTML"
        )

    else:
        # Если предложение не найдено или нет прав на его принятие
        randommessagehelp1 = random.choice(randommessagehelp)
        print("qqqqq6")
        await callback_query.answer(f"{randommessagehelp1}")



@dp.callback_query(lambda c: c.data.startswith('marriageclosemessage_'))
async def send_request_pm(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    partner_id = int(callback_query.data.split('_') [ -1 ])

    # Проверяем существование запроса на брак
    marriage_request_info = await db.get_marriage_request_info(user_id , partner_id)

    if marriage_request_info:
        await db.remove_marriage_request(user_id , partner_id)
        await callback_query.answer("🕊 Запрос был удален",show_alert=True)
        await callback_query.message.delete()


    else:
        randommessagehelp1 = random.choice(randommessagehelp)
        await callback_query.answer(f"{randommessagehelp1}")
@dp.callback_query(lambda c: c.data.startswith('smarriageend_request_pm_'))  # Обработчик для кнопки "Отправить запрос в лс"
async def send_request_pm(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    partner_id = int(callback_query.data.split('_') [ -1 ])

    # Проверяем существование запроса на брак
    marriage_request_info = await db.get_marriage_request_info(user_id , partner_id)

    if marriage_request_info:
        await callback_query.answer()
        # Получаем данные отправителя


        first_name11 = await db.get_firstname_by_user_id(user_id)
        username11 = await db.get_username_by_user_id(user_id)
        name_link1111 = await create_user_link(user_id , first_name11 , username11)


        comment = marriage_request_info.get("comment" , "")  # Получаем комментарий, если он есть

        randommessage = random.choice(
            [ f"💍 <b>{name_link1111} предложил(-а) вам брак</b>" ,
                f'💍 <b>{name_link1111} сделал(-а) вам предложение!</b>' ,
                f'💍 <b>{name_link1111} предложил(-а) вам руку и сердце!</b>' ])

        if comment:
            randommessage += f"\n💬 <b>{comment}</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ ])

        # Подбираем кнопки в зависимости от сообщения
        if "предложил(-а) вам брак" in randommessage:
            accept_button = InlineKeyboardButton(text="🌹 Да" , callback_data="accept2")
            reject_button = InlineKeyboardButton(text="🥀 Нет" , callback_data="reject2")
        elif "сделал(-а) вам предложение" in randommessage:
            accept_button = InlineKeyboardButton(text="🌹 Принять" , callback_data="accept2")
            reject_button = InlineKeyboardButton(text="🥀 Отклонить" , callback_data="reject2")
        else:
            # Если сообщение не содержит нужных фраз, добавляем дефолтные кнопки
            accept_button = InlineKeyboardButton(text="🌹 Принять" , callback_data="accept2")
            reject_button = InlineKeyboardButton(text="🥀 Отклонить" , callback_data="reject2")

        # Добавляем кнопки в клавиатуру
        keyboard.inline_keyboard.append([ reject_button , accept_button ])

        # Отправляем сообщение с запросом на брак и кнопками "Принять" и "Отклонить"

        messagecalldadd = randommessage

        first_name111 = await db.get_firstname_by_user_id(partner_id)
        username111 = await db.get_username_by_user_id(partner_id)
        name_link11111 = await create_user_link(partner_id , first_name111 , username111)

        await callback_query.message.edit_text(
            f"🕊 <b>Запрос на брак отправлен в лс {name_link11111}</b>" ,
            parse_mode="HTML", disable_web_page_preview=True)

        try:
            await bot1.send_message(chat_id=partner_id, text=messagecalldadd, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
        except TelegramForbiddenError:
            print(f"❌ Пользователь {partner_id} не запускал бота. Нельзя начать диалог.")
            await callback_query.answer(
                f"⚠️ Не удалось отправить запрос на брак пользователю {first_name111}. Он не начал разговор с ботом.")
        except TelegramBadRequest as e:
            print(f"Произошла ошибка при отправке: {e}")
            await callback_query.answer("Произошла ошибка при отправке сообщения.")
    else:
        randommessagehelp1 = random.choice(randommessagehelp)
        await callback_query.answer(f"{randommessagehelp1}")
















async def my_marriage_info(message: Message):
    if message.text.lower() in [ "мой брак3412" ]:
        user_id = message.from_user.id

        try:
            marriage_info = await db.get_marriage_info(user_id)

            if not marriage_info:
                await message.reply("☁️ <b>Вы не состоите в браке</b>" , parse_mode="HTML")
                return

            partner_info_set = set()
            partner_info_list = [ ]
            love_coins_total = 0

            for marriage in marriage_info:
                partner_id , status , marriage_date , love_coins = marriage
                if status != 1:
                    continue

                love_coins_total += love_coins
                if partner_id in partner_info_set:
                    continue

                partner_info_set.add(partner_id)
                partner_data = await db.get_partner_data(partner_id)

                if partner_data:
                    first_name = await db.get_firstname_by_user_id(partner_id)
                    username = await db.get_username_by_user_id(partner_id)
                    partner_link = await create_user_link(partner_id , first_name , username)
                    partner_info_list.append(partner_link)

            try:
                marriage_datetime = datetime.strptime(marriage_date , "%d.%m.%Y %H:%M:%S")
            except ValueError:
                marriage_datetime = datetime.strptime(marriage_date , "%Y-%m-%d %H:%M:%S")

            marriage_duration_str = format_timedelta(datetime.now() - marriage_datetime)
            formatted_love_coins = f"{love_coins_total:,}".replace("," , ".")

            user_first_name = await db.get_firstname_by_user_id(user_id)
            user_username = await db.get_username_by_user_id(user_id)
            user_link = await create_user_link(user_id , user_first_name , user_username)

            if partner_info_list:
                partner_info_str = ', '.join(partner_info_list)
                message_text = f"""
🌹 <b>{user_link} и {partner_info_str}</b>
💋 <b>Вместе уже {marriage_duration_str}</b>
❣️ <b>Свадьба {marriage_datetime.strftime('%d.%m.%Y %H:%M:%S')}</b>
                    """.strip()
                await message.answer(message_text , parse_mode="HTML" , disable_web_page_preview=True)
            else:
                await message.reply("☁️ <b>Вы не состоите в браке</b>" , parse_mode="HTML")

        except Exception as e:
            print(f"Ошибка при обработке команды 'Мой брак': {e}")
            await message.reply("❗ Произошла ошибка при выполнении запроса.")

    # Запускаем асинхронно метод для удаления неактивных браков без ожидания его завершения
        #await db.delete_inactive_marriages()

# Определяем метод форматирования длительности брака
def format_timedelta(delta):
    years = delta.days // 365
    months = delta.days % 365 // 30
    days = delta.days % 30
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    duration_str = ""

    if delta.days >= 365:
        duration_str += f"{years} {'год' if years == 1 else 'года' if 2 <= years <= 4 else 'лет'}"
        if days > 0:
            duration_str += f", {days} {'день' if days == 1 else 'дня' if 2 <= days <= 4 else 'дней'}"
        if hours > 0:
            duration_str += f", {hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}"
    elif delta.days >= 30:
        duration_str += f"{months} {'месяц' if months == 1 else 'месяца' if 2 <= months <= 4 else 'месяцев'}"
        if days > 0:
            duration_str += f", {days} {'день' if days == 1 else 'дня' if 2 <= days <= 4 else 'дней'}"
        if hours > 0:
            duration_str += f", {hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}"
    elif delta.days >= 1:
        duration_str += f"{days} {'день' if days == 1 else 'дня' if 2 <= days <= 4 else 'дней'}"
        if hours > 0:
            duration_str += f", {hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}"
    elif delta.seconds >= 3600:
        duration_str += f"{hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}"
        if minutes > 0:
            duration_str += f", {minutes} {'минута' if minutes == 1 else 'минуты' if 2 <= minutes <= 4 else 'минут'}"
    elif delta.seconds >= 60:
        duration_str += f"{minutes} {'минута' if minutes == 1 else 'минуты' if 2 <= minutes <= 4 else 'минут'}"
        if seconds > 0:
            duration_str += f", {seconds} {'секунда' if seconds == 1 else 'секунды' if 2 <= seconds <= 4 else 'секунд'}"
    else:
        duration_str += f"{seconds} {'секунда' if seconds == 1 else 'секунды' if 2 <= seconds <= 4 else 'секунд'}"

    return duration_str


