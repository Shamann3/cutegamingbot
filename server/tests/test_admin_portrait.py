"""Портрет администратора на карточке игрока: только staff, детерминированный текст."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_permissions import ROLE_JUNIOR, ROLE_MODERATOR, ROLE_OWNER, ROLE_SENIOR
from admin_portrait import (
    AdminPortraitFacts,
    assemble_staff_portrait_payload,
    generate_admin_portrait,
    is_project_staff,
    staff_search_badge,
    tenure_days_from,
)


def _facts(**overrides) -> AdminPortraitFacts:
    base = dict(
        user_id=6801702632,
        role=ROLE_SENIOR,
        role_label="Старший администратор",
        section_labels=("Игроки", "Поддержка", "Архив"),
        tab_labels=("Поддержка · очередь",),
        tenure_days=120,
        hired_at="2026-05-10T12:00:00+00:00",
        tickets_closed=42,
        replies=90,
        tiktok_approved=11,
        tiktok_rejected=3,
        bans=7,
        unbans=2,
        mutes=4,
        warns=1,
        kicks=None,
        balance_adjusts=5,
        item_grants=None,
    )
    base.update(overrides)
    return AdminPortraitFacts(**base)


def test_ordinary_player_is_not_staff():
    assert is_project_staff(None, None) is False
    assert is_project_staff("applicant", "active") is False
    assert is_project_staff("moderator", "pending") is False
    assert is_project_staff("moderator", "suspended") is False
    assert is_project_staff("owner", "active") is True
    assert staff_search_badge("junior_admin", "active") is not None
    assert staff_search_badge("applicant", "active") is None
    assert assemble_staff_portrait_payload(role="applicant", status="active", facts=_facts()) is None
    assert assemble_staff_portrait_payload(role=ROLE_MODERATOR, status="pending", facts=_facts()) is None
    assert assemble_staff_portrait_payload(role=None, status=None, facts=None) is None


def test_admin_payload_has_portrait_and_achievements():
    payload = assemble_staff_portrait_payload(
        role=ROLE_SENIOR,
        status="active",
        facts=_facts(),
    )
    assert payload is not None
    assert payload["portrait"]
    assert "Старший администратор" in payload["portrait"] or "старш" in payload["portrait"].lower()
    assert payload["roleLabel"] == "Старший администратор"
    ids = {a["id"] for a in payload["achievements"]}
    assert "tickets" in ids
    assert "access" in ids
    assert "tt_ok" in ids
    assert all("salary" not in a["id"] for a in payload["achievements"])


def test_same_inputs_same_text():
    a = generate_admin_portrait(_facts())
    b = generate_admin_portrait(_facts())
    assert a == b
    assert 2 <= a.count(".") <= 4


def test_different_roles_different_texture():
    senior = generate_admin_portrait(_facts(role=ROLE_SENIOR, role_label="Старший администратор"))
    owner = generate_admin_portrait(_facts(role=ROLE_OWNER, role_label="Владелец"))
    junior = generate_admin_portrait(_facts(role=ROLE_JUNIOR, role_label="Младший администратор"))
    mod = generate_admin_portrait(_facts(role=ROLE_MODERATOR, role_label="Модератор"))
    texts = {senior, owner, junior, mod}
    assert len(texts) == 4
    assert "Владелец" in owner
    assert "Модератор" in mod or "модератор" in mod.lower()


def test_never_claims_counter_not_passed():
    text = generate_admin_portrait(
        _facts(
            tickets_closed=None,
            replies=None,
            tiktok_approved=None,
            tiktok_rejected=None,
            bans=None,
            unbans=None,
            mutes=None,
            warns=None,
            kicks=None,
            balance_adjusts=None,
            item_grants=None,
        )
    )
    low = text.lower()
    assert "тикет" not in low
    assert "tiktok" not in low
    assert "в архиве модерации" not in low
    assert "одобрен" not in low
    assert "отклонен" not in low
    assert "правк" not in low
    assert "выдач" not in low
    assert "barnum" not in low
    assert "сгенерир" not in low


def test_zero_counters_are_hidden_like_missing():
    text = generate_admin_portrait(
        _facts(
            tickets_closed=0,
            replies=0,
            tiktok_approved=0,
            tiktok_rejected=0,
            bans=0,
            unbans=0,
            mutes=0,
            warns=0,
            kicks=0,
            balance_adjusts=0,
            item_grants=0,
        )
    )
    low = text.lower()
    assert "тикет" not in low
    assert "tiktok" not in low
    payload = assemble_staff_portrait_payload(
        role=ROLE_SENIOR,
        status="active",
        facts=_facts(
            tickets_closed=0,
            replies=0,
            tiktok_approved=0,
            tiktok_rejected=0,
            bans=0,
            unbans=0,
            mutes=0,
            warns=0,
            kicks=0,
            balance_adjusts=0,
            item_grants=0,
            tab_labels=(),
        ),
    )
    ids = {a["id"] for a in payload["achievements"]}
    assert "tickets" not in ids
    assert "tt_ok" not in ids
    assert "bans" not in ids
    assert "access" in ids


def test_section_names_keep_capitals():
    text = generate_admin_portrait(_facts(section_labels=("Игроки", "Поддержка")))
    assert "Игроки" in text or "Поддержка" in text


def test_passed_ticket_counter_is_woven():
    text = generate_admin_portrait(_facts(tickets_closed=17, replies=None))
    assert "17" in text
    assert "тикет" in text.lower()


def test_tenure_from_hired_at():
    hired = datetime(2026, 3, 14, tzinfo=timezone.utc)
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    assert tenure_days_from(hired, None, now=now) == 184
    assert tenure_days_from(None, None) is None
