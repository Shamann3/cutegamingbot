import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("proof_blobs", ROOT / "server" / "proof_blobs.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sniff_image_type = _mod.sniff_image_type


def test_sniff_knows_a_real_photo():
    assert sniff_image_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert sniff_image_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert sniff_image_type(b"GIF89a") == "image/gif"
    assert sniff_image_type(b"RIFF0000WEBP") == "image/webp"
    assert sniff_image_type(b"not a photo") == ""
    assert sniff_image_type(b"\xff\xd8\xff", "text/html") == "image/jpeg"
    assert sniff_image_type(b"abc", "image/jpeg") == "image/jpeg"


def test_photo_proxy_serves_the_saved_copy_first():
    root = ROOT
    cache = (root / "server" / "telegram_file_cache.py").read_text(encoding="utf-8")
    start = cache.index("async def download_telegram_file")
    chunk = cache[start:cache.index("tokens = await candidate_tokens_for_file")]
    assert "load_proof_blob" in chunk
    assert "save_proof_blob" in cache[start:]

    bot = (root / "bot" / "admins" / "proof_blob.py").read_text(encoding="utf-8")
    assert "staff_proof_blobs" in bot
    assert "schedule_proof_save" in bot
    for name in ("ban.py", "mute.py", "kick.py", "warn.py"):
        assert "schedule_proof_save" in (root / "bot" / "admins" / name).read_text(encoding="utf-8")
