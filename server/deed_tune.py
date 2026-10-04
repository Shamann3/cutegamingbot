"""Нормы под кут технических групп.

Верхняя граница — полная цена карточки. Если группы не покрывают неделю,
цена сжимается. Последние 40% баланса код не планирует трогать,
а за неделю на зарплаты отпускает не больше 15%.

Куты сами не уходят: выплату по-прежнему отпускает создатель.
"""
from __future__ import annotations

from datetime import date, timedelta

# (каждые, кут за эту пачку) — верхняя цена, когда группы полные.
IDEAL = {
    "ban": (100, 200, "Баны"),
    "mute": (50, 80, "Муты"),
    "kick": (40, 60, "Кики"),
    "warn": (80, 50, "Предупреждения"),
    "check_admin": (100, 40, "Проверки администраторов"),
    "check_staff": (100, 60, "Проверки сотрудников"),
}

PUNISH = ("ban", "mute", "kick", "warn")
RESERVE_NUM, RESERVE_DEN = 2, 5
WEEK_CAP_NUM, WEEK_CAP_DEN = 3, 20


def bucket(action: str) -> str:
    if action == "check_admin":
        return "admin"
    if action == "check_staff":
        return "staff"
    if action in PUNISH:
        return "issue"
    return ""


def money(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


def unit_text(every: int, reward: int) -> str:
    """«2», «1,6», «0,62» — кут за одну карточку."""
    every = int(every or 0)
    reward = int(reward or 0)
    if every <= 0 or reward <= 0:
        return "0"
    hundredths = reward * 100 // every
    whole, frac = divmod(hundredths, 100)
    if frac == 0:
        return str(whole)
    text = f"{frac:02d}".rstrip("0")
    return f"{whole},{text}"


def week_room(purse: int, owed: int) -> dict:
    purse = max(0, int(purse or 0))
    owed = max(0, int(owed or 0))
    reserve = purse * RESERVE_NUM // RESERVE_DEN
    cap = purse * WEEK_CAP_NUM // WEEK_CAP_DEN
    spendable = max(0, purse - reserve)
    budget = max(0, min(spendable, cap) - owed)
    return {"reserve": reserve, "cap": cap, "budget": budget}


def full_week_cost(counts: dict) -> int:
    total = 0
    for action, (every, reward, _title) in IDEAL.items():
        n = int(counts.get(action) or 0)
        if n > 0 and every > 0:
            total += n * reward // every
    return total


def scale_of(budget: int, full: int) -> tuple[int, int]:
    budget = max(0, int(budget or 0))
    full = max(0, int(full or 0))
    if budget <= 0:
        return 0, 1
    if full <= 0 or budget >= full:
        return 1, 1
    return budget, full


def reward_for(every_n: int, ideal_every: int, ideal_reward: int, num: int, den: int) -> int:
    if every_n <= 0 or ideal_every <= 0 or den <= 0 or ideal_reward <= 0 or num <= 0:
        return 0
    return ideal_reward * int(every_n) * int(num) // (ideal_every * int(den))


def purse_moved(old: int, new: int) -> bool:
    old = max(0, int(old or 0))
    new = max(0, int(new or 0))
    if old <= 0:
        return new > 0
    return abs(new - old) * 10 >= old


def explain(*, purse, groups, reserve, budget, full, num, den, opened, held) -> str:
    if purse <= 0:
        text = "В технических группах сейчас нет кута. Новые нормы стоят на нуле."
    elif full <= 0 and num > 0:
        text = (
            f"В {groups} группах лежит {money(purse)} кут. "
            "За 7 дней подтверждённых карточек не было, поэтому стоят полные нормы. "
            f"За неделю на зарплаты можно отпустить {money(budget)} кут. "
            f"{money(reserve)} кут код не трогает."
        )
    elif num <= 0:
        text = (
            f"В группах лежит {money(purse)} кут, но очередь выплат уже занимает эту неделю. "
            "Новые нормы не растут, пока очередь не отпущена."
        )
    elif den > 0 and num >= den:
        text = (
            f"Группы покрывают полную неделю: {money(budget)} кут можно отпустить на зарплаты "
            f"из {money(purse)}. Нормы стоят на верхней границе."
        )
    else:
        pct = num * 100 // den if den else 0
        text = (
            f"Группы покрывают {pct}% полной недели. Нормы ужаты: "
            f"на зарплаты можно отпустить {money(budget)} кут, "
            f"{money(reserve)} кут остаётся в группах."
        )
    if opened:
        text += " Выключенные нормы включены. Уже совпавшие карточки войдут в первую выплату, когда вы её отпустите."
    if held:
        text += " Нормы с невыплаченной очередью код не обнулял."
    text += " Кут уходит из групп только по кнопке «Выплатить»."
    return text


def plan_tune(purse: int, owed: int, counts: dict, rates: list[dict], owed_actions: set[str], groups: int = 0) -> dict:
    """Какие суммы записать. Ручные нормы («создатель платит сам») не трогает."""
    room = week_room(purse, owed)
    full = full_week_cost(counts)
    num, den = scale_of(room["budget"], full)
    by = {item["action"]: item for item in rates}
    updates = []
    opened = []
    held = []
    for action, (ideal_every, ideal_reward, title) in IDEAL.items():
        current = by.get(action) or {
            "action": action,
            "every_n": ideal_every,
            "reward": 0,
            "purse": "tech",
            "enabled": False,
            "title": title,
        }
        if current.get("purse") == "manual":
            continue
        every = int(current.get("every_n") or ideal_every)
        reward = reward_for(every, ideal_every, ideal_reward, num, den)
        if reward <= 0 and action in owed_actions:
            held.append(action)
            continue
        was_live = bool(current.get("enabled")) and int(current.get("reward") or 0) > 0
        if reward > 0 and not was_live:
            opened.append(action)
        updates.append({
            "action": action,
            "every_n": every,
            "reward": reward,
            "enabled": reward > 0,
            "title": (current.get("title") or title),
            "idealReward": reward_for(every, ideal_every, ideal_reward, 1, 1),
        })
    return {
        "reserve": room["reserve"],
        "budget": room["budget"],
        "full": full,
        "num": num,
        "den": den,
        "updates": updates,
        "opened": opened,
        "held": held,
        "note": explain(
            purse=int(purse or 0),
            groups=int(groups or 0),
            reserve=room["reserve"],
            budget=room["budget"],
            full=full,
            num=num,
            den=den,
            opened=opened,
            held=held,
        ),
    }


def fill_days(sparse: list[dict], today: date, days: int = 14) -> list[dict]:
    by = {}
    for item in sparse:
        key = item.get("day")
        if hasattr(key, "isoformat"):
            key = key.isoformat()
        by[str(key)] = item
    out = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        row = by.get(day.isoformat()) or {}
        out.append({
            "day": day.isoformat(),
            "issue": int(row.get("issue") or 0),
            "admin": int(row.get("admin") or 0),
            "staff": int(row.get("staff") or 0),
        })
    return out
