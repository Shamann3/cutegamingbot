import re
import sys
from pathlib import Path


def _visible(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from pr_groups_logic import (
    BAN_DAYS,
    GIFT_MIN,
    SHARE_PCT,
    classify_player,
    expected_newcomers,
    free_balance,
    is_broke,
    is_new_class,
    left_days_hint,
    looks_like_confirm,
    looks_like_group_ref,
    looks_like_help,
    parse_group_ref,
    startgroup_url,
    nika_step_amount,
    promoter_cut,
    recommend_seed,
    recommend_split,
    spendable_amount,
    text_after_photos_reco,
    text_entry,
    text_gift,
    text_how,
    text_forward_no_group,
    text_need_link,
    text_need_photo,
    text_wait_photo,
    extract_group_ref,
    chat_id_from_ref,
    weekly_seed_budget,
    withdrawable_chat,
)


def test_entry_explains_commission_for_both_roles():
    html = text_entry()
    assert "зарабат" in html.lower()
    assert "узнавал" in html.lower()
    assert "проект" in html
    assert "Нажмите, кто вы" in html
    assert "35%" not in html
    assert "карман" not in html
    assert "Кут - игры" not in html
    assert "игры в Telegram" not in html
    assert "1." not in html
    assert "Начать" not in html
    owner = text_how(intent="owner")
    reco = text_how(intent="reco")
    assert "35%" in reco
    assert "комиссии" in reco
    assert "14 дней" in reco
    assert "личный баланс" in reco
    assert "чужой" in reco
    assert "карман" in owner
    assert "баланс группы" in owner
    assert "владел" in owner.lower()


def test_how_tells_what_to_do_next():
    owner = text_how(intent="owner")
    assert "Сдать свою группу" in owner
    assert "проект" in owner
    assert "подар" in owner
    assert "@группа" in owner
    assert "t.me" in owner
    assert "пересл" not in owner.lower()
    assert "Шаг 1 из 4" in owner
    reco = text_how(intent="reco")
    assert "чужой" in reco
    assert "проект" in reco
    assert "подар" in reco
    assert "@CuteGamingBot" in reco
    assert "пересл" not in reco.lower()
    assert "Шаг 1 из 5" in reco
    need = text_need_link()
    assert "t.me" in need
    assert "id" in need.lower()
    assert "пересл" not in need.lower()
    assert "Копировать ссылку" in need
    assert "Шаг 2 из 4" in need
    assert "Шаг 2 из 5" in text_need_link(intent="reco")
    bad = text_forward_no_group()
    assert "не подходит" in bad
    assert "@группа" in bad
    assert "id" in bad.lower()
    photo = text_wait_photo(0, 0)
    assert "1 из 3" in photo
    assert "Пришлите фото сюда" in photo
    assert "@CuteGamingBot" in photo
    assert "Так чтобы было видно, что бот в чате отвечает." in text_wait_photo(1, 1)
    assert "Шаг 3 из 4" in photo
    assert "Шаг 3 из 5" in text_wait_photo(0, 0, intent="reco")
    second = text_wait_photo(1, 1)
    assert "Есть 1 из 3" in _visible(second)
    assert "2 из 3" in second


def test_need_photo_explains_the_mistake():
    assert "не видео" in text_need_photo("video")
    assert "не файл" in text_need_photo("file")
    assert "уже есть" in text_need_photo("dup")
    assert "галереи" in text_need_photo()
    assert looks_like_help("хелп")
    assert looks_like_help("Help")
    assert not looks_like_help("привет")


def test_reco_after_photos_mentions_confirm():
    html = text_after_photos_reco()
    assert "подтверждение" in html
    assert "Да" in html
    assert "которую в которую" not in html


def test_reco_bridge_does_not_pretend_they_are_owner():
    from pr_groups_logic import (
        text_after_proofs_owner,
        text_after_proofs_reco,
        text_cant_add,
        text_choose_role,
    )
    choose = text_choose_role()
    assert "Кто вы" in choose
    cant = text_cant_add()
    assert "@CuteGamingBot" in cant
    assert "@группа" in cant
    owner = text_after_proofs_owner()
    assert "Доказательства приняты" in owner
    assert "только у вас" in owner
    assert "проект" in owner
    assert "подар" in owner
    assert "проверку" in owner
    assert "этот чат" in owner or "сюда" in owner
    assert "стол" not in owner.lower()
    assert "соло" not in owner.lower()
    assert "Шаг 4 из 4" in owner
    assert "Мои группы" in owner
    reco = text_after_proofs_reco()
    assert "Доказательства приняты" in reco
    assert "14 дней" in reco
    assert "проект" in reco
    assert "подар" in reco
    assert "сюда" in reco
    assert "комисси" not in reco.lower()
    assert "Шаг 5 из 5" in reco
    assert "Мои группы" in reco
    assert "Шаг 4 из 5" in text_after_photos_reco()


def test_gift_has_kut_and_user_wording():
    html = text_gift(1, "Вася", 10)
    assert "10 кут в подарок" in _visible(html)
    assert "научится играть" in html
    assert "хелп" in html
    assert "tg://user?id=1" in html


def test_spendable_keeps_nika_reserve():
    assert spendable_amount(12000, 7400) == 4600
    assert spendable_amount(100, 400) == 0


def test_weekly_budget_is_15_percent():
    assert weekly_seed_budget(1000) == 150


def test_smart_split_covers_play_and_table():
    rec = recommend_split(1000, 80)
    assert rec["table"] + rec["pool"] == 1000
    assert rec["gift"] >= GIFT_MIN
    assert rec["slots"] >= 1
    tiny = recommend_split(40, 8)
    assert tiny["table"] + tiny["pool"] == 40


def test_recommend_seed_respects_spendable():
    assert recommend_seed(200, 50) == 50
    assert recommend_seed(20, 5000) <= 400


def test_expected_newcomers_clamped():
    assert expected_newcomers(0) == 3
    assert expected_newcomers(10000) == 40


def test_player_classes():
    t0 = 1_000_000
    week = 7 * 86400
    assert classify_player(last_real_ts=t0 - 100, first_seen_ts=t0 - week * 2, joined_ts=t0) == "active"
    assert classify_player(last_real_ts=t0 - week - 10, first_seen_ts=t0 - week * 2, joined_ts=t0) == "dormant"
    assert classify_player(last_real_ts=None, first_seen_ts=t0 - week - 10, joined_ts=t0) == "ghost"
    assert classify_player(last_real_ts=None, first_seen_ts=t0 - 100, joined_ts=t0) == "warming"
    assert classify_player(last_real_ts=None, first_seen_ts=None, joined_ts=t0) == "brand"
    # игра после входа Кута не делает человека «своим»
    assert classify_player(last_real_ts=t0 + 10, first_seen_ts=None, joined_ts=t0) == "brand"
    assert classify_player(last_real_ts=t0 + 10, first_seen_ts=t0 + 5, joined_ts=t0) == "brand"
    assert classify_player(last_real_ts=t0 + 10, first_seen_ts=t0 - week - 10, joined_ts=t0) == "ghost"
    assert is_new_class("dormant")
    assert is_new_class("brand")
    assert not is_new_class("active")
    assert not is_new_class("warming")


def test_claim_schema_has_money_and_confirm_columns():
    from pr_groups_logic import CLAIM_COLUMNS, ST_FULFILLING, WEEK_SEED_STATUSES
    names = {name for name, _spec in CLAIM_COLUMNS}
    for col in ("seed_applied", "confirm_token", "confirm_expires_at", "slot_hold_until", "last_digest_at", "freeze"):
        assert col in names
    assert ST_FULFILLING == "fulfilling"
    assert "accepting" in WEEK_SEED_STATUSES


def test_html_without_custom_emoji_keeps_inner():
    from pr_groups_logic import html_without_custom_emoji

    raw = "<tg-emoji emoji-id='1'>📣</tg-emoji> <b>текст</b>"
    assert html_without_custom_emoji(raw) == "📣 <b>текст</b>"


def test_need_photo_album_asks_one_at_a_time():
    from pr_groups_logic import text_need_photo

    html = text_need_photo("album").lower()
    assert "одно" in html or "альбом" in html


def test_deliver_dm_can_send_fresh_instead_of_edit():
    import inspect
    from bot.funcs.pr_groups import deliver_dm

    param = inspect.signature(deliver_dm).parameters["fresh"]
    assert param.default is False
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_claim_sql_quotes_freeze():
    from pr_groups_logic import alter_claim_column_sql, claim_set_sql, sql_ident

    assert sql_ident("freeze") == '"freeze"'
    alter = alter_claim_column_sql("freeze", "TEXT")
    assert '"freeze"' in alter
    assert "EXISTS freeze " not in alter
    sql, args = claim_set_sql(
        {"status": "live", "freeze": None, "nika_on": True},
        claim_id=9,
    )
    assert '"freeze" = $2' in sql
    assert '"status" = $1' in sql
    assert "freeze =" not in sql.replace('"freeze" = $2', "")
    assert args == ["live", None, True, 9]


def test_broke_and_locks():
    assert is_broke(4)
    assert not is_broke(5)
    assert free_balance(40, 12) == 28
    assert withdrawable_chat(900, 300) == 600
    assert withdrawable_chat(50, 300) == 0


def test_promoter_cut_is_35_and_capped():
    assert promoter_cut(100, 0, 100) == 35
    assert promoter_cut(100, 30, 100) == 5
    assert promoter_cut(100, 35, 100) == 0
    assert abs(SHARE_PCT - 0.35) < 1e-9


def test_nika_step_half_table_cap():
    assert nika_step_amount(table_origin=140, chat_balance=40, already_topped=0) == 20
    assert nika_step_amount(table_origin=140, chat_balance=130, already_topped=0) == 10
    assert nika_step_amount(table_origin=140, chat_balance=40, already_topped=70) == 0


def test_left_days_bands():
    assert left_days_hint(3)["hint"] == "скорее нет"
    assert left_days_hint(20)["hint"] == "осторожно"
    assert left_days_hint(40)["hint"] == "можно смотреть"
    assert left_days_hint(None) is None


def test_confirm_words():
    assert looks_like_confirm("Подтверждение")
    assert looks_like_confirm("подтвердить")
    assert looks_like_confirm("подтвердить.")
    assert looks_like_confirm("  ПОДТВЕРДИ  ")
    assert not looks_like_confirm("привет")


def test_gift_lock_cannot_leave_gift_group():
    from pr_groups_logic import bet_fits_gift_lock, gift_covers_this_play, own_kut_amount

    assert own_kut_amount(20, 8) == 12
    assert gift_covers_this_play(gift_chat_id=-100, play_chat_id=-100, solo=True, private=False)
    assert not gift_covers_this_play(gift_chat_id=-100, play_chat_id=-200, solo=True, private=False)
    assert not gift_covers_this_play(gift_chat_id=-100, play_chat_id=-100, solo=True, private=True)
    assert not gift_covers_this_play(gift_chat_id=-100, play_chat_id=-100, solo=False, private=False)
    assert bet_fits_gift_lock(balance=20, bet=15, gift_amount=8, gift_chat_id=-100, play_chat_id=-100)
    assert not bet_fits_gift_lock(balance=20, bet=15, gift_amount=8, gift_chat_id=-100, play_chat_id=-200)
    assert bet_fits_gift_lock(balance=20, bet=10, gift_amount=8, gift_chat_id=-100, play_chat_id=-200)
    assert bet_fits_gift_lock(
        balance=20, bet=5, gift_amount=8, gift_chat_id=-100, play_chat_id=-100, private=True,
    )
    assert not bet_fits_gift_lock(
        balance=20, bet=15, gift_amount=8, gift_chat_id=-100, play_chat_id=-100, private=True,
    )


def test_parse_group_ref():
    assert parse_group_ref("@myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("  вот @My_Friends смотри ") == {"kind": "username", "value": "My_Friends"}
    assert parse_group_ref("https://t.me/myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("http://t.me/myfriends/") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("https://www.t.me/myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("https://telegram.me/myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("https://telegram.dog/myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("t.me/myfriends/12")["kind"] == "username"
    assert parse_group_ref("https://t.me/myfriends/12?single")["value"] == "myfriends"
    assert parse_group_ref("tg://resolve?domain=myfriends") == {"kind": "username", "value": "myfriends"}
    assert parse_group_ref("https://t.me/+AbCdEf")["kind"] == "invite"
    assert parse_group_ref("https://t.me/joinchat/AAAA")["kind"] == "invite"
    assert parse_group_ref("https://t.me/c/1234567890/5") == {
        "kind": "id", "value": "-1001234567890", "chat_id": -1001234567890,
    }
    assert parse_group_ref("https://t.me/c/1234567890/5/7")["chat_id"] == -1001234567890
    assert parse_group_ref("-1001234567890")["chat_id"] == -1001234567890
    assert parse_group_ref("1234567890")["chat_id"] == -1001234567890
    assert parse_group_ref("1001234567890")["chat_id"] == -1001234567890
    assert parse_group_ref("tg://openmessage?chat_id=-1001234567890")["chat_id"] == -1001234567890
    assert parse_group_ref("привет") is None
    assert parse_group_ref("hello") is None
    assert parse_group_ref("https://t.me/share/url?url=x") is None
    assert parse_group_ref("https://t.me/addstickers/Pack") is None
    assert looks_like_group_ref("@CuteGroup")
    assert not looks_like_group_ref("хелп")
    assert extract_group_ref(text="наш чат", urls=["https://t.me/myfriends/3"])["value"] == "myfriends"
    assert chat_id_from_ref(parse_group_ref("t.me/c/2574123456")) == -1002574123456
    assert chat_id_from_ref(parse_group_ref("@myfriends")) is None
    assert "startgroup=pr" in startgroup_url()
    assert "admin=" in startgroup_url()


def test_ban_is_31_days():
    assert BAN_DAYS == 31


def test_earnings_screen_and_card_are_plain():
    from datetime import datetime, timedelta, timezone

    from pr_groups_logic import (
        claim_button_label,
        claim_status_label,
        moscow_day_start,
        text_confirm_prompt,
        text_digest,
        text_earnings,
        text_freeze_admin,
        text_group_card,
        text_accepted,
        text_accepting,
    )

    live = {
        "id": 1,
        "chat_title": "Друзья",
        "status": "live",
        "role": "reco",
        "paid_kut": 40,
        "gifts": 0,
        "freeze": None,
        "live_until": datetime.now(timezone.utc) + timedelta(days=11),
    }
    own = {
        "id": 2,
        "chat_title": "Мой чат",
        "status": "live",
        "role": "owner",
        "paid_kut": 0,
        "gifts": 7,
        "freeze": None,
    }
    html = text_earnings([live, own], total=40, today=8, live=True)
    assert "Заработки" in html
    assert "Всего вам пришло: 40 кут" in _visible(html)
    assert "Сегодня: 8 кут" in _visible(html)
    assert "кута" not in html.lower()
    pending = text_earnings([{"chat_title": "x", "status": "pending"}], total=0, today=0, live=False)
    assert "Мои группы" in pending
    reco_card = text_group_card(live, today=3, newcomers=6, gifts=0)
    assert "Вам уже пришло" in reco_card
    assert "Сегодня: 3 кут" in _visible(reco_card)
    assert "Новых людей: 6" in _visible(reco_card)
    assert "замороз" not in reco_card.lower()
    owner_card = text_group_card(own, today=0, newcomers=4, gifts=7, chat_balance=80)
    assert "Баланс группы" in owner_card
    assert "Подарков новым: 7" in _visible(owner_card)
    pause = text_group_card({**live, "freeze": "admin"}, today=0, newcomers=1)
    assert "пауза: Куту нужна админка" in pause
    assert "Верните Кут в администраторы" in pause
    btn = claim_button_label(live)
    assert "Друзья" in btn
    assert "40 кут" in btn
    own_btn = claim_button_label(own)
    assert "подарков: 7" in own_btn
    assert "3 фото" in claim_status_label("photos")
    assert "идёт заработок" in claim_status_label("live")
    assert "кута" not in text_confirm_prompt(1, "Игорь").lower()
    assert "добав" in text_confirm_prompt(1, "Игорь").lower()
    digest = text_digest(newcomers=2, paid=5, days_left=9, title="Друзья")
    assert "Сегодня с «Друзья»" in digest
    assert "комисси" not in digest.lower()
    assert "5 кут" in digest
    freeze = text_freeze_admin()
    assert "Пауза" in freeze
    assert "замороз" not in freeze.lower()
    accepted = text_accepted(14)
    assert "комисси" not in accepted.lower()
    assert "14 дней" in accepted
    assert "капают сами" in accepted
    assert "проект" in accepted
    assert "подар" in accepted
    assert "Мои группы" in accepted
    own_ok = text_accepted(14, role="owner")
    assert "капают сами" in own_ok
    assert "проект" in own_ok
    assert "подар" in own_ok
    assert "Мои группы" in own_ok
    seeding = text_accepting()
    assert "приня" in seeding.lower()
    assert "баланс группы" in seeding
    assert "35%" not in seeding
    start = moscow_day_start(datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc))
    assert start.tzinfo is not None
    blob = "\n".join([html, reco_card, owner_card, pause, digest, freeze, accepted]).lower()
    assert "кута " not in blob
    assert "замороз" not in blob


def test_each_pr_message_has_one_unique_premium_emoji():
    import re
    from datetime import datetime, timedelta, timezone

    from pr_groups_logic import (
        premium_emoji_ids,
        text_accepted,
        text_accepting,
        text_after_photos_reco,
        text_after_proofs_owner,
        text_after_proofs_reco,
        text_are_owner_switch,
        text_banned_31,
        text_bot_joined,
        text_bot_not_there,
        text_cancelled,
        text_cant_add,
        text_choose_role,
        text_confirm_expired,
        text_confirm_no_first,
        text_confirm_no_second,
        text_confirm_prompt,
        text_confirm_timeout,
        text_confirm_yes,
        text_confirm_not_needed,
        text_creator_typed_confirm,
        text_digest,
        text_drop_confirm,
        text_dropped,
        text_admin_ended,
        text_earnings,
        text_entry,
        text_forward_no_group,
        text_freeze_admin,
        text_freeze_public,
        text_gift,
        text_gift_locked,
        text_group_busy,
        text_group_blocked,
        text_group_card,
        text_group_not_found,
        text_how,
        text_how_admin,
        text_how_public,
        text_kicked,
        text_link_invite,
        text_need_admin,
        text_need_link,
        text_need_photo,
        text_need_photos_first,
        text_need_public,
        text_not_a_group,
        text_not_creator,
        text_not_in_group,
        text_not_owner_switch,
        text_not_your_claim,
        text_owner_bridge,
        text_owner_no_confirm,
        text_pick_group,
        text_pick_role,
        text_photos_expired,
        text_reco_bridge,
        text_rejected,
        text_resume_claim,
        text_term_end,
        text_two_live,
        text_two_pending,
        text_wait_photo,
        text_wrong_group,
        text_wrote_confirm,
        text_confirm_not_needed,
        text_creator_typed_confirm,
        text_drop_confirm,
        text_dropped,
        text_admin_ended,
        text_group_blocked,
    )

    live = {
        "chat_title": "Друзья",
        "status": "live",
        "role": "reco",
        "paid_kut": 4,
        "live_until": datetime.now(timezone.utc) + timedelta(days=3),
    }
    own = {
        "chat_title": "Мой чат",
        "status": "live",
        "role": "owner",
        "paid_kut": 0,
        "gifts": 2,
    }
    samples = [
        text_entry(),
        text_choose_role(),
        text_how(intent="owner"),
        text_how(intent="reco"),
        text_how_public(),
        text_how_admin(),
        text_need_public("x"),
        text_need_admin("x"),
        text_bot_joined("x"),
        text_need_link(),
        text_forward_no_group(),
        text_link_invite(),
        text_group_not_found(),
        text_bot_not_there("x"),
        text_cant_add(),
        text_not_in_group("x"),
        text_not_a_group(),
        text_pick_group(),
        text_not_owner_switch("x"),
        text_are_owner_switch("x"),
        text_wait_photo(0, 0),
        text_wait_photo(1, 1),
        text_wait_photo(2, 2),
        text_need_photo("video"),
        text_photos_expired(),
        text_after_proofs_owner(),
        text_after_proofs_reco(),
        text_after_photos_reco("x"),
        text_wrote_confirm(),
        text_earnings([], total=0, today=0, live=False),
        text_earnings([live], total=4, today=1, live=True),
        text_group_card(live, today=1, newcomers=2),
        text_cancelled(),
        text_confirm_prompt(1, "Игорь"),
        text_confirm_yes(),
        text_confirm_no_first(),
        text_digest(newcomers=1, paid=2, days_left=5, title="x"),
        text_gift(1, "Вася", 8),
        text_gift_locked(),
        text_kicked(),
        text_two_pending(),
        text_two_live(),
        text_banned_31(),
        text_freeze_admin(),
        text_accepted(14),
        text_accepted(14, role="owner"),
        text_accepting(),
        text_bot_joined("x", has_intent=True),
        text_how_admin(intent="reco"),
        text_need_admin("x", intent="reco"),
        text_bot_not_there("x", intent="reco"),
        text_need_photo("album"),
        text_need_photo("dup"),
        text_confirm_no_second(),
        text_not_your_claim(),
        text_not_creator(),
        text_confirm_expired(),
        text_wrong_group(),
        text_confirm_not_needed(),
        text_creator_typed_confirm(),
        text_drop_confirm("Друзья"),
        text_dropped(),
        text_admin_ended("Друзья", "Проект снял эту группу."),
        text_group_blocked(),
        text_need_photos_first(),
        text_term_end(),
        text_rejected("Мало людей", can_fix=True),
        text_rejected("18+", can_fix=False),
        text_freeze_public(),
        text_group_busy(),
        text_group_busy(owner=True),
        text_confirm_timeout(),
        text_owner_no_confirm(),
        text_resume_claim("Друзья", "photos"),
        text_pick_role("Друзья"),
        text_owner_bridge("Друзья"),
        text_reco_bridge("Друзья"),
        text_group_card(own, today=0, newcomers=1, gifts=2, chat_balance=10),
        text_group_card({**live, "status": "photos"}, today=0, newcomers=0),
        text_group_card({**live, "status": "rejected", "reject_text": "Мало людей"}, today=0, newcomers=0),
    ]
    extra_re = re.compile(r"<blockquote><b><i>.*?</i></b></blockquote>", re.S)
    quote_re = re.compile(r"<blockquote>.*?</blockquote>", re.S)
    for html in samples:
        ids = premium_emoji_ids(html)
        assert len(ids) == 1, html
        assert "<b>" in html, html
        stripped = extra_re.sub("", html)
        for quote in quote_re.findall(html):
            assert quote.startswith("<blockquote><b><i>"), html
            assert quote.endswith("</i></b></blockquote>"), html


def test_pr_themed_emojis_and_extra_quote():
    from pr_groups_logic import (
        EMOJI_ADMIN,
        EMOJI_EARN,
        EMOJI_GROUPS,
        EMOJI_HUB,
        EMOJI_OWNER,
        EMOJI_PHOTO,
        EMOJI_PUBLIC,
        EMOJI_RECO,
        STATUS_EMOJI_NO,
        STATUS_EMOJI_OK,
        STATUS_EMOJI_WAIT,
        extra,
        text_after_proofs_owner,
        text_cant_add,
        text_choose_role,
        text_entry,
        text_earnings,
        text_forward_no_group,
        text_how,
        text_how_admin,
        text_how_public,
        text_need_link,
        text_wait_photo,
    )

    assert extra("факт") == "<blockquote><b><i>факт</i></b></blockquote>"
    hub = text_entry()
    assert EMOJI_HUB in hub
    assert "Нажмите, кто вы" in hub
    assert "зарабат" in hub.lower()
    assert EMOJI_OWNER in text_how(intent="owner")
    assert EMOJI_RECO in text_how(intent="reco")
    assert EMOJI_RECO in text_choose_role()
    assert EMOJI_PUBLIC in text_how_public()
    assert EMOJI_ADMIN in text_how_admin()
    assert EMOJI_PHOTO in text_wait_photo(0, 0)
    assert EMOJI_GROUPS in text_earnings([], total=0, today=0, live=False)
    assert EMOJI_EARN in text_earnings([], total=4, today=1, live=True)
    assert STATUS_EMOJI_NO in text_forward_no_group()
    assert STATUS_EMOJI_OK in text_after_proofs_owner()
    assert STATUS_EMOJI_WAIT in text_need_link()
    assert "Подойдёт" in text_cant_add()
    assert "<blockquote><i>" not in text_need_link()


def test_design_file_drives_hub_and_buttons():
    from pr_groups_design import HUB, SCREENS, design_errors, emoji_id, iter_button_rows
    from pr_groups_logic import text_entry

    hub = SCREENS["hub"]
    assert "Нажмите, кто вы" in hub["text"]
    assert "зарабат" in hub["text"].lower()
    assert "узнавал" in hub["text"].lower()
    assert "35%" not in hub["text"]
    assert "Кут - игры" not in hub["text"]
    assert emoji_id(hub["emoji"]) == emoji_id(HUB)
    assert emoji_id(HUB) in text_entry()
    hub_gos = [btn.get("go") for row in iter_button_rows(hub["buttons"]) for btn in row]
    assert "owner" in hub_gos
    assert not design_errors()
    for name, spec in SCREENS.items():
        assert spec.get("emoji"), name
        assert spec.get("text"), name
        for row in iter_button_rows(spec.get("buttons")):
            if isinstance(row, dict):
                assert row.get("repeat")
                continue
            gos = [btn.get("go") for btn in row]
            assert len(gos) == len(set(gos)), (name, gos)
            for btn in row:
                assert btn.get("icon"), (name, btn.get("text"))


def test_words_drive_every_short_label():
    from pr_groups_design import STATUS, TASKS_MENU, TASKS_MENU_TEXT, WORDS
    from pr_groups_logic import claim_status_label, kut_amount, pause_label, say

    assert kut_amount(40) == say("kut", n=40)
    assert claim_status_label("photos") == STATUS["photos"]
    assert claim_status_label("accepting") == STATUS["accepting"]
    assert "посев" in STATUS["accepting"]
    assert claim_status_label("live", "admin") == pause_label("admin")
    assert "<" not in TASKS_MENU_TEXT
    assert ">" not in TASKS_MENU_TEXT
    assert TASKS_MENU_TEXT == "Рекомендация проекта"
    assert "5391270106464539040" in TASKS_MENU["icon"]
    assert WORDS["toast_check"]
    assert WORDS["history_gift"]
    assert WORDS["photo_have"]


def test_every_pr_message_has_valid_telegram_html():
    from pr_groups_logic import html_errors, text_need_photo, text_wait_photo

    samples = [
        text_wait_photo(0, 0),
        text_wait_photo(1, 1),
        text_wait_photo(2, 2),
        text_need_photo("video"),
        text_need_photo("file"),
        text_need_photo("sticker"),
        text_need_photo("text"),
        text_need_photo("album"),
        text_need_photo("dup"),
        text_need_photo(""),
    ]
    from pr_groups_logic import (
        text_accepted,
        text_accepting,
        text_after_photos_reco,
        text_after_proofs_owner,
        text_cant_add,
        text_entry,
        text_gift,
        text_group_card,
        text_how,
        text_need_link,
        text_rejected,
        text_resume_claim,
    )
    from datetime import datetime, timedelta, timezone

    live = {
        "chat_title": "Друзья",
        "status": "live",
        "role": "reco",
        "paid_kut": 4,
        "live_until": datetime.now(timezone.utc) + timedelta(days=3),
    }
    samples.extend([
        text_entry(),
        text_how(intent="owner"),
        text_how(intent="reco"),
        text_need_link(),
        text_cant_add(),
        text_after_proofs_owner(),
        text_after_photos_reco("Друзья"),
        text_accepted(14),
        text_accepted(14, role="owner"),
        text_accepting(),
        text_rejected("Мало людей", can_fix=True),
        text_gift(1, "Игорь", 8),
        text_resume_claim("Друзья", "photos"),
        text_resume_claim("Друзья", "wait_confirm"),
        text_group_card(live, today=1, newcomers=2),
        text_group_card({**live, "status": "photos", "freeze": None}, today=0, newcomers=0),
        text_group_card({**live, "status": "wait_confirm"}, today=0, newcomers=0),
        text_group_card({**live, "freeze": "admin"}, today=0, newcomers=1),
    ])
    for html in samples:
        bad = html_errors(html)
        assert not bad, (bad, html)

