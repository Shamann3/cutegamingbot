# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flame_bonus_plus import (
    board_cell_faces,
    board_cells,
    board_range,
    canon_board_cells,
    gift_plus_defaults,
    parse_cell_paste,
    preview_has_content,
    preview_hidden_names,
    preview_kuty_lines,
    preview_max_gifts,
    preview_show_names,
    roll_extra_bundle,
)
from flame_bonus_plus_copy import screen_board, screen_intro, screen_possible, screen_result


def test_board_cells_follow_the_grid():
    cells = board_cells("")
    assert len(cells) == 9
    assert cells[0]["id"] == "5321218545621706269"
    assert cells[0]["alt"] == "🎈"
    pasted = parse_cell_paste(
        "<tg-emoji emoji-id='5999999999999999991'>🔥</tg-emoji>"
        "<tg-emoji emoji-id='5999999999999999992'>⭐</tg-emoji>"
    )
    assert [item["id"] for item in pasted] == ["5999999999999999991", "5999999999999999992"]
    assert pasted[0]["alt"] == "🔥"
    changed = board_cells([{"id": "5999999999999999991", "alt": "🔥"}])
    assert changed[0] == {"id": "5999999999999999991", "alt": "🔥"}
    assert changed[1]["id"] == cells[1]["id"]
    assert board_cells([{"id": "нет", "alt": "🔥"}])[0]["id"] == cells[0]["id"]
    faces = board_cell_faces(changed)
    assert faces[0] == "<tg-emoji emoji-id='5999999999999999991'>🔥</tg-emoji>"
    assert faces[1].startswith(f"<tg-emoji emoji-id='{cells[1]['id']}'>")
    assert parse_cell_paste("просто текст") == []
    assert canon_board_cells(changed) == canon_board_cells(canon_board_cells(changed))


def test_defaults_and_board_range():
    conf = gift_plus_defaults({
        "gift_enabled": True,
        "gift_mult": 2,
        "gift_kuty_min": 10,
        "gift_kuty_max": 20,
        "gift_item_count": 3,
    })
    assert conf["mult"] == 2
    assert conf["item_count"] == 3
    assert board_range(conf) == (20, 40)


def test_extra_can_request_item_and_kuty_independently():
    conf = gift_plus_defaults({
        "gift_extra_kuty_on": True,
        "gift_extra_kuty_chance": 100,
        "gift_extra_kuty_min": 7,
        "gift_extra_kuty_max": 7,
        "gift_item_on": True,
        "gift_item_chance": 100,
        "drops": [
            {"kind": "item", "item_name": "Купон", "weight": 1},
            {"kind": "item", "item_name": "Вода", "weight": 1},
        ],
    })
    hit = False
    for _ in range(40):
        bundle = roll_extra_bundle(conf)
        if bundle["extra_kuty"] == 7 and bundle["want_item"] and "Купон" in bundle["item_names"]:
            hit = True
            break
    assert hit


def test_multi_item_slots_without_duplicate_preferred():
    conf = gift_plus_defaults({
        "gift_item_on": True,
        "gift_item_chance": 100,
        "gift_item_count": 2,
        "gift_extra_kuty_on": False,
        "drops": [
            {"kind": "item", "item_name": "Купон", "weight": 100},
            {"kind": "item", "item_name": "Вода", "weight": 100},
        ],
    })
    bundle = roll_extra_bundle(conf)
    assert bundle["want_item"] is True
    assert len(bundle["item_picks"]) == 2
    preferred = [picks[0] for picks in bundle["item_picks"]]
    assert len(set(preferred)) == 2


def test_preview_only_checked_items():
    conf = gift_plus_defaults({
        "gift_item_on": True,
        "gift_item_count": 3,
        "gift_kuty_min": 10,
        "gift_kuty_max": 20,
        "gift_mult": 1,
        "gift_extra_kuty_on": True,
        "gift_extra_kuty_min": 5,
        "gift_extra_kuty_max": 25,
        "drops": [
            {"kind": "item", "item_name": "Купон", "weight": 1, "show_preview": True},
            {"kind": "item", "item_name": "Секрет", "weight": 1, "show_preview": False},
            {"kind": "item", "item_name": "Вода", "weight": 1, "showPreview": True},
        ],
    })
    assert preview_show_names(conf) == ["Купон", "Вода"]
    assert preview_max_gifts(conf) == 2
    assert preview_has_content(conf) is True
    assert preview_hidden_names(conf) == ["Секрет"]
    kuty = preview_kuty_lines(conf)
    assert any("10" in line and "20" in line for line in kuty)
    assert any("иногда" in line and "5" in line and "25" in line for line in kuty)
    sure = gift_plus_defaults({**conf, "extra_kuty_chance": 100})
    assert any(line.startswith("ещё ") for line in preview_kuty_lines(sure))
    silent = gift_plus_defaults({**conf, "extra_kuty_chance": 0})
    assert len(preview_kuty_lines(silent)) == 1


def test_copy_keeps_intro_mysterious():
    text = screen_intro(mult=2)
    assert "Бонус +" in text
    assert "улучшенный бонус" in text
    assert "Нажмите на одну из кнопок" in text
    assert "кут" not in text.lower()
    assert "Купон" not in text
    possible = screen_possible(
        max_gifts=2,
        lines=["<code>🎁</code> <b>Купон</b>", "<code>💧</code> <b>Вода</b>"],
        kuty_lines=["<b>+10…30</b> кут с клетки", "иногда ещё <b>+5…25</b> кут"],
        hidden=True,
    )
    assert "<b>2шт</b>" in possible
    assert "Купон" in possible and "Вода" in possible
    assert "10…30" in possible
    assert "в списке не всё" in possible
    board = screen_board(mult=2, kuty_lo=10, kuty_hi=40)
    assert "Выберите одну клетку" in board
    assert "кут" not in board.lower()


def test_copy_mentions_project_kuty():
    result = screen_result(
        board_kuty=12,
        extra_kuty=5,
        project_kuty=9,
        item_lines=["🎁 + <b>Купон</b>", "💧 + <b>Вода</b>"],
    )
    assert "Бонус открыт" in result
    assert "Вот что в нём было :" in result
    assert "<b>+ 12 кут</b>" in result
    assert "<i>Спасибо, что вы с нами</i>" in result
    assert "куты от проекта" in result.lower()
    assert "30%" not in result
    assert "+12" in result or "12" in result
    assert "Купон" in result and "Вода" in result


def test_empty_result_is_honest():
    text = screen_result(board_kuty=0, extra_kuty=0, project_kuty=0, item_lines=[])
    assert "наградить нечем" in text.lower() or "нечем" in text.lower()
