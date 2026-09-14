"""Чистая логика TikTok-заработка: ники, ссылки, просмотры, хеши, тексты."""

from __future__ import annotations

import hashlib
import io
import math
import random
import re
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

NICK_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")
MAX_NICKS = 3
PHOTOS_REQUIRED = 15
COMMENT_REWARD = 5
VIEWS_PER_UNIT = 1000
KUT_PER_UNIT = 30
RECHECK_DAYS = 7
HASH_THRESHOLD = 10
VIDEO_CANONICAL_RE = re.compile(r"/video/(\d+)")
SHORT_CODE_RE = re.compile(r"tiktok\.com/(?:t/)?([A-Za-z0-9]+)/?$")

DEFAULT_COMMENT_TAG = "тг звезды"
DEFAULT_VIDEO_HASHTAG = "@CuteGamingBot"

DEFAULT_REJECT_REASONS: list[dict[str, str]] = [
    {"id": "bad_link", "label": "Некорректная ссылка"},
    {"id": "no_hashtag", "label": "Не указан хештег проекта"},
    {"id": "not_about_bot", "label": "Ролик не про бота"},
    {"id": "adult", "label": "18+ контент"},
    {"id": "insult", "label": "Оскорбление проекта"},
    {"id": "repost", "label": "Чужой ролик / репост"},
    {"id": "watermark", "label": "Водяной знак другого проекта"},
    {"id": "low_quality", "label": "Низкое качество / набор слайдов без смысла"},
]

BARNUM_REJECTS: tuple[str, ...] = (
    "Эта пачка не прошла проверку. Часть кадров выглядит так, будто задание собрано не так, как мы просили. Сделай 15 разных комментариев под роликами с нужным тегом, лайк на своём, свежие скрины — и пришли ещё раз.",
    "Проверка смотрит не только на количество кадров, а на то, как собрана вся пачка. Сейчас она выглядит незавершённой. Сделай 15 разных комментариев под роликами с нужным тегом, лайк на своём — и пришли новые скрины.",
    "Мы не смогли принять эту пачку: по ней не складывается цельная картина выполнения. Попробуй ещё раз с нуля: 15 свежих скринов, один комментарий — один кадр.",
    "Эта сдача не прошла. Иногда так бывает, если кадры слишком похожи друг на друга или не показывают задание целиком. Собери новую пачку и отправь снова.",
)

TAB_TEASERS: dict[str, str] = {
    "comments": "Эту очередь разбирают те, кому доверили живые скрины. Когда откроют — окажешься здесь.",
    "videos": "Ссылку и просмотры видят только те, кого пустили к роликам. Должность выше — дверь ближе.",
    "live": "Живые ролики и доплаты за тысячи просмотров. Сюда пускают после доверия к обычной очереди.",
    "archive": "Архив — память раздела. Его открывают тем, кто уже умеет закрывать дела, а не только смотреть.",
    "settings": "Награды, теги и причины отказа. Эту комнату оставляют тем, кто отвечает за правила, не только за проверку.",
}


def normalize_nick(raw: str) -> str:
    nick = (raw or "").strip()
    if "tiktok.com" in nick.lower() and "/@" in nick:
        nick = nick.split("/@", 1)[1]
    nick = nick.split("/")[0].strip()
    nick = nick.split("?")[0].strip()
    nick = nick.lstrip("@").strip()
    return nick.lower()


def validate_nick(raw: str) -> str:
    nick = normalize_nick(raw)
    if not NICK_RE.match(nick):
        raise ValueError("Ник: латиница, цифры, точка или _, от 2 до 24 символов")
    return nick


def parse_tiktok_url(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Это не похоже на ссылку TikTok. Пришли tiktok.com или vm.tiktok.com.")
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.netloc or "").lower().lstrip("www.")
    if host.startswith("www."):
        host = host[4:]
    allowed = (
        host == "tiktok.com"
        or host.endswith(".tiktok.com")
        or host in {"vm.tiktok.com", "vt.tiktok.com"}
    )
    if not allowed:
        raise ValueError("Это не похоже на ссылку TikTok. Пришли tiktok.com или vm.tiktok.com.")
    path = parsed.path or ""
    match = VIDEO_CANONICAL_RE.search(path)
    if match:
        video_id = match.group(1)
        return {
            "url": f"https://www.tiktok.com{path}" if path.startswith("/") else text,
            "canonical": f"video:{video_id}",
            "videoId": video_id,
        }
    if host in {"vm.tiktok.com", "vt.tiktok.com"}:
        code = path.strip("/").split("/")[0]
        if not code:
            raise ValueError("Это не похоже на ссылку TikTok. Пришли tiktok.com или vm.tiktok.com.")
        return {"url": text, "canonical": f"short:{code.lower()}", "videoId": ""}
    short = SHORT_CODE_RE.search(host + path)
    if "tiktok.com/t/" in f"{host}{path}" or re.search(r"/t/[A-Za-z0-9]+", path):
        code = path.rstrip("/").split("/")[-1]
        return {"url": text, "canonical": f"short:{code.lower()}", "videoId": ""}
    qs = parse_qs(parsed.query)
    if qs.get("share_item_id"):
        video_id = str(qs["share_item_id"][0])
        return {"url": text, "canonical": f"video:{video_id}", "videoId": video_id}
    raise ValueError("Это не похоже на ссылку TikTok. Пришли tiktok.com или vm.tiktok.com.")


def thousands_from_views(views: int) -> int:
    views = int(views or 0)
    if views < 0:
        raise ValueError("Просмотры не могут быть меньше 0")
    return views // VIEWS_PER_UNIT


def kut_for_thousands(thousands: int, kut_per_unit: int = KUT_PER_UNIT) -> int:
    return max(0, int(thousands)) * int(kut_per_unit)


def kut_for_views(views: int, kut_per_unit: int = KUT_PER_UNIT) -> int:
    return kut_for_thousands(thousands_from_views(views), kut_per_unit)


def payout_delta(old_views: int, new_views: int, kut_per_unit: int = KUT_PER_UNIT) -> dict[str, int]:
    if int(new_views) < int(old_views):
        raise ValueError("Новые просмотры меньше уже учтённых")
    old_t = thousands_from_views(old_views)
    new_t = thousands_from_views(new_views)
    delta_t = new_t - old_t
    return {
        "oldViews": int(old_views),
        "newViews": int(new_views),
        "oldThousands": old_t,
        "newThousands": new_t,
        "deltaThousands": delta_t,
        "kut": kut_for_thousands(delta_t, kut_per_unit),
    }


def pick_barnum(
    rng: random.Random | None = None,
    texts: Iterable[str] | None = None,
) -> str:
    pool = [t.strip() for t in (texts or BARNUM_REJECTS) if str(t).strip()]
    if not pool:
        pool = list(BARNUM_REJECTS)
    src = rng or random
    return src.choice(pool)


def next_queue_item(items: list[dict[str, Any]], current_id: int | None) -> dict[str, Any] | None:
    if not items:
        return None
    if current_id is None:
        return items[0]
    for index, item in enumerate(items):
        try:
            if int(item.get("id")) == int(current_id):
                return items[index + 1] if index + 1 < len(items) else None
        except (TypeError, ValueError):
            continue
    return items[0]


def hamming_hex(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def hashes_similar(left: dict[str, str], right: dict[str, str], threshold: int = HASH_THRESHOLD) -> bool:
    scores = []
    for key in ("ahash", "dhash", "phash"):
        a, b = left.get(key) or "", right.get(key) or ""
        if a and b:
            scores.append(hamming_hex(a, b))
    if not scores:
        return False
    return min(scores) <= threshold


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def find_matches(
    photos: list[dict[str, Any]],
    library: list[dict[str, Any]],
    *,
    verdicts: dict[tuple[str, str], str] | None = None,
    threshold: int = HASH_THRESHOLD,
) -> list[dict[str, Any]]:
    """Находит похожие пары. photos — текущая пачка, library — история (может включать текущую)."""
    verdicts = verdicts or {}
    found: list[dict[str, Any]] = []
    seen_pairs: set[tuple[Any, Any, Any, Any]] = set()
    for src in photos:
        for other in library:
            if src is other:
                continue
            if src.get("id") and other.get("id") and src["id"] == other["id"]:
                continue
            if src.get("caseId") and other.get("caseId") and src.get("index") == other.get("index"):
                if src["caseId"] == other["caseId"]:
                    if src is other:
                        continue
            if not hashes_similar(src, other, threshold):
                continue
            key = pair_key(src.get("phash") or src.get("ahash") or "", other.get("phash") or other.get("ahash") or "")
            if verdicts.get(key) == "unique":
                continue
            pair_id = (
                src.get("caseId"),
                src.get("index"),
                other.get("caseId"),
                other.get("index"),
            )
            rev = (pair_id[2], pair_id[3], pair_id[0], pair_id[1])
            if pair_id in seen_pairs or rev in seen_pairs:
                continue
            seen_pairs.add(pair_id)
            found.append(
                {
                    "source": src,
                    "match": other,
                    "distance": min(
                        hamming_hex(src.get(k) or "0", other.get(k) or "0")
                        for k in ("ahash", "dhash", "phash")
                        if src.get(k) and other.get(k)
                    ) if any(src.get(k) and other.get(k) for k in ("ahash", "dhash", "phash")) else 64,
                    "verdict": verdicts.get(key),
                }
            )
    found.sort(key=lambda x: x["distance"])
    return found[:48]


def _avg_hash(pixels: list[int], width: int, height: int) -> str:
    mean = sum(pixels) / max(1, len(pixels))
    bits = 0
    for i, p in enumerate(pixels):
        if p >= mean:
            bits |= 1 << i
    return f"{bits:016x}"


def _dhash(pixels: list[int], width: int, height: int) -> str:
    bits = 0
    bit = 0
    for y in range(height):
        row = y * width
        for x in range(width - 1):
            if pixels[row + x] < pixels[row + x + 1]:
                bits |= 1 << bit
            bit += 1
    return f"{bits:016x}"


def _phash(pixels: list[int], size: int = 32) -> str:
    """Упрощённый pHash: DCT по 32×32, берём 8×8 низких частот."""
    vals = [float(p) for p in pixels]
    n = size
    dct = [[0.0] * n for _ in range(n)]
    for u in range(8):
        cu = math.sqrt(1 / n) if u == 0 else math.sqrt(2 / n)
        for v in range(8):
            cv = math.sqrt(1 / n) if v == 0 else math.sqrt(2 / n)
            acc = 0.0
            for y in range(n):
                for x in range(n):
                    acc += vals[y * n + x] * math.cos((2 * x + 1) * u * math.pi / (2 * n)) * math.cos(
                        (2 * y + 1) * v * math.pi / (2 * n)
                    )
            dct[u][v] = cu * cv * acc
    flat = [dct[u][v] for u in range(8) for v in range(8)]
    flat[0] = 0.0
    median = sorted(flat)[len(flat) // 2]
    bits = 0
    for i, val in enumerate(flat):
        if val > median:
            bits |= 1 << i
    return f"{bits:016x}"


def hashes_from_image_bytes(data: bytes) -> dict[str, str]:
    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("L")
    small = image.resize((8, 8), Image.Resampling.BILINEAR)
    dsmall = image.resize((9, 8), Image.Resampling.BILINEAR)
    psmall = image.resize((32, 32), Image.Resampling.BILINEAR)
    ahash = _avg_hash(list(small.getdata()), 8, 8)
    dhash = _dhash(list(dsmall.getdata()), 9, 8)
    phash = _phash(list(psmall.getdata()), 32)
    md5 = hashlib.md5(data).hexdigest()
    return {"ahash": ahash, "dhash": dhash, "phash": phash, "md5": md5}


def format_nicks(nicks: Iterable[str]) -> str:
    items = [f"@{normalize_nick(n)}" for n in nicks if n]
    return "\n".join(items)


def days_left(seconds: float) -> int:
    if seconds <= 0:
        return 0
    return max(1, math.ceil(seconds / 86400))


def recheck_wait_text(seconds: float) -> str:
    days = days_left(seconds)
    word = "день" if days == 1 else ("дня" if days < 5 else "дней")
    return f"Следующая проверка через {days} {word}."
