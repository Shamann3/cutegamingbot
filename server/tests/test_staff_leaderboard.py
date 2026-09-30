"""Рейтинг сотрудников не должен кодировать Telegram ID как int4."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_db import _leaderboard_entry, _leaderboard_sql


def test_leaderboard_query_never_binds_a_user_id():
    sql = _leaderboard_sql("to_timestamp(ac.slot)")
    assert "$1" in sql
    assert "$2" not in sql
    assert "resolved_by" in sql
    assert "::bigint = m.user_id::bigint" in sql


def test_leaderboard_rejects_an_unknown_slot_expression():
    try:
        _leaderboard_sql("ac.slot; DROP TABLE staff_actions")
    except ValueError:
        return
    raise AssertionError("slot expression was not rejected")


def test_leaderboard_score_matches_the_member_card():
    row = {
        "user_id": 7555666259,
        "username": "wide",
        "first_name": "Широкий",
        "role": "moderator",
        "actions_total": 4,
        "bans": 1,
        "unbans": 0,
        "mutes": 2,
        "taken": 3,
        "resolved": 2,
        "avg_s": 12.9,
        "slots": 7,
    }
    item = _leaderboard_entry(row)
    # 4 действия + 2 закрытые жалобы × 3 + 3 взятые + 70 минут // 60
    assert item["userId"] == 7555666259
    assert item["score"] == 4 + 6 + 3 + 1
    assert item["onlineMinutes"] == 70
    assert item["avgResponseSeconds"] == 12
    assert item["complaintsResolved"] == 2
    assert item["complaintsTaken"] == 3


def test_leaderboard_score_allows_an_empty_period():
    item = _leaderboard_entry({
        "user_id": 7,
        "username": None,
        "first_name": None,
        "role": "moderator",
        "actions_total": 0,
        "bans": 0,
        "unbans": 0,
        "mutes": 0,
        "taken": 0,
        "resolved": 0,
        "avg_s": None,
        "slots": 0,
    })
    assert item["score"] == 0
    assert item["avgResponseSeconds"] is None
    assert item["onlineMinutes"] == 0
