"""Тексты реферальной системы. Одни и те же слова на всех экранах."""


def cute_amount(coins: int) -> str:
    try:
        amount = int(coins)
    except (TypeError, ValueError):
        amount = 0
    if amount < 0:
        amount = 0
    shown = f"{amount:,}".replace(",", ".")
    return f"{shown} кут"


def referral_card(link: str, coins: int) -> str:
    amount = cute_amount(coins)
    return (
        "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{link}</code>\n\n"
        "<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
        f"<b>Друг заходит по ней в первый раз и играет одну игру — вам обоим приходит {amount}.</b>\n\n"
        "<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> "
        "<b>С каждой его покупки в магазине вам приходит 25%.</b>\n\n"
        "<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> "
        "<b>Повторный вход по этой ссылке не считается. "
        "Человек, который уже открывал бота, тоже не считается.</b>"
    )


def referral_share_text(coins: int) -> str:
    amount = cute_amount(coins)
    return (
        "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Вас приглашают в бота.</b>\n\n"
        f"<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>Кнопка ниже — первый вход. "
        f"Одна игра, и вам с пригласившим придёт {amount}.</b>\n"
        "<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> "
        "<b>Если вы уже открывали бота, ссылка не сработает.</b>"
    )


def referral_button_label() -> str:
    return "Зайти по приглашению"


def visitor_text(verdict: str, coins: int) -> str:
    amount = cute_amount(coins)
    if verdict == "ok":
        return (
            "<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>Вы зашли по приглашению.</b>\n\n"
            f"<tg-emoji emoji-id='5317000922096769303'>🎁</tg-emoji> <b>Сыграйте одну игру — "
            f"вам и пригласившему придёт {amount}.</b>\n"
            "<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> "
            "<b>С ваших покупок в магазине пригласившему придёт 25%.</b>\n\n"
            "<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
            "<b>Эта ссылка срабатывает один раз и только при первом входе.</b>"
        )
    lines = {
        "self": "Это ваша ссылка. Себя по ней пригласить нельзя.",
        "no_inviter": "Такой ссылки нет. Попросите новую у того, кто вас приглашает.",
        "same": "Вы уже заходили по этой ссылке. Второй раз она не считается.",
        "taken": "Вас уже пригласил другой человек. Новая ссылка не заменяет первую.",
        "used": "Вы уже открывали бота раньше. Приглашение считается только при самом первом входе.",
        "bad": "Ссылка повреждена. Попросите отправить её ещё раз.",
    }
    line = lines.get(verdict, lines["bad"])
    return f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>{line}</b>"


def inviter_arrived_text(guest_html: str, coins: int) -> str:
    amount = cute_amount(coins)
    return (
        "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> "
        "<b>По вашей ссылке зашёл новый человек.</b>\n"
        f"<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>{guest_html}</b>\n\n"
        f"<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>Это его первый вход. "
        f"{amount} придёт вам обоим, когда он сыграет одну игру.</b>\n"
        "<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> "
        "<b>С его покупок в магазине вам придёт 25%.</b>"
    )


def inviter_skip_text(verdict: str) -> str:
    lines = {
        "used": "Этот человек уже открывал бота. Приглашение считается только при первом входе.",
        "same": "Этого человека уже приглашали. Вторая ссылка не сработает.",
        "taken": "Этого человека уже пригласил кто-то другой. Ваша ссылка его не заменит.",
        "self": "Себя пригласить нельзя.",
        "no_inviter": "Ссылка ещё не готова. Откройте бота в личных сообщениях и зайдите снова.",
        "bad": "Не получилось проверить приглашение. Попробуйте ещё раз.",
    }
    line = lines.get(verdict, lines["bad"])
    return f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>{line}</b>"


def counted_inviter_text(guest_html: str, coins: int) -> str:
    amount = cute_amount(coins)
    return (
        "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> "
        f"<b>Приглашение засчитано. Вам пришёл {amount}.</b>\n"
        "<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> "
        f"<b>Первая игра сыграна: {guest_html}.</b>"
    )


def counted_guest_text(coins: int) -> str:
    amount = cute_amount(coins)
    return (
        "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> "
        f"<b>Приглашение засчитано. Вам пришёл {amount}.</b>\n"
        "<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> "
        "<b>Это награда за первую игру. Второй раз она не придёт.</b>"
    )
