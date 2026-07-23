# -*- coding: utf-8 -*-
"""
Система кика нарушителей из официальных групп проекта.

Подключение (main.py):
    from bot.admins.kick import attach_kick_system
    attach_kick_system(dp)

Форматы:
    • Ответ + фото + подпись:  кик причина
    • Без ответа + фото:       кик @user причина
                               кик username причина
                               кик 123456789 причина
    • Охват: кик - только эта группа; кикалл / киквсе - все официальные группы
    • Два шага: текст → фото (в течение 5 мин)
    • Отмена: отменить кик @user

proof_media_id → staff_actions (action_type = 'kick')

Права:
    admin_accounts - должность (role)
    staff_rules    - столбец kick (1/0)
"""
from __future__ import annotations

import os
import re
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional, Tuple

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
  _format_chat_line,
  _format_mute_reason_block,
  _format_player_line,
  _format_scope_block,
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
  _send_no_permission,
  deny_permission,
  _service_unavailable_message,
  _generic_handler_error_message,
  _target_lookup_error_message,
  _db_acquire,
  _reply_db_unavailable,
  _format_scope_with_groups,
  _resolve_reply_or_explicit,
  check_staff_permission,
  DbUnavailableError,
  NO_PREVIEW,
  cfg,
  parse_command_scope,
  scope_label,
  is_protected_creator,
  protected_creator_denied_html,
)

kick_router = Router(name="staff_kick")

# --- Команды ---
KICK_COMMANDS: frozenset = frozenset({
  "кик", "/kick", "kick", "кикнуть", "/кик", "выгнать", "выкинуть",
})
_KICK_CMD_ROOTS: Tuple[str, ...] = ("кик", "kick", "кикнуть", "выгнать", "выкинуть")

_CANCEL_KICK_RE = re.compile(r"^(?:отмена|отменить)\s+(?:кик|кика)\b", re.IGNORECASE)

KICK_LOG_FILE = os.path.join(
  os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
  "log_kick.txt",
)

_pending_kicks: Dict[int, Dict[str, Any]] = LazyGameStore("_pending_kicks")
_kick_system_attached = False
_kick_maintenance_last = 0.0
_KICK_MAINTENANCE_INTERVAL_SEC = 5.0


# =============================================================================
#  📝 ТЕКСТЫ СИСТЕМЫ КИКА - меняйте текст и эмодзи ПРЯМО ЗДЕСЬ
# -----------------------------------------------------------------------------
#  Всё, что видит администратор/нарушитель в системе кика, собрано тут.
#  • Чтобы поменять текст - правьте строки.
#  • Чтобы поменять эмодзи - меняйте эмодзи прямо в строках.
#  • {фигурные_скобки} - это автоподстановка (имя, причина, группа и т.п.).
# =============================================================================

class KickText:
  # --- Справка ---
  HELP = (
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Справка об исключении из групп</b>\n\n"
    "<b>Фото обязательно</b> - в подписи к команде или отдельным сообщением "
    "(до {timeout} мин.).\n\n"
    "<i>Текст после указания нарушителя считается причиной.</i>\n"
    "· ответ на сообщение + <code>кик причина</code>\n"
    "· <code>кик @user причина</code> · <code>кик username причина</code>\n\n"
    "<b>Охват:</b>\n"
    "· <code>кик</code> - только <i>эта</i> группа\n"
    "· <code>кикалл</code> · <code>киквсе</code> - <i>все</i> официальные группы\n\n"
    "<b>Отмена ожидания:</b>\n"
    "<code>отменить кик @user</code>"
  )

  # --- Ошибки разбора цели ---
  NOT_FOUND_EXPLICIT = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>{token}</code> не найден</b>\n"
    "<blockquote><i>Проверьте @username/ID или ответьте на сообщение без указания пользователя.</i></blockquote>"
  )
  NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Кого исключить?</b>\n"
    "<b>Ответьте на сообщение нарушителя или напишите :</b> "
    "<code>кик [username, id, имя] [причина]</code>"
  )
  NOT_FOUND_USERNAME = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    "Пользователь <code>@{username}</code> не найден</b>"
  )
  NOT_FOUND_ID = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> ID <code>{token}</code> не найден</b>"
  NOT_FOUND_NAME = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> «{token}» не найден</b>"

  # --- Ожидание фото (шаг 2) ---
  PENDING = (
    "{header} <b>· ждём фото</b>\n"
    "{player_line}\n"
    "{reason_part}"
    "<blockquote><i><b>Фото в этот чат за {timeout} мин.</b> · отмена - кнопкой ниже</i></blockquote>"
  )

  # --- Уведомление нарушителя в ЛС ---
  INTRO_ALL = "{actor} исключил вас {scope}."
  INTRO_CHAT = "{actor} исключил вас из группы «{title}»."
  VIOLATOR = (
    "{greeting}\n"
    "{staff_line}"
    "<blockquote><i>{intro}</i></blockquote>{reason_suffix}\n"
    "<blockquote><b><i>Вернуться можно по ссылке-приглашению на группу.</i></b></blockquote>"
  )
  BTN_RETURN = "Вернуться в группу"

  # --- Уведомление в группах ---
  GROUP_TITLE = "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Участник исключён</b>"
  GROUP_FOOTER = "<blockquote><b><i>{actor} исключил {player_short}.</i></b></blockquote>"
  GROUP = (
    "{group_title}\n"
    "{player_line}\n"
    "{staff_line}"
    "{chat_line}{reason_suffix}\n"
    "{group_footer}"
  )

  # --- Успех (в исходной группе) ---
  WARN_NONE = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "<i>Не удалось исключить - проверьте права бота и статус участника.</i></b>"
  )
  WARN_PARTIAL = (
    "\n<b><tg-emoji emoji-id='5420323339723881652'>⚠️</tg-emoji> "
    "<i>Исключён из {count} групп; часть чатов пропущена.</i></b>"
  )
  SUCCESS = (
    "{header} <b>· выполнен</b>\n"
    "{player_line}\n"
    "{staff_line}\n"
    "{reason_block}{warn}"
  )

  # --- Пруф / ошибки ---
  PROOF_MISSING = (
    "<b><tg-emoji emoji-id='5454419255430767770'>📎</tg-emoji> Исключение не выполнено</b>\n"
    "<blockquote><i>Фото-доказательство не получено.</i></blockquote>"
  )
  DB_ERROR = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ошибка - не удалось сохранить кик.</b>"
  NEED_PHOTO = "<b><tg-emoji emoji-id='5305265301917549162'>📎</tg-emoji> Нужно фото - прикрепите изображение.</b>"
  WRONG_CHAT = (
    "{greeting}\n"
    "{staff_line}\n"
    "{player_line}"
    "{pending_chat_line}"
    "<blockquote><b>Отправьте фото в тот же чат, где была выдана команда кика.</b></blockquote>"
  )

  # --- Запреты / предпроверка ---
  SELF = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя кикнуть себя</b>"
  BOT = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нельзя кикнуть бота</b>"
  BLOCKED = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> {reason}</b>"
  NOT_MEMBER = "<b><tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> {player_short} не состоит {where}</b>"
  WHERE_CHAT = "в этой группе"
  WHERE_ALL = "в группах проекта"

  # --- Ожидание: истекло / отмена ---
  EXPIRED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Время ожидания истекло</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "{reason_part}"
    "<blockquote><b><i>Исключение не применено - фото не получено вовремя.</i></b></blockquote>"
  )
  CANCELLED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "{reason_part}"
    "<blockquote><b><i>Исключение не применено - фото больше не требуется.</i></b></blockquote>"
  )
  SUPERSEDED = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "<blockquote><b><i>Начато новое действие модерации - это ожидание фото "
    "больше не активно.</i></b></blockquote>"
  )
  CANCEL_FALLBACK = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Ожидание отменено</b>\n"
    "{player_line}\n"
    "{chat_line}\n"
    "<blockquote><i>Исключение не применено - фото больше не требуется.</i></blockquote>"
  )

  # --- Отмена ожидания (команды) ---
  CANCEL_NO_TARGET = (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> Укажите нарушителя</b>\n"
    "<code>отменить кик @user</code> · <code>отменить кик username</code>\n"
    "<blockquote><i>Или ответьте на сообщение нарушителя.</i></blockquote>"
  )
  NO_PENDING = (
    "{greeting}\n"
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет ожидания кика</b>\n"
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
    "<b>Для отмены укажите, для кого отменяется ожидание кика:</b>\n"
    "<code>{cancel_hint}</code>\n\n"
    "<blockquote><i>Либо нажмите кнопку «Отменить ожидание» под сообщением о фото.</i></blockquote>"
  )

  # --- Кнопка и всплывающие ответы (callback) ---
  BTN_CANCEL = "Отменить ожидание"
  CB_BAD_DATA = "Некорректные данные."
  CB_ONLY_AUTHOR = "Отменить может только автор команды."
  CB_DB = "База данных временно недоступна."
  CB_NO_PERM = "Недостаточно прав."
  CB_DONE = "Ожидание уже завершено или истекло."
  CB_STALE = "Данные устарели. Используйте команду отмены."
  CB_WRONG_CHAT = "Действие недоступно в этой группе."
  CB_CANCELLED = "Ожидание отменено."


class KickDebug:
  @staticmethod
  def log(stage: str, detail: str, **fields: Any) -> None:
    if not cfg.DEBUG:
      return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items()) if fields else ""
    line = f"[KICK][{stage}] {detail}" + (f" | {extra}" if extra else "")
    print(line)
    try:
      with open(KICK_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception as e:
      print(f"[KICK][LOGFILE] write error: {e}")

  @staticmethod
  def error(stage: str, detail: str, exc: Optional[BaseException] = None, **fields: Any) -> None:
    tb = traceback.format_exc() if exc else ""
    KickDebug.log(stage, f"ERROR: {detail}", **fields)
    if tb:
      print(tb)
      try:
        with open(KICK_LOG_FILE, "a", encoding="utf-8") as fh:
          fh.write(tb + "\n")
      except Exception:
        pass


def _debug_hint(code: str) -> str:
  if not cfg.DEBUG_ADMIN_HINTS:
    return ""
  return f"\n\n<i>🔧 debug:</i> <code>{escape(code)}</code>"


@dataclass
class ParsedKick:
  target_id: int
  target_name: str
  target_username: Optional[str]
  reason: str
  scope: Scope = "chat"


def _kick_badge(scope: Scope) -> str:
  """Короткая «шапка» с названием системы и охватом."""
  if scope == "all":
    return (
      "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Кикалл</b> "
      "<i>· все группы</i>"
    )
  return (
    "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Кик</b> "
    "<i>· эта группа</i>"
  )


def _kick_command_scope(text: str) -> Scope:
  _, scope = parse_command_scope(_cmd_word(text), KICK_COMMANDS, _KICK_CMD_ROOTS)
  return scope


def _is_kick_command(text: str) -> bool:
  ok, _ = parse_command_scope(_cmd_word(text), KICK_COMMANDS, _KICK_CMD_ROOTS)
  return ok


def _is_cancel_kick_command(text: str) -> bool:
  return bool(_CANCEL_KICK_RE.match((text or "").strip()))


def _is_kick_related_message(message: Message) -> bool:
  if not message.from_user:
    return False
  text = _get_command_text(message)
  if text:
    low = text.lower()
    if _is_cancel_kick_command(text):
      return True
    if _is_kick_command(text):
      return True
    if low in ("отмена", "cancel", "/cancel"):
      return True
  if _has_proof_media(message):
    from bot.admins.punish_proof import pending_contains
    if pending_contains(_pending_kicks, message.from_user.id):
      return True
  return False


def _strip_cancel_kick_prefix(text: str) -> str:
  m = _CANCEL_KICK_RE.match((text or "").strip())
  if not m:
    return ""
  return text[m.end():].strip()


def _cmd_word(text: str) -> str:
  parts = (text or "").strip().split()
  if not parts:
    return ""
  return parts[0].lower().split("@")[0]


def _strip_kick_prefix(text: str) -> str:
  t = (text or "").strip()
  if not t:
    return ""
  ok, _ = parse_command_scope(_cmd_word(t), KICK_COMMANDS, _KICK_CMD_ROOTS)
  if ok:
    parts = t.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
  return ""


def _suggest_cancel_kick_command(
  target_id: int,
  target_name: str,
  target_username: Optional[str] = None,
) -> str:
  if target_username:
    return f"отменить кик @{target_username.lstrip('@')}"
  if target_name and not str(target_name).isdigit():
    return f"отменить кик {target_name}"
  return f"отменить кик {target_id}"


def _kick_cancel_callback_data(admin_id: int, target_id: int) -> str:
  return f"kick:cancel:{admin_id}:{target_id}"


def _kick_pending_cancel_keyboard(admin_id: int, target_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
      text=KickText.BTN_CANCEL,
      callback_data=_kick_cancel_callback_data(admin_id, target_id),
    ),
  ]])


def _build_pending_kick_proof_text(
  parsed: ParsedKick,
  chat_line: str,
  cancel_hint: str,
) -> str:
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  return KickText.PENDING.format(
    player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
    chat_line=chat_line,
    header=_kick_badge(parsed.scope),
    scope_block=_format_scope_block(parsed.scope),
    reason_part=reason_part,
    timeout=cfg.proof_timeout_minutes(),
    cancel_hint=escape(cancel_hint),
  )


async def parse_kick_command(message: Message) -> ParsedKick | ParseError:
  text = _get_command_text(message)
  parts = text.split()
  KickDebug.log("PARSE", "start", text=text, parts=parts, reply=bool(message.reply_to_message))

  reply_msg = _get_reply_target_message(message)
  body_after_cmd = parts[1:] if len(parts) > 1 else []
  source_chat_id = message.chat.id

  if reply_msg and reply_msg.from_user:
    # Явное указание пользователя в команде (например @werkov3) важнее ответа.
    target_id, target_name, target_username, rest, not_found = await _resolve_reply_or_explicit(
      reply_msg.from_user, body_after_cmd, source_chat_id=source_chat_id,
    )
    if not_found:
      if str(not_found).isdigit():
        return ParseError(
          "kick_user_not_found",
          KickText.NOT_FOUND_ID.format(token=escape(not_found)),
          not_found,
        )
      return ParseError(
        "user_not_found",
        KickText.NOT_FOUND_EXPLICIT.format(token=escape(not_found)),
        not_found,
      )
    reason = " ".join(rest).strip() or "Не указана"
    return ParsedKick(
      target_id=target_id,
      target_name=target_name,
      target_username=target_username,
      reason=reason,
      scope=_kick_command_scope(text),
    )

  if not body_after_cmd:
    return ParseError(
      "kick_no_target",
      KickText.NO_TARGET,
      "no reply and empty body",
    )

  first = body_after_cmd[0]
  target_id, target_name, target_username = await _lookup_target_by_token(
    first, source_chat_id=source_chat_id,
  )
  if not target_id:
    if first.startswith("@") or _looks_like_username_token(first):
      username = first.lstrip("@")
      return ParseError(
        "kick_user_not_found",
        KickText.NOT_FOUND_USERNAME.format(username=escape(username)),
        first,
      )
    if first.isdigit():
      return ParseError(
        "kick_user_not_found",
        KickText.NOT_FOUND_ID.format(token=escape(first)),
        first,
      )
    return ParseError(
      "kick_user_not_found",
      KickText.NOT_FOUND_NAME.format(token=escape(first)),
      first,
    )

  reason = " ".join(body_after_cmd[1:]).strip() or "Не указана"
  scope = _kick_command_scope(text)
  return ParsedKick(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    reason=reason,
    scope=scope,
  )


def _looks_like_username_token(token: str) -> bool:
  from bot.admins.mute import _looks_like_telegram_username
  return _looks_like_telegram_username(token)


async def _send_kick_help(message: Message) -> None:
  await message.reply(
    KickText.HELP.format(timeout=cfg.proof_timeout_minutes()),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def _validate_kick_target_in_chat(chat_id: int, target_id: int) -> Optional[str]:
  """Ошибка на русском или None, если кик в этой группе допустим."""
  if chat_id > 0:
    return "кик доступен только в группах"
  from bot.admins.punish_validate import inspect_chat_member
  member, err = await inspect_chat_member(chat_id, target_id)
  if err == "invalid_user":
    return "пользователь не найден в Telegram"
  if member is None:
    KickDebug.log("TG", "get_chat_member", chat_id=chat_id, user_id=target_id, err=err)
    if err == "not_participant":
      return None
    return "не удалось проверить участника в группе"

  status = getattr(member, "status", None)
  user = getattr(member, "user", None)
  if user and getattr(user, "is_bot", False):
    return "нельзя кикнуть бота"
  if status in ("left", "kicked"):
    return None  # уже не в группе - пропускаем без ошибки
  if status == "creator":
    return "нельзя кикнуть создателя группы"
  if status == "administrator":
    return "нельзя кикнуть администратора Telegram"
  return None


async def _kick_in_chat(chat_id: int, user_id: int) -> bool:
  """Мягкий кик: ban + unban - пользователь может вернуться по ссылке."""
  if chat_id > 0:
    return False
  try:
    bot = _bot()
    await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
    await bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
    KickDebug.log("TG", "kick OK", chat_id=chat_id, user_id=user_id)
    return True
  except TypeError:
    try:
      await _bot().unban_chat_member(chat_id=chat_id, user_id=user_id)
      KickDebug.log("TG", "kick OK (legacy unban)", chat_id=chat_id, user_id=user_id)
      return True
    except Exception as e:
      KickDebug.error("TG", "kick", e, chat_id=chat_id, user_id=user_id)
      return False
  except Exception as e:
    from bot.admins.punish_validate import is_invalid_telegram_user_error
    if is_invalid_telegram_user_error(e):
      KickDebug.log("TG", "kick invalid user", chat_id=chat_id, user_id=user_id)
      return False
    KickDebug.error("TG", "kick", e, chat_id=chat_id, user_id=user_id)
    return False


_BLOCKING_KICK_ERRORS = frozenset({
  "нельзя кикнуть бота",
  "нельзя кикнуть создателя группы",
  "нельзя кикнуть администратора Telegram",
  "пользователь не найден в Telegram",
})


async def _validate_kick_before(target_id: int , * , scope: Scope , source_chat_id: int , user_id: int = None ,
        # добавлен параметр
) -> Tuple [ Optional [ str ] , bool ]:
  """Предпроверка кика: блокирующая ошибка и состоит ли пользователь в целевых группах."""
  chat_ids = list(cfg.STAFF_CHAT_IDS) if scope == "all" else [ source_chat_id ]
  any_member = False
  for cid in chat_ids:
    if scope == "chat" and not _is_staff_chat(cid , user_id):  # передаём user_id
      return "команда доступна только в официальных группах проекта" , False
    err = await _validate_kick_target_in_chat(cid , target_id)
    if err in _BLOCKING_KICK_ERRORS:
      return err , any_member
    from bot.admins.punish_validate import inspect_chat_member
    member , _probe_err = await inspect_chat_member(cid , target_id)
    if member and getattr(member , "status" , None) not in ("left" , "kicked"):
      any_member = True
  return None , any_member

async def _kick_with_scope(target_id: int , * , scope: Scope , source_chat_id: int , user_id: int = None ,
        # добавлен параметр
) -> Tuple [ int , List [ int ] , List [ str ] ]:
    """Исключает пользователя из одной группы или из всех групп проекта."""
    if scope == "all":
      return await _kick_in_all_staff_chats(target_id)

    if not _is_staff_chat(source_chat_id , user_id):
      return 0 , [ ] , [ "команда доступна только в официальных группах проекта" ]

    err = await _validate_kick_target_in_chat(source_chat_id , target_id)
    if err in _BLOCKING_KICK_ERRORS:
      return 0 , [ ] , [ err ]
    if err:
      return 0 , [ ] , [ err ]

    try:
      member = await _bot().get_chat_member(source_chat_id , target_id)
      if getattr(member , "status" , None) in ("left" , "kicked"):
        return 0 , [ ] , [ "пользователь не состоит в этой группе" ]
    except Exception as e:
      return 0 , [ ] , [ str(e) ]

    if await _kick_in_chat(source_chat_id , target_id):
      return 1 , [ source_chat_id ] , [ ]
    return 0 , [ ] , [ "не удалось исключить из группы" ]


async def _kick_in_all_staff_chats(
  target_id: int,
) -> Tuple[int, List[int], List[str]]:
  """Кикает из всех групп проекта, где пользователь состоит."""
  kicked: List[int] = []
  errors: List[str] = []
  for cid in cfg.STAFF_CHAT_IDS:
    err = await _validate_kick_target_in_chat(cid, target_id)
    if err in _BLOCKING_KICK_ERRORS:
      errors.append(err)
      continue
    if err:
      errors.append(f"чат {cid}: {err}")
      continue
    try:
      member = await _bot().get_chat_member(cid, target_id)
      if getattr(member, "status", None) in ("left", "kicked"):
        continue
    except Exception as e:
      errors.append(f"чат {cid}: {e}")
      continue
    if await _kick_in_chat(cid, target_id):
      kicked.append(cid)
  return len(kicked), kicked, errors


async def _apply_kick_db(
  target_user_id: int,
  target_name: str,
  admin_user_id: int,
  admin_name: str,
  reason: str,
  proof_media_id: str,
  chat_id: int,
  scope: Scope = "chat",
) -> Tuple[bool, Optional[int]]:
  try:
    async with _db_acquire() as conn:
      async with conn.transaction():
        await conn.execute(
          """
          INSERT INTO users (user_id, first_name)
          VALUES ($1, $2)
          ON CONFLICT (user_id) DO UPDATE
          SET first_name = COALESCE(users.first_name, EXCLUDED.first_name)
          """,
          target_user_id, target_name,
        )
        row = await conn.fetchrow(
          """
          INSERT INTO staff_actions (
            admin_user_id, admin_name, action_type,
            target_player_id, target_name,
            reason, proof_media_id, chat_id, scope, proof_bot_token
          )
          VALUES ($1, $2, 'kick', $3, $4, $5, $6, $7, $8, $9)
          RETURNING id
          """,
          admin_user_id, admin_name, target_user_id, target_name,
          reason, proof_media_id, chat_id, scope,
          _proof_owner_token(proof_media_id),
        )
        action_id = row["id"] if row else None
        KickDebug.log(
          "DB", "kick saved",
          target=target_user_id, chat_id=chat_id,
          proof=proof_media_id[:24], action_id=action_id,
        )
        return True, action_id
  except DbUnavailableError as e:
    KickDebug.log("DB", "apply_kick skipped", err=str(e), target=target_user_id)
    return False, None
  except Exception as e:
    KickDebug.error("DB", "apply_kick", e, target=target_user_id)
    return False, None


async def _notify_kick(
  source_chat_id: int,
  parsed: ParsedKick,
  *,
  acting_admin_id: int,
  acting_admin_name: str,
  acting_admin_role: Optional[str],
  acting_admin_username: Optional[str],
  kicked_chat_ids: List[int],
) -> None:
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  staff = StaffRef(
    acting_admin_id, acting_admin_name, acting_admin_role, acting_admin_username,
  )
  reason_line = _format_mute_reason_block(parsed.reason, label="Причина")
  reason_suffix = f"\n{reason_line}" if reason_line else ""
  staff_line = f"{staff.line}\n"
  actor = staff.actor

  if parsed.scope == "all":
    violator_intro = KickText.INTRO_ALL.format(actor=actor, scope=scope_label("all"))
    notify_chats = set(kicked_chat_ids) if kicked_chat_ids else set(cfg.STAFF_CHAT_IDS)
  else:
    disp = await _get_chat_display(source_chat_id)
    violator_intro = KickText.INTRO_CHAT.format(actor=actor, title=escape(disp.title))
    notify_chats = {source_chat_id}

  # В исходной группе уже показано «Исключение выполнено» - групповое
  # уведомление туда не дублируем; оно идёт только в ОСТАЛЬНЫЕ группы.
  notify_chats.discard(source_chat_id)

  violator_text = KickText.VIOLATOR.format(
    greeting=player.greeting,
    staff_line=staff_line,
    intro=violator_intro,
    reason_suffix=reason_suffix,
  )

  group_title = KickText.GROUP_TITLE
  group_footer = KickText.GROUP_FOOTER.format(actor=actor, player_short=player.short)

  primary_link: Optional[str] = None
  for cid in kicked_chat_ids or list(notify_chats):
    disp = await _get_chat_display(cid)
    if disp.link_url and not primary_link:
      primary_link = disp.link_url

  try:
    if primary_link:
      kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=KickText.BTN_RETURN, url=primary_link),
      ]])
      await _bot().send_message(
        parsed.target_id, violator_text, parse_mode="HTML", reply_markup=kb,
        link_preview_options=NO_PREVIEW,
      )
    else:
      await _bot().send_message(
        parsed.target_id, violator_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
  except Exception as e:
    KickDebug.log("NOTIFY", "violator skip", user_id=parsed.target_id, err=str(e))

  for group_chat_id in notify_chats:
    disp = await _get_chat_display(group_chat_id)
    chat_line = _format_chat_line(disp)
    group_text = KickText.GROUP.format(
      group_title=group_title,
      player_line=player.line,
      staff_line=staff_line,
      chat_line=chat_line,
      reason_suffix=reason_suffix,
      group_footer=group_footer,
    )
    try:
      await _bot().send_message(
        group_chat_id, group_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
    except Exception as e:
      KickDebug.log("NOTIFY", "group skip", chat_id=group_chat_id, err=str(e))


async def _send_success_kick(
  message: Message,
  parsed: ParsedKick,
  chat_id: int,
  kicked_count: int,
  kicked_ids: List[int],
  errors: List[str],
) -> None:
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  warn = ""
  if kicked_count == 0:
    warn = KickText.WARN_NONE
  elif errors:
    warn = KickText.WARN_PARTIAL.format(count=kicked_count)
  scope_block = await _format_scope_with_groups(parsed.scope, kicked_ids)
  staff = await StaffRef.from_message(message)
  await message.reply(
    KickText.SUCCESS.format(
      player_line=_format_player_line(parsed.target_id, parsed.target_name, parsed.target_username),
      staff_line=staff.line,
      chat_line=chat_line,
      header=_kick_badge(parsed.scope),
      scope_block=scope_block,
      reason_block=_format_mute_reason_block(parsed.reason, label="Причина"),
      warn=warn,
    ),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
  )


async def _finalize_kick(
  message: Message,
  parsed: ParsedKick,
  proof_media_id: str,
  chat_id: int,
  admin_name: str,
) -> bool:
  # Наказание выдаётся СТРОГО после подтверждения пруфа: без фото - не применяем.
  if not proof_media_id:
    await message.reply(
      KickText.PROOF_MISSING + _debug_hint("proof_required"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    KickDebug.log("PROOF", "finalize blocked - no proof", target=getattr(parsed, "target_id", None))
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("kick_invalid_user_finalize"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    KickDebug.log("TG", "kick finalize blocked - invalid user", target=parsed.target_id)
    return True
  ok, _action_id = await _apply_kick_db(
    target_user_id=parsed.target_id,
    target_name=parsed.target_name,
    admin_user_id=message.from_user.id,
    admin_name=admin_name,
    reason=parsed.reason,
    proof_media_id=proof_media_id,
    chat_id=chat_id,
    scope=parsed.scope,
  )
  if not ok:
    await message.reply(
      KickText.DB_ERROR + _debug_hint("kick_db_failed"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  kicked_count, kicked_ids, errors = await _kick_with_scope(
    parsed.target_id,
    scope=parsed.scope,
    source_chat_id=chat_id,
  )
  admin_name, admin_role, _ = await _resolve_admin_identity(message)
  await _send_success_kick(message, parsed, chat_id, kicked_count, kicked_ids, errors)
  await _notify_kick(
    chat_id, parsed,
    acting_admin_id=message.from_user.id,
    acting_admin_name=admin_name,
    acting_admin_role=admin_role,
    acting_admin_username=message.from_user.username,
    kicked_chat_ids=kicked_ids,
  )
  return True


async def _expire_pending_kick(admin_id: int, data: Dict[str, Any]) -> None:
  from bot.admins.punish_proof import coerce_telegram_user_id, safe_edit_message_text
  admin_id = coerce_telegram_user_id(admin_id)
  if admin_id is None or data.get("expiry_notified"):
    return
  data["expiry_notified"] = True

  parsed: ParsedKick = data["parsed"]
  player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
  prompt_chat = data.get("prompt_chat_id")
  prompt_msg_id = data.get("prompt_message_id")
  chat_id = data.get("chat_id", 0)
  disp = await _get_chat_display(chat_id) if chat_id else None
  chat_line = _format_chat_line(disp) if disp else ""
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  final_text = KickText.EXPIRED.format(
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
      KickDebug.log("PENDING", "edit expired skip", err=str(e))
  try:
    await _bot().send_message(
      admin_id, final_text, parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  except Exception as e:
    KickDebug.log("PENDING", "notify admin expired skip", admin_id=admin_id, err=str(e))


async def _cleanup_expired_pending_kicks_async() -> None:
  from bot.admins.punish_proof import is_proof_expired, pending_items, pending_pop

  now = time.time()
  for uid, data in pending_items(_pending_kicks):
    if not is_proof_expired(data.get("expires_at", 0), now=now):
      continue
    pending_pop(_pending_kicks, uid)
    KickDebug.log("PENDING", "expired - kick NOT applied", admin_id=uid)
    await _expire_pending_kick(uid, data)


async def _finish_pending_kick_cancel(
  admin_id: int,
  player_line: str,
  chat_id: int,
  parsed: ParsedKick,
) -> bool:
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_kicks, admin_id)
  if not pending:
    return False
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  reason_line = _format_mute_reason_block(parsed.reason, label="Заявленная причина")
  reason_part = f"{reason_line}\n" if reason_line else ""
  final_text = KickText.CANCELLED.format(
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
      KickDebug.error("FLOW", "edit pending prompt", e, chat=prompt_chat, msg=prompt_msg_id)
  return False


async def _complete_kick_with_proof(message: Message) -> bool:
  from bot.admins.punish_proof import (
    is_proof_expired,
    latest_pending_system_for,
    pending_get,
    pending_pop,
  )

  admin_id = message.from_user.id
  if latest_pending_system_for(admin_id) != "kick":
    return False

  pending = pending_get(_pending_kicks, admin_id)
  if not pending:
    KickDebug.log("PROOF", "no pending", admin_id=admin_id)
    return False

  if is_proof_expired(pending.get("expires_at", 0)):
    pending_pop(_pending_kicks, admin_id)
    KickDebug.log("PROOF", "late proof ignored - expired", admin_id=admin_id)
    return True

  pending_chat = pending.get("chat_id")
  if not _is_staff_chat(message.chat.id) or message.chat.id != pending_chat:
    staff = await StaffRef.from_message(message)
    parsed: ParsedKick = pending.get("parsed")
    player_line = PlayerRef(
      parsed.target_id, parsed.target_name, parsed.target_username,
    ).line + "\n" if parsed else ""
    pending_disp = await _get_chat_display(pending_chat) if pending_chat else None
    pending_chat_line = (
      _format_chat_line(pending_disp) + "\n" if pending_disp else ""
    )
    await message.reply(
      KickText.WRONG_CHAT.format(
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
      KickText.NEED_PHOTO + _debug_hint("kick_proof_missing"),
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
    debug_tag="kick_invalid_user_proof",
  ):
    pending_pop(_pending_kicks, admin_id)
    await clear_pending_prompt_keyboard(pending)
    return True

  KickDebug.log("PROOF", "received", admin_id=admin_id, file_id=proof_media_id[:24])
  await run_finalize_with_pending_fallback(
    message, admin_id, _pending_kicks, pending,
    lambda: _finalize_kick(
      message, parsed, proof_media_id,
      pending["chat_id"], pending["admin_name"],
    ),
    on_db_unavailable=lambda: _reply_db_unavailable(message),
  )
  return True


async def _supersede_pending_kick(admin_id: int) -> None:
  """Снимает «зависшее» ожидание фото у этого администратора при начале нового
  действия кика, чтобы случайное фото позже не закрыло его повторно."""
  from bot.admins.punish_proof import pending_pop
  pending = pending_pop(_pending_kicks, admin_id)
  if not pending:
    return
  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if prompt_chat and prompt_msg_id:
    try:
      await _bot().edit_message_text(
        KickText.SUPERSEDED,
        chat_id=prompt_chat, message_id=prompt_msg_id,
        parse_mode="HTML", reply_markup=None, link_preview_options=NO_PREVIEW,
      )
    except Exception:
      try:
        await _bot().edit_message_reply_markup(
          chat_id=prompt_chat, message_id=prompt_msg_id, reply_markup=None,
        )
      except Exception as e:
        KickDebug.log("PROOF", "supersede cleanup skip", err=str(e))
  KickDebug.log("PROOF", "superseded by new kick action", admin_id=admin_id)


async def _handle_kick_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _db().ensure_pool():
    await message.reply(_service_unavailable_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  if not await _require_staff_chat(message):
    return True

  command_text = _get_command_text(message)
  if _is_kick_command(command_text) and len(command_text.split()) == 1:
    await _send_kick_help(message)
    return True

  result = await parse_kick_command(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    KickDebug.log("PARSE", "error", code=result.code, info=result.debug_info)
    return True

  parsed = result

  if is_protected_creator(parsed.target_id):
    await message.reply(protected_creator_denied_html(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    KickDebug.log("AUTH", "protected creator blocked", target=parsed.target_id)
    return True
  if parsed.target_id == message.from_user.id:
    await message.reply(KickText.SELF, parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True
  if parsed.target_id == _bot().id:
    await message.reply(KickText.BOT, parse_mode="HTML", link_preview_options=NO_PREVIEW)
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
      punishment_invalid_user_html(parsed.target_id) + _debug_hint("kick_invalid_user"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    KickDebug.log("TG", "kick blocked - invalid user", target=parsed.target_id)
    return True

  chat_id = message.chat.id
  block_err, any_member = await _validate_kick_before(
    parsed.target_id,
    scope=parsed.scope,
    source_chat_id=chat_id,
  )
  if block_err:
    await message.reply(
      KickText.BLOCKED.format(reason=escape(block_err.capitalize()))
      + _debug_hint("kick_blocked"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True
  if not any_member:
    player = PlayerRef(parsed.target_id, parsed.target_name, parsed.target_username)
    where = KickText.WHERE_CHAT if parsed.scope == "chat" else KickText.WHERE_ALL
    await message.reply(
      KickText.NOT_MEMBER.format(player_short=player.short, where=where)
      + _debug_hint("kick_not_member"),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  proof_id = _get_proof_file_id(message)
  admin_name, admin_role, _ = await _resolve_admin_identity(message)

  # Новое действие кика отменяет прежнее «зависшее» ожидание этого админа.
  await _supersede_pending_kick(message.from_user.id)

  if proof_id:
    KickDebug.log("FLOW", "one-step kick with photo", proof=proof_id[:24])
    await _finalize_kick(message, parsed, proof_id, chat_id, admin_name)
    return True

  admin_id = message.from_user.id
  from bot.admins.punish_proof import (
    clear_other_pending_proofs,
    new_pending_record,
    pending_get,
    pending_set,
  )
  ensure_proof_pending_worker()
  clear_other_pending_proofs(admin_id, keep="kick")
  pending_set(_pending_kicks, admin_id, new_pending_record(
    parsed=parsed,
    chat_id=chat_id,
    admin_name=admin_name,
    admin_role=admin_role,
  ))
  disp = await _get_chat_display(chat_id)
  chat_line = _format_chat_line(disp)
  cancel_hint = _suggest_cancel_kick_command(
    parsed.target_id, parsed.target_name, parsed.target_username,
  )
  sent = await message.reply(
    _build_pending_kick_proof_text(parsed, chat_line, cancel_hint)
    + _debug_hint("awaiting_kick_proof"),
    parse_mode="HTML", link_preview_options=NO_PREVIEW,
    reply_markup=_kick_pending_cancel_keyboard(admin_id, parsed.target_id),
  )
  pending = pending_get(_pending_kicks, admin_id)
  if pending is not None:
    pending["prompt_chat_id"] = sent.chat.id
    pending["prompt_message_id"] = sent.message_id
  KickDebug.log(
    "FLOW", "pending proof",
    admin_id=admin_id, target=parsed.target_id, message_id=sent.message_id,
  )
  return True


async def _resolve_cancel_kick_target(message: Message) -> ParsedKick | ParseError:
  reply_msg = _get_reply_target_message(message)
  if reply_msg and reply_msg.from_user:
    u = reply_msg.from_user
    return ParsedKick(
      target_id=u.id,
      target_name=u.full_name or u.first_name or str(u.id),
      target_username=u.username,
      reason="",
    )

  body = _strip_cancel_kick_prefix(_get_command_text(message))
  if not body:
    return ParseError(
      "cancel_kick_no_target",
      KickText.CANCEL_NO_TARGET,
      "",
    )

  target_id, target_name, target_username = await _resolve_target_from_body(message, body)
  if not target_id:
    return ParseError(
      "cancel_kick_not_found",
      _target_lookup_error_message(body, target_username=target_username),
      body,
    )

  return ParsedKick(
    target_id=target_id,
    target_name=target_name or str(target_id),
    target_username=target_username,
    reason="",
  )


async def _handle_cancel_kick_command(message: Message) -> bool:
  await _ensure_mute_schema()
  if not await _require_staff_chat(message):
    return True

  result = await _resolve_cancel_kick_target(message)
  if isinstance(result, ParseError):
    await message.reply(result.admin_message + _debug_hint(result.code), parse_mode="HTML", link_preview_options=NO_PREVIEW)
    return True

  target = result
  admin_id = message.from_user.id
  staff = await StaffRef.from_message(message)
  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_kicks, admin_id)
  player = PlayerRef(target.target_id, target.target_name, target.target_username)

  if not pending:
    await message.reply(
      KickText.NO_PENDING.format(greeting=staff.greeting, player_line=player.line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  if pending["parsed"].target_id != target.target_id:
    pending_player = PlayerRef(
      pending["parsed"].target_id,
      pending["parsed"].target_name,
      pending["parsed"].target_username,
    )
    cancel_hint = escape(_suggest_cancel_kick_command(
      pending["parsed"].target_id, pending["parsed"].target_name, pending["parsed"].target_username,
    ))
    await message.reply(
      KickText.OTHER_PENDING.format(
        greeting=staff.greeting,
        pending_player_line=pending_player.line,
        cancel_hint=cancel_hint,
      ),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
    return True

  chat_id = pending.get("chat_id", message.chat.id)
  edited = await _finish_pending_kick_cancel(
    admin_id, player.line, chat_id, pending["parsed"],
  )
  if not edited:
    disp = await _get_chat_display(chat_id)
    chat_line = _format_chat_line(disp)
    await message.reply(
      KickText.CANCEL_FALLBACK.format(player_line=player.line, chat_line=chat_line),
      parse_mode="HTML", link_preview_options=NO_PREVIEW,
    )
  KickDebug.log("FLOW", "pending cancelled", admin_id=admin_id, target=target.target_id)
  return True


async def _maybe_kick_maintenance() -> None:
  """Ожидание фото обрабатывает proof worker."""
  return


async def kick_process(message: Message) -> bool:
  """Обрабатывает сообщения системы кика. True = перехвачено."""
  if not message.from_user:
    return False

  from bot.admins.punish_proof import (
    is_proof_only_photo,
    pending_contains,
    pending_get,
  )

  chat_id = message.chat.id
  uid = message.from_user.id
  pending = pending_contains(_pending_kicks, uid)

  if not pending and chat_id > 0:
    return False
  if not pending and chat_id < 0 and not _is_staff_chat(chat_id):
    if not _is_kick_related_message(message):
      return False

  await _ensure_mute_schema()

  command_text = _get_command_text(message)
  KickDebug.log(
    "IN", "message",
    uid=uid, chat=chat_id,
    text=command_text[:80] if command_text else "",
    photo=bool(message.photo), reply=bool(message.reply_to_message),
    pending=pending,
  )

  if pending:
    if is_proof_only_photo(message):
      return await _complete_kick_with_proof(message)

    if not command_text:
      KickDebug.log("PROOF", "ignored non-photo while pending", uid=uid)
      return True

    low = command_text.lower().strip()
    if low in ("отмена", "cancel", "/cancel"):
      if not pending_contains(_pending_kicks, uid):
        return False
      perm = await check_staff_permission(uid, "kick")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        await _send_no_permission(message, "kick")
        return True
      if not _is_staff_chat(message.chat.id):
        return False
      pending_data = pending_get(_pending_kicks, uid)
      if not pending_data:
        return False
      p: ParsedKick = pending_data["parsed"]
      hint = _suggest_cancel_kick_command(p.target_id, p.target_name, p.target_username)
      staff = await StaffRef.from_message(message)
      player = PlayerRef(p.target_id, p.target_name, p.target_username)
      await message.reply(
        KickText.CANCEL_HELP.format(
          greeting=staff.greeting,
          staff_line=staff.line,
          player_line=player.line,
          cancel_hint=escape(hint),
        ),
        parse_mode="HTML", link_preview_options=NO_PREVIEW,
      )
      return True

    if _is_cancel_kick_command(command_text):
      perm = await check_staff_permission(uid, "kick")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "cancel_kick")
      return await _handle_cancel_kick_command(message)

    if _is_kick_command(command_text):
      perm = await check_staff_permission(uid, "kick")
      if perm == "db_unavailable":
        await _reply_db_unavailable(message)
        return True
      if perm != "allowed":
        return await deny_permission(message, "kick")
      return await _handle_kick_command(message)

    KickDebug.log("PROOF", "ignored text while pending", uid=uid, text=command_text[:60])
    return True

  if is_proof_only_photo(message) and _is_kick_related_message(message):
    perm = await check_staff_permission(uid, "kick")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "kick")
    return await _handle_kick_command(message)

  if not command_text:
    return False

  low = command_text.lower().strip()
  if low in ("отмена", "cancel", "/cancel"):
    return False

  if _is_cancel_kick_command(command_text):
    perm = await check_staff_permission(message.from_user.id, "kick")
    if perm == "db_unavailable":
      await _reply_db_unavailable(message)
      return True
    if perm != "allowed":
      return await deny_permission(message, "cancel_kick")
    return await _handle_cancel_kick_command(message)

  if not _is_kick_command(command_text):
    return False

  perm = await check_staff_permission(message.from_user.id, "kick")
  if perm == "db_unavailable":
    await _reply_db_unavailable(message)
    return True
  if perm != "allowed":
    return await deny_permission(message, "kick")

  return await _handle_kick_command(message)


@kick_router.callback_query(F.data.startswith("kick:cancel:"))
async def on_kick_pending_cancel(callback: CallbackQuery) -> None:
  if not callback.from_user or not callback.message:
    await callback.answer()
    return

  parts = (callback.data or "").split(":")
  if len(parts) != 4:
    await callback.answer(KickText.CB_BAD_DATA, show_alert=True)
    return

  admin_id = int(parts[2])
  target_id = int(parts[3])

  if callback.from_user.id != admin_id:
    await callback.answer(KickText.CB_ONLY_AUTHOR, show_alert=True)
    return

  perm = await check_staff_permission(admin_id, "kick")
  if perm != "allowed":
    if perm == "db_unavailable":
      await callback.answer(KickText.CB_DB, show_alert=True)
    else:
      await callback.answer(KickText.CB_NO_PERM, show_alert=True)
    return

  from bot.admins.punish_proof import pending_get
  pending = pending_get(_pending_kicks, admin_id)
  if not pending:
    try:
      await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
      pass
    await callback.answer(KickText.CB_DONE, show_alert=True)
    return

  if pending["parsed"].target_id != target_id:
    await callback.answer(KickText.CB_STALE, show_alert=True)
    return

  if not _is_staff_chat(callback.message.chat.id):
    await callback.answer(KickText.CB_WRONG_CHAT, show_alert=True)
    return

  parsed: ParsedKick = pending["parsed"]
  player_line = PlayerRef(
    target_id, parsed.target_name, parsed.target_username,
  ).line
  chat_id = pending.get("chat_id", callback.message.chat.id)
  await _finish_pending_kick_cancel(admin_id, player_line, chat_id, parsed)
  await callback.answer(KickText.CB_CANCELLED)
  KickDebug.log("FLOW", "pending cancelled via button", admin_id=admin_id, target=target_id)


# ---------------------------------------------------------------------------
# Middleware - перехват сообщений системы кика
# ---------------------------------------------------------------------------

class KickMiddleware(BaseMiddleware):
  """
  Фоновая поддержка системы кика:
    • шаг 2 - фото-пруф / отмена при активном ожидании (pending);
    • одношаговый кик с фото-пруфом и подписью-командой (медиа main.py не ловит).

  Текстовые команды кика (без фото) приходят из main.py по паттерну игровых
  команд - здесь они НЕ перехватываются, чтобы не было двойной обработки.
  """
  async def __call__(self, handler, event: TelegramObject, data: dict):
    if not isinstance(event, Message) or not event.from_user:
      return await handler(event, data)

    msg: Message = event
    uid = msg.from_user.id
    from bot.admins.punish_proof import pending_contains
    pending = pending_contains(_pending_kicks, uid)
    staff_group = msg.chat.id < 0 and _is_staff_chat(msg.chat.id)

    media_command = (
      not pending
      and staff_group
      and _has_proof_media(msg)
      and _is_kick_related_message(msg)
    )

    if not pending and not media_command:
      return await handler(event, data)

    try:
      if await kick_process(msg):
        KickDebug.log("MW", "handled kick", msg_id=msg.message_id, pending=pending)
        return None
    except Exception as e:
      KickDebug.error("MW", "kick_process crash", e, msg_id=getattr(msg, "message_id", None))
      try:
        await msg.reply(_generic_handler_error_message(), parse_mode="HTML", link_preview_options=NO_PREVIEW)
      except Exception:
        pass
    return await handler(event, data)


# ---------------------------------------------------------------------------
# Роутер (запасной канал)
# ---------------------------------------------------------------------------

@kick_router.message(F.photo)
async def kick_on_photo(message: Message) -> None:
  if _is_kick_related_message(message):
    await kick_process(message)


async def kick(message: Message) -> None:
  await kick_process(message)


def attach_kick_system(dp) -> None:

  global _kick_system_attached
  if _kick_system_attached:
    KickDebug.log("WIRE", "already attached")
    return
  try:
    dp.message.middleware(KickMiddleware())
    dp.include_router(kick_router)
    _kick_system_attached = True
    ensure_proof_pending_worker()
    KickDebug.log("WIRE", "attached middleware + router", log_file=KICK_LOG_FILE)
    print(f"[KICK] ✅ Система кика подключена → лог: {KICK_LOG_FILE}")
  except Exception as e:
    KickDebug.error("WIRE", "attach failed", e)
    print(f"[KICK][WIRE][ERROR] {e}")
