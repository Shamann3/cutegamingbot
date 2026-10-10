from bot.funcs.flag_book import country_title, iso_code, normalize_flag


def test_norway_has_its_name():
    assert country_title("🇳🇴") == "Флаг Норвегии"
    assert country_title("🇳🇴\ufe0f") == "Флаг Норвегии"
    assert iso_code("🇳🇴") == "NO"


def test_shop_name_is_what_the_profile_shows():
    assert country_title("🇳🇴", "Флаг Норвегии") == "Флаг Норвегии"


def test_invisible_mark_does_not_hide_the_country():
    assert normalize_flag(" 🇳🇴\u200b ") == "🇳🇴"
    assert country_title(" 🇳🇴\u200b ") == "Флаг Норвегии"


def test_russia_and_an_empty_value():
    assert country_title("🇷🇺") == "Флаг России"
    assert country_title("") == ""
    assert country_title("не флаг") == "Неизвестная страна"
