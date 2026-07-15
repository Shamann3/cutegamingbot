# -*- coding: utf-8 -*-
"""
Система мутов администраторов.

Подключение (main.py):
    # Текстовые команды - в обработчике @dp.message(F.text), паттерн как у «шарик»:
    #   mute_cmd_text / kick_cmd_text → lazy import → update() → measure_time(mute/kick)
    # Фоновая поддержка (фото-доказательства, кнопки отмены, блокировка замученных):
    from bot.admins.kick import attach_kick_system
    from bot.admins.mute import attach_mute_system
    attach_kick_system(dp)
    attach_mute_system(dp)

Форматы мута:
    • Ответ + фото + подпись:  мут 60с причина
    • Без ответа + фото:       мут @user 60с причина
                               мут 123456789 1ч
                               мут Иван 1ч
    • Два шага: текст → фото (в течение 5 мин)
    • Размут: размут / снять мут @user / размут username (без @)

Форматы кика (bot/admins/kick.py):
    • Ответ + фото: кик причина
    • кик @user причина · кик username · кик ID
    • Отмена: отменить кик @user

proof_media_id → staff_actions (Telegram file_id)

Права:
    admin_accounts - должность (role), статус, доступность
    staff_rules    - mute, kick, unmute и др. (столбцы 1/0)
"""
from __future__ import annotations

import os
import re
import time
import traceback
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Tuple, Union

from bot.db_create.pklcode import LazyGameStore

Scope = Literal["chat", "all"]
# Режим наказания (бан/варн):
#   chat - только текущая группа;
#   all  - все официальные группы проекта (…алл / …всё / …all);
#   full - все официальные группы + полная блокировка во всём проекте
#          (…фулл / …фул / …full): WebApp (users.banned) и таблица banusers.
Mode = Literal["chat", "all", "full"]

_MOD_SCOPE_ALL_SUFFIXES: Tuple[str, ...] = ("all", "все", "всё", "алл", "вся")
# Суффиксы «полной» блокировки во всём проекте (банфул/банфулл/banfull).
_MOD_SCOPE_FULL_SUFFIXES: Tuple[str, ...] = ("full", "фулл", "фул", "фулл")
_MUTE_CMD_ROOTS: Tuple[str, ...] = ("мут", "mute", "замутить")

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
  CallbackQuery,
  ChatPermissions,
  InlineKeyboardButton,
  InlineKeyboardMarkup,
  LinkPreviewOptions,
  Message,
  TelegramObject,
  User,
)

mute_router = Router(name="staff_mute")


# =============================================================================
#  НАСТРОЙКИ СИСТЕМЫ МУТА - меняйте параметры в этом блоке
# =============================================================================

from bot.admins.punish_proof import (
  PROOF_TIMEOUT_SEC,
  ensure_proof_pending_worker,
  is_proof_expired,
  proof_expires_at,
)


class MuteConfig:
  """
  Центральные настройки мута.
  Все важные параметры собраны здесь для удобной настройки.
  """

  # --- Официальные чаты проекта (мута/кика/размута) ---
  STAFF_CHAT_IDS: frozenset = frozenset({
    -1001612636292,
    -1001921925861,
  })

  # --- Группы, где модерация намеренно отключена (бот работает как обычно) ---
  MODERATION_EXCLUDED_CHAT_IDS: frozenset = frozenset({})

  # --- Команды ---
  MUTE_COMMANDS: frozenset = frozenset({
    "мут", "/mute", "mute", "замутить", "/замутить",
  })
  UNMUTE_COMMANDS: frozenset = frozenset({
    "размутить", "размут", "/unmute", "unmute", "/размутить",
  })

  # --- Ожидание фото-доказательства (шаг 2) ---
  # Единый таймаут для всех систем наказаний правка только в punish_proof.py
  PROOF_TIMEOUT_SEC: int = PROOF_TIMEOUT_SEC

  # --- Фоновый воркер ---
  # Как часто проверять истёкшие муты (секунды); ожидание фото punish_proof
  WORKER_INTERVAL_SEC: int = 20

  # --- Отладка и логи ---
  DEBUG: bool = True
  DEBUG_ADMIN_HINTS: bool = False  # технические подсказки в ответах админу
  LOG_FILE: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "log_mute.txt",
  )

  # Подпись строки нарушителя в структурированных сообщениях
  PLAYER_LINE_LABEL: str = "Нарушитель"

  # Кэш записей из БД (секунды)
  ADMIN_ACCOUNT_CACHE_SEC: int = 30
  STAFF_RULES_CACHE_SEC: int = 60

  # Внутренние коды действий системы мута (не роли - привязка к столбцам staff_rules)
  MUTE_SYSTEM_ACTIONS: Tuple[str, ...] = (
    "mute", "unmute", "cancel_mute", "cancel_pending",
  )

  @classmethod
  def proof_timeout_minutes(cls) -> int:
    from bot.admins.punish_proof import proof_timeout_minutes
    return proof_timeout_minutes()


# Единый объект настроек (используется во всём модуле)
cfg = MuteConfig()

# Обратная совместимость для внешних импортов
STAFF_CHAT_IDS = cfg.STAFF_CHAT_IDS
MODERATION_EXCLUDED_CHAT_IDS = cfg.MODERATION_EXCLUDED_CHAT_IDS
MUTE_COMMANDS = cfg.MUTE_COMMANDS
UNMUTE_COMMANDS = cfg.UNMUTE_COMMANDS
PROOF_TIMEOUT_SEC = cfg.PROOF_TIMEOUT_SEC
MUTE_DEBUG = cfg.DEBUG
MUTE_DEBUG_ADMIN_HINTS = cfg.DEBUG_ADMIN_HINTS
MUTE_LOG_FILE = cfg.LOG_FILE


# =============================================================================
#  📝 ТЕКСТЫ СИСТЕМЫ МУТА / РАЗМУТА - меняйте текст и эмодзи ПРЯМО ЗДЕСЬ
# -----------------------------------------------------------------------------
#  Всё, что видит администратор/нарушитель в системе мута, собрано в этом классе.
#  • Чтобы поменять текст - правьте строки ниже.
#  • Чтобы поменять эмодзи - меняйте эмодзи прямо в строках.
#  • {фигурные_скобки} - автоподстановка (имя, срок, причина и т.п.).
# =============================================================================

class MuteText:
  SERVICE_UNAVAILABLE = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Сервис временно недоступен</b>\n"
    "<i>Попробуйте позже или обратитесь к старшему администратору.</i>"
  )
  GENERIC_ERROR = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Не удалось выполнить команду</b>\n"
    "<i>Попробуйте ещё раз. Если проблема повторится - обратитесь к старшему администратору.</i>"
  )
  RULES_UNAVAILABLE = (
    "<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> Модерация временно недоступна</b>\n"
    "<i>Правила доступа сейчас не загружены. Попробуйте позже или обратитесь к старшему "
    "администратору.</i>"
  )
  HELP = (
    "<b><tg-emoji emoji-id='5890838600433536921'>🔇</tg-emoji> Справка о временном ограничении</b>\n\n"
    "<b>Фото обязательно</b> - в подписи к команде или отдельным сообщением "
    "(до {timeout} мин.).\n\n"
    "<i>Текст после времени в команде считается причиной.</i>\n"
    "· ответ на сообщение + <code>мут 60с нарушение правил</code>\n"
    "· <code>мут @user 1ч</code> · <code>мут username 1ч</code>\n\n"
    "<b>Охват:</b>\n"
    "· <code>мут</code> - только <i>эта</i> группа\n"
    "· <code>муталл</code> · <code>мутвсе</code> - <i>все</i> официальные группы\n\n"
    "· <code>размут @user</code> · <code>размут username</code> · ответ + <code>размут</code>\n\n"
    "<b>Отмена ожидания:</b>\n"
    "<code>отменить мут @user</code>"
  )
  NO_PERMISSION = (
    "{greeting}\n"
    "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Нет доступа</b>\n"
    "<i>{reason}.</i>\n"
    "<i>{action_label} могут выполнять : {allowed_hint}.</i>\n"
    "<blockquote><i>Если считаете, что это ошибка - обратитесь к старшему администратору.</i>"
    "</blockquote>"
  )
  ERR_NEED_TIME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите время.</b>\n"
    "<code>мут 60с</code> · <code>мут [username, id, имя нарушителя] [время]</code>"
  )
  ERR_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Кого мутить?</b>\n"
    "<b>Ответьте на сообщение нарушителя или напишите :</b> "
    "<code>мут [username, id, имя нарушителя] [время]</code>"
  )
  ERR_NEED_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<code>мут [username, id, имя нарушителя] [время]</code>"
  )
  ERR_NOT_FOUND_USERNAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> <code>{token}</code> не найдено</b>"
  ERR_NOT_FOUND_ID = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> ID <code>{token}</code> не найдено</b>"
  ERR_NOT_FOUND_NAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> «{token}» не найдено</b>"
  ERR_NO_DURATION = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите время</b>\n"
    "<code>60с</code> · <code>1ч</code> · <code>1д</code> · <code>1мес</code> · <code>1год</code>"
  )
  ERR_BAD_DURATION = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Неверное время :</b> <code>{duration}</code>"
  UNMUTE_NOT_FOUND_USERNAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>@{username}</code> не найден</b>\n"
    "<blockquote><i>Убедитесь, что username указан верно и пользователь есть в базе.</i></blockquote>"
  )
  UNMUTE_NOT_FOUND_ID = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "ID <code>{token}</code> не найден</b>"
  )
  UNMUTE_NOT_FOUND_NAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "«{body}» не найден</b>"
  )
  UNMUTE_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<code>размут @user</code> · <code>размут username</code> · "
    "<code>снять мут @user</code>\n"
    "<code>размут ID</code> · <code>размут Имя</code>\n"
    "<blockquote><i>Или ответьте на сообщение нарушителя.</i></blockquote>"
  )
  CANCEL_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<code>отменить мут @user</code> · <code>отменить мут username</code> · "
    "<code>отменить мут ID</code>\n"
    "<blockquote><i>Или ответьте на сообщение нарушителя.</i></blockquote>"
  )
  SELF = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя замутить себя</b>"
  BOT = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя замутить бота</b>"
  PENDING = (
    "{header} <b>· ждём фото</b>\n"
    "{player_line}\n{term_block}\n{reason_block}"
    "\n<blockquote><i><b>Фото в этот чат за {timeout} мин.</b> · отмена - кнопкой ниже</i></blockquote>"
  )
  BTN_CANCEL = "Отменить ожидание"
  BTN_REVOKE = "Снять мут"
  PENDING_CANCELLED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n{chat_line}\n{reason_part}"
    "<blockquote><b><i>Наказание не применено - фото больше не требуется.</i></b></blockquote>"
  )
  PENDING_CANCELLED_FALLBACK = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n{chat_line}\n"
    "<blockquote><i>Наказание не применено - фото больше не требуется.</i></blockquote>"
  )
  PENDING_SUPERSEDED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "<blockquote><b><i>Начато новое действие модерации - это ожидание фото "
    "больше не активно.</i></b></blockquote>"
  )
  SUCCESS = (
    "{header} <b>· выдан</b>\n"
    "{player_line}\n"
    "{staff_line}\n"
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> {duration} · до</b> <code>{until}</code>\n"
    "{reason_block}{warn}"
  )
  SUCCESS_WARN = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "<i>Ограничение в чате не применено - повторите.</i></b>"
  )
  DB_ERROR = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ошибка - не удалось сохранить мут.</b>"
  SUCCESS_FALLBACK = (
    "<b><tg-emoji emoji-id='5210956306952758910'>🔇</tg-emoji> Мут выдан · {duration}</b>"
  )
  NEED_PHOTO = "<b><tg-emoji emoji-id='5305265301917549162'>📎</tg-emoji> Нужно фото - прикрепите изображение.</b>"
  WRONG_CHAT = (
    "{greeting}\n{staff_line}\n{player_line}{pending_chat_line}"
    "<blockquote><b>Отправьте фото в тот же чат, где была выдана команда мута.</b></blockquote>"
  )
  VIOLATOR_MUTED = (
    "{greeting}\n"
    "{header}\n"
    "<blockquote><i>вам ограничена отправка сообщений {scope}.</i></blockquote>\n"
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> {duration} · до</b> <code>{until}</code>\n"
    "{reason_block}"
  )
  GROUP = (
    "{header} <b>· выдан</b>\n"
    "{player_line}\n"
    "{staff_line}"
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> {duration} · до</b> <code>{until}</code>\n"
    "{reason_block}"
  )
  CHAT_UNMUTE_VIOLATOR = (
    "{greeting}\n"
    "<blockquote><i>срок мута {scope} истёк - снова можете писать.</i></blockquote>"
  )
  CHAT_UNMUTE_GROUP = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Мут снят</b> <i>· истёк срок</i>\n"
    "{player_line}\n"
    "<blockquote><b><i>{player_short} снова может писать.</i></b></blockquote>"
  )
  EXPIRED_VIOLATOR = (
    "{greeting}\n"
    "<blockquote><i>срок мута во всех группах истёк - снова можете писать.</i></blockquote>{reason_suffix}"
  )
  EXPIRED_ADMIN = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Авторазмут</b> <i>· все группы</i>\n"
    "{player_line}\n{staff_line}{reason_suffix}\n"
    "<blockquote><b><i>Срок истёк - {player_short} снова может писать.</i></b></blockquote>"
  )
  EXPIRED_GROUP_FOOTER = (
    "<blockquote><b><i>Срок истёк - {player_short} снова может писать.</i></b></blockquote>"
  )
  EXPIRED_TITLE = "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Мут снят</b>"
  CANCELLED_VIOLATOR = (
    "{greeting}\n{staff_line}"
    "<blockquote><i>{actor} снял ваш мут - снова можете писать.</i></blockquote>{reason_suffix}"
  )
  CANCELLED_ADMIN = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Мут отменён</b>\n"
    "{player_line}\n{staff_line}{reason_suffix}\n"
    "<blockquote><b><i>{player_short} снова может писать.</i></b></blockquote>"
  )
  CANCELLED_GROUP_FOOTER = (
    "<blockquote><b><i>{actor} отменил мут - {player_short} снова может писать.</i></b></blockquote>"
  )
  CANCELLED_TITLE = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Мут отменён</b>"
  MANUAL_VIOLATOR = (
    "{greeting}\n{staff_line}"
    "<blockquote><i>{actor} снял ваш мут - снова можете писать.</i></blockquote>{reason_suffix}"
  )
  MANUAL_ADMIN = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Размут выполнен</b>\n"
    "{player_line}\n{staff_line}{reason_suffix}\n"
    "<blockquote><b><i>{player_short} снова может писать.</i></b></blockquote>"
  )
  MANUAL_GROUP_FOOTER = (
    "<blockquote><b><i>{actor} снял мут - {player_short} снова может писать.</i></b></blockquote>"
  )
  MANUAL_TITLE = "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Мут снят</b>"
  UNMUTE_GROUP = (
    "{group_title}\n{player_line}\n{staff_line}{chat_line}{reason_suffix}\n{group_footer}"
  )
  NOT_MUTED = (
    "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> {player_short} не в муте</b>\n"
    "{staff_line}\n{player_line}"
  )
  UNMUTE_DB_ERROR = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ошибка</b>"
  SYNC_NOTE = "\n<blockquote><i>Ограничение в чате было активно - снято вручную.</i></blockquote>"
  RESULT_TITLE_CANCELLED = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ограничение отменено</b>"
  RESULT_TITLE_DONE = "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Размут выполнен</b>"
  UNMUTE_RESULT = "{title}\n{staff_line}\n{player_line}{sync_note}"
  DB_REASON_CANCEL = "Отмена мута - {role_title} {admin_name}"
  DB_REASON_UNMUTE = "Размут - {role_title} {admin_name}"
  OTHER_PENDING = (
    "{greeting}\n"
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Другой нарушитель в ожидании</b>\n"
    "<b>Сейчас ожидается фото для:\n{pending_player_line}</b>\n\n"
    "<blockquote><i>Для отмены укажите именно {pending_player_short}:</i> "
    "<code>{cancel_hint}</code></blockquote>"
  )
  CANCEL_HELP = (
    "{greeting}\n{staff_line}\n{player_line}\n"
    "<b>Для отмены укажите, для кого отменяется ожидание:</b>\n"
    "<code>{cancel_hint}</code>\n\n"
    "<blockquote><i>Либо нажмите кнопку «Отменить ожидание» под сообщением о фото.</i></blockquote>"
  )
  STAFF_CHAT_EXCLUDED = (
    "{greeting}\n{staff_line}\n"
    "<blockquote><b>Команды мута, размута и кика недоступны в этой группе.</b></blockquote>\n"
    "<i>Остальные функции бота работают в обычном режиме.</i>"
  )
  STAFF_CHAT_ONLY = (
    "{greeting}\n{staff_line}\n"
    "<blockquote><b>Команды мута, размута и кика доступны только "
    "в официальных чатах проекта.</b></blockquote>"
  )
  PENDING_EXPIRED_GROUP = (
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Время ожидания истекло</b>\n"
    "{player_line}\n"
    "<tg-emoji emoji-id='6019107055699236857'>💬</tg-emoji> {chat_line}\n"
    "{reason_part}"
    "<blockquote><i>Наказание не применено - фото-доказательство не получено "
    "в течение {timeout} мин.</i></blockquote>"
  )
  PENDING_EXPIRED_ADMIN = (
    "{greeting}\n"
    "<b>время ожидания фото-доказательства истекло.</b>\n\n"
    "{player_line}\n"
    "<tg-emoji emoji-id='6019107055699236857'>💬</tg-emoji> {chat_line}\n"
    "{reason_part}"
    "<blockquote><i>Наказание <b>не применено</b> - фото-доказательство не было получено "
    "за {timeout} мин.</i></blockquote>"
  )
  CB_BAD_DATA = "Некорректные данные кнопки."
  CB_ONLY_AUTHOR = "Отменить ожидание может только {actor}."
  CB_NO_PERM = "Недостаточно прав."
  CB_DONE = "Ожидание уже завершено или истекло."
  CB_STALE = "Данные устарели. Используйте команду отмены."
  CB_WRONG_CHAT = "Действие недоступно в этой группе."
  CB_CANCELLED = "Ожидание отменено."
  CB_DB = "База данных временно недоступна - попробуйте позже."
  CB_REVOKED = "Мут снят."
  CB_NOT_MUTED = "Нарушитель уже не в муте."
  CB_REVOKE_FAILED = "Не удалось снять мут - попробуйте позже."
  CB_SELF_REVOKE = "Нельзя снять наказание с самого себя."
  REVOKED_EDIT = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Мут снят</b>\n"
    "{player_line}\n{staff_line}"
    "<blockquote><b><i>{player_short} снова может писать.</i></b></blockquote>"
  )


# =============================================================================
#  📋 ТЕКСТЫ СВОДКИ «НАКАЗАНИЯ» - единый список активных наказаний пользователя
# -----------------------------------------------------------------------------
#  Любой пользователь может посмотреть активные наказания: ответом на сообщение
#  + «наказания» / «твои наказания» / «ваши наказания», либо «наказания @user».
# =============================================================================
class PunishText:
  HEADER = (
    "<b><tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> Активные наказания</b>\n"
    "{player_line}\n"
  )
  NONE = (
    "<b><tg-emoji emoji-id='5260463209562776385'>✅</tg-emoji> Активных наказаний нет</b>\n"
    "{player_line}\n"
    "<blockquote><b><i>Нет активных мутов, банов и предупреждений.</i></b></blockquote>"
  )
  # --- Раздел мута ---
  MUTE_SECTION = (
    "\n<b><tg-emoji emoji-id='5454419255430767770'>🔇</tg-emoji> Мут</b>\n"
    "<blockquote><b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> "
    "До:</b> <code>{until}</code></blockquote>"
  )
  MUTE_HEADER = "\n<b><tg-emoji emoji-id='5454419255430767770'>🔇</tg-emoji> Муты</b>\n"
  MUTE_ITEM = (
    "<blockquote><b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> "
    "До:</b> <code>{until}</code>\n"
    "{chats}\n"
    "<b><tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> <b>Причина:</b> {reason}</blockquote>"
  )
  MUTE_CHAT = "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> {title}"
  MUTE_CHAT_ALL = (
    "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> во всех официальных группах"
  )
  # --- Раздел банов ---
  BAN_HEADER = "\n<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Блокировки</b>\n"
  BAN_ITEM = (
    "<blockquote><b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> "
    "До:</b> <code>{until}</code>\n"
    "{chats}\n"
    "<b><tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> Причина:</b> {reason}</blockquote>"
  )
  BAN_CHAT = "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> {title}"
  # --- Раздел предупреждений ---
  WARN_SECTION = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "Предупреждения</b>\n"
    "{rows}"
  )
  WARN_BREAKDOWN_CHAT = "<blockquote><b>В этой группе:</b> {count}/{total}</blockquote>"
  WARN_BREAKDOWN_ALL = "<blockquote><b>Во всех группах:</b> {count}/{total}</blockquote>"
  WARN_BREAKDOWN_FULL = "<blockquote><b>Во всём проекте:</b> {count}/{total}</blockquote>"
  WARN_ITEM = (
    "<blockquote><b>{idx}. {actor}</b>\n"
    "{where}"
    "<tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> {reason}\n"
    "<tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> {term}</blockquote>"
  )
  # Где выдан варн (кликабельная группа / охват). Пустая строка не ломает вид.
  WARN_WHERE_CHAT = "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> {group}\n"
  WARN_WHERE_ALL = (
    "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> все официальные группы\n"
  )
  WARN_WHERE_FULL = (
    "<tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> весь проект\n"
  )
  WARN_TERM_PERMANENT = "постоянное"
  WARN_TERM_TIMED = "до {until}"
  REASON_EMPTY = "не указана"
  NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Чьи наказания показать?</b>\n"
    "<b>Ответьте на сообщение нарушителя или напишите :</b> "
    "<code>наказания [username, id, имя]</code>"
  )


# =============================================================================
#  👮 ТЕКСТЫ СОСТАВА АДМИНИСТРАЦИИ - «кто админ» / «/staff» / «админ состав»
# -----------------------------------------------------------------------------
#  Любой пользователь может посмотреть список сотрудников по должностям.
# =============================================================================

class StaffRosterText:
  # ВАЖНО: здесь используются ТОЛЬКО обычные unicode-эмодзи (без <tg-emoji>).
  # Кастомные premium-эмодзи требуют валидный emoji-id, доступный боту; неверный
  # id приводит к ошибке «can't parse entities» и сообщение не отправляется вовсе.
  #
  # Дизайн - древовидный «орг-чарт»: заголовок, должности с эмодзи и участники
  # ветками (├/└), плюс точечный индикатор онлайна и компактный «живой» подвал.
  HEADER = "<b><tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji> ПЕРСОНАЛ ПРОЕКТА <tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji></b>"
  # Заголовок должности: ствол дерева (┏) + эмодзи + название (+ старшинство).
  ROLE_HEADER = "\n\n<code>┏</code> {emoji} <b>{role}{imp}</b>"
  # Число старшинства внутри названия должности (из staff_rules.importance): «(5)».
  ROLE_IMPORTANCE = " ({n})"
  # Строка участника: ветка дерева + статус + ссылка (+ заметка).
  MEMBER_LINE = "\n<code>{branch}</code> {status} {member}{note}"
  # Подстрока-«хвостик» под участником («был N назад») с вертикальным рельсом.
  HINT_LINE = "\n<code>{rail}</code> <i>{hint}</i>"
  # Пустая должность (нет назначенных) - деликатный плейсхолдер (обычно не виден).
  ROLE_EMPTY_LINE = "\n<code>┗</code> <i>- вакантно</i>"
  # Ветви дерева (box-drawing «heavy»): связь и завершение ветки.
  BRANCH_MID = "┣"
  BRANCH_END = "┗"
  # Вертикальные «рельсы» для подстрок-хвостиков: продолжение / конец.
  RAIL_MID = "┃"
  RAIL_END = " "
  # Подсказки под составом (выбираются по ROSTER_SHOW_ROLE_BUTTONS):
  #   • TAP_HINT_ALL   - одна кнопка «Все права»;
  #   • TAP_HINT_ROLES - кнопки по каждой должности.
  TAP_HINT_ALL = "\n\n<i>Нажмите «Все права» - что может каждая должность</i>"
  TAP_HINT_ROLES = "\n\n<i>Нажмите должность ниже - покажу её права</i>"
  # Подвал: легенда + статус живого обновления.
  FOOTER_LIVE = (
    "\n\n<blockquote><i><tg-emoji emoji-id='5339112148175959615'>🟢</tg-emoji> в сети · <tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji> недавно · <tg-emoji emoji-id='5339113303522161846'>⚪️</tg-emoji> не в сети · <tg-emoji emoji-id='5336936725765700868'>🟠</tg-emoji> не на смене</i>\n"
    "<i>{pulse} обновляется каждые 2 минуты · {time}</i></blockquote>"
  )
  FOOTER_STATIC = (
    "\n\n<blockquote><i><tg-emoji emoji-id='5339112148175959615'>🟢</tg-emoji> в сети · <tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji> недавно · <tg-emoji emoji-id='5339113303522161846'>⚪️</tg-emoji> не в сети · <tg-emoji emoji-id='5336936725765700868'>🟠</tg-emoji> не на смене</i>\n"
    "<i>обновлено в {time} · для точной информации напишите «кто админ» ещё раз</i></blockquote>"
  )
  # Метки статуса активности.
  STATUS_ONLINE = "<tg-emoji emoji-id='5339112148175959615'><tg-emoji emoji-id='5339112148175959615'>🟢</tg-emoji></tg-emoji>"
  STATUS_RECENT = "<tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji>"
  STATUS_OFFLINE = "<tg-emoji emoji-id='5339113303522161846'>⚪️</tg-emoji>"
  STATUS_AWAY = "<tg-emoji emoji-id='5336936725765700868'>🟠</tg-emoji>"
  # Кадры «пульса» живого индикатора (чередуются между обновлениями).
  PULSE_FRAMES = ("◍", "◌")
  EMPTY = (
    "<b><tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji> ПЕРСОНАЛ ПРОЕКТА <tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji></b>\n"
    "<blockquote><b><i>Сейчас нет назначенных сотрудников.</i></b></blockquote>"
  )
  UNAVAILABLE = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Список сотрудников временно недоступен - попробуйте позже.</b>"
  )


# =============================================================================
#  ЭМОДЗИ ДОЛЖНОСТЕЙ - СТРОГО по таблице staff_rules.
# -----------------------------------------------------------------------------
#  Эмодзи должности определяется ТОЛЬКО её уровнем - столбцом importance в
#  таблице staff_rules (1..5). Подбора по названию роли нет.
#
#  Каждый эмодзи задаётся парой (plain, custom_id):
#    • plain     - обычный unicode-эмодзи (показывается на кнопках и как фолбэк);
#    • custom_id - id премиум-эмодзи Telegram (или None для обычного эмодзи).
# =============================================================================

# -----------------------------------------------------------------------------
#  ЛЕСТНИЦА СТАРШИНСТВА (по staff_rules.importance): чем выше уровень - тем
#  «весомее» эмодзи. Глаз сразу считывает иерархию:
#    1 · 🔹 мелкая роль (минимум прав)      →  маленький синий ромб
#    2 · 🔸 чуть выше                        →  ромб покрупнее (оранжевый)
#    3 · 💠 средняя                          →  огранённый ромб
#    4 · 💎 высокая                          →  бриллиант (ценность/сила)
#    5 · 👑 высшая роль, даёт всё            →  корона
#  Это ОСНОВНОЙ источник эмодзи: он привязан к уровню, а не к названию роли.
#  Меняйте свободно - порядок «растёт» слева направо по ценности.
# -----------------------------------------------------------------------------
_LEVEL_EMOJI: Dict[int, Tuple[str, Optional[str]]] = {
  1: ("🔹", "5393514467394875868"),
  2: ("🔸", "4958900559139570572"),
  3: ("💠", "5402366352042252021"),
  4: ("💎", "5296491512660534111"),
  5: ("👑", "5305629674058061875"),
}

# Эмодзи, когда у должности НЕ задан уровень (importance пуст в staff_rules).
_ROLE_EMOJI_DEFAULT: Tuple[str, Optional[str]] = ("🔹", "5391006515731659274")


def _emoji_html(plain: str, custom_id: Optional[str]) -> str:
  """HTML-представление эмодзи: премиум <tg-emoji> при наличии id, иначе обычный."""
  if custom_id:
    return f"<tg-emoji emoji-id='{custom_id}'>{plain}</tg-emoji>"
  return plain


def _level_emoji_parts(importance: Optional[int]) -> Optional[Tuple[str, Optional[str]]]:
  """Эмодзи по уровню старшинства (1..5). None - если уровень не задан."""
  if importance is None:
    return None
  level = max(1, min(5, int(importance)))
  return _LEVEL_EMOJI.get(level)


def _role_emoji_parts(role_key: str, title: str) -> Tuple[str, Optional[str]]:
  """Подбирает (plain, custom_id) эмодзи должности СТРОГО по staff_rules.

  Эмодзи определяется только уровнем должности - столбцом importance в таблице
  staff_rules (1..5). Никакого подбора по названию роли нет. Если уровень не
  задан в таблице - используется нейтральный дефолт.
  """
  by_level = _level_emoji_parts(_role_importance(role_key))
  if by_level is not None:
    return by_level
  return _ROLE_EMOJI_DEFAULT


def _role_emoji(role_key: str, title: str) -> str:
  """HTML-эмодзи должности (для текста сообщения, с premium-эмодзи)."""
  plain, custom_id = _role_emoji_parts(role_key, title)
  return _emoji_html(plain, custom_id)


def _role_emoji_plain(role_key: str, title: str) -> str:
  """Обычный unicode-эмодзи должности (для текста инлайн-кнопок)."""
  return _role_emoji_parts(role_key, title)[0]


# =============================================================================
#  ПРАВА ДОЛЖНОСТЕЙ - карточка «что может делать должность».
# -----------------------------------------------------------------------------
#  Каждая способность сопоставлена со столбцом staff_rules. Значение 1 → можно
#  (✅), 0 → нельзя (❌). Показываются ТОЛЬКО столбцы, которые реально есть в
#  таблице (определяется интроспекцией схемы). Список легко расширять/править.
#    (column, emoji, короткое имя, краткое пояснение)
# =============================================================================
_PERMISSION_DISPLAY: Tuple[Tuple[str, str, str, str], ...] = (
  ("mute",     "<tg-emoji emoji-id='6023965819057217444'>🔇</tg-emoji>", "Мут",      "запрещает писать в определенной официальной группе"),
  ("muteall",  "<tg-emoji emoji-id='5843462551358148756'>🔇</tg-emoji>", "Муталл",   "запрещает писать во всех официальных группах"),
  ("unmute",   "<tg-emoji emoji-id='5260325873688518261'>🔊</tg-emoji>", "Размут",   "снимает мут раньше срока"),
  ("kick",     "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji>", "Кик",      "удаляет участника из определенной официальной группы"),
  ("kickall",  "<tg-emoji emoji-id='5397773700562960960'>🪖</tg-emoji>", "Кикалл",   "удаляет участника со всех официальных групп"),
  ("warn",     "<tg-emoji emoji-id='5213181173026533794'>⚠️</tg-emoji>", "Варн",     "выдаёт предупреждение в определенной группе"),
  ("warnall",  "<tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji>", "Варналл",  "выдаёт предупреждение во всех официальных группах"),
  ("warnfull", "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji>", "Варнфулл", "предупреждение с угрозой блокировки во всём проекте"),
  ("ban",      "<tg-emoji emoji-id='4956337889593000947'>🚫</tg-emoji>", "Бан",      "блокирует участника в определенной официальной группе"),
  ("banall",   "<tg-emoji emoji-id='5472267631979405211'>🚫</tg-emoji>", "Баналл",   "блокирует во всех официальных группах"),
  ("banfull",  "<tg-emoji emoji-id='5379979620990870060'>🤩</tg-emoji>", "Банфулл",  "полная блокировка во всём проекте"),
)


class StaffPermsText:
  """Тексты карточек прав должностей («права админов» / детали по кнопке).

  Принцип: показываем ТОЛЬКО то, что должность реально умеет. Недоступные
  действия не перечисляются вовсе - карточка остаётся чистой и понятной.
  """
  TITLE = "<b><tg-emoji emoji-id='5373346752671804066'>👑</tg-emoji> ПРАВА ДОЛЖНОСТИ</b>"
  ALL_TITLE = "<b><tg-emoji emoji-id='5373346752671804066'>👑</tg-emoji> ПРАВА ПЕРСОНАЛА</b>"
  # Заголовок должности внутри карточки: эмодзи + название + «уровень N».
  ROLE_LINE = "{emoji} <b>{title}</b>{imp}"
  ROLE_IMPORTANCE = " <i>· уровень {n}</i>"
  # Подзаголовок перед списком доступных действий.
  SUBTITLE = "<i>Доступные действия:</i>"
  # Строки способностей (ветви дерева, как в составе): средняя / последняя.
  CAP_MID = "<code>┣</code> {emoji} <b>{name}</b> <i>- {desc}</i>"
  CAP_END = "<code>┗</code> {emoji} <b>{name}</b> <i>- {desc}</i>"
  # Тихий итог снизу.
  COUNT = "<blockquote><i>Доступно действий: {n}</i></blockquote>"
  NO_RULES = "<blockquote><i>Для этой должности ещё не настроены правила доступа.</i></blockquote>"
  NO_PERMS = "<blockquote><i>Должность без полномочий модерации.</i></blockquote>"
  # Обзор «права админов»: компактная строка доступных действий под должностью.
  ALL_HINT = "<blockquote><i>Кто и что может делать в проекте.</i></blockquote>"
  ALL_ALLOWED = "<blockquote>{caps}</blockquote>"
  ALL_NONE = "<blockquote><i>без прав модерации</i></blockquote>"
  # ✏️ Примечание под обзором прав - легко менять текст.
  # Показывается внизу карточки «Все права». Доступ к админ-панели - общий для всех
  # сотрудников проекта, поэтому выносим это отдельной заметкой (а не в каждую роль).
  ADMIN_PANEL_NOTE = (
    "\n<blockquote><tg-emoji emoji-id='5390858914885568318'>👑</tg-emoji> <b>Каждый сотрудник получает доступ к "
    "админ-панели проекта - <i>для удобства в процессе администрации.</i></b>"
    "</blockquote>"
  )
  ALL_EMPTY = (
    "<b><tg-emoji emoji-id='5373346752671804066'>👑</tg-emoji> ПРАВА ПЕРСОНАЛА</b>\n"
    "<blockquote><i>Должности и правила доступа ещё не настроены.</i></blockquote>"
  )
  # Кнопки (короткие и интуитивные).
  BTN_BACK = "К составу"
  BTN_ALL = "Все права"
  # Алерты колбэков.
  CB_ONLY_AUTHOR = "Эти кнопки - для того, кто открыл список 🙂"
  CB_STALE = "Список обновился - откройте «кто админ» заново."
  CB_UNAVAILABLE = "Список прав временно недоступен."


def _current_staff_schema() -> "StaffRulesSchema":
  """Текущая схема staff_rules из кэша (или пустая, если кэш не прогрет)."""
  if _staff_rules_cache:
    return _staff_rules_cache[1]
  return StaffRulesSchema("roles", "description", ())


def _rule_column_state(
  rule: "StaffRuleRecord",
  schema: "StaffRulesSchema",
  column: str,
) -> Tuple[bool, bool]:
  """(present, allowed) для столбца права: present - есть ли столбец в схеме."""
  cols_lower = {c.lower(): c for c in schema.permission_columns}
  actual = cols_lower.get(column.lower())
  if not actual:
    return False, False
  return True, bool(rule.permissions.get(actual))


def _role_caps(role_key: str) -> Optional[List[Tuple[str, str, str, bool]]]:
  """Список способностей должности: (emoji, name, desc, allowed).

  Возвращает None, если правил для должности нет вовсе. В список попадают только
  способности, чьи столбцы реально присутствуют в таблице staff_rules.
  """
  rule = _role_rule(role_key)
  if not rule:
    return None
  schema = _current_staff_schema()
  caps: List[Tuple[str, str, str, bool]] = []
  for column, emoji, name, desc in _PERMISSION_DISPLAY:
    present, allowed = _rule_column_state(rule, schema, column)
    if not present:
      continue
    caps.append((emoji, name, desc, allowed))
  return caps


def _role_perms_card(role_key: str) -> str:
  """HTML-карточка прав одной должности: ТОЛЬКО доступные действия, деревом."""
  title = role_title_from_cache(role_key)
  imp = _role_importance(role_key)
  imp_html = StaffPermsText.ROLE_IMPORTANCE.format(n=imp) if imp is not None else ""
  parts: List[str] = [
    StaffPermsText.TITLE,
    "",
    StaffPermsText.ROLE_LINE.format(
      emoji=_role_emoji(role_key, title), title=escape(title), imp=imp_html,
    ),
  ]
  caps = _role_caps(role_key)
  if caps is None:
    parts += ["", StaffPermsText.NO_RULES]
    return "\n".join(parts)
  # Показываем ТОЛЬКО доступные действия; недоступные не перечисляем.
  allowed = [c for c in caps if c[3]]
  if not allowed:
    parts += ["", StaffPermsText.NO_PERMS]
    return "\n".join(parts)
  parts += ["", StaffPermsText.SUBTITLE]
  last = len(allowed) - 1
  for i, (emoji, name, desc, _ok) in enumerate(allowed):
    tmpl = StaffPermsText.CAP_END if i == last else StaffPermsText.CAP_MID
    parts.append(tmpl.format(emoji=emoji, name=escape(name), desc=escape(desc)))
  parts += ["", StaffPermsText.COUNT.format(n=len(allowed))]
  return "\n".join(parts)


def _all_perms_card() -> str:
  """HTML-обзор «права админов»: все должности и их доступные действия."""
  rules: Dict[str, "StaffRuleRecord"] = _staff_rules_cache[0] if _staff_rules_cache else {}
  if not rules:
    return StaffPermsText.ALL_EMPTY
  order = sorted(
    rules.keys(),
    key=lambda rk: (-_role_sort_weight(rk), role_title_from_cache(rk).lower()),
  )
  parts: List[str] = [StaffPermsText.ALL_TITLE, StaffPermsText.ALL_HINT]
  for role_key in order:
    title = role_title_from_cache(role_key)
    imp = _role_importance(role_key)
    imp_html = StaffPermsText.ROLE_IMPORTANCE.format(n=imp) if imp is not None else ""
    parts.append("")
    parts.append(StaffPermsText.ROLE_LINE.format(
      emoji=_role_emoji(role_key, title), title=escape(title), imp=imp_html,
    ))
    caps = _role_caps(role_key)
    allowed = [c for c in (caps or []) if c[3]]
    if not allowed:
      parts.append(StaffPermsText.ALL_NONE)
      continue
    # Для каждой должности перечисляем доступные действия деревом и поясняем,
    # что именно делает каждая функция (мут, бан, баналл и т.д.).
    cap_lines: List[str] = []
    last = len(allowed) - 1
    for i, (emoji, name, desc, _ok) in enumerate(allowed):
      branch = "┗" if i == last else "┣"
      cap_lines.append(
        f"<code>{branch}</code> {emoji} <b>{escape(name)}</b> <i>- {escape(desc)}</i>"
      )
    parts.append(StaffPermsText.ALL_ALLOWED.format(caps="\n".join(cap_lines)))
  # Общая заметка про доступ к админ-панели (одинакова для всех должностей).
  parts.append(StaffPermsText.ADMIN_PANEL_NOTE)
  return "\n".join(parts)


def _sanitize_username(raw: Any) -> Optional[str]:
  """Чистит username до валидного для ссылки t.me (буквы/цифры/_, 4..32)."""
  if not raw:
    return None
  u = str(raw).strip().lstrip("@")
  if _TELEGRAM_USERNAME_RE.match(u):
    return u
  return None


def _roster_member_link(row: Dict[str, Any], uid: int) -> str:
  """Кликабельное ИМЯ участника - нажатие открывает профиль пользователя.

  Показываем именно имя (first_name), а не @username. Ссылка ведёт в профиль:
  t.me/username при наличии, иначе tg://user?id. Если имени нет - подставляется
  @username, и лишь в самом крайнем случае - голый ID.
  """
  username = _sanitize_username(_row_value(row, "username", "user_name"))
  name = (str(_row_value(row, "first_name", "name") or "")).strip()
  return _display_name_link(uid, name, username)


def _roster_member_note(row: Dict[str, Any], role_title: str) -> str:
  """Опциональная персональная подпись « » заметка», если такой столбец есть."""
  note = _row_value(row, "note", "comment", "post", "label", "title", "prefix", "description")
  if note is None:
    return ""
  text = str(note).strip()
  if not text or text.lower() == (role_title or "").lower():
    return ""
  return f" <i>» {escape(text)}</i>"


class LiveRosterConfig:
  """Параметры живого обновления состава администрации.

  Обновление статусов сделано ЛЁГКИМ: правка сообщения раз в минуту (а не каждые
  пару секунд). Перерисовка берёт данные из памяти - БД при тиках не трогается,
  Telegram-правок мало, нагрузка на систему минимальна.
  """
  # ⚙️ Период обновления статусов (сек). Сейчас - раз в 2 минуты (легко и не грузит).
  # Можно увеличить ещё - будет реже/легче.
  REFRESH_SEC: float = 120.0
  # ⚙️ Максимум обновлений сообщения. После этого правки прекращаются и
  # вставляется финальная подсказка «напишите кто админ ещё раз». 20 правок по
  # 2 минуты ≈ 40 минут «живого» сообщения.
  MAX_UPDATES: int = 20
  # Страховочная граница по времени (на случай зависаний): чуть больше, чем
  # MAX_UPDATES * REFRESH_SEC. Обычно цикл останавливается по числу обновлений.
  WINDOW_SEC: float = 3000.0
  # Максимум одновременных живых сессий (по одной на чат; защита от перегрузки).
  MAX_CONCURRENT: int = 6
  # Сколько подряд неудачных правок терпим, прежде чем остановить сессию.
  MAX_EDIT_FAILURES: int = 3
  # Часовой пояс отметки времени в подвале (проект работает в UTC+3).
  TZ = timezone(timedelta(hours=3))


_INVALID_CHAT_STRINGS = frozenset({
  "", "нет", "none", "null",
  "username отсутствует", "приватная ссылка не найдена",
})

_pending_mutes: Dict[int, Dict[str, Any]] = LazyGameStore("_pending_mutes")
_chat_mutes: Dict[Tuple[int, int], datetime] = LazyGameStore("_chat_mutes")
# Анти-дубликат уведомлений об авто-размуте: user_id → monotonic-время последней
# отправки. Несколько фоновых триггеров могут «поймать» истёкший мут почти
# одновременно - гарантируем единственное сообщение на снятие.
_recent_auto_unmute: Dict[int, float] = LazyGameStore("_recent_auto_unmute")
_AUTO_UNMUTE_DEDUP_SEC = 90.0
_admin_account_cache: Dict[int, Tuple["AdminAccount", float]] = LazyGameStore("_admin_account_cache")
_staff_rules_cache: Optional[Tuple[Dict[str, "StaffRuleRecord"], "StaffRulesSchema", float]] = None
_expiry_worker_started = False
_mute_system_attached = False
_schema_ready = False
_mute_maintenance_last = 0.0
_MUTE_MAINTENANCE_INTERVAL_SEC = 5.0

# Активность сотрудников - момент последнего сообщения, замеченного ботом.
#
# МОДЕЛЬ (как просил пользователь): «онлайн по факту переписки».
# Любое сообщение администратора - в любой группе, где есть бот, или в личке с
# ботом, любого типа (текст/фото/стикер/голос и т.д.) - фиксирует момент его
# активности. После этого администратор считается «в сети» ещё ACTIVITY_ONLINE_SEC
# секунд (≈1 минута), затем некоторое время «недавно был», затем «не в сети».
#
# Bot API НЕ отдаёт реальный онлайн-статус Telegram, поэтому это самый честный и
# предсказуемый способ: статус отражает реальную работу администратора с ботом.
# Хранилище в памяти (сбрасывается при рестарте - это корректно: сразу после
# перезапуска никто не «в сети», пока снова не напишет сообщение).
_admin_last_active: Dict[int, float] = LazyGameStore("_admin_last_active")
_ADMIN_LAST_ACTIVE_MAX = 10000
# UID'ы, по которым Telegram возвращал "chat not found".
# Чтобы не спамить сеть/логи, повторную проверку делаем только через TTL.
_staff_tg_identity_retry_at: Dict[int, float] = {}
_STAFF_TG_IDENTITY_RETRY_SEC = 6 * 60 * 60
# Пороги статусов активности (секунды):
#   ≤ ONLINE  → 🟢 в сети   (активен прямо сейчас, ~минуту после сообщения)
#   ≤ RECENT  → 🟡 недавно   (был активен совсем недавно)
#   иначе     → ⚪ не в сети
_ACTIVITY_ONLINE_SEC = 60          # 1 минута «в сети» после сообщения
_ACTIVITY_RECENT_SEC = 10 * 60     # до 10 минут - «недавно был»

# --- Лёгкая персистентность активности (чтобы статус переживал рестарт) ---
# Множество известных администраторов: только для них пишем активность в БД,
# чтобы не плодить запись на каждого обычного пользователя.
_known_admin_ids: set = set()
# Когда в последний раз активность uid была записана в БД (тротлинг записи).
_admin_last_persisted: Dict[int, float] = LazyGameStore("_admin_last_persisted")
# ⚙️ Не чаще одной записи в БД на администратора раз в N секунд - это делает
# нагрузку на БД пренебрежимо малой даже при очень активной переписке.
# (Запись идёт в фоне, не блокируя обработку сообщения.)
_ACTIVITY_PERSIST_THROTTLE_SEC = 60.0
_activity_schema_ready = False
_activity_loaded_from_db = False
# Как хранится admin_activity.slot в конкретной БД (кэш после introspection).
_activity_slot_kind: Optional[str] = None  # 'timestamptz' | 'numeric'


def _slot_to_timestamp(raw: Any) -> Optional[float]:
  """Преобразует значение столбца slot в unix-timestamp (секунды).

  Поддерживает TIMESTAMPTZ/TIMESTAMP, BIGINT/INTEGER (секунды или миллисекунды).
  """
  if raw is None:
    return None
  if isinstance(raw, datetime):
    dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    return dt.timestamp()
  if isinstance(raw, (int, float)):
    v = float(raw)
    if v > 1e11:  # похоже на миллисекунды
      return v / 1000.0
    return v
  return None


async def _resolve_activity_slot_kind(conn) -> str:
  """Определяет тип admin_activity.slot (один раз, с кэшем)."""
  global _activity_slot_kind
  if _activity_slot_kind:
    return _activity_slot_kind
  row = await conn.fetchrow(
    """
    SELECT data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'admin_activity'
      AND column_name = 'slot'
    """,
  )
  if row and row["data_type"] in (
    "bigint", "integer", "smallint", "numeric", "double precision", "real",
  ):
    _activity_slot_kind = "numeric"
  else:
    _activity_slot_kind = "timestamptz"
  return _activity_slot_kind


def _track_known_admin(user_id: Optional[int]) -> None:
  """Помечает uid как администратора (для выборочной персистентности активности)."""
  if user_id:
    _known_admin_ids.add(int(user_id))


async def _upsert_activity_slot(conn, user_id: int, ts: float) -> None:
  """Записывает slot для admin_user_id без ON CONFLICT (таблица может быть без PK)."""
  kind = await _resolve_activity_slot_kind(conn)
  uid = int(user_id)
  if kind == "numeric":
    slot_val = int(ts)
    row = await conn.fetchrow(
      """
      UPDATE admin_activity
      SET slot = $2::bigint
      WHERE admin_user_id = $1
      RETURNING admin_user_id
      """,
      uid, slot_val,
    )
    if not row:
      await conn.execute(
        """
        INSERT INTO admin_activity (admin_user_id, slot)
        VALUES ($1, $2::bigint)
        """,
        uid, slot_val,
      )
  else:
    row = await conn.fetchrow(
      """
      UPDATE admin_activity
      SET slot = to_timestamp($2)
      WHERE admin_user_id = $1
      RETURNING admin_user_id
      """,
      uid, float(ts),
    )
    if not row:
      await conn.execute(
        """
        INSERT INTO admin_activity (admin_user_id, slot)
        VALUES ($1, to_timestamp($2))
        """,
        uid, float(ts),
      )


async def _persist_activity(user_id: int, ts: float) -> None:
  """Тротлинг-запись активности администратора в admin_activity (upsert).

  Использует реальную схему таблицы: admin_user_id + slot.
  Тип slot определяется автоматически (TIMESTAMPTZ или числовой unix-time).
  """
  try:
    if not await _ensure_activity_schema():
      return
    async with _db_acquire() as conn:
      await _upsert_activity_slot(conn, user_id, ts)
  except Exception as e:
    MuteDebug.log("ACT", "persist skip", err=str(e))


def note_admin_activity(user_id: Optional[int]) -> None:
  """Фиксирует активность пользователя.

  Вызывается из middleware на КАЖДОЕ входящее сообщение (любой чат, любой тип),
  поэтому ловит и группы, и личные сообщения с ботом. В памяти - мгновенно;
  в БД - с тротлингом и только для известных администраторов (минимум нагрузки).
  """
  if not user_id:
    return
  now = time.time()
  _admin_last_active[user_id] = now
  # Ограничиваем размер словаря, отбрасывая самые старые записи.
  if len(_admin_last_active) > _ADMIN_LAST_ACTIVE_MAX:
    for uid, _ts in sorted(_admin_last_active.items(), key=lambda kv: kv[1])[:1000]:
      _admin_last_active.pop(uid, None)
  # Персистим активность редко и только для админов - чтобы не грузить БД.
  if user_id in _known_admin_ids:
    if now - _admin_last_persisted.get(user_id, 0.0) >= _ACTIVITY_PERSIST_THROTTLE_SEC:
      _admin_last_persisted[user_id] = now
      try:
        asyncio.create_task(_persist_activity(user_id, now))
      except RuntimeError:
        pass  # нет активного event loop - пропускаем запись


async def _ensure_activity_schema() -> bool:
  """Гарантирует наличие таблицы admin_activity (admin_user_id + slot).

  Если таблица уже есть в БД - не пересоздаём, только проверяем столбец slot.
  """
  global _activity_schema_ready
  if _activity_schema_ready:
    return True
  pool = _db().pool
  if not pool:
    return False
  try:
    async with _db_acquire() as conn:
      exists = await conn.fetchval(
        "SELECT to_regclass('public.admin_activity') IS NOT NULL",
      )
      if not exists:
        await conn.execute(
          """
          CREATE TABLE admin_activity (
            admin_user_id BIGINT      PRIMARY KEY,
            slot          TIMESTAMPTZ NOT NULL
          )
          """,
        )
      else:
        has_slot = await conn.fetchval(
          """
          SELECT 1
          FROM information_schema.columns
          WHERE table_schema = 'public'
            AND table_name = 'admin_activity'
            AND column_name = 'slot'
          """,
        )
        if not has_slot:
          MuteDebug.log("ACT", "schema skip", err="admin_activity.slot missing")
          return False
        # Ускоряет upsert на новых установках; на старой схеме не обязателен.
        try:
          await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS admin_activity_admin_user_id_uidx
            ON admin_activity (admin_user_id)
            """,
          )
        except Exception:
          pass
    _activity_schema_ready = True
    return True
  except Exception as e:
    MuteDebug.log("ACT", "schema skip", err=str(e))
    return False


async def _load_activity_from_db(ids: List[int]) -> None:
  """Подтягивает сохранённую активность администраторов в память (один раз).

  После рестарта это позволяет сразу видеть, кто был активен недавно, не дожидаясь
  нового сообщения. В память кладём только если запись из БД свежее, чем в памяти.
  """
  global _activity_loaded_from_db
  if not ids:
    return
  if not await _ensure_activity_schema():
    return
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        "SELECT admin_user_id, slot FROM admin_activity WHERE admin_user_id = ANY($1::bigint[])",
        [int(x) for x in ids],
      )
  except Exception as e:
    MuteDebug.log("ACT", "load skip", err=str(e))
    return
  for r in rows:
    try:
      uid = int(r["admin_user_id"])
    except (TypeError, ValueError, KeyError):
      continue
    ts = _slot_to_timestamp(r.get("slot"))
    if ts is None:
      continue
    if ts > _admin_last_active.get(uid, 0.0):
      _admin_last_active[uid] = ts
  _activity_loaded_from_db = True


async def _warm_activity_state() -> None:
  """Разовый прогрев при старте: список админов + их сохранённая активность.

  Благодаря этому персистентность активности работает с первого же сообщения,
  а статусы «в сети/недавно» корректны сразу после рестарта (а не с нуля).
  Делает несколько попыток, пока поднимается пул БД.
  """
  for _ in range(10):
    try:
      _groups, ids = await _load_staff_groups()
    except Exception as e:
      MuteDebug.log("ACT", "warm skip", err=str(e))
      ids = []
    if ids:
      MuteDebug.log("ACT", "warm done", admins=len(ids))
      return
    await asyncio.sleep(3)

# Права Telegram: полный запрет писать в группе
_PERM_MUTE = ChatPermissions(
  can_send_messages=False,
  can_send_media_messages=False,
  can_send_polls=False,
  can_send_other_messages=False,
  can_add_web_page_previews=False,
)
_PERM_FULL = ChatPermissions(
  can_send_messages=True,
  can_send_media_messages=True,
  can_send_polls=True,
  can_send_other_messages=True,
  can_add_web_page_previews=True,
)

_DURATION_UNITS: Tuple[Tuple[str, ...], str] = (
    (("секунд", "секунды", "секунда", "second", "seconds", "сек", "sec"), "seconds"),
    (("минут", "минуты", "минута", "minute", "minutes", "мин", "min"), "minutes"),
    (("месяц", "месяца", "месяцев", "month", "months", "mouth", "мес", "mo"), "months"),
    (("часов", "часа", "час", "hour", "hours", "ч", "hr", "h"), "hours"),
    (("дней", "дня", "день", "days", "day", "дн", "д"), "days"),
    (("лет", "года", "год", "years", "year", "г", "y", "yr"), "years"),
    (("вечность", "forever", "permanent", "perm"), "forever"),
)

_COMPACT_DURATION_RE = re.compile(
    r"^(\d+)\s*("
    r"сек|секунд|секунды|секунда|с|s|sec|second|seconds|"
    r"мин|минут|минуты|минута|min|minute|minutes|"
    r"мес|месяц|месяца|месяцев|month|months|mouth|mo|"
    r"час|часа|часов|ч|h|hr|hour|hours|"
    r"день|дня|дней|д|day|days|"
    r"год|года|лет|г|y|yr|year|years|"
    r"вечность|forever|perm|permanent"
    r")$",
    re.IGNORECASE,
)
_COMPACT_MINUTE_RE = re.compile(r"^(\d+)\s*м$", re.IGNORECASE)
_COMPACT_MINUTE_LATIN_RE = re.compile(r"^(\d+)\s*m$", re.IGNORECASE)
_CANCEL_MUTE_RE = re.compile(r"^(?:отмена|отменить)\s+(?:мут|мута)\b", re.IGNORECASE)
# Фразовые команды размута: «снять мут @user», «убрать мутить user»
_UNMUTE_PHRASE_RE = re.compile(
  r"^(?:"
  r"снять\s+мут(?:ить)?|"
  r"убрать\s+мут(?:ить)?|"
  r"отключить\s+мут(?:ить)?|"
  r"снять\s+ограничение"
  r")\b",
  re.IGNORECASE,
)
# Telegram username: 5–32 символа, латиница/цифры/_, начинается с буквы
_TELEGRAM_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")

# Команда «наказания» - единая сводка активных наказаний (доступна всем).
_PUNISH_CMD_WORDS: frozenset = frozenset({
  "наказания", "наказание", "punishments", "/punishments", "/наказания",
  "моинаказания", "твоинаказания", "вашинаказания", "mypunishments", "/mypunishments",
})
# Фразовые формы: «мои/твои/ваши/его/её наказания», а также синонимы по видам
# наказаний: «мои муты», «мои баны», «мои варны», «мои предупреждения», «мои кики».
# Все они показывают единую сводку активных наказаний пользователя.
_PUNISH_PHRASE_RE = re.compile(
  r"^(?:мои|твои|ваши|его|её|ее|их)\s+"
  r"(?:наказани[яе]|"
  r"мут(?:ы|ов|а)?|"
  r"бан(?:ы|ов|а)?|"
  r"варн(?:ы|ов|а)?|"
  r"кик(?:и|ов|а)?|"
  r"пред(?:ы|упреждени[йяе])?)\b",
  re.IGNORECASE,
)

# Команда «состав администрации»: «кто админ», «/staff», «админ состав» и т.п.
# Доступна всем пользователям.
_STAFF_ROSTER_CMD_WORDS: frozenset = frozenset({
  "/staff", "staff", "/админы", "/админсостав", "/состав",
  "админы", "администрация", "админсостав", "админ-состав",
})
_STAFF_ROSTER_PHRASE_RE = re.compile(
  r"^(?:"
  r"кто\s+(?:тут\s+|здесь\s+|у\s+нас\s+|из\s+)?админ(?:ы|ов|истратор(?:ы|ов)?)?|"
  r"админ(?:ский)?\s+состав|"
  r"состав\s+админ(?:ов|истрации)?|"
  r"список\s+админ(?:ов|истраторов)?|"
  r"кто\s+(?:в\s+)?(?:администрации|админке|персонал[еа])|"
  r"персонал\s+проекта"
  r")\b",
  re.IGNORECASE,
)

# Команда «права админов» - обзор полномочий должностей. Доступна всем.
_STAFF_PERMS_CMD_WORDS: frozenset = frozenset({
  "/rights", "/perms", "/permissions", "/права", "праваадминов",
  "праваадмина", "правадолжностей", "праваперсонала",
})
_STAFF_PERMS_PHRASE_RE = re.compile(
  r"^(?:"
  r"права\s+(?:админ(?:а|ов|истратор(?:а|ов)?)?|должност(?:и|ей)|персонала|ролей|роли)|"
  r"какие\s+права\s+(?:у\s+)?админ|"
  r"что\s+мож(?:ет|но)\s+(?:делать\s+)?админ|"
  r"полномочия\s+(?:админ(?:ов)?|должност(?:и|ей)|персонала)"
  r")\b",
  re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Отладка
# ---------------------------------------------------------------------------

class MuteDebug:
  @staticmethod
  def log(stage: str, detail: str, **fields: Any) -> None:
    if not cfg.DEBUG:
      return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items()) if fields else ""
    line = f"[MUTE][{stage}] {detail}" + (f" | {extra}" if extra else "")
    print(line)
    try:
      with open(cfg.LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception as e:
      print(f"[MUTE][LOGFILE] write error: {e}")

  @staticmethod
  def error(stage: str, detail: str, exc: Optional[BaseException] = None, **fields: Any) -> None:
    tb = traceback.format_exc() if exc else ""
    MuteDebug.log(stage, f"ERROR: {detail}", **fields)
    if tb:
      print(tb)
      try:
        with open(cfg.LOG_FILE, "a", encoding="utf-8") as fh:
          fh.write(tb + "\n")
      except Exception:
        pass


def _bot():
  from main import bot1
  return bot1


def _db():
  from main import db
  return db


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _to_utc(dt: datetime) -> datetime:
  """Приводит datetime к UTC-aware - для сравнения naive (БД) и aware (Telegram)."""
  if dt.tzinfo is None:
    return dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(timezone.utc)


def _is_datetime_active(until: datetime, *, now: Optional[datetime] = None) -> bool:
  return _to_utc(until) > _to_utc(now or _utc_now())


# ---------------------------------------------------------------------------
# Парсинг
# ---------------------------------------------------------------------------

@dataclass
class ParsedMute:
  target_id: int
  target_name: str
  target_username: Optional[str]
  duration_text: str
  time_delta: timedelta
  duration_minutes: int
  mute_until: datetime
  reason: str
  scope: Scope = "chat"


@dataclass
class ParseError:
  code: str
  admin_message: str
  debug_info: str


@dataclass
class PlayerRef:
  """Контекст нарушителя для единообразных подписей в сообщениях."""
  user_id: int
  name: str
  username: Optional[str] = None

  @classmethod
  def from_parsed(cls, parsed: ParsedMute) -> PlayerRef:
    return cls(parsed.target_id, parsed.target_name, parsed.target_username)

  @property
  def display_name(self) -> str:
    return (self.name or "").strip() or str(self.user_id)

  @property
  def line(self) -> str:
    return _format_player_line(self.user_id, self.name, self.username)

  @property
  def greeting(self) -> str:
    return (
      f"<b><tg-emoji emoji-id='5420542898452077602'>🧘‍♂️</tg-emoji> "
      f"Уважаемый {_display_name_link(self.user_id, self.display_name, self.username)},</b>"
    )

  @property
  def short(self) -> str:
    return _display_name_link(self.user_id, self.display_name, self.username)

  @property
  def plain(self) -> str:
    return escape(self.display_name)


_ACTION_PUBLIC_LABELS: Dict[str, str] = {
  "mute": "выдачу временного ограничения",
  "muteall": "ограничение во всех официальных группах",
  "unmute": "снятие ограничений",
  "kick": "исключение из группы",
  "kickall": "исключение из всех официальных групп",
  "ban": "блокировку в этой группе",
  "banall": "блокировку во всех официальных группах",
  "banfull": "полную блокировку во всём проекте",
  "unban": "снятие блокировки в этой группе",
  "unbanall": "снятие блокировки во всех официальных группах",
  "unbanfull": "снятие полной блокировки во всём проекте",
  "warn": "выдачу предупреждения",
  "warnall": "предупреждение во всех официальных группах",
  "warnfull": "предупреждение с полной блокировкой в проекте",
  "cancel_mute": "отмену ожидания мута",
  "cancel_kick": "отмену ожидания кика",
  "cancel_pending": "отмену ожидания",
}

_ACTION_PERMISSION_KEY: Dict[str, str] = {
  "cancel_mute": "mute",
  "cancel_kick": "kick",
  "cancel_pending": "mute",
  # Снятие наказаний проверяет соответствующее право системы бана по охвату.
  "cancel_ban": "ban",
  "unban": "ban",
  "unbanall": "banall",
  "unbanfull": "banfull",
  "cancel_warn": "warn",
  "unwarn": "warn",
}


def _action_public_label(action: str) -> str:
  return _ACTION_PUBLIC_LABELS.get(action, "это действие")


def _permission_action(action: str) -> str:
  return _ACTION_PERMISSION_KEY.get(action, action)


# Текст-отказ при попытке снять наказание с самого себя - общий для всех систем.
# Политика снятия наказаний (мут/бан/варн), реализованная во всех системах:
#   1. Нарушитель не может снять наказание с самого себя - даже если у него есть
#      должность с правом на эту систему наказаний (проверка actor_id == target_id
#      в ядрах снятия _execute_unmute_core / _execute_unban_core / _execute_unwarn_core).
#   2. Снять наказание может только сотрудник с доступом к соответствующей системе
#      (право mute / ban / warn) - это гарантируют check_staff_permission в командах
#      и под кнопками снятия.
# Нижестоящие должности без права и обычные пользователи снять наказание не могут.
SELF_REVOKE_ALERT = "Нельзя снять наказание с самого себя."


def self_revoke_denied_html() -> str:
  """HTML-ответ при попытке снять наказание с самого себя (мут/бан/варн)."""
  return (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Действие запрещено</b>\n"
    "<blockquote><b><i>Снять наказание с самого себя нельзя.</i></b>\n"
    "<i>Сделать это может только сотрудник вышестоящей должности, "
    "имеющий доступ к этой системе наказаний.</i></blockquote>"
  )


# Создатели проекта - их нельзя наказать ни одной из систем (мут/варн/бан/кик),
# ни в каком охвате (chat/all/full). Защита действует на самом раннем этапе -
# сразу после определения цели наказания.
PROTECTED_CREATOR_IDS: frozenset = frozenset({6908672757, 6801702632})


def is_protected_creator(user_id: Optional[int]) -> bool:
  """True, если пользователь - защищённый создатель проекта (наказывать нельзя)."""
  try:
    return int(user_id) in PROTECTED_CREATOR_IDS
  except (TypeError, ValueError):
    return False


def protected_creator_denied_html() -> str:
  """Ироничный ответ от первого лица при попытке наказать создателя проекта."""
  return (
    "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Хорошая попытка</b>\n"
    "<blockquote><b><i>Но нет - я не стану наказывать его</i></b>\n"
    "<i>Я никогда не пойду против своего создателя. Без него меня бы здесь не было.</i></blockquote>"
  )


def _service_unavailable_message() -> str:
  return MuteText.SERVICE_UNAVAILABLE


def _generic_handler_error_message() -> str:
  return MuteText.GENERIC_ERROR


class DbUnavailableError(Exception):
  """База данных временно недоступна."""


NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

_TRANSIENT_DB_ERROR_NAMES = frozenset({
  "ConnectionDoesNotExistError",
  "ConnectionResetError",
  "InterfaceError",
  "TooManyConnectionsError",
  "CannotConnectNowError",
  "PostgresConnectionError",
  "ConnectionRefusedError",
  "TimeoutError",
  "OSError",
})


def _is_transient_db_error(exc: BaseException) -> bool:
  if type(exc).__name__ in _TRANSIENT_DB_ERROR_NAMES:
    return True
  msg = str(exc).lower()
  return any(
    token in msg
    for token in (
      "connection", "pool", "closed", "timeout", "terminated",
      "reset by peer", "cannot connect", "server closed", "пул соединений",
    )
  )


@asynccontextmanager
async def _db_acquire():
  db = _db()
  last_err: Optional[BaseException] = None
  for attempt in range(3):
    try:
      async with db.acquire() as conn:
        yield conn
        return
    except RuntimeError as e:
      last_err = e
    except Exception as e:
      if _is_transient_db_error(e):
        last_err = e
      else:
        raise
    if attempt < 2:
      await asyncio.sleep(0.3 * (attempt + 1))
  raise DbUnavailableError(str(last_err) if last_err else "database unavailable")


async def _reply_db_unavailable(message: Message) -> None:
  await message.reply(
    _service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def check_staff_permission(user_id: int, action: str) -> str:
  db = _db()
  if not await db.ensure_pool():
    return "db_unavailable"
  try:
    async with _db_acquire():
      pass
  except DbUnavailableError:
    return "db_unavailable"
  try:
    await load_staff_rules()
    account = await get_admin_account(user_id)
  except DbUnavailableError:
    return "db_unavailable"
  except Exception as e:
    if _is_transient_db_error(e) or not db.pool:
      return "db_unavailable"
    MuteDebug.error("AUTH", "check_staff_permission", e, user_id=user_id, action=action)
    return "db_unavailable"
  if not account:
    if not db.pool or not await db.ensure_pool():
      return "db_unavailable"
    return "denied"
  if await account.can_perform(action):
    return "allowed"
  return "denied"


async def deny_permission(message: Message, action: str = "mute") -> bool:
  await _send_no_permission(message, action)
  return True


# Служебные столбцы staff_rules (не права)
_STAFF_RULES_SKIP_COLUMNS = frozenset({
  "id", "created_at", "updated_at",
})
# Столбцы staff_rules, которые никогда не считаются флагами разрешений
_STAFF_RULES_METADATA_COLUMNS = frozenset({
  "description", "roles", "role",
  "required_status", "account_status", "status_required",
  "required_availability", "account_availability", "availability_required",
  # Числовой «вес» должности (старшинство). Это НЕ право - иначе целочисленный
  # столбец importance ошибочно попал бы в флаги разрешений.
  "importance", "priority", "rank", "weight", "level", "seniority", "sort_order",
})
# Возможные имена столбца «старшинство должности» (чем больше - тем выше роль).
_STAFF_RULES_IMPORTANCE_NAMES: Tuple[str, ...] = (
  "importance", "priority", "rank", "weight", "level", "seniority", "sort_order",
)
# Имена столбцов-разрешений (определяются по имени, тип не важен - может быть text)
_STAFF_RULES_PERMISSION_NAMES = frozenset({
  "mute", "muteall", "unmute", "ban", "banall", "banfull",
  "kick", "kickall", "warn", "warnall", "warnfull",
})

# Приоритетные цепочки столбцов прав для каждого действия. Если у должности нет
# узкоспециализированного права (например banall), проверяется следующий по
# цепочке - вплоть до базового (ban → mute). Это гарантирует, что более широкое
# действие никогда не доступно «легче», чем базовое: чтобы получить banall, как
# минимум нужно право ban (или mute, если ban-столбца нет вовсе).
_ACTION_COLUMN_FALLBACKS: Dict[str, Tuple[str, ...]] = {
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

_staff_rules_ready: bool = True
_staff_rules_error: Optional[str] = None


@dataclass(frozen=True)
class StaffRulesSchema:
  """Схема staff_rules, определённая из information_schema."""
  role_column: str
  description_column: Optional[str]
  permission_columns: Tuple[str, ...]
  load_error: Optional[str] = None
  importance_column: Optional[str] = None

  @property
  def is_valid(self) -> bool:
    return bool(self.permission_columns) and not self.load_error

  def column_for_action(self, action: str) -> str:
    # 1. Прямое совпадение имени действия со столбцом.
    if action in self.permission_columns:
      return action
    # 2. Приоритетная цепочка (banall → ban → mute и т.п.).
    cols_lower = {c.lower(): c for c in self.permission_columns}
    for candidate in _ACTION_COLUMN_FALLBACKS.get(action, (action,)):
      if candidate in self.permission_columns:
        return candidate
      if candidate.lower() in cols_lower:
        return cols_lower[candidate.lower()]
    # 3. Общий запасной вариант - mute, иначе первый доступный столбец.
    if "mute" in cols_lower:
      return cols_lower["mute"]
    return self.permission_columns[0] if self.permission_columns else "mute"

  def action_label(self, action: str) -> str:
    return self.column_for_action(action).replace("_", " ")


@dataclass(frozen=True)
class StaffRuleRecord:
  """Строка из staff_rules: должность и разрешения."""
  role: str
  display_name: str
  permissions: Dict[str, bool]
  required_status: Optional[str] = None
  required_availability: Optional[str] = None
  # Старшинство должности (чем больше - тем выше роль). 5 = Владелец и т.п.
  importance: Optional[int] = None

  def allows(self, action: str, schema: StaffRulesSchema) -> bool:
    col = schema.column_for_action(action)
    return bool(self.permissions.get(col))

  def matches_account(self, account: "AdminAccount") -> bool:
    if self.required_status and account.status != self.required_status:
      return False
    if self.required_availability and account.availability != self.required_availability:
      return False
    return True


def _humanize_role_slug(slug: str) -> str:
  return slug.replace("_", " ").strip().title()


def _perm_truthy(value: Any) -> bool:
  if value is None:
    return False
  if isinstance(value, bool):
    return value
  if isinstance(value, (int, float)):
    return int(value) == 1
  return str(value).strip().lower() in ("1", "true", "yes", "да", "t")


def _first_present(row: Dict[str, Any], columns: Tuple[str, ...]) -> Optional[str]:
  for col in columns:
    val = row.get(col)
    if val is not None and str(val).strip():
      return str(val).strip()
  return None


def _column_by_name(names: List[str], *candidates: str) -> Optional[str]:
  targets = {c.lower() for c in candidates}
  for name in names:
    if name.lower() in targets:
      return name
  return None


def _is_metadata_column(name: str) -> bool:
  low = name.lower()
  if low in _STAFF_RULES_METADATA_COLUMNS:
    return True
  if low in _STAFF_RULES_SKIP_COLUMNS:
    return True
  return any(h in low for h in ("title", "label", "display")) and low not in ("roles", "role")


def _is_permission_column(name: str, data_type: str) -> bool:
  if _is_metadata_column(name):
    return False
  low = name.lower()
  if low in _STAFF_RULES_PERMISSION_NAMES:
    return True
  if low.startswith("can_") or low.endswith("_allowed"):
    return True
  dt = (data_type or "").lower()
  return dt in {
    "smallint", "integer", "bigint", "boolean", "bit",
  } or dt.startswith(("int", "smallint", "bigint", "bool", "bit"))


async def _introspect_staff_rules_schema(conn) -> StaffRulesSchema:
  """Определяет столбцы staff_rules через information_schema."""
  cols = await conn.fetch(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'staff_rules'
    ORDER BY ordinal_position
    """,
  )
  if not cols:
    return StaffRulesSchema(
      "roles", "description", (), load_error="таблица staff_rules не найдена",
    )

  names = [c["column_name"] for c in cols]
  types = {c["column_name"]: c["data_type"] for c in cols}

  role_col = _column_by_name(names, "roles", "role") or (names[0] if names else "roles")
  description_col = _column_by_name(names, "description")
  importance_col = _column_by_name(names, *_STAFF_RULES_IMPORTANCE_NAMES)

  perm_cols: List[str] = []
  for name in names:
    if _is_permission_column(name, types.get(name, "")):
      perm_cols.append(name)

  # mute по имени - приоритет (часто text/varchar с '0'/'1')
  mute_col = _column_by_name(names, "mute")
  if mute_col and mute_col not in perm_cols:
    perm_cols.insert(0, mute_col)
  # Остальные именованные права (в т.ч. text-столбцы '0'/'1', которые не
  # распознаются по типу): muteall, ban, banall, banfull, kick, kickall, warn, warnall, warnfull.
  for named in ("muteall", "ban", "banall", "banfull", "kick", "kickall", "warn", "warnall", "warnfull"):
    col = _column_by_name(names, named)
    if col and col not in perm_cols:
      perm_cols.append(col)

  perm_cols = list(dict.fromkeys(perm_cols))
  load_error: Optional[str] = None
  if not perm_cols:
    load_error = "в staff_rules не найден столбец mute или другие флаги разрешений"

  return StaffRulesSchema(
    role_col,
    description_col,
    tuple(perm_cols),
    load_error=load_error,
    importance_column=importance_col,
  )


def _parse_importance(row: Dict[str, Any], schema: StaffRulesSchema) -> Optional[int]:
  """Читает старшинство должности из столбца importance (если он есть)."""
  if not schema.importance_column:
    return None
  raw = row.get(schema.importance_column)
  if raw is None or str(raw).strip() == "":
    return None
  try:
    return int(float(str(raw).strip()))
  except (TypeError, ValueError):
    return None


def _rule_display_name(row: Dict[str, Any], role_key: str, schema: StaffRulesSchema) -> str:
  if schema.description_column:
    val = row.get(schema.description_column)
    if val is not None and str(val).strip():
      return str(val).strip()
  return _humanize_role_slug(role_key)


def _parse_rule_record(row: Dict[str, Any], schema: StaffRulesSchema) -> Optional[StaffRuleRecord]:
  raw_role = row.get(schema.role_column)
  if raw_role is None or not str(raw_role).strip():
    return None
  role_key = str(raw_role).strip().lower()
  permissions = {
    col: _perm_truthy(row.get(col))
    for col in schema.permission_columns
  }
  required_status = _first_present(row, (
    "required_status", "account_status", "status_required",
  ))
  required_availability = _first_present(row, (
    "required_availability", "account_availability", "availability_required",
  ))
  importance = _parse_importance(row, schema)
  return StaffRuleRecord(
    role=role_key,
    display_name=_rule_display_name(row, role_key, schema),
    permissions=permissions,
    required_status=required_status,
    required_availability=required_availability,
    importance=importance,
  )


def role_title_from_cache(role: Optional[str]) -> str:
  if not role:
    return "-"
  if _staff_rules_cache:
    rec = _staff_rules_cache[0].get(role.strip().lower())
    if rec:
      return rec.display_name
  return _humanize_role_slug(role)


async def get_staff_rules_schema() -> StaffRulesSchema:
  await load_staff_rules()
  if _staff_rules_cache:
    return _staff_rules_cache[1]
  return StaffRulesSchema("roles", "description", (), load_error=_staff_rules_error)


async def load_staff_rules(*, force_refresh: bool = False) -> Dict[str, StaffRuleRecord]:
  """Загружает staff_rules и схему таблицы из БД (с кэшем)."""
  global _staff_rules_cache, _staff_rules_ready, _staff_rules_error

  if not force_refresh and _staff_rules_cache:
    rules, _schema, loaded_at = _staff_rules_cache
    if time.time() - loaded_at < cfg.STAFF_RULES_CACHE_SEC:
      return rules

  pool = _db().pool
  if not pool:
    MuteDebug.log("RULES", "no db pool")
    return _staff_rules_cache[0] if _staff_rules_cache else {}

  schema: StaffRulesSchema
  rows = []
  try:
    async with pool.acquire() as conn:
      schema = await _introspect_staff_rules_schema(conn)
      if schema.is_valid:
        rows = await conn.fetch("SELECT * FROM staff_rules")
      else:
        _staff_rules_ready = False
        _staff_rules_error = schema.load_error
        MuteDebug.log("RULES", "schema incomplete", detail=schema.load_error or "")
        _staff_rules_cache = ({}, schema, time.time())
        return {}
  except Exception as e:
    _staff_rules_ready = False
    _staff_rules_error = "не удалось прочитать staff_rules"
    MuteDebug.log("RULES", "load failed", err=str(e))
    if cfg.DEBUG and not isinstance(e, (ValueError, KeyError)):
      MuteDebug.error("RULES", "staff_rules unexpected", e)
    return _staff_rules_cache[0] if _staff_rules_cache else {}

  rules: Dict[str, StaffRuleRecord] = {}
  for row in rows:
    record = _parse_rule_record(dict(row), schema)
    if record:
      rules[record.role] = record

  _staff_rules_ready = True
  _staff_rules_error = None
  _staff_rules_cache = (rules, schema, time.time())
  MuteDebug.log(
    "RULES", "loaded",
    count=len(rules),
    role_column=schema.role_column,
    description_column=schema.description_column,
    permission_columns=list(schema.permission_columns),
  )
  return rules


def invalidate_staff_rules_cache() -> None:
  global _staff_rules_cache, _staff_rules_ready, _staff_rules_error
  _staff_rules_cache = None
  _staff_rules_ready = True
  _staff_rules_error = None


async def staff_rules_status_message() -> Optional[str]:
  """Сообщение для пользователя, если правила доступа не загружены."""
  await load_staff_rules()
  if _staff_rules_ready and not _staff_rules_error:
    return None
  return MuteText.RULES_UNAVAILABLE


async def get_staff_rule(role: Optional[str]) -> Optional[StaffRuleRecord]:
  if not role:
    return None
  rules = await load_staff_rules()
  return rules.get(role.strip().lower())


async def action_roles_hint(action: str) -> str:
  """Должности, которым разрешено действие (только человекочитаемые названия)."""
  perm_action = _permission_action(action)
  rules = await load_staff_rules()
  schema = await get_staff_rules_schema()
  titles = sorted(
    r.display_name for r in rules.values() if r.allows(perm_action, schema)
  )
  if not titles:
    return "сотрудники с соответствующими полномочиями"
  if len(titles) == 1:
    return titles[0]
  return ", ".join(titles[:-1]) + f" или {titles[-1]}"


@dataclass
class AdminAccount:
  """
  Запись из admin_accounts.
  Единый источник правды о должности и доступности сотрудника.
  """
  user_id: int
  role: Optional[str]
  status: str
  availability: str
  availability_until: Optional[datetime]
  username: Optional[str]
  first_name: Optional[str]

  @property
  def display_name(self) -> str:
    return (self.first_name or "").strip() or str(self.user_id)

  @property
  def role_title(self) -> str:
    return role_title_from_cache(self.role)

  def is_operational(
    self,
    rule: Optional[StaffRuleRecord] = None,
    now: Optional[datetime] = None,
  ) -> bool:
    """Проверка по admin_accounts и опциональным требованиям из staff_rules."""
    if not self.role:
      return False
    if rule and not rule.matches_account(self):
      return False
    now = now or datetime.now(timezone.utc)
    if self.availability_until:
      until = self.availability_until
      if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
      if until > now:
        return False
    return bool(self.status)

  async def can_perform(self, action: str, now: Optional[datetime] = None) -> bool:
    if not self.role:
      return False
    rule = await get_staff_rule(self.role)
    if not rule or not self.is_operational(rule, now):
      return False
    schema = await get_staff_rules_schema()
    return rule.allows(_permission_action(action), schema)

  async def denial_reason(self, action: str, now: Optional[datetime] = None) -> str:
    perm_action = _permission_action(action)
    action_label = _action_public_label(action)
    if not self.role:
      return "для вас не назначена должность сотрудника"
    rule = await get_staff_rule(self.role)
    if rule and not rule.matches_account(self):
      if rule.required_status and self.status != rule.required_status:
        return (
          f"для должности «{rule.display_name}» требуется другой статус учётной записи"
        )
      if rule.required_availability and self.availability != rule.required_availability:
        return (
          f"для должности «{rule.display_name}» требуется другой режим доступности"
        )
    if not self.is_operational(rule, now):
      if self.availability_until:
        return "ваша учётная запись временно недоступна для модерации"
      return "ваша учётная запись сейчас не готова к модерации"
    if not rule:
      return "для вашей должности не настроены правила доступа"
    schema = await get_staff_rules_schema()
    if not rule.allows(perm_action, schema):
      return (
        f"должности «{rule.display_name}» не разрешено: {action_label}"
      )
    return "недостаточно прав"


@dataclass
class StaffRef:
  """Контекст сотрудника с конкретной должностью для сообщений."""
  user_id: int
  name: str
  role: Optional[str] = None
  username: Optional[str] = None

  @property
  def role_title(self) -> str:
    return role_title_from_cache(self.role) if self.role else "-"

  @property
  def line(self) -> str:
    return _format_staff_line(self.user_id, self.name, self.role, self.username)

  @property
  def greeting(self) -> str:
    return (
      f"<b><tg-emoji emoji-id='5316887736823591263'>👤</tg-emoji> "
      f"Уважаемый {escape(self.role_title)},</b> "
      f"{_user_link(self.user_id, self.name)}"
    )

  @property
  def actor(self) -> str:
    return f"<i>{escape(self.role_title)} {escape(self.name)}</i>"

  @property
  def actor_plain(self) -> str:
    return f"{self.role_title} {self.name}"

  @classmethod
  def from_account(cls, account: AdminAccount) -> StaffRef:
    return cls(
      account.user_id,
      account.display_name,
      account.role,
      account.username,
    )

  @classmethod
  async def from_message(cls, message: Message) -> StaffRef:
    account = await get_admin_account(message.from_user.id)
    if account:
      return cls.from_account(account)
    user = message.from_user
    return cls(
      user.id,
      user.full_name or user.first_name or str(user.id),
      None,
      user.username,
    )

  @classmethod
  async def from_user_id(
    cls,
    user_id: int,
    name: Optional[str] = None,
    username: Optional[str] = None,
  ) -> StaffRef:
    account = await get_admin_account(user_id)
    if account:
      return cls.from_account(account)
    if not name:
      try:
        async with _db().pool.acquire() as conn:
          row = await conn.fetchrow(
            "SELECT first_name, username FROM users WHERE user_id = $1", user_id,
          )
        if row:
          name = row["first_name"] or str(user_id)
          username = username or row["username"]
        else:
          name = str(user_id)
      except Exception:
        name = str(user_id)
    return cls(user_id, name, None, username)


@dataclass
class ChatDisplay:
  chat_id: int
  title: str
  link_url: Optional[str]


@dataclass
class LastMuteRecord:
  admin_user_id: int
  admin_name: str
  admin_role: Optional[str]
  mute_reason: str


def _is_moderation_excluded_chat(chat_id: int) -> bool:
  return chat_id in cfg.MODERATION_EXCLUDED_CHAT_IDS


def _is_staff_chat(chat_id: int) -> bool:
  """Официальная группа проекта, где разрешены команды мута/кика/размута."""
  if _is_moderation_excluded_chat(chat_id):
    return False
  return chat_id in cfg.STAFF_CHAT_IDS


async def _require_staff_chat(message: Message) -> bool:
  """True - чат разрешён для модерации; False - уже отправлен ответ сотруднику."""
  chat_id = message.chat.id
  if _is_moderation_excluded_chat(chat_id):
    staff = await StaffRef.from_message(message)
    await message.reply(
      MuteText.STAFF_CHAT_EXCLUDED.format(
        greeting=staff.greeting, staff_line=staff.line,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return False
  if _is_staff_chat(chat_id):
    return True
  staff = await StaffRef.from_message(message)
  await message.reply(
    MuteText.STAFF_CHAT_ONLY.format(
      greeting=staff.greeting, staff_line=staff.line,
    ),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )
  return False


def _get_command_text(message: Message) -> str:
  return (message.text or message.caption or "").strip()


def _get_proof_file_id(message: Message) -> Optional[str]:
  if message.photo:
    return message.photo[-1].file_id
  doc = message.document
  if doc and doc.mime_type and doc.mime_type.startswith("image/"):
    return doc.file_id
  return None


def _has_proof_media(message: Message) -> bool:
  return _get_proof_file_id(message) is not None


def _normalize_cmd_token(word: str) -> str:
  return (word or "").strip().lower().split("@")[0]


def parse_command_scope(
  word: str,
  known_commands: frozenset,
  roots: Tuple[str, ...],
) -> Tuple[bool, Scope]:
  """
  Распознаёт команду и область действия.
  «мут» / «кик» → только текущая группа; «муталл», «киквсе» и т.п. → все группы проекта.
  """
  w = _normalize_cmd_token(word)
  if not w:
    return False, "chat"
  if w in known_commands:
    return True, "chat"
  for root in roots:
    root_clean = root.lstrip("/").lower()
    candidates = {root_clean, f"/{root_clean}"}
    for base in candidates:
      for suffix in _MOD_SCOPE_ALL_SUFFIXES:
        for variant in (f"{base}{suffix}", f"{base}_{suffix}"):
          if w == variant:
            return True, "all"
  return False, "chat"


def parse_command_mode(
  word: str,
  known_commands: frozenset,
  roots: Tuple[str, ...],
) -> Tuple[bool, Mode]:
  """
  Распознаёт команду наказания и её режим: chat / all / full.

  Примеры:
    «бан»      → (True, "chat")  - только текущая группа;
    «баналл»   → (True, "all")   - все официальные группы;
    «банфулл»  → (True, "full")  - все группы + полная блокировка в проекте.

  Суффиксы режима «full» проверяются раньше «all», чтобы «…фулл» не было
  ошибочно принято за «…фул»+что-то. Возвращает (распознано, режим).
  """
  w = _normalize_cmd_token(word)
  if not w:
    return False, "chat"
  if w in known_commands:
    return True, "chat"
  # Длинные суффиксы проверяем первыми, чтобы «фулл» не уступал «фул».
  full_suffixes = tuple(sorted(set(_MOD_SCOPE_FULL_SUFFIXES), key=len, reverse=True))
  for root in roots:
    root_clean = root.lstrip("/").lower()
    bases = (root_clean, f"/{root_clean}")
    for base in bases:
      for suffix in full_suffixes:
        for variant in (f"{base}{suffix}", f"{base}_{suffix}"):
          if w == variant:
            return True, "full"
      for suffix in _MOD_SCOPE_ALL_SUFFIXES:
        for variant in (f"{base}{suffix}", f"{base}_{suffix}"):
          if w == variant:
            return True, "all"
  return False, "chat"


def mode_to_scope(mode: Mode) -> Scope:
  """Режим наказания → охват по группам: chat → chat; all/full → all."""
  return "chat" if mode == "chat" else "all"


def scope_label(scope: Scope, *, short: bool = False) -> str:
  if scope == "all":
    return "все официальные группы" if short else "во всех официальных группах проекта"
  return "только эта группа" if short else "только в этой группе"


def _format_scope_block(scope: Scope) -> str:
  if scope == "all":
    return (
      "<b><tg-emoji emoji-id='6024039683904772353'>👤</tg-emoji> Охват:</b> "
      "<i>все официальные группы проекта</i>"
    )
  return (
    "<b><tg-emoji emoji-id='6024039683904772353'>👤</tg-emoji> Охват:</b> "
    "<i>только эта группа</i>"
  )


def _mute_badge(scope: Scope) -> str:
  """Короткая «шапка» с названием системы и охватом - видна в каждой карточке."""
  if scope == "all":
    return (
      "<b><tg-emoji emoji-id='5890838600433536921'>🔇</tg-emoji> Муталл</b> "
      "<i>· все группы</i>"
    )
  return (
    "<b><tg-emoji emoji-id='5890838600433536921'>🔇</tg-emoji> Мут</b> "
    "<i>· эта группа</i>"
  )


async def _format_scope_with_groups(scope: Scope, affected_chat_ids: List[int]) -> str:
  header = _format_scope_block(scope)
  if scope != "all" or not affected_chat_ids:
    return header
  group_lines = []
  for chat_id in affected_chat_ids:
    disp = await _get_chat_display(chat_id)
    group_lines.append(_format_chat_line(disp))
  return header + ("\n" + "\n".join(group_lines) if group_lines else "")


def _cmd_word(text: str) -> str:
  parts = (text or "").strip().split()
  if not parts:
    return ""
  return parts[0].lower().split("@")[0]


def _mute_command_scope(text: str) -> Scope:
  _, scope = parse_command_scope(_cmd_word(text), MUTE_COMMANDS, _MUTE_CMD_ROOTS)
  return scope


def _is_mute_command(text: str) -> bool:
  ok, _ = parse_command_scope(_cmd_word(text), MUTE_COMMANDS, _MUTE_CMD_ROOTS)
  return ok


def _is_unmute_command(text: str) -> bool:
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in UNMUTE_COMMANDS:
    return True
  return bool(_UNMUTE_PHRASE_RE.match(t))


def _is_punishments_command(text: str) -> bool:
  """«наказания», «наказания @user», «мои/твои/ваши наказания» и т.п."""
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in _PUNISH_CMD_WORDS:
    return True
  return bool(_PUNISH_PHRASE_RE.match(t))


def _strip_punishments_prefix(text: str) -> str:
  """Возвращает текст после команды «наказания …» (возможная цель)."""
  t = (text or "").strip()
  if not t:
    return ""
  m = _PUNISH_PHRASE_RE.match(t)
  if m:
    return t[m.end():].strip()
  if _cmd_word(t) in _PUNISH_CMD_WORDS:
    parts = t.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""
  return ""


def _is_staff_roster_command(text: str) -> bool:
  """«кто админ», «/staff», «админ состав», «список админов» и т.п."""
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in _STAFF_ROSTER_CMD_WORDS:
    return True
  return bool(_STAFF_ROSTER_PHRASE_RE.match(t))


def _is_staff_permissions_command(text: str) -> bool:
  """«права админов», «права должностей», «/rights», «что может админ» и т.п."""
  t = (text or "").strip()
  if not t:
    return False
  if _cmd_word(t) in _STAFF_PERMS_CMD_WORDS:
    return True
  return bool(_STAFF_PERMS_PHRASE_RE.match(t))


def _strip_unmute_prefix(text: str) -> str:
  """Текст после команды размута (цель: @user, username, id, имя)."""
  t = (text or "").strip()
  if not t:
    return ""
  if _cmd_word(t) in UNMUTE_COMMANDS:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  m = _UNMUTE_PHRASE_RE.match(t)
  if m:
    return t[m.end():].strip()
  return ""


def _looks_like_telegram_username(token: str) -> bool:
  return bool(_TELEGRAM_USERNAME_RE.match(token.lstrip("@")))


def _normalize_username_token(token: str) -> str:
  return token.strip().lstrip("@")


def _is_cancel_mute_command(text: str) -> bool:
  return bool(_CANCEL_MUTE_RE.match((text or "").strip()))


def _strip_cancel_mute_prefix(text: str) -> str:
  m = _CANCEL_MUTE_RE.match((text or "").strip())
  if not m:
    return ""
  return text[m.end():].strip()


def _suggest_cancel_command(
  target_id: int,
  target_name: str,
  target_username: Optional[str] = None,
) -> str:
  if target_username:
    return f"отменить мут @{target_username.lstrip('@')}"
  if target_name and not str(target_name).isdigit():
    return f"отменить мут {target_name}"
  return f"отменить мут {target_id}"


def _cancel_callback_data(admin_id: int, target_id: int) -> str:
  return f"mute:cancel:{admin_id}:{target_id}"


def _pending_cancel_keyboard(admin_id: int, target_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=MuteText.BTN_CANCEL,
      callback_data=_cancel_callback_data(admin_id, target_id),icon_custom_emoji_id="5256110225848543598",
    ),
  ]])


def _revoke_callback_data(admin_id: int, target_id: int) -> str:
  return f"mute:revoke:{admin_id}:{target_id}"


def _mute_revoke_keyboard(admin_id: int, target_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=MuteText.BTN_REVOKE,
      callback_data=_revoke_callback_data(admin_id, target_id),
    ),
  ]])


async def _edit_revoked_message(message: Message, new_text: str) -> None:
  """Редактирует сообщение-подтверждение на месте: новый текст, без кнопки.

  Если правка текста не удалась (например, медиа-сообщение или текст совпал) -
  как минимум убираем клавиатуру, чтобы кнопку нельзя было нажать повторно.
  """
  try:
    await message.edit_text(
      new_text, parse_mode="HTML", reply_markup=None,
      link_preview_options=NO_PREVIEW,
    )
    return
  except Exception:
    pass
  try:
    await message.edit_caption(caption=new_text, parse_mode="HTML", reply_markup=None)
    return
  except Exception:
    pass
  await _edit_remove_keyboard(message)


async def _edit_remove_keyboard(message: Message) -> None:
  """Убирает inline-клавиатуру у сообщения (без изменения текста)."""
  try:
    await message.edit_reply_markup(reply_markup=None)
  except Exception:
    pass


async def _resolve_user_display(user_id: int) -> Tuple[str, Optional[str]]:
  """Имя и username нарушителя из БД (для кнопок снятия наказания)."""
  name = str(user_id)
  username: Optional[str] = None
  pool = getattr(_db(), "pool", None)
  if not pool:
    return name, username
  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow(
        "SELECT first_name, username FROM users WHERE user_id = $1", user_id,
      )
    if row:
      name = row["first_name"] or str(user_id)
      username = row["username"]
  except Exception:
    pass
  return name, username


def _format_reason(reason: str) -> str:
  if not reason or reason.strip() == "Не указана":
    return "<i>не указана</i>"
  return escape(reason.strip())


def _format_mute_reason_block(reason: Optional[str], *, label: str = "Причина наказания") -> str:
  """Строка с причиной для публичных сообщений. Пустая, если причина не указана."""
  if not reason or reason.strip() in ("", "Не указана"):
    return ""
  return f"<b><tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji></b> {label} : {_format_reason(reason)}"


def _format_player_line(
  user_id: int,
  name: str,
  username: Optional[str] = None,
) -> str:
  # Username намеренно не выводим: в карточке наказания оставляем только
  # самое важное - кликабельное имя и ID нарушителя.
  parts = [_display_name_link(user_id, name, username), f"<code>{user_id}</code>"]
  label = escape(cfg.PLAYER_LINE_LABEL)
  return (
    f"<b><tg-emoji emoji-id='5420542898452077602'>🧘‍♂️</tg-emoji> {label}:</b> "
    + " · ".join(parts)
  )


def _staff_line_label(role: Optional[str]) -> str:
  title = role_title_from_cache(role)
  return (
    f"<b><tg-emoji emoji-id='5316887736823591263'>👮</tg-emoji> "
    f"{escape(title)}:</b>"
  )


def _format_staff_line(
  user_id: int,
  name: str,
  role: Optional[str] = None,
  username: Optional[str] = None,
) -> str:
  # Username администратора не показываем - только должность, имя и ID.
  parts = [_display_name_link(user_id, name, username), f"<code>{user_id}</code>"]
  return _staff_line_label(role) + " · " + " · ".join(parts)


def _has_command_text(text: str) -> bool:
  return bool((text or "").strip())


def _is_mute_related_message(message: Message) -> bool:
  if not message.from_user:
    return False
  text = _get_command_text(message)
  if text:
    if _is_cancel_mute_command(text):
      return True
    if _is_mute_command(text) or _is_unmute_command(text):
      return True
  from bot.admins.punish_proof import pending_contains
  if _has_proof_media(message) and pending_contains(_pending_mutes, message.from_user.id):
    return True
  return False


def _cleanup_expired_chat_mutes_sync() -> List[Tuple[int, int]]:
  """Возвращает список (chat_id, user_id) с истёкшим мутом."""
  now = datetime.now()
  expired: List[Tuple[int, int]] = []
  for key, until in list(_chat_mutes.items()):
    if until <= now:
      expired.append(key)
      _chat_mutes.pop(key, None)
      MuteDebug.log("CHAT_MUTE", "expired", chat=key[0], user=key[1])
  return expired


async def _resolve_mute_scope(user_id: int) -> Tuple[bool, List[int]]:
  """Охват действующего мута ДО снятия: (глобальный_ли, точные_затронутые_группы).

  • глобальный - мут «во всех группах» (muteall / запись users.mute_until);
  • точные затронутые группы - ИМЕННО те официальные чаты, где наказание реально
    наложено: конкретные ряды active_mutes (chat_id≠0) и записи в памяти
    `_chat_mutes` (туда попадают только успешно ограниченные чаты).

  Здесь НЕ делаем подстановку «все группы» для глобального охвата - это решает
  вызывающий код (как запасной вариант, когда точный набор неизвестен, например
  после перезапуска). Это и даёт правило: уведомление о снятии уходит только в
  группы, где пользователь действительно был наказан.
  """
  global_scope = False
  chats: List[int] = []
  seen = set()
  pool = _db().pool
  if pool:
    try:
      async with pool.acquire() as conn:
        rows = await conn.fetch(
          "SELECT chat_id, scope FROM active_mutes WHERE user_id = $1", user_id,
        )
        for r in rows:
          cid = int(r["chat_id"])
          if (r["scope"] or "") == "all" or cid == 0:
            global_scope = True
          if _is_staff_chat(cid) and cid not in seen:
            seen.add(cid)
            chats.append(cid)
        urow = await conn.fetchrow(
          "SELECT mute_until FROM users WHERE user_id = $1", user_id,
        )
        if urow and urow["mute_until"] is not None:
          global_scope = True
    except Exception as e:
      MuteDebug.log("AUTO", "resolve scope skip", err=str(e), user=user_id)
  for (cid, uid) in list(_chat_mutes.keys()):
    if uid == user_id and _is_staff_chat(cid) and cid not in seen:
      seen.add(cid)
      chats.append(cid)
  return global_scope, chats


async def _expire_mute(
  user_id: int,
  target_name: str = "",
  trigger_chat_id: int = 0,
  *,
  notify: bool = True,
  known_chats: Optional[List[int]] = None,
) -> None:
  """Единая идемпотентная точка авто-снятия истёкшего мута.

  Определяет охват (chat / all), снимает ограничение в нужных группах,
  чистит БД/память/таймер и отправляет РОВНО ОДНО уведомление на снятие -
  ТОЛЬКО в те группы, где пользователь действительно был наказан.

  • known_chats - точный набор групп, переданный фоновой очисткой (записи из
    памяти `_chat_mutes` снимаются раньше, чем сюда дойдёт управление, поэтому
    их передают явно, чтобы не потерять точный набор);
  • если точный набор неизвестен (например, после перезапуска) - для глобального
    охвата запасной вариант «все официальные группы».
  Анти-дубликат в _notify_unmute не даёт нескольким фоновым триггерам
  отправить повторное сообщение.
  """
  global_scope, chats = await _resolve_mute_scope(user_id)
  if known_chats:
    for c in known_chats:
      if _is_staff_chat(c) and c not in chats:
        chats.append(c)
  if not chats:
    if global_scope:
      chats = [c for c in cfg.STAFF_CHAT_IDS if _is_staff_chat(c)]
    elif _is_staff_chat(trigger_chat_id):
      chats = [trigger_chat_id]

  if global_scope:
    _clear_mute_all_staff_chats(user_id)
    try:
      async with _db().pool.acquire() as conn:
        await conn.execute(
          "UPDATE users SET mute_until = NULL WHERE user_id = $1 AND mute_until <= NOW()",
          user_id,
        )
    except Exception as e:
      MuteDebug.error("AUTO", "db clear", e, user_id=user_id)
    await _delete_active_mutes(user_id)
    await _unrestrict_in_all_staff_chats(user_id)
  else:
    for cid in chats:
      _clear_chat_mute(cid, user_id)
      await _delete_active_mutes(user_id, cid)
      await _unrestrict_in_chat(cid, user_id)

  log_chat = trigger_chat_id if _is_staff_chat(trigger_chat_id) else (chats[0] if chats else 0)
  await _log_auto_unmute_db(user_id, target_name, log_chat, scope=("all" if global_scope else "chat"))

  try:
    from bot.admins import punish_timers
    punish_timers.cancel_mute(user_id)
  except Exception:
    pass

  if notify and chats:
    src = trigger_chat_id if _is_staff_chat(trigger_chat_id) else chats[0]
    await _notify_unmute(
      src, user_id, target_name,
      event="expired",
      notify_chats=chats,
    )

  MuteDebug.log(
    "AUTO", "unmuted", user_id=user_id, name=target_name,
    scope=("all" if global_scope else "chat"), chats=chats,
  )


async def _auto_unmute_user(
  chat_id: int,
  user_id: int,
  target_name: str = "",
  notify: bool = True,
) -> None:
  """Совместимая обёртка: авто-снятие мута с авто-определением охвата."""
  await _expire_mute(user_id, target_name, chat_id, notify=notify)


async def _release_expired_chat_mute(
  chat_id: int,
  user_id: int,
  *,
  notify: bool = True,
) -> None:
  """Снимает истёкший мут (охват определяется автоматически)."""
  name = await _db().get_firstname_by_user_id(user_id) or str(user_id)
  await _expire_mute(user_id, name, chat_id, notify=notify)


async def _cleanup_expired_chat_mutes_async() -> None:
  # Группируем по пользователю: один человек → одно снятие и одно уведомление,
  # даже если в памяти было несколько истёкших записей по разным группам.
  # Собираем ПОЛНЫЙ набор затронутых групп и передаём его как known_chats -
  # уведомление уйдёт ровно в те группы, где пользователь был наказан.
  by_user: Dict[int, List[int]] = {}
  for chat_id, user_id in _cleanup_expired_chat_mutes_sync():
    by_user.setdefault(user_id, []).append(chat_id)
  for user_id, chat_ids in by_user.items():
    name = await _db().get_firstname_by_user_id(user_id) or str(user_id)
    await _expire_mute(
      user_id, name, chat_ids[0] if chat_ids else 0,
      notify=True, known_chats=chat_ids,
    )


async def _sync_user_mute_status(chat_id: int, user_id: int) -> bool:
  """
  Проверяет актуальность мута. Если срок истёк - размучивает.
  Возвращает True, если пользователь сейчас в муте в этом чате.
  """
  now = _utc_now()
  key = (chat_id, user_id)
  until_mem = _chat_mutes.get(key)

  if until_mem:
    if _to_utc(until_mem) > now:
      return True
    name = await _db().get_firstname_by_user_id(user_id) or str(user_id)
    await _release_expired_chat_mute(chat_id, user_id, notify=True)
    return False

  db_until = await _fetch_db_mute_until(user_id)
  if db_until:
    if chat_id < 0:
      _chat_mutes[key] = db_until
    return True

  if _is_staff_chat(chat_id):
    tg_muted, _ = await _check_telegram_mute_in_chat(chat_id, user_id)
    if tg_muted:
      return True

  try:
    async with _db().pool.acquire() as conn:
      row = await conn.fetchrow(
        "SELECT mute_until, first_name FROM users WHERE user_id = $1", user_id,
      )
    if row and row["mute_until"] and not _is_datetime_active(row["mute_until"], now=now):
      name = row["first_name"] or str(user_id)
      await _auto_unmute_user(chat_id, user_id, name, notify=True)
  except Exception as e:
    MuteDebug.error("AUTO", "sync status", e, user_id=user_id)
  return False


async def _scan_expired_mutes_from_db() -> None:
  """Размут по БД (после рестарта бота или без записи в кэше)."""
  db = _db()
  if not await db.ensure_pool():
    return
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT user_id, first_name
        FROM users
        WHERE mute_until IS NOT NULL AND mute_until <= NOW()
        LIMIT 50
        """,
      )
  except DbUnavailableError:
    return
  except Exception as e:
    if _is_transient_db_error(e):
      MuteDebug.error("AUTO", "db scan", e)
    return

  for row in rows:
    user_id = row["user_id"]
    name = row["first_name"] or str(user_id)
    # Охват и затронутые группы определяются внутри _expire_mute; для записи в
    # users.mute_until это всегда глобальный мут → уведомление во все группы.
    await _expire_mute(user_id, name, 0, notify=True)


async def _mute_expiry_loop() -> None:
  """Фоновая проверка: истёкшие муты (ожидание фото punish_proof worker)."""
  while True:
    try:
      await asyncio.sleep(cfg.WORKER_INTERVAL_SEC)
      await _cleanup_expired_chat_mutes_async()
      await _scan_expired_mutes_from_db()
    except asyncio.CancelledError:
      break
    except Exception as e:
      MuteDebug.error("WORKER", "tick", e)


def _ensure_expiry_worker() -> None:
  global _expiry_worker_started
  if _expiry_worker_started:
    return
  _expiry_worker_started = True
  ensure_proof_pending_worker()
  asyncio.create_task(_mute_expiry_loop())
  MuteDebug.log("WORKER", "started")


async def _expire_pending_mute(admin_id: int, data: Dict[str, Any]) -> None:
  """
  Истечение ожидания фото: правит сообщение в группе и уведомляет сотрудника в ЛС.
  """
  from bot.admins.punish_proof import coerce_telegram_user_id, safe_edit_message_text
  admin_id = coerce_telegram_user_id(admin_id)
  if admin_id is None:
    return
  if data.get("expiry_notified"):
    return
  data["expiry_notified"] = True

  parsed = data.get("parsed")
  chat_id = data.get("chat_id")
  prompt_chat = data.get("prompt_chat_id")
  prompt_msg_id = data.get("prompt_message_id")
  timeout_min = cfg.proof_timeout_minutes()
  admin_name = data.get("admin_name") or str(admin_id)
  account = await get_admin_account(admin_id)
  staff = (
    StaffRef.from_account(account)
    if account else
    StaffRef(admin_id, admin_name, data.get("admin_role"))
  )

  player_line = ""
  chat_line = ""
  player: Optional[PlayerRef] = None
  if parsed:
    player = PlayerRef.from_parsed(parsed)
    player_line = player.line
    if chat_id:
      disp = await _get_chat_display(chat_id)
      chat_line = _format_chat_line(disp)

  reason_line = _format_mute_reason_block(
    parsed.reason if parsed else None, label="Заявленная причина",
  )
  reason_part = f"<tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> {reason_line}\n" if reason_line else ""
  group_text = MuteText.PENDING_EXPIRED_GROUP.format(
    player_line=player_line,
    chat_line=chat_line,
    reason_part=reason_part,
    timeout=timeout_min,
  ).strip()

  if prompt_chat and prompt_msg_id:
    try:
      await safe_edit_message_text(
        _bot(),
        chat_id=prompt_chat,
        message_id=prompt_msg_id,
        text=group_text,
        reply_markup=None,
      )
      MuteDebug.log(
        "PENDING", "group prompt updated on expiry",
        admin_id=admin_id, chat_id=prompt_chat, message_id=prompt_msg_id,
      )
    except Exception as e:
      MuteDebug.error("PENDING", "edit group prompt on expiry", e, admin_id=admin_id)

  admin_body = MuteText.PENDING_EXPIRED_ADMIN.format(
    greeting=staff.greeting,
    player_line=player_line,
    chat_line=chat_line,
    reason_part=reason_part,
    timeout=timeout_min,
  ).strip()

  try:
    await _bot().send_message(admin_id, admin_body, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    MuteDebug.log("PENDING", "admin notified on expiry", admin_id=admin_id)
  except Exception as e:
    MuteDebug.error("PENDING", "notify admin on expiry", e, admin_id=admin_id)


async def _notify_pending_expired(admin_id: int, data: Dict[str, Any]) -> None:
  await _expire_pending_mute(admin_id, data)


async def _cleanup_expired_pending_async() -> None:
  from bot.admins.punish_proof import is_proof_expired, pending_items, pending_pop

  now = time.time()
  for uid, data in pending_items(_pending_mutes):
    if not is_proof_expired(data.get("expires_at", 0), now=now):
      continue
    pending_pop(_pending_mutes, uid)
    MuteDebug.log("PENDING", "expired - punishment NOT applied", admin_id=uid)
    await _expire_pending_mute(uid, data)


async def _maybe_mute_maintenance() -> None:
  """Фоновая уборка истёкших мутов (ожидание фото только proof worker)."""
  global _mute_maintenance_last
  now = time.time()
  if now - _mute_maintenance_last < _MUTE_MAINTENANCE_INTERVAL_SEC:
    return
  _mute_maintenance_last = now
  _ensure_expiry_worker()
  await _cleanup_expired_chat_mutes_async()


def _format_duration_human(delta: timedelta) -> str:
  total_sec = int(delta.total_seconds())
  if total_sec >= 365 * 24 * 3600 * 100:
    return "<b>навсегда</b>"
  days, rem = divmod(total_sec, 86400)
  hours, rem = divmod(rem, 3600)
  minutes, seconds = divmod(rem, 60)
  parts: List[str] = []
  if days:
    parts.append(f"<b>{days}</b> д.")
  if hours:
    parts.append(f"<b>{hours}</b> ч.")
  if minutes:
    parts.append(f"<b>{minutes}</b> мин.")
  if seconds:
    parts.append(f"<b>{seconds}</b> сек.")
  return " ".join(parts) if parts else "<b>0</b> сек."


def _format_until(dt: datetime) -> str:
  return dt.strftime("%d.%m %H:%M:%S")


def _display_name_link(user_id: int, name: str, username: Optional[str] = None) -> str:
  """Кликабельное имя: t.me/@username если есть, иначе tg://user?id."""
  clean = _sanitize_username(username)
  display = (name or "").strip() or (f"@{clean}" if clean else str(user_id))
  if clean:
    return f'<a href="https://t.me/{escape(clean)}">{escape(display)}</a>'
  return f'<a href="tg://user?id={user_id}">{escape(display)}</a>'


def _user_link(user_id: int, name: str) -> str:
  return _display_name_link(user_id, name)


def _format_duration_short(delta: timedelta) -> str:
  total_sec = int(delta.total_seconds())
  if total_sec >= 365 * 24 * 3600 * 100:
    return "навсегда"
  days, rem = divmod(total_sec, 86400)
  hours, rem = divmod(rem, 3600)
  minutes, seconds = divmod(rem, 60)
  parts: List[str] = []
  if days:
    parts.append(f"{days} д.")
  if hours:
    parts.append(f"{hours} ч.")
  if minutes:
    parts.append(f"{minutes} мин.")
  if seconds:
    parts.append(f"{seconds} сек.")
  return " ".join(parts) if parts else "0 сек."


_FOREVER_DELTA: timedelta = timedelta(days=365 * 100)
_FOREVER_THRESHOLD_SEC: int = int(_FOREVER_DELTA.total_seconds())
# Telegram: ограничение >366 суток считается постоянным (until_date не передаём).
_TELEGRAM_MAX_TIMED_SEC: int = 366 * 24 * 3600
# Верхняя граница Unix time для Windows и API Telegram.
_MAX_SAFE_UNIX_TS: int = 2_147_483_647


def _is_forever_delta(time_delta: timedelta) -> bool:
  return time_delta.total_seconds() >= _FOREVER_THRESHOLD_SEC


def _normalize_time_delta(time_delta: timedelta) -> timedelta:
  """Слишком большие сроки приводим к каноническому «навсегда» (безопасно для БД и ОС)."""
  if _is_forever_delta(time_delta):
    return _FOREVER_DELTA
  return time_delta


def _safe_unix_timestamp(dt: datetime) -> int:
  if dt.tzinfo is not None:
    dt = dt.replace(tzinfo=None)
  try:
    ts = int(dt.timestamp())
  except (OSError, OverflowError, ValueError):
    ts = _MAX_SAFE_UNIX_TS
  if ts > _MAX_SAFE_UNIX_TS:
    ts = _MAX_SAFE_UNIX_TS
  if ts < 0:
    ts = 0
  return ts


def _rebase_expiry_at_now(time_delta: timedelta) -> datetime:
  """Конец срока наказания от текущего момента - после подтверждения фото-пруфа."""
  return datetime.now() + _normalize_time_delta(time_delta)


def _refresh_parsed_mute_expiry(parsed: ParsedMute) -> None:
  """Пересчитывает mute_until от момента применения наказания (не от разбора команды)."""
  parsed.time_delta = _normalize_time_delta(parsed.time_delta)
  parsed.mute_until = _rebase_expiry_at_now(parsed.time_delta)


def _format_until_display(until: datetime, time_delta: timedelta) -> str:
  if _is_forever_delta(time_delta):
    return "навсегда"
  return _format_until(until)


def _pending_mute_term_block(parsed: ParsedMute) -> str:
  """Срок в сообщении ожидания пруфа - без точной даты (она появится после фото)."""
  if _is_forever_delta(parsed.time_delta):
    return (
      "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : навсегда</b>"
    )
  duration = _format_duration_short(parsed.time_delta)
  return (
    f"<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : {duration}</b>\n"
    "<blockquote><i>Точное время окончания будет указано после подтверждения фото.</i></blockquote>"
  )


def _duration_pair(time_delta: timedelta) -> Tuple[timedelta, int]:
  td = _normalize_time_delta(time_delta)
  return td, max(1, int(td.total_seconds()) // 60)


def parse_duration(text: str) -> Optional[Tuple[timedelta, int]]:
  raw = (text or "").strip().lower().replace(",", ".")
  if not raw:
    return None
  m = _COMPACT_DURATION_RE.match(raw)
  if m:
    return _amount_unit_to_delta(int(m.group(1)), m.group(2).lower())
  m = _COMPACT_MINUTE_RE.match(raw) or _COMPACT_MINUTE_LATIN_RE.match(raw)
  if m:
    return _duration_pair(timedelta(minutes=int(m.group(1))))
  m = re.match(r"^(\d+)\s+(.+)$", raw, re.IGNORECASE)
  if m:
    amount = int(m.group(1))
    unit_phrase = m.group(2).strip().lower()
    unit_token = unit_phrase.split()[0] if unit_phrase else ""
    for aliases, kind in _DURATION_UNITS:
      if unit_phrase in aliases or unit_token in aliases:
        return _delta_from_kind(amount, kind)
    return _amount_unit_to_delta(amount, unit_token)
  return None


def _amount_unit_to_delta(amount: int, unit: str) -> Optional[Tuple[timedelta, int]]:
  unit = unit.lower()
  for aliases, kind in _DURATION_UNITS:
    if unit in aliases:
      return _delta_from_kind(amount, kind)
  single_map = {"с": "seconds", "s": "seconds", "ч": "hours", "h": "hours",
                "д": "days", "d": "days", "г": "years", "y": "years"}
  if unit in single_map:
    return _delta_from_kind(amount, single_map[unit])
  if unit in ("м", "m"):
    return _duration_pair(timedelta(minutes=amount))
  return None


def _delta_from_kind(amount: int, kind: str) -> Tuple[timedelta, int]:
  if kind == "seconds":
    td = _normalize_time_delta(timedelta(seconds=amount))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "minutes":
    td = _normalize_time_delta(timedelta(minutes=amount))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "hours":
    td = _normalize_time_delta(timedelta(hours=amount))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "days":
    td = _normalize_time_delta(timedelta(days=amount))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "months":
    td = _normalize_time_delta(timedelta(days=amount * 30))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "years":
    td = _normalize_time_delta(timedelta(days=amount * 365))
    return td, max(1, int(td.total_seconds()) // 60)
  if kind == "forever":
    return _FOREVER_DELTA, 365 * 100 * 24 * 60
  td = _normalize_time_delta(timedelta(minutes=amount))
  return td, max(1, int(td.total_seconds()) // 60)


def _extract_duration_and_reason(parts: List[str], start: int) -> Tuple[Optional[str], str, int]:
  """Сначала ищет кратчайший валидный срок - всё после него считается причиной."""
  for span in (1, 2, 3):
    if len(parts) < start + span:
      continue
    candidate = " ".join(parts[start:start + span])
    if parse_duration(candidate):
      reason = " ".join(parts[start + span:]).strip() or "Не указана"
      return candidate, reason, start + span
  return None, "Не указана", start


def _body_starts_with_duration(parts: List[str]) -> bool:
  """True, если тело команды начинается со срока (например «1 день …» без @user)."""
  if not parts:
    return False
  dur_text, _, _ = _extract_duration_and_reason(parts, 0)
  return dur_text is not None


def _get_reply_target_message(message: Message) -> Optional[Message]:
  if message.reply_to_message:
    return message.reply_to_message
  ext = getattr(message, "external_reply", None)
  if ext and getattr(ext, "from_user", None):
    return ext  # type: ignore[return-value]
  return None


async def _confirm_lookup_user_id(
  uid: Optional[int],
  name: Optional[str],
  username: Optional[str],
  *,
  source_chat_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Отбрасывает user_id, которого нет в Telegram."""
  if uid is None:
    return None, name, username
  from bot.admins.punish_validate import probe_chat_ids, verify_telegram_user_exists
  if not await verify_telegram_user_exists(
    uid, probe_chat_ids=probe_chat_ids(source_chat_id),
  ):
    MuteDebug.log("PARSE", "invalid telegram user id", uid=uid, token=username or name)
    return None, name, username
  return uid, name, username


def _staff_tg_identity_allowed(uid: int) -> bool:
  retry_at = float(_staff_tg_identity_retry_at.get(int(uid), 0.0) or 0.0)
  return time.time() >= retry_at


def _staff_tg_identity_backoff(uid: int) -> None:
  _staff_tg_identity_retry_at[int(uid)] = time.time() + _STAFF_TG_IDENTITY_RETRY_SEC
  # Лёгкая уборка, чтобы словарь не рос бесконечно.
  if len(_staff_tg_identity_retry_at) > 5000:
    now = time.time()
    for k in list(_staff_tg_identity_retry_at.keys()):
      if _staff_tg_identity_retry_at.get(k, 0.0) <= now:
        _staff_tg_identity_retry_at.pop(k, None)


async def _safe_fetch_user_chat(uid: int):
  uid = int(uid)
  if uid <= 0:
    return None
  if not _staff_tg_identity_allowed(uid):
    return None
  try:
    return await _bot().get_chat(uid)
  except TelegramBadRequest as e:
    if "chat not found" in str(e).lower():
      _staff_tg_identity_backoff(uid)
    return None
  except Exception:
    return None


async def _lookup_target_by_token(
  token: str,
  *,
  source_chat_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  token = token.strip()
  if not token:
    return None, None, None
  db = _db()

  if token.startswith("https://t.me/"):
    username = _normalize_username_token(token.replace("https://t.me/", "").split("/")[0])
    uid = await db.get_user_id_by_username(username)
    if uid:
      name = await db.get_firstname_by_user_id(uid)
      return await _confirm_lookup_user_id(
        uid, name or username, username, source_chat_id=source_chat_id,
      )
    return None, None, username

  if token.startswith("@"):
    username = _normalize_username_token(token)
    uid = await db.get_user_id_by_username(username)
    if uid:
      name = await db.get_firstname_by_user_id(uid)
      return await _confirm_lookup_user_id(
        uid, name or username, username, source_chat_id=source_chat_id,
      )
    return None, None, username

  if token.isdigit():
    uid = int(token)
    uid, name, username = await _confirm_lookup_user_id(
      uid, None, None, source_chat_id=source_chat_id,
    )
    if not uid:
      return None, None, None
    name = await db.get_firstname_by_user_id(uid)
    if not name:
      chat = await _safe_fetch_user_chat(uid)
      if chat is not None:
        name = (
          getattr(chat, "full_name", None)
          or getattr(chat, "first_name", None)
        )
    return uid, name or str(uid), None

  if _looks_like_telegram_username(token):
    username = _normalize_username_token(token)
    uid = await db.get_user_id_by_username(username)
    if uid:
      name = await db.get_firstname_by_user_id(uid)
      return await _confirm_lookup_user_id(
        uid, name or username, username, source_chat_id=source_chat_id,
      )
    MuteDebug.log("PARSE", "username not in db", username=username)
    return None, None, username

  users_map = await db.get_user_id_by_first_name(token)
  if users_map and len(users_map) == 1:
    uid = next(iter(users_map))
    return await _confirm_lookup_user_id(
      uid, users_map[uid], None, source_chat_id=source_chat_id,
    )
  if users_map and len(users_map) > 1:
    MuteDebug.log("PARSE", "ambiguous name", token=token, matches=len(users_map))
    return None, None, None

  return None, None, None


def _is_explicit_user_token(token: str) -> bool:
  """Однозначная ссылка на пользователя в тексте команды.

  Это @username, ссылка t.me или username из букв. Голое число
  (например «10» в «бан 10 сек привет») НЕ считается целью - при ответе
  на сообщение это часть срока, а нарушитель берётся из reply.
  """
  token = (token or "").strip()
  if not token:
    return False
  if token.startswith("@") or token.startswith("https://t.me/"):
    return True
  return _looks_like_telegram_username(token)


async def _resolve_reply_or_explicit(
  reply_user: User,
  body: List[str],
  *,
  source_chat_id: Optional[int] = None,
) -> Tuple[int, str, Optional[str], List[str], Optional[str]]:
  # При ответе на сообщение нарушитель по умолчанию автор этого сообщения.
  # Цель переопределяем при явной ссылке (@user / t.me / username) или при
  # числовом ID в начале команды. Если число не существует в Telegram
  # («кик 10 10»), НЕ подменяем на автора reply возвращаем not_found.
  if body:
    from bot.admins.punish_validate import invalid_numeric_target_token

    bad_num = invalid_numeric_target_token(body)
    if bad_num:
      return 0, "", None, body[1:], bad_num
    first = body[0].strip()
    if _is_explicit_user_token(first):
      target_id, target_name, target_username = await _lookup_target_by_token(
        first, source_chat_id=source_chat_id,
      )
      if target_id:
        return target_id, target_name or str(target_id), target_username, body[1:], None
      return 0, "", target_username, body[1:], first
    if first.isdigit():
      if not _body_starts_with_duration(body):
        target_id, target_name, target_username = await _lookup_target_by_token(
          first, source_chat_id=source_chat_id,
        )
        if target_id:
          return target_id, target_name or str(target_id), target_username, body[1:], None
        return 0, "", None, body[1:], first
  u = reply_user
  return u.id, u.full_name or u.first_name or str(u.id), u.username, body, None


async def _resolve_target_from_entities(
  message: Message,
  *,
  source_chat_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Цель из @mention или text_mention в сообщении."""
  text = _get_command_text(message)
  entities = message.entities or message.caption_entities or []
  if not text or not entities:
    return None, None, None

  db = _db()
  for ent in entities:
    etype = getattr(ent, "type", None)
    type_key = etype.value if hasattr(etype, "value") else str(etype)
    if type_key == "text_mention" and getattr(ent, "user", None):
      u = ent.user
      return (
        u.id,
        u.full_name or u.first_name or str(u.id),
        u.username,
      )
    if type_key == "mention":
      fragment = text[ent.offset: ent.offset + ent.length]
      username = _normalize_username_token(fragment)
      uid = await db.get_user_id_by_username(username)
      if uid:
        name = await db.get_firstname_by_user_id(uid)
        return await _confirm_lookup_user_id(
          uid, name or username, username, source_chat_id=source_chat_id,
        )
  return None, None, None


async def _resolve_target_from_body(
  message: Message,
  body: str,
  *,
  source_chat_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Ищет нарушителя в тексте: entities → первый токен → вся строка."""
  body = (body or "").strip()
  if not body:
    return None, None, None

  chat_id = source_chat_id
  if chat_id is None:
    chat_id = getattr(getattr(message, "chat", None), "id", None)

  ent_id, ent_name, ent_username = await _resolve_target_from_entities(
    message, source_chat_id=chat_id,
  )
  if ent_id:
    return ent_id, ent_name, ent_username

  parts = body.split()
  target_id, target_name, target_username = await _lookup_target_by_token(
    parts[0], source_chat_id=chat_id,
  )
  if not target_id and len(parts) > 1:
    target_id, target_name, target_username = await _lookup_target_by_token(
      body, source_chat_id=chat_id,
    )
  return target_id, target_name, target_username


async def _resolve_unmute_target(
  message: Message,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Цель для размута: ответ на сообщение или токен после команды."""
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return (
      u.id,
      u.full_name or u.first_name or str(u.id),
      u.username,
    )
  body = _strip_unmute_prefix(_get_command_text(message))
  return await _resolve_target_from_body(message, body)


def _target_lookup_error_message(
  body: str,
  *,
  target_username: Optional[str] = None,
) -> str:
  token = (body.split()[0] if body else "").strip()
  if target_username or token.startswith("@") or _looks_like_telegram_username(token):
    username = target_username or _normalize_username_token(token)
    return MuteText.UNMUTE_NOT_FOUND_USERNAME.format(username=escape(username))
  if token.isdigit():
    return MuteText.UNMUTE_NOT_FOUND_ID.format(token=escape(token))
  if token:
    return MuteText.UNMUTE_NOT_FOUND_NAME.format(body=escape(body))
  return MuteText.UNMUTE_NO_TARGET


async def _resolve_cancel_mute_target(message: Message) -> ParsedMute | ParseError:
  """Определяет игрока для отмены мута: ответ на сообщение или токен после команды."""
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return ParsedMute(
      target_id=u.id,
      target_name=u.full_name or u.first_name or str(u.id),
      target_username=u.username,
      duration_text="",
      time_delta=timedelta(),
      duration_minutes=0,
      mute_until=datetime.now(),
      reason="",
    )

  body = _strip_cancel_mute_prefix(_get_command_text(message))
  if not body:
    return ParseError("cancel_no_target", MuteText.CANCEL_NO_TARGET, "empty body")

  target_id, target_name, target_username = await _resolve_target_from_body(message, body)

  if not target_id:
    return ParseError(
      "cancel_user_not_found",
      _target_lookup_error_message(body, target_username=target_username),
      body,
    )

  return ParsedMute(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    duration_text="",
    time_delta=timedelta(),
    duration_minutes=0,
    mute_until=datetime.now(),
    reason="",
  )


async def parse_mute_command(message: Message) -> ParsedMute | ParseError:
  text = _get_command_text(message)
  parts = text.split()
  MuteDebug.log("PARSE", "start", text=text, parts=parts, reply=bool(message.reply_to_message))

  if len(parts) < 2:
    return ParseError("help", MuteText.ERR_NEED_TIME, "too few parts")

  reply_msg = _get_reply_target_message(message)
  body = parts[1:]
  source_chat_id = message.chat.id

  target_id: Optional[int] = None
  target_name: Optional[str] = None
  target_username: Optional[str] = None
  rest: List[str] = body

  if reply_msg and reply_msg.from_user:
    # Явное указание пользователя в команде (например @werkov3) важнее ответа -
    # это согласует мут с бан/варн/кик и позволяет «мут @werkov3 10сек 1111»
    # работать даже когда команда отправлена ответом (в т.ч. с фото-пруфом).
    target_id, target_name, target_username, rest, not_found = await _resolve_reply_or_explicit(
      reply_msg.from_user, body, source_chat_id=source_chat_id,
    )
    if not_found:
      if str(not_found).isdigit():
        return ParseError(
          "user_not_found",
          MuteText.ERR_NOT_FOUND_ID.format(token=escape(not_found)),
          not_found,
        )
      return ParseError(
        "user_not_found",
        MuteText.ERR_NOT_FOUND_USERNAME.format(token=escape(not_found)),
        not_found,
      )
    MuteDebug.log("PARSE", "target reply/explicit", target_id=target_id, target_name=target_name)
  else:
    if not body:
      return ParseError("no_target", MuteText.ERR_NO_TARGET, "no reply and empty body")
    if _body_starts_with_duration(body) or parse_duration(body[0]):
      return ParseError(
        "no_target",
        MuteText.ERR_NEED_TARGET,
        f"starts with duration: {' '.join(body[:3])}",
      )
    first = body[0]
    target_id, target_name, target_username = await _lookup_target_by_token(
      first, source_chat_id=source_chat_id,
    )
    if not target_id:
      if first.startswith("@"):
        return ParseError("user_not_found", MuteText.ERR_NOT_FOUND_USERNAME.format(token=escape(first)), first)
      if first.isdigit():
        return ParseError("user_not_found", MuteText.ERR_NOT_FOUND_ID.format(token=escape(first)), first)
      return ParseError("user_not_found", MuteText.ERR_NOT_FOUND_NAME.format(token=escape(first)), first)
    rest = body[1:]
    MuteDebug.log("PARSE", "target from token", token=first, target_id=target_id)

  dur_text, reason, _ = _extract_duration_and_reason(rest, 0)
  if not dur_text:
    return ParseError("no_duration", MuteText.ERR_NO_DURATION, f"rest={rest}")
  parsed = parse_duration(dur_text)
  if not parsed:
    return ParseError("bad_duration", MuteText.ERR_BAD_DURATION.format(duration=escape(dur_text)), dur_text)

  time_delta, duration_minutes = parsed
  time_delta = _normalize_time_delta(time_delta)
  mute_until = _rebase_expiry_at_now(time_delta)
  scope = _mute_command_scope(text)

  return ParsedMute(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    duration_text=dur_text,
    time_delta=time_delta,
    duration_minutes=duration_minutes,
    mute_until=mute_until,
    reason=reason,
    scope=scope,
  )


# ---------------------------------------------------------------------------
# Группы проекта (таблица chat)
# ---------------------------------------------------------------------------

def _clean_chat_field(value: Optional[str]) -> str:
  return (value or "").strip()


def _is_usable_chat_field(value: str) -> bool:
  return value.lower() not in _INVALID_CHAT_STRINGS


async def _fetch_chat_display_from_db(chat_id: int) -> Optional[ChatDisplay]:
  pool = _db().pool
  if not pool:
    return None
  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow(
        "SELECT chat_id, namechat, usernamechat, chatlink FROM chat WHERE chat_id = $1",
        chat_id,
      )
    if not row:
      return None
    title = _clean_chat_field(row["namechat"]) or "Группа проекта"
    username = _clean_chat_field(row["usernamechat"])
    chatlink = _clean_chat_field(row["chatlink"])
    link_url: Optional[str] = None
    if _is_usable_chat_field(username):
      link_url = f"https://t.me/{username.lstrip('@')}"
    elif _is_usable_chat_field(chatlink):
      link_url = chatlink if chatlink.startswith("http") else f"https://{chatlink}"
    return ChatDisplay(chat_id=chat_id, title=title, link_url=link_url)
  except Exception as e:
    MuteDebug.error("CHAT", "fetch db", e, chat_id=chat_id)
    return None


async def _get_chat_display(chat_id: int) -> ChatDisplay:
  if chat_id < 0:
    disp = await _fetch_chat_display_from_db(chat_id)
    if disp:
      return disp
    try:
      tg_chat = await _bot().get_chat(chat_id)
      title = tg_chat.title or "Группа проекта"
      link_url: Optional[str] = None
      if tg_chat.username:
        link_url = f"https://t.me/{tg_chat.username}"
      elif getattr(tg_chat, "invite_link", None):
        link_url = tg_chat.invite_link
      return ChatDisplay(chat_id=chat_id, title=title, link_url=link_url)
    except Exception as e:
      MuteDebug.log("CHAT", "telegram fallback skip", chat_id=chat_id, err=str(e))
  return ChatDisplay(chat_id=chat_id, title="Группа проекта", link_url=None)


def _format_chat_line(disp: ChatDisplay) -> str:
  label = escape(disp.title)
  if disp.link_url:
    return f"<b><tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> Группа : <a href='{escape(disp.link_url)}'>{label}</a></b>"
  return f"<b><tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> Группа :</b> <b>{label}</b>"


def _chat_link_inline(disp: ChatDisplay) -> str:
  """Короткое кликабельное имя группы для перечислений (без иконки/префикса)."""
  label = escape((disp.title or "группа проекта").strip())
  if disp.link_url:
    return f"<a href='{escape(disp.link_url)}'>{label}</a>"
  return label


async def _other_groups_line(current_chat_id: int, affected_chat_ids: List[int]) -> str:
  """Строка-перечисление ДРУГИХ официальных групп (кроме текущей), где было
  выдано/снято наказание.

  Возвращает пустую строку, если других групп нет (наказание было только в
  текущей группе) - тогда сообщение остаётся коротким и без лишних деталей.
  """
  others: List[int] = []
  seen = set()
  for cid in affected_chat_ids:
    if cid == current_chat_id or cid in seen or not _is_staff_chat(cid):
      continue
    seen.add(cid)
    others.append(cid)
  if not others:
    return ""
  names: List[str] = []
  for cid in others:
    disp = await _get_chat_display(cid)
    names.append(_chat_link_inline(disp))
  return (
    "\n<blockquote><i>🌐 Также в группах проекта: "
    + ", ".join(names)
    + "</i></blockquote>"
  )


async def _format_chats_line(
  chat_ids: List[int], *, current_chat_id: Optional[int] = None
) -> str:
  """Строка «💬 Группа(ы) :» со списком ВСЕХ затронутых официальных групп.

  Все группы, где пользователь был наказан / снова может писать, перечисляются
  прямо в этой строке (текущая - первой), каждая как кликабельная ссылка. Это
  заменяет связку «💬 Группа» + отдельная строка «Также в группах проекта»:
  получается одна аккуратная строка, на которую приятно смотреть.

  Слово склоняется: одна группа → «Группа», несколько → «Группы».
  """
  ordered: List[int] = []
  seen: set = set()
  if current_chat_id is not None and _is_staff_chat(current_chat_id):
    ordered.append(current_chat_id)
    seen.add(current_chat_id)
  for cid in chat_ids:
    if cid in seen or not _is_staff_chat(cid):
      continue
    seen.add(cid)
    ordered.append(cid)
  if not ordered and current_chat_id is not None:
    ordered.append(current_chat_id)
  if not ordered:
    return ""
  names: List[str] = []
  for cid in ordered:
    disp = await _get_chat_display(cid)
    names.append(_chat_link_inline(disp))
  word = "Группа" if len(names) == 1 else "Группы"
  return (
    f"<b><tg-emoji emoji-id='6030863729808120196'>💬</tg-emoji> {word} : "
    + ", ".join(names)
    + "</b>"
  )


# ---------------------------------------------------------------------------
# БД
# ---------------------------------------------------------------------------

async def _ensure_mute_schema() -> None:
  global _schema_ready, _activity_schema_ready
  if _schema_ready:
    return
  pool = _db().pool
  if not pool:
    return
  try:
    async with pool.acquire() as conn:
      await conn.execute(
        "ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS chat_id BIGINT",
      )
      # Охват наказания в архиве: 'chat' / 'all' / 'full'. Общая миграция для
      # ВСЕХ систем (мут/кик/бан/варн и снятия) - _ensure_mute_schema вызывается
      # в каждом флоу до записи в staff_actions (тем же путём, что и chat_id
      # выше), поэтому колонка гарантированно существует к моменту INSERT.
      await conn.execute(
        "ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS scope TEXT",
      )
      # Токен бота, получившего фото-пруф (file_id валиден только для него).
      # Общая миграция для всех систем: пишется рядом с proof_media_id, чтобы
      # архив мог скачать фото именно «другим ботом» модерации. Только сервер.
      await conn.execute(
        "ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS proof_bot_token TEXT",
      )
      # Постоянный учёт активных мутов (аналогично active_bans): нужен для
      # сводки «наказания» и восстановления после рестарта. chat_id = 0 -
      # охват «во всех официальных группах» (scope='all').
      await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_mutes (
          user_id         BIGINT      NOT NULL,
          chat_id         BIGINT      NOT NULL,
          mute_until      TIMESTAMP   NOT NULL,
          target_name     TEXT,
          target_username TEXT,
          admin_user_id   BIGINT,
          admin_name      TEXT,
          admin_role      TEXT,
          reason          TEXT,
          scope           TEXT,
          created_at      TIMESTAMP   DEFAULT NOW(),
          PRIMARY KEY (user_id, chat_id)
        )
        """,
      )
      # Лёгкий учёт активности сотрудников: момент последнего сообщения,
      # замеченного ботом. Нужен, чтобы статус «в сети» переживал рестарт бота.
      # Запись обновляется с тротлингом (раз в ~30с на админа), поэтому почти
      # не нагружает БД. Столбец slot - момент последней активности.
      exists = await conn.fetchval(
        "SELECT to_regclass('public.admin_activity') IS NOT NULL",
      )
      if not exists:
        await conn.execute(
          """
          CREATE TABLE admin_activity (
            admin_user_id BIGINT      PRIMARY KEY,
            slot          TIMESTAMPTZ NOT NULL
          )
          """,
        )
    _schema_ready = True
    _activity_schema_ready = True
    MuteDebug.log("SCHEMA", "staff_actions.chat_id + active_mutes + admin_activity ready")
  except Exception as e:
    MuteDebug.error("SCHEMA", "ensure", e)
  await load_staff_rules()


async def _get_last_mute_record(chat_id: int, target_user_id: int) -> Optional[LastMuteRecord]:
  pool = _db().pool
  if not pool:
    return None
  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow(
        """
        SELECT sa.admin_user_id, sa.admin_name, sa.reason, aa.role AS admin_role
        FROM staff_actions sa
        LEFT JOIN admin_accounts aa ON aa.user_id = sa.admin_user_id
        WHERE sa.action_type = 'mute'
          AND sa.target_player_id = $1
          AND (sa.chat_id = $2 OR sa.chat_id IS NULL)
        ORDER BY sa.id DESC
        LIMIT 1
        """,
        target_user_id, chat_id,
      )
    if row and row["admin_user_id"]:
      return LastMuteRecord(
        admin_user_id=int(row["admin_user_id"]),
        admin_name=row["admin_name"] or str(row["admin_user_id"]),
        admin_role=row["admin_role"],
        mute_reason=(row["reason"] or "").strip() or "Не указана",
      )
  except Exception as e:
    MuteDebug.error("DB", "last mute record", e, chat_id=chat_id, user=target_user_id)
  return None


async def _get_last_mute_admin(chat_id: int, target_user_id: int) -> Optional[Tuple[int, str]]:
  rec = await _get_last_mute_record(chat_id, target_user_id)
  if rec:
    return rec.admin_user_id, rec.admin_name
  return None


async def _get_last_mute_record_any(target_user_id: int) -> Optional[LastMuteRecord]:
  """Последний мут пользователя без привязки к конкретному чату.

  Нужно для атрибуции администратора при авто-размуте мутов с охватом «все
  группы» (там исходный чат не сохраняется в active_mutes)."""
  pool = _db().pool
  if not pool:
    return None
  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow(
        """
        SELECT sa.admin_user_id, sa.admin_name, sa.reason, aa.role AS admin_role
        FROM staff_actions sa
        LEFT JOIN admin_accounts aa ON aa.user_id = sa.admin_user_id
        WHERE sa.action_type = 'mute' AND sa.target_player_id = $1
        ORDER BY sa.id DESC
        LIMIT 1
        """,
        target_user_id,
      )
    if row and row["admin_user_id"]:
      return LastMuteRecord(
        admin_user_id=int(row["admin_user_id"]),
        admin_name=row["admin_name"] or str(row["admin_user_id"]),
        admin_role=row["admin_role"],
        mute_reason=(row["reason"] or "").strip() or "Не указана",
      )
  except Exception as e:
    MuteDebug.error("DB", "last mute record any", e, user=target_user_id)
  return None


async def get_proof_file_url(proof_media_id: str) -> Optional[str]:
  if not proof_media_id:
    return None
  try:
    bot = _bot()
    tg_file = await bot.get_file(proof_media_id)
    if tg_file and tg_file.file_path:
      return f"https://api.telegram.org/file/bot{bot.token}/{tg_file.file_path}"
  except Exception as e:
    MuteDebug.error("FILE", "get_proof_file_url", e, file_id=proof_media_id[:30])
  return None


def _proof_owner_token(proof_media_id: Optional[str]) -> Optional[str]:
  """Токен бота, ПОЛУЧИВШЕГО фото-пруф (Telegram file_id валиден только для него).

  Пишется в staff_actions.proof_bot_token рядом с proof_media_id всеми системами
  наказаний (мут/кик/бан/варн). Пруф снимает бот модерации (_bot()), поэтому его
  токен и есть владелец file_id. Админ-панель хранит токен в БД и скачивает фото
  именно им (даже если это «другой бот», чей токен серверу неизвестен). Токен
  используется ТОЛЬКО на сервере (photo-proxy отдаёт байты) и клиенту не уходит.
  """
  if not proof_media_id:
    return None
  try:
    return _bot().token or None
  except Exception:
    return None


async def get_admin_account(
  user_id: int,
  *,
  force_refresh: bool = False,
) -> Optional[AdminAccount]:
  """Загружает запись сотрудника из admin_accounts (с коротким кэшем)."""
  from bot.admins.punish_proof import coerce_telegram_user_id
  user_id = coerce_telegram_user_id(user_id)
  if user_id is None:
    return None

  if not force_refresh:
    cached = _admin_account_cache.get(user_id)
    if cached and time.time() - cached[1] < cfg.ADMIN_ACCOUNT_CACHE_SEC:
      return cached[0]

  pool = _db().pool
  if not pool:
    MuteDebug.log("AUTH", "no db pool", user_id=user_id)
    return None

  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow(
        """
        SELECT user_id, role, status, availability, availability_until,
               username, first_name
        FROM admin_accounts
        WHERE user_id = $1
        """,
        user_id,
      )
  except Exception as e:
    MuteDebug.error("DB", "admin_accounts fetch", e, user_id=user_id)
    return None

  if not row:
    _admin_account_cache.pop(user_id, None)
    return None

  account = AdminAccount(
    user_id=int(row["user_id"]),
    role=row["role"],
    status=row["status"] or "",
    availability=row["availability"] or "",
    availability_until=row["availability_until"],
    username=row["username"],
    first_name=row["first_name"],
  )
  _admin_account_cache[user_id] = (account, time.time())
  if account.role:
    _track_known_admin(user_id)
  MuteDebug.log(
    "AUTH", "account loaded",
    user_id=user_id, role=account.role, status=account.status,
    availability=account.availability, operational=account.is_operational(),
  )
  return account


def invalidate_admin_account_cache(user_id: Optional[int] = None) -> None:
  if user_id is None:
    _admin_account_cache.clear()
  else:
    _admin_account_cache.pop(user_id, None)


async def _get_staff_role(user_id: int) -> Optional[str]:
  account = await get_admin_account(user_id)
  return account.role if account else None


async def is_staff_admin(user_id: int, action: str = "mute") -> bool:
  await load_staff_rules()
  account = await get_admin_account(user_id)
  if not account:
    MuteDebug.log("AUTH", "check denied", user_id=user_id, action=action, reason="no_account")
    return False
  ok = await account.can_perform(action)
  rule = await get_staff_rule(account.role)
  schema = await get_staff_rules_schema()
  perm_col = schema.column_for_action(action)
  MuteDebug.log(
    "AUTH", "check",
    user_id=user_id, role=account.role, status=account.status,
    availability=account.availability, action=action, allowed=ok,
    staff_rules_perm=rule.permissions.get(perm_col) if rule else None,
    perm_column=perm_col,
  )
  return ok


async def _resolve_admin_identity(message: Message) -> Tuple[str, Optional[str], Optional[AdminAccount]]:
  """Имя, роль и запись admin_accounts для текущего пользователя."""
  account = await get_admin_account(message.from_user.id)
  if account:
    return account.display_name, account.role, account
  return _admin_display_name(message), None, None


async def _format_staff_line_from_user(user_id: int, message: Optional[Message] = None) -> str:
  if message and message.from_user and message.from_user.id == user_id:
    staff = await StaffRef.from_message(message)
    return staff.line
  staff = await StaffRef.from_user_id(user_id)
  return staff.line


async def _apply_mute_restrictions(
  user_id: int,
  until: datetime,
  *,
  scope: Scope,
  source_chat_id: int,
) -> bool:
  """Применяет ограничение в Telegram с учётом охвата команды."""
  if scope == "all":
    return await _restrict_in_all_staff_chats(user_id, until)
  if not _is_staff_chat(source_chat_id):
    return False
  ok = await _restrict_in_chat(source_chat_id, user_id, until)
  if ok:
    _register_chat_mute(source_chat_id, user_id, until)
  return ok


async def _apply_mute_db(
  target_user_id: int,
  target_name: str,
  target_username: Optional[str],
  mute_until: datetime,
  admin_user_id: int,
  admin_name: str,
  reason: str,
  proof_media_id: str,
  duration_minutes: int,
  chat_id: int,
  *,
  scope: Scope = "chat",
) -> Tuple[bool, Optional[int]]:
  try:
    db = _db()
    async with db.pool.acquire() as conn:
      async with conn.transaction():
        if scope == "all":
          await conn.execute(
            """
            INSERT INTO users (user_id, first_name, username, mute_until)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET mute_until = EXCLUDED.mute_until,
                first_name = COALESCE(users.first_name, EXCLUDED.first_name),
                username   = COALESCE(users.username, EXCLUDED.username)
            """,
            target_user_id, target_name, target_username, mute_until,
          )
        else:
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
        row = await conn.fetchrow(
          """
          INSERT INTO staff_actions (
            admin_user_id, admin_name, action_type,
            target_player_id, target_name,
            reason, proof_media_id, duration_minutes, chat_id, scope,
            proof_bot_token
          )
          VALUES ($1, $2, 'mute', $3, $4, $5, $6, $7, $8, $9, $10)
          RETURNING id
          """,
          admin_user_id, admin_name, target_user_id, target_name,
          reason, proof_media_id, duration_minutes, chat_id, scope,
          _proof_owner_token(proof_media_id),
        )
        action_id = row["id"] if row else None
        MuteDebug.log(
          "DB", "mute saved",
          target=target_user_id, until=str(mute_until), chat_id=chat_id,
          scope=scope, proof=proof_media_id[:24], action_id=action_id,
        )
        return True, action_id
  except Exception as e:
    MuteDebug.error("DB", "apply_mute", e, target=target_user_id)
    return False, None


async def _clear_mute_db(
  target_user_id: int,
  admin_user_id: int,
  admin_name: str,
  target_name: str,
  chat_id: int,
  reason: str = "Размут сотрудником",
  scope: Scope = "chat",
) -> bool:
  try:
    async with _db().pool.acquire() as conn:
      async with conn.transaction():
        await conn.execute("UPDATE users SET mute_until = NULL WHERE user_id = $1", target_user_id)
        # Снимаем постоянный учёт активного мута во всех группах пользователя.
        await conn.execute("DELETE FROM active_mutes WHERE user_id = $1", target_user_id)
        await conn.execute(
          """
          INSERT INTO staff_actions (
            admin_user_id, admin_name, action_type,
            target_player_id, target_name, reason, chat_id, scope
          )
          VALUES ($1, $2, 'unmute', $3, $4, $5, $6, $7)
          """,
          admin_user_id, admin_name, target_user_id, target_name, reason, chat_id, scope,
        )
    return True
  except Exception as e:
    MuteDebug.error("DB", "clear_mute", e)
    return False


async def _log_auto_unmute_db(
  target_user_id: int,
  target_name: str,
  chat_id: int,
  scope: Scope = "chat",
) -> None:
  try:
    async with _db().pool.acquire() as conn:
      await conn.execute(
        """
        INSERT INTO staff_actions (
          admin_user_id, admin_name, action_type,
          target_player_id, target_name, reason, chat_id, scope
        )
        VALUES (0, 'Система', 'unmute', $1, $2, 'Срок мута истёк', $3, $4)
        """,
        target_user_id, target_name, chat_id, scope,
      )
  except Exception as e:
    MuteDebug.error("DB", "auto_unmute log", e, user=target_user_id, chat_id=chat_id)


async def _fetch_db_mute_until(user_id: int) -> Optional[datetime]:
  """Активный mute_until из users или None."""
  pool = _db().pool
  if not pool:
    return None
  try:
    async with pool.acquire() as conn:
      row = await conn.fetchrow("SELECT mute_until FROM users WHERE user_id = $1", user_id)
    if not row or not row["mute_until"]:
      return None
    until = row["mute_until"]
    if not _is_datetime_active(until):
      return None
    return until
  except Exception as e:
    MuteDebug.error("DB", "mute_until", e, user_id=user_id)
    return None


async def _is_player_muted_in_db(user_id: int) -> bool:
  return await _fetch_db_mute_until(user_id) is not None


# ---------------------------------------------------------------------------
# Постоянный учёт активных мутов (active_mutes) - источник для сводки «наказания»
# ---------------------------------------------------------------------------

def _mute_record_chat_ids(scope: Scope, source_chat_id: int) -> List[int]:
  """Группы, для которых сохраняем запись об активном муте.

  • scope='all'  → один обобщённый ряд chat_id = 0 («во всех группах»);
  • scope='chat' → конкретная официальная группа (если это staff-чат).
  """
  if scope == "all":
    return [0]
  if _is_staff_chat(source_chat_id):
    return [source_chat_id]
  return []


async def _record_active_mute(
  parsed: ParsedMute,
  *,
  source_chat_id: int,
  admin_user_id: int,
  admin_name: str,
  admin_role: Optional[str],
) -> None:
  """Сохраняет активный мут для сводки «наказания» и восстановления после рестарта."""
  chat_ids = _mute_record_chat_ids(parsed.scope, source_chat_id)
  if not chat_ids:
    return
  await _ensure_mute_schema()
  if not _schema_ready:
    return
  try:
    async with _db_acquire() as conn:
      async with conn.transaction():
        for cid in chat_ids:
          await conn.execute(
            """
            INSERT INTO active_mutes (
              user_id, chat_id, mute_until, target_name, target_username,
              admin_user_id, admin_name, admin_role, reason, scope
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (user_id, chat_id) DO UPDATE
            SET mute_until      = EXCLUDED.mute_until,
                target_name     = EXCLUDED.target_name,
                target_username = EXCLUDED.target_username,
                admin_user_id   = EXCLUDED.admin_user_id,
                admin_name      = EXCLUDED.admin_name,
                admin_role      = EXCLUDED.admin_role,
                reason          = EXCLUDED.reason,
                scope           = EXCLUDED.scope,
                created_at      = NOW()
            """,
            parsed.target_id, cid, parsed.mute_until,
            parsed.target_name, parsed.target_username,
            admin_user_id, admin_name, admin_role, parsed.reason, parsed.scope,
          )
    MuteDebug.log(
      "DB", "active mute recorded",
      target=parsed.target_id, chats=chat_ids, until=str(parsed.mute_until), scope=parsed.scope,
    )
  except DbUnavailableError as e:
    MuteDebug.log("DB", "record active mute skipped", err=str(e))
  except Exception as e:
    MuteDebug.error("DB", "record active mute", e, target=parsed.target_id)


async def _delete_active_mutes(user_id: int, chat_id: Optional[int] = None) -> None:
  """Снимает запись(и) об активном муте. chat_id=None → все группы пользователя."""
  pool = _db().pool
  if not pool:
    return
  try:
    async with _db_acquire() as conn:
      if chat_id is None:
        await conn.execute("DELETE FROM active_mutes WHERE user_id = $1", user_id)
      else:
        # Удаляем как локальную запись группы, так и обобщённую (scope='all').
        await conn.execute(
          "DELETE FROM active_mutes WHERE user_id = $1 AND chat_id IN ($2, 0)",
          user_id, chat_id,
        )
  except Exception as e:
    MuteDebug.log("DB", "delete active mute skip", err=str(e), user=user_id, chat=chat_id)


async def list_active_mutes_for_user(user_id: int) -> List[Dict[str, Any]]:
  """Активные (ещё не истёкшие) муты пользователя по группам.

  Используется сводкой «наказания». Возвращает список словарей с ключами:
  chat_id, mute_until, reason, admin_name, admin_role, scope.
  Истёкшие ряды пропускаются (их снимет авто-размут).
  """
  await _ensure_mute_schema()
  if not _schema_ready:
    return []
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT chat_id, mute_until, reason, admin_name, admin_role, scope
        FROM active_mutes
        WHERE user_id = $1
        ORDER BY mute_until
        """,
        user_id,
      )
  except Exception as e:
    MuteDebug.log("DB", "list active mutes skip", err=str(e), user=user_id)
    return []
  out: List[Dict[str, Any]] = []
  for r in rows:
    until = r["mute_until"]
    if until is not None and not _is_datetime_active(until):
      continue
    out.append(dict(r))
  return out


def _format_until_or_forever(until: datetime) -> str:
  """Дата окончания или «навсегда» для очень больших сроков."""
  try:
    remaining = (_to_utc(until) - _utc_now()).total_seconds()
  except Exception:
    remaining = 0
  if remaining >= _FOREVER_THRESHOLD_SEC:
    return "навсегда"
  return _format_until(until)


def _memory_mute_until(user_id: int) -> Optional[datetime]:
  """Самый поздний срок мута из оперативного кэша по группам проекта."""
  now = _utc_now()
  best: Optional[datetime] = None
  for cid in cfg.STAFF_CHAT_IDS:
    until = _chat_mutes.get((cid, user_id))
    if until and _to_utc(until) > now and (best is None or _to_utc(until) > _to_utc(best)):
      best = until
  return best


def _telegram_member_is_muted(member: Any) -> bool:
  """
  Проверяет через объект ChatMember, что пользователь не может писать в группе.
  Совместимо с aiogram 2/3 (проверка по status и полям).
  """
  if getattr(member, "status", None) != "restricted":
    return False
  if getattr(member, "is_member", True) is False:
    return False
  return getattr(member, "can_send_messages", True) is False


def _telegram_member_mute_until(member: Any) -> Optional[datetime]:
  until = getattr(member, "until_date", None)
  if not until:
    return None
  if not _is_datetime_active(until):
    return None
  return until


async def _check_telegram_mute_in_chat(
  chat_id: int,
  user_id: int,
) -> Tuple[bool, Optional[datetime]]:
  """Статус ограничения пользователя в одной группе через Telegram API."""
  if chat_id > 0:
    return False, None
  try:
    member = await _bot().get_chat_member(chat_id, user_id)
  except Exception as e:
    MuteDebug.log(
      "TG", "get_chat_member",
      chat_id=chat_id, user_id=user_id, err=str(e),
    )
    return False, None
  if not _telegram_member_is_muted(member):
    return False, None
  return True, _telegram_member_mute_until(member)


async def _scan_telegram_mute_state(
  user_id: int,
) -> Tuple[bool, Tuple[int, ...], Optional[datetime]]:
  """Проверяет ограничение во всех официальных группах проекта."""
  if not cfg.STAFF_CHAT_IDS:
    return False, (), None
  chat_ids = tuple(cfg.STAFF_CHAT_IDS)
  results = await asyncio.gather(
    *(_check_telegram_mute_in_chat(cid, user_id) for cid in chat_ids),
  )
  muted_chats: List[int] = []
  until_best: Optional[datetime] = None
  for cid, (muted, until) in zip(chat_ids, results):
    if not muted:
      continue
    muted_chats.append(cid)
    if until and (until_best is None or _to_utc(until) > _to_utc(until_best)):
      until_best = until
  return bool(muted_chats), tuple(muted_chats), until_best


@dataclass
class PlayerMuteState:
  """Сводный статус мута: база, память бота и фактическое ограничение в Telegram."""
  in_db: bool = False
  in_memory: bool = False
  in_telegram: bool = False
  telegram_chats: Tuple[int, ...] = ()
  db_until: Optional[datetime] = None
  memory_until: Optional[datetime] = None
  telegram_until: Optional[datetime] = None

  @property
  def is_muted(self) -> bool:
    return self.in_db or self.in_memory or self.in_telegram

  @property
  def needs_db_sync(self) -> bool:
    """В Telegram ограничен, но в базе активной записи нет."""
    return self.in_telegram and not self.in_db


async def _resolve_player_mute_state(user_id: int) -> PlayerMuteState:
  """
  Определяет, находится ли пользователь в муте.
  Источники: users.mute_until, кэш бота, get_chat_member по группам проекта.
  """
  state = PlayerMuteState()
  state.db_until = await _fetch_db_mute_until(user_id)
  state.in_db = state.db_until is not None
  state.memory_until = _memory_mute_until(user_id)
  state.in_memory = state.memory_until is not None
  tg_muted, tg_chats, tg_until = await _scan_telegram_mute_state(user_id)
  state.in_telegram = tg_muted
  state.telegram_chats = tg_chats
  state.telegram_until = tg_until
  MuteDebug.log(
    "MUTE_STATE", "resolved",
    user_id=user_id,
    in_db=state.in_db,
    in_memory=state.in_memory,
    in_telegram=state.in_telegram,
    tg_chats=list(state.telegram_chats),
  )
  return state


def _register_chat_mute(chat_id: int, user_id: int, until: datetime) -> None:
  if chat_id < 0 and _is_staff_chat(chat_id):
    _chat_mutes[(chat_id, user_id)] = until
    MuteDebug.log("CHAT_MUTE", "registered", chat_id=chat_id, user_id=user_id, until=str(until))


def _clear_chat_mute(chat_id: int, user_id: int) -> None:
  key = (chat_id, user_id)
  if key in _chat_mutes:
    _chat_mutes.pop(key, None)
    MuteDebug.log("CHAT_MUTE", "cleared", chat_id=chat_id, user_id=user_id)


def _is_muted_in_chat(chat_id: int, user_id: int) -> bool:
  until = _chat_mutes.get((chat_id, user_id))
  if not until:
    return False
  if not _is_datetime_active(until):
    _chat_mutes.pop((chat_id, user_id), None)
    return False
  return True


def _until_to_telegram_date(until: Optional[datetime]) -> Optional[Union[int, datetime]]:
  if until is None:
    return None
  remaining = (until - datetime.now()).total_seconds()
  if remaining >= _FOREVER_THRESHOLD_SEC or remaining > _TELEGRAM_MAX_TIMED_SEC:
    return None
  if remaining < 30:
    return None
  return _safe_unix_timestamp(until)


async def _restrict_in_chat(chat_id: int, user_id: int, until: Optional[datetime]) -> bool:
  if chat_id > 0:
    return True
  try:
    bot = _bot()
    until_arg = _until_to_telegram_date(until)
    await bot.restrict_chat_member(
      chat_id=chat_id,
      user_id=user_id,
      permissions=_PERM_MUTE,
      until_date=until_arg,
    )
    MuteDebug.log("TG", "restrict OK", chat_id=chat_id, user_id=user_id, until=str(until))
    return True
  except Exception as e:
    from bot.admins.punish_validate import is_invalid_telegram_user_error
    if is_invalid_telegram_user_error(e):
      MuteDebug.log("TG", "restrict invalid user", chat_id=chat_id, user_id=user_id)
      return False
    MuteDebug.error("TG", "restrict", e, chat_id=chat_id, user_id=user_id)
    return False


async def _restrict_in_all_staff_chats(user_id: int, until: Optional[datetime]) -> bool:
  """Ограничивает пользователя во всех официальных группах проекта."""
  ok_any = False
  for cid in cfg.STAFF_CHAT_IDS:
    if await _restrict_in_chat(cid, user_id, until):
      ok_any = True
      _register_chat_mute(cid, user_id, until)
  return ok_any


async def _unrestrict_in_all_staff_chats(user_id: int) -> None:
  """Снимает ограничение во всех официальных группах проекта."""
  for cid in cfg.STAFF_CHAT_IDS:
    await _unrestrict_in_chat(cid, user_id)
    _clear_chat_mute(cid, user_id)


def _clear_mute_all_staff_chats(user_id: int) -> None:
  for cid in cfg.STAFF_CHAT_IDS:
    _clear_chat_mute(cid, user_id)


async def _unrestrict_in_chat(chat_id: int, user_id: int) -> bool:
  if chat_id > 0:
    return True
  try:
    await _bot().restrict_chat_member(
      chat_id=chat_id,
      user_id=user_id,
      permissions=_PERM_FULL,
      until_date=None,
    )
    MuteDebug.log("TG", "unrestrict OK", chat_id=chat_id, user_id=user_id)
    return True
  except Exception as e:
    MuteDebug.error("TG", "unrestrict", e, chat_id=chat_id, user_id=user_id)
    return False


async def _notify_unmute(
  source_chat_id: int,
  target_user_id: int,
  target_name: str,
  target_username: Optional[str] = None,
  *,
  event: str,
  acting_admin_id: Optional[int] = None,
  acting_admin_name: Optional[str] = None,
  acting_admin_role: Optional[str] = None,
  acting_admin_username: Optional[str] = None,
  cancelled: bool = False,
  mute_reason: Optional[str] = None,
  broadcast_groups: bool = True,
  notify_chats: Optional[List[int]] = None,
) -> None:
  """Уведомляет нарушителя, сотрудника и группы проекта о снятии ограничения.

  • notify_chats - конкретные группы, куда слать уведомление. Если None -
    все официальные группы (используется при ручном размуте). Для авто-снятия
    сюда передаётся точный список затронутых групп, и в каждой указываются
    ДРУГИЕ группы, где наказание тоже было снято.
  • broadcast_groups=False - не слать групповые сообщения (снятие кнопкой:
    исходное сообщение редактируется на месте).
  """
  # Анти-дубликат: при авто-истечении несколько фоновых триггеров могут
  # вызвать снятие почти одновременно - пропускаем повторное уведомление.
  if event == "expired":
    now_ts = time.monotonic()
    last_ts = _recent_auto_unmute.get(target_user_id)
    if last_ts is not None and (now_ts - last_ts) < _AUTO_UNMUTE_DEDUP_SEC:
      MuteDebug.log("NOTIFY", "dup auto-unmute suppressed", user_id=target_user_id)
      return
    _recent_auto_unmute[target_user_id] = now_ts

  player = PlayerRef(target_user_id, target_name, target_username)
  reason_line = _format_mute_reason_block(mute_reason)
  reason_suffix = f"\n{reason_line}" if reason_line else ""

  chats = list(notify_chats) if notify_chats is not None else list(cfg.STAFF_CHAT_IDS)

  staff: Optional[StaffRef] = None
  if acting_admin_id and acting_admin_name:
    account = await get_admin_account(acting_admin_id)
    if account:
      staff = StaffRef.from_account(account)
    else:
      staff = StaffRef(
        acting_admin_id, acting_admin_name, acting_admin_role, acting_admin_username,
      )
  elif event == "expired":
    last = await _get_last_mute_record(source_chat_id, target_user_id)
    if not last:
      last = await _get_last_mute_record_any(target_user_id)
    if last:
      account = await get_admin_account(last.admin_user_id)
      if account:
        staff = StaffRef.from_account(account)
      else:
        staff = StaffRef(last.admin_user_id, last.admin_name, last.admin_role)

  staff_line = f"{staff.line}\n" if staff else ""
  actor = staff.actor if staff else "<i>-</i>"

  if event == "expired":
    violator_text = MuteText.EXPIRED_VIOLATOR.format(greeting=player.greeting, reason_suffix=reason_suffix)
    admin_text = MuteText.EXPIRED_ADMIN.format(
      player_line=player.line, staff_line=staff_line,
      reason_suffix=reason_suffix, player_short=player.short,
    )
    group_footer = MuteText.EXPIRED_GROUP_FOOTER.format(player_short=player.short)
    group_title = MuteText.EXPIRED_TITLE
  elif cancelled:
    violator_text = MuteText.CANCELLED_VIOLATOR.format(
      greeting=player.greeting, staff_line=staff_line, actor=actor, reason_suffix=reason_suffix,
    )
    admin_text = MuteText.CANCELLED_ADMIN.format(
      player_line=player.line, staff_line=staff_line,
      reason_suffix=reason_suffix, player_short=player.short,
    )
    group_footer = MuteText.CANCELLED_GROUP_FOOTER.format(actor=actor, player_short=player.short)
    group_title = MuteText.CANCELLED_TITLE
  else:
    violator_text = MuteText.MANUAL_VIOLATOR.format(
      greeting=player.greeting, staff_line=staff_line, actor=actor, reason_suffix=reason_suffix,
    )
    admin_text = MuteText.MANUAL_ADMIN.format(
      player_line=player.line, staff_line=staff_line,
      reason_suffix=reason_suffix, player_short=player.short,
    )
    group_footer = MuteText.MANUAL_GROUP_FOOTER.format(actor=actor, player_short=player.short)
    group_title = MuteText.MANUAL_TITLE

  if broadcast_groups:
    for group_chat_id in chats:
      chat_line = await _format_chats_line(chats, current_chat_id=group_chat_id)
      group_text = MuteText.UNMUTE_GROUP.format(
        group_title=group_title, player_line=player.line, staff_line=staff_line,
        chat_line=chat_line, reason_suffix=reason_suffix, group_footer=group_footer,
      )
      try:
        await _bot().send_message(group_chat_id, group_text, parse_mode="HTML", link_preview_options=NO_PREVIEW)
        MuteDebug.log("NOTIFY", "group unmute sent", chat_id=group_chat_id, user_id=target_user_id)
      except Exception as e:
        MuteDebug.log("NOTIFY", "group unmute skip", chat_id=group_chat_id, err=str(e))

  try:
    await _bot().send_message(target_user_id, violator_text, parse_mode="HTML", link_preview_options=NO_PREVIEW)
  except Exception as e:
    MuteDebug.log("NOTIFY", "violator unmute skip", user_id=target_user_id, err=str(e))

  admin_ids: List[int] = []
  if acting_admin_id:
    admin_ids.append(acting_admin_id)
  elif event == "expired":
    last_admin = await _get_last_mute_admin(source_chat_id, target_user_id)
    if not last_admin:
      rec_any = await _get_last_mute_record_any(target_user_id)
      if rec_any:
        last_admin = (rec_any.admin_user_id, rec_any.admin_name)
    if last_admin:
      admin_ids.append(last_admin[0])

  for admin_id in admin_ids:
    if event == "manual" and admin_id == acting_admin_id:
      continue
    try:
      await _bot().send_message(admin_id, admin_text, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    except Exception as e:
      MuteDebug.log("NOTIFY", "admin unmute skip", admin_id=admin_id, err=str(e))


async def _notify_mute_groups(
  parsed: ParsedMute,
  source_chat_id: int,
  staff: StaffRef,
) -> None:
  """При муталл оповещает все официальные группы (кроме исходной - там уже
  показана карточка-подтверждение), чтобы было видно: ограничение применено
  во всём проекте, а не только там, где выдана команда."""
  if parsed.scope != "all":
    return
  player = PlayerRef.from_parsed(parsed)
  duration = _format_duration_short(parsed.time_delta)
  until = _format_until_display(parsed.mute_until, parsed.time_delta)
  reason_block = _format_mute_reason_block(parsed.reason, label="Причина наказания")
  for cid in cfg.STAFF_CHAT_IDS:
    if cid == source_chat_id:
      continue
    try:
      await _bot().send_message(
        cid,
        MuteText.GROUP.format(
          header=_mute_badge(parsed.scope),
          player_line=player.line,
          staff_line=f"{staff.line}\n",
          duration=duration,
          until=until,
          reason_block=reason_block,
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      MuteDebug.log("NOTIFY", "group mute sent", chat_id=cid, user_id=parsed.target_id)
    except Exception as e:
      MuteDebug.log("NOTIFY", "group mute skip", chat_id=cid, err=str(e))


async def _notify_violator_muted(parsed: ParsedMute, chat_id: int) -> None:
  if not _is_staff_chat(chat_id):
    return
  try:
    player = PlayerRef.from_parsed(parsed)
    disp = await _get_chat_display(chat_id)
    chat_line = _format_chat_line(disp)
    dur = _format_duration_short(parsed.time_delta)
    scope_text = scope_label(parsed.scope)
    await _bot().send_message(
      parsed.target_id,
      MuteText.VIOLATOR_MUTED.format(
        greeting=player.greeting, scope=scope_text, chat_line=chat_line,
        header=_mute_badge(parsed.scope),
        scope_block=_format_scope_block(parsed.scope),
        duration=dur,
        until=_format_until_display(parsed.mute_until, parsed.time_delta),
        reason_block=_format_mute_reason_block(parsed.reason, label="Причина наказания"),
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    MuteDebug.log("NOTIFY", "violator mute skip", user_id=parsed.target_id, err=str(e))


async def _enforce_muted_user_in_chat(message: Message) -> bool:
  """Удаляет сообщение замученного в этой группе. Возвращает True, если перехвачено."""
  if not message.from_user or message.chat.id > 0:
    return False
  if not _is_staff_chat(message.chat.id):
    return False

  user_id = message.from_user.id
  chat_id = message.chat.id

  if await is_staff_admin(user_id):
    return False

  _ensure_expiry_worker()
  if not await _sync_user_mute_status(chat_id, user_id):
    return False

  MuteDebug.log("ENFORCE", "delete muted message", chat_id=chat_id, user_id=user_id)
  try:
    await message.delete()
  except Exception as e:
    MuteDebug.error("ENFORCE", "delete failed", e, chat_id=chat_id, user_id=user_id)

  return True


# ---------------------------------------------------------------------------
# UI для администратора
# ---------------------------------------------------------------------------

def _admin_display_name(message: Message) -> str:
  u = message.from_user
  return u.full_name or u.first_name or str(u.id)


def _debug_hint(code: str) -> str:
  if not cfg.DEBUG_ADMIN_HINTS:
    return ""
  return f"\n\n<i>🔧 debug:</i> <code>{escape(code)}</code>"


async def _send_no_permission(message: Message, action: str = "mute") -> None:
  rules_msg = await staff_rules_status_message()
  if rules_msg:
    await message.reply(rules_msg, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return

  staff = await StaffRef.from_message(message)
  account = await get_admin_account(message.from_user.id)
  action_label = _action_public_label(action)

  if account:
    reason = await account.denial_reason(action)
  else:
    reason = "вы не зарегистрированы как сотрудник проекта"

  allowed_hint = await action_roles_hint(action)
  await message.reply(
    MuteText.NO_PERMISSION.format(
      greeting=staff.greeting,
      reason=escape(reason.capitalize()),
      action_label=escape(action_label.capitalize()),
      allowed_hint=escape(allowed_hint),
    ),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def _send_help(message: Message) -> None:
  await message.reply(
    MuteText.HELP.format(timeout=cfg.proof_timeout_minutes()),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


def _build_pending_proof_text(
  parsed: ParsedMute,
  chat_line: str,
  cancel_hint: str,
) -> str:
  return MuteText.PENDING.format(
    player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
    chat_line=chat_line,
    header=_mute_badge(parsed.scope),
    scope_block=_format_scope_block(parsed.scope),
    term_block=_pending_mute_term_block(parsed),
    reason_block=_format_mute_reason_block(parsed.reason, label="Причина наказания"),
    timeout=cfg.proof_timeout_minutes(),
    cancel_hint=escape(cancel_hint),
  )


async def _finish_pending_cancel(
  admin_id: int,
  player_line: str,
  chat_id: int,
) -> bool:
  """Отменяет ожидание фото и обновляет сообщение с кнопкой."""
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_mutes, admin_id)
  if not pending:
    return False

  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  parsed = pending.get("parsed")
  reason_line = _format_mute_reason_block(
    parsed.reason if parsed else None, label="Заявленная причина",
  )
  reason_part = f"{reason_line}\n" if reason_line else ""
  final_text = MuteText.PENDING_CANCELLED.format(
    player_line=player_line, chat_line=chat_line, reason_part=reason_part,
  )

  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        final_text,
        chat_id=prompt_chat,
        message_id=prompt_msg_id,
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
        reply_markup=None,
      )
      MuteDebug.log("FLOW", "pending prompt edited", chat_id=prompt_chat, message_id=prompt_msg_id)
      return True
    except Exception as e:
      MuteDebug.error("FLOW", "edit pending prompt", e, chat=prompt_chat, msg=prompt_msg_id)

  return False


async def _send_success_mute(
  message: Message,
  parsed: ParsedMute,
  tg_ok: bool,
  chat_id: int,
) -> None:
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  warn = MuteText.SUCCESS_WARN if (not tg_ok and chat_id < 0) else ""
  staff = await StaffRef.from_message(message)
  await message.reply(
    MuteText.SUCCESS.format(
      player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
      staff_line=staff.line,
      chat_line=chat_line,
      header=_mute_badge(parsed.scope),
      scope_block=_format_scope_block(parsed.scope),
      duration=_format_duration_short(parsed.time_delta),
      until=_format_until_display(parsed.mute_until, parsed.time_delta),
      reason_block=_format_mute_reason_block(parsed.reason, label="Причина наказания"),
      warn=warn,
    ),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_mute_revoke_keyboard(message.from_user.id, parsed.target_id),
  )


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------

async def _finalize_mute(
  message: Message,
  parsed: ParsedMute,
  proof_media_id: str,
  chat_id: int,
  admin_name: str,
) -> bool:
  # Срок отсчитывается с момента подтверждения пруфа, а не с разбора команды.
  if not proof_media_id:
    await message.reply(
      MuteText.NEED_PHOTO + _debug_hint("proof_required"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    MuteDebug.log("PROOF", "finalize blocked - no proof", target=getattr(parsed, "target_id", None))
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("mute_invalid_user_finalize"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    MuteDebug.log("TG", "mute finalize blocked - invalid user", target=parsed.target_id)
    return True
  _refresh_parsed_mute_expiry(parsed)
  ok, action_id = await _apply_mute_db(
    target_user_id=parsed.target_id,
    target_name=parsed.target_name,
    target_username=parsed.target_username,
    mute_until=parsed.mute_until,
    admin_user_id=message.from_user.id,
    admin_name=admin_name,
    reason=parsed.reason,
    proof_media_id=proof_media_id,
    duration_minutes=parsed.duration_minutes,
    chat_id=chat_id,
    scope=parsed.scope,
  )
  if not ok:
    await message.reply(MuteText.DB_ERROR + _debug_hint("db_apply_failed"), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  _ensure_expiry_worker()
  tg_ok = await _apply_mute_restrictions(
    parsed.target_id,
    parsed.mute_until,
    scope=parsed.scope,
    source_chat_id=chat_id,
  )
  try:
    from bot.admins import punish_timers
    punish_timers.register_mute(
      parsed.target_id,
      parsed.mute_until,
      target_name=parsed.target_name,
      target_username=parsed.target_username,
      source_chat_id=chat_id,
      scope=parsed.scope,
    )
  except Exception as e:
    MuteDebug.log("TIMER", "register mute skip", err=str(e), user=parsed.target_id)

  # Постоянный учёт активного мута - чтобы сводка «наказания» его показывала
  # (в т.ч. для мутов с охватом «только эта группа») и переживала рестарт.
  admin_role: Optional[str] = None
  try:
    acc = await get_admin_account(message.from_user.id)
    admin_role = acc.role if acc else None
  except Exception:
    admin_role = None
  await _record_active_mute(
    parsed,
    source_chat_id=chat_id,
    admin_user_id=message.from_user.id,
    admin_name=admin_name,
    admin_role=admin_role,
  )

  # Уведомления не должны «ронять» уже применённое наказание: мут наложен в БД и
  # Telegram - даже если отрисовка карточки/HTML по какой-то причине упадёт,
  # администратор всё равно получит подтверждение (с резервным простым текстом).
  try:
    await _send_success_mute(message, parsed, tg_ok, chat_id)
  except Exception as e:
    MuteDebug.error("NOTIFY", "success mute card failed", e, user=parsed.target_id)
    try:
      await message.reply(
        MuteText.SUCCESS_FALLBACK.format(
          duration=_format_duration_short(parsed.time_delta),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception:
      try:
        await message.reply("Ограничение выдано.")
      except Exception:
        pass
  if parsed.scope == "all":
    try:
      staff = await StaffRef.from_message(message)
      await _notify_mute_groups(parsed, chat_id, staff)
    except Exception as e:
      MuteDebug.log("NOTIFY", "group mute broadcast skip", err=str(e))
  await _notify_violator_muted(parsed, chat_id)
  return True


async def _complete_mute_with_proof(message: Message) -> bool:
  from bot.admins.punish_proof import (
    is_proof_expired,
    latest_pending_system_for,
    pending_get,
    pending_pop,
  )

  admin_id = message.from_user.id
  if latest_pending_system_for(admin_id) != "mute":
    return False

  pending = pending_get(_pending_mutes, admin_id)
  if not pending:
    MuteDebug.log("PROOF", "no pending", admin_id=admin_id)
    return False

  if is_proof_expired(pending.get("expires_at", 0)):
    pending_pop(_pending_mutes, admin_id)
    MuteDebug.log("PROOF", "late proof ignored - expired", admin_id=admin_id)
    return True

  pending_chat = pending.get("chat_id")
  if not _is_staff_chat(message.chat.id) or message.chat.id != pending_chat:
    staff = await StaffRef.from_message(message)
    parsed = pending.get("parsed")
    player_line = ""
    if parsed:
      player_line = PlayerRef.from_parsed(parsed).line + "\n"
    pending_disp = await _get_chat_display(pending_chat) if pending_chat else None
    pending_chat_line = (
      _format_chat_line(pending_disp) + "\n" if pending_disp else ""
    )
    await message.reply(
      MuteText.WRONG_CHAT.format(
        greeting=staff.greeting, staff_line=staff.line,
        player_line=player_line, pending_chat_line=pending_chat_line,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  proof_media_id = _get_proof_file_id(message)
  if not proof_media_id:
    await message.reply(MuteText.NEED_PHOTO + _debug_hint("proof_missing"), parse_mode="HTML", link_preview_options=NO_PREVIEW)
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
    debug_tag="mute_invalid_user_proof",
  ):
    pending_pop(_pending_mutes, admin_id)
    await clear_pending_prompt_keyboard(pending)
    return True

  MuteDebug.log("PROOF", "received", admin_id=admin_id, file_id=proof_media_id[:24])
  await run_finalize_with_pending_fallback(
    message, admin_id, _pending_mutes, pending,
    lambda: _finalize_mute(
      message, parsed, proof_media_id,
      pending["chat_id"], pending["admin_name"],
    ),
    on_db_unavailable=lambda: _reply_db_unavailable(message),
  )
  return True


async def _supersede_pending_mute(admin_id: int) -> None:
  """Снимает «зависшее» ожидание фото у этого администратора при начале нового
  действия мута, чтобы случайное фото позже не закрыло его повторно."""
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_mutes, admin_id)
  if not pending:
    return
  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        MuteText.PENDING_SUPERSEDED,
        chat_id=prompt_chat, message_id=prompt_msg_id,
        parse_mode="HTML", reply_markup=None, link_preview_options=NO_PREVIEW,
      )
    except Exception:
      try:
        await _bot().edit_message_reply_markup(
          chat_id=prompt_chat, message_id=prompt_msg_id, reply_markup=None,
        )
      except Exception as e:
        MuteDebug.log("PROOF", "supersede cleanup skip", err=str(e))
  MuteDebug.log("PROOF", "superseded by new mute action", admin_id=admin_id)


async def _handle_mute_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  if not await _require_staff_chat(message):
    return True

  command_text = _get_command_text(message)
  if _is_mute_command(command_text) and len(command_text.split()) == 1:
    await _send_help(message)
    return True

  result = await parse_mute_command(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    MuteDebug.log("PARSE", "error", code=result.code, info=result.debug_info)
    return True

  parsed = result

  # Муталл (охват «все официальные группы») требует отдельного права muteall в
  # staff_rules. Базовое право mute уже проверено в mute_process; здесь, при
  # глобальном охвате, дополнительно проверяем доступ именно к муталлу.
  if parsed.scope == "all":
    perm_all = await check_staff_permission(message.from_user.id, "muteall")
    if perm_all == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm_all != "allowed":
      MuteDebug.log("AUTH", "muteall denied", user_id=message.from_user.id)
      return await deny_permission(message, "muteall")

  if is_protected_creator(parsed.target_id):
    await message.reply(protected_creator_denied_html(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    MuteDebug.log("AUTH", "protected creator blocked", target=parsed.target_id)
    return True
  if parsed.target_id == message.from_user.id:
    await message.reply(MuteText.SELF, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if parsed.target_id == _bot().id:
    await message.reply(MuteText.BOT, parse_mode="HTML", link_preview_options=NO_PREVIEW)
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("mute_invalid_user"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    MuteDebug.log("TG", "mute blocked - invalid user", target=parsed.target_id)
    return True

  proof_id = _get_proof_file_id(message)
  admin_name, admin_role, _admin_account = await _resolve_admin_identity(message)
  chat_id = message.chat.id

  # Новое действие мута отменяет прежнее «зависшее» ожидание этого админа.
  await _supersede_pending_mute(message.from_user.id)

  if proof_id:
    MuteDebug.log("FLOW", "one-step mute with photo", proof=proof_id[:24])
    await _finalize_mute(message, parsed, proof_id, chat_id, admin_name)
    return True

  admin_id = message.from_user.id
  from bot.admins.punish_proof import (
    clear_other_pending_proofs,
    new_pending_record,
    pending_get,
    pending_set,
  )
  ensure_proof_pending_worker()
  clear_other_pending_proofs(admin_id, keep="mute")
  pending_set(_pending_mutes, admin_id, new_pending_record(
    parsed=parsed,
    chat_id=chat_id,
    admin_name=admin_name,
    admin_role=admin_role,
  ))
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  cancel_hint = _suggest_cancel_command(
    parsed.target_id, parsed.target_name, parsed.target_username,
  )
  prompt_text = _build_pending_proof_text(parsed, chat_line, cancel_hint)
  sent = await message.reply(
    prompt_text + _debug_hint("awaiting_proof"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_pending_cancel_keyboard(admin_id, parsed.target_id),
  )
  pending = pending_get(_pending_mutes, admin_id)
  if pending is not None:
    pending["prompt_chat_id"] = sent.chat.id
    pending["prompt_message_id"] = sent.message_id
  MuteDebug.log(
    "FLOW", "pending proof",
    admin_id=admin_id, target=parsed.target_id, message_id=sent.message_id,
  )
  return True


async def _execute_unmute_core(
  *,
  chat_id: int,
  actor_id: int,
  actor_username: Optional[str],
  admin_name: str,
  admin_role: Optional[str],
  staff: "StaffRef",
  target_id: int,
  target_name: str,
  target_username: Optional[str],
  cancelled: bool,
  reply: Callable[[str], Awaitable[Any]],
  broadcast_groups: bool = True,
  announce_result: bool = True,
) -> str:
  """Ядро снятия мута. Возвращает 'revoked' | 'not_muted' | 'db_error'.

  Не зависит от способа вызова (команда или кнопка): актёр и способ ответа
  передаются параметрами.

  broadcast_groups=False - не рассылать групповые уведомления;
  announce_result=False - не отправлять текстовый ответ-результат (используется
  при снятии через кнопку, когда исходное сообщение редактируется на месте).
  """
  player = PlayerRef(target_id, target_name, target_username)

  # Защита «в глубину»: снять мут с самого себя нельзя даже сотруднику с правами.
  if actor_id == target_id:
    if announce_result:
      await reply(self_revoke_denied_html() + _debug_hint("self_revoke"))
    MuteDebug.log("AUTH", "self revoke blocked", actor=actor_id, target=target_id)
    return "forbidden_self"

  rule = await get_staff_rule(admin_role)
  role_title = rule.display_name if rule else role_title_from_cache(admin_role)
  db_reason = (
    MuteText.DB_REASON_CANCEL.format(role_title=role_title, admin_name=admin_name)
    if cancelled else
    MuteText.DB_REASON_UNMUTE.format(role_title=role_title, admin_name=admin_name)
  )

  mute_state = await _resolve_player_mute_state(target_id)
  if not mute_state.is_muted:
    if announce_result:
      await reply(
        MuteText.NOT_MUTED.format(
          player_short=player.short, staff_line=staff.line, player_line=player.line,
        ) + _debug_hint("not_muted")
      )
    return "not_muted"

  last_mute = await _get_last_mute_record(chat_id, target_id)
  mute_reason = last_mute.mute_reason if last_mute else None

  # Охват определяем ДО очистки записей: уведомляем ТОЛЬКО те группы, где
  # пользователь реально был замучен. Если точный набор неизвестен, но мут был
  # глобальным (muteall) - запасной вариант «все официальные группы».
  _global_scope, affected_chats = await _resolve_mute_scope(target_id)
  if affected_chats:
    unmute_notify_chats: Optional[List[int]] = affected_chats
  elif _global_scope:
    unmute_notify_chats = [c for c in cfg.STAFF_CHAT_IDS if _is_staff_chat(c)]
  else:
    unmute_notify_chats = None

  if not await _clear_mute_db(
    target_id, actor_id, admin_name, target_name, chat_id, reason=db_reason,
    scope=("all" if _global_scope else "chat"),
  ):
    if announce_result:
      await reply(MuteText.UNMUTE_DB_ERROR + _debug_hint("unmute_db"))
    return "db_error"

  await _unrestrict_in_all_staff_chats(target_id)
  if not target_username:
    try:
      async with _db().pool.acquire() as conn:
        row = await conn.fetchrow(
          "SELECT username FROM users WHERE user_id = $1", target_id,
        )
      if row and row["username"]:
        target_username = row["username"]
    except Exception:
      pass
  player.username = target_username
  await _notify_unmute(
    chat_id, target_id, target_name, target_username,
    event="manual",
    acting_admin_id=actor_id,
    acting_admin_name=admin_name,
    acting_admin_role=admin_role,
    acting_admin_username=actor_username,
    cancelled=cancelled,
    mute_reason=mute_reason,
    broadcast_groups=broadcast_groups,
    notify_chats=unmute_notify_chats,
  )

  if announce_result:
    sync_note = MuteText.SYNC_NOTE if mute_state.needs_db_sync else ""
    title = MuteText.RESULT_TITLE_CANCELLED if cancelled else MuteText.RESULT_TITLE_DONE
    await reply(
      MuteText.UNMUTE_RESULT.format(
        title=title, staff_line=staff.line, player_line=player.line, sync_note=sync_note,
      ) + _debug_hint("unmute_ok")
    )
  try:
    from bot.admins import punish_timers
    punish_timers.cancel_mute(target_id)
  except Exception:
    pass
  return "revoked"


async def _execute_unmute(
  message: Message,
  target_id: int,
  target_name: str,
  *,
  cancelled: bool = False,
  target_username: Optional[str] = None,
) -> bool:
  """Снимает мут с нарушителя и уведомляет участников (вызов из команды)."""
  admin_name, admin_role, admin_account = await _resolve_admin_identity(message)
  staff = (
    StaffRef.from_account(admin_account)
    if admin_account else
    await StaffRef.from_message(message)
  )

  async def _reply(text: str) -> None:
    await message.reply(text, parse_mode="HTML", link_preview_options=NO_PREVIEW)

  await _execute_unmute_core(
    chat_id=message.chat.id,
    actor_id=message.from_user.id,
    actor_username=message.from_user.username,
    admin_name=admin_name,
    admin_role=admin_role,
    staff=staff,
    target_id=target_id,
    target_name=target_name,
    target_username=target_username,
    cancelled=cancelled,
    reply=_reply,
  )
  return True


async def _handle_cancel_mute_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _require_staff_chat(message):
    return True

  result = await _resolve_cancel_mute_target(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  target = result
  admin_id = message.from_user.id
  staff = await StaffRef.from_message(message)
  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_mutes, admin_id)
  player = PlayerRef(target.target_id, target.target_name, target.target_username)

  if pending:
    pending_target = pending["parsed"]
    if pending_target.target_id != target.target_id:
      pending_player = PlayerRef.from_parsed(pending_target)
      await message.reply(
        MuteText.OTHER_PENDING.format(
          greeting=staff.greeting,
          pending_player_line=pending_player.line,
          pending_player_short=pending_player.short,
          cancel_hint=escape(_suggest_cancel_command(
            pending_target.target_id, pending_target.target_name, pending_target.target_username,
          )),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      return True

    chat_id = pending.get("chat_id", message.chat.id)
    edited = await _finish_pending_cancel(admin_id, player.line, chat_id)
    if not edited:
      disp = await _get_chat_display(chat_id)
      chat_line = _format_chat_line(disp)
      await message.reply(
        MuteText.PENDING_CANCELLED_FALLBACK.format(
          player_line=player.line, chat_line=chat_line,
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    MuteDebug.log("FLOW", "pending cancelled", admin_id=admin_id, target=target.target_id)
    return True

  return await _execute_unmute(
    message, target.target_id, target.target_name,
    cancelled=True, target_username=target.target_username,
  )


async def _handle_unmute_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _require_staff_chat(message):
    return True

  body = _strip_unmute_prefix(_get_command_text(message))
  target_id, target_name, target_username = await _resolve_unmute_target(message)

  if not target_id:
    await message.reply(
      _target_lookup_error_message(body, target_username=target_username)
      + _debug_hint("unmute_no_target"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  return await _execute_unmute(
    message, target_id, target_name or str(target_id),
    cancelled=False, target_username=target_username,
  )


async def mute_process(message: Message) -> bool:
  """
  Обрабатывает сообщение. Возвращает True, если сообщение относится к муту
  и обработано (остальные handlers можно пропустить).
  """
  if not message.from_user:
    return False

  from bot.admins.punish_proof import (
    is_proof_only_photo,
    pending_contains,
    pending_get,
  )

  chat_id = message.chat.id
  uid = message.from_user.id
  pending = pending_contains(_pending_mutes, uid)

  if not pending and chat_id > 0:
    return False
  if not pending and chat_id < 0 and not _is_staff_chat(chat_id):
    if not _is_mute_related_message(message):
      return False

  await _ensure_mute_schema()

  command_text = _get_command_text(message)
  content = message.content_type

  MuteDebug.log(
    "IN", "message",
    uid=uid, chat=chat_id,
    type=content, text=command_text[:80] if command_text else "",
    photo=bool(message.photo), reply=bool(message.reply_to_message),
    pending=pending,
  )

  if pending:
    if is_proof_only_photo(message):
      return await _complete_mute_with_proof(message)

    if not command_text:
      MuteDebug.log("PROOF", "ignored non-photo while pending", uid=uid)
      return True

    low = command_text.lower().strip()
    if low in ("отмена", "cancel", "/cancel"):
      if not pending_contains(_pending_mutes, uid):
        return False
      if not await is_staff_admin(uid, "cancel_pending"):
        await _send_no_permission(message, "cancel_pending")
        return True
      if not _is_staff_chat(message.chat.id):
        return False
      pending_data = pending_get(_pending_mutes, uid)
      if not pending_data:
        return False
      p = pending_data["parsed"]
      hint = _suggest_cancel_command(p.target_id, p.target_name, p.target_username)
      staff = await StaffRef.from_message(message)
      player = PlayerRef(p.target_id, p.target_name, p.target_username)
      await message.reply(
        MuteText.CANCEL_HELP.format(
          greeting=staff.greeting, staff_line=staff.line,
          player_line=player.line, cancel_hint=escape(hint),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      return True

    if _is_cancel_mute_command(command_text):
      perm = await check_staff_permission(uid, "cancel_mute")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "cancel_mute")
      return await _handle_cancel_mute_command(message)

    if _is_mute_command(command_text):
      return await _dispatch_mute_with_feedback(message)

    MuteDebug.log("PROOF", "ignored text while pending", uid=uid, text=command_text[:60])
    return True

  if is_proof_only_photo(message) and _is_mute_related_message(message):
    return await _dispatch_mute_with_feedback(message)

  if not command_text:
    return False

  low = command_text.lower().strip()
  if low in ("отмена", "cancel", "/cancel"):
    return False

  if _is_cancel_mute_command(command_text):
    perm = await check_staff_permission(uid, "cancel_mute")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "cancel_mute")
    return await _handle_cancel_mute_command(message)

  if _is_unmute_command(command_text):
    perm = await check_staff_permission(uid, "unmute")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "unmute")
    return await _handle_unmute_command(message)

  if not _is_mute_command(command_text):
    return False

  return await _dispatch_mute_with_feedback(message)


async def _dispatch_mute_with_feedback(message: Message) -> bool:
  """Запускает обработку мут/муталл так, чтобы команда НИКОГДА не «молчала».

  Логика полностью совпадает с системой варнов: на любую команду мут/муталл
  пользователь получает ответ -
    • БД недоступна          → сервисное сообщение;
    • есть право mute        → обычная обработка (а для муталла внутри
                               дополнительно проверяется право muteall);
    • нет права (в т.ч. не сотрудник) → карточка «⛔️ Нет доступа».
  Так устраняется ситуация «при муталл/мут ничего не происходит».
  """
  perm = await check_staff_permission(message.from_user.id, "mute")
  if perm == "db_unavailable":
    await _reply_db_unavailable(message)
    return True
  if perm != "allowed":
    MuteDebug.log("AUTH", "mute denied", user_id=message.from_user.id, perm=perm)
    return await deny_permission(message, "mute")

  return await _handle_mute_command(message)


async def mute(message: Message) -> None:
  await _run_mute_guarded(message)


# ---------------------------------------------------------------------------
# Сводка «наказания» - единый список активных наказаний пользователя
# ---------------------------------------------------------------------------

async def _resolve_punishments_target(
  message: Message,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Цель сводки: ответ на сообщение → его автор; «мои наказания» → себя; иначе токен."""
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return u.id, u.full_name or u.first_name or str(u.id), u.username

  text = _get_command_text(message)
  t = (text or "").strip()
  if _PUNISH_PHRASE_RE.match(t):
    phrase = _PUNISH_PHRASE_RE.match(t).group(0).lower()
    if phrase.startswith("мои"):
      u = message.from_user
      return u.id, u.full_name or u.first_name or str(u.id), u.username

  body = _strip_punishments_prefix(text)
  if not body:
    return None, None, None
  return await _resolve_target_from_body(message, body)


async def _build_punishments_report(user_id: int, name: str, username: Optional[str]) -> str:
  """Собирает HTML-сводку активных мутов, банов и варнов."""
  from bot.admins.ban import list_active_bans_for_user
  from bot.admins.warn import (
    WARN_THRESHOLD,
    count_active_warns_for_user,
    list_active_warns_for_user,
    warn_counts_by_type,
    warn_kind_rows,
  )

  player = PlayerRef(user_id, name, username)
  player_line = player.line

  mutes = await list_active_mutes_for_user(user_id)
  mute_until = await _fetch_db_mute_until(user_id)
  bans = await list_active_bans_for_user(user_id)
  warn_count = await count_active_warns_for_user(user_id)

  if not mutes and not mute_until and not bans and warn_count == 0:
    return PunishText.NONE.format(player_line=player_line)

  parts: List[str] = [PunishText.HEADER.format(player_line=player_line)]

  if mutes:
    # Подробный список активных мутов по группам (включая «только эта группа»).
    parts.append(PunishText.MUTE_HEADER)
    for m in mutes:
      reason = (m.get("reason") or "").strip() or PunishText.REASON_EMPTY
      until = m.get("mute_until")
      until_str = _format_until_or_forever(until) if until else "-"
      m_chat_id = int(m.get("chat_id") or 0)
      if m_chat_id == 0:
        chat_line = PunishText.MUTE_CHAT_ALL
      else:
        disp = await _get_chat_display(m_chat_id)
        chat_line = (
          PunishText.MUTE_CHAT.format(title=escape(disp.title)) if disp else ""
        )
      parts.append(
        PunishText.MUTE_ITEM.format(
          until=until_str,
          chats=chat_line,
          reason=escape(reason),
        )
      )
  elif mute_until:
    # Запасной путь для устаревших записей без active_mutes.
    parts.append(PunishText.MUTE_SECTION.format(until=_format_until_or_forever(mute_until)))

  if bans:
    parts.append(PunishText.BAN_HEADER)
    for ban in bans:
      reason = (ban.get("reason") or "").strip() or PunishText.REASON_EMPTY
      until = ban.get("ban_until")
      until_str = _format_until(until) if until else "-"
      chat_id = int(ban.get("chat_id") or 0)
      disp = await _get_chat_display(chat_id) if chat_id else None
      chat_line = (
        PunishText.BAN_CHAT.format(title=escape(disp.title))
        if disp else ""
      )
      parts.append(
        PunishText.BAN_ITEM.format(
          until=until_str,
          chats=chat_line,
          reason=escape(reason),
        )
      )

  if warn_count > 0:
    # Единый с обзором «варны @user» формат: группировка по видам и группам,
    # под каждым видом - короткое последствие со ссылкой на нужную группу.
    warn_rows = await warn_kind_rows(user_id)
    if warn_rows:
      parts.append(
        PunishText.WARN_SECTION.format(rows="\n".join(warn_rows))
      )

  return "".join(parts)


async def _handle_punishments_command(message: Message) -> bool:
  """Показывает активные наказания пользователя. Доступно всем."""
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  target_id, target_name, target_username = await _resolve_punishments_target(message)
  if not target_id:
    await message.reply(PunishText.NO_TARGET, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  text = await _build_punishments_report(
    target_id,
    target_name or str(target_id),
    target_username,
  )
  await message.reply(text, parse_mode="HTML", link_preview_options=NO_PREVIEW)
  MuteDebug.log("FLOW", "punishments shown", target=target_id, viewer=message.from_user.id)
  return True


async def punishments(message: Message) -> None:
  """Точка входа из main.py для команды «наказания»."""
  await _handle_punishments_command(message)


# ---------------------------------------------------------------------------
# Состав администрации - список сотрудников по должностям (доступно всем)
# ---------------------------------------------------------------------------

def _role_rule(role: Optional[str]) -> Optional["StaffRuleRecord"]:
  if not role:
    return None
  if _staff_rules_cache:
    return _staff_rules_cache[0].get(role.strip().lower())
  return None


def _role_importance(role: Optional[str]) -> Optional[int]:
  """Старшинство должности из staff_rules.importance (чем больше - тем выше)."""
  rule = _role_rule(role)
  if rule and rule.importance is not None:
    return rule.importance
  return None


def _role_rank(role: Optional[str]) -> int:
  """Грубый ранг должности для сортировки: больше прав → выше в списке."""
  if not role:
    return -1
  rule = _role_rule(role)
  if not rule:
    return 0
  return sum(1 for v in rule.permissions.values() if v)


def _role_sort_weight(role: Optional[str]) -> int:
  """Вес сортировки должности: importance (приоритет) → иначе число прав."""
  imp = _role_importance(role)
  if imp is not None:
    return imp
  return _role_rank(role)


def _staff_member_is_away(
  availability_until: Optional[Any],
  now: Optional[datetime] = None,
) -> bool:
  """Сотрудник временно недоступен, если availability_until ещё не наступил."""
  if not availability_until or not isinstance(availability_until, datetime):
    return False
  until = availability_until
  if until.tzinfo is None:
    until = until.replace(tzinfo=timezone.utc)
  return until > (now or datetime.now(timezone.utc))


def _row_value(row: Dict[str, Any], *names: str) -> Any:
  """Безопасно достаёт значение по одному из возможных имён столбцов."""
  for n in names:
    if n in row and row[n] is not None:
      return row[n]
  return None


_STATUS_SORT: Dict[str, int] = {
  StaffRosterText.STATUS_ONLINE: 0,
  StaffRosterText.STATUS_RECENT: 1,
  StaffRosterText.STATUS_OFFLINE: 2,
  StaffRosterText.STATUS_AWAY: 3,
}


def _ago_label(sec: int) -> str:
  """Человеческая подпись «был(а) N назад» по числу секунд с последней активности."""
  if sec < 45:
    return "был(а) только что"
  if sec < 3600:
    return f"был(а) {sec // 60} мин назад"
  if sec < 86400:
    return f"был(а) {sec // 3600} ч назад"
  return f"был(а) {sec // 86400} дн назад"


def _status_for(
  uid: int,
  availability_until: Optional[Any],
  now: datetime,
) -> Tuple[str, Optional[str]]:
  """Метка статуса сотрудника и (опционально) подпись «был(а) …».

  Модель «онлайн по факту переписки» - статус считается ТОЛЬКО по последнему
  сообщению, замеченному ботом (в любой группе с ботом или в личке):
    1) объявленная недоступность («не на смене») - бизнес-флаг, высший приоритет;
    2) сообщение ≤ ACTIVITY_ONLINE_SEC назад → 🟢 «в сети»;
    3) сообщение ≤ ACTIVITY_RECENT_SEC назад → 🟡 «недавно» + «был(а) N назад»;
    4) иначе → ⚪ «не в сети» (+ «был(а) N назад», если активность вообще была).
  """
  if _staff_member_is_away(availability_until, now):
    return StaffRosterText.STATUS_AWAY, None
  last = _admin_last_active.get(uid)
  if last is None:
    return StaffRosterText.STATUS_OFFLINE, None
  sec = max(0, int(time.time() - last))
  if sec <= _ACTIVITY_ONLINE_SEC:
    return StaffRosterText.STATUS_ONLINE, None
  if sec <= _ACTIVITY_RECENT_SEC:
    return StaffRosterText.STATUS_RECENT, _ago_label(sec)
  return StaffRosterText.STATUS_OFFLINE, _ago_label(sec)


async def _enrich_staff_identity(row: Dict[str, Any], uid: int) -> None:
  """Дозаполняет имя/username сотрудника, чтобы в составе не светился голый ID.

  Голый user_id в списке «кто админ» - крайний случай. Он допустим ТОЛЬКО когда
  исчерпаны все источники. Порядок поиска (по убыванию доверия):
    1) admin_accounts - то, что уже пришло в row (могло быть пустым);
    2) таблица users по user_id - сначала first_name, затем username;
    3) сам Telegram (get_chat по user_id) - если в БД пусто.
  Найденное дописывается в row и (по возможности) закрепляется в admin_accounts,
  чтобы имя не пропадало при следующих обновлениях состава.
  """
  first_name = (str(_row_value(row, "first_name", "name") or "")).strip()
  username = _sanitize_username(_row_value(row, "username", "user_name"))
  if first_name and username:
    return

  resolved_name: Optional[str] = None
  resolved_username: Optional[str] = None
  db = _db()

  # 2) Таблица users по user_id: имя, затем username.
  if not first_name:
    try:
      db_name = await db.get_firstname_by_user_id(uid)
    except Exception:
      db_name = None
    if db_name and str(db_name).strip():
      first_name = resolved_name = str(db_name).strip()

  if not username:
    try:
      db_username = await db.get_username_by_user_id(uid)
    except Exception:
      db_username = None
    clean = _sanitize_username(db_username)
    if clean:
      username = resolved_username = clean

  # 3) Последний рубеж перед голым ID - спросить сам Telegram по user_id.
  if not first_name and not username:
    chat = await _safe_fetch_user_chat(uid)
    if chat is not None:
      tg_name = getattr(chat, "full_name", None) or getattr(chat, "first_name", None)
      if tg_name and str(tg_name).strip():
        first_name = resolved_name = str(tg_name).strip()
      tg_username = _sanitize_username(getattr(chat, "username", None))
      if tg_username:
        username = resolved_username = tg_username

  if resolved_name:
    row["first_name"] = resolved_name
  if resolved_username:
    row["username"] = resolved_username

  # Best-effort: закрепляем найденное в admin_accounts, чтобы не искать заново.
  if resolved_name or resolved_username:
    try:
      pool = db.pool
      if pool:
        await pool.execute(
          """
          UPDATE admin_accounts
          SET first_name = COALESCE($2, first_name),
              username = COALESCE($3, username)
          WHERE user_id = $1
          """,
          uid, resolved_name, resolved_username,
        )
        invalidate_admin_account_cache(uid)
    except Exception:
      pass


async def _load_staff_groups() -> Tuple[Optional[Dict[str, List[Dict[str, Any]]]], List[int]]:
  """Читает admin_accounts и группирует сотрудников по должностям.

  Возвращает (groups, ids). groups=None означает недоступность БД (покажем
  UNAVAILABLE); пустой ids означает «нет назначенных сотрудников».
  Список участников читается один раз и переиспользуется при живых обновлениях
  (между тиками меняются только статусы, а не состав).
  """
  await load_staff_rules()
  pool = _db().pool
  if not pool:
    return None, []
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch("SELECT * FROM admin_accounts")
  except DbUnavailableError:
    return None, []
  except Exception as e:
    MuteDebug.log("ROSTER", "load staff skip", err=str(e))
    return None, []

  groups: Dict[str, List[Dict[str, Any]]] = {}
  ids: List[int] = []
  for r in rows:
    row = dict(r)
    raw_role = _row_value(row, "role", "roles")
    if raw_role is None or not str(raw_role).strip():
      continue
    uid_raw = _row_value(row, "user_id", "id", "tg_id")
    if uid_raw is None:
      continue
    try:
      row["_uid"] = int(uid_raw)
    except (TypeError, ValueError):
      continue
    # Гарантируем читаемое имя/username: users по user_id, затем сам Telegram.
    # Голый ID останется только если все источники ничего не дали.
    await _enrich_staff_identity(row, row["_uid"])
    groups.setdefault(str(raw_role).strip().lower(), []).append(row)
    ids.append(row["_uid"])

  # Все эти uid - администраторы: включаем для них персистентность активности
  # и подтягиваем сохранённую активность (важно сразу после рестарта).
  if ids:
    _known_admin_ids.update(ids)
    await _load_activity_from_db(ids)
  return groups, ids


def _roster_visible_roles(groups: Dict[str, List[Dict[str, Any]]]) -> List[str]:
  """Должности для показа - ТОЛЬКО те, на которых есть назначенные сотрудники.

  Вакантные должности (без участников) полностью скрываются. Сортировка - по
  старшинству (staff_rules.importance) по убыванию: самое большое число (например
  5 = Владелец) идёт первым.
  """
  visible = [rk for rk, members in groups.items() if members]
  return sorted(
    visible,
    key=lambda rk: (
      -_role_sort_weight(rk),
      -len(groups.get(rk, [])),
      role_title_from_cache(rk).lower(),
    ),
  )


def _render_roster(
  groups: Dict[str, List[Dict[str, Any]]],
  *,
  live: bool,
  pulse_idx: int = 0,
) -> str:
  """Рисует HTML состава в виде дерева: заголовок → должности → ветки участников.

  Статусы вычисляются на лету из активности, замеченной ботом, поэтому каждая
  перерисовка (в т.ч. живое обновление) отражает свежее состояние без доп. запросов.
  """
  now = datetime.now(timezone.utc)
  parts: List[str] = [StaffRosterText.HEADER]
  shown_roles = 0

  def _member_sort_key(m: Dict[str, Any]) -> Tuple[int, str]:
    uid = m["_uid"]
    dot, _ = _status_for(uid, _row_value(m, "availability_until"), now)
    name = (str(_row_value(m, "first_name", "name") or "")).lower()
    return (_STATUS_SORT.get(dot, 9), name)

  for role_key in _roster_visible_roles(groups):
    title = role_title_from_cache(role_key)
    members = list(groups.get(role_key, []))
    if not members:
      continue
    shown_roles += 1

    imp = _role_importance(role_key)
    imp_html = StaffRosterText.ROLE_IMPORTANCE.format(n=imp) if imp is not None else ""
    parts.append(StaffRosterText.ROLE_HEADER.format(
      emoji=_role_emoji(role_key, title), role=escape(title), imp=imp_html))

    members.sort(key=_member_sort_key)
    last_idx = len(members) - 1
    for i, m in enumerate(members):
      is_last = i == last_idx
      branch = StaffRosterText.BRANCH_END if is_last else StaffRosterText.BRANCH_MID
      uid = int(m["_uid"])
      link = _roster_member_link(m, uid)
      note = _roster_member_note(m, title)
      dot, hint = _status_for(uid, _row_value(m, "availability_until"), now)
      parts.append(StaffRosterText.MEMBER_LINE.format(
        branch=branch, status=dot, member=link, note=note))
      if hint:
        rail = StaffRosterText.RAIL_END if is_last else StaffRosterText.RAIL_MID
        parts.append(StaffRosterText.HINT_LINE.format(rail=rail, hint=escape(hint)))

  # Подсказка про кнопки - только если есть что открывать (видимые должности).
  if shown_roles:
    parts.append(
      StaffRosterText.TAP_HINT_ROLES if ROSTER_SHOW_ROLE_BUTTONS
      else StaffRosterText.TAP_HINT_ALL
    )

  stamp = datetime.now(LiveRosterConfig.TZ).strftime("%H:%M:%S")
  if live:
    frames = StaffRosterText.PULSE_FRAMES
    parts.append(StaffRosterText.FOOTER_LIVE.format(
      pulse=frames[pulse_idx % len(frames)], time=stamp))
  else:
    parts.append(StaffRosterText.FOOTER_STATIC.format(time=stamp))
  return "".join(parts)


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_plain(html_text: str) -> str:
  """Грубое превращение HTML-разметки в чистый текст (для безопасного фолбэка)."""
  plain = _HTML_TAG_RE.sub("", html_text)
  return (
    plain.replace("&lt;", "<").replace("&gt;", ">")
    .replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
  )


# Чаты, где сейчас открыта карточка прав (детали/обзор) вместо состава: живое
# обновление приостанавливается, чтобы не «затирать» открытую карточку.
_roster_paused: set = set()


# ⚙️ НАСТРОЙКА: показывать ли отдельные кнопки по каждой должности под составом.
#   False (по умолчанию) - под «кто админ» одна кнопка «📋 Все права».
#   True                 - добавляются кнопки по каждой должности (детали по клику).
ROSTER_SHOW_ROLE_BUTTONS: bool = False


def _build_roster_keyboard(
  groups: Dict[str, List[Dict[str, Any]]],
  viewer_id: Optional[int],
) -> Optional[InlineKeyboardMarkup]:
  """Клавиатура под составом.

  По умолчанию - одна кнопка «📋 Все права» (без выбора отдельных должностей).
  Если ROSTER_SHOW_ROLE_BUTTONS=True - сверху добавляются кнопки по должностям
  (callback_data «staff:detail:{viewer}:{idx}»). Нажимать может только вызвавший.
  """
  if viewer_id is None:
    return None
  visible = _roster_visible_roles(groups)
  if not visible:
    return None
  rows: List[List[InlineKeyboardButton]] = []
  if ROSTER_SHOW_ROLE_BUTTONS:
    row: List[InlineKeyboardButton] = []
    for idx, role_key in enumerate(visible):
      title = role_title_from_cache(role_key)
      emoji = _role_emoji_plain(role_key, title)
      label = f"{emoji} {title}"
      if len(label) > 30:
        label = label[:29] + "…"
      row.append(InlineKeyboardButton(
        text=label, callback_data=f"staff:detail:{viewer_id}:{idx}",
      ))
      if len(row) == 2:
        rows.append(row)
        row = []
    if row:
      rows.append(row)
  rows.append([InlineKeyboardButton(
    text=StaffPermsText.BTN_ALL, callback_data=f"staff:all:{viewer_id}",
  )])
  return InlineKeyboardMarkup(inline_keyboard=rows)


def _perms_back_keyboard(viewer_id: int) -> InlineKeyboardMarkup:
  """Кнопка возврата из карточки «Все права» к составу администрации."""
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text=StaffPermsText.BTN_BACK, callback_data=f"staff:back:{viewer_id}"),
  ]])


async def _roster_safe_reply(
  message: Message,
  html_text: str,
  reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Optional[Message]:
  """Отправляет ответ HTML; при ошибке Telegram переходит на plain-текст.

  Гарантирует ответ пользователю и ВОЗВРАЩАЕТ отправленное сообщение - оно нужно
  для последующего живого обновления (in-place редактирования).
  """
  try:
    return await message.reply(
      html_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      reply_markup=reply_markup,
    )
  except Exception as e:
    MuteDebug.error("ROSTER", "html reply failed, falling back to plain", e)
  try:
    return await message.reply(
      _html_to_plain(html_text)[:4000], link_preview_options=NO_PREVIEW,
      reply_markup=reply_markup,
    )
  except Exception as e:
    MuteDebug.error("ROSTER", "plain reply failed too", e)
    return None


async def _safe_edit(
  sent: Message,
  html_text: str,
  reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
  """Безопасно редактирует сообщение состава; «not modified» - это не ошибка.

  reply_markup передаётся всегда, иначе edit_text СНЯЛ БЫ инлайн-кнопки.
  """
  from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
  try:
    await sent.edit_text(
      html_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      reply_markup=reply_markup,
    )
    return True
  except TelegramRetryAfter as e:
    await asyncio.sleep(float(getattr(e, "retry_after", 3)) + 0.5)
    return True
  except TelegramBadRequest as e:
    if "not modified" in str(e).lower():
      return True
    try:
      await sent.edit_text(
        _html_to_plain(html_text)[:4000], link_preview_options=NO_PREVIEW,
        reply_markup=reply_markup,
      )
      return True
    except Exception:
      return False
  except Exception as e:
    MuteDebug.log("ROSTER", "edit failed", err=str(e))
    return False


# Активные «живые» сессии состава: chat_id → задача обновления.
_live_roster_tasks: Dict[int, "asyncio.Task"] = {}


async def _live_roster_loop(
  sent: Message,
  viewer_id: Optional[int],
  groups: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
  """Каждые REFRESH_SEC секунд перерисовывает состав в реальном времени.

  Обновляет сообщение МАКСИМУМ MAX_UPDATES раз (по одному разу за REFRESH_SEC),
  затем фиксирует финальный снимок со статичной подсказкой «для точной информации
  напишите кто админ ещё раз». Бесконечное редактирование упёрлось бы в лимиты
  Telegram. Индикатор-«пульс» и отметка времени гарантируют, что правка всегда
  проходит (нет «not modified»). Пока в чате открыта карточка прав (chat_id в
  _roster_paused) - правки состава пропускаются (и лимит не расходуется), чтобы
  не «затирать» карточку. Клавиатура передаётся при каждой правке, иначе
  edit_text снял бы кнопки.
  """
  chat_id = sent.chat.id
  try:
    if groups is None:
      groups, ids = await _load_staff_groups()
    else:
      ids = [m["_uid"] for members in groups.values() for m in members]
    if not groups or not ids:
      return
    keyboard = _build_roster_keyboard(groups, viewer_id)
    deadline = time.time() + LiveRosterConfig.WINDOW_SEC
    failures = 0
    pulse = 0
    updates = 0  # сколько раз реально обновили сообщение (максимум MAX_UPDATES)
    while updates < LiveRosterConfig.MAX_UPDATES and time.time() < deadline:
      await asyncio.sleep(LiveRosterConfig.REFRESH_SEC)
      # Пока открыта карточка прав - не трогаем сообщение и не тратим лимит правок.
      if chat_id in _roster_paused:
        continue
      pulse += 1
      updates += 1
      text = _render_roster(groups, live=True, pulse_idx=pulse)
      ok = await _safe_edit(sent, text, reply_markup=keyboard)
      if ok:
        failures = 0
      else:
        failures += 1
        if failures >= LiveRosterConfig.MAX_EDIT_FAILURES:
          MuteDebug.log("ROSTER", "live stop: too many edit failures", chat=chat_id)
          return
    # Достигнут лимит обновлений (или окно) - фиксируем финальный снимок со
    # статичной подсказкой «для точной информации напишите кто админ ещё раз».
    if chat_id not in _roster_paused:
      await _safe_edit(sent, _render_roster(groups, live=False), reply_markup=keyboard)
    MuteDebug.log("ROSTER", "live finished", chat=chat_id, updates=updates)
  except asyncio.CancelledError:
    raise
  except Exception as e:
    MuteDebug.error("ROSTER", "live loop crashed", e)
  finally:
    if _live_roster_tasks.get(chat_id) is asyncio.current_task():
      _live_roster_tasks.pop(chat_id, None)


async def _start_live_roster(
  sent: Optional[Message],
  viewer_id: Optional[int] = None,
  groups: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
  """Запускает живое обновление для отправленного сообщения состава."""
  if sent is None:
    return
  chat_id = sent.chat.id
  # Свежая команда «кто админ» сбрасывает паузу и прежнюю сессию этого чата.
  _roster_paused.discard(chat_id)
  prev = _live_roster_tasks.get(chat_id)
  if prev is not None and not prev.done():
    prev.cancel()
  active = sum(1 for t in _live_roster_tasks.values() if not t.done())
  if active >= LiveRosterConfig.MAX_CONCURRENT:
    MuteDebug.log("ROSTER", "live limit reached -> static only", chat=chat_id)
    return
  _live_roster_tasks[chat_id] = asyncio.create_task(
    _live_roster_loop(sent, viewer_id, groups)
  )


async def _handle_staff_roster_command(
  message: Message,
) -> Tuple[Optional[Message], Optional[int], Optional[Dict[str, List[Dict[str, Any]]]]]:
  """Показывает состав администрации и возвращает (сообщение, viewer, groups).

  Метод намеренно «непробиваем»: при любой внутренней ошибке пользователь всё
  равно получит понятный ответ, чтобы команда никогда не выглядела «молчащей».
  Возвращённые viewer/groups нужны для живого обновления и инлайн-кнопок прав.
  """
  viewer = getattr(getattr(message, "from_user", None), "id", None)
  MuteDebug.log("FLOW", "staff roster requested", viewer=viewer)
  try:
    await _ensure_mute_schema()
    if not await _db().ensure_pool():
      await _roster_safe_reply(message, StaffRosterText.UNAVAILABLE)
      return None, None, None

    groups, ids = await _load_staff_groups()
    if groups is None:
      await _roster_safe_reply(message, StaffRosterText.UNAVAILABLE)
      return None, None, None
    if not ids:
      await _roster_safe_reply(message, StaffRosterText.EMPTY)
      return None, None, None

    text = _render_roster(groups, live=True, pulse_idx=0)
    keyboard = _build_roster_keyboard(groups, viewer)
    sent = await _roster_safe_reply(message, text, reply_markup=keyboard)
    MuteDebug.log("FLOW", "staff roster shown", viewer=viewer)
    return sent, viewer, groups
  except Exception as e:
    MuteDebug.error("ROSTER", "handle command failed", e)
    await _roster_safe_reply(message, StaffRosterText.UNAVAILABLE)
    return None, None, None


async def staff_roster(message: Message) -> None:
  """Точка входа из main.py для команды «кто админ» / «/staff» / «состав».

  Отправляет состав и запускает живое обновление статусов в реальном времени.
  """
  sent, viewer, groups = await _handle_staff_roster_command(message)
  await _start_live_roster(sent, viewer, groups)


async def staff_permissions(message: Message) -> None:
  """Точка входа из main.py для команды «права админов» - обзор прав должностей."""
  MuteDebug.log("FLOW", "staff permissions requested",
                viewer=getattr(getattr(message, "from_user", None), "id", None))
  try:
    await _ensure_mute_schema()
    if not await _db().ensure_pool():
      await _roster_safe_reply(message, StaffRosterText.UNAVAILABLE)
      return
    await load_staff_rules()
    await _roster_safe_reply(message, _all_perms_card())
  except Exception as e:
    MuteDebug.error("ROSTER", "permissions command failed", e)
    await _roster_safe_reply(message, StaffRosterText.UNAVAILABLE)


# ---------------------------------------------------------------------------
# Middleware - перехват ВСЕХ сообщений до остальных handlers
# ---------------------------------------------------------------------------

class MuteMiddleware(BaseMiddleware):
  """
  Только фоновая поддержка: блокировка сообщений замученных и шаг 2 (фото/отмена).
  Текстовые команды мут/размут вызываются из main.py по паттерну игровых команд.
  """
  async def __call__(self, handler, event: TelegramObject, data: dict):
    if not isinstance(event, Message) or not event.from_user:
      return await handler(event, data)

    msg: Message = event
    uid = msg.from_user.id
    # Фиксируем активность пользователя для эвристики «в сети» в составе админов.
    note_admin_activity(uid)
    from bot.admins.punish_proof import pending_contains
    pending = pending_contains(_pending_mutes, uid)
    staff_group = msg.chat.id < 0 and _is_staff_chat(msg.chat.id)

    # Одношаговый мут: фото-пруф + подпись-команда («мут @user 10сек причина»).
    # main.py (обработчик F.text) такие сообщения не видит - у фото нет .text, -
    # а роутер фото может перехватить другая система. Поэтому ловим это здесь,
    # ровно как в бан/варн/кик.
    media_command = (
      not pending
      and staff_group
      and _has_proof_media(msg)
      and _is_mute_related_message(msg)
    )

    if not pending and not staff_group:
      return await handler(event, data)

    try:
      if media_command:
        if await mute_process(msg):
          MuteDebug.log("MW", "handled media mute", msg_id=msg.message_id)
          return None

      if staff_group and not pending:
        if await _enforce_muted_user_in_chat(msg):
          MuteDebug.log("MW", "blocked muted user msg", msg_id=msg.message_id)
          return None

      if pending:
        if await mute_process(msg):
          MuteDebug.log("MW", "handled pending mute", msg_id=msg.message_id)
          return None
    except Exception as e:
      MuteDebug.error("MW", "mute_process crash", e, msg_id=getattr(msg, "message_id", None))
      try:
        await msg.reply(
          _generic_handler_error_message(),
          parse_mode="HTML", link_preview_options=NO_PREVIEW,
        )
      except Exception:
        pass
    return await handler(event, data)


# ---------------------------------------------------------------------------
# Роутер (запасной канал)
# ---------------------------------------------------------------------------

async def _run_mute_guarded(message: Message) -> bool:
  """Единая защищённая точка запуска обработки мута.

  Любая ошибка внутри mute_process логируется с полным трейсбэком и
  превращается в видимое сообщение администратору - команда НИКОГДА не
  завершается «молча». Это приводит мут к тому же уровню надёжности, что и
  бан/варн/кик (там та же защита реализована через middleware).
  """
  try:
    return await mute_process(message)
  except Exception as e:
    MuteDebug.error("FATAL", "mute_process crash", e, msg_id=getattr(message, "message_id", None))
    try:
      await message.reply(
        MuteText.GENERIC_ERROR + _debug_hint("mute_crash"),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception:
      pass
    return True


@mute_router.message(F.photo)
async def mute_on_photo(message: Message) -> None:
  if _is_mute_related_message(message):
    await _run_mute_guarded(message)


@mute_router.message(F.document)
async def mute_on_document(message: Message) -> None:
  if message.document and (message.document.mime_type or "").startswith("image/"):
    if _is_mute_related_message(message):
      await _run_mute_guarded(message)


@mute_router.callback_query(F.data.startswith("mute:cancel:"))
async def mute_cancel_callback(callback: CallbackQuery) -> None:
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) != 4:
    await callback.answer(MuteText.CB_BAD_DATA, show_alert=True)
    return

  try:
    admin_id = int(parts[2])
    target_id = int(parts[3])
  except ValueError:
    await callback.answer(MuteText.CB_BAD_DATA, show_alert=True)
    return

  if callback.from_user.id != admin_id:
    owner = await StaffRef.from_user_id(admin_id)
    await callback.answer(
      MuteText.CB_ONLY_AUTHOR.format(actor=owner.actor_plain), show_alert=True,
    )
    return

  if not await is_staff_admin(admin_id, "cancel_pending"):
    await callback.answer(MuteText.CB_NO_PERM, show_alert=True)
    return

  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_mutes, admin_id)
  if not pending:
    try:
      await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
      pass
    await callback.answer(MuteText.CB_DONE, show_alert=True)
    return

  if pending["parsed"].target_id != target_id:
    await callback.answer(MuteText.CB_STALE, show_alert=True)
    return

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(MuteText.CB_WRONG_CHAT, show_alert=True)
    return

  player_line = _format_player_line(
    target_id,
    pending["parsed"].target_name,
    pending["parsed"].target_username,
  )
  chat_id = pending.get("chat_id", callback.message.chat.id)
  await _finish_pending_cancel(admin_id, player_line, chat_id)
  await callback.answer(MuteText.CB_CANCELLED)
  MuteDebug.log("FLOW", "pending cancelled via button", admin_id=admin_id, target=target_id)


@mute_router.callback_query(F.data.startswith("mute:revoke:"))
async def mute_revoke_callback(callback: CallbackQuery) -> None:
  """Снятие мута по кнопке под сообщением «Ограничение выдано».

  Нажать может любой сотрудник с правом на снятие мута (unmute).
  """
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) != 4:
    await callback.answer(MuteText.CB_BAD_DATA, show_alert=True)
    return
  try:
    target_id = int(parts[3])
  except ValueError:
    await callback.answer(MuteText.CB_BAD_DATA, show_alert=True)
    return

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(MuteText.CB_WRONG_CHAT, show_alert=True)
    return

  clicker = callback.from_user.id
  perm = await check_staff_permission(clicker, "unmute")
  if perm != "allowed":
    await callback.answer(
      MuteText.CB_DB if perm == "db_unavailable" else MuteText.CB_NO_PERM,
      show_alert=True,
    )
    return

  account = await get_admin_account(clicker)
  staff = StaffRef.from_account(account) if account else await StaffRef.from_user_id(clicker)
  target_name, target_username = await _resolve_user_display(target_id)

  async def _noop(_text: str) -> None:
    return None

  chat_id = callback.message.chat.id
  status = await _execute_unmute_core(
    chat_id=chat_id,
    actor_id=clicker,
    actor_username=callback.from_user.username,
    admin_name=staff.name,
    admin_role=staff.role,
    staff=staff,
    target_id=target_id,
    target_name=target_name,
    target_username=target_username,
    cancelled=False,
    reply=_noop,
    broadcast_groups=False,
    announce_result=False,
  )

  if status == "revoked":
    player = PlayerRef(target_id, target_name, target_username)
    disp = await _get_chat_display(chat_id)
    new_text = MuteText.REVOKED_EDIT.format(
      player_line=player.line,
      chat_line=_format_chat_line(disp),
      staff_line=f"{staff.line}\n",
      player_short=player.short,
    )
    await _edit_revoked_message(callback.message, new_text)
    await callback.answer(MuteText.CB_REVOKED)
  elif status == "not_muted":
    await _edit_remove_keyboard(callback.message)
    await callback.answer(MuteText.CB_NOT_MUTED, show_alert=True)
  elif status == "forbidden_self":
    await callback.answer(MuteText.CB_SELF_REVOKE, show_alert=True)
  else:
    await callback.answer(MuteText.CB_REVOKE_FAILED, show_alert=True)
  MuteDebug.log("FLOW", "mute revoked via button", actor=clicker, target=target_id, status=status)


@mute_router.callback_query(F.data.startswith("staff:"))
async def staff_perms_callback(callback: CallbackQuery) -> None:
  """Кнопки под «кто админ»: показать права должности / обзор / вернуться к составу.

  Нажимать может ТОЛЬКО тот, кто вызвал список (viewer_id в callback_data).
  Формат: staff:detail:{viewer}:{idx} · staff:all:{viewer} · staff:back:{viewer}.
  """
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) < 3:
    await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
    return
  action = parts[1]
  try:
    viewer_id = int(parts[2])
  except ValueError:
    await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
    return

  # Только инициатор списка может листать карточки прав.
  if callback.from_user.id != viewer_id:
    await callback.answer(StaffPermsText.CB_ONLY_AUTHOR, show_alert=True)
    return

  chat_id = callback.message.chat.id
  try:
    await load_staff_rules()
  except Exception as e:
    MuteDebug.error("ROSTER", "perms callback rules load", e)
    await callback.answer(StaffPermsText.CB_UNAVAILABLE, show_alert=True)
    return

  if action == "detail":
    if len(parts) < 4:
      await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
      return
    try:
      idx = int(parts[3])
    except ValueError:
      await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
      return
    groups, _ids = await _load_staff_groups()
    visible = _roster_visible_roles(groups or {})
    if idx < 0 or idx >= len(visible):
      await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
      return
    _roster_paused.add(chat_id)
    await _safe_edit(
      callback.message, _role_perms_card(visible[idx]),
      reply_markup=_perms_back_keyboard(viewer_id),
    )
    await callback.answer()
    return

  if action == "all":
    _roster_paused.add(chat_id)
    await _safe_edit(
      callback.message, _all_perms_card(),
      reply_markup=_perms_back_keyboard(viewer_id),
    )
    await callback.answer()
    return

  if action == "back":
    _roster_paused.discard(chat_id)
    groups, _ids = await _load_staff_groups()
    if not groups:
      await callback.answer(StaffPermsText.CB_STALE, show_alert=True)
      return
    # Если живое обновление ещё активно - оно само продолжит править состав;
    # здесь сразу показываем актуальный снимок с кнопками должностей.
    live = chat_id in _live_roster_tasks and not _live_roster_tasks[chat_id].done()
    await _safe_edit(
      callback.message, _render_roster(groups, live=live),
      reply_markup=_build_roster_keyboard(groups, viewer_id),
    )
    await callback.answer()
    return

  await callback.answer(StaffPermsText.CB_STALE, show_alert=True)


# ---------------------------------------------------------------------------
# Подключение к dispatcher
# ---------------------------------------------------------------------------

def attach_mute_system(dp) -> None:
  global _mute_system_attached
  if _mute_system_attached:
    MuteDebug.log("WIRE", "already attached")
    return
  try:
    dp.message.middleware(MuteMiddleware())
    dp.include_router(mute_router)
    _mute_system_attached = True
    try:
      loop = asyncio.get_running_loop()
      loop.create_task(load_staff_rules(force_refresh=True))
      loop.create_task(_warm_activity_state())
      ensure_proof_pending_worker()
    except RuntimeError:
      pass
    MuteDebug.log("WIRE", "attached middleware + router", log_file=cfg.LOG_FILE)
    print(f"[MUTE] ✅ Система мута подключена → лог: {cfg.LOG_FILE}")
  except Exception as e:
    MuteDebug.error("WIRE", "attach failed", e)
    print(f"[MUTE][WIRE][ERROR] {e}")
