"""Кэш файлов Telegram для photo-proxy: диск + короткий LRU для превью.

Полные байты не держим в RAM пачками: оригинал пишется на диск,
в памяти живут только небольшие JPEG-превью. Повторное открытие
той же заявки не ходит в Telegram.
"""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

THUMB_EDGE = 320
DISK_TTL_SEC = 24 * 3600
MEM_TTL_SEC = 15 * 60
MEM_MAX_THUMBS = 80
CACHE_DIR = Path(tempfile.gettempdir()) / "cutegaming-tg-photo-cache"

_MEM: dict[str, tuple[float, bytes, str]] = {}
_TOKEN_HIT: dict[str, str] = {}


def photo_cache_key(file_id: str, size: str = "full") -> str:
    digest = hashlib.sha256((file_id or "").encode("utf-8")).hexdigest()[:24]
    kind = "thumb" if size == "thumb" else "full"
    return f"{kind}_{digest}"


def photo_proxy_url_shape(file_id: str, size: str = "full") -> str:
    kind = "thumb" if size == "thumb" else "full"
    query = urlencode({"file_id": file_id or "", "size": kind})
    return f"/admin/api/photo-proxy?{query}"


def normalize_photo_size(size: str | None) -> str:
    return "thumb" if (size or "").strip().lower() == "thumb" else "full"


def make_thumb_jpeg(data: bytes, max_edge: int = THUMB_EDGE) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(data))
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=72, optimize=True)
    return out.getvalue()


def _disk_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.bin"


def _mem_get(key: str) -> tuple[bytes, str] | None:
    hit = _MEM.get(key)
    if not hit:
        return None
    ts, data, content_type = hit
    if time.time() - ts > MEM_TTL_SEC:
        _MEM.pop(key, None)
        return None
    return data, content_type


def _mem_put(key: str, data: bytes, content_type: str) -> None:
    if len(_MEM) >= MEM_MAX_THUMBS:
        oldest = min(_MEM.items(), key=lambda item: item[1][0])[0]
        _MEM.pop(oldest, None)
    _MEM[key] = (time.time(), data, content_type)


def _disk_get(key: str) -> bytes | None:
    path = _disk_path(key)
    try:
        if not path.is_file():
            return None
        age = time.time() - path.stat().st_mtime
        if age > DISK_TTL_SEC:
            path.unlink(missing_ok=True)
            return None
        return path.read_bytes()
    except OSError:
        return None


def _disk_put(key: str, data: bytes) -> None:
    path = _disk_path(key)
    try:
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError:
        logger.debug("photo cache write failed key=%s", key)


def cache_get(file_id: str, size: str = "full") -> tuple[bytes, str] | None:
    key = photo_cache_key(file_id, size)
    mem = _mem_get(key)
    if mem:
        return mem
    raw = _disk_get(key)
    if raw is None:
        return None
    content_type = "image/jpeg" if size == "thumb" else "image/jpeg"
    if size == "thumb":
        _mem_put(key, raw, content_type)
    return raw, content_type


def cache_put(file_id: str, size: str, data: bytes, content_type: str = "image/jpeg") -> None:
    key = photo_cache_key(file_id, size)
    _disk_put(key, data)
    if size == "thumb":
        _mem_put(key, data, content_type)


async def download_telegram_file(file_id: str) -> tuple[bytes, str]:
    """Скачивает оригинал из Telegram. Результат кладёт на диск."""
    cached = cache_get(file_id, "full")
    if cached:
        return cached

    import aiohttp
    from admin_moderation import candidate_tokens_for_file

    tokens = await candidate_tokens_for_file(file_id)
    if not tokens:
        raise FileNotFoundError("token")
    preferred = _TOKEN_HIT.get(file_id)
    if preferred:
        tokens = [preferred] + [t for t in tokens if t != preferred]

    last_gone = False
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for token in tokens:
            try:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getFile",
                    params={"file_id": file_id},
                ) as resp:
                    data = await resp.json(content_type=None)
            except Exception:
                continue
            if not data.get("ok"):
                desc = str((data.get("description") or "")).lower()
                if "not found" in desc or "wrong file" in desc:
                    last_gone = True
                continue
            file_path = (data.get("result") or {}).get("file_path")
            if not file_path:
                continue
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            try:
                async with session.get(file_url) as img_resp:
                    if img_resp.status != 200:
                        continue
                    content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                    content = await img_resp.read()
            except Exception:
                continue
            if not content:
                continue
            _TOKEN_HIT[file_id] = token
            cache_put(file_id, "full", content, content_type)
            return content, content_type

    if last_gone:
        raise FileNotFoundError("gone")
    raise FileNotFoundError("unavailable")


async def load_telegram_photo(file_id: str, size: str = "full") -> tuple[bytes, str]:
    kind = normalize_photo_size(size)
    if kind == "thumb":
        cached = cache_get(file_id, "thumb")
        if cached:
            return cached
        full, _ctype = await download_telegram_file(file_id)
        try:
            thumb = make_thumb_jpeg(full)
            cache_put(file_id, "thumb", thumb, "image/jpeg")
            return thumb, "image/jpeg"
        except Exception:
            logger.exception("thumb encode failed, serving original")
            return full, _ctype or "image/jpeg"
    return await download_telegram_file(file_id)


