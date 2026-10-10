from main import *
@dp.message()
async def refsystem(message: Message):
    if message.text in [ '🌿 Реферальная система' , 'Рефералка помощь' , 'рефералка помощь' , 'реф помощь' ,
                         'Реф помощь' , 'Помощь реф' , 'помощь реф' , 'Помощь рефералки' , 'помощь рефералки' ,
                         'Реферальная помощь' , 'реферальная помощь' , 'Реф хелп' , 'реф хелп' ,
                         'Хелп реферальная система','хелп реферальная система' , 'Хелп реф' , 'хелп реф' , 'реферальный хелп' ,
                         'Реферальный хелп' ]:
        link = await get_start_link(message.from_user.id)
        from bot.funcs.referral_copy import referral_card
        await message.reply(text=referral_card(link, ref_coin), parse_mode="HTML")