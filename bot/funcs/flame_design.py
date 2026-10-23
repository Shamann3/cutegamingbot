# -*- coding: utf-8 -*-
"""Тексты огонька. Правьте server/flame_copy.py — этот файл только показывает его боту."""
from __future__ import annotations

import sys
from pathlib import Path

_server = Path(__file__).resolve().parents[2] / "server"
if str(_server) not in sys.path:
    sys.path.insert(0, str(_server))

import flame_copy as _impl

for _key, _value in vars(_impl).items():
    if _key.startswith("__"):
        continue
    globals()[_key] = _value
