"""Отчёты об ошибках в Telegram"""

from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any

from config import (
    ERROR_REPORT_ENABLED,
    ERROR_TELEGRAM_CHAT_ID,
    ERROR_TELEGRAM_THREAD_ID,
)
from error_codes import (
    code_from_api_path,
    code_from_http_status,
    error_meaning,
    error_title,
    is_security_code,
    resolve_error_code,
)
from telegram_notify import send_telegram_message

logger = logging.getLogger("cute-farm.errors")

_DEDUP_SECONDS = 45
_recent_keys: dict[str, float] = {}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _should_send(dedup_key: str) -> bool:
    now = time.monotonic()
    last = _recent_keys.get(dedup_key, 0.0)
    if now - last < _DEDUP_SECONDS:
        return False
    _recent_keys[dedup_key] = now
    if len(_recent_keys) > 500:
        oldest = sorted(_recent_keys.items(), key=lambda item: item[1])[:100]
        for key, _ in oldest:
            _recent_keys.pop(key, None)
    return True


def _format_error_message(
    code: str,
    *,
    user_id: int | None = None,
    path: str = "",
    method: str = "",
    message: str = "",
    status: int | None = None,
    source: str = "server",
) -> str:
    resolved = resolve_error_code(code)
    lines = []
    if is_security_code(resolved):
        lines.append("<tg-emoji emoji-id='5373059848856421989'>❗️</tg-emoji> <b>ПОДОЗРЕНИЕ НА ВЗЛОМ</b>")
    lines.extend([
        f"<tg-emoji emoji-id='5222453530677225961'>🚨</tg-emoji> <b>{_escape(resolved)}</b>",
        f"<tg-emoji emoji-id='5454074580010295588'>🔄</tg-emoji> {_escape(error_title(resolved))}",
    ])
    if status is not None:
        lines.append(f"<tg-emoji emoji-id='5391250718982180415'>🔢</tg-emoji> <b>HTTP: {_escape(status)}</b>")
    if user_id is not None:
        lines.append(f"<tg-emoji emoji-id='5364052602357044385'>🐶</tg-emoji> <b>ID: <code>{_escape(user_id)}</code></b>")
    if method or path:
        lines.append(f"<tg-emoji emoji-id='5249244862359812334'>📍</tg-emoji> <b>{_escape(method)} {_escape(path)}</b>".strip())
    lines.append(f"<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Источник : {_escape(source)}</b>")
    if message:
        trimmed = message.strip()
        if len(trimmed) > 500:
            trimmed = trimmed[:497] + "..."
        lines.append(f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> <b>{_escape(trimmed)}</b>")
    lines.append(f"<tg-emoji emoji-id='5341355074587206546'>📖</tg-emoji> <b>{_escape(error_meaning(resolved))}</b>")
    return "\n".join(lines)


async def _deliver_error(text: str) -> None:
    if not (ERROR_REPORT_ENABLED and ERROR_TELEGRAM_CHAT_ID):
        return
    await send_telegram_message(
        text,
        chat_id=ERROR_TELEGRAM_CHAT_ID,
        thread_id=ERROR_TELEGRAM_THREAD_ID,
    )


async def report_error(
    code: str,
    *,
    user_id: int | None = None,
    path: str = "",
    method: str = "",
    message: str = "",
    status: int | None = None,
    source: str = "server",
    client_ip: str = "",
) -> None:
    resolved = resolve_error_code(code)
    dedup_key = f"{resolved}:{user_id or 0}:{path}:{message[:80]}"
    if not _should_send(dedup_key):
        return

    await _persist_system_log(
        resolved,
        user_id=user_id,
        path=path,
        method=method,
        message=message,
        status=status,
        source=source,
        client_ip=client_ip,
    )

    if not ERROR_REPORT_ENABLED:
        return

    text = _format_error_message(
        resolved,
        user_id=user_id,
        path=path,
        method=method,
        message=message,
        status=status,
        source=source,
    )
    try:
        await _deliver_error(text)
    except Exception:
        logger.exception("Error report delivery failed (%s)", resolved)


def _log_category(code: str, *, status: int | None) -> str:
    if is_security_code(code):
        return "security"
    if status is not None and status >= 500:
        return "error"
    if code.startswith("ERR_DB") or code == "ERR_API_500":
        return "error"
    return "api"


async def _persist_system_log(
    code: str,
    *,
    user_id: int | None = None,
    path: str = "",
    method: str = "",
    message: str = "",
    status: int | None = None,
    source: str = "server",
    client_ip: str = "",
) -> None:
    try:
        from db import db

        if db.pool is None:
            return
        category = _log_category(code, status=status)
        if category == "api":
            return
        ip = (client_ip or "").strip()
        if ip.startswith("IP: "):
            ip = ip[4:].strip()
        await db.pool.execute(
            """
            INSERT INTO system_logs (
                category, code, user_id, method, path, status, message, source, client_ip
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            category,
            code,
            user_id,
            method or None,
            path or None,
            status,
            (message or "")[:2000] or None,
            source or None,
            ip or None,
        )
    except Exception:
        logger.exception("System log persist failed (%s)", code)


def schedule_error_report(
    code: str,
    *,
    user_id: int | None = None,
    path: str = "",
    method: str = "",
    message: str = "",
    status: int | None = None,
    source: str = "server",
    client_ip: str = "",
) -> None:
    msg = message
    if client_ip:
        msg = f"{message} | IP: {client_ip}".strip(" |")
    asyncio.create_task(
        report_error(
            code,
            user_id=user_id,
            path=path,
            method=method,
            message=msg,
            status=status,
            source=source,
            client_ip=client_ip,
        )
    )


def schedule_security_alert(
    code: str,
    *,
    request=None,
    user_id: int | None = None,
    path: str = "",
    method: str = "",
    message: str = "",
    status: int | None = None,
    source: str = "security",
) -> None:
    ip = ""
    if request is not None:
        if getattr(request, "client", None) is not None:
            ip = request.client.host or ""
        path = path or request.url.path
        method = method or request.method
    schedule_error_report(
        code,
        user_id=user_id,
        path=path,
        method=method,
        message=message,
        status=status,
        source=source,
        client_ip=ip,
    )


def _is_expected_client_auth_failure(status: int, detail: str) -> bool:
    """Истёкшая сессия / закрытый WebApp — не баг, не слать в Telegram."""
    if status != 401:
        return False
    text = detail.strip().lower()
    return (
        "сессия истекла" in text
        or "откройте ферму снова" in text
        or "откройте ферму через telegram" in text
    )


def schedule_http_error(
    *,
    user_id: int | None,
    method: str,
    path: str,
    status: int,
    detail: str,
    source: str = "server",
) -> None:
    if path == "/api/report-error":
        return
    if not ERROR_REPORT_ENABLED:
        return
    if _is_expected_client_auth_failure(status, detail):
        return
    code = code_from_api_path(path, status)
    if status == 401 and "Сессия истекла" in detail:
        code = "ERR_AUTH_EXPIRED"
    if status == 401 and "user_id" in detail.lower():
        code = "ERR_AUTH_401"
    if status == 400 and "user_id берётся" in detail:
        code = "ERR_SEC_BODY_UID"
    if status == 400 and ("balance" in detail.lower() or "kut" in detail.lower()):
        code = "ERR_SEC_BODY_BALANCE"
    if status == 403 and "localhost" in detail.lower():
        code = "ERR_SEC_DEV_SPOOF"
    if status == 422:
        code = "ERR_SEC_EXTRA_FIELDS"
    if status == 429:
        code = "ERR_SEC_RATE_ABUSE"
    if status == 500 and "не настроен" in detail.lower():
        code = "ERR_AUTH_NO_BOT"

    schedule_error_report(
        code,
        user_id=user_id,
        path=path,
        method=method,
        message=detail,
        status=status,
        source=source,
    )


def schedule_server_exception(
    *,
    user_id: int | None,
    method: str,
    path: str,
    exc: Exception,
) -> None:
    if path == "/api/report-error":
        return
    message = str(exc)
    code = "ERR_API_500"
    if "PostgreSQL" in message or "asyncpg" in message.lower():
        code = "ERR_DB_QUERY"
    schedule_error_report(
        code,
        user_id=user_id,
        path=path,
        method=method,
        message=message,
        status=500,
        source="server",
    )
