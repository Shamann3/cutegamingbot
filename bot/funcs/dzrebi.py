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

from aiogram.types import CallbackQuery



from bot.funcs.func import *

gamesdzrebi = {}

gamenumdzrebi = []# Словарь для хранения информации об играх


@dp.message()
async def dzrebi(message: Message):
    parts = message.text.split()
    if len(parts) == 2 and parts[0].lower() in ["жребий34123412", "жребии34123412", "жреби34123412"]:
        try:
            bet_str = parts[1].replace(',', '').replace('.', '')
            if not bet_str.isdigit():
                raise ValueError("Некорректная ставка")

            bet = int(bet_str)
            if bet <= 0:
                await message.reply("🚫 Ставка должна быть больше 0")
                return
        except ValueError:
            print("Ошибка: некорректная ставка")
            return

        creator_id = message.from_user.id

        # Здесь должна быть проверка баланса (замените на фактическую логику проверки баланса)
        creator_balance = 1000  # Пример проверки баланса

        if creator_balance < bet:
            from bot.funcs.help import callbaYTRWEQck_main
            button = InlineKeyboardButton(text=f"Как заработать кут?" , callback_data="9help_btn22")

            multiplier = donate_bet
            result = bet * multiplier
            bet_amount_str = str(int(result)) if isinstance(result , float) and result.is_integer() else str(result)
            bet_amount_win_formated = "{:,.0f}".format(bet).replace("," , ".")
            bot_username = await get_bot_username_by_token(TOKEN)
            user_id = message.from_user.id
            pending_context [ user_id ] = {"stars_amount": bet_amount_str , "sent": False}
            button1 = InlineKeyboardButton(
                text=f"💫 Купить {bet_amount_win_formated} кут 💰" , url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button1 ] , [ button ] ])

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>" , reply_markup=keyboard , parse_mode="HTML" ,
                disable_web_page_preview=True)
            await asyncio.sleep(timeoutdonate)

            if user_id in pending_context and not pending_context [ user_id ] [ "sent" ]:
                stars_amount = pending_context [ user_id ] [ "stars_amount" ]
                invoice_message = await send_invoice_to_user(message , stars_amount)

                # сохраним id сообщения
                pending_context [ user_id ] [ "manual_message_id" ] = invoice_message.message_id
            return

        game_id = message.message_id  # Используем message_id как уникальный идентификатор игры

        gamesdzrebi[game_id] = {"creator": creator_id, "bet": bet, "participants": [creator_id]}

        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Присоединиться", callback_data=f"joindzrebi:{game_id}"),
            InlineKeyboardButton("Начать игру", callback_data=f"startdzrebi:{game_id}")
        )

        await message.reply(
            f"🪄 Бросаем <b>Жребий</b>\n📡 Участники:\n- <a href='tg://user?id={creator_id}'>{message.from_user.full_name}</a>",
            reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith('joindzrebi:'))
async def join_game_callback(callback_query: types.CallbackQuery):

    print("Обработка запроса на присоединение к игре...")
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gamesdzrebi:
        await callback_query.answer("Эта игра больше не существует.1")
        return

    game = gamesdzrebi[game_id]

    if user_id == game['creator']:
        await callback_query.answer("Вы не можете присоединиться к своей игре.")
        return

    # Здесь должна быть проверка баланса пользователя перед присоединением
    bet = game['bet']
    current_balance = 1000  # Пример проверки баланса
    if current_balance < bet:
        await callback_query.answer("У вас недостаточно средств для участия в игре.")
        return

    if user_id in game['participants']:
        await callback_query.answer("Вы уже участвуете в этой игре.")
        return

    await callback_query.answer()

    game['participants'].append(user_id)

    participants_names = []
    for uid in game['participants']:
        user = await bot1.get_chat_member(callback_query.message.chat.id, uid)
        user_name = user.user.full_name if user else 'Unknown User'
        participant_link = f"- <a href='tg://user?id={uid}'>{user_name}</a>"
        participants_names.append(participant_link)

    participants_text = "\n".join(participants_names)

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Присоединиться", callback_data=f"joindzrebi:{game_id}"),
        InlineKeyboardButton("Начать игру", callback_data=f"startdzrebi:{game_id}")
    )

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🪄 Бросаем <b>Жребий</b>\n🕊 Возможный выигрыш: {game['bet'] * len(game['participants'])}\n\n📡 Участники:\n{participants_text}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )



@dp.callback_query(lambda c: c.data.startswith('startdzrebi:'))
async def start_dzrebi_callback(callback_query: types.CallbackQuery):

    print("Обработка запроса на начало игры...")
    game_id = int(callback_query.data.split(':')[1])
    creator_id = callback_query.from_user.id

    if game_id not in gamesdzrebi:
        await callback_query.answer("Эта игра больше не существует.10")
        return

    game = gamesdzrebi[game_id]

    if creator_id != game['creator']:
        await callback_query.answer("Вы не создатель этой игры.")
        return
    await callback_query.answer()

    await start_game(game_id, callback_query.message.chat.id)


# Функция для начала игры
async def start_game(game_id: int, chat_id: int):
    print("Запуск игры...")
    game = gamesdzrebi.get(game_id)
    if not game:
        return

    num_participants = len(game['participants'])

    # Определяем случайным образом длинную палочку
    winner_stick_index = random.randint(0, num_participants - 1)
    game['winner_stick_index'] = winner_stick_index

    # Создаем кнопки для выбора палочек
    buttons = []
    for i in range(1, num_participants + 1):
        buttons.append(InlineKeyboardButton(f"{i}", callback_data=f"choose_stick:{i}:{game_id}"))

    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(*buttons)

    # Начальное отображение палочек
    sticks_display = " | " * num_participants

    msg = await bot1.send_message(
        chat_id=chat_id,
        text=f"Игра начата! Выберите палочку:\n\n{sticks_display}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    # Сохраняем ID сообщения для последующего обновления
    gamesdzrebi[game_id]['message_id'] = msg.message_id

@dp.callback_query(lambda c: c.data.startswith('choose_stick:'))
async def choose_stick_callback(callback_query: CallbackQuery):

    print("Обработка выбора палочки...")
    data = callback_query.data.split(':')
    stick_index = int(data[1])
    game_id = int(data[2])
    user_id = callback_query.from_user.id

    game = gamesdzrebi.get(game_id)
    if not game or 'winner_stick_index' not in game:
        await callback_query.answer("Ошибка: игра не найдена или состояние игры некорректно.")
        return

    if stick_index < 1 or stick_index > len(game['participants']):
        await callback_query.answer("Ошибка выбора палочки: некорректный номер палочки.")
        return

    # Проверяем, выбрал ли пользователь уже палочку
    if 'sticks' in game and user_id in game['sticks']:
        await callback_query.answer("Вы уже выбрали палочку.")
        return

    await callback_query.answer()

    # Добавляем выбранную палочку в список палочек игры
    if 'sticks' not in game:
        game['sticks'] = []
    game['sticks'].append(user_id)

    # Проверяем, является ли выбранная палочка выигрышной
    if stick_index - 1 == game['winner_stick_index']:
        stick_type = "длинная (победная)"
    else:
        stick_type = "короткая"

    # Удаляем кнопку выбранной палочки из клавиатуры
    keyboard = InlineKeyboardMarkup(row_width=3)
    for i in range(1, len(game['participants']) + 1):
        if i != stick_index:
            keyboard.add(InlineKeyboardButton(f"{i}", callback_data=f"choose_stick:{i}:{game_id}"))

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"{callback_query.from_user.full_name} выбрал палочку номер {stick_index} ({stick_type})",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    # Если все выбрали палочки, завершаем игру
    if len(game['sticks']) == len(game['participants']):
        await end_game(game_id, callback_query.message.chat.id)


# Функция для завершения игры
async def end_game(game_id: int, chat_id: int):
    game = gamesdzrebi.get(game_id)
    if not game or 'winner_stick_index' not in game:
        print("Ошибка: игра не найдена или состояние игры некорректно.")
        return

    winner_stick_index = game['winner_stick_index']

    # Выводим сообщение о победе
    winner_user_id = game['participants'][winner_stick_index]
    winner_name = (await bot1.get_chat_member(chat_id, winner_user_id)).user.full_name
    await bot1.send_message(
        chat_id=chat_id,
        text=f"Игра окончена! Победил {winner_name}.",
        parse_mode="HTML"
    )

    # Очищаем данные игры
    del gamesdzrebi[game_id]