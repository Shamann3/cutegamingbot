# -*- coding: utf-8 -*-
# bot/db_create/hash_backend.py
# ------------------------------------------------------------
# Per-key Redis Hash storage for GameStore.
# Replaces full-dict pickle blobs with incremental HSET/HGET.
# All network I/O is designed to run off the asyncio event loop
# (via pklcode's dedicated IO thread).
# ------------------------------------------------------------

from __future__ import annotations

import os
import pickle
import time
import zlib
from typing import Any, Dict, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from bot.db_create.pklcode import GameStore

COMPRESS_THRESHOLD = int(os.getenv("PKL_COMPRESS_THRESHOLD", "512"))
ZLIB_LEVEL = int(os.getenv("PKL_ZLIB_LEVEL", "3"))


def redis_keys(name: str) -> Tuple[str, str, str]:
    """Return (data_hash, ts_hash, exp_zset) Redis key names."""
    return (
        f"pkl:{name}:data",
        f"pkl:{name}:ts",
        f"pkl:{name}:exp",
    )


def serialize_value(value: Any) -> bytes:
    """Pickle a single value with optional zlib compression."""
    raw = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    if len(raw) > COMPRESS_THRESHOLD:
        return b"\x01" + zlib.compress(raw, level=max(1, min(ZLIB_LEVEL, 9)))
    return b"\x00" + raw


def deserialize_value(blob: bytes) -> Any:
    """Restore a single pickled (optionally compressed) value."""
    if not blob:
        return None
    flag = blob[0]
    data = blob[1:]
    if flag == 1:
        data = zlib.decompress(data)
    return pickle.loads(data)


def _key_bytes(key: str) -> bytes:
    return key.encode("utf-8")


def _wants_exp_zset(store: "GameStore") -> bool:
    """
    Whether the expiry sorted set must be maintained for this store.

    With a single owning process local timestamps are authoritative and TTL is
    evaluated in memory, so the zset is pure overhead (one ZADD per write).
    """
    fn = getattr(store, "_maintain_exp_zset", None)
    if fn is not None:
        try:
            return bool(fn())
        except Exception:
            pass
    return store.name not in store._excluded_stores()


def hash_has_data(rc, name: str) -> bool:
    """True if hash storage exists for this store."""
    data_key, _, _ = redis_keys(name)
    try:
        return bool(rc.exists(_key_bytes(data_key)))
    except Exception:
        return False


def hash_load_all(store: "GameStore", rc) -> bool:
    """
    Load all keys from Redis Hash into store memory.
    Returns True on success (including empty store).
    """
    data_key, ts_key, exp_key = redis_keys(store.name)
    try:
        raw_data = rc.hgetall(_key_bytes(data_key))
        raw_ts = rc.hgetall(_key_bytes(ts_key))
    except Exception as e:
        store._log_err("hash_load_all: Redis HGETALL failed", e)
        return False

    data_dict: Dict[str, Any] = {}
    for key_b, value_b in (raw_data or {}).items():
        key = key_b.decode("utf-8", "ignore")
        try:
            data_dict[key] = deserialize_value(bytes(value_b))
        except Exception:
            continue

    ts_dict: Dict[str, float] = {}
    for key_b, ts_b in (raw_ts or {}).items():
        key = key_b.decode("utf-8", "ignore")
        try:
            ts_dict[key] = float(ts_b.decode("utf-8"))
        except Exception:
            pass

    with store._lock:
        store.clear()
        store.update(data_dict)
        store.timestamps = ts_dict
        store._rebuild_expire_heap()
        store._migrate_keys_to_str()

    # Sync expiry sorted set with loaded timestamps.
    # Skipped when local timestamps are authoritative (single-process): this loop
    # issued one ZADD per key, which made boot load O(keys) round-trips of work.
    try:
        if ts_dict and _wants_exp_zset(store):
            pipe = rc.pipeline()
            for sk, ts in ts_dict.items():
                pipe.zadd(_key_bytes(exp_key), {sk: ts + store.expiry_seconds})
            pipe.execute()
    except Exception:
        pass

    return True


def hash_save_keys(store: "GameStore", rc, keys: Set[str]) -> bool:
    """Persist only the given keys to Redis Hash (pipeline)."""
    if not keys:
        return True

    data_key, ts_key, exp_key = redis_keys(store.name)
    use_zset = _wants_exp_zset(store)

    try:
        # Snapshot what to write while holding the store lock, then build and
        # run the pipeline without it, so Redis latency never blocks readers.
        writes: list = []
        deletes: list = []
        with store._lock:
            for sk in keys:
                if dict.__contains__(store, sk):
                    value = dict.__getitem__(store, sk)
                    writes.append((sk, serialize_value(value), store.timestamps.get(sk)))
                else:
                    deletes.append(sk)

        pipe = rc.pipeline()
        for sk, blob, ts in writes:
            pipe.hset(_key_bytes(data_key), _key_bytes(sk), blob)
            if ts is not None:
                pipe.hset(_key_bytes(ts_key), _key_bytes(sk), str(ts).encode("utf-8"))
                if use_zset:
                    pipe.zadd(_key_bytes(exp_key), {sk: ts + store.expiry_seconds})
        for sk in deletes:
            # Key was deleted locally
            pipe.hdel(_key_bytes(data_key), _key_bytes(sk))
            pipe.hdel(_key_bytes(ts_key), _key_bytes(sk))
            if use_zset:
                pipe.zrem(_key_bytes(exp_key), sk)
        pipe.execute()
        return True
    except Exception as e:
        store._log_err(f"hash_save_keys({len(keys)} keys) failed", e)
        return False


def hash_save_timestamps(store: "GameStore", rc, keys: Set[str]) -> bool:
    """
    Persist only TTL timestamps for the given keys (no value re-serialization).

    Reads refresh a key's TTL, and those refreshes must survive a restart -
    otherwise a hot key that is never written looks stale after boot and gets
    swept. Values are untouched, so this is a cheap HSET-only pipeline.
    """
    if not keys:
        return True

    _, ts_key, exp_key = redis_keys(store.name)
    use_zset = _wants_exp_zset(store)

    try:
        with store._lock:
            pairs = [(sk, store.timestamps.get(sk)) for sk in keys]

        pipe = rc.pipeline()
        wrote = 0
        for sk, ts in pairs:
            if ts is None:
                continue
            pipe.hset(_key_bytes(ts_key), _key_bytes(sk), str(ts).encode("utf-8"))
            if use_zset:
                pipe.zadd(_key_bytes(exp_key), {sk: ts + store.expiry_seconds})
            wrote += 1
        if wrote:
            pipe.execute()
        return True
    except Exception as e:
        store._log_err(f"hash_save_timestamps({len(keys)} keys) failed", e)
        return False


def hash_delete_store(rc, name: str) -> int:
    """Remove all hash keys for a store. Returns count of Redis keys deleted."""
    data_key, ts_key, exp_key = redis_keys(name)
    removed = 0
    try:
        removed += int(rc.delete(_key_bytes(data_key)) or 0)
        removed += int(rc.delete(_key_bytes(ts_key)) or 0)
        removed += int(rc.delete(_key_bytes(exp_key)) or 0)
    except Exception:
        pass
    return removed


def hash_cleanup_expired(store: "GameStore", rc) -> int:
    """Remove expired keys using sorted set scores."""
    if store.name in store._excluded_stores():
        return 0

    _, _, exp_key = redis_keys(store.name)
    data_key, ts_key, _ = redis_keys(store.name)
    now = time.time()

    try:
        expired_raw = rc.zrangebyscore(_key_bytes(exp_key), 0, now)
    except Exception:
        return 0

    if not expired_raw:
        return 0

    keys = [k.decode("utf-8", "ignore") for k in expired_raw]
    removed = 0

    try:
        pipe = rc.pipeline()
        for sk in keys:
            pipe.hdel(_key_bytes(data_key), _key_bytes(sk))
            pipe.hdel(_key_bytes(ts_key), _key_bytes(sk))
        pipe.zrem(_key_bytes(exp_key), *expired_raw)
        pipe.execute()
    except Exception:
        return 0

    with store._lock:
        for sk in keys:
            ts = store.timestamps.get(sk)
            if ts is None:
                continue
            if now - ts > store.expiry_seconds:
                if dict.__contains__(store, sk):
                    dict.__delitem__(store, sk)
                    removed += 1
                store.timestamps.pop(sk, None)

    return removed


def hash_get_single(store: "GameStore", rc, sk: str) -> Optional[Any]:
    """Fetch one key from Redis (multi-process heal)."""
    data_key, ts_key, exp_key = redis_keys(store.name)
    try:
        raw = rc.hget(_key_bytes(data_key), _key_bytes(sk))
        if raw is None:
            return None
        value = deserialize_value(bytes(raw))
        ts_raw = rc.hget(_key_bytes(ts_key), _key_bytes(sk))
        ts = float(ts_raw.decode("utf-8")) if ts_raw else time.time()
    except Exception:
        return None

    with store._lock:
        dict.__setitem__(store, sk, value)
        store.timestamps[sk] = ts
        if store.name not in store._excluded_stores():
            store._push_expiry(sk, ts)
    return value


def hash_migrate_from_blob(
    store: "GameStore",
    rc,
    *,
    load_blob_fn,
    unpack_blob_fn,
    delete_blob_fn,
) -> bool:
    """
    One-time migration: load legacy blob snapshot into memory,
    then persist as hash keys and remove blob.
    """
    raw_bytes = load_blob_fn()
    if raw_bytes is None:
        return False

    try:
        data_dict, ts_dict = unpack_blob_fn(raw_bytes)
    except Exception as e:
        store._log_err("hash_migrate_from_blob: unpack failed", e)
        return False

    with store._lock:
        store.clear()
        store.update(data_dict)
        store.timestamps = dict(ts_dict)
        store._rebuild_expire_heap()
        store._migrate_keys_to_str()

    all_keys = set(store.keys())
    if not hash_save_keys(store, rc, all_keys):
        return False

    try:
        delete_blob_fn(rc)
    except Exception:
        pass

    store._log_ok(f"Migrated blob → hash ({len(all_keys)} keys)")
    return True


def hash_verify_persisted(rc, name: str) -> Dict[str, Any]:
    """Check hash storage exists (for diagnostics)."""
    data_key, ts_key, _ = redis_keys(name)
    out: Dict[str, Any] = {
        "store": name,
        "mode": "hash",
        "ok": False,
        "fields": 0,
        "ts_fields": 0,
    }
    try:
        fields = rc.hlen(_key_bytes(data_key))
        ts_fields = rc.hlen(_key_bytes(ts_key))
        out["fields"] = int(fields or 0)
        out["ts_fields"] = int(ts_fields or 0)
        out["ok"] = out["fields"] > 0
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out
