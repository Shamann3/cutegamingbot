"""Admin panel: Telegram initData (admin-бот), TOTP, сессии."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import unquote

logger = logging.getLogger(__name__)


def _auth_debug(request: "Request", msg: str) -> None:
    """Пишет строку диагностики авторизации в logs/admin-auth-debug.log.

    Нужен для отладки входа с телефона: показывает, какой запрос и почему
    отклоняется, независимо от кэша/фронтенда на устройстве."""
    try:
        import datetime
        log_dir = Path(__file__).resolve().parents[1] / "logs"
        log_dir.mkdir(exist_ok=True)
        method = getattr(request, "method", "?")
        path = getattr(getattr(request, "url", None), "path", "?")
        ua = (request.headers.get("user-agent", "")[:60]) if hasattr(request, "headers") else ""
        line = f"{datetime.datetime.now().isoformat(timespec='seconds')} | {method} {path} | {msg} | ua={ua}\n"
        with open(log_dir / "admin-auth-debug.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _resolve_env_file() -> Path:
    """Единый источник — корневой .env. server/.env оставлен как заглушка,
    поэтому ADMIN_LOGIN_KEY читаем из корня; локальный .env — только fallback."""
    root_env = Path(__file__).resolve().parents[1] / ".env"
    local_env = Path(__file__).resolve().parent / ".env"
    if root_env.is_file():
        return root_env
    return local_env


_ENV_FILE = _resolve_env_file()

import pyotp
import qrcode
from fastapi import Depends, Header, HTTPException, Request

from config import (
    ADMIN_BOT_TOKEN,
    ADMIN_ENABLED,
    ADMIN_LOGIN_KEY,
    ADMIN_JWT_SECRET,
    ADMIN_SESSION_MINUTES,
    ADMIN_TOTP_VALID_WINDOW,
    ALLOW_DEV_AUTH,
    INIT_DATA_MAX_AGE,
    PRODUCTION,
    admin_user_ids,
)
from error_reporter import schedule_security_alert

_DEV_CLIENT_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_local_client(request: Request) -> bool:
    if request.client is None:
        return False
    return request.client.host in _DEV_CLIENT_HOSTS


def _normalize_key(value: str) -> str:
    return value.strip().strip("\ufeff").strip("\r")


def _read_login_key_from_env_file() -> str:
    """Читаем ADMIN_LOGIN_KEY напрямую из server/.env — не зависим от cwd и кэша uvicorn."""
    if not _ENV_FILE.is_file():
        return ""
    try:
        text = _ENV_FILE.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "ADMIN_LOGIN_KEY":
            return _normalize_key(value)
    return ""


def _fresh_login_key() -> str:
    login = _read_login_key_from_env_file()
    if not login:
        login = _normalize_key(ADMIN_LOGIN_KEY)
    return login


def _key_matches(candidate: str, expected: str) -> bool:
    if not expected:
        return False
    a = _normalize_key(candidate)
    b = _normalize_key(expected)
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def classify_admin_key(value: str) -> str | None:
    """Определяет ветку регистрации по введённому ключу.

    'owner' — ключ для владельцев (= ADMIN_LOGIN_KEY), анкета пропускается.
    None    — ключ не подошёл (DB-инвайты проверяются отдельно в admin_routes).
    """
    login_key = _fresh_login_key()
    if login_key and _key_matches(value, login_key):
        return "owner"
    return None


def validate_login_key(value: str) -> bool:
    login_key = _fresh_login_key()
    if not login_key:
        logger.warning("admin login: ADMIN_LOGIN_KEY not configured in %s", _ENV_FILE)
        return False
    ok = _key_matches(value, login_key)
    if not ok:
        logger.warning(
            "admin login: key mismatch (provided len=%s, login len=%s)",
            len(_normalize_key(value)),
            len(login_key),
        )
    return ok


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_uri(secret: str, *, account_name: str, issuer: str = "CuteEpsilon") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def totp_qr_data_url(otpauth_uri: str) -> str:
    image = qrcode.make(otpauth_uri, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def normalize_totp_code(code: str) -> str:
    """Только цифры, максимум 6 — пробелы/дефисы из буфера обмена отбрасываются."""
    digits = "".join(ch for ch in (code or "") if ch.isdigit())
    return digits[:6]


def normalize_totp_secret(secret: str) -> str:
    """Base32-секрет для pyotp: без пробелов, верхний регистр."""
    return (secret or "").replace(" ", "").upper()


def verify_totp(secret: str, code: str, *, valid_window: int = 2) -> bool:
    """Проверка кода. valid_window по умолчанию 2 (как в рабочем cutefarmer);
    более широкое окно используется только для «получить подтверждающий код»,
    чтобы компенсировать рассинхрон часов телефона."""
    norm_secret = normalize_totp_secret(secret)
    norm_code = normalize_totp_code(code)
    if not norm_secret or len(norm_code) != 6:
        return False
    try:
        return pyotp.TOTP(norm_secret).verify(norm_code, valid_window=max(1, int(valid_window)))
    except Exception:
        return False


def totp_code_now(secret: str) -> str | None:
    """Текущий 6-значный код сервера для секрета."""
    norm_secret = normalize_totp_secret(secret)
    if not norm_secret:
        return None
    try:
        return pyotp.TOTP(norm_secret).now()
    except Exception:
        return None


def create_setup_token() -> str:
    return secrets.token_urlsafe(32)


def _validate_admin_init_data(init_data: str, request: Request) -> tuple[int, dict]:
    if not ADMIN_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Admin-бот не настроен")

    parsed: dict[str, str] = {}
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key] = unquote(value)

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Откройте панель через admin-бота")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", ADMIN_BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status_code=401, detail="Откройте панель через admin-бота, не через игрового")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(status_code=401, detail="Сессия Telegram недействительна")

    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise HTTPException(status_code=401, detail="Сессия истекла. Откройте панель снова")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="Откройте панель через admin-бота")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Сессия Telegram недействительна")

    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Сессия Telegram недействительна")

    request.state.telegram_user = user
    return int(user_id), user


def _bearer_token(request: Request) -> str:
    """Достаём Bearer-токен из заголовка Authorization (или пустая строка)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    return ""


async def get_admin_user_id(
    request: Request,
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: str | None = Header(None, alias="X-Dev-User-Id"),
) -> int:
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=503, detail="Admin panel отключён")

    user_id: int | None = None
    init_ok = False
    token_ok = False

    # 1) Самый свежий источник — Telegram initData. Если он есть и валиден — берём
    #    личность из него. Если initData присутствует, но не прошёл (устарел/битый
    #    на мобильном WebView), НЕ падаем сразу — пробуем токен сессии ниже.
    if x_telegram_init_data:
        try:
            user_id, _user = _validate_admin_init_data(x_telegram_init_data, request)
            init_ok = True
        except HTTPException as exc:
            user_id = None
            _auth_debug(request, f"initData FAIL: {exc.detail}")

    # 2) Fallback — валидный подписанный токен сессии. Он выдаётся только после
    #    полной аутентификации (ключ + TOTP + initData) при входе, подделать его
    #    нельзя. Это делает панель стабильной на любом устройстве весь срок сессии,
    #    не завися от особенностей initData на телефонах.
    if user_id is None:
        token = _bearer_token(request)
        verified = verify_admin_token(token) if token else None
        if verified is not None:
            user_id = verified[0]
            token_ok = True

    _auth_debug(
        request,
        f"get_user: initData_present={bool(x_telegram_init_data)} init_ok={init_ok} "
        f"bearer_present={bool(_bearer_token(request))} token_ok={token_ok} user_id={user_id}",
    )

    # 3) Dev-режим (только локально, вне production).
    if user_id is None:
        if PRODUCTION or not ALLOW_DEV_AUTH or not x_dev_user_id:
            _auth_debug(request, "get_user RAISE 401: нет initData/токена/dev")
            raise HTTPException(status_code=401, detail="Откройте панель через admin-бота")
        elif not _is_local_client(request):
            raise HTTPException(status_code=403, detail="Dev-режим только с localhost")
        else:
            try:
                user_id = int(x_dev_user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный dev user id")
            if user_id <= 0:
                raise HTTPException(status_code=400, detail="Неверный dev user id")

    # Гейт доступа: владелец из конфига ИЛИ зарегистрированный admin-аккаунт
    # (включая кандидатов — их активность/роль проверяет require_active_admin
    # для защищённых роутов и admin_login по статусу).
    from config import owner_user_ids

    is_owner = user_id in owner_user_ids()
    has_account = False
    if not is_owner:
        try:
            from db import db
            has_account = bool(
                await db.pool.fetchval(
                    "SELECT 1 FROM admin_accounts WHERE user_id = $1",
                    user_id,
                )
            )
        except Exception as exc:
            logger.error("get_admin_user_id DB error for %s: %s", user_id, exc)
            raise HTTPException(status_code=503, detail="Ошибка доступа. Попробуйте ещё раз")

    if not is_owner and not has_account:
        schedule_security_alert(
            "ERR_SEC_NO_AUTH",
            request=request,
            message=f"admin login без аккаунта/owner: {user_id}",
            status=403,
        )
        raise HTTPException(status_code=403, detail="Нет доступа к панели")

    request.state.user_id = user_id
    return user_id


async def get_any_telegram_user_id(
    request: Request,
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: str | None = Header(None, alias="X-Dev-User-Id"),
) -> int:
    """Telegram initData без проверки ADMIN_USER_IDS — для регистрации."""
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=503, detail="Admin panel отключён")

    if x_telegram_init_data:
        user_id, _user = _validate_admin_init_data(x_telegram_init_data, request)
    elif PRODUCTION or not ALLOW_DEV_AUTH or not x_dev_user_id:
        raise HTTPException(status_code=401, detail="Откройте панель через admin-бота")
    elif not _is_local_client(request):
        raise HTTPException(status_code=403, detail="Dev-режим только с localhost")
    else:
        try:
            user_id = int(x_dev_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный dev user id")
        if user_id <= 0:
            raise HTTPException(status_code=400, detail="Неверный dev user id")

    request.state.user_id = user_id
    return user_id


def _get_client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded[:64] if forwarded else (request.client.host if request.client else "unknown")


def _ua_fingerprint(request: Request) -> str:
    ua = request.headers.get("user-agent", "")[:256]
    return hashlib.sha256(ua.encode()).hexdigest()[:16]


def issue_admin_token(user_id: int) -> tuple[str, int]:
    if not ADMIN_JWT_SECRET:
        raise HTTPException(status_code=500, detail="ADMIN_JWT_SECRET не настроен")
    try:
        from admin_session_cache import get_admin_session_minutes_cached
        session_minutes = get_admin_session_minutes_cached()
    except Exception:
        session_minutes = ADMIN_SESSION_MINUTES
    iat = int(time.time())
    exp = iat + session_minutes * 60
    body = f"{user_id}.{iat}.{exp}"
    sig = hmac.new(ADMIN_JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}", exp


def verify_admin_token(token: str) -> tuple[int, int] | None:
    """Returns (user_id, iat) or None if invalid/expired."""
    if not token or not ADMIN_JWT_SECRET:
        return None
    parts = token.split(".")
    # Support both new 4-part tokens and legacy 3-part tokens
    if len(parts) == 4:
        user_part, iat_part, exp_part, sig = parts
        body = f"{user_part}.{iat_part}.{exp_part}"
    elif len(parts) == 3:
        user_part, exp_part, sig = parts
        iat_part = "0"
        body = f"{user_part}.{exp_part}"
    else:
        return None
    try:
        user_id = int(user_part)
        iat = int(iat_part)
        exp = int(exp_part)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    expected = hmac.new(ADMIN_JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return user_id, iat


async def store_session_fingerprint(user_id: int, request: Request) -> None:
    """Called after successful login to register device fingerprint.

    Также сбрасываем force_reauth_at: свежий успешный вход снимает прежнее
    требование повторной аутентификации, иначе только что выданный токен мог
    бы сразу отклоняться (и панель «не входила» бы после входа)."""
    fingerprint = _ua_fingerprint(request)
    ip = _get_client_ip(request)
    try:
        from db import db
        await db.pool.execute(
            """
            UPDATE admin_accounts
            SET session_fingerprint = $2, last_ip = $3, last_seen_at = NOW(),
                force_reauth_at = NULL
            WHERE user_id = $1
            """,
            user_id, fingerprint, ip,
        )
    except Exception:
        pass


async def require_admin_session(
    request: Request,
    user_id: int = Depends(get_admin_user_id),
) -> int:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    verified = verify_admin_token(token) if token else None

    # Сессия действительна, если ЛИБО валиден подписанный токен, ЛИБО запрос прошёл
    # по свежему Telegram initData (его Telegram подписывает токеном бота и присылает
    # на КАЖДЫЙ запрос). Второй путь спасает телефоны: там WebView не сохраняет JWT
    # между запросами, а initData есть всегда. get_admin_user_id уже проверил initData
    # и выставил request.state.telegram_user, значит личность подтверждена.
    init_authenticated = getattr(request.state, "telegram_user", None) is not None

    if verified is not None and verified[0] == user_id:
        iat = verified[1]
    elif init_authenticated:
        iat = int(time.time())
    else:
        _auth_debug(
            request,
            f"session RAISE 401: token_present={bool(token)} verified={verified} "
            f"init_auth={init_authenticated} user_id={user_id}",
        )
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова")

    try:
        from db import db
        row = await db.pool.fetchrow(
            "SELECT session_fingerprint, force_reauth_at FROM admin_accounts WHERE user_id = $1",
            user_id,
        )
        if row:
            # Force re-auth: строгий "разлогинить всех" (kill-switch владельца).
            if row["force_reauth_at"] and iat < row["force_reauth_at"].timestamp():
                _auth_debug(
                    request,
                    f"session RAISE 401 force_reauth: iat={iat} "
                    f"force_reauth_at={row['force_reauth_at']}",
                )
                raise HTTPException(
                    status_code=401,
                    detail="Требуется повторная аутентификация",
                )
        _auth_debug(request, f"session OK user_id={user_id}")
        # Отпечаток устройства НЕ используем как жёсткий блок: он ломал вход с
        # нового устройства (регистрация на ПК → вход с телефона). Личность уже
        # подтверждена подписанным токеном, поэтому просто обновляем отпечаток на
        # текущее устройство (учёт), не блокируя.
        # Fire-and-forget: обновляем ip, время визита и отпечаток устройства.
        import asyncio
        asyncio.create_task(
            _update_last_seen(user_id, _get_client_ip(request), _ua_fingerprint(request))
        )
    except HTTPException:
        raise
    except Exception as exc:
        # Fail-closed: a DB error must not grant access. Log and reject.
        logger.error("require_admin_session DB error for user %s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail="Ошибка сессии. Попробуйте ещё раз")

    return user_id


async def _update_last_seen(user_id: int, ip: str, fingerprint: str | None = None) -> None:
    try:
        from db import db
        if fingerprint:
            # Держим отпечаток «плавающим» — всегда равным последнему устройству,
            # с которого реально работали. Это не блокирует вход, а лишь ведёт учёт.
            await db.pool.execute(
                "UPDATE admin_accounts SET last_ip = $2, last_seen_at = NOW(), session_fingerprint = $3 WHERE user_id = $1",
                user_id, ip, fingerprint,
            )
        else:
            await db.pool.execute(
                "UPDATE admin_accounts SET last_ip = $2, last_seen_at = NOW() WHERE user_id = $1",
                user_id, ip,
            )
        # Фиксируем слот активности для подсчёта часов онлайн
        from admin_db import record_admin_activity
        await record_admin_activity(user_id)
    except Exception:
        pass


async def force_reauth(user_id: int | None = None) -> int:
    """Set force_reauth_at = NOW() for one or all admins. Returns rows updated."""
    from db import db
    if user_id is not None:
        result = await db.pool.execute(
            "UPDATE admin_accounts SET force_reauth_at = NOW(), session_fingerprint = NULL WHERE user_id = $1",
            user_id,
        )
    else:
        result = await db.pool.execute(
            "UPDATE admin_accounts SET force_reauth_at = NOW(), session_fingerprint = NULL"
        )
    try:
        return int(result.split()[-1])
    except Exception:
        return 0
