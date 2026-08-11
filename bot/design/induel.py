
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
from main import games_roulettinduel,_format_hms,_pair_seconds_left,_pair_seconds_left, inline_add_or_update_user_info,db, bot1, dp,get_current_time_formatted,timehistorygames


import random



@dp.callback_query(lambda c: c.data.startswith('induel_create'))
async def induel_create_game_callback(callback_query: types.CallbackQuery):

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
    # Создание игры
    game_id = len(games_roulettinduel) + 1
    games_roulettinduel [ game_id ] = {'creator': user_id , 'bet': bet_amount , 'participants': [ user_id ]}

    creator_name = await db.get_firstname_by_user_id(user_id)
    win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".")



    join_button = InlineKeyboardButton(text="Присоединиться" , callback_data=f"joinroulinduel_{game_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ join_button ] ])
    first_name = await db.get_firstname_by_user_id(user_id)
    username = await db.get_username_by_user_id(user_id)

    # Формируем ссылку на пользователя
    name_link = await create_user_link(user_id , first_name , username)
    win_amount_formatted = "{:,.0f}".format(bet_amount).replace("," , ".")
    bet_message = f"<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji> Ставка : {win_amount_formatted} кут\n" if bet_amount > 0 else ""
    if "inline_message_id" not in games_roulettinduel [ game_id ]:
        games_roulettinduel [ game_id ] [ "inline_message_id" ] = callback_query.inline_message_id
    inline_message_id = games_roulettinduel [ game_id ] [ "inline_message_id" ]
    await bot1.edit_message_text(
        f"<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Играем в Дуэль\n{bet_message}<tg-emoji emoji-id='5460873384390830669'>🦖</tg-emoji> - {name_link}</b>" ,inline_message_id=inline_message_id,
        reply_markup=keyboard , parse_mode="HTML", disable_web_page_preview=True)
    games_roulettinduel.save()

_roul_induel_locks: Dict[int, asyncio.Lock] = {}
_roul_induel_inflight: Set[Tuple[int, int]] = set()
MAX_ROUL_INDUEL_PLAYERS = 2  # дуэль

def _get_roul_induel_lock(game_id: int) -> asyncio.Lock:
    lock = _roul_induel_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _roul_induel_locks[game_id] = lock
    return lock

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set(); out = []
    for uid in items:
        uid = int(uid)
        if uid not in seen:
            seen.add(uid); out.append(uid)
    return out
@dp.callback_query(lambda c: c.data and c.data.startswith('joinroulinduel_'))
async def induel_Roullet_process_join(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    # парсим game_id
    try:
        game_id = int(callback_query.data.split('_', 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    # есть ли игра
    if game_id not in games_roulettinduel:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # анти-дребезг
    inflight_key = (game_id, user_id)
    if inflight_key in _roul_induel_inflight:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=True)
        return
    _roul_induel_inflight.add(inflight_key)

    try:
        lock = _get_roul_induel_lock(game_id)
        async with lock:
            # актуальная игра внутри лока
            game = games_roulettinduel.get(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            inline_message_id = game.get("inline_message_id")

            # профиль (не падаем, если не обновится)
            try:
                first_name_raw = callback_query.from_user.first_name or "Игрок"
                first_name = re.sub(r'[<>/{}"]', '', first_name_raw)
                username = callback_query.from_user.username
                await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
            except Exception:
                pass

            # базовые проверки
            creator_id = int(game.get("creator"))
            if user_id == creator_id:
                await callback_query.answer("💭 Создатель не может присоединиться к своей игре!", show_alert=True)
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            # нормализуем участников и дедупим
            participants = _dedupe_preserve_order_uids(list(game.get("participants", [])))
            game["participants"] = participants

            if len(participants) >= MAX_ROUL_INDUEL_PLAYERS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            if user_id in participants:
                await callback_query.answer("❕ Вы уже участвуете в этой игре.", show_alert=True)
                return

            # баланс / ставка
            bet_amount = int(game.get("bet", 0) or 0)
            try:
                user_balance = await db.get_user_balance(user_id)
                enough = (user_balance is not None) and int(user_balance) >= bet_amount
            except Exception:
                enough = False
            if not enough:
                await callback_query.answer("💭 Недостаточно средств для игры.", show_alert=True)
                return

            # ===== анти-реф защита (строго внутри лока) =====
            # 0) очистка устаревших записей
            try:
                if hasattr(db, "remove_expired_refout"):
                    await db.remove_expired_refout()
                else:
                    await db.cleanup_expired_refout()
            except Exception:
                pass

            parts_set = set(game["participants"])
            parts_set.add(creator_id)

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
                await callback_query.answer("💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471", show_alert=True)
                return

            # ---- критическая точка: добавляем атомарно ----
            if len(game["participants"]) >= MAX_ROUL_INDUEL_PLAYERS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            game["participants"].append(user_id)
            game["participants"] = _dedupe_preserve_order_uids(game["participants"])
            games_roulettinduel.save()

            # ---- UI: текст и кнопка старта ----
            # ссылки на обоих игроков
            creator_first = await db.get_firstname_by_user_id(creator_id)
            creator_user = await db.get_username_by_user_id(creator_id)
            creator_link = await create_user_link(creator_id, creator_first, creator_user)

            opp_first = await db.get_firstname_by_user_id(user_id)
            opp_user = await db.get_username_by_user_id(user_id)
            opp_link = await create_user_link(user_id, opp_first, opp_user)

            # сообщение о ставке
            bet_message = f"<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji> <b>Ставка : {bet_amount:,.0f} кут</b>\n".replace(",", ".") if bet_amount > 0 else ""

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"startroulinduel_{game_id}")]]
            )

            text = f"<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Игра заполнена</b>\n{bet_message}<b><tg-emoji emoji-id='5460873384390830669'>🦖</tg-emoji> - {creator_link}\n<tg-emoji emoji-id='5461115427272796310'>🦕</tg-emoji> - {opp_link}</b>"

            try:
                await bot1.edit_message_text(
                    text=text,
                    inline_message_id=inline_message_id,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[ROUL_INDUEL] edit_message_text error: {e}")

            await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)
            games_roulettinduel.save()

    except Exception as e:
        print(f"[ROUL_INDUEL] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _roul_induel_inflight.discard(inflight_key)

@dp.callback_query(lambda c: c.data and c.data.startswith('startroulinduel_'))
async def induel_Roullet_process_start(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game_id = int(callback_query.data.split('_')[1])
    inline_message_id = games_roulettinduel [ game_id ] [ "inline_message_id" ]
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username , db , start_balance)

    # Проверка существования игры
    if game_id not in games_roulettinduel:
        await callback_query.answer("🛠 Игра не найдена!", show_alert=True)
        return

    game111 = games_roulettinduel[game_id]

    if game111['creator'] != user_id:
        await callback_query.answer("💭 Только создатель может начать игру!", show_alert=True)
        return
    bet_amount = game111.get('bet' , 0)

    # Если ставка больше 0, проверяем, достаточно ли у игрока денег
    if bet_amount > 0:
        user_balance = await db.get_user_balance(
            callback_query.from_user.id)  # Предполагается, что баланс хранится в поле 'balance'
        if user_balance < bet_amount:
            await callback_query.answer("💭 Недостаточно средств для игры." , show_alert=True)
            return
    # Проверка баланса всех участников
    for participant_id in game111['participants']:
        current_balance = await db.get_user_balance(participant_id)

        # Если у участника недостаточно средств, останавливаем игру
        if current_balance is None or current_balance < game111['bet']:
            first_name = await db.get_firstname_by_user_id(participant_id)
            username = await db.get_username_by_user_id(participant_id)

            # Формируем сообщение об остановке игры
            insufficient_user_link = await create_user_link(participant_id, first_name, username)
            message_text = f"⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>"
            await bot1.edit_message_text(
                text=message_text,inline_message_id=inline_message_id,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            del games_roulettinduel[game_id]  # Удаляем игру из активных игр
            return  # Завершаем выполнение функции

    # Проверяем баланс создателя игры
    user_balance = await db.get_user_balance(user_id)
    if game111['bet'] > user_balance:
        await callback_query.answer("💭 Недостаточно средств для старта игры", show_alert=True)
        return

    participants = game111['participants']

    if len(participants) < 2:
        await callback_query.answer("💭 Недостаточно участников для начала игры!", show_alert=True)
        return

    await callback_query.answer()


    shoot_button = InlineKeyboardButton(text="⚡️ Выстрелить" , callback_data=f"shootroulinduel_{game_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ shoot_button ] ])

    await bot1.edit_message_text(
        f"<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Выстрелите быстрее противника!</b>",inline_message_id=inline_message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
    games_roulettinduel.save()
@dp.callback_query(lambda c: c.data and c.data.startswith('shootroulinduel_'))
async def induel_Roullet_process_shoot(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game_id = int(callback_query.data.split('_')[1])
    inline_message_id = games_roulettinduel [ game_id ] [ "inline_message_id" ]
    first_name = re.sub(r'[<>/{}"]' , '' , callback_query.from_user.first_name)
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username , db , start_balance)

    try:
        game = games_roulettinduel[game_id]
        user_balance = await db.get_user_balance(user_id)
        if game['bet'] > user_balance:
            await callback_query.answer("💭 Недостаточно средств для участия в игре", show_alert=True)
            return

        # Проверка наличия игры и участников
        if game_id not in games_roulettinduel or 'participants' not in games_roulettinduel[game_id]:
            await callback_query.answer("🛠 Игра не найдена или еще не началась!", show_alert=True)
            return

        if user_id not in games_roulettinduel[game_id]['participants']:
            await callback_query.answer("💭 Вы не участвуете в этой игре!", show_alert=True)
            return

        # Инициализация структуры для хранения результатов выстрелов
        if 'shots' not in games_roulettinduel[game_id]:
            games_roulettinduel[game_id]['shots'] = {games_roulettinduel[game_id]['participants'][0]: None,
                                               games_roulettinduel[game_id]['participants'][1]: None}

        # Проверяем, был ли уже выстрел от текущего пользователя в этой игре
        if games_roulettinduel[game_id]['shots'][user_id] is not None:
            await callback_query.answer("❕ Вы уже сделали выстрел в этой игре!", show_alert=True)
            return

        # Сохраняем результат выстрела текущего пользователя
        shot_by_user = random.choice([True, False])  # True - попадание, False - промах
        games_roulettinduel[game_id]['shots'][user_id] = shot_by_user

        # Если текущий пользователь попал, он выигрывает
        if shot_by_user:
            winner_id = user_id
            loser_id = games_roulettinduel[game_id]['participants'][1] if games_roulettinduel[game_id]['participants'][0] == user_id else games_roulettinduel[game_id]['participants'][0]

            bet = games_roulettinduel[game_id]['bet']
            bet2 = bet * 2  # Умножение ставки на два

            # Обновление балансов
            winner_balance = await db.get_user_balance(winner_id)
            loser_balance = await db.get_user_balance(loser_id)

            if winner_balance is not None and loser_balance is not None:
                new_winner_balance = winner_balance + bet
                new_loser_balance = loser_balance - bet

                await db.update_user_balance(winner_id, new_winner_balance)
                await db.update_user_balance(loser_id, new_loser_balance)
                await db.touch_balance_last_active(winner_id , set_active_status=True)
                await db.touch_balance_last_active(loser_id , set_active_status=True)
                await db.cutehistory_plus(winner_id , bet , "инлайн дуэль")
                await db.cutehistory_minus(loser_id , bet , "инлайн дуэль")
                await db.update_user_wins(winner_id , 1, bot1, ref_coin)
                await db.update_user_winamount(winner_id , bet)#
                await db.update_user_loose(loser_id , 1, bot1, ref_coin)#
                await db.update_game_last_activity(winner_id)
                await db.update_game_last_activity(loser_id)
                #await db.add_commissiondue(winner_id, bet, 'user')
                #await db.add_commissiondue(loser_id, bet, 'bot')

                winner_name = await db.get_firstname_by_user_id(winner_id)
                win_amount_formatted = "{:,.0f}".format(bet).replace(",", ".")

                win_text = f"<tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if bet > 0 else ""

                await db.add_xp_to_games(winner_id)
                first_name = await db.get_firstname_by_user_id(winner_id)
                username = await db.get_username_by_user_id(winner_id)

                # Формируем ссылку на пользователя
                name_link111 = await create_user_link(winner_id , first_name , username)
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
                new_message_text = f"<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>{name_link111} выстрелил первым!</b>\n{win_text}"

                # Проверка, чтобы избежать ошибки редактирования
                from main import check_bet_and_set_item
                await check_bet_and_set_item(winner_id , game [ 'bet' ])

                # Проверка, чтобы message не был None
                #if callback_query.message and callback_query.message.text != new_message_text:
                bet_amount = game.get('bet' , 0)
                if bet_amount > 0:
                    btn_create_inmine = InlineKeyboardButton(text=
                        "Создать новую игру" ,
                        callback_data=f"induel_create:{callback_query.from_user.id}:{bet_amount}")
                else:
                    btn_create_inmine = InlineKeyboardButton(text="Создать новую игру" , callback_data="induel_create")
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[ [ btn_create_inmine ] ])
                await bot1.edit_message_text(
                    new_message_text , inline_message_id=inline_message_id ,reply_markup=keyboard,
                    parse_mode=ParseMode.HTML , disable_web_page_preview=True)


            # Удаляем игру из словаря после завершения
            del games_roulettinduel[game_id]
            return

        # Сообщение для текущего пользователя о холостом выстреле
        await callback_query.answer("❕ Холостой выстрел", show_alert=True)

        # Проверка результатов выстрелов обоих участников
        user1_id = games_roulettinduel[game_id]['participants'][0]
        user2_id = games_roulettinduel[game_id]['participants'][1]

        user1_shot = games_roulettinduel[game_id]['shots'][user1_id]
        user2_shot = games_roulettinduel[game_id]['shots'][user2_id]

        # Если оба результата известны и оба промахнулись
        if user1_shot is False and user2_shot is False:
            new_message_text = "<tg-emoji emoji-id='5434121252874756456'>🕊</tg-emoji> <b>Ничья! Оба игрока выстрелили холостыми патронами.</b>"

            # Проверка, чтобы избежать ошибки редактирования
            #if callback_query.message.text != new_message_text:
            bet_amount = game.get('bet' , 0)
            if bet_amount > 0:
                btn_create_inmine = InlineKeyboardButton(text=
                    "Создать новую игру" , callback_data=f"induel_create:{callback_query.from_user.id}:{bet_amount}")
            else:
                btn_create_inmine = InlineKeyboardButton(text="Создать новую игру" , callback_data="induel_create")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ btn_create_inmine ] ])
            await bot1.edit_message_text(
                new_message_text,inline_message_id=inline_message_id,reply_markup=keyboard,parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )

            # Удаляем игру из словаря после завершения
            del games_roulettinduel[game_id]

    except Exception as e:
        print(f"Ошибка в обработчике Roullet_process_shoot: {e}")

    games_roulettinduel.save()