"""Распознавание команд царя статистики и кнопка «Открыть в ЛС»."""
import io, sys, asyncio, types as pytypes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import bot.funcs.king_stats as ks

# Любое упоминание царя статистики открывает меню
for text in ("система царя статистики", "статистика царя", "царя статистику покажи",
             "царь статистики", "king stats", "царь", "включить царя статистики",
             "настройки царя статистики"):
    assert ks.is_king_stats_command(text) is True, f"должно распознаваться: {text!r}"

# Посторонний текст не задевается
for text in ("привет как дела", "статистика группы", "бан @user", "баланс"):
    assert ks.is_king_stats_command(text) is False, f"не должно распознаваться: {text!r}"

# Справочное сообщение удалено вместе с клавиатурой
assert not hasattr(ks, '_HELP_TEXT'), "_HELP_TEXT должен быть удалён"
assert not hasattr(ks, '_help_keyboard_for_user'), "клавиатура справки должна быть удалена"


class Bot:
    async def get_me(self):
        return pytypes.SimpleNamespace(username="CuteGamingBot")


class BrokenBot:
    async def get_me(self):
        raise Exception("нет связи")


kb = asyncio.run(ks._open_in_dm_keyboard(Bot()))
button = kb.inline_keyboard[0][0]
assert button.text == "Открыть в ЛС", button.text
assert button.url == "https://t.me/CuteGamingBot", button.url

# Без username кнопку не рисуем, а не падаем
assert asyncio.run(ks._open_in_dm_keyboard(BrokenBot())) is None

print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
