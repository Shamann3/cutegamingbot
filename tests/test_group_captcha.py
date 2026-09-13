# -*- coding: utf-8 -*-
import random

from bot.funcs.group_captcha import (
    EMOJI,
    PASS_ALERT,
    SCHEMA_SQL,
    VARIANT_LABELS,
    answer_callback_data,
    build_challenge,
    card_plain_and_entities,
    check_sign,
    disable_callback_data,
    emoji,
    is_correct_pick,
    parse_answer_callback,
    parse_disable_callback,
    parse_premium_emoji,
    pick_variant,
    sign_parts,
    text_outside_tg_emoji,
)


def test_pass_alert_is_set():
    assert "пройдена" in PASS_ALERT.lower()
    assert "вы" in PASS_ALERT.lower()


def test_schema_is_one_statement_each():
    assert len(SCHEMA_SQL) >= 8
    for stmt in SCHEMA_SQL:
        body = stmt.strip().rstrip(";")
        assert body.count(";") == 0
        assert body.upper().startswith("CREATE")


def test_parse_premium_emoji_from_tag():
    item = parse_premium_emoji("<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji>")
    assert item.emoji_id == "5472164874886846699"
    assert "5472164874886846699" in item.as_html()
    assert "<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji>" == item.as_html()
    assert "\u2060" not in item.as_html()


def test_card_uses_premium_tags_not_raw_faces():
    faces = {emoji(k).face for k in ("shield", "fire", "diamond", "gift", "star", "dollar")}
    for i in range(20):
        card = build_challenge(rng=random.Random(i + 9))
        text = card.get("text") or ""
        assert "<tg-emoji emoji-id='" in text
        visible = text_outside_tg_emoji(text)
        for face in faces:
            if face and face in visible:
                raise AssertionError(f"обычный эмодзи {face!r} оказался вне <tg-emoji>")
        markup = __import__("bot.funcs.group_captcha", fromlist=["build_markup"]).build_markup(
            3, -100, card,
        )
        for btn in markup.inline_keyboard[0]:
            assert btn.text.strip() == ""
            assert getattr(btn, "icon_custom_emoji_id", None)
            for face in faces:
                assert face not in (btn.text or "")


def test_all_catalog_tags_have_ids():
    for key, raw in EMOJI.items():
        item = emoji(key)
        assert item.emoji_id.isdigit(), key
        assert len(item.emoji_id) >= 5, key
        assert item.face, key
        html = item.as_html()
        assert f"emoji-id='{item.emoji_id}'" in html
        assert item.face in html
        assert "\u2060" not in html


def test_variant_1_target_and_shuffle_change():
    seen_correct = set()
    seen_order = set()
    for i in range(40):
        card = build_challenge(1, rng=random.Random(i + 3))
        assert card["variant"] == 1
        assert set(card["options"]) == {"shield", "fire", "diamond"}
        assert card["correct"] in card["options"]
        seen_correct.add(card["correct"])
        seen_order.add(tuple(card["options"]))
        assert emoji(card["correct"]).emoji_id in card["text"]
        assert "5391270106464539040" in card["text"]
    assert len(seen_correct) == 3
    assert len(seen_order) > 1


def test_answers_are_underlined_and_card_is_bold():
    from types import SimpleNamespace
    from bot.funcs.group_captcha import card_html

    card = build_challenge(2, rng=random.Random(2))
    assert f"<u>{card['color']}</u>" in card["text"]
    html = card_html(card, SimpleNamespace(id=1, full_name="Анна", first_name="Анна", is_bot=False))
    assert "Это капча." in html
    assert "писать в группе" in html
    assert "5389099803655305880" in html
    assert "5213205860498549992" in html
    assert "<b>Это капча.</b>" in html
    assert "<b>Нажмите" in html
    assert html.endswith("</b>")
    assert "<u>" in html
    # вложенный <b> вокруг mention ломает parse entities у Telegram
    assert not html.startswith("<b><a ")


def test_variant_2_color_word_matches_correct():
    words = {"red": "красный", "green": "зелёный", "blue": "синий"}
    seen = set()
    for i in range(24):
        card = build_challenge(2, rng=random.Random(100 + i))
        assert card["correct"] in words
        assert words[card["correct"]] in card["text"]
        assert set(card["options"]) == {"red", "green", "blue"}
        seen.add(card["correct"])
    assert seen == {"red", "green", "blue"}


def test_variant_3_prefix_is_the_answer():
    for i in range(20):
        card = build_challenge(3, rng=random.Random(200 + i))
        assert card["correct"] in {"gift", "star", "dollar"}
        assert card["prefix_id"] == emoji(card["correct"]).emoji_id
        assert set(card["options"]) == {"gift", "star", "dollar"}


def test_variant_4_and_6_rotate_task():
    asks4, asks6 = set(), set()
    for i in range(30):
        c4 = build_challenge(4, rng=random.Random(300 + i))
        c6 = build_challenge(6, rng=random.Random(400 + i))
        asks4.add(c4["ask"])
        asks6.add(c6["mood"])
        assert is_correct_pick(c4, c4["correct"])[0] == "pass"
        assert is_correct_pick(c4, "nope")[0] == "fail"
    assert len(asks4) == 3
    assert len(asks6) == 3
    assert 8 not in VARIANT_LABELS
    assert all(pick_variant(random.Random(i)) != 8 for i in range(80))


def test_variant_5_keeps_left_right_order():
    seen = set()
    for i in range(16):
        card = build_challenge(5, rng=random.Random(600 + i))
        assert card["options"] == ["left", "right"]
        seen.add(card["correct"])
        assert card["side"] in card["text"]
    assert seen == {"left", "right"}


def test_variant_7_two_steps():
    card = build_challenge(7, rng=random.Random(7))
    first, second = card["sequence"]
    assert first != second
    assert is_correct_pick(card, "zzz")[0] == "fail"
    status, nxt = is_correct_pick(card, first)
    assert status == "next"
    assert nxt["step"] == 1
    assert is_correct_pick(nxt, first)[0] == "fail"
    assert is_correct_pick(nxt, second)[0] == "pass"


def test_signed_callbacks_are_short_and_tamper_proof():
    data = answer_callback_data(123456, "diamond")
    assert len(data) <= 64
    parsed = parse_answer_callback(data)
    assert parsed == (123456, "diamond", sign_parts("a", 123456, "diamond"))
    assert check_sign(parsed[2], "a", 123456, "diamond")
    assert not check_sign("0000000000", "a", 123456, "diamond")
    off = disable_callback_data(-100123)
    assert len(off) <= 64
    chat_id, mac = parse_disable_callback(off)
    assert chat_id == -100123
    assert check_sign(mac, "x", -100123)


def test_card_entities_carry_custom_emoji():
    from types import SimpleNamespace

    user = SimpleNamespace(id=7, full_name="Иэрихон Cute", first_name="Иэрихон", is_bot=False)
    card = build_challenge(5, rng=random.Random(5))
    text, ents = card_plain_and_entities(card, user)
    assert "Это капча." in text
    assert "писать в группе" in text
    kinds = [str(getattr(e, "type", "")) for e in ents]
    assert "custom_emoji" in kinds
    assert "underline" in kinds
    assert "bold" in kinds
    custom = [e for e in ents if str(getattr(e, "type", "")) == "custom_emoji"]
    custom_ids = [e.custom_emoji_id for e in custom]
    assert "5389099803655305880" in custom_ids
    assert "5213205860498549992" in custom_ids
    assert card["prefix_id"] in custom_ids
    assert card["prefix_face"] in text
    # в подписи кнопки этого лица быть не должно — только пробел + icon
    markup = __import__("bot.funcs.group_captcha", fromlist=["build_markup"]).build_markup(1, -100, card)
    for btn in markup.inline_keyboard[0]:
        assert btn.text == " "
        assert btn.icon_custom_emoji_id
        assert card["prefix_face"] not in btn.text


def test_buttons_carry_premium_emoji_ids():
    from bot.funcs.group_captcha import build_markup, premium_button

    card = build_challenge(2, rng=random.Random(11))
    markup = build_markup(9, -1001, card)
    row = markup.inline_keyboard[0]
    ids = {btn.icon_custom_emoji_id for btn in row}
    expected = {emoji(k).emoji_id for k in card["options"]}
    assert ids == expected
    assert all(btn.text == " " for btn in row)
    disable = markup.inline_keyboard[1][0]
    assert disable.text == "Убрать капчу"
    assert disable.icon_custom_emoji_id == "5462990652943904884"
    assert disable.callback_data.startswith("gcX:")
    sample = premium_button(emoji("spark"), "x", plain=True)
    assert sample.icon_custom_emoji_id == "5472164874886846699"
    assert sample.text == " "
    assert "✨" not in sample.text


def test_hydrate_recovers_old_payload():
    from bot.funcs.group_captcha import hydrate_payload

    old = {
        "variant": 5,
        "options": ["left", "right"],
        "correct": "right",
        "prefix_id": emoji("v5_prefix").emoji_id,
        "side": "направо",
        "text": "legacy",
    }
    hydrated = hydrate_payload(old)
    assert hydrated["prefix_face"] == emoji("v5_prefix").face
    assert hydrated["chunks"][1]["value"] == "направо"
    text, ents = card_plain_and_entities(old, type("U", (), {"id": 1, "full_name": "Аня", "first_name": "Аня"})())
    custom = [e for e in ents if str(getattr(e, "type", "")) == "custom_emoji"]
    custom_ids = [e.custom_emoji_id for e in custom]
    assert "5389099803655305880" in custom_ids
    assert old["prefix_id"] in custom_ids
    total = len(text.encode("utf-16-le")) // 2
    for e in ents:
        assert 0 <= e.offset < total
        assert e.offset + e.length <= total


def test_button_dump_keeps_icon_and_space():
    from bot.funcs.group_captcha import build_markup

    card = build_challenge(5, rng=random.Random(8))
    markup = build_markup(4, -1002, card)
    dumped = markup.model_dump()
    row = dumped["inline_keyboard"][0]
    for btn in row:
        assert btn["text"] == " "
        assert btn["icon_custom_emoji_id"]
        assert "✨" not in btn["text"]
        assert emoji("left").face not in btn["text"]
        assert emoji("right").face not in btn["text"]
    disable = dumped["inline_keyboard"][1][0]
    assert disable["text"] == "Убрать капчу"
    assert disable["icon_custom_emoji_id"] == "5462990652943904884"


def test_variant_7_is_rare_but_present():
    rng = random.Random(2026)
    picks = [pick_variant(rng) for _ in range(400)]
    share = picks.count(7) / len(picks)
    assert 0.05 < share < 0.20
    assert set(picks) >= {1, 2, 3, 4, 5, 6, 7}
    assert 8 not in picks
