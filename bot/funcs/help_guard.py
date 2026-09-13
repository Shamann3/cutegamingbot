# -*- coding: utf-8 -*-
"""Кто может нажимать кнопки справки."""


def help_callback_allowed(user_id: int, message_id: int, owners: dict | None = None) -> bool:
    """Личный «хелп» — только автор. Карточка без владельца (приветствие бота,
    потерянный pkl после рестарта) — общая, иначе кнопки выглядят мёртвыми."""
    owner = None
    for uid, mid in (owners or {}).items():
        try:
            if int(mid) == int(message_id):
                owner = int(uid)
                break
        except (TypeError, ValueError):
            continue
    if owner is None:
        return True
    try:
        return int(user_id) == owner
    except (TypeError, ValueError):
        return False
