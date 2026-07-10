"""Клиентские данные игрока: устройство, IP, Telegram — при входе в WebApp."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

from db import db

logger = logging.getLogger("cute-farm")

_LOGIN_EVENT_MIN_INTERVAL_SECONDS = 30 * 60
_SYNC_THROTTLE_SECONDS = 300
_last_sync_at: dict[int, float] = {}


def _clean_text(value: Any, *, max_len: int = 500) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _clean_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_client_info_header(request) -> dict | None:
    raw = (request.headers.get("x-client-info") or "").strip()
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw, validate=False)
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def merge_client_payload(request, payload: dict | None) -> dict:
    header = parse_client_info_header(request) or {}
    body = payload or {}
    merged = {**header, **body}
    return {k: v for k, v in merged.items() if v is not None and v != ""}


def build_client_snapshot(
    request,
    payload: dict | None,
    tg_user: dict | None,
) -> dict:
    body = merge_client_payload(request, payload)
    tg = tg_user or {}

    ip = ""
    if request.client is not None:
        ip = (request.client.host or "").strip()
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        ip = forwarded[:64]
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        ip = real_ip[:64]

    ua_header = (request.headers.get("user-agent") or "").strip()[:500]
    ua_body = _clean_text(body.get("userAgent"), max_len=500)
    user_agent = ua_body or ua_header or None

    platform = _clean_text(body.get("platform") or body.get("tgPlatform"), max_len=64)

    premium_raw = tg.get("is_premium")
    if premium_raw is None:
        premium_raw = body.get("isPremium")
    is_premium = bool(premium_raw) if premium_raw is not None else None

    info_patch = {
        k: v
        for k, v in {
            "viewportWidth": _clean_int(body.get("viewportWidth")),
            "viewportHeight": _clean_int(body.get("viewportHeight")),
            "screenWidth": _clean_int(body.get("screenWidth")),
            "screenHeight": _clean_int(body.get("screenHeight")),
            "timezone": _clean_text(body.get("timezone"), max_len=64),
            "colorScheme": _clean_text(body.get("colorScheme"), max_len=16),
            "deviceModel": _clean_text(body.get("deviceModel"), max_len=120),
            "navigatorLanguage": _clean_text(body.get("navigatorLanguage"), max_len=32),
            "isExpanded": body.get("isExpanded"),
            "tgVersion": _clean_text(body.get("appVersion"), max_len=32),
        }.items()
        if v is not None and v != ""
    }

    return {
        "client_ip": ip or None,
        "user_agent": user_agent,
        "platform": platform,
        "app_version": _clean_text(body.get("appVersion"), max_len=32),
        "language_code": _clean_text(tg.get("language_code") or body.get("language"), max_len=16),
        "is_premium": is_premium,
        "info_patch": info_patch,
    }


async def sync_user_client_info(
    user_id: int,
    request,
    payload: dict | None = None,
    tg_user: dict | None = None,
    *,
    force: bool = False,
) -> None:
    if not force:
        last = _last_sync_at.get(user_id, 0.0)
        if time.monotonic() - last < _SYNC_THROTTLE_SECONDS:
            return

    await db.ensure_user(user_id)
    snap = build_client_snapshot(request, payload, tg_user)

    if not any([
        snap["client_ip"],
        snap["user_agent"],
        snap["platform"],
        snap["app_version"],
        snap["language_code"],
        snap["is_premium"] is not None,
        snap["info_patch"],
    ]):
        return

    _last_sync_at[user_id] = time.monotonic()

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET last_client_ip = CASE WHEN $2::text IS NOT NULL THEN $2 ELSE last_client_ip END,
                last_user_agent = CASE WHEN $3::text IS NOT NULL THEN $3 ELSE last_user_agent END,
                last_platform = CASE WHEN $4::text IS NOT NULL THEN $4 ELSE last_platform END,
                last_app_version = CASE WHEN $5::text IS NOT NULL THEN $5 ELSE last_app_version END,
                last_language_code = CASE WHEN $6::text IS NOT NULL THEN $6 ELSE last_language_code END,
                is_premium = CASE WHEN $7::boolean IS NOT NULL THEN $7 ELSE is_premium END,
                client_info = COALESCE(client_info, '{}'::jsonb) || $8::jsonb,
                client_info_updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            snap["client_ip"],
            snap["user_agent"],
            snap["platform"],
            snap["app_version"],
            snap["language_code"],
            snap["is_premium"],
            json.dumps(snap["info_patch"], ensure_ascii=False),
        )

        try:
            recent = await conn.fetchrow(
                """
                SELECT id, client_ip, platform, user_agent, created_at
                FROM user_login_events
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
            )

            should_log = recent is None
            if recent and not should_log:
                changed = (
                    (snap["client_ip"] and snap["client_ip"] != recent["client_ip"])
                    or (snap["platform"] and snap["platform"] != recent["platform"])
                    or (snap["user_agent"] and snap["user_agent"] != recent["user_agent"])
                )
                if changed:
                    should_log = True
                else:
                    age = await conn.fetchval(
                        "SELECT EXTRACT(EPOCH FROM (NOW() - $1::timestamptz))::float",
                        recent["created_at"],
                    )
                    if age is not None and age >= _LOGIN_EVENT_MIN_INTERVAL_SECONDS:
                        should_log = True

            if should_log:
                info = snap["info_patch"]
                await conn.execute(
                    """
                    INSERT INTO user_login_events (
                        user_id, client_ip, user_agent, platform, device_model,
                        app_version, language_code, is_premium,
                        screen_width, screen_height, timezone, payload
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
                    """,
                    user_id,
                    snap["client_ip"],
                    snap["user_agent"],
                    snap["platform"],
                    info.get("deviceModel"),
                    snap["app_version"],
                    snap["language_code"],
                    snap["is_premium"],
                    info.get("screenWidth"),
                    info.get("screenHeight"),
                    info.get("timezone"),
                    json.dumps(info, ensure_ascii=False),
                )
        except Exception:
            logger.exception("user_login_events insert failed for user_id=%s", user_id)
