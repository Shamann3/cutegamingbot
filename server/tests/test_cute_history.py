"""История кут: чистые функции нормализации/слияния, без БД."""
from datetime import datetime, timezone

from admin_cute_history import (
    cute_direction,
    counterparty_id,
    normalize_cute_row,
    normalize_donate_row,
    merge_and_paginate,
)

TS_A = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
TS_B = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def test_cute_direction():
    assert cute_direction(100, None) == "in"
    assert cute_direction(None, 50) == "out"


def test_counterparty_id_out_returns_receiver():
    assert counterparty_id("out", 111, 222) == 222


def test_counterparty_id_in_returns_sender():
    assert counterparty_id("in", 111, 222) == 111


def test_counterparty_id_none_when_missing_side():
    assert counterparty_id("out", None, None) is None
    assert counterparty_id("in", 111, None) is None


def test_normalize_cute_transfer_out_attaches_receiver():
    row = {"plus": None, "minus": 500, "cause": "дать", "balance": 1500,
           "transfer_id": 7, "ts": TS_A, "sender_id": 111, "receiver_id": 222}
    item = normalize_cute_row(row, {222: {"name": "Аня", "username": "anya"}})
    assert item["direction"] == "out"
    assert item["amount"] == 500
    assert item["kind"] == "transfer"
    assert item["counterparty"] == {"userId": 222, "name": "Аня", "username": "anya"}
    assert item["ts"] == "2026-07-21T10:00:00+00:00"


def test_normalize_cute_transfer_in_attaches_sender():
    row = {"plus": 500, "minus": None, "cause": "дать", "balance": 2000,
           "transfer_id": 7, "ts": TS_A, "sender_id": 111, "receiver_id": 222}
    item = normalize_cute_row(row, {111: {"name": "Боб", "username": None}})
    assert item["direction"] == "in"
    assert item["kind"] == "transfer"
    assert item["counterparty"]["userId"] == 111


def test_normalize_cute_plain_has_no_counterparty():
    row = {"plus": 200, "minus": None, "cause": "+ выигрыш bingo", "balance": 1700,
           "transfer_id": None, "ts": TS_A, "sender_id": None, "receiver_id": None}
    item = normalize_cute_row(row, {})
    assert item["kind"] == "cute"
    assert "counterparty" not in item
    assert item["amount"] == 200


def test_normalize_donate():
    item = normalize_donate_row({"count": 100, "ts": TS_A})
    assert item == {"ts": "2026-07-21T10:00:00+00:00", "cause": "донат",
                    "amount": 100, "direction": "in", "balance": None, "kind": "donate"}


def test_merge_sorts_desc_across_sources():
    cute = [{"ts": TS_A.isoformat(), "kind": "cute"}]
    donate = [{"ts": TS_B.isoformat(), "kind": "donate"}]
    out = merge_and_paginate(cute, donate, 0, 10)
    assert [i["kind"] for i in out] == ["donate", "cute"]


def test_merge_pagination_offset_limit():
    items = [{"ts": datetime(2026, 7, 21, h, tzinfo=timezone.utc).isoformat(),
              "kind": str(h)} for h in range(5)]
    out = merge_and_paginate(items, [], 1, 2)  # desc: 4,3,2,1,0 -> offset1,limit2 -> 3,2
    assert [i["kind"] for i in out] == ["3", "2"]


def test_merge_none_ts_goes_last():
    out = merge_and_paginate(
        [{"ts": None, "kind": "x"}],
        [{"ts": TS_A.isoformat(), "kind": "y"}],
        0, 10,
    )
    assert [i["kind"] for i in out] == ["y", "x"]


def test_cute_history_route_registered():
    import os
    os.environ.setdefault("PRODUCTION", "false")
    from app import app
    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert any(p.endswith("/users/{target_user_id}/cute-history") for p in paths), (
        f"cute-history route not registered: {paths}"
    )


def test_parse_date_returns_date_or_none():
    from datetime import date
    from admin_cute_history import _parse_date
    assert _parse_date("2026-05-10") == date(2026, 5, 10)
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("not-a-date") is None
    assert _parse_date(date(2026, 7, 22)) == date(2026, 7, 22)


def test_date_filters_bound_as_date_objects_not_strings():
    """Regression: asyncpg encodes a $N::date param with its date codec, which
    calls .toordinal() and therefore needs a datetime.date, not a str. Passing
    the raw 'YYYY-MM-DD' string raised
    `DataError: ... 'str' object has no attribute 'toordinal'`.
    get_user_cute_history must convert date_from/date_to before binding."""
    import asyncio
    from datetime import date
    import admin_cute_history

    captured_args = []

    class FakePool:
        async def fetchval(self, query, *args):
            captured_args.extend(args)
            return 0

        async def fetch(self, query, *args):
            captured_args.extend(args)
            return []

    original_pool = admin_cute_history.db.pool
    admin_cute_history.db.pool = FakePool()
    try:
        asyncio.run(admin_cute_history.get_user_cute_history(
            123, date_from="2026-05-10", date_to="2026-07-22",
        ))
    finally:
        admin_cute_history.db.pool = original_pool

    # raw date strings must never reach asyncpg
    assert "2026-05-10" not in captured_args
    assert "2026-07-22" not in captured_args
    # they must be bound as datetime.date objects
    assert date(2026, 5, 10) in captured_args
    assert date(2026, 7, 22) in captured_args
