import random

from main import *
import uuid
user_coefficients = {}
user_gild = {}
gamesgild = {}

async def check_balance_gild(user_id, bet):
    current_balance = await db.get_user_balance(user_id)
    return current_balance is not None and current_balance >= bet


def create_game_board_gild():
    board = ['ㅤ'] * 64

    # Расположение шашек игрока 1 (создателя игры)
    board[55] = '🔴'  # 1 шашка
    board[62] = '🔴'  # 2 шашки
    board[63] = '🔴'  # 3 шашки

    # Расположение шашек игрока 2 (противника)
    board[0] = '❤️'  # 1 шашка
    board[1] = '❤️'  # 2 шашки
    board[8] = '❤️'  # 3 шашки

    return board

def create_game_keyboard_gild(board, game_id):
    keyboard = InlineKeyboardMarkup(row_width=8)
    for i in range(0, len(board), 8):
        row = [InlineKeyboardButton(board[j], callback_data=f"gildclick:{j}:{game_id}") for j in range(i, i + 8)]
        keyboard.add(*row)
    return keyboard

def get_neighbors(pos):
    neighbors = []
    if pos % 8 > 0:  # Left
        neighbors.append(pos - 1)
    if pos % 8 < 7:  # Right
        neighbors.append(pos + 1)
    if pos >= 8:  # Up
        neighbors.append(pos - 8)
    if pos < 56:  # Down
        neighbors.append(pos + 8)
    return neighbors

def update_board_on_move(board, pos, color):
    # Добавляем шашку только если ячейка пуста
    if board[pos] == 'ㅤ':
        board[pos] = color
        if color == '❤️':
            # Распространение оранжевого цвета
            spread_stones(board, pos, '🟠')
        elif color == '🟠':
            # Распространение оранжевого цвета
            spread_stones(board, pos, '🔴')

def spread_stones(board, pos, color):
    neighbors = get_neighbors(pos)
    for neighbor in neighbors:
        if 0 <= neighbor < 64:
            if board[neighbor] == 'ㅤ':
                board[neighbor] = color

def check_victory(board, players):
    player1_check = any(cell.startswith('🔴') for cell in board)
    player2_check = any(cell.startswith('❤️') for cell in board)

    if not player1_check:
        return players[1]  # Player 2 wins
    if not player2_check:
        return players[0]  # Player 1 wins
    return None  # Game continues

@dp.message()
async def gild(message: Message):
    parts = message.text.split()
    bet_str = ''

    if len(parts) == 2 and parts[0].lower() == "гильд":
        bet_str = parts[1].replace(',', '').replace('.', '')
    elif len(parts) == 1 and parts[0].lower() == "гильд":
        bet_str = '0'
    else:
        return

    try:
        if bet_str.isdigit():
            bet = int(bet_str)
        else:
            raise ValueError("Некорректная ставка")
    except ValueError:
        await message.reply("🛠 Некорректная ставка")
        return

    creator_id = message.from_user.id

    if not await check_balance_gild(creator_id, bet):
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


    game_id = str(uuid.uuid4())
    gamesgild[game_id] = {"creator": creator_id, "bet": bet, "participants": [creator_id], "turn": creator_id,
        "board": create_game_board_gild(), "game_active": True}

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Присоединиться", callback_data=f"gildjoin:{game_id}"))

    formatted_win_amount = "{:,.0f}".format(bet).replace(',', '.')
    first_name = await db.get_firstname_by_user_id(creator_id)

    await message.reply(
        f"🧨 <b>Играем в гильд</b>\n- <a href='tg://user?id={creator_id}'>{first_name}</a>",
        reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith('gildjoin:'))
async def join_game_callback(callback_query: types.CallbackQuery):
    game_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id

    if game_id not in gamesgild:
        await callback_query.answer("Эта игра больше не существует.")
        return

    game = gamesgild[game_id]

    if user_id == game['creator']:
        await callback_query.answer("Вы не можете присоединиться к своей игре.")
        return

    if len(game['participants']) >= 2:
        await callback_query.answer("Игра заполнена")
        return

    if not await check_balance_gild(user_id, game['bet']):
        await callback_query.answer("Недостаточно средств для участия в игре.")
        return

    if user_id in game['participants']:
        await callback_query.answer("Вы уже участвуете в этой игре.")
        return

    game['participants'].append(user_id)

    participants_names = []
    for uid in game['participants']:
        user = await bot1.get_chat_member(callback_query.message.chat.id, uid)
        user_name = user.user.full_name if user else 'Unknown User'
        participant_link = f"- <a href='tg://user?id={uid}'>{user_name}</a>"
        participants_names.append(participant_link)

    participants_text = "\n".join(participants_names)
    total_pot = game['bet'] * len(game['participants'])

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Начать игру", callback_data=f"gildstart:{game_id}"))

    win_amount_formatted2 = "{:,.0f}".format(total_pot).replace(",", ".")
    win_text = f"\n💰 Выигрыш <b>{win_amount_formatted2}</b> кут" if total_pot > 0 else ""

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🧨 <b>Играем в гильд</b>{win_text}\n{participants_text}",
        reply_markup=keyboard,
        parse_mode="HTML")

    await callback_query.answer("Вы присоединились к игре!")

@dp.callback_query(lambda c: c.data.startswith('gildstart:'))
async def start_game_callback(callback_query: types.CallbackQuery):
    game_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id

    if game_id not in gamesgild:
        await callback_query.answer("Эта игра больше не существует.")
        return

    game = gamesgild[game_id]

    if user_id != game['creator']:
        await callback_query.answer("Только создатель игры может начать игру.")
        return

    if len(game['participants']) != 2:
        await callback_query.answer("В игре должны участвовать 2 игрока.")
        return

    keyboard = create_game_keyboard_gild(game['board'], game_id)

    creator_name = await db.get_firstname_by_user_id(game['creator'])

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🌟 Первый ход от <a href='tg://user?id={game['creator']}'>{creator_name}</a>.",
        reply_markup=keyboard,
        parse_mode="HTML")

    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('gildclick:'))
async def board_click_callback(callback_query: types.CallbackQuery):
    data = callback_query.data.split(':')
    pos = int(data[1])
    game_id = data[2]
    user_id = callback_query.from_user.id

    if game_id not in gamesgild:
        await callback_query.answer("Эта игра больше не существует.")
        return

    game = gamesgild[game_id]

    if not game['game_active']:
        await callback_query.answer("Игра завершена.")
        return

    if user_id != game['turn']:
        await callback_query.answer("Сейчас не ваш ход.")
        return

    current_player_symbol = '🔴' if user_id == game['creator'] else '❤️'
    current_player_name = await db.get_firstname_by_user_id(user_id)

    # Убедитесь, что шашка размещается правильно
    if game['board'][pos] != 'ㅤ':
        await callback_query.answer("На этом месте уже стоит шашка.")
        return

    update_board_on_move(game['board'], pos, current_player_symbol)

    winner = check_victory(game['board'], game['participants'])
    if winner:
        game['game_active'] = False
        winner_name = await bot1.get_chat_member(callback_query.message.chat.id, winner)
        winner_name_text = winner_name.user.full_name if winner_name else 'Unknown User'
        await bot1.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"🏆 Игра окончена! Победитель: <a href='tg://user?id={winner}'>{winner_name_text}</a>",
            parse_mode="HTML"
        )
        return

    # Switch turn
    game['turn'] = game['participants'][1] if user_id == game['participants'][0] else game['participants'][0]

    # Update the game board
    keyboard = create_game_keyboard_gild(game['board'], game_id)
    next_turn_name = await bot1.get_chat_member(callback_query.message.chat.id, game['turn'])
    next_turn_name_text = next_turn_name.user.full_name if next_turn_name else 'Unknown User'

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🔄 Ход игрока <a href='tg://user?id={game['turn']}'>{next_turn_name_text}</a>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback_query.answer()
