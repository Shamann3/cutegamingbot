import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import re

from tiktok_earn_logic import (  # noqa: E402
    BARNUM_REJECTS,
    COMMENT_REWARD_MAX,
    COMMENT_REWARD_MIN,
    VIDEO_REWARD_MAX,
    VIDEO_REWARD_MIN,
    append_case_photos,
    assert_can_approve_comments,
    comment_progress,
    kut_for_views,
    normalize_nick,
    parse_tiktok_url,
    payout_delta,
    ru_gone_verb,
    ru_screenshot_word,
    validate_comment_reward,
    validate_nick,
    validate_video_reward,
    wrap_barnum_html,
)

_TY_RE = re.compile(
    r"(?<![А-Яа-яA-Za-z])(ты|тебя|тебе|тобой|твой|твоя|твоё|твое|твои|твоих|твоим|твоему|твоей)(?![А-Яа-яA-Za-z])",
    re.IGNORECASE,
)


def test_nick_taken_message_is_defined():
    from bot.funcs import tiktok_earn as tt
    src = Path(tt.__file__).read_text(encoding="utf-8")
    assert "Этот ник уже занят другим игроком" in src
    assert "Можно не больше" in src
    assert "уже на проверке" in src
    assert "напишите имя своего TikTok" in src
    assert "require_nicks" in src
    assert "INSERT INTO tiktok_comment_cases" in src
    assert "append_case_photos" in src


def test_bot_texts_match_plan():
    from bot.funcs.tiktok_earn import help_earnings_block, text_ask_nick, text_hub, text_need_nick
    assert "Тик ток" in text_hub()
    assert "cuteplayer" in text_ask_nick()
    assert "Задания" in help_earnings_block()
    assert "Напишите имя своего TikTok" in text_need_nick()
    assert "@cuteplayer" in text_need_nick()
    assert text_ask_nick() == text_need_nick()


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
    from bot.funcs.tiktok_earn import text_photos_on_review, text_wait_link, text_wait_photos
    blobs.append(text_photos_on_review(1, 1, 15))
    blobs.append(text_photos_on_review(5, 5, 15))
    blobs.append(text_photos_on_review(1, 15, 15))
    blobs.append(text_wait_photos())
    blobs.append(text_wait_link())
    help_src = Path("bot/funcs/help.py").read_text(encoding="utf-8")
    tiktok_help = help_src.split("<b>TikTok</b>")[1].split("<b>Промокоды</b>")[0]
    blobs.append(tiktok_help)
    for blob in blobs:
        assert "—" not in blob
        assert "–" not in blob
    assert "<b>" in text_hub()
    assert "<i>" in text_hub()
    assert "<i>" in text_comments({})
    assert "<i>" in text_videos({})


def _kb_data(kb) -> str:
    return " ".join(btn.callback_data or "" for row in kb.inline_keyboard for btn in row)


def test_collect_progress_and_undo_available_before_full():
    from bot.funcs.tiktok_earn import collect_keyboard, collect_text, pick_thumb_file_id

    text = collect_text(7, 15, ["cuteplayer"])
    assert "7 из 15" in text
    assert "Ещё 8" in text
    assert "@cuteplayer" in text
    dumped = _kb_data(collect_keyboard(7, 15))
    assert "tt:undo_photo" in dumped
    assert "tt:submit_photos" not in dumped
    full = _kb_data(collect_keyboard(15, 15))
    assert "tt:undo_photo" in full
    assert "tt:submit_photos" in full

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


def test_bot_texts_follow_settings_rewards():
    from bot.funcs.tiktok_earn import comments_keyboard, text_comments, text_hub, text_videos

    comments = text_comments({"commentReward": 17, "photosRequired": 15})
    assert "17" in comments
    assert "5 кут" not in comments
    videos = text_videos({"kutPerUnit": 42, "viewsPerUnit": 1000})
    assert "42" in videos
    assert "30 кут" not in videos
    hub = text_hub({"commentReward": 88, "kutPerUnit": 9, "photosRequired": 15})
    assert "88" in hub
    assert "9" in hub
    dumped = _kb_data(comments_keyboard(can_send=True, count=15, needed=15, complete=True))
    assert "tt:submit_photos" in dumped
    assert "tt:send_photos" not in dumped


def test_direction_then_work_on_same_screen():
    from bot.funcs.tiktok_earn import comments_keyboard, hub_keyboard, text_hub, text_videos, videos_keyboard

    hub = text_hub({"commentReward": 12, "kutPerUnit": 40})
    assert "Выберите" in hub
    assert "Настройки" not in hub
    dumped = _kb_data(hub_keyboard())
    assert dumped.split()[:2] == ["tt:comments", "tt:videos"]
    assert "tt:nicks" not in dumped
    work = _kb_data(comments_keyboard(can_send=True, count=3, needed=15, waiting=False))
    assert "tt:submit_photos" not in work
    assert "tt:undo_photo" in work
    assert "tt:hub" in work
    assert "tt:nicks" in _kb_data(videos_keyboard([]))
    assert "cuteplayer" in text_videos({"kutPerUnit": 40})


def test_reward_caps_and_payout_use_stored_value():
    assert validate_comment_reward(17) == 17
    assert validate_video_reward(40) == 40
    try:
        validate_comment_reward(0)
        assert False
    except ValueError as exc:
        assert str(COMMENT_REWARD_MIN) in str(exc)
    try:
        validate_comment_reward(COMMENT_REWARD_MAX + 1)
        assert False
    except ValueError:
        pass
    try:
        validate_video_reward(VIDEO_REWARD_MAX + 1)
        assert False
    except ValueError:
        pass
    assert VIDEO_REWARD_MIN == 1
    assert payout_delta(1000, 3500, kut_per_unit=40)["kut"] == 80
    assert kut_for_views(2500, kut_per_unit=40) == 80


def test_shared_url_and_payout():
    assert normalize_nick("@Foo") == "foo"
    assert validate_nick("foo_1") == "foo_1"
    parsed = parse_tiktok_url("www.tiktok.com/@x/video/111")
    assert parsed["canonical"] == "video:111"
    assert kut_for_views(1000) == 30
    assert payout_delta(0, 1000)["kut"] == 30


def test_navigation_callbacks_stay_on_path():
    from pathlib import Path

    src = Path("bot/handlers/tiktok_earn.py").read_text(encoding="utf-8")
    assert "F.data == tt.TT_COMMENTS" in src
    assert "F.data == tt.TT_VIDEOS" in src
    assert "await show_comments" in src
    assert "await show_videos" in src
    assert "MODE_WAIT_LINK" in src
    assert 'after": "comments"' in src or '"after": "comments"' in src
    assert "ChatType.PRIVATE" in src
    assert "dp.message.register" in src
    assert "message_matches_wait_text" in src
    assert "get_pending_comment_case" in src
    assert "text_photos_on_review" in src


def test_partial_case_logic_and_approve_gate():
    first = append_case_photos([], [{"fileId": "a"}], 15)
    assert first["added"] == 1
    assert first["received"] == 1
    assert first["incomplete"] is True
    assert first["complete"] is False
    mid = append_case_photos(first["photos"], [{"fileId": "b"}, {"fileId": "c"}], 15)
    assert mid["received"] == 3
    assert mid["added"] == 2
    done = append_case_photos([{"i": n} for n in range(14)], [{"i": 14}], 15)
    assert done["complete"] is True
    assert done["received"] == 15
    extra = append_case_photos(done["photos"], [{"i": 99}], 15)
    assert extra["added"] == 0
    assert extra["received"] == 15
    try:
        assert_can_approve_comments([1, 2, 3], 15)
        assert False
    except ValueError as exc:
        assert "3 из 15" in str(exc)
    assert assert_can_approve_comments(list(range(15)), 15)["complete"] is True
    assert comment_progress([], 15)["incomplete"] is True


def test_review_copy_uses_vy_and_counts():
    from bot.funcs.tiktok_earn import text_photos_on_review

    one = text_photos_on_review(1, 1, 15)
    assert "1 скриншот ушёл на проверку" in one
    assert "1 из 15" in one
    three = text_photos_on_review(3, 3, 15)
    assert "3 скриншота ушли на проверку" in three
    five = text_photos_on_review(5, 5, 15)
    assert "5 скриншотов ушли на проверку" in five
    full = text_photos_on_review(1, 15, 15)
    assert "15 из 15" in full
    assert "Ждём решение" in full
    assert ru_screenshot_word(1) == "скриншот"
    assert ru_gone_verb(1) == "ушёл"


def test_player_tiktok_copy_is_formal_vy():
    from bot.funcs.tiktok_earn import (
        help_earnings_block,
        text_ask_nick,
        text_comments,
        text_hub,
        text_need_nick,
        text_nicks,
        text_nick_required_alert,
        text_photos_on_review,
        text_press_send_link,
        text_press_send_photos,
        text_videos,
        text_wait_link,
        text_wait_photos,
        collect_text,
    )

    blobs = [
        text_hub({"commentReward": 17, "kutPerUnit": 40}),
        text_comments({"commentReward": 17}),
        text_videos({"kutPerUnit": 40}),
        text_need_nick("comments"),
        text_need_nick("videos"),
        text_ask_nick(),
        text_nicks(["cuteplayer"], locked=False),
        text_nicks(["cuteplayer"], locked=True),
        help_earnings_block(),
        collect_text(3, 15, ["cuteplayer"]),
        text_photos_on_review(1, 1, 15),
        text_nick_required_alert(),
        text_wait_photos(),
        text_wait_link(),
        text_press_send_photos(),
        text_press_send_link(),
    ]
    help_src = Path("bot/funcs/help.py").read_text(encoding="utf-8")
    blobs.append(help_src.split("<b>TikTok</b>")[1].split("<b>Промокоды</b>")[0])
    blobs.extend(BARNUM_REJECTS)
    blobs.append(wrap_barnum_html("Проверка не сложилась."))
    handler = Path("bot/handlers/tiktok_earn.py").read_text(encoding="utf-8")
    for blob in blobs:
        assert "—" not in blob
        hit = _TY_RE.search(blob)
        assert hit is None, f"informal: {hit.group(0)} in {blob[:80]}"
    assert "Выберите" in text_hub()
    assert "Напишите имя своего TikTok" in text_need_nick()
    assert "копия" not in "".join(BARNUM_REJECTS).lower()


def test_wait_modes_photo_ignored_until_button():
    from bot.funcs.tiktok_earn import (
        EXAMPLE_COMMENT,
        EXAMPLE_NICK,
        EXAMPLE_VIDEO_URL,
        MODE_COMMENTS,
        MODE_WAIT_PHOTOS,
        PHOTO_WAIT_MODES,
        comments_keyboard,
        looks_like_tiktok_url,
        text_ask_nick,
        text_comments,
        text_need_nick,
        text_press_send_photos,
        text_videos,
        videos_keyboard,
    )

    idle = _kb_data(comments_keyboard(waiting=False, count=0, needed=15))
    assert idle.count("tt:hub") >= 1
    waiting = _kb_data(comments_keyboard(waiting=True, count=2, needed=15))
    assert "tt:undo_photo" in waiting
    assert "tt:hub" in waiting
    assert "tt:send_link" not in _kb_data(videos_keyboard([], waiting=False))
    assert MODE_WAIT_PHOTOS in PHOTO_WAIT_MODES
    assert MODE_COMMENTS not in PHOTO_WAIT_MODES
    assert looks_like_tiktok_url(EXAMPLE_VIDEO_URL)
    assert looks_like_tiktok_url("https://vm.tiktok.com/ZMabcdef/")
    assert not looks_like_tiktok_url("просто текст")
    assert "Сначала нажмите кнопку" in text_press_send_photos()

    src = Path("bot/handlers/tiktok_earn.py").read_text(encoding="utf-8")
    funcs = Path("bot/funcs/tiktok_earn.py").read_text(encoding="utf-8")
    assert "dp.message.register" in src
    assert "message_matches_wait_text" in src
    assert "begin_wait" in funcs
    assert "PHOTO_WAIT_MODES" in funcs
    assert "MODE_NEED_NICK" in src
    assert "wait_photos" in funcs
    assert "ForceReply" in src
    assert "_reprompt" in src

    ask = text_ask_nick()
    assert "Напишите имя своего TikTok" in ask
    assert EXAMPLE_NICK in ask
    need = text_need_nick("comments")
    assert "Напишите имя своего TikTok" in need
    assert EXAMPLE_NICK in need
    assert EXAMPLE_COMMENT in text_comments({})
    assert EXAMPLE_VIDEO_URL in text_videos({})
    for blob in (ask, need, text_comments({}), text_videos({})):
        assert "<code>" in blob
        assert "—" not in blob


def test_gift_like_wait_flag_lets_handler_accept_text():
    from bot.funcs.tiktok_earn import (
        begin_wait,
        clear_wait,
        handler_would_accept_text,
        is_awaiting_photos,
        is_awaiting_text,
        message_matches_wait_photo,
        message_matches_wait_text,
        should_skip_main_text_handler,
    )

    class _User:
        def __init__(self, uid):
            self.id = uid

    class _Chat:
        def __init__(self, typ):
            self.type = typ

    class _Msg:
        def __init__(self, uid, text="", chat_type="private", photo=None):
            self.from_user = _User(uid)
            self.chat = _Chat(chat_type)
            self.text = text
            self.photo = photo

    uid = 980011
    clear_wait(uid)
    assert not handler_would_accept_text(uid, "Ooooo")
    assert not message_matches_wait_text(_Msg(uid, "Cutetestjerichocute"))
    assert not should_skip_main_text_handler(uid)

    begin_wait(uid, "nick", after="comments")
    assert is_awaiting_text(uid)
    assert should_skip_main_text_handler(uid)
    assert handler_would_accept_text(uid, "Ooooo")
    assert handler_would_accept_text(uid, "Cutetestjerichocute")
    assert message_matches_wait_text(_Msg(uid, "Ooooo"))
    assert not handler_would_accept_text(uid, "/start")
    assert not handler_would_accept_text(uid, "Ooooo", chat_type="group")
    clear_wait(uid)
    assert not handler_would_accept_text(uid, "Cutetestjerichocute")

    begin_wait(uid, "photos", after="comments")
    assert is_awaiting_photos(uid)
    assert message_matches_wait_photo(_Msg(uid, photo=["x"]))
    assert not message_matches_wait_photo(_Msg(uid, photo=["x"], chat_type="group"))
    assert not message_matches_wait_text(_Msg(uid, "просто текст"))
    clear_wait(uid)
    assert not message_matches_wait_photo(_Msg(uid, photo=["x"]))

    class _Reply:
        def __init__(self, mid):
            self.message_id = mid

    class _ReplyMsg(_Msg):
        def __init__(self, uid, text="", chat_type="private", photo=None, reply_mid=None):
            super().__init__(uid, text, chat_type, photo)
            self.reply_to_message = _Reply(reply_mid) if reply_mid else None

    begin_wait(uid, "nick", after="comments", prompt_message_id=100)
    assert message_matches_wait_text(_ReplyMsg(uid, "Ooooo", reply_mid=100))
    assert message_matches_wait_text(_Msg(uid, "Ooooo"))
    assert not message_matches_wait_text(_ReplyMsg(uid, "Ooooo", reply_mid=999))
    clear_wait(uid)


def test_invalid_nick_error_stays_on_same_screen():
    from bot.funcs.tiktok_earn import text_need_nick
    try:
        validate_nick("!")
        raise AssertionError("expected invalid nick")
    except ValueError as exc:
        screen = text_need_nick("comments", error=str(exc))
        assert "латиница" in str(exc)
        assert str(exc) in screen
        assert "Напишите имя своего TikTok" in screen
        assert "@cuteplayer" in screen


def test_button_and_attach_use_gift_like_wait():
    handler = Path("bot/handlers/tiktok_earn.py").read_text(encoding="utf-8")
    funcs = Path("bot/funcs/tiktok_earn.py").read_text(encoding="utf-8")
    main_src = Path("main.py").read_text(encoding="utf-8")
    assert "begin_wait" in funcs
    assert "awaiting" in funcs
    assert "arm_wait" in handler
    assert "_arm_nick_screen" in handler
    assert "dp.message.register" in handler
    assert "SkipHandler" in main_src
    assert "should_skip_main_text_handler" in main_src
    assert "ForceReply" in handler
    assert "ForceReply(selective=True)" in handler
    assert "_reprompt" in handler
    assert "process_tiktok_wait_text" in main_src
    assert "process_user_gift_recipient" in main_src
    assert main_src.index("async def process_tiktok_wait_text") < main_src.index(
        "async def add_firstname_to_usercheck_balance"
    )
    assert main_src.index("async def process_user_gift_recipient") < main_src.index(
        "async def process_tiktok_wait_text"
    )
    assert "prompt_message_id" in funcs
    assert "persist_prompt" in funcs
    assert "is_cancel_input" in funcs
