from main import *
import os
from pathlib import Path
OWNER_ID = 6801702632  # твой id

def resolve_asset(filename: str) -> Path:
    """
    Ищем файл в нескольких типичных местах, чтобы не ловить 'не найден'.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "assets" / filename,                    # CuteUpdate1/bot/funcs/assets/...
        here.parents[1] / "assets" / filename,                # CuteUpdate1/bot/assets/...
        here.parents[2] / "assets" / filename,                # CuteUpdate1/assets/...
        Path.cwd() / "assets" / filename,                     # ./assets/...
        Path.cwd() / "CuteUpdate1" / "assets" / filename,     # ./CuteUpdate1/assets/...
    ]
    for p in candidates:
        if p.exists():
            return p
    checked = "\n".join(str(p) for p in candidates)
    raise FileNotFoundError(f"{filename} не найден. Проверенные пути:\n{checked}")

@dp.message()
async def reklamachat(message: types.Message):
    if message.text.lower() != "старт чаты":
        return
    if message.from_user.id != OWNER_ID:
        return

    successful_count = 0
    failed_count = 0

    try:
        caption = (
            """
💷 | НОВЫЙ ИГРОВОЙ БОТ - ЛУНА

🌀 | Луна представляет из себя игрового бота в котором можно:

🔞 | Использовать рп команды
🎮 | Играть в игры
🪅 | Растить своего собственного - Чужого
💭 | И многое другое...

🏜️ | Скорей переходи на бота - @Lunaki_bot"""
        )

        # --- КНОПКИ ---
        kb = InlineKeyboardBuilder()
        kb.button(text="🚀 Перейти на бота", url="https://t.me/Lunaki_bot")
        kb.button(text="📢 Канал", url="https://t.me/luna_all")
        kb.button(text="💬 Чат", url="https://t.me/Lunaki_chat")
        kb.adjust(1, 2)

        # --- Находим файл устойчиво ---
        photo_path = resolve_asset("postik.jpg")

        # --- 1) ОДИН РАЗ ГРУЗИМ ФОТО -> ПОЛУЧАЕМ file_id ---
        tech_msg = await bot1.send_photo(
            chat_id=message.chat.id,  # можно в свой чат/ЛС
            photo=FSInputFile(str(photo_path), filename="postik.jpg"),
            caption="(служебная загрузка для получения file_id - будет удалено)",
            parse_mode="HTML",
        )
        file_id = tech_msg.photo[-1].file_id
        try:
            await bot1.delete_message(chat_id=message.chat.id, message_id=tech_msg.message_id)
        except Exception:
            pass

        # --- 2) РАССЫЛКА ТОЛЬКО ПО file_id ---
        chat_ids = await db.get_all_chat_ids()
        total_count = len(chat_ids)

        for idx, chat_id in enumerate(chat_ids, start=1):
            try:
                await bot1.send_photo(
                    chat_id=chat_id,
                    photo=file_id,                # ключевой момент!
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb.as_markup(),
                )
                successful_count += 1

            except aiogram.exceptions.TelegramForbiddenError:
                print(f"{idx}/{total_count} Бот удалён/заблокирован в чате {chat_id}")
                failed_count += 1

            except aiogram.exceptions.TelegramRetryAfter as e:
                print(f"{idx}/{total_count} Flood control: ждём {e.retry_after}s для {chat_id}")
                await asyncio.sleep(e.retry_after)
                try:
                    await bot1.send_photo(
                        chat_id=chat_id,
                        photo=file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=kb.as_markup(),
                    )
                    successful_count += 1
                except Exception as e2:
                    print(f"{idx}/{total_count} Повтор неудачен {chat_id}: {e2}")
                    failed_count += 1

            except aiogram.exceptions.TelegramBadRequest as e:
                print(f"{idx}/{total_count} Неверный запрос {chat_id}: {e}")
                failed_count += 1

            except Exception as e:
                print(f"{idx}/{total_count} Ошибка отправки в чат {chat_id}: {e}")
                failed_count += 1

            await asyncio.sleep(0.05)  # мягкий троттлинг

        await message.answer(f"✅ Оповещение отправлено. Успешно: {successful_count}, Ошибок: {failed_count}")

    except FileNotFoundError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        print(f"Ошибка в процессе отправки: {e}")
        await message.answer("❌ Произошла ошибка при отправке.")

