# -*- coding: utf-8 -*-
"""Должности сотрудника, которые создаёт только создатель проекта.

Ключ роли стабильный: одно и то же название не плодит вторую строку.
Наказания в staff_rules стартуют выключенными. Вкладки панели — тоже.
"""
from __future__ import annotations

import hashlib

from db import db

_BUILTIN = frozenset({
    "owner",
    "senior_admin",
    "junior_admin",
    "moderator",
    "applicant",
    "suspended",
})


def role_key(title: str) -> str:
    clean = " ".join((title or "").lower().split())
    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:10]
    return f"custom_{digest}"


async def ensure_staff_post_table() -> None:
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_staff_posts (
            role_key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


async def is_custom_role(role: str) -> bool:
    key = (role or "").strip()
    if not key:
        return False
    posts = await list_staff_posts()
    return key in {item["id"] for item in posts}


async def list_staff_posts() -> list[dict]:
    await ensure_staff_post_table()
    rows = await db.pool.fetch(
        "SELECT role_key, title FROM epsilon_staff_posts ORDER BY created_at, title"
    )
    return [{"id": r["role_key"], "label": r["title"]} for r in rows]


async def create_staff_post(title: str) -> dict:
    clean = " ".join((title or "").split())
    if len(clean) < 2:
        raise ValueError("Название должности — хотя бы два символа")
    if len(clean) > 40:
        raise ValueError("Название длиннее 40 символов")
    key = role_key(clean)
    if key in _BUILTIN:
        raise ValueError("Это имя уже занято лестницей проекта")
    await ensure_staff_post_table()
    existing = await db.pool.fetchrow(
        "SELECT title FROM epsilon_staff_posts WHERE role_key = $1",
        key,
    )
    if existing:
        raise ValueError(f"Такая должность уже есть: {existing['title']}")
    await db.pool.execute(
        "INSERT INTO epsilon_staff_posts (role_key, title) VALUES ($1, $2)",
        key,
        clean,
    )
    from staff_rules import ensure_blank_role

    try:
        await ensure_blank_role(db.pool, key, clean)
    except Exception:
        # Вкладки уже есть. Наказания останутся пустыми, пока строка staff_rules не запишется.
        return {
            "id": key,
            "label": clean,
            "punishNote": "Должность создана. Строка наказаний не записалась — откройте матрицу ещё раз после перезапуска.",
        }
    return {"id": key, "label": clean}
