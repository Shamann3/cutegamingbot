"""Перевод, который не останавливает бота и не бьёт в лимит Google.

Google разрешает около 5 запросов в секунду. Вызовы идут по одному,
с паузой, из отдельного потока. Повтор одной и той же фразы берётся из памяти.
"""

import asyncio
import threading
import time

_LOCK = threading.RLock()
_CACHE = {}
_CACHE_MAX = 400
_NEXT_AT = 0.0
_GAP = 0.25
_RETRY_WAIT = 0.8


def reset_translate_state():
    global _NEXT_AT
    with _LOCK:
        _CACHE.clear()
        _NEXT_AT = 0.0


def _is_rate_limit(exc):
    msg = str(exc).lower()
    return "too many requests" in msg or "server error" in msg


def _pace(clock, sleeper):
    global _NEXT_AT
    now = clock()
    wait = _NEXT_AT - now
    if wait > 0:
        sleeper(wait)
        now = clock()
    _NEXT_AT = now + _GAP


def _remember(key, value):
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = value


def _google_translate(text, source, target):
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source=source, target=target).translate(text)


def _google_batch(texts, source, target):
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source=source, target=target).translate_batch(list(texts))


def translate_blocking(text, target="ru", source="auto", *, translate=None, clock=None, sleeper=None):
    raw = text if isinstance(text, str) else ("" if text is None else str(text))
    stripped = raw.strip()
    if not stripped:
        return raw
    if source != "auto" and source == target:
        return raw

    key = (source, target, stripped)
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    translate = translate or _google_translate

    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        _pace(clock, sleeper)
        try:
            out = translate(stripped, source, target)
        except Exception as exc:
            if not _is_rate_limit(exc):
                return raw
            sleeper(_RETRY_WAIT)
            _pace(clock, sleeper)
            try:
                out = translate(stripped, source, target)
            except Exception:
                return raw
        clean = (out or "").strip() or raw
        _remember(key, clean)
        return clean


def translate_many_blocking(texts, target="ru", source="en", *, translate_batch=None, translate=None, clock=None, sleeper=None):
    items = list(texts or [])
    out = [""] * len(items)
    pending_i = []
    pending_t = []
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    single = translate or _google_translate
    batch = translate_batch or _google_batch

    for index, text in enumerate(items):
        raw = text if isinstance(text, str) else ("" if text is None else str(text))
        stripped = raw.strip()
        if not stripped or (source != "auto" and source == target):
            out[index] = raw
            continue
        key = (source, target, stripped)
        with _LOCK:
            cached = _CACHE.get(key)
        if cached is not None:
            out[index] = cached
            continue
        pending_i.append(index)
        pending_t.append(stripped)

    if not pending_t:
        return out

    translated = None
    try:
        with _LOCK:
            _pace(clock, sleeper)
            translated = batch(pending_t, source, target)
        if not isinstance(translated, list) or len(translated) != len(pending_t):
            translated = None
    except Exception:
        translated = None

    if translated is None:
        for index, text in zip(pending_i, pending_t):
            out[index] = translate_blocking(
                text, target, source, translate=single, clock=clock, sleeper=sleeper,
            )
        return out

    for index, text, value in zip(pending_i, pending_t, translated):
        clean = (value or "").strip() or text
        with _LOCK:
            _remember((source, target, text), clean)
        out[index] = clean
    return out


async def translate_async(text, target="ru", source="auto"):
    return await asyncio.to_thread(translate_blocking, text, target, source)


async def translate_many_async(texts, target="ru", source="en"):
    return await asyncio.to_thread(translate_many_blocking, list(texts or []), target, source)
