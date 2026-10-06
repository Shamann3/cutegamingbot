from bot.admins.group_roster import (
    find_post,
    granted_lines,
    group_rights_rows,
    group_roster_rows,
    highest_vacancy,
    pick_post,
    render_group_rights,
    render_group_roster,
    roster_shape,
    split_icon_label,
    staff_return_row,
    stored_owner_name,
)


def test_group_roster_lists_this_group_not_project_staff():
    text = render_group_roster("CuteGamingChat", [
        {
            "title": "Администратор ГЧ",
            "rank": 4,
            "people": [{"html": "Аня", "status": "🟢", "hint": ""}],
        },
        {"title": "Хелпер", "rank": 1, "people": []},
    ], stamp="12:00:00")
    assert "АДМИНИСТРАТОРЫ ГРУППЫ" in text
    assert "CuteGamingChat" in text
    assert "Администратор ГЧ" in text
    assert "вакантно" in text
    assert "ПЕРСОНАЛ ПРОЕКТА" not in text
    assert "12:00:00" in text


def test_group_rights_follow_the_position_switches():
    quiet = granted_lines(3, ["punish_mute"])
    assert quiet == [("Мут", "только этот чат")]
    assert granted_lines(3, ["punish_ban"]) == [("Бан в чате", "только этот чат")]
    full = granted_lines(2, ["banfull", "muteall"])
    assert ("Банфулл", "весь проект") in full
    assert ("Муталл", "все официальные группы") in full
    creator = [name for name, _place in granted_lines(5, [])]
    assert "Мут" in creator
    assert "Банфулл" not in creator
    card = render_group_rights("CuteGamingChat", [
        {"title": "Хелпер", "rank": 1, "rights": []},
        {"title": "Администратор", "rank": 4, "rights": ["banfull"]},
    ])
    assert "Наказания у этой должности выключены" in card
    assert "Банфулл" in card
    assert "весь проект" in card


def test_the_highest_empty_post_is_the_only_one_filled_from_the_database():
    posts = [
        {"title": "Создатель группы", "rank": 5, "people": []},
        {"title": "Администратор", "rank": 4, "people": [{"html": "Аня"}]},
        {"title": "Хелпер", "rank": 1, "people": []},
    ]
    assert highest_vacancy(posts) == 0
    occupied = [
        {"title": "Создатель группы", "rank": 5, "people": [{"html": "Илья"}]},
        {"title": "Хелпер", "rank": 1, "people": []},
    ]
    assert highest_vacancy(occupied) is None
    assert highest_vacancy([]) is None
    name, username = stored_owner_name("", "Илья", "@ilya", 15)
    assert name == "Илья"
    assert username == "ilya"
    bare, no_user = stored_owner_name("", "", "", 15)
    assert bare == "15"
    assert no_user == ""


def test_only_the_opener_is_named_in_the_buttons():
    rows = group_roster_rows(42, [{"title": "Администратор", "rank": 4}])
    flat = [item[1] for row in rows for item in row]
    icons = [item[2] for row in rows for item in row]
    assert "staff:gperm:42:0" in flat
    assert "staff:gall:42" in flat
    assert "staff:gstf:42" in flat
    assert all(":42" in data for data in flat)
    assert "5296491512660534111" in icons
    assert "5373346752671804066" in icons
    assert "5296773795091094130" in icons
    back = group_rights_rows(42)
    assert back[0][0][1] == "staff:gback:42"
    assert back[0][0][2] == "5296773795091094130"
    assert back[1][0][1] == "staff:gstf:42"
    assert staff_return_row(42)[0][1] == "staff:gadm:42"
    assert staff_return_row(42)[0][2] == "5296773795091094130"


def test_roster_buttons_reuse_the_message_rank_emoji():
    rows = group_roster_rows(7, [
        {"title": "Создатель", "rank": 5},
        {"title": "Хелпер", "rank": 1},
    ])
    first = rows[0]
    assert first[0][2] == "5305629674058061875"
    assert first[1][2] == "5393514467394875868"
    assert "👑" in first[0][0]
    assert "🔹" in first[1][0]


def test_icon_buttons_do_not_show_the_emoji_twice():
    # Иконка Telegram стоит перед текстом сама: в надписи остаётся только слово.
    assert split_icon_label("👑 Все права") == ("👑", "Все права")
    assert split_icon_label("🔸 Модератор") == ("🔸", "Модератор")
    assert split_icon_label("💎 Сотрудники проекта") == ("💎", "Сотрудники проекта")
    assert split_icon_label("Модератор") == ("", "Модератор")
    assert split_icon_label("🔸") == ("", "🔸")
    for row in group_roster_rows(3, [{"title": "Админ", "rank": 4}]) + group_rights_rows(3):
        for label, _data, icon in row:
            mark, text = split_icon_label(label)
            assert icon and mark and text and mark not in text


def test_a_shifted_list_still_opens_the_pressed_post():
    posts = [
        {"id": 11, "title": "Создатель", "rank": 5},
        {"id": 12, "title": "Модератор", "rank": 2},
    ]
    assert pick_post(posts, "1") == 1
    assert pick_post(posts, "1", "Модератор") == 1
    assert pick_post(posts, "1", "🔸 Модератор") == 1
    moved = [{"id": 13, "title": "Хелпер", "rank": 1}] + posts
    assert pick_post(moved, "1", "Модератор") == 2
    assert pick_post(moved, "9", "Модератор") == 2
    assert pick_post(moved, "1", "Удалённая") is None
    assert pick_post(posts, "x") is None
    assert pick_post(posts, "5") is None
    assert find_post(moved, 12) == 2
    assert find_post(moved, "12") == 2
    assert find_post(moved, 99) is None


def test_status_ticks_do_not_count_as_a_roster_change():
    base = [{
        "id": 1, "title": "Админ", "rank": 4, "rights": ["punish_mute"],
        "people": [{"uid": 5, "html": "Аня", "status": "🟢", "hint": ""}],
    }]
    away = [{**base[0], "people": [{"uid": 5, "html": "Аня", "status": "⚪️", "hint": "был час назад"}]}]
    assert roster_shape(base) == roster_shape(away)
    renamed = [{**base[0], "title": "Старший админ"}]
    other = [{**base[0], "people": [{"uid": 6, "html": "Илья", "status": "🟢"}]}]
    rights = [{**base[0], "rights": ["punish_mute", "banall"]}]
    for changed in (renamed, other, rights, []):
        assert roster_shape(changed) != roster_shape(base)
