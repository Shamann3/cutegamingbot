from main import *




@dp.message(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def invite(message: Message):
    # Проверяем, что сообщение пришло из группы или супергруппы
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        # Получаем идентификатор чата и его название
        chat_id = message.chat.id
        chat_name = message.chat.title

        # Получаем идентификатор пользователя, который добавил новых участников
        inviter_id = message.from_user.id

        # Обрабатываем всех новых участников
        for new_member in message.new_chat_members:
            # Получаем идентификатор добавленного участника
            invited_user_id = new_member.id

            # Проверяем, достаточно ли денег на балансе чата для выплаты
            chat_balance = await db.get_chat_balance(bot1,chat_id)
            if chat_balance >= coinchat:
                # Уменьшаем баланс чата на 10 кут
                chat_balance -= coinchat
                await db.update_chat_balance(bot1,chat_id, chat_balance)

                # Увеличиваем баланс пользователя на 10 кут
                await db.update_user_balance(inviter_id, coinchat)

                # Обновляем информацию о приглашениях
                await db.update_invite_info(inviter_id, chat_id, chat_name)

                # Уведомляем пользователя о начислении средств
                await message.reply(f"🎉 Вы получили 10 кут за приглашение нового друга в чат '{chat_name}'!")
            else:
                await message.reply(f"⚠️ Недостаточно средств на балансе чата для начисления бонуса.")

            # Логгируем действие
            print(f"Пользователь {inviter_id} добавил {invited_user_id} в чат '{chat_name}' ({chat_id}). Баланс чата: {chat_balance} кут.")
