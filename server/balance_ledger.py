# -*- coding: utf-8 -*-
"""Сложение кут по карманам: игроки, живые группы и проект."""
from __future__ import annotations


def _whole(value) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def split_pots(users, living_chat, living_dex, tech_chat, tech_dex) -> dict:
    """Те же корзины, что команда «все балансы», плюс технический карман проекта.

    «Все балансы» — игроки и чат-балансы, без покупок групп.
    «Система» — всё, включая покупки и технические группы.
    """
    people = _whole(users)
    groups_chat = _whole(living_chat)
    groups_dex = _whole(living_dex)
    project_chat = _whole(tech_chat)
    project_dex = _whole(tech_dex)
    groups = groups_chat + groups_dex
    project = project_chat + project_dex
    return {
        "users": people,
        "groups": groups,
        "project": project,
        "system": people + groups + project,
        "allBalances": people + groups_chat + project_chat,
        "livingChat": groups_chat,
        "livingDex": groups_dex,
        "techChat": project_chat,
        "techDex": project_dex,
    }
