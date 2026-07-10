from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import *

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from bot.db_create.db import *
from bot.config.config import *
import math
import json
import os

from main import db




last_user_id3 = None
last_sell_user_id3 = None# Глобальная переменная для хранения последнего идентификатора пользователя


@dp.message()
async def shop_gelicopter(message: Message):
    global last_user_id3  # Объявляем глобальную переменную
    if message.text.lower() in ("Вертолеты","вертолеты","Купить вертолеты","купить вертолеты","купить вертолет","Купить вертолет","купить вертолёт","Купить вертолёт"):
        last_user_id3 = message.from_user.id  # Сохраняем идентификатор пользователя
        keyboard = await generate_gelicopter_buttons_with_navigation(last_user_id3)
        await message.answer("🚁 Выберите вертолет для покупки", reply_markup=keyboard)

    if message.text.lower() in (("Продать вертолет" , "продать вертолет","Продажа вертолета","продажа вертолета","Продажа вертолёта","продажа вертолёта")):
        global last_sell_user_id3
        user_id = message.from_user.id
        last_sell_user_id3 = message.from_user.id
        keyboard = await generate_gelicopter_buttons_with_navigation1(last_sell_user_id3)
        if keyboard:
            await message.answer("Выберите вертолет для продажи" , reply_markup=keyboard)
        else:
            await message.answer("✖️ У вас нет вертолетов для продажи.")



    async def show_user_gelicopter1(message , user_id):
        user_cars = await db.show_user_gelicopter(user_id)

        if user_cars:
            car_list = "\n".join([ f"{i + 1}. {car}" for i , car in enumerate(user_cars) ])
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("Посмотреть картинки" , callback_data="show_gelicopter_images"))

            await message.answer("Ваше имущество:\n" + car_list , reply_markup=keyboard)
        else:
            await message.answer("У вас нет вертоелетов в имуществе.")

    if message.text.lower() in ("Мой вертолет" , "мой вертолет","мои вертолеты","Мои вертолеты","мои вертолёты","Мои вертолёты"):
        await show_gelicopter_images(message)


async def show_gelicopter_images(message):
    user_id = message.from_user.id
    user_cars = await db.show_user_gelicopter(user_id)

    if user_cars:
        keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2
        for idx, car in enumerate(user_cars):  # Добавляем счетчик индекса
            if idx < 10:  # Ограничиваем количество кнопок до 10
                keyboard.add(InlineKeyboardButton(car, callback_data=f"view_gelicopter_{car}"))  # Добавляем кнопку в строку

        # Отправляем новое сообщение с встроенной клавиатурой
        sent_message = await message.answer(
            text="Выберите вертолет для просмотра", reply_markup=keyboard)

        # Возвращаем ID нового сообщения для удаления
        return sent_message.message_id
    else:
        await message.answer(
            text="У вас нет вертолетов")


CAR_IMAGES_DIR = "gelicopter"


@dp.callback_query(lambda c: c.data.startswith('view_gelicopter_'))
async def view_gelicopter(callback_query: types.CallbackQuery):

    car_name = callback_query.data.split('_') [ -1 ]

    # Создание инлайн клавиатуры с кнопкой "Вернуться"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Вернуться" , callback_data="return_to_my_gelicopter"))

    image_filename = car_name.replace(" " , "") + ".PNG"
    image_path = os.path.join(CAR_IMAGES_DIR , image_filename)

    if os.path.isfile(image_path):
        # Отправка изображения вместе с сообщением
        with open(image_path , "rb") as image_file:
            await callback_query.answer()  # Ответим на запрос, чтобы убрать тайм-аут

            # Поиск описания машины по её имени в списке car_text
            car_description = None
            for name , description in gelicopter_text:
                if name == car_name:
                    car_description = description
                    break

            car_price = None
            for car_tuple in gelicopter_catalog:
                if car_tuple [ 0 ] == car_name:
                    car_price = car_tuple [ 1 ]
                    break

            # Формирование подписи к изображению с использованием f-строки



            # Проверка наличия описания машины
            if car_price is not None:
                formatted_price = "{:,.0f}".format(car_price).replace(',' , '.')
                caption = f"{car_name}\n\n💰 Стоимость: {formatted_price}\n{car_description}"
            else:
                caption = f"{car_name}\n\nЦена не найдена\n{car_description}"

            await callback_query.message.answer_photo(
                photo=image_file , caption=caption ,  # Название машины, описание и цена (если есть)
                reply_markup=keyboard)

        # Удаление старого сообщения с кнопками с названиями машин
        await callback_query.message.delete()
    else:
        # Если изображение не найдено, выводим сообщение об ошибке
        await callback_query.message.answer(text="Изображение вертолета не найдено.")


@dp.callback_query(lambda c: c.data == 'return_to_my_gelicopter')
async def return_to_my_gelicopter(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    user_cars = await db.show_user_gelicopter(user_id)

    if user_cars:
        keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2
        for idx, car in enumerate(user_cars):  # Добавляем счетчик индекса
            if idx < 10:  # Ограничиваем количество кнопок до 10
                keyboard.add(InlineKeyboardButton(car, callback_data=f"view_gelicopter_{car}"))  # Добавляем кнопку в строку

        # Отправляем новое сообщение с встроенной клавиатурой
        sent_message = await callback_query.message.answer(
            text="Выберите вертолет для просмотра", reply_markup=keyboard)

        # Удаляем старое сообщение с кнопками
        await callback_query.message.delete()
    else:
        await callback_query.message.answer(
            text="У вас нет вертолетов")



async def generate_gelicopter_buttons_with_navigation(user_id):
    page_number1 = 1
    return await generate_gelicopter_buttons(page_number1 , user_id)

@dp.callback_query(lambda c: c.data.startswith(('prev_page_' , 'next_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):

    print('1255')
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
            keyboard = await generate_gelicopter_buttons(page_number , user_id)
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
            keyboard = await generate_gelicopter_buttons12(page_number , user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Некорректный формат данных")


# Функция для генерации кнопок перелистывания страниц
async def generate_navigation_buttons(page_number1):
    navigation_buttons = []

    if page_number1 == 1 and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number1 + 1}")
        )
    elif page_number1 == num_pages and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number1 - 1}")
        )
    else:
        row_buttons = []
        if page_number1 > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"prev_page_{page_number1 - 1}"))
        if page_number1 < num_pages:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"next_page_{page_number1 + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons


async def generate_gelicopter_buttons12(page_number1, user_id):
    user_cars = await db.show_user_gelicopter(user_id)
    global num_pages  # Делаем переменную num_pages глобальной
    num_pages = (len(user_cars) + 9) // 10
    start_index = (page_number1 - 1) * 10
    end_index = min(page_number1 * 10, len(user_cars))
    cars_on_page = user_cars[start_index:end_index]

    keyboard = InlineKeyboardMarkup(row_width=2)  # Изменили ширину строки на 2

    for car in cars_on_page:
        keyboard.add(InlineKeyboardButton(car, callback_data=f"view_gelicopter_{car}"))

    navigation_buttons = await generate_navigation_buttons1(page_number1,user_id)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
        keyboard.add(InlineKeyboardButton(text="❌", callback_data="close123123"))

    return keyboard









@dp.callback_query(lambda c: c.data.startswith(('prev1_page_' , 'next1_page_')))
async def process_page_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    callback_data_parts = callback_query.data.split('_')
    if len(callback_data_parts) == 3:
        _, direction, page_number1 = callback_data_parts
        if page_number1.isdigit():
            page_number1 = int(page_number1)
            if direction == 'next':
                page_number1 += 1
            elif direction == 'prev':
                page_number1 -= 1
            keyboard = await generate_gelicopter_buttons(page_number1 , user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Некорректный формат данных")


# Функция для генерации кнопок перелистывания страниц
async def generate_navigation_buttons1(page_number1, user_id):
    global last_user_id3  # Объявляем, что будем использовать глобальную переменную last_user_id

    # Проверяем, совпадает ли идентификатор пользователя с последним пользователем
    if last_user_id3 != user_id:
        print('124521512112124124')  # Отправляем сообщение об ошибке через объект bot
          # Если идентификаторы не совпадают, возвращаем пустой список кнопок

    navigation_buttons1 = []  # Создаем список для хранения кнопок навигации

    if page_number1 == 1 and len(gelicopter_catalog) > 10:
        navigation_buttons1.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"next1_page_{page_number1 + 1}")
        )
    elif page_number1 == (len(gelicopter_catalog) // 10) + 1 and len(gelicopter_catalog) > 10:
        navigation_buttons1.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"prev1_page_{page_number1 - 1}")
        )
    else:
        row_buttons = []
        if page_number1 > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"prev1_page_{page_number1 - 1}"))
        if len(gelicopter_catalog) > page_number1 * 10:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"next1_page_{page_number1 + 1}"))
        navigation_buttons1.extend(row_buttons)

    return navigation_buttons1


# Функция для генерации кнопок перелистывания страниц и кнопок для покупки машин
async def generate_gelicopter_buttons(page_number1, user_id):
    start_index = (page_number1 - 1) * 10
    end_index = min(page_number1 * 10, len(gelicopter_catalog))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, (car_name, price) in enumerate(gelicopter_catalog[start_index:end_index], start=start_index + 1):
        formatted_win_amount = "{:,.0f}".format(price).replace(',' , '.')

        keyboard.add(types.InlineKeyboardButton(text=f"{car_name} - {formatted_win_amount} кут", callback_data=f"buy_gelicopter_{i}"))

    # Добавляем кнопку "Закрыть"


    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_navigation_buttons1(page_number1,user_id)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
        keyboard.add(types.InlineKeyboardButton(text="❌" , callback_data="close12"))

    return keyboard




# Функция для генерации кнопок перелистывания страниц и кнопок для покупки машин
async def generate_gelicopter_buttons_with_navigation1(user_id):
    page_number = 1
    print('_++')
    return await generate_gelicopter_buttons(page_number, user_id)






@dp.callback_query(lambda c: c.data == 'close12')
async def process_close_callback(callback_query: types.CallbackQuery):

    if callback_query.from_user.id == last_user_id3:
        await callback_query.answer('Магазин с машинами удален')
        await callback_query.message.delete()
    else:
        await callback_query.answer("Доступ запрещен.")


@dp.callback_query(lambda c: c.data.startswith('buy_gelicopter_'))
async def process_callback(callback_query: types.CallbackQuery):

    global last_user_id3
    if callback_query.from_user.id == last_user_id3:
        user_id = callback_query.from_user.id
        callback_data_parts = callback_query.data.split('_')
        if len(callback_data_parts) == 3:
            _, _, index = callback_data_parts
            if index.isdigit():
                index = int(index)
                if 0 < index <= len(gelicopter_catalog):
                    car_name, price = gelicopter_catalog[index - 1]
                    car_inventory_count = db.get_user_gelicopter_count(user_id)

                    if car_inventory_count >= 5:
                        print("Уже 10 машин в инвентаре")
                        await callback_query.answer("Вы купили максимальное количество машин (10)")
                        return

                    # Удаляем сообщение о магазине машин
                    await callback_query.message.delete()

                    keyboard = InlineKeyboardMarkup(row_width=2)
                    keyboard.add(InlineKeyboardButton("❌", callback_data="cancel_gelicopter"),
                                    InlineKeyboardButton("✅", callback_data=f"confirm_gelicopter_{car_name}"))

                    # Отправляем изображение машины
                    win_amount_formatted = "{:,.0f}".format(price).replace("," , ".")
                    image_filename = car_name.replace(" ", "") + ".PNG"
                    image_path = os.path.join(CAR_IMAGES_DIR, image_filename)
                    if os.path.isfile(image_path):
                        # Отправляем изображение вместе с сообщением
                        with open(image_path, "rb") as image_file:
                            await callback_query.answer()  # Ответим на запрос, чтобы убрать тайм-аут
                            await callback_query.message.answer_photo(
                                photo=image_file, caption=f"{car_name} - {win_amount_formatted} кут",  # Название машины и цена в качестве комментария
                                reply_markup=keyboard)
                    else:
                        print(f"Ошибка: Файл изображения машины не найден: {image_filename}")
                else:
                    print("Ошибка: Выбранной машины не существует")
                    await callback_query.answer("Выбранного вертолета не существует")
            else:
                print(f"Ошибка: Некорректный формат индекса: {index}")
                await callback_query.answer("Некорректный формат данных")
        else:
            print(f"Ошибка: Некорректный формат данных: {callback_data_parts}")
            await callback_query.answer("Некорректный формат данных")
    else:
        await callback_query.answer("Сообщение вызвано для другого пользователя")

    await asyncio.sleep(3)  # Добавляем задержку в 3 секунды перед следующей покупкой

async def show_gelicopter_shop(message: Message):
    user_id = message.from_user.id
    keyboard = await generate_gelicopter_buttons_with_navigation(user_id)
    await message.answer("🚁 Выберите вертолет для покупки" , reply_markup=keyboard)
@dp.callback_query(lambda c: c.data == 'cancel_gelicopter')
async def cancel_buy_callback(callback_query: types.CallbackQuery):

    await callback_query.message.delete()
    # Изменяем сообщение с выбором на сообщение с магазином машин
    await show_gelicopter_shop(callback_query.message)


@dp.callback_query(lambda c: c.data.startswith('confirm_gelicopter_'))
async def confirm_buy_callback(callback_query: types.CallbackQuery):

    car_name = callback_query.data.split('_')[-1]


    # Находим цену для car_name в car_catalog
    price = 0  # По умолчанию устанавливаем цену 0
    for name, car_price in gelicopter_catalog:
        if name == car_name:
            price = car_price
            break

    user_id = callback_query.from_user.id
    current_balance = await db.get_user_balance(user_id)

    if current_balance >= price:
        new_balance = current_balance - price

        success, message = await db.update_user_balance(user_id, new_balance)
        if success:
            success, message = await db.add_gelicopter_to_inventory(user_id, car_name)
            if success:
                return_button = InlineKeyboardButton("Вернуться", callback_data="return_to_gelicopter_menu")
                keyboard = InlineKeyboardMarkup().add(return_button)
                await callback_query.message.answer(f"✅ Вы успешно купили{car_name}", reply_markup=keyboard)
                await callback_query.answer(f"Вы успешно купили{car_name}")
                await callback_query.message.delete()
            else:
                print(f"Ошибка при добавлении машины в инвентарь: {message}")
                await callback_query.answer(f"Ошибка: {message}")
        else:
            print(f"Ошибка при обновлении баланса: {message}")
            await callback_query.answer(f"Ошибка: {message}")
    else:
        print("Ошибка: У вас недостаточно средств")
        await callback_query.answer("У вас недостаточно средств")


@dp.callback_query(lambda c: c.data == 'return_to_gelicopter_menu')
async def return_to_buy_gelicopter(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    page_number = 1  # Assuming page number 1 for now
    keyboard = await generate_gelicopter_buttons(page_number, user_id)
    await callback_query.message.edit_text("🚁 Выберите вертолет для покупки", reply_markup=keyboard)


async def generate_gelicopter_buttons1(page_number1, user_cars):
    start_index = (page_number1 - 1) * 10
    end_index = min(page_number1 * 10, len(user_cars))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, car_name in enumerate(user_cars[start_index:end_index], start=start_index + 1):
        keyboard.add(types.InlineKeyboardButton(text=f"Продать {car_name}", callback_data=f"sell_gelicopter_{car_name}"))

    # Добавляем кнопку "Закрыть"
    keyboard.add(types.InlineKeyboardButton(text="❌", callback_data="close"))

    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_user_navigation_buttons1(page_number1, len(user_cars))
    if navigation_buttons:
        keyboard.row(*navigation_buttons)

    return keyboard





async def generate_user_navigation_buttons1(page_number1, total_cars):
    navigation_buttons = []

    if page_number1 == 1 and total_cars > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜", callback_data=f"user_next1_page_{page_number1 + 1}")
        )
    elif page_number1 == (total_cars // 10) + 1 and total_cars > 10:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙", callback_data=f"user_prev1_page_{page_number1 - 1}")
        )
    else:
        row_buttons = []
        if page_number1 > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙", callback_data=f"user_prev1_page_{page_number1 - 1}"))
        if total_cars > page_number1 * 10:
            row_buttons.append(types.InlineKeyboardButton(text="🔜", callback_data=f"user_next1_page_{page_number1 + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons


@dp.callback_query(lambda c: c.data.startswith(('user_prev1_page_', 'user_next1_page_')))
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
            keyboard = await generate_gelicopter_buttons_with_navigation1(user_id, page_number)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        else:
            print("Ошибка: Некорректный формат номера страницы")
            await callback_query.answer("Ошибка: Некорректный формат номера страницы")
    else:
        print("Ошибка: Некорректный формат данных")
        await callback_query.answer("Ошибка: Некорректный формат данных")


async def generate_gelicopter_buttons_with_navigation1(user_id, page_number1=1):  # Добавлен аргумент по умолчанию для page_number
    # Получаем список машин пользователя
    user_cars = await db.show_user_gelicopter(user_id)

    # Если у пользователя нет машин, возвращаем сообщение об этом
    if not user_cars:
        return types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton(text="У вас нет вертолета", callback_data="dummy")
        )

    # Определяем количество машин пользователя
    total_cars = len(user_cars)

    # Генерируем кнопки для текущей страницы
    start_index = (page_number1 - 1) * 10
    end_index = min(page_number1 * 10, len(user_cars))

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, car_name in enumerate(user_cars[start_index:end_index], start=start_index + 1):
        keyboard.add(types.InlineKeyboardButton(text=f"Продать {car_name}", callback_data=f"sell_gelicopter_{car_name}"))

    # Добавляем кнопку "Закрыть"


    # Добавляем кнопки для перелистывания страниц
    navigation_buttons = await generate_user_navigation_buttons1(page_number1, total_cars)
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
    keyboard.add(types.InlineKeyboardButton(text="❌" , callback_data="close"))

    return keyboard




@dp.callback_query(lambda c: c.data.startswith('sell_gelicopter_'))
async def sell_gelicopter_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    # Проверяем, совпадает ли пользователь, который вызвал продажу, с текущим пользователем
    if user_id != last_sell_user_id3:
        await callback_query.answer("Вы не можете продавать вертолеты других пользователей.")
        return

    car_name = callback_query.data.split('_') [ 2 ]  # Changed index to 1
    print(f"Попытка продажи машины с именем: '{car_name}'")




    # Получаем список машин пользователя
    user_cars = await db.show_user_gelicopter(user_id)

    # Проверяем, существует ли указанное имя машины в списке user_cars
    if car_name in user_cars:
        # Получаем официальную цену машины из списка car_catalog
        for name, price in gelicopter_catalog:
            if name.lower() == car_name.lower():
                sale_price = price
                break
        else:
            await callback_query.answer(f"Ошибка: Официальная цена для {car_name} не найдена.")
            return

        # Создаем сообщение с выбором "вы уверены продать машину (название машины)" и кнопками "продать" и "отменить"
        confirmation_message = f"✨ Вы уверены, что хотите продать вертолет\n<b>{car_name}?</b>"
        confirmation_keyboard = types.InlineKeyboardMarkup(row_width=2)
        confirmation_keyboard.add(
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_gelicoptersell"),
            types.InlineKeyboardButton("✅ Продать", callback_data=f"confirm_gelicoptersell_{car_name}")
        )

        # Получаем путь к изображению машины
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
            print(f"Ошибка: Файл изображения машины не найден: {image_filename}")
            await callback_query.answer(f"Ошибка: Файл изображения вертолета не найден")

    else:
        print(f"Ошибка: Машина '{car_name}' не найдена в списке вертолетоа пользователя.")
        await callback_query.answer("Ошибка: вертолет не найдена.")

# Обработчик нажатия кнопки "Продать"
@dp.callback_query(lambda c: c.data.startswith('confirm_gelicoptersell_'))
async def confirm_sell_callback(callback_query: types.CallbackQuery):

    car_name = callback_query.data.split('_')[2]

    # Получаем user_id и остальные данные из контекста callback'а
    user_id = callback_query.from_user.id

    # Проверяем, совпадает ли пользователь, вызвавший функцию, с пользователем, который вызвал последнюю команду на продажу машины
    if user_id != last_sell_user_id3:
        await callback_query.answer("Вы не можете продать вертолет другого пользователя.")
        return

    # Получаем официальную цену машины из списка car_catalog
    for name, price in gelicopter_catalog:
        if name.lower() == car_name.lower():
            sale_price = price
            break
    else:
        await callback_query.answer(f"Ошибка: Официальная цена для {car_name} не найдена.")
        return

    # Рассчитываем цену со скидкой
    sale_price_discounted = int(sale_price * 0.85)

    # Выполняем продажу машины и обновляем баланс пользователя
    success, message = await db.sell_gelicopter(user_id, car_name, sale_price_discounted)
    if success:
        formatted_sale_price = "{:,.0f}".format(sale_price_discounted).replace(',', '.')
        await callback_query.answer("✔️ Успешная продажа")
        # Создаем инлайн-кнопку "вернуться"
        return_button = InlineKeyboardButton("Вернуться", callback_data="return_to_gelicopter1231_menu")
        # Создаем клавиатуру с одной кнопкой
        keyboard = InlineKeyboardMarkup().add(return_button)
        await callback_query.message.answer(
            f"💸🚁 вертолет {car_name} был продана за {formatted_sale_price} кут", reply_markup=keyboard)
        # Удаляем сообщение после продажи
        await callback_query.message.delete()
    else:
        await callback_query.answer(f"Ошибка: {message}")


@dp.callback_query(lambda c: c.data == 'return_to_gelicopter1231_menu')
async def return_to_sell_menu(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    user_cars = await db.show_user_gelicopter(user_id)
    await callback_query.message.delete()
    if user_cars:
        keyboard = await generate_gelicopter_buttons_with_navigation1(user_id)
        await callback_query.message.answer("Выберите вертолет для продажи:", reply_markup=keyboard)
    else:
        await callback_query.message.answer("✖️ У вас нет вертолетов для продажи.")

# Обработчик кнопки "Отменить" при продаже машины
@dp.callback_query(lambda c: c.data == 'cancel_gelicoptersell')
async def cancel_sell_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    if user_id != last_sell_user_id3:
        await callback_query.answer("Вы не можете отменить продажу вертолета другого пользователя.")
        return
    keyboard = await generate_gelicopter_buttons_with_navigation1(user_id)
    await callback_query.message.answer("🚁 Выберите вертолет для продажи:", reply_markup=keyboard)
    await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == 'close123123')
async def process_close_callback(callback_query: types.CallbackQuery):

    if callback_query.from_user.id == last_sell_user_id3:
        await callback_query.answer('Список вертолетов для продажи удален')
        await callback_query.message.delete()
    else:
        await callback_query.answer("Доступ запрещен.")



