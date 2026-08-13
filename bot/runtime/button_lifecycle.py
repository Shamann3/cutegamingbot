# -*- coding: utf-8 -*-
"""
Button Lifecycle (BLC) — единая система жизни всех inline-кнопок.

Зачем:
  Telegram хранит клавиатуру на сообщении. Сессии/токены — в памяти бота.
  После рестарта без BLC кнопки «живые» в UI, но callback_data никуда не ведёт.

Что делает BLC (одно целое с pkl + Мэджик):
  1) CAPTURE  — автоматически запоминает каждое сообщение с inline-клавиатурой
                (через Bot session middleware: send/edit/…).
  2) PAYLOADS — дублирует opaque-токены (greq/prep/spd/skipcb/srq/…) в durable
                pkl-стор с write-through → переживают .r / деплой.
  3) HYDRATE  — на клике, если основной стор пуст, поднимает payload из BLC
                обратно в PREP/GIFT/… → handler снова работает.
  4) RAISE    — после старта/handoff мягко обновляет reply_markup через Telegram
                (editMessageReplyMarkup) у недавних сообщений — «будит» кнопки.
  5) ORPHAN   — последний шанс: обновить клавиатуру сообщения и сказать
                «нажмите ещё раз», вместо вечного спиннера.

Не заменяет Мэджик (антиспам/answer) и не заменяет игровые handler'ы.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("button_lifecycle")

# ── opaque callback prefixes → имя стора в main/pkl ──
OPAQUE_PREFIX_TO_STORE: Dict[str, str] = {
    "greq": "GIFT_CALLBACK_ACTIONS",
    "prep": "PREP_CALLBACK_ACTIONS",
    "skipcb": "SKIP_CALLBACK_ACTIONS",
    "spd": "SPEEDCONC_CALLBACK_ACTIONS",
    "srq": "SEND_REQUEST_ACTIONS",
    "ggsr": "GIFTGIFT_SEND_REQUEST_ACTIONS",
}

# Методы Telegram, после которых нужно запомнить клавиатуру
_CAPTURE_METHODS = frozenset({
    "SendMessage",
    "SendPhoto",
    "SendAnimation",
    "SendSticker",
    "SendDocument",
    "SendVideo",
    "SendVoice",
    "SendAudio",
    "SendVideoNote",
    "CopyMessage",
    "EditMessageText",
    "EditMessageCaption",
    "EditMessageReplyMarkup",
    "EditMessageMedia",
})

_INDEX_TTL_SEC = 7 * 24 * 3600
_PAYLOAD_TTL_SEC = 7 * 24 * 3600
_RAISE_MAX_MESSAGES = 40
_RAISE_MAX_AGE_SEC = 48 * 3600
_RAISE_DELAY_SEC = 0.08
_MAX_INDEX_ENTRIES = 8000

_installed_bots: Set[int] = set()
_raise_lock = asyncio.Lock()
_last_raise_mono: float = 0.0


def _lazy(name: str):
    from bot.db_create.pklcode import LazyGameStore

    return LazyGameStore(name)


# Durable индексы (создаются лениво)
def _messages() -> Any:
    return _lazy("blc_messages")


def _payloads() -> Any:
    return _lazy("blc_payloads")


def _token_index() -> Any:
    return _lazy("blc_token_index")


# ══════════════════════════════════════════════════════════
# Policy / pkl
# ══════════════════════════════════════════════════════════

_CRITICAL_STORES: Set[str] = {
    "blc_messages",
    "blc_payloads",
    "blc_token_index",
    "PREP_CALLBACK_ACTIONS",
    "GIFT_CALLBACK_ACTIONS",
    "SKIP_CALLBACK_ACTIONS",
    "SPEEDCONC_CALLBACK_ACTIONS",
    "SEND_REQUEST_ACTIONS",
    "GIFTGIFT_SEND_REQUEST_ACTIONS",
    "session_data",
    "user_to_session",
    "gamesorelinline",
    "button_inlinegamesorel",
    "gamesmine_inmine",
    "games_memory_inline",
    "rps_games",
    "inline_game_scah",
    "tic_tac_toe_games",
    "game_roulettinduel",
    "gamesorel",
    "button_gamesorel",
    "gamessha",
    "button_gamessha",
    "gamesmine",
    "button_gamesmine",
    "gamesbingo",
    "button_bingo",
    "games_memory",
    "button_memory",
    "gamesknb",
    "button_gamesknb",
    "games_roulett",
    "button_roulett",
    "gamesruletka",
    "button_gamesruletka",
    "gameskosti",
    "button_kosti",
    "games_tictactoe",
    "button_games_tictactoe",
    "tank_active_games",
    "button_tank_active_games",
    "user_messagetank",
    "active_games_plate",
    "button_active_games_plate",
    "user_message_plate",
    "active_games_risk",
    "button_active_games_risk",
    "user_message_risk",
    "bombs_user_game_data",
    "button_bombs_user_game_data",
}


def install_pkl_policy() -> int:
    """Write-through + длинный TTL для всех критичных сторов кнопок."""
    try:
        from bot.db_create import pklcode as P
    except Exception as e:
        logger.warning("pkl import: %r", e)
        return 0

    n = 0
    for name in _CRITICAL_STORES:
        try:
            P.register_store_write_through(name, True)
            P.register_store_expiry(name, float(_INDEX_TTL_SEC))
            n += 1
        except Exception as e:
            logger.warning("policy %s: %r", name, e)

    # Авто-расширение: любые уже живые GameStore button_*/games*
    try:
        for sname, inst in list(getattr(P.GameStore, "_instances", {}).items()):
            if sname in _CRITICAL_STORES:
                continue
            if str(sname).startswith(("button_", "games", "GIFT", "PREP", "SKIP", "SPEED", "SEND_")):
                P.register_store_write_through(sname, True)
                P.register_store_expiry(sname, float(_INDEX_TTL_SEC))
                n += 1
    except Exception:
        pass
    return n


def _persist_store(store: Any) -> None:
    try:
        from bot.db_create import pklcode as P

        inner = store._load() if hasattr(store, "_load") else store
        name = getattr(inner, "name", None) or "blc"
        if hasattr(inner, "_write_through_save"):
            P._io_submit(str(name), inner._write_through_save, wait=False)
        elif hasattr(inner, "save"):
            inner.save()
    except Exception as e:
        logger.debug("persist_store: %r", e)


# ══════════════════════════════════════════════════════════
# Markup helpers
# ══════════════════════════════════════════════════════════

def _btn_has_web_app(btn: Any) -> bool:
    """WebApp / Mini App кнопки — НЕ трогаем (они и так работают)."""
    if btn is None:
        return False
    try:
        if isinstance(btn, dict):
            return bool(btn.get("web_app"))
        return bool(getattr(btn, "web_app", None))
    except Exception:
        return False


def markup_has_web_app(markup: Any) -> bool:
    if markup is None:
        return False
    try:
        rows = getattr(markup, "inline_keyboard", None)
        if rows is None and isinstance(markup, dict):
            rows = markup.get("inline_keyboard")
        for row in rows or []:
            for btn in row or []:
                if _btn_has_web_app(btn):
                    return True
    except Exception:
        return False
    return False


def spec_has_web_app(spec: Any) -> bool:
    if not spec:
        return False
    try:
        for row in spec:
            for btn in row or []:
                if isinstance(btn, dict) and btn.get("web_app"):
                    return True
    except Exception:
        return False
    return False


def markup_to_spec(markup: Any) -> Optional[List[List[Dict[str, Any]]]]:
    """Сериализуемый снимок inline-клавиатуры (без Magic-классов).

    Клавиатуры с WebApp намеренно НЕ сохраняем — raise мог бы их сломать.
    """
    if markup is None:
        return None
    if markup_has_web_app(markup):
        return None
    try:
        rows = getattr(markup, "inline_keyboard", None)
        if rows is None and isinstance(markup, dict):
            rows = markup.get("inline_keyboard")
        if not rows:
            return None
        out: List[List[Dict[str, Any]]] = []
        for row in rows:
            out_row: List[Dict[str, Any]] = []
            for btn in row:
                if btn is None:
                    continue
                if _btn_has_web_app(btn):
                    return None  # смешанная клавиатура с WebApp — не трогаем
                if hasattr(btn, "model_dump"):
                    d = btn.model_dump(mode="python", exclude_none=True)
                elif isinstance(btn, dict):
                    d = dict(btn)
                else:
                    d = {
                        "text": getattr(btn, "text", "") or "",
                        "callback_data": getattr(btn, "callback_data", None),
                        "url": getattr(btn, "url", None),
                        "switch_inline_query": getattr(btn, "switch_inline_query", None),
                        "switch_inline_query_current_chat": getattr(
                            btn, "switch_inline_query_current_chat", None
                        ),
                        "style": getattr(btn, "style", None),
                        "icon_custom_emoji_id": getattr(btn, "icon_custom_emoji_id", None),
                    }
                # WebApp никогда не кладём в spec
                d.pop("web_app", None)
                clean = {k: v for k, v in d.items() if v is not None and k != "pay"}
                if clean.get("text") is not None or clean.get("callback_data"):
                    out_row.append(clean)
            if out_row:
                out.append(out_row)
        return out or None
    except Exception as e:
        logger.debug("markup_to_spec: %r", e)
        return None


def spec_to_markup(spec: Any):
    """Собрать InlineKeyboardMarkup из spec."""
    if not spec:
        return None
    # Не восстанавливаем клавиатуры с WebApp — Mini App не трогаем
    if spec_has_web_app(spec):
        return None
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        rows = []
        for row in spec:
            btns = []
            for d in row:
                if not isinstance(d, dict):
                    continue
                if d.get("web_app"):
                    return None
                kwargs = {k: v for k, v in d.items() if v is not None}
                # WebApp / служебное — выкидываем всегда
                kwargs.pop("web_app", None)
                for bad in ("copy_text", "login_url", "callback_game"):
                    if bad in kwargs and not kwargs[bad]:
                        kwargs.pop(bad, None)
                try:
                    btns.append(InlineKeyboardButton(**kwargs))
                except Exception:
                    cd = kwargs.get("callback_data")
                    url = kwargs.get("url")
                    text = str(kwargs.get("text") or "·")
                    if url:
                        btns.append(InlineKeyboardButton(text=text, url=str(url)))
                    elif cd:
                        btns.append(InlineKeyboardButton(text=text, callback_data=str(cd)[:64]))
            if btns:
                rows.append(btns)
        if not rows:
            return None
        return InlineKeyboardMarkup(inline_keyboard=rows)
    except Exception as e:
        logger.debug("spec_to_markup: %r", e)
        return None


def _extract_callbacks(spec: Optional[List[List[Dict[str, Any]]]]) -> List[str]:
    out: List[str] = []
    if not spec:
        return out
    for row in spec:
        for btn in row:
            cd = btn.get("callback_data") if isinstance(btn, dict) else None
            if cd:
                out.append(str(cd))
    return out


def _parse_opaque(callback_data: str) -> Optional[Tuple[str, str]]:
    data = str(callback_data or "")
    if ":" not in data:
        return None
    prefix, token = data.split(":", 1)
    prefix = prefix.strip()
    token = token.strip()
    if prefix in OPAQUE_PREFIX_TO_STORE and token:
        return prefix, token
    return None


def message_key(
    *,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    inline_message_id: Optional[str] = None,
) -> Optional[str]:
    if inline_message_id:
        return f"i:{inline_message_id}"
    if chat_id is not None and message_id is not None:
        return f"m:{int(chat_id)}:{int(message_id)}"
    return None


# ══════════════════════════════════════════════════════════
# Remember / tokens
# ══════════════════════════════════════════════════════════

def remember_token(
    *,
    store_name: str,
    token: str,
    payload: Dict[str, Any],
    prefix: Optional[str] = None,
    msg_key: Optional[str] = None,
) -> None:
    """Durable копия opaque-токена + обратный индекс."""
    token = str(token or "").strip()
    if not token or not store_name:
        return
    now = time.time()
    key = f"{store_name}:{token}"
    try:
        _payloads()[key] = {
            "store": str(store_name),
            "token": token,
            "prefix": prefix,
            "payload": dict(payload or {}),
            "msg_key": msg_key,
            "ts": now,
        }
        _persist_store(_payloads())
        if prefix:
            _token_index()[f"{prefix}:{token}"] = {
                "store": str(store_name),
                "token": token,
                "msg_key": msg_key,
                "ts": now,
            }
            _persist_store(_token_index())
    except Exception as e:
        logger.warning("remember_token: %r", e)


def remember_message(
    *,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    inline_message_id: Optional[str] = None,
    markup: Any = None,
    markup_spec: Any = None,
    kind: str = "auto",
    store_keys: Optional[List[str]] = None,
    raise_on_boot: bool = True,
) -> Optional[str]:
    """Запомнить сообщение с inline-кнопками."""
    spec = markup_spec if markup_spec is not None else markup_to_spec(markup)
    if not spec:
        return None
    key = message_key(
        chat_id=chat_id,
        message_id=message_id,
        inline_message_id=inline_message_id,
    )
    if not key:
        return None

    callbacks = _extract_callbacks(spec)
    opaque: List[Dict[str, str]] = []
    for cd in callbacks:
        parsed = _parse_opaque(cd)
        if parsed:
            prefix, token = parsed
            opaque.append({"prefix": prefix, "token": token, "store": OPAQUE_PREFIX_TO_STORE[prefix]})
            # связать токен с сообщением
            try:
                idx = _token_index().get(f"{prefix}:{token}")
                if isinstance(idx, dict):
                    idx = dict(idx)
                    idx["msg_key"] = key
                    _token_index()[f"{prefix}:{token}"] = idx
                pk = f"{OPAQUE_PREFIX_TO_STORE[prefix]}:{token}"
                row = _payloads().get(pk)
                if isinstance(row, dict):
                    row = dict(row)
                    row["msg_key"] = key
                    _payloads()[pk] = row
            except Exception:
                pass

    rec = {
        "key": key,
        "chat_id": int(chat_id) if chat_id is not None else None,
        "message_id": int(message_id) if message_id is not None else None,
        "inline_message_id": str(inline_message_id) if inline_message_id else None,
        "kind": str(kind or "auto"),
        "markup_spec": spec,
        "callbacks": callbacks[:64],
        "opaque": opaque,
        "store_keys": list(store_keys or [])[:32],
        "raise_on_boot": bool(raise_on_boot),
        "ts": time.time(),
    }
    try:
        _messages()[key] = rec
        _persist_store(_messages())
        _maybe_prune_messages()
    except Exception as e:
        logger.warning("remember_message: %r", e)
        return None
    return key


def forget_message(
    *,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    inline_message_id: Optional[str] = None,
) -> None:
    key = message_key(
        chat_id=chat_id,
        message_id=message_id,
        inline_message_id=inline_message_id,
    )
    if not key:
        return
    try:
        _messages().pop(key, None)
        _persist_store(_messages())
    except Exception:
        pass


def _maybe_prune_messages() -> None:
    """Не раздувать индекс бесконечно."""
    try:
        store = _messages()
        n = len(store)
        if n <= _MAX_INDEX_ENTRIES:
            return
        items = []
        for k, v in list(store.items()):
            ts = float((v or {}).get("ts", 0) or 0) if isinstance(v, dict) else 0.0
            items.append((ts, k))
        items.sort()
        drop = max(0, n - int(_MAX_INDEX_ENTRIES * 0.85))
        for _, k in items[:drop]:
            store.pop(k, None)
        _persist_store(store)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# Hydrate / resurrect
# ══════════════════════════════════════════════════════════

def _get_live_store(store_name: str) -> Any:
    """Достать живой LazyGameStore/GameStore из main или создать Lazy."""
    try:
        import main as M

        for attr in (
            "PREP_CALLBACK_ACTIONS",
            "GIFT_CALLBACK_ACTIONS",
            "SKIP_CALLBACK_ACTIONS",
            "SPEEDCONC_CALLBACK_ACTIONS",
            "SEND_REQUEST_ACTIONS",
            "GIFTGIFT_SEND_REQUEST_ACTIONS",
            "session_data",
            "user_to_session",
        ):
            if attr == store_name and hasattr(M, attr):
                return getattr(M, attr)
    except Exception:
        pass
    try:
        import bot.config.config as cfg

        if store_name == "GIFTGIFT_SEND_REQUEST_ACTIONS" and hasattr(cfg, store_name):
            return getattr(cfg, store_name)
    except Exception:
        pass
    return _lazy(store_name)


def hydrate_opaque_callback(callback_data: str) -> Dict[str, Any]:
    """
    Если opaque-токен пропал из основного стора — поднять из blc_payloads.
    Возвращает {ok, hydrated, store, token, prefix}.
    """
    out: Dict[str, Any] = {"ok": False, "hydrated": False}
    parsed = _parse_opaque(callback_data)
    if not parsed:
        out["ok"] = True  # не opaque — не наше дело
        return out
    prefix, token = parsed
    store_name = OPAQUE_PREFIX_TO_STORE[prefix]
    out.update({"prefix": prefix, "token": token, "store": store_name})

    live = _get_live_store(store_name)
    try:
        if token in live:
            out["ok"] = True
            return out
    except Exception:
        pass

    # durable backup
    row = None
    try:
        row = _payloads().get(f"{store_name}:{token}")
    except Exception:
        row = None
    if not isinstance(row, dict):
        # try token_index → payloads
        try:
            idx = _token_index().get(f"{prefix}:{token}")
            if isinstance(idx, dict):
                row = _payloads().get(f"{idx.get('store')}:{idx.get('token')}")
        except Exception:
            pass

    if not isinstance(row, dict):
        return out

    payload = row.get("payload")
    if not isinstance(payload, dict):
        return out

    # TTL check
    try:
        ts = float(row.get("ts", 0) or 0)
        if ts > 0 and (time.time() - ts) > _PAYLOAD_TTL_SEC:
            return out
    except Exception:
        pass

    try:
        live[token] = dict(payload)
        _persist_store(live)
        out["ok"] = True
        out["hydrated"] = True
        print(
            f"[BLC] hydrate {prefix}:{token[:12]}… → {store_name}",
            flush=True,
        )
    except Exception as e:
        out["error"] = repr(e)
    return out


async def refresh_message_markup(
    bot: Any,
    *,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    inline_message_id: Optional[str] = None,
    rec: Optional[Dict[str, Any]] = None,
) -> bool:
    """Поднять кнопки на сообщении через Telegram editReplyMarkup."""
    if rec is None:
        key = message_key(
            chat_id=chat_id,
            message_id=message_id,
            inline_message_id=inline_message_id,
        )
        if not key:
            return False
        try:
            rec = _messages().get(key)
        except Exception:
            rec = None
    if not isinstance(rec, dict):
        return False

    markup = spec_to_markup(rec.get("markup_spec"))
    if markup is None:
        return False

    try:
        imid = rec.get("inline_message_id") or inline_message_id
        if imid:
            await bot.edit_message_reply_markup(
                inline_message_id=str(imid),
                reply_markup=markup,
            )
            return True
        cid = rec.get("chat_id") if rec.get("chat_id") is not None else chat_id
        mid = rec.get("message_id") if rec.get("message_id") is not None else message_id
        if cid is None or mid is None:
            return False
        await bot.edit_message_reply_markup(
            chat_id=int(cid),
            message_id=int(mid),
            reply_markup=markup,
        )
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "message to edit not found" in err or "message identifier" in err:
            forget_message(
                chat_id=rec.get("chat_id"),
                message_id=rec.get("message_id"),
                inline_message_id=rec.get("inline_message_id"),
            )
        logger.debug("refresh_message_markup: %r", e)
        return False


async def handle_callback_preflight(query: Any) -> Dict[str, Any]:
    """
    Вызывать до handler'ов (middleware): hydrate opaque + при необходимости
    refresh markup сообщения.
    """
    out: Dict[str, Any] = {"hydrated": False, "refreshed": False}
    data = str(getattr(query, "data", "") or "")
    if not data:
        return out

    hyd = hydrate_opaque_callback(data)
    out["hydrate"] = hyd
    out["hydrated"] = bool(hyd.get("hydrated"))

    # привязка к сообщению клика
    msg = getattr(query, "message", None)
    chat_id = None
    message_id = None
    inline_message_id = getattr(query, "inline_message_id", None)
    if msg is not None:
        try:
            chat_id = int(msg.chat.id)
            message_id = int(msg.message_id)
        except Exception:
            pass

    # если hydrate не удался для opaque — попробуем поднять markup
    if hyd.get("prefix") and not hyd.get("ok"):
        bot = getattr(query, "bot", None)
        if bot is not None:
            ok = await refresh_message_markup(
                bot,
                chat_id=chat_id,
                message_id=message_id,
                inline_message_id=inline_message_id,
            )
            out["refreshed"] = bool(ok)
            if ok:
                out["ask_retry"] = True
    return out


async def handle_orphan_callback(query: Any) -> bool:
    """
    Последний шанс для callback без handler.
    True = мы ответили пользователю (не нужен пустой answer снаружи).
    """
    data = str(getattr(query, "data", "") or "")
    # сначала hydrate — вдруг handler не сматчился из-за пустого стора
    hyd = hydrate_opaque_callback(data)
    if hyd.get("hydrated"):
        # токен поднят — попросим нажать ещё раз (handler уже прошёл мимо)
        try:
            await query.answer(
                "♻️ Кнопки восстановлены после перезапуска.\nНажмите ещё раз.",
                show_alert=True,
            )
        except Exception:
            try:
                await query.answer()
            except Exception:
                pass
        # и обновим markup на всякий случай
        bot = getattr(query, "bot", None)
        msg = getattr(query, "message", None)
        if bot is not None and msg is not None:
            try:
                await refresh_message_markup(
                    bot,
                    chat_id=int(msg.chat.id),
                    message_id=int(msg.message_id),
                    inline_message_id=getattr(query, "inline_message_id", None),
                )
            except Exception:
                pass
        return True

    bot = getattr(query, "bot", None)
    msg = getattr(query, "message", None)
    refreshed = False
    if bot is not None:
        try:
            refreshed = await refresh_message_markup(
                bot,
                chat_id=int(msg.chat.id) if msg is not None else None,
                message_id=int(msg.message_id) if msg is not None else None,
                inline_message_id=getattr(query, "inline_message_id", None),
            )
        except Exception:
            refreshed = False

    try:
        if refreshed:
            await query.answer(
                "♻️ Кнопки обновлены.\nНажмите нужную ещё раз.",
                show_alert=True,
            )
        else:
            await query.answer(
                "⏳ Кнопка устарела после перезапуска.\nОткройте меню заново.",
                show_alert=True,
            )
    except Exception:
        try:
            await query.answer()
        except Exception:
            pass
    return True


# ══════════════════════════════════════════════════════════
# Capture middleware (Bot session)
# ══════════════════════════════════════════════════════════

def _markup_from_method(method: Any) -> Any:
    return getattr(method, "reply_markup", None)


def _capture_result(method: Any, result: Any) -> None:
    markup = _markup_from_method(method)
    if markup is None:
        return
    spec = markup_to_spec(markup)
    if not spec:
        return

    chat_id = None
    message_id = None
    inline_message_id = getattr(method, "inline_message_id", None)

    # результат Message
    if result is not None and hasattr(result, "message_id"):
        try:
            message_id = int(result.message_id)
            chat_id = int(result.chat.id) if getattr(result, "chat", None) else None
        except Exception:
            pass

    # edit без Message в ответе — берём из method
    if message_id is None:
        try:
            if getattr(method, "message_id", None) is not None:
                message_id = int(method.message_id)
            if getattr(method, "chat_id", None) is not None:
                chat_id = int(method.chat_id)
        except Exception:
            pass

    if not inline_message_id and chat_id is None:
        return

    remember_message(
        chat_id=chat_id,
        message_id=message_id,
        inline_message_id=str(inline_message_id) if inline_message_id else None,
        markup_spec=spec,
        kind="auto",
        raise_on_boot=True,
    )


try:
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware as _BaseReqMw
except Exception:  # pragma: no cover
    _BaseReqMw = object  # type: ignore


class ButtonLifecycleCaptureMiddleware(_BaseReqMw):
    """Захват каждой отправленной/отредактированной inline-клавиатуры."""

    async def __call__(self, make_request, bot, method):
        result = await make_request(bot, method)
        try:
            name = method.__class__.__name__
            if name in _CAPTURE_METHODS:
                _capture_result(method, result)
        except Exception as e:
            logger.debug("capture: %r", e)
        return result


# ══════════════════════════════════════════════════════════
# Callback preflight middleware (Dispatcher)
# ══════════════════════════════════════════════════════════

try:
    from aiogram import BaseMiddleware as _BaseMw
except Exception:  # pragma: no cover
    _BaseMw = object  # type: ignore


class ButtonLifecycleCallbackMiddleware(_BaseMw):
    """outer middleware: hydrate opaque tokens перед handler'ами."""

    async def __call__(self, handler, event, data):
        try:
            from aiogram.types import CallbackQuery

            if isinstance(event, CallbackQuery):
                await handle_callback_preflight(event)
        except Exception as e:
            logger.debug("preflight: %r", e)
        return await handler(event, data)


# ══════════════════════════════════════════════════════════
# Raise after restart
# ══════════════════════════════════════════════════════════

async def raise_buttons_after_restart(
    bot: Any,
    *,
    reason: str = "boot",
    max_messages: int = _RAISE_MAX_MESSAGES,
    max_age_sec: float = _RAISE_MAX_AGE_SEC,
) -> Dict[str, Any]:
    """
    Через Telegram «поднять» недавние inline-клавиатуры.
    Не спамит: лимит сообщений + пауза + только raise_on_boot.
    """
    global _last_raise_mono
    out: Dict[str, Any] = {
        "reason": reason,
        "candidates": 0,
        "raised": 0,
        "failed": 0,
        "skipped": 0,
    }
    async with _raise_lock:
        now_m = time.monotonic()
        if now_m - _last_raise_mono < 3.0 and reason != "manual":
            out["skipped"] = 1
            out["skip_reason"] = "debounce"
            return out
        _last_raise_mono = now_m

        try:
            items = []
            for k, v in list(_messages().items()):
                if not isinstance(v, dict):
                    continue
                if not v.get("raise_on_boot", True):
                    continue
                ts = float(v.get("ts", 0) or 0)
                if ts > 0 and (time.time() - ts) > float(max_age_sec):
                    continue
                if not v.get("markup_spec"):
                    continue
                items.append((ts, k, v))
            items.sort(reverse=True)
            items = items[: max(0, int(max_messages))]
            out["candidates"] = len(items)

            for _, _k, rec in items:
                try:
                    # WebApp / Mini App — пропуск (не edit_reply_markup)
                    if spec_has_web_app(rec.get("markup_spec")):
                        out["skipped"] += 1
                        continue
                    ok = await refresh_message_markup(bot, rec=rec)
                    if ok:
                        out["raised"] += 1
                    else:
                        out["failed"] += 1
                except Exception:
                    out["failed"] += 1
                await asyncio.sleep(_RAISE_DELAY_SEC)
        except Exception as e:
            out["error"] = repr(e)

    print(
        f"[BLC] raise ({reason}): raised={out['raised']} "
        f"fail={out['failed']} cand={out['candidates']}",
        flush=True,
    )
    return out


# ══════════════════════════════════════════════════════════
# Install / protect
# ══════════════════════════════════════════════════════════

def install_on_bot(bot: Any) -> bool:
    """Повесить capture middleware на Bot session."""
    try:
        bid = id(bot)
        if bid in _installed_bots:
            return False
        bot.session.middleware(ButtonLifecycleCaptureMiddleware())
        _installed_bots.add(bid)
        print("✅ [BLC] capture middleware на Bot session", flush=True)
        return True
    except Exception as e:
        print(f"⚠️ [BLC] capture install: {e!r}", flush=True)
        return False


def install_on_dispatcher(dp: Any) -> bool:
    """Повесить hydrate middleware на callback_query."""
    try:
        mw = ButtonLifecycleCallbackMiddleware()
        try:
            dp.callback_query.outer_middleware(mw)
        except Exception:
            dp.callback_query.middleware(mw)
        print("✅ [BLC] callback hydrate middleware на Dispatcher", flush=True)
        return True
    except Exception as e:
        print(f"⚠️ [BLC] callback middleware: {e!r}", flush=True)
        return False


def install(bot: Any = None, dp: Any = None) -> Dict[str, Any]:
    """Полная установка BLC."""
    out: Dict[str, Any] = {"policy": 0}
    out["policy"] = install_pkl_policy()
    if bot is not None:
        out["bot"] = install_on_bot(bot)
    if dp is not None:
        out["dp"] = install_on_dispatcher(dp)
    print(f"✅ [BLC] installed policy={out['policy']}", flush=True)
    return out


def protect_before_restart(*, wait_timeout: float = 12.0) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False}
    try:
        install_pkl_policy()
        # дожать индексы
        for s in (_messages(), _payloads(), _token_index()):
            _persist_store(s)
        from bot.db_create.pklcode import flush_all_stores_for_handoff

        out.update(flush_all_stores_for_handoff(wait_timeout=wait_timeout) or {})
        out["ok"] = int(out.get("failed", 0) or 0) == 0
        print(f"[BLC] before_restart: {out}", flush=True)
    except Exception as e:
        out["error"] = repr(e)
        print(f"[BLC] before_restart FAIL: {e!r}", flush=True)
    return out


def protect_after_start(*, reason: str = "boot", adopt: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {"reason": reason, "policy": 0}
    try:
        out["policy"] = install_pkl_policy()
    except Exception as e:
        out["policy_err"] = repr(e)
    if adopt:
        try:
            from bot.db_create.pklcode import adopt_stores_after_handoff

            out["adopt"] = adopt_stores_after_handoff()
        except Exception as e:
            out["adopt_err"] = repr(e)
    print(f"[BLC] after_start ({reason}): {out}", flush=True)
    return out


async def protect_after_start_async(
    *,
    bot: Any = None,
    dp: Any = None,
    reason: str = "boot",
    adopt: bool = True,
    revive_magic: bool = True,
    # По умолчанию НЕ спамим editReplyMarkup по старым сообщениям:
    # handlers + pkl достаточно; raise только по явному запросу / handoff.
    raise_markups: bool = False,
) -> Dict[str, Any]:
    out = await asyncio.to_thread(protect_after_start, reason=reason, adopt=adopt)

    # КРИТИЧНО: зарегистрировать handlers игр ДО трафика.
    # Без этого kostijoin/… после .r уходят в orphan (модули ленивые).
    try:
        from bot.runtime.callback_bootstrap import ensure_handlers_for_dispatcher

        out["callbacks"] = ensure_handlers_for_dispatcher(dp)
        print(f"[BLC] callback handlers: {out['callbacks']}", flush=True)
    except Exception as e:
        out["callbacks_err"] = repr(e)
        print(f"⚠️ [BLC] callback ensure: {e!r}", flush=True)

    if bot is not None:
        try:
            install_on_bot(bot)
        except Exception:
            pass
    if dp is not None:
        try:
            install_on_dispatcher(dp)
        except Exception:
            pass

    if revive_magic:
        try:
            from bot.magic.install import revive_magic_system

            out["magic"] = await revive_magic_system(
                dp=dp,
                reason=f"blc:{reason}",
                hard=(reason == "handoff"),
                run_audit=False,
            )
        except Exception as e:
            out["magic_err"] = repr(e)

    if raise_markups and bot is not None:
        try:
            # на cold boot тоже поднимаем — но лимитированно
            out["raise"] = await raise_buttons_after_restart(bot, reason=reason)
        except Exception as e:
            out["raise_err"] = repr(e)

    return out


def persist_callback_store(store: Any) -> None:
    """Совместимость с button_survival / main._register_callback_payload."""
    _persist_store(store)


def bind_registered_token(
    store: Any,
    token: str,
    payload: Dict[str, Any],
    *,
    prefix: Optional[str] = None,
) -> None:
    """Вызывать сразу после записи токена в PREP/GIFT/…"""
    store_name = None
    try:
        inner = store._load() if hasattr(store, "_load") else store
        store_name = getattr(inner, "name", None)
    except Exception:
        store_name = None
    if not store_name:
        store_name = "UNKNOWN"
    # угадать prefix по стору
    if not prefix:
        for pfx, sname in OPAQUE_PREFIX_TO_STORE.items():
            if sname == store_name:
                prefix = pfx
                break
    remember_token(
        store_name=str(store_name),
        token=str(token),
        payload=dict(payload or {}),
        prefix=prefix,
    )
    persist_callback_store(store)
