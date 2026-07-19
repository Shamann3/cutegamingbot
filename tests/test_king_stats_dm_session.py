"""15-минутная сессия настройки в ЛС."""
import io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import bot.funcs.king_stats as ks

USER, GROUP = 6908672757, -1004203778966
ks._KING_DM_SESSIONS._load().clear()

# 1. Нет записи -> НЕ блокируем (состояние могло потеряться)
assert ks._dm_session_expired(USER, GROUP) is False, "отсутствие сессии не должно блокировать"

# 2. Свежая сессия активна
ks._touch_dm_session(USER, GROUP)
assert ks._dm_session_expired(USER, GROUP) is False, "свежая сессия должна быть активна"
assert ks._dm_session_left_sec(USER, GROUP) > 14 * 60, "остаток близок к 15 минутам"

# 3. Активность продлевает окно
ks._KING_DM_SESSIONS[ks._dm_menu_key(USER, GROUP)] = time.time() - 14 * 60
assert ks._dm_session_expired(USER, GROUP) is False, "14 минут - ещё активна"
ks._touch_dm_session(USER, GROUP)
assert ks._dm_session_left_sec(USER, GROUP) > 14 * 60, "активность обнуляет таймер"

# 4. Больше 15 минут -> закрыта
ks._KING_DM_SESSIONS[ks._dm_menu_key(USER, GROUP)] = time.time() - 15 * 60 - 5
assert ks._dm_session_expired(USER, GROUP) is True, "после 15 минут сессия закрыта"
assert ks._dm_session_left_sec(USER, GROUP) == 0

# 5. Сессии разных групп независимы
OTHER = -1001612636292
ks._touch_dm_session(USER, OTHER)
assert ks._dm_session_expired(USER, OTHER) is False
assert ks._dm_session_expired(USER, GROUP) is True, "группы не влияют друг на друга"

# 6. Битое значение не блокирует
ks._KING_DM_SESSIONS[ks._dm_menu_key(USER, GROUP)] = "мусор"
assert ks._dm_session_expired(USER, GROUP) is False, "битые данные трактуем в пользу пользователя"

print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
