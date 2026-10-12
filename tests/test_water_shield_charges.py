# -*- coding: utf-8 -*-
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import water_shield_charges as charges


def test_kind_follows_the_item_even_after_it_is_sold():
    assert charges.kind_of("Зонтик") == "dryumbrella"
    assert charges.kind_of("сухой сейф") == "drysafe"
    assert charges.kind_of("339") == "drysafe"
    assert charges.kind_of("Пистолетик") is None


def test_leftover_freezes_the_time_that_is_still_left():
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    assert charges.leftover_seconds(None, now) is None
    assert charges.leftover_seconds(now + timedelta(hours=2, minutes=5), now) == 7500
    assert charges.leftover_seconds(now - timedelta(seconds=1), now) == 0
