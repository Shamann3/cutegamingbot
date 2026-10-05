"""Живая сверка архива и колод не забирает карточку из рук."""

import inspect

from admin_moderation import list_moderation_logs
from deed_pay import deed_pulse
from group_realm import group_pulse


def test_group_pulse_reads_the_same_archive_as_the_cabinet():
    source = inspect.getsource(group_pulse)
    assert "_moderation_counts" in source
    assert "chat_warn_watch" in source
    assert "_grab" not in source


def test_deed_pulse_counts_without_taking_a_card():
    source = inspect.getsource(deed_pulse)
    assert "_count" in source
    assert "_grab" not in source
    assert "_open_deck" not in source
    for key in ("work", "staff", "own", "queue"):
        assert f'"{key}"' in source


def test_archive_can_ask_for_rows_after_an_id():
    source = inspect.getsource(list_moderation_logs)
    assert "after_id" in source
    assert "id >" in source
    assert "COUNT(*)" in source
