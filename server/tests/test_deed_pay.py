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


def test_one_answer_closes_the_stage_and_moves_the_card_on():
    from deed_pay import UNDO_SORT_SQL, UNDO_STAFF_SQL, _staff_where, _work_where
    from deed_sort import (
        CREATOR_ORDER_SQL,
        FOLD_UNCLEAR_SQL,
        creator_ready_sql,
        reviewer_roster_sql,
        reviewer_totals_sql,
        verdict_of_sql,
    )

    work = _work_where()
    staff = _staff_where()
    assert "ds.action_id IS NULL" in work
    assert "epsilon_deed_claims" in work
    assert "epsilon_deed_unclear" not in work
    assert "st.action_id IS NULL" in staff
    assert "admin_accounts" in staff
    assert "senior_admin" in staff
    ready = creator_ready_sql()
    assert "lift_status = 'pending'" in ready
    assert "admin_accounts" in ready
    assert CREATOR_ORDER_SQL.index("lift_status = 'pending'") < CREATOR_ORDER_SQL.index("ds.verdict = 'clear' AND st.verdict = 'clear'")
    assert CREATOR_ORDER_SQL.index("ds.verdict = 'clear' AND st.verdict = 'clear'") < CREATOR_ORDER_SQL.index("ds.verdict = 'wrong' AND st.verdict = 'wrong'")
    assert "epsilon_deed_staff" in UNDO_SORT_SQL
    assert "INTERVAL '10 minutes'" in UNDO_SORT_SQL
    assert "lift_status IS NULL" in UNDO_STAFF_SQL
    assert "INSERT INTO epsilon_deed_sorts" in FOLD_UNCLEAR_SQL
    assert "DELETE FROM epsilon_deed_sorts" not in FOLD_UNCLEAR_SQL
    roster = reviewer_roster_sql()
    assert "UNION" in roster
    assert "epsilon_deed_staff" in roster
    assert "view_archive" in roster
    assert "cutegamingbot" in roster
    assert "JOIN staff_actions" in roster
    assert "COUNT(DISTINCT m.action_id)" in reviewer_totals_sql()
    archive = verdict_of_sql("s.id")
    assert "epsilon_deed_sorts" in archive
    assert "epsilon_deed_unclear" not in archive


def test_card_carries_the_chain_the_credits_and_the_lift():
    from deed_pay import CHECK_COUNT_SQL, ISSUE_COUNT_SQL, _by_person, _card

    row = {
        "id": 7, "action_type": "ban", "scope": "chat", "chat_id": -1001, "duration_minutes": 60,
        "created_at": None, "chat_title": "Кьют Чат", "admin_user_id": 3, "admin_name": "Пётр",
        "target_player_id": 9, "target_name": "Дима", "target_photo": None, "reason": "спам",
        "evidence": "", "proof_media_id": "file", "archive_count": 1, "rate_title": "Баны",
        "every_n": 50, "reward_kut": 80, "rate_enabled": True,
        "sort_verdict": "wrong", "sorter_id": 4, "sorter_name": "Анна",
        "staff_verdict": "wrong", "staff_id": 8, "staff_name": "Игорь",
        "lift_ask": True, "lift_status": "pending", "review_status": None,
    }
    card = _card(row, [])
    assert card["direct"] is False
    assert [step["role"] for step in card["chain"]] == ["admin", "staff"]
    assert card["chain"][0]["label"] == "Наказание выдано неправильно"
    assert card["lift"]["canLift"] is True
    assert card["lift"]["status"] == "pending"
    payable = {item["role"]: item["payable"] for item in card["credits"]}
    assert payable == {"issue": "keep", "admin": "drop", "staff": "drop"}
    direct = _card({
        **row,
        "sort_verdict": "", "sorter_name": "", "staff_verdict": "", "staff_name": "",
        "lift_ask": False, "lift_status": None,
    }, [])
    assert direct["direct"] is True
    assert direct["chain"] == []
    assert direct["lift"] is None
    person = _by_person(2, "s.id")
    assert "ds.sorter_id = $2" in person
    assert "mark.staff_id = $2" in person
    assert "credits_set" in ISSUE_COUNT_SQL
    assert "epsilon_deed_credits" in CHECK_COUNT_SQL


def test_pay_follows_the_matching_answer_and_a_kick_cannot_be_lifted():
    from deed_sort import can_apply_lift, credit_eligible, lift_actions, pick_credits

    people = [("issue", 3, ""), ("admin", 4, "clear"), ("staff", 8, "wrong"), ("admin", 5, "weak")]
    assert pick_credits("kept", people, None) == [("issue", 3), ("admin", 4)]
    assert pick_credits("dropped", people, None) == [("staff", 8)]
    assert pick_credits("kept", people, set()) == []
    assert pick_credits("dropped", people, {("staff", 8)}) == [("staff", 8)]
    assert credit_eligible("kept", "admin", "weak") is False
    assert credit_eligible("dropped", "issue", "") is False
    assert lift_actions("ban", "chat") == ("unban",)
    assert lift_actions("ban", "full") == ("unbanall", "bot_unban")
    assert lift_actions("mute", "all") == ("unmuteall",)
    assert lift_actions("warn", "chat") == ("unwarn_chat",)
    assert lift_actions("kick", "chat") is None
    ok, why = can_apply_lift("kick", "chat", -100, 9)
    assert ok is False
    assert "Кик" in why
    ok, why = can_apply_lift("ban", "chat", 0, 9)
    assert ok is False
    assert "группа" in why
    assert can_apply_lift("ban", "chat", -100, 9) == (True, "")


def test_project_sort_order_is_fixed():
    from deed_sort import ADMIN_ORDER_SQL, CREATOR_ORDER_SQL, VERDICT_LABELS, creator_rank, evidence_band

    assert evidence_band(True, "") == "photo"
    assert evidence_band(False, "спам") == "reason"
    assert evidence_band(False, "  ") == "empty"
    assert [creator_rank(name) for name in ("clear", "wrong", "weak", None)] == [1, 2, 4, 5]
    assert VERDICT_LABELS["clear"] == "Подходит"
    assert VERDICT_LABELS["wrong"] == "Наказание выдано неправильно"
    assert VERDICT_LABELS["weak"] == "Непонятно"
    assert CREATOR_ORDER_SQL.index("clear") < CREATOR_ORDER_SQL.index("wrong") < CREATOR_ORDER_SQL.index("weak")
    assert "proof_media_id" in ADMIN_ORDER_SQL
    assert "created_at ASC" in ADMIN_ORDER_SQL
    from deed_sort import self_can_sort
    seat = self_can_sort()
    assert "view_archive" in seat
    assert "me.user_id <>" in seat
    assert "key_hash" in seat


def test_norms_shrink_to_the_technical_purse_and_keep_a_reserve():
    from datetime import date

    from deed_pay import DAYS_SQL, PAID_SPLIT_SQL, PURSE_SQL
    from deed_tune import fill_days, plan_tune, unit_text, week_room

    room = week_room(100_000, 0)
    assert room["reserve"] == 40_000
    assert room["budget"] == 15_000
    assert week_room(100_000, 20_000)["budget"] == 0

    full = plan_tune(1_000_000, 0, {}, [], set(), groups=12)
    by = {item["action"]: item for item in full["updates"]}
    assert by["ban"]["reward"] == 200 and by["ban"]["enabled"] is True
    assert by["check_admin"]["reward"] == 40 and by["check_admin"]["enabled"] is True
    assert by["check_staff"]["reward"] == 60
    assert "полные нормы" in full["note"]
    assert "Выплатить" in full["note"]

    tight = plan_tune(100_000, 0, {"ban": 10_000}, [
        {"action": "ban", "every_n": 100, "reward": 200, "purse": "tech", "enabled": True, "title": "Баны"},
    ], set(), groups=4)
    ban = next(item for item in tight["updates"] if item["action"] == "ban")
    assert ban["reward"] < 200
    assert ban["every_n"] == 100
    assert "ужаты" in tight["note"]

    empty = plan_tune(0, 0, {"ban": 10}, [
        {"action": "ban", "every_n": 100, "reward": 200, "purse": "tech", "enabled": True, "title": "Баны"},
    ], {"ban"}, groups=0)
    assert all(item["action"] != "ban" for item in empty["updates"])
    assert empty["held"] == ["ban"]

    manual = plan_tune(1_000_000, 0, {}, [
        {"action": "ban", "every_n": 100, "reward": 10, "purse": "manual", "enabled": True, "title": "Баны"},
    ], set())
    assert all(item["action"] != "ban" for item in manual["updates"])

    assert unit_text(100, 200) == "2"
    assert unit_text(50, 80) == "1,6"
    assert unit_text(100, 40) == "0,4"
    days = fill_days([{"day": date(2026, 10, 4), "issue": 5, "admin": 1, "staff": 1}], date(2026, 10, 4))
    assert len(days) == 14
    assert days[-1] == {"day": "2026-10-04", "issue": 5, "admin": 1, "staff": 1}
    assert days[0]["issue"] == 0
    assert "is_technical" in PURSE_SQL
    assert "purse = 'tech'" in PAID_SPLIT_SQL
    assert "check_admin" in DAYS_SQL and "check_staff" in DAYS_SQL
