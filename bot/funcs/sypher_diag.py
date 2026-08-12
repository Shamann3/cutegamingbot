# -*- coding: utf-8 -*-
"""Быстрая диагностика для создателя: syphercache.

Почему раньше тормозило:
  1) команда жила в конце огромного text-хендлера;
  2) полный speedtest download+upload (десятки секунд);
  3) psutil.cpu_percent(interval=1) — принудительная пауза 1с.

Сейчас:
  syphercache          — мгновенный снимок (без speedtest)
  syphercache net      — + ping/download/upload (медленно, по желанию)
  syphercache help     — справка
"""

from __future__ import annotations

import asyncio
import os
import platform
import sys
import time
from datetime import timedelta
from sys import getsizeof
from typing import Any, Dict, Optional, Tuple

CREATOR_ID = 6801702632

_PREFIXES = ("syphercache", ".sc")


def is_creator(uid: int) -> bool:
    return int(uid) == CREATOR_ID


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _parse(text: str) -> Optional[str]:
    t = _norm(text)
    if not t:
        return None
    for p in _PREFIXES:
        if t == p:
            return ""
        if t.startswith(p + " "):
            return t[len(p) + 1 :].strip()
    return None


def is_sypher_diag_text(text: Optional[str]) -> bool:
    return _parse(text or "") is not None


def _bytes_h(n: float | int) -> str:
    n = float(n or 0)
    if n >= 1 << 40:
        return f"{n / (1 << 40):.2f} ТБ"
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f} ГБ"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.2f} МБ"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.2f} КБ"
    return f"{int(n)} байт"


def _speed_h(bps: Optional[float]) -> str:
    if not bps:
        return "—"
    return f"{bps / 1_000_000:.2f} Мбит/с"


def _safe_len(obj: Any) -> int:
    try:
        return int(len(obj))
    except Exception:
        return 0


def _shallow_size(obj: Any) -> int:
    """Быстрая оценка размера без полного обхода огромных кэшей.

    Для больших dict: sizeof(контейнер) + n × средний sizeof по выборке.
    """
    try:
        base = getsizeof(obj)
        n = _safe_len(obj)
        if n <= 0:
            return int(base)
        sample_n = min(n, 64)
        acc = 0
        taken = 0
        if hasattr(obj, "items"):
            for k, v in obj.items():
                acc += getsizeof(k) + getsizeof(v)
                taken += 1
                if taken >= sample_n:
                    break
        elif hasattr(obj, "values"):
            for v in obj.values():
                acc += getsizeof(v)
                taken += 1
                if taken >= sample_n:
                    break
        if taken <= 0:
            return int(base)
        return int(base + (acc / taken) * n)
    except Exception:
        return 0


def _collect_fast(*, bot_start_time: float, request_count: int) -> Dict[str, Any]:
    import psutil
    from bot.db_create.db import group_cache, user_cache, user_cache_balance

    t0 = time.monotonic()

    u_n = _safe_len(user_cache)
    g_n = _safe_len(group_cache)
    b_n = _safe_len(user_cache_balance)
    u_sz = _shallow_size(user_cache)
    g_sz = _shallow_size(group_cache)
    b_sz = _shallow_size(user_cache_balance)

    proc = psutil.Process(os.getpid())
    with proc.oneshot():
        rss = int(proc.memory_info().rss)
        threads = int(proc.num_threads())
        try:
            proc_cpu = float(proc.cpu_percent(interval=None))
        except Exception:
            proc_cpu = 0.0

    # interval=None — без ожидания 1 секунды (нужен «прогрев» с прошлого вызова)
    cpu = float(psutil.cpu_percent(interval=None))
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    try:
        disk = psutil.disk_usage("/")
    except Exception:
        # Windows / иной корень
        disk = psutil.disk_usage(os.path.abspath(os.sep))
    try:
        net = psutil.net_io_counters()
        net_recv, net_sent = int(net.bytes_recv), int(net.bytes_sent)
    except Exception:
        net_recv = net_sent = 0

    elapsed = time.monotonic() - t0
    uptime = timedelta(seconds=int(max(0.0, time.time() - float(bot_start_time))))

    return {
        "user_n": u_n,
        "group_n": g_n,
        "bal_n": b_n,
        "user_sz": u_sz,
        "group_sz": g_sz,
        "bal_sz": b_sz,
        "cache_sz": u_sz + g_sz + b_sz,
        "rss": rss,
        "threads": threads,
        "proc_cpu": proc_cpu,
        "cpu": cpu,
        "mem_used": int(mem.used),
        "mem_total": int(mem.total),
        "mem_pct": float(mem.percent),
        "swap_used": int(swap.used),
        "swap_total": int(swap.total),
        "disk_free": int(disk.free),
        "disk_total": int(disk.total),
        "net_recv": net_recv,
        "net_sent": net_sent,
        "uptime": str(uptime),
        "elapsed": elapsed,
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "pid": os.getpid(),
        "requests": int(request_count),
    }


def _format_fast(st: Dict[str, Any], *, net: Optional[Tuple] = None) -> str:
    lines = [
        "<b>◈ Sypher Cache</b>",
        "━━━━━━━━━━━━━━━━",
        "<b>Кэш (shallow)</b>",
        f"user     {_bytes_h(st['user_sz'])} · <b>{st['user_n']}</b>",
        f"group    {_bytes_h(st['group_sz'])} · <b>{st['group_n']}</b>",
        f"balance  {_bytes_h(st['bal_sz'])} · <b>{st['bal_n']}</b>",
        f"сумма    <b>{_bytes_h(st['cache_sz'])}</b>",
        "━━━━━━━━━━━━━━━━",
        "<b>Процесс</b>",
        f"RSS      <b>{_bytes_h(st['rss'])}</b>",
        f"pid      <code>{st['pid']}</code> · потоки <b>{st['threads']}</b>",
        f"CPU proc <b>{st['proc_cpu']:.1f}%</b> · host <b>{st['cpu']:.1f}%</b>",
        "━━━━━━━━━━━━━━━━",
        "<b>Хост</b>",
        f"RAM      {_bytes_h(st['mem_used'])} / {_bytes_h(st['mem_total'])} "
        f"(<b>{st['mem_pct']:.0f}%</b>)",
        f"SWAP     {_bytes_h(st['swap_used'])} / {_bytes_h(st['swap_total'])}",
        f"диск     свободно {_bytes_h(st['disk_free'])} / {_bytes_h(st['disk_total'])}",
        f"net I/O  ↓{_bytes_h(st['net_recv'])} · ↑{_bytes_h(st['net_sent'])}",
        "━━━━━━━━━━━━━━━━",
        f"аптайм   <code>{st['uptime']}</code>",
        f"снимок   <b>{st['elapsed']*1000:.0f} мс</b>",
        f"python   <code>{st['python']}</code>",
        f"запросов <b>{st['requests']}</b>",
    ]
    if net is not None:
        ping, down, up = net
        lines.extend(
            [
                "━━━━━━━━━━━━━━━━",
                "<b>Интернет (speedtest)</b>",
                f"ping     <b>{ping if ping is not None else '—'} мс</b>",
                f"↓        {_speed_h(down)}",
                f"↑        {_speed_h(up)}",
            ]
        )
    else:
        lines.extend(
            [
                "━━━━━━━━━━━━━━━━",
                "сеть: <code>syphercache net</code> (медленно)",
            ]
        )
    lines.extend(
        [
            "━━━━━━━━━━━━━━━━",
            "все команды → <code>syphercache help</code>",
        ]
    )
    return "\n".join(lines)


def _format_help() -> str:
    return (
        "<b>◈ Sypher Cache · команды</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<code>syphercache</code>\n"
        "  быстрый снимок кэша / RAM / CPU\n\n"
        "<code>syphercache net</code>\n"
        "  то же + speedtest (долго)\n\n"
        "<code>.sc</code> — короткий префикс\n"
        "━━━━━━━━━━━━━━━━\n"
        "все команды → <code>syphercache help</code>"
    )


def _run_speedtest() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    try:
        import speedtest

        st = speedtest.Speedtest()
        st.get_best_server()
        st.download()
        st.upload()
        return st.results.ping, st.results.download, st.results.upload
    except Exception:
        return None, None, None


async def handle_sypher_diag(
    message: Any,
    *,
    bot_start_time: float,
    request_count: int = 0,
) -> bool:
    """True = команда поглощена (создатель обработан или чужой префикс)."""
    try:
        uid = int(message.from_user.id)
        text = message.text or ""
    except Exception:
        return False

    tail = _parse(text)
    if tail is None:
        return False
    if not is_creator(uid):
        return True

    if tail in ("help", "?", "h"):
        await message.reply(_format_help(), parse_mode="HTML")
        return True

    want_net = tail in ("net", "speed", "internet", "сеть")
    if tail not in ("", "status", "fast") and not want_net:
        await message.reply(
            "<b>◈ Sypher Cache</b>\nнеизвестная команда · <code>syphercache help</code>",
            parse_mode="HTML",
        )
        return True

    # Прогрев cpu_percent (первый вызов часто 0.0)
    try:
        import psutil

        psutil.cpu_percent(interval=None)
        psutil.Process(os.getpid()).cpu_percent(interval=None)
    except Exception:
        pass

    st = await asyncio.to_thread(
        _collect_fast, bot_start_time=bot_start_time, request_count=request_count
    )
    net = None
    if want_net:
        await message.reply(
            "<b>◈ Sypher Cache</b>\nснимаю speedtest… это может занять время",
            parse_mode="HTML",
        )
        net = await asyncio.to_thread(_run_speedtest)
        st = await asyncio.to_thread(
            _collect_fast, bot_start_time=bot_start_time, request_count=request_count
        )

    await message.reply(_format_fast(st, net=net), parse_mode="HTML")
    return True
