"""IP-банлист: блокировка по IP-адресу или CIDR-подсети.

Хранит активные баны в памяти для быстрой проверки в middleware.
Перезагружается при любом изменении через CRUD-функции.
"""

from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_exact_banned: set[str] = set()          # exact IP strings
_cidr_banned: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []


def _parse_net(
    ip_or_cidr: str,
) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(ip_or_cidr, strict=False)
    except ValueError:
        return None


def _rebuild_cache(rows: list) -> None:
    global _exact_banned, _cidr_banned
    exact: set[str] = set()
    cidrs: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for row in rows:
        val = row["ip_or_cidr"]
        net = _parse_net(val)
        if net is None:
            continue
        if net.prefixlen == net.max_prefixlen:  # exact host
            exact.add(str(net.network_address))
        else:
            cidrs.append(net)
    _exact_banned = exact
    _cidr_banned = cidrs


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def _normalize_ip(ip: str) -> str:
    """Нормализует IP: IPv4-mapped IPv6 (::ffff:x.x.x.x) → чистый IPv4."""
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(addr)
    except ValueError:
        return ip


def is_ip_banned_sync(ip: str) -> bool:
    """Fast sync check — called from middleware, must not block."""
    if not ip or ip in ("unknown", "127.0.0.1", "::1"):
        return False
    normalized = _normalize_ip(ip)
    logger.debug("ip_ban check: raw=%r normalized=%r", ip, normalized)
    if normalized in _exact_banned:
        logger.debug("ip_ban: BLOCKED %s", normalized)
        return True
    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    for net in _cidr_banned:
        if addr in net:
            logger.debug("ip_ban: BLOCKED %s (cidr %s)", normalized, net)
            return True
    return False


# ---------------------------------------------------------------------------
# Init / reload
# ---------------------------------------------------------------------------

async def init_ip_ban_cache() -> None:
    """Load active, non-expired bans from DB into memory. Called at startup and after changes."""
    try:
        from db import db
        rows = await db.pool.fetch(
            """
            SELECT ip_or_cidr FROM ip_bans
            WHERE active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
            """
        )
        _rebuild_cache(rows)
        logger.info("ip_ban: loaded %d active ban(s)", len(rows))

        # Deactivate any bans that have passed their expires_at in DB as well
        await db.pool.execute(
            "UPDATE ip_bans SET active = FALSE WHERE active = TRUE AND expires_at IS NOT NULL AND expires_at <= NOW()"
        )
    except Exception as e:
        logger.error("ip_ban: failed to load cache: %s", e)


async def _reload_cache() -> None:
    await init_ip_ban_cache()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_ip_bans() -> list[dict]:
    from db import db
    rows = await db.pool.fetch(
        """
        SELECT id, ip_or_cidr, reason, banned_by, banned_at, expires_at, active
        FROM ip_bans
        ORDER BY banned_at DESC
        LIMIT 500
        """
    )
    return [
        {
            "id": int(r["id"]),
            "ipOrCidr": r["ip_or_cidr"],
            "reason": r["reason"] or "",
            "bannedBy": int(r["banned_by"]),
            "bannedAt": r["banned_at"].isoformat(),
            "expiresAt": r["expires_at"].isoformat() if r["expires_at"] else None,
            "active": bool(r["active"]),
        }
        for r in rows
    ]


async def add_ip_ban(
    ip_or_cidr: str,
    *,
    reason: str,
    banned_by: int,
    expires_at: Any = None,
) -> dict:
    net = _parse_net(ip_or_cidr)
    if net is None:
        raise ValueError(f"Некорректный IP или CIDR: {ip_or_cidr!r}")

    normalized = str(net)

    from db import db
    # Upsert: if active ban already exists for this IP, update it; otherwise insert new
    existing = await db.pool.fetchrow(
        "SELECT id FROM ip_bans WHERE ip_or_cidr = $1 AND active = TRUE",
        normalized,
    )
    if existing:
        row = await db.pool.fetchrow(
            """
            UPDATE ip_bans
            SET reason = $2, banned_by = $3, expires_at = $4, banned_at = NOW()
            WHERE id = $5
            RETURNING id, ip_or_cidr, reason, banned_by, banned_at, expires_at, active
            """,
            reason.strip()[:200],
            banned_by,
            expires_at,
            existing["id"],
        )
    else:
        row = await db.pool.fetchrow(
            """
            INSERT INTO ip_bans (ip_or_cidr, reason, banned_by, expires_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id, ip_or_cidr, reason, banned_by, banned_at, expires_at, active
            """,
            normalized,
            reason.strip()[:200],
            banned_by,
            expires_at,
        )

    await _reload_cache()
    return {
        "id": int(row["id"]),
        "ipOrCidr": row["ip_or_cidr"],
        "reason": row["reason"] or "",
        "bannedBy": int(row["banned_by"]),
        "bannedAt": row["banned_at"].isoformat(),
        "expiresAt": row["expires_at"].isoformat() if row["expires_at"] else None,
        "active": bool(row["active"]),
    }


async def remove_ip_ban(ban_id: int) -> bool:
    from db import db
    result = await db.pool.execute(
        "UPDATE ip_bans SET active = FALSE WHERE id = $1 AND active = TRUE",
        ban_id,
    )
    await _reload_cache()
    return result == "UPDATE 1"
