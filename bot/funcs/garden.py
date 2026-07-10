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
import random

from bot.funcs.func import *
from bot.funcs.shophouse import *

from main import db



current_user341234123412 = None
current_user3412341234123412 = None




@dp.message()
async def garden(message: Message):
    if message.text.lower() in ["создать огород","Создать огород","построить огород","Построить огород"]:
        user_id = message.from_user.id

        house_name = db.user_has_house(user_id)
        if house_name:
            house_info = db.get_house_info(house_name)
            if house_info:
                gardenplace = house_info [ 2 ]
                gardenslots = house_info [ 3 ]

                db.create_garden(user_id , gardenplace , gardenslots)
                await message.reply("🧑🏼‍🌾 Огород успешно создан!")
            else:
                await message.reply("⚠️ Информация о доме не найдена.")
        else:
            await message.reply("🔥 У вас нет дома для создания огорода.")





    elif message.text.lower() in ['выкопать культуру','Выкопать культуру','выкопать растение','Выкопать растение']:
        user_id = message.from_user.id
        global current_user3412341234123412
        current_user3412341234123412 = message.from_user.id
        plants_info = db.get_plants_info(user_id)
        garden_info = db.get_garden_info(user_id)
        print(f"Полученная информация о растениях: {plants_info}")
        if garden_info:
            if not plants_info or all(info is None or not info.strip() for info in plants_info):
                await message.reply("🔥 У вас нет культур для выращивания.\n💲 Купите или используйте семена")
            else:
                available_plants = [ ]
                print(f"Доступные растения на начальном этапе: {available_plants}")

                for plant_info in plants_info:
                    if plant_info:
                        available_plants.extend([ plant.strip() for plant in plant_info.split(",") if plant.strip() ])

                markup = InlineKeyboardMarkup()
                for plant in available_plants:
                    markup.add(InlineKeyboardButton(plant , callback_data=f'dig_{plant}'))

                await message.reply("🧑🏼‍🌾 Выберите культуру для выкапывания" , reply_markup=markup)

        else:

            await message.reply("🔥 У вас нет огорода.")

















    elif message.text.lower() in ["мой огород","Мой огород"]:
        if message.chat.type == 'private':

            global current_user34123412341234123412
            current_user34123412341234123412 = message.from_user.id

            user_id = message.from_user.id

            garden_info = db.get_garden_info(user_id)

            plants_info = db.get_plants_info(user_id)

            if garden_info:

                gardenplace , gardenslots = garden_info

                if not plants_info or all(plant is None for plant in plants_info):

                    plants = "Нет"

                else:

                    # Используем plants_info как кортеж

                    cucumbers , tomatoes , carrots , potato , cabbage , apple , melon , banana , berry , corn , marix = plants_info

                    # Создаем список культур для вывода

                    plants_list = [ ]

                    if cucumbers:
                        plants_list.append("Огурцы")

                    if tomatoes:
                        plants_list.append("Помидоры")

                    if carrots:
                        plants_list.append("Морковь")

                    if potato:
                        plants_list.append("Картофель")

                    if cabbage:
                        plants_list.append("Капуста")

                    if apple:
                        plants_list.append("Яблоки")

                    if melon:
                        plants_list.append("Арбуз")

                    if banana:
                        plants_list.append("Бананы")

                    if berry:
                        plants_list.append("Клубника")

                    if corn:
                        plants_list.append("Кукуруза")

                    if marix:
                        plants_list.append("Марихуана")

                    # Преобразуем список в строку

                    plants = ", ".join(plants_list)
                    print(plants_list)

                keyboard = types.InlineKeyboardMarkup()

                keyboard.add(types.InlineKeyboardButton("Растить культуры" , callback_data="grow_cultures"))

                await message.reply(

                    f"🧑🏼‍🌾 Мест для посадки: {gardenplace}\n"

                    f"🪴 Культуры : <b>{plants}</b>" ,

                    reply_markup=keyboard ,

                    parse_mode="HTML"

                )

            else:

                await message.reply("🔥 У вас нет огорода.")


        else:

            reply_markup = types.InlineKeyboardMarkup()

            button = types.InlineKeyboardButton(text="Написать в личные сообщения" , url="https://t.me/Cutee3Bot")

            reply_markup.add(button)

            await message.reply(
            '⚠️ Эта функция работает только в личных сообщениях с ботом ' , reply_markup=reply_markup)

    @dp.callback_query(lambda c: c.data == 'grow_cultures1')
    async def handle_grow_cultures1(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        #if callback_query.from_user.id != current_user34123412341234123412:
            #await callback_query.answer("Это сообщение для другого пользователя1")
            #return
        user_id = callback_query.from_user.id

        garden_info = db.get_garden_info(user_id)
        plants_info = db.get_plants_info(user_id)

        if garden_info:
            gardenplace , gardenslots = garden_info

            if not plants_info or all(plant is None for plant in plants_info):
                plants = "Нет"
            else:
                # Используем plants_info как кортеж
                cucumbers,tomatoes , carrots , potato , cabbage , apple , melon , banana , berry , corn, marix = plants_info

                # Создаем список культур для вывода
                plants_list = [ ]

                if cucumbers:
                    plants_list.append("Огурцы")
                if tomatoes:
                    plants_list.append("Помидоры")
                if carrots:
                    plants_list.append("Морковь")
                if potato:
                    plants_list.append("Картофель")
                if cabbage:
                    plants_list.append("Капуста")
                if apple:
                    plants_list.append("Яблоки")
                if melon:
                    plants_list.append("Арбуз")
                if banana:
                    plants_list.append("Бананы")
                if berry:
                    plants_list.append("Клубника")
                if corn:
                    plants_list.append("Кукуруза")
                if marix:
                    plants_list.append("Марихуана")

                # Преобразуем список в строку
                plants = ", ".join(plants_list)

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Растить культуры" , callback_data="grow_cultures"))

            await callback_query.message.edit_text(
                f"🧑🏼‍🌾 Мест для посадки: {gardenplace}\n"
                f"🪴 Культуры: <b>{plants}</b>" , reply_markup=keyboard , parse_mode="HTML")
        else:

            await callback_query.message.answer_sticker(
                "CAACAgQAAxkBAV9ndGZhydvHBK2TGXX4jkr6RhB_M6YbAALAAAOWvJEOlhj0a3NDtfo1BA")
            await callback_query.message.reply("🔥 У вас нет огорода.")


    @dp.callback_query(lambda c: c.data == 'grow_cultures')
    async def handle_grow_cultures3412(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        #if callback_query.from_user.id != current_user34123412341234123412:
            #await callback_query.answer("Это сообщение для другого пользователя2")
            #return
        user_id = callback_query.from_user.id
        await send_grow_cultures_keyboard(user_id , callback_query.message)

    async def send_grow_cultures_keyboard(user_id , message):

        plants_info = db.get_plants_info(user_id)
        print(f"Полученная информация о растениях: {plants_info}")

        if not plants_info or all(info is None or not info.strip() for info in plants_info):
            await message.reply("🔥 У вас нет культур для выращивания.\n💲 Купите или используйте семена")
        else:
            available_plants = [ ]
            print(f"Доступные растения на начальном этапе: {available_plants}")

            for plant_info in plants_info:
                if plant_info:
                    available_plants.extend([ plant.strip() for plant in plant_info.split(",") if plant.strip() ])

            print(f"Обновленные доступные растения: {available_plants}")

            # Важно заполнять!
            cucumbers_growth = db.get_cucumbers_growth(user_id)
            tomatoes_growth = db.get_tomatoes_growth(user_id)
            carrot_growth = db.get_carrot_growth(user_id)
            potato_growth = db.get_potato_growth(user_id)
            cabbage_growth = db.get_cabbage_growth(user_id)
            apple_growth = db.get_apple_growth(user_id)
            melon_growth = db.get_melon_growth(user_id)
            banana_growth = db.get_banana_growth(user_id)
            berry_growth = db.get_berry_growth(user_id)
            corn_growth = db.get_corn_growth(user_id)
            marix_growth = db.get_marix_growth(user_id)

            print(f"Рост огурцов: {cucumbers_growth}%")
            print(f"Рост помидоров: {tomatoes_growth}%")
            print(f"Рост моркови: {carrot_growth}%")
            print(f"Рост картофеля: {potato_growth}%")
            print(f"Рост капусты: {cabbage_growth}%")
            print(f"Рост яблок: {apple_growth}%")
            print(f"Рост яблок: {melon_growth}%")
            print(f"Рост яблок: {banana_growth}%")
            print(f"Рост яблок: {berry_growth}%")
            print(f"Рост яблок: {corn_growth}%")

            keyboard = types.InlineKeyboardMarkup()
            if "помидоры" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить помидоры [{tomatoes_growth}%]" if tomatoes_growth is not None else "растить помидоры" ,
                        callback_data="plant_tomatoes"))
                print("Кнопка для выращивания помидоров добавлена")

            if "огурцы" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить огурцы [{cucumbers_growth}%]" if cucumbers_growth is not None else "растить огурцы" ,
                        callback_data="plant_cucumbers"))
                print("Кнопка для выращивания огурцов добавлена")

            if "морковь" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить морковь [{carrot_growth}%]" if carrot_growth is not None else "растить морковь" ,
                        callback_data="plant_carrot"))
                print("Кнопка для выращивания моркови добавлена")

            if "картофель" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить картофель [{potato_growth}%]" if potato_growth is not None else "растить картофель" ,
                        callback_data="plant_potato"))
                print("Кнопка для выращивания картофеля добавлена")

            if "капуста" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить капусту [{cabbage_growth}%]" if cabbage_growth is not None else "растить капусту" ,
                        callback_data="plant_cabbage"))
                print("Кнопка для выращивания капусты добавлена")

            if "яблоко" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить яблоки [{apple_growth}%]" if apple_growth is not None else "растить яблоки" ,
                        callback_data="plant_apple"))
                print("Кнопка для выращивания яблок добавлена")

            if "арбуз" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить арбузы [{melon_growth}%]" if melon_growth is not None else "растить арбузы" ,
                        callback_data="plant_melon"))
                print("Кнопка для выращивания яблок добавлена")

            if "бананы" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить бананы [{banana_growth}%]" if banana_growth is not None else "растить бананы" ,
                        callback_data="plant_banana"))
                print("Кнопка для выращивания яблок добавлена")

            if "клубника" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить клубнику [{berry_growth}%]" if berry_growth is not None else "растить клубнику" ,
                        callback_data="plant_berry"))
                print("Кнопка для выращивания яблок добавлена")

            if "кукуруза" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить кукурузу [{corn_growth}%]" if corn_growth is not None else "растить кукурузу" ,
                        callback_data="plant_corn"))
                print("Кнопка для выращивания яблок добавлена")

            if "марихуана" in available_plants:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"растить марихуану [{marix_growth}%]" if marix_growth is not None else "растить марихуану" ,
                        callback_data="plant_marix"))
                print("Кнопка для выращивания яблок добавлена")

            keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures1"))
            print("Кнопка 'Назад' добавлена")

            await bot1.edit_message_text(
                chat_id=message.chat.id , message_id=message.message_id , text="👨🏼‍🌾 Выберите, что хотите вырастить" ,
                reply_markup=keyboard)
            print("Сообщение с клавиатурой отправлено")

    game123 = [ ]  # Список для отслеживания состояния игры

    @dp.callback_query(lambda c: c.data == 'plant_tomatoes')
    async def handle_plant_tomatoes(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        #if callback_query.from_user.id != current_user34123412341234123412:
            #await callback_query.answer("Это сообщение для другого пользователя")
            #return
        user_id = callback_query.from_user.id
        await start_planting_game(user_id , "помидоры" , callback_query.message , "tomato")

    async def start_planting_game(user_id , plant , message , plant_type):

        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        game123.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(game123)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)

        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🍅" , callback_data=f"check_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))
        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id , text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}" ,
            reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('check_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message  # Получаем сообщение из callback_query
        data = callback_query.data.split('_')  # Разбиваем строку по '_'
        index = int(data [ 1 ])  # Получаем индекс кнопки из данных
        random123 = random.randint(5 , 25)

        # Получаем текст кнопки из сообщения
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        # Проверяем, что текст кнопки содержит символ 🍅
        if '🍅' in button_text:
            # Находим информацию о текущей игре пользователя
            current_game = next((game for game in game123 if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1  # Увеличиваем количество нажатых кнопок

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Обновляем данные о прогрессе роста помидоров перед проверкой

                    tomato_proz = db.check_tomato_growth_progress(user_id)
                    print(f"Updated growth progress: {tomato_proz}%")  # Лог для отладки

                    if tomato_proz + random123 >= 100:
                        item_to_send = "🍅 Помидор"
                        quantity = 2

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_tomato_growth_progress(user_id , random123)

                        await message.edit_text(
                            f"👨🏼‍🌾 Помидоры выросли! Вы получили <b>{quantity}</b> шт помидор", parse_mode="HTML")

                        db.annul_tomatoproz(user_id)
                        game123.remove(current_game)
                    else:
                        # Увеличение показателя процесса роста
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_tomato_growth_progress(user_id , random123)
                        await message.edit_text(f"🍅 Ваши помидоры выросли на {random123}%",reply_markup=keyboard)
                        game123.remove(current_game)

                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    # Изменяем эмодзи нажатой кнопки
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id ,
                        reply_markup=change_button_emoji(message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        else:
            await bot1.answer_callback_query(
                callback_query.id , "Нажимайте только на помеченные кнопки.")  # Ответ на callback_query без изменения сообщения

    # Функция для изменения эмодзи нажатой кнопки
    def change_button_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]

        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup

    gameplants = [ ]
    @dp.callback_query(lambda c: c.data == 'plant_cucumbers')
    async def handle_plant_cucumbers(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_cucumbers(user_id , "огурцы" , callback_query.message , "plants")

    async def start_planting_cucumbers(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gameplants.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gameplants)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🥒" , callback_data=f"checkcucumbers_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))


        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))


        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkcucumbers_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomcucu = random.randint(5 , 25)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🥒' in button_text:
            current_game = next((game for game in gameplants if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_plants_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randomcucu >= 100:
                        item_to_send = "🥒 Огурец"
                        quantity = 2

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_cucumbers_growth_progress(user_id , randomcucu)
                        await message.edit_text(
                            f"👨🏼‍🌾 Огурцы выросли! Вы получили <b>{quantity}</b> шт огурцов", parse_mode="HTML")
                        db.annul_plantsproz(user_id)
                        gameplants.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_cucumbers_growth_progress(user_id , randomcucu)
                        await message.edit_text(f"🥒 Ваши огурцы выросли на {randomcucu}%",reply_markup=keyboard)
                        gameplants.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_cucumbers_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")
    # Функция для изменения эмодзи нажатой кнопки
    def change_cucumbers_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup









    gamecarrot = [ ]
    @dp.callback_query(lambda c: c.data == 'plant_carrot')
    async def handle_plant_carrot(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_carrot(user_id , "морковь" , callback_query.message , "carrot")

    async def start_planting_carrot(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gamecarrot.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gamecarrot)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🥕" , callback_data=f"checkcarrot_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkcarrot_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomcarrot = random.randint(5 , 25)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🥕' in button_text:
            current_game = next((game for game in gamecarrot if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_carrot_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randomcarrot >= 100:
                        item_to_send = "🥕 Морковь"
                        quantity = 2

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_carrot_growth_progress(user_id , randomcarrot)
                        await message.edit_text(
                            f"👨🏼‍🌾 Морковь выросла! Вы получили <b>{quantity}</b> шт моркови", parse_mode="HTML")
                        db.annul_carrotproz(user_id)
                        gamecarrot.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_carrot_growth_progress(user_id , randomcarrot)
                        await message.edit_text(f"🥕 Ваша морковь выросла на {randomcarrot}%",reply_markup=keyboard)
                        gamecarrot.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_carrot_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_carrot_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup









    gamepotato = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_potato')
    async def handle_plant_potato(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_potato(user_id , "картофель" , callback_query.message , "potato")

    async def start_planting_potato(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gamepotato.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gamepotato)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🥔" , callback_data=f"checkpotato_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkpotato_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randompotato = random.randint(5 , 25)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🥔' in button_text:
            current_game = next((game for game in gamepotato if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_potato_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randompotato >= 100:
                        item_to_send = "🥔 Картофель"
                        quantity = 3

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_potato_growth_progress(user_id , randompotato)
                        await message.edit_text(
                            f"👨🏼‍🌾 Картофель выросла! Вы получили <b>{quantity}</b> шт картошки", parse_mode="HTML")
                        db.annul_potatoproz(user_id)
                        gamepotato.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_potato_growth_progress(user_id , randompotato)
                        await message.edit_text(f"🥔 Ваша картофель выросла на {randompotato}%",reply_markup=keyboard)
                        gamepotato.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_potato_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_potato_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup















    gamecabbage = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_cabbage')
    async def handle_plant_cabbage(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_cabbage(user_id , "капуста" , callback_query.message , "cabbage")

    async def start_planting_cabbage(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gamecabbage.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gamecabbage)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🥬" , callback_data=f"checkcabbage_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkcabbage_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomcabbage = random.randint(5 , 20)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🥬' in button_text:
            current_game = next((game for game in gamecabbage if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_cabbage_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randomcabbage >= 100:
                        item_to_send = "🥬 Капуста"
                        quantity = 3

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_cabbage_growth_progress(user_id , randomcabbage)
                        await message.edit_text(
                            f"👨🏼‍🌾 Капуста выросла! Вы получили <b>{quantity}</b> шт капусты", parse_mode="HTML")
                        db.annul_cabbageproz(user_id)
                        gamecabbage.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_cabbage_growth_progress(user_id , randomcabbage)
                        await message.edit_text(f"🥬 Ваша капуста выросла на {randomcabbage}%",reply_markup=keyboard)
                        gamecabbage.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_cabbage_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_cabbage_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup







    gameapple = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_apple')
    async def handle_plant_cabbage(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_apple(user_id , "яблоко" , callback_query.message , "apple")

    async def start_planting_apple(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gameapple.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gameapple)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🍏" , callback_data=f"checkapple_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkapple_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomapple = random.randint(5, 18)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🍏' in button_text:
            current_game = next((game for game in gameapple if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_apple_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randomapple >= 100:
                        item_to_send = "🍏 Яблоко"
                        quantity = 3

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_apple_growth_progress(user_id , randomapple)
                        await message.edit_text(
                            f"👨🏼‍🌾 Яблоки выросли! Вы получили <b>{quantity}</b> шт яблок", parse_mode="HTML")
                        db.annul_appleproz(user_id)
                        gameapple.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_apple_growth_progress(user_id , randomapple)
                        await message.edit_text(f"🍏 Ваши яблоки выросли на {randomapple}%",reply_markup=keyboard)
                        gameapple.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_apple_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_apple_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup




    gamemelon = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_melon')
    async def handle_plant_cabbage(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_melon(user_id , "арбуз" , callback_query.message , "melon")

    async def start_planting_melon(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gamemelon.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gamemelon)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🍉" , callback_data=f"checkmelon_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkmelon_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randommelon = random.randint(5, 17)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🍉' in button_text:
            current_game = next((game for game in gamemelon if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_melon_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randommelon >= 100:
                        item_to_send = "🍉 Арбуз"
                        quantity = 3

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_melon_growth_progress(user_id , randommelon)
                        await message.edit_text(
                            f"👨🏼‍🌾 Арбуз вырос! Вы получили <b>{quantity}</b> арбуза" ,
                            parse_mode="HTML")
                        db.annul_melonproz(user_id)
                        gamemelon.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_melon_growth_progress(user_id , randommelon)
                        await message.edit_text(f"🍉 Арбуз вырос на {randommelon}%",reply_markup=keyboard)
                        gamemelon.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_melon_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_melon_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup







    gamebanana = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_banana')
    async def handle_plant_cabbage(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_banana(user_id , "банан" , callback_query.message , "banana")

    async def start_planting_banana(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gamebanana.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gamebanana)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🍌" , callback_data=f"checkbanana_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkbanana_'))
    async def handle_check(callback_query: types.CallbackQuery):


        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randombanana = random.randint( 5, 16)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🍌' in button_text:
            current_game = next((game for game in gamebanana if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_banana_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randombanana >= 100:
                        item_to_send = "🍌 Бананы"
                        quantity = 5

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_banana_growth_progress(user_id , randombanana)
                        await message.edit_text(
                            f"👨🏼‍🌾 Бананы выросли! Вы получили <b>{quantity}</b> шт бананов", parse_mode="HTML")
                        db.annul_bananaproz(user_id)
                        gamebanana.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_banana_growth_progress(user_id , randombanana)
                        await message.edit_text(f"🍌 Бананы выросли на {randombanana}%",reply_markup=keyboard)
                        gamebanana.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_banana_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_banana_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup






    gameberry = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_berry')
    async def handle_plant_corn(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_berry(user_id , "клубника" , callback_query.message , "berry")

    async def start_planting_berry(user_id , plant , message , plant_type):
        # Генерируем случайное количество ячеек для подсветки (от 2 до 5)
        num_highlighted_cells = random.randint(2 , 3)
        gameberry.append(
            {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
             "plant_type": plant_type})
        print(gameberry)  # Добавляем информацию о новой игре в список game123
        # Генерируем случайные индексы для подсветки
        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()  # Добавляем новую строку каждые 5 кнопок
            if i in highlighted_indices:  # Если индекс в списке для подсветки
                keyboard.insert(types.InlineKeyboardButton("🍓" , callback_data=f"checkberry_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkberry_'))
    async def handle_check(callback_query: types.CallbackQuery):


        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomberry = random.randint(5 , 14)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🍓' in button_text:
            current_game = next((game for game in gameberry if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    # Update the growth progress first

                    cucumber_proz = db.check_berry_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Log for debugging

                    if cucumber_proz + randomberry >= 100:
                        item_to_send = "🍓 Клубника"
                        quantity = 5

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_berry_growth_progress(user_id , randomberry)
                        await message.edit_text(
                            f"👨🏼‍🌾 Клубника выросла! Вы получили <b>{quantity}</b> шт клубники", parse_mode="HTML")
                        db.annul_berryproz(user_id)
                        gameberry.remove(current_game)


                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_berry_growth_progress(user_id , randomberry)
                        await message.edit_text(f"🍓 Клубника выросла на {randomberry}%",reply_markup=keyboard)
                        gameberry.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_berry_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_berry_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        # Изменяем эмодзи кнопки
        button.text = "🌱"
        return reply_markup

    gamecorn = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_corn')
    async def handle_plant_corn(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_corn(user_id , "кукуруза" , callback_query.message , "corn")

    async def start_planting_corn(user_id , plant , message , plant_type):
        num_highlighted_cells = random.randint(2 , 3)
        game_info = {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
                     "plant_type": plant_type}
        gamecorn.append(game_info)
        print(f"Добавлена новая игра: {game_info}")  # Debug log
        print(f"Тип растения: {plant_type}")  # Debug log

        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()
            if i in highlighted_indices:
                keyboard.insert(types.InlineKeyboardButton("🌽" , callback_data=f"checkcorn_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkcorn_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randomcorn = random.randint(5 , 20)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🌽' in button_text:
            current_game = next((game for game in gamecorn if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    cucumber_proz = db.check_corn_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Debug log

                    if cucumber_proz + randomcorn >= 100:
                        item_to_send = "🌽 Кукуруза"
                        quantity = 3

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_corn_growth_progress(user_id , randomcorn)
                        await message.edit_text(
                            f"👨🏼‍🌾 Кукуруза выросла! Вы получили <b>{quantity}</b> шт кукурузы", parse_mode="HTML")
                        db.annul_cornproz(user_id)
                        gamecorn.remove(current_game)

                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_corn_growth_progress(user_id , randomcorn)
                        await message.edit_text(f"🌽 Кукуруза выросла на {randomcorn}%",reply_markup=keyboard)
                        gamecorn.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_corn_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_corn_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        button.text = "🌱"
        return reply_markup






    gamemarix = [ ]

    @dp.callback_query(lambda c: c.data == 'plant_marix')
    async def handle_plant_marix(callback_query: types.CallbackQuery):

        global current_user34123412341234123412

        # предполагается, что current_user используется для отслеживания текущего пользователя
        # if callback_query.from_user.id != current_user34123412341234123412:
        # await callback_query.answer("Это сообщение для другого пользователя")
        # return
        user_id = callback_query.from_user.id
        await start_planting_marix(user_id , "марихуана" , callback_query.message , "marix")

    async def start_planting_marix(user_id , plant , message , plant_type):
        num_highlighted_cells = random.randint(2 , 3)
        game_info = {"user_id": user_id , "total_buttons": num_highlighted_cells , "pressed_buttons": 0 ,
                     "plant_type": plant_type}
        gamemarix.append(game_info)
        print(f"Добавлена новая игра: {game_info}")  # Debug log
        print(f"Тип растения: {plant_type}")  # Debug log

        highlighted_indices = random.sample(range(25) , num_highlighted_cells)

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        for i in range(25):
            if i % 5 == 0:
                keyboard.add()
            if i in highlighted_indices:
                keyboard.insert(types.InlineKeyboardButton("🌿" , callback_data=f"checkmarix_{i}"))
            else:
                keyboard.insert(types.InlineKeyboardButton(" " , callback_data=f"empty_{i}"))

        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))

        await bot1.edit_message_text(
            chat_id=message.chat.id , message_id=message.message_id ,
            text=f"🧑🏼‍🌾 Нажмите на кнопки чтобы вырастить {plant}!" , reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith('checkmarix_'))
    async def handle_check(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message = callback_query.message
        data = callback_query.data.split('_')
        index = int(data [ 1 ])
        randommarix = random.randint(1 , 3)
        button_text = message.reply_markup.inline_keyboard [ index // 5 ] [ index % 5 ].text

        if '🌿' in button_text:
            current_game = next((game for game in gamemarix if game [ "user_id" ] == user_id) , None)
            if current_game:
                current_game [ "pressed_buttons" ] += 1

                if current_game [ "pressed_buttons" ] == current_game [ "total_buttons" ]:
                    cucumber_proz = db.check_marix_growth_progress(user_id)
                    print(f"Updated growth progress: {cucumber_proz}%")  # Debug log

                    if cucumber_proz + randommarix >= 100:
                        item_to_send = "🌿 Марихуана"
                        quantity = 4

                        receiver_inventory = await db.get_user_inventory(user_id)
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                        await db.set_user_inventory(user_id , receiver_inventory)
                        db.update_marix_growth_progress(user_id , randommarix)
                        await message.edit_text(
                            f"👨🏼‍🌾 Марихуана выросла! Вы получили <b>{quantity}</b> шт марихуаны" ,
                            parse_mode="HTML")
                        db.annul_marixproz(user_id)
                        gamemarix.remove(current_game)

                    else:
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
                        db.update_marix_growth_progress(user_id , randommarix)
                        await message.edit_text(f"🌿 Марихуана выросла на {randommarix}%",reply_markup=keyboard)
                        gamemarix.remove(current_game)
                else:
                    await bot1.answer_callback_query(
                        callback_query.id , "Отлично! Продолжайте нажимать помеченные кнопки.")
                    await bot1.edit_message_reply_markup(
                        message.chat.id , message.message_id , reply_markup=change_marix_emoji(
                            message.reply_markup , index))

                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Назад" , callback_data="grow_cultures"))
        else:
            await bot1.answer_callback_query(callback_query.id , "Нажимайте только на помеченные кнопки.")

    # Функция для изменения эмодзи нажатой кнопки
    def change_marix_emoji(reply_markup , index):
        keyboard = reply_markup.inline_keyboard
        row_index = index // 5
        col_index = index % 5
        button = keyboard [ row_index ] [ col_index ]
        button.text = "🌱"
        return reply_markup


@dp.callback_query(lambda c: c.data.startswith('dig_'))
async def process_callback_dig(callback_query: types.CallbackQuery):

    global current_user3412341234123412
# предполагается, что current_user используется для отслеживания текущего пользователя
    if callback_query.from_user.id != current_user3412341234123412:
        await callback_query.answer("Это сообщение для другого пользователя")
    else:
        plant = callback_query.data [ len('dig_'): ]
        user_id = callback_query.from_user.id
        db.update_plant_info(user_id , plant)
        await bot1.answer_callback_query(callback_query.id , f"{plant} выкопан")
        await callback_query.message.edit_text(f"✅ {plant} успешно выкопан из огорода.")


