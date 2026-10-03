"""Нормы оплаты за наказания: сколько кут и откуда списывать."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from deed_pay import _filters, milestones_for, plan_take, progress_line
from human_actor import human_actor_sql


def test_hundred_confirmed_bans_are_one_payout():
    assert milestones_for(99, 100) == 0
    assert milestones_for(100, 100) == 1
    assert milestones_for(250, 100) == 2
    assert milestones_for(10, 0) == 0
    line = progress_line(37, 100, 200)
    assert line == {"confirmed": 37, "into": 37, "left": 63, "nextReward": 200}


def test_kut_comes_from_the_richest_technical_groups_first():
    assert plan_take([(11, 150), (22, 80)], 200) == [(11, 150), (22, 50)]
    assert plan_take([(11, 500)], 200) == [(11, 200)]
    try:
        plan_take([(11, 40)], 200)
    except ValueError as exc:
        assert "не хватает" in str(exc)
    else:
        raise AssertionError("short purse must fail")


def test_creator_review_hides_bot_actions():
    where, params = _filters("", 0)
    assert params == [["ban", "mute", "kick", "warn"]]
    assert "система" in where
    assert "cutegamingbot" in where
    assert "7683193125" in where
    assert "s.admin_user_id" in human_actor_sql("s")
    assert "admin_name" in human_actor_sql()
    assert "ds.action_id IS NOT NULL" in where
    assert "view_archive" in where


def test_reviewer_roster_counts_every_verdict_and_later_decision():
    from deed_pay import _filters, _reviewer
    from deed_sort import reviewer_roster_sql

    sql = reviewer_roster_sql()
    assert "epsilon_deed_sorts" in sql
    assert "verdict = 'clear'" in sql
    assert "verdict = 'wrong'" in sql
    assert "verdict = 'weak'" in sql
    assert "status = 'kept'" in sql
    assert "status = 'dropped'" in sql
    assert "view_archive" in sql
    assert "UNION" in sql
    where, params = _filters("", 0, 15)
    assert "ds.sorter_id = $2" in where
    assert params[-1] == 15
    person = _reviewer({
        "id": 4,
        "name": "Анна",
        "username": "anna",
        "title": "Модератор",
        "reviewed": 12,
        "clear_n": 7,
        "wrong_n": 3,
        "weak_n": 2,
        "kept_n": 5,
        "dropped_n": 1,
        "open_n": 6,
        "last_at": None,
    })
    assert person["name"] == "Анна (@anna)"
    assert person["reviewed"] == 12
    assert person["waiting"] == 6
    assert person["lastAt"] is None


def test_undo_only_touches_your_own_fresh_decision():
    from deed_pay import UNDO_MINUTES, UNDO_REVIEW_SQL, UNDO_SORT_SQL

    assert UNDO_MINUTES == 10
    assert "reviewer_id = $2" in UNDO_REVIEW_SQL
    assert "INTERVAL '10 minutes'" in UNDO_REVIEW_SQL
    assert "RETURNING status" in UNDO_REVIEW_SQL
    assert "sorter_id = $2" in UNDO_SORT_SQL
    assert "INTERVAL '10 minutes'" in UNDO_SORT_SQL
    assert "NOT EXISTS" in UNDO_SORT_SQL
    assert "epsilon_deed_reviews" in UNDO_SORT_SQL


def test_roster_ignores_deleted_and_bot_records():
    from deed_sort import reviewer_roster_sql, reviewer_totals_sql

    for sql in (reviewer_roster_sql(), reviewer_totals_sql()):
        assert "JOIN staff_actions s ON s.id = m.action_id" in sql
        assert "cutegamingbot" in sql
        assert "'ban', 'mute', 'kick', 'warn'" in sql


def test_unclear_stays_open_for_other_admins_and_reaches_creator_at_once():
    from deed_pay import UNDO_UNCLEAR_SQL, _work_where
    from deed_sort import (
        CREATOR_ORDER_SQL,
        MOVE_OLD_UNCLEAR_SQL,
        creator_ready_sql,
        reviewer_roster_sql,
        reviewer_totals_sql,
        verdict_of_sql,
    )

    work = _work_where()
    assert "ds.action_id IS NULL" in work
    assert "mine.sorter_id = $2" in work
    assert "dq.n" not in work
    assert "COALESCE(dq.n, 0) > 0" in creator_ready_sql()
    assert CREATOR_ORDER_SQL.index("'wrong'") < CREATOR_ORDER_SQL.index("dq.n") < CREATOR_ORDER_SQL.index("ELSE 3")
    assert "sorter_id = $2" in UNDO_UNCLEAR_SQL
    assert "INTERVAL '10 minutes'" in UNDO_UNCLEAR_SQL
    assert "epsilon_deed_reviews" in UNDO_UNCLEAR_SQL
    assert "epsilon_deed_sorts" in UNDO_UNCLEAR_SQL
    assert "DELETE FROM epsilon_deed_sorts" in MOVE_OLD_UNCLEAR_SQL
    assert "INSERT INTO epsilon_deed_unclear" in MOVE_OLD_UNCLEAR_SQL
    roster = reviewer_roster_sql()
    assert "UNION ALL" in roster
    assert "epsilon_deed_unclear" in roster
    assert "COUNT(DISTINCT m.action_id)" in reviewer_totals_sql()
    archive = verdict_of_sql("s.id")
    assert "epsilon_deed_sorts" in archive and "epsilon_deed_unclear" in archive


def test_card_shows_unclear_without_a_precise_answer():
    from deed_pay import _by_sorter, _card, _verdict_of

    assert _verdict_of({"sort_verdict": None, "unclear_n": 2}) == "weak"
    assert _verdict_of({"sort_verdict": "clear", "unclear_n": 1}) == "clear"
    assert _verdict_of({}) == ""
    row = {
        "id": 7, "action_type": "mute", "scope": "chat", "chat_id": -1001, "duration_minutes": 60,
        "created_at": None, "chat_title": "Кьют Чат", "admin_user_id": 3, "admin_name": "Пётр",
        "target_player_id": 9, "target_name": "Дима", "target_photo": None, "reason": "спам",
        "evidence": "", "proof_media_id": "file", "archive_count": 1, "rate_title": "Муты",
        "every_n": 50, "reward_kut": 80, "rate_enabled": True,
        "sort_verdict": None, "sorter_name": "", "unclear_n": 2, "unclear_names": ["Анна", "Олег"],
    }
    card = _card(row, [])
    assert card["sortVerdict"] == "weak"
    assert card["sortLabel"] == "Непонятно"
    assert card["unclearCount"] == 2
    assert card["unclearNames"] == ["Анна", "Олег"]
    assert card["direct"] is False
    assert card["sorterName"] == ""
    direct = _card({**row, "unclear_n": 0, "unclear_names": []}, [])
    assert direct["direct"] is True
    assert direct["sortVerdict"] is None
    sorter = _by_sorter(3, "s.id")
    assert "ds.sorter_id = $3" in sorter
    assert "mark.sorter_id = $3" in sorter


def test_project_sort_order_is_fixed():
    from deed_sort import ADMIN_ORDER_SQL, CREATOR_ORDER_SQL, VERDICT_LABELS, creator_rank, evidence_band

    assert evidence_band(True, "") == "photo"
    assert evidence_band(False, "спам") == "reason"
    assert evidence_band(False, "  ") == "empty"
    assert [creator_rank(name) for name in ("clear", "wrong", "weak", None)] == [0, 1, 2, 3]
    assert VERDICT_LABELS["clear"] == "Подходит"
    assert VERDICT_LABELS["wrong"] == "Не подходит"
    assert VERDICT_LABELS["weak"] == "Непонятно"
    assert CREATOR_ORDER_SQL.index("clear") < CREATOR_ORDER_SQL.index("wrong") < CREATOR_ORDER_SQL.index("weak")
    assert "proof_media_id" in ADMIN_ORDER_SQL
    assert "created_at ASC" in ADMIN_ORDER_SQL
    from deed_sort import self_can_sort
    seat = self_can_sort()
    assert "view_archive" in seat
    assert "me.user_id <>" in seat
    assert "key_hash" in seat
