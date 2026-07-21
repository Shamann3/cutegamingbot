# server/admin_permissions.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from admin_auth import require_admin_session
from db import db

ROLE_OWNER = "owner"
ROLE_SENIOR = "senior_admin"
ROLE_JUNIOR = "junior_admin"
ROLE_MODERATOR = "moderator"
ROLE_APPLICANT = "applicant"
ROLE_SUSPENDED = "suspended"

# Максимум сотрудников на роль и общий лимит
STAFF_LIMITS: dict[str, int] = {
    ROLE_SENIOR:    1,
    ROLE_JUNIOR:    2,
    ROLE_MODERATOR: 3,
}
STAFF_TOTAL_LIMIT = 8  # включая владельцев

STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
STATUS_SUSPENDED = "suspended"

ROLE_LABELS = {
    ROLE_OWNER: "Владелец",
    ROLE_SENIOR: "Старший администратор",
    ROLE_JUNIOR: "Младший администратор",
    ROLE_MODERATOR: "Модератор",
    ROLE_APPLICANT: "Кандидат",
    ROLE_SUSPENDED: "Отстранён",
}

# Полный набор прав (= права владельца).
ALL_PERMISSIONS = {
    # Игроки и модерация
    "view_players",            # видеть раздел «Игроки» и базовый профиль
    "view_player_sensitive",   # видеть IP / устройство / гео игрока (owner)
    "moderate_ban",            # бан игрока (с доказательствами)
    "moderate_unban",          # разбан (с доказательствами)
    "adjust_balance",          # правка баланса игрока
    "give_items",              # выдача/списание предметов игрока (owner)
    # Разделы только для просмотра / биржа
    "view_market",             # раздел «Биржа»
    "market_cancel",           # отмена лотов
    "view_logs",               # раздел «Логи»
    "view_analytics",          # раздел «Аналитика» (owner)
    "view_accounts",           # раздел «Аккаунты» (чувствительные данные, owner)
    # Изменение игры — только владелец
    "manage_economy",
    "manage_farm",
    "manage_content",
    "manage_broadcast",
    "manage_events",
    "manage_settings",
    "manage_security",
    # Стафф
    "review_applications",     # смотреть/отклонять заявки
    "assign_roles",            # одобрять заявки = выдавать роль (owner)
    "manage_staff",            # сотрудники, отстранение, жалобы
    "set_salary",              # выставлять зарплату
    "approve_salary",          # одобрять зарплату (owner)
    "pay_salary",              # выплачивать зарплату (owner)
    "manage_appeals",          # апелляции банов (owner + senior)
}

PERMISSIONS_BY_ROLE = {
    ROLE_OWNER: set(ALL_PERMISSIONS),
    ROLE_SENIOR: {
        "view_players",
        "moderate_ban",
        "moderate_unban",
        "adjust_balance",
        "view_market",
        "market_cancel",
        "view_logs",
        "review_applications",
        "manage_staff",
        "set_salary",
        "pay_salary",
        "manage_appeals",
    },
    ROLE_JUNIOR: {
        "view_players",
        "moderate_ban",
    },
    ROLE_MODERATOR: {
        "view_players",
        "moderate_ban",
    },
    ROLE_APPLICANT: set(),
    ROLE_SUSPENDED: set(),
}


def permissions_for_role(role: str) -> list[str]:
    return sorted(PERMISSIONS_BY_ROLE.get(role, set()))


async def get_admin_account_security(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name, role, status,
               hired_at, hired_by, rules_accepted_at, rules_version,
               payout_type, payout_details, registered_at
        FROM admin_accounts
        WHERE user_id = $1
        """,
        user_id,
    )
    if not row:
        return None

    role = row["role"] or ROLE_APPLICANT
    status = row["status"] or STATUS_PENDING

    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "firstName": row["first_name"],
        "role": role,
        "roleLabel": ROLE_LABELS.get(role, role),
        "status": status,
        "permissions": permissions_for_role(role) if status == STATUS_ACTIVE else [],
        "hiredAt": row["hired_at"].isoformat() if row["hired_at"] else None,
        "hiredBy": int(row["hired_by"]) if row["hired_by"] else None,
        "rulesAcceptedAt": row["rules_accepted_at"].isoformat() if row["rules_accepted_at"] else None,
        "rulesVersion": int(row["rules_version"] or 1),
        "payoutType": row["payout_type"],
        "payoutDetails": row["payout_details"],
        "registeredAt": row["registered_at"].isoformat() if row["registered_at"] else None,
    }


async def require_active_admin(
    request: Request,
    user_id: int = Depends(require_admin_session),
) -> int:
    account = await get_admin_account_security(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Админ-аккаунт не найден")

    if account["status"] != STATUS_ACTIVE:
        raise HTTPException(status_code=403, detail="Аккаунт администратора ещё не активирован")

    if account["role"] == ROLE_SUSPENDED:
        raise HTTPException(status_code=403, detail="Аккаунт администратора отстранён")

    request.state.admin_account = account
    return user_id


def require_admin_permission(permission: str):
    async def dependency(
        request: Request,
        user_id: int = Depends(require_active_admin),
    ) -> int:
        account = getattr(request.state, "admin_account", None)
        if not account:
            account = await get_admin_account_security(user_id)
            request.state.admin_account = account

        if permission not in set(account.get("permissions") or []):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        return user_id

    return dependency


def require_admin_role(*roles: str):
    allowed = set(roles)

    async def dependency(
        request: Request,
        user_id: int = Depends(require_active_admin),
    ) -> int:
        account = getattr(request.state, "admin_account", None)
        if not account:
            account = await get_admin_account_security(user_id)
            request.state.admin_account = account

        if account.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        return user_id

    return dependency