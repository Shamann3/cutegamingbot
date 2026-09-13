from tiktok_earn_logic import (
    find_matches,
    hashes_from_image_bytes,
    hashes_similar,
    kut_for_views,
    normalize_nick,
    parse_tiktok_url,
    payout_delta,
    recheck_wait_text,
    thousands_from_views,
    validate_nick,
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
