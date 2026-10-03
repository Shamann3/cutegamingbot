"""Пуск игры только если в базе хватает настоящих кут.

Кнопка «N кут» и эта проверка смотрят в одну колонку users.balance.
Тёплый кэш сюда не входит: иначе на экране 0, а игра всё равно стартует.
Demo и 0demo не заменяют эту проверку. Они меняют поле, но не открывают
игру человеку, у которого на кнопке ноль.
"""

from __future__ import annotations


def stake_covers(balance, bet) -> bool:
    """Ставка разрешена только когда она больше нуля и баланс её покрывает."""
    try:
        have = int(balance)
        need = int(bet)
    except (TypeError, ValueError):
        return False
    return need > 0 and have >= need


async def read_stake_balance(user_id: int) -> int:
    """Баланс для решения «пускать ли игру». Сначала гасим кэш, потом читаем базу.

    Любая ошибка чтения закрывает игру: лучше отказать, чем сыграть в ноль.
    """
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return 0

    try:
        from bot.db_create.db import user_cache_balance
        for key in (uid, str(uid)):
            try:
                user_cache_balance.pop(key, None)
            except Exception:
                try:
                    del user_cache_balance[key]
                except Exception:
                    pass
    except Exception:
        pass

    try:
        from main import db
        db.invalidate_user_balance_cache(uid)
        raw = await db.get_user_balance(uid)
        have = int(raw or 0)
        return have if have > 0 else 0
    except Exception:
        return 0


async def paid_stake_ok(user_id, amount) -> bool:
    """Платный вход: ставка больше нуля и в базе хватает кут.

    Нулевая ставка не тратит кошелёк, поэтому её этот замок не держит.
    Ошибка чтения для платной ставки закрывает вход.
    """
    try:
        need = int(amount)
    except (TypeError, ValueError):
        return False
    if need <= 0:
        return True
    return stake_covers(await read_stake_balance(user_id), need)


async def block_short_stake(message, user_id, bet) -> bool:
    """True — игру начинать нельзя. Сообщение уже отправлено."""
    if stake_covers(await read_stake_balance(user_id), bet):
        return False
    try:
        await message.reply(
            "🎩 Недостаточно денег для игры",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        pass
    return True
