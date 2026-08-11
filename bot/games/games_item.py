from aiogram import Bot, Dispatcher, types

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
from bot.db_create.db import *
import asyncio
import random
from bot.config.config import *


def get_combo_text(dice_value: int):
    """
    Возвращает то, что было на конкретном дайсе-казино
    :param dice_value: значение дайса (число)
    :return: массив строк, содержащий все выпавшие элементы в виде текста

    Альтернативный вариант (ещё раз спасибо t.me/svinerus):
        return [casino[(dice_value - 1) // i % 4]for i in (1, 4, 16)]
    """
    #           0       1         2        3
    values = ["BAR", "виноград", "лимон", "семь"]

    dice_value -= 1
    result = []
    for _ in range(3):
        result.append(values[dice_value % 4])
        dice_value //= 4
    return result




class Slots:
    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        self.bet = bet
        self.user_id = user_id
        self.balance = balance  # Store initial balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("Покрутить слот еще раз 🎰").add("Вернуться назад 📂")

    async def main(self):

        # Play the dice game
        first_slots = await self.message.reply_dice(emoji='🎰')
        await asyncio.sleep(1)  # Delay for 1 second

        combo = get_combo_text(first_slots.dice.value)  # Get the combo

        multiplier_dict = {
            ('семь', 'семь', 'семь'): 2.7,
            ('виноград', 'виноград', 'виноград'): 1.9,
            ('лимон', 'лимон', 'лимон'): 2.5,
            ('BAR', 'BAR', 'BAR'): 2.3,
            ('семь', 'BAR', 'BAR'): 1.6,
            ('виноград', 'BAR', 'BAR'): 1.6,
            ('лимон', 'BAR', 'BAR'): 1.6,
            ('BAR', 'BAR', 'семь'): 1.6,
            ('BAR', 'BAR', 'виноград'): 1.6,
            ('BAR', 'BAR', 'лимон'): 1.6,
            ('лимон', 'лимон', 'семь'): 1.6,
            ('лимон', 'лимон', 'виноград'): 1.6,
            ('лимон', 'лимон', 'BAR'): 1.6,
            ('семь', 'лимон', 'лимон'): 1.6,
            ('виноград', 'лимон', 'лимон'): 1.6,
            ('BAR', 'лимон', 'лимон'): 1.6,
            ('виноград', 'виноград', 'BAR'): 1.6,
            ('виноград', 'виноград', 'лимон'): 1.6,
            ('виноград', 'виноград', 'семь'): 1.6,
            ('BAR', 'виноград', 'виноград'): 1.6,
            ('лимон', 'виноград', 'виноград'): 1.6,
            ('семь', 'виноград', 'виноград'): 1.6,
            ('семь', 'семь', 'BAR'): 1.6,
            ('семь', 'семь', 'лимон'): 1.6,
            ('семь', 'семь', 'виноград'): 1.6,
            ('BAR', 'семь', 'семь'): 1.6,
            ('лимон', 'семь', 'семь'): 1.6,
            ('виноград', 'семь', 'семь'): 1.6
        }

        # Get win multiplier and calculate winnings
        win_multiplier = multiplier_dict.get(tuple(combo), 0)
        win_amount = self.bet * win_multiplier  # Winning = bet * multiplier
        win_amount_rounded = round(win_amount)  # Round winnings
        print(win_amount_rounded)

        if win_multiplier == 0:
            # Проигрыш
            #await self.db.add_commissionslots(self.user_id , self.bet , winner='bot')

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔥 Ничего не выиграно" , callback_data="money_won"))
            await self.send_inline_button(first_slots , keyboard)
            return 0  # Возвращаем 0 в случае проигрыша

        else:
            # Выигрыш
            new_balance = self.balance + win_amount
            await self.db.update_user_balance(self.user_id , new_balance)
            #await self.db.add_commissionslots(self.user_id , win_amount , winner='user')
            win_amount_commission = round(win_amount)
            win_amount_formatted = "{:,.0f}".format(win_amount_commission).replace("," , ".")
            await self.db.add_xp_to_games(self.user_id)

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"🎰 Победа: {win_amount_formatted} | {win_multiplier:.1f}x" , callback_data="money_won"))
            await self.send_inline_button(first_slots , keyboard)
            return win_amount  # Возвращаем сумму выигрыша



    async def send_inline_button(self, message, keyboard):
        # Change message layout with animation
        await message.edit_reply_markup(reply_markup=keyboard)



class Bowling:
    MAX_BET = 500000  # Максимальная ставка

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db

        self.target_value = 6  # Цель - выпасть 6 на кубике

        # Клавиатура для действий
        self.cube = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        self.cube.add(KeyboardButton("Сыграть в боулинг еще раз 🎳"))
        self.cube.add(KeyboardButton("Вернуться назад 📂"))

    async def send_max_bet_error(self):
        """Отправка ошибки при превышении максимальной ставки."""
        await self.message.answer(
            "Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML",
        show_alert=True,
        )

    async def main(self):
        """Основная логика игры в боулинг."""
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return 0  # Ошибка ставки, возвращаем 0

        # Бросок кубика с эмодзи 🎳
        user_dice = await self.message.reply_dice(emoji='🎳')



        # Проверяем результат кубика
        result = user_dice.dice.value == self.target_value

        if result:
            win_amount = self.bet * 2.7  # Выигрыш без комиссии
            win_amount_commission = round(win_amount)  # С учетом комиссии
            message_text = f"💸 Победа! {win_amount_commission:,.0f} кут".replace(",", ".")
            callback_data = "money_won"

            # Учёт выигрыша в БД
            #await self.db.add_commissionboul(self.user_id, win_amount_commission, winner='user')
        else:
            win_amount_commission = 0  # Проигрыш - комиссия 0
            new_balance = self.balance - self.bet  # Списание ставки


            message_text = "🔥 Вы не сбили все кегли."
            callback_data = "money_lost"
            #await self.db.add_commissionboul(self.user_id, self.bet, winner='bot')

        # Отправляем финальное сообщение с клавиатурой
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton(message_text, callback_data=callback_data)
        )
        await self.send_inline_button(user_dice, keyboard)  # Изменяем клавиатуру

        # Возвращаем сумму выигрыша с комиссией
        return win_amount_commission

    async def send_inline_button(self, dice_message, keyboard):
        """Изменение клавиатуры у сообщения с броском кубика."""
        await dice_message.edit_reply_markup(reply_markup=keyboard)



class Dart:
    MAX_BET = 500000  # Максимальная ставка

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.target_value = 6  # Цель - выпасть 6 на кубике

        # Клавиатура для действий
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        self.keyboard.add(KeyboardButton("Сыграть в дартс еще раз 🎯"))
        self.keyboard.add(KeyboardButton("Вернуться назад 📂"))

    async def send_max_bet_error(self):
        """Отправка ошибки при превышении максимальной ставки."""
        await self.message.answer(
            "Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML",
        show_alert=True,
        )

    async def main(self):
        """Основная логика игры в дартс."""
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return 0  # Ошибка ставки, возвращаем 0

        # Бросок кубика с эмодзи 🎯
        user_dart = await self.message.reply_dice(emoji='🎯')

        # Проверяем результат броска
        result = user_dart.dice.value == self.target_value

        if result:
            win_amount = self.bet * 2.6  # Выигрыш без комиссии
            win_amount_commission = round(win_amount)  # С учетом комиссии
            message_text = f"💸 Победа! {win_amount_commission:,.0f} кут".replace(",", ".")
            callback_data = "money_won"

            # Учёт выигрыша в БД

        else:
            win_amount_commission = 0  # Проигрыш - комиссия 0
            new_balance = self.balance - self.bet  # Списание ставки

            message_text = "🔥 Промах!"
            callback_data = "money_lost"

        # Отправляем финальное сообщение с клавиатурой
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton(message_text, callback_data=callback_data)
        )
        await self.send_inline_button(user_dart, keyboard)  # Изменяем клавиатуру

        # Возвращаем сумму выигрыша с комиссией
        return win_amount_commission

    async def send_inline_button(self, dice_message, keyboard):
        """Изменение клавиатуры у сообщения с броском кубика."""
        await dice_message.edit_reply_markup(reply_markup=keyboard)


class FootGame:
    MAX_BET = 500000  # Максимальная ставка

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db

        self.target_value = [5,6,3,4]  # Цель - выпасть 6 на кубиек

        # Клавиатура для действий
        self.keyboard = ReplyKeyboardMarkup(
            keyboard=[ [ KeyboardButton(text="⚽️") , KeyboardButton(text="Вернуться назад 📂") ] ] ,
            resize_keyboard=True , selective=True)

    async def send_max_bet_error(self):
        """Отправка ошибки при превышении максимальной ставки."""
        await self.message.answer(
            "Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML",
        show_alert=True,
        )

    async def main(self):
        """Основная логика игры в футбол."""
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return 0  # Ошибка ставки, возвращаем 0

        # Бросок кубика с эмодзи ⚽️
        user_dice = await self.message.reply_dice(emoji='⚽️')

        # Проверяем результат кубика
        print('s',user_dice)
        result = user_dice.dice.value in self.target_value

        if result:
            win_amount = self.bet * 2.4  # Выигрыш без комиссии
            win_amount_commission = round(win_amount)  # С учетом комиссии
            message_text = f"💸 Победа! {win_amount_commission:,.0f} кут".replace(",", ".")
            callback_data = "money_won"

            # Учёт выигрыша в БД
            #await self.db.add_commissionfoot(self.user_id, win_amount_commission, winner='user')
        else:
            win_amount_commission = 0  # Проигрыш - комиссия 0
            new_balance = self.balance - self.bet  # Списание ставки

            message_text = "🔥 Промах"
            callback_data = "money_lost"
            #await self.db.add_commissionfoot(self.user_id, self.bet, winner='bot')

        # Подготовка финального сообщения с клавиатурой
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton(message_text, callback_data=callback_data)
        )

        await self.send_inline_button(user_dice, keyboard)  # Изменяем клавиатуру

        return win_amount_commission  # Возвращаем сумму выигрыша

    async def send_inline_button(self, dice_message, keyboard):
        """Изменение клавиатуры у сообщения с броском кубика."""
        await dice_message.edit_reply_markup(reply_markup=keyboard)




class Basketball:
    MAX_BET = 500000  # Максимальная ставка
    TARGET_VALUE = [ 4, 5 , 6 ]  # Целевые значения для попадания

    def __init__(self , bet: int , user_id , balance , bot , dp , message):
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db

        # Клавиатура с действиями
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True , selective=True).add(
            "Сыграть еще раз 🏀" , "Вернуться назад 📂")

    async def send_max_bet_error(self):
        """Отправка ошибки при превышении максимальной ставки."""
        await self.message.answer(
            "Максимальная ставка <b>500.000 кут</b>" , parse_mode="HTML", show_alert=True)

    async def main(self):
        """Основная логика игры в баскетбол."""
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return 0  # Ошибка ставки, возвращаем 0

        # Бросок кубика с эмодзи 🏀
        user_dice = await self.message.reply_dice(emoji='🏀')
        print(user_dice)

        # Проверка результата броска
        result = user_dice.dice.value in self.TARGET_VALUE


        if result:
            win_amount = self.bet * 2.4  # Расчёт выигрыша
            win_amount_commission = round(win_amount)  # С учётом комиссии
            message_text = f"💸 Попадание! {win_amount_commission:,.0f} кут".replace("," , ".")
            callback_data = "money_won"

            # Учёт выигрыша в БД
            #await self.db.add_commissionbasket(self.user_id , win_amount_commission , winner='user')
        else:
            message_text = "🔥 Промах"
            callback_data = "money_lost"
            #await self.db.add_commissionbasket(self.user_id , self.bet , winner='bot')

        # Отправка финального сообщения с результатом
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton(message_text , callback_data=callback_data))
        await self.send_inline_button(user_dice , keyboard)

        return win_amount_commission if result else 0  # Возвращаем выигрыш или 0


    async def send_inline_button(self, bot_dice_animation, keyboard):
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)