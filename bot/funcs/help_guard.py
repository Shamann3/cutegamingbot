# -*- coding: utf-8 -*-
"""Кто может нажимать кнопки справки."""


def _owner_pairs(owners):
    if owners is None:
        return ()
    items = getattr(owners, "items", None)
    if callable(items):
        try:
            return tuple(items())
        except Exception:
            return ()
    try:
        return tuple((key, owners[key]) for key in owners)
    except Exception:
        return ()


def help_callback_allowed(user_id: int, message_id: int, owners=None) -> bool:
    """Личный «хелп» — только автор. Карточка без владельца (приветствие бота,
    потерянный pkl после рестарта) — общая, иначе кнопки выглядят мёртвыми."""
    owner = None
    for uid, mid in _owner_pairs(owners):
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
