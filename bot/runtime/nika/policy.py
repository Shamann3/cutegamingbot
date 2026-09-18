# -*- coding: utf-8 -*-
"""Ника: решения о доливе и о сборе излишка - чистая математика.

Зачем отдельным модулем. Здесь нет ни БД, ни Telegram, ни времени «сейчас» -
только числа на входе и план на выходе. Поэтому формулу можно проверить
тестами без живой базы, а engine.py остаётся тонким: собрал цифры -> спросил
план -> подвигал куты.

Два инварианта, которые здесь держатся жёстко:
  • недостача НИКОГДА не закрывается одним переводом (см. gap_share);
  • мелкие отклонения от цели не трогаются вообще (см. dead_zone) - иначе
    получаются качели «снял - долил - снял».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from bot.config.config import (
    BACKGROUND_EARNINGS_CHAT_ID,
    GAME_COMMISSION_CHAT_ID,
    PROFIT_JAR_CHAT_ID,
    TECH_CHAT_ID,
)

# ---------------------------------------------------------------------------
# Лестница источников долива. Порядок - решение владельца и менять его нельзя:
# копилка чистой прибыли идёт последней и только когда выше пусто.
# ---------------------------------------------------------------------------
SOURCE_LADDER: Tuple[Tuple[int, str], ...] = (
    (GAME_COMMISSION_CHAT_ID, "игры"),
    (BACKGROUND_EARNINGS_CHAT_ID, "фон"),
    (TECH_CHAT_ID, "дом игр"),
    (PROFIT_JAR_CHAT_ID, "копилка"),
)

# Куда уходит излишек. Та же копилка, что и последний источник: излишек группы
# - это и есть чистый заработок проекта.
SWEEP_DEST_CHAT_ID = PROFIT_JAR_CHAT_ID

SPEED_MODES: Tuple[str, ...] = ("auto", "slow", "medium", "aggressive")
DEFAULT_SPEED_MODE = "auto"

# ---------------------------------------------------------------------------
# Готовые режимы владельца: (доля цели за один долив, максимальная доля
# недостачи за один долив, минимальный интервал между доливами в секундах).
#
# Для цели 5000 кут это:
#   slow       - 100 кут не чаще раза в 30 мин  (до 200 кут/час)
#   medium     - 250 кут не чаще раза в 15 мин  (до 1000 кут/час)
#   aggressive - 500 кут не чаще раза в 5 мин   (до 6000 кут/час, дальше
#                упирается в суточный потолок)
# ---------------------------------------------------------------------------
_FIXED_MODES: Dict[str, Tuple[float, float, int]] = {
    "slow": (0.02, 0.25, 1800),
    "medium": (0.05, 0.40, 900),
    "aggressive": (0.10, 0.60, 300),
}

# ---------------------------------------------------------------------------
# Автоматический режим: тир активности по числу событий growth_fund_ledger
# в группе за последние 24 часа. Играют часто - доливаем крупнее и чаще,
# тихо - редко и по чуть-чуть.
#
# (порог событий, имя тира, доля цели, доля недостачи, интервал сек)
# ---------------------------------------------------------------------------
_AUTO_TIERS: Tuple[Tuple[int, str, float, float, int], ...] = (
    (120, "hot", 0.10, 0.60, 300),
    (40, "busy", 0.08, 0.50, 600),
    (10, "normal", 0.05, 0.40, 900),
    (1, "quiet", 0.025, 0.30, 1800),
    (0, "idle", 0.015, 0.25, 3600),
)

# Скорость убывания баланса, которую считаем «нормальной»: 5% цели в час.
# Реальный расход делим на неё и этим множителем поправляем шаг (только auto).
DRAIN_REFERENCE_PCT = 0.05
DRAIN_MULT_MIN = 0.6
DRAIN_MULT_MAX = 2.0

# Шаг мельче этого не имеет смысла: ползли бы к цели по одному куту.
MIN_STEP_PCT = 0.005

# Дефолты, от которых считаются потолки новой группы (см. store.suggest_caps).
DEFAULT_DEAD_ZONE_PCT = 0.05
DEFAULT_DEAD_ZONE_MIN = 100
DEFAULT_MAX_TRANSFER_PCT = 0.20
DEFAULT_MAX_TRANSFER_FLOOR = 50
DEFAULT_MAX_DAILY_TARGETS = 2.0
DEFAULT_MAX_DAILY_FLOOR = 500
DEFAULT_SWEEP_SHARE = 0.25
DEFAULT_SWEEP_DELAY_SEC = 3600
DEFAULT_SWEEP_COOLDOWN_SEC = 1800


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else (high if value > high else value)


@dataclass(frozen=True)
class GroupPolicy:
    """Настройки одной группы в том виде, в каком их нужно считать.

    Отдельный тип, а не строка из БД: формулу тестируем без asyncpg, а engine
    собирает этот объект из nika_group_settings.
    """

    chat_id: int
    target_balance: int
    speed_mode: str = DEFAULT_SPEED_MODE
    dead_zone_pct: float = DEFAULT_DEAD_ZONE_PCT
    dead_zone_min: int = DEFAULT_DEAD_ZONE_MIN
    max_transfer: int = 1000
    max_daily_topup: int = 10000
    max_daily_sweep: int = 10000
    sweep_share: float = DEFAULT_SWEEP_SHARE
    sweep_delay_sec: int = DEFAULT_SWEEP_DELAY_SEC
    sweep_cooldown_sec: int = DEFAULT_SWEEP_COOLDOWN_SEC


@dataclass(frozen=True)
class Plan:
    """Что делать с группой прямо сейчас.

    amount == 0 означает «ничего не делаем», и тогда skip объясняет причину -
    это же объяснение уходит в лог и в сводку для админки.
    """

    action: str  # topup | sweep | none
    amount: int
    cooldown_sec: int
    tier: str
    reason: str
    skip: Optional[str] = None
    dead_zone: int = 0
    gap: int = 0
    step_raw: int = 0


def dead_zone(policy: GroupPolicy) -> int:
    """Мёртвая зона вокруг цели: отклонения внутри неё игнорируем полностью."""
    by_pct = int(round(max(0, policy.target_balance) * max(0.0, policy.dead_zone_pct)))
    return int(max(0, policy.dead_zone_min, by_pct))


def normalize_speed_mode(mode: object) -> str:
    text = str(mode or "").strip().lower()
    return text if text in SPEED_MODES else DEFAULT_SPEED_MODE


def activity_tier(events_24h: int) -> Tuple[str, float, float, int]:
    """Тир активности по событиям growth_fund_ledger за сутки."""
    events = int(max(0, events_24h))
    for threshold, name, step_pct, gap_share, cooldown in _AUTO_TIERS:
        if events >= threshold:
            return name, step_pct, gap_share, cooldown
    # _AUTO_TIERS заканчивается порогом 0, до этой строки дойти нельзя.
    return "idle", 0.015, 0.25, 3600


def drain_multiplier(drain_per_hour: float, target_balance: int) -> float:
    """Поправка шага на фактическую скорость убывания баланса."""
    reference = max(1.0, float(target_balance) * DRAIN_REFERENCE_PCT)
    return float(_clamp(float(max(0.0, drain_per_hour)) / reference, DRAIN_MULT_MIN, DRAIN_MULT_MAX))


def _mode_profile(
    policy: GroupPolicy,
    events_24h: int,
    drain_per_hour: float,
) -> Tuple[str, float, float, int, float]:
    """(tier, step_pct, gap_share, cooldown_sec, drain_mult) для режима группы."""
    mode = normalize_speed_mode(policy.speed_mode)
    if mode != "auto":
        step_pct, gap_share, cooldown = _FIXED_MODES[mode]
        return mode, step_pct, gap_share, cooldown, 1.0

    tier, step_pct, gap_share, cooldown = activity_tier(events_24h)
    mult = drain_multiplier(drain_per_hour, policy.target_balance)
    # Чем быстрее убывает баланс, тем короче пауза между доливами.
    cooldown = int(max(60, round(cooldown / max(0.5, mult))))
    return f"auto:{tier}", step_pct, gap_share, cooldown, mult


def plan_topup(
    policy: GroupPolicy,
    *,
    balance: int,
    events_24h: int = 0,
    drain_per_hour: float = 0.0,
    daily_topup_used: int = 0,
) -> Plan:
    """Сколько долить группе прямо сейчас.

    Порядок ограничений важен: сначала считаем «желаемый» шаг по скорости,
    потом режем его долей недостачи (чтобы не закрыть дыру одним переводом),
    потом потолком одного перевода и остатком суточного лимита.
    """
    target = int(max(0, policy.target_balance))
    dz = dead_zone(policy)
    gap = target - int(balance)

    tier, step_pct, gap_share, cooldown, mult = _mode_profile(policy, events_24h, drain_per_hour)

    if target <= 0:
        return Plan("none", 0, cooldown, tier, "цель не задана", skip="no_target", dead_zone=dz, gap=gap)
    if gap <= dz:
        return Plan("none", 0, cooldown, tier, "баланс в пределах мёртвой зоны", skip="dead_zone", dead_zone=dz, gap=gap)

    step_raw = int(round(target * step_pct * mult))
    min_step = int(max(1, round(target * MIN_STEP_PCT)))
    amount = max(step_raw, min_step)

    # Главный запрет: одним переводом недостачу не закрываем.
    amount = min(amount, int(gap * gap_share))

    amount = min(amount, int(max(0, policy.max_transfer)))
    daily_left = int(max(0, policy.max_daily_topup)) - int(max(0, daily_topup_used))
    amount = min(amount, daily_left)

    if amount <= 0:
        skip = "daily_cap" if daily_left <= 0 else "cap"
        return Plan("none", 0, cooldown, tier, f"долив заблокирован потолком ({skip})", skip=skip,
                    dead_zone=dz, gap=gap, step_raw=step_raw)

    reason = (
        f"долив до цели {target}: баланс {int(balance)}, недостача {gap}, "
        f"режим {tier}, шаг {step_raw}→{amount}, расход {drain_per_hour:.0f} кут/час, "
        f"событий за 24ч {int(events_24h)}"
    )
    return Plan("topup", int(amount), cooldown, tier, reason, dead_zone=dz, gap=gap, step_raw=step_raw)


def plan_sweep(
    policy: GroupPolicy,
    *,
    balance: int,
    stable_balance: Optional[int],
    history_covers_delay: bool,
    daily_sweep_used: int = 0,
) -> Plan:
    """Сколько излишка снять в копилку прямо сейчас.

    stable_balance - МИНИМУМ баланса за окно sweep_delay_sec. Именно он, а не
    текущий баланс, даёт требуемую задержку: свежее пополнение группы в это
    окно ещё не попало, поэтому оно не собирается сразу, а только после того,
    как продержалось выше цели весь период ожидания.
    """
    target = int(max(0, policy.target_balance))
    dz = dead_zone(policy)
    gap = target - int(balance)

    if target <= 0:
        return Plan("none", 0, policy.sweep_cooldown_sec, "sweep", "цель не задана", skip="no_target", dead_zone=dz, gap=gap)
    if int(balance) - target <= dz:
        return Plan("none", 0, policy.sweep_cooldown_sec, "sweep", "излишек в пределах мёртвой зоны",
                    skip="dead_zone", dead_zone=dz, gap=gap)
    if not history_covers_delay or stable_balance is None:
        return Plan("none", 0, policy.sweep_cooldown_sec, "sweep", "жду выдержку излишка",
                    skip="sweep_delay", dead_zone=dz, gap=gap)

    stable_excess = int(stable_balance) - target
    if stable_excess <= dz:
        return Plan("none", 0, policy.sweep_cooldown_sec, "sweep", "устойчивого излишка нет",
                    skip="sweep_delay", dead_zone=dz, gap=gap)

    step_raw = int(round(stable_excess * max(0.0, policy.sweep_share)))
    min_step = int(max(1, round(target * MIN_STEP_PCT)))
    amount = max(step_raw, min_step)

    # Ниже цели группу не опускаем даже на кут.
    amount = min(amount, stable_excess)
    amount = min(amount, int(max(0, policy.max_transfer)))
    daily_left = int(max(0, policy.max_daily_sweep)) - int(max(0, daily_sweep_used))
    amount = min(amount, daily_left)

    if amount <= 0:
        skip = "daily_cap" if daily_left <= 0 else "cap"
        return Plan("none", 0, policy.sweep_cooldown_sec, "sweep", f"сбор заблокирован потолком ({skip})",
                    skip=skip, dead_zone=dz, gap=gap, step_raw=step_raw)

    reason = (
        f"сбор излишка над целью {target}: баланс {int(balance)}, "
        f"устойчивый излишек {stable_excess}, доля {policy.sweep_share:.2f}, шаг {step_raw}→{amount}"
    )
    return Plan("sweep", int(amount), int(max(60, policy.sweep_cooldown_sec)), "sweep", reason,
                dead_zone=dz, gap=gap, step_raw=step_raw)


def allocate_from_ladder(
    need: int,
    sources: Tuple[Tuple[int, int], ...],
) -> Tuple[Tuple[Tuple[int, int], ...], int]:
    """Разложить недостачу по лестнице источников, не уходя в минус.

    sources — (chat_id, доступный баланс) уже в порядке SOURCE_LADDER.
    Возвращает ((chat_id, сколько взять), ...), сколько всё ещё не хватает.
    Пустые и нулевые источники пропускаются; с одного источника больше, чем
    на нём лежит, не берём никогда.
    """
    remaining = int(max(0, need))
    takes: list[Tuple[int, int]] = []
    if remaining <= 0:
        return tuple(takes), 0
    for chat_id, available in sources:
        if remaining <= 0:
            break
        take = min(remaining, int(max(0, available)))
        if take <= 0:
            continue
        takes.append((int(chat_id), take))
        remaining -= take
    return tuple(takes), int(remaining)


def suggest_caps(target_balance: int) -> Dict[str, int]:
    """Разумные потолки для новой группы, посчитанные от её цели."""
    target = int(max(0, target_balance))
    return {
        "max_transfer": int(max(DEFAULT_MAX_TRANSFER_FLOOR, round(target * DEFAULT_MAX_TRANSFER_PCT))),
        "max_daily_topup": int(max(DEFAULT_MAX_DAILY_FLOOR, round(target * DEFAULT_MAX_DAILY_TARGETS))),
        "max_daily_sweep": int(max(DEFAULT_MAX_DAILY_FLOOR, round(target * DEFAULT_MAX_DAILY_TARGETS))),
        "dead_zone_min": int(max(1, min(DEFAULT_DEAD_ZONE_MIN, round(target * DEFAULT_DEAD_ZONE_PCT)))),
    }
