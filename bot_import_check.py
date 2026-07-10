"""Проверка, что все тяжёлые зависимости main.py установились в образе.
Используется как временный run_command воркера ДО реального запуска main.py,
чтобы отладить сборку без конфликта с ботом на сервере."""
import importlib
import time

mods = [
    "aiogram", "telethon", "pyrogram", "numpy", "PIL", "redis", "asyncpg",
    "bs4", "emoji", "geopy", "timezonefinder", "langdetect", "googletrans",
    "deep_translator", "translate", "praw", "pyowm", "cachetools", "psutil",
    "aiofiles", "aiohttp", "pydantic", "geonamescache", "better_profanity",
    "transliterate", "ntplib", "speedtest", "yandex.Translater",
    "google_trans_new", "libretranslatepy", "fragment_api_lib", "aiosend",
    "pyowm",
]

failed = []
for m in mods:
    try:
        importlib.import_module(m)
        print("ok:", m, flush=True)
    except Exception as e:
        print("FAIL:", m, "->", type(e).__name__, e, flush=True)
        failed.append(m)

if failed:
    print("IMPORT CHECK FAILED:", failed, flush=True)
else:
    print("ALL IMPORTS OK", flush=True)

time.sleep(999999)
