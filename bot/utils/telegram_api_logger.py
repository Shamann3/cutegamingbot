import asyncio
import logging
import sys
import time

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.methods import TelegramMethod

# Кратковременные обрывы до api.telegram.org (ClientConnectorError и т.п.).
# GetUpdates сюда не попадают (_SKIP_METHODS) — у polling свой цикл перезапуска.
_NETWORK_RETRY_ATTEMPTS = 3
_NETWORK_RETRY_BASE_DELAY = 0.45

logger = logging.getLogger("telegram_api")

if not logger.handlers:
    formatter = logging.Formatter(
        "[TG-API %(asctime)s] %(levelname)s %(message)s",
        "%d.%m.%Y %H:%M:%S"
    )

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler("/app/log_telegram_api.txt", encoding="utf-8"))
    except OSError:
        pass

    for h in handlers:
        h.setFormatter(formatter)
        logger.addHandler(h)

    logger.setLevel(logging.INFO)
    logger.propagate = False


# Служебные методы long-polling не логируем (только шум).
_SKIP_METHODS = {"GetUpdates", "GetMe"}

# Ожидаемые (штатные) ошибки Telegram API для некоторых методов:
# их не нужно печатать как traceback на каждый вызов.
_SOFTFAIL_METHODS = {
    "GetChat",
    "GetChatAdministrators",
    "GetChatMemberCount",
    "GetChatMember",
}
_SOFTFAIL_PATTERNS = (
    "chat not found",
    "user not found",
    "bot was kicked from the supergroup chat",
)
_SOFTFAIL_DEBOUNCE_SEC = 180.0
_softfail_last_logged = {}
_SOFTFAIL_MAX_ENTRIES = 2000

# При лаге event loop самолечение глушит шумные START/END логи,
# чтобы sync FileHandler не добивал кнопки.
_quiet_mode = False
_quiet_since = 0.0

# Ответ на callback живёт у Telegram считанные секунды. Просрочка - не сбой
# бота: так бывает при рестарте (в очереди лежат старые нажатия), при клике
# по давнему сообщению и при двойном ответе на один и тот же query.
#
# Ронять на этом обработчик нельзя: `await call.answer()` обычно стоит первой
# строкой, и исключение обрывает всю обработку - человек жмёт кнопку, а экран
# не меняется. Поэтому такую ошибку гасим и возвращаем True, как если бы
# ответ прошёл. Оплату (AnswerPreCheckoutQuery) не трогаем - там ошибка важна.
_STALE_QUERY_METHODS = {"AnswerCallbackQuery", "AnswerInlineQuery"}
_STALE_QUERY_PATTERNS = (
    "query is too old",
    "query id is invalid",
    "query_id_invalid",
    "query is too old and response timeout expired",
    "already answered",
    "query_id_invalid",
)

# AnswerCallbackQuery на критическом пути UX: меньше ретраев и меньше логов.
_FAST_METHODS = {"AnswerCallbackQuery"}
_FAST_NETWORK_RETRY_ATTEMPTS = 2
_FAST_NETWORK_RETRY_BASE_DELAY = 0.2
_stale_query_count = 0

# Ожидаемые ответы Telegram, которые вызывающий код уже умеет разбирать
# (например, «экран и так нужный» или «сообщение успели удалить»).
# Их пробрасываем как обычно, но печатаем одной строкой без traceback -
# иначе штатная ситуация выглядит в логах как авария.
_QUIET_PATTERNS = (
    "message is not modified",
    "message to edit not found",
    "message to delete not found",
    "message can't be deleted",
    "message to be replied not found",
    "message identifier is not specified",
    "bot was blocked by the user",
    "user is deactivated",
    "chat not found",
    "have no rights to send a message",
    "not enough rights",
    "document_invalid",
    "can't parse entities",
)

# Edit уже в нужном виде: для Telegram это BadRequest, для нас - успех.
# Возвращаем True (как у aiogram при частичных edit), без ❌ FAIL и без traceback.
_IDEMPOTENT_EDIT_METHODS = {
    "EditMessageText",
    "EditMessageCaption",
    "EditMessageReplyMarkup",
    "EditMessageMedia",
}
_IDEMPOTENT_OK_PATTERNS = (
    "message is not modified",
)


def _error_text(error: Exception) -> str:
    return str(error).lower()


def _is_quiet_error(error: Exception) -> bool:
    if not isinstance(error, (TelegramBadRequest, TelegramForbiddenError)):
        return False
    text = _error_text(error)
    return any(pattern in text for pattern in _QUIET_PATTERNS)


def _is_idempotent_edit_ok(method_name: str, error: Exception) -> bool:
    if method_name not in _IDEMPOTENT_EDIT_METHODS:
        return False
    if not isinstance(error, TelegramBadRequest):
        return False
    text = _error_text(error)
    return any(pattern in text for pattern in _IDEMPOTENT_OK_PATTERNS)


def _is_softfail_exception(method_name: str, error: Exception) -> bool:
    if method_name not in _SOFTFAIL_METHODS:
        return False

    if not isinstance(error, (TelegramBadRequest, TelegramForbiddenError)):
        return False

    text = str(error).lower()
    return any(pattern in text for pattern in _SOFTFAIL_PATTERNS)


def _is_stale_query(method_name: str, error: Exception) -> bool:
    if method_name not in _STALE_QUERY_METHODS:
        return False
    if not isinstance(error, TelegramBadRequest):
        return False
    text = str(error).lower()
    return any(pattern in text for pattern in _STALE_QUERY_PATTERNS)


def _should_log_softfail_once(signature: str) -> bool:
    now = time.monotonic()
    last_ts = _softfail_last_logged.get(signature, 0.0)
    if (now - last_ts) < _SOFTFAIL_DEBOUNCE_SEC:
        return False
    _softfail_last_logged[signature] = now
    if len(_softfail_last_logged) > _SOFTFAIL_MAX_ENTRIES:
        trim_softfail_cache(keep=_SOFTFAIL_MAX_ENTRIES // 2)
    return True


def trim_softfail_cache(keep: int = 500) -> dict:
    """Чистит разросшийся softfail-кэш (вызывается из button_health)."""
    global _softfail_last_logged
    before = len(_softfail_last_logged)
    if before <= keep:
        return {"before": before, "after": before, "removed": 0}
    # оставляем самые свежие
    newest = sorted(_softfail_last_logged.items(), key=lambda x: x[1], reverse=True)[:keep]
    _softfail_last_logged = dict(newest)
    after = len(_softfail_last_logged)
    return {"before": before, "after": after, "removed": before - after}


def set_quiet_mode(enabled: bool, reason: str = "") -> None:
    """Включает/выключает тихий режим логов API (самолечение кнопок)."""
    global _quiet_mode, _quiet_since
    enabled = bool(enabled)
    if enabled == _quiet_mode:
        return
    _quiet_mode = enabled
    _quiet_since = time.monotonic() if enabled else 0.0
    logger.warning(
        "QUIET_MODE %s %s",
        "ON" if enabled else "OFF",
        f"({reason})" if reason else "",
    )


def is_quiet_mode() -> bool:
    return bool(_quiet_mode)


def _is_network_error(error: Exception) -> bool:
    if isinstance(error, TelegramNetworkError):
        return True
    name = type(error).__name__
    if name in ("ClientConnectorError", "ServerDisconnectedError", "ClientOSError"):
        return True
    text = str(error).lower()
    return (
        "cannot connect to host" in text
        or "clientconnectorerror" in text
        or "connection reset" in text
        or "temporarily unavailable" in text
    )


class TelegramApiLogger(BaseRequestMiddleware):

    async def __call__(self, make_request, bot, method: TelegramMethod):
        method_name = method.__class__.__name__

        if method_name in _SKIP_METHODS:
            return await make_request(bot, method)

        is_fast = method_name in _FAST_METHODS
        max_attempts = (
            _FAST_NETWORK_RETRY_ATTEMPTS if is_fast else _NETWORK_RETRY_ATTEMPTS
        )
        retry_base = (
            _FAST_NETWORK_RETRY_BASE_DELAY if is_fast else _NETWORK_RETRY_BASE_DELAY
        )

        started = time.perf_counter()
        quiet = _quiet_mode

        # В quiet / для fast-методов не пишем START (sync disk I/O тормозит loop)
        if not is_fast and not quiet:
            logger.info(
                "➡ START %-28s",
                method_name
            )

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = await make_request(bot, method)

                elapsed = (time.perf_counter() - started) * 1000
                if is_fast:
                    # AnswerCallbackQuery: лог только при ретрае/медленном ответе
                    if attempt > 1 or elapsed >= 250:
                        logger.info(
                            "✅ END   %-28s %.2f ms%s",
                            method_name,
                            elapsed,
                            f" (retry {attempt} ok)" if attempt > 1 else "",
                        )
                elif quiet:
                    # В тихом режиме — только медленные/ретраи
                    if attempt > 1 or elapsed >= 400:
                        logger.info(
                            "✅ END   %-28s %.2f ms%s",
                            method_name,
                            elapsed,
                            f" (retry {attempt} ok)" if attempt > 1 else "",
                        )
                elif attempt > 1:
                    logger.info(
                        "✅ END   %-28s %.2f ms (retry %d ok)",
                        method_name,
                        elapsed,
                        attempt,
                    )
                else:
                    logger.info(
                        "✅ END   %-28s %.2f ms",
                        method_name,
                        elapsed
                    )
                return result

            except Exception as e:
                last_error = e
                elapsed = (time.perf_counter() - started) * 1000

                # Сетевой обрыв — пробуем ещё раз, не роняем handler с первого раза.
                if _is_network_error(e) and attempt < max_attempts:
                    delay = retry_base * (2 ** (attempt - 1))
                    logger.warning(
                        "↻ NET   %-28s %.2f ms attempt %d/%d → sleep %.1fs %s",
                        method_name,
                        elapsed,
                        attempt,
                        max_attempts,
                        delay,
                        type(e).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue

                if _is_stale_query(method_name, e):
                    global _stale_query_count
                    _stale_query_count += 1
                    if _should_log_softfail_once(f"stale|{method_name}"):
                        logger.warning(
                            "⌛ STALE %-28s %.2f ms просрочен/уже отвечен callback "
                            "(всего с запуска: %d)",
                            method_name,
                            elapsed,
                            _stale_query_count,
                        )
                    return True

                # Экран уже такой, какой нужен - это не ошибка.
                if _is_idempotent_edit_ok(method_name, e):
                    if _should_log_softfail_once(f"same|{method_name}"):
                        logger.info(
                            "↩ SAME  %-28s %.2f ms already current",
                            method_name,
                            elapsed,
                        )
                    return True

                if _is_softfail_exception(method_name, e):
                    signature = f"{method_name}|{type(e).__name__}|{_error_text(e)}"
                    if _should_log_softfail_once(signature):
                        logger.warning(
                            "⚠ SOFTFAIL %-28s %.2f ms %s",
                            method_name,
                            elapsed,
                            repr(e)
                        )
                    raise

                if _is_quiet_error(e):
                    signature = f"quiet|{method_name}|{_error_text(e)}"
                    if _should_log_softfail_once(signature):
                        logger.warning(
                            "⚠ EXPECTED %-27s %.2f ms %s",
                            method_name,
                            elapsed,
                            str(e),
                        )
                    raise

                logger.exception(
                    "❌ FAIL  %-28s %.2f ms %s",
                    method_name,
                    elapsed,
                    repr(e)
                )
                raise

        # На практике недостижимо: цикл либо return, либо raise.
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"telegram request failed: {method_name}")