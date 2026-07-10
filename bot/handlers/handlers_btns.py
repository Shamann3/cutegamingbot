from aiogram import Bot, Dispatcher, types

from datetime import datetime
import asyncio

from aiogram.types import InputFile 
from aiogram.filters import StateFilter

import os
import tracemalloc
import aiohttp

from bot.db_create.db import *

from bot.funcs.func import *

from aiogram.fsm.context import FSMContext


from bot.games.games import Cube122, Bowling34, Basketball34, Slots1
from main import (dp, money, db, bot1, Start, button_creators)


from bot.design.buttons import *
from bot.config.config import *


listt = []
async def get_start_link(user_id):
    username_bot = await get_bot_username_by_token(TOKEN)
    return f"https://t.me/{username_bot}?start={user_id}"
tracemalloc.start()
def is_number(_str):
	try:
		int(_str)
		return True
	except ValueError:
		return False

@dp.message(StateFilter(money.money_cube))
async def send_number4(message: Message, state: FSMContext):
    if is_number(message.text):
        message_money = int(message.text)
        if message_money >= 10:
            users = await db.get_data_users()
            balance = ""
            for row in users:
                if message.from_user.id == row[0]:
                    balance = row[1]
            if int(message.text) <= int(balance):
                cube_class = Cube122(
                    bet=int(message.text),
                    user_id=message.from_user.id,
                    balance=balance,
                    bot=bot1,
                    dp=dp,
                    message=message
                )
                await cube_class.cuber()
                await state.clear()
            else:
                await message.reply(
                    '🎩 Недостаточно денег для игры',
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                await state.clear()



		



@dp.callback_query(lambda c: c.data.startswith('1ref'))
async def process_callback_kb1btn1(call: types.CallbackQuery):
    await call.answer()
    link = await get_start_link(call.from_user.id)
	#📇 Рефералы
    user_id = call.from_user.id
    print(user_id)
    button_id = call.data
    print(button_id)
    creator_id = button_creators.get(f"{button_id}{user_id}")
    print(creator_id)
    if creator_id is not None and user_id == creator_id:
        win_amount_formatted = "{:,.0f}".format(ref_coin).replace(",", ".")
        await call.message.edit_text(
            caption=f'''
<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка :</b> 

<code>{link}</code>

<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>1 друг = 1 кут </b>

<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>+ 25% с каждой покупки, которую совершит ваш реферал в магазине!</b>

<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>+ Каждый приглашённый - рост вашей реферальной статистики!</b>''',
            reply_markup=btn_back1,
            parse_mode="HTML"
        )
    else:
        await call.answer("✖️ эта кнопка для другого пользователя")



@dp.callback_query(lambda c: c.data.startswith('ref1'))
async def process_callback_kb1btn1(call: types.CallbackQuery):
    await call.answer()

    link = await get_start_link(call.from_user.id)


    user_id = call.from_user.id
    print(user_id)
    button_id = call.data
    print(button_id)
    creator_id = button_creators.get(f"{button_id}{user_id}")
    print(creator_id)
    if creator_id is not None and user_id == creator_id:
        await bot1.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = f'''
<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка :</b> 

<code>{link}</code>

<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>1 друг = 1 кут </b>

<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>+ 25% с каждой покупки, которую совершит ваш реферал в магазине!</b>

<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>+ Каждый приглашённый - рост вашей реферальной статистики!</b>''', reply_markup = btn_back1, parse_mode="HTML")
    else:
        await bot1.answer_callback_query(call.id, text="❌Эту кнопку может нажать только её автор.")



@dp.callback_query(lambda c: c.data.startswith('repost_btn1'))
async def process_adm_menu(call: types.CallbackQuery):
    await call.answer()

    if call.from_user.id in admin_id:
        await bot1.send_message(
            call.from_user.id,
            "Введите сообщение с картинкой, которое вы хотите отправить всем пользователям."
        )


@dp.callback_query(lambda c: c.data.startswith('money_lost'))
async def callback_top(call: types.CallbackQuery):


	randommessagehelp1 = random.choice(randommessagehelp)
	await call.answer(randommessagehelp1)


@dp.callback_query(lambda c: c.data.startswith('money_won'))
async def callback_top(call: types.CallbackQuery):
    random_message = random.choice(sksokdoskd)

    await call.answer(random_message)


@dp.callback_query(lambda c: c.data.startswith('back_btn'))
async def callback_main(call: types.CallbackQuery):
    await call.answer()
    users = db.get_data_users()
    balanc = 0
    refferals = 0
    for row in users:
        if call.from_user.id == row[0]:
            balanc = row[1]
            refferals = row[2]

    # Форматируем баланс через точки
    formatted_balanc = "{:,.0f}".format(balanc).replace(",", ".")

    await call.message.edit_caption(caption=f'''
🎩 Профиль пользователя

🏆 Тег : @{call.from_user.username}
🔒 ID : {call.from_user.id}
💸 Баланс : {formatted_balanc} кут
🤝 Рефералы : {refferals} Человек (-а)

🚀 Путешествие к богатству только начинается!🤑''', reply_markup=privates, parse_mode="HTML")













@dp.callback_query(lambda c: c.data.startswith('repost_btn_send'))
async def callback_main(call: types.CallbackQuery):
    await call.answer()


    users = db.get_data_users()
	
    async with aiohttp.ClientSession() as session:
            async with session.get(listt[2]) as response:
                if response.status == 200:
                    with open(listt[0], 'rb') as photo:
                        for row in users:
                            await bot1.send_photo(chat_id=row[0], photo=photo, caption=listt[1])
                        os.remove(listt[0])




















# if db_clan.clan_exists(message.text.split()[2]) == True and int(row[1]) != int(message.from_user.id):
                    #     try:
                    #         if str(message.from_user.id) not in row[2].split():
                    #             if row[2] == None:
                    #                 db_clan.set_full(message.text.split()[2], members = f"{message.from_user.id}")
                    #                 await message.reply(f"Вы присоединились к клану {row[0]}")
                    #             else:
                    #                 db_clan.set_full(message.text.split()[2], members = f"{row[2]} {message.from_user.id}")
                    #                 await message.reply(f"Вы присоединились к клану {row[0]}")
                    #     except Exception:
                    #         if row[2] == None:
                    #             db_clan.set_full(message.text.split()[2], members = f"{message.from_user.id}")
                    #             await message.reply(f"Вы присоединились к клану {row[0]}")
                    #         else:
                    #             db_clan.set_full(message.text.split()[2], members = f"{row[2]} {message.from_user.id}")
                    #             await message.reply(f"Вы присоединились к клану {row[0]}")

                    # else:
                    #     await message.reply("Вы уже состоите в клане или такого клана не существует")

@dp.callback_query(lambda c: c.data.startswith('join_clan'))
async def callback_main(call: types.CallbackQuery):
    await call.answer()
    for row in db.data():
        if str(row[0]) == str(call.data.split()[1]):
            if await db.clan_exists(call.data.split()[1]) and int(row[1]) != int(call.from_user.id):
                try:
                    if str(call.from_user.id) not in row[2].split():
                        if row[2] is None:
                            await db.set_full(call.data.split()[1], members=f"{call.from_user.id}")
                            await bot1.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=f"✅ Вы присоединились к клану {row[0]}"
                            )
                        else:
                            await db.set_full(call.data.split()[1], members=f"{row[2]} {call.from_user.id}")
                            await bot1.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=f"✅ Вы присоединились к клану {row[0]}"
                            )
                except Exception:
                    if row[2] is None:
                        await db.set_full(call.data.split()[1], members=f"{call.from_user.id}")
                        await bot1.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=f"✅ Вы присоединились к клану {row[0]}"
                        )
                    else:
                        await db.set_full(call.data.split()[1], members=f"{row[2]} {call.from_user.id}")
                        await bot1.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=f"✅ Вы присоединились к клану {row[0]}"
                        )


