from bot.db_create.db import *
from bot.db_create.items_codec import decode_items, encode_items
from aiogram import Bot, Dispatcher, types
from bot.config.config import *
from main import dp
import math
import aiohttp
from googletrans import Translator
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
from main import *
from bot.games.games_item import Slots, Bowling,Dart,FootGame,Basketball
translator = Translator('ru')  # Указываем целевой язык, например, 'ru' для русского




user_message_craftl = {}
pagecraft_cooldowns = {}
slots_cooldowns = {}
bask_cooldowns = {}
bowling_cooldowns = {}
dart_cooldowns = {}
foot_cooldowns = {}

REST = 1.5
def get_crafting_navigation_buttons(page, total_pages):
    buttons = []

    # Предыдущая страница
    if page > 0:
        buttons.append(InlineKeyboardButton("🔙", callback_data=f"craftpage_{page - 1}"))

    # Первая страница
    if page == 0 and total_pages > 1:
        buttons.append(InlineKeyboardButton("🔜🔜", callback_data=f"craftpage_{total_pages - 1}"))

    # Следующая страница
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("🔜", callback_data=f"craftpage_{page + 1}"))

    # Последняя страница
    if page == total_pages - 1 and total_pages > 1:
        buttons.append(InlineKeyboardButton("🔙🔙", callback_data=f"craftpage_0"))

    return buttons

async def generate_crafting_catalog_page(crafts, page, items_per_page):
    start = page * items_per_page
    end = start + items_per_page
    page_crafts = crafts[start:end]

    catalog = ""
    for craft in page_crafts:
        catalog += f"<code>{craft['item1']} + {craft['item2']}</code> = {craft['item']}\n"

    return catalog
async def nout(user_id , message):
    crafts = await db.get_crafts()
    items_per_page = 15
    total_pages = math.ceil(len(crafts) / items_per_page)

    if total_pages == 0:
        total_pages = 1

    page = 0

    catalog = await generate_crafting_catalog_page(crafts , page , items_per_page)
    navigation_buttons = get_crafting_navigation_buttons(page , total_pages)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.inline_keyboard.append(navigation_buttons)  # navigation_buttons - одна строка
    markup.inline_keyboard.append(
        [ InlineKeyboardButton(text="✖️ Закрыть" , callback_data="store_craft_close_message") ])
    craftmessage = await message.reply(f'<b>🧩 Список возможных крафтов</b>\n\n{catalog}' , parse_mode="HTML" ,
        reply_markup=markup)
    user_message_craftl [ user_id ] = craftmessage.message_id


@dp.callback_query(lambda c: c.data and c.data.startswith('craftpage_'))
async def process_pagination(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    current_time = time.time()


    # Получаем время последнего использования функции пользователем
    last_usage_time = pagecraft_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = REST - (current_time - last_usage_time)
        await callback_query.answer(f"⌚️ Пожалуйста, подождите {int(remaining_time)} секунд", show_alert=True)
        return

    # Обновляем время последнего использования
    pagecraft_cooldowns [ user_id ] = current_time

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_craftl or user_message_craftl [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    page = int(callback_query.data.split('_')[1])
    crafts = await db.get_crafts()
    items_per_page = 15
    total_pages = math.ceil(len(crafts) / items_per_page)

    catalog = await generate_crafting_catalog_page(crafts, page, items_per_page)
    navigation_buttons = get_crafting_navigation_buttons(page, total_pages)

    markup = InlineKeyboardMarkup(row_width=2)

    # Добавляем строку с кнопками навигации
    markup.inline_keyboard.append(navigation_buttons)  # navigation_buttons - список кнопок, например: [btn1, btn2]

    # Добавляем строку с кнопкой "Закрыть"
    markup.inline_keyboard.append(
        [ InlineKeyboardButton(text="✖️ Закрыть" , callback_data="store_craft_close_message") ])

    await callback_query.message.edit_text(
        text=f'<b>🧩 Список возможных крафтов</b>\n\n{catalog}',
        parse_mode="HTML",
        reply_markup=markup)


@dp.callback_query(lambda c: c.data == 'store_craft_close_message')
async def close_message(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_message_craftl or user_message_craftl [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return
    await callback_query.answer('Список крафтов удален')
    await callback_query.message.delete()

async def eaglewithdrawal(db, user_id: int, message):
    """
    Увеличивает лимит вывода, отправляет стикер и сообщает новый баланс.
    """
    try:
        uid = int(user_id)
        amount = 100

        # 1) Берём текущий эффективный лимит (withdraw_limits -> fallback users.canwithdrawal)
        try:
            current_limit, current_cooldown = await db.get_user_withdraw_limits(uid)
        except Exception as e:
            print(f"[ITEM][EAGLE][WARN] get_user_withdraw_limits err={e!r}")
            current_limit = await db.get_canwithdrawal(uid)
            current_cooldown = int(
                getattr(db, "WITHDRAW_DEFAULT_COOLDOWN_SEC", WITHDRAW_DEFAULT_COOLDOWN_SEC)
                or WITHDRAW_DEFAULT_COOLDOWN_SEC
            )

        legacy_limit = int(await db.get_canwithdrawal(uid) or 0)
        current_limit = max(int(current_limit or 0), int(legacy_limit or 0))
        current_cooldown = int(current_cooldown or 0)
        new_limit_value = current_limit + amount

        # 2) Обновляем источник истины для лимитов
        await db.upsert_withdraw_limit(
            uid,
            daily_amount_limit=int(new_limit_value),
            cooldown_seconds=int(current_cooldown),
        )

        # 3) Синхронизируем legacy-поле users.canwithdrawal для совместимости
        await db.set_canwithdrawal(uid, int(new_limit_value))

        # 4) Если был кулдаун по daily_limit снимаем его, т.к. лимит повышен предметом
        try:
            if getattr(db, "pool", None):
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        """
                        DELETE FROM withdraw_cooldown
                        WHERE user_id = $1
                          AND until_at > NOW()
                          AND (
                                cause = 'daily_limit'
                                OR cause LIKE 'daily_limit:%'
                              )
                        """,
                        uid,
                    )
        except Exception as e:
            print(f"[ITEM][EAGLE][WARN] cooldown cleanup err={e!r}")

        # 5) Пересчитываем quota window сразу, чтобы UI/проверки увидели новый лимит в этот же момент.
        #    min_withdraw из каталога подарков — чтобы «крошки» < мин. подарка сразу ушли в таймер.
        min_w = 0
        try:
            from bot.design.buttons import get_min_withdraw_amount_from_gifts
            bot_obj = getattr(message, "bot", None)
            if bot_obj is not None:
                min_w = int(await get_min_withdraw_amount_from_gifts(bot_obj) or 0)
        except Exception as e:
            print(f"[ITEM][EAGLE][WARN] min gift price err={e!r}")
        try:
            state = await db.refresh_withdraw_quota_if_needed(
                uid,
                daily_limit=int(new_limit_value),
                cooldown_seconds=int(current_cooldown),
                min_withdraw_amount=int(min_w or 0),
            )
            new_limit = int(state.get("daily_limit") or new_limit_value)
        except Exception as e:
            print(f"[ITEM][EAGLE][WARN] refresh_withdraw_quota_if_needed err={e!r}")
            new_limit = int(new_limit_value)

        # 6) Отправляем стикер
        await message.answer_sticker(
            "CAACAgIAAxkBAsly4mmKhmL5DgNlCiVDEJDCbRLELirxAAI4lAACg2UQSKgOxw5D17OVOgQ"
        )
        bet_amount_win_formated1 = "{:,.0f}".format(amount).replace("," , ".")
        bet_amount_win_formated = "{:,.0f}".format(new_limit).replace("," , ".")
        # 7) Отправляем сообщение
        await message.answer(
            f"<tg-emoji emoji-id='5192951739623447936'>🦅</tg-emoji> <b>Лимит вывода увеличен!</b>\n\n"
            f"<tg-emoji emoji-id='5318892863780579996'>🎩</tg-emoji> <b>Добавлено : {bet_amount_win_formated1}</b>\n"
            f"<tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> <b>Текущий лимит : {bet_amount_win_formated}</b>",
            parse_mode="HTML"
        )

        return True

    except Exception as e:
        print(f"Ошибка в eaglewithdrawal: {e}")
        return False


async def tomato(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return

    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "помидоры" not in plants_info:
            db.plant_tomato(user_id)  # Await the async method
            await message.answer("🍅 Вы посадили помидоры на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете помидоры")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def ogyrchik(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "огурцы" not in plants_info:
            db.plant_plants(user_id)  # Await the async method
            await message.answer("🥒 Вы посадили огурцы на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете огурцы")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def carrot(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "морковь" not in plants_info:
            db.plant_carrot(user_id)  # Await the async method
            await message.answer("🥕 Вы посадили морковь на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете морковь")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def premium3(user_id , message):
    sticker_id = 'CAACAgIAAxkBAYzMmmb6n2PqnL5bfPhaw3fSsXxyvIjLAAK5QAACe_pISTNku6-QgbswNgQ'

    # Отправка стикера
    await message.reply_sticker(sticker_id)

    # Сообщение о получении премиума
    premium_message = ("⭐️ <b>Премиум на 3 месяца почти ваш!</b> 🎉\n"
                       "💌 Напишите <b>@HelperCute</b> и отправьте ему предмет для получения премиума на 3 месяца! \n"
                       "🚀 Укажите, что это для получения премиума. ")

    # Создание инлайн-кнопки для контакта

    button = InlineKeyboardButton(text="Получить премиум" , url="https://t.me/HelperCute")
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])

    # Отправка сообщения с кнопкой
    await message.reply(premium_message , reply_markup=inline_keyboard,parse_mode="HTML")

async def ringtggift(user_id , message):

    # Сообщение о получении премиума
    premium_message = ("⛵️ <b>Подарок почти ваш!</b> \n"
                       "🥂 Напишите <b>@HelperCute</b> и отправьте ему подарок [предмет] \n"
                       "🔥 Укажите, что это для получения подарка. ")

    # Создание инлайн-кнопки для контакта

    button = InlineKeyboardButton(text="Написать админу" , url="https://t.me/HelperCute")
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])

    # Отправка сообщения с кнопкой
    await message.reply(premium_message , reply_markup=inline_keyboard,parse_mode="HTML")

async def premium6(user_id , message):
    sticker_id = 'CAACAgIAAxkBAZbPTGcUMFS8J7XRuiSauJZBC20vmyncAAL9WQACnnShSGv45qgjHI7-NgQ'

    # Отправка стикера
    await message.reply_sticker(sticker_id)

    # Сообщение о получении премиума
    premium_message = ("🌟 <b>Премиум на 6 месяцов почти ваш!</b> 🎉\n"
                       "💌 Напишите <b>@HelperCute</b> и отправьте ему предмет для получения премиума на 6 месяцев! \n"
                       "🚀 Укажите, что это для получения премиума. ")

    # Создание инлайн-кнопки для контакта


    button = InlineKeyboardButton(text="Получить премиум" , url="https://t.me/HelperCute")
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])

    # Отправка сообщения с кнопкой
    await message.reply(premium_message , reply_markup=inline_keyboard,parse_mode="HTML")

async def potato(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "картофель" not in plants_info:
            db.plant_potato(user_id)  # Await the async method
            await message.answer("🥔 Вы посадили картофель на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете картофель")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def cabbage(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "капуста" not in plants_info:
            db.plant_cabbage(user_id)  # Await the async method
            await message.answer("🥬 Вы посадили капусту на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете капусту")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def greenapple(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "яблоко" not in plants_info:
            db.plant_apple(user_id)  # Await the async method
            await message.answer("🍏 Вы посадили яблоню на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете яблока")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def melon(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Handle the case where get_info might be None
    if get_info is None:
        filtered_info = [ ]
    else:
        # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
        filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]

    print('вот этот пиздец :' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return

    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "арбуз" not in plants_info:
            db.plant_melon(user_id)  # Await the async method
            await message.answer("🍉 Вы посадили арбуз на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете арбуз")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def banana(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "бананы" not in plants_info:
            db.plant_banana(user_id)  # Await the async method
            await message.answer("🍌 Вы посадили бананы на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете бананы")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def berry(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "клубника" not in plants_info:
            db.plant_berry(user_id)  # Await the async method
            await message.answer("🍓 Вы посадили клубнику на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете клубнику")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def corn(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "кукуруза" not in plants_info:
            db.plant_corn(user_id)  # Await the async method
            await message.answer("🌽 Вы посадили кукурузу на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете кукурузу")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def marix(db , user_id , message):
    get_info = db.get_plants_info(user_id)
    available_plants = db.get_available_plants(user_id)

    # Убираем None и пустые строки из get_info, но учитываем пустые строки с символами
    filtered_info = [ item for item in get_info if item is not None and (item.strip() != '' or len(item) > 0) ]
    print('вот этот пиздец : ' , filtered_info , available_plants)

    # Проверка на количество предметов
    if len(filtered_info) >= available_plants:
        await message.answer("⚠️ Недостаточно мест для выращивания")
        return
    if available_plants > 0:
        plants_info = db.get_plants_info(user_id)
        if plants_info is None or "марихуана" not in plants_info:
            db.plant_marix(user_id)  # Await the async method
            await message.answer("🌿 Вы посадили марихуану на свой огород")
        else:
            await message.answer("⚠️ Вы уже выращиваете марихуану")
    else:
        await message.answer("⚠️ Недостаточно мест для выращивания")


async def case5000_15000(db, user_id, message):
    # Проверка наличия ключа и кейса в инвентаре пользователя
    user_data = await db.fetch_all("SELECT items, balance FROM users WHERE user_id=$1", (user_id,))
    if not user_data:
        await message.reply("<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>", parse_mode="HTML")
        return

    row = user_data[0]
    user_inventory = decode_items(row["items"])
    print(f"Инвентарь пользователя: {user_inventory}")

    key_name = "Ключ"
    case_name = "Маленький кейс"

    if user_inventory.get(case_name, 0) > 0:
        if user_inventory.get(key_name, 0) > 0:
            # Генерируем случайное число от 1 до 125
            amount = random.randint(1, 50)

            # Обновляем баланс пользователя
            current_balance = row["balance"]
            new_balance = current_balance + amount
            await db.update_user_balance(user_id, new_balance)
            await db.cutehistory_plus(
                user_id , amount , "открытие маленького кейса")

            win_amount_formatted = "{:,.0f}".format(amount).replace(",", ".")

            button = InlineKeyboardButton(text=" " , callback_data="9close_bonus", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
            await message.answer(text='✨')
            await message.reply(
                f"📦 <b>Вы открыли маленький кейс с {win_amount_formatted} кут</b>",
                parse_mode="HTML"
            )

            # Удаляем 1 шт ключа и кейса из инвентаря пользователя после успешного открытия кейса
            user_inventory[key_name] -= 1
            if user_inventory[key_name] == 0:
                del user_inventory[key_name]

            user_inventory[case_name] -= 1
            if user_inventory[case_name] == 0:
                del user_inventory[case_name]

            updated_inventory = encode_items(user_inventory)
            await db.fetch_all("UPDATE users SET items=$1 WHERE user_id=$2", (updated_inventory, user_id))
        else:
            # Если у пользователя нет ключа, отправляем сообщение об ошибке
            await message.reply(
                "✖️ <b>У вас нет ключа для открытия кейса.</b>", parse_mode="HTML"
            )
    else:
        # Если у пользователя нет кейса, отправляем сообщение об ошибке
        await message.reply(
            "✖️ <b>У вас нет маленького кейса для открытия.</b>", parse_mode="HTML"
        )


async def case20000_40000(db, user_id, message):
    # Проверка наличия данных пользователя
    user_data = await db.fetch_all("SELECT items, balance FROM users WHERE user_id=$1", (user_id,))
    if not user_data:
        await message.reply("<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>", parse_mode="HTML")
        return

    row = user_data[0]
    user_inventory = decode_items(row["items"])
    print(f"Инвентарь пользователя: {user_inventory}")

    key_name = "Ключ"
    case_name = "Средний кейс"

    if user_inventory.get(case_name, 0) > 0:
        if user_inventory.get(key_name, 0) > 0:
            # Генерируем случайное число от 70 до 160
            amount = random.randint(30, 70)

            # Обновляем баланс пользователя
            current_balance = row["balance"]
            new_balance = current_balance + amount
            await db.update_user_balance(user_id, new_balance)
            await db.cutehistory_plus(
                user_id , amount , "открытие среднего кейса")

            win_amount_formatted = "{:,.0f}".format(amount).replace(",", ".")
            await message.answer(text='⚡️')
            await message.reply(
                f"🎒 <b>Вы открыли средний кейс с {win_amount_formatted} кут</b>",
                parse_mode="HTML"
            )

            # Удаляем 1 шт ключа и кейса из инвентаря пользователя после успешного открытия кейса
            user_inventory[key_name] -= 1
            if user_inventory[key_name] == 0:
                del user_inventory[key_name]

            user_inventory[case_name] -= 1
            if user_inventory[case_name] == 0:
                del user_inventory[case_name]

            updated_inventory = encode_items(user_inventory)
            await db.fetch_all("UPDATE users SET items=$1 WHERE user_id=$2", (updated_inventory, user_id))
        else:
            # Если у пользователя нет ключа, отправляем сообщение об ошибке
            await message.reply(
                "✖️ <b>У вас нет ключа для открытия кейса.</b>", parse_mode="HTML"
            )
    else:
        # Если у пользователя нет кейса, отправляем сообщение об ошибке
        await message.reply(
            "✖️ <b>У вас нет среднего кейса для открытия.</b>", parse_mode="HTML"
        )


async def case50000_100000(db, user_id, message):
    # Проверка наличия данных пользователя
    user_data = await db.fetch_all("SELECT items, balance FROM users WHERE user_id=$1", (user_id,))
    if not user_data:
        await message.reply("<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>", parse_mode="HTML")
        return

    row = user_data[0]
    user_inventory = decode_items(row["items"])
    print(f"Инвентарь пользователя: {user_inventory}")

    key_name = "Ключ"
    case_name = "Большой кейс"

    if user_inventory.get(case_name, 0) > 0:
        if user_inventory.get(key_name, 0) > 0:
            # Генерируем случайное число от 80 до 220
            amount = random.randint(50, 170)

            # Обновляем баланс пользователя
            current_balance = row["balance"]
            new_balance = current_balance + amount
            await db.update_user_balance(user_id, new_balance)
            await db.cutehistory_plus(
                user_id , amount , "открытие большого кейса")

            win_amount_formatted = "{:,.0f}".format(amount).replace(",", ".")
            await message.answer(text='🧳')
            await message.reply(
                f"🧳 <b>Вы открыли большой кейс с {win_amount_formatted} кут</b>",
                parse_mode="HTML"
            )

            # Удаляем 1 шт ключа и кейса из инвентаря пользователя после успешного открытия кейса
            user_inventory[key_name] -= 1
            if user_inventory[key_name] == 0:
                del user_inventory[key_name]

            user_inventory[case_name] -= 1
            if user_inventory[case_name] == 0:
                del user_inventory[case_name]

            updated_inventory = encode_items(user_inventory)
            await db.fetch_all("UPDATE users SET items=$1 WHERE user_id=$2", (updated_inventory, user_id))
        else:
            # Если у пользователя нет ключа, отправляем сообщение об ошибке
            await message.reply(
                "✖️ <b>У вас нет ключа для открытия кейса.</b>", parse_mode="HTML"
            )
    else:
        # Если у пользователя нет кейса, отправляем сообщение об ошибке
        await message.reply(
            "✖️ <b>У вас нет большого кейса для открытия.</b>", parse_mode="HTML"
        )
async def meh_vor(self , user_id , message):
    target_id = self.get_random_user_id()

    if user_id == target_id:
        await message.reply("✖️ Вы не можете ограбить самого себя.")
        return

    result = await self.grab(message , user_id , target_id)
    if result:
        await message.reply(result , parse_mode="HTML")


async def Ephorin(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 10)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            # Отправляем сообщение о получении кутенина
            await message.reply(f"🍬 Вы использовали Эйфорин получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:1" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Psilophor(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 20)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            # Отправляем сообщение о получении кутенина
            await message.reply(f"🍄 Вы использовали Псилофлор получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:3" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Virtodin(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 30)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            # Отправляем сообщение о получении кутенина
            await message.reply(f"💉 Вы использовали Виртодин получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:4" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Ectazon(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 45)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            # Отправляем сообщение о получении кутенина
            await message.reply(f"🧬 Вы использовали Экстазон получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:5" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Mentalidin(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 60)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            await message.answer(text='💊')
            await message.reply(f"💊 Вы использовали Менталидин получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:6" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Mistinglin(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 75)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            await message.answer(text='🔮')
            await message.reply(f"🔮 Вы использовали Мистинглин получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:7" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def Cristalin(self , user_id , message):
    try:
        # Обновляем баланс кутенина
        amount = random.randint(1 , 100)
        new_cutenin = await db.update_cutenin_balance(user_id , amount)  # Увеличиваем на 1, как указано в функции
        if new_cutenin is not None:
            await message.answer(text='💎')
            await message.reply(f"💎 Вы использовали Кристалин получив {amount} кутенина")
            return new_cutenin

    except Exception as e:
        # В случае ошибки в базе данных или другой ошибки обработаем её здесь
        print("Error:8" , e)
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return None


async def BonusPlus(self , user_id , message):
    # Проверяем текущее значение столбца use1 для данного user_id

    bonus_amount = random.randint(10 , 50)
    balance = await db.get_user_balance(user_id)
    win = balance + bonus_amount
    await db.update_user_balance(user_id , win)
    win_amount_formatted = "{:,.0f}".format(bonus_amount).replace("," , ".")
    await message.reply(
        f"🎁 Вы использовали бонус получив <b>{win_amount_formatted}</b> ктк" , parse_mode="HTML")


async def country1(user_id , message , country_emoji):
    # Определяем название страны по эмодзи
    country = country_dict.get(country_emoji , "Неизвестная страна")

    if not country_emoji:
        raise ValueError("Не найдено эмодзи флага")

    # Проверяем, есть ли у пользователя уже установленный флаг
    current_flag = await db.get_user_flag(user_id)

    if current_flag:
        # Находим название текущего флага через эмодзи
        flag_name = await db.get_item_name_by_emoji(current_flag)

        if flag_name:
            # Если пользователь пытается установить тот же флаг, отправляем ошибку
            if current_flag == country_emoji:
                await message.reply(
                    f"❕ У вас уже установлен флаг <code>{country_emoji}</code> <b>{country}</b>." , parse_mode="HTML")
                await db.set_items(user_id , flag_name , 1)
                return  # Прерываем выполнение функции

            # Возвращаем текущий флаг обратно в инвентарь
            await db.set_items(user_id , flag_name , 1)
        else:
            print("Произошла ошибка: не удалось найти название флага.")

    # Если флага нет, обновляем страну пользователя
    await db.update_user_country(user_id , country_emoji)
    await message.reply(
        f'<code>{country_emoji}</code> Вы повесили <b>{country}</b> в своем профиле' , parse_mode="HTML")






async def tuchka(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4ejGaaYyCkAmXme2NP7qPcEe-5vJ_WAAJvVAACptrZSKEeXNXm0i3jNQQ'
    await message.reply_sticker(sticker_id)

async def Cute(user_id, message):
    # Test with a known valid sticker ID
    sticker_id = 'CAACAgIAAxkBAW4hTmaabvicSE67HjQsmazBnorLDY3iAAIkUgACb6bQSAlqcGMXrGHWNQQ'

    sent_sticker = await message.reply_sticker(sticker_id)

    # Отправка ответа на стикер с текстом
    await bot1.send_message(
        chat_id=message.chat.id , text="🎩 Фигурка 'Cute'" , reply_to_message_id=sent_sticker.message_id)

async def moxito(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4pLmaajOq5EYcha-8S121WhjB1SEXmAAI9UQACbT7ZSCQtSSdAV99PNQQ'
    await message.reply_sticker(sticker_id)

async def cola(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4pRmaajTskY5WkGddJbSfsp0mW76JAAAKTUQAC-RvYSLQVtRaNhjexNQQ'
    await message.reply_sticker(sticker_id)

async def wine(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4qw2aajqRNAs1ALZFPIZbHRlBEzbyWAAL3UgACLH7YSPUqpsIHb5h0NQQ'
    await message.reply_sticker(sticker_id)

async def con(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4rVGaaj81Cxqoby2jhrcM90WdgF8sJAAJmUgACsvnQSLd4B8Gm90TbNQQ'
    await message.reply_sticker(sticker_id)

async def sham(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4ru2aakKGzZh-1pD4SXUY5CtVXRPzWAAIfXwACoOHZSJZQz5PRQCCNNQQ'
    await message.reply_sticker(sticker_id)

async def beer(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW4sZGaakVm-aD0Fw7QQYx8ec46EOZpnAAImVwACYuTQSAYQdEq3OaKDNQQ'
    sticker_id2 = 'CAACAgIAAxkBAW4sZmaakVrfrdtFy1noUgL2di9_SY0eAAI0WwACybzZSJH31-gzILraNQQ'
    await message.reply_sticker(sticker_id)
    await message.reply_sticker(sticker_id2)




async def sigareta(user_id, message):
    """
    Использование сигареты: +5% к бонусу крафта (не более 100),
    удаляет одну сигарету из инвентаря.
    """
    # Получаем инвентарь пользователя
    user_data = await db.get_user_data_craft(user_id)
    if not user_data:
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Пользователь не найден.</b>", parse_mode="HTML")
        return
    _, _, user_items_json = user_data


    try:
        inventory = decode_items(user_items_json)
        if not isinstance(inventory, dict):
            raise ValueError("Инвентарь не словарь")


        current_bonus = await db.get_user_craftprox(user_id)
        new_bonus = current_bonus + 100
        if new_bonus > 100:
            await message.reply(
                f"<tg-emoji emoji-id='5213181173026533794'>⚠️</tg-emoji> <b>Ваш бонус уже {current_bonus}% и не может превысить 100%.</b>\n"
                f"Сначала используйте его в крафте, потом покурите ещё раз",
                parse_mode="HTML"
            )
            return

        await db.set_user_craftprox(user_id, new_bonus)

        # Отправляем стикер
        sticker_id = 'CAACAgIAAxkBAytLLmodAnRSdBaw8OV6fxsyYn5_hRxeAAL5FQACeF7hS13K5y35r2HVOwQ'
        await message.reply_sticker(sticker_id)

        await message.reply(
            f"<tg-emoji emoji-id='6017083782505437474'>🚬</tg-emoji> <b>Вы покурили - шансы на удачный крафт увеличены!</b>\n\n"
            f"{current_bonus}% → {new_bonus}%\n\n"
            f"<tg-emoji emoji-id='6032644646587338669'>🎁</tg-emoji> <b><i>Бонус сгорит после следующего крафта (неважно, успешного или провального).</i></b>" , parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка в sigareta: {e}")
        await message.reply("<b>Попробуйте позже.</b>", parse_mode="HTML")

async def b2eer(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5ihWablc0gLBZv67FV7V1HAhe3jOIQAAK2VAACIpPhSIyxZEe_q-0UNQQ'
    await message.reply_sticker(sticker_id)

async def kon(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5kgGabmzXOI7Y8kgawKhv-VZtlkPBbAAJITwACyQ_YSBZihWwmHGbVNQQ'
    await message.reply_sticker(sticker_id)

async def palochka(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5kpGabm4yYIV2tSLImdw8wOrNZ0w44AALYVgACZBvhSKgkvCaSYJU_NQQ'
    await message.reply_sticker(sticker_id)


async def edino(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5k1Gabm_e77Xh2sUlN0Vf-maHWIvHFAAI8UQAC1cDhSJJ1Oda4Dq-fNQQ'
    await message.reply_sticker(sticker_id)

async def dog(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5leWabnq0gDKLC8yOMVsDZo3qTXLtRAAIwTAAC3IzgSBYgQm3OH01PNQQ'
    await message.reply_sticker(sticker_id)

async def cat(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5l4WaboDjU5PLDpH1HxbamEnjLBp83AAJBUAACswTZSIogY4WYjNCYNQQ'
    await message.reply_sticker(sticker_id)


async def mich(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5mDWaboQcy7azjDUAL9FOJ3PNelFctAAK4TAACMx3hSFxQbSzQ_VGQNQQ'
    await message.reply_sticker(sticker_id)

async def hamster(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5mQmabodLgQzBtn4VTbnXW33B47kmdAAL5SQAChXHgSCx2PI8maNPSNQQ'
    await message.reply_sticker(sticker_id)

async def rabi(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5mfGabopcV8N5DXyKjBdpdtMWESfogAAL7TAACfrXZSO414ItYrAa_NQQ'
    await message.reply_sticker(sticker_id)

async def lis(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5mlmabowUQd0fAMFkJHI-x10xaAvxCAAJPUwAC7LvhSAn_pSoOyQYdNQQ'
    await message.reply_sticker(sticker_id)

async def ber(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5m1Wabo5W4UtC6_PiCS5LamT_FSl1cAALeTQACgHvgSHXschMtARtoNQQ'
    await message.reply_sticker(sticker_id)

async def whiteber(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5nIWabpHYBKVcnSOpqdUDfmA5sfjkSAAK7UgACPgnZSCP0bOEldyJPNQQ'
    await message.reply_sticker(sticker_id)

async def koala(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5nTmabpRwBoXmTrT9V8KYVmHipg63CAAJ8VgAC_e3hSMVBzgaDKG7NNQQ'
    await message.reply_sticker(sticker_id)

async def tiger(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5nYGabpY1BG2jDBe9GvzbX6DBI3NzRAAIDTAACOcngSHV5kncCd-cPNQQ'
    await message.reply_sticker(sticker_id)

async def lion(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5nd2abpe47YR_c1opbVry42g3jn96NAAKHVwACZg3ZSLfEU7PSkEMDNQQ'
    await message.reply_sticker(sticker_id)

async def pig(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5oK2abp68lP9b_kpBUe6kieu9MJTK1AAIrTAACikTYSB0XQjepbi1SNQQ'
    await message.reply_sticker(sticker_id)

async def kvaa(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5o7GabqrWmNYoEMdglCsG9tYwcsiPPAAI_UgACFkfZSIdNYuzCBFHMNQQ'
    await message.reply_sticker(sticker_id)

async def monkey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5pI2abq3IJS1nuVcSWLQwPhYzmWj3BAAI3UAACBbTYSBusfE_NxU-1NQQ'
    await message.reply_sticker(sticker_id)

async def closemonkey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5pR2abrBCL7UoePXZwTaqtv3sqa5MHAAJrTQACsGLYSFpv4oxBnypENQQ'
    await message.reply_sticker(sticker_id)

async def openmonkey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5pYmabrHIERl0tN4RlYVqvO-Kztb9EAAIIVAAC4jPYSPV2IZBDlEnHNQQ'
    await message.reply_sticker(sticker_id)

async def qwemonkey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5pfGabrNiEFv8Nb53Wbybms71pGHtmAAKnRQAC-svgSJTKcjNraZ41NQQQ'
    await message.reply_sticker(sticker_id)

async def osmonkey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5pz2abreoyzvsEOouLOE5kqIOJMPhSAALHUgAC7KvhSPAZ0COx2PL3NQQ'
    await message.reply_sticker(sticker_id)

async def pin(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5qLWabrw9fI6_7NKqSjeHFB5G0jqCWAAIeVAAC2BnhSOs0oLCEZyY3NQQ'
    await message.reply_sticker(sticker_id)

async def bird(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5qUWabr3i_OlkwqS4hFHrpkavq2O7QAALKUwACZnfhSBdi0JmOt6gINQQ'
    await message.reply_sticker(sticker_id)

async def chip(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5qj2absGo-zwPB9vsPbcSj7bV26E8lAAJpUAACvlzhSD-I4ZDaj5oFNQQ'
    await message.reply_sticker(sticker_id)

async def iachip(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5qvGabsPjmgtEAASFEeR1YOBXfCe6bOwAC0E0AAqsd2Uhn7c1y8gMxdDUE'
    await message.reply_sticker(sticker_id)

async def yqqwchip(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5q02absWD3u72FacmVp0N5N7JGDD6oAAKGTAACj4_hSKDqMAABNUnVAAE1BA'
    await message.reply_sticker(sticker_id)

async def goose(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5rAAFmm7InnE9-iztkt3I8coKi4VRKBAACR1kAAo894EjPJL2XzfXC-DUE'
    await message.reply_sticker(sticker_id)

async def voron(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5rQWabs0TmJwAB2bON9ZJyjEJry193SAAC1k8AAvNS4Ug5Td7hfoD1ozUE'
    await message.reply_sticker(sticker_id)

async def frymo(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5rXmabs7fISYGav5SYF1W3tYfMSoBFAAI_UQACfA3YSNf0N58htzfNNQQ'
    await message.reply_sticker(sticker_id)

async def bzasddf(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5r9mabtSoym2lFGbE6hfPkrvxcnrjpAAK7TAACrpvYSAIO1PsAAWeZpTUE'
    await message.reply_sticker(sticker_id)

async def sdfkow(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5sKWabtdcFEZ4eGNFPNUcChWKzoMBLAAKaUQACpiHgSCB_0Q2VrPEpNQQ'
    await message.reply_sticker(sticker_id)

async def butterfly(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5sYGabtpM3vrR4O9mquNRCuoR6AyUQAALXUQACg-XgSOy0NpbMOQr9NQQ'
    await message.reply_sticker(sticker_id)

async def ulitka(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5shmabtwTImlFGFj-ve6mHvTgXva3tAAJFTgACQsbgSOt_v3dzJ3pGNQQ'
    await message.reply_sticker(sticker_id)

async def korovka(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5stGabt3qROmNtZ65Oclpd0OEsoKChAAKaUAAC3rLYSErlens1v5kNNQQ'
    await message.reply_sticker(sticker_id)

async def muravey(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5s5Wabt_H8VsYF9CSJJBwrY58mX5h6AAISSgACGAvhSDNRilRm-8SFNQQ'
    await message.reply_sticker(sticker_id)

async def juk(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5tH2abuIXwvR4xQx7umsVkccfsjqd3AAJiRgACJlTgSCKX3r54INL7NQQ'
    await message.reply_sticker(sticker_id)

async def tarakan(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5tO2abuOqyU1kIQlSk8H-HvZ-EPjefAAK7VgAC9ZnhSLGEr9b4MClqNQQ'
    await message.reply_sticker(sticker_id)

async def komar(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5tT2abuUlmDEnDE_dBVtAZGcSgqkQRAAIEUQACxirYSOjnJz336x_TNQQ'
    await message.reply_sticker(sticker_id)

async def nechik(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5tZ2abuckxvp0DX9GNbFyLqxHdj93DAAIVVQACR6LgSEJ3W_vLLl3YNQQ'
    await message.reply_sticker(sticker_id)

async def spider(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5tf2abume-K7dvamfNlKOIe-yNZs5XAAIGTwACaX_ZSPc9jz8P74K9NQQ'
    await message.reply_sticker(sticker_id)

async def turtle(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5t0mabu2-wft_53oxlXlmiP9bvkTviAAL0TgACiULgSLpoj6LbvdtmNQQ'
    await message.reply_sticker(sticker_id)

async def snake(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5uOWabvLZZj59e5JnBu99-8qL3d4o8AAKrUwAC9U7gSDy1PBO4EjauNQQ'
    await message.reply_sticker(sticker_id)

async def dragon(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5udGabvU66pCVAScDcD1v7uHdbTE-JAALFUAACSKjgSDTbCcxsf3SANQQ'
    await message.reply_sticker(sticker_id)

async def bluedragon(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5up2abvextPaShQySeFlcD4FtJ6F1tAAJLUAACDWPgSChcyeMrhb34NQQ'
    await message.reply_sticker(sticker_id)

async def osminog(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5uymabvmJPcQSnMNTmo0H0Qdjlpnj8AAIiVQACbkXgSNKph8qzGo2ENQQ'
    await message.reply_sticker(sticker_id)

async def kalmar(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5vGWabv065tHZtvkyxJm0nilNwqwuaAAItUgAChSXhSNOS7K1HlUmvNQQ'
    await message.reply_sticker(sticker_id)

async def revetka(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5vQmabv-ah8qNqNTAU2iTcuc5YUrKqAAKrUgACyW7hSBxMoDyhzllRNQQ'
    await message.reply_sticker(sticker_id)

async def omar(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5vYGabwF811GHJlMgH6FjmFPVSf4c9AALqVwACDvzhSP72lndWb3Z_NQQ'
    await message.reply_sticker(sticker_id)

async def crab(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5vi2abwN3k4xVhCHZ6DK9xnPn_0tvEAANRAAL7VOBIfc8cD0Hs6tw1BA'
    await message.reply_sticker(sticker_id)

async def fish(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5vs2abwZQ4A8RLP0lMfsC80u15qTJpAAJrSgAC2v_gSEW59MFVs9leNQQ'
    await message.reply_sticker(sticker_id)

async def luefish(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5v1GabwfkD-VZePo2FY3-0kw3tGZRcAAKqTwACU47gSM4C1U7AR5T6NQQ'
    await message.reply_sticker(sticker_id)

async def itkit(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5wFWabws5BXTcb9eGUi5k8PUsi15KQAALRXAACEfPhSN0CTyKZSNULNQQ'
    await message.reply_sticker(sticker_id)

async def tulen(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5whWabw4sLFnkXHBuV9DyS9jTIUZPAAAKUUgACQo_ZSKHxsRDvxRp3NQQ'
    await message.reply_sticker(sticker_id)

async def niger(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5wuWabxKRTYZA2Rgf5QeiptOQcRGaTAALBTwAC1UrgSB3i9QuzUQbbNQQ'
    await message.reply_sticker(sticker_id)

async def opard(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5w4GabxQd4gIMtNM-2ae4wXcW_W_zkAALlVwACInnYSKo0ql5BD1bFNQQ'
    await message.reply_sticker(sticker_id)

async def xebra(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5w9GabxXEWVxZv_9rlRbp-2laqoUZtAALuUwAC91TgSKVFwdoNt9gNNQQ'
    await message.reply_sticker(sticker_id)

async def gorila(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5xLWabxnG0OPGvQM4jJwZKlBQsLkyDAALSUAAClrnhSFx8kNXdeANQNQQ'
    await message.reply_sticker(sticker_id)

async def raf(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5xi2abyThvb6RIfRVvC9juVsULNZh5AAJCTgAC7xzZSH9pHlGXKHFoNQQ'
    await message.reply_sticker(sticker_id)

async def ceng(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5xnWabyZgQMM_D91u-cwU0l8xt6is6AALWRwACuDzhSAfR7Xgq1cWHNQQ'
    await message.reply_sticker(sticker_id)

async def buvol(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5xrmabyf65f_Kmk40veCxNMF_hf8pCAAKSTwAC6eXhSCdz-C3rfZzANQQ'
    await message.reply_sticker(sticker_id)

async def ox(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5yAWabyx7QWJym3D3mHWXIxGrPc2UqAALcUAACr8LhSJPS9uUKEM6YNQQ'
    await message.reply_sticker(sticker_id)

async def myyyy(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5yY2abzdMwGD4PSHQWC1Muwks9y4UUAAJSTAAC5oHhSB7FCb3NMVGHNQQ'
    await message.reply_sticker(sticker_id)

async def big(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5yimabzxWcMrcLwqEED2T6Dsn9hkO_AAK5VgAC9rvgSNnZ-h5FTuJ3NQQ'
    await message.reply_sticker(sticker_id)

async def ovsa(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW5yxWabz4cg3x2ntEK4IZAI_JT0v-3nAAJATwACVp3YSBe8injNeUr5NQQ'
    await message.reply_sticker(sticker_id)

async def gator(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAW58QGab_ucPjrji9yrrziQ6un7ixzG9AAL5VAACNjjhSEMwBGA76cUyNQQ'
    await message.reply_sticker(sticker_id)

async def key(user_id , message):
    # Отправляем стикер
    await message.reply('🔑 Ключ можно использовать только для открытия кейсов')

async def taxi(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAXAUL2aiEWmmdDWbPLoekhmHfyqcgRMKAAKkVQAC6cUQSYZ_n3xIo0F_NQQ'
    await message.reply_sticker(sticker_id)

async def police(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAXAVmWaiE7GxHuQXDqsK5e7LrOsPG9fsAAKOTgACTgwRSVNI-6aDMuXZNQQ'
    await message.reply_sticker(sticker_id)


async def chat5(user_id , message):
    # Отправляем стикер
    sticker_id = 'CAACAgIAAxkBAXNPlmauIbGtRAzHq20uaMtVXUWBREn4AALFTAAC8GpwSXkNooIKUFoyNQQ'
    await message.reply_sticker(sticker_id)


async def get_motivation_quote():
    url = 'https://api.quotable.io/random?tags=inspirational'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                quote = data['content']
                return quote
            else:
                return 'Не удалось получить мотивационную цитату.'

async def translate_text(text, dest_language='ru'):
    translation = translator.translate(text, dest=dest_language)
    return translation.text

async def motivation(user_id, message):
    quote = await get_motivation_quote()
    translated_quote = await translate_text(quote)
    full_message = f'<b>{translated_quote}</b>'
    await message.reply(full_message, parse_mode=ParseMode.HTML)

async def skidka(user_id, message):
    sticker_id = 'CAACAgIAAxkBAXsLymbLSEqze38y8uBkszv71AUywY_7AAIfUAACW6HwSJ81ejhD44RENQQ'
    await message.reply_sticker(sticker_id)
    await message.reply('🎟 Купон на скидку можно использовать при покупке предметов в магазине')

async def buket(user_id, message):
    sticker_id = 'CAACAgIAAxkBAXtRkGbMWz0iwdk-22xy6dZmxuOsDowNAAJ6TgACRLZgSqi7mQbJrO-ZNQQ'
    await message.reply_sticker(sticker_id)

async def svidobrake(user_id, message):
    sticker_id = 'CAACAgIAAxkBAXtUqGbMYjjcqyxkcRuZi7W539MaLr3vAAJfVQACI0FoSoPJdJ_mRcLMNQQ'
    await message.reply_sticker(sticker_id)






async def slots(user_id , message):
    bet = await db.get_price_by_emoji('🎰')
    balance = await db.get_user_balance(user_id)

    current_time = time.time()
    REST = 3

    # Получаем время последнего использования функции пользователем
    last_usage_time = slots_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = int(REST - (current_time - last_usage_time))
        await message.reply(f"⌚️ <b>Пожалуйста, подождите <i>{remaining_time}</i> секунд</b>",parse_mode="HTML")
        return

    # Обновляем время последнего использования
    slots_cooldowns [ user_id ] = current_time



    slot_game = Slots(bet , user_id , balance , bot1 , dp , message)
    win_amount = await slot_game.main()  # Получаем сумму выигрыша

    if win_amount > 0:
        win_amount_commission = round(win_amount)
        await db.update_user_balance(user_id, balance + win_amount_commission)
        await db.cutehistory_plus(
            user_id , win_amount_commission , "предмет слоты")
        await db.set_items(user_id , "Геймпад" , 1)
        print(f"Пользователь {user_id} выиграл {win_amount}. Баланс обновлён.")



async def bowling(user_id, message):
    bet = await db.get_price_by_emoji('🎳')
    balance = await db.get_user_balance(user_id)  # Получение текущего баланса

    current_time = time.time()
    REST = 3

    # Получаем время последнего использования функции пользователем
    last_usage_time = bowling_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = int(REST - (current_time - last_usage_time))
        await message.reply(
            f"⌚️ <b>Пожалуйста, подождите <i>{remaining_time}</i> секунд</b>" , parse_mode="HTML")
        return

    # Обновляем время последнего использования
    bowling_cooldowns [ user_id ] = current_time

    # Инициализируем и запускаем игру в боулинг
    bowling_game = Bowling(bet, user_id, balance, bot1, dp, message)
    win_amount_commission = await bowling_game.main()  # Получаем сумму выигрыша

    if win_amount_commission > 0:
        new_balance = balance + win_amount_commission  # Обновляем баланс с выигрышем
        await db.update_user_balance(user_id, new_balance)  # Запись в БД
        await db.cutehistory_plus(
            user_id , win_amount_commission , "предмет боулинг")
        await db.set_items(user_id , "Геймпад" , 1)
        print(f"Пользователь {user_id} выиграл {win_amount_commission}. Баланс обновлён.")


async def dart(user_id, message):
    bet = await db.get_price_by_emoji('🎯')
    balance = await db.get_user_balance(user_id)  # Get current balance

    current_time = time.time()
    REST = 3

    # Получаем время последнего использования функции пользователем
    last_usage_time = dart_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = int(REST - (current_time - last_usage_time))
        await message.reply(
            f"⌚️ <b>Пожалуйста, подождите <i>{remaining_time}</i> секунд</b>" , parse_mode="HTML")
        return

    # Обновляем время последнего использования
    dart_cooldowns [ user_id ] = current_time

    # Initialize and start the Dart game
    dart_game = Dart(bet, user_id, balance, bot1, dp, message)
    win_amount_commission = await dart_game.main()  # Get win amount

    if win_amount_commission > 0:
        new_balance = balance + win_amount_commission  # Update balance with win
        await db.update_user_balance(user_id, new_balance)  # Update in the database
        await db.cutehistory_plus(
            user_id , win_amount_commission , "предмет дартс")
        await db.set_items(user_id , "Геймпад" , 1)
        print(f"Пользователь {user_id} выиграл {win_amount_commission}. Баланс обновлён.")



async def foot(user_id, message):
    bet = await db.get_price_by_emoji('⚽️')
    balance = await db.get_user_balance(user_id)  # Get current balance

    current_time = time.time()
    REST = 3

    # Получаем время последнего использования функции пользователем
    last_usage_time = foot_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = int(REST - (current_time - last_usage_time))
        await message.reply(
            f"⌚️ <b>Пожалуйста, подождите <i>{remaining_time}</i> секунд</b>" , parse_mode="HTML")
        return

    # Обновляем время последнего использования
    foot_cooldowns [ user_id ] = current_time

    # Initialize and start the FootGame
    foot_game = FootGame(bet, user_id, balance, bot1, dp, message)
    win_amount_commission = await foot_game.main()  # Get win amount

    # Check if win_amount_commission is None or 0
    if win_amount_commission is None:
        print(f"Ошибка: выигрыш не определен для пользователя {user_id}.")
        return

    if win_amount_commission > 0:
        new_balance = balance + win_amount_commission  # Update balance with win
        await db.update_user_balance(user_id, new_balance)  # Update in the database
        await db.cutehistory_plus(
            user_id , win_amount_commission , "предмет футбол")
        await db.set_items(user_id , "Геймпад" , 1)
        print(f"Пользователь {user_id} выиграл {win_amount_commission}. Баланс обновлён.")



async def bask(user_id, message):
    bet = await db.get_price_by_emoji('🏀')
    balance = await db.get_user_balance(user_id)  # Get current balance

    current_time = time.time()
    REST = 3

    # Получаем время последнего использования функции пользователем
    last_usage_time = bask_cooldowns.get(user_id , 0)

    # Проверяем, прошёл ли период отдыха
    if current_time - last_usage_time < REST:
        remaining_time = int(REST - (current_time - last_usage_time))
        await message.reply(
            f"⌚️ <b>Пожалуйста, подождите <i>{remaining_time}</i> секунд</b>" , parse_mode="HTML")
        return

    # Обновляем время последнего использования
    bask_cooldowns [ user_id ] = current_time

    # Initialize and start the FootGame
    Basketball_game = Basketball(bet, user_id, balance, bot1, dp, message)
    win_amount_commission = await Basketball_game.main()  # Get win amount

    # Check if win_amount_commission is None or 0
    if win_amount_commission is None:
        print(f"Ошибка: выигрыш не определен для пользователя {user_id}.")
        return

    if win_amount_commission > 0:
        new_balance = balance + win_amount_commission  # Update balance with win

        await db.update_user_balance(user_id, new_balance)  # Update in the database
        await db.cutehistory_plus(
            user_id , win_amount_commission , "предмет баскетбол")
        await db.set_items(user_id , "Геймпад" , 1)
        print(f"Пользователь {user_id} выиграл {win_amount_commission}. Баланс обновлён.")



async def gamepad(user_id, message):
    new_value = await db.update_give(user_id)

    if new_value is not None:
        await message.reply(f"<b>💰 Лимит переводов повышен на 20 кут\n🔰 Текущий лимит : {new_value}</b>", parse_mode="HTML")
    else:
        await message.reply("🛠 Ошибка, обратитесь к создателю. код ошибки 12141211232", parse_mode="HTML")


async def giveinfinity(user_id , message):
    give_limit = await db.get_user_give_limit(user_id)

    if give_limit is None:
        print("Лимит перевода не установлен.")
        return  # Прекращаем выполнение, если лимит отсутствует

    # Добавляем 100000 к текущему значению give для данного пользователя
    await db.add_to_user_give(user_id , 10000000)
    await message.reply('🚀 <b>Ваш лимит переводов пополнен на 10.000.000 кут, поздравляю! ⭐️</b>', parse_mode="HTML")
    print(f"К пользователю с user_id {user_id} добавлено 10000000 к его give лимиту.")


async def hui(user_id , message):
    await message.reply("<b><code>💧</code> Вода нужна для использования пистолетика <code>🔫</code></b>", parse_mode="HTML")



async def pistoletik(db, user_id, message):
    # Получение данных пользователя
    user_data = await db.fetch_all("SELECT items, balance FROM users WHERE user_id=$1", (user_id,))
    if not user_data:
        await message.reply("<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>", parse_mode="HTML")
        return

    row = user_data[0]
    user_inventory = decode_items(row["items"])

    key_name = "Вода ( для пистолетика )"
    case_name = "Пистолетик"

    if user_inventory.get(case_name, 0) > 0:
        if user_inventory.get(key_name, 0) > 0:
            # Получение данных цели
            if not message.reply_to_message:
                await message.reply("✖️ <b>Вы должны ответить на сообщение цели.</b>", parse_mode="HTML")
                return

            user_id_enemy = message.reply_to_message.from_user.id
            enemy_data = await db.fetch_all("SELECT balance FROM users WHERE user_id=$1", (user_id_enemy,))
            if not enemy_data:
                await message.reply("✖️ <b>Цель не найдена в базе данных.</b>", parse_mode="HTML")
                return

            enemy_balance = enemy_data[0]["balance"]
            random_percentage = random.randint(2 , 10)

            # Рассчитываем amount
            amount = int(enemy_balance * (random_percentage / 100))

            new_enemy_balance = max(0, enemy_balance - amount)  # Баланс цели не может быть отрицательным

            # Обновляем баланс цели
            await db.update_user_balance(user_id_enemy, new_enemy_balance)
            await db.cutehistory_minus(
                user_id , amount , "пистолетик с водой")

            # Обновляем баланс стрелявшего
            current_balance = row["balance"]
            new_balance = current_balance + amount
            await db.update_user_balance(user_id, new_balance)
            await db.cutehistory_plus(
                user_id , amount , "пистолетик с водой")

            # Уведомление о результате
            win_amount_formatted = "{:,.0f}".format(amount).replace(",", ".")
            sender_name = await db.get_firstname_by_user_id(user_id_enemy)
            sender_username = await db.get_username_by_id(user_id_enemy)
            name_link = await create_user_link(user_id_enemy , sender_name , sender_username)
            await message.reply(
                f"🔫 <b>Вы облили {name_link} водой, заработав {win_amount_formatted} кут</b>",
                parse_mode="HTML" , disable_web_page_preview=True
            )
            #item_name = "Пистолетик"
            #await db.delete_user_inventory1(user_id , item_name)

            # Обновление инвентаря
            user_inventory[key_name] -= 1
            if user_inventory[key_name] == 0:
                del user_inventory[key_name]

            #user_inventory[case_name] -= 1
            #if user_inventory[case_name] == 0:
                #del user_inventory[case_name]

            updated_inventory = encode_items(user_inventory)
            await db.fetch_all("UPDATE users SET items=$1 WHERE user_id=$2", (updated_inventory, user_id))
        else:
            await message.reply(
                "✖️ <b>У вас нет воды для выстрела из пистолетика.</b>", parse_mode="HTML"
            )
    else:
        await message.reply(
            "✖️ <b>У вас нет пистолетика для выстрела.</b>", parse_mode="HTML"
        )



async def freebonus(user_id, message):
    user_id = message.from_user.id

    # Генерация кнопок бонуса





    random.shuffle(emojisbonus)  # Перемешиваем список эмодзи
    randomemoji = random.choice(emojisbonus)
    randomtextfraza = random.choice(textfraza)

    # Выбираем случайное количество кнопок от 15 до 25
    num_buttons = random.randint(3, 10)


    # Выбираем эмодзи
    selected_emojis = emojisbonus [ :num_buttons ]   # Создаём кнопки с эмодзи
    buttons = [ InlineKeyboardButton(text=emoji , callback_data=str(random.randint(1 , itembonusbet))) for emoji in
                selected_emojis ]

    # Разбиваем на ряды по 5 кнопок
    keyboard_layout = [ buttons [ i:i + 5 ] for i in range(0 , len(buttons) , 5) ]

    # Добавляем кнопку ✖️ в отдельном ряду
    # keyboard_layout.append([ InlineKeyboardButton(text=" " , callback_data="9close_bonus", style="default" ,
    #                 icon_custom_emoji_id="5226660202035554522") ])

    # Создаём клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_layout)

    # Отправка сообщения с кнопками бонуса

    randomtextfraza = random.choice(textfraza)
    send_message_bonus = await message.reply(
        f"{randomtextfraza}" , parse_mode="HTML" , reply_markup=keyboard)

    # Сохранение id сообщения, отправленного пользователю
    message_id = send_message_bonus.message_id
    user_freebonus_requests.setdefault(user_id , [ ]).append(message_id)






async def shlapa(user_id , message):
    sticker_id = 'CAACAgIAAxkBAXtfxGbMgIb_AgtD9NwErGpIy2XXqxqZAAKBkQACKVhgSkNvSgnlLr-ENQQ'
    await message.reply_sticker(sticker_id)

    # Выбираем случайный предмет с учетом шанса выпадения
    item_name = await db.get_random_item_by_chance()
    await asyncio.sleep(1)
    if item_name:
        # Находим эмодзи предмета по его названию
        item_emoji = await db.find_emoji_by_item_name(item_name)

        # Если предмет выпал, выдаем его пользователю
        await db.set_items(user_id , item_name , 1)

        await message.reply(f"🎩 Шляпа использована!\n<b><code>{item_emoji}</code> {item_name}</b>", parse_mode="HTML")
    else:
        await message.reply("🎩 В этот раз ничего не выпало.", parse_mode="HTML")



        
@dp.callback_query(lambda c: c.data == 'close_freebonus')
async def close_bonus_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    if user_id not in user_freebonus_requests or message_id not in user_freebonus_requests[user_id]:
        randommessagebonus1 = random.choice(randommessagehelp)
        await callback_query.answer(randommessagebonus1)
        return
    try:
        # Удаляем текущее сообщение
        await callback_query.answer("❕ Сообщение с бонусом удалено.")
        await callback_query.message.delete()
    except aiogram.utils.exceptions.MessageToDeleteNotFound:
        await callback_query.answer(
            "🛠 Не удалось удалить сообщение, возможно, оно уже было удалено.", show_alert=True)
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        await callback_query.answer("🛠 Произошла ошибка при удалении сообщения.", show_alert=True)
