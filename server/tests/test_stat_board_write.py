from pathlib import Path


def test_message_day_write_keeps_tid_inside_sql():
    """asyncpg не кодирует tid из строки '(блок,строка)' — из-за этого сохранение давало 500."""
    source = (Path(__file__).resolve().parents[1] / "stat_board.py").read_text(encoding="utf-8")
    start = source.index("async def _write_message_day")
    end = source.index("async def _set_players")
    body = source[start:end]
    assert "::tid" not in body
    assert "ctid::text" not in body
    assert "keeper.tid" in body
    assert "INSERT INTO chatchange" in body
