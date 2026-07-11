import random



from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types import Message, ContentType
import uuid
import time
from bot.funcs.help import wordhelp,brak,ffunc,other,gamehelp,textstore,textglobhelp,textzabhelp,clanss

from bot.design.inlinetictactoe import *
from bot.funcs.func import *
from bot.design.inlinetictac2 import *
from bot.design.schahinline import *
from bot.design.inlinememory import *
from bot.design.inmine import *
from bot.design.inorel import *
from bot.design.induel import *

from aiogram.enums import ParseMode, ChatType  # Импортируем ParseMode из aiogram.enums
from main import rps_games,_format_hms,_pair_seconds_left,_pair_seconds_left,_words_extract_payload_b64_safe,_words_force_close,_try_soft_lock,WORDS_CB_CLOSED
user_info_dict = LazyGameStore("user_info_dict")





















async def parse_amount_async(amount_str: str) -> int:
    """
    Асинхронно преобразует строку с числом в целое число, удаляя разделители.
    Поддерживаются форматы: 1.000, 1,000, 1 000, 1000.
    """
    # Удаляем пробелы, запятые и точки
    cleaned_str = amount_str.replace(",", "").replace(".", "").replace(" ", "")
    try:
        # Преобразуем в число
        return int(cleaned_str)
    except ValueError:
        raise ValueError(f"Неверный формат числа: {amount_str}")


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

inline_temp_whispers: Dict[int, Dict] = {}

async def inline_store_temp_whisper(sender_id: int, receiver_id: int, message: str, ttl: int = 180):
    inline_temp_whispers[receiver_id] = {
        'sender_id': sender_id,
        'message': message
    }

    await asyncio.sleep(ttl)
    inline_temp_whispers.pop(receiver_id, None)
# Command to start the inline mode
user_message_help_inline = {}




# Обработчик для callback-запроса

game_style1 = [
    ("<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>", "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>"),  # Камень и ножницы
    ("<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>", "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>"),  # Камень и бумага
    ("<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>", "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>"),  # Ножницы и камень
    ("<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>", "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji>"),  # Ножницы и бумага
    ("<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>", "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>"),  # Бумага и камень
    ("<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>", "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>"),  # Бумага и ножницы
]


actions_dict = {
    "Поцеловать": {
        "request": "{name} хочет поцеловать вас",
        "accept": "поцеловал(-а)",
        "decline": "{name} отказали в поцелуе",
        "emoji": "💋"
    },
    "Поздравить": {
        "request": "{name} хочет поздравить вас",
        "accept": "поздравил(-а)",
        "decline": "{name} отказали в поздравлениях",
        "emoji": "🎉"
    },
    "Воздушный поцелуй": {
        "request": "{name} хочет послать вам воздушный поцелуй",
        "accept": "послал(-а) воздушный поцелуй",
        "decline": "{name} отказали в воздушном поцелуе",
        "emoji": "💌"
    },
    "Подмигнуть": {
        "request": "{name} хочет подмигнуть вам",
        "accept": "подмигнул(-а)",
        "decline": "{name} отказали в подмигивании",
        "emoji": "😉"
    },
    "Обнять": {
        "request": "{name} хочет обнять вас",
        "accept": "обнял(-а)",
        "decline": "{name} отказали в обьятиях",
        "emoji": "💕"
    },
    "Кусь": {
        "request": "{name} хочет вас куснуть",
        "accept": "куснул(-а)",
        "decline": "{name} отказали в укусе",
        "emoji": "🐾"
    },
    "Чмок": {
        "request": "{name} хочет чмокнуть вас",
        "accept": "чмокнул(-а)",
        "decline": "{name} отказали в чмоке",
        "emoji": "💋"
    },
    "Пошалить": {
        "request": "{name} хочет пошалить с вами",
        "accept": "пошалил(-а)",
        "decline": "{name} отказали в шалости",
        "emoji": "😜"
    },
    "Пожать руку": {
        "request": "{name} хочет пожать вам руку",
        "accept": "пожал(-а) руку",
        "decline": "{name} отказали в рукопожатии",
        "emoji": "🤝"
    },
    "Накормить": {
        "request": "{name} хочет накормить вас",
        "accept": "накормил(-а)",
        "decline": "{name} отказали в кормлении",
        "emoji": "🍽️"
    },
    "Покормить": {
        "request": "{name} хочет покормить вас",
        "accept": "покормил(-а)",
        "decline": "{name} отказали в кормлении",
        "emoji": "🍽️"
    },
    "Приласкать": {
        "request": "{name} хочет приласкать вас",
        "accept": "приласкал(-а)",
        "decline": "{name} отказали в ласке",
        "emoji": "💖"
    },
    "Обрадовать": {
        "request": "{name} хочет обрадовать вас",
        "accept": "обрадовал(-а)",
        "decline": "{name} отказали в радости",
        "emoji": "😊"
    },
    "Смешить": {
        "request": "{name} хочет вас рассмешить",
        "accept": "рассмешил(-а)",
        "decline": "{name} не смог рассмешить вас",
        "emoji": "😂"
    },
    "Помочь": {
        "request": "{name} хочет вам помочь",
        "accept": "помог(-ла)",
        "decline": "{name} отказали в помощи",
        "emoji": "🤝"
    },
    "Пожалеть": {
        "request": "{name} хочет вас пожалеть",
        "accept": "пожалел(-а)",
        "decline": "{name} не пожалели вас",
        "emoji": "💔"
    },
    "Похвалить": {
        "request": "{name} хочет похвалить вас",
        "accept": "похвалил(-а)",
        "decline": "{name} отказали в похвале",
        "emoji": "👏"
    },
    "Извиниться": {
        "request": "{name} хочет извиниться перед вами",
        "accept": "извинился(-ась) перед",
        "decline": "{name} откакали извинятся ",
        "emoji": "🙏"
    },
    "Флиртовать": {
        "request": "{name} хочет флиртовать с вами",
        "accept": "флиртовал(-а)",
        "decline": "{name} отказали в флирте",
        "emoji": "😘"
    },
    "Принести чай": {
        "request": "{name} хочет принести вам чай",
        "accept": "принес чай",
        "decline": "{name} отказали в принесении чая",
        "emoji": "🍵"
    },
    "Поплакать": {
        "request": "{name} хочет поплакать с вами",
        "accept": "поплакал(-а)",
        "decline": "{name} не смог поплакать с вами",
        "emoji": "😢"
    },
    "Похлопать": {
        "request": "{name} хочет похлопать вам по плечу",
        "accept": "похлопал(-а)",
        "decline": "{name} отказали в похлопывании",
        "emoji": "👏"
    },
    "Трахнуть": {
        "request": "{name} хочет трахнуть вас",
        "accept": "трахнул(-а)",
        "decline": "{name} не дали (",
        "emoji": "🍓"
    },
    "Убить": {
        "request": "{name} хочет убить вас",
        "accept": "убил(-а)",
        "decline": "{name} отказали в убийстве 😂",
        "emoji": "🔫"
    },
    "Минет": {
        "request": "{name} хочет сделать вам минет",
        "accept": "сделал(-а) минет",
        "decline": "{name} отказали",
        "emoji": "🔞"
    },
    "Оттрахать": {
        "request": "{name} хочет оттрахать вас",
        "accept": "трахнул(-а)",
        "decline": "{name} отказали ",
        "emoji": "🍓"
    },
    "Вдуть": {
        "request": "{name} хочет вдуть вам",
        "accept": "вдул(-а)",
        "decline": "{name} отказали",
        "emoji": "🍓"
    },
    "Отлизать": {
        "request": "{name} хочет отлизать вам",
        "accept": "отлизал(-а)",
        "decline": "{name} отказали",
        "emoji": "🍓"
    },
    "Изнасиловать": {
        "request": "{name} хочет изнасиловать вас",
        "accept": "изнасиловал(-а)",
        "decline": "{name} отказали в изнасиловании 😌",
        "emoji": "🍓"
    },
    "Раздеть": {
        "request": "{name} хочет раздеть вас",
        "accept": "раздел(-а)",
        "decline": "{name} отказали",
        "emoji": "🔞"
    },
    "Куни": {
        "request": "{name} хочет сделать вам куни",
        "accept": "сделал(-а) куни",
        "decline": "{name} отказали в куни",
        "emoji": "🔞"
    },
    "Заняться сексом": {
        "request": "{name} хочет заняться сексом с вами",
        "accept": "Занялся(-ась) сексом с",
        "decline": "{name} отказали в сексе",
        "emoji": "🍓"
    },
    "Потрогать грудь": {
        "request": "{name} хочет потрогать вашу грудь",
        "accept": "потрогал(-а) грудь",
        "decline": "{name} не дали потрогать грудь 🥹",
        "emoji": "🔞"
    },
    "Закусать": {
        "request": "{name} хочет закусать вас",
        "accept": "закусал(-а)",
        "decline": "{name} отказали в кусании ",
        "emoji": "🐾"
    },
    "Расстрелять": {
        "request": "{name} хочет расстрелять вас",
        "accept": "расстрелял(-а)",
        "decline": "{name} отказали в расстреле 😩",
        "emoji": "🔥"
    },
    "Прижать за талию": {
        "request": "{name} хочет прижать вас за талию",
        "accept": "прижал(-а) за талию",
        "decline": "{name} отказали в прижимании за талию 😩",
        "emoji": "👫🫦"
    },



    "Уебать": {
        "request": "{name} хочет уебать вас",
        "accept": "уебал(-а)",
        "decline": "{name} отказали в уебании 😩",
        "emoji": "✊✨"
    },
    "Выебать": {
        "request": "{name} хочет выебать вас",
        "accept": "выебал(-а)",
        "decline": "{name} отказали в выебывании, ха-ха 😩",
        "emoji": "👉👌"
    },
    "Погладить": {
        "request": "{name} хочет погладить",
        "accept": "погладил(-а)",
        "decline": "{name} отказали в поглаживании 😩",
        "emoji": "🫦"
    },
    "Дать автограф": {
        "request": "{name} хочет дать вам автограф",
        "accept": "дал(-а) автограф",
        "decline": "{name} отказали автограф 😩",
        "emoji": "📜 ✍️"
    },
    "Стукнуть": {
        "request": "{name} хочет стукнуть вас",
        "accept": "стукнул(-а)",
        "decline": "{name} отказали в стуканье 😩",
        "emoji": "👊💥"
    },
    "Задушить": {
        "request": "{name} хочет задушить вас",
        "accept": "задушил(-а)",
        "decline": "{name} отказали в удушении 😩",
        "emoji": "😵"
    },
    "Утопить": {
        "request": "{name} хочет утопить вас",
        "accept": "утопил(-а)",
        "decline": "{name} отказали в утоплении 😩",
        "emoji": "💦☠️"
    },
    "Засосать": {
        "request": "{name} хочет засосать вас",
        "accept": "засосал(-а)",
        "decline": "{name} отказали в засасывании 😩",
        "emoji": "😘🌷"
    },
    "Помурчать": {
        "request": "{name} хочет помурчать вам",
        "accept": "помурчал(-а)",
        "decline": "{name} отказали в мурчании 😩",
        "emoji": "💕"
    },
    "Отшлепать": {
        "request": "{name} хочет отшлепать",
        "accept": "отшлепал(-а)",
        "decline": "{name} отказали отшлепывании 😩",
        "emoji": "🫣"
    },
    "Напоить": {
        "request": "{name} хочет напоить вас",
        "accept": "напоил(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🥃"
    },
    "Насрать": {
        "request": "{name} хочет насрать на вас",
        "accept": "насрал(-а) на",
        "decline": "{name} отказали 😩",
        "emoji": "💩"
    },
    "Избить": {
        "request": "{name} хочет избить вас",
        "accept": "избил(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🤬"
    },
    "Зарезать": {
        "request": "{name} хочет зарезать вас",
        "accept": "зарезал(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🔪🩸"
    },
    "Переехать": {
        "request": "{name} хочет переехать вас",
        "accept": "переехал(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "👫🫦"
    },
    "Нассать": {
        "request": "{name} хочет нассать на вас",
        "accept": "нассал(-а) на",
        "decline": "{name} отказали 😩",
        "emoji": "😣"
    },
    "Украсть": {
        "request": "{name} хочет украсть вас",
        "accept": "украл(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🙊"
    },
    "Поймать": {
        "request": "{name} хочет поймать вас",
        "accept": "поймал(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🙊"
    },
    "Поняшиться": {
        "request": "{name} хочет поняшиться с вами",
        "accept": "поняшился(-ась) с",
        "decline": "{name} отказали😩",
        "emoji": "🌷💕"
    },
    "Облить водой": {
        "request": "{name} хочет облить вас водой",
        "accept": "облил(-а) водой",
        "decline": "{name} отказали 😩",
        "emoji": "💦"
    },
    "Cбить машиной": {
        "request": "{name} хочет сбить вас машиной",
        "accept": "сбил(-а) машиной",
        "decline": "{name} отказали 😩",
        "emoji": "🚗"
    },
    "Порезать": {
        "request": "{name} хочет порезать вас",
        "accept": "порезал(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🔪🩸"
    },
    "Засудить": {
        "request": "{name} хочет засудить вас",
        "accept": "засудил(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🤵"
    },
    "Поставить раком": {
        "request": "{name} хочет поставить вас раком",
        "accept": "поставил(-а) раком",
        "decline": "{name} отказали 😩",
        "emoji": "🦞"
    },
    "Нагнуть": {
        "request": "{name} хочет нагнуть вас",
        "accept": "нагнул(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "🥸"
    },
    "Поиграть": {
        "request": "{name} хочет поиграть с вами",
        "accept": "поиграл(-а) с",
        "decline": "{name} отказали 😩",
        "emoji": "👫🫦"
    },
    "Пнуть": {
        "request": "{name} хочет пнуть вас",
        "accept": "пнул(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "💥"
    },
    "Ударить": {
        "request": "{name} хочет ударить вас",
        "accept": "ударил(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "💥"
    },
    "Попросить прощения": {
        "request": "{name} хочет попросить прощения",
        "accept": "попросил(-а) прощения",
        "decline": "{name} отказали 😩",
        "emoji": "🥺"
    },
    "Кастрировать": {
        "request": "{name} хочет кастрировать вас",
        "accept": "кастрировал(-а)",
        "decline": "{name} отказали 😩",
        "emoji": "✂️"
    },
    "Сбить машиной": {
        "request": "{name} хочет сбить вас машиной",
        "accept": "сбил(-а) машиной",
        "decline": "{name} отказали 😩",
        "emoji": "🚗"
    }


}


@dp.inline_query()
async def inline_help_game(inline_query: types.InlineQuery):
    query_text = inline_query.query.strip().lower()
    user_id = inline_query.from_user.id
    print(f"🎩🎩🎩 Получен инлайн-запрос: {query_text}")

    import time

    start = time.perf_counter()
    print("[INLINE] START")




    # Сообщение помощи
    randomwordhelp = random.choice(wordhelp)
    message_text = f'📚'

    help_result = InlineQueryResultArticle(
        id=uuid.uuid4().hex,
        title="Помощь",
        description="📚 Помощь всегда с вами",
        input_message_content=InputTextMessageContent(
            message_text=message_text, parse_mode="HTML"),
        thumb_url="https://i.imgur.com/bXVqrZp.png",
        reply_markup=btn_help_inline
    )

    # Кнопка для запроса баланса
    user_id = inline_query.from_user.id
    balance = await db.get_user_balance(user_id)  # Получаем баланс из базы данных
    first_name = inline_query.from_user.first_name
    username = inline_query.from_user.username

    balance_message = f"💰"

    # Инлайн кнопка для отображения баланса
    balance_button = InlineKeyboardButton(
        text="💰 Посмотреть баланс" , callback_data="show_balance")

    balance_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ balance_button ] ])

    balance_result = InlineQueryResultArticle(
        id=uuid.uuid4().hex , title="Ваш баланс" , description="💰 Ваш текущий баланс и информация" ,
        input_message_content=InputTextMessageContent(
            message_text=balance_message , parse_mode="HTML") , thumb_url="https://i.imgur.com/rVMUqhm.png" ,
        reply_markup=balance_keyboard  # Добавляем кнопку
    )

    # Данные об играх для создания инлайн-результатов
    games = {
        "крестики-нолики": {
            "keywords": ["кн", "крестики нолики", "крестики-нолики","крестикинолики"],
            "title": "Крестики-нолики",
            "description": "🎨 Начать игру в крестики-нолики",
            "message": "*💭 Играем в Крестики-нолики*\n🎨 Нажмите чтобы создать игру.",
            "thumb_url": "https://i.imgur.com/izTmUAC.png",
            "callback_data": "tic_tac_create"
        },
        "шашки": {
            "keywords": ["шашки"],
            "title": "Шашки",
            "description": "♟ Начать игру в шашки",
            "message": "*♟ Играем в Шашки*\n🐾 Нажмите чтобы создать игру.",
            "thumb_url": "https://i.imgur.com/n2ZMNEv.png",
            "callback_data": "checkers_create"
        },
        "камень-ножницы-бумага": {
            "keywords": ["кнб", "камень ножницы бумага", "камень-ножницы-бумага","каменьножницыбумага","бумага камень ножницы","бумага ножницы камень","бумага ножницы камень","ножницы бумага камень","камень бумага ножницы","ножницы камень бумага"],
            "title": "Камень-ножницы-бумага",
            "description": "🪨 Начать игру в камень-ножницы-бумага",
            "message": "*✊ Играем в Камень-ножницы-бумага ✋*\n✌️ Нажмите чтобы создать игру.",
            "thumb_url": "https://i.imgur.com/IpL9qdB.png",
            "callback_data": "rps_create"
        },

        "Найди пару": {
            "keywords": [ "мемори","найди пару","найти пару","память","пара","пары","пару" ] ,
            "title": "Найди пару" , "description": "🚀 Начать игру в мемори" ,
            "message": "*🚀 Играем в Найти пару*\n✨ Нажмите чтобы создать игру." ,
            "thumb_url": "https://i.imgur.com/wpgj0x2.png" , "callback_data": "1tmemory_create"},

        "Мины": {"keywords": [ "мины" ] ,
            "title": "Мины" , "description": "🧨 Начать игру в мины" ,
            "message": "*🧨 Играем в Мины*\n✨ Нажмите чтобы создать игру." ,
            "thumb_url": "https://i.imgur.com/Vw59UIX.png" , "callback_data": "inmine_create"},

        "Дуэль": {"keywords": [ "дуэль" , "дуэли" , "дуели" , "дуель" ] , "title": "Дуэль" ,
            "description": "🦖 Начать игру в дуэль" , "message": "*🔫 Играем в дуэль*\n✨ Нажмите чтобы создать игру." ,
            "thumb_url": "https://i.imgur.com/6cTDXsV.png" , "callback_data": "induel_create"},

        "Орел и решка": {"keywords": [ "орел или решка","орел","Орёл","орел и решка","орёл и решка","решка или орёл","решка или орел","решка","решка и орёл","решка и орел" ] , "title": "Орел или решка" , "description": "🪙 Начать игру в орел или решка" ,
                 "message": "*🪙 Играем в Орел или решка*\n✨ Нажмите чтобы создать игру." ,
                 "thumb_url": "https://i.imgur.com/1pyorwL.png" , "callback_data": "inorel_create"}


    }

    # Функция для создания инлайн-результата игры
    def create_game_result(game):
        button = InlineKeyboardButton(
            text="Создать игру" , callback_data=game [ "callback_data" ])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ button ] ])

        return InlineQueryResultArticle(
            id=uuid.uuid4().hex , title=game [ "title" ] , description=game [ "description" ] ,
            input_message_content=InputTextMessageContent(
                message_text=game [ "message" ] , parse_mode='Markdown') , thumb_url=game [ "thumb_url" ] ,
            reply_markup=keyboard)

    # Логика поиска и отображения результатов
    results = [ ]

    referral_message = (f"🎩")

    # Генерация реферальной ссылки
    referral_link = await get_start_link(inline_query.from_user.id)

    referral_button = InlineKeyboardButton(
        text=f"💰 Получить {ref_coin} кут!" , url=referral_link)

    referral_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ referral_button ] ])

    referral_result = InlineQueryResultArticle(
        id=uuid.uuid4().hex , title="Реферальная ссылка" , description="🎩 Делитесь радостью и наполняйте кошельки вместе!" ,
        input_message_content=InputTextMessageContent(
            message_text=referral_message , parse_mode="HTML") , thumb_url="https://i.imgur.com/xoglgbo.png" ,
        reply_markup=referral_keyboard)

    if await db.is_user_banned(user_id):
        print("пользователь заблокирован в боте")

        banned_result = InlineQueryResultArticle(
            id=uuid.uuid4().hex , title="🚫 Доступ запрещён" , description="💋 Вы были заблокированы в боте" ,
            input_message_content=InputTextMessageContent(
                message_text="🚫 <b>Вы были заблокированы в боте и не можете использовать его функции.</b>" ,
                parse_mode="HTML") , thumb_url="https://i.imgur.com/kfxeqQn.png")

        await bot1.answer_inline_query(inline_query.id , results=[ banned_result ] , cache_time=1 , is_personal=True)
        return

    if (query_text or "").lower().startswith(("выкуп" , "выкупить")):

        bot_username = (await get_bot_username_by_token(TOKEN)) or ""
        bot_username_norm = bot_username.strip().lower()
        preview_url = "https://i.imgur.com/kHVPzjH.png"
        status_emoji = "🎩" if bot_username_norm == "cutegamingbot" else "🐶"

        parts = (query_text or "").strip().split(maxsplit=1)
        amount_raw = parts [ 1 ].strip() if len(parts) >= 2 else ""
        amount_raw_norm = (amount_raw or "").lower().strip()
        bad_templates = {"(сумма)" , "сумма" , "[сумма]" , "{сумма}" , "(кол-во)" , "(кол-во кут)" , "(кол-во звёзд)" ,
                         "(количество)" , "[кол-во]" , "[количество]" , "(amount)" , "amount"}
        no_amount = ((not amount_raw_norm) or (amount_raw_norm in bad_templates) or (
            not any(ch.isdigit() for ch in amount_raw_norm)))

        # Получаем доступные потерянные куты
        try:
            user_home = await db.get_user_home(inline_query.from_user.id)
        except Exception:
            user_home = 0

        if user_home <= 0:
            result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="У вас нет потерянных кут" ,
                description="Вы не теряли куты на ловушках, либо уже всё выкупили" ,
                input_message_content=InputTextMessageContent(
                    "🏚 У вас пока нет потерянных кут, доступных для выкупа." , parse_mode="HTML") ,
                thumb_url=preview_url)
            results.append(result)

        else:
            # Сетка сумм для выкупа (только до доступного лимита)
            amount_steps = [ 5 , 10 , 15 , 25 , 50 , 100 , 200 , 500 , 1000 ]
            amounts = [ s for s in amount_steps if s <= user_home ]
            if user_home not in amounts:
                amounts.append(user_home)

            # Разбиваем на две колонки
            grid = [ ]
            row = [ ]
            for a in amounts:
                row.append(a)
                if len(row) == 2:
                    grid.append(row)
                    row = [ ]
            if row:
                grid.append(row)

            def _build_amounts_kb():
                return InlineKeyboardMarkup(
                    inline_keyboard=[ [ InlineKeyboardButton(
                        text=str(a) , switch_inline_query_current_chat=f"выкуп {a}" , style="default" ,
                        icon_custom_emoji_id="6028338546736107668") for a in r ] for r in grid ])

            base_info = (f"{status_emoji} <b>Выкуп потерянных кут со скидкой 20%</b>\n"
                         f"Доступно для выкупа: {user_home} кут\n"
                         f"<i>(ваши потери на ловушках)</i>")

            if no_amount:
                kb = _build_amounts_kb()
                result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="Выберите сумму выкупа" , description=f"Доступно: {user_home} кут" ,
                    input_message_content=InputTextMessageContent("🎗" , parse_mode="HTML") , reply_markup=kb ,
                    thumb_url=preview_url)
                results.append(result)

            else:
                bet_str = amount_raw.replace("," , "").replace("." , "").replace(" " , "").strip()
                if not bet_str or not bet_str.isdigit():
                    kb = _build_amounts_kb()
                    msg = (f"<b>❌ Сумма должна быть целым числом.</b>\n{base_info}\n"
                           f"<b>Например:</b> <code>выкуп 50</code>")
                    result = InlineQueryResultArticle(
                        id=uuid.uuid4().hex , title="Ошибка суммы" , description="Нужно целое число" ,
                        input_message_content=InputTextMessageContent(msg , parse_mode="HTML") , reply_markup=kb ,
                        thumb_url=preview_url)
                    results.append(result)

                else:
                    bet = int(bet_str)
                    if bet <= 0:
                        kb = _build_amounts_kb()
                        msg = (f"<b>❌ Нельзя выкупить 0 кут.</b>\n{base_info}\n"
                               f"<b>Например:</b> <code>выкуп 10</code>")
                        result = InlineQueryResultArticle(
                            id=uuid.uuid4().hex , title="Нельзя выкупить 0 кут" , description="Минимум 1" ,
                            input_message_content=InputTextMessageContent(msg , parse_mode="HTML") , reply_markup=kb ,
                            thumb_url=preview_url)
                        results.append(result)

                    elif bet > 99999:
                        kb = _build_amounts_kb()
                        msg = (f"💭 <b>Максимальная сумма выкупа - 99.999 кут</b>\n\n{base_info}")
                        result = InlineQueryResultArticle(
                            id=uuid.uuid4().hex , title="Слишком большая сумма" , description="Максимум: 99.999" ,
                            input_message_content=InputTextMessageContent(msg , parse_mode="HTML") , reply_markup=kb ,
                            thumb_url=preview_url)
                        results.append(result)

                    elif bet > user_home:
                        kb = _build_amounts_kb()
                        msg = (f"💭 <b>Недостаточно потерянных кут.</b>\n"
                               f"У вас сейчас можно выкупить не более {user_home} кут.\n"
                               f"Вы запросили: {bet} кут\n\n{base_info}")
                        result = InlineQueryResultArticle(
                            id=uuid.uuid4().hex , title="Недостаточно доступных кут" ,
                            description=f"Доступно: {user_home}, запрос: {bet}" ,
                            input_message_content=InputTextMessageContent(msg , parse_mode="HTML") , reply_markup=kb ,
                            thumb_url=preview_url)
                        results.append(result)

                    else:
                        # Расчёт цены со скидкой 20%
                        multiplier = 0.8
                        stars_price = max(1 , int(bet * multiplier))
                        stars_price_str = str(stars_price)
                        bet_formatted = "{:,.0f}".format(bet).replace("," , ".")

                        nonce = uuid.uuid4().hex [ :10 ]
                        buy_cb = f"buyback_inline:{stars_price_str}:{bet}:{nonce}"

                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[ [ InlineKeyboardButton(
                                text=f"💰 {bet_formatted} кут = {stars_price_str} ⭐️" , callback_data=buy_cb) ] ,
                                [ InlineKeyboardButton(
                                    text="Купить" , callback_data=buy_cb) ] ])

                        result = InlineQueryResultArticle(
                            id=uuid.uuid4().hex , title=f"Выкуп {bet_formatted} кут" ,
                            description=f"Скидка 20%: {bet_formatted} кут = {stars_price_str} ⭐️" ,
                            input_message_content=InputTextMessageContent("🎗" , parse_mode="HTML") , reply_markup=kb ,
                            thumb_url=preview_url)
                        results.append(result)
    if any(query_text.startswith(keyword) for keyword in [ "прижать за талию","поцеловать","поздравить","расстрелять","закусать","потрогать грудь","заняться сексом","куни","раздеть","изнасиловать","отлизать","вдуть","оттрахать","минет","убить","трахнуть","похлопать","поплакать","принести чай","флиртовать","извиниться","похвалить","пожалеть","помочь","смешить","обрадовать","приласкать","воздушный поцелуй","подмигнуть","обнять","кусь","чмок","пошалить","пожать руку","накормить","покормить","кастрировать","попросить прощения","ударить","пнуть","поиграть","нагнуть","поставить раком","засудить","порезать","сбить машиной","облить водой","поняшиться","поймать","украсть","нассать","переехать","зарезать","избить","насрать","напоить","отшлепать","помурчать","засосать","утопить","задушить","стукнуть","дать автограф","погладить","выебать","уебать" ]):
        # Получаем firstname и username пользователя
        firstname = await db.get_firstname_by_user_id(inline_query.from_user.id)
        username = await db.get_username_by_user_id(inline_query.from_user.id)

        action_key = None
        comment = None  # Инициализируем переменную для комментария

        # Приводим query_text к нижнему регистру для поиска
        query_text_lower = query_text.lower()

        # Если есть комментарий после основного слова действия
        for action in actions_dict:
            if query_text_lower.startswith(action.lower()):  # Приводим action к нижнему регистру
                action_key = action
                comment = query_text [ len(action): ].strip()  # Извлекаем комментарий (если есть)
                break

        if action_key:
            action = actions_dict [ action_key ]
            emoji_action = action [ "emoji" ]

            # Сохраняем информацию о пользователе в словарь user_info_dict
            user_info_dict [ inline_query.from_user.id ] = {"firstname": firstname , "username": username ,
                "action_key": action_key , "comment": comment  # Добавляем комментарий в словарь
            }

            # Формируем сообщение с эмодзи и добавляем комментарий, если он есть
            creator_name_link = await create_user_link(inline_query.from_user.id , firstname , username)
            message_text = f"<b>{emoji_action} {action [ 'request' ].format(name=creator_name_link , user=firstname)}</b>"
            if comment:
                message_text += f'\n<i><b>💬 С комментарием "{comment}"</b></i>'  # Добавляем комментарий в текст сообщения

            # Формируем инлайн кнопки для принятия/отказа с передачей только id, action_key, firstname и username
            callback_data_value = f"{inline_query.from_user.id}:{action_key}"
            accept_button = InlineKeyboardButton(
                text="Принять" , callback_data=f"accept_action:{callback_data_value}")

            decline_button = InlineKeyboardButton(
                text="Отказать" , callback_data=f"decline_action:{callback_data_value}")

            action_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ decline_button , accept_button ] ])

            # Создаем объект ответа с изменением описания
            description = f""
            if comment:
                description = f'💬 {action_key} с комментарием "{comment}"'  # Измененное описание

            result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title=f"{emoji_action} {action_key} собеседника" , description=description ,
                input_message_content=InputTextMessageContent(
                    message_text=message_text , parse_mode="HTML" , disable_web_page_preview=True) ,
                reply_markup=action_keyboard)
            results.append(result)


    if query_text.startswith("тестирование"):
        # 1) определяем username бота по TOKEN
        bot_username = (await get_bot_username_by_token(TOKEN)) or ""
        bot_username_norm = bot_username.strip().lower()

        # 2) выбираем эмодзи
        status_emoji = "🎩" if bot_username_norm == "cutegamingbot" else "🐶"

        # 3) время
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        # 4) инлайн-кнопка "now" (с эмодзи)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[ [ InlineKeyboardButton(text=f"{now}" , callback_data="noopppppp") ] ])

        # 5) сообщение (без phrases)
        message = f"{status_emoji}"

        result = InlineQueryResultArticle(
            id=uuid.uuid4().hex , title=f"{status_emoji} Режим тестирования" ,
            description=bot_username or "UnknownBot" , input_message_content=InputTextMessageContent(
                message_text=message , parse_mode="HTML") , reply_markup=kb ,
            thumb_url="https://i.imgur.com/kfxeqQn.png" , )

        results.append(result)

    if (query_text or "").lower().startswith("донат"):

        # 1) определяем username бота по TOKEN
        bot_username = (await get_bot_username_by_token(TOKEN)) or ""
        bot_username_norm = bot_username.strip().lower()

        # превью картинка
        asdqjaisdqj = "https://i.imgur.com/kHVPzjH.png"

        # 2) выбираем эмодзи (оставил как было)
        status_emoji = "🎩" if bot_username_norm == "cutegamingbot" else "🐶"

        # 3) пытаемся взять сумму из текста: "донат 10"
        parts = (query_text or "").strip().split(maxsplit=1)
        amount_raw = parts [ 1 ].strip() if len(parts) >= 2 else ""

        # 4) если пользователь пишет "донат (сумма)" или не указал цифры - считаем, что суммы НЕТ
        amount_raw_norm = (amount_raw or "").lower().strip()
        bad_templates = {"(сумма)" , "сумма" , "[сумма]" , "{сумма}" , "(кол-во)" , "(кол-во кут)" , "(кол-во звёзд)" ,
            "(количество)" , "[кол-во]" , "[количество]" , "(amount)" , "amount"}

        no_amount = ((not amount_raw_norm) or (amount_raw_norm in bad_templates) or (
            not any(ch.isdigit() for ch in amount_raw_norm)))

        # ✅ Кнопки сумм
        donate_amounts_grid = [ [ 10 , 50 ] , [ 100 , 250 ] , [ 500 , 1000 ] , [ 5000 , 10000 ] ]

        def _build_amounts_kb() -> InlineKeyboardMarkup:
            return InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text=str(a) , switch_inline_query_current_chat=f"донат {a}" , style="default" ,
                    icon_custom_emoji_id="6028338546736107668" , ) for a in row ] for row in donate_amounts_grid ])

        # единый базовый текст (чтобы не дублировать)
        base_info = f"{status_emoji} <b>1 ⭐️ = 1 кут</b>"

        # ✅ если суммы нет - показываем выбор
        if no_amount:
            kb = _build_amounts_kb()

            result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="Выберите сумму" , description="1 ⭐️ = 1 кут" ,
                input_message_content=InputTextMessageContent(
                    message_text="🎗" , parse_mode="HTML" , ) , reply_markup=kb , thumb_url=asdqjaisdqj , )
            results.append(result)

        else:
            # чистим сумму: убираем , . пробелы
            bet_amount_str = (amount_raw or "").replace("," , "").replace("." , "").replace(" " , "").strip()

            # ✅ если не число
            if (not bet_amount_str) or (not bet_amount_str.isdigit()):
                kb = _build_amounts_kb()

                message = (f"<b>❌ Сумма должна быть числом.</b>\n"
                           f"{base_info}\n"
                           f"<b>Например :</b> <code>донат 10</code>")

                result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="Ошибка суммы" , description="Нужно целое число" ,
                    input_message_content=InputTextMessageContent(
                        message_text=message , parse_mode="HTML" , ) , reply_markup=kb , thumb_url=asdqjaisdqj , )
                results.append(result)

            else:
                bet_amount = int(bet_amount_str)

                # ✅ НЕЛЬЗЯ купить 0 кут
                if bet_amount <= 0:
                    kb = _build_amounts_kb()

                    message = (f"<b>❌ Нельзя купить 0 кут.</b>\n"
                               f"{base_info}\n"
                               f"<b>Например :</b> <code>донат 10</code>")

                    result = InlineQueryResultArticle(
                        id=uuid.uuid4().hex , title="Нельзя купить 0 кут" , description="Минимум 1" ,
                        input_message_content=InputTextMessageContent(
                            message_text=message , parse_mode="HTML" , ) , reply_markup=kb , thumb_url=asdqjaisdqj , )
                    results.append(result)

                # ✅ максимум
                elif bet_amount > 99999:
                    kb = _build_amounts_kb()

                    message = (f"💭 <b>Максимальная сумма доната - 99.999</b>\n\n"
                               f"{base_info}")

                    result = InlineQueryResultArticle(
                        id=uuid.uuid4().hex , title="Слишком большая сумма" , description="Максимум : 99.999" ,
                        input_message_content=InputTextMessageContent(
                            message_text=message , parse_mode="HTML" , ) , reply_markup=kb , thumb_url=asdqjaisdqj , )
                    results.append(result)

                else:
                    # ✅ multiplier как у тебя
                    multiplier = 1
                    stars_amount_int = int(bet_amount * multiplier)
                    stars_amount_str = str(stars_amount_int)

                    bet_amount_win_formated = "{:,.0f}".format(bet_amount).replace("," , ".")

                    # ✅ ВАЖНО: в inline используем callback_data, чтобы можно было:
                    # - отправить invoice в ЛС
                    # - отредактировать inline-сообщение в чате на "Счёт отправлен"
                    nonce = uuid.uuid4().hex [ :10 ]
                    buy_cb = f"donate_buy:{stars_amount_str}:{nonce}"

                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[ [ InlineKeyboardButton(
                            text=f"💰 {bet_amount_win_formated} кут = {stars_amount_str} ⭐️" , callback_data=buy_cb) ] ,
                            [ InlineKeyboardButton(text="Купить" , callback_data=buy_cb) ] , ])

                    result = InlineQueryResultArticle(
                        id=uuid.uuid4().hex , title=f"Донат на {bet_amount_win_formated} кут" ,
                        description="1 ⭐️ = 1 кут" , input_message_content=InputTextMessageContent(
                            message_text="🎗" , parse_mode="HTML" , ) , reply_markup=kb , thumb_url=asdqjaisdqj , )
                    results.append(result)



    if query_text.startswith(("эмоции" , "эмоция")):
        emotions = emotions = [
    "(＾▽＾)", "(⌒‿⌒)", "(≧◡≦)", "(╥_╥)", "(¬‿¬)", "(งツ)ว", "(ノ・∀・)ノ", "(￣ー￣)", "(~_^)",
    "(✿◠‿◠)", "(ᵔᴥᵔ)", "(^人^)", "(¬_¬)", "(ʘ‿ʘ)", "(ಥ﹏ಥ)", "(・_・ヾ", "(*≧ω≦)", "(^_)〜☆",
    "(¬‿¬ )", "(^▽^)", "｡◕‿◕｡", "(*^‿^*)", "(T_T)", "(#^.^#)", "(ʘ‿ʘ)╯", "(＾◡＾)っ", "(ノωヽ)",
    "(ಥ‿ಥ)", "(ﾉ◕ヮ◕)ﾉ", "( ˘︹˘ )", "(・_・;)", "(^_~)", "(・ω・)", "(⌐■_■)", "(^・ω・^ )",
    "( ˘ω˘ )", "(ಥ_ಥ)", "(ノ・ω・)ノ", "(＠＾◡＾)", "(*≧ω≦)", "(*￣з￣)", "(*≧▽≦)", "(´。＿。｀)"
]

        descriptions = [ "Случайная эмоция дня" , "Выражение внутреннего состояния" , "Эмоциональный код" ,
            "Что на душе - то в сообщении" , "Чувства через символы" , "Настроение одним взглядом" ,
            "Лицо этого момента" , "Эмоция загружена" , "Эмоциональный пакет доставлен" , "Доставлено с чувствами" ,
            "Выражение... чего-то" , "Это... просто эмоция" ]

        for emo in random.sample(emotions , k=min(50 , len(emotions))):
            result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title=emo , description=random.choice(descriptions) ,
                input_message_content=InputTextMessageContent(
                    message_text=f"<b>{emo}</b>" , parse_mode="HTML"))
            results.append(result)

    async def process_transfer_inline(query_text: str , user_id: int , results: list , callback_prefix: str):
        """
        Единый обработчик команд «дать» и «ддать».
        callback_prefix должен быть 'giveaccept_transfer' или 'ddaccept_transfer'.
        """
        current_time = datetime.now()
        try:
            amount_str = query_text.split(" ") [ 1 ]  # Извлекаем сумму
            amount = await parse_amount_async(amount_str)
            current_balance = await db.get_user_balance(user_id)
            win_amount_formatted2 = "{:,.0f}".format(current_balance).replace("," , ".")

            print(f"🏆 Запрос от пользователя {user_id}: текущий баланс = {win_amount_formatted2} кут.")

            # Проверяем лимит на передачу
            give_limit = await db.get_user_give_limit(user_id)
            if give_limit is None:
                print(f"🏆 Лимит на передачу для пользователя {user_id} не установлен.")
                error_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Лимит не установлен" ,
                    description="💰 Лимит на передачу не установлен." , input_message_content=InputTextMessageContent(
                        message_text="⚠️ <b>У вас не установлен лимит на передачу средств.</b>" , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(error_result)
                print("Вывод пользователю: Лимит на передачу не установлен.")
                return

            print(f"🏆 Лимит на передачу для пользователя {user_id} = {give_limit} кут.")
            daily_sum = await db.get_daily_give_sum(user_id)
            print(f"🏆 Сумма отправлений за сегодня для пользователя {user_id} = {daily_sum} кут.")

            # Проверка баланса
            if current_balance < amount:
                give_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {win_amount_formatted2} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств на балансе для передачи" , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(give_result)
                return

            remaining_amount = give_limit - daily_sum

            if amount > remaining_amount:
                remaining_text = f"\n<b>💸 Вы ещё можете отправить : <i>{remaining_amount}</i> кут</b>."
                error_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Превышен лимит" ,
                    description=f"💰 Вы можете передать {remaining_amount} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text=f"⚠️ <b>{remaining_text}</b>" , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(error_result)

            if remaining_amount <= 0:
                user_in_givetime = await db.check_user_in_givetime(user_id)
                if user_in_givetime:
                    last_open_time , data_over = await db.get_give_times(user_id)
                    if last_open_time and data_over:
                        last_open_dt = datetime.strptime(last_open_time , "%Y-%m-%d %H:%M:%S")
                        data_over_dt = datetime.strptime(data_over , "%Y-%m-%d %H:%M:%S")
                        print(
                            f"🏆 Данные времени для пользователя {user_id}: последний доступ {last_open_time}, время сброса лимита {data_over}.")

                        if current_time < data_over_dt:
                            wait_time = int((data_over_dt - current_time).total_seconds())
                            remaining_text = f"\n<b>💸 Вы ещё можете отправить : <i>{remaining_amount}</i> кут</b>." if remaining_amount > 0 else ""
                            time_text = ""

                            hours , remainder = divmod(wait_time , 3600)
                            minutes , seconds = divmod(remainder , 60)

                            if hours > 0:
                                hours_word = get_declension(hours , "час" , "часа" , "часов")
                                time_text += f"{hours} {hours_word}"
                            if minutes > 0:
                                if hours > 0:
                                    time_text += " "
                                minutes_word = get_declension(minutes , "минута" , "минуты" , "минут")
                                time_text += f"{minutes} {minutes_word}"
                            if seconds > 0:
                                if hours > 0 or minutes > 0:
                                    time_text += " "
                                seconds_word = get_declension(seconds , "секунда" , "секунды" , "секунд")
                                time_text += f"{seconds} {seconds_word}"

                            error_result = InlineQueryResultArticle(
                                id=uuid.uuid4().hex , title="⚠️ Лимит сбрасывается" ,
                                description=f"💰 Лимит будет сброшен через\n{time_text.strip()}" ,
                                input_message_content=InputTextMessageContent(
                                    message_text=f"⚠️ <b>Вы использовали весь лимит на передачу.\n🔰 До обнуления лимита</b>\n<b>{time_text.strip()}{remaining_text}</b>" ,
                                    parse_mode="HTML") , thumb_url="https://i.imgur.com/kfxeqQn.png")
                            results.append(error_result)
                            return
                else:
                    error_result = InlineQueryResultArticle(
                        id=uuid.uuid4().hex , title="⚠️ Лимит переведен" ,
                        description=f"💰 Лимит на передачу средств исчерпан на сегодня." ,
                        input_message_content=InputTextMessageContent(
                            message_text=f"⚠️ <b>Вы исчерпали свой лимит на передачу средств.</b>\n<b>Попробуйте позже.</b>" ,
                            parse_mode="HTML") , thumb_url="https://i.imgur.com/kfxeqQn.png")
                    results.append(error_result)
                    return

            if amount <= remaining_amount:
                win_amount_formatted21 = "{:,.0f}".format(amount).replace("," , ".")
                # Собираем callback_data с переданным префиксом
                transfer_button = InlineKeyboardButton(
                    text="Получить" , callback_data=f"{callback_prefix}:{user_id}:{amount}")
                transfer_button1 = InlineKeyboardButton(
                    text=f"{win_amount_formatted21} кут" , callback_data=f"{callback_prefix}:{user_id}:{amount}")
                transfer_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ transfer_button ] , [ transfer_button1 ] ])

                give_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="💰 Передача кут" , description=f"{win_amount_formatted21} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text=f"💰" , parse_mode="HTML") , thumb_url="https://i.imgur.com/kHVPzjH.png" ,
                    reply_markup=transfer_keyboard)
                results.append(give_result)

        except (IndexError , ValueError):
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Некорректная сумма" , description="💰 Введите сумму для перевода." ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Укажите корректную сумму для передачи.</b>" , parse_mode="HTML") ,
                thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)

    if query_text.startswith("дать"):
        await process_transfer_inline(query_text , user_id , results , callback_prefix="giveaccept_transfer")

    if query_text.startswith("ддать"):
        if user_id != 6801702632:
            # Ничего не показываем - пользователь просто не увидит результатов
            return
        await process_transfer_inline(query_text , user_id , results , callback_prefix="ddaccept_transfer")

    if query_text.startswith("дддать"):
        if user_id != 6801702632:
            return
        await process_transfer_inline(query_text , user_id , results , callback_prefix="dddaccept_transfer")
        # Добавляем обработку реферальной ссылки
    if any(
            query_text.startswith(keyword) for keyword in
            [ "кнб" , "камень ножницы бумага" , "камень-ножницы-бумага" , "каменьножницыбумага" ,
              "бумага камень ножницы" , "бумага ножницы камень" , "ножницы бумага камень" , "камень бумага ножницы" ,
              "ножницы камень бумага" ]):
        game_type = "rps"  # Камень-ножницы-бумага
        game_title = "🪨 Камень-ножницы-бумага"
        thumb_url = "https://i.imgur.com/IpL9qdB.png"
        game_icon = "✊"
    elif any(
            query_text.startswith(keyword) for keyword in
            [ "кн" , "крестики нолики" , "крестики-нолики" , "крестикинолики" , "крестики" , "нолики" ]):
        game_type = "tic_tac"  # Крестики-нолики
        game_title = "🎨 Крестики-нолики"
        thumb_url = "https://i.imgur.com/izTmUAC.png"
        game_icon = "💭"
    else:
        game_type = None

    if game_type:
        try:
            query_text = query_text.strip()
            bet_amount = 0

            if query_text [ -1 ].isdigit():
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]
                bet_amount = await parse_amount_async(bet_amount_str)
                query_text = " ".join(parts [ :-1 ])

            current_balance = await db.get_user_balance(user_id)
            win_amount_formatted2 = "{:,.0f}".format(current_balance).replace("," , ".")

            if current_balance >= bet_amount:
                win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""
                message_text = (f"<b>{game_icon} Играем в {game_title}</b>\n"
                                f"🎮 Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>{game_icon} Играем в {game_title}\n💰 Ставка: {win_amount_formatted} кут.</b>\n"
                                                                                          f"🎮 Нажмите, чтобы создать игру.")

                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"{game_type}_create:{user_id}:{bet_amount}")
                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])

                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title=game_title ,
                    description=f"💰 Ставка {win_amount_formatted} кут" if bet_amount > 0 else f"{game_icon} Начать игру" ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") , thumb_url=thumb_url ,
                    reply_markup=start_game_keyboard)
                results.append(game_result)
            else:
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {win_amount_formatted2} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Недостаточно средств для начала игры." , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(game_result)
        except (IndexError , ValueError):
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" ,
                    parse_mode="HTML") , thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)

    if any(query_text.startswith(keyword) for keyword in [ "шашки" ]):
        # Обработка команды "шашки"
        try:
            # Убираем лишние пробелы в начале и конце строки
            query_text = query_text.strip()

            # Проверяем, если последние символы строки являются числом (ставка)
            bet_amount = 0
            if query_text [ -1 ].isdigit():  # Если последний символ - цифра
                # Найдем последнее число в строке (ставку)
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]  # Последнее слово - это ставка
                bet_amount = await parse_amount_async(bet_amount_str)  # Преобразуем строку в число
                query_text = " ".join(parts [ :-1 ])  # Оставляем только команду без ставки
            else:
                # Если ставки нет, оставляем её как 0
                bet_amount = 0

            # Получаем текущий баланс пользователя
            current_balance = await db.get_user_balance(user_id)
            win_amount_formatted2 = "{:,.0f}".format(current_balance).replace("," , ".")

            # Проверяем, достаточно ли средств для игры
            if current_balance >= bet_amount:
                win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""

                # Формируем сообщение с кнопкой для создания игры
                message_text = f"<b>♟ Играем в Шашки</b>\n🐾 Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>♟ Играем в Шашки\n💰 Ставка : {win_amount_formatted} кут.</b>\n🐾 Нажмите, чтобы создать игру."

                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"checkers_create:{user_id}:{bet_amount}")
                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="🎨 Шашки" ,
                    description=f"💰 Ставка {win_amount_formatted} кут" if bet_amount > 0 else "♟Начать игру в шашки" ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/n2ZMNEv.png" , reply_markup=start_game_keyboard)
                results.append(game_result)
            else:
                # Недостаточно средств для игры
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {win_amount_formatted2} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств для начала игры." , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(game_result)

        except (IndexError , ValueError) as e:
            # Если произошла ошибка при обработке ставки или других данных
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" , parse_mode="HTML") ,
                thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)



    if any(
            query_text.startswith(keyword) for keyword in
            [ "мемори" , "найди пару" , "найти пару" , "память" , "пара" , "пары" , "пару" ]):
        # Обработка команды "Найди пару"
        try:
            # Убираем лишние пробелы в начале и конце строки
            query_text = query_text.strip()

            # Проверяем, если последние символы строки являются числом (ставка)
            bet_amount = 0
            if query_text [ -1 ].isdigit():  # Если последний символ - цифра
                # Найдем последнее число в строке (ставку)
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]  # Последнее слово - это ставка
                bet_amount = await parse_amount_async(bet_amount_str)  # Преобразуем строку в число
                query_text = " ".join(parts [ :-1 ])  # Оставляем только команду без ставки
            else:
                # Если ставки нет, оставляем её как 0
                bet_amount = 0

            # Получаем текущий баланс пользователя
            current_balance = await db.get_user_balance(user_id)
            win_amount_formatted2 = "{:,.0f}".format(current_balance).replace("," , ".")

            # Проверяем, достаточно ли средств для игры
            if current_balance >= bet_amount:
                win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""

                # Формируем сообщение с кнопкой для создания игры
                message_text = (
                    f"<b>🚀 Играем в Найди пару</b>\n✨ Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>🚀 Играем в Найди пару\n💰 Ставка: {win_amount_formatted} кут.</b>\n✨ Нажмите, чтобы создать игру.")

                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"1tmemory_create:{user_id}:{bet_amount}")

                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])

                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="🚀 Найди пару" , description=(
                        f"💰 Ставка {win_amount_formatted} кут" if bet_amount > 0 else "🚀 Начать игру в Найди пару") ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/wpgj0x2.png" , reply_markup=start_game_keyboard)
                results.append(game_result)
            else:
                # Недостаточно средств для игры
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {win_amount_formatted2} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств для начала игры." , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(game_result)
        except (IndexError , ValueError) as e:
            # Если произошла ошибка при обработке ставки или других данных
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" , parse_mode="HTML") ,
                thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)

    if any(query_text.startswith(keyword) for keyword in [ "мины" ]):
        # Обработка команды "Мины"
        try:
            query_text = query_text.strip()

            # Проверка на наличие ставки в запросе
            bet_amount = 0
            if query_text [ -1 ].isdigit():  # Если последний символ - цифра
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]  # Последнее слово - это ставка
                bet_amount = await parse_amount_async(bet_amount_str)  # Преобразуем строку в число
                query_text = " ".join(parts [ :-1 ])  # Убираем ставку из команды
            else:
                bet_amount = 0  # Если ставки нет, оставляем 0

            # Получение текущего баланса пользователя
            current_balance = await db.get_user_balance(user_id)
            balance_formatted = "{:,.0f}".format(current_balance).replace("," , ".")

            # Проверка достаточности средств
            if current_balance >= bet_amount:
                bet_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""

                # Формирование текста сообщения
                message_text = (
                    f"<b>🧨 Играем в Мины</b>\n✨ Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>🧨 Играем в Мины\n💰 Ставка: {bet_formatted} кут.</b>\n✨ Нажмите, чтобы создать игру.")

                # Создание кнопки для старта игры
                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"inmine_create:{user_id}:{bet_amount}")

                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])

                # Формирование результата для инлайн-запроса
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="🧨 Мины" ,
                    description=(f"💰 Ставка {bet_formatted} кут" if bet_amount > 0 else "🧨 Начать игру в Мины") ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/Vw59UIX.png" , reply_markup=start_game_keyboard)
                results.append(game_result)
            else:
                # Недостаточно средств для игры
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {balance_formatted} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств для начала игры." , parse_mode=ParseMode.HTML) ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(game_result)
        except (IndexError , ValueError) as e:
            # Обработка ошибок
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" ,
                    parse_mode=ParseMode.HTML) , thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)

    if any(
            query_text.startswith(keyword) for keyword in
            [ "орел или решка" , "орел" , "Орёл" , "орел и решка" , "орёл и решка" , "решка или орёл" ,
              "решка или орел" , "решка" , "решка и орёл" , "решка и орел" ]):
        # Обработка команды "Орел или решка"
        try:
            query_text = query_text.strip()

            # Определение стороны монеты, если указано
            choice = None
            if "орел" in query_text.lower():
                choice = "орел"
            elif "решка" in query_text.lower():
                choice = "решка"

            # Проверка на наличие ставки в запросе
            bet_amount = 0
            if query_text [ -1 ].isdigit():  # Если последний символ - цифра
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]  # Последнее слово - это ставка
                bet_amount = await parse_amount_async(bet_amount_str)  # Преобразуем строку в число
                query_text = " ".join(parts [ :-1 ])  # Убираем ставку из команды
            else:
                bet_amount = 0  # Если ставки нет, оставляем 0

            # Получение текущего баланса пользователя
            current_balance = await db.get_user_balance(user_id)
            balance_formatted = "{:,.0f}".format(current_balance).replace("," , ".")

            # Проверка достаточности средств
            if current_balance >= bet_amount:
                bet_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""

                # Если выбор стороны монеты не указан, назначаем случайным образом
                if not choice:
                    choice = random.choice([ "орел" , "решка" ])

                # Формирование текста сообщения
                message_text = (
                    f"<b>🪙 Играем в Орел или решка</b>\n✨ Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>🪙 Играем в Орел или решка\n💰 Ставка: {bet_formatted} кут.</b>\n✨ Нажмите, чтобы создать игру.")

                # Создание кнопки для старта игры с добавлением выбранной стороны в callback_data
                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"inorel_create:{user_id}:{bet_amount}:{choice}")

                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])

                # Формирование результата для инлайн-запроса
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="🪙 Орел или решка" , description=(
                        f"💰 Ставка {bet_formatted} кут" if bet_amount > 0 else "🪙 Начать игру в Орел или решка") ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") , thumb_url="https://i.imgur.com/E7MJClp.png" ,
                    reply_markup=start_game_keyboard)

                results.append(game_result)
            else:
                # Недостаточно средств для игры
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {balance_formatted} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств для начала игры." , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png")
                results.append(game_result)
        except (IndexError , ValueError) as e:
            # Обработка ошибок
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" , parse_mode="HTML") ,
                thumb_url="https://i.imgur.com/kfxeqQn.png")
            results.append(error_result)
    if any(query_text.startswith(keyword) for keyword in [ "дуэль","дуэли","дуели","дуель" ]):
        # Обработка команды "Дуэль"
        try:
            query_text = query_text.strip()

            # Проверка на наличие ставки в запросе
            bet_amount = 0
            if query_text [ -1 ].isdigit():  # Если последний символ - цифра
                parts = query_text.split()
                bet_amount_str = parts [ -1 ]  # Последнее слово - это ставка
                bet_amount = await parse_amount_async(bet_amount_str)  # Преобразуем строку в число
                query_text = " ".join(parts [ :-1 ])  # Убираем ставку из команды
            else:
                bet_amount = 0  # Если ставки нет, оставляем 0

            # Получение текущего баланса пользователя
            current_balance = await db.get_user_balance(user_id)
            balance_formatted = "{:,.0f}".format(current_balance).replace("," , ".")

            # Проверка достаточности средств
            if current_balance >= bet_amount:
                bet_formatted = "{:,.0f}".format(bet_amount).replace("," , ".") if bet_amount > 0 else ""

                # Формирование текста сообщения
                message_text = (
                    f"<b>🔫 Играем в Дуэль</b>\n✨ Нажмите, чтобы создать игру." if bet_amount == 0 else f"<b>🔫 Играем в Дуэль\n💰 Ставка: {bet_formatted} кут.</b>\n✨ Нажмите, чтобы создать игру.")

                # Создание кнопки для старта игры
                start_game_button = InlineKeyboardButton(
                    text="Создать игру" , callback_data=f"induel_create:{user_id}:{bet_amount}")

                start_game_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ start_game_button ] ])

                # Формирование результата для инлайн-запроса
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="🔫 Дуэль" ,
                    description=(f"💰 Ставка {bet_formatted} кут" if bet_amount > 0 else "🦖 Начать игру в дуэль") ,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text , parse_mode="HTML") ,
                    thumb_url="https://i.imgur.com/6cTDXsV.png" , reply_markup=start_game_keyboard , )
                results.append(game_result)
            else:
                # Недостаточно средств для игры
                game_result = InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                    description=f"💰 На балансе всего {balance_formatted} кут" ,
                    input_message_content=InputTextMessageContent(
                        message_text="💭 Недостаточно средств для начала игры." , parse_mode="HTML" , ) ,
                    thumb_url="https://i.imgur.com/kfxeqQn.png" , )
                results.append(game_result)
        except (IndexError , ValueError) as e:
            # Обработка ошибок
            error_result = InlineQueryResultArticle(
                id=uuid.uuid4().hex , title="⚠️ Непонятный запрос" ,
                description="💰 Перепроверьте правильность написания запроса" ,
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ <b>Произошла ошибка при обработке вашего запроса.</b>" ,
                    parse_mode="HTML" , ) , thumb_url="https://i.imgur.com/kfxeqQn.png" , )
            results.append(error_result)





    elif any(query_text.startswith(keyword) for keyword in [ "шепнуть" , "прошептать" ]):

        try:

            # Очищаем запрос от ключевых слов

            whisper_message = query_text.lower()

            for keyword in [ "шепнуть" , "прошептать" ]:
                whisper_message = whisper_message.replace(keyword , "").strip()

            if not whisper_message:
                raise ValueError("Нет сообщения")

            # Парсим команду на @username или id

            parts = whisper_message.split(" " , 1)  # Разделяем на две части: получатель и сообщение

            if len(parts) < 2:
                raise ValueError("Нет получателя для шепота")

            target = parts [ 0 ].strip()  # Это будет либо @username, либо id

            message = parts [ 1 ].strip()

            # Проверяем, если это @username

            if target.startswith("@"):  # Если это @username

                target = target [ 1: ]  # Убираем @

                print(f"Ищем пользователя по username: {target}")  # Лог для отладки

                receiver_id = await db.get_user_id_by_username(target)  # Получаем ID по username


            # Проверяем, если это числовой ID

            elif target.isdigit():  # Если это числовой ID

                receiver_id = int(target)


            # Если получатель не является ни @username, ни числовым ID

            else:

                raise ValueError("Неверный формат получателя")

            if not receiver_id:
                raise ValueError("Не удалось найти пользователя по данному ID или @username")

            # Создаем кнопку, чтобы получить шепот

            send_button = InlineKeyboardButton(

                text="Прочитать" , callback_data=f"inline_view_message_{receiver_id}"

            )

            whisper_keyboard = InlineKeyboardMarkup(

                inline_keyboard=[ [ send_button ] ]

            )

            # Сохраняем шепот во временное хранилище

            asyncio.create_task(

                inline_store_temp_whisper(

                    sender_id=user_id ,

                    receiver_id=receiver_id ,

                    message=message ,

                )

            )

            receiver_name = await db.get_user_first_name(receiver_id)
            receiver_username = await db.get_username_by_user_id(receiver_id)

            name_link1 = await create_user_link(receiver_id , receiver_name , receiver_username)

            result = InlineQueryResultArticle(

                id=uuid.uuid4().hex ,

                title=f"💬 Отправка скрытого сообщения {receiver_name}" ,

                description="Отправьте скрытое сообщение в любой чат" ,

                input_message_content=InputTextMessageContent(

                    message_text=f"💬 <b>Кто-то отправил скрытое сообщение {name_link1}!</b>" ,

                    parse_mode="HTML", disable_web_page_preview=True

                ) ,

                reply_markup=whisper_keyboard

            )

            results.append(result)


        except ValueError as e:

            error_result = InlineQueryResultArticle(

                id=uuid.uuid4().hex ,

                title="⚠️ Неправильный формат" ,

                description="🕊 Прошептать [@username или id] [сообщение]" ,

                input_message_content=InputTextMessageContent(

                    message_text=f"❌ {str(e)}" , parse_mode="HTML"

                ) ,

                thumb_url="https://i.imgur.com/kfxeqQn.png"

            )

            results.append(error_result)

    elif query_text.startswith(("помощь" , "хелп" , "help")):
        results.append(help_result)

    elif query_text.startswith(("игры" , "играть" , "игрульки" , "игрушки")):
        # Отображаем все игры, если пользователь ищет "игры"
        results = [ create_game_result(game) for game in games.values() ]
    elif query_text.startswith("баланс"):
        results.append(balance_result)



    elif query_text.startswith(("реферальная ссылка","реф","реферальная","реферальный","рефка","инвайт","инвайты","реф ссылка","реф сылка","ссылка","сылка")):
        results.append(referral_result)

    # ───────── «СЛОВА» - инлайн: строгий порядок (ставка?) (слово) (подсказка?) ─────────
    if (inline_query.query or "").strip().lower().startswith(("слово" , "слова")):
        try:
            query_text_raw = (inline_query.query or "").strip()
            query_text = query_text_raw.lower()
            results = [ ]

            user_id = inline_query.from_user.id
            words_creator_id = user_id
            words_creator_name = (await db.get_firstname_by_user_id(words_creator_id)) or (
                    inline_query.from_user.first_name or "Игрок")

            # ── Парсер: (bet?) (word) (hint?), поддерживает и вариант с 🌸 ──
            def _parse_strict(qraw: str):
                """
                Возвращает: bet:int|0, word:str|"" , hint:str|"" , have_bet, have_word, have_hint
                Порядок:
                  1) первое ПОЛОЖИТЕЛЬНОЕ число после «слова» - ставка (опционально)
                  2) следующий НЕчисловой токен - слово (обязательно для создания)
                  3) всё оставшееся - подсказка (опционально)
                Если встретили символ 🌸 - всё после него считаем подсказкой.
                """
                src = (qraw or "").strip()

                # отделим «слово/слова»
                parts_all = src.split()
                if parts_all and parts_all [ 0 ].lower() in ("слово" , "слова"):
                    parts_all = parts_all [ 1: ]

                # если есть явный 🌸 - используем его как разделитель подсказки
                hint_explicit = None
                if "🌸" in src:
                    left , right = src.split("🌸" , 1)
                    hint_explicit = right.strip()

                    left_parts = left.strip().split()
                    if left_parts and left_parts [ 0 ].lower() in ("слово" , "слова"):
                        left_parts = left_parts [ 1: ]
                    tokens = left_parts
                else:
                    tokens = parts_all

                bet = 0
                word = ""
                hint = ""
                have_bet = False
                have_word = False
                have_hint = False

                idx = 0
                # 1) ставка (если первый токен - число > 0)
                if idx < len(tokens):
                    try:
                        v = int(tokens [ idx ])
                        if v > 0:
                            bet = v
                            have_bet = True
                            idx += 1
                    except Exception:
                        pass

                # 2) слово - первый НЕчисловой токен
                while idx < len(tokens):
                    t = tokens [ idx ]
                    try:
                        _ = int(t)
                        idx += 1
                        continue
                    except Exception:
                        word = t
                        have_word = bool(word)
                        idx += 1
                        break

                # 3) подсказка
                if hint_explicit is not None:
                    hint = hint_explicit
                    have_hint = bool(hint)
                else:
                    tail = tokens [ idx: ]
                    if tail:
                        hint = " ".join(tail).strip()
                        have_hint = bool(hint)

                return bet , word , hint , have_bet , have_word , have_hint

            bet_soft , word_soft , hint_soft , have_bet , have_word , have_hint = _parse_strict(query_text_raw)

            # ── Вспомогательные сборщики карточек ──
            def _make_hint_article(title: str , desc: str , buttons: list [ str ]):
                """
                buttons: список строк вида "ТекстКнопки → | слова 10 кот", где часть справа - switch_inline_query_current_chat
                """
                kb_rows = [ [ InlineKeyboardButton(
                    text=btn.split("|" , 1) [ 0 ].strip() ,
                    switch_inline_query_current_chat=btn.split("|" , 1) [ 1 ].strip()) ] for btn in buttons ]

                return InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title=f"🧭 {title}" , description=desc ,
                    input_message_content=InputTextMessageContent(
                        message_text="⭐️ <b>«Слова»</b>\n<blockquote><b>Пожалуйста, добавьте недостающие данные и вернитесь сюда.</b></blockquote>" ,
                        parse_mode="HTML" , disable_web_page_preview=True , ) ,
                    thumb_url="https://i.imgur.com/rVMUqhm.png" ,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows) , )

            async def _make_create_article(words_bet: int , words_word_to_guess: str , words_hint: str):
                game_id = uuid.uuid4().hex
                payload_b64 = words_build_start_payload(
                    game_id=game_id , creator_id=words_creator_id , bet=words_bet , word_to_guess=words_word_to_guess ,
                    hint=words_hint , session_rev=WORDS_SESSION_REV , )
                send_text , _ = await words_build_start_plain_text(
                    creator_id=words_creator_id , creator_name=words_creator_name , bet=words_bet , hint=words_hint ,
                    payload_b64=payload_b64 , )
                words_kb = words_build_cancel_kb(game_id)
                descr = " | ".join(
                    [ f"Ставка: {'нет' if words_bet <= 0 else words_fmt_int(words_bet) + ' кут'}" ,
                        f"Слово: {words_word_to_guess}" ,
                        f"Подсказка: {'есть' if (words_hint or '').strip() else 'нет'}" , ])
                return InlineQueryResultArticle(
                    id=uuid.uuid4().hex , title="⭐️ Создать игру" , description=descr ,
                    input_message_content=InputTextMessageContent(
                        message_text=send_text , parse_mode="HTML" , disable_web_page_preview=True , ) ,
                    thumb_url="https://i.imgur.com/rVMUqhm.png" , reply_markup=words_kb , )

            # ── Логика показа (ровно по твоим правилам) ──

            # 1) только триггер → ТОЛЬКО помощник (ставка ИЛИ слово)
            if query_text in ("слово" , "слова"):
                helper = _make_hint_article(
                    title="Добавьте ставку или слово →" , desc="Укажите ставку (по желанию) или слово для отгадывания" ,
                    buttons=[ "Добавить ставку → | слова 10 " , "Добавить слово  → | слова " ])
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=[ helper ] , cache_time=1 , is_personal=True)
                return

            # 2) введена ставка, но нет слова → помощник «добавить слово»
            if have_bet and not have_word:
                helper = _make_hint_article(
                    title="Добавьте слово →" , desc="Пожалуйста, укажите слово для отгадывания" ,
                    buttons=[ f"Добавить слово → | слова {bet_soft} " ])
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=[ helper ] , cache_time=1 , is_personal=True)
                return

            # 3) есть слово без ставки и без подсказки → просим подсказку (создавать пока НЕ предлагаем)
            if have_word and not have_bet and not have_hint:
                helper = _make_hint_article(
                    title="Добавьте подсказку →" , desc="Например: краткое описание загаданного слова" ,
                    buttons=[ f"Добавить подсказку → | слова {word_soft} " ])
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=[ helper ] , cache_time=1 , is_personal=True)
                return

            # 4) есть слово и ставка, но нет подсказки → помощник + создать игру
            if have_word and have_bet and not have_hint:
                helper = _make_hint_article(
                    title="Добавьте подсказку →" , desc="При желании укажите подсказку" ,
                    buttons=[ f"Добавить подсказку → | слова {bet_soft} {word_soft} " ])
                results.append(helper)

                words_bet = int(bet_soft) if bet_soft > 0 else 0
                if words_bet > 0:
                    current_balance = await db.get_user_balance(words_creator_id)
                    if current_balance < words_bet:
                        results.append(
                            InlineQueryResultArticle(
                                id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                                description=f"На балансе {words_fmt_int(current_balance)} • требуется ≥ {words_fmt_int(words_bet)}" ,
                                input_message_content=InputTextMessageContent(
                                    message_text="<blockquote>💰 <b>Пополните баланс для начала игры.</b></blockquote>" , parse_mode="HTML" ,
                                    disable_web_page_preview=True , ) , thumb_url="https://i.imgur.com/kfxeqQn.png" , ))
                    else:
                        results.append(
                            await _make_create_article(words_bet , word_soft.strip() , (hint_soft or "").strip()))
                else:
                    results.append(await _make_create_article(0 , word_soft.strip() , (hint_soft or "").strip()))
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=results , cache_time=1 , is_personal=True)
                return

            # 5) есть слово без ставки, но уже есть подсказка → ТОЛЬКО «создать игру»
            if have_word and not have_bet and have_hint:
                results.append(await _make_create_article(0 , word_soft.strip() , hint_soft.strip()))
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=results , cache_time=1 , is_personal=True)
                return

            # 6) есть ставка + слово + подсказка → ТОЛЬКО «создать игру»
            if have_word and have_bet and have_hint:
                words_bet = int(bet_soft) if bet_soft > 0 else 0
                if words_bet > 0:
                    current_balance = await db.get_user_balance(words_creator_id)
                    if current_balance < words_bet:
                        results.append(
                            InlineQueryResultArticle(
                                id=uuid.uuid4().hex , title="⚠️ Недостаточно средств" ,
                                description=f"На балансе {words_fmt_int(current_balance)} • требуется ≥ {words_fmt_int(words_bet)}" ,
                                input_message_content=InputTextMessageContent(
                                    message_text="<blockquote>💰 <b>Пополните баланс для начала игры.</b></blockquote>" , parse_mode="HTML" ,
                                    disable_web_page_preview=True , ) , thumb_url="https://i.imgur.com/kfxeqQn.png" , ))
                    else:
                        results.append(await _make_create_article(words_bet , word_soft.strip() , hint_soft.strip()))
                else:
                    results.append(await _make_create_article(0 , word_soft.strip() , hint_soft.strip()))
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(results=results , cache_time=1 , is_personal=True)
                return

            # fallback - мягкий помощник
            helper = _make_hint_article(
                title="Добавьте слово →" , desc="Пожалуйста, укажите слово для отгадывания" ,
                buttons=[ "Добавить слово → | слова " ])
            print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
            await inline_query.answer(results=[ helper ] , cache_time=1 , is_personal=True)

        except Exception as e:
            print(f"[WORDS_INLINE][FATAL] {e!r}")
            try:
                print(f"[INLINE] BEFORE ANSWER: {time.perf_counter() - start:.3f}s")
                await inline_query.answer(
                    results=[ ] , cache_time=1 , is_personal=True , switch_pm_text="Произошла ошибка" ,
                    switch_pm_parameter="start" , )
            except Exception:
                pass
    else:
        # Проверяем каждую игру на совпадение с запросом
      pass

        #for game in games.values():
            #if any(query_text.startswith(keyword) for keyword in game [ "keywords" ]):
                #results.append(create_game_result(game))
                #break  # Останавливаемся при нахождении совпадения



    # ===== ФИНАЛЬНАЯ ОТПРАВКА =====
    if not results:
        results = [ create_game_result(game) for game in games.values() ] + [ help_result ] + [ balance_result ] + [
            referral_result ]

    await bot1.answer_inline_query(inline_query.id , results=results , cache_time=0 , is_personal=True)


transfer_flags = {}
BUTTON_PRESS_DELAY = 2  # Задержка в секундах между нажатием кнопок



@dp.callback_query(lambda c: c.data and c.data.startswith(f"{WORDS_CB_CANCEL}:"))
async def words_cancel_handler(call: types.CallbackQuery):
    try:
        _, game_id = call.data.split(":", 1)
        g = WORDS_STORE.get(game_id)

        # Мягкий фоллбек: если игру не нашли - пробуем ответить аккуратно,
        # но без «ломания» UX.
        if not g:
            try: await call.answer("Игра уже удалена или не найдена.", show_alert=False)
            except Exception: pass
            return

        # Разрешаем отмену только создателю
        if call.from_user.id != int(g.get("creator_id", 0)):
            return await call.answer("Отменить может только создатель.", show_alert=True)

        if g.get("closed"):
            try: await call.answer("Игра уже завершена.", show_alert=False)
            except Exception: pass
            return

        # Закрываем
        g["closed"] = True
        g["winner_id"] = None
        g["payout_done"] = True

        # UI
        try:
            await bot1.edit_message_text(
                "🌿",
                chat_id=g["chat_id"],
                message_id=g["message_id"],
                parse_mode="HTML",
                reply_markup=words_build_closed_kb()
            )
        except Exception as e:
            print(f"[WORDS][CANCEL][UI_ERR] {e!r}")

        try: await call.answer("Готово: игра отменена.", show_alert=False)
        except Exception: pass

    except Exception as e:
        print(f"[WORDS][CANCEL][FATAL] {e!r}")
        try: await call.answer("Ошибка обработки отмены.", show_alert=True)
        except Exception: pass

@dp.callback_query(lambda c: c.data == WORDS_CB_CLOSED)
async def words_closed_handler(call: types.CallbackQuery):
    try:
        await call.answer("Игра завершена.", show_alert=False)
    except Exception:
        pass
@dp.callback_query(lambda c: c.data == WORDS_CB_FINISHED)
async def words_finished_dummy(call: types.CallbackQuery):
    try:
        await call.answer("Эта игра уже завершена.", show_alert=False)
    except Exception:
        pass

@dp.callback_query(lambda c: c.data.startswith('inline_view_message_'))
async def view_message(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    receiver_id = int(callback_query.data.split('_')[-1])

    if user_id == receiver_id:
        whisper_data = inline_temp_whispers.get(receiver_id)

        if whisper_data:
            whisper_message = whisper_data['message']
            inline_temp_whispers.pop(receiver_id, None)  # Удаляем сразу после показа

            await callback_query.answer(whisper_message, show_alert=True)

            #try:
            #    await asyncio.sleep(10)
            #    await callback_query.message.delete()
            #except TelegramAPIError as e:
            #    if 'message to delete not found' in str(e).lower():
            #        print("Сообщение для удаления не найдено.")
            #    else:
            #        print(f"Произошла ошибка при удалении сообщения: {e}")
        else:
            await callback_query.answer("⏰ Срок действия сообщения истёк", show_alert=True)
    else:
        await callback_query.answer("🤷🏽 Это сообщение не для вас")

@dp.callback_query(lambda c: c.data.startswith("accept_action"))
async def accept_action_handler(callback_query: types.CallbackQuery):

    action_data = callback_query.data.split(":")

    recipient_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , recipient_id , first_name , username , db , start_balance)


    if len(action_data) < 3:
        await callback_query.answer("Ошибка: некорректные данные.", show_alert=True)
        return

    creator_user_id = int(action_data[1])
    action_key = action_data[2]

    user_id = callback_query.from_user.id
    firstname = await db.get_firstname_by_user_id(user_id)
    username = await db.get_username_by_user_id(user_id)

    name_link = await create_user_link(user_id, firstname, username)
    creator_info = user_info_dict.get(creator_user_id)

    if creator_info:
        creator_firstname = creator_info["firstname"]
        creator_username = creator_info["username"]
        creator_name_link = await create_user_link(creator_user_id, creator_firstname, creator_username)

        if user_id == creator_user_id:
            await callback_query.answer("😌 Это для собеседника!", show_alert=True)
            return

        action = actions_dict[action_key]
        emoji_action = action["emoji"]

        # Получаем комментарий, если он есть
        comment = creator_info.get("comment", "")

        response_text = f"<b>{emoji_action} {creator_name_link} {action['accept']} {name_link}</b>"
        if comment:
            response_text += f"\n<i><b>💬 С Комментарием : {comment}</b></i>"  # Добавляем комментарий в ответ

        await bot1.edit_message_text(
            response_text, inline_message_id=callback_query.inline_message_id, parse_mode="HTML",
            disable_web_page_preview=True)

        # Удаляем информацию о пользователе из словаря после использования
        del user_info_dict[creator_user_id]

@dp.callback_query(lambda c: c.data.startswith("decline_action"))
async def decline_action_handler(callback_query: types.CallbackQuery):

    action_data = callback_query.data.split(":")

    recipient_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , recipient_id , first_name , username , db , start_balance)


    if len(action_data) < 3:
        await callback_query.answer("Ошибка: некорректные данные.", show_alert=True)
        return

    creator_user_id = int(action_data[1])
    action_key = action_data[2]

    user_id = callback_query.from_user.id
    firstname = await db.get_firstname_by_user_id(user_id)
    username = await db.get_username_by_user_id(user_id)

    name_link = await create_user_link(user_id, firstname, username)
    creator_info = user_info_dict.get(creator_user_id)

    if creator_info:
        creator_firstname = creator_info["firstname"]
        creator_username = creator_info["username"]
        creator_name_link = await create_user_link(creator_user_id, creator_firstname, creator_username)

        if user_id == creator_user_id:
            await callback_query.answer("🙃 Вы не можете отказать себе!", show_alert=True)
            return

        action = actions_dict[action_key]
        emoji_action = action["emoji"]

        # Получаем комментарий, если он есть
        comment = creator_info.get("comment", "")

        response_text = f"<b>{emoji_action} {action['decline'].format(name=name_link, user=name_link)}</b>"
        if comment:
            response_text += f'<i><b>\n💬 С Комментарием : "{comment}"</b></i>'  # Добавляем комментарий в ответ

        await bot1.edit_message_text(
            response_text, inline_message_id=callback_query.inline_message_id, parse_mode="HTML",
            disable_web_page_preview=True)

        # Удаляем информацию о пользователе из словаря после использования
        del user_info_dict[creator_user_id]

claimed_transfers = set()  # set[str]
try:
    BUTTON_PRESS_DELAY
except NameError:
    BUTTON_PRESS_DELAY = 0.0

transfer_locks_runtime: Dict[str, asyncio.Lock] = {}

# Быстрый RAM-кэш для уже принятых переводов в рамках текущего процесса
claimed_transfers: Set[str] = set()
def build_transfer_done_kb(amount: int, recipient_id: int, first_name: str) -> InlineKeyboardMarkup:
    """
    1) Кнопка с суммой (noop)
    2) Кнопка с именем, открывает профиль по tg://user?id=... (работает без username)
    """
    win_amount_fmt = "{:,.0f}".format(int(amount)).replace(",", ".")
    safe_name = (first_name or "Пользователь").strip()

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{win_amount_fmt} кут", callback_data="noop"),
            ],
            [
                InlineKeyboardButton(text=f"{safe_name}", url=f"tg://user?id={int(recipient_id)}"),
            ],
        ]
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("giveaccept_transfer"))
async def accept_transfer_handler(callback_query: types.CallbackQuery):
    """
    Единственная точка принятия перевода.
    Гарантия «только один заберёт»: только самый первый клик проходит.
    После принятия: 🎊 сообщение + кнопки:
      - 💰 сумма
      - 👤 имя (url tg://user?id=... открывает профиль даже без username)
    """

    # --- Разбор callback_data ---
    try:
        # Ожидаем формат: "giveaccept_transfer:sender_id:amount"
        parts = (callback_query.data or "").split(":")
        if len(parts) != 3:
            raise ValueError("Неверное количество сегментов в callback_data")
        _, sender_id_str, amount_str = parts
        sender_id = int(sender_id_str)
        amount = int(amount_str)
    except Exception as e:
        print(f"[accept_transfer] Неверные данные кнопки: {callback_query.data} | err={e}")
        await callback_query.answer("⚠️ Неверные данные кнопки.", show_alert=True)
        return

    recipient_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name or "Пользователь"
    username = callback_query.from_user.username

    # Инлайн-режим → chat_id отсутствует, прокидываем 0 для логов лимитов
    chat_id = 0
    chat_name = "инлайн"

    # --- Обновление базовой инфы о пользователе (как у тебя принято) ---
    try:
        await inline_add_or_update_user_info(
            bot1, recipient_id, first_name, username, db, start_balance
        )
    except Exception as e:
        print(f"[accept_transfer] inline_add_or_update_user_info ошибка: {e}")

    # --- Учёт лимитов перевода (оставлено по твоей логике) ---
    try:
        sender_name = await db.get_firstname_by_user_id(sender_id)
        user_username = await db.get_username_by_id(sender_id)

        await db.add_give_limit(
            sender_id,
            sender_name,
            user_username,
            amount,
            chat_id,
            chat_name,
            time_to_remove_give,
        )

        sumgiveuser1 = await db.get_daily_give_sum(sender_id)   # Сумма переводов за сегодня
        give_limit1 = await db.get_user_give_limit(sender_id)   # Лимит пользователя
        now = datetime.now()

        if sumgiveuser1 >= give_limit1:
            last_open_time, data_over = await db.get_give_times(sender_id)
            if last_open_time is None or data_over is None:
                last_open_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                data_open = now + timedelta(seconds=time_to_remove_give)
                data_open_str = data_open.strftime("%Y-%m-%d %H:%M:%S")
                user_name2 = await db.get_firstname_by_user_id(sender_id)
                user_username2 = await db.get_username_by_id(sender_id)

                await db.add_give_time(
                    chat_id,
                    chat_name,
                    sender_id,
                    user_name2,
                    user_username2,
                    last_open_time_str,
                    data_open_str,
                )
                print(f"[accept_transfer] Проставили окно лимита до {data_open_str} для {sender_id}")
            else:
                print(f"[accept_transfer] Лимит уже активен до {data_over} для {sender_id}")
    except Exception as e:
        print(f"[accept_transfer] Ошибка секции лимитов: {e}")

    # --- Запрет на самопринятие ---
    if sender_id == recipient_id:
        await callback_query.answer("⚠️ Вы не можете принять свою же транзакцию.", show_alert=True)
        return

    # --- Уникальный ключ перевода (одно инлайн-сообщение → один перевод) ---
    inline_id = callback_query.inline_message_id or "no-inline"
    transfer_key = f"{sender_id}:{amount}:{inline_id}"

    # --- Получаем/создаём блокировку для этого перевода (ТОЛЬКО В RAM) ---
    lock = transfer_locks_runtime.get(transfer_key)
    if lock is None:
        new_lock = asyncio.Lock()
        lock = transfer_locks_runtime.setdefault(transfer_key, new_lock)

    # --- Критическая секция: только один «первый» проходит внутрь ---
    async with lock:
        # Если уже кто-то забрал - всё, опоздали
        if transfer_key in claimed_transfers:
            await callback_query.answer("🤷🏽 Этот перевод уже забрали.", show_alert=True)
            return

        # Баланс отправителя - повторная проверка ПЕРЕД самой операцией
        try:
            sender_balance = await db.get_user_balance(sender_id)
        except Exception as e:
            print(f"[accept_transfer] Ошибка чтения баланса отправителя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к балансу отправителя.", show_alert=True)
            return

        if sender_balance is None or sender_balance < amount:
            print(
                f"[accept_transfer] Недостаточно средств у отправителя {sender_id}: "
                f"нужно {amount}, есть {sender_balance}"
            )
            await callback_query.answer("⚠️ Недостаточно средств у отправителя.", show_alert=True)
            return

        # Баланс получателя (для корректного начисления)
        try:
            recipient_balance = await db.get_user_balance(recipient_id)
        except Exception as e:
            print(f"[accept_transfer] Ошибка чтения баланса получателя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к вашему балансу.", show_alert=True)
            return

        # --- Списываем/начисляем (атомарно на уровне логики хэндлера) ---
        try:
            await db.update_user_balance(sender_id, sender_balance - amount)
            await db.update_user_balance(recipient_id, (recipient_balance or 0) + amount)
            await db.touch_balance_last_active(sender_id , set_active_status=True)
            await db.touch_balance_last_active(recipient_id , set_active_status=True)
            # История: у отправителя МИНУС, у получателя ПЛЮС
            try:
                await db.cutehistory_minus(sender_id, amount, "инлайн перевод (отправитель)")
            except Exception as e:
                print(f"[accept_transfer] cutehistory_minus ошибка: {e}")

            try:
                await db.cutehistory_plus(recipient_id, amount, "инлайн перевод (получатель)")
            except Exception as e:
                print(f"[accept_transfer] cutehistory_plus ошибка: {e}")

            # Фиксируем «забрано» ДО обновления UI - гонок больше нет
            claimed_transfers.add(transfer_key)

            # --- 🎊 Обновляем инлайн-сообщение: текст + кнопки (сумма + профиль) ---
            try:
                win_amount_fmt = "{:,.0f}".format(amount).replace(",", ".")
                safe_name = (first_name or "Пользователь").strip()

                final_text = (
                    f"🎊")

                kb_done = build_transfer_done_kb(
                    amount=amount,
                    recipient_id=recipient_id,
                    first_name=safe_name,
                )

                await bot1.edit_message_text(
                    text=final_text,
                    inline_message_id=inline_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb_done,
                )
            except Exception as e:
                # Даже если не смогли обновить UI - деньги уже переведены, повторного приёма не будет
                print(f"[accept_transfer] Не удалось обновить инлайн-сообщение: {e}")

            # Аккуратный ответ первому кликеру
            await callback_query.answer("✅ Перевод принят.", show_alert=False)

        except Exception as e:
            # Ошибка в момент перевода - ничего не помечаем «забрано»
            print(f"[accept_transfer] Ошибка при выполнении перевода: {e}")
            await callback_query.answer("⚠️ Ошибка при обработке перевода.", show_alert=True)
            return
        finally:
            if BUTTON_PRESS_DELAY > 0:
                await asyncio.sleep(BUTTON_PRESS_DELAY)

    # ВНЕ лока: при повторных кликах этот же transfer_key уже в claimed_transfers → «уже забрали».
    # (Опционально) чистим локи, чтобы не рос словарь при огромном количестве переводов.
    if transfer_key in claimed_transfers:
        transfer_locks_runtime.pop(transfer_key, None)



@dp.callback_query(lambda c: c.data and c.data.startswith("ddaccept_transfer"))
async def accept_transfer_handler_dd(callback_query: types.CallbackQuery):
    """
    Единственная точка принятия перевода (ддать).
    Гарантия «только один заберёт» + автоматическое накопление в demo-колонке.
    """

    # --- Разбор callback_data ---
    try:
        # Ожидаем формат: "ddaccept_transfer:sender_id:amount"
        parts = (callback_query.data or "").split(":")
        if len(parts) != 3:
            raise ValueError("Неверное количество сегментов в callback_data")
        _, sender_id_str, amount_str = parts
        sender_id = int(sender_id_str)
        amount = int(amount_str)
    except Exception as e:
        print(f"[accept_transfer_dd] Неверные данные кнопки: {callback_query.data} | err={e}")
        await callback_query.answer("⚠️ Неверные данные кнопки.", show_alert=True)
        return

    recipient_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name or "Пользователь"
    username = callback_query.from_user.username

    # Инлайн-режим → chat_id отсутствует, прокидываем 0 для логов лимитов
    chat_id = 0
    chat_name = "инлайн"

    # --- Обновление базовой инфы о пользователе ---
    try:
        await inline_add_or_update_user_info(
            bot1, recipient_id, first_name, username, db, start_balance
        )
    except Exception as e:
        print(f"[accept_transfer_dd] inline_add_or_update_user_info ошибка: {e}")

    # --- Учёт лимитов перевода (полная копия из оригинального хэндлера) ---
    try:
        sender_name = await db.get_firstname_by_user_id(sender_id)
        user_username = await db.get_username_by_id(sender_id)

        await db.add_give_limit(
            sender_id,
            sender_name,
            user_username,
            amount,
            chat_id,
            chat_name,
            time_to_remove_give,
        )

        sumgiveuser1 = await db.get_daily_give_sum(sender_id)   # Сумма переводов за сегодня
        give_limit1 = await db.get_user_give_limit(sender_id)   # Лимит пользователя
        now = datetime.now()

        if sumgiveuser1 >= give_limit1:
            last_open_time, data_over = await db.get_give_times(sender_id)
            if last_open_time is None or data_over is None:
                last_open_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                data_open = now + timedelta(seconds=time_to_remove_give)
                data_open_str = data_open.strftime("%Y-%m-%d %H:%M:%S")
                user_name2 = await db.get_firstname_by_user_id(sender_id)
                user_username2 = await db.get_username_by_id(sender_id)

                await db.add_give_time(
                    chat_id,
                    chat_name,
                    sender_id,
                    user_name2,
                    user_username2,
                    last_open_time_str,
                    data_open_str,
                )
                print(f"[accept_transfer_dd] Проставили окно лимита до {data_open_str} для {sender_id}")
            else:
                print(f"[accept_transfer_dd] Лимит уже активен до {data_over} для {sender_id}")
    except Exception as e:
        print(f"[accept_transfer_dd] Ошибка секции лимитов: {e}")

    # --- Запрет на самопринятие ---
    if sender_id == recipient_id:
        await callback_query.answer("⚠️ Вы не можете принять свою же транзакцию.", show_alert=True)
        return

    # --- Уникальный ключ перевода ---
    inline_id = callback_query.inline_message_id or "no-inline"
    transfer_key = f"{sender_id}:{amount}:{inline_id}"

    # --- Блокировка в RAM (только один клик проходит) ---
    lock = transfer_locks_runtime.get(transfer_key)
    if lock is None:
        new_lock = asyncio.Lock()
        lock = transfer_locks_runtime.setdefault(transfer_key, new_lock)

    async with lock:
        if transfer_key in claimed_transfers:
            await callback_query.answer("🤷🏽 Этот перевод уже забрали.", show_alert=True)
            return

        # Баланс отправителя
        try:
            sender_balance = await db.get_user_balance(sender_id)
        except Exception as e:
            print(f"[accept_transfer_dd] Ошибка чтения баланса отправителя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к балансу отправителя.", show_alert=True)
            return

        if sender_balance is None or sender_balance < amount:
            print(
                f"[accept_transfer_dd] Недостаточно средств у отправителя {sender_id}: "
                f"нужно {amount}, есть {sender_balance}"
            )
            await callback_query.answer("⚠️ Недостаточно средств у отправителя.", show_alert=True)
            return

        # Баланс получателя
        try:
            recipient_balance = await db.get_user_balance(recipient_id)
        except Exception as e:
            print(f"[accept_transfer_dd] Ошибка чтения баланса получателя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к вашему балансу.", show_alert=True)
            return

        # --- Выполняем перевод ---
        try:
            await db.update_user_balance(sender_id, sender_balance - amount)
            await db.update_user_balance(recipient_id, (recipient_balance or 0) + amount)
            await db.touch_balance_last_active(sender_id, set_active_status=True)
            await db.touch_balance_last_active(recipient_id, set_active_status=True)

            # История
            try:
                await db.cutehistory_minus(sender_id, amount, "инлайн перевод (отправитель)")
            except Exception as e:
                print(f"[accept_transfer_dd] cutehistory_minus ошибка: {e}")

            try:
                await db.cutehistory_plus(recipient_id, amount, "инлайн перевод (получатель)")
            except Exception as e:
                print(f"[accept_transfer_dd] cutehistory_plus ошибка: {e}")

            # ⚡️ ГЛАВНОЕ НОВОВВЕДЕНИЕ: автоматически плюсуем сумму в demo получателю
            try:
                await db.add_demo_amount(recipient_id, amount)
                print(f"[accept_transfer_dd] Добавлено {amount} к demo пользователя {recipient_id}")
            except Exception as e:
                print(f"[accept_transfer_dd] Ошибка при обновлении demo: {e}")

            # Фиксируем «забрано» ДО обновления UI
            claimed_transfers.add(transfer_key)

            # --- Обновляем инлайн‑сообщение ---
            try:
                win_amount_fmt = "{:,.0f}".format(amount).replace(",", ".")
                safe_name = (first_name or "Пользователь").strip()

                final_text = "🎊"

                kb_done = build_transfer_done_kb(
                    amount=amount,
                    recipient_id=recipient_id,
                    first_name=safe_name,
                )

                await bot1.edit_message_text(
                    text=final_text,
                    inline_message_id=inline_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb_done,
                )
            except Exception as e:
                print(f"[accept_transfer_dd] Не удалось обновить инлайн-сообщение: {e}")

            await callback_query.answer("✅ Перевод принят.", show_alert=False)

        except Exception as e:
            print(f"[accept_transfer_dd] Ошибка при выполнении перевода: {e}")
            await callback_query.answer("⚠️ Ошибка при обработке перевода.", show_alert=True)
            return
        finally:
            if BUTTON_PRESS_DELAY > 0:
                await asyncio.sleep(BUTTON_PRESS_DELAY)

    if transfer_key in claimed_transfers:
        transfer_locks_runtime.pop(transfer_key, None)



@dp.callback_query(lambda c: c.data and c.data.startswith("dddaccept_transfer"))
async def accept_transfer_handler_ddd(callback_query: types.CallbackQuery):
    """
    Единственная точка принятия перевода (дддать).
    Гарантия «только один заберёт» + автоматическое накопление в 0demo-колонке.
    """

    # --- Разбор callback_data ---
    try:
        # Ожидаем формат: "dddaccept_transfer:sender_id:amount"
        parts = (callback_query.data or "").split(":")
        if len(parts) != 3:
            raise ValueError("Неверное количество сегментов в callback_data")
        _, sender_id_str, amount_str = parts
        sender_id = int(sender_id_str)
        amount = int(amount_str)
    except Exception as e:
        print(f"[accept_transfer_ddd] Неверные данные кнопки: {callback_query.data} | err={e}")
        await callback_query.answer("⚠️ Неверные данные кнопки.", show_alert=True)
        return

    recipient_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name or "Пользователь"
    username = callback_query.from_user.username

    # Инлайн-режим → chat_id отсутствует, прокидываем 0 для логов лимитов
    chat_id = 0
    chat_name = "инлайн"

    # --- Обновление базовой инфы о пользователе ---
    try:
        await inline_add_or_update_user_info(
            bot1, recipient_id, first_name, username, db, start_balance
        )
    except Exception as e:
        print(f"[accept_transfer_ddd] inline_add_or_update_user_info ошибка: {e}")

    # --- Учёт лимитов перевода (полная копия из оригинального хэндлера) ---
    try:
        sender_name = await db.get_firstname_by_user_id(sender_id)
        user_username = await db.get_username_by_id(sender_id)

        await db.add_give_limit(
            sender_id,
            sender_name,
            user_username,
            amount,
            chat_id,
            chat_name,
            time_to_remove_give,
        )

        sumgiveuser1 = await db.get_daily_give_sum(sender_id)   # Сумма переводов за сегодня
        give_limit1 = await db.get_user_give_limit(sender_id)   # Лимит пользователя
        now = datetime.now()

        if sumgiveuser1 >= give_limit1:
            last_open_time, data_over = await db.get_give_times(sender_id)
            if last_open_time is None or data_over is None:
                last_open_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                data_open = now + timedelta(seconds=time_to_remove_give)
                data_open_str = data_open.strftime("%Y-%m-%d %H:%M:%S")
                user_name2 = await db.get_firstname_by_user_id(sender_id)
                user_username2 = await db.get_username_by_id(sender_id)

                await db.add_give_time(
                    chat_id,
                    chat_name,
                    sender_id,
                    user_name2,
                    user_username2,
                    last_open_time_str,
                    data_open_str,
                )
                print(f"[accept_transfer_ddd] Проставили окно лимита до {data_open_str} для {sender_id}")
            else:
                print(f"[accept_transfer_ddd] Лимит уже активен до {data_over} для {sender_id}")
    except Exception as e:
        print(f"[accept_transfer_ddd] Ошибка секции лимитов: {e}")

    # --- Запрет на самопринятие ---
    if sender_id == recipient_id:
        await callback_query.answer("⚠️ Вы не можете принять свою же транзакцию.", show_alert=True)
        return

    # --- Уникальный ключ перевода ---
    inline_id = callback_query.inline_message_id or "no-inline"
    transfer_key = f"{sender_id}:{amount}:{inline_id}"

    # --- Блокировка в RAM (только один клик проходит) ---
    lock = transfer_locks_runtime.get(transfer_key)
    if lock is None:
        new_lock = asyncio.Lock()
        lock = transfer_locks_runtime.setdefault(transfer_key, new_lock)

    async with lock:
        if transfer_key in claimed_transfers:
            await callback_query.answer("🤷🏽 Этот перевод уже забрали.", show_alert=True)
            return

        # Баланс отправителя
        try:
            sender_balance = await db.get_user_balance(sender_id)
        except Exception as e:
            print(f"[accept_transfer_ddd] Ошибка чтения баланса отправителя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к балансу отправителя.", show_alert=True)
            return

        if sender_balance is None or sender_balance < amount:
            print(
                f"[accept_transfer_ddd] Недостаточно средств у отправителя {sender_id}: "
                f"нужно {amount}, есть {sender_balance}"
            )
            await callback_query.answer("⚠️ Недостаточно средств у отправителя.", show_alert=True)
            return

        # Баланс получателя
        try:
            recipient_balance = await db.get_user_balance(recipient_id)
        except Exception as e:
            print(f"[accept_transfer_ddd] Ошибка чтения баланса получателя: {e}")
            await callback_query.answer("⚠️ Ошибка доступа к вашему балансу.", show_alert=True)
            return

        # --- Выполняем перевод ---
        try:
            await db.update_user_balance(sender_id, sender_balance - amount)
            await db.update_user_balance(recipient_id, (recipient_balance or 0) + amount)
            await db.touch_balance_last_active(sender_id, set_active_status=True)
            await db.touch_balance_last_active(recipient_id, set_active_status=True)

            # История
            try:
                await db.cutehistory_minus(sender_id, amount, "инлайн перевод (отправитель 0demo)")
            except Exception as e:
                print(f"[accept_transfer_ddd] cutehistory_minus ошибка: {e}")

            try:
                await db.cutehistory_plus(recipient_id, amount, "инлайн перевод (получатель 0demo)")
            except Exception as e:
                print(f"[accept_transfer_ddd] cutehistory_plus ошибка: {e}")

            # ⚡️ ГЛАВНОЕ: автоматически плюсуем сумму в 0demo получателю
            try:
                await db.add_0demo_amount(recipient_id, amount)
                print(f"[accept_transfer_ddd] Добавлено {amount} к 0demo пользователя {recipient_id}")
            except Exception as e:
                print(f"[accept_transfer_ddd] Ошибка при обновлении 0demo: {e}")

            # Фиксируем «забрано» ДО обновления UI
            claimed_transfers.add(transfer_key)

            # --- Обновляем инлайн‑сообщение ---
            try:
                win_amount_fmt = "{:,.0f}".format(amount).replace(",", ".")
                safe_name = (first_name or "Пользователь").strip()

                final_text = "🎊"

                kb_done = build_transfer_done_kb(
                    amount=amount,
                    recipient_id=recipient_id,
                    first_name=safe_name,
                )

                await bot1.edit_message_text(
                    text=final_text,
                    inline_message_id=inline_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb_done,
                )
            except Exception as e:
                print(f"[accept_transfer_ddd] Не удалось обновить инлайн-сообщение: {e}")

            await callback_query.answer("✅ Перевод 0demo принят.", show_alert=False)

        except Exception as e:
            print(f"[accept_transfer_ddd] Ошибка при выполнении перевода: {e}")
            await callback_query.answer("⚠️ Ошибка при обработке перевода.", show_alert=True)
            return
        finally:
            if BUTTON_PRESS_DELAY > 0:
                await asyncio.sleep(BUTTON_PRESS_DELAY)

    if transfer_key in claimed_transfers:
        transfer_locks_runtime.pop(transfer_key, None)

@dp.callback_query(lambda c: c.data == "show_balance")
async def show_balance_handler(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id

    # Извлекаем и очищаем имя пользователя от специальных символов
    first_name = re.sub(r'[<>/{}"]', '', callback_query.from_user.first_name)

    # Получаем username пользователя, если он есть
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1, user_id, first_name, username,db, start_balance)
    balance = await db.get_user_balance(user_id)  # Получаем баланс из базы данных

    # Формируем ссылку на пользователя
    name_link111 = await create_user_link(user_id, first_name, username)

    # Форматируем баланс


    ajsskdaasd = random.choice(sksokdoskd)
    win_amount_formatted = "{:,.0f}".format(balance).replace(",", ".")

    # Формируем сообщение о балансе с условием для username
    if username:
        balance_message = (f"<b>🎩 {name_link111}\n"
                           f"🪪 <code>@{username}</code>\n💲 <code>{user_id}</code>\n💰 Ваш баланс ~ {win_amount_formatted} кут</b>")
    else:
        balance_message = (f"<b>🎩 {name_link111}\n"
                           f"💲 <code>{user_id}</code>\n💰 Ваш баланс ~ {win_amount_formatted} кут</b>")

    # Создаем клавиатуру для редактируемого сообщения
    button = InlineKeyboardButton(
        text=f"{ajsskdaasd}" , callback_data="show_balance")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ button ] ])

    # Редактируем текущее сообщение
    try:
        await bot1.edit_message_text(
            text=balance_message , inline_message_id=callback_query.inline_message_id , reply_markup=keyboard ,
            parse_mode="HTML" , disable_web_page_preview=True)
    except TelegramAPIError as e:
        if 'message is not modified' in str(e).lower():
            # Игнорируем ошибку, если сообщение не было измен
            # ено
            print('1241242141241241')
            print(f"Сообщение не было изменено.")
        else:
            # Обработка других ошибок Telegram API
            print(f"Произошла ошибка при обновлении сообщения: {e}")

        pass











@dp.callback_query(lambda c: c.data.startswith('rps_create'))
async def inline_knb_create_game_callback(callback_query: types.CallbackQuery):

    creator_id = callback_query.from_user.id

    # Генерация уникального game_id для каждой игры
    game_id = str(uuid.uuid4())
    game_style = random.choice(game_style1)  # Выбираем случайный стиль для игры
    user_id = callback_query.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    data_parts = callback_query.data.split(":")
    bet_amount = int(data_parts [ 2 ]) if len(data_parts) > 2 else 0  # Ставка передается как 3-й параметр
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте")
        return
    # Если ставка больше 0, проверяем, достаточно ли у пользователя средств
    if bet_amount > 0:
        user_balance = await db.get_user_balance(user_id)
        if user_balance < bet_amount:
            # Если средств недостаточно, отправляем сообщение и выходим из функции
            await callback_query.answer("💭 Недостаточно средств для игры с такой ставкой." , show_alert=True)
            return
    # Создание новой игры с сохранением стиля
    rps_games[game_id] = {
        'game_id': game_id,
        'creator': creator_id,
        'creator_username' : callback_query.from_user.username,# Идентификатор создателя игры
        "participants": [creator_id],
        "choices": {},
        'opponent': None,  # Противник ещё не присоединился
        'style': game_style,  # Сохраняем стиль игры
        'creator_name': callback_query.from_user.first_name,  # Имя создателя
        'opponent_id' : None,
        'opponent_name': None,
        'opponent_username' : None,# Имя противника (пока нет)
        'bet_amount': bet_amount  # Сохраняем ставку в словарь игры
    }

    # Кнопка для присоединения к игре
    btn_join = InlineKeyboardButton(
        text="Присоединиться" , callback_data=f"rps_join:{creator_id}:{game_id}")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ btn_join ] ])
    win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".")
    bet_message = f"<tg-emoji emoji-id='5195369389599265575'>💰</tg-emoji> Ставка : {win_amount_formatted} кут\n" if bet_amount > 0 else ""
    # Отправка сообщения с возможностью присоединиться
    if "inline_message_id" not in rps_games [ game_id ]:
        rps_games [ game_id ] [ "inline_message_id" ] = callback_query.inline_message_id
    inline_message_id = rps_games [ game_id ] [ "inline_message_id" ]
    await bot1.edit_message_text(
        f"<b><tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Играем в Камень-Ножницы-Бумага</b>\n"
        f"<b>{bet_message}</b>"
        f"<b>{game_style[0]} {callback_query.from_user.first_name}</b>",
        inline_message_id=inline_message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback_query.answer("❕ Игра создана!")
    rps_games.save()

_RPS_JOIN_LOCKS: Dict[str, asyncio.Lock] = {}
_RPS_INFLIGHT: Set[Tuple[str, int]] = set()
MAX_RPS_PLAYERS = 2  # дуэль

def _get_rps_lock(game_id: str) -> asyncio.Lock:
    lock = _RPS_JOIN_LOCKS.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _RPS_JOIN_LOCKS[game_id] = lock
    return lock

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set(); out = []
    for uid in items:
        uid = int(uid)
        if uid not in seen:
            seen.add(uid); out.append(uid)
    return out
@dp.callback_query(lambda c: c.data and c.data.startswith('rps_join:'))
async def inline_knb_join_game_callback(callback_query: types.CallbackQuery):
    try:
        # формат: rps_join:{creator_id}:{game_id}
        _, creator_id_str, game_id = callback_query.data.split(':', 2)
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    # быстрый отбой
    if game_id not in rps_games:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте")
        return
    # анти-дребезг
    inflight_key = (game_id, user_id)
    if inflight_key in _RPS_INFLIGHT:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…")
        return
    _RPS_INFLIGHT.add(inflight_key)

    try:
        lock = _get_rps_lock(game_id)
        async with lock:
            # актуальная игра внутри лока
            game = rps_games.get(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.")
                return

            inline_message_id = game.get("inline_message_id")

            # профиль (обновим, но не падём, если что-то не так)
            try:
                first_name = re.sub(r'[<>/{}"]', '', callback_query.from_user.first_name or "Игрок")
                username = callback_query.from_user.username
                await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
            except Exception:
                pass

            creator_id = int(game.get('creator', creator_id_str or 0) or 0)
            if user_id == creator_id:
                await callback_query.answer("❗️ Вы не можете присоединиться к своей игре.")
                return

            # нормализуем участников и уберём дубли
            participants = _dedupe_preserve_order_uids(list(game.get('participants', [])))
            game['participants'] = participants

            if len(participants) >= MAX_RPS_PLAYERS:
                await callback_query.answer("❗️ В игре нет мест.")
                return

            if user_id in participants:
                await callback_query.answer("❗️ Вы уже участвуете в этой игре.")
                return

            # ставка / баланс
            bet_amount = int(game.get('bet_amount', 0) or 0)
            if bet_amount > 0:
                try:
                    user_balance = await db.get_user_balance(user_id)
                    enough = (user_balance is not None) and int(user_balance) >= bet_amount
                except Exception:
                    enough = False
                if not enough:
                    await callback_query.answer("💭 Недостаточно средств для игры.")
                    return

            # ===== анти-реф внутри лока =====
            try:
                # 0) очистка просроченного
                try:
                    if hasattr(db, "remove_expired_refout"):
                        await db.remove_expired_refout()
                    else:
                        await db.cleanup_expired_refout()
                except Exception:
                    pass

                parts_set = set(participants)
                parts_set.add(creator_id)

                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id and int(inviter_id) in parts_set:
                    secs = await _pair_seconds_left(db, user_id, int(inviter_id), now=datetime.now())
                    if secs > 0:
                        await callback_query.answer(
                            "💭 Нельзя присоединиться: в лобби ваш пригласитель.\n"
                            f"⏳ До снятия ограничения: {_format_hms(secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for inv_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(inv_id), now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
                        await callback_query.answer(
                            "💭 Нельзя присоединиться: в лобби ваш приглашённый.\n"
                            f"⏳ До снятия ограничения: {_format_hms(min_secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer("💭 Техническая ошибка. Код: #1212471", show_alert=True)
                return

            # ---- критическая точка: добавляем атомарно ----
            if len(game['participants']) >= MAX_RPS_PLAYERS:
                await callback_query.answer("❗️ В игре нет мест.")
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order_uids(game['participants'])

            # сохраняем данные второго игрока
            game['opponent_id'] = user_id
            game['opponent_name'] = callback_query.from_user.first_name
            game['opponent_username'] = callback_query.from_user.username
            rps_games.save()

            # ---- UI ----
            style = game.get('style', ["<tg-emoji emoji-id='5472404692975753822'>✊</tg-emoji>", "<tg-emoji emoji-id='5472354553527541051'>✋</tg-emoji>"])
            creator_name = game.get('creator_name') or (await db.get_firstname_by_user_id(creator_id))
            opponent_name = game.get('opponent_name') or (await db.get_firstname_by_user_id(user_id))

            bet_msg = f"<tg-emoji emoji-id='5195369389599265575'>💰</tg-emoji> Ставка : {bet_amount:,.0f} кут\n".replace(",", ".") if bet_amount > 0 else ""
            participants_text = f"<b>{style[0]} {creator_name}\n{style[1]} {opponent_name}</b>"

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"start_rps:{game_id}")]]
            )

            try:
                await bot1.edit_message_text(
                    text=f"<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> <b>Играем в камень-ножницы-бумага</b>\n<b>{bet_msg}{participants_text}</b>",
                    inline_message_id=inline_message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[RPS] edit_message_text error: {e}")

            await callback_query.answer("❕ Вы присоединились к игре!")
            rps_games.save()

    except Exception as e:
        print(f"[RPS] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _RPS_INFLIGHT.discard((game_id, user_id))


@dp.callback_query(lambda c: c.data.startswith('start_rps:'))
async def inline_knb_start_game_callback(callback_query: types.CallbackQuery):

    try:
        game_id = callback_query.data.split(':')[1]
        user_id = callback_query.from_user.id
        first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
        username = callback_query.from_user.username
        await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
        inline_message_id = rps_games [ game_id ] [ "inline_message_id" ]
        # Проверяем, существует ли игра
        game = rps_games.get(game_id)
        if game is None:
            await callback_query.answer("🛠 Эта игра больше не существует.")
            return

        # Проверяем, что только создатель может начать игру
        if user_id != game.get('creator'):
            await callback_query.answer("❗️ Только создатель игры может начать игру.")
            return

        # Проверяем, что есть хотя бы два участника
        if len(game.get('participants', [])) < 2:
            await callback_query.answer("❗️ Невозможно начать игру. Недостаточно участников.")
            return

        bet_amount = game.get('bet_amount' , 0)

        # Если ставка больше 0, проверяем, достаточно ли у игрока денег
        if bet_amount > 0:
            user_balance = await db.get_user_balance(
                callback_query.from_user.id)  # Предполагается, что баланс хранится в поле 'balance'
            if user_balance < bet_amount:
                await callback_query.answer("💭 Недостаточно средств для игры." , show_alert=True)
                return

        # Создаем клавиатуру для выбора
        choices_keyboard = InlineKeyboardMarkup(
            row_width=3 , inline_keyboard=[
                [ InlineKeyboardButton(text="🪨 Камень" , callback_data=f"rpschooseknb:{game_id}:rock") ,
                    InlineKeyboardButton(text="✂️ Ножницы" , callback_data=f"rpschooseknb:{game_id}:scissors") ,
                    InlineKeyboardButton(text="📃 Бумага" , callback_data=f"rpschooseknb:{game_id}:paper") ] ])

        # Извлекаем данные о создателе и оппоненте
        creator_id = game.get('creator')
        creator_name = game.get('creator_name', 'Игрок 1')
        creator_username = game.get('creator_username')  # Получаем username создателя
        participant_id = game.get('opponent_id')
        participant_username = game.get('opponent_username')  # Получаем username участника
        participant_name = game.get('opponent_name', 'Игрок 2')
        game_name = 'rps'

        # Вставляем данные о новой игре в базу данных
        await db.add_game_inline(
            user_id1=creator_id, name_user1=creator_name,
            user_id2=participant_id, name_user2=participant_name,
            namegame=game_name, username1=creator_username , username2=participant_username
        )

        # Редактируем сообщение для начала игры
        await bot1.edit_message_text(
            text="<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> <b>Пора сделать выбор!</b>",
            inline_message_id=inline_message_id,
            reply_markup=choices_keyboard,
            parse_mode=ParseMode.HTML
        )

        await callback_query.answer("❕ Игра началась!")

    except Exception as e:
        print(f"Ошибка в start_game_callback: {e}")
    rps_games.save()

@dp.callback_query(lambda c: c.data.startswith('rpschooseknb:'))
async def inline_knb_choose_callback(callback_query: types.CallbackQuery):

    try:
        data = callback_query.data.split(':')
        game_id = data[1]
        choice = data[2]
        user_id = callback_query.from_user.id
        first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
        username = callback_query.from_user.username
        await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
        inline_message_id = rps_games [ game_id ] [ "inline_message_id" ]
        if game_id not in rps_games:
            await callback_query.answer("🛠 Эта игра больше не существует.")
            return

        game = rps_games[game_id]

        if user_id not in game['participants']:
            await callback_query.answer("❗️ Вы не участвуете в этой игре.")
            return

        if user_id in game['choices']:
            await callback_query.answer("❗️ Вы уже сделали свой выбор!")
            return

        # Сохраняем выбор игрока
        game['choices'][user_id] = choice
        print(game['choices'][user_id])

        await callback_query.answer(f"{rps_get_choice_text(choice)}")

        if len(game['choices']) == len(game['participants']):
            await rps_declare_winner(inline_message_id, game_id)
        else:
            await callback_query.answer("Вы сделали свой выбор!")
    except Exception as e:
        print(f"Ошибка в choose_callback: {e}")
    rps_games.save()

def rps_get_choice_text(choice):
    if choice == 'rock':
        return 'камень'
    elif choice == 'scissors':
        return 'ножницы'
    elif choice == 'paper':
        return 'бумага'
    else:
        return choice


def rps_describe_move(user_choice, winner_choice):
    if user_choice == 'rock' and winner_choice == 'scissors':
        return "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji> Камень разбил ножницы"
    elif user_choice == 'rock' and winner_choice == 'paper':
        return "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji> Бумага накрыла камень"
    elif user_choice == 'scissors' and winner_choice == 'paper':
        return "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Ножницы разрезали бумагу"
    elif user_choice == 'scissors' and winner_choice == 'rock':
        return "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji> Камень разбил ножницы"
    elif user_choice == 'paper' and winner_choice == 'rock':
        return "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji> Бумага накрыла камень"
    elif user_choice == 'paper' and winner_choice == 'scissors':
        return "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Ножницы разрезали бумагу"
    elif user_choice == winner_choice:
        return f"<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> {user_choice.capitalize()} не может победить само себя"
    else:
        return "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> Ошибка в объяснении результата игры"


async def rps_declare_winner(inline_message_id, game_id):
    try:
        game = rps_games[game_id]
        choices = game['choices']

        results = []
        user_names = {user_id: user_name for user_id, user_name in zip(game['participants'], [game['creator_name'], game['opponent_name']])}  # Словарь для имен участников

        for user_id, user_choice in choices.items():
            choice_text = rps_get_choice_text(user_choice)
            choice_emoji = {
                'rock': "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>",
                'scissors': "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>",
                'paper': "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji>"
            }.get(user_choice, '')

            # Добавляем результаты в виде строк
            results.append(f"{choice_emoji} {user_names[user_id]} выбрал(-а) {choice_text}")

        winner_id = rps_determine_winner(choices)

        if winner_id is not None:
            winner_choice = choices [ winner_id ]  # Получаем выбор победителя
            loser_id = next(user_id for user_id in choices if user_id != winner_id)  # Находим проигравшего
            loser_choice = choices [ loser_id ]  # Получаем выбор проигравшего
            win_description = rps_describe_move(loser_choice , winner_choice)  # Передаем оба выбора для объяснения

            # Получаем балансы участников
            winner_balance = await db.get_user_balance(winner_id)
            loser_balance = await db.get_user_balance(loser_id)
            bet_amount = game.get('bet_amount' , 0)
            await db.update_user_wins(user_id , 1 , bot1 , ref_coin)
            await db.update_user_loose(user_id , 1 , bot1 , ref_coin)#
            await db.update_game_last_activity(user_id)
            if bet_amount > 0:
                if loser_balance >= bet_amount:
                    # Обновляем балансы
                    await db.update_user_balance(winner_id , winner_balance + bet_amount)
                    await db.update_user_balance(loser_id , loser_balance - bet_amount)

                    await db.cutehistory_plus(winner_id , bet_amount , "инлайн кнб")
                    await db.cutehistory_minus(loser_id , bet_amount , "инлайн кнб ")
                    # Форматируем сумму выигрыша
                    win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".")
                    results_text = (f"<b>{win_description}</b>\n"
                                    f"<tg-emoji emoji-id='5262906070996642883'>🏆</tg-emoji> <b>{user_names [ winner_id ]} победитель!</b>\n"
                                    f"<tg-emoji emoji-id='5195369389599265575'>💰</tg-emoji> <b>Выигрыш: {win_amount_formatted} кут.</b>")
                else:
                    # У проигравшего недостаточно средств
                    results_text = (f"<b>{win_description}</b>\n"
                                    f"<tg-emoji emoji-id='5262906070996642883'>🏆</tg-emoji> <b>{user_names [ winner_id ]} победитель!</b>\n"
                                    f"<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>У проигравшего недостаточно средств для выплаты.</b>")

                # Формируем callback_data для кнопки с учетом ставки
                btn_create_game = InlineKeyboardButton(
                    text="Создать новую игру" , callback_data=f"rps_create:{winner_id}:{bet_amount}")
            else:
                # Если ставки не было
                results_text = (f"<b>{win_description}</b>\n"
                                f"<tg-emoji emoji-id='5262906070996642883'>🏆</tg-emoji> <b>{user_names [ winner_id ]} победитель!</b>\n"
                                f"<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <b>Игра завершена!</b>")

                # Формируем callback_data без ставки
                btn_create_game = InlineKeyboardButton(
                    text="Создать новую игру" , callback_data=f"rps_create")
            chat_name = "1"

            print(f"Название чата: {chat_name}")

            # Получаем данные о бонусах
            last_open_time , data_open = await db.get_historygames_times(winner_id)

            print(f"Время последнего открытия бонуса: {last_open_time}, Время окончания бонуса: {data_open}")

            # Проверяем, есть ли данные о бонусах для пользователя
            current_time = time.time()
            if last_open_time is None or data_open is None:
                # Если данных нет, создаем их
                last_open_time = get_current_time_formatted()  # Получаем текущее время
                data_open = current_time + timehistorygames  # Устанавливаем время окончания бонуса на 24 часа вперед

                print(
                    f"Данных о бонусе для пользователя {winner_id} нет. Создаем новый бонус. Время последнего открытия: {last_open_time}, Время окончания: {data_open}")

                user_name = await db.get_firstname_by_user_id(winner_id)  # Получаем имя пользователя

                print(f"Имя пользователя: {user_name}")

                # Добавляем новую запись о бонусе
                await db.add_historygames(
                    chat_id , chat_name , winner_id , user_name , last_open_time ,
                    datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Проверка, истек ли бонус
                print(f"Бонус существует. Проверяем, истек ли он. Текущее время: {current_time}")

                # Преобразуем data_open в метку времени (секунды)
                try:
                    data_open_timestamp = data_open.timestamp()  # Преобразуем datetime в метку времени (секунды)
                    print(f"Метка времени окончания бонуса: {data_open_timestamp}")
                except Exception as e:
                    print(f"Ошибка при преобразовании data_open в метку времени: {e}")
                    return

                try:
                    if current_time < data_open_timestamp:
                        # Если бонус еще активен, обновляем данные в строке
                        print(
                            f"Бонус еще активен. Текущее время: {current_time}, Метка времени окончания бонуса: {data_open_timestamp}")

                        # Обновляем данные бонуса для пользователя
                        last_open_time = get_current_time_formatted()  # Обновляем время последнего бонуса
                        data_open = current_time + timehistorygames  # Устанавливаем новое время окончания бонуса

                        # Обновляем запись в базе данных с новыми данными
                        await db.update_historygames(
                            winner_id , last_open_time ,
                            datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"))

                        # Сообщаем пользователю, что бонус был обновлен
                        print(
                            f"Данные бонуса обновлены для пользователя {winner_id}. Время последнего открытия: {last_open_time}, Время окончания: {data_open}")


                    else:
                        # Если бонус истек, обновляем его
                        print(
                            f"Бонус истек. Обновляем бонус. Текущее время: {current_time}, Новое время окончания бонуса: {data_open}")

                        last_open_time = get_current_time_formatted()  # Обновляем время последнего бонуса
                        data_open = current_time + timehistorygames  # Устанавливаем новое время окончания бонуса

                        # Обновляем запись в базе данных с новыми данными
                        await db.update_historygames(
                            winner_id , last_open_time ,
                            datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"))

                        # Сообщаем пользователю, что бонус был обновлен
                        print(
                            f"Бонус обновлен для пользователя {winner_id}. Время последнего открытия: {last_open_time}, Время окончания: {data_open}")

                except Exception as e:
                    print(f"Ошибка при проверке или обновлении бонуса: {e}")
                    return
            # Создаем клавиатуру с кнопкой для новой игры
            rps_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ btn_create_game ] ])
            # Отправляем результаты и кнопку для новой игры
            await bot1.edit_message_text(
                text=results_text , inline_message_id=inline_message_id , reply_markup=rps_keyboard ,
                parse_mode=ParseMode.HTML)

            del rps_games [ game_id ]
        else:
            # Если победителя нет (ничья)
            results_text = "<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <b>Игра завершилась ничьей!</b>"
            bet_amount = game.get('bet_amount' , 0)

            if bet_amount > 0:
                # Формируем callback_data с учетом ставки

                btn_create_game = InlineKeyboardButton(
                    text="Создать новую игру" , callback_data=f"rps_create:{winner_id}:{bet_amount}")

            else:
                # Если ставки не было
                btn_create_game = InlineKeyboardButton(
                    text="Создать новую игру" , callback_data=f"rps_create")
            # Создаем клавиатуру с кнопкой для новой игры
            rps_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ btn_create_game ] ])
            await bot1.edit_message_text(
                text=results_text , inline_message_id=inline_message_id , reply_markup=rps_keyboard ,
                parse_mode=ParseMode.HTML)

            del rps_games [ game_id ]
    except Exception as e:
        print(f"Ошибка в declare_winner: {e}")


def rps_determine_winner(choices):
    counts = {"rock": [], "scissors": [], "paper": []}
    for user_id, choice in choices.items():
        counts[choice].append(user_id)

    if counts["rock"] and counts["scissors"]:
        return counts["rock"][0]  # rock wins over scissors

    if counts["scissors"] and counts["paper"]:
        return counts["scissors"][0]  # scissors win over paper

    if counts["paper"] and counts["rock"]:
        return counts["paper"][0]  # paper wins over rock

    return None  # draw if all choices are the same or no clear winner

@dp.callback_query(lambda c: c.data and c.data.startswith("donate_buy:"))
async def donate_buy_callback(callback: types.CallbackQuery):
    # donate_buy:<stars_amount>:<nonce>

    try:
        _p, stars_amount_str, _nonce = callback.data.split(":", 2)
    except Exception:
        await callback.answer("❌ Ошибка кнопки.", show_alert=True)
        return

    await send_invoice_to_user_and_edit_payment(callback, stars_amount_str)