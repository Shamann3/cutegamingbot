# -*- coding: utf-8 -*-
"""
Проверка существования цели наказания в Telegram.

Короткое число вроде «10» человеком не считается.
USER_ID_INVALID и PEER_ID_INVALID — такого аккаунта нет.
PARTICIPANT_ID_INVALID у getChatMember — человек не в этой группе:
Telegram так отвечает и на живой id, поэтому это не отказ в аккаунте.
"""
from __future__ import annotations

import asyncio
import time
from html import escape
from typing import Any, Iterable, Optional, Tuple

_INVALID_TG_USER_MARKERS = frozenset({
  "USER_ID_INVALID",
  "PEER_ID_INVALID",
})

_USER_NOT_PARTICIPANT_MARKERS = frozenset({
  "PARTICIPANT_ID_INVALID",
  "USER_NOT_PARTICIPANT",
  "MEMBER_NOT_FOUND",
  "USER_NOT_FOUND",
})


def _telegram_error_text(exc: BaseException) -> str:
  """Собирает текст ошибки Telegram API из aiogram-исключения."""
  parts: list[str] = []
  for val in (
    getattr(exc, "message", None),
    getattr(exc, "description", None),
    getattr(exc, "method", None),
    str(exc),
  ):
    text = str(val or "").strip()
    if text and text not in parts:
      parts.append(text)
  return " ".join(parts).upper()


def _marker_hit(msg: str, markers: Iterable[str]) -> bool:
  folded = msg.replace(" ", "_")
  return any(marker in msg or marker in folded for marker in markers)


def is_invalid_telegram_user_error(exc: BaseException) -> bool:
  """True, если Telegram однозначно сообщает, что user_id не существует."""
  return _marker_hit(_telegram_error_text(exc), _INVALID_TG_USER_MARKERS)


def is_user_not_participant_error(exc: BaseException) -> bool:
  """True, если user_id валиден, но пользователь не состоит в группе."""
  msg = _telegram_error_text(exc)
  if "CHAT_NOT_FOUND" in msg.replace(" ", "_") or "CHAT NOT FOUND" in msg:
    return False
  return _marker_hit(msg, _USER_NOT_PARTICIPANT_MARKERS)


def _bot():
  from main import bot1
  return bot1


def _staff_chat_ids() -> Iterable[int]:
  from bot.admins.mute import live_staff_chat_ids
  return live_staff_chat_ids()


def probe_chat_ids(source_chat_id: Optional[int] = None) -> Tuple[int, ...]:
  """Чаты для проверки: сначала текущий, затем все официальные группы."""
  seen: set[int] = set()
  ordered: list[int] = []
  if source_chat_id and source_chat_id < 0:
    seen.add(source_chat_id)
    ordered.append(source_chat_id)
  for cid in _staff_chat_ids():
    if cid not in seen and cid < 0:
      seen.add(cid)
      ordered.append(cid)
  return tuple(ordered)


# Совместимость с существующим именем внутри модуля.
_probe_chat_ids = probe_chat_ids


async def inspect_chat_member(
  chat_id: int,
  user_id: int,
) -> Tuple[Optional[Any], Optional[str]]:
  """
  Запрашивает участника в группе.

  Возвращает (member, error_kind):
    • (member, None) успех (любой status, в т.ч. left/kicked);
    • (None, 'invalid_user') Telegram сказал, что такого аккаунта нет;
    • (None, 'not_participant') в этой группе его нет, аккаунт при этом может быть;
    • (None, 'check_failed') сетевая/прочая ошибка.
  """
  if chat_id > 0:
    return None, "check_failed"
  try:
    member = await _bot().get_chat_member(chat_id, user_id)
    return member, None
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return None, "invalid_user"
    if is_user_not_participant_error(e):
      return None, "not_participant"
    return None, "check_failed"


async def verify_telegram_user_exists(
  user_id: int,
  *,
  probe_chat_ids: Optional[Iterable[int]] = None,
) -> bool:
  """
  Проверяет, что user_id реальный аккаунт Telegram.

  Стратегия:
    1. getChat(user_id) — Telegram отдаёт человека, если бот его уже видел;
    2. USER_ID_INVALID / PEER_ID_INVALID — аккаунта нет;
    3. иначе юзербот спрашивает users.getUsers, а длинный id всё равно проходит.
  getChatMember сюда не входит: «нет в этой группе» он путает с несуществующим id.
  """
  if user_id <= 0:
    return False

  bot = _bot()
  try:
    chat = await bot.get_chat(user_id)
    chat_id = getattr(chat, "id", None)
    chat_type = getattr(chat, "type", None)
    type_key = chat_type.value if hasattr(chat_type, "value") else str(chat_type or "")
    if chat_id == user_id and type_key == "private":
      if bool(getattr(chat, "is_bot", False)):
        return False
      return True
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return False

  return await _unseen_account_is_real(user_id)


async def validate_punishment_target_user(
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
) -> Optional[str]:
  """
  Возвращает текст ошибки для администратора или None, если цель валидна.
  """
  if not await verify_telegram_user_exists(
    user_id,
    probe_chat_ids=probe_chat_ids(source_chat_id),
  ):
    return "пользователь не найден в Telegram"
  return None


def punishment_invalid_user_html(user_id: int) -> str:
  """Единое HTML-сообщение для всех систем наказаний."""
  return (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    f"Пользователь <code>{escape(str(user_id))}</code> не найден в Telegram</b>\n"
    "<i>Проверьте ID, @username или укажите нарушителя ответом на сообщение.</i>"
  )


def invalid_numeric_target_token(body: list[str]) -> Optional[str]:
  """
  «бан 10 10», «кик 99 99» только цифры без единиц срока.
  Возвращает первый токен для сообщения об ошибке или None.
  """
  if not body:
    return None
  from bot.admins.mute import _body_starts_with_duration

  tokens = [p.strip() for p in body if p.strip()]
  if not tokens:
    return None
  if _body_starts_with_duration(tokens):
    return None
  if all(t.isdigit() for t in tokens):
    return tokens[0]
  return None


def _identity_rules():
  import sys
  from pathlib import Path
  server = Path(__file__).resolve().parents[2] / "server"
  folder = str(server)
  if folder not in sys.path:
    sys.path.insert(0, folder)
  import cute_identity
  return cute_identity


def _database():
  from bot.admins.mute import _db
  return _db()


def _person_from_telegram_object(obj: Any, *, private_only: bool) -> Optional[dict]:
  """Имя и username с объекта aiogram. Чужой чат человеком не считается."""
  if obj is None:
    return None
  if private_only:
    chat_type = getattr(obj, "type", None)
    type_key = chat_type.value if hasattr(chat_type, "value") else str(chat_type or "")
    if type_key != "private":
      return None
  rules = _identity_rules()
  return rules.person_from_user_fields(
    getattr(obj, "id", None),
    getattr(obj, "first_name", None),
    getattr(obj, "last_name", None),
    getattr(obj, "username", None),
    is_bot=bool(getattr(obj, "is_bot", False)),
  )


async def _stored_user(user_id: int) -> Tuple[bool, str, Optional[str]]:
  if user_id <= 0:
    return False, "", None
  db = _database()
  pool = getattr(db, "pool", None)
  if pool is None and hasattr(db, "ensure_pool"):
    try:
      await db.ensure_pool()
    except Exception:
      return False, "", None
    pool = getattr(db, "pool", None)
  if pool is None:
    return False, "", None
  try:
    row = await pool.fetchrow(
      "SELECT first_name, username FROM users WHERE user_id = $1",
      int(user_id),
    )
  except Exception:
    return False, "", None
  if not row:
    return False, "", None
  return True, (row["first_name"] or ""), (row["username"] or None)


async def _adopt_person(person: dict) -> None:
  rules = _identity_rules()
  db = _database()
  pool = getattr(db, "pool", None)
  if pool is None and hasattr(db, "ensure_pool"):
    await db.ensure_pool()
    pool = getattr(db, "pool", None)
  if pool is None:
    return
  await pool.execute(
    rules.ADOPT_USER_SQL,
    int(person["user_id"]),
    person["first_name"],
    person.get("username"),
  )


_USERBOT_WAIT = 4.0
_USERBOT_MEMORY = 45.0
_userbot_seen: dict[int, tuple[float, str, Optional[dict]]] = {}


def _remember_userbot(user_id: int, kind: str, person: Optional[dict]) -> tuple[str, Optional[dict]]:
  _userbot_seen[int(user_id)] = (time.time(), kind, person)
  if len(_userbot_seen) > 2000:
    now = time.time()
    for key, item in list(_userbot_seen.items()):
      if now - item[0] > _USERBOT_MEMORY:
        _userbot_seen.pop(key, None)
  return kind, person


async def _ask_userbot(user_id: int) -> tuple[str, Optional[dict]]:
  """("person", словарь) | ("missing", None) | ("bot", None) | ("unknown", None)."""
  cached = _userbot_seen.get(int(user_id))
  if cached and time.time() - cached[0] < _USERBOT_MEMORY:
    return cached[1], cached[2]
  try:
    from bot.funcs import who_lookup as who
    client = who.find_userbot()
    if client is None:
      return _remember_userbot(user_id, "unknown", None)
    kind, value = await asyncio.wait_for(
      who.resolve_user_id(client, int(user_id)),
      timeout=_USERBOT_WAIT,
    )
  except Exception:
    return _remember_userbot(user_id, "unknown", None)
  if kind == "missing":
    return _remember_userbot(user_id, "missing", None)
  if kind != "person" or value is None:
    return _remember_userbot(user_id, "unknown", None)
  if bool(getattr(value, "is_bot", False)):
    return _remember_userbot(user_id, "bot", None)
  first = getattr(value, "first_name", None)
  last = getattr(value, "last_name", None)
  if getattr(value, "deleted", False) and not str(first or "").strip() and not str(last or "").strip():
    first = "Удалённый аккаунт"
  person = _identity_rules().person_from_user_fields(
    getattr(value, "user_id", user_id),
    first,
    last,
    getattr(value, "username", None),
    is_bot=False,
  )
  if not person:
    return _remember_userbot(user_id, "unknown", None)
  return _remember_userbot(user_id, "person", person)


def _named_person(person: Optional[dict], user_id: int) -> Optional[dict]:
  if not person:
    return None
  if _identity_rules().name_is_placeholder(person.get("first_name"), user_id):
    return None
  return person


async def _unseen_account_is_real(user_id: int) -> bool:
  """Telegram не показал человека, но и не сказал, что id фальшивый."""
  kind, person = await _ask_userbot(user_id)
  if kind == "person" and person:
    return True
  if kind in ("missing", "bot"):
    return False
  return bool(_identity_rules().account_id_can_be_saved(user_id))


async def describe_telegram_user(
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
) -> Optional[dict]:
  """Имя из Telegram.

  Сначала getChat: бот получает человека, которого уже видел.
  Потом users.getUsers у юзербота — Telegram отвечает User или UserEmpty.
  getChatMember только в чате команды и только если имени ещё нет:
  для участника группы это успешный ответ с именем, для чужого —
  PARTICIPANT_ID_INVALID, и это не повод решать, что аккаунта нет.
  """
  if user_id <= 0:
    return None
  rules = _identity_rules()
  bot = _bot()
  chat = None
  try:
    chat = await bot.get_chat(user_id)
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return None
  if chat is not None and bool(getattr(chat, "is_bot", False)):
    return None
  private = _person_from_telegram_object(chat, private_only=True) if chat is not None else None
  named = _named_person(private, user_id)
  if named:
    return named
  kind, via_user = await _ask_userbot(user_id)
  if kind in ("missing", "bot") and private is None:
    return None
  richer = _named_person(via_user, user_id)
  if richer:
    return richer
  seen_in_chat = private
  # Один чат команды, не все группы проекта: иначе Telegram на каждого
  # отсутствующего отвечает PARTICIPANT_ID_INVALID.
  chats = probe_chat_ids(source_chat_id)[:1]
  for cid in chats:
    member, err = await inspect_chat_member(cid, user_id)
    if err == "invalid_user":
      return None
    if member is None:
      continue
    member_user = getattr(member, "user", None)
    if member_user is not None and bool(getattr(member_user, "is_bot", False)):
      return None
    person = _person_from_telegram_object(member_user, private_only=False)
    if _named_person(person, user_id):
      return person
    if person and seen_in_chat is None:
      seen_in_chat = person
  if seen_in_chat:
    return seen_in_chat
  if via_user:
    return via_user
  return rules.profile_when_telegram_is_silent(user_id, telegram_denied=False)


# Юзербот спрашивает Telegram по username. Ответ обычно за доли секунды,
# но короткий FloodWait Telethon ждёт молча, поэтому ждём не дольше этого.
_USERNAME_WAIT = 6.0
_MISS_MEMORY = 600.0
_username_miss: dict[str, tuple[float, str, str]] = {}


def _username_key(username: Any) -> str:
  return str(username or "").strip().lstrip("@").casefold()


def _miss(username: str, kind: str, detail: str = "") -> tuple[str, Optional[dict]]:
  now = time.time()
  _username_miss[_username_key(username)] = (now, kind, detail)
  if len(_username_miss) > 2000:
    for key, item in list(_username_miss.items()):
      if now - item[0] > _MISS_MEMORY:
        _username_miss.pop(key, None)
  return kind, None


def username_miss(username: str) -> tuple[str, str]:
  """Почему по username не нашёлся человек: (вид, подробность).

  missing — в Telegram такого username нет. place — это канал или группа.
  bot — это бот. flood и unknown — Telegram сейчас не ответил.
  Пустой вид — Telegram об этом username не спрашивали.
  """
  item = _username_miss.get(_username_key(username))
  if not item or time.time() - item[0] > _MISS_MEMORY:
    return "", ""
  return item[1], item[2]


def _userbot_person(value: Any, username: str) -> tuple[str, Optional[dict]]:
  if value is None:
    return _miss(username, "unknown")
  if bool(getattr(value, "is_bot", False)):
    return _miss(username, "bot")
  person = _identity_rules().person_from_user_fields(
    getattr(value, "user_id", None),
    getattr(value, "first_name", None),
    getattr(value, "last_name", None),
    getattr(value, "username", None) or username,
    is_bot=False,
  )
  if not person:
    return _miss(username, "unknown")
  _username_miss.pop(_username_key(username), None)
  return "person", person


async def _username_from_telegram(clean: str, budget: Any, who: Any) -> tuple[str, Any]:
  """Сначала юзербот: только он видит людей по username. Потом Bot API для каналов и групп."""
  kind, value = "unknown", None
  client = who.find_userbot()
  wait = budget.paused_for(time.monotonic())
  if wait > 0:
    kind, value = "flood", int(wait)
  elif client is not None:
    budget.spend(0, time.monotonic())
    try:
      kind, value = await asyncio.wait_for(
        who.resolve_with_userbot(client, clean),
        timeout=_USERNAME_WAIT,
      )
    except Exception:
      kind, value = "unknown", None
    if kind == "flood":
      budget.pause(float(value or 60), time.monotonic())
    elif kind in ("person", "place", "missing"):
      budget.remember(clean, kind, value, time.monotonic())
      return kind, value

  try:
    chat = await asyncio.wait_for(_bot().get_chat(f"@{clean}"), timeout=_USERNAME_WAIT)
  except Exception:
    chat = None
  found = who.from_bot_chat(chat) if chat is not None else None
  if isinstance(found, who.TgPerson):
    budget.remember(clean, "person", found, time.monotonic())
    return "person", found
  if isinstance(found, who.TgPlace):
    budget.remember(clean, "place", found, time.monotonic())
    return "place", found
  return kind, value


async def find_telegram_username(username: str) -> tuple[str, Optional[dict]]:
  """Человек по username прямо из Telegram, даже если в Куте его ещё нет.

  ("person", словарь для users) — нашёлся человек.
  ("missing" | "place" | "bot" | "flood" | "unknown", None) — человека нет
  или Telegram не ответил. Причину потом отдаёт username_miss().
  Ответы помнятся в том же кэше, что у «кто ты»: Telegram спрашивается редко.
  """
  clean = _identity_rules().normalize_username(username)
  if not clean:
    return _miss(username, "missing")
  from bot.funcs import who_lookup as who
  budget = who.USERNAME_BUDGET
  hit = budget.cached(clean, time.monotonic())
  kind, value = hit if hit is not None else await _username_from_telegram(clean, budget, who)
  if kind == "person":
    return _userbot_person(value, clean)
  if kind == "place":
    return _miss(clean, "place", str(getattr(value, "kind", "") or ""))
  if kind == "flood":
    return _miss(clean, "flood", str(int(value or 0)))
  if kind == "missing":
    return _miss(clean, "missing")
  return _miss(clean, "unknown")


async def describe_telegram_username(username: str) -> Optional[dict]:
  kind, person = await find_telegram_username(username)
  return person if kind == "person" else None


_MISS_HEAD = "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "


def username_miss_html(username: str, fallback: str) -> str:
  """Ответ админу, когда по username никого не нашли. Без причины — прежний текст."""
  kind, detail = username_miss(username)
  name = escape(str(username or "").strip().lstrip("@"))
  if kind == "missing":
    return (
      _MISS_HEAD + f"Пользователь <code>@{name}</code> не найден</b>\n"
      "<blockquote><i>В Telegram нет такого username. Проверьте написание, "
      "укажите ID или ответьте на сообщение нарушителя.</i></blockquote>"
    )
  if kind == "place":
    what = "канал" if detail == "channel" else "группа"
    return (
      _MISS_HEAD + f"<code>@{name}</code> — это {what}, а не человек</b>\n"
      "<blockquote><i>Укажите username самого нарушителя или ответьте на его сообщение.</i></blockquote>"
    )
  if kind == "bot":
    return (
      _MISS_HEAD + f"<code>@{name}</code> — это бот, а не человек</b>\n"
      "<blockquote><i>Наказания выдаются людям. Укажите username нарушителя "
      "или ответьте на его сообщение.</i></blockquote>"
    )
  if kind == "flood":
    minutes = max(1, (int(detail or 0) + 59) // 60)
    return (
      _MISS_HEAD + f"Не получилось проверить <code>@{name}</code> в Telegram</b>\n"
      f"<blockquote><i>Telegram попросил подождать {minutes} мин. Пока укажите ID "
      "или ответьте на сообщение нарушителя.</i></blockquote>"
    )
  if kind == "unknown":
    return (
      _MISS_HEAD + f"Не получилось проверить <code>@{name}</code> в Telegram</b>\n"
      "<blockquote><i>Telegram сейчас не ответил. Повторите команду через минуту, "
      "укажите ID или ответьте на сообщение нарушителя.</i></blockquote>"
    )
  return fallback


async def ensure_punishment_profile(
  user_id: int,
  *,
  first_name: Optional[str] = None,
  last_name: Optional[str] = None,
  username: Optional[str] = None,
  source_chat_id: Optional[int] = None,
  from_telegram: bool = False,
) -> Optional[Tuple[int, str, Optional[str]]]:
  """Строка users перед наказанием.

  Если человека нет в Куте, имя берётся из Telegram и записывается.
  Уже известное имя не перезаписывается и Telegram повторно не спрашивается.
  None — Telegram прямо отказал в этом id, либо это короткое число, не аккаунт.
  """
  rules = _identity_rules()
  uid = int(user_id or 0)
  in_db, stored_name, stored_username = await _stored_user(uid)
  passed_username = rules.normalize_username(username) or stored_username
  if in_db and not rules.needs_telegram_profile(True, stored_name, uid):
    return uid, stored_name, passed_username or None

  handed = None
  if from_telegram and uid > 0:
    handed = rules.person_from_user_fields(
      uid, first_name, last_name, username, is_bot=False,
    )
  person = None
  if handed and not rules.name_is_placeholder(handed["first_name"], uid):
    person = handed
  elif uid > 0:
    person = await describe_telegram_user(uid, source_chat_id=source_chat_id)
  elif username:
    person = await describe_telegram_username(username)

  if person is None and handed is not None:
    person = handed
  if person is None:
    if in_db:
      label = " ".join(str(stored_name or "").split()) or str(uid)
      return uid, label, passed_username or None
    return None
  try:
    await _adopt_person(person)
  except Exception:
    pass
  return int(person["user_id"]), person["first_name"], person.get("username") or passed_username


async def reject_invalid_target_reply(
  message: Any,
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
  debug_tag: str = "invalid_user",
) -> bool:
  """
  План Б на шаге пруфа/финализации: если цель недействительна ответ админу.

  Returns True, если цель отклонена (вызывающий код должен прервать обработку).
  """
  if user_id <= 0:
    err = "пользователь не найден в Telegram"
  else:
    err = await validate_punishment_target_user(
      user_id, source_chat_id=source_chat_id,
    )
  if not err:
    return False
  from bot.admins.mute import NO_PREVIEW, _debug_hint

  try:
    await message.reply(
      punishment_invalid_user_html(user_id) + _debug_hint(debug_tag),
      parse_mode="HTML",
      link_preview_options=NO_PREVIEW,
    )
  except Exception:
    pass
  return True
