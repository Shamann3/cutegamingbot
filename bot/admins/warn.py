# -*- coding: utf-8 -*-
"""
Система предупреждений (варнов) нарушителей в официальных группах проекта.

Идея: администратор выдаёт нарушителю предупреждение (с фото-доказательством).
Предупреждения копятся (по умолчанию до 3). При достижении лимита (3/3) код
АВТОМАТИЧЕСКИ выдаёт постоянный бан во всех официальных группах и обнуляет счёт.

Принцип работы скопирован с систем мута/кика/бана:
    • обязательное фото-доказательство (одношагово - подписью, или двушагово);
    • цель определяется по самому Telegram (ответ / @username / id / имя);
    • права берутся из таблицы staff_rules по столбцу «warn».

Подключение (main.py):
    from bot.admins.warn import attach_warn_system
    attach_warn_system(dp)

Форматы:
    • Ответ + фото + подпись:  варн причина
    • Без ответа + фото:        варн @user причина
                                варн username причина
                                варн 123456789 причина
    • Два шага: текст → фото (в течение 5 мин)
    • Отмена ожидания: отменить варн @user
    • Снять предупреждение:     снять варн @user · разварн @user
    • Проверить предупреждения: варны @user · варны (в ответ)

proof_media_id → staff_actions (action_type = 'warn')

Права:
    admin_accounts - должность (role), статус, доступность
    staff_rules    - столбец warn (1/0); код сам определяет, кому разрешено
"""
from __future__ import annotations

import os
import re
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from bot.db_create.pklcode import LazyGameStore

from bot.admins.punish_proof import (
  ensure_proof_pending_worker,
  is_proof_expired,
  proof_expires_at,
)

from aiogram import BaseMiddleware, F, Router
from aiogram.types import (
  CallbackQuery,
  InlineKeyboardButton,
  InlineKeyboardMarkup,
  Message,
  TelegramObject,
)

from bot.admins.mute import (
  ParseError,
  PlayerRef,
  StaffRef,
  Scope,
  _bot,
  _db,
  _ensure_mute_schema,
  _chat_link_inline,
  _format_chat_line,
  _format_chats_line,
  _format_mute_reason_block,
  _format_player_line,
  _format_scope_block,
  _format_duration_short,
  _format_until,
  _get_chat_display,
  _get_command_text,
  _get_proof_file_id,
  _get_reply_target_message,
  _has_command_text,
  _has_proof_media,
  _is_staff_chat,
  _proof_owner_token,
  _looks_like_telegram_username,
  _lookup_target_by_token,
  _require_staff_chat,
  _resolve_admin_identity,
  _resolve_target_from_body,
  _resolve_user_display,
  _user_link,
  _display_name_link,
  _edit_revoked_message,
  _edit_remove_keyboard,
  _resolve_reply_or_explicit,
  _extract_duration_and_reason,
  _body_starts_with_duration,
  Mode,
  parse_command_mode,
  mode_to_scope,
  _MOD_SCOPE_ALL_SUFFIXES,
  _MOD_SCOPE_FULL_SUFFIXES,
  parse_duration,
  role_title_from_cache,
  deny_permission,
  _rebase_expiry_at_now,
  _normalize_time_delta,
  self_revoke_denied_html,
  is_protected_creator,
  protected_creator_denied_html,
  SELF_REVOKE_ALERT,
  _service_unavailable_message,
  _generic_handler_error_message,
  _target_lookup_error_message,
  _db_acquire,
  _reply_db_unavailable,
  check_staff_permission,
  DbUnavailableError,
  NO_PREVIEW,
  cfg,
)

warn_router = Router(name="staff_warn")

# --- Лимит предупреждений: при достижении выдаётся автоматический бан ---
WARN_THRESHOLD: int = 3


# =============================================================================
#  📝 ТЕКСТЫ СИСТЕМЫ ПРЕДУПРЕЖДЕНИЙ - меняйте текст и эмодзи ПРЯМО ЗДЕСЬ
# -----------------------------------------------------------------------------
#  Всё, что видит администратор/нарушитель в системе варнов, собрано тут.
#  • Чтобы поменять текст - правьте строки.
#  • Чтобы поменять эмодзи - меняйте эмодзи прямо в строках.
#  • {фигурные_скобки} - это автоподстановка (имя, причина, счётчик и т.п.),
#    их трогать не нужно; можно убрать ненужную подстановку из текста.
# =============================================================================

class WarnText:
  # --- Строка срока предупреждения ---
  TERM_PERMANENT = "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : постоянное</b>"
  TERM_TIMED = (
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : {duration} · до</b> "
    "<code>{until}</code>"
  )

  # --- Эмодзи шкалы предупреждений (нарастание «тревожности») ---
  BAR_LOW = "<tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji>"      # 1 предупреждение
  BAR_MID = "<tg-emoji emoji-id='5336936725765700868'>🟠</tg-emoji>"      # 2 предупреждения
  BAR_HIGH = "<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>"     # 3 (лимит)
  BAR_EMPTY = "<tg-emoji emoji-id='5339113303522161846'>⚪️</tg-emoji>"    # свободные ячейки

  # --- Счётчик предупреждений ---
  COUNT_LINE = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> Предупреждения:</b> "
    "<b>{count}/{total}</b>  {bar}"
  )
  # Строка одной «копилки» предупреждений (обычный / варналл / варнфулл).
  TYPED_LINE = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> {label}:</b> "
    "<b>{count}/{total}</b>  {bar}"
  )
  TYPED_LABEL_CHAT = "Обычные (эта группа)"
  TYPED_LABEL_CHAT_ANY = "Обычные (в группе)"
  TYPED_LABEL_ALL = "Во всех группах"
  TYPED_LABEL_FULL = "Во всём проекте"

  # --- Тип предупреждения (короткая «шапка» во ВСЕХ сообщениях системы варнов) ---
  TYPE_LINE = "<b><tg-emoji emoji-id='5397976749436842796'>⚡</tg-emoji> {label}</b>"
  WARN_TYPE_LABEL_CHAT = "Варн · эта группа"
  WARN_TYPE_LABEL_ALL = "Варналл · все группы"
  WARN_TYPE_LABEL_FULL = "Варнфулл · весь проект"
  WARN_TYPE_LABEL_MIXED = "Варны · все виды"

  # --- Охват предупреждения по типу (chat / all / full) ---
  # Точнее общего scope-блока: отдельно различает «весь проект» (варнфулл).
  SCOPE_CHAT = (
    "<b><tg-emoji emoji-id='6024039683904772353'>👤</tg-emoji> Охват:</b> "
    "<i>только эта группа</i>"
  )
  SCOPE_ALL = (
    "<b><tg-emoji emoji-id='6024039683904772353'>👤</tg-emoji> Охват:</b> "
    "<i>все официальные группы проекта</i>"
  )
  SCOPE_FULL = (
    "<b><tg-emoji emoji-id='6024039683904772353'>👤</tg-emoji> Охват:</b> "
    "<i>весь проект</i>"
  )

  # --- Последствия по типу варна (для сообщений выдачи / ожидания / ЛС) ---
  CONSEQUENCE = "<blockquote><i>При {th}/{th} - {effect}.</i></blockquote>"
  CONSEQUENCE_EFFECT_CHAT = "бан в этой группе"
  CONSEQUENCE_EFFECT_ALL = "бан во всех группах"
  CONSEQUENCE_EFFECT_FULL = "блокировка во всём проекте"
  # Короткая фраза «что будет при лимите» для ЛС-уведомления нарушителю.
  BAN_PHRASE_CHAT = "бан в этой группе"
  BAN_PHRASE_ALL = "бан во всех официальных группах проекта"
  BAN_PHRASE_FULL = "полная блокировка во всём проекте"

  # --- Справка ---
  HELP = (
    "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Предупреждения</b>\n"
    "<blockquote><i>Нужно фото (в подписи или ответом, до {timeout} мин). "
    "Без срока - навсегда.</i></blockquote>\n"
    "<b>Выдать:</b> <code>варн @user 1ч причина</code>\n"
    "· <code>варн</code> - эта группа\n"
    "· <code>варналл</code> - все группы\n"
    "· <code>варнфулл</code> - весь проект\n"
    "<i>При {th}/{th} - авто-бан (по охвату варна).</i>\n"
    "<b>Снять:</b> <code>разварн @user</code> · <code>разварналл</code> · <code>разварнфулл</code>\n"
    "<b>Все:</b> <code>очистить варны @user</code>\n"
    "<b>Проверить:</b> <code>варны @user</code> · <code>мои варны</code>\n"
    "<b>Отмена фото:</b> <code>отменить варн @user</code>"
  )

  # --- Ошибки разбора цели ---
  NOT_FOUND_EXPLICIT = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "<code>{token}</code> не найден</b>"
  )
  NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Кого предупредить?</b>\n"
    "<blockquote><i>Ответьте на сообщение или: <code>варн @user причина</code></i></blockquote>"
  )
  NEED_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<blockquote><i>Сначала выберите кого: <code>варн @user срок причина</code></i></blockquote>"
  )
  NOT_FOUND_USERNAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>@{username}</code> не найден</b>"
  )
  NOT_FOUND_ID = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> ID <code>{token}</code> не найден</b>"
  NOT_FOUND_NAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> «{token}» не найден</b>"
  BAD_DURATION = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Неверное время :</b> <code>{duration}</code>"

  # --- Уведомление нарушителя в ЛС ---
  VIOLATOR_TAIL_LEFT = (
    "<blockquote><i>Ещё {left} - и {ban_phrase}.</i></blockquote>"
  )
  VIOLATOR_TAIL_LAST = (
    "<blockquote><i>Лимит - далее {ban_phrase}.</i></blockquote>"
  )
  VIOLATOR = (
    "{type_line}\n"
    "{count_line}{reason_suffix}\n"
    "{tail}"
  )

  # --- Уведомления в группах (варналл) ---
  GROUP_TITLE = "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Выдано предупреждение</b>"
  GROUP_FOOTER = (
    "<blockquote><b><i>{actor} выдал {player_short} предупреждение "
    "({count}/{total}).</i></b></blockquote>"
  )
  GROUP = (
    "{type_line}\n"
    "{player_line}\n"
    "{count_line}{reason_suffix}\n"
    "{consequence}"
  )

  # --- Истечение временного варна ---
  EXPIRED_DM = (
    "{type_line} <b>· снято по сроку</b>\n"
    "{count_line}"
  )
  EXPIRED_GROUP = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Варн снят</b> <i>· истёк срок</i>\n"
    "{type_line}\n"
    "{player_line}\n"
    "{chat_line}\n"
    "{count_line}"
  )
  # Доп. примечание, когда вместе со снятием варна снимается и авто-блокировка.
  EXPIRED_DM_UNBLOCKED = (
    "\n<blockquote><i>Бан снят - варнов меньше порога.</i></blockquote>"
  )
  EXPIRED_DM_UNBLOCKED_FULL = (
    "\n<blockquote><i>Блокировка проекта снята - группы и приложение открыты.</i></blockquote>"
  )
  EXPIRED_GROUP_UNBLOCKED = (
    "\n<blockquote><i>Бан снят - варнов меньше {total}.</i></blockquote>"
  )

  # --- Успех выдачи (в группе) ---
  SUCCESS = (
    "{type_line} <b>· выдан</b>\n"
    "{player_line}\n"
    "{staff_line}\n"
    "{count_line}{reason_suffix}\n"
    "{consequence}"
  )

  # --- Авто-бан по достижению лимита ---
  BAN_SCOPE_CHAT = "<i>только эта группа</i>"
  BAN_SCOPE_ALL = "<i>все официальные группы проекта</i>"
  BAN_SCOPE_FULL = "<i>весь проект - все группы и WebApp-приложение</i>"
  BAN_RESULT_OK = (
    "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Лимит {th}/{th} - бан</b>\n"
    "{type_line}\n"
    "{player_line}{reason_suffix}\n"
    "{closing}"
  )
  # Закрывающая строка авто-бана зависит от срочности предупреждений:
  BAN_CLOSING_PERMANENT = (
    "<blockquote><i>Снимет только админ.</i></blockquote>"
  )
  BAN_CLOSING_TIMED = (
    "<blockquote><i>Снимется, когда варнов станет меньше {th}.</i></blockquote>"
  )
  BAN_RESULT_FAIL = (
    "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Лимит {th}/{th}</b>\n"
    "{type_line}\n"
    "{player_line}\n"
    "<blockquote><i>Бан не применён - проверьте права бота.</i></blockquote>"
  )

  # --- Пруф / ошибки выдачи ---
  PROOF_MISSING = (
    "<b><tg-emoji emoji-id='5454419255430767770'>📎</tg-emoji> Предупреждение не выдано</b>\n"
    "<blockquote><i>Фото-доказательство не получено.</i></blockquote>"
  )
  DB_FAILED = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Не удалось сохранить предупреждение.</b>"
  NEED_PHOTO = "<b><tg-emoji emoji-id='5305265301917549162'>📎</tg-emoji> Нужно фото - прикрепите изображение.</b>"
  WRONG_CHAT = (
    "{greeting}\n"
    "{staff_line}\n"
    "{player_line}{pending_chat_line}"
    "<blockquote><i>Отправьте фото в тот же чат, где была команда.</i></blockquote>"
  )

  # --- Ожидание фото (шаг 2) ---
  PENDING = (
    "{type_line} <b>· ждём фото</b>\n"
    "{player_line}\n"
    "{reason_part}"
    "<b>Будет:</b> <b>{next_count}/{th}</b>\n"
    "<blockquote><i>Фото в этот чат за {timeout} мин · отмена - кнопкой.</i></blockquote>"
  )
  EXPIRED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Время вышло</b>\n"
    "{player_line}\n"
    "<blockquote><i>Варн не выдан - фото не пришло.</i></blockquote>"
  )
  CANCELLED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "<blockquote><i>Варн не выдан.</i></blockquote>"
  )
  SUPERSEDED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "<blockquote><i>Начато новое действие модерации.</i></blockquote>"
  )
  CANCEL_FALLBACK = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "<blockquote><i>Варн не выдан.</i></blockquote>"
  )

  # --- Запреты ---
  SELF = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя предупредить себя</b>"
  BOT = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя предупредить бота</b>"

  # --- Снятие одного предупреждения ---
  NO_WARNS = (
    "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> У {player_short} нет варнов</b>"
  )
  UNWARN_DB_FAIL = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Не удалось снять предупреждение.</b>"
  UNWARN_DM = (
    "{type_line} <b>· снят</b>\n"
    "<blockquote><i>{actor} снял один варн.</i></blockquote>\n"
    "{count_line}"
  )
  UNWARN_OK = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Варн снят</b>\n"
    "{type_line}\n"
    "{player_line}\n"
    "{count_line}"
  )

  # --- Снятие варналл / варнфулл (полный откат во всех группах / во всём проекте) ---
  UNWARN_SCOPED_TITLE_ALL = "Варны сняты во всех группах"
  UNWARN_SCOPED_TITLE_FULL = "Откат · варны и блокировка сняты"
  UNWARN_SCOPED_DETAIL_ALL = (
    "<blockquote><i>Разблокирован во всех группах.</i></blockquote>"
  )
  UNWARN_SCOPED_DETAIL_FULL = (
    "<blockquote><i>Блокировка проекта снята.</i></blockquote>"
  )
  UNWARN_SCOPED_OK = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> {title}</b>\n"
    "{type_line}\n"
    "{player_line}\n"
    "{detail}"
  )
  UNWARN_SCOPED_DM = (
    "{type_line}\n"
    "<blockquote><i>{actor} снял все ваши варны{extra}.</i></blockquote>\n"
    "{tail}"
  )
  UNWARN_SCOPED_DM_EXTRA_FULL = " и блокировку"
  UNWARN_SCOPED_DM_TAIL_ALL = "<blockquote><i>Снова можете писать во всех группах.</i></blockquote>"
  UNWARN_SCOPED_DM_TAIL_FULL = "<blockquote><i>Доступ к проекту восстановлен.</i></blockquote>"
  UNWARN_GROUP_TITLE = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Предупреждения сняты</b>"
  )
  UNWARN_GROUP = (
    "{group_title}\n"
    "{type_line}\n"
    "{player_line}\n"
    "{chat_line}\n"
    "<blockquote><b><i>{actor} снял варны с {player_short} {scope_tail}.</i></b></blockquote>"
  )
  UNWARN_GROUP_TAIL_ALL = "во всех группах"
  UNWARN_GROUP_TAIL_FULL = "и блокировку во всём проекте"

  # --- Снятие всех предупреждений ---
  CLEAR_DM = (
    "<blockquote><i>{actor} снял все ваши варны.</i></blockquote>\n"
    "{count_line}"
  )
  CLEAR_OK = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Все варны сняты</b>\n"
    "{type_line}\n"
    "{player_line}\n"
    "<blockquote><i>Снято: {before}.</i></blockquote>\n"
    "{count_line}"
  )

  # =====================================================================
  #  ИНТЕРАКТИВНЫЙ обзор предупреждений - «мои варны» / «варны @user».
  #  Показываются ТОЛЬКО реально имеющиеся виды (варн / варналл / варнфулл).
  #  Кнопки ведут к подробностям каждого вида и к простому объяснению
  #  «как это работает» - понятно даже ребёнку.
  # =====================================================================
  OV_TITLE_SELF = (
    "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Ваши предупреждения</b>"
  )
  OV_TITLE_OTHER = (
    "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Предупреждения участника</b>"
  )
  # Названия видов (коротко).
  OV_KIND_TITLE_CHAT = "Варн"
  OV_KIND_TITLE_ALL = "Варналл"
  OV_KIND_TITLE_FULL = "Варнфулл"
  OV_KIND_NOTE_HERE = " (эта группа)"
  OV_KIND_NOTE_ANY = " (в группе)"

  # Короткие ярлыки видов для подвала.
  OV_KIND_LABEL_CHAT = "варн"
  OV_KIND_LABEL_ALL = "варналл"
  OV_KIND_LABEL_FULL = "варнфулл"

  # Нижняя строка-последствие при лимите (коротко, ≤7 слов).
  OV_FX_CHAT = "блокировка в этой группе"
  OV_FX_ALL = "блокировка во всех группах"
  OV_FX_FULL = "блокировка во всём проекте"
  OV_FOOTER = "<blockquote><b><i>При {th}/{th} - {effect}.</i></b></blockquote>"

  # Последствие ПОД КАЖДЫМ видом варна (понятно даже ребёнку: что и где будет).
  #  • для обычного варна - ссылка на КОНКРЕТНУЮ группу (по строке на группу);
  #  • для варналл/варнфулл - общий охват.
  # Это ВНУТРЕННИЙ текст: оборачивается в один blockquote вместе со сроками варнов.
  OV_CONS_CHAT = "При {th}/{th} - блокировка в {group}."
  OV_CONS_ALL = "При {th}/{th} - блокировка во всех официальных группах."
  OV_CONS_FULL = "При {th}/{th} - блокировка во всём проекте."

  # Полная карточка ОДНОГО варна (внутри blockquote под строкой вида):
  #   кто выдал · причина · когда выдан · когда исчезнет.
  OV_ITEM_ACTOR = (
    "<b>{num}.</b> <tg-emoji emoji-id='5316887736823591263'>👮</tg-emoji> <i>{actor}</i>"
  )
  OV_ITEM_REASON = "<tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> <i>{reason}</i>"
  OV_ITEM_WHEN = "<tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> <i>{when}</i>"
  OV_ITEM_CREATED = "выдан {created}"
  OV_ITEM_EXP_TIMED = "исчезнет {until}"
  OV_ITEM_EXP_PERM = "постоянный · снимет только админ"
  OV_ITEM_REASON_NONE = "без причины"

  # Строка одного вида: счётчик + шкала (одна строка, без лишнего текста).
  OV_ROW = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> {title}:</b> "
    "<b>{count}/{th}</b>  {bar}"
  )
  # Вторая строка вида: создаёт ощущение приближения к черте (мягко, но ясно).
  OV_ROW_NOTE_LEFT = "<i>↳ ещё {left} - и {effect}</i>"
  OV_ROW_NOTE_LAST = "<b><i>↳ остался последний шаг - и {effect}</i></b>"
  OV_ROW_NOTE_DONE = "<b><i>↳ предел достигнут - {effect}</i></b>"

  OV_HOME_HINT = (
    "<blockquote><i>Нажмите на любой вид ниже - покажу подробности. А кнопка "
    "«Как это работает» объяснит всё простыми словами.</i></blockquote>"
  )
  OV_EMPTY_SELF = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> У вас нет предупреждений</b>\n"
    "{player_line}\n"
    "<blockquote><b><i>Прекрасно! Так держать - продолжайте соблюдать правила, "
    "и всё будет хорошо.</i></b></blockquote>"
  )
  OV_EMPTY_OTHER = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> У участника нет "
    "предупреждений</b>\n"
    "{player_line}"
  )

  # Экран подробностей одного вида.
  OV_DETAIL_TITLE = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> {title} - "
    "{count}/{th}</b>  {bar}"
  )
  OV_DETAIL_EFFECT = (
    "<blockquote><b><i>Если этого вида станет {th}/{th} - {effect}.</i></b>\n"
    "<i>{extra}</i></blockquote>"
  )
  OV_DETAIL_EXTRA_CHAT = "Считается только в этой группе."
  OV_DETAIL_EXTRA_ALL = "Считается во всех официальных группах вместе."
  OV_DETAIL_EXTRA_FULL = (
    "Считается по всему проекту. Блокировка закроет и все группы, "
    "и приложение."
  )
  OV_DETAIL_NONE = (
    "<blockquote><i>Предупреждений этого вида у вас нет - это хорошо.</i></blockquote>"
  )
  OV_ITEMS_OPEN = "<blockquote expandable>"
  OV_ITEMS_CLOSE = "</blockquote>"
  OV_ITEM = (
    "\n<b>{idx}.</b> {actor}{group_part}\n"
    "    <tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> {reason}\n"
    "    <tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> {term}"
  )
  OV_ITEM_GROUP_LINK = "  ·  <a href='{url}'>{group}</a>"
  OV_ITEM_GROUP_PLAIN = "  ·  <i>{group}</i>"
  OV_TERM_PERMANENT = "постоянное"
  OV_TERM_TIMED = "временное · до {until}"
  OV_REASON_NONE = "без причины"

  # Экран «как это работает» (только имеющиеся виды; если их нет - все три).
  OV_INFO_TITLE = "<b>ℹ️ Как всё устроено - простыми словами</b>"
  OV_INFO_INTRO = (
    "<blockquote><i>Предупреждение - это вежливое замечание. Их собирается до "
    "{th}. На {th}/{th} включается блокировка. Чем серьёзнее вид - тем шире "
    "блокировка.</i></blockquote>"
  )
  OV_INFO_CHAT = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> Варн</b> - замечание "
    "в этой группе. Наберётся {th} - <b>закроется доступ в эту группу</b>."
  )
  OV_INFO_ALL = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> Варналл</b> - замечание "
    "сразу во всех группах. Наберётся {th} - <b>закроется доступ во все официальные "
    "группы</b>."
  )
  OV_INFO_FULL = (
    "<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> Варнфулл</b> - самое "
    "серьёзное. Наберётся {th} - <b>закроется доступ ко всему проекту: и группы, "
    "и приложение</b>."
  )
  OV_INFO_TAIL = (
    "<blockquote><i>Каждый вид считается отдельно. Временные предупреждения "
    "исчезнут сами, когда выйдет их срок; постоянные снимает только администратор. "
    "Соблюдайте правила - и беспокоиться будет не о чем.</i></blockquote>"
  )

  # Подвал главного экрана - тон усиливается по мере приближения к черте.
  OV_FOOTER_LEFT_SELF = (
    "<blockquote><b><i>Пожалуйста, будьте аккуратны: ближе всего «{label}» - "
    "осталось {left} до блокировки ({th}/{th}). Соблюдайте правила, и всё будет "
    "хорошо.</i></b></blockquote>"
  )
  OV_FOOTER_LAST_SELF = (
    "<blockquote><b><i>⚠️ Остался последний шаг по виду «{label}» - ещё одно "
    "предупреждение, и последует блокировка. Очень просим вас быть "
    "внимательнее.</i></b></blockquote>"
  )
  OV_FOOTER_LEFT_OTHER = (
    "<blockquote><b><i>Ближе всего «{label}» - осталось {left} до блокировки "
    "({th}/{th}).</i></b></blockquote>"
  )
  OV_FOOTER_LAST_OTHER = (
    "<blockquote><b><i>По виду «{label}» остался последний шаг до "
    "блокировки.</i></b></blockquote>"
  )
  OV_FOOTER_DONE = (
    "<blockquote><b><i>Предел по виду «{label}» достигнут - действует блокировка. "
    "Если хотите всё исправить - обратитесь к администрации.</i></b></blockquote>"
  )

  # Кнопки.
  OV_BTN_KIND = "{title}: {count}/{th}"
  OV_BTN_INFO = "Как это работает"
  OV_BTN_BACK = "Назад"
  OV_BTN_REFRESH = "Обновить"

  # Всплывающие ответы callback.
  OV_CB_FOREIGN = "Эти кнопки доступны только тому, кто открыл обзор."
  OV_CB_BAD = "Кнопка устарела - откройте обзор заново."

  # --- Отмена ожидания (команды) ---
  CANCEL_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<blockquote><i>Ответьте на сообщение или: <code>отменить варн @user</code></i></blockquote>"
  )
  NO_PENDING = (
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет ожидания варна</b>\n"
    "{player_line}"
  )
  OTHER_PENDING = (
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> В ожидании другой нарушитель</b>\n"
    "{pending_player_line}\n"
    "<blockquote><i>Отмена: <code>{cancel_hint}</code></i></blockquote>"
  )
  CANCEL_HELP = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Для кого отменить?</b>\n"
    "<blockquote><i><code>{cancel_hint}</code> · или кнопкой под сообщением.</i></blockquote>"
  )

  # --- Кнопка и всплывающие ответы (callback) ---
  BTN_CANCEL = "Отменить ожидание"
  BTN_REVOKE = "Снять варн"
  CB_BAD_DATA = "Некорректные данные."
  CB_ONLY_AUTHOR = "Отменить может только автор команды."
  CB_DB = "База данных временно недоступна."
  CB_NO_PERM = "Недостаточно прав."
  CB_DONE = "Ожидание уже завершено или истекло."
  CB_STALE = "Данные устарели. Используйте команду отмены."
  CB_WRONG_CHAT = "Действие недоступно в этой группе."
  CB_CANCELLED = "Ожидание отменено."
  CB_REVOKED = "Предупреждение снято."
  CB_NONE = "У нарушителя нет предупреждений."
  CB_REVOKE_FAILED = "Не удалось снять предупреждение - попробуйте позже."
  CB_SELF_REVOKE = SELF_REVOKE_ALERT
  REVOKED_EDIT = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Предупреждение снято</b>\n"
    "{staff_line}\n{player_line}\n{type_line}\n{count_line}"
  )


# --- Команды ---
_WARN_CMD_ROOTS: Tuple[str, ...] = (
  "варн", "warn", "предупредить", "предупреждение", "пред",
)
WARN_COMMANDS: frozenset = frozenset({
  "варн", "warn", "/warn", "/варн", "предупредить", "предупреждение", "пред", "/пред",
})
# Снятие предупреждения: «снять варн @user», /unwarn, /unwarns и т.п.
#   • «снять варн» / «разварн»        - снять ОДНО предупреждение (эта группа);
#   • «снять варналл» / «разварналл»  - снять предупреждения + разблокировать во
#                                       ВСЕХ официальных группах;
#   • «снять варнфулл» / «разварнфулл»- снять предупреждения + полностью снять
#                                       блокировку во ВСЁМ проекте (WebApp + группы).
# Поддерживаются как слитные («снятьварн»), так и раздельные («снять варн») формы.
UNWARN_COMMANDS: frozenset = frozenset({
  "разварн", "unwarn", "unwarns", "/unwarn", "/unwarns", "/разварн", "/снятьварн",
  "минусварн", "снятьварн", "убратьварн",
})
# Корни команды снятия предупреждения (для суффиксов …алл / …фулл).
_UNWARN_CMD_ROOTS: Tuple[str, ...] = (
  "разварн", "unwarn", "снятьварн", "минусварн", "убратьварн",
)
# Singular-формы («варн», «варна», «предупреждение») с опциональным суффиксом
# режима (алл / фулл / all / full / все). Группа 1 - суффикс режима.
_UNWARN_RE = re.compile(
  r"^(?:снять|убрать|снимите|уберите|минус)\s+"
  r"(?:варн|варна|предупреждение|пред)"
  r"(алл|all|все|всё|вся|фулл|фул|full)?\b",
  re.IGNORECASE,
)
# Полная очистка ВСЕХ предупреждений: «снять все варны», «очистить варны», /clearwarns
CLEAR_WARNS_COMMANDS: frozenset = frozenset({
  "очиститьварны", "сброситьварны", "обнулитьварны", "clearwarns", "/clearwarns",
  "/очиститьварны",
})
# Plural-формы («варны», «предупреждения») и «все …» → снять все.
_CLEAR_WARNS_RE = re.compile(
  r"^(?:снять|убрать|снимите|уберите|очистить|сбросить|обнулить)\s+"
  r"(?:все\s+)?(?:варны|варнов|предупреждения|предупреждений)\b",
  re.IGNORECASE,
)
# Проверка предупреждений участника - доступно любому пользователю (не только staff).
WARN_STATUS_COMMANDS: frozenset = frozenset({
  "варны", "warns", "/warns", "/варны", "предупреждения",
})
# «Мои варны» - любой пользователь может посмотреть СВОИ предупреждения.
MY_WARNS_COMMANDS: frozenset = frozenset({
  "моиварны", "моиварн", "моипредупреждение", "моипредупреждения",
  "mywarns", "mywarn", "/mywarns", "/mywarn", "/моиварны", "/моиварн",
})
_MY_WARNS_RE = re.compile(
  r"^мои\s+(?:варны|варнов|предупреждения|предупреждений|преды)\b",
  re.IGNORECASE,
)
_MY_WARN_SINGULAR_RE = re.compile(
  r"^мой\s+(?:варн|варна|предупреждение|пред)\b",
  re.IGNORECASE,
)
# Отмена ожидания фото
_CANCEL_WARN_RE = re.compile(r"^(?:отмена|отменить)\s+(?:варн|варна)\b", re.IGNORECASE)

WARN_LOG_FILE = os.path.join(
  os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
  "log_warn.txt",
)

_pending_warns: Dict[int, Dict[str, Any]] = LazyGameStore("_pending_warns")
_warn_system_attached = False
_warn_maintenance_last = 0.0
_WARN_MAINTENANCE_INTERVAL_SEC = 5.0

_warn_schema_ready = False
_warn_schema_fail_last = 0.0


class WarnDebug:
  @staticmethod
  def log(stage: str, detail: str, **fields: Any) -> None:
    if not cfg.DEBUG:
      return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items()) if fields else ""
    line = f"[WARN][{stage}] {detail}" + (f" | {extra}" if extra else "")
    print(line)
    try:
      with open(WARN_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception as e:
      print(f"[WARN][LOGFILE] write error: {e}")

  @staticmethod
  def error(stage: str, detail: str, exc: Optional[BaseException] = None, **fields: Any) -> None:
    tb = traceback.format_exc() if exc else ""
    WarnDebug.log(stage, f"ERROR: {detail}", **fields)
    if tb:
      print(tb)
      try:
        with open(WARN_LOG_FILE, "a", encoding="utf-8") as fh:
          fh.write(tb + "\n")
      except Exception:
        pass


def _debug_hint(code: str) -> str:
  if not cfg.DEBUG_ADMIN_HINTS:
    return ""
  return f"\n\n<i>🔧 debug:</i> <code>{escape(code)}</code>"


@dataclass
class ParsedWarn:
  target_id: int
  target_name: str
  target_username: Optional[str]
  reason: str
  scope: Scope = "chat"
  # Режим: chat / all / full - определяет охват авто-бана при 3/3.
  mode: Mode = "chat"
  until: Optional[datetime] = None
  duration_text: Optional[str] = None
  time_delta: Optional[timedelta] = None
  duration_minutes: Optional[int] = None

  @property
  def is_full(self) -> bool:
    return self.mode == "full"


def _cmd_word(text: str) -> str:
  parts = (text or "").strip().split()
  if not parts:
    return ""
  return parts[0].lower().split("@")[0]


def _looks_like_username_token(token: str) -> bool:
  return _looks_like_telegram_username(token)


# ---------------------------------------------------------------------------
# Распознавание команд
# ---------------------------------------------------------------------------

def _is_warn_command(text: str) -> bool:
  ok, _ = parse_command_mode(_cmd_word(text), WARN_COMMANDS, _WARN_CMD_ROOTS)
  return ok


def _warn_command_mode(text: str) -> Mode:
  """Режим варна: chat (варн) / all (варналл) / full (варнфулл)."""
  ok, mode = parse_command_mode(_cmd_word(text), WARN_COMMANDS, _WARN_CMD_ROOTS)
  return mode if ok else "chat"


def _warn_command_scope(text: str) -> Scope:
  return mode_to_scope(_warn_command_mode(text))


# Режим варна → ключ права в staff_rules (warn / warnall / warnfull).
_WARN_MODE_PERMISSION: Dict[str, str] = {
  "chat": "warn",
  "all": "warnall",
  "full": "warnfull",
}


def _warn_permission_action(text: str) -> str:
  return _WARN_MODE_PERMISSION.get(_warn_command_mode(text), "warn")


def _suffix_to_mode(suffix: str) -> Mode:
  """Суффикс режима снятия → режим: алл/all → all; фулл/фул/full → full."""
  s = (suffix or "").strip().lower()
  if not s:
    return "chat"
  if s in _MOD_SCOPE_FULL_SUFFIXES:
    return "full"
  if s in _MOD_SCOPE_ALL_SUFFIXES:
    return "all"
  return "chat"


def _unwarn_mode(text: str) -> Optional[Mode]:
  """Режим снятия предупреждения (chat/all/full) или None, если это не команда снятия."""
  t = (text or "").strip()
  if not t:
    return None
  ok, mode = parse_command_mode(_cmd_word(t), UNWARN_COMMANDS, _UNWARN_CMD_ROOTS)
  if ok:
    return mode
  m = _UNWARN_RE.match(t)
  if m:
    return _suffix_to_mode(m.group(1) or "")
  return None


def _is_unwarn_command(text: str) -> bool:
  return _unwarn_mode(text) is not None


def _is_clear_warns_command(text: str) -> bool:
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in CLEAR_WARNS_COMMANDS:
    return True
  return bool(_CLEAR_WARNS_RE.match(t))


def _is_warn_status_command(text: str) -> bool:
  return _cmd_word(text) in WARN_STATUS_COMMANDS


def _is_my_warns_command(text: str) -> bool:
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in MY_WARNS_COMMANDS:
    return True
  if _MY_WARNS_RE.match(t):
    return True
  return bool(_MY_WARN_SINGULAR_RE.match(t))


def _is_cancel_warn_command(text: str) -> bool:
  return bool(_CANCEL_WARN_RE.match((text or "").strip()))


def _is_warn_related_message(message: Message) -> bool:
  if not message.from_user:
    return False
  text = _get_command_text(message)
  if text:
    low = text.lower()
    if _is_cancel_warn_command(text):
      return True
    if _is_clear_warns_command(text):
      return True
    if _is_unwarn_command(text):
      return True
    if _is_my_warns_command(text):
      return True
    if _is_warn_status_command(text):
      return True
    if _is_warn_command(text):
      return True
    if low in ("отмена", "cancel", "/cancel"):
      return True
  from bot.admins.punish_proof import pending_contains
  if _has_proof_media(message) and pending_contains(_pending_warns, message.from_user.id):
    return True
  return False


def _strip_command_prefix(text: str, commands: frozenset) -> str:
  t = (text or "").strip()
  if _cmd_word(t) in commands:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  return ""


def _strip_unwarn_prefix(text: str) -> str:
  t = (text or "").strip()
  ok, _ = parse_command_mode(_cmd_word(t), UNWARN_COMMANDS, _UNWARN_CMD_ROOTS)
  if ok:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  m = _UNWARN_RE.match(t)
  if m:
    return t[m.end():].strip()
  return ""


def _strip_clear_warns_prefix(text: str) -> str:
  t = (text or "").strip()
  if _cmd_word(t) in CLEAR_WARNS_COMMANDS:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  m = _CLEAR_WARNS_RE.match(t)
  if m:
    return t[m.end():].strip()
  return ""


def _strip_cancel_warn_prefix(text: str) -> str:
  m = _CANCEL_WARN_RE.match((text or "").strip())
  if not m:
    return ""
  return text[m.end():].strip()


# ---------------------------------------------------------------------------
# База данных: схема и операции со счётчиком предупреждений
# ---------------------------------------------------------------------------

async def _ensure_warn_schema() -> None:
  """Создаёт таблицу active_warns (по строке на каждое активное предупреждение)."""
  global _warn_schema_ready, _warn_schema_fail_last
  if _warn_schema_ready:
    return
  if not await _db().ensure_pool():
    now = time.time()
    if now - _warn_schema_fail_last > 60:
      WarnDebug.log("SCHEMA", "ensure skipped - db unavailable")
      _warn_schema_fail_last = now
    return
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_warns (
          id              SERIAL      PRIMARY KEY,
          user_id         BIGINT      NOT NULL,
          chat_id         BIGINT,
          admin_user_id   BIGINT,
          admin_name      TEXT,
          admin_role      TEXT,
          reason          TEXT,
          proof_media_id  TEXT,
          expires_at      TIMESTAMP,
          scope           TEXT        DEFAULT 'chat',
          mode            TEXT        DEFAULT 'chat',
          created_at      TIMESTAMP   DEFAULT NOW()
        )
        """,
      )
      await conn.execute(
        "ALTER TABLE active_warns ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP",
      )
      await conn.execute(
        "ALTER TABLE active_warns ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'chat'",
      )
      # Режим предупреждения: chat / all / full - независимые «копилки».
      await conn.execute(
        "ALTER TABLE active_warns ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'chat'",
      )
      # Бэкфилл для записей, созданных до появления столбца mode: у них режим
      # не сохранялся, но scope='all' однозначно указывает на «во всех группах».
      # (Старые «фулл»-варны тоже имели scope='all' - это допустимо: трактуем как
      # 'all'. Идемпотентно: новые варны всегда пишут mode явно.)
      await conn.execute(
        "UPDATE active_warns SET mode = 'all' WHERE scope = 'all' AND mode = 'chat'",
      )
      await conn.execute(
        "ALTER TABLE active_warns ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
      )
      await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_active_warns_user ON active_warns (user_id)",
      )
      await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_active_warns_user_mode "
        "ON active_warns (user_id, mode)",
      )
      # Реестр авто-банов по предупреждениям: помечает, что блокировка данного
      # охвата (chat/all/full) выдана ИМЕННО за достижение порога варнов. Нужен,
      # чтобы при истечении срочных варнов снять ровно «варн-бан», а не задеть
      # ручную блокировку, выданную администратором по другой причине.
      await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS warn_auto_bans (
          user_id     BIGINT      NOT NULL,
          mode        TEXT        NOT NULL,
          chat_id     BIGINT      NOT NULL DEFAULT 0,
          created_at  TIMESTAMP   DEFAULT NOW(),
          PRIMARY KEY (user_id, mode, chat_id)
        )
        """,
      )
    _warn_schema_ready = True
    WarnDebug.log("SCHEMA", "active_warns ready")
  except DbUnavailableError as e:
    now = time.time()
    if now - _warn_schema_fail_last > 60:
      WarnDebug.log("SCHEMA", "ensure skipped", err=str(e))
      _warn_schema_fail_last = now
  except Exception as e:
    WarnDebug.error("SCHEMA", "ensure", e)


async def _count_warns(user_id: int) -> int:
  """Всего активных предупреждений у пользователя (сумма по всем режимам)."""
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return 0
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        "SELECT COUNT(*) AS c FROM active_warns WHERE user_id = $1", user_id,
      )
    return int(row["c"]) if row else 0
  except Exception as e:
    WarnDebug.log("DB", "count skip", err=str(e), user=user_id)
    return 0


def _typed_count_query(mode: Mode, chat_id: int) -> Tuple[str, Tuple[Any, ...]]:
  """SQL + параметры подсчёта предупреждений ОДНОГО режима.

  • chat - копилка отдельной группы (user_id + chat_id);
  • all  - единая копилка «во всех группах» (по всему проекту);
  • full - единая копилка «во всём проекте».

  Это делает варн / варналл / варнфулл независимыми видами предупреждений.
  """
  if mode == "chat":
    return (
      "SELECT COUNT(*) AS c FROM active_warns "
      "WHERE user_id = $1 AND mode = 'chat' AND chat_id = $2",
      (chat_id,),
    )
  if mode == "full":
    return (
      "SELECT COUNT(*) AS c FROM active_warns "
      "WHERE user_id = $1 AND mode = 'full'",
      (),
    )
  # all
  return (
    "SELECT COUNT(*) AS c FROM active_warns "
    "WHERE user_id = $1 AND mode = 'all'",
    (),
  )


async def _count_warns_typed(user_id: int, mode: Mode, chat_id: int = 0) -> int:
  """Счётчик предупреждений конкретного вида (chat/all/full).

  Для chat учитывается КОНКРЕТНАЯ группа (chat_id); для all/full - весь проект.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return 0
  sql, extra = _typed_count_query(mode, chat_id)
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(sql, user_id, *extra)
    return int(row["c"]) if row else 0
  except Exception as e:
    WarnDebug.log("DB", "typed count skip", err=str(e), user=user_id, mode=mode)
    return 0


async def _warn_type_expiry_profile(
  user_id: int, mode: Mode, chat_id: int = 0,
) -> Tuple[bool, bool]:
  """Профиль срочности предупреждений одного вида: (есть_срочные, есть_постоянные).

  «Срочные» - с заполненным expires_at; «постоянные» - без срока. Используется,
  чтобы понять, снимется ли авто-бан сам (по мере истечения) или он постоянный.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return False, False
  if mode == "chat":
    where_sql = "user_id = $1 AND mode = 'chat' AND chat_id = $2"
    params: Tuple[Any, ...] = (user_id, chat_id)
  elif mode == "full":
    where_sql = "user_id = $1 AND mode = 'full'"
    params = (user_id,)
  else:
    where_sql = "user_id = $1 AND mode = 'all'"
    params = (user_id,)
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        f"""
        SELECT
          COUNT(*) FILTER (WHERE expires_at IS NOT NULL) AS timed,
          COUNT(*) FILTER (WHERE expires_at IS NULL)     AS permanent
        FROM active_warns WHERE {where_sql}
        """,
        *params,
      )
    if not row:
      return False, False
    return int(row["timed"]) > 0, int(row["permanent"]) > 0
  except Exception as e:
    WarnDebug.log("DB", "expiry profile skip", err=str(e), user=user_id, mode=mode)
    return False, False


async def warn_counts_by_type(user_id: int) -> Dict[str, int]:
  """Сводка «копилок» предупреждений по видам для отчётов.

  Возвращает: {'chat_max': макс. по одной группе, 'all': N, 'full': N}.
  Для обычных варнов берём максимум по группам - это ближайшая к авто-бану
  величина (порог считается отдельно для каждой группы).
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return {"chat_max": 0, "all": 0, "full": 0}
  try:
    async with _db_acquire() as conn:
      chat_row = await conn.fetchrow(
        """
        SELECT COALESCE(MAX(c), 0) AS m FROM (
          SELECT COUNT(*) AS c FROM active_warns
          WHERE user_id = $1 AND mode = 'chat'
          GROUP BY chat_id
        ) t
        """,
        user_id,
      )
      mode_rows = await conn.fetch(
        """
        SELECT mode, COUNT(*) AS c FROM active_warns
        WHERE user_id = $1 AND mode IN ('all', 'full')
        GROUP BY mode
        """,
        user_id,
      )
    counts = {"chat_max": int(chat_row["m"]) if chat_row else 0, "all": 0, "full": 0}
    for r in mode_rows:
      counts[str(r["mode"])] = int(r["c"])
    return counts
  except Exception as e:
    WarnDebug.log("DB", "counts by type skip", err=str(e), user=user_id)
    return {"chat_max": 0, "all": 0, "full": 0}


async def chat_warn_counts_by_group(user_id: int) -> List[Tuple[int, int]]:
  """Обычные (chat) предупреждения по КАЖДОЙ официальной группе отдельно.

  Возвращает список (chat_id, count) с count > 0, по убыванию счётчика. Нужно,
  чтобы в обзоре «варны @user» показать строку на каждую группу, где у участника
  есть обычные варны, и подсказать, в какой именно группе наступит блокировка.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return []
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT chat_id, COUNT(*) AS c FROM active_warns
        WHERE user_id = $1 AND mode = 'chat'
        GROUP BY chat_id
        ORDER BY c DESC, chat_id
        """,
        user_id,
      )
    return [(int(r["chat_id"] or 0), int(r["c"])) for r in rows if int(r["c"]) > 0]
  except Exception as e:
    WarnDebug.log("DB", "chat warns by group skip", err=str(e), user=user_id)
    return []


async def _add_warn(
  user_id: int,
  chat_id: int,
  admin_user_id: int,
  admin_name: str,
  admin_role: Optional[str],
  reason: str,
  proof_media_id: Optional[str],
  *,
  expires_at: Optional[datetime] = None,
  scope: Scope = "chat",
  mode: Mode = "chat",
) -> Tuple[int, int]:
  """Добавляет предупреждение. Возвращает (счётчик ЭТОГО вида, id записи); (0, 0) при ошибке.

  Счётчик считается отдельно по виду (chat/all/full), чтобы варн, варналл и
  варнфулл были независимыми предупреждениями со своими порогами.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return 0, 0
  count_sql, count_extra = _typed_count_query(mode, chat_id)
  try:
    async with _db_acquire() as conn:
      async with conn.transaction():
        row = await conn.fetchrow(
          """
          INSERT INTO active_warns (
            user_id, chat_id, admin_user_id, admin_name, admin_role,
            reason, proof_media_id, expires_at, scope, mode
          )
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
          RETURNING id
          """,
          user_id, chat_id, admin_user_id, admin_name, admin_role,
          reason, proof_media_id, expires_at, scope, mode,
        )
        count_row = await conn.fetchrow(count_sql, user_id, *count_extra)
    warn_id = int(row["id"]) if row else 0
    new_count = int(count_row["c"]) if count_row else 0
    WarnDebug.log(
      "DB", "warn added", user=user_id, mode=mode, count=new_count, warn_id=warn_id,
    )
    return new_count, warn_id
  except DbUnavailableError as e:
    WarnDebug.log("DB", "add skipped", err=str(e), user=user_id)
    return 0, 0
  except Exception as e:
    WarnDebug.error("DB", "add", e, user=user_id)
    return 0, 0


async def _remove_warn_by_id(warn_id: int) -> bool:
  """Удаляет предупреждение по id. True - запись была удалена."""
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return False
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        "DELETE FROM active_warns WHERE id = $1 RETURNING id",
        warn_id,
      )
    if row:
      try:
        from bot.admins import punish_timers
        punish_timers.cancel_warn(warn_id)
      except Exception:
        pass
    return bool(row)
  except Exception as e:
    WarnDebug.log("DB", "remove by id skip", err=str(e), warn_id=warn_id)
    return False


async def _remove_last_warn(user_id: int) -> Tuple[bool, Optional[int]]:
  """Удаляет последнее предупреждение. Возвращает (удалено, id записи)."""
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return False, None
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        """
        DELETE FROM active_warns
        WHERE id = (
          SELECT id FROM active_warns WHERE user_id = $1
          ORDER BY created_at DESC, id DESC LIMIT 1
        )
        RETURNING id
        """,
        user_id,
      )
    if row:
      warn_id = int(row["id"])
      try:
        from bot.admins import punish_timers
        punish_timers.cancel_warn(warn_id)
      except Exception:
        pass
      return True, warn_id
    return False, None
  except Exception as e:
    WarnDebug.log("DB", "remove skip", err=str(e), user=user_id)
    return False, None


async def _remove_last_warn_typed(
  user_id: int, mode: Mode, chat_id: int = 0,
) -> Tuple[bool, Optional[int]]:
  """Удаляет ПОСЛЕДНЕЕ предупреждение указанного вида. (удалено, id записи).

  • chat - в конкретной группе (chat_id);
  • all / full - последнее предупреждение соответствующей копилки проекта.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return False, None
  if mode == "chat":
    where_sql = "user_id = $1 AND mode = 'chat' AND chat_id = $2"
    params: Tuple[Any, ...] = (user_id, chat_id)
  elif mode == "full":
    where_sql = "user_id = $1 AND mode = 'full'"
    params = (user_id,)
  else:
    where_sql = "user_id = $1 AND mode = 'all'"
    params = (user_id,)
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        f"""
        DELETE FROM active_warns
        WHERE id = (
          SELECT id FROM active_warns WHERE {where_sql}
          ORDER BY created_at DESC, id DESC LIMIT 1
        )
        RETURNING id
        """,
        *params,
      )
    if row:
      warn_id = int(row["id"])
      try:
        from bot.admins import punish_timers
        punish_timers.cancel_warn(warn_id)
      except Exception:
        pass
      return True, warn_id
    return False, None
  except Exception as e:
    WarnDebug.log("DB", "remove typed skip", err=str(e), user=user_id, mode=mode)
    return False, None


async def _list_warns_detailed(user_id: int) -> List[Dict[str, Any]]:
  """Список активных предупреждений с админом/причиной/сроком/видом (новые сверху).

  Включает `mode` и `chat_id`, чтобы можно было сгруппировать предупреждения по
  видам (варн / варналл / варнфулл) и показать группу для обычных варнов.
  Запросы выстроены от самой полной схемы к самой простой - на случай старой БД.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return []
  queries = (
    """
    SELECT admin_user_id, admin_name, admin_role, reason, expires_at, created_at, mode, chat_id
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
    """
    SELECT admin_user_id, admin_name, admin_role, reason, expires_at, created_at, scope, chat_id
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
    """
    SELECT admin_name, admin_role, reason, expires_at, created_at, mode, chat_id
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
    """
    SELECT admin_name, admin_role, reason, expires_at, created_at, scope, chat_id
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
    """
    SELECT admin_name, admin_role, reason, expires_at, created_at
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
    """
    SELECT admin_name, admin_role, reason, expires_at
    FROM active_warns
    WHERE user_id = $1
    ORDER BY id DESC
    """,
  )
  for sql in queries:
    try:
      async with _db_acquire() as conn:
        rows = await conn.fetch(sql, user_id)
      return [dict(r) for r in rows]
    except Exception as e:
      WarnDebug.log("DB", "list detailed retry", err=str(e), user=user_id)
  return []


async def list_active_warns_for_user(user_id: int) -> List[Dict[str, Any]]:
  """Публичная обёртка для сводки «наказания»: активные варны с деталями."""
  return await _list_warns_detailed(user_id)


async def count_active_warns_for_user(user_id: int) -> int:
  """Публичная обёртка для сводки «наказания»: число активных варнов."""
  return await _count_warns(user_id)


async def _clear_warns(user_id: int) -> None:
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        "SELECT id FROM active_warns WHERE user_id = $1 AND expires_at IS NOT NULL",
        user_id,
      )
      await conn.execute("DELETE FROM active_warns WHERE user_id = $1", user_id)
    try:
      from bot.admins import punish_timers
      for row in rows:
        punish_timers.cancel_warn(int(row["id"]))
      punish_timers.cancel_warns_for_user(user_id)
    except Exception:
      pass
    await _unmark_all_warn_bans(user_id)
    WarnDebug.log("DB", "warns cleared", user=user_id)
  except Exception as e:
    WarnDebug.log("DB", "clear skip", err=str(e), user=user_id)


async def _clear_warns_scoped(user_id: int, mode: Mode, chat_id: int = 0) -> int:
  """Снимает предупреждения ТОЛЬКО одного вида (chat/all/full).

  • chat - только в указанной группе (chat_id);
  • all  - все предупреждения «во всех группах»;
  • full - все предупреждения «во всём проекте».

  Возвращает число удалённых записей. Остальные виды копилок не трогаются -
  это и обеспечивает независимость варн / варналл / варнфулл.
  """
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return 0
  if mode == "chat":
    where_sql = "user_id = $1 AND mode = 'chat' AND chat_id = $2"
    params: Tuple[Any, ...] = (user_id, chat_id)
  elif mode == "full":
    where_sql = "user_id = $1 AND mode = 'full'"
    params = (user_id,)
  else:
    where_sql = "user_id = $1 AND mode = 'all'"
    params = (user_id,)
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        f"DELETE FROM active_warns WHERE {where_sql} RETURNING id", *params,
      )
    removed_ids = [int(r["id"]) for r in rows]
    if removed_ids:
      try:
        from bot.admins import punish_timers
        for wid in removed_ids:
          punish_timers.cancel_warn(wid)
      except Exception:
        pass
    # Эта копилка обнулена администратором - пометка авто-бана больше не нужна.
    await _unmark_warn_ban(user_id, mode, chat_id)
    WarnDebug.log(
      "DB", "warns cleared scoped",
      user=user_id, mode=mode, chat_id=chat_id, removed=len(removed_ids),
    )
    return len(removed_ids)
  except Exception as e:
    WarnDebug.log("DB", "clear scoped skip", err=str(e), user=user_id, mode=mode)
    return 0


# ---------------------------------------------------------------------------
# Реестр авто-банов по варнам + условное снятие блокировки
# ---------------------------------------------------------------------------

def _warn_ban_key_chat(mode: Mode, chat_id: int) -> int:
  """chat_id ключа реестра: для chat - конкретная группа; для all/full - 0."""
  return chat_id if mode == "chat" else 0


async def _mark_warn_ban(user_id: int, mode: Mode, chat_id: int = 0) -> None:
  """Помечает, что блокировка выдана за достижение порога варнов этого вида."""
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return
  key_chat = _warn_ban_key_chat(mode, chat_id)
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        """
        INSERT INTO warn_auto_bans (user_id, mode, chat_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, mode, chat_id) DO UPDATE SET created_at = NOW()
        """,
        user_id, mode, key_chat,
      )
    WarnDebug.log("AUTOBAN", "marked", user=user_id, mode=mode, chat_id=key_chat)
  except Exception as e:
    WarnDebug.log("DB", "mark warn-ban skip", err=str(e), user=user_id, mode=mode)


async def _has_warn_ban(user_id: int, mode: Mode, chat_id: int = 0) -> bool:
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return False
  key_chat = _warn_ban_key_chat(mode, chat_id)
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        "SELECT 1 FROM warn_auto_bans WHERE user_id = $1 AND mode = $2 AND chat_id = $3",
        user_id, mode, key_chat,
      )
    return bool(row)
  except Exception as e:
    WarnDebug.log("DB", "has warn-ban skip", err=str(e), user=user_id, mode=mode)
    return False


async def _unmark_warn_ban(user_id: int, mode: Mode, chat_id: int = 0) -> None:
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return
  key_chat = _warn_ban_key_chat(mode, chat_id)
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        "DELETE FROM warn_auto_bans WHERE user_id = $1 AND mode = $2 AND chat_id = $3",
        user_id, mode, key_chat,
      )
    WarnDebug.log("AUTOBAN", "unmarked", user=user_id, mode=mode, chat_id=key_chat)
  except Exception as e:
    WarnDebug.log("DB", "unmark warn-ban skip", err=str(e), user=user_id, mode=mode)


async def _unmark_all_warn_bans(user_id: int) -> None:
  """Снимает все пометки авто-банов пользователя (например, при ручном бане)."""
  await _ensure_warn_schema()
  if not _warn_schema_ready:
    return
  try:
    async with _db_acquire() as conn:
      await conn.execute("DELETE FROM warn_auto_bans WHERE user_id = $1", user_id)
  except Exception as e:
    WarnDebug.log("DB", "unmark all warn-ban skip", err=str(e), user=user_id)


async def clear_warn_ban_marks_for_manual_ban(user_id: int) -> None:
  """Публичный хук для ban.py: при РУЧНОЙ блокировке снимаем пометки авто-бана,
  чтобы истечение варнов не сняло блокировку, которую администратор выдал сам."""
  await _unmark_all_warn_bans(user_id)


async def _lift_warn_ban_scope(
  user_id: int,
  mode: Mode,
  chat_id: int = 0,
) -> Tuple[bool, List[int]]:
  """Снимает блокировку, ранее выданную за варны данного вида.

  • chat - разблокировка в конкретной группе (chat_id);
  • all  - во всех официальных группах;
  • full - во всех группах + снятие полной блокировки проекта (WebApp + banusers).

  Идемпотентно. Возвращает (снята_ли_полная_блокировка_проекта, список_групп).
  """
  lifted_groups: List[int] = []
  full_lifted = False
  try:
    if mode == "chat":
      if chat_id:
        from bot.admins.ban import _unban_in_chat, _delete_active_ban
        if await _unban_in_chat(chat_id, user_id):
          lifted_groups.append(chat_id)
        await _delete_active_ban(user_id, chat_id)
    else:
      from bot.admins.ban import _lift_ban_everywhere, _delete_all_active_bans
      _was, lifted_groups = await _lift_ban_everywhere(user_id)
      await _delete_all_active_bans(user_id)
      if mode == "full":
        from bot.admins.ban import _lift_full_project_block
        full_lifted = await _lift_full_project_block(user_id)
  except Exception as e:
    WarnDebug.log("AUTOBAN", "lift scope skip", err=str(e), user=user_id, mode=mode)

  try:
    from bot.admins import punish_timers
    punish_timers.cancel_ban(user_id)
  except Exception:
    pass
  return full_lifted, lifted_groups


async def _log_warn_action(
  action_type: str,
  target_user_id: int,
  target_name: str,
  target_username: Optional[str],
  admin_user_id: int,
  admin_name: str,
  reason: str,
  proof_media_id: Optional[str],
  chat_id: int,
  mode: Mode = "chat",
) -> None:
  """Запись в staff_actions (аудит). action_type: 'warn' / 'unwarn'.

  mode - охват предупреждения ('chat' / 'all' / 'full'): пишется в столбец
  scope, чтобы архив в админ-панели различал Варн/Варналл/Варнфулл и
  Разварн/Разварналл/Разварнфулл.
  """
  try:
    async with _db_acquire() as conn:
      async with conn.transaction():
        await conn.execute(
          """
          INSERT INTO users (user_id, first_name, username)
          VALUES ($1, $2, $3)
          ON CONFLICT (user_id) DO UPDATE
          SET first_name = COALESCE(users.first_name, EXCLUDED.first_name),
              username   = COALESCE(users.username, EXCLUDED.username)
          """,
          target_user_id, target_name, target_username,
        )
        if proof_media_id:
          await conn.execute(
            """
            INSERT INTO staff_actions (
              admin_user_id, admin_name, action_type,
              target_player_id, target_name, reason, proof_media_id, chat_id, scope,
              proof_bot_token
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            admin_user_id, admin_name, action_type,
            target_user_id, target_name, reason, proof_media_id, chat_id, mode,
            _proof_owner_token(proof_media_id),
          )
        else:
          await conn.execute(
            """
            INSERT INTO staff_actions (
              admin_user_id, admin_name, action_type,
              target_player_id, target_name, reason, chat_id, scope
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            admin_user_id, admin_name, action_type,
            target_user_id, target_name, reason, chat_id, mode,
          )
    WarnDebug.log("DB", "action logged", type=action_type, target=target_user_id)
  except DbUnavailableError as e:
    WarnDebug.log("DB", "log skipped", err=str(e), target=target_user_id)
  except Exception as e:
    WarnDebug.error("DB", "log action", e, target=target_user_id)


# ---------------------------------------------------------------------------
# Оформление сообщений
# ---------------------------------------------------------------------------

def _warn_progress_bar(count: int, total: int = WARN_THRESHOLD) -> str:
  """
  Визуальная шкала предупреждений с нарастанием «тревожности» по позициям:
    • 1/3 → 🟡 ⚪️ ⚪️
    • 2/3 → 🟡 🟠 ⚪️
    • 3/3 → 🔴 🔴 🔴   (лимит - вся шкала «горит»)
  Заполненные ячейки окрашиваются по позиции (🟡 → 🟠 → 🔴); при достижении
  лимита вся шкала становится красной - психологически показывает «край».
  """
  count = max(0, min(count, total))
  palette = (WarnText.BAR_LOW, WarnText.BAR_MID, WarnText.BAR_HIGH)
  cells: List[str] = []
  for i in range(total):
    if count >= total:
      cells.append(WarnText.BAR_HIGH)            # лимит - всё красное
    elif i < count:
      cells.append(palette[i] if i < len(palette) else WarnText.BAR_HIGH)
    else:
      cells.append(WarnText.BAR_EMPTY)
  return " ".join(cells)


def _warn_count_line(count: int) -> str:
  bar = _warn_progress_bar(count)
  shown = min(count, WARN_THRESHOLD)
  return WarnText.COUNT_LINE.format(count=shown, total=WARN_THRESHOLD, bar=bar)


def _warn_reason_suffix(reason: Optional[str]) -> str:
  """Короткая строка причины с переносом (пустая, если причины нет).

  Даёт «📋 Причина : …» отдельной строкой и НЕ оставляет пустых строк, когда
  причина не указана - сообщение остаётся коротким.
  """
  line = _format_mute_reason_block(reason, label="Причина")
  return f"\n{line}" if line else ""


def _warn_type_label(mode: Mode) -> str:
  """Человеческое название вида предупреждения для всех сообщений системы."""
  if mode == "full":
    return WarnText.WARN_TYPE_LABEL_FULL
  if mode == "all":
    return WarnText.WARN_TYPE_LABEL_ALL
  return WarnText.WARN_TYPE_LABEL_CHAT


def _warn_type_line(mode: Mode) -> str:
  """Готовая строка «Тип предупреждения: …» для вставки в любое сообщение."""
  return WarnText.TYPE_LINE.format(label=_warn_type_label(mode))


def _warn_scope_block(mode: Mode) -> str:
  """Строка «Охват: …» по типу варна (chat / all / full)."""
  if mode == "full":
    return WarnText.SCOPE_FULL
  if mode == "all":
    return WarnText.SCOPE_ALL
  return WarnText.SCOPE_CHAT


def _warn_consequence(mode: Mode) -> str:
  """Готовый блок «При N/N - <последствие>» для конкретного типа варна."""
  if mode == "full":
    effect = WarnText.CONSEQUENCE_EFFECT_FULL
  elif mode == "all":
    effect = WarnText.CONSEQUENCE_EFFECT_ALL
  else:
    effect = WarnText.CONSEQUENCE_EFFECT_CHAT
  return WarnText.CONSEQUENCE.format(th=WARN_THRESHOLD, effect=effect)


def _warn_ban_phrase(mode: Mode) -> str:
  """Короткая фраза о последствии лимита для ЛС-уведомления нарушителю."""
  if mode == "full":
    return WarnText.BAN_PHRASE_FULL
  if mode == "all":
    return WarnText.BAN_PHRASE_ALL
  return WarnText.BAN_PHRASE_CHAT


def _warn_typed_line(label: str, count: int) -> str:
  """Строка-«копилка» одного вида предупреждений: «Ярлык: N/3  ▮▮▯»."""
  bar = _warn_progress_bar(count)
  shown = min(count, WARN_THRESHOLD)
  return WarnText.TYPED_LINE.format(
    label=label, count=shown, total=WARN_THRESHOLD, bar=bar,
  )


def _warn_standing_block(
  chat_count: int,
  all_count: int,
  full_count: int,
  *,
  chat_label: str,
  show_zero: bool = False,
) -> str:
  """Блок «копилок» по видам (обычный / варналл / варнфулл).

  show_zero=True - показываем все виды (удобно администратору); иначе только
  ненулевые. Если активных предупреждений нет вовсе - отдаём общий счётчик 0/3.
  """
  lines: List[str] = []
  if show_zero or chat_count > 0:
    lines.append(_warn_typed_line(chat_label, chat_count))
  if show_zero or all_count > 0:
    lines.append(_warn_typed_line(WarnText.TYPED_LABEL_ALL, all_count))
  if show_zero or full_count > 0:
    lines.append(_warn_typed_line(WarnText.TYPED_LABEL_FULL, full_count))
  if not lines:
    return _warn_count_line(0)
  return "\n".join(lines)


def _warn_term_line(parsed: ParsedWarn) -> str:
  if parsed.until is None or parsed.time_delta is None:
    return WarnText.TERM_PERMANENT
  duration = _format_duration_short(parsed.time_delta)
  return WarnText.TERM_TIMED.format(
    duration=duration,
    until=_format_until(parsed.until),
  )


def _warn_pending_term_line(parsed: ParsedWarn) -> str:
  """Срок в ожидании пруфа - без точной даты окончания."""
  if parsed.until is None or parsed.time_delta is None:
    return WarnText.TERM_PERMANENT
  duration = _format_duration_short(parsed.time_delta)
  return (
    f"<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : {duration}</b>\n"
    "<blockquote><i>Точное время окончания будет указано после подтверждения фото.</i></blockquote>"
  )


def _refresh_parsed_warn_expiry(parsed: ParsedWarn) -> None:
  if parsed.time_delta is not None:
    parsed.time_delta = _normalize_time_delta(parsed.time_delta)
    parsed.until = _rebase_expiry_at_now(parsed.time_delta)


async def _send_warn_help(message: Message) -> None:
  await message.reply(
    WarnText.HELP.format(timeout=cfg.proof_timeout_minutes(), th=WARN_THRESHOLD),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


# ---------------------------------------------------------------------------
# Разбор команды
# ---------------------------------------------------------------------------

async def parse_warn_command(message: Message) -> ParsedWarn | ParseError:
  text = _get_command_text(message)
  parts = text.split()
  WarnDebug.log("PARSE", "start", text=text, parts=parts, reply=bool(message.reply_to_message))

  reply_msg = _get_reply_target_message(message)
  body = parts[1:] if len(parts) > 1 else []
  source_chat_id = message.chat.id

  target_id: Optional[int] = None
  target_name: Optional[str] = None
  target_username: Optional[str] = None
  rest: List[str] = body

  if reply_msg and reply_msg.from_user:
    # Явное указание пользователя в команде (например @werkov3) важнее ответа.
    target_id, target_name, target_username, rest, not_found = await _resolve_reply_or_explicit(
      reply_msg.from_user, body, source_chat_id=source_chat_id,
    )
    if not_found:
      if str(not_found).isdigit():
        return ParseError(
          "warn_user_not_found",
          WarnText.NOT_FOUND_ID.format(token=escape(not_found)),
          not_found,
        )
      return ParseError(
        "warn_user_not_found",
        WarnText.NOT_FOUND_EXPLICIT.format(token=escape(not_found)),
        not_found,
      )
  else:
    if not body:
      return ParseError(
        "warn_no_target",
        WarnText.NO_TARGET,
        "no reply and empty body",
      )

    if _body_starts_with_duration(body) or parse_duration(body[0]):
      return ParseError(
        "warn_no_target",
        WarnText.NEED_TARGET,
        f"starts with duration: {' '.join(body[:3])}",
      )

    first = body[0]
    target_id, target_name, target_username = await _lookup_target_by_token(
      first, source_chat_id=source_chat_id,
    )
    if not target_id:
      if first.startswith("@") or _looks_like_username_token(first):
        username = first.lstrip("@")
        return ParseError(
          "warn_user_not_found",
          WarnText.NOT_FOUND_USERNAME.format(username=escape(username)),
          first,
        )
      if first.isdigit():
        return ParseError(
          "warn_user_not_found",
          WarnText.NOT_FOUND_ID.format(token=escape(first)),
          first,
        )
      return ParseError(
        "warn_user_not_found",
        WarnText.NOT_FOUND_NAME.format(token=escape(first)),
        first,
      )
    rest = body[1:]

  dur_text, reason_from_extract, _ = _extract_duration_and_reason(rest, 0)
  until: Optional[datetime] = None
  duration_text: Optional[str] = None
  time_delta: Optional[timedelta] = None
  duration_minutes: Optional[int] = None

  if dur_text:
    parsed_dur = parse_duration(dur_text)
    if not parsed_dur:
      return ParseError(
        "warn_bad_duration",
        WarnText.BAD_DURATION.format(duration=escape(dur_text)),
        dur_text,
      )
    time_delta, duration_minutes = parsed_dur
    time_delta = _normalize_time_delta(time_delta)
    duration_text = dur_text
    until = _rebase_expiry_at_now(time_delta)
    reason = reason_from_extract
  else:
    reason = " ".join(rest).strip() or "Не указана"

  mode = _warn_command_mode(text)
  scope = mode_to_scope(mode)
  return ParsedWarn(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    reason=reason,
    scope=scope,
    mode=mode,
    until=until,
    duration_text=duration_text,
    time_delta=time_delta,
    duration_minutes=duration_minutes,
  )


# ---------------------------------------------------------------------------
# Выдача предупреждения + авто-бан
# ---------------------------------------------------------------------------

async def _notify_warn_violator(
  player: PlayerRef,
  staff: StaffRef,
  count: int,
  reason: str,
  parsed: ParsedWarn,
) -> None:
  reason_line = _format_mute_reason_block(reason, label="Причина")
  reason_suffix = f"\n{reason_line}" if reason_line else ""
  left = WARN_THRESHOLD - count
  ban_phrase = _warn_ban_phrase(parsed.mode)
  if left > 0:
    tail = WarnText.VIOLATOR_TAIL_LEFT.format(left=left, ban_phrase=ban_phrase)
  else:
    tail = WarnText.VIOLATOR_TAIL_LAST.format(ban_phrase=ban_phrase)
  text = WarnText.VIOLATOR.format(
    greeting=player.greeting,
    staff_line=staff.line,
    actor=staff.actor,
    type_line=_warn_type_line(parsed.mode),
    term_line=_warn_term_line(parsed),
    count_line=_warn_count_line(count),
    reason_suffix=reason_suffix,
    tail=tail,
  )
  try:
    await _bot().send_message(
      player.user_id, text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("NOTIFY", "violator skip", user_id=player.user_id, err=str(e))


async def _send_warn_success(
  message: Message,
  player: PlayerRef,
  staff: StaffRef,
  count: int,
  parsed: ParsedWarn,
  chat_id: int,
) -> None:
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  await message.reply(
    WarnText.SUCCESS.format(
      staff_line=staff.line,
      player_line=player.line,
      chat_line=chat_line,
      type_line=_warn_type_line(parsed.mode),
      scope_block=_warn_scope_block(parsed.mode),
      term_line=_warn_term_line(parsed),
      count_line=_warn_count_line(count),
      reason_suffix=_warn_reason_suffix(parsed.reason),
      consequence=_warn_consequence(parsed.mode),
    )
    + _debug_hint("warn_ok"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_warn_revoke_keyboard(message.from_user.id, player.user_id, parsed.mode),
  )


async def _format_groups_block(chat_ids: List[int]) -> str:
  uniq: List[int] = []
  for cid in chat_ids:
    if cid not in uniq:
      uniq.append(cid)
  lines: List[str] = []
  for cid in uniq:
    disp = await _get_chat_display(cid)
    label = escape(disp.title)
    if disp.link_url:
      lines.append(f"   <b>•</b> <a href='{escape(disp.link_url)}'>{label}</a>")
    else:
      lines.append(f"   <b>•</b> <b>{label}</b>")
  return "\n".join(lines)


def _warn_ban_scope_value(mode: Mode) -> str:
  if mode == "full":
    return WarnText.BAN_SCOPE_FULL
  if mode == "all":
    return WarnText.BAN_SCOPE_ALL
  return WarnText.BAN_SCOPE_CHAT


async def _send_warn_ban_result(
  message: Message,
  player: PlayerRef,
  staff: StaffRef,
  reason: str,
  banned_ids: List[int],
  ban_ok: bool,
  mode: Mode,
  closing: str = "",
) -> None:
  if ban_ok and banned_ids:
    # Для охвата «эта группа» список групп не дублируем (он и так один).
    if mode == "chat":
      groups_part = ""
    else:
      groups_block = await _format_groups_block(banned_ids)
      groups_part = f"\n{groups_block}" if groups_block else ""
    body = WarnText.BAN_RESULT_OK.format(
      th=WARN_THRESHOLD,
      staff_line=staff.line,
      player_line=player.line,
      type_line=_warn_type_line(mode),
      scope_value=_warn_ban_scope_value(mode),
      groups_part=groups_part,
      reason_suffix=_warn_reason_suffix(reason),
      closing=closing or WarnText.BAN_CLOSING_PERMANENT,
    )
  else:
    body = WarnText.BAN_RESULT_FAIL.format(
      th=WARN_THRESHOLD,
      staff_line=staff.line,
      player_line=player.line,
      type_line=_warn_type_line(mode),
    )
  await message.reply(
    body + _debug_hint("warn_threshold"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def _broadcast_warn_groups(
  source_chat_id: int,
  parsed: ParsedWarn,
  staff: StaffRef,
  player: PlayerRef,
  count: int,
) -> None:
  """Рассылка объявления о варне во все официальные группы (варналл)."""
  if parsed.scope != "all":
    return

  reason_line = _format_mute_reason_block(parsed.reason, label="Причина")
  reason_suffix = f"\n{reason_line}" if reason_line else ""
  term_line = _warn_term_line(parsed)
  count_line = _warn_count_line(count)
  staff_line = f"{staff.line}\n"
  group_title = WarnText.GROUP_TITLE
  group_footer = WarnText.GROUP_FOOTER.format(
    actor=staff.actor,
    player_short=player.short,
    count=count,
    total=WARN_THRESHOLD,
  )

  notify_chats = set(cfg.STAFF_CHAT_IDS)
  notify_chats.discard(source_chat_id)

  for group_chat_id in notify_chats:
    disp = await _get_chat_display(group_chat_id)
    chat_line = _format_chat_line(disp)
    group_text = WarnText.GROUP.format(
      group_title=group_title,
      player_line=player.line,
      staff_line=staff_line,
      chat_line=chat_line,
      type_line=_warn_type_line(parsed.mode),
      scope_block=_warn_scope_block(parsed.mode),
      term_line=term_line,
      count_line=count_line,
      reason_suffix=reason_suffix,
      group_footer=group_footer,
      consequence=_warn_consequence(parsed.mode),
    )
    try:
      await _bot().send_message(
        group_chat_id,
        group_text,
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      WarnDebug.log("NOTIFY", "warn group skip", chat_id=group_chat_id, err=str(e))


async def expire_timed_warn(warn_id: int, payload: Dict[str, Any]) -> None:
  """Снимает одно временное предупреждение по истечении срока (из punish_timers)."""
  if not await _remove_warn_by_id(warn_id):
    return

  user_id = int(payload.get("user_id") or 0)
  if not user_id:
    return

  target_name = payload.get("target_name") or str(user_id)
  target_username = payload.get("target_username")
  source_chat_id = int(payload.get("source_chat_id") or 0)
  scope = payload.get("scope") or "chat"
  # Режим истёкшего предупреждения: chat / all / full. Для старых таймеров
  # (без mode) аккуратно выводим из scope.
  mode: Mode = payload.get("mode") or ("all" if scope == "all" else "chat")

  # Показываем счётчик ИМЕННО этого вида предупреждений (после снятия одного).
  count = await _count_warns_typed(user_id, mode, source_chat_id)
  player = PlayerRef(user_id, target_name, target_username)

  # Условное снятие блокировки: если варнов этого вида стало меньше порога и
  # блокировка была выдана ИМЕННО за варны (есть пометка), снимаем её.
  # Постоянные варны при этом сохраняются - они просто перестают «держать» бан.
  unblocked = False
  full_unblocked = False
  if count < WARN_THRESHOLD and await _has_warn_ban(user_id, mode, source_chat_id):
    full_unblocked, lifted_groups = await _lift_warn_ban_scope(
      user_id, mode, source_chat_id,
    )
    await _unmark_warn_ban(user_id, mode, source_chat_id)
    unblocked = True
    WarnDebug.log(
      "AUTOBAN", "lifted on expiry",
      user=user_id, mode=mode, full=full_unblocked, groups=lifted_groups,
    )

  dm_note = ""
  if unblocked:
    dm_note = (
      WarnText.EXPIRED_DM_UNBLOCKED_FULL if mode == "full"
      else WarnText.EXPIRED_DM_UNBLOCKED
    )

  try:
    await _bot().send_message(
      user_id,
      WarnText.EXPIRED_DM.format(
        greeting=player.greeting,
        type_line=_warn_type_line(mode),
        count_line=_warn_count_line(count),
      ) + dm_note,
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("NOTIFY", "warn expire dm skip", user_id=user_id, err=str(e))

  # Куда сообщить о снятии по сроку:
  #   • all / full - во ВСЕ официальные группы, ВКЛЮЧАЯ ту, где выдавался варн;
  #   • chat       - только в исходную группу.
  # Исходная группа уведомляется всегда (раньше она ошибочно исключалась для
  # охвата «во всех группах», из-за чего там ничего не писалось).
  notify_chats: List[int] = []
  if scope == "all":
    notify_chats = [cid for cid in cfg.STAFF_CHAT_IDS if _is_staff_chat(cid)]
  if source_chat_id and _is_staff_chat(source_chat_id) and source_chat_id not in notify_chats:
    notify_chats.append(source_chat_id)

  for group_chat_id in notify_chats:
    chat_line = await _format_chats_line(notify_chats, current_chat_id=group_chat_id)
    text = WarnText.EXPIRED_GROUP.format(
      player_line=player.line,
      chat_line=chat_line,
      type_line=_warn_type_line(mode),
      count_line=_warn_count_line(count),
      player_short=player.short,
      count=count,
      total=WARN_THRESHOLD,
    )
    if unblocked:
      text += WarnText.EXPIRED_GROUP_UNBLOCKED.format(total=WARN_THRESHOLD)
    try:
      await _bot().send_message(
        group_chat_id,
        text,
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      WarnDebug.log("NOTIFY", "warn expire group skip", chat_id=group_chat_id, err=str(e))

  WarnDebug.log("AUTO", "timed warn expired", warn_id=warn_id, user=user_id, count=count)


async def _trigger_auto_ban(
  message: Message,
  parsed: ParsedWarn,
  proof_media_id: Optional[str],
  chat_id: int,
  admin_name: str,
  admin_role: Optional[str],
  staff: StaffRef,
) -> None:
  """Достигнут лимит - бан соответствующего охвата, привязанный к варнам.

  Предупреждения НЕ обнуляются: блокировка снимется автоматически, когда из-за
  истечения срочных варнов их станет меньше порога (см. expire_timed_warn).
  """
  from bot.admins.ban import apply_ban_for_warns  # ленивый импорт (без циклов)

  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  ban_reason = (
    f"<b>Автоматический бан: {WARN_THRESHOLD}/{WARN_THRESHOLD} предупреждений </b>"
    f"<b>(последняя причина: {parsed.reason})</b>"
  )
  ban_ok, _banned_count, banned_ids = await apply_ban_for_warns(
    target_id=parsed.target_id,
    target_name=parsed.target_name,
    target_username=parsed.target_username,
    admin_id=message.from_user.id,
    admin_name=admin_name,
    admin_role=admin_role,
    admin_username=message.from_user.username,
    proof_media_id=proof_media_id,
    source_chat_id=chat_id,
    reason=ban_reason,
    mode=parsed.mode,
  )
  # ВАЖНО: предупреждения НЕ обнуляем - блокировка «привязана» к ним.
  # Срочные варны со временем истекут и сами снимут блокировку (когда их станет
  # меньше порога); постоянные - удержат её до снятия администратором. Это даёт
  # точное поведение: 2 пожизненных + 1 срочный варнфулл → разблокировка после
  # истечения срочного; 2 срочных + 1 пожизненный → разблокировка после
  # истечения срочных, а пожизненный варн остаётся у пользователя.
  closing = WarnText.BAN_CLOSING_PERMANENT
  if ban_ok:
    has_timed, _has_perm = await _warn_type_expiry_profile(
      parsed.target_id, parsed.mode, chat_id,
    )
    # Помечаем блокировку как «варн-бан», чтобы истечение срочных варнов снимало
    # именно её, а не ручную блокировку администратора по другой причине.
    await _mark_warn_ban(parsed.target_id, parsed.mode, chat_id)
    if has_timed:
      closing = WarnText.BAN_CLOSING_TIMED.format(th=WARN_THRESHOLD)
  await _send_warn_ban_result(
    message, player, staff, parsed.reason, banned_ids, ban_ok, parsed.mode, closing,
  )
  WarnDebug.log(
    "FLOW", "auto-ban done",
    target=parsed.target_id, ok=ban_ok, mode=parsed.mode,
    timed=(closing != WarnText.BAN_CLOSING_PERMANENT),
  )


async def _finalize_warn(
  message: Message,
  parsed: ParsedWarn,
  proof_media_id: str,
  chat_id: int,
  admin_name: str,
) -> bool:
  # Наказание выдаётся СТРОГО после подтверждения пруфа: без фото - не применяем.
  if not proof_media_id:
    await message.reply(
      WarnText.PROOF_MISSING + _debug_hint("proof_required"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    WarnDebug.log("PROOF", "finalize blocked - no proof", target=getattr(parsed, "target_id", None))
    return True
  from bot.admins.punish_validate import (
    punishment_invalid_user_html,
    validate_punishment_target_user,
  )
  tg_err = await validate_punishment_target_user(
    parsed.target_id, source_chat_id=chat_id,
  )
  if tg_err:
    await message.reply(
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("warn_invalid_user_finalize"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    WarnDebug.log("TG", "warn finalize blocked - invalid user", target=parsed.target_id)
    return True
  admin_name, admin_role, admin_account = await _resolve_admin_identity(message)
  staff = (
    StaffRef.from_account(admin_account)
    if admin_account else
    await StaffRef.from_message(message)
  )
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)

  _refresh_parsed_warn_expiry(parsed)

  new_count, warn_id = await _add_warn(
    parsed.target_id, chat_id, message.from_user.id, admin_name, admin_role,
    parsed.reason, proof_media_id,
    expires_at=parsed.until,
    scope=parsed.scope,
    mode=parsed.mode,
  )
  if new_count <= 0 or warn_id <= 0:
    await message.reply(
      WarnText.DB_FAILED + _debug_hint("warn_db_failed"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  if parsed.until:
    try:
      from bot.admins import punish_timers
      punish_timers.register_warn(
        warn_id,
        parsed.until,
        user_id=parsed.target_id,
        target_name=parsed.target_name,
        target_username=parsed.target_username,
        source_chat_id=chat_id,
        scope=parsed.scope,
        mode=parsed.mode,
        admin_name=admin_name,
        admin_role=admin_role,
        reason=parsed.reason,
      )
    except Exception as e:
      WarnDebug.log("TIMER", "register warn skip", err=str(e), warn_id=warn_id)

  await _log_warn_action(
    "warn", parsed.target_id, parsed.target_name, parsed.target_username,
    message.from_user.id, admin_name, parsed.reason, proof_media_id, chat_id,
    mode=parsed.mode,
  )

  if new_count >= WARN_THRESHOLD:
    # На лимите бан-флоу сам уведомит нарушителя и остальные группы.
    await _trigger_auto_ban(
      message, parsed, proof_media_id, chat_id, admin_name, admin_role, staff,
    )
  else:
    await _send_warn_success(message, player, staff, new_count, parsed, chat_id)
    await _notify_warn_violator(player, staff, new_count, parsed.reason, parsed)
    await _broadcast_warn_groups(chat_id, parsed, staff, player, new_count)
  return True


# ---------------------------------------------------------------------------
# Ожидание фото (шаг 2)
# ---------------------------------------------------------------------------

def _warn_cancel_callback_data(admin_id: int, target_id: int) -> str:
  return f"warn:cancel:{admin_id}:{target_id}"


def _warn_pending_cancel_keyboard(admin_id: int, target_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=WarnText.BTN_CANCEL,
      callback_data=_warn_cancel_callback_data(admin_id, target_id),
    ),
  ]])


def _warn_revoke_callback_data(admin_id: int, target_id: int, mode: Mode = "chat") -> str:
  return f"warn:revoke:{admin_id}:{target_id}:{mode}"


def _warn_revoke_keyboard(
  admin_id: int, target_id: int, mode: Mode = "chat",
) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=WarnText.BTN_REVOKE,
      callback_data=_warn_revoke_callback_data(admin_id, target_id, mode),
    ),
  ]])


def _suggest_cancel_warn_command(
  target_id: int,
  target_name: str,
  target_username: Optional[str] = None,
) -> str:
  if target_username:
    return f"отменить варн @{target_username.lstrip('@')}"
  if target_name and not str(target_name).isdigit():
    return f"отменить варн {target_name}"
  return f"отменить варн {target_id}"


def _build_pending_warn_text(
  parsed: ParsedWarn,
  chat_line: str,
  next_count: int,
  cancel_hint: str,
) -> str:
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  return WarnText.PENDING.format(
    player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
    chat_line=chat_line,
    type_line=_warn_type_line(parsed.mode),
    scope_block=_warn_scope_block(parsed.mode),
    term_line=_warn_pending_term_line(parsed),
    next_count=next_count,
    th=WARN_THRESHOLD,
    consequence=_warn_consequence(parsed.mode),
    reason_part=reason_part,
    timeout=cfg.proof_timeout_minutes(),
    cancel_hint=escape(cancel_hint),
  )


async def _expire_pending_warn(admin_id: int, data: Dict[str, Any]) -> None:
  from bot.admins.punish_proof import coerce_telegram_user_id, safe_edit_message_text
  admin_id = coerce_telegram_user_id(admin_id)
  if admin_id is None or data.get("expiry_notified"):
    return
  data["expiry_notified"] = True

  parsed: ParsedWarn = data["parsed"]
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  prompt_chat = data.get("prompt_chat_id")
  prompt_msg_id = data.get("prompt_message_id")
  chat_id = data.get("chat_id", 0)
  disp = await _get_chat_display(chat_id) if chat_id else None
  chat_line = _format_chat_line(disp) if disp else ""
  final_text = WarnText.EXPIRED.format(player_line=player.line, chat_line=chat_line)
  if prompt_chat and prompt_msg_id:
    try:
      await safe_edit_message_text(
        _bot(),
        chat_id=prompt_chat,
        message_id=prompt_msg_id,
        text=final_text,
        reply_markup=None,
      )
    except Exception as e:
      WarnDebug.log("PENDING", "edit expired skip", err=str(e))
  try:
    await _bot().send_message(
      admin_id, final_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("PENDING", "notify admin expired skip", admin_id=admin_id, err=str(e))


async def _cleanup_expired_pending_warns_async() -> None:
  from bot.admins.punish_proof import is_proof_expired, pending_items, pending_pop

  now = time.time()
  for uid, data in pending_items(_pending_warns):
    if not is_proof_expired(data.get("expires_at", 0), now=now):
      continue
    pending_pop(_pending_warns, uid)
    WarnDebug.log("PENDING", "expired - warn NOT applied", admin_id=uid)
    await _expire_pending_warn(uid, data)


async def _finish_pending_warn_cancel(
  admin_id: int,
  player_line: str,
  chat_id: int,
) -> bool:
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_warns, admin_id)
  if not pending:
    return False
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  final_text = WarnText.CANCELLED.format(player_line=player_line, chat_line=chat_line)
  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        final_text, chat_id=prompt_chat, message_id=prompt_msg_id,
        parse_mode="HTML", reply_markup=None, link_preview_options=NO_PREVIEW,
      )
      return True
    except Exception as e:
      WarnDebug.error("FLOW", "edit pending prompt", e, chat=prompt_chat, msg=prompt_msg_id)
  return False


async def _complete_warn_with_proof(message: Message) -> bool:
  from bot.admins.punish_proof import (
    is_proof_expired,
    latest_pending_system_for,
    pending_get,
    pending_pop,
  )

  admin_id = message.from_user.id
  if latest_pending_system_for(admin_id) != "warn":
    return False

  pending = pending_get(_pending_warns, admin_id)
  if not pending:
    WarnDebug.log("PROOF", "no pending", admin_id=admin_id)
    return False

  if is_proof_expired(pending.get("expires_at", 0)):
    pending_pop(_pending_warns, admin_id)
    WarnDebug.log("PROOF", "late proof ignored - expired", admin_id=admin_id)
    return True

  pending_chat = pending.get("chat_id")
  if not _is_staff_chat(message.chat.id) or message.chat.id != pending_chat:
    staff = await StaffRef.from_message(message)
    parsed: ParsedWarn = pending.get("parsed")
    player_line = (
      PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username).line + "\n"
      if parsed else ""
    )
    pending_disp = await _get_chat_display(pending_chat) if pending_chat else None
    pending_chat_line = (
      _format_chat_line(pending_disp) + "\n" if pending_disp else ""
    )
    await message.reply(
      WarnText.WRONG_CHAT.format(
        greeting=staff.greeting,
        staff_line=staff.line,
        player_line=player_line,
        pending_chat_line=pending_chat_line,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  proof_media_id = _get_proof_file_id(message)
  if not proof_media_id:
    await message.reply(
      WarnText.NEED_PHOTO + _debug_hint("warn_proof_missing"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  parsed = pending["parsed"]
  from bot.admins.punish_validate import reject_invalid_target_reply
  from bot.admins.punish_proof import (
    clear_pending_prompt_keyboard,
    pending_pop,
    run_finalize_with_pending_fallback,
  )

  if await reject_invalid_target_reply(
    message, parsed.target_id,
    source_chat_id=pending_chat,
    debug_tag="warn_invalid_user_proof",
  ):
    pending_pop(_pending_warns, admin_id)
    await clear_pending_prompt_keyboard(pending)
    return True

  WarnDebug.log("PROOF", "received", admin_id=admin_id, file_id=proof_media_id[:24])
  await run_finalize_with_pending_fallback(
    message, admin_id, _pending_warns, pending,
    lambda: _finalize_warn(
      message, parsed, proof_media_id, pending["chat_id"], pending["admin_name"],
    ),
    on_db_unavailable=lambda: _reply_db_unavailable(message),
  )
  return True


async def _supersede_pending_warn(admin_id: int) -> None:
  """Снимает «зависшее» ожидание фото у этого администратора.

  Вызывается, когда админ начинает НОВОЕ действие варна (как одношаговый варн
  с фото, так и новый запрос ожидания). Это исключает ситуацию, когда старое
  ожидание остаётся активным и затем ошибочно «закрывается» случайным фото,
  приводя к повторному наказанию.
  """
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_warns, admin_id)
  if not pending:
    return
  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        WarnText.SUPERSEDED,
        chat_id=prompt_chat, message_id=prompt_msg_id,
        parse_mode="HTML", reply_markup=None, link_preview_options=NO_PREVIEW,
      )
    except Exception:
      try:
        await _bot().edit_message_reply_markup(
          chat_id=prompt_chat, message_id=prompt_msg_id, reply_markup=None,
        )
      except Exception as e:
        WarnDebug.log("PENDING", "supersede cleanup skip", err=str(e))
  WarnDebug.log("PENDING", "superseded by new warn action", admin_id=admin_id)


# ---------------------------------------------------------------------------
# Команда варна
# ---------------------------------------------------------------------------

async def _handle_warn_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if not await _require_staff_chat(message):
    return True

  command_text = _get_command_text(message)
  # Одиночное «варн» без ответа на нарушителя → справка.
  if (
    _is_warn_command(command_text)
    and len(command_text.split()) == 1
    and not _get_reply_target_message(message)
  ):
    await _send_warn_help(message)
    return True

  result = await parse_warn_command(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    WarnDebug.log("PARSE", "error", code=result.code, info=result.debug_info)
    return True

  parsed = result
  if is_protected_creator(parsed.target_id):
    await message.reply(protected_creator_denied_html(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    WarnDebug.log("AUTH", "protected creator blocked", target=parsed.target_id)
    return True
  if parsed.target_id == message.from_user.id:
    await message.reply(WarnText.SELF, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if parsed.target_id == _bot().id:
    await message.reply(WarnText.BOT, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  from bot.admins.punish_validate import (
    punishment_invalid_user_html,
    validate_punishment_target_user,
  )
  tg_err = await validate_punishment_target_user(
    parsed.target_id, source_chat_id=message.chat.id,
  )
  if tg_err:
    await message.reply(
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("warn_invalid_user"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    WarnDebug.log("TG", "warn blocked - invalid user", target=parsed.target_id)
    return True

  chat_id = message.chat.id
  proof_id = _get_proof_file_id(message)
  admin_name, admin_role, _ = await _resolve_admin_identity(message)

  # Новое действие варна отменяет любое прежнее «зависшее» ожидание этого
  # админа - иначе случайное фото позже могло бы закрыть его повторно.
  await _supersede_pending_warn(message.from_user.id)

  if proof_id:
    WarnDebug.log("FLOW", "one-step warn with photo", proof=proof_id[:24])
    await _finalize_warn(message, parsed, proof_id, chat_id, admin_name)
    return True

  admin_id = message.from_user.id
  current = await _count_warns_typed(parsed.target_id, parsed.mode, chat_id)
  next_count = min(current + 1, WARN_THRESHOLD)
  from bot.admins.punish_proof import (
    clear_other_pending_proofs,
    new_pending_record,
    pending_get,
    pending_set,
  )
  ensure_proof_pending_worker()
  clear_other_pending_proofs(admin_id, keep="warn")
  pending_set(_pending_warns, admin_id, new_pending_record(
    parsed=parsed,
    chat_id=chat_id,
    admin_name=admin_name,
    admin_role=admin_role,
  ))
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  cancel_hint = _suggest_cancel_warn_command(
    parsed.target_id, parsed.target_name, parsed.target_username,
  )
  sent = await message.reply(
    _build_pending_warn_text(parsed, chat_line, next_count, cancel_hint)
    + _debug_hint("awaiting_warn_proof"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_warn_pending_cancel_keyboard(admin_id, parsed.target_id),
  )
  pending = pending_get(_pending_warns, admin_id)
  if pending is not None:
    pending["prompt_chat_id"] = sent.chat.id
    pending["prompt_message_id"] = sent.message_id
  WarnDebug.log(
    "FLOW", "pending proof",
    admin_id=admin_id, target=parsed.target_id, message_id=sent.message_id,
  )
  return True


# ---------------------------------------------------------------------------
# Снятие предупреждения (разварн)
# ---------------------------------------------------------------------------

async def _resolve_simple_target(
  message: Message,
  body: str,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return u.id, u.full_name or u.first_name or str(u.id), u.username
  return await _resolve_target_from_body(message, body)


async def _handle_unwarn_command(message: Message, mode: Mode = "chat") -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if not await _require_staff_chat(message):
    return True

  body = _strip_unwarn_prefix(_get_command_text(message))
  target_id, target_name, target_username = await _resolve_simple_target(message, body)
  if not target_id:
    await message.reply(
      _target_lookup_error_message(body, target_username=target_username)
      + _debug_hint("unwarn_no_target"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  staff = await StaffRef.from_message(message)
  admin_name, _admin_role, _ = await _resolve_admin_identity(message)

  async def _reply(text: str) -> None:
    await message.reply(text, parse_mode="HTML", link_preview_options=NO_PREVIEW)

  if mode in ("all", "full"):
    # «снять варналл» / «снять варнфулл» - полный откат: чистим предупреждения и
    # снимаем блокировку соответствующего охвата (все группы / весь проект).
    await _execute_unwarn_scoped(
      chat_id=message.chat.id,
      actor_id=message.from_user.id,
      admin_name=admin_name,
      staff=staff,
      target_id=target_id,
      target_name=target_name,
      target_username=target_username,
      mode=mode,
      reply=_reply,
    )
  else:
    await _execute_unwarn_core(
      chat_id=message.chat.id,
      actor_id=message.from_user.id,
      admin_name=admin_name,
      staff=staff,
      target_id=target_id,
      target_name=target_name,
      target_username=target_username,
      reply=_reply,
    )
  return True


async def _broadcast_unwarn_groups(
  source_chat_id: int,
  player: PlayerRef,
  staff: StaffRef,
  mode: Mode,
) -> None:
  """Объявляет о снятии предупреждений во всех официальных группах (кроме исходной)."""
  scope_tail = (
    WarnText.UNWARN_GROUP_TAIL_FULL if mode == "full"
    else WarnText.UNWARN_GROUP_TAIL_ALL
  )
  all_chats = [c for c in cfg.STAFF_CHAT_IDS if _is_staff_chat(c)]
  notify_chats = set(cfg.STAFF_CHAT_IDS)
  notify_chats.discard(source_chat_id)
  for cid in notify_chats:
    chat_line = await _format_chats_line(all_chats, current_chat_id=cid)
    text = WarnText.UNWARN_GROUP.format(
      group_title=WarnText.UNWARN_GROUP_TITLE,
      player_line=player.line,
      staff_line=staff.line,
      chat_line=chat_line,
      type_line=_warn_type_line(mode),
      actor=staff.actor,
      player_short=player.short,
      scope_tail=scope_tail,
    )
    try:
      await _bot().send_message(
        cid, text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      WarnDebug.log("NOTIFY", "unwarn group skip", chat_id=cid, err=str(e))


async def _execute_unwarn_scoped(
  *,
  chat_id: int,
  actor_id: int,
  admin_name: str,
  staff: StaffRef,
  target_id: int,
  target_name: Optional[str],
  target_username: Optional[str],
  mode: Mode,
  reply: Callable[[str], Awaitable[Any]],
) -> str:
  """
  Снятие варналл / варнфулл (полный откат). Возвращает 'revoked' | 'none' |
  'forbidden_self'.

  • mode="all"  - чистит все предупреждения и снимает блокировку во всех
                  официальных группах проекта;
  • mode="full" - дополнительно снимает полную блокировку во всём проекте
                  (WebApp users.banned + таблица banusers).
  """
  player = PlayerRef(target_id, target_name or str(target_id), target_username)

  # Снять наказание с самого себя нельзя даже сотруднику с правами.
  if actor_id == target_id:
    await reply(self_revoke_denied_html() + _debug_hint("self_revoke"))
    WarnDebug.log("AUTH", "self revoke blocked (scoped)", actor=actor_id, target=target_id)
    return "forbidden_self"

  # Считаем и снимаем ТОЛЬКО предупреждения этого вида: «снять варналл» не
  # трогает варнфулл и наоборот (виды независимы).
  before = await _count_warns_typed(target_id, mode, 0)

  # Разблокировка во всех официальных группах (идемпотентно).
  lifted_groups: List[int] = []
  try:
    from bot.admins.ban import _lift_ban_everywhere, _delete_all_active_bans
    _was_banned, lifted_groups = await _lift_ban_everywhere(target_id)
    await _delete_all_active_bans(target_id)
  except Exception as e:
    WarnDebug.log("UNWARN", "group unban skip", err=str(e), target=target_id)

  full_lifted = False
  if mode == "full":
    try:
      from bot.admins.ban import _lift_full_project_block
      full_lifted = await _lift_full_project_block(target_id)
    except Exception as e:
      WarnDebug.log("UNWARN", "full lift skip", err=str(e), target=target_id)

  if before > 0:
    await _clear_warns_scoped(target_id, mode, 0)

  reversed_block = bool(lifted_groups) or full_lifted
  if before == 0 and not reversed_block:
    await reply(
      WarnText.NO_WARNS.format(
        player_short=player.short, staff_line=staff.line, player_line=player.line,
      )
      + _debug_hint("unwarn_nothing")
    )
    return "none"

  await _log_warn_action(
    "unwarn", target_id, player.name, target_username,
    actor_id, admin_name,
    (
      "Полный откат предупреждений и блокировки"
      if mode == "full" else
      "Снятие предупреждений во всех группах"
    ),
    None, chat_id,
    mode=mode,
  )

  # Уведомление нарушителю в ЛС.
  extra = WarnText.UNWARN_SCOPED_DM_EXTRA_FULL if mode == "full" else ""
  tail = (
    WarnText.UNWARN_SCOPED_DM_TAIL_FULL if mode == "full"
    else WarnText.UNWARN_SCOPED_DM_TAIL_ALL
  )
  try:
    await _bot().send_message(
      target_id,
      WarnText.UNWARN_SCOPED_DM.format(
        greeting=player.greeting,
        staff_line=staff.line,
        actor=staff.actor,
        extra=extra,
        type_line=_warn_type_line(mode),
        count_line=_warn_count_line(0),
        tail=tail,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("NOTIFY", "scoped unwarn dm skip", user_id=target_id, err=str(e))

  # Объявление в остальных официальных группах.
  await _broadcast_unwarn_groups(chat_id, player, staff, mode)

  title = (
    WarnText.UNWARN_SCOPED_TITLE_FULL if mode == "full"
    else WarnText.UNWARN_SCOPED_TITLE_ALL
  )
  detail = (
    WarnText.UNWARN_SCOPED_DETAIL_FULL if mode == "full"
    else WarnText.UNWARN_SCOPED_DETAIL_ALL
  )
  await reply(
    WarnText.UNWARN_SCOPED_OK.format(
      title=title,
      staff_line=staff.line,
      player_line=player.line,
      type_line=_warn_type_line(mode),
      count_line=_warn_count_line(0),
      detail=detail,
    )
    + _debug_hint("unwarn_scoped_ok")
  )

  # Снимаем возможные таймеры бана нарушителя.
  try:
    from bot.admins import punish_timers
    punish_timers.cancel_ban(target_id)
  except Exception:
    pass

  WarnDebug.log(
    "FLOW", "scoped unwarn done",
    target=target_id, mode=mode, before=before,
    groups=lifted_groups, full=full_lifted,
  )
  return "revoked"


async def _execute_unwarn_core(
  *,
  chat_id: int,
  actor_id: int,
  admin_name: str,
  staff: StaffRef,
  target_id: int,
  target_name: Optional[str],
  target_username: Optional[str],
  reply: Callable[[str], Awaitable[Any]],
  announce_result: bool = True,
  mode: Mode = "chat",
) -> str:
  """Ядро снятия ОДНОГО предупреждения вида `mode`. 'revoked' | 'none' | 'db_error'.

  Не зависит от способа вызова (команда или кнопка). Счётчик и удаление -
  по конкретному виду: chat (в этой группе) / all / full.

  announce_result=False - не отправлять текстовый ответ-результат (для снятия
  через кнопку, когда исходное сообщение редактируется на месте). Для видов
  all / full дополнительно объявляем снятие во всех официальных группах.
  """
  player = PlayerRef(target_id, target_name or str(target_id), target_username)

  # Защита «в глубину»: снять варн с самого себя нельзя даже сотруднику с правами.
  if actor_id == target_id:
    if announce_result:
      await reply(self_revoke_denied_html() + _debug_hint("self_revoke"))
    WarnDebug.log("AUTH", "self revoke blocked", actor=actor_id, target=target_id)
    return "forbidden_self"

  before = await _count_warns_typed(target_id, mode, chat_id)
  if before <= 0:
    if announce_result:
      await reply(
        WarnText.NO_WARNS.format(
          player_short=player.short, staff_line=staff.line, player_line=player.line,
        )
      )
    return "none"

  removed, _removed_id = await _remove_last_warn_typed(target_id, mode, chat_id)
  after = await _count_warns_typed(target_id, mode, chat_id)
  if not removed:
    if announce_result:
      await reply(WarnText.UNWARN_DB_FAIL + _debug_hint("unwarn_db"))
    return "db_error"

  await _log_warn_action(
    "unwarn", target_id, player.name, target_username,
    actor_id, admin_name, "Снятие предупреждения", None, chat_id,
    mode=mode,
  )

  # Уведомим нарушителя в ЛС - приятно и прозрачно.
  try:
    await _bot().send_message(
      target_id,
      WarnText.UNWARN_DM.format(
        greeting=player.greeting,
        staff_line=staff.line,
        actor=staff.actor,
        type_line=_warn_type_line(mode),
        count_line=_warn_count_line(after),
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("NOTIFY", "unwarn dm skip", user_id=target_id, err=str(e))

  # Для варналл/варнфулл объявляем снятие предупреждения во ВСЕХ группах.
  if mode in ("all", "full"):
    await _broadcast_unwarn_groups(chat_id, player, staff, mode)

  if announce_result:
    await reply(
      WarnText.UNWARN_OK.format(
        staff_line=staff.line,
        player_line=player.line,
        type_line=_warn_type_line(mode),
        count_line=_warn_count_line(after),
      )
      + _debug_hint("unwarn_ok")
    )
  WarnDebug.log(
    "FLOW", "unwarn done", target=target_id, mode=mode, before=before, after=after,
  )
  return "revoked"


async def _handle_clear_warns_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if not await _require_staff_chat(message):
    return True

  body = _strip_clear_warns_prefix(_get_command_text(message))
  target_id, target_name, target_username = await _resolve_simple_target(message, body)
  if not target_id:
    await message.reply(
      _target_lookup_error_message(body, target_username=target_username)
      + _debug_hint("clear_warns_no_target"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  # Снять все варны с самого себя нельзя даже сотруднику с правом на варны.
  if message.from_user.id == target_id:
    await message.reply(
      self_revoke_denied_html() + _debug_hint("self_revoke"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    WarnDebug.log("AUTH", "self clear blocked", actor=message.from_user.id, target=target_id)
    return True

  staff = await StaffRef.from_message(message)
  player = PlayerRef(target_id, target_name or str(target_id), target_username)
  before = await _count_warns(target_id)
  if before <= 0:
    await message.reply(
      WarnText.NO_WARNS.format(
        player_short=player.short, staff_line=staff.line, player_line=player.line,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  await _clear_warns(target_id)
  admin_name, _admin_role, _ = await _resolve_admin_identity(message)
  await _log_warn_action(
    "unwarn", target_id, player.name, target_username,
    message.from_user.id, admin_name,
    f"Снятие всех предупреждений ({before})", None, message.chat.id,
    mode="all",
  )

  try:
    await _bot().send_message(
      target_id,
      WarnText.CLEAR_DM.format(
        greeting=player.greeting,
        staff_line=staff.line,
        actor=staff.actor,
        type_line=WarnText.TYPE_LINE.format(label=WarnText.WARN_TYPE_LABEL_MIXED),
        count_line=_warn_count_line(0),
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    WarnDebug.log("NOTIFY", "clear dm skip", user_id=target_id, err=str(e))

  await message.reply(
    WarnText.CLEAR_OK.format(
      staff_line=staff.line,
      player_line=player.line,
      type_line=WarnText.TYPE_LINE.format(label=WarnText.WARN_TYPE_LABEL_MIXED),
      before=before,
      count_line=_warn_count_line(0),
    )
    + _debug_hint("clear_warns_ok"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )
  WarnDebug.log("FLOW", "clear warns done", target=target_id, before=before)
  return True


# ---------------------------------------------------------------------------
# Обзор предупреждений: «мои варны» и «варны @user»
# ---------------------------------------------------------------------------

# Порядок видов «от мягкого к строгому» - для разделов и выбора ближайшего бана.
_WARN_KIND_ORDER: Tuple[Mode, ...] = ("chat", "all", "full")


def _peak_warn_kind(chat_count: int, all_count: int, full_count: int) -> Tuple[Mode, int]:
  """Вид с наибольшим счётом (первым «упрётся» в лимит).

  При равенстве выбираем более строгий вид (full > all > chat), чтобы нижняя
  строка предупреждала о самом серьёзном последствии.
  """
  ranked: List[Tuple[Mode, int]] = [
    ("full", full_count), ("all", all_count), ("chat", chat_count),
  ]
  best_mode, best_count = ranked[0]
  for mode, count in ranked:
    if count > best_count:
      best_mode, best_count = mode, count
  return best_mode, best_count


def _warn_kind_title(mode: Mode) -> str:
  """Короткое название вида: «Варн» / «Варналл» / «Варнфулл»."""
  if mode == "full":
    return WarnText.OV_KIND_TITLE_FULL
  if mode == "all":
    return WarnText.OV_KIND_TITLE_ALL
  return WarnText.OV_KIND_TITLE_CHAT


def _warn_footer_effect(mode: Mode) -> str:
  """Короткое последствие при лимите (для нижней строки)."""
  if mode == "full":
    return WarnText.OV_FX_FULL
  if mode == "all":
    return WarnText.OV_FX_ALL
  return WarnText.OV_FX_CHAT


async def _warn_overview_text(
  *,
  chat_id: int,
  chat_type: str,
  target_id: int,
  self_view: bool,
  target_name: Optional[str] = None,
  target_username: Optional[str] = None,
) -> str:
  """Короткий обзор в одном сообщении: показываем только реально имеющиеся виды,
  под каждым - короткое последствие при лимите. Обычные (chat) варны разбиваем по
  группам: строка на каждую группу + ссылка на ту самую группу в последствии."""
  # Имя участника - кликабельная ссылка (t.me/@username или tg://user).
  name = (target_name or "").strip()
  username = target_username
  rname, ruser = await _resolve_user_display(target_id)
  if not name:
    name = (rname or "").strip() or str(target_id)
  if not username:
    username = ruser
  player = PlayerRef(target_id, name, username)

  rows = await warn_kind_rows(target_id)
  if not rows:
    if self_view:
      return WarnText.OV_EMPTY_SELF.format(player_line=player.line)
    return WarnText.OV_EMPTY_OTHER.format(player_line=player.line)

  parts: List[str] = [WarnText.OV_TITLE_SELF if self_view else WarnText.OV_TITLE_OTHER]
  parts.append(player.line)
  parts.extend(rows)
  return "\n".join(parts)


def _warn_kind_row(mode: Mode, count: int) -> str:
  """Одна строка вида: «💼 {Вид}: {count}/{th}  {шкала}»."""
  return WarnText.OV_ROW.format(
    title=_warn_kind_title(mode),
    count=min(count, WARN_THRESHOLD), th=WARN_THRESHOLD,
    bar=_warn_progress_bar(count),
  )


def _warn_item_card(num: int, row: Dict[str, Any]) -> str:
  """Полная карточка одного варна: кто выдал · причина · когда выдан · когда
  исчезнет. Многострочная, аккуратная - видна вся информация о предупреждении."""
  role_title = role_title_from_cache(row.get("admin_role"))
  admin_name = (row.get("admin_name") or "").strip() or "-"
  admin_id = row.get("admin_user_id")
  # Имя администратора - кликабельная ссылка на профиль (если знаем его id).
  if admin_id:
    actor = f"{escape(role_title)} {_user_link(int(admin_id), admin_name)}".strip()
  else:
    actor = f"{escape(role_title)} {escape(admin_name)}".strip()
  reason = (row.get("reason") or "").strip()
  reason_txt = escape(reason) if reason else WarnText.OV_ITEM_REASON_NONE

  frags: List[str] = []
  created = row.get("created_at")
  if created is not None:
    frags.append(WarnText.OV_ITEM_CREATED.format(created=_format_until(created)))
  exp = row.get("expires_at")
  if exp is None:
    frags.append(WarnText.OV_ITEM_EXP_PERM)
  else:
    frags.append(WarnText.OV_ITEM_EXP_TIMED.format(until=_format_until(exp)))

  lines = [
    WarnText.OV_ITEM_ACTOR.format(num=num, actor=actor),
    WarnText.OV_ITEM_REASON.format(reason=reason_txt),
    WarnText.OV_ITEM_WHEN.format(when=" · ".join(frags)),
  ]
  return "\n".join(lines)


def _warn_bucket_block(consequence_text: str, items: List[Dict[str, Any]]) -> str:
  """Единый blockquote под строкой вида: последствие при лимите + ПОЛНЫЕ карточки
  каждого варна этого вида.

  Карточки сортируются «ближайший к исчезновению - сверху» (что сгорит раньше - то
  и выше); постоянные варны идут в конце.
  """
  ordered = sorted(items, key=lambda r: (r.get("expires_at") is None, r.get("expires_at") or datetime.max))
  cards = [_warn_item_card(i, r) for i, r in enumerate(ordered, start=1)]
  body = f"<blockquote><i>{consequence_text}</i>"
  if cards:
    body += "\n\n" + "\n\n".join(cards)
  body += "</blockquote>"
  return body


async def warn_kind_rows(user_id: int) -> List[str]:
  """Сгруппированный по видам блок предупреждений: строка вида (тип + счёт + шкала)
  и blockquote с последствием при лимите и ПОЛНОЙ информацией о каждом варне
  (кто выдал · причина · когда выдан · когда исчезнет · в какой группе).

  Единый формат и для обзора «варны @user» / «мои варны», и для сводки «наказания»:
    • обычный варн - по строке на КАЖДУЮ группу (ссылка именно на ту группу);
    • варналл - одна строка, последствие «во всех официальных группах»;
    • варнфулл - одна строка, последствие «во всём проекте».
  Показываются только реально имеющиеся виды; пустой список - варнов нет.
  """
  rows = await _list_warns_detailed(user_id)
  if not rows:
    return []

  chat_buckets: Dict[int, List[Dict[str, Any]]] = {}
  all_list: List[Dict[str, Any]] = []
  full_list: List[Dict[str, Any]] = []
  for r in rows:
    mode = str(r.get("mode") or ("all" if r.get("scope") == "all" else "chat"))
    if mode == "full":
      full_list.append(r)
    elif mode == "all":
      all_list.append(r)
    else:
      chat_buckets.setdefault(int(r.get("chat_id") or 0), []).append(r)

  lines: List[str] = []
  # Каждый вид отделяем пустой строкой сверху - так блоки читаются как отдельные
  # карточки, а не сливаются в сплошную «простыню».
  # Обычные варны - по строке на каждую группу (больше счёт → выше).
  for g_chat_id, items in sorted(chat_buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    lines.append("")
    lines.append(_warn_kind_row("chat", len(items)))
    if g_chat_id and _is_staff_chat(g_chat_id):
      disp = await _get_chat_display(g_chat_id)
      group_label = _chat_link_inline(disp)
    else:
      group_label = "<i>этой группе</i>"
    cons = WarnText.OV_CONS_CHAT.format(th=WARN_THRESHOLD, group=group_label)
    lines.append(_warn_bucket_block(cons, items))

  if all_list:
    lines.append("")
    lines.append(_warn_kind_row("all", len(all_list)))
    lines.append(_warn_bucket_block(WarnText.OV_CONS_ALL.format(th=WARN_THRESHOLD), all_list))

  if full_list:
    lines.append("")
    lines.append(_warn_kind_row("full", len(full_list)))
    lines.append(_warn_bucket_block(WarnText.OV_CONS_FULL.format(th=WARN_THRESHOLD), full_list))

  return lines


async def build_block_warn_overview(
  user_id: int,
  *,
  name: Optional[str] = None,
  username: Optional[str] = None,
) -> str:
  """Обзор варнов пользователя ДЛЯ БАРЬЕРА ПОЛНОЙ БЛОКИРОВКИ (вид «от первого лица»).

  Публичная обёртка над обзором «мои варны»: барьер полной блокировки
  (bot/admins/ban.py) показывает её заблокированному пользователю, чтобы он сразу
  видел свои варнфулл/варны и причину. Возвращает ПУСТУЮ строку, если варнов нет
  (например, «банфулл»/блокировка выданы вручную) - тогда барьер ограничится
  своим баннером. Полностью защищено от ошибок: обзор не критичен для самой
  блокировки, поэтому любой сбой лишь скрывает детали, но не ломает барьер.
  """
  try:
    await _ensure_warn_schema()
    rows = await warn_kind_rows(user_id)
    if not rows:
      return ""
    rname, ruser = await _resolve_user_display(user_id)
    disp_name = (name or "").strip() or (rname or "").strip() or str(user_id)
    disp_username = username or ruser
    player = PlayerRef(user_id, disp_name, disp_username)
    parts: List[str] = [WarnText.OV_TITLE_SELF, player.line]
    parts.extend(rows)
    return "\n".join(parts)
  except Exception as e:
    WarnDebug.log("BLOCK", "overview build skip", err=str(e), user=user_id)
    return ""


async def _handle_warn_status_command(message: Message) -> bool:
  """«варны @user» / ответом - обзор предупреждений участника (доступно всем)."""
  await _ensure_warn_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  body = _strip_command_prefix(_get_command_text(message), WARN_STATUS_COMMANDS)
  target_id, target_name, target_username = await _resolve_simple_target(message, body)
  if not target_id:
    await message.reply(
      _target_lookup_error_message(body, target_username=target_username)
      + _debug_hint("warns_no_target"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  text = await _warn_overview_text(
    chat_id=message.chat.id,
    chat_type=message.chat.type,
    target_id=target_id,
    self_view=False,
    target_name=target_name,
    target_username=target_username,
  )
  await message.reply(
    text + _debug_hint("warns_status"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )
  WarnDebug.log("FLOW", "warns status shown", target=target_id)
  return True


async def _handle_my_warns_command(message: Message) -> bool:
  """«мои варны» / «мой варн» - короткий обзор СВОИХ предупреждений (для всех)."""
  await _ensure_warn_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  user = message.from_user
  text = await _warn_overview_text(
    chat_id=message.chat.id,
    chat_type=message.chat.type,
    target_id=user.id,
    self_view=True,
    target_name=user.full_name,
    target_username=user.username,
  )
  await message.reply(
    text + _debug_hint("my_warns"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )
  WarnDebug.log("FLOW", "my_warns shown", user=user.id)
  return True


# ---------------------------------------------------------------------------
# Отмена ожидания
# ---------------------------------------------------------------------------

async def _resolve_cancel_warn_target(message: Message) -> ParsedWarn | ParseError:
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return ParsedWarn(
      target_id=u.id,
      target_name=u.full_name or u.first_name or str(u.id),
      target_username=u.username,
      reason="",
    )
  body = _strip_cancel_warn_prefix(_get_command_text(message))
  if not body:
    return ParseError(
      "cancel_warn_no_target",
      WarnText.CANCEL_NO_TARGET,
      "",
    )
  target_id, target_name, target_username = await _resolve_target_from_body(message, body)
  if not target_id:
    return ParseError(
      "cancel_warn_not_found",
      _target_lookup_error_message(body, target_username=target_username),
      body,
    )
  return ParsedWarn(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    reason="",
  )


async def _handle_cancel_warn_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _require_staff_chat(message):
    return True

  result = await _resolve_cancel_warn_target(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  target = result
  admin_id = message.from_user.id
  staff = await StaffRef.from_message(message)
  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_warns, admin_id)
  player = PlayerRef(target.target_id, target.target_name, target.target_username)

  if not pending:
    await message.reply(
      WarnText.NO_PENDING.format(greeting=staff.greeting, player_line=player.line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  if pending["parsed"].target_id != target.target_id:
    pending_player = PlayerRef(
      pending["parsed"].target_id,
      pending["parsed"].target_name,
      pending["parsed"].target_username,
    )
    cancel_hint = escape(_suggest_cancel_warn_command(
      pending["parsed"].target_id, pending["parsed"].target_name, pending["parsed"].target_username,
    ))
    await message.reply(
      WarnText.OTHER_PENDING.format(
        greeting=staff.greeting,
        pending_player_line=pending_player.line,
        cancel_hint=cancel_hint,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  chat_id = pending.get("chat_id", message.chat.id)
  edited = await _finish_pending_warn_cancel(admin_id, player.line, chat_id)
  if not edited:
    disp = await _get_chat_display(chat_id)
    chat_line = _format_chat_line(disp)
    await message.reply(
      WarnText.CANCEL_FALLBACK.format(player_line=player.line, chat_line=chat_line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  WarnDebug.log("FLOW", "pending cancelled", admin_id=admin_id, target=target.target_id)
  return True


# ---------------------------------------------------------------------------
# Основной обработчик
# ---------------------------------------------------------------------------

async def _maybe_warn_maintenance() -> None:
  """Ожидание фото обрабатывает proof worker."""
  return


async def warn_process(message: Message) -> bool:
  """Обрабатывает сообщения системы предупреждений. True = перехвачено."""
  if not message.from_user:
    return False

  from bot.admins.punish_proof import (
    is_proof_only_photo,
    pending_contains,
    pending_get,
  )

  chat_id = message.chat.id
  uid = message.from_user.id
  pending = pending_contains(_pending_warns, uid)

  # «Мои варны» и «варны @user» доступны любому пользователю в любом чате
  # (включая ЛС) - обрабатываем до проверок типа чата и ожиданий.
  early_text = _get_command_text(message)
  if early_text and _is_my_warns_command(early_text):
    return await _handle_my_warns_command(message)
  if early_text and _is_warn_status_command(early_text):
    return await _handle_warn_status_command(message)

  if not pending and chat_id > 0:
    return False
  if not pending and chat_id < 0 and not _is_staff_chat(chat_id):
    if not _is_warn_related_message(message):
      return False

  await _ensure_mute_schema()

  command_text = _get_command_text(message)
  WarnDebug.log(
    "IN", "message",
    uid=uid, chat=chat_id,
    text=command_text[:80] if command_text else "",
    photo=bool(message.photo), reply=bool(message.reply_to_message),
    pending=pending,
  )

  if pending:
    if is_proof_only_photo(message):
      return await _complete_warn_with_proof(message)

    if not command_text:
      WarnDebug.log("PROOF", "ignored non-photo while pending", uid=uid)
      return True

    low = command_text.lower().strip()
    if low in ("отмена", "cancel", "/cancel"):
      if not pending_contains(_pending_warns, uid):
        return False
      perm = await check_staff_permission(uid, "warn")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "warn")
      if not _is_staff_chat(message.chat.id):
        return False
      pending_data = pending_get(_pending_warns, uid)
      if not pending_data:
        return False
      p: ParsedWarn = pending_data["parsed"]
      hint = _suggest_cancel_warn_command(p.target_id, p.target_name, p.target_username)
      staff = await StaffRef.from_message(message)
      player = PlayerRef(p.target_id, p.target_name, p.target_username)
      await message.reply(
        WarnText.CANCEL_HELP.format(
          greeting=staff.greeting,
          staff_line=staff.line,
          player_line=player.line,
          cancel_hint=escape(hint),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      return True

    if _is_cancel_warn_command(command_text):
      perm = await check_staff_permission(uid, "warn")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "warn")
      return await _handle_cancel_warn_command(message)

    if _is_warn_command(command_text):
      warn_action = _warn_permission_action(command_text)
      perm = await check_staff_permission(uid, warn_action)
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, warn_action)
      return await _handle_warn_command(message)

    WarnDebug.log("PROOF", "ignored text while pending", uid=uid, text=command_text[:60])
    return True

  if is_proof_only_photo(message) and _is_warn_related_message(message):
    warn_action = _warn_permission_action(command_text)
    perm = await check_staff_permission(uid, warn_action)
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, warn_action)
    return await _handle_warn_command(message)

  if not command_text:
    return False

  low = command_text.lower().strip()
  if low in ("отмена", "cancel", "/cancel"):
    return False

  if _is_cancel_warn_command(command_text):
    perm = await check_staff_permission(message.from_user.id, "warn")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "warn")
    return await _handle_cancel_warn_command(message)

  if _is_clear_warns_command(command_text):
    perm = await check_staff_permission(message.from_user.id, "warn")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "warn")
    return await _handle_clear_warns_command(message)

  if _is_unwarn_command(command_text):
    # Право проверяем по охвату снятия: warn / warnall / warnfull.
    unwarn_mode = _unwarn_mode(command_text) or "chat"
    unwarn_action = _WARN_MODE_PERMISSION.get(unwarn_mode, "warn")
    perm = await check_staff_permission(message.from_user.id, unwarn_action)
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, unwarn_action)
    return await _handle_unwarn_command(message, unwarn_mode)

  # Обзор «варны @user» уже обработан выше (доступен всем) - сюда не доходим.
  if _is_warn_status_command(command_text):
    return False

  if not _is_warn_command(command_text):
    return False

  # Право проверяем по конкретному режиму: warn / warnall / warnfull.
  warn_action = _warn_permission_action(command_text)
  perm = await check_staff_permission(message.from_user.id, warn_action)
  if perm == "db_unavailable":
    await _reply_db_unavailable(message)
    return True
  if perm != "allowed":
    return await deny_permission(message, warn_action)

  return await _handle_warn_command(message)


@warn_router.callback_query(F.data.startswith("warn:cancel:"))
async def on_warn_pending_cancel(callback: CallbackQuery) -> None:
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) != 4:
    await callback.answer(WarnText.CB_BAD_DATA, show_alert=True)
    return

  admin_id = int(parts[2])
  target_id = int(parts[3])

  if callback.from_user.id != admin_id:
    await callback.answer(WarnText.CB_ONLY_AUTHOR, show_alert=True)
    return

  perm = await check_staff_permission(admin_id, "warn")
  if perm != "allowed":
    if perm == "db_unavailable":
      await callback.answer(WarnText.CB_DB, show_alert=True)
    else:
      await callback.answer(WarnText.CB_NO_PERM, show_alert=True)
    return

  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_warns, admin_id)
  if not pending:
    try:
      await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
      pass
    await callback.answer(WarnText.CB_DONE, show_alert=True)
    return

  if pending["parsed"].target_id != target_id:
    await callback.answer(WarnText.CB_STALE, show_alert=True)
    return

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(WarnText.CB_WRONG_CHAT, show_alert=True)
    return

  parsed: ParsedWarn = pending["parsed"]
  player_line = PlayerRef(target_id, parsed.target_name, parsed.target_username).line
  chat_id = pending.get("chat_id", callback.message.chat.id)
  await _finish_pending_warn_cancel(admin_id, player_line, chat_id)
  await callback.answer(WarnText.CB_CANCELLED)
  WarnDebug.log("FLOW", "pending cancelled via button", admin_id=admin_id, target=target_id)


@warn_router.callback_query(F.data.startswith("warn:revoke:"))
async def on_warn_revoke(callback: CallbackQuery) -> None:
  """Снятие одного предупреждения по кнопке под сообщением «Предупреждение выдано».

  Нажать может любой сотрудник с правом на выдачу/снятие предупреждений.
  """
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  # Совместимость: старые кнопки без режима (4 части) трактуем как 'chat'.
  if len(parts) < 4:
    await callback.answer(WarnText.CB_BAD_DATA, show_alert=True)
    return
  try:
    target_id = int(parts[3])
  except ValueError:
    await callback.answer(WarnText.CB_BAD_DATA, show_alert=True)
    return
  raw_mode = parts[4] if len(parts) >= 5 else "chat"
  mode: Mode = raw_mode if raw_mode in ("chat", "all", "full") else "chat"

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(WarnText.CB_WRONG_CHAT, show_alert=True)
    return

  clicker = callback.from_user.id
  # Право снятия соответствует виду предупреждения: warn / warnall / warnfull.
  revoke_action = _WARN_MODE_PERMISSION.get(mode, "warn")
  perm = await check_staff_permission(clicker, revoke_action)
  if perm != "allowed":
    await callback.answer(
      WarnText.CB_DB if perm == "db_unavailable" else WarnText.CB_NO_PERM,
      show_alert=True,
    )
    return

  staff = await StaffRef.from_user_id(clicker)
  target_name, target_username = await _resolve_user_display(target_id)

  async def _noop(_text: str) -> None:
    return None

  status = await _execute_unwarn_core(
    chat_id=callback.message.chat.id,
    actor_id=clicker,
    admin_name=staff.name,
    staff=staff,
    target_id=target_id,
    target_name=target_name,
    target_username=target_username,
    reply=_noop,
    announce_result=False,
    mode=mode,
  )

  if status == "revoked":
    after = await _count_warns_typed(target_id, mode, callback.message.chat.id)
    player = PlayerRef(target_id, target_name or str(target_id), target_username)
    new_text = WarnText.REVOKED_EDIT.format(
      staff_line=staff.line,
      player_line=player.line,
      type_line=_warn_type_line(mode),
      count_line=_warn_count_line(after),
    )
    await _edit_revoked_message(callback.message, new_text)
    await callback.answer(WarnText.CB_REVOKED)
  elif status == "none":
    await _edit_remove_keyboard(callback.message)
    await callback.answer(WarnText.CB_NONE, show_alert=True)
  elif status == "forbidden_self":
    await callback.answer(WarnText.CB_SELF_REVOKE, show_alert=True)
  else:
    await callback.answer(WarnText.CB_REVOKE_FAILED, show_alert=True)
  WarnDebug.log("FLOW", "warn revoked via button", actor=clicker, target=target_id, status=status)


# ---------------------------------------------------------------------------
# Middleware - перехват сообщений системы предупреждений
# ---------------------------------------------------------------------------

class WarnMiddleware(BaseMiddleware):
  """
  Фоновая поддержка системы предупреждений:
    • шаг 2 - фото-пруф / отмена при активном ожидании (pending);
    • одношаговый варн с фото-пруфом и подписью-командой (медиа main.py не ловит).

  Текстовые команды варна (без фото) приходят из main.py по паттерну команд -
  здесь они НЕ перехватываются, чтобы не было двойной обработки.
  """
  async def __call__(self, handler, event: TelegramObject, data: dict):
    if not isinstance(event, Message) or not event.from_user:
      return await handler(event, data)

    msg: Message = event
    uid = msg.from_user.id
    from bot.admins.punish_proof import pending_contains
    pending = pending_contains(_pending_warns, uid)
    staff_group = msg.chat.id < 0 and _is_staff_chat(msg.chat.id)

    media_command = (
      not pending
      and staff_group
      and _has_proof_media(msg)
      and _is_warn_related_message(msg)
    )

    if not pending and not media_command:
      return await handler(event, data)

    try:
      if await warn_process(msg):
        WarnDebug.log("MW", "handled warn", msg_id=msg.message_id, pending=pending)
        return None
    except Exception as e:
      WarnDebug.error("MW", "warn_process crash", e, msg_id=getattr(msg, "message_id", None))
      try:
        await msg.reply(_generic_handler_error_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
      except Exception:
        pass
    return await handler(event, data)


# ---------------------------------------------------------------------------
# Роутер (запасной канал для фото) + публичная точка входа
# ---------------------------------------------------------------------------

@warn_router.message(F.photo)
async def warn_on_photo(message: Message) -> None:
  if _is_warn_related_message(message):
    await warn_process(message)


async def warn(message: Message) -> None:
  await warn_process(message)


def attach_warn_system(dp) -> None:
  global _warn_system_attached
  if _warn_system_attached:
    WarnDebug.log("WIRE", "already attached")
    return
  try:
    dp.message.middleware(WarnMiddleware())
    dp.include_router(warn_router)
    _warn_system_attached = True
    ensure_proof_pending_worker()
    WarnDebug.log("WIRE", "attached middleware + router", log_file=WARN_LOG_FILE)
    print(f"[WARN] ✅ Система предупреждений подключена → лог: {WARN_LOG_FILE}")
  except Exception as e:
    WarnDebug.error("WIRE", "attach failed", e)
    print(f"[WARN][WIRE][ERROR] {e}")
