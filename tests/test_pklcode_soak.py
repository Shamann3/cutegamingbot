"""
Длительная работа pkl: ничего не должно расти без предела и теряться.

Прогоняем смесь операций (запись/чтение/удаление/истечение), затем проверяем:
 1. внутренние структуры не растут (куча TTL, очередь touch, метки времени);
 2. в Redis не остаётся полей от удалённых и истёкших ключей;
 3. после «перезапуска» данные восстанавливаются ровно те, что должны;
 4. удаление по нормализованному ключу (int/строка-число) не оставляет мусора;
 5. очередь писателя не растёт.
"""
import io
import os
import pathlib
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bot.config.db_config import bootstrap_database_env
bootstrap_database_env()
os.environ.setdefault("PKL_LOG_LEVEL", "50")
os.environ.setdefault("PKL_SUMMARY", "0")

import bot.db_create.pklcode as P

HAVE_REDIS = P._raw_client() is not None or P._try_bind_redis_from_env()
print(f"redis: {'есть' if HAVE_REDIS else 'НЕТ (проверки в Redis пропущены)'}")

NAME = "_soak_store"
CYCLES = 30_000


def _fresh(name: str) -> P.GameStore:
    P.GameStore._instances.pop(name, None)
    s = P.GameStore(name)
    s._need_initial_sync = False
    s._sweep_not_before = 0.0
    with s._lock:
        s.clear()
        s.timestamps.clear()
        s._hash_dirty_keys.clear()
        s._touch_keys.clear()
        s._expire_heap.clear()
    if HAVE_REDIS:
        P.hash_backend.hash_delete_store(P._raw_client(), name)
    return s


# ---------- 1-2. смесь операций, затем проверка на утечки ----------
s = _fresh(NAME)
s.expiry_seconds = 60

live = set()
for i in range(CYCLES):
    k = f"user{i % 500}"
    s[k] = {"n": i, "items": [i, i + 1]}
    live.add(k)
    s.get(k)
    s.get(f"нет_{i}")           # промах
    if i % 5 == 0:              # регулярные удаления
        victim = f"user{i % 500}"
        if victim in live:
            del s[victim]
            live.discard(victim)

s.flush()
time.sleep(0.3)

assert len(s._expire_heap) == 0, f"куча TTL выросла до {len(s._expire_heap)}"
assert len(s) == len(live), f"в памяти {len(s)} ключей, ожидалось {len(live)}"
assert set(s.keys()) == live, "состав ключей разошёлся с ожидаемым"
assert len(s.timestamps) == len(live), (
    f"осиротевшие метки времени: {len(s.timestamps)} меток на {len(live)} ключей"
)
assert len(s._touch_keys) <= len(live), f"очередь touch раздулась: {len(s._touch_keys)}"
print(f"1. после {CYCLES * 3} операций: ключей={len(s)}, меток={len(s.timestamps)}, "
      f"куча={len(s._expire_heap)}, touch={len(s._touch_keys)}")

if HAVE_REDIS:
    fields = P._raw_client().hlen(f"pkl:{NAME}:data".encode("utf-8"))
    ts_fields = P._raw_client().hlen(f"pkl:{NAME}:ts".encode("utf-8"))
    assert fields == len(live), f"в Redis {fields} полей, живых ключей {len(live)}"
    assert ts_fields == len(live), f"в Redis {ts_fields} меток, живых ключей {len(live)}"
    print(f"2. в Redis ровно живые ключи: data={fields}, ts={ts_fields}")

# ---------- 3. истечение чистит и память, и Redis ----------
with s._lock:
    for k in list(s.timestamps):
        s.timestamps[k] = time.time() - 10_000
swept = 0
for _ in range(10):
    swept += s._sweep_expired_step()
    if not s.timestamps:
        break
s.flush()
time.sleep(0.3)
assert len(s) == 0, f"после истечения в памяти осталось {len(s)} ключей"
assert not s.timestamps, f"после истечения осталось {len(s.timestamps)} меток"
if HAVE_REDIS:
    fields = P._raw_client().hlen(f"pkl:{NAME}:data".encode("utf-8"))
    assert fields == 0, f"в Redis осталось {fields} полей от истёкших ключей"
print(f"3. истечение вычистило {swept} ключей из памяти и из Redis")

# ---------- 4. целостность после «перезапуска» ----------
if HAVE_REDIS:
    s = _fresh(NAME)
    expected = {}
    for i in range(300):
        k, v = f"k{i}", {"n": i}
        s[k] = v
        expected[k] = v
    for i in range(0, 300, 3):
        del s[f"k{i}"]
        expected.pop(f"k{i}")
    s.flush()

    P.GameStore._instances.pop(NAME, None)
    revived = P.GameStore(NAME)
    revived._sweep_not_before = 0.0
    revived._initial_sync_if_needed()
    assert not revived._need_initial_sync, "перезалив после рестарта не прошёл"
    got = {k: revived.get(k) for k in expected}
    assert got == expected, "данные после рестарта не совпадают с ожидаемыми"
    assert len(revived) == len(expected), (
        f"после рестарта {len(revived)} ключей вместо {len(expected)} - "
        "удалённые ключи вернулись из Redis"
    )
    print(f"4. после рестарта восстановлено ровно {len(expected)} ключей, удалённые не вернулись")

# ---------- 5. удаление по нормализованному ключу не оставляет мусора ----------
s = _fresh("_soak_norm")
s[12345] = "v"          # ляжет как "12345"
assert s.get("12345") == "v"
del s["12345"]
assert not s.timestamps, f"осиротевшая метка после удаления: {s.timestamps}"

s[777] = "v"
del s[777]              # удаление int-ключом
assert len(s) == 0 and not s.timestamps, "удаление int-ключом оставило мусор"
if HAVE_REDIS:
    s.flush()
    time.sleep(0.2)
    fields = P._raw_client().hlen(b"pkl:_soak_norm:data")
    assert fields == 0, f"в Redis осталось {fields} полей после удаления"
print("5. удаление по нормализованному ключу чистит и метки, и Redis")

# ---------- 6. очередь писателя не растёт ----------
time.sleep(max(0.6, P.WRITE_DEBOUNCE_MS / 1000.0 * 3))
assert len(P._writer_pending) <= 2, f"очередь писателя не расходится: {len(P._writer_pending)}"
print(f"6. очередь писателя после простоя: {len(P._writer_pending)}")

if HAVE_REDIS:
    for _n in (NAME, "_soak_norm"):
        P.hash_backend.hash_delete_store(P._raw_client(), _n)

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")
