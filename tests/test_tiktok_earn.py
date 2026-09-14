import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from tiktok_earn_logic import (  # noqa: E402
    kut_for_views,
    normalize_nick,
    parse_tiktok_url,
    payout_delta,
    validate_nick,
)


def test_nick_taken_message_is_defined():
    from bot.funcs import tiktok_earn as tt
    src = Path(tt.__file__).read_text(encoding="utf-8")
    assert "Этот ник уже занят другим игроком" in src
    assert "Можно не больше" in src
    assert "Эта пачка ещё на проверке" in src
    assert "Без него скриншоты принять нельзя" in src
    assert "require_nicks" in src


def test_bot_texts_match_plan():
    from bot.funcs.tiktok_earn import help_earnings_block, text_ask_nick, text_hub, text_need_nick
    assert "Тик ток" in text_hub()
    assert "cuteplayer" in text_ask_nick()
    assert "Задания" in help_earnings_block()
    assert "по которому тебя можно найти" in text_need_nick() or "можно найти" in text_need_nick()


def test_hub_buttons_use_premium_emoji_ids():
    from bot.funcs.tiktok_earn import ICON_COMMENTS, ICON_VIDEOS, hub_keyboard

    kb = hub_keyboard()
    comments = kb.inline_keyboard[0][0]
    videos = kb.inline_keyboard[1][0]
    assert comments.text == "Комментарии"
    assert videos.text == "Видео о боте"
    assert "<tg-emoji" not in comments.text
    assert comments.icon_custom_emoji_id == ICON_COMMENTS == "5350367217349311525"
    assert videos.icon_custom_emoji_id == ICON_VIDEOS == "5375309569905938163"


def test_player_tiktok_texts_have_no_emdash():
    from bot.funcs.tiktok_earn import (
        collect_text,
        help_earnings_block,
        text_ask_nick,
        text_comments,
        text_hub,
        text_need_nick,
        text_nicks,
        text_videos,
    )
    from pathlib import Path

    blobs = [
        text_hub(),
        text_comments({}),
        text_videos({}),
        text_need_nick(),
        text_ask_nick(),
        text_nicks(["cuteplayer"], locked=False),
        help_earnings_block(),
        collect_text(7, 15, ["cuteplayer"]),
        collect_text(15, 15, ["cuteplayer"]),
    ]
    help_src = Path("bot/funcs/help.py").read_text(encoding="utf-8")
    tiktok_help = help_src.split("<b>TikTok</b>")[1].split("<b>Промокоды</b>")[0]
    blobs.append(tiktok_help)
    for blob in blobs:
        assert "—" not in blob
        assert "–" not in blob
    assert "<b>" in text_hub()
    assert "<i>" not in text_hub()


def _kb_data(kb) -> str:
    return " ".join(btn.callback_data or "" for row in kb.inline_keyboard for btn in row)


def test_collect_progress_and_undo_available_before_full():
    from bot.funcs.tiktok_earn import collect_keyboard, collect_text, pick_thumb_file_id

    text = collect_text(7, 15, ["cuteplayer"])
    assert "7 из 15" in text
    assert "Осталось 8" in text
    assert "@cuteplayer" in text
    dumped = _kb_data(collect_keyboard(7, 15))
    assert "tt:undo_photo" in dumped
    assert "tt:submit_photos" not in dumped
    assert "tt:submit_photos" in _kb_data(collect_keyboard(15, 15))

    class _Size:
        def __init__(self, file_id, width):
            self.file_id = file_id
            self.width = width

    assert pick_thumb_file_id([_Size("small", 90), _Size("mid", 320), _Size("big", 1280)]) == "mid"


def test_video_recheck_state_and_keyboard():
    from datetime import datetime, timedelta, timezone
    from bot.funcs.tiktok_earn import video_recheck_state, videos_keyboard

    now = datetime.now(timezone.utc)
    waiting = video_recheck_state(now, 7)
    assert waiting["ready"] is False
    assert "через" in waiting["waitText"]
    ready = video_recheck_state(now - timedelta(days=8), 7)
    assert ready["ready"] is True
    dumped = _kb_data(videos_keyboard([
        {"id": 4, "status": "live", "recheckPending": False, "recheckReady": False},
        {"id": 5, "status": "live", "recheckPending": False, "recheckReady": True},
    ]))
    assert "tt:recheck:5" in dumped
    assert "tt:recheck:4" not in dumped


def test_shared_url_and_payout():
    assert normalize_nick("@Foo") == "foo"
    assert validate_nick("foo_1") == "foo_1"
    parsed = parse_tiktok_url("www.tiktok.com/@x/video/111")
    assert parsed["canonical"] == "video:111"
    assert kut_for_views(1000) == 30
    assert payout_delta(0, 1000)["kut"] == 30
