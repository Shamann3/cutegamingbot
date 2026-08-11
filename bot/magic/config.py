# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║                     МЭДЖИК — ГЛАВНЫЙ ФАЙЛ НАСТРОЕК                        ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  Меняй значения в секции «БЫСТРЫЕ НАСТРОЙКИ» ниже.                       ║
║  После правки файла — перезапусти бота.                                  ║
║                                                                          ║
║  Или меняй на лету (без перезапуска), из любого места кода:              ║
║                                                                          ║
║      from bot.magic import magic                                         ║
║                                                                          ║
║      magic.set_mode("strict")     # жёстче                               ║
║      magic.set_mode("balanced")   # по умолчанию                         ║
║      magic.set_mode("fast")       # мягче / быстрее для игроков          ║
║                                                                          ║
║      magic.tune(debounce_sec=0.5, user_max_clicks=8)                     ║
║      magic.add_priority_prefix("mygame_")                                ║
║      magic.add_priority_exact("my_stub")                                 ║
║      print(magic.show_config())                                          ║
║                                                                          ║
║  Приоритеты игр/магазина:  bot/magic/priorities.py                       ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional, Set


# ══════════════════════════════════════════════════════════════════════════
# БЫСТРЫЕ НАСТРОЙКИ  ←←←  обычно достаточно менять только здесь
# ══════════════════════════════════════════════════════════════════════════

# Режим работы. Один из: "strict" | "balanced" | "fast"
#   strict   — максимум защиты (если кто-то пытается положить бота)
#   balanced — баланс защиты и скорости (рекомендуется)
#   fast     — игры/кнопки ощущаются максимально «лёгкими»
MODE: str = "balanced"

# Включить всю систему Мэджик (False = middleware не ставится)
ENABLED: bool = True

# При блоке клика — тихо гасить «часики» БЕЗ текста/alert
# (для пользователя выглядит как мгновенный отказ, без всплывашек)
SILENT_BLOCK: bool = True

# Патчить InlineKeyboardButton/Markup + rebind модулей проекта
# (логика кнопок НЕ меняется, только учёт/единая цепь)
PATCH_KEYBOARDS: bool = True

# Полный аудит при старте: сканирует каждый .py и связывает InlineKeyboard* с Мэджик
# (вызывается из install_magic / start_magic_health; можно вручную: magic.bind_all_inline())
RUN_FULL_AUDIT_ON_START: bool = True

# ── Telegram INLINE MODE (@бот запрос в любом чате) ──────────────────────────
# Отдельно от inline-кнопок. Нужно, чтобы режим не зависал на долгом аптайме.
INLINE_QUERY_PROTECT: bool = True
# Сколько секунд максимум ждём handler inline_query (Telegram ждёт быстрый ответ)
INLINE_QUERY_TIMEOUT_SEC: float = 4.5

# РАННИЙ пустой answer (гасит «часики» до конца handler).
# ВАЖНО: Telegram даёт только ОДИН answer на callback.
# Если поставить > 0 — show_alert / текст ошибки из игр ПРОПАДУТ
# (Мэджик успеет ответить пусто раньше handler).
# Держи 0.0 — алерты работают; спиннер гасится в finally или по STUCK_*.
AUTO_ANSWER_DELAY_SEC: float = 0.0

# Если handler завис и сам не ответил — погасить часики через N сек
# (страховка, не мешает обычным show_alert)
STUCK_ANSWER_DELAY_SEC: float = 8.0

# Как часто самолечение чистит память/кэши (секунды)
HEALTH_INTERVAL_SEC: float = 300.0

# Порог лагов event-loop, после которого включается тихий режим TG-логгера
HEALTH_LAG_SAMPLE_SEC: float = 0.25
HEALTH_LAG_WARN_SEC: float = 0.35
HEALTH_PENDING_WARN: int = 800
HEALTH_INFLIGHT_WARN: int = 300


# ─── Ручные оверрайды поверх режима ───────────────────────────────────────
# Оставь None — возьмётся значение из выбранного MODE.
# Поставь число — оно ПОБЕДИТ значение режима.
#
# Пример: хочешь жёстче debounce только для обычных кнопок:
#   OVERRIDE_DEBOUNCE_SEC = 0.8

OVERRIDE_USER_MAX_CLICKS: Optional[int] = None
OVERRIDE_USER_WINDOW_SEC: Optional[float] = None
OVERRIDE_DEBOUNCE_SEC: Optional[float] = None

OVERRIDE_PRIO_USER_MAX_CLICKS: Optional[int] = None
OVERRIDE_PRIO_USER_WINDOW_SEC: Optional[float] = None
OVERRIDE_PRIO_DEBOUNCE_SEC: Optional[float] = None

OVERRIDE_GLOBAL_INFLIGHT: Optional[int] = None
OVERRIDE_PRIO_GLOBAL_INFLIGHT: Optional[int] = None

OVERRIDE_STRIKE_WINDOW_SEC: Optional[float] = None
OVERRIDE_STRIKE_LIMIT: Optional[int] = None
OVERRIDE_COOLDOWN_SEC: Optional[float] = None
OVERRIDE_PRIO_COOLDOWN_SEC: Optional[float] = None

OVERRIDE_TRIM_IDLE_SEC: Optional[float] = None
OVERRIDE_TRIM_MAX_USERS: Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════
# ПРЕСЕТЫ РЕЖИМОВ
# ══════════════════════════════════════════════════════════════════════════
# Можно править сами пресеты — set_mode() подхватит новые цифры.
#
# Что значит каждое поле (коротко):
#   user_max_clicks      — сколько кликов обычной кнопки за окно
#   user_window_sec      — длина окна для обычных кнопок (сек)
#   debounce_sec         — мин. пауза между одинаковыми обычными кликами
#   prio_*               — то же самое, но для игр/магазина (быстрее)
#   global_inflight_soft — сколько handler'ов одновременно «в полёте»
#   strike_* / cooldown_ — после серии блоков → тихий бан на N секунд
#   trim_*               — чистка памяти неактивных пользователей

PRESETS: Dict[str, Dict[str, Any]] = {
    # Жёсткая защита: сложнее зафлудить бота
    "strict": {
        "user_max_clicks": 4,
        "user_window_sec": 2.0,
        "debounce_sec": 0.85,
        "prio_user_max_clicks": 24,
        "prio_user_window_sec": 2.0,
        "prio_debounce_sec": 0.12,
        "global_inflight_soft": 100,
        "prio_global_inflight_soft": 200,
        "strike_window_sec": 8.0,
        "strike_limit": 8,
        "cooldown_sec": 18.0,
        "prio_cooldown_sec": 4.0,
        "trim_idle_sec": 240.0,
        "trim_max_users": 60_000,
    },
    # Баланс (по умолчанию) — то, что стоит в проде сейчас
    "balanced": {
        "user_max_clicks": 6,
        "user_window_sec": 2.0,
        "debounce_sec": 0.65,
        "prio_user_max_clicks": 36,
        "prio_user_window_sec": 2.0,
        "prio_debounce_sec": 0.08,
        "global_inflight_soft": 140,
        "prio_global_inflight_soft": 260,
        "strike_window_sec": 8.0,
        "strike_limit": 10,
        "cooldown_sec": 12.0,
        "prio_cooldown_sec": 3.0,
        "trim_idle_sec": 300.0,
        "trim_max_users": 80_000,
    },
    # Быстрее для игроков (защита чуть мягче)
    "fast": {
        "user_max_clicks": 10,
        "user_window_sec": 2.0,
        "debounce_sec": 0.40,
        "prio_user_max_clicks": 48,
        "prio_user_window_sec": 2.0,
        "prio_debounce_sec": 0.05,
        "global_inflight_soft": 180,
        "prio_global_inflight_soft": 320,
        "strike_window_sec": 8.0,
        "strike_limit": 14,
        "cooldown_sec": 8.0,
        "prio_cooldown_sec": 2.0,
        "trim_idle_sec": 360.0,
        "trim_max_users": 100_000,
    },
}


# ══════════════════════════════════════════════════════════════════════════
# ВНУТРЕННЯЯ МОДЕЛЬ (обычно руками не трогают)
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class MagicConfig:
    """Живой снимок настроек Мэджик (применяется к limits/middleware/health)."""

    mode: str = "balanced"
    enabled: bool = True
    silent_block: bool = True
    patch_keyboards: bool = True
    # 0.0 = не отвечать заранее (нужно для show_alert во всех играх/системах)
    auto_answer_delay_sec: float = 0.0
    stuck_answer_delay_sec: float = 8.0
    inline_query_protect: bool = True
    inline_query_timeout_sec: float = 4.5

    health_interval_sec: float = 300.0
    health_lag_sample_sec: float = 0.25
    health_lag_warn_sec: float = 0.35
    health_pending_warn: int = 800
    health_inflight_warn: int = 300

    # лимиты (копия активных значений)
    user_max_clicks: int = 6
    user_window_sec: float = 2.0
    debounce_sec: float = 0.65
    prio_user_max_clicks: int = 36
    prio_user_window_sec: float = 2.0
    prio_debounce_sec: float = 0.08
    global_inflight_soft: int = 140
    prio_global_inflight_soft: int = 260
    strike_window_sec: float = 8.0
    strike_limit: int = 10
    cooldown_sec: float = 12.0
    prio_cooldown_sec: float = 3.0
    trim_idle_sec: float = 300.0
    trim_max_users: int = 80_000

    # приоритеты (mutable — можно дополнять на лету)
    priority_exact: Set[str] = field(default_factory=set)
    priority_prefixes: List[str] = field(default_factory=list)

    # ── фабрика из «быстрых настроек» модуля ──────────────────────────────

    @classmethod
    def from_file_defaults(cls) -> "MagicConfig":
        """Собрать конфиг из констант вверху этого файла + priorities.py."""
        from bot.magic.priorities import PRIORITY_EXACT, PRIORITY_PREFIXES

        mode = str(MODE or "balanced").strip().lower()
        if mode not in PRESETS:
            mode = "balanced"

        cfg = cls(
            mode=mode,
            enabled=bool(ENABLED),
            silent_block=bool(SILENT_BLOCK),
            patch_keyboards=bool(PATCH_KEYBOARDS),
            auto_answer_delay_sec=float(AUTO_ANSWER_DELAY_SEC),
            stuck_answer_delay_sec=float(STUCK_ANSWER_DELAY_SEC),
            inline_query_protect=bool(INLINE_QUERY_PROTECT),
            inline_query_timeout_sec=float(INLINE_QUERY_TIMEOUT_SEC),
            health_interval_sec=float(HEALTH_INTERVAL_SEC),
            health_lag_sample_sec=float(HEALTH_LAG_SAMPLE_SEC),
            health_lag_warn_sec=float(HEALTH_LAG_WARN_SEC),
            health_pending_warn=int(HEALTH_PENDING_WARN),
            health_inflight_warn=int(HEALTH_INFLIGHT_WARN),
            priority_exact=set(PRIORITY_EXACT),
            priority_prefixes=list(PRIORITY_PREFIXES),
        )
        cfg.apply_mode(mode, keep_overrides=True)
        return cfg

    # ── режимы / оверрайды ────────────────────────────────────────────────

    def apply_mode(self, mode: str, *, keep_overrides: bool = True) -> None:
        """Применить пресет. keep_overrides=True учитывает OVERRIDE_* из файла."""
        mode = str(mode or "balanced").strip().lower()
        if mode not in PRESETS:
            raise ValueError(
                f"Неизвестный режим Мэджик: {mode!r}. "
                f"Доступно: {', '.join(sorted(PRESETS))}"
            )
        self.mode = mode
        for key, value in PRESETS[mode].items():
            setattr(self, key, value)

        if keep_overrides:
            self._apply_file_overrides()

    def _apply_file_overrides(self) -> None:
        """Наложить OVERRIDE_* из верхней секции файла (если не None)."""
        mapping = {
            "user_max_clicks": OVERRIDE_USER_MAX_CLICKS,
            "user_window_sec": OVERRIDE_USER_WINDOW_SEC,
            "debounce_sec": OVERRIDE_DEBOUNCE_SEC,
            "prio_user_max_clicks": OVERRIDE_PRIO_USER_MAX_CLICKS,
            "prio_user_window_sec": OVERRIDE_PRIO_USER_WINDOW_SEC,
            "prio_debounce_sec": OVERRIDE_PRIO_DEBOUNCE_SEC,
            "global_inflight_soft": OVERRIDE_GLOBAL_INFLIGHT,
            "prio_global_inflight_soft": OVERRIDE_PRIO_GLOBAL_INFLIGHT,
            "strike_window_sec": OVERRIDE_STRIKE_WINDOW_SEC,
            "strike_limit": OVERRIDE_STRIKE_LIMIT,
            "cooldown_sec": OVERRIDE_COOLDOWN_SEC,
            "prio_cooldown_sec": OVERRIDE_PRIO_COOLDOWN_SEC,
            "trim_idle_sec": OVERRIDE_TRIM_IDLE_SEC,
            "trim_max_users": OVERRIDE_TRIM_MAX_USERS,
        }
        for key, value in mapping.items():
            if value is not None:
                setattr(self, key, value)

    def tune(self, **kwargs: Any) -> List[str]:
        """
        Точечно поменять настройки.

        Пример:
            cfg.tune(debounce_sec=0.5, prio_debounce_sec=0.06)
        """
        allowed = {f.name for f in fields(self)} - {
            "priority_exact",
            "priority_prefixes",
        }
        changed: List[str] = []
        for key, value in kwargs.items():
            if key not in allowed:
                raise KeyError(
                    f"Неизвестная настройка: {key!r}. "
                    f"Смотри magic.show_config() / поля MagicConfig."
                )
            setattr(self, key, value)
            changed.append(key)
        return changed

    # ── приоритеты ────────────────────────────────────────────────────────

    def add_priority_exact(self, *items: str) -> int:
        """Добавить точные callback_data в приоритет. Вернёт сколько новых."""
        n = 0
        for it in items:
            s = str(it or "").strip()
            if not s:
                continue
            if s not in self.priority_exact:
                self.priority_exact.add(s)
                n += 1
        return n

    def add_priority_prefix(self, *items: str) -> int:
        """Добавить префиксы в приоритет. Вернёт сколько новых."""
        n = 0
        existing = set(self.priority_prefixes)
        for it in items:
            s = str(it or "").strip()
            if not s or s in existing:
                continue
            self.priority_prefixes.append(s)
            existing.add(s)
            n += 1
        return n

    def is_priority(self, data: str) -> bool:
        """Проверка: этот callback идёт по быстрому каналу?"""
        d = str(data or "")
        if not d:
            return False
        if d in self.priority_exact or d.lower() in self.priority_exact:
            return True
        dl = d.lower()
        for p in self.priority_prefixes:
            if d.startswith(p) or dl.startswith(p.lower()):
                return True
        return False

    # ── экспорт в limits / отображение ────────────────────────────────────

    def limits_kwargs(self) -> Dict[str, Any]:
        """Поля, которые нужно проставить в MagicLimits."""
        return {
            "user_max_clicks": int(self.user_max_clicks),
            "user_window_sec": float(self.user_window_sec),
            "debounce_sec": float(self.debounce_sec),
            "prio_user_max_clicks": int(self.prio_user_max_clicks),
            "prio_user_window_sec": float(self.prio_user_window_sec),
            "prio_debounce_sec": float(self.prio_debounce_sec),
            "global_inflight_soft": int(self.global_inflight_soft),
            "prio_global_inflight_soft": int(self.prio_global_inflight_soft),
            "strike_window_sec": float(self.strike_window_sec),
            "strike_limit": int(self.strike_limit),
            "cooldown_sec": float(self.cooldown_sec),
            "prio_cooldown_sec": float(self.prio_cooldown_sec),
            "trim_idle_sec": float(self.trim_idle_sec),
            "trim_max_users": int(self.trim_max_users),
        }

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority_exact"] = sorted(self.priority_exact)
        d["priority_prefixes_count"] = len(self.priority_prefixes)
        # полный список префиксов большой — в show даём count + первые
        d["priority_prefixes_head"] = list(self.priority_prefixes)[:12]
        return d

    def show(self) -> str:
        """Человекочитаемый статус настроек."""
        lines = [
            "════ МЭДЖИК CONFIG ════",
            f"mode                  = {self.mode}",
            f"enabled               = {self.enabled}",
            f"silent_block          = {self.silent_block}",
            f"patch_keyboards       = {self.patch_keyboards}",
            f"auto_answer_delay_sec = {self.auto_answer_delay_sec}  (0=алерты OK)",
            f"stuck_answer_delay_sec= {self.stuck_answer_delay_sec}",
            f"inline_query_protect  = {self.inline_query_protect}",
            f"inline_query_timeout  = {self.inline_query_timeout_sec}s",
            f"health_interval_sec   = {self.health_interval_sec}",
            "── обычные кнопки ──",
            f"  max_clicks/window   = {self.user_max_clicks} / {self.user_window_sec}s",
            f"  debounce            = {self.debounce_sec}s",
            f"  inflight            = {self.global_inflight_soft}",
            "── игры + магазин (priority) ──",
            f"  max_clicks/window   = {self.prio_user_max_clicks} / {self.prio_user_window_sec}s",
            f"  debounce            = {self.prio_debounce_sec}s",
            f"  inflight            = {self.prio_global_inflight_soft}",
            "── анти-абьюз ──",
            f"  strike {self.strike_limit} / {self.strike_window_sec}s → "
            f"cooldown {self.cooldown_sec}s (prio {self.prio_cooldown_sec}s)",
            f"── priority exact={len(self.priority_exact)} "
            f"prefixes={len(self.priority_prefixes)} ──",
        ]
        return "\n".join(lines)


# Глобальный конфиг процесса (один на весь бот)
CFG: MagicConfig = MagicConfig.from_file_defaults()


def reload_config_from_file() -> MagicConfig:
    """
    Перечитать константы из этого модуля + priorities.py.

    Внимание: в уже запущенном процессе Python не перечитывает файл сам.
    Чтобы подтянуть правки с диска — нужен рестарт бота,
    либо правь через magic.set_mode / magic.tune.
    """
    global CFG
    CFG = MagicConfig.from_file_defaults()
    return CFG


def get_config() -> MagicConfig:
    return CFG
