import logging
import sys
import time

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods import TelegramMethod

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
)
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
)


def _is_quiet_error(error: Exception) -> bool:
    if not isinstance(error, (TelegramBadRequest, TelegramForbiddenError)):
        return False
    text = str(error).lower()
    return any(pattern in text for pattern in _QUIET_PATTERNS)


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
    return True


class TelegramApiLogger(BaseRequestMiddleware):

    async def __call__(self, make_request, bot, method: TelegramMethod):
        method_name = method.__class__.__name__

        if method_name in _SKIP_METHODS:
            return await make_request(bot, method)

        started = time.perf_counter()

        logger.info(
            "➡ START %-28s",
            method_name
        )

        try:
            result = await make_request(bot, method)

            elapsed = (time.perf_counter() - started) * 1000

            logger.info(
                "✅ END   %-28s %.2f ms",
                method_name,
                elapsed
            )

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - started) * 1000

            if _is_stale_query(method_name, e):
                global _stale_query_count
                _stale_query_count += 1
                if _should_log_softfail_once(f"stale|{method_name}"):
                    logger.warning(
                        "⌛ STALE %-28s %.2f ms просрочен ответ на нажатие "
                        "(всего с запуска: %d)",
                        method_name,
                        elapsed,
                        _stale_query_count,
                    )
                return True

            if _is_softfail_exception(method_name, e):
                signature = f"{method_name}|{type(e).__name__}|{str(e).lower()}"
                if _should_log_softfail_once(signature):
                    logger.warning(
                        "⚠ SOFTFAIL %-28s %.2f ms %s",
                        method_name,
                        elapsed,
                        repr(e)
                    )
                raise

            if _is_quiet_error(e):
                signature = f"quiet|{method_name}|{str(e).lower()}"
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