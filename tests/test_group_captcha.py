# -*- coding: utf-8 -*-
import random

from bot.funcs.group_captcha import (
    EMOJI,
    PASS_ALERT,
    event_meta,
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


def test_event_meta_keeps_names():
    user = type("U", (), {"full_name": "Анна Cute", "first_name": "Анна", "username": "anna"})()
    chat = type("C", (), {"title": "Игры", "username": "games"})()
    meta = event_meta(user, chat, extra={"trigger": "message", "pick": "right"})
    assert meta["name"] == "Анна Cute"
    assert meta["username"] == "anna"
    assert meta["chat"] == "Игры"
    assert meta["trigger"] == "message"
    assert meta["pick"] == "right"


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
        for btn, key in zip(markup.inline_keyboard[0], card["options"]):
            item = emoji(str(key))
            assert btn.text == " "
            assert item.face not in (btn.text or "")
            assert getattr(btn, "icon_custom_emoji_id", None) == item.emoji_id


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
    assert "Это " in html and "капча" in html
    assert "писать в группе" in html
    assert "выполните задание ниже" in html
    assert "5389099803655305880" in html
    assert "6025996269141364975" in html
    intro = html.split("\n\n", 1)[0]
    assert "<u>" not in intro
    assert f"<u>{card['color']}</u>" in html
    assert "<b>Нажмите" in html
    assert html.endswith("</blockquote>")
    assert "<blockquote><b>Или напишите в чат \"" in html
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


def test_variant_3_is_removed():
    assert 3 not in VARIANT_LABELS
    for i in range(80):
        assert pick_variant(random.Random(i)) != 3
    card = build_challenge(3, rng=random.Random(3))
    assert card["variant"] != 3


def test_variant_4_rotates_bird_potato_suitcase():
    asks4 = set()
    for i in range(30):
        c4 = build_challenge(4, rng=random.Random(300 + i))
        asks4.add(c4["ask"])
        assert "значок, который обозначает" in c4["text"]
        assert c4["ask"] in c4["text"]
        assert f"<u>{c4['ask']}</u>" in c4["text"]
        assert is_correct_pick(c4, c4["correct"])[0] == "pass"
        assert is_correct_pick(c4, "nope")[0] == "fail"
    assert asks4 == {"птица", "картошка", "чемодан"}
    assert 3 not in VARIANT_LABELS
    assert 6 not in VARIANT_LABELS
    assert 7 not in VARIANT_LABELS
    assert 8 not in VARIANT_LABELS
    assert all(pick_variant(random.Random(i)) not in {3, 6, 7, 8} for i in range(80))


def test_variant_5_keeps_left_right_order():
    seen = set()
    for i in range(16):
        card = build_challenge(5, rng=random.Random(600 + i))
        assert card["options"] == ["left", "right"]
        seen.add(card["correct"])
        assert card["side"] in card["text"]
    assert seen == {"left", "right"}


def test_removed_variants_are_not_issued():
    for i in range(120):
        assert pick_variant(random.Random(i)) in {1, 2, 4, 5}
    for gone in (3, 6, 7, 8):
        card = build_challenge(gone, rng=random.Random(gone * 17))
        assert card["variant"] in {1, 2, 4, 5}


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
    assert "выполните задание ниже" in text
    kinds = [str(getattr(e, "type", "")) for e in ents]
    assert "custom_emoji" in kinds
    assert "underline" in kinds
    assert "bold" in kinds
    under = [e for e in ents if str(getattr(e, "type", "")) == "underline"]
    assert len(under) == 1
    raw = text.encode("utf-16-le")
    marked = raw[under[0].offset * 2:(under[0].offset + under[0].length) * 2].decode("utf-16-le")
    assert marked == card["side"]
    custom = [e for e in ents if str(getattr(e, "type", "")) == "custom_emoji"]
    custom_ids = [e.custom_emoji_id for e in custom]
    assert "5389099803655305880" in custom_ids
    assert "6025996269141364975" in custom_ids
    assert card["prefix_id"] in custom_ids
    assert card["prefix_face"] in text
    markup = __import__("bot.funcs.group_captcha", fromlist=["build_markup"]).build_markup(1, -100, card)
    for btn, key in zip(markup.inline_keyboard[0], card["options"]):
        item = emoji(str(key))
        assert btn.text == " "
        assert btn.icon_custom_emoji_id == item.emoji_id


def test_buttons_carry_premium_emoji_ids():
    from bot.funcs.group_captcha import build_markup, premium_button

    card = build_challenge(2, rng=random.Random(11))
    markup = build_markup(9, -1001, card)
    row = markup.inline_keyboard[0]
    ids = {btn.icon_custom_emoji_id for btn in row}
    expected = {emoji(k).emoji_id for k in card["options"]}
    assert ids == expected
    assert all(btn.text == " " for btn in row)
    assert all(emoji(k).face not in (btn.text or "") for btn, k in zip(row, card["options"]))
    disable = markup.inline_keyboard[1][0]
    assert disable.text == "Убрать капчу"
    assert disable.icon_custom_emoji_id == "5462990652943904884"
    assert disable.callback_data.startswith("gcX:")
    sample = premium_button(emoji("spark"), "x", plain=True)
    assert sample.icon_custom_emoji_id == "5472164874886846699"
    assert sample.text == " "


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


def test_option_buttons_never_put_unicode_faces_in_text():
    from bot.funcs.group_captcha import ICON_ONLY_TEXT, build_markup

    faces = {emoji(k).face for k in EMOJI}
    faces.discard("")
    for variant in (1, 2, 4, 5):
        card = build_challenge(variant, rng=random.Random(40 + variant))
        markup = build_markup(variant, -100, card)
        for btn in markup.inline_keyboard[0]:
            assert btn.text == ICON_ONLY_TEXT
            assert btn.icon_custom_emoji_id
            for face in faces:
                assert face not in (btn.text or "")
        disable = markup.inline_keyboard[1][0]
        assert disable.text == "Убрать капчу"
        assert disable.icon_custom_emoji_id == "5462990652943904884"


def test_button_dump_keeps_icon_and_space():
    from bot.funcs.group_captcha import build_markup

    card = build_challenge(5, rng=random.Random(8))
    markup = build_markup(4, -1002, card)
    dumped = markup.model_dump()
    row = dumped["inline_keyboard"][0]
    for btn, key in zip(row, card["options"]):
        item = emoji(str(key))
        assert btn["text"] == " "
        assert btn["icon_custom_emoji_id"] == item.emoji_id
    disable = dumped["inline_keyboard"][1][0]
    assert disable["text"] == "Убрать капчу"
    assert disable["icon_custom_emoji_id"] == "5462990652943904884"


def test_active_variants_are_only_match_color_object_side():
    rng = random.Random(2026)
    picks = [pick_variant(rng) for _ in range(400)]
    assert set(picks) == {1, 2, 4, 5}
    assert 3 not in picks
    assert 6 not in picks
    assert 7 not in picks


def test_help_and_farm_callbacks_are_free_before_captcha():
    from bot.funcs.group_captcha import GATE_ALERT, is_free_callback

    assert is_free_callback("help_btn1")
    assert is_free_callback("9help_btn22")
    assert is_free_callback("help_deletehelp")
    assert is_free_callback("help_hide")
    assert is_free_callback("twogreet_cut")
    assert is_free_callback("starthowtoplay")
    assert is_free_callback("9close_bonus")
    assert is_free_callback("store_close_message")
    assert is_free_callback("close_message_inventory")
    assert is_free_callback("gcA:1:x:abc")
    assert is_free_callback("gcX:1:abc")
    assert not is_free_callback("greet_cut")
    assert not is_free_callback("kosti_take_1")
    assert not is_free_callback("craft_choose:1")
    assert "капчу" in GATE_ALERT.lower()


def test_farm_deep_link_works_in_groups():
    from bot.funcs.webapp_links import (
        farm_url,
        group_safe_url,
        infer_startapp,
        is_our_mini_app,
    )

    assert farm_url() == "https://t.me/CuteGamingBot/cute?startapp=farm"
    assert infer_startapp("https://cutegaming-ridbh.ondigitalocean.app/", "Открыть ферму") == "farm"
    assert infer_startapp("https://cutegaming-ridbh.ondigitalocean.app/?startapp=shop", "") == "shop"
    assert group_safe_url(
        "https://cutegaming-ridbh.ondigitalocean.app/",
        "Ферма",
        as_web_app=True,
    ) == farm_url()
    assert group_safe_url("https://example.com/page", "Сайт", as_web_app=False) == "https://example.com/page"
    assert is_our_mini_app("https://cutegaming-ridbh.ondigitalocean.app/")
    assert not is_our_mini_app("https://evil.example/cutegaming")


def test_help_unowned_card_is_public():
    from bot.funcs.help_guard import help_callback_allowed

    owners = {11: 900}
    assert help_callback_allowed(11, 900, owners)
    assert not help_callback_allowed(22, 900, owners)
    assert help_callback_allowed(22, 901, owners)
    assert help_callback_allowed(1, 1, {})


def test_click_uses_message_chat_id_after_supergroup_upgrade():
    from bot.funcs.group_captcha import resolve_click_chat_id

    row = {"chat_id": -12345, "user_id": 7}
    assert resolve_click_chat_id(row, -10012345) == -10012345
    assert resolve_click_chat_id(row, None) == -12345
    assert resolve_click_chat_id(row, 0) == -12345


def test_live_challenge_index_survives_chat_id_patch():
    from bot.funcs import group_captcha as gc

    gc._clear_pass_memory()
    gc.remember_live({
        "id": 91,
        "chat_id": -11,
        "user_id": 5,
        "payload": {"variant": 5, "correct": "right", "options": ["left", "right"]},
    })
    found = gc.peek_live_user(-11, 5)
    assert found is not None
    assert found["id"] == 91
    gc.patch_live(91, chat_id=-10011)
    assert gc.peek_live_user(-11, 5) is None
    moved = gc.peek_live_user(-10011, 5)
    assert moved is not None
    assert moved["chat_id"] == -10011
    gc.forget_live(91)
    assert gc.peek_live(91) is None


def test_captcha_callbacks_are_magic_priority():
    from bot.magic.priorities import PRIORITY_PREFIXES
    from bot.magic.limits import MagicLimits

    assert "gcA:" in PRIORITY_PREFIXES
    assert "gcX:" in PRIORITY_PREFIXES
    lim = MagicLimits(
        prio_debounce_sec=30,
        debounce_sec=30,
        prio_user_max_clicks=1,
        user_max_clicks=1,
        global_inflight_soft=0,
        prio_global_inflight_soft=0,
    )
    for i in range(12):
        ok, reason = lim.allow(7, f"gcA:{i}:left:deadbeef")
        assert ok, reason
        ok, reason = lim.allow(7, f"gcX:-100:{i}")
        assert ok, reason


def test_card_adds_blockquote_chat_hint():
    from types import SimpleNamespace
    from bot.funcs.group_captcha import card_html, chat_hint_line, chat_hint_quoted

    user = SimpleNamespace(id=3, full_name="Наташа", first_name="Наташа")
    card = build_challenge(4, rng=random.Random(3))
    html = card_html(card, user)
    quoted = chat_hint_quoted(card)
    line = chat_hint_line(card)
    assert quoted
    assert line == f'Или напишите в чат "{quoted}"'
    assert f"<blockquote><b>{line}</b></blockquote>" in html
    text, ents = card_plain_and_entities(card, user)
    assert line in text
    kinds = [str(getattr(e, "type", "")) for e in ents]
    assert "blockquote" in kinds


def test_chat_answers_cover_every_variant_and_many_aliases():
    from bot.funcs.group_captcha import CHAT_OPTION, match_chat_answer

    v2 = build_challenge(2, rng=random.Random(2))
    color = v2["color"]
    assert match_chat_answer(v2, color)[0] == "pass"
    assert match_chat_answer(v2, color.upper())[0] == "pass"
    assert match_chat_answer(v2, f'Или напишите в чат "{color}"')[0] == "pass"
    wrong = "синий" if color != "синий" else "красный"
    assert match_chat_answer(v2, wrong)[0] == "fail"
    assert match_chat_answer(v2, "привет как дела всем")[0] == "miss"

    v5 = build_challenge(5, rng=random.Random(5))
    side = v5["side"]
    short = "лево" if side == "налево" else "право"
    alias = "влево" if side == "налево" else "вправо"
    assert match_chat_answer(v5, alias)[0] == "pass"
    assert match_chat_answer(v5, short)[0] == "pass"
    assert match_chat_answer(v5, "налево" if side == "направо" else "направо")[0] == "fail"
    assert match_chat_answer(v5, "лево" if side == "направо" else "право")[0] == "fail"

    v1 = build_challenge(1, rng=random.Random(1))
    key = v1["correct"]
    hint = CHAT_OPTION[key][0]
    assert match_chat_answer(v1, hint)[0] == "pass"
    assert match_chat_answer(v1, CHAT_OPTION[key][1][1])[0] == "pass"

    v4 = build_challenge(4, rng=random.Random(4))
    ask = v4["ask"]
    assert ask in {"птица", "картошка", "чемодан"}
    assert match_chat_answer(v4, ask)[0] == "pass"
    near = {"птица": "птицу", "картошка": "картошку", "чемодан": "чемоданом"}[ask]
    assert match_chat_answer(v4, near)[0] == "pass"
    old = {"птица": "живое", "картошка": "еду", "чемодан": "вещь"}[ask]
    assert match_chat_answer(v4, old)[0] == "pass"
    other = "птица" if ask != "птица" else "чемодан"
    assert match_chat_answer(v4, other)[0] == "fail"

    for variant in (1, 2, 4, 5):
        card = build_challenge(variant, rng=random.Random(20 + variant))
        html = __import__("bot.funcs.group_captcha", fromlist=["card_html"]).card_html(
            card, type("U", (), {"id": 1, "full_name": "Аня"})(),
        )
        assert "<blockquote><b>Или напишите в чат \"" in html
        assert "</b></blockquote>" in html


def test_fuzzy_chat_answers_accept_close_wording():
    from bot.funcs.group_captcha import CHAT_OPTION, match_chat_answer

    v4 = build_challenge(4, rng=random.Random(11))
    ask = v4["ask"]
    typo = {"птица": "птицца", "картошка": "картошкаа", "чемодан": "чемоданн"}[ask]
    phrase = f"мне кажется это {ask}"
    assert match_chat_answer(v4, phrase)[0] == "pass"
    assert match_chat_answer(v4, typo)[0] == "pass"
    assert match_chat_answer(v4, "привет всем в чате")[0] == "miss"

    v5_left = dict(build_challenge(5, rng=random.Random(5)))
    v5_left["correct"] = "left"
    v5_left["side"] = "налево"
    assert match_chat_answer(v5_left, "лево")[0] == "pass"
    assert match_chat_answer(v5_left, "налева")[0] == "pass"
    assert match_chat_answer(v5_left, "право")[0] == "fail"

    v2 = build_challenge(2, rng=random.Random(8))
    color_key = v2["correct"]
    stem = {"red": "красн", "green": "зелен", "blue": "синенький"}[color_key]
    assert match_chat_answer(v2, f"думаю {stem}")[0] == "pass"

    v1 = build_challenge(1, rng=random.Random(3))
    hint = CHAT_OPTION[v1["correct"]][0]
    assert match_chat_answer(v1, f"ну это {hint} же")[0] == "pass"


def test_handler_reexports_cleanup_and_next_alert():
    from bot.handlers.group_captcha import start_cleanup_task, stop_cleanup_task
    from bot.funcs.group_captcha import NEXT_ALERT

    assert callable(start_cleanup_task)
    assert callable(stop_cleanup_task)
    assert "вторую" in NEXT_ALERT
