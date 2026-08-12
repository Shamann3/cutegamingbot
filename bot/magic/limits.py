# -*- coding: utf-8 -*-
"""
Лимиты Мэджик: жёсткая защита + приоритет игр/магазина.

────────────────────────────────────────────────────────────
ВАЖНО: цифры и приоритеты НЕ правят здесь.
       Меняй bot/magic/config.py  и  bot/magic/priorities.py
────────────────────────────────────────────────────────────

Как работает:
  1) allow(uid, callback_data) — можно ли обработать клик
  2) если нельзя — middleware тихо гасит «часики» (без toast)
  3) игры/магазин идут по priority-каналу (быстрее)
  4) после серии блоков — тихий cooldown (эскалация)
  5) inflight — по токенам; stale-слоты чистятся (защита от «залипания» кнопок)
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from bot.magic.config import MagicConfig


def _cfg():
    """Актуальный конфиг (всегда свежий синглтон)."""
    from bot.magic.config import CFG

    return CFG


def is_priority(data: str) -> bool:
    """Публичная проверка приоритета (читает живой CFG)."""
    return _cfg().is_priority(data)


# совместимость со старым именем
_is_priority = is_priority


@dataclass
class MagicLimits:
    """
    Рабочие лимиты. Значения подставляются из CFG при создании
    и при каждом magic.apply_config() / set_mode() / tune().
    """

    # --- обычные кнопки ---
    user_max_clicks: int = 6
    user_window_sec: float = 2.0
    debounce_sec: float = 0.65

    # --- приоритет: игры + магазин ---
    prio_user_max_clicks: int = 36
    prio_user_window_sec: float = 2.0
    prio_debounce_sec: float = 0.08

    # глобальный soft-потолок одновременных handler'ов
    global_inflight_soft: int = 140
    prio_global_inflight_soft: int = 260

    # анти-абьюз: после серии блоков — тихий cooldown
    strike_window_sec: float = 8.0
    strike_limit: int = 10
    cooldown_sec: float = 12.0
    prio_cooldown_sec: float = 3.0

    trim_idle_sec: float = 300.0
    trim_max_users: int = 80_000
    # handler дольше этого = «осиротевший» inflight (кнопки начинали «зависать»)
    inflight_stale_sec: float = 45.0

    _clicks: Dict[int, Deque[float]] = field(default_factory=dict)
    _prio_clicks: Dict[int, Deque[float]] = field(default_factory=dict)
    _last_data: Dict[int, Tuple[str, float]] = field(default_factory=dict)
    _strikes: Dict[int, Deque[float]] = field(default_factory=dict)
    _cooldown_until: Dict[int, float] = field(default_factory=dict)
    _prio_cooldown_until: Dict[int, float] = field(default_factory=dict)
    # token -> monotonic start; leave(token) обязателен
    _active: Dict[int, float] = field(default_factory=dict)
    _token_seq: int = 0
    _stats_blocked_user: int = 0
    _stats_blocked_debounce: int = 0
    _stats_blocked_global: int = 0
    _stats_blocked_cooldown: int = 0
    _stats_passed: int = 0
    _stats_prio_passed: int = 0
    _stats_stale_inflight: int = 0
    _stats_force_recover: int = 0

    @property
    def _inflight(self) -> int:
        return len(self._active)

    @classmethod
    def from_config(cls, cfg: Optional["MagicConfig"] = None) -> "MagicLimits":
        """Создать лимиты из конфига."""
        c = cfg or _cfg()
        return cls(**c.limits_kwargs())

    def apply_config(self, cfg: Optional["MagicConfig"] = None) -> None:
        """
        Применить конфиг к уже живому объекту.
        Состояние кликов/cooldown НЕ сбрасывается — меняются только пороги.
        """
        c = cfg or _cfg()
        for key, value in c.limits_kwargs().items():
            setattr(self, key, value)

    def _note_block(self, uid: int, now: float) -> None:
        """Учесть блок; при серии блоков — выдать тихий cooldown."""
        q = self._strikes.get(uid)
        if q is None:
            q = deque()
            self._strikes[uid] = q
        q.append(now)
        cutoff = now - self.strike_window_sec
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.strike_limit:
            # эскалация: чем больше страйков подряд — тем дольше бан
            severity = min(4, max(1, len(q) // self.strike_limit))
            base = self.cooldown_sec * severity
            self._cooldown_until[uid] = now + base
            self._prio_cooldown_until[uid] = now + min(
                self.prio_cooldown_sec * severity, base
            )
            q.clear()

    def allow(self, uid: int, data: str) -> Tuple[bool, str]:
        """
        Можно ли пустить клик в handler.

        Возвращает (ok, reason). reason пустой если ok,
        иначе: debounce | user_rate | global_busy | cooldown
        """
        now = time.monotonic()
        data = str(data or "")
        prio = is_priority(data)

        # лёгкая очистка stale inflight на горячем пути (дёшево, раз в N вызовов)
        if (self._token_seq & 31) == 0 and self._active:
            self.trim_stale_inflight()

        until = self._cooldown_until.get(uid)
        if until is not None and now >= until:
            self._cooldown_until.pop(uid, None)
            until = None
        p_until = self._prio_cooldown_until.get(uid)
        if p_until is not None and now >= p_until:
            self._prio_cooldown_until.pop(uid, None)
            p_until = None

        # тихий cooldown: обычные кнопки дольше, игры — короче
        if prio:
            if p_until is not None and now < p_until:
                self._stats_blocked_cooldown += 1
                return False, "cooldown"
        elif until is not None and now < until:
            self._stats_blocked_cooldown += 1
            return False, "cooldown"

        debounce = self.prio_debounce_sec if prio else self.debounce_sec
        prev = self._last_data.get(uid)
        if prev is not None:
            prev_data, prev_ts = prev
            if prev_data == data and (now - prev_ts) < debounce:
                self._stats_blocked_debounce += 1
                self._note_block(uid, now)
                return False, "debounce"
        self._last_data[uid] = (data, now)

        if prio:
            qmap = self._prio_clicks
            max_c = self.prio_user_max_clicks
            win = self.prio_user_window_sec
            gmax = self.prio_global_inflight_soft
        else:
            qmap = self._clicks
            max_c = self.user_max_clicks
            win = self.user_window_sec
            gmax = self.global_inflight_soft

        q = qmap.get(uid)
        if q is None:
            q = deque()
            qmap[uid] = q
        cutoff = now - win
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_c:
            self._stats_blocked_user += 1
            self._note_block(uid, now)
            return False, "user_rate"
        q.append(now)

        if self._inflight >= gmax:
            # перед блокировкой — ещё раз снять протухшие слоты
            dropped = self.trim_stale_inflight()
            if not dropped or self._inflight >= gmax:
                self._stats_blocked_global += 1
                self._note_block(uid, now)
                return False, "global_busy"

        if prio:
            self._stats_prio_passed += 1
        self._stats_passed += 1
        return True, ""

    def enter(self) -> int:
        """Зарегистрировать handler в полёте. Вернуть token для leave()."""
        self._token_seq += 1
        tok = self._token_seq
        self._active[tok] = time.monotonic()
        return tok

    def leave(self, token: Optional[int] = None) -> None:
        """Снять handler из полёта (по token; без token — безопасный no-op)."""
        if token is None:
            return
        self._active.pop(int(token), None)

    def trim_stale_inflight(self, max_age_sec: Optional[float] = None) -> int:
        """Убрать осиротевшие inflight-слоты (handler завис / leave не вызвали)."""
        age = float(
            self.inflight_stale_sec if max_age_sec is None else max_age_sec
        )
        if age <= 0 or not self._active:
            return 0
        now = time.monotonic()
        cutoff = now - age
        stale = [tok for tok, started in self._active.items() if started < cutoff]
        for tok in stale:
            self._active.pop(tok, None)
        n = len(stale)
        if n:
            self._stats_stale_inflight += n
        return n

    def force_recover(self) -> Dict[str, int]:
        """
        Аварийное восстановление при «залипших» кнопках:
        сброс stale inflight + просроченных cooldown.
        """
        self._stats_force_recover += 1
        dropped = self.trim_stale_inflight(
            max_age_sec=min(15.0, float(self.inflight_stale_sec) or 15.0)
        )
        hard = 0
        soft_cap = max(int(self.global_inflight_soft), int(self.prio_global_inflight_soft))
        if self._inflight >= soft_cap:
            hard = len(self._active)
            self._active.clear()
        now = time.monotonic()
        cd = 0
        for store_cd in (self._cooldown_until, self._prio_cooldown_until):
            for uid, until in list(store_cd.items()):
                if until < now:
                    store_cd.pop(uid, None)
                    cd += 1
        return {
            "stale_dropped": dropped,
            "hard_inflight_cleared": hard,
            "cooldowns_cleared": cd,
            "inflight_now": self._inflight,
        }

    def trim(self) -> Dict[str, int]:
        """Почистить idle-пользователей и просроченные cooldown."""
        now = time.monotonic()
        idle_before = now - self.trim_idle_sec
        removed = 0
        stale_inf = self.trim_stale_inflight()

        for store in (self._clicks, self._prio_clicks):
            for uid, q in list(store.items()):
                if not q or q[-1] < idle_before:
                    store.pop(uid, None)
                    removed += 1

        for uid, q in list(self._strikes.items()):
            if not q or q[-1] < idle_before:
                self._strikes.pop(uid, None)
                removed += 1

        for uid, (_data, ts) in list(self._last_data.items()):
            if ts < idle_before:
                self._last_data.pop(uid, None)
                removed += 1

        for store_cd in (self._cooldown_until, self._prio_cooldown_until):
            for uid, until in list(store_cd.items()):
                if until < now:
                    store_cd.pop(uid, None)
                    removed += 1

        total_users = len(self._clicks) + len(self._prio_clicks)
        if total_users > self.trim_max_users:
            ranked = []
            for uid, q in self._clicks.items():
                ranked.append((uid, q[-1] if q else 0.0, False))
            for uid, q in self._prio_clicks.items():
                ranked.append((uid, q[-1] if q else 0.0, True))
            ranked.sort(key=lambda x: x[1])
            overflow = total_users - self.trim_max_users
            for uid, _, is_prio in ranked[:overflow]:
                if is_prio:
                    self._prio_clicks.pop(uid, None)
                else:
                    self._clicks.pop(uid, None)
                self._last_data.pop(uid, None)
                self._strikes.pop(uid, None)
                self._cooldown_until.pop(uid, None)
                self._prio_cooldown_until.pop(uid, None)
                removed += 1

        return {
            "removed": removed,
            "stale_inflight": stale_inf,
            "users": len(self._clicks),
            "prio_users": len(self._prio_clicks),
            "inflight": self._inflight,
            "cooldowns": len(self._cooldown_until),
            "blocked_user": self._stats_blocked_user,
            "blocked_debounce": self._stats_blocked_debounce,
            "blocked_global": self._stats_blocked_global,
            "blocked_cooldown": self._stats_blocked_cooldown,
            "passed": self._stats_passed,
            "prio_passed": self._stats_prio_passed,
            "stale_inflight_total": self._stats_stale_inflight,
            "force_recover_total": self._stats_force_recover,
        }

    def snapshot(self) -> Dict[str, int]:
        return {
            "users": len(self._clicks),
            "prio_users": len(self._prio_clicks),
            "inflight": self._inflight,
            "cooldowns": len(self._cooldown_until),
            "blocked_user": self._stats_blocked_user,
            "blocked_debounce": self._stats_blocked_debounce,
            "blocked_global": self._stats_blocked_global,
            "blocked_cooldown": self._stats_blocked_cooldown,
            "passed": self._stats_passed,
            "prio_passed": self._stats_prio_passed,
            "stale_inflight_total": self._stats_stale_inflight,
            "force_recover_total": self._stats_force_recover,
        }
