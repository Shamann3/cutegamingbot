"""
Горячий путь pklcode: чтение/запись не должны трогать Redis из event-loop.

Проверяем инварианты v2 (PKL_HOT_PATH_V2):
 1. промах чтения не ходит в Redis;
 2. чтения не растят _expire_heap;
 3. запись доезжает до Redis и читается обратно;
 4. TTL считается локально и настраивается на стор (в т.ч. "никогда");
 5. touch на чтении продлевает TTL и доезжает до Redis батчем;
 6. запись не создаёт поток на каждую операцию;
 7. запись не делает рекурсивное сравнение вложенных структур;
 8. в многопроцессном режиме reload-on-miss по-прежнему работает.
"""
import io
import os
import pathlib
import sys
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# .env нужен ради REDIS_PASSWORD: pklcode биндится к Redis сам, из окружения.
_env = _ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

os.environ.setdefault("PKL_LOG_LEVEL", "50")
os.environ.setdefault("PKL_SUMMARY", "0")

import bot.db_create.pklcode as P
import bot.funcs.king_stats as ks

assert P.PKL_HOT_PATH_V2, "тест написан под PKL_HOT_PATH_V2=1"
HAVE_REDIS = P._raw_client() is not None or P._try_bind_redis_from_env()
print(f"redis: {'есть' if HAVE_REDIS else 'НЕТ (проверки персистентности пропущены)'}")


def _fresh(name: str) -> P.GameStore:
    s = P.GameStore(name)
    s._need_initial_sync = False
    s._sweep_not_before = 0.0  # тесты проверяют TTL сразу, без грации
    with s._lock:
        s.clear()
        s.timestamps.clear()
        s._hash_dirty_keys.clear()
        s._touch_keys.clear()
        s._expire_heap.clear()
        s._sweep_keys = []
        s._sweep_pos = 0
    if HAVE_REDIS:
        P.hash_backend.hash_delete_store(P._raw_client(), name)
    return s


# ---------- 1. промах чтения не ходит в Redis ----------
backing = ks._KING_PENDING_INPUTS._load()
backing._need_initial_sync = False
with backing._lock:
    backing.clear()
    backing.timestamps.clear()
N = 2000
t0 = time.perf_counter()
for i in range(N):
    ks._get_pending_input(-100000 - i, 900 + i)
per_call_us = (time.perf_counter() - t0) / N * 1e6
assert per_call_us < 50, f"промах стоит {per_call_us:.1f} мкс - похоже, снова ходим в Redis"
print(f"1. промах чтения: {per_call_us:.1f} мкс/вызов")

# выставленный pending по-прежнему читается
ks._set_pending_input(555, 555, {"type": "start_date_custom"}, group_chat_id=-100777)
got = ks._get_pending_input(555, 555)
assert got is not None and got["group_chat_id"] == -100777, "pending должен читаться"

# ---------- 2. чтения не растят _expire_heap ----------
s = _fresh("_test_hotpath")
s["живой"] = 1
heap_before = len(s._expire_heap)
for _ in range(20000):
    s.get("живой")
    s.get("нет_такого")
assert len(s._expire_heap) == heap_before, (
    f"_expire_heap вырос с {heap_before} до {len(s._expire_heap)} - "
    "куча снова растёт на каждое чтение"
)
assert s._touch_keys, "touch-метки должны копиться для батч-сохранения"
print(f"2. _expire_heap после 40k чтений: {len(s._expire_heap)} (touch в очереди: {len(s._touch_keys)})")

# ---------- 3. запись доезжает до Redis и читается обратно ----------
if HAVE_REDIS:
    s = _fresh("_test_persist")
    s["ключ"] = {"вложено": [1, 2, 3]}
    s.flush()
    raw = P._raw_client().hget(b"pkl:_test_persist:data", "ключ".encode("utf-8"))
    assert raw is not None, "значение не доехало до Redis"
    assert P.hash_backend.deserialize_value(bytes(raw)) == {"вложено": [1, 2, 3]}

    s2 = P.GameStore("_test_persist")
    with s2._lock:
        s2.clear()
        s2.timestamps.clear()
    assert P.hash_backend.hash_load_all(s2, P._raw_client())
    assert s2.get("ключ") == {"вложено": [1, 2, 3]}, "значение не восстановилось из Redis"
    print("3. запись -> Redis -> загрузка обратно: ок")

# ---------- 4. TTL локальный и настраиваемый на стор ----------
s = _fresh("_test_ttl")
s.expiry_seconds = 60
s["протухнет"] = "x"
s["свежий"] = "y"
with s._lock:
    s.timestamps["протухнет"] = time.time() - 3600
removed = s._sweep_expired_step()
assert removed == 1, f"должен истечь ровно 1 ключ, истекло {removed}"
assert s.get("протухнет") is None, "просроченный ключ должен исчезнуть"
assert s.get("свежий") == "y", "свежий ключ трогать нельзя"
if HAVE_REDIS:
    s.flush()
    assert P._raw_client().hget(b"pkl:_test_ttl:data", "протухнет".encode("utf-8")) is None, \
        "истёкший ключ должен быть удалён и из Redis"

# "никогда не истекает" - как в bot/admins/punish_timers.py
s = _fresh("_test_forever")
s.expiry_seconds = 10 ** 12
s["вечный"] = "z"
with s._lock:
    s.timestamps["вечный"] = time.time() - 10 ** 6
assert s._never_expires(), "стор с огромным expiry_seconds не должен чистить TTL"
assert s._sweep_expired_step() == 0
assert s.get("вечный") == "z", "вечный ключ не должен истекать"
print("4. TTL: истечение по локальным меткам + per-store 'никогда': ок")

# ---------- 5. touch на чтении продлевает TTL и доезжает до Redis ----------
if HAVE_REDIS:
    s = _fresh("_test_touch")
    s.expiry_seconds = 60
    s["горячий"] = "v"
    s.flush()
    ts_old = float(P._raw_client().hget(b"pkl:_test_touch:ts", "горячий".encode("utf-8")))

    # состарим метку так, чтобы ключ был на грани истечения, и прочитаем его
    with s._lock:
        s.timestamps["горячий"] = time.time() - 59
    time.sleep(0.05)
    s.get("горячий")
    assert s._sweep_expired_step() == 0, "активно читаемый ключ не должен истекать"

    s._last_touch_save_ts = 0.0
    s._maybe_flush_touch_ts()
    ts_new = float(P._raw_client().hget(b"pkl:_test_touch:ts", "горячий".encode("utf-8")))
    assert ts_new > ts_old, f"метка TTL не обновилась в Redis: {ts_old} -> {ts_new}"
    assert not s._touch_keys, "очередь touch должна опустеть после слива"
    print(f"5. touch продлил TTL в Redis: {ts_old:.3f} -> {ts_new:.3f}")

# ---------- 6. запись не создаёт поток на каждую операцию ----------
s = _fresh("_test_threads")
threads_before = threading.active_count()
for i in range(3000):
    s[f"k{i}"] = i
threads_after = threading.active_count()
assert threads_after - threads_before <= 2, (
    f"3000 записей добавили {threads_after - threads_before} потоков - "
    "похоже, снова threading.Timer на каждую запись"
)
print(f"6. потоки после 3000 записей: +{threads_after - threads_before}")

# ---------- 7. запись не делает рекурсивное сравнение вложенных структур ----------
s = _fresh("_test_nested")
big = {f"f{i}": {"a": list(range(20)), "b": {"c": i}} for i in range(300)}
s["big"] = big
t0 = time.perf_counter()
for _ in range(300):
    s["big"] = big
per_write_us = (time.perf_counter() - t0) / 300 * 1e6
assert per_write_us < 200, (
    f"перезапись большого вложенного значения стоит {per_write_us:.1f} мкс - "
    "похоже, вернулось рекурсивное сравнение в __setitem__"
)
print(f"7. перезапись вложенного значения: {per_write_us:.1f} мкс/запись")

# ---------- 8. многопроцессный режим: reload-on-miss всё ещё работает ----------
s = P.GameStore("_test_merge_guard")
s._need_initial_sync = False
with s._lock:
    s.clear()
    s.timestamps.clear()
s._storage_mode = "blob"
s["старый"] = "из_redis"
stale = s._pack_bytes()
s._load_payload = lambda: stale

P.PKL_SINGLE_PROCESS = False
try:
    s["новый"] = "ещё_не_сохранён"  # -> _pending_dirty = True
    s._heal_last_reload_ts = 0.0
    s.get("промах")  # промах -> перезалив с мерджем
    assert s.get("новый") == "ещё_не_сохранён", "несохранённая запись потеряна"
    assert s.get("старый") == "из_redis", "данные из снапшота потеряны"

    s._pending_dirty = False
    s._dirty_since_boot = False
    s["лишний"] = "должен_исчезнуть_после_перезалива"
    s._pending_dirty = False  # имитируем "всё сохранено"
    s._dirty_since_boot = False
    s._heal_last_reload_ts = 0.0
    s.get("промах2")
    assert s.get("лишний") is None, "быстрый путь должен просто взять снапшот"
finally:
    P.PKL_SINGLE_PROCESS = True
print("8. multi-process reload-on-miss: ок")

# ---------- 9. TTL известен с момента создания стора ----------
# Раньше срок жизни выставляли постфактум (punish_timers/king_stats), и уборщик
# успевал снести наказания и привязки меню по дефолтным 2 часам.
# Реальные сторы здесь только читаем: писать в живые наказания нельзя.
assert P.STORE_EXPIRY_OVERRIDES["mod_punish_timers"] >= P.NEVER_EXPIRE_SEC, \
    "наказания должны быть объявлены вечными"
for _menu_store in ("_KING_MENU_OWNERS", "_KING_MENU_TARGET",
                    "_KING_MENU_RENDER_STATE", "_KING_DM_LAST_MENU"):
    days = P.STORE_EXPIRY_OVERRIDES[_menu_store] / 86400
    assert abs(days - 30) < 0.01, f"{_menu_store}: ожидались 30 дней, а не {days:.2f}"

# сам механизм: объявленный срок применяется в момент создания стора
P.register_store_expiry("_test_registry_forever", P.NEVER_EXPIRE_SEC)
P.GameStore._instances.pop("_test_registry_forever", None)
reg = P.GameStore("_test_registry_forever")
reg._need_initial_sync = False
assert reg._never_expires(), "объявленный срок не применился при создании"
assert reg._sweep_not_before == 0.0, "для объявленного стора грация не нужна"
reg["ключ"] = "v"
with reg._lock:
    reg.timestamps["ключ"] = time.time() - 10 ** 6
assert reg._sweep_expired_step() == 0 and reg.get("ключ") == "v", \
    "вечный стор потерял ключ по TTL"
print("9. TTL задан при создании: наказания вечные, меню 30 дней")

# ---------- 10. страховка: незнакомый стор не подметается сразу ----------
P.GameStore._instances.pop("_test_grace", None)
grace = P.GameStore("_test_grace")
grace._need_initial_sync = False
assert grace._sweep_not_before > time.time(), "должен быть грациозный период"
grace["ключ"] = "v"
with grace._lock:
    grace.timestamps["ключ"] = time.time() - 10 ** 6
assert grace._sweep_expired_step() == 0, "в грациозный период удалять нельзя"
grace._sweep_not_before = 0.0
assert grace._sweep_expired_step() == 1, "после грациозного периода TTL работает"
print(f"10. грациозный период: {P.PKL_SWEEP_GRACE_SEC:.0f}с, затем TTL включается")

# ---------- 11. Redis лёг на старте: не сдаёмся и не теряем записи ----------
if HAVE_REDIS:
    NAME = "_test_offline_boot"
    P.hash_backend.hash_delete_store(P._raw_client(), NAME)
    P.GameStore._instances.pop(NAME, None)

    seed = P.GameStore(NAME)
    seed._need_initial_sync = False
    seed["из_redis"] = "старое"
    seed.flush()

    # новый процесс, Redis недоступен
    P.GameStore._instances.pop(NAME, None)
    saved_raw, P._rds_raw = P._rds_raw, None
    try:
        cold = P.GameStore(NAME)
        assert cold._need_initial_sync, "стор должен ждать первой загрузки"
        cold["пока_лежал"] = "новое"
        assert cold._need_initial_sync, (
            "стор сдался навсегда - раньше он до перезапуска отдавал пустоту, "
            "хотя данные в Redis целы"
        )
        assert cold.get("из_redis") is None, "данных из Redis пока быть не может"
    finally:
        P._rds_raw = saved_raw

    # Redis вернулся
    cold._sync_retry_after = 0.0
    cold._initial_sync_if_needed()
    assert not cold._need_initial_sync, "после возврата Redis загрузка должна пройти"
    assert cold.get("из_redis") == "старое", "данные из Redis не подхватились"
    assert cold.get("пока_лежал") == "новое", (
        "запись, сделанная пока Redis лежал, потеряна при загрузке"
    )
    cold.flush()
    stored = P._raw_client().hkeys(f"pkl:{NAME}:data".encode("utf-8"))
    assert b"\xd0\xbf\xd0\xbe\xd0\xba\xd0\xb0_\xd0\xbb\xd0\xb5\xd0\xb6\xd0\xb0\xd0\xbb" in stored, \
        f"запись не доехала до Redis после восстановления: {stored}"
    print("11. Redis лёг на старте: восстановился, ни одна запись не потеряна")

# ---------- уборка ----------
if HAVE_REDIS:
    for _n in (
        "_test_hotpath", "_test_persist", "_test_ttl", "_test_forever",
        "_test_touch", "_test_threads", "_test_nested", "_test_merge_guard",
        "_test_grace", "_test_offline_boot", "_test_registry_forever",
    ):
        P.hash_backend.hash_delete_store(P._raw_client(), _n)

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")
