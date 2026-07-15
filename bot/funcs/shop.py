from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *


from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
import re
from bot.db_create.db import *
from bot.db_create.items_codec import decode_items
import json
import math
import logging

from bot.handlers.useitems import *
from main import db, bot1,user_sorting_state,button_user_sorting_state,user_shop1234



user_buy = LazyGameStore("user_buy")
user_inventory1 = LazyGameStore("user_inventory1")
user_sell1 = LazyGameStore("user_sell1")
user_giveitem = LazyGameStore("user_giveitem")

user_give = LazyGameStore("user_give")
user_message_craft = LazyGameStore("user_message_craft")
shop_cooldowns = LazyGameStore("shop_cooldowns")
user_dell = LazyGameStore("user_dell")
userbuystick = LazyGameStore("userbuystick")
usergivestick = LazyGameStore("usergivestick")
usergivestickreceiver_id = LazyGameStore("usergivestickreceiver_id")
userdellstick = LazyGameStore("userdellstick")
pending_craft_confirmations = LazyGameStore("pending_craft_confirmations")
from bot.funcs.func import *
import unicodedata
from wcwidth import wcswidth






ITEMS_PER_PAGE = 100
ITEMS_DEX_PAGE = 15
current_sale_data = LazyGameStore("current_sale_data")

global current_user3412
global current_user34123412
global current_user_id1234
global current_user_id12341234
global price3412

global sender_id
global receiver_name
global sender_name
global args
import unicodedata

REFERRAL_SOURCE_CHAT_ID = -1002135149822
BLACK_MARKET_GROUP_CHAT_ID = -1003855337972


def _safe_int(value , default=0):
    try:

        if value is None:
            return default

        return int(value)

    except Exception:

        return default


def _fmt_amount(value):
    try:

        return "{:,.0f}".format(int(value)).replace("," , ".")

    except Exception:

        return "0"


async def _maybe_await(result):
    try:

        if hasattr(result , "__await__"):
            return await result

        return result

    except TypeError:

        return result


async def _get_group_balance_safe(chat_id: int) -> Optional [ int ]:
    """

    Пытается получить баланс группы разными методами.

    Возвращает int или None, если получить баланс не удалось.

    """

    variants = [

        ("get_chat_balance" , (chat_id ,)) ,

        ("get_group_balance" , (chat_id ,)) ,

        ("get_chat_balance" , (bot1 , chat_id)) ,

        ("get_group_balance" , (bot1 , chat_id)) ,

    ]

    for method_name , args in variants:

        method = getattr(db , method_name , None)

        if method is None:
            continue

        try:

            value = await method(*args)

            balance = _safe_int(value , 0)

            print(f"[REFERRAL][GROUP_BALANCE] {method_name}{args} -> {balance}")

            return balance

        except Exception as e:

            print(f"[REFERRAL][GROUP_BALANCE][FAIL] {method_name}{args}: {e}")

    return None


async def _set_group_balance_safe(chat_id: int , new_balance: int) -> bool:
    """

    Пытается установить новый баланс группы.

    """

    new_balance = _safe_int(new_balance , 0)

    variants = [

        ("update_chat_balance" , (chat_id , new_balance)) ,

        ("update_group_balance" , (chat_id , new_balance)) ,

        ("set_chat_balance" , (chat_id , new_balance)) ,

        ("set_group_balance" , (chat_id , new_balance)) ,

        ("update_chat_balance" , (bot1 , chat_id , new_balance)) ,

        ("update_group_balance" , (bot1 , chat_id , new_balance)) ,

    ]

    for method_name , args in variants:

        method = getattr(db , method_name , None)

        if method is None:
            continue

        try:

            await method(*args)

            print(f"[REFERRAL][GROUP_SET] {method_name}{args} -> OK")

            return True

        except Exception as e:

            print(f"[REFERRAL][GROUP_SET][FAIL] {method_name}{args}: {e}")

    return False


async def _debit_group_balance_safe(chat_id: int , amount: int) -> bool:
    """

    Проверяет баланс группы и пытается списать amount.

    Если денег не хватает - возвращает False.

    Если списание удалось - True.

    """

    amount = _safe_int(amount , 0)

    if amount <= 0:
        print(f"[REFERRAL][GROUP_DEBIT] Некорректная сумма списания: {amount}")

        return False

    group_balance = await _get_group_balance_safe(chat_id)

    if group_balance is None:
        print(f"[REFERRAL][GROUP_DEBIT] Не удалось получить баланс группы {chat_id}")

        return False

    if group_balance < amount:
        print(

            f"[REFERRAL][GROUP_DEBIT] Недостаточно денег в группе {chat_id}. "

            f"Баланс: {group_balance}, нужно: {amount}"

        )

        return False

    delta_variants = [

        ("update_chat_balance" , (bot1 , chat_id , -amount)) ,

        ("add_chat_balance" , (chat_id , -amount)) ,

        ("add_group_balance" , (chat_id , -amount)) ,

        ("change_chat_balance" , (chat_id , -amount)) ,

        ("change_group_balance" , (chat_id , -amount)) ,

        ("update_chat_balance" , (chat_id , f"-{amount}")) ,

        ("update_group_balance" , (chat_id , f"-{amount}")) ,

        ("update_chat_balance" , (bot1 , chat_id , f"-{amount}")) ,

        ("update_group_balance" , (bot1 , chat_id , f"-{amount}")) ,

    ]

    for method_name , args in delta_variants:

        method = getattr(db , method_name , None)

        if method is None:
            continue

        try:

            await method(*args)

            print(

                f"[REFERRAL][GROUP_DEBIT] {method_name}{args} -> OK, "

                f"списано {amount} с группы {chat_id}"

            )

            return True

        except Exception as e:

            print(f"[REFERRAL][GROUP_DEBIT][DELTA_FAIL] {method_name}{args}: {e}")

    new_balance = group_balance - amount

    ok = await _set_group_balance_safe(chat_id , new_balance)

    if ok:
        print(

            f"[REFERRAL][GROUP_DEBIT][FALLBACK] Баланс группы {chat_id}: "

            f"{group_balance} -> {new_balance}"

        )

        return True

    print(f"[REFERRAL][GROUP_DEBIT] Не удалось списать {amount} с группы {chat_id}")

    return False



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






# Функция для получения длины строки с учетом сложных эмодзи
def get_display_width(text):
    """Возвращает ширину текста с учетом ширины Unicode-символов."""
    return wcswidth(text)

def adjust_row(row, col_positions):
    """Выравнивает строку с учетом заданных позиций колонок и добавляет разделители."""
    adjusted_row = ''
    current_pos = 0
    for idx, item in enumerate(row):
        item_width = get_display_width(item)
        target_pos = col_positions[idx]
        if current_pos < target_pos:
            adjusted_row += ' ' * (target_pos - current_pos)
        adjusted_row += item
        current_pos = target_pos + item_width
        # Добавляем пробелы после строки, если это не последний элемент
        if idx < len(row) - 1:
            adjusted_row += ' ' * (col_positions[idx + 1] - current_pos)
    return adjusted_row

# В одном ряду инвентаря всегда 3 предмета.
INVENTORY_ITEMS_PER_ROW = 3


def inventory_page_size() -> int:
    """Сколько предметов помещается на одной странице инвентаря.

    Зависит от флага True_button_navigation_inventory из config:
      • True  → INVENTORY_MAX_ROWS_PER_PAGE рядов × 3 предмета;
      • False → все предметы на одной странице (навигации нет).
    """
    if globals().get("True_button_navigation_inventory", True):
        rows = int(globals().get("INVENTORY_MAX_ROWS_PER_PAGE", 10) or 10)
        return max(1, rows) * INVENTORY_ITEMS_PER_ROW
    return 0  # 0 = без ограничения (одна бесконечная страница)


def inventory_total_pages(total_items: int) -> int:
    """Число страниц инвентаря с учётом флага навигации."""
    size = inventory_page_size()
    if size <= 0:
        return 1
    return max(1, math.ceil(total_items / size))


async def generate_inventory_page(inventory_items, page):
    """Генерирует страницу с инвентарем, включая все предметы и разделители."""
    items_list = list(inventory_items.items())

    size = inventory_page_size()
    if size <= 0:
        # Навигация выключена показываем весь инвентарь одним списком.
        page_items = items_list
    else:
        start = page * size
        end = min(start + size, len(items_list))
        page_items = items_list[start:end]

    if not page_items:
        return "—"

    # Один SQL-запрос на всю страницу вместо N отдельных get_emoji_for_item.
    emoji_map = await db.get_emojis_for_items(name for name, _ in page_items)

    rows = []
    current_row = []

    for item_name , quantity in page_items:
        emoji = emoji_map.get(item_name) or "❌"

        if emoji == "✖️":
            continue  # Пропускаем этот предмет

        formatted_quantity = "{:,.0f}".format(quantity).replace(',' , '.')
        formatted_item = f"<code>{emoji}</code> <b>{formatted_quantity}</b>"
        current_row.append(formatted_item)

        if len(current_row) == 3:
            rows.append(current_row)
            current_row = [ ]

    if current_row:
        rows.append(current_row)

    if not rows:
        return "—"

    def get_column_widths(rows):
        """Определяет максимальные ширины колонок."""
        num_columns = len(rows[0])
        column_widths = [0] * num_columns
        for row in rows:
            for idx, item in enumerate(row):
                column_widths[idx] = max(column_widths[idx], get_display_width(item))
        return column_widths

    def get_col_positions(column_widths):
        """Определяет позиции для выравнивания колонок по первому ряду."""
        positions = []
        pos = 0
        for width in column_widths:
            positions.append(pos)
            pos += width + 2  # Увеличиваем ширину колонки и пробелы до 4 для разделителей
        return positions

    # Определяем ширину колонок по первому ряду
    column_widths = get_column_widths(rows)
    col_positions = get_col_positions(column_widths)

    # Выравниваем все строки по первым колонкам
    formatted_rows = [adjust_row(row, col_positions) for row in rows]
    inventory_list = "\n".join(formatted_rows)

    return inventory_list
def get_inventory_navigation_buttons(page, total_pages):
    buttons = []

    # Навигация полностью отключена флагом кнопок нет.
    if not globals().get("True_button_navigation_inventory", True):
        return buttons

    if page > 0:
        buttons.append(InlineKeyboardButton(
            text=" " , callback_data=f"inv_page_{page - 1}" , style="default" ,
            icon_custom_emoji_id="5255703720078879038"))

    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(
            text=" " , callback_data=f"inv_page_{page + 1}" , style="default" ,
            icon_custom_emoji_id="5253767677670862169"))



    # Добавляем кнопку "закрыть"

    #buttons.append(InlineKeyboardButton("Закрыть", callback_data="close_inventory"))

    return buttons


# ---------- ОТЛАДКА (включена) ----------
DEBUG_SHOP = True  # False - выключить логи

def debug_print(*args, **kwargs):
    if DEBUG_SHOP:
        print("[SHOP_DEBUG]", *args, **kwargs)

# ---------- ХРАНИЛИЩА ----------
current_purchase_data = LazyGameStore("current_purchase_data")  # если нужен

# ---------- СОСТОЯНИЯ МАГАЗИНА ----------
user_shop_messages: Dict[int, int] = LazyGameStore("user_shop_messages")          # user_id -> message_id магазина
active_filter: Dict[int, Optional[str]] = LazyGameStore("active_filter")     # message_id -> символ фильтра
nav_cooldowns: Dict[int, float] = LazyGameStore("nav_cooldowns")            # user_id -> время последней навигации
filter_cooldowns: Dict[int, float] = LazyGameStore("filter_cooldowns")          # user_id -> время последнего фильтра

RANDOM_HELP = ["Сообщение устарело, откройте магазин заново."]

# ---------- НАСТРОЙКИ ----------
ITEMS_PER_PAGE = 10          # предметов на странице
ANTISPAM_NAV = 1.5           # задержка между нажатиями стрелок (сек)
ANTISPAM_FILTER = 0.8        # задержка для кнопок фильтра




# ---------- КЭШ СКИДОК ----------
_discount_cache: Dict[str, Tuple[Optional[int], float]] = LazyGameStore("_discount_cache")



async def preload_discounts(emojis: List[str]):
    now = time.time()
    to_fetch = []
    for emoji in emojis:
        cached = _discount_cache.get(emoji)
        if cached:
            price, ts = cached
            if price is not None and (now - ts) < DISCOUNT_CACHE_TTL:
                continue
        to_fetch.append(emoji)
    if not to_fetch:
        return
    debug_print(f"Загрузка скидок для {len(to_fetch)} эмодзи...")
    # ОДИН запрос вместо N (раньше 240 отдельных get_discounted_price).
    prices = await db.get_discounts_bulk(to_fetch)
    mapping = {emoji: (prices.get(emoji), now) for emoji in to_fetch}

    # Запись в pklcode-кэш синхронный Redis-I/O. 240 записей в цикле на
    # event-loop раньше морозили его на ~2.6с. Пишем в ОТДЕЛЬНОМ потоке.
    def _store(mapping):
        for emoji, val in mapping.items():
            _discount_cache[emoji] = val
    await asyncio.to_thread(_store, mapping)

async def get_discounted_price(emoji: str) -> Optional[int]:
    cached = _discount_cache.get(emoji)
    if cached:
        price, ts = cached
        if price is not None and (time.time() - ts) < DISCOUNT_CACHE_TTL:
            return price
    return None

async def get_available_items(filter_symbol: Optional[str] = None) -> List[Tuple[str, int, int, str]]:
    full = await get_full_items()
    debug_print(f"Фильтрация: filter_symbol='{filter_symbol}', всего предметов в базе: {len(full)}")
    items = []
    for name, price, remains, sorting, emoji in full:
        if remains <= 0:
            continue
        if filter_symbol:
            # защита от None в sorting
            if not sorting or filter_symbol not in sorting:
                continue
        items.append((name, price, remains, emoji))
    unique_emojis = list({emoji for _, _, _, emoji in items})
    await preload_discounts(unique_emojis)
    debug_print(f"После фильтра доступно предметов: {len(items)}")
    return items

# ------------------------------------------------------------
# КНОПКИ СОРТИРОВКИ (ДИНАМИЧЕСКИЕ)
# ------------------------------------------------------------
async def build_sorting_buttons() -> List[InlineKeyboardButton]:
    full = await get_full_items()
    unique = set()
    for _, _, _, sorting, _ in full:
        if sorting:
            unique.add(sorting)
    buttons = []
    for sym in sorted(unique):
        buttons.append(InlineKeyboardButton(
            text=sym,
            callback_data=f"filter_by_sorting_{sym}"
        ))
    debug_print(f"Кнопки сортировки: {sorted(unique)}")
    return buttons

def get_navigation_buttons(page: int, total_pages: int, prefix: str = "page") -> List[InlineKeyboardButton]:
    """
    Возвращает ряд кнопок навигации с индикатором страницы.
    При total_pages == 1 - только кнопка "1/1".
    Иначе: [◀️ (или петля)] [1/5] [▶️ (или петля)].
    """
    if total_pages <= 1:
        return [InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="page_info"
        )]

    row = []

    # Кнопка назад
    if page > 0:
        row.append(InlineKeyboardButton(
            text=" ",
            callback_data=f"{prefix}_{page - 1}",
            icon_custom_emoji_id="5805509901048356965"  # ◀️
        ))
    else:
        # Первая страница - кнопка-петля на последнюю
        row.append(InlineKeyboardButton(
            text=" ",
            callback_data=f"{prefix}_{total_pages - 1}",
            icon_custom_emoji_id="5805274936272494654"  # 🔄
        ))

    # Индикатор страницы
    row.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="page_info"
    ))

    # Кнопка вперёд
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(
            text=" ",
            callback_data=f"{prefix}_{page + 1}",
            icon_custom_emoji_id="5807453545548487345"  # ▶️
        ))
    else:
        # Последняя страница - петля на первую
        row.append(InlineKeyboardButton(
            text=" ",
            callback_data=f"{prefix}_0",
            icon_custom_emoji_id="5807461581432298554"  # 🔄
        ))

    return row

async def build_shop_markup(
    page: int,
    total_pages: int,
    prefix: str
) -> InlineKeyboardMarkup:
    sorting_btns = await build_sorting_buttons()
    nav_btns = get_navigation_buttons(page, total_pages, prefix)
    reset_btn = InlineKeyboardButton(
        text=" ", callback_data="reset_sorting",
        icon_custom_emoji_id="5454409660473827001"
    )
    close_btn = InlineKeyboardButton(
        text=" ", callback_data="store_close_message",
        icon_custom_emoji_id="5226660202035554522"
    )

    keyboard = []

    # Добавляем кнопку веб-приложения только если buttonwebapp != 0
    if buttonwebapp == 1:
        webapp_btn = InlineKeyboardButton(
            text="Открыть в приложении",
            url=f"https://t.me/{BOT_USERNAME123412}/{APP_NAME}?startapp=shop"
        )
        keyboard.append([webapp_btn])

    if sorting_btns:
        keyboard.append(sorting_btns)
    keyboard.append(nav_btns)
    keyboard.append([reset_btn])
    keyboard.append([close_btn])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ------------------------------------------------------------
# ГЕНЕРАЦИЯ СТРАНИЦЫ (С ЗАЩИТОЙ ОТ HTML)
# ------------------------------------------------------------
import html

def format_price(value: int) -> str:
    return "{:,.0f}".format(value).replace(",", ".")

async def generate_catalog_page(items: List[Tuple[str, int, int, str]], page: int) -> Tuple[str, int]:
    if not items:
        return "Каталог пуст", 0
    start = page * ITEMS_PER_PAGE
    end = min(start + ITEMS_PER_PAGE, len(items))

    page_emojis = [emoji for _, _, _, emoji in items[start:end]]
    await preload_discounts(page_emojis)
    disc_map = {}
    for emoji in page_emojis:
        disc_map[emoji] = await get_discounted_price(emoji)

    catalog = "<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Магазин</b>\n\n"
    for name, price, remains, emoji in items[start:end]:
        disc_price = disc_map.get(emoji)
        remains_fmt = format_price(remains)
        price_fmt = format_price(price)
        safe_name = html.escape(name, quote=False)  # экранируем HTML-символы в названии
        if disc_price and disc_price > 0:
            disc_fmt = format_price(disc_price)
            catalog += (
                f"<code>{emoji}</code> <b>{safe_name} [ <i>{remains_fmt} шт</i> ] - </b>"
                f"<s>{price_fmt}</s> <b>{disc_fmt}</b> "
                f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji>\n\n"
            )
        else:
            catalog += (
                f"<code>{emoji}</code> <b>{safe_name} [ <i>{remains_fmt} шт</i> ] - "
                f"{price_fmt}</b> "
                f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji>\n\n"
            )
    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
    debug_print(f"Сгенерирована страница {page}/{total_pages}, длина текста: {len(catalog)}")
    return catalog.strip(), total_pages

# ============================================================
# ОБРАБОТЧИК ОТКРЫТИЯ МАГАЗИНА
# ============================================================
@dp.message()
async def shop_op(message: Message):
    if message.text.strip().lower() in [ "ферма" ]:
        if buttonwebapp != 1:  # если 0, None или False
            return  # выходим из обработчика, ничего не отправляем

        STICKER_FARM = "CAACAgIAAxkBAz0Olmo3EismmDFcJjau6qhIBikZzK7wAAIwTQACGKbRSluouIGSQuh5PAQ"
        url = f"https://t.me/{BOT_USERNAME123412}/{APP_NAME}?startapp=farm"
        webapp_btn = InlineKeyboardButton(text="Открыть ферму" , url=url)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ webapp_btn ] ])
        await message.answer_sticker(STICKER_FARM , reply_markup=keyboard)

    if message.text.strip().lower() in [ "биржа" , "рынок" , "маркет" ]:
        if buttonwebapp != 1:
            return

        STICKER_MARKET = "CAACAgIAAxkBAzsOFGo0URpw6VHeFJ0cV7uIWEXerD59AALNAAOYv4ANUzcwURozRpk8BA"
        url = f"https://t.me/{BOT_USERNAME123412}/{APP_NAME}?startapp=market"
        webapp_btn = InlineKeyboardButton(text="Открыть биржу" , url=url)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ webapp_btn ] ])
        await message.answer_sticker(STICKER_MARKET , reply_markup=keyboard)

    if message.text.strip().lower() in ["магазин", "/shop", "/shop@cutegamingbot", "shop", "шоп"]:

        user_id = message.from_user.id
        debug_print(f"Открытие магазина пользователем {user_id}")
        if random.randint(1, 100) <= 20 and message.chat.type == "private":
            await message.answer(
                random.choice(["<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji>"]),
                parse_mode="HTML"
            )
        items = await get_available_items()
        catalog, total_pages = await generate_catalog_page(items, 0)
        markup = await build_shop_markup(0, total_pages, "page")
        sent = await message.reply(
            catalog, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
        )
        msg_id = sent.message_id
        user_shop_messages[user_id] = msg_id
        active_filter[msg_id] = None
        nav_cooldowns.pop(user_id, None)
        filter_cooldowns.pop(user_id, None)


    # Проверяем первое слово и его длину списка слов
    # Исправленный блок кода для обработчика "купить"
    words = message.text.lower().split()
    if message.text in ['хелп крафты','Хелп крафты','хелп крафт','Хелп крафт']:
        await message.reply('''
<tg-emoji emoji-id='5296631769112525274'>🎩</tg-emoji> <b>КРАФТ ПРЕДМЕТОВ</b>

<tg-emoji emoji-id='5472427031100667803'>🍄</tg-emoji> <b>Что такое крафт?</b>
<blockquote><b>Это объединение двух предметов в один новый.</b></blockquote>

<tg-emoji emoji-id='5242451907724716893'>⌨️</tg-emoji> <b>Как создать предмет?</b>
<b>Напишите эту команду :</b>
<code>Крафт 🍺 + 🍺</code>

<tg-emoji emoji-id='5321074406519229640'>🤔</tg-emoji> <b>А где взять другие рецепты?</b>
<tg-emoji emoji-id='5359736160224586485'>🎁</tg-emoji> <b>Бот НЕ показывает все рецепты сразу - их нужно узнавать у других пользователей.</b>
<blockquote><b><tg-emoji emoji-id='6001565902456228848'>✔️</tg-emoji> Спросите в общем чате @CuteGamingChat : «Кто знает, как скрафтить двойное пиво?»</b></blockquote>
<blockquote><b><tg-emoji emoji-id='6001565902456228848'>✔️</tg-emoji> Или обменяйтесь рецептами с друзьями.</b></blockquote>
        ''',parse_mode="HTML")

    def craft_log(level , *args):
        if not DEBUG_CRAFT or level > DEBUG_CRAFT_LEVEL:
            return
        print(f"[CRAFT]" , *args)

    if len(words) >= 2 and words [ 0 ] in [ "крафт" , "скрафтить" ]:
        user_id = message.from_user.id
        craft_text = ' '.join(words [ 1: ])
        craft_log(1 , f"Пользователь {user_id} ввёл: {craft_text}")

        # Парсинг пары "эмодзи + эмодзи"
        match = re.match(r"(.+?)\s*\+\s*(.+)" , craft_text)
        if match:
            emoji_left , emoji_right = match.groups()
            emoji_left = emoji_left.strip()
            emoji_right = emoji_right.strip()
        else:
            parts = craft_text.split()
            if len(parts) == 2:
                emoji_left , emoji_right = parts
            else:
                await message.reply(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                    "<b>Неверный формат. Пример: крафт 🪵 + 🔥</b>" , parse_mode="HTML")
                return

        # Получаем названия предметов из БД
        item_left_name = await db.find_item_by_emoji_craft(emoji_left)
        item_right_name = await db.find_item_by_emoji_craft(emoji_right)
        if not item_left_name or not item_right_name:
            await message.reply(
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Один из предметов не подходит для крафта.</b>" , parse_mode="HTML")
            return

        # Данные пользователя
        user_data = await db.get_user_data_craft(user_id)
        if not user_data:
            await message.reply(
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Пользователь не найден.</b>" , parse_mode="HTML")
            return
        _ , _ , user_items_json = user_data
        if not user_items_json:
            await message.reply(
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Ваш инвентарь пуст</b>" , parse_mode="HTML")
            return

        try:
            inventory = decode_items(user_items_json)
            if not inventory:
                raise ValueError("Инвентарь пуст или не распознан")

            if not isinstance(inventory , dict):
                raise ValueError("Инвентарь не словарь")
            craft_log(2 , f"Инвентарь {user_id}: {inventory}")

            if inventory.get(item_left_name , 0) < 1 or inventory.get(item_right_name , 0) < 1:
                await message.reply(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                    "<b>Недостаточно предметов.</b>" , parse_mode="HTML")
                return

            # Запрос рецептов (любой порядок предметов)
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT item, remains, craftchance 
                    FROM craft 
                    WHERE (item1 = $1 AND item2 = $2) OR (item1 = $2 AND item2 = $1)
                    """ , emoji_left , emoji_right)
                recipes = [ ]
                for row in rows:
                    chance = row [ 'craftchance' ]
                    if chance is None:
                        chance = 100
                    else:
                        chance = int(chance)
                    recipes.append(
                        {'result_emoji': row [ 'item' ] , 'remains': row [ 'remains' ] , 'craftchance': chance})

            if not recipes:
                await message.reply(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                    "<b>Рецепт не найден.</b>" , parse_mode="HTML")
                return

            craft_log(2 , f"Найдено рецептов: {len(recipes)}")

            # Формируем кнопки выбора рецепта (макс. 30)
            buttons = [ ]
            for idx , rec in enumerate(recipes):
                result_emoji = rec [ 'result_emoji' ]
                result_name = await db.find_item_name_by_emoji(result_emoji)
                if not result_name:
                    craft_log(0 , f"Не найден предмет для эмодзи {result_emoji}, пропускаем")
                    continue
                btn_text = f"{result_emoji}"
                callback_data = f"craft_choose:{emoji_left}+{emoji_right}:{idx}"
                buttons.append(InlineKeyboardButton(text=btn_text , callback_data=callback_data))
                if len(buttons) >= 30:
                    craft_log(1 , "Достигнут лимит 30 кнопок, остальные рецепты не показаны")
                    break

            if not buttons:
                await message.reply(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                    "<b>Нет доступных результатов для крафта.</b>" , parse_mode="HTML")
                return

            # ========== ПОСТРОЕНИЕ КЛАВИАТУРЫ ==========
            MAX_BUTTONS_PER_ROW = 8
            keyboard_rows = [ ]

            # Ряды с кнопками выбора рецептов
            for i in range(0 , len(buttons) , MAX_BUTTONS_PER_ROW):
                keyboard_rows.append(buttons [ i:i + MAX_BUTTONS_PER_ROW ])

            # Кнопка «Открыть в приложении» – добавляем только если buttonwebapp == 1
            if buttonwebapp == 1:
                webapp_button = InlineKeyboardButton(
                    text="Открыть в приложении" , url=f"https://t.me/{BOT_USERNAME123412}/{APP_NAME}?startapp=craft")
                keyboard_rows.append([ webapp_button ])

            # Кнопка отмены (закрытия)
            cancel_btn = InlineKeyboardButton(
                text=" " , callback_data="craft_cancel" , icon_custom_emoji_id="5226660202035554522")
            keyboard_rows.append([ cancel_btn ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            sent_msg = await message.reply(
                "<tg-emoji emoji-id='5262565883816995477'>💎</tg-emoji> "
                "<b>Выберите результат крафта:</b>" , reply_markup=keyboard , parse_mode="HTML")
            pending_craft_confirmations [ user_id ] = {'message_id': sent_msg.message_id , 'recipes': recipes ,
                'emoji_left': emoji_left , 'emoji_right': emoji_right , 'item_left_name': item_left_name ,
                'item_right_name': item_right_name}
            craft_log(1 , f"Кнопки выбора отправлены для {user_id}")

        except json.JSONDecodeError as e:
            craft_log(0 , f"Ошибка JSON: {e}")
            await message.reply("<b>Ошибка чтения инвентаря (неверный формат данных).</b>" , parse_mode="HTML")
        except ValueError as e:
            craft_log(0 , f"Ошибка значения: {e}")
            await message.reply("<b>Ошибка данных инвентаря.</b>" , parse_mode="HTML")
        except Exception as e:
            craft_log(0 , f"Неожиданная ошибка: {e}")
            await message.reply("<b>Ошибка обработки инвентаря.</b>" , parse_mode="HTML")

    # ------------------------------------------------------------
    # ОБРАБОТЧИК ВЫБОРА РЕЗУЛЬТАТА КРАФТА (с информацией о бонусе)
    # ------------------------------------------------------------
    @dp.callback_query(lambda c: c.data and c.data.startswith('craft_choose:'))
    async def craft_choose_handler(callback_query: types.CallbackQuery):
        user_id = None
        try:
            _ , pair , idx_str = callback_query.data.split(':')
            emoji_left , emoji_right = pair.split('+')
            idx = int(idx_str)
            user_id = callback_query.from_user.id
            msg_id = callback_query.message.message_id

            craft_log(1 , f"Пользователь {user_id} выбрал вариант {idx} для {emoji_left}+{emoji_right}")

            # Проверяем актуальность
            if user_id not in pending_craft_confirmations:
                await callback_query.answer(random.choice(randommessagehelp))
                return
            data = pending_craft_confirmations [ user_id ]
            if data [ 'message_id' ] != msg_id:
                await callback_query.answer(random.choice(randommessagehelp))
                return

            if idx < 0 or idx >= len(data [ 'recipes' ]):
                await callback_query.answer("Неверный выбор." , show_alert=True)
                return

            recipe = data [ 'recipes' ] [ idx ]
            result_emoji = recipe [ 'result_emoji' ]
            result_count = recipe [ 'remains' ]
            base_chance = recipe [ 'craftchance' ]  # 0..100

            item_left_name = data [ 'item_left_name' ]
            item_right_name = data [ 'item_right_name' ]

            # Повторная проверка инвентаря
            user_data = await db.get_user_data_craft(user_id)
            if not user_data:
                await callback_query.message.edit_text(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Пользователь не найден.</b>" ,
                    parse_mode="HTML")
                return
            _ , _ , user_items_json = user_data
            if not user_items_json:
                await callback_query.message.edit_text(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ваш инвентарь пуст.</b>" ,
                    parse_mode="HTML")
                return
            inventory = decode_items(user_items_json)
            if not inventory:
                await callback_query.message.edit_text(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ваш инвентарь пуст.</b>" ,
                    parse_mode="HTML")
                return
            if inventory.get(item_left_name , 0) < 1 or inventory.get(item_right_name , 0) < 1:
                await callback_query.message.edit_text(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Предметов больше нет.</b>" ,
                    parse_mode="HTML")
                return

            # Получаем бонус пользователя ДО крафта
            user_bonus = await db.get_user_craftprox(user_id)
            user_bonus = max(0 , min(100 , user_bonus))
            final_chance = min(base_chance + user_bonus , 100)
            roll = random.randint(1 , 100)
            success = roll <= final_chance

            craft_log(
                1 ,
                f"Шанс: базовый={base_chance} + бонус={user_bonus} = {final_chance} | выпало={roll} | успех={success}")

            # Удаляем исходные предметы и сбрасываем бонус
            await db.remove_items_craft(user_id , item_left_name , 1)
            await db.remove_items_craft(user_id , item_right_name , 1)
            await db.reset_craftprox(user_id)

            # Формируем текст с информацией о бонусе
            bonus_text = ""
            if user_bonus > 0:
                bonus_text = f"\n<i>{user_bonus}% бонус, сгорел</i>"

            if success:
                result_name = await db.find_item_name_by_emoji(result_emoji)
                if not result_name:
                    raise ValueError(f"Не найден предмет для эмодзи {result_emoji}")
                await db.add_item_craft(user_id , result_name , result_count)
                if result_count > 1:
                    text = f"<tg-emoji emoji-id='5247186516463091814'>🐒</tg-emoji> <b>Успех! +{result_count} <code>{result_emoji}</code></b>{bonus_text}"
                else:
                    text = f"<tg-emoji emoji-id='5247186516463091814'>🐒</tg-emoji> <b>Успех! Вы получили <code>{result_emoji}</code></b>{bonus_text}"
            else:
                text = f"<tg-emoji emoji-id='5247114421142058549'>🐒</tg-emoji> <b>Провал! Предметы сгорели.</b>{bonus_text}"

            await callback_query.message.edit_text(text , parse_mode="HTML")
            craft_log(1 , f"Крафт завершён: {'успех' if success else 'провал'}")

        except Exception as e:
            craft_log(0 , f"Ошибка в craft_choose_handler: {e}")
            if user_id:
                await callback_query.message.edit_text("<b>Произошла ошибка.</b>" , parse_mode="HTML")
        finally:
            if user_id and user_id in pending_craft_confirmations:
                del pending_craft_confirmations [ user_id ]
            if callback_query:
                await callback_query.answer()

    # ------------------------------------------------------------
    # ОБРАБОТЧИК ОТМЕНЫ КРАФТА
    # ------------------------------------------------------------
    @dp.callback_query(lambda c: c.data == 'craft_cancel')
    async def craft_cancel_handler(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        msg_id = callback_query.message.message_id

        if user_id not in pending_craft_confirmations or pending_craft_confirmations [ user_id ].get(
                'message_id') != msg_id:
            await callback_query.answer(random.choice(randommessagehelp))
            return
        await callback_query.answer()

        await callback_query.message.edit_text(
            "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Крафт отменён.</b>" , parse_mode="HTML")
        if user_id in pending_craft_confirmations:
            del pending_craft_confirmations [ user_id ]
        craft_log(1 , f"Крафт отменён пользователем {user_id}")











    #3
    print('🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈🎈' )

    if any(
            command in message.text.strip().lower() for command in
            ["инвентарь", "инвент", "рюкзак", "/backpack@cutegamingbot", "/backpack", "/backpack@CuteGamingBot",
             "/bp", "/bp", "/BP", "/bP", "/Bp"]):
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            first_name = await db.get_firstname_by_user_id(user_id)
            username = await db.get_username_by_user_id(user_id)
            name_link = await create_user_link(user_id, first_name, username)
            header = f"<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Инвентарь {name_link}</b>\n\n"
        else:
            user_id = message.from_user.id
            header = "<tg-emoji emoji-id='5319009880164570032'>🎒</tg-emoji> <b>Ваш инвентарь</b>\n\n"

        try:
            # Санитизация на лету:
            # - удаляем предметы, которых нет в dex;
            # - emoji-ключи приводим к каноническому dex.name;
            # - при изменениях сохраняем обратно в users.items как чистый JSON.
            inventory_items = await db.sanitize_user_inventory_against_dex(user_id)
            if not inventory_items:
                await message.reply(
                    f"<tg-emoji emoji-id='5837137271416950239'>🏝</tg-emoji> <b>Инвентарь пуст</b>",
                    parse_mode="HTML")
                return

            page = 0
            total_pages = inventory_total_pages(len(inventory_items))

            inventory_list = await generate_inventory_page(inventory_items, page)
            navigation_buttons = get_inventory_navigation_buttons(page, total_pages)

            closeinventory1 = InlineKeyboardButton(
                text=" ", callback_data="close_message_inventory", style="default",
                icon_custom_emoji_id="5226660202035554522")

            # ====== ПОСТРОЕНИЕ КЛАВИАТУРЫ ======
            keyboard_rows = []

            # Кнопка веб-приложения – только если buttonwebapp != 0
            if buttonwebapp == 1:
                webapp_button = InlineKeyboardButton(
                    text="Открыть в приложении",
                    url=f"https://t.me/{BOT_USERNAME123412}/{APP_NAME}?startapp=inventory")
                keyboard_rows.append([webapp_button])

            # Навигационные кнопки (только если есть куда листать)
            if navigation_buttons:
                keyboard_rows.append(navigation_buttons)
            # Кнопка закрытия
            keyboard_rows.append([closeinventory1])

            markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            sent_inventory = await message.reply(
                f'{header}{inventory_list}', parse_mode="HTML", disable_web_page_preview=True,
                reply_markup=markup)
            user_inventory1[user_id] = sent_inventory.message_id

        except Exception as e:
            logging.exception("inventory display error for user %s: %s", user_id, e)
            await message.reply(
                f"<b>Ошибка чтения инвентаря. Обратитесь к создателю бота</b>", parse_mode="HTML",
                disable_web_page_preview=True)
        return
    elif len(words) > 1 and words [ 0 ] in [ "купить" , "Купить" , "/buy@CuteGamingBot" ]:

        try:

            user_id = message.from_user.id

            if len(words) < 2 or not words [ 1 ]:
                await message.reply("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неправильный формат команды. Используйте: купить <эмодзи> <количество></b>", parse_mode="HTML" ,disable_web_page_preview=True)
                return  # Немедленный выход из функции

            print(f"🛠️ [DEBUG] Обработка команды 'купить'. ID пользователя: {user_id}")

            inputs = words [ 1: ]

            emojis = [ ]

            quantity = 1

            print(f"🛠️ [DEBUG] Входные данные: {inputs}")

            for input_str in inputs:

                if ',' in input_str:

                    emojis.extend(input_str.split(','))

                else:

                    emojis.append(input_str)

            print(f"🛠️ [DEBUG] Эмодзи для покупки: {emojis}")

            if len(emojis) > 1 and emojis [ -1 ].isdigit():
                quantity = int(emojis.pop())

            print(f"🛠️ [DEBUG] Количество предметов для покупки: {quantity}")

            bought_items = [ ]

            total_price = 0

            discount_coupon = None

            # Получаем инвентарь пользователя

            user_inventory = await db.get_user_inventory(user_id)

            print(f"🛠️ [DEBUG] Инвентарь пользователя: {user_inventory}")

            user_inventory = decode_items(user_inventory)
            if not user_inventory:
                user_inventory = LazyGameStore("user_inventory")
                print(f"🛠️ [DEBUG] Инвентарь пользователя пуст или в неправильном формате.")

            # Проверка на наличие купонов

            if 'Купон на скидку' in user_inventory:
                coupon_quantity = user_inventory.get('Купон на скидку' , 0)

                discount_coupon = f"{coupon_quantity}🎟"

                print(f"🛠️ [DEBUG] Найден купон на скидку: {discount_coupon}")

            is_discount_coupon_in_cart = False

            for emoji in emojis:

                item_info = await db.get_item_info_by_emoji(emoji)

                print(f"🛠️ [DEBUG] Информация о предмете для эмодзи {emoji}: {item_info}")

                if item_info:

                    item_name , item_remain = item_info

                    # Проверяем, покупает ли пользователь "Купон на скидку"

                    if item_name == "Купон на скидку":
                        is_discount_coupon_in_cart = True

                    bought_quantity = min(quantity , item_remain)

                    max_quantity = 501 if item_name == "💠 CuteCoin" else 1001 if item_name == "💖 LoveCoin" else 5

                    formatted_max_quantity = "{:,.0f}".format(max_quantity).replace(',' , '.')

                    print(f"🛠️ [DEBUG] Максимально допустимое количество для {item_name}: {formatted_max_quantity}")

                    if bought_quantity > max_quantity:
                        await message.reply(f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Нельзя купить более {formatted_max_quantity} предметов за раз</b>", parse_mode="HTML" ,disable_web_page_preview=True)

                        print(f"⚠️ [DEBUG] Превышено допустимое количество для покупки.")

                        return

                    discounted_price = await db.get_discounted_price(emoji)

                    # Если скидка существует и больше 0, используем её; иначе используем стандартную цену
                    if discounted_price is not None and discounted_price > 0:
                        item_price = discounted_price
                        print(f"🛠️ [DEBUG] Цена за единицу {item_name} со скидкой: {item_price}")
                    else:
                        item_price = await db.get_item_price(item_name)
                        print(f"🛠️ [DEBUG] Цена за единицу {item_name}: {item_price}")

                    if item_price is not None:

                        if bought_quantity > 0:

                            total_price += bought_quantity * item_price

                            formatted_bought_quantity = "{:,.0f}".format(bought_quantity).replace(',' , '.')

                            item_emoji = await db.get_emoji_for_item_name(item_name)

                            bought_items.append(

                                f"<code>{item_emoji}</code> <b>{item_name} [{formatted_bought_quantity} шт]</b>")

                            print(f"🛠️ [DEBUG] Добавлено в корзину: {item_name} [{formatted_bought_quantity} шт]")

                        else:

                            await message.reply(f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предмета нет в наличии</b>", parse_mode="HTML" ,disable_web_page_preview=True)

                            print(f"⚠️ [DEBUG] Предмета {item_name} нет в наличии.")

                            return

                    else:

                        print(f"⚠️ [DEBUG] Не удалось получить цену для {item_name}.")

                        return

                #else:

                    #await message.reply("⚠️ Предмета нет в наличии")

                    #print(f"⚠️ [DEBUG] Предмет с эмодзи {emoji} не найден.")

            # Если есть что покупать, создаем Inline-кнопки для подтверждения

            current_purchase_data [ user_id ] = {

                'emojis': emojis ,

                'quantity': quantity ,

                'user_id': user_id ,

                'bought_items': bought_items ,

                'total_price': total_price

            }

            print(f"🛠️ [DEBUG] Данные покупки: {current_purchase_data [ user_id ]}")

            if bought_items:

                sticker_id = await db.get_item_sticker(emoji=emoji)

                if sticker_id:  # Если стикер найден
                    try:
                        print(f"🛠️ [DEBUG] Найден стикер для {emoji}: {sticker_id}")
                        sent_stick = await message.reply_sticker(sticker_id)  # Отправляем стикер перед сообщением
                        userbuystick [ user_id ] = sent_stick.message_id
                    except Exception as e:
                        print(f"⚠️ [DEBUG] Ошибка при отправке стикера: {e}")
                        await message.reply(
                            f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Ошибка: некорректный идентификатор стикера для предмета {item_name}.</b>" ,
                            parse_mode="HTML" , disable_web_page_preview=True , )
                        return
                else:
                    print(f"⚠️ [DEBUG] Стикер для {emoji} не найден или некорректен.")

                # Создаем клавиатуру для кнопок
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[  # Здесь создаем список кнопок
                        [ InlineKeyboardButton(text="Отменить" , callback_data="cancel341234123412"), InlineKeyboardButton(text="Купить" , callback_data="buy341234123412") ] , ])

                # Добавление кнопки для купона, если он есть
                if discount_coupon and not is_discount_coupon_in_cart:
                    keyboard.inline_keyboard.append(
                        [  # Используем append для добавления новой строки кнопок
                            InlineKeyboardButton(text=f"{discount_coupon}" , callback_data="apply_coupon") ])
                # Печать для отладки
                print(f"🛠️ [DEBUG] Добавлены кнопки 'Отменить' и 'Купить' в одном ряду.")

                # Форматируем сумму для сообщения
                win_amount_formatted = "{:,.0f}".format(total_price).replace("," , ".")

                # Добавляем текст инструкции
                instruction_text = f"\n\n<tg-emoji emoji-id='5389057356493511934'>🚀</tg-emoji> <b><i>В случае, если кнопки не работают, напишите : <code>.купить {' '.join(words [ 1: ])}</code></i></b>"

                try:
                    sent_buy = await message.reply(
                        "\n".join(bought_items) + f"\n<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> <b>{win_amount_formatted} кут</b>" + instruction_text ,
                        reply_markup=keyboard , parse_mode="HTML" , )
                    print(f"🛠️ [DEBUG] Отправлено сообщение с выбором: {sent_buy.message_id}")
                    user_buy [ user_id ] = sent_buy.message_id
                except Exception as e:
                    print(f"⚠️ [DEBUG] Ошибка при отправке сообщения: {e}")
            else:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [ InlineKeyboardButton(text="Предмета не существует" , callback_data="noop") ] ,
                        [ InlineKeyboardButton(text="в магазине" , callback_data="noop") ] ])

                # Отправка стикера вместо сообщения
                await message.answer_sticker(
                    sticker="CAACAgIAAxkBAsBOE2mBslvl7h2sEFMyB5Vr1Z6iF0tSAAIzmgACmpkISLfZRhfQLvA3OAQ" , reply_markup=kb)

        except (IndexError , ValueError) as e:

            print(f"⚠️ [DEBUG] Ошибка при обработке покупки: {e}")



    elif len(words) > 1 and words [ 0 ] in [ ".купить" , ".Купить" ]:

        try:

            user_id = message.from_user.id

            if len(words) < 2 or not words [ 1 ]:
                await message.reply(

                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неправильный формат команды. Используйте: .купить &lt;эмодзи&gt; &lt;количество&gt;</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            print(f"🛠️ [DEBUG] Обработка команды '.купить'. ID пользователя: {user_id}")

            inputs = words [ 1: ]

            emojis = [ ]

            quantity = 1

            # Разделение по запятым и обработка количества

            for input_str in inputs:

                if "," in input_str:

                    for part in input_str.split(","):

                        part = str(part).strip()

                        if part:
                            emojis.append(part)

                else:

                    input_str = str(input_str).strip()

                    if input_str:
                        emojis.append(input_str)

            print(f"🛠️ [DEBUG] Сырые данные для покупки: {emojis}")

            if emojis and str(emojis [ -1 ]).isdigit():
                quantity = _safe_int(emojis.pop() , 1)

            if not emojis:
                await message.reply(

                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Вы не указали предмет для покупки</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            if quantity <= 0:
                await message.reply(

                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Количество должно быть больше 0</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            print(f"🛠️ [DEBUG] Эмодзи для покупки: {emojis}")

            print(f"🛠️ [DEBUG] Количество предметов для покупки: {quantity}")

            bought_items = [ ]

            total_price = 0

            purchase_rows = [ ]

            # =========================================================

            # ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА ВСЕХ ПРЕДМЕТОВ

            # =========================================================

            for emoji in emojis:

                try:

                    item_info = await db.get_item_info_by_emoji(emoji)

                except Exception as e:

                    print(f"[BUY_MESSAGE] Ошибка получения информации по предмету {emoji}: {e}")

                    item_info = None

                if not item_info:
                    kb = InlineKeyboardMarkup(

                        inline_keyboard=[

                            [ InlineKeyboardButton(text="Предмета не существует" , callback_data="noop") ] ,

                            [ InlineKeyboardButton(text="в магазине" , callback_data="noop") ]

                        ]

                    )

                    await message.answer_sticker(

                        sticker="CAACAgIAAxkBAsBOE2mBslvl7h2sEFMyB5Vr1Z6iF0tSAAIzmgACmpkISLfZRhfQLvA3OAQ" ,

                        reply_markup=kb

                    )

                    return

                try:

                    item_name , item_remain = item_info

                except Exception:

                    print(f"[BUY_MESSAGE] Некорректный формат item_info для {emoji}: {item_info}")

                    await message.reply(

                        "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Ошибка данных предмета</b>" ,

                        parse_mode="HTML" ,

                        disable_web_page_preview=True

                    )

                    return

                item_remain = _safe_int(item_remain , 0)

                bought_quantity = min(quantity , item_remain)

                max_quantity = (

                    500 if item_name == "💠 CuteCoin" else

                    1000 if item_name == "💖 LoveCoin" else

                    5

                )

                if quantity > max_quantity:
                    await message.reply(

                        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Нельзя купить более {max_quantity} предметов за раз</b>" ,

                        parse_mode="HTML" ,

                        disable_web_page_preview=True

                    )

                    print(f"⚠️ [DEBUG] Превышено допустимое количество для {item_name}.")

                    return

                if bought_quantity <= 0:
                    await message.reply(

                        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предмет {item_name} недоступен или его количество равно 0</b>" ,

                        parse_mode="HTML" ,

                        disable_web_page_preview=True

                    )

                    return

                try:

                    discounted_price = await db.get_discounted_price(emoji)

                except Exception as e:

                    print(f"[BUY_MESSAGE] Ошибка получения скидочной цены для {emoji}: {e}")

                    discounted_price = None

                if discounted_price is not None and _safe_int(discounted_price , 0) > 0:

                    item_price = _safe_int(discounted_price , 0)

                    print(f"🛠️ [DEBUG] Цена за единицу {item_name} со скидкой: {item_price}")

                else:

                    try:

                        raw_item_price = await db.get_item_price(item_name)

                    except Exception as e:

                        print(f"[BUY_MESSAGE] Ошибка получения обычной цены для {item_name}: {e}")

                        raw_item_price = None

                    item_price = _safe_int(raw_item_price , 0)

                    print(f"🛠️ [DEBUG] Цена за единицу {item_name}: {item_price}")

                if item_price <= 0:
                    await message.reply(

                        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Цена предмета {item_name} не найдена</b>" ,

                        parse_mode="HTML" ,

                        disable_web_page_preview=True

                    )

                    return

                item_total_price = bought_quantity * item_price

                total_price += item_total_price

                purchase_rows.append(
                    {

                        "emoji": emoji ,

                        "item_name": item_name ,

                        "item_remain": item_remain ,

                        "bought_quantity": bought_quantity ,

                        "item_price": item_price ,

                        "item_total_price": item_total_price ,

                    })

            # =========================================================

            # ПРОВЕРКА ОБЩЕГО БАЛАНСА ПЕРЕД ПОКУПКОЙ

            # =========================================================

            try:

                current_balance = _safe_int(await db.get_user_balance(user_id) , 0)

            except Exception as e:

                print(f"[BUY_MESSAGE] Ошибка получения баланса пользователя {user_id}: {e}")

                await message.reply(

                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Не удалось получить ваш баланс</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            if current_balance < total_price:
                await message.reply(

                    f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Недостаточно средств для покупки</b>\n<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> <b>Нужно : {_fmt_amount(total_price)} кут</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            new_balance = current_balance - total_price

            source_chat_id = int(getattr(message.chat , "id" , 0) or 0)

            # =========================================================

            # ПРИМЕНЕНИЕ ПОКУПКИ

            # =========================================================

            market_deposit_ok = False
            try:

                # LEGACY: dexbalance заморожен.
                # Теперь покупка всегда уходит в баланс чёрного рынка
                # и логируется по пользователю.
                market_deposit_ok = await db.record_shop_purchase_black_market_deposit(
                    bot1 ,
                    user_id=user_id ,
                    amount=total_price ,
                    source_chat_id=source_chat_id ,
                    note="shop_buy_message" ,
                    target_chat_id=BLACK_MARKET_GROUP_CHAT_ID ,
                )
                if not market_deposit_ok:
                    raise RuntimeError("black market deposit failed")

                await db.update_user_balance(user_id , new_balance)

                await db.cutehistory_minus(user_id , total_price , "покупка предмета через .купить")

            except Exception as e:

                if market_deposit_ok:
                    try:
                        await db.update_chat_balance(bot1 , BLACK_MARKET_GROUP_CHAT_ID , -total_price)
                    except Exception as rollback_err:
                        print(f"[BUY_MESSAGE][ROLLBACK] Не удалось откатить рынок: {rollback_err}")

                print(f"[BUY_MESSAGE] Ошибка при основном списании/зачислении: {e}")

                await message.reply(

                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Не удалось завершить покупку</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

                return

            for row in purchase_rows:

                item_name = row [ "item_name" ]

                bought_quantity = row [ "bought_quantity" ]

                emoji = row [ "emoji" ]

                try:

                    await db.set_items(user_id , item_name , bought_quantity)

                    await db.buy_item(item_name , bought_quantity)

                except Exception as e:

                    print(

                        f"[BUY_MESSAGE] Ошибка обновления инвентаря/биржи "
    
                        f"для пользователя {user_id}, item={item_name}: {e}"

                    )

                    continue

                if item_name == "💠 CuteCoin":

                    try:

                        result = db.update_user_cutecoin_balance(user_id , bought_quantity)

                        await _maybe_await(result)

                    except Exception as e:

                        print(f"[BUY_MESSAGE][CUTECOIN] Ошибка обновления CuteCoin баланса: {e}")

                try:

                    item_emoji = await db.get_emoji_for_item_name(item_name)

                except Exception:

                    item_emoji = emoji

                formatted_bought_quantity = _fmt_amount(bought_quantity)

                bought_items.append(

                    f"<code>{item_emoji}</code> <b>{item_name} [{formatted_bought_quantity} шт]</b>"

                )

                print(

                    f"🛠️ [DEBUG] Пользователь {user_id} приобрел {bought_quantity} шт. {item_name}. "
    
                    f"Цена за единицу: {row [ 'item_price' ]}, сумма: {row [ 'item_total_price' ]}"

                )

            # =========================================================

            # ИТОГОВОЕ СООБЩЕНИЕ О ПОКУПКЕ

            # =========================================================

            if bought_items:
                formatted_total_price = _fmt_amount(total_price)

                await message.reply(

                    f"<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Покупка завершена!</b>\n"
    
                    f"{chr(10).join(bought_items)}\n"
    
                    f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> <b>Общая стоимость: {formatted_total_price} кут</b>" ,

                    parse_mode="HTML" ,

                    disable_web_page_preview=True

                )

            # =========================================================

            # РЕФЕРАЛКА ДЛЯ ПОКУПКИ ЧЕРЕЗ СООБЩЕНИЕ

            # =========================================================

            try:

                refferer_id = await db.get_refferer_id(user_id)

            except Exception as e:

                print(f"[REFERRAL][MESSAGE_BUY] Ошибка получения refferer_id для {user_id}: {e}")

                refferer_id = None

            if refferer_id is not None:

                try:

                    invitetop = await db.get_invitetop(refferer_id)

                except Exception as e:

                    print(f"[REFERRAL][MESSAGE_BUY] Ошибка получения invitetop для {refferer_id}: {e}")

                    invitetop = 0

                try:

                    if invitetop is None:
                        invitetop = 0

                    try:

                        invitetop_decimal = Decimal(str(invitetop))

                    except Exception:

                        invitetop_decimal = Decimal("0")

                    if invitetop_decimal <= 0 or total_price <= 0:
                        print(

                            f"[REFERRAL][MESSAGE_BUY] invitetop={invitetop_decimal}, "
    
                            f"total_price={total_price} -> бонус не начисляем"

                        )

                        return

                    bonus_amount = Decimal(str(total_price)) * invitetop_decimal

                    try:

                        win_amount_rounded = int(round(bonus_amount - Decimal("0.5")))

                    except Exception:

                        win_amount_rounded = int(round(float(bonus_amount) - 0.5))

                    if win_amount_rounded <= 0:
                        print(

                            f"[REFERRAL][MESSAGE_BUY] Вычисленный бонус для {refferer_id} = "
    
                            f"{win_amount_rounded} -> сообщение не отправляем"

                        )

                        return

                    percentage = int(invitetop_decimal * 100)

                    # Сначала проверяем деньги в группе и списываем их

                    debit_ok = await _debit_group_balance_safe(

                        REFERRAL_SOURCE_CHAT_ID ,

                        win_amount_rounded

                    )

                    if not debit_ok:
                        print(

                            f"[REFERRAL][MESSAGE_BUY] Бонус {win_amount_rounded} для {refferer_id} НЕ выдан. "
    
                            f"Причина: в группе {REFERRAL_SOURCE_CHAT_ID} недостаточно денег "
    
                            f"или не удалось выполнить списание."

                        )

                        return

                    # Потом начисляем рефереру

                    try:

                        current_refferer_balance = _safe_int(await db.get_user_balance(refferer_id) , 0)

                        new_refferer_balance = current_refferer_balance + win_amount_rounded

                        await db.update_user_balance(refferer_id , new_refferer_balance)

                        await db.cutehistory_plus(

                            refferer_id ,

                            win_amount_rounded ,

                            "кто-то из приглашенных пользователей совершил покупку через .купить"

                        )

                        print(

                            f"[REFERRAL][MESSAGE_BUY] Пользователю {refferer_id} начислено {win_amount_rounded}. "
    
                            f"Баланс: {current_refferer_balance} -> {new_refferer_balance}"

                        )

                    except Exception as e:

                        print(

                            f"[REFERRAL][MESSAGE_BUY] Ошибка обновления баланса/истории для {refferer_id}: {e}"

                        )

                        return

                    bonus_amount_formatted = _fmt_amount(win_amount_rounded)

                    # Проверяем наличие предмета "Фигурка свободы"

                    try:

                        referrer_items = await db.get_user_items(refferer_id)

                    except Exception as e:

                        print(f"[REFERRAL][MESSAGE_BUY] Ошибка получения предметов пользователя {refferer_id}: {e}")

                        referrer_items = {}

                    has_statue = False

                    try:

                        if isinstance(referrer_items , dict):

                            has_statue = _safe_int(referrer_items.get("Фигурка свободы" , 0) , 0) > 0

                        elif isinstance(referrer_items , (list , set , tuple)):

                            has_statue = "Фигурка свободы" in referrer_items

                        else:

                            has_statue = "Фигурка свободы" in referrer_items

                    except Exception as e:

                        print(f"[REFERRAL][MESSAGE_BUY] Ошибка анализа предметов пользователя {refferer_id}: {e}")

                        has_statue = False

                    if not has_statue:

                        try:

                            await db.set_items(refferer_id , "Фигурка свободы" , 1)

                            referral_message = (

                                f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
    
                                f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
    
                                f"[{percentage}% от стоимости покупки] и фигурку свободы</b>"

                            )

                        except Exception as e:

                            print(f"[REFERRAL][MESSAGE_BUY] Ошибка при выдаче Фигурки свободы для {refferer_id}: {e}")

                            referral_message = (

                                f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
    
                                f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
    
                                f"[{percentage}% от стоимости покупки]</b>"

                            )

                    else:

                        referral_message = (

                            f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
    
                            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
    
                            f"[{percentage}% от стоимости покупки]</b>"

                        )

                    try:

                        await bot1.send_message(

                            refferer_id ,

                            referral_message ,

                            parse_mode=ParseMode.HTML ,

                            disable_web_page_preview=True

                        )

                    except Exception as e:

                        print(f"[REFERRAL][MESSAGE_BUY] Ошибка отправки сообщения рефереру {refferer_id}: {e}")


                except Exception as e:

                    print(

                        f"[REFERRAL][MESSAGE_BUY] Общая ошибка при обработке реферального бонуса "
    
                        f"для {refferer_id}: {e}"

                    )


        except (IndexError , ValueError) as e:

            print(f"⚠️ [DEBUG] Ошибка при обработке покупки через .купить: {e}")

        except Exception as e:

            print(f"⚠️ [DEBUG] Неожиданная ошибка при обработке покупки через .купить: {e}")





    elif len(words) >= 2 and words [ 0 ] == "341234123412продать":

        try:
            parts = message.text.lower().split()
            global current_user3412
            current_user3412 = message.from_user.id

            if len(parts) < 2 or len(parts) > 3:
                await message.edit_text("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> Неправильный формат")
                return

            item_index = int(parts [ 1 ])
            quantity = int(parts [ 2 ]) if len(parts) == 3 else 1

            # Обработка для "💠 CuteCoin"
            users_data = db.get_data_users()
            for user_data in users_data:
                user_id , user_balance , user_items = user_data [ 0 ] , user_data [ 1 ] , user_data [ -1 ]

                if user_id == message.from_user.id:
                    if user_items:
                        inventory = decode_items(user_items)
                        if item_index <= len(inventory):
                            item_to_sell = list(inventory.keys()) [ item_index - 1 ]
                            if item_to_sell == "💠 CuteCoin":
                                max_quantity = 500
                            elif item_to_sell == "💖 LoveCoin":
                                max_quantity = 1000
                            else:
                                max_quantity = 5

                            formatted_win_amount = "{:,.0f}".format(max_quantity).replace(',' , '.')
                            if quantity < 1 or quantity > max_quantity:
                                await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> Вы можете продать от 1 до {formatted_win_amount} предметов за раз.")
                                return

                            if inventory.get(item_to_sell , 0) >= quantity:
                                item_price = await db.get_item_price(item_to_sell)
                                price = 0.90 * item_price * quantity

                                # Сохранение данных о продаже в глобальную переменную
                                global current_sale_data
                                current_sale_data = {"user_id": user_id , "item_to_sell": item_to_sell ,
                                    "quantity": quantity , "price": price , "inventory": inventory ,
                                    "user_balance": user_balance}

                                # Создаем инлайн-кнопки
                                cancel_button = InlineKeyboardButton(text="Отмена" , callback_data="cancelsell")
                                sell_button = InlineKeyboardButton(text="Продать" , callback_data="sellitem")

                                # Создаем клавиатуру, где каждая строка кнопок представлена как вложенный список
                                markup = InlineKeyboardMarkup(inline_keyboard=[ [ cancel_button , sell_button ] ])

                                win_amount_formatted = "{:,.0f}".format(price).replace("," , ".")
                                formatted_win_amount123 = "{:,.0f}".format(quantity).replace(',' , '.')
                                sent_sell = await message.reply(
                                    f"🪄 Продажа предмета\n\n{item_to_sell} [{formatted_win_amount123} шт]\n\n💰 Итого : {win_amount_formatted} кут" ,
                                    reply_markup=markup)
                                user_sell1 [ user_id ] = sent_sell.message_id
                                print(user_sell1)
                            else:
                                await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> У вас нет такого количества предметов")
                        else:
                            await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> У вас нет предмета с таким номером")
                    else:
                        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> У вас нет предметов для продажи")
        except (IndexError , ValueError) as e:
            print(f"⚠️ Ошибка при обработке продажи: {e}")


















    elif message.text.startswith(

            ("отправить" , "Отправить" , "передать" , "Передать" , "сделка" , "Сделка" , "/ex@CuteGamingBot","/ex" ,

             "подарить" , "Подарить")):

        global current_user_id1234 , price3412 , args , user_giveitem

        user_id = message.from_user.id

        print("Начало обработки запроса на отправку предмета...")

        args = message.text.strip().split()

        quantity = 1

        price3412 = 0

        user_to_send = None

        if len(args) < 2:
            await message.reply(

                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Неправильный формат передачи предмета. Укажите эмодзи предмета.</b>" ,

                parse_mode="HTML" , disable_web_page_preview=True)

            return

        try:

            # Разделение на несколько эмодзи через запятую

            emojis = args [ 1 ].split(',')
            if len(emojis) > 5:
                await message.reply(
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Вы не можете передавать больше 5 предметов за раз.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return
            # Проверяем количество предметов и цену, если указано

            if len(args) >= 3 and args [ 2 ].isdigit():
                quantity = int(args [ 2 ])

            if len(args) == 4 and args [ 3 ].isdigit():
                price3412 = int(args [ 3 ])

            # Определяем получателя предмета

            if message.reply_to_message:
                user_to_send = message.reply_to_message.from_user

                receiver_id = user_to_send.id

                current_user_id1234 = receiver_id

            if not user_to_send:
                await message.reply(

                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Невозможно определить получателя.</b>" ,

                    parse_mode="HTML" , disable_web_page_preview=True)

                print("Ошибка: Невозможно определить получателя.")

                return

            if user_id == receiver_id:
                await message.reply(

                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Вы не можете отправить предмет самому себе.</b>" ,

                    parse_mode="HTML" , disable_web_page_preview=True)

                print("Ошибка: Пользователь пытается отправить предмет самому себе.")

                return

            sender_inventory = await db.get_user_inventory(user_id)

            items_to_send = [ ]  # Список для предметов, которые отправляются

            missing_items = [ ]  # Список для предметов, которых нет у отправителя

            # Проверяем все эмодзи из списка

            for emoji in emojis:

                emoji = emoji.strip()

                # Получаем название предмета по эмодзи

                item_to_send = await db.get_item_name_by_emoji(emoji)

                if item_to_send is None:
                    missing_items.append(f"Предмет с эмодзи '{emoji}' не найден.")

                    continue

                # Проверяем, есть ли нужное количество предметов в инвентаре отправителя

                if item_to_send not in sender_inventory or sender_inventory [ item_to_send ] < quantity:
                    item_emoji = await db.find_emoji_by_item_name(item_to_send)
                    missing_items.append(f"<b>{item_emoji} Недостаточно предметов {item_to_send}</b>")

                    continue

                # Добавляем предмет в список для отправки

                item_emoji = await db.find_emoji_by_item_name(item_to_send)

                items_to_send.append((item_to_send , item_emoji))

            if missing_items:
                asidjdjasidjas = random.choice(
                    [ "Опа, проблемка" , "Проблема с передачей" , "Ёлки палки!" , "Беда беда!" , "Не фурычит" ])

                await message.reply(

                    f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>{asidjdjasidjas}</b>\n" + "\n".join(missing_items) ,

                    parse_mode="HTML" , disable_web_page_preview=True)

                return

            # Формируем информацию о передаваемых предметах

            item_info = ""

            emojis_for_callback = [ ]

            for item_to_send , item_emoji in items_to_send:
                formatted_total_pot1241241 = "{:,.0f}".format(quantity).replace("," , ".")
                item_info += f"\n<code>{item_emoji}</code> {item_to_send} [{formatted_total_pot1241241} шт]"

                emojis_for_callback.append(item_emoji)

            # Создаем клавиатуру с кнопками



            # Используем все эмодзи в одном callback_data

            callback_data_accept = f"accept_{user_id}_{receiver_id}_{','.join(emojis_for_callback)}_{quantity}_{price3412}"

            callback_data_decline = f"decline_{user_id}_{receiver_id}_{','.join(emojis_for_callback)}_{quantity}"

            callback_data_cancel = f"cancel_{user_id}_{receiver_id}_{','.join(emojis_for_callback)}_{quantity}"

            decline_button = InlineKeyboardButton(text="Отклонить" , callback_data=callback_data_decline, style="default" ,
                icon_custom_emoji_id="4958526153955476488")
            accept_button = InlineKeyboardButton(text="Принять" , callback_data=callback_data_accept, style="default" ,
                icon_custom_emoji_id="5424998570539373838")
            cancel_button = InlineKeyboardButton(text="Отменить сделку" , callback_data=callback_data_cancel)

            # Создаем клавиатуру, где каждая строка кнопок представлена как вложенный список
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ decline_button , accept_button ] ,  # Первая строка с двумя кнопками
                    [ cancel_button ]  # Вторая строка с одной кнопкой
                ])
            currency_units = "кут" if price3412 > 0 else ""





            first_name = await db.get_name_by_user_id(user_id)
            username = await db.get_username_by_user_id(user_id)

            # Формируем ссылку на пользователя
            sender_name = await create_user_link(user_id , first_name , username)

            first_name1 = await db.get_name_by_user_id(receiver_id)
            username1 = await db.get_username_by_user_id(receiver_id)

            # Формируем ссылку на пользователя
            receiver_name = await create_user_link(receiver_id , first_name1 , username1)

            total_items_count = len(items_to_send)

            print(f"Общее количество передаваемых предметов: {total_items_count}")

            # Формируем текст о количестве предметов, если их больше 3
            formatted_total_pot = "{:,.0f}".format(total_items_count).replace("," , ".")
            items_count_text = f"\n<b><tg-emoji emoji-id='5318892863780579996'>🎩</tg-emoji> {formatted_total_pot} предметов</b>" if total_items_count > 3 else ""

            # Формируем строку с ценой
            formatted_total_pot12412411241241 = "{:,.0f}".format(price3412).replace("," , ".")
            price_text = f"\n<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> Стоимость : {formatted_total_pot12412411241241} {currency_units}" if price3412 else ''

            # Формируем и отправляем сообщение
            instruction_text = f"\n\n<tg-emoji emoji-id='5389057356493511934'>🚀</tg-emoji> <b><i>В случае, если кнопки не работают, напишите : <code>.передать {' '.join(args[1:])}</code></i></b>" if price3412 == 0 else ''

            sent_message = await message.reply(
                f"<tg-emoji emoji-id='5389057356493511934'>🚀</tg-emoji> <b>Передача предметов\n<tg-emoji emoji-id='5472178859300363509'>🏖️</tg-emoji> Для {receiver_name}\n{item_info}\n{items_count_text}{price_text}\n<tg-emoji emoji-id='5467519850576354798'>❕</tg-emoji> Получатель должен принять предмет.</b>" + instruction_text ,
                reply_markup=keyboard , parse_mode="HTML" , disable_web_page_preview=True)

            user_giveitem [ user_id ] = sent_message.message_id
            user_give [ receiver_id ] = sent_message.message_id

            print(f"Запрос на передачу предметов создан. ID сообщения: {sent_message.message_id}")


        except ValueError as e:

            print(f"Ошибка: {e}")

            await message.reply(

                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неправильный формат команды.</b>" ,

                parse_mode="HTML" , disable_web_page_preview=True)


    # Обработчик для кнопки "Принять" с указанием количества предметов и цены
    @dp.callback_query(lambda c: c.data.startswith('decline_'))
    async def process_decline_callback(callback_query: types.CallbackQuery):

        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id
        print(f"ID сообщения: {message_id}")
        data = callback_query.data.split('_')
        sender_id = int(data [ 1 ])
        receiver_id = int(data [ 2 ])

        user_id = callback_query.from_user.id

        # Проверяем, является ли нажавший кнопку - получателем
        if user_id != receiver_id:
            await callback_query.answer("💭 Только получатель может отклонить предмет.")
            return
        randommessagehelp1 = random.choice(randommessagehelp)
        print("qqsq,oqsdqqqq1")
        if user_id not in user_give or user_give [ user_id ] != message_id:
            await callback_query.answer(randommessagehelp1)
            return
        await callback_query.answer()

        try:
            # Отладка перед удалением стикера
            if user_id in usergivestickreceiver_id:
                sticker_message_id = usergivestickreceiver_id.get(user_id)
                print(f"🛠️ [DEBUG] Идентификатор сообщения со стикером: {sticker_message_id}")
                if sticker_message_id:
                    try:
                        await bot1.delete_message(
                            chat_id=callback_query.message.chat.id , message_id=sticker_message_id)
                        print(f"🛠️ [DEBUG] Сообщение со стикером удалено: {sticker_message_id}")
                    except Exception as e:
                        print(f"⚠️ [DEBUG] Ошибка при удалении сообщения со стикером: {e}")
                else:
                    print("⚠️ [DEBUG] Стикер не найден в словаре")
            else:
                print("⚠️ [DEBUG] Пользователь не найден в usergivestick")

            # Обновляем сообщение
            await callback_query.message.edit_text(
                "<tg-emoji emoji-id='5424998570539373838'>✅</tg-emoji> <b>Сделка отклонена</b>" , parse_mode="HTML" , disable_web_page_preview=True)

            # Логирование отклонённой сделки
            print(f"✖️ Сделка отклонена: {user_id}")

            # Удаляем данные
            del user_giveitem [ user_id ]  # Удаляем сообщение с покупкой из отслеживаемых
            if user_id in usergivestickreceiver_id:
                del usergivestickreceiver_id [ user_id ]  # Удаляем сообщение со стикером из отслеживаемых

        except Exception as e:
            print(f"Ошибка обработки запроса на отклонение: {e}")

    @dp.callback_query(lambda callback_query: callback_query.data.startswith('cancel_'))
    async def cancel_send_item(callback_query: types.CallbackQuery):

        try:
            user_id = callback_query.from_user.id
            message_id = callback_query.message.message_id
            print(f"ID сообщения: {message_id}")

            randommessagehelp1 = random.choice(randommessagehelp)
            if user_id not in user_giveitem or user_giveitem [ user_id ] != message_id:
                await callback_query.answer("💭 Отменить сделку может только отправитель.")
                return

            data = callback_query.data.split('_')

            if len(data) != 5:
                await callback_query.answer("⚠️ Некорректные данные в запросе.")
                print(f"Ошибка: Некорректный формат данных в callback_data: {data}")
                return

            sender_id = int(data [ 1 ])
            receiver_id = int(data [ 2 ])
            item_emoji = data [ 3 ]
            quantity = int(data [ 4 ])

            # Поиск названия предмета по эмодзи
            item_name = await db.find_item_name_by_emoji(item_emoji)
            if not item_name:
                await callback_query.answer(f"⚠️ Предмет с эмодзи '{item_emoji}' не найден.")
                print(f"Ошибка: Не удалось найти название для предмета с эмодзи '{item_emoji}'.")
                return
            await callback_query.answer()

            # Удаление стикера, если он был отправлен
            if user_id in usergivestick:
                try:
                    sticker_message_id = usergivestick [ user_id ]
                    await bot1.delete_message(chat_id=callback_query.message.chat.id , message_id=sticker_message_id)
                    print(f"🛠️ [DEBUG] Сообщение со стикером удалено: {sticker_message_id}")
                except Exception as e:
                    print(f"⚠️ [DEBUG] Ошибка при удалении сообщения со стикером: {e}")

            # Удаление сообщения с покупкой/предложением
            await callback_query.message.edit_text(
                f"<tg-emoji emoji-id='5359736160224586485'>🎁</tg-emoji> <b>Сделка отменена</b>" , parse_mode="HTML" , disable_web_page_preview=True)

            # Удаление данных об отслеживаемых сообщениях
            del user_giveitem [ user_id ]  # Удаляем сообщение с покупкой из отслеживаемых
            if user_id in usergivestick:
                del usergivestick [ user_id ]  # Удаляем сообщение со стикером из отслеживаемых

            # Уведомление об отмене
            print(f"✔️ Отправка предмета отменена: {quantity} шт {item_name} от {sender_id} к {receiver_id}")

        except Exception as e:
            print(f"Ошибка обработки запроса на отмену отправки: {e}")

    @dp.callback_query(lambda c: c.data.startswith('accept_'))
    async def process_accept_callback(callback_query: types.CallbackQuery):

        global price3412 , current_user_id1234 , sender_id , receiver_name , sender_name , args

        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id
        print(f"ID сообщения: {message_id}")

        data = callback_query.data.split('_')
        sender_id = int(data [ 1 ])
        receiver_id = int(data [ 2 ])

        if user_id != receiver_id:
            await callback_query.answer("💭 Только получатель может отклонить предмет.")
            return

        randommessagehelp1 = random.choice(randommessagehelp)
        if user_id not in user_give or user_give [ user_id ] != message_id:
            await callback_query.answer(randommessagehelp1)
            return

        if len(data) < 6:
            print(f"Ошибка: Некорректный формат данных в callback_data: {data}")
            await callback_query.answer("⚠️ Некорректные данные в запросе.")
            return

        try:
            items_data = data [ 3:-1 ]  # Обрабатываем несколько предметов
            total_price = int(data [ -1 ])  # Получаем общую цену за все предметы
        except ValueError as e:
            print(f"Ошибка при разборе данных: {e}")
            await callback_query.answer("⚠️ Ошибка при разборе данных.")
            return
        await callback_query.answer()

        print(
            f"💬 Обработка запроса на передачу:\nОтправитель: {sender_id}\nПолучатель: {receiver_id}\nПредметы: {items_data}\nЦена: {total_price}")

        # Получаем инвентарь отправителя
        sender_inventory = await db.get_user_inventory(sender_id)
        print(f"💼 Инвентарь отправителя: {sender_inventory}")

        items_to_send = [ ]
        items_info = ""
        total_items_count = 0  # Для подсчета общего количества предметов

        for i in range(0 , len(items_data) , 2):  # Каждый предмет состоит из эмодзи и количества
            item_emoji = items_data [ i ]
            item_emojis = item_emoji.split(',')  # Разделение через запятую

            for item_emoji in item_emojis:
                item_emoji = item_emoji.strip()  # Убираем лишние пробелы
                item_name = await db.find_item_name_by_emoji(item_emoji)  # Проверяем название по эмодзи

                if not item_name:
                    await callback_query.message.edit_text(
                        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предмет с эмодзи '<code>{item_emoji}</code>' не найден.</b>" ,
                        parse_mode="HTML" , disable_web_page_preview=True)
                    print(f"⚠️ Ошибка: Не удалось найти название для предмета с эмодзи '{item_emoji}'.")
                    return

                quantity = int(items_data [ i + 1 ])  # Получаем количество из следующего элемента
                items_info += f"<code>{item_emoji}</code> {item_name} [{quantity} шт]\n"

                available_quantity = sender_inventory.get(item_name , 0)
                if available_quantity < quantity:
                    await callback_query.message.edit_text(
                        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>У отправителя недостаточно предметов <code>{item_emoji}</code> {item_name}. \nТребуется : {quantity}\nДоступно : {available_quantity}</b>" ,
                        parse_mode="HTML" , disable_web_page_preview=True)
                    print(f"⚠️ Ошибка: Недостаточное количество предметов у отправителя {sender_id}.")
                    return

                items_to_send.append((item_name , quantity))
                total_items_count += quantity  # Подсчитываем общее количество предметов

        formatted_total_pot = "{:,.0f}".format(total_items_count).replace("," , ".")
        items_count_text = f"\n<b><tg-emoji emoji-id='5431420156532235514'>⚜️</tg-emoji> {formatted_total_pot} предметов</b>" if total_items_count > 3 else ""

        sender_balance = await db.get_user_balance(sender_id)
        receiver_balance = await db.get_user_balance(receiver_id)
        print(total_price)

        pricefor = total_price

        if receiver_balance >= pricefor:
            receiver_inventory = await db.get_user_inventory(receiver_id)
            for item_name , quantity in items_to_send:
                receiver_inventory [ item_name ] = receiver_inventory.get(item_name , 0) + quantity
            await db.set_user_inventory(receiver_id , receiver_inventory)

            for item_name , quantity in items_to_send:
                sender_inventory [ item_name ] -= quantity
                if sender_inventory [ item_name ] == 0:
                    del sender_inventory [ item_name ]
            await db.set_user_inventory(sender_id , sender_inventory)

            await db.update_user_balance(sender_id , sender_balance + pricefor)
            await db.update_user_balance(receiver_id , receiver_balance - pricefor)

            await db.cutehistory_plus(
                sender_id , pricefor , "передача предметов")
            await db.cutehistory_minus(
                receiver_id , pricefor , "передача предметов")

            await db.remove_zero_items(sender_id)
            await db.remove_zero_items(receiver_id)

            sender_name = await db.get_user_first_name(sender_id)
            receiver_name = await db.get_user_first_name(receiver_id)
            win_amount_formatted124 = "{:,.0f}".format(pricefor).replace("," , ".")
            first_name = await db.get_firstname_by_user_id(receiver_id)
            username = await db.get_username_by_user_id(receiver_id)

            name_link = await create_user_link(receiver_id , first_name , username)

            await callback_query.message.edit_text(
                f"<tg-emoji emoji-id='6005661956931850799'>⭐️</tg-emoji> <b>Успешная сделка\n<tg-emoji emoji-id='5318892863780579996'>🎩</tg-emoji> Для {name_link}\n\n{items_info}{items_count_text}\n{'' if total_price == 0 else f'<tg-emoji emoji-id="5375296873982604963">💰</tg-emoji> Итого : {win_amount_formatted124} кут'}</b>" ,
                parse_mode="HTML" , disable_web_page_preview=True)
            print(
                f"✔️ Успешная передача {', '.join([ f'{quantity} шт {item_name}' for item_name , quantity in items_to_send ])} от {sender_name} ({sender_id}) к {receiver_name} ({receiver_id})")
        else:

            await callback_query.message.edit_text(
                "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Недостаточно средств для покупки предметов</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print(f"⚠️ Ошибка: Недостаточно средств на счету получателя {receiver_id}.")






    #/
    if message.text.startswith(
            (".отправить" , ".Отправить" , ".передать" , ".Передать" , ".сделка" , ".Сделка" , ".подарить" ,
             ".Подарить")):

        user_id = message.from_user.id
        print("Начало обработки запроса на отправку предмета...")

        args = message.text.strip().split()
        quantity = 1
        user_to_send = None

        if len(args) < 2:
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неправильный формат передачи предмета. Укажите эмодзи предмета.</b>" ,
                parse_mode="HTML" , disable_web_page_preview=True)
            return

        try:
            # Разделение на несколько эмодзи через запятую
            emojis = args [ 1 ].split(',')
            if len(emojis) > 5:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Вы не можете передавать больше 5 предметов за раз.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            # Проверяем количество предметов, если указано
            if len(args) >= 3 and args [ 2 ].isdigit():
                quantity = int(args [ 2 ])

            # Определяем получателя предмета
            if message.reply_to_message:
                user_to_send = message.reply_to_message.from_user
                receiver_id = user_to_send.id

            if not user_to_send:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Невозможно определить получателя.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                print("Ошибка: Невозможно определить получателя.")
                return

            if user_id == receiver_id:
                await message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Вы не можете отправить предмет самому себе.</b>" , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                print("Ошибка: Пользователь пытается отправить предмет самому себе.")
                return

            sender_inventory = await db.get_user_inventory(user_id)
            items_to_send = [ ]  # Список для предметов, которые отправляются
            missing_items = [ ]  # Список для предметов, которых нет у отправителя

            # Проверяем все эмодзи из списка
            for emoji in emojis:
                emoji = emoji.strip()

                # Получаем название предмета по эмодзи
                item_to_send = await db.get_item_name_by_emoji(emoji)

                if item_to_send is None:
                    missing_items.append(f"Предмет с эмодзи '{emoji}' не найден.")
                    continue

                # Проверяем, есть ли нужное количество предметов в инвентаре отправителя
                if item_to_send not in sender_inventory or sender_inventory [ item_to_send ] < quantity:
                    item_emoji = await db.find_emoji_by_item_name(item_to_send)
                    missing_items.append(f"<b>{item_emoji} Недостаточно предметов {item_to_send}</b>")
                    continue

                # Добавляем предмет в список для отправки
                item_emoji = await db.find_emoji_by_item_name(item_to_send)
                items_to_send.append((item_to_send , item_emoji))

            if missing_items:
                asidjdjasidjas = random.choice(
                    [ "Опа, проблемка" , "Проблема с передачей" , "Ёлки палки!" , "Беда беда!" , "Не фурычит" ])
                await message.reply(
                    f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>{asidjdjasidjas}</b>\n" + "\n".join(missing_items) , parse_mode="HTML" ,
                    disable_web_page_preview=True)
                return

            # Теперь отправляем все предметы получателю
            receiver_inventory = await db.get_user_inventory(receiver_id)
            for item_name , _ in items_to_send:
                receiver_inventory [ item_name ] = receiver_inventory.get(item_name , 0) + quantity
            await db.set_user_inventory(receiver_id , receiver_inventory)

            for item_name , _ in items_to_send:
                sender_inventory [ item_name ] -= quantity
                if sender_inventory [ item_name ] == 0:
                    del sender_inventory [ item_name ]
            await db.set_user_inventory(user_id , sender_inventory)

            await db.remove_zero_items(user_id)
            await db.remove_zero_items(receiver_id)

            # Отправляем сообщение о передаче
            item_info = ""
            for item_to_send , item_emoji in items_to_send:
                formatted_total_pot = "{:,.0f}".format(quantity).replace("," , ".")
                item_info += f"\n<code>{item_emoji}</code> {item_to_send} [{formatted_total_pot} шт]"

            first_name = await db.get_name_by_user_id(receiver_id)
            username = await db.get_username_by_user_id(receiver_id)

            # Формируем ссылку на пользователя
            receiver_id_name = await create_user_link(receiver_id , first_name , username)

            await message.reply(
                f"<tg-emoji emoji-id='5389057356493511934'>🚀</tg-emoji> <b>Передача предметов\n<tg-emoji emoji-id='5472178859300363509'>🏖️</tg-emoji> Для {receiver_id_name}\n{item_info}</b>" ,
                parse_mode="HTML" , disable_web_page_preview=True)
            print("Предметы успешно отправлены.")

        except ValueError as e:
            print(f"Ошибка: {e}")
            await message.reply(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Неправильный формат команды.</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)

    if message.text.lower().startswith(('юз','использовать' , 'открыть' , 'повесить')):
        user_id = message.from_user.id
        parts = message.text.split()
        if len(parts) != 2:
            await message.reply(
                "<tg-emoji emoji-id='5282835135861892082'>❗️</tg-emoji> Неправильный формат команды. Используйте 'использовать [эмодзи предмета]'." ,
                parse_mode="HTML" , disable_web_page_preview=True)
            return

        item_emoji = parts [ 1 ]
        print(f"Команда 'использовать' для предмета с эмодзи: {item_emoji}")

        # Получаем инвентарь пользователя (нужно использовать await)
        user_inventory = await db.get_user_inventory_use(message.from_user.id)
        print(f"Инвентарь пользователя: {user_inventory}")

        # Получаем название предмета по эмодзи (нужно использовать await)
        item_name = await db.get_item_name_by_emoji_use(item_emoji)

        print(f"Название предмета для использования: {item_name}")

        # Проверка, если предмет не найден в базе данных
        if not item_name:
            await message.reply(
                "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>У вас нет этого предмета</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print("Ошибка: Предмет не найден в базе данных.")
            return

        # Проверка, есть ли предмет в инвентаре
        if item_name not in user_inventory:
            await message.reply(
                "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>У вас нет этого предмета</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print("Ошибка: Предмет отсутствует в инвентаре.")
            return

        # Получаем информацию о предмете (нужно использовать await)
        item_info = await db.get_item_info_use(item_name)
        if not item_info:
            await message.reply(
                "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Ошибка при получении данных о предмете.</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print("Ошибка: Данные о предмете отсутствуют.")
            return

        print(f"Информация о предмете: {item_info}")

        item_use = item_info [ 'use' ]
        if item_use != 1:
            await message.reply(
                "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Этот предмет нельзя использовать</b>" , parse_mode="HTML" ,
                disable_web_page_preview=True)
            print("Ошибка: Этот предмет нельзя использовать.")
            return

        # Обработка использования предмета
        second_name = item_info [ 'name1' ]
        print(f"Второе название предмета: {second_name}")
        if "Russian" in str(second_name):
            country_emoji = item_emoji  # Устанавливаем эмодзи флага как country_emoji
            await country1(user_id , message , country_emoji)
            await db.delete_user_inventory1(user_id , item_name)

        elif "case5000_15000" in str(second_name):
            await case5000_15000(db , user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)


        elif "case20000_40000" in str(second_name):
            await case20000_40000(db , user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "case50000_100000" in str(second_name):
            await case50000_100000(db , user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "meh_vor" in str(second_name):
            await meh_vor(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "Ephorin" in str(second_name):
            await Ephorin(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "Virtodin" in str(second_name):
            await Virtodin(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)
        elif "Psilophor" in str(second_name):
            await Psilophor(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "Ectazon" in str(second_name):
            await Ectazon(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "Mentalidin" in str(second_name):
            await Mentalidin(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)
        elif "Mistinglin" in str(second_name):
            await Mistinglin(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)
        elif "Cristalin" in str(second_name):
            await Cristalin(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "BonusPlus" in str(second_name):
            await BonusPlus(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "key" in str(second_name):
            await key(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)














        elif "eaglewithdrawal" in str(second_name):
            ok = await eaglewithdrawal(db , user_id , message)
            if ok:
                await db.delete_user_inventory1(user_id , item_name)
            else:
                await message.reply(
                    "⚠️ <b>Не удалось применить предмет.</b>\n"
                    "Предмет не был списан. Попробуйте ещё раз.",
                    parse_mode="HTML",
                )
        elif "ogyrchik" in str(second_name):
            await ogyrchik(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "tomato" in str(second_name):
            await tomato(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "carrot" in str(second_name):
            await carrot(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)


        elif "potato" in str(second_name):
            await potato(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "cabbage" in str(second_name):
            await cabbage(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "greenapple" in str(second_name):
            await greenapple(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "melon" in str(second_name):
            await melon(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "banana" in str(second_name):
            await banana(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "berry" in str(second_name):
            await berry(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "corn" in str(second_name):
            await corn(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "marix" in str(second_name):
            await marix(db , user_id , message)
            await db.delete_user_inventory1(user_id , item_name)





        elif "tuchka" in str(second_name):
            await tuchka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "Cute" in str(second_name):
            await Cute(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "moxito" in str(second_name):
            await moxito(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "cola" in str(second_name):
            await cola(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "wine" in str(second_name):
            await wine(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "con" in str(second_name):
            await con(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "sham" in str(second_name):
            await sham(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "beer" in str(second_name):
            await beer(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)



        elif "sigareta" in str(second_name):
            await sigareta(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "b2eer" in str(second_name):
            await b2eer(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "kon" in str(second_name):
            await kon(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "palochka" in str(second_name):
            await palochka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "edino" in str(second_name):
            await edino(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "dog" in str(second_name):
            await dog(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "cat" in str(second_name):
            await cat(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "mich" in str(second_name):
            await mich(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "hamster" in str(second_name):
            await hamster(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "rabi" in str(second_name):
            await rabi(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "lis" in str(second_name):
            await lis(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "ber" in str(second_name):
            await ber(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "whiteber" in str(second_name):
            await whiteber(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "koala" in str(second_name):
            await koala(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "tiger" in str(second_name):
            await tiger(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "lion" in str(second_name):
            await lion(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "pig" in str(second_name):
            await pig(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "kvaa" in str(second_name):
            await kvaa(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "monkey" in str(second_name):
            await monkey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "closemonkey" in str(second_name):
            await closemonkey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "openmonkey" in str(second_name):
            await openmonkey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "qwemonkey" in str(second_name):
            await qwemonkey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "osmonkey" in str(second_name):
            await osmonkey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "pin" in str(second_name):
            await pin(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "bird" in str(second_name):
            await bird(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "chip" in str(second_name):
            await chip(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "iachip" in str(second_name):
            await iachip(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "yqqwchip" in str(second_name):
            await yqqwchip(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "goose" in str(second_name):
            await goose(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "voron" in str(second_name):
            await voron(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "frymo" in str(second_name):
            await frymo(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "bzasddf" in str(second_name):
            await bzasddf(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "sdfkow" in str(second_name):
            await bzasddf(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "butterfly" in str(second_name):
            await butterfly(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "ulitka" in str(second_name):
            await ulitka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "korovka" in str(second_name):
            await korovka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "muravey" in str(second_name):
            await muravey(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "juk" in str(second_name):
            await juk(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "tarakan" in str(second_name):
            await tarakan(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "komar" in str(second_name):
            await komar(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "nechik" in str(second_name):
            await nechik(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "spider" in str(second_name):
            await spider(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "turtle" in str(second_name):
            await turtle(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "snake" in str(second_name):
            await snake(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "dragon" in str(second_name):
            await dragon(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "bluedragon" in str(second_name):
            await bluedragon(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "osminog" in str(second_name):
            await osminog(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "kalmar" in str(second_name):
            await kalmar(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "revetka" in str(second_name):
            await revetka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "omar" in str(second_name):
            await omar(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "crab" in str(second_name):
            await crab(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "fish" in str(second_name):
            await fish(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "luefish" in str(second_name):
            await luefish(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "itkit" in str(second_name):
            await itkit(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "tulen" in str(second_name):
            await tulen(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "niger" in str(second_name):
            await niger(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "opard" in str(second_name):
            await opard(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "xebra" in str(second_name):
            await xebra(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "gorila" in str(second_name):
            await gorila(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "raf" in str(second_name):
            await raf(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "ceng" in str(second_name):
            await ceng(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "buvol" in str(second_name):
            await buvol(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "ox" in str(second_name):
            await ox(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "myyyy" in str(second_name):
            await myyyy(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "big" in str(second_name):
            await big(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "ovsa" in str(second_name):
            await ovsa(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "gator" in str(second_name):
            await gator(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "taxi" in str(second_name):
            await taxi(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "police" in str(second_name):
            await police(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "chat5" in str(second_name):
            await chat5(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "nout" in str(second_name):
            await nout(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "motivation" in str(second_name):
            await motivation(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "skidka" in str(second_name):
            await skidka(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "buket" in str(second_name):
            await skidka(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "svidobrake" in str(second_name):
            await svidobrake(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "shlapa" in str(second_name):
            await shlapa(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "premium3" in str(second_name):
            await premium3(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "premium6" in str(second_name):
            await premium6(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)

        elif "slots" in str(second_name):
            await slots(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "bowling" in str(second_name):
            await bowling(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "dart" in str(second_name):
            await dart(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "foot" in str(second_name):
            await foot(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "bask" in str(second_name):
            await bask(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "gamepad" in str(second_name):
            await gamepad(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)

        elif "giveinfinity" in str(second_name):
            await giveinfinity(user_id , message)
            await db.delete_user_inventory1(user_id , item_name)


        elif "pistoletik" in str(second_name):
            await pistoletik(db , user_id , message)

        elif "hui" in str(second_name):
            await hui(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)
        elif "freebonus" in str(second_name):
            await freebonus(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)
        elif "ringtggift" in str(second_name):
            await ringtggift(user_id , message)
            #await db.delete_user_inventory1(user_id , item_name)


        else:  # Обработка других случаев, когда предмет не соответствует заранее заданным категориям
            await message.reply("<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Предмет не подходит для использования, он будет удалён.</b>" , parse_mode="HTML" ,disable_web_page_preview=True)
            print(f"Предмет '{item_name}' не относится к известным категориям. Удаляем его из инвентаря.")
            print(f"Предмет '{item_name}' удалён из инвентаря, так как не подходит для использования.")
    text_parts = message.text.split()


    if len(text_parts) == 2 and text_parts [ 0 ].lower() in ['выставить','слить']:
        item_emoji = text_parts [ 1 ]
        quantity = 1  # По умолчанию устанавливаем количество на 1

    elif len(text_parts) == 3 and text_parts [ 0 ].lower() in ['выставить','слить']:
        item_emoji = text_parts [ 1 ]
        try:
            quantity = int(text_parts [ 2 ])  # Устанавливаем количество из сообщения
            print(f"Установлено количество: {quantity}")
        except ValueError:
            await message.reply("<tg-emoji emoji-id='5988023995125993550'>🛠</tg-emoji> <b>Количество должно быть числом.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
            print("Ошибка: Количество некорректно. Введено:" , text_parts [ 2 ])
            return  # Прерываем выполнение, если количество некорректно
    else:

        return  # Прерываем выполнение, если формат неверный

    # Получаем ID пользователя
    user_id = message.from_user.id
    print(f"ID пользователя: {user_id}")

    # Получаем текущий инвентарь пользователя
    user_inventory = await db.get_user_inventory(user_id)
    print(f"Инвентарь пользователя: {user_inventory}")

    # Проверяем, что инвентарь не пустой
    if user_inventory is None or len(user_inventory) == 0:
        await message.reply("<tg-emoji emoji-id='5988023995125993550'>🛠</tg-emoji> <b>Ваш инвентарь пуст.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print("Ошибка: Инвентарь пуст.")
        return  # Прерываем выполнение, если инвентарь не найден или пуст

    # Преобразуем инвентарь в словарь (единый кодек любой формат из БД)
    user_inventory = decode_items(user_inventory)
    if not user_inventory:
        await message.reply("<b>Ошибка: Невозможно загрузить инвентарь пользователя.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print("Ошибка: Невозможно загрузить инвентарь пользователя, данные некорректны.")
        return

    # Получаем название предмета по эмодзи
    item_name = await db.get_item_name_by_emoji(item_emoji)
    print(f"Название предмета для эмодзи '{item_emoji}': {item_name}")

    if item_name is None:
        await message.reply(f"<b>Ошибка: Предмет с эмодзи '{item_emoji}' не найден.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print(f"Ошибка: Предмет с эмодзи '{item_emoji}' не найден в базе данных.")
        return  # Прерываем выполнение, если предмет не найден

    # Проверяем наличие предмета в инвентаре по названию
    if item_name not in user_inventory:
        await message.reply(f"<tg-emoji emoji-id='5988023995125993550'>🛠</tg-emoji> <b>У вас нет этого предмета в инвентаре.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print(f"Ошибка: Предмет '{item_name}' отсутствует в инвентаре.")
        return  # Прерываем выполнение, если предмет отсутствует

    # Получаем количество предметов в инвентаре
    user_item_quantity = user_inventory [ item_name ]
    print(f"Количество предметов '{item_name}' в инвентаре: {user_item_quantity}")

    # Проверяем, достаточно ли предметов для выставления
    if user_item_quantity < quantity:
        await message.reply(
            f"<b><tg-emoji emoji-id='5988023995125993550'>🛠</tg-emoji> У вас нет такого количества предметов</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print(
            f"Ошибка: Недостаточно предметов. Текущее количество: {user_item_quantity}, требуемое количество: {quantity}.")
        return  # Прерываем выполнение, если недостаточно предметов

    # Получаем цену предмета по эмодзи

    discounted_price = await db.get_discounted_price(item_emoji)

    # Если скидка существует и больше 0, используем её; иначе используем стандартную цену
    if discounted_price is not None and discounted_price > 0:
        item_price = discounted_price
        print(f"🛠️ [DEBUG] Цена за единицу {item_name} со скидкой: {item_price}")
    else:
        item_price = await db.get_price_by_emoji(item_emoji)
        print(f"🛠️ [DEBUG] Цена за единицу {item_name}: {item_price}")

    print(f"Цена предмета по эмодзи '{item_emoji}': {item_price}")

    if item_price is not None:
        # Расчёт общей стоимости
        total_price = item_price * quantity
        percentage = random.randint(25 , 45) / 100  # Генерируем процент от 25% до 45%
        final_price = total_price * percentage
        win_amount_rounded = round(final_price)
        win_amount_formatted = "{:,.0f}".format(quantity).replace("," , ".")

        # Вывод в отладку
        print(f"Цена предмета за {quantity} шт: {total_price}")
        print(f"Процент от 25% до 45%: {percentage * 100}%")
        print(f"Итоговая сумма (25-45% от полной стоимости): {final_price}")

        # Отправляем сообщение с подтверждением
        sticker_id = await db.get_item_sticker(emoji=item_emoji)

        if sticker_id:  # Если стикер найден
            try:
                print(f"🛠️ [DEBUG] Найден стикер для {item_emoji}: {sticker_id}")
                sent_stick = await message.reply_sticker(sticker_id)  # Отправляем стикер перед сообщением
                userdellstick [ user_id ] = sent_stick.message_id
            except Exception as e:
                print(f"⚠️ [DEBUG] Ошибка при отправке стикера: {e}")
                await message.reply(
                    f"<b><tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> Ошибка: некорректный идентификатор стикера для предмета {item_name}.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
                return
        else:
            print(f"⚠️ [DEBUG] Стикер для {item_emoji} не найден или некорректен.")
        confirm_message = (f"🚀 <b>Подтвердите действие для выставления предмета</b>\n"
                           f"<b><code>{item_emoji}</code> {item_name} - {win_amount_formatted} шт</b>\n"
                           ) #f"Цена: {win_amount_formatted} (25-45% от полной стоимости)"
        cancel_button = InlineKeyboardButton(text="Отменить" , callback_data="canceldell")
        confirm_button = InlineKeyboardButton(text="Выставить" , callback_data=f"confirmdell:{item_emoji}:{quantity}:{win_amount_rounded}")

        # Создаем клавиатуру, где каждая строка кнопок представлена как вложенный список
        confirm_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ cancel_button , confirm_button ]  # Одна строка с двумя кнопками
            ])
        sent_message = await message.reply(confirm_message , reply_markup=confirm_keyboard,parse_mode="HTML")
        user_dell [ user_id ] = sent_message.message_id
    else:
        await message.reply(f"<b>Ошибка: Цена предмета с эмодзи '{item_emoji}' не найдена.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
        print(f"Ошибка: Цена предмета с эмодзи '{item_emoji}' не найдена.")






























@dp.callback_query(lambda call: call.data == "canceldell")
async def cancel_action(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_dell or user_dell [ user_id ] != message_id:
        await call.answer(randommessagebonus1)
        return
    await call.answer()

    if user_id in userdellstick:
        try:
            sticker_message_id = userdellstick [ user_id ]
            await bot1.delete_message(chat_id=call.message.chat.id , message_id=sticker_message_id)
            print(f"🛠️ [DEBUG] Сообщение со стикером удалено: {sticker_message_id}")
        except Exception as e:
            print(f"⚠️ [DEBUG] Ошибка при удалении сообщения со стикером: {e}")
    await call.message.edit_text("<tg-emoji emoji-id='5424998570539373838'>✅</tg-emoji> <b>Выставление предмета было отменено.</b>", parse_mode="HTML" ,disable_web_page_preview=True)

    del user_dell [ user_id ]  # Удаляем сообщение с покупкой из отслеживаемых
    if user_id in userdellstick:
        del userdellstick [ user_id ]  # Удаляем сообщение со стикером из отслеживаемых


@dp.callback_query(lambda call: call.data.startswith("confirmdell:"))
async def confirm_action(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    # Проверка, что сообщение принадлежит пользователю
    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_dell or user_dell [ user_id ] != message_id:
        await call.answer(randommessagebonus1)
        return
    await call.answer()

    # Извлекаем данные из callback_data
    _ , item_emoji , quantity_str , final_price_str = call.data.split(":")
    quantity = int(quantity_str)  # Преобразуем количество в целое число
    final_price = float(final_price_str)  # Преобразуем финальную цену в float

    # Ваш код для выставления предмета на биржу
    item_row = await db.get_item_by_emoji34123412(item_emoji)
    if item_row:
        item_name , remains = item_row

        # Обновляем количество в remains
        await db.update_item_remains(item_emoji , quantity)  # Обновляем количество в remains
        print(f"Количество предметов '{item_name}' в remains обновлено на: {quantity}")

        # Удаляем нужное количество предметов из инвентаря пользователя
        await db.delete_user_inventory12(user_id , item_name , quantity)  # Удаляем нужное количество предметов
        print(f"Количество предметов '{item_name}' удалено из инвентаря пользователя.")

        # Получаем текущий баланс пользователя
        current_balance = await db.get_user_balance(user_id)

        # Рассчитываем новый баланс после добавления финальной суммы
        win_amount_rounded = round(final_price)
        win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")

        new_balance = current_balance + final_price

        # Обновляем баланс пользователя
        await db.update_user_balance(user_id , new_balance)
        await db.cutehistory_plus(
            user_id , final_price , "выставление предмета на биржу")
        print(f"Баланс пользователя {user_id} обновлён. Новый баланс: {new_balance}")
        win_amount_formatted1 = "{:,.0f}".format(quantity).replace("," , ".")

        # Редактируем сообщение
        await call.message.edit_text(
            f"<tg-emoji emoji-id='5424998570539373838'>✅</tg-emoji> <code>{item_emoji}</code> <b>{item_name} [{win_amount_formatted1} шт] был выставлен на биржу.</b>\n\n"
            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {win_amount_formatted} кут [20-45% от стоимости]</b>",parse_mode="HTML")
    else:
        await call.message.edit_text("<tg-emoji emoji-id='5988023995125993550'>🛠</tg-emoji> <b>Предмет не найден в базе данных.</b>", parse_mode="HTML" ,disable_web_page_preview=True)


@dp.callback_query(lambda call: call.data.startswith('apply_coupon'))
async def handle_apply_coupon(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_buy or user_buy [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()
    coupon_name = "Купон на скидку"
    # Получаем информацию о покупке
    purchase_data = current_purchase_data.get(user_id)
    if not purchase_data:
        await call.message.edit_text("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Ошибка обработки покупки.</b>")
        return
    # Получаем инвентарь пользователя
    user_inventory = decode_items(await db.get_user_inventory(user_id)) or {}
    # Проверяем наличие купона (сам купон спишем только при успешной покупке)
    coupon_quantity = int(user_inventory.get(coupon_name , 0) or 0)
    if coupon_quantity > 0:
        total_price = max(0 , int(round(float(purchase_data.get('total_price' , 0)))))
        # Если купон уже применяли на этой карточке покупки, повторно процент не «перекручиваем»
        coupon_offer = purchase_data.get("coupon_offer")
        if (
            isinstance(coupon_offer , dict)
            and coupon_offer.get("message_id") == message_id
            and 20 <= _safe_int(coupon_offer.get("discount_percent") , 0) <= 75
        ):
            discount_percent = _safe_int(coupon_offer.get("discount_percent") , 0)
            discount_price = _safe_int(coupon_offer.get("discount_total") , total_price)
        else:
            discount_percent = random.randint(20 , 75)  # от 20% до 75%
            discount_price = max(0 , int(round(total_price * (100 - discount_percent) / 100)))
        # Нормализуем значения и сохраняем
        discount_percent = max(20 , min(75 , int(discount_percent)))
        discount_price = max(0 , int(round(total_price * (100 - discount_percent) / 100)))
        purchase_data["coupon_offer"] = {
            "message_id": message_id ,
            "discount_percent": discount_percent ,
            "discount_total": discount_price
        }
        current_purchase_data[user_id] = purchase_data
        items_text = "\n".join(purchase_data.get("bought_items" , [])) or "-"
        # Создаем клавиатуру с двумя кнопками
        cancel_button = InlineKeyboardButton(text="Отменить" , callback_data="cancel341234123412")
        confirm_button = InlineKeyboardButton(
            text="Купить" , callback_data="buy_with_coupon")
        # Создаем клавиатуру с использованием вложенных списков для кнопок
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ cancel_button, confirm_button ]  # Одна строка с двумя кнопками
            ])
        await call.message.edit_text(
            f"<tg-emoji emoji-id='5377599075237502153'>🎟</tg-emoji> <b>Купон почти применён!</b>\n"
            f"{items_text}\n\n"
            f"<tg-emoji emoji-id='5377599075237502153'>🎟</tg-emoji> <b>Нажмите «Купить», чтобы завершить покупку с купоном.</b>" ,
            reply_markup=keyboard ,
            parse_mode="HTML" ,
            disable_web_page_preview=True
        )
    else:
        await call.message.edit_text("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>У вас нет купонов для применения.</b>", parse_mode="HTML" ,disable_web_page_preview=True)
@dp.callback_query(lambda call: call.data.startswith('buy_with_coupon'))
async def handle_confirm_purchase(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id
    randommessagehelp1 = random.choice(randommessagehelp)
    # защита от «чужих» кликов по этой карточке покупки
    if user_id not in user_buy or user_buy[user_id] != message_id:
        await call.answer(randommessagehelp1)
        return
    purchase_data = current_purchase_data.get(user_id)
    if not purchase_data:
        await call.answer("⚠️ Ошибка: информация о покупке не найдена")
        return
    coupon_offer = purchase_data.get("coupon_offer")
    offer_message_id = None
    offer_discount_percent = None
    offer_discount_total = None
    if isinstance(coupon_offer , dict):
        offer_message_id = _safe_int(coupon_offer.get("message_id") , 0)
        offer_discount_percent = _safe_int(coupon_offer.get("discount_percent") , 0)
        offer_discount_total = float(_safe_int(coupon_offer.get("discount_total") , 0))
    # Подтверждаем покупку только по купону, который уже применён к текущей карточке
    if offer_message_id == message_id and 20 <= offer_discount_percent <= 75:
        discount_percent = int(offer_discount_percent)
        discount_total = max(0.0 , float(offer_discount_total))
    else:
        await call.message.edit_text(
            "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Купон недействителен. Примените купон заново.</b>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
    emojis = purchase_data.get('emojis')
    quantity = purchase_data.get('quantity')
    if not emojis or quantity is None:
        await call.answer("⚠️ Ошибка: недостающие данные для обработки покупки")
        return
    await call.answer()  # снимаем «часики»
    # --- 1) Подготовка корзины: читаем остатки и цены, считаем "полную" стоимость без скидки
    prepared_items = []  # элементы: dict(emoji, name, can_buy, price)
    total_price = 0.0
    for emoji in emojis:
        try:
            item_info = await db.get_item_info_by_emoji(emoji)  # ожидаем (name, remain)
        except Exception as e:
            print(f"[BUY][WARN] get_item_info_by_emoji({emoji}) failed: {e!r}")
            item_info = None
        if not item_info:
            # такого предмета нет - просто пропускаем
            continue
        item_name, item_remain = item_info
        can_buy = max(0, min(int(quantity), int(item_remain or 0)))
        if can_buy <= 0:
            # нет в наличии - пропускаем
            continue
        try:
            item_price = await db.get_item_price(item_name)
        except Exception as e:
            print(f"[BUY][WARN] get_item_price({item_name}) failed: {e!r}")
            item_price = None
        if item_price is None:
            # цену не нашли - пропускаем
            continue
        prepared_items.append({
            "emoji": emoji,
            "name": item_name,
            "can_buy": can_buy,
            "price": float(item_price),
        })
        total_price += float(item_price) * can_buy
    # если после фильтрации нечего покупать
    if not prepared_items:
        try:
            await call.message.edit_text(
                "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предметы недоступны или закончились в наличии.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"[BUY][WARN] edit_text no items failed: {e!r}")
        return
    total_price = max(0.0 , float(total_price))
    full_total = int(round(total_price))
    discount_percent = max(20 , min(75 , int(discount_percent)))
    discount_total = float(max(0 , round(full_total * (100 - discount_percent) / 100)))
    saved_amount = max(0.0 , float(full_total) - float(discount_total))
    # --- 2) Списание средств ОДИН РАЗ (discount_total - это цена для пользователя за всю корзину)
    try:
        current_balance = await db.get_user_balance(user_id)
    except Exception as e:
        print(f"[BUY][ERR] get_user_balance failed: {e!r}")
        await call.message.reply("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Внутренняя ошибка счёта.</b>", parse_mode="HTML", disable_web_page_preview=True)
        return
    if float(current_balance) < float(discount_total):
        await call.message.reply("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Недостаточно средств</b>", parse_mode="HTML", disable_web_page_preview=True)
        return
    # списываем в «-истории» сразу всю discount_total
    new_balance = float(current_balance) - float(discount_total)
    try:
        await db.update_user_balance(user_id, new_balance)
        await db.cutehistory_minus(user_id, float(discount_total), "покупка предметов через скидочный купон")
    except Exception as e:
        print(f"[BUY][ERR] balance/cutehistory_minus failed: {e!r}")
        await call.message.reply("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Ошибка списания средств.</b>", parse_mode="HTML", disable_web_page_preview=True)
        return
    # зачисляем в баланс чёрного рынка один раз
    try:
        source_chat_id = int(getattr(call.message.chat , "id" , 0) or 0)
        market_deposit_amount = _safe_int(discount_total , 0)
        market_deposit_ok = await db.record_shop_purchase_black_market_deposit(
            bot1 ,
            user_id=user_id ,
            amount=market_deposit_amount ,
            source_chat_id=source_chat_id ,
            note="shop_buy_coupon" ,
            target_chat_id=BLACK_MARKET_GROUP_CHAT_ID ,
        )
        if not market_deposit_ok:
            raise RuntimeError("black market deposit failed")
    except Exception as e:
        print(f"[BUY][WARN] black market deposit failed: {e!r}")
        try:
            # Откатываем списание пользователя, если не смогли зачислить в рынок.
            await db.update_user_balance(user_id , current_balance)
            await db.cutehistory_plus(
                user_id ,
                float(discount_total) ,
                "возврат средств: не удалось зачислить куты на черный рынок" ,
            )
        except Exception as rollback_err:
            print(f"[BUY][CRIT] rollback after market deposit failure failed: {rollback_err!r}")
        await call.message.reply(
            "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> "
            "<b>Покупка отменена: не удалось зачислить куты на чёрный рынок. Средства возвращены.</b>" ,
            parse_mode="HTML" ,
            disable_web_page_preview=True ,
        )
        return
    # --- 3) Проведение покупки по предметам
    bought_items_lines = []
    for it in prepared_items:
        emoji = it["emoji"]
        item_name = it["name"]
        can_buy = it["can_buy"]
        item_price = it["price"]
        # уменьшаем остаток на бирже и добавляем в инвентарь
        try:
            await db.set_items(user_id, item_name, can_buy)         # пользователю
            await db.buy_item(item_name, can_buy)                   # со склада/биржи
        except Exception as e:
            print(f"[BUY][WARN] stock/inventory update failed for {item_name}: {e!r}")
            # продолжаем другие позиции
        # спец-логика для CuteCoin
        if item_name == "💠 CuteCoin":
            try:
                await db.update_user_cutecoin_balance(user_id, can_buy)
            except Exception as e:
                print(f"[BUY][WARN] update_user_cutecoin_balance failed: {e!r}")
        bought_items_lines.append(
            f"<code>{emoji}</code> {item_name} [{str(can_buy).replace(',', '.')} шт]"
        )
    # удаляем купон, если он был
    try:
        await db.delete_user_inventory1(user_id, "Купон на скидку")
    except Exception as e:
        print(f"[BUY][WARN] delete coupon failed: {e!r}")
    # очищаем оффер купона после попытки покупки
    try:
        if isinstance(purchase_data , dict):
            purchase_data.pop("coupon_offer" , None)
            current_purchase_data[user_id] = purchase_data
    except Exception as e:
        print(f"[BUY][WARN] clear coupon_offer failed: {e!r}")
    # фиксируем пользователю «успешную покупку»
    try:
        full_amount_formatted = _fmt_amount(full_total)
        win_amount_formatted = _fmt_amount(discount_total)
        saved_amount_formatted = _fmt_amount(saved_amount)
        items_list = "\n".join(bought_items_lines) if bought_items_lines else "-"
        await call.message.edit_text(
            f"<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Успешная покупка!</b>\n"
            f"{items_list}\n\n"
            f"<tg-emoji emoji-id='5377599075237502153'>🎟</tg-emoji> <b>Экономия : {saved_amount_formatted} кут</b>\n"
            f"<tg-emoji emoji-id='4967518033061872209'>💳</tg-emoji> <b>Было : {full_amount_formatted} кут</b>\n"
            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>К оплате : {win_amount_formatted} кут</b>" ,
            parse_mode="HTML" ,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[BUY][WARN] edit_text result failed: {e!r}")
    # --- 4) Реферальное вознаграждение
    # бонус считаем от полной цены без скидки (total_price), 25%, округляем
    try:
        refferer_id = await db.get_refferer_id(user_id)
    except Exception as e:
        print(f"[BUY][WARN] get_refferer_id failed: {e!r}")
        refferer_id = None
    if refferer_id is not None and refferer_id != user_id:
        try:
            bonus_amount = max(0.0, float(total_price) * 0.25)
            win_amount_rounded = int(round(bonus_amount))
            # если бонус = 0 - НИЧЕГО НЕ ДЕЛАЕМ и НИЧЕГО НЕ ПИШЕМ
            if win_amount_rounded > 0:
                # начисляем куты рефереру
                try:
                    current_ref_balance = await db.get_user_balance(refferer_id)
                    new_ref_balance = float(current_ref_balance) + win_amount_rounded
                    await db.update_user_balance(refferer_id, new_ref_balance)
                    await db.cutehistory_plus(
                        refferer_id, win_amount_rounded,
                        "кто-то из приглашённых пользователей сделал покупку в магазине"
                    )
                except Exception as e:
                    print(f"[BUY][ERR] referral balance update failed: {e!r}")
                # фигурка свободы - только если нет
                add_figurine = False
                try:
                    ref_items = await db.get_user_items(refferer_id) or {}
                    if "Фигурка свободы" not in ref_items:
                        await db.set_items(refferer_id, "Фигурка свободы", 1)
                        add_figurine = True
                except Exception as e:
                    print(f"[BUY][WARN] set figurine failed: {e!r}")
                # сообщение рефереру
                try:
                    bonus_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace(",", ".")
                    if add_figurine:
                        msg = f"<tg-emoji emoji-id='5193209274452425995'>🎉</tg-emoji> <b>Кто-то из приглашённых пользователей совершил покупку в магазине, вы получили {bonus_amount_formatted} кут и фигурку свободы</b>"
                    else:
                        msg = f"<tg-emoji emoji-id='5193209274452425995'>🎉</tg-emoji> <b>Кто-то из приглашённых пользователей совершил покупку в магазине, вы получили {bonus_amount_formatted} кут</b>"
                    await bot1.send_message(refferer_id, msg, parse_mode="HTML", disable_web_page_preview=True)
                except Exception as e:
                    print(f"[BUY][WARN] notify referrer failed: {e!r}")
            else:
                # лог для диагностики, но без сообщений пользователю
                print(f"[BUY][REF] bonus rounded to 0 (total_price={total_price}) - skip notify")
        except Exception as e:
            print(f"[BUY][WARN] referral block failed: {e!r}")
    else:
        # нет реферера или он совпадает с покупателем
        if refferer_id == user_id:
            print("[BUY][REF] refferer_id == user_id → skip referral")

















#asdqsd1


@dp.callback_query(lambda c: c.data == 'buy341234123412')
async def process_buy_callback(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        message_id = callback_query.message.message_id

        # Проверяем соответствие текущего сообщения и пользователя
        if user_id not in user_buy or user_buy[user_id] != message_id:
            await callback_query.answer(random.choice(randommessagehelp))
            return

        purchase_data = current_purchase_data.get(user_id)
        if purchase_data is None:
            await callback_query.answer("Ошибка: информация о покупке не найдена")
            return

        emojis = purchase_data.get("emojis")
        quantity = _safe_int(purchase_data.get("quantity"), 0)
        discount_price = _safe_int(purchase_data.get("discount_price", 0), 0)

        if not emojis or quantity <= 0:
            await callback_query.answer("Ошибка: недостающие данные для обработки покупки")
            return

        await callback_query.answer()

        bought_items = []
        total_price = 0

        # =========================================================
        # ПОКУПКА КАЖДОГО ПРЕДМЕТА
        # =========================================================
        for emoji in emojis:
            try:
                item_info = await db.get_item_info_by_emoji(emoji)
            except Exception as e:
                print(f"[BUY] Ошибка получения информации по предмету {emoji}: {e}")
                item_info = None

            if not item_info:
                await callback_query.message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предмета нет в наличии</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                continue

            try:
                item_name, item_remain = item_info
            except Exception:
                print(f"[BUY] Некорректный формат item_info для {emoji}: {item_info}")
                continue

            item_remain = _safe_int(item_remain, 0)
            bought_quantity = min(quantity, item_remain)

            if bought_quantity <= 0:
                await callback_query.message.edit_text(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Предмета нет в наличии</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                print(
                    f"[BUY] Количество предмета '{item_name}' равно 0, "
                    f"поэтому он не добавляется в инвентарь."
                )
                continue

            # Получаем цену
            try:
                discounted_price_for_item = await db.get_discounted_price(emoji)
            except Exception as e:
                print(f"[BUY] Ошибка получения скидочной цены для {emoji}: {e}")
                discounted_price_for_item = None

            if discounted_price_for_item is not None and _safe_int(discounted_price_for_item, 0) > 0:
                item_price = _safe_int(discounted_price_for_item, 0)
                print(f"🛠️ [DEBUG] Цена за единицу {item_name} со скидкой: {item_price}")
            else:
                try:
                    raw_item_price = await db.get_item_price(item_name)
                except Exception as e:
                    print(f"[BUY] Ошибка получения обычной цены для {item_name}: {e}")
                    raw_item_price = None

                item_price = _safe_int(raw_item_price, 0)
                print(f"🛠️ [DEBUG] Цена за единицу {item_name}: {item_price}")

            if item_price <= 0:
                print(f"⚠️ Цена предмета '{item_name}' не найдена или некорректна.")
                return

            item_total_price = bought_quantity * item_price

            try:
                current_balance = _safe_int(await db.get_user_balance(user_id), 0)
            except Exception as e:
                print(f"[BUY] Ошибка получения баланса пользователя {user_id}: {e}")
                return

            if current_balance < item_total_price:
                await callback_query.message.reply(
                    "<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>Недостаточно средств</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return

            new_balance = current_balance - item_total_price

            # Списание у пользователя / зачисление в чёрный рынок / выдача предмета
            market_deposit_ok = False
            try:
                source_chat_id = int(getattr(callback_query.message.chat , "id" , 0) or 0)
                market_deposit_ok = await db.record_shop_purchase_black_market_deposit(
                    bot1 ,
                    user_id=user_id ,
                    amount=item_total_price ,
                    source_chat_id=source_chat_id ,
                    note="shop_buy_callback" ,
                    target_chat_id=BLACK_MARKET_GROUP_CHAT_ID ,
                )
                if not market_deposit_ok:
                    raise RuntimeError("black market deposit failed")
                await db.update_user_balance(user_id, new_balance)
                await db.cutehistory_minus(user_id, item_total_price, "покупка предмета")
                await db.set_items(user_id, item_name, bought_quantity)
                await db.buy_item(item_name, bought_quantity)
            except Exception as e:
                if market_deposit_ok:
                    try:
                        await db.update_chat_balance(bot1 , BLACK_MARKET_GROUP_CHAT_ID , -item_total_price)
                    except Exception as rollback_err:
                        print(f"[BUY][ROLLBACK] Не удалось откатить рынок: {rollback_err}")
                try:
                    await db.update_user_balance(user_id , current_balance)
                except Exception as rollback_err:
                    print(f"[BUY][ROLLBACK] Не удалось откатить баланс пользователя: {rollback_err}")
                print(
                    f"[BUY] Ошибка финансового/инвентарного обновления "
                    f"для пользователя {user_id}, item={item_name}: {e}"
                )
                return

            if item_name == "💠 CuteCoin":
                try:
                    result = db.update_user_cutecoin_balance(user_id, bought_quantity)
                    await _maybe_await(result)
                except Exception as e:
                    print(f"[BUY][CUTECOIN] Ошибка обновления CuteCoin баланса: {e}")

            total_price += item_total_price

            formatted_bought_quantity = _fmt_amount(bought_quantity)
            bought_items.append(f"<code>{emoji}</code> {item_name} [{formatted_bought_quantity} шт]")

            print(
                f"[BUY] Пользователь {user_id} приобрел {bought_quantity} шт. {item_name} "
                f"за {item_price} кутов каждый. Общая цена: {item_total_price}"
            )

        # =========================================================
        # ОБНОВЛЕНИЕ ТЕКСТА ПОКУПКИ
        # =========================================================
        if bought_items:
            shown_total = discount_price if discount_price > 0 else total_price
            win_amount_formatted = _fmt_amount(shown_total)
            items_list = "\n".join(bought_items)

            await callback_query.message.edit_text(
                f"<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Успешная покупка!\n{items_list}\n<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> {win_amount_formatted}</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # =========================================================
        # РЕФЕРАЛКА
        # =========================================================
        try:
            refferer_id = await db.get_refferer_id(user_id)
        except Exception as e:
            print(f"[REFERRAL] Ошибка получения refferer_id для {user_id}: {e}")
            refferer_id = None

        if refferer_id is not None:
            try:
                invitetop = await db.get_invitetop(refferer_id)
            except Exception as e:
                print(f"[REFERRAL] Ошибка получения invitetop для {refferer_id}: {e}")
                invitetop = 0

            try:
                if invitetop is None:
                    invitetop = 0

                try:
                    invitetop_decimal = Decimal(str(invitetop))
                except Exception:
                    invitetop_decimal = Decimal("0")

                if invitetop_decimal <= 0 or total_price <= 0:
                    print(
                        f"[REFERRAL] invitetop={invitetop_decimal}, total_price={total_price} "
                        f"-> бонус не начисляем"
                    )
                    return

                bonus_amount = Decimal(str(total_price)) * invitetop_decimal

                # Округление по твоему старому принципу
                try:
                    win_amount_rounded = int(round(bonus_amount - Decimal("0.5")))
                except Exception:
                    win_amount_rounded = int(round(float(bonus_amount) - 0.5))

                if win_amount_rounded <= 0:
                    print(
                        f"[REFERRAL] Вычисленный бонус для {refferer_id} = "
                        f"{win_amount_rounded} -> сообщение не отправляем"
                    )
                    return

                percentage = int(invitetop_decimal * 100)

                # =================================================
                # СНАЧАЛА ПРОВЕРЯЕМ ДЕНЬГИ В ГРУППЕ И СПИСЫВАЕМ ИХ
                # =================================================
                debit_ok = await _debit_group_balance_safe(
                    REFERRAL_SOURCE_CHAT_ID,
                    win_amount_rounded
                )

                if not debit_ok:
                    print(
                        f"[REFERRAL] Бонус {win_amount_rounded} для {refferer_id} НЕ выдан. "
                        f"Причина: в группе {REFERRAL_SOURCE_CHAT_ID} "
                        f"недостаточно денег или не удалось выполнить списание."
                    )
                    return

                # =================================================
                # ТОЛЬКО ПОСЛЕ ЭТОГО НАЧИСЛЯЕМ РЕФЕРЕРУ
                # =================================================
                try:
                    current_refferer_balance = _safe_int(await db.get_user_balance(refferer_id), 0)
                    new_refferer_balance = current_refferer_balance + win_amount_rounded

                    await db.update_user_balance(refferer_id, new_refferer_balance)
                    await db.cutehistory_plus(
                        refferer_id,
                        win_amount_rounded,
                        "кто-то из приглашенных пользователей совершил покупку"
                    )

                    print(
                        f"[REFERRAL] Пользователю {refferer_id} начислено {win_amount_rounded}. "
                        f"Баланс: {current_refferer_balance} -> {new_refferer_balance}"
                    )
                except Exception as e:
                    print(
                        f"[REFERRAL] Ошибка обновления баланса/истории для {refferer_id}: {e}"
                    )
                    return

                bonus_amount_formatted = _fmt_amount(win_amount_rounded)

                # Проверяем наличие предмета "Фигурка свободы"
                try:
                    referrer_items = await db.get_user_items(refferer_id)
                except Exception as e:
                    print(f"[REFERRAL] Ошибка получения предметов пользователя {refferer_id}: {e}")
                    referrer_items = {}

                has_statue = False
                try:
                    if isinstance(referrer_items, dict):
                        has_statue = _safe_int(referrer_items.get("Фигурка свободы", 0), 0) > 0
                    elif isinstance(referrer_items, (list, set, tuple)):
                        has_statue = "Фигурка свободы" in referrer_items
                    else:
                        has_statue = "Фигурка свободы" in referrer_items
                except Exception as e:
                    print(f"[REFERRAL] Ошибка анализа предметов пользователя {refferer_id}: {e}")
                    has_statue = False

                if not has_statue:
                    try:
                        await db.set_items(refferer_id, "Фигурка свободы", 1)
                        message = (
                            f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
                            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
                            f"[{percentage}% от стоимости покупки] и фигурку свободы</b>"
                        )
                    except Exception as e:
                        print(f"[REFERRAL] Ошибка при выдаче Фигурки свободы для {refferer_id}: {e}")
                        message = (
                            f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
                            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
                            f"[{percentage}% от стоимости покупки]</b>"
                        )
                else:
                    message = (
                        f"<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji> <b>Кто-то из приглашенных пользователей совершил покупку в магазине</b>\n"
                        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Вы получили {bonus_amount_formatted} кут "
                        f"[{percentage}% от стоимости покупки]</b>"
                    )

                try:
                    await bot1.send_message(
                        refferer_id,
                        message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"[REFERRAL] Ошибка отправки сообщения рефереру {refferer_id}: {e}")

            except Exception as e:
                print(
                    f"[REFERRAL] Общая ошибка при обработке реферального бонуса "
                    f"для {refferer_id}: {e}"
                )

    except (IndexError, ValueError) as e:
        print(f"⚠️ Ошибка при обработке покупки: {e}")
    except Exception as e:
        print(f"⚠️ Неожиданная ошибка при обработке покупки: {e}")




@dp.callback_query(lambda c: c.data == 'sellitem')
async def process_sell_callback(callback_query: types.CallbackQuery):

    global current_sale_data

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_sell1 or user_sell1[user_id] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer()

    data = current_sale_data
    if not data:
        await callback_query.message.edit_text("<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> <b>данные о продаже не найдены.</b>")
        return

    user_id = data['user_id']
    item_to_sell = data['item_to_sell']
    quantity = data['quantity']
    price = data['price']
    inventory = data['inventory']
    user_balance = data['user_balance']

    inventory[item_to_sell] -= quantity
    if inventory[item_to_sell] == 0:
        del inventory[item_to_sell]
    await db.increase_item_quantity(item_to_sell, quantity)
    new_balance = user_balance + price
    await db.update_user_balance(user_id, new_balance)
    await db.cutehistory_plus(
        user_id , price , "старая система продажи предметов")
    await db.set_user_items(user_id, inventory)

    # Специальная обработка для "💠 CuteCoin"
    if item_to_sell == "💠 CuteCoin":
        db.update_user_cutecoin_balance(user_id, -quantity)

    formatted_win_amount = "{:,.0f}".format(quantity).replace(',' , '.')

    items_list = f"{item_to_sell} [ {formatted_win_amount} шт ]"
    win_amount_formatted = "{:,.0f}".format(price).replace(",", ".")


    await callback_query.message.edit_text(f"<b><tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> Успешная продажа\n\n{items_list}\n\n<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> Итого : {win_amount_formatted} кут</b>")

    current_sale_data = {}  # Сбрасываем данные после завершения продажи

@dp.callback_query(lambda c: c.data == 'cancel341234123412')
async def process_cancel_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_buy or user_buy[user_id] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    # Удаляем сообщение со стикером, если оно было отправлено
    if user_id in userbuystick:
        try:
            sticker_message_id = userbuystick[user_id]
            await bot1.delete_message(chat_id=callback_query.message.chat.id, message_id=sticker_message_id)
            print(f"🛠️ [DEBUG] Сообщение со стикером удалено: {sticker_message_id}")
        except Exception as e:
            print(f"⚠️ [DEBUG] Ошибка при удалении сообщения со стикером: {e}")

    # Удаляем сообщение с покупкой
    await callback_query.answer('✅ Сообщение с покупкой удалено')
    await callback_query.message.delete()

    # Очищаем данные после отмены
    current_sale_data = {}
    del user_buy[user_id]  # Удаляем сообщение с покупкой из отслеживаемых
    if user_id in userbuystick:
        del userbuystick[user_id]  # Удаляем сообщение со стикером из отслеживаемых


@dp.callback_query(lambda c: c.data == 'cancelsell')
async def process_cancel_callback(callback_query: types.CallbackQuery):

    global current_sale_data

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_sell1 or user_sell1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    current_sale_data = {}
    await callback_query.answer('Сообщение с продажей удалено')# Сбрасываем данные при отмене
    await callback_query.message.delete()



@dp.callback_query(lambda c: c.data == 'close_inventory')
async def close_inventory(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await callback_query.message.delete()





@dp.callback_query(lambda c: c.data and c.data.startswith('inv_page_'))
async def process_inventory_pagination(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_inventory1 or user_inventory1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return
    await callback_query.answer()
    page = int(callback_query.data.split('_') [ 2 ])
    user_id = callback_query.from_user.id

    inventory_items = await db.get_user_inventory(user_id)
    if not inventory_items:
        await callback_query.message.edit_text(
            "<tg-emoji emoji-id='5837137271416950239'>🏝</tg-emoji> <b>Инвентарь пуст</b>" ,
            parse_mode="HTML")
        return

    total_pages = inventory_total_pages(len(inventory_items))
    page = max(0 , min(page , total_pages - 1))

    inventory_list = await generate_inventory_page(inventory_items , page)
    navigation_buttons = get_inventory_navigation_buttons(page , total_pages)

    closeinventory1 = types.InlineKeyboardButton(
        text=" " , callback_data="close_message_inventory" , style="default" ,
        icon_custom_emoji_id="5226660202035554522")

    keyboard_rows = []
    if navigation_buttons:
        keyboard_rows.append(navigation_buttons)
    keyboard_rows.append([ closeinventory1 ])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback_query.message.edit_text(
        text=f'<tg-emoji emoji-id="5319122988128299716">🎩</tg-emoji> <b>Инвентарь</b>\n\n{inventory_list}' ,
        parse_mode="HTML" , reply_markup=keyboard)




# Обработчик кнопки "Купить"





@dp.callback_query(lambda c: c.data == 'close_message_inventory')
async def process_buy_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)
    if user_id not in user_inventory1 or user_inventory1 [ user_id ] != message_id:
        await callback_query.answer(randommessagehelp1)
        return

    await callback_query.answer('сообщение с инвентарем удалено')
    await callback_query.message.delete()


@dp.callback_query(lambda c: c.data == 'store_close_message')
async def process_close_store(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    msg_id = callback.message.message_id
    debug_print(f"❌ Закрытие магазина (store_close_message): user={user_id}, msg_id={msg_id}")
    try:
        # Проверяем, что сообщение принадлежит активному магазину
        if user_shop_messages.get(user_id) != msg_id:
            debug_print("⛔ Игнорируем, сообщение не магазин")
            await callback.answer(random.choice(RANDOM_HELP), show_alert=True)
            return

        await callback.answer('Сообщение с магазином удалено')
        chat_id = callback.message.chat.id
        await callback.message.delete()
        debug_print("🗑️ Сообщение удалено")

        # Отправляем стикер (как в старом обработчике)
        sticker_id = "CAACAgIAAxkBAzsOFGo0URpw6VHeFJ0cV7uIWEXerD59AALNAAOYv4ANUzcwURozRpk8BA"
        try:
            await callback.bot.send_sticker(chat_id, sticker_id)
        except Exception as e:
            debug_print(f"⚠️ Не удалось отправить стикер: {e}")

    except TelegramAPIError as e:
        debug_print(f"⚠️ Ошибка удаления: {e}")
    except Exception as e:
        debug_print(f"💥 Ошибка: {type(e).__name__}: {e}")
    finally:
        # Очищаем все состояния, связанные с магазином
        user_shop_messages.pop(user_id, None)
        active_filter.pop(msg_id, None)
        nav_cooldowns.pop(user_id, None)
        filter_cooldowns.pop(user_id, None)
        debug_print("🧹 Состояния очищены")




# ============================================================
# ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ КОЛБЭКОВ (регистрируются один раз)
# ============================================================
@dp.callback_query(lambda c: c.data == "reset_sorting")
async def reset_filter_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    msg_id = callback.message.message_id
    debug_print(f"🔄 reset_sorting от user={user_id}, msg_id={msg_id}, сохранённое: {user_shop_messages.get(user_id)}")
    try:
        if user_shop_messages.get(user_id) != msg_id:
            debug_print("⛔ Сообщение не совпадает")
            await callback.answer(random.choice(RANDOM_HELP), show_alert=True)
            return
        await callback.answer()
        active_filter[msg_id] = None
        debug_print(f"✅ Сброс фильтра")
        items = await get_available_items()
        debug_print(f"📦 После сброса доступно: {len(items)}")
        catalog, total_pages = await generate_catalog_page(items, 0)
        markup = await build_shop_markup(0, total_pages, "page")
        try:
            await callback.message.edit_text(
                catalog, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
            )
            debug_print("✏️ Сообщение обновлено (сброс)")
        except TelegramAPIError as e:
            if "message is not modified" not in str(e).lower():
                debug_print(f"❌ Ошибка редактирования: {e}")
                raise
            debug_print("⚠️ Сообщение не изменилось")
    except Exception as e:
        debug_print(f"💥 КРИТИЧЕСКАЯ ОШИБКА в reset: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

@dp.callback_query(lambda c: c.data.startswith("filter_by_sorting_"))
async def apply_filter_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    msg_id = callback.message.message_id
    symbol = callback.data[len("filter_by_sorting_"):]
    debug_print(f"🔍 Фильтр по '{symbol}' от user={user_id}, msg_id={msg_id}")
    try:
        if user_shop_messages.get(user_id) != msg_id:
            debug_print("⛔ Сообщение не актуально")
            await callback.answer(random.choice(RANDOM_HELP), show_alert=True)
            return
        now = time.time()
        last = filter_cooldowns.get(user_id, 0)
        if now - last < ANTISPAM_FILTER:
            debug_print(f"⏱️ Антиспам фильтра: {now - last:.2f} сек")
            await callback.answer("⏳ Подождите немного", show_alert=True)
            return
        filter_cooldowns[user_id] = now
        await callback.answer()
        debug_print("⏳ Загрузка отфильтрованных предметов...")
        items = await get_available_items(filter_symbol=symbol)
        debug_print(f"📦 Найдено предметов: {len(items)}")
        if not items:
            debug_print("🈳 Товаров нет, заглушка")
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=" ", callback_data="reset_sorting",
                    icon_custom_emoji_id="5260426225599405269"
                )],
                [InlineKeyboardButton(
                    text=" ", callback_data="store_close_message",
                    icon_custom_emoji_id="5226660202035554522"
                )]
            ])
            no_text = random.choice([
                "🕊 Похоже, предметов нет в наличии",
                "🌿 Извините, товар отсутствует",
                "🔓 Нет в наличии",
                "🙂 К сожалению, товар закончился",
                "🌸 Предметы в данный момент недоступны",
                "🪴 Товара нет в наличии",
                "🌙 Предметы распроданы",
                "🍃 К сожалению, товар отсутствует"
            ])
            try:
                await callback.message.edit_text(
                    f"<b>{no_text}</b>", parse_mode="HTML", reply_markup=markup
                )
                debug_print("✏️ Заглушка показана")
            except TelegramAPIError as e:
                if "message is not modified" not in str(e).lower():
                    debug_print(f"❌ Ошибка: {e}")
                    raise
            active_filter[msg_id] = symbol
            return
        catalog, total_pages = await generate_catalog_page(items, 0)
        markup = await build_shop_markup(0, total_pages, "filter_page")
        try:
            await callback.message.edit_text(
                catalog, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
            )
            debug_print(f"✏️ Каталог обновлён, страница 0/{total_pages}")
        except TelegramAPIError as e:
            if "message is not modified" not in str(e).lower():
                debug_print(f"❌ Ошибка: {e}")
                raise
            debug_print("⚠️ Сообщение не изменилось")
        active_filter[msg_id] = symbol
    except Exception as e:
        debug_print(f"💥 КРИТИЧЕСКАЯ ОШИБКА в filter: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

@dp.callback_query(lambda c: c.data.startswith(("page_", "filter_page_")))
async def paginate_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    msg_id = callback.message.message_id
    data = callback.data
    debug_print(f"📄 Пагинация: data={data}, user={user_id}, msg_id={msg_id}")
    try:
        if user_shop_messages.get(user_id) != msg_id:
            debug_print("⛔ Сообщение не актуально")
            await callback.answer(random.choice(RANDOM_HELP), show_alert=True)
            return
        now = time.time()
        last = nav_cooldowns.get(user_id, 0)
        if now - last < ANTISPAM_NAV:
            debug_print(f"⏱️ Антиспам навигации: {now - last:.2f} сек")
            await callback.answer(
                random.choice(["⏳ Не спешите", "🕰️ Терпение", "🐢 Медленно, но верно"]),
                show_alert=True
            )
            return
        nav_cooldowns[user_id] = now
        await callback.answer()
        if data.startswith("filter_page_"):
            prefix = "filter_page"
            page = int(data[len("filter_page_"):])
            symbol = active_filter.get(msg_id)
            debug_print(f"🔍 Активный фильтр: {symbol}")
            items = await get_available_items(filter_symbol=symbol) if symbol else []
        else:
            prefix = "page"
            page = int(data[len("page_"):])
            items = await get_available_items()
        debug_print(f"📦 Предметов: {len(items)}, целевая страница: {page}")
        if not items:
            debug_print("🈳 Каталог пуст")
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=" ", callback_data="reset_sorting",
                    icon_custom_emoji_id="5454409660473827001"
                )],
                [InlineKeyboardButton(
                    text=" ", callback_data="store_close_message",
                    icon_custom_emoji_id="5226660202035554522"
                )]
            ])
            try:
                await callback.message.edit_text(
                    "<b>Каталог пуст</b>", parse_mode="HTML", reply_markup=markup
                )
                debug_print("✏️ Заглушка 'Каталог пуст'")
            except TelegramAPIError as e:
                if "message is not modified" not in str(e).lower():
                    debug_print(f"❌ Ошибка: {e}")
                    raise
            return
        catalog, total_pages = await generate_catalog_page(items, page)
        markup = await build_shop_markup(page, total_pages, prefix)
        try:
            await callback.message.edit_text(
                catalog, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
            )
            debug_print(f"✏️ Страница {page}/{total_pages} обновлена")
        except TelegramAPIError as e:
            if "message is not modified" not in str(e).lower():
                debug_print(f"❌ Ошибка: {e}")
                raise
            debug_print("⚠️ Сообщение не изменилось")
    except Exception as e:
        debug_print(f"💥 КРИТИЧЕСКАЯ ОШИБКА в paginate: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()



@dp.callback_query(lambda c: c.data == "page_info")
async def page_info_handler(callback: CallbackQuery):
    await callback.answer("Информационная кнопка")  # просто скрываем "часики", ничего не делаем


# ---------------------------------------------------------------------------
# Публичные алиасы для ButtonRegistry (main.py) и IDE/статического анализа.
# Логика в обработчиках выше; здесь только стабильные имена экспорта.
# ---------------------------------------------------------------------------
shop_reset_sorting = reset_filter_handler
shop_filter_by_sorting = apply_filter_handler
shop_process_pagination = paginate_handler
shop_process_filter_pagination = paginate_handler