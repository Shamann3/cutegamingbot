import random
import asyncio
from datetime import datetime
from typing import Optional

from main import *
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

# ═════════════════════════════════════════════════════════════
# ЛОКАЛЬНАЯ ОТЛАДКА

def _log(*args):
    if BONUS_DEBUG:
        print("[BONUS]", *args)

