from aiogram import Bot, Dispatcher, types

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
from bot.db_create.db import *
import random

import asyncio
import json
from aiogram.exceptions import TelegramAPIError  # Для обработки исключений
from bot.db_create.db import *
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


class Cube122:

    MAX_BET = 500000

    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("Бросить кубик 🎲").add(
            "Вернуться назад 📂")

    async def cuber(self):
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return  # Stop the function if the bet exceeds the maximum value

        user_id = self.message.from_user.id

        # Get user information
        user_info = {'first_name': self.message.from_user.first_name, 'username': self.message.from_user.username}
        first_name = user_info.get('first_name', '') if user_info else ''
        username = user_info.get('username', '') if user_info else ''
        user_link = f'<a href="https://t.me/{username}">{first_name}</a>' if first_name else \
            f'<a href="https://t.me/{username}">@{username}</a>' if username else "Имя не указано"

        # Send message to initiate the game for the user
        style_number = await self.db.get_user_style(user_id)
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji = style [ 1 ] , style [ 2 ]
                break
        else:
            if style_number == 0:
                user_emoji , bot_emoji = "🎲" , "🎲"
            else:
                user_emoji , bot_emoji = "" , ""

        # Send message to initiate the game for the user
        await self.message.answer(
            f'{user_emoji} Ход пользователя \n{user_link}' , parse_mode="HTML",
            disable_web_page_preview=True)
        user_cube = await self.message.reply_dice(emoji='🎲')

        await asyncio.sleep(0.5)

        # Send message for bot's turn
        await self.message.answer(f'{bot_emoji} Ход бота' , parse_mode="HTML")
        bot_dice_animation = await self.message.reply_dice()

        # Determine winner and handle balance
        winner = self.determine_winner(user_cube.dice.value, bot_dice_animation.dice.value)
        await self.handle_balance(winner, user_id, bot_dice_animation)

    async def send_max_bet_error(self):
        await self.message.answer("Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML")

    def determine_winner(self, user_value, bot_value):
        if user_value > bot_value:
            return 'user'
        elif user_value < bot_value:
            return 'bot'
        else:
            return 'draw'

    async def handle_balance(self , winner , user_id , bot_dice_animation):
        balance = await self.db.get_user_balance(user_id)

        if winner == 'bot':
            new_balance = balance - self.bet
            await self.db.update_user_balance(user_id , new_balance)
            # Record the lost bet in kubelose column
            #await self.db.add_commission(user_id , self.bet , winner='bot')
            keyboard3 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔥 Деньги сгорели" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard3)
        elif winner == 'user':

            win_bet = self.bet * 2
            commission = win_bet * commission_tg
            win_amount_commission = round(commission)


            win_amount = win_bet - commission
            win_amount_rounded = round(win_amount)
            #await self.db.add_commission(user_id , win_amount_rounded , winner='user')


            win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
            new_balance = balance + win_amount_rounded
            await self.db.update_user_balance(user_id , new_balance - self.bet )

            # Check for and update user's achievements based on the game played
            game_name = "kube"  # Example: replace "kube" with the actual game played
            new_achievements = await self.db.update_user_achievements(user_id , game_name)

            # Notify user about new achievements
            if new_achievements:
                if not isinstance(new_achievements , list):
                    new_achievements = [ new_achievements ]
                for achievement in new_achievements:
                    pass#await self.message.answer(f"Поздравляем! Вы получили достижение: {achievement}")

            # Add new achievements to the achievements column in moneyachiv table
            if new_achievements:
                user_achievements = await self.db.get_user_achievements(user_id)
                if user_achievements:
                    achiv_column = json.loads(user_achievements.get("achiv" , "[]"))
                else:
                    achiv_column = [ ]
                achiv_column.extend(new_achievements)
                await self.db.update_user_achievements(user_id, json.dumps(achiv_column))

            # Create an inline button for win
            await self.db.add_xp_to_games(user_id)
            keyboard1 = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"💸 Победа : {win_amount_formatted}" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard1)
        else:
            # Create an inline button for draw
            keyboard2 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🕊 Ничья" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard2)

    async def send_inline_button(self, bot_dice_animation, keyboard):
        # Edit reply markup of bot's dice animation message
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)



class dart122:
    MAX_BET = 500000

    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db

        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("Бросить дартс 🎯").add(
            "Вернуться назад 📂")

    async def dart(self):
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return  # Stop the function if the bet exceeds the maximum value

        user_id = self.message.from_user.id

        # Get user information
        user_info = {'first_name': self.message.from_user.first_name, 'username': self.message.from_user.username}
        first_name = user_info.get('first_name', '') if user_info else ''
        username = user_info.get('username', '') if user_info else ''
        user_link = f'<a href="https://t.me/{username}">{first_name}</a>' if first_name else \
            f'<a href="https://t.me/{username}">@{username}</a>' if username else "Имя не указано"

        style_number = await self.db.get_user_style(user_id)
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji = style [ 1 ] , style [ 2 ]
                break
        else:
            if style_number == 0:
                user_emoji , bot_emoji = "🎯" , "🎯"
            else:
                user_emoji , bot_emoji = "" , ""
        # Send message to initiate the game for the user
        await self.message.answer(
            f'{user_emoji} Ход пользователя \n{user_link} ', parse_mode="HTML", disable_web_page_preview=True)
        user_cube = await self.message.reply_dice(emoji='🎯')

        await asyncio.sleep(0.5)

        # Send message for bot's turn
        await self.message.answer(f"{bot_emoji} Ход бота ", parse_mode="HTML")
        bot_dice_animation = await self.message.reply_dice(emoji='🎯')



        # Send message to initiate the game for the user

        # Determine winner and handle balance
        winner = self.determine_winner(user_cube.dice.value, bot_dice_animation.dice.value)
        await self.handle_balance(winner, user_id, bot_dice_animation)

    async def send_max_bet_error(self):
        await self.message.answer("Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML")

    def determine_winner(self, user_value, bot_value):
        if user_value > bot_value:
            return 'user'
        elif user_value < bot_value:
            return 'bot'
        else:
            return 'draw'

    async def handle_balance(self , winner , user_id , bot_dice_animation):
        balance = await self.db.get_user_balance(user_id)

        if winner == 'bot':
            new_balance = balance - self.bet
            await self.db.update_user_balance(user_id , new_balance)
            # Record the lost bet in kubelose column

            #await self.db.add_commissiondart(user_id , self.bet , winner='bot')
            keyboard3 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔥 Деньги сгорели" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard3)
        elif winner == 'user':
            win_bet = self.bet * 2
            commission = win_bet * commission_tg
            win_amount_rounded1 = round(commission)
            #await self.db.add_commissiondart(user_id , win_amount_rounded1 , winner='user')

            win_amount = win_bet - commission
            win_amount_rounded = round(win_amount)
            win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
            new_balance = balance + win_amount_rounded
            await self.db.update_user_balance(user_id , new_balance - self.bet)

            # Check for and update user's achievements based on the game played
            game_name = "kube"  # Example: replace "kube" with the actual game played
            new_achievements = await self.db.update_user_achievements(user_id , game_name)

            # Notify user about new achievements
            if new_achievements:
                if not isinstance(new_achievements , list):
                    new_achievements = [ new_achievements ]
                for achievement in new_achievements:
                    pass#await self.message.answer(f"Поздравляем! Вы получили достижение: {achievement}")

            # Add new achievements to the achievements column in moneyachiv table
            if new_achievements:
                user_achievements = await self.db.get_user_achievements(user_id)
                if user_achievements:
                    achiv_column = json.loads(user_achievements.get("achiv" , "[]"))
                else:
                    achiv_column = [ ]
                achiv_column.extend(new_achievements)
                await self.db.update_user_achievements(user_id, json.dumps(achiv_column))

            # Create an inline button for win
            await self.db.add_xp_to_games(user_id)
            keyboard1 = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"💸 Победа : {win_amount_formatted}" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard1)
        else:
            # Create an inline button for draw
            keyboard2 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🕊 Ничья" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard2)

    async def send_inline_button(self, bot_dice_animation, keyboard):
        # Edit reply markup of bot's dice animation message
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)



class foot1:
    MAX_BET = 500000

    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("⚽️").add(
            "Вернуться назад 📂")

    async def foot(self):
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return  # Stop the function if the bet exceeds the maximum value

        user_id = self.message.from_user.id

        # Get user information
        user_info = {'first_name': self.message.from_user.first_name, 'username': self.message.from_user.username}
        first_name = user_info.get('first_name', '') if user_info else ''
        username = user_info.get('username', '') if user_info else ''
        user_link = f'<a href="https://t.me/{username}">{first_name}</a>' if first_name else \
            f'<a href="https://t.me/{username}">@{username}</a>' if username else "Имя не указано"

        # Send message to initiate the game for the user
        style_number = await self.db.get_user_style(user_id)
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji = style [ 1 ] , style [ 2 ]
                break
        else:
            if style_number == 0:
                user_emoji , bot_emoji = "⚽️" , "⚽️"
            else:
                user_emoji , bot_emoji = "" , ""
        # Send message to initiate the game for the user
        await self.message.answer(
            f'{user_emoji} Ход пользователя \n{user_link} ' , parse_mode="HTML" ,
            disable_web_page_preview=True)
        user_cube = await self.message.reply_dice(emoji='⚽️')

        await asyncio.sleep(0.5)

        # Send message for bot's turn
        await self.message.answer(f"{bot_emoji} Ход бота " , parse_mode="HTML")
        bot_dice_animation = await self.message.reply_dice(emoji='⚽️')

        # Determine winner and handle balance
        winner = self.determine_winner(user_cube.dice.value, bot_dice_animation.dice.value)
        await self.handle_balance(winner, user_id, bot_dice_animation)

    async def send_max_bet_error(self):
        await self.message.answer("Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML")

    def determine_winner(self, user_value, bot_value):
        if user_value > bot_value:
            return 'user'
        elif user_value < bot_value:
            return 'bot'
        else:
            return 'draw'

    async def handle_balance(self , winner , user_id , bot_dice_animation):
        balance = await self.db.get_user_balance(user_id)

        if winner == 'bot':
            new_balance = balance - self.bet
            await self.db.update_user_balance(user_id , new_balance)
            # Record the lost bet in kubelose column
            #await self.db.add_commissionfoot(user_id , self.bet , winner='bot')
            keyboard3 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔥 Деньги сгорели" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard3)
        elif winner == 'user':
            win_bet = self.bet * 2
            commission = win_bet * commission_tg
            win_amount_rounded1 = round(commission)


            win_amount = win_bet - commission
            win_amount_rounded = round(win_amount)
            #await self.db.add_commissionfoot(user_id , win_amount_rounded , winner='user')
            win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
            new_balance = balance + win_amount_rounded
            await self.db.update_user_balance(user_id , new_balance - self.bet)

            # Check for and update user's achievements based on the game played
            game_name = "kube"  # Example: replace "kube" with the actual game played
            new_achievements = await self.db.update_user_achievements(user_id , game_name)

            # Notify user about new achievements
            if new_achievements:
                if not isinstance(new_achievements , list):
                    new_achievements = [ new_achievements ]
                for achievement in new_achievements:
                    pass#await self.message.answer(f"Поздравляем! Вы получили достижение: {achievement}")

            # Add new achievements to the achievements column in moneyachiv table
            if new_achievements:
                user_achievements = await self.db.get_user_achievements(user_id)
                if user_achievements:
                    achiv_column = json.loads(user_achievements.get("achiv" , "[]"))
                else:
                    achiv_column = [ ]
                achiv_column.extend(new_achievements)
                await self.db.update_user_achievements(user_id, json.dumps(achiv_column))

            # Create an inline button for win
            await self.db.add_xp_to_games(user_id)
            keyboard1 = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"💸 Победа : {win_amount_formatted}" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard1)
        else:
            # Create an inline button for draw
            keyboard2 = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🕊 Ничья" , callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation , keyboard2)

    async def send_inline_button(self, bot_dice_animation, keyboard):
        # Edit reply markup of bot's dice animation message
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)


class Bowling34:
    MAX_BET = 500000

    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.cube = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        self.cube.add(KeyboardButton("Сыграть в боулинг еще раз 🎳"))
        self.cube.add(KeyboardButton("Вернуться назад 📂"))

    async def send_max_bet_error(self):
        await self.message.answer("Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML")

    async def main(self):
        users = await self.db.get_data_users()
        balance = ""
        for row in users:
            if int(self.user_id) == row[0]:
                balance = row[1]

        try:
            if self.bet > self.MAX_BET:
                await self.send_max_bet_error()
                return

            user_id = self.message.from_user.id
            user_info = {'first_name': self.message.from_user.first_name, 'username': self.message.from_user.username}
            first_name = user_info.get('first_name', '') if user_info else ''
            username = user_info.get('username', '') if user_info else ''
            user_link = f'<a href="https://t.me/{username}">{first_name}</a>' if first_name else f'<a href="https://t.me/{username}">@{username}</a>' if username else "Имя не указано"

            style_number = await self.db.get_user_style(user_id)
            for style in styleset:
                if style [ 0 ] == f'style{style_number}':
                    user_emoji , bot_emoji = style [ 1 ] , style [ 2 ]
                    break
            else:
                if style_number == 0:
                    user_emoji , bot_emoji = "🎳" , "🎳"
                else:
                    user_emoji , bot_emoji = "" , ""
            # Send message to initiate the game for the user
            await self.message.answer(
                f'{user_emoji} Ход пользователя \n{user_link} ' , parse_mode="HTML" ,
                disable_web_page_preview=True)
            user_dice = await self.message.reply_dice(emoji='🎳')

            await asyncio.sleep(0.5)

            # Send message for bot's turn
            await self.message.answer(f"{bot_emoji} Ход бота " , parse_mode="HTML")
            bot_dice_animation = await self.message.reply_dice(emoji='🎳')

            result = self.determine_winner(user_dice.dice.value, bot_dice_animation.dice.value)








            if result == "win":
                win_bet = self.bet * 2
                commission = win_bet * commission_tg

                win_amount = win_bet - commission
                win_amount_rounded = round(win_amount)
                #await self.db.add_commissionboul(self.user_id , win_amount_rounded , winner='user')
                new_balance = balance + win_amount_rounded
                await self.db.update_user_balance(self.user_id, new_balance - self.bet)
                win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
                await self.db.add_xp_to_games(user_id)
                keyboard = InlineKeyboardMarkup().add(
                    InlineKeyboardButton(
                        f"💸 Победа : {win_amount_formatted}", callback_data="money_won"))
                await self.send_inline_button(bot_dice_animation, keyboard)

            elif result == "lose":
                new_balance = int(balance) - self.bet
                await self.db.update_user_balance(self.user_id, new_balance)
                #await self.db.add_commissionboul(self.user_id, self.bet, winner='bot')  # Проигрыш идет в столбец boullose
                keyboard = InlineKeyboardMarkup().add(
                    InlineKeyboardButton(
                        "Ваши деньги сгорели 🔥", callback_data="money_won"))
                await self.send_inline_button(bot_dice_animation, keyboard)

            else:
                keyboard = InlineKeyboardMarkup().add(
                    InlineKeyboardButton(
                        "🕊 Ничья", callback_data="money_won"))
                await self.send_inline_button(bot_dice_animation, keyboard)


        except TelegramAPIError as e:

            if 'retry after' in str(e).lower():
                # Извлекаем время задержки из ошибки и ждем указанное время

                timeout = float(str(e).split('retry after') [ -1 ].strip().split() [ 0 ])

                await asyncio.sleep(timeout)

    def determine_winner(self, user_value, bot_value):
        if user_value > bot_value:
            return "win"
        elif user_value < bot_value:
            return "lose"
        else:
            return "draw"

    async def send_inline_button(self, bot_dice_animation, keyboard):
        # Edit reply markup of bot's dice animation message
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)




class Basketball34:
    MAX_BET = 500000

    def __init__(self, bet: int, user_id: int, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        self.keyboard.add("Сыграть в баскетбол еще раз 🏀").add("Вернуться назад 📂")

    async def send_max_bet_error(self):
        await self.message.answer("Максимальная ставка <b>500.000 кут</b>", parse_mode="HTML")

    async def main(self):
        if self.bet > self.MAX_BET:
            await self.send_max_bet_error()
            return

        user_id = self.message.from_user.id
        user_info = {'first_name': self.message.from_user.first_name, 'username': self.message.from_user.username}
        first_name = user_info.get('first_name', '') if user_info else ''
        username = user_info.get('username', '') if user_info else ''
        user_link = f'<a href="https://t.me/{username}">{first_name}</a>' if first_name else f'<a href="https://t.me/{username}">@{username}</a>' if username else "Имя не указано"

        style_number = await self.db.get_user_style(user_id)
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji = style [ 1 ] , style [ 2 ]
                break
        else:
            if style_number == 0:
                user_emoji , bot_emoji = "🏀" , "🏀"
            else:
                user_emoji , bot_emoji = "" , ""
        # Send message to initiate the game for the user
        await self.message.answer(
            f'{user_emoji} Ход пользователя \n{user_link} ' , parse_mode="HTML" ,
            disable_web_page_preview=True)
        first_cube = await self.message.reply_dice(emoji='🏀')

        await asyncio.sleep(0.5)

        # Send message for bot's turn
        await self.message.answer(f"{bot_emoji} Ход бота " , parse_mode="HTML")
        bot_dice_animation = await self.message.reply_dice(emoji='🏀')

        result = self.determine_winner(first_cube.dice.value, bot_dice_animation.dice.value)






        if result == "win":
            win_bet = self.bet * 2
            commission = win_bet * commission_tg

            win_amount = win_bet - commission
            win_amount_rounded = round(win_amount)
            #await self.db.add_commissionbasket(self.user_id , win_amount_rounded , winner='user')
            new_balance = self.balance + win_amount_rounded
            await self.db.update_user_balance(self.user_id , new_balance - self.bet)
            win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
            await self.db.add_xp_to_games(user_id)
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"💸 Победа : {win_amount_formatted}", callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation, keyboard)

        elif result == "lose":
            new_balance = self.balance - self.bet
            await self.db.update_user_balance(self.user_id, int(new_balance))
            #await self.db.add_commissionbasket(self.user_id, self.bet, winner='bot')
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    "Ваши деньги сгорели 🔥", callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation, keyboard)

        else:
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    "🕊 Ничья", callback_data="money_won"))
            await self.send_inline_button(bot_dice_animation, keyboard)

    def determine_winner(self, user_value, bot_value):
        if user_value > bot_value:
            return "win"
        elif user_value < bot_value:
            return "lose"
        else:
            return "draw"

    async def send_inline_button(self, bot_dice_animation, keyboard):
        await bot_dice_animation.edit_reply_markup(reply_markup=keyboard)


class Slots1:
    def __init__(self, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("Покрутить слот еще раз 🎰").add("Вернуться назад 📂")

    async def main(self):
        user_id = self.message.from_user.id

        users = self.db.get_data_users()
        balance = ""
        for row in users:
            if int(self.user_id) == row [ 0 ]:
                balance = row [ 1 ]

        first_slots = await self.message.reply_dice(emoji='🎰')
        await asyncio.sleep(1)  # Delay for 3 seconds

        combo = get_combo_text(first_slots.dice.value)


        multiplier_dict = {
            ('семь','семь','семь'):7,
            ('виноград', 'виноград', 'виноград'): 3,
            ('лимон', 'лимон', 'лимон'): 3,
            ('BAR' , 'BAR' , 'BAR'): 5 ,

            ('семь' , 'BAR' , 'BAR'): 2 ,
            ('виноград' , 'BAR' , 'BAR'): 2 ,
            ('лимон' , 'BAR' , 'BAR'): 2 ,

            ('BAR' , 'BAR' , 'семь'): 2 ,
            ('BAR' , 'BAR' , 'виноград'): 2 ,
            ('BAR' , 'BAR' , 'лимон'): 2 ,

            ('лимон' , 'лимон' , 'семь'): 2 ,
            ('лимон' , 'лимон' , 'виноград'): 2 ,
            ('лимон' , 'лимон' , 'BAR'): 2 ,

            ('семь' , 'лимон' , 'лимон'): 2 ,
            ('виноград' , 'лимон' , 'лимон'): 2 ,
            ('BAR' , 'лимон' , 'лимон'): 2 ,

            ('виноград' , 'виноград' , 'BAR'): 2 ,
            ('виноград' , 'виноград' , 'лимон'): 2 ,
            ('виноград' , 'виноград' , 'семь'): 2 ,

            ('BAR' , 'виноград' , 'виноград'): 2 ,
            ('лимон' , 'виноград' , 'виноград'): 2 ,
            ('семь' , 'виноград' , 'виноград'): 2 ,

            ('семь' , 'семь' , 'BAR'): 2 ,
            ('семь' , 'семь' , 'лимон'): 2 ,
            ('семь' , 'семь' , 'виноград'): 2 ,

            ('BAR' , 'семь' , 'семь'): 2 ,
            ('лимон' , 'семь' , 'семь'): 2 ,
            ('виноград' , 'семь' , 'семь'): 2 , }

        win_multiplier = multiplier_dict.get(tuple(combo) , 0)
        win_amount = int(self.bet * win_multiplier)

        commission = win_amount * commission_tg
        win_amount1 = win_amount - commission
        win_amount_rounded = round(win_amount1)


        if win_multiplier == 0:
            # Loss scenario
            loss_amount = self.bet
            #await self.db.add_commissionslots(self.user_id , loss_amount , winner='bot')

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔥 Ничего не выиграно" , callback_data="money_won"))

            await self.send_inline_button(first_slots , keyboard)  # Send the inline button within the animation
        else:
            # Win scenario
            await self.db.update_user_balance(self.user_id , self.balance + win_amount_rounded - self.bet )
            #await self.db.add_commissionslots(self.user_id , win_amount_rounded , winner='user')

            win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")
            await self.db.add_xp_to_games(user_id)
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    f"🎰 Победа : {win_amount_formatted} | {win_multiplier}x" , callback_data="money_won"))
            await self.send_inline_button(first_slots , keyboard)  # Send the inline button within the animation

    async def send_inline_button(self , message , keyboard):
        # Edit the reply markup of the message containing the animation
        await message.edit_reply_markup(reply_markup=keyboard)


class Trade:
    def __init__(self, option, bet: int, user_id, balance: int, bot, dp, message):
        from main import db
        self.bet = bet
        self.user_id = user_id
        self.balance = balance
        self.bot = bot
        self.dp = dp
        self.message = message
        self.option = option
        self.db = db
        self.keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("Предугадать еще раз 📊").add("Вернуться назад 📂")

    async def main(self):
        user_id = self.message.from_user.id
        rand_num = random.randint(1, 100)
        rand_game = random.randint(1, 100)

        style_number = await self.db.get_user_style(self.user_id)
        user_emoji , bot_emoji = '💲' , '💲'
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji = style [ 4 ] , style [ 4 ]
                break
        send_win = random.choice(['Вы угадали ход графика, выиграв'
                                  ,'Ваша удача не подвела, вы выиграли'
                                  ,'Верное предположение, вы в выигрыше на'
                                  ,'Мастерская стратегия! Вы выиграли'
                                  ,'Ваша интуиция сработала, вы выиграли'
                                  ,'Успешный ход, вы заработали'
                                  ,'Поздравляю, вы выиграли'
                                  ,'Вы угадали направление движения, вы заработали'
                                  ,'Ваша стратегия сработала, вы заработали'
                                  ,'Вы заработали'])
        send_lose = random.choice([
            "Вы ошиблись, тем самым проиграв",
            "Вы потеряли",
            "Увы, вы не угадали, потеряв",
            "Вы проиграли",
            "График пошел вверх, вы потеряли",
            "Неудача! Вы потеряли свои",
            "Неудачное решение! Вы потеряли",
            "Попытка была неудачной, вы проиграли",
            "Сожалею, вы проиграли",
            "К сожалению, вы потеряли"])

        loss_amount = self.bet

        win_amount = self.bet * 2
        commission = win_amount * commission_tg
        win_amount1 = win_amount - commission
        win_amount_rounded = round(win_amount1)

        win_amount_formatted = "{:,.0f}".format(win_amount_rounded).replace("," , ".")

        if self.option == 1:
            if rand_game >= 50:  # шанс выпадения, если меньше 48 - больше шанс, если больше - меньше шанс
                #await self.db.add_commissiontrade(self.user_id , win_amount_rounded , winner='user')
                await self.db.add_xp_to_games(user_id)
                await self.message.reply(
                    f'✅ Курс пошел вверх с <b>{rand_num}x</b>\n{user_emoji} Вы выиграли <b>{win_amount_formatted}</b> кут' ,
                    parse_mode="HTML" , disable_web_page_preview=True)
                await self.db.update_user_balance(self.user_id , self.balance + win_amount_rounded - self.bet)
            else:
                #await self.db.add_commissiontrade(self.user_id , loss_amount , winner='bot')
                await self.message.reply(
                    f'❌ Курс пошел вниз с <b>{rand_num}x</b>' , parse_mode="HTML" ,
                    disable_web_page_preview=True)
        elif self.option == 0:
            if rand_game < 50:  # Increased losing threshold
                #await self.db.add_commissiontrade(self.user_id , win_amount_rounded , winner='user')
                await self.db.add_xp_to_games(user_id)
                await self.message.reply(
                    f'✅ Курс пошел вниз с <b>{rand_num}x</b>\n{bot_emoji} {send_win} <b>{win_amount_formatted}</b> кут' ,
                    parse_mode="HTML" , disable_web_page_preview=True)
                await self.db.update_user_balance(self.user_id , self.balance + win_amount_rounded - self.bet)
            else:
                #await self.db.add_commissiontrade(self.user_id , loss_amount , winner='bot')
                await self.message.reply(
                    f'❌ Курс пошел вверх с <b>{rand_num}x</b>' , parse_mode="HTML" ,
                    disable_web_page_preview=True)






async def gamekazik_function(message, db, commission_kazik, colld_kazino):
    user_id = message.from_user.id
    current_time = int(datetime.now().timestamp())

    # Check if the message starts with keywords indicating casino game
    if message.text.lower().startswith(("казик34123412", "казино34123412", "Казик34123412", "Казино34123412")):
        last_game_time = db.get_last_game_time(user_id)

        style_number = await db.get_user_style(user_id)
        user_emoji , bot_emoji , emoji = '🎰' , '🔥' , '🍀'
        for style in styleset:
            if style [ 0 ] == f'style{style_number}':
                user_emoji , bot_emoji , emoji = style [ 3 ] , style [ 5 ] , style [
                    6 ]  # Используем третий эмодзи из стиля
                break

        # Add the user to the kazik table if they are not already present

        parts = message.text.split()
        if len(parts) >= 2:
            bet_str = parts[1].replace(',', '').replace('.', '')  # Убираем точку из ставки для числового преобразования
            if bet_str.isdigit():
                bet = float(bet_str)
            else:
                await message.reply("⚠️ Ставка должна быть числом.")
                return

            balance = await db.get_user_balance(user_id)

            if bet <= 0:
                await message.reply("⚠️ Ставка должна быть больше нуля.")
                return
            if bet > balance:
                from bot.funcs.help import callbaYTRWEQck_main
                button = InlineKeyboardButton(text=f"Как заработать кут?" , callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result , float) and result.is_integer() else str(result)
                bet_amount_win_formated = "{:,.0f}".format(bet).replace("," , ".")
                bot_username = await get_bot_username_by_token(TOKEN)
                user_id = message.from_user.id
                from main import pending_context,send_invoice_to_user
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

            random_number = random.randint(1 , 100)
            print(random_number)


            if random_number < 40:
                multiplier = 0
                balance -= bet
                winnings_str = "{:,.0f}".format(int(bet)).replace("," , ".")
                await message.reply(f"{bot_emoji} Вы проиграли {winnings_str} [{multiplier}x]", parse_mode="HTML")
                await db.update_user_balance(user_id , balance)
                #await db.add_commissionkazik(user_id , bet , 'bot')  # Добавляем сумму ставки в столбец kaziklose
            elif random_number > 50:
                multipliers = [ 1.25, 1.50 , 1.75 , 2 , 2.25 ]
                weights = [ 20 , 20 , 20 , 20 , 20 ]  # Adjusted weights to match the population
                multiplier = random.choices(multipliers) [ 0 ]
                winnings = bet * multiplier
                commission = winnings * commission_kazik
                winnings -= commission  # Вычитаем комиссию из суммы выигрыша
                balance += winnings
                win_amount_rounded = round(balance)

                await db.add_xp_to_games(user_id)
                winnings_str = "{:,.0f}".format(int(winnings)).replace("," , ".")
                await message.reply(f"{user_emoji} Вы выиграли <b>{winnings_str}</b> [{multiplier}x]", parse_mode="HTML")

                await db.update_user_balance(user_id , win_amount_rounded)
                win_amount_rounded1 = round(commission)
                #await db.add_commissionkazik(
                    #user_id , winnings , 'user')  # Добавляем комиссию в столбец kazik
            else:
                await message.reply(f"{emoji} Ваши деньги остаются при вас [1х]", parse_mode="HTML")

            # Set a timer to remove the user from the table after 5 seconds
            await asyncio.sleep(colld_kazino)


            if last_game_time is not None and current_time - last_game_time < db.kazikCOOLDOWN:
                wait_time = db.kazikCOOLDOWN - int(current_time - last_game_time)
                await message.reply(f"⚠️ Подождите {wait_time} секунд.")
                return


async def lottery_function(message, db, commission_lot):
    if message.text.lower().startswith(("лотерея34123412" , "Лотерея34123412")):
        try:
            # Получаем сумму ставки из сообщения
            bet_amount_str = message.text.split() [ 1 ].replace(',' , '').replace(
                '.' , '')  # Удаляем запятые и точки для числового преобразования
            if bet_amount_str.isdigit():
                bet_amount = float(bet_amount_str)
            else:
                await message.answer("⚠️ Ставка должна быть числом.")
                return

            user_id = message.from_user.id

            style_number = await db.get_user_style(user_id)
            user_emoji , bot_emoji , emoji = '💸' , '🔥' , '🍀'
            for style in styleset:
                if style [ 0 ] == f'style{style_number}':
                    user_emoji , bot_emoji , emoji = style [ 3 ] , style [ 5 ] , style [
                        6 ]  # Используем третий эмодзи из стиля
                    break

            # Получаем текущий баланс пользователя
            current_balance = await db.get_user_balance(user_id)

            # Проверяем, достаточно ли у пользователя средств для ставки
            if bet_amount > current_balance:
                from bot.funcs.help import callbaYTRWEQck_main
                bet = bet_amount
                button = InlineKeyboardButton(text=f"Как заработать кут?" , callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result , float) and result.is_integer() else str(result)
                bet_amount_win_formated = "{:,.0f}".format(bet).replace("," , ".")
                bot_username = await get_bot_username_by_token(TOKEN)
                user_id = message.from_user.id
                from main import pending_context,send_invoice_to_user
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

            # Проверяем, разрешено ли пользователю играть в данный момент
            allowed_to_play = await db.is_rool_allowed(user_id)
            if not allowed_to_play:
                await message.answer("⌚️ Подождите немного")
                return

            # Добавляем пользователя в таблицу timerool с текущим временем как временем последней игры


            # Генерируем случайный шанс выжить
            survival_chance = random.randint(1 , 100)

            # Если шанс выжить меньше 60, пользователь проиграл
            if survival_chance < 60:
                await message.answer(
                    f"{bot_emoji} Вы проиграли [ <b>{survival_chance}% выжить</b> ]" , parse_mode='HTML')
                # Уменьшаем баланс на сумму ставки
                new_balance = current_balance - bet_amount
                await db.update_user_balance(user_id , new_balance)
                #await db.add_commissionlot(
                    #user_id , bet_amount , 'bot')  # Добавляем сумму ставки в столбец lotlose
            elif survival_chance > 90:
                await message.answer(
                    f"{emoji} Оружие заклинило [ <b>{survival_chance}% выжить</b> ]" , parse_mode='HTML')
            else:
                multiplier = 2  # random.choice([2])  # Рандомный выбор умножителя
                win_amount = bet_amount * multiplier
                commission = win_amount * commission_lot
                win_amount -= commission  # Вычитаем комиссию из суммы выигрыша
                win_amount_rounded = round(win_amount)

                # Форматируем сумму выигрыша
                formatted_win_amount = "{:,.0f}".format(win_amount_rounded).replace("," , ".")

                await db.add_xp_to_games(user_id)
                await message.answer(
                    f"{user_emoji} Вы выжили, получив <b>{formatted_win_amount}</b> кут [ <b> {survival_chance}% выжить </b> ]" ,
                    parse_mode='HTML')
                # Увеличиваем баланс на выигрыш
                new_balance = current_balance + win_amount_rounded
                await db.update_user_balance(user_id , new_balance - bet_amount)

                win_amount_rounded1 = round(commission)
                #await db.add_commissionlot(user_id , win_amount_rounded , 'user')  # Добавляем комиссию в столбец lot
        except (IndexError , ValueError):
            await message.answer("Неправильный формат сообщения")








