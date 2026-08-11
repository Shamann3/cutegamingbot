from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import bot1, dp
from bot.games.group_only import reject_if_private_game

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from bot.db_create.db import *
import random
import json
from main import *
import uuid
from bot.funcs.func import *
from bot.games.safe_game_edit import safe_game_edit
user_message_bullet = {}
user_messagebullet = {}


active_games_bullet = {}


def initialize_game_field_roulette():
    chamber = [" "] * 7
    bullet_positions = random.sample(range(7), random.randint(1, 4))  # Случайное количество пуль от 1 до 3
    for pos in bullet_positions:
        chamber[pos] = "💣"  # Устанавливаем пули
    print(f"[DEBUG] Инициализировано игровое поле: {chamber}")  # Отладка
    return chamber

# Функция для создания клавиатуры для игры в русскую рулетку
def create_keyboard_russian_roulette(target_player_name: str):
    keyboard = InlineKeyboardMarkup()
    # Список эмодзи, из которых будет выбран один случайный
    emojis = [
        "🧑🏻‍🚀", "‍🧑🏻‍✈️", "‍🧑🏻‍🚒", "🧑🏻‍🔬", "👨🏻‍🔧",
        "👨‍💻", "️👩🏻‍🏫", "🧑🏼‍🎓", "👩🏻‍🌾", "🧑🏼‍🍳",
        "👮🏼", "👷🏼‍♂️"
    ]
    soajdasdjaos = random.choice(emojis)  # Выбираем случайное эмодзи из списка

    # Обновляем текст кнопки с именем участника
    keyboard.add(
        InlineKeyboardButton(text=f"👻 В {target_player_name} ", callback_data="shoot_bot"),
        InlineKeyboardButton(text=f"{soajdasdjaos} В себя" , callback_data="shoot_self")
    )
    keyboard.add(
        InlineKeyboardButton(text="Крутить барабан", callback_data="spin")
    )
    print("[DEBUG] Создана клавиатура русской рулетки")  # Отладка
    return keyboard


@dp.message()
async def bullet(message: Message):
    parts = message.text.split()
    user_id = message.from_user.id
    chat_id = message.chat.id
    bet_str = '0'

    if len(parts) == 2 and parts[0].lower() == "пуля34123412":
        bet_str = parts[1].replace(',', '').replace('.', '')
    elif len(parts) == 1 and parts[0].lower() == "пуля34123412":
        bet_str = '0'
    else:
        return  # Неправильный формат команды

    if await reject_if_private_game(message):
        return

    try:
        if bet_str.isdigit():
            bet = int(bet_str)
        else:
            raise ValueError("Некорректная ставка")
    except ValueError:
        await message.reply("🛠 <b>Некорректная ставка</b>", parse_mode="HTML", disable_web_page_preview=True)
        return

    current_balance = await db.get_user_balance(user_id)
    chat_balance = await db.get_chat_balance(bot1,chat_id)

    # Проверка баланса
    if bet > current_balance:
        await message.reply("💭 <b>Недостаточно средств для игры</b>", parse_mode="HTML", disable_web_page_preview=True)
        return

    #if bet > chat_balance:

    # Создаем уникальный идентификатор для игры
    game_id = str(uuid.uuid4())
    game_field = initialize_game_field_roulette()

    active_games_bullet[game_id] = {
        "creator": user_id,
        "game_field": game_field,
        "bet": bet,
        "participants": [user_id]
    }

    # Получаем имя создателя игры
    creator_first_name = await db.get_firstname_by_user_id(user_id) or "Неизвестный"
    creator_username = await db.get_username_by_user_id(user_id)
    creator_link = await create_user_link(user_id, creator_first_name, creator_username)

    # Создаем клавиатуру для присоединения к игре
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Присоединиться", callback_data=f"bulletjoin:{game_id}")
    )

    await message.reply(
        f"🎯 <b>Играем в русскую рулетку!\n- {creator_link}</b>",
        reply_markup=keyboard,
        parse_mode="HTML", disable_web_page_preview=True
    )

# Обработчик для присоединения к игре
@dp.callback_query(lambda c: c.data.startswith('bulletjoin:'))
async def join_game_callback(callback_query: CallbackQuery):
    game_id = callback_query.data.split(':') [ 1 ]
    user_id = callback_query.from_user.id

    if game_id not in active_games_bullet:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    game = active_games_bullet [ game_id ]

    if user_id == game [ 'creator' ]:
        await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
        return

    if len(game [ 'participants' ]) >= 2:
        await callback_query.answer("❕ Игра заполнена", show_alert=True)
        return

    if not await db.get_user_balance(user_id) >= game [ 'bet' ]:
        await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
        return

    game [ 'participants' ].append(user_id)
    first_name = await db.get_firstname_by_user_id(user_id) or "Неизвестный"
    username = await db.get_username_by_user_id(user_id)

    # Формируем ссылку на пользователя
    name_link = await create_user_link(user_id , first_name , username)

    # Получаем имя создателя игры
    creator_id = game [ 'creator' ]
    creator_first_name = await db.get_firstname_by_user_id(creator_id) or "Неизвестный"
    creator_username = await db.get_username_by_user_id(creator_id)
    creator_link = await create_user_link(creator_id , creator_first_name , creator_username)

    participants_text = "\n".join(
        [
            f"<b>- {await create_user_link(pid , await db.get_firstname_by_user_id(pid) or 'Неизвестный' , await db.get_username_by_user_id(pid))}</b>"
            for pid in game [ 'participants' ] ])

    total_pot = game [ 'bet' ] * len(game [ 'participants' ])

    # Формируем текст сообщения
    bet_text = f"💰 <b>Выигрыш {game [ 'bet' ]*2} 💰</b>\n" if game [ 'bet' ] > 0 else ""

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Начать игру" , callback_data=f"bulletstart:{game_id}"))

    await safe_game_edit(
        game,
        chat_id=callback_query.message.chat.id , message_id=callback_query.message.message_id ,
        text=(f"🎯 <b>Играем в русскую рулетку!\n"
              f"{bet_text}"  # Добавляем текст со ставкой, если она больше 0
              f"{participants_text}</b>") , reply_markup=keyboard , parse_mode="HTML", disable_web_page_preview=True)
    await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('bulletstart:'))
async def start_game_callback(callback_query: CallbackQuery):
    game_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    # Извлекаем информацию о игре
    game = active_games_bullet.get(game_id)
    if game is None:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # Проверка на участие пользователя в игре
    if user_id not in game["participants"]:
        await callback_query.answer("❗ Вы не участвуете в этой игре.", show_alert=True)
        return

    # Гасим спиннер сразу, до сетевых/БД запросов ниже.
    await callback_query.answer()

    # Инициализация current_player, если это первая игра
    if 'current_player' not in game:
        game['current_player'] = game["participants"][0]  # Первый участник - создатель игры

    bet_amount = game['bet']  # Извлекаем ставку игры
    game_field = game['game_field']  # Извлекаем поле игры

    # Получаем текущий баланс пользователя и баланс чата
    current_balance = await db.get_user_balance(user_id)
    chat_balance = await db.get_chat_balance(bot1,chat_id)

    # Проверка наличия достаточного баланса у пользователя и в группе
    if bet_amount > current_balance:
        await callback_query.message.reply(
            "💭 <b>Недостаточно средств для игры</b>", parse_mode="HTML", disable_web_page_preview=True
        )
        return

    print(f"[DEBUG] Игра начата для пользователя {user_id}. Поле: {game_field}, Ставка: {bet_amount}")

    # Случайное приветственное сообщение
    random_message_text = random.choice(["Сделай выбор!", "Твой выбор ждет!", "Выбери свою судьбу!"])

    # Получаем имя текущего игрока
    pepepepe = game["participants"][1]
    pepeppefirst_name = await db.get_firstname_by_user_id(pepepepe) or "Неизвестный"
    creator_first_name = await db.get_firstname_by_user_id(game['current_player']) or "Неизвестный"
    creator_username = await db.get_username_by_user_id(game['current_player'])
    creator_link = await create_user_link(game['current_player'], creator_first_name, creator_username)

    # Создаем клавиатуру, передавая имя участника
    keyboard = create_keyboard_russian_roulette(pepeppefirst_name)

    await safe_game_edit(
        game,
        chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id,
        text=f"<b>🎯 В кого стреляем? {random_message_text} \n♨️ Текущий ход : {creator_link}</b>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard
    )

    await callback_query.answer("❕ Игра началась! Сделайте выбор.", show_alert=True)

@dp.callback_query(lambda c: c.data in ["shoot_bot", "shoot_self", "spin"])
async def game_actions(call: types.CallbackQuery):
    user_id = call.from_user.id
    game_info = None

    # Поиск игры по участнику
    for game_id, game in active_games_bullet.items():
        if user_id in game["participants"]:
            game_info = game
            break

    if game_info is None:
        await call.answer("❗ Игра не активна. Начните новую игру с командой 'пуля <сумма>'.", show_alert=True)
        return

    # Проверка, что текущий игрок - это пользователь
    if game_info['current_player'] != user_id:
        await call.answer("❗ Не ваш ход.", show_alert=True)
        return

    # chat_id/message_id сообщения игры - для безопасного редактирования.
    _chat_id = call.message.chat.id if call.message else None
    _message_id = call.message.message_id if call.message else None

    # Убеждаемся, что `game_field` и `shots_used` инициализированы
    if "game_field" not in game_info or "shots_used" not in game_info:
        game_info["game_field"] = ["💣"] + [" "] * 6
        random.shuffle(game_info["game_field"])
        game_info["shots_used"] = 0

    # Логика прокрутки барабана
    if call.data == "spin":
        random.shuffle(game_info["game_field"])
        await call.answer("🔄 Барабан прокручивается...")
        print(f"[DEBUG] Пользователь {user_id} крутит барабан.")
        return

    bullet_index = random.randint(0, 6)
    bullet_status = game_info["game_field"][bullet_index]

    # Получаем имя и ссылку на противника
    opponent_user_id = game['participants'][0] if game['participants'][0] != user_id else game['participants'][1]
    opponent_first_name = await db.get_firstname_by_user_id(opponent_user_id) or "Неизвестный"
    opponent_username = await db.get_username_by_user_id(opponent_user_id)
    opponent_link = await create_user_link(opponent_user_id, opponent_first_name, opponent_username)

    # Получаем имя и ссылку на текущего игрока
    creator_first_name = await db.get_firstname_by_user_id(user_id) or "Неизвестный"
    creator_username = await db.get_username_by_user_id(user_id)
    creator_link = await create_user_link(user_id, creator_first_name, creator_username)

    current_index = game_info["participants"].index(user_id)
    next_index = (current_index + 1) % len(game_info["participants"])
    game_info['current_player'] = game_info["participants"][next_index]

    # Обновляем имя следующего игрока
    next_player_id = game_info['current_player']
    next_player_first_name = await db.get_firstname_by_user_id(next_player_id) or "Неизвестный"
    next_player_username = await db.get_username_by_user_id(next_player_id)
    next_player_link = await create_user_link(next_player_id, next_player_first_name, next_player_username)

    bet = game_info.get("bet_amount")  # Сумма ставки должна быть сохранена в игре

    if call.data == "shoot_bot":
        game_info["shots_used"] += 1
        if bullet_status == "💣":
            await call.answer()  # гасим спиннер кнопки сразу
            await safe_game_edit(
                game_info, chat_id=_chat_id, message_id=_message_id,
                text=f"💥 <b>{opponent_link} проиграл! Выстрел был смертельным!</b>",
                reply_markup=None, parse_mode="HTML")
            winner_id = opponent_user_id  # Противник стал победителем
            loser_id = user_id

            # Проверка на корректность ставки
            if bet is not None:
                winner_balance = await db.get_user_balance(winner_id)
                loser_balance = await db.get_user_balance(loser_id)
                new_winner_balance = winner_balance + bet
                new_loser_balance = loser_balance - bet

                await db.update_user_balance(winner_id, new_winner_balance)
                await db.update_user_balance(loser_id, new_loser_balance)
            else:
                print(f"[DEBUG] Ставка не установлена для игры с участником {user_id}.")  # Убедитесь, что ставки действительно не установлены

            del active_games_bullet[game_info["game_id"]]  # Убедитесь, что `game_id` существует перед удалением
            print(f"[DEBUG] Пользователь {user_id} выстрелил в бота и проиграл.")
        else:
            game_info["game_field"][bullet_index] = "✔️"
            textbotsurvival = random.choice([f"{opponent_link} выжил", f"{opponent_link} остался в живых"])
            await call.answer(textbotsurvival)
            await safe_game_edit(
                game_info, chat_id=_chat_id, message_id=_message_id,
                text=f"💠 <b>{textbotsurvival} | {game_info['shots_used']} / 7 пуль использовано \n🩵 Текущий ход : {next_player_link}</b>",
                parse_mode="HTML", disable_web_page_preview=True,
                reply_markup=create_keyboard_russian_roulette(creator_first_name)
            )
            print(f"[DEBUG] Пользователь {user_id} выстрелил в бота, использовано пуль: {game_info['shots_used']}.")

    elif call.data == "shoot_self":
        game_info["shots_used"] += 1
        if bullet_status == "💣":
            await call.answer()  # гасим спиннер кнопки сразу
            await safe_game_edit(
                game_info, chat_id=_chat_id, message_id=_message_id,
                text="💢 <b>Вы проиграли! Выстрел в себя был смертельным!</b>",
                reply_markup=None, parse_mode="HTML")
            winner_id = opponent_user_id  # Противник стал победителем
            loser_id = user_id

            # Проверка на корректность ставки
            if bet is not None:
                winner_balance = await db.get_user_balance(winner_id)
                loser_balance = await db.get_user_balance(loser_id)
                new_winner_balance = winner_balance + bet
                new_loser_balance = loser_balance - bet

                await db.update_user_balance(winner_id, new_winner_balance)
                await db.update_user_balance(loser_id, new_loser_balance)
            else:
                print(f"[DEBUG] Ставка не установлена для игры с участником {user_id}.")

            del active_games_bullet[game_info["game_id"]]  # Убедитесь, что `game_id` существует перед удалением
            print(f"[DEBUG] Пользователь {user_id} выстрелил в себя и проиграл.")
        else:
            game_info["game_field"][bullet_index] = "✔️"
            textselfsurvival = random.choice(["Вы выжили", "Вы остались в живых"])
            await call.answer(textselfsurvival)
            await safe_game_edit(
                game_info, chat_id=_chat_id, message_id=_message_id,
                text=f"❇️ <b>{textselfsurvival} | {game_info['shots_used']} / 7 пуль использовано \n💚 Текущий ход : {next_player_link}</b>",
                parse_mode="HTML", disable_web_page_preview=True,
                reply_markup=create_keyboard_russian_roulette(creator_first_name)
            )
            print(f"[DEBUG] Пользователь {user_id} выстрелил в себя, использовано пуль: {game_info['shots_used']}.")

    # Проверка на окончание игры (только если игра ещё активна - на смертельном
    # выстреле она уже удалена выше, повторное удаление дало бы KeyError).
    if game_info["shots_used"] >= 7 and game_info.get("game_id") in active_games_bullet:
        await safe_game_edit(
            game_info, chat_id=_chat_id, message_id=_message_id,
            text="♨️ <b>Игра окончена!</b>", reply_markup=None,
            parse_mode="HTML", disable_web_page_preview=True)
        del active_games_bullet[game_info["game_id"]]

