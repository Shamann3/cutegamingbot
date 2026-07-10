"""GeoIP lookup for admin (ip-api.com, cached)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from ipaddress import ip_address, ip_network

logger = logging.getLogger("cute-farm")

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 86400

_PRIVATE_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
)


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ip_address(ip.strip())
    except ValueError:
        return True
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _fetch_geo_sync(ip: str) -> dict | None:
    url = (
        f"http://ip-api.com/json/{ip}"
        f"?fields=status,country,countryCode,regionName,city,isp,query"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "cute-farm-admin"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        logger.debug("GeoIP lookup failed for %s", ip, exc_info=True)
        return None

    if data.get("status") != "success":
        return None

    city = (data.get("city") or "").strip()
    region = (data.get("regionName") or "").strip()
    country = (data.get("country") or "").strip()
    parts = [p for p in (city, region, country) if p]

    return {
        "country": country or None,
        "countryCode": (data.get("countryCode") or "").strip() or None,
        "region": region or None,
        "city": city or None,
        "isp": (data.get("isp") or "").strip() or None,
        "label": ", ".join(parts) if parts else country or None,
        "private": False,
    }


async def lookup_ip_geo(ip: str | None) -> dict | None:
    raw = (ip or "").strip()
    if not raw:
        return None
    if _is_private_ip(raw):
        return {
            "country": None,
            "countryCode": None,
            "region": None,
            "city": None,
            "isp": None,
            "label": "Локальная / частная сеть",
            "private": True,
        }

    cached = _CACHE.get(raw)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    geo = await asyncio.to_thread(_fetch_geo_sync, raw)
    if geo:
        _CACHE[raw] = (time.monotonic(), geo)
    return geo
