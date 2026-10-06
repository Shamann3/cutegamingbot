from bot.admins.group_roster import (
    granted_lines,
    group_rights_rows,
    group_roster_rows,
    render_group_rights,
    render_group_roster,
    staff_return_row,
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


def test_only_the_opener_is_named_in_the_buttons():
    rows = group_roster_rows(42, [{"title": "Администратор", "rank": 4}])
    flat = [data for row in rows for _label, data in row]
    assert "staff:gperm:42:0" in flat
    assert "staff:gall:42" in flat
    assert "staff:gstf:42" in flat
    assert all(":42" in data for data in flat)
    back = group_rights_rows(42)
    assert back[0][0][1] == "staff:gback:42"
    assert back[1][0][1] == "staff:gstf:42"
    assert staff_return_row(42)[0][1] == "staff:gadm:42"
