# -*- coding: utf-8 -*-
"""Тексты Бонуса +. Правьте server/flame_bonus_plus_copy.py."""
from __future__ import annotations

import sys
from pathlib import Path

_server = Path(__file__).resolve().parents[2] / "server"
if str(_server) not in sys.path:
    sys.path.insert(0, str(_server))

import flame_bonus_plus_copy as _impl

for _key, _value in vars(_impl).items():
    if _key.startswith("__"):
        continue
    globals()[_key] = _value
