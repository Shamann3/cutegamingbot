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
    from bot.funcs.tiktok_earn import format_hashtag, help_earnings_block, text_ask_nick, text_hub, text_need_nick
    assert "Тик ток" in text_hub()
    assert "cuteplayer" in text_ask_nick()
    assert "Задания" in help_earnings_block()
    assert "Напишите имя своего TikTok" in text_need_nick()
    assert "@cuteplayer" in text_need_nick()
    assert text_ask_nick() == text_need_nick()
    assert format_hashtag("тг звезды") == "#тгзвезды"
    assert format_hashtag("@CuteGamingBot") == "#CuteGamingBot"


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
    for row in kb.inline_keyboard:
        for btn in row:
            assert btn.icon_custom_emoji_id, btn.text


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
    from bot.funcs.tiktok_earn import text_photos_on_review, text_wait_expired, text_wait_link, text_wait_photos
    blobs.append(text_photos_on_review(1, 1, 15))
    blobs.append(text_photos_on_review(5, 5, 15))
    blobs.append(text_photos_on_review(1, 15, 15))
    blobs.append(text_wait_photos())
    blobs.append(text_wait_link())
    blobs.append(text_wait_expired())
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
    assert "tt:withdraw" not in dumped
    full = _kb_data(collect_keyboard(15, 15))
    assert "tt:withdraw" in full
    assert "tt:hub" in full
    assert "tt:undo_photo" not in full
    assert "tt:submit_photos" not in full

    class _Size:
        def __init__(self, file_id, width):
            self.file_id = file_id
            self.width = width

    assert pick_thumb_file_id([_Size("small", 90), _Size("mid", 320), _Size("big", 1280)]) == "mid"


def test_video_recheck_state_and_keyboard():
    from datetime import datetime, timedelta, timezone
    from bot.funcs.tiktok_earn import my_videos_keyboard, video_card_keyboard, video_recheck_state

    now = datetime.now(timezone.utc)
    waiting = video_recheck_state(now, 7)
    assert waiting["ready"] is False
    assert "через" in waiting["waitText"]
    ready = video_recheck_state(now - timedelta(days=8), 7)
    assert ready["ready"] is True
    dumped = _kb_data(video_card_keyboard({
        "id": 5, "status": "live", "recheckPending": False, "recheckReady": True,
    }))
    assert "tt:recheck:5" in dumped
    waiting_kb = _kb_data(video_card_keyboard({
        "id": 4, "status": "live", "recheckPending": False, "recheckReady": False,
    }))
    assert "tt:recheck:4" not in waiting_kb
    items = [{"id": i, "status": "live", "paidKut": 30} for i in range(1, 12)]
    page0 = _kb_data(my_videos_keyboard(items, page=0))
    assert "tt:vpage:1" in page0
    assert "tt:vid:1" in page0
    assert "tt:vid:11" not in page0
    page1 = _kb_data(my_videos_keyboard(items, page=1))
    assert "tt:vid:11" in page1
    assert "tt:vpage:0" in page1
    page_labels = " ".join(btn.text for row in my_videos_keyboard(items, page=0).inline_keyboard for btn in row)
    assert "Дальше" in page_labels
    assert page_labels.count("Назад") == 1


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
    assert "tt:withdraw" in dumped
    assert "tt:hub" in dumped
    assert "tt:submit_photos" not in dumped
    assert "tt:send_photos" not in dumped
    assert "tt:undo_photo" not in dumped


def test_direction_then_work_on_same_screen():
    from bot.funcs.tiktok_earn import comments_keyboard, hub_keyboard, text_hub, text_videos, videos_keyboard

    hub = text_hub({"commentReward": 12, "kutPerUnit": 40})
    assert "Выберите" in hub
    assert "Настройки" not in hub
    dumped = _kb_data(hub_keyboard())
    assert dumped.split()[:2] == ["tt:comments", "tt:videos"]
    assert "tt:nicks" in dumped
    assert "tt:my_videos" in dumped
    work = _kb_data(comments_keyboard(can_send=True, count=3, needed=15, waiting=False))
    assert "tt:submit_photos" not in work
    assert "tt:undo_photo" in work
    assert "tt:hub" in work
    assert "tt:nicks" in _kb_data(videos_keyboard([]))
    assert "tt:hub" in _kb_data(videos_keyboard([]))
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
    assert "TT_WITHDRAW" in src
    assert "withdraw_comment_case" in src


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
        text_case_withdrawn,
        text_videos,
        text_wait_expired,
        text_wait_link,
        text_wait_photos,
        text_wait_title,
        collect_text,
        text_done_nick_added,
        text_done_nick_changed,
        text_done_video_sent,
        text_my_videos,
        text_video_card,
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
        text_wait_title(),
        text_wait_expired(),
        text_done_nick_added("cuteplayer", ["cuteplayer"]),
        text_done_nick_changed("oldnick", "newnick"),
        text_done_video_sent("https://vt.tiktok.com/ZSqxKyCTB/"),
        text_my_videos([]),
        text_video_card({"id": 1, "url": "https://vt.tiktok.com/ZSqxKyCTB/", "status": "live", "lastViews": 2500, "paidKut": 60, "lastPaidThousands": 2, "kutPerUnit": 30}),
        text_press_send_photos(),
        text_press_send_link(),
        text_wait_expired(),
        text_case_withdrawn(),
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
    assert looks_like_tiktok_url("https://vt.tiktok.com/ZSqxKyCTB/")
    assert looks_like_tiktok_url("смотрите https://vt.tiktok.com/ZSqxKyCTB/")
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
    assert "nick_wait_keyboard" in funcs
    assert "_reprompt" in src

    ask = text_ask_nick()
    assert "Напишите имя своего TikTok" in ask
    assert EXAMPLE_NICK in ask
    need = text_need_nick("comments")
    assert "Напишите имя своего TikTok" in need
    assert EXAMPLE_NICK in need
    assert EXAMPLE_COMMENT in text_comments({})
    assert EXAMPLE_VIDEO_URL in text_videos({})
    assert "vt.tiktok.com" in text_videos({})
    assert "<b>1.</b>" in text_videos({})
    assert "<b>2.</b>" in text_videos({})
    assert "<blockquote><code>" not in text_videos({})
    comments = text_comments({})
    videos = text_videos({})
    assert "хештег" in comments
    assert "Тег ролика" not in comments
    assert "<blockquote>" in comments
    assert "<blockquote>" in videos
    assert "Делайте по порядку" in comments
    assert "Делайте по порядку" in videos
    for blob in (ask, need, comments, videos):
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
    assert should_skip_main_text_handler(uid, chat_type="private")
    assert not should_skip_main_text_handler(uid, chat_type="group")
    assert not should_skip_main_text_handler(uid, chat_type="supergroup")
    assert not should_skip_main_text_handler(uid, chat_type="channel")
    assert handler_would_accept_text(uid, "Ooooo")
    assert handler_would_accept_text(uid, "Cutetestjerichocute")
    assert message_matches_wait_text(_Msg(uid, "Ooooo"))
    assert not message_matches_wait_text(_Msg(uid, "Ooooo", chat_type="group"))
    assert not message_matches_wait_text(_Msg(uid, "Ooooo", chat_type="supergroup"))
    assert not message_matches_wait_text(_Msg(uid, "Ooooo", chat_type="channel"))
    assert not handler_would_accept_text(uid, "/start")
    assert not handler_would_accept_text(uid, "Ooooo", chat_type="group")
    clear_wait(uid)
    assert not handler_would_accept_text(uid, "Cutetestjerichocute")

    begin_wait(uid, "photos", after="comments")
    assert is_awaiting_photos(uid)
    assert message_matches_wait_photo(_Msg(uid, photo=["x"]))
    assert not message_matches_wait_photo(_Msg(uid, photo=["x"], chat_type="group"))
    assert not message_matches_wait_photo(_Msg(uid, photo=["x"], chat_type="supergroup"))
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
    assert message_matches_wait_text(_ReplyMsg(uid, "Ooooo", reply_mid=999))
    clear_wait(uid)

    begin_wait(uid, "photos", after="comments", prompt_message_id=100)
    assert message_matches_wait_photo(_ReplyMsg(uid, photo=["x"], reply_mid=999))
    assert message_matches_wait_photo(_Msg(uid, photo=["x"]))
    clear_wait(uid)


def test_tiktok_wait_never_matches_group_chats():
    from bot.funcs.tiktok_earn import (
        begin_wait,
        clear_wait,
        message_matches_wait_noise,
        message_matches_wait_photo,
        message_matches_wait_text,
        should_skip_main_text_handler,
        should_skip_photo_handler,
    )

    class _User:
        def __init__(self, uid):
            self.id = uid

    class _Chat:
        def __init__(self, typ):
            self.type = typ

    class _Msg:
        def __init__(self, uid, text="", chat_type="private", photo=None, document=None):
            self.from_user = _User(uid)
            self.chat = _Chat(chat_type)
            self.text = text
            self.photo = photo
            self.document = document

    uid = 980044
    clear_wait(uid)
    begin_wait(uid, "nick", after="comments")
    assert message_matches_wait_text(_Msg(uid, "cuteplayer"))
    for typ in ("group", "supergroup", "channel"):
        assert not message_matches_wait_text(_Msg(uid, "cuteplayer", chat_type=typ))
        assert not should_skip_main_text_handler(uid, chat_type=typ)
    assert should_skip_main_text_handler(uid, chat_type="private")

    begin_wait(uid, "photos", after="comments")
    assert message_matches_wait_photo(_Msg(uid, photo=["x"]))
    assert message_matches_wait_noise(_Msg(uid, "просто текст"))
    for typ in ("group", "supergroup", "channel"):
        assert not message_matches_wait_photo(_Msg(uid, photo=["x"], chat_type=typ))
        assert not message_matches_wait_noise(_Msg(uid, "просто текст", chat_type=typ))
        assert not should_skip_photo_handler(uid, chat_type=typ)
        assert not should_skip_main_text_handler(uid, chat_type=typ)
    assert should_skip_photo_handler(uid, chat_type="private")
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
    assert "_arm_wait_on_message" in handler
    assert "nick_wait_keyboard" in handler
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
    assert "expires_at" in funcs
    assert "WAIT_TTL_SECONDS" in funcs
    assert "text_wait_expired" in funcs
    assert "expire_wait_if_needed" in handler
    assert "message_is_private_chat" in main_src
    assert "is_private_chat_type" in main_src
    assert "should_skip_photo_handler" in Path("bot/handlers/admin_panel.py").read_text(encoding="utf-8")
    assert "if not _private(message)" in handler


def test_admin_photo_proxy_client_uses_jwt_query_and_thumb():
    client = Path("admin/src/lib/adminClient.js").read_text(encoding="utf-8")
    photo = Path("admin/src/components/TgPhoto.jsx").read_text(encoding="utf-8")
    section = Path("admin/src/pages/sections/TikTokSection.jsx").read_text(encoding="utf-8")
    assert "export function getPhotoProxyUrl" in client
    assert "size=${kind}" in client
    assert "&t=${encodeURIComponent(token" in client
    assert "loadTgPhotoUrl" in photo
    assert "getPhotoProxyUrl(fileId, kind)" in photo
    assert "loadTgPhotoUrl" in section
    assert "size=\"thumb\"" in section or "size='thumb'" in section
    css = Path("admin/src/styles/tiktok.css").read_text(encoding="utf-8")
    assert "aspect-ratio: 1 / 1" not in css
    assert "tt-shot-empty" not in section
    assert "nickBreakdown" not in section
    assert "Следующее · конец" not in section
    assert "readonly={tab === 'archive'}" in section
    assert "VideoWorkspace" in section
    assert "Открыть улику в TikTok" in section
    assert "busyRef.current" in section


def test_wait_expires_after_five_minutes_and_keeps_escape():
    from datetime import datetime, timedelta, timezone

    from bot.funcs.tiktok_earn import (
        CANCEL_HINT,
        WAIT_TTL_SECONDS,
        begin_wait,
        clear_wait,
        handler_would_accept_text,
        is_cancel_input,
        is_wait_expired,
        message_matches_wait_photo,
        message_matches_wait_text,
        should_skip_main_text_handler,
        text_link_screen,
        text_need_nick,
        text_photos_on_review,
        text_wait_expired,
        text_wait_link,
        text_wait_photos,
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

    assert WAIT_TTL_SECONDS == 300
    assert is_cancel_input("Назад")
    assert is_cancel_input("«Завершить»")
    uid = 980033
    clear_wait(uid)
    rec = begin_wait(uid, "nick", after="comments")
    assert rec.get("expires_at")
    assert not is_wait_expired(uid)
    assert message_matches_wait_text(_Msg(uid, "Назад"))
    assert message_matches_wait_text(_Msg(uid, "Завершить"))
    assert message_matches_wait_text(_Msg(uid, "cuteplayer"))

    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    begin_wait(uid, "nick", after="comments", extra={"expires_at": past})
    assert is_wait_expired(uid)
    assert not handler_would_accept_text(uid, "cuteplayer")
    assert not message_matches_wait_text(_Msg(uid, "cuteplayer"))
    assert not should_skip_main_text_handler(uid)
    begin_wait(uid, "photos", after="comments", extra={"expires_at": past})
    assert not message_matches_wait_photo(_Msg(uid, photo=["x"]))
    clear_wait(uid)

    expiry = text_wait_expired()
    assert "Срок ввода истёк" in expiry
    assert "Попробуйте повторно загрузить доказательства" in expiry
    assert "<b>" in expiry and "<i>" in expiry
    assert "—" not in expiry
    for blob in (
        text_need_nick(),
        text_need_nick("comments", error="Этот ник уже занят другим игроком"),
        text_wait_photos(),
        text_wait_photos(3, 15),
        text_wait_link(),
        text_link_screen("Это не ссылка TikTok."),
        text_photos_on_review(1, 1, 15),
    ):
        assert "Назад" in blob
        assert "Завершить" in blob
        assert CANCEL_HINT in blob
        assert "Ответьте" in blob or "отправьте" in blob.lower()
        assert "—" not in blob


def test_video_title_then_link_and_retry_flow():
    from bot.funcs.tiktok_earn import (
        MODE_WAIT_TITLE,
        TT_HUB,
        TT_RETRY_VIDEO,
        WAIT_TITLE,
        clip_button_text,
        done_keyboard,
        my_videos_keyboard,
        text_done_video_sent,
        text_my_videos,
        text_video_card,
        text_wait_title,
        text_videos,
        video_card_keyboard,
    )

    assert MODE_WAIT_TITLE == "await_video_title"
    assert WAIT_TITLE == "title"
    title_screen = text_wait_title()
    assert "название" in title_screen.lower()
    assert "ссылку пришлёте" in title_screen.lower() or "следующим" in title_screen.lower()
    assert "—" not in title_screen
    assert "cuteplayer" in text_videos({}) or "Обзор" in text_videos({})
    done = " ".join(btn.text for row in done_keyboard(after="mine").inline_keyboard for btn in row)
    dumped = " ".join(btn.callback_data or "" for row in done_keyboard(after="hub").inline_keyboard for btn in row)
    assert "В главное меню" in done
    assert "Тик ток" not in done
    assert TT_HUB in dumped
    card = text_video_card({
        "id": 9,
        "title": "Обзор бота",
        "url": "https://vt.tiktok.com/ZSqxKyCTB/",
        "status": "rejected",
        "lastViews": 0,
        "paidKut": 0,
    })
    assert "Обзор бота" in card
    assert "vt.tiktok.com" in card
    retry = " ".join(btn.callback_data or "" for row in video_card_keyboard({"id": 9, "status": "rejected"}).inline_keyboard for btn in row)
    assert f"{TT_RETRY_VIDEO}9" in retry
    labels = " ".join(btn.text for row in my_videos_keyboard([
        {"id": 3, "title": "Мой обзор CuteGamingBot", "status": "pending"},
    ], page=0).inline_keyboard for btn in row)
    assert "Мой обзор CuteGamingBot" in labels
    assert clip_button_text("x" * 80).endswith("...")
    sent = text_done_video_sent("https://vt.tiktok.com/ZSqxKyCTB/", "Обзор бота")
    assert "Обзор бота" in sent
    assert "Ваши ролики" in text_my_videos([]) or "пусто" in text_my_videos([]).lower()
    handler = Path("bot/handlers/tiktok_earn.py").read_text(encoding="utf-8")
    funcs = Path("bot/funcs/tiktok_earn.py").read_text(encoding="utf-8")
    assert "WAIT_TITLE" in handler
    assert "replaceVideoId" in handler
    assert "В главное меню" in funcs
    assert "validate_video_title" in handler

