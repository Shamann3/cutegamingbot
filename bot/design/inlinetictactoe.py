from main import *


from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode, ChatType  # Импортируем ParseMode из aiogram.enums

from bot.funcs.help import wordhelp,brak,ffunc,other,gamehelp,textstore,textglobhelp,textzabhelp,clanss,texteditprofile
import uuid
import time

# Обработчик для callback-запросов (кнопки инлайн)

@dp.callback_query(lambda c: c.data == 'help_profileedit')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=texteditprofile,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data == 'help_info_main')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=textglobhelp,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data == 'help_earnings')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=textzabhelp,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data == 'help_games')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=gamehelp,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data == 'help_misc')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=other,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data == 'help_marriages')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=brak,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data == 'help_market')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=textstore,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data == 'help_clans')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=clanss,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data == 'help_functions')
async def callback_main(call: CallbackQuery):

    print("Обработчик callback_main запущен.")
    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print(f"ID пользователя: {user_id}.")

    # Редактируем сообщение после нажатия на инлайн-кнопку
    try:
        # Меняем текст на то, что нужно при нажатии на кнопку
        await bot1.edit_message_text(
            text=ffunc,  # Новое сообщение
            inline_message_id=call.inline_message_id,
            parse_mode="HTML",
            reply_markup=btn_help_inline
        )
        print("Сообщение успешно отредактировано для любого пользователя.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data == 'help_hide')
async def callback_main(call: CallbackQuery):

    user_id = call.from_user.id
    first_name = re.sub(r'[<>/{}"]' , '' , call.from_user.first_name)
    username = call.from_user.username
    await inline_add_or_update_user_info(bot1 , user_id , first_name , username,db, start_balance)
    print("Обработчик callback_main запущен.")
    try:
        # Отправляем ответ на callback, чтобы избежать ошибки timeout
        await call.answer("♻️ Сообщение было удалено.")

        # Удаляем сообщение путем редактирования инлайн-сообщения на пустое
        await bot1.edit_message_text(
            inline_message_id=call.inline_message_id,
            text="♻️ Сообщение было удалено."
        )
        print("Сообщение успешно скрыто.")


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified








