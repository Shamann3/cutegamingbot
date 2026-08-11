# -*- coding: utf-8 -*-
"""
Ядро системы Мэджик — единый контроллер всех inline-кнопок.

────────────────────────────────────────────────────────────
КАК УДОБНО УПРАВЛЯТЬ
────────────────────────────────────────────────────────────
Обычно правь файл:  bot/magic/config.py

На лету (в коде / shell):

    from bot.magic import magic

    magic.set_mode("strict")                 # сменить режим
    magic.tune(debounce_sec=0.5)             # точечно
    magic.add_priority_prefix("mygame_")     # приоритет новой игры
    magic.add_priority_exact("my_stub")
    print(magic.show_config())               # посмотреть текущее
    print(magic.snapshot())                  # статистика кликов

────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from bot.magic.config import CFG, MagicConfig, get_config, reload_config_from_file
from bot.magic.limits import MagicLimits

logger = logging.getLogger("magic")


class Magic:
    """Единый контроллер всех inline-кнопок проекта."""

    def __init__(self, cfg: Optional[MagicConfig] = None) -> None:
        # живой конфиг (тот же объект, что CFG)
        self.cfg: MagicConfig = cfg or get_config()
        # лимиты сразу из конфига
        self.limits = MagicLimits.from_config(self.cfg)
        self.balance_watcher: Any = None
        self._installed = False
        self._health_started = False
        self.stats_callbacks = 0
        self.stats_blocked = 0
        self.stats_buttons_created = 0
        self.stats_markups_created = 0
        self.stats_inline_queries = 0
        self.stats_inline_timeouts = 0
        self.stats_inline_blocked = 0
        self.last_audit: Any = None

    # ── состояние установки ───────────────────────────────────────────────

    @property
    def installed(self) -> bool:
        return bool(self._installed)

    def attach_balance_watcher(self, watcher: Any) -> None:
        self.balance_watcher = watcher

    def mark_installed(self) -> None:
        self._installed = True

    # ── удобное управление настройками ────────────────────────────────────

    def apply_config(self, cfg: Optional[MagicConfig] = None) -> None:
        """
        Применить конфиг к живым лимитам.
        Вызывается автоматически из set_mode / tune / reload.
        """
        if cfg is not None:
            self.cfg = cfg
        self.limits.apply_config(self.cfg)
        logger.info("config applied mode=%s", self.cfg.mode)

    def set_mode(self, mode: str) -> str:
        """
        Сменить режим: "strict" | "balanced" | "fast".

        Пример:
            magic.set_mode("strict")
        """
        self.cfg.apply_mode(mode, keep_overrides=False)
        self.apply_config()
        msg = f"mode → {self.cfg.mode}"
        print(f"✅ [MAGIC] {msg}")
        return self.cfg.mode

    def tune(self, **kwargs: Any) -> List[str]:
        """
        Точечно поменять цифры без смены режима.

        Пример:
            magic.tune(debounce_sec=0.5, prio_debounce_sec=0.06)
            magic.tune(auto_answer_delay_sec=0.03)
        """
        changed = self.cfg.tune(**kwargs)
        self.apply_config()
        print(f"✅ [MAGIC] tune: {', '.join(changed)}")
        return changed

    def add_priority_prefix(self, *prefixes: str) -> int:
        """
        Добавить префиксы игр/магазина в быстрый канал.

        Пример:
            magic.add_priority_prefix("mygame_", "shop_new_")
        """
        n = self.cfg.add_priority_prefix(*prefixes)
        print(f"✅ [MAGIC] +{n} priority prefix(es)")
        return n

    def add_priority_exact(self, *items: str) -> int:
        """
        Добавить точные callback_data в быстрый канал.

        Пример:
            magic.add_priority_exact("my_stub", "pass2")
        """
        n = self.cfg.add_priority_exact(*items)
        print(f"✅ [MAGIC] +{n} priority exact")
        return n

    def is_priority(self, data: str) -> bool:
        """Этот callback в приоритете (игры/магазин)?"""
        return self.cfg.is_priority(data)

    def show_config(self) -> str:
        """Человекочитаемые текущие настройки (для логов/отладки)."""
        text = self.cfg.show()
        print(text)
        return text

    def bind_all_inline(self, *, import_missing: bool = True, dp: Any = None) -> Any:
        """
        Запустить полный цикл: проверить каждый файл проекта
        и связать все InlineKeyboard* с Мэджик.

        Пример:
            magic.bind_all_inline()
        """
        from bot.magic.audit import run_magic_audit

        report = run_magic_audit(dp=dp, import_missing=import_missing, verbose=True)
        self.last_audit = report
        return report

    def reload_from_file(self) -> MagicConfig:
        """
        Пересобрать CFG из констант модуля config.py + priorities.py.

        В уже запущенном процессе Python не читает файл с диска заново —
        для правок на диске нужен рестарт бота.
        Этот метод полезен, если ты менял PRESETS/OVERRIDE в памяти.
        """
        cfg = reload_config_from_file()
        self.cfg = cfg
        self.apply_config()
        print("✅ [MAGIC] config reloaded from module defaults")
        print(self.cfg.show())
        return cfg

    # ── мониторинг ────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        snap = self.limits.snapshot()
        snap.update(
            {
                "installed": int(self._installed),
                "mode": self.cfg.mode,
                "callbacks": self.stats_callbacks,
                "blocked_total": self.stats_blocked,
                "buttons_created": self.stats_buttons_created,
                "markups_created": self.stats_markups_created,
                "inline_queries": self.stats_inline_queries,
                "inline_timeouts": self.stats_inline_timeouts,
                "inline_blocked": self.stats_inline_blocked,
            }
        )
        return snap

    def heal_once(self) -> dict:
        """Один проход самолечения (вызывается health-loop)."""
        out = {"limits": self.limits.trim(), "mode": self.cfg.mode}
        try:
            if self.balance_watcher is not None and hasattr(self.balance_watcher, "trim"):
                out["balance"] = self.balance_watcher.trim()
        except Exception as e:
            out["balance_err"] = repr(e)
        try:
            from bot.utils import telegram_api_logger as tg_log

            if hasattr(tg_log, "trim_softfail_cache"):
                out["tg_softfail"] = tg_log.trim_softfail_cache()
        except Exception as e:
            out["tg_err"] = repr(e)
        # Подхватить модули, которые импортировали ПОСЛЕ старта
        # (новые ссылки InlineKeyboard* → снова под Мэджик)
        try:
            if self.cfg.patch_keyboards:
                from bot.magic.audit import rebind_all_inline_refs

                mods, attrs = rebind_all_inline_refs()
                out["rebind"] = {"modules": mods, "attrs": attrs}
        except Exception as e:
            out["rebind_err"] = repr(e)
        return out


# Глобальный синглтон Мэджик — одна цепь на весь процесс
magic = Magic(CFG)
