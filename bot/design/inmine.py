import random

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
from main import gamesmine_inmine,_format_hms,_pair_seconds_left,_pair_seconds_left, db, bot1, dp,get_current_time_formatted,timehistorygames,inline_add_or_update_user_info


import uuid



async def check_balance_inmine(user_id, bet):
    current_balance = await db.get_user_balance(user_id)
    return current_balance is not None and current_balance >= bet


def create_game_board_inmine():
    print("Отладка: Создание игрового поля.")
    board = ['ㅤ'] * 25  # Поле 5x5
    return board

def create_game_keyboard_inmine(board, game_id):

    expected_size = 25
    if len(board) != expected_size:
        print(f"Отладка: Некорректный размер доски. Ожидалось {expected_size}, получено {len(board)}.")
        return InlineKeyboardMarkup()  # Возвращаем пустую клавиатуру, если размер некорректен

    # Создаем список строк для клавиатуры
    rows = []
    for i in range(0, len(board), 5):
        row = [
            InlineKeyboardButton(text=board[j], callback_data=f"mineclickinmine:{j}:{game_id}")
            for j in range(i, i + 5)
        ]
        rows.append(row)  # Добавляем строку в список

    # Создаем клавиатуру с rows и row_width
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows, row_width=5)
    return keyboard

@dp.callback_query(lambda c: c.data.startswith('inmine_create'))
async def inline_mine_create_game_callback(callback_query: types.CallbackQuery):

    creator_id = callback_query.from_user.id
    user_id = callback_query.from_user.id

    data_parts = callback_query.data.split(":")
    bet_amount = int(data_parts [ 2 ]) if len(data_parts) > 2 else 0  # Ставка передается как 3-й параметр
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username , db , start_balance)
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return
    # Если ставка больше 0, проверяем, достаточно ли у пользователя средств
    if bet_amount > 0:
        user_balance = await db.get_user_balance(user_id)
        if user_balance < bet_amount:
            # Если средств недостаточно, отправляем сообщение и выходим из функции
            await callback_query.answer("💭 Недостаточно средств для игры с такой ставкой." , show_alert=True)
            return

    await callback_query.answer()

    game_id = str(uuid.uuid4())  # Генерируем уникальный ID игры
    gamesmine_inmine [ game_id ] = {"creator": creator_id , "bet": bet_amount , "participants": [ creator_id ] , "turn": creator_id ,
        # Первый ход делает создатель игры
        "mines": set() , "board": create_game_board_inmine() ,  # Создаем начальное состояние игрового поля
        "game_active": True}

    print(f"Отладка: Игра создана. ID игры: {game_id}, Создатель: {creator_id}")


    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ [ InlineKeyboardButton(text="Присоединиться" , callback_data=f"minejoininmine:{game_id}") ] ])
    formatted_win_amount = "{:,.0f}".format(bet_amount).replace(',' , '.')
    first_name = await db.get_firstname_by_user_id(creator_id)
    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)

    win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".")
    bet_message = f"<tg-emoji emoji-id='5294323314385248014'>💰</tg-emoji> Ставка : {win_amount_formatted} кут\n" if bet_amount > 0 else ""

    # Формируем ссылку   на пользователя
    name_link = await create_user_link(creator_id , first_name , username)
    if "inline_message_id" not in gamesmine_inmine [ game_id ]:
        gamesmine_inmine [ game_id ] [ "inline_message_id" ] = callback_query.inline_message_id
    inline_message_id = gamesmine_inmine [ game_id ] [ "inline_message_id" ]
    await bot1.edit_message_text(f"<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> <b>Играем в мины\n{bet_message}- {name_link}</b>" ,inline_message_id=inline_message_id, reply_markup=keyboard , parse_mode="HTML" , disable_web_page_preview=True)
    gamesmine_inmine.save()

_inline_mines_join_locks: Dict[str, asyncio.Lock] = {}
_inline_mines_inflight: Set[Tuple[str, int]] = set()

def _get_inline_mines_lock(game_id: str) -> asyncio.Lock:
    lock = _inline_mines_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _inline_mines_join_locks[game_id] = lock
    return lock

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set(); out = []
    for uid in items:
        uid = int(uid)
        if uid not in seen:
            seen.add(uid); out.append(uid)
    return out
@dp.callback_query(lambda c: c.data and c.data.startswith('minejoininmine:'))
async def inline_mine_join_game_callback(callback_query: types.CallbackQuery):
    # парсим game_id
    try:
        game_id = callback_query.data.split(':', 1)[1]
    except Exception:
        await callback_query.answer("🛠 Неверные данные игры.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return
    # быстрый отбой: игра существует?
    if game_id not in gamesmine_inmine:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # анти-дребезг: не запускаем параллельные попытки для одного (игра, пользователь)
    inflight_key = (game_id, user_id)
    if inflight_key in _inline_mines_inflight:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=True)
        return
    _inline_mines_inflight.add(inflight_key)

    try:
        lock = _get_inline_mines_lock(game_id)
        async with lock:
            # ещё раз получаем игру внутри лока
            game = gamesmine_inmine.get(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            inline_message_id = game.get("inline_message_id")

            # профиль - обновим безопасно
            try:
                first_name = re.sub(r'[<>/{}"]', '', (callback_query.from_user.first_name or "Игрок"))
                username = callback_query.from_user.username
                await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
            except Exception:
                pass

            creator_id = int(game.get('creator'))

            # базовые проверки
            if user_id == creator_id:
                await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            # нормализуем и дедупим участников
            participants = _dedupe_preserve_order_uids(list(game.get('participants', [])))
            game['participants'] = participants

            if len(participants) >= 2:
                await callback_query.answer("❕ Игра заполнена", show_alert=True)
                return

            if user_id in participants:
                await callback_query.answer("💭 Вы уже участвуете в этой игре.", show_alert=True)
                return

            # баланс / ставка
            bet = int(game.get('bet', 0) or 0)
            if bet > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                    enough = (bal is not None) and int(bal) >= bet
                except Exception:
                    enough = False
                if not enough:
                    await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
                    return

            # ================== АНТИ-РЕФ (строго внутри лока) ==================
            # 0) очистка просроченного
            try:
                if hasattr(db, "remove_expired_refout"):
                    await db.remove_expired_refout()
                else:
                    await db.cleanup_expired_refout()
            except Exception:
                pass

            # 1) участники лобби (множество user_id)
            parts_set = set(participants)
            parts_set.add(creator_id)

            # 2) пригласитель в лобби?
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id and int(inviter_id) in parts_set:
                    secs = await _pair_seconds_left(db, user_id, int(inviter_id), now=datetime.now())
                    if secs > 0:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471", show_alert=True
                )
                return

            # 3) любой из приглашённых в лобби?
            try:
                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for inv_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(inv_id), now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(min_secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471", show_alert=True
                )
                return

            # ===== КРИТИЧЕСКАЯ ТОЧКА - добавляем игрока атомарно =====
            if len(game['participants']) >= 2:
                await callback_query.answer("❕ Игра заполнена", show_alert=True)
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order_uids(game['participants'])
            gamesmine_inmine.save()

            # UI: список участников
            participants_lines = []
            for uid in game['participants']:
                fn = await db.get_firstname_by_user_id(uid)
                un = await db.get_username_by_user_id(uid)
                link = await create_user_link(uid, fn, un)
                participants_lines.append(f"<b>- {link}</b>")
            participants_text = "\n".join(participants_lines)

            bet_message = f"<tg-emoji emoji-id='5294323314385248014'>💰</tg-emoji> Ставка : {bet:,.0f} кут\n".replace(",", ".") if bet > 0 else ""
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"minestartinmine:{game_id}")]]
            )

            try:
                await bot1.edit_message_text(
                    text=f"<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> <b>Играем в мины</b>\n{bet_message}{participants_text}",
                    inline_message_id=inline_message_id,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[MINES_INLINE] edit_message_text error: {e}")

            try:
                await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)
            except Exception:
                pass

            gamesmine_inmine.save()

    except Exception as e:
        print(f"[MINES_INLINE] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _inline_mines_inflight.discard((game_id, user_id))
        try:
            gamesmine_inmine.save()
        except Exception:
            pass

@dp.callback_query(lambda c: c.data.startswith('minestartinmine:'))
async def inline_mine_start_game_callback(callback_query: CallbackQuery):

    game_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username , db , start_balance)
    inline_message_id = gamesmine_inmine [ game_id ] [ "inline_message_id" ]
    print(f"Отладка: Начало игры. ID игры: {game_id}, Создатель: {user_id}")

    if game_id not in gamesmine_inmine:
        print(f"Отладка: Игра с ID {game_id} не найдена в gamesmine.")
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    game = gamesmine_inmine[game_id]

    if user_id != game['creator']:
        print(f"Отладка: Пользователь с ID {user_id} пытается начать игру, но он не создатель.")
        await callback_query.answer("💭 Только создатель игры может начать игру.", show_alert=True)
        return

    if len(game['participants']) != 2:
        print(f"Отладка: В игре с ID {game_id} должно быть 2 игрока.")
        await callback_query.answer("💭 В игре должны участвовать 2 игрока.", show_alert=True)
        return

    bet_amount = game.get('bet' , 0)

    # Если ставка больше 0, проверяем, достаточно ли у игрока денег
    if bet_amount > 0:
        user_balance = await db.get_user_balance(
            callback_query.from_user.id)  # Предполагается, что баланс хранится в поле 'balance'
        if user_balance < bet_amount:
            await callback_query.answer("💭 Недостаточно средств для игры." , show_alert=True)
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

        await bot1.edit_message_text(text=message_text ,inline_message_id=inline_message_id,
            parse_mode=ParseMode.HTML , disable_web_page_preview=True)
        del gamesmine_inmine [ game_id ]  # Удаляем игру из активных игр
        return  # Завершаем выполнение функции
    # Генерация случайного количества мин на поле (10 мин)
    mines_count = 4
    game['mines'] = set(random.sample(range(25), mines_count))  # Размещаем мины на поле

    print(f"Отладка: Мин размещены на позициях {game['mines']}")

    # Обновляем поле с невидимыми символами
    game['board'] = create_game_board_inmine()

    # Создание клавиатуры с кнопками для игрового поля 5x5
    keyboard = create_game_keyboard_inmine(game['board'], game_id)

    creator_name = await db.get_firstname_by_user_id(game['creator'])

    first_name = await db.get_firstname_by_user_id(game['creator'])
    username = await db.get_username_by_user_id(game['creator'])

    # Формируем ссылку на пользователя
    name_link111 = await create_user_link(game['creator'] , first_name , username)
    await bot1.edit_message_text(
        text=f"<tg-emoji emoji-id='5188216731453103384'>✔️</tg-emoji> <b>Первый ход от {name_link111}</b>",inline_message_id=inline_message_id,
        reply_markup=keyboard, parse_mode="HTML" , disable_web_page_preview=True
    )
    gamesmine_inmine.save()


@dp.callback_query(lambda c: c.data.startswith('mineclickinmine:'))
async def inline_mine_mine_click_callback(callback_query: CallbackQuery):

    data = callback_query.data.split(':')
    x = int(data[1])
    game_id = data[2]
    user_id = callback_query.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username , db , start_balance)
    inline_message_id = gamesmine_inmine [ game_id ] [ "inline_message_id" ]
    print(f"Отладка: Пользователь с ID {user_id} нажал на клетку {x} в игре с ID {game_id}")

    if game_id not in gamesmine_inmine:
        print(f"Отладка: Игра с ID {game_id} не найдена в gamesmine.")
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    game = gamesmine_inmine[game_id]

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

        await bot1.edit_message_text(text=message_text ,inline_message_id=inline_message_id,
            parse_mode=ParseMode.HTML , disable_web_page_preview=True)
        del gamesmine_inmine [ game_id ]  # Удаляем игру из активных игр
        return  # Завершаем выполнение функции

    if not game['game_active']:
        print(f"Отладка: Игра с ID {game_id} уже завершена.")
        await callback_query.answer("💭 Игра уже завершена.", show_alert=True)
        return

    if user_id != game['turn']:
        print(f"Отладка: Ход пользователя с ID {user_id}, но это не его ход.")
        await callback_query.answer("❕ Сейчас не ваш ход.", show_alert=True)
        return

    if x < 0 or x >= 25:
        print(f"Отладка: Некорректная позиция: {x}. Должно быть от 0 до 24.")
        await callback_query.answer("💭 Некорректная позиция.", show_alert=True)
        return

    # Проверка на разминирование
    if game['board'][x] in ['✔️', '✖️']:
        print(f"Отладка: Пользователь с ID {user_id} попытался нажать на уже разминированную клетку {x}.")
        await callback_query.answer("❕ Эта клетка уже разминирована.", show_alert=True)
        return

    if x in game['mines']:
        print(f"Отладка: Пользователь с ID {user_id} попал на мину!")
        game['game_active'] = False
        winner_id = game['participants'][0] if user_id == game['participants'][1] else game['participants'][1]
        loser_name = await db.get_firstname_by_user_id(user_id)
        winner_name = await db.get_firstname_by_user_id(winner_id)

        bet = game [ 'bet' ]

        winner_balance = await db.get_user_balance(winner_id)
        loser_balance = await db.get_user_balance(user_id)
        if loser_balance < bet:
            await callback_query.answer("💭 Недостаточно средств для выплаты выигрыша победителю",show_alert=True)
            return

        await callback_query.answer()
        new_winner_balance = winner_balance + bet
        new_loser_balance = loser_balance - bet


        await db.update_user_balance(winner_id, new_winner_balance)
        await db.update_user_balance(user_id, new_loser_balance)

        await db.touch_balance_last_active(winner_id , set_active_status=True)
        await db.touch_balance_last_active(user_id , set_active_status=True)


        await db.cutehistory_plus(winner_id , bet , "инлайн мины")
        await db.cutehistory_minus(user_id , bet , "инлайн мины")



        #await db.add_commissionmine(winner_id, bet, 'user')
        #await db.add_commissionmine(user_id, bet, 'bot')
        bum = random.choice(["БУМ!","ВЗРЫВ!","БАБАХ!","БУМ..БУМ..БУМ!"])

        total_pot = game [ 'bet' ] #* len(game [ 'participants' ])

        win_amount_formatted2 = "{:,.0f}".format(total_pot).replace("," , ".")

        total_pot = game [ 'bet' ] * len(game [ 'participants' ])
        win_text = f"💰 {win_amount_formatted2} кут" if total_pot > 0 else ""
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
        await db.update_game_last_activity(winner_id)
        await db.update_user_loose(user_id , 1, bot1, ref_coin)#
        await db.update_game_last_activity(user_id)

        # Формируем ссылку на пользователя
        name_link1111 = await create_user_link(winner_id , first_name , username)
        bet_amount = game.get('bet' , 0)
        if bet_amount > 0:
            btn_create_inmine = InlineKeyboardButton(text=
                "Создать новую игру" , callback_data=f"inmine_create:{callback_query.from_user.id}:{bet_amount}")
        else:
            btn_create_inmine = InlineKeyboardButton(text="Создать новую игру" , callback_data="inmine_create")

        if total_pot > 0:
            button = InlineKeyboardButton(text=f"{bum}" , callback_data="hsudshjskfpuoaoisd")
            button2 = InlineKeyboardButton(text=f"{win_text}" , callback_data="minesbetchechtextanswer")
            button3 = InlineKeyboardButton(text=f"🏆 {first_name} " , callback_data="winnerminesanswertext")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] , [ button3 ], [ button2 ],[ btn_create_inmine ] ])
        else:
            button = InlineKeyboardButton(text=f"{bum}" , callback_data="hsudshjskfpuoaoisd")
            button2 = InlineKeyboardButton(text=f"🏆 {first_name}" , callback_data="winnerminesanswertext")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ button ],[ button2 ],[ btn_create_inmine ] ])


        messagetextmemem = random.choice(["💥"])

        await bot1.edit_message_text(
            text="<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji>",inline_message_id=inline_message_id,
            reply_markup=keyboard, parse_mode="HTML" , disable_web_page_preview=True
        )
        return

    if user_id == game['participants'][0]:
        game['board'][x] = "✔️"
    else:
        game['board'][x] = "✖️"

    game['turn'] = game['participants'][0] if game['participants'][1] == user_id else game['participants'][1]

    next_player_name = await db.get_firstname_by_user_id(game['turn'])
    next_player_emoji = "<tg-emoji emoji-id='5188216731453103384'>✔️</tg-emoji>" if game['turn'] == game['creator'] else "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji>"

    keyboard = create_game_keyboard_inmine(game['board'], game_id)
    first_name = await db.get_firstname_by_user_id(game['turn'])
    username = await db.get_username_by_user_id(game['turn'])

    # Формируем ссылку на пользователя
    name_link111111 = await create_user_link(game['turn'] , first_name , username)
    await bot1.edit_message_text(
        text=f"{next_player_emoji} <b>Ход от {name_link111111}</b>",inline_message_id=inline_message_id,
        reply_markup=keyboard, parse_mode="HTML" , disable_web_page_preview=True
    )
    gamesmine_inmine.save()


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