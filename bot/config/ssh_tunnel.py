"""Быстрый SSH-туннель через plink перед connect() (только main/remote)."""
from __future__ import annotations

import asyncio
import atexit
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from bot.config.db_config import (
    APP_MODE,
    DB_HOST,
    DB_PORT,
    DB_LOCATION,
    MAIN_DB_TARGET,
    _file_env,
    _safe_log,
)

_PROC: Optional[subprocess.Popen] = None
_STARTED = False
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0


def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _plink_path() -> Optional[Path]:
    for name in ("plink", "plink.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for p in (
        Path(r"C:\Program Files\PuTTY\plink.exe"),
        Path(r"C:\Program Files (x86)\PuTTY\plink.exe"),
    ):
        if p.is_file():
            return p
    return None


def _plink_args() -> List[str]:
    local = int(_file_env("SSH_TUNNEL_PORT", str(DB_PORT)) or str(DB_PORT))
    remote_host = _file_env("SSH_TUNNEL_REMOTE_HOST", "127.0.0.1")
    remote_pg = int(_file_env("SSH_REMOTE_PG_PORT", "5432") or "5432")
    forward = f"{local}:{remote_host}:{remote_pg}"
    ssh_host = _file_env("SSH_HOST", "207.154.219.208")
    ssh_user = _file_env("SSH_USER", "root")
    ssh_port = int(_file_env("SSH_PORT", "22") or "22")
    password = _file_env("SSH_PASSWORD", "")
    session = _file_env("SSH_PUTTY_SESSION", "")
    use_key = _file_env("SSH_USE_KEY", "false").lower() in ("1", "true", "yes", "on")
    key_path = _file_env("SSH_KEY_PATH", "")

    if session:
        return ["-batch", "-load", session, "-N", "-L", forward]
    args = ["-batch", "-ssh", "-P", str(ssh_port), "-l", ssh_user]
    if use_key and key_path:
        args.extend(["-i", key_path])
    elif password:
        args.extend(["-pw", password])
    args.extend(["-N", "-L", forward, ssh_host])
    return args


def _accept_host_key(plink: Path) -> None:
    password = _file_env("SSH_PASSWORD", "")
    if not password or _file_env("SSH_USE_KEY", "false").lower() in ("1", "true", "yes", "on"):
        return
    ssh_host = _file_env("SSH_HOST", "207.154.219.208")
    ssh_user = _file_env("SSH_USER", "root")
    ssh_port = int(_file_env("SSH_PORT", "22") or "22")
    cmd = (
        f'echo y| "{plink}" -ssh -P {ssh_port} -l {ssh_user} '
        f'-pw "{password}" {ssh_host} exit'
    )
    try:
        subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _stop() -> None:
    global _PROC, _STARTED
    if not _STARTED or _PROC is None:
        return
    proc, _PROC = _PROC, None
    _STARTED = False
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


async def ensure_ssh_tunnel() -> None:
    """Если расположение = remote и порт закрыт — поднять plink (для ЛЮБОЙ базы:
    и main, и test). Иначе мгновенный return."""
    if DB_LOCATION != "remote":
        return
    if _port_open(DB_HOST, DB_PORT):
        return

    auto = (_file_env("SSH_AUTO_TUNNEL", "true").lower() not in ("0", "false", "no", "off"))
    if not auto:
        raise RuntimeError(
            f"Порт {DB_HOST}:{DB_PORT} закрыт. Открой туннель WinSCP "
            f"или SSH_AUTO_TUNNEL=true в .env"
        )

    plink = _plink_path()
    if not plink:
        raise RuntimeError(
            "plink.exe не найден. Установи PuTTY или открой туннель WinSCP вручную."
        )
    if not _file_env("SSH_PASSWORD") and not _file_env("SSH_PUTTY_SESSION"):
        raise RuntimeError("SSH_PASSWORD пуст в .env")

    global _PROC, _STARTED
    _safe_log(f"[SSH] Туннель :{DB_PORT} → {_file_env('SSH_HOST')} (plink)...")
    _accept_host_key(plink)
    _PROC = subprocess.Popen(
        [str(plink), *_plink_args()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
    )
    _STARTED = True
    atexit.register(_stop)

    try:
        timeout = float(_file_env("SSH_TUNNEL_START_TIMEOUT", "20"))
    except ValueError:
        timeout = 20.0
    deadline = time.monotonic() + max(5.0, timeout)

    while time.monotonic() < deadline:
        if _port_open(DB_HOST, DB_PORT):
            _safe_log(f"[SSH] Туннель готов :{DB_PORT}")
            return
        if _PROC.poll() is not None:
            break
        await asyncio.sleep(0.15)

    _stop()
    raise RuntimeError(
        f"Не удалось открыть SSH-туннель на {DB_HOST}:{DB_PORT}. "
        f"Проверь SSH_PASSWORD / SSH_HOST в .env"
    )
