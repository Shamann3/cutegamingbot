"""Кто какое наказание может выдать. Одни правила для бота, кабинета группы и панели.

Здесь нет базы и FastAPI: бот берёт этот файл из папки server, как official_ids.
Запросы ниже каждая сторона выполняет своим пулом.

Сотрудник проекта наказывает по столбцам staff_rules — так же, как бот.
Должность в группе наказывает только в своей группе и только тех, кто младше.
Шире группы — лишь тем, что включено переключателем на должности.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

# Их не наказывает никто: ни сотрудник, ни должность.
PROTECTED_CREATOR_IDS = frozenset({6488580935, 6801702632})

# Действие в одной группе → право должности (как ACTION_RIGHT кабинета).
SEAT_CHAT_RIGHT: dict[str, str] = {
    "mute": "punish_mute",
    "unmute": "punish_mute",
    "cancel_mute": "punish_mute",
    "cancel_pending": "punish_mute",
    "kick": "punish_kick",
    "cancel_kick": "punish_kick",
    "warn": "punish_warn",
    "unwarn": "punish_warn",
    "cancel_warn": "punish_warn",
    "ban": "punish_ban",
    "unban": "punish_ban",
    "cancel_ban": "punish_ban",
    "voice": "punish_voice",
    "unvoice": "punish_voice",
}

# Шире одной группы → переключатель на должности. Наказание чата его не включает.
SEAT_WIDE_RIGHT: dict[str, str] = {
    "muteall": "muteall",
    "unmuteall": "muteall",
    "kickall": "kickall",
    "warnall": "warnall",
    "unwarnall": "warnall",
    "warnfull": "warnfull",
    "unwarnfull": "warnfull",
    "banall": "banall",
    "unbanall": "banall",
    "banfull": "banfull",
    "unbanfull": "banfull",
}

CHAT_PUNISH_RIGHTS = frozenset(SEAT_CHAT_RIGHT.values())
WIDE_SWITCHES = frozenset(SEAT_WIDE_RIGHT.values())

# Названия переключателей так, как они подписаны на должности в кабинете.
SWITCH_LABELS: dict[str, str] = {
    "muteall": "Муталл",
    "kickall": "Кикалл",
    "warnall": "Варналл",
    "warnfull": "Варнфулл",
    "banall": "Баналл",
    "banfull": "Банфулл",
}

# Не сотрудники, хотя запись в admin_accounts есть.
NOT_STAFF_ROLES = frozenset({"", "applicant", "suspended"})

# Действие → ключ права сотрудника. Как _ACTION_PERMISSION_KEY в bot/admins/mute.py.
STAFF_ACTION_KEY: dict[str, str] = {
    "cancel_mute": "mute",
    "cancel_kick": "kick",
    "cancel_pending": "mute",
    "cancel_ban": "ban",
    "unban": "ban",
    "unbanall": "banall",
    "unbanfull": "banfull",
    "cancel_warn": "warn",
    "unwarn": "warn",
    "clearwarns": "warn",
    "unmuteall": "unmute",
}

# Если столбца нет в staff_rules — следующий по цепочке. Как _ACTION_COLUMN_FALLBACKS бота.
STAFF_COLUMN_CHAIN: dict[str, tuple[str, ...]] = {
    "mute": ("mute",),
    "muteall": ("muteall", "mute"),
    "unmute": ("unmute", "mute"),
    "kick": ("kick", "mute"),
    "kickall": ("kickall", "kick", "mute"),
    "ban": ("ban", "mute"),
    "banall": ("banall", "ban", "mute"),
    "banfull": ("banfull", "banall", "ban", "mute"),
    "warn": ("warn", "mute"),
    "warnall": ("warnall", "warn", "mute"),
    "warnfull": ("warnfull", "warnall", "warn", "mute"),
}

SELF_BLOCK = "Себя наказать нельзя"
PROTECTED_BLOCK = "Создателя проекта наказать нельзя"
STAFF_TARGET_BLOCK = "Сотрудника проекта должность в группе не наказывает"
STAFF_TARGET_HINT = "Это делает сотрудник проекта своими правами."
RANK_BLOCK = "Наказать можно только того, кто младше вашей должности в этой группе"
RANK_BLOCK_WIDE = (
    "Это наказание действует во всех официальных группах, "
    "а в одной из них у человека должность не младше вашей"
)
SELF_LIFT_BLOCK = "Снять наказание с самого себя нельзя"
STAFF_LIFT_BLOCK = "С сотрудника проекта наказание снимает только сотрудник проекта"
RANK_LIFT_BLOCK = "Снять наказание можно только с того, кто младше вашей должности в этой группе"

WIDE_MUTE_LIFT = "Этот мут выдан во всех официальных группах"
WIDE_MUTE_LIFT_HINT = "Снять его может сотрудник проекта или должность с включённым «Муталл»."
WIDE_BAN_LIFT = {
    "banall": (
        "Эта блокировка выдана во всех официальных группах",
        "Снять её может сотрудник проекта или должность с включённым «Баналл».",
    ),
    "banfull": (
        "Эта блокировка выдана во всём проекте",
        "Снять её может сотрудник проекта или должность с включённым «Банфулл».",
    ),
}


def _key(value: Any) -> str:
    return str(value or "").strip().lower()


def seat_need(action: str) -> Optional[str]:
    """Право или переключатель должности, без которого действие закрыто."""
    key = _key(action)
    return SEAT_CHAT_RIGHT.get(key) or SEAT_WIDE_RIGHT.get(key)


def is_wide(action: str) -> bool:
    return _key(action) in SEAT_WIDE_RIGHT


def is_lift(action: str) -> bool:
    return _key(action).startswith("un")


def parse_rights(value: Any) -> list[str]:
    """Права должности из jsonb: список, строка JSON или пусто."""
    if isinstance(value, (list, tuple, set, frozenset)):
        raw = list(value)
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except (TypeError, ValueError):
            return []
    else:
        return []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def seat_rights(stored: Any, rank: int) -> frozenset[str]:
    """Наказания места так, как их считает кабинет группы.

    С ранга 5 должность держит все наказания чата. Шире чата — только отмеченные переключатели.
    """
    items = set(parse_rights(stored))
    local = set(CHAT_PUNISH_RIGHTS) if int(rank) >= 5 else items & CHAT_PUNISH_RIGHTS
    return frozenset(local | (items & WIDE_SWITCHES))


def seat_allows(rights: Iterable[str], action: str) -> bool:
    need = seat_need(action)
    return bool(need) and need in set(rights or ())


def may_punish_rank(actor_rank: int, target_rank: int, *, same_person: bool) -> Optional[str]:
    """Наказать можно только того, кто строго младше в этой группе.

    Нет должности — ниже даже ранга 0. Две должности ранга 0 равны.
    Равный и старший не проходят. Себя наказать нельзя.
    """
    if same_person:
        return SELF_BLOCK
    if int(target_rank) >= int(actor_rank):
        return RANK_BLOCK
    return None


def is_staff_account(role: Any, status: Any) -> bool:
    """Действующий сотрудник проекта: роль есть, кандидатом или отстранённым не числится."""
    return _key(role) not in NOT_STAFF_ROLES and _key(status) == "active"


def covers_target(
    *,
    staff_grant: bool,
    seat_allows: bool,
    actor_rank: int,
    target_rank: int,
    same_person: bool,
    target_staff: bool,
    wide: bool = False,
    lift: bool = False,
    actor_creator: bool = False,
) -> Optional[str]:
    """Можно ли наказать этого человека. None — можно.

    Сотрудник проекта, у которого это право включено, старше любой должности
    группы: он наказывает и участника, и администратора группы. Должность
    его не ограничивает. Сама должность наказывает только младших и не
    трогает сотрудников проекта.
    """
    if same_person:
        return SELF_LIFT_BLOCK if lift else SELF_BLOCK
    if staff_grant or actor_creator:
        return None
    if not seat_allows:
        return "Должность не даёт этого наказания"
    return seat_target_block(
        actor_rank=actor_rank,
        target_rank=target_rank,
        same_person=False,
        target_staff=target_staff,
        wide=wide,
        lift=lift,
        actor_creator=False,
    )


def seat_target_block(
    *,
    actor_rank: int,
    target_rank: int,
    same_person: bool,
    target_staff: bool,
    wide: bool = False,
    actor_creator: bool = False,
    lift: bool = False,
) -> Optional[str]:
    """Отказ для наказания по должности. None — можно.

    Для наказания шире чата target_rank — самая старшая должность цели во всех группах.
    Снятие наказания подчиняется тем же правилам, что и выдача.
    """
    if same_person:
        return SELF_LIFT_BLOCK if lift else SELF_BLOCK
    if target_staff and not actor_creator:
        return STAFF_LIFT_BLOCK if lift else STAFF_TARGET_BLOCK
    if may_punish_rank(actor_rank, target_rank, same_person=False):
        if lift:
            return RANK_LIFT_BLOCK
        return RANK_BLOCK_WIDE if wide else RANK_BLOCK
    return None


def staff_column(action: str, columns: Sequence[str]) -> Optional[str]:
    """Столбец staff_rules, который решает действие. Повторяет бота один в один."""
    cols = [str(col) for col in columns or () if str(col)]
    if not cols:
        return None
    key = STAFF_ACTION_KEY.get(_key(action), _key(action))
    if key in cols:
        return key
    lower = {col.lower(): col for col in cols}
    for candidate in STAFF_COLUMN_CHAIN.get(key, (key,)):
        if candidate in cols:
            return candidate
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    if "mute" in lower:
        return lower["mute"]
    return cols[0]


def staff_allows(permissions: Mapping[str, Any], action: str, columns: Sequence[str]) -> bool:
    column = staff_column(action, columns)
    return bool(column) and bool(permissions.get(column))


def punish_action(kind: str, mode: str) -> str:
    """mute/kick/ban/warn и охват chat/all/full → столбец права.

    Банфулл не подменяется баном, варнфулл — варном. Если столбца в таблице нет,
    цепочку запасных столбцов решает staff_column, не эта функция.
    """
    table = {
        "mute": {"chat": "mute", "all": "muteall"},
        "kick": {"chat": "kick", "all": "kickall"},
        "ban": {"chat": "ban", "all": "banall", "full": "banfull"},
        "warn": {"chat": "warn", "all": "warnall", "full": "warnfull"},
    }.get(kind) or {}
    return table.get(mode) or table.get("chat") or kind


def outside_seat_block(*, staff_grant: bool, official: bool) -> Optional[str]:
    """Сотрудник проекта без должности в этой группе.

    Право из staff_rules действует в любой официальной группе, не только в своей.
    Без этого права чужая группа закрыта. Неофициальный чат закрыт всегда.
    """
    if staff_grant and official:
        return None
    if staff_grant:
        return "Эта группа не отмечена официальной"
    return "В этой группе у вас нет должности"


# Панель сотрудника: что выдаётся из карточки человека. Снятие варнов и банфулла — в боте.
STAFF_PANEL_ACTIONS: tuple[dict[str, Any], ...] = (
    {"id": "mute", "label": "Мут", "scope": "chat", "needsUntil": True,
     "hint": "Только в выбранной группе: писать нельзя, пока идёт срок."},
    {"id": "unmute", "label": "Снять мут", "scope": "chat", "needsUntil": False,
     "hint": "Снимает мут только в выбранной группе."},
    {"id": "kick", "label": "Кик", "scope": "chat", "needsUntil": False,
     "hint": "Исключает из выбранной группы. Вернуться по ссылке можно."},
    {"id": "warn", "label": "Варн", "scope": "chat", "needsUntil": True,
     "hint": "Предупреждение в выбранной группе на срок."},
    {"id": "ban", "label": "Бан", "scope": "chat", "needsUntil": True,
     "hint": "Бан только в выбранной группе."},
    {"id": "unban", "label": "Снять бан", "scope": "chat", "needsUntil": False,
     "hint": "Снимает бан только в выбранной группе."},
    {"id": "muteall", "label": "Муталл", "scope": "all", "needsUntil": True,
     "hint": "Мут в каждой официальной группе."},
    {"id": "unmuteall", "label": "Снять муталл", "scope": "all", "needsUntil": False,
     "hint": "Снимает мут во всех официальных группах."},
    {"id": "kickall", "label": "Кикалл", "scope": "all", "needsUntil": False,
     "hint": "Исключает из каждой официальной группы."},
    {"id": "warnall", "label": "Варналл", "scope": "all", "needsUntil": True,
     "hint": "Предупреждение во всех официальных группах."},
    {"id": "banall", "label": "Баналл", "scope": "all", "needsUntil": True,
     "hint": "Бан в каждой официальной группе. Это ещё не бан всего проекта."},
    {"id": "unbanall", "label": "Снять баналл", "scope": "all", "needsUntil": False,
     "hint": "Снимает бан во всех официальных группах."},
    {"id": "warnfull", "label": "Варнфулл", "scope": "full", "needsUntil": True,
     "hint": "Предупреждение во всём проекте, не только в группах."},
    {"id": "banfull", "label": "Банфулл", "scope": "full", "needsUntil": True,
     "hint": "Бан во всех группах и закрытый вход в бота."},
)
LIFT_ACTIONS = frozenset({"unmute", "unban", "unmuteall", "unbanall"})


def staff_panel_action(action: str) -> Optional[dict[str, Any]]:
    key = _key(action)
    for item in STAFF_PANEL_ACTIONS:
        if item["id"] == key:
            return dict(item)
    return None


def staff_panel_actions(
    permissions: Mapping[str, Any],
    columns: Sequence[str],
    *,
    creator: bool = False,
) -> list[dict[str, Any]]:
    """Действия панели, которые даёт роль. Создателю проекта — все."""
    return [
        dict(item)
        for item in STAFF_PANEL_ACTIONS
        if creator or staff_allows(permissions, item["id"], columns)
    ]


# Место человека в официальной группе. Срок и закрытый кабинет решает код, чтобы отказ был точным.
SEAT_SQL = """
    SELECT p.title, p.rank, p.rights,
           (s.term_end IS NULL OR s.term_end > NOW()) AS in_term,
           EXISTS (
             SELECT 1 FROM epsilon_group_keys k
             WHERE k.user_id = s.user_id AND k.disabled
           ) AS key_off
    FROM epsilon_seats s
    JOIN epsilon_official_groups g ON g.chat_id = s.chat_id AND g.is_official
    JOIN epsilon_positions p ON p.id = s.position_id
    WHERE s.user_id = $1 AND s.chat_id = $2
    ORDER BY p.rank DESC
    LIMIT 1
"""

# Действующее место цели в одной группе.
TARGET_SEAT_SQL = """
    SELECT p.title, p.rank
    FROM epsilon_seats s
    JOIN epsilon_positions p ON p.id = s.position_id
    WHERE s.user_id = $1 AND s.chat_id = $2
      AND (s.term_end IS NULL OR s.term_end > NOW())
      AND NOT EXISTS (
        SELECT 1 FROM epsilon_group_keys k
        WHERE k.user_id = s.user_id AND k.disabled
      )
    ORDER BY p.rank DESC
    LIMIT 1
"""

# Самое старшее действующее место цели во всех официальных группах — для наказаний шире чата.
TARGET_TOP_SEAT_SQL = """
    SELECT p.title, p.rank
    FROM epsilon_seats s
    JOIN epsilon_official_groups g ON g.chat_id = s.chat_id AND g.is_official
    JOIN epsilon_positions p ON p.id = s.position_id
    WHERE s.user_id = $1
      AND (s.term_end IS NULL OR s.term_end > NOW())
      AND NOT EXISTS (
        SELECT 1 FROM epsilon_group_keys k
        WHERE k.user_id = s.user_id AND k.disabled
      )
    ORDER BY p.rank DESC
    LIMIT 1
"""

# Должности группы — для подсказки «кто в этой группе может».
CHAT_POSITIONS_SQL = """
    SELECT title, rank, rights
    FROM epsilon_positions
    WHERE chat_id = $1
    ORDER BY rank DESC, id
"""

# Бан шире одного чата: срочные строки и последние записи журнала.
WIDE_BAN_SQL = """
    SELECT
      EXISTS (
        SELECT 1 FROM active_bans b
        WHERE b.user_id = $1 AND coalesce(b.mode, 'chat') = 'full'
      ) AS timed_full,
      EXISTS (
        SELECT 1 FROM active_bans b
        WHERE b.user_id = $1
          AND (coalesce(b.scope, 'chat') = 'all' OR coalesce(b.mode, 'chat') IN ('all', 'full'))
      ) AS timed_wide,
      (
        SELECT max(s.created_at) FROM staff_actions s
        WHERE s.target_player_id = $1
          AND (
            lower(s.action_type) = 'banall'
            OR (lower(s.action_type) = 'ban' AND coalesce(s.scope, 'chat') = 'all')
          )
      ) AS all_at,
      (
        SELECT max(s.created_at) FROM staff_actions s
        WHERE s.target_player_id = $1
          AND (
            lower(s.action_type) = 'banfull'
            OR (lower(s.action_type) = 'ban' AND coalesce(s.scope, 'chat') = 'full')
          )
      ) AS full_at,
      (
        SELECT max(s.created_at) FROM staff_actions s
        WHERE s.target_player_id = $1
          AND (
            lower(s.action_type) = 'unbanall'
            OR (lower(s.action_type) = 'unban' AND coalesce(s.scope, 'chat') IN ('all', 'full'))
          )
      ) AS lifted_at
"""

# Мут шире одного чата: строки муталла и общий срок в users.
WIDE_MUTE_SQL = """
    SELECT
      EXISTS (
        SELECT 1 FROM active_mutes m
        WHERE m.user_id = $1 AND (m.chat_id = 0 OR coalesce(m.scope, 'chat') = 'all')
      ) AS rows_all,
      (SELECT u.mute_until FROM users u WHERE u.user_id = $1) AS mute_until
"""


def _after(stamp: Any, lifted: Any) -> bool:
    if stamp is None:
        return False
    if lifted is None:
        return True
    try:
        return stamp > lifted
    except TypeError:
        return True


def wide_ban_switch(row: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Какой переключатель нужен, чтобы снять бан в одной группе: banfull, banall или никакой."""
    if not row:
        return None
    lifted = row.get("lifted_at")
    if row.get("timed_full") or _after(row.get("full_at"), lifted):
        return "banfull"
    if row.get("timed_wide") or _after(row.get("all_at"), lifted):
        return "banall"
    return None


def switch_covers(rights: Iterable[str], need: Optional[str]) -> bool:
    """Банфулл шире баналла, поэтому снимает и его."""
    if not need:
        return True
    have = set(rights or ())
    if need == "banall":
        return bool({"banall", "banfull"} & have)
    return need in have


def mute_until_active(value: Any, *, now: Optional[datetime] = None) -> bool:
    """Срок из users.mute_until. Наивное время — местные часы, как у бота при выдаче."""
    if not isinstance(value, datetime):
        return False
    if now is None:
        now = datetime.now() if value.tzinfo is None else datetime.now(timezone.utc)
    try:
        return value > now
    except TypeError:
        return False


def wide_mute_on(row: Optional[Mapping[str, Any]], *, now: Optional[datetime] = None) -> bool:
    if not row:
        return False
    return bool(row.get("rows_all")) or mute_until_active(row.get("mute_until"), now=now)
