# -*- coding: utf-8 -*-
"""Пиар в группах — весь дизайн в одном файле.

Эмодзи: вставь готовый тег Telegram, как есть.
    HUB = "<tg-emoji emoji-id='5192865432255616771'>🌟</tg-emoji>"

Сообщение:
    title — жирный заголовок
    body  — жирные факты (строка или список строк)
    extra — ТОЛЬКО доп. информация → цитата <blockquote><b><i>
    next  — что сделать дальше, жирным

Кнопки — сразу под сообщением, рядами.
    go    — действие (не меняй, если не уверен)
    text  — подпись
    icon  — тот же tg-emoji тег или пусто
    style — default / primary / success / danger
    show  — когда показать: always, live, mine, not_live, reco,
            no_public, no_admin, have_photos, has_username,
            photos, wait_confirm, pending
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Палитра. Меняешь тег здесь — меняется везде, где на него ссылаются.
# ---------------------------------------------------------------------------

HUB = "<tg-emoji emoji-id='5452002597592382164'>📣</tg-emoji>"
OWNER = "<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>"
RECO = "<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>"
RECO_BTN = "<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>"
PHOTO = "<tg-emoji emoji-id='5373098002641805602'>📷</tg-emoji>"
EARN = "<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji>"
GROUPS = "<tg-emoji emoji-id='5192951739623447936'>👥</tg-emoji>"
PUBLIC = "<tg-emoji emoji-id='6021625933759257863'>🔗</tg-emoji>"
ADMIN = "<tg-emoji emoji-id='6037421444789440735'>👤</tg-emoji>"
OK = "<tg-emoji emoji-id='5339112148175959615'>🟢</tg-emoji>"
WAIT = "<tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji>"
NO = "<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>"
GIFT = "<tg-emoji emoji-id='5199552030615558774'>🪙</tg-emoji>"
CONFIRM = "<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji>"
GO = "<tg-emoji emoji-id='5317000922096769303'>➡️</tg-emoji>"
BACK = "<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>"
BACK_HUB = "<tg-emoji emoji-id='5348423147647414077'>↩️</tg-emoji>"
CANT = "<tg-emoji emoji-id='5213205860498549992'>🚫</tg-emoji>"
OPEN = "<tg-emoji emoji-id='5229011542011299168'>🔗</tg-emoji>"
WROTE = "<tg-emoji emoji-id='5350367217349311525'>💬</tg-emoji>"
UNDO = "<tg-emoji emoji-id='5415925890213232864'>🟣</tg-emoji>"
MORE = "<tg-emoji emoji-id='5339564150534200424'>➕</tg-emoji>"
CONT = "<tg-emoji emoji-id='5253767677670862169'>▶️</tg-emoji>"

LINK_HINT = "<code>@группа</code> · <code>t.me/группа</code> · <code>t.me/c/id</code> · id"

PHOTO_STEPS = (
    {
        "what": "Сделайте скриншот списка администраторов группы.",
        "need": "На кадре должен быть <code>@CuteGamingBot</code>.",
    },
    {
        "what": "Сообщение от бота в этой группе.",
        "need": "Нужно видеть, что бот там отвечает на сообщения.",
    },
    {
        "what": "Кто создатель группы.",
        "need": "Показать, кто именно является владельцем группы.",
    },
)

NEED_PHOTO = {
    "video": {
        "title": "Нужно фото, не видео.",
        "extra": "Видео и кружок не принимаем.",
        "next": "Картинка из галереи — сюда.",
    },
    "file": {
        "title": "Нужно фото, не файл.",
        "extra": "Документ без картинки не принимаем.",
        "next": "Картинка из галереи — сюда.",
    },
    "sticker": {
        "title": "Нужно фото из группы.",
        "extra": "Стикер и эмодзи не считаются скрином группы.",
        "next": "Картинка из группы — сюда.",
    },
    "text": {
        "title": "Нужно фото, не текст.",
        "extra": "Текст сюда не подходит — нужен кадр.",
        "next": "Картинка из галереи — сюда.",
    },
    "album": {
        "title": "По одному фото.",
        "extra": "Альбом Telegram считает одним сообщением — кадры склеятся.",
        "next": "Следующий кадр — отдельным сообщением.",
    },
    "dup": {
        "title": "Это фото уже есть.",
        "extra": "Этот кадр уже принят.",
        "next": "Пришлите другой кадр.",
    },
    "": {
        "title": "Нужно именно фото.",
        "extra": "Нужен скрин из самой группы.",
        "next": "Картинка из галереи — сюда.",
    },
}


def btn(go: str, text: str, icon: str = "", style: str = "default", show: str = "always") -> dict:
    row = {"go": go, "text": text, "show": show}
    if icon:
        row["icon"] = icon
    if style and style != "default":
        row["style"] = style
    return row


def screen(*, emoji: str, title: str, body: str = "", extra: str = "", next: str = "", buttons=None, **more) -> dict:
    data = {
        "emoji": emoji,
        "title": title,
        "body": body,
        "extra": extra,
        "next": next,
        "buttons": list(buttons or []),
    }
    data.update(more)
    return data


def repeat(kind: str, go: str, text: str) -> dict:
    return {"repeat": kind, "go": go, "text": text}


# Кнопки. Меняешь текст/иконку здесь — на всех экранах, где кнопка переиспользуется.
B_OWNER = btn("owner", "Я владелец группы", OWNER, "primary")
B_OWNER_PLAIN = btn("owner", "Я владелец группы", OWNER)
B_OWNER_OK = btn("owner", "Я владелец группы", OWNER, "success")
B_MY_GROUP = btn("owner", "Это моя группа", OWNER, "primary")
B_RECO = btn("reco", "Я рекомендую бот в группах", RECO_BTN, "primary")
B_RECO_PLAIN = btn("reco", "Я рекомендую бот в группах", RECO_BTN)
B_RECO_OK = btn("reco", "Я рекомендую бот в группах", RECO_BTN, "success")
B_RECO_KUT = btn("reco", "Я рекомендую Кут в группах", RECO_BTN)
B_EARNINGS = btn("earnings", "Заработки", EARN, "success", "live")
B_MY_GROUPS = btn("groups", "Мои группы", GROUPS, show="mine")
B_MY_GROUPS_OK = btn("groups", "Мои группы", GROUPS, "success")
B_MY_GROUPS_ALWAYS = btn("groups", "Мои группы", GROUPS)
B_ADD = btn("add_bot", "Добавить Кут", GO)
B_CANT = btn("cant", "Не могу добавить", CANT, show="reco")
B_ADDED = btn("check", "Уже добавил", OK, "success")
B_CHECK = btn("check", "Проверить", OK, "success")
B_PUBLIC = btn("public", "Нет @адреса", PUBLIC, show="no_public")
B_ADMIN = btn("admin", "Не админ", ADMIN, show="no_admin")
B_OPEN = btn("open_group", "Открыть группу", OPEN, show="has_username")
B_WROTE = btn("wrote", "Я написал", WROTE, "success")
B_WROTE_PLAIN = btn("wrote", "Я написал", WROTE, show="wait_confirm")
B_UNDO = btn("undo", "Другое фото", UNDO, show="have_photos")
B_CANCEL = btn("cancel", "Снять", NO)
B_CANCEL_PHOTOS = btn("cancel", "Снять", NO, show="photos")
B_CANCEL_CONFIRM = btn("cancel", "Снять", NO, show="wait_confirm")
B_CANCEL_PENDING = btn("cancel", "Снять", NO, show="pending")
B_MORE = btn("more", "Сдать ещё группу", MORE)
B_MORE_OK = btn("more", "Сдать ещё группу", MORE, "success")
B_MORE_LIVE = btn("more", "Сдать ещё группу", MORE, "success", "live")
B_MORE_WAIT = btn("more", "Сдать ещё группу", MORE, show="not_live")
B_CONT = btn("continue_photo", "Продолжить фото", CONT, "success", "photos")
B_YES = btn("yes", "Да", OK, "success")
B_NO = btn("no_confirm", "Нет", NO, "danger")
B_BACK_HUB = btn("back_hub", "Назад, в главное меню", BACK_HUB, "success")
B_BACK_TASKS = btn("back_tasks", "Назад, в главное меню", BACK_HUB, "success")
B_BACK_HOW = btn("back_how", "Назад", BACK)
B_BACK_MINE = btn("back_mine", "Назад", BACK)
B_BACK = btn("back_hub", "Назад", BACK)

HOW_BTNS = [[B_ADD], [B_CANT], [B_ADDED], [B_PUBLIC, B_ADMIN], [B_BACK_HUB]]
HOW_FIX_BTNS = [[B_ADD], [B_CANT], [B_CHECK], [B_BACK_HOW]]
ADD_BTNS = [[B_ADD], [B_CANT], [B_BACK_HUB]]
PHOTO_BTNS = [[B_UNDO], [B_CANCEL], [B_BACK_HUB]]
ROLE_BTNS = [[B_OWNER], [B_RECO_PLAIN], [B_BACK_HUB]]
HUB_ONLY = [[B_BACK_HUB]]
PENDING_BTNS = [[B_MY_GROUPS_OK], [B_BACK_HUB]]
AFTER_CANCEL_BTNS = [[B_MORE_OK], [B_BACK_HUB]]
AFTER_OWNER_BTNS = [[B_MY_GROUPS_OK], [B_BACK_HUB]]
AFTER_RECO_BTNS = [[B_OPEN], [B_WROTE], [B_MY_GROUPS_ALWAYS], [B_CANCEL], [B_BACK_HUB]]


SCREENS: dict[str, dict] = {
    # 1. Хаб
    "hub": screen(
        emoji=HUB,
        title="Рекомендация бота в группах",
        body="Заработок - до 35% комиссии с игр новых людей.",
        extra="Длительность заработка - 14 дней · с той группы, в которую вы добавите нашего бота",
        next="Нажмите, кто вы. Дальше бот покажет что нужно делать далее",
        buttons=[[B_OWNER], [B_RECO], [B_EARNINGS], [B_MY_GROUPS], [B_BACK_TASKS]],
    ),
    # 2. Кто вы
    "choose": screen(
        emoji=RECO,
        title="Кто вы?",
        body="Владелец — корона в списке админов. Если привели бота в чужой чат — вторая кнопка.",
        next="Нажмите одну кнопку. Потом бот скажет, что прислать.",
        buttons=[[B_OWNER_PLAIN], [B_RECO_PLAIN], [B_BACK_HUB]],
    ),
    # 3. Владелец — инструкция
    "how_owner": screen(
        emoji=OWNER,
        title="Ваша группа",
        body="Добавьте Кут в список администраторов в свою публичную группу.",
        extra="Подойдёт {link_hint}{seen}",
        next="Нажмите «Добавить Кут», выберите чат. Потом пришлите сюда ссылку.",
        buttons=HOW_BTNS,
    ),
    # 4. Рекомендация — инструкция
    "how_reco": screen(
        emoji=RECO,
        title="Чужой чат",
        body="Попросите создателя добавить @CuteGamingBot в админы.",
        extra="Подойдёт {link_hint}{seen}",
        next="Когда Кут в админах — пришлите сюда ссылку.",
        buttons=HOW_BTNS,
    ),
    "how_public": screen(
        emoji=PUBLIC,
        title="Нужен @адрес",
        body="Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.",
        extra="Без открытого @адреса группу сдать нельзя.",
        next="Сделайте группу публичной. Потом пришлите сюда ссылку.",
        buttons=HOW_FIX_BTNS,
    ),
    "how_admin": screen(
        emoji=ADMIN,
        title="Кут должен быть админом",
        body="<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.",
        extra="Без админки Кут не видит чат и не может принять заявку.",
        next="Нажмите «Проверить» или пришлите ссылку сюда.",
        buttons=HOW_FIX_BTNS,
    ),
    "how_admin_reco": screen(
        emoji=ADMIN,
        title="Кут должен быть админом",
        body="Попросите создателя: <b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.",
        extra="Без админки Кут не видит чат и не может принять заявку.",
        next="Когда Кут в админах — пришлите сюда ссылку.",
        buttons=HOW_FIX_BTNS,
    ),
    "need_public": screen(
        emoji=NO,
        title="У «{name}» нет @адреса",
        body="Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.",
        extra="Закрытую группу сдать нельзя.",
        next="Сделайте группу публичной. Потом пришлите сюда ссылку.",
        buttons=HOW_FIX_BTNS,
    ),
    "need_admin": screen(
        emoji=NO,
        title="В «{name}» Кут не админ",
        body="<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.",
        extra="Без админки заявку не примем.",
        next="Нажмите «Проверить» или пришлите ссылку сюда.",
        buttons=HOW_FIX_BTNS,
    ),
    "need_admin_reco": screen(
        emoji=NO,
        title="В «{name}» Кут не админ",
        body="Попросите создателя дать ему админку.",
        extra="Без админки заявку не примем.",
        next="Когда Кут в админах — пришлите сюда ссылку.",
        buttons=HOW_FIX_BTNS,
    ),
    "bot_joined": screen(
        emoji=OK,
        title="Кут зашёл в «{name}»",
        extra="Дальше нужен только один шаг: кто вы.",
        next="Нажмите, кто вы: владелец или рекомендуете. Дальше бот скажет следующий шаг.",
        buttons=ROLE_BTNS,
    ),
    "bot_joined_intent": screen(
        emoji=OK,
        title="Кут зашёл в «{name}»",
        extra="Если он ещё не админ — сначала дайте админку.",
        next="Если он админ — нажмите «Проверить» или пришлите ссылку сюда.",
        buttons=HOW_FIX_BTNS,
    ),
    "need_link": screen(
        emoji=WAIT,
        title="Нужна ссылка на группу",
        body="В группе : сообщение → Копировать ссылку — вставьте сюда текстом",
        extra="Подойдёт {link_hint}",
        next="Пришлите сюда ссылку текстом.",
        buttons=HOW_BTNS,
    ),
    "forward_no_group": screen(
        emoji=NO,
        title="Пересылка не подходит",
        body="Не пересылайте сообщение. Пришлите ссылку текстом.",
        extra="Подойдёт {link_hint}",
        next="Пришлите ссылку сюда текстом.",
        buttons=HOW_BTNS,
    ),
    "link_invite": screen(
        emoji=NO,
        title="Это закрытая ссылка",
        body="Нужна публичная группа.",
        extra="Пригласительная ссылка с + или joinchat не подходит.",
        next="Сделайте @адрес и пришлите обычную ссылку.",
        buttons=HOW_FIX_BTNS,
    ),
    "group_not_found": screen(
        emoji=NO,
        title="Такую группу не вижу",
        extra="Кут должен уже быть в чате, иначе группу не найдёт.",
        next="Проверьте ссылку. Кут должен быть в чате. Потом пришлите ссылку снова.",
        buttons=ADD_BTNS,
    ),
    "bot_not_there": screen(
        emoji=NO,
        title="Кут не в «{name}»",
        extra="Сначала добавьте бота, потом снова ссылку.",
        next="Нажмите «Добавить Кут», выберите этот чат. Потом пришлите ссылку снова.",
        buttons=ADD_BTNS,
    ),
    "bot_not_there_reco": screen(
        emoji=NO,
        title="Кут не в «{name}»",
        body="Попросите создателя добавить @CuteGamingBot в админы.",
        extra="Пока Кут не в чате — ссылку проверять рано.",
        next="Когда Кут будет в чате — пришлите сюда ссылку снова.",
        buttons=ADD_BTNS,
    ),
    "cant_add": screen(
        emoji=RECO,
        title="Чужая группа",
        body="Напишите создателю: добавь @CuteGamingBot в админы.",
        extra="Подойдёт {link_hint}",
        next="Когда Кут будет в чате — пришлите сюда ссылку.",
        buttons=[[B_ADD], [B_BACK_HOW]],
    ),
    "not_in_group": screen(
        emoji=NO,
        title="Вас нет в «{name}»",
        extra="Сдавать можно только чат, в котором вы сами состоите.",
        next="Сначала вступите в группу. Потом вернитесь сюда и пришлите ссылку.",
        buttons=ADD_BTNS,
    ),
    "not_a_group": screen(
        emoji=NO,
        title="Это не группа",
        extra="Канал, бот и личка не подходят.",
        next="Нужен чат, не канал и не человек. Пришлите ссылку на группу.",
        buttons=ADD_BTNS,
    ),
    "pick_group": screen(
        emoji=GROUPS,
        title="Какую группу сдаём?",
        extra="Список — чаты, где Кут уже есть. Одна кнопка — одна группа.",
        next="Нажмите на нужную группу. Если список не тот — «Назад», в главное меню.",
        buttons=[repeat("groups", "pick_group", "{title}"), [B_BACK_HUB]],
    ),
    "pick_role": screen(
        emoji=RECO,
        title="«{name}»",
        body="Кто сдаёт эту группу?",
        extra="Создатель потом нажмёт Да в группе, если вы не владелец.",
        next="Своя — первая кнопка. Привели Кут — вторая.",
        buttons=[[B_MY_GROUP], [B_RECO_KUT], [B_BACK_HUB]],
    ),
    "owner_bridge": screen(
        emoji=OWNER,
        title="«{name}»",
        body="Вы создатель. Дальше 3 фото — и заявка на проверку.",
        extra="Если друг просил добавить Кут — не забирайте заявку: пусть он пришлёт ссылку в бота.",
        next="Пришлите первое фото сюда.",
        buttons=PHOTO_BTNS,
    ),
    "reco_bridge": screen(
        emoji=RECO,
        title="«{name}»",
        body="Вы не создатель. Чтобы доля шла вам, создатель нажмёт Да в группе.",
        extra="Да нажимает только человек с короной в админах.",
        next="Пришлите первое фото сюда.",
        buttons=PHOTO_BTNS,
    ),
    "not_owner_switch": screen(
        emoji=NO,
        title="Вы не владелец «{name}»",
        extra="Чужой чат сдаётся через рекомендацию, не через корону.",
        next="Нажмите «Я рекомендую бот в группах».",
        buttons=[[B_RECO_OK], [B_BACK_HUB]],
    ),
    "are_owner_switch": screen(
        emoji=OWNER,
        title="«{name}» — ваша группа",
        extra="Корона в админах — вы создатель. Сдавайте этим путём.",
        next="Нажмите «Я владелец группы».",
        buttons=[[B_OWNER_PLAIN], [B_BACK_HUB]],
    ),
    "wait_photo": screen(
        emoji=PHOTO,
        title="{step} из {total}",
        body="{body}",
        extra="{need}",
        next="{tail}",
        buttons=PHOTO_BTNS,
        next_by={
            "0": "Пришлите фото сюда",
            "1": "Пришлите следующее фото сюда, одним кадром.",
            "2": "Пришлите последнее фото сюда - и заявка уйдёт дальше.",
        },
    ),
    "need_photo": screen(
        emoji=NO,
        title="{title}",
        extra="{extra}",
        next="{tail}",
        buttons=PHOTO_BTNS,
    ),
    "photos_expired": screen(
        emoji=NO,
        title="24 часа вышли",
        extra="Три фото нужно успеть за сутки с первого кадра.",
        next="Нажмите «Сдать ещё группу» или «Назад» — и сдайте три фото заново.",
        buttons=AFTER_CANCEL_BTNS,
    ),
    "after_proofs_owner": screen(
        emoji=OK,
        title="Доказательства приняты",
        body="Новым людям проект даст куты — играть ими можно только у вас, в этой группе.",
        extra="Теперь ваша группа уйдёт на проверку. Ответ придёт сюда.",
        next="Нажмите «Мои группы», чтобы видеть статус. «Назад» — в меню пиара.",
        buttons=AFTER_OWNER_BTNS,
    ),
    "after_proofs_reco": screen(
        emoji=OK,
        title="Доказательства приняты",
        body="14 дней вам будет капать доля с игр новых людей в этой группе.",
        extra="Теперь эта группа уйдёт на проверку. Ответ придёт сюда.",
        next="Нажмите «Мои группы», чтобы видеть статус. «Назад» — в меню пиара.",
        buttons=AFTER_OWNER_BTNS,
    ),
    "after_photos_reco": screen(
        emoji=WAIT,
        title="Напишите в группе",
        body="Откройте «{name}» и отправьте слово <code>подтверждение</code>.",
        extra="Да нажимает только создатель (корона). 24 часа.",
        next="Нажмите «Открыть группу», напишите слово, дождитесь Да. Потом можно нажать «Я написал».",
        buttons=AFTER_RECO_BTNS,
    ),
    "wrote_confirm": screen(
        emoji=WAIT,
        title="Ждём создателя",
        body="Под сообщением в группе он должен нажать Да.",
        extra="Без Да доля вам не пойдёт.",
        next="Если не нажал — откройте группу и напишите «подтверждение» ещё раз.",
        buttons=AFTER_RECO_BTNS,
    ),
    "earnings": screen(
        emoji=EARN,
        title="Заработки",
        body="Всего вам пришло: {total}\nСегодня: {today}",
        extra="{barnum}",
        next="Нажмите группу — откроется карточка. «Сдать ещё группу» — новое меню.",
        buttons=[repeat("claims", "open_claim", "{label}"), [B_MORE_LIVE], [B_MORE_WAIT], [B_BACK_HUB]],
        extra_by={
            "empty": "Пока тихо. Сдайте группу — и здесь появятся цифры, которые захочется открывать.",
            "live_paid": "Это уже ваши цифры. Откройте группу — будет видно, откуда капает.",
            "live": "Группа уже в работе. Первые куты приходят, когда новые люди начинают играть.",
            "today": "Сегодня уже есть движение. Откройте группу — там подробнее.",
            "pending": "Вы уже сделали свою часть. Пока смотрим заявку — можно подождать здесь.",
        },
        next_empty="Нажмите «Сдать ещё группу» и выберите, кто вы.",
    ),
    "mine": screen(
        emoji=GROUPS,
        title="Мои группы",
        body="Всего вам пришло: {total}\nСегодня: {today}",
        extra="{barnum}",
        next="Нажмите группу — откроется карточка. «Сдать ещё группу» — новое меню.",
        buttons=[repeat("claims", "open_claim", "{label}"), [B_MORE_LIVE], [B_MORE_WAIT], [B_BACK_HUB]],
        extra_by={
            "empty": "Пока тихо. Сдайте группу — и здесь появятся цифры, которые захочется открывать.",
            "live_paid": "Это уже ваши цифры. Откройте группу — будет видно, откуда капает.",
            "live": "Группа уже в работе. Первые куты приходят, когда новые люди начинают играть.",
            "today": "Сегодня уже есть движение. Откройте группу — там подробнее.",
            "pending": "Вы уже сделали свою часть. Пока смотрим заявку — можно подождать здесь.",
        },
        next_empty="Нажмите «Сдать ещё группу» и выберите, кто вы.",
    ),
    "card": screen(
        emoji=WAIT,
        title="«{name}»",
        body="{facts}",
        extra="{hint}",
        next="{action}",
        buttons=[
            [B_OPEN],
            [B_CONT],
            [B_WROTE_PLAIN],
            [B_CANCEL_PHOTOS],
            [B_CANCEL_CONFIRM],
            [B_CANCEL_PENDING],
            [B_BACK_MINE],
        ],
        emoji_by={
            "live_owner": OWNER,
            "live_reco": EARN,
            "photos": PHOTO,
            "error": NO,
            "wait": WAIT,
        },
        extra_by={
            "pause": "Начисления стоят, пока это не исправить.",
            "photos": "Три кадра нужны, чтобы заявка ушла дальше.",
            "wait_confirm": "Да нажимает только создатель с короной.",
            "pending": "Решение придёт в этот чат.",
            "live": "Пока Кут в админах и группа открытая — цифры обновляются сами.",
            "ended": "Новые куты с этой группы больше не капают.",
            "rejected": "{reason}",
            "burned": "Если Кут вернуть в админы — это уже новая заявка.",
        },
        next_by={
            "pause": "{hint} «Назад» — к списку групп.",
            "photos": "Нажмите «Продолжить фото» и пришлите следующий кадр сюда.",
            "wait_confirm": "Нажмите «Открыть группу», напишите «подтверждение», дождитесь Да.",
            "pending": "Ждите. «Назад» — к списку.",
            "live": "Ничего нажимать не нужно. «Назад» — к списку групп.",
            "ended": "Срок вышел. «Назад» — к списку. Новую группу сдайте с главного меню.",
            "rejected": "«Назад» — к списку.",
            "burned": "Кут убрали из группы. «Назад» — к списку.",
            "default": "«Назад» — к списку групп.",
        },
        facts_owner=["{status}", "Баланс группы: {balance}", "Подарков новым: {gifts}", "Новых людей: {newcomers}"],
        facts_reco=["{status}", "Вам уже пришло: {paid}", "Сегодня: {today}", "Осталось дней: {days}", "Новых людей: {newcomers}"],
    ),
    "cancelled": screen(
        emoji=WAIT,
        title="Заявку сняли",
        extra="Эту группу можно сдать снова, если слот свободен.",
        next="Нажмите «Сдать ещё группу» — и выберите путь заново.",
        buttons=AFTER_CANCEL_BTNS,
    ),
    "confirm": screen(
        emoji=CONFIRM,
        title="{who} добавил Кут сюда. Если это так — нажмите Да. Тогда заработок пойдёт ему.",
        extra="Нет — если вы его не просили. Да нажимает только создатель.",
        buttons=[[B_YES, B_NO]],
    ),
    "confirm_yes": screen(
        emoji=OK,
        title="Подтверждено. Заявка на проверке.",
        extra="Решение придёт пригласившему в личку.",
        next="Ничего больше нажимать не нужно.",
    ),
    "confirm_no_first": screen(
        emoji=NO,
        title="Создатель не подтвердил",
        extra="Остался один шанс в течение 24 часов.",
        next="Откройте группу и напишите <code>подтверждение</code> ещё раз.",
        buttons=AFTER_RECO_BTNS,
    ),
    "confirm_no_second": screen(
        emoji=NO,
        title="Снова нет",
        extra="После двух отказов группу нельзя сдавать 31 день.",
        next="Эту группу нельзя 31 день. Нажмите «Назад» и возьмите другую.",
        buttons=HUB_ONLY,
    ),
    "not_your_claim": screen(
        emoji=NO,
        title="Это не ваша заявка.",
        extra="Подтверждение и снятие доступны только тому, кто сдавал группу.",
        next="Нажмите «Назад» — откроется меню пиара.",
        buttons=HUB_ONLY,
    ),
    "not_creator": screen(
        emoji=NO,
        title="Подтверждает только создатель",
        extra="Корона в списке админов — вот кто может нажать Да.",
        next="Да должен нажать человек с короной в списке админов.",
    ),
    "confirm_expired": screen(
        emoji=WAIT,
        title="Это подтверждение уже не действует.",
        extra="Кнопки Да/Нет живут 24 часа с момента слова «подтверждение».",
        next="Напишите в группе «подтверждение» снова.",
    ),
    "wrong_group": screen(
        emoji=NO,
        title="Не та группа.",
        extra="Слово «подтверждение» срабатывает только в сданном чате.",
        next="Откройте ту группу, куда вы добавляли Кут, и напишите «подтверждение» там.",
    ),
    "need_photos_first": screen(
        emoji=PHOTO,
        title="Сначала 3 фото в боте",
        extra="Подтверждение в группе открывается только после трёх кадров.",
        next="Пришлите их сюда, в этот чат, по одному кадру.",
        buttons=PHOTO_BTNS,
    ),
    "accepted": screen(
        emoji=OK,
        title="Группу приняли.",
        body="{days} дней вам капает доля с игр новых.",
        extra="Капает только с людей, которых Кут ещё не знал.",
        next="Нажмите «Заработки» или «Мои группы», когда захотите цифры.",
        buttons=AFTER_OWNER_BTNS,
    ),
    "accepted_owner": screen(
        emoji=OK,
        title="Группу приняли.",
        body="{days} дней · новые смогут играть у вас на подарочные куты.",
        extra="Подарки работают только в играх этой группы, одному.",
        next="Нажмите «Мои группы», когда захотите цифры.",
        buttons=AFTER_OWNER_BTNS,
    ),
    "digest": screen(
        emoji=EARN,
        title="Сегодня с «{name}»: {newcomers} новых людей · вам {paid}.",
        body="Осталось {days} дн.",
        extra="{note}",
        next="Откройте «Заработки», чтобы видеть цифры по группам.",
        extra_by={
            "paid": "Это уже на вашем балансе.",
            "empty": "Как появятся игры новых — цифра вырастет.",
        },
    ),
    "gift": screen(
        emoji=GIFT,
        title="{who}, На ваш баланс было выдано {amount} кут в подарок, для того чтобы научится играть в @CuteGamingBot",
        extra="В случае каких либо непоняток, напишите \"хелп\"",
    ),
    "gift_locked": screen(
        emoji=NO,
        title="Подарочные куты можно поставить только в играх этой группы, одному.",
        extra="Снять или перевести нельзя — ими учатся играть у вас.",
    ),
    "term_end": screen(
        emoji=WAIT,
        title="Срок по этой группе закончился. Новые куты с неё больше не капают.",
        extra="Уже начисленные куты остаются у вас.",
        next="Откройте «Мои группы», чтобы увидеть статус. Новую можно сдать с главного меню.",
        buttons=PENDING_BTNS,
    ),
    "kicked": screen(
        emoji=NO,
        title="Кут убрали из группы. Начисления стоп.",
        extra="Заявка по этой группе сгорает, если бота выгнали.",
        next="Верните Кут в админы, если хотите продолжить. Статус — в «Мои группы».",
    ),
    "rejected": screen(
        emoji=NO,
        title="Не приняли.",
        body="{reason}",
        extra="Эту заявку уже не поправить.",
        next="Нажмите «Назад» — в меню пиара.",
        buttons=HUB_ONLY,
    ),
    "rejected_fix": screen(
        emoji=NO,
        title="Не приняли.",
        body="{reason}",
        extra="Есть 48 часов, чтобы исправить и сдать снова.",
        next="Исправьте и сдайте снова через «Сдать ещё группу».",
        buttons=AFTER_CANCEL_BTNS,
    ),
    "two_pending": screen(
        emoji=NO,
        title="Уже 2 заявки",
        extra="Одновременно смотрим не больше двух заявок на человека.",
        next="Нажмите «Мои группы»: дождитесь проверки или снимите одну.",
        buttons=PENDING_BTNS,
    ),
    "two_live": screen(
        emoji=NO,
        title="Уже 2 живые группы",
        extra="Живых групп на человеке не больше двух.",
        next="Нажмите «Заработки». Новую можно сдать, когда освободится слот.",
        buttons=PENDING_BTNS,
    ),
    "banned_31": screen(
        emoji=NO,
        title="Эту группу нельзя 31 день",
        extra="После отказа создателя или срыва слот на чат закрывается на месяц.",
        next="Нажмите «Назад» и возьмите другую — или подождите.",
        buttons=HUB_ONLY,
    ),
    "freeze_admin": screen(
        emoji=WAIT,
        title="Пауза: Кут нужна админка",
        extra="Начисления стоят, пока бот не администратор.",
        next="Верните Кут в администраторы группы. Потом снова начнёт капать.",
    ),
    "freeze_public": screen(
        emoji=WAIT,
        title="Пауза: группа стала закрытой",
        extra="Начисления стоят, пока нет открытого @адреса.",
        next="Сделайте группу открытой с @адресом. Потом снова начнёт капать.",
    ),
    "group_busy": screen(
        emoji=NO,
        title="Эту группу уже сдают",
        extra="Одна группа — один человек. Первый, кто сдал доказательства, держит слот.",
        next="Нажмите «Назад» и возьмите другую.",
        buttons=HUB_ONLY,
    ),
    "group_busy_owner": screen(
        emoji=NO,
        title="Эту группу уже сдаёт создатель",
        extra="Одна группа — один человек. Первый, кто сдал доказательства, держит слот.",
        next="Нажмите «Назад» и возьмите другую.",
        buttons=HUB_ONLY,
    ),
    "confirm_timeout": screen(
        emoji=NO,
        title="Создатель не нажал Да за 24 часа",
        extra="Без Да рекомендация не идёт на проверку.",
        next="Нажмите «Сдать ещё группу» — можно начать снова.",
        buttons=AFTER_CANCEL_BTNS,
    ),
    "owner_no_confirm": screen(
        emoji=OWNER,
        title="Вам подтверждение не нужно",
        extra="Создатель не пишет «подтверждение» сам себе.",
        next="Заявка создателя идёт на проверку без Да. Смотрите «Мои группы».",
        buttons=PENDING_BTNS,
    ),
    "resume": screen(
        emoji=WAIT,
        title="«{name}»",
        body="{status}",
        extra="Заявка не потерялась — продолжаем с того же шага.",
        next="Нажмите кнопку ниже — бот продолжит с этого шага.",
        buttons=[
            [B_CANCEL_PHOTOS],
            [B_WROTE_PLAIN],
            [B_CANCEL_CONFIRM],
            [B_MY_GROUPS_ALWAYS],
            [B_BACK_HUB],
        ],
        emoji_by={
            "live_owner": OWNER,
            "live_reco": EARN,
            "photos": PHOTO,
            "error": NO,
            "wait": WAIT,
        },
    ),
}


PALETTE = {
    "hub": HUB,
    "owner": OWNER,
    "reco": RECO,
    "photo": PHOTO,
    "earn": EARN,
    "groups": GROUPS,
    "public": PUBLIC,
    "admin": ADMIN,
    "ok": OK,
    "wait": WAIT,
    "no": NO,
    "gift": GIFT,
    "confirm": CONFIRM,
}

_EMOJI_RE = re.compile(r"<tg-emoji emoji-id=['\"](\d+)['\"]>(.*?)</tg-emoji>", re.I | re.S)


def parse_emoji(tag: str) -> tuple[str, str]:
    raw = str(tag or "").strip()
    match = _EMOJI_RE.search(raw)
    if match:
        return match.group(1), match.group(2)
    if raw.isdigit():
        return raw, "🔹"
    return "", ""


def emoji_id(tag: str) -> str:
    return parse_emoji(tag)[0]


def emoji_html(tag: str) -> str:
    raw = str(tag or "").strip()
    if "<tg-emoji" in raw:
        return raw
    eid, face = parse_emoji(raw)
    if not eid:
        return ""
    return f"<tg-emoji emoji-id='{eid}'>{face}</tg-emoji>"


EMOJI_HUB = emoji_id(HUB)
EMOJI_OWNER = emoji_id(OWNER)
EMOJI_RECO = emoji_id(RECO)
EMOJI_PHOTO = emoji_id(PHOTO)
EMOJI_EARN = emoji_id(EARN)
EMOJI_GROUPS = emoji_id(GROUPS)
EMOJI_PUBLIC = emoji_id(PUBLIC)
EMOJI_ADMIN = emoji_id(ADMIN)
STATUS_EMOJI_OK = emoji_id(OK)
STATUS_EMOJI_WAIT = emoji_id(WAIT)
STATUS_EMOJI_NO = emoji_id(NO)
GIFT_EMOJI = emoji_id(GIFT)
CONFIRM_EMOJI = emoji_id(CONFIRM)

ICON_GO = emoji_id(GO)
ICON_CHECK = emoji_id(OK)
ICON_NO = emoji_id(NO)
ICON_BACK = emoji_id(BACK)
ICON_BACK_HUB = emoji_id(BACK_HUB)
ICON_OWNER = emoji_id(OWNER)
ICON_RECO = emoji_id(RECO_BTN)
ICON_EARN = emoji_id(EARN)
ICON_GROUPS = emoji_id(GROUPS)
ICON_CANT = emoji_id(CANT)
ICON_PUBLIC = emoji_id(PUBLIC)
ICON_ADMIN = emoji_id(ADMIN)
ICON_OPEN = emoji_id(OPEN)
ICON_WROTE = emoji_id(WROTE)
ICON_UNDO = emoji_id(UNDO)
ICON_MORE = emoji_id(MORE)
ICON_CONT = emoji_id(CONT)
ICON_OK = ICON_CHECK
