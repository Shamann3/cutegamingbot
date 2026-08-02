from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from collections import defaultdict
from bot.db_create.db import *
from bot.config.config import *
from pathlib import Path

#mystic_inline_keyboard = InlineKeyboardMarkup()
#button_help = InlineKeyboardButton(text="📚 Помощь" , callback_data="helpstarthelp")
#button_bonus = InlineKeyboardButton(text="🎁 Бонус" , callback_data="bonusstartbonus")
#button_freesubcutechat3 = InlineKeyboardButton(text="💰 Бесплатные куты" , callback_data="subcutechat3")
#button_for_cut_welcome = InlineKeyboardButton(text="Поиграем?)" , callback_data="greet_cut")

#mystic_inline_keyboard.add(button_help)
#mystic_inline_keyboard.add(button_bonus)  # Добавляем кнопку "🎁 Бонус" на новый ряд
#mystic_inline_keyboard.add(button_freesubcutechat3)
#mystic_inline_keyboard.add(button_for_cut_welcome)


async def create_start_inline_markup(subscription_status, user_id, db):
    buttons = []

    # Кнопки с лаконичными названиями
    button_play = InlineKeyboardButton(text="Играть!", callback_data="greet_cut", style="default" ,icon_custom_emoji_id="5206482003297342650")
    button_bonus = InlineKeyboardButton(text="Бонус", callback_data=str(random.randint(1 , bonusbet)) + "_+", style="default" ,icon_custom_emoji_id="5294001020039363545")
    button_kut = InlineKeyboardButton(text="О Куте", callback_data="3412helpstarthelp", style="default" ,icon_custom_emoji_id="5436339947080548936")
    button_profile = InlineKeyboardButton(text="Профиль", callback_data="9back_to_menu1", style="default" ,icon_custom_emoji_id="5192951739623447936")
    button_perks = InlineKeyboardButton(text="🚀 Плюшки", callback_data="subcutechat3")
    button_withdraw = InlineKeyboardButton(text="Вывод", callback_data="conc_stars", style="default" ,icon_custom_emoji_id="5848021027782661221")
    button_donate = InlineKeyboardButton(text="Донат", callback_data="insert_stars", style="default" ,icon_custom_emoji_id="5848259999763011021")
    button_questions = InlineKeyboardButton(text="Задания" , callback_data="questions_stars", style="default" ,icon_custom_emoji_id="5318892863780579996")
    button_blackshop = InlineKeyboardButton(
        text="Черный рынок" , callback_data="blackshop" , style="default" , icon_custom_emoji_id="5438440765908874600")

    button_about = InlineKeyboardButton(text="О нас", callback_data="about_start", style="default" ,icon_custom_emoji_id="6037421444789440735")


    # 1 ряд
    buttons.append([button_play])

    # Проверка бонуса
    last_open_time, data_open = await db.get_bonus_times(user_id)
    show_bonus_button = False

    if last_open_time is not None and data_open is not None:
        if isinstance(last_open_time, str):
            last_open_time = datetime.strptime(last_open_time, "%Y-%m-%d %H:%M:%S")
        if isinstance(data_open, str):
            data_open = datetime.strptime(data_open, "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_open_time).days >= 1:
            show_bonus_button = True
    else:
        show_bonus_button = True
    if enabled_bonus:
        if show_bonus_button:
            buttons.append([button_bonus])  # 2 ряд

    # 3 ряд
    buttons.append([button_kut])
    buttons.append([button_profile])

    # 4 ряд (Плюшки)
    #buttons.append([button_perks])

    # 5 ряд
    buttons.append([button_withdraw, button_donate])
    buttons.append([ button_questions ])
    buttons.append([ button_blackshop ])

    # 6 ряд
    buttons.append([button_about])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


BOT_USERNAME = "CuteGamingBot"

ADD_TO_GROUP_URL = (
    f"https://t.me/{BOT_USERNAME}"
    "?startgroup=true"
    "&admin=delete_messages+restrict_members+pin_messages+invite_users+manage_chat+manage_video_chats+promote_members"
)
button1 = InlineKeyboardButton(text="Играть", switch_inline_query="игры", style="default" ,icon_custom_emoji_id="5408935401442267103")
button2 = InlineKeyboardButton(text="Инструкция", callback_data="starthowtoplay", style="default" ,icon_custom_emoji_id="5269288899204640214")
button3 = InlineKeyboardButton(text="Добавить в чат", url=ADD_TO_GROUP_URL, style="default" ,icon_custom_emoji_id="5305796731106002595")
button4 = InlineKeyboardButton(text=" ", callback_data="9close_bonus", style="default" ,icon_custom_emoji_id="5226660202035554522")

# Создаем список кнопок
inline_keyboard = [
    [button1],
    [button2],  # Ряд с одной кнопкой
    [button3],  # Ряд с одной кнопкой
    [button4]   # Ряд с одной кнопкой
]

# Создаем разметку с кнопками
markup_start13412 = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
button_link = InlineKeyboardButton(text="🎩 Присоединиться", url="chat_link")
button_link2 = InlineKeyboardButton(text="🔎 Проверить подписку", callback_data='donesub')

# Создаем разметку с кнопками
inline_keyboard = [[button_link, button_link2]]

markup_error = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



button_socials2 = InlineKeyboardButton(text="Новости", url="https://t.me/CuteGamingNews", style="default" ,icon_custom_emoji_id="6050679691004612757")
button_socials11 = InlineKeyboardButton(text="Группа", url="https://t.me/CuteGamingChat", style="default" ,icon_custom_emoji_id="6034831751308644168")
button_socials22 = InlineKeyboardButton(text="💬 2№", url="https://t.me/CuteChat3")
button_socials3 = InlineKeyboardButton(text="Семья Cute", url="https://t.me/JerichoCuteFamily", style="default" ,icon_custom_emoji_id="5805553606635559688")
button_socials5 = InlineKeyboardButton(text="Отзывы", url="https://t.me/ReviewsCute", style="default" ,icon_custom_emoji_id="6028338546736107668")
button_socials6 = InlineKeyboardButton(text="Выплаты", url="https://t.me/CurrencyCute", style="default" ,icon_custom_emoji_id="6028346797368283073")
button_socials4 = InlineKeyboardButton(text="Поддержка", url="https://t.me/HelperCute", style="default" ,icon_custom_emoji_id="6039605143601680423")


socials = InlineKeyboardMarkup(inline_keyboard=[
    [button_socials3],
    [button_socials2],# Строка с кнопкой для группы
    [button_socials11],
    [button_socials5 , button_socials6],  # Строка с кнопкой для отзывов
    [button_socials4],  # Строка с кнопкой для поддержки
    [InlineKeyboardButton(text=" ", callback_data="9close_bonus", style="default" ,icon_custom_emoji_id="5226660202035554522")]  # Строка с кнопкой для закрытия
])



private_office_refferals = InlineKeyboardButton(text="Реферальная система", callback_data="refprofile1", style="primary" ,
                icon_custom_emoji_id="5208847722823587097")
# Пример дополнительных кнопок, которые можно раскомментировать по необходимости
# button_rewards = InlineKeyboardButton(text="🥇 Награды", callback_data="vip1")
# button_style = InlineKeyboardButton(text="📯 Стили", callback_data="style3412_")
# button_im = InlineKeyboardButton(text="🚘 Имущество", callback_data="im3412")

# Формируем клавиатуру с кнопками
privates = InlineKeyboardMarkup(inline_keyboard=[
    [private_office_refferals]  # Строка с кнопкой для рефералной системы
    # [button_rewards],  # Можно добавить другие кнопки по необходимости
    # [button_style],
    # [button_im],
])



profileprivatebuttons = InlineKeyboardButton(text="🌿 Реферальная система", callback_data="refprofile1")

# Создание клавиатуры с этой кнопкой
profileprivate = InlineKeyboardMarkup(inline_keyboard=[
    [profileprivatebuttons]  # Строка с кнопкой для рефералной системы
])




#games = ReplyKeyboardMarkup(
    #resize_keyboard=True,
    #selective=True,
    #keyboard=[
        #[KeyboardButton("ㅤ🎲ㅤ"), KeyboardButton("ㅤ🎳ㅤ"), KeyboardButton("ㅤ⚽️ㅤ")],
        #[KeyboardButton("ㅤ🏀ㅤ"), KeyboardButton("ㅤ🎰ㅤ"), KeyboardButton("ㅤ🎯ㅤ")],
        #[KeyboardButton("🎟 Лотерея"), KeyboardButton("🪨✂️📄"), KeyboardButton("🎱 Шарик")],
        #[KeyboardButton("🃏 Казино"), KeyboardButton("🚀 Краш"), KeyboardButton("📊 Трейд")],
        #[KeyboardButton("🎡 Фортуна"), KeyboardButton("🎩 Рулетка")],
        #[KeyboardButton("Вернуться в главное меню")]
    #]
#)

# Создание других клавиатур для отдельных игр

#ref1 = ReplyKeyboardMarkup(
#    keyboard=[[KeyboardButton("Вернуться в главное меню")]],
#    resize_keyboard=True
#)
# Пример клавиатуры для Кубов
#back_kube = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_kube.add(KeyboardButton("Куб 10000"))
#back_kube.row(KeyboardButton("Куб 5000"), KeyboardButton("Куб 1000"))
#back_kube.add(KeyboardButton("💸 Баланс"))
#back_kube.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Боулов
#back_boul = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_boul.add(KeyboardButton("Боул 10000"))
#back_boul.row(KeyboardButton("Боул 5000"), KeyboardButton("Боул 1000"))
#back_boul.add(KeyboardButton("💸 Баланс"))
#back_boul.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Баскетбола
#back_bask = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_bask.add(KeyboardButton("Баскет 10000"))
#back_bask.row(KeyboardButton("Баскет 5000"), KeyboardButton("Баскет 1000"))
#back_bask.add(KeyboardButton("💸 Баланс"))
#back_bask.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Слотов
#back_slots = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_slots.add(KeyboardButton("Слоты 10000"))
#back_slots.row(KeyboardButton("Слоты 5000"), KeyboardButton("Слоты 1000"))
#back_slots.add(KeyboardButton("💸 Баланс"))
#back_slots.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Трейда
#back_Trade = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_Trade.row(KeyboardButton("Трейд вверх 10000"), KeyboardButton("Трейд вниз 10000"))
#back_Trade.row(KeyboardButton("Трейд вверх 5000"), KeyboardButton("Трейд вниз 5000"))
#back_Trade.row(KeyboardButton("Трейд вверх 1000"), KeyboardButton("Трейд вниз 1000"))
#back_Trade.add(KeyboardButton("💸 Баланс"))
#back_Trade.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Казино
#back_casino = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_casino.add(KeyboardButton("Казино 10000"))
#back_casino.row(KeyboardButton("Казино 5000"), KeyboardButton("Казино 1000"))
#back_casino.add(KeyboardButton("💸 Баланс"))
#back_casino.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Рулетки
#back_roul = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_roul.add(KeyboardButton("Лотерея 10000"))
#back_roul.row(KeyboardButton("Лотерея 5000"), KeyboardButton("Лотерея 1000"))
#back_roul.add(KeyboardButton("💸 Баланс"))
#back_roul.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Шарика
#back_ball = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_ball.add(KeyboardButton("Шарик 10000"))
#back_ball.row(KeyboardButton("Шарик 5000"), KeyboardButton("Шарик 1000"))
#back_ball.add(KeyboardButton("💸 Баланс"))
#back_ball.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Кнб
#back_knb = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_knb.add(KeyboardButton("Кнб 10000"))
#back_knb.row(KeyboardButton("Кнб 5000"), KeyboardButton("Кнб 1000"))
#back_knb.add(KeyboardButton("💸 Баланс"))
#back_knb.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Фортуны
#back_roul1 = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_roul1.add(KeyboardButton("Фортуна 5000 К"), KeyboardButton("Фортуна 5000 Ч"))
#back_roul1.row(KeyboardButton("Фортуна 5000 П"), KeyboardButton("Фортуна 5000 Н"))
#back_roul1.row(KeyboardButton("Фортуна 5000 [число - число]"))
#back_roul1.row(KeyboardButton("Фортуна 5000 [число]"))
#back_roul1.add(KeyboardButton("💸 Баланс"))
#back_roul1.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Краша
#back_crash1 = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_crash1.add(KeyboardButton("Краш 1.5 1000"), KeyboardButton("Краш 2 1000"))
#back_crash1.row(KeyboardButton("Краш 1.5 10000"), KeyboardButton("Краш 2 10000"))
#back_crash1.row(KeyboardButton("Краш 1.5 15000"), KeyboardButton("Краш 2 15000"))
#back_crash1.add(KeyboardButton("💸 Баланс"))
#back_crash1.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Дартса
#back_dart = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_dart.add(KeyboardButton("Дарт 10000"))
#back_dart.row(KeyboardButton("Дарт 5000"), KeyboardButton("Дарт 1000"))
#back_dart.add(KeyboardButton("💸 Баланс"))
#back_dart.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Футбола
#back_foot = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_foot.add(KeyboardButton("Футбол 10000"))
#back_foot.row(KeyboardButton("Футбол 5000"), KeyboardButton("Футбол 1000"))
#back_foot.add(KeyboardButton("💸 Баланс"))
#back_foot.add(KeyboardButton("🎩 Вернуться в главное меню"))

# Пример клавиатуры для Рулетки (черный)
#back_black = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
#back_black.add(KeyboardButton("Рулетка 10000"))
#back_black.row(KeyboardButton("Рулетка 5000"), KeyboardButton("Рулетка 1000"))
#back_black.add(KeyboardButton("💸 Баланс"))
#back_black.add(KeyboardButton("🎩 Вернуться в главное меню"))





btn_help1 = InlineKeyboardButton(text="Что такое Кут?", callback_data="help_btn1", style="default" ,icon_custom_emoji_id="5318959255385043017")
btn_help22 = InlineKeyboardButton(text="Как заработать?", callback_data="help_btn22", style="default" ,icon_custom_emoji_id="5303547422373349738")
btn_help2 = InlineKeyboardButton(text="Игры", callback_data="help_btn2", style="default" ,icon_custom_emoji_id="5319229795375018323")
btn_help3 = InlineKeyboardButton(text="Разное", callback_data="help_btn3", style="default" ,icon_custom_emoji_id="5354789281317548026")
btn_help4 = InlineKeyboardButton(text="💘 Браки", callback_data="help_btn4")
btn_help5 = InlineKeyboardButton(text="Магазин", callback_data="help_btn5", style="default" ,icon_custom_emoji_id="5206249426523295267")

btn_help6 = InlineKeyboardButton(text="🛡 Кланы", callback_data="help_btn6")
# btn_help7 = InlineKeyboardButton(text="🌳 Золотое дерево", callback_data="help_btn7")
# btn_help8 = InlineKeyboardButton(text="🏡 Имущество", callback_data="help_btn8")
# btn_help9 = InlineKeyboardButton(text="🧑🏼‍🌾 Фермерство", callback_data="help_btn9")
btn_help10 = InlineKeyboardButton(text="Функции", callback_data="help_btnfunk", style="default" ,icon_custom_emoji_id="5206482003297342650")
btn_helpking = InlineKeyboardButton(text="Царь статы", callback_data="help_btnking", style="default" ,icon_custom_emoji_id="5262924479226473498")

btn_help1111 = InlineKeyboardButton(text="🩵 Оформление профиля", callback_data="help_editprofile")

btn_help5123 = InlineKeyboardButton(text="Админы", callback_data="help_btnadmin", style="default" ,icon_custom_emoji_id="5352668069984510307")
btn_help11 = InlineKeyboardButton(text="Скрыть", callback_data="help_deletehelp", style="default" ,icon_custom_emoji_id="5226660202035554522")

# Создаем список кнопок
inline_keyboard = [
    [btn_help1],
    [btn_help22],
    [btn_help10],
    [btn_helpking],
    [btn_help2, btn_help3],
    [btn_help5],
    [btn_help5123],
    #[btn_help4],
    # [btn_help6],  # Разкомментируйте, если нужно,
    [btn_help11]
]

# Создаем InlineKeyboardMarkup с кнопками
btn_help = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)






#btn_help8 = InlineKeyboardMarkup(text="VIP", callback_data="help_btn8")


btn_help19 = InlineKeyboardButton(text="Что такое Кут?", callback_data="9help_btn1", style="default" ,icon_custom_emoji_id="5318959255385043017")
btn_help229 = InlineKeyboardButton(text="Как заработать?", callback_data="9help_btn22", style="default" ,icon_custom_emoji_id="5303547422373349738")
btn_help29 = InlineKeyboardButton(text="Игры", callback_data="9help_btn2", style="default" ,icon_custom_emoji_id="5319229795375018323")
btn_help39 = InlineKeyboardButton(text="Разное", callback_data="9help_btn3", style="default" ,icon_custom_emoji_id="5354789281317548026")
btn_help49 = InlineKeyboardButton(text="💘 Браки", callback_data="9help_btn4")
btn_help59 = InlineKeyboardButton(text="Магазин", callback_data="9help_btn5", style="default" ,icon_custom_emoji_id="5206249426523295267")
btn_help69 = InlineKeyboardButton(text="🛡 Кланы", callback_data="9help_btn6")
# btn_help79 = InlineKeyboardButton(text="🌳 Золотое дерево", callback_data="9help_btn7")
# btn_help89 = InlineKeyboardButton(text="🏡 Имущество", callback_data="9help_btn8")
# btn_help99 = InlineKeyboardButton(text="🧑🏼‍🌾 Фермерство", callback_data="9help_btn9")
btn_help109 = InlineKeyboardButton(text="Функции", callback_data="9help_btnfunk", style="default" ,icon_custom_emoji_id="5206482003297342650")
btn_helpking9 = InlineKeyboardButton(text="Царь статы", callback_data="9help_btnking", style="default" ,icon_custom_emoji_id="5262924479226473498")

btn_help11119 = InlineKeyboardButton(text="🩵 Оформление профиля", callback_data="9help_editprofile")
btn_help5123123 = InlineKeyboardButton(text="Админы", callback_data="help_btnadmin", style="default" ,icon_custom_emoji_id="5352668069984510307")
btn_help119 = InlineKeyboardButton(text="Скрыть", callback_data="9help_deletehelp", style="default" ,icon_custom_emoji_id="5226660202035554522")

# Создаем список кнопок
inline_keyboard = [
    [btn_help19],
    [btn_help229],
    [btn_help109],
    [btn_helpking9],
    [btn_help29, btn_help39],
    [btn_help59],
    [btn_help5123123],
    #[btn_help49],
    # [btn_help69],  # Разкомментируйте, если нужно
    [btn_help119]
]

# Создаем InlineKeyboardMarkup с кнопками
btn_help9 = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)




btn_help119 = InlineKeyboardButton(text="Скрыть" , callback_data="deletehelp0101", style="default" ,icon_custom_emoji_id="5226660202035554522")
inline_keyboard = [ [ btn_help119 ] ]
btn_helplol = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)




btn_info_inline = InlineKeyboardButton(text="Что такое Кут?", callback_data="help_info_main", style="default" ,icon_custom_emoji_id="5318959255385043017")
btn_earnings_inline = InlineKeyboardButton(text="Как заработать?", callback_data="help_earnings", style="default" ,icon_custom_emoji_id="5303547422373349738")
btn_games_inline = InlineKeyboardButton(text="Игры", callback_data="help_games", style="default" ,icon_custom_emoji_id="5319229795375018323")
btn_misc_inline = InlineKeyboardButton(text="Разное", callback_data="help_misc", style="default" ,icon_custom_emoji_id="5354789281317548026")
btn_marriages_inline = InlineKeyboardButton(text="💘 Браки", callback_data="help_marriages")
btn_market_inline = InlineKeyboardButton(text="Магазин", callback_data="help_market", style="default" ,icon_custom_emoji_id="5206249426523295267")
btn_clans_inline = InlineKeyboardButton(text="🛡 Кланы", callback_data="help_clans")
# btn_tree_inline = InlineKeyboardButton(text="🌳 Золотое дерево", callback_data="help_tree")
# btn_property_inline = InlineKeyboardButton(text="🏡 Имущество", callback_data="help_property")
# btn_farming_inline = InlineKeyboardButton(text="🧑🏼‍🌾 Фермерство", callback_data="help_farming")
btn_functions_inline = InlineKeyboardButton(text="Функции", callback_data="help_functions", style="default" ,icon_custom_emoji_id="5206482003297342650")
btn_helpking91 = InlineKeyboardButton(text="Царь статы", callback_data="9help_btnking", style="default" ,icon_custom_emoji_id="5262924479226473498")
btn_hide_inline = InlineKeyboardButton(text="Скрыть", callback_data="help_hide", style="default" ,icon_custom_emoji_id="5226660202035554522")
btn_help5123123123 = InlineKeyboardButton(text="Админы", callback_data="help_btnadmin", style="default" ,icon_custom_emoji_id="5352668069984510307")
btn_help1111_inline = InlineKeyboardButton(text="🩵 Оформление профиля", callback_data="help_profileedit")


# Собираем кнопки в список
inline_keyboard = [
    [btn_info_inline],
    [btn_earnings_inline],
    [btn_functions_inline],
    [btn_games_inline, btn_misc_inline],
    [btn_market_inline],
    [btn_help5123123123],
    #[btn_marriages_inline],
    [btn_hide_inline]
]

# Создаем InlineKeyboardMarkup с кнопками
btn_help_inline = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)








#btn_help.add(btn_help7)



btn_topcutes = InlineKeyboardButton(text="Богачи" , callback_data="cutessss", style="default" ,
                icon_custom_emoji_id="5321499578216769477")
btn_topstate = InlineKeyboardButton(text="Статистика" , callback_data="state123", style="default" ,
                icon_custom_emoji_id="5307577823978882332")
btn_wins = InlineKeyboardButton(text="Wins" , callback_data="userwinstop", style="default" ,
                icon_custom_emoji_id="5848259999763011021")
btn_loose = InlineKeyboardButton(text="Looses" , callback_data="userloosetop", style="default" ,
                icon_custom_emoji_id="5420315771991497307")
btn_donaters = InlineKeyboardButton(text="Донатеры" , callback_data="donaters34123412", style="default" ,
                icon_custom_emoji_id="5438440765908874600")
btn_winsamount = InlineKeyboardButton(text="Выиграно" , callback_data="userwinamountstop", style="default" ,
                icon_custom_emoji_id="5165970432947389596")
btn_invite = InlineKeyboardButton(text="Приглашения" , callback_data="topinvite", style="default" ,
                icon_custom_emoji_id="5424987025667293801")
btn_balancegroup = InlineKeyboardButton(text="Баланс групп" , callback_data="balancegrouptop", style="default" ,
                icon_custom_emoji_id="5425098093521571791")
btn_topmarry = InlineKeyboardButton(text="🌷 Браки" , callback_data="marry1213")
btn_close = InlineKeyboardButton(text="Скрыть" , callback_data="help_deletestate", style="default" ,icon_custom_emoji_id="5226660202035554522")

# Создание inline_keyboard
inline_keyboard = [ [ btn_topcutes ] ,
                    [ btn_wins , btn_loose ] ,
                    [ btn_balancegroup ],
                    [ btn_donaters ] ,
                    [ btn_winsamount ] ,
                    [ btn_topstate ] ,
                    [ btn_invite ] ,
                    [ btn_close ] ]

# Создание InlineKeyboardMarkup
btn_top = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)




btn_backtop = InlineKeyboardButton(text="Назад", callback_data="backtop", style="default" ,
                icon_custom_emoji_id="5255703720078879038")
btn_backtop123 = InlineKeyboardMarkup(inline_keyboard=[[btn_backtop]])

btn_back = InlineKeyboardButton(text="Назад", callback_data="back_btn", style="default" ,
                icon_custom_emoji_id="5255703720078879038")
btn_back1 = InlineKeyboardMarkup(inline_keyboard=[[btn_back]])

btn_back11 = InlineKeyboardButton(text="Назад", callback_data="back_btn1", style="default" ,
                icon_custom_emoji_id="5255703720078879038")
btn_back12 = InlineKeyboardMarkup(inline_keyboard=[[btn_back11]])

btn_back111 = InlineKeyboardButton(text="Назад", callback_data="back_to_menu1", style="default" ,
                icon_custom_emoji_id="5255703720078879038")
btn_back122 = InlineKeyboardMarkup(inline_keyboard=[[btn_back111]])

#btn_admin = InlineKeyboardButton(text = "📲Рассылка пользователям бота", callback_data = "repost_btn1")
#btns_repost = InlineKeyboardMarkup().add(btn_admin)

#btn_admin1 = InlineKeyboardButton(text = "📲Разослать", callback_data = "repost_btn_send")
#btns_repost1 = InlineKeyboardMarkup().add(btn_admin1)


#btn_apply_buy_farm = InlineKeyboardButton(text = f"Купить RTX4090 | {str(price_farm)} кутов", callback_data = "btn_apply_buy_farm")
#btn_apply_buy_farm_markup = InlineKeyboardMarkup().add(btn_apply_buy_farm)

#btn_apply_buy_mine = InlineKeyboardButton(text = f"Купить руду | {str(price_mine)} кутов", callback_data = "btn_apply_buy_mine")
#btn_apply_buy_mine_markup = InlineKeyboardMarkup().add(btn_apply_buy_mine)

#btn_apply_buy_buisness = InlineKeyboardButton(text = f"Купить 1 м^3 | {str(price_buisness)} кутов", callback_data = "btn_apply_buy_buisness")
#btn_apply_buy_buisness_markup = InlineKeyboardMarkup().add(btn_apply_buy_buisness)

#start_work_farm = InlineKeyboardButton(text = f"Приступить к работе", callback_data = "start_work_farm")
#start_work_farm_markup = InlineKeyboardMarkup().add(start_work_farm)

#start_work_mine = InlineKeyboardButton(text = f"Приступить к работе", callback_data = "start_work_mine")
#start_work_mine_markup = InlineKeyboardMarkup().add(start_work_mine)

#start_work_buisness = InlineKeyboardButton(text = f"Приступить к работе", callback_data = "start_work_buisness")
#start_work_buisness_markup = InlineKeyboardMarkup().add(start_work_buisness)


#btn_farm_get_payment = InlineKeyboardButton(text = f"💰 Получить прибыль", callback_data = "btn_farm_get_payment")
#btn_farm_pay_taxes = InlineKeyboardButton(text = f"📜 Оплатить налоги", callback_data = "btn_farm_pay_taxes")
#btn_farm_buy_farm = InlineKeyboardButton(text = f"🛠 Купить RTX4090 | {str(price_farm)} кутов", callback_data = "btn_farm_buy_farm")
#btn_farm_kb = InlineKeyboardMarkup(row_width = 2).add(btn_farm_get_payment).add(btn_farm_pay_taxes).add(btn_farm_buy_farm)

#btn_buisness_get_payment = InlineKeyboardButton(text = f"💰 Получить прибыль", callback_data = "btn_buisness_get_payment")
#btn_buisness_pay_taxes = InlineKeyboardButton(text = f"📜 Оплатить налоги", callback_data = "btn_buisness_pay_taxes")
#btn_buisness_buy_farm = InlineKeyboardButton(text = f"🛠 Купить 1км^3 | {str(price_farm)} кутов", callback_data = "btn_buisness_buy_farm")
#btn_buisness_kb = InlineKeyboardMarkup(row_width=2).add(btn_buisness_get_payment).add(btn_buisness_pay_taxes).add(btn_buisness_buy_farm)

#btn_mine_get_payment = InlineKeyboardButton(text = f"💰 Получить прибыль", callback_data = "btn_mine_get_payment")
#btn_mine_buy_farm = InlineKeyboardButton(text = f"🛠 Поиск следующей руды | {str(price_farm)} кутов", callback_data = "btn_mine_buy_farm")
#btn_mine_kb = InlineKeyboardMarkup(row_width=2).add(btn_mine_get_payment).add(btn_mine_buy_farm)

#btn_add_bot_confirm = InlineKeyboardButton(text = f"Я добавил бота ✅", callback_data = "btn_add_bot_confirm")
#btn_add_bot_confirm_markup = InlineKeyboardMarkup().add(btn_add_bot_confirm)

#buis_buy_btn = InlineKeyboardButton(text = f"Запустить фабрику | {price_buisness} кутов", callback_data = "btn_buy_factory")
#buis_but_markup = InlineKeyboardMarkup().add(buis_buy_btn)

#buis_career_buy_btn = InlineKeyboardButton(text = f"Запустить карьер | {price_career} кутов", callback_data = "btn_buy_career")
#buis_career_but_markup = InlineKeyboardMarkup().add(buis_career_buy_btn)

#buis_solar_buy_btn = InlineKeyboardButton(text = f"Запустить бизнес по панелям | {price_solar} кутов", callback_data = "btn_buy_solar")
#buis_solar_but_markup = InlineKeyboardMarkup().add(buis_solar_buy_btn)

#buis_building_buy_btn = InlineKeyboardButton(text = f"Запустить бизнес по постройкам | {price_buildings} кутов", callback_data = "btn_buy_building")
#buis_building_but_markup = InlineKeyboardMarkup().add(buis_building_buy_btn)


#info_marr_btn = InlineKeyboardButton(text = f"📝Инфо Пользователя", callback_data = "marr_info")
#marriage_buttons = InlineKeyboardMarkup(row_width=1).add(info_marr_btn)

def mines_2_btns(listt : list = None, rad = None):
    column1 = InlineKeyboardButton(text = " ", callback_data = "lol0")
    column2 = InlineKeyboardButton(text = " ", callback_data = "lol1")
    column3 = InlineKeyboardButton(text = " ", callback_data = "lol2")
    column4 = InlineKeyboardButton(text = " ", callback_data = "lol3")
    column5 = InlineKeyboardButton(text = " ", callback_data = "lol4")
    column6 = InlineKeyboardButton(text = " ", callback_data = "lol5")
    column7 = InlineKeyboardButton(text = " ", callback_data = "lol6")
    column8 = InlineKeyboardButton(text = " ", callback_data = "lol7")
    column9 = InlineKeyboardButton(text = " ", callback_data = "lol8")
    column10 = InlineKeyboardButton(text = " ", callback_data = "lol9")
    column11 = InlineKeyboardButton(text = " ", callback_data = "lol10")
    column12 = InlineKeyboardButton(text = " ", callback_data = "lol11")
    column13 = InlineKeyboardButton(text = " ", callback_data = "lol12")
    column14 = InlineKeyboardButton(text = " ", callback_data = "lol13")
    column15 = InlineKeyboardButton(text = " ", callback_data = "lol14")
    column16 = InlineKeyboardButton(text = " ", callback_data = "lol15")
    column17 = InlineKeyboardButton(text = " ", callback_data = "lol16")
    column18 = InlineKeyboardButton(text = "  ️", callback_data = "lol17")
    column19 = InlineKeyboardButton(text = " ", callback_data = "lol18")
    column20 = InlineKeyboardButton(text = " ", callback_data = "lol19")
    column21 = InlineKeyboardButton(text = " ", callback_data = "lol20")
    column22 = InlineKeyboardButton(text = " ", callback_data = "lol21")
    column23 = InlineKeyboardButton(text = " ", callback_data = "lol22")
    column24 = InlineKeyboardButton(text = " ", callback_data = "lol23")
    column25 = InlineKeyboardButton(text = " ", callback_data = "lol24")
    take_money = InlineKeyboardButton(text = "Остановить", callback_data = "get_payment_mines")
    if listt:
        indices_for_clicked_poison = [index for index, value in enumerate(listt) if value == "*"]
        indices_for_clicked_cush = [index for index, value in enumerate(listt) if value == "I"]
        indices_for_clicked_money = [index for index, value in enumerate(listt) if value == "X"]

        for i in indices_for_clicked_poison:
            if i == 0:
                column1 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 1:
                column2 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 2:
                column3 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 3:
                column4 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 4:
                column5 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 5:
                column6 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 6:
                column7 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 7:
                column8 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 8:
                column9 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 9:
                column10 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 10:
                column11 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 11:
                column12 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 12:
                column13 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 13:
                column14 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 14:
                column15 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 15:
                column16 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 16:
                column17 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 17:
                column18 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 18:
                column19 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 19:
                column20 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 20:
                column21 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 21:
                column22 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 22:
                column23 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 23:
                column24 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 24:
                column25 = InlineKeyboardButton(text = "💣", callback_data = "#")
        for i in indices_for_clicked_cush:
            if i == 0:
                column1 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 1:
                column2 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 2:
                column3 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 3:
                column4 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 4:
                column5 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 5:
                column6 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 6:
                column7 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 7:
                column8 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 8:
                column9 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 9:
                column9 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 10:
                column10 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 11:
                column11 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 12:
                column12 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 13:
                column13 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 14:
                column14 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 15:
                column15 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 16:
                column16 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 17:
                column17 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 18:
                column18 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 19:
                column19 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 20:
                column20 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 21:
                column21 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 22:
                column22 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 23:
                column23 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 24:
                column24 = InlineKeyboardButton(text = "💰", callback_data = "#")
            elif i == 25:
                column25 = InlineKeyboardButton(text = "💰", callback_data = "#")
        for i in indices_for_clicked_money:
            if i == 0:
                column1 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 1:
                column2 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 2:
                column3 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 3:
                column4 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 4:
                column5 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 5:
                column6 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 6:
                column7 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 7:
                column8 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 8:
                column9 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 9:
                column9 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 10:
                column10 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 11:
                column11 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 12:
                column12 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 13:
                column13 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 14:
                column14 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 15:
                column15 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 16:
                column16 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 17:
                column17 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 18:
                column18 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 19:
                column19 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 20:
                column20 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 21:
                column21 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 22:
                column22 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 23:
                column23 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 24:
                column24 = InlineKeyboardButton(text = "💵", callback_data = "#")
            elif i == 25:
                column25 = InlineKeyboardButton(text = "💵", callback_data = "#")
    if rad == 0:
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(take_money)
    elif rad == 1:
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(take_money)
    elif rad == 2:
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(column11, column12, column13, column14, column15)
    elif rad == 3:
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(column11, column12, column13, column14, column15).add(column16, column17, column18, column19, column20).add(take_money)
    elif rad == 4:
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(column11, column12, column13, column14, column15).add(column16, column17, column18, column19, column20).add(column21, column22, column23, column24, column25).add(take_money)

def mines_btns(listt : list = None, lose : list  = None):
    column1 = InlineKeyboardButton(text = " ", callback_data = "vol0")
    column2 = InlineKeyboardButton(text = " ", callback_data = "vol1")
    column3 = InlineKeyboardButton(text = " ", callback_data = "vol2")
    column4 = InlineKeyboardButton(text = " ", callback_data = "vol3")
    column5 = InlineKeyboardButton(text = " ", callback_data = "vol4")
    column6 = InlineKeyboardButton(text = " ", callback_data = "vol5")
    column7 = InlineKeyboardButton(text = " ", callback_data = "vol6")
    column8 = InlineKeyboardButton(text = " ", callback_data = "vol7")
    column9 = InlineKeyboardButton(text = " ", callback_data = "vol8")
    column10 = InlineKeyboardButton(text = " ", callback_data = "vol9")
    column11 = InlineKeyboardButton(text = " ", callback_data = "vol10")
    column12 = InlineKeyboardButton(text = " ", callback_data = "vol11")
    column13 = InlineKeyboardButton(text = " ", callback_data = "vol12")
    column14 = InlineKeyboardButton(text = " ", callback_data = "vol13")
    column15 = InlineKeyboardButton(text = " ", callback_data = "vol14")
    column16 = InlineKeyboardButton(text = " ", callback_data = "vol15")
    column17 = InlineKeyboardButton(text = " ", callback_data = "vol16")
    column18 = InlineKeyboardButton(text = "  ️", callback_data = "vol17")
    column19 = InlineKeyboardButton(text = " ", callback_data = "vol18")
    column20 = InlineKeyboardButton(text = " ", callback_data = "vol19")
    column21 = InlineKeyboardButton(text = " ", callback_data = "vol20")
    column22 = InlineKeyboardButton(text = " ", callback_data = "vol21")
    column23 = InlineKeyboardButton(text = " ", callback_data = "vol22")
    column24 = InlineKeyboardButton(text = " ", callback_data = "vol23")
    column25 = InlineKeyboardButton(text = " ", callback_data = "vol24")
    accept = InlineKeyboardButton(text = "Забрать выигрыш", callback_data = "stop")

    if lose:
        column1 = InlineKeyboardButton(text = " ", callback_data = "#")
        column2 = InlineKeyboardButton(text = " ", callback_data = "#")
        column3 = InlineKeyboardButton(text = " ", callback_data = "#")
        column4 = InlineKeyboardButton(text = " ", callback_data = "#")
        column5 = InlineKeyboardButton(text = " ", callback_data = "#")
        column6 = InlineKeyboardButton(text = " ", callback_data = "#")
        column7 = InlineKeyboardButton(text = " ", callback_data = "#")
        column8 = InlineKeyboardButton(text = " ", callback_data = "#")
        column9 = InlineKeyboardButton(text = " ", callback_data = "#")
        column10 = InlineKeyboardButton(text = " ", callback_data = "#")
        column11 = InlineKeyboardButton(text = " ", callback_data = "#")
        column12 = InlineKeyboardButton(text = " ", callback_data = "#")
        column13 = InlineKeyboardButton(text = " ", callback_data = "#")
        column14 = InlineKeyboardButton(text = " ", callback_data = "#")
        column15 = InlineKeyboardButton(text = " ", callback_data = "#")
        column16 = InlineKeyboardButton(text = " ", callback_data = "#")
        column17 = InlineKeyboardButton(text = " ", callback_data = "#")
        column18 = InlineKeyboardButton(text = " ", callback_data = "#")
        column19 = InlineKeyboardButton(text = " ", callback_data = "#")
        column20 = InlineKeyboardButton(text = " ", callback_data = "#")
        column21 = InlineKeyboardButton(text = " ", callback_data = "#")
        column22 = InlineKeyboardButton(text = " ", callback_data = "#")
        column23 = InlineKeyboardButton(text = " ", callback_data = "#")
        column24 = InlineKeyboardButton(text = " ", callback_data = "#")
        column25 = InlineKeyboardButton(text = " ", callback_data = "#")
        indices_for_clicked_X = [index for index, value in enumerate(lose) if value == "X"]
        indices_for_clicked_o = [index for index, value in enumerate(lose) if value == "o"]
        for i in indices_for_clicked_X:
            if i == 0:
                column1 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 1:
                column2 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 2:
                column3 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 3:
                column4 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 4:
                column5 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 5:
                column6 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 6:
                column7 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 7:
                column8 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 8:
                column9 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 9:
                column10 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 10:
                column11 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 11:
                column12 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 12:
                column13 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 13:
                column14 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 14:
                column15 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 15:
                column16 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 16:
                column17 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 17:
                column18 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 18:
                column19 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 19:
                column20 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 20:
                column21 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 21:
                column22 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 22:
                column23 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 23:
                column24 = InlineKeyboardButton(text = "💣", callback_data = "#")
            elif i == 24:
                column25 = InlineKeyboardButton(text = "💣", callback_data = "#")

        for i in indices_for_clicked_o:
            if i == 0:
                column1 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 1:
                column2 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 2:
                column3 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 3:
                column4 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 4:
                column5 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 5:
                column6 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 6:
                column7 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 7:
                column8 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 8:
                column9 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 9:
                column9 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 10:
                column10 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 11:
                column11 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 12:
                column12 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 13:
                column13 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 14:
                column14 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 15:
                column15 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 16:
                column16 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 17:
                column17 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 18:
                column18 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 19:
                column19 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 20:
                column20 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 21:
                column21 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 22:
                column22 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 23:
                column23 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 24:
                column24 = InlineKeyboardButton(text = " ", callback_data = "#")
            elif i == 25:
                column25 = InlineKeyboardButton(text = " ", callback_data = "#")
        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(column11, column12, column13, column14, column15).add(column16, column17, column18, column19, column20).add(column21, column22, column23, column24, column25)
    else:
        indices_for_clicked = [index for index, value in enumerate(listt) if value == "o"]
        if indices_for_clicked:
            for i in indices_for_clicked:
                if i == 0:
                    column1 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 1:
                    column2 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 2:
                    column3 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 3:
                    column4 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 4:
                    column5 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 5:
                    column6 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 6:
                    column7 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 7:
                    column8 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 8:
                    column9 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 9:
                    column10 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 10:
                    column11 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 11:
                    column12 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 12:
                    column13 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 13:
                    column14 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 14:
                    column15 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 15:
                    column16 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 16:
                    column17 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 17:
                    column18 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 18:
                    column19 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 19:
                    column20 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 20:
                    column21 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 21:
                    column22 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 22:
                    column23 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 23:
                    column24 = InlineKeyboardButton(text = "✔️", callback_data = "#")
                elif i == 24:
                    column25 = InlineKeyboardButton(text = "✔️", callback_data = "#")

        return InlineKeyboardMarkup(row_width=5).add(column1, column2, column3, column4, column5).add(column6, column7, column8, column9, column10).add(column11, column12, column13, column14, column15).add(column16, column17, column18, column19, column20).add(column21, column22, column23, column24, column25).add(accept)

async def toe_btns(listt, emoji, emoji2):
    # Ensure listt is iterable
    if not isinstance(listt, (list, tuple)):
        raise ValueError("Input must be a list or tuple")

    # Define buttons with initial empty text
    column1 = InlineKeyboardButton(text=" ", callback_data="col1")
    column2 = InlineKeyboardButton(text=" ", callback_data="col2")
    column3 = InlineKeyboardButton(text=" ", callback_data="col3")
    column4 = InlineKeyboardButton(text=" ", callback_data="col4")
    column5 = InlineKeyboardButton(text=" ", callback_data="col5")
    column6 = InlineKeyboardButton(text=" ", callback_data="col6")
    column7 = InlineKeyboardButton(text=" ", callback_data="col7")
    column8 = InlineKeyboardButton(text=" ", callback_data="col8")
    column9 = InlineKeyboardButton(text=" ", callback_data="col9")

    # Find indices of 'o' and 'x'
    indices_for_o = [index for index, value in enumerate(listt) if value == "o"]
    indices_for_x = [index for index, value in enumerate(listt) if value == "x"]

    # Assign appropriate emoji to the buttons for 'o'
    for i in indices_for_o:
        if i == 0:
            column1 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 1:
            column2 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 2:
            column3 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 3:
            column4 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 4:
            column5 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 5:
            column6 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 6:
            column7 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 7:
            column8 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")
        elif i == 8:
            column9 = InlineKeyboardButton(text=f'{emoji}', callback_data="#")

    # Assign appropriate emoji to the buttons for 'x'
    for i in indices_for_x:
        if i == 0:
            column1 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 1:
            column2 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 2:
            column3 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 3:
            column4 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 4:
            column5 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 5:
            column6 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 6:
            column7 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 7:
            column8 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")
        elif i == 8:
            column9 = InlineKeyboardButton(text=f'{emoji2}', callback_data="#")

    # Return the markup with buttons arranged in rows
    return InlineKeyboardMarkup(row_width=3).add(column1, column2, column3).add(column4, column5, column6).add(column7, column8, column9)
#keyboardvuvodcutesfrombots = InlineKeyboardMarkup(
#        row_width=6 , inline_keyboard=[
#            [ InlineKeyboardButton(text="15⭐️" , callback_data="btnstars_15") ,
#            InlineKeyboardButton(text="25⭐️" , callback_data="btnstars_25") ] ,
#
#            [ InlineKeyboardButton(text="50⭐️" , callback_data="btnstars_50") ,
 #             InlineKeyboardButton(text="100⭐️" , callback_data="btnstars_100") ] ,
#
#            [ InlineKeyboardButton(text="150⭐️" , callback_data="btnstars_150") ,
#              InlineKeyboardButton(text="300⭐️" , callback_data="btnstars_300") ] ,
#
#            [ InlineKeyboardButton(text="350⭐️" , callback_data="btnstars_350") ,
 #             InlineKeyboardButton(text="500⭐️" , callback_data="btnstars_500") ] ,
#
 #           [ InlineKeyboardButton(text="1.000⭐️" , callback_data="btnstars_1000") ] ,
#
#            [ InlineKeyboardButton(text=" " , callback_data="9close_bonus", style="default" ,
#                 icon_custom_emoji_id="5226660202035554522") ] ])


# ============================================================
# ✅ Gift helpers (ЛИМИТЫ ПРАВИЛЬНО)
# ============================================================
async def extract_gift_counts(bot1, gift_id: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Возвращает (used, remaining, total)
    Где:
      total     = total_count
      remaining = remaining_count
      used      = total - remaining
    """
    try:
        gifts_response = await bot1.get_available_gifts()
        gift_list = getattr(gifts_response, "gifts", [])
    except Exception as e:
        print(f"[GIFTS][COUNTS][ERROR] get_available_gifts: {e}")
        return None, None, None

    for gift in gift_list:
        try:
            current_id = str(getattr(gift, "id", ""))
            if current_id != str(gift_id):
                continue

            total = getattr(gift, "total_count", None)
            remaining = getattr(gift, "remaining_count", None)

            if total is None or remaining is None:
                return None, None, None

            total_i = int(total)
            remaining_i = int(remaining)

            used_i = max(0, total_i - remaining_i)
            remaining_i = max(0, remaining_i)

            return used_i, remaining_i, total_i

        except Exception as e:
            print(f"[GIFTS][COUNTS][ERROR] gift_id={gift_id}: {e}")

    return None, None, None


async def get_gift_details_from_response(bot1, gift_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает (emoji, limit_text)
      limit_text = "used / total" если total_count есть
    """
    try:
        gifts_response = await bot1.get_available_gifts()
        gift_list = getattr(gifts_response, "gifts", [])
        print(f"📦 Тип данных gift_list: {type(gift_list)}")
        print(f"📦 Кол-во подарков: {len(gift_list)}")
    except Exception as e:
        print(f"[GIFTS][DETAILS][ERROR] get_available_gifts: {e}")
        return None, None

    for gift in gift_list:
        try:
            current_id = str(getattr(gift, "id", ""))
            if current_id != str(gift_id):
                continue

            emoji = getattr(getattr(gift, "sticker", None), "emoji", "🎁")

            total = getattr(gift, "total_count", None)
            remaining = getattr(gift, "remaining_count", None)

            if total is None or remaining is None:
                return str(emoji), None

            total_i = int(total)
            remaining_i = int(remaining)
            used_i = max(0, total_i - remaining_i)

            used_fmt = "{:,.0f}".format(used_i).replace(",", ".")
            total_fmt = "{:,.0f}".format(total_i).replace(",", ".")
            limit_text = f"{used_fmt} / {total_fmt}"

            return str(emoji), limit_text

        except Exception as e:
            print(f"[GIFTS][DETAILS][ERROR] gift={gift}: {e}")

    return None, None

PREMIUM_ICON_MAP: Dict[str, str] = {
    '😀': '5372954454653933911','😃': '5370601486885591701','😄': '5373330410321223066','😁': '5373329319399529171','😆': '5372881676433105377','🥹': '5371007876691138460','😅': '5373015670822804395','😂': '5370953476635368811','🤣': '5370712413005945913','🥲': '5370959021438146805','☺️': '5371037748188683677','😊': '5370738629486319646','😇': '5370947515220761242','🙃': '5373179691328871991','😉': '5373101475679443553','😌': '5370699111492229743','😍': '5372886001465170842','🥰': '5370900820336319679','😗': '5373292756342938165','😙': '5372828792500788028','😚': '5370967353674701492','😋': '5371057462088570593','😛': '5370823648363943942','😝': '5370564490037303348','😜': '5371087054413241706','🤪': '5370853232098681087','🤨': '5370562939554111732','🧐': '5373153968769735192','😎': '5373141891321699086','🥸': '5370574634750056701','🥳': '5370870691140737817','🙂': '5400065288953679132','😏': '5370976574969486150','😒': '5370763368497944736','🙂': '5400022850381827997','😔': '5370781385885751708','😟': '5370987174948771923','😕': '5373272140499918095','🙁': '5372872665591717013','😣': '5370679238678551249','😖': '5370843963559254781','😫': '5371077231823036079','😩': '5370553005294754329','🥺': '5373230475022179039','😢': '5370881342659631698','😶‍🌫️': '5370547013815376328','😱': '5370810157871667232','😭': '5370646412243510708','😤': '5370650883304462905','😨': '5370664287897393412','😰': '5373122864616577600','😠': '5370752953202252786','😡': '5372811453717813644','😥': '5370603784693094754','😓': '5370846862662179567','🤬': '5373123633415723713','🤯': '5370745797786738962','🤗': '5373192254108211756','🤔': '5370724846936267183','😳': '5372864857341172842','🫣': '5373117556036999296','🤭': '5373044447103687138','🥶': '5372892693024218813','🫢': '5370782936368946402','🫨': '5249119354825487565','😬': '5372815907598899227','🫡': '5372952487558912793','🤫': '5370930189322688800','🙄': '5370669532052461802','😯': '5370964879773539088','🫠': '5373161588041718232','🤥': '5373069598432172355','😦': '5373345399757085790','😧': '5370892118732576453','😶': '5370588928401218156','🫥': '5372913502140766965','😮': '5370824412868122831','😐': '5370771949842602821','🫤': '5370849697340593527','🥱': '5373159114140555980','😴': '5372923973271034075','😑': '5371039809772985021','🤧': '5370880659759831851','🤮': '5372824841130879657','🤢': '5371041051018533122','🥴': '5370571834431380930','🤐': '5372800046284674872','😵‍💫': '5370890542479579293','😵': '5372869745013954798','😮‍💨': '5373111135060892185','😪': '5371009319800150304','🤤': '5370743302410738268','😷': '5370702049249859619','🤒': '5373262021556967911','🤑': '5373303394976929925','🤠': '5373308531757817004','😈': '5370856741086960948','👿': '5373150640170081115','👹': '5372951839018850336','👺': '5372931824471251423','🤡': '5371074117971745503','😸': '5370679174254041760','😺': '5370996619581856274','🎃': '5370610867094166617','🤖': '5372981976804366741','👾': '5370869711888194012','👽': '5371018382181145040','☠️': '5370842086658546991','💀': '5370971163310693562','👻': '5371017798065592581','💩': '5371035398841571673','😹': '5370677443382221953','🙌': '5469645992531862101','👏': '5471921242866981303','😻': '5370597492566006063','😼': '5386828444560530381','👍': '5469770542288478598','😽': '5372993873863776984','🙀': '5370704475906383039','👎': '5472309400536358507','👊': '5470058558500382450','😿': '5386666691797195065','😾': '5370977588581767676','✊': '5472404692975753822','🤛': '5469724332735340531','🫶': '5357107687484038897','🤲': '5471895949804575096','🤜': '5472101816177008629','🫷': '5433871032375060997','👐': '5472221443901103190','🫳': '5357041699606503565','🤏': '5472060215123778885','🤌': '5472234792659458002','👌': '5471984997361523302','🤘': '5470076726212042350','🤟': '5471957105843904125','🫰': '5357461124637794049','✌️': '5469986291380657759','🤞': '5472139590414376346','🫸': '5434103785242768167','🫴': '5357429539448299875','👋': '5472055112702629499','🤙': '5469774158650942877','👈': '5469735272017043817','👉': '5471978009449731768','🫲': '5472370131373923279','🫱': '5472348819746200625','👆': '5469718869536940860','👇': '5470177992950946662','💪': '5471883477219549006','🦾': '5386766919154016047','☝️': '5472105307985419058','✋': '5472354553527541051','🖕': '5470028837326691625','✍️': '5470060791883374114','🤚': '5469904794376217131','🖐': '5472241608772557596','🙏': '5472189549473963781','🫵': '5357423427709838027','🖖': '5471893463018511081','👂': '5472199711366584503','👅': '5470039656349310887','🦷': '5469760204302196866','👄': '5391137757047298749','🫦': '5390999527819844807','💋': '5420273668427096000','💄': '5425119671437237058','🦿': '5415966542078683753','🦵': '5472145530354145694','🦶': '5469873690223059497','🦻': '5472248558029642850','👃': '5471966722275679446','👣': '5188501157072347830','👁': '5424892643760937442','👀': '5424885441100782420','🧠': '5237799019329105246','🗣': '5370765563226236970','👤': '5373012449597335010','👥': '5372926953978341366','🫂': '5370867268051806190','👨‍💻': '5190498849440931467','🧑‍💻': '5190458330719461749','👨‍🏫': '5373039692574893940','👨‍⚕️': '5429363657471434941','👩‍⚕️': '5431602426354344379','👮‍♂️': '5377754411319698237','👮‍♀️': '5370872220149099318','👵': '5190941656274181429','👶': '5379601719703379510','🤶': '5190595636528947694','🤦‍♀️': '5283021507377768251','🤦': '5282722547589196222','🧑‍🎄': '5190748979746317724','🎅': '5190723690978886110','🤦‍♂️': '5282785636363807099','🤷‍♀️': '5190569523127787186','🧛‍♀️': '5190445793709924936','🧛': '5192935590546382362','🤷': '5395517004486551976','🤷‍♂️': '5190748314026385859','🧛‍♂️': '5190548452018233240','🧟‍♀️': '5190533149049757592','💅': '5373334855612375386','💃': '5190799832159100491','🧟': '5190680981824085932','🧟‍♂️': '5190733157086796387','🕺': '5190758974135212829','👠': '5372917273122054051','🤰': '5386381480198938366','🧳': '5375106250449100282','💼': '5359785904535774578','👜': '5380056101473492248','👛': '5472363448404809929','💍': '5402100905883488232','👑': '5467406098367521267','🪖': '5375271950287379933','🎓': '5375163339154399459','🎩': '5467480195143310096','👨‍👩‍👧‍👦': '5386539642369614675','🐶': '5283020991981693429','🐱': '5282816560128336499','🐭': '5283220982838864517','🐹': '5282938489954902480','🦊': '5283051451889756068','🐰': '5413628907343588244','🐻': '5282822525837911765','🐼': '5280639613004685879','🐻‍❄️': '5280924618444514633','🐨': '5282989982317814757','🙊': '5467550297599516219','🙉': '5465507121527266133','🙈': '5467370583282950466','🐵': '5465449362807070392','🐸': '5411083752673650595','🐽': '5357546847890055677','🐷': '5357233044694508227','🐮': '5393123749924984737','🦁': '5397972596203462916','🐯': '5364298326025970096','🐔': '5283202076392827429','🐧': '5361541227604878624','🐦': '5332594174527022579','🐤': '5282786130285044165','🐣': '5470113903448956707','🐥': '5470012829983580233','🪿': '5271913686863208405','🦆': '5368684320858843385','🐦‍⬛️': '5271564922633869989','🦉': '5445146051671497117','🐞': '5368487491097601104','🐌': '5368469400695351161','🦋': '5445096582238181549','🐛': '5397991236361527676','🪱': '5233206123036682153','🐝': '5411500325846656872','🦄': '5415696465945173620','🐴': '5339237329292764502','🐺': '5276289730256842699','🦇': '5442769745050871204','🐜': '5472009457200277262','🪰': '5224189032472275894','🪲': '5445397693805373887','🪳': '5460712963067362896','🦟': '5397618806862392535','🦗': '5397617947868930988','🕸': '5445388468215619925','🦂': '5380003148821712039','🐢': '5350813992732338949','🐠': '5397842858126353661','🦀': '5222474515887435551','🦞': '5397772549511717747','🦐': '5361600498153564481','🦑': '5474140796066210842','🐙': '5352815688010441881','🦕': '5461115427272796310','🦖': '5460873384390830669','🦎': '5238108342873762772','🐍': '5409076727341130651','🐟': '5382210409824525356','🐬': '5362063083311214432','🐳': '5431815452437257407','🐋': '5222292529533167322','🦈': '5361632650278744629','🦭': '5420642954010175242','🐅': '5474425672657021493','🐆': '5409152396074952733','🦓': '5339136715388887338','🦍': '5461044878139991881','🐃': '5454199713882449973','🦬': '5341464046497440643','🦘': '5395748653547662674','🦒': '5395848782120233514','🐫': '5436346870567806865','🐪': '5224323379049296560','🦏': '5195097801637243044','🦛': '5247022225374063963','🐘': '5224708023435404637','🦣': '5222463202943575830','🐂': '5427148558153295349','🐄': '5417952788359423425','🐎': '5350774831220532974','🐖': '5201910092215105927','🐏': '5221960120539293842','🐑': '5222303808117306484','🐐': '5222141780476046109','🦌': '5427137412713161135','🐕': '5429363803500338694','🦜': '5449565637443593864','🦚': '5197299191419789230','🦤': '5319003338929366294','🦃': '5438309683506979622','🐓': '5318986601441813952','🐈‍⬛': '5413703918947413540','🐈': '5413492778355140447','🐕‍🦺': '5255982403326846597','🦮': '5244914019201984931','🐩': '5429286305110449868','🦢': '5350817398641404705','🦩': '5413616769766009559','🕊': '5434121252874756456','🐇': '5460999037954042754','🦝': '5460664743469525674','🦡': '5221982978355243461','🦫': '5222285176549156658','🦦': '5235720796323719802','🦥': '5226639796645932042','🐁': '5233312311808108588','🌳': '5449918202718985124','🌲': '5449523005598210324','🎄': '5449857802593901902','🌵': '5449820402018688838','🐲': '5258112758645282249','🐉': '5470088387048266598','🐾': '5188308218551475917','🦔': '5397600806654453370','🐿': '5233608776220681373','🐀': '5325622678101451093','🌴': '5449372007432985754','🪵': '5188239353045868629','🌱': '5449885771420934013','🌿': '5449850741667668411','☘️': '5368544635637475254','🍀': '5395325195542078574','🎍': '5465271641355350028','🪴': '5278428495121248059','🍁': '5281026503658728615','🍄': '5467491306223730835','🌻': '5211226911367257670','🌼': '5370731117588523522','🌸': '5440354006335495210','🌺': '5440748683765227563','🪷': '5208911829505432564','🪻': '5375282786489880721','🥀': '5208923808169222461','🌹': '5440911110838425969','🌷': '5404835520150773707','💐': '5190661263629243818','🌞': '5467597172872584200','🌝': '5467387526928931399','🌛': '5465643984955120548','🌜': '5467894148386265851','🌚': '5465374681915727405','🌕': '5188608638628929611','🌖': '5188452705546281155','🌗': '5188420746694633417','🌘': '5188377234380954537','🌑': '5188497854242495901','✨': '5472164874886846699','🌟': '5458799228719472718','⭐️': '5435957248314579621','💫': '5469741319330996757','🌏': '5397753673130463064','🌍': '5399898266265475100','🌎': '5397575638146110953','🌔': '5188461347020481276','🌓': '5190851612284819957','🌒': '5188666899860298925','⚡️': '5431449001532594346','💥': '5469785308386041323','🔥': '5420315771991497307','🌈': '5427042798878610107','☀️': '5469947168523558652','🌤': '5283075860188898177','🌥': '5283155153875116393','☁️': '5287571024500498635','🌦': '5283097055852503586','🍉': '5305336095863485125','🍌': '5390950002551954897','🍋‍🟩': '5197480146981906157','⛄️': '5470093614023449749','☃️': '5471950641918121951','❄️': '5431895003821513760','🌨': '5282833267551117457','🌩': '5282731554135615450','⛈': '5282939632416206153','🌧': '5283243028905994049','🍓': '5469963154391833732','🍒': '5406759193052995173','🍑': '5375191900686927814','🍆': '5354916382284730411','🥖': '5222351452189509927','🥨': '5389005589252676667','🍳': '5388747006451655179','🥞': '5373004843210251169','🍗': '5470182756069678947','🍖': '5470159421512359552','🫕': '5197351413927128451','🥗': '5264946326491134516','🌮': '5370940699107662298','🥙': '5370689026909018935','🥪': '5388893447656577052','🍕': '5370980663778351052','🍟': '5370962534721395008','🍔': '5372998546788194447','🌭': '5370724786806725431','🦴': '5470173702278622823','🥫': '5471958978449644934','🍣': '5188646425751198926','🍱': '5393575567599607062','🍙': '5188216117272780281','🍘': '5469832166479240291','🍥': '5469759478452722926','🍢': '5373282031809600510','🍡': '5373024050303999039','🍦': '5372799217355987430','🥧': '5372806755023592592','🍯': '5402418909557053333','🍪': '5370783443175086955','🍩': '5373351094883719887','🍿': '5371081166013078244','🍫': '5348308557919970713','🍭': '5424799150912838494','🍮': '5370817227387857270','🎂': '5370999492914976897','🍰': '5390932938646887892','🧁': '5372907046804920585','🥛': '5413704369918978673','🫗': '5411324253662356461','🍼': '5411128690916467494','🫖': '5429279123925130812','☕️': '5359370246190801956','🧃': '5469782971923831839','🥤': '5370775909802449577','🧋': '5474268541278493225','🍶': '5267028002650204185','🍺': '5402227731972771532','🧂': '5429368016863254478','🍽': '5359678839591018693','🍾': '5370900768796711127','🧉': '5411156256016573323','🍹': '5361684086807076580','🍸': '5330136791808746014','🥃': '5330015368788322059','🍷': '5330280024673101519','🥂': '5372923951796198347','🍻': '5264737672684907396','⚽️': '5373101763442255191','🛹': '5413496837099246635','🛼': '5389109381432366393','🏀': '5384088040677319401','🪀': '5429528601395485922','🛷': '5445060431498451052','⛸': '5400004424972129965','🏓': '5269563867305879894','🏸': '5251537923924306335','🏆': '5409008750893734809','🥇': '5280735858926822987','⛳️': '5264710717470158023','🪁': '5233706705769997857','🥈': '5283195573812340110','🥉': '5282750778409233531','🏹': '5228736616859706595','🤿': '5251345466439772001','🏅': '5334644364280866007','🎖': '5332547853304734597','🥊': '5377674666661924559','🎹': '5467398680959023683','🎼': '5229095839334410849','🎤': '5382360961313152917','🎬': '5375464961822695044','🎨': '5431456208487716895','🎭': '5359441070201513074','🎟': '5377599075237502153','🎫': '5418010521309815154','🎗': '5454172415070315962','🏵': '5454388756867986435','🪇': '5467918917462688479','🎮': '5467583879948803288','🚗': '5445085952194124000','🥁': '5465293043177388397','🪘': '5467919926780001747','🚕': '5445015510435502457','🏎': '5190458184690588640','🎷': '5467793203769933478','🎺': '5467522887118257234','🚓': '5444893443169983691','🚑': '5445188473063480079','🪗': '5465250832238803903','🎸': '5465665777619204788','🚂': '5359595190807962128','✈️': '5361600266225326825','🪕': '5467853243117761295','🎻': '5265153614497740567','🛫': '5267341200255363810','🛬': '5237795059369257857','🪈': '5467646199924291236','🗺': '5415803062738504079','🛥': '5359437440954147777','🚤': '5395404390444062636','⛵️': '5188322825735267247','🛶': '5201984627077567357','🚁': '5438101579456602876','🛸': '5319139188744936824','🚀': '5445284980978621387','🛰': '5321304062715517873','🛩': '5384178664487278651','🗿': '5442983582882601962','🗽': '5454219968948229067','🏰': '5429403746696189687','🎡': '5226711870492126219','🎢': '5440551785284510215','🎠': '5224362841208793190','🏖': '5433645645376264953','🏝': '5431751483194351011','🏕': '5359636199155704118','🏠': '5465226866321268133','🏫': '5265002646397285605','🏪': '5267092422864694820','🏨': '5265159812135546996','🏦': '5264895611517300926','🏥': '5264827875588077689','🏤': '5265256642173235585','🏣': '5264716824913671598','🏬': '5265105755677159697','🏢': '5264733042710181045','🏭': '5264746606216904351','🏛': '5359778044745622115','☎️': '5465169893580086142','📺': '5373330964372004748','🎆': '5431783411981228752','🎇': '5431585985219534209','🎙': '5382013970905309819','🧭': '5433825729060018456','📱': '5407025283456835913','📲': '5406809207947142040','⏰': '5413704112220949842','⌛️': '5451646226975955576','💻': '5431376038628171216','⌨️': '5472111548572900003','⏳': '5451732530048802485','💡': '5472146462362048818','🖨': '5386494631112353009','📹': '5375309569905938163','🛢': '5436341901290658109','💸': '5472030678633684592','📞': '5467539229468793355','💣': '5469654973308476699','🔬': '5379679518740978720','🔭': '5372846474881146350','🔫': '5222486447306602688','⛓️‍💥': '5375466233133030264','💈': '5400271640657418526','🪬': '5404451992456156919','⛓️': '5318757666800031348','🧱': '5436275698664759373','🧿': '5426900601101374618','🔮': '5361837567463399422','🧰': '5449428597922079323','💎': '5471952986970267163','⚰️': '5433769525117983603','⚔️': '5408935401442267103','🪪': '5422683699130933153','💰': '5375296873982604963','🗡': '5393607290228067750','🧨': '5469913852462242978','🪙': '5379600444098093058','🩺': '5359299744302639114','💊': '5433635625217563352','💉': '5472317878801800869','🦠': '5433656554593196791','🧪': '5411512278740640309','🌡': '5470049770997292425','🧻': '5433689153394973729','🧼': '5472386005573049567','🪥': '5199649509193308558','🪒': '5469909248257317234','🎈': '5472091323571903308','🎁': '5199749070830197566','🛒': '5431499171045581032','🛍': '5373052667671093676','🖼': '5375074927252621134','🪆': '5429629795119944797','🧸': '5397915559037785261','🗝': '5330100898767054648','🔑': '5330115548900501467','🧽': '5188365693803830912','🎏': '5449737629408975897','🎀': '5375152498656961898','🪄': '5260426225599405269','🪅': '5447147987467788070','🎊': '5435933711893797296','🎉': '5436040291507247633','🪭': '5379705640732087225','🎐': '5319290706601204434','🪩': '5375407018418904583','📨': '5406631276042002796','📉': '5361748661640372834','📈': '5373001317042101552','📊': '5431577498364158238','📭': '5352896944496728039','📬': '5350421256627838238','📫': '5350403531297809491','📪': '5350310124349053625','📤': '5433614747381538714','📥': '5433811242135331842','💌': '5472019095106886003','📆': '5431897022456145283','🗳': '5359741159566484212','📁': '5433653135799228968','📂': '5431721976769027887','🗂': '5431736674147114227','📰': '5433982607035474385','📚': '5373098009640836781','📖': '5226512880362332956','🔗': '5375129357373165375','📎': '5377844313575150051','🧡': '5449599833973203438','❤️': '5449505950283078474','🩷': '5434031913260035048','🔐': '5472308992514464048','🔎': '5188311512791393083','🔍': '5188217332748527444','✏️': '5334673106202010226','📝': '5334882760735598374','✂️': '5237808360882977239','🧮': '5472404950673791399','💛': '5449366943666543715','💚': '5449380056201697322','🩵': '5433856365061746058','💙': '5449759615346548186','💜': '5449468596952507859','🖤': '5449692618151695997','🩶': '5433713454319938373','🤍': '5451714942157724312','🤎': '5449727072379346350','💔': '5471954395719539651','💝': '5465263910414195580','💘': '5452140079495518256','💖': '5465540480538254161','💗': '5451745243151997382','💓': '5449455694870748968','💞': '5451609943092239685','💕': '5465511459444235288','❣️': '5471898432295673647','❤️‍🩹': '5470166383654347072','❤️‍🔥': '5449394813709327952','💟': '5436275462441542596','♐️': '5424710210730075565','♑️': '5424710661701642809','⛎': '5424649771950287002','♈️': '5424657219423577765','♒️': '5424638381697018084','♓️': '5425091973193147960','♉️': '5424777671781393596','♊️': '5422582995032746400','❌': '5465665476971471368','💯': '5188208446461188962','♋️': '5424934828929723803','♌️': '5424717464929838278','💢': '5467910507916697142','♨️': '5465432711218863135','♍️': '5425070270723402683','♎️': '5424647753315657842','🔞': '5422542669584800702','❗️': '5467928559664242360','♏️': '5424922309100053218','🛄': '5429116151391070736','🛃': '5343824560523322473','🛂': '5429612430567155314','💤': '5451959871257713464','✅': '5427009714745517609','⁉️': '5467596412663372909','‼️': '5467890025217661107','❔': '5467461928647399673','❓': '5467666648263564704','❕': '5467519850576354798','🛅': '5429337466760864755','🚹': '5429564911048992647','🚺': '5429474729620677471','🚼': '5447506874935030757','🆗': '5363850326577259091','🆙': '5364105043907716258','🆒': '5362038683602002650','🆕': '5361979468887893611','🔄': '5264727218734524899','👁‍🗨': '5228686859663585439','®️': '5228901410459887866','©️': '5229177516727478228','💱': '5471899089425667918','✖️': '5226660202035554522','➗': '5226470789682833538','➖': '5229113891081956317','➕': '5226945370684140473','🎶': '5188705588925702510','🎵': '5188621441926438751','🔝': '5422354988103901774','✔️': '5188216731453103384','☑️': '5454096630372379732','🔔': '5242628160297641831','🔕': '5244807637157029775','📣': '5469903029144657419','💬': '5465300082628763143','💭': '5465143921912846619','🗯': '5465132703458270101','🏳️': '5411285332668720752','🏴': '5411091492204716695','🏴‍☠️': '5386372293263892965','🏁': '5411520005386806155','🚩': '5411175424455613715','🏳️‍🌈': '5269245889402125871','🏳️‍⚧️': '5269534159017096888',
}
# ============================================================
# ✅ CONFIG
# ============================================================
GIFTS_TTL = 12.0
GIFTS_TIMEOUT = 1.8

GIFTS_DEBUG = True
GIFTS_DEBUG_PRINT_IDS_ONLY = False
GIFTS_DEBUG_MAX_ITEMS = 200

SYSTEM_ICON_IDS: Dict[str, Optional[str]] = {
    "back": "5960671702059848143",
    "close": "5226660202035554522",
    "info": None,
}

GIFT_BUTTON_RULES: Dict[str, Any] = {
    "hide_unicode_emoji_when_premium": True,
    "show_separator": True,
    "show_stars_symbol": True,
    "nft_tag_text": "[ NFT ]",
    "styled_when_premium": True,
    "manual_suffix": " ",
}

UI_TEXTS: Dict[str, str] = {
    "back": "Назад к балансу",
    "min_withdraw_prefix": "Мин. вывод сейчас : ",
    "min_withdraw_prefix_info": "Мин. вывод сейчас: ",
    "withdraw_locked": "Вывод временно недоступен",
    "withdraw_wait_limit": "Дождитесь обновления лимита",
    "speed_title": "⚡ Моментальный вывод",
}

SPEED_RULES: Dict[str, Any] = {
    "min_remaining": 50,
    "cb_prefix": "speedwithdrawal",
    "signal": "+",
}

CB_RULES: Dict[str, str] = {
    "noop": "noop",
    "close": "9close_bonus",
}


# ============================================================
# ✅ CACHE / STORES
# ============================================================
_gifts_cache_ts: float = 0.0
_gifts_cache_data: List[Any] = []
_gifts_lock = asyncio.Lock()

_min_price_cache_ts: float = 0.0
_min_price_cache_val: Optional[int] = None
_min_price_lock = asyncio.Lock()
MIN_PRICE_TTL = 12.0

_gift_menu_emoji_overrides_lock = asyncio.Lock()
_gift_menu_emoji_overrides: Dict[str, Dict[str, str]] = LazyGameStore("_gift_menu_emoji_overrides")

_gift_menu_manual_gifts_lock = asyncio.Lock()
_gift_menu_manual_gifts: Dict[str, Dict[str, Any]] = LazyGameStore("_gift_menu_manual_gifts")


# ============================================================
# ✅ NORMALIZERS
# ============================================================
def _normalize_gift_id(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _normalize_custom_emoji_id(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _safe_int(
    x: Any,
    *,
    default: Optional[int] = None,
    clamp_min: Optional[int] = None,
) -> Optional[int]:
    try:
        v = int(x)
        if clamp_min is not None and v < clamp_min:
            v = clamp_min
        return v
    except Exception:
        return default


def _fmt_int1(n: Any) -> str:
    try:
        return f"{int(_safe_int(n, default=0) or 0):,}".replace(",", ".")
    except Exception:
        return "0"


# ============================================================
# ✅ OVERRIDES - хранится в Redis-бэкенде (_gift_menu_emoji_overrides -
# LazyGameStore), как и все остальные постоянные данные бота. Раньше здесь
# был отдельный слой на локальных JSON-файлах (относительный путь), который
# на каждом рестарте/редеплое (эфемерная ФС хостинга) терял данные -
# из-за этого sypheraddgift/sypherupdategift выглядели как "не сохраняются".
# ============================================================
_LEGACY_GIFT_MENU_EMOJI_OVERRIDES_FILE = Path("gift_menu_emoji_overrides.json")
_LEGACY_GIFT_MENU_MANUAL_GIFTS_FILE = Path("gift_menu_manual_gifts.json")
_gift_menu_legacy_migration_lock = asyncio.Lock()
_gift_menu_legacy_migration_done = False


async def _migrate_legacy_gift_menu_json_once() -> None:
    """Разовый перенос старых локальных JSON (до фикса персистентности) в Redis."""
    global _gift_menu_legacy_migration_done

    if _gift_menu_legacy_migration_done:
        return

    async with _gift_menu_legacy_migration_lock:
        if _gift_menu_legacy_migration_done:
            return
        _gift_menu_legacy_migration_done = True

        try:
            if _LEGACY_GIFT_MENU_EMOJI_OVERRIDES_FILE.exists():
                raw = json.loads(_LEGACY_GIFT_MENU_EMOJI_OVERRIDES_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for gift_id, payload in raw.items():
                        gid = _normalize_gift_id(gift_id)
                        if not gid or gid in _gift_menu_emoji_overrides or not isinstance(payload, dict):
                            continue
                        ceid = _normalize_custom_emoji_id(payload.get("custom_emoji_id"))
                        if ceid:
                            _gift_menu_emoji_overrides[gid] = {"custom_emoji_id": ceid}
                # Переименовываем legacy-файл ТОЛЬКО после подтверждённой записи
                # в Redis - иначе при обрыве между миграцией и debounce-сохранением
                # данные терялись бы безвозвратно (флаг миграции не переживает
                # рестарт процесса, а переименованный файл - уже не подхватится).
                if await _flush_gift_store(_gift_menu_emoji_overrides, "_gift_menu_emoji_overrides"):
                    _LEGACY_GIFT_MENU_EMOJI_OVERRIDES_FILE.rename(
                        _LEGACY_GIFT_MENU_EMOJI_OVERRIDES_FILE.with_suffix(".json.migrated")
                    )
                    print("🟩 [GIFT_MENU_EMOJI][MIGRATE] legacy JSON перенесён в Redis")
        except Exception as e:
            print(f"🟥 [GIFT_MENU_EMOJI][MIGRATE][ERROR] {e!r}")

        try:
            if _LEGACY_GIFT_MENU_MANUAL_GIFTS_FILE.exists():
                raw = json.loads(_LEGACY_GIFT_MENU_MANUAL_GIFTS_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for gift_id, payload in raw.items():
                        gid = _normalize_gift_id(gift_id)
                        if not gid or gid in _gift_menu_manual_gifts or not isinstance(payload, dict):
                            continue
                        _gift_menu_manual_gifts[gid] = {
                            "custom_emoji_id": _normalize_custom_emoji_id(payload.get("custom_emoji_id")),
                            "emoji": str(payload.get("emoji") or "🎁"),
                            "price": int(_safe_int(payload.get("price"), default=0, clamp_min=0) or 0),
                            "upgrade_price": int(_safe_int(payload.get("upgrade_price"), default=0, clamp_min=0) or 0),
                            "has_upgrade": int(_safe_int(payload.get("has_upgrade"), default=0, clamp_min=0) or 0),
                        }
                if await _flush_gift_store(_gift_menu_manual_gifts, "_gift_menu_manual_gifts"):
                    _LEGACY_GIFT_MENU_MANUAL_GIFTS_FILE.rename(
                        _LEGACY_GIFT_MENU_MANUAL_GIFTS_FILE.with_suffix(".json.migrated")
                    )
                    print("🟩 [GIFT_MENU_MANUAL][MIGRATE] legacy JSON перенесён в Redis")
        except Exception as e:
            print(f"🟥 [GIFT_MENU_MANUAL][MIGRATE][ERROR] {e!r}")


async def _flush_gift_store(store: Any, store_label: str) -> bool:
    """
    Синхронно дожидается реального сохранения в Redis вместо того, чтобы
    полагаться на фоновый debounce-таймер (WRITE_DEBOUNCE_MS). Без этого
    админ мог получить "успешно добавлено", а изменение могло не успеть
    доехать до Redis (например рестарт/редеплой в течение debounce-окна) -
    внешне это выглядело как "подарок пропал/настройки откатились".
    """
    try:
        await asyncio.to_thread(store.flush)
    except Exception as e:
        print(f"🟥 [GIFT_MENU][FLUSH][ERROR] store={store_label} err={e!r}")
        return False

    if bool(getattr(store, "_dirty_since_boot", False)):
        print(f"🟥 [GIFT_MENU][FLUSH][NOT_PERSISTED] store={store_label} - Redis недоступен или запись не подтвердилась")
        return False

    return True


async def get_gift_menu_emoji_override(gift_id: Any) -> Optional[str]:
    await _migrate_legacy_gift_menu_json_once()
    gid = _normalize_gift_id(gift_id)
    if not gid:
        return None

    try:
        payload = _gift_menu_emoji_overrides.get(gid) or {}
        ceid = _normalize_custom_emoji_id(payload.get("custom_emoji_id"))
        return ceid or None
    except Exception as e:
        print(f"🟥 [GIFT_MENU_EMOJI][GET][ERROR] gift_id={gift_id!r} err={e!r}")
        return None


async def set_gift_menu_emoji_override(gift_id: Any, custom_emoji_id: Any) -> bool:
    await _migrate_legacy_gift_menu_json_once()
    gid = _normalize_gift_id(gift_id)
    ceid = _normalize_custom_emoji_id(custom_emoji_id)

    if not gid or not ceid:
        return False

    try:
        async with _gift_menu_emoji_overrides_lock:
            _gift_menu_emoji_overrides[gid] = {"custom_emoji_id": ceid}
        return await _flush_gift_store(_gift_menu_emoji_overrides, "_gift_menu_emoji_overrides")
    except Exception as e:
        print(f"🟥 [GIFT_MENU_EMOJI][SET][ERROR] gift_id={gift_id!r} err={e!r}")
        return False


async def reset_gift_menu_emoji_override(gift_id: Any) -> bool:
    await _migrate_legacy_gift_menu_json_once()
    gid = _normalize_gift_id(gift_id)
    if not gid:
        return False

    try:
        async with _gift_menu_emoji_overrides_lock:
            if gid in _gift_menu_emoji_overrides:
                del _gift_menu_emoji_overrides[gid]
        return await _flush_gift_store(_gift_menu_emoji_overrides, "_gift_menu_emoji_overrides")
    except Exception as e:
        print(f"🟥 [GIFT_MENU_EMOJI][RESET][ERROR] gift_id={gift_id!r} err={e!r}")
        return False


async def resolve_gift_menu_icon_override(gift_id: Any) -> Optional[str]:
    try:
        return await get_gift_menu_emoji_override(gift_id)
    except Exception:
        return None


# ============================================================
# ✅ MANUAL GIFTS - хранится в Redis-бэкенде (_gift_menu_manual_gifts)
# ============================================================
_DEFAULT_MANUAL_GIFTS = {
    "5922558454332916696": {
        "custom_emoji_id": "5345935030143196497",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5956217000635139069": {
        "custom_emoji_id": "5379850840691476775",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5801108895304779062": {
        "custom_emoji_id": "5224628072619216265",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5800655655995968830": {
        "custom_emoji_id": "5226661632259691727",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5866352046986232958": {
        "custom_emoji_id": "5289761157173775507",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5893356958802511476": {
        "custom_emoji_id": "5317000922096769303",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5935895822435615975": {
        "custom_emoji_id": "5359736160224586485",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5969796561943660080": {
        "custom_emoji_id": "5393309541620291208",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "6026193266406327981": {
        "custom_emoji_id": "5447213743417105726",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
    "5974210632977745012": {
        "custom_emoji_id": "5398092984136802109",
        "emoji": "🎁",
        "price": 60,
        "upgrade_price": 0,
        "has_upgrade": 0,
    },
}

async def get_all_manual_gifts() -> Dict[str, Dict[str, Any]]:
    await _migrate_legacy_gift_menu_json_once()
    try:
        # Если хранилище пустое (нет данных в памяти) — загружаем дефолтные
        if not _gift_menu_manual_gifts:
            _gift_menu_manual_gifts.update(_DEFAULT_MANUAL_GIFTS)
        return dict(_gift_menu_manual_gifts)
    except Exception as e:
        print(f"🟥 [GIFT_MENU_MANUAL][GET_ALL][ERROR] {e!r}")
        return {}


async def add_manual_gift(
    gift_id: Any,
    custom_emoji_id: Any,
    *,
    emoji: str = "🎁",
    price: int = 0,
    upgrade_price: int = 0,
    has_upgrade: int = 0,
) -> bool:
    await _migrate_legacy_gift_menu_json_once()
    gid = _normalize_gift_id(gift_id)
    ceid = _normalize_custom_emoji_id(custom_emoji_id)

    if not gid:
        return False

    try:
        async with _gift_menu_manual_gifts_lock:
            _gift_menu_manual_gifts[gid] = {
                "custom_emoji_id": ceid,
                "emoji": str(emoji or "🎁"),
                "price": int(_safe_int(price, default=0, clamp_min=0) or 0),
                "upgrade_price": int(_safe_int(upgrade_price, default=0, clamp_min=0) or 0),
                "has_upgrade": int(_safe_int(has_upgrade, default=0, clamp_min=0) or 0),
            }

        ok = await _flush_gift_store(_gift_menu_manual_gifts, "_gift_menu_manual_gifts")
        if ok:
            print(
                f"🟩 [GIFT_MENU_MANUAL][ADD] "
                f"gift_id={gid} custom_emoji_id={ceid} price={price}"
            )
        return ok
    except Exception as e:
        print(f"🟥 [GIFT_MENU_MANUAL][ADD][ERROR] gift_id={gift_id!r} err={e!r}")
        return False


async def remove_manual_gift(gift_id: Any) -> bool:
    await _migrate_legacy_gift_menu_json_once()
    gid = _normalize_gift_id(gift_id)
    if not gid:
        return False

    try:
        async with _gift_menu_manual_gifts_lock:
            if gid in _gift_menu_manual_gifts:
                del _gift_menu_manual_gifts[gid]
        return await _flush_gift_store(_gift_menu_manual_gifts, "_gift_menu_manual_gifts")
    except Exception as e:
        print(f"🟥 [GIFT_MENU_MANUAL][REMOVE][ERROR] gift_id={gift_id!r} err={e!r}")
        return False


# ============================================================
# ✅ CONTROL BUTTONS
# ============================================================
def build_gift_menu_ids_callback() -> str:
    return "giftmenuids:list"


def build_gift_menu_emoji_reset_callback(gift_id: Any) -> str:
    return f"giftmenureset:{_normalize_gift_id(gift_id)}"


def build_gift_menu_delete_callback(gift_id: Any) -> str:
    return f"giftmenudelete:{_normalize_gift_id(gift_id)}"


def build_gift_menu_emoji_reset_row(gift_id: Any) -> List[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="Вернуть базовое эмодзи", callback_data=build_gift_menu_emoji_reset_callback(gift_id))]


def build_gift_menu_delete_row(gift_id: Any) -> List[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="Удалить подарок", callback_data=build_gift_menu_delete_callback(gift_id))]


def build_gift_menu_ids_row() -> List[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="Список идентификаторов", callback_data=build_gift_menu_ids_callback())]


def build_gift_menu_control_kb(gift_id: Any) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            build_gift_menu_delete_row(gift_id),
            build_gift_menu_emoji_reset_row(gift_id),
            build_gift_menu_ids_row(),
        ]
    )


# ============================================================
# ✅ GIFT FETCH
# ============================================================
async def get_available_gifts_fast(bot1) -> List[Any]:
    global _gifts_cache_ts, _gifts_cache_data

    loop = asyncio.get_running_loop()
    now = loop.time()

    if (now - _gifts_cache_ts) <= GIFTS_TTL and _gifts_cache_data:
        return list(_gifts_cache_data)

    async with _gifts_lock:
        now2 = loop.time()

        if (now2 - _gifts_cache_ts) <= GIFTS_TTL and _gifts_cache_data:
            return list(_gifts_cache_data)

        try:
            resp = await asyncio.wait_for(bot1.get_available_gifts(), timeout=GIFTS_TIMEOUT)
            gift_list = list(getattr(resp, "gifts", []) or [])
            _gifts_cache_data = gift_list
            _gifts_cache_ts = now2
            _min_price_cache_val = None
            return list(gift_list)
        except Exception as e:
            print(f"🟥 [GIFTS][FAST][ERROR] {e!r}")
            if _gifts_cache_data:
                return list(_gifts_cache_data)
            return []


async def debug_print_available_gift_ids(bot1) -> List[str]:
    try:
        gifts = await get_available_gifts_fast(bot1)
        return [str(getattr(g, "id", "") or "").strip() for g in gifts if str(getattr(g, "id", "") or "").strip()]
    except Exception:
        return []


# ============================================================
# ✅ INTERNAL MERGE
# ============================================================
def _extract_live_gift_item(gift: Any) -> Optional[Dict[str, Any]]:
    try:
        gift_id = str(getattr(gift, "id", "") or "").strip()
        if not gift_id:
            return None

        emoji = str(getattr(getattr(gift, "sticker", None), "emoji", "🎁") or "🎁")
        star_count = int(_safe_int(getattr(gift, "star_count", 0), default=0, clamp_min=0) or 0)
        upgrade_raw = getattr(gift, "upgrade_star_count", None)
        upgrade_price = int(_safe_int(upgrade_raw, default=0, clamp_min=0) or 0)
        has_upgrade = 1 if upgrade_raw is not None else 0

        return {
            "id": gift_id,
            "emoji": emoji,
            "base_emoji": emoji,
            "price": star_count,
            "upgrade_price": upgrade_price,
            "has_upgrade": has_upgrade,
            "manual_custom_emoji_id": "",
            "is_manual": False,
            "is_available_live": True,
        }
    except Exception as e:
        print(f"🟥 [GIFTS][EXTRACT_LIVE][ERROR] {e!r}")
        return None


def _merge_live_and_manual_gifts(
    live_gifts: List[Any],
    manual_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    live_by_id: Dict[str, Dict[str, Any]] = {}

    for g in (live_gifts or []):
        item = _extract_live_gift_item(g)
        if item and item.get("id"):
            live_by_id[str(item["id"])] = item

    merged: List[Dict[str, Any]] = []

    # 1) Ручные подарки - ВСЕГДА первыми
    for gid, payload in (manual_map or {}).items():
        live_item = live_by_id.get(str(gid))

        if live_item:
            live_item = dict(live_item)
            live_item["manual_custom_emoji_id"] = _normalize_custom_emoji_id(payload.get("custom_emoji_id"))
            live_item["is_manual"] = True
            live_item["is_available_live"] = True
            merged.append(live_item)
        else:
            merged.append({
                "id": str(gid),
                "emoji": str(payload.get("emoji") or "🎁"),
                "base_emoji": str(payload.get("emoji") or "🎁"),
                "price": int(_safe_int(payload.get("price"), default=0, clamp_min=0) or 0),
                "upgrade_price": int(_safe_int(payload.get("upgrade_price"), default=0, clamp_min=0) or 0),
                "has_upgrade": int(_safe_int(payload.get("has_upgrade"), default=0, clamp_min=0) or 0),
                "manual_custom_emoji_id": _normalize_custom_emoji_id(payload.get("custom_emoji_id")),
                "is_manual": True,
                "is_available_live": False,
            })

    # 2) Потом все остальные живые подарки
    manual_ids = set((manual_map or {}).keys())
    for gid, live_item in live_by_id.items():
        if gid in manual_ids:
            continue
        merged.append(dict(live_item))

    return merged


# ============================================================
# ✅ BUTTON FACTORY
# ============================================================
def _get_premium_icon_id(unicode_emoji: Optional[str]) -> Optional[str]:
    try:
        e = str(unicode_emoji or "").strip()
        if not e:
            return None
        return PREMIUM_ICON_MAP.get(e)
    except Exception:
        return None


def _extract_leading_emoji(text: str) -> Tuple[Optional[str], str]:
    try:
        s = str(text or "").lstrip()
        if not s:
            return None, ""

        if " | " in s:
            first, rest = s.split(" | ", 1)
            first = first.strip()
            if first:
                return first, " | " + rest
            return None, s

        parts = s.split(" ", 1)
        if len(parts) == 2:
            return parts[0].strip(), " " + parts[1]

        return None, s
    except Exception:
        return None, str(text or "")


def _mk_btn(
    *,
    text: str,
    callback_data: str,
    emoji_for_icon: Optional[str] = None,
    force_icon_id: Optional[str] = None,
    prefer_styled: bool = True,
    hide_unicode_if_premium: bool = False,
) -> InlineKeyboardButton:
    icon_id = force_icon_id or (_get_premium_icon_id(emoji_for_icon) if emoji_for_icon else None)

    final_text = str(text or "")
    if icon_id and hide_unicode_if_premium:
        leading_emoji, rest = _extract_leading_emoji(final_text)
        if leading_emoji and emoji_for_icon and leading_emoji == str(emoji_for_icon):
            final_text = rest.lstrip()
            if final_text.startswith("|"):
                final_text = final_text[1:].lstrip()

    if icon_id:
        if prefer_styled:
            return InlineKeyboardButton(
                text=final_text,
                callback_data=str(callback_data),
                style="default",
                icon_custom_emoji_id=str(icon_id),
            )
        return InlineKeyboardButton(
            text=final_text,
            callback_data=str(callback_data),
            icon_custom_emoji_id=str(icon_id),
        )

    return InlineKeyboardButton(text=final_text, callback_data=str(callback_data))


def _mk_switch_inline_btn(
    *,
    text: str,
    switch_inline_query_current_chat: str,
    emoji_for_icon: Optional[str] = None,
    force_icon_id: Optional[str] = None,
    prefer_styled: bool = True,
    hide_unicode_if_premium: bool = False,
) -> InlineKeyboardButton:
    icon_id = force_icon_id or (_get_premium_icon_id(emoji_for_icon) if emoji_for_icon else None)

    final_text = str(text or "")
    if icon_id and hide_unicode_if_premium:
        leading_emoji, rest = _extract_leading_emoji(final_text)
        if leading_emoji and emoji_for_icon and leading_emoji == str(emoji_for_icon):
            final_text = rest.lstrip()
            if final_text.startswith("|"):
                final_text = final_text[1:].lstrip()

    if icon_id:
        if prefer_styled:
            return InlineKeyboardButton(
                text=final_text,
                switch_inline_query_current_chat=str(switch_inline_query_current_chat),
                style="default",
                icon_custom_emoji_id=str(icon_id),
            )
        return InlineKeyboardButton(
            text=final_text,
            switch_inline_query_current_chat=str(switch_inline_query_current_chat),
            icon_custom_emoji_id=str(icon_id),
        )

    return InlineKeyboardButton(text=final_text, switch_inline_query_current_chat=str(switch_inline_query_current_chat))


def _mk_back_row(back_callback: Optional[str]) -> List[InlineKeyboardButton]:
    if back_callback:
        return [_mk_btn(text=UI_TEXTS["back"], callback_data=str(back_callback), force_icon_id=SYSTEM_ICON_IDS.get("back"), prefer_styled=True)]
    return [_mk_btn(text=" ", callback_data=CB_RULES["close"], force_icon_id=SYSTEM_ICON_IDS.get("close"), prefer_styled=True)]


def _mk_info_row(text: str, *, emoji_for_icon: Optional[str] = None) -> List[InlineKeyboardButton]:
    return [_mk_btn(text=text, callback_data=CB_RULES["noop"], emoji_for_icon=emoji_for_icon, prefer_styled=True, hide_unicode_if_premium=False)]


def _mk_donate_row() -> List[InlineKeyboardButton]:
    return [_mk_switch_inline_btn(
        text="Пополнить баланс",
        switch_inline_query_current_chat="донат 100",
        force_icon_id="6028338546736107668",
        prefer_styled=True,
    )]


# ============================================================
# ✅ MIN PRICE
# ============================================================
async def get_min_withdraw_amount_from_gifts(bot1) -> int:
    global _min_price_cache_ts, _min_price_cache_val

    loop = asyncio.get_running_loop()
    now = loop.time()

    if (now - _min_price_cache_ts) <= MIN_PRICE_TTL and _min_price_cache_val is not None:
        return int(_min_price_cache_val or 0)

    async with _min_price_lock:
        now2 = loop.time()

        if (now2 - _min_price_cache_ts) <= MIN_PRICE_TTL and _min_price_cache_val is not None:
            return int(_min_price_cache_val or 0)

        try:
            live_gifts = await get_available_gifts_fast(bot1)
            manual_map = await get_all_manual_gifts()
            merged = _merge_live_and_manual_gifts(live_gifts, manual_map)

            prices = []
            for item in merged:
                p = int(_safe_int(item.get("price"), default=0, clamp_min=0) or 0)
                if p > 0:
                    prices.append(p)

            min_p = min(prices) if prices else 0
            _min_price_cache_val = int(min_p)
            _min_price_cache_ts = now2
            return int(_min_price_cache_val or 0)

        except Exception as e:
            print(f"🟥 [GIFTS][MIN][ERROR] {e!r}")
            if _min_price_cache_val is not None:
                return int(_min_price_cache_val or 0)
            return 0


# ============================================================
# ✅ SANITIZER
# ============================================================
def sanitize_remove_speed_buttons(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    try:
        if not kb or not getattr(kb, "inline_keyboard", None):
            return kb

        new_rows = []
        for row in kb.inline_keyboard:
            new_row = []
            for btn in row:
                cd = getattr(btn, "callback_data", None)
                if isinstance(cd, str) and cd.startswith(str(SPEED_RULES["cb_prefix"])):
                    continue
                new_row.append(btn)
            if new_row:
                new_rows.append(new_row)

        kb.inline_keyboard = new_rows
        return kb
    except Exception:
        return kb


# ============================================================
# ✅ MAIN GENERATOR
# ============================================================
async def generate_gift_keyboard(
    bot1,
    *,
    remaining: Optional[int] = None,
    speed_allowed: bool = False,
    owner_id: int = 0,
    back_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    rem = _safe_int(remaining, default=None, clamp_min=0)

    live_gifts = await get_available_gifts_fast(bot1)
    manual_map = await get_all_manual_gifts()
    merged_gifts = _merge_live_and_manual_gifts(live_gifts, manual_map)

    min_price = int(await get_min_withdraw_amount_from_gifts(bot1) or 0)

    if min_price <= 0 and not merged_gifts:
        rows: List[List[InlineKeyboardButton]] = []
        rows.append(_mk_donate_row())
        rows.append(_mk_back_row(back_callback))
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # Остаток меньше самого дешёвого подарка — не «повысьте/донат»,
    # а ожидание обновления лимита (таймер ставит refresh_withdraw_quota).
    if isinstance(rem, int) and min_price > 0 and rem < min_price:
        rows: List[List[InlineKeyboardButton]] = []
        rows.append(_mk_info_row(UI_TEXTS["withdraw_locked"], emoji_for_icon="❤️"))
        rows.append(_mk_info_row(UI_TEXTS["withdraw_wait_limit"], emoji_for_icon="🧘‍♂️"))
        rows.append(_mk_back_row(back_callback))
        return InlineKeyboardMarkup(inline_keyboard=rows)

    return await process_gifts_list(
        merged_gifts,
        remaining=rem,
        speed_allowed=bool(speed_allowed),
        owner_id=int(owner_id or 0),
        back_callback=back_callback,
    )


# ============================================================
# ✅ PROCESS LIST
# ============================================================
async def process_gifts_list(
    gift_data: List[Dict[str, Any]],
    *,
    remaining: Optional[int] = None,
    speed_allowed: bool = False,
    owner_id: int = 0,
    back_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    rem = _safe_int(remaining, default=None, clamp_min=0)
    back_signal = "+" if back_callback else "-"

    keyboard_buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for gift in (gift_data or []):
        try:
            gift_id = str(gift.get("id") or "").strip()
            if not gift_id:
                continue

            base_emoji = str(gift.get("base_emoji") or gift.get("emoji") or "🎁")
            price = int(_safe_int(gift.get("price"), default=0, clamp_min=0) or 0)
            upgrade_price = int(_safe_int(gift.get("upgrade_price"), default=0, clamp_min=0) or 0)
            has_upgrade = bool(gift.get("has_upgrade", False))
            is_manual = bool(gift.get("is_manual", False))
            is_available_live = bool(gift.get("is_available_live", False))

            if isinstance(rem, int) and price > 0 and price > rem:
                continue

            formatted_price = _fmt_int1(price) if price > 0 else "-"
            sep = " | " if bool(GIFT_BUTTON_RULES.get("show_separator", True)) else " "
            stars = " ⭐️" if bool(GIFT_BUTTON_RULES.get("show_stars_symbol", True)) and price > 0 else ""
            nft_text = f" {GIFT_BUTTON_RULES.get('nft_tag_text', '[ NFT ]')}" if has_upgrade else ""

            suffix = ""
            if is_manual:
                suffix = GIFT_BUTTON_RULES.get("manual_suffix" , " ")

            text = f"{base_emoji}{sep}{formatted_price}{stars}{nft_text}{suffix}"

            # ✅ И live, и manual подарки идут по одной и той же callback-схеме
            cd = f"sts:g:{gift_id}:{price}:{upgrade_price}:0:{back_signal}:{int(owner_id or 0)}"

            manual_custom_emoji_id = _normalize_custom_emoji_id(gift.get("manual_custom_emoji_id"))
            gift_override_icon_id = await resolve_gift_menu_icon_override(gift_id)
            icon_id = manual_custom_emoji_id or gift_override_icon_id or _get_premium_icon_id(base_emoji)

            btn = _mk_btn(
                text=text,
                callback_data=cd,
                emoji_for_icon=base_emoji,
                force_icon_id=icon_id,
                prefer_styled=True,
                hide_unicode_if_premium=True,
            )

            row.append(btn)

            if len(row) == 2:
                keyboard_buttons.append(row)
                row = []

        except Exception as e:
            print(f"🧨 [GIFTS][ERROR] build button gift={gift!r} err={e!r}")

    if row:
        keyboard_buttons.append(row)

    min_need = int(SPEED_RULES.get("min_remaining", 50) or 50)
    if bool(speed_allowed) and isinstance(rem, int) and rem >= min_need:
        winf = _fmt_int1(rem)
        keyboard_buttons.append([
            _mk_btn(
                text=f"{UI_TEXTS['speed_title']} ({winf})",
                callback_data=f"{SPEED_RULES['cb_prefix']}:{int(rem)}:{str(SPEED_RULES.get('signal', '+'))}",
                emoji_for_icon="⚡",
                prefer_styled=True,
                hide_unicode_if_premium=True,
            )
        ])

    keyboard_buttons.append(_mk_donate_row())
    keyboard_buttons.append(_mk_back_row(back_callback))

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    if not speed_allowed:
        kb = sanitize_remove_speed_buttons(kb)

    return kb

