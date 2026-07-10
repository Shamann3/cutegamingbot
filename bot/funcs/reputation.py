from main import *

@dp.message()
async def reputation(message: Message):
    REST_DURATION = 3
    if message.reply_to_message:
        replied_user_id = message.reply_to_message.from_user.id
        user_name = await db.get_user_first_name(replied_user_id)

        if user_name:
            # Получаем текущее время
            current_time = time.time()
            # Получаем время последнего использования функции пользователем
            last_usage_time = user_cooldowns.get(message.from_user.id , 0)

            # Проверяем, прошёл ли период отдыха


            # Проверка и обновление репутации
            if message.text in [ '+','++','+++','++++','+++++' , "лучший" , "Лучший" , "лучшая" , "Лучшая" , "Ты молодец" , "ты молодец" ,
                                 "молодец" , "Молодец" , "Харош" , "харош" , "Умница" , "умница" , "Умник" ,
                                 "умник","+ репутация" ]:

                if message.from_user.id == replied_user_id:
                    await message.reply("✊ <b>Вы не можете изменять свою собственную репутацию.</b>", parse_mode="HTML")
                    return
                if current_time - last_usage_time < REST_DURATION:
                    await message.reply(f"⌚️ Пожалуйста, подождите {REST_DURATION} секунды")
                    return



                # Обновляем время последнего использования
                user_cooldowns [ message.from_user.id ] = current_time
                await db.update_rep_plus(replied_user_id , 1)
                first_name = await db.get_firstname_by_user_id(replied_user_id)  # Получаем имя участника
                username = await db.get_username_by_user_id(replied_user_id)  # Получаем username участника

                # Формируем ссылку на пользователя
                name_link = await create_user_link(replied_user_id , first_name , username)
                await message.reply(
                    f"✅ <b>Репутация {name_link} увеличена </b>" ,
                    parse_mode="HTML",disable_web_page_preview=True)

            elif message.text in [ '-','--','---','----','-----' , 'дибил' , 'Дибил' , 'еблан' , 'Еблан' , 'Ебланка' , 'ебланка' , 'тупой' ,
                                   'Тупой' , 'Ты тупой' , 'ты тупой' , 'даун' , 'Даун' , 'дура' , 'Дура',"- репутация","ты тупой?","ты тупой?","долбоеб","Долбоеб","долбоеб","долбоеб?","уебище","Уебище" ]:
                if message.from_user.id == replied_user_id:
                    await message.reply("✊ <b>Вы не можете изменять свою собственную репутацию.</b>", parse_mode="HTML")
                    return
                if current_time - last_usage_time < REST_DURATION:
                    await message.reply(f"⌚️ Пожалуйста, подождите {REST_DURATION} секунды")
                    return

                # Обновляем время последнего использования
                user_cooldowns [ message.from_user.id ] = current_time
                await db.update_rep_minus(replied_user_id , 1)
                first_name = await db.get_firstname_by_user_id(replied_user_id)  # Получаем имя участника
                username = await db.get_username_by_user_id(replied_user_id)  # Получаем username участника

                # Формируем ссылку на пользователя
                name_link = await create_user_link(replied_user_id , first_name , username)
                await message.reply(
                    f"🔥 <b>Репутация {name_link} уменьшена</b>" ,
                    parse_mode="HTML",disable_web_page_preview=True)