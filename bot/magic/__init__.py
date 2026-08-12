# -*- coding: utf-8 -*-
"""
Мэджик — единая система управления всеми inline-кнопками.

════════════════════════════════════════════════════════════
ГДЕ МЕНЯТЬ НАСТРОЙКИ
════════════════════════════════════════════════════════════
  bot/magic/config.py       ← цифры, режимы, переключатели
  bot/magic/priorities.py   ← какие callback = игры/магазин
  bot/magic/audit.py        ← цикл: каждый файл → под Мэджик
                              (или: magic.bind_all_inline())

════════════════════════════════════════════════════════════
БЫСТРЫЙ СТАРТ
════════════════════════════════════════════════════════════
  from bot.magic import magic, btn, markup, fire_answer, install_magic

  install_magic(dp)   # один раз при старте

  kb = markup([[btn("🌴 Ок", callback_data="ok")]])
  fire_answer(callback)

  # на лету:
  magic.set_mode("strict")
  magic.tune(debounce_sec=0.5)
  magic.add_priority_prefix("mygame_")
  magic.force_recover()   # если кнопки «залипли» после долгого аптайма
  print(magic.show_config())

Что даёт Мэджик каждому callback_query:
  • ранний/идемпотентный answer (без залипающих «часиков»)
  • антиспам и защита от наплыва (per-user + global)
  • debounce одинаковых кликов
  • приоритет игр и магазина
  • тихое гашение спиннера при блоке
  • самолечение при долгом аптайме (stale inflight + редкий rebind)
"""
from __future__ import annotations

from bot.magic.config import CFG, MagicConfig, get_config
from bot.magic.core import Magic, magic
from bot.magic.buttons import btn, markup, row, simple_kb
from bot.magic.answer import fire_answer, safe_answer
from bot.magic.install import install_magic, start_magic_health, attached_dispatcher_count
from bot.magic.limits import is_priority
from bot.magic.audit import run_magic_audit

__all__ = [
    "Magic",
    "magic",
    "CFG",
    "MagicConfig",
    "get_config",
    "btn",
    "markup",
    "row",
    "simple_kb",
    "fire_answer",
    "safe_answer",
    "install_magic",
    "start_magic_health",
    "attached_dispatcher_count",
    "is_priority",
    "run_magic_audit",
]
