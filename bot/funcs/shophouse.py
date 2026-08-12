from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import *

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from bot.db_create.db import *
import math
import json
import os

from bot.funcs.func import *



last_user_id1 = None
last_sell_user_id1 = None
from bot.db_create.pklcode import LazyGameStore
user_message_house = LazyGameStore("user_message_house")
# Глобальная переменная для хранения последнего идентификатора пользователя

@dp.message()
async def shop_house(message: Message):
    from bot.funcs.garden import garden
    await garden(message)
    global last_user_id1  # Объявляем глобальную переменную
    if message.text.lower() in ("Дома","дома","Купить дом","купить дом"):
        user_id = message.from_user.id
        #if user_id == 999884389:
        last_user_id1 = message.from_user.id  # Сохраняем идентификатор пользователя
        keyboard = await generate_house_buttons_with_navigation(last_user_id1)
        sent_house = await message.answer("🏡 Выберите дом для покупки" , reply_markup=keyboard)
        user_message_house [ user_id ] = sent_house.message_id
        print(user_message_house)

    if message.text.lower() in (("Продать дом" , "продать дом")):
        global last_sell_user_id1
        user_id = message.from_user.id
        last_sell_user_id1 = message.from_user.id
        keyboard = await generate_house_buttons_with_navigation1(last_sell_user_id1)
        if keyboard:
            await message.answer("🛒 Выберите дом для продажи" , reply_markup=keyboard)
        else:
            await message.reply("✖️ У вас нет дома для продажи.")



    async def show_user_cars1(message , user_id):
        user_cars = await db.show_user_house(user_id)

        if user_cars:
            car_list = "\n".join([ f"{i + 1}. {car}" for i , car in enumerate(user_cars) ])
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("Посмотреть на дом" , callback_data="show_house_images"))

            await message.reply("Ваше имущество:\n" + car_list , reply_markup=keyboard)
        else:
            await message.reply("✖️ У вас нет дома")

    if message.text.lower() in ("Мой дом" , "мой дом"):
        await show_house_images(message)


async def show_house_images(message):
    user_id = message.from_user.id
    user_cars = await db.show_user_house(user_id)

    if user_cars:
        keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2
        for idx, car in enumerate(user_cars):  # Добавляем счетчик индекса
            if idx < 10:  # Ограничиваем количество кнопок до 10
                keyboard.add(InlineKeyboardButton(car, callback_data=f"view_house_{car}"))  # Добавляем кнопку в строку

        # Отправляем новое сообщение с встроенной клавиатурой
        sent_message = await message.answer(
            text="🕊 Выберите дом для просмотра", reply_markup=keyboard)

        # Возвращаем ID нового сообщения для удаления
        return sent_message.message_id
    else:
        await message.reply(
            text="✖️ У вас нет дома")


CAR_IMAGES_DIR = "house"


@dp.callback_query(lambda c: c.data.startswith('view_house_'))
async def view_house(callback_query: types.CallbackQuery):
    car_name = callback_query.data.split('_')[-1]

    # Создание инлайн клавиатуры с кнопкой "Вернуться"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Вернуться", callback_data="return_to_my_house"))

    image_filename = car_name.replace(" ", "") + ".PNG"
    image_path = os.path.join(CAR_IMAGES_DIR, image_filename)

    if os.path.isfile(image_path):
        # Отправка изображения вместе с сообщением
        with open(image_path, "rb") as image_file:
            await callback_query.answer()  # Ответим на запрос, чтобы убрать тайм-аут

            # Поиск описания машины по её имени в списке car_text
            car_description = None
            for name, description in house_text:
                if name == car_name:
                    car_description = description
                    break

            additional_info = None
            for house in house_catalog:
                if house [ 0 ] == car_name:
                    additional_info = house [ 2 ] if len(house) > 2 else ""
                    break

            garden_info = ""
            user_id = callback_query.from_user.id
            if db.user_has_garden(user_id):
                garden_info = "🌿 У дома есть огород"

            # Проверка наличия описания машины
            if car_description:
                # Получение баланса пользователя
                user_id = callback_query.from_user.id
                balances = await db.get_user_balance(user_id)

                # Определение информации о хранилище
                storage_info = ""
                if balances:
                    balance2, balance3 = balances
                    win_amount_formatted = "{:,.0f}".format(balance2).replace("," , ".")
                    win_amount_formatted1 = "{:,.0f}".format(balance3).replace("," , ".")
                    if balance2 > 0:
                        storage_info += f"\n\n💰 Хранилище\n🎩 {win_amount_formatted} кут"
                    if balance3 > 0:
                        storage_info += f"\n📯 {win_amount_formatted1} ктк"

                # Формирование подписи к изображению с использованием f-строки
                caption = f"🏡 {car_name}\n{car_description}{storage_info}\n🧑🏼‍🌾 Мест для культур : {additional_info}\n{garden_info}"
                await callback_query.message.answer_photo(
                    photo=image_file, caption=caption,  # Название машины и описание (если есть)
                    reply_markup=keyboard)
            else:
                await callback_query.message.answer(
                    text="⚠️ Описание для этого дома не найдено. (обратитесь к создателю бота)")

        # Удаление старого сообщения с кнопками с названиями машин
        await callback_query.message.delete()
    else:
        # Если изображение не найдено, выводим сообщение об ошибке
        await callback_query.message.answer(text="⚠️ Изображение дома не найдено. (обратитесь к создателю бота)")

@dp.callback_query(lambda c: c.data == 'return_to_my_house')
async def return_to_my_house(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_cars = await db.show_user_house(user_id)

    if user_cars:
        keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2
        for idx, car in enumerate(user_cars):  # Добавляем счетчик индекса
            if idx < 10:  # Ограничиваем количество кнопок до 10
                keyboard.add(InlineKeyboardButton(car, callback_data=f"view_house_{car}"))  # Добавляем кнопку в строку

        # Отправляем новое сообщение с встроенной клавиатурой
        sent_message = await callback_query.message.answer(
            text="🕊 Выберите дом для просмотра", reply_markup=keyboard)

        # Удаляем старое сообщение с кнопками
        await callback_query.message.delete()
    else:
        await callback_query.message.answer(
            text="✖️ У вас нет дома")



async def generate_house_buttons_with_navigation(user_id):
    page_number = 1
    return await generate_house_buttons(page_number , user_id)

@dp.callback_query(lambda c: c.data.startswith(('prev_page_' , 'next_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    callback_data_parts = callback_query.data.split('_')
    if len(callback_data_parts) == 3:
        _ , direction , page_number = callback_data_parts
        if page_number.isdigit():
            page_number = int(page_number)
            if direction == 'next':
                page_number += 1
            elif direction == 'prev':
                page_number -= 1
            keyboard = await generate_house_buttons(page_number , user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Некорректный формат данных")





@dp.callback_query(lambda c: c.data.startswith(('prev_page_' , 'next_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    callback_data_parts = callback_query.data.split('_')
    if len(callback_data_parts) == 3:
        _, direction, page_number = callback_data_parts
        if page_number.isdigit():
            page_number = int(page_number)
            if direction == 'next':
                page_number += 1
            elif direction == 'prev':
                page_number -= 1
            keyboard = await generate_house_buttons12(page_number , user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Некорректный формат данных")


# Функция для генерации кнопок перелистывания страниц
async def generate_navigation_buttons(page_number):
    navigation_buttons = []

    if page_number == 1 and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number + 1}")
        )
    elif page_number == num_pages and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number - 1}")
        )
    else:
        row_buttons = []
        if page_number > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number - 1}"))
        if page_number < num_pages:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons


async def generate_house_buttons12(page_number, user_id):
    user_cars = await db.show_user_house(user_id)
    global num_pages  # Делаем переменную num_pages глобальной
    num_pages = (len(user_cars) + 9) // 10
    start_index = (page_number - 1) * 10
    end_index = min(page_number * 10, len(user_cars))
    cars_on_page = user_cars[start_index:end_index]

    keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2

    for car in cars_on_page:
        keyboard.add(InlineKeyboardButton(car, callback_data=f"view_house_{car}"))

    navigation_buttons = await generate_navigation_buttons(page_number)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
        keyboard.add(InlineKeyboardButton(text="❌", callback_data="close3412341234123412"))

    return keyboard









@dp.callback_query(lambda c: c.data.startswith(('prev_page_' , 'next_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    callback_data_parts = callback_query.data.split('_')
    if len(callback_data_parts) == 3:
        _, direction, page_number = callback_data_parts
        if page_number.isdigit():
            page_number = int(page_number)
            if direction == 'next':
                page_number += 1
            elif direction == 'prev':
                page_number -= 1
            keyboard = await generate_house_buttons(page_number , user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Некорректный формат данных")


# Функция для генерации кнопок перелистывания страниц
async def generate_navigation_buttons(page_number, user_id):
    global last_user_id  # Объявляем, что будем использовать глобальную переменную last_user_id

    # Проверяем, совпадает ли идентификатор пользователя с последним пользователем
    if last_user_id1 != user_id:
        print('124521512124152151215')  # Отправляем сообщение об ошибке через объект bot
          # Если идентификаторы не совпадают, возвращаем пустой список кнопок

    navigation_buttons = []  # Создаем список для хранения кнопок навигации

    if page_number == 1 and len(house_catalog) > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number + 1}")
        )
    elif page_number == (len(house_catalog) // 10) + 1 and len(house_catalog) > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number - 1}")
        )
    else:
        row_buttons = []
        if page_number > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number - 1}"))
        if len(house_catalog) > page_number * 10:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons

# Функция для генерации кнопок перелистывания страниц и кнопок для покупки машин
async def generate_house_buttons(page_number, user_id):
    start_index = (page_number - 1) * 10
    end_index = min(page_number * 10, len(house_catalog))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, house in enumerate(house_catalog[start_index:end_index], start=start_index + 1):
        house_name = house[0]
        price = house[1]
        formatted_win_amount = "{:,.0f}".format(price).replace(',' , '.')

        keyboard.add(types.InlineKeyboardButton(text=f"{house_name} - {formatted_win_amount} кут", callback_data=f"buy_house_{i}"))



    # Добавляем кнопку "Закрыть"


    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_navigation_buttons(page_number,user_id)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
        keyboard.add(types.InlineKeyboardButton(text="❌" , callback_data="close1"))

    return keyboard




# Функция для генерации кнопок перелистывания страниц и кнопок для покупки машин
async def generate_house_buttons_with_navigation(user_id):
    page_number = 1
    return await generate_house_buttons(page_number, user_id)






@dp.callback_query(lambda c: c.data == 'close1')
async def process_close_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == last_user_id1:
        await callback_query.answer('Магазин с домами удален')
        await callback_query.message.delete()
    else:
        await callback_query.answer("Доступ запрещен.")


@dp.callback_query(lambda c: c.data.startswith('buy_house_'))
async def process_callback(callback_query: types.CallbackQuery):
    global last_user_id1
    if callback_query.from_user.id == last_user_id1:
        user_id = callback_query.from_user.id
        callback_data_parts = callback_query.data.split('_')
        if len(callback_data_parts) == 3:
            _ , _ , index = callback_data_parts
            if index.isdigit():
                index = int(index)
                if 0 < index <= len(house_catalog):
                    house_name , price , *_ = house_catalog [ index - 1 ]  # Извлекаем только первые два элемента

                    car_inventory_count = db.get_user_house_count(user_id)

                    if car_inventory_count >= 1:
                        print("Уже есть дом")
                        await callback_query.answer("💲 Можно купить только 1 дом" , show_alert=True)
                        return

                    # Удаляем сообщение о магазине машин
                    await callback_query.message.delete()

                    keyboard = types.InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        types.InlineKeyboardButton("❌" , callback_data="cancel_house") ,
                        types.InlineKeyboardButton("✅" , callback_data=f"confirm_house_{house_name}"))

                    # Отправляем изображение машины
                    win_amount_formatted = "{:,.0f}".format(price).replace("," , ".")
                    image_filename = house_name.replace(" " , "") + ".PNG"
                    image_path = os.path.join(CAR_IMAGES_DIR , image_filename)
                    if os.path.isfile(image_path):
                        # Отправляем изображение вместе с сообщением
                        with open(image_path , "rb") as image_file:
                            await callback_query.answer()  # Ответим на запрос, чтобы убрать тайм-аут
                            await callback_query.message.answer_photo(
                                photo=image_file , caption=f"{house_name} - {win_amount_formatted} кут" ,
                                # Название дома и цена в качестве комментария
                                reply_markup=keyboard)
                    else:
                        print(f"Ошибка: Файл изображения дома не найден: {image_filename}")
                else:
                    print("Ошибка: Выбранного дома не существует")
                    await callback_query.answer("Выбранного дома не существует")
            else:
                print(f"Ошибка: Некорректный формат индекса: {index}")
                await callback_query.answer("Некорректный формат данных")
        else:
            print(f"Ошибка: Некорректный формат данных: {callback_data_parts}")
            await callback_query.answer("Некорректный формат данных")
    else:
        await callback_query.answer("Сообщение вызвано для другого пользователя")

    await asyncio.sleep(3)  # Добавляем задержку в 3 секунды перед следующей покупкой

async def show_car_shop(message: Message):
    user_id = message.from_user.id
    keyboard = await generate_house_buttons_with_navigation(user_id)
    await message.answer("🏡 Выберите дом для покупки" , reply_markup=keyboard)
@dp.callback_query(lambda c: c.data == 'cancel_house')
async def cancel_buy_callback(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    # Изменяем сообщение с выбором на сообщение с магазином машин
    await show_car_shop(callback_query.message)


@dp.callback_query(lambda c: c.data.startswith('confirm_house_'))
async def confirm_buy_callback(callback_query: types.CallbackQuery):
    car_name = callback_query.data.split('_')[-1]

    # Находим цену для car_name в house_catalog
    price = 0  # По умолчанию устанавливаем цену 0
    for name, car_price, *_ in house_catalog:  # Извлекаем только название и цену
        if name.strip() == car_name.strip():
            price = car_price
            break

    user_id = callback_query.from_user.id
    current_balance = await db.get_user_balance(user_id)

    if current_balance >= price:
        new_balance = current_balance - price

        success, message = await db.update_user_balance(user_id, new_balance)
        if success:
            success, message = db.add_house_to_inventory(user_id, car_name)
            if success:
                return_button = types.InlineKeyboardButton(text="Вернуться", callback_data="return_to_buy_menu")


                return_button = InlineKeyboardMarkup(inline_keyboard=[ [ return_button ] ])
                await callback_query.message.answer(f"✅ Вы успешно купили {car_name}", reply_markup=return_button)
                await callback_query.answer(f"Успешная покупка {car_name}")
                await callback_query.message.delete()
            else:
                print(f"Ошибка при добавлении дома в инвентарь: {message}")
                await callback_query.answer(f"Ошибка: {message}")
        else:
            print(f"Ошибка при обновлении баланса: {message}")
            await callback_query.answer(f"Ошибка: {message}")
    else:
        print("Ошибка: У вас недостаточно средств")
        await callback_query.answer("Недостаточно средств")


@dp.callback_query(lambda c: c.data == 'return_to_buy_menu')
async def return_to_buy_cars(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    page_number = 1  # Assuming page number 1 for now
    keyboard = await generate_house_buttons(page_number, user_id)
    await callback_query.message.edit_text("🏡 Выберите дом для покупки", reply_markup=keyboard)


async def generate_house_buttons1(page_number, user_cars):
    start_index = (page_number - 1) * 10
    end_index = min(page_number * 10, len(user_cars))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, car_name in enumerate(user_cars[start_index:end_index], start=start_index + 1):
        keyboard.add(types.InlineKeyboardButton(text=f"Продать{car_name}", callback_data=f"sell_house_{car_name}"))

    # Добавляем кнопку "Закрыть"
    keyboard.add(types.InlineKeyboardButton(text="❌", callback_data="close3412341234123412"))

    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_user_navigation_buttons1(page_number, len(user_cars))
    if navigation_buttons:
        keyboard.row(*navigation_buttons)

    return keyboard





async def generate_user_navigation_buttons1(page_number, total_cars):
    navigation_buttons = []

    if page_number == 1 and total_cars > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"user_next_page_{page_number + 1}")
        )
    elif page_number == (total_cars // 10) + 1 and total_cars > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"user_prev_page_{page_number - 1}")
        )
    else:
        row_buttons = []
        if page_number > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"user_prev_page_{page_number - 1}"))
        if total_cars > page_number * 10:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"user_next_page_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons


@dp.callback_query(lambda c: c.data.startswith(('user_prev_page_', 'user_next_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    callback_data_parts = callback_query.data.split('_')
    print("Начало обработки callback'а...")
    print("User ID:", user_id)
    print("Callback data parts:", callback_data_parts)
    if len(callback_data_parts) == 4:
        _, direction, _, page_number = callback_data_parts
        if page_number.isdigit():
            page_number = int(page_number)
            if direction == 'next':
                page_number += 1
            elif direction == 'prev':
                page_number -= 1
            keyboard = await generate_house_buttons_with_navigation1(user_id, page_number)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Ошибка: Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Ошибка: Некорректный формат данных")


async def generate_house_buttons_with_navigation1(user_id, page_number=1):  # Добавлен аргумент по умолчанию для page_number
    # Получаем список машин пользователя
    user_cars = await db.show_user_house(user_id)

    # Если у пользователя нет машин, возвращаем сообщение об этом
    if not user_cars:
        return types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton(text="✖️ У вас нет дома", callback_data="dummy")
        )

    # Определяем количество машин пользователя
    total_cars = len(user_cars)

    # Генерируем кнопки для текущей страницы
    start_index = (page_number - 1) * 10
    end_index = min(page_number * 10, len(user_cars))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, car_name in enumerate(user_cars[start_index:end_index], start=start_index + 1):
        keyboard.add(types.InlineKeyboardButton(text=f"Продать {car_name}", callback_data=f"sell_house_{car_name}"))

    # Добавляем кнопку "Закрыть"


    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_user_navigation_buttons1(page_number, total_cars)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
    keyboard.add(types.InlineKeyboardButton(text="❌" , callback_data="close3412341234123412"))

    return keyboard


@dp.callback_query(lambda c: c.data.startswith('confirmhouse_sell_'))
async def confirm_sell_callback(callback_query: types.CallbackQuery):
    car_name = callback_query.data.split('_')[2]

    # Получаем user_id и остальные данные из контекста callback'а
    user_id = callback_query.from_user.id

    # Проверяем, совпадает ли пользователь, вызвавший функцию, с пользователем, который вызвал последнюю команду на продажу дома
    if user_id != last_sell_user_id1:
        await callback_query.answer("Вы не можете продать дом другого пользователя.")
        return

    # Получаем официальную цену дома из списка house_catalog
    for name, price, *_ in house_catalog:  # Извлекаем только название и цену
        if name.strip().lower() == car_name.strip().lower():
            sale_price = price
            break
    else:
        print(f"Ошибка: Официальная цена для {car_name} не найдена.")
        return

    # Рассчитываем цену со скидкой
    sale_price_discounted = int(sale_price * 0.85)

    # Получаем данные о балансе пользователя
    balance2, balance3 = await db.get_user_balances(user_id)

    # Проверяем наличие сумм в balance2 и balance3 и добавляем их к цене со скидкой
    if balance2:
        sale_price_discounted += balance2

    # Проверяем, если есть значение в balance3
    if balance3:
        # Получаем количество штук в balance3 и добавляем к sale_price_discounted
        sale_price_discounted += balance3 * sellktkhouse

    # Выполняем продажу дома и обновляем баланс пользователя
    success, message = await db.sell_house(user_id, car_name, sale_price_discounted)
    if success:
        db.reset_user_balances(user_id)
        # Форматируем цену продажи
        formatted_sale_price = "{:,.0f}".format(sale_price_discounted).replace(',', '.')
        # Отправляем уведомление о успешной продаже
        await callback_query.answer("✔️ Успешная продажа")
        # Создаем инлайн-кнопку "вернуться"
        return_button = types.InlineKeyboardButton(text="Вернуться", callback_data="return_to_sellhouse_menu")
        # Создаем клавиатуру с одной кнопкой

        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ return_button ] ])
        await callback_query.message.answer(
            f"✅ {car_name} был продан за <b>{formatted_sale_price}</b> кут",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        # Удаляем сообщение после продажи
        await callback_query.message.delete()
    else:
        # Отправляем сообщение об ошибке в случае неудачной продажи
        await callback_query.answer(f"Ошибка: {message}")

@dp.callback_query(lambda c: c.data.startswith('sell_house_'))
async def sell_car_callback(callback_query: types.CallbackQuery):
    global formatted_sale_price
    user_id = callback_query.from_user.id
    # Проверяем, совпадает ли пользователь, который вызвал продажу, с текущим пользователем
    if user_id != last_sell_user_id1:
        await callback_query.answer("Вы не можете продавать дома других пользователей.")
        return

    car_name = callback_query.data.split('_')[2]  # Извлекаем имя дома из callback_data
    print(f"Попытка продажи дома с именем: '{car_name}'")

    # Получаем список домов пользователя
    user_cars = await db.show_user_house(user_id)

    # Проверяем, существует ли указанное имя дома в списке user_cars
    if car_name in user_cars:
        # Получаем официальную цену дома из списка house_catalog
        for name, price, *_ in house_catalog:  # Извлекаем только название и цену
            if name.strip().lower() == car_name.strip().lower():
                sale_price = price
                break
        else:
            print(f"Ошибка: Официальная цена для {car_name} не найдена.")
            return

        sale_price_discounted = int(sale_price * 0.85)

        # Получаем данные о балансе пользователя
        balance2, balance3 = await db.get_user_balances(user_id)

        # Проверяем наличие сумм в balance2 и balance3 и добавляем их к цене со скидкой
        if balance2:
            sale_price_discounted += balance2

        # Проверяем, если есть значение в balance3
        if balance3:
            # Получаем количество штук в balance3 и добавляем к sale_price_discounted
            sale_price_discounted += balance3 * sellktkhouse

        # Создаем сообщение с выбором "вы уверены продать дом (название дома)" и кнопками "продать" и "отменить"
        formatted_sale_price = "{:,.0f}".format(sale_price_discounted).replace(',', '.')
        confirmation_message = f"💫 Продажа дома\n💲 {car_name} за <b>{formatted_sale_price} кут?</b>"
        confirmation_keyboard = types.InlineKeyboardMarkup(row_width=2)
        confirmation_keyboard.add(
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancelhouse_sell"),
            types.InlineKeyboardButton("✅ Продать", callback_data=f"confirmhouse_sell_{car_name}")
        )

        # Получаем путь к изображению дома
        image_filename = car_name.replace(" ", "") + ".PNG"
        image_path = os.path.join(CAR_IMAGES_DIR, image_filename)

        if os.path.isfile(image_path):
            # Удаляем старое сообщение
            await callback_query.message.delete()

            # Отправляем изображение вместе с сообщением о продаже
            await callback_query.message.answer_photo(
                photo=open(image_path, "rb"),
                caption=confirmation_message,
                reply_markup=confirmation_keyboard,
                parse_mode="HTML"
            )
        else:
            print(f"Ошибка: Файл изображения дома не найден: {image_filename}")
            await callback_query.answer("Файл изображения дома не найден")

    else:
        print(f"Ошибка: Дом '{car_name}' не найден в списке домов пользователя.")
        await callback_query.answer("Дом не найден.")

# Обработчик нажатия кнопки "Продать"



@dp.callback_query(lambda c: c.data == 'return_to_sellhouse_menu')
async def return_to_sell_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_cars = await db.show_user_house(user_id)
    await callback_query.message.delete()
    if user_cars:
        keyboard = await generate_house_buttons_with_navigation1(user_id)
        await callback_query.message.answer("✨ Выберите дом для продажи:", reply_markup=keyboard)
    else:
        await callback_query.message.answer("✖️ У вас нет дома для продажи.")

# Обработчик кнопки "Отменить" при продаже машины
@dp.callback_query(lambda c: c.data == 'cancelhouse_sell')
async def cancel_sell_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != last_sell_user_id1:
        await callback_query.answer("Вы не можете отменить продажу дома другого пользователя.")
        return
    keyboard = await generate_house_buttons_with_navigation1(user_id)
    await callback_query.message.answer("✨ Выберите дом для продажи:", reply_markup=keyboard)
    await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == 'close3412341234123412')
async def process_close_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == last_sell_user_id1:
        await callback_query.answer('Список домов для продажи удален')
        await callback_query.message.delete()
    else:
        await callback_query.answer("Доступ запрещен.")



