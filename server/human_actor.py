"""Наказания, которые в архив записал человек, а не сам бот.

Проверка создателя и архив группы показывают только такие строки.
Автоснятие по сроку пишется от «Системы» с admin_user_id = 0.
Числа ниже — id игрового и второго бота в Telegram, не токены.
"""

MACHINE_ADMIN_IDS = (0, 7683193125, 7357700583)
MACHINE_ADMIN_NAMES = ("система", "бот", "bot", "system", "cutegamingbot")


def human_actor_sql(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    ids = ", ".join(str(int(item)) for item in MACHINE_ADMIN_IDS)
    names = ", ".join("'" + name.replace("'", "") + "'" for name in MACHINE_ADMIN_NAMES)
    return (
        f"COALESCE({prefix}admin_user_id, 0) NOT IN ({ids})"
        f" AND lower(btrim(COALESCE({prefix}admin_name, ''))) NOT IN ({names})"
    )
