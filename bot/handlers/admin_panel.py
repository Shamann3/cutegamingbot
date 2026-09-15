from aiogram import Bot, Dispatcher, types

from datetime import datetime
import asyncio


import os
import tracemalloc
import aiohttp

from bot.db_create.db import *

from bot.config.config import *
from bot.funcs.func import *


from bot.games.games import Cube122, Bowling34, Basketball34, Slots1
from main import (dp, money, db, bot1, Start, button_creators)
from aiogram import Bot, Dispatcher, types, F
import re

from bot.design.buttons import *
from bot.config.config import *

keyboard1 = 0
send_value = []

@dp.message()
async def admin_filter(message: Message):
    try:
        from aiogram.dispatcher.event.bases import SkipHandler
        from bot.funcs.tiktok_earn import (
            restore_wait_from_session,
            should_skip_main_text_handler,
            should_skip_photo_handler,
        )
        _uid = message.from_user.id if message.from_user else 0
        _chat_type = getattr(getattr(message, "chat", None), "type", "")
        if _uid:
            await restore_wait_from_session(_uid)
        if should_skip_photo_handler(_uid, chat_type=_chat_type) or should_skip_main_text_handler(
            _uid, chat_type=_chat_type
        ):
            raise SkipHandler()
    except Exception as _tt_skip_err:
        from aiogram.dispatcher.event.bases import SkipHandler as _SkipHandler
        if isinstance(_tt_skip_err, _SkipHandler):
            raise
    mes = message.text
    if not mes:
        return
    if mes == "рассылка" and int(message.from_user.id) in admin_id:
        await message.reply("Введите кнопки в формате [кнопка ссылка]")
    elif mes[0] == "[" and int(message.from_user.id) in admin_id:
        global keyboard1
        buttons = []
        pattern = r'\[(.*?) (.*?)\]'
        matches = re.findall(pattern, message.text)

        for match in matches:
            text = match[0]
            link = match[1]
            button = InlineKeyboardButton(text=text, url=link)
            buttons.append(button)
        
        keyboard1 = InlineKeyboardMarkup(row_width=1)
        
        keyboard1.add(*buttons)
        print(keyboard1)


        





@dp.message(F.photo)
async def send_msg_to_usrs(message : types.Message):
    global keyboard1
    _tt_photo_wait = False
    try:
        from bot.funcs.tiktok_earn import restore_wait_from_session, should_skip_photo_handler
        await restore_wait_from_session(message.from_user.id)
        _tt_photo_wait = should_skip_photo_handler(
            message.from_user.id,
            chat_type=getattr(getattr(message, "chat", None), "type", ""),
        )
    except Exception:
        _tt_photo_wait = False
    if _tt_photo_wait:
        from aiogram.dispatcher.event.bases import SkipHandler
        raise SkipHandler()
    try:
        if message.from_user.id in admin_id and keyboard1["inline_keyboard"]:
                keyboard = keyboard1
                keyboard1 = 0
                
                users = await db.get_data_users()
                photo = message.photo[-1]
                file_info = await bot1.get_file(photo.file_id)
                image_url = f'https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}'
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as response:
                        if response.status == 200:
                            filename = f'downloaded_image.jpg'
                            with open(filename, 'wb') as f:
                                f.write(await response.read())

                            for row in users:
                                print(row)
                                with open(filename, 'rb') as photo:
                                    try:
                                        await bot1.send_photo(chat_id=row[0], photo=photo, caption = message.caption, parse_mode="HTML", reply_markup=keyboard)

                                    except Exception as ex: 
                                        print(ex)
    except:
        pass