
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
from main import gamesknb,_format_hms,_pair_seconds_left,_pair_seconds_left,button_gamesknb, db, bot1, dp,get_current_time_formatted,timehistorygames,pending_context,send_invoice_to_user


from bot.funcs.func import *


global gamenum



@dp.message()
async def knb(message: Message):
    try:
        if not message.text:
            return

        text = message.text.strip()
        parts = text.split()
        if not parts:
            return

        words = ("камень", "ножницы", "бумага")

        bet = 0
        bet_str = None

        p0 = parts[0].lower()

        # ✅ "кнб" / "кнб <число>"
        if p0 == "кнб":
            if len(parts) == 1:
                bet = 0
            elif len(parts) == 2:
                bet_s = parts[1]
                if not bet_s.isdigit():
                    return
                bet_str = bet_s
            else:
                return

        # ✅ "<камень|ножницы|бумага>" (1 слово) или 3 слова из списка
        elif len(parts) in (1, 3) and all(p.lower() in words for p in parts):
            bet = 0

        # ✅ 4 слова: первые 3 из words + ставка числом
        elif len(parts) == 4 and all(p.lower() in words for p in parts[:3]):
            bet_s = parts[3]
            if not bet_s.isdigit():
                return
            bet_str = bet_s

        else:
            return

        if bet_str is not None:
            bet = int(bet_str)
        else:
            bet = 0

        if bet < 0:
            return

        if await reject_if_private_game(message):
            return

        creator_id = message.from_user.id

        # Проверка баланса (только если ставка > 0)
        if bet > 0:
            creator_balance = await db.get_user_balance(creator_id)
            if creator_balance is None:
                return
            if int(creator_balance) < int(bet):
                from bot.funcs.help import callbaYTRWEQck_main  # noqa: F401

                button_help = InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
                bet_amount_win_formated = "{:,.0f}".format(bet).replace(",", ".")

                try:
                    bot_username = await get_bot_username_by_token(TOKEN)
                except Exception:
                    bot_username = "CuteGamingBot"

                user_id = creator_id
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

        # Генерация ID игры
        game_id = message.message_id

        gamesknb[game_id] = {
            "creator": creator_id,
            "bet": bet,
            "participants": [creator_id],
            "choices": {},
            "chat_id": None,
            "message_id": None,
        }

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinknb:{game_id}")]
            ]
        )
        button_gamesknb[game_id] = {}
        button_gamesknb[game_id]["keyboard_join"] = keyboard

        first_name = await db.get_firstname_by_user_id(creator_id)
        username = await db.get_username_by_user_id(creator_id)
        name_link1 = await create_user_link(creator_id, first_name, username)

        msg = await message.reply(
            f"<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> <b>Играем в камень-ножницы-бумага\n- {name_link1}</b>",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        gamesknb[game_id]["chat_id"] = msg.chat.id
        gamesknb[game_id]["message_id"] = msg.message_id

        try:
            gamesknb.save()
        except Exception:
            pass

    except Exception as e:
        print(f"Ошибка в knb: {e}")



_knb_join_locks: Dict[int, asyncio.Lock] = {}
_knb_inflight: Set[Tuple[int, int]] = set()
MAX_KNB_PLAYERS = 2  # KNB - дуэль

def _get_knb_lock(game_id: int) -> asyncio.Lock:
    lock = _knb_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _knb_join_locks[game_id] = lock
    return lock

def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set(); out = []
    for x in items:
        if x not in seen:
            seen.add(x); out.append(x)
    return out
@dp.callback_query(lambda c: c.data.startswith('joinknb:'))
async def knb_join_game_callback(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        try:
            game_id = int(callback_query.data.split(':', 1)[1])
        except Exception:
            await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
            return

        # быстрый отбой, если игры нет
        if game_id not in gamesknb:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
            return

        # анти-дребезг: не пускаем повторы, пока идёт обработка
        inflight_key = (game_id, user_id)
        if inflight_key in _knb_inflight:
            await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=True)
            return
        _knb_inflight.add(inflight_key)

        lock = _get_knb_lock(game_id)
        async with lock:
            # актуальное состояние - внутри лока
            if game_id not in gamesknb:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamesknb[game_id]
            chat_id = game.get("chat_id")
            message_id = game.get("message_id")

            # базовые проверки
            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            if user_id == int(game.get('creator')):
                await callback_query.answer("❕ Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            # нормализуем участников и убираем дубли
            participants = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
            game['participants'] = participants

            if len(participants) >= MAX_KNB_PLAYERS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            if user_id in participants:
                await callback_query.answer("❕ Вы уже участвуете в этой игре.", show_alert=True)
                return

            # баланс / ставка
            bet = int(game.get('bet', 0) or 0)
            try:
                current_balance = await db.get_user_balance(user_id)
                enough = (current_balance is not None) and int(current_balance) >= bet
            except Exception:
                enough = False
            if not enough:
                await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
                return

            # === Анти-реф защита (строго внутри лока) ===
            parts_set = set(game['participants'])
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
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=datetime.now())
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

            # ---- КРИТИЧЕСКАЯ ТОЧКА: добавляем атомарно ----
            if len(game['participants']) >= MAX_KNB_PLAYERS:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order(game['participants'])
            gamesknb.save()

            # ---- UI ----
            # список участников с кликабельными ссылками
            participants_names = []
            for uid in game['participants']:
                first_name = await db.get_firstname_by_user_id(uid)
                username = await db.get_username_by_user_id(uid)
                name_link = await create_user_link(uid, first_name, username)
                participants_names.append(f"<b>- {name_link}</b>")
            participants_text = "\n".join(participants_names)

            # кнопка старта
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"startknb:{game_id}")]]
            )
            button_gamesknb[game_id]['keyboard_start'] = keyboard

            total_pot = bet * len(game['participants'])
            win_amount_formatted = "{:,.0f}".format(max(total_pot - bet, 0)).replace(",", ".")
            win_text = f"\n<tg-emoji emoji-id='5195369389599265575'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""

            if chat_id is not None and message_id is not None:
                try:
                    await bot1.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> <b>Играем в камень-ножницы-бумага</b>{win_text}\n{participants_text}",
                        reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
                    )
                except (TelegramAPIError, TelegramBadRequest) as e:
                    if "message is not modified" not in str(e).lower():
                        print(f"[KNB] edit_message_text error: {e}")

            await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)

    except Exception as e:
        print(f"[KNB] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _knb_inflight.discard((game_id, callback_query.from_user.id))
        try:
            gamesknb.save()
        except Exception:
            pass
@dp.callback_query(lambda c: c.data.startswith('startknb:'))
async def knb_start_game_callback(callback_query: CallbackQuery):

    try:
        game_id = int(callback_query.data.split(':')[1])
        user_id = callback_query.from_user.id
        chat_id = gamesknb [ game_id ] [ "chat_id" ]
        message_id = gamesknb [ game_id ] [ "message_id" ]
        if game_id not in gamesknb:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
            return

        game = gamesknb[game_id]

        if user_id != game['creator']:
            await callback_query.answer("💭 Только создатель игры может начать игру.", show_alert=True)
            return

        if len(game['participants']) < 2:
            await callback_query.answer("💭 Невозможно начать игру. Недостаточно участников.", show_alert=True)
            return

        bet = game['bet']
        current_balance = await db.get_user_balance(user_id)
        if current_balance is None or current_balance < bet:
            await callback_query.answer("💭 Недостаточно средств для старта игры.", show_alert=True)
            return

        await callback_query.answer()

        choices_keyboard = InlineKeyboardMarkup(
            row_width=3 ,
            inline_keyboard=[ [
                InlineKeyboardButton(text="🪨 Камень" , callback_data=f"chooseknb:{game_id}:rock"),
                InlineKeyboardButton(text="✂️ Ножницы" , callback_data=f"chooseknb:{game_id}:scissors"),
                InlineKeyboardButton(text="📃 Бумага" , callback_data=f"chooseknb:{game_id}:paper") ] ])

        for participant_id in game [ 'participants' ]:
            current_balance = await db.get_user_balance(participant_id)

            # Если у участника недостаточно средств, останавливаем игру
            if current_balance is None or current_balance < game [ 'bet' ]:
                first_name = await db.get_firstname_by_user_id(participant_id)
                username = await db.get_username_by_user_id(participant_id)

                # Формируем сообщение об остановке игры
                insufficient_user_link = await create_user_link(participant_id , first_name , username)
                message_text = f"⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>"
                await bot1.edit_message_text(
                    chat_id=chat_id , message_id=message_id ,
                    text=message_text , parse_mode="HTML" , disable_web_page_preview=True)
                del gamesknb [ game_id ]  # Удаляем игру из активных игр
                return  # Завершаем выполнение функции
        button_gamesknb [ game_id ] [ 'keyboard_ASFAS' ] = choices_keyboard
        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> <b>Пора сделать выбор!</b>",
            reply_markup=choices_keyboard,
            parse_mode="HTML",
                disable_web_page_preview=True
        )


    except Exception as e:
        print(f"Ошибка в start_game_callback: {e}")
    gamesknb.save()
@dp.callback_query(lambda c: c.data.startswith('chooseknb:'))
async def knb_choose_callback(callback_query: CallbackQuery):

    try:
        data = callback_query.data.split(':')
        game_id = int(data[1])
        choice = data[2]
        user_id = callback_query.from_user.id
        chat_id = gamesknb [ game_id ] [ "chat_id" ]
        message_id = gamesknb [ game_id ] [ "message_id" ]
        if game_id not in gamesknb:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
            return

        game = gamesknb[game_id]

        if user_id not in game['participants']:
            await callback_query.answer("💭 Вы не участвуете в этой игре.", show_alert=True)
            return

        if user_id in game['choices']:
            await callback_query.answer("❕ Вы уже сделали свой выбор!", show_alert=True)
            return

        # Проверка текущего баланса пользователя
        current_balance = await db.get_user_balance(user_id)  # Обязательно используйте await

        if current_balance is None or current_balance < game['bet']:
            first_name = await db.get_firstname_by_user_id(user_id)
            username = await db.get_username_by_user_id(user_id)

            # Формируем сообщение об остановке игры
            insufficient_user_link = await create_user_link(user_id, first_name, username)
            message_text = f"⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>"
            await bot1.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            del gamesknb[game_id]  # Удаляем игру из активных игр
            return  # Завершаем выполнение функции

        game['choices'][user_id] = choice

        await callback_query.answer(f"{get_choice_text(choice)}", show_alert=True)

        if len(game['choices']) == len(game['participants']):
            await declare_winner(chat_id, message_id, game_id)
        else:
            await callback_query.answer("❕ Вы сделали свой выбор!", show_alert=True)
    except Exception as e:
        print(f"Ошибка в choose_callback: {e}")
    gamesknb.save()
def get_choice_text(choice):
    if choice == 'rock':
        return 'камень'
    elif choice == 'scissors':
        return 'ножницы'
    elif choice == 'paper':
        return 'бумага'
    else:
        return choice  # handle unexpected choices here if any


def describe_move(user_choice, winner_choice):
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


async def declare_winner(chat_id , message_id , game_id):
    try:
        game = gamesknb [ game_id ]
        choices = game [ 'choices' ]

        results = [ ]
        explanations = [ ]
        for user_id , user_choice in choices.items():
            try:
                user = await bot1.get_chat_member(chat_id , user_id)

                first_name = await db.get_firstname_by_user_id(user_id)
            except Exception as e:
                print(f"Ошибка при получении пользователя с ID {user_id}: {e}")
                continue

            if user_choice == 'rock':
                choice_text = 'камень'
            elif user_choice == 'scissors':
                choice_text = 'ножницы'
            elif user_choice == 'paper':
                choice_text = 'бумагу'
            else:
                choice_text = user_choice  # handle unexpected choices here if any


            if user_choice == 'rock':
                choice_text1 = "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji>"
            elif user_choice == 'scissors':
                choice_text1 = "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>"
            elif user_choice == 'paper':
                choice_text1 = "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji>"
            else:
                choice_text1 = user_choice  # handle unexpected choices here if any


            # Формирование строки с результатами, включая ссылки на профили
            first_name = await db.get_firstname_by_user_id(user_id)
            username = await db.get_username_by_user_id(user_id)

            # Формируем ссылку на пользователя
            name_link1 = await create_user_link(user_id , first_name , username)

            results.append(f"<b>- {choice_text1} {name_link1} выбрал(-а) {choice_text}</b>")

        winner_id = determine_winner(choices)
        if winner_id is not None:
            try:
                winner_choice = choices [ winner_id ]
                winner_user = await bot1.get_chat_member(chat_id , winner_id)

                first_name = await db.get_firstname_by_user_id(winner_id)
                win_description = describe_move(winner_choice)
                total_pot = game [ 'bet' ] * len(game [ 'participants' ])
                win_amount = total_pot
                results_text = "\n".join(results)
                win_amount_formatted = "{:,.0f}".format(total_pot - game [ 'bet' ]).replace("," , ".")
                first_name = await db.get_firstname_by_user_id(winner_id)
                username = await db.get_username_by_user_id(winner_id)

                # Формируем ссылку на пользователя
                name_link1111= await create_user_link(winner_id , first_name , username)
                winner_link = f"<b>{name_link1111}</b>"
                bet = game [ 'bet' ]



                # Обновление балансов победителя и проигравших
                for user_id , user_choice in choices.items():

                    loser_id = user_id
                    winner_clan_emoji = await db.get_clan_emoji3(winner_id)
                    loser_clan_emoji = await db.get_clan_emoji3(loser_id)

                    if winner_clan_emoji and loser_clan_emoji:
                        attack_info = await db.get_clan_attack(loser_clan_emoji)

                        if attack_info and attack_info [ 0 ] == 1 and attack_info [ 1 ] == winner_clan_emoji:
                            # Обновляем баланс кланов
                            await db.adjust_clan_coins(winner_clan_emoji , bet , 'add')
                            await db.adjust_clan_coins(loser_clan_emoji , bet , 'deduct')

                            # Проверяем баланс проигравшего клана
                            loser_clan_balance = await db.get_clan_balance(loser_clan_emoji)
                            if loser_clan_balance <= 0:
                                # Очистка данных о битве
                                await db.clear_clan_attack(winner_clan_emoji)
                                await db.clear_clan_attack(loser_clan_emoji)

                                # Отправка сообщений участникам и владельцам кланов
                                loser_clan_members , loser_clan_owner = await db.get_clan_members_and_owner(
                                    loser_clan_emoji)
                                winner_clan_members , winner_clan_owner = await db.get_clan_members_and_owner(
                                    winner_clan_emoji)

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
                                            member_id ,
                                            f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>" ,
                                            parse_mode="HTML")
                                    except Exception as e:
                                        print(
                                            f"Ошибка при отправке сообщения участнику проигравшего клана {member_id}: {e}")

                                # Отправляем сообщение владельцу проигравшего клана
                                if loser_clan_owner:
                                    try:
                                        await bot1.send_message(
                                            loser_clan_owner ,
                                            f"🚩 Ваш клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b> проиграл битву против клана <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b>" ,
                                            parse_mode="HTML")
                                    except Exception as e:
                                        print(
                                            f"Ошибка при отправке сообщения владельцу проигравшего клана {loser_clan_owner}: {e}")

                                # Отправляем сообщения участникам победившего клана
                                for member_id in winner_clan_members:
                                    try:
                                        await bot1.send_message(
                                            member_id ,
                                            f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>" ,
                                            parse_mode="HTML")
                                    except Exception as e:
                                        print(
                                            f"Ошибка при отправке сообщения участнику победившего клана {member_id}: {e}")

                                # Отправляем сообщение владельцу победившего клана
                                if winner_clan_owner:
                                    try:
                                        await bot1.send_message(
                                            winner_clan_owner ,
                                            f"🎉 Ваш клан <b><code>{winner_clan_emoji}</code> {winner_clan_name}</b> победил клан <b><code>{loser_clan_emoji}</code> {loser_clan_name}</b>" ,
                                            parse_mode="HTML")
                                    except Exception as e:
                                        print(
                                            f"Ошибка при отправке сообщения владельцу победившего клана {winner_clan_owner}: {e}")
                    if user_id == winner_id:
                        balance = await db.get_user_balance(user_id)
                        await db.update_user_balance(user_id ,balance + win_amount - game [ 'bet' ])
                        await db.touch_balance_last_active(user_id , set_active_status=True)
                        await db.cutehistory_plus(user_id , win_amount - game [ 'bet' ] , "+ кнб")
                        #await db.add_commissionknb(user_id , win_amount - game [ 'bet' ] , 'user')

                    else:
                        balance = await db.get_user_balance(user_id)
                        await db.update_user_balance(user_id ,balance - game [ 'bet' ])
                        await db.touch_balance_last_active(user_id , set_active_status=True)
                        await db.cutehistory_minus(user_id , game [ 'bet' ] , "- кнб")
                        #await db.add_commissionknb(user_id , game [ 'bet' ] , 'bot')


                await db.update_user_wins(winner_id , 1, bot1, ref_coin)
                await db.update_user_winamount(winner_id , win_amount - game [ 'bet' ])#
                await db.update_user_loose(user_id , 1, bot1, ref_coin)#
                await db.update_game_last_activity(winner_id)
                await db.update_game_last_activity(user_id)

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
                win_text = f"\n<tg-emoji emoji-id='5195369389599265575'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""
                from main import check_bet_and_set_item
                await check_bet_and_set_item(winner_id , game [ 'bet' ])
                await bot1.edit_message_text(
                    chat_id=chat_id , message_id=message_id ,
                    text=f"<b>{win_description}\n\n<tg-emoji emoji-id='5262906070996642883'>🏆</tg-emoji> {winner_link}{win_text}\n\n{results_text}</b>" ,
                    parse_mode="HTML",disable_web_page_preview=True)
                del gamesknb [ game_id ]
            except Exception as e:
                print(f"Ошибка при отображении результатов игры: {e}")
                await bot1.edit_message_text(
                    chat_id=chat_id , message_id=message_id ,
                    text=f"{results_text}\n\n✖️ Ошибка при отображении победителя" , parse_mode="HTML",disable_web_page_preview=True)
                del gamesknb [ game_id ]
        else:
            results_text = "\n".join(results)
            await bot1.edit_message_text(
                chat_id=chat_id , message_id=message_id , text=f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji> <b>Ничья!</b>\n\n{results_text}" ,
                parse_mode="HTML",disable_web_page_preview=True)
            del gamesknb [ game_id ]
    except Exception as e:
        print(f"Ошибка в declare_winner: {e}")

def determine_winner(choices):
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

def describe_move(choice):
    if choice == 'rock':
        return "<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji> Камень разбил ножницы"
    elif choice == 'scissors':
        return "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Ножницы разрезали бумагу"
    elif choice == 'paper':
        return "<tg-emoji emoji-id='5262707329974954117'>🗒</tg-emoji> Бумага накрыла камень"
    else:
        return f"<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> сделал неожиданный ход {choice}"