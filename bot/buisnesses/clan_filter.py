from aiogram import Bot , Dispatcher , types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import bot1 , dp , db
import aiogram
from aiogram import types
from aiogram import types

from aiogram.exceptions import TelegramAPIError  # Исключения теперь из aiogram.exceptions
import emoji
import math
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
from aiogram.types import CallbackQuery
from aiogram.types import Message

from bot.db_create.pklcode import LazyGameStore
user_clan_control = LazyGameStore("user_clan_control")
user_message_rename = LazyGameStore("user_message_rename")
user_message_createclan = LazyGameStore("user_message_createclan")
user_message_deleteclan = LazyGameStore("user_message_deleteclan")
user_message_joinclan = LazyGameStore("user_message_joinclan")
user_message_attackclan = LazyGameStore("user_message_attackclan")
user_message_moiclan = LazyGameStore("user_message_moiclan")
user_message_vusenie = LazyGameStore("user_message_vusenie")
user_message_ponizenie = LazyGameStore("user_message_ponizenie")
user_bebebe = LazyGameStore("user_bebebe")
user_cooldowns = LazyGameStore("user_cooldowns_clan")
user_ras = LazyGameStore("user_ras")

ITEMS_PER_PAGE = 10


ITEMS_user_PER_PAGE = 15  # Количество участников на одной странице функции "пользователи клана"

# Функция для создания кнопок навигации по участникам клана
def get_user_navigation_buttons(page, total_pages):
    buttons = []

    if page > 0:
        buttons.append(InlineKeyboardButton("🔙", callback_data=f"user_page_{page - 1}"))

    if page == 0 and total_pages > 1:
        buttons.append(InlineKeyboardButton("🔜🔜", callback_data=f"user_page_{total_pages - 1}"))

    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("🔜", callback_data=f"user_page_{page + 1}"))

    if page == total_pages - 1 and total_pages > 1:
        buttons.append(InlineKeyboardButton("🔙🔙", callback_data=f"user_page_0"))

    return buttons
def clan_get_navigation_buttons(page, total_pages):
    buttons = []

    if page > 0:
        buttons.append(InlineKeyboardButton("🔙", callback_data=f"clan_page_{page - 1}"))


    # Если это первая страница, показываем кнопку перехода на последнюю страницу
    if page == 0 and total_pages > 1:
        buttons.append(InlineKeyboardButton("☑️", callback_data=f"clan_page_{total_pages - 1}"))

    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("🔜", callback_data=f"clan_page_{page + 1}"))


    # Если это последняя страница, показываем кнопку перехода на первую страницу
    if page == total_pages - 1 and total_pages > 1:
        buttons.append(InlineKeyboardButton("☑️", callback_data=f"clan_page_0"))

    return buttons

async def send_clan_creation_confirmation(message: Message, clan_name: str):
    keyboard = InlineKeyboardMarkup(row_width=2)
    cancel_button = InlineKeyboardButton("Отменить", callback_data="cancel_clan_creation")
    create_button = InlineKeyboardButton("Создать", callback_data="confirm_clan_creation")
    keyboard.add(cancel_button, create_button)

    await message.reply(
        f"🛡 Создание клана <b><code>{clan_name}<code></b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

def create_war_keyboard(clan_emoji):
    keyboard = InlineKeyboardMarkup(row_width=1)
    finish_button = InlineKeyboardButton(
        "Завершить битву",
        callback_data=f"finish_battle:{clan_emoji}"
    )
    keyboard.add(finish_button)
    return keyboard


def create_surrender_keyboard(clan_emoji):
    keyboard = InlineKeyboardMarkup(row_width=1)
    finish_button = InlineKeyboardButton(
        "сдаться",
        callback_data=f"surrender_battle:{clan_emoji}"
    )
    keyboard.add(finish_button)
    return keyboard


def surrender_confirm_keyboard(clan_emoji):
    keyboard = InlineKeyboardMarkup(row_width=2)
    cancel_data = f"cancel_finish:{clan_emoji}"
    confirm_data = f"confirm_surrender:{clan_emoji}"

    cancel_button = InlineKeyboardButton(
        "Отменить", callback_data=cancel_data
    )
    confirm_button = InlineKeyboardButton(
        "Сдаться клану", callback_data=confirm_data
    )
    keyboard.add(cancel_button, confirm_button)
    return keyboard
def create_confirm_keyboard(clan_emoji):
    keyboard = InlineKeyboardMarkup(row_width=2)
    cancel_data = f"cancel_finish:{clan_emoji}"
    confirm_data = f"confirm_finish:{clan_emoji}"

    cancel_button = InlineKeyboardButton(
        "Отменить", callback_data=cancel_data
    )
    confirm_button = InlineKeyboardButton(
        "Завершить", callback_data=confirm_data
    )
    keyboard.add(cancel_button, confirm_button)
    return keyboard




@dp.message()
async def clan_filter(message: Message):
    original_text = message.text

    mes = original_text.lower()
    words = mes.split()
    split_mes = original_text.split()

    if len(words) >= 3:
        if words [ 0 ] in [ "создать" , "клан" ] and words [ 1 ] in [ "создать" , "клан" ]:
            clan_name = ' '.join(words [ 2: ]).strip()

            if clan_name:
                user_id = message.from_user.id

                user_in_clan = await db.user_in_clan(user_id)

                if user_in_clan:
                    await message.reply("⚠️ Вы уже являетесь лидером или участником клана.")
                    return

                if len(clan_name) > MAX_CLAN_NAME_LENGTH:
                    await message.reply(
                        f"🛠 Максимальная длина названия {MAX_CLAN_NAME_LENGTH} [ У вас <b>{len(clan_name)}</b> ]" ,
                        parse_mode="HTML")
                    return

                clan_emojis = await db.extract_emojis(clan_name)

                if not clan_emojis:
                    await message.reply("⚠️ Название клана должно содержать эмодзи.")
                    return

                clan_name_without_emojis = emoji.replace_emoji(clan_name , replace='').strip().lower()

                existing_emojis = await db.get_all_clan_emojis()
                existing_clan_names = await db.get_all_clan_names()

                # Проверка на занятость эмодзи
                if any(emoji in existing_emojis for emoji in clan_emojis):
                    await message.reply("⚠️ Эмодзи клана уже занят. Попробуйте другой.")
                    return

                # Проверка на существование названия
                #if clan_name_without_emojis in existing_clan_names:
                    #await message.reply("⚠️ Клан с таким названием уже существует.")
                    #return

                # Отправляем сообщение с подтверждением создания клана
                keyboard = types.InlineKeyboardMarkup()
                confirm_button = types.InlineKeyboardButton(
                    "Подтвердить" , callback_data=f"confirm_clan_creation:{clan_name}")
                cancel_button = types.InlineKeyboardButton("Отменить" , callback_data="cancel_clan_creation")
                keyboard.add(cancel_button , confirm_button)

                sent_createclan = await message.reply(
                    f"🛡 Создание клана <b><code>{clan_name}</code></b>" , reply_markup=keyboard ,
                    parse_mode="HTML")
                user_message_createclan [ user_id ] = sent_createclan.message_id

            else:
                await message.reply("⚠️ Название клана не может быть пустым.")

    @dp.callback_query(
        lambda c: c.data.startswith("confirm_clan_creation:") or c.data == "cancel_clan_creation")
    async def handle_clan_creation_callback(callback_query: types.CallbackQuery):
        import emoji
        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id


        randommessagebonus1 = random.choice(randommessagehelp)
        print("qqqqq7")
        if user_id not in user_message_createclan or user_message_createclan [ user_id ] != message_id:
            await callback_query.answer(randommessagebonus1)
            return

        data = callback_query.data

        if data == "cancel_clan_creation":
            await callback_query.answer('Создание отменено')
            await callback_query.message.edit_text("✖️ Создание клана отменено")
            return

        if data.startswith("confirm_clan_creation:"):
            clan_name = data.split(":" , 1) [ 1 ].strip()
            clan_name_without_emojis = emoji.replace_emoji(clan_name , replace='').strip()

            user_in_clan = await db.user_in_clan(user_id)
            if user_in_clan:
                await callback_query.message.edit_text("⚠️ Вы уже являетесь лидером или участником клана.")
                return

            if len(clan_name_without_emojis) > MAX_CLAN_NAME_LENGTH:
                await callback_query.message.edit_text(
                    f"🛠 Максимальная длина названия {MAX_CLAN_NAME_LENGTH} [ У вас <b>{len(clan_name)}</b> ]" ,
                    parse_mode="HTML")
                return

            clan_emojis = await db.extract_emojis(clan_name)
            if not clan_emojis:
                await callback_query.message.edit_text("⚠️ Название клана должно содержать эмодзи.")
                return

            existing_emojis = await db.get_all_clan_emojis()

            if any(emoji in existing_emojis for emoji in clan_emojis):
                await callback_query.message.edit_text("⚠️ Эмодзи клана уже занят. Попробуйте другой.")
                return

            clan_exists = await db.clan_exists(clan_name_without_emojis)
            #if clan_exists:
                #await callback_query.message.edit_text("⚠️ Клан с таким названием уже существует.")
                #return

            user_balance = await db.get_user_balance(user_id)
            if user_balance >= clan_creation_cost:
                updated_user_balance = user_balance - clan_creation_cost
                await db.update_user_balance(user_id , updated_user_balance)
                await db.add_clan(clan_name_without_emojis , user_id , clan_emojis)
                await callback_query.message.edit_text(
                    f"✅ Успешное создание клана <b>{clan_name}</b>" , parse_mode="HTML")
            else:
                await callback_query.message.edit_text(
                    f"⚠️ Недостаточно средств для создания клана [ требуется {clan_creation_cost} кут ]")

    parts = message.text.lower().split()

    if len(parts) >= 4 and parts [ 0 ] in [ "присоединиться" , "зайти" ] and parts [ 1 ] == "к" and parts [ 2 ] == "клану":
        clan_emoji = parts [ 3 ]
        print(f"[DEBUG] Extracted command: join {clan_emoji}")

        # Проверка существования клана с данным эмодзи
        clan_info = await db.get_clan_info_by_emoji(clan_emoji)
        if clan_info:
            user_id = str(message.from_user.id)
            print(f"[INFO] User ID: {user_id}")

            # Проверка, является ли пользователь уже членом клана
            user_in_clan = await db.user_in_clan(user_id)
            if user_in_clan:
                print(f"[WARNING] User {user_id} is already a member of a clan.")
                await message.reply("🛠 Вы уже являетесь лидером или участником клана.")
                return

            # Получение текущих членов клана
            members = await db.get_clan_members(clan_emoji)

            # Проверка, является ли пользователь уже членом клана
            if user_id in members:
                print(f"[WARNING] User {user_id} is already a member of clan {clan_emoji}")
                await message.reply("🛠 Вы уже являетесь членом этого клана.")
                return

            # Получение статуса приватности клана
            privacy_status = await db.get_clan_private_status(clan_emoji)

            if privacy_status == 0:  # Публичный клан
                # Прямое добавление пользователя в клан
                await db.add_user_to_clan(clan_emoji , user_id)
                await message.reply(
                    f"✅ Вы успешно присоединились к клану <code>{clan_emoji}</code> <b>{clan_info [ 'name' ]}</b>.", parse_mode="HTML")
            elif privacy_status == 1:  # Приватный клан
                # Уведомление лидера клана
                leader_id = int(clan_info [ 'owner' ])
                # Подготовка сообщений и кнопок
                keyboard = InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    InlineKeyboardButton("Отклонить" , callback_data=f"inus_join_{clan_emoji}_{user_id}") ,
                    InlineKeyboardButton("Добавить в клан" , callback_data=f"ept_join_{clan_emoji}_{user_id}"))

                join_request_message = (
                    f"🧩 <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> хочет присоединиться к вашему клану <code>{clan_emoji}</code> <b>{clan_info [ 'name' ]}</b>.\n"
                    f"🛠 Пожалуйста, примите или отклоните запрос.")

                # Отправка сообщения только лидеру
                try:
                    await bot1.send_message(
                        leader_id , join_request_message , parse_mode="HTML" , reply_markup=keyboard)
                except Exception as e:
                    print(f"[ERROR] Failed to send message to {leader_id}: {e}")

                await message.reply(
                    "✅ Запрос на вступление отправлен лидеру клана.\n🛠 Ожидайте ответа от бота в личных сообщениях")
        else:
            print(f"[ERROR] Clan with emoji {clan_emoji} does not exist.")
            await message.reply("🛠 Клан с таким эмодзи не существует.")



















    # 1231

    if message.text.lower() in [ "повысить" , "повысить до зама" , "сделать замом" , "повысить до заместителя" ]:
        # Проверка наличия reply на сообщение
        if message.reply_to_message:
            initiator_id = message.from_user.id
            user_id = initiator_id
            target_id = message.reply_to_message.from_user.id

            # Получаем информацию о клане пользователя, вызвавшего команду
            clan_info = await db.get_clan_by_user_id(initiator_id)

            if not clan_info:
                await message.answer("🛠 Вы не являетесь членом какого-либо клана.")
                return

            # Проверка, является ли пользователь лидером клана
            if clan_info.get('owner') != initiator_id:
                await message.answer("🛠 Вы не являетесь лидером клана.")
                return

            # Проверка, является ли целевой пользователь участником клана
            if str(target_id) not in clan_info.get('members' , [ ]):
                await message.answer("🛠 Этот пользователь не является участником вашего клана.")
                return

            # Преобразование 'zam' в список, если это не список
            zam_list = clan_info.get('zam' , [ ])
            if isinstance(zam_list , int):
                zam_list = [ ]  # Инициализируем пустой список, если zam_list - целое число
            elif isinstance(zam_list , str):
                zam_list = zam_list.split(',')  # Преобразуем строку в список

            # Проверка, не является ли целевой пользователь уже заместителем
            if str(target_id) in zam_list:
                await message.answer("🛠 Этот пользователь уже является заместителем клана.")
                return

            # Получаем имя целевого пользователя
            target_name = await db.get_user_first_name(target_id)
            if not target_name:
                target_name = "неизвестный пользователь"

            # Получаем эмодзи и название клана
            clan_emoji = clan_info.get('emoji' , '🛡')  # Убедитесь, что 'emoji' присутствует в информации о клане
            clan_name = clan_info.get(
                'name' , 'неизвестный клан')  # Убедитесь, что 'name' присутствует в информации о клане

            # Создание инлайн-кнопок для подтверждения повышения
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("Отменить" , callback_data=f"promotion_cancel_{target_id}") ,
                InlineKeyboardButton("Повысить" , callback_data=f"motion_confirm_{target_id}"))

            # Отправка сообщения с кнопками
            sent_vusenie = await message.answer(
                f"🚀 Вы уверены в повышении <b><a href='tg://user?id={target_id}'>{target_name}</a></b> до заместителя клана <code>{clan_emoji}</code> <b>{clan_name}</b>" ,
                reply_markup=keyboard , parse_mode="HTML")

            user_message_vusenie [ user_id ] = sent_vusenie.message_id

    if message.text in [ "понизить" , "Понизить" , "понизить должность" , "Понизить должность" , "забрать зама" ,
        "Забрать зама" , "снять" , "Снять" , "снять зама" , "Снять зама" , "снять заместителя" , "Снять заместителя","Понизить заместителя","понизить заместителя" ]:
        if message.reply_to_message:
            initiator_id = message.from_user.id
            target_id = message.reply_to_message.from_user.id
            user_id = initiator_id

            # Проверка условий понижения
            error_message , clan_info = await db.check_demotion_conditions(initiator_id , target_id)

            if error_message:
                await message.answer(error_message)
                return

            # Получаем имя целевого пользователя
            target_name = await db.get_user_first_name(target_id)
            if not target_name:
                target_name = "неизвестный пользователь"

            # Получаем эмодзи и название клана
            clan_emoji = clan_info.get('emoji' , '🛡')
            clan_name = clan_info.get('name' , 'неизвестный клан')

            # Создание инлайн-кнопок для подтверждения понижения
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("Отменить" , callback_data=f"demotion_cancel_{target_id}") ,
                InlineKeyboardButton("Понизить" , callback_data=f"demotion_confirm_{target_id}"))

            # Отправка сообщения с кнопками
            sent_ponizenie = await message.answer(
                f"🔽 Вы уверены в понижении <b><a href='tg://user?id={target_id}'>{target_name}</a></b> "
                f"до члена клана {clan_emoji} <b>{clan_name}</b>?" , reply_markup=keyboard , parse_mode="HTML")
            user_message_ponizenie [ user_id ] = sent_ponizenie.message_id
























#12
    if message.text.lower() in [ "список кланов" , "список кланов" , "клановый список" , "клановый список" ,
                                 "клан список" , "клан список" ]:
        user_id = message.from_user.id

        # Получаем список всех кланов
        clans_data = await db.get_all_clans3412()

        # Определяем количество элементов на одной странице
        items_per_page = 10
        total_pages = (len(clans_data) + items_per_page - 1) // items_per_page

        # По умолчанию отображаем первую страницу
        page = 0

        # Определяем начало и конец списка для текущей страницы
        start_index = page * items_per_page
        end_index = min(start_index + items_per_page , len(clans_data))

        # Создаем текст ответа для текущей страницы
        text = "📋 Список кланов:\n"

        # Добавляем информацию о каждом клане на текущей странице
        for clan in clans_data [ start_index:end_index ]:
            clan_emoji = clan [ 0 ]
            clan_name = clan [ 1 ]
            owner_id = clan [ 2 ]
            members_str = clan [ 3 ]  # Предполагаем, что это строка с ID участников, разделенными запятыми

            # Преобразуем строку с участниками в список
            members_list = members_str.split(',') if members_str else [ ]

            # Добавляем владельца клана в список участников, если его еще там нет
            if str(owner_id) not in members_list:
                members_list.append(str(owner_id))

            # Считаем количество участников
            members_count = len(members_list)

            # Определяем правильное окончание для слова "участник/участника/участников"
            if members_count == 1:
                participant_word = "участник"
            elif 2 <= members_count <= 4:
                participant_word = "участника"
            else:
                participant_word = "участников"

            # Формируем строку для текущего клана
            text += f"\n<code>{clan_emoji}</code> {clan_name} ~ <b>{members_count}</b> {participant_word}"

        # Создаем кнопки навигации
        navigation_buttons = clan_get_navigation_buttons(page , total_pages)
        keyboard = InlineKeyboardMarkup(row_width=2).add(*navigation_buttons)

        close_button = InlineKeyboardButton(text="Закрыть" , callback_data="clan_list_close")
        keyboard.add(close_button)

        # Отправляем сообщение с информацией о кланах и кнопками навигации
        sent_listclan = await message.reply(text , parse_mode="HTML" , reply_markup=keyboard)

        # Сохраняем ID сообщения для управления
        user_clan_control [ user_id ] = sent_listclan.message_id
        print(user_clan_control)
    original_text = message.text


    split_mes = original_text.split(maxsplit=1)


    # Убедимся, что split_mes содержит как минимум 2 элемента
    if len(split_mes) == 2:
        new_name = split_mes [ 1 ].strip()


        # Проверяем, что команда "переименовать" указана в тексте
        if split_mes [ 0 ].lower() == "переименовать":
            user_id = message.from_user.id


            # Получаем текущую информацию о клане
            clan_data = await db.get_clan_by_owner(message.from_user.id)


            if clan_data:
                current_name = clan_data [ 2 ]
                current_emojis = clan_data [ 1 ]  # Предположим, что эмодзи клана находятся в 2-й позиции


                # Извлекаем новые эмодзи из нового названия
                emojis = await db.extract_emojis(new_name)


                # Объединяем все эмодзи в строку
                new_emoji = ''.join(emojis)


                # Отделяем текст от эмодзи
                new_name_text = re.sub(r'[^\w\s]' , '' , new_name).strip()


                # Проверяем наличие эмодзи в новом названии
                if not new_emoji:
                    await message.reply("⚠️ Новое название клана должно содержать эмодзи.")

                    return

                # Проверяем наличие нового эмодзи в базе данных
                existing_clans = await db.get_clans_by_emoji(new_emoji)
                print(f"Отладка: Кланы с новым эмодзи = {existing_clans}")

                if existing_clans:
                    # Проверяем, что новый эмодзи не используется в клане этого же владельца
                    emoji_conflict = any(clan [ 0 ] != current_name for clan in existing_clans)
                    if emoji_conflict:
                        await message.reply("⚠️ Эмодзи клана уже занят. Попробуйте другой.")

                        return

                # Отправляем сообщение с инлайн кнопками для подтверждения или отмены
                confirm_markup = InlineKeyboardMarkup(row_width=2)
                confirm_markup.add(
                    InlineKeyboardButton("Отменить" , callback_data="cancel_rename") , InlineKeyboardButton(
                        "Подтвердить" , callback_data=f"confirm_rename:{current_name}:{new_name_text}:{new_emoji}"))


                sent_rename = await message.reply(
                    f"🗽 Изменение названия клана <b>{current_name}</b> на <b>{new_emoji}{new_name_text}</b>" , reply_markup=confirm_markup, parse_mode="HTML")
                user_message_rename [ user_id ] = sent_rename.message_id
                print(user_message_rename)
            else:
                await message.reply("⚠️ Не удалось найти ваш клан.")


    @dp.callback_query(lambda c: c.data and c.data.startswith('confirm_rename:'))
    async def process_confirm_rename(callback_query: CallbackQuery):
        # Parse the callback data

        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id


        randommessagebonus1 = random.choice(randommessagehelp)
        print("qqqqq8")
        if user_id not in user_message_rename or user_message_rename [ user_id ] != message_id:
            await callback_query.answer(randommessagebonus1)
            return
        data = callback_query.data.split(':')
        _ , current_name , new_name_text , new_emoji = data
        owner_id = callback_query.from_user.id

        # Update the clan name and emoji
        db.update_clan(
            current_name=current_name , new_name=new_name_text , new_emoji=new_emoji , owner_id=owner_id)

        # Edit the message to confirm the update
        await callback_query.message.edit_text("✅ Успешное изменение названия и эмодзи клана.", parse_mode="HTML")


    # Define callback handler for canceling clan rename
    @dp.callback_query(lambda c: c.data == 'cancel_rename')
    async def process_cancel_rename(callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id

        randommessagebonus1 = random.choice(randommessagehelp)
        print("qqqqq9")
        if user_id not in user_message_rename or user_message_rename [ user_id ] != message_id:
            await callback_query.answer(randommessagebonus1)
            return
        # Edit the message to indicate cancellation
        await callback_query.answer('☑️ Переименование отменено')
        await callback_query.message.edit_text("☑️ Переименование клана отменено", parse_mode="HTML")

    if len(words) >= 2 and words [ 0 ].lower() == "мой" and words [ 1 ] == "клан":
        user_id = message.from_user.id
        clans = await db.get_all_clans()

        for clan in clans:
            clan_leader_id = int(clan [ 'owner' ])
            clan_name = clan.get('name')
            members_str = clan.get('members')
            clan_coins = clan.get('coins')
            clan_emoji = clan.get('emoji')

            if clan_coins is None:
                clan_coins = 0

            items_json = clan.get('items' , '{}')
            is_leader = user_id == clan_leader_id
            is_member = members_str and str(user_id) in members_str.split(',')

            if is_leader or is_member:
                try:
                    clan_storage = json.loads(items_json) if items_json else {}
                except json.JSONDecodeError:
                    clan_storage = {}

                if not clan_storage:
                    inventory_str = "пуст"
                else:
                    inventory_list = [ f"{i + 1}. {item_name} - {quantity}" for i , (item_name , quantity) in
                                       enumerate(clan_storage.items()) ]
                    inventory_str = "\n".join(inventory_list)

                members_list = members_str.split(',') if members_str else [ ]
                if clan_leader_id not in map(int , members_list):
                    members_list.append(clan_leader_id)
                num_members = len(members_list)

                leader_username = await db.get_user_username(clan_leader_id)
                formatted_clan_coins = f"{clan_coins:,.0f}".replace("," , ".")
                firstname_leader = await db.get_firstname_by_user_id(clan_leader_id)
                leader_link = f"<a href='tg://user?id={clan_leader_id}'>{firstname_leader}</a>" if not is_leader else 'Вы'

                war_status = await db.get_clan_war_status(clan_emoji)

                # Получаем статус приватности
                privacy_status_num = await db.get_clan_private_status(clan_emoji)
                privacy_status = "🔴 Приватный клан" if privacy_status_num == 1 else "🟢 Публичный клан" if privacy_status_num == 0 else "🔐 Не определен"

                # Получаем список заместителей
                zam_ids = await db.get_clan_zam_list(clan_emoji)
                zam_list_str = await db.get_zam_info(zam_ids)

                # Отладка: выводим статус приватности и список заместителей
                print(f"Статус приватности клана {clan_emoji}: {privacy_status}")
                print(f"Список заместителей для клана {clan_emoji}: {zam_ids}")
                print(f"Строка с заместителями для клана {clan_emoji}: {zam_list_str}")

                # Изначально создаем клавиатуру с кнопкой "Настройки"
                keyboard = InlineKeyboardMarkup()

                if is_leader:
                    settings_button = InlineKeyboardButton("⚙️ Настройки" , callback_data=f"setclan:{clan_emoji}")
                    keyboard.add(settings_button)
                    attacking_clan_emoji = await db.get_clan_at(clan_emoji)
                    is_attacking = await db.is_clan_in_war(clan_emoji)

                    if is_attacking:  # Клан находится в состоянии войны
                        if attacking_clan_emoji:  # Клан является атакующим
                            war_keyboard = create_war_keyboard(clan_emoji)
                            keyboard.inline_keyboard.extend(war_keyboard.inline_keyboard)  # Добавляем кнопки войны
                        else:  # Клан не является атакующим
                            surrender_keyboard = create_surrender_keyboard(clan_emoji)
                            keyboard.inline_keyboard.extend(
                                surrender_keyboard.inline_keyboard)  # Добавляем кнопки сдачи

                # Формируем строку с заместителями только если заместители есть
                zam_line = f"⚜️ Заместители : <b>{zam_list_str}</b>\n" if zam_list_str and zam_list_str != "Нет заместителей" else ""

                # Отправляем сообщение с клавиатурой
                sent_moiclan = await message.reply(
                    f"<code>{clan_emoji}</code> <b>{clan_name}</b>\n\n"
                    f"<b>{privacy_status}</b>\n"
                    f"👑 Лидер : <b>{leader_link}</b>\n"
                    f"{zam_line}"
                    f"⚔️ {war_status}\n"
                    f"⭐️ Очки рейтинга : <b>{formatted_clan_coins}</b>\n"
                    f"🥷 Кол-во участников : <b>{num_members}</b>\n",
                      # Добавляем строку с заместителями, если есть
                    parse_mode="HTML" , disable_web_page_preview=True , reply_markup=keyboard)

                user_message_moiclan [ user_id ] = sent_moiclan.message_id
                return

        await message.reply("⚠️ Вы не состоите в клане.")

    user_id = message.from_user.id
    message_text = message.text.lower()
    words = message_text.split()
    if len(words) > 1 and words [ 0 ] in [ "клан" , "клановая","раздать" ] and words [ 1 ] in [ "раздача","клану" ]:
        try:
            # Обработка возможных форматов
            if words [ -1 ] == "кут":
                amount = int(words [ -2 ])
            elif words [ -1 ].isdigit():
                amount = int(words [ -1 ])
            elif words [ -2 ] == "кут" and words [ -1 ].isdigit():
                amount = int(words [ -1 ])
            elif words [ -1 ].isdigit() and words [ -2 ] in [ "кут" ]:
                amount = int(words [ -1 ])
            else:
                await message.reply("🔄 Ошибка: Неверный формат суммы.")
                return
        except ValueError:
            await message.reply("🔄 Ошибка: Неверный формат суммы.")
            return

        # Получаем информацию о клане
        clan_info = await db.get_clan_by_user_id(user_id)

        # Проверяем наличие ключа 'emoji' и валидность данных
        if not clan_info or 'emoji' not in clan_info:
            await message.reply("🛠 Не удалось найти информацию о вашем клане.")
            return

        clan_id = clan_info [ 'emoji' ]  # Используем эмодзи для идентификации клана

        # Проверяем, что пользователь является лидером клана
        clan_info = await db.get_clan_by_user_id(user_id)

        if not clan_info:
            await message.answer("🛠 Вы не являетесь членом какого-либо клана.")
            return

        # Проверка, является ли пользователь лидером клана
        if clan_info.get('owner') != user_id:
            await message.answer("🛠 Вы не являетесь лидером клана.")
            return

        # Получаем баланс владельца клана
        owner_balance = await db.get_user_balance(user_id)

        # Проверка корректности данных
        if not isinstance(owner_balance , int):
            await message.reply("🔄 Ошибка: Неверный формат данных о балансе.")
            return

        if owner_balance < amount:
            await message.reply("❌ Недостаточно средств для раздачи.")
            return

        # Получаем членов клана
        clan_members = clan_info.get('members' , [ ])

        if not clan_members or not isinstance(clan_members , list):
            await message.reply("🛠 В вашем клане нет участников.")
            return

        num_members = len(clan_members)
        if num_members == 0:
            await message.reply("🛠 В вашем клане нет участников.")
            return

        # Вычисляем сумму для каждого участника
        amount_per_member = amount / num_members

        win_amount_rounded1111 = round(amount_per_member)
        win_amount_rounded111 = round(amount)
        formatted_win_amount34121231241241241412 = "{:,.0f}".format(win_amount_rounded111).replace(',' , '.')

        # Проверяем, что сумма на участника больше 0
        if amount <= 19:
            await message.reply("🛠 Сумма раздачи должна быть больше 20 кут")
            return

        # Создаем инлайн клавиатуру для подтверждения
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(
                text="Отменить" , callback_data=f"rahdachaclancancel_{message.message_id}") , InlineKeyboardButton(
                text="Раздать" ,
                callback_data=f"rahdachaclandistribute_{win_amount_rounded1111}_{clan_id}_{user_id}_{message.message_id}"))

        # Отправляем сообщение с кнопками
        sent_ras = await message.reply(
            f"✅ Клановая раздача на <b>{formatted_win_amount34121231241241241412} кут</b> " , reply_markup=markup, parse_mode="HTML")

        user_ras [ user_id ] = sent_ras.message_id

    # Проверка команд, начиная с "клан инвест"

    if len(words) > 0 and words [ 0 ].lower() == "пригласить":
        if len(words) > 1 and words [ 1 ].lower() == "в" and len(words) > 2 and words [ 2 ].lower() == "клан":
            user_inviter_id = message.from_user.id

            # Проверяем, состоит ли пользователь в клане, как участник или владелец
            inviter_clan = await db.get_clan_by_user_id(user_inviter_id)
            if not inviter_clan:
                await message.reply("⚠️ Вы не состоите ни в одном клане.")
                return

            # Извлекаем эмодзи клана и другие данные
            clan_emoji = inviter_clan [ 'emoji' ]
            clan_name = inviter_clan [ 'name' ] or ""

            # Проверяем статус клана
            clan_info = await db.get_clan_info_by_emoji(clan_emoji)
            if not clan_info:
                await message.reply("🛠 Не удалось найти информацию о клане.")
                return

            private_status = clan_info [ 'private' ]
            zam_ids = await db.get_clan_zam_list(clan_emoji)
            is_leader = user_inviter_id == int(clan_info [ 'owner' ])
            is_zam = str(user_inviter_id) in zam_ids

            # Проверка на права приглашения
            if private_status == 1 and not is_zam and not is_leader:
                await message.reply("🛠 В приватный клан могут приглашать только заместители и лидер.")
                return

            user_to_invite_name = "Пользователь"
            user_inviter_name = await db.get_firstname_by_user_id(user_inviter_id)

            # Проверяем, является ли это сообщение ответом на другое сообщение
            if message.reply_to_message:
                user_to_invite_id = message.reply_to_message.from_user.id
                user_to_invite_name = await db.get_firstname_by_user_id(user_to_invite_id)
            else:
                if len(words) > 3:
                    user_to_invite_username = words [ 3 ].strip()

                    # Убираем префикс "https://t.me/" и символ '@' из имени пользователя
                    if user_to_invite_username.startswith("https://t.me/"):
                        user_to_invite_username = user_to_invite_username [ len("https://t.me/"): ]
                    user_to_invite_username = user_to_invite_username.lstrip('@')

                    # Ищем пользователя по username
                    user_to_invite = await db.get_user_by_username(user_to_invite_username)
                    if not user_to_invite:
                        await message.reply("<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> Пользователь не найден.")
                        return

                    user_to_invite_id = user_to_invite [ 0 ]
                    user_to_invite_name = db.get_firstname_by_user_id(user_to_invite_id)
                else:
                    await message.reply("🛠 Недостаточно данных для приглашения в клан.")
                    return

            # Проверяем, состоит ли пользователь, которого хотят пригласить, в каком-либо клане
            user_to_invite_clan = await db.get_clan_by_user_id(user_to_invite_id)
            if user_to_invite_clan:
                await message.reply("🛠 Этот пользователь уже состоит в клане.")
                return

            # Создаем клавиатуру с кнопками "Принять" и "Отклонить"
            btn_accept = InlineKeyboardButton(
                "Принять" , callback_data=f"clan_accept_entry_{clan_emoji}_{user_to_invite_id}")
            btn_reject = InlineKeyboardButton(
                "Отклонить" , callback_data=f"clan_reject_entry_{clan_emoji}_{user_to_invite_id}")
            reply_markup = InlineKeyboardMarkup().add(btn_reject , btn_accept)

            # Формируем сообщение для отправки в чат
            invited_message = f'🧩 <a href="tg://user?id={user_to_invite_id}">{user_to_invite_name}</a>'
            invited_message += f' вас пригласили в клан <code>{clan_emoji}</code> <b>{clan_name}</b>'

            # Если сообщение не является ответом, отправляем сообщение в тот же чат, иначе в ответ на исходное сообщение
            if message.reply_to_message:
                await message.reply_to_message.reply(
                    invited_message , parse_mode="HTML" , disable_web_page_preview=True ,
                    reply_markup=reply_markup)
            else:
                await message.reply(
                    invited_message , parse_mode="HTML" , disable_web_page_preview=True ,
                    reply_markup=reply_markup)

    if len(words) > 1 and words [ 0 ].lower() in [ "клан" , "покинуть" ] and words [ 1 ].lower() in [ "покинуть" ,
                                                                                                      "выйти" ,
                                                                                                      "клан" ]:
        # Получаем идентификатор пользователя
        user_id = message.from_user.id

        # Ищем клан, в котором состоит пользователь
        clan_info = await db.get_clan_by_user_id(user_id)

        if not clan_info:
            # Если пользователь не состоит в клане
            await message.reply("⚠️ Вы не состоите в клане.")
            return

        # Получаем эмодзи клана и идентификатор владельца
        clan_emoji = clan_info [ 'emoji' ]
        owner_id = clan_info [ 'owner' ]

        # Проверяем, является ли пользователь создателем клана
        if user_id == owner_id:
            await message.reply("⚠️ Вы являетесь создателем клана и не можете его покинуть")
            return

        # Проверяем, является ли пользователь участником клана
        if str(user_id) not in clan_info [ 'members' ]:
            await message.reply("⚠️ Вы не являетесь участником клана.")
            return

        # Если пользователь является участником клана, удаляем его из клана
        operation_result = await db.exit_user_from_clan(clan_emoji , user_id)

        if operation_result:
            await message.reply("☑️ Вы успешно покинули клан.")
        else:
            await message.reply("⚠️ Произошла ошибка при попытке покинуть клан.")








    #s
    if len(words) >= 4 and words [ 0 ].lower() == "выгнать" and words [ 1 ].lower() in ["из","с"] and words [
        2 ].lower() == "клана":
        username_to_remove = words [ 3 ].strip()
        print(f"Имя пользователя для удаления: {username_to_remove}")

        # Очищаем username от префиксов
        if username_to_remove.startswith("https://t.me/"):
            username_to_remove = username_to_remove [ len("https://t.me/"): ]
        username_to_remove = username_to_remove.lstrip('@')
        print(f"Username после очистки: {username_to_remove}")

        # Получаем ID текущего пользователя
        current_user_id = message.from_user.id
        print(f"ID текущего пользователя: {current_user_id}")

        # Получаем данные о клане
        user_clan_data = await db.get_clan_by_owner(current_user_id)
        print(f"Полученные данные о клане для текущего пользователя: {user_clan_data}")

        if not user_clan_data:
            await message.reply("⚠️ Вы не являетесь лидером клана.")
            print("Ошибка: текущий пользователь не является лидером клана.")
            return

        clan_emoji = user_clan_data [ 1 ]  # Получаем эмодзи клана
        print(f"Эмодзи клана: {clan_emoji}")

        # Получаем участников клана по эмодзи
        members = await db.get_clan_members(clan_emoji)
        print(f"Члены клана до удаления: {members}")

        # Получаем данные пользователя по username
        user_to_remove = await db.get_user_by_username(username_to_remove)
        print(f"Результаты запроса для пользователя '{username_to_remove}': {user_to_remove}")

        if user_to_remove is None:
            await message.reply("⚠️ Не удалось найти пользователя.")
            print(f"Ошибка: пользователь с username '{username_to_remove}' не найден.")
            return

        # Извлекаем ID пользователя
        user_to_remove_id = user_to_remove.get('user_id')
        if user_to_remove_id is None:
            await message.reply("⚠️ Не удалось получить ID пользователя.")
            print(f"Ошибка: не удалось получить ID пользователя для '{username_to_remove}'.")
            return

        print(f"ID пользователя для удаления: {user_to_remove_id}")

        # Преобразуем ID пользователя к строке
        user_to_remove_id_str = str(user_to_remove_id)

        if not members:
            await message.reply("⚠️ Клан пуст или не существует.")
            print("Ошибка: Клан пуст или не существует.")
            return

        # Преобразуем ID членов клана к строкам для сравнения
        members = [ str(member) for member in members ]
        print(f"Члены клана после преобразования в строки: {members}")

        if user_to_remove_id_str not in members:
            await message.reply("⚠️ Пользователь не является участником клана.")
            print(f"Ошибка: пользователь с ID {user_to_remove_id} не найден среди членов клана.")
            return

        # Удаляем пользователя из клана
        members.remove(user_to_remove_id_str)
        await db.update_clan_members(clan_emoji , members)
        print(f"Члены клана после удаления: {members}")

        # Получаем имя пользователя для ответа
        firstnameleader = await db.get_firstname_by_user_id(user_to_remove_id)
        print(f"Имя пользователя для ответа: {firstnameleader}")

        await message.reply(
            f"✅ Пользователь <a href='tg://user?id={user_to_remove_id}'>{firstnameleader}</a> успешно удален из клана." ,
            parse_mode="HTML" , disable_web_page_preview=True)
        print("Ответ отправлен пользователю.")

#wqda

    if len(words) > 1 and words [ 0 ].lower() in [ "клан" , "Клан" , "Пользователи" , "пользователи" ] and words [
        1 ].lower() in [ "пользователи" , "клана" ]:
        # Получаем идентификатор пользователя, который вызывает функцию
        user_id = message.from_user.id

        # Ищем клан, в котором находится пользователь
        clan_info = await db.get_clan_by_user_id(user_id)

        if not clan_info:
            await message.reply("🛠 Вы не состоите ни в одном клане.")
        else:
            # Извлекаем информацию о клане
            clan_emoji = clan_info [ 'emoji' ]
            clan_name = clan_info [ 'name' ]
            owner_id = clan_info [ 'owner' ]

            # Преобразуем строки в списки, если данные не пустые и строковые
            members_ids = clan_info [ 'members' ].split(',') if isinstance(clan_info [ 'members' ] , str) and \
                                                                clan_info [ 'members' ] else [ ]
            zam_ids = clan_info [ 'zam' ].split(',') if isinstance(clan_info [ 'zam' ] , str) and clan_info [
                'zam' ] else [ ]

            # Получаем имена пользователей для каждого из участников, фильтруем `None` и пустые строки
            owner_name = await db.get_firstname_by_user_id(owner_id)
            zam_names = [ await db.get_firstname_by_user_id(zam_id) for zam_id in zam_ids if
                          await db.get_firstname_by_user_id(zam_id) ]
            member_names = [ await db.get_firstname_by_user_id(member_id) for member_id in members_ids ]

            # Формируем сообщение с информацией о пользователях клана
            message_text = f"<b><code>{clan_emoji}</code> {clan_name} </b>\n\n"
            message_text += f"👑 <b>Создатель :</b>\n- <a href='tg://user?id={owner_id}'>{owner_name}</a>\n"

            # Добавляем заместителей, если они есть и не содержат `None`
            if zam_names:
                message_text += "\n🛡️ <b>Заместители :</b>\n"
                for zam_name , zam_id in zip(zam_names , zam_ids):
                    message_text += f"- <a href='tg://user?id={zam_id}'>{zam_name}</a>\n"

            # Добавляем участников с указанием количества и кнопками навигации, если участников больше 1
            if member_names:
                page = 0
                total_pages = math.ceil(len(members_ids) / ITEMS_user_PER_PAGE)
                paginated_members = member_names [ :ITEMS_user_PER_PAGE ]
                message_text += f"\n👥 <b>Участники [{len(member_names)}] :</b>\n"
                message_text += "\n".join(
                    [ f"- <a href='tg://user?id={members_ids [ i ]}'>{name}</a>" for i , name in
                      enumerate(paginated_members) ])

                # Создаем кнопки навигации
                if total_pages > 1:
                    navigation_buttons = get_user_navigation_buttons(page , total_pages)
                    markup = InlineKeyboardMarkup(row_width=2)
                    markup.add(*navigation_buttons)
                    markup.add(InlineKeyboardButton(text="✖️ Закрыть" , callback_data="clan_close_message"))

                    # Отправляем сообщение с кнопками
                    user_bebebe2222 = await message.reply(message_text , parse_mode="HTML" , reply_markup=markup)

                    user_bebebe [ user_id ] = user_bebebe2222.message_id

                else:
                    # Отправляем сообщение без кнопок, если только одна страница
                    await message.reply(message_text , parse_mode="HTML")









    #продолжение кода тут


    if len(words) > 1 and words [ 0 ].lower() in [ "клан" , "Клан","Удалить","удалить","Удаление","удаление" ] and words [ 1 ].lower() in ["удалить","клана","клан"]:
        user_id = message.from_user.id
        user_id = message.from_user.id  # Получаем идентификатор пользователя из сообщения
        clan_info = await db.get_clan_by_user_id(user_id)  # Получаем информацию о клане пользователя

        if not clan_info:
            await message.reply("🛠 Вы не состоите ни в одном клане.")
        else:
            # Извлекаем информацию о клане
            clan_emoji = clan_info [ 'emoji' ]
            clan_name = clan_info [ 'name' ]


            # Создаем инлайн-клавиатуру с кнопками в ряд
            inline_kb = InlineKeyboardMarkup(row_width=2)
            inline_kb.add(
                InlineKeyboardButton(text="Отмена" , callback_data="cancel_delete"),
                InlineKeyboardButton(text="Удалить" , callback_data=f"delete_{clan_emoji}"))

            # Отправляем вопрос о согласии на удаление клана в чате, где вызвали функцию
            sent_deleteclan = await message.answer(
                f"☑️ Удаление клана <code>{clan_emoji}</code> <b>{clan_name}</b>.\n🛠 Очки рейтинга клана будут поделены между другими кланами" , reply_markup=inline_kb , parse_mode="HTML")
            user_message_deleteclan [ user_id ] = sent_deleteclan.message_id







    #s


















#121

    words = message.text.split()

    if len(words) < 3 or words [ 0 ].lower() != "атаковать" or words [ 1 ].lower() != "клан":

        return

    user_id = message.from_user.id
    chat_id = message.chat.id  # Получаем ID текущего чата

    # Проверяем, состоит ли пользователь в каком-либо клане или является его владельцем
    clan = await db.find_clan_by_member_or_owner(user_id)

    if not clan:
        await message.reply("🛠 Вы не состоите в клане.")
        return

    clan_name , clan_emoji , clan_owner = clan

    # Проверяем, является ли пользователь лидером клана
    if clan_owner != user_id:
        await message.reply(f"🛠 Вы не являетесь лидером клана.")
        return

    # Определяем клан, на который идет атака
    target_clan_emoji = words [ 2 ]

    # Проверяем, существует ли целевой клан
    target_clan = await db.find_clan_by_emoji(target_clan_emoji)

    if not target_clan:
        await message.reply("🛠 Клан не найден.")
        return

    target_clan_name , target_clan_owner = target_clan [ 2 ] , target_clan [ 3 ]

    # Проверяем, не атакует ли пользователь свой собственный клан
    if clan_emoji == target_clan_emoji:
        await message.reply("🛠 Вы не можете атаковать свой собственный клан.")
        return

    # Проверяем статус битвы для атакующего и целевого клана
    attacking_clan_attack_status = await db.get_clan_attack_status(clan_emoji)
    target_clan_attack_status = await db.get_clan_attack_status(target_clan_emoji)

    if attacking_clan_attack_status == 1:
        await message.reply("🛠 Ваш клан уже участвует в битве.")
        return

    if target_clan_attack_status == 1:
        await message.reply(f"🛠 Клан '<b><code>{target_clan_emoji}</code> {target_clan_name}</b>' уже участвует в битве.", parse_mode="HTML")
        return

    # Проверяем рейтинги
    clan_rating = await db.get_clan_rating(clan_emoji)
    target_clan_rating = await db.get_clan_rating(target_clan_emoji)

    if clan_rating < 100 or target_clan_rating < 100:
        await message.reply("🛠 Для атаки оба клана должны иметь минимум 100 очков рейтинга.")
        return

    # Создаем клавиатуру с кнопками
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Отступить" , callback_data=f"retreat_{clan_emoji}_{target_clan_emoji}") ,
        types.InlineKeyboardButton("В Атаку!" , callback_data=f"attack_{clan_emoji}_{target_clan_emoji}"))

    # Формируем сообщение с информацией о целевом клане
    message_text = (f"⚔️ Вы уверены в атаке на клан <b><code>{target_clan_emoji}</code> {target_clan_name}</b>?")

    random_number1231 = random.randint(1 , 100)

    # Определяем, нужно ли отправлять стикер
    if random_number1231 > 50:
        sticker_id = 'CAACAgIAAxkBAXu2aWbNvCXMot45fR9LYOeLDOHQlyDEAAK1VAACUAhwSu6UMl3LhF5BNQQ'
        await message.reply_sticker(sticker_id)

    sent_attackclan = await message.reply(message_text , reply_markup=markup , parse_mode="HTML")
    user_message_attackclan [ user_id ] = sent_attackclan.message_id
#sada




















# sada
    #words = message.text.split()

    # Проверяем, что сообщение начинается с "пополнить" и "клан", и что третье слово - это сумма
    #if len(words) > 2 and words [ 0 ].lower() == "пополнить" and words [ 1 ].lower() == "клан" and words [
        #2 ].isdigit():
        #replenish_amount = int(words [ 2 ])  # Сумма пополнения
        #user_id = message.from_user.id  # Получаем идентификатор пользователя

        # Проверяем, состоит ли пользователь в клане
        #clan_info = db_clan.get_clan_by_user_id(user_id)

        #if not clan_info:
            #await message.reply("🛠 Вы не состоите ни в одном клане.")
            #return

        # Извлекаем информацию о клане
        #clan_emoji = clan_info [ 'emoji' ]
        #clan_name = clan_info [ 'name' ]

        # Проверяем текущий баланс пользователя
        #user_balance = db.get_balance(user_id)

        #if replenish_amount > user_balance:
            #await message.reply("🛠 Недостаточно средств.")
            #return

        # Получаем текущий баланс клана
        #clan_balance = db_clan.get_clan_balance(clan_emoji)

        # Обновляем баланс клана (добавляем сумму пополнения)
        #db_clan.update_clan_balance(clan_emoji , clan_balance + replenish_amount)

        # Обновляем баланс пользователя (отнимаем сумму пополнения)
        #await db.update_user_balance(user_id , user_balance - replenish_amount)

        # Сообщаем об успешном пополнении
        #await message.reply(f"💰 Вы успешно пополнили баланс своего клана {clan_name} на {replenish_amount} рейтинга")


































#sss




@dp.callback_query(lambda c: c.data.startswith("cancel_promotion:") or c.data.startswith("confirm_promotion:"))
async def promotion_callback_handler(callback_query: types.CallbackQuery , db):
    action , target_id = callback_query.data.split(':')
    target_id = int(target_id)
    initiator_id = callback_query.from_user.id

    clan_info = await db.get_clan_by_user_id(initiator_id)

    if not clan_info or clan_info [ 'owner' ] != initiator_id:
        await callback_query.message.edit_text("Произошла ошибка, попробуйте снова.")
        return

    if action == "cancel_promotion":
        await callback_query.message.edit_text("Повышение пользователя отменено.")
    elif action == "confirm_promotion":
        clan_info [ 'zam' ].append(str(target_id))
        clan_info [ 'members' ].remove(str(target_id))

        await db.update_clan_members_and_zam(clan_info [ 'emoji' ] , clan_info [ 'members' ] , clan_info [ 'zam' ])

        await callback_query.message.edit_text("Пользователь успешно повышен до заместителя клана.")












#sasda
@dp.callback_query(lambda c: c.data and c.data.startswith("retreat"))
async def handle_retreat(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqq10")
    if user_id not in user_message_attackclan or user_message_attackclan[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    clan_emoji = data[1]
    target_clan_emoji = data[2]

    print(f"Атака отменена пользователем. Клан: {clan_emoji}, Целевой клан: {target_clan_emoji}")

    random_number1231 = random.randint(1, 100)
    sticker_id = 'CAACAgIAAxkBAXu6UGbNxu77YAa7xmynm8Gf-PCN19pfAAIGWgACUjZxSsxMWsgp1094NQQ'  # Обновите этот идентификатор на правильный

    # Определяем, нужно ли отправлять стикер
    if random_number1231 > 50:
        try:
            await callback_query.message.bot.send_sticker(chat_id=callback_query.message.chat.id, sticker=sticker_id)
        except aiogram.utils.exceptions.BadRequest as e:
            print(f"Ошибка при отправке стикера: {e}")

    await callback_query.answer('Атака отменена')
    await callback_query.message.edit_text("☑️ Атака отменена")


@dp.callback_query(lambda c: c.data and c.data.startswith("attack"))
async def handle_attack(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqq11")
    if user_id not in user_message_attackclan or user_message_attackclan[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    attacking_clan_emoji = data[1]
    target_clan_emoji = data[2]

    # Проверяем данные для атакующего клана
    clan = await db.find_clan_by_emoji(attacking_clan_emoji)

    if not clan:
        await callback_query.message.edit_text("🛠 Ваш клан не найден. Атака невозможна.")
        return

    attacking_clan_name = clan[2]  # Название атакующего клана

    # Проверяем данные для целевого клана
    target_clan = await db.find_clan_by_emoji(target_clan_emoji)

    if not target_clan:
        await callback_query.message.edit_text("🛠 Клан для атаки не найден. Атака невозможна.")
        return

    target_clan_name, target_clan_owner = target_clan[2], target_clan[3]

    # Получаем статус атаки для обоих кланов
    attacking_clan_attack_status = await db.get_clan_attack_status(attacking_clan_emoji)
    target_clan_attack_status = await db.get_clan_attack_status(target_clan_emoji)

    if attacking_clan_attack_status == 1:
        await callback_query.message.edit_text("🛠 Ваш клан уже участвует в битве.")
        return

    if target_clan_attack_status == 1:
        await callback_query.message.edit_text(
            f"🛠 Клан {target_clan_name} ({target_clan_emoji}) уже участвует в битве.")
        return

    try:
        # Обновляем статус атаки для обоих кланов
        await db.update_clan_attack_status(attacking_clan_emoji, 1)
        await db.update_clan_attack_status(target_clan_emoji, 1)

        # Обновляем столбец clanattack для обоих кланов
        await db.update_clan_attackclan(attacking_clan_emoji, target_clan_emoji)  # Атакующий клан указывает целевой
        await db.update_clan_attackclan(target_clan_emoji, attacking_clan_emoji)  # Целевой клан указывает атакующий

        await db.update_clan_at(attacking_clan_emoji , target_clan_emoji)
    except Exception as e:
        print(f"Ошибка при обновлении статуса атаки: {e}")
        await callback_query.message.edit_text("🛠 Не удалось обновить статус атаки. Обратитесь к создателю")
        return

    # Получаем список участников целевого клана
    target_clan_members_info = await db.get_clan_members_and_owner(target_clan_emoji)

    if not target_clan_members_info:
        print("Не удалось получить информацию о членах целевого клана.")
        await callback_query.message.edit_text("🛠 Не удалось получить информацию о членах целевого клана.")
        return

    target_clan_members, target_clan_owner = target_clan_members_info

    if isinstance(target_clan_members, list):
        target_clan_members.append(target_clan_owner)
    else:
        target_clan_members = [target_clan_owner]

    # Формируем сообщение для всех участников целевого клана
    attack_message = f"⚔️ Клан <b>'<code>{attacking_clan_emoji}</code> {attacking_clan_name}'</b> атакует ваш клан!"

    for member_id in target_clan_members:
        if member_id:  # Проверяем, что member_id не пустой
            try:
                await bot1.send_message(member_id, attack_message, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка при отправке уведомления пользователю {member_id}: {e}")

    print(f"Атака начата на клан {target_clan_emoji}. Статус атаки обновлен.")
    random_number1231 = random.randint(1, 100)

    # Определяем, нужно ли отправлять стикер
    if random_number1231 > 50:
        sticker_id = 'CAACAgIAAxkBAXu6gmbNx34glhtdgwaDyD3KhrcAAUGMLAACFFQAAi-iaUpZ0U9Z_gdd9jUE'
        try:
            await callback_query.message.bot.send_sticker(chat_id=callback_query.message.chat.id, sticker=sticker_id)
        except aiogram.utils.exceptions.BadRequest as e:
            print(f"Ошибка при отправке стикера: {e}")

    await callback_query.answer('Атака началась!')
    await callback_query.message.edit_text("⚔️ Атака начата! Удачи в бою!")























#121

# Handler for "Join" button clicks
@dp.callback_query(lambda c: c.data and c.data.startswith("qeclanjoin_"))
async def process_join_clan(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    message_id = callback_query.message.message_id
    print(f"[INFO] Message ID: {message_id}")

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqq12")
    if user_id not in user_message_joinclan or user_message_joinclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    clan_emoji = callback_query.data.split("_") [ 1 ]
    clan_name = await db.get_clan_name_by_emoji(clan_emoji)

    if clan_name is None:
        await callback_query.message.edit_text("⚠️ Клан с таким эмодзи не существует.")
        await callback_query.answer()
        return

    members = await db.get_clan_members(clan_emoji)

    if user_id in members:
        print(f"[WARNING] User {user_id} is already a member of clan {clan_emoji}")
        await callback_query.message.edit_text(f"☑️ Вы уже являетесь участником этого клана")
        return

    members.append(user_id)
    print(f"[INFO] Adding user {user_id} to clan {clan_name}")

    await db.update_clan_members(clan_emoji , members)

    await callback_query.message.edit_text(
        f"✅ Успешное присоединение к клану <code>{clan_emoji}</code> <b>{clan_name}</b>", parse_mode="HTML")
    await callback_query.answer('Успешное присоединение')


# Handler for "Cancel" button clicks
@dp.callback_query(lambda c: c.data and c.data.startswith("weclancancel_"))
async def process_cancel_clan(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    message_id = callback_query.message.message_id
    print(f"[INFO] Message ID: {message_id}")

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_joinclan or user_message_joinclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    clan_emoji = callback_query.data.split("_") [ 1 ]
    await callback_query.answer('☑️ Присоединение к клану отклонено')
    await callback_query.message.edit_text("☑️ Присоединение к клану отклонено")


@dp.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def process_delete_clan(callback_query: types.CallbackQuery):
    clan_emoji = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    print(f"Обработка удаления клана: emoji={clan_emoji}, пользователь={user_id}, сообщение={message_id}")

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqosakldaskdqq1")
    if user_id not in user_message_deleteclan or user_message_deleteclan[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        print(f"Пользователь {user_id} не авторизован для удаления клана или сообщение не совпадает.")
        return

    # Извлечение информации о клане
    clan_info = await db.get_clan_by_user_id(user_id)
    clan_name = clan_info['name']
    owner_id = clan_info['owner']

    # Получение данных о клане для расчета очков
    clan_coins = await db.get_clan_coins_by_emoji(clan_emoji)
    clans_data = await db.get_clans_data()
    total_clans = len(clans_data)

    if total_clans <= 1:
        print("Ошибка: Нет других кланов для распределения очков.")
        await callback_query.message.edit_text("⚠️ Нет других кланов для распределения очков.")
        return

    # Удаляем клан из базы данных
    response_message, creators_to_notify = await db.sell_clan(clan_emoji, user_id, user_id)

    if response_message.startswith("⚠️"):
        await callback_query.message.edit_text(response_message)
        return

    # Распределение очков рейтинга
    distribute_message, creators_points, win_amount_rounded = await db.distribute_clan_points(clan_emoji, clan_coins)

    # Удаляем сообщение с кнопками
    await callback_query.message.edit_text('🪦 Ваш клан успешно удален')
    print(f"Сообщение с кнопками удалено для клана {clan_emoji}.")
    print(f"Выплаченная сумма: {win_amount_rounded}")
    win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
    # Отправляем результат удаления создателю клана в личные сообщения
    if creators_points:
        for creator_emoji, (creator_name, _) in creators_points.items():
            # Поиск user_id по emoji клана
            creator_id = await db.get_user_id_by_clan_emoji(creator_emoji)
            if creator_id:
                if win_amount_rounded > 0:  # Проверка, что сумма больше 0
                    message = f"🌟 Ваш клан получил <b>{win_amount_formatted}</b> очков рейтинга благодаря удалению другого клана!"
                    try:
                        await bot1.send_message(creator_id, message, parse_mode="HTML")
                        print(f"Сообщение отправлено пользователю {creator_id}: {message}")
                    except Exception as e:
                        print(f"Не удалось отправить сообщение пользователю {creator_id}: {e}")
                else:
                    print(f"Сумма очков для клана {creator_name} не положительна, сообщение не отправлено.")
            else:
                print(f"Создатель клана с emoji {creator_emoji} не найден.")

# Обработчик для нажатия на кнопку "Отмена"
@dp.callback_query(lambda c: c.data == "cancel_delete")
async def process_cancel_delete(callback_query: types.CallbackQuery):
    # Удаляем сообщение с кнопками
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id


    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqmoasdpqlqq1")
    if user_id not in user_message_deleteclan or user_message_deleteclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    await callback_query.answer('☑️ Удаление клана отменено')
    await callback_query.message.edit_text("☑️ Удаление клана отменено")

    # Отправляем сообщение об отмене в том же чате



# Функция для отправки вопроса о согласии на удаление клана
async def ask_for_clan_deletion(callback_query: types.CallbackQuery, clan_name: str):
    # Создаем инлайн-кнопки для подтверждения или отмены
    inline_kb = InlineKeyboardMarkup(row_width=2)  # Кнопки в ряд
    inline_kb.add(
        InlineKeyboardButton(text="Удалить", callback_data=f"delete_{clan_name}"),
        InlineKeyboardButton(text="Отменить", callback_data="cancel_delete")
    )

    # Отправляем сообщение с вопросом о согласии на удаление клана в том же чате
    await callback_query.message.reply(f"🤯 Удаление клана <b>{clan_name}</b>", reply_markup=inline_kb, parse_mode="HTML")











@dp.callback_query(lambda c: c.data.startswith('clan_accept_entry_') or c.data.startswith('clan_reject_entry_'))
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data.split('_')
    clan_emoji = data[3]
    user_to_invite_id = int(data[4])

    try:
        print(f"[DEBUG] Retrieving clan name for emoji: {clan_emoji}")
        clan_name = await db.get_clan_name_by_emoji(clan_emoji) or ""  # Если имя клана None, заменяем на пустую строку
        if clan_name:
            print(f"[DEBUG] Clan name found: {clan_name}")
        else:
            print(f"[DEBUG] Clan name not found for emoji: {clan_emoji}")

    except Exception as e:
        await callback_query.answer("Произошла ошибка при получении информации о клане.")
        print(f"Ошибка при получении названия клана по эмодзи: {e}")
        return

    if user_id != user_to_invite_id:
        await callback_query.answer("Это приглашение не для вас.")
        return

    await callback_query.answer()

    if callback_query.data.startswith("clan_accept_entry_"):
        try:
            await db.add_user_to_clan(clan_emoji, user_to_invite_id)
            #await callback_query.message.edit_reply_markup(reply_markup=None)
            await callback_query.message.edit_text(
                f"✅ Успешное вступление в клан <code>{clan_emoji}</code> <b>{clan_name}</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка при добавлении пользователя в клан: {e}")
            await callback_query.answer("Произошла ошибка при обработке приглашения. Пожалуйста, попробуйте снова.")

    elif callback_query.data.startswith("clan_reject_entry_"):
        empty_markup = types.InlineKeyboardMarkup()
        await callback_query.message.edit_text(
            f"☑️ Приглашение в клан <code>{clan_emoji}</code> <b>{clan_name}</b> отклонено",
            reply_markup=empty_markup,
            parse_mode="HTML"
        )




@dp.callback_query(lambda c: c.data and c.data.startswith('clan_page_'))
async def process_pagination(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    # Проверка на случайные сообщения или авторизацию, если необходимо
    # Например, замените это проверкой на ваш конкретный случай
    if user_id not in user_clan_control or user_clan_control [ user_id ] != message_id:
        await callback_query.answer("⚠️ Вы не можете управлять этими кнопками")
        return

    # Определяем номер страницы из callback_data
    page = int(callback_query.data.split('_') [ 2 ])

    # Получаем список всех кланов
    clans = await db.get_all_clans()

    # Определяем количество элементов на одной странице
    items_per_page = 10
    total_pages = math.ceil(len(clans) / items_per_page)

    # Создаем текст для текущей страницы
    text = "📋 Список кланов :\n"

    # Определяем начало и конец списка для текущей страницы
    start_index = page * items_per_page
    end_index = min(start_index + items_per_page , len(clans))

    # Добавляем информацию о каждом клане на текущей странице
    for clan in clans [ start_index:end_index ]:
        clan_name = clan [ 'name' ]
        owner_id = clan [ 'owner' ]
        members_str = clan [ 'members' ]  # Предполагаем, что это строка с ID участников, разделенными запятыми

        # Преобразуем строку с участниками в список
        members_list = members_str.split(',') if members_str else [ ]

        # Добавляем владельца клана в список участников, если его еще там нет
        if str(owner_id) not in members_list:
            members_list.append(str(owner_id))

        # Считаем количество участников
        members_count = len(members_list)

        # Получаем эмодзи клана
        clan_emoji = await db.get_clan_emoji(clan_name)

        # Определяем правильное окончание для слова "участник/участника/участников"
        if members_count == 1:
            participant_word = "участник"
        elif 2 <= members_count <= 4:
            participant_word = "участника"
        else:
            participant_word = "участников"

        # Формируем строку для текущего клана
        text += f"\n<code>{clan_emoji}</code> {clan_name} ~ {members_count} {participant_word}"

    # Создаем кнопки навигации
    navigation_buttons = clan_get_navigation_buttons(page , total_pages)
    markup = InlineKeyboardMarkup(row_width=2).add(*navigation_buttons)

    # Добавляем кнопку закрытия, если нужно
    close_button = InlineKeyboardButton(text="Закрыть" , callback_data="clan_list_close")
    markup.add(close_button)

    # Обновляем сообщение с новым списком кланов и кнопками навигации
    await callback_query.message.edit_text(
        text=f'{text}' , parse_mode="HTML" , reply_markup=markup)

    # Подтверждаем получение нажатия кнопки
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == 'clan_list_close')
async def close_clan_list(callback_query: types.CallbackQuery):
    # Удаляем сообщение с кланами
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    if user_id not in user_clan_control or user_clan_control [ user_id ] != message_id:
        await callback_query.answer("⚠️ Вы не можете удалить сообщение другого пользователя ")
        return
    await callback_query.answer('☑️ Сообщение удалено')
    await callback_query.message.delete()





# Обработка инлайн кнопок
@dp.callback_query(lambda c: c.data.startswith("finish_battle"))
async def process_finish_battle(callback_query: CallbackQuery):
    clan_emoji = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqq,pdqlwqqq1")
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Извлекаем данные о клане из базы данных
    clan_info = await db.get_clan_info_by_emoji(clan_emoji)

    if clan_info:
        # Показываем кнопки "Отменить" и "Завершить"
        sticker_id = 'CAACAgIAAxkBAXvLlmbN9ppOXlySIMEM9s0JF3hFdVsyAAKxVQACsk1wShQtNsxWwz85NQQ'
        await callback_query.message.answer_sticker(sticker_id)
        await callback_query.message.edit_text(
            "🛡 Вы уверены, что хотите завершить битву?",
            reply_markup=create_confirm_keyboard(clan_emoji)
        )
    else:
        await callback_query.message.edit_text("🛠 Не удалось найти информацию о клане.")

@dp.callback_query(lambda c: c.data.startswith("confirm_finish"))
async def process_confirm_finish(callback_query: CallbackQuery):
    clan_emoji = callback_query.data.split(':')[1]

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    print("qqqqsqkdoqsdqlq1")
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    # Завершаем битву
    await db.clear_clan_at(clan_emoji)
    await db.finish_clan_war(clan_emoji)
    await callback_query.message.edit_text(
        "✅ Битва завершена. Ваш клан больше не атакует и не находится под атакой.")
    await callback_query.answer('Битва завершена!')
    sticker_id = 'CAACAgIAAxkBAXvSRGbODcIfVOa42zdc1nGQDIzHoocGAALHWAAC7ntwSvfx2Y-1CprCNQQ'
    await callback_query.message.answer_sticker(sticker_id)

@dp.callback_query(lambda c: c.data.startswith("cancel_finish"))
async def process_cancel_finish(callback_query: CallbackQuery):
    clan_emoji = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Получаем информацию о клане
    clan_info = await db.get_clan_info_by_emoji(clan_emoji)
    if not clan_info:
        await callback_query.message.edit_text("🛠 Не удалось найти информацию о клане.")
        return

    members_str = clan_info['members']
    clan_leader_id = clan_info['owner']
    is_leader = user_id == clan_leader_id

    # Проверка, является ли пользователь лидером клана
    members_list = members_str.split(',') if members_str else []
    if clan_leader_id not in map(int, members_list):
        members_list.append(clan_leader_id)
    num_members = len(members_list)

    # Получаем дополнительную информацию
    firstname_leader = await db.get_firstname_by_user_id(clan_leader_id)
    leader_link = f"<a href='tg://user?id={clan_leader_id}'>{firstname_leader}</a>" if not is_leader else 'Вы'

    war_status = await db.get_clan_war_status(clan_emoji)
    attacking_clan_emoji = await db.get_clan_at(clan_emoji)
    is_attacking = await db.is_clan_in_war(clan_emoji)
    clan_coins = await db.get_clan_balance(clan_emoji)
    formatted_clan_coins = f"{clan_coins:,.0f}".replace(",", ".")

    # Получаем статус приватности
    privacy_status_num = await db.get_clan_private_status(clan_emoji)
    privacy_status = "🔴 Приватный клан" if privacy_status_num == 1 else "🟢 Публичный клан" if privacy_status_num == 0 else "🔐 Не определен"

    # Получаем список заместителей
    zam_ids = await db.get_clan_zam_list(clan_emoji)
    zam_list_str = await db.get_zam_info(zam_ids) if zam_ids else "Нет заместителей"

    # Логируем информацию для отладки
    print(f"Статус приватности клана {clan_emoji}: {privacy_status}")
    print(f"Список заместителей для клана {clan_emoji}: {zam_ids}")
    print(f"Строка с заместителями для клана {clan_emoji}: {zam_list_str}")

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup()

    if is_leader:
        settings_button = InlineKeyboardButton("⚙️ Настройки", callback_data=f"setclan:{clan_emoji}")
        keyboard.add(settings_button)

        if is_attacking:  # Клан находится в состоянии войны
            if attacking_clan_emoji:  # Клан является атакующим
                war_keyboard = create_war_keyboard(clan_emoji)
                keyboard.inline_keyboard.extend(war_keyboard.inline_keyboard)  # Добавляем кнопки войны
            else:  # Клан не является атакующим
                surrender_keyboard = create_surrender_keyboard(clan_emoji)
                keyboard.inline_keyboard.extend(surrender_keyboard.inline_keyboard)  # Добавляем кнопки сдачи

    # Формируем строку с заместителями
    zam_line = f"⚜️ Заместители : <b>{zam_list_str}</b>\n" if zam_list_str and zam_list_str != "Нет заместителей" else ""

    # Отправляем сообщение с информацией о клане и клавиатурой
    await callback_query.message.edit_text(
        f"<code>{clan_info['emoji']}</code> <b>{clan_info['name']}</b>\n\n"
        f"<b>{privacy_status}</b>\n"
        f"👑 Лидер : <b>{leader_link}</b>\n"
        f"{zam_line}"
        f"⚔️ {war_status}\n"
        f"⭐️ Очки рейтинга : <b>{formatted_clan_coins}</b>\n"
        f"🥷 Кол-во участников : <b>{num_members}</b>\n",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard
    )



@dp.callback_query(lambda c: c.data.startswith("surrender_battle"))
async def process_surrender(callback_query: CallbackQuery):
    clan_emoji = callback_query.data.split(':')[1]

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    defending_clan_coins = await db.get_clan_coins_by_emoji(clan_emoji) or 0
    surrender_penalty = round(defending_clan_coins / 2)
    formatted_win_amount = "{:,.0f}".format(surrender_penalty).replace(',' , '.')
    # Показать сообщение с кнопками "Отменить" и "Сдаться клану"
    await callback_query.message.edit_text(
        f"🛡 Вы уверены, что хотите сдаться?\n⭐️ Вы передадите атакующему клану <b>{formatted_win_amount}</b> кут", parse_mode="HTML",
        reply_markup=surrender_confirm_keyboard(clan_emoji)
    )
    await callback_query.answer()
@dp.callback_query(lambda c: c.data.startswith("confirm_surrender"))
async def process_confirm_surrender(callback_query: CallbackQuery):
    clan_emoji = callback_query.data.split(':')[1]

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Получаем данные о кланах
    defending_clan_coins = await db.get_clan_coins_by_emoji(clan_emoji) or 0
    attacking_clan_emoji = await db.get_clan_attacker(clan_emoji)

    if not attacking_clan_emoji:
        await callback_query.message.edit_text(
            "🛠 Ошибка: Не удалось найти атакующий клан.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback_query.answer('🛠 Ошибка! Не удалось найти атакующий клан.')
        return

    # Делим очки рейтинга защищающегося клана на 3
    surrender_penalty = round(defending_clan_coins / 2)

    # Обновляем баланс защищающегося клана
    new_defending_clan_coins = defending_clan_coins - surrender_penalty
    await db.update_clan_coins(clan_emoji, new_defending_clan_coins)

    # Обновляем баланс атакующего клана
    attacking_clan_coins = await db.get_clan_coins_by_emoji(attacking_clan_emoji) or 0
    new_attacking_clan_coins = attacking_clan_coins + surrender_penalty
    await db.update_clan_coins(attacking_clan_emoji, new_attacking_clan_coins)

    # Завершаем битву и очищаем данные
    await db.clear_clan_at(clan_emoji)
    await db.clear_clan_attack(attacking_clan_emoji)
    await db.finish_clan_war(clan_emoji)

    # Отправляем сообщение о завершении битвы
    await callback_query.message.edit_text(
        "✅ Битва завершена. Ваш клан сдался. Очки рейтинга были переданы атакующему клану.",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback_query.answer('Битва завершена!')


@dp.callback_query(lambda c: c.data.startswith('demotion_cancel_'))
async def cancel_demotion(callback_query: types.CallbackQuery):
    target_id = callback_query.data.split('_') [ -1 ]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_ponizenie or user_message_ponizenie [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    if not clan_info:
        await callback_query.answer("Вы не состоите в клане.")
        return

    # Проверка, является ли пользователь лидером клана
    if clan_info [ 'owner' ] != user_id:
        await callback_query.answer("Вы не являетесь лидером клана.")
        return

    try:
        # Обновляем сообщение, чтобы указать, что понижение отменено
        await callback_query.message.edit_text("☑️ Понижение пользователя отменено.")
    except TelegramAPIError as e:
        if 'message is not modified' in str(e).lower():
            # Игнорируем ошибку, если сообщение не было изменено
            print(f"Сообщение не было изменено.")
        # Если сообщение не изменилось, ничего не делаем
        pass

    # Удаляем коллбэк из кэша
    await callback_query.answer("☑️ Понижение пользователя отменено.")


@dp.callback_query(lambda c: c.data.startswith('demotion_confirm_'))
async def confirm_demotion(callback_query: types.CallbackQuery):
    target_id = callback_query.data.split('_') [ -1 ]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_ponizenie or user_message_ponizenie [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    if not clan_info:
        await callback_query.answer("Вы не состоите в клане.")
        return

    # Проверка, является ли пользователь лидером клана
    if clan_info [ 'owner' ] != user_id:
        await callback_query.answer("Вы не являетесь лидером клана.")
        return

    # Получаем эмодзи клана
    clan_emoji = clan_info [ 'emoji' ]

    # Удаление идентификатора пользователя из списка заместителей
    success = await db.remove_zam(clan_emoji , target_id)

    if success:
        await callback_query.message.edit_text("✅ Понижение пользователя успешно выполнено.")
    else:
        await callback_query.message.edit_text("🛠 Не удалось выполнить понижение пользователя.")

    # Удаляем коллбэк из кэша
    await callback_query.answer("✅ Понижение пользователя успешно выполнено.")







#12312
@dp.callback_query(lambda c: c.data.startswith('promotion_cancel_'))
async def cancel_promotion(callback_query: types.CallbackQuery):
    target_id = callback_query.data.split('_') [ -1 ]
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_vusenie or user_message_vusenie [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return


    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    if not clan_info:
        await callback_query.answer("Вы не состоите в клане.")
        return

    # Проверка, является ли пользователь лидером клана
    if clan_info [ 'owner' ] != user_id:
        await callback_query.answer("Вы не являетесь лидером клана.")
        return

    try:
        # Обновляем сообщение, чтобы указать, что повышение отменено
        await callback_query.message.edit_text("☑️ Повышение пользователя отменено.")
    except TelegramAPIError as e:
        if 'message is not modified' in str(e).lower():
            # Игнорируем ошибку, если сообщение не было изменено
            print(f"Сообщение не было изменено.")
        # Если сообщение не изменилось, ничего не делаем
        pass

    # Удаляем коллбэк из кэша
    await callback_query.answer("☑️ Повышение пользователя отменено.")

# Обработчик кнопки "Повысить"
@dp.callback_query(lambda c: c.data.startswith('motion_confirm_'))
async def confirm_promotion(callback_query: types.CallbackQuery):
    target_id = int(callback_query.data.split('_')[-1])
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_vusenie or user_message_vusenie[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    if not clan_info:
        await callback_query.answer("Вы не состоите в клане.")
        return

    # Проверка, является ли пользователь лидером клана
    if clan_info['owner'] != user_id:
        await callback_query.answer("Вы не являетесь лидером клана.")
        return

    # Проверка, является ли целевой пользователь участником клана
    if str(target_id) not in clan_info['members']:
        await callback_query.answer("Пользователь не является участником вашего клана.")
        return

    # Проверка, не является ли целевой пользователь уже заместителем
    if await db.is_target_id_zam(clan_info['emoji'], target_id):
        await callback_query.answer("Этот пользователь уже является заместителем клана.")
        return

    # Добавляем идентификатор пользователя в список заместителей через функцию
    await db.add_zam_to_clan(clan_info['emoji'], target_id)

    try:
        # Обновляем сообщение, чтобы указать, что повышение успешно выполнено
        await callback_query.message.edit_text("✅ Пользователь успешно повышен на должность заместителя.")
    except TelegramAPIError as e:
        if 'message is not modified' in str(e).lower():
            # Игнорируем ошибку, если сообщение не было изменено
            print(f"Сообщение не было изменено.")
        # Если сообщение не изменилось, ничего не делаем
        pass


@dp.callback_query(lambda c: c.data.startswith('setclan:'))
async def process_settings(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    clan_emoji = callback_query.data.split(':')[1]  # Получение эмодзи клана из callback_data

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    # Проверяем, является ли пользователь лидером клана
    if not clan_info or clan_info['owner'] != user_id:
        await callback_query.answer("Вы не являетесь лидером клана.")
        return

    # Получаем статус приватности клана через метод get_clan_private_status
    private_status = await db.get_clan_private_status(clan_emoji)

    # Проверка наличия статуса приватности
    if private_status is None:
        await callback_query.answer("Ошибка получения статуса приватности клана.")
        return

    private_emoji = "🟢" if private_status else "🔴"  # Определяем эмодзи статуса

    # Создаем клавиатуру с кнопкой для изменения статуса приватности
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(f"{private_emoji} Приватность клана", callback_data=f"toggle_private:{clan_emoji}"))

    await callback_query.message.edit_text(
        "⚙️ Настройки клана", reply_markup=keyboard
    )

# Обработчик нажатия кнопки "Приватный клан"
@dp.callback_query(lambda c: c.data.startswith('toggle_private:'))
async def process_toggle_private(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    clan_emoji = callback_query.data.split(':')[1]  # Получение эмодзи клана из callback_data

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)

    # Проверяем, является ли пользователь лидером клана
    if not clan_info or clan_info['owner'] != user_id:
        await callback_query.answer("Только лидер клана может изменять настройки.")
        return

    # Создаем клавиатуру с кнопками "Отмена" и "Применить"
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Отмена", callback_data=f"cancel_finish:{clan_emoji}"),
        InlineKeyboardButton("Применить", callback_data=f"apply_change:{clan_emoji}")
    )

    await callback_query.message.edit_text(
        "🤫 Вы уверены, что хотите изменить статус клана?", reply_markup=keyboard
    )

# Обработчик нажатия кнопки "Применить"
@dp.callback_query(lambda c: c.data.startswith('apply_change:'))
async def process_apply_change(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_moiclan or user_message_moiclan [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    clan_emoji = callback_query.data.split(':') [ 1 ]  # Получение эмодзи клана из callback_data

    # Получаем информацию о владельце и участниках клана по эмодзи
    members_list , owner_id = await db.get_clan_members_and_owner(clan_emoji)

    if owner_id is not None:
        # Проверяем, что идентификатор владельца корректен
        try:
            owner_id = int(owner_id)
        except (ValueError , TypeError):
            await callback_query.answer("Некорректный идентификатор лидера клана.")
            return

        if owner_id == user_id:
            # Получаем текущий статус приватности
            current_private_status = 1 if members_list else 0  # Используйте фактический способ получения текущего статуса

            # Изменяем статус приватности в базе данных
            new_private_status = 1 if current_private_status == 0 else 0
            await db.update_clan_private_status(clan_emoji , new_private_status)  # Обновление статуса приватности

            await callback_query.message.edit_text("✅ Статус клана успешно изменён.")
        else:
            await callback_query.answer("Только лидер клана может изменять настройки.")
    else:
        await callback_query.answer("Клан не найден.")








#12131


@dp.callback_query(lambda c: c.data.startswith('inus_join_'))
async def process_reject_join(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    clan_emoji = data[2]
    user_id = data[3]

    # Получите информацию о клане и пользователе
    clan_info = await db.get_clan_info_by_emoji(clan_emoji)
    user_firstname = await db.get_firstname_by_user_id(user_id)  # Получение имени пользователя

    if clan_info:
        leader_id = int(clan_info['owner'])
        deputy_ids = await db.get_clan_zam_list(clan_emoji)
        if str(callback_query.from_user.id) == str(leader_id) or str(callback_query.from_user.id) in [str(deputy_id) for deputy_id in deputy_ids]:
            # Проверка, является ли пользователь уже членом клана
            if await db.user_in_clan(user_id):
                # Уведомление, что кто-то другой уже добавил пользователя
                await callback_query.answer("🛠 Этот пользователь уже был добавлен в клан другим пользователем", parse_mode=ParseMode.HTML)
            else:
                # Уведомление пользователя о том, что его запрос отклонен
                await bot1.send_message(
                    user_id,
                    f"❌ Ваш запрос на присоединение к клану <code>{clan_emoji}</code> <b>{clan_info['name']}</b> был отклонен.", parse_mode="HTML"
                )
                # Уведомление лидера или заместителей о том, что запрос был отклонен
                await callback_query.message.edit_text(
                    f"❌ Запрос на присоединение пользователя <a href='tg://user?id={user_id}'>{user_firstname}</a> к клану <code>{clan_emoji}</code> <b>{clan_info['name']}</b> был отклонен.", parse_mode=ParseMode.HTML
                )
        else:
            await callback_query.answer("🛠 У вас нет прав для отклонения этого запроса.")
    else:
        await callback_query.answer("🛠 Клан с таким эмодзи не найден.")




@dp.callback_query(lambda c: c.data.startswith('ept_join_'))
async def process_accept_join(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    clan_emoji = data[2]
    user_id = data[3]

    # Получите информацию о клане и пользователе
    clan_info = await db.get_clan_info_by_emoji(clan_emoji)
    user_firstname = await db.get_firstname_by_user_id(user_id)  # Получение имени пользователя

    if clan_info:
        leader_id = int(clan_info['owner'])
        deputy_ids = await db.get_clan_zam_list(clan_emoji)
        if str(callback_query.from_user.id) == str(leader_id) or str(callback_query.from_user.id) in [str(deputy_id) for deputy_id in deputy_ids]:
            # Проверка, является ли пользователь уже членом клана
            if await db.user_in_clan(user_id):
                # Уведомление, что кто-то другой уже добавил пользователя
                await callback_query.answer("🛠 Этот пользователь уже был добавлен в клан другим пользователем", parse_mode="HTML")
            else:
                # Добавление пользователя в клан
                await db.add_user_to_clan(clan_emoji, user_id)

                # Уведомление пользователя о том, что его запрос принят
                await bot1.send_message(
                    user_id,
                    f"🎉 Ваш запрос на присоединение к клану <code>{clan_emoji}</code> <b>{clan_info['name']}</b> был принят.", parse_mode="HTML"
                )
                # Уведомление лидера или заместителей о том, что запрос принят
                await callback_query.message.edit_text(
                    f"✅ Запрос на присоединение пользователя <a href='tg://user?id={user_id}'>{user_firstname}</a> к клану <code>{clan_emoji}</code> <b>{clan_info['name']}</b> был принят.", parse_mode=ParseMode.HTML
                )
        else:
            await callback_query.answer("🛠 У вас нет прав для принятия этого запроса.")
    else:
        await callback_query.answer("🛠 Клан с таким эмодзи не найден.")






@dp.callback_query(lambda c: c.data and c.data.startswith('user_page_'))
async def process_pagination(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    # Настройки для cooldown
    current_time = time.time()
    REST = 1.5

    # Проверяем, прошёл ли период отдыха для пользователя
    last_usage_time = user_cooldowns.get(user_id, 0)
    if current_time - last_usage_time < REST:
        remaining_time = REST - (current_time - last_usage_time)
        await callback_query.answer(f"⌚️ Пожалуйста, подождите {int(remaining_time)} секунд", show_alert=True)
        return
    user_cooldowns[user_id] = current_time  # Обновляем время последнего использования

    # Проверка правильности вызова по user_id и message_id
    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_bebebe or user_bebebe[user_id] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    # Получаем номер страницы из callback_data
    page = int(callback_query.data.split('_')[2])

    # Получаем информацию о клане пользователя
    clan_info = await db.get_clan_by_user_id(user_id)
    if not clan_info:
        await callback_query.answer("🛠 Вы не состоите ни в одном клане.")
        return

    # Извлекаем данные клана и участников
    clan_emoji = clan_info['emoji']
    clan_name = clan_info['name']
    owner_id = clan_info['owner']

    # Преобразуем строки участников в списки
    members_ids = clan_info['members'].split(',') if clan_info['members'] else []
    zam_ids = clan_info['zam'].split(',') if clan_info['zam'] else []

    # Подсчитываем количество страниц
    total_pages = math.ceil(len(members_ids) / ITEMS_user_PER_PAGE)

    # Генерация списка участников для текущей страницы
    start = page * ITEMS_user_PER_PAGE
    end = start + ITEMS_user_PER_PAGE
    paginated_members = members_ids[start:end]
    member_names = [await db.get_firstname_by_user_id(member_id) for member_id in paginated_members]

    # Формируем текст страницы участников
    member_list = "\n".join([f"- <a href='tg://user?id={member_id}'>{name}</a>" for member_id, name in zip(paginated_members, member_names)])
    text = f"👥 <b>Участники [{len(members_ids)}] :</b>\n{member_list}"

    # Создаем кнопки навигации
    navigation_buttons = get_user_navigation_buttons(page, total_pages)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(*navigation_buttons)
    markup.add(InlineKeyboardButton(text="✖️ Закрыть", callback_data="clan_close_message"))

    # Редактируем сообщение с участниками
    await callback_query.message.edit_text(
        text=text, parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=markup
    )


@dp.callback_query(lambda c: c.data == 'clan_close_message')
async def process_buy_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_bebebe or user_bebebe [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    await callback_query.answer('сообщение с пользователями клана удалено')
    await callback_query.message.delete()


@dp.callback_query(lambda c: c.data.startswith('rahdachaclancancel_'))
async def handle_clan_distribution_cancel(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_ras or user_ras [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    if len(data) < 2:
        await callback_query.answer("🔄 Ошибка: Неверный формат данных." , show_alert=True)
        return

    original_message_id = int(data [ 1 ])

    await callback_query.message.edit_text("☑️ Клановая раздача отменена" )
    await callback_query.answer("☑️ Клановая раздача отменена")


@dp.callback_query(lambda c: c.data.startswith('rahdachaclandistribute_'))
async def handle_clan_distribution_distribute(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_ras or user_ras[user_id] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    if len(data) < 5:
        await callback_query.answer("🔄 Неверный формат данных.", show_alert=True)
        return

    try:
        amount_per_member = float(data[1])
        clan_id = data[2]
        user_id = int(data[3])
        original_message_id = int(data[4])
    except (ValueError, IndexError):
        await callback_query.answer("🔄 Неверный формат данных.", show_alert=True)
        return

    clan_info = await db.get_clan_by_user_id(user_id)
    if not clan_info or clan_info['emoji'] != clan_id:
        await callback_query.message.edit_text("🛠 Клан не найден.")
        return

    owner_balance = await db.get_user_balance(user_id)
    if not isinstance(owner_balance, int):
        await callback_query.message.edit_text("🔄 Ошибка: Проблемы с балансом.")
        return

    clan_members_str = clan_info.get('members', '')
    if not clan_members_str:
        await callback_query.message.edit_text("⚠️ В клане нет участников.")
        return

    member_ids = clan_members_str.split(',')
    num_members = len(member_ids)
    if num_members == 0:
        await callback_query.message.edit_text("⚠️ В клане нет участников.")
        return

    total_amount = amount_per_member * num_members
    if owner_balance < total_amount:
        await callback_query.message.edit_text("❌ Недостаточно средств.")
        return

    win_amount_rounded1 = round(total_amount)
    await db.update_user_balance(user_id, owner_balance - win_amount_rounded1)

    successful_members = 0
    telegram_errors = 0
    critical_errors = 0
    error_reasons = []  # Для хранения причин ошибок

    for member_id in member_ids:
        try:
            member_balance = await db.get_user_balance(member_id)
            win_amount_rounded = round(amount_per_member)
            formatted_win_amount = "{:,.0f}".format(win_amount_rounded).replace(',', '.')
            formatted_win_amount1 = "{:,.0f}".format(win_amount_rounded1).replace(',', '.')

            await db.update_user_balance(member_id, member_balance + win_amount_rounded)

            await bot1.send_message(
                member_id,
                f"💰 Ваш клан раздал {formatted_win_amount1} кут. Вы получили <b>{formatted_win_amount}</b> кут.",
                parse_mode=ParseMode.HTML
            )
            successful_members += 1


        except TelegramAPIError as e:

            # Проверка текста ошибки для выявления причины

            if 'chat not found' in str(e).lower():

                reason = "Чат недоступен"

            elif 'cant initiate conversation' in str(e).lower():

                reason = "Бот не может написать в ЛС"

            else:

                reason = f"Неизвестная ошибка: {e}"

            error_reasons.append(f"ID {member_id}: {reason}")

            telegram_errors += 1
        except Exception as e:
            print(f"❌ Критическая ошибка для пользователя {member_id}: {e}")
            critical_errors += 1

    # Формируем сообщение о результате
    formatted_members_count = "{:,.0f}".format(num_members).replace(',', '.')
    formatted_successful_count = "{:,.0f}".format(successful_members).replace(',', '.')

    result_message = (
        f"✅ <b><i>Клановая раздача завершена. С вашего баланса списано {formatted_win_amount1} кут</i></b>\n"
        f"👥 <b><i>Всего участников : {formatted_members_count}</i></b>\n"
        f"🎉 <b><i>Получили кут : {formatted_successful_count}</i></b>\n"
    )

    # Добавляем информацию об ошибках
    if critical_errors > 0:
        result_message += f"⚠️ <b><i>Критические ошибки [обратитесь в поддержку @HelperCute]: {critical_errors}</i></b>\n"
    if telegram_errors > 0:
        result_message += (
            f"📵 <b><i>Ошибки Телеграмма : {telegram_errors}</i></b>\n"
            + "\n".join(error_reasons)  # Добавляем причины ошибок
        )

    await callback_query.message.edit_text(result_message, parse_mode="HTML")
    await callback_query.answer("✅ Клановая раздача завершена.")