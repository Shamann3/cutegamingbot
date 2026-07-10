from aiogram import Bot , Dispatcher , types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import bot1 , dp

from aiogram.types import ReplyKeyboardRemove , ReplyKeyboardMarkup , KeyboardButton , InlineKeyboardMarkup , \
    InlineKeyboardButton
from bot.db_create.db import *
import random
import json

from bot.funcs.func import *
from main import *

  # Лучше использовать Redis или SQLite в проде

from aiogram import types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.funcs.help import callbaYTRWEQck_main  # модуль подсказок


@dp.message()
async def game_filter_promo(message: Message):

    if message.text.lower() in ["промокодылист", "промолист", "промокодлист", "листпромокоды", "листпромокод"]:
        promo_list = await db.get_all_promocodes_with_usage()
        if not promo_list:
            await message.reply("❌ <b>Промокоды не найдены.</b>", parse_mode="HTML")
            return

        lines = [ ]
        for idx , row in enumerate(promo_list , start=1):
            promo_code = row [ "promo" ]
            max_count = row [ "count" ]
            used_count = row [ "used_count" ]
            lines.append(f"<b>{idx}. <code>{promo_code}</code> | {used_count}/{max_count}</b>")

        await message.reply("\n".join(lines),parse_mode="HTML")
    if message.text.lower().startswith(("создатьпромо", "создатьпромокод","промосоздать","промокодсоздать")):
        parts = message.text.split()
        user_id = message.from_user.id
        if user_id != 6801702632:
            return
        if len(parts) < 3:
            return await message.reply(
                "⚠️ <b>Неверный формат.</b>\n🛠 Используй: <code>создатьпромо (промокод) (сумма) [макс. использований]</code>",
                parse_mode="HTML"
            )

        promo_code = parts[1]
        try:
            max_price = float(parts[2])
        except ValueError:
            return await message.reply("❌ <b>Неверная сумма. Укажи число.</b>", parse_mode="HTML")

        if max_price <= 0:
            return await message.reply("❌ <b>Сумма должна быть больше нуля.</b>", parse_mode="HTML")

        if len(parts) >= 4:
            try:
                max_count = int(parts[3])
                if max_count <= 0:
                    return await message.reply("❌ <b>Количество использований должно быть больше нуля.</b>", parse_mode="HTML")
            except ValueError:
                return await message.reply("❌ <b>Неверное количество использований. Укажи целое число.</b>", parse_mode="HTML")
        else:
            max_count = 0  # бесконечные использования

        if max_count:
            try:
                max_count = int(max_count)
                if max_count <= 0:
                    return await message.reply("❌ <b>Количество использований должно быть больше нуля.</b>", parse_mode="HTML")
            except ValueError:
                return await message.reply("❌ <b>Неверное количество использований. Укажи целое число.</b>", parse_mode="HTML")

            # Проверка: сумма должна делиться на количество пользователей без остатка
            if max_price % max_count != 0:
                suggested_counts = [i for i in range(max_count - 10, max_count + 11) if i > 0 and max_price % i == 0]
                base = int(max_price // max_count)
                suggested_amounts = [base * max_count, (base + 1) * max_count]

                hints = []
                if suggested_counts:
                    hints.append(
                        "🔁 <b>Попробуй одно из допустимых количеств использований:</b>\n" + "\n".join(
                            [f"• <b>{i} × {int(max_price // i)} кут</b>" for i in suggested_counts[:5]]
                        )
                    )

                hints.append(
                    f"💰 <b>Или измени сумму, чтобы она делилась на {max_count} человек:</b>\n" + "\n".join(
                        [f"• <b>{amt} кут → по {amt // max_count} кут каждому</b>" for amt in suggested_amounts]
                    )
                )

                return await message.reply(
                    f"❌ <b>Сумма {max_price} не может быть равномерно поделена на {max_count} человек.</b>\n\n" + "\n\n".join(hints),
                    parse_mode="HTML"
                )

            price_per_user = int(max_price // max_count)
        else:
            price_per_user = int(max_price)

        # Проверка баланса
        user_id = message.from_user.id
        chat_id = message.chat.id

        current_balance = await db.get_user_balance(user_id)
        chat_balance = await db.get_chat_balance(bot1,chat_id)

        if max_price > chat_balance:
            win_amount_formatted = "{:,.0f}".format(chat_balance).replace(",", ".")
            return await message.reply(
                f"💸 <b>В группе недостаточно средств для создания промокода.</b>\n📉 <b>Доступно: {win_amount_formatted} кут</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # Если промокод уже существует
        existing_promo = await db.get_promocode_by_code(promo_code)
        if existing_promo:
            promo, used, maxcount, priceonone, maxprice, created_at = existing_promo
            win_amount_formatted = "{:,.0f}".format(int(maxprice)).replace("," , ".")
            win_amount_formatted1 = "{:,.0f}".format(int(priceonone)).replace("," , ".")
            win_amount_formatted11 = "{:,.0f}".format(used).replace("," , ".")
            win_amount_formatted111 = "{:,.0f}".format('Бесконечно' if maxcount == 0 else maxcount).replace("," , ".")

            return await message.answer(
                f"⚠️ <b>Промокод '<code>{promo}</code>' уже существует!</b>\n\n"
                f"🍹 <b>Общая сумма : {win_amount_formatted} кут</b>\n"
                f"💰 <b>Получит каждый : {win_amount_formatted1} кут</b>\n"
                f"🏆 <b>Кол-во использований : {win_amount_formatted11}/{win_amount_formatted111}</b>\n"
                f"<b>Создан : {created_at.strftime('%Y-%m-%d %H:%M:%S')}</b>",
                parse_mode="HTML"
            )

        # Всё готово к созданию

        win_amount_formatted2 = "{:,.0f}".format(int(max_price)).replace("," , ".")
        win_amount_formatted12 = "{:,.0f}".format(price_per_user).replace("," , ".")

        win_amount_formatted1112 = "{:,.0f}".format('♾️ Бесконечно' if max_count == 0 else max_count).replace("," , ".")

        text = (
            f"🎁 <b>Новый промокод : <code>{promo_code}</code></b>\n\n"
            f"🍹 <b>Всего будет роздано : {win_amount_formatted2} кут</b>\n"
            f"💰 <b>Каждый получит : {win_amount_formatted12} кут</b>\n"
            f"🏆 <b>Количество использований : {win_amount_formatted1112}</b>\n\n"
        )



        unique_id = str(uuid.uuid4().hex) [ :12 ]  # Укороченный UUID
        promo_data_cache [ unique_id ] = {"promo_code": promo_code , "max_price": max_price , "max_count": max_count}

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [ InlineKeyboardButton(text="❌ Отмена" , callback_data="promo_cancel123xyz") , InlineKeyboardButton(
                    text="✅ Подтвердить" , callback_data=f"promo_confirm123xyz|{unique_id}") ] ])

        await message.reply(text, reply_markup=kb, parse_mode="HTML")


    if message.text.lower().startswith(("промокод","промо")):

        user_id = message.from_user.id
        text = message.text.strip()
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            return
        if not await check_user_name_for_bot(user_id, message.from_user.first_name, message.from_user.last_name):
            emoji = f"<tg-emoji emoji-id='5465143921912846619'>💭</tg-emoji>"
            first_name = await db.get_user_first_name(user_id)
            await message.reply(
                f'<b>{emoji}  Ваш ник должен содержать приписку семьи бота "<code>Cute</code>"\n[ {first_name} <code>Cute</code> ]</b>\n<blockquote><b><i>После обновления имени - активируйте промокод еще раз.</i></b></blockquote>' ,
                parse_mode="HTML" , disable_web_page_preview=True)
            return
        # Проверяем, есть ли данные о бонусах для пользователя
        last_open_time , data_open = await db.get_historygames_times(user_id)
        if last_open_time is None or data_open is None:
            # Если данных нет, сообщаем, что для получения бонуса нужно выиграть в игре
            print(f"Пользователь {user_id} не найден в таблице historygames.")
            button1 = InlineKeyboardButton(text="Играть!", switch_inline_query="Игры", style="default" ,icon_custom_emoji_id="5408935401442267103")
            kb_butt124ons = [ [ button1 ] ]

            buttot = InlineKeyboardMarkup(inline_keyboard=kb_butt124ons)
            await message.reply(
                "<tg-emoji emoji-id='5895583431194054511'>🌟</tg-emoji> <b>Сначала победите противника в любой игре и активировать промокод ещё раз</b>",reply_markup=buttot , parse_mode="HTML")
            return

        promo_code = parts[1].strip().lower()

        promo = await db.get_promocode_by_code(promo_code)
        if not promo:
            return await message.reply("💭 <b>Промокод больше нельзя использовать</b>" , parse_mode="HTML")

        already_used = await db.has_user_used_promo(user_id , promo_code)
        if already_used:
            return await message.reply("💭 <b>Вы уже использовали этот промокод.</b>" , parse_mode="HTML")




        print(f"Время последнего открытия промокода: {last_open_time}, Время окончания промокода: {data_open}")



        price_on_one = float(promo [ "priceonone" ])
        group_chat_id = int(promo [ "chat_id" ])

        # Получаем баланс группы
        group_balance = await db.get_chat_balance(group_chat_id)

        # Проверка: существует ли группа и есть ли у неё баланс
        if group_balance is None:
            return await message.reply(
                "💭 <b>Группа, к которой привязан промокод, не зарегистрирована в базе данных.</b>" , parse_mode="HTML")

        if group_balance < price_on_one:
            return await message.reply(
                "💭 <b>Куты для промокода закончились</b>" , parse_mode="HTML")

        # Обновляем баланс пользователя и группы
        user_balance = await db.get_user_balance(user_id)
        if user_balance is None:
            user_balance = 0  # Если пользователь впервые

        await db.update_user_balance(user_id , user_balance + price_on_one)
        await db.update_chat_balance_minus(group_chat_id , price_on_one)

        await db.add_user_to_promo_users(user_id , promo_code)
        await db.decrement_promo_count_or_delete(promo_code)

        win_amount_formatted = "{:,.0f}".format(int(price_on_one)).replace("," , ".")
        await message.reply(
            f"🌿 <b>Промокод <code>{promo_code}</code> активирован! | + {win_amount_formatted} кут!</b>" ,
            parse_mode="HTML")

    if message.text.lower().startswith(("удалитьпромо","промоудалить","удалитьпромокод","промокодудалить")):

        text = message.text.strip()
        parts = text.split(maxsplit=1)
        user_id = message.from_user.id
        if user_id != 6801702632:
            return
            # Проверка: указан ли промокод после команды
        if len(parts) < 2:
            return await message.reply("❌ <b>Укажите промокод для удаления.</b>" , parse_mode="HTML")

        promo_code = parts [ 1 ].strip()

        # Проверяем наличие промокода
        promo = await db.get_promocode_by_code(promo_code)
        if not promo:
            return await message.reply("❌ <b>Промокод не найден или уже был удалён.</b>" , parse_mode="HTML")

        # Удаляем промокод
        await db.delete_promocode(promo_code)

        return await message.reply(f"✅ <b>Промокод <code>{promo_code}</code> успешно удалён.</b>" , parse_mode="HTML")


    # Обработка отмены
@dp.callback_query(lambda c: c.data == "promo_cancel123xyz")
async def cancel_promo(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != 6801702632:
        return await callback_query.answer("❌ У вас нет прав на создание промокодов." , show_alert=True)
    await callback_query.answer('сообщение удалено')
    await callback_query.message.delete()

# Обработка подтверждения
@dp.callback_query(lambda c: c.data.startswith("promo_confirm123xyz|"))
async def confirm_promo(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != 6801702632:
        return await callback_query.answer("🚫 У вас нет прав на создание промокодов.", show_alert=True)

    chat_id = callback_query.message.chat.id
    try:
        _, data_key = callback_query.data.split("|")

        data = promo_data_cache.get(data_key)
        if not data:
            return await callback_query.answer("❌ Данные не найдены или устарели.", show_alert=True)

        promo_code = data["promo_code"]
        max_price = float(data["max_price"])
        max_count = int(data["max_count"])
        price_per_user = max_price / max_count if max_count else max_price

        await db.add_promocode_to_db(
            promo_code=promo_code,
            max_price=max_price,
            max_count=max_count,
            price_per_user=price_per_user,
            chat_id=chat_id
        )

        win_amount_formatted = "{:,.0f}".format(int(max_price)).replace(",", ".")
        win_amount_formatted1 = "{:,.0f}".format(int(price_per_user)).replace(",", ".")
        win_amount_formatted111 = "♾️ Бесконечно" if max_count == 0 else "{:,.0f}".format(max_count).replace(",", ".")

        await callback_query.message.edit_text(
            f"🍀 <b>Промокод успешно создан!</b>\n\n"
            f"🌿 <b>Промо : <code>{promo_code}</code></b>\n"
            f"🦖 <b>Общая сумма : {win_amount_formatted} кут</b>\n"
            f"🌴 <b>Каждый получит : {win_amount_formatted1} кут</b>\n"
            f"🪴 <b>Кол-во использований : {win_amount_formatted111}</b>",
            parse_mode="HTML"
        )

        # Очистка использованных данных
        promo_data_cache.pop(data_key, None)

    except Exception as e:
        print(f"[ERROR] Ошибка при создании промокода: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при создании промокода.</b>",
            parse_mode="HTML"
        )