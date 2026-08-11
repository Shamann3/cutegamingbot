# -*- coding: utf-8 -*-
"""
Прозрачный патч aiogram-клавиатур под Мэджик.

Логика кнопок НЕ меняется — только обёртка классов + rebind.

ВАЖНО про pickle / Redis (button_kosti, button_bingo, …):
  Классы ОБЯЗАНЫ быть на уровне модуля (не внутри функции),
  иначе pickle падает:
    AttributeError: Can't get local object 'patch_aiogram_keyboards.<locals>.Magic…'

  При сериализации Magic-* превращаются в обычные InlineKeyboard*
  aiogram — сторы LazyGameStore остаются совместимы.

Выключается в config.py:  PATCH_KEYBOARDS = False
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from aiogram.types import InlineKeyboardButton as _AiogramInlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup as _AiogramInlineKeyboardMarkup

logger = logging.getLogger("magic")

_PATCHED = False
_MagicBtn: Any = None
_MagicMarkup: Any = None
_OrigBtn: Any = _AiogramInlineKeyboardButton
_OrigMarkup: Any = _AiogramInlineKeyboardMarkup
_BUILDER_PATCHED = False


# ── helpers для pickle (должны быть top-level, иначе снова local object) ──


def _rebuild_inline_button(data: Dict[str, Any]) -> _AiogramInlineKeyboardButton:
    """Восстановить обычную кнопку aiogram из dict (без Magic-класса)."""
    try:
        return _AiogramInlineKeyboardButton.model_validate(data)
    except Exception:
        return _AiogramInlineKeyboardButton(**data)


def _rebuild_inline_markup(data: Dict[str, Any]) -> _AiogramInlineKeyboardMarkup:
    """Восстановить обычную клавиатуру aiogram из dict (без Magic-класса)."""
    try:
        return _AiogramInlineKeyboardMarkup.model_validate(data)
    except Exception:
        return _AiogramInlineKeyboardMarkup(**data)


def _dump_model(obj: Any) -> Dict[str, Any]:
    try:
        return obj.model_dump(mode="python")
    except Exception:
        try:
            return dict(obj)
        except Exception:
            return {"inline_keyboard": getattr(obj, "inline_keyboard", [])}


# ── Magic-классы на уровне МОДУЛЯ (pickle-safe имя: bot.magic.patch.*) ──


class MagicInlineKeyboardButton(_AiogramInlineKeyboardButton):  # type: ignore[misc,valid-type]
    """Обёртка кнопки: логика та же, + счётчик Мэджик. Pickle → обычная кнопка."""

    _magic_wrapped = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            from bot.magic.core import magic

            magic.stats_buttons_created += 1
        except Exception:
            pass
        super().__init__(*args, **kwargs)

    def __reduce_ex__(self, protocol: int):
        # В Redis/pkl всегда кладём обычный InlineKeyboardButton
        try:
            return (_rebuild_inline_button, (_dump_model(self),))
        except Exception:
            return super().__reduce_ex__(protocol)


class MagicInlineKeyboardMarkup(_AiogramInlineKeyboardMarkup):  # type: ignore[misc,valid-type]
    """Обёртка markup: логика та же, + счётчик Мэджик. Pickle → обычный markup."""

    _magic_wrapped = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            from bot.magic.core import magic

            magic.stats_markups_created += 1
        except Exception:
            pass
        super().__init__(*args, **kwargs)

    def __reduce_ex__(self, protocol: int):
        try:
            return (_rebuild_inline_markup, (_dump_model(self),))
        except Exception:
            return super().__reduce_ex__(protocol)


def patch_aiogram_keyboards() -> bool:
    """Поставить Magic-обёртки на InlineKeyboard* и Builder."""
    global _PATCHED, _MagicBtn, _MagicMarkup, _OrigBtn, _OrigMarkup, _BUILDER_PATCHED
    if _PATCHED:
        rebind_project_modules()
        return True

    try:
        from bot.magic.core import magic
        import aiogram.types as aiotypes
    except Exception as e:
        logger.warning("patch import failed: %r", e)
        return False

    try:
        # Если уже запатчено другим путём
        if getattr(aiotypes.InlineKeyboardButton, "_magic_wrapped", False):
            _MagicBtn = aiotypes.InlineKeyboardButton
            _MagicMarkup = aiotypes.InlineKeyboardMarkup
            _PATCHED = True
            rebind_project_modules()
            return True

        _OrigBtn = _AiogramInlineKeyboardButton
        _OrigMarkup = _AiogramInlineKeyboardMarkup
        _MagicBtn = MagicInlineKeyboardButton
        _MagicMarkup = MagicInlineKeyboardMarkup

        aiotypes.InlineKeyboardButton = MagicInlineKeyboardButton  # type: ignore[misc,assignment]
        aiotypes.InlineKeyboardMarkup = MagicInlineKeyboardMarkup  # type: ignore[misc,assignment]

        if not _BUILDER_PATCHED:
            try:
                from aiogram.utils.keyboard import InlineKeyboardBuilder

                _orig_button = InlineKeyboardBuilder.button
                _orig_as_markup = InlineKeyboardBuilder.as_markup

                def _magic_button(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
                    try:
                        magic.stats_buttons_created += 1
                    except Exception:
                        pass
                    return _orig_button(self, *args, **kwargs)

                def _magic_as_markup(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
                    mk = _orig_as_markup(self, *args, **kwargs)
                    try:
                        magic.stats_markups_created += 1
                    except Exception:
                        pass
                    return mk

                InlineKeyboardBuilder.button = _magic_button  # type: ignore[method-assign]
                InlineKeyboardBuilder.as_markup = _magic_as_markup  # type: ignore[method-assign]
                _BUILDER_PATCHED = True
            except Exception as e:
                logger.warning("builder patch skip: %r", e)

        _PATCHED = True
        n = rebind_project_modules()
        logger.info("keyboards patched; rebound modules=%s", n)
        print(
            f"✅ [MAGIC] InlineKeyboard* под Мэджик "
            f"(логика не изменена, rebound={n} модулей, pickle-safe)"
        )
        return True
    except Exception as e:
        logger.exception("patch failed: %r", e)
        print(f"⚠️ [MAGIC] patch keyboards failed: {e!r}")
        return False


def rebind_project_modules() -> int:
    """
    Подменяет уже импортированные ссылки InlineKeyboard* на Magic-версии.

    Использует усиленный audit.rebind_all_inline_refs (ловит алиасы).
    Возвращает число затронутых модулей.
    """
    try:
        from bot.magic.audit import rebind_all_inline_refs

        mods, _attrs = rebind_all_inline_refs()
        return int(mods)
    except Exception:
        pass

    if _MagicBtn is None or _MagicMarkup is None:
        return 0

    changed = 0
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if not (
            name in ("main", "__main__")
            or name.startswith("bot.")
            or name.startswith("aiogram")
            or name.startswith("b_Eden")
            or name.startswith("server")
            or name.startswith("admin")
        ):
            continue
        try:
            d = getattr(mod, "__dict__", None)
            if not isinstance(d, dict):
                continue
            local = 0
            for attr, val in list(d.items()):
                if val is _OrigBtn or (
                    isinstance(val, type)
                    and getattr(val, "__name__", "") == "InlineKeyboardButton"
                    and not getattr(val, "_magic_wrapped", False)
                    and val is not _MagicBtn
                ):
                    setattr(mod, attr, _MagicBtn)
                    local += 1
                elif val is _OrigMarkup or (
                    isinstance(val, type)
                    and getattr(val, "__name__", "") == "InlineKeyboardMarkup"
                    and not getattr(val, "_magic_wrapped", False)
                    and val is not _MagicMarkup
                ):
                    setattr(mod, attr, _MagicMarkup)
                    local += 1
            if local:
                changed += 1
        except Exception:
            continue
    return changed
