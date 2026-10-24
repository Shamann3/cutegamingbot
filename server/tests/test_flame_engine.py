# -*- coding: utf-8 -*-
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flame_copy import is_flame_help_text, is_flame_mine_text, is_restore_command, screen_mine
from flame_engine import (
    gap_starts_new_series,
    live_streak,
    next_paying_day,
    gift_preview,
    help_html,
    need_for,
    profile_line,
    restore_view,
    span_label,
    title_for,
)


def test_status_presets_cover_reward_days():
    from flame_copy import STATUS_DAYS, status_presets

    packs = status_presets()
    assert len(packs) >= 3
    assert STATUS_DAYS[0] == 2
    assert STATUS_DAYS[-1] == 365
    for pack in packs:
        days = [row["from_day"] for row in pack["titles"]]
        names = [row["title"] for row in pack["titles"]]
        assert days == list(STATUS_DAYS)
        assert len(names) == len(STATUS_DAYS)
        assert len(set(names)) == len(names)
        assert all(name.strip() for name in names)


def test_span_label_is_the_exact_day_count():
    assert span_label(1) == "1 день"
    assert span_label(2) == "2 дня"
    assert span_label(5) == "5 дней"
    assert span_label(21) == "21 день"
    assert span_label(30) == "30 дней"
    assert span_label(40) == "40 дней"
    assert span_label(50) == "50 дней"
    assert span_label(90) == "90 дней"
    assert span_label(100) == "100 дней"
    assert span_label(365) == "365 дней"
    assert span_label(400) == "400 дней"
    assert "месяц" not in span_label(100)
    assert "год" not in span_label(365)


def test_need_grows_from_the_chosen_day():
    steps = [{"from_day": 7, "messages": 250}, {"from_day": 30, "messages": 400}]
    assert need_for(1, 200, steps) == 200
    assert need_for(6, 200, steps) == 200
    assert need_for(7, 200, steps) == 250
    assert need_for(29, 200, steps) == 250
    assert need_for(30, 200, steps) == 400


def test_profile_line_with_status_title():
    assert profile_line(0) == ""
    text = profile_line(2)
    assert "Сейчас" in text
    assert "Рекорд" in text
    assert "Статус" in text
    assert "<b>2 дня</b>" in text
    assert "<blockquote>" in text
    titled = profile_line(10, [{"from_day": 7, "title": "Живой огонь", "emoji_id": "1"}])
    assert "Живой огонь" in titled
    assert "<b>10 дней</b>" in titled
    assert "emoji-id='1'" in titled
    shorter = profile_line(3, None, 10)
    assert "Сейчас · <b>3 дня</b>" in shorter
    assert "Рекорд · <b>10 дней</b>" in shorter
    gone = profile_line(0, None, 10)
    assert "Сейчас · <b>погас</b>" in gone
    assert "Рекорд · <b>10 дней</b>" in gone
    assert "Статус · <b>нет</b>" in gone


def test_passed_days_do_not_pay_again_after_the_flame_dies():
    from flame_engine import reward_is_new

    for day in range(1, 11):
        assert reward_is_new(day, 10) is False
    assert reward_is_new(11, 10) is True
    assert reward_is_new(1, 0) is True
    assert reward_is_new(10, 9) is True


def test_title_picks_highest_unlocked():
    titles = [
        {"from_day": 3, "title": "Искра"},
        {"from_day": 14, "title": "Негасимый"},
    ]
    assert title_for(2, titles) is None
    assert title_for(3, titles)["title"] == "Искра"
    assert title_for(20, titles)["title"] == "Негасимый"


def test_help_lists_rewards_and_warm_hour():
    html = help_html({
        "settings": {"enabled": True, "base_messages": 200, "min_words": 2},
        "steps": [{"from_day": 7, "messages": 250}],
        "rewards": [
            {"day": 3, "kind": "bonus", "amount": 1, "item_name": ""},
            {"day": 7, "kind": "kuty", "amount": 50, "item_name": ""},
            {"day": 7, "kind": "item", "amount": 1, "item_name": "Купон"},
        ],
        "titles": [{"from_day": 7, "title": "Живой огонь"}],
        "warm": {"enabled": True, "min_day": 3, "every": 40, "cap": 3, "hour": 18},
        "gift": {"enabled": True, "mult": 2, "item_count": 2},
    })
    assert "200" in html
    assert "Норма сообщений для продлевания огонька будет расти со временем" in html
    assert "с 7-го — <b>250</b>" not in html
    assert "<b>3 дня</b>" in html
    assert "5325547803936572038" in html
    assert "<b>7 дней</b>" in html
    assert "50 кут" in html
    assert "Купон" in html
    assert "<blockquote><tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> 50 кут\n<b>+ Предметы :</b>\n🎁 Купон</blockquote>" in html
    assert html.index("50 кут") < html.index("Купон")
    assert html.index("Награды за дни") < html.index("Как работает")
    assert "Подарок приходит один раз" in html
    assert "Награды за уже пройденные дни не выдаются" in html
    assert "длиннее, чем уже был" in html
    assert "приносить пользу" in html
    assert "Тёплый час" in html
    assert "какой-то подарок от проекта" in html
    assert "18:00" in html
    assert "5354952069168009105" in html
    assert "Stremlenue" in html
    assert "мой огонёк" in html
    assert "Что делать сегодня" in html
    assert "🎁" in html
    assert "официальных группах" in html
    assert "Бонус +" not in html
    assert "использовать" not in html
    assert "продлите огонёк" in html.lower()
    assert "закрыть день" not in html.lower()
    assert "вернуть огонёк можно ещё" not in html.lower()
    assert "с 7-го" not in html
    assert html.count("<blockquote>") == 2
    assert not html.startswith("<blockquote>")
    assert "</blockquote>" not in html.split("Как работает", 1)[1].split("Тёплый час", 1)[0]


def test_help_day_cards_keep_each_item_emoji():
    html = help_html({
        "settings": {"enabled": True, "base_messages": 100, "min_words": 2},
        "steps": [],
        "rewards": [
            {"day": 2, "kind": "bonus", "amount": 1, "item_name": ""},
            {"day": 2, "kind": "bonus_x2", "amount": 1, "item_name": ""},
            {"day": 2, "kind": "kuty", "amount": 10, "item_name": ""},
            {"day": 2, "kind": "item", "amount": 1, "item_name": "Саженец", "emoji": "🌱"},
            {"day": 2, "kind": "item", "amount": 1, "item_name": "Табак", "emoji": "🍂"},
            {"day": 5, "kind": "item", "amount": 2, "item_name": "Ключ", "emoji": "🔑"},
        ],
        "titles": [],
        "warm": {"enabled": False},
        "gift": {"enabled": False},
    })
    assert html.count("<blockquote>") == 2
    day2 = html.split("<b>5 дней</b>")[0]
    day5 = html.split("<b>5 дней</b>", 1)[1]
    assert "<b>2 дня</b>" in day2
    assert "5325547803936572038" in day2
    quote2 = day2.split("<blockquote>", 1)[1].split("</blockquote>", 1)[0]
    gift = "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>"
    money = "<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji>"
    assert quote2 == "\n".join((
        f"{gift} Бесплатный бонус",
        f"{gift} Бонус ×2",
        f"{money} 10 кут",
        "<b>+ Предметы :</b>",
        "🌱 Саженец",
        "🍂 Табак",
    ))
    assert "5 дней" not in day2
    assert "<blockquote><b>+ Предметы :</b>\n🔑 Ключ ×2</blockquote>" in day5
    assert "Бонус" not in day5
    assert "Куты —" not in html


def test_help_offers_restore_from_the_one_text_file():
    html = help_html({
        "settings": {
            "enabled": True,
            "base_messages": 200,
            "min_words": 2,
            "restore_enabled": True,
            "restore_days": 3,
            "restore_kuty": 500,
            "restore_item": "Купон",
            "restore_item_count": 2,
        },
        "steps": [],
        "rewards": [],
        "titles": [],
        "warm": {"enabled": False},
        "gift": {"enabled": False},
    })
    assert "вернуть огонёк" in html
    assert "<b>500</b> кут" in html
    assert "Купон ×2" in html
    assert "Новая серия" in html or "новой серии" in html
    assert "вернуть огонёк можно ещё" in html.lower()
    assert "<b>3</b> дня" in html
    assert "закрыть день" not in html.lower()


def test_restore_window_and_blocks():
    today = date(2026, 10, 25)
    priced = {
        "restore_enabled": True,
        "restore_days": 3,
        "restore_kuty": 500,
        "restore_item": "",
        "restore_item_count": 1,
    }
    ready = restore_view(0, 10, date(2026, 10, 23), priced, today)
    assert ready["code"] == "ready"
    assert ready["streak"] == 10
    assert ready["days_left"] == 1
    assert ready["label"] == "10 дней"
    assert restore_view(0, 10, date(2026, 10, 22), priced, today)["code"] == "late"
    assert restore_view(4, 10, date(2026, 10, 24), priced, today)["code"] == "alive"
    assert restore_view(0, 0, None, priced, today)["code"] == "none"
    bare = {**priced, "restore_kuty": 0}
    assert restore_view(0, 10, date(2026, 10, 24), bare, today)["code"] == "off"
    switched = {**priced, "restore_enabled": False}
    assert restore_view(0, 10, date(2026, 10, 24), switched, today)["code"] == "off"
    assert gap_starts_new_series(date(2026, 10, 20), today) is True
    assert gap_starts_new_series(date(2026, 10, 24), today) is False
    assert is_restore_command("Вернуть Огонёк") is True
    assert is_restore_command("просто огонёк") is False


def test_flame_help_phrases():
    assert is_flame_help_text("хелп огонёк") is True
    assert is_flame_help_text("хелп огонек") is True
    assert is_flame_help_text("что такое огонёк") is True
    assert is_flame_help_text("как пользоваться огоньком") is True
    assert is_flame_help_text("как использовать огонек") is True
    assert is_flame_help_text("огонёк хелп") is True
    assert is_flame_help_text("help flame") is True
    assert is_flame_help_text("зачем нужен огонёк") is True
    assert is_flame_help_text("вернуть огонёк") is False
    assert is_flame_help_text("просто огонёк") is False
    assert is_flame_help_text("хелп магазин") is False
    assert is_flame_help_text("огонёк") is False


def test_mine_phrase_is_exact_and_the_card_is_short():
    assert is_flame_mine_text("мой огонёк") is True
    assert is_flame_mine_text("Мой Огонек") is True
    assert is_flame_mine_text("  мой   огонёк! ") is True
    assert is_flame_mine_text("огонёк мой") is True
    assert is_flame_mine_text("мойогонёк") is True
    assert is_flame_mine_text("мой огонёк пожалуйста") is False
    assert is_flame_mine_text("хелп огонёк") is False
    assert is_flame_mine_text("вернуть огонёк") is False
    assert is_flame_mine_text("огонёк") is False
    assert is_flame_help_text("мой огонёк") is False
    card = screen_mine(
        now="3 дня",
        record="10 дней",
        status="нет",
        have=40,
        need=100,
        words=2,
        next_day="11 дней",
        replay=True,
    )
    assert "Продлите огонёк" in card
    assert "60 сообщений" in card
    assert "<b>40</b> из <b>100</b>" in card
    assert "Сейчас · <b>3 дня</b>" in card
    assert "Рекорд · <b>10 дней</b>" in card
    assert "Статус" not in card
    assert "11 дней" in card
    assert "без подарка" in card
    assert "хотя бы <b>2</b> слов" in card
    assert "станет длиннее" in card
    assert "Бонус +" not in card
    fresh = screen_mine(
        now="погас",
        record="нет",
        status="нет",
        have=0,
        need=100,
        words=2,
        next_day="2 дня",
        fresh=True,
    )
    assert "Зажгите огонёк" in fresh
    assert "огонёк загорится" in fresh
    assert "100 сообщений" in fresh
    assert "официальных группах" in fresh
    assert "Первый подарок" in fresh
    assert "Рекорд" not in fresh
    assert "Статус" not in fresh
    started = screen_mine(
        now="погас",
        record="10 дней",
        have=12,
        need=100,
        words=2,
        next_day="11 дней",
        replay=True,
    )
    assert "88 сообщений" in started
    assert "Напишите" not in started
    assert "<b>12</b> из <b>100</b>" in started
    assert "<blockquote>" in started
    from flame_copy import screen_mine_how, screen_mine_rewards
    rules = screen_mine_how(base=100, words=2, rises=True)
    assert "Как писать" in rules
    assert "Что делать" in rules
    assert "Норма сообщений для продлевания огонька будет расти со временем" in rules
    rewards = screen_mine_rewards("<b>2 дня</b>", replay=True)
    assert "Что я получу" in rewards
    assert "один раз" in rewards
    assert "старые дни без подарка" in rewards
    assert "Пишите сегодня" in rewards


def test_next_gift_starts_after_the_record():
    rewards = [{"day": 2}, {"day": 10}, {"day": 11}]
    assert next_paying_day(rewards, 10) == 11
    assert next_paying_day(rewards, 0) == 2
    assert next_paying_day(rewards, 11) is None
    today = date(2026, 10, 24)
    streak, best, kept = live_streak(10, 10, date(2026, 10, 22), today)
    assert (streak, best, kept) == (0, 10, False)
    streak, best, kept = live_streak(3, 10, date(2026, 10, 23), today)
    assert (streak, best, kept) == (3, 10, False)
    streak, best, kept = live_streak(3, 3, today, today)
    assert kept is True and streak == 3


def test_gift_preview_shows_average():
    preview = gift_preview(
        [
            {"kind": "item", "item_name": "Купон", "weight": 1},
            {"kind": "kuty", "amount_min": 10, "amount_max": 10, "weight": 1},
        ],
        mult=2,
        kuty_min=1,
        kuty_max=3,
    )
    assert preview["mult"] == 2
    assert preview["kutyMin"] == 2
    assert preview["kutyMax"] == 6
    assert preview["itemChancePct"] == 50.0
    assert preview["avgPerOpen"] > 0


def test_missed_day_is_before_yesterday():
    today = date(2026, 10, 22)
    yesterday = today - timedelta(days=1)
    assert yesterday == date(2026, 10, 21)
    assert date(2026, 10, 20) < yesterday


def test_reward_cards_name_the_person_and_the_day():
    from flame_copy import screen_reward_hall, screen_reward_private

    private = screen_reward_private("5 дней", "Живой огонь", ["Маленький кейс", "Ключ"])
    assert "Огонёк уже 5 дней" in private
    assert "Маленький кейс" in private
    assert "Ключ" in private
    assert "<blockquote>" in private

    hall = screen_reward_hall("<a href=\"https://t.me/nick\">Аня</a>", "5 дней", ["Маленький кейс", "Ключ <"])
    assert "Аня" in hall
    assert "5 дней" in hall
    assert "Маленький кейс" in hall
    assert "Ключ &lt;" in hall
    assert "хелп огонёк" in hall
    assert "первого дня" in hall
    assert "Бонус +" not in hall


def test_kind_words_name_bonus_and_x2():
    from flame_copy import kind_words
    assert "бонус" in kind_words("bonus", 1).lower()
    assert "×2" in kind_words("bonus_x2", 1) or "x2" in kind_words("bonus_x2", 1).lower()
    assert kind_words("item", 1, "Купон") == "Купон"
    assert "50" in kind_words("kuty", 50)
