"""Детект подозрительных запросов и попыток взлома."""

from __future__ import annotations

import re
from urllib.parse import unquote

from starlette.requests import Request

from error_reporter import schedule_security_alert

_SUSPICIOUS_PATHS = (
    "/admin",
    "/wp-admin",
    "/wp-login",
    "/.env",
    "/.git",
    "/config",
    "/phpmyadmin",
    "/api/v1",
    "/swagger",
    "/docs",
    "/actuator",
    "/../",
    "/cgi-bin",
)

_SQL_PROBE = re.compile(
    r"(union\s+select|drop\s+table|insert\s+into|delete\s+from|"
    r";\s*--|'\s*or\s*'|/\*|\*/|xp_|information_schema)",
    re.IGNORECASE,
)

_SCANNER_UA = re.compile(
    r"(sqlmap|nikto|nmap|masscan|curl/|wget/|python-requests|go-http-client|"
    r"scanner|bot|crawler|spider)",
    re.IGNORECASE,
)


def client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def client_user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "").strip()[:200]


def scan_request(request: Request) -> str | None:
    path = (request.url.path or "").lower()
    query = unquote(str(request.url.query or ""))
    ua = client_user_agent(request)

    if path.startswith("/admin/api/"):
        return None

    for suspicious in _SUSPICIOUS_PATHS:
        if suspicious in path:
            return "ERR_SEC_SCAN_PATH"

    if _SQL_PROBE.search(query):
        return "ERR_SEC_SQL_PROBE"

    if _SCANNER_UA.search(ua) and path.startswith("/api/"):
        return "ERR_SEC_SCANNER"

    return None


def report_if_suspicious(request: Request) -> None:
    code = scan_request(request)
    if not code:
        return
    schedule_security_alert(
        code,
        request=request,
        path=request.url.path,
        method=request.method,
        message=f"IP={client_ip(request)} | UA={client_user_agent(request)} | q={request.url.query}",
        status=404 if code == "ERR_SEC_SCAN_PATH" else 400,
    )
