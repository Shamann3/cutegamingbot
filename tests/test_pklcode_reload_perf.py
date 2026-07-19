"""Перезалив стора: быстрый путь без несохранённого, мердж - только когда есть что защищать."""
import io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import bot.db_create.pklcode as P
import bot.funcs.king_stats as ks

# 1. Горячий путь: промах по pending не должен ходить в Redis
backing = ks._KING_PENDING_INPUTS._load()
backing.clear(); backing.timestamps.clear()
N = 2000
t0 = time.perf_counter()
for i in range(N):
    ks._get_pending_input(-100000 - i, 900 + i)
per_call_us = (time.perf_counter() - t0) / N * 1e6
assert per_call_us < 50, f"промах стоит {per_call_us:.1f} мкс - похоже, снова ходим в Redis"

# 2. Выставленный pending по-прежнему читается
ks._set_pending_input(555, 555, {"type": "start_date_custom"}, group_chat_id=-100777)
got = ks._get_pending_input(555, 555)
assert got is not None and got["group_chat_id"] == -100777, "pending должен читаться"

# 3. Мердж защищает несохранённые записи
s = P.GameStore("_test_merge_guard")
s.clear(); s.timestamps.clear()
s["старый"] = "из_redis"
s.flush()
stale = s._pack_bytes()
s._load_payload = lambda: stale
s["новый"] = "ещё_не_сохранён"          # -> _pending_dirty = True
s._heal_last_reload_ts = 0.0
s.get("промах")                          # промах -> перезалив
assert s.get("новый") == "ещё_не_сохранён", "несохранённая запись потеряна"
assert s.get("старый") == "из_redis", "данные из снапшота потеряны"

# 4. Без несохранённого используется быстрый путь (снапшот авторитетен)
s._pending_dirty = False
s._dirty_since_boot = False
s["лишний"] = "должен_исчезнуть_после_перезалива"
s._pending_dirty = False                 # имитируем "всё сохранено"
s._dirty_since_boot = False
s._heal_last_reload_ts = 0.0
s.get("промах2")
assert s.get("лишний") is None, "быстрый путь должен просто взять снапшот"

print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
