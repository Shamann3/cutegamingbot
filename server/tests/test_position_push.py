import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from group_realm import (
    MEMBER_RIGHTS,
    PUSH_GONE_REASON,
    PUSH_OWNER_REASON,
    PUSH_TWIN_REASON,
    plan_position_push,
    push_pages,
    router,
)

VOICE = [*MEMBER_RIGHTS, "can_manage_video_chats"]


def _source():
    return [
        {"id": 1, "title": "Создатель группы", "kind": "post", "rank": 5, "ladder": 0, "rights": []},
        {"id": 2, "title": "Администратор ГЧ", "kind": "post", "rank": 4, "ladder": 0, "rights": VOICE, "prefix": "ГЧ"},
        {
            "id": 3,
            "title": "Администратор",
            "kind": "post",
            "rank": 3,
            "ladder": 1,
            "rights": ["view_members", "view_archive", "punish_mute", "punish_ban", "can_delete_messages", "banfull"],
            "pages": ["work", "archive", "activity"],
        },
        {"id": 4, "title": "Модератор", "kind": "post", "rank": 2, "ladder": 2, "rights": ["view_members", "punish_mute", "punish_warn"]},
        {"id": 5, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 3, "rights": ["view_members", "punish_warn"]},
        {"id": 6, "title": "Обычный пользователь", "kind": "member", "rank": 0, "ladder": 0, "rights": list(MEMBER_RIGHTS)},
        {"id": 7, "title": "Спам блок", "kind": "spamblock", "rank": 0, "ladder": 0, "rights": [], "prefix": "спам блок"},
    ]


def _fresh_group():
    return [
        {"id": 11, "title": "Создатель группы", "kind": "post", "rank": 5, "ladder": 0, "rights": []},
        {
            "id": 12,
            "title": "Администратор",
            "kind": "post",
            "rank": 3,
            "ladder": 0,
            "rights": ["view_members", "view_archive", "punish_mute", "punish_ban", "punish_kick", "punish_warn"],
        },
        {
            "id": 13,
            "title": "Модератор",
            "kind": "post",
            "rank": 2,
            "ladder": 0,
            "rights": ["view_members", "view_archive", "punish_mute", "punish_kick", "punish_warn"],
        },
        {"id": 14, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 0, "rights": ["view_members", "punish_warn"]},
        {"id": 15, "title": "Обычный пользователь", "kind": "member", "rank": 0, "ladder": 0, "rights": list(MEMBER_RIGHTS)},
        {"id": 16, "title": "Спам блок", "kind": "spamblock", "rank": 0, "ladder": 0, "rights": [], "prefix": "спам блок"},
    ]


def test_whole_group_lands_as_here_and_the_creator_stays():
    plan = plan_position_push(_source(), _fresh_group(), [1, 2, 3, 4, 5, 6, 7])

    assert plan["skipped"] == [{"sourceId": 1, "title": "Создатель группы", "reason": PUSH_OWNER_REASON}]
    assert [(item["title"], item["rank"], item["prefix"]) for item in plan["create"]] == [("Администратор ГЧ", 4, "ГЧ")]
    assert set(plan["create"][0]["rights"]) == set(VOICE)

    updated = {item["title"]: item for item in plan["update"]}
    assert set(updated) == {"Администратор", "Модератор"}
    assert updated["Администратор"]["targetId"] == 12
    assert "banfull" in updated["Администратор"]["rights"]
    assert updated["Администратор"]["pages"] == ["work", "archive", "activity"]
    assert "rights" in updated["Администратор"]["changes"]
    assert "accepting" not in updated["Администратор"]["changes"]
    assert updated["Модератор"]["changes"] == ["rights", "pages"]
    assert updated["Модератор"]["pages"] is None
    assert [item["rank"] for item in plan["update"]] == [3, 2]

    assert {item["title"] for item in plan["same"]} == {"Хелпер", "Обычный пользователь", "Спам блок"}
    assert plan["shifts"] == []
    assert plan["order"] == [("new", 2), ("old", 12), ("old", 13), ("old", 14)]
    touched = {item["targetId"] for item in plan["update"]}
    assert 11 not in touched
    assert ("old", 11) not in plan["order"]


def test_one_post_follows_its_neighbours_from_here():
    target = _fresh_group()
    target[1]["rank"], target[2]["rank"], target[3]["rank"] = 3, 4, 2

    plan = plan_position_push(_source(), target, [4])

    assert plan["order"] == [("old", 12), ("old", 13), ("old", 14)]
    moved = plan["update"][0]
    assert (moved["title"], moved["rankFrom"], moved["rank"]) == ("Модератор", 4, 3)
    assert "rank" in moved["changes"]
    assert plan["shifts"] == [{"id": 12, "title": "Администратор", "from": 3, "to": 4}]


def test_application_switch_travels_with_the_post():
    source = [{"id": 5, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 0, "rights": ["view_members"], "accepting": False}]
    target = [{"id": 14, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 0, "rights": ["view_members"], "accepting": True}]
    plan = plan_position_push(source, target, [5])
    assert plan["update"][0]["changes"] == ["accepting"]
    assert plan["update"][0]["accepting"] is False
    assert plan["create"] == []


def test_same_place_and_same_rights_change_nothing():
    plan = plan_position_push(_source(), _fresh_group(), [5])

    assert plan["create"] == []
    assert plan["update"] == []
    assert [item["title"] for item in plan["same"]] == ["Хелпер"]
    assert plan["order"] is None
    assert plan["shifts"] == []


def test_without_common_posts_the_rank_from_here_decides():
    source = [{"id": 1, "title": "Стажёр", "kind": "post", "rank": 2, "ladder": 0, "rights": ["view_members"]}]
    target = [
        {"id": 21, "title": "Старший", "kind": "post", "rank": 4, "ladder": 0, "rights": []},
        {"id": 22, "title": "Дежурный", "kind": "post", "rank": 3, "ladder": 1, "rights": []},
    ]
    low = plan_position_push(source, target, [1])
    assert low["order"] == [("old", 21), ("old", 22), ("new", 1)]
    assert low["create"][0]["rank"] == 2
    assert low["shifts"] == []

    source[0]["rank"] = 4
    high = plan_position_push(source, target, [1])
    assert high["order"] == [("old", 21), ("new", 1), ("old", 22)]
    assert high["create"][0]["rank"] == 3
    assert high["shifts"] == [{"id": 22, "title": "Дежурный", "from": 3, "to": 2}]


def test_names_that_belong_to_other_kinds_are_not_taken():
    source = [
        {"id": 1, "title": "Спам блок", "kind": "post", "rank": 2, "ladder": 0, "rights": []},
        {"id": 2, "title": "создатель  группы", "kind": "post", "rank": 3, "ladder": 0, "rights": []},
        {"id": 3, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 1, "rights": []},
        {"id": 4, "title": "Хелпер", "kind": "post", "rank": 1, "ladder": 2, "rights": []},
    ]
    plan = plan_position_push(source, _fresh_group(), [1, 2, 3, 4, 99])
    reasons = {(item["sourceId"], item["reason"]) for item in plan["skipped"]}
    assert (99, PUSH_GONE_REASON) in reasons
    assert (1, "Так в той группе называется спам-блок") in reasons
    assert (2, "Так в той группе называется создатель группы") in reasons
    assert (4, PUSH_TWIN_REASON) in reasons
    assert [item["title"] for item in plan["update"] + plan["same"]] == ["Хелпер"]


def test_member_and_spam_block_match_by_kind_and_rename_only_when_free():
    source = _source()
    source[5]["title"] = "Участник"
    source[6]["prefix"] = ""
    plan = plan_position_push(source, _fresh_group(), [6, 7])
    renamed = plan["update"][0]
    assert (renamed["title"], renamed["targetId"], renamed["changes"]) == ("Участник", 15, ["title"])
    assert [item["title"] for item in plan["same"]] == ["Спам блок"]

    target = _fresh_group()
    target.append({"id": 17, "title": "Участник", "kind": "post", "rank": 1, "ladder": 5, "rights": []})
    kept = plan_position_push(source, target, [6])
    assert kept["update"] == []
    assert kept["same"][0]["title"] == "Обычный пользователь"


def test_pages_follow_rights_until_a_list_is_saved():
    assert push_pages(["view_archive"], None) == {"work", "archive"}
    assert push_pages(["punish_warn"], None) == {"activity"}
    assert push_pages(["view_archive"], ["rights", "pay", "bogus"]) == {"rights", "pay"}


def test_push_route_is_creator_only_and_sits_before_the_edit_route():
    from group_realm import _push_into, push_positions

    paths = [(route.path, sorted(route.methods or [])) for route in router.routes]
    push_at = paths.index(("/group-realm/positions/push", ["POST"]))
    edit_at = paths.index(("/group-realm/positions/{position_id}", ["POST"]))
    assert push_at < edit_at
    assert "_require_creator(user_id)" in inspect.getsource(push_positions)
    body = inspect.getsource(_push_into)
    assert "connection.transaction()" in body
    assert "connection=connection" in body
    assert "epsilon_seats" not in body
