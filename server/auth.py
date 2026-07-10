import hashlib
import hmac
import json
import time
from urllib.parse import unquote

from fastapi import Header, HTTPException, Request

from config import ALLOW_DEV_AUTH, BOT_TOKEN, INIT_DATA_MAX_AGE, PRODUCTION
from error_reporter import schedule_security_alert
from private_mode import is_allowed

_DEV_CLIENT_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _validate_telegram_init_data(init_data: str, request: Request) -> int:
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Сервер не настроен")

    parsed: dict[str, str] = {}
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key] = unquote(value)

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        schedule_security_alert(
            "ERR_SEC_FAKE_INIT",
            request=request,
            message="initData без hash",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        schedule_security_alert(
            "ERR_SEC_HASH_FAIL",
            request=request,
            message="HMAC initData не совпал",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        schedule_security_alert(
            "ERR_SEC_FAKE_INIT",
            request=request,
            message="Битый auth_date в initData",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise HTTPException(status_code=401, detail="Сессия истекла. Пожалуйста, откройте ферму снова")

    user_raw = parsed.get("user")
    if not user_raw:
        schedule_security_alert(
            "ERR_SEC_FAKE_INIT",
            request=request,
            message="initData без user",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        schedule_security_alert(
            "ERR_SEC_FAKE_INIT",
            request=request,
            message="Битый JSON user в initData",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    user_id = user.get("id")
    if not user_id:
        schedule_security_alert(
            "ERR_SEC_FAKE_INIT",
            request=request,
            message="user без id в initData",
            status=401,
        )
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram")

    request.state.telegram_user = user
    uid = int(user_id)
    if not is_allowed(uid):
        raise HTTPException(status_code=503, detail="сервис временно недоступен")
    return uid


def _is_local_client(request: Request) -> bool:
    if request.client is None:
        return False
    host = request.client.host
    return host in _DEV_CLIENT_HOSTS


async def get_user_id(
    request: Request,
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: str | None = Header(None, alias="X-Dev-User-Id"),
) -> int:
    if x_telegram_init_data:
        return _validate_telegram_init_data(x_telegram_init_data, request)

    if PRODUCTION:
        if x_dev_user_id:
            schedule_security_alert(
                "ERR_SEC_PROD_BYPASS",
                request=request,
                message=f"X-Dev-User-Id={x_dev_user_id}",
                status=401,
            )
        else:
            schedule_security_alert(
                "ERR_SEC_NO_AUTH",
                request=request,
                message="Нет initData на проде",
                status=401,
            )
        raise HTTPException(status_code=401, detail="Пожалуйста, откройте ферму через Telegram бота")

    if ALLOW_DEV_AUTH and x_dev_user_id:
        if not _is_local_client(request):
            schedule_security_alert(
                "ERR_SEC_DEV_SPOOF",
                request=request,
                message=f"X-Dev-User-Id={x_dev_user_id}",
                status=403,
            )
            raise HTTPException(status_code=403, detail="Dev-режим только с localhost")
        try:
            user_id = int(x_dev_user_id)
        except ValueError:
            schedule_security_alert(
                "ERR_SEC_DEV_INVALID",
                request=request,
                message=f"X-Dev-User-Id={x_dev_user_id}",
                status=400,
            )
            raise HTTPException(status_code=400, detail="Неверный dev user id")
        if user_id <= 0:
            schedule_security_alert(
                "ERR_SEC_DEV_INVALID",
                request=request,
                message=f"X-Dev-User-Id={x_dev_user_id}",
                status=400,
            )
            raise HTTPException(status_code=400, detail="Неверный dev user id")
        if not is_allowed(user_id):
            raise HTTPException(status_code=503, detail="сервис временно недоступен")
        return user_id

    schedule_security_alert(
        "ERR_SEC_NO_AUTH",
        request=request,
        message="Нет initData и нет dev-auth",
        status=401,
    )
    raise HTTPException(status_code=401, detail="Пожалуйста, откройте ферму через Telegram бота")
