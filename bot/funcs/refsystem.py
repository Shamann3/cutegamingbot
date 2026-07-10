from main import *
@dp.message()
async def refsystem(message: Message):
    if message.text in [ '🌿 Реферальная система' , 'Рефералка помощь' , 'рефералка помощь' , 'реф помощь' ,
                         'Реф помощь' , 'Помощь реф' , 'помощь реф' , 'Помощь рефералки' , 'помощь рефералки' ,
                         'Реферальная помощь' , 'реферальная помощь' , 'Реф хелп' , 'реф хелп' ,
                         'Хелп реферальная система','хелп реферальная система' , 'Хелп реф' , 'хелп реф' , 'реферальный хелп' ,
                         'Реферальный хелп' ]:
        link = await get_start_link(message.from_user.id)
        user_id = message.from_user.id
        print(user_id)
        win_amount_formatted = "{:,.0f}".format(ref_coin).replace("," , ".")
        try:
            subscription_status = await db.get_user_subscription(user_id)
        except Exception as e:
            print(f"Ошибка при получении статуса подписки для пользователя {user_id}: {e}")
            subscription_status = 0  # Устанавливаем значение по умолчанию в случае ошибки

        # Создаем клавиатуру на основе статуса подписки

        button = InlineKeyboardButton(text="Назад" , callback_data="back_to_menu1")

        # Создаем клавиатуру с указанным параметром inline_keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ button ] ])  # Важно: inline_keyboard должен быть списком списков

        await message.reply(
            text=f'''
<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка :</b> 

<code>{link}</code>

<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>1 друг = 1 кут </b>

<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>+ 25% с каждой покупки, которую совершит ваш реферал в магазине!</b>

<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>+ Каждый приглашённый - рост вашей реферальной статистики!</b>
''' , parse_mode="HTML")