# -*- coding: utf-8 -*-
from aiogram import Bot, Dispatcher, types
from aiogram import types
from bot.db_create.db import *
from main import *




import random
async def create_user_link(user_id: int, first_name: str, username: str = None) -> str:
    """Создает ссылку на профиль пользователя."""
    if username:
        # Если есть username, создаем гиперссылку с именем
        user_hyperlink = f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name)}</a>"
    elif first_name:
        # Если username нет, используем имя без ссылки
        user_hyperlink = html.escape(first_name)
    else:
        # Если отсутствуют и имя, и username
        return "У пользователя нет имени."

    return user_hyperlink


rp_commands = ['прижать за талию','обнять','уебать','выебать','погладить','дать автограф','стукнуть', 'поцеловать', 'поздравить', 'воздушный поцелуй', 'подмигнуть', 'кусь', 'чмок', 'пошалить', 'пожать руку', 'трахнуть', 'убить', 'минет', 'отлизать', 'заняться сексом', 'потрогать грудь', 'задушить', 'утопить', 'расстрелять', 'засосать', 'закусать', 'помурчать', 'накормить', 'покормить', 'отшлепать', 'напоить', 'приласкать', 'насрать', 'пожалеть', 'избить', 'зарезать', 'изнасиловать', 'переехать', 'нассать', 'раздеть', 'флиртовать', 'принести чай', 'вдуть', 'украсть', 'поймать', 'поняшиться',  'обрадовать', 'смешить', 'облить водой', 'сбить машиной', 'похвалить', 'порезать', 'помочь', 'поплакать', 'засудить', 'поставить раком', 'нагнуть', 'похлопать', 'поиграть','пнуть', 'ударить','оттрахать','извиниться','попросить прощения','кастрировать']
async def perform_action_with_caption(
    message: Message,
    action: str,
    caption: str = None,
    comment_emoji: str = None,
    default_emoji: str = ''
):
    mes = message.text.lower()

    # Проверка на команду
    if not mes.startswith(tuple(rp_commands)):
        print("[ОТЛАДКА] Сообщение не является командой.")
        return  # Если сообщение не является командой, ничего не делаем

    if message.reply_to_message:  # Если сообщение является ответом на другое сообщение
        replied_msg = message.reply_to_message
        replied_user = replied_msg.from_user
        replied_user_id = replied_user.id
        replied_user_first_name = replied_user.first_name
        replied_user_username = replied_user.username

        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username

        # Формирование ссылки на отправителя и того, на чье сообщение отвечаем
        user = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
        user_mention = f'<a href="tg://user?id={replied_user.id}">{replied_user.first_name}</a>'

        # Создание ссылок с учётом никнеймов
        user = await create_user_link(user_id, first_name, username)
        user_mention = await create_user_link(replied_user_id, replied_user_first_name, replied_user_username)

        # Формирование текста ответа
        response_text = f'{default_emoji} | {user} {action} {user_mention}'
        if caption:
            response_text += f'\n💬 Сказав: «{caption}»'

        elif default_emoji:
            response_text = f'<b>{default_emoji} | {user} {action} {user_mention}</b>'

        try:
            # Пытаемся отправить сообщение в ответ на сообщение пользователя
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                reply_to_message_id=replied_msg.message_id,  # Сообщение, на которое ответили
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            print(f"[ОТЛАДКА] Ответ отправлен на сообщение {replied_msg.message_id}")
        except TelegramAPIError as e:
            print(f"[ОШИБКА] Не удалось отправить ответ на сообщение {replied_msg.message_id}. Ошибка: {e}")
            # Если не удалось отправить на ответное сообщение, отправляем обычным способом
            try:
                await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)
                print(f"[ОТЛАДКА] Ответ отправлен обычным способом.")
            except Exception as reply_exception:
                print(f"[ОШИБКА] Не удалось отправить сообщение вообще. Ошибка: {reply_exception}")
    else:
        print("[ОТЛАДКА] Сообщение не является ответом.")
        return  # Если сообщение не является ответом, ничего не делаем

async def kiss(message: Message):
    mes = message.text.lower()
    if not mes.startswith(tuple(rp_commands)):
        return

    user_id = message.from_user.id

    if 'поцеловать' in mes or 'Поцеловать' in mes:
        # Извлечение партнера из сообщения
        if 'поцеловать' in mes:
            caption = mes.split('поцеловать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Поцеловать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            # Использование идентификатора пользователя, на чье сообщение был отправлен запрос
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1, lovecoins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'поцеловал(-а) + {coins} 💖' , caption , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>" , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'поцеловал(-а)' , caption , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>" , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'поцеловал(-а)' , caption , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>" , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'поцеловал(-а)' , caption , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>" , "<tg-emoji emoji-id='5474525960143385880'>💋</tg-emoji>")


    #if 'стукнуть' in mes or 'Стукнуть' in mes:
        # Извлечение партнера из сообщения
        #if 'стукнуть' in mes:
        #    caption = mes.split('стукнуть' , 1) [ 1 ].strip()
        #else:
        #    caption = mes.split('Стукнуть' , 1) [ 1 ].strip()
        #marriage = await db.is_user_married(user_id)
        #if marriage:
        #    user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
        #    partner_id = user_id2 if user_id == user_id1 else user_id1
        #    # Использование идентификатора пользователя, на чье сообщение был отправлен запрос
        #    try:
        #        requested_partner_id = message.reply_to_message.from_user.id
        #    except AttributeError:
        #        requested_partner_id = None
        #    if requested_partner_id == partner_id:
        #        xp = await db.add_xp_to_marriage(user_id)
        #        coins = random.randint(1, lovecoins)
        #        if xp > 0:

        #            item_to_send = "LoveCoin"
        #            quantity = coins

                    #receiver_inventory = await db.get_user_inventory(user_id)
                    #receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    #await db.set_user_inventory(user_id , receiver_inventory)
                    #await perform_action_with_caption(
                        #message , f'1стукнул(-а) + {coins} 💖' , caption , '💥' , '💥')
                #else:
                    #await perform_action_with_caption(message , '1стукнул(-а)' , caption , '💥' , '💥')
            #else:
                #await perform_action_with_caption(message , '1стукнул(-а)' , caption , '💥' , '💥')
        #else:
            #await perform_action_with_caption(message , '1стукнул(-а)' , caption , '💥' , '💥')

    if 'кастрировать' in mes or 'Кастрировать' in mes:
        # Извлечение партнера из сообщения
        if 'кастрировать' in mes:
            caption = mes.split('кастрировать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Кастрировать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            # Использование идентификатора пользователя, на чье сообщение был отправлен запрос
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1, lovecoins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'кастрировал(-а) + {coins} 💖' , caption , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>" , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'кастрировал(-а)' , caption , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>" , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'кастрировал(-а)' , caption , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>" , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'кастрировал(-а)' , caption , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>" , "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji>")


    elif 'попросить прощения' in mes or 'Попросить прощения' in mes:
        if 'попросить прощения' in mes:
            caption = mes.split('попросить прощения' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Попросить прощения' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'попросил(-а) прощения + {coins} 💖' , caption , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>" , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'попросил(-а) прощения' , caption , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>" , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'попросил(-а) прощения' , caption , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>" , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>")

        else:
            await perform_action_with_caption(message , 'попросил(-а) прощения' , caption , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>" , "<tg-emoji emoji-id='5377618041813080281'>🥺</tg-emoji>")


    elif 'воздушный поцелуй' in mes or 'Воздушный поцелуй' in mes:
        if 'воздушный поцелуй' in mes:
            caption = mes.split('воздушный поцелуй' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Воздушный поцелуй' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'отправил(-а) воздушный поцелуй + {coins} 💖' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'отправил(-а) воздушный поцелуй' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'отправил(-а) воздушный поцелуй' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")

        else:
            await perform_action_with_caption(message , 'отправил(-а) воздушный поцелуй' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")


    elif 'чмок' in mes or 'Чмок' in mes:
        if 'чмок' in mes:
            caption = mes.split('чмок' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Чмок' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'чмокнул(-а) + {xp} XP 💖' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'чмокнул(-а)' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'чмокнул(-а)' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'чмокнул(-а)' , caption , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>" , "<tg-emoji emoji-id='5366286462092323271'>😘</tg-emoji>")



    elif 'трахнуть' in mes or 'Трахнуть' in mes:
        if 'трахнуть' in mes:
            caption = mes.split('трахнуть' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Трахнуть' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:
                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'трахнул(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>" , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'трахнул(-а)' , caption , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>" , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'трахнул(-а)' , caption , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>" , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'трахнул(-а)' , caption , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>" , "<tg-emoji emoji-id='5868738502614584375'>😈</tg-emoji>")



    elif 'пошалить' in mes or 'Пошалить' in mes:
        if 'пошалить' in mes:
            caption = mes.split('пошалить' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Пошалить' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'решил(-а) пошалить с + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>" , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'решил(-а) пошалить с' , caption , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>" , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'решил(-а) пошалить с' , caption , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>" , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'решил(-а) пошалить с' , caption , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>" , "<tg-emoji emoji-id='5834815029844643624'>🫦</tg-emoji>")


    elif 'минет' in mes or 'Минет' in mes:
        if 'минет' in mes:
            caption = mes.split('минет' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Минет' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'отсосал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>" , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'отсосал(-а)' , caption , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>" , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'отсосал(-а)' , caption , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>" , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'отсосал(-а)' , caption , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>" , "<tg-emoji emoji-id='5832644989028404876'>🍌</tg-emoji>")


    elif 'отлизать' in mes or 'Отлизать' in mes:
        if 'отлизать' in mes:
            caption = mes.split('отлизать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Отлизать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'отлизал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>" , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'отлизал(-а)' , caption , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>" , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'отлизал(-а)' , caption , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>" , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'отлизал(-а)' , caption , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>" , "<tg-emoji emoji-id='5834976056758505296'>👅</tg-emoji>")


    elif 'заняться сексом' in mes or 'Заняться сексом' in mes:
        if 'заняться сексом' in mes:
            caption = mes.split('заняться сексом' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Заняться сексом' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'занялись сексом + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>" , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'занялись сексом' , caption , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>" , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'занялись сексом' , caption , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>" , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'занялись сексом' , caption , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>" , "<tg-emoji emoji-id='5834683754169241985'>🔞</tg-emoji>")



    elif 'потрогать грудь' in mes or 'Потрогать грудь' in mes:
        if 'потрогать грудь' in mes:
            caption = mes.split('потрогать грудь' , 1) [ 1 ].strip()

        else:
            caption = mes.split('Потрогать грудь' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'потрогал(-а) грудь + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>" , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'потрогал(-а) грудь' , caption , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>" , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'потрогал(-а) грудь' , caption , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>" , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'потрогал(-а) грудь' , caption , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>" , "<tg-emoji emoji-id='5980878659899101595'>💇‍♀️</tg-emoji>")


    elif 'засосать' in mes or 'Засосать' in mes:
        if 'засосать' in mes:
            caption = mes.split('засосать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Засосать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'засосал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>" , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'засосал(-а)' , caption , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>" , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'засосал(-а)' , caption , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>" , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'засосал(-а)' , caption , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>" , "<tg-emoji emoji-id='5834760818767433249'>👄</tg-emoji>")


    elif 'помурчать' in mes or 'Помурчать' in mes:
        if 'помурчать' in mes:
            caption = mes.split('помурчать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Помурчать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'нежно мурчит для + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>" , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'нежно мурчит для' , caption , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>" , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'нежно мурчит для' , caption , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>" , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'нежно мурчит для' , caption , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>" , "<tg-emoji emoji-id='5262606930819426800'>🐱</tg-emoji>")


    elif 'поднять на руки' in mes or 'Поднять на руки' in mes:
        if 'поднять на руки' in mes:
            caption = mes.split('поднять на руки' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Поднять на руки' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'романтично поднял(-а) на руки + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
                else:
                    await perform_action_with_caption(
                        message , 'романтично поднял(-а) на руки' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'романтично поднял(-а) на руки' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'романтично поднял(-а) на руки' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")



    elif 'накормить' in mes or 'Накормить' in mes:
        if 'накормить' in mes:
            caption = mes.split('накормить' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Накормить' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'покормил(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")



    elif 'покормить' in mes or 'Покормить' in mes:
        if 'покормить' in mes:
            caption = mes.split('покормить' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Покормить' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'покормил(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'покормил(-а)' , caption , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>" , "<tg-emoji emoji-id='5348308557919970713'>🍫</tg-emoji>")



    elif 'отшлепать' in mes or 'Отшлепать' in mes:
        if 'отшлепать' in mes:
            caption = mes.split('отшлепать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Отшлепать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'отшлёпал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>" , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'отшлёпал(-а)' , caption , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>" , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'отшлёпал(-а)' , caption , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>" , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'отшлёпал(-а)' , caption , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>" , "<tg-emoji emoji-id='5373117556036999296'>🫣</tg-emoji>")


    elif 'напоить' in mes or 'Напоить' in mes:
        if 'напоить' in mes:
            caption = mes.split('напоить' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Напоить' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'напоил(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>" , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'напоил(-а)' , caption , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>" , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'напоил(-а)' , caption , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>" , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'напоил(-а)' , caption , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>" , "<tg-emoji emoji-id='5330015368788322059'>🥃</tg-emoji>")


    elif 'приласкать' in mes or 'Приласкать' in mes:
        if 'приласкать' in mes:
            caption = mes.split('приласкать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Приласкать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'Нежно приласкал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>" , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'Нежно приласкал(-а)' , caption , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>" , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'Нежно приласкал(-а)' , caption , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>" , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'Нежно приласкал(-а)' , caption , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>" , "<tg-emoji emoji-id='5255911149819412788'>💕</tg-emoji>")


    elif 'пожалеть' in mes or 'Пожалеть' in mes:
        if 'пожалеть' in mes:
            caption = mes.split('пожалеть' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Пожалеть' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'пожалел(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'пожалел(-а)' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'пожалел(-а)' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'пожалел(-а)' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>", "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")



    elif 'раздеть' in mes or 'Раздеть' in mes:
        if 'раздеть' in mes:
            caption = mes.split('раздеть' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Раздеть' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'нежно снял(-а) одежку с + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'нежно снял(-а) одежку с' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'нежно снял(-а) одежку с' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>", "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'нежно снял(-а) одежку с' , caption , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>" , "<tg-emoji emoji-id='5377509400615327935'>🥹</tg-emoji>")


    elif 'флиртовать' in mes or 'Флиртовать' in mes:
        if 'флиртовать' in mes:
            caption = mes.split('флиртовать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Флиртовать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(message , f'Флиртует с + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>" , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'Флиртует с' , caption , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>" , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'Флиртует с' , caption , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>" , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'Флиртует с' , caption , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>" , "<tg-emoji emoji-id='5296688956602078390'>❤️</tg-emoji>")


    elif 'принести чай' in mes or 'Принести чай' in mes:
        if 'принести чай' in mes:
            caption = mes.split('принести чай' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Принести чай' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'принес(-ла) чай для + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>" , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'принес(-ла) чай для' , caption , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>" , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'принес(-ла) чай для' , caption , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>" , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'принес(-ла) чай для' , caption , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>" , "<tg-emoji emoji-id='5359370246190801956'>☕️</tg-emoji>")



    elif 'вдуть' in mes or 'Вдуть' in mes:
        if 'вдуть' in mes:
            caption = mes.split('вдуть' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Вдуть' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:

                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'вдул(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'вдул(-а)' , caption , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'вдул(-а)' , caption , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'вдул(-а)' , caption , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5866442237004485645'>🍆</tg-emoji>")


    elif 'украсть' in mes or 'Украсть' in mes:
        if 'украсть' in mes:
            caption = mes.split('украсть' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Украсть' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'украл(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'украл(-а)' , caption , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'украл(-а)' , caption , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'украл(-а)' , caption , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>" , "<tg-emoji emoji-id='5868225885382904788'>🍆</tg-emoji>")


    elif 'поймать' in mes or 'Поймать' in mes:
        if 'поймать' in mes:
            caption = mes.split('поймать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Поймать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'поймал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>" , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'поймал(-а)' , caption , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>" , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'поймал(-а)' , caption , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>", "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'поймал(-а)' , caption , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>" , "<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji>")



    elif 'поняшиться' in mes or 'Поняшиться' in mes:
        if 'поняшиться' in mes:
            caption = mes.split('поняшиться' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Поняшиться' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'мило няшиться с + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>" , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'мило няшиться с' , caption , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>" , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'мило няшиться с' , caption , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>", "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'мило няшиться с' , caption , "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>", "<tg-emoji emoji-id='5370900820336319679'>🥰</tg-emoji>")


    elif 'обрадовать' in mes or 'Обрадовать' in mes:
        if 'обрадовать' in mes:
            caption = mes.split('обрадовать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Обрадовать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'обрадовал(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'обрадовал(-а)' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>" , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'обрадовал(-а)' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>", "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'обрадовал(-а)' , caption , "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>", "<tg-emoji emoji-id='5465511459444235288'>💕</tg-emoji>")


    elif 'смешить' in mes or 'Смешить' in mes:
        if 'смешить' in mes:
            caption = mes.split('смешить' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Смешить' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'разсмешил(-а) + {coins} XP 💖' , caption , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>" , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>")
                else:
                    await perform_action_with_caption(message , 'разсмешил(-а)' , caption , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>" , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>")
            else:
                await perform_action_with_caption(message , 'разсмешил(-а)' , caption , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>", "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>")
        else:
            await perform_action_with_caption(message , 'разсмешил(-а)' , caption , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>" , "<tg-emoji emoji-id='5370953476635368811'>😂</tg-emoji>")


    elif 'оттрахать' in mes or 'Оттрахать' in mes:
        if 'оттрахать' in mes:
            caption = mes.split('оттрахать' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Оттрахать' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'оттрахал(-а) + {coins} XP 💖' , caption , '👉👌' , '👉👌')
                else:
                    await perform_action_with_caption(message , 'оттрахал(-а)' , caption , '👉👌' , '👉👌')
            else:
                await perform_action_with_caption(message , 'оттрахал(-а)' , caption , '👉👌' , '👉👌')
        else:
            await perform_action_with_caption(message , 'оттрахал(-а)' , caption , '👉👌' , '👉👌')

    elif 'обнять' in mes or 'Обнять' in mes:
        if 'обнять' in mes:
            caption = mes.split('обнять' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Обнять' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'обнял(-а) + {coins} XP 💖' , caption , '💕' , '💕')
                else:
                    await perform_action_with_caption(message , 'обнял(-а)' , caption , '💕' , '💕')
            else:
                await perform_action_with_caption(message , 'обнял(-а)' , caption , '💕' , '💕')
        else:
            await perform_action_with_caption(message , 'обнял(-а)' , caption , '💕' , '💕')

    elif 'извиниться' in mes or 'Извиниться' in mes:
        if 'извиниться' in mes:
            caption = mes.split('извиниться' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Извиниться' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'извинился(-ась) перед {coins} 💖' , caption , '🥺' , '🥺')
                else:
                    await perform_action_with_caption(message , 'извинился(-ась) перед' , caption , '🥺' , '🥺')
            else:
                await perform_action_with_caption(message , 'извинился(-ась) перед' , caption , '🥺' , '🥺')

        else:
            await perform_action_with_caption(message , 'извинился(-ась) перед' , caption , '🥺' , '🥺')


    elif 'дать автограф' in mes or 'Дать автограф' in mes:
        if 'дать автограф' in mes:
            caption = mes.split('дать автограф' , 1) [ 1 ].strip()
        else:
            caption = mes.split('Дать автограф' , 1) [ 1 ].strip()
        marriage = await db.is_user_married(user_id)
        if marriage:
            user_id1 , user_id2 = marriage [ 0 ] , marriage [ 1 ]
            partner_id = user_id2 if user_id == user_id1 else user_id1
            try:
                requested_partner_id = message.reply_to_message.from_user.id
            except AttributeError:
                requested_partner_id = None
            if requested_partner_id == partner_id:
                xp = await db.add_xp_to_marriage(user_id)
                coins = random.randint(1 , lovecoins)
                print(coins)
                if xp > 0:

                    item_to_send = "LoveCoin"
                    quantity = coins

                    receiver_inventory = await db.get_user_inventory(user_id)
                    receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity
                    await db.set_user_inventory(user_id , receiver_inventory)
                    await perform_action_with_caption(
                        message , f'дал(-а) автограф {coins} 💖' , caption , '📜 ✍️' , '📜 ✍️')
                else:
                    await perform_action_with_caption(message , 'дал(-а) автограф' , caption , '📜 ✍️' , '📜 ✍️')
            else:
                await perform_action_with_caption(message , 'дал(-а) автограф' , caption , '📜 ✍️' , '📜 ✍️')

        else:
            await perform_action_with_caption(message , 'дал(-а) автограф' , caption , '📜 ✍️' , '📜 ✍️')


    elif 'кастрировать' in mes:
        caption = mes.split('кастрировать', 1)[1].strip()
        await perform_action_with_caption(message, 'кастрировал(-а)', caption, '✂️', '✂️')

    elif 'Кастрировать' in mes:
        caption = mes.split('Кастрировать', 1)[1].strip()
        await perform_action_with_caption(message, 'кастрировал(-а)', caption, '✂️', '✂️')

    elif 'попросить прощения' in mes:
        caption = mes.split('попросить прощения', 1)[1].strip()
        await perform_action_with_caption(message, 'попросил(-а) прощения', caption, '🥺', '🥺')

    elif 'Попросить прощения' in mes:
        caption = mes.split('Попросить прощения', 1)[1].strip()
        await perform_action_with_caption(message, 'попросил(-а) прощения', caption, '🥺', '🥺')

    elif 'извивниться' in mes:
        caption = mes.split('извивниться', 1)[1].strip()
        await perform_action_with_caption(message, 'извинился(-ась)', caption, '🥺', '🥺')

    elif 'Извивниться' in mes:
        caption = mes.split('Извивниться', 1)[1].strip()
        await perform_action_with_caption(message, 'извинился(-ась)', caption, '🥺', '🥺')


    elif 'поздравить' in mes:
        caption = mes.split('поздравить', 1)[1].strip()
        await perform_action_with_caption(message, 'поздравил(-а)', caption, '🎉', '🎉')

    elif 'Поздравить' in mes:
        caption = mes.split('Поздравить', 1)[1].strip()
        await perform_action_with_caption(message, 'поздравил(-а)', caption, '🎉', '🎉')
    elif 'подмигнуть' in mes:
        caption = mes.split('подмигнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'подмигнул(-а)', caption, '😉', '😉')

    elif 'Подмигнуть' in mes:
        caption = mes.split('Подмигнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'подмигнул(-а)', caption, '😉', '😉')

    elif 'кусь' in mes:
        caption = mes.split('кусь', 1)[1].strip()
        await perform_action_with_caption(message, 'укусил(-а)', caption, '😝', '😝')

    elif 'Кусь' in mes:
        caption = mes.split('Кусь', 1)[1].strip()
        await perform_action_with_caption(message, 'укусил(-а)', caption, '😝', '😝')

    elif 'пожать руку' in mes:
        caption = mes.split('пожать руку', 1)[1].strip()
        await perform_action_with_caption(message, 'пожал(-а) руку', caption, '🤝', '🤝')

    elif 'Пожать руку' in mes:
        caption = mes.split('Пожать руку', 1)[1].strip()
        await perform_action_with_caption(message, 'пожал(-а) руку', caption, '🤝', '🤝')

    elif 'убить' in mes:
        caption = mes.split('убить', 1)[1].strip()
        await perform_action_with_caption(message, 'убил(-а)', caption, '⚰️😵', '⚰️😵')

    elif 'Убить' in mes:
        caption = mes.split('Убить', 1)[1].strip()
        await perform_action_with_caption(message, 'убил(-а)', caption, '⚰️😵', '⚰️😵')


    elif 'задушить' in mes:
        caption = mes.split('задушить', 1)[1].strip()
        await perform_action_with_caption(message, 'задушил(-а)', caption, '😵', '😵')

    elif 'Задушить' in mes:
        caption = mes.split('Задушить', 1)[1].strip()
        await perform_action_with_caption(message, 'задушил(-а)', caption, '😵', '😵')


    elif 'утопить' in mes:
        caption = mes.split('утопить', 1)[1].strip()
        await perform_action_with_caption(message, 'утопил(-а)', caption, '💦☠️', '💦☠️')

    elif 'Утопить' in mes:
        caption = mes.split('Утопить', 1)[1].strip()
        await perform_action_with_caption(message, 'утопил(-а)', caption, '💦☠️', '💦☠️')


    elif 'расстрелять' in mes:
        caption = mes.split('расстрелять', 1)[1].strip()
        await perform_action_with_caption(message, 'расстрелял(-а)', caption, '☠️🔫', '☠️🔫')

    elif 'расстрелять' in mes:
        caption = mes.split('расстрелять', 1)[1].strip()
        await perform_action_with_caption(message, 'расстрелял(-а)', caption, '☠️🔫', '☠️🔫')


    elif 'закусать' in mes:
        caption = mes.split('закусать', 1)[1].strip()
        await perform_action_with_caption(message, 'закусал(-а)', caption, '😵🧛', '😵🧛')

    elif 'Закусать' in mes:
        caption = mes.split('Закусать', 1)[1].strip()
        await perform_action_with_caption(message, 'закусал(-а)', caption, '😵🧛', '😵🧛')


    elif 'насрать' in mes:
        caption = mes.split('насрать', 1)[1].strip()
        await perform_action_with_caption(message, 'насрал(-а) на', caption, '💩', '💩')

    elif 'Насрать' in mes:
        caption = mes.split('Насрать', 1)[1].strip()
        await perform_action_with_caption(message, 'насрал(-а) на', caption, '💩', '💩')


    elif 'избить' in mes:
        caption = mes.split('избить', 1)[1].strip()
        await perform_action_with_caption(message, 'избил(-а)', caption, '🤬', '🤬')

    elif 'Избить' in mes:
        caption = mes.split('Избить', 1)[1].strip()
        await perform_action_with_caption(message, 'избил(-а)', caption, '🤬', '🤬')


    elif 'зарезать' in mes:
        caption = mes.split('зарезать', 1)[1].strip()
        await perform_action_with_caption(message, 'зарезал(-а)', caption, '🔪🩸', '🔪🩸')

    elif 'Зарезать' in mes:
        caption = mes.split('Зарезать', 1)[1].strip()
        await perform_action_with_caption(message, 'зарезал(-а)', caption, '🔪🩸', '🔪🩸')


    elif 'изнасиловать' in mes:
        caption = mes.split('изнасиловать', 1)[1].strip()
        await perform_action_with_caption(message, 'изнасиловал(-а)', caption, '🤫🩸', '🤫🩸')

    elif 'Изнасиловать' in mes:
        caption = mes.split('Изнасиловать', 1)[1].strip()
        await perform_action_with_caption(message, 'изнасиловал(-а)', caption, '🤫🩸', '🤫🩸')


    elif 'переехать' in mes:
        caption = mes.split('переехать', 1)[1].strip()
        await perform_action_with_caption(message, 'переехал(-а)', caption, '🚘🩸', '🚘🩸')

    elif 'Переехать' in mes:
        caption = mes.split('Переехать', 1)[1].strip()
        await perform_action_with_caption(message, 'переехал(-а)', caption, '🚘🩸', '🚘🩸')


    elif 'нассать' in mes:
        caption = mes.split('нассать', 1)[1].strip()
        await perform_action_with_caption(message, 'нассал(-а) на', caption, '😣', '😣')

    elif 'Нассать' in mes:
        caption = mes.split('Нассать', 1)[1].strip()
        await perform_action_with_caption(message, 'нассал(-а) на', caption, '😣', '😣')


    elif 'облить водой' in mes:
        caption = mes.split('облить водой', 1)[1].strip()
        await perform_action_with_caption(message, 'облил водой(-а)', caption, '💦', '💦')

    elif 'Облить водой' in mes:
        caption = mes.split('Облить водой', 1)[1].strip()
        await perform_action_with_caption(message, 'облил водой(-а)', caption, '💦', '💦')


    elif 'сбить машиной' in mes:
        caption = mes.split('сбить машиной', 1)[1].strip()
        await perform_action_with_caption(message, 'сбил машиной(-а)', caption, '🚗', '🚗')

    elif 'Сбить машиной' in mes:
        caption = mes.split('Сбить машиной', 1)[1].strip()
        await perform_action_with_caption(message, 'сбил машиной(-а)', caption, '🚗', '🚗')


    elif 'похвалить' in mes:
        caption = mes.split('похвалить', 1)[1].strip()
        await perform_action_with_caption(message, 'похвалил(-а)', caption, '😉🥹', '😉🥹')

    elif 'Похвалить' in mes:
        caption = mes.split('Похвалить', 1)[1].strip()
        await perform_action_with_caption(message, 'похвалил(-а)', caption, '😉🥹', '😉🥹')


    elif 'порезать' in mes:
        caption = mes.split('порезать', 1)[1].strip()
        await perform_action_with_caption(message, 'порезал(-а)', caption, '🔪🩸', '🔪🩸')

    elif 'Порезать' in mes:
        caption = mes.split('Порезать', 1)[1].strip()
        await perform_action_with_caption(message, 'порезал(-а)', caption, '🔪🩸', '🔪🩸')


    elif 'помочь' in mes:
        caption = mes.split('помочь', 1)[1].strip()
        await perform_action_with_caption(message, 'помог(-ла)', caption, '🆘', '🆘')

    elif 'Помочь' in mes:
        caption = mes.split('Помочь', 1)[1].strip()
        await perform_action_with_caption(message, 'помог(-ла)', caption, '🆘', '🆘')


    elif 'поплакать' in mes:
        caption = mes.split('поплакать', 1)[1].strip()
        await perform_action_with_caption(message, 'поплакал(-а)', caption, '😭', '😭')

    elif 'Поплакать' in mes:
        caption = mes.split('Поплакать', 1)[1].strip()
        await perform_action_with_caption(message, 'поплакал(-а)', caption, '😭', '😭')


    elif 'засудить' in mes:
        caption = mes.split('засудить', 1)[1].strip()
        await perform_action_with_caption(message, 'засудил(-а)', caption, '🤵', '🤵')

    elif 'Засудить' in mes:
        caption = mes.split('Засудить', 1)[1].strip()
        await perform_action_with_caption(message, 'засудил(-а)', caption, '🤵', '🤵')


    elif 'поставить раком' in mes:
        caption = mes.split('поставить раком', 1)[1].strip()
        await perform_action_with_caption(message, 'поставил(-а) раком', caption, '🦞', '🦞')

    elif 'Поставить раком' in mes:
        caption = mes.split('Поставить раком', 1)[1].strip()
        await perform_action_with_caption(message, 'поставил(-а) раком', caption, '🦞', '🦞')


    elif 'нагнуть' in mes:
        caption = mes.split('нагнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'нагнул(-а)', caption, '🥸', '🥸')

    elif 'Нагнуть' in mes:
        caption = mes.split('Нагнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'нагнул(-а)', caption, '🥸', '🥸')


    elif 'похлопать' in mes:
        caption = mes.split('похлопать', 1)[1].strip()
        await perform_action_with_caption(message, 'похлопал(-а)', caption, '👏', '👏')

    elif 'Похлопать' in mes:
        caption = mes.split('Похлопать', 1)[1].strip()
        await perform_action_with_caption(message, 'похлопал(-а)', caption, '👏', '👏')


    elif 'поиграть' in mes:
        caption = mes.split('поиграть', 1)[1].strip()
        await perform_action_with_caption(message, 'поиграл(-а)', caption, '🎮', '🎮')

    elif 'Поиграть' in mes:
        caption = mes.split('Поиграть', 1)[1].strip()
        await perform_action_with_caption(message, 'поиграл(-а)', caption, '🎮', '🎮')


    elif 'ударить' in mes:
        caption = mes.split('ударить', 1)[1].strip()
        await perform_action_with_caption(message, 'ударил(-а)', caption, '💥', '💥')

    elif 'Ударить' in mes:
        caption = mes.split('Ударить', 1)[1].strip()
        await perform_action_with_caption(message, 'ударил(-а)', caption, '💥', '💥')

    elif 'стукнуть' in mes:
        caption = mes.split('стукнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'стукнул(-а)', caption, '👊💥', '👊💥')

    elif 'Стукнуть' in mes:
        caption = mes.split('Стукнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'стукнул(-а)', caption, '👊💥', '👊💥')


    elif 'дать автограф' in mes:
        caption = mes.split('с', 1)[1].strip()
        await perform_action_with_caption(message, 'дал(-а) автограф', caption, '📜 ✍️', '📜 ✍️')

    elif 'Дать автограф' in mes:
        caption = mes.split('Дать автограф', 1)[1].strip()
        await perform_action_with_caption(message, 'дал(-а) автограф', caption, '📜 ✍️', '📜 ✍️')

    elif 'пнуть' in mes:
        caption = mes.split('пнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'пнул (-а)', caption, '💥', '💥')

    elif 'Пнуть' in mes:
        caption = mes.split('Пнуть', 1)[1].strip()
        await perform_action_with_caption(message, 'пнул (-а)', caption, '💥', '💥')

    elif 'погладить' in mes:
        caption = mes.split('погладить' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'погладил(-а)' , caption , '☺️' , '☺️')

    elif 'Погладить' in mes:
        caption = mes.split('Погладить' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'погладил(-а)' , caption , '☺️' , '☺️')


    elif 'выебать' in mes:
        caption = mes.split('выебать' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'выебал(-а)' , caption , '🍓🔞' , '🍓🔞')

    elif 'Выебать' in mes:
        caption = mes.split('Выебать' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'выебал(-а)' , caption , '🍓🔞' , '🍓🔞')

    elif 'уебать' in mes:
        caption = mes.split('уебать' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'уебал(-а)' , caption , '👊🔞' , '👊🔞')

    elif 'Уебать' in mes:
        caption = mes.split('Уебать' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'уебал(-а)' , caption , '👊🔞' , '👊🔞')


    elif 'прижать за талию' in mes:
        caption = mes.split('прижать за талию' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'прижал(-а) за талию' , caption , '👫🫦' , '👫🫦')

    elif 'Прижать за талию' in mes:
        caption = mes.split('Прижать за талию' , 1) [ 1 ].strip()
        await perform_action_with_caption(message , 'Прижал(-а) за талию' , caption , '👫🫦' , '👫🫦')



    elif message.text.lower() in ['рп команды','команды рп','рп функции','функции рп','взаимодействия рп','рп взаимодействия']:
        user_id = message.from_user.id
        chat_type = message.chat.type  # Определяем тип чата (private, group, supergroup)

        if chat_type in [ 'group' , 'supergroup' ]:
            sent_successfully = await send_rp_list(user_id)

            if sent_successfully:

                button = InlineKeyboardButton(text="Перейти в лс" , url=f"https://t.me/CuteGamingBot")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
                await message.reply("✏️" , reply_markup=keyboard, parse_mode="HTML")
            else:
                button = InlineKeyboardButton(text="Запустить бот" , url=f"https://t.me/CuteGamingBot")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
                await message.reply("❓",parse_mode="HTML")
                await message.reply(
                    "📕 <b>Бот не смог написать вам. Запустите его и попробуйте снова</b>" ,
                    reply_markup=keyboard, parse_mode="HTML")

        else:
            await send_rp_list(user_id)




    else:
        if 'поцеловать' in mes or 'поздравить' in mes or 'поцеловать в щеку' in mes or 'воздушный поцелуй' in mes or 'подмигнуть' in mes or 'обнять' in mes or 'кусь' in mes or 'чмок' in mes or 'пошалить' in mes or 'пожать руку' in mes or 'трахнуть' in mes or 'убить' in mes or 'минет' in mes or 'отлизать' in mes or 'заняться сексом' in mes or 'потрогать за грудь' in mes or 'задушить' in mes or 'утопить' in mes or 'расстрелять' in mes or 'засосать' in mes or 'закусать' in mes or 'помурчать' in mes or 'поднять на руки' in mes or 'накормить' in mes or 'покормить' in mes or 'отшлепать' in mes or 'напоить' in mes or 'приласкать' in mes or 'насрать' in mes or 'пожалеть' in mes or 'избить' in mes or 'зарезать' in mes or 'изнасиловать' in mes or 'переехать' in mes or 'нассать' in mes or 'раздеть' in mes or 'флиртовать' in mes or 'принести чай' in mes or 'вдуть' in mes or 'украсть' in mes or 'поймать' in mes or 'поняшится' in mes or 'обрадовать' in mes or 'смешить' in mes or 'облить водой' in mes or 'сбить машиной' in mes or 'похвалить' in mes or 'порезать' in mes or 'помочь' in mes or 'поплакать' in mes or 'засудить' in mes or 'поставить раком' in mes or 'нагнуть' in mes or 'похлопать' in mes or 'поиграть' in mes or 'ударить' in mes or 'оттрахать' in mes or 'извиниться' in mes or 'попросить прощения' in mes or 'кастрировать' in mes or 'стукнуть' in mes or 'дать автограф' in mes or 'прижать за талию' in mes:
            pass


async def send_rp_list(user_id):
    """Функция для отправки списка РП-команд в ЛС."""
    chunk_size = 50
    try:
        await bot1.send_message(user_id, "📖", parse_mode=ParseMode.HTML)
        for i in range(0, len(rp_commands), chunk_size):
            chunk = rp_commands[i:i + chunk_size]
            response = "\n".join(f"<b>{i + j + 1} | {cmd}</b>" for j, cmd in enumerate(chunk))
            await bot1(
                SendMessage(
                    chat_id=user_id ,  # Идентификатор чата
                    text=response ,  # Текст сообщения
                    message_effect_id="5107584321108051014" ,  # Дополнительный параметр, если он нужен
                      # Клавиатура (если нужна)
                    parse_mode=ParseMode.HTML  # Указание на использование HTML разметки
                ))
            await asyncio.sleep(0.5)
        return True
    except Exception:
        return False
