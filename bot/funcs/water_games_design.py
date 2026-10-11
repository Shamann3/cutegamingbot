# -*- coding: utf-8 -*-
"""Тексты водных игр. Живой файл лежит в server/py, панель и бот читают его."""
from __future__ import annotations

import sys
from pathlib import Path

_py = Path(__file__).resolve().parents[2] / "server" / "py"
if str(_py) not in sys.path:
    sys.path.insert(0, str(_py))

from water_games import design as _impl

for _key, _value in vars(_impl).items():
    if _key.startswith("__"):
        continue
    globals()[_key] = _value
