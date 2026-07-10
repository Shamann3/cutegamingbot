"""Smoke-test: bot and server inventory codecs are mutually compatible."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot" / "db_create"))
sys.path.insert(0, str(ROOT / "server"))

from items_codec import decode_items as bot_decode, encode_items as bot_encode
from json_db_codec import decode_json_payload as srv_decode, encode_json_payload as srv_encode

sample = {"Ключ": 7, "Бонус": 1, "Вода": 98}

# 1. Bot roundtrip
bot_str = bot_encode(sample)
assert bot_decode(bot_str) == sample, f"bot roundtrip fail: {bot_str}"

# 2. Server new format
srv_str = srv_encode(sample)
assert srv_decode(srv_str) == sample, f"srv decode fail: {srv_str}"
assert bot_decode(srv_str) == sample, f"bot decode srv fail: {srv_str}"

# 3. Legacy wrapped format
inner = json.dumps(sample, ensure_ascii=True, separators=(", ", ": "))
legacy = '"' + inner.replace('"', '""') + '"'
assert bot_decode(legacy) == sample, f"bot decode legacy fail: {legacy!r}"
assert srv_decode(legacy) == sample, f"srv decode legacy fail: {legacy!r}"

# 4. Cross-write
assert srv_decode(bot_encode({"Ключ": 3})) == {"Ключ": 3}
assert bot_decode(srv_encode({"Вода": 5})) == {"Вода": 5}

# 5. dict passthrough
assert bot_decode(sample) == sample

print("ALL TESTS PASSED")
print("bot encode:", bot_str[:80])
print("srv encode:", srv_str[:80])
print("formats match:", bot_str == srv_str)
