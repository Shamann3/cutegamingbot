import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, ChannelInvalidError, UserNotParticipantError, FloodWaitError
from telethon.tl.types import Channel, UserStatusRecently, UserStatusOffline, UserStatusOnline, \
    ChannelParticipantAdmin, User
#from bot.db_create.db import *
from bot.db_create.db import Database

from telethon.tl.types import User, ChannelParticipantsAdmins
from telethon.errors import FloodWaitError
from telethon.tl.types import UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth
from aiogram.enums import ParseMode  # Для ParseMode из aiogram.enums
import telethon

# Настройки API
API_ID = '25518850'  # Ваш API_ID
API_HASH = '68bb1970e5dc75f0f152ee955bfc7071'  # Ваш API_HASH
SESSION_NAME = 'session_name'

# Создание клиента
telethon_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
group_username = "LEAN_CHAT_LEAN"#



# Подключение клиента Telethon
async def connect_telethon_client():
    if not telethon_client.is_connected():
        try:
            await telethon_client.start()
            print("Telethon успешно подключен")
        except Exception as e:
            print(f"Ошибка подключения Telethon: {e}")

async def get_total_participants(group_username):
    total_count = 0
    try:
        # Получаем объект чата
        chat = await telethon_client.get_entity(group_username)

        # Перебираем всех участников с пагинацией
        participants_iter = telethon_client.iter_participants(chat)

        async for _ in participants_iter:
            total_count += 1  # Увеличиваем счетчик за каждого участника

        return total_count

    except FloodWaitError as e:
        print(f"Слишком много запросов. Ожидание {e.seconds} секунд.")
        await asyncio.sleep(e.seconds)
        return await get_total_participants(group_username)  # Повторный вызов после ожидания

    except Exception as e:
        print(f"Ошибка: {e}")
        return 0


# Получение информации о группе и участниках
async def get_group_info(group_username):
    try:
        await connect_telethon_client()
        total_participants = await get_total_participants(group_username)
        print(f"Общее количество участников: {total_participants}")

        # Получаем информацию о чате
        chat = await telethon_client.get_entity(group_username)
        if not isinstance(chat, Channel):
            return None, "Ошибка: объект не является каналом или группой.", {}, None

        admins = await telethon_client.get_participants(chat, filter=ChannelParticipantsAdmins)
        formatted_group_id = f"-100{chat.id}"

        group_info = f"""
            <b>Информация о группе:</b>
            ID группы: {formatted_group_id}
            Название группы: {chat.title or 'Отсутствует'}
            Тип: {"Супергруппа" if chat.megagroup else "Группа"}
            Имя пользователя: @{chat.username or "Отсутствует"}
            Описание: {getattr(chat, 'about', 'Отсутствует')}
            Количество участников: <пока не подсчитываем>
            Публичная группа: {"Да" if chat.username else "Нет"}
        """

        participants_info = []
        status_counts = {
            "В сети прямо сейчас": 0,
            "Недавно был онлайн": 0,
            "Был в сети недавно": 0,
            "Был в сети давно": 0,
            "Был в сети очень давно": 0
        }

        participants_iter = telethon_client.iter_participants(chat)

        # Начинаем цикл получения участников с пагинацией
        async for participant in participants_iter:
            if isinstance(participant, User):
                # Определяем статус участника
                if isinstance(participant.status, UserStatusOnline):
                    status = "В сети"
                elif isinstance(participant.status, UserStatusRecently):
                    status = "Недавно был онлайн"
                elif isinstance(participant.status, UserStatusLastWeek):
                    status = "Был в сети недавно"
                else:
                    # Пропускаем пользователей, у которых нет нужного статуса
                    continue

                # Увеличиваем счетчик для каждого статуса
                status_counts[status] += 1

                # Определяем роль участника
                is_admin = any(admin.id == participant.id for admin in admins)
                role = "Администратор" if is_admin else "Участник"

                participants_info.append(
                    {"id": participant.id, "username": participant.username or '',
                     "first_name": participant.first_name or '', "last_name": participant.last_name or '',
                     "status": status, "bot": participant.bot, "role": role}
                )

        # Заменяем информацию о количестве участников
        total_count = sum(status_counts.values())
        group_info = group_info.replace("<пока не подсчитываем>", str(total_count))

        # Добавляем информацию по статусам участников
        status_summary = "\n".join([f"{key}: {value}" for key, value in status_counts.items()])
        group_info += f"\n\n<b>Состояние участников:</b>\n{status_summary}"

        return formatted_group_id, group_info, participants_info, chat.title or 'Отсутствует'

    except FloodWaitError as e:
        print(f"Слишком много запросов. Ожидание {e.seconds} секунд.")
        await asyncio.sleep(e.seconds)
        return await get_group_info(group_username)
    except Exception as e:
        return None, f"Ошибка при получении данных: {e}", {}, None


# Форматирование информации об участнике
def format_participant_info(participant):
    return f"{str(participant['id']).ljust(10)}|{participant['username'].ljust(15)}|{participant['first_name'].ljust(15)}|{participant['last_name'].ljust(15)}|{participant['status'].ljust(15)}|{'Да' if participant['bot'] else 'Нет'.ljust(10)}|{participant['role'].ljust(15)}\n"


# Сохранение информации в файл
def save_info_to_file(group_username, group_info, participants_info):
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    file_name = f"{group_username}.txt"
    file_path = os.path.join(desktop_path, file_name)

    counter = 1
    while os.path.exists(file_path):
        file_name = f"{group_username}_{counter}.txt"
        file_path = os.path.join(desktop_path, file_name)
        counter += 1

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(group_info)
        f.write("\n\n")
        header = ("ID".ljust(10) + "|" + "Username".ljust(15) + "|" + "Имя".ljust(15) + "|" + "Фамилия".ljust(
            15) + "|" + "Статус".ljust(15) + "|" + "Бот".ljust(10) + "|" + "Роль".ljust(15) + "\n")
        f.write(header)
        f.write("-" * len(header) + "\n")
        for participant in participants_info:
            f.write(format_participant_info(participant))
    print(f"[DEBUG] Информация о группе и участниках сохранена в файл: {file_path}")


# Обработка дубликатов пользователей
async def handle_duplicate_users(db, participant_id, formatted_group_id):
    existing_user, duplicate_rowids = await db.user_exists_in_chat1111(participant_id, formatted_group_id)

    if existing_user and len(duplicate_rowids) > 1:
        print(f"❤️ Найден дубликат пользователя с id {participant_id} в чате {formatted_group_id}. Удаляем лишние записи...")
        await db.delete_duplicate_users_from_chat(duplicate_rowids)
        print(f"❤️ Дубликаты для пользователя с id {participant_id} удалены из базы.")
    else:
        print(f"❤️ Пользователь с id {participant_id} и chat_id {formatted_group_id} не имеет дубликатов.")


# Основная функция парсинга с разбиением на блоки по 2000 участников
async def parse(message: Message):
    try:
        formatted_group_id, group_info, participants_info, title = await get_group_info(group_username)

        if message.text.lower() == "парсер блокнот":
            user_id = message.from_user.id
            allowed_users = [ 6801702632 ]  # Разрешенные пользователи

            if user_id not in allowed_users:
                return  # Завершаем выполнение функции, если ID не в списке
            if formatted_group_id is None:
                await message.reply(group_info)
            else:
                save_info_to_file(group_username, group_info, participants_info)
                await message.reply(
                    f"Информация о группе '{group_username}' успешно сохранена на рабочем столе.\nchat_id группы: {formatted_group_id}"
                )

        elif message.text.lower() == "парсер":
            user_id = message.from_user.id
            allowed_users = [ 6801702632 ]  # Разрешенные пользователи

            if user_id not in allowed_users:
                return  # Завершаем выполнение функции, если ID не в списке
            if formatted_group_id is None:
                await message.reply(group_info)
            else:
                total_participants = len(participants_info)
                new_users_count = 0
                existing_users_count = 0
                recently_online_count = 0
                long_ago_count = 0
                other_status_count = 0
                online_count = 0  # Добавим счетчик для онлайн пользователей
                chunk_size = 2000

                print(f"Всего участников в группе: {total_participants}")

                processed_participants = set()
                participants_to_process = participants_info[:]

                while len(processed_participants) < total_participants:
                    remaining_participants = [
                        p for p in participants_to_process if p['id'] not in processed_participants
                    ]

                    for i in range(0, len(remaining_participants), chunk_size):
                        chunk = remaining_participants[i:i + chunk_size]

                        for participant in chunk:
                            print(f"✅ Проверяем участника {participant['id']}...")

                            current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
                            full_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()

                            # Проверка существования пользователя
                            user_exists = await db.user_exists_in_chat(participant["id"], formatted_group_id)
                            if user_exists:
                                existing_users_count += 1
                            else:
                                new_users_count += 1
                                await db.add_user_to_chat(
                                    participant["id"], full_name, participant.get("username", ""), formatted_group_id,
                                    title, current_date
                                )

                            # Определение статуса участника
                            status = participant['status']
                            if isinstance(status, UserStatusOnline):
                                recently_online_count += 1
                                online_count += 1  # Увеличиваем счетчик онлайн пользователей
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'В сети прямо сейчас'.")
                            elif isinstance(status, UserStatusRecently):
                                recently_online_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Недавно был в сети'.")
                            elif isinstance(status, UserStatusOffline):
                                long_ago_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Не был в сети долгое время'.")
                            elif isinstance(status, UserStatusLastMonth):
                                long_ago_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Не был в сети месяц назад'.")
                            elif isinstance(status, UserStatusLastWeek):
                                long_ago_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Не был в сети неделю назад'.")
                            # Добавляем проверку на строковые статусы
                            elif status == "Недавно был онлайн":
                                recently_online_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Недавно был онлайн'.")
                            elif status == "Был в сети давно":
                                long_ago_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет статус: 'Был в сети давно'.")
                            else:
                                # Выводим неизвестный статус напрямую
                                other_status_count += 1
                                print(f"Участник {full_name} ({participant['id']}) имеет неизвестный статус: {status}.")

                            processed_participants.add(participant['id'])
                            await handle_duplicate_users(db, participant['id'], formatted_group_id)

                        await asyncio.sleep(0.1)

                total_status_count = recently_online_count + long_ago_count + other_status_count

                await message.reply(
                    f"Парсинг группы '{group_username}' завершен. Все участники были обработаны.\n"
                    f"Общее количество пользователей: {total_status_count}\n"
                    f"Новых пользователей: {new_users_count}, уже существующих пользователей: {existing_users_count}.\n"
                    f"Пользователей со статусом 'недавно в сети': {recently_online_count}\n"
                    f"Пользователей со статусом 'давно': {long_ago_count}\n"
                    f"Пользователей с другими статусами: {other_status_count}\n"
                    f"Пользователей 'в сети прямо сейчас': {online_count}"  # Добавляем строку с онлайн пользователями
                )
    except Exception as e:
        print(f"Ошибка: {e}")
        await message.reply(f"Ошибка: {e}")

# Основной асинхронный цикл
#async def main():
    #await connect_telethon_client()


#if __name__ == "__main__":
    #asyncio.run(main())