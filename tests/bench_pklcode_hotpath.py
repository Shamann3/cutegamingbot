"""
A/B горячего пути: PKL_HOT_PATH_V2=0 (как было) против =1 (как стало).

Запуск: python tests/bench_pklcode_hotpath.py 0
        python tests/bench_pklcode_hotpath.py 1
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

_env = _ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

MODE = sys.argv[1] if len(sys.argv) > 1 else "1"
os.environ["PKL_HOT_PATH_V2"] = MODE
os.environ.setdefault("PKL_LOG_LEVEL", "50")
os.environ.setdefault("PKL_SUMMARY", "0")

import bot.db_create.pklcode as P

NAME = "_bench_hotpath"
KEYS = 20000
MISSES = 300

print(f"=== PKL_HOT_PATH_V2={MODE} | ключей в сторе: {KEYS} ===")
if P._raw_client() is None:
    P._try_bind_redis_from_env()
assert P._raw_client() is not None, "нужен работающий Redis"

s = P.GameStore(NAME)
s._need_initial_sync = False
P.hash_backend.hash_delete_store(P._raw_client(), NAME)
with s._lock:
    s.clear()
    s.timestamps.clear()

payload = {"balance": 1234, "items": list(range(10)), "meta": {"lvl": 7}}
s.bulk_load({f"user{i}": dict(payload) for i in range(KEYS)})
s.flush()
time.sleep(0.3)

# --- 1. стоимость промаха чтения ---
t0 = time.perf_counter()
for i in range(MISSES):
    s.get(f"нет_такого_{i}")
    s._heal_last_reload_ts = 0.0  # снимаем анти-спам, как при потоке разных промахов
miss_ms = (time.perf_counter() - t0) / MISSES * 1000
print(f"промах чтения        : {miss_ms:8.3f} мс/вызов")

# --- 2. рост _expire_heap на чтениях ---
heap0 = len(s._expire_heap)
for i in range(20000):
    s.get(f"user{i % KEYS}")
print(f"_expire_heap +20k чт : {len(s._expire_heap) - heap0:8d} элементов")

# --- 3. потоки на 2000 записей ---
th0 = threading.active_count()
for i in range(2000):
    s[f"user{i}"] = {"balance": i, "items": list(range(10)), "meta": {"lvl": 1}}
print(f"потоков на 2000 зап. : {threading.active_count() - th0:8d}")

# --- 4. перезапись большого вложенного значения ---
big = {f"f{i}": {"a": list(range(20)), "b": {"c": i}} for i in range(300)}
s["big"] = big
t0 = time.perf_counter()
for _ in range(200):
    s["big"] = big
print(f"перезапись вложенного: {(time.perf_counter() - t0) / 200 * 1000:8.3f} мс/запись")

P.hash_backend.hash_delete_store(P._raw_client(), NAME)
