from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import bot1, dp
from bot.games.group_only import reject_if_private_game

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
from main import button_roulett,_format_hms,_pair_seconds_left,_pair_seconds_left,games_roulett, db, bot1, dp,get_current_time_formatted,timehistorygames,pending_context,send_invoice_to_user

from bot.funcs.func import *





@dp.message()
async def roulett(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    parts = text.split()
    if not parts:
        return

    cmd = parts[0].lower()
    if cmd not in ("дуель", "дуэль", "дуэли"):
        return

    # строго только: "<cmd>" / "<cmd> <число>"
    if len(parts) == 1:
        bet = 0
    elif len(parts) == 2:
        bet_s = parts[1]
        # строго целое число (без точек/запятых/слов)
        if not bet_s.isdigit():
            return
        bet = int(bet_s)
    else:
        return

    if bet < 0:
        return

    if await reject_if_private_game(message):
        return

    user_id = message.from_user.id

    # Проверка баланса пользователя (только если ставка > 0)
    if bet > 0:
        user_balance = await db.get_user_balance(user_id)
        if user_balance is None:
            await message.reply(
                "🛠 <b>Ошибка при получении баланса пользователя.</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return

        if bet > user_balance:
            from bot.funcs.help import callbaYTRWEQck_main  # noqa: F401

            button_help = InlineKeyboardButton(
                text="Как заработать кут?",
                callback_data="9help_btn22"
            )

            multiplier = donate_bet
            result = bet * multiplier
            bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
            bet_amount_win_formated = "{:,.0f}".format(bet).replace(",", ".")

            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"

            pending_context[user_id] = {"stars_amount": bet_amount_str, "sent": False}

            button_buy = InlineKeyboardButton(
                text=f"💫 Купить {bet_amount_win_formated} кут 💰",
                url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_buy], [button_help]])

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            await asyncio.sleep(timeoutdonate)

            if user_id in pending_context and not pending_context[user_id].get("sent"):
                stars_amount = pending_context[user_id]["stars_amount"]
                invoice_message = await send_invoice_to_user(message, stars_amount)
                pending_context[user_id]["manual_message_id"] = invoice_message.message_id
            return

    # Создание игры
    game_id = len(games_roulett) + 1
    games_roulett[game_id] = {
        "creator": user_id,
        "bet": bet,
        "participants": [user_id],
        "chat_id": None,
        "message_id": None,
    }

    join_button = InlineKeyboardButton(
        text="Присоединиться",
        callback_data=f"joinroul_{game_id}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[join_button]])

    button_roulett[game_id] = {}
    button_roulett[game_id]["keyboard_join"] = keyboard

    first_name = await db.get_firstname_by_user_id(user_id)
    username = await db.get_username_by_user_id(user_id)
    name_link = await create_user_link(user_id, first_name, username)

    try:
        if random.randint(1, 100) > 99:
            await message.answer_sticker("CAACAgIAAxkBAcC1pmeGpM5rg9R7NR1rQSP61FZGHVVhAAJjBwACAVKxSIfyvNs6UiMUNgQ")
    except Exception:
        pass

    msg = await message.reply(
        f"<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Играем в Дуэль\n<tg-emoji emoji-id='5460873384390830669'>🦖</tg-emoji> - {name_link}</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    games_roulett[game_id]["chat_id"] = msg.chat.id
    games_roulett[game_id]["message_id"] = msg.message_id
    games_roulett.save()

_roul_join_locks: Dict[int, asyncio.Lock] = {}
_roul_inflight: Set[Tuple[int, int]] = set()
MAX_ROUL_PARTICIPANTS = 2  # Дуэль - два игрока

def _get_roul_lock(game_id: int) -> asyncio.Lock:
    lock = _roul_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _roul_join_locks[game_id] = lock
    return lock

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for uid in items:
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out
@dp.callback_query(lambda c: c.data and c.data.startswith('joinroul_'))
async def Roullet_process_join(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        game_id = int(callback_query.data.split('_', 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    # Быстрая проверка существования игры
    if game_id not in games_roulett:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # Анти-дребезг: не пускаем дубли, пока идёт обработка
    inflight_key = (game_id, user_id)
    if inflight_key in _roul_inflight:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=True)
        return
    _roul_inflight.add(inflight_key)

    try:
        lock = _get_roul_lock(game_id)
        async with lock:
            # Актуальная игра внутри лока
            if game_id not in games_roulett:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = games_roulett[game_id]

            # Базовые проверки
            creator_id = int(game.get('creator'))
            if creator_id == user_id:
                await callback_query.answer("💭 Создатель не может присоединиться к своей игре!", show_alert=True)
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            # Участники - список user_id
            participants = [int(x) for x in game.get('participants', [])]
            participants = _dedupe_preserve_order_uids(participants)
            game['participants'] = participants

            # Лимит мест
            if len(participants) >= MAX_ROUL_PARTICIPANTS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            # Уже в игре?
            if user_id in participants:
                await callback_query.answer("❕ Вы уже участвуете в этой игре.", show_alert=True)
                return

            # Баланс / ставка
            bet = int(game.get('bet', 0) or 0)
            try:
                user_balance = await db.get_user_balance(user_id)
                enough = (user_balance is not None) and int(user_balance) >= bet
            except Exception:
                enough = False
            if not enough:
                await callback_query.answer("💭 Недостаточно средств для присоединения к этой игре", show_alert=True)
                return

            # ===== Анти-реф защита (строго внутри лока) =====
            parts_set = set(participants)
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id and int(inviter_id) in parts_set:
                    secs = await _pair_seconds_left(db, user_id, int(inviter_id), now=datetime.now())
                    if secs > 0:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                            "который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                            "которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(min_secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                    show_alert=True
                )
                return

            # ---- КРИТИЧЕСКАЯ ТОЧКА: добавляем атомарно ----
            # Повторно проверим лимит - вдруг другой присоединился
            if len(game['participants']) >= MAX_ROUL_PARTICIPANTS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order_uids(game['participants'])
            games_roulett.save()

            # ---- UI: готовим отображение двух игроков, ставку и кнопку старта ----
            chat_id = game.get("chat_id")
            message_id = game.get("message_id")

            # ссылки на игроков
            creator_first = await db.get_firstname_by_user_id(creator_id)
            creator_user = await db.get_username_by_user_id(creator_id)
            creator_link = await create_user_link(creator_id, creator_first, creator_user)

            opp_first = await db.get_firstname_by_user_id(user_id)
            opp_user = await db.get_username_by_user_id(user_id)
            opp_link = await create_user_link(user_id, opp_first, opp_user)

            # список участников для текста (первый - создатель, второй - оппонент)
            participants_lines = [f"<tg-emoji emoji-id='5460873384390830669'>🦖</tg-emoji> - {creator_link}"]
            if len(game['participants']) >= 2:
                participants_lines.append(f"<tg-emoji emoji-id='5461115427272796310'>🦕</tg-emoji> - {opp_link}")
            participants_text = "\n".join(f"<b>{line}</b>" for line in participants_lines)

            total_pot = bet * len(game['participants'])
            win_amount_formatted = "{:,.0f}".format(max(total_pot - bet, 0)).replace(",", ".")
            win_text = f"\n<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"startroul_{game_id}")]]
            )
            button_roulett[game_id]['keyboard_start'] = keyboard

            # безопасное редактирование
            if chat_id is not None and message_id is not None:
                try:
                    await bot1.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Играем в Дуэль</b>{win_text}\n{participants_text}",
                        reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
                    )
                except (TelegramAPIError, TelegramBadRequest) as e:
                    # игнорим "message is not modified" и прочие мелочи
                    if "message is not modified" not in str(e).lower():
                        print(f"[ROULETTE] edit_message_text error: {e}")

            await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)
            games_roulett.save()
    finally:
        _roul_inflight.discard(inflight_key)

@dp.callback_query(lambda c: c.data and c.data.startswith('startroul_'))
async def Roullet_process_start(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game_id = int(callback_query.data.split('_')[1])
    chat_id = games_roulett [ game_id ] [ "chat_id" ]
    message_id = games_roulett [ game_id ] [ "message_id" ]
    # Проверка существования игры
    if game_id not in games_roulett:
        await callback_query.answer("🛠 Игра не найдена!", show_alert=True)
        return

    game111 = games_roulett[game_id]

    if game111['creator'] != user_id:
        await callback_query.answer("💭 Только создатель может начать игру!", show_alert=True)
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
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            del games_roulett[game_id]  # Удаляем игру из активных игр
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

    shoot_button = InlineKeyboardButton(text="⚡️ Выстрелить" , callback_data=f"shootroul_{game_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ shoot_button ] ])
    button_roulett [ game_id ] [ 'keyboard_bum' ] = keyboard
    await bot1.edit_message_text(
        chat_id=chat_id , message_id=message_id ,
        text="<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> <b>Выстрелите быстрее противника!</b>" , reply_markup=keyboard , parse_mode="HTML" ,
        disable_web_page_preview=True)
    games_roulett.save()
@dp.callback_query(lambda c: c.data and c.data.startswith('shootroul_'))
async def Roullet_process_shoot(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    game_id = int(callback_query.data.split('_')[1])
    chat_id = games_roulett [ game_id ] [ "chat_id" ]
    message_id = games_roulett [ game_id ] [ "message_id" ]
    try:
        game = games_roulett[game_id]
        user_balance = await db.get_user_balance(user_id)
        if game['bet'] > user_balance:
            await callback_query.answer("💭 Недостаточно средств для участия в игре", show_alert=True)
            return

        # Проверка наличия игры и участников
        if game_id not in games_roulett or 'participants' not in games_roulett[game_id]:
            await callback_query.answer("🛠 Игра не найдена или еще не началась!", show_alert=True)
            return

        if user_id not in games_roulett[game_id]['participants']:
            await callback_query.answer("💭 Вы не участвуете в этой игре!", show_alert=True)
            return

        # Инициализация структуры для хранения результатов выстрелов
        if 'shots' not in games_roulett[game_id]:
            games_roulett[game_id]['shots'] = {games_roulett[game_id]['participants'][0]: None,
                                               games_roulett[game_id]['participants'][1]: None}

        # Проверяем, был ли уже выстрел от текущего пользователя в этой игре
        if games_roulett[game_id]['shots'][user_id] is not None:
            await callback_query.answer("❕ Вы уже сделали выстрел в этой игре!", show_alert=True)
            return
        await callback_query.answer()

        # Сохраняем результат выстрела текущего пользователя
        shot_by_user = random.choice([True, False])  # True - попадание, False - промах
        games_roulett[game_id]['shots'][user_id] = shot_by_user

        # Если текущий пользователь попал, он выигрывает
        if shot_by_user:
            winner_id = user_id
            loser_id = games_roulett[game_id]['participants'][1] if games_roulett[game_id]['participants'][0] == user_id else games_roulett[game_id]['participants'][0]

            bet = games_roulett[game_id]['bet']
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

                await db.cutehistory_plus(winner_id , bet , "+ дуэль")
                await db.cutehistory_minus(loser_id , bet , "- дуэль")
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
                # Формируем ссылку на пользователя
                name_link111 = await create_user_link(winner_id , first_name , username)

                new_message_text = f"<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>{name_link111} выстрелил первым!</b>\n{win_text}"

                # Проверка, чтобы избежать ошибки редактирования
                from main import check_bet_and_set_item
                await check_bet_and_set_item(winner_id , game [ 'bet' ])
                if callback_query.message.text != new_message_text:
                    await bot1.edit_message_text(
                        text=new_message_text , chat_id=chat_id ,
                        message_id=message_id , parse_mode="HTML" ,
                        disable_web_page_preview=True)

                # Дополнительная логика для кланов
                winner_clan_emoji = await db.get_clan_emoji3(winner_id)
                loser_clan_emoji = await db.get_clan_emoji3(loser_id)

                if winner_clan_emoji and loser_clan_emoji:
                    attack_info = await db.get_clan_attack(loser_clan_emoji)

                    if attack_info and attack_info[0] == 1 and attack_info[1] == winner_clan_emoji:
                        # Обновляем баланс кланов
                        await db.adjust_clan_coins(winner_clan_emoji, bet, 'add')
                        await db.adjust_clan_coins(loser_clan_emoji, bet, 'deduct')

                        # Проверяем баланс проигравшего клана
                        loser_clan_balance = await db.get_clan_balance(loser_clan_emoji)
                        if loser_clan_balance <= 0:
                            # Очистка данных о битве
                            await db.clear_clan_attack(winner_clan_emoji)
                            await db.clear_clan_attack(loser_clan_emoji)

                            # Отправка сообщений участникам и владельцам кланов
                            loser_clan_members, loser_clan_owner = await db.get_clan_members_and_owner(loser_clan_emoji)
                            winner_clan_members, winner_clan_owner = await db.get_clan_members_and_owner(winner_clan_emoji)

                            if loser_clan_members is None or winner_clan_members is None:
                                print("Ошибка: Не удалось получить участников кланов.")
                                return

                            # Получаем названия кланов
                            winner_clan_name = await db.get_clan_name(winner_clan_emoji)
                            loser_clan_name = await db.get_clan_name(loser_clan_emoji)

                            if winner_clan_name is None or loser_clan_name is None:
                                print("Ошибка: Не удалось получить названия кланов.")
                                return

                            # Отправляем сообщения участникам проигравшего клана
                            for member_id in loser_clan_members:
                                try:
                                    await bot1.send_message(
                                        member_id,
                                        f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>",
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    print(f"Ошибка при отправке сообщения участнику проигравшего клана {member_id}: {e}")

                            # Отправляем сообщение владельцу проигравшего клана
                            if loser_clan_owner:
                                try:
                                    await bot1.send_message(
                                        loser_clan_owner,
                                        f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>",
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    print(f"Ошибка при отправке сообщения владельцу проигравшего клана {loser_clan_owner}: {e}")

                            # Отправляем сообщения участникам победившего клана
                            for member_id in winner_clan_members:
                                try:
                                    await bot1.send_message(
                                        member_id,
                                        f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>",
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    print(f"Ошибка при отправке сообщения участнику победившего клана {member_id}: {e}")

                            # Отправляем сообщение владельцу победившего клана
                            if winner_clan_owner:
                                try:
                                    await bot1.send_message(
                                        winner_clan_owner,
                                        f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>",
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    print(f"Ошибка при отправке сообщения владельцу победившего клана {winner_clan_owner}: {e}")

            # Удаляем игру из словаря после завершения
            del games_roulett[game_id]
            return

        # Сообщение для текущего пользователя о холостом выстреле
        #await callback_query.answer("❕ Холостой выстрел")

        # Проверка результатов выстрелов обоих участников
        user1_id = games_roulett[game_id]['participants'][0]
        user2_id = games_roulett[game_id]['participants'][1]

        user1_shot = games_roulett[game_id]['shots'][user1_id]
        user2_shot = games_roulett[game_id]['shots'][user2_id]

        # Если оба результата известны и оба промахнулись
        if user1_shot is False and user2_shot is False:
            new_message_text = "<tg-emoji emoji-id='5434121252874756456'>🕊</tg-emoji> <b>Ничья! Оба игрока выстрелили холостыми патронами.</b>"

            # Проверка, чтобы избежать ошибки редактирования
            if callback_query.message.text != new_message_text:
                await bot1.edit_message_text(text=new_message_text,
                    chat_id=chat_id,
                    message_id=message_id,parse_mode="HTML", disable_web_page_preview=True
                )

            # Удаляем игру из словаря после завершения
            del games_roulett[game_id]

    except Exception as e:
        print(f"Ошибка в обработчике Roullet_process_shoot: {e}")
    games_roulett.save()
