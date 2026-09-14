"""Портрет сотрудника для карточки «Игроки».

Чистые функции: кто считается стаффом панели, медали по реальным счётчикам,
короткий текст в духе тёплого личного портрета (без выдуманных тикетов и рангов).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import blake2b
from typing import Any, Mapping, Sequence

from admin_permissions import (
    ROLE_JUNIOR,
    ROLE_LABELS,
    ROLE_MODERATOR,
    ROLE_OWNER,
    ROLE_SENIOR,
)

# Тот же источник истины, что и вход в панель: активный аккаунт с ролью сотрудника.
STAFF_ROLES = frozenset({ROLE_OWNER, ROLE_SENIOR, ROLE_JUNIOR, ROLE_MODERATOR})

_FORBIDDEN_META = ("barnum", "сгенерир", "код сгенерир", "шаблон", "нейросет")


@dataclass(frozen=True)
class AdminPortraitFacts:
    user_id: int
    role: str
    role_label: str
    section_labels: tuple[str, ...] = ()
    tab_labels: tuple[str, ...] = ()
    tenure_days: int | None = None
    hired_at: str | None = None
    tickets_closed: int | None = None
    replies: int | None = None
    tiktok_approved: int | None = None
    tiktok_rejected: int | None = None
    bans: int | None = None
    unbans: int | None = None
    mutes: int | None = None
    warns: int | None = None
    kicks: int | None = None
    balance_adjusts: int | None = None
    item_grants: int | None = None


def is_project_staff(role: str | None, status: str | None) -> bool:
    """Сотрудник панели: активный admin_accounts с staff-ролью.

    Кандидат, отстранённый и «просто админ телеграм-группы» сюда не попадают.
    """
    return (status or "") == "active" and (role or "") in STAFF_ROLES


def staff_search_badge(role: str | None, status: str | None) -> dict[str, Any] | None:
    if not is_project_staff(role, status):
        return None
    return {
        "isStaff": True,
        "role": role,
        "roleLabel": ROLE_LABELS.get(role, role),
    }


def _pos(value: int | None) -> int | None:
    if value is None:
        return None
    n = int(value)
    return n if n > 0 else None


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


def format_tenure_label(days: int | None) -> str | None:
    if days is None:
        return None
    d = max(0, int(days))
    if d <= 0:
        return "сегодня"
    if d < 30:
        return f"{d} {ru_plural(d, 'день', 'дня', 'дней')}"
    months = d // 30
    if d < 365:
        return f"{months} {ru_plural(months, 'месяц', 'месяца', 'месяцев')}"
    years = d // 365
    rem_m = (d % 365) // 30
    year_part = f"{years} {ru_plural(years, 'год', 'года', 'лет')}"
    if rem_m <= 0:
        return year_part
    return f"{year_part} {rem_m} {ru_plural(rem_m, 'месяц', 'месяца', 'месяцев')}"


def tenure_days_from(hired_at, registered_at, *, now: datetime | None = None) -> int | None:
    start = hired_at or registered_at
    if start is None:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    if getattr(start, "tzinfo", None) is None:
        start = start.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return max(0, (now - start).days)


def _rng_index(seed: int, modulus: int) -> int:
    if modulus <= 1:
        return 0
    return seed % modulus


def _seed(facts: AdminPortraitFacts) -> int:
    payload = "|".join(
        [
            str(int(facts.user_id)),
            facts.role or "",
            str(facts.tickets_closed or 0),
            str(facts.replies or 0),
            str(facts.tiktok_approved or 0),
            str(facts.tiktok_rejected or 0),
            str(facts.bans or 0),
            str(facts.unbans or 0),
            str(facts.mutes or 0),
            str(facts.warns or 0),
            str(facts.kicks or 0),
            str(facts.balance_adjusts or 0),
            str(facts.item_grants or 0),
            str(len(facts.section_labels)),
            str(facts.tenure_days if facts.tenure_days is not None else ""),
        ]
    )
    digest = blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _pick(seed: int, salt: int, options: Sequence[str]) -> str:
    return options[_rng_index(seed + salt, len(options))]


def _fmt_n(n: int) -> str:
    return f"{int(n):,}".replace(",", "\u00a0")


def _access_phrase(labels: Sequence[str], seed: int) -> str | None:
    names = [x for x in labels if x]
    if not names:
        return None
    if len(names) == 1:
        return f"открывает «{names[0]}»"
    if len(names) <= 4:
        quoted = "», «".join(names[:-1])
        return f"открывает «{quoted}» и «{names[-1]}»"
    first = names[0]
    last = names[-1]
    return _pick(
        seed,
        11,
        (
            f"открывает {len(names)} разделов: от «{first}» до «{last}»",
            f"в панели {len(names)} разделов — от «{first}» до «{last}»",
        ),
    )


def _role_openers(facts: AdminPortraitFacts, seed: int) -> str:
    label = facts.role_label or ROLE_LABELS.get(facts.role, "Администратор")
    access = _access_phrase(facts.section_labels, seed)
    tail = f" — {access}" if access else ""
    by_role = {
        ROLE_OWNER: (
            f"{label} держит проект как целую карту{tail}.",
            f"{label} — рабочий стол, а не строка в списке{tail}.",
            f"С этой карточки видно сразу: {label.lower()} панели{tail}.",
        ),
        ROLE_SENIOR: (
            f"{label}: на спокойный разбор опираются, когда вокруг уже шум{tail}.",
            f"{label} держит связки между разделами, чтобы мелочи не разъехались{tail}.",
            f"В команде это {label.lower()} — человек, к которому приходят за ясностью{tail}.",
        ),
        ROLE_JUNIOR: (
            f"{label} с аккуратной рукой: сначала смотрит, потом действует{tail}.",
            f"В панели — {label.lower()}, тот, кто замечает деталь, пока остальные уже бегут дальше{tail}.",
            f"{label}: тихая точность, без театра{tail}.",
        ),
        ROLE_MODERATOR: (
            f"{label} стоит на границе игрока и проекта: тон чата слышит раньше, чем он становится проблемой{tail}.",
            f"{label} — чувство меры, а не набор кнопок{tail}.",
            f"Линию можно оставить на модератора и знать, что её доведут{tail}.",
        ),
    }
    options = by_role.get(facts.role) or (f"{label} в команде панели{tail}.",)
    text = _pick(seed, 3, options).strip()
    if not text.endswith("."):
        text += "."
    return text.replace("..", ".")


def _tenure_sentence(facts: AdminPortraitFacts, seed: int) -> str | None:
    label = format_tenure_label(facts.tenure_days)
    if not label:
        return None
    if label == "сегодня":
        return _pick(
            seed,
            17,
            (
                "В команде с сегодняшнего дня — уже видно, что человека взяли не «для галочки».",
                "Только вошёл в состав: походка ещё новая, взгляд уже свой.",
            ),
        )
    with_date = f" с {facts.hired_at[:10]}" if facts.hired_at else ""
    return _pick(
        seed,
        19,
        (
            f"В команде{with_date} уже {label} — срок оставляет походку: без суеты, со своей меркой.",
            f"Рядом с проектом {label}{with_date}: достаточно, чтобы команда чувствовала характер, а не должность.",
            f"Стаж {label} — не цифра в анкете, а привычка доводить начатое.",
        ),
    )


def _work_clauses(facts: AdminPortraitFacts) -> list[str]:
    clauses: list[str] = []
    closed = _pos(facts.tickets_closed)
    replies = _pos(facts.replies)
    if closed:
        word = ru_plural(closed, "тикет", "тикета", "тикетов")
        clauses.append(f"на поддержке закрыл {_fmt_n(closed)} {word}")
    elif replies:
        word = ru_plural(replies, "ответ", "ответа", "ответов")
        clauses.append(f"на линии поддержки {_fmt_n(replies)} {word} игрокам")

    approved = _pos(facts.tiktok_approved)
    rejected = _pos(facts.tiktok_rejected)
    if approved and rejected:
        clauses.append(
            f"в TikTok-очереди {_fmt_n(approved)} "
            f"{ru_plural(approved, 'одобрение', 'одобрения', 'одобрений')} "
            f"и {_fmt_n(rejected)} "
            f"{ru_plural(rejected, 'отклонение', 'отклонения', 'отклонений')}"
        )
    elif approved:
        clauses.append(
            f"в TikTok-очереди {_fmt_n(approved)} "
            f"{ru_plural(approved, 'одобрение', 'одобрения', 'одобрений')}"
        )
    elif rejected:
        clauses.append(
            f"в TikTok-очереди {_fmt_n(rejected)} "
            f"{ru_plural(rejected, 'отклонение', 'отклонения', 'отклонений')}"
        )

    bans = _pos(facts.bans)
    mutes = _pos(facts.mutes)
    warns = _pos(facts.warns)
    kicks = _pos(facts.kicks)
    unbans = _pos(facts.unbans)
    mod_bits: list[str] = []
    if bans:
        mod_bits.append(f"{_fmt_n(bans)} {ru_plural(bans, 'бан', 'бана', 'банов')}")
    if mutes:
        mod_bits.append(f"{_fmt_n(mutes)} {ru_plural(mutes, 'мут', 'мута', 'мутов')}")
    if warns:
        mod_bits.append(f"{_fmt_n(warns)} {ru_plural(warns, 'варн', 'варна', 'варнов')}")
    if kicks:
        mod_bits.append(f"{_fmt_n(kicks)} {ru_plural(kicks, 'кик', 'кика', 'киков')}")
    if unbans:
        mod_bits.append(f"{_fmt_n(unbans)} {ru_plural(unbans, 'разбан', 'разбана', 'разбанов')}")
    if mod_bits:
        clauses.append("архив модерации: " + ", ".join(mod_bits[:3]))

    adj = _pos(facts.balance_adjusts)
    grants = _pos(facts.item_grants)
    if adj:
        clauses.append(
            f"{_fmt_n(adj)} {ru_plural(adj, 'правка', 'правки', 'правок')} баланса"
        )
    if grants:
        clauses.append(
            f"{_fmt_n(grants)} {ru_plural(grants, 'выдача', 'выдачи', 'выдач')} предметов"
        )
    return clauses


def _work_sentence(facts: AdminPortraitFacts, seed: int) -> str | None:
    clauses = _work_clauses(facts)
    if not clauses:
        return None
    # Не CSV: один-два живых факта, порядок стабилен от сида.
    if len(clauses) == 1:
        chosen = [clauses[0]]
    else:
        start = _rng_index(seed, len(clauses))
        chosen = [clauses[start]]
        if len(clauses) > 1:
            chosen.append(clauses[(start + 1 + _rng_index(seed, 3)) % len(clauses)])
            if chosen[0] == chosen[1] and len(clauses) > 2:
                chosen[1] = clauses[(start + 2) % len(clauses)]
        # уникальные, максимум два
        seen: list[str] = []
        for c in chosen:
            if c not in seen:
                seen.append(c)
        chosen = seen[:2]
    if len(chosen) == 1:
        body = chosen[0]
        return _pick(
            seed,
            29,
            (
                f"По делу видно сразу: {body}.",
                f"След в панели конкретный — {body}.",
            ),
        )
    return _pick(
        seed,
        31,
        (
            f"След в работе: {chosen[0]}; {chosen[1]}.",
            f"Цифры не громкие, зато свои: {chosen[0]} и {chosen[1]}.",
        ),
    )


def _texture_sentence(facts: AdminPortraitFacts, seed: int) -> str:
    by_role = {
        ROLE_OWNER: (
            "Команда чувствует: здесь можно оставить задачу и знать, что её доведут до края, без театра.",
            "Решения проходят через этот стол не потому что так написано в роли, а потому что взгляд широкий.",
            "Есть вкус к порядку: не ради галочки, а чтобы игроку было спокойнее в кутах и в чате.",
        ),
        ROLE_SENIOR: (
            "В сложные минуты рядом оказывается именно этот человек — не громче остальных, а ровнее.",
            "Умеет заметить то, что другие пропускают: сбой в тоне, дыру в процессе, лишний жест.",
            "На такого старшего опираются молча: меньше переспрашивают, больше делают.",
        ),
        ROLE_JUNIOR: (
            "Работает так, будто каждый тик панели кого-то касается — и в этом нет позы.",
            "Ещё набирает вес в команде, но уже видно характер: аккуратность без робости.",
            "Тот редкий младший, после которого не приходится подчищать следы.",
        ),
        ROLE_MODERATOR: (
            "Игроки редко знают имя, зато чувствуют, что линия держится.",
            "Чувство меры важнее силы: остановить вовремя и не сломать атмосферу.",
            "Команда знает: модерация здесь — ремесло, а не охота за цифрами.",
        ),
    }
    options = by_role.get(facts.role) or (
        "В команде на такого человека опираются молча: меньше шума, больше дела.",
        "Есть вкус к порядку и уважение к игроку — это видно даже по короткой карточке.",
    )
    return _pick(seed, 41, options)


def generate_admin_portrait(facts: AdminPortraitFacts) -> str:
    """2–4 предложения. Детерминировано для тех же входов. Не выдумывает счётчики."""
    seed = _seed(facts)
    sentences = [_role_openers(facts, seed)]
    tenure = _tenure_sentence(facts, seed)
    work = _work_sentence(facts, seed)
    texture = _texture_sentence(facts, seed)

    extras = [s for s in (tenure, work) if s]
    # Всегда тёплый третий слой, если ещё есть место; иначе — если предложений мало.
    if extras:
        sentences.extend(extras)
        if len(sentences) < 4:
            sentences.append(texture)
    else:
        sentences.append(texture)

    cleaned: list[str] = []
    for raw in sentences:
        text = " ".join((raw or "").split())
        if text and text not in cleaned:
            cleaned.append(text)
    out = " ".join(cleaned[:4])
    low = out.lower()
    for token in _FORBIDDEN_META:
        if token in low:
            out = texture
            break
    return out


def build_staff_achievements(facts: AdminPortraitFacts) -> list[dict[str, Any]]:
    """Медали только по реальным ненулевым фактам. Пустые категории скрыты."""
    items: list[dict[str, Any]] = []
    if facts.section_labels:
        items.append(
            {
                "id": "access",
                "title": "Разделы панели",
                "value": str(len(facts.section_labels)),
                "detail": " · ".join(facts.section_labels),
            }
        )
    tenure = format_tenure_label(facts.tenure_days)
    if tenure:
        items.append(
            {
                "id": "tenure",
                "title": "В команде",
                "value": tenure,
                "detail": (facts.hired_at[:10] if facts.hired_at else None),
            }
        )
    closed = _pos(facts.tickets_closed)
    if closed:
        items.append(
            {
                "id": "tickets",
                "title": "Тикеты закрыты",
                "value": str(closed),
            }
        )
    replies = _pos(facts.replies)
    if replies and not closed:
        items.append(
            {
                "id": "replies",
                "title": "Ответы в поддержке",
                "value": str(replies),
            }
        )
    approved = _pos(facts.tiktok_approved)
    rejected = _pos(facts.tiktok_rejected)
    if approved:
        items.append({"id": "tt_ok", "title": "TikTok · одобрено", "value": str(approved)})
    if rejected:
        items.append({"id": "tt_no", "title": "TikTok · отклонено", "value": str(rejected)})
    for key, title in (
        ("bans", "Баны"),
        ("unbans", "Разбаны"),
        ("mutes", "Муты"),
        ("warns", "Варны"),
        ("kicks", "Кики"),
        ("balance_adjusts", "Правки баланса"),
        ("item_grants", "Выдачи предметов"),
    ):
        n = _pos(getattr(facts, key))
        if n:
            items.append({"id": key, "title": title, "value": str(n)})
    if facts.tab_labels and len(facts.tab_labels) <= 16:
        items.append(
            {
                "id": "tabs",
                "title": "Вкладки",
                "value": str(len(facts.tab_labels)),
                "detail": " · ".join(facts.tab_labels),
            }
        )
    elif facts.tab_labels:
        items.append(
            {
                "id": "tabs",
                "title": "Вкладки",
                "value": str(len(facts.tab_labels)),
            }
        )
    return items


def assemble_staff_portrait_payload(
    *,
    role: str | None,
    status: str | None,
    facts: AdminPortraitFacts | None = None,
) -> dict[str, Any] | None:
    """None для обычного игрока — карточка не получает портрет и медали."""
    if not is_project_staff(role, status) or facts is None:
        return None
    portrait = generate_admin_portrait(facts)
    return {
        "role": facts.role,
        "roleLabel": facts.role_label,
        "hiredAt": facts.hired_at,
        "tenureDays": facts.tenure_days,
        "tenureLabel": format_tenure_label(facts.tenure_days),
        "sections": [{"label": label} for label in facts.section_labels],
        "tabs": [{"label": label} for label in facts.tab_labels],
        "achievements": build_staff_achievements(facts),
        "portrait": portrait,
    }


def facts_from_mapping(data: Mapping[str, Any]) -> AdminPortraitFacts:
    sections = tuple(data.get("section_labels") or ())
    tabs = tuple(data.get("tab_labels") or ())
    return AdminPortraitFacts(
        user_id=int(data["user_id"]),
        role=str(data.get("role") or ""),
        role_label=str(data.get("role_label") or ROLE_LABELS.get(data.get("role"), data.get("role") or "")),
        section_labels=sections,
        tab_labels=tabs,
        tenure_days=data.get("tenure_days"),
        hired_at=data.get("hired_at"),
        tickets_closed=data.get("tickets_closed"),
        replies=data.get("replies"),
        tiktok_approved=data.get("tiktok_approved"),
        tiktok_rejected=data.get("tiktok_rejected"),
        bans=data.get("bans"),
        unbans=data.get("unbans"),
        mutes=data.get("mutes"),
        warns=data.get("warns"),
        kicks=data.get("kicks"),
        balance_adjusts=data.get("balance_adjusts"),
        item_grants=data.get("item_grants"),
    )
