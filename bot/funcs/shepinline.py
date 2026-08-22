from aiogram import Bot, Dispatcher, types

import random
import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from aiogram.types import InputFile
from datetime import datetime
from aiogram import types
import html

import asyncio


import hashlib
from main import *
from bot.config.config import *
from bot.design.buttons import *
from bot.db_create.db import *
from aiogram.types import InlineQuery, InputTextMessageContent, InlineQueryResultArticle, InlineKeyboardMarkup, InlineKeyboardButton


hidden_messages = []

# Функция для добавления скрытого сообщения в список
def add_hidden_message(sender_id, receiver_id, message):
    hidden_messages.append({
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message': message
    })

# Функция для получения скрытого сообщения
def get_hidden_message(receiver_id):
    for msg in hidden_messages:
        if msg['receiver_id'] == receiver_id:
            return msg['message']
    return None

# Функция для удаления скрытого сообщения
def delete_hidden_message(receiver_id):
    global hidden_messages
    hidden_messages = [msg for msg in hidden_messages if msg['receiver_id'] != receiver_id]

# Обработчик инлайн-запроса
hidden_messages = []

def add_hidden_message(sender_id, receiver_id, message):
    hidden_messages.append({
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message': message
    })

# Обработчик инлайн-запроса
@dp.inline_query()
async def shepinline(inline_query: types.InlineQuery) -> None:
    # Получаем текст инлайн-запроса или используем "Echo" по умолчанию
    text = inline_query.query or "Echo"
    result_id: str = hashlib.md5(text.encode()).hexdigest()  # Генерируем уникальный ID для результата

    if text.startswith("шепнуть "):  # Проверяем, начинается ли текст с "шепнуть "
        hidden_message = text [ len("шепнуть "): ].strip()  # Получаем скрытое сообщение
        sender_id = inline_query.from_user.id

        # Пример ID получателя (можно использовать реальный ID в зависимости от вашей логики)
        receiver_id = random.randint(100000 , 999999)
        add_hidden_message(sender_id , receiver_id , hidden_message)  # Сохраняем скрытое сообщение

        # Создаем кнопку для просмотра скрытого сообщения
        inline_btn = InlineKeyboardButton("Посмотреть сообщение" , callback_data=f"view_message_{receiver_id}")
        keyboard = InlineKeyboardMarkup().add(inline_btn)

        # Создаем контент для инлайн-результата
        input_content = InputTextMessageContent(
            message_text=f"💬 Скрытое сообщение от пользователя: {hidden_message}" , parse_mode="HTML")

        # Формируем инлайн-результат
        item = InlineQueryResultArticle(
            id=result_id , title="Скрытое сообщение" , input_message_content=input_content , reply_markup=keyboard)

        # Возвращаем результат инлайн-запроса
        await dp.bot1.answer_inline_query(inline_query.id , results=[ item ] , cache_time=1)

    else:
        # Если текст не начинается с "шепнуть ", можно добавить поведение по умолчанию
        input_content = InputTextMessageContent(text)  # Используем обычный текст
        item = InlineQueryResultArticle(
            id=result_id , title=text , input_message_content=input_content , )

        await dp.bot1.answer_inline_query(inline_query.id , results=[ item ] , cache_time=1)
# Обработчик для CallbackQuery
@dp.callback_query(lambda c: c.data.startswith('view_message_'))
async def view_message(callback_query: types.CallbackQuery):
    receiver_id = int(callback_query.data.split('_')[-1])
    user_id = callback_query.from_user.id

    # Проверяем, что сообщение предназначено для правильного пользователя
    if user_id == receiver_id:
        hidden_message = get_hidden_message(receiver_id)

        if hidden_message:
            delete_hidden_message(receiver_id)
            await callback_query.answer(hidden_message, show_alert=True)
            try:
                await asyncio.sleep(3)
                await callback_query.message.delete()


            except TelegramAPIError as e:
                if 'message to delete not found' in str(e).lower():
                    # Игнорируем ошибку, если сообщение для удаления не найдено
                    print("Сообщение для удаления не найдено.")
                else:
                    # Обработка других ошибок
                    print(f"Произошла ошибка при удалении сообщения: {e}")
                pass
    else:
        await callback_query.answer("Вы не имеете доступа к этому сообщению.")
