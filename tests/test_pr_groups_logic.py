import sys
from pathlib import Path

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
    looks_like_help,
    nika_step_amount,
    promoter_cut,
    recommend_seed,
    recommend_split,
    spendable_amount,
    text_after_photos_reco,
    text_entry,
    text_gift,
    text_how,
    text_need_photo,
    text_wait_photo,
    weekly_seed_budget,
    withdrawable_chat,
)


def test_entry_is_short_and_honest():
    html = text_entry()
    assert "35%" in html
    assert "комиссии" in html
    assert "14 дней" in html
    assert "1." not in html
    assert "Начать" not in html


def test_how_tells_what_to_do_next():
    html = text_how()
    assert "@CuteGamingBot" in html
    assert "Проверить" in html
    assert "администратором" in html
    assert "1." not in html
    photo = text_wait_photo(0, 0)
    assert "1 из 3" in photo
    assert "Пришлите фото сюда" in photo
    assert "@CuteGamingBot" in photo
    second = text_wait_photo(1, 1)
    assert "Есть 1 из 3" in second
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
    assert "которую в которую" not in html


def test_gift_has_kut_and_user_wording():
    html = text_gift(1, "Вася", 10)
    assert "10 кут в подарок" in html
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
    for col in ("seed_applied", "confirm_token", "confirm_expires_at", "slot_hold_until", "last_digest_at"):
        assert col in names
    assert ST_FULFILLING == "fulfilling"
    assert "accepting" in WEEK_SEED_STATUSES


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
    assert not looks_like_confirm("привет")


def test_ban_is_31_days():
    assert BAN_DAYS == 31
