# -*- coding: utf-8 -*-
"""
Система банов нарушителей в официальных группах проекта.

Бан = исключение с блокировкой возврата до указанного администратором времени
(Telegram `ban_chat_member` с `until_date`; по истечении срока Telegram
автоматически снимает блокировку). Принцип работы скопирован с систем мута и
кика: обязательное фото-доказательство, охват chat/all, права из БД.

Подключение (main.py):
    from bot.admins.ban import attach_ban_system
    attach_ban_system(dp)

Форматы:
    • Ответ + фото + подпись:  бан 1д причина
    • Без ответа + фото:       бан @user 1д причина
                               бан username 7д причина
                               бан 123456789 12ч причина
    • Охват: бан - только эта группа; баналл / банвсе - все официальные группы
    • Два шага: текст → фото (в течение 5 мин)
    • Отмена ожидания: отменить бан @user

proof_media_id → staff_actions (action_type = 'ban')

Права:
    admin_accounts - должность (role), статус, доступность
    staff_rules    - столбец ban (1/0); если столбца нет, действует право mute
"""
from __future__ import annotations

import asyncio
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
  Scope,
  StaffRef,
  _bot,
  _db,
  _ensure_mute_schema,
  _extract_duration_and_reason,
  _body_starts_with_duration,
  _format_chat_line,
  _format_chats_line,
  _format_duration_short,
  _format_mute_reason_block,
  _format_player_line,
  _format_scope_block,
  _format_until,
  _get_chat_display,
  _get_command_text,
  _get_proof_file_id,
  _get_reply_target_message,
  _has_command_text,
  _has_proof_media,
  _is_staff_chat,
  _proof_owner_token,
  _lookup_target_by_token,
  _require_staff_chat,
  _resolve_admin_identity,
  _resolve_target_from_body,
  _resolve_user_display,
  _edit_revoked_message,
  _edit_remove_keyboard,
  _send_no_permission,
  deny_permission,
  _service_unavailable_message,
  _generic_handler_error_message,
  _target_lookup_error_message,
  _until_to_telegram_date,
  _db_acquire,
  _reply_db_unavailable,
  _is_transient_db_error,
  _format_scope_with_groups,
  _resolve_reply_or_explicit,
  check_staff_permission,
  parse_duration,
  DbUnavailableError,
  NO_PREVIEW,
  cfg,
  Mode,
  parse_command_mode,
  mode_to_scope,
  scope_label,
  _MOD_SCOPE_ALL_SUFFIXES,
  _MOD_SCOPE_FULL_SUFFIXES,
  _rebase_expiry_at_now,
  _normalize_time_delta,
  self_revoke_denied_html,
  is_protected_creator,
  protected_creator_denied_html,
  SELF_REVOKE_ALERT,
)

ban_router = Router(name="staff_ban")

# --- Команды ---
BAN_COMMANDS: frozenset = frozenset({
  "бан", "/ban", "ban", "забанить", "/бан", "заблокировать", "блокировка",
})
# ВНИМАНИЕ: «баналл»/«банвсе»/«banall» (охват all) и «банфулл»/«банфул»/«banfull»
# (полная блокировка в проекте) НЕ перечисляем - их режим определяется суффиксами
# (_MOD_SCOPE_ALL_SUFFIXES / _MOD_SCOPE_FULL_SUFFIXES) в parse_command_mode.
_BAN_CMD_ROOTS: Tuple[str, ...] = ("бан", "ban", "забанить", "заблокировать", "блокировка")

_CANCEL_BAN_RE = re.compile(r"^(?:отмена|отменить)\s+(?:бан|бана)\b", re.IGNORECASE)

# --- Команды разбана (ручное снятие блокировки) ---
# «отмена бана» отменяет ОЖИДАНИЕ фото; разбан снимает УЖЕ выданную блокировку.
#
# Охват снятия (по аналогии с баном) определяется суффиксом и проверяет своё право:
#   • «разбан»     (chat) - снять блокировку только в текущей группе - право ban;
#   • «разбаналл»  (all)  - снять во всех официальных группах        - право banall;
#   • «разбанфулл» (full) - снять везде + полную блокировку проекта  - право banfull.
UNBAN_COMMANDS: frozenset = frozenset({
  "разбан", "разбанить", "разблокировать", "разблокировка",
  "unban", "/unban", "/разбан", "/разбанить", "/разблокировать", "/разблокировка",
})
# Корни команды разбана для распознавания суффиксов …алл / …фулл
# («разбаналл», «разбанфулл», «unbanall», «unbanfull» и т.п.).
_UNBAN_CMD_ROOTS: Tuple[str, ...] = (
  "разбан", "разбанить", "разблокировать", "разблокировка", "unban",
)
# Фразовые формы: «снять бан @user», «убрать блокировку user», а также
# «снять баналл», «снять банфулл». Группа 1 - суффикс охвата (алл/фулл).
_UNBAN_PHRASE_RE = re.compile(
  r"^(?:снять|убрать|снимите|уберите)\s+"
  r"(?:бан|бана|блок|блокировку|блокировки|блокировка)"
  r"(алл|all|все|всё|вся|фулл|фул|full)?\b",
  re.IGNORECASE,
)

BAN_LOG_FILE = os.path.join(
  os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
  "log_ban.txt",
)

_pending_bans: Dict[int, Dict[str, Any]] = LazyGameStore("_pending_bans")
_ban_system_attached = False
_ban_maintenance_last = 0.0
_BAN_MAINTENANCE_INTERVAL_SEC = 5.0

# Авто-разблокировка по истечении срока
_ban_schema_ready = False
_ban_schema_fail_last = 0.0
_ban_expiry_worker_started = False

# Срок «навсегда» по умолчанию, если администратор не указал время.
# Совпадает с поведением parse_duration("навсегда") в системе мута.
_FOREVER_DELTA: timedelta = timedelta(days=365 * 100)
_FOREVER_MINUTES: int = 365 * 100 * 24 * 60
# Порог «вечности»: всё, что ≥ 100 лет, считается постоянным баном.
_FOREVER_THRESHOLD_SEC: int = 365 * 24 * 3600 * 100


# =============================================================================
#  📝 ТЕКСТЫ СИСТЕМЫ БАНА / РАЗБАНА - меняйте текст и эмодзи ПРЯМО ЗДЕСЬ
# -----------------------------------------------------------------------------
#  Всё, что видит администратор/нарушитель в системе бана и разбана, собрано тут.
#  • Чтобы поменять текст - правьте строки.
#  • Чтобы поменять эмодзи - меняйте эмодзи прямо в строках.
#  • {фигурные_скобки} - это автоподстановка (имя, срок, причина и т.п.).
# =============================================================================

class BanText:
  # --- Строка срока блокировки ---
  TERM_FOREVER = "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : навсегда</b>"
  TERM_TIMED = (
    "<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : {duration} · до</b> "
    "<code>{until}</code>"
  )

  # --- Справка ---
  HELP = (
    "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Справка о блокировке (бан)</b>\n\n"
    "<b>Фото обязательно</b> - в подписи к команде или отдельным сообщением "
    "(до {timeout} мин.).\n\n"
    "<i>Срок указывается сразу после нарушителя, остальное - причина.</i>\n"
    "· ответ на сообщение + <code>бан 1д причина</code>\n"
    "· <code>бан @user 7д причина</code> · <code>бан username 12ч</code>\n\n"
    "<b>Срок:</b> <code>60с</code> · <code>30м</code> · <code>1ч</code> · "
    "<code>1д</code> · <code>1мес</code> · <code>1год</code> · <code>навсегда</code>\n\n"
    "<b>Охват:</b>\n"
    "· <code>бан</code> - только <i>эта</i> группа\n"
    "· <code>баналл</code> · <code>банвсе</code> - <i>все</i> официальные группы\n"
    "· <code>банфулл</code> · <code>банфул</code> - <i>все</i> группы <b>и</b> "
    "полная блокировка во <i>всём проекте</i> (WebApp)\n\n"
    "<b>Отмена ожидания:</b>\n"
    "<code>отменить бан @user</code>\n\n"
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Разблокировка (разбан):</b>\n"
    "· <code>разбан @user</code> · <code>разбан username</code> · "
    "<code>разбан ID</code> · ответ + <code>разбан</code>\n"
    "<b>Охват снятия (нужно соответствующее право):</b>\n"
    "· <code>разбан</code> - только <i>эта</i> группа (право <code>ban</code>)\n"
    "· <code>разбаналл</code> · <code>разбанвсе</code> - <i>все</i> официальные "
    "группы (право <code>banall</code>)\n"
    "· <code>разбанфулл</code> · <code>разбанфул</code> - <i>все</i> группы <b>и</b> "
    "снятие полной блокировки во <i>всём проекте</i> (право <code>banfull</code>)"
  )

  # --- 🛡️ Барьер полной блокировки (для заблокированного во всём проекте) ---
  # Показывается пользователю, который заблокирован во всём проекте (варнфулл 3/3
  # или ручная блокировка) и всё ещё пытается пользоваться ботом. Под баннером
  # барьер добавляет обзор его варнов (если варны есть) - чтобы причина была видна.
  PROJECT_BLOCK_TITLE = (
    "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Доступ к проекту закрыт</b>"
  )
  PROJECT_BLOCK_INTRO = (
    "<blockquote><i>Вы заблокированы во всём проекте, поэтому бот не принимает "
    "от вас команды. Снять блокировку может только администрация Эпсилона.</i></blockquote>"
  )

  # --- Ошибки разбора цели/срока ---
  NOT_FOUND_EXPLICIT = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>{token}</code> не найден</b>\n"
    "<blockquote><i>Проверьте @username/ID или ответьте на сообщение без указания пользователя.</i></blockquote>"
  )
  NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Кого заблокировать?</b>\n"
    "<b>Ответьте на сообщение нарушителя или напишите :</b> "
    "<code>бан [username, id, имя] [срок] [причина]</code>"
  )
  NEED_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<blockquote><i>Срок в начале команды без ответа на сообщение - "
    "сначала выберите нарушителя (ответом или @user).</i></blockquote>\n"
    "<code>бан [username, id, имя] [срок] [причина]</code>"
  )
  NOT_FOUND_USERNAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>@{username}</code> не найден</b>"
  )
  NOT_FOUND_ID = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> ID <code>{token}</code> не найден</b>"
  NOT_FOUND_NAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> «{token}» не найден</b>"
  BAD_DURATION = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Неверный срок :</b> <code>{duration}</code>"

  # --- Ожидание фото (шаг 2) ---
  PENDING = (
    "{header} <b>· ждём фото</b>\n"
    "{player_line}\n"
    "{term_line}\n"
    "{reason_part}"
    "<blockquote><i><b>Фото в этот чат за {timeout} мин.</b> · отмена - кнопкой ниже</i></blockquote>"
  )

  # --- Авто-разблокировка по истечении срока ---
  EXPIRED_GROUP = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Бан снят</b> <i>· истёк срок</i>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "<blockquote><b><i>{player_short} снова может вернуться.</i></b></blockquote>"
  )
  EXPIRED_DM = (
    "{greeting}\n"
    "<blockquote><i>срок вашей блокировки истёк - снова можете вернуться.</i></blockquote>{full_note}"
  )
  # Пометка для срочного «банфулл»: восстановлен доступ ко всему проекту.
  EXPIRED_DM_FULL_NOTE = (
    "\n<blockquote><b><i>Полная блокировка снята - доступ к приложению открыт.</i></b></blockquote>"
  )

  # --- Уведомление о бане ---
  INTRO_ALL = "{actor} заблокировал вас {scope}."
  INTRO_CHAT = "{actor} заблокировал вас в группе «{title}»."
  CLOSING_FOREVER = (
    "<blockquote><b><i>Блокировка постоянная - вернуться нельзя.</i></b></blockquote>"
  )
  CLOSING_TIMED = (
    "<blockquote><b><i>До конца срока вернуться нельзя.</i></b></blockquote>"
  )
  VIOLATOR = (
    "{greeting}\n"
    "{header}\n"
    "{staff_line}"
    "<blockquote><i>{intro}</i></blockquote>\n"
    "{term_line}{reason_suffix}\n"
    "{closing}"
  )
  GROUP_TITLE = "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Участник заблокирован</b>"
  GROUP_FOOTER_FOREVER = "<blockquote><b><i>{actor} заблокировал {player_short} навсегда.</i></b></blockquote>"
  GROUP_FOOTER_TIMED = "<blockquote><b><i>{actor} заблокировал {player_short} до {until}.</i></b></blockquote>"
  GROUP = (
    "{group_title}\n"
    "{player_line}\n"
    "{staff_line}"
    "{term_line}{reason_suffix}\n"
    "{group_footer}"
  )

  # --- Успех (в исходной группе) ---
  WARN_NONE = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "<i>Не удалось заблокировать - проверьте права бота.</i></b>"
  )
  WARN_PARTIAL = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "<i>Заблокирован в {count} групп; часть чатов пропущена.</i></b>"
  )
  SUCCESS = (
    "{header} <b>· выполнен</b>\n"
    "{player_line}\n"
    "{staff_line}\n"
    "{term_line}\n"
    "{reason_block}{full_note}{warn}"
  )
  # Пометка о полной блокировке во всём проекте (режим banfull).
  FULL_NOTE = (
    "\n<b><i>Закрыт доступ к группам и приложению проекта.</i></b>"
  )

  # --- Пруф / ошибки ---
  PROOF_MISSING = (
    "<b><tg-emoji emoji-id='5454419255430767770'>📎</tg-emoji> Блокировка не выполнена</b>\n"
    "<blockquote><i>Фото-доказательство не получено.</i></blockquote>"
  )
  DB_ERROR = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ошибка - не удалось сохранить бан.</b>"
  NEED_PHOTO = "<b><tg-emoji emoji-id='5305265301917549162'>📎</tg-emoji> Нужно фото - прикрепите изображение.</b>"
  WRONG_CHAT = (
    "{greeting}\n"
    "{staff_line}\n"
    "{player_line}"
    "{pending_chat_line}"
    "<blockquote><b>Отправьте фото в тот же чат, где была выдана команда бана.</b></blockquote>"
  )

  # --- Запреты / предпроверка ---
  SELF = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя заблокировать себя</b>"
  BOT = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя заблокировать бота</b>"
  BLOCKED = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> {reason}</b>"

  # --- Ожидание: истекло / отмена ---
  PENDING_EXPIRED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Время ожидания истекло</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "{reason_part}"
    "<blockquote><b><i>Блокировка не применена - фото не получено вовремя.</i></b></blockquote>"
  )
  PENDING_CANCELLED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "{reason_part}"
    "<blockquote><b><i>Блокировка не применена - фото больше не требуется.</i></b></blockquote>"
  )
  CANCEL_FALLBACK = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "<blockquote><i>Блокировка не применена - фото больше не требуется.</i></blockquote>"
  )
  PENDING_SUPERSEDED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "<blockquote><b><i>Начато новое действие модерации - это ожидание фото "
    "больше не активно.</i></b></blockquote>"
  )

  # --- Отмена ожидания (команды) ---
  CANCEL_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<code>отменить бан @user</code> · <code>отменить бан username</code>\n"
    "<blockquote><i>Или ответьте на сообщение нарушителя.</i></blockquote>"
  )
  NO_PENDING = (
    "{greeting}\n"
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет ожидания бана</b>\n"
    "{player_line}\n"
    "<blockquote><i>Для этого нарушителя сейчас не ожидается фото-подтверждение.</i></blockquote>"
  )
  OTHER_PENDING = (
    "{greeting}\n"
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Другой нарушитель в ожидании</b>\n"
    "<b>Сейчас ожидается фото для:\n{pending_player_line}</b>\n\n"
    "<blockquote><i>Для отмены укажите: <code>{cancel_hint}</code></i></blockquote>"
  )
  CANCEL_HELP = (
    "{greeting}\n"
    "{staff_line}\n"
    "{player_line}\n"
    "<b>Для отмены укажите, для кого отменяется ожидание бана:</b>\n"
    "<code>{cancel_hint}</code>\n\n"
    "<blockquote><i>Либо нажмите кнопку «Отменить ожидание» под сообщением о фото.</i></blockquote>"
  )

  # --- Разбан ---
  UNBAN_NOT_FOUND_USERNAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>@{username}</code> не найден</b>\n"
    "<blockquote><i>Проверьте @username/ID или ответьте на сообщение нарушителя.</i></blockquote>"
  )
  UNBAN_NOT_FOUND_ID = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> ID <code>{token}</code> не найден</b>"
  UNBAN_NOT_FOUND_NAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> «{body}» не найден</b>"
  UNBAN_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Кого разблокировать?</b>\n"
    "<b>Ответьте на сообщение нарушителя или напишите :</b>\n"
    "<code>разбан @user</code> · <code>разбан username</code> · "
    "<code>разбан ID</code> · <code>разбан Имя</code>"
  )
  UNBAN_BOT = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Это бот</b>"
  NOT_BANNED = (
    "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> {player_short} не заблокирован</b>\n"
    "{staff_line}\n"
    "{player_line}"
  )
  UNBAN_DM = (
    "{greeting}\n"
    "{staff_line}\n"
    "<blockquote><i>{actor} снял вашу блокировку - снова можете вернуться.</i></blockquote>"
  )
  UNBAN_GROUP_TITLE = "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Участник разблокирован</b>"
  UNBAN_GROUP = (
    "{group_title}\n"
    "{player_line}\n"
    "{staff_line}\n"
    "{chat_line}\n"
    "<blockquote><b><i>{actor} снял блокировку с {player_short}.</i></b></blockquote>"
  )
  UNBAN_SUCCESS = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Разблокировка выполнена</b>\n"
    "{staff_line}\n"
    "{player_line}{groups_part}"
  )

  # --- Кнопки и всплывающие ответы (callback) ---
  BTN_RETURN = "Вернуться: {title}"
  BTN_CANCEL = "Отменить ожидание"
  BTN_REVOKE = "Снять бан"
  CB_BAD_DATA = "Некорректные данные."
  CB_ONLY_AUTHOR = "Отменить может только автор команды."
  CB_DB = "База данных временно недоступна."
  CB_NO_PERM = "Недостаточно прав."
  CB_DONE = "Ожидание уже завершено или истекло."
  CB_STALE = "Данные устарели. Используйте команду отмены."
  CB_WRONG_CHAT = "Действие недоступно в этой группе."
  CB_CANCELLED = "Ожидание отменено."
  CB_REVOKED = "Бан снят."
  CB_NOT_BANNED = "Нарушитель не заблокирован."
  CB_REVOKE_FAILED = "Не удалось снять бан - попробуйте позже."
  CB_SELF_REVOKE = SELF_REVOKE_ALERT
  REVOKED_EDIT = (
    "<b><tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> Бан снят</b>\n"
    "{player_line}\n{chat_line}\n{staff_line}"
    "<blockquote><b><i>{player_short} разблокирован во всех группах проекта.</i></b></blockquote>"
  )


class BanDebug:
  @staticmethod
  def log(stage: str, detail: str, **fields: Any) -> None:
    if not cfg.DEBUG:
      return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items()) if fields else ""
    line = f"[BAN][{stage}] {detail}" + (f" | {extra}" if extra else "")
    print(line)
    try:
      with open(BAN_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception as e:
      print(f"[BAN][LOGFILE] write error: {e}")

  @staticmethod
  def error(stage: str, detail: str, exc: Optional[BaseException] = None, **fields: Any) -> None:
    tb = traceback.format_exc() if exc else ""
    BanDebug.log(stage, f"ERROR: {detail}", **fields)
    if tb:
      print(tb)
      try:
        with open(BAN_LOG_FILE, "a", encoding="utf-8") as fh:
          fh.write(tb + "\n")
      except Exception:
        pass


def _debug_hint(code: str) -> str:
  if not cfg.DEBUG_ADMIN_HINTS:
    return ""
  return f"\n\n<i>🔧 debug:</i> <code>{escape(code)}</code>"


@dataclass
class ParsedBan:
  target_id: int
  target_name: str
  target_username: Optional[str]
  duration_text: str
  time_delta: timedelta
  duration_minutes: int
  ban_until: datetime
  reason: str
  scope: Scope = "chat"
  # Режим: chat (эта группа) / all (все группы) / full (все группы + весь проект).
  mode: Mode = "chat"

  @property
  def is_full(self) -> bool:
    return self.mode == "full"


def _is_forever(parsed: ParsedBan) -> bool:
  """True, если бан выдан навсегда (постоянный)."""
  return parsed.time_delta.total_seconds() >= _FOREVER_THRESHOLD_SEC


def _ban_badge(mode: Mode) -> str:
  """Короткая «шапка» с названием системы и охватом - видна в каждой карточке."""
  if mode == "full":
    return (
      "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Банфулл</b> "
      "<i>· весь проект</i>"
    )
  if mode == "all":
    return (
      "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Баналл</b> "
      "<i>· все группы</i>"
    )
  return (
    "<b><tg-emoji emoji-id='5834895792409677476'>⛔️</tg-emoji> Бан</b> "
    "<i>· эта группа</i>"
  )


def _ban_until_for_telegram(parsed: ParsedBan):
  """until_date для Telegram: None при вечном бане (постоянная блокировка)."""
  if _is_forever(parsed):
    return None
  return _until_to_telegram_date(parsed.ban_until)


def _term_line(parsed: ParsedBan) -> str:
  """Строка срока для уведомлений. Для вечного бана дата разблокировки не указывается."""
  if _is_forever(parsed):
    return BanText.TERM_FOREVER
  return BanText.TERM_TIMED.format(
    duration=_format_duration_short(parsed.time_delta),
    until=_format_until(parsed.ban_until),
  )


def _pending_ban_term_line(parsed: ParsedBan) -> str:
  """Срок в ожидании пруфа - без точной даты окончания."""
  if _is_forever(parsed):
    return BanText.TERM_FOREVER
  duration = _format_duration_short(parsed.time_delta)
  return f"<b><tg-emoji emoji-id='5348236797606379943'>⏰</tg-emoji> Срок : {duration}</b>"


def _refresh_parsed_ban_expiry(parsed: ParsedBan) -> None:
  from bot.admins.mute import _normalize_time_delta
  parsed.time_delta = _normalize_time_delta(parsed.time_delta)
  parsed.ban_until = _rebase_expiry_at_now(parsed.time_delta)


def _cmd_word(text: str) -> str:
  parts = (text or "").strip().split()
  if not parts:
    return ""
  return parts[0].lower().split("@")[0]


def _ban_command_mode(text: str) -> Mode:
  """Режим бана из текста команды: chat (бан) / all (баналл) / full (банфулл)."""
  ok, mode = parse_command_mode(_cmd_word(text), BAN_COMMANDS, _BAN_CMD_ROOTS)
  return mode if ok else "chat"


def _ban_command_scope(text: str) -> Scope:
  return mode_to_scope(_ban_command_mode(text))


def _is_ban_command(text: str) -> bool:
  ok, _ = parse_command_mode(_cmd_word(text), BAN_COMMANDS, _BAN_CMD_ROOTS)
  return ok


# Режим бана → ключ права в staff_rules (ban / banall / banfull).
_BAN_MODE_PERMISSION: Dict[str, str] = {
  "chat": "ban",
  "all": "banall",
  "full": "banfull",
}


def _ban_permission_action(text: str) -> str:
  return _BAN_MODE_PERMISSION.get(_ban_command_mode(text), "ban")


def _is_cancel_ban_command(text: str) -> bool:
  return bool(_CANCEL_BAN_RE.match((text or "").strip()))


def _suffix_to_mode(suffix: str) -> Mode:
  """Суффикс охвата → режим: алл/all → all; фулл/фул/full → full; иначе chat."""
  s = (suffix or "").strip().lower()
  if not s:
    return "chat"
  if s in _MOD_SCOPE_FULL_SUFFIXES:
    return "full"
  if s in _MOD_SCOPE_ALL_SUFFIXES:
    return "all"
  return "chat"


def _is_unban_command(text: str) -> bool:
  t = (text or "").strip()
  if not t:
    return False
  ok, _ = parse_command_mode(_cmd_word(t), UNBAN_COMMANDS, _UNBAN_CMD_ROOTS)
  if ok:
    return True
  return bool(_UNBAN_PHRASE_RE.match(t))


def _unban_command_mode(text: str) -> Mode:
  """Режим разбана из текста: chat (разбан) / all (разбаналл) / full (разбанфулл)."""
  t = (text or "").strip()
  if not t:
    return "chat"
  ok, mode = parse_command_mode(_cmd_word(t), UNBAN_COMMANDS, _UNBAN_CMD_ROOTS)
  if ok:
    return mode
  m = _UNBAN_PHRASE_RE.match(t)
  if m:
    return _suffix_to_mode(m.group(1) or "")
  return "chat"


def _unban_permission_action(text: str) -> str:
  """Право для разбана по охвату: разбан→ban, разбаналл→banall, разбанфулл→banfull."""
  return _BAN_MODE_PERMISSION.get(_unban_command_mode(text), "ban")


# Режим разбана → ключ действия для текста отказа (корректная формулировка
# именно про СНЯТИЕ блокировки, а не про выдачу).
_UNBAN_MODE_ACTION: Dict[str, str] = {
  "chat": "unban",
  "all": "unbanall",
  "full": "unbanfull",
}


def _unban_deny_action(text: str) -> str:
  return _UNBAN_MODE_ACTION.get(_unban_command_mode(text), "unban")


def _strip_unban_prefix(text: str) -> str:
  """Текст после команды разбана (цель: @user, username, id, имя)."""
  t = (text or "").strip()
  ok, _ = parse_command_mode(_cmd_word(t), UNBAN_COMMANDS, _UNBAN_CMD_ROOTS)
  if ok:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  m = _UNBAN_PHRASE_RE.match(t)
  if m:
    return t[m.end():].strip()
  return ""


def _is_ban_related_message(message: Message) -> bool:
  if not message.from_user:
    return False
  text = _get_command_text(message)
  if text:
    low = text.lower()
    if _is_cancel_ban_command(text):
      return True
    if _is_unban_command(text):
      return True
    if _is_ban_command(text):
      return True
    if low in ("отмена", "cancel", "/cancel"):
      return True
  from bot.admins.punish_proof import pending_contains
  if _has_proof_media(message) and pending_contains(_pending_bans, message.from_user.id):
    return True
  return False


def _strip_cancel_ban_prefix(text: str) -> str:
  m = _CANCEL_BAN_RE.match((text or "").strip())
  if not m:
    return ""
  return text[m.end():].strip()


def _looks_like_username_token(token: str) -> bool:
  from bot.admins.mute import _looks_like_telegram_username
  return _looks_like_telegram_username(token)


def _suggest_cancel_ban_command(
  target_id: int,
  target_name: str,
  target_username: Optional[str] = None,
) -> str:
  if target_username:
    return f"отменить бан @{target_username.lstrip('@')}"
  if target_name and not str(target_name).isdigit():
    return f"отменить бан {target_name}"
  return f"отменить бан {target_id}"


def _ban_cancel_callback_data(admin_id: int, target_id: int) -> str:
  return f"ban:cancel:{admin_id}:{target_id}"


def _ban_pending_cancel_keyboard(admin_id: int, target_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=BanText.BTN_CANCEL,
      callback_data=_ban_cancel_callback_data(admin_id, target_id),
    ),
  ]])


def _ban_revoke_callback_data(admin_id: int, target_id: int, mode: Mode = "full") -> str:
  # mode хранит охват выданного бана (chat/all/full), чтобы кнопка снимала ровно
  # тот же охват и проверяла соответствующее право (ban/banall/banfull).
  return f"ban:revoke:{admin_id}:{target_id}:{mode}"


def _ban_revoke_keyboard(
  admin_id: int, target_id: int, mode: Mode = "full",
) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=BanText.BTN_REVOKE,
      callback_data=_ban_revoke_callback_data(admin_id, target_id, mode),
    ),
  ]])


def _build_pending_ban_proof_text(
  parsed: ParsedBan,
  chat_line: str,
  cancel_hint: str,
) -> str:
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  return BanText.PENDING.format(
    player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
    chat_line=chat_line,
    header=_ban_badge(parsed.mode),
    scope_block=_format_scope_block(parsed.scope),
    term_line=_pending_ban_term_line(parsed),
    reason_part=reason_part,
    timeout=cfg.proof_timeout_minutes(),
    cancel_hint=escape(cancel_hint),
  )


async def _send_ban_help(message: Message) -> None:
  await message.reply(
    BanText.HELP.format(timeout=cfg.proof_timeout_minutes()),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def parse_ban_command(message: Message) -> ParsedBan | ParseError:
  text = _get_command_text(message)
  parts = text.split()
  BanDebug.log("PARSE", "start", text=text, parts=parts, reply=bool(message.reply_to_message))

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
          "ban_user_not_found",
          BanText.NOT_FOUND_ID.format(token=escape(not_found)),
          not_found,
        )
      return ParseError(
        "ban_user_not_found",
        BanText.NOT_FOUND_EXPLICIT.format(token=escape(not_found)),
        not_found,
      )
  else:
    if not body:
      return ParseError(
        "ban_no_target",
        BanText.NO_TARGET,
        "no reply and empty body",
      )

    if _body_starts_with_duration(body) or parse_duration(body[0]):
      return ParseError(
        "ban_no_target",
        BanText.NEED_TARGET,
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
          "ban_user_not_found",
          BanText.NOT_FOUND_USERNAME.format(username=escape(username)),
          first,
        )
      if first.isdigit():
        return ParseError(
          "ban_user_not_found",
          BanText.NOT_FOUND_ID.format(token=escape(first)),
          first,
        )
      return ParseError(
        "ban_user_not_found",
        BanText.NOT_FOUND_NAME.format(token=escape(first)),
        first,
      )
    rest = body[1:]

  dur_text, reason, _ = _extract_duration_and_reason(rest, 0)
  if not dur_text:
    # Срок не указан («бан @user» / «баналл @user [причина]») → бан навсегда.
    # Весь остаток после нарушителя считаем причиной.
    dur_text = "навсегда"
    reason = " ".join(rest).strip() or "Не указана"
    time_delta, duration_minutes = _FOREVER_DELTA, _FOREVER_MINUTES
  else:
    parsed_dur = parse_duration(dur_text)
    if not parsed_dur:
      return ParseError(
        "ban_bad_duration",
        BanText.BAD_DURATION.format(duration=escape(dur_text)),
        dur_text,
      )
    time_delta, duration_minutes = parsed_dur
    time_delta = _normalize_time_delta(time_delta)

  ban_until = _rebase_expiry_at_now(time_delta)
  mode = _ban_command_mode(text)
  scope = mode_to_scope(mode)
  return ParsedBan(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    duration_text=dur_text,
    time_delta=time_delta,
    duration_minutes=duration_minutes,
    ban_until=ban_until,
    reason=reason,
    scope=scope,
    mode=mode,
  )


# ---------------------------------------------------------------------------
# Авто-разблокировка: схема, учёт активных банов, фоновый воркер
# ---------------------------------------------------------------------------

async def _ensure_ban_schema() -> None:
  """Создаёт таблицу active_bans для отслеживания срочных банов."""
  global _ban_schema_ready, _ban_schema_fail_last
  if _ban_schema_ready:
    return
  if not await _db().ensure_pool():
    now = time.time()
    if now - _ban_schema_fail_last > 60:
      BanDebug.log("SCHEMA", "ensure skipped - db unavailable")
      _ban_schema_fail_last = now
    return
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_bans (
          user_id         BIGINT      NOT NULL,
          chat_id         BIGINT      NOT NULL,
          ban_until       TIMESTAMP   NOT NULL,
          target_name     TEXT,
          target_username TEXT,
          admin_user_id   BIGINT,
          admin_name      TEXT,
          admin_role      TEXT,
          reason          TEXT,
          scope           TEXT,
          mode            TEXT        DEFAULT 'chat',
          created_at      TIMESTAMP   DEFAULT NOW(),
          PRIMARY KEY (user_id, chat_id)
        )
        """,
      )
      # Мягкая миграция для уже существующих таблиц: столбец mode хранит
      # охват наказания (chat/all/full). Нужен, чтобы при авто-снятии срочного
      # «банфулл» снять и полную блокировку проекта (users.banned + banusers).
      try:
        await conn.execute(
          "ALTER TABLE active_bans ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'chat'",
        )
      except Exception as e:
        BanDebug.log("SCHEMA", "active_bans mode column skip", err=str(e))
    _ban_schema_ready = True
    BanDebug.log("SCHEMA", "active_bans ready")
  except DbUnavailableError as e:
    now = time.time()
    if now - _ban_schema_fail_last > 60:
      BanDebug.log("SCHEMA", "ensure skipped", err=str(e))
      _ban_schema_fail_last = now
  except Exception as e:
    BanDebug.error("SCHEMA", "ensure", e)


async def _record_active_bans(
  parsed: ParsedBan,
  *,
  banned_chat_ids: List[int],
  admin_user_id: int,
  admin_name: str,
  admin_role: Optional[str],
) -> None:
  """
  Запоминает срочные баны для последующей авто-разблокировки.
  Вечные баны не записываются - они не истекают.
  """
  if _is_forever(parsed) or not banned_chat_ids:
    return
  await _ensure_ban_schema()
  if not _ban_schema_ready:
    return
  try:
    async with _db_acquire() as conn:
      async with conn.transaction():
        for cid in banned_chat_ids:
          await conn.execute(
            """
            INSERT INTO active_bans (
              user_id, chat_id, ban_until, target_name, target_username,
              admin_user_id, admin_name, admin_role, reason, scope, mode
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (user_id, chat_id) DO UPDATE
            SET ban_until       = EXCLUDED.ban_until,
                target_name     = EXCLUDED.target_name,
                target_username = EXCLUDED.target_username,
                admin_user_id   = EXCLUDED.admin_user_id,
                admin_name      = EXCLUDED.admin_name,
                admin_role      = EXCLUDED.admin_role,
                reason          = EXCLUDED.reason,
                scope           = EXCLUDED.scope,
                mode            = EXCLUDED.mode
            """,
            parsed.target_id, cid, parsed.ban_until,
            parsed.target_name, parsed.target_username,
            admin_user_id, admin_name, admin_role, parsed.reason,
            parsed.scope, parsed.mode,
          )
    BanDebug.log(
      "DB", "active bans recorded",
      target=parsed.target_id, chats=banned_chat_ids, until=str(parsed.ban_until),
    )
  except DbUnavailableError as e:
    BanDebug.log("DB", "record active bans skipped", err=str(e))
  except Exception as e:
    BanDebug.error("DB", "record active bans", e, target=parsed.target_id)


async def _delete_active_ban(user_id: int, chat_id: int) -> None:
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        "DELETE FROM active_bans WHERE user_id = $1 AND chat_id = $2",
        user_id, chat_id,
      )
  except Exception as e:
    BanDebug.log("DB", "delete active ban skip", err=str(e), user=user_id, chat=chat_id)


async def _unban_in_chat(chat_id: int, user_id: int) -> bool:
  """Снимает блокировку в группе (идемпотентно; Telegram уже мог снять по сроку)."""
  if chat_id > 0:
    return False
  try:
    await _bot().unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
    BanDebug.log("TG", "unban OK", chat_id=chat_id, user_id=user_id)
    return True
  except TypeError:
    try:
      await _bot().unban_chat_member(chat_id=chat_id, user_id=user_id)
      return True
    except Exception as e:
      BanDebug.error("TG", "unban", e, chat_id=chat_id, user_id=user_id)
      return False
  except Exception as e:
    BanDebug.error("TG", "unban", e, chat_id=chat_id, user_id=user_id)
    return False


async def _notify_ban_expired_group(
  chat_id: int, row: Any, affected_chats: Optional[List[int]] = None,
) -> None:
  player = PlayerRef(
    int(row["user_id"]),
    row["target_name"] or str(row["user_id"]),
    row["target_username"],
  )
  chat_line = await _format_chats_line(affected_chats or [chat_id], current_chat_id=chat_id)
  text = BanText.EXPIRED_GROUP.format(
    player_line=player.line, chat_line=chat_line, player_short=player.short,
  )
  try:
    await _bot().send_message(
      chat_id, text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    BanDebug.log("NOTIFY", "expire group skip", chat_id=chat_id, err=str(e))


async def _notify_ban_expired_user(
  user_id: int,
  target_name: str,
  target_username: Optional[str],
  chat_ids: List[int],
  full_lifted: bool = False,
) -> None:
  player = PlayerRef(user_id, target_name or str(user_id), target_username)
  links: List[InlineKeyboardButton] = []
  for cid in chat_ids:
    disp = await _get_chat_display(cid)
    if disp.link_url:
      links.append(InlineKeyboardButton(text=BanText.BTN_RETURN.format(title=disp.title), url=disp.link_url))
      if len(links) >= 3:
        break
  text = BanText.EXPIRED_DM.format(
    greeting=player.greeting,
    full_note=BanText.EXPIRED_DM_FULL_NOTE if full_lifted else "",
  )
  try:
    if links:
      kb = InlineKeyboardMarkup(inline_keyboard=[[b] for b in links])
      await _bot().send_message(
        user_id, text, parse_mode="HTML", reply_markup=kb,
        link_preview_options=NO_PREVIEW,
      )
    else:
      await _bot().send_message(
        user_id, text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
  except Exception as e:
    BanDebug.log("NOTIFY", "expire user skip", user_id=user_id, err=str(e))


def _as_naive(dt: Optional[datetime]) -> Optional[datetime]:
  """Приводит дату к наивной (без tz), чтобы сравнивать с datetime.now()."""
  if dt is None:
    return None
  if dt.tzinfo is not None:
    return dt.replace(tzinfo=None)
  return dt


async def list_active_bans_for_user(user_id: int) -> List[Dict[str, Any]]:
  """Активные (ещё не истёкшие) срочные баны пользователя по группам.

  Используется сводкой «наказания». Возвращает список словарей с ключами:
  chat_id, ban_until, reason, admin_name, admin_role, scope.
  Постоянные (вечные) баны здесь не отслеживаются - они не записываются
  в active_bans, поэтому в сводку не попадают.
  """
  await _ensure_ban_schema()
  if not _ban_schema_ready:
    return []
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT chat_id, ban_until, reason, admin_name, admin_role, scope
        FROM active_bans
        WHERE user_id = $1
        ORDER BY ban_until
        """,
        user_id,
      )
  except Exception as e:
    BanDebug.log("DB", "list active bans skip", err=str(e), user=user_id)
    return []
  now = datetime.now()
  out: List[Dict[str, Any]] = []
  for r in rows:
    bu = _as_naive(r["ban_until"])
    if bu is not None and bu <= now:
      continue  # срок уже истёк - авто-разблокировка снимет такие записи
    out.append(dict(r))
  return out


async def _scan_expired_bans() -> None:
  """Находит истёкшие срочные баны, снимает их и уведомляет группы и нарушителя."""
  if not await _db().ensure_pool():
    return
  await _ensure_ban_schema()
  if not _ban_schema_ready:
    return
  try:
    async with _db_acquire() as conn:
      # Сравнение срока делаем в Python тем же datetime.now(), которым бан
      # создавался - это исключает рассинхрон таймзоны сессии БД и NOW().
      all_rows = await conn.fetch(
        """
        SELECT user_id, chat_id, ban_until, target_name, target_username, mode
        FROM active_bans
        ORDER BY ban_until
        LIMIT 500
        """,
      )
  except DbUnavailableError:
    return
  except Exception as e:
    if _is_transient_db_error(e):
      BanDebug.log("AUTO", "db scan skipped", err=str(e))
    else:
      BanDebug.error("AUTO", "db scan", e)
    return

  now = datetime.now()
  rows = [r for r in all_rows if (_as_naive(r["ban_until"]) or now) <= now]
  if not rows:
    return

  # 1-й проход - группируем по пользователю, чтобы знать ВСЕ затронутые группы
  # ещё до отправки уведомлений (для перечисления «также в группах …»).
  per_user: Dict[int, Dict[str, Any]] = {}
  for row in rows:
    uid = int(row["user_id"])
    cid = int(row["chat_id"])
    entry = per_user.setdefault(uid, {
      "name": row["target_name"] or str(uid),
      "username": row["target_username"],
      "chats": [],
      "rows": {},
      "all_cids": [],
      "full": False,
      "scope": "chat",
    })
    entry["all_cids"].append(cid)
    if _is_staff_chat(cid):
      if cid not in entry["chats"]:
        entry["chats"].append(cid)
      entry["rows"][cid] = row
    # Охват для лога авто-разблокировки: берём максимальный (full > all > chat).
    _row_mode = row["mode"] or "chat"
    _scope_rank = {"chat": 0, "all": 1, "full": 2}
    if _scope_rank.get(_row_mode, 0) > _scope_rank.get(entry["scope"], 0):
      entry["scope"] = _row_mode
    # Срочный «банфулл» - снимаем и полную блокировку во всём проекте.
    if _row_mode == "full":
      entry["full"] = True

  # 2-й проход - снимаем бан и шлём по одному сообщению на группу.
  for uid, info in per_user.items():
    staff_chats: List[int] = info["chats"]
    for cid in staff_chats:
      await _unban_in_chat(cid, uid)
      await _notify_ban_expired_group(cid, info["rows"][cid], staff_chats)
      BanDebug.log("AUTO", "ban expired", user_id=uid, chat_id=cid)
    for cid in info["all_cids"]:
      await _delete_active_ban(uid, cid)
    full_lifted = False
    if info.get("full"):
      full_lifted = await _lift_full_project_block(uid)
      BanDebug.log("AUTO", "full block lifted on expiry", user_id=uid, ok=full_lifted)
    # Аудит авто-разблокировки в архив (как у мутов): одна запись на пользователя.
    _log_chat = staff_chats[0] if (info["scope"] == "chat" and staff_chats) else 0
    await _log_auto_unban_db(uid, info["name"], _log_chat, info["scope"])
    await _notify_ban_expired_user(
      uid, info["name"], info["username"], staff_chats, full_lifted=full_lifted,
    )


async def expire_bans_from_timer(entry: Dict[str, Any]) -> None:
  """Снятие истёкших банов по таймеру из punish_timers (идемпотентно)."""
  await _scan_expired_bans()
  try:
    from bot.admins import punish_timers
    punish_timers.cancel_ban(int(entry["user_id"]))
  except Exception:
    pass


async def _ban_expiry_loop() -> None:
  """Фоновый цикл авто-разблокировки истёкших банов."""
  BanDebug.log("WORKER", "started")
  while True:
    try:
      await asyncio.sleep(cfg.WORKER_INTERVAL_SEC)
      await _scan_expired_bans()
    except asyncio.CancelledError:
      break
    except Exception as e:
      BanDebug.error("WORKER", "tick", e)


def _ensure_ban_expiry_worker() -> None:
  """Лениво запускает фоновый воркер (нужен запущенный event loop)."""
  global _ban_expiry_worker_started
  if _ban_expiry_worker_started:
    return
  try:
    asyncio.get_running_loop()
  except RuntimeError:
    return  # event loop ещё не запущен - стартуем позже
  _ban_expiry_worker_started = True
  ensure_proof_pending_worker()
  asyncio.create_task(_ban_expiry_loop())
  BanDebug.log("WORKER", "scheduled")


# ---------------------------------------------------------------------------
# Telegram-операции
# ---------------------------------------------------------------------------

_BLOCKING_BAN_ERRORS = frozenset({
  "нельзя заблокировать бота",
  "нельзя заблокировать создателя группы",
  "нельзя заблокировать администратора Telegram",
  "пользователь не найден в Telegram",
})


async def _validate_ban_target_in_chat(chat_id: int, target_id: int) -> Optional[str]:
  """Блокирующая ошибка или None. Отсутствие в группе НЕ ошибка (превентивный бан)."""
  if chat_id > 0:
    return "блокировка доступна только в группах"
  from bot.admins.punish_validate import inspect_chat_member
  member, err = await inspect_chat_member(chat_id, target_id)
  if err == "invalid_user":
    return "пользователь не найден в Telegram"
  if member is None and err == "check_failed":
    BanDebug.log("TG", "get_chat_member", chat_id=chat_id, user_id=target_id, err=err)
    return None  # не удалось проверить - разрешаем попытку (мог ещё не вступить)
  if member is None:
    return None  # not_participant — превентивный бан допустим

  status = getattr(member, "status", None)
  user = getattr(member, "user", None)
  if user and getattr(user, "is_bot", False):
    return "нельзя заблокировать бота"
  if status == "creator":
    return "нельзя заблокировать создателя группы"
  if status == "administrator":
    return "нельзя заблокировать администратора Telegram"
  return None


async def _ban_in_chat(chat_id: int, user_id: int, tg_until: Optional[int]) -> bool:
  """
  Банит пользователя в группе.

  tg_until = None  → постоянная блокировка (дата разблокировки не передаётся);
  tg_until = int   → Telegram сам снимет блокировку, когда наступит это время.
  """
  if chat_id > 0:
    return False
  try:
    if tg_until is None:
      await _bot().ban_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        revoke_messages=False,
      )
      BanDebug.log("TG", "ban OK (forever)", chat_id=chat_id, user_id=user_id)
    else:
      await _bot().ban_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        until_date=tg_until,
        revoke_messages=False,
      )
      BanDebug.log("TG", "ban OK", chat_id=chat_id, user_id=user_id, until=tg_until)
    return True
  except TypeError:
    try:
      await _bot().ban_chat_member(chat_id=chat_id, user_id=user_id)
      BanDebug.log("TG", "ban OK (legacy)", chat_id=chat_id, user_id=user_id)
      return True
    except Exception as e:
      BanDebug.error("TG", "ban", e, chat_id=chat_id, user_id=user_id)
      return False
  except Exception as e:
    from bot.admins.punish_validate import is_invalid_telegram_user_error
    if is_invalid_telegram_user_error(e):
      BanDebug.log("TG", "ban invalid user", chat_id=chat_id, user_id=user_id)
      return False
    BanDebug.error("TG", "ban", e, chat_id=chat_id, user_id=user_id)
    return False


async def _validate_ban_before(
  target_id: int,
  *,
  scope: Scope,
  source_chat_id: int,
) -> Optional[str]:
  """Предпроверка бана: только блокирующая ошибка (бот/создатель/админ) или текст об охвате."""
  chat_ids = list(cfg.STAFF_CHAT_IDS) if scope == "all" else [source_chat_id]
  for cid in chat_ids:
    if scope == "chat" and not _is_staff_chat(cid):
      return "команда доступна только в официальных группах проекта"
    err = await _validate_ban_target_in_chat(cid, target_id)
    if err in _BLOCKING_BAN_ERRORS:
      return err
  return None


async def _ban_with_scope(
  target_id: int,
  tg_until: Optional[int],
  *,
  scope: Scope,
  source_chat_id: int,
) -> Tuple[int, List[int], List[str]]:
  """Блокирует в одной группе или во всех группах проекта."""
  if scope == "all":
    return await _ban_in_all_staff_chats(target_id, tg_until)

  if not _is_staff_chat(source_chat_id):
    return 0, [], ["команда доступна только в официальных группах проекта"]

  err = await _validate_ban_target_in_chat(source_chat_id, target_id)
  if err:
    return 0, [], [err]

  if await _ban_in_chat(source_chat_id, target_id, tg_until):
    return 1, [source_chat_id], []
  return 0, [], ["не удалось заблокировать в группе"]


async def _ban_in_all_staff_chats(
  target_id: int,
  tg_until: Optional[int],
) -> Tuple[int, List[int], List[str]]:
  """Банит во всех группах проекта (в т.ч. превентивно, даже если сейчас не состоит)."""
  banned: List[int] = []
  errors: List[str] = []
  for cid in cfg.STAFF_CHAT_IDS:
    err = await _validate_ban_target_in_chat(cid, target_id)
    if err in _BLOCKING_BAN_ERRORS:
      errors.append(err)
      continue
    if err:
      errors.append(f"чат {cid}: {err}")
      continue
    if await _ban_in_chat(cid, target_id, tg_until):
      banned.append(cid)
  return len(banned), banned, errors


async def _apply_ban_db(
  target_user_id: int,
  target_name: str,
  target_username: Optional[str],
  ban_until: datetime,
  admin_user_id: int,
  admin_name: str,
  reason: str,
  proof_media_id: str,
  duration_minutes: int,
  chat_id: int,
  mode: Mode = "chat",
) -> Tuple[bool, Optional[int]]:
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
        row = await conn.fetchrow(
          """
          INSERT INTO staff_actions (
            admin_user_id, admin_name, action_type,
            target_player_id, target_name,
            reason, proof_media_id, duration_minutes, chat_id, scope,
            proof_bot_token
          )
          VALUES ($1, $2, 'ban', $3, $4, $5, $6, $7, $8, $9, $10)
          RETURNING id
          """,
          admin_user_id, admin_name, target_user_id, target_name,
          reason, proof_media_id, duration_minutes, chat_id, mode,
          _proof_owner_token(proof_media_id),
        )
        action_id = row["id"] if row else None
        BanDebug.log(
          "DB", "ban saved",
          target=target_user_id, chat_id=chat_id, until=str(ban_until),
          proof=proof_media_id[:24], action_id=action_id,
        )
        return True, action_id
  except DbUnavailableError as e:
    BanDebug.log("DB", "apply_ban skipped", err=str(e), target=target_user_id)
    return False, None
  except Exception as e:
    BanDebug.error("DB", "apply_ban", e, target=target_user_id)
    return False, None


async def _ensure_users_ban_columns(conn) -> None:
  """
  Мягко гарантирует наличие столбцов полной блокировки в таблице users:
    • banned        BOOLEAN - флаг блокировки для WebApp-приложения;
    • banned_at     TIMESTAMP - момент выдачи полной блокировки;
    • banned_reason TEXT - причина полной блокировки.

  Безопасно вызывать многократно (ADD COLUMN IF NOT EXISTS). Ошибки отдельных
  ALTER не прерывают остальные - каждый изолирован.
  """
  statements = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMP",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason TEXT",
  )
  for stmt in statements:
    try:
      await conn.execute(stmt)
    except Exception as e:
      BanDebug.log("FULL", "ensure users ban column skip", stmt=stmt[:48], err=str(e))


async def _apply_full_project_block(
  target_id: int,
  target_name: str,
  target_username: Optional[str],
  reason: str,
) -> bool:
  """
  Полная блокировка нарушителя во ВСЁМ проекте (режим banfull / варнфулл):
    • users.banned = TRUE  - блокирует вход в WebApp-приложение проекта;
    • запись в banusers (user_id, name, username, cause, data) - блокирует
      пользователя во всём проекте (бот + приложение).

  Идемпотентно и устойчиво к ошибкам: каждый шаг изолирован, чтобы сбой одного
  не отменял другой. Возвращает True, если хотя бы один шаг выполнен.
  """
  ok_any = False
  ban_reason_text = (reason or "").strip() or "Полная блокировка"

  # 1) Флаги users.banned / banned_at / banned_reason для WebApp. Столбцы
  #    добавляем мягко (idempotent), если их ещё нет.
  try:
    async with _db_acquire() as conn:
      await _ensure_users_ban_columns(conn)
      await conn.execute(
        """
        UPDATE users
        SET banned        = TRUE,
            banned_at     = NOW(),
            banned_reason = $2
        WHERE user_id = $1
        """,
        target_id, ban_reason_text,
      )
    ok_any = True
    BanDebug.log("FULL", "users.banned set", target=target_id, reason=ban_reason_text[:64])
  except DbUnavailableError as e:
    BanDebug.log("FULL", "users.banned skip - db", err=str(e), target=target_id)
  except Exception as e:
    BanDebug.error("FULL", "users.banned", e, target=target_id)

  # 2) Запись в banusers (полная блокировка во всём проекте). Используем
  #    готовый идемпотентный метод базы (сам ставит дату и пропускает дубли).
  try:
    clean_username = (target_username or "").lstrip("@") or None
    await _db().ban_user(
      target_id,
      clean_username,
      target_name or str(target_id),
      reason or "Полная блокировка",
    )
    ok_any = True
    BanDebug.log("FULL", "banusers record done", target=target_id)
  except Exception as e:
    BanDebug.error("FULL", "banusers record", e, target=target_id)

  return ok_any


async def _is_full_project_blocked(target_id: int) -> bool:
  """True, если нарушитель заблокирован во всём проекте (users.banned или banusers)."""
  # banusers - основной признак (есть готовый метод проверки).
  try:
    if await _db().is_user_banned(target_id):
      return True
  except Exception as e:
    BanDebug.log("FULL", "is_user_banned check skip", err=str(e), target=target_id)
  # users.banned - флаг для WebApp (столбца может не быть).
  try:
    async with _db_acquire() as conn:
      row = await conn.fetchrow(
        "SELECT banned FROM users WHERE user_id = $1", target_id,
      )
    if row and bool(row["banned"]):
      return True
  except Exception as e:
    BanDebug.log("FULL", "users.banned check skip", err=str(e), target=target_id)
  return False


async def _lift_full_project_block(
  target_id: int,
) -> bool:
  """
  Снимает полную блокировку нарушителя во ВСЁМ проекте (обратное к
  _apply_full_project_block):
    • users.banned = FALSE, banned_at = NULL, banned_reason = NULL -
      открывает доступ к WebApp-приложению проекта;
    • удаление из banusers - снимает блокировку во всём проекте.

  Идемпотентно и устойчиво к ошибкам. Возвращает True, если выполнен хотя бы
  один шаг (даже если пользователь и не был заблокирован - это безопасно).
  """
  ok_any = False

  # 1) Снимаем флаги users.banned / banned_at / banned_reason (WebApp).
  #    Столбцы добавляем мягко при отсутствии.
  try:
    async with _db_acquire() as conn:
      await _ensure_users_ban_columns(conn)
      await conn.execute(
        """
        UPDATE users
        SET banned        = FALSE,
            banned_at     = NULL,
            banned_reason = NULL
        WHERE user_id = $1
        """,
        target_id,
      )
    ok_any = True
    BanDebug.log("FULL", "users.banned cleared", target=target_id)
  except DbUnavailableError as e:
    BanDebug.log("FULL", "users.banned clear skip - db", err=str(e), target=target_id)
  except Exception as e:
    BanDebug.error("FULL", "users.banned clear", e, target=target_id)

  # 2) Удаляем из banusers (готовый идемпотентный метод базы).
  try:
    await _db().unban_user(target_id)
    ok_any = True
    BanDebug.log("FULL", "banusers record removed", target=target_id)
  except Exception as e:
    BanDebug.error("FULL", "banusers remove", e, target=target_id)

  return ok_any


async def _notify_ban(
  source_chat_id: int,
  parsed: ParsedBan,
  *,
  acting_admin_id: int,
  acting_admin_name: str,
  acting_admin_role: Optional[str],
  acting_admin_username: Optional[str],
  banned_chat_ids: List[int],
) -> None:
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  staff = StaffRef(
    acting_admin_id, acting_admin_name, acting_admin_role, acting_admin_username,
  )
  reason_line = _format_mute_reason_block(parsed.reason, label="Причина")
  reason_suffix = f"\n{reason_line}" if reason_line else ""
  staff_line = f"{staff.line}\n"
  actor = staff.actor
  forever = _is_forever(parsed)
  term_line = _term_line(parsed)

  if parsed.scope == "all":
    violator_intro = BanText.INTRO_ALL.format(actor=actor, scope=scope_label("all"))
    notify_chats = set(banned_chat_ids) if banned_chat_ids else set(cfg.STAFF_CHAT_IDS)
  else:
    disp = await _get_chat_display(source_chat_id)
    violator_intro = BanText.INTRO_CHAT.format(actor=actor, title=escape(disp.title))
    notify_chats = {source_chat_id}

  # В исходной группе уже показано «Блокировка выполнена» - групповое
  # уведомление туда не дублируем; оно идёт только в ОСТАЛЬНЫЕ группы.
  notify_chats.discard(source_chat_id)

  closing = BanText.CLOSING_FOREVER if forever else BanText.CLOSING_TIMED

  violator_text = BanText.VIOLATOR.format(
    greeting=player.greeting,
    header=_ban_badge(parsed.mode),
    staff_line=staff_line,
    intro=violator_intro,
    term_line=term_line,
    reason_suffix=reason_suffix,
    closing=closing,
  )

  group_title = _ban_badge(parsed.mode)
  if forever:
    group_footer = BanText.GROUP_FOOTER_FOREVER.format(actor=actor, player_short=player.short)
  else:
    group_footer = BanText.GROUP_FOOTER_TIMED.format(
      actor=actor, player_short=player.short, until=_format_until(parsed.ban_until),
    )

  try:
    await _bot().send_message(
      parsed.target_id, violator_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    BanDebug.log("NOTIFY", "violator skip", user_id=parsed.target_id, err=str(e))

  for group_chat_id in notify_chats:
    disp = await _get_chat_display(group_chat_id)
    chat_line = _format_chat_line(disp)
    group_text = BanText.GROUP.format(
      group_title=group_title,
      player_line=player.line,
      staff_line=staff_line,
      chat_line=chat_line,
      term_line=term_line,
      reason_suffix=reason_suffix,
      group_footer=group_footer,
    )
    try:
      await _bot().send_message(
        group_chat_id, group_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      BanDebug.log("NOTIFY", "group skip", chat_id=group_chat_id, err=str(e))


async def _send_success_ban(
  message: Message,
  parsed: ParsedBan,
  chat_id: int,
  banned_count: int,
  banned_ids: List[int],
  errors: List[str],
) -> None:
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  warn = ""
  if banned_count == 0:
    warn = BanText.WARN_NONE
  elif errors:
    warn = BanText.WARN_PARTIAL.format(count=banned_count)
  scope_block = await _format_scope_with_groups(parsed.scope, banned_ids)
  revoke_kb = (
    _ban_revoke_keyboard(message.from_user.id, parsed.target_id, parsed.mode)
    if banned_count > 0 else None
  )
  full_note = BanText.FULL_NOTE if parsed.is_full else ""
  staff = await StaffRef.from_message(message)
  await message.reply(
    BanText.SUCCESS.format(
      player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
      staff_line=staff.line,
      chat_line=chat_line,
      header=_ban_badge(parsed.mode),
      scope_block=scope_block,
      term_line=_term_line(parsed),
      reason_block=_format_mute_reason_block(parsed.reason, label="Причина"),
      full_note=full_note,
      warn=warn,
    ),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=revoke_kb,
  )


async def _finalize_ban(
  message: Message,
  parsed: ParsedBan,
  proof_media_id: str,
  chat_id: int,
  admin_name: str,
) -> bool:
  # Наказание выдаётся СТРОГО после подтверждения пруфа: без фото - не применяем.
  if not proof_media_id:
    await message.reply(
      BanText.PROOF_MISSING + _debug_hint("proof_required"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    BanDebug.log("PROOF", "finalize blocked - no proof", target=getattr(parsed, "target_id", None))
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("ban_invalid_user_finalize"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    BanDebug.log("TG", "ban finalize blocked - invalid user", target=parsed.target_id)
    return True
  _refresh_parsed_ban_expiry(parsed)
  ok, _action_id = await _apply_ban_db(
    target_user_id=parsed.target_id,
    target_name=parsed.target_name,
    target_username=parsed.target_username,
    ban_until=parsed.ban_until,
    admin_user_id=message.from_user.id,
    admin_name=admin_name,
    reason=parsed.reason,
    proof_media_id=proof_media_id,
    duration_minutes=parsed.duration_minutes,
    chat_id=chat_id,
    mode=parsed.mode,
  )
  if not ok:
    await message.reply(
      BanText.DB_ERROR + _debug_hint("ban_db_failed"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  banned_count, banned_ids, errors = await _ban_with_scope(
    parsed.target_id,
    _ban_until_for_telegram(parsed),
    scope=parsed.scope,
    source_chat_id=chat_id,
  )
  if banned_count == 0:
    err_text = errors[0] if errors else "не удалось заблокировать в группе"
    await message.reply(
      BanText.BLOCKED.format(reason=escape(err_text.capitalize()))
      + _debug_hint("ban_tg_failed"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    BanDebug.log(
      "FLOW", "ban aborted - telegram failed",
      target=parsed.target_id, errors=errors,
    )
    return True
  # Режим «фулл»: дополнительно блокируем нарушителя во всём проекте
  # (WebApp users.banned + таблица banusers).
  if parsed.is_full:
    await _apply_full_project_block(
      parsed.target_id, parsed.target_name, parsed.target_username, parsed.reason,
    )
  # Ручная блокировка «забирает» нарушителя у системы варнов: снимаем пометки
  # авто-бана, чтобы истечение варнов не сняло блокировку, выданную вручную.
  try:
    from bot.admins.warn import clear_warn_ban_marks_for_manual_ban
    await clear_warn_ban_marks_for_manual_ban(parsed.target_id)
  except Exception as e:
    BanDebug.log("AUTOBAN", "clear marks skip", err=str(e), target=parsed.target_id)
  admin_name, admin_role, _ = await _resolve_admin_identity(message)
  # Срочные баны кладём в active_bans для авто-разблокировки по истечении срока.
  await _record_active_bans(
    parsed,
    banned_chat_ids=banned_ids,
    admin_user_id=message.from_user.id,
    admin_name=admin_name,
    admin_role=admin_role,
  )
  _ensure_ban_expiry_worker()
  if not _is_forever(parsed):
    try:
      from bot.admins import punish_timers
      punish_timers.register_ban(
        parsed.target_id,
        parsed.ban_until,
        target_name=parsed.target_name,
        target_username=parsed.target_username,
        source_chat_id=chat_id,
        scope=parsed.scope,
      )
    except Exception as e:
      BanDebug.log("TIMER", "register ban skip", err=str(e), user=parsed.target_id)
  await _send_success_ban(message, parsed, chat_id, banned_count, banned_ids, errors)
  await _notify_ban(
    chat_id, parsed,
    acting_admin_id=message.from_user.id,
    acting_admin_name=admin_name,
    acting_admin_role=admin_role,
    acting_admin_username=message.from_user.username,
    banned_chat_ids=banned_ids,
  )
  return True


async def apply_ban_for_warns(
  *,
  target_id: int,
  target_name: str,
  target_username: Optional[str],
  admin_id: int,
  admin_name: str,
  admin_role: Optional[str],
  admin_username: Optional[str],
  proof_media_id: Optional[str],
  source_chat_id: int,
  reason: str,
  mode: Mode = "all",
) -> Tuple[bool, int, List[int]]:
  """
  Программный ПОСТОЯННЫЙ бан по достижении лимита предупреждений (3/3).

  Охват зависит от режима варна, вызвавшего лимит:
    • mode="chat" - бан только в исходной группе («варн»);
    • mode="all"  - бан во всех официальных группах («варналл»);
    • mode="full" - бан во всех группах + полная блокировка в проекте
                    («варнфулл»: WebApp users.banned + таблица banusers).

  Возвращает (ok, banned_count, banned_ids). Итоговое сообщение в исходный чат
  показывает вызывающая сторона - здесь рассылаются только уведомления
  нарушителю и в остальные группы.
  """
  # Защита создателей: их нельзя забанить даже авто-баном по лимиту варнов.
  if is_protected_creator(target_id):
    BanDebug.log("AUTH", "protected creator auto-ban blocked", target=target_id)
    return False, 0, []

  scope = mode_to_scope(mode)
  ban_until = datetime.now() + _FOREVER_DELTA
  parsed = ParsedBan(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    duration_text="навсегда",
    time_delta=_FOREVER_DELTA,
    duration_minutes=_FOREVER_MINUTES,
    ban_until=ban_until,
    reason=reason,
    scope=scope,
    mode=mode,
  )
  ok, _action_id = await _apply_ban_db(
    target_user_id=parsed.target_id,
    target_name=parsed.target_name,
    target_username=parsed.target_username,
    ban_until=parsed.ban_until,
    admin_user_id=admin_id,
    admin_name=admin_name,
    reason=reason,
    proof_media_id=proof_media_id or "",
    duration_minutes=parsed.duration_minutes,
    chat_id=source_chat_id,
    mode=parsed.mode,
  )
  if not ok:
    return False, 0, []

  banned_count, banned_ids, _errors = await _ban_with_scope(
    parsed.target_id,
    _ban_until_for_telegram(parsed),
    scope=scope,
    source_chat_id=source_chat_id,
  )
  # Полная блокировка во всём проекте для режима «варнфулл».
  if parsed.is_full:
    await _apply_full_project_block(
      parsed.target_id, parsed.target_name, parsed.target_username, reason,
    )
  await _record_active_bans(
    parsed,
    banned_chat_ids=banned_ids,
    admin_user_id=admin_id,
    admin_name=admin_name,
    admin_role=admin_role,
  )
  _ensure_ban_expiry_worker()
  await _notify_ban(
    source_chat_id, parsed,
    acting_admin_id=admin_id,
    acting_admin_name=admin_name,
    acting_admin_role=admin_role,
    acting_admin_username=admin_username,
    banned_chat_ids=banned_ids,
  )
  BanDebug.log("WARN-BAN", "applied", target=target_id, banned=banned_ids)
  return True, banned_count, banned_ids


# ---------------------------------------------------------------------------
# Ожидание фото (шаг 2)
# ---------------------------------------------------------------------------

async def _expire_pending_ban(admin_id: int, data: Dict[str, Any]) -> None:
  from bot.admins.punish_proof import coerce_telegram_user_id, safe_edit_message_text
  admin_id = coerce_telegram_user_id(admin_id)
  if admin_id is None or data.get("expiry_notified"):
    return
  data["expiry_notified"] = True

  parsed: ParsedBan = data["parsed"]
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  prompt_chat = data.get("prompt_chat_id")
  prompt_msg_id = data.get("prompt_message_id")
  chat_id = data.get("chat_id", 0)
  disp = await _get_chat_display(chat_id) if chat_id else None
  chat_line = _format_chat_line(disp) if disp else ""
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  final_text = BanText.PENDING_EXPIRED.format(
    player_line=player.line, chat_line=chat_line, reason_part=reason_part,
  )
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
      BanDebug.log("PENDING", "edit expired skip", err=str(e))
  try:
    await _bot().send_message(
      admin_id, final_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    BanDebug.log("PENDING", "notify admin expired skip", admin_id=admin_id, err=str(e))


async def _cleanup_expired_pending_bans_async() -> None:
  from bot.admins.punish_proof import is_proof_expired, pending_items, pending_pop

  now = time.time()
  for uid, data in pending_items(_pending_bans):
    if not is_proof_expired(data.get("expires_at", 0), now=now):
      continue
    pending_pop(_pending_bans, uid)
    BanDebug.log("PENDING", "expired - ban NOT applied", admin_id=uid)
    await _expire_pending_ban(uid, data)


async def _finish_pending_ban_cancel(
  admin_id: int,
  player_line: str,
  chat_id: int,
  parsed: ParsedBan,
) -> bool:
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_bans, admin_id)
  if not pending:
    return False
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  final_text = BanText.PENDING_CANCELLED.format(
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
      return True
    except Exception as e:
      BanDebug.error("FLOW", "edit pending prompt", e, chat=prompt_chat, msg=prompt_msg_id)
  return False


async def _complete_ban_with_proof(message: Message) -> bool:
  from bot.admins.punish_proof import (
    is_proof_expired,
    latest_pending_system_for,
    pending_get,
    pending_pop,
  )

  admin_id = message.from_user.id
  if latest_pending_system_for(admin_id) != "ban":
    return False

  pending = pending_get(_pending_bans, admin_id)
  if not pending:
    BanDebug.log("PROOF", "no pending", admin_id=admin_id)
    return False

  if is_proof_expired(pending.get("expires_at", 0)):
    pending_pop(_pending_bans, admin_id)
    BanDebug.log("PROOF", "late proof ignored - expired", admin_id=admin_id)
    return True

  pending_chat = pending.get("chat_id")
  if not _is_staff_chat(message.chat.id) or message.chat.id != pending_chat:
    staff = await StaffRef.from_message(message)
    parsed: ParsedBan = pending.get("parsed")
    player_line = PlayerRef(
      parsed.target_id, parsed.target_name, parsed.target_username,
    ).line + "\n" if parsed else ""
    pending_disp = await _get_chat_display(pending_chat) if pending_chat else None
    pending_chat_line = (
      _format_chat_line(pending_disp) + "\n" if pending_disp else ""
    )
    await message.reply(
      BanText.WRONG_CHAT.format(
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
      BanText.NEED_PHOTO + _debug_hint("ban_proof_missing"),
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
    debug_tag="ban_invalid_user_proof",
  ):
    pending_pop(_pending_bans, admin_id)
    await clear_pending_prompt_keyboard(pending)
    return True

  BanDebug.log("PROOF", "received", admin_id=admin_id, file_id=proof_media_id[:24])
  await run_finalize_with_pending_fallback(
    message, admin_id, _pending_bans, pending,
    lambda: _finalize_ban(
      message, parsed, proof_media_id,
      pending["chat_id"], pending["admin_name"],
    ),
    on_db_unavailable=lambda: _reply_db_unavailable(message),
  )
  return True


async def _supersede_pending_ban(admin_id: int) -> None:
  """Снимает «зависшее» ожидание фото у этого администратора при начале нового
  действия бана, чтобы случайное фото позже не закрыло его повторно."""
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_bans, admin_id)
  if not pending:
    return
  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        BanText.PENDING_SUPERSEDED,
        chat_id=prompt_chat, message_id=prompt_msg_id,
        parse_mode="HTML", reply_markup=None, link_preview_options=NO_PREVIEW,
      )
    except Exception:
      try:
        await _bot().edit_message_reply_markup(
          chat_id=prompt_chat, message_id=prompt_msg_id, reply_markup=None,
        )
      except Exception as e:
        BanDebug.log("PROOF", "supersede cleanup skip", err=str(e))
  BanDebug.log("PROOF", "superseded by new ban action", admin_id=admin_id)


# ---------------------------------------------------------------------------
# Команда бана
# ---------------------------------------------------------------------------

async def _handle_ban_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  if not await _require_staff_chat(message):
    return True

  command_text = _get_command_text(message)
  # Справку показываем только если одиночное «бан» без ответа на нарушителя.
  # «бан» в ответ на сообщение → бан навсегда (срок не обязателен).
  if (
    _is_ban_command(command_text)
    and len(command_text.split()) == 1
    and not _get_reply_target_message(message)
  ):
    await _send_ban_help(message)
    return True

  result = await parse_ban_command(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    BanDebug.log("PARSE", "error", code=result.code, info=result.debug_info)
    return True

  parsed = result

  if is_protected_creator(parsed.target_id):
    await message.reply(protected_creator_denied_html(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    BanDebug.log("AUTH", "protected creator blocked", target=parsed.target_id)
    return True
  if parsed.target_id == message.from_user.id:
    await message.reply(BanText.SELF, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if parsed.target_id == _bot().id:
    await message.reply(BanText.BOT, parse_mode="HTML", link_preview_options=NO_PREVIEW)
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("ban_invalid_user"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    BanDebug.log("TG", "ban blocked - invalid user", target=parsed.target_id)
    return True

  chat_id = message.chat.id
  block_err = await _validate_ban_before(
    parsed.target_id,
    scope=parsed.scope,
    source_chat_id=chat_id,
  )
  if block_err:
    await message.reply(
      BanText.BLOCKED.format(reason=escape(block_err.capitalize()))
      + _debug_hint("ban_blocked"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  proof_id = _get_proof_file_id(message)
  admin_name, admin_role, _ = await _resolve_admin_identity(message)

  # Новое действие бана отменяет прежнее «зависшее» ожидание этого админа.
  await _supersede_pending_ban(message.from_user.id)

  if proof_id:
    BanDebug.log("FLOW", "one-step ban with photo", proof=proof_id[:24])
    await _finalize_ban(message, parsed, proof_id, chat_id, admin_name)
    return True

  admin_id = message.from_user.id
  from bot.admins.punish_proof import (
    clear_other_pending_proofs,
    new_pending_record,
    pending_get,
    pending_set,
  )
  ensure_proof_pending_worker()
  clear_other_pending_proofs(admin_id, keep="ban")
  pending_set(_pending_bans, admin_id, new_pending_record(
    parsed=parsed,
    chat_id=chat_id,
    admin_name=admin_name,
    admin_role=admin_role,
  ))
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  cancel_hint = _suggest_cancel_ban_command(
    parsed.target_id, parsed.target_name, parsed.target_username,
  )
  sent = await message.reply(
    _build_pending_ban_proof_text(parsed, chat_line, cancel_hint)
    + _debug_hint("awaiting_ban_proof"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_ban_pending_cancel_keyboard(admin_id, parsed.target_id),
  )
  pending = pending_get(_pending_bans, admin_id)
  if pending is not None:
    pending["prompt_chat_id"] = sent.chat.id
    pending["prompt_message_id"] = sent.message_id
  BanDebug.log(
    "FLOW", "pending proof",
    admin_id=admin_id, target=parsed.target_id, message_id=sent.message_id,
  )
  return True


# ---------------------------------------------------------------------------
# Отмена ожидания
# ---------------------------------------------------------------------------

async def _resolve_cancel_ban_target(message: Message) -> ParsedBan | ParseError:
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return ParsedBan(
      target_id=u.id,
      target_name=u.full_name or u.first_name or str(u.id),
      target_username=u.username,
      duration_text="",
      time_delta=timedelta(),
      duration_minutes=0,
      ban_until=datetime.now(),
      reason="",
    )

  body = _strip_cancel_ban_prefix(_get_command_text(message))
  if not body:
    return ParseError(
      "cancel_ban_no_target",
      BanText.CANCEL_NO_TARGET,
      "",
    )

  target_id, target_name, target_username = await _resolve_target_from_body(message, body)
  if not target_id:
    return ParseError(
      "cancel_ban_not_found",
      _target_lookup_error_message(body, target_username=target_username),
      body,
    )

  return ParsedBan(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    duration_text="",
    time_delta=timedelta(),
    duration_minutes=0,
    ban_until=datetime.now(),
    reason="",
  )


async def _handle_cancel_ban_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _require_staff_chat(message):
    return True

  result = await _resolve_cancel_ban_target(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  target = result
  admin_id = message.from_user.id
  staff = await StaffRef.from_message(message)
  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_bans, admin_id)
  player = PlayerRef(target.target_id, target.target_name, target.target_username)

  if not pending:
    await message.reply(
      BanText.NO_PENDING.format(greeting=staff.greeting, player_line=player.line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  if pending["parsed"].target_id != target.target_id:
    pending_player = PlayerRef(
      pending["parsed"].target_id,
      pending["parsed"].target_name,
      pending["parsed"].target_username,
    )
    cancel_hint = escape(_suggest_cancel_ban_command(
      pending["parsed"].target_id, pending["parsed"].target_name, pending["parsed"].target_username,
    ))
    await message.reply(
      BanText.OTHER_PENDING.format(
        greeting=staff.greeting,
        pending_player_line=pending_player.line,
        cancel_hint=cancel_hint,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  chat_id = pending.get("chat_id", message.chat.id)
  edited = await _finish_pending_ban_cancel(
    admin_id, player.line, chat_id, pending["parsed"],
  )
  if not edited:
    disp = await _get_chat_display(chat_id)
    chat_line = _format_chat_line(disp)
    await message.reply(
      BanText.CANCEL_FALLBACK.format(player_line=player.line, chat_line=chat_line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  BanDebug.log("FLOW", "pending cancelled", admin_id=admin_id, target=target.target_id)
  return True


# ---------------------------------------------------------------------------
# Разбан - ручное снятие блокировки
# ---------------------------------------------------------------------------

async def _resolve_unban_target(
  message: Message,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
  """Цель разбана: ответ на сообщение либо токен после команды (@user, id, имя)."""
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return u.id, u.full_name or u.first_name or str(u.id), u.username
  body = _strip_unban_prefix(_get_command_text(message))
  return await _resolve_target_from_body(message, body)


def _unban_target_error_message(body: str, target_username: Optional[str]) -> str:
  token = (body.split()[0] if body else "").strip()
  if target_username or token.startswith("@") or _looks_like_username_token(token):
    username = (target_username or token).lstrip("@")
    return BanText.UNBAN_NOT_FOUND_USERNAME.format(username=escape(username))
  if token.isdigit():
    return BanText.UNBAN_NOT_FOUND_ID.format(token=escape(token))
  if token:
    return BanText.UNBAN_NOT_FOUND_NAME.format(body=escape(body))
  return BanText.UNBAN_NO_TARGET


async def _delete_all_active_bans(user_id: int) -> None:
  try:
    async with _db_acquire() as conn:
      await conn.execute("DELETE FROM active_bans WHERE user_id = $1", user_id)
  except Exception as e:
    BanDebug.log("DB", "delete all active bans skip", err=str(e), user=user_id)


async def _lift_ban_everywhere(target_id: int) -> Tuple[bool, List[int]]:
  """
  Снимает блокировку во всех официальных группах, ориентируясь на сам Telegram:
  фактический статус участника (kicked) определяет, где он реально забанен.

  Возвращает (был_ли_забанен_где-либо, список_чатов_где_сняли).
  """
  was_banned = False
  lifted: List[int] = []
  for cid in cfg.STAFF_CHAT_IDS:
    if cid > 0:
      continue
    status = None
    try:
      member = await _bot().get_chat_member(cid, target_id)
      status = getattr(member, "status", None)
    except Exception as e:
      BanDebug.log("TG", "unban status skip", chat_id=cid, err=str(e))
    status_val = status.value if hasattr(status, "value") else status
    if status_val == "kicked":
      was_banned = True
      if await _unban_in_chat(cid, target_id):
        lifted.append(cid)
    else:
      # Идемпотентно снимаем на случай рассинхрона; «был забанен» не помечаем.
      await _unban_in_chat(cid, target_id)
  return was_banned, lifted


async def _log_unban_db(
  target_user_id: int,
  target_name: str,
  target_username: Optional[str],
  admin_user_id: int,
  admin_name: str,
  reason: str,
  chat_id: int,
  mode: Mode = "chat",
) -> bool:
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
        await conn.execute(
          """
          INSERT INTO staff_actions (
            admin_user_id, admin_name, action_type,
            target_player_id, target_name, reason, chat_id, scope
          )
          VALUES ($1, $2, 'unban', $3, $4, $5, $6, $7)
          """,
          admin_user_id, admin_name, target_user_id, target_name, reason, chat_id, mode,
        )
    BanDebug.log("DB", "unban saved", target=target_user_id, chat_id=chat_id)
    return True
  except DbUnavailableError as e:
    BanDebug.log("DB", "log_unban skipped", err=str(e), target=target_user_id)
    return False
  except Exception as e:
    BanDebug.error("DB", "log_unban", e, target=target_user_id)
    return False


async def _log_auto_unban_db(
  target_user_id: int,
  target_name: str,
  chat_id: int,
  scope: Mode = "chat",
) -> None:
  """Аудит авто-разблокировки (истёк срок бана) в staff_actions.

  Симметрично `_log_auto_unmute_db`: пишем от «Системы» (admin_user_id=0), чтобы
  в архиве админ-панели было видно и автоматическое снятие блокировки с охватом.
  """
  try:
    async with _db_acquire() as conn:
      await conn.execute(
        """
        INSERT INTO staff_actions (
          admin_user_id, admin_name, action_type,
          target_player_id, target_name, reason, chat_id, scope
        )
        VALUES (0, 'Система', 'unban', $1, $2, 'Срок блокировки истёк', $3, $4)
        """,
        target_user_id, target_name, chat_id, scope,
      )
  except DbUnavailableError as e:
    BanDebug.log("DB", "auto_unban log skipped", err=str(e), target=target_user_id)
  except Exception as e:
    BanDebug.error("DB", "auto_unban log", e, target=target_user_id)


async def _format_unbanned_groups(chat_ids: List[int]) -> str:
  """Список групп, где блокировка снята (кликабельно, без превью-карточки)."""
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


async def _notify_unban(
  source_chat_id: int,
  player: PlayerRef,
  staff: StaffRef,
  lifted_chat_ids: List[int],
  *,
  broadcast_groups: bool = True,
) -> None:
  actor = staff.actor

  links: List[InlineKeyboardButton] = []
  for cid in lifted_chat_ids:
    disp = await _get_chat_display(cid)
    if disp.link_url:
      links.append(InlineKeyboardButton(text=BanText.BTN_RETURN.format(title=disp.title), url=disp.link_url))
      if len(links) >= 3:
        break
  dm_text = BanText.UNBAN_DM.format(
    greeting=player.greeting, staff_line=staff.line, actor=actor,
  )
  try:
    kb = InlineKeyboardMarkup(inline_keyboard=[[b] for b in links]) if links else None
    await _bot().send_message(
      player.user_id, dm_text, parse_mode="HTML", reply_markup=kb, link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    BanDebug.log("NOTIFY", "unban dm skip", user_id=player.user_id, err=str(e))

  # В исходной группе уже показан ответ «🔓 Разблокировка выполнена» - туда
  # групповое уведомление не дублируем; оно идёт только в ОСТАЛЬНЫЕ группы.
  # При снятии через кнопку (broadcast_groups=False) групповые сообщения не шлём.
  if not broadcast_groups:
    return
  notify_chats = set(lifted_chat_ids)
  notify_chats.discard(source_chat_id)
  group_title = BanText.UNBAN_GROUP_TITLE
  for cid in notify_chats:
    chat_line = await _format_chats_line(list(lifted_chat_ids), current_chat_id=cid)
    text = BanText.UNBAN_GROUP.format(
      group_title=group_title,
      player_line=player.line,
      staff_line=staff.line,
      chat_line=chat_line,
      actor=actor,
      player_short=player.short,
    )
    try:
      await _bot().send_message(
        cid, text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      BanDebug.log("NOTIFY", "unban group skip", chat_id=cid, err=str(e))


async def _execute_unban_core(
  *,
  chat_id: int,
  actor_id: int,
  admin_name: str,
  staff: StaffRef,
  target_id: int,
  target_name: str,
  target_username: Optional[str],
  reply: Callable[[str], Awaitable[Any]],
  mode: Mode = "full",
  broadcast_groups: bool = True,
  announce_result: bool = True,
) -> str:
  """Ядро снятия бана. Возвращает 'revoked' | 'not_banned' | 'forbidden_self'.

  Не зависит от способа вызова (команда или кнопка).

  Охват снятия (mode):
    • chat - снять блокировку только в текущей группе (chat_id);
    • all  - снять во всех официальных группах проекта;
    • full - снять во всех группах + полную блокировку проекта (WebApp + banusers).

  broadcast_groups=False - не рассылать групповые уведомления;
  announce_result=False - не отправлять текстовый ответ-результат (для снятия
  через кнопку, когда исходное сообщение редактируется на месте).
  """
  # Защита «в глубину»: снять бан с самого себя нельзя даже сотруднику с правами.
  if actor_id == target_id:
    if announce_result:
      await reply(self_revoke_denied_html() + _debug_hint("self_revoke"))
    BanDebug.log("AUTH", "self revoke blocked", actor=actor_id, target=target_id)
    return "forbidden_self"

  was_banned = False
  lifted: List[int] = []
  full_blocked = False

  if mode == "chat":
    # Снимаем блокировку ТОЛЬКО в текущей группе.
    if _is_staff_chat(chat_id):
      status_val = None
      try:
        member = await _bot().get_chat_member(chat_id, target_id)
        status = getattr(member, "status", None)
        status_val = status.value if hasattr(status, "value") else status
      except Exception as e:
        BanDebug.log("TG", "unban status skip", chat_id=chat_id, err=str(e))
      if status_val == "kicked":
        was_banned = True
      ok = await _unban_in_chat(chat_id, target_id)
      if was_banned and ok:
        lifted.append(chat_id)
      await _delete_active_ban(target_id, chat_id)
  else:
    # all / full - снимаем во всех официальных группах.
    was_banned, lifted = await _lift_ban_everywhere(target_id)
    await _delete_all_active_bans(target_id)
    if mode == "full":
      # Полную блокировку проекта (WebApp + banusers) учитываем как «бан»,
      # чтобы разбанфулл корректно снимал банфулл/варнфулл целиком.
      full_blocked = await _is_full_project_blocked(target_id)
      await _lift_full_project_block(target_id)

  BanDebug.log(
    "FLOW", "unban scope", target=target_id, mode=mode,
    was_banned=was_banned, lifted=lifted, full=full_blocked,
  )

  # Дополним username из БД, если в команде его не было (для красивой подписи).
  if not target_username:
    try:
      async with _db_acquire() as conn:
        row = await conn.fetchrow(
          "SELECT username FROM users WHERE user_id = $1", target_id,
        )
      if row and row["username"]:
        target_username = row["username"]
    except Exception:
      pass
  player = PlayerRef(target_id, target_name, target_username)

  if not was_banned and not lifted and not full_blocked:
    if announce_result:
      await reply(
        BanText.NOT_BANNED.format(
          player_short=player.short, staff_line=staff.line, player_line=player.line,
        )
        + _debug_hint("not_banned")
      )
    return "not_banned"

  await _log_unban_db(
    target_id, target_name, target_username,
    actor_id, admin_name,
    f"Разбан - {admin_name}", chat_id,
    mode=mode,
  )
  await _notify_unban(chat_id, player, staff, lifted, broadcast_groups=broadcast_groups)

  if announce_result:
    groups_block = await _format_unbanned_groups(lifted)
    groups_part = f"\n{groups_block}" if groups_block else ""
    await reply(
      BanText.UNBAN_SUCCESS.format(
        staff_line=staff.line, player_line=player.line, groups_part=groups_part,
      )
      + _debug_hint("unban_ok")
    )
  BanDebug.log("FLOW", "unban done", target=target_id, lifted=lifted)
  try:
    from bot.admins import punish_timers
    punish_timers.cancel_ban(target_id)
  except Exception:
    pass
  # Ручное снятие блокировки - снимаем и пометки авто-бана по варнам, чтобы
  # последующее истечение варнов не делало повторное (лишнее) снятие.
  try:
    from bot.admins.warn import clear_warn_ban_marks_for_manual_ban
    await clear_warn_ban_marks_for_manual_ban(target_id)
  except Exception:
    pass
  return "revoked"


async def _execute_unban(
  message: Message,
  target_id: int,
  target_name: str,
  target_username: Optional[str],
  mode: Mode = "full",
) -> bool:
  """Снимает блокировку нарушителя и уведомляет участников (вызов из команды)."""
  admin_name, admin_role, admin_account = await _resolve_admin_identity(message)
  staff = (
    StaffRef.from_account(admin_account)
    if admin_account else
    await StaffRef.from_message(message)
  )

  async def _reply(text: str) -> None:
    await message.reply(text, parse_mode="HTML", link_preview_options=NO_PREVIEW)

  await _execute_unban_core(
    chat_id=message.chat.id,
    actor_id=message.from_user.id,
    admin_name=admin_name,
    staff=staff,
    target_id=target_id,
    target_name=target_name,
    target_username=target_username,
    reply=_reply,
    mode=mode,
  )
  return True


async def _handle_unban_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if not await _require_staff_chat(message):
    return True

  body = _strip_unban_prefix(_get_command_text(message))
  target_id, target_name, target_username = await _resolve_unban_target(message)
  if not target_id:
    await message.reply(
      _unban_target_error_message(body, target_username) + _debug_hint("unban_no_target"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True
  if target_id == _bot().id:
    await message.reply(BanText.UNBAN_BOT, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  mode = _unban_command_mode(_get_command_text(message))
  return await _execute_unban(
    message, target_id, target_name or str(target_id), target_username, mode=mode,
  )


# ---------------------------------------------------------------------------
# Основной обработчик
# ---------------------------------------------------------------------------

async def _maybe_ban_maintenance() -> None:
  """Ожидание фото обрабатывает proof worker."""
  return


async def ban_process(message: Message) -> bool:
  """Обрабатывает сообщения системы бана. True = перехвачено."""
  if not message.from_user:
    return False

  from bot.admins.punish_proof import (
    is_proof_only_photo,
    pending_contains,
    pending_get,
  )

  chat_id = message.chat.id
  uid = message.from_user.id
  pending = pending_contains(_pending_bans, uid)

  if not pending and chat_id > 0:
    return False
  if not pending and chat_id < 0 and not _is_staff_chat(chat_id):
    if not _is_ban_related_message(message):
      return False

  await _ensure_mute_schema()

  command_text = _get_command_text(message)
  BanDebug.log(
    "IN", "message",
    uid=uid, chat=chat_id,
    text=command_text[:80] if command_text else "",
    photo=bool(message.photo), reply=bool(message.reply_to_message),
    pending=pending,
  )

  if pending:
    if is_proof_only_photo(message):
      return await _complete_ban_with_proof(message)

    if not command_text:
      BanDebug.log("PROOF", "ignored non-photo while pending", uid=uid)
      return True

    low = command_text.lower().strip()
    if low in ("отмена", "cancel", "/cancel"):
      if not pending_contains(_pending_bans, uid):
        return False
      perm = await check_staff_permission(uid, "ban")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        await _send_no_permission(message, "ban")
        return True
      if not _is_staff_chat(message.chat.id):
        return False
      pending_data = pending_get(_pending_bans, uid)
      if not pending_data:
        return False
      p: ParsedBan = pending_data["parsed"]
      hint = _suggest_cancel_ban_command(p.target_id, p.target_name, p.target_username)
      staff = await StaffRef.from_message(message)
      player = PlayerRef(p.target_id, p.target_name, p.target_username)
      await message.reply(
        BanText.CANCEL_HELP.format(
          greeting=staff.greeting,
          staff_line=staff.line,
          player_line=player.line,
          cancel_hint=escape(hint),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      return True

    if _is_cancel_ban_command(command_text):
      perm = await check_staff_permission(uid, "ban")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "cancel_ban")
      return await _handle_cancel_ban_command(message)

    if _is_ban_command(command_text):
      ban_action = _ban_permission_action(command_text)
      perm = await check_staff_permission(uid, ban_action)
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, ban_action)
      return await _handle_ban_command(message)

    BanDebug.log("PROOF", "ignored text while pending", uid=uid, text=command_text[:60])
    return True

  if is_proof_only_photo(message) and _is_ban_related_message(message):
    ban_action = _ban_permission_action(command_text)
    perm = await check_staff_permission(uid, ban_action)
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, ban_action)
    return await _handle_ban_command(message)

  if not command_text:
    return False

  low = command_text.lower().strip()
  if low in ("отмена", "cancel", "/cancel"):
    return False

  if _is_cancel_ban_command(command_text):
    perm = await check_staff_permission(message.from_user.id, "ban")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "cancel_ban")
    return await _handle_cancel_ban_command(message)

  if _is_unban_command(command_text):
    # Право проверяем по охвату снятия: разбан→ban, разбаналл→banall,
    # разбанфулл→banfull (та же иерархия прав, что и при бане).
    unban_mode = _unban_command_mode(command_text)
    unban_action = _unban_permission_action(command_text)
    BanDebug.log(
      "UNBAN", "command recognised",
      uid=uid, mode=unban_mode, action=unban_action,
      text=command_text[:60],
    )
    perm = await check_staff_permission(message.from_user.id, unban_action)
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      BanDebug.log("UNBAN", "denied", uid=uid, action=unban_action, perm=perm)
      return await deny_permission(message, _unban_deny_action(command_text))
    # Любой сбой в снятии блокировки должен дать видимый ответ сотруднику,
    # а не «тихо» проглотиться (main.py запускает обработчик как fire-and-forget).
    try:
      return await _handle_unban_command(message)
    except DbUnavailableError:
      await _reply_db_unavailable(message)
      return True
    except Exception as e:
      BanDebug.error("UNBAN", "handler crash", e, uid=uid, mode=unban_mode)
      try:
        await message.reply(
          _generic_handler_error_message() + _debug_hint("unban_crash"),
          parse_mode="HTML", link_preview_options=NO_PREVIEW,
        )
      except Exception:
        pass
      return True

  if not _is_ban_command(command_text):
    return False

  # Право проверяем по конкретному режиму: ban / banall / banfull.
  ban_action = _ban_permission_action(command_text)
  perm = await check_staff_permission(message.from_user.id, ban_action)
  if perm == "db_unavailable":
    await _reply_db_unavailable(message)
    return True
  if perm != "allowed":
    return await deny_permission(message, ban_action)

  return await _handle_ban_command(message)


@ban_router.callback_query(F.data.startswith("ban:cancel:"))
async def on_ban_pending_cancel(callback: CallbackQuery) -> None:
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) != 4:
    await callback.answer(BanText.CB_BAD_DATA, show_alert=True)
    return

  admin_id = int(parts[2])
  target_id = int(parts[3])

  if callback.from_user.id != admin_id:
    await callback.answer(BanText.CB_ONLY_AUTHOR, show_alert=True)
    return

  perm = await check_staff_permission(admin_id, "ban")
  if perm != "allowed":
    if perm == "db_unavailable":
      await callback.answer(BanText.CB_DB, show_alert=True)
    else:
      await callback.answer(BanText.CB_NO_PERM, show_alert=True)
    return

  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_bans, admin_id)
  if not pending:
    try:
      await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
      pass
    await callback.answer(BanText.CB_DONE, show_alert=True)
    return

  if pending["parsed"].target_id != target_id:
    await callback.answer(BanText.CB_STALE, show_alert=True)
    return

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(BanText.CB_WRONG_CHAT, show_alert=True)
    return

  parsed: ParsedBan = pending["parsed"]
  player_line = PlayerRef(
    target_id, parsed.target_name, parsed.target_username,
  ).line
  chat_id = pending.get("chat_id", callback.message.chat.id)
  await _finish_pending_ban_cancel(admin_id, player_line, chat_id, parsed)
  await callback.answer(BanText.CB_CANCELLED)
  BanDebug.log("FLOW", "pending cancelled via button", admin_id=admin_id, target=target_id)


@ban_router.callback_query(F.data.startswith("ban:revoke:"))
async def on_ban_revoke(callback: CallbackQuery) -> None:
  """Снятие бана по кнопке под сообщением «Блокировка выполнена».

  Нажать может любой сотрудник с правом на бан/разбан.
  """
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  # Формат: ban:revoke:{admin_id}:{target_id}[:{mode}]. mode - необязателен
  # (старые сообщения без него считаем полным снятием для обратной совместимости).
  parts = (callback.data or "").split(":")
  if len(parts) not in (4, 5):
    await callback.answer(BanText.CB_BAD_DATA, show_alert=True)
    return
  try:
    target_id = int(parts[3])
  except ValueError:
    await callback.answer(BanText.CB_BAD_DATA, show_alert=True)
    return
  mode: Mode = parts[4] if len(parts) == 5 and parts[4] in ("chat", "all", "full") else "full"

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(BanText.CB_WRONG_CHAT, show_alert=True)
    return

  clicker = callback.from_user.id
  # Право проверяем по охвату снятия: ban / banall / banfull.
  revoke_action = _BAN_MODE_PERMISSION.get(mode, "ban")
  perm = await check_staff_permission(clicker, revoke_action)
  if perm != "allowed":
    await callback.answer(
      BanText.CB_DB if perm == "db_unavailable" else BanText.CB_NO_PERM,
      show_alert=True,
    )
    return

  staff = await StaffRef.from_user_id(clicker)
  target_name, target_username = await _resolve_user_display(target_id)
  chat_id = callback.message.chat.id

  async def _noop(_text: str) -> None:
    return None

  status = await _execute_unban_core(
    chat_id=chat_id,
    actor_id=clicker,
    admin_name=staff.name,
    staff=staff,
    target_id=target_id,
    target_name=target_name,
    target_username=target_username,
    reply=_noop,
    mode=mode,
    broadcast_groups=False,
    announce_result=False,
  )

  if status == "revoked":
    player = PlayerRef(target_id, target_name, target_username)
    disp = await _get_chat_display(chat_id)
    new_text = BanText.REVOKED_EDIT.format(
      player_line=player.line,
      chat_line=_format_chat_line(disp),
      staff_line=f"{staff.line}\n",
      player_short=player.short,
    )
    await _edit_revoked_message(callback.message, new_text)
    await callback.answer(BanText.CB_REVOKED)
  elif status == "not_banned":
    await _edit_remove_keyboard(callback.message)
    await callback.answer(BanText.CB_NOT_BANNED, show_alert=True)
  elif status == "forbidden_self":
    await callback.answer(BanText.CB_SELF_REVOKE, show_alert=True)
  else:
    await callback.answer(BanText.CB_REVOKE_FAILED, show_alert=True)
  BanDebug.log("FLOW", "ban revoked via button", actor=clicker, target=target_id, status=status)


# ---------------------------------------------------------------------------
# Middleware - перехват сообщений системы бана
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 🛡️ Барьер полной блокировки: заблокированный во всём проекте НЕ пользуется ботом
# ---------------------------------------------------------------------------
# Проверяется КАЖДОЕ входящее сообщение, но это почти бесплатно: db.is_user_banned()
# держит ответ в памяти 60 секунд, поэтому БД трогается не чаще раза в минуту на
# пользователя. Нет блокировки - сообщение идёт дальше без задержек. Есть -
# обработка мгновенно останавливается (return None: ни один handler не сработает),
# а пользователю (с антиспам-троттлингом) показывается его наказание.
#
# ВАЖНО: это единый барьер для warnfull 3/3 И ручной блокировки (blockchat.py) -
# оба вида пишут пользователя в таблицу banusers, которую и проверяет is_user_banned.

# user_id → monotonic-время последнего показанного уведомления о блокировке.
# Обычный dict (не персистентный): троттлинг живёт в пределах одного запуска, а
# time.monotonic() и не переживает рестарт - так нет ложных «тихих» окон.
_block_notice_at: Dict[int, float] = {}
# Как часто напоминать заблокированному о блокировке (антиспам, секунды).
_BLOCK_NOTICE_COOLDOWN_SEC: float = 30.0


async def _blocked_notice_text(user) -> str:
  """Баннер блокировки + обзор варнов пользователя (если варны есть)."""
  parts = [BanText.PROJECT_BLOCK_TITLE, BanText.PROJECT_BLOCK_INTRO]
  try:
    from bot.admins.warn import build_block_warn_overview
    overview = await build_block_warn_overview(
      user.id,
      name=getattr(user, "full_name", None),
      username=getattr(user, "username", None),
    )
  except Exception as e:
    overview = ""
    BanDebug.log("GUARD", "overview skip", err=str(e), user=getattr(user, "id", None))
  if overview:
    parts.append(overview)
  return "\n".join(parts)


async def _notify_blocked_throttled(message: Message, uid: int) -> None:
  """Показывает наказание заблокированному, но не чаще одного раза в cooldown."""
  now = time.monotonic()
  last = _block_notice_at.get(uid)
  if last is not None and (now - last) < _BLOCK_NOTICE_COOLDOWN_SEC:
    return
  _block_notice_at[uid] = now
  try:
    text = await _blocked_notice_text(message.from_user)
    await message.reply(text, parse_mode="HTML", link_preview_options=NO_PREVIEW)
  except Exception as e:
    BanDebug.log("GUARD", "notify skip", err=str(e), user=uid)


class ProjectBlockGuardMiddleware(BaseMiddleware):
  """Внешний барьер: не пускает заблокированного во всём проекте дальше по цепочке.

  Навешивается как outer-middleware на сообщения, поэтому срабатывает РАНЬШЕ любых
  фильтров и хендлеров - и на команды, и на игры, и на обычный текст. Проверка
  дешёвая (кэш в БД-слое), так что скорость бота не страдает.
  """
  async def __call__(
    self,
    handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: Dict[str, Any],
  ) -> Any:
    if not isinstance(event, Message) or not event.from_user:
      return await handler(event, data)
    user = event.from_user
    uid = user.id
    # Никогда не трогаем ботов и защищённых создателей проекта (антисамолок).
    if user.is_bot or is_protected_creator(uid):
      return await handler(event, data)
    # Быстрая проверка: ответ кэшируется в БД-слое на 60 секунд.
    try:
      blocked = await _db().is_user_banned(uid)
    except Exception as e:
      BanDebug.log("GUARD", "is_user_banned skip", err=str(e), user=uid)
      blocked = False
    if not blocked:
      return await handler(event, data)
    # Заблокирован во всём проекте - обработку останавливаем и показываем причину.
    await _notify_blocked_throttled(event, uid)
    BanDebug.log("GUARD", "message blocked", user=uid, chat=getattr(event.chat, "id", None))
    return None


class BanMiddleware(BaseMiddleware):
  """
  Фоновая поддержка системы бана:
    • шаг 2 - фото-пруф / отмена при активном ожидании (pending);
    • одношаговый бан с фото-пруфом и подписью-командой (медиа main.py не ловит).

  Текстовые команды бана (без фото) приходят из main.py по паттерну игровых
  команд - здесь они НЕ перехватываются, чтобы не было двойной обработки.
  """
  async def __call__(self, handler, event: TelegramObject, data: dict):
    if not isinstance(event, Message) or not event.from_user:
      return await handler(event, data)

    # Гарантируем запуск фонового воркера авто-разблокировки (есть event loop).
    _ensure_ban_expiry_worker()

    msg: Message = event
    uid = msg.from_user.id
    from bot.admins.punish_proof import pending_contains
    pending = pending_contains(_pending_bans, uid)
    staff_group = msg.chat.id < 0 and _is_staff_chat(msg.chat.id)

    media_command = (
      not pending
      and staff_group
      and _has_proof_media(msg)
      and _is_ban_related_message(msg)
    )

    if not pending and not media_command:
      return await handler(event, data)

    try:
      if await ban_process(msg):
        BanDebug.log("MW", "handled ban", msg_id=msg.message_id, pending=pending)
        return None
    except Exception as e:
      BanDebug.error("MW", "ban_process crash", e, msg_id=getattr(msg, "message_id", None))
      try:
        await msg.reply(_generic_handler_error_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
      except Exception:
        pass
    return await handler(event, data)


# ---------------------------------------------------------------------------
# Роутер (запасной канал)
# ---------------------------------------------------------------------------

@ban_router.message(F.photo)
async def ban_on_photo(message: Message) -> None:
  if _is_ban_related_message(message):
    await ban_process(message)


async def ban(message: Message) -> None:
  await ban_process(message)


def attach_ban_system(dp) -> None:
  global _ban_system_attached
  if _ban_system_attached:
    BanDebug.log("WIRE", "already attached")
    return
  try:
    # Барьер полной блокировки ставим ПЕРВЫМ (outer): заблокированный во всём
    # проекте пользователь не должен доходить ни до одного хендлера бота.
    dp.message.outer_middleware(ProjectBlockGuardMiddleware())
    dp.message.middleware(BanMiddleware())
    dp.include_router(ban_router)
    _ban_system_attached = True
    ensure_proof_pending_worker()
    BanDebug.log("WIRE", "attached guard + middleware + router", log_file=BAN_LOG_FILE)
    print(f"[BAN] ✅ Система бана подключена → лог: {BAN_LOG_FILE}")
  except Exception as e:
    BanDebug.error("WIRE", "attach failed", e)
    print(f"[BAN][WIRE][ERROR] {e}")
