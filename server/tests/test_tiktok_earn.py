from telegram_file_cache import (
    make_thumb_jpeg,
    photo_cache_key,
    photo_proxy_url_shape,
)
from tiktok_earn_logic import (
    COMMENT_REWARD_MAX,
    VIDEO_REWARD_MAX,
    find_matches,
    hashes_from_image_bytes,
    hashes_similar,
    kut_for_views,
    next_queue_item,
    normalize_nick,
    parse_tiktok_url,
    payout_delta,
    pick_barnum,
    recheck_wait_text,
    thousands_from_views,
    validate_comment_reward,
    validate_nick,
    validate_video_reward,
)


def test_normalize_and_validate_nick():
    assert normalize_nick("@CutePlayer") == "cuteplayer"
    assert normalize_nick("https://www.tiktok.com/@CutePlayer") == "cuteplayer"
    assert validate_nick("@cute_player") == "cute_player"


def test_reject_bad_nick():
    try:
        validate_nick("я")
        assert False
    except ValueError:
        pass
    try:
        validate_nick("")
        assert False
    except ValueError:
        pass


def test_parse_tiktok_video_url():
    parsed = parse_tiktok_url("https://www.tiktok.com/@cute/video/1234567890123456789")
    assert parsed["canonical"] == "video:1234567890123456789"
    assert parsed["videoId"] == "1234567890123456789"


def test_parse_short_and_vm_links():
    short = parse_tiktok_url("https://vm.tiktok.com/ZMabcdef/")
    assert short["canonical"].startswith("short:")
    tlink = parse_tiktok_url("https://www.tiktok.com/t/ZTdabcde/")
    assert tlink["canonical"].startswith("short:")


def test_reject_non_tiktok_url():
    try:
        parse_tiktok_url("https://youtube.com/watch?v=1")
        assert False
    except ValueError as exc:
        assert "TikTok" in str(exc)


def test_views_formula_and_delta():
    assert thousands_from_views(999) == 0
    assert kut_for_views(999) == 0
    assert kut_for_views(2400) == 60
    delta = payout_delta(2400, 12500)
    assert delta["oldThousands"] == 2
    assert delta["newThousands"] == 12
    assert delta["kut"] == 300


def test_delta_rejects_lower_views():
    try:
        payout_delta(2000, 500)
        assert False
    except ValueError:
        pass


def test_one_pending_rule_helper():
    from admin_tiktok import submit_comment_case
    import inspect
    src = inspect.getsource(submit_comment_case)
    assert "pending" in src
    assert "Эта пачка ещё на проверке" in src


def test_recheck_wait_text():
    assert "1 день" in recheck_wait_text(100)
    assert "7 дней" in recheck_wait_text(7 * 86400)


def test_hash_similarity_same_image():
    from PIL import Image
    import io

    img = Image.new("RGB", (64, 64), (40, 80, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    left = hashes_from_image_bytes(data)
    right = hashes_from_image_bytes(data)
    assert hashes_similar(left, right)


def test_find_matches_marks_near_duplicates():
    from PIL import Image
    import io

    def png(color):
        img = Image.new("RGB", (48, 48), color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return hashes_from_image_bytes(buf.getvalue())

    a = {"id": "1:0", "caseId": 1, "index": 0, **png((10, 10, 10))}
    b = {"id": "2:0", "caseId": 2, "index": 0, **png((11, 11, 11))}
    c = {"id": "3:0", "caseId": 3, "index": 0, **png((250, 10, 10))}
    matches = find_matches([a], [a, b, c])
    assert any(m["match"]["id"] == "2:0" for m in matches)


def test_photo_cache_keys_and_proxy_url_shape():
    assert photo_cache_key("AgAC_file", "thumb").startswith("thumb_")
    assert photo_cache_key("AgAC_file", "full").startswith("full_")
    assert photo_cache_key("AgAC_file", "thumb") != photo_cache_key("AgAC_file", "full")
    url = photo_proxy_url_shape("AgAC abc", "thumb")
    assert url.startswith("/admin/api/photo-proxy?")
    assert "file_id=AgAC+abc" in url or "file_id=AgAC%20abc" in url
    assert "size=thumb" in url
    assert "base64" not in url


def test_thumb_jpeg_is_smaller_than_source():
    from PIL import Image
    import io

    img = Image.new("RGB", (800, 600), (20, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    raw = buf.getvalue()
    thumb = make_thumb_jpeg(raw, max_edge=320)
    assert thumb[:2] == b"\xff\xd8"
    assert len(thumb) < len(raw)


def test_next_queue_item():
    items = [{"id": 3}, {"id": 7}, {"id": 11}]
    assert next_queue_item(items, 3)["id"] == 7
    assert next_queue_item(items, 11) is None
    assert next_queue_item(items, 99)["id"] == 3
    assert next_queue_item([], 1) is None


def test_pick_barnum_uses_settings_texts():
    text = pick_barnum(rng=__import__("random").Random(1), texts=["Только эта формулировка."])
    assert text == "Только эта формулировка."


def test_photo_proxy_uses_cache_and_thumb_size():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "admin_routes.py").read_text(encoding="utf-8")
    assert "load_telegram_photo" in src
    assert 'size: str = Query("full")' in src
    assert "410" in src


def test_reward_validators_and_stored_payout():
    assert validate_comment_reward(17) == 17
    assert validate_video_reward(90) == 90
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
    assert payout_delta(2000, 5000, kut_per_unit=25)["kut"] == 75
    assert kut_for_views(1999, kut_per_unit=25) == 25


def test_owner_only_reward_write_and_settings_read():
    import inspect
    from admin_tiktok import is_tiktok_rewards_owner, tiktok_put_settings, update_settings

    owner_src = inspect.getsource(is_tiktok_rewards_owner)
    assert "owner_user_ids" in owner_src
    assert "ROLE_OWNER" in owner_src
    put_src = inspect.getsource(tiktok_put_settings)
    assert "is_tiktok_rewards_owner" in put_src
    assert "403" in put_src
    assert "Награду меняет только создатель проекта" in put_src
    assert "payload.pop(\"commentReward\"" in put_src or "payload.pop('commentReward'" in put_src
    upd = inspect.getsource(update_settings)
    assert "validate_comment_reward" in upd
    assert "validate_video_reward" in upd
    assert "photos_required = int(current[\"photosRequired\"])" in upd


def test_counts_and_settings_endpoints_exist():
    import inspect
    from admin_tiktok import (
        overview_counts,
        tiktok_counts,
        tiktok_put_settings,
        update_settings,
    )

    src = inspect.getsource(overview_counts)
    assert "pendingComments" in src
    assert "pendingTotal" in src
    assert inspect.getsource(tiktok_counts).count("overview_counts") >= 1
    settings_src = inspect.getsource(update_settings)
    assert "barnumRejects" in settings_src
    assert "rejectReasons" in settings_src
    body_src = inspect.getsource(tiktok_put_settings)
    assert "SettingsBody" in body_src
    from admin_tiktok import tiktok_get_settings, tiktok_overview

    assert "canEditRewards" in inspect.getsource(tiktok_get_settings)
    assert "canEditRewards" in inspect.getsource(tiktok_overview)


def test_comment_list_is_light_and_paginated():
    import inspect
    from admin_tiktok import list_comment_archive, list_comment_cases, tiktok_comments

    from admin_tiktok import _library_photos

    src = inspect.getsource(list_comment_cases)
    assert "light" in src
    assert "OFFSET" in src
    assert "LIMIT 200" in inspect.getsource(_library_photos)
    assert "limit" in inspect.getsource(tiktok_comments)
    assert "OFFSET" in inspect.getsource(list_comment_archive)
