from aiogram import Bot, Dispatcher, types
from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from main import *

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from bot.db_create.db import *
import random
import json

from bot.funcs.func import *



def generate_rows():
    listt = [ ]
    for t in range(7):
        listt.append([ 'x' ] * 7)  # Создание списка 7x7, заполненного 'x'

    value = 111
    for f in range(7):
        for t in range(3):
            rand_v = random.randint(0 , 6)  # Генерация случайного числа от 0 до 6
            if value != rand_v:
                listt [ f ] [ rand_v ] = "$"  # Установка символа '$' в случайные позиции
                value = rand_v
            else:
                rand_v = random.randint(0 , 6)
                listt [ f ] [ rand_v ] = "$"
                value = rand_v

        listt [ f ] [ random.randint(0 , 6) ] = "$$"  # Установка символа '$$' в случайные позиции

    listt [ 3 ] [ 3 ] = "0"  # Установка "0" в центре списка
    return listt


# Функция для преобразования двумерного списка в одномерный
def split_list(listt):
    new_list = [ ]
    for t in listt:
        for f in t:
            new_list.append(f)
    return new_list


# Функция для генерации клавиатуры с кнопками
def generate_inline_buttons(listt):
    keyboard = InlineKeyboardMarkup(row_width=7)
    buttons = [ ]

    if "0" in listt:
        a = listt.index("0")  # Находим индекс центральной кнопки
        positions = [ a - 1 , a + 1 , a - 7 , a + 7 ]  # Определяем позиции соседних кнопок

    for i in range(0 , 49):
        if "0" in listt and listt [ i ] == "0":
            button = InlineKeyboardButton(
                text=" " , callback_data=f'button_{i}')  # Создание кнопки для центральной ячейки
            buttons.append(button)
        elif listt [ i ] == "X":
            button = InlineKeyboardButton(text=" " , callback_data=f'button_{i}')  # Создание кнопки с символом '$'
            buttons.append(button)
        elif listt [ i ] == "X$":
            button = InlineKeyboardButton(text="🦋" , callback_data=f'button_{i}')  # Создание кнопки с символом '$$'
            buttons.append(button)
        elif i in positions:
            if i == positions [ 0 ]:
                button = InlineKeyboardButton(text="◀" , callback_data=f'button_{i}')  # Кнопка "◀"
                buttons.append(button)
            elif i == positions [ 1 ]:
                button = InlineKeyboardButton(text="▶" , callback_data=f'button_{i}')  # Кнопка "▶"
                buttons.append(button)
            elif i == positions [ 2 ]:
                button = InlineKeyboardButton(text="⬆️" , callback_data=f'button_{i}')  # Кнопка "🔼"
                buttons.append(button)
            elif i == positions [ 3 ]:
                button = InlineKeyboardButton(text="🔽" , callback_data=f'button_{i}')  # Кнопка "🔽"
                buttons.append(button)
        elif listt [ i ] in [ "x" , "$" , "$$" ]:
            button = InlineKeyboardButton(text=" " , callback_data=f'button_{i}')  # Пустая кнопка
            buttons.append(button)

    # Добавляем кнопку для вывода денег
    button = InlineKeyboardButton(text="💠 Завершить игру" , callback_data="mouse_withdraw")
    buttons.append(button)

    keyboard.add(*buttons)  # Добавляем все кнопки на клавиатуру
    return keyboard


# Функция для отображения клавиатуры после выигрыша или проигрыша
def open_pos(listt):
    keyboard = InlineKeyboardMarkup(row_width=7)
    buttons = [ ]

    for i in range(0 , 49):
        if listt [ i ] == "0":
            button = InlineKeyboardButton(text=" " , callback_data=f'#')  # Кнопка для центральной ячейки
            buttons.append(button)
        elif listt [ i ] == "X":
            button = InlineKeyboardButton(text=" " , callback_data=f'#')  # Кнопка с символом '$'
            buttons.append(button)
        elif listt [ i ] == "X$":
            button = InlineKeyboardButton(text="💰" , callback_data=f'#')  # Кнопка с символом '$$'
            buttons.append(button)
        elif listt [ i ] == "x":
            button = InlineKeyboardButton(text="🕸" , callback_data=f'#')  # Кнопка, обозначающая пустую ячейку
            buttons.append(button)
        elif listt [ i ] == "$":
            button = InlineKeyboardButton(text=" " , callback_data=f'#')  # Кнопка с символом '$'
            buttons.append(button)
        elif listt [ i ] == "$$":
            button = InlineKeyboardButton(text="🦋" , callback_data=f'#')  # Кнопка с символом '$$'
            buttons.append(button)

    keyboard.add(*buttons)  # Добавляем все кнопки на клавиатуру
    return keyboard


@dp.message()
async def game_filter(message: Message):
    mes = message.text

    if mes is None:
        return

    mes_parts = mes.split()

    # Проверяем, что сообщение начинается с одной из команд игры
    if mes_parts [ 0 ] in [ "бабочка341234123412" , "Бабочка341234123412" , "бк12412412" , "Бк12314125" , "БК121421" , "бК1251251" ]:
        # Проверяем, что сообщение содержит достаточно частей для анализа
        if len(mes_parts) < 2:
            await message.reply("Укажите ставку для игры.")
            return

        required_amount_str = mes_parts [ 1 ]

        # Проверяем, что ставка является числом и больше 0
        try:
            required_amount = int(required_amount_str)
        except ValueError:
            await message.reply("Ставка должна быть числом.")
            return

        if required_amount <= 0:
            await message.reply("Ставка должна быть больше 0.")
            return

        # Получаем данные пользователя из базы данных
        user_data = None
        for user in await db.get_data_users():
            if int(user [ 0 ]) == message.from_user.id:
                user_data = user
                break

        if user_data:
            listt = split_list(generate_rows())
            db.add_usermouse(message.from_user.id , listt , required_amount)
            await message.reply("🦋 Какой будет следуйщий ход?" , reply_markup=generate_inline_buttons(listt))



@dp.callback_query(lambda c: c.data.startswith('button_'))
async def process_adm_menu(call: types.CallbackQuery):
    # Гасим спиннер кнопки сразу - раньше этот обработчик не отвечал на
    # callback ни на одном пути, и кнопка «висела» до таймаута.
    try:
        await call.answer()
    except Exception:
        pass
    if db.exists(call.from_user.id):
        for user in db.data():
            if int(user[0]) == int(call.from_user.id):
                listt = json.loads(user[3])
                position = int(call.data[7:])
                a = listt.index('0')
                positions = [a - 1, a + 1, a - 7, a + 7]
                if position in positions:
                    if listt[position] == "x":
                        db.delete_column(user[0])
                        # Получение проигранной ставки
                        bet_amount = int(user[1])
                        # Форматирование проигранной ставки
                        formatted_loss = "{:,.0f}".format(bet_amount).replace(",", ".")
                        # Вычитание проигранной ставки из баланса пользователя
                        await db.subtract_money(user[0], bet_amount)
                        # Сохранение проигранной ставки в столбце bklose
                        #await db.add_commissionbk(user[0], bet_amount, winner='bot')
                        await call.message.edit_text(
                            text=f"🕸 Вы проиграли {formatted_loss} кут", reply_markup=open_pos(listt))
                    elif listt[position] == "$":
                        listt[a] = "X"
                        listt[position] = "0"
                        value0 = random.randint(1, 20)
                        await db.update_user_balance(user[0], int(user[1]))
                        db.set_status_list(user[0], listt)
                        await call.message.edit_text(text=f"🎩 Пропуск", reply_markup=generate_inline_buttons(listt))
                    elif listt[position] == "$$":
                        listt[a] = "X$"
                        listt[position] = "0"
                        value = random.randint(3, 10)
                        await db.update_user_balance(user[0], int(user[1]) * value)
                        db.set_status_list(user[0], listt)
                        await call.message.edit_text(
                            text=f"🦋 Вы нашли умножитель <b>{value}x</b> ",
                            parse_mode="HTML",
                            reply_markup=generate_inline_buttons(listt))


@dp.callback_query(lambda c: c.data.startswith('mouse_withdraw'))
async def process_adm_menu(call: types.CallbackQuery):
    if db.exists(call.from_user.id):
        for user in db.data():
            if int(user [ 0 ]) == int(call.from_user.id):
                # Проверяем, сделал ли пользователь хотя бы один ход
                if len(user [ 3 ]) == 0:
                    await call.message.answer("Вы не сделали ни одного хода в игре.", show_alert=True)
                    return

                listt = json.loads(user [ 3 ])
                db.delete_column(user [ 0 ])
                for t in await db.get_data_users():
                    if int(t [ 0 ]) == int(call.from_user.id):
                        # Получение суммы ставки из таблицы mouse_game
                        bet_amount = int(user [ 2 ])
                        # Проверяем совпадение суммы ставки и текущего баланса пользователя
                        if bet_amount == int(t [ 1 ]):
                            # Если суммы совпадают, баланс пользователя не изменяется
                            formatted_amount = "{:,.0f}".format(bet_amount).replace("," , ".")
                        else:
                            # Вычитаем комиссию из суммы ставки
                            bet_amount1 = bet_amount - commission_bk
                            # Получение текущего баланса пользователя из таблицы db_users
                            current_balance = int(t [ 1 ])
                            # Вычитаем сумму ставки с комиссией из баланса пользователя
                            new_balance = current_balance + bet_amount1
                            await db.update_user_balance(user [ 0 ] , new_balance)
                            # Форматирование суммы вывода с использованием запятых
                            formatted_amount = "{:,.0f}".format(bet_amount1).replace("," , ".")
                        break  # Выход из цикла, если найден пользователь
                bet_amount = int(user [ 2 ])
                bet_amount1 = bet_amount - commission_bk
                formatted_amount = "{:,.0f}".format(bet_amount1).replace("," , ".")
                await call.message.edit_text(
                    text=f"💠 Вы получили : <b>{formatted_amount}</b> кут" , parse_mode="HTML" ,
                    reply_markup=open_pos(listt))