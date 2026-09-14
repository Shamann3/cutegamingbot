from telegram_file_cache import (
    make_thumb_jpeg,
    photo_cache_key,
    photo_proxy_url_shape,
)
from tiktok_earn_logic import (
    COMMENT_REWARD_MAX,
    VIDEO_REWARD_MAX,
    append_case_photos,
    assert_can_approve_comments,
    comment_progress,
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
    assert short["canonical"] == "short:zmabcdef"
    tlink = parse_tiktok_url("https://www.tiktok.com/t/ZTdabcde/")
    assert tlink["canonical"] == "short:ztdabcde"
    vt = parse_tiktok_url("https://vt.tiktok.com/ZSqxKyCTB/")
    assert vt["canonical"] == "short:zsqxkyctb"
    assert vt["kind"] == "short"
    wrapped = parse_tiktok_url("вот ссылка https://vt.tiktok.com/ZSqxKyCTB/ смотрите")
    assert wrapped["canonical"] == "short:zsqxkyctb"
    noscheme = parse_tiktok_url("vt.tiktok.com/ZSqxKyCTB/")
    assert noscheme["canonical"] == "short:zsqxkyctb"
    mobile = parse_tiktok_url("https://m.tiktok.com/v/1234567890123456789.html")
    assert mobile["canonical"] == "video:1234567890123456789"
    share = parse_tiktok_url("https://www.tiktok.com/share/video/1234567890123456789")
    assert share["canonical"] == "video:1234567890123456789"
    try:
        parse_tiktok_url("https://www.tiktok.com/@cute/photo/1234567890123456789")
        assert False
    except ValueError as exc:
        assert "видео" in str(exc).lower()


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


def test_find_matches_skips_same_series_lookalikes():
    zero = "0" * 16
    eight = "00000000000000ff"
    one = "0000000000000001"
    src = {"id": "1:0", "caseId": 1, "index": 0, "ahash": zero, "dhash": zero, "phash": zero}
    same_series = {"id": "1:1", "caseId": 1, "index": 1, "ahash": eight, "dhash": eight, "phash": eight}
    other_case = {"id": "2:0", "caseId": 2, "index": 0, "ahash": one, "dhash": one, "phash": one}
    near = {"id": "1:2", "caseId": 1, "index": 2, "ahash": one, "dhash": one, "phash": one}
    matches = find_matches([src], [src, same_series, other_case, near])
    ids = {m["match"]["id"] for m in matches}
    assert "1:1" not in ids
    assert "2:0" in ids
    assert "1:2" in ids
    cross = [m for m in matches if not m["sameCase"]]
    assert all(m["similarity"] >= 94 for m in cross)


def test_payout_messages_name_the_job():
    from tiktok_earn_logic import format_comment_payout_html, format_video_payout_html

    comments = format_comment_payout_html(5, 15)
    assert "+5 кут" in comments
    assert "комментарии" in comments.lower()
    assert "15 скринов" in comments
    assert "—" not in comments
    video = format_video_payout_html(kut=6390, views=213012, kut_per_unit=30)
    assert "+6390 кут" in video
    assert "213012" in video
    assert "213 × 30" in video
    assert "видео" in video.lower()
    zero = format_video_payout_html(kut=0, views=400, kut_per_unit=30)
    assert "1000" in zero
    recheck = format_video_payout_html(
        kut=60, views=5000, kut_per_unit=30, is_recheck=True, old_views=2000, days=7
    )
    assert "доплата" in recheck.lower()
    assert "2000" in recheck


def test_photo_cache_keys_and_proxy_url_shape():
    assert photo_cache_key("AgAC_file", "thumb").startswith("thumb_")
    assert photo_cache_key("AgAC_file", "full").startswith("full_")
    assert photo_cache_key("AgAC_file", "thumb") != photo_cache_key("AgAC_file", "full")
    url = photo_proxy_url_shape("AgAC abc", "thumb")
    assert url.startswith("/admin/api/photo-proxy?")
    assert "file_id=AgAC+abc" in url or "file_id=AgAC%20abc" in url
    assert "size=thumb" in url
    assert "base64" not in url


def test_photo_records_normalize_nested_and_snake_case():
    from admin_tiktok import _photo_records

    recs = _photo_records(
        9,
        42,
        [
            {
                "file_id": "AgAC_full",
                "thumb_file_id": "AgAC_thumb",
                "hashes": {"ahash": "aa", "phash": "pp"},
            },
            {"fileId": "AgAC_b", "ahash": "bb"},
            "AgAC_plain",
        ],
        None,
    )
    assert recs[0]["fileId"] == "AgAC_full"
    assert recs[0]["thumbFileId"] == "AgAC_thumb"
    assert recs[0]["ahash"] == "aa"
    assert recs[0]["phash"] == "pp"
    assert recs[1]["fileId"] == "AgAC_b"
    assert recs[2]["fileId"] == "AgAC_plain"
    assert all("base64" not in (r["fileId"] or "") for r in recs)


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
    assert "commentRejectReasons" in settings_src
    body_src = inspect.getsource(tiktok_put_settings)
    assert "SettingsBody" in body_src
    from admin_tiktok import tiktok_get_settings, tiktok_overview

    assert "canEditRewards" in inspect.getsource(tiktok_get_settings)
    assert "canEditRewards" in inspect.getsource(tiktok_overview)


def test_incomplete_case_cannot_be_approved():
    first = append_case_photos([], [{"fileId": "one"}], 15)
    assert first["received"] == 1
    assert first["incomplete"] is True
    fifteenth = append_case_photos([{"n": i} for i in range(14)], [{"n": 14}], 15)
    assert fifteenth["complete"] is True
    try:
        assert_can_approve_comments(first["photos"], 15)
        assert False
    except ValueError as exc:
        assert "1 из 15" in str(exc)
    assert comment_progress(fifteenth["photos"], 15)["complete"] is True

    import inspect
    from admin_tiktok import approve_comment_case, reject_comment_case

    approve_src = inspect.getsource(approve_comment_case)
    assert "assert_can_approve_comments" in approve_src
    reject_src = inspect.getsource(reject_comment_case)
    assert "assert_can_approve_comments" not in reject_src
    assert "pending" in reject_src
    assert "format_photo_reject_html" in reject_src
    assert "reason_ids" in reject_src


def test_photo_reject_message_lists_selected_reasons():
    from tiktok_earn_logic import format_photo_reject_html

    text = format_photo_reject_html(["18+ контент", "Оскорбление проекта или людей"])
    assert "18+ контент" in text
    assert "Оскорбление проекта" in text
    assert "копия" not in text.lower()
    assert "<blockquote>" in text
    assert "Комментарии не приняли" in text
    try:
        format_photo_reject_html([])
        assert False
    except ValueError:
        pass


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
    assert "withdrawn" in inspect.getsource(list_comment_archive)
