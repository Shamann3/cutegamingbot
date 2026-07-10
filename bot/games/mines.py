import random
from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import bot1, dp

from aiogram.types import ReplyKeyboardMarkup
from aiogram.enums import ParseMode, ChatType  # Импортируем ParseMode из aiogram.enums

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from bot.db_create.db import *
from aiogram import exceptions as aiogram_exceptions  # Общие исключения теперь импортируются из aiogram
from aiogram.fsm.context import FSMContext  # Используем новый путь для FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.state import StatesGroup, State  # Новый путь для состояний
from aiogram.exceptions import TelegramAPIError  # Для исключений, связанных с API, теперь используем TelegramAPIError
import math
import json
import os
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import Bot, Dispatcher, types, F
from main import gamesmine,button_gamesmine,_format_hms,_pair_seconds_left,_pair_seconds_left, db, bot1, dp,get_current_time_formatted,timehistorygames,pending_context,send_invoice_to_user

import uuid



async def check_balance(user_id, bet):
    current_balance = await db.get_user_balance(user_id)
    return current_balance is not None and current_balance >= bet


def create_game_board():
    print("Отладка: Создание игрового поля.")
    board = ['❓'] * 25  # Поле 5x5
    return board

def create_game_keyboard(board, game_id):
    # Размер поля должен быть 5x5
    expected_size = 25
    if len(board) != expected_size:
        print(f"Отладка: Некорректный размер доски. Ожидалось {expected_size}, получено {len(board)}.")
        return InlineKeyboardMarkup()  # Возвращаем пустую клавиатуру, если размер некорректен

    # Создаем список строк для клавиатуры
    rows = []
    for i in range(0, len(board), 5):
        row = [
            InlineKeyboardButton(text=board[j], callback_data=f"mineclick:{j}:{game_id}")
            for j in range(i, i + 5)
        ]
        rows.append(row)  # Добавляем строку в список

    # Создаем клавиатуру с rows и row_width
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows, row_width=5)
    return keyboard

@dp.message()
async def mines(message: Message):

    parts = message.text.split()
    bet_str = ''  # Инициализируем переменную

    if len(parts) == 2 and parts [ 0 ].lower() == "мины":
        bet_str = parts [ 1 ].replace(',' , '').replace('.' , '')
    elif len(parts) == 1 and parts [ 0 ].lower() == "мины":
        bet_str = '0'  # Устанавливаем bet_str как строку '0'
    else:
        # Неправильный формат команды, выходим
        return

    try:
        # Проверяем, что bet_str не пустой и является числом
        if bet_str.isdigit():
            bet = int(bet_str)
        else:
            raise ValueError("Некорректная ставка")

        # Проверяем, что ставка больше 0
        #if bet <= 0:
            #await message.reply("🛠 Ставка должна быть больше 0")
            #return
    except ValueError:
        await message.reply("🛠 <b>Некорректная ставка</b>",
            parse_mode="HTML",
            disable_web_page_preview=True)
        return

    creator_id = message.from_user.id
    print(f"Отладка: Создатель игры с ID {creator_id}. Ставка: {bet}")

    if not await check_balance(creator_id , bet):
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

    game_id = str(uuid.uuid4())  # Генерируем уникальный ID игры
    gamesmine [ game_id ] = {"creator": creator_id , "bet": bet , "participants": [ creator_id ] , "turn": creator_id ,
        # Первый ход делает создатель игры
        "mines": set() , "board": create_game_board() ,  # Создаем начальное состояние игрового поля
        "game_active": True}

    print(f"Отладка: Игра создана. ID игры: {game_id}, Создатель: {creator_id}")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ InlineKeyboardButton(text="Присоединиться" , callback_data=f"minejoin:{game_id}") ] ])
    button_gamesmine [ game_id ] = {}
    button_gamesmine [ game_id ] [ 'keyboard_join' ] = keyboard
    formatted_win_amount = "{:,.0f}".format(bet).replace(',' , '.')
    first_name = await db.get_firstname_by_user_id(creator_id)
    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)

    # Формируем ссылку на пользователя
    name_link = await create_user_link(creator_id , first_name , username)
    msg = await message.reply(
        f"<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> <b>Играем в мины\n- {name_link}</b>" , reply_markup=keyboard , parse_mode="HTML" , disable_web_page_preview=True)
    gamesmine [ game_id ] [ "chat_id" ] = msg.chat.id
    gamesmine [ game_id ] [ "message_id" ] = msg.message_id
    gamesmine.save()


_mines_join_locks: Dict[str, asyncio.Lock] = {}
_mines_inflight: Set[Tuple[str, int]] = set()

def _get_mines_lock(game_id: str) -> asyncio.Lock:
    lock = _mines_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _mines_join_locks[game_id] = lock
    return lock

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set(); out = []
    for uid in items:
        if uid not in seen:
            seen.add(uid); out.append(int(uid))
    return out
@dp.callback_query(lambda c: c.data.startswith('minejoin:'))
async def mines_join_game_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        game_id = callback_query.data.split(':', 1)[1]  # В твоём коде ключи строковые - так и оставим
    except Exception:
        try:
            await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        except Exception:
            pass
        return

    # Быстрый отбой, если игры нет
    if game_id not in gamesmine:
        try:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        except Exception:
            pass
        return

    # Анти-дребезг: пока идёт обработка - не пускаем повторы
    inflight_key = (game_id, user_id)
    if inflight_key in _mines_inflight:
        try:
            await callback_query.answer("⏳ Обрабатываю ваше присоединение…")
        except Exception:
            pass
        return
    _mines_inflight.add(inflight_key)

    try:
        lock = _get_mines_lock(game_id)
        async with lock:
            # Ещё раз проверим игру внутри лока
            game = gamesmine.get(game_id)
            if not game:
                try:
                    await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                except Exception:
                    pass
                return

            chat_id = game.get("chat_id")
            message_id = game.get("message_id")

            # БАЗОВЫЕ ПРОВЕРКИ
            if await db.is_user_banned(user_id):
                try:
                    await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                except Exception:
                    pass
                return

            if user_id == int(game.get('creator')):
                try:
                    await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
                except Exception:
                    pass
                return

            # нормализуем участников и убираем дубли
            participants = [ (p[0] if isinstance(p, (tuple, list)) else int(p))
                             for p in game.get('participants', []) ]
            participants = _dedupe_preserve_order_uids(participants)
            game['participants'] = participants

            if len(participants) >= 2:
                try:
                    await callback_query.answer("❕ Игра заполнена", show_alert=True)
                except Exception:
                    pass
                return

            if user_id in participants:
                try:
                    await callback_query.answer("💭 Вы уже участвуете в этой игре.", show_alert=True)
                except Exception:
                    pass
                return

            # Баланс/ставка
            bet = int(game.get('bet', 0) or 0)
            if bet > 0:
                bal = await db.get_user_balance(user_id)
                try:
                    enough = (bal is not None) and int(bal) >= bet
                except Exception:
                    enough = False
                if not enough:
                    try:
                        await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
                    except Exception:
                        pass
                    return

            # ================== АНТИ-РЕФ ПРОВЕРКИ (строго внутри лока) ==================
            # 0) Очистка просроченных refout
            try:
                if hasattr(db, "remove_expired_refout"):
                    await db.remove_expired_refout()
                else:
                    await db.cleanup_expired_refout()
            except Exception:
                pass

            # 1) Участники лобби как множество user_id (+ создаём множество прям отсюда)
            participants_user_ids = set(participants)
            try:
                participants_user_ids.add(int(game.get('creator')))
            except Exception:
                pass

            # 2) Пригласитель в лобби?
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id is not None:
                    inviter_id = int(inviter_id)

                if inviter_id and inviter_id in participants_user_ids:
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=datetime.now())
                    if secs > 0:
                        try:
                            await callback_query.answer(
                                "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                                "который пригласил вас в Кут. Пока действует временная защита.\n\n"
                                f"⏳ До снятия ограничения : {_format_hms(secs)}\n#AntiFarmSystem",
                                show_alert=True
                            )
                        except Exception:
                            pass
                        return
            except Exception:
                try:
                    await callback_query.answer(
                        "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

            # 3) Любой из приглашённых в лобби?
            try:
                invitees_here = await db.get_invitees_in(
                    inviter_id=user_id,
                    candidates=list(participants_user_ids)
                )
                if invitees_here:
                    now = datetime.now()
                    min_secs = None
                    for invitee_id in invitees_here:
                        try:
                            invitee_id = int(invitee_id)
                        except Exception:
                            continue
                        secs = await _pair_seconds_left(db, user_id, invitee_id, now=now)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)

                    if min_secs is not None:
                        try:
                            await callback_query.answer(
                                "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                                "которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                                f"⏳ До снятия ограничения : {_format_hms(min_secs)}\n#AntiFarmSystem",
                                show_alert=True
                            )
                        except Exception:
                            pass
                        return
            except Exception:
                try:
                    await callback_query.answer(
                        "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

            # ===== КРИТИЧЕСКАЯ ТОЧКА - добавляем атомарно =====
            if len(game['participants']) >= 2:
                try:
                    await callback_query.answer("❕ Игра заполнена", show_alert=True)
                except Exception:
                    pass
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order_uids(game['participants'])
            gamesmine.save()

            # ===== UI =====
            # список участников с кликабельными ссылками
            participants_names = []
            for uid in game['participants']:
                first_name = await db.get_firstname_by_user_id(uid)
                username = await db.get_username_by_user_id(uid)
                name_link = await create_user_link(uid, first_name, username)
                participants_names.append(f"<b>- {name_link}</b>")
            participants_text = "\n".join(participants_names)

            total_pot = bet * len(game['participants'])
            win_amount_formatted = "{:,.0f}".format(max(total_pot - bet, 0)).replace(",", ".")
            win_text = f"\n<tg-emoji emoji-id='5294323314385248014'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"minestart:{game_id}")]]
            )
            button_gamesmine[game_id]['keyboard_start'] = keyboard

            try:
                await bot1.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> <b>Играем в мины</b>{win_text}\n{participants_text}",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[MINES] edit_message_text error: {e}")

            try:
                await callback_query.answer("❕ Вы присоединились к игре!")
            except Exception:
                pass

            gamesmine.save()

    except Exception as e:
        print(f"[MINES] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _mines_inflight.discard(inflight_key)


@dp.callback_query(lambda c: c.data.startswith('minestart:'))
async def mines_start_game_callback(callback_query: CallbackQuery):

    game_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    chat_id = gamesmine [ game_id ] [ "chat_id" ]
    message_id = gamesmine [ game_id ] [ "message_id" ]
    print(f"Отладка: Начало игры. ID игры: {game_id}, Создатель: {user_id}")

    if game_id not in gamesmine:
        print(f"Отладка: Игра с ID {game_id} не найдена в gamesmine.")
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    game = gamesmine[game_id]

    if user_id != game['creator']:
        print(f"Отладка: Пользователь с ID {user_id} пытается начать игру, но он не создатель.")
        await callback_query.answer("💭 Только создатель игры может начать игру.")
        return

    if len(game['participants']) != 2:
        print(f"Отладка: В игре с ID {game_id} должно быть 2 игрока.")
        await callback_query.answer("💭 В игре должны участвовать 2 игрока.")
        return
    await callback_query.answer()

    required_bet = game [ 'bet' ]  # Предполагается, что в игре есть ставка
    insufficient_balance = [ ]
    for participant in game [ 'participants' ]:
        current_balance = await db.get_user_balance(participant)  # Получаем баланс участника асинхронно
        if current_balance is None or current_balance < required_bet:
            insufficient_balance.append(participant)

    if insufficient_balance:
        first_names = [ await db.get_firstname_by_user_id(participant) for participant in insufficient_balance ]
        usernames = [ await db.get_username_by_user_id(participant) for participant in insufficient_balance ]

        # Формируем сообщение об остановке игры
        insufficient_user_links = [ await create_user_link(participant , first_name , username) for
            participant , first_name , username in zip(insufficient_balance , first_names , usernames) ]
        user_links_text = ', '.join(insufficient_user_links)
        message_text = f"⛑ <b>Игра остановлена!\nНедостаточно средств для игры у {user_links_text}</b>"

        await bot1.edit_message_text(
            chat_id=chat_id , message_id=message_id , text=message_text ,
            parse_mode="HTML" , disable_web_page_preview=True)
        del gamesmine [ game_id ]  # Удаляем игру из активных игр
        return  # Завершаем выполнение функции
    # Генерация случайного количества мин на поле (10 мин)
    mines_count = 4
    game['mines'] = set(random.sample(range(25), mines_count))  # Размещаем мины на поле

    print(f"Отладка: Мин размещены на позициях {game['mines']}")

    # Обновляем поле с невидимыми символами
    game['board'] = create_game_board()
    print(game['board'])
    # Создание клавиатуры с кнопками для игрового поля 5x5
    keyboard = create_game_keyboard(game['board'], game_id)
    button_gamesmine [ game_id ] [ 'keyboard_start' ] = keyboard
    creator_name = await db.get_firstname_by_user_id(game['creator'])

    first_name = await db.get_firstname_by_user_id(game['creator'])
    username = await db.get_username_by_user_id(game['creator'])

    # Формируем ссылку на пользователя
    name_link111 = await create_user_link(game['creator'] , first_name , username)
    await bot1.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text=f"<tg-emoji emoji-id='5188216731453103384'>✔️</tg-emoji> <b>Первый ход от {name_link111}</b>",
        reply_markup=keyboard, parse_mode="HTML" , disable_web_page_preview=True
    )
    gamesmine.save()


@dp.callback_query(lambda c: c.data.startswith('mineclick:'))
async def mines_mine_click_callback(callback_query: CallbackQuery):

    data = callback_query.data.split(':')
    x = int(data[1])
    game_id = data[2]
    user_id = callback_query.from_user.id
    chat_id = gamesmine [ game_id ] [ "chat_id" ]
    message_id = gamesmine [ game_id ] [ "message_id" ]
    print(f"Отладка: Пользователь с ID {user_id} нажал на клетку {x} в игре с ID {game_id}")

    if game_id not in gamesmine:
        print(f"Отладка: Игра с ID {game_id} не найдена в gamesmine.")
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    game = gamesmine[game_id]

    required_bet = game [ 'bet' ]  # Предполагается, что в игре есть ставка
    insufficient_balance = [ ]
    for participant in game [ 'participants' ]:
        current_balance = await db.get_user_balance(participant)  # Получаем баланс участника асинхронно
        if current_balance is None or current_balance < required_bet:
            insufficient_balance.append(participant)

    if insufficient_balance:
        first_names = [ await db.get_firstname_by_user_id(participant) for participant in insufficient_balance ]
        usernames = [ await db.get_username_by_user_id(participant) for participant in insufficient_balance ]

        # Формируем сообщение об остановке игры
        insufficient_user_links = [ await create_user_link(participant , first_name , username) for
                                    participant , first_name , username in
                                    zip(insufficient_balance , first_names , usernames) ]
        user_links_text = ', '.join(insufficient_user_links)
        message_text = f"⛑ <b>Игра остановлена!\nНедостаточно средств для игры у {user_links_text}</b>"

        await bot1.edit_message_text(
            chat_id=chat_id , message_id=message_id , text=message_text ,
            parse_mode="HTML" , disable_web_page_preview=True)
        del gamesmine [ game_id ]  # Удаляем игру из активных игр
        return  # Завершаем выполнение функции

    if not game['game_active']:
        print(f"Отладка: Игра с ID {game_id} уже завершена.")
        await callback_query.answer("💭 Игра уже завершена.")
        return

    if user_id != game['turn']:
        print(f"Отладка: Ход пользователя с ID {user_id}, но это не его ход.")
        await callback_query.answer("❕ Сейчас не ваш ход.")
        return

    if x < 0 or x >= 25:
        print(f"Отладка: Некорректная позиция: {x}. Должно быть от 0 до 24.")
        await callback_query.answer("💭 Некорректная позиция.")
        return

    # Проверка на разминирование
    if game['board'][x] in ['✔️', '✖️']:
        print(f"Отладка: Пользователь с ID {user_id} попытался нажать на уже разминированную клетку {x}.")
        await callback_query.answer("❕ Эта клетка уже разминирована.")
        return
    await callback_query.answer()

    if x in game['mines']:
        print(f"Отладка: Пользователь с ID {user_id} попал на мину!")
        game['game_active'] = False
        winner_id = game['participants'][0] if user_id == game['participants'][1] else game['participants'][1]
        loser_name = await db.get_firstname_by_user_id(user_id)
        winner_name = await db.get_firstname_by_user_id(winner_id)

        bet = game [ 'bet' ]

        winner_balance = await db.get_user_balance(winner_id)
        loser_balance = await db.get_user_balance(user_id)
        new_winner_balance = winner_balance + bet
        new_loser_balance = loser_balance - bet

        await db.update_user_balance(winner_id, new_winner_balance)
        await db.update_user_balance(user_id, new_loser_balance)

        await db.touch_balance_last_active(winner_id , set_active_status=True)
        await db.touch_balance_last_active(user_id , set_active_status=True)


        await db.cutehistory_plus(winner_id , bet , "+ мины")
        await db.cutehistory_minus(user_id , bet , "- мины")
        winner_clan_emoji = await db.get_clan_emoji3(winner_id)
        loser_clan_emoji = await db.get_clan_emoji3(user_id)

        if winner_clan_emoji and loser_clan_emoji:
            attack_info = await db.get_clan_attack(loser_clan_emoji)

            if attack_info and attack_info [ 0 ] == 1 and attack_info [ 1 ] == winner_clan_emoji:
                await db.adjust_clan_coins(winner_clan_emoji , bet , 'add')
                await db.adjust_clan_coins(loser_clan_emoji , bet , 'deduct')

                loser_clan_balance = await db.get_clan_balance(loser_clan_emoji)
                if loser_clan_balance <= 0:
                    await db.clear_clan_attack(winner_clan_emoji)
                    await db.clear_clan_attack(loser_clan_emoji)

                    loser_clan_members , loser_clan_owner = await db.get_clan_members_and_owner(loser_clan_emoji)
                    winner_clan_members , winner_clan_owner = await db.get_clan_members_and_owner(winner_clan_emoji)

                    if loser_clan_members is None or winner_clan_members is None:
                        print("Ошибка: Не удалось получить участников кланов.")
                        return

                    winner_clan_name = await db.get_clan_name(winner_clan_emoji)
                    loser_clan_name = await db.get_clan_name(loser_clan_emoji)

                    if winner_clan_name is None or loser_clan_name is None:
                        print("Ошибка: Не удалось получить названия кланов.")
                        return

                    # Сообщение о том, что рейтинг кланов изменен
                    #await callback_query.message.answer(
                        #f"⚔️ Рейтинг кланов изменен!\n"
                        #f"🎉 Клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> выиграл {bet} ⭐️.\n"
                        #f"🚩 Клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл {bet} ⭐️." ,
                        #parse_mode="HTML")

                    # Отправляем сообщения членам проигравшего клана
                    for member_id in loser_clan_members:
                        try:

                            await bot1.send_message(
                                member_id ,
                                f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>" ,
                                parse_mode="HTML")
                        except Exception as e:
                            print(f"Ошибка при отправке сообщения участнику проигравшего клана {member_id}: {e}")

                    if loser_clan_owner:
                        try:
                            await bot1.send_message(
                                loser_clan_owner ,
                                f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>" ,
                                parse_mode="HTML")
                        except Exception as e:
                            print(f"Ошибка при отправке сообщения владельцу проигравшего клана {loser_clan_owner}: {e}")

                    # Отправляем сообщения членам победившего клана
                    for member_id in winner_clan_members:
                        try:
                            await bot1.send_message(
                                member_id ,
                                f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>" ,
                                parse_mode="HTML")
                        except Exception as e:
                            print(f"Ошибка при отправке сообщения участнику победившего клана {member_id}: {e}")

                    if winner_clan_owner:
                        try:
                            await bot1.send_message(
                                winner_clan_owner ,
                                f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>" ,
                                parse_mode="HTML")
                        except Exception as e:
                            print(f"Ошибка при отправке сообщения владельцу победившего клана {winner_clan_owner}: {e}")



        #await db.add_commissionmine(winner_id, bet, 'user')
        #await db.add_commissionmine(user_id, bet, 'bot')
        bum = random.choice(["БУМ!","ВЗРЫВ!","БАБАХ!","БУМ..БУМ..БУМ!"])

        total_pot = game [ 'bet' ] * len(game [ 'participants' ])

        win_amount_formatted2 = "{:,.0f}".format(total_pot - game [ 'bet' ]).replace("," , ".")

        total_pot = game [ 'bet' ] #* len(game [ 'participants' ])
        win_text = f"{win_amount_formatted2} кут" if total_pot > 0 else ""
        from main import check_bet_and_set_item
        await check_bet_and_set_item(winner_id , game [ 'bet' ])
        from main import check_bet_and_set_item
        await check_bet_and_set_item(user_id , game [ 'bet' ])
        first_name = await db.get_firstname_by_user_id(winner_id)
        username = await db.get_username_by_user_id(winner_id)

        await db.update_user_wins(winner_id , 1, bot1, ref_coin)

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
                        winner_id , last_open_time , datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"))

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
                        winner_id , last_open_time , datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"))

                    # Сообщаем пользователю, что бонус был обновлен
                    print(
                        f"Бонус обновлен для пользователя {winner_id}. Время последнего открытия: {last_open_time}, Время окончания: {data_open}")

            except Exception as e:
                print(f"Ошибка при проверке или обновлении бонуса: {e}")
                return
        await db.update_user_winamount(winner_id , bet)#
        await db.update_user_loose(user_id , 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(user_id)

        # Формируем ссылку на пользователя
        name_link1111 = await create_user_link(winner_id , first_name , username)

        if total_pot > 0:
            button = InlineKeyboardButton(text=f"{bum}" , callback_data="hsudshjskfpuoaoisd")
            button2 = InlineKeyboardButton(text=f"{win_text}" , callback_data="minesbetchechtextanswer")
            button3 = InlineKeyboardButton(text=f"🏆 {first_name} " , callback_data="winnerminesanswertext")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] , [ button3 ], [ button2 ] ])
        else:
            button = InlineKeyboardButton(text=f"{bum}" , callback_data="hsudshjskfpuoaoisd")
            button2 = InlineKeyboardButton(text=f"🏆 {first_name}" , callback_data="winnerminesanswertext")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ],[ button2 ] ])
        button_gamesmine [ game_id ] [ 'keyboard_stрsfiasfjasart' ] = keyboard
        messagetextmemem = random.choice(["🔥", "💥"])
        await bot1.edit_message_text(
            chat_id=chat_id , message_id=message_id ,
            text=f"<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji>" ,
            reply_markup=keyboard ,  # Empty list for inline_keyboard
            parse_mode="HTML" , disable_web_page_preview=True)
        return

    if user_id == game['participants'][0]:
        game['board'][x] = "✔️"
    else:
        game['board'][x] = "✖️"

    game['turn'] = game['participants'][0] if game['participants'][1] == user_id else game['participants'][1]

    next_player_name = await db.get_firstname_by_user_id(game['turn'])
    next_player_emoji = "<tg-emoji emoji-id='5188216731453103384'>✔️</tg-emoji>" if game['turn'] == game['creator'] else "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji>"

    keyboard = create_game_keyboard(game['board'], game_id)
    first_name = await db.get_firstname_by_user_id(game['turn'])
    username = await db.get_username_by_user_id(game['turn'])

    # Формируем ссылку на пользователя
    name_link111111 = await create_user_link(game['turn'] , first_name , username)
    await bot1.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text=f"{next_player_emoji} <b>Ход {name_link111111}</b>",
        reply_markup=keyboard, parse_mode="HTML" , disable_web_page_preview=True
    )
    gamesmine.save()

@dp.callback_query(lambda c: c.data == 'winnerminesanswertext')
async def mines_mineasdufioiaasd_click_callback(callback_query: CallbackQuery):
    await callback_query.answer(
        "🧨 Один из игроков взорвался на мине \n"
        "🏆 Победитель - тот, чьё имя указано на кнопке! ",show_alert=True
    )

@dp.callback_query(lambda c: c.data == 'minesbetchechtextanswer')
async def mineahsjidfokadsns_mine_click_callback(callback_query: CallbackQuery):
    await callback_query.answer(
        "💰 Это сумма, которую получил победитель",show_alert=True
    )